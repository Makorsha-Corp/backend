# Verification — `app/dao/access_control.py`

> **Verdict:** PASS
> Tests: 31 passed · 4 xfail, 2 strict, 2 non-strict (reproduced ✅) · coverage 100% branch (11 statements, 0 branches)
> Mutation: 10 mutants · 10 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 35 unfaithful** (35 / 35 right)
> Hand variants: 50 · 43 caught by a pass card · 7 others: 4 bug path, 3 equivalent, no rule gap
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted.** My script rebuilt every test from its card and found no difference; each line it could not match mechanically (the 101-row Givens, `idset(e)` lines) I read by eye.
- Every mutant is killed, and every hand variant is caught by a pass card, except the order variants (caught by the BUG-1408 cards) and three that cannot change behaviour.
- The 1b shapes are all present: filter before paging (GT-06, X sorts first), `limit=1000` on both lists, the default cap, one shape per refusal.

Written by Claude (all 35 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 35. No `access_control.local-run.json`, so no `## Local-coder patterns` section.

## Findings
None.

## Surviving mutants
None. All 10 kills end in a plain `N failed`.

**Guard.** My own driver re-ran each of the 10 mutants with all tests, markers on, no `-x`: every run reached all 35 tests, with no collection or setup error, and the same 10 are killed by a pass card.

## Hand variants
`wsv\plug\variants.py`, on my reference (`plug\ref\access_control.py`: `ORDER BY id` on both lists) with `--runxfail`, default plan. Every edit was asserted to apply exactly once; every run reached all 35 tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| gr_r1 | 5 | 4 | ACL-GR-01 … GR-06 | `gr_r1_distinct` |
| gr_r3 | 1 | 1 | ACL-GR-01 | — |
| gr_r5 | 8 | 8 | ACL-GR-01 … GR-04, GR-06, GR-09 … | — |
| gr_r4 | 2 | 0 | — | `gr_r4_desc`, `gr_r4_target` |
| gr_r2 | 1 | 0 | — | `gr_r2_upper` |
| gr_kw | 1 | 1 | ACL-GR-18 | — |
| gt_r1 | 5 | 4 | ACL-GT-01 … GT-06 | `gt_r1_distinct` |
| gt_r3 | 1 | 1 | ACL-GT-01 | — |
| gt_r5 | 7 | 7 | ACL-GT-01, GT-02, GT-03, GT-05, GT-06, GT-07 … | — |
| gt_r4 | 2 | 0 | — | `gt_r4_desc`, `gt_r4_target` |
| gt_kw | 1 | 1 | ACL-GT-15 | — |
| get_by_role w (side effects) | 8 | 8 | ACL-GR-19 | — |
| get_by_type w (side effects) | 8 | 8 | ACL-GT-16 | — |
| **Total** | **50** | **43** | | **7** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `gr_r4_*`, `gt_r4_*` (4) | **Bug path** (BUG-1408). Each fails GR-07/GT-08 on Then 2 and GR-08/GT-09 on Then 4 or 5. |
| `gr_r1_distinct`, `gt_r1_distinct` | **Equivalent:** `DISTINCT ON (…, id)` — `id` is unique, so no row is dropped. |
| `gr_r2_upper` | **Equivalent:** upper-casing a string role maps the value `"owner"` to the name `"OWNER"`, and R2 says both match the same rows. |

## xfail tests against the reference
With `--runxfail` on the reference: 35 passed. **The alarm works:** with the markers on, `2 failed, 31 passed, 2 xpassed`, the strict cards `XPASS(strict)`.

| Cards | Marker | Fails today on |
|---|---|---|
| ACL-GR-07, ACL-GT-08 | non-strict | Then 2, as the card says |
| ACL-GR-08, ACL-GT-09 | strict | Then 2, as the card says |

## Reproduced claims
- **Result line of the notes holds:** `31 passed, 4 xfailed` in 3 of 3 default runs, the coverage run among them, plus 4 more inside my driver. No flaky test.
- `--runxfail`: `4 failed, 31 passed`, exactly the four bug cards, each on its Fails line.
- **Mocks:** none. No `try`, no broad `pytest.raises`.

## Traceability
cases 35 · tests 35 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. BUG-1408 is in `docs/testing/bugs.md`. `ruff check` passes.

My own script (`wsv\rebuild.py`) rebuilt each test's marker, docstring, Given builder calls and code steps (in order), When call and its wrappers, and every Then line inside its `# Then N` block, for all 269 cards of the batch: 0 reports. Selftest: 1315 of 1328 planted mistakes of 27 kinds, in tests and cards. The 13 it misses are all in two places I read by eye in every module: values on the 101/51-row loop Given lines, and column names passed as strings to count helpers.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- Variants ran on the default plan only. The bug-path order cards were run on today's code by the executor under five forced plans.
- **Runs were not isolated.** Other agents may have been live. Each kill is a plain `N failed`.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/access_control.py tests/unit/dao/test_access_control.py --timeout 300 --json <scratch>/res/mut_access_control.json
  Mutants: 10 · killed 10 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_access_control.py -q -p no:cacheprovider --cov=app.dao.access_control --cov-branch --cov-report=term-missing
  31 passed, 4 xfailed · app\dao\access_control.py 11 0 0 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_access_control.py -q -p no:cacheprovider --runxfail -rf
  4 failed, 31 passed
pytest, default, 2 more runs                                   31 passed, 4 xfailed (each)
drive.py bases; drive.py muts; drive.py vars                    as above
rebuild.py; rebuild.py --selftest 8                             269 cards, 0 reports; 1315 of 1328
.venv/Scripts/python.exe -m ruff check <the seven test files>  All checks passed!
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsv\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
None.
