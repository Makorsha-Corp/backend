# Verification — `app/dao/workspace_audit_log.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 23 cases). See "Round 2" at the end. The rest of this block is round 1.
>

> **Verdict:** NEEDS WORK — only the case designer has work (one small gap). No test is wrong.
> Tests: 18 passed · 3 xfail, all strict (reproduced ✅) · coverage 100% branch (11 statements, 0 branches)
> Mutation: 1 mutant · 1 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 21 unfaithful** (21 / 21 right)
> Hand variants: 29 · 20 caught by a pass card · 9 others: 1 rule gap in Findings (2 variants), 2 bug path, 5 not listed
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** My script rebuilt all 21 with no difference. I read the count lines and LA-20's own `count_sql` by eye. LA-16's Then order (`<=` before `>=`) is the card's own.
- `mutate.py` finds only one site in this module (the `return`), so the hand variants carry the weight here.
- **Why NEEDS WORK:** R7 says `workspace_id`, `user_id` and `action` have no default, but only `action` has a card.

Written by Claude (all 21 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 21. No `workspace_audit_log.local-run.json`, so no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `log_action` R7 ("`workspace_id`, `user_id` and `action` have no default: leaving one out raises `TypeError`") | LA-19 leaves out `action` only. | `la_r1_ws_default` (`workspace_id … = None`) and `la_r7_user_default` pass all 21. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\prop\test_p_workspace_audit_log.py`, not in the repo.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | two new cards, R7 | W1 has no audit rows. When `dao.log_action(db, user_id=U1.id, action="x")` (no `workspace_id`); and, as its own card, `dao.log_action(db, workspace_id=W1.id, action="x")` (no `user_id`), each inside `raises: TypeError` | `raises: TypeError`; nothing written | pass | `la_r1_ws_default`; `la_r7_user_default` |

## Surviving mutants
None.

**Guard.** My own driver re-ran the one mutant with all tests, markers on, no `-x`: it reached all 21 tests, with no collection or setup error.

## Hand variants
On my reference (`plug\ref\workspace_audit_log.py`: `ip_address[:45]`, and `created_at` written as aware UTC; the spec puts the BUG-1403 fix in the model's default, and my reference sets the same value from the DAO) with `--runxfail`, default plan. Every edit applied once; every run reached all 21 tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| la_r1 (each value stored, NULLs, metadata) | 14 | 10 | WAL-LA-01 … LA-06 … | `la_r1_ws_default`, `la_r1_action_strip`, `la_r1_ua_strip`, `la_r1_meta_copy` |
| la_r3 | 3 | 2 | WAL-LA-05, LA-06 | `la_r3_ip46` |
| la_r5 | 1 | 0 | — | `la_r5_naive` |
| la_r6 (no existence check, no dedupe) | 3 | 3 | WAL-LA-17, LA-21 | — |
| la_r7 | 3 | 2 | WAL-LA-18, LA-19 | `la_r7_user_default` |
| w (commit, rollback, expire, expunge, raw write) | 5 | 3 | WAL-LA-20, LA-21 … | `expire_all`, `expunge_all` |
| **Total** | **29** | **20** | | **9** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `la_r3_ip46`, `la_r5_naive` | **Bug path** (BUG-1405, BUG-1403): fail LA-07 in the When, and LA-15/LA-16 on Then 2. |
| `la_r1_action_strip`, `la_r1_ua_strip` | No rule names trimming. R1 says "exactly the given values", and every card's values hold under it. Unlike waitlist R1 (`" Z "` stays `" Z "`), the spec does not single out surrounding spaces. |
| `la_r1_meta_copy` | **Equivalent:** a copy of the dict stores the same JSON. |
| `w:log_action:expire_all`, `expunge_all` | Session housekeeping after the write; no rule names it. |

## xfail tests against the reference
With `--runxfail` on the reference: 21 passed. **The alarm works:** with the markers on, `3 failed, 18 passed`, all `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| WAL-LA-07 | strict | the When (`DataError`), before Then 1, as the card says |
| WAL-LA-15, WAL-LA-16 | strict | Then 2, as the cards say |

## Reproduced claims
- **Result line of the notes holds:** `18 passed, 3 xfailed` in 3 of 3 default runs, the coverage run among them. No flaky test.
- `--runxfail`: `3 failed, 18 passed`.
- **Mocks:** only the commit spy of LA-20 (`MagicMock(wraps=db.commit)` set with `monkeypatch`). No `try`, no broad `pytest.raises`.

## Traceability
cases 21 · tests 21 · unmatched: none · duplicates: none · marker mismatches: none. BUG-1403 and BUG-1405 are in `bugs.md`. `ruff check` passes. `rebuild.py`: 269 cards, 0 reports; selftest 1315 of 1328.

## Limits of this round
- **The reference and the variants are mine.** Variants ran on the default plan only.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/workspace_audit_log.py tests/unit/dao/test_workspace_audit_log.py --timeout 300 --json <scratch>/res/mut_workspace_audit_log.json
  Mutants: 1 · killed 1 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_workspace_audit_log.py -q -p no:cacheprovider --cov=app.dao.workspace_audit_log --cov-branch --cov-report=term-missing
  18 passed, 3 xfailed · app\dao\workspace_audit_log.py 11 0 0 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_workspace_audit_log.py -q -p no:cacheprovider --runxfail -rf
  3 failed, 18 passed
pytest, default, 2 more runs                                   18 passed, 3 xfailed (each)
drive.py bases; drive.py muts; drive.py vars; propdrive.py      as above
rebuild.py; rebuild.py --selftest 8                             269 cards, 0 reports; 1315 of 1328
.venv/Scripts/python.exe -m ruff check <the seven test files>  All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add recipe R-1 (two cards).
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 20 passed · 3 xfail, all strict (reproduced ✅) · coverage 100% branch (11 statements, 0 branches)
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 23 unfaithful** (the 2 new read by eye against their cards; all 23 rebuilt by script)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. I edited no test and made no commit.

### New tests
Each was read against its card and matches its recipe. "Fails" means the round 1 gap variant fails that card on my reference with `--runxfail`, on all three plans (default; sequential scans off; index, bitmap and index-only scans off), with every run reaching all 23 tests.

| Card | Recipe | Fails |
|---|---|---|
| WAL-LA-22 | R-1 | `la_r1_ws_default` |
| WAL-LA-23 | R-1 | `la_r7_user_default` |

Both use a plain `pytest.raises(TypeError)` (no savepoint), and the count is taken before the call, as the card's "nothing written" says.

### Reproduced
- **Result line of the notes holds:** `20 passed, 3 xfailed` in 3 of 3 default runs, the coverage run among them. No flaky test.
- **`--runxfail`:** exactly the bug cards fail, each on its Fails line.
- **Reference:** 23 passed with `--runxfail` on all three plans. **Alarm:** with the markers on, `3 failed, 20 passed`, the strict cards `XPASS(strict)`.
- **Traceability:** cases 23 · tests 23 · unmatched: none · marker mismatches: none. `rebuild.py` over the seven files: 297 cards, 0 reports. `ruff check` passes.
- **Limit:** I kept no copy of the round 1 test file, so "existing tests unchanged" rests on the rebuild of all 23 against their cards, not on a line diff.

### Commands run
```
rebuild.py                                                    297 cards, 0 reports
r2check.py   (gap variants x 3 plans, reference base runs)    every gap variant fails its new card(s); problems: none
repro.sh     (coverage run, --runxfail -rf, 2 more runs)      as under Reproduced
drive.py bases <module>                                       as under Reproduced
.venv/Scripts/python.exe -m ruff check <the six test files>   All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\`. Only this report was edited in the repo. Nothing was stopped or killed.
