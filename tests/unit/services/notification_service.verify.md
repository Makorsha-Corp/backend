# Verification — `app/services/notification_service.py`

> **Current verdict: PASS** (round 2, 2026-11-04, cases revision 2). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 38 passed · 8 xfail, 7 strict + 1 non-strict (reproduced ✅) · coverage 100% branch (37 statements, 6 branches)
> Mutation: 21 mutants · 21 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Fidelity: **0 of 46 unfaithful** (46 / 46 right; rebuilt by script)
> Hand variants: 31 · 28 caught by a pass card · 3 others: 1 rule gap (in Findings), 2 bug-path
> Source commit: e48a092 · Cases revision: 1; spec APPROVED

## Summary
- **The tests can be trusted as written.** All 46 match their cards.
- **`mark_read`'s transaction is guarded:** a dropped commit, a flush instead of the commit, a count lost, and a rollback or a swallowed error added around the update each fail a pass card (NSV-M-01, M-06, M-11). `list_for_user` committing or rolling back fails NSV-L-05; `fan_out_mentions` committing fails NSV-F-07.
- **Why NEEDS WORK:** `fan_out_mentions` R6 says a database error reaches the caller **without** a rollback (the caller owns the transaction). NSV-F-09 checks the error but not that no rollback ran, so a `try / except: db.rollback(); raise` around the DAO call passes every card. One recipe below.

