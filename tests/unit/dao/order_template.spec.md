# Spec — `app/dao/order_template.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** O1 is the owner's answer (owner's answers relayed by the coordinator, 2026-11-02): BUG-1226, whose rule belongs to the manager (FU-1 (d)). **Delegated:** Q1 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-02); not the owner's own answer.

> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Raw lookups stay raw (HR-4 scope). Things of a soft-deleted parent are hidden by the parent's state: whether a deactivated template is a soft-deleted parent is Q1. HR-16: a row linking to another workspace's row is invalid data. Base behaviour is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Verified by running** (scripts `rd_h.py`, `rd_0.py`, `rd_4.py`, `rd_4b.py`, `rd_5.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\refdao\`, each transaction rolled back against `marker_test`; nothing committed): both tables' columns, constraints, indexes, no trigger, referencing keys; `get_by_workspace` with every filter value below, defaults and caps (101 rows → 100, `limit=1000` → 101), `limit=0`, `skip` past the end, negative paging errors, a positional call; **five templates of one `created_at`: the order changed after one was updated, and paging one row at a time gave `[2079], [2079], [2082], [2083], [2080]`, so 2081 was never shown and 2079 twice**; items of one `line_number`, whose order changed the same way; the two by-id lookups; items of a deactivated template; an item row whose `workspace_id` differs from its template's; inherited `remove` of a template with items; through `OrderTemplateManager`: `cost_center_id` of another workspace, an unknown one, a non-member `default_approver_id`, `expense_category="garbage"`, setting `unit_price` to 0, `delete_template` then `get_template`, `get_items`, `add_item`, `update_template` with `is_active: true`; `create_expense_order_from_template` refusing the foreign department. **Not run:** anything over HTTP; two concurrent transactions; the intended behavior of any bug.

## Review
> All answered 2026-11-02.

| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | A "deleted" template and its lines stay readable and editable | intended: `DELETE` here means deactivate | Claude, delegated |
| O1 | Setting a template line's price to 0 leaves the old subtotal | bug — subtotal 0 | owner |

### House-rule violations — applied automatically

- **HR-6** `OrderTemplateDAO.get_by_workspace` R5 — a page ordered by `created_at` alone. Rows of one timestamp have no order, and paging repeated one row and missed another (verified). Intended: `created_at` descending, then `id` descending, before paging. Newest first stays: that is a chosen order, not a missing one, as BUG-600 and BUG-1190 kept theirs.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1210 (pattern `tied-timestamp-no-tiebreak`). Rules: `get_by_workspace` R5.
- **HR-6** `OrderTemplateItemDAO.get_by_template` R2 — ordered by `line_number` alone, and `line_number` is not unique: two concurrent `add_item` calls can give two lines one number. Intended: `line_number` ascending, then `id` ascending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1211 (pattern `unordered-pagination`). Rules: `get_by_template` R2.

Two more bugs reach this module and belong to its manager (FU-1), so no rule here carries the tags: **BUG-1014** (account, existing) and **BUG-1216** (HR-16: `cost_center_id`, `default_approver_id`, pattern `cross-workspace-link-not-refused`).

Checked and **not** a new line here: **HR-5** — every filter is in the query. **HR-7** — `GET /order-templates/` requires `1 <= limit <= 1000` and `skip >= 0`. **HR-8** — no `LIKE`; `expense_category` is an exact match. **HR-3** — `expense_category` is meant as a code (`factory`, `department`, `other`), not free text, so the exact compare is right and the missing validation is FU-1 (b). **HR-4** — no `is_deleted` column, Q1. **HR-9** — the DAO writes nothing of its own; the manager's stamp is FU-1 (c). **HR-10** — only reads. **HR-15** — no rounding here; the `Numeric(15, 2)` columns round half away from zero (verified: `3 × 0.125` → `0.38`). **HR-16** — both DAOs compare the row's own `workspace_id`, `get_by_template` R4.

### New questions

### Q1. A "deleted" template and its lines stay readable and editable — ✅ intended
**Background:** Order templates have no `is_deleted` column. `DELETE /order-templates/{id}/` sets `is_active = False`, and the code's comment calls that "Already deleted". The list has an `is_active` filter, default `True`, so `?is_active=false` shows such templates, and `PUT` with `is_active: true` brings one back. Things of a soft-deleted parent are hidden by the parent's state. `POST /expense-orders/from-template/{id}/` already refuses an inactive template with 400 `Template is inactive`.
**What happens today:** After `DELETE`: `GET /order-templates/{id}/` answers 200, `GET …/items/` lists its lines, and a line can be added or changed. (Verified.)
**Example:** "Office rent" is deleted. It is gone from the default list. `GET /order-templates/12/items/` still returns its three lines, and it can be switched back on.
**Rules affected:** `OrderTemplateDAO.get_by_id_and_workspace` R3, `get_by_template` R5, `OrderTemplateItemDAO.get_by_id_and_workspace` R3
**Suggested answer:** `intended — is_active is an on/off switch with an API to reverse it, not a soft delete, so HR-4 and the hidden-parent decision do not apply; the two by-id reads are raw anyway`. It cannot make an order: the 400 above stands. Alternative: `bug — an inactive template answers 404 and its lines are hidden unless include_deleted is given`, which would have to allow for the `?is_active=false` list.
**Answer:** intended — is_active is an on/off switch with an API to reverse it, not a soft delete, so HR-4 and the hidden-parent decision do not apply; the two by-id reads are raw anyway
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): rules unchanged. Rules: `OrderTemplateDAO.get_by_id_and_workspace` R3 ✅, `get_by_template` R5 ✅, `OrderTemplateItemDAO.get_by_id_and_workspace` R3 ✅.

### O1. Setting a template line's price to 0 leaves the old subtotal — 🐞 BUG-1226
**Background:** A line stores `unit_price` and `line_subtotal`. `OrderTemplateManager.update_item` recomputes the subtotal when either quantity or price is sent, using `update_dict.get('unit_price') or record.unit_price or 0`, so a price of 0 counts as "not sent" and falls back to the old price. This is the manager's code, noted here because this DAO's spec found it, and it is money.
**What happens today, verified:** A line of 2 × 10.00 has subtotal 20.00. `PUT` with `unit_price: 0` stores `unit_price = 0.00` and leaves `line_subtotal = 20.00`.
**Example:** A template line is made free. It reads 0.00 each, 20.00 in total. An expense order made from the template copies the quantity and price, not the subtotal, so the wrong figure stays on the template.
**Rules affected:** none here; the rule goes in the order template manager's spec.
**Suggested answer:** `bug — a price of 0 is a price: the subtotal is quantity × 0 = 0`.
**Answer:** bug — a price of 0 is a price: the subtotal is quantity × 0 = 0
**Resolution:** owner's answer 2026-11-02: 🐞 BUG-1226 (pattern `falsy-zero-treated-as-missing`). The rule goes in the order template manager's spec, FU-1 (d). Rules here: none.

## Overview
This module holds two DAOs for expense order templates: `OrderTemplateDAO` for templates and `OrderTemplateItemDAO` for their lines. Both are called only by `OrderTemplateManager`, reached by `/order-templates/` and by `create_expense_order_from_template`. Each has a workspace-filtered read; they write nothing of their own, and creates and updates are the base's. There is no `is_deleted`: `delete_template` sets `is_active = False`.

**Callables:** 4 specified · 4 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts:**
- `order_templates` (`app.models.order_template.OrderTemplate`): `workspace_id` NOT NULL, FK CASCADE. `template_name` String(255) NOT NULL, no unique constraint. `is_active` Boolean NOT NULL, Python default `True`. `expense_category` String(100) nullable, no check. `cost_center_id` Integer nullable, **no foreign key**: a factory or department id, depending on the category. `account_id` FK `accounts.id` RESTRICT. `default_approver_id`, `created_by`, `updated_by` FK `profiles.id` SET NULL. `created_at` naive, Python default `utcnow`, no database default. `updated_at` nullable, Python `onupdate`. Referenced by `order_template_items` (CASCADE) and `expense_orders.order_template_id` (SET NULL).
- `order_template_items` (`…order_template_item.OrderTemplateItem`): `workspace_id` NOT NULL, FK CASCADE. `order_template_id` NOT NULL, FK CASCADE. `line_number` Integer NOT NULL, **no unique constraint**. `quantity` `Numeric(15, 2)` NOT NULL, default 1. `unit_price`, `line_subtotal` `Numeric(15, 2)` nullable. No trigger on either table.
- The database does not require an item's `workspace_id` to be its template's.

**Notes for the test designer:**
- Use the singletons `order_template_dao` and `order_template_item_dao`. Every parameter after `db` is keyword-only (a positional call raises `TypeError`).
- Workspaces from `tests/unit/factories.py`; build rows directly, and give `created_at` explicitly, with distinct values unless the case is about a tie.
- **The ties (BUG-1210, BUG-1211):** several rows of one `created_at`, or one `line_number`, then update an early row, flush, `db.expire_all()`. Today's order rests on physical row order: write the case to the intended result and mark it **non-strict** xfail.
- **Database errors:** wrap calls expected to raise `DataError` in `with db.begin_nested():` inside `pytest.raises(...)`.

## Not specified
- `order_template_dao`, `order_template_item_dao` — module-level singletons, no logic.
- Inherited `BaseDAO` methods of both DAOs — `tests/unit/dao/base.spec.md`. `OrderTemplateDAO.get_by_workspace` replaces the base method, so **BUG-100's fix does not reach it**, and `get_multi` has no caller. `remove` has no caller on either DAO: on a template with items it would raise `IntegrityError` 23502, because the ORM empties `order_template_id` before the database's `CASCADE` can run (verified). `OrderTemplateItemDAO.get_by_workspace` is the base method, with no caller.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Order template manager** (`app/managers/order_template_manager.py`, not yet specified) | (a) **BUG-1216 (HR-16), logged:** `create_template` and `update_template` store `cost_center_id` and `default_approver_id` unchecked (verified with another workspace's department, an unknown id and a non-member); the expense order made from such a template then fails with 404 `Selected department not found`. BUG-1014 is the account. (b) `expense_category` takes any text (`"garbage"` stored, verified): validate as BUG-360 did. (c) `update_template` stamps `updated_by` on every call (HR-9, read). (d) **BUG-1226, logged:** in `update_item`, a `unit_price` of 0 gives a subtotal of 0 (O1). (e) `OrderTemplateCreate` has no trim or blank check on `template_name` (HR-1, read). | reading the callers |

---

## `OrderTemplateDAO.get_by_workspace(db, *, workspace_id, is_active=None, expense_category=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `OrderTemplateManager.list_templates` ← `GET /order-templates/`, which passes `is_active` default `True`: the `None` default is not reachable from the API)

**Purpose:** One workspace's templates, newest first, with two optional filters.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `workspace_id` | int | equality on the row's `workspace_id` |
| `is_active` | `bool` \| `None` | `None` = both |
| `expense_category` | `str` \| `None` | `None` or `""` = no filter; otherwise compared exactly |
| `skip` | int, default `0` | not validated |
| `limit` | int, default `100` | not validated |

**Returns:** a `list` of `OrderTemplate` (possibly empty).

**Rules:**
- **R1.** Only rows of that workspace are returned. An unknown workspace, or one with no templates, returns `[]`.
- **R2.** `is_active=None` returns active and inactive rows; `True` or `False` only those.
- **R3.** A non-empty `expense_category` keeps rows equal to it exactly: case-sensitive, no trimming, no wildcards. `"factory"` does not find `"Factory"`; `" "` and `"%"` return `[]`.
- **R4.** `expense_category=None` and `""` both apply no filter.
- **R5.** [BUG-1210] (HR-6) Rows are ordered by `created_at` descending, then `id` descending, before `skip` / `limit`, so consecutive pages neither repeat nor miss a row. *(Today: `created_at` only. Verified: with one timestamp, paging one row at a time repeated one row and missed another.)*
- **R6.** Filters combine (AND) and apply before `skip` / `limit`.
- **R7.** At most `limit` rows after `skip`; with the defaults at most 100: given 101 rows, 100; with `limit=1000`, 101.
- **R8.** `limit=0`, or `skip` past the end, returns `[]`. A negative `limit` or `skip` raises (see Errors).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## `OrderTemplateDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by every by-id method of `OrderTemplateManager`)

**Purpose:** One template of a workspace. A line-for-line copy of the base method.

**Returns:** the row, or `None`.

**Rules:**
- **R1.** The row with that id in that workspace is returned.
- **R2.** Another workspace's id, or an unknown id, returns `None`.
- **R3.** ✅ (Q1) `is_active` is not looked at: an inactive template is returned.

**Errors:** none. **Side effects:** none

---

## `OrderTemplateItemDAO.get_by_template(db, *, order_template_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `OrderTemplateManager.get_items` ← `GET /order-templates/{id}/items/`, `create_expense_order_from_template`; `add_item`, for the next line number)

**Purpose:** All lines of one template, in line order. Not paged.

**Returns:** a `list` of `OrderTemplateItem` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `order_template_id` and that `workspace_id`, all of them. A template with no lines, or an unknown template, returns `[]`.
- **R2.** [BUG-1211] (HR-6) Ordered by `line_number` ascending, then `id` ascending. Lines stored out of order come back `1, 2, 3`. *(Today: `line_number` only. Verified: with one number the order changed after an update.)*
- **R3.** A call with another workspace returns `[]`.
- **R4.** Workspace isolation follows the row: only the item's own `workspace_id` is compared, not the template's. A row with `workspace_id` B on a template of A is returned for B and not for A. (HR-16: invalid data. Nothing writes it: the manager sets both.)
- **R5.** ✅ (Q1) The template's state is not looked at: the lines of an inactive template are returned.

**Errors:** none. **Side effects:** none

---

## `OrderTemplateItemDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `OrderTemplateManager.update_item`, `remove_item`)

**Purpose:** One line of a workspace.

**Returns:** the row, or `None`.

**Rules:**
- **R1.** The row with that id in that workspace is returned.
- **R2.** Another workspace's id, or an unknown id, returns `None`.
- **R3.** ✅ (Q1) The template's state is not looked at: a line of an inactive template is returned.

**Errors:** none. **Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 18 | keyword-only parameters; defaults | Notes; `get_by_workspace` R2, R4, R7 |
| 19 | workspace | `get_by_workspace` R1 |
| 20–21 | `is_active is not None`: filter / both | `get_by_workspace` R2, R6 |
| 22–23 | `if expense_category:` `None` / `""` skip; exact match | `get_by_workspace` R3, R4, R6 |
| 24 | `created_at` desc, no tie-break (BUG-1210); offset / limit | `get_by_workspace` R5, R7, R8, Errors |
| 27 | id AND workspace; no `is_active`; `.first()` | `OrderTemplateDAO.get_by_id_and_workspace` R1, R2, R3 |
| 32 | template AND workspace; `line_number`, no tie-break (BUG-1211); no parent state | `get_by_template` R1–R5 |
| 35 | id AND workspace; no parent state; `.first()` | `OrderTemplateItemDAO.get_by_id_and_workspace` R1, R2, R3 |
| 38–39 | module singletons | Not specified |
