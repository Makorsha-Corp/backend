# Verification — `app/dao/mobile_upload_session.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 51 cases). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 31 passed · 6 xfail, 6 strict, 0 non-strict (reproduced ✅) · coverage 100% branch (19 statements, 4 branches, 0 missed)
> Mutation: 17 mutants · 17 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 37 unfaithful** (37 / 37 right)
> Hand variants: 93 · 61 caught by a pass card · 32 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 37 match their cards.
- **Why NEEDS WORK:** 17 of 17 sites killed; five gaps for the case designer: the token's exact compare, "status is not looked at" beyond two statuses, the creator read's other-row shapes, side effects, and what `mark_expired_if_needed` must leave alone.
- No money, stock or order state.

Written by Claude (all 37 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 37. No `mobile_upload_session.local-run.json` exists, so there is no `## Local-coder patterns` section. Script-compared; its differences read by eye (none in this file).

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_token_hash` R2 (skill 1b exact compare) | Arguments tried: unknown, `""`, upper case. No part, no `_`, no space; stored side: no capitals, no space, no longer value. | `t_like`, `t_lower_col`, `t_strip_arg`, `t_lstrip_arg`, `t_trim_col`, `t_ltrim_col` pass all 31. | case designer |
| 2 | case-missing | `get_by_token_hash` R3, `get_for_creator` R3: status and expiry are not looked at | Cards cover `cancelled`, `expired` (T) and `cancelled`, past `waiting` (C). A filter on another status passes. One statement check covers every status without multiplying cards (skill 1a). | `t_r3_not_consumed`, `t_r3_not_uploaded`, `c_r3_not_expired`, `c_r3_not_consumed`, `c_r3_not_uploaded` pass all 31. | case designer |
| 3 | case-missing | `get_for_creator` R1, R2 | The other workspace's and other user's rows are never the earlier id with a later match behind them. | `c_r1_id_ge`, `c_r2_ws_ge`, `c_r2_user_ge` pass all 31. | case designer |
| 4 | case-missing | both reads, Side effects: none (skill 1b) | MUS-T-09, MUS-C-07 check a pending row only. | the ten `t_w_*`, `c_w_*` pass all 31. | case designer |
| 5 | case-missing | `mark_expired_if_needed` R4 and Side effects "sets `session.status` in memory only" | No card checks `expires_at` after the change, or that a pending row of the caller is left alone. | `m_r4_add_expire_stamp`, `m_r4_read_first` pass all 31. | case designer |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\prop\test_prop_mobile_upload_session.py`, not in the repo. Each passes on today's code (a non-strict xfail recipe may fail today) and on the reference, on all three plans. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | cards on T R2 | A = session. When `token_hash=` `"a" * 63`, `" " + "a" * 64`, `"a" * 64 + " "`, `"a%"`, `"a" * 63 + "_"`; and stored `"A" * 64`, `" " + "a" * 63`, `"a" * 63 + " "`, `"xy" + "a" * 62`, each asked with its plain lower-case form | `result is None` | pass | the six `t_*` text variants |
| R-2 | two lines on MUS-T-09, MUS-C-07 | `where` = the text of `sql` after `WHERE` | `statement: "status" not in where`; `statement: "expires_at" not in where` | pass | the five `*_r3_not_*` |
| R-3 | two new cards, C R1, R2 | Z = session, but `workspace_id W2.id`; then A = session, but `token_hash TK2`; When `get_for_creator(session_id=Z.id, workspace_id=W1.id, created_by=U1.id)`. And Z = session, but `created_by U2.id`, then A the same way | `result is None` | pass | `c_r1_id_ge`, `c_r2_ws_ge`, `c_r2_user_ge` |
| R-4 | two new cards, Side effects | A = session; B = session, but `token_hash TK2`; `B.status = "cancelled"`, not flushed. When the token read for TK1 / `get_for_creator` for A | `result.id == A.id`; `session: B in db.dirty`; `session: len(db.dirty) == 1` | pass | the ten `*_w_*` |
| R-5 | a Then line on MUS-M-01 and a new card | M-01 as it is: `re-read S in memory: S.expires_at == PAST`. New: A = session, but `expires_at PAST`; `P` = a pending session with `token_hash TK2`; patched When `mark_expired_if_needed(A)` | `result.status == "expired"`; `pending: P in db.new`; `pending: len(db.new) == 1` | pass | `m_r4_add_expire_stamp`, `m_r4_read_first` |

## Surviving mutants
None. All 17 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 17 mutants with no `-x`: every run reached all 31 pass tests, with no collection or setup error.

## Hand variants
`variants.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv`, on the reference (`_naive_utc` converts to UTC before stripping the zone), with `--runxfail`, on three plans: default, sequential scans off, index and bitmap scans off. Every edit was asserted to apply once and every run reached all 37 tests with no error. Group names: the rule, `w` session side effects, `txt` text compare, `page` paging, `ret` return shape, `ov` parent state.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| n_r1 | 3 | 3 | MUS-M-01, MUS-M-02, MUS-M-03, MUS-M-09, MUS-N-01 | — |
| n_r2 | 3 | 1 | MUS-M-08, MUS-M-11, MUS-M-12, MUS-M-15, MUS-N-02 | `n_r2_today`, `n_r2_add_offset` |
| t_r1 | 4 | 3 | MUS-T-01, MUS-T-02, MUS-T-03, MUS-T-04, MUS-T-05, MUS-T-06 … | `t_r2_one_or_none` |
| t_r3 | 6 | 4 | MUS-T-01, MUS-T-02, MUS-T-06, MUS-T-07, MUS-T-08, MUS-T-09 | `t_r3_not_consumed`, `t_r3_not_uploaded` |
| t_r2 | 2 | 2 | MUS-T-01, MUS-T-03, MUS-T-04, MUS-T-05 | — |
| t_txt | 14 | 8 | MUS-T-04, MUS-T-05 | `t_like`, `t_lower_col`, `t_strip_arg`, `t_lstrip_arg`, `t_trim_col`, `t_ltrim_col` |
| t_ret | 1 | 1 | MUS-T-01, MUS-T-02, MUS-T-06, MUS-T-07, MUS-T-08, MUS-T-09 | — |
| t_w | 12 | 7 | MUS-T-06, MUS-T-08, MUS-T-09 | `t_w_expire`, `t_w_expire_post`, `t_w_dirty_refresh`, `t_w_dirty_flush`, `t_w_dirty_expire` |
| c_r1 | 3 | 2 | MUS-C-01, MUS-C-04 | `c_r1_id_ge` |
| c_r2 | 6 | 4 | MUS-C-02, MUS-C-03 | `c_r2_ws_ge`, `c_r2_user_ge` |
| c_r3 | 6 | 3 | MUS-C-01, MUS-C-05, MUS-C-06, MUS-C-07 | `c_r3_not_expired`, `c_r3_not_consumed`, `c_r3_not_uploaded` |
| c_ret | 1 | 1 | MUS-C-01, MUS-C-05, MUS-C-06, MUS-C-07 | — |
| c_w | 12 | 7 | MUS-C-05, MUS-C-06, MUS-C-07 | `c_w_expire`, `c_w_expire_post`, `c_w_dirty_refresh`, `c_w_dirty_flush`, `c_w_dirty_expire` |
| m_r1 | 5 | 5 | MUS-M-01, MUS-M-02, MUS-M-03, MUS-M-04, MUS-M-05, MUS-M-06 … | — |
| m_r2 | 2 | 2 | MUS-M-02, MUS-M-03, MUS-M-11, MUS-M-12 | — |
| m_r3 | 6 | 5 | MUS-M-04, MUS-M-05, MUS-M-06 | `m_r3_case` |
| m_r4 | 4 | 2 | MUS-M-08 | `m_r4_add_expire_stamp`, `m_r4_read_first` |
| m_r5 | 2 | 1 | MUS-M-08, MUS-M-11, MUS-M-12, MUS-M-15 | `m_r5_raw` |
| m_r5a | 1 | 0 | — | `m_r5a_today` |
| **Total** | **93** | **61** |  | **32** |

With the recipes added, 87 of 93 are caught; the rest are below.

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `n_r2_today`, `n_r2_add_offset`, `m_r5_raw`, `m_r5a_today` | **Bug path** (BUG-1282): each fails strict cards; `m_r5_raw` is today's own comparison written out. |
| `t_r2_one_or_none` | **Equivalent:** `token_hash` is unique. |
| `m_r3_case` | **Equivalent on real states:** statuses are written lower-case by the manager only. |

## xfail tests against the reference
Reference: `_naive_utc` converts to UTC before stripping the zone, swapped in memory. Nothing is written to `app/`. With `--runxfail` on the reference: 37 passed. **The alarm works:** with the markers on, every strict card goes `XPASS(strict)`.

| Card | Marker | Card's Fails line | Seen |
|---|---|---|---|
| MUS-N-03 | strict | Then 2 | fails on Then 2 in 3 of 3 `--runxfail` runs, as the card says |
| MUS-N-04 | strict | Then 2 | fails on Then 2 in 3 of 3 `--runxfail` runs, as the card says |
| MUS-M-13 | strict | Then 2 | fails on Then 2 in 3 of 3 `--runxfail` runs, as the card says |
| MUS-M-14 | strict | Then 2 | fails on Then 2 in 3 of 3 `--runxfail` runs, as the card says |
| MUS-M-16 | strict | Then 2 | fails on Then 2 in 3 of 3 `--runxfail` runs, as the card says |
| MUS-M-17 | strict | Then 2 | fails on Then 2 in 3 of 3 `--runxfail` runs, as the card says |

## Reproduced claims
- Coverage run: `31 passed, 6 xfailed in 4.25s`; `app\dao\mobile_upload_session.py      19      0      4      0   100%`. Four more default runs: `31 passed, 6 xfailed in 2.39s`, `31 passed, 6 xfailed in 2.29s`, `31 passed, 6 xfailed in 2.29s`, `31 passed, 6 xfailed in 2.28s`.
- `--runxfail -rf`: `6 failed, 31 passed in 2.26s`; failed: MUS-N-03, MUS-N-04, MUS-M-13, MUS-M-14, MUS-M-16, MUS-M-17.
- 15 more runs (5 per plan): 31 passed in every run, no pass card or strict card moved. **No flaky test.** Only non-strict cards move between XFAIL and XPASS, which their markers allow; the notes' sample default line is one heap's result.
- **Mocks:** only `app.dao.mobile_upload_session.utcnow`, the spec's one external. No `try`, no `if`, no broad `pytest.raises` in a test body.

## Traceability
cases 37 · tests 37 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md` and each reason carries the row's title. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script (`rebuild.py`) rebuilt each test's Given, snapshots, When, Then and marker from its card, and the constants, standing rows, builders and helpers from the Conventions, and compared by AST, for all 302 cards of the batch: 0 reports. Selftest (`selftest.py`, 3 seeds): 9306 of 9306 planted mistakes of 81 kinds, in tests, helpers and cards, reported on the right card.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents were live on `marker_test`. Every kill is a plain `N failed` with all tests reached.
- **No DDL.** The one schema question (PBL-G-14) was answered with `SET LOCAL session_replication_role = replica` inside a rolled-back test, which switches foreign-key actions off without a lock.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/mobile_upload_session.py tests/unit/dao/test_mobile_upload_session.py --timeout 300 --json <scratch>/res/mut_mobile_upload_session.json   (through runmut.py, TEMP in scratch)
  17 mutants · 17 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_mobile_upload_session.py -q -p no:cacheprovider --cov=app.dao.mobile_upload_session --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  31 passed, 6 xfailed in 4.25s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_mobile_upload_session.py -q -p no:cacheprovider --runxfail -rf
  6 failed, 31 passed in 2.26s
repro.py; nonstrict.py (5 runs x 3 plans); thenloc.py                as under Reproduced
drive.py bases | muts | vars --plan default|seq|idx                     as above
propdrive.py (3 plans)                                                  recipes as in the table
rebuild.py; selftest.py 7|21|33                                         302 cards, 0 reports; 9306 of 9306
.venv/Scripts/python.exe -m ruff check <the eleven test files>         All checks passed!
git diff --stat -- app/dao                                              (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add the recipes above; the Givens and Thens are written out.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 45 passed · 6 xfail, 6 strict, 0 non-strict (reproduced ✅) · coverage as round 1
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 51 unfaithful** (new and changed cards read by eye; all 51 rebuilt by script)
> Hand variants: 93 · 87 caught by a pass card · every round-1 gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1

Every finding of round 1 is closed. No new rule gap. No test edited, no commit. Nothing parked for the owner.

### New and changed tests
MUS-T-10 … MUS-T-19, MUS-C-08 … MUS-C-10, MUS-M-18; new Then lines on MUS-T-09, MUS-C-07, MUS-M-01. Each was read against its card. "Fails" means the variant fails that card on the reference with `--runxfail`, on all three plans.

| Card | Recipe | Fails |
|---|---|---|
| MUS-T-10 … T-18 | R-1 | the six `t_*` text variants |
| MUS-T-09, MUS-C-07 | R-2 | `t_r3_not_*`, `c_r3_not_*` |
| MUS-C-08, MUS-C-09 | R-3 | `c_r2_ws_ge`, `c_r2_user_ge`, `c_r1_id_ge` |
| MUS-T-19, MUS-C-10 | R-4 | the ten `*_w_*` |
| MUS-M-01, MUS-M-18 | R-5 | `m_r4_add_expire_stamp`, `m_r4_read_first` |

### Rest of the batch
All 93 variants ran again on the reference, each reaching all 51 tests, on all three plans. Left without a pass card: `m_r3_case`, `m_r5_raw`, `m_r5a_today`, `n_r2_add_offset`, `n_r2_today`, `t_r2_one_or_none`. Each is under round 1's "Considered and not listed" (bug path, a cap above the card's own rows, or equivalent); none is a new rule gap.

### Reproduced
- Coverage run: `45 passed, 6 xfailed in 4.50s`; `['app\\dao\\mobile_upload_session.py      19      0      4      0   100%']`. Four more default runs: `45 passed, 6 xfailed in 2.56s`, `45 passed, 6 xfailed in 2.65s`, `45 passed, 6 xfailed in 2.35s`, `45 passed, 6 xfailed in 2.39s`.
- `--runxfail`: `6 failed, 45 passed in 2.41s ['mus_n_03', 'mus_n_04', 'mus_m_13', 'mus_m_14', 'mus_m_16', 'mus_m_17']`. Every strict card fails on its card's `Fails today on` line.
- 15 more runs (5 per plan): 45 passed in every run; only non-strict cards move. No flaky test.
- Traceability: cases 51 · tests 51 · unmatched: none · marker mismatches: none. `rebuild.py`: 361 cards over the eleven files, 0 reports (it learned the new `where` name of `mobile_upload_session`). Selftest: 9306 of 9306 planted mistakes, 3 seeds. `ruff check` passes.
- **Limit:** I kept no copy of the round-1 test file; "existing tests unchanged" rests on the rebuild of all cards against the current cases file.

### Commands run
```
drive.py bases | vars --plan default|seq|idx <module>     reference, alarm, variants
r2check.py                                             gap variants against their new cards
repro.py; nonstrict.py; thenloc.py                     as under Reproduced
rebuild.py; selftest.py 7|21|33                        361 cards, 0 reports; 9306 of 9306
.venv/Scripts/python.exe -m ruff check <the eleven test files>     All checks passed!
git diff --stat -- app/dao                             (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\`. Only this report was edited in the repo. Nothing was stopped or killed.
