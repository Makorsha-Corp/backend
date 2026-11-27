# Spec — `app/dao/work_order_item.py`

> **Status:** APPROVED (2026-11-02; no questions, house-rule lines pre-filled)
> **Source commit:** e48a092

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Things of a soft-deleted parent are hidden. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v2.py`, `v6.py`, `v7.py`, harness `h.py`, `w.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns and constraints; soft-deleted lines with `include_deleted` `False`, `True` and `None`; no `ORDER BY`; the order changing after an update; 101 lines; unknown ids; another workspace; a soft-deleted line by id; a soft-deleted work order through the DAO and `WorkOrderManager.get_items`; keyword-only parameters. **Not run:** anything over HTTP; two concurrent transactions; the intended behaviour of the bugs below.

## Review
> Nothing open. Overwrite a pre-filled answer only if the house rule should not apply here.

### House-rule violations — applied automatically

- **HR-6** `get_by_work_order` R5 — no `ORDER BY`. Verified: two lines came back higher `id` first once the lower `id` was updated. The same read drives the parts list and the posting of stock at start, so it also decides which line fails first. Intended: `id` ascending (BUG-906 precedent).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1272 (pattern `unordered-pagination`). Rules: `get_by_work_order` R5.
- **HR-4** `get_by_work_order` R3 — the `include_deleted` option exists and no caller passes it, so voided lines cannot be listed through the API. Intended: `GET /work-orders/{id}/items/` accepts `include_deleted`, default false. The rule of this DAO does not change.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** BUG-1273 (pattern `flag-unreachable-from-api`). The tag belongs to the work order manager's spec, FU-1 (b). If the owner would rather drop the flag, it goes to the dead-code list instead.

Checked and **not** a new line here: **HR-4** on `get_by_id_and_workspace` — it returns a soft-deleted line (R1 of that method), and both callers refuse it themselves with 404 `Work order item not found`. **HR-5, HR-7, HR-8** — no paging, no `LIKE`. **HR-9, HR-10** — the DAO only reads. **HR-15** — the DAO computes no money. **HR-16** — the read follows the row; cross-workspace item ids on writes are BUG-1016.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Work order manager** (`app/managers/work_order_manager.py`, not yet specified) | (a) **BUG-1279, logged:** `get_work_order` returns a soft-deleted order, so `get_items` lists its lines (verified), and `add_item`, `update_item`, `remove_item` reach them. Same finding as `tests/unit/dao/work_order_approver.spec.md` FU-1 (b). The manager's spec must carry the rule and the tag. (b) **BUG-1273:** the same spec carries the `include_deleted` rule. | standing decision |

## Overview
`WorkOrderItemDAO` reads `work_order_items`, the parts lines of a work order. Lines are soft-deleted by `remove_item` (`is_deleted`, `deleted_at`, `deleted_by`). Callers: `WorkOrderManager` only. It takes no lock.

**Callables:** 2 specified · 2 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `work_order_items`):** `workspace_id` FK CASCADE, `work_order_id` FK CASCADE, `item_id` FK (no action), `quantity` Numeric(15,2) are NOT NULL; `uses_inventory` default false, `action_type` default `'CONSUME'`, `is_deleted` default false, all three with database defaults. `item` and `replaced_item` load joined. No unique constraint.

**Notes for the test designer:** `from app.dao.work_order_item import work_order_item_dao`. Parents: `Factory`, `Item(workspace_id, name, unit, name_normalized)`, `WorkOrderType(workspace_id, name)`, `WorkOrder(workspace_id, work_order_number, title, factory_id, work_order_type_id)`. Flush before calling. **BUG-1272:** two lines, update the lower `id`, flush, `db.expire_all()`. The result rests on physical order: **non-strict** xfail, assertion not weakened.

## Not specified
- `work_order_item_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods not overridden — covered by the base spec. `create` and `update` are used by the manager.

---

## `WorkOrderItemDAO.get_by_work_order(db, *, work_order_id, workspace_id, include_deleted=False)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderManager.get_items`, `_ensure_catalog_item_not_on_wo`, and the stock posting steps; `include_deleted` is never passed)

**Purpose:** The lines of one work order, live ones unless asked otherwise.

**Returns:** a `list` of `WorkOrderItem` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `work_order_id` and that `workspace_id`. Another workspace returns `[]`; a row of workspace B on an order of A is returned only for B.
- **R2.** An unknown order, `0`, or an order with no lines returns `[]`.
- **R3.** With `include_deleted` false, or left out, soft-deleted lines are not returned. Any falsy value (`None`) acts the same.
- **R4.** With `include_deleted=True` soft-deleted lines are returned with the live ones.
- **R5.** [BUG-1272] (HR-6) Ordered by `id` ascending. *(Today: no `ORDER BY`.)*
- **R6.** No paging and no cap: 101 lines give 101 rows.
- **R7.** The state of the order is not looked at: the live lines of a soft-deleted order are returned. The caller names the order, and hiding it is `get_work_order`'s (BUG-1279).
- **R8.** Positional `work_order_id` raises `TypeError`.

**Errors:** none of its own.

**Side effects:** none

---

## `WorkOrderItemDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderManager.update_item`, `remove_item`)

**Purpose:** One line by id, inside one workspace.

**Returns:** the `WorkOrderItem`, or `None`.

**Rules:**
- **R1.** An override with the same outcome as `BaseDAO.get_by_id_and_workspace` R1–R4: found, `None` for another workspace, `None` for an unknown id, and a soft-deleted line is returned.

**Errors:** none.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 16–23 | keyword-only parameters; default `False` | `get_by_work_order` R3, R8 |
| 25–28 | order AND workspace; no parent state | `get_by_work_order` R1, R2, R7 |
| 29–30 | `not include_deleted`: filter / none | `get_by_work_order` R3, R4 |
| 31 | no `ORDER BY` (BUG-1272); `.all()`: no cap | `get_by_work_order` R5, R6 |
| 37–40 | id AND workspace; no `is_deleted`; `.first()`: row / `None` | `get_by_id_and_workspace` R1 |
| 43 | module singleton | Not specified |
