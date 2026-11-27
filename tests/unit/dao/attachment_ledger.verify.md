# Verification — `app/dao/attachment_ledger.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 73 cases). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 47 passed · 9 xfail, 7 strict, 2 non-strict (reproduced ✅) · coverage 100% branch (21 statements, 10 branches, 0 missed)
> Mutation: 17 mutants · 17 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 56 unfaithful** (56 / 56 right)
> Hand variants: 115 · 79 caught by a pass card · 36 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** Read fully by eye against every card: all 56 match, and my script agrees.
- **Why NEEDS WORK:** 17 of 17 sites killed, but hand variants show five gaps for the case designer, the largest R3 and R4's exact compare. ATL-G-42 needs a new Given, not only a new parenthesis.
- No money, stock or order state.
- **Ruling on the executor's point:** ATL-G-42: the `Fails today on` parenthesis is backwards, as the executor says; the card also needs the higher id updated (Finding 6).

Written by Claude (all 56 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 56. No `attachment_ledger.local-run.json` exists, so there is no `## Local-coder patterns` section. Read fully by eye.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | R3 "exact matches, case-sensitive" (skill 1b exact compare) | Arguments tried: another case, unknown, `""`. No part of the value, no `_` or `%`, no leading or trailing space; stored side: no capitals, no spaces, no longer value. | `r3_like`, `r3_contains`, `r3_contains_raw`, `r3_startswith`, `r3_endswith`, `r3_lower_col`, `r3_strip_arg`, `r3_lstrip_arg`, `r3_trim_col`, `r3_ltrim_col` pass all 47 on all three plans. | case designer |
| 2 | case-missing | R4, the same for `transaction_type` | As above. | the same ten `r4_*` pass all 47. | case designer |
| 3 | case-missing | R2 `attachment_id` | ATL-G-05 filters on the lower id with a decoy on the higher one, so `attachment_id <= arg` passes. | `r2_le` passes all 47. | case designer |
| 4 | case-missing | Side effects: none (skill 1b) | ATL-G-56 checks a pending row only. | the five `g_w_*` pass all 47. | case designer |
| 5 | case-missing | skill 1b real states, R13; cases Spec gap 1 | ATD lacks `deleted_by`. `AttachmentDAO.soft_delete` writes `is_deleted`, `deleted_at`, `deleted_by` (app/dao/attachment.py:70), which answers Spec gap 1. No variant survives today (ATL-G-56 forbids `attachments`). | scratch `test_r9_real_close` passes. | case designer |
| 6 | case-missing | ATL-G-42 (ruling on the executor's point) | The executor is right that the parenthesis is backwards: in this descending list the updated lower id coming second is the intended `[B, A]`. Worse, that is why the card almost never fails: XPASS 5/5 default, 5/5 index-off, 4/5 sequential-off. Updating the **higher** id puts it after A in the heap, and the card then fails today on all three plans and passes on the reference. | `res/nonstrict.json`; scratch `test_r7_tie_higher_id_updated`. | case designer |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\prop\test_prop_attachment_ledger.py`, not in the repo. Each passes on today's code (a non-strict xfail recipe may fail today) and on the reference, on all three plans. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | cards on R3, argument side | A = entry, `performed_at H10` (entity `purchase_order`). When `entity_type=` `"PURCHASE_ORDER"`, `" purchase_order"`, `"purchase_order "`, `"purchase"`, `"order"`, `"purchase%"`, `"purchase_orde_"` | `result == []` | pass | all ten `r3_*` with R-2 |
| R-2 | cards on R3, stored side | A = entry, `performed_at H10`, but `entity_type` `"PURCHASE_ORDER"`, `" purchase_order"`, `"purchase_order "`, `"purchase_orderX"`, `"Xpurchase_order"`, `"purchaseXorder"`. When `entity_type="purchase_order"` | `result == []` | pass | `r3_lower_col`, `r3_trim_col`, `r3_ltrim_col`, `r3_like`, `r3_contains*`, `r3_*with` |
| R-3 | the same two shapes for R4 | with `"ready"`: arguments `"READY"`, `" ready"`, `"rea"`, `"dy"`, `"rea%"`, `"r_ady"`, `"ready "`; stored `"READY"`, `" ready"`, `"ready "`, `"readyX"`, `"Xready"`; and stored `"pendingX"` asked as `"pending_"` | `result == []` | pass | all ten `r4_*` |
| R-4 | new card, R2 | A = entry, `performed_at H11`, but `attachment_id AT2.id`; B = entry, `performed_at H12`. When `attachment_id=AT2.id` | `ids(result) == [A.id]` | pass | `r2_le` |
| R-5 | new card, Side effects | A = entry, `performed_at H10`; B = entry, `performed_at H11`; `B.file_name = "edited.png"`, not flushed. When `get_by_workspace(workspace_id=W1.id, skip=1, limit=1)` | `ids(result) == [A.id]`; `session: B in db.dirty`; `session: len(db.dirty) == 1` | pass | the five `g_w_*` |
| R-6 | Conventions | ATD = the same as AT1, but `is_deleted True`, `deleted_at T12`, `deleted_by U1.id` | ATL-G-55 unchanged | pass | (shape) |
| R-7 | ATL-G-42 Given 3 | `B.file_size = 200`, then `db.flush()` (the higher id), instead of A; Fails line: "Then 2 (the updated higher id moves after A in the heap)" | unchanged | xfail BUG-640 (non-strict) | fails today on all three plans; `r8_id_asc`, `r8_no_tail`, `r8_name_desc_tail` |

## Surviving mutants
None. All 17 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 17 mutants with no `-x`: every run reached all 47 pass tests, with no collection or setup error.

## Hand variants
`variants.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv`, on the reference (`order_by(desc(performed_at), desc(id))`; a naive bound gets `tzinfo=UTC`), with `--runxfail`, on three plans: default, sequential scans off, index and bitmap scans off. Every edit was asserted to apply once and every run reached all 56 tests with no error. Group names: the rule, `w` session side effects, `txt` text compare, `page` paging, `ret` return shape, `ov` parent state.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| r1 | 3 | 3 | ATL-G-02, ATL-G-03, ATL-G-04, ATL-G-08 | — |
| r2 | 5 | 4 | ATL-G-02, ATL-G-03, ATL-G-04, ATL-G-05, ATL-G-06, ATL-G-08 … | `r2_le` |
| r3 | 4 | 4 | ATL-G-09, ATL-G-10, ATL-G-11, ATL-G-12, ATL-G-13, ATL-G-53 … | — |
| r4 | 2 | 2 | ATL-G-14, ATL-G-16, ATL-G-17, ATL-G-18, ATL-G-53, ATL-G-54 | — |
| r5 | 6 | 4 | ATL-G-19, ATL-G-21, ATL-G-23, ATL-G-24, ATL-G-28, ATL-G-29 … | `r5_trunc_s`, `r5_truthy` |
| r6 | 8 | 7 | ATL-G-19, ATL-G-20, ATL-G-21, ATL-G-22, ATL-G-23, ATL-G-24 … | `r6_truthy` |
| r7 | 4 | 4 | ATL-G-19, ATL-G-20, ATL-G-21, ATL-G-23, ATL-G-24, ATL-G-25 … | — |
| r7a | 4 | 2 | ATL-G-31, ATL-G-34 | `r7a_today_s`, `r7a_today_e` |
| r8 | 5 | 5 | ATL-G-01, ATL-G-07, ATL-G-10, ATL-G-11, ATL-G-15, ATL-G-16 … | — |
| r8t | 4 | 0 | — | `r8_no_tail`, `r8_id_asc`, `r8_name_tail`, `r8_name_desc_tail` |
| r9 | 4 | 4 | ATL-G-01, ATL-G-02, ATL-G-05, ATL-G-07, ATL-G-09, ATL-G-10 … | — |
| r13 | 6 | 6 | ATL-G-55, ATL-G-56 | — |
| r3_txt | 14 | 4 | ATL-G-12 | `r3_like`, `r3_contains`, `r3_contains_raw`, `r3_startswith`, `r3_endswith`, `r3_lower_col`, `r3_strip_arg`, `r3_lstrip_arg`, `r3_trim_col`, `r3_ltrim_col` |
| r4_txt | 14 | 4 | ATL-G-17 | `r4_like`, `r4_contains`, `r4_contains_raw`, `r4_startswith`, `r4_endswith`, `r4_lower_col`, `r4_strip_arg`, `r4_lstrip_arg`, `r4_trim_col`, `r4_ltrim_col` |
| p_page | 16 | 15 | ATL-G-01, ATL-G-02, ATL-G-05, ATL-G-07, ATL-G-09, ATL-G-10 … | `p_lim_cap500` |
| g_ret | 4 | 4 | ATL-G-01, ATL-G-03, ATL-G-04, ATL-G-06, ATL-G-07, ATL-G-08 … | — |
| g_w | 12 | 7 | ATL-G-56 | `g_w_expire`, `g_w_expire_post`, `g_w_dirty_refresh`, `g_w_dirty_flush`, `g_w_dirty_expire` |
| **Total** | **115** | **79** |  | **36** |

With the recipes added, 109 of 115 are caught; the rest are below.

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `r5_truthy`, `r6_truthy` | **Equivalent:** a `datetime` is always true. |
| `r5_trunc_s` | Truncating the column to the second on the start bound only; caught on the end bound by ATL-G-20. A contrived edit, not a rule gap. |
| `r7a_today_s`, `r7a_today_e` | **Bug path** (BUG-1281): each fails three strict cards. |
| `r8_name_tail` | **Bug path** (BUG-640): fails the strict ATL-G-44. |
| `p_lim_cap500` | A cap above the card's own 105 rows; `cap100`, `cap101`, `cap103`, `cap104` are caught. |

## xfail tests against the reference
Reference: `order_by(desc(performed_at), desc(id))`; a naive bound gets `tzinfo=UTC`, swapped in memory. Nothing is written to `app/`. With `--runxfail` on the reference: 56 passed. **The alarm works:** with the markers on, every strict card goes `XPASS(strict)`.

| Card | Marker | Card's Fails line | Seen |
|---|---|---|---|
| ATL-G-32 | strict | Then 1 | fails on Then 1 in 3 of 3 `--runxfail` runs, as the card says |
| ATL-G-33 | strict | Then 1 | fails on Then 1 in 3 of 3 `--runxfail` runs, as the card says |
| ATL-G-35 | strict | Then 1 | fails on Then 1 in 3 of 3 `--runxfail` runs, as the card says |
| ATL-G-36 | strict | Then 1 | fails on Then 1 in 3 of 3 `--runxfail` runs, as the card says |
| ATL-G-37 | strict | Then 1 | fails on Then 1 in 3 of 3 `--runxfail` runs, as the card says |
| ATL-G-38 | strict | Then 1 | fails on Then 1 in 3 of 3 `--runxfail` runs, as the card says |
| ATL-G-42 | non-strict | Then 2 | default: XPASS 5; idx: XPASS 5; seq: XFAIL 1, XPASS 4; fails on Then 2 when it fails, also under wrong tie orders |
| ATL-G-43 | non-strict | Then 2 | default: XPASS 5; idx: XFAIL 5; seq: XFAIL 1, XPASS 4; fails on Then 2 when it fails, also under wrong tie orders |
| ATL-G-44 | strict | Then 3 | fails on Then 3 in 3 of 3 `--runxfail` runs, as the card says |

## Reproduced claims
- Coverage run: `47 passed, 8 xfailed, 1 xpassed in 5.36s`; `app\dao\attachment_ledger.py      21      0     10      0   100%`. Four more default runs: `47 passed, 8 xfailed, 1 xpassed in 2.80s`, `47 passed, 7 xfailed, 2 xpassed in 2.74s`, `47 passed, 7 xfailed, 2 xpassed in 2.76s`, `47 passed, 7 xfailed, 2 xpassed in 2.94s`.
- `--runxfail -rf`: `7 failed, 49 passed in 2.64s`; failed: ATL-G-32, ATL-G-33, ATL-G-35, ATL-G-36, ATL-G-37, ATL-G-38, ATL-G-44.
- 15 more runs (5 per plan): 47 passed in every run, no pass card or strict card moved. **No flaky test.** Only non-strict cards move between XFAIL and XPASS, which their markers allow; the notes' sample default line is one heap's result.
- **Mocks:** none. No `try`, no `if`, no broad `pytest.raises` in a test body.

## Traceability
cases 56 · tests 56 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md` and each reason carries the row's title. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script (`rebuild.py`) rebuilt each test's Given, snapshots, When, Then and marker from its card, and the constants, standing rows, builders and helpers from the Conventions, and compared by AST, for all 302 cards of the batch: 0 reports. Selftest (`selftest.py`, 3 seeds): 9306 of 9306 planted mistakes of 81 kinds, in tests, helpers and cards, reported on the right card.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents were live on `marker_test`. Every kill is a plain `N failed` with all tests reached.
- **No DDL.** The one schema question (PBL-G-14) was answered with `SET LOCAL session_replication_role = replica` inside a rolled-back test, which switches foreign-key actions off without a lock.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/attachment_ledger.py tests/unit/dao/test_attachment_ledger.py --timeout 300 --json <scratch>/res/mut_attachment_ledger.json   (through runmut.py, TEMP in scratch)
  17 mutants · 17 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_attachment_ledger.py -q -p no:cacheprovider --cov=app.dao.attachment_ledger --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  47 passed, 8 xfailed, 1 xpassed in 5.36s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_attachment_ledger.py -q -p no:cacheprovider --runxfail -rf
  7 failed, 49 passed in 2.64s
repro.py; nonstrict.py (5 runs x 3 plans); thenloc.py                as under Reproduced
drive.py bases | muts | vars --plan default|seq|idx                     as above
propdrive.py (3 plans)                                                  recipes as in the table
rebuild.py; selftest.py 7|21|33                                         302 cards, 0 reports; 9306 of 9306
.venv/Scripts/python.exe -m ruff check <the eleven test files>         All checks passed!
git diff --stat -- app/dao                                              (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add the recipes above; the Givens and Thens are written out. Fix the parenthesis named in the ruling.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 64 passed · 9 xfail, 7 strict, 2 non-strict (reproduced ✅) · coverage as round 1
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 73 unfaithful** (new and changed cards read by eye; all 73 rebuilt by script)
> Hand variants: 115 · 105 caught by a pass card · every round-1 gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1

Every finding of round 1 is closed. No new rule gap. No test edited, no commit. Nothing parked for the owner.

### New and changed tests
ATL-G-57 … ATL-G-73; ATD's Conventions and ATL-G-55's Given; ATL-G-42 rewritten. Each was read against its card. "Fails" means the variant fails that card on the reference with `--runxfail`, on all three plans.

| Card | Recipe | Fails |
|---|---|---|
| ATL-G-57 … G-63 | R-1, R-2 | all ten `r3_*` text variants |
| ATL-G-64 … G-71 | R-3 | all ten `r4_*` text variants |
| ATL-G-72 | R-4 | `r2_le` |
| ATL-G-73 | R-5 | the five `g_w_*` |
| ATD | R-6 | shape; `atd` fixture equals the Conventions |
| ATL-G-42 | R-7, non-strict | `r8_id_asc`, `r8_name_desc_tail` on all three plans; today XFAIL 5/5 default and index-off, 1/5 sequential-off |

### Rest of the batch
All 115 variants ran again on the reference, each reaching all 73 tests, on all three plans. Left without a pass card: `p_lim_cap500`, `r5_trunc_s`, `r5_truthy`, `r6_truthy`, `r7a_today_e`, `r7a_today_s`, `r8_id_asc`, `r8_name_desc_tail`, `r8_name_tail`, `r8_no_tail`. Each is under round 1's "Considered and not listed" (bug path, a cap above the card's own rows, or equivalent); none is a new rule gap.

### Reproduced
- Coverage run: `64 passed, 9 xfailed in 5.63s`; `['app\\dao\\attachment_ledger.py      21      0     10      0   100%']`. Four more default runs: `64 passed, 9 xfailed in 3.06s`, `64 passed, 9 xfailed in 2.83s`, `64 passed, 9 xfailed in 2.95s`, `64 passed, 9 xfailed in 2.86s`.
- `--runxfail`: `9 failed, 64 passed in 2.75s ['atl_g_32', 'atl_g_33', 'atl_g_35', 'atl_g_36', 'atl_g_37', 'atl_g_38', 'atl_g_42', 'atl_g_43', 'atl_g_44']`. Every strict card fails on its card's `Fails today on` line.
- 15 more runs (5 per plan): 64 passed in every run; only non-strict cards move. No flaky test.
- Traceability: cases 73 · tests 73 · unmatched: none · marker mismatches: none. `rebuild.py`: 361 cards over the eleven files, 0 reports (it learned the new `where` name of `mobile_upload_session`). Selftest: 9306 of 9306 planted mistakes, 3 seeds. `ruff check` passes.
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
