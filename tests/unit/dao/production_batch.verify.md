# Verification — `app/dao/production_batch.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 179 passed · 38 xfail (29 strict, 9 non-strict) (reproduced ✅) · coverage 95% branch (36 statements, 6 branches; line 166 and branch 216→220 missed: dead `get_by_date_range` and the dead `year` parameter)
> Mutation: 51 mutants · 45 killed · 6 survived → score 100% (after excluding 0 equivalent, 6 dead, 0 bug-path)
> Fidelity: **0 of 217 unfaithful** (217 / 217 read by eye against their cards; my script agrees)
> Hand variants: 215 · 165 caught by a pass card · 33 bug path · 17 others: 4 rule gaps (10 variants) in Findings, 7 under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** I read every card and test by eye, and my comparator agrees: no difference. The helpers match the Conventions:
  - the standing rows and their order;
  - FD's columns, which equal what `FactoryDAO.soft_delete` writes;
  - `clocks()`, which patches the module's `datetime.now` and `utcnow` only;
  - the recorder.
- **Why NEEDS WORK:** 4 rule gaps, all for the case designer, with Givens and Thens below:
  - Another workspace's row ahead of the page, in all four lists.
  - The other direction of the workspace check, for `get_by_formula`, `get_by_status` and `generate_batch_number`.
  - Stored-side exact compare in `count_by_status`.
- **Unordered queries have their alarms.** The four lists order by `batch_date DESC` alone (BUG-1321). Each has a strict SQL card: GW-13, GL-15, GF-14 and GS-22. The nine tie cards are non-strict, and none passed today in my runs. Every ordered pass card uses distinct dates, which I checked by script.
  - `generate_batch_number` orders by a unique number.
  - `get_by_date_range` is dead (P1).
  - `count_by_status` and `get_by_id_and_workspace` need no order.
- **Stock and order-workflow:** no new question. The stock items are Deferred to `ProductionBatchManager`, as the cases say:
  - FU-1 (c): two starts take the inputs twice.
  - (d): a cancel does not return them.
  - (e): a lost number race gives a 500.
  - (h): an overflow leaves stock half posted.
  - BUG-1331: `delete_factory` should refuse while batches are open.

