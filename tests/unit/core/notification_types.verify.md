# Verification — `app/core/notification_types.py`

> **Verdict:** PASS
> Tests: 5 passed · 0 xfail (reproduced ✅) · coverage 100% branch (10 statements, 0 branches)
> Mutation: 10 mutants · 10 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 5 unfaithful** (5 / 5 right)
> Hand variants: 7 · 7 caught by a pass card
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted.** All five tests were read against their cards by eye, and my script agrees: each constant is compared exactly, and the web-app list, pairwise difference, length and character rules each have their own check.
- No finding for any stage.

Written by Claude (all 5 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 5. No local-run file.

## Findings
None.

## Surviving mutants
None. All 10 mutants (each value → `""`) are killed with a plain `N failed`. **Guard:** my own driver re-ran each with no `-x`; every run reached all 5 tests, and each status matched `mutate.py`.

## Hand variants
| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| nty_r1 | 2 | 2 | NTY-K-01, NTY-K-02 | — |
| nty_r2 | 1 | 1 | NTY-K-01, NTY-K-02 | — |
| nty_r3 | 1 | 1 | NTY-K-01, NTY-K-02, NTY-K-03 | — |
| nty_r4 | 2 | 2 | NTY-S-01 | — |
| nty_r5 | 1 | 1 | NTY-S-01, NTY-S-02 | — |
| **Total** | **7** | **7** |  | **0** |

Swapped kinds, a plural, a duplicate kind, a capital, swapped and duplicate sources, a trailing `_`.

## Reproduced claims
- **Result line of the notes holds:** `5 passed` in 4 of 4 runs, the coverage run among them. No flaky test.
- **Mocks:** none.

## Traceability
cases 5 · tests 5 · unmatched: none · marker mismatches: none. Card order equals file order; docstrings and `# Then N` match. `ruff check` passes. `rebuild.py`: 0 reports.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/core/notification_types.py tests/unit/core/test_notification_types.py --timeout 300 --json <scratch>/res/mut_notification_types.json
  10 mutants · 10 killed
.venv/Scripts/python.exe -m pytest tests/unit/core/test_notification_types.py -q -p no:cacheprovider --cov=app.core.notification_types --cov-branch --cov-report=term-missing
  5 passed · TOTAL 10 0 0 0 100%
pytest (same file), 3 more runs                               5 passed each
drive.py bases / muts / vars notification_types; rebuild.py
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctv\`. Private `COVERAGE_FILE`. Only this report was written in the repo. No commit. Nothing was killed.
