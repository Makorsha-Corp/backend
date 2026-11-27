# Impact review 1: dao-machine_maintenance_log

Date: 2026-11-27. Diff: worktree `bugfix/dao-machine_maintenance_log`, `git diff origin/main -- app alembic`
(one file, `app/dao/machine_maintenance_log.py`; no alembic change).

## Old code really showed each bug (confirmed, the fixer had not reproduced)

Same throwaway rowkit script (`marker_test`, rolled back) run against the main checkout and the worktree:

| Check | Old code (main) | New code (worktree) |
|---|---|---|
| 4 logs on one date + 1 cross-workspace log, `get_by_workspace` | ids ascending `[..61, ..62, ..63, ..64, ..65]` (physical order, no tie-break) and includes the cross-workspace log ..65 | `[..69, ..68, ..67, ..66]`: id descending, cross-workspace log ..70 absent |
| `get_by_id_and_workspace` on the cross-workspace log | returns the row | `None` |
| `soft_delete` under `SET LOCAL TIME ZONE 'Asia/Dhaka'` | `deleted_at` = 02:45 next day (Dhaka local, +6 h off UTC) | `deleted_at` = Python UTC (20:45) |

Compiled SQL (Postgres dialect, `scripts/bugfix/compile_query.py`), before: `FROM machine_maintenance_logs WHERE ... ORDER BY maintenance_date DESC`.
After: `FROM machine_maintenance_logs JOIN machines ON machines.id = machine_maintenance_logs.machine_id
WHERE machines.workspace_id = machine_maintenance_logs.workspace_id AND <own filters> ORDER BY
machine_maintenance_logs.maintenance_date DESC, machine_maintenance_logs.id DESC LIMIT .. OFFSET ..`.
So all three fixes target the real cause.

## Upstream

- Only caller: `MachineMaintenanceLogManager` (`self.log_dao`), wrapped by `MachineMaintenanceLogService`;
  nothing else in `app/` imports the DAO (grepped `machine_maintenance_log_dao`, `MachineMaintenanceLogDAO`).
- `get_log`, `update_log`, `delete_log` read through `get_by_id_and_workspace` and answer their normal 404
  on `None`, so a cross-workspace log now gives 404 everywhere (HR-16 / BUG-1086 rule). `delete_log`'s
  "already deleted → 400" check still sees same-workspace deleted logs (the by-id query has no `is_deleted` filter).
- `list_logs` returns the DAO list as is; no re-sort or set conversion, so the id tie-break reaches the endpoint.
- No sibling fallback path; no guard.

## Downstream

- Inner join on `machines` with an explicit ON clause: `machine_id` is a NOT NULL FK to `machines.id`,
  so no valid log is dropped and none duplicated; `.first()` and paging behave as before.
- The join reads only `machines.workspace_id`, never `is_deleted`/`is_active` of machine or factory:
  owner's history decision (R3 of each list) kept; confirmed by the fixer's check and by the query text.
- No locks, no eager loads involved (model relationships are default lazy). No commit added; `soft_delete` still only flushes.
- `utcnow` imported at module level (the tests' patch target), same as `app/dao/machine.py`.

## Query shape / workspace bound

ORDER BY uses ORM columns (`machine_maintenance_logs.id DESC`), not text. Filter is in the WHERE before
OFFSET/LIMIT (HR-5). Every query is bounded by the log's `workspace_id` filter and the join compares
the machine's workspace to the log's (HR-16). AND-only predicates, no NULL branches.

## API contract

No shape, status-code, input or message change. Value-only changes (see `contract.md`): tie order on the
list, cross-workspace (invalid) rows now hidden / 404, `deleted_at` now UTC. Frontend
(`features/machineMaintenanceLogs`, `MachineDetailBody.tsx`) renders the list as given and does not show `deleted_at`.

## Database

No constraint, index or migration: no check or repair script needed. Cross-workspace rows stay
(left for `scripts/find_cross_workspace_rows.py` clean-up, as the brief says).

## Neighbouring bugs

- BUG-1150 (manager `get_log include_deleted`): independent; MMLM-G-21/22 keep their xfail (label fix on main).
- BUG-1805 (calendar maintenance collector): its intended rule also hides BUG-1101 rows, but the calendar
  does not use this DAO; no clash. When BUG-1805 is fixed, reusing this DAO's filter would be the natural choice.
- BUG-1152 (`machine_id=0` lists everything) is in the manager; unaffected.

## Shortcuts / scope

None. One private helper shared by the five reads (no copied logic). Inherited `get`/`get_multi` are
untouched, as the brief requires. Nothing outside the brief changed.

## New bugs found

None.

## Verdict

**APPROVE.** No contract change requiring frontend work (`contract.md` written).
