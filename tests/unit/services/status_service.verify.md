# Verification — `app/services/status_service.py`

> **Current verdict: PASS** (round 4, 2026-11-04, cases revision 5). See "Round 4" at the end. Round 3 was NEEDS WORK; its findings are closed. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 36 passed · 35 xfailed (34 strict, 1 non-strict: L-09) (reproduced ✅) · coverage 93% branch (41 statements, 3 missed: lines 23–25, unreachable until BUG-035; 4 branches, all covered)
> Mutation: 17 mutants · 15 killed · 2 survived → score 94% (after excluding 0 equivalent, 0 dead, 1 bug-path)
> Fidelity: **0 of 71 unfaithful** (all 71 read by eye against their cards, SSV-U-20 after its fix included)
> Hand variants: 47 · 42 caught by a pass card · 5 others: 3 gaps (in Findings), 1 bug-path, 1 with no observable effect
> Source commit: e48a092 · Cases revision: 2 (with the 2026-11-04 SSV-U-20 fix); spec APPROVED

## Summary
- **The tests can be trusted as written.** All 71 match their cards. The SSV-U-20 fix is in: the notes have the entry (Revision history, 2026-11-04). The cases give G `type "STM"`, and the test builds it so. Under `--runxfail`, U-20 now fails at Then 1 (`DID NOT RAISE HTTPException`), the line its card names, no longer in its Given.
- **The guards hold.** S1, S3 and S4 are guarded on every path. S2 is guarded for a dropped rollback and a swallowed error. Each of these fails a pass card: a missing re-read, a re-read before the commit, a failing re-read swallowed or undone, a commit or rollback on "not found", and a commit, rollback or flush in either read. The passing sides of BUG-1220 hold too: protection by substring, case-insensitively or after trimming, on a comment-only edit, on the current name, or by another workspace's sequence is caught by U-10 … U-13, U-24, D-12 and D-16.
- **The leak cards:** the Reviewer summary marks SSV-G-04, C-02, U-06 and D-04 to retire with BUG-035. **SSV-L-01 is missing from that list**, although its title says "(documents BUG-035)" and it cannot pass after the fix. The executor's notes list all five.
- **Why NEEDS WORK:** three small gaps, all for the case designer. (1) The L-01 retire entry. (2) As in `account_tag_service`, the failing-commit cards check `str(exc.value)` only, so a re-raise as a new `RuntimeError` passes on update and delete. (3) The default `skip=0` cannot be seen by SSV-L-05: mutant #3 survives.

