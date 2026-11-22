# Verification — `app/dao/order_workflow.py`

> **Current verdict: PASS** (round 2, 2026-11-02, revision 1, 30 cases). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 24 passed · 1 xfail, strict (reproduced ✅) · coverage 100% branch (8 statements, 0 branches)
> Mutation: 3 mutants · 3 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 25 unfaithful** (25 / 25 right)
> Hand variants: 52 · 42 caught by a pass card · 10 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** This is the second file read fully by eye, against every card. All 25 match, and the script agrees.
- **Why NEEDS WORK:** 3 sites, all killed, but hand variants show 3 rule gaps. Each is a missing test on a rule already decided, so no owner question arises from them.

Written by Claude (all 25 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 25. No `order_workflow.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_type` R3 "The compare is exact" | The miss cards change case or spaces or use `%`. No card asks for a part of the type, or uses `_`. | `txt_contains_auto`, `txt_startswith`, `txt_endswith`, `txt_like_esc_pct` pass all 25. | **case designer** |
| 2 | case-missing | `get_by_type` R3 | Every card stores a clean type. `type` is unvalidated text (FU-1), so a stored value with a space can exist, and trimming the stored side is never seen. | `txt_trim_col` passes all 25. | **case designer** |
| 3 | case-missing | Side effects: none | A read may leave a change for the caller's next commit, or drop the caller's own unflushed edit. OWF-GT-19 checks new rows and statements sent, not edited rows. | `gt_w_dirty_hit`, `gt_w_expire` pass all 25. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\prop\test_prop.py`, not in the repo. Each passes on today's code and on the reference. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | three new cards, R3 | A = workflow; When `workflow_type="PF"`, `"FM"`, `"P_M"` | `result is None` | pass | `txt_contains_auto`, `txt_startswith`, `txt_endswith`, `txt_like_esc_pct` |
| R-2 | new card, R3 | A = workflow, but `type " PFM"`; When `workflow_type="PFM"` | `result is None` | pass | `txt_trim_col` |
| R-3 | new card, Side effects | A = workflow; B = workflow, but `type "STM"`; `B.description = "Edited"`, not flushed; When `workflow_type="PFM"` | `result.id == A.id`; `session: B in db.dirty`; `session: len(db.dirty) == 1` (`session:` as in `workspace.cases.md`) | pass | `gt_w_dirty_hit`, `gt_w_expire` |

## Surviving mutants
None. All 3 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 3 mutants with no `-x`: every run reached all 25 tests, with no collection or setup error.

## Hand variants
`plug\variants.py`, on the reference with `--runxfail`, default plan. Every edit was asserted to apply once and every run reached all 25 tests. Group names: the rule, `w` writes and session, `s` side effects, `txt` the text compare, `kw` keyword-only.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| txt | 20 | 15 | OWF-GT-01, OWF-GT-02, OWF-GT-03, OWF-GT-04, OWF-GT-05, OWF-GT-08 … | `txt_like_esc_pct`, `txt_contains_auto`, `txt_startswith`, `txt_endswith`, `txt_trim_col` |
| gt_w | 10 | 8 | OWF-GT-01, OWF-GT-02, OWF-GT-03, OWF-GT-04, OWF-GT-14, OWF-GT-15 … | `gt_w_expire`, `gt_w_dirty_hit` |
| r2 | 5 | 5 | OWF-GT-01, OWF-GT-02, OWF-GT-03, OWF-GT-04, OWF-GT-06, OWF-GT-07 … | — |
| r4 | 3 | 3 | OWF-GT-12, OWF-GT-13 | — |
| r1 | 4 | 3 | OWF-GT-01, OWF-GT-02, OWF-GT-03, OWF-GT-04, OWF-GT-05, OWF-GT-06 … | `r1_one_or_none` |
| r5 | 3 | 3 | OWF-GT-01, OWF-GT-03, OWF-GT-04, OWF-GT-14, OWF-GT-15, OWF-GT-16 … | — |
| o3 | 1 | 1 | OWF-GT-17 | — |
| kw | 1 | 0 | — | `kw_positional` |
| n1 | 3 | 3 | OWF-IN-01, OWF-IN-02, OWF-IN-03 | — |
| n2 | 1 | 1 | OWF-IN-04 | — |
| n3 | 1 | 0 | — | `n3_detach` |
| **Total** | **52** | **42** |  | **10** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `n3_detach` | **Bug path.** Today's behaviour of BUG-1222; caught by OWF-IN-05 alone, which is what that card is for. |
| `r1_one_or_none` | **Equivalent.** A unique constraint or primary key leaves one row, so `.one_or_none()` cannot differ from `.first()`. |
| `kw_positional` | A note, not a rule: cases Spec gap 1, as in `work_order_approver.verify.md`. |

## xfail tests against the reference
Reference: `passive_deletes="all"` on the `purchase_orders` backref, swapped in memory. Nothing is written to `app/`.

With `--runxfail` on the reference: 25 passed. **The alarm works:** with the markers on, `1 failed, 24 passed`, the strict cards `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| OWF-IN-05 | strict | Then 1, `DID NOT RAISE`, as the card says |

## Reproduced claims
- **Result line of the notes holds:** `24 passed, 1 xfailed` in 5 of 5 default runs, the coverage run among them. No flaky test.
- `--runxfail`, on 3 plans: `1 failed, 24 passed`.
- **Mocks:** none. No `try`, no broad `pytest.raises`, no `if` in a test body.

## Carried, not findings
- **Order, carried from cases Spec gap 2, still open:** "a list changed in place is not saved" is stated as a fact, with no rule. The sequence decides which orders count as finished. The cases file asks whether a rule is wanted. For the owner.

## Traceability
cases 25 · tests 25 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script rebuilt each test's Given, snapshots, When, Then and marker from its card and compared by AST, for all 221 cards of the batch, with the helpers against the Conventions. It gave 2 reports, both the wait of WSP-IN-04 (see `workspace.verify.md`). Selftest: 1283 of 1283 planted mistakes of 60 kinds, in tests, helpers and cards.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live. Each kill is a plain `N failed`.
- **Reference DDL** ran inside each test's own rolled-back transaction, in three short runs per module that needs it, on the shared test database. Nothing persisted. Hand variants ran without it, and the bug cards it serves are left out of their counts.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/order_workflow.py tests/unit/dao/test_order_workflow.py --timeout 300 --json <scratch>/res/mut_order_workflow.json   (through runmut.py)
  3 mutants · 3 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_order_workflow.py -q -p no:cacheprovider --cov=app.dao.order_workflow --cov-branch --cov-report=term-missing --tb=no
  24 passed, 1 xfailed
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
> Tests: 29 passed · 1 xfail, strict (reproduced ✅) · coverage 100% branch (8 statements, 0 branches)
> Mutation: not re-run; round 1 stands at 3 / 3 → 100% (3 mutants)
> Fidelity: **0 of 30 unfaithful** (the 5 new read by eye; all 30 rebuilt by script)
> Hand variants: 52 · 49 caught by a pass card · every gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test edited in this round, no commit.

Cases Spec gap 2, on a list changed in place, is still open for the owner, as in round 1.

### New tests
Each was read against its card and matches its recipe. "Fails" means the variant fails that card, on the reference with `--runxfail`.

| Card | Recipe | Fails |
|---|---|---|
| OWF-GT-20 | R-1 | `txt_contains_auto`, `txt_startswith` |
| OWF-GT-21 | R-1 | `txt_contains_auto`, `txt_endswith` |
| OWF-GT-22 | R-1 | `txt_like_esc_pct` |
| OWF-GT-23 | R-2 | `txt_trim_col`, and also `txt_contains_auto`, `txt_endswith` |
| OWF-GT-24 | R-3 | `gt_w_dirty_hit`, `gt_w_expire` |

### Rest of the batch
All 52 variants ran again, each reaching all 30 tests. Left without a pass card: `n3_detach`, `r1_one_or_none`, `kw_positional`. None is a new rule gap.

### Reproduced
- **Result line of the notes holds:** `29 passed, 1 xfailed` in 5 of 5 default runs, the coverage run among them. No flaky test.
- **`--runxfail`:** `1 failed, 29 passed`.
- **Reference:** 30 passed with `--runxfail`, on the bases of round 1. **Alarm:** with the markers on, `1 failed, 29 passed`, the strict cards `XPASS(strict)`.
- **Traceability:** cases 30 · tests 30 · unmatched: none · marker mismatches: none. `rebuild.py`: 252 cards over the nine files, 1 report, the `while` of WSP-IN-04. Selftest: 1299 of 1299 planted mistakes of 60 kinds. `ruff check` passes.
- **Limit:** I kept no copy of the round 1 file, so "existing tests unchanged" rests on the rebuild of all 30 against their cards, not on a line diff.

### Commands run
```
drive.py vars <module>                 52 variants, all reached all 30 tests
r2check.py                                                gap variants against their cards
drive.py bases <module>                                   as under Reproduced
repro.py <module>                                         as under Reproduced
rebuild.py; rebuild.py --selftest 6                       252 cards, 1 report; 1299 of 1299
.venv/Scripts/python.exe -m ruff check <the eight test files>     All checks passed!
git diff --stat -- app/dao                                (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\`. Only this report was edited in the repo. Nothing was stopped or killed.
