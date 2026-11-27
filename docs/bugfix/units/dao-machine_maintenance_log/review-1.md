# Code review 1: dao-machine_maintenance_log (2026-11-27)
Verdict: PASS   (blockers: 0, majors: 0, minors: 1, nits: 1)
Diff reviewed: f27d6ca..5966805, files: app/dao/machine_maintenance_log.py (no alembic changes)

## 1. What a correct fix must do (written before reading the diff)

- **BUG-1100:** all four lists (`get_by_workspace`, `get_by_machine`, `get_by_type`,
  `get_by_machine_and_type`) order by `maintenance_date DESC, id DESC` in SQL, before
  OFFSET/LIMIT. All four, not only the one on the default route.
- **BUG-1101:** the four lists and `get_by_id_and_workspace` drop a log whose machine's
  `workspace_id` differs from the log's `workspace_id`, in SQL, before paging. Compare only
  `machines.workspace_id`. Never filter on machine or factory `is_deleted`/`is_active`, so logs
  of deleted or inactive machines still show (history rule). The join must be inner on the
  machine PK (`machine_id` NOT NULL, FK), so it can't duplicate or drop valid rows. The by-id
  lookup must still return soft-deleted logs (the manager's "already deleted" 400). No rows
  changed. `soft_delete` and `restore` stay unscoped.
- **BUG-1102:** `soft_delete` writes `deleted_at = utcnow()` (module-level import from
  `app.utils.time`, as in `app/dao/machine.py:12`, `:74`), whatever the session TimeZone. Nothing
  else in soft_delete changes. `restore`, the inherited methods, the signatures (positional vs
  keyword-only) and `created_at`/`updated_at` stay as they are.

## 2. Findings

### R1-1 [minor] Helper has no return type hint
- Where: app/dao/machine_maintenance_log.py:21 (`_same_workspace_logs`)
- Problem: it returns a `Query`, but the signature has no annotation. The module-level query
  helpers in this layer annotate it.
- Evidence: convention `app/dao/expense_order.py:179` `def _hub_base_query(db: Session, *, workspace_id: int, **filters) -> Query:`.
- Suggested direction: annotate the return as `Query`.

### R1-2 [nit] Bug id in a code docstring
- Where: app/dao/machine_maintenance_log.py:22
- Bug ids appear nowhere else in `app/` (`grep -rn "BUG-[0-9]" app` matches only this line).
  The HR-16 reference already explains the why. Owner's call.

## 3. Questions (unproven)

- None that affect correctness. The extra inner join is on `machines.id` (PK) with
  `machine_maintenance_logs.machine_id` indexed (model line 28), so there's no measurable
  cost at this table's scale.

## 4. What is good

- One shared base query applies the HR-16 rule to all five read methods, so no sibling is left
  out. It compares workspace only, never machine or factory state.
- The tie-break was added to all four lists. Ordering, filtering and paging stay in SQL.
- The `func.now()` local import was removed and `utcnow` imported at module level, matching
  `app/dao/machine.py`. `restore` and the signatures are untouched. `ruff check` is clean.
- Throwaway check (marker_test, rolled back; script in the session scratchpad at
  `rev_mml/mml_rev.py`):
  - 5 logs on one date, `limit=1`, `skip` 0..4: each of the four lists returns every id once,
    in id-descending order.
  - A log in W1 whose machine is in W2, dated later than all the others: it's hidden from the
    first page of `get_by_workspace` and `get_by_type`, `get_by_machine` and
    `get_by_machine_and_type` with W1 return `[]`, and `get_by_id_and_workspace` returns `None`
    for both W1 and W2.
  - Logs of a soft-deleted machine are still listed and found by id.
  - Under `TimeZone='America/New_York'`, `deleted_at` falls between two `utcnow()` readings.
  - A soft-deleted log is still returned by id and gone from the list.
  - `"REPAIR"` as a string works. `None` type or machine returns `[]`.
