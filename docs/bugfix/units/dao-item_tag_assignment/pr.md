## Fix: an item's tags always show in the same order, alphabetically regardless of capital letters

**Fixes BUG-932 and BUG-933.** One file, two small changes. No database change, no API shape change.

---

### What was wrong

**1. On the item list, tag chips followed the database's capital-letter rule and same-name tags could swap places (BUG-933). This is the one users see most.**

The item list (`GET /items/`) sorted each item's tags by name, but with the database's own collation. On our servers that put lower-case `"alpha"` before `"Alpha"`, and two tags with exactly the same name came back in whatever order the database picked, which could change between page loads.

*Example:* the item "M8 hex bolt" has the tags **bravo**, **Alpha**, **alpha** and the system tag **Charlie**. The chips could read *alpha, Alpha, bravo, Charlie* on one load. If the workspace also has two tags both called **Imported**, they could swap places on the next load.

**2. On the item summary, tags had no order at all (BUG-932)**

The item summary page (`GET /items/{id}/summary/`) read the item's tags with no sort, so they came back in storage order: usually the order they were added, but not guaranteed, and different from the item list.

*Example:* the same "M8 hex bolt" could show *bravo, Alpha, alpha, Charlie* on its summary and a different order on the list.

---

### What changed

All in `app/dao/item_tag_assignment.py`:

```diff
  # tags of many items (the item list)
- .order_by(ItemTagAssignment.item_id, ItemTag.name)
+ .order_by(
+     ItemTagAssignment.item_id,           # still grouped by item
+     func.lower(ItemTag.name).asc(),      # name, ignoring capital letters
+     ItemTag.id.asc(),                    # same name: the older tag first
+ )

  # tags of one item (the item summary)
+ .order_by(func.lower(ItemTag.name).asc(), ItemTag.id.asc())   # same order as the list
```

This is house rule HR-6 (every list has a fixed order that ends with id). It uses the same order as the workspace tag list (`app/dao/item_tag.py`, BUG-930).

### What you'll notice

- In both places, the example item's tags now read **Alpha, alpha, bravo, Charlie**. "Alpha" and "alpha" are the same name ignoring capitals, so the one created first comes first.
- System tags are sorted in with the others by name. They are not pulled to the front.
- The item list and the item summary always agree, and the order doesn't change between loads.
- Nothing else changes: same tags, same fields, same item order.

### What to look at when reviewing

- **Ignoring capital letters.** Sorting `"Alpha"` and `"alpha"` together and then by age was decided by Claude under the reviewer's delegation (2026-10-17), to match the workspace tag list. Say so if you want capitals first instead.
- **Saving or deleting an item.** When an item is saved with new tags or deleted, each old tag's usage count goes down by one. Those tags are now visited in this fixed order instead of a random one. The result is the same, and the database locks are now taken in a predictable order.
- **Same pattern elsewhere.** Account tags (BUG-1486, `app/dao/account_tag_assignment.py`) have the same problem. That is left for its own PR.

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:** callers are `ItemManager.get_tags_for_item(s)`, used by the item summary service, the item list service, and the tag-count updates in `update_item` / `delete_item`. None of them re-sorts the tags or depends on the old order. The frontend shows tags in API order without sorting them, so there is no frontend PR.
- **Contract:** no change (`contract.md`). Only the order inside each item's `tags` array changes.
- **Tests:** the 8 tests marked as known failures for these bugs (the DAO, the item list service and the item summary service) now pass, and their markers are removed. Every other test in the full suite had the same result before and after (flip check CLEAN, base `092776b`).
- **Commits:** `ec2b64c` on `bugfix/dao-item_tag_assignment` (fix, marker removals, bugs.md status).

</details>

## Code review

Code review: **PASS**, 0 blockers, 0 majors, 0 minors, 1 nit (strict independent review, `review-1.md`).

Nit: in `get_tags_for_items` the first sort key `item_id` has no explicit `.asc()` while the new keys do (unchanged from before; harmless).
