# Verification — `app/managers/machine_item_manager.py`

> **Verdict:** PASS (round 2, 2026-10-31) — the 10 new tests are faithful, and all 7 gap variants and mutant L259 now fail the right card. No test edited.
> Tests: 280 passed · 210 xfail as designed (207 or 208 xfailed, 2 or 3 non-strict xpassed; reproduced ✅) · coverage 100% branch
> Mutation: line 259 only: 3 / 3 killed. Whole file 114 / 114 = 100%, with round 1's other results carried over (1 equivalent, 1 dead, 1 bug-path excluded)
> Source commit: e48a092 · Cases revision: 5 (490 cases; spec APPROVED)
> Round 1 is below, kept as written.

## Round 2 (2026-10-31) — scoped to L-67 … L-70, W-33, D-246 … D-250

- **Read:** the 10 tests by eye against their cards and R4, R5 (a), R6, R7, R9, G10: each Given row, When call and numbered Then line matches, in order. All `# [claude]`. Unfaithful: 0 of 10.
- **Rebuild, all 490:** card order equals file order, and markers and docstrings match. Then lines went from 2 533 to 2 588, and the 55 added are exactly these 10 cards, so no existing card gained or lost a line. The only reports are round 1's 4, none real. The 480 earlier tests were checked this way, not re-read.
- **Reference:** no change needed. It never read `action_type` in R5 (a), which is what G10 now states. 490 of 490 pass with `--runxfail`, so every new Then line runs. G10 is recorded as a fact verified by the describer; I did not re-run `p11.py`.
- **Gap variants, each failing the right card:**

| Round 1 finding | Variant / mutant | Now fails | Only failure |
|---|---|---|---|
| 1 | `after_sorted_w_machine` | L-67 T1 | yes |
| 1 | `after_sorted_w_factory` | L-68 T1 | yes |
| 1 | `after_sorted_w_foreign`, `l_foreign_after_page` | L-70 T1 | yes (each) |
| 1 | `after_sorted_m_foreign` | L-69 T1 | yes |
| 2 | `c_value_after_even` | W-33 T2 | yes |
| 3 | `d_ref_action_type_consume` | D-247, D-248, D-249 T1 | these 3 |
| 4 | mutant L259 `> 0` → `> 1` | D-246 | yes |

- **Added variants:** `a_not_install`, `a_not_borrow`, `a_not_replace` fail D-247, D-248, D-249 T1, one each. `wo_per_line` now also fails D-250 T4, beside D-77 … D-79. `a_sorted_by_line_asc` still fails D-69 T4. 12 of 12 caught, no setup error.
- **xfails:** all 9 new ones fail at the Then line their card names, with its reason: L-67 … L-70 show the two counted rows, W-33 shows `0.00`, D-247 … D-250 show `DID NOT RAISE ValueError`. Over the file, 208 failed in the `--runxfail` run and none on setup. L-24, L-36 passed there, as in round 1, and their proof stands. D-246 passes today, as its card says.
- **Mutation:** `--lines 259-259`: 3 mutants, 3 killed. The only `case-missing` of round 1 is closed: 114 / (117 − 3) = 100%. The other 114 mutants were not re-run, on the coordinator's instruction; only tests were added, and `app/` is unchanged, so no kill can be lost.
- **Runs:** 3 without `--runxfail` gave 280 passed, with 207 or 208 xfailed and 2 or 3 xpassed, all among L-24, L-36, L-58, as the notes say. Coverage 100%. `ruff check` passes. Test and cases files have the same hash at the start and end of these runs. `git diff --stat app/managers/machine_item_manager.py` is empty.
- **Finding 5 (`mutate.py`):** line 160 now sets stdout to UTF-8. Read, not exercised: line 259 prints no `→`, and my run had `PYTHONIOENCODING` set.
- **Accepted, not open:** the 13 schema-only Then lines, optional. No owner question is open: G10 settles round 1's order-workflow flag, and finding 2 was only a missing card.
- **Limits:** the round 1 hand variants were not re-run, only the 12 above. The new xfails' later Then lines passed on the reference but were not each forced to fail on their own line. The reference is one fix, mine.

Scratch: `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\mimv\` (`variants2.json`, `mut2_259.json`, `runx4.txt`, `rb2.out`). Only this report was written in the repo. No commit. No model server.

```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/machine_item_manager.py tests/unit/managers/test_machine_item_manager.py --lines 259-259 --timeout 300 --json <scratch>/mut2_259.json
  Mutants: 3 · killed 3 · timeout 0 · survived 0
