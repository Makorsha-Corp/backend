# Verification — `app/services/machine_maintenance_log_service.py`

> **Verdict:** PASS
> Tests: 22 passed · 13 xfail, 12 strict + 1 non-strict (reproduced ✅) · coverage 100% branch (42 statements, 0 branches)
> Mutation: 10 mutants · 10 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 35 unfaithful** (35 / 35 right; rebuilt by script)
> Hand variants: 45 · 41 caught by a pass card · 4 others: 3 equivalent, 1 bug-path (none is a rule gap)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 35 match their cards.
- **The transaction contract is guarded on every write** (`create_log`, `update_log`, `delete_log`), activity entries included: dropped commit, dropped rollback, swallowed or wrapped error, dropped re-read, re-read before the commit each fail a pass card. `get_log` and `list_logs` are caught committing, rolling back or flushing (TC6). Every list argument (`machine_id`, `maintenance_type`, `skip`, `limit`, default limit) is checked.
- Every mutant is killed; the variants no pass card sees are equivalent or the BUG-1150 path.

Written by Claude (all 35 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 35. No `machine_maintenance_log_service.local-run.json`, so no `## Local-coder patterns` section.

## Findings
None.

## Surviving mutants
None. All 10 kills end in a plain `N failed`.

**Guard.** `drive.py muts` re-ran each mutant without `-x`: every run reached all 22 pass tests, no collection or setup error, outcome equal to `mutate.py`'s.

## Hand variants
On my reference through `plug\vplug.py`, `--runxfail`, the 11 unserved cards deselected. Every edit applied once; every run reached all 24 served tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| tc1 | 6 | 6 | MLS-C-01, MLS-C-05, MLS-C-06, MLS-U-01, MLS-D-01 | — |
| tc2 | 6 | 6 | MLS-C-01, MLS-C-06, MLS-U-01, MLS-D-01 | — |
| tc3 | 12 | 12 | MLS-C-02 … MLS-C-06, MLS-C-11, MLS-U-02, MLS-U-03, MLS-D-02, MLS-D-03 | — |
| tc4 | 3 | 0 | — | 3 × `*_tc4_raw_commit` |
| tc5 | 3 | 3 | MLS-C-01, MLS-C-06, MLS-U-01, MLS-D-01 | — |
| tc6 | 6 | 6 | MLS-G-06, MLS-L-06 | — |
| r1 | 3 | 3 | MLS-C-01, MLS-C-11, MLS-U-01, MLS-D-01 | — |
| r2 | 1 | 0 | — | `get_log_r2_ignore_flag` |
| arg | 5 | 5 | MLS-L-01 … MLS-L-05 | — |
| **Total** | **45** | **41** | | **4** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| 3 × `*_tc4_raw_commit` | **Equivalent:** the method's own `except` rolls back and re-raises a failing raw commit. |
| `get_log_r2_ignore_flag` | **Bug-path** BUG-1150: only MLS-G-03. |

## xfail tests against the reference
Reference: `get_log(..., include_deleted=False)` refuses a deleted log with the manager's 404. Manager pass-through bugs are not fixed in it; unserved: MLS-C-07 … C-10, MLS-D-04, MLS-G-05, MLS-L-07, MLS-L-08, MLS-U-04 … U-06. `--runxfail` on the reference: 24 passed, 11 failed (exactly those). **Alarm:** with the markers on, MLS-G-03 and MLS-G-04 XPASS(strict) and fail.

Fails today, from `failmap.py`: C-07, C-10, G-03, G-05 on Then 1 (`DID NOT RAISE`); C-08, C-09, U-04, U-05 on Then 2; U-06 on Then 4; L-07 on Then 1; L-08 (non-strict) on Then 2; D-04 on Then 3; G-04 in the When, `TypeError`. Each is the line its card names.

## Reproduced claims
- **Result line of the notes holds:** `22 passed, 13 xfailed` in 4 of 4 default runs, the coverage run among them. No flaky test.
- `--runxfail -rf`: `13 failed, 22 passed`.
- **Mocks:** only the failing commit / refresh wraps and the MLS-D-04 clock patch the Conventions name. No `try`, no `if`, no broad `pytest.raises`.

## Traceability
cases 35 · tests 35 · unmatched: none · marker mismatches: none. Order, docstrings, `# Then N`, `# [claude] <ID>` match; every BUG ID is in `bugs.md`; `ruff check` passes. `cmp.py`: 0 reports; selftest 2876 of 2880 (one miss here: a planted `rows[0]` → `rows[1]` in MLS-U-01 Then 6, an index my script does not compare).

## Limits of this round
The reference and the variants are mine; runs were not isolated from other agents; HTTP and a real race not exercised.

## Commands run
```
mutate.py app/services/machine_maintenance_log_service.py tests/unit/services/test_machine_maintenance_log_service.py --timeout 300 --json <scratch>/res/mut_machine_maintenance_log.json
  Mutants: 10 · killed 10 · timeout 0 · survived 0 · score 100%
pytest tests/unit/services/test_machine_maintenance_log_service.py -q -p no:cacheprovider --cov=app.services.machine_maintenance_log_service --cov-branch --cov-report=term-missing
  22 passed, 13 xfailed · 42 0 0 0 100%
pytest … --runxfail -rf                                                     13 failed, 22 passed
drive.py bases / muts / vars; post.py; cmp.py (+ --selftest); ruff check; git diff --stat -- app/services (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v\`. Only this report was written in the repo. No commit. Nothing was killed.
