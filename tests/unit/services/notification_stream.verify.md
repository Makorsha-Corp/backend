# Verification — `app/services/notification_stream.py`

> **Verdict:** PASS
> Tests: 26 passed · 9 xfailed, all strict (reproduced ✅) · coverage 100% branch (33 statements, 6 branches)
> Mutation: 19 mutants · 19 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 35 unfaithful** (35 / 35 right; read by eye against cases revision 3)
> Hand variants: 46 · 44 caught by a pass card · 2 others: 2 bug-path (none is a rule gap)
> Source commit: e48a092 · Cases revision: 3; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 35 match their cards. DISCREPANCY-1 is closed: cases revision 3 now reads `conn.mock_calls` in **closes** and NST-G-03 Then 6, which is what the tests read (`Fakes.closes()`, `Fakes.call_names()`). Every expected value is the card's.
- **No test can hang.** Every `select` script is a finite list ending on STOP (an exhausted `side_effect` list raises, too). The four tests that leave a generator suspended (G-03, G-34, G-35, and G-01 which never starts it) close it in the test. No mutant or variant timed out. The longest whole-file run took 3 s.
- **Ping timing and connection close paths are guarded.** The 30-s `select` timeout, no ping, two pings, a ping that falls through to `poll`, a ping on every round and a ping after a ready round all fail a pass card (G-09, G-10, G-35 and others). Dropping, swapping or doubling a close, closing only on error, only on `close()`, or before the connected frame all fail G-26 … G-30.
- Every mutant is killed. The only variants no pass card sees are the BUG-1802 and BUG-1803 fixes, and they flip exactly their own strict xfail cards.

