# Verification — `app/dao/product.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — work for the case designer, plus one spec gap for the describer. No test is wrong. `get_by_item` R3c (BUG-1338, spec revision 2026-11-03) is changing in parallel and was **not judged**; see "Not judged".
> Tests: 123 passed · 41 xfail (32 strict, 9 non-strict) (reproduced ✅) · coverage 100% branch (36 statements, 4 branches)
> Mutation: 33 mutants · 33 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 163 judged unfaithful** (163 / 163 read by eye; my script agrees). 1 nit: PRD-GW-45.
> Hand variants: 151 · 106 caught by a pass card · 39 bug path · 6 others: 3 rule gaps and 1 spec gap in Findings, 2 under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED with revision 2026-11-03 (BUG-1338) not yet in the cases

## Summary
- **The tests can be trusted as written.** All 163 judged tests match their cards, by eye and by my comparator.
- **Why NEEDS WORK:**
  - **3 rule gaps, for the case designer.** Recipes are below.
    - Another workspace's row placed ahead of the page (`get_by_workspace`).
    - A later workspace's row for the new `_get_any_by_factory_item_available` (BUG-1336).
    - `restore` moving `updated_at` from `None`.
  - **1 spec gap, for the describer:** a stock row with `is_active False`, `is_deleted False` has no rule in `get_by_item`.
- **Unordered queries have their alarms.**
  - `get_by_workspace` (BUG-1325) has the strict SQL card GW-37. GW-38 to GW-44 are non-strict.
  - `get_by_item` (BUG-1326) has the strict card GT-17. GT-18 and GT-19 are non-strict.
  - Non-strict cards that pass today on every plan, by row order: **GW-39, GW-40**. GW-41, GT-18 and GT-19 pass on some plans. Their strict alarms cover them.
  - No pass card depends on row order.
- **Stock:** `soft_delete` keeps `qty` on the row (FU-1 (b), owner). `_get_any_*` (BUG-1336) is the owner's answer. No gap touches an amount.

