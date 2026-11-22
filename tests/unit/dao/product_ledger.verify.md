# Verification — `app/dao/product_ledger.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1). See "Round 2" at the end. The block below is round 1.

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 83 passed · 9 xfail (6 strict, 3 non-strict) (reproduced ✅) · coverage 97% branch (25 statements, 10 branches; line 65 missed, the dead override)
> Mutation: 27 mutants · 24 killed · 3 survived → score 100% (after excluding 0 equivalent, 3 dead, 0 bug-path)
> Fidelity: **0 of 92 unfaithful** (92 / 92 read by eye against their cards; my script agrees)
> Hand variants: 94 · 78 caught by a pass card · 10 bug path · 6 others: 3 rule gaps in Findings, 3 under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** I read every test against its card, and my own comparator found the same: no difference.
- **Why NEEDS WORK:** all 24 live mutants are killed, but my hand variants show 3 rule gaps. They are for the case designer, and the Givens and Thens are written out below. The largest is R4a: the aware-bound cards use `Z` bounds only, so "strip the zone" cannot be told apart from "convert to UTC".
- **The one unordered query has its alarm.** `get_by_workspace` ties are BUG-640. The strict SQL card PLG-GW-42 goes off when the fix lands, and GW-43 to GW-45 are non-strict. No pass card depends on row order: every ordered pass card has distinct `performed_at` values.
- **Money / stock:** this module only reads the ledger. None of the gaps touches an amount. The double-post guard is FU-1 (a), owned by the manager.

Written by Claude (all 92 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 92. No `product_ledger.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_workspace` R4a "converted to UTC and made naive" | Every aware bound is `Z(h, m)`, which is already UTC. Dropping the zone without converting gives the same numbers, so no card fails. | `gw_r4a_strip_only` passes all 92 cards on all three plans. | **case designer** |
| 2 | case-missing | `exists_for_production_batch` R3 "another `source_type` does not count" | The stored-side cards cover capitals, a leading space, a part, and `-`. No stored value *extends* the constant, so a `LIKE 'production_batch%'` passes. | `ex_r3_startswith` passes all 92 on all three plans. | **case designer** |
| 3 | case-missing | `get_by_workspace` R1 with R6 (step 1b "filter before paging") | GW-38 to GW-41 put the factory, item, type and date filters before the page. No card puts *another workspace's* row ahead of the skipped row, so a workspace filter applied after `LIMIT` passes. | `gw_r1_ws_after_page` passes all 92 on all three plans. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
These are in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\prodv\prop\test_prop_product_ledger.py`, not in the repo. Each one passes on today's code and on my reference, on all three plans, and fails under its named variant.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, R4a | `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`; A = entry, `performed_at T12`. When `dao.get_by_workspace(db, workspace_id=W1.id, start_date=datetime(2026, 3, 1, 17, 30, tzinfo=timezone(timedelta(hours=6))), end_date=datetime(2026, 3, 1, 18, 30, tzinfo=timezone(timedelta(hours=6))))` | `ids(result) == [A.id]` | pass (today, PostgreSQL converts the bound itself under a UTC session) | `gw_r4a_strip_only` |
| R-2 | new card, EX R3 | A = entry, `performed_at T10`, `source_type "production_batch_v2"`, `source_id 88`. When `dao.exists_for_production_batch(db, workspace_id=W1.id, batch_id=88)` | `result is False` | pass | `ex_r3_startswith` |
| R-3 | new card, R1/R6 | Z = entry, `performed_at T12`, `workspace_id W2.id`, `factory_id F9.id`, `item_id I9.id`; A = entry, `performed_at T11`; B = entry, `performed_at T10`. When `dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)` | `ids(result) == [B.id]` | pass | `gw_r1_ws_after_page` |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 8 | 65 | `return` → `return None` | dead | `get_by_id_and_workspace` override: spec P4, "Not specified", dead-code checklist `app/dao/product_ledger.py:61` | — |
| 22 | 66 | `ProductLedger.id == id` → `!=` | dead | same override | — |
| 23 | 67 | `workspace_id ==` → `!=` | dead | same override | — |

**Guard.** My own driver ran each of the 27 mutants again, without `-x`, through an in-memory swap plugin. Every run reached all 83 pass tests, with no collection or setup error. The killed and surviving sets are the same as `mutate.py`'s.

## Hand variants
`variants.py` holds my hand variants. I ran them on my reference with `--runxfail` on the default plan. Every variant that no pass card caught ran again with sequential scans off and with index and bitmap scans off, and none changed. Every edit was asserted to apply exactly once, and every run reached all 92 tests.

| Group | Variants | Pass card | Others |
|---|---|---|---|
| gw_r1 (workspace) | 4 | 3 | `gw_r1_ws_after_page` (Finding 3) |
| gw_r2 / gw_r3 (factory, item; `0` is a filter) | 8 | 8 | — |
| gw_r4 (bounds, inclusive, day-truncation, end of day) | 8 | 8 | — |
| gw_r4a (aware bounds) | 5 | 1 | 3 bug path (GW-20 to GW-23); `gw_r4a_strip_only` (Finding 1) |
| gw_r5 / gw_r5a (exact type, blank type) | 12 | 12 | — |
| gw_r6 (AND; each filter before the page) | 5 | 5 | — |
| gw_r7 / gw_r7a (tie key, direction) | 9 | 3 | 6 bug path, caught by GW-42 strict and GW-44 |
| gw_r11 (parents not joined) | 2 | 2 | — |
| gw_pg (paging, defaults, negatives) | 10 | 9 | `gw_pg_cap101` |
| gw_w (flush, expire, dirty, commit) | 4 | 4 | — |
| ex_r2 / ex_r4 (source id, workspace) | 8 | 8 | — |
| ex_r3 (exact `source_type`) | 13 | 10 | `ex_r3_startswith` (Finding 2); `ex_r3_lower_arg`, `ex_r3_trim_arg` |
| ex_ret / ex_w | 6 | 6 | — |
| inh_r2a (`performed_at` from the database clock) | 1 | 0 | bug path (INH-05) |
| **Total** | **94** | **78** | **16** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `gw_pg_cap101` | A cap above the card's own 101 rows. `gw_pg_cap100` is caught by GW-50, and 1000 is the endpoint's bound. |
| `ex_r3_lower_arg`, `ex_r3_trim_arg` | **Equivalent:** the argument is the constant `"production_batch"`, which is already lower case and has no spaces. |

## xfail tests against the reference
My reference is in `ref/product_ledger.py`. It converts aware bounds to UTC, adds `id DESC` as the tie key, and sets `performed_at = utcnow()` in `create`. It is swapped in memory only, and nothing is written to `app/`.

- With `--runxfail` on the reference: **92 passed**.
- **The alarm works:** with the markers on, `6 failed, 83 passed, 3 xpassed`. The six strict cards report `XPASS(strict)`.
- With `--runxfail` on today's code: every xfail test fails on its card's "Fails today on" line, on all three plans:
  - GW-20 to GW-23 fail on Then 1.
  - GW-42 fails on Then 4.
  - GW-43 to GW-45 fail on Then 2.
  - INH-05 fails on Then 2.

  No non-strict card passed today in these runs.

## Reproduced claims
- **The notes' Result line holds:** `83 passed, 9 xfailed` in 4 of 4 default runs, the coverage run among them. No test is flaky.
- **Mocks:** only the commit spy `patch.object(db, "commit", wraps=db.commit)` on the rolled-back cards. There is no `try`, no broad `pytest.raises`, and no `if` in a test body.
- **Step 1b shapes:** each shape is present as the cases describe it. The exception is filter-before-page for the workspace filter (Finding 3).

## Traceability
cases 92 · tests 92 · unmatched: none · duplicates: none · marker mismatches: none.
- Card order matches file order.
- Each docstring repeats its card's ID, title and Rules line.
- The `# Then N` numbers match the card.
- Every BUG ID (640, 992, 1337) is in `docs/testing/bugs.md`.
- `ruff check` passes.

