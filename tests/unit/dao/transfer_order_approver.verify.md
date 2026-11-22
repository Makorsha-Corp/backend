# Verification — `app/dao/transfer_order_approver.py`

> **Current verdict: PASS** (round 2, 2026-11-02, revision 1, 39 cases). See "Round 2" at the end. The rest of this block is round 1.
>
> **Round 1 verdict:** NEEDS WORK — only the case designer has work: 4 rule gaps, closed by 4 recipes. No test is wrong.
> Tests: 32 passed · 3 xfail, 1 strict, 2 non-strict (reproduced ✅) · coverage 100% branch (10 statements, 0 branches)
> Mutation: 7 mutants · 7 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 35 unfaithful** (35 / 35 right)
> Hand variants: 112 · 89 caught by a pass card on every plan · 23 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases: 35 cases, READY; spec APPROVED

## Summary
- **The tests can be trusted as written.** The file implements its cards exactly. I read its normalised differences from the purchase file, which I read fully by eye: module constants, the order fixture, and any cards of its own. My own script then rebuilt every test's Given, When, Then and marker from its card and compared them by AST across all five files. Nothing is mocked and no assert is weaker than its card.
- **No shared mistake.** The five files came from one generator, so the helper section and row builders were compared too: after names are normalised they are one text in all five.
- **Why NEEDS WORK:** `mutate.py` has only 7 sites here, the five `==` and the two `return`, and all 7 die. It has no operator for `order_by`, for a subquery or for a pending object, so the hand variants carry those, and 4 rules have a broken shape that passes.
- **No money or order-workflow question arises.** These reads hold no money, and each gap is a missing test on a rule already decided. R8 is sound here: `completed_at` is `order_completed` on this model, and OC builds it.

