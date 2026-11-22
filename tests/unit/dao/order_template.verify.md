# Verification — `app/dao/order_template.py`

> **Current verdict: PASS** (round 2, 2026-11-02, revision 1, 74 cases). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 55 passed · 7 xfail, 2 strict, 5 non-strict (reproduced ✅) · coverage 100% branch (23 statements, 4 branches)
> Mutation: 18 mutants · 18 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 62 unfaithful** (62 / 62 right)
> Hand variants: 149 · 112 caught by a pass card · 37 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** This file was read fully by eye, against every card. All 62 match, and the script agrees.
- **Why NEEDS WORK:** 18 sites, all killed, but hand variants show 4 rule gaps, for the case designer. The largest is R3's exact compare.
- **Money:** line prices are only read back here, and no gap touches them. BUG-1226 stays the manager's.

Written by Claude (all 62 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 62. No `order_template.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_workspace` R3 "compared exactly: case-sensitive, no trimming, no wildcards" | GW-08 and GW-09 test one direction each. No argument in capitals, no leading space, no part of a category, no `_` (cases Spec gap 6). | `gw_r3_lower_arg`, `gw_r3_lstrip`, `gw_r3_contains_auto`, `gw_r3_startswith`, `gw_r3_endswith`, `gw_r3_like_esc_pct` pass all 62 on all three plans. | **case designer** |
| 2 | case-missing | `get_by_workspace` R3 "no trimming" | Every card stores a clean category, and `expense_category` takes any text (FU-1 (b)), so a stored space can exist. | `gw_r3_trim_col` passes all 62 on all three plans. | **case designer** |
| 3 | case-missing | both by-id reads, R2 "Another workspace's id ... returns `None`" | GI-02 and II-02 build the other workspace's row last, so a wrong `>=` on `id` finds nothing there. The workspace rule leaks when that row is the earlier one. | `gi_r2_id_ge`, `ii_r2_id_ge` pass all 62 on all three plans. `<=` is caught. | **case designer** |
| 4 | case-missing | all four readers, Side effects: none | A read may leave a change for the caller's next commit, or drop the caller's own unflushed edit. GW-33, GI-07, GT-15, II-07 check new rows and statements sent, not edited rows. | `gw_w_dirty_hit`, `gi_w_dirty_hit`, `gt_w_dirty_hit`, `ii_w_dirty_hit` and the four `*_w_expire` pass all 62 on all three plans. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\prop\test_prop.py`, not in the repo. Each passes on today's code and on the reference. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | five new cards, R3 | A = template, `created_at T10`, but `expense_category "factory"`; When `expense_category=` `"FACTORY"`, `" factory"`, `"fact"`, `"tory"`, `"f_ctory"` | `result == []` | pass | `gw_r3_lower_arg`, `gw_r3_lstrip`, `gw_r3_contains_auto`, `gw_r3_startswith`, `gw_r3_endswith`, `gw_r3_like_esc_pct` |
| R-2 | new card, R3 | A = template, `created_at T10`, but `expense_category " factory"`; When `expense_category="factory"` | `result == []` | pass | `gw_r3_trim_col` |
| R-3 | two new cards, R2 | GI: Z = template, `created_at T10`, but `workspace_id W2.id`; then A = template, `created_at T11`; When `id=Z.id, workspace_id=W1.id`. II: T = template, `created_at T10`; Z = line on T, `line_number 1`, but `workspace_id W2.id`; then A = line on T, `line_number 2`; When `id=Z.id, workspace_id=W1.id` | `result is None` | pass | `gi_r2_id_ge`, `ii_r2_id_ge` |
| R-4 | four new cards, Side effects | GW: A = template, `created_at T10`; B = template, `created_at T10`, but `workspace_id W2.id`; `B.expense_category = "other"`, not flushed. GI: A, then B = template, `created_at T11`, edited the same way. GT: T, S templates; A = line on T, `line_number 1`; B = line on S, `line_number 1`; `B.description = "Edited"`, not flushed. II: A, B lines on T, `line_number` 1 and 2, B edited the same way. Each When reads A | the card's result check; `session: B in db.dirty`; `session: len(db.dirty) == 1` (`session:` as in `workspace.cases.md`) | pass | the eight variants of Finding 4 |

## Surviving mutants
None. All 18 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 18 mutants with no `-x`: every run reached all 62 tests, with no collection or setup error.

## Hand variants
`plug\variants.py`, on the reference with `--runxfail`, default plan, then again with sequential scans off and with index and bitmap scans off: the same variants caught by the same pass cards. Every edit was asserted to apply once and every run reached all 62 tests. Group names: the rule, `w` writes and session, `s` side effects, `txt` the text compare, `kw` keyword-only.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| gw_r1 | 5 | 5 | OTP-GW-01, OTP-GW-02, OTP-GW-03, OTP-GW-04, OTP-GW-05, OTP-GW-06 … | — |
| gw_r2 | 6 | 6 | OTP-GW-01, OTP-GW-06, OTP-GW-07, OTP-GW-21, OTP-GW-22 | — |
| gw_r3 | 20 | 13 | OTP-GW-08, OTP-GW-09, OTP-GW-10, OTP-GW-11, OTP-GW-21, OTP-GW-23 | `gw_r3_like_esc_pct`, `gw_r3_contains_auto`, `gw_r3_startswith`, `gw_r3_endswith`, `gw_r3_lower_arg`, `gw_r3_lstrip`, `gw_r3_trim_col` |
| gw_r4 | 3 | 3 | OTP-GW-08, OTP-GW-09, OTP-GW-10, OTP-GW-11, OTP-GW-13, OTP-GW-21 … | — |
| gw_r5 | 13 | 6 | OTP-GW-01, OTP-GW-05, OTP-GW-12, OTP-GW-13, OTP-GW-14, OTP-GW-15 … | `gw_r5_id_asc_tail`, `gw_r5_no_tail`, `gw_r5_name_tail`, `gw_r5_name_desc_tail`, `gw_r5_flag_tail`, `gw_r5_flag2_tail`, `gw_r5_cat_tail` |
| gw_r6 | 3 | 3 | OTP-GW-06, OTP-GW-07, OTP-GW-08, OTP-GW-09, OTP-GW-10, OTP-GW-11 … | — |
| gw_r7 | 14 | 12 | OTP-GW-01, OTP-GW-02, OTP-GW-05, OTP-GW-06, OTP-GW-07, OTP-GW-08 … | `gw_r7_cap_101`, `gw_r7_cap_1000` |
| gw_r8 | 7 | 7 | OTP-GW-27, OTP-GW-31, OTP-GW-32 | — |
| gw_kw | 1 | 0 | — | `gw_kw_positional` |
| gw_w | 9 | 7 | OTP-GW-01, OTP-GW-02, OTP-GW-05, OTP-GW-06, OTP-GW-07, OTP-GW-08 … | `gw_w_expire`, `gw_w_dirty_hit` |
| gi_r1 | 3 | 2 | OTP-GI-01, OTP-GI-02, OTP-GI-03, OTP-GI-04, OTP-GI-06 | `gi_r1_one_or_none` |
| gi_r2 | 7 | 6 | OTP-GI-01, OTP-GI-02, OTP-GI-03, OTP-GI-04, OTP-GI-05, OTP-GI-06 … | `gi_r2_id_ge` |
| gi_r3 | 1 | 1 | OTP-GI-05 | — |
| gi_w | 10 | 8 | OTP-GI-01, OTP-GI-05, OTP-GI-06, OTP-GI-07 | `gi_w_expire`, `gi_w_dirty_hit` |
| gt_r1 | 3 | 2 | OTP-GT-02, OTP-GT-03, OTP-GT-04, OTP-GT-05 | `gt_r1_cap_101` |
| gt_r3 | 1 | 1 | OTP-GT-11, OTP-GT-13 | — |
| gt_r2 | 9 | 3 | OTP-GT-05, OTP-GT-06, OTP-GT-07, OTP-GT-14 | `gt_r2_no_tail`, `gt_r2_id_desc_tail`, `gt_r2_qty_tail`, `gt_r2_qty_desc_tail`, `gt_r2_price_tail`, `gt_r2_price_desc_tail` |
| gt_r4 | 2 | 2 | OTP-GT-12, OTP-GT-13 | — |
| gt_r5 | 1 | 1 | OTP-GT-14 | — |
| gt_x | 1 | 0 | — | `gt_x_nonzero` |
| gt_w | 9 | 7 | OTP-GT-01, OTP-GT-02, OTP-GT-05, OTP-GT-06, OTP-GT-07, OTP-GT-12 … | `gt_w_expire`, `gt_w_dirty_hit` |
| ii_r1 | 3 | 2 | OTP-II-01, OTP-II-02, OTP-II-03, OTP-II-04, OTP-II-06 | `ii_r1_one_or_none` |
| ii_r2 | 7 | 6 | OTP-II-01, OTP-II-02, OTP-II-03, OTP-II-04, OTP-II-06 | `ii_r2_id_ge` |
| ii_r3 | 1 | 1 | OTP-II-05 | — |
| ii_w | 10 | 8 | OTP-II-01, OTP-II-05, OTP-II-06, OTP-II-07 | `ii_w_expire`, `ii_w_dirty_hit` |
| **Total** | **149** | **112** |  | **37** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `gw_r5_*_tail` (7), `gt_r2_*_tail` and `gt_r2_id_desc_tail` (6) | **Bug path.** Wrong tie orders, caught only by GW-17 to GW-20 and GT-08 to GT-10, which is what those cards are for. They become pass cards when BUG-1210 and BUG-1211 are fixed. Each fails its strict SQL card or a non-strict card on Then 2. |
| `gw_r7_cap_101`, `gw_r7_cap_1000`, `gt_r1_cap_101` | A cap above the card's own 101. `gw_r7_cap_100` and `gt_r1_cap_100` are caught; 1000 is the endpoint's bound. |
| `gt_x_nonzero` | An added filter on a column no rule names. |
| `gi_r1_one_or_none`, `ii_r1_one_or_none` | **Equivalent:** the primary key leaves one row. |
| `gw_kw_positional` | A note, not a rule: cases Spec gap 1, as in `work_order_approver.verify.md`. |

## xfail tests against the reference
Reference: both `order_by`s with their `id` tail, swapped in memory. Nothing is written to `app/`.

With `--runxfail` on the reference: 62 passed. **The alarm works:** with the markers on, `2 failed, 55 passed, 5 xpassed`, the strict cards `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| OTP-GW-17, GW-18, GW-19 | non-strict | Then 2, in all 3 plans |
| OTP-GW-20 | strict | Then 4, as the card says |
| OTP-GT-08 | non-strict | Then 2 when it fails: always with index and bitmap scans off, sometimes on the default plan, which its Fails line allows |
| OTP-GT-09 | non-strict | Passes on today's code in every run, which its Fails line allows. Fails Then 2 under every wrong tie order that decides it |
| OTP-GT-10 | strict | Then 4, as the card says |

## Reproduced claims
- **Result line of the notes holds:** `55 passed, 6 xfailed, 1 xpassed` in 5 of 5 default runs, the coverage run among them. No flaky test.
- `--runxfail`, on 3 plans: `5 or 6 failed, the rest passed; GT-08 is the one that moves`.
- **Mocks:** none. No `try`, no broad `pytest.raises`, no `if` in a test body.

## Traceability
cases 62 · tests 62 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script rebuilt each test's Given, snapshots, When, Then and marker from its card and compared by AST, for all 221 cards of the batch, with the helpers against the Conventions. It gave 2 reports, both the wait of WSP-IN-04 (see `workspace.verify.md`). Selftest: 1283 of 1283 planted mistakes of 60 kinds, in tests, helpers and cards.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live. Each kill is a plain `N failed`.
- **Reference DDL** ran inside each test's own rolled-back transaction, in three short runs per module that needs it, on the shared test database. Nothing persisted. Hand variants ran without it, and the bug cards it serves are left out of their counts.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/order_template.py tests/unit/dao/test_order_template.py --timeout 300 --json <scratch>/res/mut_order_template.json   (through runmut.py)
  18 mutants · 18 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_order_template.py -q -p no:cacheprovider --cov=app.dao.order_template --cov-branch --cov-report=term-missing --tb=no
  55 passed, 6 xfailed, 1 xpassed
pytest, default, 4 more runs; pytest --runxfail --tb=short, 3 plans        repro.py
drive.py bases; drive.py muts; drive.py vars                               as above
propdrive.py                                                               0 problems
rebuild.py; rebuild.py --selftest 6                                        221 cards, 2 reports; 1283 of 1283
.venv/Scripts/python.exe -m ruff check <the nine test files>               All checks passed!
git diff --stat -- app/dao                                                 (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add the recipes above; the Givens and Thens are written out.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-02 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 67 passed · 7 xfail, 2 strict, 5 non-strict (reproduced ✅) · coverage 100% branch (23 statements, 4 branches)
> Mutation: not re-run; round 1 stands at 18 / 18 → 100% (18 mutants)
> Fidelity: **0 of 74 unfaithful** (the 12 new read by eye; all 74 rebuilt by script)
> Hand variants: 149 · 129 caught by a pass card · every gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test edited in this round, no commit.

### New tests
Each was read against its card and matches its recipe. "Fails" means the variant fails that card, on the reference with `--runxfail`, on all three plans.

| Card | Recipe | Fails |
|---|---|---|
| OTP-GW-34 | R-1 | `gw_r3_lower_arg` |
| OTP-GW-35 | R-1 | `gw_r3_lstrip` |
| OTP-GW-36 | R-1 | `gw_r3_contains_auto`, `gw_r3_startswith` |
| OTP-GW-37 | R-1 | `gw_r3_contains_auto`, `gw_r3_endswith` |
| OTP-GW-38 | R-1 | `gw_r3_like_esc_pct` |
| OTP-GW-39 | R-2 | `gw_r3_trim_col`, and also `gw_r3_contains_auto`, `gw_r3_endswith` |
| OTP-GI-08 | R-3 | `gi_r2_id_ge` |
| OTP-II-08 | R-3 | `ii_r2_id_ge` |
| OTP-GW-40 | R-4 | `gw_w_dirty_hit`, `gw_w_expire` |
| OTP-GI-09 | R-4 | `gi_w_dirty_hit`, `gi_w_expire` |
| OTP-GT-16 | R-4 | `gt_w_dirty_hit`, `gt_w_expire` |
| OTP-II-09 | R-4 | `ii_w_dirty_hit`, `ii_w_expire` |

### Rest of the batch
All 149 variants ran again, each reaching all 74 tests, on all three plans. Left without a pass card: the 20 under "Considered and not listed". None is a new rule gap.

### Reproduced
- **Result line of the notes holds:** `67 passed, 6 xfailed, 1 xpassed` in 5 of 5 default runs, the coverage run among them. No flaky test.
- **`--runxfail`:** `5 failed, 69 passed` on the default and sequential-off settings; `6 failed, 68 passed` with index and bitmap scans off.
- **Reference:** 74 passed with `--runxfail`, on the bases of round 1. **Alarm:** with the markers on, `2 failed, 67 passed, 5 xpassed`, the strict cards `XPASS(strict)`.
- **Traceability:** cases 74 · tests 74 · unmatched: none · marker mismatches: none. `rebuild.py`: 252 cards over the nine files, 1 report, the `while` of WSP-IN-04. Selftest: 1299 of 1299 planted mistakes of 60 kinds. `ruff check` passes.
- **Limit:** I kept no copy of the round 1 file, so "existing tests unchanged" rests on the rebuild of all 74 against their cards, not on a line diff.

### Commands run
```
drive.py vars <module> (and --plan seq, --plan idx)                 149 variants, all reached all 74 tests
r2check.py                                                gap variants against their cards
drive.py bases <module>                                   as under Reproduced
repro.py <module>                                         as under Reproduced
rebuild.py; rebuild.py --selftest 6                       252 cards, 1 report; 1299 of 1299
.venv/Scripts/python.exe -m ruff check <the eight test files>     All checks passed!
git diff --stat -- app/dao                                (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\`. Only this report was edited in the repo. Nothing was stopped or killed.
