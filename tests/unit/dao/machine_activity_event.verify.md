# Verification — `app/dao/machine_activity_event.py`

> **Current verdict: PASS** (round 2, 2026-10-31, revision 1, 81 cases). See "Round 2" at the end. The rest of this block is round 1.
>
> **Round 1 verdict:** NEEDS WORK — only the case designer has work: 2 rule gaps, closed by 3 cards. No test is wrong, and no test was edited.
> Tests: 76 passed · 2 xfail, 1 strict, 1 non-strict (reproduced ✅) · coverage 100% branch (25 statements, 8 branches)
> Mutation: 32 mutants · 32 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 78 unfaithful** (78 / 78 right)
> Hand variants: 148 · 131 caught on every plan · 5 rule gaps (Findings 1, 2) · 12 not listed, each with its reason
> Source commit: e48a092 · Cases: 78 cases, READY; spec APPROVED

## Summary
- **The tests can be trusted as written.** I read all 78 against their cards, then rebuilt each test's Given calls, When call, Then asserts and marker from the card by a script of my own, which shares nothing with the executor's parser. Nothing extra is mocked, and no assert is weaker than its card.
- **The evidence goes beyond reading.** A reference fix passes 78 of 78. So do three other fix shapes, one of them `DISTINCT ON`. LM-15 fails on its Then 2 in every run and LM-14 on its Then 3 whenever it fails. With the fix and the markers on, LM-15 turns the run red, as its card intends.
- **Why NEEDS WORK:** the 32 mutants all die, but `mutate.py` has no operator for these two gaps. LS-03 cannot see the `id` tiebreak dropped on a sequential scan, and no card separates "equals" from a substring match on `event_type`.
- **No money or order-workflow question arises.**

