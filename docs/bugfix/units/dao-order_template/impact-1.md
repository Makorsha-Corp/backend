# Impact review: dao-order_template, round 1 (2026-11-27)

Diff: `git -C E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-order_template diff origin/main -- app alembic`.
Two lines in `app/dao/order_template.py`; nothing in `alembic/`. Worktree has no other changes.

- `OrderTemplateDAO.get_by_workspace`: `ORDER BY created_at DESC` becomes `created_at DESC, id DESC`, still before `offset` / `limit` (BUG-1210, spec R5).
- `OrderTemplateItemDAO.get_by_template`: `ORDER BY line_number` becomes `line_number, id` (both ascending) (BUG-1211, spec R2).

## Upstream

| Caller | Use | Effect |
|---|---|---|
| `OrderTemplateManager.list_templates` (`app/managers/order_template_manager.py:78`) ← `GET /order-templates/` | passes the list through | Tied rows now come back in a fixed order; pages no longer repeat or miss a row. Nothing relies on the old (undefined) tie order. |
| `OrderTemplateManager.add_item` (`:102`) | `max(line_number) + 1` over the lines | Order-independent. Unchanged. |
| `OrderTemplateManager.get_items` (`:143`) ← `GET /order-templates/{id}/items/` and `ExpenseOrderManager.create_expense_order_from_template` | passes the list through | Fixed order on ties. |

No other module imports `order_template_dao` / `order_template_item_dao` (the `work_order_template` DAOs with the same method names are separate classes, in another unit). Return types, None vs `[]`, raised errors and signatures (keyword-only) are unchanged.

### `create_expense_order_from_template` (tester pre-check "Outside this unit")

`app/managers/expense_order_manager.py:632` re-sorts the lines with `sorted(tpl_items, key=lambda x: x.line_number)`. Python's `sorted` is **stable**: lines that tie on `line_number` keep the order they came in, which is now `id` ascending from the DAO. So the DAO fix reaches the expense order too: lines of one number are copied in `id` order, giving the order's own `line_number` 1, 2, 3 … deterministically. The re-sort is redundant but harmless; no change is needed there and no separate bug is warranted. The manager spec's FU-1 remark ("BUG-1211 applies there too") is satisfied by this fix. Not money: only the order of copied lines changes, not quantities, prices or totals.

## Downstream

Plain `SELECT` with `ORDER BY`; no locks, no flush, no commit. `id` is the primary key (indexed). No transaction-contract (TC1–TC6) effect.

## API contract

No contract change. Same status codes, fields and messages; only the order of rows that tie on `created_at` (templates) or `line_number` (lines) becomes fixed. No frontend work.

## Database

No migration, constraint or index. No check script needed.

## Neighbouring bugs

- BUG-100 (base DAO order): not reached; these methods build their own query.
- BUG-1226, BUG-1216, BUG-1014 (order template manager): untouched, no clash.
- Duplicate `line_number` from concurrent `add_item` (fixer's "seen, not fixed"): already the root cause named in BUG-1211's "Today"; a unique constraint would be a `db-change` unit of its own. Not blocking.
- BUG-1200 (approver `get_by_order` tie-break): same pattern, other files; no interaction.

## Shortcuts / scope

None. Both changes are the rule as written (HR-6: chosen order kept, `id` last, in the given direction). Nothing outside the two bugs changed. Matches the tester pre-check expectations (two keys each, `id` last, desc/asc as stated).

## Risk tag

`trivial` holds: one file, no migration, no contract change, no frontend PR, not money/stock/order-workflow/security, patterns `tied-timestamp-no-tiebreak` and `unordered-pagination` on the trivial list.

## Verdict

**APPROVE.** To the tester.
