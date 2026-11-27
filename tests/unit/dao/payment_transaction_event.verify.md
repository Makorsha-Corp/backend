# Verification — `app/dao/payment_transaction_event.py`

> **Current verdict: PASS** (round 2, 2026-11-02, revision 1, 23 cases). See "Round 2" at the end. The rest of this block is round 1.
>
> **Round 1 verdict:** NEEDS WORK — only the case designer has work: 5 rule gaps, closed by 5 recipes. No test is wrong.
> Tests: 12 passed · 7 xfail, 5 strict, 2 non-strict (reproduced ✅) · coverage 100% branch (7 statements, 0 branches)
> Mutation: 2 mutants · 2 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 19 unfaithful** (19 / 19 right)
> Hand variants: 97 · 62 caught by a pass card on every plan · 35 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases: 19 cases, READY; spec APPROVED

## Summary
- **The tests can be trusted as written.** I read this file fully by eye, every test against its card, because it differs from the family. My own script then rebuilt every test's Given, When, Then and marker from its card and compared them by AST, for all eight modules. Nothing is mocked and no assert is weaker than its card.
- **No shared mistake.** One generator built these files, so the helper section and row builders were compared too. After names are normalised the helper section is one text in all eight, with `order_part_of` added here in payment only.
- **Why NEEDS WORK:** `mutate.py` has only 2 sites here and all die. It has no operator for `order_by`, a parent filter or a pending object, so the hand variants carry those, and 5 rules have a broken shape that passes.
- **Money questions flagged:** see "For the owner". This read holds no money itself, but the rows are a payment's trail, and BUG-1191 is open on it. Nothing in Findings needs the answer.

