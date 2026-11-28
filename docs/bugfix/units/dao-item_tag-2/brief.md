# Fix brief: dao-item_tag-2

## 1. Unit

| | |
|---|---|
| Slug | `dao-item_tag-2` (follow-up unit on the same file as `dao-item_tag`) |
| Source file | `app/dao/item_tag.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-item_tag-2` |
| Branch | `bugfix/dao-item_tag-2` (from `origin/main`) |
| Risk | `normal` (pattern `stale-identity-after-savepoint-rollback` is not on the trivial list) |

## 2. Bugs

### BUG-3302: After a savepoint rollback, a decremented tag still shows the rolled-back count in memory
- **Pattern:** `stale-identity-after-savepoint-rollback`
- **Where:** `ItemTagDAO.decrement_usage_count` in `app/dao/item_tag.py`.
- **Today:** The guarded UPDATE uses `synchronize_session=False`, so a rollback of a surrounding savepoint does not expire the tag: with 5 stored, decrement inside a savepoint (reads 4), roll back, and the session still shows 4 while the database has 5. The increment gets this right. No app path wraps tag counters in a savepoint today, and the stale value is never written back.
- **Intended:** After a savepoint rollback the in-memory `usage_count` equals the stored value, as for the increment (for example `synchronize_session="fetch"` plus expire, as `app/dao/account_tag.py` does).
- **Example:** Tag "Bolt" has 5 stored. Code opens a savepoint, decrements the tag (the tag now reads 4, the database has 4), then rolls the savepoint back. The database is back at 5; reading `usage_count` on the same tag object must also give 5, not 4.

## 3. Intended behaviour (spec rules, copied)

Facts for the whole file: table `item_tags`; `is_active = False` **is the soft delete** for item tags (there is no `is_deleted`). `usage_count` is integer NOT NULL, Python default `0`, no check constraint (a negative value can be stored by a direct write). No `updated_at` / `updated_by` columns. Every parameter after `db` is keyword-only in all five methods of the class (a positional call raises `TypeError`). The session runs with `autoflush=False`. The class never commits; the counters flush.

