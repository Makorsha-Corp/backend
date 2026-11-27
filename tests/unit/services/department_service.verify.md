# Verification — `app/services/department_service.py`

> **Verdict:** PASS
> Tests: 22 passed · 12 xfail, 8 strict + 4 non-strict (reproduced ✅) · coverage 100% branch (41 statements, 0 branches)
> Mutation: 10 mutants · 10 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 34 unfaithful** (34 / 34 right; read by eye and rebuilt by script)
> Hand variants: 47 · 41 caught by a pass card · 6 others: 3 equivalent, 3 bug-path (none is a rule gap)
> Source commit: e48a092 · Cases revision: 0; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 34 match their cards; I read every one by eye against its card, and my own script rebuilt them too.
- **The transaction contract is guarded on every write.** Dropping the commit, dropping the rollback, swallowing the error, wrapping it, dropping the re-read or re-reading before the commit each fails a pass card on `create_department`, `update_department` and `delete_department`. Each read is caught when it commits, rolls back or flushes (TC6).
- Every mutant is killed. The only variants no pass card sees are equivalent (a raw `db.commit()` instead of `_commit_transaction`) or bug paths (BUG-005, BUG-010).

Written by Claude (all 34 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 34. No `department_service.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
None.

## Surviving mutants
None. All 10 kills end in a plain `N failed`.

**Guard.** My own driver (`drive.py muts`) re-ran each of the 10 mutants without `-x`: every run reached all 22 pass tests, with no collection or setup error, and every outcome equals the outcome from `mutate.py`.

## Hand variants
`plug\vplug.py` runs the service from my reference source plus one edit; `variants.py` holds the edits. They ran on the reference with `--runxfail`, with the 8 cards the reference does not serve deselected (see below). Every edit was checked to apply exactly once, and every run reached all 26 served tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| tc1 (drop commit, flush instead) | 6 | 6 | DSV-C-01, DSV-C-04, DSV-C-05, DSV-U-01, DSV-D-01 | — |
| tc2 (drop refresh, refresh before commit) | 6 | 6 | DSV-C-01, DSV-C-05, DSV-U-01, DSV-D-01 | — |
| tc3 (drop rollback, commit on error, swallow, wrap) | 12 | 12 | DSV-C-02, DSV-C-03, DSV-U-02, DSV-U-03, DSV-D-02, DSV-D-03 … | — |
| tc4 (raw `db.commit()`) | 3 | 0 | — | 3 × `*_tc4_raw_commit` |
| tc5 (no re-read) | 3 | 3 | DSV-C-01, DSV-C-05, DSV-U-01, DSV-D-01 | — |
| tc6 (read commits, rolls back, flushes) | 6 | 6 | DSV-G-07, DSV-L-07 | — |
| r1 (`user_id` not passed on) | 3 | 3 | DSV-C-01, DSV-U-01, DSV-D-01 | — |
| r2 (`include_deleted`) | 4 | 1 | DSV-L-05 | `get_department_r2_ignore_flag`, `get_department_r2_always_hide`, `get_departments_r2_flag_dropped` |
| arg (`skip`, `limit`, `search`, default limit) | 4 | 4 | DSV-L-01 … DSV-L-04 | — |
| **Total** | **47** | **41** | | **6** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `create_/update_/delete_department_tc4_raw_commit` | **Equivalent.** A raw `db.commit()` that raises still lands in the method's own `except`, which rolls back and re-raises: the TC4 outcome is the same (DSV-C-04 counts rollbacks as "at least one", as the spec says). |
| `get_department_r2_ignore_flag`, `get_department_r2_always_hide` | **Bug-path** (BUG-005). Only DSV-G-04, DSV-G-05 see them, as designed. |
| `get_departments_r2_flag_dropped` | **Bug-path** (BUG-010). Only DSV-L-06 sees it. |

## xfail tests against the reference
Reference: today's service with `get_department(..., include_deleted=False)` refusing a deleted row with the manager's 404, and `get_departments(..., include_deleted=False)` passing the flag to the manager. Written from the spec only; nothing under `app/` touched. Manager bugs are not fixed in it, so their pass-through cards stay failing and are left out of the variant counts: DSV-C-06 … DSV-C-09, DSV-L-08 … DSV-L-10, DSV-U-05.

With `--runxfail` on the reference: 26 passed, 8 failed (exactly the unserved list). **The alarm works:** with the markers on, the 4 served strict cards XPASS(strict) and fail.

| Cards | Marker | Fails today on |
|---|---|---|
| DSV-C-06, DSV-C-08, DSV-C-09, DSV-G-04 | strict / non-strict as the card | Then 1, `DID NOT RAISE HTTPException` |
| DSV-C-07, DSV-U-05 | strict | Then 2 (`' Sales ' == 'Sales'`; `updated_by` is U1) |
| DSV-G-05, DSV-L-06 | strict | the When, `TypeError` (no `include_deleted`), as the card says |
| DSV-G-06 | strict | Then 1, `TypeError` inside the `raises` wrap |
| DSV-L-08, DSV-L-09 | non-strict | Then 1 (`[] == [...]`) |
| DSV-L-10 | non-strict | Then 2 (insertion order) |

## Reproduced claims
- **Result line of the notes holds:** `22 passed, 12 xfailed` in 4 of 4 default runs, the coverage run among them. No flaky test.
- `--runxfail -rf`: `12 failed, 22 passed`; each fails on the line its card names (table above, from my `failmap.py` plugin).
- **Mocks:** only the failing commit / refresh wraps and the DSV-C-09 race simulation, as Conventions say. No `try`, no `if`, no broad `pytest.raises` in a test body.

## Traceability
cases 34 · tests 34 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring holds its card's ID, title and Rules; `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All sit under `# [claude] <ID>`. `ruff check` passes.

My own script (`cmp.py`) parsed every card and test of the batch (315 cards) and compared ID, order, docstring, marker, Then numbering, each Then line's values and operators against the asserts of its segment, `db.rollback()` before `committed:` lines, raise types, patches allowed by Conventions, Given literals before the When and around the commit point, and the When call itself: 0 reports. Selftest: 2876 of 2880 planted mistakes of 23 kinds, in tests and cards, over 3 seeds. The 4 misses: 2 changed list indexes (`rows[0]` → `rows[1]`) in "that row" lines, 2 deleted membership lines inside NSV-A-03's loop. None in this file.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live on `marker_test`. Each kill is a plain `N failed`.
- **Not exercised:** HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/department_service.py tests/unit/services/test_department_service.py --timeout 300 --json <scratch>/res/mut_department.json   (through runmut.py)
  Mutants: 10 · killed 10 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_department_service.py -q -p no:cacheprovider --cov=app.services.department_service --cov-branch --cov-report=term-missing
  22 passed, 12 xfailed · app\services\department_service.py 41 0 0 0 100%
.venv/Scripts/python.exe -m pytest tests/unit/services/test_department_service.py -q -p no:cacheprovider --runxfail -rf
  12 failed, 22 passed
pytest, default, 2 more runs + 1 in drive.py bases                          22 passed, 12 xfailed each
drive.py bases; drive.py muts; drive.py vars; post.py                      as above
cmp.py; cmp.py --selftest 6 / 11 / 23                                      0 reports; 2876 of 2880
.venv/Scripts/python.exe -m ruff check tests/unit/services/                All checks passed!
git diff --stat -- app/services                                            (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v\` (private `COVERAGE_FILE`). Only this report was written in the repo. No commit. Nothing was killed.
