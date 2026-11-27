# Spec — `app/dao/machine_maintenance_log.py`

> **Status:** APPROVED (2026-10-31; nothing open)
> **Source commit:** e48a092

> **Review round 2026-10-31.** **Delegated:** P1, P2, P3, Q1, Q2 accepted as suggested, decided by Claude under the reviewer's delegation (2026-10-31). None of these is the owner's own answer. A maintenance log is history. FU-1 (d) and (g) stay **OWNER** for the manager review. The house-rule lines stand.
>
> **Revision 2026-10-31, for the case designer:** `soft_delete` R1 is split: R1a is new and tagged [BUG-1102]; R3 no longer pins the value of `deleted_at`. ✅ added to the rules of P1, P2, P3 and Q1. Externals to mock and the notes on `now()` changed.

> **Standing reviewer decisions applied here (not asked again):**
> 1. Soft-deleted rows are kept but must not show up in lists or be counted (inventory DAO Q2, owner, 2026-10-10). The log's own soft delete does that here, and the four lists honour it.
> 2. Things of a soft-deleted parent are hidden by the parent's state ("hidden, not cascaded", 2026-10-11), **but ledgers and history logs are history and stay complete** (owner, 2026-10-30; inventory ledger DAO Q3, Q4, Q5). A maintenance log is history (Q1).
> 3. Raw lookups stay raw (HR-4 scope; base DAO spec).
> 4. Physical row order and collation order are **not** an order: a missing `ORDER BY`, or a sort key that can tie with no tie-break, is a bug.
> 5. A row linking to another workspace's row is invalid data; no response shows another workspace's ids (HR-16). What a reader gets instead was decided for machine stock: not found, everywhere (BUG-1086).
>
> **Verified by running** (scripts `mml_h.py`, `mml_p0.py`, `mml_p1.py`, `mml_p2.py` in the agent's scratch folder, each transaction rolled back against `marker_test`; nothing committed): every "Today:" note below; the table's columns, nullability, defaults, foreign keys, indexes, enum labels, no check constraint, no trigger, no table referencing it; `ORDER BY maintenance_date DESC` with no tie-break, in the SQL; five rows on one date: order changes after one row is updated, and paging one row at a time **repeats one row and misses another** (`[571], [571], [573], [574], [570]`, row 572 never shown); defaults and caps (101 rows → 100 from all four lists, 101 with `limit=1000`); negative paging errors in all four; `limit=0`; own / other / unknown workspace, machine and id; a soft-deleted log, an inactive live log; logs of a soft-deleted machine, of a machine in a soft-deleted factory, of inactive machines and factories in all five reads; a stored row linked to another workspace's machine in all five reads; `maintenance_type` as a member, a matching string, a wrong string, `None`; `soft_delete` and `restore` in full, including already deleted, already live, an unknown profile, `None`, savepoint rollback; `deleted_at` under `America/New_York`, `UTC`, `Asia/Dhaka`; inherited `create`, `update`, `remove`, `get`, `get_multi`; cost rounding and range; hard-delete blocks. The Follow-ups marked verified were run through `MachineMaintenanceLogManager` (not the service, so nothing was committed). **Not run:** anything over HTTP; two concurrent transactions; the intended behavior of the bug rules.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | Reading one log by id also finds a soft-deleted log | intended here; `get_log` must answer 404 (manager review) | Claude, delegated |
| P2 | "Restore a deleted log" is never called | intended — keep, per machine DAO Q5 | Claude, delegated |
| P3 | A restore records nobody | intended for the DAO, per machine DAO Q8 | Claude, delegated |
| Q1 | Logs of a deleted machine stay listed | intended — a maintenance log is history | Claude, delegated |
| Q2 | The delete time comes from the database clock in the database's own time zone, not UTC as on machines and factories | bug — use `utcnow()` (BUG-1102) | Claude, delegated |

None of these is marked OWNER: no money, stock or order figure depends on them. The one money question this module raises, a negative `cost`, is at the schema and is FU-1 (d), **OWNER**.

### House-rule violations — applied automatically

- **HR-6** `get_by_workspace` R4a, `get_by_machine` R5, `get_by_type` R3, `get_by_machine_and_type` R3 — sorted by `maintenance_date` only; logs on one date have no order, and paging repeats and misses rows (verified: five logs on one date, paged one at a time, showed one twice and one never). Intended: `maintenance_date` descending, then `id` descending, before `skip` / `limit` (BUG-600 precedent: newest first by date, ties newest insert first). The BUG-100 fix does not reach `get_by_workspace`: this override has its own query.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1100 (pattern `unordered-pagination`), one ID for the four queries: same line, same fix, same file.
- **HR-16** `get_by_workspace` R8, `get_by_id_and_workspace` R6, `get_by_machine` R8, `get_by_type` R5, `get_by_machine_and_type` R5 — a stored log with `workspace_id` = A pointing at a machine of workspace B is returned to A, and the response shows B's `machine_id`. Nothing writes such a row today (the manager reads the machine by workspace, and `MachineMaintenanceLogUpdate` has no `machine_id`), but rows already stored stay, and `scripts/find_cross_workspace_rows.py` covers this foreign key. Intended, per BUG-1086: treated as not found, in the query, before paging. Only the machine's `workspace_id` is compared, never its state, so this does not touch Q1. The by-id lookup changes here and not in the manager, because `get_log`, `update_log` and `delete_log` all read through it and no caller needs the row: the audit script uses its own SQL.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** BUG-1101 (pattern `cross-workspace-row-exposed`).

Checked and **not** a new line here: **HR-4** — the four lists filter `is_deleted` in the query; the raw by-id lookup is P1. **HR-5** — every filter is in the query; BUG-1101's must stay there. **HR-7** — `GET /machine-maintenance-logs/` already requires `1 <= limit <= 1000` and `skip >= 0`. **HR-8** — no `LIKE`. **HR-9** — this DAO writes no `updated_by`; `soft_delete` and `restore` never touch it; the no-op stamp is the manager's (FU-1 (e)). **HR-10** — a plain soft delete and restore need no lock, and no stock or money moves. **HR-15** — no Python rounding anywhere here; `cost` is rounded by the `Numeric(15, 2)` column, half away from zero (verified: 0.125 → 0.13, 2.675 → 2.68, -1.005 → -1.01). **HR-1, HR-2, HR-3** — nothing in this DAO; `summary` and `performed_by` are at the schema (FU-1 (c)).

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-10-31))

