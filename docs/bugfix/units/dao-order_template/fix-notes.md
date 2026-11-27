# Fix notes: dao-order_template

## Round 1 (2026-11-27)

### Changed
- **BUG-1210**: `app/dao/order_template.py`, `OrderTemplateDAO.get_by_workspace`. The order went from `desc(created_at)` to `desc(created_at), desc(id)`, still before `offset`/`limit`.
- **BUG-1211**: `app/dao/order_template.py`, `OrderTemplateItemDAO.get_by_template`. The order went from `line_number` to `line_number, id` (both ascending).

### Why
Both lists now end in `id` (HR-6), so rows that tie on the first key always come back in the same order. Paging by `skip`/`limit` therefore cannot repeat or miss a row. The direction matches the Intended text: newest first then `id` descending for templates; line number then `id` ascending for lines. Filters, keyword-only signatures and the `get_by_id_and_workspace` methods are unchanged.

### Checks
- I compiled both queries through the real DAO methods with a stub session. The SQL ends in `ORDER BY order_templates.created_at DESC, order_templates.id DESC LIMIT .. OFFSET ..` and `ORDER BY order_template_items.line_number, order_template_items.id`.
- `import app.main` works. `ruff check app/dao/order_template.py` passes. `.scratch/` is deleted.

### Assumptions
- None beyond the brief.

### Seen, not fixed
- `line_number` is not unique per template. Two concurrent `add_item` calls can still store one number twice. This fix only makes the order of such lines stable. A unique constraint would need a migration and a data check, which is outside this unit's scope.

### Risk
- Very low. Only the order of tied rows changes.
