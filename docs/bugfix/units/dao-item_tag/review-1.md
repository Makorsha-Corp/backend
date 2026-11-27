# Code review 1: dao-item_tag (2026-11-27)
Verdict: PASS   (blockers: 0, majors: 0, minors: 1, nits: 3)
Diff reviewed: f27d6ca..10ac8de, files: app/dao/item_tag.py (no alembic changes)

## 1. What a correct fix must do (written before reading the diff)

- **BUG-929** `get_system_tags_in_workspace`: add `ORDER BY lower(name) ASC, id ASC` in SQL. Filters stay the same
  (workspace, `is_system_tag`, `is_active`). No limit.
- **BUG-930** `get_active_tags_in_workspace`: `ORDER BY is_system_tag DESC, lower(name) ASC, id ASC`. Keep system tags first.
- **BUG-931 increment**: one relative UPDATE (`usage_count = usage_count + 1`) on the stored row. The returned
  instance (the session's own) must show the stored result, not the loaded value plus 1. Stale 3 / stored 10 gives 11.
  Negative values go up by one. Another workspace or an unknown id gives `None` with no write. The pending
  changes of the session must still be flushed (R6). Savepoint rollback must restore the value. No row lock.
  - Pitfall to avoid: `synchronize_session="evaluate"` would compute the in-memory value in Python (4, not 11).
- **BUG-931 decrement**: a relative UPDATE guarded by `usage_count > 0` in SQL. When it writes, the stored value
  goes down by 1, the returned tag shows it, and the session flushes. When it does not write (stored 0 or
  negative), no UPDATE and no flush happen. Note the session runs with `autoflush=False`
  (app/db/session.py:11), so R2's "flushes nothing" is meaningful. The returned tag must show the **stored**
  value (stale 3 / stored 0 gives 0). `None` for another workspace or an unknown id.
- Must not change: the signatures, keyword-only params, the workspace check through `get_by_id_and_workspace`,
  `get_by_code_in_workspace` and the inherited methods. No commit.

## 2. Findings

### R1-1 [minor] Decrement: after a savepoint rollback the in-memory count can stay stale, and the comment says "savepoint-safe"
- Where: app/dao/item_tag.py:141-145 (`decrement_usage_count`, written branch)
- Problem: The change is made by a Core-style UPDATE with `synchronize_session=False` and then `db.expire(tag, ["usage_count"])`.
  The unit of work never sees the tag as modified. If `usage_count` is read again inside the savepoint (which
  reloads 4), a savepoint rollback does not expire it. The stored value goes back to 5, but the instance and any
  later ORM query in the same session (identity map) still show 4. The old code (`tag.usage_count -= 1` through
  the unit of work) and the new `increment_usage_count` both behave correctly here.
- Evidence (rowkit, marker_test, rolled back): stored 5; `begin_nested()` → decrement → read `t.usage_count`
  (4) → `sp.rollback()`. Then `t.usage_count` = 4 and `db.query(ItemTag).filter(id==t.id).first().usage_count` = 4,
  while the stored value is 5. The same steps with `increment_usage_count` give 5 / 5. Without the read inside
  the savepoint the value is correct (5 / 5). The stale value is never written back: an unrelated flush leaves 5
  stored.
- Why only minor: no app path wraps the tag counters in a savepoint today. `begin_nested` is used only in
  app/dao/inventory.py:276 and the seed script. The stored data is always right.
- Suggested direction: make the written branch's in-memory state follow savepoint rollback the same way
  increment does, or at least correct the comment so it doesn't claim savepoint safety.

### Nits
1. The two counters use different mechanisms: increment assigns an SQL expression through the unit of work,
   decrement uses `update()...returning()`. Decrement needs the guarded UPDATE for "nothing written or flushed at 0",
   but a one-line comment explaining why it differs would help the next reader.
2. In the written branch, `stored` is used only as a "row was updated" flag. The RETURNING value itself is thrown
   away and reloaded through `expire`, so the name reads as if it were used.
3. The docstrings still say "Returns: Updated tag" for calls that can return `None` or an unchanged tag. This was
   already there and the brief says to leave the annotation, so it is noted only.

## 3. Questions (unproven)

- Decrement else-branch (line 150-153): `scalar_one()` raises `NoResultFound` if the row is gone between the
  lookup and the re-read. A tag is never hard-deleted by the app (soft delete only). The only path is a concurrent
  workspace delete cascading, so this is not reproducible in practice. `scalar_one_or_none()` with a fall-back
  would be more defensive.
- Same flaw outside this unit: `app/dao/account_tag.py:100,119-120` (`AccountTagDAO.increment/decrement_usage_count`)
  still does `+= 1` / `-= 1` on the loaded value. It is a different file, so it is out of this unit's scope. Check
  whether it is logged in bugs.md.

## 4. What is good

- Both orderings are done in SQL with the right keys and end in `id`. Checked: system first; "Alpha"(lower id),
  "alpha", "Bolt", "Bolt"(lower id first), "bravo", "Charlie". The system list gives "Bolt", "consumable", "Tool", "zz".
  Deleted tags and other workspaces are excluded, and an unknown workspace gives `[]`.
- Increment uses the expression-assignment pattern correctly. Checked results: stale 3 / stored 10 → 11 returned
  and stored, −2 → −1, a pending rename is flushed with it, savepoint rollback restores it, and another workspace
  or an unknown id gives `None`. A dirty in-memory 99 over stored 5 gives 6.
- Decrement guards in SQL and is race-safe under READ COMMITTED (Postgres re-checks `usage_count > 0` after a lock
  wait). Checked: 3/10 → 9, 3/0 → 0, −2 stays −2, at 0 a pending rename stays unflushed, when written a pending
  rename is flushed, another workspace gives `None` with no write. `autoflush=False` and
  `synchronize_session=False` are deliberate and correct (no "evaluate" pitfall).
- The change is small and limited to the one file, with no signature changes. `ruff check` is clean.
