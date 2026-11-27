# Fix notes: dao-work_order_template

## Round 1 (2026-11-27)

### Changed
File: `app/dao/work_order_template.py` (only file touched).

- **BUG-2330**: `WorkOrderTemplateDAO.get_by_workspace`: the `order_by` is now `desc(created_at), desc(id)`. Before, it was `desc(created_at)` only. Filters, `skip` and `limit` are unchanged.
- **BUG-2331**: `WorkOrderTemplateApproverDAO.get_by_template`: added `.order_by(WorkOrderTemplateApprover.id)` (ascending).
- **BUG-2332**: `WorkOrderTemplateDAO.list_recurring_due`:
  - Section scope (`factory_section_id is not None`): the equality filter stays. A second condition was added: `default_factory_section_id IN (SELECT id FROM factory_sections WHERE is_deleted = false)`. A run that names a deleted section now returns nothing.
  - Factory scope (`factory_id is not None`): the outer join is unchanged. The match branch is now `factory_id == :factory_id AND FactorySection.is_deleted = false`, so a template whose section is deleted no longer matches. The `default_factory_section_id IS NULL` branch is unchanged, so templates with no section still match.

### Why
- R5 (get_by_workspace): `id` is the last sort key, so rows with the same `created_at` always come out in the same order. Pages therefore never repeat or miss a row.
- R2 (approvers): `id` ascending is the order the approvers were chosen in.
- R5a (HR-4): a deleted section is left out of both scopes. The template rows themselves are not changed, so they match again as soon as the section is restored. R4, R5b and R6 still hold: `factory_section_id=0` returns `[]`, `factory_id=0` returns only templates with no section, and both scopes together combine with AND.

### Checks run (throwaway, rolled-back transaction, now deleted)
Setup: one factory with a live section and a deleted section, and three due recurring templates (section live, section deleted, no section).
- Factory run returned live and none.
- Run naming the deleted section returned `[]`.
- Run naming the live section returned live.
- Both scopes together returned live.
- `factory_id=0` returned none.
- No scope returned all three (unchanged).
- `get_by_workspace` paged with `limit=1`: the three templates shared one `created_at`, and the pages came back in `id` descending order with no repeats.
- The approver query ran (no approver rows, because profiles were not built).
- `import app.main` works and `ruff check` passes.

### Assumptions
- For the section scope I used an `IN (live section ids)` subquery instead of a second join. That way it cannot clash with the factory-scope join when both scopes are given.
- The live-section subquery is not limited to the workspace. Whether a template's section belongs to the right workspace is not part of this bug (HR-16). The workspace filter on the template already limits the result.
- The deleted state of the factory itself is not checked, as the brief says.

### Seen, not fixed
- None in this file beyond the out-of-scope items the brief lists.

### Risk
- Low. Callers of `list_recurring_due` (the generate-drafts endpoint) will now skip templates whose default section is deleted. That is the intended behaviour, but plan-day runs may make fewer drafts than before.
