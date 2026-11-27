# Fix brief: dao-machine_maintenance_log

## 1. Unit

| | |
|---|---|
| Slug | `dao-machine_maintenance_log` |
| Source file | `app/dao/machine_maintenance_log.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-machine_maintenance_log` |
| Branch | `bugfix/dao-machine_maintenance_log` (from `origin/main`) |
| Risk | `normal` (BUG-1100 is a trivial-list pattern; BUG-1101 `cross-workspace-row-exposed` and BUG-1102 `database-clock-timestamp` are not on the list. Logs carry an optional `cost`, but none of these bugs touches it.) |

## 2. Bugs

### BUG-1100: Maintenance logs on the same date have no order
- **Pattern:** `unordered-pagination`
- **Where:** `MachineMaintenanceLogDAO.get_by_workspace`, `get_by_machine`, `get_by_type`, `get_by_machine_and_type`; reached through `GET /machine-maintenance-logs/`.
- **Today:** `ORDER BY maintenance_date DESC` only: logs on one date come back in no fixed order, and paging repeats one and misses another (five logs on one date, one per page, showed one twice and one never).
- **Intended:** HR-6: `maintenance_date` descending, then `id` descending, before `skip` / `limit` (per BUG-600: newest first by date, ties newest insert first).

### BUG-1101: A stored maintenance log linked to another workspace's machine shows that machine's id
- **Pattern:** `cross-workspace-row-exposed`
- **Where:** `MachineMaintenanceLogDAO.get_by_workspace`, `get_by_id_and_workspace`, `get_by_machine`, `get_by_type`, `get_by_machine_and_type`; reached through `GET`, `PUT`, `DELETE /machine-maintenance-logs/`.
- **Today:** Only the log's own `workspace_id` is compared: the row is listed and read, with the other workspace's `machine_id`.
- **Intended:** HR-16, per BUG-1086: treated as not found, in the query, before paging, by comparing the machine's `workspace_id` to the log's; the machine's state is not read; the row stays (it is left for a one-off clean-up by the cross-workspace audit script, which uses its own SQL).
- **Why the by-id lookup changes here:** `get_log`, `update_log` and `delete_log` in the manager all read through `get_by_id_and_workspace`, answer their normal 404 on `None`, and no caller needs such a row.

### BUG-1102: A maintenance log's delete time depends on the database's time zone
- **Pattern:** `database-clock-timestamp`
- **Where:** `MachineMaintenanceLogDAO.soft_delete`; reached through `DELETE /machine-maintenance-logs/{id}/`.
- **Today:** `deleted_at` is the database's `now()`, stored as local time in the session's `TimeZone`: at 17:08 UTC it is 13:08 under `America/New_York`, 23:08 under `Asia/Dhaka`; a machine deleted at that moment records 17:08.
- **Intended:** `deleted_at` is written from `utcnow()` (naive UTC), as the machine DAO's `soft_delete` does (decided by Claude under the reviewer's delegation (2026-10-31)). Import `utcnow` from `app.utils.time`, the way `app/dao/machine.py` does, as a module-level name of `app/dao/machine_maintenance_log.py`. `created_at` and `updated_at` stay with the database clock (a separate, project-wide decision).

## 3. Intended behaviour (spec rules, copied)

