# Verification — `app/dao/attachment_markup_event.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 21 passed · 3 xfail, 2 strict, 1 non-strict (reproduced ✅) · coverage 100% branch (12 statements, 0 branches)
> Mutation: 5 mutants · 4 killed · 1 survived → score 100% (after excluding 0 equivalent, 0 dead, 1 bug-path)
> Fidelity: **0 of 24 unfaithful** (24 / 24 right)
> Hand variants: 18 · 14 caught by a pass card · 4 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 24 match their cards.
- **Why NEEDS WORK:** one rule gap for the case designer. No card asks for workspace W2 while a W1 entry exists.
- **Weak card AME-LA-09:** not a gap. See Rulings.

Written by Claude (all 24 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 24. No `attachment_markup_event.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `list_for_attachment` R2 (another workspace) | LA-03 asks for W1 with the other entry in W2, the later id. A `<=` on `workspace_id` leaks the earlier workspace's entries. | `la_ws_le` passes all 24. Recipe R-1. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\prop\prop_attachment_markup_event.py`, not in the repo, run by `propdrive.py` in a temporary copy of the backend. Each passes on today's code (the xfail ones xfail or xpass, as non-strict allows) and on my reference with `--runxfail`. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card AME-LA-14, R2 | A = entry, `created_at T11`; Z = entry, `created_at T11`, but `workspace_id W2.id`; When `list_for_attachment(db, workspace_id=W2.id, attachment_id=AT1.id)` | `ids(result) == [Z.id]` | pass | `la_ws_le` |

## Rulings asked for
- **AME-LA-09: no change needed.** Its Then 5 counts `DESC` words, so `created_at DESC, user_id DESC, id` passes it (my `la_ord_desc_user`). LA-08 fails that order on Then 2. The fix's `XPASS(strict)` of LA-09 turns the run red, and the notes have LA-08's marker removed with LA-09's. LA-08 then fails that order as a pass card. Same as ALK-GA-30.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | L18 | `200 -> 201` (the `limit` default) | bug-path | The 200 cap is BUG-1437, and only AME-LA-10 (xfail) targets it; the spec lists `limit` for removal with the fix | — |

**Guard.** My own driver (`drive.py muts`) re-ran every mutant of mutate.py's own list with no `-x`. Every run reached every pass test, with no collection or setup error, and each kill or survival matched mutate.py's.

## Hand variants
My reference fix and the variants are a pytest plugin, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\plug\attvref.py` (`-p attvref`). It replaces the DAO's methods in-process with the spec's intended behaviour, bug rules included; nothing is written to `app/`. Runs used `--runxfail` on the default plan. Every variant was asserted to be applied, and every run reached all 24 tests. Group = the method's tag.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| la | 13 | 9 | AME-LA-01, AME-LA-02, AME-LA-03, AME-LA-04, AME-LA-05, AME-LA-06 … | `la_ws_le`, `la_ord_desc_user`, `la_ord_id_asc`, `la_cap200` |
| ce | 5 | 5 | AME-CE-01, AME-CE-02, AME-CE-03, AME-CE-04, AME-CE-06, AME-CE-11 | — |
| **Total** | **18** | **14** |  | **4** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `la_ord_desc_user`, `la_ord_id_asc` | **Bug path.** `la_ord_id_asc` fails LA-08 and LA-09; `la_ord_desc_user` fails LA-08 only (see Rulings). An extra variant with a text key before the tail, `created_at DESC, description, id DESC` (not in the table), fails LA-09. |
| `la_cap200` | **Bug path.** Today's cap; LA-10 Then 2. |

## xfail tests against the reference
With `--runxfail` on the reference: 24 passed. **The alarm works:** with the markers on, every strict card is `XPASS(strict)`.

| Cards | Marker | Fails today on (`--runxfail`, my script mapping the failing line to its `# Then N`) |
|---|---|---|
| AME-LA-08 | non-strict | Then 2 |
| AME-LA-09 | strict | Then 3 |
| AME-LA-10 | strict | Then 2 |

Each fails on the line its card's "Fails today on" names.

## Reproduced claims
- **Result line of the notes holds:** `21 passed, 3 xfailed` in 3 of 3 default runs, the coverage run among them, and again in the mutation and variant bases. No flaky test.
- **Mocks:** only those the Conventions name (the commit spy). No `try`, no broad `pytest.raises`. `ruff check` passes.

## Traceability
cases 24 · tests 24 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules (several end with a period the card lacks; cosmetic). `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All tests sit under `# [claude] <ID>`.

My own script (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\tools\rebuild.py`) compares each test with its card by AST and by text: name, docstring, marker, the When call's arguments, each Given line in order, each Then line's expression, operators and literals. Over the 433 cards of this batch it leaves no unexplained report; each report it gave was read by eye. Eye-read here: the differences the script reported (AME-LA-08, CE-02, CE-03, CE-11) and every pending-row and edit line. Selftest: 1306 of 1334 planted mistakes of 22 kinds reported. The 28 it misses are values inside pending-row code lines and re-read lines that go through a helper; those lines were read by eye in every module.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live on the shared test database. Each kill is a plain `N failed`.
- **Variants ran on the default plan only**, not under forced plans; the order cards' plan sensitivity is the executor's notes'.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/attachment_markup_event.py tests/unit/dao/test_attachment_markup_event.py --timeout 300 --json <scratch>/res/mut_attachment_markup_event.json   (through runmut.sh)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_attachment_markup_event.py -q -p no:cacheprovider --cov=app.dao.attachment_markup_event --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  21 passed, 3 xfailed; then 2 more default runs and one --runxfail run
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
> Tests: 22 passed, 3 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 25 unfaithful** (the new and changed tests read by eye; all 25 compared by script)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test or card edited in this round, no commit.

- **New cards:** AME-LA-14. **Changed:** none. Each new or changed test was read against its card and matches it, its recipe included.

### Gap variants against the new cards
Each round 1 gap variant ran on my reference with `--runxfail` on three plans: default; `enable_seqscan=off`; index, bitmap and index-only scans off. "Fails" means the named card failed in all three runs. Every run reached all tests.

| Variant | Card that must fail | Plans where it failed |
|---|---|---|
| `la_ws_le` | AME-LA-14 | default, seqoff, idxoff (3 of 3) |

**Reference bases, `--runxfail`:** default: 25 of 25 passed, seqoff: 25 of 25 passed, idxoff: 25 of 25 passed.

### Reproduced
- `22 passed, 3 xfailed` in the coverage run. The ten files together gave `411 passed, 50 xfailed, 1 xpassed` in 2 of 2 runs, matching the coordinator's line. No flaky test.
- `ruff check` passes. `rebuild.py` over the ten files reports nothing beyond round 1's known alias noise. `git diff --stat -- app/dao` is empty.

### Commands run
```
rebuild.py <ten modules>; show.py <module> <new and changed ids>     read against the cards
round2.py                                                          gap variants and bases, 3 plans
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_attachment_markup_event.py -q -p no:cacheprovider --cov=app.dao.attachment_markup_event --cov-branch   (private COVERAGE_FILE)
.venv/Scripts/python.exe -m pytest <the ten test files> -q -p no:cacheprovider     x2
xfline.py; .venv/Scripts/python.exe -m ruff check <the seven test files>
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\`. Only this report was edited in the repo. Nothing was stopped or killed.
