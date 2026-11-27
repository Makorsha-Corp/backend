# Verification — `app/dao/workspace_invitation.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 43 cases). See "Round 2" at the end. The rest of this block is round 1.
>

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 28 passed · 9 xfail, 6 strict, 3 non-strict (reproduced ✅) · coverage 100% branch (17 statements, 0 branches)
> Mutation: 19 mutants · 19 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 37 unfaithful** (37 / 37 right; read fully by eye and rebuilt by script)
> Hand variants: 120 · 86 caught by a pass card · 34 others: 11 rule gaps in Findings, 23 bug path
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** I read all 37 tests by eye against their cards (Given order, "but" columns, the patch around every When, the recorder, the `# Then N` lines, the markers), and my script agrees.
- **Why NEEDS WORK:** every mutant is killed, but hand variants show 4 rule gaps, for the case designer. Each of the three queries carries its own copy of the "pending" filter, and the status shapes were tested on `get_pending_invitations` only. The other workspace is always the later id.
- BUG-1402's fix is not fully pinned: no card stores an email with spaces around it, although R2 says "on both sides".

Written by Claude (all 37 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 37. No `workspace_invitation.local-run.json`, so no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_user_invitations` R1 ("pending … as `get_pending_invitations` R1": status exactly `'pending'`) | UI-01 has only an `accepted` row against the status filter: no `Pending`, no ` pending`, no `cancelled`. It is its own query, not a shared helper (1b). | `ui_r1_status_lower_col`, `_trim_col`, `_ltrim_col`, `_ilike`, `_not_accepted` pass all 37. | **case designer** |
| 2 | case-missing | `count_pending_invitations` R1 | CP-01 has `Pending` but no ` pending`. | `cp_r1_status_trim_col`, `cp_r1_status_ltrim_col` pass all 37. | **case designer** |
| 3 | case-missing | `get_pending_invitations` R3, `count_pending_invitations` R1, `get_all_invitations` R1 (another workspace never appears) | The other workspace's row is always W2, asked about as W1. | `gp_r3_ws_le`, `cp_r3_ws_le`, `ga_r1_ws_le` pass all 37. | **case designer** |
| 4 | case-missing | `get_user_invitations` R2 [BUG-1402] ("surrounding spaces on both sides") | UI-03 pads the argument; no card stores a padded email. After the fix nothing would notice a fix that trims only the argument. | On my reference, `ui_r2_no_trim_col` passes all 37 with `--runxfail`. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\prop\test_p_workspace_invitation.py`, not in the repo. Every When runs under the `utcnow` patch. Each passes on today's code (R-4 xfails) and on my reference; each named variant fails it.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, UI R1 | A = invitation A; B = invitation B, but `status "Pending"`; C = invitation C, but `status " pending"`; D = invitation D, but `status "cancelled"`. When `dao.get_user_invitations(db, email="a@x.com")` | `idset(result) == {A.id}` | pass | the five `ui_r1_status_*` |
| R-2 | new card, CP R1 | A = invitation A; C = invitation C, but `status " pending"`. When `dao.count_pending_invitations(db, workspace_id=W1.id)` | `result == 1` | pass | `cp_r1_status_trim_col`, `cp_r1_status_ltrim_col` |
| R-3 | three new cards, GP R3, CP R1, GA R1 | Z = invitation Z; A = invitation A, but `workspace_id W2.id`. When `get_pending_invitations` / `count_pending_invitations` / `get_all_invitations` with `workspace_id=W2.id` | `idset(result) == {A.id}`; `result == 1`; `idset(result) == {A.id}` | pass | `gp_r3_ws_le`; `cp_r3_ws_le`; `ga_r1_ws_le` |
| R-4 | new card, UI R2 | A = invitation A, but `email " john.doe@example.com"`. When `dao.get_user_invitations(db, email="john.doe@example.com")` | `ids(result) == [A.id]` | xfail BUG-1402 (strict); fails today on Then 1 | `ui_r2_no_trim_col` (on the reference) |

## Surviving mutants
None. All 19 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 19 mutants with all tests, markers on, no `-x`: every run reached all 37 tests, with no collection or setup error.

## Hand variants
On my reference (`plug\ref\workspace_invitation.py`: `ORDER BY invited_at DESC, id DESC` on the three lists; email `lower(btrim(col)) == arg.strip().lower()`) with `--runxfail`, default plan. Every edit applied once; every run reached all 37 tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| gt_r2 (token exact compare) | 13 | 13 | WSI-GT-01 … GT-06 | — |
| gp_r1 | 6 | 6 | WSI-GP-01 | — |
| gp_r2 | 3 | 3 | WSI-GP-01, GP-02, GP-04, GP-05, GP-08 | — |
| gp_r3 | 4 | 3 | WSI-GP-01, GP-03, GP-04, GP-05 | `gp_r3_ws_le` |
| gp_r4 | 7 | 0 | — | the seven `gp_r4_ord_*` |
| ui_r1 | 6 | 1 | WSI-UI-01 | five `ui_r1_status_*` |
| ui_r2 | 10 | 7 | WSI-UI-01, UI-05, UI-06, UI-07, UI-10, UI-11 | `ui_r2_no_trim_col`, `ui_r2_no_trim_arg`, `ui_r2_exact` |
| ui_r3 | 1 | 1 | WSI-UI-07 | — |
| ui_r4 | 7 | 0 | — | the seven `ui_r4_ord_*` |
| cp_r1 | 6 | 4 | WSI-CP-01, CP-02 | `cp_r1_status_trim_col`, `cp_r1_status_ltrim_col` |
| cp_r2 | 3 | 3 | WSI-CP-01, CP-02, CP-04 | — |
| cp_r3 | 3 | 2 | WSI-CP-01, CP-03, CP-04 | `cp_r3_ws_le` |
| ga_r1 | 3 | 2 | WSI-GA-01, GA-03, GA-07 | `ga_r1_ws_le` |
| ga_r2 | 1 | 1 | WSI-GA-02 | — |
| ga_r3 | 1 | 1 | WSI-GA-04 | — |
| ga_r4 | 7 | 0 | — | the seven `ga_r4_ord_*` |
| w, five readers | 39 | 39 | WSI-GT-07, GP-02, GP-05, UI-11, CP-04, GA-07 | — |
| **Total** | **120** | **86** | | **34** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| 21 `*_r4_ord_*` | **Bug path** (BUG-1401). Each fails the strict SQL card (GP-07, UI-09, GA-06) on Then 3, 4 or 6. The `token_tail` variants pass GP-06, UI-08 and GA-05: tokens `tok-A` … `tok-D` sort like the ids. That is the same blind spot the executor found in waitlist LS-15, and the strict card covers it here too. |
| `ui_r2_no_trim_arg`, `ui_r2_exact` | **Bug path** (BUG-1402): fail UI-02 to UI-04 on Then 2. |

## xfail tests against the reference
With `--runxfail` on the reference: 37 passed. **The alarm works:** with the markers on, `6 failed, 28 passed, 3 xpassed`, the six strict cards `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| WSI-GP-06, UI-08, GA-05 | non-strict | Then 2, as the cards say |
| WSI-GP-07, UI-09, GA-06 | strict | Then 2, as the cards say |
| WSI-UI-02, UI-03, UI-04 | strict | Then 2, as the cards say |

## Reproduced claims
- **Result line of the notes holds:** `28 passed, 9 xfailed` in 3 of 3 default runs, the coverage run among them. No flaky test.
- `--runxfail`: `9 failed, 28 passed`, exactly the nine bug cards.
- **Mocks:** only `app.dao.workspace_invitation.utcnow`, the spec's one external, around every When. No `try`, no broad `pytest.raises`.

## Traceability
cases 37 · tests 37 · unmatched: none · duplicates: none · marker mismatches: none. BUG-1401 and BUG-1402 are in `bugs.md`. Card order equals file order. Docstrings and `# Then N` numbers match. `ruff check` passes. `rebuild.py`: 269 cards over the seven files, 0 reports; selftest 1315 of 1328.

## Limits of this round
- **The reference and the variants are mine.** Variants ran on the default plan only.
- **Runs were not isolated.** Other agents may have been live.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/workspace_invitation.py tests/unit/dao/test_workspace_invitation.py --timeout 300 --json <scratch>/res/mut_workspace_invitation.json
  Mutants: 19 · killed 19 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_workspace_invitation.py -q -p no:cacheprovider --cov=app.dao.workspace_invitation --cov-branch --cov-report=term-missing
  28 passed, 9 xfailed · app\dao\workspace_invitation.py 17 0 0 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_workspace_invitation.py -q -p no:cacheprovider --runxfail -rf
  9 failed, 28 passed
pytest, default, 2 more runs                                   28 passed, 9 xfailed (each)
drive.py bases; drive.py muts; drive.py vars; propdrive.py      as above
rebuild.py; rebuild.py --selftest 8                             269 cards, 0 reports; 1315 of 1328
.venv/Scripts/python.exe -m ruff check <the seven test files>  All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add recipes R-1 to R-4; the Givens and Thens are written out above.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 33 passed · 10 xfail, 7 strict, 3 non-strict (reproduced ✅) · coverage 100% branch (17 statements, 0 branches)
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 43 unfaithful** (the 6 new read by eye against their cards; all 43 rebuilt by script)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. I edited no test and made no commit.

### New tests
Each was read against its card and matches its recipe. "Fails" means the round 1 gap variant fails that card on my reference with `--runxfail`, on all three plans (default; sequential scans off; index, bitmap and index-only scans off), with every run reaching all 43 tests.

| Card | Recipe | Fails |
|---|---|---|
| WSI-UI-12 | R-1 | the five `ui_r1_status_*` |
| WSI-CP-05 | R-2 | `cp_r1_status_trim_col`, `cp_r1_status_ltrim_col` |
| WSI-GP-09 | R-3 | `gp_r3_ws_le` |
| WSI-CP-06 | R-3 | `cp_r3_ws_le` |
| WSI-GA-08 | R-3 | `ga_r1_ws_le` |
| WSI-UI-13 | R-4 (xfail BUG-1402, strict) | `ui_r2_no_trim_col` (on the reference) |

UI-13 is `xfail(strict=True)` with a reason naming BUG-1402. Today it fails on Then 2 (`[] == [id]`), as its Fails line says. On the reference it passes, so it joins the alarm: with the markers on, the reference gives 7 `XPASS(strict)`.

### Reproduced
- **Result line of the notes holds:** `33 passed, 10 xfailed` in 3 of 3 default runs, the coverage run among them. No flaky test.
- **`--runxfail`:** exactly the bug cards fail, each on its Fails line.
- **Reference:** 43 passed with `--runxfail` on all three plans. **Alarm:** with the markers on, `7 failed, 33 passed, 3 xpassed`, the strict cards `XPASS(strict)`.
- **Traceability:** cases 43 · tests 43 · unmatched: none · marker mismatches: none. `rebuild.py` over the seven files: 297 cards, 0 reports. `ruff check` passes.
- **Limit:** I kept no copy of the round 1 test file, so "existing tests unchanged" rests on the rebuild of all 43 against their cards, not on a line diff.

### Commands run
```
rebuild.py                                                    297 cards, 0 reports
r2check.py   (gap variants x 3 plans, reference base runs)    every gap variant fails its new card(s); problems: none
repro.sh     (coverage run, --runxfail -rf, 2 more runs)      as under Reproduced
drive.py bases <module>                                       as under Reproduced
.venv/Scripts/python.exe -m ruff check <the six test files>   All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\`. Only this report was edited in the repo. Nothing was stopped or killed.
