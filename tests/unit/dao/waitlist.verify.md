# Verification — `app/dao/waitlist.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 52 cases). See "Round 2" at the end. The rest of this block is round 1.
>

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 40 passed · 5 xfail, 4 strict, 1 non-strict (reproduced ✅) · coverage 100% branch (30 statements, 6 branches)
> Mutation: 16 mutants · 16 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 45 unfaithful** (45 / 45 right)
> Hand variants: 103 · 76 caught by a pass card · 27 others: 3 rule gaps in Findings (9 variants), 8 bug path, 10 not listed
> Source commit: e48a092 · Cases revision: none; spec APPROVED · Conventions path corrected (see below)

## Summary
- **The tests can be trusted as written.** My script rebuilt all 45 with no difference. I read by eye the `mk_101` loop, the `N0` cards, US-01's "unchanged except status" (a dict compare without `status`) and the raw `SELECT` lines of US-04.
- **Why NEEDS WORK:** 3 rule gaps, for the case designer. The status filter's exact compare has only capitals and a prefix. The search is trimmed on the left side only in the cards. No card stores an email in capitals.
- **Cosmetic, done by me:** the Conventions line of `waitlist.cases.md` named `app.models.waitlist.WaitlistSignup`. I corrected it to `app.models.waitlist_signup.WaitlistSignup`, as the executor's notes asked (spec gap 1). Nothing else in the cases file changed. The test already imported the real path.

