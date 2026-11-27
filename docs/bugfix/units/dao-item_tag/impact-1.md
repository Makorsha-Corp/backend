# Impact review 1: dao-item_tag

Date: 2026-11-27. Reviewer: systems engineer (stage 3). Diff: `app/dao/item_tag.py` only (worktree
`bugfix/dao-item_tag`, uncommitted). Bugs BUG-929, BUG-930, BUG-931.

## Verdict: APPROVE

No blocking finding. Contract: no change (see `contract.md`).

## Changed functions

### `get_system_tags_in_workspace` (BUG-929), `get_active_tags_in_workspace` (BUG-930)
- SQL: `ORDER BY lower(item_tags.name) ASC, item_tags.id ASC` and
  `ORDER BY item_tags.is_system_tag DESC, lower(item_tags.name) ASC, item_tags.id ASC`. ORM columns
  only (the SQL-text tests SYS-10 / ACT-13 look for `lower(item_tags.name)` and `item_tags.id`).
  System-first key kept in front.
- Upstream: `ItemTagService.get_tags` / `get_system_tags` ← `GET /item-tags/`, `GET /item-tags/system/`.
  Neither re-sorts or converts to a set; `get_tags` only overwrites each instance's `usage_count`
  with the live count (unchanged by this fix). Frontend (`../frontend/src/features/items/itemTagsApi.ts`)
  does no sorting of item tags; it shows the API order, which is now deterministic.
- Workspace bound unchanged (outer filter).

### `increment_usage_count` (BUG-931)
- `tag.usage_count = ItemTag.usage_count + 1` + `db.flush()`. Emitted SQL (captured):
  `UPDATE item_tags SET usage_count=(item_tags.usage_count + 1) WHERE item_tags.id = ?`, together
  with any other pending column of the same tag (`SET name=..., usage_count=(...)`), as R6 wants.
  The attribute is reloaded from the database after the flush, so the returned tag shows the stored
  value. The instance is in the flush's modified set, so a savepoint rollback expires it correctly.
- The expression only lives on the instance between the assignment and the immediate flush; if the
  flush raises, the transaction is lost anyway. Acceptable.

### `decrement_usage_count` (BUG-931)
- Guarded Core `UPDATE ... WHERE id AND workspace_id AND usage_count > 0 RETURNING usage_count`,
  `synchronize_session=False, autoflush=False`; written → expire `usage_count` + `db.flush()`;
  not written → `SELECT usage_count` (autoflush off) + `set_committed_value`, no flush (keeps R2: a
  pending change elsewhere stays unflushed).
- Simpler single-statement form considered: a `CASE` expression assigned through the ORM would write
  (and flush) at 0, breaking R2/R3; an ORM-flush UPDATE cannot carry the `> 0` guard. The two-path
  form is justified. The extra SELECT at ≤ 0 is cheap and its race with the UPDATE is harmless.
- Pending changes on the same tag: an unflushed `usage_count` change on the tag would be discarded
  by the expire; no caller produces one (increment always flushes at once; the only other writer,
  `ItemTagService.get_tags`, is a read endpoint). A pending rename survives both paths (checked).

## Callers (upstream)

Grepped `item_tag_dao` and `increment_usage_count` / `decrement_usage_count` (the account-tag DAO
has methods of the same name; `account_tag_assignment.py` uses `account_tag_dao`, not this one).
- `ItemManager._assign_tags_to_item` (increment, per new link) ← `create_item` / `update_item`.
- `ItemManager.update_item` (decrement per old tag, then remove links, then increment per new tag).
- `ItemManager.delete_item` (decrement per active tag, after `item_dao.update` of the item).
- Return value ignored by every caller; no caller relies on raised errors or ordering.
- Session: `SessionLocal(autoflush=False)`. `item_dao.update` flushes, so the item row is never
  pending while the Core UPDATE runs.

Rolled-back rowkit check (script in the scratchpad, not kept), both with autoflush off and on:
- update_item re-tagging the same tag: 1 → decrement 0 → increment 1; stored and instance agree.
- stored 0 with a pending rename: decrement leaves 0, flushes nothing (autoflush off); the next
  increment writes the rename with `usage_count + 1`.
- loaded/stored mismatch: decrement from stored 10 gives 9 / 9.
- two decrements then two increments: back to the start value; instance == stored.

## Non-blocking note: identity-map value after a savepoint rollback
In the decrement's written path the instance is not in the savepoint's modified set (the change
came from a Core UPDATE, and the expire leaves nothing to flush). If the caller **reads**
`tag.usage_count` inside the savepoint and then rolls the savepoint back, the instance keeps the
rolled-back value (seen: instance 9, stored 10). Re-reading after rollback without reading first is
correct (expired → reload). Before the fix, the ORM change put the instance in the modified set, so
it was expired on rollback. No app path wraps the item counters in a savepoint (`begin_nested` is
used only in `app/dao/inventory.py` around an inventory create and in a seed script), the counters'
return value is ignored, and the spec rule (R7) is about the stored value. Not worth a round. A
later variant could close it with `flag_modified`-style bookkeeping or by expiring the tag on
savepoint rollback, but nothing needs it today.

## Pre-existing, unchanged
- With an `autoflush=True` session, the lookup (`get_by_id_and_workspace`) flushes pending changes
  before the counter logic, so "decrement at 0 flushes nothing" cannot hold there. App sessions use
  `autoflush=False`. As before the fix.

## Neighbouring bugs
- BUG-1484 (`app/dao/account_tag.py`): same read-then-write counter, not touched; should copy this
  fix. Its pre-check should add the same SQL-text check as BUG-931's tests (see tester pre-check).
- BUG-945 (`delete_item` skips deleted tags): unaffected; the DAO counters already accept deleted
  tags (lookup is not filtered by `is_active`), so a manager fix can call them as is.
- BUG-934 / BUG-935 (tag links recreated on save): the decrement-then-increment sequence now nets
  out correctly against the stored value; their own behaviour is unchanged.
- BUG-100 (base `get_by_workspace` order): unrelated.

## Scope / shortcuts
Only `app/dao/item_tag.py`; nothing outside the brief. No special-cased inputs, no swallowed errors,
no lock (HR-10). Return annotation left alone as the brief allows.

## Database
No schema, constraint, index or migration change. No check script needed.

## New bugs found
None.