pytest --cov (branch)                 78 statements, 24 branches, 100%; 280 passed, 207 xfailed, 3 xpassed
pytest (twice)                        280 passed, 207 xfailed, 3 xpassed; 280 passed, 208 xfailed, 2 xpassed
pytest --runxfail -rf                 208 failed, 282 passed
MIMREF=fix ... -p ref_mim --runxfail  490 passed
```

---

The sections below are round 1, kept as written.

> **Verdict:** NEEDS WORK — the tests are faithful (0 of 480 unfaithful). Only the case designer has work: 4 small gaps. No test edited.
> Tests: 279 passed · 201 xfail as designed (199 or 200 xfailed, 1 or 2 non-strict xpassed; reproduced ✅) · coverage 100% branch (78 statements, 24 branches)
> Mutation: 117 mutants · 113 killed · 4 survived → score 99% (113 / 114, after excluding 1 equivalent, 1 dead, 1 bug-path; 1 `case-missing` remains)
> **Mutation says nothing about `delete_machine_item` R5, R5a, R5b:** no blocking code exists today. Those rules rest on the reference and the hand variants.
> Hand variants on my reference: 243 · 230 caught · 13 survived (7 `case-missing`, 3 equivalent, 2 belong to the DAO's rules, 1 depends on the query plan)
> Source commit: e48a092 · Cases revision: 3 (480 cases; spec APPROVED)

## Summary
- **The generated tests can be trusted as written.** Every test matches its card. No swapped object, weakened check, extra mock or missing Then line turned up, and no xfail fails on setup.
- **The evidence goes beyond reading.** My own reference fix, written from the spec and not the executor's, passed 480 of 480 on its first run. So every line of every card runs, and no pass test pins a bug. My own translator of the cards finds 600 of 600 planted mistakes.
- **All 201 xfails fail for their card's reason.** 199 were mapped to the card's line and message. L-24, L-36 passed in the `--runxfail` runs, so they were proved with a forced wrong order.
- **Why NEEDS WORK:** 4 rule gaps, all for the case designer. Scratch tests show each is closed by one or a few small cards. The largest is finding 1: once a fix sorts by name, the "takes no place in the page" cards can no longer see a filter applied after paging.
- **One tool warning:** `mutate.py` crashes when its output is redirected on Windows (finding 5).
- **No owner question is open.** One money gap and one order-workflow gap are flagged below, but both rules are already written.

Written by Claude: all 480 under `# [claude]`. There is no `machine_item_manager.local-run.json`, so there is no `## Local-coder patterns` section. Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 480.

## Findings
| # | Kind | Case / rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `list_machine_items` R7, R9 "takes no place in the page"; L-40, L-42, L-45, L-61, L-64 | The hidden rows in these cards do not sort ahead of the visible row. Under the intended name order they fall after it (`Far Clip`, `Far Spring` after `Bolt M8`) or tie before it and still leave it on the page, so filtering after `limit` still returns the expected row. The cards fail today only because no order is requested. L-46 covers a removed item this way; a deleted machine, a deleted factory and a foreign item have no such card. | `after_sorted_w_machine`, `after_sorted_w_factory`, `after_sorted_w_foreign`, `after_sorted_m_foreign`, `l_foreign_after_page` pass all 480 | **case designer** |
| 2 | case-missing (money) | `_write_ledger_entry` R4, HR-15, G6 | W-32 has `value_after` 2 × 0.125 = 0.25, which is exact. `value_after` has no midpoint on any card, so half to even passes. `value_before` is covered. The rule is written. | `c_value_after_even` passes all 480 | **case designer** |
| 3 | case-missing (order workflow) | `delete_machine_item` R5 (a) | R5 (a) does not read `action_type`, but every blocking source line has the default `CONSUME`. A fix that blocks on `CONSUME` lines only lets a row go while an `INSTALL` or `BORROW` line still sources from it. The rule is written; see the flag below. | `d_ref_action_type_consume` passes all 480 | **case designer** |
| 4 | case-missing | `delete_machine_item` R6 boundary | No delete card has `qty 1`. C-29 has this boundary on create; delete has 5, 3, 0, −3. | mutant L259 `> 0` → `> 1` | **case designer** |
| 5 | tool | `tests/unit/_tools/mutate.py` line 193 | The `print` raises `UnicodeEncodeError` on a mutant description holding `→` when stdout is redirected (cp1252). The run stops at that mutant and writes no JSON. `PYTHONIOENCODING=utf-8` avoids it. | Chunk 61-126: `rc=1`; rerun with the variable: `rc=0` | **tool owner** |

