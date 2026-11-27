# Verification — `app/dao/notification.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 39 cases). See "Round 2" at the end. The rest of this block is round 1.
>

> **Verdict:** NEEDS WORK — only the case designer has work (one gap). No test is wrong.
> Tests: 33 passed · 5 xfail, 4 strict, 1 non-strict (reproduced ✅) · coverage 100% branch (30 statements, 4 branches)
> Mutation: 27 mutants · 27 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 38 unfaithful** (38 / 38 right)
> Hand variants: 74 · 63 caught by a pass card · 11 others: 1 rule gap in Findings, 6 bug path, 1 equivalent, 3 not listed
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** My script rebuilt all 38 with no difference. I read the 51-row loops, CR-11's `w_count` lines and MR-09's raw `SELECT` lines by eye. The `pg_notify` recorder properties match the Conventions.
- **Why NEEDS WORK:** one rule gap, a privacy one. Every "another recipient" row belongs to U3, a higher id than the U1 who asks, so a `recipient_user_id <= user_id` would show earlier users' notifications to later users.

Written by Claude (all 38 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 38. No `notification.local-run.json`, so no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_for_user` R1 ("rows of … another recipient never appear") | X (another recipient) is always U3, asked about as U1. 1b, "the earlier id as well as the later one". | `gf_r1_user_le` passes all 38. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\prop\test_p_notification.py`, not in the repo.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, GF R1 | X = note; A = note, but `recipient_user_id U3.id`. When `dao.get_for_user(db, workspace_id=W1.id, user_id=U3.id)` | `idset(result[0]) == {A.id}`; `result[1] == 1`; `result[2] == 1` | pass | `gf_r1_user_le` |

## Surviving mutants
None. All 27 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 27 mutants with all tests, markers on, no `-x`: every run reached all 38 tests, with no collection or setup error.

## Hand variants
On my reference (`plug\ref\notification.py`: `ORDER BY created_at DESC, id DESC`; `if ids is not None`; `read_at` as aware UTC) with `--runxfail`, default plan. Every edit applied once; every run reached all 38 tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| gf_r1 | 6 | 5 | NTF-GF-01 … GF-05, GF-08 | `gf_r1_user_le` |
| gf_r2 | 3 | 3 | NTF-GF-01, GF-02, GF-03, GF-09 | — |
| gf_r3 | 6 | 5 | NTF-GF-01 … GF-04, GF-08, GF-09 | `gf_r3_uc_base` |
| gf_r4 | 6 | 2 | NTF-GF-03, GF-05, GF-08 … GF-10, GF-17 | four tie-break variants |
| gf_r5 | 5 | 5 | NTF-GF-03, GF-08 … GF-12, GF-15 | — |
| gf_r6 | 2 | 2 | NTF-GF-17 | — |
| cr_r1 … cr_r4 | 20 | 20 | NTF-CR-01 … CR-08 | — |
| mr_r1 | 3 | 3 | NTF-MR-01, MR-02, MR-08 | — |
| mr_r2 | 1 | 0 | — | `mr_r2_truthy` |
| mr_r3 | 2 | 1 | NTF-MR-01, MR-02 | `mr_r3_naive` |
| mr_r4 | 4 | 3 | NTF-MR-01, MR-02, MR-06 … MR-08 | `mr_r4_keep_read_at` |
| w, get_for_user | 8 | 8 | NTF-GF-10, GF-18 | — |
| w, create, mark_read | 8 | 6 | the commit spies, MR-07 … | `w:create:expire_all`, `w:create:expunge_all` |
| **Total** | **74** | **63** | | **11** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| four `gf_r4_*`, `mr_r2_truthy`, `mr_r3_naive` | **Bug path** (BUG-1412, BUG-1414, BUG-1413): fail GF-06 on Then 2 and GF-07 on Then 4 or 6; MR-03 on Then 1; MR-04/MR-05 on Then 2. |
| `gf_r3_uc_base` | **Equivalent:** `base` plus `is_read = false` is the same set as the separate unread query, with or without `unread_only`. |
| `mr_r4_keep_read_at` | Keeps an existing `read_at` on a row still unread. Such a row cannot arise (`read_at` is set only together with `is_read`); no rule covers it. |
| `w:create:expire_all`, `expunge_all` | Session housekeeping after a write; no rule names it. |

## xfail tests against the reference
With `--runxfail` on the reference: 38 passed. **The alarm works:** with the markers on, `4 failed, 33 passed, 1 xpassed`, the four strict cards `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| NTF-GF-06 | non-strict | Then 2, as the card says |
| NTF-GF-07 | strict | Then 4, as the card says |
| NTF-MR-03 | strict | Then 1, as the card says |
| NTF-MR-04, NTF-MR-05 | strict | Then 2, as the cards say |

## Reproduced claims
- **Result line of the notes holds:** `33 passed, 5 xfailed` in 3 of 3 default runs, the coverage run among them. No flaky test.
- `--runxfail`: `5 failed, 33 passed`.
- **Mocks:** only `app.dao.notification.utcnow` around every `mark_read` When, plus the commit spies of CR-11 and MR-09. No `try`, no broad `pytest.raises`.

## Traceability
cases 38 · tests 38 · unmatched: none · duplicates: none · marker mismatches: none. BUG-1412, BUG-1413, BUG-1414 are in `bugs.md`. `ruff check` passes. `rebuild.py`: 269 cards, 0 reports; selftest 1315 of 1328.

## Limits of this round
- **The reference and the variants are mine.** Variants ran on the default plan only.
- **Not exercised:** delivery of `pg_notify` (needs a commit; integration only).

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/notification.py tests/unit/dao/test_notification.py --timeout 300 --json <scratch>/res/mut_notification.json
  Mutants: 27 · killed 27 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_notification.py -q -p no:cacheprovider --cov=app.dao.notification --cov-branch --cov-report=term-missing
  33 passed, 5 xfailed · app\dao\notification.py 30 0 4 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_notification.py -q -p no:cacheprovider --runxfail -rf
  5 failed, 33 passed
pytest, default, 2 more runs                                   33 passed, 5 xfailed (each)
drive.py bases; drive.py muts; drive.py vars; propdrive.py      as above
rebuild.py; rebuild.py --selftest 8                             269 cards, 0 reports; 1315 of 1328
.venv/Scripts/python.exe -m ruff check <the seven test files>  All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add recipe R-1.
2. **Executor,** after 1: implement it and send back for re-verification.

## Round 2 — 2026-11-03 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 34 passed · 5 xfail, 4 strict, 1 non-strict (reproduced ✅) · coverage 100% branch (30 statements, 4 branches)
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 39 unfaithful** (the 1 new read by eye against their cards; all 39 rebuilt by script)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. I edited no test and made no commit.

### New tests
Each was read against its card and matches its recipe. "Fails" means the round 1 gap variant fails that card on my reference with `--runxfail`, on all three plans (default; sequential scans off; index, bitmap and index-only scans off), with every run reaching all 39 tests.

| Card | Recipe | Fails |
|---|---|---|
| NTF-GF-19 | R-1 | `gf_r1_user_le` |

X is the default note (recipient U1). The call asks for U3, a later id. Then checks the items, `total == 1` and `unread_count == 1`.

### Reproduced
- **Result line of the notes holds:** `34 passed, 5 xfailed` in 3 of 3 default runs, the coverage run among them. No flaky test.
- **`--runxfail`:** exactly the bug cards fail, each on its Fails line.
- **Reference:** 39 passed with `--runxfail` on all three plans. **Alarm:** with the markers on, `4 failed, 34 passed, 1 xpassed`, the strict cards `XPASS(strict)`.
- **Traceability:** cases 39 · tests 39 · unmatched: none · marker mismatches: none. `rebuild.py` over the seven files: 297 cards, 0 reports. `ruff check` passes.
- **Limit:** I kept no copy of the round 1 test file, so "existing tests unchanged" rests on the rebuild of all 39 against their cards, not on a line diff.

### Commands run
```
rebuild.py                                                    297 cards, 0 reports
r2check.py   (gap variants x 3 plans, reference base runs)    every gap variant fails its new card(s); problems: none
repro.sh     (coverage run, --runxfail -rf, 2 more runs)      as under Reproduced
drive.py bases <module>                                       as under Reproduced
.venv/Scripts/python.exe -m ruff check <the six test files>   All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\`. Only this report was edited in the repo. Nothing was stopped or killed.