Written by Claude (all 35 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 35. No `notification_stream.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
None.

**Bookkeeping — done (checked 2026-11-04, round 2 of the batch):** the notes header and the test docstring now say cases revision 3, and DISCREPANCY-1 is marked closed in the notes and in the comment above `Fakes.closes()`. Re-run: `26 passed, 9 xfailed`. Nothing else changed, so the verdict stays PASS.

*Original note:* the notes header and the test module docstring still say "cases revision 2", and the comment above `Fakes.closes()` still describes DISCREPANCY-1 as open. Cases revision 3 closed it with no change to any expected value, so the tests need no change. Only the wording is out of date.

## Surviving mutants
None. All 19 kills end in a plain `1 failed` (from `killed_by` in `mut_ns.json`). None came from a collection or setup error, and there were 0 timeouts. The `while True` → `while False` mutant ends the stream at once and is killed by G-09. It is not a hang.

## Hand variants
`plug\vplug.py` execs a variant of the module into `app.services.notification_stream` before collection. `drive.py` applies each edit (checked to apply exactly once), then runs the whole file (normal mode, xfail markers on) with a 60-s hang guard. `var_ns.py` holds the edits. The control variant (a docstring edit) gives `26 passed, 9 xfailed`.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| ping timing (`select` timeout 29 / 60 / none; never; twice; falls through to `poll`; every round; after a ready round; wrong text) | 9 | 9 | G-09, G-10, G-35; every-round and after-ready variants also fail G-12 … G-24 | — |
| close paths (drop cursor / connection close, swapped, connection twice, only on error, only on `GeneratorExit`, swallow error, cursor closed before the connected frame) | 8 | 8 | G-26 … G-30; swallow also fails G-09 … G-24 | — |
| setup (no autocommit, level 1, `autocommit = True`, `LISTEN` without `;`, `LISTEN` after the connected frame, `connect()` without URL, eager connect, `select` on the cursor) | 8 | 8 | G-03 (all setup lines), G-05, G-01/G-02/G-04 (eager), G-09 (`select` target) | — |
| setup moved inside `try` (BUG-1803 fix) | 1 | 0 | — | G-06, G-07, G-08 XPASS(strict) |
| queue (newest first, one per round, no `poll`, `poll` twice) | 4 | 4 | G-13, G-23, G-27; G-12 … G-25; G-12, G-14, G-35 | — |
| parse (bad JSON breaks the round) | 1 | 1 | G-15 | — |
| parse (skip non-object, BUG-1802 fix) | 1 | 0 | — | G-16, G-17 XPASS(strict) |
| match (drop workspace, drop user, `<=` / `>=` on user and on workspace, `str()` compare, `is`, `int()` cast) | 9 | 9 | G-18, G-19, G-21, G-22, G-23 | — |
| frame (whole payload, skip missing id, compact JSON, connected frame text) | 4 | 4 | G-13 … G-25, G-27, G-32; G-25; G-03 … | — |
| **Total** | **46** | **44** | | **2** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `setup_inside_try` | **Bug-path** (BUG-1803). Only G-06 … G-08 see it, as designed. No pass card breaks. |
| `parse_skip_non_dict` | **Bug-path** (BUG-1802). Only G-16 and G-17 see it, as designed. No pass card breaks. |

The isolation invariant (R7) holds against every comparison variant. That is because G-18 and G-19 put the other user and the other workspace on both sides of the number (6 / 8, 2 / 4), and G-22 and G-23 pin Python equality.

## Reproduced claims
- **Result line of the notes holds:** `26 passed, 9 xfailed` in 4 of 4 default runs, the coverage run among them, plus the control variant. No flaky test.
- `--runxfail --tb=short`: `9 failed, 26 passed`. Each test fails on the line its card names:

| Cards | Fails today on |
|---|---|
| G-06, G-07 | Then 2, `conn.close.call_count` `0 == 1` |
| G-08 | Then 2, `[] == ['cursor().close', 'close']` |
| G-11 | Then 2, frames are only the connected frame (3 pings missing) |
| G-16, G-17 | Then 1, `AttributeError` (`'list'` / `'NoneType' object has no attribute 'get'`) out of `collect(OSError)` |
| G-31 | Then 2, an extra `: ping` |
| G-33 | Then 2, no ping after the notification |
| G-34 | Then 3, `third` is `: ping` |

- **Mocks:** only the module names `ns.psycopg2`, `ns.select` and, in the R5a cards, `ns.time` (`create=True`), as in the spec's Externals. No database, no session, no DAO. There is no `try/except` around an action. The `try/finally` in G-03, G-34 and G-35 only closes the generator after the asserts.
- **Docstring and comment:** every test carries `# [claude] <ID>`, its card's ID, title and Rules, and `# Then N` numbers that match the card.

## Traceability
cases 35 · tests 35 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Every strict xfail reason names its BUG (BUG-1802, BUG-1803, BUG-1804), and all three are in `docs/testing/bugs.md`. Checked by my own `trace.py` (it parses the cards' `Expect` lines and the test AST). `ruff check` passes.

## Limits of this round
- **The variants are mine.** They show what these tests catch around them, not every possible break.
- **Not exercised:** real `LISTEN`/`NOTIFY` delivery, a Starlette client disconnect (integration-only per the spec), and the intended BUG-1804 behavior. G-10 and G-35 only start to read the clock after that fix. The executor's notes already warn that a fix importing `monotonic` by name would bypass the `ns.time` patch.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/notification_stream.py tests/unit/services/test_notification_stream.py --timeout 60 --json <scratch>/mut_ns.json
  Mutants: 19 · killed 19 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_notification_stream.py -q -p no:cacheprovider --cov=app.services.notification_stream --cov-branch --cov-report=term-missing
  26 passed, 9 xfailed · app\services\notification_stream.py 33 0 6 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_notification_stream.py -q -p no:cacheprovider --runxfail -rf
  9 failed, 26 passed
pytest, default, 3 more runs                                               26 passed, 9 xfailed each
drive.py var_ns.py (47 runs, control included)                             as above; no HANG
trace.py notification_stream.cases.md test_notification_stream.py NST      cards 35 · test-ids 35 · 0 reports
.venv/Scripts/python.exe -m ruff check tests/unit/services/test_notification_stream.py   All checks passed!
git diff --stat -- app/services                                            (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc4v2\` (private `COVERAGE_FILE`). Only this report was written in the repo. No commit. Nothing was killed.
