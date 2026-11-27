# Spec — `app/dao/expense_order.py`

> **Status:** APPROVED (2026-11-11; nothing open — OQ-42, OQ-43, OQ-44 answered by the owner: 🐞 BUG-2717, BUG-2718, BUG-2719; the case designer's four gaps closed, Gap log at the end)
> **Source commit:** e48a092

> **Review round 2026-11-11 (apply-review + fill-gaps).** **Owner (2026-11-11):** OQ-42 bug as suggested → 🐞 BUG-2717; OQ-43 bug as suggested → 🐞 BUG-2718; OQ-44 bug as suggested → 🐞 BUG-2719. The rules that were *pending* now state the intended behaviour, tagged, with today's behaviour in *(Today: …)*. **Delegated (decided by Claude under the reviewer's delegation, 2026-11-11):** which hub-stats counts OQ-42 touches (see the OQ-42 Resolution: the same split the owner chose for the PO hub in OQ-35); `locked` counts as confirmed for OQ-43 / OQ-44 (the PO manager treats `confirmed` and `locked` alike, OQ-37); an order whose invoice is voided is treated as having no invoice in the due timeline; two accounts may share a name (G2); the same number in another workspace is accepted (G3, rule `get_next_number` R4a under BUG-749). **Gaps:** all four gaps of `expense_order.cases.md` closed (Gap log).
>
> **Review round 2026-11-10 (describe).** **Owner:** nothing answered yet; OQ-42…3 parked in `docs/testing/owner-questions.md`. **Delegated:** P1–P4 and the house-rule lines were decided by Claude under the reviewer's delegation (2026-11-10). None of them is the owner's own answer.
>
> **Already decided in the approved expense order manager spec** (`tests/unit/managers/expense_order_manager.spec.md`, PASS) and reused here with their IDs, not re-asked: unescaped search wildcards (BUG-745), recent-orders order (BUG-746), open-by-account ties (BUG-747), unpaid-pipeline sample ties (BUG-748), expense numbering — global unique index, text-sorted "highest", no lock (BUG-749), `account_id` / `order_template_id` not checked for workspace (BUG-750), `invoice_id` client-writable (BUG-751). That spec states the hub filter rules as `list_expense_orders_for_hub` R1–R12 by reading through to this DAO; the rules below are the detailed ones, and the manager's stay pointers to them.
>
> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated (`create`, `update`, `get` are inherited and used by `ExpenseOrderManager`).
>
> **Standing decisions applied (not asked again):** no order recipe counts as deterministic unless it ends in `id`; numbers are made only by the system, upper-case, case-sensitive prefix (sales order spec G3); the year and "today" come from UTC (BUG-1334 family); HR-15 money rounds half away from zero; HR-16 a link to another workspace's row is invalid data and is treated as not found on reads (BUG-2504 / BUG-2555 precedent).
>
> **Verified by running** (my own throwaway script `v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdao\expense_order\`, one transaction on `marker_test`, rolled back, private `COVERAGE_FILE`; nothing committed): the table's indexes (both `uq_eo_workspace_number` **and** the global unique `ix_expense_orders_expense_number` exist); `get_next_number` in an empty workspace (`EXP-2026-001`) and with only `EXP-2026-abc` stored (`EXP-2026-001`); a second workspace's `EXP-2026-001` failing on `ix_expense_orders_expense_number` (23505); search `Foreign` finding an order linked to another workspace's account, `Gone` finding one linked to a soft-deleted account, `o` and `_` matching every order; hub stats with a voided order included (`(3, 180.00, 3, 180.00, 3)`); the filtered snapshot (voided order counted in `draft`, foreign and deleted accounts named in `open_by_account`); the actionable snapshot (a draft invoice counted as "Unpaid" 100.00; another workspace's confirmed invoice counted as "Partial" 50.00; an order due beyond this month in no bucket); `get_by_workspace(invoice_id=…, limit=1)`, `account_id=0` (no filter); `status_ids=[9]` (no filter); `get_by_order` leaving out a line stored with another `workspace_id`. **Read, not run:** `ExpenseOrderManager`, `ExpenseOrderService`, `AccountInvoiceService.confirm_invoice`, `AttachmentManager`, `GET /expense-orders/`, `GET /expense-orders/hub-stats`, the web app's `expenseOrderHubApiParams.ts` and `ExpenseOrderFinancialOverview.tsx`. **Not run:** anything over HTTP; two concurrent transactions.

## Review
> All answered. Delegated items applied 2026-11-10; owner answers OQ-42…44 applied 2026-11-11.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | The year in an expense number comes from the server's local clock | bug — from UTC (BUG-2710) | Claude, delegated |
| P2 | "Expense orders of an invoice" has no final tie-breaker | bug — then `id` desc (BUG-2711) | Claude, delegated |
| P3 | Lines of one order with the same line number have no order | bug — then `id` asc (BUG-2713) | Claude, delegated |
| P4 | Dashboard category breakdown has unordered ties | bug — then category key asc (BUG-2712) | Claude, delegated |
| OQ-42 | Hub money figures include voided expense orders (the web app never leaves them out) | bug — voided orders never count in money figures (BUG-2717) | owner, 2026-11-11 |
| OQ-43 | The "unpaid pipeline" only ever shows draft invoices, never bills waiting for payment | bug — confirmed unpaid bills, at amount − paid (BUG-2718) | owner, 2026-11-11 |
| OQ-44 | The due timeline drops an order once it is completed, and counts the full total, not what is still owed | bug — what is still to pay (BUG-2719) | owner, 2026-11-11 |

Decided by house rules: hub search, the open-by-account widget and the unpaid pipeline use another workspace's account or invoice (BUG-2714, HR-16); hub search matches a soft-deleted account's name (BUG-2715, HR-4).
Reused from the manager spec: BUG-745, BUG-746, BUG-747, BUG-748, BUG-749, BUG-750, BUG-751.

### House-rule violations — applied automatically

- **HR-16** `_apply_expense_order_hub_filters` R11, `aggregate_financial_snapshot_filtered` R9, `aggregate_financial_snapshot_actionable` R10 — the account join (search, open by account) and the invoice join (unpaid pipeline) compare ids only. Verified: an order linked to workspace B's account "Foreign Co" is found by searching `Foreign` and listed in A's open-by-account as `Foreign Co` with B's account id; an order linked to B's confirmed invoice puts B's outstanding 50.00 in A's "Partial" bucket. Such links can be stored today (BUG-750 account, BUG-751 invoice). Intended: such a link is treated as not found — the account's name does not match, the order is left out of open by account (as if it had no account), the order is left out of the unpaid pipeline.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-2714 (pattern `cross-workspace-row-exposed`, per BUG-2504 / BUG-2555). Rules: `_apply_expense_order_hub_filters` R11, `aggregate_financial_snapshot_filtered` R9, `aggregate_financial_snapshot_actionable` R10.

- **HR-4** `_apply_expense_order_hub_filters` R12 — the search's account join ignores `accounts.is_deleted`. Verified: searching `Gone` finds the order of the deleted account "Gone Ltd". Intended: a soft-deleted account's name does not match (the order can still match on its number or category).
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-2715 (pattern `join-ignores-soft-deleted`). Rule: `_apply_expense_order_hub_filters` R12. Decided by Claude under the reviewer's delegation (2026-11-10): `open_by_account` still groups a live order under its soft-deleted account (it is money still open on that account and the name is this workspace's own) — intended, `aggregate_financial_snapshot_filtered` R10.

- **HR-6** `get_by_workspace` R6, `ExpenseOrderItemDAO.get_by_order` R2, `aggregate_financial_snapshot_filtered` R2 — see P2, P3, P4 below.

- **HR-8** `_apply_expense_order_hub_filters` R10 — already 🐞 BUG-745 (manager spec); restated here as the DAO rule.
**Answer:** bug — per HR-8 (house rule)
**Resolution:** reused BUG-745. Rule: `_apply_expense_order_hub_filters` R10.

Checked and **not** a new line here: **HR-4** — `expense_orders` and `expense_order_items` have no soft-delete column (voiding is a flag the hub filters on). **HR-5** — every filter is in SQL before `OFFSET`/`LIMIT`. **HR-7** — `GET /expense-orders/` has `limit` `ge=1, le=100`; `list_recent_for_hub` gets a fixed 10; `get_by_workspace` gets `limit=1` from its only caller. **HR-9** — this DAO writes no audit stamp (`updated_at` is the model's `onupdate`). **HR-10** — this DAO has no check-then-change; numbering is BUG-749. **HR-15** — every money figure is a SQL `SUM` of `Numeric(15, 2)` values or an exact `Decimal` subtraction; nothing is rounded here.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-10)

### P1. The year in an expense number comes from the server's local clock — 🐞 BUG-2710
**Background:** `get_next_number` builds `EXP-<year>-<n>` with the year from `datetime.now()`, the local time of the machine running the API; `created_at` and every other stamp is UTC. Ruled a bug for batch numbers (BUG-1334), help tickets (BUG-1441), sales orders (BUG-2440).
**What happens today:** Around New Year a server whose local year differs from UTC numbers the order with the local year.
**Example:** A server set to `Asia/Dhaka` (UTC+6). An order saved at 20:00 UTC on 31 December 2026 is numbered `EXP-2027-001` while its `created_at` says 2026.
**Rules affected:** `get_next_number` R1
**Answer:** bug — per BUG-1334 precedent: the year comes from `utcnow()`
**Resolution:** 🐞 BUG-2710 (pattern `local-clock-instead-of-utc`). Rule: `get_next_number` R1 (tagged).

### P2. "Expense orders of an invoice" has no final tie-breaker — 🐞 BUG-2711
**Background:** `get_by_workspace` orders by `created_at` newest first and nothing else. Its only caller, `AccountInvoiceService.confirm_invoice`, asks for `invoice_id=<id>, limit=1` to find the expense order to notify about when a payable invoice is confirmed. Two orders can share an invoice today (BUG-751).
**What happens today:** Two orders on one invoice with the same `created_at` → which one is notified is arbitrary.
**Example:** Orders 12 and 15 both point at invoice 40 and were created in the same microsecond by a template run; confirming invoice 40 notifies the approvers of either order, varying between runs.
**Rules affected:** `get_by_workspace` R6
**Answer:** bug — per HR-6 / BUG-978 precedent: `created_at` desc, then `id` desc
**Resolution:** 🐞 BUG-2711 (pattern `unordered-pagination`). Rule: `get_by_workspace` R6.

### P3. Lines of one order with the same line number have no order — 🐞 BUG-2713
**Background:** `get_by_order` orders lines by `line_number` only; `line_number` is not unique, and two concurrent `add_item` calls can give two lines one number (BUG-743). Same root cause as template lines (BUG-1211).
**What happens today:** Two lines numbered 3 come back in arbitrary order; the invoice built from the lines and the order page can show them swapped between calls.
**Example:** Lines "Electricity" and "Water" both have line number 3; the order page shows Electricity first on one load and Water first on the next.
**Rules affected:** `ExpenseOrderItemDAO.get_by_order` R2
**Answer:** bug — per BUG-1211 precedent: `line_number`, then `id` ascending
**Resolution:** 🐞 BUG-2713 (pattern `unordered-pagination`). Rule: `ExpenseOrderItemDAO.get_by_order` R2.

### P4. Dashboard category breakdown has unordered ties — 🐞 BUG-2712
**Background:** The hub's category breakdown is ordered by total value, largest first, and is cut after 6 entries. The manager spec fixed ties for the open-by-account widget (BUG-747) but its R1 for this widget did not.
**What happens today:** Two categories with the same total come in arbitrary order.
**Example:** Factory and Department each total 5,000.00; the dashboard shows Factory first on one load and Department first on the next.
**Rules affected:** `aggregate_financial_snapshot_filtered` R2
**Answer:** bug — per HR-6 / BUG-747 precedent: ties by category key ascending
**Resolution:** 🐞 BUG-2712 (pattern `unordered-pagination`). Rule: `aggregate_financial_snapshot_filtered` R2.

### Owner questions (answered by the owner, 2026-11-11)

### OQ-42. Hub money figures include voided expense orders — 🐞 BUG-2717
**Background:** Voiding an expense order keeps the row with `voided = true`. Every hub figure takes the filter `exclude_voided`; the API's default is `false`, and the web app's expense hub always sends `false` (the purchase order hub has a "show voided" toggle that is off by default).
**What happens today:** On the expense hub, voided orders are counted in "total value", in "open" count and value (a voided order is never completed), in "not invoiced", in the category breakdown, in the stage pipeline (as `draft`, or `invoiced` if still linked) and in open-by-account.
**Example:** Orders of 100.00 and 50.00, and a voided duplicate of 30.00. The hub shows total 180.00, open 3 orders / 180.00, Draft 3 / 180.00 (verified).
**Rules affected:** `aggregate_hub_stats` R1–R3a, `aggregate_financial_snapshot_filtered` R1, R5, R6a, R8
**Suggested answer:** bug — voided orders never count in the hub's money figures (stats, category breakdown, stage pipeline, open by account), whatever `exclude_voided` says; the list and its count still follow `exclude_voided`, and the web app gets a "show voided" toggle like the purchase order hub (frontend note).
**Answer:** owner, 2026-11-11: bug, suggested answer.
**Resolution:** 🐞 BUG-2717 (pattern `voided-record-not-excluded`, BUG-717 / BUG-2521). Voided orders are left out of every money figure whatever `exclude_voided` says: `total_value`, `open_count` / `open_value` (a voided order is not open), the category breakdown, the stage pipeline and open by account (their counts and values). `total_count` and `not_invoiced_count` keep following `exclude_voided`, like the list and `count_for_hub` — decided by Claude under the reviewer's delegation (2026-11-11): the split the owner chose for the PO hub (OQ-35), so both hubs read alike. The web app's "show voided" toggle is FU-3. Rules: `aggregate_hub_stats` R1, R2, R3a, `aggregate_financial_snapshot_filtered` R1, R5, R6a.

### OQ-43. The "unpaid pipeline" only shows draft invoices — 🐞 BUG-2718
**Background:** Completing an expense order confirms its invoice; payments can be recorded only against confirmed invoices. A draft invoice has `payment_status = 'unpaid'` by default and nothing paid.
**What happens today:** The pipeline counts orders that are not voided and **not completed**, with a linked invoice that is not voided and in `unpaid` / `partial` / `overdue`. So it lists only draft invoices, at their full amount, as "Unpaid"; "Partial" and "Overdue" stay empty except for invalid data. Once the order is completed — the moment the bill becomes payable — it leaves the pipeline even if nothing is paid.
**Example:** EO-1 is approved, its draft invoice is 100.00 → "Unpaid 100.00". It is completed (invoice confirmed), 40.00 is paid → the pipeline is empty, though 60.00 is still owed.
**Rules affected:** `aggregate_financial_snapshot_actionable` R8, R9
**Suggested answer:** bug — the pipeline lists not-voided orders, completed or not, whose linked invoice is **confirmed** with `payment_status` `unpaid` / `partial` / `overdue`, at `invoice_amount − paid_amount`; draft invoices are left out.
**Answer:** owner, 2026-11-11: bug, suggested answer.
**Resolution:** 🐞 BUG-2718 (pattern `outstanding-report-wrong-scope`). The pipeline lists not-voided orders, completed or not, whose invoice is **confirmed** (or `locked`, which the PO manager treats as confirmed — decided by Claude under the reviewer's delegation, 2026-11-11, as in OQ-37) with `payment_status` `unpaid` / `partial` / `overdue`, at `invoice_amount − paid_amount`; draft and voided invoices are left out. Rules: `aggregate_financial_snapshot_actionable` R8, R9.

### OQ-44. The due timeline drops completed orders and counts full totals — 🐞 BUG-2719
**Background:** Each expense order has its own `due_date` (when payment is due); its invoice has a separate `due_date`. The timeline buckets: overdue, due this week, due later this month, no due date.
**What happens today:** The timeline takes orders that are not voided and **not completed**, by the order's `due_date`, at the order's `total_amount`. A completed order (bill confirmed, maybe unpaid) is not in it; amounts already paid are not taken off.
**Example:** EO-7 for 500.00 was due yesterday, is completed and nothing is paid → not in "Overdue". EO-8 for 300.00, not completed, due tomorrow → "Due this week 300.00".
**Rules affected:** `aggregate_financial_snapshot_actionable` R4–R6
**Suggested answer:** bug — the timeline is "what we still have to pay": not-voided orders that are not fully paid (no invoice or a draft invoice → the order total; a confirmed invoice → `invoice_amount − paid_amount`, left out at 0), bucketed by the order's `due_date`.
**Answer:** owner, 2026-11-11: bug, suggested answer.
**Resolution:** 🐞 BUG-2719 (pattern `outstanding-report-wrong-scope`). The timeline counts not-voided orders, completed or not, that are not fully paid, at what is still to pay: no invoice, a draft invoice or a voided invoice → the order's `total_amount`; a confirmed / `locked` invoice → `invoice_amount − paid_amount`, and the order is left out when that is 0 or less or the invoice is `paid`. Bucketed by the **order's** `due_date`. Decided by Claude under the reviewer's delegation (2026-11-11): a voided invoice means "no bill" (the order is still owed in full, as before the invoice existed); `locked` as in OQ-43. Rules: `aggregate_financial_snapshot_actionable` R4, R5, R6.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever revisits the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Expense order manager spec** (`tests/unit/managers/expense_order_manager.spec.md`, PASS) and `app/models/expense_order.py` | `create_expense_order` R4: `expense_date` not given → `date.today()`, the server's local date (model default `default=date.today`). Per BUG-2542 / BUG-1334 it must be the UTC date → 🐞 **BUG-2716** (decided by Claude under the reviewer's delegation, 2026-11-10; not a rule of this DAO). The manager's R4 wording and its cases follow. | reading the model |
| FU-2 | **Expense order manager spec** | `list_expense_orders_for_hub` R9 / R11, `expense_order_financial_snapshot` R1, R4–R6, R10–R12 summarise rules detailed here; BUG-2712, BUG-2714, BUG-2715, BUG-2717, BUG-2718 and BUG-2719 change them. Wording follows when that spec is next opened; the manager's cases go through this DAO. | P4, HR-16, HR-4, OQs |
| FU-3 | **Web app** (`frontend/src/pages/newpages/orders/expenseOrderHubApiParams.ts`) | `exclude_voided: false` is hard-coded; the purchase order hub has a "show voided" toggle. Owner answered OQ-42 (2026-11-11): the hub gets a "show voided" toggle like the PO hub, off by default; the money figures leave voided orders out either way (BUG-2717). Frontend note only. | OQ-42 |

## Overview
`ExpenseOrderDAO` reads `expense_orders` for the expense-order hub (list, count, stats, recent orders, financial dashboard), finds an invoice's expense order, and makes the next expense number; `ExpenseOrderItemDAO` reads an order's lines. Callers: `ExpenseOrderManager` (every method except `get_by_workspace`, which only its dead `list_expense_orders` used), `AccountInvoiceService.confirm_invoice` (`get_by_workspace(invoice_id=…, limit=1)`), `AttachmentManager` (`get_by_id_and_workspace`, to check the order an attachment goes on). It never writes except through inherited `create` / `update`, never commits, takes no lock.

The hub's "stage" is derived, not stored: **complete** = `completed_at` set; else **invoiced** = `invoice_id` set; else **draft**. Voiding does not change the stage. The API's stage ids are `1` draft, `2` invoiced, `3` complete (constants `EO_STAGE_DRAFT/INVOICED/COMPLETE`, matched by the web app's filter options).

**Callables:** 18 specified · 4 not specified (+ inherited `BaseDAO` methods, base spec)
**Externals to mock:** `utcnow` in `app.dao.expense_order` (today for the due windows; after BUG-2710 also the number's year). `get_next_number` imports `datetime` **inside** the function, so today's year is changed by `mock.patch("datetime.datetime", Fake)` (the module attribute is read at call time), not by patching `app.dao.expense_order.datetime`.
**Integration-only behavior:** the race half of BUG-749 (two concurrent transactions).

**Model facts (table `expense_orders`, class `app.models.expense_order.ExpenseOrder`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `expense_number` | String(100) NOT NULL; unique per workspace (`uq_eo_workspace_number`) **and** globally (`ix_expense_orders_expense_number`, BUG-749) | — |
| `order_template_id` | FK `order_templates.id` SET NULL, nullable | `NULL` |
| `account_id` | FK `accounts.id` RESTRICT, nullable | `NULL` |
| `expense_category` | String(100) NOT NULL (`factory` / `department` / `other`, checked by the manager) | — |
| `cost_center_id` | Integer nullable, no FK | `NULL` |
| `expense_date` | Date NOT NULL | Python `date.today` (FU-1) |
| `due_date` | Date nullable | `NULL` |
| `subtotal`, `total_amount` | Numeric(15, 2) NOT NULL | `0` |
| `required_approvals` | Integer nullable | `NULL` |
| `invoice_id` | FK `account_invoices.id` SET NULL, nullable, not unique | `NULL` |
| `voided` | Boolean NOT NULL | `false` |
| `void_note`, `voided_at`, `voided_by` | nullable | `NULL` |
| `description` | Text nullable | `NULL` |
| `created_by` | NOT NULL FK `profiles.id` SET NULL | — |
| `created_at` | DateTime NOT NULL | Python `utcnow` |
| `updated_by`, `updated_at` (`onupdate=utcnow`), `items_updated_at`, `approved_by`, `approved_at`, `completed_by`, `completed_at` | nullable | `NULL` |
Table `expense_order_items` (`ExpenseOrderItem`): `workspace_id` NOT NULL, `expense_order_id` NOT NULL FK CASCADE, `line_number` Integer NOT NULL (not unique), `quantity` Numeric(15, 2) NOT NULL default 1, `unit_price`, `line_subtotal` Numeric(15, 2) nullable, `approved` Boolean default false, `description`, `unit`, `notes`. No soft-delete column on either table.
`account_invoices` fields read here: `workspace_id`, `invoice_status` (`draft` / `confirmed` / `voided`, NOT NULL, default `draft`), `payment_status` (`unpaid` / `partial` / `paid` / `overdue`, NOT NULL, default `unpaid`), `invoice_amount` NOT NULL, `paid_amount` NOT NULL default 0. `accounts`: `workspace_id`, `name`, `is_deleted`.

**Notes for the test designer:**
- `from app.dao.expense_order import expense_order_dao, expense_order_item_dao, _due_date_bucket, _due_window_dates, _category_label`. Parents: `make_workspace`, `make_profile` (`tests/unit/factories.py`); `Account(workspace_id, name)`; `AccountInvoice(workspace_id, account_id, invoice_type='payable', invoice_amount, invoice_date, invoice_status=…, payment_status=…, paid_amount=…)`. Insert orders directly as `ExpenseOrder(workspace_id, expense_number, expense_category, created_by, …)`.
- The global unique index (BUG-749) is in the test database: orders in two workspaces need distinct `expense_number`s, except in the BUG-749 card.
- The hub methods' filters are keyword arguments passed straight to `_apply_expense_order_hub_filters`; their DAO defaults are `exclude_complete=True`, `exclude_voided=True` (the service always passes both, default `False`). Pass both explicitly in cards that are not about them.
- The due windows depend on today: patch `app.dao.expense_order.utcnow` to a fixed time (e.g. Tuesday 2026-11-10 12:00 → week ends Sunday 2026-11-15, month ends 2026-11-30).
- `SAWarning: Coercing Subquery object into a select()` is printed by `count_for_hub`'s siblings; harmless.
- **A real account soft delete** (`AccountManager.delete_account`) writes `is_deleted = True`, `is_active = False`, `deleted_at = utcnow()`, `deleted_by = <user id>` (and a `financial_audit_logs` row, irrelevant here). Build deleted accounts with all four (G1).
- **Account names are not unique** (no unique index; duplicate names intended, account manager spec Q5): two accounts of one workspace may both be called "Acme" (G2).
- **A real void** of an expense order writes `voided = True`, `voided_at`, `voided_by`, `void_note`; the stage and `invoice_id` stay. The DAO reads only `voided`.

## Not specified
- `_expense_order_is_complete_clause` — the expression `completed_at IS NOT NULL`; its effect is stated in each rule that uses it ("completed").
- `_hub_base_query` — `SELECT expense_orders` plus `_apply_expense_order_hub_filters`; no logic of its own.
- `EO_*` constants — data, stated where used.
- `expense_order_dao`, `expense_order_item_dao` — module-level singletons.
- Inherited `BaseDAO` methods (`create`, `update`, `get`, …) — base spec.

---

## `_expense_order_stage_key_expr()`
**Shape:** helper
**Persistence:** pure (SQL expression)
**Visibility:** internal (used by: `aggregate_financial_snapshot_filtered`)

**Purpose:** The derived stage of an order, as SQL.

**Rules:**
- **R1.** `complete` when `completed_at` is set (even if `invoice_id` is null or the order is voided); else `invoiced` when `invoice_id` is set; else `draft`.

**Errors:** none. **Side effects:** none.

---

## `_category_label(slug)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** internal (used by: `aggregate_financial_snapshot_filtered`)

**Rules:**
- **R1.** `factory` → `Factory`, `department` → `Department`, `other` → `Other`.
- **R2.** Any other slug → underscores replaced by spaces, then title-cased: `office_rent` → `Office Rent`, `utilities` → `Utilities`, `""` → `""`. Case-sensitive lookup: `Factory` → `Factory` (by title-casing), `FACTORY` → `Factory`.

**Errors:** `AttributeError` for a non-string (no caller passes one; the column is NOT NULL). **Side effects:** none.

---

## `_due_date_bucket(due, *, today, end_of_week, end_of_month)`
**Shape:** compute
**Persistence:** pure
**Visibility:** internal (used by: `aggregate_financial_snapshot_actionable`)

**Rules (checked in this order):**
- **R1.** `due` is `None` → `no_due_date`.
- **R2.** `due < today` → `overdue` (yesterday is overdue; today is not).
- **R3.** `due <= end_of_week` → `due_this_week` (today and the week's last day included).
- **R4.** `due <= end_of_month` → `due_later_this_month`.
- **R5.** Otherwise → `beyond_scope`. Because R3 comes before R4, a `end_of_week` in the next month puts next month's first days in `due_this_week`.
- **R6.** Keyword-only `today`, `end_of_week`, `end_of_month`; positional use raises `TypeError`.

**Errors:** none of its own. **Side effects:** none.

---

## `_due_window_dates()`
**Shape:** compute
**Persistence:** pure (reads the clock)
**Visibility:** internal (used by: `aggregate_financial_snapshot_actionable`)

**Rules:**
- **R1.** `today` = the UTC date (`utcnow().date()`). Decided intended by Claude under the reviewer's delegation (2026-11-10): UTC is the system's clock (BUG-1334 family).
- **R2.** `end_of_week` = the coming Sunday (Monday-based week); when today is Sunday, today. Example: Tuesday 2026-11-10 → 2026-11-15; Sunday 2026-11-15 → 2026-11-15.
- **R3.** `end_of_month` = the last day of today's month (28/29 February respected: 2028-02-10 → 2028-02-29).
- **R4.** Returns the tuple `(today, end_of_week, end_of_month)`.

**Errors:** none. **Side effects:** none.

---

## `_apply_expense_order_stage_filter(query, status_ids)`
**Shape:** helper
**Persistence:** pure (builds SQL)
**Visibility:** internal (used by: `_apply_expense_order_hub_filters`)

**Rules:**
- **R1.** Each id adds one alternative; an order passes when it matches **any**: `1` → not completed and no invoice; `2` → not completed and invoice linked; `3` → completed. Voided is not part of the stage.
- **R2.** Ids other than 1, 2, 3 are ignored; a list with only unknown ids (e.g. `[9]`) applies **no** stage filter (verified: every order returned). Decided intended by Claude under the reviewer's delegation (2026-11-10): non-money validation, same as the approved manager rule R5; the API's query list is the web app's fixed options.
- **R3.** Repeated ids behave like one (`[1, 1]` = `[1]`).

**Errors:** none. **Side effects:** none.

---

## `_apply_expense_order_hub_filters(query, *, workspace_id, expense_category=None, account_id=None, invoice_id=None, date_from=None, date_to=None, status_ids=None, invoice_filter=None, search=None, exclude_complete=True, exclude_voided=True)`
**Shape:** helper
**Persistence:** pure (builds SQL)
**Visibility:** internal (used by every hub method through `_hub_base_query`)

**Purpose:** The hub's filter set; every hub method below means "the orders passing these filters".

**Rules (all combined with AND, all in SQL before any paging):**
- **R1.** Only orders whose own `workspace_id` is the given one; another workspace's orders never pass.
- **R2.** `expense_category` truthy → exact, case-sensitive match; `None` or `""` → no filter.
- **R3.** `account_id` not `None` → exact match (`0` keeps nothing, since no order has account 0); `None` → no filter.
- **R4.** `invoice_id` not `None` → exact match; `None` → no filter.
- **R5.** `date_from` → `expense_date >= date_from`; `date_to` → `expense_date <= date_to` (both ends included).
- **R6.** `status_ids` non-empty → stage filter per `_apply_expense_order_stage_filter`; `None` / `[]` → no filter.
- **R7.** `invoice_filter == 'invoiced'` → invoice linked; `'not_invoiced'` → no invoice; any other value (`'all'`, `''`, `None`, `'Invoiced'`) → no filter.
- **R8.** `exclude_voided` true → voided orders left out; false → included.
- **R9.** `exclude_complete` true → completed orders left out; false → included. (Combined with `status_ids=[3]` and `exclude_complete=True`, nothing passes.)
- **R10.** `search`: `None`, `""` or whitespace only → no filter. Otherwise the trimmed text matches, case-insensitively as a substring, the order's `expense_number`, its `expense_category`, or its account's `name`; it also matches every order of a known category whose label (`Factory` / `Department` / `Other`) contains the text case-insensitively (e.g. `o` → factory and other; `t` → all three). Orders without an account still match on number or category. [BUG-745] `%`, `_` and `\` in the text match literally. *(Today: unescaped — verified `_` matches every order.)*
- **R11.** [BUG-2714] (HR-16) An account of **another workspace** linked to the order is treated as not found: its name does not match. *(Today: the account join compares ids only — verified `Foreign` finds the order linked to workspace B's "Foreign Co".)*
- **R12.** [BUG-2715] (HR-4) A **soft-deleted** account's name (real delete: `is_deleted = True`, `is_active = False`, `deleted_at`, `deleted_by` set) does not match. *(Today: verified `Gone` finds the order of deleted "Gone Ltd".)*
- **R13.** Unknown keyword → `TypeError` (raised when a hub method passes it on).

**Errors:** `TypeError` for an unknown keyword. **Side effects:** none.

---

## `ExpenseOrderDAO.get_by_workspace(db, *, workspace_id, expense_category=None, account_id=None, invoice_id=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `AccountInvoiceService.confirm_invoice` with `invoice_id`, `limit=1`; `ExpenseOrderManager.list_expense_orders`, dead per the manager spec Q24)

**Purpose:** A workspace's orders, optionally of one category, account or invoice.

**Rules:**
- **R1.** Only orders of this workspace; voided and completed included.
- **R2.** `expense_category` truthy → exact match; `None` / `""` → no filter.
- **R3.** `account_id` truthy → exact match; `None` **and `0`** → no filter (verified: `account_id=0` returns every order). Unlike the hub's R3; no caller passes `account_id`, decided intended by Claude under the reviewer's delegation (2026-11-10), no bug.
- **R4.** `invoice_id` not `None` → exact match (`0` keeps nothing).
- **R5.** `skip` / `limit` applied after the filters (defaults 0 / 100).
- **R6.** [BUG-2711] Ordered by `created_at` newest first, then `id` descending. *(Today: `created_at` only; equal `created_at` → arbitrary.)*
- **R7.** Positional arguments after `db` raise `TypeError`.

**Errors:** none of its own. **Side effects:** none.

---

## `ExpenseOrderDAO.list_for_hub(db, *, workspace_id, skip=0, limit=50, **filters)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderManager.list_expense_orders_for_hub` ← `GET /expense-orders/`)

**Rules:**
- **R1.** The orders passing the filters (`_apply_expense_order_hub_filters` R1–R13; DAO defaults `exclude_complete=True`, `exclude_voided=True`).
- **R2.** Ordered by `expense_date` desc, then `created_at` desc, then `id` desc.
- **R3.** Then `skip` / `limit` (defaults 0 / 50); `[]` past the end.

**Errors:** `TypeError` for an unknown filter. **Side effects:** none.

---

## `ExpenseOrderDAO.count_for_hub(db, *, workspace_id, **filters)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderManager.count_expense_orders_for_hub`)

**Rules:**
- **R1.** The number of distinct orders passing the filters (same defaults as `list_for_hub`), with no paging; an `int`, `0` when none.

**Errors:** `TypeError` for an unknown filter. **Side effects:** none.

---

## `ExpenseOrderDAO.list_recent_for_hub(db, *, workspace_id, limit=10, **filters)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderManager.list_expense_orders_recent_for_hub`, limit 10)

**Rules:**
- **R1.** At most `limit` orders passing the filters.
- **R2.** [BUG-746] Ordered by `coalesce(updated_at, created_at)` descending, then `id` descending. *(Today: `updated_at` desc, `created_at` desc, no `id`; Postgres puts `NULL` first when descending, so never-edited orders come before recently edited ones.)*

**Errors:** `TypeError` for an unknown filter. **Side effects:** none.

---

## `ExpenseOrderDAO.aggregate_hub_stats(db, *, workspace_id, **filters)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderManager.expense_order_hub_stats` ← `GET /expense-orders/hub-stats`)

**Returns:** `(total_count: int, total_value: Decimal, open_count: int, open_value: Decimal, not_invoiced_count: int)`.

**Rules (over the orders passing the filters):**
- **R1.** `total_count` = their number (voided orders included when `exclude_voided` is false). [BUG-2717] `total_value` = the sum of `total_amount` of those that are **not voided**. *(Today: voided orders' totals are added when `exclude_voided` is false — verified 100 + 50 + voided 30 = 180.00.)*
- **R2.** [BUG-2717] `open_count` / `open_value` = count / sum of `total_amount` of those **not completed and not voided**. *(Today: a voided order counts as open.)*
- **R3.** `not_invoiced_count` = the number with no invoice; voided orders included when `exclude_voided` is false (OQ-42 Resolution).
- **R3a.** [BUG-2717] With `exclude_voided=True` every figure is as today (no voided order passes); the fix changes only `total_value`, `open_count` and `open_value`, and only when voided orders pass the filters.
- **R4.** None passing → `(0, Decimal('0'), 0, Decimal('0'), 0)`; values are exact sums of 2-decimal amounts, negative and zero totals included as they are.

**Errors:** `TypeError` for an unknown filter. **Side effects:** none.

---

## `ExpenseOrderDAO._filtered_orders_query(db, *, workspace_id, **filters)`
**Shape:** helper
**Persistence:** reads (builds a query)
**Visibility:** internal (used by: `aggregate_financial_snapshot_filtered`)

**Rules:**
- **R1.** A query over exactly the orders passing the filters (same defaults as `list_for_hub`), each once, with no join left on it (so grouping by account later does not see the search's account join).

**Errors:** `TypeError` for an unknown filter (raised when executed by the caller). **Side effects:** none.

---

## `ExpenseOrderDAO.aggregate_financial_snapshot_filtered(db, *, workspace_id, **filters)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderManager.expense_order_financial_snapshot`)

**Returns:** `{"category_breakdown": [...], "stage_pipeline": [...], "open_by_account": [...]}`.

**Rules — category breakdown (over the orders passing the filters):**
- **R1.** One entry per category present: `{key: slug, label: _category_label(slug), count, total_value: Decimal}`. [BUG-2717] Voided orders are left out (count and value) whatever `exclude_voided` says; a category with only voided orders has no entry. *(Today: included when `exclude_voided` is false.)*
- **R2.** [BUG-2712] Ordered by `total_value` descending, ties by `key` ascending. *(Today: ties arbitrary.)*
- **R3.** The first 6 entries are kept; entries 7 onward are added together into one trailing `{key: "other", label: "Other", count, total_value}`. Unreachable through the API (the manager allows only 3 categories); the merged entry would then sit beside a real `other` entry with the same key. Decided by Claude under the reviewer's delegation (2026-11-10): no bug, unreachable.
- **R4.** No orders passing → `[]`.

**Rules — stage pipeline:**
- **R5.** Always three entries in this order: `draft` "Draft", `invoiced` "Invoiced", `complete` "Complete", each `{key, label, count, total_value}`; a stage with no orders gives `count 0`, `total_value Decimal('0')`. Stage per `_expense_order_stage_key_expr` R1. [BUG-2717] Voided orders are left out of every stage. *(Today: a voided order shows as draft / invoiced / complete when `exclude_voided` is false.)*

**Rules — open by account (orders passing the filters that are not completed and have an account):**
- **R6.** Grouped per account: `{account_id, account_name, count, total_value}`.
- **R7.** Orders without an account are left out.
- **R6a.** [BUG-2717] Voided orders are left out of open by account whatever `exclude_voided` says. *(Today: counted when `exclude_voided` is false.)*
- **R8.** [BUG-747] At most 5 entries, by `total_value` descending, ties by account name case-insensitive ascending, then account id ascending. *(Today: ties arbitrary.)* The id tie-break is reachable: two accounts of one workspace may share a name (account manager spec Q5, intended; G2).
- **R9.** [BUG-2714] (HR-16) An order whose account belongs to **another workspace** is left out (as if it had no account); no other workspace's id or name appears. *(Today: verified `Foreign Co` with workspace B's account id listed.)*
- **R10.** An order of a **soft-deleted** account of this workspace (as a real delete leaves it: `is_deleted = True`, `is_active = False`, `deleted_at`, `deleted_by` set) still counts under that account and its name (decided intended, HR-4 line above).

**Errors:** `TypeError` for an unknown filter. **Side effects:** none.

---

## `ExpenseOrderDAO.aggregate_financial_snapshot_actionable(db, *, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderManager.expense_order_financial_snapshot`)

**Purpose:** Due timeline and unpaid pipeline; takes **no** filters (always the whole workspace).

**Returns:** `{"due_timeline": [...], "unpaid_pipeline": [...]}`.

**Rules — due timeline:**
- **R1.** Always four buckets in this order: `overdue` "Overdue", `due_this_week` "Due this week", `due_later_this_month` "Due later this month", `no_due_date` "No due date"; each `{key, label, count, total_value: Decimal, samples: []}` even when empty.
- **R2.** Bucket of an order per `_due_date_bucket` with the dates of `_due_window_dates`; an order due after the current month (or after the week's end when that is later) is in no bucket.
- **R3.** Orders of other workspaces never count.
- **R4.** [BUG-2719] The orders considered are those **not voided** (completed or not) that are **not fully paid**: an order with no invoice, a draft invoice or a voided invoice always counts; an order with a confirmed or `locked` invoice counts while `payment_status` is not `paid` and `invoice_amount − paid_amount` is above 0. *(Today: not voided and **not completed**, whatever is paid — a completed order is never in the timeline.)*
- **R5.** [BUG-2719] `count` +1 per order; `total_value` adds what is still to pay: the order's `total_amount` (no, draft or voided invoice), or `invoice_amount − paid_amount` (confirmed / `locked` invoice). *(Today: always the order's `total_amount`.)* Orders with no invoice add exactly `total_amount` today and after the fix.
- **R6.** `samples`: the first 3 orders of the bucket as `{id, order_number: expense_number, total_value: total_amount, sublabel: due date as ISO text, or None}`, taken by `due_date` ascending (no due date last), then `expense_number` ascending as text (unique per workspace, so stable; `EXP-2026-1000` sorts before `EXP-2026-999` — decided intended by Claude under the reviewer's delegation (2026-11-10), sample order only). [BUG-2719] The orders are those of R4, and a sample's `total_value` is the amount R5 counts. *(Today: open orders only, at `total_amount`.)*

**Rules — unpaid pipeline:**
- **R7.** Always three buckets in this order: `unpaid` "Unpaid", `partial` "Partial", `overdue` "Overdue"; each `{key, label, count, outstanding_value: Decimal, samples: []}` even when empty.
- **R8.** [BUG-2718] An order counts when it is of this workspace, not voided (completed or not), and has a linked invoice whose `invoice_status` is `confirmed` or `locked` and whose `payment_status` is `unpaid`, `partial` or `overdue`; it goes to the bucket of that status. A draft or voided invoice, or `payment_status` `paid`, puts the order in no bucket. *(Today: only orders **not completed**, with any invoice that is not voided — a draft invoice counts as `unpaid`, verified 100.00; a completed order is never listed.)*
- **R9.** `outstanding_value` adds `invoice_amount − paid_amount` (exact; an overpaid invoice adds a negative amount). Unchanged by BUG-2718, which only changes which orders R8 lets in.
- **R10.** [BUG-2714] (HR-16) An order whose invoice belongs to **another workspace** is left out. *(Today: the join compares ids only — verified workspace B's confirmed invoice put 50.00 in A's "Partial".)*
- **R11.** [BUG-748] `samples`: the first 3 orders of the bucket, `{id, order_number, total_value: outstanding, sublabel: payment_status}`, by outstanding descending, ties by order `id` ascending. *(Today: ties arbitrary.)*
- **R12.** Two orders sharing one invoice (possible today, BUG-751) each count with the invoice's full outstanding.

**Errors:** none of its own. **Side effects:** none.

---

## `ExpenseOrderDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderManager`, `AttachmentManager`)

**Rules:**
- **R1.** Returns the order with that id when it belongs to this workspace (voided and completed included); `None` for an unknown id or another workspace's order.
- **R2.** Keyword-only; positional use raises `TypeError`.

**Errors:** none. **Side effects:** none.

---

## `ExpenseOrderDAO.get_next_number(db, *, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderManager.create_expense_order`)

**Purpose:** The next expense number of a workspace for the current year.

**Rules:**
- **R1.** [BUG-2710] The prefix is `EXP-<year>-` with the current **UTC** year (`utcnow().year`). *(Today: `datetime.now().year`, the server's local year.)*
- **R2.** No number of this workspace with the prefix → `EXP-<year>-001`. Other workspaces' numbers and other years' numbers do not count. The prefix match is case-sensitive (`exp-2026-005` is not counted; sales order spec G3).
- **R3.** [BUG-749] Otherwise the numeric maximum of the year's numeric suffixes + 1, zero-padded to at least 3 digits: `…-002` → `…-003`; `…-999` → `…-1000`; `…-1000` and `…-999` → `…-1001`. Suffixes that are not digits are ignored (`EXP-2026-abc` alone → `…-001`; with `…-004` → `…-005`). *(Today: the "highest" is the text maximum — `…-999` beats `…-1000`, so after 1000 it returns `…-1000` again; a non-numeric highest suffix (`abc` sorts above digits) returns `…-001` — verified — even when `…-001` exists. Both then fail at insert.)*
- **R4.** [BUG-749] Race-safety and per-workspace uniqueness are the create's (manager `create_expense_order` R6): this method only reads, takes no lock.
- **R4a.** [BUG-749] A number is unique **per workspace** only: an order stored (inherited `create`) in workspace B with `EXP-2026-001`, while workspace A already has `EXP-2026-001`, is accepted; the same number twice in one workspace fails on `uq_eo_workspace_number` (`IntegrityError`, 23505). *(Today: B's order fails on the global index `ix_expense_orders_expense_number`, 23505 — verified.)* The fix is BUG-749's migration (drop the global unique index, keep a plain index). Decided by Claude under the reviewer's delegation (2026-11-11), G3: stated here because the number this method returns for B (R2) is only usable once this holds.
- **R5.** Keyword-only; positional use raises `TypeError`.

**Errors:** none of its own. **Side effects:** none.

---

## `ExpenseOrderItemDAO.get_by_order(db, *, expense_order_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderManager` — readiness checks, totals, `get_items`, line numbering)

**Rules:**
- **R1.** All lines with that `expense_order_id` **and** that `workspace_id`; a line stored with another `workspace_id` is left out (verified); `[]` when none or for an unknown order. No paging.
- **R2.** [BUG-2713] Ordered by `line_number` ascending, then `id` ascending. *(Today: `line_number` only.)*

**Errors:** none. **Side effects:** none.

---

## `ExpenseOrderItemDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderManager.update_item`, `remove_item`)

**Rules:**
- **R1.** Returns the line with that id when its own `workspace_id` matches; `None` otherwise (the parent order's workspace is not looked at).
- **R2.** Keyword-only; positional use raises `TypeError`.

**Errors:** none. **Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 60–64 | CASE complete / invoiced / draft | `_expense_order_stage_key_expr` R1 |
| 68 | known slug or title-case fallback | `_category_label` R1, R2 |
| 72 | `due is None` | `_due_date_bucket` R1 |
| 74 | `due < today` | `_due_date_bucket` R2 |
| 76 | `due <= end_of_week` | `_due_date_bucket` R3 |
| 78 | `due <= end_of_month` | `_due_date_bucket` R4 |
| 80 | fall-through `beyond_scope` | `_due_date_bucket` R5 |
| 71 | keyword-only `*` | `_due_date_bucket` R6 |
| 84 | `utcnow().date()` | `_due_window_dates` R1 |
| 85 | days to Sunday | `_due_window_dates` R2 |
| 86–87 | month's last day | `_due_window_dates` R3 |
| 93 | loop over ids (empty / one / many) | `_apply_expense_order_stage_filter` R1, R3 |
| 94, 101, 108 | id 1 / 2 / 3 | `_apply_expense_order_stage_filter` R1 |
| 108 (no else) | unknown id ignored | `_apply_expense_order_stage_filter` R2 |
| 110 | any clause collected | `_apply_expense_order_stage_filter` R2 |
| 130 | workspace filter | `_apply_expense_order_hub_filters` R1 |
| 132 | `expense_category` truthy | `_apply_expense_order_hub_filters` R2 |
| 134 | `account_id is not None` | `_apply_expense_order_hub_filters` R3 |
| 136 | `invoice_id is not None` | `_apply_expense_order_hub_filters` R4 |
| 138, 140 | `date_from` / `date_to` | `_apply_expense_order_hub_filters` R5 |
| 142 | `status_ids` truthy | `_apply_expense_order_hub_filters` R6 |
| 145, 147 | `invoice_filter` invoiced / not_invoiced / other | `_apply_expense_order_hub_filters` R7 |
| 150 | `exclude_voided` | `_apply_expense_order_hub_filters` R8 |
| 153 | `exclude_complete` | `_apply_expense_order_hub_filters` R9 |
| 156 | `search` truthy and not blank | `_apply_expense_order_hub_filters` R10 |
| 160–166 | label contains term (the `startswith` half is implied by `in`) | `_apply_expense_order_hub_filters` R10 |
| 167 | account outer join by id only, no deleted check | `_apply_expense_order_hub_filters` R11, R12 |
| 169–171 | unescaped `ILIKE` | `_apply_expense_order_hub_filters` R10 |
| 181 | `**filters` passed on | `_apply_expense_order_hub_filters` R13 |
| 197 | `expense_category` truthy | `get_by_workspace` R2 |
| 199 | `account_id` truthy (0 falsy) | `get_by_workspace` R3 |
| 201 | `invoice_id is not None` | `get_by_workspace` R4 |
| 203 | order, offset, limit | `get_by_workspace` R5, R6 |
| 214–223 | hub filters, order, paging | `list_for_hub` R1–R3 |
| 227–233 | distinct ids, count, `or 0` | `count_for_hub` R1 |
| 243–247 | hub filters, order, limit | `list_recent_for_hub` R1, R2 |
| 261–268 | open = not completed (no voided check) | `aggregate_hub_stats` R2, R3a |
| 269 | not invoiced | `aggregate_hub_stats` R3 |
| 273–285 | coalesce sums, `or 0` | `aggregate_hub_stats` R1, R4 |
| 290–296 | id subquery | `_filtered_orders_query` R1 |
| 304–313 | group by category, order by sum | `aggregate_financial_snapshot_filtered` R1, R2 |
| 317–330 | `idx < 6` keep / merge | `aggregate_financial_snapshot_filtered` R3 |
| 331 | `other_count > 0` | `aggregate_financial_snapshot_filtered` R3, R4 |
| 341–362 | stage groups, three fixed entries, missing → 0 | `aggregate_financial_snapshot_filtered` R5 |
| 364 | not completed (no voided check) | `aggregate_financial_snapshot_filtered` R6, R6a |
| 366 | inner join account by id | `aggregate_financial_snapshot_filtered` R7, R9, R10 |
| 374–375 | order by sum, limit 5 | `aggregate_financial_snapshot_filtered` R8 |
| 386 | `account_id is not None` (always true after the inner join) | `aggregate_financial_snapshot_filtered` R7 |
| 401–410 | open orders, order by due, number | `aggregate_financial_snapshot_actionable` R3, R4, R6 |
| 412–415 | four empty buckets | `aggregate_financial_snapshot_actionable` R1 |
| 416 | loop over orders (none / many) | `aggregate_financial_snapshot_actionable` R1, R5 |
| 420 | `beyond_scope` skipped | `aggregate_financial_snapshot_actionable` R2 |
| 424 | `total_amount or 0` | `aggregate_financial_snapshot_actionable` R5 |
| 425 | `len(samples) < 3` | `aggregate_financial_snapshot_actionable` R6 |
| 426 | due date or `None` sublabel | `aggregate_financial_snapshot_actionable` R6 |
| 438–451 | invoice join by id, status filters, order by outstanding | `aggregate_financial_snapshot_actionable` R8, R10, R11 |
| 465 | status not a bucket (unreachable after the `IN`) | `aggregate_financial_snapshot_actionable` R8 |
| 467–469 | outstanding, `or 0` | `aggregate_financial_snapshot_actionable` R9 |
| 473 | `len(samples) < 3` | `aggregate_financial_snapshot_actionable` R11 |
| 493–497 | id + workspace, `.first()` | `ExpenseOrderDAO.get_by_id_and_workspace` R1 |
| 502 | `datetime.now().year` | `get_next_number` R1 |
| 505–512 | workspace + prefix `LIKE`, text max | `get_next_number` R2, R3 |
| 513 | `last` found | `get_next_number` R2, R3 |
| 515 | `int(suffix) + 1`, `:03d` | `get_next_number` R3 |
| 516 | `ValueError` / `IndexError` → fall through | `get_next_number` R3 |
| 518 | `…001` | `get_next_number` R2 |
| 527–535 | order + workspace, order by line number | `get_by_order` R1, R2 |
| 540–544 | id + workspace | `ExpenseOrderItemDAO.get_by_id_and_workspace` R1 |

## Gap log
- G1 (`expense_order.cases.md` gap 1) — Fact — a real account soft delete (`AccountManager.delete_account`) writes `is_deleted = True`, `is_active = False`, `deleted_at = utcnow()`, `deleted_by`; added to the Notes for the test designer and to `_apply_expense_order_hub_filters` R12 and `aggregate_financial_snapshot_filtered` R10. A real void's columns were added to the Notes too.
- G2 (gap 2) — Fact, decided under delegation (2026-11-11) — account names are not unique (no unique index; duplicates intended, account manager spec Q5), so two accounts may share a name and the account-id tie-break of `aggregate_financial_snapshot_filtered` R8 is reachable; added to R8 and the Notes.
- G3 (gap 3) — Contradiction, resolved by a new rule — `get_next_number` R4a [BUG-749]: the same number in another workspace is accepted; only a repeat within one workspace fails. Decided by Claude under the reviewer's delegation (2026-11-11); kept in this spec (NX-27 stays here) because it is what makes R2's per-workspace number usable.
- G4 (gap 4) — Intent, now answered — OQ-43 / OQ-44 answered by the owner with the suggested answers (2026-11-11): `aggregate_financial_snapshot_actionable` R4–R6 tagged BUG-2719, R8 tagged BUG-2718. The UP and SA cards on confirmed invoices of open orders and on no-invoice orders hold before and after the fix; the OQ43 / OQ44 cards must now assert the intended rule (expected to fail until fixed). OQ-42 → BUG-2717 likewise (`aggregate_hub_stats` R1, R2, R3a; `aggregate_financial_snapshot_filtered` R1, R5, R6a).
