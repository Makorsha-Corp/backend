# Verification — `app/dao/machine_maintenance_log.py`

> **Current verdict: PASS** (round 2, 2026-10-31, revision 1, 183 cases). See "Round 2" at the end. The rest of this block is round 1.
>
> **Round 1 verdict:** NEEDS WORK — the tests are right; 6 rule gaps need 12 new cards (case designer, one line for the describer first). No test edited.
> Tests: 151 passed · 17 xfailed, 12 strict, 5 non-strict (reproduced ✅) · coverage 100% branch (35 statements, 0 branches)
> Mutation: 37 mutants · 37 killed · 0 survived → score 100% (37 / 37, after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 168 unfaithful** (168 / 168 right)
> Hand variants: 206 · 188 caught, 18 survived: 12 are the 6 findings, 2 equivalent, 4 further shapes with no finding
> Source commit: e48a092 · Cases: 168 cases, READY; spec APPROVED

## Summary
- **The tests can be trusted for what their cards say.** I read all 168 against their cards, and a rebuild of my own that shares nothing with the executor's parser agrees. Nothing extra is mocked, and no assert is vacuous by mistake.
- **The evidence goes beyond reading.** A reference fix of BUG-1100, BUG-1101 and BUG-1102 passes 168 of 168, twice. All 17 xfails fail on the Then line their card names, by assertion.
- **Why NEEDS WORK:** the mutation score says little here, because the module has no branches and a mutant cannot move a filter. Hand variants show 6 places where a written rule can break and no card notices. The two that matter most: the four "takes no place in the page" cards do not prove the filter runs before paging, and `soft_delete` can stamp `updated_by` unnoticed, because SD-03 and RS-09 delete as the same profile that is already in `updated_by`.
- **Cost holds up well.** 19 of 20 cost variants are caught, including every wrong rounding mode. The one survivor is Finding 6.
- **No fix was test-side.** All 6 are cards that do not exist, so the test file is unchanged.

**For the owner, not decided here:** FU-1 (d), a negative `cost`, and FU-1 (g), the activity entry records `cost` as typed. Both stay OWNER, for the manager review. Finding 6 pins inherited R4 as written and does not touch either question.

Written by Claude (all 168 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 168. No `machine_maintenance_log.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence (survives every test) | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_workspace` R2 "the filter runs before `skip` / `limit`"; `get_by_machine` R3; `get_by_type` R1; `get_by_machine_and_type` R1 | GW-05, GM-06, GT-06, GP-07 put the gone row **after** the skipped row, so a Python filter after paging gives the same `[C]`. A gone row inside the skipped part is never tried. | `get_by_workspace:page_del`, `get_by_machine:page_del`, `get_by_type:page_del`, `get_by_machine_and_type:page_del` | **case designer** |
| 2 | case-missing | `soft_delete` R2 "no `updated_by` stamp" | SD-03 has `updated_by P2.id` and deletes with `deleted_by=P2.id`, and RS-09 does the same, so the stamp writes the value already there. No other card reads `updated_by` after a delete. | `sd:stamp_updated_by` | **case designer** |
| 3 | case-missing | `get_by_machine` R6, `get_by_type` R4, `get_by_machine_and_type` R4, each following `get_by_workspace` R5 ("with `limit=1000`, 101") | Only GW-13 goes past 100. The manager passes up to 1000, so a cap of 100 in these three lists cuts results silently. | `get_by_machine:cap100`, `get_by_type:cap100`, `get_by_machine_and_type:cap100` | **case designer** |
| 4 | case-missing | `get_by_type` R5 "as `get_by_workspace` R8" (takes no place in the page) | GT-22 has no paging. GW-25 is the only such card, and this list has its own query. | `get_by_type:page_link` | **case designer** |
| 5 | spec-gap, then case-missing | `soft_delete` Side effects "no activity event"; `restore` R2 "no activity row is added" | The cases file's Spec gap 1: the table is not named, so no card counts it. The table is `machine_activity_events`. | `sd:activity`, `rs:activity` | **describer** (name the table), then **case designer** |
| 6 | case-missing (cost) | inherited R4 "keeps the value as given until `db.refresh`", "Nothing is rounded in Python" | INH-14 checks this for `create` only; INH-15 checks `update` by stored value. A Python half-up rounding in `update` stores the same number and changes the object. FU-1 (g) reads that object, so the difference reaches the activity entry. | `cost:py_round_update` | **case designer** |
| 7 | notes correction (low) | `machine_maintenance_log.notes.md` | The Result line, the Discrepancies section and the proof tables still read 150 passed, 18 xfailed and "167 passed, 1 failed". The closing section corrects the counts, so nothing is wrong in substance. | The runs below | **executor** |

No fidelity finding. The other spec gaps in the cases file are unchanged.

### Scratch tests that close the gaps
12 tests in `mmlv\prop\test_mml_prop.py`, not in the repo. All 12 pass on the reference. Each variant named fails exactly the card shown, by assertion.

| Recipe | Given → expected | Expect | Fails on |
|---|---|---|---|
| P1 … P4 | gone log on D3, then B on D2, C on D1; each list with `skip=1` gives `[C.id]` | pass | the `page_del` of that list |
| P5 | A on D1, X = log on M9 on D3; `get_by_type(skip=1) == []` | strict BUG-1101 | `get_by_type:page_link` |
| P6 … P8 | 101 dated logs; `limit=1000` on `get_by_machine`, `get_by_type`, `get_by_machine_and_type` gives all 101 | pass | the `cap100` of that list |
| P9 | A with `updated_by P2.id`; `soft_delete(deleted_by=P1.id)`; re-read `updated_by == P2.id` | pass | `sd:stamp_updated_by` |
| P10, P11 | after `soft_delete`, after `restore`: `machine_activity_events` rows for M1 is 0 | pass | `sd:activity`, `rs:activity` |
| P12 | A with `cost 5.00`; `update` with `0.125`; `result.cost == Decimal("0.125")`, then after `db.refresh` `Decimal("0.13")` | pass | `cost:py_round_update` |

On today's code: 11 pass, and P5 fails on its assertion, as a strict BUG-1101 card should.

## Surviving mutants
None. 37 of 37 killed, and every kill ends in `N failed`, so none is an error or a clash with another run.

Score: 37 / (37 − 0 − 0 − 0) = 37 / 37 = **100%**.

## Hand variants
Each ran on the reference with `--runxfail`. Every edit is asserted to apply once, and all 206 compile.

| Group | Variants | Caught | Survivors |
|---|---|---|---|
| `get_by_workspace` | 27 | 26 | Finding 1 |
| `get_by_machine` | 29 | 25 | Findings 1, 3; 2 below |
| `get_by_type` | 30 | 27 | Findings 1, 3, 4 |
| `get_by_machine_and_type` | 32 | 27 | Findings 1, 3; 3 below |
| `get_by_id_and_workspace` | 10 | 9 | 1 below |
| `soft_delete` | 24 | 22 | Findings 2, 5 |
| `restore` | 16 | 15 | Finding 5 |
| inherited, `app/dao/base.py` | 12 | 12 | — |
| cost: 7 rounding modes, sign, zero, NaN, range, float read, Python rounding, schema | 20 | 19 | Finding 6 |
| other columns | 6 | 6 | — |
| **Total** | **206** | **188** | **18** |

The list variants cover: dropped workspace, machine, type and soft-delete filters; `is_active` in place of `is_deleted`; parent-state filters; wrong or missing order and tie-break; caps, clamps and swapped paging; a Python filter after paging; a flush in a read; a read that writes X. `soft_delete` clock variants (`func.now()`, local, stdlib UTC, aware, shifted) are all caught by SD-02 and SD-05 on Then 3.

**Survivors with no finding, and why:**

| Variant | Class | Why |
|---|---|---|
| `get_by_machine:page_link`, `get_by_machine_and_type:page_link` | equivalent | For one machine and one workspace, the matching rows are either all linked or all not, so filtering after paging gives the same list. |
| `get_by_id_and_workspace:factory_active`, `get_by_machine:factory_active`, `get_by_machine_and_type:factory_active` | further shape | The rule is covered for a soft-deleted machine and factory (GI-07, GI-08, GM-07, GM-08, GP-17, GP-18). The `Factory.is_active` filter is seen only by GW-06 and GT-14, because FD stays active. **My call:** GI R5 does say "state", so this is the closest one to a finding. One card on MG per reader closes it. |
| `get_by_machine_and_type:type_upper` | further shape | GP-10 covers "any other string" with `"BOGUS"`. Lower case has its card on the sister list, GT-10. |

**Caught by a non-assertion error:** 17 variants. All are real: a raised error where the card wants a result or another error type, or a `commit` that closes the card's savepoint (`ResourceClosedError`). None is a crash of my own variant. `cost:nan_none` is caught by an `AttributeError` on `row.cost.is_nan()`, which is the card's line reading `None`.

## Non-strict cards
| Run on today's code, `--runxfail` | Result |
|---|---|
| Explicit tie order `id ASC` in every window | GW-09, GM-10, GT-12, GP-15 fail on Then 2; GW-11 on Then 3 |
| `id ASC` for `skip < 2`, `id DESC` from `skip = 2` | all 5 fail on Then 2 |

The second row is the proof for all five, and it does not depend on plan or heap. In both rows 17 cards fail, the same 17, and no pass card fails. This matches the notes' table, except that RS-03 no longer appears, as its fix explains. No XPASS in 3 default runs or in 2 runs with a changed plan.

## xfail tests against the reference
`mmlv\plug\ref_mml.py` swaps the source of four `app` modules in memory, through a meta-path finder, built by asserted text edits in `refsrc_mml.py`. Nothing is written to `app/`. It orders by date then `id` descending, adds a correlated `EXISTS` on the machine's workspace to all five reads, and writes `deleted_at = utcnow()`, imported as `app/dao/machine.py` does.

**168 passed**, twice with `--runxfail`: every xfail passes in full, and no pass card pins a bug.

## Reproduced claims
| Cards | Strict | Card says | Seen, 3 of 3 runs |
|---|---|---|---|
| GW-10, GM-11, GT-13, GP-16 | yes | Then 4 | Then 4 |
| GW-24, GW-25, GT-22, GM-20, GP-25 | yes | Then 3 | Then 3 |
| GI-09 | yes | Then 2 | Then 2 |
| SD-02, SD-05 | yes | Then 3 | Then 3 |
| GW-09, GW-11, GM-10, GT-12, GP-15 | no | Then 2 | Then 2 |

- All 17 are `AssertionError`; no setup or import error.
- **No flaky test.** The same result in all 3 default runs, the 2 runs with a changed plan and the 3 `--runxfail` runs on today's code.
- Mocks: only the `clock` patch and the commit spies, which wrap the real `db.commit`. No `try`, no broad `pytest.raises`, no `if` in a test body.
- **RS-03 is not vacuous.** `rs:touch` fails it on Then 2, so the recorder does see the `UPDATE`.
- The closing section of the notes holds: 151 passed, 17 xfailed. Its earlier sections are Finding 7.

## Traceability
cases 168 · tests 168 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card in all 168, 461 Then lines. 151 `pass` cards have no marker; 17 xfail cards name exactly the card's bug, 12 strict, 5 non-strict. BUG-1100, BUG-1101, BUG-1102 are in `docs/testing/bugs.md`. Cards deferred to `base.cases.md` (BASE-R-03, BASE-G-02, BASE-GM-04) exist. `ruff check` passes.

## Limits of this round
- **Rebuild.** It compares Given builders, When calls, Then lines and markers. Its one report is its own: it cannot parse RS-03's Given sentence, which the test has right (`db.refresh(a)`). It found 308 of 319 planted mistakes in 10 kinds. The 11 misses are in things it does not parse, such as `count_rows` filter text, `len(...)` and `without(...)` column lists. Those rest on my reading.
- **Later Then lines were not each forced.** Variants fail a card on its first broken line. The later lines rest on reading and on the reference passing them.
- **The reference is one fix, mine.** Variants show what these tests catch around it. Another correct fix could expose a card that assumes something mine does. A fix in a subquery or alias would need the recorder lines changed (cases Spec gap 5).
- **Column limits were not changed in the database.** Cost variants act in Python, at the bind or on the object. No variant altered `Numeric(15, 2)`, because DDL would lock the table against other agents' runs. Column range is held by INH-16 … INH-19 on `create` only; `update` beyond the range has no card, which I count as a further shape.
- **Runs were not isolated.** Other agents' pytest runs were live. It does not matter here: every mutant kill is a plain `N failed`, and my variants took no long locks.
- Not exercised: anything at manager, service or HTTP level; a real race; a real hard delete of a workspace with its own machines. The notes report that a BUG-1101 row can refuse such a delete; no rule says so, and inherited R14 could note it.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/machine_maintenance_log.py tests/unit/dao/test_machine_maintenance_log.py --timeout 300 --json <scratch>/mut.json
  Mutants: 37 · killed 37 · timeout 0 · survived 0 · score 100%
  every kill's last line: "N failed, ..."

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine_maintenance_log.py -q -p no:cacheprovider --cov=app.dao.machine_maintenance_log --cov-branch --cov-report=term-missing --tb=no
  app\dao\machine_maintenance_log.py      35      0      0      0   100%
  151 passed, 17 xfailed, 2 warnings      (and twice more without coverage)

--runxfail through the plugin, 3 runs                           17 failed, 151 passed
MMLREF=fix -p ref_mml --runxfail                                168 passed (twice)
MMLORDER=asc / MMLORDER=split --runxfail                        17 failed, 151 passed (each)
PGOPTIONS="-c enable_seqscan=off"                               151 passed, 17 xfailed
PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off"    151 passed, 17 xfailed
drive.py variants                                               206 run, 188 caught, 18 survived
prop: today                                                     11 passed, 1 xfailed
prop: MMLREF=fix --runxfail                                     12 passed
prop: drive.py on the 12 finding survivors                      each fails exactly its card
trace.py     cards 168 · tests 168 · same order · 461 Then lines · 1 report (tool's own)
selftest.py  319 planted, 308 found
.venv/Scripts/python.exe -m ruff check tests/unit/dao/test_machine_maintenance_log.py     All checks passed!
git diff --stat -- app/dao app/models app/schemas               (empty)
```
Scratch, all under `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\mmlv\`: `plug\ref_mml.py`, `plug\refsrc_mml.py`, `plug\variants_mml.py`, `prop\test_mml_prop.py`, `drive.py`, `checkv.py`, `trace.py`, `selftest.py`, `variants.json`, `variants.log`, `prop.json`, `mut.json`, `mut.log`, `test_machine_maintenance_log.delivered.py`.

Only this report was written in the repo. Nothing under `app/`, the spec, the cases file, the notes or the test file was edited; the test file is byte-identical to the delivered copy. No commit. Nothing was stopped or killed.

## Fix list
1. **Describer:** name `machine_activity_events` in the spec (Finding 5).
2. **Case designer:** add 12 cards for Findings 1–6; the recipes above are the Givens and Thens. Optional: one card on MG per reader for the `factory_active` survivors.
3. **Executor,** after 2: implement them, correct the notes (Finding 7), and send back for re-verification.

## Round 2 — 2026-10-31 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 165 passed · 18 xfailed, 13 strict, 5 non-strict (reproduced ✅) · coverage 100% branch (35 statements, 0 branches)
> Mutation: not re-run, as asked; round 1 stands at 37 / 37 → 100%
> Fidelity: **0 of 15 new tests unfaithful**
> Hand variants: the 12 finding survivors and the 3 `factory_active` survivors all fail now; the other 188 not re-run
> Source commit: e48a092 · Cases revision: 1 (183 cases; spec APPROVED)

Findings 1–7 are closed, and so is my `factory_active` call. No test edited in this round, no commit.

### What changed since round 1
A line diff against my saved copy of the delivered file shows 15 added tests and one helper, `count_activity`, the same raw count on `machine_activity_events`. No existing test body changed. Mutation runs tests, not cards, so adding 14 pass tests cannot lower a score that had no survivor.

### The 15 new tests
Each was read against its card: every Given row, the When call, every Then line, the marker. All 15 are right.

| Finding | Cards | Marker | Variants that now fail |
|---|---|---|---|
| 1 | GW-26, GM-24, GT-23, GP-26 | pass | each list's `page_del`, on Then 1, on that card only |
| 2 | SD-12 | pass | `sd:stamp_updated_by`, Then 3 |
| 3 | GM-25, GT-24, GP-27 | pass | each list's `cap100`, Then 1 |
| 4 | GT-25 | strict BUG-1101 | `get_by_type:page_link`, Then 3 |
| 5 | SD-13, RS-10 | pass | `sd:activity`, `rs:activity`, Then 3 |
| 6 | INH-45 | pass | `cost:py_round_update`, Then 2 |
| `factory_active` | GI-10, GM-26, GP-28 | pass | each reader's `factory_active`, Then 1 |

All 15 variants fail on an assertion, and on the new card alone. GT-25 fails today on Then 3, as its card says, with `AssertionError`.

**Still surviving, no finding:** `get_by_machine:page_link` and `get_by_machine_and_type:page_link` (equivalent, argued in round 1) and `get_by_machine_and_type:type_upper` (further shape, unchanged).

### Reference and xfails
- **Reference: 183 passed, twice** with `--runxfail`.
- **All 18 xfails fail where the card says,** in 3 of 3 `--runxfail` runs on today's code, all `AssertionError`. No pass card is red.
- **All 5 non-strict cards are proven on Then 2** under the split explicit wrong order: 18 failed, 165 passed, the same 18.
- **No flaky test.** 165 passed, 18 xfailed in 3 default runs and 1 run with a changed plan, with no XPASS.

### Closed outside the tests
- **Finding 5:** the spec's `soft_delete` Side effects and Gap log G1 now name `machine_activity_events`.
- **Finding 7:** the notes' Result line reads 165 passed, 18 xfailed. The 150 / 18 figure stays only in the Revision history, where it belongs.
- **Round 1's "Not exercised" line:** the BUG-1101 row that refuses a workspace delete is now in the spec, as Gap log G2.

**Small mismatch, no action needed:** the cases header says "the spec did not change", but the spec has the G1 and G2 lines. Both are facts with no new rule, and no card depends on the difference.

**Money, unchanged:** FU-1 (d) and FU-1 (g) stay OWNER for the manager review. INH-45 pins inherited R4 and decides neither.

### Limits of this round
The rebuild reads all 183 cards. Its 3 reports are its own: RS-03's Given sentence from round 1, and the Then 3 of SD-13 and RS-10, because it looks for `count_rows` and those lines use `count_activity`. Both were read by hand and are right. Other agents' runs were live; nothing was stopped or killed.

### Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine_maintenance_log.py -q -p no:cacheprovider --cov=app.dao.machine_maintenance_log --cov-branch --cov-report=term-missing --tb=no
  app\dao\machine_maintenance_log.py      35      0      0      0   100%
  165 passed, 18 xfailed, 2 warnings      (and twice more without coverage)
--runxfail through the plugin, 3 runs                           18 failed, 165 passed
MMLREF=fix -p ref_mml --runxfail                                183 passed (twice)
MMLORDER=split --runxfail                                       18 failed, 165 passed
PGOPTIONS="-c enable_seqscan=off"                               165 passed, 18 xfailed
drive.py on 23 variants (the 15 above, 8 neighbours)            20 caught, 3 survived (listed above)
trace.py     cards 183 · tests 183 · same order · 489 Then lines · marker mismatches: none · 3 reports (tool's own)
.venv/Scripts/python.exe -m ruff check tests/unit/dao/test_machine_maintenance_log.py     All checks passed!
git diff --stat -- app/dao app/models app/schemas               (empty)
```
Scratch in `mmlv\`: `r2.json`, `r2today1.json` … `r2today3.json`, `r2split.json`.
