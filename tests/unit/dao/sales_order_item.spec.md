# Spec — `app/dao/sales_order_item.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** **Delegated:** Q1 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-02). It is not the owner's own answer. BUG-1270 stands from the house rule.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v2.py`, `v6.py`, `v7.py`, harness `h.py`, `w.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, check constraint, referencing tables; the order of `get_by_sales_order`; no `ORDER BY` and no `FOR UPDATE` in either statement; 103 lines; unknown ids, another workspace; a row of workspace B on an order of A; a free-text line and a line on an inactive item. **Not run:** anything over HTTP; the intended behaviour of BUG-1270.

## Review
> All answered; applied 2026-11-02.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | `get_by_item` has no caller | remove | Claude, delegated |

Decided by a house rule: a sales order's lines have no sort order (BUG-1270, HR-6).

### House-rule violations — applied automatically

- **HR-6** `get_by_sales_order` R3 — no `ORDER BY`. Verified: three lines came back in the order highest `id`, lowest, middle with nothing updated, and in another order after an update. This is the line list of a sales order, also read for return checks and the fully-delivered check. Intended: `id` ascending (BUG-906 precedent: the table has no `line_number`, and `id` is the order they were entered).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1270 (pattern `unordered-pagination`). Rules: `get_by_sales_order` R3.

Checked and **not** a new line here: **HR-5, HR-8** — filters are in the query, no `LIKE`. **HR-7** — `get_by_sales_order` does not page. **HR-4** — neither this table nor `sales_orders` has a soft-delete column. **HR-9, HR-10** — the DAO only reads. **HR-15** — the DAO computes no money. **HR-16** — no response is affected: writes take the checked workspace. Line 332 of `sales_manager.py` uses the unscoped inherited `get`, with an id from a row already scoped.

### New questions

### Q1. `get_by_item` has no caller — ✅ remove
**Background:** The method lists the sales order lines of one catalog item, a page at a time. No code in `app/` calls it, and no endpoint reaches it. The item summary page reads `SalesOrderItem` with its own query in `app/services/item_summary_service.py`. Its neighbours `get_pending_items` and two delivery item methods were already removed as dead code, and the checklist does not mark this one.
**What happens today:** Nothing can reach it; it works when called directly (verified).
**Example:** A search of the code for callers of `get_by_item` on this DAO finds none, so no user action can run it. Its bug, if any, shows nowhere.
**Rules affected:** none left; the section is removed
**Suggested answer:** `remove` — unreachable, and keeping it means fixing and testing code nobody runs. Alternative: `intended — keep`, and BUG-1270 then covers its order too.
**Answer:** remove
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): dead code, to be removed. Moved to **Not specified**, section and Branch-map rows deleted, listed in `docs/testing/dead-code-removal-checklist.md`.

## Overview
`DAOSalesOrderItem` reads `sales_order_items`, the lines of a sales order. Callers: `SalesManager`, `SalesService`, `SalesOrderReturnManager`, plus inherited `create`, `get_by_id_and_workspace` and `get`. Reached through `GET /sales-orders/{id}/items/` and the order, delivery and return flows.

**Callables:** 1 specified · 3 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `sales_order_items`):** `workspace_id` FK CASCADE, `sales_order_id` FK CASCADE, `quantity_ordered`, `quantity_delivered`, `unit_price`, `line_total` (Numeric(15,2)) are NOT NULL; `item_id` FK RESTRICT nullable, `description` nullable, with the check `ck_sales_order_items_item_or_description` requiring one of them. `requires_delivery` default true; `quantity_returned`, `quantity_refunded` default 0. `sales_delivery_items` and `sales_order_return_items` reference it with RESTRICT. `item` loads by a join in the same statement. No soft delete, no unique constraint.

**Notes for the test designer:** `from app.dao.sales_order_item import sales_order_item_dao`. Build `SalesOrder` as in `tests/unit/dao/sales_delivery_item.spec.md`. **BUG-1270:** three lines, update the lowest `id`, flush, `db.expire_all()`. The result rests on physical order: **non-strict** xfail, assertion not weakened.

## Not specified
- `sales_order_item_dao` — module-level singleton, no logic.
- `DAOSalesOrderItem.get_by_item` — dead code, to be removed (Claude, delegated).
- Inherited `BaseDAO` methods — covered by the base spec.

---

## `DAOSalesOrderItem.get_by_sales_order(db, *, sales_order_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `SalesManager`, `SalesService`, `SalesOrderReturnManager`)

**Purpose:** All lines of one sales order.

**Returns:** a `list` of `SalesOrderItem` (possibly empty).

**Rules:**
- **R1.** Returns every row with that `sales_order_id` and that `workspace_id`, free-text lines (`item_id` `None`, `item_name` = `description`) included. Another workspace returns `[]`; a row of workspace B on an order of A is returned only for B.
- **R2.** An unknown order, `0`, or an order with no lines returns `[]`.
- **R3.** [BUG-1270] (HR-6) Ordered by `id` ascending. *(Today: no `ORDER BY`.)*
- **R4.** No paging and no cap: 103 lines give 103 rows.
- **R5.** The state of the catalog item is not looked at: a line on an inactive item is returned, with that item's name.
- **R6.** Positional `sales_order_id` raises `TypeError`.

**Errors:** none of its own.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 13–19 | keyword-only parameters | `get_by_sales_order` R6 |
| 23–26 | order AND workspace; no item state | `get_by_sales_order` R1, R2, R5 |
| 21–28 | no `ORDER BY` (BUG-1270) | `get_by_sales_order` R3 |
| 27 | `.all()`: no cap | `get_by_sales_order` R4 |
| 51 | module singleton | Not specified |
