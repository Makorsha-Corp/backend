# Tester pre-check: dao-machine_section_assignment

Date: 2026-11-27. Main checkout, before any fix. DB: `bf_dao_machine_section_assignment_test`.
Run: `pytest -o addopts="" --runxfail -rf -k "<the 8 target tests>"` over
`tests/unit/dao/test_machine_section_assignment.py`,
`tests/unit/managers/test_machine_section_assignment_manager.py`,
`tests/unit/managers/test_machine_manager.py` → 4 failed (the strict ones), 4 passed (the non-strict ones), 5.7 s.

Search: bare numbers `906` / `909` across `tests/**/*.py` (no helper constants; every marker carries the reason string inline), plus the caller test files (assignment manager, machine manager; factory section manager / services have no marker for these bugs).

## BUG-906 (get_by_section has no order) — tests RIGHT

| Test | File | Strict | Today (`--runxfail`) | Card's failing line | Verdict |
|---|---|---|---|---|---|
| `test_msa_gs_22__the_by_section_query_asks_the_database_for_an_order` | `tests/unit/dao/test_machine_section_assignment.py` | yes | fails at line 1183 (`"ORDER BY" in select`; SQL has only `LIMIT … OFFSET`) | Then 2 | right |
| `test_msa_gs_20__rows_come_back_by_id_ascending` | same | no | passes (physical order matched) | Then 2 | right |
| `test_msa_gs_21__a_middle_window_holds_the_second_and_third_row_by_id` | same | no | passes | Then 1 | right |
| `test_msa_cl_11__the_machine_ids_come_back_in_the_order_of_the_row_ids` | same | no | passes | Then 2 | right |
| `test_msm_clr_13__the_machine_ids_come_back_in_the_order_of_the_link_ids` | `tests/unit/managers/test_machine_section_assignment_manager.py` | no | passes | Then 2 | right |

- Rule: `get_by_section` R6 (`id` ascending before `skip` / `limit`, windows partition), `clear_for_section` R7 (ids follow that order); assignment manager `clear_for_section` R7 cites the same bug.
- The non-strict cards say the physical order can match by accident; today it did, for all four. That is allowed: the strict SQL-text card is the proof that the bug exists. They update row A1 to push it physically last; the intended order is by row id (CL-11 / CLR-13 deliberately use row ids rising in a different order than machine ids, so a sort by `machine_id` would fail them — good).
- **Note for the systems engineer / stage C:** GS-22 only checks that *an* `ORDER BY` is sent, not that it is `id`. Correctness of the column is carried by the four non-strict tests, which become plain tests once their markers are removed in stage C and must then pass. A raw `text("id")` order would also pass GS-22 (it still emits `ORDER BY`); no risk there. A Python-side sort after `.limit()` would fail GS-22 and break R6's paging — correctly rejected.

## BUG-909 (re-saving the same section re-creates the row) — tests RIGHT

| Test | File | Strict | Today (`--runxfail`) | Card's failing line | Verdict |
|---|---|---|---|---|---|
| `test_msa_up_03__re_saving_the_section_the_machine_already_has_leaves_its_row_untouched` | `tests/unit/dao/test_machine_section_assignment.py` | yes | fails at line 350 (`result.id == a1_id`: 21 vs 20) | Then 3 | right |
| `test_msm_set_08__re_saving_the_section_the_machine_already_has_leaves_its_link` | `tests/unit/managers/test_machine_section_assignment_manager.py` | yes | fails at line 358 (33 vs 32) | Then 3 | right |
| `test_mcm_u_73__re_sending_the_current_section_keeps_the_link_row` | `tests/unit/managers/test_machine_manager.py` | yes | fails at line 2861 (19 vs 18) | Then 3 | right |

- Rule: `upsert_for_machine` R3 (same `id`, `created_by`, `created_at`; nothing written); `set_assignment` R4 and `update_machine` R18 cite it.
- Each uses two profiles (U1 created the row, U2 re-saves) and checks returned id, re-read id, re-read `created_by == U1`, one row. `created_at` is not checked — correct, it is the transaction start time and cannot tell a re-created row apart (spec note). Nothing the spec does not require is checked. A correct DAO-only fix (return the existing row when its `factory_section_id` equals the argument) passes all three; the callers need no change.
- Companion tests that hold today and after the fix (`test_msa_up_04…`, `test_msm_set_09…`, `test_mcm_u_74…` — one row, right section, no event) keep passing with that fix. The R10 tests (loaded machine not refreshed) all move to a *different* section or clear, so the no-op path does not touch them.
- No dependency on another unfixed bug.

## Wrong tests

None. `docs/bugfix/wrong-tests.md` not touched.

## Outside this unit

- `test_mcm_u_75…` (BUG-971, machine manager: edit re-sending a left-over link to a deleted section) stays xfailed after BUG-909 — the manager refuses with 400 before the DAO is called. Expect no flip there.
- BUG-907 tests (10 001-row cap, DAO `clear_for_section` R4 and manager `clear_for_section` R3) are strict xfails that must **stay** xfailed in this unit's flip check; BUG-907 closes with the removal of `clear_for_section` in the BUG-908 unit. Flip check for this unit: `--bugs BUG-906,BUG-909`.
- When BUG-908 is planned, its unit removes `get_by_section` / `clear_for_section` (DAO) and the manager's `clear_for_section`, with their tests (dead-code list); the BUG-906 tests above go with them.
