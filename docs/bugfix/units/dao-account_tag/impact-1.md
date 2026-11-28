# Impact review 1: dao-account_tag

Date: 2026-11-27. Diff: worktree `bugfix/dao-account_tag`, `git diff origin/main -- app alembic`
(only `app/dao/account_tag.py`; no migration). SQLAlchemy 2.0.51, Postgres `marker_test`, all
checks in rolled-back rowkit sessions (scripts in the scratch folder `se_account_tag/`).

**Verdict: APPROVE.** No contract change for the frontend (see `contract.md`).

## Changed functions

### `get_active_tags_in_workspace` (BUG-1482, BUG-1485)
- ORDER BY `is_system_tag DESC, lower(name) ASC, id ASC`; ORM columns and `func.lower`, so the SQL
  text has `account_tags.is_system_tag DESC`, `lower(account_tags.name)`, `account_tags.id` (what
  the pre-check's SQL-text tests look for). No `offset` / `limit`.
- **Signature change** `(db, *, workspace_id)`. Every caller, searched by method name and by
  `account_tag_dao` in `app/`, `scripts/`, `alembic/`: only `AccountTagService.get_tags`
  (`app/services/account_tag_service.py:14`), which passes only `workspace_id`.
  `item_tag_service` calls the same-named method on `item_tag_dao` (other class, untouched).
  `app/dao/account_tag_assignment.py` imports the DAO lazily but only calls `decrement_usage_count`.
  Endpoint `GET /account-tags/` (`app/api/v1/endpoints/account_tags.py:34`) never had query
  parameters, so no client could pass skip/limit. Frontend: `src/features/accounts/accountTagsApi.ts:28`
  `query: () => 'account-tags/'`, no params.
- Checked: 3 system + many user tags → `Bank, client, Utility` then user tags by name.

### `get_system_tags_in_workspace` (BUG-1482, BUG-1483)
- Adds `is_active == True` and ORDER BY `lower(name), id`.
- Callers needing inactive system tags: none. Only `AccountTagService.get_system_tags` ←
  `GET /account-tags/system/`. The frontend defines `useGetSystemTagsQuery` for account tags but no
  component uses it (only the item-tag one is imported elsewhere). Workspace seeding creates tags
  through `create`, not this list. Checked: `Utility, client, Bank, Deleted(inactive)` →
  `Bank, client, Utility`.

### `increment_usage_count` (BUG-1484)
- `tag.usage_count = AccountTag.usage_count + 1; db.flush()` → one
  `UPDATE account_tags SET usage_count=(account_tags.usage_count + 1) WHERE account_tags.id = ...`,
  attribute expired, reloaded on access. No `FOR UPDATE`.
- Checked (autoflush off and on): loaded 3 / stored 10 → 11 returned and stored; savepoint
  roll-back after reading 6 inside → memory 5, stored 5; pending rename flushed with it (as before,
  R6); other workspace / unknown → `None`; −2 → −1.

### `decrement_usage_count` (BUG-1484) — the `"fetch"` + expire pair
- One ORM-enabled UPDATE: `... SET usage_count=(usage_count - 1) WHERE id AND workspace_id AND
  usage_count > 0 RETURNING ...`. On Postgres "fetch" uses RETURNING, so **no extra SELECT** before
  or after the UPDATE (statement log: SELECT for the lookup, the UPDATE, then only the lazy reload
  when the caller reads the attribute).
- The result rows hold only the requested column: `[(11,)]`, so `scalar_one_or_none()` is the
  stored value, not the id (checked directly).
- Loaded 3 / stored 10 → 9; loaded 3 / stored 0 → 0, nothing written, tag not dirty; −2 stays −2.
- **Savepoint:** decrement inside `begin_nested`, read 4 inside, roll back → memory 5, stored 5.
  Correct because "fetch" registers the instance as altered in the nested transaction.
- **Pending rename:** with value > 0 the rename is flushed by the trailing `db.flush()` and kept
  (stored `(4, 'Renamed1')`); the expire touches only `usage_count`, so the rename is not lost.
  At stored 0 with autoflush off: nothing flushed, rename still pending and written by a later flush
  (R2 / pre-check DEC-03). With autoflush on, the rename is flushed by the `get_by_id_and_workspace`
  query before the method's own code (pre-existing, not this fix; the app's `SessionLocal` has
  `autoflush=False`).
- `AccountTagAssignmentDAO.remove_all_tags_from_account`: two links (counters 2 and 0) → both
  links deleted, counters 1 and 0, in memory and stored. The UPDATE's `autoflush=False` leaves the
  previous loop iteration's `db.delete(assignment)` pending; it is flushed by the decrement's flush
  or the method's final flush. No ordering problem (no FK from tags to assignments).

## Downstream / transactions
- No commit anywhere (TC rules: DAO flushes only). No row lock (HR-10). The UPDATE is bounded by
  `workspace_id` as well as id (HR-16).
- Minor edge, not blocking: in the "nothing written" branch `scalar_one()` raises if the row was
  deleted by another transaction between the lookup and the SELECT (READ COMMITTED). Tags are only
  soft-deleted through the API, and `item_tag` (prior art) has the same line.

## API contract
Shape, inputs, codes unchanged. Visible value changes: order of both lists, no cap at 100, inactive
system tags gone from `/system/`, `usage_count` correct under concurrency. Frontend renders the
list in server order (no re-sort in Add/Edit/Manage/AccountSelector dialogs), so it just gets the
documented order. Details in `contract.md`. Frontend stage: skip.

## Database
No schema change, no constraint, no check script needed.

## Neighbouring bugs
- BUG-1486 (assignment list order), BUG-1487 / BUG-870 / BUG-2987 (account manager): untouched, no
  clash. BUG-2987 means deleted tags can still be counted; the DAO stays raw by spec.
- BUG-1683…1693 (service / schema): untouched. BUG-1690 (`GET /account-tags/` 500 after a bad
  code) is unaffected: lifting the cap returns more rows, it can't make that 500 more likely except
  that a bad tag past row 100 is no longer hidden; same bug, already logged.
- BUG-1484 test correction (`ca0ffe8`) is on `origin/main`, so BUG-1484 stays in the unit
  (14 targets).

## Follow-up (not blocking)
- **`app/dao/item_tag.py` `decrement_usage_count` (on main, BUG-931 fix)** uses
  `synchronize_session=False`. Reproduced: tag 5, decrement inside a savepoint, read inside (4),
  roll back → memory **4**, stored 5. Same remedy as here (`"fetch"`, keep the expire). Suggest the
  orchestrator log it as a new bug:
  - pattern `stale-after-savepoint-rollback`; file `app/dao/item_tag.py`
    (`decrement_usage_count`); title "Item tag counter shows a rolled-back value after a savepoint
    roll-back"; today: memory keeps the decremented value read inside the savepoint; intended: after
    the roll-back the tag shows the stored value.

## New bugs found
- The item_tag one above. Nothing else.

## Shortcuts / scope
- No special-cased inputs, no swallowed errors. Return annotations `-> AccountTag | None` (allowed
  by brief §6). Docstrings of the counters still say "Updated tag" (cosmetic). Nothing out of scope.

## Notes for docs/future
None.
