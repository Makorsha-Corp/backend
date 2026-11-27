# Verification — `app/dao/invoice_item.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 43 cases). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work, plus one money question for the describer and owner. No test is wrong.
> Tests: 34 passed · 3 xfail, 1 strict, 2 non-strict (reproduced ✅) · coverage 100% branch (13 statements, 0 branches, 0 missed)
> Mutation: 8 mutants · 8 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 37 unfaithful** (37 / 37 right)
> Hand variants: 85 · 62 caught by a pass card · 23 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** Read fully by eye against every card: all 37 match, and my script agrees.
- **Why NEEDS WORK:** 8 of 8 sites killed, but hand variants show 3 rule gaps for the case designer and one money question for the describer and owner.
- **Money: `delete_all_for_invoice` deletes the lines behind the invoice total. One open question for the owner (Finding 4); it is the cases file's own Spec gap 1.**

Written by Claude (all 37 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 37. No `invoice_item.local-run.json` exists, so there is no `## Local-coder patterns` section. Read fully by eye.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_id_and_workspace` R1, another workspace | II-GW-02 keeps both rows in W1 and asks W2, so a wrong `>=` on `workspace_id` or on `id` finds nothing there. The row of the other workspace must be the earlier id. | `gw_r1_ws_ge`, `gw_r1_id_ge` pass all 34 on all three plans. | case designer |
| 2 | case-missing | Overview "does not look at the invoice's status"; skill 1b: a reader does not join its parent | II-GI-19 and II-GI-20 hold this for `get_by_invoice` only. Nothing holds it for `get_by_id_and_workspace`: no confirmed invoice, no `"account_invoices" not in sql`. | `gw_ov_join`, `gw_ov_draft`, `gw_ov_draft_join` pass all 34. | case designer |
| 3 | case-missing | both readers, Side effects: none (skill 1b) | II-GI-20 and II-GW-04 check a pending row only. A read that drops the caller's unflushed edit, or flushes it, passes. | `gi_w_expire`, `gi_w_expire_post`, `gi_w_dirty_refresh`, `gi_w_dirty_flush`, `gi_w_dirty_expire` and the five `gw_w_*` pass all 34. | case designer |
| 4 | spec-gap (money) | `delete_all_for_invoice` R1, R5 | A line of this same invoice added and not flushed: today the `DELETE` runs first and the method's flush then stores the line, so it survives. A flush before the delete removes it. No rule says which is intended (cases Spec gap 1). | `da_r5_flush_first` passes all 34. Today's behaviour read from the source and the run. | describer, owner |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv\prop\test_prop_invoice_item.py`, not in the repo. Each passes on today's code (a non-strict xfail recipe may fail today) and on the reference, on all three plans. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, GW R1 | Z = line, `line_number 1`, but `workspace_id W2.id`, `invoice_id IN9.id`; then A = line, `line_number 2`. When `get_by_id_and_workspace(id=Z.id, workspace_id=W1.id)` | `result is None` | pass | `gw_r1_ws_ge`, `gw_r1_id_ge` |
| R-2 | new card, GW Overview | A = line, `line_number 1`, but `invoice_id INC.id`; a recorder. When `get_by_id_and_workspace(id=A.id, workspace_id=W1.id)` | `result.id == A.id`; `statement: "account_invoices" not in sql` | pass | `gw_ov_join`, `gw_ov_draft`, `gw_ov_draft_join` |
| R-3 | new card, GI Side effects | A = line, `line_number 1`; B = line, `line_number 1`, but `invoice_id IN2.id`; `B.description = "Edited"`, not flushed. When `get_by_invoice(invoice_id=IN1.id, workspace_id=W1.id)` | `ids(result) == [A.id]`; `session: B in db.dirty`; `session: len(db.dirty) == 1` | pass | the five `gi_w_*` |
| R-4 | new card, GW Side effects | A = line, `line_number 1`; B = line, `line_number 2`; `B.description = "Edited"`, not flushed. When `get_by_id_and_workspace(id=A.id, workspace_id=W1.id)` | `result.id == A.id`; `session: B in db.dirty`; `session: len(db.dirty) == 1` | pass | the five `gw_w_*` |

## Surviving mutants
None. All 8 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 8 mutants with no `-x`: every run reached all 34 pass tests, with no collection or setup error.

## Hand variants
`variants.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childv`, on the reference (`order_by(line_number, id)` in `get_by_invoice`), with `--runxfail`, on three plans: default, sequential scans off, index and bitmap scans off. Every edit was asserted to apply once and every run reached all 37 tests with no error. Group names: the rule, `w` session side effects, `txt` text compare, `page` paging, `ret` return shape, `ov` parent state.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| gi_r1 | 3 | 3 | II-GI-02, II-GI-07, II-GI-08, II-GI-09 | — |
| gi_r2 | 5 | 5 | II-GI-02, II-GI-03, II-GI-04, II-GI-05, II-GI-06, II-GI-07 … | — |
| gi_ov | 2 | 2 | II-GI-19, II-GI-20 | — |
| gi_r6 | 3 | 1 | II-GI-17 | `gi_r6_cap_101`, `gi_r6_cap_1000` |
| gi_ret | 4 | 4 | II-DA-12, II-GI-01, II-GI-03, II-GI-04, II-GI-07, II-GI-08 … | — |
| gi_r4 | 6 | 6 | II-GI-01, II-GI-11, II-GI-12, II-GI-13, II-GI-17 | — |
| gi_r5 | 4 | 0 | — | `gi_r5_no_tail`, `gi_r5_id_desc`, `gi_r5_desc_tail`, `gi_r5_sub_tail` |
| gi_r7 | 1 | 1 | II-GI-18 | — |
| gi_w | 12 | 7 | II-GI-10, II-GI-20 | `gi_w_expire`, `gi_w_expire_post`, `gi_w_dirty_refresh`, `gi_w_dirty_flush`, `gi_w_dirty_expire` |
| gw_r1 | 8 | 5 | II-DA-13, II-GW-01, II-GW-02, II-GW-03 | `gw_r1_ws_ge`, `gw_r1_id_ge`, `gw_r1_one_or_none` |
| gw_ov | 3 | 0 | — | `gw_ov_join`, `gw_ov_draft`, `gw_ov_draft_join` |
| gw_ret | 1 | 1 | II-GW-01, II-GW-04 | — |
| gw_w | 12 | 7 | II-GW-04 | `gw_w_expire`, `gw_w_expire_post`, `gw_w_dirty_refresh`, `gw_w_dirty_flush`, `gw_w_dirty_expire` |
| da_r1 | 3 | 3 | II-DA-01, II-DA-02, II-DA-03, II-DA-04, II-DA-05, II-DA-06 … | — |
| da_r2 | 2 | 2 | II-DA-03, II-DA-10 | — |
| da_r3 | 2 | 2 | II-DA-04, II-DA-05, II-DA-06 | — |
| da_r4 | 3 | 3 | II-DA-07, II-DA-10 | — |
| da_r5 | 3 | 2 | II-DA-08, II-DA-09, II-DA-11 | `da_r5_flush_first` |
| da_r6 | 3 | 3 | II-DA-11 | — |
| da_s | 5 | 5 | II-DA-01, II-DA-02, II-DA-03, II-DA-04, II-DA-05, II-DA-06 … | — |
| **Total** | **85** | **62** |  | **23** |

With the recipes added, 77 of 85 are caught; the rest are below.

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `gi_r6_cap_101`, `gi_r6_cap_1000` | A cap above the card's own 101 rows. `gi_r6_cap_100` is caught. |
| `gi_r5_no_tail`, `gi_r5_id_desc`, `gi_r5_desc_tail`, `gi_r5_sub_tail` | **Bug path** (BUG-638): each fails II-GI-16 (strict) and II-GI-14/15 on at least one plan. |
| `gw_r1_one_or_none` | **Equivalent:** the primary key leaves one row. |

## xfail tests against the reference
Reference: `order_by(line_number, id)` in `get_by_invoice`, swapped in memory. Nothing is written to `app/`. With `--runxfail` on the reference: 37 passed. **The alarm works:** with the markers on, every strict card goes `XPASS(strict)`.

| Card | Marker | Card's Fails line | Seen |
|---|---|---|---|
| II-GI-14 | non-strict | Then 2 | default: XFAIL 5; idx: XFAIL 5; seq: XPASS 1, XFAIL 4; fails on Then 2 when it fails, also under wrong tie orders |
| II-GI-15 | non-strict | Then 2 | default: XPASS 5; idx: XPASS 5; seq: XPASS 5; fails on Then 2 when it fails, also under wrong tie orders |
| II-GI-16 | strict | Then 4 | fails on Then 4 in 3 of 3 `--runxfail` runs, as the card says |

## Reproduced claims
- Coverage run: `34 passed, 2 xfailed, 1 xpassed in 4.91s`; `app\dao\invoice_item.py      13      0      0      0   100%`. Four more default runs: `34 passed, 2 xfailed, 1 xpassed in 2.77s`, `34 passed, 2 xfailed, 1 xpassed in 2.74s`, `34 passed, 2 xfailed, 1 xpassed in 2.80s`, `34 passed, 2 xfailed, 1 xpassed in 2.77s`.
- `--runxfail -rf`: `2 failed, 35 passed in 2.64s`; failed: II-GI-14, II-GI-16.
- 15 more runs (5 per plan): 34 passed in every run, no pass card or strict card moved. **No flaky test.** Only non-strict cards move between XFAIL and XPASS, which their markers allow; the notes' sample default line is one heap's result.
- **Mocks:** one `db.commit` spy (II-DA-08), the Conventions' own `rolled back`. No `try`, no `if`, no broad `pytest.raises` in a test body.

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
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/invoice_item.py tests/unit/dao/test_invoice_item.py --timeout 300 --json <scratch>/res/mut_invoice_item.json   (through runmut.py, TEMP in scratch)
  8 mutants · 8 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_invoice_item.py -q -p no:cacheprovider --cov=app.dao.invoice_item --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  34 passed, 2 xfailed, 1 xpassed in 4.91s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_invoice_item.py -q -p no:cacheprovider --runxfail -rf
  2 failed, 35 passed in 2.64s
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
2. **Describer, with the owner (money):** decide Finding 4, then the case designer adds its card.
3. **Executor,** after 1: implement them and send back for re-verification.

Note: BUG-638's row in `docs/testing/bugs.md` names `account_invoice_manager.py` as the file; the spec puts the fix in this DAO. The row's intended text (ties by item `id` ascending) agrees with R5; only the file column differs (cases Spec gap 2). Worth one word in the row when the bug is fixed.

## Round 2 — 2026-11-03 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 39 passed · 4 xfail, 2 strict, 2 non-strict (reproduced ✅) · coverage as round 1
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 43 unfaithful** (new and changed cards read by eye; all 43 rebuilt by script)
> Hand variants: 87 · 78 caught by a pass card · every round-1 gap variant fails its new card
> Source commit: e48a092 · Cases revision: 1

Every finding of round 1 is closed. No new rule gap. No test edited, no commit. The money question of round 1 is answered by the owner (BUG-1283, `delete_all_for_invoice` R7); nothing new to park.

### New and changed tests
II-GW-05, II-GW-06, II-GW-07, II-GI-21, II-DA-14, II-DA-15. Each was read against its card. "Fails" means the variant fails that card on the reference with `--runxfail`, on all three plans.

| Card | Recipe | Fails |
|---|---|---|
| II-GW-05 | R-1 | `gw_r1_ws_ge`, `gw_r1_id_ge` |
| II-GW-06 | R-2 | `gw_ov_join`, `gw_ov_draft`, `gw_ov_draft_join` |
| II-GI-21 | R-3 | the five `gi_w_*` |
| II-GW-07 | R-4 | the five `gw_w_*` |
| II-DA-14 | R7 [BUG-1283], strict | `da_r7_today` (today's order: delete, then flush); fails on Then 2 as the card says |
| II-DA-15 | R7 | `da_r5_noflush`, `da_r7_expunge_new` |

**Reference updated for R7:** `db.flush()` moved before the bulk `DELETE`. With it, 43 passed under `--runxfail`; with the markers on, the two strict cards (II-GI-16, II-DA-14) go `XPASS(strict)`. `da_r7_flush_both` (flush, delete, flush) is equivalent to the reference: the second flush has nothing left to write.

### Rest of the batch
All 87 variants ran again on the reference, each reaching all 43 tests, on all three plans. Left without a pass card: `da_r7_flush_both`, `da_r7_today`, `gi_r5_desc_tail`, `gi_r5_id_desc`, `gi_r5_no_tail`, `gi_r5_sub_tail`, `gi_r6_cap_1000`, `gi_r6_cap_101`, `gw_r1_one_or_none`. Each is under round 1's "Considered and not listed" (bug path, a cap above the card's own rows, or equivalent); none is a new rule gap.

### Reproduced
- Coverage run: `39 passed, 3 xfailed, 1 xpassed in 5.13s`; `['app\\dao\\invoice_item.py      13      0      0      0   100%']`. Four more default runs: `39 passed, 3 xfailed, 1 xpassed in 2.74s`, `39 passed, 3 xfailed, 1 xpassed in 2.79s`, `39 passed, 3 xfailed, 1 xpassed in 2.66s`, `39 passed, 3 xfailed, 1 xpassed in 2.81s`.
- `--runxfail`: `3 failed, 40 passed in 2.70s ['ii_gi_14', 'ii_gi_16', 'ii_da_14']`. Every strict card fails on its card's `Fails today on` line.
- 15 more runs (5 per plan): 39 passed in every run; only non-strict cards move. No flaky test.
- Traceability: cases 43 · tests 43 · unmatched: none · marker mismatches: none. `rebuild.py`: 361 cards over the eleven files, 0 reports (it learned the new `where` name of `mobile_upload_session`). Selftest: 9306 of 9306 planted mistakes, 3 seeds. `ruff check` passes.
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
