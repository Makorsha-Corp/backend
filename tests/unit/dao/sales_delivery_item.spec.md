# Spec — `app/dao/sales_delivery_item.py`

> **Status:** APPROVED (2026-11-02; no questions, house-rule line pre-filled)
> **Source commit:** e48a092

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v2.py`, `v6.py`, `v7.py`, harness `h.py`, `w.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns and constraints; no `ORDER BY`; the order changing after an update; 101 rows; unknown id; another workspace. **Not run:** anything over HTTP; the intended behaviour of BUG-1271.

## Review
> Nothing open. Overwrite the pre-filled answer only if the house rule should not apply here.

### House-rule violations — applied automatically

- **HR-6** `get_by_delivery` R3 — no `ORDER BY`. Verified: two lines came back higher `id` first once the lower `id` was updated, so the lines of a delivery can change place between two views. Intended: `id` ascending (BUG-906 precedent: the rows have no name, and `id` is the order they were entered).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1271 (pattern `unordered-pagination`). Rules: `get_by_delivery` R3.

Checked and **not** a new line here: **HR-5, HR-7, HR-8** — no paging, no `LIKE`. **HR-4** — neither this table nor `sales_deliveries` has a soft-delete column. **HR-9, HR-10** — the DAO only reads; `complete_delivery` holds the check-then-write and the sales manager spec covers it. **HR-15** — no money. **HR-16** — no response is affected: `create_delivery_with_items` writes the checked workspace, and a line from another order is BUG-723.

## Overview
`DAOSalesDeliveryItem` reads `sales_delivery_items`, the lines of one delivery. Callers: `SalesManager` (stock posting on completion), `SalesService` (`get_delivery_items` and the delivery response) and inherited `create`. Reached through `GET /sales-deliveries/…` and delivery completion.

**Callables:** 1 specified · 2 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `sales_delivery_items`):** `workspace_id` FK CASCADE, `delivery_id` FK CASCADE, `sales_order_item_id` FK RESTRICT, `quantity_delivered` Numeric(15,2) are NOT NULL; `item_id` FK RESTRICT is nullable (a free-text line); `notes` nullable. No soft delete, no unique constraint.

**Notes for the test designer:** `from app.dao.sales_delivery_item import sales_delivery_item_dao`. Parents need `Account`, `Factory`, `Status(workspace_id, name, comment)`, `SalesOrder(workspace_id, sales_order_number, account_id, factory_id, order_date, total_amount, current_status_id, created_by)`, `SalesOrderItem(workspace_id, sales_order_id, description, quantity_ordered, unit_price, line_total)`, `SalesDelivery(workspace_id, sales_order_id, delivery_number, delivery_status, created_by)`. Flush before calling. **BUG-1271:** two rows, update the lower `id`, flush, `db.expire_all()`. The result rests on physical order: **non-strict** xfail, assertion not weakened.

## Not specified
- `sales_delivery_item_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — covered by the base spec.

---

## `DAOSalesDeliveryItem.get_by_delivery(db, *, delivery_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `SalesManager.complete_delivery`, `SalesService`)

**Purpose:** All lines of one delivery.

**Returns:** a `list` of `SalesDeliveryItem` (possibly empty).

**Rules:**
- **R1.** Returns every row with that `delivery_id` and that `workspace_id`. Another workspace returns `[]`, and a row of workspace B on a delivery of A is returned only for B.
- **R2.** An unknown delivery, `0`, or a delivery with no lines returns `[]`.
- **R3.** [BUG-1271] (HR-6) Ordered by `id` ascending. *(Today: no `ORDER BY`; the order changed after the lower `id` was updated.)*
- **R4.** No paging and no cap: 101 lines give 101 rows.
- **R5.** Positional `delivery_id` raises `TypeError`.

**Errors:** none of its own.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 16–22 | keyword-only parameters | R5 |
| 26–29 | delivery AND workspace | R1, R2 |
| 25–30 | no `ORDER BY` (BUG-1271) | R3 |
| 30 | `.all()`: no cap; empty / many | R2, R4 |
| 33 | module singleton | Not specified |
