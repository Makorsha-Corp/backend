# Verification — `app/dao/expense_order_event.py`

> **Current verdict: PASS** (round 2, 2026-11-02, revision 1, 21 cases). See "Round 2" at the end. The rest of this block is round 1.
>
> **Round 1 verdict:** NEEDS WORK — only the case designer has work: 4 rule gaps, closed by 4 recipes. No test is wrong.
> Tests: 18 passed · 0 xfail (nothing to reproduce) · coverage 100% branch (8 statements, 0 branches)
> Mutation: 3 mutants · 3 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 18 unfaithful** (18 / 18 right)
> Hand variants: 96 · 67 caught by a pass card on every plan · 29 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases: 18 cases, READY; spec APPROVED

## Summary
- **The tests can be trusted as written.** I read this file fully by eye, every test against its card. My own script then rebuilt every test's Given, When, Then and marker from its card and compared them by AST, for all eight modules. Nothing is mocked and no assert is weaker than its card.
- **No shared mistake.** One generator built these files, so the helper section and row builders were compared too. After names are normalised the helper section is one text in all eight, with `order_part_of` added here in payment only.
- **Why NEEDS WORK:** `mutate.py` has only 3 sites here and all die. It has no operator for `order_by`, a parent filter or a pending object, so the hand variants carry those, and 4 rules have a broken shape that passes.
- **No money or order-workflow question arises.** Each gap is a missing test on a rule already decided.