### `ItemTagDAO.decrement_usage_count(db, *, tag_id, workspace_id)` (the bug's method)
Used by `ItemManager.update_item` (once per **active** tag of the item when `tag_ids` is sent, before all its assignments are removed) and `ItemManager.delete_item` (once per active tag of the item) ← `PUT /items/{id}/`, `DELETE /items/{id}/`. Purpose: count one item less for a tag, never going below zero. Returns the `ItemTag` (the session's instance), or `None` when no tag with that id exists in the workspace.
- **R1.** Given a tag of the workspace with `usage_count` above 0, its stored `usage_count` goes down by exactly 1 and the tag is returned; e.g. 3 → 2, 1 → 0.
- **R2.** Given a tag with `usage_count = 0`, nothing is written: the value stays 0 and the tag is returned. This call flushes nothing (another pending change of the session stays unflushed).
- **R3.** Given a tag with a negative stored `usage_count` (only possible by a direct write), nothing is written and the tag is returned with its value unchanged (−2 stays −2).
- **R4.** Given an id that does not exist, or a tag of another workspace, `None` is returned, nothing is written and no error is raised (decided: callers check the tag first).
- **R5.** A deleted tag (`is_active = False`) and a system tag are decremented like any other (raw write, decided).
- **R6.** (BUG-931, fixed) The decrease and the "not below 0" check are applied to the value stored in the database at that moment, not to a value held in memory: loaded object 3 / stored 10 → stored 9, returned tag shows 9; loaded object 3 / stored 0 → stays 0, returned tag shows 0. This is one relative UPDATE in the database (`usage_count = usage_count - 1` with the condition `usage_count > 0` in the same statement's WHERE); no row lock. Re-reading the counter and then writing an absolute number is not acceptable.
- **R7.** When a value is written it is flushed, not committed: a fresh query in the same session sees it; rolling back a savepoint around the call restores the old one. As in `increment_usage_count` R6, the flush also writes other pending changes of the session (an unflushed rename of the same tag is saved with it).
- **R7, extended by BUG-3302:** after such a savepoint rollback, the tag object the session holds (the returned instance) also shows the restored stored value when its `usage_count` is read, including when it was read inside the savepoint before the rollback.
- Errors: none raised by the method itself. Side effects: at most one `item_tags` row's `usage_count` changed, flushed when changed; no commit; no other column or table written.

### `ItemTagDAO.increment_usage_count(db, *, tag_id, workspace_id)` (not in the bug; must not change)
Used by `ItemManager._assign_tags_to_item`, once per tag newly attached to an item ← `ItemManager.create_item` / `update_item` ← `POST /items/`, `PUT /items/{id}/`. Purpose: count one more item for a tag. Returns the `ItemTag` (the session's instance, flushed, not committed), or `None`.
- **R1.** Given a tag with that id in that workspace, its stored `usage_count` goes up by exactly 1 and the tag is returned (the same instance the session holds); e.g. 2 → 3.
- **R2.** Given an id that does not exist, or a tag of another workspace, `None` is returned, nothing is written and no error is raised.
- **R3.** A deleted tag (`is_active = False`) and a system tag are counted like any other.
- **R4.** There is no upper bound and no sign check: a stored negative value (only possible by a direct write) goes up by one (−2 → −1).
- **R5.** (BUG-931, fixed) The increase is applied to the value stored in the database at that moment, not to a value held in memory: given a tag whose loaded object says 3 while the stored value is 10, the stored value becomes 11 and the returned tag shows 11. One relative UPDATE (`usage_count = usage_count + 1`).
- **R6.** The change is flushed, not committed: a fresh query in the same session sees the new value; rolling back a savepoint around the call restores the old one (and the session's tag object shows the old value again; this already holds today). The flush also writes any other pending change of the session (e.g. an unflushed rename of the same tag is saved with it).
- Errors: none. Side effects: at most one `item_tags` row's `usage_count` changed, flushed (together with whatever else was pending in the session); no commit; no other column or table written.

### Other methods of the file (not in the bug; must not change)
`get_by_code_in_workspace`, `get_system_tags_in_workspace`, `get_active_tags_in_workspace` and the inherited generic methods stay exactly as they are.

## 4. Rules that apply

- **HR-10. Harmful state transitions lock the row** only for money, stock quantities, approvals or duplicate side effects. A tag usage counter is none of these: **no row lock** (`SELECT … FOR UPDATE` is not wanted). The counter stays a single relative UPDATE in the database (BUG-931 decision, decided by Claude under the reviewer's delegation, 2026-10-17).
- **HR-16. Nothing links across workspaces.** The counters keep filtering on the tag's `workspace_id`.
- No owner answer (OQ-n) touches this bug.

## 5. Scope

- May change: `app/dao/item_tag.py` only, and within it only `decrement_usage_count` (the increment already behaves as intended).
- No migration, no schema change, no API change. Signatures and return values stay the same. R2 (stored 0: nothing written, nothing flushed) and R6 (one guarded relative UPDATE) must keep holding.

## 6. Out of scope (leave alone)

- No other open bug is in `app/dao/item_tag.py` (BUG-929, BUG-930, BUG-931 are already fixed).
- `app/dao/item_tag_assignment.py`: BUG-932 (an item's tags on its summary have no sort order), BUG-933 (item list tag chips sorted by collation name with no tie-break).
- `app/managers/item_manager.py`: BUG-934 (saving an item's tags re-creates unchanged tag links), BUG-935 (saving an item's tags erases its links to deleted tags), BUG-943 (deleted item tags can be put on items), BUG-945 (deleting an item leaves its deleted tags counting it), BUG-947 (item edit can delete / restore an item, bypassing tag counters), and the other item manager bugs.
- `app/services/item_tag_service.py` / `app/schemas/item_tag.py` / `item_tags` table: BUG-1526 … BUG-1533.
- The annotation of the two counters (`-> ItemTag` although they can return `None`) is known and not a bug; it may be corrected to `ItemTag | None` if the fix touches those lines anyway.
