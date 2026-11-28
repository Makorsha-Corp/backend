# API contract: dao-attachment_markup_event

**No contract change** (no frontend work; the frontend stage is skipped).

Request inputs, status codes, error messages and response fields of
`GET /attachments/{id}/markups/events` are unchanged. The endpoint never took a `limit`; only the
internal DAO method lost it.

Value changes a client can see (none needs frontend work; `MarkupEventLogPanel` shows the items in
server order and groups consecutive entries by `session_id`, without re-sorting):

- **Order among ties:** entries with the same `created_at` now come highest `id` first, always.
  Example: entries 213, 214, 215 saved in one clock tick and 216 a minute later always read
  `216, 215, 214, 213`, even after one of them was updated (before: could read `216, 214, 215, 213`,
  which could split one session's group in the panel).
- **Completeness:** every entry is returned, not just the newest 200. Example: a drawing with 260
  markup saves now lists all 260, newest first (before: 200, the first 60 missing).
- **Size:** the response grows ~270 bytes per entry (1 000 entries ≈ 271 KiB) and is refetched
  after every autosave while the panel is open. Until BUG-2119 is fixed the server also reads one
  profile per entry (1 000 entries ≈ 0.6 s locally). Called out in the PR; no client change
  required.