Written by Claude (all 18 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 18. No `expense_order_event.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_order` R5 | The approver verifier's shared finding, here: id and the other columns rise together, or do not differ. In EOE-G-13 and EOE-G-14 every other column is equal, except `description` in EOE-G-14, where it runs with `id` for one direction. No card with two rows has a performer. So a key beside `created_at` that is not `id` goes unseen. | `r5_key_after_event_type_asc`, `r5_key_after_event_type_desc`, `r5_key_after_description_desc`, `r5_key_after_performed_by_asc`, `r5_key_after_performed_by_desc`, `r5_key_first_description_desc`, `r5_key_first_performed_by_asc`, `r5_key_first_performed_by_desc` pass all 18 on all three plans. The other key shapes are caught, by EOE-G-14 or EOE-G-01. | **case designer** |
| 2 | case-missing | `get_by_order` R5 | Every Given row but the long log differs by whole days, and in the long log ids rise with the stamps. So an order by the truncated stamp, then `id`, gives the same list. No card has an older row with a higher id inside one day. | `r5_coarse_second`, `r5_coarse_minute`, `r5_coarse_hour`, `r5_coarse_day` pass all 18 on all three plans. The stamp has microseconds, and the code writes them. | **case designer** |
| 3 | case-missing | `get_by_order` R7 "The call changes nothing", Side effects none | The approver verifier's shared finding, here. "Nothing written" counts stored rows, and the Conventions say a pending row does not count. EOE-G-18 checks that P stays pending, not that P is alone, and its `unchanged` line calls `db.expire_all()` first, which throws a pending change away. So a read that leaves a row or a change for the caller's next commit passes. | `w_add_pending`, `w_add_pending_empty`, `w_delete_pending`, `w_dirty_pending` pass all 18 on all three plans. | **case designer** |
| 4 | case-missing | `get_by_order` R1, Branch map "no join to the parent"; standing decision 2 | PTE-G-10, the payment module's card, checks that the read does not touch the parent. This module has no such card, and its parents all stand in their first state. So a read that hides the log of a closed expense order passes. | `r4_join_voided_false`, `r4_sub_voided_false`, `r4_join_voided_at_null`, `r4_sub_voided_at_null`, `r4_join_completed_at_null`, `r4_sub_completed_at_null` pass all 18 on all three plans. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `prop\test_expense_order_event_plus.py` under `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\evv\`, not in the repo. Each passes on today's code and on the references, on all three plans. With them added, every variant in Findings fails on an assertion of the recipe named, on all three plans. R-3's lines and R-4 ran as separate scratch tests with the same Given.

| Recipe | Where | Given | Then | Expect | Closes |
|---|---|---|---|---|---|
| R-1 | new card, R5 | `U2`, `U3` = two more `profiles` rows, made after U1. A = event, `created_at T2`, but `event_type "b"`, `description "b"`, `performed_by U2.id`. B = the same, but `"a"`, `"a"`, `U1.id`. C = the same, but `"c"`, `"c"`, `U3.id`. `db.expire_all()` | `ids(result) == [C.id, B.id, A.id]` | pass | Finding 1. Each column runs neither with `id` nor against it, so one card sees both directions |
| R-2 | new card, R5 | A = event, `created_at T2 + timedelta(microseconds=1)`. B = event, `created_at T2` | `ids(result) == [A.id, B.id]` | pass | Finding 2, every unit |
| R-3 | two lines on EOE-G-18, placed before its `unchanged` line; one new card | Lines: as EOE-G-18. New card: EOE-G-18's Given, with the When on O2, which has no events | Lines: `pending: len(db.new) == 1`, `pending: not db.dirty and not db.deleted`. New card: `result == []`, `pending: len(db.new) == 1` | pass | Finding 3: the lines catch three, the new card `w_add_pending_empty` |
| R-4 | one Then line on EOE-G-18 | as EOE-G-18 | `statement: "expense_orders" not in sql` | pass | Finding 4, join and subquery forms |

## Surviving mutants
None. All 3 kills end in a plain `1 failed`; no run errored, so the tool's repeat never applied. `mutate.py` stops a run at its first failure (`-x`), so its kills do not reach every test. As the guard, the same changes also ran as hand variants without `-x`, and each reached all 18. Its base run collects 18 tests under `-m "not xfail"`, which is every pass card.

Score: 3 / (3 − 0 − 0 − 0) = **100%**.

| Line | Mutation | Status | Same change as a hand variant |
|---|---|---|---|
| 14 | return None | KILLED | `r1_return_none` |
| 17 | Eq -> NotEq | KILLED | `r1_parent_ne` |
| 18 | Eq -> NotEq | KILLED | `r2_ws_ne` |

## Hand variants
Each ran on the reference with `--runxfail`, on three plans (default, sequential only, index only). Every edit is asserted to apply once and every run is required to reach all tests; no run fell short. The base is `plug\ref_ev.py`, which runs the source unchanged, as this module has no bug.

| Rule group | Variants | Pass card, every plan | Cards that fail (default plan) | Others |
|---|---|---|---|---|
| R1 | 18 | 18 | G-01, G-02, G-03, G-04, G-05, G-06, G-07 … | — |
| R2 | 7 | 7 | G-01, G-02, G-03, G-04, G-05, G-06, G-09 … | — |
| R3 | 4 | 4 | G-03, G-06, G-07, G-08, G-09, G-10, G-11 | — |
| R4 | 7 | 0 | — | `r4_join_voided_false`, `r4_sub_voided_false`, `r4_join_voided_at_null`, `r4_sub_voided_at_null`, `r4_join_completed_at_null`, `r4_sub_completed_at_null`, `r4_join_plain` |
| R5 | 25 | 13 | G-01, G-12, G-13, G-14, G-15, G-17 | `r5_key_after_event_type_asc`, `r5_key_after_event_type_desc`, `r5_key_after_description_desc`, `r5_key_first_description_desc`, `r5_key_after_performed_by_asc`, `r5_key_first_performed_by_asc`, `r5_key_after_performed_by_desc`, `r5_key_first_performed_by_desc`, `r5_coarse_second`, `r5_coarse_minute`, `r5_coarse_hour`, `r5_coarse_day` |
| R6 | 5 | 3 | G-01, G-02, G-04, G-05, G-12, G-13, G-14 … | `r6_cap_158`, `r6_cap_1000` |
| R7 | 8 | 6 | G-01, G-02, G-04, G-05, G-12, G-13, G-14 … | `s_joinedload_performer`, `s_defer_metadata` |
| writes | 21 | 16 | G-07, G-08, G-09, G-11, G-15, G-16, G-17 … | `w_add_pending`, `w_add_pending_empty`, `w_delete_pending`, `w_dirty_pending`, `x_read_parent` |
| keyword | 1 | 0 | — | `kw_positional` |
| **Total** | **96** | **67** | | **29** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `r6_cap_158`, `r6_cap_1000` | A cap at or above the card's own row count. No finite card can see the next one. The cap below it is caught. |
| `r4_join_plain` | **Equivalent** in result: the foreign key is `NOT NULL`, so an inner join to the parent drops no row. R-4 catches it anyway. |
| `s_joinedload_performer` | **Equivalent:** an outer join that loads the same rows and the same performer. |
| `s_defer_metadata` | **Equivalent:** the value loads on first read and is the same value. |
| `x_read_parent` | **Equivalent** on these cards: `db.get` finds the parent in the session and sends nothing, and no rule counts reads here. |
| `kw_positional` | A note, not a rule: cases Spec gap 1. |
| A whitelist of the cards' own event types | Not run as a finding: R1 says every event type, the column has no check constraint, and no finite card can list them all. Hiding any one of the cards' types is caught. |

## Other shapes of the same query
`eq_select`, the same query in `select()` style, passes 18 of 18 on all three plans, and so do the recipes. The tests do not lean on the query's form.

## Reproduced claims
- **Result line of the notes holds.** `18 passed` in all 5 default runs, 2 `--runxfail` runs, and on the sequential and index plans.
- **No flaky test.**
- **Notes figures checked:** 8 statements, 0 branches. Line endings and `ruff check` as the notes say.
- **Mocks:** none. No `try`, no broad `pytest.raises`, no `if` in a test body.

## Traceability
cases 18 · tests 18 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card in all 18. 18 `pass` cards have no marker. All 18 sit under `# [claude] <ID>`. `ruff check` passes.


## Limits of this round
- **Rebuild.** It finds 2866 of 2866 planted mistakes of 72 kinds across the eight modules, in tests and in cards, each by a named report. It cannot see a mistake shared by a test and its card; the hand variants look for that.
- **The references are mine.** Variants show what these tests catch around them, not every possible break.
- **Plans.** Three were forced with `PGOPTIONS`. The default plan is what the planner chose while other agents ran.
- **Runs were not isolated.** Other agents may have been live; all kills are a plain `1 failed`. Four of my modules ran side by side, and no two processes ran one module.
- **Cascade.** EOE-G-11 tests the database's own `ON DELETE CASCADE`. No variant can remove it without DDL on the shared test database.
- **Not exercised:** manager, service or HTTP level; a real race; the bugs routed to the managers.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/expense_order_event.py tests/unit/dao/test_expense_order_event.py --timeout 300 --json <scratch>/res/mut_expense_order_event.json
  Mutants: 3 · killed 3 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_expense_order_event.py -q -p no:cacheprovider --cov=app.dao.expense_order_event --cov-branch --cov-report=term-missing   (COVERAGE_FILE private)
  app\dao\expense_order_event.py       8      0      0      0   100%
  18 passed
  18 passed
  18 passed
  18 passed
  18 passed
  18 passed
  18 passed
  18 passed
  18 passed
  18 tests collected
drive.py expense_order_event <plan>, 3 plans                       96 variants each, reach failures 0
drive.py expense_order_event <plan> --test <plus file>, 3 plans    96 variants each, reach failures 0, survivors: 6, all under Considered
rebuild.py                                            157 cards, 0 reports, one helper text
rebuild.py --selftest                                 2866 planted, 2866 found, 72 kinds
.venv/Scripts/python.exe -m ruff check --no-cache <the eight test files>     All checks passed!
git diff --stat -- app/dao                            (empty)
```
Scratch, all under `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\evv\`: `rebuild.py`, `selfcount.py`, `drive.py`, `mkref.py`, `mkplus.py`, `sumvar.py`, `sumbase.py`, `norm.py`, `plug\ref_ev.py`, `plug\variants_ev.py`, `prop\`, `res\`, `delivered\`.

Nothing under `app/`, the spec, the cases, the notes or the tests was edited. No commit. No model server. No process was stopped or killed.

## Fix list
1. **Case designer:** add the recipes above; the Givens and Thens are written out. None touches money or order workflow.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-02 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 21 passed · 0 xfail · coverage 100% branch (8 statements, 0 branches)
> Mutation: not re-run, as agreed; round 1 stands
> Fidelity: **0 of 3 new tests unfaithful, 0 of the changed tests**
> Findings' variants: 27, every one fails its named card on an assertion on all three plans
> Source commit: e48a092 · Cases revision: 1 (21 cases; spec APPROVED, unchanged)

Findings 1 to 4 are closed. No test edited in this round, no commit.

### What changed since round 1
A line diff against my saved copy shows: 3 tests added; EOE-G-18 gained Then 5, 6 and 10, and its old 5 to 7 moved to 7 to 9, and its Rules line gained the rule of the new line, as its card says. No other test, helper or marker changed.

### The new and changed tests
Each was read against its card: every Given row, the When call, each Then line, and the marker. All are right. `rebuild.py`, taught the new Given forms, gives 182 cards, 0 reports, and finds 3329 of 3329 planted mistakes of 71 kinds.

| Finding | Recipe | Card | Variants | Fails on, all three plans |
|---|---|---|---|---|
| 1 | R-1 | EOE-G-19 | key beside `created_at` | Then 1 |
| 2 | R-2 | EOE-G-20 | truncated stamp | Then 1 |
| 3 | R-3 | EOE-G-18 Then 5, 6; EOE-G-21 Then 2 | row, delete or change left pending | those lines |
| 4 | R-4 | EOE-G-18 Then 10 | parent filters, join and subquery | Then 10 |

### Reproduced
- **Runs:** `21 passed` in all 3 default runs, with `--runxfail`, and on the sequential and index plans.
- **No flaky test.**
- **Result line of the notes holds.** `ruff check` passes. `git diff --stat -- app/dao` is empty.

### Commands run
```
pytest tests/unit/dao/test_expense_order_event.py --cov=app.dao.expense_order_event --cov-branch   (COVERAGE_FILE private)
  app\dao\expense_order_event.py       8      0      0      0   100%
pytest, default 3 runs, then --runxfail on default, sequential, index
  21 passed
  21 passed
  21 passed
  21 passed
  21 passed
  21 passed
drive.py expense_order_event <plan> --only <Findings variants>, 3 plans   27 variants, reach failures 0
sum_r2.py                                                    27 variants, 0 misses of a named card
rebuild.py                                                   182 cards, 0 reports
rebuild.py --selftest                                        3329 planted, 3329 found, 71 kinds
```
Scratch in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\evv\`: `run_r2.sh`, `sum_r2.py`, `res\r2_*`. Only this report was edited in the repo. Nothing was stopped or killed.
