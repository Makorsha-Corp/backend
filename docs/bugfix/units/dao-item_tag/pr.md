## Fix: item tag "used by" counts no longer lose changes, and tag lists keep a fixed order

**Fixes BUG-931, BUG-929 and BUG-930.** One file (`app/dao/item_tag.py`). No database change, no API change.

---

### What was wrong

**1. A tag's usage counter could lose changes (BUG-931). This is the one that matters most.**

Every item tag keeps a count of how many items use it. When an item is created, re-tagged or deleted, the count goes up or down by one. The code read the count, added or subtracted one in Python, and wrote the result back as a fixed number. If the count had changed in the database since the tag was loaded (another person saving an item at the same moment, for example), that change was overwritten.

*Example:* the tag "Hex Bolt" is used by 5 items. Rahim and Karim each create a new item with "Hex Bolt" at the same moment. Both requests read 5, both write 6. The tag now says 6 items although 7 use it. The "not below 0" check had the same weakness: it looked at the loaded number, not the stored one, so a tag the database already had at 0 could be written to a wrong value from a stale copy.

**2. The system tag list came back in no fixed order (BUG-929)**

`GET /item-tags/system/` had no sort at all, so the built-in tags could come back in a different order from one call to the next.

*Example:* the system tags "Tool", "consumable" and "Bolt" could come back in any order. They now always come back "Bolt", "consumable", "Tool".

**3. The tag list sorted capitals oddly and had no tie-break (BUG-930)**

`GET /item-tags/` put system tags first (kept), then sorted by name using the database's collation. Depending on the server, "alpha" might come before "Alpha" or all capitals might come first, and two tags with the same name could swap places between calls.

*Example:* user tags "bravo", "Alpha", "alpha", "Charlie" now always come back "Alpha", "alpha", "bravo", "Charlie" (the older "Alpha" first), after the system tags.

---

### What changed

All in `app/dao/item_tag.py`:

```diff
  # system tag list (BUG-929)
+ .order_by(func.lower(ItemTag.name).asc(), ItemTag.id.asc())     # name ignoring case, then id

  # active tag list (BUG-930)
- .order_by(ItemTag.is_system_tag.desc(), ItemTag.name)
+ .order_by(ItemTag.is_system_tag.desc(),                          # system tags still first
+           func.lower(ItemTag.name).asc(), ItemTag.id.asc())     # then name ignoring case, then id

  # increase the counter (BUG-931)
- tag.usage_count += 1
+ tag.usage_count = ItemTag.usage_count + 1     # the database adds 1 to the stored value

  # decrease the counter (BUG-931)
- if tag and tag.usage_count > 0:
-     tag.usage_count -= 1
+ UPDATE item_tags SET usage_count = usage_count - 1
+   WHERE id = … AND workspace_id = … AND usage_count > 0          # check and change on the stored value
+   RETURNING usage_count
+ # nothing changed (already 0): read the stored value, write nothing
```

The sort follows house rule HR-6 (every list sorts names ignoring case and ends with id). The counter takes no row lock, which matches house rule HR-10 (a relative update is enough here, no lock needed).

### What you'll notice

- Tag counts stay right when several people save items at the same time.
- The tag pickers and the tag settings list show tags in the same order every time.
- Unchanged: system tags still come first, the `usage_count` shown on `GET /item-tags/` is still the live count worked out by the service, and a count never goes below 0.

### What to look at when reviewing

- **The decrease takes two steps when the count is already 0:** a guarded UPDATE that changes nothing, then a read of the stored value. That keeps the "at 0, write nothing" rule. A single-statement version would always write, even at 0.
- **One edge case accepted:** if code reads the tag's count inside a savepoint, then rolls that savepoint back, the in-memory tag can show the rolled-back number until it is reloaded. The stored number is right. No code in the app wraps these counters in a savepoint, and every caller ignores the returned tag. Say so if you want it closed now.
- **Account tags have the same counter problem.** `app/dao/account_tag.py` has the same read-then-write counter (BUG-1484) and unsorted lists (BUG-1482). They are left for a later unit, which should copy this fix.
- **Wrong item counts already in the database are not repaired.** This fix stops new drift only. Item saves that recreate or miss counter changes are separate open bugs (BUG-934, BUG-935, BUG-945).

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:** callers are `ItemTagService.get_tags` / `get_system_tags` (`GET /item-tags/`, `GET /item-tags/system/`) and `ItemManager` create / update / delete item (the counters). None of them re-sorts the lists or uses the counters' return value. The frontend (`src/features/items/itemTagsApi.ts`) shows the API order as is, so there is no frontend PR.
- **Contract:** no change. Same fields, statuses and messages. Only the list order is now fixed.
- **Tests:** the 11 tests marked as known failures for these bugs (item tag DAO and item tag service) now pass, and their markers are removed. The counter tests also check that the database does the change relative to the stored value. Every other test in the full suite had the same result before and after (flip check CLEAN, 11 flipped as intended, base `f27d6ca`).
- **Database:** no schema or migration change, so there is no data-check script.
- **Commits:** `10ac8de` (fix).

</details>

## Code review

**PASS**: 0 blockers, 0 majors, 1 minor, 3 nits. This was an independent strict review; the reviewer didn't see the test results. Details are in `docs/bugfix/units/dao-item_tag/review-1.md`.

For you to decide:
- **Minor (R1-1):** say a decrement runs inside a savepoint, and the count is read before that savepoint is rolled back. The database goes back to 5, but the in-memory tag still shows 4. The increment gets this right. The code comment calls the decrement "savepoint-safe", which isn't accurate. No app code wraps tag counters in a savepoint today, and the wrong value is never written back. The systems engineer flagged the same edge case on its own and also judged it non-blocking. Fixing it means expiring the attribute after the write; the alternative is to correct the comment.
- Open question: if the row disappears between the decrement's two steps (the workspace is deleted at the same moment), the re-read would raise. Very unlikely.
- The same counter flaw exists in `app/dao/account_tag.py` (BUG-1484, already logged).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
