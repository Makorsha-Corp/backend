# Verification — `app/dao/project_component_task.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 33 passed · 5 xfail, 2 strict, 3 non-strict (reproduced ✅) · coverage 100% branch (13 statements, 2 branches)
> Mutation: 17 mutants · 17 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 38 unfaithful** (38 / 38 right)
> Hand variants: 37 · 28 caught by a pass card · 9 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 38 match their cards.
- **Why NEEDS WORK:** 2 rule gaps for the case designer. One is the case-insensitive part of R4, as in `project`; the other is a W2-asked `get_incomplete_tasks`.

Written by Claude (all 38 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 38. No `project_component_task.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_component` R4, `get_incomplete_tasks` R4 [BUG-1447] ("`name` case-insensitive") | As `project.verify.md` Finding 1: GC-12 builds `roof` first, and the collation already sorts GC-11's and GI-08's names case-insensitively. | `gc_ord_case_sensitive`, `gi_ord_case_sensitive` pass all 38, with `--runxfail` too. Recipe R-1. | **case designer** |
| 2 | case-missing | `get_incomplete_tasks` R1 (workspace, as `get_by_component` R1) | Its isolation card asks for W1 with the other row in W2. A `<=` on `workspace_id` leaks the earlier workspace's rows. `get_by_component` has a W2-asked card; this query does not. | `gi_ws_le` passes all 38. Recipe R-2. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\prop\prop_project_component_task.py`, not in the repo, run by `propdrive.py` in a temporary copy of the backend. Each passes on today's code (the xfail ones xfail or xpass, as non-strict allows) and on my reference with `--runxfail`. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | two new cards PCT-GC-23, PCT-GI-17, R4 [BUG-1447] | B = task, `name "Roof"`; A = task, `name "roof"`; C = task, `name "Banana"`; D = task, `name "apple"`; When `get_by_component(db, project_component_id=PC1.id, workspace_id=W1.id)` / `get_incomplete_tasks(...)` with the same arguments | `ids(result) == [D.id, C.id, B.id, A.id]` | xfail BUG-1447 (non-strict); Fails today on: Then 1 | `gc_ord_case_sensitive`, `gi_ord_case_sensitive` |
| R-2 | new card PCT-GI-18, R1 | A = task, `name "Alpha"`; Z = task, `name "Zed"`, but `workspace_id W2.id`; When `get_incomplete_tasks(db, project_component_id=PC1.id, workspace_id=W2.id)` | `ids(result) == [Z.id]` | pass | `gi_ws_le` |

## Rulings asked for
- **Case-insensitive order (executor's note): a real gap.** Same ruling and the same verified recipe as `project.verify.md`.

## Surviving mutants
None. Every kill ends in a plain `N failed`.

**Guard.** My own driver (`drive.py muts`) re-ran every mutant of mutate.py's own list with no `-x`. Every run reached every pass test, with no collection or setup error, and each kill or survival matched mutate.py's.

## Hand variants
My reference fix and the variants are a pytest plugin, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\plug\attvref.py` (`-p attvref`). It replaces the DAO's methods in-process with the spec's intended behaviour, bug rules included; nothing is written to `app/`. Runs used `--runxfail` on the default plan. Every variant was asserted to be applied, and every run reached all 38 tests. Group = the method's tag.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| gc | 19 | 15 | PCT-GC-01, PCT-GC-02, PCT-GC-03, PCT-GC-04, PCT-GC-05, PCT-GC-06 … | `gc_ord_case_sensitive`, `gc_ord_id_desc`, `gc_ord_desc`, `gc_ord_idonly` |
| gi | 18 | 13 | PCT-GI-01, PCT-GI-02, PCT-GI-03, PCT-GI-04, PCT-GI-05, PCT-GI-06 … | `gi_ws_le`, `gi_ord_case_sensitive`, `gi_ord_id_desc`, `gi_ord_desc`, `gi_ord_idonly` |
| **Total** | **37** | **28** |  | **9** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `gc_ord_id_desc`, `gc_ord_desc`, `gc_ord_idonly`, `gi_ord_*` (3) | **Bug path** (BUG-1447). Each fails GC-13 or GI-09 (strict), most also GC-11, GC-12 or GI-08. Extra variants `lower(name), description, id` (not in the table) fail GC-13 and GI-09. |

## xfail tests against the reference
With `--runxfail` on the reference: 38 passed. **The alarm works:** with the markers on, every strict card is `XPASS(strict)`.

| Cards | Marker | Fails today on (`--runxfail`, my script mapping the failing line to its `# Then N`) |
|---|---|---|
| PCT-GC-11, GC-12, GI-08 | non-strict | Then 2 |
| PCT-GC-13, GI-09 | strict | Then 2 |

Each fails on the line its card's "Fails today on" names.

## Reproduced claims
- **Result line of the notes holds:** `33 passed, 5 xfailed` in 3 of 3 default runs, the coverage run among them, and again in the mutation and variant bases. No flaky test.
- **Mocks:** only those the Conventions name (the commit spy). No `try`, no broad `pytest.raises`. `ruff check` passes.

## Traceability
cases 38 · tests 38 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules (several end with a period the card lacks; cosmetic). `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All tests sit under `# [claude] <ID>`.

My own script (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\tools\rebuild.py`) compares each test with its card by AST and by text: name, docstring, marker, the When call's arguments, each Given line in order, each Then line's expression, operators and literals. Over the 433 cards of this batch it leaves no unexplained report; each report it gave was read by eye. Eye-read here: the difference the script reported (PCT-GC-12) and every pending-row and edit line. Selftest: 1306 of 1334 planted mistakes of 22 kinds reported. The 28 it misses are values inside pending-row code lines and re-read lines that go through a helper; those lines were read by eye in every module.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live on the shared test database. Each kill is a plain `N failed`.
- **Variants ran on the default plan only**, not under forced plans; the order cards' plan sensitivity is the executor's notes'.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/project_component_task.py tests/unit/dao/test_project_component_task.py --timeout 300 --json <scratch>/res/mut_project_component_task.json   (through runmut.sh)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_project_component_task.py -q -p no:cacheprovider --cov=app.dao.project_component_task --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  33 passed, 5 xfailed; then 2 more default runs and one --runxfail run
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
> Tests: 34 passed, 7 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 41 unfaithful** (the new and changed tests read by eye; all 41 compared by script)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test or card edited in this round, no commit.

- **New cards:** PCT-GC-23, GI-17, GI-18. **Changed:** none. Each new or changed test was read against its card and matches it, its recipe included.
- **xfail:** PCT-GC-23, GI-17: non-strict, each fails today on Then 1, as its card says.

### Gap variants against the new cards
Each round 1 gap variant ran on my reference with `--runxfail` on three plans: default; `enable_seqscan=off`; index, bitmap and index-only scans off. "Fails" means the named card failed in all three runs. Every run reached all tests.

| Variant | Card that must fail | Plans where it failed |
|---|---|---|
| `gc_ord_case_sensitive` | PCT-GC-23 | default, seqoff, idxoff (3 of 3) |
| `gi_ord_case_sensitive` | PCT-GI-17 | default, seqoff, idxoff (3 of 3) |
| `gi_ws_le` | PCT-GI-18 | default, seqoff, idxoff (3 of 3) |

**Reference bases, `--runxfail`:** default: 41 of 41 passed, seqoff: 41 of 41 passed, idxoff: 41 of 41 passed.

### Reproduced
- `34 passed, 7 xfailed` in the coverage run. The ten files together gave `411 passed, 50 xfailed, 1 xpassed` in 2 of 2 runs, matching the coordinator's line. No flaky test.
- `ruff check` passes. `rebuild.py` over the ten files reports nothing beyond round 1's known alias noise. `git diff --stat -- app/dao` is empty.

### Commands run
```
rebuild.py <ten modules>; show.py <module> <new and changed ids>     read against the cards
round2.py                                                          gap variants and bases, 3 plans
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_project_component_task.py -q -p no:cacheprovider --cov=app.dao.project_component_task --cov-branch   (private COVERAGE_FILE)
.venv/Scripts/python.exe -m pytest <the ten test files> -q -p no:cacheprovider     x2
xfline.py; .venv/Scripts/python.exe -m ruff check <the seven test files>
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\`. Only this report was edited in the repo. Nothing was stopped or killed.
