# Test cases — `app/utils/work_order_generation.py`

> **Spec:** `tests/unit/utils/work_order_generation.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — re-run on the same APPROVED spec (source commit e48a092, no rule changes). `work_order_generation.verify.md` (PASS) has no case-designer (`case-missing`) findings; its 4 surviving mutants are dead-branch (L27–31, listed for removal) or bug-path (BUG-342 cap, covered by xfail WOG-R-28/37). No cases added, changed or retired.
> **Counts:** 38 cases · 26 expected-to-pass · 12 expected-to-fail (bugs) · 0 deferred

## Reviewer summary
- **Per callable:** `resolve_template_machine_ids` 38 cases (12 bug): default-machine path 14 (8 bug: BUG-340 ×3, BUG-341 ×5), section path 14 (2 bug: BUG-343, BUG-342), factory path 9 (2 bug: BUG-343, BUG-342), nothing-set path 1.
- **Notable design choices:**
  - Passing section/factory cases compare the result **order-insensitively** (sorted ids + length), because ordering is itself a bug (BUG-343) and today's order is undefined. Order is asserted only in the two xfail ordering cases. (best-practice default, delegated by reviewer)
  - The no-cap bug (BUG-342) is tested on both sides of the 1000 boundary: 1000 machines → 1000 ids (pass today and after the fix), 1001 machines → 1001 ids (xfail). Done for both section and factory. These four cases insert 1000+ rows each.
  - Every "rejected default machine" xfail case also puts live machines in the template's section / requested factory so a wrong fall-through (R1) would be caught once the bug is fixed.
  - The template is built in memory and never added to the session, so "no side effects" can be checked as "session has no new or dirty objects after the call". (best-practice default, delegated by reviewer)
  - WOG-R-18 needs a machine of W2 assigned to a section of W1 — the spec (R4) states this situation explicitly, so it is set up directly.
- **Needs a decision:** None.

## Conventions for this module
- **IDs:** `WOG` = work_order_generation, `R` = `resolve_template_machine_ids`.
- **Workspaces:** W1, W2.
- **Factories:** F1, F2 in W1; F3 in W2.
- **Sections:** S1, S2 belong to F1 (W1). No sections in W2 unless a case says so.
- **Machines:** every machine is created with `is_deleted = False`, `is_active = True`, in the workspace/factory the case states, unless the case says otherwise. "assigned S1" = a `MachineSectionAssignment` row linking the machine to S1; "unassigned" = no assignment row.
- **Template T:** an in-memory `WorkOrderTemplate` (never added to the session, never flushed) with only `default_machine_id` and `default_factory_section_id` set as the case says; both are `None` unless stated.
- **Call:** `resolve_template_machine_ids(session, template=T, workspace_id=W1)` unless the case names other arguments; `factory_section_id` / `factory_id` default to `None`.
- **"Set equals {…}"** = `sorted(result) == sorted([...])` **and** `len(result)` equals the set size (catches duplicates, R9). **"returns [X]"** = exact list equality.
- **"no pending changes"** = after the call, `session.new` and `session.dirty` are empty.
- **Externals mocked:** none. **Time:** not used. **Race simulations:** none.

## `resolve_template_machine_ids`

### Default-machine path

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOG-R-01 | R1, R2, R2d | happy | M1 in W1/F1, assigned S1; M2 in W1/F1, assigned S2; T.default_machine_id = M1, T.default_factory_section_id = S2 | call, no scope args | returns exactly `[M1]` (S2's M2 not included, template section not compared with M1); no pending changes | pass |
| WOG-R-02 | R2 | boundary | M1 in W1/F1 with `is_active = False`, `is_deleted = False`; T.default_machine_id = M1 | call, no scope args | returns `[M1]` | pass |
| WOG-R-03 | R1, R2, R2c | boundary | M1 in W1/F1, unassigned; M2, M3 live in W1/F1; T.default_machine_id = M1 | call with `factory_id=F1` | returns exactly `[M1]` (factory's other machines not added) | pass |
| WOG-R-04 | R2, R2c | boundary | M1 in W1/F1, assigned S1; M2 in W1/F1, assigned S1; T.default_machine_id = M1 | call with `factory_section_id=S1` | returns exactly `[M1]` | pass |
| WOG-R-05 | R2, R2c | boundary | M1 in W1/F1, assigned S1; T.default_machine_id = M1 | call with `factory_id=F1, factory_section_id=S1` | returns `[M1]` | pass |
| WOG-R-06 | R2, R2d | boundary | M1 in W1/F1, unassigned; M2 in W1/F1 assigned S1; T.default_machine_id = M1, T.default_factory_section_id = S1 | call, no scope args | returns exactly `[M1]` (unassigned machine not filtered when no run scope; template section ignored) | pass |
| WOG-R-07 | R2a [BUG-340], R1 | bug | M1 in W1/F1 with `is_deleted = True`; M2 live in W1/F1 assigned S1; T.default_machine_id = M1, T.default_factory_section_id = S1 | call with `factory_id=F1` | returns `[]` (no fall-through to S1's M2 or F1's machines) | xfail BUG-340 — fails today on: returns `[M1]` |
| WOG-R-08 | R2a [BUG-340] | bug | M9 live in W2/F3; T.default_machine_id = M9 | call with `workspace_id=W1`, no scope args | returns `[]` | xfail BUG-340 — fails today on: returns `[M9]` |
| WOG-R-09 | R2b [BUG-340] | bug | M1 live in W1/F1 assigned S1; X = an id not present in `machines` (use 2147483000, assert absent before the call); T.default_machine_id = X, T.default_factory_section_id = S1 | call, no scope args | returns `[]` (no fall-through to S1) | xfail BUG-340 — fails today on: returns `[X]` |
| WOG-R-10 | R2c [BUG-341], R1 | bug | M1 in W1/F1, unassigned; M5 live in W1/F2; T.default_machine_id = M1 | call with `factory_id=F2` | returns `[]` (no fall-through to F2's M5) | xfail BUG-341 — fails today on: returns `[M1]` |
| WOG-R-11 | R2c [BUG-341], R1 | bug | M1 in W1/F1, assigned S1; M2 in W1/F1, assigned S2; T.default_machine_id = M1 | call with `factory_section_id=S2` | returns `[]` (no fall-through to S2's M2) | xfail BUG-341 — fails today on: returns `[M1]` |
| WOG-R-12 | R2c [BUG-341] | bug | M1 in W1/F1, unassigned; M2 in W1/F1, assigned S1; T.default_machine_id = M1 | call with `factory_section_id=S1` | returns `[]` | xfail BUG-341 — fails today on: returns `[M1]` |
| WOG-R-13 | R2c [BUG-341] | bug | M1 in W1/F1, assigned S1; T.default_machine_id = M1 | call with `factory_id=F1, factory_section_id=S2` (factory matches, section does not) | returns `[]` | xfail BUG-341 — fails today on: returns `[M1]` |
| WOG-R-14 | R2c [BUG-341] | bug | M1 in W1/F1, assigned S1; T.default_machine_id = M1 | call with `factory_id=F2, factory_section_id=S1` (section matches, factory does not) | returns `[]` | xfail BUG-341 — fails today on: returns `[M1]` |

### Section path (no default machine)

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOG-R-15 | R3, R4, R9 | happy | In W1/F1: M1 "Lathe" assigned S1, M2 "Mill" assigned S1, M3 "Press" assigned S2, M4 "Saw" unassigned; T.default_factory_section_id = S1 | call, no scope args | set equals {M1, M2}; no pending changes | pass |
| WOG-R-16 | R3, R4 | happy | same machines as WOG-R-15; T has no default section | call with `factory_section_id=S1` | set equals {M1, M2} | pass |
| WOG-R-17 | R3 | boundary | same machines as WOG-R-15; T.default_factory_section_id = S1 | call with `factory_section_id=S2` | set equals {M1, M2} (M3 of S2 not included) | pass |
| WOG-R-18 | R4 | isolation | M1 in W1/F1 assigned S1; M9 live in W2/F3 assigned S1; T.default_factory_section_id = S1 | call with `workspace_id=W1` | returns `[M1]` (M9 excluded) | pass |
| WOG-R-19 | R4 | isolation | M1, M2 in W1/F1 assigned S1; T.default_factory_section_id = S1 | call with `workspace_id=W2` | returns `[]` | pass |
| WOG-R-20 | R4, R1 | boundary | M1, M2 in W1/F1 assigned S1; M5 live in W1/F2 unassigned; T.default_factory_section_id = S1 | call with `factory_id=F2` | set equals {M1, M2} (factory_id ignored; M5 not included) | pass |
| WOG-R-21 | R5 | soft-delete | In W1/F1 assigned S1: M1 live; M2 `is_deleted = True`; M3 `is_active = False`, `is_deleted = False`; T.default_factory_section_id = S1 | call | set equals {M1, M3} | pass |
| WOG-R-22 | R6, R5 | boundary | M2 in W1/F1 assigned S1 with `is_deleted = True` (only machine in S1); M4 live in W1/F1 unassigned; T.default_factory_section_id = S1 | call with `factory_id=F1` | returns `[]` (no factory fallback to M4) | pass |
| WOG-R-23 | R6 | boundary | S1 has no assignment rows; M4 live in W1/F1 unassigned; T has no default section | call with `factory_section_id=S1, factory_id=F1` | returns `[]` (no factory fallback) | pass |
| WOG-R-24 | R4, R9 | boundary | M1 in W1/F1 assigned S1 (only machine in S1); T.default_factory_section_id = S1 | call | returns `[M1]` | pass |
| WOG-R-25 | R9 | boundary | M1, M2, M3 in W1/F1 all assigned S1; T.default_factory_section_id = S1 | call | `len(result) == 3`, `len(set(result)) == 3`, set equals {M1, M2, M3} | pass |
| WOG-R-26 | R5a [BUG-343] | bug | In W1/F1, all assigned S1, inserted in this order: A "beta", B "Alpha", C "alpha", D "Gamma", E "Drill", F "Drill" (ids ascend with insertion); T.default_factory_section_id = S1 | call | returns exactly `[B, C, A, E, F, D]` (name case-insensitive asc, then id asc) | xfail BUG-343 — fails today on: exact list order (no ORDER BY) |
| WOG-R-27 | R5b | boundary | 1000 live machines in W1/F1, all assigned S1 (names "Machine 0001"…"Machine 1000"); T.default_factory_section_id = S1 | call | `len(result) == 1000`; set equals all 1000 ids | pass |
| WOG-R-28 | R5b [BUG-342] | bug | 1001 live machines in W1/F1, all assigned S1 (names "Machine 0001"…"Machine 1001"); T.default_factory_section_id = S1 | call | `len(result) == 1001`; set equals all 1001 ids | xfail BUG-342 — fails today on: `len(result) == 1001` (today 1000) |

### Factory path (no default machine, no section)

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOG-R-29 | R7, R9 | happy | In W1/F1: M1 assigned S1, M4 unassigned; M5 live in W1/F2; T has no default machine or section | call with `factory_id=F1` | set equals {M1, M4}; no pending changes | pass |
| WOG-R-30 | R7, R5 | soft-delete | In W1/F1: M1 live; M2 `is_deleted = True`; M3 `is_active = False`, `is_deleted = False` | call with `factory_id=F1` | set equals {M1, M3} | pass |
| WOG-R-31 | R7 | boundary | F2 has no machines; M1 live in W1/F1 | call with `factory_id=F2` | returns `[]` | pass |
| WOG-R-32 | R7, R5 | boundary | F2's only machine M6 has `is_deleted = True`; M1 live in W1/F1 | call with `factory_id=F2` | returns `[]` | pass |
| WOG-R-33 | R7 | isolation | M9, M10 live in W2/F3 | call with `workspace_id=W1, factory_id=F3` | returns `[]` | pass |
| WOG-R-34 | R9 | boundary | M1, M2, M3 live in W1/F1 (M1 assigned S1, others unassigned) | call with `factory_id=F1` | `len(result) == 3`, `len(set(result)) == 3`, set equals {M1, M2, M3} | pass |
| WOG-R-35 | R5a [BUG-343], R7 | bug | In W1/F1, unassigned, inserted in this order: A "beta", B "Alpha", C "alpha", D "Gamma", E "Drill", F "Drill"; no other machines in F1 | call with `factory_id=F1` | returns exactly `[B, C, A, E, F, D]` | xfail BUG-343 — fails today on: exact list order (no ORDER BY) |
| WOG-R-36 | R5b, R7 | boundary | 1000 live machines in W1/F1 (names "Machine 0001"…"Machine 1000"), no other machines in F1 | call with `factory_id=F1` | `len(result) == 1000`; set equals all 1000 ids | pass |
| WOG-R-37 | R5b [BUG-342], R7 | bug | 1001 live machines in W1/F1 (names "Machine 0001"…"Machine 1001"), no other machines in F1 | call with `factory_id=F1` | `len(result) == 1001`; set equals all 1001 ids | xfail BUG-342 — fails today on: `len(result) == 1001` (today 1000) |

### Nothing set

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WOG-R-38 | R8 | happy | M1 live in W1/F1 assigned S1; M4 live in W1/F1 unassigned; T has no default machine and no default section | call with `workspace_id=W1`, `factory_section_id=None`, `factory_id=None` | returns `[]`; no pending changes | pass |

## Deferred to other specs
None. (The dead branch L27–31 is listed for removal in the spec's Not specified section; it has no observable behavior to test.)

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `resolve_template_machine_ids` | R1 | WOG-R-01, 03, 07, 09, 10, 11, 20 |
| `resolve_template_machine_ids` | R2 | WOG-R-01, 02, 03, 04, 05, 06 |
| `resolve_template_machine_ids` | R2a [BUG-340] | WOG-R-07, 08 |
| `resolve_template_machine_ids` | R2b [BUG-340] | WOG-R-09 |
| `resolve_template_machine_ids` | R2c [BUG-341] | pass side: WOG-R-03, 04, 05 · bug: WOG-R-10, 11, 12, 13, 14 |
| `resolve_template_machine_ids` | R2d | WOG-R-01, 06 |
| `resolve_template_machine_ids` | R3 | WOG-R-15, 16, 17 |
| `resolve_template_machine_ids` | R4 | WOG-R-15, 16, 18, 19, 20, 24 |
| `resolve_template_machine_ids` | R5 | WOG-R-21, 22, 30, 32 |
| `resolve_template_machine_ids` | R5a [BUG-343] | WOG-R-26, 35 |
| `resolve_template_machine_ids` | R5b [BUG-342] | pass side: WOG-R-27, 36 · bug: WOG-R-28, 37 |
| `resolve_template_machine_ids` | R6 | WOG-R-22, 23 |
| `resolve_template_machine_ids` | R7 | WOG-R-29, 30, 31, 32, 33, 34, 35, 36, 37 |
| `resolve_template_machine_ids` | R8 | WOG-R-38 |
| `resolve_template_machine_ids` | R9 | WOG-R-15, 24, 25, 29, 34 |
| `resolve_template_machine_ids` | Errors: none | — (no error rows) |
| `resolve_template_machine_ids` | Side effects: none | WOG-R-01, 15, 29, 38 (no pending changes) |
