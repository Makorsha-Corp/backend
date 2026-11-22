# Verification — `app/dao/account.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 3, 76 cases). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 51 passed · 15 xfail, 13 strict, 2 non-strict (reproduced ✅) · coverage 96% branch (21 statements, 4 branches; line 31 dead)
> Mutation: 43 mutants · 33 killed · 10 survived → score 100% (after excluding 0 equivalent, 10 dead, 0 bug-path)
> Fidelity: **0 of 66 unfaithful** (66 / 66 right)
> Hand variants: 82 · 50 caught by a pass card · 32 others: 8 rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: 2; spec APPROVED (Gap log G1 applied)

## Summary
- **The tests can be trusted as written.** This file was read fully by eye, against every card. All 66 match, and my script agrees.
- **Why NEEDS WORK:** every mutant is killed or sits in dead code, but hand variants show 8 rule gaps, for the case designer. The largest: the workspace filters are tested only against a workspace with a higher id, and "accounts with tag N" never meets an account or link from another workspace.
- **Money:** none here. The invoice rows in ACC-INH-07 / 09 only block a delete.

Written by Claude (all 66 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 66. No `account.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_accounts_in_workspace` R1, workspace filter | Every IW card asks W1, and every other workspace's row is in W2, the higher id. A `<=` on the workspace passes. | `iw_r1_ws_le` passes all 66 on all three plans. | **case designer** |
| 2 | case-missing | `get_accounts_in_workspace` R5, the link's workspace | ACC-IW-16 records the link in W2, the higher id. A `<=` on the link's workspace passes. | `iw_r5_ws_le` passes all 66 on all three plans. | **case designer** |
| 3 | case-missing | `get_accounts_in_workspace` R5 "a tag with that code" (exact today; case-insensitive and trimmed after BUG-861) | No argument that is the end of the code, no stored code that is a part of the argument, no stored `_`. | `iw_r5_ends`, `iw_r5_rev_contains`, `iw_r5_rev_like` pass all 66 on all three plans. | **case designer** |
| 4 | case-missing | `get_accounts_in_workspace` R7 "returned once" with R10 paging | ACC-IW-24 has no `limit`, and the ORM drops duplicate rows after the database has counted them. A join without `DISTINCT` (the likely way to fix BUG-866, whose spec note says `DISTINCT` must go) lets one account take two places of a page. | `iw_r7_join_dup` passes all 66 on all three plans. | **case designer** |
| 5 | case-missing | `get_accounts_in_workspace` R2 [BUG-637] "`name` is trimmed" | ACC-IW-09's `" acme "` still matches "Acme Ltd" when only the left side is trimmed, because "Acme " is in the name. No xfail card has a trailing space that is not in the name. | `iw_r2_lstrip` passes all 66, xfail cards included, on all three plans. | **case designer** |
| 6 | case-missing | `get_accounts_in_workspace` R8 [BUG-866], `get_accounts_by_tag_id` R4 [BUG-1480] "then `id` ascending" | ACC-IW-28 and ACC-BT-09 check that `accounts.id` is in the `ORDER BY`, not its direction; the order cards have no tied names. | `iw_r8_tail_desc`, `bt_r4_tail_desc` pass all 66, xfail cards included. | **case designer** |
| 7 | case-missing | `get_accounts_by_tag_id` R1 "accounts of `workspace_id` … an assignment recorded in `workspace_id`" | No card has an account of another workspace or a link recorded in a lower workspace. The account's own workspace filter can be dropped. | `bt_r1_accws_le`, `bt_r1_accws_ge`, `bt_r1_accws_drop`, `bt_r1_linkws_le` pass all 66 on all three plans. | **case designer** |
| 8 | case-missing | `get_accounts_by_tag_id` R2 "only the assignment's `tag_id` is compared" | No card links an account to another workspace's tag. A filter on the tag's workspace passes. ACC-IW-25 does this for the other list. | `bt_r2_tag_ws_added` passes all 66 on all three plans. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctv\prop\test_prop_account.py`, not in the repo. Each passes on today's code, or fails as its strict xfail says, and passes on my reference. Each named variant fails its recipe, on all three plans.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, IW R1 | Z1 = account, `name "Acme Far"`; A1 = account, `name "Acme Ltd"`, but `workspace_id W2.id`. When `get_accounts_in_workspace(db, workspace_id=W2.id)` | `ids(result) == [A1.id]` | pass | `iw_r1_ws_le` |
| R-2 | new card, IW R5 | T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `workspace_id W2.id`; A1 = account, `name "Acme Ltd"`, but `workspace_id W2.id`; L1 = link(A1, T1) (recorded in W1). When `workspace_id=W2.id, tag_code="supplier"` | `result == []` | pass | `iw_r5_ws_le` |
| R-3 | three new cards, IW R5 | T1 = tag, `name "Supplier"`, but `tag_code` (a) `"supplier"`, (b) `"supp"`, (c) `"s_pplier"`; A1 = account, `name "Acme Ltd"`; L1 = link(A1, T1). When `tag_code=` (a) `"plier"`, (b) `"supplier"`, (c) `"supplier"` | `result == []` | pass | (a) `iw_r5_ends`; (b) `iw_r5_rev_contains`; (c) `iw_r5_rev_like`, `iw_r5_rev_contains` |
| R-4 | new card, IW R7 + R10 | T1 = tag, `name "Supplier A"`, `tag_code "supplier"`; T2 = tag, `name "Supplier B"`, `tag_code "supplier"`; A1 = account, `name "Acme Ltd"`; A2 = account, `name "Beta Co"`; link(A1, T1); link(A1, T2); link(A2, T1). When `tag_code="supplier", limit=2` | `sorted(ids(result)) == [A1.id, A2.id]` | pass | `iw_r7_join_dup` |
| R-5 | new card, IW R2 | A1 = account, `name "Acme Ltd"`; A2 = account, `name "Beta Co"`. When `name="ltd "` | `ids(result) == [A1.id]` | xfail BUG-637, fails today on Then 1 (`[]`) | `iw_r2_lstrip` |
| R-6 | one new Then line each on ACC-IW-28 and ACC-BT-09 | as the cards | `statement: "DESC" not in order_part.upper()` | the cards' strict xfail; the line holds after the fix | `iw_r8_tail_desc`, `bt_r4_tail_desc` |
| R-7 | two new cards, BT R1 | (a) T1 = tag, `name "Supplier"`, `tag_code "supplier"`; Z1 = account, `name "Far"`, but `workspace_id W2.id`; A1 = account, `name "Acme Ltd"`; link(Z1, T1) (recorded in W1); link(A1, T1). When `get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=T1.id)`. (b) T1 as (a); A1 = account, `name "Acme Ltd"`; Z1 = account, `name "Far"`, but `workspace_id W2.id`; link(A1, T1), but `workspace_id W2.id`; link(Z1, T1) (recorded in W1). When `workspace_id=W2.id, tag_id=T1.id` | (a) `ids(result) == [A1.id]`; (b) `result == []` | pass | (a) `bt_r1_accws_ge`, `bt_r1_accws_drop`; (b) `bt_r1_accws_le`, `bt_r1_linkws_le` |
| R-8 | new card, BT R2 | Z1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `workspace_id W2.id`; A1 = account, `name "Acme Ltd"`; link(A1, Z1). When `workspace_id=W1.id, tag_id=Z1.id` | `ids(result) == [A1.id]` | pass | `bt_r2_tag_ws_added` |

R-7 and R-8 build cross-workspace rows, which HR-16 calls invalid data; the rules name these filters, so the cards pin them, as ACC-IW-25 does for the other list.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | 31 | `return None` | dead | `search_by_name_in_workspace`, spec "Not specified" (P3, remove; dead-code checklist) | — |
| 7 | 16 | `skip` default 0 → 1 | dead | same method | — |
| 8 | 16 | `limit` default 100 → 101 | dead | same method | — |
| 29 | 34 | `==` → `!=` on workspace | dead | same method | — |
| 30 | 36 | `==` → `!=` on `is_active` | dead | same method | — |
| 31 | 37 | `==` → `!=` on `is_deleted` | dead | same method | — |
| 32 | 36 | `True` → `False` | dead | same method | — |
| 33 | 37 | `False` → `True` | dead | same method | — |
| 34 | 35 | `'%'` → `''` (left) | dead | same method | — |
| 35 | 35 | `'%'` → `''` (right) | dead | same method | — |

**Guard.** My own driver re-ran each of the 43 mutants with no `-x`: every run reached all 51 pass tests, with no collection or setup error, and each status matched `mutate.py`. All 33 kills end in a plain `N failed`.

## Hand variants
`variants.py`, on my reference with `--runxfail`, on the default plan, with sequential scans off and with index and bitmap scans off: the same variants caught by the same pass cards. Every edit was asserted to apply once, and every run reached all 66 tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| iw_r1 | 6 | 5 | ACC-IW-02, ACC-IW-04, ACC-IW-05, ACC-IW-35, ACC-IW-36 | `iw_r1_ws_le` |
| iw_r1a | 1 | 1 | ACC-IW-02, ACC-IW-35 | — |
| iw_r2 | 3 | 0 | — | `iw_r2_notrim`, `iw_r2_lstrip`, `iw_r2_rstrip` |
| iw_r3 | 6 | 5 | ACC-IW-10, ACC-IW-26 | `iw_r3_noescape` |
| iw_r5 | 17 | 7 | ACC-IW-15, ACC-IW-16, ACC-IW-20, ACC-IW-21, ACC-IW-25, ACC-IW-26 | `iw_r5_ws_le`, `iw_r5_ends`, `iw_r5_rev_contains`, `iw_r5_rev_like`, `iw_r5_exact`, `iw_r5_nolower_arg`, `iw_r5_nolower_col`, `iw_r5_notrim_arg`, `iw_r5_notrim_col`, `iw_r5_ltrim_col` |
| iw_r6 | 1 | 0 | — | `iw_r6_active_drop` |
| iw_r7 | 2 | 1 | ACC-IW-25 | `iw_r7_join_dup` |
| iw_r8 | 6 | 0 | — | `iw_r8_no_order`, `iw_r8_no_tail`, `iw_r8_tail_desc`, `iw_r8_name_cs`, `iw_r8_name_desc`, `iw_r8_order_after_page` |
| iw_r9 | 1 | 1 | ACC-IW-26 | — |
| iw_r10 | 7 | 7 | ACC-IW-29, ACC-IW-30, ACC-IW-31, ACC-IW-32, ACC-IW-33, ACC-IW-34 | — |
| iw_w | 3 | 3 | ACC-IW-33, ACC-IW-34, ACC-IW-36 | — |
| cnt_r1 | 4 | 4 | ACC-CNT-01, ACC-CNT-03 | — |
| cnt_r2 | 1 | 1 | ACC-CNT-02 | — |
| cnt_r3 | 1 | 1 | ACC-CNT-03 | — |
| bt_r1 | 9 | 5 | ACC-BT-02, ACC-BT-03, ACC-BT-04, ACC-BT-15 | `bt_r1_accws_le`, `bt_r1_accws_ge`, `bt_r1_accws_drop`, `bt_r1_linkws_le` |
| bt_r2 | 3 | 2 | ACC-BT-01, ACC-BT-06 | `bt_r2_tag_ws_added` |
| bt_r3 | 1 | 0 | — | `bt_r3_tagactive_drop` |
| bt_r4 | 3 | 0 | — | `bt_r4_no_order`, `bt_r4_no_tail`, `bt_r4_tail_desc` |
| bt_r5 | 5 | 5 | ACC-BT-01, ACC-BT-02, ACC-BT-03, ACC-BT-10, ACC-BT-11, ACC-BT-13 … | — |
| bt_w | 2 | 2 | ACC-BT-16 | — |
| **Total** | **82** | **50** |  | **32** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `iw_r2_notrim`, `iw_r2_rstrip`, `iw_r3_noescape`, `iw_r5_exact`, `iw_r5_nolower_arg`, `iw_r5_nolower_col`, `iw_r5_notrim_arg`, `iw_r6_active_drop`, `iw_r8_*` (5 of 6), `bt_r3_tagactive_drop`, `bt_r4_no_order`, `bt_r4_no_tail` | **Bug path.** Today's behaviour of BUG-637, BUG-868, BUG-861, BUG-864, BUG-866, BUG-1481, BUG-1480; each fails its strict xfail card (or the non-strict order card) on the reference, which is what those cards are for. `iw_r2_lstrip`, `iw_r8_tail_desc`, `bt_r4_tail_desc` are not caught by them: Findings 5, 6. |
| `iw_r5_notrim_col`, `iw_r5_ltrim_col` | A stored code with a leading space. HR-3 has codes stored trimmed, so the filter need not trim the stored side. |

## xfail tests against the reference
Reference: my in-memory rewrite of `get_accounts_in_workspace` (`include_inactive`; name trimmed, blank = no filter; `%`, `_`, `\` escaped; code trimmed and lower-cased on both sides; active tags only; `EXISTS` instead of join + `DISTINCT`; `ORDER BY lower(name), id`) and `get_accounts_by_tag_id` (active tag only; same order). Nothing is written to `app/`.

With `--runxfail` on the reference: 66 passed, on all three plans. **The alarm works:** with the markers on, `13 failed, 51 passed, 2 xpassed`, the 13 strict cards `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| ACC-IW-06 | strict | the call (`TypeError`: no `include_inactive`), as the card says |
| ACC-IW-08, 09, 11, 12, 13, 17, 18, 19, 22 | strict | Then 1, in all 3 plans |
| ACC-IW-27, ACC-BT-08 | non-strict | Then 2, in all 3 plans |
| ACC-IW-28, ACC-BT-07, ACC-BT-09 | strict | Then 2, in all 3 plans (BT-07's Then 1 holds) |

## Reproduced claims
- **Result line of the notes holds:** `51 passed, 15 xfailed` in 4 of 4 default runs, the coverage run among them. No flaky test.
- `--runxfail` on today's code: `15 failed, 51 passed` on all three plans; each fails on the line its card names (table above).
- Coverage: 96% branch; the one missed line is 31, the dead method.
- **Mocks:** none. No `try`, no broad `pytest.raises`.

## Traceability
cases 66 · tests 66 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID (878, 637, 868, 861, 864, 866, 1480, 1481) is in `docs/testing/bugs.md`. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script (`rebuild.py`) rebuilt each test's Given rows, steps, When, Then assertions and marker from its card and compared them by AST, for all 205 cards of the batch: 0 reports here. Selftest: 1141 of 1141 planted mistakes of 40 kinds, in tests and cards.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live on the shared test database; each kill is a plain `N failed`.
- **Not exercised:** manager, service or HTTP level.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/account.py tests/unit/dao/test_account.py --timeout 300 --json <scratch>/res/mut_account.json
  43 mutants · 33 killed · 10 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_account.py -q -p no:cacheprovider --cov=app.dao.account --cov-branch --cov-report=term-missing
  51 passed, 15 xfailed · TOTAL 21 1 4 0 96%
pytest (same file), 3 more default runs                       51 passed, 15 xfailed each
drive.py bases account; rx.py; drive.py muts account; drive.py vars account (3 plans); propdrive.py
rebuild.py; rebuild.py --selftest 30                          205 cards, 0 reports; 1141 of 1141
.venv/Scripts/python.exe -m ruff check <the seven test files>  All checks passed!
git diff --stat -- app/dao app/core                           (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctv\`. Private `COVERAGE_FILE`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add R-1 to R-8; the Givens and Thens are written out above.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 3, narrow)

> **Verdict:** PASS
> Tests: 60 passed · 16 xfail, 14 strict, 2 non-strict (reproduced ✅) · coverage 96% branch (line 31 dead, as before)
> Mutation: not re-run; round 1 stands at 33 / 33 → 100% (43 mutants, 10 dead)
> Fidelity: **0 of 76 unfaithful** (the 10 new tests and the 2 changed ones read by eye; all 76 rebuilt by script)
> Source commit: e48a092 · Cases revision: 3; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test edited in this round.

### New and changed tests
Each was read against its card and matches its recipe. "Fails" means the variant fails that card, on my reference with `--runxfail`, on all three plans; every run reached all 76 tests.

| Card | Recipe | Fails |
|---|---|---|
| ACC-IW-37 | R-1 | `iw_r1_ws_le` |
| ACC-IW-38 | R-2 | `iw_r5_ws_le` |
| ACC-IW-39 | R-3 (a) | `iw_r5_ends` |
| ACC-IW-40 | R-3 (b) | `iw_r5_rev_contains` |
| ACC-IW-41 | R-3 (c) | `iw_r5_rev_like`, `iw_r5_rev_contains` |
| ACC-IW-42 | R-4 | `iw_r7_join_dup` |
| ACC-IW-43 (xfail BUG-637) | R-5 | `iw_r2_lstrip` |
| ACC-IW-28, Then 5 | R-6 | `iw_r8_tail_desc` |
| ACC-BT-09, Then 5 | R-6 | `bt_r4_tail_desc` |
| ACC-BT-17 | R-7 (a) | `bt_r1_accws_ge`, `bt_r1_accws_drop` |
| ACC-BT-18 | R-7 (b) | `bt_r1_accws_le`, `bt_r1_linkws_le`, `bt_r1_accws_drop` |
| ACC-BT-19 | R-8 | `bt_r2_tag_ws_added` |

### Reproduced
- **Result line of the notes holds:** `60 passed, 16 xfailed` in 3 of 3 default runs, the coverage run among them. No flaky test.
- **`--runxfail`:** `16 failed, 60 passed` on all three plans; every xfail fails on the Then its card names (ACC-IW-43 on Then 1; IW-28 and BT-09 still on Then 2).
- **Reference:** 76 passed with `--runxfail`, on all three plans. **Alarm:** with the markers on, `14 failed, 60 passed, 2 xpassed`, the 14 strict cards `XPASS(strict)`.
- **Traceability:** cases 76 · tests 76 · unmatched: none · marker mismatches: none. `rebuild.py`: 0 reports here. `ruff check` passes.
- **Limit of my script, found by its selftest this round:** it compares Given rows by their columns, so swapping two rows built with identical columns (only the variable name differs) goes unnoticed. The new tests here have no such rows; I read them by eye.

### Commands run
```
rebuild.py; rebuild.py --selftest 30                           221 cards over the seven files, 1 report (LIM-01 docstring)
drive.py one-off runs: var:account:<gap variant> --runxfail × 3 plans   each named variant fails its new card
drive.py bases account; rx.py                                  as under Reproduced
pytest tests/unit/dao/test_account.py --cov=app.dao.account --cov-branch, then 2 more runs
git diff --stat -- app/dao app/core                            (empty)
```
No full mutation run (narrow round). Only this report was edited in the repo. No commit. Nothing was killed.
