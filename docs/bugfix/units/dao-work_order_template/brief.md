# Fix brief: dao-work_order_template

## 1. Unit

| | |
|---|---|
| Slug | `dao-work_order_template` |
| Source file | `app/dao/work_order_template.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-work_order_template` |
| Branch | `bugfix/dao-work_order_template` (from `origin/main`) |
| Risk | `normal` (BUG-2330 and BUG-2331 are trivial-list patterns; BUG-2332 `join-ignores-soft-deleted` is not on the list) |

## 2. Bugs

### BUG-2330: Work order template list repeats and misses rows when timestamps tie
- **Pattern:** `tied-timestamp-no-tiebreak`
- **Where:** `WorkOrderTemplateDAO.get_by_workspace`; reached through `GET /work-order-templates/`.
- **Today:** Ordered by `created_at` only; `created_at` is the transaction's `now()`, so templates made in one request share it (verified).
- **Intended:** `created_at` descending, then `id` descending, before `skip` / `limit` (HR-6; same as BUG-1210). This method replaces the base one, so a fix in the base DAO does not reach it.

### BUG-2331: A template's default approvers have no order
- **Pattern:** `unordered-pagination`
- **Where:** `WorkOrderTemplateApproverDAO.get_by_template`; reached through `GET /work-order-templates/{id}/approvers/` and `create_work_order_from_template`.
- **Today:** No `ORDER BY`; the list is shown and is the order a generated work order receives its approvers.
- **Intended:** `id` ascending, the order they were chosen in (HR-6, standing decision: a missing `ORDER BY` is a bug).

