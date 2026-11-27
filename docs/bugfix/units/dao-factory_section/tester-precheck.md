# Tester pre-check: dao-factory_section (2026-11-27)

Source: `app/dao/factory_section.py`, `DAOFactorySection.get_by_factory`. Database:
`bf_dao_factory_section_test`. The only production caller is
`app/managers/factory_section_manager.py` (`search_factory_sections` with a factory,
`_check_name_exists_in_factory`). Caller test files searched: every `tests/unit/**/test_*.py`
that mentions `factory_section` (17 files). Only the manager and service files hold tests for
these bugs.

Run once with `--runxfail -rf`: all 16 target tests fail today, each on the line its card names.

**Verdict: every target test is right. No wrong tests. But the unit, as scoped (DAO file only), cannot pass the flip check.** See "Blocker" below.

## BUG-903 (no sort order)

| Test | File | Strict | Verdict |
|---|---|---|---|
| FSD-GF-32, GF-33, GF-34, GF-35 | `tests/unit/dao/test_factory_section.py` | no | right (R6 example and windows; GF-33 checks the `id` tie-break for "bolt" / "Bolt") |
| FSD-GF-36 | same | yes | right, with a note: SQL-text check |
| FSM-S-64 | `tests/unit/managers/test_factory_section_manager.py` | no | right (pass-through) |
| FSM-S-66 | same | yes | right, with a note: SQL-text check (`order by` followed by `name`) |
| FSS-L-09 | `tests/unit/services/test_factory_section_service.py` | no | right (pass-through) |

Notes for the systems engineer:
- FSD-GF-36 requires **exactly one** `SELECT` during the call, and that it has `ORDER BY`.
  A fix that hides sections of a deleted factory with a join or `EXISTS` in the same query
  passes. A fix that first reads the factory in a **separate** query fails it, even though
  its behaviour is right. Steer toward a single query.
- FSM-S-66 looks for `name` after `order by`. `func.lower(FactorySection.name)` passes it; a
  raw `text()` sort could fail it.

## BUG-904 (sections of a soft-deleted factory are returned)

| Test | File | Strict | Verdict |
|---|---|---|---|
| FSD-GF-15 | `tests/unit/dao/test_factory_section.py` | yes | right (R3a) |
| FSD-RS-16 | same | yes | right (`restore` R7c, `get_by_factory` R3a) |
| FSM-S-20 | `tests/unit/managers/test_factory_section_manager.py` | yes | right (pass-through) |
| FSS-L-10 | `tests/unit/services/test_factory_section_service.py` | yes | right (pass-through) |

The pass cards around them (R1a cross-workspace FSD-GF-39/40, inactive factory, restoring the
factory FSD-GF-19 / RS-17 / FSM-S-24) still pass under a simulated fix. So the fix must filter
on `factories.is_deleted` only, never on the factory's workspace.

## BUG-905 (soft-deleted sections are returned)

| Test | File | Strict | Verdict |
|---|---|---|---|
| FSD-GF-10, GF-11, GF-12, GF-13 | `tests/unit/dao/test_factory_section.py` | yes | right (R2, R4, R5) |

## Blocker: two passing manager tests break after a correct fix

I simulated the fix in memory with a scratch pytest plugin that replaced `get_by_factory` with
join factory, `is_deleted` filters, `ORDER BY lower(name), id`. `app/` was not touched. I
compared it with today's run over the 17 files (2738 tests). Every target test flipped as
expected. Two **passing, non-xfail** tests turned into failures:

- `test_fsm_s_16__include_deleted_true_with_a_factory_lists_its_soft_deleted_sections`.
  Manager spec `search_factory_sections` R6 [BUG-920]: with `include_deleted=True`, soft-deleted
  sections are returned "the manager does so today". After BUG-905 the DAO no longer returns them.
- `test_fsm_s_22__include_deleted_true_with_the_soft_deleted_factory_as_filter_lists`.
  Manager spec R7 / P-answer: "With `include_deleted=True` such sections are returned too". After
  BUG-904 the DAO hides them.

Both tests are **right**: they are the manager's intended behaviour. The spec predicted this
(manager spec R6: "After BUG-905 the factory branch needs a DAO lookup that still returns them
(FU-1)"; BUG-920 row: "after BUG-905 the manager needs a lookup that still returns deleted
sections"). The manager's `factory_id` branch calls `get_by_factory` and only filters deleted
rows itself afterwards, so the include-deleted path depends on the old raw DAO behaviour.

The flip check will reject any DAO-only fix. Options for the planner / systems engineer:
1. **Recommended:** widen the unit to two files. In the DAO, add a keyword
   `include_deleted: bool = False` to `get_by_factory`. When it is True, it skips both
   deleted filters (sections and factory) but keeps the order. In the manager's factory branch,
   pass `include_deleted=include_deleted` through. This is a one-line caller change.
   `_check_name_exists_in_factory` keeps the default. This changes no public API (BUG-920 still
   leaves the flag unreachable from the endpoint).
2. Or fix BUG-903 alone in this round (the order change breaks nothing; see below), and move
   BUG-904 / BUG-905 to a round that pairs them with the manager.

Add a matching rule to the brief for option 1: "with `include_deleted=True`, `get_by_factory`
returns soft-deleted sections and sections of a soft-deleted factory too, in the same order".

## Expected collateral (non-strict, ignored by the flip check)

Under the simulated fix these non-strict xfails went XFAIL → XPASS:
- BUG-917 `FSM-S-55`, `FSM-S-56`, and BUG-911 `FSM-CN-15`. The manager spec says the
  "100 deleted first" recipe passes once BUG-905 alone is fixed. The strict / 101-live cases
  for those bugs stay xfailed.
- Physical-order noise in other files: `test_factory.py` FCD-GW-22/23/24 (BUG-100 family),
  `test_machine_section_assignment.py` MSA-GS-20.

No strict xfail of another bug flipped.

## Outside this unit

- `FactorySectionManager._check_name_exists_in_factory` after BUG-904 sees no sections of a
  deleted factory. Today no caller reaches it for one (create refuses; the update of a
  section inside one is BUG-926, still open). While BUG-926 is open, a rename inside a deleted
  factory would skip the duplicate check. This has no test and is low risk, but the systems
  engineer should mention it.
- The same "manager include-deleted path relies on a raw DAO list" pattern is likely in other
  DAO units that hide deleted rows in a module-specific list (machines BUG-956 family).
  Planners should grep callers for `include_deleted` before scoping a DAO-only soft-delete fix.
