# Verification — `app/services/mobile_upload_service.py`

> **Verdict:** NEEDS WORK (case designer: 4 card gaps; describer: 1 small spec fact; nothing for the executor)
> **Current verdict (Round 2):** PASS. Cases Rev 3 and spec G5 close findings 1–6. 49 passed · 23 xfailed in 3 identical runs, 97% branch. Every round-1 survivor now fails a card. See Round 2.
> Tests: 47 passed · 19 xfailed (reproduced ✅, 3 identical runs) · coverage 97% branch (71 statements, 2 branches; only line 156, unreachable as the spec says)
> Mutation: 22 mutants · 14 killed · 8 survived → score 100% (14 / 14, after excluding 6 equivalent, 2 dead, 0 bug-path)
> Hand variants: 45 against the verifier's own reference (66 passed with `--runxfail`). 37 killed, 8 survived: all 8 go to the case designer (Findings 1–5).
> Source commit: e48a092 · Cases revision: 2

## Summary
The tests do what the cards say:
- Traceability is clean: 66 cards and 66 tests, every marker matches its card, and every BUG ID exists in bugs.md.
- Each Then line has its assertions, in card order.
- Nothing is mocked beyond the listed externals, and no failure is swallowed.
- With `--runxfail`, each of the 19 strict xfails fails on the Then line named by the card's "Fails today on".

Three plain runs gave the same result. My own reference implementation passes all 66 tests with `--runxfail`, and the tool mutants are all killed. The service is thin, so the real test was the hand variants. Eight of them pass every test, and each one points to a missing card, not a weak test:
1. A lock taken after the work is done passes the lock cards.
2. "Commit, then raise" applied to a refusal on create, promote or sign passes, and so does a promote whose HR-13 commit drops unrelated pending rows (R4a). No refusal card has a pending row.
3. A re-sign whose commit fails still deletes the earlier file. No card covers it.
4. After the BUG-2205 fix, an error from the delete that runs after the commit can reach the caller. No card covers that either.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | MUSV-CN-06, MUSV-PM-14 (`cancel_session` R1, `promote_session` R1 [BUG-2139], HR-10) | **locked** = any statement during the call that names `mobile_upload_sessions` and contains `FOR UPDATE`. A lock taken *after* the manager has already acted (a re-select `FOR UPDATE` just before the commit) passes, but it protects nothing: the Cloudinary rename or destroy has already happened. The check should require that the statement that **reads** the session (the first `SELECT … FROM mobile_upload_sessions` of the call) carries `FOR UPDATE`, or at least that it comes before the first Cloudinary call. | variants `late_lock_cancel`, `late_lock_promote`: 66 passed each | case designer |
| 2 | case-missing | `create_session` R2, `promote_session` R3, `public_sign` R4 (TC3: "every other uncommitted change pending in that session is discarded") | TC3's "pending X discarded" is checked once per callable, and never for a refusal. Create checks it only with C-03 (`IntegrityError`); promote only with PM-06 and sign only with PS-06, both of which fail before the manager is reached. A service that commits, then raises, on a refusal passes every test because the refusal itself flushed nothing: `AttachmentNotFoundError` on create, any of `MobileUploadSessionError` / `AttachmentValidationError` / `AttachmentNotFoundError` on promote, `MobileUploadSessionError` on sign. This is the realistic way a BUG-2137 / BUG-2204 fix goes wrong, by applying "commit then raise" too broadly. Fix: add "pending X" with `count: x_gone` to one refusal card per callable (e.g. C-07 (xfail BUG-2131), PM-04 or PM-05, PS-07). Today PM-12 kills the promote variant only by accident: `AttachmentLimitError` comes after the move (BUG-2133), and once BUG-2133 is fixed nothing will check this. | variants `commit_on_refusal_create`, `commit_on_refusal_promote`, `commit_on_refusal_sign`: 66 passed each | case designer |
| 3 | case-missing | `promote_session` R4a [BUG-2204] | R4a says the HR-13 commit takes the whole session, unrelated pending changes included. PC-09 checks this for `public_confirm` R3a, but no card checks it for promote. A promote that discards the unrelated pending changes before its failure commit (here: `db.rollback()` at entry) still passes PM-09 and PM-10. Needs a PM-09 twin with "pending X" and `committed: x_kept` (strict xfail BUG-2204). | variant `rollback_at_entry_promote`: 66 passed (its confirm twin `rollback_at_entry_confirm` is killed by PC-09) | case designer |
| 4 | case-missing | `public_sign` R3 [BUG-2205] | CN-08 covers "a failing commit never deletes the staged file" for cancel only. Sign has PS-04, where the error is raised inside the manager, and PS-08, where the session holds no earlier file. A fix that deletes the earlier file in a `finally` after the commit, so that it also deletes when the commit fails, passes. Needs a card: a session with `public_id OLD`, a failing commit, then `dr.called is False` and re-read `public_id == OLD` (strict xfail BUG-2205). | variant `delete_finally_sign`: 66 passed (`delete_finally_cancel` is killed by CN-08) | case designer |
| 5 | case-missing | `cancel_session` R3, `public_sign` R3 (manager R3: a failed Cloudinary destroy is swallowed, BUG-2136) | No card makes `dr` raise. Today the manager swallows the error. After the BUG-2205 fix, the delete runs after the commit, possibly in the service. If its error then reaches the caller, a cancel that was saved answers 500. Needs a card: an uploaded session, `dr` with `side_effect = RuntimeError("down")`, then the cancel returns `status == "cancelled"` and the committed row reads `cancelled`. Same for re-sign with `OLD`. These pass today. | variant `delete_error_propagates`: 66 passed | case designer |
| 6 | spec-gap (Facts) | spec "Externals to mock" | The cards (Conventions "Settings and time") also patch `app.dao.mobile_upload_session.utcnow`, the clock behind `mark_expired_if_needed`, plus `uuid.uuid4` and `secrets.token_urlsafe` of the manager. The service spec's list names only Cloudinary, `utcnow` / `time.time` of the manager, and `settings`. The patches are correct and needed (without the DAO clock every LATER session would read as expired today), but the spec should list them. This does not change the tests. | test file L180–184; spec L63 | describer (fill-gaps, one line) |

