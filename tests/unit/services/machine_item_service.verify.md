# Verification — `app/services/machine_item_service.py`

> **Verdict:** PASS
> Tests: 24 passed · 18 xfail, 17 strict + 1 non-strict (reproduced ✅) · coverage 100% branch (39 statements, 0 branches)
> Mutation: 9 mutants · 9 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 42 unfaithful** (42 / 42 right; rebuilt by script)
> Hand variants: 43 · 34 caught by a pass card · 9 others: 2 equivalent, 7 bug-path (none is a rule gap)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 42 match their cards.
- **The transaction contract is guarded on every write**, ledger and activity rows included: dropped commit, dropped rollback, swallowed or wrapped error (all three writes), dropped re-read and re-read before the commit (create, update; delete re-reads nothing) each fail a pass card. Both reads are caught committing, rolling back or flushing.
- **Q1's scope is guarded today:** a variant that also translates a `ValueError` on create fails MIS-C-14 (pass). Everything about the delete translation itself (rollback first, `detail`, `errors` as given and in order) is caught only by MIS-D-03, which is BUG-1081's xfail card: a bug path, correct until the fix lands.

Written by Claude (all 42 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 / 42. No `machine_item_service.local-run.json`, so no `## Local-coder patterns` section.

## Findings
None.

## Surviving mutants
None. All 9 kills end in a plain `N failed`.

**Guard.** `drive.py muts` re-ran each mutant without `-x`: every run reached all 24 pass tests, no collection or setup error, outcome equal to `mutate.py`'s.

## Hand variants
On my reference through `plug\vplug.py`, `--runxfail`, the 13 unserved cards deselected. Every edit applied once; every run reached all 29 served tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| tc1 (incl. delete) | 5 | 5 | MIS-C-01, MIS-C-06, MIS-C-07, MIS-U-01, MIS-U-05, MIS-D-01, MIS-D-08 | — |
| tc2 | 4 | 4 | MIS-C-01, MIS-C-07, MIS-U-01 | — |
| tc3 (incl. delete) | 10 | 10 | MIS-C-02 … MIS-C-07, MIS-C-14, MIS-C-15, MIS-U-02, MIS-D-02 … | — |
| tc4 | 2 | 0 | — | 2 × `*_tc4_raw_commit` |
| tc5 | 2 | 2 | MIS-C-01, MIS-C-07, MIS-U-01 | — |
| tc6 | 6 | 6 | MIS-G-07, MIS-L-05 | — |
| r1 | 2 | 2 | MIS-C-01, MIS-C-15, MIS-D-01, MIS-D-08 … | — |
| r2 (translation, `include_deleted`) | 7 | 1 | MIS-C-14 | 5 × `delete_r2_*`, `get_r2_ignore_flag` |
| r3 (another workspace's item) | 1 | 0 | — | `get_r3_no_item_ws_check` |
| arg | 4 | 4 | MIS-L-01 … MIS-L-05 | — |
| **Total** | **43** | **34** | | **9** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| 2 × `*_tc4_raw_commit` | **Equivalent:** the method's own `except` rolls back and re-raises a failing raw commit. |
| `delete_r2_no_rollback_on_valueerror`, `delete_r2_errors_reversed`, `delete_r2_errors_dropped`, `delete_r2_detail_str`, `delete_r2_no_translation` | **Bug-path** BUG-1081: each fails MIS-D-03 on the reference (rollback via the uncommitted X row and `unchanged(MI)`, `detail`, `errors` exact and in order). |
| `get_r2_ignore_flag` | **Bug-path** BUG-1077: only MIS-G-03. |
| `get_r3_no_item_ws_check` | **Bug-path** BUG-1077 / BUG-1086: only MIS-G-05, MIS-G-06. |

## xfail tests against the reference
Reference: `get_machine_item(..., include_deleted=False)` refuses a row of a deleted machine, of a machine in a deleted factory, or of a removed item, unless asked, and always refuses a row whose item is in another workspace; `delete_machine_item` turns the manager's `ValueError(detail, errors)` into `app.core.exceptions.ValidationError` after the rollback. Manager bugs are not fixed; unserved: MIS-C-08 … C-12, MIS-D-04, D-06, D-07, MIS-L-06 … L-08, MIS-U-03, U-04. `--runxfail` on the reference: 29 passed, 13 failed (exactly those). **Alarm:** with the markers on, MIS-G-03 … G-06 and MIS-D-03 XPASS(strict) and fail.

Fails today, from `failmap.py`: every xfail test fails on the Then line (or the When `TypeError`) its card names; MIS-D-03 on Then 1 with the patched manager's `ValueError` escaping, as the card says.

## Reproduced claims
- **Result line of the notes holds:** `24 passed, 18 xfailed` in 4 of 4 default runs, the coverage run among them. No flaky test.
- `--runxfail -rf`: `18 failed, 24 passed`.
- **Mocks:** only the failing commit / refresh wraps and the manager patches the Conventions name (MIS-D-03, MIS-C-14). No `try`, no `if`, no broad `pytest.raises`.

## Traceability
cases 42 (no MIS-D-05 exists, as the notes say) · tests 42 · unmatched: none · marker mismatches: none. Order, docstrings, `# Then N`, `# [claude] <ID>` match; every BUG ID is in `bugs.md`; `ruff check` passes. `cmp.py`: 0 reports; selftest 2876 of 2880 (one miss here: a planted `entries[0]` → `entries[1]` in MIS-D-01, an index my script does not compare).

## Limits of this round
The reference and the variants are mine; runs were not isolated from other agents; HTTP (the 400 body) and a real race not exercised.

## Commands run
```
mutate.py app/services/machine_item_service.py tests/unit/services/test_machine_item_service.py --timeout 300 --json <scratch>/res/mut_machine_item.json
  Mutants: 9 · killed 9 · timeout 0 · survived 0 · score 100%
pytest tests/unit/services/test_machine_item_service.py -q -p no:cacheprovider --cov=app.services.machine_item_service --cov-branch --cov-report=term-missing
  24 passed, 18 xfailed · 39 0 0 0 100%
pytest … --runxfail -rf                                                     18 failed, 24 passed
drive.py bases / muts / vars; post.py; cmp.py (+ --selftest); ruff check; git diff --stat -- app/services (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v\`. Only this report was written in the repo. No commit. Nothing was killed.
