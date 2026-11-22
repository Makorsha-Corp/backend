# Verification — `app/managers/machine_activity_manager.py`

> **Verdict:** PASS (round 2, 2026-11-01) — M1 and M2 are closed, and the 3 changes in scope are faithful. Scoped round: no full mutation.
> Tests: 156 passed · 12 xfailed · 2 XPASS (reproduced ✅) · coverage 100% branch (59 statements, 18 branches)
> Mutation: 55 / 55 = 100%, from round 1; not re-run, on the coordinator's instruction
> Source commit: e48a092 · Cases revision: 1 (170 cases; spec APPROVED)
> Round 1 is below, kept as written.

## Round 2 (2026-11-01) — scoped to `standing_rows`, MAC-LE-33, MAC-GS-21

- **Read:** `standing_rows` is autouse, skips tests with no `db`, and requests `m9`, the end of the fixture chain, so every database test builds all standing rows in Conventions order. LE-33 and GS-21 match their cards line by line, with no marker. Both are `# [claude]`.
- **Unfaithful in scope:** 0 of 3. M1's 5 tests are no longer affected: each now fails on the variant shown.

| Variant | Round 1, as written | Now fails |
|---|---|---|
| `li_r2_zero_first` | survived | LI-22, LI-23 T1 |
| `gs_r3_zero_first` | survived | GS-13 T1 |
| `li_ref_write` | LI-20 T4 only | LI-20, LI-21, LI-22, LI-23 T4 |
| `gs_ref_write` | GS-14 T4 only | GS-12, GS-13, GS-14 T4 |
| `le_r7_inactive_live` | survived | LE-33 call, only |
| `gs_r5_inactive_live` | survived | GS-21 call, only |

- **Count:** that is 4 setup variants covering round 1's 5 tests, plus the 2 of M2: 6 variants, all caught, no setup error.
- **Then lines:** GS-12, GS-13 T4 can now fail on their own, so 27 of the 31 lines past an xfail's failure point are forced. The other 4 are round 1's.
- **Runs:** 3 without `--runxfail` gave 156 passed, 12 xfailed, 2 XPASS, including coverage. `--runxfail` gave 12 failed, 158 passed. The reference gave 170 of 170. `ruff check` passes. `git diff --stat` on the manager and the DAO is empty.
- **Traceability:** rebuild: cards 170, tests 170, Then lines 350, no report. This matches the notes' Result line.
- **Open:** nothing. No money or order-workflow question. The owner items in round 1 stand unchanged.
- **Limits:** the other 168 tests were re-run and rebuilt, not re-read, and I kept no round 1 copy to diff against. Mutation and the other 244 variants were not re-run on the new fixture; the suite passes with it, and round 1's `MACALL=1` runs gave the same outcomes.

Scratch: `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\macv\r2.json`. Only this report was written in the repo. No commit. No model server.

---

The sections below are round 1 (2026-10-31), kept as written.

> **Verdict:** NEEDS WORK (2026-10-31) — two small items: one setup fault for the executor, one pair of missing cards for the case designer. No test asserts a wrong value.
> Tests: 154 passed · 12 xfailed · 2 XPASS (reproduced ✅) · coverage 100% branch (59 statements, 18 branches)
> Mutation: 55 mutants · 55 killed · 0 survived → score 100% (55 / 55; none excluded)
> Fidelity: **5 of 168 unfaithful**, one cause (Given not fully built). The other 163 match their cards.
> Hand variants on my reference: 250 · 241 caught · 9 survived (2 finding M1, 2 finding M2, 5 no finding)
> Source commit: e48a092 · Cases revision: 0 (168 cases; spec APPROVED)

## Summary
- **Given, When and Then text matches the cards.** I read all 168 tests against their cards. Each When call and numbered Then line is the card's, in order, and every written Given row is built. A separate rebuild from the cards agrees on all 346 Then lines and finds 259 of 259 planted mistakes.
- **The one fidelity fault is in the fixtures.** Conventions put every standing row "in every test". The fixture chain builds only the rows up to the one a test names. Outcomes do not change today, but 5 tests can miss a broken fix because W1 has no machine in them.
- **The evidence goes beyond reading.** My own reference passed 168 of 168 on its first run. All 12 strict xfails fail where their cards say, none on a setup error. Mutation killed all 55, each by a real test failure.
- **Why NEEDS WORK:** finding M1 (executor) and finding M2 (case designer). Each is small. Fixing M1 changes no outcome: with all rows built, today's source gives 154 / 12 / 2 and the reference gives 168 of 168.
- **No money or order-workflow question arises.**