Unfaithful tests: none.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 3–8 | 190–195 | each `__all__` string → `""` | equivalent | `__all__` is read only by `from … import *`. No module does that with this one (grep over `app/` and `tests/`), and the tests import every name explicitly. | — |
| 19 | 156 | `raise MobileUploadSessionNotFoundError(...)` → `pass` | dead | Spec "Not specified": `mobile_upload_sessions.workspace_id` is `NOT NULL` with an `ON DELETE CASCADE` FK (`app/models/mobile_upload_session.py` L15–20). `BaseDAO.get` (`app/dao/base.py` L43) has no soft-delete filter, and `Workspace` has no `is_deleted`. So `workspace_dao.get(db, session.workspace_id)` cannot return `None` for a session that was just read. Unreachable confirmed. | — |
| 22 | 156 | message → `""` | dead | same line | — |

## Hand variants
These are my own in-process plugins: `v_mob.py` in scratch, not the executor's `refplug_mob.py`. `MV=base` is an independent intended-behaviour reference covering:
- PR-1 / PR-2 before create and before the move (BUG-2130, BUG-2131, BUG-2134);
- the session read with `FOR UPDATE` (BUG-2139);
- `destroy_resource` collected during the manager call and replayed after the commit, with errors swallowed (BUG-2205);
- commit-then-raise when the promote's file was moved (BUG-2204) or the confirm cleared the session (BUG-2137), with a failing commit there giving TC4.

The base reference passes **66 / 66** with `--runxfail`. Each other variant adds one defect to it.