### P1. Reading one log by id also finds a soft-deleted log — ✅ intended
**Background:** Deleting a log sets `is_deleted = True` and the row stays. `get_by_id_and_workspace` is a line-for-line copy of the base method and does not look at `is_deleted`. HR-4 keeps that lookup raw, because "already deleted → 400" checks and `restore` need it, and says to flag the manager that exposes the result.
**What happens today:** A soft-deleted log is returned. `update_log` and `delete_log` then answer 400 as they should; `get_log` returns it with 200 (verified).
**Example:** Log 12 is deleted. `DELETE /machine-maintenance-logs/12/` a second time answers 400 "Maintenance log is already deleted", which needs this lookup. `GET /machine-maintenance-logs/12/` answers 200 with the deleted log, which is the manager's to fix.
**Rules affected:** `get_by_id_and_workspace` R4
**Answer:** intended — per HR-4 scope: raw at the DAO; `MachineMaintenanceLogManager.get_log` must answer 404 by default (BUG-966 precedent), logged in that manager's spec, FU-1 (a)
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-31): rule unchanged. Rules: `get_by_id_and_workspace` R4 ✅.

### P2. "Restore a deleted log" is never called — ✅ keep
**Background:** `restore` brings a soft-deleted log back. No endpoint, service or manager method calls it, and no list can show a deleted log to pick one. For machines the owner answered "keep restore" (machine DAO Q5, 2026-10-10), because a delete must be undoable once the feature exists. The same holds for factories and sections.
**What happens today:** The method works (verified) and nothing reaches it.
**Example:** A user removes a log by mistake from the machine's activity list. There is no button or API call to bring it back.
**Rules affected:** `restore` (all)
**Answer:** intended — keep, per machine DAO Q5 precedent: specified in full below
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-31): kept, not on the dead-code list. Rules: `restore` R1–R7 ✅.

### P3. A restore records nobody — ✅ intended
**Background:** `soft_delete` stamps who and when, and the manager writes a `maintenance_removed` activity entry. `restore` has no "who" argument.
**What happens today:** After a restore `deleted_at` and `deleted_by` are empty, `updated_by` keeps its old value and no activity entry exists.
**Example:** Rahim removes a log on Monday, Karim restores it on Tuesday once the feature exists. The row shows neither.
**Rules affected:** `restore` R2
**Answer:** intended for the DAO — per machine DAO Q8 precedent: the manager method that will call `restore` records the user and writes the activity entry (FU-2)
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-31): rule unchanged. Rules: `restore` R2 ✅.

### New questions

### Q1. Logs of a deleted machine stay listed — ✅ intended
**Background:** A maintenance log records work done on a machine, with an optional `cost`. Things of a soft-deleted parent are normally hidden by the parent's state, but ledgers and history logs are history and stay complete (owner, 2026-10-30). `delete_machine` R4b already says logs neither block a delete nor change with it. Unlike a ledger, a log can be edited and deleted by itself; nothing counts these rows, and no code in `app/` or the frontend adds up `cost`.
**What happens today:** All four lists and the by-id lookup ignore the machine and its factory: logs of a soft-deleted machine, or of a machine in a soft-deleted factory, are returned like any other (verified). A log the user deleted stays hidden; that is the log's own state and is not part of this question.
**Example:** "Press 4" had a 4 000 taka bearing change in March and is deleted in June. `GET /machine-maintenance-logs/` still lists the March job, and `?machine_id=<Press 4>` still shows its history. If logs followed the machine, the record of that work would vanish while the machine's ledger entries stay.
**Rules affected:** `get_by_workspace` R3, `get_by_id_and_workspace` R5, `get_by_machine` R4, `get_by_type` R3a, `get_by_machine_and_type` R3a
**Suggested answer:** `intended` — a maintenance log is history: it records work that really happened, it is not a count, and hiding it would leave a gap next to the machine's ledger and activity log, which both stay. If a report ever adds up `cost`, whether deleted machines count is that report's decision. Alternative: `bug — hidden by the parent's state, rows untouched, as stock (BUG-979)`.
**Answer:** intended — a maintenance log is history
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-31): logs of a soft-deleted machine, or of a machine in a soft-deleted factory, stay listed; the log's own soft delete still hides it. Rules unchanged: `get_by_workspace` R3 ✅, `get_by_id_and_workspace` R5 ✅, `get_by_machine` R4 ✅, `get_by_type` R3a ✅, `get_by_machine_and_type` R3a ✅.