Written by Claude (all 46 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 46. No `notification_service.local-run.json`, so no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `fan_out_mentions` R6, Errors | Only the success path checks "no commit, no rollback" (NSV-F-07, spies). On the error path NSV-F-09 asserts the `IntegrityError` and "nothing written", which a rollback also satisfies. | variant `f_r6_rollback_on_error` (DAO call wrapped in `try / except Exception: db.rollback(); raise`) fails no card. | **case designer** |

No fidelity finding.

### Scratch card that closes the gap
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v\prop\test_prop_svc1v.py` (`test_r_nt_1`), not in the repo. It passes today and on my reference, and fails on the variant.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-NT-1 | new card (or two Then lines on NSV-F-09), `fan_out_mentions` R6, Errors | No notification exists. When `svc.fan_out_mentions(db, workspace_id=W1.id, actor_user_id=MISSING, mentioned_user_ids=[UA.id], entity_type="purchase_order", entity_id=12, source_id=77)`, with **spies**, inside the savepoint wrap of `raises:` | 1. raises: `IntegrityError`. 2. raises: `exc.value.orig.pgcode == "23503"`. 3. mock called: `cm.call_count == 0`. 4. mock called: `rb.call_count == 0`. | pass | `f_r6_rollback_on_error` |

The spies sit outside `pytest.raises` and the savepoint wrap (`with spies(db) as (cm, rb): with pytest.raises(IntegrityError) as exc: with db.begin_nested(): …`); the savepoint's own rollback does not go through `db.rollback`, so today `rb.call_count == 0` (verified).

## Surviving mutants
None. All 21 kills end in a plain `N failed`.

**Guard.** `drive.py muts` re-ran each mutant without `-x`: every run reached all 38 pass tests, no collection or setup error, outcome equal to `mutate.py`'s.

## Hand variants
On my reference through `plug\vplug.py`, `--runxfail`, NSV-L-06, M-07, M-08 deselected (not served). Every edit applied once; every run reached all 43 served tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| r1 (preview cut; members; list args; `ids`; fan-out fields) | 14 | 14 | NSV-H-01 …, NSV-A-01 … A-03, NSV-L-01 … L-04, NSV-M-01, M-03, NSV-F-01 … F-03, F-05 | — |
| r2 (no read without token; list commit / rollback; mark commit; membership check) | 6 | 6 | NSV-H-05, NSV-L-05, NSV-M-01, M-06, NSV-F-03, F-08 … | — |
| r3 (every token, `@`; dedupe) | 3 | 3 | NSV-H-02, H-06, H-07, H-08, H-12, H-16, NSV-F-05 | — |
| r4 (fallback text; mark rollback / swallow on error; actor) | 4 | 3 | NSV-H-08, NSV-M-06, M-11 | `f_r4_actor_notified` |
| r5 (workspace scope) | 1 | 0 | — | `h_r5_scope_ignored` |
| r6 (fan-out commits; rolls back on error) | 2 | 1 | NSV-F-07 | `f_r6_rollback_on_error` |
| r8 (preview writes) | 1 | 1 | NSV-H-17 | — |
| **Total** | **31** | **28** | | **3** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `h_r5_scope_ignored` | **Bug-path** BUG-1534: only NSV-H-09, H-10. |
| `f_r4_actor_notified` | **Bug-path** BUG-1535: only NSV-F-04. |

## xfail tests against the reference
Reference: tokens take ASCII `0-9` only; `humanize_mention_preview` takes `workspace_id` and names only profiles with a membership in it; `fan_out_mentions` skips the actor. **One deviation from the spec:** my `workspace_id` is keyword-only with default `None` (today's lookup when absent), so the 13 preview cards that do not pass it yet still run; the spec makes it required. Not served: NSV-L-06 (DAO order, non-strict), NSV-M-07, M-08 (DAO bugs). `--runxfail` on the reference: 43 passed, 3 failed (exactly those). **Alarm:** with the markers on, NSV-H-09 … H-11, H-14 and F-04 XPASS(strict) and fail.

Fails today, from `failmap.py`: H-09 … H-11 in the When, `TypeError` (no `workspace_id`), as their cards say; H-14, F-04, M-07 on Then 1; M-08 and L-06 (non-strict) on Then 2. Each is the line its card names.

## Reproduced claims
- **Result line of the notes holds:** `38 passed, 8 xfailed` in 4 of 4 default runs, the coverage run among them. No flaky test.
- `--runxfail -rf`: `8 failed, 38 passed`.
- **Mocks:** only the failing commit wrap, the spies, the NSV-M-08 clock patch and the NSV-M-11 failing update the Conventions name. No `try`, no `if`, no broad `pytest.raises`. NSV-H-17 names the recorded writes `writes` (helper `writes_of`), the Conventions' `written`: the same statements, only the name differs.

## Traceability
cases 46 (no NSV-M-05 exists, as the notes say) · tests 46 · unmatched: none · marker mismatches: none. Order, docstrings, `# Then N`, `# [claude] <ID>` match; every BUG ID is in `bugs.md`; `ruff check` passes. `cmp.py`: 0 reports; selftest 2876 of 2880 (two misses here: a deleted membership line inside NSV-A-03's loop, whose literals my script also finds in helpers; the card's `len(result) == 103` would still fail it).

## Limits of this round
The reference and the variants are mine; runs were not isolated from other agents; HTTP and the live stream not exercised.

## Commands run
```
mutate.py app/services/notification_service.py tests/unit/services/test_notification_service.py --timeout 300 --json <scratch>/res/mut_notification.json
  Mutants: 21 · killed 21 · timeout 0 · survived 0 · score 100%
pytest tests/unit/services/test_notification_service.py -q -p no:cacheprovider --cov=app.services.notification_service --cov-branch --cov-report=term-missing
  38 passed, 8 xfailed · 37 0 6 0 100%
pytest … --runxfail -rf                                                     8 failed, 38 passed
drive.py bases / muts / vars; post.py; propdrive.py (R-NT-1); cmp.py (+ --selftest); ruff check; git diff --stat -- app/services (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1v\`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Case designer:** add R-NT-1 (Given, When and Then written out above).
2. **Executor,** after 1: implement it and send back for re-verification.

## Round 2 — 2026-11-04 (cases revision 2, narrow)

> **Verdict:** PASS
> Tests: 39 passed · 8 xfail (reproduced ✅) · coverage 100% branch (37 statements, 6 branches)
> Mutation: not re-run; round 1 stands at 21 / 21 → 100% (21 mutants)
> Fidelity: **0 of 47 unfaithful** (the new card read by eye; all 47 rebuilt by script)
> Hand variants: 31 · 29 caught by a pass card · the 2 others are the bug paths of round 1
> Source commit: e48a092 · Cases revision: 2; spec APPROVED, unchanged

Finding 1 is closed. No new rule gap. No test edited by me, no commit.

| Card | Recipe | Read against card | Fails on |
|---|---|---|---|
| NSV-F-10 | R-NT-1 | matches: spies outermost, then `pytest.raises(IntegrityError)`, then `db.begin_nested()`; pgcode `23503`, `cm.call_count == 0`, `rb.call_count == 0` | `f_r6_rollback_on_error` |

- **Reproduced:** `39 passed, 8 xfailed` in 4 of 4 default runs; `--runxfail`: `8 failed, 39 passed`. Reference `--runxfail`: 44 passed, the same 3 unserved. Every variant run reached all 44 served tests.
- **Traceability:** cases 47 · tests 47 · unmatched: none · marker mismatches: none; `cmp.py` 0 reports; `ruff check` passes.

```
repro.py notification; drive.py bases notification; drive.py vars notification; post.py; cmp.py notification
```