No fidelity finding.

### Scratch tests that close the gaps
In `mimv\prop\test_mim_prop.py`, not in the repo. All 7 pass on the reference, and each fails on the variants shown.

| Scratch test | Finding | Fails on |
|---|---|---|
| hidden rows of a deleted machine sort first (`Aaa1`, `Aaa2`), `limit=2` gives the visible row | 1 | `after_sorted_w_machine` |
| the same, deleted factory | 1 | `after_sorted_w_factory` |
| the same, W2 items, no `machine_id` | 1 | `after_sorted_w_foreign` |
| the same, W2 items, with `machine_id` | 1 | `after_sorted_m_foreign` |
| 2 → 1 at an unexpired 0.125 gives `value_after` 0.13 | 2 | `c_value_after_even` |
| an `INSTALL` source line blocks | 3 | `d_ref_action_type_consume` |
| delete with `qty 1` books `quantity` 1, 1 → 0 | 4 | mutant L259 |

The scratch delete test also passes today and fails only on that mutant, in a run with the 480 tests alongside.

## Flagged for the owner
No decision is needed; both rules are written.
- **Money:** finding 2 only adds a card for HR-15.
- **Order workflow:** finding 3 reads R5 (a) literally: any `action_type`. My reference does the same, and that is a reading, not a decision. I did not check what `INSTALL` or `BORROW` lines do at posting. If only `CONSUME` lines were meant, R5 (a) must say so.

G3, G4, G5 and the correction are recorded in the spec as relayed answers. I checked the tests against them, not the answers themselves.

## Surviving mutants
Each was re-run alone against today's source with xfails visible.

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 11 (chunk 1-60) | 33 | `"Item #"` → `""` | dead | The fallback is on the dead-code list and goes with BUG-1086; spec R3 gives it no direct case. Re-run identical. | — |
| 11 (chunk 190-245) | 205 | `exclude_unset` `True` → `False` | equivalent | `exclude_none` stays and every field defaults to `None`, so the same keys remain. Re-run identical. | — |
| 12 (chunk 190-245) | 205 | `exclude_none` `True` → `False` | bug-path (BUG-1075) | U-23, U-24, U-25 XPASS. Nothing else changes. | — |
| 6 (chunk 246-292) | 259 | `item.qty > 0` → `> 1` | **case-missing** | Finding 4. | **case designer** |

Score: 113 / (117 − 1 − 1 − 1) = 113 / 114 = **99%**. Raw tool figure: 97%. All 113 kills end in `N failed`; none is an error-only run.

## Reference and hand variants
`mimv\plug\ref_mim.py` is a pytest plugin that swaps the source of the manager, `app.dao.machine_item` and `app.schemas.machine_item` in memory. Nothing is written to `app/`. It fixes BUG-1081, BUG-1086, BUG-993, BUG-1040, BUG-983, BUG-1079, BUG-1080, BUG-1083 … BUG-1085, BUG-1070 … BUG-1078, and also BUG-1010, BUG-976, BUG-979, BUG-980 so all 480 can run. BUG-983's unique index is created inside the transaction of MIM-C-25 only. **480 passed** with `--runxfail`, on the first run.

Each variant's edit is asserted to apply. No variant run shows a setup error. `variants.json` has the failing card and Then line of each.

| Group | Variants | Caught | Survivors |
|---|---|---|---|
| Each blocker type dropped | 4 | 4 | none |
| Each non-blocking state made to block | 30 | 30 | none |
| A blocking state narrowed (status, stage, voided, consumed, parents) | 21 | 20 | `d_ref_action_type_consume`, finding 3 |
| Row's own quantities block | 3 | 3 | none |
| Cross-workspace shapes, generic entry | 34 | 34 | none |
| Sort | 9 | 8 | `wo_unsorted`, below |
| Dedupe and ids | 8 | 8 | none |
| Write before refusal | 11 | 11 | none |
| Order of checks | 3 | 3 | none |
| Form of the refusal | 11 | 11 | none |
| BUG-1080 | 4 | 4 | none |
| BUG-1083, 1084, 1076, 1085, 1010 | 13 | 13 | none |
| BUG-1086 | 9 | 8 | `l_foreign_after_page`, finding 1 |
| BUG-1077 | 5 | 5 | none |
| Lists (BUG-1070, 1071, 1074, 979, 980, 976) | 13 | 12 | `m_sort_tie_desc`, below |
| BUG-993, BUG-1040 | 20 | 19 | `c_value_after_even`, finding 2 |
| BUG-983 | 4 | 3 | `r_all_integrity`, below |
| BUG-1072, 1073 | 3 | 3 | none |
| Schemas (BUG-1075, 1078, 1079) | 29 | 29 | none |
| Filter after a sorted page | 8 | 1 | 4 in finding 1; 3 below |
| Forced wrong order (proof) | 1 | 1 | none |

