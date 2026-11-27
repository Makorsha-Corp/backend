# Verification — `app/core/notification_channels.py`

> **Verdict:** PASS
> Tests: 3 passed · 0 xfail (reproduced ✅) · coverage 100% branch (1 statement, 0 branches)
> Mutation: 1 mutant · 1 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 3 unfaithful** (3 / 3 right)
> Hand variants: 4 · 4 caught by a pass card
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted.** All three tests were read against their cards by eye; my script agrees on IDs, markers, Then blocks and When.
- NCH-03 really delivers a notify between two autocommit connections and closes both in a `finally`, as its card says; it writes nothing to any table.
- No finding for any stage.

Written by Claude (all 3 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 3. No local-run file.

## Findings
None.

## Surviving mutants
None. The one mutant (`"user_notifications"` → `""`) is killed with a plain `N failed`. **Guard:** my own driver re-ran it with no `-x`; the run reached all 3 tests.

## Hand variants
| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| nch_r1 | 4 | 4 | NCH-01, NCH-02, NCH-03 | — |

`"User_notifications"`, `"user-notifications"`, `"user_notification"`, `"user_notifications "`: each fails NCH-01 and NCH-03; the capital, the dash and the space also fail NCH-02.

## Reproduced claims
- **Result line of the notes holds:** `3 passed` in 4 of 4 runs, the coverage run among them; `select.select` returned within the 5-second wait every time. No flaky test.
- **Mocks:** none.

## Traceability
cases 3 · tests 3 · unmatched: none · marker mismatches: none. Card order equals file order; docstrings and `# Then N` match. `ruff check` passes. `rebuild.py`: 0 reports; NCH-03's Given (two connections, `LISTEN`, the `finally`) read by eye.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/core/notification_channels.py tests/unit/core/test_notification_channels.py --timeout 300 --json <scratch>/res/mut_notification_channels.json
  1 mutant · 1 killed
.venv/Scripts/python.exe -m pytest tests/unit/core/test_notification_channels.py -q -p no:cacheprovider --cov=app.core.notification_channels --cov-branch --cov-report=term-missing
  3 passed · TOTAL 1 0 0 0 100%
pytest (same file), 3 more runs                               3 passed each
drive.py bases / muts / vars notification_channels; rebuild.py
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctv\`. Private `COVERAGE_FILE`. Only this report was written in the repo. No commit. Nothing was killed.
