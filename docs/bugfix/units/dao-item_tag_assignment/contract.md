# Contract note: dao-item_tag_assignment

**No contract change.** The frontend stage is skipped.

Response shapes, status codes and error messages of `GET /items/` and
`GET /items/{id}/summary/` are unchanged. The only visible difference is the order of each
item's `tags` array, which is the fix itself: name case-insensitive ascending, then id
ascending, system tags not grouped first. Example: tags "bravo" (id 1), "Alpha" (2),
"alpha" (3), system tag "Charlie" (4) come back 2, 3, 1, 4. The frontend renders tags in API
order without re-sorting, so no frontend change is needed.
