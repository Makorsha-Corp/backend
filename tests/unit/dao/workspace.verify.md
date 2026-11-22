# Verification — `app/dao/workspace.py`

> **Current verdict: PASS** (round 2, 2026-11-02, revision 2, 23 cases). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 20 passed · 0 xfail (reproduced ✅) · coverage 100% branch (8 statements, 0 branches)
> Mutation: 2 mutants · 2 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 20 unfaithful** (20 / 20 right)
> Hand variants: 42 · 35 caught by a pass card · 7 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 20 match their cards. WSP-IN-04's wait is in the test and now in the card (revision 1): `while utcnow() <= u0: pass`.
- **One harmless order difference, not counted:** the card's Conventions take the snapshot after the last Given line, and the test takes `before_a` just before the wait. The wait reads only the clock, so the snapshot is the same either way.
- **Why NEEDS WORK:** `mutate.py` has 2 sites and both die. Hand variants show 2 rule gaps, both for the case designer.

Written by Claude (all 20 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 20. No `workspace.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_slug` R2 "The compare is exact" | Every miss card differs by case, a space or a wildcard. No card asks for a part of a stored slug, so a substring match passes, and `create_workspace` would refuse a free slug. | `txt_contains_auto`, `txt_startswith`, `txt_endswith` pass all 20. | **case designer** |
| 2 | case-missing | Side effects: none | A read may leave a change for the caller's next commit, or drop the caller's own unflushed edit. WSP-GS-15 checks new rows and statements sent, not edited rows. | `gs_w_dirty_hit`, `gs_w_expire` pass all 20. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\prop\test_prop.py`, not in the repo. Each passes on today's code and on the reference. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | two new cards, R2 | A = W("acme-co"); When `slug="acme"`, and again with `slug="co"` | `result is None` | pass | `txt_contains_auto`, `txt_startswith`, `txt_endswith` |
| R-2 | new card, Side effects | A = W("acme-co"); B = W("beta-co"); `B.name = "Edited"`, not flushed; When `slug="acme-co"` | `result.id == A.id`; `session: B in db.dirty`; `session: len(db.dirty) == 1` | pass | `gs_w_dirty_hit`, `gs_w_expire` |

## Surviving mutants
None. All 2 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 2 mutants with no `-x`: every run reached all 20 tests, with no collection or setup error.

## Hand variants
`plug\variants.py`, on the reference with `--runxfail`, default plan. Every edit was asserted to apply once and every run reached all 20 tests. Group names: the rule, `w` writes and session, `s` side effects, `txt` the text compare, `kw` keyword-only.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| txt | 20 | 16 | WSP-GS-01, WSP-GS-02, WSP-GS-03, WSP-GS-04, WSP-GS-05, WSP-GS-06 … | `txt_contains_auto`, `txt_startswith`, `txt_endswith`, `txt_trim_col` |
| gs_w | 10 | 8 | WSP-GS-01, WSP-GS-05, WSP-GS-12, WSP-GS-13, WSP-GS-14, WSP-GS-15 | `gs_w_expire`, `gs_w_dirty_hit` |
| r4 | 4 | 3 | WSP-GS-02, WSP-GS-03, WSP-GS-04, WSP-GS-06, WSP-GS-07, WSP-GS-08 … | `r4_one_or_none` |
| r5 | 3 | 3 | WSP-GS-01, WSP-GS-05, WSP-GS-12, WSP-GS-13, WSP-GS-15 | — |
| kw | 1 | 1 | WSP-GS-16 | — |
| n1 | 1 | 1 | WSP-IN-01 | — |
| n2 | 1 | 1 | WSP-IN-02 | — |
| n3 | 2 | 2 | WSP-IN-04 | — |
| **Total** | **42** | **35** |  | **7** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `txt_trim_col` | A stored slug with spaces cannot be made: `WorkspaceCreate` refuses it, and the column is the unique key. |
| `r4_one_or_none` | **Equivalent.** A unique constraint or primary key leaves one row, so `.one_or_none()` cannot differ from `.first()`. |

## xfail tests against the reference
No xfail card.

## Reproduced claims
- **Result line of the notes holds:** `20 passed` in 5 of 5 default runs, the coverage run among them. No flaky test.
- `--runxfail`, on 3 plans: `20 passed`.
- **Mocks:** none. No `try`, no broad `pytest.raises`, no `if` in a test body.

## Carried, not findings
- `workspace.spec.md` N3 still says `updated_at` is later than `created_at` inside one test, which holds only because of the wait. For the describer, when next touched.

## Traceability
cases 20 · tests 20 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script rebuilt each test's Given, snapshots, When, Then and marker from its card and compared by AST, for all 221 cards of the batch, with the helpers against the Conventions. It gave 2 reports, both the wait of WSP-IN-04 (see `workspace.verify.md`). Selftest: 1283 of 1283 planted mistakes of 60 kinds, in tests, helpers and cards.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live. Each kill is a plain `N failed`.
- **Reference DDL** ran inside each test's own rolled-back transaction, in three short runs per module that needs it, on the shared test database. Nothing persisted. Hand variants ran without it, and the bug cards it serves are left out of their counts.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/workspace.py tests/unit/dao/test_workspace.py --timeout 300 --json <scratch>/res/mut_workspace.json   (through runmut.py)
  2 mutants · 2 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_workspace.py -q -p no:cacheprovider --cov=app.dao.workspace --cov-branch --cov-report=term-missing --tb=no
  20 passed
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

## Round 2 — 2026-11-02 (revision 2, narrow)

> **Verdict:** PASS
> Tests: 23 passed · 0 xfail (reproduced ✅) · coverage 100% branch (8 statements, 0 branches)
> Mutation: not re-run; round 1 stands at 2 / 2 → 100% (2 mutants)
> Fidelity: **0 of 23 unfaithful** (the 3 new read by eye; all 23 rebuilt by script)
> Hand variants: 42 · 40 caught by a pass card · every gap variant fails its new card
> Source commit: e48a092 · Cases revision: 2; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test edited in this round, no commit.

WSP-IN-04's snapshot now follows the wait, as the card's Conventions say, so round 1's order difference is gone. My script's one report here is the `while` itself, which the card prescribes.

### New tests
Each was read against its card and matches its recipe. "Fails" means the variant fails that card, on the reference with `--runxfail`.

| Card | Recipe | Fails |
|---|---|---|
| WSP-GS-17 | R-1 | `txt_contains_auto`, `txt_startswith` |
| WSP-GS-18 | R-1 | `txt_contains_auto`, `txt_endswith` |
| WSP-GS-19 | R-2 | `gs_w_dirty_hit`, `gs_w_expire` |

### Rest of the batch
All 42 variants ran again, each reaching all 23 tests. Left without a pass card: `txt_trim_col`, `r4_one_or_none`. None is a new rule gap.

### Reproduced
- **Result line of the notes holds:** `23 passed` in 5 of 5 default runs, the coverage run among them. No flaky test.
- **`--runxfail`:** `23 passed`.
- **Reference:** 23 passed with `--runxfail`, on the bases of round 1. No xfail card, so no alarm to check.
- **Traceability:** cases 23 · tests 23 · unmatched: none · marker mismatches: none. `rebuild.py`: 252 cards over the nine files, 1 report, the `while` of WSP-IN-04. Selftest: 1299 of 1299 planted mistakes of 60 kinds. `ruff check` passes.
- **Limit:** I kept no copy of the round 1 file, so "existing tests unchanged" rests on the rebuild of all 23 against their cards, not on a line diff.

### Commands run
```
drive.py vars <module>                 42 variants, all reached all 23 tests
r2check.py                                                gap variants against their cards
drive.py bases <module>                                   as under Reproduced
repro.py <module>                                         as under Reproduced
rebuild.py; rebuild.py --selftest 6                       252 cards, 1 report; 1299 of 1299
.venv/Scripts/python.exe -m ruff check <the eight test files>     All checks passed!
git diff --stat -- app/dao                                (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\`. Only this report was edited in the repo. Nothing was stopped or killed.
