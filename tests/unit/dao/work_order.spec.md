# Spec — `app/dao/work_order.py`

> **Status:** APPROVED (2026-11-10; no owner question — every finding is delegated: ordering, filters, search, clocks, numbering mechanics, soft delete)
> **Source commit:** e48a092

> **Fill-gaps round 2026-11-11.** The five gaps of `work_order.cases.md` are closed: four from the code, one decided by Claude under the reviewer's delegation (2026-11-11), the defaults of BUG-2675's new parameters. No new bug, no new question, nothing about money, stock or status transitions. Rules are not renumbered; `get_next_number` R3a is new. Gap log at the end.

> **Review round 2026-11-10 (describe + delegated review).** No owner answer in this round. Every item below is decided by Claude under the reviewer's delegation (2026-11-10) or by a house rule; none of them is the owner's own answer. Nothing here decides what an amount, a stock movement or a status transition should be: this DAO reads and lists work orders, numbers them and soft-deletes them. Which statuses count as an "open order for a machine, day and type" was already settled in the approved work order template manager spec (`tests/unit/managers/work_order_template_manager.spec.md`, Facts + `generate_drafts_for_anchored_range` R2, `generate_drafts` R7: every status except `VOIDED`); it is reused here, not re-asked.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated (`create`, `update` are inherited and used by `WorkOrderManager`; `AttachmentManager` uses `get_by_id_and_workspace`).
>
> **Standing decisions applied here (not asked again):** a missing or tie-prone `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id` (HR-6). Raw lookups stay raw (HR-4 scope). HR-8: search text is literal. HR-15: `cost` is `Numeric(15, 2)` and this DAO never computes money. HR-16: reads filter on the row's own `workspace_id`; refusing foreign links on writes is the manager's job (BUG-1016). Numbering follows the BUG-1333 / BUG-1440 / BUG-1334 precedents (text-sorted suffix, count-then-insert race, local clock).
>
> **Verified by running** (throwaway script `v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdao\work_order\`, one transaction rolled back against `marker_test`, private `COVERAGE_FILE`; nothing committed): `get_next_number` in an empty workspace (`WO-2026-001`), after `-998`/`-999` (`WO-2026-1000`), with `-999` and `-1000` both present (`WO-2026-1000` again; inserting it → `IntegrityError` 23505 on `uq_wo_workspace_number`), in a second workspace (`WO-2026-001`, accepted: the constraint is per workspace), with `-005` and `-abc` (`-abc` sorts highest → `WO-2026-001`), a soft-deleted `-005` still counted (`WO-2026-006`), last year's `WO-2025-050` ignored, a patched `datetime.now()` of 1 January 2031 (`WO-2031-001`); four orders flushed in one transaction share one `created_at` (the database's `now()` is the transaction start) and `get_by_workspace` emits `ORDER BY work_orders.created_at DESC` only; search `_` matched all 5 rows; search `Oil` found nothing although a row's title is "Oil change" (title is not searched); search `"   "` matched all; `status_scope="planned"` counted the draft planned for tomorrow, not today's; `status_scope="bogus"` counted everything; `soft_delete` under `SET LOCAL TIME ZONE 'Asia/Dhaka'` stored `deleted_at` 06:27 while UTC was 00:27; `get_by_machine_date_type` with two tied rows returned the lower id, and returned a `COMPLETED` row once the other was `VOIDED`; `count_by_calendar_date_for_sheet` keyed undated rows by the date of `created_at`; a machine-less order is in `get_by_workspace` but never in the sheet. **Read, not run:** `WorkOrderManager`, `WorkOrderTemplateManager` (both `get_by_machine_date_type` callers), `PurchaseOrderService` active-orders panel, `GET /work-orders/`, `/sheet/`, `/sheet/daily-counts/`, the web app's sheet params (`workOrderSheetApiParams.ts`, `workOrdersApi.ts`, `WorkOrdersToolbar.tsx`). **Not run:** anything over HTTP; two concurrent transactions.

## Review
> All decided; nothing pending.

### Quick list — all decided
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | After `WO-<year>-999` the next number is `-1000` forever, a 500 on every create | bug — numeric highest suffix + 1 (BUG-2676) | Claude, delegated (BUG-1333 precedent) |
| P2 | Two work orders created at once can get the same number | bug — race-free numbering (BUG-2677) | Claude, delegated (BUG-1440 precedent) |
| P3 | The number's year comes from the server's local clock | bug — UTC year (BUG-2678) | Claude, delegated (BUG-1334 precedent) |
| P4 | A work order's delete time comes from the database clock in its own time zone | bug — `utcnow()` (BUG-2679) | Claude, delegated (BUG-1102 precedent) |
| Q1 | "Planned" on the sheet means "after today" by the server's local date | bug — UTC date (BUG-2673) | Claude, delegated |
| Q2 | An unknown `status_scope` value is silently ignored | bug — 422 (BUG-2674) | Claude, delegated |
| Q3 | The sheet's calendar dots ignore "hide completed", "planned" and the search box | bug — dots use the list's filters (BUG-2675) | Claude, delegated |
| Q4 | `restore` has no caller | remove | Claude, delegated |
| Q5 | Sheet search covers number, description and assignee, not title | intended | Claude, delegated |
| Q6 | The plain list's date filter uses the planned date only; the sheet's uses the calendar day | intended | Claude, delegated |

Decided by house rules: list by creation time has no tie-breaker (BUG-2670); "existing order for machine, day, type" picks an arbitrary one of a tie (BUG-2671); `%` / `_` in the sheet search are wildcards (BUG-2672).
Already decided elsewhere and reused: "open order" = any status except `VOIDED` (work order template manager spec); `get_work_order` returning deleted orders is the manager's (BUG-1279); foreign machine / component links are the manager's (BUG-1016).

### House-rule violations — applied automatically

- **HR-6** `get_by_workspace` R11 — ordered by `created_at` descending only. `created_at` is the database's `now()`, the transaction's start time, so every order made in one request (a recurring program's drafts, a sheet entry) ties (verified: 4 rows, one timestamp). `GET /work-orders/` pages over it with `skip`/`limit`. Intended: `created_at` descending, then `id` descending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-2670 (pattern `tied-timestamp-no-tiebreak`, BUG-1210 precedent). Rules: `get_by_workspace` R11.

- **HR-6** `get_by_machine_date_type` R3 — `.first()` ordered by `created_at` descending only; tied rows (one recurring run) give an arbitrary one (verified: the lower id came back). Callers only test for existence today, but the method returns the row. Intended: `created_at` descending, then `id` descending (the newest).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-2671 (pattern `ambiguous-latest-row-tiebreak`). Rules: `get_by_machine_date_type` R3.

- **HR-8** `_apply_sheet_list_filters` R10 — the search text goes into `ILIKE '%…%'` unescaped: `_` matched every row (verified 5 of 5), `%` likewise. Intended: `%`, `_` (and `\`) match literally.
**Answer:** bug — per HR-8 (house rule)
**Resolution:** BUG-2672 (pattern `unescaped-like-wildcards`). Rules: `_apply_sheet_list_filters` R10.

Checked and **not** a new line here: **HR-4** — every list excludes soft-deleted rows; `get_by_id_and_workspace` is raw like BaseDAO's (scope rule), the manager's exposure is BUG-1279. **HR-5** — every filter is in SQL before `OFFSET`/`LIMIT` (the purchase order service's Python filter after `limit=1000` is FU-1). **HR-7** — the endpoints have `ge=1` on `limit`. **HR-9** — `soft_delete` / `restore` write no `updated_by`; `updated_at` is the model's `onupdate`. **HR-10** — `soft_delete` is a plain soft delete; the draft-only bulk deletes read then delete, and the worst race is two stamps (no lock needed); numbering is P2. **HR-15** — no money arithmetic. **HR-16** — reads filter on the row's own `workspace_id` (verified another workspace's rows never appear).

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-10)

### P1. After number 999 in a year, every new work order fails — 🐞 BUG-2676
**Background:** `get_next_number` takes the workspace's highest number of the year **as text** (`ORDER BY work_order_number DESC`) and adds one to its last part. Numbers are unique per workspace (`uq_wo_workspace_number`).
**What happens today:** `WO-2026-999` sorts above `WO-2026-1000`, so once both exist the next number is `-1000` again and every create fails with `IntegrityError` 23505, a 500, until New Year (verified). If the text-highest number has a suffix that is not a number (`WO-2026-abc`, only possible through a direct write), numbering restarts at `-001`, which already exists.
**Example:** A plant with daily recurring maintenance on five machines reaches 1000 work orders in October; from then on nobody can create a work order.
**Rules affected:** `get_next_number` R3, R4
**Answer:** bug — per BUG-1333 precedent: the next number is the numerically highest all-digit suffix of that workspace and year, plus one; a suffix that is not all digits is ignored
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): 🐞 BUG-2676 (pattern `text-sorted-sequence-number`). Rules: `get_next_number` R3, R4 (tagged).

### P2. Two work orders created at once can get the same number — 🐞 BUG-2677
**Background:** The number is computed by reading the highest one and the row is inserted later by the manager, with no lock or sequence.
**What happens today:** Two concurrent creates in one workspace both read `-041` and both try `-042`; the second fails at flush with `IntegrityError` 23505, a 500 (read; the duplicate insert itself was verified).
**Example:** Two supervisors save a sheet entry in the same second; one gets an error and loses the entry.
**Rules affected:** `get_next_number` R7
**Answer:** bug — per BUG-1440 / BUG-727 precedent: numbering is race-free (a locked per-workspace, per-year counter, or a retry on the unique violation)
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): 🐞 BUG-2677 (pattern `count-then-insert-race`). Integration-only (two transactions). Rules: `get_next_number` R7 (tagged).

### P3. The year in a work order number comes from the server's local clock — 🐞 BUG-2678
**Background:** `get_next_number` uses `datetime.now().year`, the local time of the machine running the API; the rest of the app stamps UTC.
**What happens today:** Around New Year a server whose local year differs from UTC numbers with the local year (verified `WO-2031-001` with a patched `datetime.now()`).
**Example:** A server on `Asia/Dhaka`: an order saved at 20:00 UTC on 31 December 2026 is `WO-2027-001`.
**Rules affected:** `get_next_number` R2
**Answer:** bug — per BUG-1334 precedent: the year comes from `utcnow()`
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): 🐞 BUG-2678 (pattern `local-clock-instead-of-utc`). Rules: `get_next_number` R2 (tagged).

### P4. A work order's delete time comes from the database clock — 🐞 BUG-2679
**Background:** `soft_delete` sets `deleted_at` to the database's `now()`. The column is a plain `timestamp`, so Postgres stores the local time of the session's `TimeZone` (the test database runs `America/New_York`).
**What happens today:** The stored time depends on the database's time-zone setting (verified: 06:27 under `Asia/Dhaka` while UTC was 00:27).
**Example:** The calendar and the attachment checks read `deleted_at` as UTC; a deletion at 00:27 UTC shows as 06:27.
**Rules affected:** `soft_delete` R1a
**Answer:** bug — per BUG-1102 precedent: `deleted_at = utcnow()`
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): 🐞 BUG-2679 (pattern `database-clock-timestamp`). Rules: `soft_delete` R1a (tagged).

### New questions — all decided (Claude under the reviewer's delegation, 2026-11-10)

### Q1. "Planned" on the sheet counts from the server's local date — 🐞 BUG-2673
**Background:** The sheet's "Planned" status option sends `status_scope=planned`: drafts with a planned date **after today**. "Today" is `date.today()`, the local date of the machine running the API.
**What happens today:** On a server whose local date differs from UTC, the cut-off moves by a day around midnight UTC.
**Example:** Server on `America/New_York`, 22:00 local on 10 November = 03:00 UTC on 11 November: a draft planned for 11 November is still "planned" (after the local 10th) although in UTC it is today.
**Rules affected:** `_apply_sheet_list_filters` R6
**Answer:** bug — "today" is `utcnow().date()` (BUG-2542 / BUG-1334 precedent)
**Resolution:** 🐞 BUG-2673 (pattern `local-clock-instead-of-utc`). Rules: `_apply_sheet_list_filters` R6 (tagged).

### Q2. An unknown `status_scope` is silently ignored — 🐞 BUG-2674
**Background:** `GET /work-orders/sheet/` takes `status_scope` as free text; only `planned` means anything.
**What happens today:** Any other value (`Planned`, `future`, `bogus`) is ignored and the full list comes back (verified 7 of 7), and the `status` filter then applies as if no scope was sent.
**Example:** A client sends `status_scope=Planned` and shows every order, done ones included, as "planned".
**Rules affected:** `_apply_sheet_list_filters` R7
**Answer:** bug — `status_scope` accepts only `planned` (endpoint `Literal["planned"]`), anything else → 422; the DAO behaviour for `None` / `planned` is unchanged
**Resolution:** 🐞 BUG-2674 (pattern `silently-ignored-input`), fix in `app/api/v1/endpoints/work_orders.py`. Rules: `_apply_sheet_list_filters` R7 (tagged; the case is written at the DAO to today's behaviour and the endpoint fix is noted).

### Q3. The sheet's calendar dots ignore three of the list's filters — 🐞 BUG-2675
**Background:** The sheet shows a page of orders and a week strip with a dot count per day (`/sheet/daily-counts/`). The dots take factory, machine, dates, status, type and priority, but not `status_scope`, `exclude_completed` or `search`; the web app does not send them either.
**What happens today:** With "hide completed" on (the default), a day whose orders are all completed still shows a dot with a count, and the list for that day is empty. With "Planned" or a search, every day still shows the unfiltered counts.
**Example:** Machine M had 3 completed orders on Monday. The list (completed hidden) shows nothing for Monday; the strip shows "3".
**Rules affected:** `count_by_calendar_date_for_sheet` R3
**Answer:** bug — the dots count exactly the set the list would show for the same filters: `count_by_calendar_date_for_sheet` takes `status_scope`, `exclude_completed` and `search` with the same meaning *(requires new parameters, passed through the manager, service, `GET /work-orders/sheet/daily-counts/` and the web app's `buildWorkOrderSheetDailyCountsParams`)*
**Resolution:** 🐞 BUG-2675 (pattern `inconsistent-sibling-filter`). Rules: `count_by_calendar_date_for_sheet` R3 (tagged).

### Q4. `restore` has no caller — 🗑️ removed
**Background:** `restore` clears the soft-delete fields of a work order.
**What happens today:** Nothing in `app/`, `tests/` or `scripts/` calls it; no endpoint restores a work order.
**Example:** Deleting it changes no API response.
**Rules affected:** none (moved to Not specified)
**Answer:** remove — no caller, dead code (sales order DAO Q1 precedent)
**Resolution:** under **Not specified**; line in `deadcode.md` for the dead-code checklist. No bug ID.

### Q5. Sheet search does not look at the title — ✅ intended
**Background:** Search matches `work_order_number`, `description` and `assigned_to`. The search box says "Search WO# or description…", and the sheet rows do not show the title.
**What happens today:** Searching "Oil" finds nothing when only the title says "Oil change" (verified).
**Example:** —
**Rules affected:** `_apply_sheet_list_filters` R10
**Answer:** intended — the search covers what the box promises and the rows show
**Resolution:** rule unchanged ✅.

### Q6. Two date-filter meanings — ✅ intended
**Background:** `GET /work-orders/` (`get_by_workspace`) filters on `planned_date` and drops undated orders when a date bound is given; the sheet filters on the calendar day (planned date, else the creation date).
**What happens today:** An undated order created on 5 November is on the sheet for 5 November but not in `GET /work-orders/?planned_date_from=2026-11-05`.
**Example:** —
**Rules affected:** `get_by_workspace` R8, R9; `_apply_sheet_list_filters` R3, R4
**Answer:** intended — the plain list's parameters are named after `planned_date` and filter on it; the sheet's calendar day is its own documented concept
**Resolution:** rules unchanged ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Purchase order service** (`app/services/purchase_order_service.py`, active-orders panel near line 1171, not yet specified) | HR-5: it loads the machine's newest 1000 live work orders (`get_by_workspace`, `limit=1000`) and only then keeps `DRAFT` / `IN_PROGRESS` and the project component in Python; an in-flight order beyond the newest 1000 is missed, and with `machine_id=None` it scans the whole workspace's newest 1000 for a component. It also shows `cost` as the row's `total_amount`. | reading the callers |
| FU-2 | **Work order manager / model** (`app/managers/work_order_manager.py`, `app/models/work_order.py`, not yet specified) | `created_at` defaults to the database's `now()` (plain `timestamp`, session time zone) and `updated_at` to `onupdate=func.now()` — the BUG-2333 pattern. The sheet's calendar day of an undated order is the date of that local `created_at`. One fix for the model, then the date of the calendar day follows. | verification |
| FU-3 | **Work order manager** | BUG-975 asks for a DAO method listing a machine's open work orders; when it is added it needs its own rules here (filter on status, `is_deleted`, `ORDER BY … id`). | bugs.md |

## Overview
`WorkOrderDAO` reads, lists, numbers and soft-deletes `work_orders`, the records of maintenance and other work done on machines or project components. Callers: `WorkOrderManager` (create → `get_next_number`; get / update / delete → `get_by_id_and_workspace`, `soft_delete`; `GET /work-orders/` → `get_by_workspace`; recurring-program repick and bulk delete → the two draft lists and `soft_delete`; the planning sheet → `list_for_sheet`, `count_for_sheet`, `count_by_calendar_date_for_sheet`), `WorkOrderTemplateManager` (`get_by_machine_date_type` before generating a draft), `PurchaseOrderService` (`get_by_workspace` for the active-orders panel), `AttachmentManager` (`get_by_id_and_workspace`). It flushes in `soft_delete` only, never commits, and takes no lock.

**Callables:** 12 specified (3 module-level helpers, 9 methods) · 2 not specified (+ inherited `BaseDAO` methods, base spec)
**Externals to mock:** `datetime.now` (in `get_next_number`, imported inside the function with `from datetime import datetime`, so there is no module-level name to patch: the target is the stdlib attribute **`datetime.datetime`**, patched with a subclass whose `now()` is fixed, as `v1.py` did; after the BUG-2678 fix the target becomes `app.dao.work_order.utcnow`); `date.today` in `app.dao.work_order` for `status_scope="planned"` (patch the module's `date` name with a subclass). After BUG-2673 / BUG-2678 also `utcnow` (see Notes).
**Integration-only behavior:** the race half of BUG-2677 (two concurrent transactions).

**Model facts (table `work_orders`, class `app.models.work_order.WorkOrder`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` CASCADE | — |
| `work_order_number` | String(50) NOT NULL, indexed; **unique per workspace** (`uq_wo_workspace_number` on `(workspace_id, work_order_number)`) | — |
| `work_order_type_id` | Integer NOT NULL, FK `work_order_types.id` RESTRICT | — |
| `title` | String(255) NOT NULL | — |
| `description` | Text nullable | `NULL` |
| `priority` | native enum `workorderpriorityenum` NOT NULL (`LOW`, `MEDIUM`, `HIGH`, `URGENT`) | Python `MEDIUM` |
| `status` | String(20) NOT NULL, indexed (plain text; values of `WorkOrderStatusEnum`: `DRAFT`, `IN_PROGRESS`, `COMPLETED`, `VOIDED`) | Python `'DRAFT'` |
| `factory_id` | Integer NOT NULL, FK `factories.id` | — |
| `machine_id`, `project_component_id` | Integer nullable FKs | `NULL` |
| `work_order_template_id` | Integer nullable, FK `work_order_templates.id` SET NULL | `NULL` |
| `planned_date`, `end_date` | Date nullable | `NULL` |
| `uses_inventory` | Boolean NOT NULL | `true` (Python and database) |
| `cost` | Numeric(15, 2) nullable | `NULL` |
| `account_id`, `invoice_id` | nullable FKs (RESTRICT / SET NULL) | `NULL` |
| `assigned_to`, `completed_by_names` | String(255) nullable | `NULL` |
| `required_approvals` | Integer nullable | `NULL` |
| `approved_by`, `started_by`, `completed_by`, `voided_by` | Integer nullable, FK `profiles.id` SET NULL | `NULL` |
| `approved_at`, `started_at`, `completed_at`, `voided_at` | DateTime (naive) nullable | `NULL` |
| `void_note`, `completion_notes` | Text nullable | `NULL` |
| `created_at` | DateTime (naive) NOT NULL | database `now()` (transaction start, session time zone; FU-2) |
| `created_by`, `updated_by` | nullable FK `profiles.id` | `NULL` |
| `updated_at` | DateTime nullable, `onupdate=func.now()` | `NULL` |
| `is_active` / `is_deleted` | Boolean NOT NULL | `true` / `false` (Python) |
| `deleted_at`, `deleted_by` | nullable | `NULL` |

**The calendar day** of a work order is `coalesce(planned_date, created_at::date)`: its planned date, or the date of `created_at` when undated.

**Imports and names (G1):** `WorkOrderStatusEnum` and `WorkOrderPriorityEnum` live in `app.models.enums` (the DAO and the model both import them from there; `app.models.work_order` re-exposes them only as an import side effect, so use `app.models.enums`). The singleton is `work_order_dao` in `app.dao.work_order` (class `WorkOrderDAO`). Relationships on `WorkOrder`: `work_order_type`, `work_order_template`, `factory`, `machine`, `project_component`, `account`, `invoice`, `approver`, `starter`, `completer`, `voider`, `creator`, `updater`, `deleter`, `items` (dynamic), `approvers`, `assignee_links`, `completer_links`.

**What real state changes write (G3)** (`WorkOrderManager`, for realistic Givens; the DAO reads only `status`, `is_deleted`, `deleted_*`): start → `status = 'IN_PROGRESS'`, `started_at` (and `started_by`); complete → `status = 'COMPLETED'`, `completed_by_names`, `completed_by` (first completer id or `NULL`), `completed_at` (given time or `utcnow()`), optionally `completion_notes`; void (only from `DRAFT` / `IN_PROGRESS`) → `status = 'VOIDED'`, `void_note`, `voided_at = utcnow()`, `voided_by`; approvals met → `approved_by`, `approved_at`. A real soft delete is `soft_delete` R1 (`is_active = False`, `is_deleted = True`, `deleted_at`, `deleted_by`); `status` stays as it was.

**Notes for the test designer:**
- `from app.dao.work_order import work_order_dao`. Parents: `make_workspace`, `make_profile` (`tests/unit/factories.py`), `Factory(workspace_id, name, abbreviation)`, `Machine(workspace_id, name, factory_id)`, `WorkOrderType(workspace_id, name)`. Insert `WorkOrder(workspace_id, work_order_number, work_order_type_id, title, factory_id, …)` directly; `status` as a plain string.
- Rows flushed in one test transaction all get the same `created_at`. To order by creation time, set `created_at` explicitly.
- Search, filters and counts: build rows in a second workspace and soft-deleted rows for every list.
- **BUG-2678:** patch `datetime.datetime` (subclass, `now()` → 1 January 2027 05:00) and `app.utils.time.utcnow` plus `app.dao.work_order.utcnow` (`create=True`; the module does not import it today) → 31 December 2026 23:00. Intended `WO-2026-…`; today `WO-2027-…` → strict xfail.
- **BUG-2673:** patch `app.dao.work_order.date` (subclass with `today()` → 10 November) and `utcnow` (`create=True`) → 11 November 03:00; a draft planned for 11 November: intended not "planned", today it is → strict xfail.
- **BUG-2679:** `SET LOCAL TIME ZONE 'Asia/Dhaka'` before `soft_delete`, patch `utcnow` (`create=True`) to a fixed time; intended `deleted_at` equals it → strict xfail.
- **BUG-2671:** two rows with one explicit `created_at`; intended the higher `id`. Result rests on physical order today: non-strict xfail, or a strict check that the SQL ends in `work_orders.id DESC`. Same for **BUG-2670** (`created_at DESC, work_orders.id DESC`).

## Not specified
- `WorkOrderDAO.restore` — dead code, to be removed (decided by Claude under the reviewer's delegation (2026-11-10); Q4).
- `work_order_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods (`create`, `update`, …) — covered by the base spec.

---

## `_work_order_calendar_date_expr()`
**Shape:** helper
**Persistence:** pure (SQL expression)
**Visibility:** internal (used by: `_sheet_base_query`, `count_by_calendar_date_for_sheet`, `list_for_sheet` ordering)

**Purpose:** The SQL for a work order's calendar day.

**Rules:**
- **R1.** A row with a `planned_date` has that date as its calendar day.
- **R2.** A row without one has the date part of its `created_at` (as stored, FU-2).

**Errors:** none. **Side effects:** none

---

## `_apply_sheet_list_filters(query, *, calendar_date, factory_id, machine_id, planned_date_from, planned_date_to, status, status_scope, work_order_type_id, priority, exclude_completed, search)`
**Shape:** helper (filters)
**Persistence:** pure (adds `WHERE` clauses)
**Visibility:** internal (used by: `_sheet_base_query`, `count_by_calendar_date_for_sheet`)

**Purpose:** The planning sheet's filters, shared by its list, count and dots. All filters combine with AND; each is skipped when its argument is falsy (`None`, `0`, `""`, `False`).

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| calendar_date | SQL expression | the calendar-day expression |
| factory_id, machine_id, work_order_type_id | int \| None | equality filters |
| planned_date_from / planned_date_to | date \| None | inclusive bounds on the calendar day |
| status | `WorkOrderStatusEnum` \| None | equality on `status` |
| status_scope | str \| None | only `"planned"` has a meaning |
| priority | `WorkOrderPriorityEnum` \| None | equality on `priority` |
| exclude_completed | bool | drop `COMPLETED` |
| search | str \| None | free text, trimmed |

**Returns:** the query with filters added.

**Rules:**
- **R1.** `factory_id` keeps rows of that factory only; `machine_id` rows of that machine only.
- **R2.** `work_order_type_id` keeps rows of that type; `priority` rows of that priority.
- **R3.** `planned_date_from` keeps rows whose calendar day is on or after it (inclusive), so an undated order created on that day is kept.
- **R4.** `planned_date_to` keeps rows whose calendar day is on or before it (inclusive). Both together give an inclusive range; `from` after `to` gives nothing.
- **R5.** `status` keeps rows with exactly that status, when `status_scope` is not `"planned"`.
- **R6.** `status_scope="planned"` keeps only `DRAFT` rows with a `planned_date` strictly after today; undated drafts and drafts planned for today or earlier are left out. It **replaces** the `status` filter (a `status` sent with it is ignored). [BUG-2673] "Today" is the UTC date (`utcnow().date()`). *(Today: the server's local date, `date.today()`.)*
- **R7.** Any other `status_scope` value is ignored (the `status` filter applies as without a scope). [BUG-2674] At the endpoint, a value other than `planned` is refused with 422 and the DAO is not reached. *(Today: accepted and ignored; fix in `app/api/v1/endpoints/work_orders.py`, `status_scope: Literal["planned"] | None`.)*
- **R8.** `exclude_completed=True` drops `COMPLETED` rows; `DRAFT`, `IN_PROGRESS` and `VOIDED` stay. With `status=COMPLETED` as well, nothing is left.
- **R9.** `search` keeps rows where the trimmed text occurs, case-insensitively, in `work_order_number`, `description` or `assigned_to` (any one). `title` is not searched (Q5 ✅). A row whose `description` / `assigned_to` is NULL can still match on its number. Whitespace-only search (`"   "`) becomes an empty pattern and keeps every row (same as no search).
- **R10.** [BUG-2672] (HR-8) `%`, `_` and `\` in the search text match themselves literally. *(Today: unescaped; `_` matched every row.)*

**Errors:** none of its own. **Side effects:** none

---

## `_sheet_base_query(db, *, workspace_id, …same filters…)`
**Shape:** helper (query)
**Persistence:** reads (builds a query)
**Visibility:** internal (used by: `list_for_sheet`, `count_for_sheet`)

**Purpose:** The rows the planning sheet can show, before paging.

**Rules:**
- **R1.** Only rows of `workspace_id`; another workspace's rows never appear.
- **R2.** Soft-deleted rows (`is_deleted = True`) never appear.
- **R3.** Rows with no machine (`machine_id` NULL — project-component work) never appear on the sheet.
- **R4.** Every filter of `_apply_sheet_list_filters` applies as given (its R1–R10).
- **R5.** Returns the query and the calendar-day expression (used by `list_for_sheet` for ordering).

**Errors:** none. **Side effects:** none

---

## `WorkOrderDAO.get_by_workspace(db, *, workspace_id, work_order_type_id=None, status=None, priority=None, factory_id=None, machine_id=None, work_order_template_id=None, planned_date_from=None, planned_date_to=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderManager.list_work_orders` ← `GET /work-orders/`, `limit` 1…1000 default 100; `PurchaseOrderService` active-orders panel with `limit=1000`)

**Purpose:** The workspace's work orders, newest first, with optional filters. Overrides `BaseDAO.get_by_workspace`.

**Returns:** a list of `WorkOrder`, at most `limit`.

**Rules:**
- **R1.** Only rows of `workspace_id`; soft-deleted rows are left out. Machine-less orders are included (unlike the sheet).
- **R2.** `work_order_type_id` keeps that type only (falsy → no filter).
- **R3.** `status` keeps that status only (`None` → every status, `VOIDED` included).
- **R4.** `priority` keeps that priority only.
- **R5.** `factory_id` / `machine_id` keep that factory / machine only (falsy → no filter).
- **R6.** `work_order_template_id` keeps orders generated from that template; it applies whenever it is not `None` (`0` filters and matches nothing).
- **R7.** Every filter combines with AND and is applied before paging.
- **R8.** `planned_date_from` keeps rows with a `planned_date` on or after it; undated rows are dropped (Q6 ✅).
- **R9.** `planned_date_to` keeps rows with a `planned_date` on or before it; undated rows are dropped (Q6 ✅).
- **R10.** `skip` / `limit` page the ordered result (default first 100).
- **R11.** [BUG-2670] (HR-6) Ordered by `created_at` descending, then `id` descending. *(Today: `created_at` descending only; ties come back in no fixed order.)*

**Errors:** none of its own. **Side effects:** none

---

## `WorkOrderDAO.list_future_drafts_for_template_machine(db, *, workspace_id, work_order_template_id, machine_id, after_date)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderManager.bulk_delete_future_recurrence_drafts`, which soft-deletes every row returned)

**Purpose:** A recurring program's future drafts on one machine.

**Rules:**
- **R1.** Returns the workspace's live (`is_deleted = False`) `DRAFT` rows of that template and that machine with a `planned_date` strictly after `after_date`.
- **R2.** Left out: other statuses (`IN_PROGRESS`, `COMPLETED`, `VOIDED`), undated rows, rows on `after_date` itself or before, other templates, other machines, other workspaces, soft-deleted rows.
- **R3.** Ordered by `planned_date` ascending, then `id` ascending; no limit (all rows).

**Errors:** none. **Side effects:** none

---

## `WorkOrderDAO.list_drafts_outside_range_for_template_machine(db, *, workspace_id, work_order_template_id, machine_id, range_start, range_end)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderManager.sync_recurrence_drafts_for_machine`, which soft-deletes every row returned)

**Purpose:** A recurring program's drafts on one machine that fall outside its new date range.

**Rules:**
- **R1.** Returns the workspace's live `DRAFT` rows of that template and machine whose `planned_date` is before `range_start` or after `range_end`.
- **R2.** Rows on `range_start` or `range_end` (inclusive range) are kept out of the result; so are undated rows, other statuses, templates, machines, workspaces and soft-deleted rows.
- **R3.** `range_start` after `range_end`: every dated draft of the template and machine is returned (each date is either before the start or after the end).
- **R4.** Ordered by `planned_date` ascending, then `id` ascending; no limit.

**Errors:** none. **Side effects:** none

---

## `WorkOrderDAO.get_by_machine_date_type(db, *, workspace_id, machine_id, planned_date, work_order_type_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderTemplateManager` draft generators, existence check only)

**Purpose:** An existing order for the same machine, day and work type, so recurring generation does not duplicate it.

**Rules:**
- **R1.** Returns a live row of the workspace with that machine, exactly that `planned_date` and that type, whatever its source (template or manual) and status **other than `VOIDED`** — `DRAFT`, `IN_PROGRESS` and `COMPLETED` all count (work order template manager spec).
- **R2.** `None` when the only matches are `VOIDED`, soft-deleted, of another workspace, another machine, date or type, or undated.
- **R3.** [BUG-2671] (HR-6) Of several matches, the newest: `created_at` descending, then `id` descending. *(Today: `created_at` only; a tie returns an arbitrary one.)*

**Errors:** none. **Side effects:** none

---

## `WorkOrderDAO.list_for_sheet(db, *, workspace_id, …filters…, skip=0, limit=50)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderManager.list_sheet_orders` ← `GET /work-orders/sheet/`, `limit` 1…100 default 50)

**Purpose:** One page of the planning sheet.

**Rules:**
- **R1.** The rows are those of `_sheet_base_query` (R1–R5) with the given filters.
- **R2.** Ordered by calendar day descending, then `created_at` descending, then `id` descending.
- **R3.** `skip` / `limit` page that order (default first 50), after all filtering.
- **R4.** Filter defaults (G2): every filter keyword defaults to "no filter": `factory_id`, `machine_id`, `planned_date_from`, `planned_date_to`, `status`, `status_scope`, `work_order_type_id`, `priority`, `search` default to `None`, and `exclude_completed` defaults to `False`, so completed orders are listed unless it is sent `True`. `skip=0`, `limit=50`.

**Errors:** none. **Side effects:** none

---

## `WorkOrderDAO.count_for_sheet(db, *, workspace_id, …filters…)`
**Shape:** compute (count)
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderManager.count_sheet_orders` ← the sheet's `total`)

**Rules:**
- **R1.** Returns the number of rows `list_for_sheet` would return over all pages for the same filters (same set, no paging).
- **R2.** `0` when nothing matches (an int, never `None`).
- **R3.** Same filter keywords and defaults as `list_for_sheet` R4 (no `skip` / `limit`): with no filter sent, completed orders are counted.

**Errors:** none. **Side effects:** none

---

## `WorkOrderDAO.count_by_calendar_date_for_sheet(db, *, workspace_id, factory_id=None, machine_id=None, planned_date_from=None, planned_date_to=None, status=None, work_order_type_id=None, priority=None)`
**Shape:** compute (grouped count)
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderManager.sheet_daily_counts` ← `GET /work-orders/sheet/daily-counts/`, the week strip's dots)

**Purpose:** How many sheet orders fall on each calendar day.

**Returns:** a dict `{date: count}`; days with no orders are absent; `{}` when nothing matches.

**Rules:**
- **R1.** Counts the rows of the workspace that are live and have a machine (as `_sheet_base_query` R1–R3), grouped by calendar day; an undated order counts on its creation date.
- **R2.** Factory, machine, date bounds (on the calendar day, inclusive), `status`, type and priority filter as in `_apply_sheet_list_filters` R1–R5; no row limit, and no date bound means every day.
- **R3.** [BUG-2675] It also takes `status_scope`, `exclude_completed` and `search` with the meaning of `_apply_sheet_list_filters` R6–R10, so the counts add up to what `count_for_sheet` gives for the same filters. Their defaults are those of `list_for_sheet` R4: `status_scope=None`, `exclude_completed=False`, `search=None`, so a call that sends none of them counts exactly as today, completed orders included (decided by Claude under the reviewer's delegation (2026-11-11): same defaults as the sibling list and count, so existing callers keep their result and the dots match the list whenever the same filters are sent). *(Today: no such parameters; completed orders, non-planned orders and non-matching orders are always counted. Requires new parameters through manager, service, endpoint and web app.)*

**Errors:** none. **Side effects:** none

---

## `WorkOrderDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderManager` get / update / delete / items / approvals, `AttachmentManager`)

**Rules:**
- **R1.** Returns the row with that `id` in that workspace, **including a soft-deleted one** (raw lookup, HR-4 scope; the managers' `is_deleted` checks rely on it).
- **R2.** `None` for an unknown id or a row of another workspace.

**Errors:** none. **Side effects:** none

---

## `WorkOrderDAO.get_next_number(db, *, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderManager.create_work_order`, which inserts the row afterwards)

**Purpose:** The next work order number of the workspace for the current year, `WO-<year>-<n>`.

**Returns:** a string.

**Rules:**
- **R1.** No number of the workspace for the year yet → `WO-<year>-001`.
- **R2.** [BUG-2678] `<year>` is the current UTC year (`utcnow()`). *(Today: `datetime.now().year`, the server's local year.)*
- **R3.** [BUG-2676] Otherwise the result is the numerically highest all-digit suffix among the workspace's numbers starting `WO-<year>-`, plus one, padded to at least 3 digits (`-041` → `-042`, `-999` → `-1000`, `-999` and `-1000` present → `-1001`). *(Today: the text-highest number is taken, so with `-999` and `-1000` present the result is `-1000` again and the insert fails with 23505.)*
- **R3a.** The suffix is the text after the **last** dash (G5). Today, when the text-highest number of the year is `WO-2031-1-2` (suffix `1-2`, which sorts above `005`), the part after the last dash, `2`, is read as the last number and the result is `WO-2031-003`. Intended (R4, BUG-2676): `1-2` is not all digits, so the number is ignored and, with `WO-2031-005` present, the result is `WO-2031-006`. *(Today `WO-2031-003`; tested as part of BUG-2676, strict xfail.)*
- **R4.** [BUG-2676] Numbers whose suffix is not all digits (`WO-2026-abc`) are ignored; they never reset numbering. *(Today: when such a number is the text-highest, the result is `-001`.)*
- **R5.** Soft-deleted rows count (a deleted `-005` makes the next `-006`), so numbers are not reused. Other workspaces' numbers and other years' numbers do not count; the prefix match is case-sensitive (numbers are system-made).
- **R6.** Only numbers of the workspace count; another workspace may hold the same number (unique per workspace, verified).
- **R7.** [BUG-2677] Two concurrent creates in one workspace never get the same number *(integration-only; today they can, and the second insert fails with 23505)*.

**Errors:** none of its own. **Side effects:** none (reads only)

---

## `WorkOrderDAO.soft_delete(db, *, db_obj, deleted_by)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `WorkOrderManager.delete_work_order`, `bulk_delete_future_recurrence_drafts`, `sync_recurrence_drafts_for_machine`)

**Returns:** the same object, flushed, not committed.

**Rules:**
- **R1.** Sets `is_active = False`, `is_deleted = True`, `deleted_by = deleted_by` and a non-null `deleted_at`; flushes.
- **R1a.** [BUG-2679] `deleted_at` is the current UTC time (`utcnow()`). *(Today: the database's `now()`, stored in the session's time zone.)*
- **R2.** `status`, lines, approvers and every other field are unchanged; `updated_by` is not written.
- **R3.** No state check: an already deleted row is stamped again (the managers check first).

**Errors:** none of its own. **Side effects:** the row's four delete fields; flush.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 18 | `coalesce(planned_date, created_at::date)` | `_work_order_calendar_date_expr` R1, R2 |
| 36–39 | `factory_id` / `machine_id` truthy | `_apply_sheet_list_filters` R1 |
| 40–43 | date bounds truthy, on calendar day | `_apply_sheet_list_filters` R3, R4 |
| 44–50 | `status_scope == "planned"`, `date.today()` | `_apply_sheet_list_filters` R6 |
| 51–52 | `elif status` | `_apply_sheet_list_filters` R5, R7 |
| 53–56 | type / priority truthy | `_apply_sheet_list_filters` R2 |
| 57–58 | `exclude_completed` | `_apply_sheet_list_filters` R8 |
| 59–67 | `search` truthy, strip, ILIKE on 3 columns | `_apply_sheet_list_filters` R9, R10 |
| 87–91 | workspace, not deleted, has machine | `_sheet_base_query` R1–R3 |
| 92–106 | filters applied, return pair | `_sheet_base_query` R4, R5 |
| 125–128 | workspace, not deleted | `get_by_workspace` R1 |
| 129–138 | type / status / priority / factory / machine truthy | `get_by_workspace` R2–R5, R7 |
| 139–140 | `work_order_template_id is not None` | `get_by_workspace` R6 |
| 141–146 | date bounds truthy, `planned_date` not null | `get_by_workspace` R8, R9 |
| 147 | `ORDER BY created_at DESC`, offset, limit | `get_by_workspace` R10, R11 |
| 159–171 | draft, template, machine, dated, `> after_date`, ordered | `list_future_drafts_for_template_machine` R1–R3 |
| 185–200 | draft, template, machine, dated, outside range, ordered | `list_drafts_outside_range_for_template_machine` R1–R4 |
| 213–224 | match, not `VOIDED`, `created_at DESC`, `.first()` | `get_by_machine_date_type` R1–R3 |
| 245–264 | base query, 3-key order, offset, limit | `list_for_sheet` R1–R3 |
| 282–296 | base query, `count()` | `count_for_sheet` R1, R2 |
| 312–320 | workspace, not deleted, has machine | `count_by_calendar_date_for_sheet` R1 |
| 321–331 | subset of filters (no scope / completed / search) | `count_by_calendar_date_for_sheet` R2, R3 |
| 332–333 | group by day → dict | `count_by_calendar_date_for_sheet` R1 |
| 339–342 | id + workspace, no delete filter | `get_by_id_and_workspace` R1, R2 |
| 347 | `datetime.now().year` | `get_next_number` R2 |
| 349–352 | workspace, `LIKE 'WO-<year>-%'`, text-max | `get_next_number` R3, R5, R6 |
| 353 | `if last` | `get_next_number` R1 |
| 354–358 | `int(suffix)` (text after the last dash) else fall through | `get_next_number` R3, R3a, R4 |
| 356 | `:03d` | `get_next_number` R3 |
| 359 | `-001` | `get_next_number` R1, R4 |
| 344–359 | read then caller inserts | `get_next_number` R7 |
| 364–370 | four fields, `func.now()`, flush | `soft_delete` R1, R1a, R2, R3 |

## Gap log
- G1 (work_order.cases.md gap 1) — Fact — enum import path `app.models.enums`, singleton `work_order_dao`, relationship names: Overview "Imports and names".
- G2 (work_order.cases.md gap 2) — Fact — filter keyword defaults (`exclude_completed=False`, all others `None`, `skip=0`, `limit=50`): `list_for_sheet` R4, `count_for_sheet` R3.
- G3 (work_order.cases.md gap 3) — Fact — approval, lifecycle and void stamp columns added to the model table; what a real start, complete, void and soft delete write: Overview "What real state changes write".
- G4 (work_order.cases.md gap 4) — Intent, decided by Claude under the reviewer's delegation (2026-11-11) — BUG-2675's new parameters default to `None` / `False` / `None` like the sibling list and count, so a call without them counts as today: `count_by_calendar_date_for_sheet` R3.
- G5 (work_order.cases.md gap 5) — Fact — the suffix is the text after the last dash (`WO-2031-1-2` → `2` → `-003` today; ignored once BUG-2676 is fixed): `get_next_number` R3a. Also named the year patch target (`datetime.datetime`) in Externals.

