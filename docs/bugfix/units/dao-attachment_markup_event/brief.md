# Fix brief: dao-attachment_markup_event

## 1. Unit

| | |
|---|---|
| Slug | `dao-attachment_markup_event` |
| Source file | `app/dao/attachment_markup_event.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-attachment_markup_event` |
| Branch | `bugfix/dao-attachment_markup_event` (from `origin/main`) |
| Risk | `normal` (BUG-1436 `tied-timestamp-no-tiebreak` is on the trivial list; BUG-1437 `silent-result-cap` is not, and it removes a parameter). Not money, stock, order workflow or security: the bugs are about the order and completeness of an attachment's markup history. |

## 2. Bugs

### BUG-1436: Markup history entries of one time come back in no fixed order
- **Pattern:** `tied-timestamp-no-tiebreak`
- **Where:** `AttachmentMarkupEventDAO.list_for_attachment`; reached through the markup history of an attachment (`GET /attachments/{id}/markups/events`).
- **Today:** `ORDER BY created_at DESC` only. Of 30 entries written in a row only 4 times were distinct (coarse clock); three of one time came back `213, 214, 215`, then `214, 215, 213` after one of them was updated.
- **Intended:** HR-6: `created_at` newest first, then `id` descending (BUG-1321 precedent).
- **Precedent BUG-1321, in words:** a list ordered newest first by a date or time keeps that first key and adds `id` descending as the last key.
- **Example:** entries 213, 214 and 215 are saved within the same clock tick, and 216 a minute later. The history must always read `216, 215, 214, 213`, whatever happened to the rows since.

