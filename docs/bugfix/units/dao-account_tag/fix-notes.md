# Fix notes: dao-account_tag

## Round 1 (2026-11-27)

Only file changed: `app/dao/account_tag.py` (worktree `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-account_tag`).

### Changed

- **Imports:** added `func`, `select`, `update` from `sqlalchemy` and `set_committed_value` from `sqlalchemy.orm.attributes`, all used by the fixes. No import became unused.
- **BUG-1482** `get_active_tags_in_workspace`: added `.order_by(is_system_tag.desc(), func.lower(name).asc(), id.asc())`.
  `get_system_tags_in_workspace`: added `.order_by(func.lower(name).asc(), id.asc())`.
- **BUG-1483** `get_system_tags_in_workspace`: added the filter `AccountTag.is_active == True`.
- **BUG-1485** `get_active_tags_in_workspace`: removed the `skip` / `limit` parameters and `.offset()` / `.limit()`. The signature is now `(db, *, workspace_id)`. Its only caller, `AccountTagService.get_tags`, already passes only `workspace_id`. Updated the docstring.
- **BUG-1484** `increment_usage_count`: `tag.usage_count = AccountTag.usage_count + 1` followed by `db.flush()`. The flush sends `UPDATE account_tags SET usage_count = account_tags.usage_count + 1 WHERE id = ...`, and SQLAlchemy expires the attribute, so the next read gets the stored value.
- **BUG-1484** `decrement_usage_count`: a single ORM-enabled `UPDATE account_tags SET usage_count = usage_count - 1 WHERE id = :id AND workspace_id = :ws AND usage_count > 0 RETURNING usage_count`, with `synchronize_session="fetch"` and `autoflush=False`.
  - When a row was written: `db.expire(tag, ["usage_count"])`, then `db.flush()` (flushes other pending changes, as before).
  - When nothing was written (stored value 0 or below): no flush. The stored value is read with a plain `SELECT` (autoflush off) and set with `set_committed_value`, so the returned tag shows the stored value and nothing becomes dirty.
- Return annotations of both counters changed from `-> AccountTag` to `-> AccountTag | None`, which brief section 6 allows.

### Why

- The ordering keys are the HR-6 recipes from the brief, and both end in `id`. The active list keeps "system tags first" as its first key.
- The system list now hides soft-deleted tags (HR-4), as the item-tag twin does.
- With no limit, every active tag comes back (no hidden cap).
- Both counters change the value in the database, relative to what is stored, in one UPDATE. The decrement's "not below 0" check is in that statement's WHERE. There is no row lock (HR-10), and no value is read first and then written back as an absolute number.
- Savepoint safety of the decrement: a plain Core UPDATE, which is what `app/dao/item_tag.py` uses, is not recorded in the session transaction. A savepoint roll-back therefore does not expire the tag. In my check the in-memory value stayed at the rolled-back 4 while the database had 5 again. `synchronize_session="fetch"` makes SQLAlchemy register the matched instance as changed in the current transaction (`session._register_altered`). The roll-back then expires the tag and the next read shows the restored value. The fetch synchronisation also writes "loaded value - 1" into memory, which is stale when the row changed in the meantime. The `db.expire` straight after the UPDATE throws that value away. Postgres sends just the one UPDATE, with `RETURNING id, usage_count` and no extra SELECT for the fetch.

### Reproduction (throwaway rowkit checks against `marker_test`, before → after)

| Check | Before | After |
|---|---|---|
| Active list (user tags bravo, Alpha, alpha, Charlie; system tags Utility, client, Bank) | `Alpha, alpha, Charlie, Utility, client, Bank, bravo` | `Bank, client, Utility, Alpha, alpha, bravo, Charlie` |
| System list (with an inactive system tag "Deleted") | `Utility, client, Bank, Deleted` | `Bank, client, Utility` |
| 108 active tags | 100 returned | 108 returned |
| Signature | `(db, *, workspace_id, skip=0, limit=100)` | `(db, *, workspace_id)` |
| Increment, loaded 3 / stored 10 | returned 4, stored 4 | returned 11, stored 11 |
| Decrement, loaded 3 / stored 10 | returned 2, stored 2 | returned 9, stored 9 |
| Decrement, loaded 3 / stored 0 | returned 2, stored 2 | returned 0, stored 0 |
| Decrement at stored 0 with an unflushed rename | (not meaningful before: the stale loaded value let it write) | rename not flushed, returned 0 |
| Decrement / increment with an unflushed rename, value > 0 | rename flushed | rename flushed (unchanged) |
| Savepoint roll-back around increment (5) | 5 | 5 |
| Savepoint roll-back around decrement (5) | 5 | first try with a Core UPDATE: **4 (stale)**; final version: 5 |
| Negative: decrement −2 / increment −2 | −2 / −1 | −2 / −1 |
| Unknown id or other workspace | `None` | `None` |

SQL logged after the fix:
- Increment: `UPDATE account_tags SET usage_count=(account_tags.usage_count + 1) WHERE account_tags.id = ...`
- Decrement: `UPDATE account_tags SET usage_count=(account_tags.usage_count - 1) WHERE id = ... AND workspace_id = ... AND usage_count > 0 RETURNING id, usage_count`

Neither uses `FOR UPDATE`. `python -c "import app.main"` works, and `ruff check app/dao/account_tag.py` reports no problems. `.scratch/` has been deleted.

### Assumptions

- I matched the prior art in `item_tag.py` (expression assignment for the increment; RETURNING UPDATE plus `set_committed_value` for the decrement). The one difference is `synchronize_session="fetch"` in place of `False`, for savepoint correctness.
- The decrement's UPDATE also filters on `workspace_id`, beyond the id (HR-16, belt and braces). The row was already loaded through `get_by_id_and_workspace`.
- In the "nothing written" case, the decrement does one extra plain SELECT to show the stored value. This is needed for R2/R6 (loaded 3 / stored 0 → returns 0) and is the same as the prior art.

### Seen, not fixed

- `app/dao/item_tag.py` `decrement_usage_count` (already on main) uses `synchronize_session=False`. After a savepoint roll-back around a decrement that wrote, the in-memory `usage_count` stays at the rolled-back value: I reproduced this pattern here (4 shown, 5 stored). The same `"fetch"` change would fix it there. Its comments also carry BUG ids.
- The docstrings of both counters still say "Returns: Updated tag" although they can return `None`. I left them alone; only the annotation was corrected.

### Risk

- Look first at `decrement_usage_count`: the mix of `synchronize_session="fetch"` and the expire right after it. Behaviour depends on SQLAlchemy 2.0's bulk-update synchronisation; the venv has 2.0.51.
- The increment relies on SQLAlchemy expiring a SQL-expression attribute after the flush. This is documented behaviour and the same as `item_tag`.
