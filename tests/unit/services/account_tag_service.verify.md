# Verification — `app/services/account_tag_service.py`

> **Current verdict: PASS** (round 2, 2026-11-04, cases revision 3). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 40 passed · 41 xfailed (39 strict, 2 non-strict: T-07, Y-04) (reproduced ✅) · coverage 96% branch (64 statements, 3 missed: lines 46, 64, 80, unreachable; 12 branches, all covered)
> Mutation: 44 mutants · 41 killed · 3 survived → score 100% (after excluding 3 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 81 unfaithful** (all 81 read by eye against their cards)
> Hand variants: 58 · 50 caught by a pass card · 8 others: 5 gaps (in Findings), 2 bug-path, 1 equivalent
> Source commit: e48a092 · Cases revision: 2; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 81 match their cards: Givens, the commit point, every Then line in order, the xfail markers and reasons. No extra mock, no `try`, no broad `pytest.raises`.
- **The guards hold.** S1, S3 and S4 are guarded on every write and read. Each of these fails a pass card: a dropped commit or re-read, a re-read before the commit, a rollback before any of the five refusals, and a commit, rollback or flush in either list. So do the rule variants: workspace ignored, wrong derivation, 404/403 order, extra fields written on delete, and a recount of `usage_count`.
- **Why NEEDS WORK:** two S2 gaps, both for the case designer. (1) `update_tag` has no failing-refresh card (TC5). An update that swallows a failing re-read, or undoes the change when the re-read fails, passes every card. (2) The failing-commit cards check the error only by `str(exc.value) == "boom"`. TC3/TC4 say the caller gets the same exception object. A write that re-raises a new `RuntimeError("boom")` passes on `update_tag` and `delete_tag`, and on `create_tag` too, unless the error is the `IntegrityError` of C-39. The recipes are below. Each passes today on the real code and fails on its variant.

Written by Claude (all 81 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 81. No `account_tag_service.local-run.json`, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `update_tag` R9 with S2 (TC5); source 61 | No card makes the re-read after a successful commit fail on `update_tag` (only ATV-C-38, on create). S2 says the change then stays saved and the error reaches the caller. | variants `s2_update_swallow_refresh` (re-read error swallowed, tag returned) and `s2_update_undo_on_refresh_fail` (re-read error → `is_active = False`, commit, re-raise) pass all 40 pass cards. | **case designer** |
| 2 | case-missing | S2 / TC3–TC4 "reaches the caller unchanged"; ATV-C-37, U-22, D-07 | The failing-commit cards check only `str(exc.value) == "boom"`. A new exception with the same type and message passes. TC3 says "as the same object". | variants `s2_update_wrap`, `s2_delete_wrap` (`raise RuntimeError(str(e)) from e`) and `s2_create_wrap_same_type` (a new `RuntimeError` with the same args) pass all 40 pass cards. A wrap into `HTTPException` is caught (U-22, C-37 … C-39). | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3v\account_tag\test_prop_at.py`, not in the repo. All 4 pass today on the real code. Each fails on its variants: R-AT-1 on `s2_update_swallow_refresh` (`DID NOT RAISE RuntimeError`) and `s2_update_undo_on_refresh_fail` (`False is True`), and R-AT-2a/b/c on `s2_create_wrap_same_type`, `s2_update_wrap` and `s2_delete_wrap`.

| Recipe | Where | Given and When | Then | Expect |
|---|---|---|---|---|
| R-AT-1 | new card, `update_tag` R9; S2 (TC5) | K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`. When `svc.update_tag(db, tag_id=K1.id, tag_in=AccountTagUpdate(name="Steel"), workspace_id=W1.id)`, inside **failing refresh** | 1. raises: `str(exc.value) == "boom"`. 2. committed: re-read K1: `name == "Steel"`, `is_active is True`. | pass |
| R-AT-2 | one Then line on ATV-C-37, U-22, D-07 (or a new Convention for **failing commit**) | **failing commit** with `boom = RuntimeError("boom")` built before the wrap and given as `side_effect=boom` | new line: raises: `exc.value is boom` | pass |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 21 | L46:12 | `raise` → `pass` in `except HTTPException:` of `create_tag` | equivalent | Unreachable: nothing inside the `try` raises an `HTTPException` (spec Branch map 45–46, FU-2). Coverage confirms line 46 never runs. | — |
| 23 | L64:12 | the same in `update_tag` | equivalent | Unreachable (Branch map 63–64). | — |
| 25 | L80:12 | the same in `delete_tag` | equivalent | Unreachable (Branch map 79–80). | — |

All 41 kills end in a plain failure of a pass card. The 40 pass tests ran on every mutant (`-m "not xfail"`).

## Hand variants
Source edited in memory by my plugin `vplug.py` (the source text is changed, executed, and the methods are copied onto the live class), run against the 40 pass tests. Every variant was applied, and every run reached all 40 tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| s1 (flush for commit; no re-read; re-read before commit) | 7 | 7 | ATV-C-01, C-08, C-20, C-35 … C-38, ATV-U-07, U-18, U-19, U-22, ATV-D-01, D-07 | — |
| s2 (no rollback; swallow; wrap; refresh errors) | 15 | 10 | ATV-C-37 … C-39, ATV-U-22, ATV-D-07 | `s2_update_wrap`, `s2_delete_wrap`, `s2_create_wrap_same_type`, `s2_update_swallow_refresh`, `s2_update_undo_on_refresh_fail` |
| s3 (rollback before each of the 5 refusals) | 5 | 5 | ATV-C-19, ATV-U-01, U-05, ATV-D-02, D-06 | — |
| s4 (lists commit, roll back, flush) | 5 | 5 | ATV-T-06, ATV-Y-05 | — |
| rules: lists (deleted in, recount, `""` dropped, all workspaces) | 4 | 4 | ATV-T-01, T-02, T-03, ATV-Y-01, ATV-U-19, ATV-D-01 | — |
| rules: create (case, spaces, symbols, digits, workspace, message, status, fixed fields) | 11 | 8 | ATV-C-08, C-09, C-19, C-20, C-35, C-36 | `r_create_sent_code_lowered`, `r_create_msg_sent_code`, `r_create_system_from_input` |
| rules: update (403 before 404, workspace, exclude_unset, fields dropped, returns None, unlinks) | 6 | 6 | ATV-U-01, U-06, U-07, U-08, U-10, U-18, U-19 | — |
| rules: delete (workspace, hard unlink, usage reset, returns tag, message) | 5 | 5 | ATV-D-01, D-02, D-05 | — |
| **Total** | **58** | **50** | | **8** (5 findings, 2 bug-path, 1 equivalent) |

### Considered and not listed
| Variant | Why it is not a finding |
|---|---|
| `r_create_sent_code_lowered` | **Bug-path** BUG-1693: today a capitalised sent code is the bug side ("stored as sent"). After the fix the schema refuses it (ATV-C-02), so lower-casing in the service cannot be seen. |
| `r_create_msg_sent_code` (409 names `tag_in.tag_code`) | **Bug-path** BUG-1691: the two differ only for a taken *derived* code, which R7 turns into a suffix with no 409 (ATV-C-22 … C-24). |
| `r_create_system_from_input` (`setdefault`) | **Equivalent:** `AccountTagCreate` drops unknown keys, so `model_dump()` never carries `is_system_tag` (ATV-C-36 shows that the input is ignored). |

## xfail tests
`--runxfail` with my plugin `vfail.py` (failing line → `# Then N`): **41 failed, 40 passed**. Each fails where its card's "Fails today on" says:
- On Then 1: C-02 … C-05, C-33, U-13, U-14, U-20 (`DID NOT RAISE ValidationError`); C-16, C-27 (`DID NOT RAISE IntegrityError`); C-18, C-25, C-26, C-29, C-30, U-03, U-04, U-15 … U-17, D-04 (`DID NOT RAISE HTTPException`); C-10 `'café'`, C-11 `''`, C-14 `'_bolt_'`, C-15 `'কচমল'`; T-08 `100 == 101`; Y-03 (the deleted system tag is listed).
- On a later Then: T-04 on Then 2 (`string_too_short`); T-07, Y-04 on Then 2 (insertion order); C-28 on Then 3 (the code's message); C-34 on Then 2 (`' Bolt '`); U-09 on Then 3 (`'vendor_x'`); U-11 on Then 2 (`tag_code 'renamed'`); U-12 on Then 2 (`'#000000'`); U-21 on Then 2.
- Inside the When, as their cards say "the call raises": C-12 (`DataError` StringDataRightTruncation), C-21 (409 `vendor_x`), C-22, C-23 (409 `steelbar`), C-24 (409 with 50 × `a`).
None fails on a setup or import error.

## Reproduced claims
- **The notes' Result line holds:** `40 passed, 41 xfailed` in 3 of 3 default runs (the coverage run is one of them). No flaky test.
- `--runxfail -rf`: `41 failed, 40 passed`.
- **Mocks:** only the failing commit / refresh wraps, the spies, and the C-18 race simulation that Conventions name. `ruff check` passes.

## Traceability
cases 81 · tests 81 · unmatched: none · marker mismatches: none (40 pass with no marker; 39 `strict=True`; T-07 and Y-04 `strict=False`, as their Expect says). Every reason names its BUG ID, and every BUG ID is in `bugs.md`. Card order, docstrings, `# Then N` and `# [claude] <ID>` all match.

## Limits of this round
I did not build a reference for the intended behaviour. The executor's `refplug_at.py` already passes all 81 with `--runxfail` (notes), and I used it as evidence only, not as my own. So the bug cards were checked for failing on the right line today, not for passing on a fix. The runs were not isolated from the other mutation run on the same database.

## Commands run
```
mutate.py app/services/account_tag_service.py tests/unit/services/test_account_tag_service.py --json <scratch>/account_tag/mut.json
  Mutants: 44 · killed 41 · timeout 0 · survived 3 · score 93%
  SURVIVED #21 L46:12, #23 L64:12, #25 L80:12 raise: raise -> pass
pytest tests/unit/services/test_account_tag_service.py -q -p no:cacheprovider --cov=app.services.account_tag_service --cov-branch --cov-report=term-missing
  40 passed, 41 xfailed · 64 3 12 0 96% (46, 64, 80)
pytest … --runxfail -rf                                         41 failed, 40 passed
pytest … (x2)                                                   40 passed, 41 xfailed (both)
pytest … -p vfail --runxfail                                    failing line per card (above)
drive.py app.services.account_tag_service … variants.py         58 variants (above)
pytest test_prop_at.py (base + 5 variants)                      4 passed on base; each variant fails one proposal
trace.py (cards vs tests vs bugs.md); ruff check (passes); git status app/services (clean)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3v\` (own `COVERAGE_FILE` per run). I wrote only this report in the repo. No commit. No process was killed.

## Fix list
1. **Case designer:** add R-AT-1 as a new card, and R-AT-2's Then line to ATV-C-37, U-22 and D-07 (the wording is in the table above).
2. **Executor,** after 1: implement them, then send the module back for a narrow re-verification.

## Round 2 — 2026-11-04 (cases revision 3, narrow)

> **Verdict:** PASS
> Tests: 41 passed · 41 xfailed (reproduced ✅, 3 of 3 runs) · coverage unchanged (lines 46, 64, 80 unreachable)
> Mutation: not re-run (no source change); round 1 stands at 41 / 41 → 100% (44 mutants, 3 equivalent)
> Fidelity: **0 of 82 unfaithful** (the 4 changed or new cards read by eye; all 82 traced by script)
> Source commit: e48a092 · Cases revision: 3; spec APPROVED, unchanged

Findings 1 and 2 are closed. There is no new finding. I edited no test and made no commit.

| Card | Recipe | Read against card | Variants that now fail it |
|---|---|---|---|
| ATV-U-23 (new) | R-AT-1 | matches (pass; failing refresh, then `committed:` re-read `name == "Steel"`, `is_active is True`) | `s2_update_swallow_refresh`, `s2_update_undo_on_refresh_fail` |
| ATV-C-37 | R-AT-2 | matches (`boom` prebuilt, Then 5 `exc.value is boom`) | `s2_create_wrap_same_type` |
| ATV-U-22 | R-AT-2 | matches | `s2_update_wrap` |
| ATV-D-07 | R-AT-2 | matches | `s2_delete_wrap` |

- **Reproduced:** `41 passed, 41 xfailed` in 3 of 3 runs. `--runxfail`: `41 failed, 41 passed`.
- **Traceability:** cases 82 · tests 82 · unmatched: none · marker mismatches: none. `ruff check` passes.

```
pytest tests/unit/services/test_account_tag_service.py -q -p no:cacheprovider   (x3)   41 passed, 41 xfailed
pytest … --runxfail                                                                     41 failed, 41 passed
drive.py … s2_update_wrap s2_delete_wrap s2_create_wrap_same_type s2_update_swallow_refresh s2_update_undo_on_refresh_fail   all 5 KILLED
trace.py; ruff check
```