### BUG-2332: Plan-day run reaches templates through a deleted factory section
- **Pattern:** `join-ignores-soft-deleted`
- **Where:** `WorkOrderTemplateDAO.list_recurring_due`; reached through `POST /work-order-templates/generate-drafts/`.
- **Today:** The `factory_id` scope joins `factory_sections` without `is_deleted`: a template whose default section is deleted still matches through that section's factory (verified); a section run naming a deleted section still filters by it (read).
- **Intended:** HR-4: a deleted default section neither matches nor filters: such a template is not chosen by a factory run, and a section run naming a deleted section chooses nothing; templates with no section still match a factory run (decided by Claude under the reviewer's delegation (2026-11-06)). The template rows are untouched; they match again if the section is restored.

## 3. Intended behaviour (spec rules, copied)

### `WorkOrderTemplateDAO.get_by_workspace(db, *, workspace_id, is_active=None, work_order_type_id=None, skip=0, limit=100)`
One workspace's templates, newest first, with two optional filters. Returns a list of `WorkOrderTemplate` (possibly empty).

- **R1.** Only rows of that workspace are returned. An unknown workspace, or one with no templates, returns `[]`.
- **R2.** `is_active=None` returns active and inactive rows; `True` / `False` only those.
- **R3.** A non-zero `work_order_type_id` keeps rows of that type only. A type of another workspace returns `[]`.
- **R4.** `work_order_type_id=None` and `0` apply no filter.
- **R5.** [BUG-2330] (HR-6) Rows are ordered by `created_at` descending, then `id` descending, before `skip` / `limit`; consecutive pages neither repeat nor miss a row. (Today: `created_at` only, and rows made in one transaction share it.)
- **R6.** Filters combine (AND) and apply before `skip` / `limit`.
- **R7.** At most `limit` rows after `skip`; with the defaults at most 100 (101 rows -> 100; `limit=1000` -> 101).
- **R8.** `limit=0` or `skip` past the end returns `[]`; a negative `limit` raises `DataError` pgcode `2201W`, a negative `skip` `2201X`.

### `WorkOrderTemplateDAO.list_recurring_due(db, *, workspace_id, target_date, factory_section_id=None, factory_id=None)`
The active recurring templates of a workspace whose next run is due on `target_date`, optionally limited to a section or factory. Returns a list of `WorkOrderTemplate`, unpaged, in no guaranteed order.

Inputs: `factory_section_id` `None` = no section filter; any other value (`0` included) = equality on `default_factory_section_id`. `factory_id` `None` = no factory filter; any other value (`0` included) = R5, R5b.

- **R1.** Only rows of that workspace, with `is_active = True` and `is_recurring = True`. An inactive or non-recurring template is never returned.
- **R2.** Due means: `next_generation_date` is set **and** on or before `target_date`. Equal -> returned; one day after -> not; `NULL` -> not. An overdue template (date long past) is returned.
- **R3.** And the program has not ended: `recurrence_end_date` is `NULL`, or `target_date` is on or before it. `target_date` equal to the end date -> returned; one day after -> not.
- **R4.** With `factory_section_id`, only templates whose `default_factory_section_id` equals it. A template with no section is not returned.
- **R5.** With `factory_id`, a template is returned if it has **no** default section, or its default section belongs to that factory. A template whose section is in another factory is not returned.
- **R5a.** [BUG-2332] (HR-4) A soft-deleted default section neither matches nor filters: with `factory_id`, a template whose default section has `is_deleted = True` is **not** returned (whatever factory the section had); with `factory_section_id` naming a deleted section, nothing is returned. A template with no section still matches a factory run. (Today: the deleted section's factory still matches and the section id still filters.)
- **R5b.** `factory_id = 0` (or any id that is no factory) is a filter, not "no filter": only due templates with **no** default section are returned (the check is `is not None`). Likewise `factory_section_id = 0` returns `[]` (R4).
- **R6.** Both scopes given: both apply (AND).
- **R7.** All matching rows are returned, no cap. The due / end checks of R2, R3 run after loading every active recurring template of the scope; nothing is cut before them.

### `WorkOrderTemplateApproverDAO.get_by_template(db, *, work_order_template_id, workspace_id)`
Returns a list of `WorkOrderTemplateApprover`, unpaged.

- **R1.** The rows with that template id and that `workspace_id`; an unknown template, or another workspace, returns `[]`. Isolation follows the row's own `workspace_id`.
- **R2.** [BUG-2331] (HR-6) Ordered by `id` ascending. (Today: no `ORDER BY`.)
- **R3.** The template's `is_active` and the approver's membership are not looked at: a row for a user who has since left the workspace is returned.

Facts: `factory_sections` has an `is_deleted` column (soft delete); a factory's own deleted state is not part of this unit. All parameters after `db` stay keyword-only. The other methods of the file (`get_by_id_and_workspace` on the template and item DAOs, `WorkOrderTemplateItemDAO.get_by_template`, `delete_all_for_template`) do not change.

## 4. Rules that apply

- **HR-4. Soft-deleted rows are hidden unless asked for.** Lists/searches exclude soft-deleted rows by default. Filters, joins and searches through related rows ignore related rows that are soft-deleted (e.g. a deleted tag neither filters nor matches). Scope: enforced in managers and module-specific DAO query methods; the generic `BaseDAO` methods stay raw. (`is_active` on templates is an on/off switch with a restore endpoint, not a soft delete; it is not affected.)
- **HR-6. Every paged or top-N result has a stable order.** Default: name case-insensitive ascending, then `id` ascending. Generic `BaseDAO` lists only guarantee `id` ascending (stable paging). Standing decision: no order recipe counts as deterministic unless it ends in `id`. Where a list already has a chosen order (here: newest first), keep it and add `id` as the last key, in the direction given in the Intended text.
- No owner answer (OQ-n) touches these bugs.

## 5. Scope

- May change: `app/dao/work_order_template.py` only.
- No migration, no schema or API change.

## 6. Out of scope (leave alone)

- BUG-2333 (`created_at` / `updated_at` from the database clock): the fix is in `app/models/work_order_template.py`.
- BUG-1015, BUG-1228, BUG-360…363 and everything about what a template puts into a work order: `app/managers/work_order_template_manager.py`.
- Machines of a deleted section chosen by the generation step (`resolve_template_machine_ids`): the work order generation util, not this file.
