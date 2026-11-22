# Verification — `app/dao/account_tag.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 3, 61 cases). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 49 passed · 10 xfail, 7 strict, 3 non-strict (reproduced ✅) · coverage 100% branch (24 statements, 4 branches)
> Mutation: 22 mutants · 21 killed · 1 survived → score 100% (after excluding 0 equivalent, 0 dead, 1 bug-path)
> Fidelity: **0 of 59 unfaithful** (59 / 59 right)
> Hand variants: 67 · 50 caught by a pass card · 17 others: 3 rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: 2; spec APPROVED (Gap log G1 applied)

## Summary
- **The tests can be trusted as written.** This file was read fully by eye, against every card. All 59 match, and my script agrees.
- **Why NEEDS WORK:** two small gaps in the exact code compare and one in the tie-break direction of the system list, for the case designer.
- **Counters:** the usage counter is not money or stock. Every counter rule that holds today is caught; the stale-object rule (BUG-1484) is caught only by its strict xfail cards, as designed.
- **Not flaky, noted:** in 1 of 34 default runs a non-strict BUG-1482 order card passed by accident (`49 passed, 9 xfailed, 1 xpassed`). Its marker allows that; no pass card moved.

Written by Claude (all 59 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 59. No `account_tag.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_by_tag_code_in_workspace` R2 "Exact comparison" | No argument with a trailing space. A right-trim of the argument passes. | `code_r2_rtrim_arg` passes all 59 on all three plans. | **case designer** |
| 2 | case-missing | `get_by_tag_code_in_workspace` R2, stored side | ATG-CODE-11 tests capitals and a leading space in the stored code, not a stored `_`. An argument `LIKE` stored-code compare passes. | `code_r2_rev_like` passes all 59 on all three plans. | **case designer** |
| 3 | case-missing | `get_system_tags_in_workspace` R3 [BUG-1482] "then `id` ascending" | ATG-SYS-07 checks that `account_tags.id` is in the `ORDER BY`, not its direction; ATG-SYS-06 has no tied names. | `sys_r3_tail_desc` passes all 59, xfail cards included. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctv\prop\test_prop_tags.py`, not in the repo. Each passes on today's code, or fails as its strict xfail says, and passes on my reference. Each named variant fails its recipe, on all three plans.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| T-1 | two new cards, CODE R2 | (a) T1 = tag, `name "Supplier"`, `tag_code "supplier"`; When `get_by_tag_code_in_workspace(db, workspace_id=W1.id, tag_code="supplier ")`. (b) T1 = tag, `name "Supplier"`, `tag_code "s_pplier"`; When `tag_code="supplier"` | `result is None` | pass | (a) `code_r2_rtrim_arg`; (b) `code_r2_rev_like` |
| T-2 | one new Then line on ATG-SYS-07 | as the card | `statement: "DESC" not in order_part.upper()` | the card's strict xfail; the line holds after the fix | `sys_r3_tail_desc` |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 9 | 37 | `limit` default 100 → 101 | bug-path | R2 [BUG-1485]: the cap itself is the bug. ATG-ACT-05 (strict xfail, 101 tags) is the card that targets it and is excluded from the run; ATG-ACT-06 (100 active) holds under both values. | — |

**Guard.** My own driver re-ran each of the 22 mutants with no `-x`: every run reached all 49 pass tests, with no collection or setup error, and each status matched `mutate.py`. All 21 kills end in a plain `N failed`.

## Hand variants
`variants.py`, on my reference with `--runxfail`, on three plans (default; sequential scans off; index and bitmap scans off): the same variants caught by the same pass cards. Every edit was asserted to apply once, and every run reached all 59 tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| code_r1 | 3 | 3 | ATG-CODE-02, ATG-CODE-03, ATG-CODE-04 | — |
| code_r2 | 15 | 12 | ATG-CODE-05 … ATG-CODE-11 | `code_r2_rtrim_arg`, `code_r2_rev_like`, `code_r2_rtrim_col` |
| code_r3 | 2 | 2 | ATG-CODE-12 | — |
| code_r4 | 1 | 1 | ATG-CODE-13 | — |
| code_w | 2 | 2 | ATG-CODE-13 | — |
| act_r1 | 4 | 4 | ATG-ACT-01, ATG-ACT-02, ATG-ACT-03, ATG-ACT-04, ATG-ACT-06, ATG-ACT-10 | — |
| act_r2 | 2 | 1 | ATG-ACT-06 | `act_r2_cap_100` |
| act_r3 | 2 | 0 | — | `act_r3_system_last`, `act_r3_no_system` |
| act_r4 | 3 | 0 | — | `act_r4_name_cs`, `act_r4_no_tail`, `act_r4_tail_desc` |
| act_w | 2 | 2 | ATG-ACT-10 | — |
| sys_r1 | 4 | 4 | ATG-SYS-01, ATG-SYS-02, ATG-SYS-03, ATG-SYS-04, ATG-SYS-08 | — |
| sys_r2 | 1 | 0 | — | `sys_r2_active_drop` |
| sys_r3 | 4 | 0 | — | `sys_r3_tail_desc`, `sys_r3_no_order`, `sys_r3_no_tail`, `sys_r3_system_first` |
| sys_w | 1 | 1 | ATG-SYS-08 | — |
| inc_r1 … inc_r6 | 10 | 9 | ATG-INC-01 … ATG-INC-05, ATG-INC-07, ATG-INC-08, ATG-INC-09 | `inc_r5_loaded` |
| dec_r1 … dec_r7 | 11 | 9 | ATG-DEC-01 … ATG-DEC-07, ATG-DEC-10, ATG-DEC-11 | `dec_r6_loaded_check`, `dec_r6_no_else_set` |
| **Total** | **67** | **50** |  | **17** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `act_r2_cap_100`, `act_r3_*` (2), `act_r4_*` (3), `sys_r2_active_drop`, `sys_r3_no_order`, `sys_r3_no_tail`, `inc_r5_loaded`, `dec_r6_*` (2) | **Bug path.** Today's behaviour of BUG-1485, BUG-1482, BUG-1483, BUG-1484; each fails its strict xfail card (ACT-05, ACT-09, SYS-05, SYS-07, INC-06, DEC-08, DEC-09) or its non-strict order card on the reference. `sys_r3_tail_desc` is not caught by them: Finding 3. |
| `sys_r3_system_first` | **Equivalent:** every row of the system list has `is_system_tag = True`, so sorting on it first changes nothing. |
| `code_r2_rtrim_col` | A stored code with a trailing space. HR-3 has codes stored trimmed; the leading-space card (ATG-CODE-11) is what the exact-compare shape asks for on the stored side. |

## xfail tests against the reference
Reference: my in-memory rewrite (both lists ordered, the active list `is_system_tag DESC, lower(name), id` with no cap, the system list active only; the counters as one `UPDATE … RETURNING` on the stored value, decrement only where above 0, the stored result set on the returned object, flushed only when written). Nothing is written to `app/`.

With `--runxfail` on the reference: 59 passed, on all three plans. **The alarm works:** with the markers on, `7 failed, 49 passed, 3 xpassed`, the 7 strict cards `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| ATG-ACT-05, ACT-09, SYS-05, SYS-07, INC-06, DEC-08, DEC-09 | strict | Then 2, in all 3 plans, as the cards say |
| ATG-ACT-07, ACT-08, SYS-06 | non-strict | Then 2, in all 3 plans |

## Reproduced claims
- **Result line of the notes holds:** `49 passed, 10 xfailed` in 33 of 34 default runs (the coverage run among them); the other run had one non-strict card XPASS (see Summary). No pass card moved; no flaky test.
- `--runxfail` on today's code: `10 failed, 49 passed` on all three plans; each fails on the line its card names.
- Coverage: 100% branch.
- **Mocks:** the `db.commit` spy of ATG-INC-09 / DEC-11 only (`patch.object(db, "commit", wraps=db.commit)`, the Conventions' **rolled back**). No `try`, no broad `pytest.raises`.

## Traceability
cases 59 · tests 59 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID (1482, 1483, 1484, 1485) is in `docs/testing/bugs.md`. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script (`rebuild.py`) rebuilt each test's Given rows, steps, When, Then assertions and marker from its card and compared them by AST: 0 reports here. Selftest: 1141 of 1141 planted mistakes of 40 kinds.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live; each kill is a plain `N failed`.
- **Not exercised:** a real race between two transactions (BUG-1484 is tested with a stale object in one session, as the spec directs).

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/account_tag.py tests/unit/dao/test_account_tag.py --timeout 300 --json <scratch>/res/mut_account_tag.json
  22 mutants · 21 killed · 1 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_account_tag.py -q -p no:cacheprovider --cov=app.dao.account_tag --cov-branch --cov-report=term-missing
  49 passed, 10 xfailed · TOTAL 24 0 4 0 100%
pytest (same file), 33 more default runs                      32 × 49 passed, 10 xfailed; 1 × 49 passed, 9 xfailed, 1 xpassed
drive.py bases account_tag; rx.py; drive.py muts account_tag; drive.py vars account_tag (3 plans); propdrive.py
rebuild.py; rebuild.py --selftest 30                          205 cards, 0 reports; 1141 of 1141
.venv/Scripts/python.exe -m ruff check <the seven test files>  All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctv\`. Private `COVERAGE_FILE`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add T-1 and T-2; the Givens and Thens are written out above.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 3, narrow)

> **Verdict:** PASS
> Tests: 51 passed · 10 xfail, 7 strict, 3 non-strict (reproduced ✅) · coverage 100% branch
> Mutation: not re-run; round 1 stands at 21 / 21 → 100% (22 mutants, 1 bug-path)
> Fidelity: **0 of 61 unfaithful** (the 2 new tests and ATG-SYS-07 read by eye; all 61 rebuilt by script)
> Source commit: e48a092 · Cases revision: 3; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test edited in this round.

### New and changed tests
"Fails" means the variant fails that card, on my reference with `--runxfail`, on all three plans; every run reached all 61 tests.

| Card | Recipe | Fails |
|---|---|---|
| ATG-CODE-14 | T-1 (a) | `code_r2_rtrim_arg` |
| ATG-CODE-15 | T-1 (b) | `code_r2_rev_like` |
| ATG-SYS-07, Then 5 | T-2 | `sys_r3_tail_desc` |

### Reproduced
- **Result line of the notes holds:** `51 passed, 10 xfailed` in 3 of 3 default runs, the coverage run among them.
- **`--runxfail`:** `10 failed, 51 passed` on all three plans; every xfail fails on the Then its card names.
- **Reference:** 61 passed with `--runxfail`, on all three plans. **Alarm:** with the markers on, `7 failed, 51 passed, 3 xpassed`, the 7 strict cards `XPASS(strict)`.
- **Traceability:** cases 61 · tests 61 · unmatched: none · marker mismatches: none. `rebuild.py`: 0 reports here. `ruff check` passes.

### Commands run
```
rebuild.py; rebuild.py --selftest 30                           221 cards, 0 reports here
var:account_tag:<gap variant> --runxfail × 3 plans             each named variant fails its new card
drive.py bases account_tag; rx.py
pytest tests/unit/dao/test_account_tag.py --cov=app.dao.account_tag --cov-branch, then 2 more runs
```
No full mutation run (narrow round). Only this report was edited in the repo. No commit. Nothing was killed.
