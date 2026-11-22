# Spec — `app/dao/sales_order.py`

> **Status:** APPROVED (2026-11-10; nothing open — OQ-26 answered by the owner: BUG-2404, a rule of the sales schema / service, FU-1 (a))
> **Source commit:** e48a092

> **Review round 2026-11-09.** No owner answer in this round. **Delegated:** P1 and Q1 decided by Claude under the reviewer's delegation (2026-11-09). None of them is the owner's own answer. The house-rule line stands. The approved sales manager spec (`tests/unit/managers/sales_manager.spec.md`) already decided numbering (BUG-726, BUG-727), cross-workspace links (BUG-728) and the status default (BUG-1019); those are reused here with their IDs, not re-asked.

> **Review round 2026-11-10 (apply-review + fill-gaps).** **Owner:** OQ-26 — suggested answer: `total_amount`, `is_fully_delivered` and `is_invoiced` are system-only, and an edit that sends them gets 422 (owner, 2026-11-10) → 🐞 BUG-2404, logged against `app/schemas/sales_order.py` / `app/services/sales_service.py`; not a rule of this DAO (the DAO's inherited `update` stores what it is given), recorded as FU-1 (a) for the sales service spec, as BUG-1019 was. **Delegated (2026-11-10):** number-prefix case — the prefix match is case-sensitive and that is intended (G3). **Gaps:** both gaps of `sales_order.cases.md` closed from the code (Gap log at the end).

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated (`get_by_id_and_workspace`, `get_by_workspace`, `update` are inherited and used by `SalesManager`, `SalesService`, `AttachmentManager`).
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Raw lookups stay raw (HR-4 scope; this table has no soft delete anyway). HR-15: money rounds half away from zero. HR-16: a row linking to another workspace's row is invalid data; this DAO stores the links it is given, and refusing foreign ones is the manager's job (BUG-728, BUG-1019).
>
> **Verified by running** (throwaway scripts `schema.py`, `v1.py` with my own harness `hc.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omd\C\`, each transaction rolled back against `marker_test`, private `COVERAGE_FILE`; nothing committed): the table's columns, defaults, constraints and indexes; numbering in an empty workspace, after one, two and three orders, in a second workspace (`SO-2026-001` again), year `1` (`SO-1-001`), year `202` (does not count `SO-2026-…`), a non-numeric suffix counted (`SO-2026-abc`), a patched `datetime.now()` (1 January 2031 → `SO-2031-001`); `create_with_user` with `total_amount` omitted (stored `0.00`), `1.005` (`1.01`), `-1.005` (`-1.01`); the second workspace's first order failing on the global unique index (`IntegrityError` 23505); unknown status and unknown user (23503); positional arguments (`TypeError`); `get_by_invoice_id` with no linked order, another workspace, and two orders on one invoice under a forced sequential scan before and after an update (the row returned changed from the lower to the higher `id`); the SQL (`WHERE invoice_id = … AND workspace_id = … LIMIT 1`, no `ORDER BY`). **Read, not run:** `SalesManager`, `SalesService`, `AttachmentManager`, `POST /sales-orders/`, `PUT /sales-orders/{id}/`, the web app's order panel (`SalesOrderDetailPanel.tsx`). **Not run:** anything over HTTP; two concurrent transactions.

## Review
> All answered; applied 2026-11-09.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | The year in an order number comes from the server's local clock | bug — from UTC (BUG-2440) | Claude, delegated |
| Q1 | "Orders by factory" and "orders by status" have no caller anywhere | remove | Claude, delegated |

Decided by house rules: with two orders on one invoice, the one found is arbitrary (BUG-2441).
Already decided elsewhere and reused: numbers unique across all workspaces instead of per workspace (BUG-726), count-then-insert numbering race (BUG-727), customer / factory not checked for workspace (BUG-728), fixed status id 10 and `invoice_id` client-writable (BUG-1019).
Answered by the owner (2026-11-10), not a rule here: **OQ-26** — `PUT /sales-orders/{id}/` lets a client set `total_amount`, `is_fully_delivered` and `is_invoiced` directly → bug, system-only, an edit that sends them gets 422 (🐞 BUG-2404, sales schema / service; FU-1 (a)).

### House-rule violations — applied automatically

- **HR-6** `get_by_invoice_id` R3 — `.first()` with no `ORDER BY`. Nothing stops two orders pointing at one invoice (no unique constraint on `invoice_id`; `PUT /sales-orders/{id}/` accepts any `invoice_id` today, BUG-1019). Verified under a forced sequential scan: with orders 1047078 and 1047079 on one invoice the lookup returned 1047078, and after an update of 1047078 it returned 1047079. Through `SalesManager.sync_so_for_linked_invoice` (every invoice payment) the other order's `paid` flag is then the one kept in step. Intended: the lowest `id` (BUG-978 precedent).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-2441 (pattern `unordered-pagination`). Once BUG-1019 is fixed only the system links invoices, one new invoice per order (`SalesService` creates it), so new pairs cannot arise; the rule keeps the lookup deterministic for rows already stored. Rules: `get_by_invoice_id` R3.

Checked and **not** a new line here: **HR-4** — `sales_orders` has no soft-delete column. **HR-5, HR-7, HR-8** — no own list with paging, no `LIKE` on user text (the numbering `LIKE` prefix is built from an integer year). **HR-9** — this DAO writes no audit stamp on update (inherited `update`; `updated_at` is the model's `onupdate`). **HR-10** — numbering is BUG-727; the DAO's lookups are reads with no check-then-change. **HR-15** — `total_amount` is `Numeric(15, 2)`; Postgres rounds half away from zero (verified `1.005` → `1.01`, `-1.005` → `-1.01`), which is the house rule. **HR-16** — reads filter on the row's own `workspace_id`; writes store what the caller passes (BUG-728, BUG-1019 are the caller fixes).

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-09)

### P1. The year in an order number comes from the server's local clock — 🐞 BUG-2440
**Background:** `create_with_user` numbers the order `SO-<year>-<n>`, taking the year from `datetime.now()`, the local time of the machine running the API; `created_at` and everything else is UTC. The same was ruled a bug for batch numbers (BUG-1334) and help tickets (BUG-1441).
**What happens today:** Around New Year, a server whose local clock is in another year than UTC numbers the order with the local year. (Verified with a patched `datetime.now()` returning 1 January 2031 00:30: `SO-2031-001`.)
**Example:** A server set to `Asia/Dhaka` (UTC+6). An order saved at 20:00 UTC on 31 December 2026 is numbered `SO-2027-001`, while its `created_at` says 2026; the 2027 count then starts one early.
**Rules affected:** `create_with_user` R2
**Answer:** bug — per BUG-1334 precedent: the year comes from `utcnow()`
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-09): 🐞 BUG-2440 (pattern `local-clock-instead-of-utc`; one bug for this DAO and `app/dao/sales_delivery.py`, same line in each). The approved sales manager spec says "the server's current local year" in `create_sales_order_with_items` R5 and `create_delivery_with_items` R4; FU-2 asks for that wording to follow. Rules: `create_with_user` R2 (tagged).

### New questions

### Q1. "Orders by factory" and "orders by status" have no caller — 🗑️ removed
**Background:** `get_by_factory` and `get_by_status` list a workspace's orders by factory or by `current_status_id`. `current_status_id` is vestigial: the model says the sales flow no longer reads or writes it (it is always the fixed default, BUG-1019).
**What happens today:** Nothing in `app/`, `tests/` or `scripts/` calls either method; no endpoint reaches them. Both page with no `ORDER BY`.
**Example:** Deleting both changes no response of the API.
**Rules affected:** none (moved to Not specified)
**Answer:** remove — per the subscription plan DAO precedent (`get_by_name`): no caller, dead code
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-09): both go under **Not specified** as dead code and into `docs/testing/dead-code-removal-checklist.md`. No bug ID.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Sales service / endpoints** (`app/services/sales_service.py`, `app/api/v1/endpoints/sales_orders.py`, not yet specified) | (a) **OQ-26 → 🐞 BUG-2404** (owner, 2026-11-10: system-only; an edit that sends `total_amount`, `is_fully_delivered` or `is_invoiced` gets 422, nothing written; same treatment as `invoice_id` under BUG-1019; the sales service spec must state it as a tagged rule): `PUT /sales-orders/{id}/` takes `SalesOrderUpdate`, which includes `total_amount`, `is_fully_delivered`, `is_invoiced` (and `invoice_id`, already BUG-1019); `update_sales_order` stores them through the inherited `update` with no check, even on a finalized or completed order. The web app never sends them (it sends contact, description, expected date, `required_approvals`). (b) **HR-7:** `GET /sales-orders/` has `limit` `le=100` but no `ge=1`; `limit=-1` reaches Postgres (`DataError` 2201W, a 500). (c) `update_sales_order` is not checked against `is_so_financially_locked` (read, not run). | reading the callers |
| FU-2 | **Sales manager spec** (`tests/unit/managers/sales_manager.spec.md`, APPROVED) | `create_sales_order_with_items` R5 says the number uses "the server's current local year"; with BUG-2440 it is the UTC year. Only the wording changes; the manager's cases do not test a year boundary. | P1 |

## Overview
`DAOSalesOrder` reads and creates `sales_orders`, the contracts with customers. Callers: `SalesManager` (`create_with_user` from `create_sales_order_with_items`; `get_by_invoice_id` from `sync_so_for_linked_invoice`, which `InvoicePaymentManager` calls after every invoice payment change; inherited `get_by_id_and_workspace` everywhere), `SalesService` (inherited `get_by_id_and_workspace`, `get_by_workspace`, `update`), `AttachmentManager` (inherited `get_by_id_and_workspace`, to check the order an attachment goes on). It flushes, never commits, and takes no lock.

**Callables:** 3 specified · 3 not specified (+ inherited `BaseDAO` methods, base spec)
**Externals to mock:** `datetime.now` in `app.dao.sales_order` (patch the module's `datetime` name) for the year of `create_with_user`; after BUG-2440 also `utcnow` (see Notes).
**Integration-only behavior:** the race half of BUG-727 (two concurrent transactions), as in the sales manager spec.

**Model facts (table `sales_orders`, class `app.models.sales_order.SalesOrder`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `sales_order_number` | String(100) NOT NULL, **unique across all workspaces** (`ix_sales_orders_sales_order_number`; BUG-726) | — |
| `account_id` | Integer NOT NULL, FK `accounts.id` ON DELETE RESTRICT | — |
| `factory_id` | Integer NOT NULL, FK `factories.id` ON DELETE RESTRICT | — |
| `order_date` | Date NOT NULL | Python `date.today` |
| `expected_delivery_date` | Date nullable | `NULL` |
| `contact_name` (255), `contact_phone` (50), `description` (Text) | nullable | `NULL` |
| `total_amount` | Numeric(15, 2) NOT NULL | Python `0` |
| `current_status_id` | Integer NOT NULL, FK `statuses.id` ON DELETE RESTRICT (vestigial; schema default `10`, BUG-1019) | — |
| `is_fully_delivered`, `is_invoiced`, `paid`, `order_info_confirmed`, `items_confirmed`, `invoice_confirmed`, `order_completed` | Boolean NOT NULL | `false` (Python and database) |
| `invoice_id` | Integer nullable, FK `account_invoices.id` ON DELETE SET NULL, indexed, **not unique** | `NULL` |
| `required_approvals` | Integer nullable | `NULL` |
| `completed_at` / `completed_by` | DateTime / FK `profiles.id` SET NULL, nullable | `NULL` |
| `created_by` | Integer **NOT NULL**, FK `profiles.id` ON DELETE SET NULL | — |
| `created_at` | DateTime (naive) NOT NULL | Python `utcnow` |
| `updated_by`, `updated_at`, `items_updated_at` | nullable; `updated_at` `onupdate=utcnow` | `NULL` |
No soft-delete column. Orders are never deleted through the API (no delete endpoint); the order number is not editable (`SalesOrderUpdate` has no number field).

**Notes for the test designer:**
- `from app.dao.sales_order import sales_order_dao`. Parents: `make_workspace`, `make_profile` (`tests/unit/factories.py`), `Account(workspace_id, name)`, `Factory(workspace_id, name, abbreviation)`, `Status(workspace_id, name, comment)`; pass `current_status_id` explicitly (the schema default `10` need not exist). `AccountInvoice(workspace_id, account_id, invoice_type='receivable', invoice_amount, invoice_date)` for `get_by_invoice_id`.
- Numbers are globally unique today (BUG-726): a second workspace's first order of the year fails at flush. Tests that need orders in two workspaces insert one of them directly with a distinct `sales_order_number`, or expect the failure (BUG-726 case, strict xfail).
- **BUG-2440:** `mock.patch.object(app.dao.sales_order, "datetime", Fake)` where `Fake` subclasses `datetime` with `now()` returning 1 January 2027 05:00, and patch `app.dao.sales_order.utcnow` (`create=True`: the module does not import it today) and `app.utils.time.utcnow` to 31 December 2026 23:00. Intended `SO-2026-…`; today `SO-2027-…` → **strict** xfail.
- **BUG-2441:** two orders on one invoice; `SET LOCAL enable_indexscan/enable_bitmapscan/enable_indexonlyscan = off`, update the lower `id`, flush, `db.expire_all()`. The result rests on physical order: **non-strict** xfail, or a strict check that the emitted SQL ends in `ORDER BY sales_orders.id`.

## Not specified
- `DAOSalesOrder.get_by_factory` — dead code, to be removed (decided by Claude under the reviewer's delegation (2026-11-09); Q1).
- `DAOSalesOrder.get_by_status` — dead code, to be removed (decided by Claude under the reviewer's delegation (2026-11-09); Q1).
- `sales_order_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — covered by the base spec.

---

## `DAOSalesOrder.get_by_invoice_id(db, *, invoice_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `SalesManager.sync_so_for_linked_invoice`)

**Purpose:** The sales order an invoice belongs to, within one workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| invoice_id | int | compared with `=`; no check that the invoice exists |
| workspace_id | int | the order's own `workspace_id` |

**Returns:** a `SalesOrder` or `None`.

**Rules:**
- **R1.** Returns the order of this workspace whose `invoice_id` equals the given id.
- **R2.** `None` when no order of this workspace has that invoice: an invoice with no order (e.g. a return's credit note), an unknown id, `0`, or an order of another workspace with that `invoice_id` (another workspace's order is never returned).
- **R3.** [BUG-2441] (HR-6) When two or more orders of the workspace have that invoice, the one with the lowest `id` is returned. *(Today: no `ORDER BY`; verified the row returned changed from the lower to the higher `id` after an update.)*
- **R4.** `invoice_id=None` is compared as `IS NULL`: it returns an order of the workspace that has no invoice (or `None` when every order has one). No caller passes `None`.
- **R5.** Positional `invoice_id` / `workspace_id` raise `TypeError`.

**Errors:** none of its own.

**Side effects:** none

---

## `DAOSalesOrder.generate_sales_order_number(db, *, workspace_id, year)`
**Shape:** compute
**Persistence:** reads
**Visibility:** internal (used by: `create_with_user`)

**Purpose:** The next order number of a workspace for a year.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| workspace_id | int | whose orders are counted |
| year | int | printed as is, no padding |

**Returns:** a string `SO-<year>-<n>`.

**Rules:**
- **R1.** `<n>` is the number of this workspace's orders whose number starts with `SO-<year>-`, plus one, zero-padded to at least 3 digits: none → `SO-2026-001`; two → `SO-2026-003`; 999 → `SO-2026-1000`.
- **R2.** Only this workspace's orders count: with three orders in workspace A, workspace B gets `SO-2026-001`.
- **R3.** Only that year's prefix counts: orders of 2025 do not count for 2026, and year `202` (`SO-202-`) does not count `SO-2026-…` numbers. Year `1` gives `SO-1-001`.
- **R3a.** The prefix match is case-sensitive (`LIKE`, not `ILIKE`): a stored `so-2026-001` or `So-2026-001` is not counted. Intended (decided under the reviewer's delegation, 2026-11-10): numbers are made only here, always upper-case, and cannot be edited through the API, so a lower-case number is foreign data and must not shift the sequence.
- **R4.** Every number with the prefix counts, whatever its suffix: a stored `SO-2026-abc` counts as one order. The count says nothing about which numbers are free; through the API numbers are only made here, never edited or deleted, so the count is the highest number in use.
- **R5.** It reads only and takes no lock; whether the number is unique and race-free is `create_with_user` R5.
- **R6.** Positional arguments raise `TypeError`.

**Errors:** none of its own.

**Side effects:** none

---

## `DAOSalesOrder.create_with_user(db, *, obj_in, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `SalesManager.create_sales_order_with_items` ← `POST /sales-orders/`)

**Purpose:** Insert a new order with its number and creator.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| obj_in | `SalesOrderCreate` (`app.schemas.sales_order`) | `account_id`, `factory_id`, `order_date` required; `total_amount` is `Decimal | None` (Pydantic turns an `int`, `float` or numeric string into a `Decimal`; the value is not rounded or bounded by the schema); `expected_delivery_date`, `contact_name`, `contact_phone`, `description`, `total_amount` optional (`None`); `current_status_id` default `10`. No range, length or workspace checks. |
| workspace_id | int | stored on the row |
| user_id | int | stored as `created_by` |

**Returns:** the new `SalesOrder`, flushed (has an `id`), not committed.

**Rules:**
- **R1.** The row gets every field of `obj_in` (unset optional fields as `NULL`), `workspace_id`, `created_by = user_id` and the number from `generate_sales_order_number` for this workspace and the current year.
- **R2.** [BUG-2440] The year is the current year in UTC (`utcnow().year`). *(Today: `datetime.now().year`, the server's local year; verified `SO-2031-001` with a patched `datetime.now()`.)*
- **R3.** `total_amount` omitted (`None`) is stored as `0.00`. A given amount is stored rounded to 2 decimals, half away from zero (`1.005` → `1.01`, `-1.005` → `-1.01`, HR-15). The DAO does not compute it from the lines and accepts zero and negative amounts (the endpoint computes it; ranges are BUG-362 on the lines).
- **R4.** Defaults on the new row: `is_fully_delivered`, `is_invoiced`, `paid`, `order_info_confirmed`, `items_confirmed`, `invoice_confirmed`, `order_completed` all `False`; `invoice_id`, `required_approvals`, `completed_at`, `completed_by`, `updated_by`, `updated_at`, `items_updated_at` `NULL`; `created_at` = now (UTC, naive). The model's default holds the function `app.utils.time.utcnow` itself (bound when the model module was imported), so patching `app.utils.time.utcnow` or `app.dao.sales_order.datetime` does **not** change `created_at`; a card that needs a fixed `created_at` must compare against a window around the call, or set it after the flush.
- **R5.** [BUG-726, BUG-727] The number is unique per workspace: another workspace's `SO-2026-001` does not stop this workspace's first order of 2026, and two creates in one workspace never get the same number. *(Today [BUG-726]: the unique index is global; verified the second workspace's first order fails at flush with `IntegrityError` 23505. Today [BUG-727]: count-then-insert with no lock; the race half is integration-only.)*
- **R6.** Links are stored as given, with no workspace or live check (that is the manager's job: BUG-728 customer/factory, BUG-1019 status). An id that does not exist fails at flush with `IntegrityError` 23503 (account, factory, status, user); verified for status and user.
- **R7.** Positional arguments raise `TypeError`; an `obj_in` that is not a `SalesOrderCreate` (no `model_dump`) raises `AttributeError`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| number already used by any workspace (today; BUG-726) | `IntegrityError` 23505 at flush | DB message |
| unknown account / factory / status / user | `IntegrityError` 23503 at flush | DB message |

**Side effects:** inserts one `sales_orders` row; flush only.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 19–22 | match on `invoice_id` and `workspace_id` | `get_by_invoice_id` R1, R2 |
| 20 | `invoice_id == None` becomes `IS NULL` | `get_by_invoice_id` R4 |
| 23 | `.first()` with no `ORDER BY` | `get_by_invoice_id` R3 |
| 15 | keyword-only `*` | `get_by_invoice_id` R5 |
| 42 | prefix built from `year` | `generate_sales_order_number` R3 |
| 43–50 | count of the workspace's numbers `LIKE 'SO-<year>-%'` | `generate_sales_order_number` R1, R2, R4 |
| 52 | `{n:03d}` (at least 3 digits) | `generate_sales_order_number` R1 |
| 27 | keyword-only `*` | `generate_sales_order_number` R6 |
| 75 | `datetime.now().year` | `create_with_user` R2 |
| 76–78 | number for this workspace | `create_with_user` R1, R5 |
| 80 | `obj_in.model_dump()` (needs a schema) | `create_with_user` R1, R7 |
| 81–86 | row from schema + workspace, number, creator | `create_with_user` R1, R3, R4, R6 |
| 87–88 | add, flush (constraint errors surface here) | `create_with_user` R5, R6 |
| 57 | keyword-only `*` | `create_with_user` R7 |

## Gap log
- G1 (sales_order.cases.md gap 1) — Fact — `create_with_user` Inputs: `SalesOrderCreate.total_amount` is `Decimal | None`; Pydantic converts other numbers to `Decimal`, no rounding or bound in the schema (rounding is the column's, R3).
- G2 (sales_order.cases.md gap 2) — Fact — `create_with_user` R4: `created_at`'s default is the `utcnow` function object captured at import; no clock patch reaches it.
- G3 (coordinator, number-prefix case) — Intent, decided under delegation (2026-11-10) — new `generate_sales_order_number` R3a: the prefix match is case-sensitive, intended, because numbers are system-made upper-case and not editable. Same decision in the delivery and return specs.
- OQ-26 (owner, 2026-11-10) — applied as 🐞 BUG-2404 in FU-1 (a); no rule of this DAO changes.
