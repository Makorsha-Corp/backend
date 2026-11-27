# Spec — `app/services/calendar_service.py`

> **Status:** APPROVED (2026-11-04; P1, P2, Q1 decided by Claude under the reviewer's delegation (2026-11-04); house-rule lines applied. OQ-5 (private projects), OQ-14 (voided work orders) and OQ-15 (orders of a deleted factory) answered by the owner (2026-11-04) → BUG-1869, BUG-1876, BUG-1877, BUG-1878. Nothing parked.)
> **Revision 2026-11-04 (apply-review, OQ-14, OQ-15):** the owner answered OQ-14 with the suggested answer (a voided work order is hidden; drafts, in-progress and completed stay) and OQ-15 with alternative (a) (work and sales orders of a deleted factory are hidden now, like projects and batches). `_collect_work_orders` R3, R4 and `_collect_sales_orders` R3 rewritten to the intended behavior and tagged; no other rule changed. Cards to revise: CAL-OQ14-01, CAL-OQ14-02, CAL-OQ15-01, CAL-OQ15-02.
> **Revision 2026-11-04 (apply-review, OQ-5):** the owner answered OQ-5 with the suggested answer: a calendar entry follows its record's visibility, so a private project appears only to those who may open it. `_collect_projects` R6 rewritten to the intended behavior and tagged BUG-1869; `get_events` gains a required keyword-only `user_id` (new Inputs row, R7); the endpoint passes `current_user.id`, as the project pages do. No other rule changed. Card to revise: CAL-OQ5-01 (plus cards for each allowed-caller kind).
> **Source commit:** e48a092
> **Revision 2026-11-04 (fill-gaps, `calendar_service.cases.md` gaps 1–5):** R6 private value corrected to `"invited_only"`; amount, priority and status `None` branches recorded as unreachable (NOT NULL, verified in `marker_test`); project status values named; minimum rows for every source table added; what each close writes recorded. All Fact gaps, read from the source and models and verified by running (`g_cal_rows.py`, `g_cal_nullable.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc4d\`, rolled back). No new question, no new bug; stays APPROVED. See `## Gap log`.

> **Reachable — not dead code.** `calendar_service.get_events` is called by `GET /calendar/events` (`app/api/v1/endpoints/calendar.py`, router prefix `/calendar` in `app/api/v1/router.py`), and the frontend's calendar page calls that endpoint (`frontend/src/features/calendar/calendarApi.ts`). So it is described in full, unlike `project_component_attachment`.
>
> **Form.** As `tests/unit/services/department_service.spec.md`. A read-only aggregator: no manager, no DAO, its own `db.query` per source table. It inherits `BaseService` but never commits or rolls back (TC6 of `base_service.spec.md`). Table facts are cited from the approved DAO specs where they exist (`tests/unit/dao/production_batch.spec.md`, `project.spec.md`); the other tables are read from the models.
>
> **Routed here and written as rules:** production batch DAO **FU-3** (batches of a soft-deleted factory; BUG-1330's owner rule) → P2 / BUG-1807. **OQ-5** applies to private projects: answered by the owner (2026-11-04) → BUG-1869.
>
> **Verified by running** (`v1_cal.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc4d\`, one outer transaction rolled back against `marker_test`, session as the unit-test `db` fixture; nothing persisted): a soft-deleted project and a private project are listed; a project deadline at 23:30 on the last day is listed; a project subtitle cut to 120 characters, an empty description gives `None`; a `VOIDED` work order gives two events with `meta.status = "VOIDED"`; a payment of workspace 1 joined to workspace 2's invoice shows that invoice's id and account id; an invoice with `invoice_number = ""` is titled `Invoice #<id>`; `types=[maintenance]` gives `[]`; `types=[]` gives every category; `start > end` raises `ValueError("start must be on or before end")`; the sort order across invoices, projects and work orders on one day, and a record's two dates in field order. **Read, not run:** the purchase, expense, sales order, delivery and batch collectors; the intended behavior of BUG-1800, BUG-1801, BUG-1805 … BUG-1807.

## Review
> All answered or parked; nothing blocking. OQ-5 applied 2026-11-04.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| HR-4 | Deleted projects still appear on the calendar | bug (BUG-1800) | house rule |
| HR-16 | A payment linked to another workspace's invoice shows that invoice's id and customer id | bug (BUG-1801) | house rule |
| P1 | Projects of a deleted factory still appear | bug (BUG-1806) | Claude, delegated (precedent BUG-1446) |
| P2 | Production batches of a deleted factory still appear | bug (BUG-1807) | Claude, delegated (precedent BUG-1330, owner rule) |
| Q1 | The "Maintenance" filter the calendar offers never shows anything | bug (BUG-1805) | Claude, delegated |
| OQ-5 | Any member sees private projects' names, dates and description on the calendar | bug (BUG-1869) | owner (2026-11-04) |
| OQ-14 | Voided work orders appear, while voided purchase and expense orders do not | bug (BUG-1876) | owner (2026-11-04) |
| OQ-15 | Work and sales orders of a deleted factory appear | bug (BUG-1877, BUG-1878) | owner (2026-11-04), alternative (a) |

### House-rule violations — applied automatically

- **HR-4** `_collect_projects` R2 — soft-deleted projects are listed (verified). Intended: a project with `is_deleted = True` gives no event.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-1800 (pattern `list-returns-soft-deleted`). Rules: `_collect_projects` R2.
- **HR-16** `_collect_invoice_payments` R3 — the payment is joined to its invoice by id only, so a payment of this workspace whose `invoice_id` points at another workspace's invoice (invalid data) is listed with that invoice's id in `subtitle`, `meta.invoice_id` and `link`, and its account id in `meta.account_id` and `link` (verified). Intended: such a payment is treated as not found — no event.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-1801 (pattern `cross-workspace-row-exposed`, as BUG-1086). Rules: `_collect_invoice_payments` R3.

Checked and **not** violated: **HR-4** for work orders (deleted ones excluded); the other tables have no soft-delete column. **HR-5, HR-6, HR-7** — nothing is paged or cut to a top N: the whole range is returned, sorted (`get_events` R4). **HR-8** — no `LIKE`. **HR-9, HR-10** — read only. **HR-15** — amounts are passed through as text of the stored `Numeric(15,2)` value; nothing is computed or rounded. **HR-16** elsewhere — every query filters by the caller's workspace; ids echoed from the row itself (`account_id`, `current_status_id`, `sales_order_id`) are only as valid as the writes that stored them, and those refusals belong to the order managers (BUG-1016 family), not here.

**Permission checks:** none beyond an active membership of the workspace (endpoint dependency). Every member sees every category, including invoices, payments and amounts. Private projects: **OQ-5**, answered by the owner (2026-11-04): shown only to those who may open them (BUG-1869, `_collect_projects` R6).

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-11-04))

### P1. Projects of a deleted factory still appear — 🐞 BUG-1806
**Background:** Every project belongs to a factory. BUG-1446 ruled that project lists hide projects whose factory is soft-deleted (the rows are untouched and come back with the factory).
**What happens today:** the calendar never looks at the factory: a project of a deleted factory shows its start, end and deadline.
**Example:** the "Dhaka plant" factory is deleted; its project "Line 3 refit" no longer shows on the projects page but still shows its deadline on the calendar.
**Rules affected:** `_collect_projects` R3
**Answer:** bug — per BUG-1446 precedent: a project whose factory has `is_deleted = True` gives no event; an inactive-but-live factory hides nothing
**Resolution:** 🐞 BUG-1806 (pattern `join-ignores-soft-deleted`) — decided by Claude under the reviewer's delegation (2026-11-04). Rules: `_collect_projects` R3.

### P2. Production batches of a deleted factory still appear — 🐞 BUG-1807
**Background:** A batch belongs to a production line, and the line to a factory. The owner ruled (BUG-1330, 2026-11-02) that batches whose line's factory is soft-deleted are not listed or counted; the production batch DAO review routed the calendar here (FU-3).
**What happens today:** the calendar lists them.
**Example:** a deleted factory's batch `BATCH-2026-014` dated 10 May shows on the calendar, but not on the production page.
**Rules affected:** `_collect_production_batches` R2
**Answer:** bug — per BUG-1330 precedent: a batch whose line's factory has `is_deleted = True` gives no event; an inactive line or factory hides nothing
**Resolution:** 🐞 BUG-1807 (pattern `join-ignores-soft-deleted`) — decided by Claude under the reviewer's delegation (2026-11-04). Rules: `_collect_production_batches` R2.

### New questions

### Q1. The "Maintenance" filter never shows anything — 🐞 BUG-1805
**Background:** The calendar's categories include `maintenance`, and the frontend shows a "Maintenance" chip with its own colour. Machine maintenance logs are dated (`maintenance_date`). The service has no collector for them.
**What happens today:** `types=[maintenance]` returns an empty list; with no filter, no maintenance log ever appears (verified).
**Example:** a machine was serviced on 10 May and logged; the user turns on only "Maintenance" for May and sees an empty calendar.
**Rules affected:** `get_events` R6
**Suggested answer:** `bug — each live maintenance log of the workspace appears under maintenance on its maintenance_date.` A log is history: a deleted machine or factory hides nothing (machine maintenance log manager standing decision 1); the log's own soft delete hides it; a log linked to another workspace's machine is left out (BUG-1101). Alternative: remove `maintenance` from the categories and the frontend.
**Answer:** as suggested — decided by Claude under the reviewer's delegation (2026-11-04).
**Resolution:** 🐞 BUG-1805 (pattern `advertised-option-not-implemented`). Rules: `get_events` R6.

### Owner answers (`docs/testing/owner-questions.md`)
- **OQ-5** — private projects. The project module hides a private project from members who may not open it (`ProjectManager.can_access_project`: owner, privileged roles, its creator, its members). The calendar shows every project's name, dates, first 120 characters of description and status to every member. Added to OQ-5 as "Same case, calendar". **Answer:** bug — answered by the owner (2026-11-04): calendar entries follow the record's own visibility; a member who cannot open the private project does not see it. **Resolution:** 🐞 BUG-1869 (pattern `child-ignores-parent-visibility`). The service learns the caller as the project pages do: `get_events` takes the caller's `user_id` (the endpoint passes `current_user.id`, adding the `get_current_active_user` dependency that the project endpoints use), and `_collect_projects` keeps a private project only when the `can_access_project` rule admits that user. Rules: `get_events` Inputs, R7; `_collect_projects` R6.

- **OQ-14** — voided work orders are shown (status `VOIDED`), while voided purchase and expense orders, voided invoices and payments, cancelled deliveries and cancelled batches are hidden. **Answer:** bug — answered by the owner (2026-11-04), suggested answer: a voided work order is hidden from the calendar, like voided purchase and expense orders; drafts, in-progress and completed work orders stay. **Resolution:** 🐞 BUG-1876 (pattern `voided-record-not-excluded`, as BUG-717). Rule: `_collect_work_orders` R3.
- **OQ-15** — work orders and sales orders of a soft-deleted factory are shown, while projects and batches of one are hidden (P1, P2). **Answer:** bug — answered by the owner (2026-11-04), alternative (a): work and sales orders of a deleted factory are hidden from the calendar now, like projects and batches. **Resolution:** 🐞 BUG-1877 (work orders), BUG-1878 (sales orders) (pattern `join-ignores-soft-deleted`, as BUG-1806, BUG-1807); an inactive-but-live factory hides nothing, as P1. Rules: `_collect_work_orders` R4, `_collect_sales_orders` R3.

## Overview
`CalendarService.get_events` builds the workspace calendar: one event per date field of each dated record in a date range — work orders, purchase orders, expense orders, sales orders and deliveries, invoices and their payments, production batches, projects — optionally filtered by category, sorted by date. It reads only; it never writes, commits or rolls back. Its invariants: only the caller's workspace, only dates inside the range (both ends included), and records that are voided, cancelled or deleted are left out where the table has such a mark.

**Callables:** 15 specified · 1 not specified
**Externals to mock:** none.
**Integration-only behavior:** `GET /calendar/events` — query parsing of `start`, `end`, repeated `types`; `ValueError` → 400 with its message; any other exception → 500 `Internal server error`; `total = len(events)`.

**Facts for the test designer**
- Import: `from app.services.calendar_service import CalendarService, calendar_service, _event_id, _date_in_range, _dt_to_date`; `from app.schemas.calendar import CalendarCategory, CalendarEventResponse`. `get_events(db, *, workspace_id, start, end, types=None)`: everything after `db` is **keyword-only**; intended (BUG-1869) it also takes keyword `user_id`. The private collectors take `(db, workspace_id, start, end, allowed)` positionally, `allowed` a `set[CalendarCategory]` or `None`; intended, `_collect_projects` also receives the caller's id — its exact position is the fix's choice, so BUG-1869 cards go through `get_events`.
- `CalendarCategory` values: `work_orders`, `maintenance`, `purchase`, `expense`, `sales`, `invoices`, `production`, `projects`.
- `CalendarEventResponse` fields: `id: str`, `category`, `source_type: str`, `record_id: int`, `date: date`, `date_label: str`, `title: str`, `subtitle: str | None`, `link: str`, `meta: dict` (default `{}`).
- Date columns: `Date` on work orders (`planned_date`, `end_date`, nullable), purchase orders (`order_date`, `expected_delivery_date`, `actual_delivery_date`, all nullable), expense orders (`expense_date` NOT NULL, `due_date`), sales orders (`order_date` NOT NULL, `expected_delivery_date`), deliveries (`scheduled_date`, `actual_delivery_date`), invoices (`invoice_date` NOT NULL, `due_date`), payments (`payment_date` NOT NULL), batches (`batch_date` NOT NULL). **`DateTime`** on projects (`start_date`, `end_date`, `deadline`, nullable, naive).
- "Hidden" marks: work order `is_deleted`; purchase / expense order `voided`; delivery `delivery_status` (`'planned' | 'delivered' | 'cancelled'`); invoice `invoice_status` (`'draft' | 'confirmed' | 'voided'`); payment `is_voided`; batch `status` (`'draft' | 'in_progress' | 'completed' | 'cancelled'`); project `is_deleted` (BUG-1800). Sales orders have no such mark (a deleted sales order is removed).
- **What each close writes** (read from the code that closes; gap G5). The calendar reads **only the mark column**; the other columns never change an event, so a Given may set the mark alone.
  - Purchase order void (`PurchaseOrderService`) and expense order void (`ExpenseOrderService`): `voided = True`, `void_note`, `voided_at`, `voided_by`.
  - Invoice void (`AccountInvoiceManager`): `invoice_status = "voided"`, `void_note`, `paid_amount = 0.00`, `payment_status = "unpaid"` (the invoice has no `voided_at` column); each of its active payments is voided as below.
  - Payment void (`InvoicePaymentManager`, or the invoice void): `is_voided = True`, `voided_at`, `voided_by`, `void_note`.
  - Delivery cancel (`SalesManager`, only from `planned`): `delivery_status = "cancelled"` only (`updated_at` by `onupdate`). No `cancelled_at` column exists.
  - Batch cancel (`ProductionBatchManager.cancel_batch`, from `draft` / `in_progress`): `status = "cancelled"`, `updated_by`, and `notes` when given — so a cancelled batch's `notes` may be the cancel reason; batch delete (`draft` only) writes `status = "cancelled"` only. No `cancelled_at` column exists.
  - Work order delete (work order DAO `soft_delete`): `is_active = False`, `is_deleted = True`, `deleted_at`, `deleted_by`. Work order void: `status = "VOIDED"`, `void_note`, `voided_at`, `voided_by` — hidden by intent ([BUG-1876] R3; today shown).
  - Project delete (`ProjectManager`): `is_deleted = True`, `deleted_at`, `deleted_by` (`is_active` untouched).
- **Unreachable `None` sides** (verified: NOT NULL in the model and in `marker_test`): `total_amount` of purchase, expense and sales orders, `invoice_amount`, `payment_amount`, work order `priority` (Enum), project `status` (Enum), project `description`. So every amount in `meta` is a string, `meta.priority` is always a priority value, `meta.status` of a project is always a status value; the code's `None` fallbacks cannot be reached and get no card. Reachable `None`s: `meta.account_id` of a purchase order (nullable), `meta.payment_method` (nullable), `subtitle` of orders, invoices and batches (`description` / `notes` nullable).
- **Amount text** is `str()` of the attribute as the session holds it: an amount given as `Decimal("10.50")` gives `"10.50"`; an amount left to the model default (`0`, int) gives `"0"` while the row is in the session unexpired, and `"0.00"` once reloaded (verified). Givens always set amounts explicitly as `Decimal` with two places.
- **Who may open a private project** (BUG-1869; the rule of `ProjectManager.can_access_project`, which the project pages apply): visibility `"workspace"` → every caller; otherwise only (1) the workspace owner (`workspaces.owner_user_id`), (2) an `active` member of the workspace whose role is `owner` or `ground-team-manager`, (3) the project's `created_by`, (4) a person with a `project_members` row for that project in that workspace (`ProjectMember(workspace_id, project_id, user_id)`; project member DAO spec). Anyone else — e.g. an active `ground-team` member who is none of these — may not. `created_by` on `Project` is nullable; a private project with no creator is open only to (1), (2), (4).
- Project `status` values (`ProjectStatusEnum`): `PLANNING` (default), `IN_PROGRESS`, `COMPLETED`, `ON_HOLD`, `CANCELLED`; `meta.status` is the value text (verified for all five). Project `visibility` is a `String(20)`, values `"workspace"` (default, `server_default`) and `"invited_only"` (`ProjectVisibilityEnum.WORKSPACE` / `INVITED_ONLY`, `app.models.enums`); `"private"` is not a value the code uses.
- Minimum rows (verified): `Factory(workspace_id, name, abbreviation)`; `Project(workspace_id, factory_id, name, description)`; `WorkOrderType(workspace_id, name)`; `WorkOrder(workspace_id, work_order_number, work_order_type_id, title, factory_id)`; `Account(workspace_id, name)`; `AccountInvoice(workspace_id, account_id, invoice_type, invoice_amount, invoice_date)`; `InvoicePayment(workspace_id, invoice_id, payment_amount, payment_date)`. Workspaces and profiles from `tests/unit/factories.py` (`make_workspace`, `make_profile`).
- Minimum rows, other tables (verified by inserting each in `marker_test`; gap G3). `created_by` below is NOT NULL and a real FK: a `make_profile` row.
  - `Status(workspace_id, name, comment)` — `app.models.status`.
  - `PurchaseOrder(workspace_id, po_number, destination_type, destination_id, current_status_id, created_by)` — `app.models.purchase_order`; `destination_type` e.g. `"storage"`, `destination_id` a plain int (no FK; use the factory id); `voided` defaults `False`; `(workspace_id, po_number)` unique.
  - `ExpenseOrder(workspace_id, expense_number, expense_category, created_by)` — `app.models.expense_order`; `expense_date` defaults to today, so always set it; `(workspace_id, expense_number)` unique.
  - `SalesOrder(workspace_id, sales_order_number, account_id, factory_id, current_status_id, created_by)` — `app.models.sales_order`; `order_date` defaults to today, so always set it; `sales_order_number` unique across **all** workspaces.
  - `SalesDelivery(workspace_id, sales_order_id, delivery_number, created_by)` — `app.models.sales_delivery`; `delivery_status` defaults `"planned"`; `delivery_number` unique across all workspaces.
  - `ProductionLine(workspace_id, factory_id, name)` — `app.models.production_line`.
  - `ProductionBatch(workspace_id, batch_number, production_line_id, batch_date)` — `app.models.production_batch`; `status` defaults `"draft"`; `(workspace_id, batch_number)` unique.
  - `Machine(workspace_id, name, factory_id)` — `app.models.machine`.
  - `MachineMaintenanceLog(workspace_id, machine_id, maintenance_type, maintenance_date, summary)` — `app.models.machine_maintenance_log`; `maintenance_type` a `MaintenanceTypeEnum` (`PREVENTIVE`, `REPAIR`, `EMERGENCY`, `INSPECTION`) (BUG-1805 only).
  - Nullable text read as `subtitle`: `description` on purchase, expense and sales orders and invoices; `notes` on batches.

**Notes for the test designer**
- Session: as the Notes of `department_service.spec.md`; read only, so no commit handling is needed beyond TC6.
- **Order of ties:** records of one collector with the same date and title come in database order (no `ORDER BY`): never assert their relative order. A record's own events keep its field order (R4 of `get_events`).
- **BUG-1876, BUG-1877, BUG-1878 (OQ-14, OQ-15 answered):** strict xfail cards for the hidden record (voided work order; work order and sales order of a soft-deleted factory); plain pass cards for what stays (draft, in-progress and completed work orders; orders of an inactive but not deleted factory).
- **BUG-1869 (OQ-5 answered):** `get_events` has no `user_id` today (a call with it raises `TypeError`). Cards for R6 / R7 call `get_events(..., user_id=…)` and are strict xfail on BUG-1869 — the refused caller (private project absent) and each allowed-caller kind (present). Every other card keeps today's call without `user_id`, so it keeps regression protection now and gains `user_id` (a one-line change) when the fix lands.
- **BUG-1805:** the intended maintenance events need a `MachineMaintenanceLog` row (machine maintenance log DAO spec, Facts); today `[]` → strict xfail.

## Not specified
- `calendar_service` — module-level singleton, no logic. (`DateFieldSpec` is a type alias.)

---

## `_event_id(source_type, record_id, date_field)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `_expand_date_fields`, `_collect_invoice_payments`, `_collect_production_batches`)

**Rules:**
- **R1.** Returns `"<source_type>:<record_id>:<date_field>"`, e.g. `"project:5:deadline"`.

**Errors:** none. **Side effects:** none

---

## `_date_in_range(value, start, end)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `_expand_date_fields`)

**Rules:**
- **R1.** `True` when `start <= value <= end` (both ends included); `False` before `start`, after `end`, or when `value` is `None`.

**Errors:** none. **Side effects:** none

---

## `_dt_to_date(value)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `_collect_projects`)

**Rules:**
- **R1.** A `datetime` gives its calendar date (the time is dropped; no time-zone conversion); `None` gives `None`.

**Errors:** none. **Side effects:** none

---

## `CalendarService.get_events(db, *, workspace_id, start, end, types=None)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /calendar/events`, `types` `None` when omitted)

**Purpose:** Every dated event of the workspace between two dates, optionally of some categories only.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | the caller's workspace |
| `start`, `end` | `date` | inclusive range; `start <= end` required; no maximum length |
| `types` | sequence of `CalendarCategory` or `None` | `None` or empty → all categories; duplicates are irrelevant |
| `user_id` | int, keyword-only, required | [BUG-1869] the caller (`current_user.id`, passed by `GET /calendar/events`, which then depends on `get_current_active_user` as the project endpoints do). *(requires new parameter `user_id`; today the service has no caller identity.)* |

**Returns:** `list[CalendarEventResponse]`.

**Rules:**
- **R1.** `start` after `end` raises `ValueError("start must be on or before end")` before anything is read. `start == end` is a one-day range.
- **R2.** `types=None` and `types=[]` both give every category. Otherwise only events of the listed categories are returned, and collectors of other categories read nothing (`_category_allowed` R1).
- **R3.** The result is the union of every collector's events for the range (each collector's rules below). `sales` covers sales orders **and** deliveries; `invoices` covers invoices **and** payments.
- **R4.** Events are sorted ascending by `date`, then by the category's **value** as text (`expense` < `invoices` < `maintenance` < `production` < `projects` < `purchase` < `sales` < `work_orders`), then by `title`. Ties keep the collection order: a record's own events in its field order (e.g. `Invoice date` before `Due date` of one invoice), sales orders before deliveries, invoices before payments; records within one collector in database order (unspecified).
- **R5.** Read only: nothing is written, committed or rolled back (TC6, `base_service.spec.md`). An empty range or workspace gives `[]`.
- **R6.** [BUG-1805] (Q1) With `maintenance` allowed, each machine maintenance log of the workspace whose `maintenance_date` is in range gives one event: `category = maintenance`, `source_type = "machine_maintenance_log"`, `record_id` = the log id, `id = "machine_maintenance_log:<id>:maintenance_date"`, `date = maintenance_date`, `date_label = "Maintenance date"`. A soft-deleted log gives none; a log of a soft-deleted machine or factory still gives one (logs are history); a log linked to another workspace's machine gives none (BUG-1101). `title`, `subtitle`, `link`, `meta` are not fixed by this spec. *(Today: no collector; `maintenance` always gives nothing. Verified.)* *(requires a new collector.)*
- **R7.** [BUG-1869] (OQ-5) `user_id` reaches `_collect_projects` (its R6); no other collector uses it — every other category is the same for every member. *(Today: no `user_id`; a call with it raises `TypeError`.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `start > end` | `ValueError` | `start must be on or before end` |
| a collector's database error | unchanged | — |

**Side effects:** none

---

## `CalendarService._category_allowed(category, allowed)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: every collector)

**Rules:**
- **R1.** `True` when `allowed` is `None` or contains `category`; otherwise `False`, and the calling collector returns `[]` without reading.

**Errors:** none. **Side effects:** none

---

## `CalendarService._expand_date_fields(*, record, source_type, category, date_fields, title, subtitle, link, start, end, meta=None)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** internal (used by: the work order, purchase, expense, sales order, delivery, invoice and project collectors)

**Purpose:** One event per date field of a record that falls in the range.

**Rules:**
- **R1.** For each `(field, label)` of `date_fields`, in that order, the record's value of `field` is read (a missing attribute counts as `None`); a `datetime` is reduced to its date.
- **R2.** A value that is `None` or outside the range gives no event (`_date_in_range` R1).
- **R3.** Each value in range gives one event: `id = _event_id(source_type, record.id, field)`, `category`, `source_type`, `record_id = record.id`, `date` = the value, `date_label` = the label, `title`, `subtitle`, `link`, and `meta` = the given `meta` or `{}`.
- **R4.** A record with two fields on the same day gives two events.

**Errors:** a `title` that is not a string raises `pydantic.ValidationError` (not reachable: every title column is NOT NULL). **Side effects:** none

---

## `CalendarService._collect_work_orders(db, workspace_id, start, end, allowed)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_events`)

**Rules:**
- **R1.** Category `work_orders`. Work orders of the workspace that are not soft-deleted, with `planned_date` or `end_date` in range. Another workspace's orders never appear; a soft-deleted one never appears.
- **R2.** Events for `planned_date` (`"Planned date"`) and `end_date` (`"End date"`) as `_expand_date_fields`; `source_type = "work_order"`; `title = work_order_number`; `subtitle = title`; `link = "/orders/work"`; `meta = {"status": <status text>, "priority": <priority value, e.g. "MEDIUM">}`. `priority` is never `None` (NOT NULL Enum, default `MEDIUM`; Facts).
- **R3.** [BUG-1876] (OQ-14) A work order with status `VOIDED` gives no event. *(Today: listed, verified: `meta.status = "VOIDED"`. Answered by the owner (2026-11-04).)*
- **R3a.** Work orders with status `DRAFT`, `IN_PROGRESS` or `COMPLETED` are listed (today's behavior, unchanged by OQ-14).
- **R4.** [BUG-1877] (OQ-15) A work order whose factory has `is_deleted = True` gives no event; an inactive-but-live factory hides nothing. *(Today: listed. Read. Answered by the owner (2026-11-04), alternative (a).)*

**Errors:** none. **Side effects:** none

---

## `CalendarService._collect_purchase_orders(db, workspace_id, start, end, allowed)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_events`)

**Rules:**
- **R1.** Category `purchase`. Purchase orders of the workspace with `voided = False` and at least one of `order_date`, `expected_delivery_date`, `actual_delivery_date` in range; any status (drafts included). A voided order never appears; nor another workspace's.
- **R2.** Events for `order_date` (`"Order date"`), `expected_delivery_date` (`"Expected delivery"`), `actual_delivery_date` (`"Actual delivery"`); `source_type = "purchase_order"`; `title = po_number`; `subtitle = description`; `link = "/orders/purchase?orderId=<id>"`; `meta = {"total_amount": <str of the stored amount, e.g. "10.50">, "account_id": <id or None>, "current_status_id": <id>}`. Amounts in every collector's `meta` (`total_amount`, `invoice_amount`, `payment_amount`) are always text, never `None`: the amount columns are NOT NULL (Facts, "Unreachable `None` sides" and "Amount text"; gap G2).

**Errors:** none. **Side effects:** none

---

## `CalendarService._collect_expense_orders(db, workspace_id, start, end, allowed)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_events`)

**Rules:**
- **R1.** Category `expense`. Expense orders of the workspace with `voided = False` and `expense_date` or `due_date` in range; a voided order or another workspace's never appears.
- **R2.** Events for `expense_date` (`"Expense date"`) and `due_date` (`"Due date"`); `source_type = "expense_order"`; `title = expense_number`; `subtitle = description`; `link = "/orders/expense"`; `meta = {"category": expense_category, "total_amount": <str>}`.

**Errors:** none. **Side effects:** none

---

## `CalendarService._collect_sales_orders(db, workspace_id, start, end, allowed)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_events`)

**Rules:**
- **R1.** Category `sales`. Sales orders of the workspace with `order_date` or `expected_delivery_date` in range, whatever their progress; another workspace's never appear.
- **R2.** Events for `order_date` (`"Order date"`) and `expected_delivery_date` (`"Expected delivery"`); `source_type = "sales_order"`; `title = sales_order_number`; `subtitle = description`; `link = "/sales/overview"`; `meta = {"total_amount": <str>}`.
- **R3.** [BUG-1878] (OQ-15) A sales order whose factory has `is_deleted = True` gives no event; an inactive-but-live factory hides nothing. *(Today: listed. Read. Answered by the owner (2026-11-04), alternative (a).)* Deliveries of such an order are not covered by the owner's answer and keep R1 of `_collect_sales_deliveries`.

**Errors:** none. **Side effects:** none

---

## `CalendarService._collect_sales_deliveries(db, workspace_id, start, end, allowed)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_events`)

**Rules:**
- **R1.** Category `sales` (allowed whenever sales orders are). Deliveries of the workspace whose `delivery_status` is not exactly `"cancelled"`, with `scheduled_date` or `actual_delivery_date` in range. A cancelled delivery or another workspace's never appears.
- **R2.** Events for `scheduled_date` (`"Scheduled delivery"`) and `actual_delivery_date` (`"Actual delivery"`); `source_type = "sales_delivery"`; `title = delivery_number`; `subtitle = "Sales order #<sales_order_id>"`; `link = "/sales/pipeline"`; `meta = {"delivery_status": <status>}`.

**Errors:** none. **Side effects:** none

---

## `CalendarService._collect_invoices(db, workspace_id, start, end, allowed)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_events`)

**Rules:**
- **R1.** Category `invoices`. Invoices of the workspace whose `invoice_status` is not `"voided"` (drafts included), with `invoice_date` or `due_date` in range. A voided invoice or another workspace's never appears.
- **R2.** Events for `invoice_date` (`"Invoice date"`) and `due_date` (`"Due date"`); `source_type = "account_invoice"`; `subtitle = description`; `link = "/accounts/<account_id>?invoiceId=<id>"`; `meta = {"account_id", "invoice_type", "payment_status", "invoice_amount": <str>}`.
- **R3.** `title` is `invoice_number`; when it is `None` or `""`, `"Invoice #<id>"` (verified for `""`).

**Errors:** none. **Side effects:** none

---

## `CalendarService._collect_invoice_payments(db, workspace_id, start, end, allowed)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_events`)

**Rules:**
- **R1.** Category `invoices`. Payments of the workspace with `is_voided = False` and `payment_date` in range, each with its invoice. A voided payment or another workspace's never appears. The invoice's own status is not looked at (voiding an invoice voids its active payments: `AccountInvoiceManager`, read).
- **R2.** One event per payment: `id = "invoice_payment:<id>:payment_date"`, `category = invoices`, `source_type = "invoice_payment"`, `record_id` = payment id, `date = payment_date`, `date_label = "Payment date"`, `title = "Payment #<id>"`, `subtitle = "Invoice #<invoice_id>"`, `link = "/accounts/<invoice's account_id>?invoiceId=<invoice id>"`, `meta = {"invoice_id", "account_id": <invoice's>, "payment_amount": <str>, "payment_method": <text or None>}`.
- **R3.** [BUG-1801] (HR-16) A payment whose invoice belongs to another workspace gives no event: none of that invoice's ids appear. *(Today: listed with the other workspace's invoice id and account id. Verified.)*

**Errors:** none. **Side effects:** none

---

## `CalendarService._collect_production_batches(db, workspace_id, start, end, allowed)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_events`)

**Rules:**
- **R1.** Category `production`. Batches of the workspace whose `status` is not exactly `"cancelled"` and whose `batch_date` is in range; one event each: `id = "production_batch:<id>:batch_date"`, `source_type = "production_batch"`, `date = batch_date`, `date_label = "Batch date"`, `title = batch_number`, `subtitle = notes`, `link = "/production"`, `meta = {"status": <status>}`. A cancelled batch or another workspace's never appears.
- **R2.** [BUG-1807] (P2) A batch whose production line's factory is soft-deleted gives no event; an inactive line or factory hides nothing. *(Today: listed. Read.)*

**Errors:** none. **Side effects:** none

---

## `CalendarService._collect_projects(db, workspace_id, start, end, allowed)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `get_events`)

**Rules:**
- **R1.** Category `projects`. Projects of the workspace with `start_date`, `end_date` or `deadline` on a day in range: any time of that day counts, from 00:00 to 23:59:59.999999 of `end` (verified: 23:30 on the last day is in). Any status. Another workspace's never appear.
- **R2.** [BUG-1800] (HR-4) A soft-deleted project gives no event. *(Today: listed. Verified.)*
- **R3.** [BUG-1806] (P1) A project whose factory is soft-deleted gives no event; an inactive-but-live factory hides nothing. *(Today: listed. Read.)*
- **R4.** Events for `start_date` (`"Start date"`), `end_date` (`"End date"`), `deadline` (`"Deadline"`), each the calendar date of the stored value (`_dt_to_date` R1); `source_type = "project"`; `title = name`; `link = "/project"`; `meta = {"status": <status value, e.g. "PLANNING">}` — any of the five values (`PLANNING`, `IN_PROGRESS`, `COMPLETED`, `ON_HOLD`, `CANCELLED`) is listed, `CANCELLED` and `COMPLETED` included, with its value text (verified for all five). `status` is never `None` (NOT NULL; Facts).
- **R5.** `subtitle` is the first 120 characters of `description`; an empty description gives `None` (verified).
- **R6.** [BUG-1869] (OQ-5) A private project (`visibility = "invited_only"`, `ProjectVisibilityEnum.INVITED_ONLY`) gives its events only when the caller (`user_id`, `get_events` R7) may open it (Facts, "Who may open a private project": workspace owner, an active `owner` / `ground-team-manager` member, its creator, a project member); for anyone else it gives no event at all — no name, dates, description or status. A `"workspace"` project gives its events to every caller. R1–R5 apply unchanged to the projects that remain. *(Today: listed for every member, verified with an `invited_only` project, gap G1. Answered by the owner (2026-11-04).)*

**Errors:** none. **Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 26 | id format | `_event_id` R1 |
| 30 | `None` / before / after / inside, inclusive | `_date_in_range` R1 |
| 34–36 | `None` → `None`; datetime → date | `_dt_to_date` R1 |
| 51–52 | `start > end` → `ValueError` | `get_events` R1 |
| 54 | `types` falsy (`None`, `[]`) → all | `get_events` R2 |
| 57–70 | every collector, fixed order; no maintenance collector (BUG-1805) | `get_events` R3, R4, R6 |
| 72 | sort by date, category value, title (stable) | `get_events` R4 |
| 78 | `allowed is None` / category in / not in | `_category_allowed` R1 |
| 95 | `meta or {}` | `_expand_date_fields` R3 |
| 96–101 | per field: datetime → date; `None` / out of range → skip | `_expand_date_fields` R1, R2, R4 |
| 102–115 | event built | `_expand_date_fields` R3 |
| 126–127 | work orders not allowed → `[]` | `_category_allowed` R1 |
| 129–140 | workspace, not deleted, either date in range; status and factory ignored (BUG-1876, BUG-1877) | `_collect_work_orders` R1, R3, R3a, R4 |
| 158 | `priority` set / `None` (`None` unreachable: NOT NULL) | `_collect_work_orders` R2 |
| 171–186 | not voided, any of three dates in range | `_collect_purchase_orders` R1 |
| 206 | `total_amount` `None` / value (`None` unreachable: NOT NULL) | `_collect_purchase_orders` R2 |
| 222–236 | not voided, either date | `_collect_expense_orders` R1 |
| 256 | amount `None` / value (`None` unreachable: NOT NULL) | `_collect_expense_orders` R2; `_collect_purchase_orders` R2 (amounts) |
| 270–282 | workspace, either date; no hidden mark; factory ignored (BUG-1878) | `_collect_sales_orders` R1, R3 |
| 301 | amount `None` / value (`None` unreachable: NOT NULL) | `_collect_sales_orders` R2; `_collect_purchase_orders` R2 (amounts) |
| 314–328 | not `"cancelled"`, either date | `_collect_sales_deliveries` R1 |
| 359–373 | not `"voided"`, either date | `_collect_invoices` R1 |
| 386 | `invoice_number` falsy → `Invoice #<id>` | `_collect_invoices` R3 |
| 395 | amount `None` / value (`None` unreachable: NOT NULL) | `_collect_invoices` R2; `_collect_purchase_orders` R2 (amounts) |
| 409–422 | payment workspace, not voided, date in range; invoice joined by id only (BUG-1801) | `_collect_invoice_payments` R1, R3 |
| 424–443 | event per payment; amount `None` / value (`None` unreachable: NOT NULL) | `_collect_invoice_payments` R2; `_collect_purchase_orders` R2 (amounts) |
| 453–465 | not `"cancelled"`, date in range; factory ignored (BUG-1807) | `_collect_production_batches` R1, R2 |
| 491–508 | day bounds; any of three dates; deleted, factory, visibility ignored (BUG-1800, BUG-1806, BUG-1869) | `_collect_projects` R1, R2, R3, R6; `get_events` R7 |
| 513–535 | dates reduced to days; events | `_collect_projects` R4 |
| 530 | description truthy → first 120 chars / `None` | `_collect_projects` R5 |
| 534 | status set / `None` (`None` unreachable: NOT NULL) | `_collect_projects` R4 |
| 540 | module singleton | Not specified |

## Gap log
- G1 (`calendar_service.cases.md` gap 1) — Fact (correction) — `_collect_projects` R6: the private value is `"invited_only"` (`ProjectVisibilityEnum.INVITED_ONLY`), not `"private"`; Facts list both visibility values. The earlier "verified" run had stored the string `"private"`, which the column accepts but the code never writes.
- G2 (`calendar_service.cases.md` gap 2) — Fact — every amount column (`total_amount` of purchase, expense, sales orders; `invoice_amount`; `payment_amount`) is NOT NULL in the model and in `marker_test`, so the `None` side of the amount branches is unreachable and `meta` always holds text; how that text looks for an explicit `Decimal` vs a model default added to Facts ("Amount text"). Pointer in `_collect_purchase_orders` R2; Branch map rows 206, 256, 301, 395, 424 annotated.
- G3 (`calendar_service.cases.md` gap 3) — Fact — minimum rows for `Status`, purchase / expense / sales orders, deliveries, production lines, batches, machines and maintenance logs added to Facts (verified by insert), with defaults and unique keys; nullable `description` / `notes` confirmed. Work order `priority` is a NOT NULL Enum (default `MEDIUM`): `None` unreachable, stated in `_collect_work_orders` R2; Branch map 158 annotated.
- G4 (`calendar_service.cases.md` gap 4) — Fact — project status values `PLANNING`, `IN_PROGRESS`, `COMPLETED`, `ON_HOLD`, `CANCELLED` named in Facts and `_collect_projects` R4 (all five listed, verified); `status` is NOT NULL, so `meta.status` is never `None`; Branch map 534 annotated.
- G5 (`calendar_service.cases.md` gap 5) — Fact — Facts "What each close writes": the columns written by purchase / expense order void, invoice void, payment void, delivery cancel, batch cancel and delete, work order delete and void, project delete. The calendar reads only the mark column; `cancelled_at` does not exist on deliveries or batches, and invoices have no `voided_at`. Givens may set the mark alone.
- Owner check: none of the five gaps changes which orders count or any amount; nothing parked, no new OQ, no new bug.
- OQ-5 (apply-review 2026-11-04, not a gap) — owner's answer applied: `get_events` Inputs (`user_id`), R7; `_collect_projects` R6 → BUG-1869. Card CAL-OQ5-01 to be rewritten; new cards for the allowed-caller kinds.
- OQ-14, OQ-15 (apply-review 2026-11-04, not a gap) — owner's answers applied: `_collect_work_orders` R3, R3a, R4; `_collect_sales_orders` R3 → BUG-1876, BUG-1877, BUG-1878. Cards CAL-OQ14-01, CAL-OQ14-02, CAL-OQ15-01, CAL-OQ15-02 to be rewritten.

## Follow-ups for other reviews
> Nothing below is a rule of this module.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | Calendar endpoint | The range has no maximum: a request for 100 years reads every dated row of the workspace in one response. A cap (e.g. 1 year → 400) is a product choice; no rule here. | reading |
| FU-2 | Calendar endpoint | Every member sees invoices, payments and amounts of the whole workspace on the calendar. Whether that matches who may open the invoice pages was not checked here; noted for the access review, not asked. | reading |
