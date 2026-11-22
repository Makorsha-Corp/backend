# Verification — `app/dao/status.py`

> **Verdict:** PASS
> Tests: 10 passed · 2 xfail, both strict (reproduced ✅) · coverage 100% branch (5 statements, 0 branches)
> Mutation: 0 mutants · the class is empty, so `mutate.py` has no site. No score: the hand variants carry this module
> Fidelity: **0 of 12 unfaithful** (12 / 12 right)
> Hand variants: 16 · 15 caught by a pass card · 1 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted.** All 12 tests match their cards. `DAOStatus` has an empty body, so the tests pin what the base does on this table.
- `mutate.py` has nothing to mutate here. 15 of 16 hand variants, written as overrides in the class, fail a pass card. The other one is under Considered.
- **O2 stays boxed.** No card, test, finding or recipe rests on it. No test reads a default status id: RM-03 and RM-04 name their own row.

Written by Claude (all 12 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 12. No `status.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
None.

## Surviving mutants
None: no site.

## Hand variants
`plug\variants.py`, on the reference with `--runxfail`, default plan. Every edit was asserted to apply once and every run reached all 12 tests. Group names: the rule, `w` writes and session, `s` side effects, `txt` the text compare, `kw` keyword-only.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| r1 | 2 | 2 | STS-CR-01 | — |
| r2 | 5 | 5 | STS-CR-02, STS-CR-03, STS-CR-04, STS-CR-05, STS-CR-06 | — |
| r3 | 5 | 5 | STS-RM-01, STS-RM-02, STS-RM-03 | — |
| r4 | 4 | 3 | STS-RM-03 | `r4_detach_soft` |
| **Total** | **16** | **15** |  | **1** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `r4_detach_soft` | Moves the order to another status, then deletes. It has no effect on RM-03, which holds one status. **Not listed on purpose:** the only shape picks a replacement status, which is O2's ground, and O2 is boxed. For the owner when O2 is opened. |

## xfail tests against the reference
Reference: a unique index on `(workspace_id, lower(btrim(name)))`, created in each test's own transaction and rolled back with it. Nothing is written to `app/`.

With `--runxfail` on the reference: 12 passed. **The alarm works:** with the markers on, `2 failed, 10 passed`, the strict cards `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| STS-CR-07, STS-CR-08 | strict | Then 1, `DID NOT RAISE`, as the cards say |

## Reproduced claims
- **Result line of the notes holds:** `10 passed, 2 xfailed` in 5 of 5 default runs, the coverage run among them. No flaky test.
- `--runxfail`, on 3 plans: `2 failed, 10 passed`.
- **Mocks:** none. No `try`, no broad `pytest.raises`, no `if` in a test body.

## Traceability
cases 12 · tests 12 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script rebuilt each test's Given, snapshots, When, Then and marker from its card and compared by AST, for all 221 cards of the batch, with the helpers against the Conventions. It gave 2 reports, both the wait of WSP-IN-04 (see `workspace.verify.md`). Selftest: 1283 of 1283 planted mistakes of 60 kinds, in tests, helpers and cards.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live. Each kill is a plain `N failed`.
- **Reference DDL** ran inside each test's own rolled-back transaction, in three short runs per module that needs it, on the shared test database. Nothing persisted. Hand variants ran without it, and the bug cards it serves are left out of their counts.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/status.py tests/unit/dao/test_status.py --timeout 300 --json <scratch>/res/mut_status.json   (through runmut.py)
  0 mutants · the class is empty, so `mutate.py` has no site. No score: the hand variants carry this module
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_status.py -q -p no:cacheprovider --cov=app.dao.status --cov-branch --cov-report=term-missing --tb=no
  10 passed, 2 xfailed
pytest, default, 4 more runs; pytest --runxfail --tb=short, 3 plans        repro.py
drive.py bases; drive.py muts; drive.py vars                               as above
propdrive.py                                                               0 problems
rebuild.py; rebuild.py --selftest 6                                        221 cards, 2 reports; 1283 of 1283
.venv/Scripts/python.exe -m ruff check <the nine test files>               All checks passed!
git diff --stat -- app/dao                                                 (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refv\`. Only this report was written in the repo. No commit. Nothing was killed.
