# Tester pre-check: dao-machine

Date: 2026-11-27 (batch 3). Source `app/dao/machine.py`. Specs and cases: `tests/unit/dao/machine.*`,
`tests/unit/managers/machine_manager.*`, `tests/unit/services/machine_service.*`.
Database: `bf_dao_machine_test`.

## Search

Bare numbers `886`…`892` (and `342`, `343`) grepped in `tests/**/*.py`. All markers for this unit's
bugs are inline `pytest.mark.xfail(strict=..., reason="BUG-88x: …")`; no helper constants. (The
`BUG_342` / `BUG_343` constants in `test_work_order_generation.py` belong to out-of-scope bugs.)

Caller test files, found with Grep for `machine_dao`, `get_by_section`, `get_by_factory`,
`search_advanced`, `search_machines`, `get_machines`, `resolve_template_machine_ids`, `generate_drafts`
(full paths):

- `tests/unit/dao/test_machine.py` (the unit's own file)
- `tests/unit/managers/test_machine_manager.py`
- `tests/unit/services/test_machine_service.py`
- `tests/unit/utils/test_work_order_generation.py`
- `tests/unit/dao/test_factory.py` (`machine_dao.get_by_factory` after a factory restore, FCD-RS-14)
- `tests/unit/dao/test_factory_section.py` (`machine_dao.get_by_section` after a section restore)
- `tests/unit/managers/test_work_order_template_manager.py`
- `tests/unit/services/test_work_order_template_service.py`
- `tests/test_work_order_template_bulk_generate.py`, `tests/test_work_order_recurrence_repick.py`,
  `tests/test_work_order_sheet_routes.py` (legacy; generate-drafts paths)
- `tests/test_work_order_sheet_entry_future_draft.py` (mocks `machine_dao.get_by_id_and_workspace` only)

Other `get_by_factory` / `get_by_section` hits (inventory, product, project, production_line,
machine_section_assignment, factory_section DAOs) are same-named methods of other DAOs.

Markers naming this unit's bugs: **60 tests in 3 files** (58 strict, 2 non-strict).

| Bug | DAO | Manager | Service | Strict |
|---|---|---|---|---|
| BUG-886 | 22 | 2 | 1 | all |
| BUG-887 | 2 | 1 | 1 | DAO strict; manager MCM-S-… (line 5576) and MCS-L-13 non-strict |
| BUG-888 | 5 | 1 | 1 | all |
| BUG-889 | 2 | 1 | 1 | all |
| BUG-890 | 5 | 2 | 1 | all |
| BUG-891 | 3 | 1 | 0 | all |
| BUG-892 | 6 | 1 | 1 | all |

No test names two bugs. No SQL-text or statement-count check in any of them (behaviour only).

## Run today

Normal run of the 12 files above: 1044 passed, 439 xfailed, 5 xpassed (BUG-100 non-strict ties
only). `test_machine_section_assignment.py` errors only when collected together with the factory
files (fixture name clash between modules); alone it is 69 passed. Unrelated to this unit; run it
separately at stage C.

With `--runxfail` every one of the 60 target tests fails today; the BUG-886 ones on
`AttributeError: 'Comparator' object has no attribute 'astext'`, as their cards say; the 2
non-strict BUG-887 caller tests xfail today (no accidental pass).

## Simulated fixes (scratch plugin, no `app/` edit)

A scratch pytest plugin swapped `DAOMachine.get_by_factory`, `get_by_section` and `search_advanced`
for candidates and recorded every outcome across the 11 caller files plus the unit file.

**Correct candidate:** join `factories` on `machines.factory_id` with `is_deleted = False` in all
three; join `factory_sections` with `is_deleted = False` for the section lookup and filter; `strip()`
then escape `\`, `%`, `_` with `ilike(..., escape="\\")`; latest status via
`row_number() over (partition by machine_id order by created_at desc, id desc)` on the workspace's
`status_updated` rows, `metadata_json["status"].as_string() == latest_event_type.value`, `rn = 1`;
name sort `lower(name)` asc/desc then `id` asc; no `ORDER BY` added to the two lookups.

Result vs today: **57 target tests flip** (55 strict xfail → pass, 2 non-strict BUG-887 →
pass); **3 BUG-886 caller tests stay failing** (see below); **no other test in any file changes**
(no BUG-342 / BUG-343 test, no passing test, no other bug's xfail).

**Plausible-but-wrong candidates** (unit file only):
- latest status without the `id` tie-break → 2 tests fail (the R12a tie cards). Caught.
- escaping `%` and `_` but not `\` → 1 test fails (the `a\b` card, R9). Caught.

## BUG-886: latest-status filter crashes

Tests: DAO 22 strict (R12, R12a–e), manager MCM-S-12, MCM-S-39, service MCS-L-12.

Verdict: DAO tests **right**. **MCM-S-12, MCM-S-39 and MCS-L-12 are wrong (input)**: they pass the
plain string `"IDLE"` where every spec types `latest_event_type` as `MachineEventTypeEnum` and the
endpoint passes the enum. A correct fix that keeps today's `.value` fails them with
`'str' object has no attribute 'value'`. Entry in `docs/bugfix/wrong-tests.md` (one-argument diff
per test, `latest_event_type=IDLE`); checked: corrected tests still xfail today on `.astext`, pass
with the correct candidate. **Conditional keep (A21):** BUG-886 stays in the unit only if that diff
is on `origin/main` before the batch-3 baseline; otherwise skip BUG-886 this round (remove it from
`brief.md`, re-run the firewall).

## BUG-887: name sort collation-dependent

Tests: DAO 2 strict (the "Bolt" / "bolt" tie ascending and descending, R14), manager and service 1
non-strict each (maintenance-date sort tie, the manager's Python sort keeps DAO order). Verdict:
**right**. The cards rely on the test database's collation putting lower case first on a case-only
tie; on CI (Linux, `en_US.UTF-8` or `C`) today's outcome may differ, but the strict cards fail
today here and pass with `lower(name)`, `id`. If CI's collation already happens to order them by
`id`, the strict cards would XPASS in the baseline there; the order sweep (C5) did not flag them.

## BUG-888: wildcards

Tests: DAO 5 strict (`%`, `_`, `\`, R9), manager 1, service 1. Verdict: **right**; the `\` card
needs `\` escaped too (the row says so).

## BUG-889: soft-deleted section

Tests: DAO 2 strict (`get_by_section` R4, `search_advanced` R6a), manager 1, service 1. Verdict:
**right**. Passing controls (inactive-but-live section, left-over assignment listed without a section
filter) stay passing with the fix.

## BUG-890: machines of a deleted factory on the machines page

Tests: DAO 5 strict (R3a incl. the `limit=1` desc case, `restore` R7a), manager 2, service 1.
Verdict: **right**. R3b / R3c pass controls (inactive factory, factory restored) stay passing.

## BUG-891: factory / section lookups

Tests: DAO 3 strict (`get_by_factory` R3a, `get_by_section` R3a, `restore` R7a), manager 1
(`_check_name_exists_in_factory` R8: no duplicate found among machines of a deleted factory).
Verdict: **right**. Compared as sets, so BUG-343 does not interfere.

## BUG-892: untrimmed search

Tests: DAO 6 strict (R8), manager 1, service 1. Verdict: **right**.

## Outside this unit

- **A16 check (include_deleted):** `MachineManager.search_machines(include_deleted=True)` reads
  through the inherited `get_by_workspace`, not `search_advanced`, so hiding deleted-factory machines
  in `search_advanced` does not narrow it (that path is BUG-957's). No caller passes
  `include_deleted` to `get_by_factory` / `get_by_section`.
- **Duplicate-name check side effect (accepted by BUG-891's row):** after BUG-891,
  `MachineManager._check_name_exists_in_factory` sees no machines of a deleted factory. Same shape as
  the factory_section batch-2 note (BUG-926 there). Creating or moving into a deleted factory is
  BUG-963; editing inside one is BUG-964, both open. Low risk, no test.
- **BUG-343 / BUG-342:** the spec says the fix of BUG-343 is in this file (`get_by_factory` R6,
  `get_by_section` R7), and its util-level tests (`test_work_order_generation.py`, 2 strict) would
  flip if the fixer added an `ORDER BY`. The brief forbids it. A later batch should plan BUG-342 /
  BUG-343 as the util + DAO two-file unit.
- `test_machine_manager.py` line 5775 also passes `latest_event_type="IDLE"`, on the
  `include_deleted=True` path (BUG-957). It ignores the filter today; when BUG-957 is fixed it will
  hit the same str-vs-enum problem. Worth correcting with the BUG-957 unit.
- BUG-1090: after the fix the filter (tie → highest `id`) and the displayed status (timestamp only)
  can disagree on a tie, as the spec's cross-spec note says.

## Batch-2 overlap

`app/dao/machine.py` imports `app.dao.base`, `app.models.*`, `app.schemas.machine`,
`app.utils.time` — none of the batch-2 files. Of the batch-2 files, only
`machine_maintenance_log_manager` calls `machine_dao`, and only `get_by_id_and_workspace`
(inherited, unchanged). `factory_section_manager` and `factory_section.py` do not call `machine_dao`.
The fix joins the `FactorySection` / `Factory` **models**, not their DAOs.

## Notes for the systems engineer

- `metadata_json` is declared generic `JSON`: `["status"].as_string()` (or `.astext` after a cast
  to `JSONB`) works; check the compiled SQL with `scripts/bugfix/compile_query.py`.
- The "latest" rule needs a tie-break on `id` and each machine once (R12a, R12e); today's
  join-on-max-`created_at` returns a machine twice on a tie.
- New joins to `factories` / `factory_sections` are bounded by the outer `machines.workspace_id`
  filter (HR-16, S9). A join must not duplicate rows (one factory per machine, one assignment per
  machine).
- Reject any `ORDER BY` added to `get_by_factory` / `get_by_section` (BUG-343 is out of scope and
  its strict util tests would flip).
- Reject removing `get_active_by_workspace` or the `include_deleted` parameters (dead code, separate change).

## Note for stage C

Remove the markers on **all 60** tests (58 strict, 2 non-strict) — every marker names one of this
unit's bugs only. Condition: the BUG-886 marker diff (wrong-tests.md) must be on main first;
otherwise keep the 25 BUG-886 markers and remove 35. Expected flip check: 60 target tests to passed
(or 35 without BUG-886), nothing else changed. Run `test_machine_section_assignment.py` on its own.