**My comparator** (`fid.py`) rebuilt each test's markers, When, Then assertions in block order, Given builder arguments and steps, snapshots, and extra statements from its card, and compared them by AST.
- It ran over all 810 cards of the batch and reported 0 differences here.
- Its selftest caught 1057 of 1057 planted mistakes of 26 kinds, in tests and in cards, across the 7 modules.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated:** other agents were live on the shared test database. Every kill is a plain `N failed`.
- **Not exercised:** the manager, service or HTTP level, and a real race.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_product_ledger.py -q -p no:cacheprovider --cov=app.dao.product_ledger --cov-branch --cov-report=term-missing --tb=no   (private COVERAGE_FILE)
  83 passed, 9 xfailed; 97% (line 65)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/product_ledger.py tests/unit/dao/test_product_ledger.py --timeout 300 --json <scratch>/res/mut_product_ledger.json
  27 mutants · 24 killed · 3 survived (L65-67)
xcheck.py (--runxfail × 3 plans, 3 plain runs); vdrive.py muts; vdrive.py vars (+ --plan seq/idx); propdrive.py; fid.py; selftest.py all 6
.venv/Scripts/python.exe -m ruff check <the seven test files>        All checks passed!
git diff --stat -- app/dao                                           (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\prodv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add R-1 to R-3.
2. **Executor,** after step 1: implement them, then send the module back for re-verification.


## Round 2 — 2026-11-03 (Revision 1 and 1b, narrow)

> **Verdict:** PASS
> Tests: 86 passed, 9 xfailed (reproduced ✅, 3 of 3 runs, no flaky test) · 95 cards
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 95 unfaithful** (new and changed tests read by eye against their cards; all 95 rebuilt by `fid.py`, 0 differences)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

Every round 1 finding is closed. I found no new rule gap. No test was edited in this round, and nothing was committed.

- **New / changed cards, read by eye:** PLG-GW-65 (R-3), PLG-GW-66 (R-1), PLG-EX-19 (R-2). Each matches its card: Given, When, every Then, and the marker.
- **Gap variants against their cards**, on my reference with `--runxfail`, on the default, sequential-off and index-off plans: `gw_r1_ws_after_page` fails GW-65, `gw_r4a_strip_only` fails GW-66, `ex_r3_startswith` fails EX-19. Each fails its named card on all three plans.
- **Reference:** `--runxfail` gives 95 passed. With markers: 6 failed (strict XPASS), 86 passed, 3 xpassed. The alarms still go off.
- **Today, `--runxfail`:** every strict xfail fails on its card's line, on three plans.
- **Parked for the owner:** nothing.

### Commands run
```
fid.py product_ledger                                     95 cards, 0 differences
r2.py (reference ±markers; gap variants × 3 plans; today --runxfail × 3 plans; 3 plain runs)
ruff check <the seven test files>               All checks passed!
git diff --stat -- app/dao                      (empty)
```
