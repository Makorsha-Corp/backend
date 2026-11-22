# Verification — `app/dao/project.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 34 passed · 11 xfail, 7 strict, 4 non-strict (reproduced ✅) · coverage 100% branch (11 statements, 0 branches)
> Mutation: 10 mutants · 10 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 45 unfaithful** (45 / 45 right)
> Hand variants: 39 · 25 caught by a pass card · 14 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 45 match their cards.
- **Why NEEDS WORK:** 2 rule gaps for the case designer. No card can see the *case-insensitive* part of R4 on this database. `get_by_status` has no filter-before-page card for a deleted project.
- **Ruling on the collation note:** a real gap, and data can close it without a check on the SQL text. See Rulings.

Written by Claude (all 45 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 45. No `project.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_factory` R4, `get_by_status` R4 [BUG-1444] ("`name` case-insensitive") | The test database sorts `roof` before `Roof` for a plain `ORDER BY name`. GF-15 builds `roof` first, so a case-sensitive `name, id` gives the same list. GF-14 and GS-10 use `Zulu`, `apple`, `Banana`, which this collation sorts case-insensitively anyway. | `gf_ord_case_sensitive`, `gs_ord_case_sensitive` pass all 45, with `--runxfail` too. Recipe R-1. | **case designer** |
| 2 | case-missing | `get_by_status` R2 [BUG-1445] ("takes no place in the page", as `get_by_factory` R2) | GF-08 checks it for the factory list. `get_by_status` is its own query, and no GS card puts a deleted project ahead of the skipped row. | `gs_deleted_after_page` passes all 45, with `--runxfail` too. Recipe R-2. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\prop\prop_project.py`, not in the repo, run by `propdrive.py` in a temporary copy of the backend. Each passes on today's code (the xfail ones xfail or xpass, as non-strict allows) and on my reference with `--runxfail`. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | two new cards PRJ-GF-27, PRJ-GS-20, R4 [BUG-1444] | B = project, `name "Roof"`; A = project, `name "roof"`; C = project, `name "Banana"`; D = project, `name "apple"` (in that order, so `Roof` has the lower id); When `get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)` / `get_by_status(db, status=ProjectStatusEnum.PLANNING, workspace_id=W1.id)` | `ids(result) == [D.id, C.id, B.id, A.id]` | xfail BUG-1444 (non-strict); Fails today on: Then 1 (no order is requested) | `*_ord_case_sensitive`: `roof` before `Roof` on this collation; on a `C` collation `Banana` before `apple` |
| R-2 | new card PRJ-GS-21, R2 [BUG-1445] | X = project, `name "Aaa"`, deleted; A = project, `name "Bbb"`; B = project, `name "Ccc"`; When `get_by_status(db, status=ProjectStatusEnum.PLANNING, workspace_id=W1.id, skip=1, limit=1)` | `ids(result) == [B.id]` | xfail BUG-1445, BUG-1444 (non-strict); Fails today on: Then 1 (the deleted project fills the first place) | `gs_deleted_after_page` |

## Rulings asked for
- **Case-insensitive order (executor's note): a real gap, routed above.** I checked it on the test database (collation `English_United States.1252`). A case-sensitive `ORDER BY name, id` sorts `apple, Banana, roof, Roof`. The intended `lower(name), id` gives `apple, Banana, Roof, roof` when `Roof` has the lower id. Recipe R-1 therefore tells them apart by data. Its `Banana`/`apple` pair also covers a `C`-collation database. A check for `lower(` in the SQL is not needed, and would tie the card to one way of writing the fix.

## Surviving mutants
None. Every kill ends in a plain `N failed`.

**Guard.** My own driver (`drive.py muts`) re-ran every mutant of mutate.py's own list with no `-x`. Every run reached every pass test, with no collection or setup error, and each kill or survival matched mutate.py's.

## Hand variants
My reference fix and the variants are a pytest plugin, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\plug\attvref.py` (`-p attvref`). It replaces the DAO's methods in-process with the spec's intended behaviour, bug rules included; nothing is written to `app/`. Runs used `--runxfail` on the default plan. Every variant was asserted to be applied, and every run reached all 45 tests. Group = the method's tag.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| gf | 20 | 13 | PRJ-GF-02, PRJ-GF-03, PRJ-GF-04, PRJ-GF-05, PRJ-GF-06, PRJ-GF-09 … | `gf_deleted_drop`, `gf_deleted_after_page`, `gf_factory_drop`, `gf_ord_case_sensitive`, `gf_ord_id_desc`, `gf_ord_desc`, `gf_ord_idonly` |
| gs | 19 | 12 | PRJ-GS-01, PRJ-GS-02, PRJ-GS-03, PRJ-GS-06, PRJ-GS-08, PRJ-GS-12 … | `gs_deleted_drop`, `gs_deleted_after_page`, `gs_factory_drop`, `gs_ord_case_sensitive`, `gs_ord_id_desc`, `gs_ord_desc`, `gs_ord_idonly` |
| **Total** | **39** | **25** |  | **14** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `gf_deleted_drop`, `gf_deleted_after_page`, `gf_factory_drop`, `gs_deleted_drop`, `gs_factory_drop` | **Bug path** (BUG-1445, BUG-1446). GF-07, GF-08, GF-10, GS-05 and GS-07 fail, as designed. |
| `gf_ord_id_desc`, `gf_ord_desc`, `gf_ord_idonly`, `gs_ord_*` (3) | **Bug path** (BUG-1444). Each fails at least GF-17 or GS-11 (strict), most also GF-14 to GF-16 or GS-10. Extra variants with a text key before the tail, `lower(name), description, id` (not in the table), fail GF-17 and GS-11. |

## xfail tests against the reference
With `--runxfail` on the reference: 45 passed. **The alarm works:** with the markers on, every strict card is `XPASS(strict)`.

| Cards | Marker | Fails today on (`--runxfail`, my script mapping the failing line to its `# Then N`) |
|---|---|---|
| PRJ-GF-07, GS-05, GS-07 | strict | Then 2 |
| PRJ-GF-08, GF-10 | strict | Then 1 |
| PRJ-GF-14, GF-15, GF-16, GS-10 | non-strict | Then 2 |
| PRJ-GF-17, GS-11 | strict | Then 2 |

Each fails on the line its card's "Fails today on" names.

## Reproduced claims
- **Result line of the notes holds:** `34 passed, 11 xfailed` in 3 of 3 default runs, the coverage run among them, and again in the mutation and variant bases. No flaky test.
- **Mocks:** only those the Conventions name (the commit spy). No `try`, no broad `pytest.raises`. `ruff check` passes.

## Traceability
cases 45 · tests 45 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules (several end with a period the card lacks; cosmetic). `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All tests sit under `# [claude] <ID>`.

My own script (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\tools\rebuild.py`) compares each test with its card by AST and by text: name, docstring, marker, the When call's arguments, each Given line in order, each Then line's expression, operators and literals. Over the 433 cards of this batch it leaves no unexplained report; each report it gave was read by eye. Eye-read here: the difference the script reported (PRJ-GF-15) and every pending-row and edit line. Selftest: 1306 of 1334 planted mistakes of 22 kinds reported. The 28 it misses are values inside pending-row code lines and re-read lines that go through a helper; those lines were read by eye in every module.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live on the shared test database. Each kill is a plain `N failed`.
- **Variants ran on the default plan only**, not under forced plans; the order cards' plan sensitivity is the executor's notes'.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/project.py tests/unit/dao/test_project.py --timeout 300 --json <scratch>/res/mut_project.json   (through runmut.sh)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_project.py -q -p no:cacheprovider --cov=app.dao.project --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  34 passed, 11 xfailed; then 2 more default runs and one --runxfail run
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
> Tests: 34 passed, 14 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 48 unfaithful** (the new and changed tests read by eye; all 48 compared by script)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test or card edited in this round, no commit.

- **New cards:** PRJ-GF-27, GS-20, GS-21. **Changed:** none. Each new or changed test was read against its card and matches it, its recipe included.
- **xfail:** PRJ-GF-27, GS-20, GS-21: non-strict, each fails today on Then 1, as its card says.

### Gap variants against the new cards
Each round 1 gap variant ran on my reference with `--runxfail` on three plans: default; `enable_seqscan=off`; index, bitmap and index-only scans off. "Fails" means the named card failed in all three runs. Every run reached all tests.

| Variant | Card that must fail | Plans where it failed |
|---|---|---|
| `gf_ord_case_sensitive` | PRJ-GF-27 | default, seqoff, idxoff (3 of 3) |
| `gs_ord_case_sensitive` | PRJ-GS-20 | default, seqoff, idxoff (3 of 3) |
| `gs_deleted_after_page` | PRJ-GS-21 | default, seqoff, idxoff (3 of 3) |

**Reference bases, `--runxfail`:** default: 48 of 48 passed, seqoff: 48 of 48 passed, idxoff: 48 of 48 passed.

### Reproduced
- `34 passed, 14 xfailed` in the coverage run. The ten files together gave `411 passed, 50 xfailed, 1 xpassed` in 2 of 2 runs, matching the coordinator's line. No flaky test.
- `ruff check` passes. `rebuild.py` over the ten files reports nothing beyond round 1's known alias noise. `git diff --stat -- app/dao` is empty.

### Commands run
```
rebuild.py <ten modules>; show.py <module> <new and changed ids>     read against the cards
round2.py                                                          gap variants and bases, 3 plans
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_project.py -q -p no:cacheprovider --cov=app.dao.project --cov-branch   (private COVERAGE_FILE)
.venv/Scripts/python.exe -m pytest <the ten test files> -q -p no:cacheprovider     x2
xfline.py; .venv/Scripts/python.exe -m ruff check <the seven test files>
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\`. Only this report was edited in the repo. Nothing was stopped or killed.
