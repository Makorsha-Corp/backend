# Spec — `app/services/mobile_upload_service.py`

> **Status:** APPROVED (2026-11-04; nothing open. Every item decided by Claude under the reviewer's delegation (2026-11-04), or already settled upstream: HR-10, HR-13, OQ-5, mobile manager D8 / BUG-2137.)
> **Source commit:** e48a092
> **Revision 2026-11-04 (fill-gaps, `mobile_upload_service.cases.md` gaps 1–4; decided by Claude under the reviewer's delegation (2026-11-04)):** request-schema import module added; TC5 marked not unit-testable on `cancel_session` and `public_confirm`; the post-commit Cloudinary delete of BUG-2205 is patched on `app.managers.mobile_upload_session_manager.destroy_resource`; HR-13 vs TC3 stated (`promote_session` R4a, `public_confirm` R3a). No new bug; status stays APPROVED.
> **Revision 2026-11-05 (verifier, `mobile_upload_service.verify.md` finding 6; decided by Claude under the reviewer's delegation (2026-11-05)):** Externals to mock completed (`utcnow` of the DAO, `uuid.uuid4`, `secrets.token_urlsafe`); `cancel_session` R3a and `public_sign` R3a: a Cloudinary delete error after the commit is logged and swallowed, as BUG-2202 / BUG-2100. Folded into BUG-2205's intended text. No new bug; status stays APPROVED.

> **Form.** As `tests/unit/services/help_ticket_service.spec.md`. The **Transaction contract TC1–TC6** is defined in `tests/unit/services/base_service.spec.md` and cited here. Below the service: `tests/unit/managers/mobile_upload_session_manager.spec.md` (APPROVED, verified PASS) and, through it, `tests/unit/managers/attachment_manager.spec.md` (**Parent-record rule PR-1 … PR-5**); `tests/unit/dao/base.spec.md` (`get`, used as `workspace_dao.get`). Their rules are cited, not restated.
>
> **Routed here and written as rules:** mobile manager FU-1 (a) BUG-2137 → `public_confirm` R3; (b) nothing more to pass for BUG-2131 / BUG-2134 (the manager reads the caller's role from `user.id`, PR-5 — checked), and `AttachmentNotFoundError` → 404 on create and promote → BUG-2203 (shared with the attachment service spec); (c) BUG-2139 → `cancel_session` R1, `promote_session` R1 (the lock is requested by this service); (d) `public_confirm` does not map `AttachmentValidationError` — unreachable, no rule; (e) `create_session` maps only `CloudinaryNotConfiguredError` → covered by BUG-2203 for the not-found case; any other error is a plain 500 (DataError of BUG-2132 is the manager's). Attachment manager FU-1 (d) (delete the Cloudinary file after the commit) applied here too → BUG-2205.
>
> **Read, not run.** Every rule was read in the code and in the approved manager specs (the manager's were partly run on `marker_test`). Nothing here needed a new database run.

## Review
> All items decided; nothing pending.

### Quick list — all decided
| # | What the code does today, in plain words | Decision | Decided by |
|---|---|---|---|
| D1 | A phone file over 10 MB is deleted in Cloudinary, but the cleared session is rolled back | bug — BUG-2137 (already logged): the cleared session is saved | mobile manager D8 |
| D2 | Promote and cancel read the session without a lock | bug — BUG-2139 (already logged): this service asks for the lock | HR-10 (house rule) |
| D3 | An attach that fails after the file was moved rolls back, so the session names the old place and the file is lost | bug — the state after the move and the failed attachment are saved → BUG-2204 | HR-13; BUG-2095 precedent |
| D4 | Cancel and re-sign delete the staged file before the change is saved | bug — the file is deleted only after the commit → BUG-2205 | attachment service D4 (BUG-2202) |
| D5 | A refused record on create / promote answers 500 | bug — 404 → BUG-2203 (endpoints, shared) | attachment service D5 |
| D6 | Polling a session or the phone page never saves "expired" | intended — mobile manager D13 | already decided |

### House-rule violations — applied automatically
- **HR-10** `cancel_session` R1, `promote_session` R1 — the session is read without a row lock, then checked and acted on (Cloudinary rename / delete, an attachment created).
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-2139 (already logged, pattern `hr-10-unlocked-state-transition`): this service reads the session with the new lock option of `get_for_creator` on these two paths. Rules: `cancel_session` R1, `promote_session` R1.
- **HR-13** `promote_session` R4 — a promote that fails verification after the file was moved: the manager has marked the new attachment `failed` with a ledger row and pointed the session at the moved file; the service rolls all of it back.
**Answer:** bug — per HR-13 (house rule)
**Resolution:** 🐞 BUG-2204 (pattern `failure-record-rolled-back`, per BUG-2095 / BUG-2137). Rules: `promote_session` R4.

Checked and **not** violated: **HR-4** — sessions have no soft delete; records are PR-1 (manager BUG-2130, BUG-2134). **HR-11** — the phone's "done" is verified with Cloudinary (manager ✅). **HR-16** — desktop paths are scoped by workspace and creator; the public paths are reached by token only and use the session's own workspace. **HR-1 … HR-3, HR-5 … HR-9, HR-12, HR-14, HR-15** — none applies.

**Permission checks:** desktop paths — the session's creator only (`get_for_creator`), plus PR-1 / PR-2 in the manager (BUG-2130, BUG-2131, BUG-2134). Public paths — the raw token only, no login (by design; `docs/future/permissions.md`).

### Decided items (Claude, under the reviewer's delegation, 2026-11-04)

### D3. An attach that fails after the move loses the file — 🐞 BUG-2204
**Background:** Attaching a phone file (`POST /mobile-upload/sessions/{id}/promote`) first moves the staged file in Cloudinary to the attachment's id, points the session at the new id, creates the attachment and then confirms it with Cloudinary. If the confirm refuses the file (lookup failed, wrong type, too large), the manager marks the attachment `failed`, writes a `failed` ledger row and raises `AttachmentConfirmError`. This service then rolls back everything. Cloudinary's move is not rolled back.
**What happens today:** The session again names the staging id, where no file is any more; the failed attachment and its ledger row vanish. Pressing Attach again answers "Cloudinary move failed: …" every time; the file sits at an id no row knows.
**Example:** Cloudinary's Admin API times out while Rahim attaches a phone photo. He presses Attach again and gets "Cloudinary move failed"; the photo is lost and nothing records the try.
**Rules affected:** `promote_session` R4
**Answer:** bug — as BUG-2095 for desktop confirm: when the promote raises `AttachmentConfirmError`, what the manager flushed is committed (the session pointing at the moved file, still `uploaded`; the `failed` attachment, its link and ledger rows), then the error is returned. A retry moves the file from where it now is. A move that itself failed (manager R8) wrote nothing, so nothing is committed.
**Resolution:** 🐞 BUG-2204 (pattern `failure-record-rolled-back`).

### D4. Cancel and re-sign delete the staged file before the change is saved — 🐞 BUG-2205
**Background:** Cancelling (`cancel_session`) deletes the session's staged file in Cloudinary; the phone's second sign (`public_sign` on a `waiting` session that already holds a file) deletes the earlier file. Both happen inside the manager, before this service commits. The attachment service has the same root (BUG-2202).
**What happens today:** If the transaction then fails, the session is rolled back and still names the deleted file. On re-sign this is reachable without a database fault: with `CLOUDINARY_API_SECRET` missing, the earlier file is deleted, then building the signature raises `CloudinaryNotConfiguredError` (503) and the session keeps the deleted id. On cancel it needs a failed commit; the session then stays `uploaded` and the desktop's Attach answers "Cloudinary move failed".
**Example:** The phone uploads `scan.pdf`, then picks a better photo while the server's Cloudinary secret is missing: 503, and `scan.pdf` is already gone though the session still names it.
**Rules affected:** `cancel_session` R3, `public_sign` R3
**Answer:** bug — the staged file is deleted only after the commit succeeded; a failed transaction calls Cloudinary's delete not at all and the session keeps its file. Combined with BUG-2140 (validate first) and BUG-2138 (cancel deletes a `waiting` session's file too).
**Resolution:** 🐞 BUG-2205 (pattern `external-delete-before-commit`, as BUG-2202). Fix spans the manager (`cancel_session`, `sign_staging_upload`: return the id to delete) and this service.

### D6. "Expired" is never saved — ✅ intended
Mobile manager D13: expiry is computed from `expires_at` on every read. `get_session` and `get_public_session` neither commit nor roll back (TC6); `cancel_session`, `promote_session`, `public_sign` and `public_confirm` roll back after the "expired" refusal. Rules: `get_session` R2, `get_public_session` R2, `cancel_session` R2 ✅.

## Overview
`MobileUploadService` is the transaction boundary of the QR flow: the desktop opens a session (`create_session`), polls it (`get_session`), attaches its file (`promote_session`) or cancels it (`cancel_session`); the phone, by token only, reads the session (`get_public_session`), gets a signed upload (`public_sign`) and confirms it (`public_confirm`). `app/api/v1/endpoints/mobile_upload.py` calls it and maps errors: every `MobileUploadSessionNotFoundError` → 404 "Upload session not found." (whatever its own message); `MobileUploadSessionError`, `AttachmentValidationError`, `AttachmentConfirmError`, `AttachmentLimitError` → 400 where caught; `CloudinaryNotConfiguredError` → 503. Every rule about the session and the file is the manager's; this service decides what is committed.

**Callables:** 7 specified · 3 not specified
**Externals to mock:** Cloudinary functions as imported in `app.managers.mobile_upload_session_manager` and `app.managers.attachment_manager` (`generate_upload_signature`, `get_resource`, `destroy_resource`, `rename_resource`, `update_resource_metadata`, `build_signed_delivery_url`); `utcnow` and `time.time` in the mobile manager; `settings` `CLOUDINARY_*`. Never call Cloudinary over the network. Also (verify finding 6, 2026-11-05): `app.dao.mobile_upload_session.utcnow` (the clock of `mark_expired_if_needed`; without it a session made with a fixed later time reads as expired), and `uuid.uuid4` and `secrets.token_urlsafe` as used by the mobile manager (staging id token, raw session token) for exact values.
**Integration-only behavior:** the endpoint mapping above (BUG-2203: `AttachmentNotFoundError` unmapped on create and promote → 500 today); rate limits (create 10/min, public 30 or 20/min); request-schema bounds (`token` 16–512, `file_name` ≤ 255, `note` ≤ 500, `entity_label` ≤ 80).

**Facts for the test designer**
- Import: `from app.services.mobile_upload_service import MobileUploadService, mobile_upload_service, MobileUploadSessionError, MobileUploadSessionNotFoundError, AttachmentConfirmError, AttachmentValidationError, CloudinaryNotConfiguredError`. Every parameter after `db` is keyword-only. The manager is the attribute `manager`; the attachment manager is `manager.attachment_mgr`.
- Request schemas (gap 1): `from app.schemas.mobile_upload import MobileUploadSessionCreateRequest, MobileUploadPromoteRequest, MobileUploadPublicSignRequest, MobileUploadPublicConfirmRequest` (the module the service imports them from).
- Requests: `MobileUploadSessionCreateRequest(entity_type, entity_id ≥ 1, entity_label ≤ 80 | None)`; `MobileUploadPromoteRequest(file_name ≤ 255 | None, note ≤ 500 | None)`; `MobileUploadPublicSignRequest(token 16–512, file_name 1–255, mime_type 1–128, file_size ≥ 1)`; `MobileUploadPublicConfirmRequest(token 16–512)`.
- Building sessions, parents and Cloudinary stubs: mobile manager spec **Notes**; attachment manager spec **Facts**.
- New option (intended, BUG-2139): `get_for_creator(…, for_update=True)` on the promote and cancel paths (mobile manager `get_for_creator` R5).

**Notes for the test designer**
- Transaction mechanics: `base_service.spec.md` Notes. "Committed": test-level `db.rollback()`, then re-select.
- **BUG-2137:** stub `get_resource` to return `bytes = 10 485 761`; `public_confirm` raises `AttachmentConfirmError`; after a test-level rollback the session intended has `public_id` and `asset_folder` `None`, status `waiting` → strict xfail.
- **BUG-2204:** an `uploaded` session; stub `rename_resource` to succeed and the attachment manager's `get_resource` to raise; `promote_session` raises `AttachmentConfirmError`; after a test-level rollback, intended: the session's `public_id` is the new attachment id, one attachment `failed` with a `failed` ledger row → strict xfail.
- **BUG-2205:** patch target, before and after the fix: `app.managers.mobile_upload_session_manager.destroy_resource`. The fixed code keeps calling it through that module's import, whichever layer (manager or service) calls it after the commit (gap 3). `public_sign` on a `waiting` session holding `public_id` P, with `CLOUDINARY_API_SECRET` empty → `CloudinaryNotConfiguredError`; intended: `destroy_resource` not called, the session still names P → strict xfail. Cancel: patch `db.commit` to raise → `destroy_resource` not called → strict xfail.
- **BUG-2139:** statement capture: the promote and cancel paths issue `SELECT … FOR UPDATE` on `mobile_upload_sessions` → strict xfail.

## Not specified
- `MobileUploadService.__init__` — stores the manager singleton, no logic.
- `mobile_upload_service`, `__all__` — module singleton and re-exports.
- `public_sign`'s "workspace not found" branch (source lines 154–156) — **not unit-testable**: `mobile_upload_sessions.workspace_id` is a NOT NULL foreign key with `ON DELETE CASCADE`, so a session always has its workspace; reachable only by patching the workspace DAO, which is not an external. Equivalent for unit purposes.

---

## `MobileUploadService.create_session(db, *, workspace, user, payload)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `POST /mobile-upload/sessions`, 201)

**Returns:** `MobileUploadSessionCreateResponse(session_id, token, expires_at, entity_label)` (manager `to_create_response` R1), built before the commit; `token` is the raw token, never stored.

**Rules:**
- **R1.** One session is created as manager `create_session` R1–R7 with `payload.entity_type`, `entity_id`, `entity_label` (BUG-1282, BUG-2130, BUG-2131, BUG-2132), and committed (TC1).
- **R2.** Any error rolls back, nothing written, and reaches the caller unchanged (TC3): `AttachmentNotFoundError` for a refused record (intended, BUG-2130 / BUG-2131), `DataError` for a long looked-up label (today, BUG-2132). [BUG-2203] At the API the not-found refusal answers 404 with its message. *(Today: unmapped → 500; integration-only.)* Commit failure: TC4.

**Errors:** unchanged from the manager. **Side effects:** one `mobile_upload_sessions` row, committed.

---

## `MobileUploadService.get_session(db, *, workspace_id, user_id, session_id)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `GET /mobile-upload/sessions/{id}`, the desktop's poll)

**Rules:**
- **R1.** The caller's own session of the workspace (manager `get_for_creator` R1, R4) is answered as manager `to_session_response` R1 (status, label, file data, preview URL; no Cloudinary id).
- **R2.** ✅ (D6) Unknown, another member's or another workspace's → `MobileUploadSessionNotFoundError("Upload session not found.")`; a `waiting` session past its time → `MobileUploadSessionNotFoundError("Upload session has expired.")`, its `expired` status in memory only. Read only (TC6): no commit, no rollback.

**Errors:** R2. **Side effects:** none

---

## `MobileUploadService.cancel_session(db, *, workspace_id, user_id, session_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `POST /mobile-upload/sessions/{id}/cancel`)

**Returns:** `MobileUploadSessionResponse` of the session after the commit.

**Rules:**
- **R1.** The session is found as `get_session` R1–R2, inside the transaction. [BUG-2139] It is read with a row lock (`get_for_creator(…, for_update=True)`). *(Today: no lock.)*
- **R2.** ✅ A not-found or expired refusal rolls back (nothing written; `expired` not saved) and reaches the caller unchanged.
- **R3.** The cancel is manager `cancel_session` R1–R6 (consumed → unchanged; otherwise `cancelled`; staged file deleted per R3 / BUG-2138; BUG-2136), committed (TC1). [BUG-2205] The staged file is deleted only after the commit succeeded; if the transaction fails, Cloudinary's delete is not called and the session keeps its status and `public_id`. *(Today: deleted inside the manager, before the commit.)*
- **R3a.** [BUG-2205] (2026-11-05) The delete runs right after the commit succeeded, before the response is built; an error of it is logged as a WARNING naming the `public_id` and the error and swallowed (mobile manager `_destroy_staging_asset` R3, BUG-2136; as attachment service `delete_attachment` R4a): the cancel still answers the cancelled session, never a 500 because of it.
- **R4.** Any other error rolls back and reaches the caller unchanged (TC3); commit failure TC4. TC5 is **not unit-testable** here (gap 2): there is no `db.refresh` after the commit, and the response is built by the manager's own `to_session_response`, which a card may not patch.

**Errors:** `MobileUploadSessionNotFoundError`. **Side effects:** session status (and BUG-2138 columns), committed; possibly one Cloudinary delete.

---

## `MobileUploadService.promote_session(db, *, workspace, user, session_id, payload)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `POST /mobile-upload/sessions/{id}/promote`)

**Purpose:** Attach the phone's file to the session's record.

**Returns:** the new attachment's `AttachmentResponse` (attachment manager `to_response` with `workspace.id`), built before the commit.

**Rules:**
- **R1.** The session is found as `cancel_session` R1–R2 (the caller's own, same workspace; not found / expired → rolled back, unchanged error). [BUG-2139] Read with a row lock. *(Today: no lock.)*
- **R2.** The promote is manager `promote_to_attachment` R1–R11 with `payload.file_name` and `payload.note`, the caller `user` (PR-5; BUG-2133, BUG-2134, BUG-2135, BUG-2136, BUG-2141). On success the attachment (`ready`), its link, ledger rows and activity entry, and the `consumed` session are committed together (TC1).
- **R3.** Every refusal before the move (session state, metadata, size, record and visibility, name and type, record full) rolls back and reaches the caller unchanged; nothing is written (TC3). [BUG-2203] `AttachmentNotFoundError` answers 404 at the API. *(Today: unmapped → 500; integration-only.)*
- **R4.** [BUG-2204] (D3, HR-13) When the promote raises `AttachmentConfirmError`, what the manager flushed is **committed**, then that same error reaches the caller: after a failed verification of the moved file, the session stays `uploaded` with `public_id` = the moved file's new id, and the `failed` attachment with its link and `pending` / `failed` ledger rows is saved. A failed move (manager R8) has written nothing, so nothing changes. *(Today: rolled back; the session names the staging id, where no file remains.)* If that commit fails, TC4.
- **R4a.** HR-13 versus TC3 (gap 4, decided by Claude under the reviewer's delegation (2026-11-04)): "commit, then raise" commits the session **as it stands**, so a change pending in the session that is unrelated to the promote is committed with the failure record. Each request owns its session, so in practice nothing unrelated is pending. TC3 (discard everything on an error) applies only to the errors where HR-13 does not, R3 and R5.
- **R5.** Every other error rolls back and reaches the caller unchanged (TC3), e.g. `AttachmentLimitError` today after the move (BUG-2133), `CloudinaryNotConfiguredError`. Commit failure on success: TC4.

**Errors:** `MobileUploadSessionNotFoundError`, `MobileUploadSessionError`, `AttachmentValidationError`, `AttachmentNotFoundError` (intended), `AttachmentLimitError`, `AttachmentConfirmError`, `CloudinaryNotConfiguredError` — unchanged.

**Side effects:** Cloudinary rename and metadata update (manager); attachment rows; session `consumed`; committed.

---

## `MobileUploadService.get_public_session(db, *, raw_token)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `GET /mobile-upload/public?token=…`, no login)

**Rules:**
- **R1.** The session of that token, in any workspace (manager `get_by_raw_token` R1, R3), is answered as manager `to_public_response` R1 (`status`, `entity_label`, `expires_at` only).
- **R2.** ✅ (D6) Unknown token → `MobileUploadSessionNotFoundError("Upload session not found.")`; `consumed` / `cancelled` → `"Upload session is no longer available."`; past its time → `"Upload session has expired."` (in memory only). Read only (TC6).

**Errors:** R2. **Side effects:** none

---

## `MobileUploadService.public_sign(db, *, payload)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `POST /mobile-upload/public/sign`, 201, no login)

**Returns:** the manager's `MobileUploadPublicSignResponse` (manager `sign_staging_upload` R7), built before the commit.

**Rules:**
- **R1.** The session is found by `payload.token` as `get_public_session` R1–R2, inside the transaction; a refusal rolls back and reaches the caller unchanged.
- **R2.** The signing is manager `sign_staging_upload` R1–R7 for that session in the session's own workspace (`session.workspace_id`, whatever workspace the token's holder belongs to), with `payload.file_name`, `mime_type`, `file_size` (BUG-2140). The new staging columns are committed (TC1).
- **R3.** [BUG-2205] (D4) An earlier staged file of the session is deleted only after the commit succeeded; when the transaction fails (e.g. `CloudinaryNotConfiguredError` from the signature, manager R6, raised after the flush), Cloudinary's delete is not called and the session keeps its earlier `public_id` and `asset_folder`. *(Today: the earlier file is deleted inside the manager, then the rollback restores the session's pointer to the deleted file.)*
- **R3a.** [BUG-2205] (2026-11-05) That delete runs right after the commit succeeded; an error of it is logged as a WARNING naming the `public_id` and the error and swallowed (as `cancel_session` R3a): the sign response is still returned.
- **R4.** Every error rolls back (nothing of the new sign saved) and reaches the caller unchanged (TC3); commit failure TC4.

**Errors:** `MobileUploadSessionNotFoundError`, `MobileUploadSessionError`, `AttachmentValidationError`, `CloudinaryNotConfiguredError` — unchanged.

**Side effects:** session staging columns, committed; one signature; possibly one Cloudinary delete (after the commit, intended).

---

## `MobileUploadService.public_confirm(db, *, payload)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `POST /mobile-upload/public/confirm`, no login)

**Returns:** `MobileUploadPublicSessionResponse` of the session after the commit (status `uploaded`).

**Rules:**
- **R1.** The session is found by `payload.token` as `public_sign` R1.
- **R2.** The verification is manager `confirm_staging_upload` R1–R6 (BUG-2141); on success the session becomes `uploaded` with the verified `format`, `version`, `file_size` (and `mime_type`), committed (TC1).
- **R3.** [BUG-2137] When the manager raises `AttachmentConfirmError`, what it flushed is **committed**, then that same error reaches the caller: for a file over 10 485 760 bytes the session is saved `waiting` with `public_id` and `asset_folder` `None` (its file deleted, manager R5). The other confirm refusals (lookup failed R3, wrong type R4) change nothing, so nothing is saved. *(Today: rolled back; the session keeps the deleted file's `public_id`, and a second confirm answers "Cloudinary verification failed: …".)* If that commit fails, TC4.
- **R3a.** HR-13 versus TC3, as `promote_session` R4a: the commit of R3 takes the session as it stands, unrelated pending changes included (none in practice); TC3 applies to R4's errors only.
- **R4.** Every other error rolls back and reaches the caller unchanged (TC3): `MobileUploadSessionNotFoundError`, `MobileUploadSessionError` (not `waiting`, not prepared), `CloudinaryNotConfiguredError` (BUG-2141). Commit failure on success: TC4. TC5 is **not unit-testable** (gap 2): no `db.refresh`, and the response is the manager's own `to_public_response`.

**Errors:** as R3, R4. **Side effects:** session columns, committed; one Cloudinary lookup; possibly one delete (manager R5).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 47–57 | manager create; response; commit | `create_session` R1 |
| 58–60 | any exception → rollback, re-raise | `create_session` R2 |
| 70–76 | `get_for_creator`; response (no commit) | `get_session` R1, R2 |
| 87–92 | `get_for_creator` (no lock: BUG-2139) | `cancel_session` R1, R2 |
| 93–95 | manager cancel (delete before commit: BUG-2205); commit; response | `cancel_session` R3, R4 |
| 96–98 | any exception → rollback, re-raise | `cancel_session` R2, R4 |
| 110–115 | `get_for_creator` (no lock: BUG-2139) | `promote_session` R1 |
| 116–123 | manager promote | `promote_session` R2, R3 |
| 124–130 | `to_response`; commit | `promote_session` R2 |
| 131–133 | any exception → rollback (failure after the move lost: BUG-2204) | `promote_session` R3, R4, R4a, R5 |
| 141–142 | `get_by_raw_token`; public response (no commit) | `get_public_session` R1, R2 |
| 151 | `get_by_raw_token` | `public_sign` R1 |
| 154–156 | workspace `None` → not found | Not specified (not unit-testable) |
| 157–166 | manager sign (earlier file deleted before commit: BUG-2205); commit | `public_sign` R2, R3 |
| 167–169 | any exception → rollback, re-raise | `public_sign` R3, R4 |
| 178–181 | `get_by_raw_token`; manager confirm; commit; public response | `public_confirm` R1, R2 |
| 182–184 | any exception → rollback (cleared session lost: BUG-2137) | `public_confirm` R3, R3a, R4 |
| 187–196 | singleton, re-exports | Not specified |

## Gap log
- G1 (mobile_upload_service.cases.md gap 1) — Fact — Facts: request schemas import from `app.schemas.mobile_upload`.
- G2 (gap 2) — Fact — `cancel_session` R4, `public_confirm` R4: TC5 not unit-testable (no `db.refresh`; responses built by the manager's own mappers). Decided by Claude under the reviewer's delegation (2026-11-04).
- G3 (gap 3) — Fact / Intent — Notes BUG-2205: `destroy_resource` stays imported in `app.managers.mobile_upload_session_manager` after the fix; tests patch it there. Decided by Claude under the reviewer's delegation (2026-11-04).
- G4 (gap 4) — Intent — `promote_session` R4a, `public_confirm` R3a: HR-13's commit takes the session as it stands (unrelated pending changes included; none in practice); TC3 applies to the other errors only. Decided by Claude under the reviewer's delegation (2026-11-04).
- G5 (mobile_upload_service.verify.md finding 6) — Fact — Externals to mock: DAO `utcnow`, `uuid.uuid4`, `secrets.token_urlsafe` added. Plus, decided by Claude under the reviewer's delegation (2026-11-05): `cancel_session` R3a, `public_sign` R3a — post-commit delete error logged and swallowed, as BUG-2202; folded into BUG-2205.
