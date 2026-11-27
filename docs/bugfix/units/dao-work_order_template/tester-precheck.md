# Tester pre-check: dao-work_order_template

Date: 2026-11-27. Source `app/dao/work_order_template.py`. Spec
`tests/unit/dao/work_order_template.spec.md`, cases
`tests/unit/dao/work_order_template.cases.md` (revision 2), tests
`tests/unit/dao/test_work_order_template.py`.

Search: `grep -rnE "233[012]" tests/` over every `.py` and `.md`. Markers use the
constants `R2330`, `R2331`, `R2332` (defined at the top of the test file). The
only tests that name these bugs are in the DAO test file. The work order
template manager cases name the bugs only to say they belong to the DAO: they use
distinct `created_at` values and set checks, so none of their tests depends on
these bugs.

Run today (`-k` on the 9 tests below, 2026-11-27): 8 xfailed, 1 xpassed
(AG-09, non-strict, as its card expects).

## BUG-2330: `get_by_workspace` order on tied `created_at` (R5)

| Test | Card | Strict | Today | Verdict |
|---|---|---|---|---|
| `test_wotp_gw_15__tie_highest_id_first_after_lowest_updated` | WOTP-GW-15 | no | xfail | right |
| `test_wotp_gw_16__tie_id_decides_over_other_columns` | WOTP-GW-16 | no | xfail | right |
| `test_wotp_gw_17__tied_rows_paged_neither_repeat_nor_miss` | WOTP-GW-17 | no | xfail | right |
| `test_wotp_gw_18__query_orders_by_created_at_then_id_desc` | WOTP-GW-18 | yes | xfail | right |

- GW-15, GW-16 and GW-17 tie three or five rows on `created_at` and expect `id`
  descending. GW-17 also checks paging (`skip=k, limit=1`), which is R5's "consecutive
  pages neither repeat nor miss a row". GW-15 and GW-17 move the lowest id physically
  last with an update, so today's physical order differs from the intended one.
- GW-18 checks the SQL: `created_at` before `.id`, exactly two `DESC`, exactly
  two keys. This is R5's recipe and nothing more. Today it fails on Then 4, as the
  card says.
- The primary key (`created_at` descending) is covered by GW-14 and GW-01, which
  pass today and must still pass.
- A correct fix (`created_at desc, id desc` before offset and limit) makes all four
  pass. A wrong direction on the tie-break fails GW-15/16/17 and GW-18 Then 6.
- Depends on no other open bug. BUG-2333 (database clock) is not involved:
  every row gets an explicit `created_at`.

## BUG-2331: approver `get_by_template` order (R2)

| Test | Card | Strict | Today | Verdict |
|---|---|---|---|---|
| `test_wotp_ag_08__out_of_order_ids_come_back_by_id` | WOTP-AG-08 | no | xfail | right |
| `test_wotp_ag_09__order_is_by_id_not_by_user` | WOTP-AG-09 | no | xpass (expected) | right |
| `test_wotp_ag_10__query_orders_by_id_ascending` | WOTP-AG-10 | yes | xfail | right |

- AG-08 inserts explicit ids out of order and updates the lowest, so today's
  physical order is 2, 3, 1. Intended is 1, 2, 3 (R2 `id` ascending).
- AG-09 passes today by chance (physical order equals id order). It guards against a
  fix that sorts by `user_id`. It is non-strict, so the XPASS is expected.
- AG-10 checks the SQL: an `ORDER BY` with `.id`, no `DESC`, one key only. "Ordered by
  `id` ascending" means `id` is the only key, so the one-key check stays within R2.
  Today it fails on Then 2, as the card says.
- Depends on no other open bug.

## BUG-2332: `list_recurring_due` through a deleted section (R5a)

| Test | Card | Strict | Today | Verdict |
|---|---|---|---|---|
| `test_wotp_rd_13__factory_run_skips_deleted_default_section` | WOTP-RD-13 | yes | xfail | right |
| `test_wotp_rd_14__section_run_naming_deleted_section_returns_nothing` | WOTP-RD-14 | yes | xfail | right |

- RD-13 runs factory F2, which holds S2 (live) and SD (`is_deleted True`). It expects the S2
  template and the template with no section, but not the SD template. That is all three
  clauses of R5a for a factory run, including "a template with no section still matches".
- RD-14 runs section SD and expects `[]`. That is R5a's "a section run naming a deleted
  section chooses nothing".
- Both compare sets (`idset` or `== []`), which is right because the rule guarantees no order.
- A correct fix makes both pass. Today both fail on Then 1, as the cards say.
- Depends on no other open bug. The factory's own deleted state is not part of the
  rule and not tested here. That matches the brief.

## Result

All 9 tests are right. There are no wrong tests and no entries in
`docs/bugfix/wrong-tests.md`. All three bugs stay in the unit. The brief is
unchanged (firewall: clean, re-run 2026-11-27).

Note for stage C: after the fix, remove the markers on all 9 tests (each names exactly
one of this unit's bugs). The flip check should show the 8 xfails turning into passes,
and AG-09 going from xpassed to passed.
