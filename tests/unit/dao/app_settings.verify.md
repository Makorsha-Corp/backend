# Verification — `app/dao/app_settings.py`

> **Current verdict: PASS** (round 2, 2026-11-02, revision 1, 23 cases). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 15 passed · 2 xfail, both strict (reproduced ✅) · coverage 100% branch (9 statements, 0 branches)
> Mutation: 3 mutants · 3 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 17 unfaithful** (17 / 17 right)
> Hand variants: 43 · 33 caught by a pass card · 10 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 17 match their cards.
- **Why NEEDS WORK:** 3 sites, all killed, but hand variants show 3 rule gaps. The one that matters most is Finding 2: R4 says the lookup stays exact after BUG-1225, and a lookup rewritten to match the new normalised index passes every card.

Written by Claude (all 17 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 17. No `app_settings.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_name` R3 "The compare is exact" | The miss cards change case or spaces or use `%`. No card asks for a part of the name, or uses `_`, so a substring match or a `LIKE` escaping only `%` passes. | `txt_contains_auto`, `txt_startswith`, `txt_endswith`, `txt_like_esc_pct` pass all 17. | **case designer** |
| 2 | case-missing | `get_by_name` R3, R4 "The lookup itself stays exact" | Every card stores `feat` and varies the argument. Normalising the stored side is never seen, and that is the likely slip when BUG-1225's index is fixed. | `txt_lower_col`, `txt_trim_col` pass all 17. | **case designer** |
| 3 | case-missing | Side effects: none | A read may leave a change for the caller's next commit, or drop the caller's own unflushed edit. ASG-GN-13 checks new rows and statements sent, not edited rows. | `gn_w_expire` passes all 17. `gn_w_dirty_hit` is caught only because the flag it flips is the row's one spare column. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\prop\test_prop.py`, not in the repo. Each passes on today's code and on the reference. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | three new cards, R3 | A = setting; When `name="fe"`, `name="at"`, `name="fe_t"` | `result is None` | pass | `txt_contains_auto`, `txt_startswith`, `txt_endswith`, `txt_like_esc_pct` |
| R-2 | two new cards, R3, R4 | A = setting, but `name "Feat"`, and again `name " feat"`; When `name="feat"` | `result is None` | pass | `txt_lower_col`, `txt_trim_col` |
| R-3 | new card, Side effects | A = setting; B = setting, but `name "beta"`; `B.enabled = False`, not flushed; When `name="feat"` | `result.id == A.id`; `session: B in db.dirty`; `session: len(db.dirty) == 1` (`session:` as in `workspace.cases.md`) | pass | `gn_w_expire` |

## Surviving mutants
None. All 3 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 3 mutants with no `-x`: every run reached all 17 tests, with no collection or setup error.

## Hand variants
`plug\variants.py`, on the reference with `--runxfail`, default plan. Every edit was asserted to apply once and every run reached all 17 tests. Group names: the rule, `w` writes and session, `s` side effects, `txt` the text compare, `kw` keyword-only.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| txt | 20 | 14 | ASG-GN-01, ASG-GN-02, ASG-GN-03, ASG-GN-06, ASG-GN-07, ASG-GN-08 … | `txt_like_esc_pct`, `txt_contains_auto`, `txt_startswith`, `txt_endswith`, `txt_lower_col`, `txt_trim_col` |
| gn_w | 10 | 9 | ASG-GN-01, ASG-GN-02, ASG-GN-03, ASG-GN-12, ASG-GN-13 | `gn_w_expire` |
| r2 | 6 | 6 | ASG-GN-01, ASG-GN-02, ASG-GN-03, ASG-GN-04, ASG-GN-05, ASG-GN-06 … | — |
| r1 | 3 | 2 | ASG-GN-02, ASG-GN-04, ASG-GN-05, ASG-GN-06, ASG-GN-07, ASG-GN-08 … | `r1_one_or_none` |
| r3 | 2 | 2 | ASG-GN-10, ASG-GN-11 | — |
| x | 1 | 0 | — | `x_order_desc` |
| kw | 1 | 0 | — | `kw_positional` |
| **Total** | **43** | **33** |  | **10** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `r1_one_or_none`, `x_order_desc` | **Equivalent under R4:** one candidate. Today they differ only with two rows of one name, which no pass card builds, by design. |
| `kw_positional` | A note, not a rule: cases Spec gap 1, as in `work_order_approver.verify.md`. |

## xfail tests against the reference
Reference: a unique index on `(workspace_id, lower(btrim(name)))`, created in each test's own transaction and rolled back with it. Nothing is written to `app/`.

With `--runxfail` on the reference: 17 passed. **The alarm works:** with the markers on, `2 failed, 15 passed`, the strict cards `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| ASG-CR-01, ASG-CR-02 | strict | Then 1, `DID NOT RAISE`, as the cards say |

## Reproduced claims
- **Result line of the notes holds:** `15 passed, 2 xfailed` in 5 of 5 default runs, the coverage run among them. No flaky test.
- `--runxfail`, on 3 plans: `2 failed, 15 passed`.
- **Mocks:** none. No `try`, no broad `pytest.raises`, no `if` in a test body.

## Traceability
cases 17 · tests 17 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script rebuilt each test's Given, snapshots, When, Then and marker from its card and compared by AST, for all 221 cards of the batch, with the helpers against the Conventions. It gave 2 reports, both the wait of WSP-IN-04 (see `workspace.verify.md`). Selftest: 1283 of 1283 planted mistakes of 60 kinds, in tests, helpers and cards.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live. Each kill is a plain `N failed`.
- **Reference DDL** ran inside each test's own rolled-back transaction, in three short runs per module that needs it, on the shared test database. Nothing persisted. Hand variants ran without it, and the bug cards it serves are left out of their counts.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/app_settings.py tests/unit/dao/test_app_settings.py --timeout 300 --json <scratch>/res/mut_app_settings.json   (through runmut.py)
  3 mutants · 3 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_app_settings.py -q -p no:cacheprovider --cov=app.dao.app_settings --cov-branch --cov-report=term-missing --tb=no
  15 passed, 2 xfailed
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
> Tests: 21 passed · 2 xfail, both strict (reproduced ✅) · coverage 100% branch (9 statements, 0 branches)
> Mutation: not re-run; round 1 stands at 3 / 3 → 100% (3 mutants)
> Fidelity: **0 of 23 unfaithful** (the 6 new read by eye; all 23 rebuilt by script)
> Hand variants: 43 · 40 caught by a pass card · every gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test edited in this round, no commit.

### New tests
Each was read against its card and matches its recipe. "Fails" means the variant fails that card, on the reference with `--runxfail`.

| Card | Recipe | Fails |
|---|---|---|
| ASG-GN-14 | R-1 | `txt_contains_auto`, `txt_startswith` |
| ASG-GN-15 | R-1 | `txt_contains_auto`, `txt_endswith` |
| ASG-GN-16 | R-1 | `txt_like_esc_pct` |
| ASG-GN-17 | R-2 | `txt_lower_col` |
| ASG-GN-18 | R-2 | `txt_trim_col`, and also `txt_contains_auto`, `txt_endswith` |
| ASG-GN-19 | R-3 | `gn_w_expire` |

### Rest of the batch
All 43 variants ran again, each reaching all 23 tests. Left without a pass card: `r1_one_or_none`, `x_order_desc`, `kw_positional`. None is a new rule gap.

### Reproduced
- **Result line of the notes holds:** `21 passed, 2 xfailed` in 5 of 5 default runs, the coverage run among them. No flaky test.
- **`--runxfail`:** `2 failed, 21 passed`.
- **Reference:** 23 passed with `--runxfail`, on the bases of round 1. **Alarm:** with the markers on, `2 failed, 21 passed`, the strict cards `XPASS(strict)`.
- **Traceability:** cases 23 · tests 23 · unmatched: none · marker mismatches: none. `rebuild.py`: 252 cards over the nine files, 1 report, the `while` of WSP-IN-04. Selftest: 1299 of 1299 planted mistakes of 60 kinds. `ruff check` passes.
- **Limit:** I kept no copy of the round 1 file, so "existing tests unchanged" rests on the rebuild of all 23 against their cards, not on a line diff.

### Commands run
```
drive.py vars <module>                 43 variants, all reached all 23 tests
r2check.py                                                gap variants against their cards
drive.py bases <module>                                   as under Reproduced
repro.py <module>                                         as under Reproduced
rebuild.py; rebuild.py --selftest 6                       252 cards, 1 report; 1299 of 1299
.venv/Scripts/python.exe -m ruff check <the eight test files>     All checks passed!
git diff --stat -- app/dao                                (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\`. Only this report was edited in the repo. Nothing was stopped or killed.
