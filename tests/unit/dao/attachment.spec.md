# Spec — `app/dao/attachment.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092
> **Revision 2026-11-04:** OQ-5 answered by the owner (2026-11-04): attachments follow the record's own visibility; a member who cannot open the private project gets 404 / does not see them. Recorded under FU-1 (c). The check belongs in the attachment service / manager, not in this DAO (it reads one attachment by id and workspace and knows neither the caller nor the record): logged as BUG-1870. No rule of this DAO changes.

> **Review round 2026-11-03.** No owner answer in this round. **Delegated:** P1–P3 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-03). None of them is the owner's own answer.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Soft-deleted parents hide their children; logs are history. Raw lookups stay raw (HR-4 scope). HR-16: a row linking to another workspace's row is invalid data. Refusals list their blockers. BUG-1091 and BUG-1192 already cover the cross-workspace links written by the attachment sign path.
>
> **Verified by running** (throwaway scripts `cat1.py`, `v_att.py` with the harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, nullability, defaults, constraints, indexes, the tables that reference it; found / other workspace / unknown / `0` / pending / failed / deleted for `get_active`; `soft_delete` on other workspace, unknown id, a live row, an already deleted row, an unknown `deleted_by`, inside a rolled-back savepoint; the stored `deleted_at` under the session time zones `UTC`, `America/New_York` and `Asia/Dhaka`; `restore`; the unique index on `(workspace_id, public_id)`; positional calls. **Read, not run:** the callers in `app/managers/attachment_manager.py`, `app/managers/attachment_markup_manager.py`, `app/services/attachment_service.py`. **Not run:** anything over HTTP; Cloudinary.

## Review
> All answered; applied 2026-11-03.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | The time an attachment was deleted is stored shifted by the database's time zone | bug — written as a true UTC moment (BUG-1430) | Claude, delegated |
| P2 | Deleting an attachment that is already deleted deletes it again and overwrites who deleted it | intended at the DAO, like every sibling `soft_delete`; the attachment manager must refuse (FU-1 (a)) | Claude, delegated |
| P3 | `restore` has no caller | remove | Claude, delegated |

### House-rule violations — applied automatically
None.

Checked and **not** a new line here: **HR-4** — `get_active` leaves deleted rows out; `get_by_id_and_workspace` (inherited) stays raw by HR-4 scope; `soft_delete` must see deleted rows to work at all (P2). **HR-6** — `get_active` and the two writes read one row by primary key, so `.first()` has nothing to choose between. **HR-9** — `soft_delete` always changes `is_deleted`, `deleted_at` or `deleted_by` except on the already-deleted case (P2). **HR-10** — a soft delete needs no lock (HR-10 scope); the duplicate side effects of a second delete are the manager's (FU-1 (a)). **HR-16** — every method filters on the row's own `workspace_id`. **HR-1, HR-2, HR-3, HR-5, HR-7, HR-8, HR-15** — no names, lists, paging, `LIKE` or money here.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-03)