Written by Claude (all 71 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 71. No `status_service.local-run.json`, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing (retire list) | Reviewer summary, BUG-035 note; SSV-L-01 | The retire list names G-04, C-02, U-06, D-04 but not L-01, which also "documents BUG-035". After the fix L-01 breaks either way. Called as today, it raises `TypeError`. Given `workspace_id=W1.id`, its Then 2 (`{Z1.id, A.id, Z2.id} <= idset(result)`) fails, since Z1 and Z2 are W2's. `status_service.notes.md` already lists L-01 among the retirees, so the two files disagree. | cases line 11 vs. card SSV-L-01 (title, Then 2) and notes "Notes for maintainers". | **case designer** |
| 2 | case-missing | S2 "reaches the caller unchanged" (TC3/TC4); SSV-U-17, D-13 | The failing-commit cards check only `str(exc.value) == "boom"`. A write that re-raises `RuntimeError(str(e))` passes. On create, SSV-C-02 (`IntegrityError`, pgcode) catches a wrap. | variants `s2_update_wrap`, `s2_delete_wrap` pass all 36 pass tests. R-ST-1a/b fail on them (`exc.value is boom`). | **case designer** |
| 3 | case-missing | `get_statuses` R2 with the default `skip=0` (spec heading); SSV-L-05 | L-05 builds 101 rows and expects 100. With a default `skip` of 1, 100 still come back. | mutant #3 (L11:52 `0 → 1`) and variant `r_list_default_skip1` pass all 36. R-ST-2 fails on them (`1 == 2`). | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3v\status\test_prop_st.py`, not in the repo. All 3 pass today, and each fails on its variants as listed.

| Recipe | Where | Given and When | Then | Expect |
|---|---|---|---|---|
| R-ST-0 | Reviewer summary (BUG-035 note) and, optionally, each leak card's title | add SSV-L-01 to "retired with the fix" | — | — |
| R-ST-1 | one Then line on SSV-U-17, D-13 (and C-12) | **failing commit** with `boom = RuntimeError("boom")` built before the wrap and given as `side_effect=boom` | new line: raises: `exc.value is boom` | pass (C-12: xfail BUG-035, as today) |
| R-ST-2 | new card, `get_statuses` R2 (defaults) | A = status. B = status, but `name "Beta"`. When `result = svc.get_statuses(db)` | 1. returns: `n_all <= 100` (a precondition of the card). 2. returns: `len(result) == n_all`. | pass (after BUG-035: `len(result) == 2` with `workspace_id=W1.id`) |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 3 | L11:52 | default `skip: int = 0` → `1` | case-missing | Finding 3. Spec `get_statuses(db, skip=0, limit=100)` and R2. The only caller (`statuses.py:22`) passes `skip`, so it cannot be seen over the API. But the spec states the default, and L-05 is meant to cover it ("with the default skip and limit"). | **case designer** |
| 5 | L25:12 | `return status` → `return None` in `create_status` | bug-path | Lines 23–25 cannot run until BUG-035: every create fails at the flush (23502). Only the xfail C-01, C-05, C-11, C-13 reach the return. | — (resolves with BUG-035) |

The 15 kills end in a plain failure of a pass card. The 36 pass tests ran on every mutant.

## Hand variants
Source edited in memory by my plugin `vplug.py`, run against the 36 pass tests. Every variant was applied, and every run reached all 36.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| s1 (flush for commit ×3; no re-read; re-read before commit; failing re-read swallowed or undone) | 7 | 6 | SSV-U-01, U-02, U-06, U-10 … U-13, U-17, U-18, U-24, SSV-D-01, D-04, D-12, D-13, D-16 | `s1_create_flush` |
| s2 (no rollback ×3, swallow ×3, wrap ×3, wrap into `HTTPException`) | 10 | 8 | SSV-C-02, SSV-U-17, U-18, SSV-D-13 | `s2_update_wrap`, `s2_delete_wrap` |
| s3 ("not found" commits, rolls back, returns `None`) | 5 | 5 | SSV-U-04, SSV-D-02, D-03 | — |
| s4 (reads commit, roll back, flush) | 6 | 6 | SSV-L-11, SSV-G-03 | — |
| list / get rules (skip, limit cap, defaults, wrong row) | 5 | 3 | SSV-L-05, L-06, L-08, SSV-G-01, G-04 | `r_list_limit_cap100`, `r_list_default_skip1` |
| update rules (exclude_unset, name only, returns None; BUG-1220's passing side ×5) | 8 | 8 | SSV-U-01 … U-03, U-06, U-10 … U-13, U-24 | — |
| delete rules (returns None, no remove, BUG-1220's passing side ×3, sequence cleaned) | 6 | 6 | SSV-D-01, D-04, D-12, D-16 | — |
| **Total** | **47** | **42** | | **5** |

### Considered and not listed
| Variant | Why it is not a finding |
|---|---|
| `s1_create_flush` | **Bug-path** BUG-035: the create's commit line is unreachable today (coverage 23–25). C-01 and C-12 check it once the fix lands. |
| `r_list_limit_cap100` (`min(limit, 100)`) | No observable effect: the endpoint bounds `limit` to ≤ 100 (spec Integration, BUG-1217), and the only caller is the endpoint. |

## Checked points
- **SSV-U-20 fix:** present in the notes (Revision history 2026-11-04), in the cases (header "Fix 2026-11-04", Given 3 `type "STM"`) and in the test (`mk_workflow([s.id], name="Alt Flow", type="STM")`). Reverified: strict xfail, fails at Then 1. The reason is `BUG_1220`, with no DISCREPANCY text left.
- **Leak cards and BUG-035:** G-04, C-02, U-06, D-04 are marked to retire in the Reviewer summary, and their titles say "documents BUG-035". L-01 is not in the list (Finding 1).

## xfail tests
`--runxfail` with my plugin `vfail.py`: **35 failed, 36 passed**. Each fails where its card's "Fails today on" says:
- Inside the When, with `TypeError: … got an unexpected keyword argument 'workspace_id'` (the card's "the call raises TypeError"): L-02, G-05, C-01, C-05, C-11 … C-13, U-07, D-05. C-09 and C-10 raise it inside their Then 1 `raises:` wrap.
- On Then 1: C-06, U-14 (`DID NOT RAISE ValidationError`); C-07 (`' Feat '`), U-15 (`' Done '`); U-16 (`DID NOT RAISE IntegrityError`); U-08, U-09, U-19 … U-23, D-06, D-07, D-14 (`DID NOT RAISE HTTPException`); D-08 … D-11, D-15, D-17, D-18 (`IntegrityError` NotNullViolation on `current_status_id`, as their cards name).
- On Then 2: L-09 (`['zeta', 'Alpha', 'beta']`, non-strict) and L-10 (`'lower(' in ''`).
None fails on a setup or import error.

## Reproduced claims
- **The notes' Result line holds:** `36 passed, 35 xfailed` in 3 of 3 default runs (the coverage run is one of them). No flaky test.
- `--runxfail -rf`: `35 failed, 36 passed`.
- **Mocks:** only the failing commit / refresh wraps, the spies and the listen-only statement recorder of L-10. `ruff check` passes.

## Traceability
cases 71 · tests 71 · unmatched: none · marker mismatches: none (36 pass with no marker; 34 `strict=True`; L-09 `strict=False`, as its Expect says). Every reason names its BUG ID, and every BUG ID is in `bugs.md`. Card order, docstrings, `# Then N` and `# [claude] <ID>` all match.

## Limits of this round
I did not build a reference for the intended behaviour. The executor's `refplug.py` passes all 71 with `--runxfail` after the U-20 fix (notes), and I used it as evidence only. The runs were not isolated from other agents' runs on the same database.

## Commands run
```
mutate.py app/services/status_service.py tests/unit/services/test_status_service.py --json <scratch>/status/mut.json
  Mutants: 17 · killed 15 · timeout 0 · survived 2 · score 88%
  SURVIVED #3 L11:52 const: 0 -> 1 ; #5 L25:12 return: return None
pytest tests/unit/services/test_status_service.py -q -p no:cacheprovider --cov=app.services.status_service --cov-branch --cov-report=term-missing
  36 passed, 35 xfailed · 41 3 4 0 93% (23-25)
pytest … --runxfail -rf (with -p vfail)                         35 failed, 36 passed
pytest … (x2)                                                   36 passed, 35 xfailed (both)
drive.py app.services.status_service … variants.py              47 variants (above)
pytest test_prop_st.py (base + 3 variants)                      3 passed on base; each variant fails its proposal
trace.py; ruff check (passes); grep of callers of status_service (only app/api/v1/endpoints/statuses.py)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3v\` (own `COVERAGE_FILE` per run). I wrote only this report in the repo. No commit. No process was killed.

## Fix list
1. **Case designer:** add SSV-L-01 to the BUG-035 retire list (R-ST-0); add R-ST-1's Then line to SSV-U-17, D-13 (and C-12); add R-ST-2.
2. **Executor,** after 1: implement them, then send the module back for a narrow re-verification.

## Round 2 — 2026-11-04 (cases revision 3, narrow)

> **Verdict:** PASS
> Tests: 37 passed · 35 xfailed (reproduced ✅, 3 of 3 runs) · coverage unchanged (lines 23–25 unreachable until BUG-035)
> Mutation: line 11 re-run: 2 mutants · 2 killed (#3 `skip 0 → 1` now killed by SSV-L-12). Overall 16 killed of 17 → score 100% (after excluding 1 bug-path, #5)
> Fidelity: **0 of 72 unfaithful** (the 4 changed or new cards read by eye; all 72 traced by script)
> Source commit: e48a092 · Cases revision: 3; spec APPROVED, unchanged

Findings 1–3 are closed. There is no new finding. I edited no test and made no commit.

| Card | Recipe | Read against card | Variant / mutant that now fails it |
|---|---|---|---|
| Reviewer summary | R-ST-0 | SSV-L-01 now in the BUG-035 retire list with G-04, C-02, U-06, D-04. This matches the notes. | — |
| SSV-C-12 | R-ST-1 | matches (`boom` prebuilt, Then 5 `exc.value is boom`; still strict xfail BUG-035, fails on the `TypeError`) | — (create is unreachable today) |
| SSV-U-17 | R-ST-1 | matches | `s2_update_wrap` |
| SSV-D-13 | R-ST-1 | matches | `s2_delete_wrap` |
| SSV-L-12 (new) | R-ST-2 | matches (Then 1 the precondition `n_all <= 100`, Then 2 `len(result) == n_all`) | `r_list_default_skip1`; mutant #3 |

- **Reproduced:** `37 passed, 35 xfailed` in 3 of 3 runs. `--runxfail`: `35 failed, 37 passed`.
- **Traceability:** cases 72 · tests 72 · unmatched: none · marker mismatches: none. `ruff check` passes.

```
mutate.py app/services/status_service.py tests/unit/services/test_status_service.py --lines 11-11
  Mutants: 2 · killed 2 · survived 0 · score 100%   (L11:52 0 -> 1 KILLED; L11:68 100 -> 101 KILLED)
pytest tests/unit/services/test_status_service.py -q -p no:cacheprovider   (x3)   37 passed, 35 xfailed
pytest … --runxfail                                                               35 failed, 37 passed
drive.py … s2_update_wrap s2_delete_wrap r_list_default_skip1   all 3 KILLED
trace.py; ruff check
```

## Round 3 — 2026-11-04 (cases revision 4, OQ-13 answered; narrow)

> **Verdict:** NEEDS WORK — 1 case gap (case designer). No test is wrong.
> Tests: 36 passed · 39 xfailed (reproduced ✅, 3 of 3 runs) · coverage unchanged (lines 23–25 unreachable until BUG-035)
> Mutation: touched lines only (30–55, `update_status` and `delete_status`): 11 mutants · 11 killed → 100%. Overall unchanged: 16 of 17 killed, #5 bug-path → 100%.
> Fidelity: **0 of 5 unfaithful** (SSV-U-24, U-25, U-26, D-16, D-19 read by eye; all 75 traced by script)
> Reference fix (mine: BUG-1220 protection with BUG-1880's matching, R4a detail, rollback before the 400): under `--runxfail`, 51 passed, 24 failed, and the 24 are exactly the cards of BUG-035, 1218, 1221, 1680 and 1681. **Every BUG-1220 and BUG-1880 card passes**, U-24, U-25, D-16 and D-19 included.
> Fix variants: 7 · 6 caught by a card · 1 survives (Finding R3-1)
> Source commit: e48a092 · Cases revision: 4; spec APPROVED (OQ-13 answered by the owner)

### Fidelity and fails-today
- **U-24, U-25, D-16, D-19:** each test matches its card. The stored names are `"receiving"`, `" Receiving "`, `" Complete"` and `"COMPLETE"`. The details quote the stored (unnormalised) name, as R4a says, plus 'Purchase Order', followed by `unchanged`.
- **U-26** (`"Re ceiving"`, renamed) is a pass card and matches.
- **`--runxfail`:** U-24, U-25, D-16 and D-19 fail on Then 1 (`DID NOT RAISE HTTPException`), as their cards say.

### Variants of the reference fix
Run with `--runxfail` against `…\svc3v\status\variants_r3.py`:

| Variant | Cards that catch it |
|---|---|
| exact spelling only (the old R4b) | U-24, U-25, D-16, D-19 |
| lower-case only, no trim | U-25, D-16 |
| trim only, no lower-case | U-24, D-19 |
| strip inner spaces too (`"Re ceiving"` → stage) | U-26 |
| prefix match (`"Receiving Bay"`, `"Completed"` → stage) | U-12, D-12 |
| detail shows the normalised name | U-24, U-25, D-16, D-19 |
| **survives:** strip inner spaces on **delete** only | — (Finding R3-1) |

### Findings (round 3)
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| R3-1 | case-missing | `delete_status` R3 with `update_status` R4b (inner spaces are not trimmed) | U-26 pins "a space inside is not a stage name" on rename only. On delete, only `"Completed"` (D-12) and `"Receiving Bay"` cover the non-stage side, and neither has an inner space. | variant `strip_inner_spaces_delete_only` passes every card on the reference. My R-ST-3 (`…\svc3v\status\test_prop_st3.py`) passes today and on the reference, and fails on that variant (`HTTPException`). | **case designer** |

**Recipe R-ST-3** (pass):
- **Given:** S = status, but `name "Com plete"`. `s_id = S.id`.
- **When:** `result = svc.delete_status(db, status_id=S.id)`.
- **Then:**
  1. returns: `result is True`.
  2. committed: `statuses` rows with `id == s_id`: exactly 0.

**Note, not a finding:** the spec's revision note says "strict xfail on BUG-1220 / BUG-1880", but U-24, U-25, D-16 and D-19 name only BUG-1880, in both Expect and reason. Today nothing protects stage statuses at all (BUG-1220), so a fix of BUG-1880 alone cannot make them pass. The case designer may want the Expect line to read `xfail BUG-1220, BUG-1880`.

### For the coming permissions feature
- **One normalisation helper.** Stage-name normalisation (trim, then lower-case) is now one rule in three places: this service's protection (BUG-1880), BUG-1221's name index, and the order code's stage lookup (BUG-1881). Use one helper so the three cannot drift apart again (the reason for BUG-1880).
- **Who may rename or delete statuses is unspecified.** The protection applies to every caller; the spec has no role rule ("any active member … after BUG-035"). If the permissions feature restricts reference-data edits by role, it is a new rule here.

### Commands run
```
pytest tests/unit/services/test_status_service.py -q -p no:cacheprovider   (x3)   36 passed, 39 xfailed
pytest … -p vfail --runxfail                                                       39 failed, 36 passed; U-24, U-25, D-16, D-19 on Then 1
pytest … -p vplug (VARIANT=ref) --runxfail                                         51 passed, 24 failed (other bugs only)
drive.py (DRIVE_ALL=1) app.services.status_service … variants_r3.py                7 fix variants, diffed against ref
pytest test_prop_st3.py: base PASS · ref PASS · strip_inner_spaces_delete_only FAIL
mutate.py app/services/status_service.py … --lines 30-55     11 mutants · 11 killed · 100%
trace.py (cards 75 · tests 75 · mismatches 0); ruff check (passes)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3v\`. I wrote only this report in the repo. No commit. No process was killed.

## Round 4 — 2026-11-04 (cases revision 5, narrow)

> **Verdict:** PASS
> Tests: 37 passed · 39 xfailed (reproduced ✅, 3 of 3 runs) · coverage unchanged (source unchanged)
> Mutation: not re-run (no source change); rounds 1–3 stand
> Fidelity: **0 unfaithful** among the changed or new cards (SSV-D-20; the xfail reasons of U-24, U-25, D-16, D-19); all 76 traced by script
> Source commit: e48a092 · Cases revision: 5

No new finding. I edited no test and made no commit.

| Variant (on my round-3 reference) | Cards that catch it |
|---|---|
| strip inner spaces on delete only (round-3 R3-1) | D-20 |
| strip inner spaces on both | D-20, U-26 |

- **Reading the tests:** D-20 matches its card (`"Com plete"`, `result is True`, row gone after `db.rollback()`). U-24, U-25, D-16 and D-19 now carry `reason=f"{BUG_1220}; {BUG_1880}"`, matching their new Expect line `xfail BUG-1220, BUG-1880`. They still fail on Then 1 (`DID NOT RAISE HTTPException`) under `--runxfail`.
- **Under my reference:** 52 passed and 24 failed, and the 24 are only the cards of BUG-035, 1218, 1221, 1680 and 1681.
- **Runs:** `37 passed, 39 xfailed` in 3 of 3 runs. Traceability: cards 76 · tests 76 · mismatches 0. `ruff check` passes.
- R3-1 and the reason note are closed.

```
pytest <test file> -q -p no:cacheprovider (x3); pytest … -p vfail --runxfail; drive.py (DRIVE_ALL=1) on the variants above; trace.py; ruff check
```
