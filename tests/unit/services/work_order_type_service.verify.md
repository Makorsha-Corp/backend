# Verification — `app/services/work_order_type_service.py`

> **Verdict:** PASS
> Tests: 23 passed · 5 xfail, all strict (reproduced ✅) · coverage 100% branch (41 statements, 0 branches)
> Mutation: 10 mutants · 10 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 28 unfaithful** (28 / 28 right; rebuilt by script, compared by eye with the department master)
> Hand variants: 47 · 41 caught by a pass card · 6 others: 3 equivalent, 3 bug-path (none is a rule gap)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 28 match their cards. The file has the department master's form line for line; my script found no difference from the cards.
- **The transaction contract is guarded on every write** (create, update, delete): a dropped commit, a dropped rollback, a swallowed or wrapped error, a dropped re-read and a re-read before the commit each fail a pass card. Both reads are caught committing, rolling back or flushing (TC6).
- Every mutant is killed; the variants no pass card sees are equivalent or BUG-1520 / BUG-1521 paths.

Written by Claude (all 28 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 28. No `work_order_type_service.local-run.json`, so no `## Local-coder patterns` section.

## Findings
None.

## Surviving mutants
None. All 10 kills end in a plain `N failed`.

**Guard.** `drive.py muts` re-ran each mutant without `-x`: every run reached all 23 pass tests, no collection or setup error, outcome equal to `mutate.py`'s.

## Hand variants
On my reference (`plug\ref\work_order_type.py`) through `plug\vplug.py`, `--runxfail`, WSV-C-05 deselected (not served). Every edit applied once; every run reached all 27 served tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| tc1 | 6 | 6 | WSV-C-01, WSV-C-03, WSV-C-04, WSV-U-01, WSV-D-01 | — |
| tc2 | 6 | 6 | WSV-C-01, WSV-C-04, WSV-U-01, WSV-D-01 | — |
| tc3 | 12 | 12 | WSV-C-02, WSV-C-03, WSV-C-04, WSV-C-06, WSV-U-02, WSV-U-03, WSV-D-02, WSV-D-03 | — |
| tc4 | 3 | 0 | — | 3 × `*_tc4_raw_commit` |
| tc5 | 3 | 3 | WSV-C-01, WSV-C-04, WSV-U-01, WSV-D-01 | — |
| tc6 | 6 | 6 | WSV-G-07, WSV-L-07 | — |
| r1 | 3 | 3 | WSV-C-01, WSV-C-04, WSV-C-06, WSV-U-01, WSV-D-01 | — |
| r2 | 4 | 1 | WSV-L-05 | `get_work_order_type_r2_ignore_flag`, `…_r2_always_hide`, `get_work_order_types_r2_flag_dropped` |
| arg | 4 | 4 | WSV-L-01 … WSV-L-04, WSV-L-08 | — |
| **Total** | **47** | **41** | | **6** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| 3 × `*_tc4_raw_commit` | **Equivalent:** a raw `db.commit()` that raises still reaches the method's `except`, which rolls back and re-raises (TC4 outcome unchanged). |
| `get_work_order_type_r2_ignore_flag`, `…_r2_always_hide` | **Bug-path** BUG-1521: only WSV-G-04, WSV-G-05 see them. |
| `get_work_order_types_r2_flag_dropped` | **Bug-path** BUG-1520: only WSV-L-06. |

## xfail tests against the reference
Reference: `get_work_order_type(..., include_deleted=False)` refuses a deleted type with the manager's 404; `get_work_order_types(..., include_deleted=False)` passes the flag on. Not served: WSV-C-05 (BUG-1214 needs the constraint changed). `--runxfail` on the reference: 27 passed, 1 failed (WSV-C-05). **Alarm:** with the markers on, WSV-G-04 … G-06 and WSV-L-06 XPASS(strict) and fail.

| Cards | Fails today on |
|---|---|
| WSV-C-05 | the When: `IntegrityError` on `uq_wo_type_workspace_name`. The card says "Then 1 (the call raises IntegrityError on `uq_wo_type_workspace_name`)": the same failure, named by the first Then line it blocks. |
| WSV-G-04 | Then 1, `DID NOT RAISE HTTPException` |
| WSV-G-05, WSV-L-06 | the When, `TypeError` (no `include_deleted`), as their cards say |
| WSV-G-06 | Then 1, `TypeError` inside the `raises` wrap |

## Reproduced claims
- **Result line of the notes holds:** `23 passed, 5 xfailed` in 4 of 4 default runs, the coverage run among them. No flaky test.
- `--runxfail -rf`: `5 failed, 23 passed`, each on its card's line (table above).
- **Mocks:** only the Conventions' failing commit / refresh wraps. No `try`, no `if`, no broad `pytest.raises`.

## Traceability
cases 28 · tests 28 · unmatched: none · marker mismatches: none. Card order equals file order; docstrings, `# Then N` and `# [claude] <ID>` match. Every BUG ID is in `bugs.md`. `ruff check` passes. `cmp.py` (all 315 cards of the batch): 0 reports; selftest 2876 of 2880 planted mistakes (see `department_service.verify.md`).

## Limits of this round
The reference and the variants are mine; runs were not isolated from other agents (each kill is a plain `N failed`); HTTP and a real race not exercised.

## Commands run
```
mutate.py app/services/work_order_type_service.py tests/unit/services/test_work_order_type_service.py --timeout 300 --json <scratch>/res/mut_work_order_type.json
  Mutants: 10 · killed 10 · timeout 0 · survived 0 · score 100%
pytest tests/unit/services/test_work_order_type_service.py -q -p no:cacheprovider --cov=app.services.work_order_type_service --cov-branch --cov-report=term-missing
  23 passed, 5 xfailed · 41 0 0 0 100%
pytest … --runxfail -rf                                                     5 failed, 23 passed
drive.py bases / muts / vars; post.py; cmp.py (+ --selftest 6, 11, 23); ruff check; git diff --stat -- app/services (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v\`. Only this report was written in the repo. No commit. Nothing was killed.
