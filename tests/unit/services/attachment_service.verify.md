# Verification — `app/services/attachment_service.py`

> **Verdict:** NEEDS WORK (case designer: 4 findings; describer: 2 spec gaps; nothing for the executor)
> **Current verdict (Round 2):** PASS. Cases Rev 4 and spec R3b / R4a close all six round-1 findings. 69 passed · 41 xfailed, the same in 3 runs; 100% branch. Mutation score 100% (22 / 22, after 4 equivalent). Every round-1 survivor now fails a card. See Round 2.
> Tests: 63 passed · 36 xfailed (reproduced ✅, 3 identical runs) · coverage 100% branch (64 statements, 4 branches)
> Mutation: 26 mutants · 20 killed · 6 survived → score 90.9% (20 / 22, after excluding 4 equivalent, 0 dead, 0 bug-path)
> Hand variants: 48 · 40 killed · 8 survived (1 invalid data, 5 → case designer, 2 → describer)
> Source commit: e48a092 · Cases revision: 3

## Summary
The tests match their cards. Traceability is clean: 99 cards and 99 tests, every marker matches its card, and every BUG ID exists in `bugs.md`. Every Then line is asserted in the card's order with the card's values. There are no extra mocks and no swallowed failures. With `--runxfail`, all 36 strict xfails fail on the Then line their card names. Three plain runs give the same result, so nothing is flaky.

I wrote my own reference implementation of the intended behaviour (not the executor's `ref_attsvc.py`). It passes all 99 tests with `--runxfail`, so the bug cards hold for a correct implementation.

The service's own work is well guarded. Variants that broke HR-13 commit-then-raise, unrelated pending rows, rollback / no rollback, TC6 reads, passing the caller down, error mapping, the BUG-2201 batch read and the BUG-2200 record check (W0 / W2 rows, explicit ids) were all killed.

The gaps are in the cards and the spec:
- The post-commit Cloudinary delete of BUG-2202 is checked only for a `ready` attachment whose delete succeeds.
- The BUG-2200 list check is tested on 4 of the 11 record types.
- The PDF page read has no TC6 card for the error path.
- Two default parameters are not pinned.
- The spec leaves two outcomes open: what the no-`public_id` refusal does to unrelated pending changes, and whether the file is still deleted when the re-read after the commit fails.

No new bug.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `delete_attachment` R4 [BUG-2202] with manager R5–R7 (BUG-2099, BUG-2100); D-02, D-08 … D-11 | Every delete card uses a `ready` attachment with a `public_id`, and `destroy_resource` always succeeds. After the BUG-2202 fix the delete runs after the commit, outside the manager's `delete_attachment`, so the manager's cards no longer see which state is deleted or that an error is swallowed. Three things go unchecked. (a) A pending or failed attachment with a `public_id` deletes its file (BUG-2099). (b) An attachment with no `public_id` makes no call. (c) A `destroy_resource` that raises after the commit is swallowed: the delete stays saved and the call answers normally, with BUG-2100's WARNING. Suggested cards: a pending delete with `dr.call_count == 1` after the commit (strict xfail BUG-2099); `public_id None` with `dr.called is False`; `dr side_effect = RuntimeError` with a returned result and the row committed as deleted. | variants `del_ready_only`, `del_any_pid`, `del_error_propagates`: 99 passed each | case designer |
| 2 | case-missing | `list_attachments` R1a [BUG-2200]; L-12 … L-18 | Spec R1a names "a soft-deleted project / machine / **work order**". The list's record check is tested only on `machine`, `project`, `project_component` and `support_ticket` (plus `scratch`). A check that skips every other type (work, purchase, sales, expense and transfer orders, item, account invoice) passes. Add at least: a deleted work order (strict xfail BUG-2200), and an unknown id of a type without soft delete, e.g. `purchase_order` MISSING. This is not delegated to the manager's PR-1 matrix: the spec makes the list check this service's own, and does not require it to reuse the manager's helper. | variant `list_check_few_types`: 99 passed | case designer |
| 3 | case-missing | `get_pdf_page_image` R3 (TC6); PG-02 … PG-06 | Only the success path has a TC6 card (PG-07). No error card holds a pending edit or spies on `rollback`, unlike `get_attachment` (G-10) and the list (L-10). A service that rolls back on a page or "not ready" error passes. Add a card like G-10: pending edit, spies, `page=0`, then `rb.called is False`, `cm.called is False`, and `F9 in db.dirty`. | variant `pdf_rollback_on_error`: 99 passed | case designer |
| 4 | case-missing | `list_attachments` default `skip=0` (L-05); `get_pdf_page_image` default `width=1600` (PG-01) | L-05 builds 101 items, so `skip` defaulting to 1 still returns 100 items. PG-01 checks only `public_id` and `fmt` of the `build_signed_delivery_url` call, so the width that reaches the transformation is never seen. Fix: in L-05 use 100 items, or check that the newest item is in the page. In PG-01 add `kw(bsu)["transformation"] == [{"page": 2, "fetch_format": "jpg", "quality": "auto:good", "width": 1600, "crop": "limit", "density": 200}]`. Low priority: the endpoint always passes both values. | mutants #11 (L109), #15 (L156) | case designer |
| 5 | spec-gap | `confirm_upload` R3 vs R3a / R4; CF-10 | R3 says that "a refusal that wrote nothing (no `public_id`) commits nothing". R3a says HR-13 commits the session as it stands. R4's roll-back list does not name this refusal. So nothing states what happens to an unrelated pending change on this path: kept and committed, or discarded (TC3)? The cards cannot tell either: CF-10 has no pending X. The simplest fix commits on every `AttachmentConfirmError` (my reference and the executor's both do). Decide which applies, then add a CF-10 twin with "pending X". | variant `cf_nopid_rollback` (rolls back only on this refusal): 99 passed, same as the reference that commits | describer (fill-gaps), then case designer |
| 6 | spec-gap | `delete_attachment` R3 (TC5) + R4 [BUG-2202]; D-11 | R4 says only "after the commit succeeded". It does not say whether the Cloudinary delete must still run when the re-read or the response after the commit fails (TC5: the delete stays saved). If it does not run, the file is left with no live row naming it (the BUG-2099 pattern `orphaned-external-file`). D-11 does not look at `dr`. | variant `del_after_refresh` (destroy after `db.refresh`): 99 passed | describer (fill-gaps), then case designer |