Written by Claude: all 168 sit under `# [claude]`. No `machine_activity_manager.local-run.json` exists, so there is no `## Local-coder patterns` section. Findings in local-written tests / local-written tests: 0 / 0. In others: 5 / 168.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| M1 | wrong setup | MAC-LI-21, LI-22, LI-23, GS-12, GS-13; cause in the fixtures (file lines 82–156) | Conventions: standing rows exist "In every test". These 5 ask only for `w1`, so no machine exists at all. Variants that misbehave only for an unknown or non-positive id pass them, and their `nothing written` line cannot notice a row, because there is no machine to write it on. | See "M1 in numbers" | **executor** |
| M2 | case-missing (low) | `log_event` R1, R6; `get_latest_status` R1, R2, R3 | Only a machine outside the workspace is refused or gets the 404, so an inactive, live machine must work. Neither method has a card with MA. `list_events` has MAC-LI-29 and the map has MAC-SM-01, SM-04. MD is `is_active False` too, but it is soft-deleted, so a check of `is_active` on live machines only slips past LE-23, GS-18. | `le_r7_inactive_live`, `gs_r5_inactive_live` survive. One scratch test closes each | **case designer** |

### M1 in numbers
- 119 of the 168 tests use the database. 11 build every standing row; 108 build fewer; 7 of those 108 build no machine (LE-20, LE-21, LI-21, LI-22, LI-23, GS-12, GS-13). The notes describe the chain, but not that rows are missing.
- Plugin switch `MACALL=1` builds all standing rows in every database test:

| Variant | As written | All rows built |
|---|---|---|
| `li_r2_zero_first`: id ≤ 0 takes the workspace's first machine | **survives** | LI-22, LI-23 T1 |
| `gs_r3_zero_first`: the same in `get_latest_status` | **survives** | GS-13 T1 |
| `li_ref_write`: a refusal also writes a row | LI-20 T4 only | adds LI-21, LI-22, LI-23 T4 |
| `gs_ref_write`: the same in `get_latest_status` | GS-14 T4 only | adds GS-12, GS-13 T4 |

- LE-20 and LE-21 are not counted: a variant there still fails on the foreign key or is rolled back by the card's own savepoint, so the missing row changes nothing I could measure. The other 101 partial tests showed no effect, but I measured that only through the 248 variants, not test by test.
- Suggested fix: an autouse fixture that requests `m9` for tests with `db`. The cards need no change.

### Scratch tests that close M2
Two tests in `prop\test_mac_prop.py`, not in the repo. Both pass on the reference; each fails only on its variant.

| Scratch test | Fails on |
|---|---|
| `log_event` on MA stores the row | `le_r7_inactive_live` |
| `get_latest_status` on MA returns its status row | `gs_r5_inactive_live` |

## Questions for the owner
None. Nothing here touches a figure, stock or an order state. M2 is a rule already written, not a decision.

Carried, unchanged, from the spec: the Q6 read-only query has not been run on production. Q2–Q6 are recorded as delegated decisions, and Q1 as the owner's answer relayed by the main session; I checked the tests against the spec's wording, not the answers themselves.

## Surviving mutants
None. All 55 were killed, so no class is used.

- Each kill's last line reads `1 failed`, with no setup error, and the number of tests passed before it fits the card expected for that line (for example #39, `limit` 101, stops at MAC-LI-35).
- `mutate.py` does not mutate keyword arguments of calls. The hand variants cover those (`li_r1_skip`, `li_r1_limit`, `li_r1_from`, `li_r1_to`, `li_r1_type`, `le_r1_perf`, `le_r1_meta`).

## Hand variants
Run on the reference with `--runxfail`. Each edit is asserted to apply, so no variant is a silent no-op. No run had a setup error. "T" = the Then line that failed; "When" = the call of a pass card.

| Method | Variants | Caught | Survivors |
|---|---|---|---|
| `format_field_value` | 17 | 17 | none |
| `collect_field_changes` | 31 | 31 | none |
| `log_event` | 53 | 50 | `le_r7_inactive_live`, `le_r1_ws`, `le_r8_member` |
| `list_events` | 66 | 65 | `li_r2_zero_first` |
| `get_latest_status` | 35 | 33 | `gs_r5_inactive_live`, `gs_r3_zero_first` |
| `get_latest_status_map` | 33 | 31 | `sm_r1_outtype`, `sm_r1_outws` |
| `status_from_activity` | 15 | 14 | `sa_r2_isnone` |

**Survivors with no finding:**

