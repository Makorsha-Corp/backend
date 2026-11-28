# Fix notes: dao-attachment_markup_event

## Round 1 (2026-11-28)

### Changed

File: `app/dao/attachment_markup_event.py`, function `AttachmentMarkupEventDAO.list_for_attachment`. No other file touched. `create_event`, the singleton and the workspace/attachment filter are unchanged.

- **BUG-1436:** `.order_by(created_at.desc())` became `.order_by(created_at.desc(), id.desc())`.
- **BUG-1437:** removed the `limit: int = 200` parameter and its `.limit(limit)` call. Signature is now `list_for_attachment(self, db, *, workspace_id, attachment_id) -> list[AttachmentMarkupEvent]`.
- Added a short docstring saying the method returns every event, newest first, uncapped, with `id` breaking ties. There was no docstring before.

Compiled SQL after the fix:
`... WHERE workspace_id = :1 AND attachment_id = :2 ORDER BY created_at DESC, id DESC` (no LIMIT).

### Why

- HR-6 and the BUG-1321 precedent: keep the existing first key (`created_at` newest first) and end with `id` descending. Rows that share a time then have a fixed order, even after one of them is updated.
- Event logs are history (the owner's ruling) and the BUG-982 precedent: the hidden cap goes, and so does the parameter nobody used. The only caller, `AttachmentMarkupManager.list_events`, never passed `limit`, so no caller breaks.

### Reproduction (throwaway rowkit check, run against `bf_dao_attachment_markup_event_test` and since deleted)

The check made 3 entries with the same `created_at`, plus 1 entry a minute later. It updated the lowest-id tied entry and then listed. After that it added 197 older entries (201 in total) and listed again.

| Check | Before | After |
|---|---|---|
| Order of tied entries after an update | `[2253, 2251, 2252, 2250]`, want `[2253, 2252, 2251, 2250]`: FAIL | `[2454, 2453, 2452, 2451]`, want the same: OK |
| Count of 201 entries | 200: FAIL | 201: OK |
| First four of the 201 are still the newest, in order | False | True |

Also: `python -c "import app.main"` imports fine, and `ruff check app/dao/attachment_markup_event.py` passes.

### Assumptions

- None beyond the brief. The docstring is new. I added it so the uncapped behaviour is written down, as the round's instructions asked.

### Seen, not fixed

- Nothing new in this file. The caller's issues (BUG-2115 to BUG-2120) are out of scope, as the brief says.

### Risk

- Low. The query returns more rows only for attachments that have more than 200 events. The response shape is unchanged. The index on `(attachment_id, created_at)` still serves the filter and the first sort key.
