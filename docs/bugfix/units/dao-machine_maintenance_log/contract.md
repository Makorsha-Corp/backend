# Contract: dao-machine_maintenance_log

No contract change (no frontend stage). Response shape, status codes, inputs and error messages of
`GET`, `PUT`, `DELETE /machine-maintenance-logs/` are unchanged.

Value-only changes (no frontend work needed; the UI renders the list as given and does not show `deleted_at`):
- Logs on the same `maintenance_date` now come back highest id first, and paging no longer repeats or skips.
  Example: logs 11, 12, 13 all dated 2026-11-20, `limit=1` → pages give 13, 12, 11 (before: any order, one could repeat).
- A log whose machine belongs to another workspace (invalid data, HR-16) is no longer listed, and get / update /
  delete on it answer 404 `Maintenance log with ID <id> not found`. Example: log 40 in workspace 1 pointing at
  machine 7 of workspace 2 → absent from `GET /machine-maintenance-logs/`, `GET /machine-maintenance-logs/40` → 404.
- `deleted_at` of a deleted log is now naive UTC, like machines. Example: deleted at 17:08 UTC on a server
  set to Asia/Dhaka → stored 17:08 (before: 23:08).
