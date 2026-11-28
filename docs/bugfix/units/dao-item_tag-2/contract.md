# Contract note: dao-item_tag-2 (BUG-3302)

**No contract change.** The frontend stage is skipped.

The fix only changes how the server's in-memory session tracks a tag's usage count
after an internal savepoint rollback. `PUT /items/{id}/` and `DELETE /items/{id}/` return
the same status codes, messages and fields. Tag `usage_count` values in responses are the
same as before (example: tag "Bolt" used by 5 items, one item deleted: it shows 4, as before).