Written by Claude (all 19 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 19. No `payment_transaction_event.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_payment_transaction` R6 [BUG-1190] | No pass or xfail card separates `id` from another column. In PTE-G-13 and PTE-G-14 every other column is equal, so a key put before `id` falls through to `id` and nothing sees it. A `performed_by` key passes because no card with two rows has a performer. | `r5_key_after_event_type_asc`, `r5_key_after_event_type_desc`, `r5_key_after_description_asc`, `r5_key_after_description_desc`, `r5_key_after_performed_by_asc`, `r5_key_after_performed_by_desc` pass all 19 with `--runxfail` on all three plans, except `r5_key_after_description_desc`, seen by PTE-G-13 alone because its update runs with the key. All on the reference, `plug\ref_ev.py`. | **case designer** |
| 2 | case-missing | `get_by_payment_transaction` R5 | No row of any pass card has a performer beside another row, and the three event types of PTE-G-01 rise in the order of the stamps. So a key put before `created_at` passes every pass card. | `r5_key_first_event_type_asc`, `r5_key_first_description_desc`, `r5_key_first_performed_by_asc`, `r5_key_first_performed_by_desc` pass every pass card on all three plans. `r5_key_first_description_desc` is seen only by PTE-G-13, a non-strict xfail. | **case designer** |
| 3 | case-missing | `get_by_payment_transaction` R5 | Every Given row but the long log differs by whole days, and in the long log ids rise with the stamps. So an order by the truncated stamp, then `id`, gives the same list. No card has an older row with a higher id inside one day. | `r5_coarse_second`, `r5_coarse_minute`, `r5_coarse_hour`, `r5_coarse_day` pass all 19 on all three plans. The stamp has microseconds, and the code writes them. | **case designer** |
| 4 | case-missing | `get_by_payment_transaction` R8 "The call changes nothing", Side effects none | The approver verifier's shared finding, here. "Nothing written" counts stored rows, and the Conventions say a pending row does not count. PTE-G-19 checks that P stays pending, not that P is alone, and its `unchanged` line calls `db.expire_all()` first, which throws a pending change away. So a read that leaves a row or a change for the caller's next commit passes. | `w_add_pending`, `w_add_pending_empty`, `w_delete_pending`, `w_dirty_pending` pass all 19 on all three plans. | **case designer** |
| 5 | case-missing | `get_by_payment_transaction` R4 | PTE-G-10 says the read does not touch the parent table, but looks only for the word `JOIN`. A subquery on the transaction names it and writes no `JOIN`. So a read that hides the log of a failed or cancelled payment passes. | `r4_sub_status_not_validated_failed`, `r4_sub_status_not_cancelled`, `r4_sub_bank_tran_id_null` pass all 19 on all three plans. The `JOIN` forms are caught by PTE-G-10 T3. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `prop\test_payment_transaction_event_plus.py`, and `prop\test_payment_transaction_event_refplus.py` for the reference under `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\evv\`, not in the repo. Each passes on today's code and on the references, on all three plans. With them added, every variant in Findings fails on an assertion of the recipe named, on all three plans. R-3's lines and R-4 ran as separate scratch tests with the same Given.

| Recipe | Where | Given | Then | Expect | Closes |
|---|---|---|---|---|---|
| R-1 | new card, R6 [BUG-1190] | `U2`, `U3` = two more `profiles` rows, made after U1. A = event, `created_at T2`, but `event_type "b"`, `description "b"`, `performed_by U2.id`. B = the same, but `"a"`, `"a"`, `U1.id`. C = the same, but `"c"`, `"c"`, `U3.id`. `db.expire_all()` | `ids(result) == [A.id, B.id, C.id]` | xfail BUG-1190 (non-strict): physical order gives the intended result today | Finding 1 |
| R-2 | new card, R5 | A = event, `created_at T2 + timedelta(microseconds=1)`. B = event, `created_at T2` | `ids(result) == [B.id, A.id]` | pass | Finding 3, every unit |
| R-3 | two lines on PTE-G-19, placed before its `unchanged` line; one new card | Lines: as PTE-G-19. New card: PTE-G-19's Given, with the When on TX2, which has no events | Lines: `pending: len(db.new) == 1`, `pending: not db.dirty and not db.deleted`. New card: `result == []`, `pending: len(db.new) == 1` | pass | Finding 4: the lines catch three, the new card `w_add_pending_empty` |
| R-4 | one Then line on PTE-G-10, in place of its T3 | as PTE-G-10 | `statement: "payment_transactions" not in sql` | pass | Finding 5, and the `JOIN` forms stay caught |
| R-5 | new card, R5 | `U2`, `U3` = two more `profiles` rows, made after U1. A = event, `created_at T1`, but `event_type "b"`, `description "b"`, `performed_by U2.id`. B = event, `created_at T2`, but `"a"`, `"a"`, `U1.id`. C = event, `created_at T3`, but `"c"`, `"c"`, `U3.id` | `ids(result) == [A.id, B.id, C.id]` | pass | Finding 2 |

## Surviving mutants
None. All 2 kills end in a plain `1 failed`; no run errored, so the tool's repeat never applied. `mutate.py` stops a run at its first failure (`-x`), so its kills do not reach every test. As the guard, the same changes also ran as hand variants without `-x`, and each reached all 19. Its base run collects 12 tests under `-m "not xfail"`, which is every pass card.

Score: 2 / (2 − 0 − 0 − 0) = **100%**.

| Line | Mutation | Status | Same change as a hand variant |
|---|---|---|---|
| 13 | return None | KILLED | `r1_return_none` |
| 15 | Eq -> NotEq | KILLED | `r1_parent_ne` |

## Hand variants
Each ran on the reference with `--runxfail`, on three plans (default, sequential only, index only). Every edit is asserted to apply once and every run is required to reach all tests; no run fell short. "Pass card on every plan" leaves out the seven xfail cards. The base is `plug\ref_ev.py`, which applies the spec's fix: required `workspace_id`, `created_at`, then `id`. Its test copy, `prop\test_payment_transaction_event_ref.py`, adds `workspace_id=w1.id` to the 15 calls of today's cards, as cases Spec gap 5 requires, and leaves everything else alone.

| Rule group | Variants | Pass card, every plan | Cards that fail (default plan) | Others |
|---|---|---|---|---|
| R1 | 18 | 18 | G-01, G-02, G-03, G-04, G-05, G-07, G-08 … | — |
| R2 | 8 | 4 | G-01, G-02, G-03, G-04, G-05, G-10, G-11 … | `r2_no_ws`, `r2_ws_ge`, `r2_ws_le`, `r2_row_and_parent_sub` |
| R3 | 4 | 4 | G-03, G-04, G-07, G-08, G-09 | — |
| R4 | 7 | 4 | G-10 | `r4_sub_status_not_validated_failed`, `r4_sub_status_not_cancelled`, `r4_sub_bank_tran_id_null` |
| R5 | 15 | 7 | G-01, G-10, G-11, G-12, G-13, G-14, G-15 … | `r5_key_first_event_type_asc`, `r5_key_first_description_desc`, `r5_key_first_performed_by_asc`, `r5_key_first_performed_by_desc`, `r5_coarse_second`, `r5_coarse_minute`, `r5_coarse_hour`, `r5_coarse_day` |
| R6 | 10 | 0 | G-13, G-14, G-15 | `r5_id_reversed`, `r5_no_id`, `r5_ctid_for_id`, `r5_ctid_rev_for_id`, `r5_key_after_event_type_asc`, `r5_key_after_event_type_desc`, `r5_key_after_description_asc`, `r5_key_after_description_desc`, `r5_key_after_performed_by_asc`, `r5_key_after_performed_by_desc` |
| R7 | 5 | 3 | G-01, G-02, G-05, G-10, G-11, G-12, G-13 … | `r6_cap_158`, `r6_cap_1000` |
| R8 | 8 | 7 | G-01, G-02, G-05, G-10, G-11, G-12, G-13 … | `s_defer_metadata` |
| writes | 21 | 15 | G-07, G-08, G-10, G-15, G-16, G-17, G-18 … | `w_add_pending`, `w_add_pending_empty`, `w_delete_pending`, `w_dirty_pending`, `w_expire_all`, `x_read_parent` |
| keyword | 1 | 0 | — | `kw_positional` |
| **Total** | **97** | **62** | | **35** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `r2_no_ws`, `r2_ws_ge`, `r2_ws_le`, `r5_id_reversed`, `r5_no_id`, `r5_ctid_for_id`, `r5_ctid_rev_for_id`, `r2_row_and_parent_sub` | **Bug path.** Caught by the xfail cards alone, which is what those cards are for. They turn into pass cards when BUG-1190 and BUG-1191 are fixed and the markers go. `r2_row_and_parent_sub` is the one exception: no delivered card sees it, R-4 does; see "For the owner". |
| `r6_cap_158`, `r6_cap_1000` | A cap at or above the card's own row count. No finite card can see the next one. The cap below it is caught. |
| `s_defer_metadata` | **Equivalent:** the value loads on first read and is the same value. |
| `w_expire_all` | **Equivalent:** no flush, no write; attributes reload to the same values. |
| `x_read_parent` | **Equivalent** on these cards: `db.get` finds the parent in the session and sends nothing, and no rule counts reads here. |
| `kw_positional` | A note, not a rule: cases Spec gap 1. |
| A whitelist of the cards' own event types | Not run as a finding: R1 says every event type, the column has no check constraint, and no finite card can list them all. Hiding any one of the cards' types is caught. |

## xfail tests against the reference
| Base | Fix shape | Result with `--runxfail`, each plan |
|---|---|---|
| `fix_req` | required `workspace_id`, `created_at`, `id`; test copy | 19 passed |
| `fix_nulls` | the same, `nulls_last()` | 19 passed |
| `fix_select` | the same, `select()` style | 19 passed |
| `fix_opt` | optional `workspace_id`, full order; delivered file | 18 passed; G-06 fails T1 by that design |
| `fix_order` | BUG-1190 alone; delivered file | 15 passed; G-03 … G-06 fail on the missing parameter |
| `fix_ws_only` | BUG-1191 alone; test copy | G-15 fails T3; G-13 also on the sequential plan |

**The alarms work.** `fix_order` with the markers on: G-15 `XPASS(strict)`, G-13 and G-14 XPASS, the run is red. `fix_opt`: G-03, G-04, G-05, G-15 `XPASS(strict)`. `fix_req` on the delivered file: the 12 pass cards fail with `TypeError`, G-03 … G-06 `XPASS(strict)`, and G-13, G-14, G-15 xfail on `TypeError`, which is cases Spec gap 5: the fix must add the argument to the whole file. If BUG-1191 lands first, G-15 stays xfail on `TypeError` and its alarm is silent, as the notes say.

## Reproduced claims
- **Result line of the notes holds.** 5 default runs: `12 passed, 5 xfailed, 2 xpassed` in 4, `12 passed, 6 xfailed, 1 xpassed` in 1. Both are forms the notes allow.
- **Each xfail fails where its card says.** G-03, G-04, G-05: the When line, `TypeError` on `workspace_id`. G-06: Then 1, `DID NOT RAISE TypeError`. G-15: Then 3, every run on every plan. G-13: Then 1 when it fails, `[higher, lower] == [lower, higher]`. G-14 XPASSED in every run, as its card says; it can only fail under a wrong order, as `r5_id_reversed` shows on T1.
- **No flaky test.** All 12 pass cards passed in every run. The only movement is G-13, which is why it is non-strict.
- **Notes figures checked:** 7 statements, 0 branches. Line endings and `ruff check` as the notes say.
- **Mocks:** none. No `try`, no broad `pytest.raises`, no `if` in a test body.

## Traceability
cases 19 · tests 19 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card in all 19. 12 `pass` cards have no marker. 7 xfail cards name BUG-1191 (4) and BUG-1190 (3), 5 strict and 2 non-strict; both are in `docs/testing/bugs.md`, and each reason carries the bug's title. All 19 sit under `# [claude] <ID>`. `ruff check` passes.

## For the owner

Money, from cases Spec gaps 3 to 6; none blocks a finding here.
1. **Spec gap 3, R2.** Is a row of workspace A on a transaction of workspace B returned for A? The sibling specs say yes; this rule does not say. `r2_row_and_parent_sub` (row filter plus a subquery on the parent's workspace) passes every delivered card, because no card reads that row for its own workspace. R-4 happens to close that shape, but the answer still decides whether a fix may return the row. Only invalid data gets there, as `_log_event` copies `txn.workspace_id`. Once answered, it is one card.
2. **Spec gap 4, R4.** Should the rule name the transaction's states? R-4 settles the read either way: it may not look at the parent.
3. **Spec gap 5.** Fix order. BUG-1190 and BUG-1191 together, or BUG-1190 first, as the notes say.

## Limits of this round
- **Rebuild.** It finds 2866 of 2866 planted mistakes of 72 kinds across the eight modules, in tests and in cards, each by a named report. It cannot see a mistake shared by a test and its card; the hand variants look for that.
- **The references are mine.** Variants show what these tests catch around them, not every possible break.
- **Plans.** Three were forced with `PGOPTIONS`. The default plan is what the planner chose while other agents ran.
- **Runs were not isolated.** Other agents may have been live; all kills are a plain `1 failed`. Four of my modules ran side by side, and no two processes ran one module.
- **Not exercised:** manager, service or HTTP level; a real race; the bugs routed to the managers.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/payment_transaction_event.py tests/unit/dao/test_payment_transaction_event.py --timeout 300 --json <scratch>/res/mut_payment_transaction_event.json
  Mutants: 2 · killed 2 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_payment_transaction_event.py -q -p no:cacheprovider --cov=app.dao.payment_transaction_event --cov-branch --cov-report=term-missing   (COVERAGE_FILE private)
  app\dao\payment_transaction_event.py       7      0      0      0   100%
  12 passed, 6 xfailed, 1 xpassed
  12 passed, 5 xfailed, 2 xpassed
  12 passed, 5 xfailed, 2 xpassed
  12 passed, 5 xfailed, 2 xpassed
  12 passed, 5 xfailed, 2 xpassed
  5 failed, 14 passed
  5 failed, 14 passed
  6 failed, 13 passed
  12 passed, 5 xfailed, 2 xpassed
  12/19 tests collected (7 deselected)
drive.py payment_transaction_event <plan>, 3 plans                       97 variants each, reach failures 0
drive.py payment_transaction_event <plan> --test <plus file>, 3 plans    97 variants each, reach failures 0, survivors: 11, all under Considered
rebuild.py                                            157 cards, 0 reports, one helper text
rebuild.py --selftest                                 2866 planted, 2866 found, 72 kinds
.venv/Scripts/python.exe -m ruff check --no-cache <the eight test files>     All checks passed!
git diff --stat -- app/dao                            (empty)
```
Scratch, all under `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\evv\`: `rebuild.py`, `selfcount.py`, `drive.py`, `mkref.py`, `mkplus.py`, `sumvar.py`, `sumbase.py`, `norm.py`, `plug\ref_ev.py`, `plug\variants_ev.py`, `prop\`, `res\`, `delivered\`.

Nothing under `app/`, the spec, the cases, the notes or the tests was edited. No commit. No model server. No process was stopped or killed.

## Fix list
1. **Case designer:** add the recipes above; the Givens and Thens are written out. Answer the "For the owner" items first if you want R2's other side carded.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-02 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 15 passed · 8 xfail, 5 strict, 3 non-strict (reproduced ✅) · coverage 100% branch (7 statements, 0 branches)
> Mutation: not re-run, as agreed; round 1 stands
> Fidelity: **0 of 4 new tests unfaithful, 0 of the changed tests**
> Findings' variants: 28, every one fails its named card on an assertion on all three plans
> Source commit: e48a092 · Cases revision: 1 (23 cases; spec APPROVED, unchanged)

Findings 1 to 5 are closed. No test edited in this round, no commit.

### What changed since round 1
A line diff against my saved copy shows: 4 tests added; PTE-G-19 gained Then 5 and 6, and its old 5 to 7 moved to 7 to 9; PTE-G-10 Then 3 replaced. No other test, helper or marker changed.

### The new and changed tests
Each was read against its card: every Given row, the When call, each Then line, and the marker. All are right. `rebuild.py`, taught the new Given forms, gives 182 cards, 0 reports, and finds 3329 of 3329 planted mistakes of 71 kinds.

| Finding | Recipe | Card | Variants | Fails on, all three plans |
|---|---|---|---|---|
| 1 | R-1 | PTE-G-20 (non-strict xfail, BUG-1190) | key after `created_at` | Then 1 |
| 2 | R-5 | PTE-G-23 | key before `created_at` | Then 1 |
| 3 | R-2 | PTE-G-21 | truncated stamp | Then 1 |
| 4 | R-3 | PTE-G-19 Then 5, 6; PTE-G-22 Then 2 | row, delete or change left pending | those lines |
| 5 | R-4 | PTE-G-10 Then 3 | parent filters, join and subquery | Then 3 |

**Finding 1 stays quiet until BUG-1190 is fixed.** PTE-G-20 is a non-strict xfail and usually XPASSES, so its catch shows with `--runxfail` only, which is what the recipe asked for. It becomes a pass card when the markers go.

**The replaced line loses nothing that matters.** With `JOIN` gone from PTE-G-10, the full 97 ran on the default plan on the reference. One variant moved: `s_joinedload_performer` now passes, an outer join to `profiles` that returns the same rows, equivalent as in the seven siblings. The other survivors are those of round 1's "Considered", plus the bug-path shapes seen only by xfail cards.

### Spec gap 3
**Closed 2026-11-02, on the coordinator's ruling:** it binds the caller, not this DAO, and R-4 stands. That ends item 1 of round 1's "For the owner". `r2_row_and_parent_sub` fails PTE-G-10 Then 3 on all three plans. I edited `payment_transaction_event.cases.md` for this, at the coordinator's instruction and against the skill's read-only rule: the "Needs a decision" line and the end of gap 3's row, nothing else. Item 3, the fix order, stands.

### Reproduced
- **Default runs:** `15 passed, 6 xfailed, 2 xpassed` in 3 of 3, a form the notes allow.
- **`--runxfail`:** default `5 failed, 18 passed`; sequential `6 failed, 17 passed`, G-13 the extra one; index `5 failed, 18 passed`.
- **References:** `fix_req`, `fix_nulls`, `fix_select` pass 23 of 23 on the test copy, on three plans. `fix_order` with the markers on: G-15 `XPASS(strict)`, the alarm.
- **No flaky test.** The only movement is G-13, as before.
- **Result line of the notes holds.** `ruff check` passes. `git diff --stat -- app/dao` is empty.

### Commands run
```
pytest tests/unit/dao/test_payment_transaction_event.py --cov=app.dao.payment_transaction_event --cov-branch   (COVERAGE_FILE private)
  app\dao\payment_transaction_event.py       7      0      0      0   100%
pytest, default 3 runs, then --runxfail on default, sequential, index
  15 passed, 6 xfailed, 2 xpassed
  15 passed, 6 xfailed, 2 xpassed
  15 passed, 6 xfailed, 2 xpassed
  5 failed, 18 passed
  6 failed, 17 passed
  5 failed, 18 passed
drive.py payment_transaction_event <plan> --only <Findings variants>, 3 plans   28 variants, reach failures 0
sum_r2.py                                                    28 variants, 0 misses of a named card
drive.py payment_transaction_event default                   97 variants, reach failures 0
rebuild.py                                                   182 cards, 0 reports
rebuild.py --selftest                                        3329 planted, 3329 found, 71 kinds
```
Scratch in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\evv\`: `run_r2.sh`, `sum_r2.py`, `res\r2_*`. Only this report and `payment_transaction_event.cases.md` (gap 3, as above) were edited in the repo. Nothing was stopped or killed.