Written by Claude (all 164 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 163. No `product.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Not judged
- **PRD-GT-16** (`get_by_item` R3c). The spec revision of 2026-11-03 makes it an xfail on BUG-1338 and adds cards for R3b's item parts. The cases and tests are being changed in parallel.
- My reference keeps today's R3c behavior, so GT-16 passes on it. Re-verify GT-16 and the new R3b and R3c cards when they land.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_workspace` R1 with R2 / R5 (step 1b "filter before paging") | No card puts another workspace's row ahead of the skipped row. A workspace filter applied after `LIMIT` passes. | `gw_r1_ws_after_page` passes all 164 on all three plans. | **case designer** |
| 2 | case-missing | `_get_any_by_factory_item_available` R2 [BUG-1336] (step 1b "other workspace's row, earlier and later") | GA-10 asks W2 for a W1 row only. A `>=` on `workspace_id` finds a W2 row for W1, and no card, xfail or pass, fails. GK-08 to GK-11 have both directions for the live lookup. | `ga_r2ws_ge`: 0 cards fail, on all three plans. | **case designer** |
| 3 | case-missing | `restore` R2 "`updated_at` moves" | RS-04 starts from `updated_at T0` and asserts `!= T0`. `None` also satisfies that. Unlike SD-04 for `soft_delete`, no restore card starts from `None`. | `rs_r2_updated_at_none` passes all 164 on all three plans. | **case designer** |
| 4 | spec-gap | `get_by_item` R1 / R2 | R2 says a soft-deleted row is hidden. The spec never says whether a row with `is_active False`, `is_deleted False` is returned. `get_by_workspace` R2 and GK R5 say it is, and such rows exist (`restore` R4). | `gt_r2_active_instead` (`is_active` filter instead of `is_deleted`) passes all 164. | **describer** (fill-gaps), then case designer |
| 5 | nit, not unfaithful | PRD-GW-45 Given 3 | `newest` = the ids is not built in the test. No Then line uses it. | Card Given 3. The test has no `newest` line. | executor (optional) |

No fidelity finding.

### Scratch cards that close the gaps
These are in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\prodv\prop\test_prop_product.py`. Each one is run on today's code, on my reference and under its named variant, on all three plans:
- **R-1** fails today with `AttributeError` (as a strict xfail should), passes on the reference, and fails under its variant.
- **R-2 and R-3** pass today and on the reference, and fail under their variants.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, GA R2 | Z = stock, `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. When `dao._get_any_by_factory_item_available(db, factory_id=F9.id, item_id=I9.id, is_available_for_sale=False, workspace_id=W1.id)` | `result is None` | xfail BUG-1336 (strict; fails today on Then 1, the call raises AttributeError) | `ga_r2ws_ge` |
| R-2 | new card, `restore` R2 | A = stock, `updated_by U1.id`, `is_active False`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id` (`updated_at` left `None`). When `dao.restore(db, db_obj=A)` | `result is A`; re-read A: `updated_at is not None`; re-read A: `updated_by == U1.id` | pass | `rs_r2_updated_at_none` |
| R-3 | new card, GW R1 | Z = stock, `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id` ("Far Crate" sorts before "Gear" and "Hook"); A = stock, `item_id I4.id`; B = stock, `item_id I5.id`. When `dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)` | `ids(result) == [B.id]` | pass | `gw_r1_ws_after_page` |

## Surviving mutants
None. All 33 kills end in a plain `N failed`.

**Guard.** My driver ran each of the 33 mutants again, without `-x`. Every run reached all 123 pass tests, with no collection or setup error, and the kill set was the same as `mutate.py`'s.

## Hand variants
These are my hand variants on my reference, run with `--runxfail` on the default plan. Every variant with no failing pass card ran again with sequential scans off and with index and bitmap scans off, and none changed. Every edit applied exactly once, and every run reached all 164 tests.

| Group | Variants | Pass card | Others |
|---|---|---|---|
| gw_r1 to gw_r4a (workspace, deleted, factory, sale flag, qty) | 17 | 16 | `gw_r1_ws_after_page` (Finding 1) |
| gw_r5a, gw_r5b, gw_r5ab (parents, BUG-1327) | 5 | 3 | 2 bug path (GW-24 to GW-32) |
| gw_r6 (order, BUG-1325) | 10 | 0 | 10 bug path (GW-37 strict, GW-38 to GW-44) |
| gw_r9 (item data, no extra query) | 2 | 2 | — |
| gw_pg / gw_w | 14 | 13 | `gw_pg_cap101` |
| gi (by id: workspace both sides, deleted, parents, writes) | 12 | 12 | — |
| gk (live key lookup) | 19 | 19 | — |
| ga (`_get_any`, BUG-1336) | 20 | 0 | 19 bug path (GA-01 to GA-16); `ga_r2ws_ge` (Finding 2) |
| gt (item rows) | 23 | 15 | 6 bug path (GT-10 to GT-12, GT-17 to GT-19); `gt_r2_active_instead` (Finding 4); `gt_r5_cap1000` |
| sd (`soft_delete`) | 18 | 16 | 2 bug path (SD-07, SD-08, BUG-1335) |
| rs (`restore`) | 11 | 10 | `rs_r2_updated_at_none` (Finding 3) |
| **Total** | **151** | **106** | **45** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `gw_pg_cap101`, `gt_r5_cap1000` | A cap above the card's own 101 rows. `gw_pg_cap100` and `gt_r5_cap100` are caught. |
| Step 1b observations (fork reading): GW-31 and GW-32 put the hidden row on "Old Gasket", which sorts after the skipped rows once BUG-1325 is fixed. GT-21's pending row is outside the filter. | Both are bug or side cards whose purpose still holds: `gw_r5ab_after_page` is caught by pass card GW-54, and `gt_w_flush` is caught by GT-21 Then 3, 4 and 6. No variant survives because of them. |

## xfail tests against the reference
My reference, `ref/product.py`, adds the following. It is swapped in memory only.
- `get_by_workspace`: parent filters and `lower(items.name), products.id`.
- `get_by_item`: the factory filter and `products.id`.
- The new `_get_any_by_factory_item_available`.
- `deleted_at = utcnow()`.

Results:
- With `--runxfail` on the reference: **164 passed**.
- **The alarm works:** with the markers on, `32 failed, 123 passed, 9 xpassed`. Every strict card reports `XPASS(strict)`.
- With `--runxfail` on today's code, every strict xfail fails on its "Fails today on" line, on three plans. GA-01 to GA-16 fail with `AttributeError` at the call, as their cards say.

## Reproduced claims
- **The notes' Result line holds:** `123 passed, 38 xfailed, 3 xpassed` in 4 of 4 default runs. Only the non-strict GW-39, GW-40 and GT-19 xpass. No test is flaky.
- **`--runxfail`:** 38 failed (default), 37 failed (sequential off), 37 failed (index off). Only the non-strict cards move.
- **Mocks:** only the commit spy and `clock_now()` (SD-07, SD-08, wrapping the When only). There is no `try` and no broad `pytest.raises`.

## Traceability
cases 164 · tests 164 · unmatched: none · duplicates: none · marker mismatches: none.
- BUG-1325 to BUG-1328 and BUG-1335 to BUG-1336 are in `bugs.md`.
- BUG-1336 cards carry `raises=AttributeError`, as the Conventions say.
- My comparator: 0 differences beyond PRD-GW-45 (nit) and three bulk Givens (GW-45, GW-46, GT-20), which I read by eye and found faithful.
- Selftest: 1057 of 1057 planted mistakes caught.
- `ruff check` passes.

## Commands run
```
pytest --cov=app.dao.product --cov-branch (private COVERAGE_FILE)   123 passed, 36 xfailed, 5 xpassed; 100%
tests/unit/_tools/mutate.py app/dao/product.py tests/unit/dao/test_product.py --timeout 300 --json <scratch>/res/mut_product.json
  33 mutants · 33 killed
