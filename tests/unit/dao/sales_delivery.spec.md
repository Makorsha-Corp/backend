# Spec — `app/dao/sales_delivery.py`

> **Status:** APPROVED (2026-11-10; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-09.** No owner answer in this round. **Delegated:** P1 and Q1 decided by Claude under the reviewer's delegation (2026-11-09). None of them is the owner's own answer. The house-rule lines stand. The approved sales manager spec (`tests/unit/managers/sales_manager.spec.md`) already decided numbering (BUG-726, BUG-727), the client-chosen status on create (BUG-722) and the unchecked delivery method (BUG-730); those are reused here with their IDs, not re-asked. Kept consistent with `tests/unit/dao/sales_order.spec.md` (same numbering, same year bug).

> **Review round 2026-11-10 (fill-gaps).** No owner question for this DAO. **Delegated (2026-11-10):** an unknown `workspace_id` on create (G2) and number-prefix case (G3), decided by Claude under the reviewer's delegation; neither is the owner's own answer. Gaps of `sales_delivery.cases.md` closed (Gap log at the end).

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated (`get_by_id_and_workspace`, `get_by_workspace`, `update` are inherited and used by `SalesManager` and `SalesService`).
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Raw lookups stay raw (HR-4 scope; this table has no soft delete). HR-16: a row linking to another workspace's row is invalid data; this DAO stores the links it is given, and refusing foreign ones is the manager's job (manager R2 for the order, BUG-730 for the method).
>
> **Verified by running** (throwaway scripts `schema.py`, `v2.py` with my own harness `hc.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omd\C\`, each transaction rolled back against `marker_test`, private `COVERAGE_FILE`; nothing committed): the table's columns, defaults, constraints and indexes; numbering in an empty workspace, after one and two deliveries, in a second workspace (`DEL-2026-001` again), a patched `datetime.now()` (1 January 2031 → `DEL-2031-001`); `create_with_user` with defaults, with `delivery_status="shipped"` (stored), with another workspace's delivery method (stored), unknown order and unknown method (`IntegrityError` 23503), no method (schema `ValidationError`); `get_by_sales_order` for the order, another workspace, an unknown order, 102 rows (all back), a row recorded under workspace B on A's order (returned only for B), order under a forced sequential scan before and after an update (`[59983, 59984, 59986]` → `[59984, 59986, 59983]`); `get_by_status` with `planned`, `Planned`, `"planned "`, `shipped`, another workspace, `skip=1, limit=1`, `limit=0`, `limit=-1` (`DataError` 2201W), the default cap (100 of 102), the SQL (no `ORDER BY`). **Read, not run:** `SalesManager`, `SalesService`, `GET /sales-deliveries/`, `GET /sales-orders/{id}/deliveries/`. **Not run:** anything over HTTP; two concurrent transactions.

## Review
> All answered; applied 2026-11-09.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | The year in a delivery number comes from the server's local clock | bug — from UTC (BUG-2440, same bug as the sales order DAO) | Claude, delegated |
| Q1 | "Deliveries in a date range" has no caller anywhere | remove | Claude, delegated |

Decided by house rules: an order's deliveries come back in no fixed order (BUG-2442); the status-filtered delivery list pages in no fixed order (BUG-2443).
Already decided elsewhere and reused: numbers unique across all workspaces (BUG-726), numbering race (BUG-727), a delivery created in any status (BUG-722), a foreign or deleted delivery method accepted (BUG-730).

### House-rule violations — applied automatically

- **HR-6** `get_by_sales_order` R3 — no `ORDER BY`. Verified under a forced sequential scan: an order's three deliveries came back `[59983, 59984, 59986]`, and after an update of 59983 as `[59984, 59986, 59983]`, so `GET /sales-orders/{id}/deliveries/` can reshuffle between two views. Intended: `id` ascending — deliveries have no name, and `id` is the order they were planned in, the same order as their numbers (BUG-1271 precedent for the delivery's lines).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-2442 (pattern `unordered-pagination`). Rules: `get_by_sales_order` R3.
- **HR-6** `get_by_status` R3 — pages with `skip` / `limit` and no `ORDER BY`. Intended: `id` ascending before `skip` / `limit`, the same order as the unfiltered branch of the same endpoint (`GET /sales-deliveries/` without a status uses the inherited `get_by_workspace`, `id` ascending after BUG-100), so a filter never changes the order.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-2443 (pattern `unordered-pagination`). Rules: `get_by_status` R3.

Checked and **not** a new line here: **HR-4** — `sales_deliveries` has no soft-delete column. **HR-5** — every filter is in the query. **HR-7** — `GET /sales-deliveries/` has no `limit >= 1` (FU-1 (b)); the DAO is not the place. **HR-8** — no `LIKE` on user text. **HR-3** — `delivery_status` is a system code (`planned`, `delivered`, `cancelled`), not free text; the filter is exact by design, and which codes a client may create is BUG-722. **HR-9, HR-10** — the DAO only inserts and reads; completing / cancelling (the check-then-change) is BUG-720 in the manager. **HR-15** — no money. **HR-16** — reads filter on the row's own `workspace_id`; writes store what the caller passes.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-09)

### P1. The year in a delivery number comes from the server's local clock — 🐞 BUG-2440
**Background:** `create_with_user` numbers the delivery `DEL-<year>-<n>`, taking the year from `datetime.now()`, the machine's local time; `created_at` is UTC. Ruled a bug for batch numbers (BUG-1334), help tickets (BUG-1441) and, in this round, sales orders (BUG-2440).
**What happens today:** Around New Year, a server whose local clock is in another year than UTC numbers the delivery with the local year. (Verified with a patched `datetime.now()` returning 1 January 2031 00:30: `DEL-2031-001`.)
**Example:** A server set to `Asia/Dhaka` (UTC+6). A delivery planned at 20:00 UTC on 31 December 2026 is `DEL-2027-001`, with `created_at` in 2026.
**Rules affected:** `create_with_user` R2
**Answer:** bug — per BUG-1334 precedent: the year comes from `utcnow()`
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-09): 🐞 BUG-2440 (pattern `local-clock-instead-of-utc`; one bug with the sales order DAO). Rules: `create_with_user` R2 (tagged).

### New questions

### Q1. "Deliveries in a date range" has no caller — 🗑️ removed
**Background:** `get_by_date_range` lists a workspace's deliveries whose `scheduled_date` lies between two dates.
**What happens today:** Nothing in `app/`, `tests/` or `scripts/` calls it; no endpoint reaches it (the calendar service queries `sales_deliveries` itself). It pages with no `ORDER BY`.
**Example:** Deleting it changes no response of the API.
**Rules affected:** none (moved to Not specified)
**Answer:** remove — per the subscription plan DAO precedent (`get_by_name`): no caller, dead code
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-09): under **Not specified** as dead code and into `docs/testing/dead-code-removal-checklist.md`. No bug ID.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Sales service / endpoints** (`app/services/sales_service.py`, `app/api/v1/endpoints/sales_deliveries.py`, `sales_orders.py`, not yet specified) | (a) `get_deliveries` treats `delivery_status=""` as "no filter" (`if delivery_status:`), and an unknown status (`"Planned"`, `"shipped"`) returns `[]` with 200 rather than 422; decide whether the endpoint validates the code (delegated, validation). (b) **HR-7:** `GET /sales-deliveries/` has `limit` `le=100` but no `ge=1`; `limit=-1` reaches Postgres (`DataError` 2201W, a 500). (c) `GET /sales-orders/{id}/deliveries/` for an unknown or another workspace's order answers `[]` (200), not 404 (read, not run). | reading the callers |
| FU-2 | **Sales manager spec** (`tests/unit/managers/sales_manager.spec.md`, APPROVED) | `create_delivery_with_items` R4 computes the delivery number "like the order number", i.e. the local year; with BUG-2440 it is the UTC year. Wording only. | P1 |

## Overview
`DAOSalesDelivery` reads and creates `sales_deliveries`, the shipments planned against a sales order. Callers: `SalesManager` (`create_with_user` from `create_delivery_with_items`; inherited `get_by_id_and_workspace` and `update` for complete, cancel and edit), `SalesService` (`get_by_sales_order` for `GET /sales-orders/{id}/deliveries/`, `get_by_status` or inherited `get_by_workspace` for `GET /sales-deliveries/`, inherited `get_by_id_and_workspace`). It flushes, never commits, and takes no lock.

**Callables:** 4 specified · 2 not specified (+ inherited `BaseDAO` methods, base spec)
**Externals to mock:** `datetime.now` in `app.dao.sales_delivery` (patch the module's `datetime` name) for the year of `create_with_user`; after BUG-2440 also `utcnow` (see Notes).
**Integration-only behavior:** the race half of BUG-727 (two concurrent transactions), as in the sales manager spec.

**Model facts (table `sales_deliveries`, class `app.models.sales_delivery.SalesDelivery`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `sales_order_id` | Integer NOT NULL, FK `sales_orders.id` ON DELETE CASCADE | — |
| `delivery_number` | String(100) NOT NULL, **unique across all workspaces** (`ix_sales_deliveries_delivery_number`; BUG-726) | — |
| `scheduled_date`, `actual_delivery_date` | Date nullable | `NULL` |
| `delivery_status` | String(50) NOT NULL, indexed, no check constraint; values used `planned`, `delivered`, `cancelled` | Python `'planned'` (no database default) |
| `delivery_method_id` | Integer nullable, FK `delivery_methods.id` ON DELETE SET NULL (required by `SalesDeliveryCreate`) | — |
| `tracking_number` (255), `completion_code` (100), `notes` (Text) | nullable | `NULL` |
| `created_by` | Integer **NOT NULL**, FK `profiles.id` ON DELETE SET NULL | — |
| `created_at` | DateTime (naive) NOT NULL | Python `utcnow` |
| `updated_by`, `updated_at` | nullable; `updated_at` `onupdate=utcnow` | `NULL` |
No soft-delete column. Deliveries are never deleted through the API (cancel sets the status); the number is not editable.

**Notes for the test designer:**
- `from app.dao.sales_delivery import sales_delivery_dao`. Parents: `make_workspace`, `make_profile`, `Account(workspace_id, name)`, `Factory(workspace_id, name, abbreviation)`, `Status(workspace_id, name, comment)`, `DeliveryMethod(workspace_id, name)`, a `SalesOrder` (insert directly with a distinct `sales_order_number`, or through `sales_order_dao.create_with_user`). `SalesDeliveryCreate(sales_order_id, delivery_method_id, …)`.
- Numbers are globally unique today (BUG-726): rows for a second workspace are inserted directly with a distinct `delivery_number`.
- **BUG-2440:** `mock.patch.object(app.dao.sales_delivery, "datetime", Fake)` with `now()` returning 1 January 2027 05:00, and patch `app.dao.sales_delivery.utcnow` (`create=True`) and `app.utils.time.utcnow` to 31 December 2026 23:00. Intended `DEL-2026-…`; today `DEL-2027-…` → **strict** xfail.
- **BUG-2442, BUG-2443:** `SET LOCAL enable_indexscan/enable_bitmapscan/enable_indexonlyscan = off`, update the lowest `id`, flush, `db.expire_all()`. Physical order: **non-strict** xfail, or a strict check that the SQL ends in `ORDER BY sales_deliveries.id`.
- **BUG-722:** the fix removes `delivery_status` from `SalesDeliveryCreate` (or ignores it, `extra='ignore'`). A test constructs `SalesDeliveryCreate(..., delivery_status="shipped")` and expects the row to be `planned` → **strict** xfail today.

## Not specified
- `DAOSalesDelivery.get_by_date_range` — dead code, to be removed (decided by Claude under the reviewer's delegation (2026-11-09); Q1).
- `sales_delivery_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — covered by the base spec.

---

## `DAOSalesDelivery.generate_delivery_number(db, *, workspace_id, year)`
**Shape:** compute
**Persistence:** reads
**Visibility:** internal (used by: `create_with_user`)

**Purpose:** The next delivery number of a workspace for a year.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| workspace_id | int | whose deliveries are counted |
| year | int | printed as is, no padding |

**Returns:** a string `DEL-<year>-<n>`.

**Rules:**
- **R1.** `<n>` is the number of this workspace's deliveries whose number starts with `DEL-<year>-`, plus one, zero-padded to at least 3 digits: none → `DEL-2026-001`; two → `DEL-2026-003`; 999 → `DEL-2026-1000`.
- **R2.** Only this workspace's deliveries count (all statuses, cancelled included): with deliveries in workspace A, workspace B gets `DEL-2026-001`.
- **R3.** Only that year's prefix counts: 2025's deliveries do not count for 2026; year `202` does not count `DEL-2026-…`.
- **R3a.** The prefix match is case-sensitive (`LIKE`, not `ILIKE`): a stored `del-2026-001` is not counted. Intended (decided under the reviewer's delegation, 2026-11-10): numbers are made only here, always upper-case, and cannot be edited through the API; same decision as `sales_order` R3a.
- **R4.** Every number with the prefix counts, whatever its suffix. Through the API numbers are only made here, never edited or deleted, so the count is the highest number in use.
- **R5.** It reads only and takes no lock; uniqueness and the race are `create_with_user` R5.
- **R6.** Positional arguments raise `TypeError`.

**Errors:** none of its own.

**Side effects:** none

---

## `DAOSalesDelivery.create_with_user(db, *, obj_in, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `SalesManager.create_delivery_with_items` ← `POST /sales-deliveries/`)

**Purpose:** Insert a new delivery with its number and creator.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| obj_in | `SalesDeliveryCreate` (`from app.schemas.sales_delivery import SalesDeliveryCreate`) | `sales_order_id`, `delivery_method_id` required (missing → `ValidationError` when the schema is built); `scheduled_date`, `tracking_number`, `notes` optional; `delivery_status` default `'planned'`, any string (today; BUG-722) |
| workspace_id | int | stored on the row |
| user_id | int | stored as `created_by` |

**Returns:** the new `SalesDelivery`, flushed (has an `id`), not committed.

**Rules:**
- **R1.** The row gets `sales_order_id`, `delivery_method_id`, `scheduled_date`, `tracking_number`, `notes` from `obj_in` (unset ones `NULL`), `workspace_id`, `created_by = user_id` and the number from `generate_delivery_number` for this workspace and the current year.
- **R2.** [BUG-2440] The year is the current year in UTC (`utcnow().year`). *(Today: `datetime.now().year`; verified `DEL-2031-001` with a patched `datetime.now()`.)*
- **R3.** [BUG-722] A new delivery is always `planned`, whatever `delivery_status` the schema object carries. *(Today: the schema's value is stored as sent; verified `"shipped"` stored.)*
- **R4.** Defaults on the new row: `actual_delivery_date`, `completion_code`, `updated_by`, `updated_at` `NULL`; `created_at` = now (UTC, naive).
- **R5.** [BUG-726, BUG-727] The number is unique per workspace: another workspace's `DEL-2026-001` does not stop this workspace's first delivery of 2026, and two creates in one workspace never get the same number. *(Today [BUG-726]: the unique index is global, so a number used by another workspace fails at flush with `IntegrityError` 23505. Today [BUG-727]: count-then-insert with no lock; the race half is integration-only.)*
- **R6.** Links are stored as given, with no workspace or live check: an order of another workspace or another workspace's delivery method is stored (verified for the method). Refusing them is the manager's job (`create_delivery_with_items` R2 for the order, BUG-730 for the method). An id that does not exist fails at flush with `IntegrityError` 23503 (order, method, user); verified for order and method.
- **R6a.** An unknown `workspace_id` is not checked by the DAO: the number is counted for it (no rows, so `-001`) and the insert fails at flush with `IntegrityError` 23503 (FK `workspaces.id`), nothing saved. If that number is already used by another workspace, the global unique index answers first with 23505 (BUG-726; unique checks run at insert, foreign keys at the end of the statement); after the BUG-726 fix it is 23503. Intended (decided under the reviewer's delegation, 2026-11-10): the workspace always comes from the request's checked membership (`get_current_workspace`), never from the body, so the DAO trusts its caller as every other DAO does (base spec); no bug.
- **R7.** Positional arguments raise `TypeError`; an `obj_in` that is not a schema object (no `model_dump`) raises `AttributeError`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| number already used by any workspace (today; BUG-726) | `IntegrityError` 23505 at flush | DB message |
| unknown order / delivery method / user / workspace | `IntegrityError` 23503 at flush | DB message |

**Side effects:** inserts one `sales_deliveries` row; flush only.

---

## `DAOSalesDelivery.get_by_sales_order(db, *, sales_order_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `SalesService.get_deliveries_for_order` ← `GET /sales-orders/{id}/deliveries/`)

**Purpose:** All deliveries of one sales order.

**Returns:** a `list` of `SalesDelivery` (possibly empty).

**Rules:**
- **R1.** Returns every delivery with that `sales_order_id` and that `workspace_id`, in every status (planned, delivered, cancelled, any other text).
- **R2.** Another workspace, an unknown order or `0` returns `[]`. A row recorded under workspace B on an order of A is returned only for B.
- **R3.** [BUG-2442] (HR-6) Ordered by `id` ascending. *(Today: no `ORDER BY`; verified the order changed after an update.)*
- **R4.** No paging and no cap: 102 deliveries give 102 rows.
- **R5.** Positional arguments raise `TypeError`.

**Errors:** none of its own.

**Side effects:** none

---

## `DAOSalesDelivery.get_by_status(db, *, delivery_status, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `SalesService.get_deliveries` ← `GET /sales-deliveries/?delivery_status=…`)

**Purpose:** A page of a workspace's deliveries in one status.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| delivery_status | str | compared exactly with `=` |
| workspace_id | int | the row's own `workspace_id` |
| skip, limit | int | passed to `OFFSET` / `LIMIT` unchecked |

**Returns:** a `list` of `SalesDelivery` (possibly empty).

**Rules:**
- **R1.** Returns the workspace's deliveries whose `delivery_status` equals the text exactly: case and spaces matter (`"Planned"` and `"planned "` return `[]` when only `planned` rows exist). Any text is accepted; one no delivery has returns `[]`.
- **R2.** Another workspace's deliveries are never returned.
- **R3.** [BUG-2443] (HR-6) Ordered by `id` ascending, then `skip` / `limit` applied. *(Today: no `ORDER BY`.)*
- **R4.** Paging: default first 100 (102 matching rows → 100); `skip=1, limit=1` gives the second row of the R3 order; `limit=0` gives `[]`; a negative `limit` or `skip` raises `DataError` (2201W / 2201X) from Postgres.
- **R5.** Positional arguments raise `TypeError`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` / `skip` | `DataError` | DB message |

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 29 | prefix built from `year` | `generate_delivery_number` R3 |
| 30–37 | count of the workspace's numbers `LIKE 'DEL-<year>-%'` | `generate_delivery_number` R1, R2, R4 |
| 39 | `{n:03d}` (at least 3 digits) | `generate_delivery_number` R1 |
| 15 | keyword-only `*` | `generate_delivery_number` R6 |
| 62 | `datetime.now().year` | `create_with_user` R2 |
| 63–65 | number for this workspace | `create_with_user` R1, R5 |
| 67 | `obj_in.model_dump()` (carries `delivery_status`) | `create_with_user` R1, R3, R7 |
| 68–73 | row from schema + workspace, number, creator | `create_with_user` R1, R4, R6 |
| 74–75 | add, flush (constraint errors surface here) | `create_with_user` R5, R6 |
| 44 | keyword-only `*` | `create_with_user` R7 |
| 87–92 | match on order and workspace, no `ORDER BY`, no limit | `get_by_sales_order` R1–R4 |
| 81 | keyword-only `*` | `get_by_sales_order` R5 |
| 107–110 | exact match on status and workspace | `get_by_status` R1, R2 |
| 106–113 | no `ORDER BY`; `OFFSET` / `LIMIT` | `get_by_status` R3, R4 |
| 98 | keyword-only `*` | `get_by_status` R5 |

## Gap log
- G1 (sales_delivery.cases.md gap 1) — Fact — `create_with_user` Inputs: import path `app.schemas.sales_delivery.SalesDeliveryCreate`.
- G2 (sales_delivery.cases.md gap 2) — Intent, decided under delegation (2026-11-10) — new `create_with_user` R6a + Errors row: an unknown workspace fails at flush with 23503 (23505 first while BUG-726 is open and the number is taken elsewhere); intended, because the workspace comes from the checked request context and DAOs trust their caller. Read, not run.
- G3 (coordinator, number-prefix case) — Intent, decided under delegation (2026-11-10) — new `generate_delivery_number` R3a: case-sensitive prefix, intended (as `sales_order` R3a).