### BUG-1437: Markup history silently stops at the 200 newest entries
- **Pattern:** `silent-result-cap`
- **Where:** `AttachmentMarkupEventDAO.list_for_attachment`; reached through the markup history of an attachment.
- **Today:** Default `limit=200`, never overridden by the caller, no paging: given 201 entries the oldest is left out with no sign.
- **Intended:** All entries are returned, no cap (logs are history; per BUG-982 precedent); the unused `limit` parameter goes with the fix (decided by Claude under the reviewer's delegation (2026-11-03)).
- **Example:** a drawing reviewed for months has 260 markup saves. Today the history shows the latest 200; the first 60, including who first marked the drawing, are missing. After the fix all 260 are listed, newest first.
- **Precedent BUG-982, in words:** a DAO read with a hidden default cap that its caller never overrides returns every matching row; the unused paging parameters are removed with the fix. If a long history ever needs paging, it is added at the endpoint later, not here.
- **Callers of the parameter (checked for this brief):** the only caller in `app/` is `AttachmentMarkupManager.list_events` (`app/managers/attachment_markup_manager.py`), which calls `list_for_attachment(session, workspace_id=..., attachment_id=...)` and **does not pass `limit`**. Nothing in `scripts/` or `alembic/` calls `list_for_attachment`. So removing the parameter breaks no caller. The parameter and its `.limit(...)` call both go.

## 3. Intended behaviour (spec rules, copied)

Facts for the whole file: table `attachment_markup_events`, the append-only history of markup saves, updates and clears on an attachment. Columns: `id` Integer PK (sequence); `workspace_id` Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE; `attachment_id` Integer NOT NULL, FK `attachments.id` ON DELETE CASCADE; `user_id` Integer NOT NULL, FK `profiles.id` ON DELETE CASCADE; `session_id` String(36) nullable, indexed, default `NULL`; `event_type` String(32) NOT NULL (written values `markup_saved`, `markup_updated`, `markup_cleared`); `description` Text NOT NULL; `metadata_json` `json` nullable (Python `None` is stored as JSON `null`); `created_at` `timestamp` (no zone) NOT NULL, Python default `utcnow()` (naive UTC). Indexes: primary key, `workspace_id`, `attachment_id`, `session_id`, and `(attachment_id, created_at)`. No check constraint, no trigger. Hard-deleting the attachment, the user or the workspace deletes the entries. The class flushes, never commits, never updates or deletes a row, and takes no lock. Every parameter after `db` is keyword-only. The module-level singleton `attachment_markup_event_dao` stays.

Callers: `AttachmentMarkupManager._log_markup_event` (`create_event`, after a layer is saved or cleared) and `AttachmentMarkupManager.list_events` (`list_for_attachment`). The manager's history rule says: order and completeness are exactly this DAO's R3 and R4 (no 200 cap).

### `AttachmentMarkupEventDAO.list_for_attachment(db, *, workspace_id, attachment_id)` (today also `limit=200`, which goes with BUG-1437)
The markup history of one attachment, newest first. Returns a `list` of `AttachmentMarkupEvent` (possibly empty).
- **R1.** Returns the entries of that attachment with that `workspace_id`; entries of another attachment never.
- **R2.** Entries with another `workspace_id` are not returned; an unknown attachment id or `0` returns `[]`.
- **R3.** [BUG-1436] (HR-6) Ordered by `created_at` newest first, then `id` descending: a later entry comes first, then entries of one time highest `id` first, also after one of them was updated. *(Today: `created_at` only; verified `213, 214, 215` → `214, 215, 213` after an update.)*
- **R4.** [BUG-1437] Every matching entry is returned: given 201, 201. *(Today: at most 200, the newest by R3.)* Of 201 entries, the first 200 returned are still the newest 200, newest first.
- **R5.** The attachment's state is not looked at: the entries of a soft-deleted attachment are returned (event logs are history; the manager answers 404 for a deleted attachment before it calls this).
- Errors: none reachable from the caller. (Today a negative `limit` passed directly raises `DataError` and `limit=0` returns `[]`; both go away with the parameter.)
- Side effects: none.

### `AttachmentMarkupEventDAO.create_event(db, *, workspace_id, attachment_id, user_id, event_type, description, session_id=None, metadata_json=None)` (not in a bug; must not change)
Appends one entry to an attachment's markup history. Returns the new row, flushed, not committed.
- **R1.** A row is created with the given values; `id` is set; `created_at` is `utcnow()` at the flush (naive UTC, equal to the database's `now() AT TIME ZONE 'UTC'` within a second).
- **R2.** `session_id` and `metadata_json` default to `None`. A `metadata_json` of `None` is stored as the JSON value `null` (`metadata_json IS NULL` is false) and reads back as `None`; a dict is stored and read back as given.
- **R3.** Nothing is validated: empty `event_type` and `description` are stored. A `session_id` over 36 or an `event_type` over 32 characters raises `DataError` (pgcode `22001`); `description=None` raises `IntegrityError` (pgcode `23502`); an unknown `attachment_id` or `user_id` raises `IntegrityError` (pgcode `23503`).
- **R4.** Flushed, not committed: rolling back a savepoint removes the row.
- Errors: as in R3. Side effects: one row inserted and flushed.

### Inherited `BaseDAO` methods
No caller on this DAO; they stay as they are.

## 4. Rules that apply

- **HR-6. Every paged or top-N result has a stable order.** No order recipe counts as deterministic unless it ends in `id`. Where a list already has a chosen first key (here: `created_at` newest first), keep it and add `id` after it (here descending, to match newest first).
- **Event logs are history** (the owner's ledger ruling, 2026-10-30): they are never trimmed or hidden, and a soft-deleted parent does not hide them. This is why the cap goes rather than being raised.
- **HR-7** (`limit` is at least 1, enforced at list endpoints) does not apply here: after the fix this method takes no `limit` at all. Do not add paging to the endpoint in this unit.
- **HR-16:** reads filter on the row's `workspace_id`. Keep that filter exactly as it is.
- No owner answer (OQ-n) touches these bugs.

## 5. Scope

- May change: `app/dao/attachment_markup_event.py` only.
- No migration, no schema change, no API response change (the history endpoint returns the same shape; only more entries and a fixed order among ties).
- The method's signature loses `limit`; `db`, `workspace_id`, `attachment_id` stay, keyword-only after `db`, with the same return type. `create_event` is unchanged.

## 6. Out of scope (leave alone)

No other open bug is in `app/dao/attachment_markup_event.py`. In its caller `app/managers/attachment_markup_manager.py` (not to be changed in this unit):
- **BUG-2115:** any member sees and draws marks on attachments of a private project or another member's help ticket.
- **BUG-2116:** markup layers send an author's old image stamp even when it names another file.
- **BUG-2117:** markup layers send a stamp picture address the browser chose.
- **BUG-2118:** saving unchanged marks writes a "markup_updated" history entry.
- **BUG-2119:** markup layers and history read the author's profile once or twice per row (the history's profile reads are not batched; leave that to its own unit).
- **BUG-2120:** two first saves of one user's layer at once: the second answers 500.
- In the neighbouring `app/dao/attachment_markup.py` (markup layers, a different file): **BUG-1435** (layers saved at one moment come back in no fixed order).