xcheck.py; vdrive.py muts / vars (+ seq, idx); propdrive.py product; fid.py; selftest.py all 6; ruff check   All checks passed!
git diff --stat -- app/dao                                          (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\prodv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Describer:** Finding 4 (fill-gaps).
2. **Case designer:** R-1 to R-3, together with the BUG-1338 revision already pending.
3. **Executor:** implement the new cards, then send the module back for re-verification, including GT-16.


## Round 2 — 2026-11-03 (Revision 1 and 1b, narrow)

> **Verdict:** PASS
> Tests: 127 passed, 38 xfailed, 5 xpassed (non-strict tie cards only) (reproduced ✅, 3 of 3 runs, no flaky test) · 170 cards
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 170 unfaithful** (new and changed tests read by eye against their cards; all 170 rebuilt by `fid.py`, 0 differences)
> Source commit: e48a092 · Cases revision: 1 and 1b; spec APPROVED

Every round 1 finding is closed. I found no new rule gap. No test was edited in this round, and nothing was committed.

- **New / changed cards, read by eye:** PRD-GT-16 (changed: now `[]`, strict xfail BUG-1338; fails today on Then 1, A is returned), PRD-GT-23 (R2a), PRD-GT-24 and GT-25 (R3b item parts), PRD-GW-57 (R-3; Revision 1b `limit=2` with a set check), PRD-GA-17 (R-1, strict xfail BUG-1336 with `raises=AttributeError`), PRD-RS-10 (R-2); GW-45 drops the unused `newest`. Each matches its card: Given, When, every Then, and the marker.
- **Gap variants against their cards**, on my reference with `--runxfail`, on the default, sequential-off and index-off plans: `gw_r1_ws_after_page` fails GW-57, `ga_r2ws_ge` fails GA-17, `rs_r2_updated_at_none` fails RS-10, `gt_r2_active_instead` fails GT-23 (former Finding 4, closed by the owner's answer and R2a), and two new R3c variants (`gt_r3c_drop`, an item filter on the wrong column) fail GT-16. Each fails its named card on all three plans.
- **Reference:** `--runxfail` gives 170 passed. With markers: 34 failed (strict XPASS), 127 passed, 9 xpassed. The alarms still go off.
- **Today, `--runxfail`:** every strict xfail fails on its card's line, on three plans.
- **My round 1 recipes for the unordered lists were order-fragile:** they named one row of a query with no `ORDER BY`. Revision 1b's `limit=2` cards fix that, and still fail the after-`LIMIT` variant on all three plans.
- **Not judged in round 1, judged now:** PRD-GT-16 and the R3b/R3c cards. My reference now hides a removed item in `get_by_item` (BUG-1338).
- **Parked for the owner:** nothing.

### Commands run
```
fid.py product                                     170 cards, 0 differences
r2.py (reference ±markers; gap variants × 3 plans; today --runxfail × 3 plans; 3 plain runs)
ruff check <the seven test files>               All checks passed!
git diff --stat -- app/dao                      (empty)
```