Written by Claude (all 78 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 78. No `machine_activity_event.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_latest_status_by_machine` R2 | LS-03 is the only pass card for the tie. It uses the map's recipe: updating the lower id moves that row physically last. The map keeps the last row, so there the recipe works against the bug. This method keeps the first row, so the recipe works for the bug: physical order alone already gives the expected row. | `ls_r2_no_id` (`.order_by(desc(created_at))`, the plain way to break R2) passes LS-03 with index and bitmap scans off, and is caught on the two other plans, so catching it rests on the plan. `ls_r2_ctid_asc` passes on all three plans. LM-14 T2 sees both, but it is non-strict xfail, so its failure turns nothing red. | **case designer** |
| 2 | case-missing | `get_by_machine` R13 "equals it exactly" | GM-32 … GM-37 cover case, padding, a space, a wildcard and an unknown type. No card has a filter that is part of a stored type, so a substring match passes all of them. `updated` and `status_updated` are both real stored types (spec, Model facts), so a filter on `updated` would also show every status change. | `gm_r13_contains_esc`, `gm_r13_startswith_esc`, `gm_r13_endswith_esc` (each with `autoescape=True`, so GM-36 cannot see it) survive on all three plans. | **case designer** |

No fidelity finding. The spec gaps listed in the cases file are unchanged.

### Scratch cards that close the gaps
3 tests in `maev\prop\test_mae_prop.py`, not in the repo. All 3 pass on today's code and on the reference, on all three plans. Each survivor fails on the recipe shown, on all three plans.

| Recipe | Given → expected | Expect | Fails on |
|---|---|---|---|
| P1 | A = status row T2, B = status row T2, **no update**; `get_latest_status_by_machine` gives `B.id` | pass | `ls_r2_no_id`, `ls_r2_ctid_asc` |
| P2 | A = event T1, `event_type "updated"`, B = status row T2; `get_by_machine(event_type="updated")` gives `[A.id]` | pass | `gm_r13_contains_esc`, `gm_r13_endswith_esc` |
| P3 | A = event T1; `get_by_machine(event_type="item")` gives `[]` | pass | `gm_r13_contains_esc`, `gm_r13_startswith_esc` |

Keep LS-03: P1 alone would let a physical order from the other side through. Together the two cards put the higher id physically last and physically first.

## Surviving mutants
None. All 32 kills end in a plain `1 failed`. No run errored, so the tool's repeat never applied. It has no operator for `and_`, `desc`, `.in_`, `func.max` or the `order_by` list, so the variants below carry those.

Score: 32 / (32 − 0 − 0 − 0) = **100%**.

## Hand variants
Each ran on the reference with `--runxfail`, and every edit is asserted to apply once. 138 ran on three plans: default, sequential only, index only. The 9 forced-write variants and `gm_r15_type_drops_dates` ran on the default plan. "Caught by" shows the cards that fail.

| Rule group | Variants | Caught on every plan | Caught by | Not caught |
|---|---|---|---|---|
| `get_by_machine` R1 … R4 | 11 | 10 | GM-01 … GM-12 | `gm_r4_factory_active` |
| R5 order and paging | 6 | 6 | GM-13, GM-16, GM-17 | — |
| R6 … R8 limits, skip, errors | 14 | 12 | GM-14 … GM-24 | `gm_r6_cap_101`, `gm_r6_cap_500` |
| R9 … R12 dates, UTC | 17 | 17 | GM-25 … GM-31, GM-41 | — |
| R13, R14 type filter | 11 | 8 | GM-32 … GM-37, GM-39 | **Finding 2** (3) |
| R15 combined | 3 | 3 | GM-40, GM-41 | — |
| R16, writes, locks | 12 | 10 | GM-42, GM-44 T1 … T7 | `gm_r16_for_no_key`, `gm_r16_for_share` |
| `get_latest_status_by_machine` R1 … R2 | 8 | 6 | LS-01, LS-02, LS-03 | **Finding 1** (2) |
| R3 … R7 | 16 | 15 | LS-04 … LS-14 | `ls_r6_factory_active` |
| writes, locks | 9 | 7 | LS-15 T1, T4 … T7 | `ls_rw_for_no_key`, `ls_rw_for_share` |
| `get_latest_status_map` R1 … R3 | 10 | 9 | LM-01 … LM-05, LM-11, LM-13, LM-16 … LM-18 | `lm_r1_none_only` |
| R4, R5 | 9 | 9 | LM-04, LM-07 … LM-12, LM-17 | — |
| R6 [BUG-1090] | 7 | 7 | LM-14, LM-15 | — |
| R7, R8, one read | 6 | 5 | LM-15, LM-16 … LM-19 | `lm_r7_factory_active` |
| writes, locks | 9 | 7 | LM-19 T1, T4 … T7 | `lm_rw_for_no_key`, `lm_rw_for_share` |
| **Total** | **148** | **131** | | **17** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `gm_r4_factory_active`, `ls_r6_factory_active`, `lm_r7_factory_active` | A filter on `Factory.is_active`. FD has `is_active True`, as the spec's soft delete does. Nothing in `app/` sets that column: only the model default writes it and only `app/dao/factory.py` line 84 reads it. An inactive, undeleted factory is not a state the app can reach. |
| `*_for_no_key`, `*_for_share` (6) | `FOR SHARE` and `FOR NO KEY UPDATE` pass Then 7, which looks only for `FOR UPDATE`. They are further shapes of the lock check that is covered, under a clause outside the numbered rules (cases Spec gap 5). A wider Then 7 would be one word if a later round wants it. |
| `gm_r6_cap_101`, `gm_r6_cap_500` | A silent cap above 101. R6 says "at most `limit`", which a cap keeps, and no rule says "no cap", unlike BUG-982. The API's limit is HR-7. |
| `lm_r1_none_only` | **Equivalent.** `[]` reaches `in_([])`, which returns no rows, so the result is `{}` either way. |

**Hand-variant details worth keeping:**
- **Plans change one result only.** `ls_r2_no_id` is the sole variant whose caught or survived outcome moves between plans.
- **Crashing variants.** `gm_r15_type_or_date` "caught" 8 cards only by crashing on my own bad SQL (a `UNION` on a `json` column). I replaced it with `gm_r15_type_drops_dates`, which GM-41 catches on an assertion; that replacement ran on the default plan only. The other non-assertion catches are real: the wrong error, a `None` result, or a read that must not happen.
- **Then lines forced alone.** For all three methods, a raw Core write forced T4, T5 and T6 of GM-44, LS-15 and LM-19 (except GM-44 T4: the inserted row shows in the read, so its T1 fires first). `with_for_update()` forced T7 of all three.
- **Dropped `ORDER BY` in the map** is caught by LM-15 alone on the default plan. Keep it strict.

## xfail tests against the reference
`maev\plug\ref_mae.py` swaps the source of `app.dao.machine_activity_event` in memory through a meta-path finder, built by asserted text edits in `variants_mae.py`. Nothing is written to `app/`.

| Base | Fix shape | Result with `--runxfail` |
|---|---|---|
| `fix` | `.order_by(id)`, last row wins | 78 passed |
| `fix_order_ca_id` | `.order_by(created_at, id)` | 78 passed |
| `fix_distinct` | `DISTINCT ON (machine_id)`, newest first | 78 passed |
| `fix_window` | ordered by `row_number()` | 78 passed |

**The alarm works:** `fix` with the markers on gives `1 failed, 76 passed, 1 xpassed`: LM-15 `XPASS(strict)`, LM-14 XPASS. A `max(id)` or Python tie-break stays silent on LM-15 and passes LM-14, which is cases Spec gap 3, already recorded; `lm_r6_python_max` confirms it.

## Reproduced claims
- **Result line of the notes holds.** Default runs: `76 passed, 1 xfailed, 1 xpassed` in 7 of 7, one of the two forms the notes allow. The brief's `2 xfailed` is the other form; it needs a plan where LM-14 fails.
- **LM-15 fails on Then 2 every time,** with no `ORDER BY` in the statement. **LM-14 fails on Then 3:** 3 of 3 runs with index and bitmap scans off. Its Then 1 and Then 2 hold.
- **LM-14's Then 3 is proven without relying on a plan:** today's query plus an explicit `ORDER BY id DESC` fails LM-14 on T3 in 3 of 3, with all 76 pass cards green. With `ORDER BY id` it passes. So no pass card depends on the order of the map's rows.
- **No flaky test.** All 76 pass cards passed and LM-15 failed in every run. The only movement is LM-14, which is why it is non-strict.
- **Notes figures checked:** 25 statements, 8 branches; `1 failed, 76 passed, 1 xpassed` for the alarm; 17 tests reach the map's statement (LM-03 … LM-19).
- **Mocks:** none. No `try`, no broad `pytest.raises`, no `if` in a test body.
- **`Given` facts checked by hand:** the standing fixtures match the Conventions row by row, FD keeps `is_active True`, and `w2` depends on `w1`, so ids rise in order. `mk_event` leaves `metadata_json` out of the constructor unless given, so GM-43 stores both forms of empty. MAE-GM-14 and GM-15 build E1 … E101 as the card says.

## Traceability
cases 78 · tests 78 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card in all 78. 76 `pass` cards have no marker; 2 xfail cards name BUG-1090, 1 strict and 1 non-strict, and BUG-1090 is in `docs/testing/bugs.md`. All 78 sit under `# [claude] <ID>`. `ruff check` passes.

## Limits of this round
- **Rebuild.** It compares Given rows, the When call, Then asserts and markers by AST, and finds 300 of 300 planted mistakes of 22 kinds. Its one report is its own: it reads "A recorder" in LM-18's Given as row A. It does not model the E1 … E101 Given or the order of code Given lines; I checked those by reading.
- **The references are mine.** Variants show what these tests catch around them. Another correct fix could expose a card that assumes something these do not.
- **Plans.** Three plans were forced with `PGOPTIONS`. The default plan is what the planner chose while other agents ran, so other plans are possible, as `ls_r2_no_id` shows.
- **Runs were not isolated.** Other agents' runs were live. Mutation is safe here because every kill is a plain `1 failed`. My lock variants locked only rows of their own uncommitted test transaction.
- **Not exercised:** anything at manager, service or HTTP level; a real race; BUG-1091, which belongs to the machine activity manager's spec.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/machine_activity_event.py tests/unit/dao/test_machine_activity_event.py --timeout 300 --json <scratch>/mut.json
  Mutants: 32 · killed 32 · timeout 0 · survived 0 · score 100%

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine_activity_event.py -q -p no:cacheprovider --cov=app.dao.machine_activity_event --cov-branch --cov-report=term-missing --tb=no
  app\dao\machine_activity_event.py      25      0      8      0   100%
  76 passed, 1 xfailed, 1 xpassed
pytest, default plan, 6 more runs                               76 passed, 1 xfailed, 1 xpassed (all 6)
pytest --runxfail -rf, default plan, 3 runs                     1 failed (LM-15), 77 passed
pytest --runxfail -rf, index and bitmap scans off, 6 runs       2 failed (LM-14 T3, LM-15 T2), 76 passed
MAEREF=fix | fix_order_ca_id | fix_distinct | fix_window -p ref_mae --runxfail      78 passed (each)
MAEREF=today -p ref_mae --runxfail                              1 failed (LM-15 T2), 77 passed
MAEREF=fix -p ref_mae                                           1 failed (LM-15 XPASS strict), 76 passed, 1 xpassed
MAEREF=fix+lm_r6_wrong_id_desc -p ref_mae --runxfail, 3 runs    1 failed (LM-14 T3), 77 passed
drive.py, 3 plans                                               139 variants each, one later replaced
drive.py --only *_core_*, default plan                          9 of 9 caught
drive.py --only gm_r15_type_drops_dates                         caught, GM-41 T1
propdrive.py, 7 bases on 3 plans                                as in the recipes table
rebuild.py                                                      78 cards, 1 report (tool's own, above)
rebuild.py --selftest                                           300 planted, 300 found, 22 kinds
.venv/Scripts/python.exe -m ruff check tests/unit/dao/test_machine_activity_event.py     All checks passed!
git diff --stat -- app/dao                                      (empty)
```
Scratch, all under `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\maev\`: `plug\ref_mae.py`, `plug\variants_mae.py`, `drive.py`, `propdrive.py`, `prop\test_mae_prop.py`, `rebuild.py`, `variants.jsonl`, `variants_seq.jsonl`, `variants_seq2.jsonl`, `variants_core.jsonl`, `v15.jsonl`, `mut.json`, `mut.log`, `test_machine_activity_event.delivered.py`.

Only this report was written in the repo. Nothing under `app/`, the spec, the cases file, the notes or the test file was edited: no test-side fix was needed, and the test file is byte-identical to the delivered copy. No commit. No model server. Nothing was stopped or killed.

## Fix list
1. **Case designer:** add cards for Findings 1 and 2, 3 cards; the recipes above are the Givens and Thens. None touches money or order workflow.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-10-31 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 79 passed · 2 xfail, 1 strict, 1 non-strict (reproduced ✅) · coverage 100% branch (25 statements, 8 branches)
> Mutation: not re-run; round 1 stands at 32 / 32 → 100% (32 mutants)
> Fidelity: **0 of 3 new tests unfaithful**
> Hand variants: 148 · 136 caught on the default plan, 12 not listed (the same 12 as round 1); the 5 rule gaps now fail on all three plans
> Source commit: e48a092 · Cases revision: 1 (81 cases; spec APPROVED, unchanged)

Findings 1 and 2 are closed. No test edited in this round, no commit.

### What changed since round 1
A line diff against my saved copy of the delivered file shows 3 added tests and nothing else: no existing test, helper or marker changed. So the 76 tests behind the round 1 kills are the same, and the mutation result stands: new tests can only add kills. `mutate.py` is unchanged too (9 050 bytes, 2026-10-30 23:50).

### The 3 new tests
Each was read against its card: every Given row, the When call, the Then line, and the marker. All 3 are right, and each matches its recipe. The rebuild agrees, and still finds 300 of 300 planted mistakes. Its one report is the LM-18 one from round 1, which is its own. The coverage matrix lists the new cards under `get_by_machine` R13 and `get_latest_status_by_machine` R2.

| Card | Recipe | Expect | Given | Then |
|---|---|---|---|---|
| MAE-GM-45 | P2 | pass | A = event T1, `event_type "updated"`; B = status row T2 | `ids(result) == [a.id]` for `event_type="updated"` |
| MAE-GM-46 | P3 | pass | A = event T1 | `result == []` for `event_type="item"` |
| MAE-LS-16 | P1 | pass | A, B = status rows T2, no update | `result.id == b.id` |

### The 5 round 1 survivors
Each ran on the reference with `--runxfail`, on three plans. All now fail on an assertion, on the card they should.

| Variant | Default | Sequential only | Index only |
|---|---|---|---|
| `ls_r2_no_id` | LS-03, **LS-16** T1, LM-14 T2 | **LS-16** T1 | LS-03, **LS-16** T1, LM-14 T2 |
| `ls_r2_ctid_asc` | LS-16 T1 | LS-16 T1 | LS-16 T1 |
| `gm_r13_contains_esc` | GM-45, GM-46 T1 | GM-45, GM-46 T1 | GM-45, GM-46 T1 |
| `gm_r13_startswith_esc` | GM-46 T1 | GM-46 T1 | GM-46 T1 |
| `gm_r13_endswith_esc` | GM-45 T1 | GM-45 T1 | GM-45 T1 |

The sequential column is the point of Finding 1: there LS-16 alone catches the dropped tiebreak, so the catch no longer rests on the plan.

### Rest of the batch
The full 148 ran once more on the default plan: 136 caught, and the 12 survivors are exactly the 12 under "Considered and not listed". None of those is a rule gap, so none holds up this verdict. No case designer item from them.

### Reproduced
- **Default runs:** 79 passed in 7 of 7. LM-14 xfailed in 1 and XPASSED in 6, both forms the notes allow.
- **`--runxfail`:** default plan 3 runs, `1 failed, 80 passed` (LM-15); index and bitmap scans off 3 runs, `2 failed, 79 passed` (LM-14, LM-15). On the reference plugin's `today` base, LM-15 fails on T2.
- **References:** `fix`, `fix_order_ca_id`, `fix_distinct`, `fix_window` each pass 81 of 81 with `--runxfail`. `fix` with the markers on gives `1 failed, 79 passed, 1 xpassed`: LM-15 `XPASS(strict)`, the alarm.
- **Notes:** the new Result line is right. I did not re-run their revision 1 table or their own variant runs; my results above agree with what they claim.
- **No flaky test.** The only movement is LM-14, as in round 1.

### Commands run
```
diff <scratch>/test_machine_activity_event.delivered.py tests/unit/dao/test_machine_activity_event.py     3 tests added, nothing else
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine_activity_event.py -q -p no:cacheprovider --cov=app.dao.machine_activity_event --cov-branch --cov-report=term-missing --tb=no
  app\dao\machine_activity_event.py      25      0      8      0   100%
  79 passed, 2 xfailed
pytest, default plan, 6 more runs                               79 passed, 1 xfailed, 1 xpassed (all 6)
pytest --runxfail, default plan, 3 runs                         1 failed, 80 passed
pytest --runxfail, index and bitmap scans off, 3 runs           2 failed, 79 passed
MAEREF=fix | fix_order_ca_id | fix_distinct | fix_window -p ref_mae --runxfail      81 passed (each)
MAEREF=today -p ref_mae --runxfail                              1 failed (LM-15 T2), 80 passed
MAEREF=fix -p ref_mae                                           1 failed (LM-15 XPASS strict), 79 passed, 1 xpassed
drive.py --only <the 5 survivors>, 3 plans                      5 of 5 caught on each
drive.py, default plan                                          148 run, 136 caught, 12 survived
rebuild.py                                                      81 cards, 1 report (tool's own)
rebuild.py --selftest                                           300 planted, 300 found, 22 kinds
.venv/Scripts/python.exe -m ruff check tests/unit/dao/test_machine_activity_event.py     All checks passed!
git diff --stat -- app/dao                                      (empty)
```
Scratch in `maev\`: `r2_def.jsonl`, `r2_seq.jsonl`, `r2_idx.jsonl`, `r2_all.jsonl`, `r2_all.log`. Only this report was edited in the repo. Nothing was stopped or killed in this round.
