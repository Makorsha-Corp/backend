# Verification — `app/dao/attachment_markup.py`

> **Verdict:** PASS
> Tests: 39 passed · 2 xfail, 1 strict, 1 non-strict (reproduced ✅) · coverage 100% branch (24 statements, 4 branches)
> Mutation: 16 mutants · 16 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 41 unfaithful** (41 / 41 right)
> Hand variants: 37 · 35 caught by a pass card · 2 others: all under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 41 match their cards.
- **No rule gap.** 35 of 37 hand variants fail a pass card; the two others are wrong tie orders on the BUG-1435 path, caught by GF-10 and GF-11.

Written by Claude (all 41 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 41. No `attachment_markup.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
None.

## Surviving mutants
None. Every kill ends in a plain `N failed`.

**Guard.** My own driver (`drive.py muts`) re-ran every mutant of mutate.py's own list with no `-x`. Every run reached every pass test, with no collection or setup error, and each kill or survival matched mutate.py's.

## Hand variants
My reference fix and the variants are a pytest plugin, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\plug\attvref.py` (`-p attvref`). It replaces the DAO's methods in-process with the spec's intended behaviour, bug rules included; nothing is written to `app/`. Runs used `--runxfail` on the default plan. Every variant was asserted to be applied, and every run reached all 41 tests. Group = the method's tag.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| gf | 12 | 10 | AMK-GF-02, AMK-GF-03, AMK-GF-04, AMK-GF-05, AMK-GF-06, AMK-GF-07 … | `gf_ord_id_desc`, `gf_ord_user` |
| gu | 9 | 9 | AMK-DL-02, AMK-DL-03, AMK-GU-01, AMK-GU-02, AMK-GU-03, AMK-GU-04 … | — |
| gua | 2 | 2 | AMK-GU-03, AMK-GU-04, AMK-UP-14 | — |
| guu | 2 | 2 | AMK-DL-02, AMK-GU-01, AMK-GU-02, AMK-UP-14 | — |
| up | 7 | 7 | AMK-UP-01, AMK-UP-02, AMK-UP-03, AMK-UP-04, AMK-UP-05, AMK-UP-06 … | — |
| dl | 5 | 5 | AMK-DL-01, AMK-DL-02, AMK-DL-03, AMK-DL-04, AMK-DL-05, AMK-DL-06 | — |
| **Total** | **37** | **35** |  | **2** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `gf_ord_id_desc`, `gf_ord_user` | **Bug path.** GF-10 Then 2 and GF-11 Then 3 fail, as designed. |

## xfail tests against the reference
With `--runxfail` on the reference: 41 passed. **The alarm works:** with the markers on, every strict card is `XPASS(strict)`.

| Cards | Marker | Fails today on (`--runxfail`, my script mapping the failing line to its `# Then N`) |
|---|---|---|
| AMK-GF-10 | non-strict | Then 2 |
| AMK-GF-11 | strict | Then 3 |

Each fails on the line its card's "Fails today on" names.

## Reproduced claims
- **Result line of the notes holds:** `39 passed, 2 xfailed` in 3 of 3 default runs, the coverage run among them, and again in the mutation and variant bases. No flaky test.
- **Mocks:** only those the Conventions name (the commit spy). No `try`, no broad `pytest.raises`. `ruff check` passes.

## Traceability
cases 41 · tests 41 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules (several end with a period the card lacks; cosmetic). `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All tests sit under `# [claude] <ID>`.

My own script (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\tools\rebuild.py`) compares each test with its card by AST and by text: name, docstring, marker, the When call's arguments, each Given line in order, each Then line's expression, operators and literals. Over the 433 cards of this batch it leaves no unexplained report; each report it gave was read by eye. Eye-read here: the differences the script reported (AMK-UP-01, UP-03, UP-04, DL-01) and every pending-row and edit line. Selftest: 1306 of 1334 planted mistakes of 22 kinds reported. The 28 it misses are values inside pending-row code lines and re-read lines that go through a helper; those lines were read by eye in every module.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live on the shared test database. Each kill is a plain `N failed`.
- **Variants ran on the default plan only**, not under forced plans; the order cards' plan sensitivity is the executor's notes'.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/attachment_markup.py tests/unit/dao/test_attachment_markup.py --timeout 300 --json <scratch>/res/mut_attachment_markup.json   (through runmut.sh)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_attachment_markup.py -q -p no:cacheprovider --cov=app.dao.attachment_markup --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  39 passed, 2 xfailed; then 2 more default runs and one --runxfail run
drive.py bases | muts | vars <module>; xfline.py; propdrive.py; rebuild.py; rebuild.py --selftest 8
.venv/Scripts/python.exe -m ruff check <the ten test files>     All checks passed!
git diff --stat -- app/dao                                   (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\`. Only this report was written in the repo. No commit. Nothing was stopped or killed.

## Fix list
Nothing.
