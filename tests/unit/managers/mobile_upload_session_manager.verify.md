# Verification — `app/managers/mobile_upload_session_manager.py`

> **Verdict:** NEEDS WORK
> **Current verdict (Round 3):** PASS — cases Revision 5 closes R2-1 (spec G6 / BUG-2134, cards PM-72…74); 188 passed · 90 xfailed in 3 identical runs, 100% branch. See Round 3.
> **Current verdict (Round 2):** NEEDS WORK — the tests are faithful and all four round-1 gaps are closed; one new spec gap is left (describer, then case designer): at promote, does the visibility check come before the size and name validation? See Round 2.
> Tests: 184 passed · 83 xfailed (reproduced ✅) · coverage 100% branch (220 statements, 54 branches)
> Mutation: 202 mutants · 193 killed · 9 survived → score 99.0% (193 / 195, after excluding 7 equivalent, 0 dead, 0 bug-path)
> Hand variants: 52 · 39 killed · 13 survived (3 equivalent, 3 delegated / invalid data, 7 → case designer)
> Source commit: e48a092 · Cases revision: 3

## Summary
The tests are faithful to the cards: traceability is clean (267 cards ↔ 267 tests, every marker matches, every BUG ID exists), every Then line has its assertions, no extra mocks, no swallowed failures, and all 83 strict xfails fail on exactly the Then line their card names. Three plain runs are identical (no flakiness). An independent reference implementation written by the verifier (not the executor's) passes all 267 tests with `--runxfail`, so the xfail cards hold against the intended behaviour too.
What is missing is in the cards, not the tests: (1) nothing checks that a platform admin is **refused** on a private project (PR-2: admin counts for tickets only); (2) the promote refusal cards re-read only `status` and `public_id`, so a refusal raised after a flush that changed another column passes; (3) Cloudinary keyword checks use `kw(m).get("delivery_type", default)`, so a misspelled keyword (`type=`) passes while the real keyword-only function would raise `TypeError`; (4) no card stores a non-default `delivery_type`. All four go to the case designer. No executor or describer work; no new bug.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `create_session` R6, `promote_to_attachment` R4 (PR-2) | No card has a platform admin (no project membership, not creator, ground-team or no role) on an `invited_only` project or its component. PR-2 grants the admin flag for tickets only; a fix that also lets admins into private projects passes every test. Only C-43 / PM-60 use `is_platform_admin`, both on tickets. | variant `admin_on_private`: 267 passed | case designer |
| 2 | case-missing | PM-19, PM-26 … PM-67 (refused cards); `promote_to_attachment` R5 "session unchanged" | Then lines check `not db.dirty`, `not db.new` and re-read `status`, `public_id` only. A refusal raised **after** a flush that changed another session column (e.g. `asset_folder` written before the PR / capacity check) passes: `not db.dirty` is true after a flush, and the two columns are untouched. The named check `unchanged(S)` exists in the Conventions and should replace the two-column re-read on refusal cards. | variants `flush_before_parent`, `flush_before_capacity`: 267 passed | case designer |
| 3 | case-missing | Conventions "Cloudinary" (`kw(m).get(...)`); cards SG-*, CF-*, DS-*, CN-*, PM-* that check `gr`, `dr`, `rr`, `um` kwargs | A default "may be left out", so `kw(gr).get("delivery_type", "authenticated") == "authenticated"` also holds when the code passes the value under a wrong name (`type="authenticated"`). The real functions are keyword-only without `**kwargs` (`app/core/cloudinary_client.py`): that call would raise `TypeError` (wrapped as "Cloudinary verification failed" / swallowed in delete and metadata update). Fix: patch the Cloudinary names with `autospec=True` (same externals, so not an extra mock), or add a line per mock call `set(kw(m)) <= {<the function's parameter names>}`. | variants `confirm_argname`, `destroy_argname`, `rename_rt_argname`, `meta_dt_argname`: 267 passed each (`rename_argname`, `gus_argname`, `meta_argname` were killed, since those keys are checked without a default) | case designer |
| 4 | case-missing | `confirm_staging_upload` R2, `promote_to_attachment` R7 | "the session's `delivery_type` (default `authenticated`)": only the default side is checked. No card stores another value (e.g. `delivery_type "upload"`), so `session.delivery_type and AUTHENTICATED` survives. | mutants #102 (L450), #176 (L345) | case designer |

Unfaithful tests: none. Cosmetic: the test module docstring says "revision 2" (cases are revision 3; the notes record that revision 3 changed no test code) — executor, optional.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 100 | 422 | `raise AttachmentValidationError(...)` → `pass` | equivalent | `normalize_upload_request` (L435) repeats the same check `file_size > MAX` on `max(file_size, 1)` with the identical message, before any write or Cloudinary call; only differs when `_promote_file_name` also raises, which needs a hand-built staged name ending in `.` (BUG-2135 path). | — |
| 102 | 450 | `session.delivery_type or AUTH` → `and` | case-missing | Finding 4. | case designer |
| 134 | 401 | `"." in base` → `"" in base` | equivalent | `base.rsplit(".", 1)[0]` on a string without `.` returns it unchanged. | — |
| 146 | 210 | `mime == "application/pdf"` → `mime == ""` | equivalent | The first operand `not mime.startswith("image/")` is already true for `application/pdf` and for `""`. | — |
| 147 | 254 | `entity_id=1` → `2` | equivalent | `normalize_upload_request` never reads `entity_id` (`app/utils/attachment_allowlist.py`). | — |
| 152 | 352 | `resource.get("bytes") or 0` → `or 1` | equivalent | Used only in `> MAX`; 0 and 1 are both below it. The stored size (L365) reads `bytes` separately. | — |
| 161 | 420 | `session.file_size or 0` → `or 1` | equivalent | Used in `> MAX` and in `max(file_size, 1)`: 0 and 1 give the same results. | — |
| 176 | 345 | `session.delivery_type or AUTH` → `and` | case-missing | Finding 4. | case designer |
| 186 | 397 | `rsplit(".", 1)[-1]` → `rsplit(".", 2)[-1]` | equivalent | The last element of the split is the same whatever the split count. | — |

## Hand variants
These are my own in-process plugins (`attv/mobs3/plug/v_mobs.py`, scratch only). `MV=base` is an independent intended-behaviour reference: **267 passed** with `--runxfail`. Each other variant adds one defect to that reference. The run uses `--runxfail`, so the bug-path cards (PR-1 / PR-2, ordering, lock) take part.

| Variant (one defect) | Failing tests | Result |
|---|---|---|
| role not read (behaves like a role parameter nobody fills) | 5 (C-38, C-42, PM-54, PM-57, PM-59) | killed |
| role read from another workspace (oldest membership row of the user) | 2 (C-47, PM-64) | killed |
| inactive / suspended membership counted | 8 | killed |
| **platform admin allowed on private projects** | 0 | **survived → Finding 1** |
| too strict: every private project refused / workspace owner refused / creator refused / project member refused / admin refused on tickets / non-member refused on workspace-wide records | 9 / 2 / 2 / 2 / 2 / 2 | killed |
| parent lookup without workspace filter | 6 | killed |
| soft delete ignored / component of a deleted project accepted | 6 / 2 | killed |
| project visibility ignored / ticket visibility ignored | 26 / 14 | killed |
| no PR check at create / at promote | 31 / 31 | killed |
| `get_for_creator` without workspace / without creator filter / without `FOR UPDATE` | 2 / 2 / 1 | killed |
| sign: staged file destroyed before the status check | 5 | killed |
| confirm: `get_resource` before the status checks | 8 | killed |
| promote: move before the size check / before the PR check / capacity after the move | 34 / 32 / 1 | killed |
| **refusal after a flush (before the PR check / before the capacity check)** | 0 / 0 | **survived → Finding 2** |
| wrong `public_id`: signature, destroy, metadata update; rename from/to swapped | 1 / 5 / 1 / 1 | killed |
| wrong keyword: `rename_resource(public_id=…)`, signature `type=`, metadata `folder=` | 1 / 1 / 1 | killed |
| **wrong keyword `type=` for `delivery_type`: get_resource, destroy, rename, metadata** | 0 each | **survived → Finding 3** |
| size `>=` instead of `>` at confirm / at promote; confirm `> MAX + 1` | 1 / 1 / 1 | killed |
| type check skipped at confirm; PDF rule `or` instead of `and` | 2 / 1 | killed |
| promoted name room off by one (256 characters) | 1 | killed |
| cancel destroys a consumed session's file | 1 | killed |
| asset folder from the session's label instead of the server's | 3 | killed |
| signature without `delivery_type` (default is the same) | 0 | equivalent |
| `max(size, 0) or 1` for `max(size, 1)` | 0 | equivalent (same value for every size) |
| label lookup with `session.workspace_id` instead of `workspace.id` | 0 | equivalent (a session reaches promote only through `get_for_creator` in that workspace) |
| project-member row looked up in any workspace | 0 | delegated: `ProjectManager.can_access_project` (cited by PR-2, scoped there; a member row in another workspace is invalid data) |
| capacity counted over links of every workspace | 0 | delegated: `AttachmentManager.assert_entity_attachment_capacity` / link DAO (attachment_manager tests) |
| component accepted when its project is in another workspace | 0 | invalid cross-workspace data, which no writer produces. PR-1 states no rule for it. Info only. |

## Traceability
cases 267 · tests 267 · unmatched: none · tests without a case ID: none · marker mismatches: none (184 pass ↔ no marker; 83 xfail ↔ `strict=True`, reason names the card's BUG ID; BUG-1282, BUG-2130 … BUG-2136, BUG-2138 … BUG-2141 all in `bugs.md`) · `# Then N` blocks match every card's Then count · `--runxfail`: 83 / 83 fail inside the Then block named by "Fails today on" (9 raise inside the call as the cards say: C-06 DataError, EA-09, GC-12 TypeError, CF-19, PF-14, PM-21, PM-27 / 35 / 36 IntegrityError).

## For the coming features
- **Permissions:** PR-5 is pinned by cards and checked by variants. The role is read only from the caller's **active** `workspace_members` row in **this** workspace. A role passed in, an inactive row, or another workspace's row all fail tests. Still open: Finding 1 (an admin on a private project). One `can_access_*` helper per record type would let the attachment, markup and mobile managers share PR-1 / PR-2 instead of three copies.
- **Notifications:** this module emits nothing of its own. The "Attached …" activity entry comes from `AttachmentManager.confirm_attachment`. A "phone upload ready" notification would hook `confirm_staging_upload` R6 (status `uploaded`). Expiry is never saved (D13), so a notifier must compute it from `expires_at`.
- **Payments:** nothing here. The QR token is bearer access (`get_by_raw_token` is unscoped by design). Do not copy that pattern for payment links without a stated TTL and a single-use rule.

## Commands run
```
mutate.py app/managers/mobile_upload_session_manager.py tests/unit/managers/test_mobile_upload_session_manager.py --json attv/mobs3/mut.json
  -> Mutants: 202 · killed 193 · timeout 0 · survived 9 · score 96%  (99.0% after 7 equivalent)
pytest <test file> -q -p no:cacheprovider --cov=app.managers.mobile_upload_session_manager --cov-branch --cov-report=term-missing
  -> 184 passed, 83 xfailed; mobile_upload_session_manager.py 220 0 54 0 100%
pytest <test file> -q -p no:cacheprovider --runxfail -rf            -> 83 failed, 184 passed
pytest <test file> -q -p no:cacheprovider   (runs 2 and 3)          -> 184 passed, 83 xfailed (both)
PYTHONPATH=attv/mobs3/plug pytest <test file> --runxfail -p v_failline  -> 83/83 fail on the card's Then line
PYTHONPATH=attv/mobs3/plug MV=<variant> pytest <test file> --runxfail -p v_mobs  -> base 267 passed; variants as tabled
```
Every run used a private `COVERAGE_FILE` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\mobs3\`.

## Round 2 — 2026-11-04

> **Verdict (Round 2):** NEEDS WORK (describer, then case designer: one spec gap; nothing for the executor)
> Tests: 188 passed · 87 xfailed (reproduced ✅, 3 identical runs) · coverage 100% branch (220 statements, 54 branches)
> Mutation, re-run on L345 and L450 only: 2 mutants · 2 killed · 0 survived → 100%. Round-1 survivors #176 (L345) and #102 (L450) are now killed by CF-23 and PM-68.
> Hand variants: 55 run against the verifier's Revision-4 reference (275 passed with `--runxfail`). 46 killed, 9 survived: 3 equivalent, 3 delegated or invalid data (as in round 1), and 1 new spec gap.
> Source commit: e48a092 (app/ unchanged) · Cases revision: 4

### Summary
Revision 4 closes all four round-1 findings. Each variant that slipped through round 1 now fails a named card (table below).
The new and changed tests match their cards:
- C-51, C-52, C-53, PM-69, PM-70, PM-71, CF-23 and PM-68 are new.
- 39 cards now check `unchanged(S)`, and each test asserts it under the card's Then number. The snapshot is taken right before the When.
- No `kw(m).get(…, default)` is left in the tests or the cards.
- `autospec=True` is used only on the ten Cloudinary names the spec lists as externals, so it is not an extra mock.
- With `--runxfail`, all 87 xfails fail on the card's "Fails today on" line.
- The test docstring now says revision 4, which closes the round-1 cosmetic point.

One variant written for this round survives: `check_after_validation`, which checks visibility after the size and name validation at promote. Promote R3 (size) comes before R4 (visibility) in the mobile spec. The attachment spec's PR-4 asks for "refusal first" in the attachment manager, but for the QR flow it only requires the check "before the file is moved". So no rule decides whether a hidden record with an oversized or badly named staged file answers 404 or 400. The executor's reference already checks visibility first.

### Round-1 survivors re-run
| Round-1 survivor | Round 2 | Killed by |
|---|---|---|
| `admin_on_private` (platform admin opens a private project or its component) | killed (4) | C-51, C-52, PM-69, PM-70 |
| `flush_before_parent` (refusal after a flush that writes `asset_folder`) | killed (34) | PM-19, PM-26 … (every `unchanged(S)` promote refusal) |
| `flush_before_capacity` | killed (1) | PM-19 |
| `confirm_argname` (`type=` for `get_resource`) | killed (16) | CF-01 … CF-08 and others (autospec `TypeError` → "Cloudinary verification failed") |
| `destroy_argname` (`type=` for `destroy_resource`) | killed (10) | SG-10, CF-10, DS-01, DS-02, DS-05 … DS-07, CN-05 and others |
| `rename_rt_argname` (`type=` for `rename_resource`) | killed (27) | PM-01 … PM-08 and others |
| `meta_dt_argname` (`type=` for `update_resource_metadata`) | killed (2) | PM-02, PM-06 |
| mutant #176 L345 `or` → `and` | killed | PM-68 |
| mutant #102 L450 `or` → `and` | killed | CF-23 |
| new: `owner_ticket_refused` (BUG-2103 grant missing) | killed (2) | C-53, PM-71 |

### Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| R2-1 | spec-gap | `promote_to_attachment` R3, R4, R6 vs `attachment_manager.spec.md` PR-4 | It is not stated whether PR-1 / PR-2 at promote come before the size check (R3) and the name/type normalization (R6). The attachment spec's PR-4 ("before every error … that depends on the input") covers only the attachment manager; for the QR flow it says only "before the file is moved". If PR-4 applies, the cards need a hidden record combined with an oversized session, and one combined with a rejected type. | variant `check_after_validation`: 275 passed | describer (fill-gaps), then case designer |

Unfaithful tests: none.

### Surviving variants
| Variant | Class | Why |
|---|---|---|
| `check_after_validation` | spec-gap | R2-1 |
| `gus_no_delivery` | equivalent | `generate_upload_signature`'s default `delivery_type` is `authenticated`, the same value |
| `size_min0` | equivalent | `max(size, 0) or 1` == `max(size, 1)` for every size |
| `label_session_ws` | equivalent | the session reaches promote only through `get_for_creator` in this workspace |
| `pmem_any_ws`, `capacity_any_ws`, `comp_parent_ws_ignored` | delegated / invalid data | as round 1: `ProjectManager.can_access_project`, the link DAO, and a cross-workspace component that no writer produces |
| `promote_no_check` / `create_no_check` etc. | — | killed; the whole table is in `attv/mobs3r2/var_*.txt` |

### Commands run (Round 2)
```
mutate.py <module> <test file> --lines 345-345 --json attv/mobs3r2/mut345.json   -> Mutants: 1 · killed 1 · survived 0 · 100%
mutate.py <module> <test file> --lines 450-450 --json attv/mobs3r2/mut450.json   -> Mutants: 1 · killed 1 · survived 0 · 100%
pytest <test file> -q -p no:cacheprovider --cov=app.managers.mobile_upload_session_manager --cov-branch --cov-report=term-missing
  -> 188 passed, 87 xfailed; 220 0 54 0 100%
pytest <test file> -q -p no:cacheprovider   (runs 2 and 3)          -> 188 passed, 87 xfailed (both)
PYTHONPATH=attv/mobs3r2/plug pytest <test file> --runxfail -rf -p v_failline  -> 87 failed, 188 passed; 87/87 on the card's Then line
PYTHONPATH=attv/mobs3r2/plug MV=<variant> pytest <test file> --runxfail -p v_mobs  -> base 275 passed; variants as tabled
ruff check <test file>                                               -> All checks passed!
```
Every run used a private `COVERAGE_FILE` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\mobs3r2\`. bugs.md unchanged (BUG-2193 … 2199 unused).

## Round 3 — 2026-11-04

Narrow re-check of cases Revision 5 (spec G6 / BUG-2134: promote's parent-record check R4 comes after the session-state checks and before size, name, type and limit).

**Verdict: PASS.** No findings.

- **New cards PM-72, PM-73 and PM-74 match their tests.**
  - Each Given is reproduced exactly: a private "Tender 2027" project, plus `file_size 10485761` / `mime_type "image/png"` / `full(PV)`.
  - The `unchanged` snapshot is taken right before the When.
  - Then 1–6 are asserted in card order with the card's exact values: `AttachmentNotFoundError`, `NF("project", PV.id)`, `not db.dirty`, `not db.new`, `cl_called(CL) == []`, `unchanged(S)`.
  - Each test carries `XF2134`, a strict xfail whose reason names BUG-2134, and BUG-2134 exists in bugs.md.
- **Fails-today lines hold.** Under `--runxfail` the three tests fail on Then 1 with exactly the card's errors:
  - PM-72: `AttachmentValidationError: File too large (10485761 bytes)…`
  - PM-73: `AttachmentValidationError: MIME type 'image/png' does not match .jpg…`
  - PM-74: `AttachmentLimitError: This record already has the maximum of 25 attachments.`
- **R2-1 is closed.**
  - The Round 2 reference (`v_mobs.py`, base) passes all 278 tests with `--runxfail`.
  - The variant `check_after_validation` (visibility checked after size and type) now fails 2 tests: PM-72 and PM-73.
  - That variant keeps the limit check after visibility, which is why PM-74 does not fail on it.
  - The limit-before-visibility order is what today's code does, and PM-74 fails on it (above).
- **Runs:** 3 plain runs gave the same 188 passed · 90 xfailed, so nothing is flaky. Coverage is 100% branch (220 statements, 54 branches).

| # | Item | Status |
|---|---|---|
| R2-1 | visibility after size/type at promote | closed: killed by PM-72, PM-73 |

### Commands run (Round 3)
```
COVERAGE_FILE=<s>/.cov.plain{1,2,3} pytest <test file> -q -p no:cacheprovider --cov=app.managers.mobile_upload_session_manager --cov-branch --cov-report=term-missing
  -> 188 passed, 90 xfailed (x3); mobile_upload_session_manager.py 220 0 54 0 100%
COVERAGE_FILE=<s>/.cov.rx pytest <test file> -q -p no:cacheprovider --runxfail -rf -k "PM_72 or PM_73 or PM_74"
  -> 3 failed (on Then 1, errors as above)
PYTHONPATH=<s>/plug MV=base pytest <test file> --runxfail -p v_mobs                    -> 278 passed
PYTHONPATH=<s>/plug MV=check_after_validation pytest <test file> --runxfail -p v_mobs  -> 2 failed (PM-72, PM-73), 276 passed
```
`<s>` = `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\mobs3r3\`, which holds the private `COVERAGE_FILE`s. bugs.md is unchanged.