**Survivors that are not findings:**
- `r_all_integrity`, equivalent: the machine and item are checked first, so a unique violation is the only error left at that flush.
- `after_sorted_m_machine`, `after_sorted_m_factory`, equivalent: every row of such a machine is hidden, so the result is `[]` either way.
- `m_sort_tie_desc`, `after_sorted_m_item`: machine item DAO rules. Spec R1 gives this manager one pass-through case each, so they belong to the DAO's cards. I did not check those cards here.
- `wo_unsorted`, no `ORDER BY` at all: D-69 asserts the order correctly and catches a wrong order (`a_sorted_by_line_asc`, `wo_desc`), but an unordered query returned the right order in this run. Whether it does depends on the plan, so a fix with no sort may pass. Not a rule gap.

My first `a_sorted_by_line` sorted line ids descending, which gives the right order by construction. It was my mistake; `a_sorted_by_line_asc` replaced it and is counted above.

**Blocking variants caught by one card only** (keep in mind when a card is edited): D-26, D-27, D-28, D-30, D-32, D-33, D-35, D-36, D-37, D-38, D-49, D-53, D-70, D-71, D-80, D-81, D-242, D-243.

### Then lines the xfails never reach
- The 201 xfails have **1 112 Then lines after the failing line**. None runs today. All run and pass on the reference.
- **693 were made to fail on their own line** by some variant. The drive records only the first failing line per card, so this is a lower bound.
- **419 were not forced alone.** Most are the repeated refusal checks: 120 `db.flush()`, 122 `session:` and `raises:` lines, 83 `nothing written` and `unchanged(MI)`. The 13 schema lines below are among them.

### Lines that cannot fail on their own
13 Then lines check the database after a When that only builds a schema: C-35, C-37, C-38, C-40, C-41, C-43 Then 2 (`machine_items` count); U-26, U-47, U-49, U-50, U-52, U-53, U-55 Then 2 (`unchanged(MI)`). The tests match their cards, so this is not a test fault. Same kind as machine manager finding 11: an optional card clean-up, no verdict impact.

