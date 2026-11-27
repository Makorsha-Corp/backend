# Tester pre-check: dao-order_template (2026-11-27)

Source `app/dao/order_template.py`. Tests: `tests/unit/dao/test_order_template.py`,
cards in `tests/unit/dao/order_template.cases.md`. Searched `tests/` for
`1210` and `1211` (with and without the `BUG-` prefix): the only markers are
the seven below. The manager tests (`order_template_manager`) only point to
the DAO cards and carry no marker for these bugs.

Run before any fix (2026-11-27): 6 xfailed, 1 xpassed (GT-09, non-strict;
its card says physical order usually matches without an update).

## BUG-1210: `OrderTemplateDAO.get_by_workspace` R5 (created_at desc, then id desc)

| Test | Card | Strict | Checks | Verdict |
|---|---|---|---|---|
| `test_otp_gw_17__on_a_tie_the_highest_id_comes_first_when_the_lowest_id_was_updated` | OTP-GW-17 | no | 3 rows at T11, lowest id updated; expects `[C, B, A]` (id desc) | right |
| `test_otp_gw_18__on_a_tie_the_id_decides_when_name_flag_and_category_would_each_sort_ot` | OTP-GW-18 | no | 3 tied rows whose name, flag and category each sort another way; expects id desc | right |
| `test_otp_gw_19__tied_rows_paged_one_at_a_time_neither_repeat_nor_miss_a_row` | OTP-GW-19 | no | 5 tied rows, one updated, paged `limit=1`; expects `[E, D, C, B, A]` (the bug row's own repro) | right |
| `test_otp_gw_20__the_query_orders_by_created_at_then_id_both_descending` | OTP-GW-20 | yes | SQL: ORDER BY has `created_at` then `.id`, two `DESC`, exactly two keys | right |

Notes: ids rise in creation order (one flush per row), so id desc is
`[C, B, A]`. `order_part_of` cuts at `LIMIT`, so the paging clause does not
leak into the checks. Today GW-20 fails on Then 4 (no `.id`), as the card
says; a fix of `created_at DESC, id DESC` (with or without `NULLS LAST`)
passes Then 1–7. Then 7 (exactly two keys) matches R5, which names exactly
this recipe. No dependence on another open bug: this method does its own
query, so BUG-100 (base DAO order) does not reach it.

## BUG-1211: `OrderTemplateItemDAO.get_by_template` R2 (line_number asc, then id asc)

| Test | Card | Strict | Checks | Verdict |
|---|---|---|---|---|
| `test_otp_gt_08__on_a_tie_the_lowest_id_comes_first_when_the_lowest_id_was_updated` | OTP-GT-08 | no | 3 lines of number 1, lowest id updated; expects `[A, B, C]` | right |
| `test_otp_gt_09__on_a_tie_the_id_decides_when_quantity_and_price_would_each_sort_otherw` | OTP-GT-09 | no | 3 tied lines whose quantity and price sort another way; expects id asc | right (XPASS today, allowed by its card) |
| `test_otp_gt_10__the_query_orders_by_line_number_then_id_ascending` | OTP-GT-10 | yes | SQL: ORDER BY has `line_number` then `.id`, no `DESC`, exactly two keys | right |

Notes: the query is not paged, so `order_part` runs to the end of the
statement; the WHERE columns (`order_template_id`, `workspace_id`) come
before ORDER BY and cannot satisfy `.id`. An explicit `ASC` still passes
Then 6. Today GT-10 fails on Then 4, as the card says. No dependence on
another open bug.

## Outside this unit (for the systems engineer)

`create_expense_order_from_template` in the expense order manager also sorts
lines by `line_number` alone (order_template_manager spec FU-1). It is not in
this file and has no test in this unit; fixing the DAO does not change it.

## Result

Both bugs go ahead. No wrong tests; nothing added to `docs/bugfix/wrong-tests.md`;
brief unchanged.
