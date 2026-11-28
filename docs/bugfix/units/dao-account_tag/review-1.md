# Code review 1: dao-account_tag (2026-11-27)
Verdict: PASS   (blockers: 0, majors: 0, minors: 2, nits: 3)
Diff reviewed: 614bbce..1846be7, files: app/dao/account_tag.py (no alembic changes)

## 1. What a correct fix must do (written before reading the diff)

- **BUG-1485** `get_active_tags_in_workspace(db, *, workspace_id)`: no `skip`/`limit`, no cap; the
  only caller (`AccountTagService.get_tags`) passes `workspace_id` only, so nothing breaks.
- **BUG-1482** active list: `ORDER BY is_system_tag DESC, lower(name) ASC, id ASC` in SQL (PG
  booleans sort true after false, so DESC puts system tags first). System list: `lower(name), id`.
  Both orders must end in `id` (HR-6).
- **BUG-1483** system list adds `is_active = True` (HR-4); workspace filter kept (HR-16).
- **BUG-1484** increment: one `UPDATE ... SET usage_count = usage_count + 1 WHERE id AND
  workspace_id`, with no row lock (HR-10). The returned tag must show the stored value, not one
  worked out from the loaded object. Watch for: `synchronize_session="evaluate"/"auto"` working out
  `loaded + 1` in Python; a full `refresh()` throwing away the caller's pending changes.
  Decrement: one `UPDATE ... SET usage_count = usage_count - 1 WHERE id AND workspace_id AND
  usage_count > 0`. When no row is written (0 or negative stored): return the tag showing the
  stored value, write nothing and flush nothing (spec R2/R3). When a row is written: flush the
  other pending changes (R7). Unknown id or another workspace's tag gives `None` and writes nothing.
  A savepoint roll-back around either call must leave the in-memory tag at the old value (R6).
- Must not change: `get_by_tag_code_in_workspace`, the inherited base methods, the counters'
  signatures, keyword-only parameters, and no commit.

## 2. Findings

No blockers or majors. I checked against `marker_test` with a rowkit script (scratchpad
`rev_account_tag/check.py`, `sp.py`, always rolled back):

| Check | Result |
|---|---|
| increment, loaded 3 / stored 10 | stored 11, returned 11; other tag untouched |
| decrement, loaded 11 / stored 10 | 9 / 9 |
| decrement, loaded 9 / stored 0 | 0 / 0, statements: SELECT, UPDATE (0 rows), SELECT |
| decrement stored -2 / increment stored -2 | -2 unchanged / -1 |
| decrement at 0 with a pending rename | rename not flushed (still dirty), stored name unchanged |
| decrement at 4 / increment at 4 with a pending rename | rename flushed with the counter |
| savepoint roll-back around decrement / increment | in memory 3, stored 3 (both) |
| savepoint roll-back, decrement, stale load (3 / stored 10) | in memory 10, stored 10 |
| another workspace's tag / unknown id | `None`, stored value unchanged |
| active list (bravo, Alpha, alpha, Charlie, system Zed, Bank, deleted Gone/gone2) | Bank, Zed, Alpha, alpha, bravo, Charlie |
| system list | Bank, Zed (deleted system tag excluded) |

`ruff check app/dao/account_tag.py`: clean.

### R1-1 [minor] Decrement throws away its RETURNING value and costs an extra SELECT
- Where: app/dao/account_tag.py:130-149 (`decrement_usage_count`)
- Problem: the UPDATE returns the new stored `usage_count`, but the code uses it only as a
  "was a row written" flag, then expires the attribute. The next access runs another SELECT
  (traced: SELECT, UPDATE ... RETURNING, then a lazy SELECT on access). The value is already
  in hand.
- Evidence: statement trace in `check.py`. Behaviour is correct; this is one needless round trip
  per decrement. `remove_all_tags_from_account` (app/dao/account_tag_assignment.py:146) decrements
  once per assignment.
- Suggested direction: optional. Put the returned value on the instance as committed state instead
  of expiring it, but only if the savepoint roll-back still restores the old value. The "fetch"
  registration should keep that working, but I did not prove it.

### R1-2 [minor] Docstrings do not match the new behaviour
- Where: app/dao/account_tag.py:68-77 (`get_system_tags_in_workspace`), :94-101 and :117-124
  (counters)
- Problem: the active-list docstring was updated ("system tags first"), but the system-list
  docstring still says "Get system tags". It does not say active only, or by name. The counters'
  "Returns: Updated tag" leaves out the `None` case that the new `AccountTag | None` hint now
  states.
- Evidence: the docstring text next to the changed signatures.
- Suggested direction: one-line docstring updates.

### Nits
- N1: increment and decrement use two different mechanisms. Increment assigns a SQL expression
  and lets the flush send the UPDATE; decrement runs an explicit `update()`. Both are correct.
  This copies the merged item-tag twin (app/dao/item_tag.py:108, :131), so it is consistent.
- N2: `autoflush=False` in the execution options repeats the app session's own setting
  (app/db/session.py:11). It is harmless and documents the intent.
- N3: `== True` comparisons (E712 style) are kept to match the surrounding code; ruff does not
  flag them under the project config.

## 3. Questions (unproven, or outside this unit)

- **Out of this unit, for the owner/planner:** the merged twin `app/dao/item_tag.py:139` uses
  `synchronize_session=False` where this unit uses `"fetch"`. I ran this unit's decrement with
  `False` in its place (`sp.py`). After a savepoint roll-back the in-memory tag kept the
  decremented value (2) while the database held 3. With `"fetch"` it correctly showed 3. So
  item_tag's decrement probably has a savepoint-staleness defect. This should be logged as a
  separate bug; it is not a finding against this diff.

## 4. What is good

- The counters are truly relative single UPDATEs, with the `> 0` guard in the WHERE. There is no
  row lock and no read-then-write.
- The `"fetch"` choice is deliberate and correct. It fixes a savepoint roll-back problem that the
  item-tag twin still has, and the comment explains why.
- The zero case leaves the caller's pending changes unflushed and still returns the stored value.
- The order recipes end in `id`, the workspace filter is kept everywhere, the diff stays in scope,
  and the types are tightened to `AccountTag | None`.
