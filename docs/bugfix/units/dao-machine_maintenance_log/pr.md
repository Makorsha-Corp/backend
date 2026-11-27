## Fix: maintenance logs keep a fixed order, logs tied to another company's machine stay hidden, and delete times are in UTC

**Fixes BUG-1100, BUG-1101 and BUG-1102.** One file (`app/dao/machine_maintenance_log.py`). No database change, no API shape change.

---

### What was wrong

**1. A maintenance log tied to another workspace's machine was shown (BUG-1101). This is the one that matters most.**

Every maintenance log belongs to a workspace and points at a machine. The code only checked the log's own workspace, never the machine's. If bad data ever linked a log to a machine of a *different* workspace, that log was listed, opened, edited and deleted like any other, showing the other workspace's machine id. House rule HR-16 says links across workspaces are never allowed and count as invalid data.

*Example:* log 40 sits in Rahman Textiles' workspace but points at machine 7, which belongs to another company. Before, Rahman Textiles saw log 40 in its maintenance list, and opening it showed machine 7. Now log 40 is absent from the list, and opening, editing or deleting it gives the usual "Maintenance log with ID 40 not found".

**2. Logs on the same date came back in random order (BUG-1100)**

The list is sorted newest date first, but logs on the same date had no second sort key. The database could return them in any order, so the list could reshuffle, and paging could show one log twice and skip another.

*Example:* logs 11, 12 and 13 are all dated 20 Nov 2026. With one log per page, the pages could show 12, 12, 11, and log 13 never appeared. Now the pages always show 13, 12, 11.

**3. The delete time depended on the database's time zone (BUG-1102)**

When a log was deleted, its `deleted_at` came from the database clock in the session's local time zone, not in UTC as everywhere else (machines, for example).

*Example:* a log deleted at 17:08 UTC on a server set to Asia/Dhaka was stored as 23:08. Now it is stored as 17:08.

---

### What changed

All in `app/dao/machine_maintenance_log.py`:

```diff
+ def _same_workspace_logs(db):                     # shared start for every read
+     return db.query(MachineMaintenanceLog).join(
+         Machine, Machine.id == MachineMaintenanceLog.machine_id
+     ).filter(Machine.workspace_id == MachineMaintenanceLog.workspace_id)   # machine must be in the log's workspace

  # the four lists and get-by-id
- return db.query(MachineMaintenanceLog).filter(
+ return _same_workspace_logs(db).filter(            # cross-workspace logs are left out, before paging

  # the four lists
- .order_by(desc(MachineMaintenanceLog.maintenance_date))
+ .order_by(desc(MachineMaintenanceLog.maintenance_date), desc(MachineMaintenanceLog.id))   # tie-break on id

  # soft_delete
- db_obj.deleted_at = func.now()
+ db_obj.deleted_at = utcnow()                       # app clock, naive UTC
```

The rules behind it: house rule HR-16 (no links across workspaces, treat them as not found), HR-5 (filter before paging), HR-6 (every list ends its sort with id), and the earlier delegated decision that delete times use `utcnow()` like machines.

### What you'll notice

- Maintenance lists for a machine, for a type or for the whole workspace keep the same order every time. Same-date logs show newest entry first, and paging no longer repeats or skips a log.
- A log linked to another workspace's machine no longer appears anywhere, and opening, editing or deleting it gives 404. These logs should not exist; any that do stay in the database for a one-off clean-up (`scripts/find_cross_workspace_rows.py`).
- Delete times of maintenance logs are now in UTC. The UI does not show this field.
- **Unchanged on purpose:** logs of a deleted or inactive machine or factory are still listed (owner decision: the history stays complete). Only the machine's workspace is checked, never its state.

### What to look at when reviewing

- **Every read now joins `machines`.** `machine_id` is a required link to a machine, so the join can't drop a valid log or count one twice. Both ids are indexed, so the cost is small.
- **Cross-workspace logs are hidden, not deleted or repaired.** That follows the house rule. If you'd rather have them fixed in the data now, that's a separate clean-up.
- **The general base-class reads (`get`, `get_multi`) are not changed.** The brief kept them as they are, and no maintenance-log endpoint uses them.
- **Left for another PR:** BUG-1150 (opening a deleted log by id). Two tests need both fixes and stay marked as known failures until BUG-1150 is fixed.

**Good to auto-merge:** no. The fix is one file with no migration and no API change, but the workspace filter adds a join to every read, and that is more than the trivial pattern.

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:** the only caller is `MachineMaintenanceLogManager` (wrapped by the service). `get_log`, `update_log` and `delete_log` already answer 404 when nothing is found. `list_logs` returns the list as is. The frontend (`features/machineMaintenanceLogs`, `MachineDetailBody.tsx`) shows the list as given and does not show `deleted_at`, so there is no frontend PR.
- **Contract:** same response shape, status codes and messages. Only values change: the order of same-date logs, cross-workspace logs hidden, and `deleted_at` in UTC.
- **Tests:** the 46 tests marked as known failures for these bugs (DAO, maintenance-log manager and service) now pass, and their markers are removed. Two more stay marked because they also need BUG-1150. Every other test in the full suite had the same result before and after (flip check CLEAN, base `f27d6ca`). CI has not run yet.
- **Database:** no migration; no data-check script needed.
- **Commits:** `5966805` (fix).

</details>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
