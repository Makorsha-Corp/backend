# Verification — `app/dao/subscription_plan.py`

> **Current verdict: PASS** (round 2, 2026-11-02, revision 1, 12 cases). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 10 passed · 1 xfail, strict (reproduced ✅) · coverage 90% (10 statements, 1 missed: line 15, dead; 0 branches)
> Mutation: 7 mutants · 5 killed · 2 survived → score 100% (after excluding 0 equivalent, 2 dead, 0 bug-path)
> Fidelity: **0 of 11 unfaithful** (11 / 11 right)
> Hand variants: 24 · 19 caught by a pass card · 5 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 11 match their cards.
- The 2 surviving mutants are both on line 15, `get_by_name`, which the spec lists as dead code to remove.
- **Why NEEDS WORK:** one rule gap on Side effects, for the case designer. Nothing touches a plan or a price.

Written by Claude (all 11 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 11. No `subscription_plan.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | Side effects: none | A read may leave a change for the caller's next commit, or drop the caller's own unflushed edit. SBP-GD-11 checks new rows and statements sent, not edited rows. | `gd_w_dirty_hit`, `gd_w_expire` pass all 11. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\prop\test_prop.py`, not in the repo. Each passes on today's code and on the reference. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, Side effects | A = plan `name "Free"`, `is_default True`; B = plan `name "Starter"`; `B.display_name = "Edited"`, not flushed | `result.id == A.id`; `session: B in db.dirty`; `session: len(db.dirty) == 1` (`session:` as in `workspace.cases.md`) | pass | `gd_w_dirty_hit`, `gd_w_expire` |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | 15 | `return` → `return None` | dead | `get_by_name`, Not specified in the spec: to be removed (Q1) | — |
| 3 | 15 | `==` → `!=` | dead | the same line | — |

**Guard.** My own driver re-ran each of the 7 mutants with no `-x`: every run reached all 11 tests, with no collection or setup error.

## Hand variants
`plug\variants.py`, on the reference with `--runxfail`, default plan. Every edit was asserted to apply once and every run reached all 11 tests. Group names: the rule, `w` writes and session, `s` side effects, `txt` the text compare, `kw` keyword-only.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| gd_w | 10 | 8 | SBP-GD-01, SBP-GD-03, SBP-GD-06, SBP-GD-10, SBP-GD-11 | `gd_w_expire`, `gd_w_dirty_hit` |
| r1 | 6 | 6 | SBP-GD-01, SBP-GD-02, SBP-GD-03, SBP-GD-04, SBP-GD-06, SBP-GD-08 … | — |
| r2 | 1 | 1 | SBP-GD-02, SBP-GD-06, SBP-GD-10 | — |
| r3 | 1 | 1 | SBP-GD-04, SBP-GD-06 | — |
| r4 | 4 | 3 | SBP-GD-02, SBP-GD-04, SBP-GD-05, SBP-GD-06, SBP-GD-10 | `r4_one_or_none` |
| x | 2 | 0 | — | `x_not_custom`, `x_order_desc` |
| **Total** | **24** | **19** |  | **5** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `x_not_custom` | An added filter on a column no rule names. No finite card set closes every such column. |
| `x_order_desc` | **Equivalent under R5:** the index leaves one candidate. |
| `r4_one_or_none` | **Equivalent under R5:** one candidate. Today it differs only with two active defaults, which no pass card builds, by design. |

## xfail tests against the reference
Reference: a partial unique index on `((1)) WHERE is_default AND is_active`, created in each test's own transaction and rolled back with it. Nothing is written to `app/`.

With `--runxfail` on the reference: 11 passed. **The alarm works:** with the markers on, `1 failed, 10 passed`, the strict cards `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| SBP-GD-07 | strict | Then 1, `DID NOT RAISE`, as the card says |

## Reproduced claims
- **Result line of the notes holds:** `10 passed, 1 xfailed` in 5 of 5 default runs, the coverage run among them. No flaky test.
- `--runxfail`, on 3 plans: `1 failed, 10 passed`.
- **Mocks:** none. No `try`, no broad `pytest.raises`, no `if` in a test body.

## Traceability
cases 11 · tests 11 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script rebuilt each test's Given, snapshots, When, Then and marker from its card and compared by AST, for all 221 cards of the batch, with the helpers against the Conventions. It gave 2 reports, both the wait of WSP-IN-04 (see `workspace.verify.md`). Selftest: 1283 of 1283 planted mistakes of 60 kinds, in tests, helpers and cards.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live. Each kill is a plain `N failed`.
- **Reference DDL** ran inside each test's own rolled-back transaction, in three short runs per module that needs it, on the shared test database. Nothing persisted. Hand variants ran without it, and the bug cards it serves are left out of their counts.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/subscription_plan.py tests/unit/dao/test_subscription_plan.py --timeout 300 --json <scratch>/res/mut_subscription_plan.json   (through runmut.py)
  7 mutants · 5 killed · 2 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_subscription_plan.py -q -p no:cacheprovider --cov=app.dao.subscription_plan --cov-branch --cov-report=term-missing --tb=no
  10 passed, 1 xfailed
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
> Tests: 11 passed · 1 xfail, strict (reproduced ✅) · coverage 90% (10 statements, 1 missed: line 15, dead; 0 branches)
> Mutation: not re-run; round 1 stands at 5 / 5 → 100% (7 mutants, 2 dead)
> Fidelity: **0 of 12 unfaithful** (the 1 new read by eye; all 12 rebuilt by script)
> Hand variants: 24 · 21 caught by a pass card · every gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test edited in this round, no commit.

### New tests
Each was read against its card and matches its recipe. "Fails" means the variant fails that card, on the reference with `--runxfail`.

| Card | Recipe | Fails |
|---|---|---|
| SBP-GD-12 | R-1 | `gd_w_dirty_hit`, `gd_w_expire` |

### Rest of the batch
All 24 variants ran again, each reaching all 12 tests. Left without a pass card: `x_not_custom`, `x_order_desc`, `r4_one_or_none`. None is a new rule gap.

### Reproduced
- **Result line of the notes holds:** `11 passed, 1 xfailed` in 5 of 5 default runs, the coverage run among them. No flaky test.
- **`--runxfail`:** `1 failed, 11 passed`.
- **Reference:** 12 passed with `--runxfail`, on the bases of round 1. **Alarm:** with the markers on, `1 failed, 11 passed`, the strict cards `XPASS(strict)`.
- **Traceability:** cases 12 · tests 12 · unmatched: none · marker mismatches: none. `rebuild.py`: 252 cards over the nine files, 1 report, the `while` of WSP-IN-04. Selftest: 1299 of 1299 planted mistakes of 60 kinds. `ruff check` passes.
- **Limit:** I kept no copy of the round 1 file, so "existing tests unchanged" rests on the rebuild of all 12 against their cards, not on a line diff.

### Commands run
```
drive.py vars <module>                 24 variants, all reached all 12 tests
r2check.py                                                gap variants against their cards
drive.py bases <module>                                   as under Reproduced
repro.py <module>                                         as under Reproduced
rebuild.py; rebuild.py --selftest 6                       252 cards, 1 report; 1299 of 1299
.venv/Scripts/python.exe -m ruff check <the eight test files>     All checks passed!
git diff --stat -- app/dao                                (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\`. Only this report was edited in the repo. Nothing was stopped or killed.