Facts: table `machine_maintenance_logs`; `machine_id` NOT NULL, foreign key to `machines.id` (every log's machine row exists). `machines.workspace_id` is NOT NULL. Soft delete of a log = `is_deleted = True` with `is_active = False`; the lists look only at `is_deleted`. `deleted_at` is `timestamp without time zone`. Parameter style differs by method: `get_by_machine(db, machine_id, *, workspace_id, …)`, `get_by_type(db, maintenance_type, *, workspace_id, …)`, `get_by_machine_and_type(db, machine_id, maintenance_type, *, workspace_id, …)` take their filters positionally or by name; `workspace_id`, `skip`, `limit` and every parameter of the other methods are keyword-only. Keep these signatures.

### `get_by_workspace(db, *, workspace_id, skip=0, limit=100)`
Override of the base method with its own query. Used by `MachineMaintenanceLogManager.list_logs` with neither filter.
- **R1.** Returns the live logs with that `workspace_id`. Logs of another workspace never appear, even when they would fit on the page.
- **R2.** A soft-deleted log (`is_deleted = True`) is not returned and takes no place in the page: the filter runs before `skip` / `limit`. A log with `is_active = False`, `is_deleted = False` is returned.
- **R3.** The state of the log's machine and factory is not looked at: logs of a soft-deleted machine, of a machine in a soft-deleted factory, and of inactive-but-live machines and factories are returned and take a place in the page. (A maintenance log is history.)
- **R4.** Logs with different dates come back latest `maintenance_date` first.
- **R4a.** [BUG-1100] (HR-6) Logs on the same date come back highest `id` first, before `skip` / `limit`, so consecutive windows partition the logs with no repeats or gaps. *(Today: no tie-break.)*
- **R5.** At most `limit` rows are returned after skipping `skip`; with the defaults at most 100: given 101 logs, exactly 100, and with `limit=1000`, 101.
- **R6.** An unknown workspace, a workspace with no logs, `skip` at or past the number of rows, or `limit=0` returns `[]`.
- **R7.** A negative `limit` or `skip` makes Postgres reject the query: `sqlalchemy.exc.DataError`, pgcode `2201W` (`LIMIT must not be negative`) or `2201X` (`OFFSET must not be negative`).
- **R8.** [BUG-1101] (HR-16) A log whose machine belongs to another workspace is not returned and takes no place in the page; the row is not changed. *(Today: it is returned, showing the other workspace's `machine_id`.)*

### `get_by_id_and_workspace(db, *, id, workspace_id)`
Override identical to the base method today. Used by `MachineMaintenanceLogManager.update_log`, `get_log`, `delete_log`, each answering 404 `Maintenance log with ID <id> not found` on `None`.
- **R1.** Given a log with that id in that workspace, it is returned (the instance the session holds).
- **R2.** Given a log with that id in another workspace, `None` is returned.
- **R3.** Given an unknown id or `id=0`, `None` is returned, with no error.
- **R4.** A soft-deleted log is returned like any other (raw lookup; the "already deleted → 400" check needs it).
- **R5.** The state of the log's machine and factory is not looked at.
- **R6.** [BUG-1101] (HR-16) A log whose machine belongs to another workspace is not found: `None`, with the row's own `workspace_id` as well; the row is not changed. *(Today: it is returned.)*

### `get_by_machine(db, machine_id, *, workspace_id, skip=0, limit=100)`
Used by `list_logs` with `?machine_id=…`.
- **R1.** Returns the live logs with that `machine_id` and that `workspace_id`. Logs of another machine are never returned.
- **R2.** A call with the right machine id and another workspace returns `[]`.
- **R3.** Soft-deleted logs follow `get_by_workspace` R2.
- **R4.** The state of the machine and its factory is not looked at: asked for a soft-deleted machine, or a machine in a soft-deleted factory, the logs are returned.
- **R5.** Order follows `get_by_workspace` R4 and, [BUG-1100], R4a.
- **R6.** `skip` and `limit` follow `get_by_workspace` R5.
- **R7.** An unknown machine id, `machine_id=0`, `machine_id=None`, a machine with no logs, `skip` at or past the matching rows, or `limit=0` returns `[]`.
- **R8.** [BUG-1101] (HR-16) A log whose machine belongs to another workspace is not returned: asked for that machine with the log's `workspace_id`, `[]`. *(Today: it is returned.)* With the machine's own workspace it is `[]` today too (R2).
- **R9.** A negative `limit` or `skip` makes Postgres reject the query, as in `get_by_workspace`.

### `get_by_type(db, maintenance_type, *, workspace_id, skip=0, limit=100)`
Used by `list_logs` with `?maintenance_type=…` and no machine.
- **R1.** Returns the live logs of that type and workspace. Logs of another type, or of another workspace with that type, are never returned. Soft-deleted logs follow `get_by_workspace` R2.
- **R2.** Input forms: a plain string equal to a member's value (`"REPAIR"`) works like the member. `None` returns `[]`, with no error. Any other string (`"BOGUS"`, lower case `"repair"`) makes Postgres reject the query (`DataError`, pgcode `22P02`).
- **R3.** Order follows `get_by_workspace` R4 and, [BUG-1100], R4a.
- **R3a.** The state of the log's machine and factory is not looked at, as `get_by_workspace` R3.
- **R4.** `skip`, `limit`, empty results and negative values follow `get_by_workspace` R5, R6, R7.
- **R5.** [BUG-1101] (HR-16) A log whose machine belongs to another workspace is not returned, as `get_by_workspace` R8. *(Today: it is returned.)*

### `get_by_machine_and_type(db, machine_id, maintenance_type, *, workspace_id, skip=0, limit=100)`
Used by `list_logs` with both filters.
- **R1.** Returns the live logs matching machine, type and workspace, all three. Soft-deleted logs follow `get_by_workspace` R2.
- **R2.** `maintenance_type` forms follow `get_by_type` R2; `machine_id` forms follow `get_by_machine` R7.
- **R3.** Order follows `get_by_workspace` R4 and, [BUG-1100], R4a.
- **R3a.** The state of the machine and its factory is not looked at, as `get_by_machine` R4.
- **R4.** `skip`, `limit`, empty results and negative values follow `get_by_workspace` R5, R6, R7.
- **R5.** [BUG-1101] (HR-16) A log whose machine belongs to another workspace is not returned, as `get_by_machine` R8. *(Today: it is returned.)*

### `soft_delete(db, *, db_obj, deleted_by)`
Used by `MachineMaintenanceLogManager.delete_log` (which first answers 404 / 400 "already deleted"). Returns the same instance, flushed, not committed.
- **R1.** Given a live log, after the call `is_deleted = True`, `is_active = False`, `deleted_by` = the given id, and `deleted_at` is set.
- **R1a.** [BUG-1102] `deleted_at` = the current time from `utcnow()` (naive UTC), whatever the database's `TimeZone`. *(Today: the database's `now()`, as local time in the session's `TimeZone`.)*
- **R2.** No other column is changed by the method: `workspace_id`, `machine_id`, `maintenance_type`, `maintenance_date`, `summary`, `cost`, `performed_by`, `created_at`, `created_by`, `updated_by` keep their values (no `updated_by` stamp). `updated_at` becomes non-null because the ORM sets it on the UPDATE.
- **R3.** Given a log that is already soft-deleted, no error is raised and the stamp is overwritten: `deleted_by` becomes the new id, and `deleted_at` is written again as in R1a.
- **R4.** The change is flushed and not committed: in the same session the log is no longer returned by the four lists and is still returned by `get_by_id_and_workspace`; rolling back makes it live again with an empty stamp. The returned object is the very instance passed in.
- **R5.** No workspace check: the log passed in is deleted whatever workspace it belongs to. Only that row changes.
- **R6.** Given a `deleted_by` that is not an existing profile id, the flush fails (`IntegrityError`, foreign key `machine_maintenance_logs_deleted_by_fkey`) and nothing is saved.
- **R7.** `deleted_by=None` is accepted: the log is deleted with `deleted_by` empty.

Side effects: one `machine_maintenance_logs` row updated and flushed; no commit; no activity event (the manager writes those); the machine is not touched.

### `restore(db, *, db_obj)` (not in a bug; must not change)
- Sets `is_deleted = False`, `is_active = True`, `deleted_at = None`, `deleted_by = None`; no other column; no workspace or machine check; issues no UPDATE for a log already live and active; flushes, does not commit; returns the same instance.

### Inherited generic methods (not overridden; must not change)
`create`, `update`, `get`, `get_multi`, `remove` stay as they are.

## 4. Rules that apply

- **HR-6. Every paged or top-N result has a stable order.** Standing decision: no order recipe counts as deterministic unless it ends in `id`. Where a list already has a chosen order (here: newest date first), keep it and add `id` as the last key, in the direction given in the Intended text (descending).
- **HR-5. Filter first, then page.** The BUG-1101 filter must be in the query, before `skip` / `limit`.
- **HR-16. Nothing links across workspaces.** A row linking to another workspace's row is invalid data, never a normal state; no response shows another workspace's ids or names. What a reader gets instead was decided for machine stock (BUG-1086): not found, everywhere. Compare only the machine's `workspace_id`, never its state.
- **Standing decision (owner, 2026-10-30):** ledgers and history logs are history and stay complete; a maintenance log is history, so a deleted machine or factory does not hide its logs (R3 of each list). The BUG-1101 filter must not change that.
- **Time stamps:** soft-delete times are naive UTC from `utcnow()`, as on machines, factories and sections.
- No owner answer (OQ-n) touches these bugs.

## 5. Scope

- May change: `app/dao/machine_maintenance_log.py` only.
- No migration, no schema or API change. No existing row is changed or deleted.

## 6. Out of scope (leave alone)

- `app/managers/machine_maintenance_log_manager.py`: BUG-1150 (`get_log` returns deleted logs), BUG-1151 (`updated_by` on no-op update), BUG-1152 (`machine_id=0` lists everything), BUG-1153 (cost and performer cannot be cleared), BUG-1154 (log added to a machine of a deleted factory).
- `app/schemas/machine_maintenance_log.py`: BUG-1155, BUG-1156, BUG-1157, BUG-1158 (summary / performer / cost validation).
- BUG-1159 (frontend only), BUG-100 and BUG-101 (`app/dao/base.py`).
- `created_at` / `updated_at` from the database clock on this table: a project-wide decision, not this unit.