### Q2. The delete time depends on the database's time zone — 🐞 BUG-1102
**Background:** `deleted_at` is a timestamp with no time zone. Seven of the eleven `soft_delete` methods (machine, factory, section, department, delivery method, work order type, attachment) write Python's `utcnow()`, so naive UTC. This one, like inventory, product and work order, writes the database's `now()`, which lands in the column as local time in the session's `TimeZone`. The application sets no `TimeZone`, so the database's own setting decides; the test database's is `America/New_York`. Production's is not known from this repository: `SHOW timezone` tells. `created_at` and `updated_at` on this table come from the database clock too, on every table that declares them this way, which is why that part is a follow-up (FU-3), not this question.
**What happens today:** At 17:08 UTC, `deleted_at` is 13:08 under `America/New_York`, 17:08 under `UTC`, 23:08 under `Asia/Dhaka` (verified). A machine deleted in the same moment records 17:08 under all three.
**Example:** On a server set to `Asia/Dhaka`, a machine and one of its logs are removed at the same moment. The API shows the machine deleted at 17:08 and the log at 23:08, with no time zone on either to explain it.
**Rules affected:** `soft_delete` R1
**Suggested answer:** `bug — deleted_at is written from utcnow(), as machine DAO soft_delete R1`. On a database set to UTC nothing visible changes. Alternative: `intended`, keeping `deleted_at` in step with `created_at` and `updated_at` on the same row until FU-3 is decided.
**Answer:** bug — `deleted_at` is written from `utcnow()`, as machine DAO `soft_delete` R1
**Resolution:** decided by Claude under the reviewer's delegation (2026-10-31): 🐞 BUG-1102 (pattern `database-clock-timestamp`). The fix imports `utcnow` the way `app/dao/machine.py` does. `created_at` and `updated_at` stay with the database clock until FU-3 is decided, so on a database not set to UTC one row can mix the two. Rules: `soft_delete` R1 (split), R1a (tagged), R3.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Machine maintenance log manager, service, endpoint, schema** (`app/managers/machine_maintenance_log_manager.py`, next in this group) | All verified through the manager. (a) `get_log` returns a soft-deleted log with 200 (HR-4, BUG-966 precedent). (b) `if machine_id` treats `0` as "no filter": `machine_id=0` lists the whole workspace (pattern `falsy-zero-treated-as-missing`). (c) `MachineMaintenanceLogCreate` / `Update` have no checks: a blank or whitespace-only `summary` is stored (HR-1 or a required-text decision), `performed_by` is stored untrimmed and `"  "` counts as a value (BUG-967 precedent), `performed_by` of 256 characters is a `DataError` (BUG-972 precedent), `summary` has no length limit. (d) **OWNER, money:** `cost` has no minimum: `-5` is stored as `-5.00` (BUG-711, BUG-1079 precedent says refuse at the input schemas; a credit or refund could be a reason to allow it). `cost` beyond the column (`1e20`, or `10000000000000`) is a `DataError`, so a 500. (e) HR-9: `update_log` stamps `updated_by` and `updated_at` when nothing changes (verified: same `summary`, stamped, no activity entry). (f) `cost` and `performed_by` cannot be cleared: `null` is dropped by `exclude_none`, the old value stays with 200 (BUG-962, BUG-1075 precedent). (g) **OWNER, money:** the activity entry records the value as typed, not as stored: `cost` `5.001` on a log at `5.00` stores `5.00`, stamps the row and logs "5.00 → 5.001". `MachineMaintenanceLog.cost` holds the unrounded value until a refresh (inherited R4), and the comparison happens before the write. (h) `create_log` refuses a soft-deleted machine with 400 but accepts a live machine in a soft-deleted factory; `update_log` and `delete_log` do not look at the machine at all (patterns `write-to-soft-deleted-related-row`, BUG-1076, BUG-1083, BUG-1084). Q1 says logs are history: decide whether an old log may still be corrected. (i) BUG-1101: `get_log`, `update_log`, `delete_log` get `None` for such a row and answer their normal 404; nothing else changes there. (j) `maintenance_date` has no bound: a future date is stored although the log records work done. | P1, Q1, HR-16 line |
| FU-2 | **The future "restore log" feature**, if built | Must record the acting user (`updated_by`, HR-9) and write a `maintenance_restored`-style activity entry, and needs a way to find deleted logs: no list can show them. | P2, P3 |
| FU-3 | **Project-wide, owner of the time-zone decision** | `created_at` (`server_default=now()`) and `updated_at` (`onupdate=now()`) follow the database's `TimeZone` on this table, and the same declaration is used widely; `inventory`, `product` and `work_order` `soft_delete` have the same `func.now()` line as Q2. On a database not set to UTC, a row's stamps are not UTC while `performed_at` and `machines.deleted_at` are. Setting the database or connection to UTC would settle all of them at once. | Q2 |
| FU-4 | **Frontend** (`frontend/src/features/machineMaintenanceLogs/`) | Only the delete mutation is used, from the machine's activity list (`MachineDetailBody.tsx`). The list, get, create and update hooks are exported and called by nobody, so nothing in the application creates a log today: rows arrive only through direct API calls. Whether the page is unfinished or the endpoints are unused is worth a product answer before the manager's tests are weighted. | Callers |
| FU-5 | **Machine activity event DAO** (`tests/unit/dao/machine_activity_event.spec.md`) | The events `maintenance_logged`, `maintenance_updated`, `maintenance_removed` carry `metadata.maintenance_log_id`. A deleted log's id stays in its old events, and the frontend still offers a delete on them: the second delete answers 400. | Callers |

## Overview
`MachineMaintenanceLogDAO` reads and soft-deletes `machine_maintenance_logs`, the record of maintenance work done on machines: type, date, summary, optional cost and the free-text name of who did it. The only caller is `MachineMaintenanceLogManager` (`GET`, `POST`, `PUT`, `DELETE /machine-maintenance-logs/`). It is meant to protect workspace isolation and to keep soft-deleted logs out of every list. It validates nothing and never commits; writes come from `soft_delete`, `restore` and the inherited `create`, `update`, which flush. `get_by_id_and_workspace` is a line-for-line copy of the base method; `get_by_workspace` is its own query, so a fix made only in `app/dao/base.py` reaches neither.

**Callables:** 7 specified (+ 1 section on inherited `BaseDAO` behavior specific to this model) · 1 not specified
**Externals to mock:** `utcnow`, patched at `app.dao.machine_maintenance_log.utcnow`, used by `soft_delete` only (BUG-1102). `restore` does not read the clock.
**Integration-only behavior:** none. (`skip >= 0`, `1 <= limit <= 1000` and the enum value of `maintenance_type` are enforced by `GET /machine-maintenance-logs/`, not here.)