Written by Claude (all 217 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 217. No local-run file exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_workspace` R1, `get_by_production_line` R1, `get_by_formula` R1, `get_by_status` R1 (step 1b "filter before paging") | The line, formula, status and BUG-1330 filters have paged cards. No card has another workspace's batch ahead of the skipped row. | `gw_`, `gl_`, `gf_`, `gs_r1_ws_after_page` each pass all 217 on all three plans. | **case designer** |
| 2 | case-missing | `get_by_formula` R1 (step 1b, both sides) | GF-04 asks W2 for a W1 batch. No card has a W2 batch on PF1 while W1 asks, so `>=` on `workspace_id` passes. | `gf_r1_ge` passes all 217. | **case designer** |
| 3 | case-missing | `get_by_status` R1 and `generate_batch_number` R4 (step 1b, both sides) | GS-02 and GN-13 put the other workspace's row in W2 and ask W1. Nothing asks W2 while the row is in W1, so `<=` passes. | `gs_r1_le`, `gn_r4_le` pass all 217. | **case designer** |
| 4 | case-missing | `count_by_status` R1/R3 "the status is compared exactly" (step 1b "exact compare, both sides") | CS-15 has the argument `"in-progress"` against a stored `"in_progress"`. No stored-side card exists: capitals, a leading space, or a longer value. `get_by_status` has them (GS-11 to GS-20). | `cs_r1s_lower_col`, `cs_r1s_trim_col`, `cs_r1s_endswith` pass all 217. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
These are in `...\prodv\prop\test_prop_production_batch.py`. Each one passes on today's code and on my reference, on three plans, and fails under its variant.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1a | new card, GW R1 | Z = batch, `batch_number "B-Z"`, `batch_date D5`, `workspace_id W2.id`, `production_line_id L9.id`; A = batch, `batch_number "B-A"`, `batch_date D4`; B = batch, `batch_number "B-B"`, `batch_date D3`. When `dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)` | `ids(result) == [B.id]` | pass | `gw_r1_ws_after_page` |
| R-1b | new card, GL R1 | Z = batch, `batch_number "B-Z"`, `batch_date D5`, `workspace_id W2.id` (on L1); A and B as R-1a. When `dao.get_by_production_line(db, production_line_id=L1.id, workspace_id=W1.id, skip=1, limit=1)` | `ids(result) == [B.id]` | pass | `gl_r1_ws_after_page` |
| R-1c | new card, GF R1 | as R-1a, every row with `formula_id PF1.id`. When `dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id, skip=1, limit=1)` | `ids(result) == [B.id]` | pass | `gf_r1_ws_after_page` |
| R-1d | new card, GS R1 | as R-1a (all `draft`). When `dao.get_by_status(db, status="draft", workspace_id=W1.id, skip=1, limit=1)` | `ids(result) == [B.id]` | pass | `gs_r1_ws_after_page` |
| R-2 | new card, GF R1 | Z = batch, `batch_number "B-Z"`, `batch_date D5`, `workspace_id W2.id`, `production_line_id L9.id`, `formula_id PF1.id`. When `dao.get_by_formula(db, formula_id=PF1.id, workspace_id=W1.id)` | `result == []` | pass | `gf_r1_ge` |
| R-3a | new card, GS R1 | A = batch, `batch_number "B-A"`, `batch_date D5`. When `dao.get_by_status(db, status="draft", workspace_id=W2.id)` | `result == []` | pass | `gs_r1_le` |
| R-3b | new card, GN R4 | A = batch, `batch_number "BATCH-2026-007"`; clocks(CK, CK). When `dao.generate_batch_number(db, workspace_id=W2.id)` | `result == "BATCH-2026-001"` | pass | `gn_r4_le` |
| R-4 | three new cards, CS R1 | A = batch, `batch_number "B-A"`, but `status` `"IN_PROGRESS"` / `" in_progress"` / `"not_in_progress"` (one per card). When `dao.count_by_status(db, workspace_id=W1.id, status="in_progress")` | `result == 0` | pass | `cs_r1s_lower_col` / `cs_r1s_trim_col` / `cs_r1s_endswith` |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 7 | 166 | `return` → `return None` | dead | `get_by_date_range`: spec P1, "Not specified", dead-code checklist `app/dao/production_batch.py:148` | — |
| 22 | 150 | `skip=0` → `1` | dead | same method's default | — |
| 23 | 150 | `limit=100` → `101` | dead | same method's default | — |
| 49 | 169 | `workspace_id ==` → `!=` | dead | same method | — |
| 50 | 170 | `>=` → `>` | dead | same method | — |
| 51 | 171 | `<=` → `<` | dead | same method | — |

**Guard.** My driver ran each of the 51 mutants again without `-x`. Every run reached all 179 pass tests, with no collection or setup error, and the sets were the same as `mutate.py`'s.

## Hand variants
These ran on my reference with `--runxfail`. Every candidate was run again on the sequential-off and index-off plans, with no change. Each edit applied exactly once, and every run reached all 217 tests.

| Group | Variants | Pass card | Others |
|---|---|---|---|
| gw (workspace, line / formula raw, BUG-1330, order, paging, writes) | 33 | 24 | 7 bug path; `gw_r1_ws_after_page`; `gw_pg_cap101` |
| gl (the same, plus the line key) | 36 | 26 | 6 bug path; `gl_r1_ws_after_page`; `gl_r2_hide_formula`; `gl_r2a_after_page`; `gl_pg_cap101` |
| gf (the same, plus the formula key, no-formula rows) | 37 | 26 | 7 bug path; `gf_r1_ge`; `gf_r1_ws_after_page`; `gf_r2_hide_line`; `gf_pg_cap101` |
| gs (the same, plus 13 exact-status variants) | 46 | 36 | 7 bug path; `gs_r1_le`; `gs_r1_ws_after_page`; `gs_pg_cap101` |
| cs (`count_by_status`: workspace, status compare, factory filter, `0` and `None`, line raw, BUG-1330, row's own workspace, writes) | 31 | 26 | 2 bug path (CS-18 to CS-20); `cs_r1s_lower_col`, `cs_r1s_trim_col`, `cs_r1s_endswith` |
| gi (by id) | 11 | 11 | — |
| gn (`generate_batch_number`: prefix, padding, +1, workspace, year, cancelled count, deleted factory counts, writes) | 21 | 16 | 4 bug path (BUG-1334 GN-03 and GN-04, BUG-1333 GN-19 to GN-22 and GN-25 to GN-28); `gn_r4_le` |
| **Total** | **215** | **165** | **50** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `gw_`, `gl_`, `gf_`, `gs_pg_cap101` | A cap above the cards' own 101 rows. The cap100 variants are caught. |
| `gl_r2a_after_page` | **Equivalent:** every batch of one line shares that line's factory, so filtering the page afterwards returns the whole page or `[]`, exactly as filtering first does. |
| `gl_r2_hide_formula`, `gf_r2_hide_line` | Not a rule. GL R2 names the line's state and GF R2 names the formula's; neither names the other parent. Optional for the describer. |
| The real-states shape (step 1b): `in_progress` / `completed` / `cancelled` rows set `status` only | This is already the cases' Spec gap 4: the spec does not say which columns `start_batch`, `complete_batch` and `cancel_batch` write. It stays with the describer. |

## xfail tests against the reference
My reference, `ref/production_batch.py`, does the following. It is swapped in memory only.
- The lists join `production_lines` and `factories` with `is_deleted False`, and order by `batch_date DESC, id DESC`.
- `count_by_status` always joins.
- `year = utcnow().year`.
- The highest number is the numeric max over suffixes that are all digits.

Results:
- With `--runxfail`: **217 passed**.
- **The alarm works:** with the markers on, `29 failed, 179 passed, 9 xpassed`, and every strict card reports `XPASS(strict)`. GN-28 included, so the letters-above-digits collation the fork was unsure of holds here.
- On today's code every strict card fails on its "Fails today on" line on all three plans. GN-25 to GN-28 fail with `ValueError: invalid literal for int()` at the call, as their cards say.

## Reproduced claims
- **The notes' Result line holds:** `179 passed, 38 xfailed` in 4 of 4 default runs. No test is flaky.
- **Mocks:** only `clocks()` (wrapping the When only) and the commit spy. There is no `try` and no broad `pytest.raises`.
- **`ruff check`** passes.

## Traceability
cases 217 · tests 217 · unmatched: none · marker mismatches: none.
- BUG-1321, BUG-1330, BUG-1333 and BUG-1334 are in `bugs.md`.
- My comparator found 0 differences. Its selftest caught 1057 of 1057 planted mistakes.

## Commands run
```
pytest --cov=app.dao.production_batch --cov-branch                  179 passed, 38 xfailed; 95% (166, 216->220)
tests/unit/_tools/mutate.py app/dao/production_batch.py tests/unit/dao/test_production_batch.py --timeout 300 --json <scratch>/res/mut_production_batch.json
  51 mutants · 45 killed · 6 survived (L150, L166, L169-171)
