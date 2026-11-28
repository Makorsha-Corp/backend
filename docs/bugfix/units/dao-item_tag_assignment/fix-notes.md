# Fix notes: dao-item_tag_assignment

## Round 1 (2026-11-28)

### Changed
File: `app/dao/item_tag_assignment.py` (only file touched; no migration).

- **BUG-932** `ItemTagAssignmentDAO.get_tags_for_item`: added
  `.order_by(func.lower(ItemTag.name).asc(), ItemTag.id.asc())`. Docstring
  "Returns" now states the order.
- **BUG-933** `ItemTagAssignmentDAO.get_tags_for_items`: changed
  `.order_by(ItemTagAssignment.item_id, ItemTag.name)` to
  `.order_by(ItemTagAssignment.item_id, func.lower(ItemTag.name).asc(), ItemTag.id.asc())`.
  Docstring "Returns" now states the order.

No imports added or removed (`func` was already imported for
`count_active_items_per_tag`).

### Why
HR-6: name case-insensitive ascending, then `id` ascending. Written in the same
form as the BUG-930 fix in `app/dao/item_tag.py` (`get_system_tags_in_workspace`),
via the ORM. `lower(name)` makes "Alpha"/"alpha" compare equal regardless of the
database collation, and `id` breaks the tie, so equal names come back lower id
first. `is_system_tag` is deliberately not an order key (system tags not grouped
first; that is only for the tag picker). In `get_tags_for_items` the leading
`item_id` key is kept; it has no effect on the result dict, whose keys still
come from `item_ids` in order of first appearance.

### Reproduction (session scratchpad, rowkit, `bf_dao_item_tag_assignment_test`)
One item, tags created in id order "bravo", "Alpha", "alpha", "Charlie"
(system tag), "Bolt", "bolt", linked in reverse order. Expected:
Alpha, alpha, Bolt, bolt, bravo, Charlie. Also checked `get_tags_for_items`
with `item_ids=[item, 999999, item]` gives keys `[item, 999999]` with `[]` for the unknown id.

Before:
```
get_tags_for_item  ['bolt', 'Bolt', 'Charlie', 'alpha', 'Alpha', 'bravo'] FAIL
get_tags_for_items ['alpha', 'Alpha', 'bolt', 'Bolt', 'bravo', 'Charlie'] FAIL
keys OK
```
After:
```
get_tags_for_item  ['Alpha', 'alpha', 'Bolt', 'bolt', 'bravo', 'Charlie'] OK
get_tags_for_items ['Alpha', 'alpha', 'Bolt', 'bolt', 'bravo', 'Charlie'] OK
keys OK
```
`python -c "import app.main"` OK; `ruff check app/dao/item_tag_assignment.py`: all checks passed.
Throwaway script deleted; no `.scratch/` in the worktree.

### Assumptions
- None beyond the brief. `lower()` (Postgres) treats non-ASCII names
  the database's way; same as the existing `item_tag.py` convention.

### Seen, not fixed
- Nothing new in this file. (The same ordering issue for account tags is
  BUG-1486, out of scope.)

### Risk
- Low. Callers that use `get_tags_for_item` for counter decrements
  (`ItemManager.update_item` / `delete_item`) only iterate the list; order does
  not affect them.
