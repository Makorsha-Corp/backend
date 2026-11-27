# Verification — `app/services/app_settings_service.py`

> **Current verdict: PASS** (round 2, 2026-11-04, cases revision 2). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 32 passed · 6 xfail, 5 strict + 1 non-strict (reproduced ✅) · coverage 100% branch (45 statements, 4 branches)
> Mutation: 19 mutants · 18 killed · 1 survived → score 95% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 38 unfaithful** (38 / 38 right; rebuilt by script)
> Hand variants: 39 · 36 caught by a pass card · 3 others: 1 rule gap (in Findings), 2 bug-path
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 38 match their cards.
- **The transaction rules are guarded** (S1–S5): a dropped commit, a dropped rollback, a swallowed error on each of the three writes, a dropped re-read or a re-read before the commit (create, update), a commit or rollback on the "not found" answers (S4), and a commit, rollback or flush in each of the three reads each fail a pass card.
- **Why NEEDS WORK:** one rule gap, for the case designer. `get_settings`'s default `limit=100` has no card: the mutant `100 → 101` survives, and so does my variant of it.

Written by Claude (all 38 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 38. No `app_settings_service.local-run.json`, so no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `get_settings` signature `limit=100`, R1 | ASV-L-02 … L-04 always pass `limit`. No card calls with the default, so a different default passes. Shape 1b of the case designer: "A default limit is a card"; the sibling services all have one (DSV-L-02 and peers). | mutant #5 L11 `100 → 101` SURVIVED; variant `get_settings_arg_limit_default` fails no card. | **case designer** |

No fidelity finding.

### Scratch card that closes the gap
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v\prop\test_prop_svc1v.py` (`test_r_as_1`), not in the repo. It passes today and on my reference, and fails on the variant named.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-AS-1 | new card, `get_settings` R1 (default limit) | 101 rows, by `add_all`: k = 0 … 100, setting, but `name f"s{k:03d}"`; When `result = svc.get_settings(db, workspace_id=W1.id)` | 1. returns: `len(result) == 100`. | pass | mutant L11 `100 → 101`; `get_settings_arg_limit_default` |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 5 | L11:87 | `limit: int = 100` → `101` | case-missing | Finding 1. | case designer |

The 18 kills end in a plain `N failed`. **Guard.** `drive.py muts` re-ran all 19 mutants without `-x`: every run reached all 32 pass tests, no collection or setup error, outcome equal to `mutate.py`'s.

## Hand variants
On my reference through `plug\vplug.py`, `--runxfail`, ASV-C-03, C-06, C-07 deselected (not served). Every edit applied once; every run reached all 35 served tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| s1 (drop commit, 3 writes) | 3 | 3 | ASV-C-01, ASV-C-08 … C-10, ASV-U-01, ASV-U-06, ASV-D-01, ASV-D-04 | — |
| s2 (drop rollback, swallow, 3 writes) | 6 | 6 | ASV-C-09 … C-11, ASV-U-07, ASV-D-04 | — |
| s3 (drop re-read, re-read before commit) | 4 | 4 | ASV-C-01, ASV-C-10, ASV-U-01 | — |
| s4 (commit / rollback on "not found") | 4 | 4 | ASV-U-02, ASV-D-02 | — |
| tc6 (reads commit, roll back, flush) | 9 | 9 | ASV-G-04, ASV-N-04, ASV-L-08 | — |
| r1 (workspace ignored) | 4 | 4 | ASV-C-01, ASV-C-02, ASV-C-08 … C-10, ASV-D-02, ASV-L-01, ASV-L-08 | — |
| r2 (update not applied, delete kept, returns) | 5 | 4 | ASV-U-01, ASV-U-06, ASV-D-01, ASV-G-02 | `get_settings_r2_no_id_tiebreak` |
| r3 (name not trimmed) | 1 | 0 | — | `create_r3_no_trim` |
| arg (`skip`, `limit`, default limit) | 3 | 2 | ASV-L-02 … L-04, ASV-L-07 | `get_settings_arg_limit_default` |
| **Total** | **39** | **36** | | **3** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `create_r3_no_trim` | **Bug-path** BUG-1524: only ASV-C-04. |
| `get_settings_r2_no_id_tiebreak` | **Bug-path** BUG-1525: only ASV-L-06 (the statement card). |

## xfail tests against the reference
Reference: `create_setting` stores the name trimmed; `get_settings` orders by `lower(name), id` before `offset` / `limit`. Not served: ASV-C-03 (schema refusal), ASV-C-06, C-07 (BUG-1225's index). `--runxfail` on the reference: 35 passed, 3 failed (exactly those). **Alarm:** with the markers on, ASV-C-04 and ASV-L-06 XPASS(strict) and fail; ASV-L-05 (non-strict) XPASSes.

Fails today, from `failmap.py`: L-05 Then 2 (`['zeta', 'Alpha', 'beta']`), L-06 Then 2 (`'lower(' in ''`), C-03 Then 1, C-04 Then 2 (`' Feat '`), C-06, C-07 Then 1 (`DID NOT RAISE IntegrityError`). Each is the line its card names.

## Reproduced claims
- **Result line of the notes holds:** `32 passed, 6 xfailed` in 4 of 4 default runs, the coverage run among them. No flaky test.
- `--runxfail -rf`: `6 failed, 32 passed`.
- **Mocks:** only the failing commit / refresh wraps and the spies the Conventions name. No `try`, no `if`, no broad `pytest.raises`.

## Traceability
cases 38 · tests 38 · unmatched: none · marker mismatches: none. Order, docstrings, `# Then N`, `# [claude] <ID>` match; every BUG ID is in `bugs.md`; `ruff check` passes. `cmp.py`: 0 reports; selftest 2876 of 2880 (see `department_service.verify.md`).

## Limits of this round
The reference and the variants are mine; runs were not isolated from other agents; BUG-1225's index was not created (no DDL on the shared database); HTTP not exercised.

## Commands run
```
mutate.py app/services/app_settings_service.py tests/unit/services/test_app_settings_service.py --timeout 300 --json <scratch>/res/mut_app_settings.json
  Mutants: 19 · killed 18 · timeout 0 · survived 1 · score 95%
  SURVIVED #5 L11:87 const: 100 -> 101
pytest tests/unit/services/test_app_settings_service.py -q -p no:cacheprovider --cov=app.services.app_settings_service --cov-branch --cov-report=term-missing
  32 passed, 6 xfailed · 45 0 4 0 100%
pytest … --runxfail -rf                                                     6 failed, 32 passed
drive.py bases / muts / vars; post.py; propdrive.py (R-AS-1); cmp.py (+ --selftest); ruff check; git diff --stat -- app/services (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add R-AS-1 (Given, When and Then written out above).
2. **Executor,** after 1: implement it and send back for re-verification.

## Round 2 — 2026-11-04 (cases revision 2, narrow)

> **Verdict:** PASS
> Tests: 33 passed · 6 xfail (reproduced ✅) · coverage 100% branch (45 statements, 4 branches)
> Mutation: not re-run in full; line 11 re-run: 2 mutants · 2 killed (the round 1 survivor `100 → 101` is killed) → 19 / 19, score 100%
> Fidelity: **0 of 39 unfaithful** (the new card read by eye; all 39 rebuilt by script)
> Hand variants: 39 · 37 caught by a pass card · the 2 others are the bug paths of round 1
> Source commit: e48a092 · Cases revision: 2; spec APPROVED, unchanged

Finding 1 is closed. No new rule gap. No test edited by me, no commit.

| Card | Recipe | Read against card | Fails on |
|---|---|---|---|
| ASV-L-09 | R-AS-1 | matches: 101 rows by `add_all`, `name f"s{k:03d}"`, commit point, `get_settings` with defaults, `len(result) == 100` | `get_settings_arg_limit_default`; mutant L11 `100 → 101` |

- **Reproduced:** `33 passed, 6 xfailed` in 4 of 4 default runs; `--runxfail`: `6 failed, 33 passed`, each on its card's line. Reference `--runxfail`: 36 passed, the same 3 unserved. Every variant run reached all 36 served tests.
- **Traceability:** cases 39 · tests 39 · unmatched: none · marker mismatches: none. `cmp.py` gives one report, `Given number 0` for ASV-L-09 — a false alarm of my script (`range(101)` starts at 0 without writing it). `ruff check` passes.

```
mutate.py app/services/app_settings_service.py tests/unit/services/test_app_settings_service.py --lines 11-11 --timeout 300
  Mutants: 2 · killed 2 · timeout 0 · survived 0 · score 100%
repro.py app_settings; drive.py bases app_settings; drive.py vars app_settings; post.py; cmp.py app_settings
```
