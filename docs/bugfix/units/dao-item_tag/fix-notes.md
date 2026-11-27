# Fix notes: dao-item_tag

## Round 1 (2026-11-27)

### Changed

Only file touched: `app/dao/item_tag.py` (worktree `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-item_tag`).

- Imports: added `from sqlalchemy import func, select, update` and
  `from sqlalchemy.orm.attributes import set_committed_value`.
- **BUG-929** `ItemTagDAO.get_system_tags_in_workspace`: added
  `.order_by(func.lower(ItemTag.name).asc(), ItemTag.id.asc())`.
- **BUG-930** `ItemTagDAO.get_active_tags_in_workspace`: order changed from
  `is_system_tag DESC, name` to
  `is_system_tag DESC, lower(name) ASC, id ASC`.
- **BUG-931** `ItemTagDAO.increment_usage_count`: replaced
  `tag.usage_count += 1` with `tag.usage_count = ItemTag.usage_count + 1`
  followed by `db.flush()` (as before). The ORM flush sends
  `SET usage_count = item_tags.usage_count + 1`, and the attribute is then
  loaded back from the stored result.
- **BUG-931** `ItemTagDAO.decrement_usage_count`: after the same lookup, it now runs
  one conditional relative UPDATE:
  `UPDATE item_tags SET usage_count = usage_count - 1 WHERE id = :id AND workspace_id = :ws AND usage_count > 0 RETURNING usage_count`
  (`synchronize_session=False, autoflush=False`).
  - If a row was updated, the `usage_count` attribute is expired so it reloads from the database, and the method calls `db.flush()` (as before).
  - If no row was updated (the stored value is 0 or below), it reads the stored value with `autoflush=False` and sets it on the instance with `set_committed_value`. Nothing is written, nothing is flushed, and the instance is not marked dirty.

### Why

- Both lists now end in `id`, and the name key ignores case, as HR-6 requires. System tags still come first in the active list.
- The counters now change the value stored in the database, not the loaded value. The "not below 0" check is in the UPDATE's WHERE clause, so it also uses the stored value. No row lock is taken (HR-10).
- The returned tag is the session's instance and shows the stored result.
- Checked with a throwaway rowkit script. Each case ran with the session's autoflush both off and on, and every case passed:
  - loaded 3 / stored 10: increment gives 11/11, decrement gives 9/9.
  - Stored 0: stays 0, and a pending rename stays unflushed (autoflush off).
  - Stored −2: decrement leaves −2, increment gives −1.
  - A tag of another workspace, or an unknown id, returns `None`.
  - When a write happens, a pending rename of the same tag is flushed with it.
  - Rolling back a savepoint around either call restores the stored value and the value on the instance.
  - Ordering: system tags "Tool", "consumable", "Bolt" come back as "Bolt", "consumable", "Tool". The active list comes back as system tags, then "Alpha"(lower id), "alpha", "bravo", "Charlie".
- `import app.main` works and `ruff check` passes. The script has been deleted.

### Assumptions

- I used `lower(name)` as the case-insensitive key. No other DAO has a case-insensitive order to copy, so this is the smallest choice. Characters that `lower()` maps to the same value still follow the database collation.
- The UPDATE in the decrement also filters on `workspace_id`, which repeats the lookup's check as a safeguard. The increment relies on the lookup having already scoped the tag to the workspace.
- When a decrement writes, the in-memory value is expired (reloaded on next access) instead of being set from RETURNING. A value set directly would survive a savepoint rollback, because the instance would not count as changed in that savepoint.

### Seen, not fixed

- If a session has `autoflush=True`, the lookup in both counters (`get_by_id_and_workspace`, a `Query`) flushes pending changes before the counter logic runs. Under that setting the decrement's "flushes nothing when the value is 0" rule cannot hold. This was already true before the fix. The app's `SessionLocal` uses `autoflush=False`, so the app itself is not affected.
- The `-> ItemTag` return annotation on both counters is known and was left alone, as the brief says.

### Risk

- Look first at `decrement_usage_count`: it makes two round trips when the stored value is ≤ 0 (the conditional UPDATE, then a SELECT), and it mixes a Core UPDATE with a later ORM flush. If the same tag also has a pending in-memory `usage_count` change, the expire in the written case discards it. Before the fix, that change would have been overwritten anyway.
- `increment_usage_count` now relies on the ORM's SQL-expression assignment. The attribute is expired or refetched after the flush, so reading `tag.usage_count` after the call costs one SELECT.