xcheck.py; vdrive.py muts / vars (+ seq, idx); propdrive.py; fid.py; selftest.py
git diff --stat -- app/dao                                          (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\prodv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add R-1a to R-4.
2. **Executor,** after step 1: implement them, then send the module back for re-verification.


## Round 2 — 2026-11-03 (Revision 1 and 1b, narrow)

> **Verdict:** PASS
> Tests: 189 passed, 38 xfailed (reproduced ✅, 3 of 3 runs, no flaky test) · 227 cards
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 227 unfaithful** (new and changed tests read by eye against their cards; all 227 rebuilt by `fid.py`, 0 differences)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

Every round 1 finding is closed. I found no new rule gap. No test was edited in this round, and nothing was committed.

- **New / changed cards, read by eye:** BAT-GW-33, GL-34, GF-33, GS-41 (R-1a … R-1d), GF-34 (R-2), GS-42 and GN-33 (R-3a, R-3b), CS-30 … CS-32 (R-4). Each matches its card: Given, When, every Then, and the marker.
- **Gap variants against their cards**, on my reference with `--runxfail`, on the default, sequential-off and index-off plans: the four `*_r1_ws_after_page` fail GW-33, GL-34, GF-33, GS-41; `gf_r1_ge` fails GF-34; `gs_r1_le` GS-42; `gn_r4_le` GN-33; `cs_r1s_lower_col`, `cs_r1s_trim_col`, `cs_r1s_endswith` fail CS-30, CS-31, CS-32. Each fails its named card on all three plans.
- **Reference:** `--runxfail` gives 227 passed. With markers: 29 failed (strict XPASS), 189 passed, 9 xpassed. The alarms still go off.
- **Today, `--runxfail`:** every strict xfail fails on its card's line, on three plans.
- **Parked for the owner:** nothing.

### Commands run
```
fid.py production_batch                                     227 cards, 0 differences
r2.py (reference ±markers; gap variants × 3 plans; today --runxfail × 3 plans; 3 plain runs)
ruff check <the seven test files>               All checks passed!
git diff --stat -- app/dao                      (empty)
```
