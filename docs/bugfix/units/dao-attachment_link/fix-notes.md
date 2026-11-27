# Fix notes: dao-attachment_link

## Round 1 (2026-11-27)

### Changed
All changes are in `app/dao/attachment_link.py`, class `AttachmentLinkDAO`.

- **BUG-1432** `get_attachments_for_entity`: `.order_by(Attachment.uploaded_at.desc())` is now
  `.order_by(Attachment.uploaded_at.desc(), Attachment.id.desc())`. It still runs before `offset` / `limit`.
- **BUG-1433** `get_links_for_attachment`: added `.order_by(AttachmentLink.id.asc())` before `.all()`.
- **BUG-1434** `count_linked_attachments_for_entity`: added the filter `Attachment.upload_status != "failed"`
  next to `is_deleted == False`. I updated the docstring to say that pending and ready count.

### Why
- BUG-1432: HR-6 says to keep the chosen order (newest first) and add `id` as the last key, descending
  as R6 asks. Rows with the same `uploaded_at` now come back in a fixed order, so pages
  no longer repeat or skip rows.
- BUG-1433: R4 asks for `id` ascending. Links now come back in the order they were made, so `links[0]`
  (the ledger's entity in `_append_attachment_ledger`) is always the first link made.
- BUG-1434: R1 asks that failed attachments not count. Pending and ready ones still count, and deleted
  ones still don't. `upload_status` is `NOT NULL` (`app/models/attachment.py:48`), so the `!=` test
  can't drop rows by accident through SQL NULL logic. The callers are the capacity check in
  `AttachmentManager.assert_entity_attachment_capacity` and `slot_count` in
  `attachment_service.py:120`. Both now see the lower count, which is the intended effect.

### Checks
- I compiled the three queries to Postgres SQL. They showed `ORDER BY attachments.uploaded_at DESC,
  attachments.id DESC` before LIMIT/OFFSET, `attachments.upload_status != ...` in the count, and
  `ORDER BY attachment_links.id ASC`.
- `import app.main` works and `ruff check app/dao/attachment_link.py` passes.
- I did not build rows in the database: each change is a single order or filter clause. `.scratch/`
  has been deleted.

### Assumptions
- I used the string literal `"failed"` because the existing `"ready"` filter in this file is a literal
  too (the manager uses `UploadStatusEnum`). The DAO does not import that enum today.

### Seen, not fixed
- Nothing new. `get_by_entity` also has no `ORDER BY`, but the brief says to leave it alone (no caller,
  listed for removal).

### Risk
- Low. BUG-1434 changes behaviour: a record with failed uploads can now take more uploads, up to 25
  pending or ready. Failed rows are never cleaned up, so the record can hold more than 25 attachment
  rows if you include failed ones. Anything that assumes "at most 25 rows per record" in total would be
  affected. I found no such code in `app/`.

### Agent improvements
- Throwaway scripts in `<worktree>/.scratch/` don't find `app` unless `PYTHONPATH=.` is set (Python
  puts the script's own folder on `sys.path`, not the working directory). The instructions could say so.
- No guard block got in the way in this unit.
