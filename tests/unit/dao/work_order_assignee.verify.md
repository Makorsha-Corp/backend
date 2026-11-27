# Verification — `app/dao/work_order_assignee.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 34 passed · 0 xfail (reproduced ✅) · coverage 100% branch (25 statements, 8 branches)
> Mutation: 13 mutants · 13 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 34 unfaithful** (34 / 34 right)
> Hand variants: 30 · 28 caught by a pass card · 2 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 34 match their cards.
- **Why NEEDS WORK:** one rule gap for the case designer. `get_user_ids_by_order` has no card asking for W2 while a W1 row exists.

Written by Claude (all 34 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 34. No `work_order_assignee.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_user_ids_by_order` R2 (another workspace) | GU cards ask for W1 with the other row in W2. A `<=` on `workspace_id` leaks the earlier workspace's rows. `get_user_ids_by_orders` has a W2-asked card. | `gu_ws_le` passes all 34. Recipe R-1. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\prop\prop_work_order_assignee.py`, not in the repo, run by `propdrive.py` in a temporary copy of the backend. Each passes on today's code (the xfail ones xfail or xpass, as non-strict allows) and on my reference with `--runxfail`. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card WOA-GU-10, R2 | A = row, `user_id U1.id`; B = row, `user_id U2.id`, but `workspace_id W2.id`; When `get_user_ids_by_order(db, work_order_id=WO1.id, workspace_id=W2.id)` | `result == [U2.id]` | pass | `gu_ws_le` |

## Surviving mutants
None. Every kill ends in a plain `N failed`.

**Guard.** My own driver (`drive.py muts`) re-ran every mutant of mutate.py's own list with no `-x`. Every run reached every pass test, with no collection or setup error, and each kill or survival matched mutate.py's.

## Hand variants
My reference fix and the variants are a pytest plugin, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\plug\attvref.py` (`-p attvref`). It replaces the DAO's methods in-process with the spec's intended behaviour, bug rules included; nothing is written to `app/`. Runs used `--runxfail` on the default plan. Every variant was asserted to be applied, and every run reached all 34 tests. Group = the method's tag.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| go | 12 | 12 | WOA-GO-01, WOA-GO-02, WOA-GO-03, WOA-GO-04, WOA-GO-05, WOA-GO-06 … | — |
| gu | 10 | 9 | WOA-GU-01, WOA-GU-02, WOA-GU-03, WOA-GU-04, WOA-GU-05, WOA-GU-06 … | `gu_ws_le` |
| rp | 8 | 7 | WOA-RP-01, WOA-RP-02, WOA-RP-03, WOA-RP-05, WOA-RP-06, WOA-RP-07 … | `rp_sync` |
| **Total** | **30** | **28** |  | **2** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `rp_sync` | `synchronize_session="fetch"`: R7's observable (a loaded `assignee_links` collection keeps the old rows) holds under both, and RP's R7 card passes. Only the identity-map state of the old row objects differs, which no rule names. |

## Reproduced claims
- **Result line of the notes holds:** `34 passed` in 3 of 3 default runs, the coverage run among them, and again in the mutation and variant bases. No flaky test.
- **Mocks:** only those the Conventions name (the commit spy). No `try`, no broad `pytest.raises`. `ruff check` passes.

## Traceability
cases 34 · tests 34 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules (several end with a period the card lacks; cosmetic). `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All tests sit under `# [claude] <ID>`.

My own script (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\tools\rebuild.py`) compares each test with its card by AST and by text: name, docstring, marker, the When call's arguments, each Given line in order, each Then line's expression, operators and literals. Over the 433 cards of this batch it leaves no unexplained report; each report it gave was read by eye. Eye-read here: the differences the script reported (WOA-GO-05, GU-05, RP-01, RP-02) and every pending-row and edit line. Selftest: 1306 of 1334 planted mistakes of 22 kinds reported. The 28 it misses are values inside pending-row code lines and re-read lines that go through a helper; those lines were read by eye in every module.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live on the shared test database. Each kill is a plain `N failed`.
- **Variants ran on the default plan only**, not under forced plans; the order cards' plan sensitivity is the executor's notes'.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/work_order_assignee.py tests/unit/dao/test_work_order_assignee.py --timeout 300 --json <scratch>/res/mut_work_order_assignee.json   (through runmut.sh)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order_assignee.py -q -p no:cacheprovider --cov=app.dao.work_order_assignee --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  34 passed; then 2 more default runs and one --runxfail run
drive.py bases | muts | vars <module>; xfline.py; propdrive.py; rebuild.py; rebuild.py --selftest 8
.venv/Scripts/python.exe -m ruff check <the ten test files>     All checks passed!
git diff --stat -- app/dao                                   (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\`. Only this report was written in the repo. No commit. Nothing was stopped or killed.

## Fix list
1. **Case designer:** add the recipes above; the Givens and Thens are written out.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 35 passed (reproduced ✅) · coverage 100% branch
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 35 unfaithful** (the new and changed tests read by eye; all 35 compared by script)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test or card edited in this round, no commit.

- **New cards:** WOA-GU-10. **Changed:** none. Each new or changed test was read against its card and matches it, its recipe included.

### Gap variants against the new cards
Each round 1 gap variant ran on my reference with `--runxfail` on three plans: default; `enable_seqscan=off`; index, bitmap and index-only scans off. "Fails" means the named card failed in all three runs. Every run reached all tests.

| Variant | Card that must fail | Plans where it failed |
|---|---|---|
| `gu_ws_le` | WOA-GU-10 | default, seqoff, idxoff (3 of 3) |

**Reference bases, `--runxfail`:** default: 35 of 35 passed, seqoff: 35 of 35 passed, idxoff: 35 of 35 passed.

### Reproduced
- `35 passed` in the coverage run. The ten files together gave `411 passed, 50 xfailed, 1 xpassed` in 2 of 2 runs, matching the coordinator's line. No flaky test.
- `ruff check` passes. `rebuild.py` over the ten files reports nothing beyond round 1's known alias noise. `git diff --stat -- app/dao` is empty.

### Commands run
```
rebuild.py <ten modules>; show.py <module> <new and changed ids>     read against the cards
round2.py                                                          gap variants and bases, 3 plans
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order_assignee.py -q -p no:cacheprovider --cov=app.dao.work_order_assignee --cov-branch   (private COVERAGE_FILE)
.venv/Scripts/python.exe -m pytest <the ten test files> -q -p no:cacheprovider     x2
xfline.py; .venv/Scripts/python.exe -m ruff check <the seven test files>
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\`. Only this report was edited in the repo. Nothing was stopped or killed.
