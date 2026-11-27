# Fix notes: dao-machine_maintenance_log

## Round 1 (2026-11-27)

All changes are in `app/dao/machine_maintenance_log.py` (worktree `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-machine_maintenance_log`). No migration, no schema change, no API change.

### Changed

- **BUG-1100:** `get_by_workspace`, `get_by_machine`, `get_by_type`, `get_by_machine_and_type`: `order_by(desc(maintenance_date))` is now `order_by(desc(maintenance_date), desc(id))`, still placed before `offset` / `limit`.
- **BUG-1101:** new module-level helper `_same_workspace_logs(db)`. It returns `db.query(MachineMaintenanceLog).join(Machine, Machine.id == MachineMaintenanceLog.machine_id).filter(Machine.workspace_id == MachineMaintenanceLog.workspace_id)`. `get_by_workspace`, `get_by_id_and_workspace`, `get_by_machine`, `get_by_type` and `get_by_machine_and_type` now start from this helper instead of `db.query(MachineMaintenanceLog)`. Their own filters are unchanged. Added the import `from app.models.machine import Machine`.
- **BUG-1102:** in `soft_delete`, `deleted_at = func.now()` is now `deleted_at = utcnow()`. The local `from sqlalchemy.sql import func` import inside the method is removed. Added the module-level import `from app.utils.time import utcnow`, the same way `app/dao/machine.py` does it.

### Why

- **BUG-1100:** `id` is unique, so ending the sort on `id` gives a total order. Consecutive skip/limit windows then split the logs with no repeats and no gaps (HR-6). The date stays the first key, newest first, and ties go to the newest insert first.
- **BUG-1101:** the machine check sits in the SQL `WHERE` / `JOIN`, so it runs before paging (HR-5). It compares only `machines.workspace_id`. It never reads `is_deleted` or `is_active` on the machine or its factory, so logs of deleted or inactive machines and factories still show (owner decision: history stays complete). `machine_id` is a NOT NULL foreign key, so the inner join never drops a valid log. `get_by_id_and_workspace` returns `None` for such a row, and the manager's existing 404 handles it. No row is changed.
- **BUG-1102:** `utcnow()` gives naive UTC in Python, so the stored value no longer depends on the session's `TimeZone`.

### Checks run (throwaway, deleted)

I used rowkit against `marker_test`:
- Five logs on one date, paged one at a time, came back in strictly descending `id` with no repeats.
- A log in workspace A whose machine is in workspace B was hidden by all four lists and by `get_by_id_and_workspace` (returned `None`).
- Same-workspace logs were still returned, including the same session instance by id. They were also still listed after their machine was soft-deleted.
- With `SET TIME ZONE 'America/New_York'`, `soft_delete` stored `deleted_at` within seconds of Python's UTC time. `get_by_id_and_workspace` still returned the deleted log.

`python -c "import app.main"` works and `ruff check` passes.

### Assumptions

- I used an inner `JOIN` on `machines` rather than an `EXISTS` subquery. Each log has exactly one machine (FK to the PK), so the join cannot duplicate rows, and `.first()` / paging behave as before.
- I put the join in a small private module-level helper so the five queries share one definition and the diff stays readable. Method signatures are unchanged.

### Seen, not fixed

- `soft_delete` / `restore` keep their existing behaviour otherwise (no workspace check, per spec R5).
- `get_multi` / `get` (inherited from the base) do not apply the cross-workspace machine filter. The brief says they must not change.

### Risk

- Every read now joins `machines`. `machine_id` and `machines.id` are indexed, so the cost should be negligible. Still worth a look if any caller depended on seeing cross-workspace rows. The brief says none does: the manager's `get_log`, `update_log` and `delete_log` all answer 404 on `None`.
