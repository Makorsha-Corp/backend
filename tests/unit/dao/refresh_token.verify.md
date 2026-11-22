# Verification — `app/dao/refresh_token.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1, 51 cases). See "Round 2" at the end. The rest of this block is round 1.
>

> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 47 passed · 2 xfail, both strict (reproduced ✅) · coverage 97% branch (35 statements, 4 branches; line 33 missed: `get_by_id`, dead code per Q3)
> Mutation: 17 mutants · 15 killed · 2 survived → score 100% (after excluding 0 equivalent, 2 dead, 0 bug-path)
> Fidelity: **0 of 49 unfaithful** (49 / 49 right; read fully by eye and rebuilt by script)
> Hand variants: 93 · 71 caught by a pass card · 22 others: 2 rule gaps in Findings, 20 under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** I read all 49 tests by eye against their cards. That covered the hash and family fixtures, the standing-row chain, every "but" column and Given order, the `utcnow` patch around each When, the `raises` / `begin_nested` nesting, the commit spies and the "unchanged" snapshots taken after the last Given line. My script agrees.
- **Why NEEDS WORK:** 2 rule gaps for the case designer. The larger one is security: in RA-02 the other user is the later id, so a "revoke all" that also revoked earlier users' sessions would pass.

Written by Claude (all 49 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 49. No `refresh_token.local-run.json`, so no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `revoke_all_for_user` R2 ("rows of other users are untouched") | RA-02's other user X is U2, revoking U1: always the higher id. | `ra_r2_le` (`user_id <= user_id`) passes all 49. | **case designer** |
| 2 | case-missing | `touch_last_used` R1 ("nothing else on the row changes") | TL-01 starts from a revoked row; TL-02 checks only `last_used_at`. No card touches an unrevoked row and checks it stays unrevoked. | `tl_r1_stamp_revoke` (`revoked_at = revoked_at or now`) passes all 49. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\prop\test_p_refresh_token.py`, not in the repo. Every When runs under the `utcnow` patch. Each passes on today's code and on my reference; each named variant fails it.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | new card, RA R2 | X = token, `token_hash H5`; A = token, `token_hash H1`, but `user_id U2.id`. When `dao.revoke_all_for_user(db, user_id=U2.id)` | `result == 1`; re-read A: `revoked_at == NOW`; unchanged(X) | pass | `ra_r2_le` |
| R-2 | new card, TL R1 | A = token, `token_hash H1`, but `user_agent "Mozilla/5.0"` (not revoked). When `dao.touch_last_used(db, row=A)` | re-read A: `last_used_at == NOW`; unchanged(A) except `last_used_at` | pass | `tl_r1_stamp_revoke` |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 2 | 33 | `return` → `return None` | dead | `get_by_id`: the spec's Q3 says dead code, to be removed (`dead-code-removal-checklist.md`) | — |
| 15 | 33 | `==` → `!=` | dead | the same line | — |

**Guard.** My own driver re-ran each of the 17 mutants with all tests, markers on, no `-x`: every run reached all 49 tests, with no collection or setup error, and the same 15 are killed by a pass card.

## Hand variants
On my reference (`plug\ref\refresh_token.py`: `user_agent[:512]`, `ip_address[:64]`) with `--runxfail`, default plan. Every edit applied once; every run reached all 49 tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| gh_r2 (hash exact compare) | 13 | 12 | RT-GH-01, GH-02, GH-04 … GH-07 | `gh_r2_txt_lower_col` |
| cr_r1 | 10 | 10 | RT-CR-01 … CR-15 | — |
| cr_r2, cr_r4, cr_r5 | 4 | 4 | RT-CR-03, CR-10, CR-13 | — |
| rv_r1 … rv_r4 | 7 | 7 | RT-RV-01 … RV-06, RV-09 | — |
| rf_r1 | 3 | 2 | RT-RF-01, RF-05 | `rf_r1_values_none` |
| rf_r2 | 15 | 8 | RT-RF-01 … RF-04, RF-06, RF-07 | seven `rf_r2_txt_*` |
| rf_r4 | 1 | 0 | — | `rf_r4_fetch` |
| ra_r1 | 4 | 3 | RT-RA-01, RA-04 | `ra_r1_values_none` |
| ra_r2 | 3 | 2 | RT-RA-02, RA-03 | `ra_r2_le` |
| ra_r4 | 1 | 0 | — | `ra_r4_fetch` |
| tl_r1 | 4 | 3 | RT-TL-01, TL-02 | `tl_r1_stamp_revoke` |
| w, get_by_hash | 8 | 8 | RT-GH-08 | — |
| w, five writers | 20 | 12 | the commit spies, RF-08, RA-05 | eight `expire_all` / `expunge_all` |
| **Total** | **93** | **71** | | **22** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `gh_r2_txt_lower_col` | Hashes are always lower-case hex (SHA-256); R2 names the argument side only. A stored capital cannot occur. |
| seven `rf_r2_txt_*` (`like`, `endswith`, lower, trims) | The cases file limits the family compare to capitals and a part on purpose, because the family is a server-made UUID with no spaces, `_` or `%` (step 1a). I agree. |
| `rf_r4_fetch`, `ra_r4_fetch` | **Equivalent here:** with `synchronize_session='fetch'`, RF-08 and RA-05 still pass. In this SQLAlchemy version the option does not refresh the loaded copy for this statement, so R4 holds either way. |
| `rf_r1_values_none`, `ra_r1_values_none` | Also clearing `replaced_by_id` on rows that are not yet revoked. Such rows have no successor in practice (`revoke` sets both together), and no rule says the bulk update leaves other columns. |
| eight writer `expire_all` / `expunge_all` | Session housekeeping after a write; no rule of this DAO names it (the 1b "side effects none" shape is for readers). |

## xfail tests against the reference
With `--runxfail` on the reference: 49 passed. **The alarm works:** with the markers on, `2 failed, 47 passed`, both `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| RT-CR-11, RT-CR-12 | strict | the When call (`DataError` at the flush), before Then 1, as the cards say |

## Reproduced claims
- **Result line of the notes holds:** `47 passed, 2 xfailed` in 3 of 3 default runs, the coverage run among them. No flaky test.
- `--runxfail`: `2 failed, 47 passed`.
- **Mocks:** only `app.dao.refresh_token.utcnow` around every When, plus the commit spies (`wraps=db.commit`). No `try`, no broad `pytest.raises`.

## Traceability
cases 49 · tests 49 · unmatched: none · duplicates: none · marker mismatches: none. BUG-1407 is in `bugs.md`. Card order equals file order. `ruff check` passes. `rebuild.py`: 269 cards, 0 reports; selftest 1315 of 1328.

## Limits of this round
- **The reference and the variants are mine.** Variants ran on the default plan only.
- **Not exercised:** the HR-10 race of the auth service (FU-1 (a)); it needs two connections.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/refresh_token.py tests/unit/dao/test_refresh_token.py --timeout 300 --json <scratch>/res/mut_refresh_token.json
  Mutants: 17 · killed 15 · timeout 0 · survived 2 · score 88%   (both on line 33, dead)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_refresh_token.py -q -p no:cacheprovider --cov=app.dao.refresh_token --cov-branch --cov-report=term-missing
  47 passed, 2 xfailed · app\dao\refresh_token.py 35 1 4 0 97% 33
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_refresh_token.py -q -p no:cacheprovider --runxfail -rf
  2 failed, 47 passed
pytest, default, 2 more runs                                   47 passed, 2 xfailed (each)
drive.py bases; drive.py muts; drive.py vars; propdrive.py      as above
rebuild.py; rebuild.py --selftest 8                             269 cards, 0 reports; 1315 of 1328
.venv/Scripts/python.exe -m ruff check <the seven test files>  All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add recipes R-1 and R-2.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 49 passed · 2 xfail, both strict (reproduced ✅) · coverage 97% branch (35 statements, 4 branches; line 33 dead)
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 51 unfaithful** (the 2 new read by eye against their cards; all 51 rebuilt by script)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. I edited no test and made no commit.

### New tests
Each was read against its card and matches its recipe. "Fails" means the round 1 gap variant fails that card on my reference with `--runxfail`, on all three plans (default; sequential scans off; index, bitmap and index-only scans off), with every run reaching all 51 tests.

| Card | Recipe | Fails |
|---|---|---|
| RT-RA-07 | R-1 | `ra_r2_le` |
| RT-TL-03 | R-2 | `tl_r1_stamp_revoke` |

RA-07 snapshots X after the last Given row, before the patched When. TL-03 snapshots A except `last_used_at` the same way, and checks `revoked_at is None` on the re-read row.

### Reproduced
- **Result line of the notes holds:** `49 passed, 2 xfailed` in 3 of 3 default runs, the coverage run among them. No flaky test.
- **`--runxfail`:** exactly the bug cards fail, each on its Fails line.
- **Reference:** 51 passed with `--runxfail` on all three plans. **Alarm:** with the markers on, `2 failed, 49 passed`, the strict cards `XPASS(strict)`.
- **Traceability:** cases 51 · tests 51 · unmatched: none · marker mismatches: none. `rebuild.py` over the seven files: 297 cards, 0 reports. `ruff check` passes.
- **Limit:** I kept no copy of the round 1 test file, so "existing tests unchanged" rests on the rebuild of all 51 against their cards, not on a line diff.

### Commands run
```
rebuild.py                                                    297 cards, 0 reports
r2check.py   (gap variants x 3 plans, reference base runs)    every gap variant fails its new card(s); problems: none
repro.sh     (coverage run, --runxfail -rf, 2 more runs)      as under Reproduced
drive.py bases <module>                                       as under Reproduced
.venv/Scripts/python.exe -m ruff check <the six test files>   All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\`. Only this report was edited in the repo. Nothing was stopped or killed.