**Model facts (table `machine_maintenance_logs`, class `app.models.machine_maintenance_log.MachineMaintenanceLog`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE (`machine_maintenance_logs_workspace_id_fkey`) | — |
| `machine_id` | Integer NOT NULL, FK `machines.id`, no cascade (`machine_maintenance_logs_machine_id_fkey`) | — |
| `maintenance_type` | Postgres enum `maintenancetypeenum` NOT NULL (`PREVENTIVE`, `REPAIR`, `EMERGENCY`, `INSPECTION`; `app.models.enums.MaintenanceTypeEnum`) | — |
| `maintenance_date` | Date NOT NULL | — |
| `summary` | Text NOT NULL, no length limit | — |
| `cost` | Numeric(15, 2), nullable | `NULL` |
| `performed_by` | String(255), nullable, free text, not a link to a profile | `NULL` |
| `created_at` | timestamp without time zone NOT NULL | database `now()` |
| `created_by` | Integer nullable, FK `profiles.id` | `NULL` |
| `updated_at` | timestamp without time zone, nullable | `NULL`; set to database `now()` by the ORM on every UPDATE |
| `updated_by` | Integer nullable, FK `profiles.id` | `NULL` |
| `is_active` | Boolean NOT NULL | `True` (Python default only) |
| `is_deleted` | Boolean NOT NULL | `False` (Python default only) |
| `deleted_at` | timestamp without time zone, nullable | `NULL` |
| `deleted_by` | Integer nullable, FK `profiles.id` (`machine_maintenance_logs_deleted_by_fkey`) | `NULL` |

- Indexes: primary key, plain `ix_machine_maintenance_logs_id`, `ix_machine_maintenance_logs_workspace_id`, `ix_machine_maintenance_logs_machine_id`. No unique constraint: any number of logs may share a machine, date and type. No check constraint, no trigger. No table references `machine_maintenance_logs`.
- Soft delete = `is_deleted = True` with `is_active = False`. The lists look only at `is_deleted`. Nothing in the application sets `is_active` apart from `soft_delete` and `restore`.
- Relationships: `machine` (lazy, backref `Machine.maintenance_logs`), `creator`, `updater`, `deleter`. No query here loads them.
- Parents, as used by Q1: `Machine` (`app.models.machine`): soft delete = `is_deleted = True` with `is_active = False`. `Factory` (`app.models.factory`): soft delete = `is_deleted = True`, `is_active` unchanged.
- Schemas (`app/schemas/machine_maintenance_log.py`): `MachineMaintenanceLogCreate` = `machine_id: int`, `maintenance_type`, `maintenance_date: date`, `summary: str`, `cost: Decimal | None = None`, `performed_by: str | None = None` (no `workspace_id`). `MachineMaintenanceLogUpdate` = the same five without `machine_id`, all optional. No validators, no minimums, no lengths. Pydantic rejects `NaN` and `Infinity` for `cost`. `MachineMaintenanceLogResponse` adds every other column.
- Time zone of the test database: `America/New_York`. Collation: `English_United States.1252` (libc).

**Notes for the test designer:**
- Use the module singleton `machine_maintenance_log_dao` (`from app.dao.machine_maintenance_log import machine_maintenance_log_dao`).
- **Parameter style differs by method:** `get_by_machine(db, machine_id, *, workspace_id, ...)`, `get_by_type(db, maintenance_type, *, workspace_id, ...)`, `get_by_machine_and_type(db, machine_id, maintenance_type, *, workspace_id, ...)` take their filters positionally or by name. `workspace_id`, `skip`, `limit` and every parameter of the other four methods are keyword-only (a positional call raises `TypeError`).
- Workspaces and profiles from `tests/unit/factories.py` (`make_workspace`, `make_profile`). Build the other rows directly (add + flush): `Factory(workspace_id, name, abbreviation)`, `Machine(workspace_id, factory_id, name)`, `MachineMaintenanceLog(workspace_id, machine_id, maintenance_type, maintenance_date, summary)`. The session runs with `autoflush=False`: flush before calling the DAO.
- **Parents (Q1):** soft-deleted machine = `is_deleted=True, is_active=False`; soft-deleted factory = `is_deleted=True` with a live machine in it; inactive-but-live = `is_active=False, is_deleted=False`.
- **Row order (BUG-1100):** order by date alone holds today and is a plain pass case. Ties are **not** deterministic today: write the tied-date cases to the intended order and mark them **non-strict** xfail (`strict=False`); never weaken the assertion. Today five rows on one date came back in insertion order until one was updated, so insert at least three, and update the lowest-id row before reading. Every case not about order compares **sets** of ids.
- **A row linked to another workspace (BUG-1101):** add it directly: `workspace_id` = A, `machine_id` = a machine of B. Today it is returned, deterministically → **strict** xfail, compared as sets. Check the row is still in the table afterwards with a raw query.
- **`now()` is the transaction start.** Each test is one transaction, so `created_at` and `updated_at` written in one test are equal. Assert `updated_at` became non-null, never "later than".
- **The clock (BUG-1102):** the module does not import `utcnow` today, so patch with `create=True`: `patch("app.dao.machine_maintenance_log.utcnow", create=True, return_value=NOW)`, with `NOW` a fixed naive datetime far from today. Today the patch is unused and `deleted_at` is the database's `now()`, which never equals `NOW`, deterministically → **strict** xfail. Keep the `is_deleted`, `is_active`, `deleted_by` checks of R1 in a separate plain pass case.
- **`cost` keeps the given value:** the object keeps the value as given until `db.refresh`.
- **Database errors:** wrap calls expected to raise in `with db.begin_nested():` inside `pytest.raises(...)` so the session stays usable. After a failed `soft_delete`, `db.refresh(row)` before reading it.
- **Not committed:** `sp = db.begin_nested()`, call, `sp.rollback()`, `db.refresh(row)`.

## Not specified
- `machine_maintenance_log_dao` — module-level singleton, no logic
- Inherited `BaseDAO` methods `get`, `get_multi`, `create`, `update`, `remove` — not overridden; specified in `tests/unit/dao/base.spec.md`. Only what is specific to this model is stated below ("Inherited `BaseDAO` methods on `MachineMaintenanceLog`").

The checklist (`docs/testing/unit-test-checklist-by-layer.md`) marks none of the seven methods as possibly unused. `restore` has no caller (P2); `get`, `get_multi` and `remove` have none on this DAO. The module's docstring says all query methods must filter by workspace: the seven methods here do, or act on an object already read; inherited `get` and `get_multi` do not and have no caller.

---

## `MachineMaintenanceLogDAO.get_by_workspace(db, *, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (override of the base method with its own query. Used by: `MachineMaintenanceLogManager.list_logs` ← `GET /machine-maintenance-logs/` with neither filter, with the caller's `skip` / `limit`)

**Purpose:** The workspace's maintenance logs, newest first, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `workspace_id` | int | equality on the row's `workspace_id` |
| `skip` | int, default `0` | rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |

**Returns:** a `list` of `MachineMaintenanceLog` instances (possibly empty).

**Rules:**
- **R1.** Returns the live logs with that `workspace_id`. Logs of another workspace never appear, even when they would fit on the page.
- **R2.** A soft-deleted log (`is_deleted = True`) is not returned and takes no place in the page: the filter runs before `skip` / `limit`. A log with `is_active = False`, `is_deleted = False` is returned.
- **R3.** ✅ (Q1) The state of the log's machine and factory is not looked at: logs of a soft-deleted machine, of a machine in a soft-deleted factory, and of inactive-but-live machines and factories are returned and take a place in the page.
- **R4.** Logs with different dates come back latest `maintenance_date` first.
- **R4a.** [BUG-1100] (HR-6) Logs on the same date come back highest `id` first, before `skip` / `limit`, so consecutive windows partition the logs with no repeats or gaps. *(Today: no tie-break; five logs on one date paged one at a time showed one log twice and one never.)*
- **R5.** At most `limit` rows are returned after skipping `skip`; with the defaults at most 100: given 101 logs, exactly 100, and with `limit=1000`, 101.
- **R6.** An unknown workspace, a workspace with no logs, `skip` at or past the number of rows, or `limit=0` returns `[]`.
- **R7.** A negative `limit` or `skip` makes Postgres reject the query (see Errors).
- **R8.** [BUG-1101] (HR-16) A log whose machine belongs to another workspace is not returned and takes no place in the page; the row is not changed. *(Today: it is returned, showing the other workspace's `machine_id`.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInLimitClause`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInResultOffsetClause`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## `MachineMaintenanceLogDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (override identical to `BaseDAO.get_by_id_and_workspace`. Used by: `MachineMaintenanceLogManager.update_log`, `get_log`, `delete_log`, each answering 404 `Maintenance log with ID <id> not found` on `None`)

**Purpose:** One log by id, inside a workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `id` | int | equality on the primary key |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** the `MachineMaintenanceLog` instance (the one the session holds), or `None`.

**Rules:**
- **R1.** Given a log with that id in that workspace, it is returned.
- **R2.** Given a log with that id in another workspace, `None` is returned (indistinguishable from not found).
- **R3.** Given an unknown id or `id=0`, `None` is returned, with no error.
- **R4.** ✅ (P1) A soft-deleted log is returned like any other.
- **R5.** ✅ (Q1) The state of the log's machine and factory is not looked at.
- **R6.** [BUG-1101] (HR-16) A log whose machine belongs to another workspace is not found: `None`, with the row's own `workspace_id` as well; the row is not changed. *(Today: it is returned.)*

**Errors:** none.

**Side effects:** none

---

## `MachineMaintenanceLogDAO.get_by_machine(db, machine_id, *, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `MachineMaintenanceLogManager.list_logs` ← `GET /machine-maintenance-logs/?machine_id=…`, with the caller's `skip` / `limit`)

**Purpose:** One machine's maintenance history, newest first, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `machine_id` | int | equality on the row's `machine_id`; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |
| `skip` | int, default `0` | rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |

**Returns:** a `list` of `MachineMaintenanceLog` instances (possibly empty).

**Rules:**
- **R1.** Returns the live logs with that `machine_id` and that `workspace_id`. Logs of another machine are never returned.
- **R2.** A call with the right machine id and another workspace returns `[]`.
- **R3.** Soft-deleted logs follow `get_by_workspace` R2.
- **R4.** ✅ (Q1) The state of the machine and its factory is not looked at: asked for a soft-deleted machine, or a machine in a soft-deleted factory, the logs are returned.
- **R5.** Order follows `get_by_workspace` R4 and, [BUG-1100], R4a.
- **R6.** `skip` and `limit` follow `get_by_workspace` R5.
- **R7.** An unknown machine id, `machine_id=0`, `machine_id=None`, a machine with no logs, `skip` at or past the matching rows, or `limit=0` returns `[]`.
- **R8.** [BUG-1101] (HR-16) A log whose machine belongs to another workspace is not returned: asked for that machine with the log's `workspace_id`, `[]`. *(Today: it is returned.)* With the machine's own workspace it is `[]` today too (R2).
- **R9.** A negative `limit` or `skip` makes Postgres reject the query, as in `get_by_workspace`.

**Errors:** as `get_by_workspace`.

**Side effects:** none

---

## `MachineMaintenanceLogDAO.get_by_type(db, maintenance_type, *, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `MachineMaintenanceLogManager.list_logs` ← `GET /machine-maintenance-logs/?maintenance_type=…`, with no `machine_id` or `machine_id=0`, with the caller's `skip` / `limit`)

**Purpose:** The workspace's logs of one maintenance type, newest first, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `maintenance_type` | `MaintenanceTypeEnum` | equality on the row's `maintenance_type`; the endpoint only lets members through. Not validated here |
| `workspace_id` | int | equality on the row's `workspace_id` |
| `skip` | int, default `0` | rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |

**Returns:** a `list` of `MachineMaintenanceLog` instances (possibly empty).

**Rules:**
- **R1.** Returns the live logs of that type and workspace. Logs of another type, or of another workspace with that type, are never returned. Soft-deleted logs follow `get_by_workspace` R2.
- **R2.** Input forms: a plain string equal to a member's value (`"REPAIR"`) works like the member. `None` returns `[]`, with no error. Any other string (`"BOGUS"`, lower case `"repair"`) makes Postgres reject the query (see Errors).
- **R3.** Order follows `get_by_workspace` R4 and, [BUG-1100], R4a.
- **R3a.** ✅ (Q1) The state of the log's machine and factory is not looked at, as `get_by_workspace` R3.
- **R4.** `skip`, `limit`, empty results and negative values follow `get_by_workspace` R5, R6, R7.
- **R5.** [BUG-1101] (HR-16) A log whose machine belongs to another workspace is not returned, as `get_by_workspace` R8. *(Today: it is returned.)*

**Errors:** as `get_by_workspace`, and:
| Condition | Raises | Detail message |
|---|---|---|
| `maintenance_type` is a string that is not a member's value | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidTextRepresentation`, `.orig.pgcode == "22P02"` | — (not asserted) |

**Side effects:** none

---

## `MachineMaintenanceLogDAO.get_by_machine_and_type(db, machine_id, maintenance_type, *, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `MachineMaintenanceLogManager.list_logs` ← `GET /machine-maintenance-logs/?machine_id=…&maintenance_type=…`, with the caller's `skip` / `limit`)

**Purpose:** One machine's logs of one maintenance type, newest first, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `machine_id` | int | as `get_by_machine` |
| `maintenance_type` | `MaintenanceTypeEnum` | as `get_by_type` |
| `workspace_id` | int | equality on the row's `workspace_id` |
| `skip` | int, default `0` | rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |

**Returns:** a `list` of `MachineMaintenanceLog` instances (possibly empty).

**Rules:**
- **R1.** Returns the live logs matching machine, type and workspace, all three: another type on that machine, that type on another machine, and the same pair in another workspace are not returned. Soft-deleted logs follow `get_by_workspace` R2.
- **R2.** `maintenance_type` forms follow `get_by_type` R2; `machine_id` forms follow `get_by_machine` R7.
- **R3.** Order follows `get_by_workspace` R4 and, [BUG-1100], R4a. The docstring does not say "newest first"; the code does it.
- **R3a.** ✅ (Q1) The state of the machine and its factory is not looked at, as `get_by_machine` R4.
- **R4.** `skip`, `limit`, empty results and negative values follow `get_by_workspace` R5, R6, R7.
- **R5.** [BUG-1101] (HR-16) A log whose machine belongs to another workspace is not returned, as `get_by_machine` R8. *(Today: it is returned.)*

**Errors:** as `get_by_type`.

**Side effects:** none

---

## `MachineMaintenanceLogDAO.soft_delete(db, *, db_obj, deleted_by)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `MachineMaintenanceLogManager.delete_log` ← `DELETE /machine-maintenance-logs/{id}/`, which first answers 404 for a missing / other-workspace log and 400 "Maintenance log is already deleted" for a deleted one)

**Purpose:** Mark a log as deleted, keeping the row.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `db_obj` | `MachineMaintenanceLog` | the log to delete; not checked for workspace or current state |
| `deleted_by` | int | profile id stored in `deleted_by`; must reference an existing profile (foreign key). `None` is stored as `NULL` |

**Returns:** the same `db_obj` instance, flushed, not committed.

**Rules:**
- **R1.** Given a live log, after the call `is_deleted = True`, `is_active = False`, `deleted_by` = the given id, and `deleted_at` is set.
- **R1a.** [BUG-1102] (Q2) `deleted_at` = the current time from `utcnow()` (naive UTC), whatever the database's `TimeZone`. *(Today: the database's `now()`, as local time in the session's `TimeZone`: 13:08 under `America/New_York`, 23:08 under `Asia/Dhaka`, at 17:08 UTC.)*
- **R2.** No other column is changed by the method: `workspace_id`, `machine_id`, `maintenance_type`, `maintenance_date`, `summary`, `cost`, `performed_by`, `created_at`, `created_by`, `updated_by` keep their values (no `updated_by` stamp). `updated_at` becomes non-null because the ORM sets it on the UPDATE.
- **R3.** Given a log that is already soft-deleted, no error is raised and the stamp is overwritten: `deleted_by` becomes the new id, and `deleted_at` is written again as in R1a. (The manager refuses this case before calling.)
- **R4.** The change is flushed and not committed: in the same session the log is no longer returned by the four lists and is still returned by `get_by_id_and_workspace`; rolling back makes it live again with an empty stamp. The returned object is the very instance passed in. `restore` undoes the delete (`restore` R7).
- **R5.** No workspace check: the log passed in is deleted whatever workspace it belongs to (the caller is responsible for the lookup). Only that row changes: other logs of the machine stay as they were.
- **R6.** Given a `deleted_by` that is not an existing profile id, the flush fails (see Errors) and nothing is saved.
- **R7.** `deleted_by=None` is accepted: the log is deleted with `deleted_by` empty. The manager always passes the acting user.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `deleted_by` references no profile | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.ForeignKeyViolation`, pgcode `23503`, constraint `machine_maintenance_logs_deleted_by_fkey` | — (not asserted) |

**Side effects:** one `machine_maintenance_logs` row updated (`is_deleted`, `is_active`, `deleted_at`, `deleted_by`; `updated_at` by the ORM) and flushed; no commit; no row added to `machine_activity_events` (column `machine_id`; the manager writes `maintenance_removed`); the machine is not touched.

---

## `MachineMaintenanceLogDAO.restore(db, *, db_obj)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: nothing today; kept, P2)

**Purpose:** Bring a soft-deleted log back, the undo of `soft_delete`.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `db_obj` | `MachineMaintenanceLog` | the log to restore; not checked for workspace, current state, or the state of its machine |

There is no "who" argument: the method cannot record the acting user.

**Returns:** the same `db_obj` instance, flushed, not committed.

**Rules:**
- **R1.** ✅ Given a soft-deleted log, after the call `is_deleted = False`, `is_active = True`, `deleted_at = None`, `deleted_by = None`, in the database, not only on the object.
- **R2.** ✅ (P2, P3) No other column is changed by the method, and nobody is recorded: `updated_by` keeps the value it had, and no activity row is added. `updated_at` becomes non-null because the ORM sets it on the UPDATE.
- **R3.** ✅ Given a live log with `is_active = True` and no stamp, nothing changes and no UPDATE is issued: `updated_at` stays as it was (e.g. `None`). No error.
- **R4.** ✅ Given a live log with `is_active = False`, `is_active` becomes `True`.
- **R5.** ✅ The change is flushed and not committed: in the same session the log is returned again by the lists; rolling back makes it soft-deleted again with its previous stamp. The returned object is the very instance passed in.
- **R6.** ✅ No workspace check and no look at the machine: a log of a soft-deleted machine is restored like any other, and the machine is not changed. Other logs are not touched.
- **R7.** ✅ Restore is the undo of `soft_delete`: a live, active log deleted and restored has the same value in every column as before, except `updated_at`.

**Errors:** none. (It only clears `deleted_by` and sets two booleans.)

**Side effects:** at most one `machine_maintenance_logs` row updated (`is_deleted`, `is_active`, `deleted_at`, `deleted_by`; `updated_at` by the ORM) and flushed; no UPDATE when the log is already live and active; no commit; no row added to `machine_activity_events` (column `machine_id`).

---

## Inherited `BaseDAO` methods on `MachineMaintenanceLog`
**Shape:** create / update / delete / get / list
**Persistence:** writes / reads
**Visibility:** public (used by: `create` with a dict ← `MachineMaintenanceLogManager.create_log`; `update` with a dict ← `MachineMaintenanceLogManager.update_log`. `get`, `get_multi`, `remove`: no caller on this DAO)

**Purpose:** `MachineMaintenanceLogDAO` does not override these; the base spec (`tests/unit/dao/base.spec.md`) applies. Only what this model and its schemas change is stated.

**Rules:**
- **R1.** `create` with a dict holding `workspace_id`, `machine_id`, `maintenance_type`, `maintenance_date`, `summary` creates a row with `is_active = True`, `is_deleted = False`, `created_at` set by the database, and `cost`, `performed_by`, `created_by`, `updated_at`, `updated_by`, `deleted_at`, `deleted_by` empty. `updated_at` stays empty on creation. The row is flushed, not committed.
- **R2.** `create` with a `MachineMaintenanceLogCreate` always fails: the schema has no `workspace_id`, so the flush raises `IntegrityError` (`NotNullViolation` on `workspace_id`) and nothing is saved. A dict without it fails the same way, and `None` for `machine_id`, `maintenance_type`, `maintenance_date` or `summary` fails likewise on that column.
- **R3.** `create` with an unknown `machine_id`, `workspace_id` or `created_by` raises `IntegrityError` (`ForeignKeyViolation`, constraints `machine_maintenance_logs_machine_id_fkey`, `..._workspace_id_fkey`, `..._created_by_fkey`). A key that is not an attribute of the model raises `TypeError` and nothing is added. A `maintenance_type` string that is not a member's value raises `DataError` at the flush (pgcode `22P02`).
- **R4.** (HR-15) `cost` is stored rounded to 2 places, half away from zero, by the column: `0.125` → `0.13`, `0.135` → `0.14`, `2.675` → `2.68`, `-1.005` → `-1.01`, `0.124` → `0.12`; a float `1.005` also gives `1.01`. The object keeps the value as given until `db.refresh`: after a flush `obj.cost` is still `Decimal("0.125")`. Nothing is rounded in Python.
- **R5.** `cost` range: `9999999999999.99` and `9999999999999.994` (stored `.99`) are accepted; `9999999999999.995` and `10000000000000` raise `sqlalchemy.exc.DataError` (`NumericValueOutOfRange`, pgcode `22003`). `Decimal("NaN")` is not checked here and is stored as `NaN`; the schema refuses it first.
- **R6.** No value checks: a negative `cost` (`-3.50`), `cost` `0`, an empty `summary`, a `summary` with surrounding spaces (kept as given) or of 100 000 characters, and a `maintenance_date` of 1900 or 2099 are all stored.
- **R7.** `performed_by` of 255 characters is stored; 256 raises `sqlalchemy.exc.DataError` (`StringDataRightTruncation`, pgcode `22001`).
- **R8.** `create` does not look at the machine's state or workspace: a row is saved for a soft-deleted machine and for another workspace's machine. Refusing both is the manager's (it reads the machine by workspace first; HR-16 holds on that path, and the second kind of row is then hidden by BUG-1101).
- **R9.** `update` with a `MachineMaintenanceLogUpdate` applies only fields set to a value: `(summary="new", cost=None)` changes `summary` and keeps `cost`; `cost=0` is applied. `cost` and `performed_by` cannot be cleared through the schema (base spec `update` R2, R3).
- **R10.** `update` with a dict sets any attribute given and skips unknown keys: `{"cost": None, "performed_by": None}` clears them, `{"machine_id": <other>}` moves the log to another machine, `{"nonsense": 1}` is ignored. `{"summary": None}` raises `IntegrityError` (`NotNullViolation`) at the flush.
- **R11.** `updated_at` is set whenever an UPDATE is issued. An `update` that sets every field to its current value issues none: `updated_at` stays empty. `updated_by` holds only what the caller passes; the DAO does not stamp it.
- **R12.** `remove` hard-deletes the row: a query in the same session no longer finds it and the deleted instance is returned. No table references it, so nothing else is deleted. [BUG-101] Given an id with no row, `None` is returned and nothing is deleted (base spec `remove` R3). *(Today: `sqlalchemy.orm.exc.UnmappedInstanceError`; nothing calls `remove` on this DAO.)*
- **R13.** `get` returns a log of any workspace, soft-deleted or not, and `None` for an unknown id. `get_multi` is not scoped to a workspace and includes soft-deleted logs. [BUG-100] It is ordered by `id` ascending (base spec `get_multi` R2). *(Today: no ordering is requested; the fix in `app/dao/base.py` reaches this method.)*
- **R14.** A hard delete of a machine that still has a log, or of a profile named in `created_by`, `updated_by` or `deleted_by`, is refused by the database (`IntegrityError`, `ForeignKeyViolation`), soft-deleted logs included: a log's machine always exists. A hard delete of the workspace removes its logs (`ON DELETE CASCADE`). The exception is a BUG-1101 row: a log of workspace A on a machine of workspace B refuses the hard delete of B (`IntegrityError`, `ForeignKeyViolation`, constraint `machine_maintenance_logs_machine_id_fkey`), because the cascade removes B's machine and not A's log; A's own delete removes the log.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `create` without `workspace_id` (any `MachineMaintenanceLogCreate`); a required column `None` in `create` or `update` | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.NotNullViolation` (pgcode `23502`) | — (not asserted) |
| `create` with an unknown `machine_id`, `workspace_id`, `created_by` | `IntegrityError`; `.orig` is `psycopg2.errors.ForeignKeyViolation` (pgcode `23503`) | — |
| `maintenance_type` string not a member's value | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidTextRepresentation` (pgcode `22P02`) | — |
| `cost` beyond `Numeric(15, 2)` after rounding | `DataError`; `.orig` is `psycopg2.errors.NumericValueOutOfRange` (pgcode `22003`) | — |
| `performed_by` over 255 characters | `DataError`; `.orig` is `psycopg2.errors.StringDataRightTruncation` (pgcode `22001`) | — |
| `create` with an unknown key | `TypeError` | — |

**Side effects:** as in the base spec. No activity event: the manager writes those.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 23, 32, 41, 51, 62 | positional / keyword-only parameters; defaults `skip=0`, `limit=100` | Notes for the test designer; `get_by_workspace` R5 |
| 26–28 | `workspace_id` AND not `is_deleted`; no parent checked; no machine workspace compared (BUG-1101) | `get_by_workspace` R1, R2, R3, R6, R8 |
| 29 | `maintenance_date` descending, no tie-break (BUG-1100); offset / limit; `limit=0`; negative values; empty / many | `get_by_workspace` R4, R4a, R5, R6, R7, Errors |
| 35–37 | id AND `workspace_id`; `is_deleted` not read; no parent checked (BUG-1101) | `get_by_id_and_workspace` R1, R2, R3, R4, R5, R6 |
| 38 | `.first()` on the primary key: row / `None` | `get_by_id_and_workspace` R1, R2, R3 |
| 44–47 | `workspace_id` AND `machine_id` AND not `is_deleted`; no parent checked (BUG-1101) | `get_by_machine` R1, R2, R3, R4, R7, R8 |
| 48 | as line 29 | `get_by_machine` R5, R6, R7, R9 |
| 54–57 | `workspace_id` AND `maintenance_type` AND not `is_deleted`; enum forms (BUG-1101) | `get_by_type` R1, R2, R3a, R5, Errors |
| 58 | as line 29 | `get_by_type` R3, R4 |
| 65–69 | `workspace_id` AND `machine_id` AND `maintenance_type` AND not `is_deleted` (BUG-1101) | `get_by_machine_and_type` R1, R2, R3a, R5 |
| 70 | as line 29 | `get_by_machine_and_type` R3, R4 |
| 75–78 | writes `is_active`, `is_deleted`, `deleted_at` from `func.now()` (BUG-1102), `deleted_by`; no state check | `soft_delete` R1, R1a, R2, R3, R5, R7 |
| 79–81 | flush; foreign key on `deleted_by`; returns the instance | `soft_delete` R4, R6, Errors |
| 85–88 | writes `is_active`, `is_deleted`, clears the stamp; no state check | `restore` R1, R2, R3, R4, R6, R7 |
| 89–91 | flush; no UPDATE when nothing differs; returns the instance | `restore` R3, R5 |
| 95 | module singleton | Not specified |
| `models/machine_maintenance_log.py` 36, 38 | `server_default=now()`; `onupdate=now()` | inherited R1, R11; `soft_delete` R2; `restore` R2 |
| `models/machine_maintenance_log.py` 42, 43 | Python defaults of `is_active`, `is_deleted` | inherited R1 |
| `base.py` 76–84 | `create`: dict / schema (no `workspace_id`); NOT NULL, FK, enum, numeric, length errors | inherited R1, R2, R3, R4, R5, R6, R7, R8 |
| `base.py` 108–119 | `update`: dict / schema (`exclude_unset`, `exclude_none`); `hasattr` false skips the key | inherited R9, R10, R11 |
| `base.py` 136–139 | `remove`: found / not found (BUG-101) | inherited R12 |
| `base.py` 43, 59 | `get`, `get_multi`: no workspace filter, no order (BUG-100) | inherited R13 |

## Gap log
G1 (coordinator, 2026-10-31) — Fact — `soft_delete` and `restore` Side effects name `machine_activity_events` (column `machine_id`).
G2 (executor finding, 2026-10-31) — Fact — inherited R14 notes that a BUG-1101 row refuses the hard delete of its machine's workspace on `machine_maintenance_logs_machine_id_fkey`.
