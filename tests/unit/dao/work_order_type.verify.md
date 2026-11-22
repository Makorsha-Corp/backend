# Verification — `app/dao/work_order_type.py`

> **Current verdict: PASS** (round 2, 2026-11-02, revision 1, 30 cases). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 24 passed · 4 xfail, all strict (reproduced ✅) · coverage 100% branch (21 statements, 0 branches)
> Mutation: 4 mutants · 4 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 28 unfaithful** (28 / 28 right)
> Hand variants: 73 · 60 caught by a pass card · 13 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 28 match their cards. After names are normalised the file differs from `test_department.py` only as the cards differ: RS-10 uses `Dup` and `dup`, the master's RS-11 is gone, its RS-12 is RS-11 here, and IN-01 to IN-06 are added.
- **Why NEEDS WORK:** 4 sites, all killed, but hand variants show 2 rule gaps, for the case designer.

Written by Claude (all 28 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 28. No `work_order_type.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `soft_delete` R4 with R7 | SD-05 repeats a delete with a profile, and SD-08 passes `None` on a live row. No card passes `None` on a row already deleted, so keeping the old `deleted_by` passes, though R4 says the stamps are overwritten. | `sd_r4_by_only_if_given` passes all 28. | **case designer** |
| 2 | case-missing | `restore` R6 "a live type" | The master's RS-11, a deleted row of that name blocks nothing, was left out because today's constraint forbids the Given. `Dup` and `dup` allow it, as RS-10 already does. | `rs_r6_refuse_deleted_twin`, `rs_r6_refuse_deleted_twin_ci` pass all 28. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\prop\test_prop.py`, not in the repo. Each passes on today's code and on the reference. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, `soft_delete` R4, R7 | A = row, but gone; When `deleted_by=None` | `result is A`; re-read A: `is_deleted is True`, `deleted_at == NOW`, `deleted_by is None` | pass | `sd_r4_by_only_if_given` |
| R-2 | new card, `restore` R6 | A = row, but gone, `name "Dup"`; B = row, but gone, `name "dup"` | `result is A`; re-read A: `is_deleted is False`; unchanged(B) | pass | `rs_r6_refuse_deleted_twin_ci`. The exact-name shape cannot be built until the constraint goes |

## Surviving mutants
None. All 4 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 4 mutants with no `-x`: every run reached all 28 tests, with no collection or setup error.

## Hand variants
`plug\variants.py`, on the reference with `--runxfail`, default plan. Every edit was asserted to apply once and every run reached all 28 tests. Group names: the rule, `w` writes and session, `s` side effects, `txt` the text compare, `kw` keyword-only.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| sd_r1 | 8 | 8 | WOT-SD-01, WOT-SD-03, WOT-SD-05, WOT-SD-06, WOT-SD-07, WOT-SD-08 … | — |
| sd_r2 | 2 | 2 | WOT-RS-02, WOT-SD-01, WOT-SD-02, WOT-SD-03, WOT-SD-04, WOT-SD-05 … | — |
| sd_r3 | 7 | 5 | WOT-SD-02, WOT-SD-03, WOT-SD-07 | `sd_r3_updated_at_none`, `sd_r3_updated_at_clock` |
| sd_r4 | 5 | 4 | WOT-SD-05 | `sd_r4_by_only_if_given` |
| sd_r5 | 2 | 2 | WOT-SD-02, WOT-SD-06 | — |
| sd_r6 | 3 | 3 | WOT-SD-07 | — |
| sd_r7 | 3 | 3 | WOT-SD-08 | — |
| sd_s | 9 | 7 | WOT-RS-02, WOT-SD-01, WOT-SD-02, WOT-SD-03, WOT-SD-04, WOT-SD-05 … | `sd_s_no_add`, `sd_s_refresh` |
| rs_r1 | 5 | 5 | WOT-RS-01, WOT-RS-02, WOT-RS-04, WOT-RS-06, WOT-RS-07, WOT-RS-08 … | — |
| rs_r2 | 6 | 5 | WOT-RS-03, WOT-RS-04, WOT-RS-07 | `rs_r2_updated_at_none` |
| rs_r3 | 2 | 2 | WOT-RS-01, WOT-RS-02, WOT-RS-03, WOT-RS-04, WOT-RS-05, WOT-RS-06 … | — |
| rs_r4 | 4 | 3 | WOT-RS-07 | `rs_r4_guard` |
| rs_r5 | 1 | 1 | WOT-RS-08 | — |
| rs_r6 | 4 | 2 | WOT-RS-11 | `rs_r6_refuse_deleted_twin`, `rs_r6_refuse_deleted_twin_ci` |
| rs_s | 7 | 5 | WOT-RS-01, WOT-RS-02, WOT-RS-04, WOT-RS-05, WOT-RS-06, WOT-RS-07 … | `rs_s_no_add`, `rs_s_refresh` |
| kw | 2 | 0 | — | `kw_sd_positional`, `kw_rs_positional` |
| n1 | 3 | 3 | WOT-IN-01, WOT-IN-05, WOT-IN-06 | — |
| **Total** | **73** | **60** |  | **13** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `sd_r3_updated_at_none`, `rs_r2_updated_at_none` | **Equivalent on the rule's domain.** Setting `None` over `None` is no change, so `onupdate` still fires. R3 and R2 speak only of a row whose `updated_at` is `NULL`. |
| `sd_r3_updated_at_clock` | No rule says which clock stamps `updated_at`, only that it becomes non-null. The department spec leaves it to machine_maintenance_log FU-3. |
| `sd_s_no_add`, `rs_s_no_add` | **Equivalent for a row in the session,** and every caller passes one. |
| `sd_s_refresh`, `rs_s_refresh` | **Equivalent:** one extra `SELECT` of the same values, no write. |
| `rs_r4_guard` | **Equivalent:** a live row with stamps set is not a state the code makes, and on a clean live row the guard changes nothing. |
| `kw_sd_positional`, `kw_rs_positional` | A note, not a rule: cases Spec gap 1, as in `work_order_approver.verify.md`. |

## xfail tests against the reference
Reference: in each test's own transaction, `uq_wo_type_workspace_name` dropped and a partial unique index on `(workspace_id, lower(btrim(name))) WHERE NOT is_deleted` created, both rolled back with it. Nothing is written to `app/`.

With `--runxfail` on the reference: 28 passed. **The alarm works:** with the markers on, `4 failed, 24 passed`, the strict cards `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| WOT-RS-10, IN-03, IN-04 | strict | Then 1, `DID NOT RAISE`, as the cards say |
| WOT-IN-02 | strict | The When: the call raises `IntegrityError` before Then 1, as the card's Fails line says |

## Reproduced claims
- **Result line of the notes holds:** `24 passed, 4 xfailed` in 5 of 5 default runs, the coverage run among them. No flaky test.
- `--runxfail`, on 3 plans: `4 failed, 24 passed`.
- **Mocks:** only `utcnow` and the `db.commit` spy, as the cards say. No `try`, no broad `pytest.raises`, no `if` in a test body.

## Carried, not findings
- **Order, carried from the spec:** FU-2, a soft-deleted type can be chosen for a new work order or template. If the work order manager's describer has not ruled, the owner is asked.
- **Order, carried from cases Spec gaps 2, 3:** N1 pins a constraint name BUG-1214's fix replaces, and R6's Today note, "cannot be reached", holds only for the exact name. For the describer, at the next touch.

## Traceability
cases 28 · tests 28 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script rebuilt each test's Given, snapshots, When, Then and marker from its card and compared by AST, for all 221 cards of the batch, with the helpers against the Conventions. It gave 2 reports, both the wait of WSP-IN-04 (see `workspace.verify.md`). Selftest: 1283 of 1283 planted mistakes of 60 kinds, in tests, helpers and cards.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live. Each kill is a plain `N failed`.
- **Reference DDL** ran inside each test's own rolled-back transaction, in three short runs per module that needs it, on the shared test database. Nothing persisted. Hand variants ran without it, and the bug cards it serves are left out of their counts.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/work_order_type.py tests/unit/dao/test_work_order_type.py --timeout 300 --json <scratch>/res/mut_work_order_type.json   (through runmut.py)
  4 mutants · 4 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order_type.py -q -p no:cacheprovider --cov=app.dao.work_order_type --cov-branch --cov-report=term-missing --tb=no
  24 passed, 4 xfailed
pytest, default, 4 more runs; pytest --runxfail --tb=short, 3 plans        repro.py
drive.py bases; drive.py muts; drive.py vars                               as above
propdrive.py                                                               0 problems
rebuild.py; rebuild.py --selftest 6                                        221 cards, 2 reports; 1283 of 1283
.venv/Scripts/python.exe -m ruff check <the nine test files>               All checks passed!
git diff --stat -- app/dao                                                 (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add the recipes above; the Givens and Thens are written out.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-02 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 26 passed · 4 xfail, all strict (reproduced ✅) · coverage 100% branch (21 statements, 0 branches)
> Mutation: not re-run; round 1 stands at 4 / 4 → 100% (4 mutants)
> Fidelity: **0 of 30 unfaithful** (the 2 new read by eye; all 30 rebuilt by script)
> Hand variants: 73 · 62 caught by a pass card · every gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test edited in this round, no commit.

**Open until BUG-1214:** `rs_r6_refuse_deleted_twin`, the exact-name shape, still passes every card. Two deleted rows of one exact name cannot be built under `uq_wo_type_workspace_name`, so no card can see it today. It needs a card when the constraint goes. It does not hold this verdict. FU-2 and cases Spec gaps 2, 3 stay carried, as in round 1.

### New tests
Each was read against its card and matches its recipe. "Fails" means the variant fails that card, on the reference with `--runxfail`.

| Card | Recipe | Fails |
|---|---|---|
| WOT-SD-12 | R-1 | `sd_r4_by_only_if_given` |
| WOT-RS-12 | R-2 | `rs_r6_refuse_deleted_twin_ci` |

### Rest of the batch
All 73 variants ran again, each reaching all 30 tests. Left without a pass card: the ten under "Considered and not listed", and `rs_r6_refuse_deleted_twin`. None is a new rule gap.

### Reproduced
- **Result line of the notes holds:** `26 passed, 4 xfailed` in 5 of 5 default runs, the coverage run among them. No flaky test.
- **`--runxfail`:** `4 failed, 26 passed`.
- **Reference:** 30 passed with `--runxfail`, on the bases of round 1. **Alarm:** with the markers on, `4 failed, 26 passed`, the strict cards `XPASS(strict)`.
- **Traceability:** cases 30 · tests 30 · unmatched: none · marker mismatches: none. `rebuild.py`: 252 cards over the nine files, 1 report, the `while` of WSP-IN-04. Selftest: 1299 of 1299 planted mistakes of 60 kinds. `ruff check` passes.
- **Limit:** I kept no copy of the round 1 file, so "existing tests unchanged" rests on the rebuild of all 30 against their cards, not on a line diff.

### Commands run
```
drive.py vars <module>                 73 variants, all reached all 30 tests
r2check.py                                                gap variants against their cards
drive.py bases <module>                                   as under Reproduced
repro.py <module>                                         as under Reproduced
rebuild.py; rebuild.py --selftest 6                       252 cards, 1 report; 1299 of 1299
.venv/Scripts/python.exe -m ruff check <the eight test files>     All checks passed!
git diff --stat -- app/dao                                (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\`. Only this report was edited in the repo. Nothing was stopped or killed.
