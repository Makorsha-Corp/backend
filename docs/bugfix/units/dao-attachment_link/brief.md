# Fix brief: dao-attachment_link

## 1. Unit

| | |
|---|---|
| Slug | `dao-attachment_link` |
| Source file | `app/dao/attachment_link.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-attachment_link` |
| Branch | `bugfix/dao-attachment_link` (from `origin/main`) |
| Risk | `normal` (BUG-1432 and BUG-1433 are trivial-list patterns; BUG-1434 `failed-attempt-holds-capacity` is not on the list) |

## 2. Bugs

### BUG-1432: Attachments with one upload time come back in no fixed order
- **Pattern:** `tied-timestamp-no-tiebreak`
- **Where:** `AttachmentLinkDAO.get_attachments_for_entity`; reached through `GET /attachments/`.
- **Today:** `ORDER BY uploaded_at DESC` only; under a forced sequential scan three attachments of one time moved lowest `id` from first to last after an update, and between pages of 2.
- **Intended:** HR-6: `uploaded_at` newest first, then `id` descending, before `skip` / `limit`.

### BUG-1433: The links of one attachment have no order
- **Pattern:** `unordered-pagination`
- **Where:** `AttachmentLinkDAO.get_links_for_attachment`; read by every attachment response and by the attachment ledger / activity writes.
- **Today:** No `ORDER BY`: links `a, b, c` came back `b, c, a` after an update of `a`; `_append_attachment_ledger` takes `links[0]` as the ledger's entity.
- **Intended:** HR-6: `id` ascending.

### BUG-1434: A failed upload keeps using up one of the record's 25 attachment places
- **Pattern:** `failed-attempt-holds-capacity`
- **Where:** `AttachmentLinkDAO.count_linked_attachments_for_entity`; reached through the `POST /attachments/sign` capacity check and `slot_count` of `GET /attachments/`.
- **Today:** Every attachment not deleted counts, `failed` included; failed ones never show in the list, so the user cannot delete them and the record can be refused at "25" with fewer files.
- **Intended:** Attachments with `upload_status = 'failed'` do not count; `pending` ones still do (decided by Claude under the reviewer's delegation (2026-11-03)).
- **Why:** a `pending` attachment is an upload in flight and must hold its place; a `failed` one is never shown and cannot be removed by the user. Example: a purchase order has 20 photos and five uploads failed; today the list shows 20 photos and "25 of 25" and the next upload is refused. After the fix the count is 20.

## 3. Intended behaviour (spec rules, copied)

### `AttachmentLinkDAO.get_attachments_for_entity(db, *, workspace_id, entity_type, entity_id, skip=0, limit=100)`
The ready, live attachments of one record, newest first, one page at a time. Returns a list of `Attachment` (possibly empty).

- **R1.** Returns the attachments linked to that `(entity_type, entity_id)` by a link of that workspace. Another entity id or another entity type is never matched; `entity_type` in another case (`"Project"`) matches nothing.
- **R2.** Workspace isolation follows the link: links of another workspace are never followed. Only the link's `workspace_id` is compared, not the attachment's.
- **R3.** Only attachments with `is_deleted = False` **and** `upload_status = 'ready'` are returned; `pending`, `failed` and deleted ones are left out and take no place in the page.
- **R4.** An unknown entity id, `entity_id=0`, or a record with no links returns `[]`.
- **R5.** At most `limit` rows after skipping `skip`; with the defaults at most 100: given 101 ready attachments, exactly 100. `limit=0` or `skip` past the end returns `[]`. A negative `limit` or `skip` raises `DataError` (pgcode `2201W` / `2201X`).
- **R6.** [BUG-1432] (HR-6) Ordered by `uploaded_at` newest first, then `id` descending, before `skip` / `limit`: of an attachment a day older and three sharing one `uploaded_at`, the three come first, highest `id` first, and the older one last; consecutive pages neither repeat nor skip. (Today: `uploaded_at` only.)
- **R7.** The record named by `entity_type` / `entity_id` is not looked at: it may not exist, be soft-deleted, or belong to another workspace (the attachment service owns that check).

### `AttachmentLinkDAO.count_linked_attachments_for_entity(db, *, workspace_id, entity_type, entity_id)`
How many of the record's attachment places are taken. Returns an `int` >= 0.

- **R1.** [BUG-1434] Counts the attachments with `is_deleted = False` and `upload_status` other than `failed` (`pending` and `ready`) linked to that `(entity_type, entity_id)` by a link of that workspace: one ready, one pending, one failed, one deleted -> 2. (Today: failed ones count too -> 3.)
- **R1a.** Deleted attachments never count, and a `pending` one counts, today and after the fix.
- **R2.** No cap and no paging: given 101 ready attachments, 101.
- **R3.** Matching and workspace isolation as `get_attachments_for_entity` R1, R2, R4 (an unknown or `0` entity id -> `0`).
- **R4.** The record itself is not looked at, as `get_attachments_for_entity` R7.

### `AttachmentLinkDAO.get_links_for_attachment(db, *, workspace_id, attachment_id)`
Every record one attachment is linked to. Returns a list of `AttachmentLink` (possibly empty).

- **R1.** Returns every link of that attachment with that `workspace_id`, whatever the entity type; no paging, no cap.
- **R2.** Links of the attachment under another `workspace_id` are not returned (only the link's `workspace_id` is compared).
- **R3.** An unknown `attachment_id` or `0` returns `[]`.
- **R4.** [BUG-1433] (HR-6) Ordered by `id` ascending: links made `a`, `b`, `c` come back `a`, `b`, `c` also after `a` is updated. (Today: no ordering is requested.)
- **R5.** The attachment's state is not looked at: the links of a soft-deleted attachment are returned (the delete flow needs them).

Facts: `upload_status` takes the values `pending`, `ready`, `failed`. All parameters after `db` stay keyword-only. `AttachmentLinkCreateSchema`, the inherited `create` and `get_by_entity` do not change.

## 4. Rules that apply

- **HR-6. Every paged or top-N result has a stable order.** Default: name case-insensitive ascending, then `id` ascending. Score-ranked results break ties the same way. Generic `BaseDAO` lists only guarantee `id` ascending (stable paging); choosing a display order is the manager's job. Standing decision: no order recipe counts as deterministic unless it ends in `id`. Where a list already has a chosen order (here: newest first), keep it and add `id` as the last key, in the direction given in the Intended text.
- **HR-16. Nothing links across workspaces.** A row linking to another workspace's row is invalid data, never a normal state. (Nothing to change here: keep comparing the link's own `workspace_id`, as R2 says.)
- OQ-5 (owner, 2026-11-04): attachments follow the record's own visibility. That check belongs to the attachment service and manager, not this file; it does not change any rule above.

## 5. Scope

- May change: `app/dao/attachment_link.py` only.
- No migration, no schema or API change. The response field `slot_count` keeps its shape; only its value drops failed uploads.

## 6. Out of scope (leave alone)

- BUG-1431 (`linked_at` stored in the database's local time): the fix is in `app/models/attachment_link.py`, not this unit.
- BUG-1870 (attachments of a private record visible to every member): attachment service / manager.
- `get_by_entity` has no caller and is listed for removal; do not remove or change it in this unit.