| Variant | Class | Why |
|---|---|---|
| `le_r1_ws` | equivalent | Takes the row's workspace from the machine. Once the check has passed, the two are the same value. |
| `le_r8_member` | further shape, covered | Refuses a performer new to a workspace that already has performers. LE-27 covers the rule, with no earlier rows. My variant is contrived to get past it. |
| `sm_r1_outtype`, `sm_r1_outws` | covered at the DAO | A row of another type or workspace with the same `created_at`. Run on `tests/unit/dao/test_machine_activity_event.py`, each fails exactly one card: MAE-LM-08, MAE-LM-10. The cases file defers this detail. |
| `sa_r2_isnone` | Spec gap 1, already filed | `{}` gives `None` either way. It differs only for `[]` and `""`, which the cases file already lists as Spec gap 1 and no writer stores. |

**Caught, by rule (every catch was read; each lands on the card for its rule):**

| Rule | Caught by |
|---|---|
| `log_event` R6 | off LE-18 … LE-22 T1 · any workspace LE-18, 19, 22 T1 · foreign only LE-20, 21 T1 · 400 T2 on all five · 403 for foreign LE-18, 19, 22 T2 · message T3 · added first LE-18, 19 T4 · flushed first LE-18, 19 T5 |
| `log_event` R1–R5, R7–R10 | LE-01 … LE-17, LE-23 … LE-32, each on its own line; a `WITH … UPDATE` hidden from `written` fails LE-04 T5, T6, T7 alone |
| `list_events` R2 | off, wrong code, wrong text LI-20 … 24 · read before the check LI-20 T4, only · 0 and −1 special cases LI-22, LI-23 |
| `list_events` R4 | soft-deleted, factory, inactive LI-27, LI-28, LI-29, one each |
| `list_events` R7, R9 | wrong person LI-33, 45, 46 · copied instance LI-34, 46 · one read per entry LI-42, 44, 45 · per person LI-45 T3, only |
| `list_events` R10 | flush LI-47 T2 · a commit LI-47 T2, by flushing the pending row · insert T4 · update T5 · no-change update T6 · lock T7 |
| filters before paging | type LI-16, date LI-17, machine LI-18, workspace LI-26, each the card meant for it |
| `get_latest_status` R3, R4 | off GS-12 … 15 · foreign only GS-12, 13 · unknown only GS-14, 15 · lets an invalid row through GS-15, only |
| `get_latest_status_map` R1–R4 | SM-01 … SM-18; ids descending SM-12, SM-13 T3; no `ORDER BY` SM-14 T3; no id in it SM-14 T4; invalid row hidden SM-16, only |
| `collect_field_changes`, `format_field_value`, `status_from_activity` | every rule by its own cards, down to one each for R2 order, R7 compare, R9 write, R9 dirty |

## xfail tests against the reference
`plug\ref_mac.py` is a pytest plugin that swaps the source of `app.managers.machine_activity_manager` and `app.dao.machine_activity_event` in memory through a meta-path finder, by asserted text edits. Nothing is written to `app/`. It is my own fix, not the executor's: `log_event` checks the machine first; `list_events` reads performers in one `IN` query; `get_latest_status` raises 404; the map orders by `created_at, id`.

**168 passed** with `--runxfail`. With the markers on, the 12 strict cards turn `XPASS(strict)` and SM-12, SM-13 XPASS, so no pass card pins a bug.

