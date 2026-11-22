# Verification — `app/dao/attachment.py`

> **Verdict:** PASS
> Tests: 24 passed · 1 xfail, strict (reproduced ✅) · coverage 68% branch (30 statements, 4 branches; every miss is the dead `restore`, lines 91–107)
> Mutation: 17 mutants · 11 killed · 6 survived → score 100% (after excluding 0 equivalent, 6 dead, 0 bug-path)
> Fidelity: **0 of 25 unfaithful** (25 / 25 right)
> Hand variants: 23 · 22 caught by a pass card · 1 others: all under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 25 match their cards; the script and my reading agree.
- **No rule gap.** 22 of 23 hand variants fail a pass card; the one other is the BUG-1430 path, caught by ATT-SD-02 as designed.
- The 6 surviving mutants are all in `restore`, which the spec lists as dead code (P3).

Written by Claude (all 25 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 25. No `attachment.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
None.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | L91–107 | 6 mutants in `restore` (if, not, const, return, two `==`) | dead | `AttachmentDAO.restore` is under Not specified: dead code to be removed (P3) | — |

**Guard.** My own driver (`drive.py muts`) re-ran every mutant of mutate.py's own list with no `-x`. Every run reached every pass test, with no collection or setup error, and each kill or survival matched mutate.py's.

## Hand variants
My reference fix and the variants are a pytest plugin, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\plug\attvref.py` (`-p attvref`). It replaces the DAO's methods in-process with the spec's intended behaviour, bug rules included; nothing is written to `app/`. Runs used `--runxfail` on the default plan. Every variant was asserted to be applied, and every run reached all 25 tests. Group = the method's tag.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| ga | 10 | 10 | ATT-GA-01, ATT-GA-02, ATT-GA-03, ATT-GA-04, ATT-GA-05, ATT-GA-06 … | — |
| sd | 13 | 12 | ATT-SD-01, ATT-SD-03, ATT-SD-04, ATT-SD-05, ATT-SD-06, ATT-SD-07 … | `sd_naive` |
| **Total** | **23** | **22** |  | **1** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `sd_naive` | **Bug path.** Today's naive stamp; ATT-SD-02 fails on Then 3, as its card says. |

## xfail tests against the reference
With `--runxfail` on the reference: 25 passed. **The alarm works:** with the markers on, every strict card is `XPASS(strict)`.

| Cards | Marker | Fails today on (`--runxfail`, my script mapping the failing line to its `# Then N`) |
|---|---|---|
| ATT-SD-02 | strict | Then 3, as the card says |

Each fails on the line its card's "Fails today on" names.

## Reproduced claims
- **Result line of the notes holds:** `24 passed, 1 xfailed` in 3 of 3 default runs, the coverage run among them, and again in the mutation and variant bases. No flaky test.
- **Mocks:** only those the Conventions name (the commit spy, the clock). No `try`, no broad `pytest.raises`. `ruff check` passes.

## Traceability
cases 25 · tests 25 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules (several end with a period the card lacks; cosmetic). `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All tests sit under `# [claude] <ID>`.

My own script (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\tools\rebuild.py`) compares each test with its card by AST and by text: name, docstring, marker, the When call's arguments, each Given line in order, each Then line's expression, operators and literals. Over the 433 cards of this batch it leaves no unexplained report; each report it gave was read by eye. Eye-read here: the differences the script reported (ATT-SD-06, SD-09, SD-12) and every pending-row and edit line. Selftest: 1306 of 1334 planted mistakes of 22 kinds reported. The 28 it misses are values inside pending-row code lines and re-read lines that go through a helper; those lines were read by eye in every module.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live on the shared test database. Each kill is a plain `N failed`.
- **Variants ran on the default plan only**, not under forced plans; the order cards' plan sensitivity is the executor's notes'.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/attachment.py tests/unit/dao/test_attachment.py --timeout 300 --json <scratch>/res/mut_attachment.json   (through runmut.sh)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_attachment.py -q -p no:cacheprovider --cov=app.dao.attachment --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  24 passed, 1 xfailed; then 2 more default runs and one --runxfail run
drive.py bases | muts | vars <module>; xfline.py; propdrive.py; rebuild.py; rebuild.py --selftest 8
.venv/Scripts/python.exe -m ruff check <the ten test files>     All checks passed!
git diff --stat -- app/dao                                   (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\`. Only this report was written in the repo. No commit. Nothing was stopped or killed.

## Fix list
Nothing.
