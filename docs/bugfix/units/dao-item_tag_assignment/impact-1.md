# Impact review, round 1: dao-item_tag_assignment

Date: 2026-11-28. Diff: `git diff origin/main -- app alembic` in the unit worktree
(one file, `app/dao/item_tag_assignment.py`; no migration).

## Change

- `get_tags_for_item` (BUG-932): adds `ORDER BY lower(item_tags.name) ASC, item_tags.id ASC`.
- `get_tags_for_items` (BUG-933): `ORDER BY item_id, name` becomes
  `ORDER BY item_tag_assignments.item_id, lower(item_tags.name) ASC, item_tags.id ASC`.
- Docstrings updated. No import change (`func` already imported).

## Query shape (compiled, Postgres dialect, `scripts/bugfix/compile_query.py`)

```
... FROM item_tags JOIN item_tag_assignments ON item_tags.id = item_tag_assignments.tag_id
WHERE item_tag_assignments.item_id = 5 AND item_tag_assignments.workspace_id = 1 AND item_tags.is_active = true
ORDER BY lower(item_tags.name) ASC, item_tags.id ASC

... FROM item_tag_assignments JOIN item_tags ON item_tags.id = item_tag_assignments.tag_id
WHERE item_tag_assignments.item_id IN (5, 6) AND item_tag_assignments.workspace_id = 1 AND item_tags.is_active = true
ORDER BY item_tag_assignments.item_id, lower(item_tags.name) ASC, item_tags.id ASC
```

- ORM columns only (`lower(item_tags.name)`, `item_tags.id` appear verbatim after ORDER BY,
  as the strict SQL-text checks need). No DISTINCT, so the ORDER BY expressions need not be
  selected. Joins, filters and workspace bound (link's own `workspace_id`, HR-16) unchanged.
- Same form as the BUG-930 convention in `app/dao/item_tag.py` (lines 58, 81-84).

## Upstream

| Caller | Use | Effect |
|---|---|---|
| `ItemManager.get_tags_for_item` <- `ItemSummaryService.get_summary` <- `GET /items/{id}/summary/` | builds `tags` list in DAO order | intended: chips now name (ci), id |
| `ItemManager.get_tags_for_items` <- `ItemService.get_items_page` <- `GET /items/` | `tags_by_item.get(item.id, [])`, list comprehension in DAO order; item order from the item page query | intended; dict keys still from `item_ids`, unaffected by the leading `item_id` key |
| `ItemManager.update_item` (tag_ids sent) | iterates old tags, `decrement_usage_count` per tag, then `remove_all_tags_from_item` | order-independent: one relative `UPDATE ... usage_count - 1 WHERE usage_count > 0` per distinct tag (BUG-931 fix). Row-lock order across concurrent saves becomes deterministic (lower(name), id) instead of undefined: no new deadlock risk, if anything less |
| `ItemManager.delete_item` | same decrement loop | same as above |

No caller re-sorts, sets, or relies on the previous order. Frontend (`ItemCatalogCard`,
`ItemDetailsDialog`, `ItemsOverviewPanel`, `ItemsPage`, `EditItemDialog`) renders tags in API
order with no client-side sort, so the new order is what users see.

## Downstream

Only the query itself; no new DAO, lock or constraint assumed.

## API contract

Response shape, status codes and errors unchanged. Only the order of `tags` inside
`GET /items/` rows and `GET /items/{id}/summary/` changes, which is the bug's intended
behaviour. See `contract.md`: no contract change (frontend stage skipped).

## Database

No constraint, index or migration. `lower()` per row on a handful of tags per item; no index needed.

## Neighbouring bugs

- BUG-934 / BUG-935 (`ItemManager.update_item` replace-all): untouched; a later diff-based fix
  is order-independent.
- BUG-1486 (`account_tag_assignment.get_tags_for_account`): same pattern, different file;
  reuse this form there.
- BUG-100 (`BaseDAO.get_by_workspace`): unrelated.

## Shortcuts / scope

None. No special-casing; both siblings fixed the same way; nothing outside the two ORDER BY
clauses and their docstrings changed.

## New bugs found

None.

## Verdict

**APPROVE.** To the tester. Expected flip: the 8 pre-checked targets (TFI-12/13/14,
ISM-DP-09, TFS-17/18/19, ITS-P-17); callers' other tests compare tags as sets.
