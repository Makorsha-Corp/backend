# Verification — `app/services/delivery_method_service.py`

> **Verdict:** PASS
> Tests: 24 passed · 4 xfail, all strict (reproduced ✅) · coverage 100% branch (41 statements, 0 branches)
> Mutation: 10 mutants · 10 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 28 unfaithful** (28 / 28 right; rebuilt by script, compared by eye with the department master)
> Hand variants: 47 · 41 caught by a pass card · 6 others: 3 equivalent, 3 bug-path (none is a rule gap)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 28 match their cards.
- **The transaction contract is guarded on every write:** dropped commit, dropped rollback, swallowed or wrapped error, dropped re-read, re-read before the commit — each fails a pass card on create, update and delete. Both reads are caught committing, rolling back or flushing (TC6).
- Every mutant is killed; the variants no pass card sees are equivalent or BUG-1522 / BUG-1523 paths.

Written by Claude (all 28 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 28. No `delivery_method_service.local-run.json`, so no `## Local-coder patterns` section.

## Findings
None.

## Surviving mutants
None. All 10 kills end in a plain `N failed`.

**Guard.** `drive.py muts` re-ran each mutant without `-x`: every run reached all 24 pass tests, no collection or setup error, outcome equal to `mutate.py`'s.

## Hand variants
On my reference through `plug\vplug.py`, `--runxfail`; the reference serves all 28 cards. Every edit applied once; every run reached all 28 tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| tc1 | 6 | 6 | DMS-C-01, DMS-C-03 … DMS-C-05, DMS-U-01, DMS-D-01 | — |
| tc2 | 6 | 6 | DMS-C-01, DMS-C-04, DMS-U-01, DMS-D-01 | — |
| tc3 | 12 | 12 | DMS-C-02, DMS-C-03, DMS-C-04, DMS-C-06, DMS-U-02, DMS-U-03, DMS-D-02, DMS-D-03 | — |
| tc4 | 3 | 0 | — | 3 × `*_tc4_raw_commit` |
| tc5 | 3 | 3 | DMS-C-01, DMS-C-04, DMS-U-01, DMS-D-01 | — |
| tc6 | 6 | 6 | DMS-G-07, DMS-L-07 | — |
| r1 | 3 | 3 | DMS-C-01, DMS-C-04, DMS-C-06, DMS-U-01, DMS-D-01 | — |
| r2 | 4 | 1 | DMS-L-05 | `get_delivery_method_r2_ignore_flag`, `…_r2_always_hide`, `get_delivery_methods_r2_flag_dropped` |
| arg | 4 | 4 | DMS-L-01 … DMS-L-04, DMS-L-08 | — |
| **Total** | **47** | **41** | | **6** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| 3 × `*_tc4_raw_commit` | **Equivalent:** the method's own `except` rolls back and re-raises a failing raw commit (TC4 outcome unchanged). |
| `get_delivery_method_r2_*` | **Bug-path** BUG-1523: only DMS-G-04, DMS-G-05. |
| `get_delivery_methods_r2_flag_dropped` | **Bug-path** BUG-1522: only DMS-L-06. |

## xfail tests against the reference
Reference: `get_delivery_method(..., include_deleted=False)` refuses a deleted method with the manager's 404; `get_delivery_methods(..., include_deleted=False)` passes the flag on. `--runxfail` on it: 28 passed. **Alarm:** with the markers on, all 4 strict cards XPASS(strict) and fail.

| Cards | Fails today on |
|---|---|
| DMS-G-04 | Then 1, `DID NOT RAISE HTTPException` |
| DMS-G-05, DMS-L-06 | the When, `TypeError` (no `include_deleted`), as their cards say |
| DMS-G-06 | Then 1, `TypeError` inside the `raises` wrap |

## Reproduced claims
- **Result line of the notes holds:** `24 passed, 4 xfailed` in 4 of 4 default runs, the coverage run among them. No flaky test.
- `--runxfail -rf`: `4 failed, 24 passed`, each on its card's line.
- **Mocks:** only the Conventions' failing commit / refresh wraps. No `try`, no `if`, no broad `pytest.raises`.

## Traceability
cases 28 · tests 28 · unmatched: none · marker mismatches: none. Order, docstrings, `# Then N`, `# [claude] <ID>` match; every BUG ID is in `bugs.md`; `ruff check` passes. `cmp.py`: 0 reports; selftest 2876 of 2880 (see `department_service.verify.md`).

## Limits of this round
The reference and the variants are mine; runs were not isolated from other agents; HTTP and a real race not exercised.

## Commands run
```
mutate.py app/services/delivery_method_service.py tests/unit/services/test_delivery_method_service.py --timeout 300 --json <scratch>/res/mut_delivery_method.json
  Mutants: 10 · killed 10 · timeout 0 · survived 0 · score 100%
pytest tests/unit/services/test_delivery_method_service.py -q -p no:cacheprovider --cov=app.services.delivery_method_service --cov-branch --cov-report=term-missing
  24 passed, 4 xfailed · 41 0 0 0 100%
pytest … --runxfail -rf                                                     4 failed, 24 passed
drive.py bases / muts / vars; post.py; cmp.py (+ --selftest); ruff check; git diff --stat -- app/services (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v\`. Only this report was written in the repo. No commit. Nothing was killed.
