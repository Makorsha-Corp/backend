# Verification — `app/dao/workspace_member.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 54 cases). See "Round 2" at the end. The rest of this block is round 1.
>

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 39 passed · 5 xfail, 3 strict, 2 non-strict (reproduced ✅) · coverage 100% branch (22 statements, 2 branches)
> Mutation: 21 mutants · 21 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 44 unfaithful** (44 / 44 right)
> Hand variants: 105 · 90 caught by a pass card · 15 others: 11 rule gaps in Findings, 4 bug path
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** My script rebuilt every test from its card with no difference; the loop Givens (GU-03, GM-10, GW-06) and the `pair_count` line of WU-06 I read by eye.
- **Why NEEDS WORK:** every mutant is killed, but hand variants show 5 rule gaps, all for the case designer.
- **The serious one is Finding 1.** `has_access` is the access gate of every workspace request. In every card the other user has a *higher* id than the one asked about. A wrong `user_id <= user_id` would let a later-registered person into a workspace that only an earlier one belongs to, and all 44 tests still pass.

Written by Claude (all 44 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 44. No `workspace_member.local-run.json`, so no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_workspace_and_user` R2, `has_access` R2 ("another user in this workspace is not matched") | The other user is always U2 or U3, asked about as U1: always the higher id. 1b, "by-id reads": the earlier id as well as the later one. | `wu_r2_user_le` passes all 44; through it, `has_access` returns `True` for a non-member. | **case designer** |
| 2 | case-missing | `get_by_user` R1 | The same shape: the other user's row (X, U2) always has the higher user id. | `gu_r1_user_le` passes all 44. | **case designer** |
| 3 | case-missing | `get_workspace_members` R3, `count_active_members` R2 | The other workspace is always W2, asked about as W1. | `gm_r3_ws_le`, `ca_r2_ws_le` pass all 44. | **case designer** |
| 4 | case-missing | `has_access` R2 (names `""`; "status exactly `'active'`") | Stored side is checked only with `'Active'` and `'inactive'`. There is no `""` (named in R2), no leading or trailing space, and no part of the word. 1b, "exact compare". | `ha_r2_strip`, `ha_r2_lstrip`, `ha_r2_rstrip`, `ha_r2_in_const` (`status in 'active'`: `""` gives `True`), `ha_r2_prefix` pass all 44. | **case designer** |
| 5 | case-missing | `count_active_members` R1 ("exactly `'active'`") | CA-01 stores `Active`, `inactive`, ` active`, but no part of the word and nothing longer. | `ca_r1_cst_prefix` (`LIKE 'active%'`), `ca_r1_cst_part` (`LIKE 'activ%'`) pass all 44. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\prop\test_p_workspace_member.py`, not in the repo. Each passes on today's code and on my reference, and each named variant fails it (`wsv\res\prop.out`).

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | two new cards, WU R2 and HA R2 | A = member. When `dao.get_by_workspace_and_user(db, workspace_id=W1.id, user_id=U2.id)`; and, as its own card, `dao.has_access(db, user_id=U2.id, workspace_id=W1.id)` | `result is None`; `result is False` | pass | `wu_r2_user_le` (both cards) |
| R-2 | new card, GU R1 | X = member; A = member, but `user_id U2.id`, `workspace_id W2.id`. When `dao.get_by_user(db, user_id=U2.id)` | `idset(result) == {A.id}` | pass | `gu_r1_user_le` |
| R-3 | two new cards, GM R3 and CA R2 | Z = member; A = member, but `workspace_id W2.id`. When `dao.get_workspace_members(db, workspace_id=W2.id, status=None)`; and `dao.count_active_members(db, workspace_id=W2.id)` | `idset(result) == {A.id}`; `result == 1` | pass | `gm_r3_ws_le`; `ca_r2_ws_le` |
| R-4 | four new cards, HA R2, one shape each | A = member, but `status ""` / `" active"` / `"active "` / `"activ"`. When `dao.has_access(db, user_id=U1.id, workspace_id=W1.id)` | `result is False` | pass | `""`: `ha_r2_in_const`; `" active"`: `ha_r2_strip`, `ha_r2_lstrip`; `"active "`: `ha_r2_strip`, `ha_r2_rstrip`, `ha_r2_prefix`; `"activ"`: `ha_r2_in_const`, `ha_r2_prefix` |
| R-5 | new card, CA R1 | A = member, but `status "activ"`; B = member, but `user_id U2.id`, `status "actives"`. When `dao.count_active_members(db, workspace_id=W1.id)` | `result == 0` | pass | `ca_r1_cst_prefix`, `ca_r1_cst_part` |

## Surviving mutants
None. All 21 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 21 mutants with all tests, markers on, no `-x`: every run reached all 44 tests, with no collection or setup error.

## Hand variants
`wsv\plug\variants.py`, on my reference (`plug\ref\workspace_member.py`: `ORDER BY id` in `get_by_user` and `get_workspace_members`) with `--runxfail`, default plan. Every edit was asserted to apply exactly once; every run reached all 44 tests. `w` = side-effect wrappers (flush, commit, rollback, expire_all, expunge_all, a pending row, a raw write, a dirtied result).

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| wu_r1 | 1 | 1 | WSM-WU-01 | — |
| wu_r2 | 6 | 5 | WSM-WU-01, WU-02, WU-03, HA-01, HA-04, HA-05 … | `wu_r2_user_le` |
| wu_kw | 1 | 1 | WSM-WU-07 | — |
| gu_r1 | 3 | 2 | WSM-GU-01, GU-02, GU-06 | `gu_r1_user_le` |
| gu_r2 | 1 | 1 | WSM-GU-03 | — |
| gu_r3 | 2 | 0 | — | `gu_r3_desc`, `gu_r3_ws` |
| gm_r1 | 1 | 1 | WSM-GM-01 | — |
| gm_r2 | 14 | 14 | WSM-GM-01, GM-03 … GM-08 | — |
| gm_r3 | 4 | 3 | WSM-GM-02, GM-04, GM-09, GM-10, GM-13, GW-01 … | `gm_r3_ws_le` |
| gm_r4 | 2 | 0 | — | `gm_r4_desc`, `gm_r4_user` |
| gw_r1 | 2 | 2 | WSM-GW-01, GW-06 | — |
| gw_r3 | 1 | 1 | WSM-GW-03, GW-04 | — |
| gw_kw | 1 | 1 | WSM-GW-05 | — |
| ca_r1 | 8 | 6 | WSM-CA-01, CA-02 | `ca_r1_cst_prefix`, `ca_r1_cst_part` |
| ca_r2 | 3 | 2 | WSM-CA-01 … CA-04 | `ca_r2_ws_le` |
| ha_r1 | 1 | 1 | WSM-HA-02, HA-03 | — |
| ha_r2 | 8 | 3 | WSM-HA-02, HA-03 | `ha_r2_strip`, `ha_r2_lstrip`, `ha_r2_rstrip`, `ha_r2_in_const`, `ha_r2_prefix` |
| w, six readers | 46 | 46 | WSM-WU-08, GU-06, GM-13, GW-07, CA-04, HA-06 … | — |
| **Total** | **105** | **90** | | **15** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `gu_r3_desc`, `gu_r3_ws`, `gm_r4_desc`, `gm_r4_user` | **Bug path** (BUG-1400). Each fails a strict SQL card (GU-05, GM-12, GW-02) on Then 3 or 4, and the `desc` ones also fail GU-04/GM-11 on Then 2. |

## xfail tests against the reference
With `--runxfail` on the reference: 44 passed. **The alarm works:** with the markers on, `3 failed, 39 passed, 2 xpassed`, the strict cards `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| WSM-GU-04, WSM-GM-11 | non-strict | Then 2, as the card says |
| WSM-GU-05, WSM-GM-12, WSM-GW-02 | strict | Then 2, as the card says |

## Reproduced claims
- **Result line of the notes holds:** `39 passed, 5 xfailed` in 3 of 3 default runs, the coverage run among them, plus the driver's plain run. No flaky test.
- `--runxfail`: `5 failed, 39 passed`, exactly the five bug cards, each on its Fails line.
- **Mocks:** none. No `try`, no broad `pytest.raises`.

## Traceability
cases 44 · tests 44 · unmatched: none · duplicates: none · marker mismatches: none (reasons are the constants `BUG_1400` / `BUG_1400_NON_STRICT`, both naming BUG-1400, which is in `bugs.md`). Card order equals file order. Docstrings, `# Then N` numbers and Given order match. `ruff check` passes.

`wsv\rebuild.py` compared all 269 cards of the batch: 0 reports. Selftest: 1315 of 1328 planted mistakes of 27 kinds; the 13 misses are loop-Given values and helper column strings, read by eye.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- Variants ran on the default plan only.
- **Runs were not isolated.** Other agents may have been live.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/workspace_member.py tests/unit/dao/test_workspace_member.py --timeout 300 --json <scratch>/res/mut_workspace_member.json
  Mutants: 21 · killed 21 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_workspace_member.py -q -p no:cacheprovider --cov=app.dao.workspace_member --cov-branch --cov-report=term-missing
  39 passed, 5 xfailed · app\dao\workspace_member.py 22 0 2 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_workspace_member.py -q -p no:cacheprovider --runxfail -rf
  5 failed, 39 passed
pytest, default, 2 more runs                                   39 passed, 5 xfailed (each)
drive.py bases; drive.py muts; drive.py vars; propdrive.py      as above
rebuild.py; rebuild.py --selftest 8                             269 cards, 0 reports; 1315 of 1328
.venv/Scripts/python.exe -m ruff check <the seven test files>  All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add recipes R-1 to R-5; the Givens and Thens are written out above. R-1 first (access gate).
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 49 passed · 5 xfail, 3 strict, 2 non-strict (reproduced ✅) · coverage 100% branch (22 statements, 2 branches)
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 54 unfaithful** (the 10 new read by eye against their cards; all 54 rebuilt by script)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. I edited no test and made no commit.

### New tests
Each was read against its card and matches its recipe. "Fails" means the round 1 gap variant fails that card on my reference with `--runxfail`, on all three plans (default; sequential scans off; index, bitmap and index-only scans off), with every run reaching all 54 tests.

| Card | Recipe | Fails |
|---|---|---|
| WSM-WU-09 | R-1 | `wu_r2_user_le` |
| WSM-HA-07 | R-1 | `wu_r2_user_le` |
| WSM-GU-07 | R-2 | `gu_r1_user_le` |
| WSM-GM-14 | R-3 | `gm_r3_ws_le` |
| WSM-CA-05 | R-3 | `ca_r2_ws_le` |
| WSM-HA-08 | R-4 | `ha_r2_in_const` |
| WSM-HA-09 | R-4 | `ha_r2_strip`, `ha_r2_lstrip` |
| WSM-HA-10 | R-4 | `ha_r2_strip`, `ha_r2_rstrip`, `ha_r2_prefix` |
| WSM-HA-11 | R-4 | `ha_r2_in_const`, `ha_r2_prefix` |
| WSM-CA-06 | R-5 | `ca_r1_cst_prefix`, `ca_r1_cst_part` |

**The access gate (WU-09, HA-07), read twice.** One member A (W1, U1). The call asks about U2, made after U1 by the chained fixtures, so the member has the *lower* id: the shape of round 1's Finding 1. Then 1 is exactly `result is None` / `result is False`. Then 2 counts the `workspace_members` rows of U2 with a new helper, `user_count` (read: a Core `count(*) … where user_id = :u`), equal to 0. No mock, no wrapper. Under `wu_r2_user_le` both fail on Then 1 on all three plans: `has_access` returns `True` for the non-member.

### Reproduced
- **Result line of the notes holds:** `49 passed, 5 xfailed` in 3 of 3 default runs, the coverage run among them. No flaky test.
- **`--runxfail`:** exactly the bug cards fail, each on its Fails line.
- **Reference:** 54 passed with `--runxfail` on all three plans. **Alarm:** with the markers on, `3 failed, 49 passed, 2 xpassed`, the strict cards `XPASS(strict)`.
- **Traceability:** cases 54 · tests 54 · unmatched: none · marker mismatches: none. `rebuild.py` over the seven files: 297 cards, 0 reports. `ruff check` passes.
- **Limit:** I kept no copy of the round 1 test file, so "existing tests unchanged" rests on the rebuild of all 54 against their cards, not on a line diff.

### Commands run
```
rebuild.py                                                    297 cards, 0 reports
r2check.py   (gap variants x 3 plans, reference base runs)    every gap variant fails its new card(s); problems: none
repro.sh     (coverage run, --runxfail -rf, 2 more runs)      as under Reproduced
drive.py bases <module>                                       as under Reproduced
.venv/Scripts/python.exe -m ruff check <the six test files>   All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\`. Only this report was edited in the repo. Nothing was stopped or killed.
