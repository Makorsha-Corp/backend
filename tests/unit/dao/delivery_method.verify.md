# Verification — `app/dao/delivery_method.py`

> **Current verdict: PASS** (round 2, 2026-11-02, revision 1, 24 cases). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 22 passed · 1 xfail, strict (reproduced ✅) · coverage 100% branch (21 statements, 0 branches)
> Mutation: 4 mutants · 4 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 23 unfaithful** (23 / 23 right)
> Hand variants: 70 · 59 caught by a pass card · 11 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 23 match their cards. After names are normalised the file is one text with `test_department.py`; the only difference is the bug tag on RS-10, BUG-1219 for BUG-003.
- **Why NEEDS WORK:** 4 sites, all killed, but hand variants show 1 rule gap, the master's, for the case designer.

Written by Claude (all 23 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 23. No `delivery_method.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `soft_delete` R4 with R7 | SD-05 repeats a delete with a profile, and SD-08 passes `None` on a live row. No card passes `None` on a row already deleted, so keeping the old `deleted_by` passes, though R4 says the stamps are overwritten. | `sd_r4_by_only_if_given` passes all 23. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\prop\test_prop.py`, not in the repo. Each passes on today's code and on the reference. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, `soft_delete` R4, R7 | A = row, but gone; When `deleted_by=None` | `result is A`; re-read A: `is_deleted is True`, `deleted_at == NOW`, `deleted_by is None` | pass | `sd_r4_by_only_if_given` |

## Surviving mutants
None. All 4 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 4 mutants with no `-x`: every run reached all 23 tests, with no collection or setup error.

## Hand variants
`plug\variants.py`, on the reference with `--runxfail`, default plan. Every edit was asserted to apply once and every run reached all 23 tests. Group names: the rule, `w` writes and session, `s` side effects, `txt` the text compare, `kw` keyword-only.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| sd_r1 | 8 | 8 | DLV-SD-01, DLV-SD-03, DLV-SD-05, DLV-SD-06, DLV-SD-07, DLV-SD-08 … | — |
| sd_r2 | 2 | 2 | DLV-RS-02, DLV-SD-01, DLV-SD-02, DLV-SD-03, DLV-SD-04, DLV-SD-05 … | — |
| sd_r3 | 7 | 5 | DLV-SD-02, DLV-SD-03, DLV-SD-07 | `sd_r3_updated_at_none`, `sd_r3_updated_at_clock` |
| sd_r4 | 5 | 4 | DLV-SD-05 | `sd_r4_by_only_if_given` |
| sd_r5 | 2 | 2 | DLV-SD-02, DLV-SD-06 | — |
| sd_r6 | 3 | 3 | DLV-SD-07 | — |
| sd_r7 | 3 | 3 | DLV-SD-08 | — |
| sd_s | 9 | 7 | DLV-RS-02, DLV-SD-01, DLV-SD-02, DLV-SD-03, DLV-SD-04, DLV-SD-05 … | `sd_s_no_add`, `sd_s_refresh` |
| rs_r1 | 5 | 5 | DLV-RS-01, DLV-RS-02, DLV-RS-04, DLV-RS-06, DLV-RS-07, DLV-RS-08 … | — |
| rs_r2 | 6 | 5 | DLV-RS-03, DLV-RS-04, DLV-RS-07 | `rs_r2_updated_at_none` |
| rs_r3 | 2 | 2 | DLV-RS-01, DLV-RS-02, DLV-RS-03, DLV-RS-04, DLV-RS-05, DLV-RS-06 … | — |
| rs_r4 | 4 | 3 | DLV-RS-07 | `rs_r4_guard` |
| rs_r5 | 1 | 1 | DLV-RS-08 | — |
| rs_r6 | 4 | 4 | DLV-RS-11, DLV-RS-12 | — |
| rs_s | 7 | 5 | DLV-RS-01, DLV-RS-02, DLV-RS-04, DLV-RS-05, DLV-RS-06, DLV-RS-07 … | `rs_s_no_add`, `rs_s_refresh` |
| kw | 2 | 0 | — | `kw_sd_positional`, `kw_rs_positional` |
| **Total** | **70** | **59** |  | **11** |

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
Reference: a partial unique index on `(workspace_id, lower(btrim(name))) WHERE NOT is_deleted`, created in each test's own transaction and rolled back with it. Nothing is written to `app/`.

With `--runxfail` on the reference: 23 passed. **The alarm works:** with the markers on, `1 failed, 22 passed`, the strict cards `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| DLV-RS-10 | strict | Then 1, `DID NOT RAISE`, as the card says |

## Reproduced claims
- **Result line of the notes holds:** `22 passed, 1 xfailed` in 5 of 5 default runs, the coverage run among them. No flaky test.
- `--runxfail`, on 3 plans: `1 failed, 22 passed`.
- **Mocks:** only `utcnow` and the `db.commit` spy, as the cards say. No `try`, no broad `pytest.raises`, no `if` in a test body.

## Traceability
cases 23 · tests 23 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script rebuilt each test's Given, snapshots, When, Then and marker from its card and compared by AST, for all 221 cards of the batch, with the helpers against the Conventions. It gave 2 reports, both the wait of WSP-IN-04 (see `workspace.verify.md`). Selftest: 1283 of 1283 planted mistakes of 60 kinds, in tests, helpers and cards.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live. Each kill is a plain `N failed`.
- **Reference DDL** ran inside each test's own rolled-back transaction, in three short runs per module that needs it, on the shared test database. Nothing persisted. Hand variants ran without it, and the bug cards it serves are left out of their counts.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/delivery_method.py tests/unit/dao/test_delivery_method.py --timeout 300 --json <scratch>/res/mut_delivery_method.json   (through runmut.py)
  4 mutants · 4 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_delivery_method.py -q -p no:cacheprovider --cov=app.dao.delivery_method --cov-branch --cov-report=term-missing --tb=no
  22 passed, 1 xfailed
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
> Tests: 23 passed · 1 xfail, strict (reproduced ✅) · coverage 100% branch (21 statements, 0 branches)
> Mutation: not re-run; round 1 stands at 4 / 4 → 100% (4 mutants)
> Fidelity: **0 of 24 unfaithful** (the 1 new read by eye; all 24 rebuilt by script)
> Hand variants: 70 · 60 caught by a pass card · every gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test edited in this round, no commit.

### New tests
Each was read against its card and matches its recipe. "Fails" means the variant fails that card, on the reference with `--runxfail`.

| Card | Recipe | Fails |
|---|---|---|
| DLV-SD-12 | R-1 | `sd_r4_by_only_if_given` |

### Rest of the batch
All 70 variants ran again, each reaching all 24 tests. Left without a pass card: the ten under "Considered and not listed". None is a new rule gap.

### Reproduced
- **Result line of the notes holds:** `23 passed, 1 xfailed` in 5 of 5 default runs, the coverage run among them. No flaky test.
- **`--runxfail`:** `1 failed, 23 passed`.
- **Reference:** 24 passed with `--runxfail`, on the bases of round 1. **Alarm:** with the markers on, `1 failed, 23 passed`, the strict cards `XPASS(strict)`.
- **Traceability:** cases 24 · tests 24 · unmatched: none · marker mismatches: none. `rebuild.py`: 252 cards over the nine files, 1 report, the `while` of WSP-IN-04. Selftest: 1299 of 1299 planted mistakes of 60 kinds. `ruff check` passes.
- **Limit:** I kept no copy of the round 1 file, so "existing tests unchanged" rests on the rebuild of all 24 against their cards, not on a line diff.

### Commands run
```
drive.py vars <module>                 70 variants, all reached all 24 tests
r2check.py                                                gap variants against their cards
drive.py bases <module>                                   as under Reproduced
repro.py <module>                                         as under Reproduced
rebuild.py; rebuild.py --selftest 6                       252 cards, 1 report; 1299 of 1299
.venv/Scripts/python.exe -m ruff check <the eight test files>     All checks passed!
git diff --stat -- app/dao                                (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\`. Only this report was edited in the repo. Nothing was stopped or killed.
