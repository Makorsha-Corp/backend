# Impact review 1: dao-item_tag-2 (BUG-3302)

Systems engineer, 2026-11-27. Diff: `git -C <worktree> diff origin/main -- app alembic`,
one hunk in `app/dao/item_tag.py`, `ItemTagDAO.decrement_usage_count`:
`synchronize_session=False` changed to `"fetch"`, plus comments. No migration.

## Comparison with the reference (`app/dao/account_tag.py`)

`AccountTagDAO.decrement_usage_count` (merged, PR #17) is now line-for-line the same
shape: guarded relative UPDATE with `synchronize_session="fetch"`, `autoflush=False`,
`RETURNING usage_count`; on write `db.expire(tag, ["usage_count"])` then `db.flush()`;
on no write a `select` + `set_committed_value`, no flush. Both DAOs **also expire** the
attribute, and in item_tag the expire was already there before this fix, so nothing is
missing. The expire still matters with "fetch": the fetch sync sets the attribute
to "loaded value - 1" in Python, which is wrong when the loaded value was stale (R6:
loaded 3, stored 10 must show 9, not 2). The expire throws that value away and the next
read loads the stored value.

Why "fetch" fixes the bug: in SQLAlchemy 2.0.51 the fetch (and evaluate) strategies
register the matched objects as altered in the current session transaction
(`_register_altered`). A nested-transaction rollback expires every object altered in
that transaction. With `False` the tag was never registered, so a value reloaded inside
the savepoint (4) survived the rollback. The increment already gets this through the
ORM flush.

## Upstream

- `item_tag_dao.decrement_usage_count` callers: `ItemManager.update_item`
  (app/managers/item_manager.py:130, once per old tag when `tag_ids` is sent) and
  `ItemManager.delete_item` (:320). Both ignore the return value. Endpoints:
  `PUT /items/{id}/`, `DELETE /items/{id}/`. The `account_tag_assignment` /
  `account_manager` hits are the account DAO, not this one.
- In `update_item`, a tag that is kept is decremented and then incremented again by
  `_assign_tags_to_item`. The increment sets a SQL expression on an attribute that is
  expired either way (expire existed before), so no change there.
- No app path uses `begin_nested()` around tag counters (only inventory.py and a seed
  script use savepoints). In production the change only adds the tag to the
  transaction's altered set. A full rollback already expires everything, and a commit
  expires on commit as before. What callers see does not change.
- Return value, `None` for a missing tag or one from another workspace, no errors,
  same instance: all unchanged.

## Downstream / query shape

- Still one statement: `UPDATE item_tags SET usage_count = usage_count - 1 WHERE id =
  .. AND workspace_id = .. AND usage_count > 0 RETURNING ...`. On Postgres "fetch"
  only adds the primary key to RETURNING. No extra SELECT, no row lock (HR-10), and the
  workspace filter stays (HR-16).
- `stored` is only checked against `None`, so the column order in RETURNING cannot
  change behaviour.
- `autoflush=False` stays, so R2 (stored 0: nothing flushed, another pending change
  stays unflushed) still holds.

## Check run (scratch copy of the worktree's app plus main's tests, own test DB)

`tests/unit/dao/test_item_tag.py`, `tests/unit/managers/test_item_manager.py`,
`tests/unit/dao/test_item_tag_assignment.py`: 313 passed, 140 xfailed. The only
failure is the BUG-3302 target as a strict XPASS, which is the intended flip. The 2
non-strict XPASSes are BUG-100 physical-order tests and are ignored. The tester's
full-suite flip check still applies.

## API contract

None. No status, message, field or value a client can see changes. See `contract.md`.

## Database

No schema change, no constraint, no check script needed.

## Neighbouring bugs

- No other open bug in `app/dao/item_tag.py`. Item manager bugs BUG-934/935/943/945/947
  are unaffected (counter arithmetic and filtering are unchanged).
- account_tag already has the same fix. No other tag DAO has a `synchronize_session=False`
  counter.

## Shortcuts / scope

None. Only the brief's method changed, it uses the same pattern as the merged
reference, and there is no special-casing. Leaving the `-> ItemTag` annotation alone is
allowed by the brief.

## New bugs found

None.

## Verdict

**APPROVE.** No contract change, so the frontend stage is skipped.
