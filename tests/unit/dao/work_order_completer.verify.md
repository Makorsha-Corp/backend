# Verification — `app/dao/work_order_completer.py`

> **Verdict:** PASS
> Tests: 25 passed · 0 xfail (reproduced ✅) · coverage 94% branch (25 statements; lines 36–45 are the dead `get_user_ids_by_order`; 8 of 8 branches)
> Mutation: 13 mutants · 10 killed · 3 survived → score 100% (after excluding 0 equivalent, 3 dead, 0 bug-path)
> Fidelity: **0 of 25 unfaithful** (25 / 25 right)
> Hand variants: 20 · 19 caught by a pass card · 1 others: all under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 25 match their cards.
- **No rule gap.** 19 of 20 hand variants fail a pass card; the other is `rp_sync`, which no rule can see (as in `work_order_assignee`). The three survivors are in dead code.

Written by Claude (all 25 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 25. No `work_order_completer.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
None.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | L36–45 | `return None`, two `== -> !=` in `get_user_ids_by_order` | dead | Not specified: dead code to be removed (P3) | — |

**Guard.** My own driver (`drive.py muts`) re-ran every mutant of mutate.py's own list with no `-x`. Every run reached every pass test, with no collection or setup error, and each kill or survival matched mutate.py's.

## Hand variants
My reference fix and the variants are a pytest plugin, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\plug\attvref.py` (`-p attvref`). It replaces the DAO's methods in-process with the spec's intended behaviour, bug rules included; nothing is written to `app/`. Runs used `--runxfail` on the default plan. Every variant was asserted to be applied, and every run reached all 25 tests. Group = the method's tag.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| go | 12 | 12 | WOC-GO-01, WOC-GO-02, WOC-GO-03, WOC-GO-04, WOC-GO-05, WOC-GO-06 … | — |
| rp | 8 | 7 | WOC-RP-01, WOC-RP-02, WOC-RP-03, WOC-RP-05, WOC-RP-06, WOC-RP-07 … | `rp_sync` |
| **Total** | **20** | **19** |  | **1** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `rp_sync` | As in `work_order_assignee.verify.md`: R7's observable holds under `"fetch"`; no rule names the identity-map state. |

## Reproduced claims
- **Result line of the notes holds:** `25 passed` in 3 of 3 default runs, the coverage run among them, and again in the mutation and variant bases. No flaky test.
- **Mocks:** only those the Conventions name (the commit spy). No `try`, no broad `pytest.raises`. `ruff check` passes.

## Traceability
cases 25 · tests 25 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules (several end with a period the card lacks; cosmetic). `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All tests sit under `# [claude] <ID>`.

My own script (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\tools\rebuild.py`) compares each test with its card by AST and by text: name, docstring, marker, the When call's arguments, each Given line in order, each Then line's expression, operators and literals. Over the 433 cards of this batch it leaves no unexplained report; each report it gave was read by eye. Eye-read here: the differences the script reported (WOC-GO-05, RP-01, RP-02) and every pending-row and edit line. Selftest: 1306 of 1334 planted mistakes of 22 kinds reported. The 28 it misses are values inside pending-row code lines and re-read lines that go through a helper; those lines were read by eye in every module.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live on the shared test database. Each kill is a plain `N failed`.
- **Variants ran on the default plan only**, not under forced plans; the order cards' plan sensitivity is the executor's notes'.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/work_order_completer.py tests/unit/dao/test_work_order_completer.py --timeout 300 --json <scratch>/res/mut_work_order_completer.json   (through runmut.sh)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order_completer.py -q -p no:cacheprovider --cov=app.dao.work_order_completer --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  25 passed; then 2 more default runs and one --runxfail run
drive.py bases | muts | vars <module>; xfline.py; propdrive.py; rebuild.py; rebuild.py --selftest 8
.venv/Scripts/python.exe -m ruff check <the ten test files>     All checks passed!
git diff --stat -- app/dao                                   (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\`. Only this report was written in the repo. No commit. Nothing was stopped or killed.

## Fix list
Nothing.
