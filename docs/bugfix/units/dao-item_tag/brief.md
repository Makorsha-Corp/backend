# Fix brief: dao-item_tag

## 1. Unit

| | |
|---|---|
| Slug | `dao-item_tag` |
| Source file | `app/dao/item_tag.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-item_tag` |
| Branch | `bugfix/dao-item_tag` (from `origin/main`) |
| Risk | `normal` (BUG-929 is a trivial-list pattern; BUG-930 `hr-6-non-default-list-order` and BUG-931 `non-atomic-counter-update` are not on the list) |

## 2. Bugs

### BUG-929: System tag list has no sort order
- **Pattern:** `unordered-pagination`
- **Where:** `ItemTagDAO.get_system_tags_in_workspace`; reached through `GET /item-tags/system/`.
- **Today:** No `ORDER BY`; the system tags come back in whatever order the database produces.
- **Intended:** Name case-insensitive ascending, then `id` ascending (HR-6) (decided by Claude under the reviewer's delegation 2026-10-17).

### BUG-930: Active tag list sorted by collation name with no tie-break
- **Pattern:** `hr-6-non-default-list-order`
- **Where:** `ItemTagDAO.get_active_tags_in_workspace`; reached through `GET /item-tags/`.
- **Today:** `ORDER BY is_system_tag DESC, name`: names follow the database collation's case rule (on one database `"alpha"` before `"Alpha"`; under a `C` collation all capitals first) and tags with the same name come back in no fixed order.
- **Intended:** System tags first (kept), then name case-insensitive ascending, then `id` ascending (HR-6; per BUG-623 precedent) (decided by Claude under the reviewer's delegation 2026-10-17).

### BUG-931: Tag usage counter can lose concurrent changes
- **Pattern:** `non-atomic-counter-update`
- **Where:** `ItemTagDAO.increment_usage_count`, `ItemTagDAO.decrement_usage_count`; reached through `POST /items/`, `PUT /items/{id}/`, `DELETE /items/{id}/` via `ItemManager`.
- **Today:** The new value is computed in Python from the loaded object and written back (`SET usage_count = <n>`); the "not below 0" check also uses the loaded value. A stale object (another request's change, or a value changed since loading) overwrites the stored count: loaded 3 / stored 10 → increment stores 4.
- **Intended:** The change is applied in the database relative to the stored value (`usage_count = usage_count + 1`; `usage_count - 1` only where `usage_count > 0`), and the returned tag shows the stored result; no row lock needed (HR-10 does not apply) (decided by Claude under the reviewer's delegation 2026-10-17).
- **Example:** Two users each create an item tagged "Bolt" (counter 5) at the same second. Both requests read 5 and write 6: two items have the tag, the counter says 6 for ever. After the fix it says 7.

## 3. Intended behaviour (spec rules, copied)

Facts for the whole file: table `item_tags`; `is_active = False` **is the soft delete** for tags (there is no `is_deleted`). `usage_count` is integer NOT NULL with no check constraint (a negative value can be stored by a direct write). No `updated_at` / `updated_by` columns. Every parameter after `db` is keyword-only in all five methods. The class never commits.

### `ItemTagDAO.get_by_code_in_workspace(db, *, workspace_id, tag_code)` (not in a bug; must not change)
- **R1.** Given a tag of the workspace with exactly that code, it is returned. A tag of another workspace with the same code is never returned; an unknown workspace id returns `None`.
- **R2.** The comparison is exact: no case folding, no trimming, no prefix or pattern match. `""` finds a tag stored with an empty code; `None` returns `None`.
- **R3.** A deleted tag (`is_active = False`) is returned exactly like an active one; `is_system_tag` does not matter.
- **R4.** Given two tags of the workspace with the same code, one of them is returned (which one is not specified).
- **R5.** Nothing is written.

### `ItemTagDAO.get_system_tags_in_workspace(db, *, workspace_id)`
Used by `ItemTagService.get_system_tags` ← `GET /item-tags/system/`. Returns a `list` of `ItemTag`.
- **R1.** Returns every tag of the workspace with `is_system_tag = True` and `is_active = True`. User tags, deleted system tags and tags of other workspaces are never returned. An unknown workspace, or one without system tags, returns `[]`.
- **R2.** No limit: all matching tags are returned.
- **R3.** [BUG-929] (HR-6) Ordered by `name` case-insensitive ascending, then `id` ascending (e.g. system tags named "Tool", "consumable", "Bolt" come back "Bolt", "consumable", "Tool"). *(Today: no ordering is requested.)*
- **R4.** Nothing is written.

### `ItemTagDAO.get_active_tags_in_workspace(db, *, workspace_id)`
Used by `ItemTagService.get_tags` ← `GET /item-tags/` (the service then replaces each tag's `usage_count` with a live count). Returns a `list` of `ItemTag`.
- **R1.** Returns every tag of the workspace with `is_active = True`, system and user tags alike. Deleted tags and tags of other workspaces are never returned. An unknown or empty workspace returns `[]`.
- **R2.** No limit: all matching tags are returned.
- **R3.** Every system tag comes before every user tag (holds today; keep it).
- **R4.** [BUG-930] (HR-6) Within each group, tags are ordered by `name` case-insensitive ascending, then `id` ascending: user tags "bravo", "Alpha" (id 1), "alpha" (id 2), "Charlie" come back "Alpha" (1), "alpha" (2), "bravo", "Charlie"; two tags both named "Bolt" come back lower id first. *(Today: `is_system_tag` descending, then `name` under the database collation, with no further key.)*
- **R5.** Nothing is written.

### `ItemTagDAO.increment_usage_count(db, *, tag_id, workspace_id)`
Used by `ItemManager._assign_tags_to_item`, once per tag newly attached to an item. Returns the `ItemTag` (the session's instance, flushed, not committed), or `None`.
- **R1.** Given a tag with that id in that workspace, its stored `usage_count` goes up by exactly 1 and the tag is returned (the same instance the session holds); e.g. 2 → 3.
- **R2.** Given an id that does not exist, or a tag of another workspace, `None` is returned, nothing is written and no error is raised.
- **R3.** A deleted tag (`is_active = False`) and a system tag are counted like any other.
- **R4.** There is no upper bound and no sign check: a stored negative value goes up by one (−2 → −1).
- **R5.** [BUG-931] The increase is applied to the value stored in the database at that moment, not to a value held in memory: given a tag whose loaded object says 3 while the stored value is 10, the stored value becomes 11 and the returned tag shows 11. *(Today: the loaded value is used: 4 is stored and returned, the other change is lost. With a freshly loaded or expired object the result is already correct: 11.)*
- **R6.** The change is flushed, not committed: a fresh query in the same session sees the new value; rolling back a savepoint around the call restores the old one. The flush also writes any other pending change of the session (e.g. an unflushed rename of the same tag is saved with it).

Side effects: at most one `item_tags` row's `usage_count` changed; no other column or table written.

### `ItemTagDAO.decrement_usage_count(db, *, tag_id, workspace_id)`
Used by `ItemManager.update_item` (once per active tag of the item when `tag_ids` is sent) and `ItemManager.delete_item` (once per active tag). Returns the `ItemTag` (the session's instance), or `None`.
- **R1.** Given a tag of the workspace with `usage_count` above 0, its stored `usage_count` goes down by exactly 1 and the tag is returned; e.g. 3 → 2, 1 → 0.
- **R2.** Given a tag with `usage_count = 0`, nothing is written: the value stays 0 and the tag is returned. This call flushes nothing (another pending change of the session stays unflushed).
- **R3.** Given a tag with a negative stored `usage_count`, nothing is written and the tag is returned with its value unchanged (−2 stays −2).
- **R4.** Given an id that does not exist, or a tag of another workspace, `None` is returned, nothing is written and no error is raised.
- **R5.** A deleted tag (`is_active = False`) and a system tag are decremented like any other.
- **R6.** [BUG-931] The decrease and the "not below 0" check are applied to the value stored in the database at that moment, not to a value held in memory: loaded object 3 / stored 10 → stored 9, returned tag shows 9; loaded object 3 / stored 0 → stays 0, returned tag shows 0. *(Today: the loaded value is used: 2 is stored in both cases.)*
- **R7.** When a value is written it is flushed, not committed: a fresh query in the same session sees it; rolling back a savepoint around the call restores the old one. As in `increment_usage_count` R6, the flush also writes other pending changes of the session.

Side effects: at most one `item_tags` row's `usage_count` changed, flushed when changed; no other column or table written.

### Inherited generic methods (not overridden; must not change)
`create`, `update`, `get`, `get_by_id_and_workspace`, `get_by_workspace`, `remove` stay as they are. The raw lookups return deleted tags like active ones.

## 4. Rules that apply

- **HR-6. Every paged or top-N result has a stable order.** Default: name case-insensitive ascending, then `id` ascending. Applied to every list shown to users, paged or not. Standing decision: no order recipe counts as deterministic unless it ends in `id`. Where a list already has a chosen first key (here: system tags first), keep it and add the name and `id` keys after it.
- **HR-10. Harmful state transitions lock the row** only for money, stock quantities, approvals or duplicate side effects. A tag usage counter is none of these: no row lock. The fix is a single relative update in the database, not a lock.
- No owner answer (OQ-n) touches these bugs.

## 5. Scope

- May change: `app/dao/item_tag.py` only.
- No migration, no schema or API change. The method signatures and return types stay as they are (the counters keep returning the tag or `None`).

## 6. Out of scope (leave alone)

- `app/services/item_tag_service.py`: BUG-1527 (a deleted tag's code can never be reused), BUG-1528 (no unique index on the code), BUG-1529 (a deleted tag can still be edited), BUG-1531 (two live tags with one name), BUG-1533 (derived code collision), BUG-1526 / BUG-1530 / BUG-1532 (name trimming, clearing fields, derived codes; fixes in `app/schemas/item_tag.py`).
- `app/managers/item_manager.py`: BUG-934 / BUG-935 (saving an item's tags recreates or erases links), BUG-943 (deleted tags can be put on items), BUG-944 (unknown tag ids dropped), BUG-945 (deleting an item leaves its deleted tags counting it).
- BUG-932 / BUG-933 (an item's tags have no order): `app/dao/item_tag_assignment.py`.
- BUG-100 (generic `get_by_workspace` has no order): `app/dao/base.py`.
- The annotation of the two counters (`-> ItemTag` although they can return `None`) is known and not a bug; leave it unless the fix touches that line anyway.
