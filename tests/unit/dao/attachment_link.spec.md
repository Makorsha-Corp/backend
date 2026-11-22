# Spec — `app/dao/attachment_link.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092
> **Revision 2026-11-04:** FU-1 (a)'s OWNER access item answered by the owner (2026-11-04), OQ-5: attachments follow the record's own visibility; a member who cannot open the private project gets 404 / does not see them. The check belongs in the attachment service / manager (this DAO knows neither the caller nor the record's visibility): BUG-1870. No rule of this DAO changes.

> **Review round 2026-11-03.** No owner answer in this round. **Delegated:** P1–P4 and Q1 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-03). None of them is the owner's own answer. The house-rule lines stand.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Soft-deleted parents hide their children; logs are history. Raw lookups stay raw (HR-4 scope). HR-16: a row linking to another workspace's row is invalid data, and no response shows another workspace's ids or names. **BUG-1091 and BUG-1192 already cover the cross-workspace links written by the attachment sign path** (`POST /attachments/sign` never checks the entity), so nothing is logged for that here.
>
> **Verified by running** (throwaway scripts `cat1.py`, `v_link.py` with the harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints and indexes; `AttachmentLinkCreateSchema` with keywords, positionally and with a missing argument; inherited `create` with the schema's dict and with the schema object; the unique constraint, also across workspaces; a 65-character `entity_type`; `now()` as a naive value under three session time zones; the attachment list and the count with ready, pending, failed and deleted attachments, another entity id, another entity type, another workspace, an unknown id, `entity_type` in another case, and a link of workspace A to an attachment of workspace B; order with four attachments, three sharing one `uploaded_at`, under a forced sequential scan before and after an update; paging, `limit=0`, negative values, 101 attachments; the links of one attachment before and after an update, in another workspace, unknown, of a deleted attachment; the SQL of both reads; `get_by_entity`; the cascade from a deleted attachment. **Not run:** anything over HTTP; two concurrent transactions.

## Review
> All answered; applied 2026-11-03.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | A failed upload keeps using up one of the record's 25 attachment places, and the user cannot see it to delete it | bug — failed uploads do not count (BUG-1434) | Claude, delegated |
| P1 | The time a link was made is stored in the database's local time | bug — naive UTC (BUG-1431) | Claude, delegated |
| P2 | The attachment list does not look at whether the record it belongs to still exists or is deleted | intended at the DAO; the attachment service checks the record (FU-1 (a)) | Claude, delegated |
| P3 | `get_by_entity` has no caller | remove | Claude, delegated |
| P4 | Inherited `create` fails when given the create schema object itself | intended — callers pass its `model_dump()` | Claude, delegated |

Decided by house rules: attachments uploaded at the same moment come back in no fixed order (BUG-1432); the links of one attachment have no order (BUG-1433).

### House-rule violations — applied automatically

- **HR-6** `get_attachments_for_entity` R6 — ordered by `uploaded_at` newest first, nothing after it. `uploaded_at` is the database's `now()`, the transaction's start, so attachments signed in one transaction share it; separate requests rarely tie. Verified under a forced sequential scan: three attachments with one `uploaded_at` came back lowest `id` last after nothing but an update, and paging `limit=2` moved them between pages. Intended: `uploaded_at` newest first, then `id` descending, before `skip` / `limit` (BUG-1321 precedent).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1432 (pattern `tied-timestamp-no-tiebreak`). Rules: `get_attachments_for_entity` R6.
- **HR-6** `get_links_for_attachment` R4 — no `ORDER BY`. Its callers take `links[0]` as "the" entity of a ledger row (`_append_attachment_ledger`), and build the `links` list of every attachment response. Verified: three links came back `a, b, c`, then `b, c, a` after an update of `a`. Intended: `id` ascending (the order the links were made).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1433 (pattern `unordered-pagination`). Rules: `get_links_for_attachment` R4.

Checked and **not** a new line here: **HR-4** — the attachment list leaves deleted attachments out and does not count them (R3, `count_linked_attachments_for_entity` R2); `get_links_for_attachment` returns the links of a deleted attachment on purpose: the delete flow reads them after the soft delete to write the "Removed …" entries (R5). The parent record's state is P2. **HR-5** — every filter is in the query. **HR-7** — `GET /attachments/` already requires `skip >= 0` and `1 <= limit <= 200`. **HR-8** — no `LIKE`. **HR-16** — reads compare the link's `workspace_id` only, never the attachment's (R2 of each read): a link of workspace A to an attachment of B shows B's file to A. Such a link is invalid data that no writer produces (the sign path writes the attachment and its link under one workspace); refusing it is the writer's job (BUG-1091, BUG-1192 for the entity side). **HR-9, HR-10** — the DAO writes nothing of its own. **HR-1, HR-2, HR-3, HR-15** — `entity_type` is an enum value written by code; no names or money.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-03)

### P1. The time a link was made is stored in the database's local time — 🐞 BUG-1431
**Background:** `attachment_links.linked_at` is a plain `timestamp` (no zone) whose default is the database's `now()`. Stored that way, `now()` becomes the local time of the session's `TimeZone`; the rest of the code reads such columns as UTC. The same default on product ledger entries was ruled a bug (BUG-1337).
**What happens today:** At 14:17 UTC the default stores 14:17 under `UTC`, 09:17 under `America/New_York` (the test database's setting) and 20:17 under `Asia/Dhaka`. (Verified with `now()::timestamp`.)
**Example:** The database runs in `Asia/Dhaka`. A link made at 14:17 UTC says 20:17; any report that treats it as UTC is six hours out. No response shows `linked_at` today.
**Rules affected:** inherited R2
**Answer:** bug — per BUG-1337 precedent: `linked_at` defaults to `utcnow()`, naive UTC
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1431 (pattern `database-clock-timestamp`). The fix is in `app/models/attachment_link.py`. Rules: inherited R2 (tagged).

### P2. The attachment list does not look at the record it belongs to — ✅ intended at the DAO
**Background:** A link names its record only by `entity_type` and `entity_id` (purchase order, project, machine, …); there is no foreign key, so the DAO cannot join the record's table. Projects, machines, items and orders have soft delete; the standing decision is that a soft-deleted parent hides its children.
**What happens today:** `get_attachments_for_entity` and `count_linked_attachments_for_entity` return the attachments and count of any `(entity_type, entity_id)`, whether the record exists, is deleted, or belongs to another workspace. (Verified for an id with no record.)
**Example:** Machine "Press 4" is deleted. `GET /attachments/?entity_type=machine&entity_id=<Press 4>` still lists its 3 photos.
**Rules affected:** `get_attachments_for_entity` R7, `count_linked_attachments_for_entity` R4
**Answer:** intended at the DAO — the polymorphic link cannot reach its parent; `AttachmentService.list_attachments` (and the sign path) must look the record up first and answer 404 for an unknown, other-workspace or soft-deleted record (FU-1 (a))
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rules unchanged. Rules: `get_attachments_for_entity` R7 ✅, `count_linked_attachments_for_entity` R4 ✅.

### P3. `get_by_entity` has no caller — 🗑️ remove
**Background:** `get_by_entity` returns the link rows of one record, unordered, 100 at a time. A search of `app/`, `tests/` and `scripts/` finds no call to `attachment_link_dao.get_by_entity` (the `get_by_entity` calls in `app/` belong to the discussion and financial audit log DAOs).
**What happens today:** It works when called directly (verified), but nothing reaches it.
**Example:** No API request lists link rows; `GET /attachments/` uses `get_attachments_for_entity`.
**Rules affected:** `get_by_entity` (whole method)
**Answer:** remove — per the subscription plan DAO precedent: no caller, dead code
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): moved to **Not specified**, listed in `docs/testing/dead-code-removal-checklist.md` (`app/dao/attachment_link.py:42`). Its missing `ORDER BY` goes with it, so no bug is logged. Not a bug — no BUG ID.

### P4. Inherited `create` fails when given the schema object — ✅ intended
**Background:** `AttachmentLinkCreateSchema` is a plain class, not a Pydantic model: its `model_dump()` takes no arguments. The inherited `create` calls `model_dump(by_alias=True)` on anything that is not a dict.
**What happens today:** `create(obj_in=AttachmentLinkCreateSchema(…))` raises `TypeError` (`model_dump() got an unexpected keyword argument 'by_alias'`) and nothing is added; `create(obj_in=schema.model_dump())` works. The only caller passes the dict. (Verified.)
**Example:** None reachable: `create_pending_attachment` passes `link_data.model_dump()`.
**Rules affected:** `AttachmentLinkCreateSchema.model_dump` R3
**Answer:** intended — the one caller passes the dict; making the class a Pydantic model is a refactor, not a fix
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rule unchanged. Rules: `AttachmentLinkCreateSchema.model_dump` R3 ✅.

### New questions

### Q1. A failed upload keeps using up one of the record's attachment places — 🐞 BUG-1434
**Background:** A record may have at most `MAX_ATTACHMENTS_PER_ENTITY` attachments (25). Signing an upload first counts the record's attachments with `count_linked_attachments_for_entity` and refuses at 25 (`This record already has the maximum of 25 attachments.`); the list endpoint returns the same count as `slot_count`. The count takes every attachment that is not deleted, in any upload state: `pending` (signed, upload not confirmed), `ready` and `failed` (Cloudinary could not verify it). The list itself shows only `ready` ones. The docstring says "all upload statuses" on purpose: an upload in flight must hold its place.
**What happens today:** A `failed` attachment counts for ever. It never appears in the list, so the user cannot find it to delete it. (Verified: one ready, one pending, one failed, one deleted → count 3, list 1.)
**Example:** A purchase order has 20 photos. Five uploads fail on a bad connection. The list shows 20 photos and "25 of 25", and the next upload is refused, although only 20 files are there; the user has nothing to delete.
**Rules affected:** `count_linked_attachments_for_entity` R1
**Suggested answer:** `bug — failed attachments do not count; pending ones still do (an upload in flight holds its place)`. Alternative: count only `ready` ones, accepting that two uploads in flight can pass 25 together; or keep counting and show failed uploads in the list so they can be deleted.
**Answer:** bug — failed attachments do not count; pending ones still do
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1434 (pattern `failed-attempt-holds-capacity`). A `pending` row that is never confirmed still holds its place; cleaning those up is the attachment manager's (FU-1 (b)). Rules: `count_linked_attachments_for_entity` R1 (tagged), R1a (untagged).

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Attachment service / manager** (`app/services/attachment_service.py`, `app/managers/attachment_manager.py`) | (a) `list_attachments` never looks the record up: any `(entity_type, entity_id)` is listed, including an unknown id, a soft-deleted record (standing decision: hidden) and another workspace's id (empty, by the link's `workspace_id`). Intended per P2: 404 for an unknown, other-workspace or soft-deleted record. **OWNER, access:** the list also ignores who may see the record: a private project's attachments are listed to any member of the workspace (read, not run). Same for `POST /attachments/sign` and the sign path's capacity check. **Answered by the owner (2026-11-04), OQ-5:** attachments follow the record's visibility; who cannot open the private project (`ProjectManager.can_access_project`; a component by its project) gets 404 and sees nothing — 🐞 BUG-1870, for the attachment service spec. (b) A `pending` attachment whose upload is never confirmed holds a place for ever (Q1); a clean-up of old pending rows, or an age limit in the count, belongs to the manager. (c) `_append_attachment_ledger` takes `links[0]` as the ledger's entity; with BUG-1433 that is the first link made. | P2, Q1, HR-6 line |

