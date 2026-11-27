# fix(order_template): BUG-1210, BUG-1211

Branch: `bugfix/dao-order_template` → `main`. Risk: `trivial`.

## Bugs

| ID | Title | Intended |
|---|---|---|
| BUG-1210 | Template list repeats and misses rows when timestamps tie | `OrderTemplateDAO.get_by_workspace`: `created_at` descending, then `id` descending, before `skip` / `limit` (HR-6) |
| BUG-1211 | Template lines of one line number have no order | `OrderTemplateItemDAO.get_by_template`: `line_number` ascending, then `id` ascending (HR-6) |

## The change

Two lines in `app/dao/order_template.py`. The template list now sorts newest first and, for templates made at the same moment, by highest id first, so paging can no longer show a template twice or skip one. Template lines now sort by line number and, for lines that share a number, by lowest id first. Nothing else changes.

The seven test markers for these two bugs are removed from `tests/unit/dao/test_order_template.py`, and both rows in `docs/testing/bugs.md` are marked `Fixed in bugfix/dao-order_template (PR pending)`.

## Impact (systems engineer, round 1: APPROVE)

- Upstream: `OrderTemplateManager.list_templates` (`GET /order-templates/`) and `get_items` (`GET /order-templates/{id}/items/`, `create_expense_order_from_template`) pass the list through. Only the order of tied rows becomes fixed. `add_item` uses `max(line_number) + 1`, which does not depend on order. The expense order manager re-sorts by `line_number` with Python's stable `sorted`, so it keeps the DAO's `id` order on ties.
- Downstream: a plain `SELECT ... ORDER BY` on the primary key. No locks, no flush, no transaction change.
- Database: no migration, constraint or index. No data-check script.
- Neighbouring bugs: BUG-100, BUG-1226, BUG-1216 and BUG-1014 are not touched. The non-unique `line_number` from concurrent `add_item` calls is still possible; a unique constraint would be a separate `db-change` unit.

## Contract note

No contract change. Same fields, status codes and messages. No frontend PR.

## Flip check

**CLEAN** against baseline `d5fea1c` (`docs/bugfix/units/dao-order_template/flipcheck.json`): **7 flipped as intended, 0 other changes, 0 notes.** The full suite after the fix had 24,423 tests: 18,425 passed, 5,900 xfailed, 97 xpassed, 1 skipped. The 7 that flipped are this unit's own tests: OTP-GW-17 to GW-20 (BUG-1210) and OTP-GT-08 to GT-10 (BUG-1211). The unit's test files (order template DAO, order template manager and expense order manager) pass: 540 passed, 188 xfailed.

## Good to auto-merge

**Good to auto-merge** (the owner merges). Reasons:
- trivial patterns: `tied-timestamp-no-tiebreak` (BUG-1210) and `unordered-pagination` (BUG-1211);
- one file (`app/dao/order_template.py`), two lines;
- no migration, no API contract change, no frontend PR;
- not money, stock, order workflow or security;
- flip check exact (see above);
- CI: the local full suite matches the baseline exactly. GitHub CI runs when the PR is opened and must be green before merging.

---
🤖 Generated with [Claude Code](https://claude.com/claude-code)