Written by Claude (all 35 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 35. No `transfer_order_approver.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_order` R4 | In every pass card that mixes the two, the pending row is the earlier one (TOA-GO-01, GO-16, GO-17). No card has an approved row before a pending row, so a list that puts pending rows first keeps every pass card green. | `go_r4_pending_first` (`order_by(approved, assigned_at, id)`) passes all pass cards on all three plans. Only TOA-GO-12 T2 sees it, and that card is a non-strict xfail today, so nothing turns red. | **case designer** |
| 2 | case-missing | `get_by_order` R5 [BUG-1200] | The tied rows of TOA-GO-11, GO-12, GO-13 have ids, users and stamps that all rise together, so `id` is not the column that decides. A second sort key placed before `id` goes unseen, by the xfail cards too. | `go_r5_user_then_id`, `go_r5_approved_at_then_id`, `go_r5_assigned_by_then_id` pass every card on all three plans with `--runxfail`. `go_r5_approved_desc_then_id` is caught only by GO-14 T6, on the word `DESC`. | **case designer** |
| 3 | case-missing | `get_by_order_and_user` R2 "Nothing is created"; both readers, Side effects none | "Nothing written" counts stored rows, and the Conventions say a pending row does not count. A row added to the session and left for the caller's next commit passes every card. | `gu_r2_create_pending`, `go_w_add_pending`, `gu_w_add_pending_hit` pass every card on all three plans. TOA-GO-19 and GU-16 check that P stays pending, not that P is alone. | **case designer** |
| 4 | case-missing | `get_by_order_and_user` R5 "whether approved or pending, for someone who left" | TOA-GU-14 has only the pending row of someone who left. TOA-GO-16 has both, for the other reader. | `gu_member_hide_left_approved` passes every card on all three plans. This is the row that BUG-1201 says stays and counts. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\apv\prop\test_apv_prop.py`, not in the repo. Each passes on today's code and on the references `fix`, `fix_asc`, `fix_nulls`, on all three plans. Each named variant fails its recipe on all three plans.

| Recipe | Where | Given | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, `get_by_order` R4 | A = approver, `assigned_at T10`, but `approved True`, `approved_at T12`; B = approver, `assigned_at T11`, but `user_id U2.id` | `ids(result) == [A.id, B.id]` | pass | `go_r4_pending_first` |
| R-2 | new card, `get_by_order` R5 | A = approver, `assigned_at T11`, but `user_id U2.id`; B = approver, `assigned_at T11`, but `user_id U1.id`, `approved True`, `approved_at T12`, `assigned_by U3.id`; `db.expire_all()` | `ids(result) == [A.id, B.id]` | xfail BUG-1200 (non-strict): physical order gives the intended result today | the 4 of Finding 2 |
| R-3 | one Then line on GO-19 and GU-16; one new card | The line: `pending: len(db.new) == 1`. New card: GU-16's Given, with the When on U1 (the row exists), `result.id == A.id`, then the same line | as shown | pass | `gu_r2_create_pending`, `go_w_add_pending` (the two lines), `gu_w_add_pending_hit` (the card) |
| R-4 | new card, `get_by_order_and_user` R5 | left U2; A = approver, `assigned_at T10`, but `user_id U2.id`, `approved True`, `approved_at T12`; When on U2 | `result.id == A.id`, `result.approved is True` | pass | `gu_member_hide_left_approved` |

## Surviving mutants
None. All 7 kills end in a plain `1 failed`; no run errored, so the tool's repeat never applied.

Score: 7 / (7 − 0 − 0 − 0) = **100%**.

## Hand variants
Each ran on the reference with `--runxfail`, on three plans (default, sequential only, index only), every edit asserted to apply once and every run required to reach all 35 tests. "Pass card on every plan" leaves out GO-12, GO-13, GO-14, which are xfail today. The catches that are not assertions are the variant's own error, or `None.id` where a row is expected, on the line that reads the result.

| Rule group | Variants | Pass card, every plan | Cards that fail (default plan) | Others |
|---|---|---|---|---|
| `get_by_order` R1 | 10 | 10 | GO-01, GO-02, GO-03, GO-04, GO-05, GO-06, GO-07 … | — |
| R2 | 4 | 4 | GO-04, GO-05, GO-19 | — |
| R3 | 9 | 9 | GO-03, GO-05, GO-06, GO-07, GO-08, GO-09 | — |
| R4 | 9 | 8 | GO-01, GO-10, GO-11, GO-12, GO-13, GO-14, GO-15 … | `go_r4_pending_first` |
| R5 [BUG-1200] | 8 | 1 | GO-10, GO-11, GO-12, GO-13, GO-14 | `go_r5_approved_at_then_id`, `go_r5_approved_desc_then_id`, `go_r5_approved_then_id`, `go_r5_assigned_by_then_id`, `go_r5_id_desc`, `go_r5_user_no_id`, `go_r5_user_then_id` |
| R6 | 3 | 1 | GO-15 | `go_r6_cap_101`, `go_r6_cap_500` |
| R7 | 4 | 4 | GO-01, GO-02, GO-04, GO-10, GO-11, GO-12, GO-13 … | — |
| R8 | 2 | 1 | GO-17 | `go_closed_status_complete` |
| R9, writes, locks | 17 | 14 | GO-01, GO-15, GO-16, GO-18, GO-19 | `go_l_for_no_key`, `go_l_for_share`, `go_w_add_pending` |
| keyword-only | 1 | 0 | — | `go_kw_positional` |
| `get_by_order_and_user` R1 | 10 | 9 | GU-01, GU-02, GU-03, GU-04, GU-05, GU-06, GU-07 … | `gu_r1_one_or_none` |
| R2 | 11 | 10 | GU-03, GU-04, GU-05, GU-06, GU-07, GU-08, GU-10 … | `gu_r2_create_pending` |
| R3 | 4 | 4 | GU-09, GU-10, GU-16 | — |
| R5 member | 4 | 3 | GU-01, GU-02, GU-09, GU-13, GU-14, GU-15 | `gu_member_hide_left_approved` |
| R5 closed | 2 | 1 | GU-15 | `gu_closed_status_complete` |
| writes, locks | 13 | 10 | GU-03, GU-04, GU-05, GU-06, GU-07, GU-13, GU-16 | `gu_l_for_no_key`, `gu_l_for_share`, `gu_w_add_pending_hit` |
| keyword-only | 1 | 0 | — | `gu_kw_positional` |
| **Total** | **112** | **89** | | **23** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `go_closed_status_complete`, `gu_closed_status_complete` | Not this table's completion. `TransferOrder.order_completed` is `completed_at is not None`, which TOA-GO-17 and GU-15 build for real. Only purchase orders are seeded with a `Complete` status. |
| R5 shapes caught only by xfail cards: `go_r5_id_desc`, `go_r5_user_no_id`, `go_r5_approved_then_id` | **Bug path.** Caught by GO-12, GO-13 or GO-14 alone, which is what those cards are for. They turn into pass cards when BUG-1200 is fixed and the markers go. |
| `go_kw_positional`, `gu_kw_positional` | A note, not a rule: cases Spec gap 1. |
| `go_l_for_share`, `go_l_for_no_key`, `gu_l_for_share`, `gu_l_for_no_key` | Other shapes of the lock check, which looks for `FOR UPDATE`, under a clause outside the numbered rules (cases Spec gap 2). As in `machine_activity_event.verify.md`. The plain `FOR UPDATE` is caught. |
| `go_r6_cap_101`, `go_r6_cap_500` | A cap above the card's own 101. No finite card can see the next one. `go_r6_cap_100` is caught. |
| `gu_r1_one_or_none` | **Equivalent.** R4's constraint leaves at most one row, so `.one_or_none()` cannot differ from `.first()`. |

## xfail tests against the reference
`plug\ref_apv.py` swaps the source of `app.dao.transfer_order_approver` in memory through a meta-path finder; nothing is written to `app/`.

| Base | Fix shape | Result with `--runxfail`, each plan |
|---|---|---|
| `fix` | `.order_by(assigned_at, id)` | 35 passed |
| `fix_asc` | both `.asc()` | 35 passed |
| `fix_nulls` | `.asc().nulls_last()`, then `id` | 35 passed |
| `fix_text` | the table's columns | 35 passed |
| `fix_python` | `sorted()` in Python | 1 failed, 34 passed: GO-14 T4, as that card asks for the query to order |

**The alarm works:** `fix` with the markers on gives `1 failed, 32 passed, 2 xpassed`: GO-14 `XPASS(strict)`.

## Reproduced claims
- **Result line of the notes holds.** 8 default runs: `32 passed, 1 xfailed, 2 xpassed` in 7, `32 passed, 2 xfailed, 1 xpassed` in 1. Both are forms the notes allow.
- **GO-14 fails on Then 4 in every run.** GO-12 fails on Then 2 with index and bitmap scans off, on this table too. GO-13 fails on Then 2 only under a wrong tie key (`go_r5_id_desc`), as the notes say. Its Then 1 holds in each.
- **No flaky test.** All 32 pass cards passed in every run. The only movement is GO-12, which is why it is non-strict.
- **Mocks:** none. No `try`, no broad `pytest.raises`, no `if` in a test body.
- **Note on the spec and BUG-1200 text, not a rule:** "moved second on three of the five tables" is not a fixed fact of a table. On today's code GO-12 fails with index and bitmap scans off on all five, and with sequential scans off on none. For the describer, when next touched.

## Traceability
cases 35 · tests 35 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card in all 35. 32 `pass` cards have no marker; 3 xfail cards name BUG-1200, 1 strict and 2 non-strict, and BUG-1200 is in `docs/testing/bugs.md`. All 35 sit under `# [claude] <ID>`. `ruff check` passes.

## Limits of this round
- **Rebuild.** It finds 2130 of 2130 planted mistakes of 71 kinds across the five modules, in tests and in cards. It does not model the 101-row Given of GO-15; `mk_many` was read by eye and is one text in all five.
- **The references are mine.** Variants show what these tests catch around them, not every possible break.
- **Plans.** Three were forced with `PGOPTIONS`. The default plan is what the planner chose while other agents ran.
- **Runs were not isolated.** Other agents may have been live. All mutation kills are a plain `1 failed`. Each of my files ran one process at a time.
- **Constraint cards.** GU-11 and GU-12 test the database's own constraint. No variant can remove it without DDL on the shared test database, so they rest on the error code and the constraint's name.
- **Not exercised:** manager, service or HTTP level; a real race; BUG-1201 and the other bugs routed to the managers.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/transfer_order_approver.py tests/unit/dao/test_transfer_order_approver.py --timeout 300 --json <scratch>/res/mut_transfer.json
  Mutants: 7 · killed 7 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_transfer_order_approver.py -q -p no:cacheprovider --cov=app.dao.transfer_order_approver --cov-branch --cov-report=term-missing --tb=no
  app\dao\transfer_order_approver.py      10      0      0      0   100%
pytest, default plan, 8 runs in all                        as under Reproduced claims
pytest --runxfail -rf, default plan, 3 runs                1 failed, 34 passed (GO-14)
pytest --runxfail -rf, index and bitmap scans off          2 failed, 33 passed (GO-12, GO-14)
drive.py transfer <plan> --bases, 3 plans                     as the reference table
drive.py transfer <plan>, 3 plans                             112 variants each
propdrive.py transfer, 3 plans                                as the recipes table
alarm.py transfer                                             1 failed, 32 passed, 2 xpassed
rebuild.py                                                 184 cards, 0 reports
rebuild.py --selftest 6                                    2130 planted, 2130 found, 71 kinds
.venv/Scripts/python.exe -m ruff check <the five test files>     All checks passed!
git diff --stat -- app/dao                                 (empty)
```
Scratch, all under `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\apv\`: `rebuild.py`, `drive.py`, `propdrive.py`, `alarm.py`, `sumvar.py`, `plug\ref_apv.py`, `plug\variants_apv.py`, `prop\test_apv_prop.py`, `res\`, `delivered\`.

Nothing under `app/`, the spec or the notes was edited. No commit. No model server. Only my own background runs were stopped; no process was killed by name.

## Fix list
1. **Case designer:** add the recipes above; the Givens and Thens are written out. None touches money or order workflow.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-02 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 35 passed · 4 xfail, 1 strict, 3 non-strict (reproduced ✅) · coverage 100% branch (10 statements, 0 branches)
> Mutation: not re-run; round 1 stands at 7 / 7 → 100% (7 mutants)
> Fidelity: **0 of 39 unfaithful** (the new and changed tests read by eye; all 39 rebuilt by script)
> Hand variants: all 9 rule-gap variants fail the right card on all three plans; 112 re-run on the default plan
> Source commit: e48a092 · Cases revision: 1 (39 cases; spec APPROVED, unchanged)

Every finding of round 1 is closed. No new rule gap. No test edited in this round, no commit.

### What changed since round 1
A line diff against my delivered copy shows additions only: 4 new tests, the Then 10 line on the two writes-nothing cards, R2 in one Rules line. No existing Given, When or assert changed. So the tests behind the round 1 kills stand, and new asserts can only add kills.

### New and changed tests
Each was read against its card, and each matches its recipe. "Fails" means the variant fails that card on that Then, on the reference with `--runxfail`, on the default, sequential-only and index-only plans.

| Cards | From | Expect | Fails |
|---|---|---|---|
| TOA-GO-20 | R-1 | pass | `go_r4_pending_first`: T1 |
| TOA-GO-21 | R-2 | xfail BUG-1200, non-strict | the 4 of Finding 2: T2 |
| TOA-GO-19, TOA-GU-16 | R-3, Then 10 added | pass | `go_w_add_pending`, `gu_r2_create_pending`: T10 |
| TOA-GU-17 | R-3 | pass | `gu_w_add_pending_hit`: T3 |
| TOA-GU-18 | R-4 | pass | `gu_member_hide_left_approved`: T1 |

The R5 card is the fourth xfail, so its catches show with `--runxfail`, like every R5 card until BUG-1200 is fixed. `go_r4_pending_first` also still fails GO-12; `go_r5_approved_desc_then_id` also still fails GO-14. No gap variant fails any other card.

### Rest of the batch
112 variants ran on the default plan. 11 survive, exactly the ones under "Considered and not listed" that have no card to catch them. The 2 `*_closed_status_complete` variants are among them, listed in round 1 as not this table's completion. `go_r5_approved_then_id` is still caught by xfail cards alone, also as listed. None is a rule gap.

### Reproduced
- **Default runs, 6 of the file:** `35 passed, 1 xfailed, 3 xpassed` in 6 of 6. Both forms are what 4 xfail cards can give; only GO-14 must always xfail. No pass card failed, so no flaky test.
- **`--runxfail`:** `2 failed, 37 passed` in all 3, GO-12 and GO-14. GO-14 fails on Then 4 every time, GO-12 on Then 2 when it fails. The new R5 card did not fail on today's code, which its `Fails today on` line allows and the notes record.
- **References:** `fix`, `fix_asc`, `fix_nulls`, `fix_text` each pass 39 of 39 on all three plans. `fix_python` fails GO-14 T4 only, as in round 1.
- **Alarm:** `fix` with the markers on gives `1 failed, 35 passed, 3 xpassed`: GO-14 `XPASS(strict)`.
- **Traceability:** cases 39 · tests 39 · unmatched: none · marker mismatches: none. `rebuild.py`: 208 cards over the five files, 0 reports. Its selftest finds 2244 of 2244 planted mistakes of 81 kinds. It missed 1 at first, a mistake in `reread_order`, so that helper is now checked directly.

### Commands run
```
diff <delivered copy> tests/unit/dao/test_transfer_order_approver.py                 additions only
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_transfer_order_approver.py -q -p no:cacheprovider --cov=app.dao.transfer_order_approver --cov-branch --cov-report=term --tb=no
  app\dao\transfer_order_approver.py 10 0 0 0 100%
pytest, default plan, 5 more runs                         as under Reproduced
pytest --runxfail -rf, 2 default, 1 index and bitmap scans off     as under Reproduced
r2check.py transfer                                          9 variants x 3 plans, 0 wrong
drive.py transfer <plan> --bases, 3 plans                    as under Reproduced
drive.py transfer default                                    112 run, 11 survive
rebuild.py; rebuild.py --selftest 6                       208 cards, 0 reports; 2244 of 2244, 81 kinds
.venv/Scripts/python.exe -m ruff check <the five test files>     All checks passed!
git diff --stat -- app/dao                                (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\apv\`. Only this report was edited in the repo. Nothing was stopped or killed in this round.
