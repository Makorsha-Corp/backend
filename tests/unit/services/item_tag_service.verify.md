# Verification — `app/services/item_tag_service.py`

> **Current verdict: PASS** (round 2, 2026-11-04, cases revision 2). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 37 passed + 1 XPASS (ITS-T-08, non-strict, as its card allows) · 26 xfailed; 27 xfail cards, 25 strict + 2 non-strict (reproduced ✅) · coverage 96% (69 statements, 3 missed: lines 53, 71, 87, unreachable; 14 branches, all covered)
> Mutation: 45 mutants · 42 killed · 3 survived → score 100% (after excluding 3 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 64 unfaithful** (64 / 64 right; read by eye and rebuilt by script)
> Hand variants: 70 · 50 caught by a pass card · 20 others: 4 rule gaps (in Findings), 13 bug-path, 3 equivalent / no rule
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 64 match their cards; I read every one by eye against its card, and my script rebuilt them too.
- **S1 and S2 are guarded on every write:** a dropped commit, a dropped rollback, a swallowed or wrapped error, a dropped re-read and a re-read before the commit each fail a pass card on `create_tag`, `update_tag`, `delete_tag`. Both lists are caught committing or rolling back (S4), and `get_tags` flushing its live count (R3).
- **Why NEEDS WORK:** S3 (a refusal does **not** roll back) is checked on one refusal per write, and three refusals are left: `delete_tag`'s 403 today, and the name 409 of BUG-1531 on create and on rename once it exists. A rollback added before any of them passes every card. Also R8's message with the **trimmed** name has no card. Four recipes for the case designer below.

Written by Claude (all 64 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 64. No `item_tag_service.local-run.json`, so no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `delete_tag` R3 with S3 | ITS-D-05 (the 403) has no uncommitted extra row, so a rollback before the 403 passes. S3 is checked on delete only through the 404 (ITS-D-02). | variant `delete_s3_rollback_on_403` fails no card. | **case designer** |
| 2 | case-missing | `create_tag` R8 with S3 [BUG-1531] | ITS-C-18 … C-20 (the name 409) have no uncommitted extra row. Once BUG-1531 is fixed, a rollback before that 409 passes every card. | variant `create_s3_rollback_on_name_409` fails no card, also with `--runxfail` on the reference. | **case designer** |
| 3 | case-missing | `update_tag` R6 with R9 / S3 [BUG-1531] | The same for the rename's name 409 (ITS-U-11). | variant `update_s3_rollback_on_name_409` fails no card. | **case designer** |
| 4 | case-missing | `create_tag` R8 [BUG-1531] | R8 says the 409 names "the trimmed submitted name". Every name card sends a name without outer spaces, so a message with the untrimmed name passes. | variant `create_r8_untrimmed_message` fails no card. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v\prop\test_prop_svc1v.py`, not in the repo. Each passes on my reference with `--runxfail` and fails on its variant. R-IT-1 passes today; R-IT-2 … R-IT-4 fail today on Then 1 (`DID NOT RAISE HTTPException`), as their Expect says.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-IT-1 | new card, `delete_tag` R3, S3 | KS = system tag, `name "Raw Material"`, `tag_code "raw_material"`. X = tag, `name "Extra"`, `tag_code "extra"` (after the commit point). When `svc.delete_tag(db, tag_id=KS.id, workspace_id=W1.id)` | 1. raises: `HTTPException`. 2. raises: `exc.value.status_code == 403`. 3. count: `item_tags` rows with `tag_code == "extra"`: exactly 1. | pass | `delete_s3_rollback_on_403` |
| R-IT-2 | new card, `create_tag` R8, R11, S3 [BUG-1531] | K1 = tag, `name "Paint"`, `tag_code "paint1"`. X = tag, `name "Extra"`, `tag_code "extra"` (after the commit point). When `svc.create_tag(db, tag_in=ItemTagCreate(name="PAINT", tag_code="paint2"), workspace_id=W1.id, user_id=U1.id)` | 1. raises: `HTTPException`. 2. raises: `exc.value.status_code == 409`. 3. count: `item_tags` rows with `tag_code == "extra"`: exactly 1. | xfail BUG-1531 · Fails today on: Then 1 (no error: names are not checked) | `create_s3_rollback_on_name_409` |
| R-IT-3 | new card, `update_tag` R6, R9, S3 [BUG-1531] | K1 = tag, `name "Paint"`, `tag_code "paint"`. K2 = tag, `name "Bolt"`, `tag_code "bolt"`. X = tag, `name "Extra"`, `tag_code "extra"` (after the commit point). When `svc.update_tag(db, tag_id=K2.id, tag_in=ItemTagUpdate(name="paint"), workspace_id=W1.id)` | 1. raises: `HTTPException`. 2. raises: `exc.value.status_code == 409`. 3. count: `item_tags` rows with `tag_code == "extra"`: exactly 1. | xfail BUG-1531 · Fails today on: Then 1 (no error: the rename is stored) | `update_s3_rollback_on_name_409` |
| R-IT-4 | new card, `create_tag` R8 [BUG-1531], Errors row 1 | K1 = tag, `name "Paint"`, `tag_code "paint1"`. When `svc.create_tag(db, tag_in=ItemTagCreate(name=" PAINT ", tag_code="paint2"), workspace_id=W1.id, user_id=U1.id)` | 1. raises: `HTTPException`. 2. raises: `exc.value.status_code == 409`. 3. raises: `exc.value.detail == "Tag with name 'PAINT' already exists"`. 4. nothing written. | xfail BUG-1531 · Fails today on: Then 1 (no error: names are not checked) | `create_r8_untrimmed_message` |

R-IT-2 and R-IT-3 could instead be one extra Given row and one Then line on ITS-C-18 and ITS-U-11; the case designer chooses.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 21 | L53:12 | `raise` → `pass` in `except HTTPException:` of `create_tag` | equivalent | Unreachable: nothing inside the `try` raises an `HTTPException` (spec Branch map 52–53, FU-3), so the clause never runs. Coverage confirms line 53 never runs. | — |
| 23 | L71:12 | the same in `update_tag` | equivalent | Unreachable (Branch map 70–71). | — |
| 25 | L87:12 | the same in `delete_tag` | equivalent | Unreachable (Branch map 86–87). | — |

The 42 kills end in a plain `N failed`. **Guard.** `drive.py muts` re-ran all 45 mutants without `-x`: every run reached all 38 pass tests (37 + ITS-T-08), no collection or setup error, outcome equal to `mutate.py`'s.

## Hand variants
On my reference through `plug\vplug.py`, `--runxfail`, the 9 unserved cards deselected. Every edit applied once; every run reached all 55 served tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| s1 (drop commit, flush instead) | 4 | 4 | ITS-C-01, C-02, C-12, C-24 … C-27, ITS-D-01 | — |
| s2 (drop rollback, swallow, wrap, re-read) | 11 | 11 | ITS-C-24, C-26, C-27, C-28, ITS-U-07, U-17, ITS-D-06 | — |
| s3 (rollback before a refusal) | 5 | 2 | ITS-C-11, ITS-U-05 | `delete_s3_rollback_on_403`, `create_s3_rollback_on_name_409`, `update_s3_rollback_on_name_409` |
| s4 (lists commit, roll back, flush) | 5 | 4 | ITS-T-02 … T-04, ITS-Y-03 | `get_system_tags_s4_flush` |
| r1 (workspace ignored, code ignored) | 3 | 3 | ITS-C-01, C-11, C-28, ITS-U-01, U-06, ITS-D-02 | — |
| r2 (derivation; live count; deleted found) | 9 | 7 | ITS-C-02, C-03, ITS-T-02, T-03, ITS-Y-02 | `update_r2_deleted_found`, `delete_r2_deleted_found` |
| r3 (cut at 50, fallback, trim; 403s) | 8 | 5 | ITS-C-07, ITS-T-03, ITS-U-05, ITS-D-05 | `create_r3_cut_51`, `create_r3_empty_fallback`, `create_r3_untrimmed` |
| r4 (code check, other workspace, detail; update fields; delete fields) | 9 | 9 | ITS-C-11, C-12, ITS-U-07, ITS-D-01 | — |
| r5 (deleted code blocks; nulls dropped) | 2 | 0 | — | `create_r5_deleted_blocks`, `update_r5_nulls_dropped` |
| r6 (own name blocks; no name check on rename) | 2 | 1 | ITS-U-12 | `update_r6_no_name_check` |
| r7 (suffix; trim on rename) | 4 | 1 | ITS-C-11 | `create_r7_no_suffix`, `create_r7_suffix_start_3`, `update_r7_untrimmed` |
| r8 (name check, message; `is_active` ignored) | 3 | 1 | ITS-U-15 | `create_r8_no_name_check`, `create_r8_untrimmed_message` |
| r9 (stored untrimmed) | 1 | 0 | — | `create_r9_untrimmed_stored` |
| r10 (fixed fields) | 4 | 2 | ITS-C-24 … | `create_r10_system_from_input`, `create_r10_usage_from_input` |
| **Total** | **70** | **50** | | **20** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `create_r3_cut_51`, `create_r3_empty_fallback`, `create_r3_untrimmed` | **Bug-path** BUG-1532 / BUG-1526: ITS-C-06, C-05, C-09, C-08. (ITS-C-07, the 50 kept whole, is the pass side.) |
| `create_r5_deleted_blocks` | **Bug-path** BUG-1527: ITS-C-13. |
| `create_r7_no_suffix`, `create_r7_suffix_start_3` | **Bug-path** BUG-1533: ITS-C-16, C-17. |
| `create_r8_no_name_check`, `update_r6_no_name_check` | **Bug-path** BUG-1531: ITS-C-18 … C-20, ITS-U-11. |
| `create_r9_untrimmed_stored`, `update_r7_untrimmed` | **Bug-path** BUG-1526: ITS-C-08, ITS-U-14. |
| `update_r2_deleted_found`, `delete_r2_deleted_found` | **Bug-path** BUG-1529: ITS-U-03, U-04, ITS-D-04. |
| `update_r5_nulls_dropped` | **Bug-path** BUG-1530: ITS-U-09. |
| `create_r10_system_from_input`, `create_r10_usage_from_input` | **Equivalent:** `ItemTagCreate` has neither field and drops unknown keys, so `model_dump()` never carries them (ITS-C-25 shows the input is ignored). |
| `get_system_tags_s4_flush` | **No rule:** S4 says the lists neither commit nor roll back; a flush is neither, and `get_system_tags` changes no object (unlike `get_tags` R3, whose flush is caught by ITS-T-03). |

## xfail tests against the reference
Reference: `create_tag` trims the name, refuses a live name (case-insensitive, trimmed) with the 409 of R8, derives the code from ASCII `a-z0-9_` cut to 50 with `tag` as fallback, lets a deleted tag's code be reused, suffixes a taken derived code `_2`, `_3`…; `update_tag` refuses a deleted tag (404), applies explicit nulls, trims and checks a new name; `delete_tag` refuses a deleted tag. Not served: ITS-C-10, U-10, U-13 (schema refusals), ITS-T-06, T-07 (response schema), ITS-C-14, C-23, C-29 (partial unique indexes: no DDL on the shared database), ITS-Y-04 (DAO order). `--runxfail` on the reference: 55 passed, 9 failed (exactly those). **Alarm:** with the markers on, the 17 served strict cards XPASS(strict) and fail.

Fails today, from `failmap.py`, each on the line its card names. Three fail inside the When: ITS-C-13, C-16, C-17 raise the 409 their "Fails today on: Then 1 (409 …)" line quotes — the same failure, named by the first Then line it blocks. ITS-T-08 (non-strict) passes under `--runxfail` on this database's collation, as its card allows.

## Reproduced claims
- **Result line of the notes holds:** `37 passed, 26 xfailed, 1 xpassed` in 4 of 4 default runs, the coverage run among them. No flaky test.
- `--runxfail -rf`: `26 failed, 38 passed` (ITS-T-08 among the passes).
- **Mocks:** only the failing commit / refresh wraps, the spies and the ITS-C-29 race simulation the Conventions name. No `try`, no `if`, no broad `pytest.raises`.

## Traceability
cases 64 · tests 64 · unmatched: none · marker mismatches: none. Order, docstrings, `# Then N`, `# [claude] <ID>` match; every BUG ID is in `bugs.md`; `ruff check` passes. `cmp.py`: 0 reports; selftest 2876 of 2880 (see `department_service.verify.md`).

## Limits of this round
The reference and the variants are mine; runs were not isolated from other agents; the index cards were not served (no DDL); HTTP and a real race not exercised.

## Commands run
```
mutate.py app/services/item_tag_service.py tests/unit/services/test_item_tag_service.py --timeout 300 --json <scratch>/res/mut_item_tag.json
  Mutants: 45 · killed 42 · timeout 0 · survived 3 · score 93%
  SURVIVED #21 L53:12, #23 L71:12, #25 L87:12 raise: raise -> pass
pytest tests/unit/services/test_item_tag_service.py -q -p no:cacheprovider --cov=app.services.item_tag_service --cov-branch --cov-report=term-missing
  37 passed, 26 xfailed, 1 xpassed · 69 3 14 0 96% (53, 71, 87)
pytest … --runxfail -rf                                                     26 failed, 38 passed
drive.py bases / muts / vars; post.py; propdrive.py (R-IT-1 … R-IT-4); cmp.py (+ --selftest); ruff check; git diff --stat -- app/services (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add R-IT-1 … R-IT-4 (Givens and Thens written out above).
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-04 (cases revision 2, narrow)

> **Verdict:** PASS
> Tests: 38 passed + 1 XPASS (ITS-T-08, allowed) · 29 xfailed; 30 xfail cards (reproduced ✅) · coverage 96% (69 statements; lines 53, 71, 87 unreachable; 14 branches, all covered)
> Mutation: not re-run; round 1 stands at 42 / 42 → 100% (45 mutants, 3 equivalent)
> Fidelity: **0 of 68 unfaithful** (the 4 new read by eye; all 68 rebuilt by script)
> Hand variants: 70 · 51 caught by a pass card · every gap variant now fails its new card; the 19 others are the bug paths, equivalents and no-rule variant of round 1
> Source commit: e48a092 · Cases revision: 2; spec APPROVED, unchanged

Findings 1–4 are closed. No new rule gap. No test edited by me, no commit.

| Card | Recipe | Read against card | Fails on (reference, `--runxfail`) |
|---|---|---|---|
| ITS-D-07 | R-IT-1 | matches (pass) | `delete_s3_rollback_on_403` |
| ITS-C-30 | R-IT-2 | matches (strict xfail BUG-1531) | `create_s3_rollback_on_name_409` |
| ITS-U-18 | R-IT-3 | matches (strict xfail BUG-1531) | `update_s3_rollback_on_name_409` |
| ITS-C-31 | R-IT-4 | matches (strict xfail BUG-1531) | `create_r8_untrimmed_message` |

- **Reproduced:** `38 passed, 29 xfailed, 1 xpassed` in 4 of 4 default runs; `--runxfail`: `29 failed, 39 passed`. ITS-C-30, C-31 and U-18 fail today on Then 1 (`DID NOT RAISE HTTPException`), as their cards say. Reference `--runxfail`: 59 passed, the same 9 unserved; with the markers on, 20 strict cards XPASS(strict). Every variant run reached all 59 served tests.
- **Traceability:** cases 68 · tests 68 · unmatched: none · marker mismatches: none; `cmp.py` 0 reports; `ruff check` passes.
- **Note, not a finding of this module:** the ID `ITS-D-07` is also used in `tests/unit/services/item_service.cases.md` (`delete_item`, BUG-948): `item_service` and `item_tag_service` share the `ITS` prefix. IDs are per file, so nothing breaks here, but a search by ID finds both.

```
repro.py item_tag; drive.py bases item_tag; drive.py vars item_tag; post.py; cmp.py item_tag
```