| Variant (one defect) | Failing tests | Result |
|---|---|---|
| **commit then raise** — HR-13 never applied on promote / on confirm | PM-09, PM-10 / PC-03, PC-04, PC-09 | killed |
| HR-13 on confirm commits only the session (rollback, re-apply, commit) | PC-09 | killed |
| HR-13 path discards unrelated pending changes: confirm / **promote** | PC-09 / **0** | **promote survived → Finding 3** |
| commit instead of rollback on every error: cancel / sign / confirm / promote (non-refusal) | CN-03, CN-05 / PS-03, PS-04, PS-06 / PC-06 / PM-12 | killed |
| **commit then raise on a refusal**: create (`AttachmentNotFoundError`) / promote (session, validation, not-found) / sign (session, validation) | 0 / 0 / 0 | **survived → Finding 2** |
| **Cloudinary delete before commit** (today's order): cancel / sign | CN-08, CN-09 / PS-04, PS-05 | killed |
| delete in `finally` after the commit (also on a failed commit): cancel / **sign** | CN-08 / **0** | **sign survived → Finding 4** |
| delete replayed with the new `public_id` instead of the earlier one (sign) | PS-02 | killed |
| **post-commit delete error reaches the caller** | 0 | **survived → Finding 5** |
| **missing row lock**: cancel / promote | CN-06 / PM-14 | killed |
| **lock taken late** (after the manager acted): cancel / promote | 0 / 0 | **survived → Finding 1** |
| **wrong error mapping**: `AttachmentNotFoundError` → `MobileUploadSessionNotFoundError` on create; `AttachmentConfirmError` → `MobileUploadSessionError` on promote; `CloudinaryNotConfiguredError` → `MobileUploadSessionError` on sign | C-05 … C-09 / PM-11 / PS-03, PS-04 | killed |
| **missing rollback (TC3)**: create / cancel / promote / sign / confirm | C-03 / CN-03, CN-05 / PM-06, PM-12 / PS-03, PS-04, PS-06 / PC-06 | killed |
| **rollback or commit in a TC6 read**: `get_session` rollback on error / rollback on success / commit on success; `get_public_session` rollback on error | GS-06 / GS-07 / GS-07 / GP-04 | killed |
| **caller not passed down** (the workspace's first member instead of `user`): create / promote | C-01, C-03, C-10 / PM-01, PM-02, PM-09 | killed |
| record check: no workspace filter / deleted ignored / `invited_only` ignored / membership of any project counts / owner role from any workspace (W0) | C-06 / C-05, PM-17 / C-07, C-08, PM-15, PM-16 / C-08, PM-16 / C-09 | killed |
| no record check on create / on promote; check after the move | C-05 … C-09 / PM-15 … PM-17 / PM-15, PM-17 | killed |
| public sign in a workspace other than the session's own | PS-01 … PS-05, PS-07, PS-08 | killed |
| HR-13 also on a failed move (PM-11) or a failed lookup (PC-05) | — | not run as a defect: equivalent under R4a / R3a, which apply TC3 only to R3 / R5 and R4 errors, and those paths flush nothing |
| **one links query per item (BUG-2201)**, **list check on the parent (BUG-2200)** | — | not applicable: this service has no list callable |

## Traceability
cards 66 · tests 66 · unmatched: none · tests without a card ID: none · marker mismatches: none (47 pass ↔ no marker; 19 xfail ↔ `strict=True`, and each `XF<n>` reason names BUG-n: 2130 ×2, 2131 ×3, 2134 ×3, 2137 ×3, 2139 ×2, 2204 ×2, 2205 ×4, all in bugs.md) · the `# Then N` blocks match every card's Then count, in order · `--runxfail`: 19 / 19 fail inside the Then block named by "Fails today on" (checked by mapping each failure's last test-file line to the preceding `# Then N`).

## For the coming features
- **Permissions:** the service's own part is to pass the caller (`user`) to the manager for PR-5, and to ask for the lock. Variants show both are pinned: a wrong caller fails PM-01, PM-02 and C-01, and a missing lock fails CN-06 and PM-14. A late lock is not pinned yet (Finding 1). PR-1 / PR-2 are pinned through the service: a W2 project (C-06), a W0-only owner role (C-09) and membership of another project (C-08, PM-16) each fail a card. The public paths are token-only by design. The phone works in the session's own workspace (PS-01), so a future "who uploaded" field can only name the desktop creator, not the phone.
- **Notifications:** nothing is emitted here. Hook a "phone file ready" notice after the commit in `public_confirm` (R2), never before it: with BUG-2137, the oversized path now commits too, and a notice there would announce a file that was deleted. The "Attached …" entry comes from the attachment manager at promote and is committed with it (PM-02).
- **Payments:** nothing here. Two patterns from this module should be reused: (1) external side effects such as a Cloudinary delete or a payment void run only after the commit, and the external call's error is handled on its own path (Finding 5 shows how that gets missed); (2) "commit, then raise" must be scoped to the one failure that needs a record (Finding 2). Don't copy the bearer token as a payment-link pattern without a stated TTL and a single-use rule.

## Commands run
```
mutate.py app/services/mobile_upload_service.py tests/unit/services/test_mobile_upload_service.py --json <s>/mut.json
  -> Mutants: 22 · killed 14 · timeout 0 · survived 8 · score 64%  (100% after 6 equivalent, 2 dead)
pytest <test file> -q -p no:cacheprovider --cov=app.services.mobile_upload_service --cov-branch --cov-report=term-missing   (x3)
  -> 47 passed, 19 xfailed (all three runs); mobile_upload_service.py 71 1 2 1 97%  missing 156
pytest <test file> -q -p no:cacheprovider --runxfail -rf                      -> 19 failed, 47 passed
PYTHONPATH=<s>/plug FAILJSON=<s>/fails.json pytest <test file> --runxfail -p v_failline ; python <s>/plug/v_trace.py <cases> <test file> <s>/fails.json
  -> cards 66 · tests 66 · 47 pass / 19 xfail · fail-line mismatches 0 of 19
PYTHONPATH=<s>/plug MV=<variant> pytest <test file> -q -p no:cacheprovider --runxfail -p v_mob
  -> base 66 passed; variants as tabled (<s>/variants.txt, <s>/variants2.txt)
ruff check <test file>                                                        -> All checks passed!
```
`<s>` = `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attsvcv\mob\`; every run used a private `COVERAGE_FILE` there. `app/` untouched; bugs.md unchanged (no new bug: every survivor is a missing card for an existing rule; BUG-2243 … 2249 unused).

## Round 2 — 2026-11-05

> **Verdict (Round 2):** PASS. No findings, and nothing to route.
> Tests: 49 passed · 23 xfailed (reproduced ✅, 3 identical runs) · coverage 97% branch (71 statements, 2 branches; only line 156, unreachable as in round 1)
> Mutation: not re-run this round (app/ unchanged at e48a092; round 1: 100% after excluding 6 equivalent and 2 dead)
> Hand variants: 48 against the verifier's Rev-3 reference (72 passed with `--runxfail`). 48 killed, 0 survived.
> Source commit: e48a092 · Cases revision: 3

### Summary
Cases Rev 3 and the spec's 2026-11-05 revision (G5; `cancel_session` R3a, `public_sign` R3a: the delete runs after the commit, and its error is logged as a WARNING and swallowed) close all six round-1 findings.

The spec's "Externals to mock" now lists `app.dao.mobile_upload_session.utcnow`, `uuid.uuid4` and `secrets.token_urlsafe`, which closes Finding 6.

The new and changed tests match their cards:
- **Changed cards:** CN-06 and PM-14 (event log, `first_read`, `acted_before`); C-07, PM-04 and PS-07 (pending X, `x_gone`).
- **New cards:** PM-19, PS-09, CN-10, PS-10, CN-11 and PS-11.
- Each Given is built as the card says:
  - pending X is added after the commit point and after the `counts` snapshot;
  - the `dr` / `rr` / `um` / `agr` side effects are installed inside `event_log`;
  - `caplog.set_level(WARNING)` is set before the When.
- Every Then line is asserted in card order with the card's exact values:
  - `"FOR UPDATE" in ev[first_read][1].upper()` and `acted_before(...) is False`;
  - `x_count == 0` / `== 1` after the card's test-level rollback;
  - PS-09 asserts `dr.called is False` and re-reads `public_id == OLD` and `asset_folder == "Dev/x/old"`;
  - CN-10 / PS-10 assert `dr.call_count == 1` and the committed re-read;
  - CN-11 / PS-11 assert `warned(STG)` / `warned(OLD)`.
- No new mocks: the event log only sets `side_effect` on externals that are already patched.
- New marker `XF2136` (`strict=True`, reason names BUG-2136, which is in bugs.md).

With `--runxfail`, all 23 xfails fail inside the Then block their card names:
- CN-06 and PM-14 fail on Then 2 (unlocked first read).
- PM-19 fails on Then 4 (X rolled back).
- PS-09 fails on Then 4 (`dr` called).
- CN-11 and PS-11 fail on Then 2 (no WARNING).
- The other 17 fail as in round 1.

Unfaithful tests: none.

### Round-1 survivors re-run
My reference (`r2/plug/v_mob.py`) is updated to Rev 3 and passes all 72 tests with `--runxfail`. The update adds the WARNING `"Cloudinary delete of <public_id> failed: <error>"` to the post-commit delete, which is then swallowed (R3a).

| Round-1 survivor | Round 2 | Killed by |
|---|---|---|
| `late_lock_cancel` (lock taken after the manager acted) | killed (1) | CN-06 |
| `late_lock_promote` | killed (1) | PM-14 |
| `commit_on_refusal_create` (commit then raise on `AttachmentNotFoundError`) | killed (1) | C-07 |
| `commit_on_refusal_promote` (session / validation / not-found refusals) | killed (1) | PM-04 |
| `commit_on_refusal_sign` (session / validation refusals) | killed (1) | PS-07 |
| `rollback_at_entry_promote` (HR-13 commit drops unrelated pending rows) | killed (1) | PM-19 |
| `delete_finally_sign` (earlier file deleted though the commit failed) | killed (1) | PS-09 |
| `delete_error_propagates` → split: `_cancel` / `_sign` (post-commit delete error reaches the caller) | killed (2 / 2) | CN-10, CN-11 / PS-10, PS-11 |
| new: `no_warning` (post-commit delete error swallowed silently) | killed (2) | CN-11, PS-11 |

The 37 variants killed in round 1 were re-run against the new reference, and all are still killed. Several now fail more cards: `delete_before_commit_sign` → PS-04, PS-05, PS-09, PS-11; `no_rollback_promote` → PM-04, PM-06, PM-12; `hr13_never_promote` → PM-09, PM-10, PM-19. Full table: `r2/variants.txt`.

### Findings
None. Round-1 Findings 1–6 are closed: 1 → CN-06 / PM-14; 2 → C-07, PM-04, PS-07; 3 → PM-19; 4 → PS-09; 5 → CN-10, PS-10 (plus CN-11, PS-11); 6 → spec G5.

### For the coming features (additions)
- **Notifications / logging:** the post-commit Cloudinary delete is now pinned to log a WARNING naming the `public_id` (CN-11, PS-11, BUG-2136). An alerting hook for failed external deletes can key on that line.
- **Payments:** the pattern is now fully pinned here: the external side effect runs after the commit, its error is logged and swallowed, and a failed commit never triggers it. Copy it for payment voids and refunds.
- **Permissions:** unchanged from round 1. The lock check now also pins *where* the lock is taken: on the first read, before any write or Cloudinary call.

### Commands run (Round 2)
```
pytest <test file> -q -p no:cacheprovider --cov=app.services.mobile_upload_service --cov-branch --cov-report=term-missing   (x3)
  -> 49 passed, 23 xfailed (all three); mobile_upload_service.py 71 1 2 1 97%  missing 156
PYTHONPATH=<s>/plug FAILJSON=<s>/r2/fails.json pytest <test file> -q -p no:cacheprovider --runxfail -rf -p v_failline
  -> 23 failed, 49 passed
python <s>/plug/v_trace.py <cases> <test file> <s>/r2/fails.json
  -> cards 72 · tests 72 · 49 pass / 23 xfail · markers ok · Then blocks ok · fail-line mismatches 0 of 23
PYTHONPATH=<s>/r2/plug MV=<variant> pytest <test file> -q -p no:cacheprovider --runxfail -p v_mob
  -> base 72 passed; 48 variants, all killed (<s>/r2/variants.txt)
ruff check <test file>                                                        -> All checks passed!
```
`<s>` = `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attsvcv\mob\`; round-2 runs used private `COVERAGE_FILE`s in `<s>\r2\`. mutate.py not run (per instruction). `app/` untouched; bugs.md unchanged (BUG-2243 … 2249 unused).