Unfaithful tests: none. Cosmetic, optional, for the executor: the test module docstring says "revision 2", but the cases are at revision 3 (the notes record the revision-3 changes).

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 5–8 | 198–201 | `__all__` entries → `""` | equivalent | `__all__` only affects `from app.services.attachment_service import *`, which nothing in the repo does. Every import is by name, and the names stay bound. The spec lists `__all__` as "Not specified" (no logic). | — |
| 11 | 109 | `skip: int = 0` → `1` | case-missing | Finding 4 (L-05 has 101 items). | case designer |
| 15 | 156 | `width: int = 1600` → `1601` | case-missing | Finding 4 (PG-01 does not check the transformation). | case designer |

## Hand variants
These are my own in-process plugins: `attsvcv/att/plug/v_att.py`, scratch only. `AV=base` is an independent reference for the intended behaviour, written from this spec and the attachment manager's PR-1 … PR-5. It covers BUG-2090, 1870, 1950, 2091, 2096, 2097, 2099, 2100, 1434, 2095, 2200, 2201 and 2202. It passes **99 / 99** with `--runxfail`.

Each other variant adds one defect to the reference. The runs use `--runxfail`, so the bug cards take part.

| Variant (one defect) | Failing tests | Result |
|---|---|---|
| **Commit then raise (HR-13, BUG-2095)** | | |
| rollback on `AttachmentConfirmError` (today's behaviour) | CF-06, CF-08, CF-09, CF-21 | killed |
| commit then raise on **every** error (not-found too) | CF-11 | killed |
| failure record committed, but unrelated pending rows discarded (rollback, then re-write and commit) | CF-09, CF-21 | killed |
| commit with no rollback when that commit fails | CF-09 | killed |
| failing commit on that path answers the original confirm error | CF-09 | killed |
| commit, then return the response instead of raising | CF-05 … CF-08, CF-10, CF-21 (6) | killed |
| **no-`public_id` refusal rolls back instead of committing** | 0 | **survived → Finding 5** |
| **Rollback (TC3) / no rollback on reads (TC6)** | | |
| sign: no rollback on error | S-05, S-06 | killed |
| sign: commit before `build_sign_response` | S-05, S-06 | killed |
| sign: no commit | S-01, S-02, S-07, S-08, S-14 | killed |
| confirm: no rollback on the non-HR-13 errors | CF-11 | killed |
| delete: no rollback on any error / not on the not-found path only | D-03, D-07 / D-03 | killed |
| list: rollback on error / commit on success | L-10 / L-09 | killed |
| get: rollback on error / rollback on success | G-10 / G-09 | killed |
| PDF page: commit on success | PG-07 | killed |
| **PDF page: rollback on error** | 0 | **survived → Finding 3** |
| **Cloudinary delete before commit (BUG-2202)** | | |
| destroy before the commit (today's behaviour) | D-09, D-10 | killed |
| destroy in a `finally`, so it also runs when the commit fails | D-09 | killed |
| **destroy after the re-read (skipped when the refresh fails)** | 0 | **survived → Finding 6** |
| **destroy only for `ready` / also with no `public_id` / error not swallowed** | 0 / 0 / 0 | **survived → Finding 1** |
| **Caller passed down** | | |
| confirm: `performed_by` dropped (None passed) | CF-02, CF-06, CF-08, CF-18, CF-19, CF-20 | killed |
| confirm: PR-3 judged for the uploader, not the caller | CF-18, CF-19 | killed |
| delete: `deleted_by` dropped / PR-3 judged for the uploader | 6 (D-01, D-07, D-11 … D-14) / D-12, D-13 | killed |
| list: `user_id` not passed on (None) | L-20, L-21, L-24 | killed |
| get: `user_id` ignored | G-11 … G-14 | killed |
| PDF page: `user_id` not passed to the manager | PG-08, PG-09, PG-10 | killed |
| PR-2 off everywhere | 16 | killed |
| **Wrong error mapping** | | |
| get: not found raised as `AttachmentLimitError` | G-04 … G-08, G-10 | killed |
| delete: `None` → `ValueError` | D-03 … D-06, D-12, D-13 | killed |
| list: record refusal worded `Attachment <id> not found.` | L-12 … L-18, L-20 … L-22 (10) | killed |
| **One links query per item (BUG-2201)** | | |
| `to_response` per item (today's behaviour) | L-11 | killed |
| batched read, links grouped wrongly (every link on every item) | L-01, L-11 | killed |
| batched read without the workspace filter | 0 | invalid data: a link filed under another workspace for a W1 attachment is cross-workspace data, which no writer produces (HR-16). Info only. |
| **List check on the parent record (BUG-2200)** | | |
| no check (today's behaviour) | L-12 … L-18, L-20 … L-22 (10) | killed |
| record looked up without the workspace filter (W0 / W2 rows) | L-16, L-17 | killed |
| record looked up in `machines` whatever the type (explicit id `XID(4)`) | L-18, L-23, L-24 | killed |
| soft delete ignored / component's deleted project ignored | L-13, L-14 / L-15 | killed |
| check after the read (signed URLs built first) | L-13, L-20 | killed |
| `scratch` refused | L-19 | killed |
| PR-1 only (no visibility) | L-20, L-21, L-22 | killed |
| **check only for machine / project / component / ticket** | 0 | **survived → Finding 2** |
| **Missing row lock (BUG-2139 pattern)** | — | not applicable: this service takes no lock. The confirm lock is the manager's BUG-2094 (HR-10, manager cases), and the cards state "Race simulations: None". Delegated. |

## Traceability
cards 99 · tests 99 · unmatched: none · tests without a case ID: none · marker mismatches: none.
- 63 pass cards carry no marker.
- 36 xfail cards carry `strict=True`, and each reason names the card's BUG ID. BUG-1434, 1870, 1950, 2090, 2091, 2095, 2096, 2097, 2200, 2201 and 2202 are all in `bugs.md`.
- The `# Then N` blocks match every card's Then count.
- With `--runxfail`, 36 of 36 fail inside the Then block named by "Fails today on".
  - 26 raise in Then 1: either `DID NOT RAISE`, or a `TypeError` for the missing `user_id`.
  - CF-06 fails on Then 3 and CF-08 on Then 2 (`'pending' == 'failed'`).
  - CF-09 Then 1 gets the confirm error; CF-15 Then 1 gets the wrapped error.
  - CF-21 Then 4: X was discarded.
  - L-08 Then 2: count 2.
  - L-11 Then 2: 7 statements.
  - D-09 Then 3: `dr.called`. D-10 Then 3: the order is `["dr", "commit"]`.

## For the coming features
- **Permissions:** the service passes the caller down as follows.
  - Passed today: `performed_by` on confirm, `deleted_by` on delete, and the `user` on sign.
  - Missing today: list, get and PDF page take no caller (BUG-1870, BUG-1950, BUG-2091, needed by the endpoint, FU-1 (b)).
  - The variants show the cards pin the caller-dependent paths, and that PR-3 is judged for the caller, not the uploader.
  - Once Finding 2 is closed, the list's record check (BUG-2200) should share the manager's PR-1 / PR-2 helper rather than keep a copy. One helper per record type would also serve the markup and mobile services.
  - `scratch` stays open to every member (manager Q14 → `docs/future/permissions.md`).
- **Notifications:** this service emits nothing itself. "Attached …" / "Removed …" activity entries come from the manager inside the same commit. A notification hook belongs **after** `_commit_transaction`, next to the post-commit Cloudinary delete of BUG-2202. It must not fire on the HR-13 failure commit of BUG-2095, which records a failure, not an attachment.
- **Payments:** nothing here. Two patterns should not be copied blindly into a payment flow. HR-13 commits the session as it stands, unrelated pending rows included (R3a). An external side effect must run only after the commit (the BUG-2202 pattern). A payment service needs the opposite of R3a: commit only its own failure record.

## Commands run
```
mutate.py app/services/attachment_service.py tests/unit/services/test_attachment_service.py --json attsvcv/att/mut.json
  -> Mutants: 26 · killed 20 · timeout 0 · survived 6 · score 77%  (90.9% after 4 equivalent)
pytest <test file> -q -p no:cacheprovider --cov=app.services.attachment_service --cov-branch --cov-report=term-missing
  -> 63 passed, 36 xfailed; attachment_service.py 64 0 4 0 100%
pytest <test file> -q -p no:cacheprovider --runxfail -rf            -> 36 failed, 63 passed
pytest <test file> -q -p no:cacheprovider   (runs 2 and 3)          -> 63 passed, 36 xfailed (both)
PYTHONPATH=attsvcv/att/plug FAILLINE_OUT=… pytest <test file> --runxfail -p v_failline  -> 36/36 fail on the card's Then line
python -I attsvcv/att/trace.py <cases> <test file> failline.json bugs.md  -> 99 cards, 99 tests, no mismatch
PYTHONPATH=attsvcv/att/plug AV=<variant> pytest <test file> --runxfail -p v_att -rf  -> base 99 passed; variants as tabled
ruff check <test file>                                               -> All checks passed!
```
Every run used a private `COVERAGE_FILE` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attsvcv\att\`. bugs.md unchanged (BUG-2230 … 2236 unused).

## Round 2 — 2026-11-05

> **Verdict (Round 2):** PASS (no findings, no routed items)
> Tests: 69 passed · 41 xfailed (reproduced ✅, 3 identical runs) · coverage 100% branch (64 statements, 4 branches)
> Mutation, whole module: 26 mutants · 22 killed · 4 survived → score 100% (22 / 22, after excluding 4 equivalent `__all__` strings, as in round 1). Round-1 survivors #11 (L109) and #15 (L156) are now killed.
> Hand variants: 17 run against my Rev-4 reference (`attsvcv/att/r2/plug/v_att2.py`). The reference passes **110 / 110** with `--runxfail`. 16 killed, 1 survived; the survivor is invalid data, as in round 1.
> Source commit: e48a092 (app/ unchanged) · Cases revision: 4

### Summary
Revision 4 adds eleven cards: CF-22, L-25, L-26, L-27, PG-12 and D-15 … D-20. It also changes PG-01, which gains Then 4. Every one of these tests matches its card:
- each Given is reproduced exactly (`wo()` builds the `WorkOrderType` first, as the Conventions say);
- each Then line is asserted in the card's order with the card's values;
- `warnings` / `warned` follow the new Convention (`caplog` at WARNING, root logger);
- no new mocks.

Traceability is clean: 110 cards ↔ 110 tests. With `--runxfail`, all 41 xfails fail on the card's "Fails today on" line. The five new xfails fail as follows:
- L-25 and L-26 on Then 1: `DID NOT RAISE`;
- D-15 and D-16 on Then 3: `dr.call_count` 0;
- D-19 on Then 2: no WARNING.

My reference is updated to the new rules:
- R3b: the no-`public_id` refusal rolls back.
- R4a: the Cloudinary delete runs right after the commit and before the re-read; an error is swallowed with a WARNING naming the `public_id`.

Unfaithful tests: none. The round-1 cosmetic point is closed: the test docstring now says revision 4.

### Round-1 survivors re-run
| Round-1 survivor | Round 2 | Killed by |
|---|---|---|
| `del_ready_only` (Finding 1) | killed (2) | D-15, D-16 |
| `del_any_pid` (Finding 1) | killed (1) | D-17 |
| `del_error_propagates` (Finding 1) | killed (2) | D-18, D-19 |
| `list_check_few_types` (Finding 2) | killed (2) | L-25, L-26 |
| `pdf_rollback_on_error` (Finding 3) | killed (1) | PG-12 |
| mutant #11 L109 `skip=0` → `1` (Finding 4) | killed | L-27 |
| mutant #15 L156 `width=1600` → `1601` (Finding 4) | killed | PG-01 Then 4 |
| `cf_nopid_rollback` (Finding 5). R3b makes rollback the intended behaviour, so the defect is now the round-1 reference's commit (`cf_nopid_commit`) | killed (1) | CF-22 |
| `del_after_refresh` (Finding 6) | killed (1) | D-20 |

### New variants for R3b / R4a
| Variant | Failing tests | Result |
|---|---|---|
| delete error swallowed with no log line | D-19 | killed |
| WARNING without the `public_id` | D-19 | killed |
| the message logged at INFO instead of WARNING | D-19 | killed |
| soft delete checked for project and machine only (deleted work order passes) | L-25 | killed |
| destroy before the commit (today's order) | D-09, D-10 | killed |
| destroy in a `finally` | D-09 | killed |
| sanity re-runs: `cf_rollback` / `cf_commit_failure_only` / `list_check_off` | 4 / 2 / 12 | killed |
| batched links read without the workspace filter | 0 | invalid data (as round 1), info only |

### D-20: why it passes today, and whether it still has teeth
**Why it passes today.** It passes because of BUG-2202 itself:
- Today `AttachmentManager.delete_attachment` calls `destroy_resource` inside the manager, **before** the service's commit (`app/managers/attachment_manager.py` lines 801–811).
- When the re-read after the commit then fails, the file has already been deleted once.
- So Then 2 (`dr.call_count == 1`, `public_id "pid-1"`) holds, but for the wrong reason: the delete ran before the commit, not after it.
- D-20 does not, and cannot, check the order. D-09 (failing commit → no call) and D-10 (commit before `dr`) catch that order. Both are strict xfails BUG-2202 that fail today.

**It still has teeth once the bug is fixed.** I ran it against my fixed reference, where the delete runs after the commit and before the re-read: D-20 passes. Then I ran the one-defect variant `del_after_refresh` (delete moved after `db.refresh`): D-20 fails on Then 2 with `assert 0 == 1` (`destroy_resource.call_count`), and it is the only test that fails. So D-20 guards R4a's "before the re-read" once BUG-2202 is fixed, and D-09 and D-10 guard "after the commit".

### Findings
None.

### For the coming features (additions)
- **Notifications:** R4a fixes the order after the commit: Cloudinary delete, then re-read, then response. A notification hook placed after the commit should come after the Cloudinary delete or be just as fail-safe. A failure in it must not undo the delete or stop the file from being deleted.
- **Permissions, Payments:** nothing new.

### Commands run (Round 2)
```
mutate.py app/services/attachment_service.py tests/unit/services/test_attachment_service.py --json attsvcv/att/r2/mut.json
  -> Mutants: 26 · killed 22 · timeout 0 · survived 4 · score 85%  (100% after 4 equivalent)
pytest <test file> -q -p no:cacheprovider --cov=app.services.attachment_service --cov-branch --cov-report=term-missing
  -> 69 passed, 41 xfailed; attachment_service.py 64 0 4 0 100%
pytest <test file> -q -p no:cacheprovider   (runs 2 and 3)          -> 69 passed, 41 xfailed (both)
PYTHONPATH=attsvcv/att/r2/plug FAILLINE_OUT=… pytest <test file> --runxfail -rf -p v_failline  -> 41 failed, 69 passed; 41/41 on the card's Then line
python -I attsvcv/att/trace.py <cases> <test file> r2/failline.json bugs.md  -> 110 cards, 110 tests, no mismatch
PYTHONPATH=attsvcv/att/r2/plug AV=<variant> pytest <test file> --runxfail -p v_att2 -rf  -> base 110 passed; variants as tabled
ruff check <test file>                                               -> All checks passed!
```
Every run used a private `COVERAGE_FILE` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attsvcv\att\r2\`. bugs.md unchanged (BUG-2230 … 2236 unused).
