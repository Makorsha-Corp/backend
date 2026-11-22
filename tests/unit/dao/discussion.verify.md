# Verification — `app/dao/discussion.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 42 passed · 6 xfail, 2 strict, 4 non-strict (reproduced ✅) · coverage 100% branch (16 statements, 0 branches)
> Mutation: 10 mutants · 10 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 48 unfaithful** (48 / 48 right)
> Hand variants: 37 · 28 caught by a pass card · 9 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** I read all 48 against their cards; all match, and the script agrees.
- **Why NEEDS WORK:** 4 rule gaps for the case designer, all small: a W2-asked list, a leading space in the argument, another entity with a lower id, and an untrimmed message on `create`.
- **DSC-GE-26:** its Expect line now names BUG-1439 and BUG-1490 (cosmetic edit, made at the coordinator's request; see Cosmetic). It fails today on Then 2, as its card now says.

Written by Claude (all 48 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 48. No `discussion.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_entity` R3 (another workspace) | GE-02 asks for W1 with the other root in W2, the later id. A `<=` on `workspace_id` leaks the earlier workspace's roots. | `ge_ws_le` passes all 48. Recipe R-1. | **case designer** |
| 2 | case-missing | `get_by_entity` R3 (exact compare) | GE-08 tests a leading space on the stored side only; skill step 1b asks for both sides. | `ge_txt_strip` passes all 48. Recipe R-2. | **case designer** |
| 3 | case-missing | `get_by_entity` R3 (another entity id) | GE-03's other entity is 502, above 501. A `<=` on `entity_id` leaks a lower one. | `gee_id_le` passes all 48. Recipe R-3. | **case designer** |
| 4 | case-missing | `create` R1 ("exactly the given values"), R2 ("nothing is validated") | No card gives a message with spaces around it, so a stripping `create` passes. CR-03's empty message is unchanged by a strip. | `cr_strip` passes all 48. Recipe R-4. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\prop\prop_discussion.py`, not in the repo, run by `propdrive.py` in a temporary copy of the backend. Each passes on today's code (the xfail ones xfail or xpass, as non-strict allows) and on my reference with `--runxfail`. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card DSC-GE-31, R3 | A = msg; Z = msg, but `workspace_id W2.id`; When `get_by_entity(db, workspace_id=W2.id, entity_type="project", entity_id=501)` | 1. `ids(items) == [Z.id]`. 2. `total == 1` | pass | `ge_ws_le` |
| R-2 | new card DSC-GE-32, R3 | A = msg; When `get_by_entity(db, workspace_id=W1.id, entity_type=" project", entity_id=501)` | `result == ([], 0)` | pass | `ge_txt_strip` |
| R-3 | new card DSC-GE-33, R3 | A = msg; X = msg, but `entity_id 500`; When as GE-03 | 1. `ids(items) == [A.id]`. 2. `total == 1` | pass | `gee_id_le` |
| R-4 | new card DSC-CR-11, R1, R2 | No `discussions` row; When `create(db, workspace_id=W1.id, entity_type="project", entity_id=501, user_id=U1.id, message="  Hi  ")` | re-read result: `message == "  Hi  "` | pass | `cr_strip` |

## Cosmetic
- **Edited at the coordinator's request:** in `discussion.cases.md`, DSC-GE-26's Expect line went from `xfail BUG-1439` to `xfail BUG-1439, BUG-1490`, to match its Fails line and its marker (whose reason already names both). No other card text changed.
- **Left for the case designer, cosmetic:** GE-26's Rules line still reads `` `get_by_entity` R6 [BUG-1439] ``, while spec R6 now names BUG-1439 and BUG-1490. The test docstring matches the card as it stands.
- **Left for the executor, cosmetic:** GE-26's marker reason ends with "(DISCREPANCY-1: fails on Then 2, not Then 3)". Now that the card says Then 2, that note is stale. The bug IDs in it are right.

## Surviving mutants
None. Every kill ends in a plain `N failed`.

**Guard.** My own driver (`drive.py muts`) re-ran every mutant of mutate.py's own list with no `-x`. Every run reached every pass test, with no collection or setup error, and each kill or survival matched mutate.py's.

## Hand variants
My reference fix and the variants are a pytest plugin, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\plug\attvref.py` (`-p attvref`). It replaces the DAO's methods in-process with the spec's intended behaviour, bug rules included; nothing is written to `app/`. Runs used `--runxfail` on the default plan. Every variant was asserted to be applied, and every run reached all 48 tests. Group = the method's tag.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| ge | 23 | 16 | DSC-GE-01, DSC-GE-02, DSC-GE-05, DSC-GE-06, DSC-GE-07, DSC-GE-08 … | `ge_ws_le`, `ge_txt_strip`, `ge_no_selectin`, `ge_replies_unordered`, `ge_replies_id_desc`, `ge_ord_id_desc`, `ge_ord_msg` |
| gee | 2 | 1 | DSC-GE-03, DSC-GE-23, DSC-GE-30 | `gee_id_le` |
| gi | 9 | 9 | DSC-GI-01, DSC-GI-02, DSC-GI-03, DSC-GI-04, DSC-GI-05, DSC-GI-06 … | — |
| cr | 3 | 2 | DSC-CR-01, DSC-CR-02, DSC-CR-03, DSC-CR-04, DSC-CR-05, DSC-CR-10 | `cr_strip` |
| **Total** | **37** | **28** |  | **9** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `ge_no_selectin`, `ge_replies_unordered`, `ge_replies_id_desc` | **Bug path** (BUG-1439, BUG-1490). The first two fail GE-24, GE-25 and GE-26; `ge_replies_id_desc` fails GE-24 and GE-25 (GE-26 only asks for an `ORDER BY`). |
| `ge_ord_id_desc`, `ge_ord_msg` | **Bug path** (BUG-1438). `ge_ord_id_desc` fails GE-19, GE-20 and GE-21. `ge_ord_msg` (`created_at, message, id`) fails GE-20 only: GE-19's tied messages rise with the ids, but GE-20's "Fourth" breaks that, so GE-20 pins it once the markers come off. |

## xfail tests against the reference
With `--runxfail` on the reference: 48 passed. **The alarm works:** with the markers on, every strict card is `XPASS(strict)`.

| Cards | Marker | Fails today on (`--runxfail`, my script mapping the failing line to its `# Then N`) |
|---|---|---|
| DSC-GE-19, GE-20 | non-strict | Then 2 |
| DSC-GE-21 | strict | Then 3 |
| DSC-GE-24, GE-25 | non-strict | Then 2 |
| DSC-GE-26 | strict | Then 2, as the card now says (no `parent_id IN` statement is sent: BUG-1490) |

Each fails on the line its card's "Fails today on" names.

## Reproduced claims
- **Result line of the notes holds:** `42 passed, 6 xfailed` in 3 of 3 default runs, the coverage run among them, and again in the mutation and variant bases. No flaky test.
- **Mocks:** only those the Conventions name (the commit spy). No `try`, no broad `pytest.raises`. `ruff check` passes.

## Traceability
cases 48 · tests 48 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules (several end with a period the card lacks; cosmetic). `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All tests sit under `# [claude] <ID>`.

My own script (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\tools\rebuild.py`) compares each test with its card by AST and by text: name, docstring, marker, the When call's arguments, each Given line in order, each Then line's expression, operators and literals. Over the 433 cards of this batch it leaves no unexplained report; each report it gave was read by eye. Eye-read here: the whole file, against every card. Selftest: 1306 of 1334 planted mistakes of 22 kinds reported. The 28 it misses are values inside pending-row code lines and re-read lines that go through a helper; those lines were read by eye in every module.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live on the shared test database. Each kill is a plain `N failed`.
- **Variants ran on the default plan only**, not under forced plans; the order cards' plan sensitivity is the executor's notes'.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/discussion.py tests/unit/dao/test_discussion.py --timeout 300 --json <scratch>/res/mut_discussion.json   (through runmut.sh)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_discussion.py -q -p no:cacheprovider --cov=app.dao.discussion --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  42 passed, 6 xfailed; then 2 more default runs and one --runxfail run
drive.py bases | muts | vars <module>; xfline.py; propdrive.py; rebuild.py; rebuild.py --selftest 8
.venv/Scripts/python.exe -m ruff check <the ten test files>     All checks passed!
git diff --stat -- app/dao                                   (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\`. Only this report was written in the repo. One cosmetic edit was made to `discussion.cases.md`, at the coordinator's request (see Cosmetic). No commit. Nothing was stopped or killed.

## Fix list
1. **Case designer:** add the recipes above; the Givens and Thens are written out.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 46 passed, 6 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 52 unfaithful** (the new and changed tests read by eye; all 52 compared by script)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test or card edited in this round, no commit.

- **New cards:** DSC-GE-31, GE-32, GE-33, CR-11. **Changed:** DSC-GE-26's marker: the stale "(DISCREPANCY-1 …)" note is gone; the reason still names BUG-1439 and BUG-1490. Each new or changed test was read against its card and matches it, its recipe included.
- The round 1 cosmetic items are closed, except GE-26's Rules line, which still names only BUG-1439 (cosmetic; not a finding). DSC-GE-24 passed once under `--runxfail` in this round; it is non-strict, so that is allowed.
- **xfail:** DSC-GE-26: strict, still fails on Then 2.

### Gap variants against the new cards
Each round 1 gap variant ran on my reference with `--runxfail` on three plans: default; `enable_seqscan=off`; index, bitmap and index-only scans off. "Fails" means the named card failed in all three runs. Every run reached all tests.

| Variant | Card that must fail | Plans where it failed |
|---|---|---|
| `ge_ws_le` | DSC-GE-31 | default, seqoff, idxoff (3 of 3) |
| `ge_txt_strip` | DSC-GE-32 | default, seqoff, idxoff (3 of 3) |
| `gee_id_le` | DSC-GE-33 | default, seqoff, idxoff (3 of 3) |
| `cr_strip` | DSC-CR-11 | default, seqoff, idxoff (3 of 3) |

**Reference bases, `--runxfail`:** default: 52 of 52 passed, seqoff: 52 of 52 passed, idxoff: 52 of 52 passed.

### Reproduced
- `46 passed, 6 xfailed` in the coverage run. The ten files together gave `411 passed, 50 xfailed, 1 xpassed` in 2 of 2 runs, matching the coordinator's line. No flaky test.
- `ruff check` passes. `rebuild.py` over the ten files reports nothing beyond round 1's known alias noise. `git diff --stat -- app/dao` is empty.

### Commands run
```
rebuild.py <ten modules>; show.py <module> <new and changed ids>     read against the cards
round2.py                                                          gap variants and bases, 3 plans
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_discussion.py -q -p no:cacheprovider --cov=app.dao.discussion --cov-branch   (private COVERAGE_FILE)
.venv/Scripts/python.exe -m pytest <the ten test files> -q -p no:cacheprovider     x2
xfline.py; .venv/Scripts/python.exe -m ruff check <the seven test files>
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\`. Only this report was edited in the repo. Nothing was stopped or killed.
