# Fix brief: dao-order_template

## 1. Unit

| | |
|---|---|
| Slug | `dao-order_template` |
| Source file | `app/dao/order_template.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-order_template` |
| Branch | `bugfix/dao-order_template` (from `origin/main`) |
| Risk | `trivial` (both bugs are list-order patterns on the trivial list; one file, no migration, no API shape change) |

## 2. Bugs

### BUG-1210: Template list repeats and misses rows when timestamps tie
- **Pattern:** `tied-timestamp-no-tiebreak`
- **Where:** `OrderTemplateDAO.get_by_workspace`; reached through `GET /order-templates/`.
- **Today:** Ordered by `created_at` only. Five rows of one timestamp, one updated: paging one row at a time gave `[2079], [2079], [2082], [2083], [2080]`, so one row twice and one never.
- **Intended:** `created_at` descending, then `id` descending, before `skip` / `limit` (HR-6). This method replaces the base one, so a fix in the base DAO does not reach it.

### BUG-1211: Template lines of one line number have no order
- **Pattern:** `unordered-pagination`
- **Where:** `OrderTemplateItemDAO.get_by_template`; reached through `GET /order-templates/{id}/items/` and `create_expense_order_from_template`.
- **Today:** Ordered by `line_number` only, and `line_number` is not unique: two concurrent `add_item` calls can give two lines one number. With one number the order changed after an update.
- **Intended:** `line_number` ascending, then `id` ascending (HR-6).

## 3. Intended behaviour (spec rules, copied)

### `OrderTemplateDAO.get_by_workspace(db, *, workspace_id, is_active=None, expense_category=None, skip=0, limit=100)`
One workspace's templates, newest first, with two optional filters. Returns a list of `OrderTemplate` (possibly empty).

- **R1.** Only rows of that workspace are returned. An unknown workspace, or one with no templates, returns `[]`.
- **R2.** `is_active=None` returns active and inactive rows; `True` or `False` only those.
- **R3.** A non-empty `expense_category` keeps rows equal to it exactly: case-sensitive, no trimming, no wildcards. `"factory"` does not find `"Factory"`; `" "` and `"%"` return `[]`.
- **R4.** `expense_category=None` and `""` both apply no filter.
- **R5.** [BUG-1210] (HR-6) Rows are ordered by `created_at` descending, then `id` descending, before `skip` / `limit`, so consecutive pages neither repeat nor miss a row. (Today: `created_at` only.)
- **R6.** Filters combine (AND) and apply before `skip` / `limit`.
- **R7.** At most `limit` rows after `skip`; with the defaults at most 100: given 101 rows, 100; with `limit=1000`, 101.
- **R8.** `limit=0`, or `skip` past the end, returns `[]`. A negative `limit` or `skip` raises `sqlalchemy.exc.DataError` (pgcode `2201W` for `LIMIT`, `2201X` for `OFFSET`), as today.

### `OrderTemplateItemDAO.get_by_template(db, *, order_template_id, workspace_id)`
All lines of one template, in line order. Not paged. Returns a list of `OrderTemplateItem` (possibly empty).

- **R1.** Returns the rows with that `order_template_id` and that `workspace_id`, all of them. A template with no lines, or an unknown template, returns `[]`.
- **R2.** [BUG-1211] (HR-6) Ordered by `line_number` ascending, then `id` ascending. Lines stored out of order come back `1, 2, 3`. (Today: `line_number` only.)
- **R3.** A call with another workspace returns `[]`.
- **R4.** Workspace isolation follows the row: only the item's own `workspace_id` is compared, not the template's.
- **R5.** The template's state is not looked at: the lines of an inactive template are returned.

All parameters after `db` stay keyword-only. The other two methods of the file (`get_by_id_and_workspace` on both DAOs) do not change.

## 4. Rules that apply

- **HR-6. Every paged or top-N result has a stable order.** Default: name case-insensitive ascending, then `id` ascending. Score-ranked results break ties the same way. Generic `BaseDAO` lists only guarantee `id` ascending (stable paging); choosing a display order is the manager's job. Standing decision: no order recipe counts as deterministic unless it ends in `id`. Where a list already has a chosen order (here: newest first, line number), keep it and add `id` as the last key, in the direction given in the Intended text.
- No owner answer (OQ-n) touches these bugs.

## 5. Scope

- May change: `app/dao/order_template.py` only.
- No migration, no schema or API change.

## 6. Out of scope (leave alone)

- BUG-1226 (a line price of 0 keeps the old subtotal), BUG-1216 and BUG-1014 (links of another workspace on templates): they belong to `app/managers/order_template_manager.py`, not this file.
- BUG-100 (base DAO list order) belongs to `app/dao/base.py`.
