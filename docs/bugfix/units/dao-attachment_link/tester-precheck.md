# Tester pre-check: dao-attachment_link (2026-11-27)

Source `app/dao/attachment_link.py`. Searched all of `tests/` for `1432`,
`1433` and `1434` (with and without the `BUG-` prefix, helper constants
included: the service file uses `X1434 = pytest.mark.xfail(...)`). Twelve
markers in three files:

- `tests/unit/dao/test_attachment_link.py` (cards in `attachment_link.cases.md`): 7
- `tests/unit/managers/test_attachment_manager.py` (cards in `attachment_manager.cases.md`): 4
- `tests/unit/services/test_attachment_service.py` (cards in `attachment_service.cases.md`): 1

The other mentions (`attachment_markup_manager`, `mobile_upload_session_manager`
notes; `purchase_order_service.verify.md` line numbers 1432–1439;
`sales_service.spec.md` "#1434284") are not markers.

Run before any fix (2026-11-27, the 7 DAO markers plus the 5 caller tests):
12 xfailed, 1 xpassed (ALK-GL-12, non-strict; its card says physical order
can match by accident). Every strict one fails today.

## BUG-1432: `get_attachments_for_entity` R6 (uploaded_at desc, then id desc)

| Test | File | Card | Strict | Checks | Verdict |
|---|---|---|---|---|---|
| `test_alk_ga_28__on_a_tie_the_highest_id_comes_first_when_the_lowest_id_was_updated` | dao | ALK-GA-28 | no | A, B, C tied (server `now()`, one transaction), D a day older, seqscan, A updated; expects `[C, B, A, D]` | right |
| `test_alk_ga_29__tied_rows_paged_one_at_a_time_neither_repeat_nor_miss_a_row` | dao | ALK-GA-29 | no | 4 tied rows, A updated, paged `limit=1`; expects `[D, C, B, A]` | right |
| `test_alk_ga_30__the_query_orders_by_uploaded_at_then_id_both_descending` | dao | ALK-GA-30 | yes | SQL: ORDER BY has `uploaded_at` before `.id`, two `DESC` | right |

Notes: `uploaded_at` is `server_default=func.now()`, so every row built in
the test shares one time; ids rise with build order. `order_part_of` cuts at
`LIMIT`, so the paging clause stays out. Today GA-30 fails on Then 3 (no
`.id`), as its card says. A fix of `uploaded_at DESC, id DESC` (with or
without `NULLS LAST`) passes all five Thens. The service's list tests read
this method but check sets, so they don't depend on the order. No
dependence on another open bug.

## BUG-1433: `get_links_for_attachment` R4 (id ascending)

| Test | File | Card | Strict | Checks | Verdict |
|---|---|---|---|---|---|
| `test_alk_gl_07__links_come_in_the_order_they_were_made_also_after_the_first_was_updated` | dao | ALK-GL-07 | no | L1, L2, L3, seqscan, L1 updated; expects `[L1, L2, L3]` | right |
| `test_alk_gl_08__the_query_orders_by_id_ascending` | dao | ALK-GL-08 | yes | SQL has `ORDER BY`, `.id` in it, no `DESC` | right |
| `test_alk_gl_12__links_come_in_id_order_not_entity_order` | dao | ALK-GL-12 | no | entity ids 9, 5, 7; expects id order (kills an `entity_id` sort) | right (XPASS today, allowed by its card) |
| `test_atcm_lg_08__first_link_is_lowest_link_id` | manager | ATCM-LG-08 | no | links built with ids XID(2) then XID(1); the ledger takes the lowest link id (`purchase_order`, 60) | right |
| `test_atcm_lg_09__links_query_is_ordered` | manager | ATCM-LG-09 | yes | every SELECT on `attachment_links` during `_append_attachment_ledger` has `ORDER BY` | right |
| `test_atcm_tr_07__w1_links_in_link_id_order` | manager | ATCM-TR-07 | no | same two links; `to_response.links` in link id order | right |

Notes: both manager paths (`_append_attachment_ledger`, `to_response`) read
links only through `get_links_for_attachment`, so the DAO fix reaches them;
the ledger insert's own statements are on `attachment_ledger`, which doesn't
match the `attachment_links` filter of LG-09. GL-08 has no LIMIT, so
`order_part` runs to the end; the WHERE columns come before ORDER BY and
can't satisfy `.id`. An explicit `ASC` passes Then 4. No dependence on
another open bug.

## BUG-1434: `count_linked_attachments_for_entity` R1 (failed not counted)

| Test | File | Card | Strict | Checks | Verdict |
|---|---|---|---|---|---|
| `test_alk_cn_01__failed_attachments_do_not_count_ready_and_pending_do` | dao | ALK-CN-01 | yes | one ready, one pending, one failed, one deleted; expects `2` (the rule's own example) | right |
| `test_atcm_cp_03__failed_not_counted` | manager | ATCM-CP-03 | yes | 24 ready + 3 failed; the capacity check (`>= 25`) does not refuse | right |
| `test_atsv_l_08__failed_attachments_do_not_use_a_place` | service | ATSV-L-08 | yes | one ready, one failed on a machine; list shows the ready one, `slot_count == 1` | right |

Notes: the companion ALK-CN-02 (pending counts, deleted never: R1a) passes
today and must still pass, so a fix that also drops `pending` is caught.
CP-03 would also pass if the count left out `pending`, but CN-02 covers that.
L-08's Then 1 passes today; it fails on Then 2 (`slot_count` 2), as its card
says. L-08 lists a machine, so BUG-1870 (private projects) does not reach it.

## Result

All three bugs go ahead. No wrong tests; nothing added to
`docs/bugfix/wrong-tests.md`; brief unchanged.

For the flip check: after the fix, the 7 DAO markers and the 5 caller
markers (ATCM-CP-03, LG-08, LG-09, TR-07, ATSV-L-08) all belong to this
unit and come off together. Each names one bug only.