Written by Claude (all 45 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 45. No `waitlist.local-run.json`, so no `## Local-coder patterns` section.

## The executor's note on LS-15
**The note is right, and it is not a rule gap.** LS-15's rows A, B, C have emails `a.`, `b.`, `c.`, which sort the same way as their ids. So a wrong tie-break `email DESC` gives the intended `[C, B, A]`. My variant `ls_r5_email_tail` passes LS-15, as the note says. That is the 1b sort-key shape ("make id, user, stamp and text values not rise together") missed on a non-strict card. But LS-16 (strict) fails the same variant on Then 4 (`".id" in order_part`), and it fails every other wrong tie-break I tried (`id ASC`, `email ASC`, `first_name DESC`, none). When BUG-1411 is fixed, both cards lose their markers and LS-16 keeps catching it. The weakness is real but covered. When the card is next revised, give A, B, C emails that sort against their ids (e.g. `c.` for A, `a.` for C), as the note proposes. Not required for this verdict. The same blind spot sits in `workspace_invitation` GP-06 / UI-08 / GA-05 (tokens `tok-A` … `tok-D`), covered there by the strict SQL cards in the same way.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `list_signups` R4 ("status keeps rows whose status is exactly that text") | LS-12 (capitals) and LS-13 (a prefix) only. No leading space on either side, no `_`, no suffix, no `""`. 1b, "exact compare". | `ls_r4_txt_like`, `_endswith`, `_strip_arg`, `_lstrip_arg`, `_trim_col`, `_ltrim_col`, `ls_r4_truthy` pass all 45. | **case designer** |
| 2 | case-missing | `list_signups` R2 ("the trimmed search text") | LS-02 has a leading space only. | `ls_r2_lstrip` passes all 45. | **case designer** |
| 3 | case-missing | `get_by_email` R1 ("exact match") | Capitals are tested on the argument side only (GE-02). CS-04 shows a capitalised email can be stored. 1b, "exact compare, both sides". | `ge_r1_txt_lower_col` passes all 45. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\prop\test_p_waitlist.py`, not in the repo. Each passes on today's code and on my reference; each named variant fails it.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | five new cards, LS R4, one shape each | B = signup, `email f"amy.{TAG}@x.com"`, but `status "contacted"` (fifth card: `status " contacted"`). When `dao.list_signups(db, search=TAG, status=…)` with `" contacted"` / `"contacte_"` / `"tacted"` / `""` / (fifth card) `"contacted"` | `result == ([], 0)` | pass | `" contacted"`: `ls_r4_txt_strip_arg`, `_lstrip_arg`; `"contacte_"`: `ls_r4_txt_like`; `"tacted"`: `ls_r4_txt_endswith`; `""`: `ls_r4_truthy`; stored `" contacted"`: `ls_r4_txt_trim_col`, `_ltrim_col`, `_endswith` |
| R-2 | new card, LS R2 | A = signup, `email f"zed.{TAG}.mid@x.com"`; B = signup, `email f"zed.{TAG}@x.com"`. When `dao.list_signups(db, search=f"{TAG}.mid ")` (a trailing space) | `ids(result[0]) == [A.id]`; `result[1] == 1` | pass | `ls_r2_lstrip` |
| R-3 | new card, GE R1 | A = signup, `email f"Zed.{TAG}@x.com"`. When `dao.get_by_email(db, email=f"zed.{TAG}@x.com")` | `result is None` | pass | `ge_r1_txt_lower_col` |

## Surviving mutants
None. All 16 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 16 mutants with all tests, markers on, no `-x`: every run reached all 45 tests, with no collection or setup error.

## Hand variants
On my reference (`plug\ref\waitlist.py`: `%`, `_`, `\` escaped with `escape="\\"`; `ORDER BY created_at DESC, id DESC`) with `--runxfail`, default plan. Every edit applied once; every run reached all 45 tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| ge_r1 | 13 | 12 | WLS-GE-01 … GE-06 | `ge_r1_txt_lower_col` |
| ls_r2 | 10 | 5 | WLS-LS-02, LS-03, LS-09 … | `ls_r2_lstrip`, `ls_r2_no_lower`, three `ls_r2_no_escape_*` |
| ls_r2a | 3 | 1 | WLS-LS-07 | `ls_r2a_is_not_none`, `ls_r2a_blank_none` |
| ls_r3 | 2 | 2 | WLS-LS-10, LS-11, LS-23, LS-24 | — |
| ls_r4 | 14 | 7 | WLS-LS-12, LS-13, LS-23 | seven (Finding 1) |
| ls_r5 | 7 | 2 | WLS-LS-14, LS-19, LS-24 | five tie-break variants |
| ls_r6, ls_r7 | 8 | 8 | WLS-LS-02 … LS-24 | — |
| cs_r1, cs_r4, cs_r5 | 15 | 15 | WLS-CS-01 … CS-08 | — |
| cs_r2 | 1 | 0 | — | `cs_r2_none` |
| us_r1 | 6 | 4 | WLS-US-01 … US-05 | `us_r1_touch`, `us_r1_copy` |
| w, two readers | 16 | 16 | WLS-GE-07, LS-19, LS-25 | — |
| w, two writers | 8 | 4 | the commit spies | four `expire_all` / `expunge_all` |
| **Total** | **103** | **76** | | **27** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| three `ls_r2_no_escape_*`, five `ls_r5_*` | **Bug path** (BUG-1410, BUG-1411): fail LS-04/05/06 on Then 2, LS-16 on Then 4 or 6, and all but `email_tail` fail LS-15 on Then 2 (see the note above). |
| `ls_r2_no_lower` | **Equivalent:** `ILIKE` ignores case. |
| `ls_r2a_is_not_none`, `ls_r2a_blank_none` | **Equivalent:** `""` then gives `ILIKE '%%'`, which every non-null email matches (`email` is NOT NULL), the same as no filter. |
| `cs_r2_none` | **Equivalent:** `bool(None)` is `False`, the default R2 names. |
| `us_r1_copy` | **Equivalent:** `db.get` returns the same identity-map object, so `result is S` holds. |
| `us_r1_touch` | Sets `source` only when it is `NULL`. No card's signup has a NULL source, and the variant is contrived. |
| four writer `expire_all` / `expunge_all` | Session housekeeping after a write; no rule names it. |

## xfail tests against the reference
With `--runxfail` on the reference: 45 passed. **The alarm works:** with the markers on, `4 failed, 40 passed, 1 xpassed`, the strict cards `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| WLS-LS-04, LS-05, LS-06 | strict | Then 2, as the cards say |
| WLS-LS-15 | non-strict | Then 2, as the card says |
| WLS-LS-16 | strict | Then 4, as the card says |

## Reproduced claims
- **Result line of the notes holds:** `40 passed, 5 xfailed` in 3 of 3 default runs, the coverage run among them. No flaky test.
- `--runxfail`: `5 failed, 40 passed`.
- **Mocks:** only the commit spies of CS-08 and US-04 (`wraps=db.commit`). No `try`, no broad `pytest.raises`.

## Traceability
cases 45 · tests 45 · unmatched: none · duplicates: none · marker mismatches: none. BUG-1410 and BUG-1411 are in `bugs.md`. `ruff check` passes. `rebuild.py`: 269 cards, 0 reports; selftest 1315 of 1328.

## Limits of this round
- **The reference and the variants are mine.** Variants ran on the default plan only.
- The table is shared and not scoped. Every proof card searches its own `TAG`, as the module's cards do.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/waitlist.py tests/unit/dao/test_waitlist.py --timeout 300 --json <scratch>/res/mut_waitlist.json
  Mutants: 16 · killed 16 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_waitlist.py -q -p no:cacheprovider --cov=app.dao.waitlist --cov-branch --cov-report=term-missing
  40 passed, 5 xfailed · app\dao\waitlist.py 30 0 6 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_waitlist.py -q -p no:cacheprovider --runxfail -rf
  5 failed, 40 passed
pytest, default, 2 more runs                                   40 passed, 5 xfailed (each)
drive.py bases; drive.py muts; drive.py vars; propdrive.py      as above
rebuild.py; rebuild.py --selftest 8                             269 cards, 0 reports; 1315 of 1328
.venv/Scripts/python.exe -m ruff check <the seven test files>  All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\`. In the repo: this report, and the one-line Conventions path correction in `waitlist.cases.md`. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add recipes R-1 to R-3. Optionally, at the same revision, give LS-15's rows emails that sort against their ids.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 47 passed · 5 xfail, 4 strict, 1 non-strict (reproduced ✅) · coverage 100% branch (30 statements, 6 branches)
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 52 unfaithful** (the 7 new read by eye against their cards; all 52 rebuilt by script)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. I edited no test and made no commit.

### New tests
Each was read against its card and matches its recipe. "Fails" means the round 1 gap variant fails that card on my reference with `--runxfail`, on all three plans (default; sequential scans off; index, bitmap and index-only scans off), with every run reaching all 52 tests.

| Card | Recipe | Fails |
|---|---|---|
| WLS-LS-26 | R-1 | `ls_r4_txt_strip_arg`, `ls_r4_txt_lstrip_arg` |
| WLS-LS-27 | R-1 | `ls_r4_txt_like` |
| WLS-LS-28 | R-1 | `ls_r4_txt_endswith` |
| WLS-LS-29 | R-1 | `ls_r4_truthy` |
| WLS-LS-30 | R-1 | `ls_r4_txt_trim_col`, `ls_r4_txt_ltrim_col`, `ls_r4_txt_endswith` |
| WLS-LS-31 | R-2 | `ls_r2_lstrip` |
| WLS-GE-08 | R-3 | `ge_r1_txt_lower_col` |

Each new card searches the test's own `TAG`, so the shared table cannot leak rows into it. LS-15 was not revised (optional in round 1); LS-16 still covers its blind spot.

### Reproduced
- **Result line of the notes holds:** `47 passed, 5 xfailed` in 3 of 3 default runs, the coverage run among them. No flaky test.
- **`--runxfail`:** exactly the bug cards fail, each on its Fails line.
- **Reference:** 52 passed with `--runxfail` on all three plans. **Alarm:** with the markers on, `4 failed, 47 passed, 1 xpassed`, the strict cards `XPASS(strict)`.
- **Traceability:** cases 52 · tests 52 · unmatched: none · marker mismatches: none. `rebuild.py` over the seven files: 297 cards, 0 reports. `ruff check` passes.
- **Limit:** I kept no copy of the round 1 test file, so "existing tests unchanged" rests on the rebuild of all 52 against their cards, not on a line diff.

### Commands run
```
rebuild.py                                                    297 cards, 0 reports
r2check.py   (gap variants x 3 plans, reference base runs)    every gap variant fails its new card(s); problems: none
repro.sh     (coverage run, --runxfail -rf, 2 more runs)      as under Reproduced
drive.py bases <module>                                       as under Reproduced
.venv/Scripts/python.exe -m ruff check <the six test files>   All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\`. Only this report was edited in the repo. Nothing was stopped or killed.
