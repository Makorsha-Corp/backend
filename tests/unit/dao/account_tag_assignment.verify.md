# Verification — `app/dao/account_tag_assignment.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 2, 36 cases). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 29 passed · 3 xfail, 2 strict, 1 non-strict (reproduced ✅) · coverage 100% branch (36 statements, 6 branches)
> Mutation: 21 mutants · 21 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 32 unfaithful** (32 / 32 right)
> Hand variants: 46 · 38 caught by a pass card · 8 others: 2 rule gaps in Findings, the rest bug path
> Source commit: e48a092 · Cases revision: none (reference change only); spec APPROVED

## Summary
- **The tests can be trusted as written.** Every test was read against its card, and my script agrees: 32 of 32 match.
- **Why NEEDS WORK:** all 21 mutants are killed, but two queries filter on ids that are tested only against a higher other row: `get_assignment` (and through it `assignment_exists`, `delete_assignment`) and `remove_all_tags_from_account`. Two recipes, for the case designer.
- **Counters:** `remove_all_tags_from_account` lowers tag counters through the account tag DAO; every counter rule here is caught by a pass card.

Written by Claude (all 32 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 32. No `account_tag_assignment.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_assignment` R2 "the same pair under another workspace, another tag or another account → `None`" | ATA-GA-02, AE-02, DA-02 record the link in W2 and ask W1; ATA-GA-03 links A2 and asks A1. The other row always has the higher id, so `<=` on the workspace or on the account passes. One card per shared query is enough: `assignment_exists` and `delete_assignment` call it. | `ga_r2_ws_le`, `ga_r2_acc_le` pass all 32 on all three plans. | **case designer** |
| 2 | case-missing | `remove_all_tags_from_account` R1 "links of other accounts and links recorded under another workspace stay" | ATA-RA-02 and RA-03 keep only links with a higher workspace or account id. `<=` on either passes. | `ra_r1_ws_le`, `ra_r1_acc_le` pass all 32 on all three plans. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctv\prop\test_prop_tags.py`, not in the repo. Each passes on today's code and on my reference. Each named variant fails its recipe, on all three plans.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| S-1 | two new cards, GA R2 | T1 = tag, `name "Supplier"`, `tag_code "supplier"`; L1 = link, tag T1. When (a) `get_assignment(db, account_id=A1.id, tag_id=T1.id, workspace_id=W2.id)`; (b) `get_assignment(db, account_id=A2.id, tag_id=T1.id, workspace_id=W1.id)` | `result is None` | pass | (a) `ga_r2_ws_le`; (b) `ga_r2_acc_le` |
| S-2 | two new cards, RA R1 | T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 2`; L1 = link, tag T1. When (a) `remove_all_tags_from_account(db, account_id=A1.id, workspace_id=W2.id)`; (b) `remove_all_tags_from_account(db, account_id=A2.id, workspace_id=W1.id)` | 1. `result == 0`; 2. count: `links(A1, W1) == 1`; 3. `stored_count(T1) == 2` | pass | (a) `ra_r1_ws_le`; (b) `ra_r1_acc_le` |

## Surviving mutants
None. All 21 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 21 mutants with no `-x`: every run reached all 29 pass tests, with no collection or setup error, and each status matched `mutate.py`.

## Hand variants
`variants.py`, on my reference with `--runxfail`, on three plans (default; sequential scans off; index and bitmap scans off): the same variants caught by the same pass cards. Every edit was asserted to apply once, and every run reached all 32 tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| gd_r2 | 2 | 2 | ATA-GD-01, ATA-GD-02 | — |
| tfa_r1 | 5 | 5 | ATA-TFA-01, ATA-TFA-02, ATA-TFA-03, ATA-TFA-04 | — |
| tfa_r2 | 4 | 4 | ATA-TFA-01, 02, 03, 05, 09 | — |
| tfa_r3 | 1 | 0 | — | `tfa_r3_active_drop` |
| tfa_r4 | 3 | 0 | — | `tfa_r4_system_first`, `tfa_r4_no_tail`, `tfa_r4_name_cs` |
| tfa_r5 | 1 | 1 | ATA-TFA-09 | — |
| tfa_w | 2 | 2 | ATA-TFA-09 | — |
| ga_r2 | 7 | 5 | ATA-GA-01, GA-02, GA-03, AE-02, DA-01, DA-02 | `ga_r2_ws_le`, `ga_r2_acc_le` |
| ga_r3 | 2 | 2 | ATA-GA-04, AE-03, DA-04 | — |
| ae_r1 | 2 | 2 | ATA-AE-01, AE-02, AE-03 | — |
| da_r1 … da_w | 5 | 5 | ATA-DA-01 … DA-05 | — |
| ra_r1 | 4 | 2 | ATA-RA-02, ATA-RA-03 | `ra_r1_ws_le`, `ra_r1_acc_le` |
| ra_r2 … ra_r6 | 8 | 8 | ATA-RA-01, RA-03, RA-04, RA-05 | — |
| **Total** | **46** | **38** |  | **8** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `tfa_r3_active_drop`, `tfa_r4_*` (3) | **Bug path.** Today's behaviour of BUG-865 and BUG-1486; each fails ATA-TFA-06 / TFA-08 (strict) or TFA-07 (non-strict) on the reference. TFA-07 has a tie ("Alpha", "alpha"), so the tie-break direction is pinned too. |

## xfail tests against the reference
Reference: `get_tags_for_account` with active tags only and `ORDER BY lower(name), id` (and the account tag DAO's own reference counters). Nothing is written to `app/`.

With `--runxfail` on the reference: 32 passed, on all three plans. **The alarm works:** with the markers on, `2 failed, 29 passed, 1 xpassed`, TFA-06 and TFA-08 `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| ATA-TFA-06, TFA-08 | strict | Then 2, in all 3 plans, as the cards say |
| ATA-TFA-07 | non-strict | Then 2, in all 3 plans |

## Reproduced claims
- **Result line of the notes holds:** `29 passed, 3 xfailed` in 4 of 4 default runs, the coverage run among them. No flaky test.
- `--runxfail` on today's code: `3 failed, 29 passed` on all three plans.
- Coverage: 100% branch.
- **Mocks:** `monkeypatch.setattr(mod, "account_tag_dao", …)` in the GD cards (declared in Conventions) and the `db.commit` spy of DA-05 / RA-05 only. No `try`, no broad `pytest.raises`.

## Traceability
cases 32 · tests 32 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID (865, 1486) is in `docs/testing/bugs.md`. All sit under `# [claude] <ID>`. `ruff check` passes. `rebuild.py`: 0 reports here; selftest 1141 of 1141.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/account_tag_assignment.py tests/unit/dao/test_account_tag_assignment.py --timeout 300 --json <scratch>/res/mut_account_tag_assignment.json
  21 mutants · 21 killed · 0 survived
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_account_tag_assignment.py -q -p no:cacheprovider --cov=app.dao.account_tag_assignment --cov-branch --cov-report=term-missing
  29 passed, 3 xfailed · TOTAL 36 0 6 0 100%
pytest (same file), 3 more default runs                       29 passed, 3 xfailed each
drive.py bases / muts / vars (3 plans); rx.py; propdrive.py; rebuild.py
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctv\`. Private `COVERAGE_FILE`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add S-1 and S-2; the Givens and Thens are written out above.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 2, narrow)

> **Verdict:** PASS
> Tests: 33 passed · 3 xfail, 2 strict, 1 non-strict (reproduced ✅) · coverage 100% branch
> Mutation: not re-run; round 1 stands at 21 / 21 → 100% (21 mutants)
> Fidelity: **0 of 36 unfaithful** (the 4 new tests read by eye; all 36 rebuilt by script)
> Source commit: e48a092 · Cases revision: 2; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test edited in this round.

### New tests
"Fails" means the variant fails that card, on my reference with `--runxfail`, on all three plans; every run reached all 36 tests.

| Card | Recipe | Fails |
|---|---|---|
| ATA-GA-05 | S-1 (a) | `ga_r2_ws_le` |
| ATA-GA-06 | S-1 (b) | `ga_r2_acc_le` |
| ATA-RA-06 | S-2 (a) | `ra_r1_ws_le` |
| ATA-RA-07 | S-2 (b) | `ra_r1_acc_le` |

### Reproduced
- **Result line of the notes holds:** `33 passed, 3 xfailed` in 3 of 3 default runs, the coverage run among them.
- **`--runxfail`:** `3 failed, 33 passed` on all three plans; every xfail fails on the Then its card names.
- **Reference:** 36 passed with `--runxfail`, on all three plans. **Alarm:** with the markers on, `2 failed, 33 passed, 1 xpassed`, TFA-06 and TFA-08 `XPASS(strict)`.
- **Traceability:** cases 36 · tests 36 · unmatched: none · marker mismatches: none. `rebuild.py`: 0 reports here. `ruff check` passes.

### Commands run
```
rebuild.py; rebuild.py --selftest 30                           221 cards, 0 reports here
var:account_tag_assignment:<gap variant> --runxfail × 3 plans  each named variant fails its new card
drive.py bases account_tag_assignment; rx.py
pytest tests/unit/dao/test_account_tag_assignment.py --cov=app.dao.account_tag_assignment --cov-branch, then 2 more runs
```
No full mutation run (narrow round). Only this report was edited in the repo. No commit. Nothing was killed.