### P1. The time an attachment was deleted depends on the database's time zone — 🐞 BUG-1430
**Background:** In the database `attachments.deleted_at` is `timestamptz` (migration `107_audit_timestamptz`), although the model still declares a plain `DateTime`. `soft_delete` writes `utcnow()`, a naive UTC value. Postgres reads a naive value written into a `timestamptz` column as local time in the session's `TimeZone`. The same mismatch on mobile upload sessions was ruled a bug (BUG-1282).
**What happens today:** A delete at 17:08 UTC is stored as 17:08 UTC under `UTC`, as 22:08 UTC under `America/New_York` (the test database's setting) and as 11:08 UTC under `Asia/Dhaka`. (Verified.)
**Example:** The database runs with `TimeZone = Asia/Dhaka`. A user deletes a photo at 17:08 UTC; every reader that converts the moment sees 11:08 UTC, six hours before the delete.
**Rules affected:** `soft_delete` R2
**Answer:** bug — per BUG-1282 precedent: `deleted_at` is written as an aware UTC moment, so the stored instant is the moment of the delete whatever the session's `TimeZone`
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1430 (pattern `aware-datetime-against-naive-column`). A UTC server sees no change; rows already stored need no repair only if production runs in UTC (FU-2). Rules: `soft_delete` R2 (tagged), R2a (untagged).

### P2. Deleting an already deleted attachment deletes it again — ✅ intended at the DAO
**Background:** `soft_delete` finds the row by id and workspace whether or not it is deleted. On factories, machines, sections, departments and maintenance logs the same DAO behaviour was kept, because their managers refuse "already deleted" before calling. `AttachmentManager.delete_attachment` does not: it calls `soft_delete` directly.
**What happens today:** The second call succeeds: `is_deleted` stays `True`, `deleted_at` and `deleted_by` are overwritten with the second call's values. (Verified.)
**Example:** Rahim deletes a drawing at 10:00. Karim sends `DELETE /attachments/{id}/` at 11:00: the answer is 200, the drawing now says Karim deleted it at 11:00, and the manager writes a second `deleted` ledger row and a second "Removed …" activity entry (read, not run).
**Rules affected:** `soft_delete` R4
**Answer:** intended at the DAO — per the factory / machine / maintenance log DAO precedent: the DAO stays raw, and the attachment manager answers 404 `Attachment <id> not found` for an attachment already deleted, as `get_active` would, with nothing written (FU-1 (a))
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rule unchanged. Rules: `soft_delete` R4 ✅.

### P3. `restore` has no caller — 🗑️ remove
**Background:** `restore` clears the deletion flag and stamp. A search of `app/`, `tests/` and `scripts/` finds no call to `attachment_dao.restore`; there is no restore endpoint for attachments.
**What happens today:** It works when called directly (verified), but nothing can reach it.
**Example:** No API request or job can bring back a deleted attachment.
**Rules affected:** `restore` (whole method)
**Answer:** remove — per the subscription plan DAO precedent (`get_by_name`): no caller, dead code
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): moved to **Not specified**, listed in `docs/testing/dead-code-removal-checklist.md` (`app/dao/attachment.py:76`). Not a bug — no BUG ID. If attachments ever get an undo, it is written then, with the Cloudinary file in mind (a ready attachment's file is destroyed on delete).

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Attachment manager / service** (`app/managers/attachment_manager.py`, `app/services/attachment_service.py`, not yet specified) | (a) `delete_attachment` on an attachment already deleted: today 200, a second `deleted` ledger row, a second `attachment_removed` activity entry on every linked parent, and a second Cloudinary destroy call; intended per P2: 404 `Attachment <id> not found`, nothing written. (b) `create_pending_attachment` writes through the inherited `create`; the database refuses a second attachment with the same `(workspace_id, public_id)` (`uq_attachments_workspace_public_id`, 23505), which only a `public_id` collision could reach (it is a random UUID). (c) **OWNER, access — answered by the owner (2026-11-04), OQ-5:** attachments follow the record's own visibility; a member who cannot open the private project gets 404 / does not see them (raised in `tests/unit/dao/attachment_link.spec.md` FU-1 (a): listing and the sign path). For the attachment service spec: 🐞 BUG-1870. | P2, reading the callers; OQ-5 |
| FU-2 | **Production check** | Whether production's database `TimeZone` is `UTC`. If not, `deleted_at` values already stored are shifted (BUG-1430). | P1 |

## Overview
`AttachmentDAO` reads and soft-deletes `attachments`, the metadata of uploaded files (the files live in Cloudinary). Callers: `AttachmentManager` (`get_active` for confirm, the PDF page image and the markup check; `soft_delete` for `DELETE /attachments/{id}/`; inherited `create` and `update` for sign and confirm), `AttachmentMarkupManager._get_ready_attachment`, `AttachmentService.get_attachment`. It is meant to protect workspace isolation: every method of this file filters on the row's `workspace_id`. It flushes, never commits, and takes no lock.

**Callables:** 2 specified · 2 not specified (+ inherited `BaseDAO` methods, base spec)
**Externals to mock:** `utcnow` (`app.dao.attachment.utcnow`), for `soft_delete`.
**Integration-only behavior:** none.

**Model facts (table `attachments`, class `app.models.attachment.Attachment`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `file_name`, `mime_type` | String NOT NULL | — |
| `file_size` | BigInteger NOT NULL | — |
| `uploaded_by` | Integer NOT NULL, FK `profiles.id` | — |
| `uploaded_at` | **`timestamptz`** in the database (model: `DateTime`) NOT NULL | database `now()` |
| `note`, `file_url` | nullable | `NULL` |
| `is_deleted` | Boolean NOT NULL | `False` (Python only) |
| `deleted_at` | **`timestamptz`** in the database (model: `DateTime`), nullable | `NULL` |
| `deleted_by` | Integer nullable, FK `profiles.id` | `NULL` |
| `storage_provider` | String(32) NOT NULL | `'cloudinary'` |
| `resource_type` | String(16) NOT NULL | `'image'` |
| `delivery_type` | String(16) NOT NULL | `'upload'` |
| `upload_status` | String(16) NOT NULL, indexed | `'pending'`; values in use `pending`, `ready`, `failed` (no check constraint) |
| `public_id`, `asset_folder` | String(512) nullable | `NULL` |
| `format` (16), `asset_id` (64), `etag` (64), `version`, `width`, `height`, `page_count` | nullable | `NULL` |

- Indexes: primary key, `ix_attachments_id`, `ix_attachments_workspace_id`, `ix_attachments_public_id`, `ix_attachments_upload_status`, and the **unique** `uq_attachments_workspace_public_id` on `(workspace_id, public_id)` (in the database, not in the model; two `NULL` `public_id`s are allowed). No check constraint, no trigger.
- Referenced by `attachment_links`, `attachment_markups`, `attachment_markup_events`, `project_attachments`, `project_component_attachments` (all ON DELETE CASCADE) and `attachment_ledger` (ON DELETE RESTRICT).
- A value read from the two `timestamptz` columns is an aware `datetime` in the session's time zone.

**Notes for the test designer:**
- Use the singleton `attachment_dao` (`from app.dao.attachment import attachment_dao`). `get_active(db, id, workspace_id)` takes its arguments positionally or by keyword; `soft_delete` takes everything after `db` by keyword only (a positional call raises `TypeError`).
- Build rows directly: `Attachment(workspace_id, file_name, mime_type, file_size, uploaded_by, upload_status=…)`, add and flush. Profiles and workspaces from `tests/unit/factories.py`.
- Patch `app.dao.attachment.utcnow` to a fixed naive value for `soft_delete`.
- **BUG-1430:** set the session's zone with `SET LOCAL TimeZone = 'Asia/Dhaka'` (any zone other than UTC), patch `utcnow` to `datetime(2026, 11, 3, 17, 8)`, call, then read `SELECT deleted_at AT TIME ZONE 'UTC'` from the database. Intended `17:08`; today `11:08` → **strict** xfail. Under `SET LOCAL TimeZone = 'UTC'` the value is `17:08` today and after the fix → plain pass (R2a).
- **Not committed:** `sp = db.begin_nested()`, call, `sp.rollback()`, re-read.

## Not specified
- `AttachmentDAO.restore` — dead code, to be removed (decided by Claude under the reviewer's delegation (2026-11-03); P3).
- `attachment_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods (`create` ← sign, `update` ← confirm, `get_by_id_and_workspace`, `get_by_workspace`, `get`, `get_multi`, `remove`) — not overridden; covered by `tests/unit/dao/base.spec.md`. Callers pass dicts (`AttachmentCreateInternal.model_dump()`, `AttachmentUpdateInternal.model_dump(exclude_unset=True)`).

---

## `AttachmentDAO.get_active(db, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `AttachmentManager.confirm_attachment`, `get_pdf_page_image`; `AttachmentMarkupManager._get_ready_attachment`; `AttachmentService.get_attachment`; each answers "not found" on `None`)

**Purpose:** One attachment that is not deleted, inside a workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `id` | int | equality on the primary key; positional or keyword |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** the `Attachment` instance the session holds, or `None`.

**Rules:**
- **R1.** Given a live row (`is_deleted = False`) with that id in that workspace, it is returned, whatever its `upload_status` (`pending`, `ready` and `failed` all count).
- **R2.** Given a row with that id in another workspace, `None` is returned.
- **R3.** Given an unknown id or `id=0`, `None` is returned, with no error.
- **R4.** Given a soft-deleted row (`is_deleted = True`), `None` is returned. Once `is_deleted` is `False` again, the row is returned.

**Errors:** none.

**Side effects:** none

---

## `AttachmentDAO.soft_delete(db, *, id, workspace_id, deleted_by)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `AttachmentManager.delete_attachment` ← `DELETE /attachments/{id}/`, which answers 404 on `None`)

**Purpose:** Mark one attachment of a workspace deleted, recording who and when.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `id` | int | equality on the primary key |
| `workspace_id` | int | equality on the row's `workspace_id` |
| `deleted_by` | int | stored as is; must be a `profiles.id` (foreign key) |

**Returns:** the changed `Attachment` instance, flushed, not committed; or `None`.

**Rules:**
- **R1.** Given a row with that id in that workspace, it is returned with `is_deleted = True`, `deleted_by` = the given id, and `deleted_at` = the value of `utcnow()`. Nothing else changes (`upload_status`, `public_id`, `file_url` stay).
- **R2.** [BUG-1430] (P1) The stored `deleted_at` is the moment of the call in UTC whatever the session's `TimeZone`: with `utcnow()` = 17:08 and `TimeZone = 'Asia/Dhaka'`, `deleted_at AT TIME ZONE 'UTC'` reads 17:08. *(Today: the naive value is read as local time of the session's zone: 11:08 under `Asia/Dhaka`, 22:08 under `America/New_York`.)*
- **R2a.** Under `TimeZone = 'UTC'` the stored moment is 17:08, today and after the fix.
- **R3.** Given a row with that id in another workspace, an unknown id or `id=0`, `None` is returned and no row changes.
- **R4.** ✅ (P2) Given a row that is already soft-deleted, no error is raised and the stamp is overwritten: `deleted_at` becomes the new `utcnow()` value and `deleted_by` the new id. (The manager must refuse this case before calling, FU-1 (a).)
- **R5.** The change is flushed, not committed: rolling back a savepoint around the call leaves the row live, `deleted_by` `NULL`.
- **R6.** An unknown `deleted_by` raises `IntegrityError` at the flush (`ForeignKeyViolation`, pgcode `23503`).
- **R7.** The linked rows (`attachment_links`, markups, markup events, ledger) are not touched.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `deleted_by` is not a profile | `sqlalchemy.exc.IntegrityError`; `.orig.pgcode == "23503"` | — |
| positional arguments after `db` | `TypeError` | — |

**Side effects:** one row updated and flushed (`is_deleted`, `deleted_at`, `deleted_by`); no commit; nothing external.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 20–21 | positional or keyword arguments | Notes for the test designer |
| 34–40 | workspace AND id AND `is_deleted == False`; `.first()` row / `None` | `get_active` R1, R2, R3, R4 |
| 43 | keyword-only parameters | `soft_delete` Errors |
| 58–63 | workspace AND id, deleted rows included | `soft_delete` R1, R3, R4 |
| 65–66 | `if not attachment` → `None` | `soft_delete` R3 |
| 68–70 | sets flag, `utcnow()` (naive, BUG-1430), `deleted_by` | `soft_delete` R1, R2, R2a, R4, R6 |
| 72–73 | add + flush, no commit | `soft_delete` R5, R7 |
| 76–107 | `restore` | Not specified (P3) |
| 111 | singleton | Not specified |