## Reproduced claims
- The notes' Result line matches: 279 passed, 201 xfail as designed, 100%.
- **xfails:** 195 fail at the Then line the card names. G-07, G-09, G-11, G-12 fail in the When with the `TypeError` their card names. Each failing value was read against the card's parenthesis, with no mismatch and no setup error. L-24, L-36 fail at Then 1 under a forced `qty, id` order. L-58 also fails at Then 1 on a reversed tie. L-02, L-46, L-55, L-56, L-57 fail at Then 1 every run.
- **No flaky test.** On the live file, 5 runs without `--runxfail` gave 279 passed, and the 193 strict and 5 steady non-strict cards xfailed (3 plain or coverage, seqscan off, index and bitmap off). L-24, L-36, L-58 moved as the notes say: 2 xpassed in 4 runs (L-24, L-36 in the 3 that name them), and L-58 alone in the index-off run. 2 runs with `--runxfail` gave 199 failed, 281 passed.
- `-W error` is not usable here: `BaseDAO.remove` (`app/dao/base.py` line 136) raises `LegacyAPIWarning` in every test that hard-deletes. 129 failed for that reason. Not a test fault.
- Mocks: only `patch.object` in C-25 and `commit_spy` in the 4 rolled-back cards, as Conventions allow. No broad `pytest.raises`, no `try` around an action (the one `try` is `record_sql`'s cleanup), no `if` in a test body.
- DISCREPANCY-1 and 2 are closed: the live cards carry `next_clock_tick()` in W-21 … W-25 and the new U-25 Then 4, and the tests match them.

## Traceability
cases 480 · tests 480 · unmatched: none · duplicates: none · marker mismatches: none. MIM-D-31 is retired and has no test. 279 `pass` cards have no marker; 201 xfail cards name the card's bug, 193 strict, 8 non-strict. `# Then N` numbers match the card in all 480. Docstrings equal title and Rules; the one difference is a space before the period in W-03, which keeps the closing quotes valid. `ruff check` passes.

**Rebuild:** my own translator, not the executor's, turns each card into expected statements and compares them in order: 2 533 Then lines, every Given, When, marker and snapshot. It reports 3 differences and 1 unread line, none real: W-03 above; C-10, C-17, where the card's `{I9.id}` sits in an f-string my lowering skips (the test has `i9.id`); W-25's When, where the test line carries a `# noqa`. Self-test: 600 planted across 15 kinds, 600 found.

## Runs cut off or redone
- **Mutation chunk 61-126:** first attempt crashed (finding 5) with no JSON. Rerun in full, `rc=0`, and that run is used.
- **Mutation chunk 1-60:** it started before the test file was synced at 16:54:43. Re-run on the live file, same result: 12 killed, 1 survived.
- **Hand variants:** the drive kept running through the usage-limit pause and finished with exit code 0, all 234 first-round results present. 9 were added after.
- `test_machine_item_manager.py` and the cases file have the same hash at the start and end of the live-file runs.

## Limits of this round
- **How the reading was done.** I read all 480 cards in a condensed listing, and the helpers, fixtures and sample tests in full. The test bodies were compared to the cards by the rebuild, not each by eye. The listing left out the repeated `session:`, `nothing written` and `unchanged(MI)` lines, which only the rebuild checked.
- **The reference is one fix, mine.** The executor's scratch reference also passed 480, so two separate fixes agree. Another correct fix could still expose a card that assumes something both do.
- **Pass-card Then lines were not each forced to fail.** They rest on mutation and the variants.
- **Runs were not isolated.** Other agents ran at the same time. All 113 kills are real test failures, and C-25's index on the reference is held for that one test.
- **Not exercised:** service or HTTP level, the FU-1 (a) translation of the `ValueError`, a real race (BUG-1072, BUG-1073, BUG-983), and the two repair scripts.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/machine_item_manager.py tests/unit/managers/test_machine_item_manager.py --lines <range> --timeout 300 --json <scratch>/mut_<range>.json
  (PYTHONIOENCODING=utf-8 for 61-126 and the 1-60 rerun; private COVERAGE_FILE)
  1-60:    13 · killed 12 · survived 1
  61-126:  35 · killed 35 · survived 0
  127-189: 27 · killed 27 · survived 0
  190-245: 25 · killed 23 · survived 2
  246-292: 17 · killed 16 · survived 1        total 117 · killed 113 · timeout 0 · survived 4

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_item_manager.py -q -p no:cacheprovider --cov=app.managers.machine_item_manager --cov-branch --cov-report=term-missing
  app\managers\machine_item_manager.py      78      0     24      0   100%
  279 passed, 199 xfailed, 2 xpassed

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_item_manager.py -q -p no:cacheprovider --runxfail -rf
  199 failed, 281 passed

PGOPTIONS="-c enable_seqscan=off"                                  279 passed, 199 xfailed, 2 xpassed
PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off"       279 passed, 200 xfailed, 1 xpassed
-W error                                                           129 failed, 150 passed, 199 xfailed, 2 xpassed (LegacyAPIWarning)
MIMREF=fix ... -p ref_mim --runxfail                               480 passed
rebuild.py                                                         2 533 Then lines, no real difference
selftest.py                                                        600 planted, 600 found
.venv/Scripts/python.exe -m ruff check tests/unit/managers/test_machine_item_manager.py     All checks passed!
git diff --stat app/managers/machine_item_manager.py                                        (empty)
```
Scratch, all under `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\mimv\`: `plug\` (`ref_mim.py`, `ref_manager.txt`, `ref_dao.txt`, `ref_schema.txt`, `variants.py`, `today_mut.py`), `prop\test_mim_prop.py`, `variants.json`, `drive.py`, `rebuild.py`, `selftest.py`, `xfloc.py`, `later.py`, `compact.py`, `mutchunks.sh`, `mut_*.json`, `mut_*.log`, `runx3.txt`.

Only this report was written in the repo. Nothing under `app/`, the spec, the cases file, the notes or the test file was edited. No commit. No model server.

## Fix list
1. **Case designer:** add cards for findings 1–4, about 7; the scratch tests above are the recipes. The 13 schema lines are optional.
2. **Executor,** after 1: implement them and send back for a scoped re-verification.
3. **Tool owner:** finding 5.
