# Tester pre-check: dao-item_tag_assignment

Date: 2026-11-28. Base: main checkout (`app/dao/item_tag_assignment.py` same as `origin/main`).
Run: `pytest --runxfail -rf` on the 8 target tests against `bf_dao_item_tag_assignment_test`;
all 8 fail today, each on the line its card names.

**Verdict: both bugs go ahead. No wrong tests.**

## BUG-932 (`get_tags_for_item` R4)

| Test | File | Strict | Fails today on | Verdict |
|---|---|---|---|---|
| `test_ita_tfi_12__names_that_differ_only_in_case_come_back_in_id_order_then_the_other` | `tests/unit/dao/test_item_tag_assignment.py` | no | Then 2 (got 73, 74, 75, 76 = id order; want 74, 75, 73, 76) | right |
| `test_ita_tfi_13__two_tags_with_the_same_name_come_back_lower_id_first` | same | no | Then 2 (got 83, 82; want 82, 83) | right |
| `test_ita_tfi_14__the_tags_of_one_item_query_asks_for_name_case_insensitive_then_id` | same | yes | Then 2 (no `ORDER BY`) | right |
| `test_ism_dp_09__tag_read_has_order_by` | `tests/unit/services/test_item_summary_service.py` | yes (`xf("BUG-932")`) | Then 2 (the one select on `item_tag_assignments` has no `ORDER BY`) | right |

- TFI-12 / 13 check exactly R4's example (name case-insensitive, then id; system tag "Charlie" not first) and nothing else. TFI-12's data differs from both id-ascending and id-descending order, so it cannot pass by accident; non-strict is because physical order is not deterministic (card says so).
- TFI-14 is a SQL-text check: `lower(item_tags.name)` and `item_tags.id` in the text after `ORDER BY`. A normal ORM fix (`func.lower(ItemTag.name).asc(), ItemTag.id.asc()`, the `app/dao/item_tag.py` convention given in the brief) passes it. **Risk for the systems engineer:** a case-insensitive collation (`collate(...)`), `ilower`, or a raw `text()` sort would satisfy the rule but fail this line; the cases file's gap note 3 already records this choice.
- ISM-DP-09 only requires an `ORDER BY` on every select touching `item_tag_assignments` during the summary; today there is exactly one such select (the DAO's). Any fix passes it.

## BUG-933 (`get_tags_for_items` R6)

| Test | File | Strict | Fails today on | Verdict |
|---|---|---|---|---|
| `test_ita_tfs_17__names_that_differ_only_in_case_come_back_in_id_order_then_the_other` | `tests/unit/dao/test_item_tag_assignment.py` | no | Then 2 (got "alpha" before "Alpha": 54, 53, 52, 55; want 53, 54, 52, 55) | right |
| `test_ita_tfs_18__two_tags_with_the_same_name_come_back_lower_id_first` | same | no | Then 2 (got 62, 61; want 61, 62) | right |
| `test_ita_tfs_19__the_tags_of_items_query_asks_for_name_case_insensitive_then_id` | same | yes | Then 4 (`ORDER BY item_tag_assignments.item_id, item_tags.name`, no `lower(...)`) | right |
| `test_its_p_17__pass_through_bug_933_an_items_tags_come_by_name_then_id` | `tests/unit/services/test_item_service.py` | no | Then 2 (got 45, 44, 43; want 44, 45, 43) | right |

- Same judgment as BUG-932. TFS-19 asserts the presence of the two keys, not their position, so keeping `item_id` first (harmless, grouping is done in Python) passes; same SQL-text risk as TFI-14.
- TFS-17 is non-strict because a `C`-collation server would order capitals first and XPASS while the bug is there (card note); TFS-19 is the strict alarm.
- ITS-P-17 is a pass-through check of `get_items_page` R2 ("BUG-932 / BUG-933 order"); right.
- None of the 8 depends on another unfixed bug.

## Outside this unit

- **BUG-1486** (`app/dao/account_tag_assignment.py`, `get_tags_for_account`): same pattern and same intended order (cites BUG-932 as precedent). Good candidate for a later unit; reuse this fix's form.
- Every caller test that reads `get_tags_for_item(s)` without an order tag compares tags as sets (spec's designer note), so the flip check should show only these tests changing. The item manager has no BUG-932 / BUG-933 tests (FU-1 (f): pass-throughs).
- The fix changes the order of the tags `ItemManager.update_item` / `delete_item` iterate when lowering counters; order does not matter there (one counter per tag), but the systems engineer should confirm.
