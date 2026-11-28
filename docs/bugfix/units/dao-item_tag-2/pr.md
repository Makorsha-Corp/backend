## Fix: an item tag's count no longer stays wrong in memory after an undone step

**Fixes BUG-3302.** One file, one line of behaviour change. No database change, no API change.

---

### What was wrong

**A tag's usage count could show a value that had been undone (BUG-3302).**

Every item tag ("Hex Bolt", "Spare part", ...) keeps a count of how many items use it. When an item is
edited or deleted, the tag's count goes down by one. If that step runs inside a savepoint (a
"try this, and undo it if something fails" block) and the savepoint is undone, the database correctly
goes back to the old count, but the tag object the server is holding in memory kept the undone value.

*Example:* tag "Hex Bolt" is used by 5 items. Code opens a savepoint, removes one item from the tag
(the count reads 4), then undoes the savepoint. The database is back at 5, but reading the tag's count
in the same request still gave **4**.

Nothing in the app wraps tag counters in a savepoint today, and the wrong value was never written
back, so users never saw this. It's a latent trap for the next piece of code that uses a savepoint
here. Raising the count already behaved correctly; only lowering it was affected.

---

### What changed

`app/dao/item_tag.py`, `ItemTagDAO.decrement_usage_count`:

```diff
-                .execution_options(synchronize_session=False, autoflush=False)
+                .execution_options(synchronize_session="fetch", autoflush=False)   # tell the session this tag changed, so an undo refreshes it
```

The rest of the hunk is comments. The change uses the same pattern as the account-tag counter that
was merged in PR #17. The count still drops in a single database statement that never goes below 0,
there is still no row lock (house rule HR-10: a usage counter isn't money or stock), and the
workspace filter stays (house rule HR-16). After the write the tag's count is still thrown away and
re-read from the database, so a stale value held in memory is never trusted.

### What you'll notice

- Nothing in normal use. Counts shown by `PUT /items/{id}/` and `DELETE /items/{id}/` are the same as before.
- Code that undoes a savepoint around a tag decrement now sees the correct count.
- Deliberately unchanged: the increment, the "never below 0" rule, and the fact that the counter writes but never commits.

### What to look at when reviewing

- **Why `"fetch"` and not a manual refresh.** `"fetch"` is how SQLAlchemy learns that the tag was
  changed in the current transaction, which is what makes an undo refresh it. On Postgres it adds
  only the row id to the statement's `RETURNING`, with no extra query. Object if you'd rather keep
  `False` and refresh by hand.
- **The extra expire is kept on purpose.** `"fetch"` computes "loaded value - 1" in Python, which is
  wrong when the row changed since it was loaded (loaded 3, stored 10 must show 9). The existing
  expire throws that value away.
- **A new test came with this PR.** The bug was found in code review and had no test, so one was
  added for it (with its test-plan card). Before the fix it failed, and now it passes.

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:** the callers are `ItemManager.update_item` and `ItemManager.delete_item`
  (`PUT /items/{id}/`, `DELETE /items/{id}/`). Both ignore the return value, and none uses a
  savepoint around the counter. The SQL is still one guarded relative UPDATE. Approved, no new bugs.
- **Contract:** none. The frontend stage is skipped.
- **Tests:** this PR adds one new test for BUG-3302. It isn't in the main baseline because it didn't
  exist on main, so it's the target, and it passes. Every other test in the full suite (24,423) had
  the same result before and after (base `092776b`). The only differences are 34 known
  physical-order tests that may go either way. The flip-check script reports "REJECTED" only because
  the new test has no baseline entry, which is expected here.
- **Data check script:** none needed (no schema change).
- **Frontend PR:** none.
- **Commits:** `8502901` (fix, new test, test-plan card, bug register) and `24c6843` (test bookkeeping after review), pushed.

</details>

## Code review

Code review: **PASS**, 0 blockers, 0 majors, 1 minor (fixed), 2 nits (strict independent review, `review-1.md`).

- **R1-1 (fixed in `24c6843`):** the case counts, the trace table and the BUG-3302 row in `bugs.md` still described the new test as an expected failure. They now match.
- The reviewer put the old decrement back on the branch: only the new test failed, so the test really catches the bug.

Nits: the return type is still `-> ItemTag`, not `ItemTag | None` (the brief allowed leaving it); a copied comment about how "fetch" computes the value doesn't matter, because the value is expired right after.
