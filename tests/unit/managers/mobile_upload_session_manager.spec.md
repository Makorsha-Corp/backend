# Spec — `app/managers/mobile_upload_session_manager.py`

> **Status:** APPROVED (2026-11-04; nothing open. Every question decided by Claude under the reviewer's delegation (2026-11-04), or already settled upstream: OQ-5, OQ-11, OQ-12, OQ-18, HR-10, HR-16, BUG-1282, BUG-1713.)
> **Source commit:** e48a092
> **Revision 2026-11-04 (verifier R2-1):** `promote_to_attachment`: the parent-record 404 (R4) now comes before the size check (R3) and the name / type / limit checks; folded into BUG-2134. Status stays APPROVED.
> **Revision 2026-11-04 (fill-gaps, cases gaps 1–5):** no `role` parameter (attachment manager PR-5: the caller is the existing `user`; the manager reads the active role and platform-admin flag itself). `rename_resource`'s return value is not read. `_promote_file_name` R4 folded into BUG-2135 (after the fix nothing raises). BUG-1282's clock named. Work-order soft-delete columns: attachment manager Facts. No new bug. Status stays APPROVED.

> **Below / above.** Below: `tests/unit/dao/mobile_upload_session.spec.md` (APPROVED: `_naive_utc`, `get_by_token_hash`, `get_for_creator`, `mark_expired_if_needed`, **Model facts**; its FU-1 and FU-2 are answered here) and `tests/unit/managers/attachment_manager.spec.md` (written in parallel: `normalize_upload_request`, `build_public_id`, `resolve_entity_label`, `build_asset_folder`, `build_display_name`, `create_pending_attachment`, `confirm_attachment`, `to_response`, and the **Parent-record rule PR-1 … PR-3**). Their rules are **cited, not restated**. Above: `app/services/mobile_upload_service.py` and `app/api/v1/endpoints/mobile_upload.py` (no spec yet), which own the transaction, the commit / rollback and the HTTP mapping.
>
> **Standing decisions applied here (not asked again):** OQ-5 / OQ-18 (owner: attachments follow the record's visibility; hidden records answer 404) → BUG-2131, BUG-2134. HR-16 → BUG-2130. OQ-11 / OQ-12 (Cloudinary ids are minted and verified by the server, never taken from the client) → stated as intended rules (✅) below. BUG-1282 (DAO Q1) → `create_session` R4, `_naive_utc`. BUG-1713 precedent → BUG-2136.
>
> **Run on `marker_test` (rolled back, Cloudinary patched; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\att\probe_mobile.py`, 2026-11-04):** a 120-character item name as label → `DataError` (StringDataRightTruncation, `varchar(80)`); a session for project id 999999 is created with label `project-999999`; `_promote_file_name` with a 255-character name → 255 characters with no extension, with `"."` → `JPG`; `promote_to_attachment` with the record full → `rename_resource` and `update_resource_metadata` already called when `AttachmentLimitError` is raised; `_ensure_active` on an `uploaded` session past its time → "Upload session has expired." and status `expired` in memory. Everything else read, not run.

## Review
> All decided; nothing pending.

### Quick list — all decided
| # | What the code does today, in plain words | Decision | Decided by |
|---|---|---|---|
| D1 | A QR session can be opened for a record that does not exist, is deleted, or belongs to another workspace | bug — refused as not found (PR-1, HR-16) → BUG-2130 | house rule HR-16 + PR-1 |
| D2 | A QR session can be opened for a private project, component or someone else's help ticket | bug — refused as not found (PR-2, OQ-5) → BUG-2131 | owner, OQ-5 (applied by Claude) |
| D3 | A long record name as the session's label crashes the request (500) | bug — the label is cut to 80 characters → BUG-2132 | Claude, delegated |
| D4 | Attaching a phone upload moves the file in Cloudinary before checking whether the attachment is allowed | bug — every refusal comes before the move → BUG-2133 | Claude, delegated |
| D5 | Attaching does not re-check that the record still exists and may be opened | bug — PR-1 / PR-2 checked at attach time, before the move → BUG-2134 | Claude, delegated (consequence of OQ-5) |
| D6 | A long or dot-only new file name loses the file's extension and the attach fails | bug — the extension is always kept → BUG-2135 | Claude, delegated |
| D7 | Failed Cloudinary deletes / metadata updates leave no trace | bug — still swallowed, logged as WARNING → BUG-2136 | BUG-1713 precedent |
| D8 | A phone file over 10 MB is deleted in Cloudinary, but the session keeps pointing at it (the clearing is rolled back) | bug — the cleared session is saved → BUG-2137 (service) | Claude, delegated |
| D9 | Cancelling a waiting session leaves a file the phone already uploaded in Cloudinary | bug — any staged file is deleted on cancel → BUG-2138 | Claude, delegated |
| D10 | Two attach (or attach + cancel) requests on one session race on the same file | bug — HR-10 row lock → BUG-2139 | house rule HR-10 |
| D11 | A bad re-sign request deletes the phone's previous upload before it is refused | bug — validate first, then delete → BUG-2140 | Claude, delegated |
| D12 | "Cloudinary not configured" during confirm / attach answers 400 instead of 503 | bug — passes through as not-configured → BUG-2141 | `lossy-error-mapping` precedent |
| D13 | "Expired" is never saved to the database | intended — expiry is computed on every read | Claude, delegated (DAO FU-1 (a)) |
| D14 | Cancelling an already consumed session answers with the session, no error | intended — cancel is idempotent; the file belongs to the attachment now | Claude, delegated |
| D15 | Every Cloudinary id used here is minted by the server and read from the session row | intended (OQ-11, OQ-12) | owner rule, confirmed |
| D16 | Staged files of sessions that expire, fail verification or are never attached stay in Cloudinary | not a rule here — no clean-up job exists (FU-2) | Claude, delegated |

### House-rule violations — applied automatically
- **HR-16** `create_session` R5 — the session's `(entity_type, entity_id)` is never looked up: another workspace's record id is accepted (and a missing or deleted one). Intended: PR-1 of `attachment_manager.spec.md`, 404 `<entity_type> <entity_id> not found.`, nothing written.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-2130 (pattern `cross-workspace-link-not-refused`). Rules: `create_session` R5.
- **HR-10** `promote_to_attachment` R11, `cancel_session` R6 — both check the session's state and then act on its Cloudinary file (rename, destroy) and create an attachment, with no row lock. Two promotes at once: the second's rename fails on a moved file and answers "Cloudinary move failed: …" instead of "No file is ready on this session."; promote and cancel at once: cancel destroys the staged file while promote moves it. Intended: the session is read `FOR UPDATE` on the promote and cancel paths; the loser sees the new state and gets the normal error.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-2139 (pattern `hr-10-unlocked-state-transition`). Rules: `promote_to_attachment` R11, `cancel_session` R6. The lock is taken where the session is read (`get_for_creator`, new `for_update` option, used by the service's promote and cancel).

Checked and **not** violated: **HR-1** — a client label is trimmed and a blank one is replaced (`resolve_entity_label` R1–R2); file names go through `sanitize_file_name`. **HR-2, HR-3, HR-5, HR-6, HR-7, HR-8** — no names to keep unique, no lists, paging or `LIKE`. **HR-4** — sessions have no soft delete; the parent's soft delete is PR-1 (BUG-2130). **HR-9** — no "changed by" field. **HR-11** — the phone's "done" is never trusted: `confirm_staging_upload` asks Cloudinary server-to-server (R3–R6) ✅. **HR-12, HR-15** — no money. **HR-13** — staging is a pre-step with no business record; the attachment made at promote has its own ledger (attachment_manager spec). **HR-14** — no batch. **HR-16** — `get_for_creator` is scoped to workspace and creator; `get_by_raw_token` is unscoped by design (the token is the access, DAO spec R1); the public sign uses the session's own workspace.

### Precedent matches — all applied
- **BUG-1282** (`create_session` R4, `_naive_utc` R2, `_ensure_active` R3) — `expires_at` written as aware UTC, compared by its true moment. Already logged; its row names this manager. DAO FU-2 answered here.
- **BUG-1713** → 🐞 BUG-2136 (`_destroy_staging_asset` R3, `promote_to_attachment` R9): a failed Cloudinary call that is swallowed still logs a WARNING naming the `public_id` and the error. Pattern `swallowed-error-unlogged`.
- **`lossy-error-mapping`** → 🐞 BUG-2141 (`confirm_staging_upload` R3, `promote_to_attachment` R8): `CloudinaryNotConfiguredError` raised inside the Cloudinary call is wrapped as `AttachmentConfirmError` (400). Intended: it passes through unchanged (503 at the endpoint, which already maps it), nothing written. Same root as `AttachmentManager.confirm_attachment` (attachment_manager spec).

### Decided items (Claude, under the reviewer's delegation, 2026-11-04)

### D2. A QR session can be opened for a record the caller may not open — 🐞 BUG-2131
**Background:** A QR session lets a phone upload one file to a record (purchase order, project, help ticket, …). The owner ruled (OQ-5) that attachments follow the record's visibility and a hidden record answers 404 (OQ-18 keeps 403 only for project pages). The desktop sign path is already logged (BUG-1870 projects, BUG-1950 tickets).
**What happens today:** `create_session` checks nothing about the record. A `ground-team` member who gets 403 on a private project can open a QR session for it, and later attach the file.
**Example:** Karim may not open the private project "Tender 2027". He opens a QR session with `entity_type=project`, `entity_id=<Tender 2027>`; the answer is 201 with the label "Tender 2027", which also tells him the project's name.
**Rules affected:** `create_session` R6
**Resolution:** applied from OQ-5 (owner): PR-2 of `attachment_manager.spec.md`; refused like a missing record, nothing written. The caller is the existing `user`; the manager reads the active role and platform-admin flag itself (attachment manager PR-5). 🐞 BUG-2131 (pattern `child-ignores-parent-visibility`).

### D3. A long record name as the label crashes the request — 🐞 BUG-2132
**Background:** `entity_label` is `varchar(80)`. A label sent by the client is cut to 80 characters; the label the server looks up (project, component, machine, item name: unbounded text) is not.
**What happens today:** Verified: an item named with 120 characters gives `DataError` (value too long for type character varying(80)) at the flush → 500.
**Example:** Machine "Heidelberg Speedmaster XL 106 … (95 characters)". Opening a QR session from its page fails with "Internal Server Error".
**Rules affected:** `resolve_entity_label` R3
**Resolution:** decided: the looked-up label is cut to its first 80 characters as well. 🐞 BUG-2132 (pattern `unchecked-column-length`).

### D4. The file is moved before the attach is known to be allowed — 🐞 BUG-2133
**Background:** Promoting moves the staged file to the attachment's id in Cloudinary (`rename_resource`), then creates the attachment. Creating it checks the record's 25-attachment limit (and, after BUG-2130/2131's attachment counterparts, the record). The service rolls back on any error, but Cloudinary does not.
**What happens today:** Verified: with the record full, `rename_resource` and `update_resource_metadata` have run when `AttachmentLimitError` is raised. After the rollback the session still names the old staging id, which no longer exists; every retry answers "Cloudinary move failed: …" and the file sits at an id no row knows.
**Example:** A purchase order already has 25 files. Rahim photographs a 26th; Attach answers "This record already has the maximum of 25 attachments." He deletes an old file and presses Attach again: "Cloudinary move failed". The photo is lost.
**Rules affected:** `promote_to_attachment` R5
**Resolution:** decided: every refusal that does not need Cloudinary (state, metadata, size, type/name, record and visibility, capacity) happens before the move; a refusal moves nothing and leaves the session `uploaded` with its staging id. 🐞 BUG-2133 (pattern `external-call-before-validation`, new).

### D5. Attaching does not re-check the record — 🐞 BUG-2134
**Background:** Up to the attach, minutes (or, for an uploaded session, any time later: DAO Q2) may pass. The record may be deleted or made private meanwhile.
**What happens today:** The session's record is never looked at; the attachment is linked to whatever `(entity_type, entity_id)` the session holds.
**Example:** A project is soft-deleted at 10:05; the desktop attaches the 10:02 photo at 10:06 — 200, the photo is linked to the deleted project.
**Rules affected:** `promote_to_attachment` R4
**Resolution:** decided as a consequence of OQ-5 and PR-1: PR-1 and PR-2 are checked at promote time, before the move (BUG-2133); refused → 404 `<entity_type> <entity_id> not found.`, nothing moved, session unchanged. The caller is the existing `user`; role read per PR-5. 🐞 BUG-2134 (pattern `child-ignores-parent-visibility`).

### D6. A long or dot-only new name loses the extension — 🐞 BUG-2135
**Background:** On attach the user may rename the file; the original extension is kept and appended. The result is cleaned and cut to 255 characters.
**What happens today:** Verified: a 255-character name gives 255 characters with the `.JPG` cut off; `"."` gives `JPG`. Either then fails the type check: 400 "File name must include a supported extension.".
**Example:** Rahim pastes a long description as the file name (the field allows 255); Attach answers that the file name must include an extension, which he never typed.
**Rules affected:** `_promote_file_name` R5, R6
**Resolution:** decided: the extension always survives: the base is shortened so that `<base>.<ext>` fits 255 characters; a base that is empty after cleaning falls back to the original name. 🐞 BUG-2135 (pattern `derived-name-loses-extension`, new).

### D8. A file over 10 MB: deleted, but the session keeps pointing at it — 🐞 BUG-2137
**Background:** The phone's sign request declares a size, but Cloudinary accepts any size. `confirm_staging_upload` reads the real size; over 10 MB it deletes the file in Cloudinary, clears the session's `public_id` / `asset_folder` and raises. The service (`public_confirm`) then rolls back.
**What happens today:** The clearing is rolled back; the session stays `waiting` with the `public_id` of a deleted file. A second confirm answers "Cloudinary verification failed: …" instead of the size message. (Read, not run: needs the service.)
**Example:** The phone uploads a 14 MB video renamed `.jpg`. The page shows "File too large"; pressing confirm again shows a Cloudinary error.
**Rules affected:** `confirm_staging_upload` R5 (the manager does it right; the loss is in the service)
**Resolution:** decided: the cleared session is saved even though the request fails (the service commits the clearing before raising, or the manager returns a refusal the service commits). Logged against `app/services/mobile_upload_service.py` for its future spec. 🐞 BUG-2137 (pattern `failure-record-rolled-back`, new).

### D9. Cancelling a waiting session leaves the phone's file in Cloudinary — 🐞 BUG-2138
**Background:** A session is `waiting` from creation until the phone's confirm succeeds. The phone may have signed and uploaded a file that is not confirmed yet (or failed verification); the session then holds its `public_id`.
**What happens today:** `cancel_session` deletes the staged file only for `uploaded` sessions; a `waiting` one keeps it in Cloudinary for ever, and `public_id` is never cleared.
**Example:** The phone uploads a photo; before it confirms, the user cancels on the desktop. The photo stays in the company's Cloudinary storage with nothing pointing at it.
**Rules affected:** `cancel_session` R3, R4
**Resolution:** decided: cancelling deletes any staged file the session holds (`public_id` set, whatever the status other than `consumed`) and clears `public_id` / `asset_folder`. 🐞 BUG-2138 (pattern `orphaned-external-file`, new).

### D11. A bad re-sign request deletes the previous upload first — 🐞 BUG-2140
**Background:** A phone may sign again while the session is `waiting` (retry); the previously staged file is then deleted.
**What happens today:** The delete runs before the new request is validated. A refused request (wrong type, too big) has already deleted the previous file; after the rollback the session still names it.
**Example:** The phone uploads `scan.pdf`, then the user picks `notes.docx` declared as `application/pdf` by mistake: 400, and `scan.pdf` is gone though the session still names it; confirming fails.
**Rules affected:** `sign_staging_upload` R3
**Resolution:** decided: the request is validated first; the previous file is deleted only once the new request is accepted. 🐞 BUG-2140 (pattern `external-call-before-validation`).

### D13. "Expired" is never saved — ✅ intended
**Background:** DAO FU-1 (a): `_ensure_active` and `get_for_creator` set `status = expired` in memory and raise; the service does not commit, so the row stays `waiting`.
**Decision:** intended. Every reader computes expiry from `expires_at`; no report reads the column. A future clean-up job must use `expires_at`, not `status` (FU-2). Rules: `_ensure_active` R4 ✅, `get_for_creator` R3 ✅.

### D14. Cancelling a consumed session — ✅ intended
**Decision:** the call returns the session unchanged, no error (a double-click after attach is harmless; the file now belongs to the attachment and must not be deleted). Rule: `cancel_session` R1 ✅.

### D15. Cloudinary ids are the server's — ✅ intended (OQ-11, OQ-12)
**Decision:** every `public_id` this manager signs, verifies, renames or deletes is minted by `build_staging_public_id` / `AttachmentManager.build_public_id` and read back from the session row; no request field can name one. The phone's sign request carries only file name, MIME type and size. Rules: `sign_staging_upload` R5 ✅, `confirm_staging_upload` R2 ✅, `_destroy_staging_asset` R1 ✅, `promote_to_attachment` R7 ✅.

## Follow-ups for other reviews
| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Mobile upload service / endpoint** (`app/services/mobile_upload_service.py`, `app/api/v1/endpoints/mobile_upload.py`; no spec yet) | (a) BUG-2137: commit the cleared session on the too-large refusal. (b) BUG-2131 / BUG-2134: nothing more to pass: the manager reads the caller's active role (BUG-1885) and platform-admin flag from `user.id` (attachment manager PR-5); map `AttachmentNotFoundError` to 404 on create and promote (today unmapped → 500). (c) BUG-2139: read the session `FOR UPDATE` on promote and cancel. (d) `public_confirm` does not map `AttachmentValidationError` (unreachable: the staged name always has an extension). (e) `create_session` maps only `CloudinaryNotConfiguredError`; any other error is a bare 500. | D2, D5, D8, HR-10 |
| FU-2 | **Clean-up (no owner yet)** | Staged files stay in Cloudinary when a session expires before confirm or attach, when the phone's file fails verification and the user gives up, when an uploaded session is never attached (it never expires on the desktop, DAO Q2), and when an attach fails after the move (verification of the moved file). Session rows are never deleted. A periodic job would delete sessions past `expires_at` (by time, D13) that are not `consumed`, with their staged file. Not a rule of this module. | D16 |
| FU-3 | **Attachment manager** (parallel spec) | Same roots, for consistency: `confirm_attachment` wraps `CloudinaryNotConfiguredError` (BUG-2141 pattern `lossy-error-mapping`); its failure writes are rolled back by the service (BUG-2137 pattern `failure-record-rolled-back`). | D8, D12 |

## Overview
`MobileUploadSessionManager` carries one file from a phone to a record via a short-lived QR session. The desktop user opens a session for a record (`create_session`) and gets a secret token; the phone, with no login, uses the token to get a signed Cloudinary upload into a staging id (`sign_staging_upload`), then asks the server to verify it (`confirm_staging_upload`). The desktop polls (`get_for_creator`, `to_session_response`) and finally promotes the staged file into a normal attachment (`promote_to_attachment`, which moves the file and uses `AttachmentManager`), or cancels. Callers: `MobileUploadService` only. The manager flushes but never commits; the service commits or rolls back. It is meant to protect: only the token holder reaches the phone steps; only the creator, in their workspace, reaches the desktop steps; nothing is trusted from the phone without Cloudinary's confirmation.

Session lifecycle: `waiting` → (`confirm`) `uploaded` → (`promote`) `consumed`; `waiting` / `uploaded` → (`cancel`) `cancelled`; `expired` is computed (D13). Statuses: `MobileUploadSessionStatusEnum` (`waiting`, `uploaded`, `consumed`, `cancelled`, `expired`).

**Callables:** 23 specified (82 rules) · 3 not specified
**Externals to mock:** Cloudinary functions as imported in `app.managers.mobile_upload_session_manager`: `generate_upload_signature`, `get_resource`, `destroy_resource`, `rename_resource`, `update_resource_metadata`, `build_signed_delivery_url`; `utcnow` and `time.time` in that module; `secrets.token_urlsafe` and `uuid.uuid4` for exact values; `settings` (`CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_UPLOAD_ENV`, `ENVIRONMENT`) on `app.core.config.settings`. `AttachmentManager` is real (its own Cloudinary calls are patched in `app.managers.attachment_manager`) or injected through `MobileUploadSessionManager(attachment_mgr=…)`.
**Integration-only behavior:** HTTP mapping (every `MobileUploadSessionNotFoundError` → 404 "Upload session not found."; `MobileUploadSessionError`, `AttachmentValidationError`, `AttachmentConfirmError`, `AttachmentLimitError` → 400; `CloudinaryNotConfiguredError` → 503), rate limits, the service's commit / rollback (BUG-2137), `workspace_dao.get` in `public_sign`.

**Facts for the test designer**
- Import: `from app.managers.mobile_upload_session_manager import MobileUploadSessionManager, mobile_upload_session_manager, MobileUploadSessionNotFoundError, MobileUploadSessionError, MOBILE_UPLOAD_TOKEN_BYTES, SESSION_TTL_MINUTES, _naive_utc`. Errors from `app.utils.attachment_allowlist`: `AttachmentValidationError`, `AttachmentConfirmError`, `MAX_FILE_SIZE_BYTES` (= 10 485 760). `CloudinaryNotConfiguredError`, `AUTHENTICATED_DELIVERY_TYPE` (= `"authenticated"`) from `app.core.cloudinary_client`. `AttachmentLimitError`, `AttachmentNotFoundError` from `app.managers.attachment_manager`.
- `MobileUploadSessionNotFoundError` is a `LookupError`; `MobileUploadSessionError` a `ValueError`.
- `MOBILE_UPLOAD_TOKEN_BYTES = 32`, `SESSION_TTL_MINUTES = 10`.
- Table and columns: DAO spec **Model facts**. `entity_label` `varchar(80)`, `file_name` 255, `mime_type` 128, `resource_type` / `format` / `status` / `delivery_type` 16, `public_id` / `asset_folder` 512.
- Settings defaults: `ENVIRONMENT = "development"`, `CLOUDINARY_UPLOAD_ENV = "development"`.
- Parent-record rule PR-1 … PR-3, the not-found message and who may open what: `attachment_manager.spec.md` Overview.

**Notes for the test designer**
- Build sessions directly (`MobileUploadSession(workspace_id, created_by, entity_type, entity_id, token_hash, expires_at, status, …)`), flush. Use aware UTC `expires_at` or `SET LOCAL TIME ZONE 'UTC'` unless the case is about BUG-1282 (DAO spec Notes).
- Patch `app.managers.mobile_upload_session_manager.utcnow` for every expiry case; `time.time` for `timestamp`.
- **BUG-2133 / BUG-2134 / BUG-2140 / BUG-2138:** assert on the recorded calls of the patched Cloudinary functions (no `rename_resource` / `destroy_resource` call at all on a refusal) and on the session's attributes in the session without a rollback → strict xfail.
- **BUG-2137:** the manager part (R5 of `confirm_staging_upload`) passes today; the bug is a service case. At manager level only R5 is tested.
- **BUG-2139:** as other HR-10 bugs: check that the promote / cancel path issues `SELECT … FOR UPDATE` on `mobile_upload_sessions` (statement capture), strict xfail.
- **BUG-2136:** `caplog` at WARNING for `app.managers.mobile_upload_session_manager`, message containing the `public_id`; strict xfail.

## Not specified
- `MobileUploadSessionManager.__init__` — wires `attachment_mgr` (the given one, else the `attachment_manager` singleton); no logic.
- `mobile_upload_session_manager` — module singleton.
- `MobileUploadSessionNotFoundError`, `MobileUploadSessionError` — empty exception classes.

---

## `_naive_utc(value)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `_ensure_active`)

**Purpose:** Make a stored `expires_at` comparable with `utcnow()`. A copy of the DAO's `_naive_utc`.

**Rules:**
- **R1.** Behaves exactly as DAO `_naive_utc` R1.
- **R2.** [BUG-1282] As DAO `_naive_utc` R2: an aware value is converted to UTC, then its zone removed. *(Today: zone removed, no conversion.)*

**Errors:** none · **Side effects:** none

---

## `MobileUploadSessionManager._hash_token(raw_token)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `create_session_token`, `get_by_raw_token`)

**Rules:**
- **R1.** Returns the SHA-256 hex digest of the UTF-8 token: 64 lowercase hex characters, equal to `app.core.security.hash_refresh_token(raw_token)`; the same input always gives the same output; `""` is hashed too.

**Errors:** none · **Side effects:** none

---

## `MobileUploadSessionManager._upload_env()` and `._is_production()`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `build_staging_public_id`, `build_staging_asset_folder`)

**Rules:**
- **R1.** `_upload_env` is `settings.CLOUDINARY_UPLOAD_ENV` when it is non-empty, otherwise `settings.ENVIRONMENT`.
- **R2.** `_is_production` is `True` only when that value is exactly `"production"` (`"Production"`, `" production"` are not).

**Errors:** none · **Side effects:** none

---

## `MobileUploadSessionManager.build_staging_public_id(*, workspace_id, session_id)`
**Shape:** compute · **Persistence:** pure · **Visibility:** public (used by: `sign_staging_upload`)

**Rules:**
- **R1.** In production: `ws-<workspace_id>/mobile-staging/<session_id>/<token>`, `<token>` being 32 lowercase hex characters, new on every call.
- **R2.** Otherwise the same, prefixed with `<upload env>/` (e.g. `development/ws-7/mobile-staging/12/<token>`).

**Errors:** none · **Side effects:** none

---

## `MobileUploadSessionManager.build_staging_asset_folder(*, workspace_name, session_id)`
**Shape:** compute · **Persistence:** pure · **Visibility:** public (used by: `sign_staging_upload`)

**Rules:**
- **R1.** In production: `<workspace_name>/Mobile Staging/session-<session_id>`; the name is used as given.
- **R2.** Otherwise the same, prefixed with `Dev/`.

**Errors:** none · **Side effects:** none

---

## `MobileUploadSessionManager.create_session_token()`
**Shape:** compute · **Persistence:** pure · **Visibility:** public (used by: `create_session`)

**Rules:**
- **R1.** Returns `(raw, hash)`: `raw` is `secrets.token_urlsafe(32)` (43 URL-safe characters), `hash` is `_hash_token(raw)`. Two calls give different tokens.

**Errors:** none · **Side effects:** none

---

## `MobileUploadSessionManager.resolve_entity_label(session, *, workspace, entity_type, entity_id, entity_label)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (used by: `create_session`)

**Purpose:** The label shown on the phone page for the session's record.

**Rules:**
- **R1.** A client label with any non-space character is returned trimmed and cut to its first 80 characters (cut after trimming).
- **R2.** `None`, `""` or whitespace only: the label is `AttachmentManager.resolve_entity_label(workspace_id=workspace.id, …)` (attachment_manager spec): the record's number or name, or `<entity_type>-<entity_id>` when not found / `scratch`.
- **R3.** [BUG-2132] A looked-up label longer than 80 characters is cut to its first 80. *(Today: returned whole; `create_session` then fails at the flush with `DataError`, 500. Verified.)*

**Errors:** none of its own · **Side effects:** none

---

## `MobileUploadSessionManager.create_session(db, *, workspace, user, entity_type, entity_id, entity_label)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `MobileUploadService.create_session`)

**Purpose:** Open a QR upload session for one record.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace` | `Workspace` | caller's workspace |
| `user` | `Profile` | creator |
| `entity_type` | `AttachmentEntityTypeEnum` | any value, `scratch` included |
| `entity_id` | int | schema `>= 1`; not looked up today |
| `entity_label` | str \| None | schema ≤ 80 |

**Returns:** `(session row, raw token)`; the row flushed, not committed. Only the hash is stored.

**Rules:**
- **R1.** A row is created with `workspace_id = workspace.id`, `created_by = user.id`, `entity_type` = the enum's value, `entity_id`, `entity_label` = `resolve_entity_label`'s result, `token_hash` = hash of the returned raw token, `status = "waiting"`, `delivery_type = "authenticated"`; `public_id`, `asset_folder`, `resource_type`, `format`, `version`, `file_name`, `mime_type`, `file_size` NULL; `created_at` / `updated_at` the database's `now()`.
- **R2.** The raw token is returned and never stored; `_hash_token(raw) == row.token_hash`.
- **R3.** `expires_at` is now + exactly 10 minutes.
- **R4.** [BUG-1282] `expires_at` is written as an aware UTC moment, so the stored instant is now + 10 minutes whatever the session's `TimeZone`. The clock is this module's `utcnow` (`app.managers.mobile_upload_session_manager.utcnow`, read once per call), made aware with `tzinfo=timezone.utc`; `_ensure_active` compares against the same module `utcnow` after the DAO's fixed `_naive_utc` conversion. Patch that name for a fixed NOW (gap 4). *(Today: naive `utcnow()`, read by Postgres in the session's `TimeZone`; DAO Q1.)*
- **R5.** [BUG-2130] PR-1: an `(entity_type, entity_id)` that is unknown, belongs to another workspace, or is soft-deleted (project, machine, work order; a component whose project is deleted) raises `AttachmentNotFoundError("<entity_type> <entity_id> not found.")` and writes nothing. `scratch` is never looked up. *(Today: accepted; the label falls back to `<entity_type>-<entity_id>`. Verified for an unknown project.)*
- **R6.** [BUG-2131] PR-2: a record the caller may not open (private project, its component, a help ticket `can_access_ticket` refuses) raises the same error, nothing written. *(Today: accepted, and the label shows the record's name; the role and platform-admin flag are read from `user.id` per attachment manager PR-5.)*
- **R7.** Each call creates a new session, even for the same user and record; nothing limits open sessions per user (the endpoint rate-limits 10 per minute).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R5, R6 (intended) | `AttachmentNotFoundError` | `<entity_type> <entity_id> not found.` |
| looked-up label > 80 (today) | `sqlalchemy.exc.DataError` | — (BUG-2132) |

**Side effects:** one `mobile_upload_sessions` row, flushed.

---

## `MobileUploadSessionManager.to_create_response(session, raw_token)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** public (used by: `MobileUploadService.create_session`)

**Rules:**
- **R1.** Returns `MobileUploadSessionCreateResponse(session_id=session.id, token=raw_token, expires_at=session.expires_at, entity_label=session.entity_label)`.

**Errors:** none · **Side effects:** none

---

## `MobileUploadSessionManager._ensure_active(session)`
**Shape:** validator · **Persistence:** pure (changes the instance only) · **Visibility:** internal (used by: `get_by_raw_token`)

**Purpose:** The phone may only use a session that is still open.

**Rules:**
- **R1.** Status `consumed`, `cancelled` or `expired` raises `MobileUploadSessionNotFoundError("Upload session is no longer available.")`, whatever `expires_at`; the status is not changed.
- **R2.** Otherwise (`waiting`, `uploaded`), `expires_at` at or before now (`<=`: exactly now is expired) sets `session.status = "expired"` and raises `MobileUploadSessionNotFoundError("Upload session has expired.")`. Verified for `uploaded`.
- **R3.** Expiry compares through `_naive_utc` (R2, BUG-1282).
- **R4.** ✅ (D13) The `expired` status is set in memory only; nothing is flushed, and through the service it is never saved.
- **R5.** Otherwise the same instance is returned unchanged.

**Errors:** see R1, R2 · **Side effects:** R2's in-memory status only.

---

## `MobileUploadSessionManager.get_by_raw_token(db, *, raw_token)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: `MobileUploadService.get_public_session`, `public_sign`, `public_confirm`)

**Rules:**
- **R1.** The session whose `token_hash` equals `_hash_token(raw_token)` is found in any workspace (DAO `get_by_token_hash` R1); no login, the token is the access.
- **R2.** No session with that hash raises `MobileUploadSessionNotFoundError("Upload session not found.")`.
- **R3.** A found session passes through `_ensure_active` (R1–R5) and is returned.

**Errors:** R2; `_ensure_active` R1, R2 · **Side effects:** none of its own.

---

## `MobileUploadSessionManager.get_for_creator(db, *, session_id, workspace_id, user_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: `MobileUploadService.get_session`, `cancel_session`, `promote_session`)

**Rules:**
- **R1.** Returns the session with that id, of that workspace, created by that user (DAO `get_for_creator` R1). Another workspace's session, another member's session or an unknown id raises `MobileUploadSessionNotFoundError("Upload session not found.")`.
- **R2.** A `waiting` session past its time is marked `expired` (DAO `mark_expired_if_needed` R1–R5a) and raises `MobileUploadSessionNotFoundError("Upload session has expired.")`.
- **R3.** ✅ (D13) That status stays in memory; nothing is flushed.
- **R4.** ✅ (DAO Q2) An `uploaded` session past its time is returned (the desktop may still attach). `consumed` and `cancelled` sessions are returned too.
- **R5.** [BUG-2139] On the promote and cancel paths the row is read with a row lock (`FOR UPDATE`). *(Today: never locked; requires a new option.)*

**Errors:** R1, R2 · **Side effects:** none of its own.

---

## `MobileUploadSessionManager._staging_preview_url(session)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal (used by: `to_session_response`)

**Purpose:** A small signed preview of a staged image for the desktop.

**Rules:**
- **R1.** `None` unless the status is `uploaded`.
- **R2.** `None` when `public_id`, `version` or `format` is missing (`None`, `""`, `0`).
- **R3.** `None` unless `mime_type`, lower-cased, starts with `image/`; PDFs (`application/pdf`) and a missing type give `None`.
- **R4.** Otherwise the signed delivery URL of `public_id` with `resource_type` (default `image`), `delivery_type` (default `authenticated`), `version` as int, `format`, and the transformation `[{"width": 400, "crop": "limit"}]`.
- **R5.** Any error while building it (e.g. Cloudinary not configured) gives `None`, nothing raised. Intended: a missing preview must not break the poll.

**Errors:** none · **Side effects:** none

---

## `MobileUploadSessionManager.to_session_response(session)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** public (used by: `MobileUploadService.get_session`, `cancel_session`)

**Rules:**
- **R1.** Returns `MobileUploadSessionResponse` with `id`, `status` and `entity_type` as their enums, `entity_id`, `entity_label`, `expires_at`, `file_name`, `mime_type`, `file_size` from the row, and `preview_url = _staging_preview_url(session)`. No Cloudinary id is sent.

**Errors:** a status or type outside the enums raises `ValueError` (not reachable: written by code) · **Side effects:** none

---

## `MobileUploadSessionManager.to_public_response(session)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** public (used by: `MobileUploadService.get_public_session`, `public_confirm`)

**Rules:**
- **R1.** Returns `MobileUploadPublicSessionResponse(status=<enum>, entity_label, expires_at)` only: no ids, no workspace, no file data reach the phone page.

**Errors:** as `to_session_response` · **Side effects:** none

---

## `MobileUploadSessionManager.normalize_public_sign(*, file_name, mime_type, file_size)`
**Shape:** validator · **Persistence:** pure · **Visibility:** public (used by: `sign_staging_upload`)

**Rules:**
- **R1.** Validates the phone's file exactly as a desktop upload: the result and errors of `AttachmentManager.normalize_upload_request` (attachment_manager spec) for a `scratch` request with entity id 1 and these three values.
- **R2.** Values outside `AttachmentSignRequest`'s limits (`file_name` 1–255, `mime_type` 1–128, `file_size >= 1`) raise Pydantic `ValidationError`; not reachable through the API (the public schema has the same limits).

**Errors:** `AttachmentValidationError` (too large, bad name, unsupported extension, MIME mismatch); `ValidationError` (R2) · **Side effects:** none

---

## `MobileUploadSessionManager.sign_staging_upload(db, *, session, workspace, file_name, mime_type, file_size)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `MobileUploadService.public_sign`)

**Purpose:** Give the phone a signed Cloudinary upload into a fresh staging id.

**Returns:** `MobileUploadPublicSignResponse`; the session flushed, not committed.

**Rules:**
- **R1.** A session whose status is not `waiting` raises `MobileUploadSessionError("This session already received a file.")`, nothing changed, no Cloudinary call.
- **R2.** A `waiting` session that already holds a `public_id` (an earlier sign) has that staged file deleted (`_destroy_staging_asset`) and the new id replaces it.
- **R3.** [BUG-2140] The request is validated (`normalize_public_sign`) before any earlier staged file is deleted; a refused request deletes nothing and leaves `public_id` / `asset_folder` as they were. *(Today: the earlier file is deleted and `public_id` / `asset_folder` set to `None` first, then the refusal is raised.)*
- **R4.** An accepted request sets on the session: `public_id` = `build_staging_public_id(workspace.id, session.id)`, `asset_folder` = `build_staging_asset_folder(workspace.name, session.id)`, `resource_type` (from the file type: `image` for images and PDF, `raw` for docx / xlsx / txt / csv), `file_name` (sanitized), `mime_type` (as sent), `file_size` (as declared by the phone), and flushes. `status` stays `waiting`.
- **R5.** ✅ (OQ-11) The `public_id` is minted here; nothing in the request names it.
- **R6.** With `CLOUDINARY_CLOUD_NAME` or `CLOUDINARY_API_KEY` empty, raises `CloudinaryNotConfiguredError("Cloudinary cloud name and API key are required.")` after R4's flush (the service rolls back). A missing `CLOUDINARY_API_SECRET` raises `CloudinaryNotConfiguredError` from the signature.
- **R7.** The response: `cloud_name`, `api_key` from settings; `timestamp = int(time.time())`; `public_id`, `asset_folder` as stored; `display_name = AttachmentManager.build_display_name(<sanitized file name>)`; `type = "authenticated"`; `signature` = the upload signature of `public_id`, `asset_folder`, `display_name`, `timestamp`, `type`; `resource_type`; `upload_url = https://api.cloudinary.com/v1_1/<cloud_name>/<resource_type>/upload`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R1 | `MobileUploadSessionError` | `This session already received a file.` |
| invalid file | `AttachmentValidationError` | normalize's message |
| R6 | `CloudinaryNotConfiguredError` | `Cloudinary cloud name and API key are required.` |

**Side effects:** session columns of R4, flushed; possibly one `destroy_resource` (R2); one signature.

---

## `MobileUploadSessionManager.confirm_staging_upload(db, *, session)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `MobileUploadService.public_confirm`)

**Purpose:** Verify with Cloudinary that the phone's file arrived and is what was signed.

**Rules:**
- **R1.** Status other than `waiting` raises `MobileUploadSessionError("This session already received a file.")`; no Cloudinary call. Missing `public_id` or `file_name` (`None` or `""`) raises `MobileUploadSessionError("Upload was not prepared.")`.
- **R2.** ✅ (OQ-11, HR-11) The file is fetched from Cloudinary server-to-server by the session's own `public_id`, `resource_type` (default `image`) and `delivery_type` (default `authenticated`); the phone's word is never taken.
- **R3.** Any error of that fetch raises `AttachmentConfirmError("Cloudinary verification failed: <error>")`; the session is unchanged and stays `waiting`. [BUG-2141] `CloudinaryNotConfiguredError` raised there passes through unchanged. *(Today: wrapped as `AttachmentConfirmError`, 400 instead of 503.)*
- **R4.** The fetched resource must match the file name's extension (`validate_cloudinary_resource`: Cloudinary `resource_type` equal to the type's, `format` among its allowed formats, compared lower-case); otherwise its `AttachmentConfirmError` is raised and the session is unchanged (the staged file stays; FU-2).
- **R5.** Cloudinary `bytes` over 10 485 760 (strictly): the staged file is deleted (`_destroy_staging_asset`), `public_id` and `asset_folder` set to `None` and flushed, `status` stays `waiting`, and `AttachmentConfirmError("File too large (<bytes> bytes). Maximum is 10485760 bytes.")` is raised. Exactly 10 485 760 passes. *(BUG-2137: the service rolls this clearing back; the intended end state is this rule's, saved.)*
- **R6.** Otherwise: `format` and `version` from the resource; `file_size` = Cloudinary `bytes`, or the declared size when `bytes` is missing or `0`; `mime_type` becomes `application/pdf` when Cloudinary says `resource_type = image` and `format = pdf`, else unchanged; `status = "uploaded"`; flushed; the session returned.

**Errors:** R1, R3, R4, R5 · **Side effects:** R5 or R6 columns, flushed; R5 one `destroy_resource`.

---

## `MobileUploadSessionManager._destroy_staging_asset(session)`
**Shape:** helper · **Persistence:** pure (Cloudinary only) · **Visibility:** internal (used by: `sign_staging_upload`, `confirm_staging_upload`, `cancel_session`)

**Rules:**
- **R1.** ✅ (OQ-11) With a `public_id` (truthy), deletes exactly that id from Cloudinary with the session's `resource_type` (default `image`) and `delivery_type` (default `authenticated`). It never changes the session.
- **R2.** No `public_id` (`None`, `""`): no call.
- **R3.** Any error of the delete is swallowed; nothing is raised. [BUG-2136] A WARNING naming the `public_id` and the error is logged. *(Today: no log.)*

**Errors:** none · **Side effects:** one `destroy_resource` call.

---

## `MobileUploadSessionManager.cancel_session(db, *, session)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `MobileUploadService.cancel_session`)

**Rules:**
- **R1.** ✅ (D14) A `consumed` session is returned unchanged: no flush, no Cloudinary call, no error.
- **R2.** Any other status ends `cancelled`, flushed, and the session is returned. A `cancelled` session is cancelled again (no error).
- **R3.** An `uploaded` session's staged file is deleted (`_destroy_staging_asset`).
- **R4.** [BUG-2138] Any session other than `consumed` that holds a `public_id` has that staged file deleted, and `public_id` / `asset_folder` are set to `None`. *(Today: only `uploaded` sessions' files are deleted, and `public_id` is never cleared: a `waiting` session's signed (maybe uploaded) file stays in Cloudinary.)*
- **R5.** A failed delete does not stop the cancel (`_destroy_staging_asset` R3).
- **R6.** [BUG-2139] The session was read with a row lock (`get_for_creator` R5), so a concurrent promote either finishes first (then R1) or waits. *(Today: no lock.)*

**Errors:** none · **Side effects:** `status` (and R4 columns), flushed; possibly one `destroy_resource`.

---

## `MobileUploadSessionManager._promote_file_name(session, requested)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `promote_to_attachment`)

**Purpose:** The attachment's file name: the user's new name with the original extension.

**Rules:**
- **R1.** `requested` `None`, `""` or whitespace only: the staged `file_name` as it is (`upload.jpg` if the session has none; not reachable from promote).
- **R2.** The original extension is the text after the last `.` of the staged name, case kept (`photo.JPG` → `JPG`); `jpg` if it has no dot (not reachable from promote).
- **R3.** Otherwise `requested` is trimmed; if it has a `.`, everything from its last `.` on is dropped; the result is `sanitize_file_name("<base>.<ext>")` (`/` and `\` → `-`, control and `<>:"|?*` characters removed, outer spaces and dots stripped, first 255 characters). Verified: `"x.png"` on `photo.JPG` → `x.JPG`.
- **R4.** [BUG-2135] Nothing here raises. *(Today: reachable only with a hand-built session whose staged `file_name` ends in `.` (e.g. `photo.`; the sign path never stores one, its names are sanitized) and a requested name of only removable characters (e.g. `"?"`): `"?."` sanitizes to nothing and raises `AttachmentValidationError("Invalid file name.")`. After the fix R6 gives the staged name instead. Decided by Claude under the reviewer's delegation (2026-11-04), gap 3.)* Former text: a name that sanitizes to nothing raises `AttachmentValidationError("Invalid file name.")`.
- **R5.** [BUG-2135] The result always ends in `.<ext>`: when `<base>.<ext>` is longer than 255, the base is shortened to fit. *(Today: the whole string is cut at 255, losing the extension; promote then fails 400 "File name must include a supported extension.". Verified.)*
- **R6.** [BUG-2135] A base that is empty after cleaning (e.g. `"."`, `".."`, `"  .x"`) gives the staged name, as R1. *(Today: `"."` gives `JPG`. Verified.)*

**Errors:** R4 · **Side effects:** none

---

## `MobileUploadSessionManager.promote_to_attachment(db, *, session, workspace, user, file_name, note)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `MobileUploadService.promote_session`)

**Purpose:** Turn the staged phone file into a ready attachment of the session's record.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `MobileUploadSession` | from `get_for_creator` (caller's own, same workspace) |
| `file_name` | str \| None | schema ≤ 255; optional new name |
| `note` | str \| None | schema ≤ 500 |

**Returns:** the `Attachment`, `ready`, flushed, not committed.

**Rules (in the intended order: R1–R6 refuse before any Cloudinary call):**
- **R1.** Status other than `uploaded` raises `MobileUploadSessionError("No file is ready on this session.")`, nothing changed, no Cloudinary call.
- **R2.** Missing `public_id`, `file_name` or `mime_type` raises `MobileUploadSessionError("Staging metadata is incomplete.")`, same.
- **R3.** Stored `file_size` over 10 485 760 raises `AttachmentValidationError("File too large (<size> bytes). Maximum is 10485760 bytes.")`, same. A missing size counts as 0; the attachment request uses `max(size, 1)`. Checked only after R4 passes (R4 order note).
- **R4.** [BUG-2134] PR-1 and PR-2 of `attachment_manager.spec.md` are checked for the session's `(entity_type, entity_id)` now: a record deleted, unknown, of another workspace, or one the caller may not open raises `AttachmentNotFoundError("<entity_type> <entity_id> not found.")`; nothing moved, the session stays `uploaded` with its staging id. *(Today: never checked; the role and platform-admin flag are read from `user.id` per attachment manager PR-5.)* **Order (verifier R2-1, decided by Claude under the reviewer's delegation (2026-11-04), as attachment PR-4):** checked after R1–R2 (the caller's own session state) and **before R3** and every name, type and limit check of R5, so a hidden record answers this 404 even when its staged file is too large or of a bad type, and never reveals anything about the file. *(Today: R3 comes first and R4 does not exist.)*
- **R5.** [BUG-2133] Every refusal that needs no Cloudinary call — R1–R4, the name and type check (`_promote_file_name`, `AttachmentManager.normalize_upload_request`) and the record's attachment limit (`AttachmentLimitError`, `AttachmentManager.assert_entity_attachment_capacity`) — is raised before `rename_resource` is called; a refusal leaves no Cloudinary call and the session unchanged. *(Today: the limit is checked inside `create_pending_attachment`, after the move and the metadata update. Verified.)*
- **R6.** The attachment request is: the session's entity type and id, the promoted name (`_promote_file_name`), the session's `mime_type`, `max(file_size, 1)`, `note`; it is normalized by `AttachmentManager.normalize_upload_request` (its errors raised).
- **R7.** ✅ (OQ-11) (`rename_resource`'s return value is not read: any return, e.g. `{}`, gives the same result; gap 2.) The file is moved in Cloudinary from the session's staging `public_id` to a new id from `AttachmentManager.build_public_id(workspace.id)`, with the session's `resource_type` (else the normalized one) and `delivery_type` (else `authenticated`); no id comes from the request.
- **R8.** A failed move raises `AttachmentConfirmError("Cloudinary move failed: <error>")`; the session is unchanged. [BUG-2141] `CloudinaryNotConfiguredError` passes through unchanged. *(Today: wrapped, 400.)*
- **R9.** After the move, `session.public_id` = the new id and `asset_folder` = `AttachmentManager.build_asset_folder(workspace.name, entity type, AttachmentManager.resolve_entity_label(…))` (the server's label, not the session's), flushed. Cloudinary's folder and display name (`build_display_name` of the normalized name) are then updated; an error there is swallowed and the promote goes on. [BUG-2136] That error is logged as a WARNING naming the new `public_id`. *(Today: no log.)*
- **R10.** The attachment is created by `AttachmentManager.create_pending_attachment` (with `stored_public_id` = the new id, that folder, `user`) and confirmed by `AttachmentManager.confirm_attachment` (`performed_by = user.id`) — rows, ledger entries and the record's "Attached …" activity entry as the attachment_manager spec says. Their errors are raised as they are.
- **R11.** On success the session becomes `consumed` with `public_id = None` (the file now belongs to the attachment); `asset_folder` keeps the attachment's folder; flushed. [BUG-2139] The session was read with a row lock (`get_for_creator` R5): a second promote of the same session waits, then gets R1. *(Today: no lock; the second's move fails, R8.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R1 | `MobileUploadSessionError` | `No file is ready on this session.` |
| R2 | `MobileUploadSessionError` | `Staging metadata is incomplete.` |
| R3 | `AttachmentValidationError` | `File too large (<size> bytes). Maximum is 10485760 bytes.` |
| R4 (intended) | `AttachmentNotFoundError` | `<entity_type> <entity_id> not found.` |
| name / type | `AttachmentValidationError` | normalize's / sanitize's message |
| record full | `AttachmentLimitError` | `This record already has the maximum of 25 attachments.` (with the configured number) |
| R8 | `AttachmentConfirmError` | `Cloudinary move failed: <error>` |
| confirm fails | `AttachmentConfirmError` | `confirm_attachment`'s message |

**Side effects:** one rename and one metadata update in Cloudinary; one attachment, link, two ledger rows and activity entries (attachment_manager spec); session `public_id`, `asset_folder`, `status`, flushed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 53 | `value.tzinfo is not None` | `_naive_utc` R1, R2 |
| 73 | sha256 hex | `_hash_token` R1 |
| 76 | `CLOUDINARY_UPLOAD_ENV or ENVIRONMENT` | `_upload_env` R1 |
| 79 | `== "production"` | `_is_production` R2 |
| 84 | production / prefixed | `build_staging_public_id` R1, R2 |
| 90 | production / `Dev/` | `build_staging_asset_folder` R1, R2 |
| 95–96 | token + hash | `create_session_token` R1 |
| 107 | client label non-blank | `resolve_entity_label` R1, R2 |
| 108 | `strip()[:80]` | `resolve_entity_label` R1 |
| 109 | looked-up label uncut | `resolve_entity_label` R3 (BUG-2132) |
| 126–149 | create row; no record lookup | `create_session` R1–R7 (R5, R6 bugs) |
| 134 | `utcnow() + 10 min` | `create_session` R3, R4 |
| 165–170 | final statuses | `_ensure_active` R1 |
| 171–173 | `expires_at <= now` | `_ensure_active` R2, R3, R4 |
| 174 | return | `_ensure_active` R5 |
| 179–180 | not found | `get_by_raw_token` R2 |
| 181 | `_ensure_active` | `get_by_raw_token` R3 |
| 197–198 | not found | `get_for_creator` R1 |
| 199–201 | mark expired; `== expired` | `get_for_creator` R2, R3, R4 |
| 191 | no lock | `get_for_creator` R5 (BUG-2139) |
| 205 | status != uploaded | `_staging_preview_url` R1 |
| 207 | public_id / version / format falsy | `_staging_preview_url` R2 |
| 210 | not `image/` or pdf | `_staging_preview_url` R3 |
| 212–222 | build / except → None | `_staging_preview_url` R4, R5 |
| 225–236 | mapping | `to_session_response` R1 |
| 239–243 | mapping | `to_public_response` R1 |
| 252–259 | scratch request, normalize | `normalize_public_sign` R1, R2 |
| 271–272 | status != waiting | `sign_staging_upload` R1 |
| 274–277 | earlier public_id destroyed before validation | `sign_staging_upload` R2, R3 (BUG-2140) |
| 279–301 | normalize, mint, write, flush | `sign_staging_upload` R4, R5 |
| 303–304 | cloud name / key missing | `sign_staging_upload` R6 |
| 306–328 | signature, response | `sign_staging_upload` R7 |
| 336–337 | status != waiting | `confirm_staging_upload` R1 |
| 338–339 | public_id / file_name falsy | `confirm_staging_upload` R1 |
| 341–348 | fetch; any error wrapped | `confirm_staging_upload` R2, R3 (BUG-2141) |
| 350 | resource vs extension | `confirm_staging_upload` R4 |
| 352–361 | `bytes > MAX` | `confirm_staging_upload` R5 (BUG-2137 in service) |
| 363–365 | format, version, size `or` | `confirm_staging_upload` R6 |
| 366–367 | image + pdf → mime | `confirm_staging_upload` R6 |
| 368–371 | uploaded, flush | `confirm_staging_upload` R6 |
| 374–375 | no public_id | `_destroy_staging_asset` R2 |
| 376–383 | destroy; swallow | `_destroy_staging_asset` R1, R3 (BUG-2136) |
| 386–387 | consumed → return | `cancel_session` R1 |
| 388–389 | uploaded → destroy | `cancel_session` R3, R4 (BUG-2138) |
| 390–393 | cancelled, flush | `cancel_session` R2, R5, R6 |
| 396 | `file_name or "upload.jpg"` | `_promote_file_name` R1 |
| 397 | has dot / `jpg` | `_promote_file_name` R2 |
| 398–399 | requested blank | `_promote_file_name` R1 |
| 401–402 | drop requested extension | `_promote_file_name` R3, R6 |
| 403 | sanitize (cut 255, may raise) | `_promote_file_name` R3, R4, R5 |
| 415–416 | status != uploaded | `promote_to_attachment` R1 |
| 417–418 | metadata falsy | `promote_to_attachment` R2 |
| 420–424 | size > MAX; `or 0` | `promote_to_attachment` R3 |
| 426–435 | name, request (`max(size,1)`), normalize | `promote_to_attachment` R6, R5 |
| 436–451 | dest id, label, folder, display name, types | `promote_to_attachment` R7, R9 |
| 452–460 | rename; any error wrapped | `promote_to_attachment` R7, R8 (BUG-2141) |
| 462–465 | session → dest, flush | `promote_to_attachment` R9 |
| 467–476 | metadata; swallow | `promote_to_attachment` R9 (BUG-2136) |
| 478–486 | create pending (capacity after move) | `promote_to_attachment` R5, R10 (BUG-2133); no record check R4 (BUG-2134) |
| 487–492 | confirm | `promote_to_attachment` R10 |
| 494–498 | consumed, public_id None, flush | `promote_to_attachment` R11 |

## Gap log
- G1 (mobile_upload_session_manager.cases.md gap 1) — Intent — `attachment_manager.spec.md` PR-5: no `role` parameter; the caller is the existing `user` of `create_session` and `promote_to_attachment`; the manager reads the active role and `is_platform_admin` itself. Cards drop `role=`. Decided by Claude under the reviewer's delegation (2026-11-04), consistent with the project manager and discussion service.
- G2 (gap 2) — Fact — `promote_to_attachment` R7: `rename_resource`'s return value is not read (keyword names in attachment manager Facts).
- G3 (gap 3) — Contradiction — `_promote_file_name` R4 tagged BUG-2135: intended "nothing raises"; today's raise needs a hand-built staged name ending in `.` plus a requested name of only removable characters, so one strict-xfail card covers it. Decided by Claude under the reviewer's delegation (2026-11-04); no new ID.
- G4 (gap 4) — Fact — `create_session` R4: the fixed code reads this module's `utcnow`, made aware UTC; patch `app.managers.mobile_upload_session_manager.utcnow`.
- G5 (gap 5) — Fact — PR-1 reads only `is_deleted`; a real work-order delete also writes `deleted_at` (database `now()` in the DAO) and `deleted_by` (attachment manager Facts, "Soft-deleted parents").
- G6 (mobile_upload_session_manager.verify.md R2-1, 2026-11-04) — Intent — `promote_to_attachment` R4 precedes R3 and the name / type / limit checks (after R1–R2), so a hidden record never reveals its file; consistent with attachment PR-4; part of BUG-2134. Decided by Claude under the reviewer's delegation (2026-11-04).