## Overview
`AttachmentLinkDAO` reads `attachment_links`, which ties an attachment to the record it belongs to, named by `entity_type` and `entity_id` (a polymorphic link, no foreign key to the record). Callers: `AttachmentManager` (capacity check on sign, inherited `create` on sign, the links of an attachment for ledger rows, activity entries and every attachment response) and `AttachmentService.list_attachments` (`GET /attachments/`). It is meant to protect workspace isolation through the link's own `workspace_id`. It never writes on its own, never commits and takes no lock. `AttachmentLinkCreateSchema` is the plain create payload.

**Callables:** 4 specified (+ inherited `create`) · 2 not specified
**Externals to mock:** none. No method reads the clock.
**Integration-only behavior:** none.

**Model facts (table `attachment_links`, class `app.models.attachment_link.AttachmentLink`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `attachment_id` | Integer NOT NULL, FK `attachments.id` ON DELETE CASCADE | — |
| `entity_type` | String(64) NOT NULL | — (values in use: `AttachmentEntityTypeEnum`, lowercase, e.g. `purchase_order`, `project`, `machine`, `support_ticket`) |
| `entity_id` | Integer NOT NULL, no foreign key | — |
| `linked_at` | `timestamp` (no zone) NOT NULL | database `now()` (BUG-1431) |
| `linked_by` | Integer NOT NULL, FK `profiles.id` | — |

- Unique constraint `uq_attachment_link_entity` on `(attachment_id, entity_type, entity_id)` — **without** `workspace_id`. Indexes: primary key, `ix_attachment_links_attachment_id`, `ix_attachment_links_workspace_entity` `(workspace_id, entity_type, entity_id)`. No check constraint, no trigger. Hard-deleting an attachment deletes its links.
- `Attachment` facts: see `tests/unit/dao/attachment.spec.md` Overview (`uploaded_at` is `timestamptz`, database `now()`; `upload_status` `pending` / `ready` / `failed`; `is_deleted`).

**Notes for the test designer:**
- Use the singleton `attachment_link_dao`. Every parameter after `db` is keyword-only in the three reads.
- Build attachments and links directly (add + flush): `Attachment(workspace_id, file_name, mime_type, file_size, uploaded_by, upload_status)`, `AttachmentLink(workspace_id, attachment_id, entity_type, entity_id, linked_by)`. Rows made in one transaction share `uploaded_at`; to give one an older time, `UPDATE attachments SET uploaded_at = now() - interval '1 day'`.
- **Order bugs (BUG-1432, BUG-1433):** the physical order of the test database is not deterministic; with no tie-break today's result may equal the intended one. Follow the base spec note: `SET LOCAL enable_indexscan = off; SET LOCAL enable_bitmapscan = off; SET LOCAL enable_indexonlyscan = off`, then update the lowest-`id` row (any column) so its new version lands last. Verified to give lowest `id` last on both reads. Write to the intended order; **non-strict** xfail. Every other case compares **sets** of ids.
- **BUG-1431:** under `SET LOCAL TimeZone = 'Asia/Dhaka'`, flush a link without `linked_at` and compare it with `SELECT now() AT TIME ZONE 'UTC'` (equal, intended) — today it equals `now()::timestamp` → **strict** xfail.
- **BUG-1434:** one `ready`, one `pending`, one `failed`, one deleted attachment on a record: intended count 2, today 3 → **strict** xfail.

## Not specified
- `AttachmentLinkDAO.get_by_entity` — dead code, to be removed (decided by Claude under the reviewer's delegation (2026-11-03); P3).
- `attachment_link_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods other than `create` — no caller on this DAO; base spec.

---

## `AttachmentLinkCreateSchema(*, workspace_id, attachment_id, entity_type, entity_id, linked_by)` and `.model_dump()`
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (used by: `AttachmentManager.create_pending_attachment`)

**Purpose:** Carry the five values of a new link and hand them over as a dict.

**Rules:**
- **R1.** The constructor takes the five values by keyword only and stores them unchanged, with no validation (any type, any value, `None` included). A positional call, or a missing argument, raises `TypeError`.
- **R2.** `model_dump()` returns exactly `{"workspace_id", "attachment_id", "entity_type", "entity_id", "linked_by"}` with the stored values, and nothing else.
- **R3.** ✅ (P4) `model_dump()` accepts no arguments: passing the object itself to the inherited `create` raises `TypeError` (`unexpected keyword argument 'by_alias'`) and nothing is added. Passing `model_dump()`'s dict creates the link (inherited R1).

**Errors:** `TypeError` as in R1, R3.

**Side effects:** none

---

## `AttachmentLinkDAO.get_attachments_for_entity(db, *, workspace_id, entity_type, entity_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `AttachmentService.list_attachments` ← `GET /attachments/?entity_type=…&entity_id=…`, with the caller's `skip` / `limit`)

**Purpose:** The ready, live attachments of one record, newest first, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality on the **link's** `workspace_id` |
| `entity_type` | str | exact, case-sensitive equality |
| `entity_id` | int | equality; not validated |
| `skip`, `limit` | int, defaults `0`, `100` | not validated |

**Returns:** a `list` of `Attachment` instances (possibly empty).

**Rules:**
- **R1.** Returns the attachments linked to that `(entity_type, entity_id)` by a link of that workspace. Another entity id or another entity type is never matched; `entity_type` in another case (`"Project"`) matches nothing.
- **R2.** Workspace isolation follows the link: links of another workspace are never followed. Only the link's `workspace_id` is compared, not the attachment's: a link of workspace A to an attachment of workspace B returns that attachment for A and not for B (HR-16: invalid data no writer produces).
- **R3.** Only attachments with `is_deleted = False` **and** `upload_status = 'ready'` are returned; `pending`, `failed` and deleted ones are left out and take no place in the page.
- **R4.** An unknown entity id, `entity_id=0`, or a record with no links returns `[]`.
- **R5.** At most `limit` rows after skipping `skip`; with the defaults at most 100: given 101 ready attachments, exactly 100. `limit=0` or `skip` past the end returns `[]`. A negative `limit` or `skip` raises `DataError` (pgcode `2201W` / `2201X`), as base `get_by_workspace`.
- **R6.** [BUG-1432] (HR-6) Ordered by `uploaded_at` newest first, then `id` descending, before `skip` / `limit`: of an attachment a day older and three sharing one `uploaded_at`, the three come first, highest `id` first, and the older one last; consecutive pages neither repeat nor skip. *(Today: `uploaded_at` only; among equal times the order is whatever the database produces — verified lowest `id` moved from first to last after an update.)*
- **R7.** ✅ (P2) The record named by `entity_type` / `entity_id` is not looked at: it may not exist, be soft-deleted, or belong to another workspace.

**Errors:** `sqlalchemy.exc.DataError` for a negative `skip` / `limit`.

**Side effects:** none

---

## `AttachmentLinkDAO.count_linked_attachments_for_entity(db, *, workspace_id, entity_type, entity_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `AttachmentManager.assert_entity_attachment_capacity` ← `POST /attachments/sign`, refusing at `MAX_ATTACHMENTS_PER_ENTITY`; `AttachmentService.list_attachments` as `slot_count`)

**Purpose:** How many of the record's attachment places are taken.

**Returns:** an `int` ≥ 0.

**Rules:**
- **R1.** [BUG-1434] (Q1) Counts the attachments with `is_deleted = False` and `upload_status` other than `failed` (`pending` and `ready`) linked to that `(entity_type, entity_id)` by a link of that workspace: one ready, one pending, one failed, one deleted → 2. *(Today: failed ones count too → 3.)*
- **R1a.** Deleted attachments never count, and a `pending` one counts, today and after the fix.
- **R2.** No cap and no paging: given 101 ready attachments, 101.
- **R3.** Matching and workspace isolation as `get_attachments_for_entity` R1, R2, R4 (an unknown or `0` entity id → `0`).
- **R4.** ✅ (P2) The record itself is not looked at, as `get_attachments_for_entity` R7.

**Errors:** none.

**Side effects:** none

---

## `AttachmentLinkDAO.get_links_for_attachment(db, *, workspace_id, attachment_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `AttachmentManager._append_attachment_ledger` (first link = the ledger's entity), `_log_attachment_entity_events` (one activity entry per link), `to_response` (the response's `links`))

**Purpose:** Every record one attachment is linked to.

**Returns:** a `list` of `AttachmentLink` instances (possibly empty).

**Rules:**
- **R1.** Returns every link of that attachment with that `workspace_id`, whatever the entity type; no paging, no cap.
- **R2.** Links of the attachment under another `workspace_id` are not returned (only the link's `workspace_id` is compared).
- **R3.** An unknown `attachment_id` or `0` returns `[]`.
- **R4.** [BUG-1433] (HR-6) Ordered by `id` ascending: links made `a`, `b`, `c` come back `a`, `b`, `c` also after `a` is updated. *(Today: no ordering is requested; verified `b, c, a` after an update of `a`.)*
- **R5.** The attachment's state is not looked at: the links of a soft-deleted attachment are returned (the delete flow needs them).

**Errors:** none.

**Side effects:** none

---

## Inherited `BaseDAO.create` on `AttachmentLink`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `AttachmentManager.create_pending_attachment`, with `AttachmentLinkCreateSchema(...).model_dump()`)

**Rules:**
- **R1.** With the dict of the five values, a link is created and flushed; `id` is set.
- **R2.** [BUG-1431] (P1) `linked_at`, when not given, is the moment of the insert in UTC, naive, whatever the session's `TimeZone`. *(Today: the database's `now()` stored as local time of the session's zone: 09:17 under `America/New_York` at 14:17 UTC.)*
- **R3.** A second link for the same `(attachment_id, entity_type, entity_id)` raises `IntegrityError` (`UniqueViolation`, pgcode `23505`, `uq_attachment_link_entity`), also when it carries another `workspace_id`. The same attachment may be linked to other records.
- **R4.** An `entity_type` longer than 64 characters raises `DataError` (pgcode `22001`). An unknown `attachment_id`, `workspace_id` or `linked_by` raises `IntegrityError` (pgcode `23503`).
- **R5.** Hard-deleting the attachment deletes its links (ON DELETE CASCADE).

**Errors:** as in R3, R4.

**Side effects:** one row inserted and flushed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 14–27 | keyword-only constructor, values stored unchecked | `AttachmentLinkCreateSchema` R1 |
| 29–36 | fixed five-key dict; no parameters | `AttachmentLinkCreateSchema` R2, R3 |
| 42–64 | `get_by_entity` | Not specified (P3) |
| 77–78 | join attachments ↔ links on the attachment id | `get_attachments_for_entity` R1, R2 |
| 80–86 | link workspace, type, id; `is_deleted == False`; `upload_status == "ready"` | `get_attachments_for_entity` R1–R4, R7 |
| 88 | `uploaded_at DESC` only (BUG-1432) | `get_attachments_for_entity` R6 |
| 89–90 | offset / limit; defaults; `0`; negative | `get_attachments_for_entity` R5 |
| 105–115 | same join and filters without the status filter (BUG-1434); `.count()` | `count_linked_attachments_for_entity` R1, R1a, R2, R3, R4 |
| 127–134 | link workspace and attachment id; no order (BUG-1433); attachment state not read | `get_links_for_attachment` R1–R5 |
| 138 | singleton | Not specified |
| `base.py` 76–84 | `create`: dict / non-dict → `model_dump(by_alias=True)`; constraints; `linked_at` default (BUG-1431) | inherited R1–R5; `AttachmentLinkCreateSchema` R3 |