### The Then lines past each failure point
- 12 strict xfails have **31 Then lines after the failing line**. None runs today. All 31 pass on the reference.
- **25 were made to fail on their own line** by a variant, 27 once M1 is fixed (GS-12, GS-13 T4).
- **4 cannot fail on their own:** LE-20, LE-21, LE-22 T4 (the card's savepoint rolls any write back) and LE-18 T6 (T5 already covers it: no row exists before).
- SM-12, SM-13 T4 follow from their T2 and T3. Both run today; they are not among the 31.

## Reproduced claims
- The notes' Result line matches: 154 passed, 12 xfailed, 2 XPASS, 100%.
- **All 12 strict xfails fail where the card says**, mapped to their `# Then N`: LE-18, LE-19, GS-12 … GS-15 at T1 `DID NOT RAISE`; LE-20, LE-21 at T1 on the `machine_id` foreign key error, LE-22 at T1 on the `workspace_id` one; LI-44 at T3 `7 <= 3`; LI-45 at T3 `6 <= 3`; SM-14 at T3 with no `ORDER BY`. None is a setup error.
- **No flaky test.** 5 default runs (coverage, 2 plain, `-W error`, `enable_seqscan=off`) gave the same result. 2 runs with `--runxfail` gave 12 failed, 156 passed.
- **SM-12 follows the plan, as the notes say.** With index scans off it xfails (154 / 13 / 1). It is non-strict, so this is not a flaky test.
- Mocks: none. The only spy is the commit spy of MAC-LE-32, as Conventions name. No broad `pytest.raises`, no `try` around an action (the one `try` is `sql_recorder`'s cleanup).

## Traceability
cases 168 · tests 168 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match in all 168. 154 `pass` cards have no marker; 12 are `strict=True` and 2 (SM-12, SM-13) `strict=False`, each naming the card's bug. BUG-1090, BUG-1091, BUG-1140, BUG-1141 are all in `docs/testing/bugs.md`. `ruff check` passes. Counts per callable add up to 168, and the 10 deferred rows are all there.

## Limits of this round
- **The reference is one fix, mine.** Variants show what these tests catch around it. Another correct fix could expose a card that assumes something mine happens to do. The cases file names one already: a BUG-1090 fix with no `ORDER BY` leaves SM-14 xfailing (Spec gap 2).
- **Pass-card Then lines were not each forced to fail.** They rest on reading, mutation and the variants.
- **`rebuild.py` is an extra check**, written from the cards. Its first two reports were its own faults, corrected. After the first selftest missed 8 of 259, I added a count of Given builders. It compares text, so it cannot judge meaning.
- **Runs were not isolated.** Other agents may have been running, and my own pytest runs overlapped the mutation run. No kill shows a setup error.
- Not exercised: service or HTTP level, a real race, production data.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/machine_activity_manager.py tests/unit/managers/test_machine_activity_manager.py --timeout 300 --json <scratch>/mut.json
  Mutants: 55 · killed 55 · timeout 0 · survived 0 · score 100%

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_activity_manager.py -q -p no:cacheprovider --cov=app.managers.machine_activity_manager --cov-branch --cov-report=term-missing -rX
  app\managers\machine_activity_manager.py     59      0     18      0   100%
  154 passed, 12 xfailed, 2 xpassed, 15 warnings

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_activity_manager.py -q -p no:cacheprovider --runxfail -rf
  12 failed, 156 passed

same file, --tb=no, twice                        154 passed, 12 xfailed, 2 xpassed
-W error                                         154 passed, 12 xfailed, 2 xpassed
PGOPTIONS seqscan off                            154 passed, 12 xfailed, 2 xpassed
PGOPTIONS index, bitmap, index-only off          154 passed, 13 xfailed, 1 xpassed

MACREF=fix ... -p ref_mac --runxfail             168 passed
MACREF=fix ... -p ref_mac                        12 failed (XPASS strict), 154 passed, 2 xpassed
MACALL=1 ... -p ref_mac                          154 passed, 12 xfailed, 2 xpassed
MACALL=1 ... -p ref_mac --runxfail               12 failed, 156 passed
MACALL=1 MACREF=fix ... --runxfail               168 passed

drive.py all                                     248 · caught 240 · survived 8 · broken 0 · setup errors 0
drive.py (setup variants, with and without MACALL=1): table under M1; adds gs_r3_zero_first, li_ref_write
MACREF=fix MACVAR=sm_r1_outtype | sm_r1_outws, on the DAO test file --runxfail    1 failed, 80 passed (each): MAE-LM-08 | MAE-LM-10
rebuild.py                                       cards 168 · tests 168 · Then lines 346 · reports 0
rebuild.py --selftest                            planted 259 · found 259
.venv/Scripts/python.exe -m ruff check tests/unit/managers/test_machine_activity_manager.py     All checks passed!
git diff --stat app/managers/machine_activity_manager.py                                        (empty)
```
Scratch, all under `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\macv\`: `plug\ref_mac.py`, `plug\variants.py`, `drive.py`, `drive.log`, `variants.json`, `macall.json`, `nomacall.json`, `liw.json`, `liw_all.json`, `xf.json`, `rebuild.py`, `prop\test_mac_prop.py`, `mut.json`, `mut.log`.

Only this report was written in the repo. Nothing under `app/`, the spec, the cases file, the notes or the test file was edited. No commit. No model server.

## Fix list
1. **Executor:** finding M1: build all standing rows in every test that uses `db`. Update the notes.
2. **Case designer:** finding M2: one card each for an inactive machine on `log_event` and `get_latest_status`.
3. **Executor,** after 2: implement the two cards and send back for a scoped re-verification.
