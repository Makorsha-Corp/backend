# Fix brief: dao-item_tag_assignment

## 1. Unit

| | |
|---|---|
| Slug | `dao-item_tag_assignment` |
| Source file | `app/dao/item_tag_assignment.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-item_tag_assignment` |
| Branch | `bugfix/dao-item_tag_assignment` (from `origin/main`) |
| Risk | `normal` (BUG-932 `unordered-pagination` is on the trivial list; BUG-933 `hr-6-non-default-list-order` is not). Not money, stock, order workflow or security: both bugs are about the display order of an item's tags. |

## 2. Bugs

### BUG-932: An item's tags on its summary have no sort order
- **Pattern:** `unordered-pagination`
- **Where:** `ItemTagAssignmentDAO.get_tags_for_item`; reached through `GET /items/{id}/summary/` via `ItemManager.get_tags_for_item` (also used by `ItemManager.update_item` and `ItemManager.delete_item` to find the tags whose counters are lowered).
- **Today:** No `ORDER BY`; the item's active tags come back in whatever order the database produces.
- **Intended:** Name case-insensitive ascending, then `id` ascending; system tags not grouped first; same order as `get_tags_for_items` (HR-6) (decided by Claude under the reviewer's delegation 2026-10-17).
- **Example:** an item carries tags "bravo" (id 1), "Alpha" (id 2), "alpha" (id 3) and the system tag "Charlie" (id 4). After the fix they come back 2, 3, 1, 4. Two tags both named "Bolt" come back lower id first.

### BUG-933: Item list tag chips sorted by collation name with no tie-break
- **Pattern:** `hr-6-non-default-list-order`
- **Where:** `ItemTagAssignmentDAO.get_tags_for_items`; reached through `GET /items/` via `ItemManager.get_tags_for_items` (the tag chips of each item on the item list page).
- **Today:** `ORDER BY item_id, name`: within an item, names follow the database collation's case rule (on a `English_United States.1252` database `"alpha"` comes before `"Alpha"`; under a `C` collation every capitalised name comes first) and tags with the same name come back in no fixed order.
- **Intended:** Within each item: name case-insensitive ascending, then `id` ascending, same as `get_tags_for_item` (HR-6; per BUG-930 / BUG-623 precedent) (decided by Claude under the reviewer's delegation 2026-10-17).
- **Example:** the same four tags as above on one item → 2, 3, 1, 4 in that item's list; the grouping by item and the dict's keys do not change.

**Codebase convention (BUG-930, already fixed on main in `app/dao/item_tag.py`):** "name case-insensitive, then id" is written there as the lower-cased name ascending followed by `ItemTag.id` ascending (see `get_system_tags_in_workspace` and `get_active_tags_in_workspace`). Follow the same form here. Unlike `get_active_tags_in_workspace` (the tag picker), these two lists do **not** put system tags first.

## 3. Intended behaviour (spec rules, copied)

Facts for the whole file: table `item_tag_assignments` (links that put a tag on an item, inside one workspace). Columns: `id` (PK), `workspace_id`, `item_id`, `tag_id` (all NOT NULL, FK ON DELETE CASCADE to `workspaces`, `items`, `item_tags`), `assigned_at` (naive UTC, Python default), `assigned_by` (nullable FK `profiles.id`). No soft-delete column; unique `uq_item_tag (item_id, tag_id)` across workspaces. Items and item tags are soft-deleted with `is_active = False`. `ItemTag` has NOT NULL `workspace_id`, `name`, `tag_code`; `is_active` (default `True`); `is_system_tag` (default `False`). Tag names are not unique (two tags of one name can exist). Every parameter after `db` is keyword-only in all five methods (a positional call raises `TypeError`). The DAO validates nothing, never touches tag counters and never commits; `remove_all_tags_from_item` (and the inherited `create`) flush.

### `ItemTagAssignmentDAO.get_tags_for_items(db, *, item_ids, workspace_id)`
Used by `ItemManager.get_tags_for_items` ← `ItemService.get_items_page` ← `GET /items/`, with the ids of the items on the current page. Returns a `dict` mapping each requested item id to a `list` of `ItemTag` instances (possibly empty lists).
- **R1.** Given `item_ids` empty (`[]`) or `None`, `{}` is returned and nothing is queried.
- **R2.** Otherwise the result has exactly one key per distinct id in `item_ids`, in the order of first appearance (an id given twice appears once); every id without a matching link (unknown id, item with no tags, item whose links are all in another workspace or all to deleted tags) maps to `[]`.
- **R3.** A tag is listed under an item when a link with that `item_id` and the given `workspace_id` points at it and the tag is active (`is_active = True`). Links recorded under another `workspace_id` are ignored; deleted tags never appear (HR-4, holds today).
- **R4.** (P1, intended) The item and the tag are not checked further: the active tags of a deleted item (`is_active = False`) are returned like those of a live one; a tag of another workspace, or an item of another workspace, reached through a link whose own `workspace_id` is the given one, is returned (such links cannot be created through the API).
- **R5.** Each tag appears at most once per item (one link per item and tag, `uq_item_tag`). A tag on several requested items appears in each of their lists as the same object.
- **R6.** [BUG-933] (HR-6) Within each item, tags are ordered by `name` case-insensitive ascending, then `id` ascending (the same order as `get_tags_for_item` R4); system tags are not grouped first. E.g. tags "bravo" (id 1), "Alpha" (2), "alpha" (3), "Charlie" (4) come back 2, 3, 1, 4; two tags named "Bolt" come back lower id first. *(Today: ordered by `name` under the database collation with no further key; `"alpha"` came before `"Alpha"` and `"bolt"` before `"Bolt"` although the capitalised tag had the lower id; tags with the same name come back in an unspecified order.)*
- **R7.** No limit: all matching tags are returned. Only flushed links are seen. Nothing is written.
- Errors: none. Side effects: none.

### `ItemTagAssignmentDAO.get_tags_for_item(db, *, item_id, workspace_id)`
Used by `ItemManager.get_tags_for_item` ← `ItemSummaryService.get_summary` ← `GET /items/{id}/summary/` (the item's tag chips); `ItemManager.update_item` (when `tag_ids` is sent: the old tags whose counters are lowered) and `ItemManager.delete_item` (the tags whose counters are lowered) ← `PUT /items/{id}/`, `DELETE /items/{id}/`. Returns a `list` of `ItemTag` instances (possibly empty).
- **R1.** Returns every active tag (`is_active = True`) that a link with this `item_id` and `workspace_id` points at, each once. An item without links, an unknown item id, or a `workspace_id` other than the links' own returns `[]` (a link recorded under another workspace is never used).
- **R2.** Deleted tags (`is_active = False`) are never returned (HR-4, holds today); system and user tags are returned alike.
- **R3.** (P1, intended) The item and the tag are not checked further: the tags of a deleted item are returned like those of a live one; a tag of another workspace, or an item of another workspace, reached through a link whose own `workspace_id` is the given one, is returned. For the same item and workspace the result holds the same tags as `get_tags_for_items` gives for that item.
- **R4.** [BUG-932] (HR-6) Ordered by `name` case-insensitive ascending, then `id` ascending; system tags are not grouped first (e.g. "bravo" (1), "Alpha" (2), "alpha" (3), "Charlie" (4) → 2, 3, 1, 4). *(Today: no ordering is requested; the order is whatever the database produces.)*
- **R5.** No limit. Only flushed links are seen. Nothing is written.
- Errors: none. Side effects: none.

### Other methods (not in a bug; must not change)
- `assignment_exists(db, *, item_id, tag_id, workspace_id)`: R1 `True` when a link with exactly this `item_id`, `tag_id` and `workspace_id` exists, else `False`. R2 a link recorded under another `workspace_id` does not count. R3 the item and tag rows are not looked at (`True` for a link to a deleted tag, of a deleted item, or to a tag of another workspace). R4 only flushed links are seen. R5 nothing is written.
- `count_active_items_per_tag(db, *, workspace_id)`: returns `{tag_id: count}`. R1 for every tag with at least one link of the workspace to a live item, the number of such links. R2 links to deleted items are not counted; a tag with no such link has no entry (not `0`). R3 links of another workspace are not counted; an unknown workspace gives `{}`. R4 only the link's workspace is checked. R5 the tag's state is not looked at. R6 only flushed rows are seen; nothing is written; the dict has no meaningful order.
- `remove_all_tags_from_item(db, *, item_id, workspace_id)`: R1 deletes every link with this `item_id` and `workspace_id` and returns their number. R2 links to deleted tags and of a deleted item are deleted too. R3 only that item's links of that workspace are touched; item and tag rows and counters are never written. R4 no links or an unknown item → `0`. R5 the deletion is flushed, not committed (the flush also writes other pending changes). R6 loaded link objects leave the session; a loaded `item.tag_assignments` collection is not refreshed.
- Inherited generic methods (`create`, `update`, `remove`, `get`, `get_multi`, `get_by_workspace`, `get_by_id_and_workspace`) are not overridden and stay as they are.

## 4. Rules that apply

- **HR-6. Every paged or top-N result has a stable order.** Default: name case-insensitive ascending, then `id` ascending. Score-ranked results break ties the same way. Generic `BaseDAO` lists only guarantee `id` ascending; choosing a display order is the manager's job. The reviewer applies HR-6 to every list shown to users, paged or not (an item's tag chips are such a list).
- **HR-4 (as it applies here):** deleted tags stay out of an item's tag lists. Both methods already do this; keep it.
- **HR-16:** every method filters on the link's own `workspace_id`; keep that.
- **"System tags first"** is the chosen order of the tag picker list (`GET /item-tags/`) only; an item's tag chips are not grouped that way (decided by Claude under the reviewer's delegation, 2026-10-17).
- No owner answer (OQ-n) touches these bugs.

## 5. Scope

- May change: `app/dao/item_tag_assignment.py` only.
- No migration, no schema or API change. Method signatures, return types and the grouping / key order of `get_tags_for_items` stay as they are.

## 6. Out of scope (leave alone)

- `app/managers/item_manager.py`: BUG-934 (saving an item's tags deletes and re-creates unchanged tag links), BUG-935 (saving an item's tags erases its links to deleted tags), BUG-936 to BUG-948 (item names, deleted items, no-op stamps, missing items, SKU, tag ids, deletion checks). Leave `remove_all_tags_from_item` as it is; it is removed later together with the fix of BUG-934.
- `app/services/item_tag_service.py`: BUG-1526, BUG-1527, BUG-1529 to BUG-1533 (tag names, codes, edits of deleted tags).
- `app/services/item_summary_service.py`: BUG-2522 and the other summary bugs (other lists on the summary page, not the tags).
- `app/dao/account_tag_assignment.py`: BUG-1486 (the same ordering problem for account tags), a different file.
- BUG-100 (generic `get_by_workspace` has no order): `app/dao/base.py`.
