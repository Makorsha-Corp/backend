# Contract: dao-item_tag

No contract change. The frontend stage is skipped.

Status codes, error messages, request inputs and response fields are unchanged.

Visible but needs no frontend work: `GET /item-tags/` and `GET /item-tags/system/` now return tags
in a fixed order (system tags first on `/item-tags/`; then name ignoring case, then id). Example:
tags "bravo", "Alpha", "alpha", "Charlie" come back "Alpha", "alpha", "bravo", "Charlie". The
frontend (`src/features/items/itemTagsApi.ts`) shows the API order and does not sort, so it simply
becomes stable. The stored `usage_count` is now changed relative to the database value; the API's
`usage_count` on `GET /item-tags/` is the live count computed by the service, unchanged.
