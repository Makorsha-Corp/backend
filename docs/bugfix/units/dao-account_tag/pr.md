## Fix: account tag counters stay right when two people tag at once, and the tag picker shows every tag in a fixed order

**Fixes BUG-1484, BUG-1485, BUG-1482 and BUG-1483.** One file (`app/dao/account_tag.py`). No database change, no API shape change.

**Not marked "Good to auto-merge":** the unit is risk `normal`; its counter, result-cap and deleted-rows patterns are not on the trivial list, and one method signature changes.

---

### What was wrong

**1. The "used by N accounts" counter could lose changes (BUG-1484). This is the one that matters most.**

Each account tag keeps a count of how many accounts carry it. The code read the count, added or subtracted 1 in Python, and wrote the new number back. If someone else changed the count in between, their change was overwritten.

*Example:* the tag "Supplier" is on 5 accounts. Rahim and Karim each tag a new account as "Supplier" at the same moment. Both read 5, both write 6. The tag now says 6, but 7 accounts carry it. Removing a tag had the same problem, and the "never below 0" check also used the stale number.

**2. The tag picker stopped at 100 tags (BUG-1485)**

The list behind the account tag picker had a built-in cap of 100 that nobody asked for. A workspace with 108 tags saw only 100, with no hint that 8 were missing. Because of bug 3, *which* 8 were missing could change from one load to the next.

**3. Tag lists had no order; "system tags first" never happened (BUG-1482)**

`GET /account-tags/` is documented as "system tags first", but neither tag list was sorted. The database returned rows in whatever order it liked. A system tag could appear last, and the order could change after someone edited a tag.

*Example:* system tags `Utility`, `client`, `Bank` and user tags `bravo`, `Alpha`, `Charlie` could come back as `Charlie, Utility, bravo, Bank, ...`. Now they always come back as `Bank, client, Utility, Alpha, bravo, Charlie`.

**4. The system tag list showed deleted system tags (BUG-1483)**

`GET /account-tags/system/` didn't filter out deleted tags. System tags can't be deleted through the app, so this only shows up with data changed outside it. No screen uses this list today.

---

### What changed

All in `app/dao/account_tag.py`:

```diff
  # the active tag list (tag picker)
- def get_active_tags_in_workspace(self, db, *, workspace_id, skip=0, limit=100):
+ def get_active_tags_in_workspace(self, db, *, workspace_id):   # no cap
-     .offset(skip).limit(limit)
+     .order_by(is_system_tag.desc(), lower(name), id)            # system first, then name, then id

  # the system tag list
+     AccountTag.is_active == True,                               # deleted system tags are left out
+     .order_by(lower(name), id)                                  # name, then id

  # adding 1
- tag.usage_count += 1
+ tag.usage_count = AccountTag.usage_count + 1                    # the database adds 1 to the stored value

  # subtracting 1
- if tag.usage_count > 0: tag.usage_count -= 1
+ UPDATE account_tags SET usage_count = usage_count - 1
+   WHERE id = … AND workspace_id = … AND usage_count > 0          # the "not below 0" check uses the stored value too
+ (the returned tag is then reloaded from the database)
```

- The sort follows **house rule HR-6** (every list has a fixed order that ends with id). It uses the same keys as the item tag lists.
- **The unused `skip` / `limit` parameters are removed.** No caller ever passed them (the only caller is the tag service, which passes only the workspace), and the endpoint never accepted them.
- No row lock (**house rule HR-10**). The database does the addition itself, so a lock isn't needed. This follows the earlier item tag fix (BUG-931).

### What you'll notice

- "Used by N accounts" counts stay correct when several people tag or untag accounts at the same time.
- The account tag picker shows every active tag, not just the first 100.
- Tags appear in the same order every time: system tags first, then by name ignoring upper and lower case (`Alpha`, `alpha`, `bravo`), then oldest first when names are equal.
- Deliberately unchanged: response fields, error messages, and the rule that a counter never goes below 0. Untagging never lowers a counter that is already negative because of old bad data.

### What to look at when reviewing

- **The subtraction is written as an explicit UPDATE statement** rather than the one-line form used for adding. It has to check "above 0" against the stored value in the same statement. The tag object is reloaded afterwards so the caller sees the stored number. If the count is already 0, nothing is written and nothing else in the session is saved early. Object if you'd prefer both counters written the same way.
- **Removing `skip` / `limit` changes the method's signature.** Every caller was searched and none used them. Say so if you'd rather keep them as optional parameters for later paging.
- **No lock, by design.** "Add 1 to whatever is stored" can't lose an update, and it follows the BUG-931 decision. If a deleted tag is still attached somewhere, its counter still moves. That is BUG-2987 in the account manager and is not part of this PR.
- **The same weakness exists elsewhere.** The item tag counter (fixed earlier) can show a rolled-back number after a savepoint roll-back. It has been suggested as a new bug and is not part of this PR.

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:** the only caller of both lists is `AccountTagService` (`GET /account-tags/`, `GET /account-tags/system/`). The counters are used by the account manager and by `AccountTagAssignmentDAO.remove_all_tags_from_account`, and both were checked, including removing several links in one go. The frontend (`accountTagsApi.ts`) sends no paging parameters and shows the list in server order.
- **Contract:** same response shape, inputs and codes. Only values change (order, no cap of 100, deleted system tags hidden, correct counts). No frontend PR.
- **Tests:** the 14 tests marked as known failures for these bugs (account tag DAO and service) now pass, and their markers are removed. That covers 9 strict and 5 order tests that sometimes passed by luck. The counter tests also confirm that the database does the addition and subtraction itself. Every other test in the full suite had the same result before and after (flip check CLEAN, base `614bbce`).
- **Database:** no migration; one Alembic head.
- **Commits:** `1846be7` (fix; branch `bugfix/dao-account_tag`, pushed yet).

</details>

## Code review

**PASS**: 0 blockers, 0 majors, 2 minors, 3 nits. This was an independent strict review; the reviewer didn't see the test results. Details are in `docs/bugfix/units/dao-account_tag/review-1.md`.

For you to decide (neither changes behaviour):
- **Minor:** the decrease doesn't reuse the value its UPDATE already returns. It reloads the field instead, which costs one extra small SELECT per decrease. That's the price of keeping the in-memory count right after a rollback.
- **Minor:** the docstrings weren't updated. The system-tag list doesn't say "active only, sorted by name", and the counters' "Returns" line doesn't mention `None`.
- Nits: the increase and the decrease use two different techniques (same as item tags); one setting repeats the app's default; the `== True` style is kept to match the surrounding code.

Related, outside this PR: the already-merged item-tag decrease has a small rollback edge case that this version gets right. It's logged as a follow-up.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
