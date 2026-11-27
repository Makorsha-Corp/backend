# Spec — `app/managers/attachment_manager.py`

> **Status:** APPROVED (2026-11-04; nothing open. Owner answers OQ-5, OQ-11, OQ-12, OQ-18 and HR-16 applied; every other question decided by Claude under the reviewer's delegation (2026-11-04).)
> **Source commit:** e48a092
> **Revision 2026-11-04 (fill-gaps, cases gaps 1–8):** caller parameters fixed for all three attachment specs (new **PR-5**: no `role` parameter; the manager reads the caller's active role and platform-admin flag itself, as `ProjectManager` and the discussion service do; `get_pdf_page_image` gains a required `user_id`). PR-2 says the manager does no membership check of its own (the API gate does). PR-3 says only links in the caller's workspace count, and an attachment with none answers 404. `confirm_attachment` with `performed_by=None` checks the uploader. Facts added: parent builder columns, activity tables' parent-id columns, enum import path, Cloudinary keyword names, `derive_urls` / `links` shapes, the `deleted_at` clock. No new bug; BUG-2091's intended text now carries the PR-3 link rule. Status stays APPROVED.
> **Revision 2026-11-04 (verifier findings 2, 3, 5; decided by Claude under the reviewer's delegation (2026-11-04)):** PR-2: the workspace owner (`workspaces.owner_user_id`) opens every help ticket of their workspace whatever their membership role (🐞 BUG-2103 in `HelpTicketManager.can_access_ticket`). PR-4: the parent-record refusal comes before every error or early return that depends on the attachment's state or the input. Part of BUG-2091's intended behaviour. No other rule changed.
> **Revision 2026-11-04 (case designer gap 9):** Overview "Integration-only behavior" no longer lists the help-ticket role lookup; per PR-5 the manager reads the role itself. No rule changed.

> **Below / above.** Below: `tests/unit/dao/attachment.spec.md` (`get_active`, `soft_delete`), `tests/unit/dao/attachment_link.spec.md` (count, list, links of an attachment, `AttachmentLinkCreateSchema`), `tests/unit/dao/attachment_ledger.spec.md`, `tests/unit/dao/base.spec.md` (`create`, `update`, `get_by_id_and_workspace`), `tests/unit/utils/attachment_allowlist.spec.md` (`normalize_upload_request`, `validate_cloudinary_resource`, BUG-120…125), `tests/unit/core/cloudinary_client.spec.md` (signature, signed URLs, `_ensure_configured`), and the `log_event` rules of `project_manager.spec.md`, `machine_activity_manager.spec.md`, `project_component_activity_manager.spec.md`, `account_invoice_manager.spec.md` (`_log_event`), `sales_manager.spec.md`, `expense_order_manager.spec.md`. DAO and helper rules are **cited, not restated**. Above: `AttachmentService` (`app/services/attachment_service.py`, no spec yet; it owns commit / rollback), `MobileUploadSessionManager` (`tests/unit/managers/mobile_upload_session_manager.spec.md`), `AttachmentMarkupManager` (`tests/unit/managers/attachment_markup_manager.spec.md`, which imports this module's errors). Both sibling specs cite the **Parent-record rule** below.
>
> **Standing decisions applied here (not asked again):** OQ-5 (owner, 2026-11-04: attachments follow the record's own visibility; a member who cannot open a private project or a help ticket gets 404) → BUG-1870 (projects and components), BUG-1950 (help tickets), and BUG-2091 below for actions by attachment id. OQ-18 (owner: project pages keep 403; attached records answer 404). HR-16 (nothing links across workspaces) → BUG-2090. OQ-11 / OQ-12 (owner: Cloudinary ids are verified, never trusted from the client) → every Cloudinary id this module signs, verifies, renames or deletes is minted here and read from our own row (rules marked ✅ OQ-11). BUG-1434 (failed uploads do not hold a place), BUG-1433 (links ordered by `id`), BUG-1091 / BUG-1192 (`log_event` refuses another workspace's parent), BUG-124 (confirm with an extension no longer allowed).
>
> **Read, not run.** Every rule was read in the code. Checked by running Python only (no database): `AttachmentUpdateInternal(...).model_dump(exclude_unset=True)` keeps explicit `None` values and a field set after construction (`mime_type`); `build_display_name`, `build_public_id`, `build_asset_folder` outputs (scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\att\pyd_check.py`).

## Review
> All questions decided; nothing pending. Each item lists the decision and who made it.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | An upload can be signed for a record that does not exist, is deleted, or belongs to another workspace | bug — refused as "not found" (BUG-2090) | HR-16; Claude, delegated for unknown / deleted |
| Q2 | Reading a PDF page, confirming or deleting an attachment by id ignores who may open its record | bug — 404 as a missing attachment (BUG-2091) | consequence of OQ-5 / OQ-18 |
| Q3 | Confirm never checks the real file size; the phone path does | bug — over 10 MB is refused and the file removed (BUG-2092) | Claude, delegated |
| Q4 | An upload confirmed after a failed try never says "Attached …" on the record | bug — the first successful confirm writes it (BUG-2093) | Claude, delegated |
| Q5 | Two confirms at once both write "ready" and "Attached …" | bug — HR-10 (BUG-2094) | house rule |
| Q6 | A failed confirm is recorded, then the service rolls the record back | bug — HR-13, the failure is kept (BUG-2095, service) | house rule |
| Q7 | Cloudinary not configured at confirm marks the user's upload failed and answers 400 | bug — 503, nothing written (BUG-2096) | Claude, delegated |
| Q8 | Deleting an attachment already deleted deletes it again | bug — 404, nothing written (BUG-2097) | attachment DAO P2 / FU-1 (a) |
| Q9 | Deleting an upload that never became ready writes "Removed …" on the record | bug — only a ready attachment gives "Removed" (BUG-2098) | Claude, delegated |
| Q10 | Deleting a pending or failed upload leaves its file in Cloudinary | bug — the file is deleted whatever the state (BUG-2099) | Claude, delegated |
| Q11 | A failed Cloudinary delete leaves no trace | bug — WARNING logged (BUG-2100) | BUG-1713 precedent |
| Q12 | With the API key missing, building URLs raises instead of returning none | bug — empty URLs (BUG-2101) | Claude, delegated |
| Q13 | The note of an upload has no length limit (the phone path allows 500) | bug — at most 500 characters (BUG-2102, schema) | Claude, delegated |
| Q14 | `scratch` uploads need no record and are open to every member | intended — owner's test playground; note for permissions | Claude, delegated |
| Q15 | The capacity check can be passed by two signs at once | intended — a soft cap; no lock (HR-10 scope) | Claude, delegated |
| Q16 | Every response shows the attachment's Cloudinary `public_id` | intended — after BUG-1864 / 1865 an id grants nothing; note for permissions | consequence of OQ-11 |

### House-rule violations — applied automatically
- **HR-16** `create_pending_attachment` R1a — the parent `(entity_type, entity_id)` is never looked up: another workspace's purchase order id is linked under the caller's workspace (the label falls back to `purchase_order-<id>`; BUG-1091 verified the same on machines). Intended: refused as not found (Parent-record rule PR-1).
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-2090 (pattern `cross-workspace-link-not-refused`), together with unknown and soft-deleted parents (Q1). Rules: `create_pending_attachment` R1a.
- **HR-10** `confirm_attachment` R10 — reads the attachment without a lock, checks `pending`, then writes `ready`, a ledger row and an activity entry on every parent: duplicate side effects. Intended: the attachment is read `FOR UPDATE`; the loser sees `ready` and returns it unchanged (R2).
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-2094 (pattern `hr-10-unlocked-state-transition`). Rules: `confirm_attachment` R10.
- **HR-13** `confirm_attachment` R4, R5 — the manager marks the attachment `failed` and writes a `failed` ledger row with the reason, then raises; `AttachmentService.confirm_upload` rolls the transaction back, so neither survives (read). Intended: the failure record is committed even though the request fails.
**Answer:** bug — per HR-13 (house rule)
**Resolution:** 🐞 BUG-2095 (pattern `failure-record-rolled-back`), against `app/services/attachment_service.py` (`confirm_upload`), logged for its future spec. The manager's own rules (flushed `failed` state, ledger row, then the error) are already the intended ones and stay untagged.

Checked and **not** a line here: **HR-4** — `get_active` hides deleted attachments (DAO); `soft_delete` must see them (Q8 is about the manager's answer). Deleted *parents* are PR-1. **HR-5, HR-6, HR-7, HR-8** — no list is built here; the list and its order are the link DAO's (BUG-1432, BUG-1433). **HR-9** — `confirm_attachment` writes only on a real state change (R2). **HR-1** — file names are the allowlist's (BUG-120, BUG-125); `build_display_name` is a Cloudinary label, not a stored name. **HR-2, HR-3, HR-15** — no unique names, grouping or money. **HR-11** — `confirm_attachment` trusts only Cloudinary's Admin API answer for the server-minted id (R7 ✅); the client's confirm body is ignored. **HR-12** — no money. **HR-14** — no batch.

### Precedent matches — all applied (decided by Claude under the reviewer's delegation, 2026-11-04)

### Q8. Deleting an attachment already deleted deletes it again — 🐞 BUG-2097
**Background:** Attachments are soft-deleted. The attachment DAO's `soft_delete` finds the row whether or not it is deleted (DAO P2, intended at the DAO), and its FU-1 (a) asked this manager to refuse.
**What happens today:** A second `DELETE /attachments/{id}` answers 200, overwrites `deleted_at` / `deleted_by`, writes a second `deleted` ledger row, a second "Removed …" entry on every parent, and calls Cloudinary's delete again.
**Example:** Rahim deletes a drawing at 10:00. Karim's tab still shows it and deletes it at 11:00: the drawing now says Karim deleted it at 11:00 and the order's activity shows "Removed drawing.pdf" twice.
**Rules affected:** `delete_attachment` R1
**Answer:** bug — per attachment DAO P2 / FU-1 (a): an attachment already deleted answers as missing (`None`; 404 `Attachment <id> not found.` at the service), nothing written, no Cloudinary call
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04): 🐞 BUG-2097 (pattern `mutation-on-soft-deleted`). Rules: `delete_attachment` R1.

### Q11. A failed Cloudinary delete leaves no trace — 🐞 BUG-2100
**Background:** Deleting a ready attachment asks Cloudinary to delete its file; any error is swallowed so that the delete still succeeds. The stamp manager does the same and was ruled a bug (BUG-1713): the delete still succeeds, but a WARNING names the file.
**What happens today:** A network error or a Cloudinary refusal is ignored without a log line; the file stays in Cloudinary and nothing records it.
**Example:** Cloudinary is down for a minute; 12 photos deleted in that minute stay in storage forever, and nobody can find them.
**Rules affected:** `delete_attachment` R7
**Answer:** bug — per BUG-1713 precedent: still swallowed and the delete still succeeds, but a WARNING naming the `public_id` and the error is logged
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04): 🐞 BUG-2100 (pattern `swallowed-error-unlogged`). Rules: `delete_attachment` R7.

### New questions

### Q1. An upload can be signed for a record that does not exist, is deleted, or is another workspace's — 🐞 BUG-2090
**Background:** An attachment names its record by `entity_type` + `entity_id` only (no foreign key). Signing (`POST /attachments/sign`) looks the record up only to build a Cloudinary folder label, and falls back to `<type>-<id>` when nothing is found. Projects, machines and work orders are soft-deleted; the standing decision is that a deleted parent hides its children (attachment link DAO P2).
**What happens today:** Any `entity_id ≥ 1` is accepted: an unknown id, a deleted machine, and another workspace's order. The attachment and its link are written; the confirm step then writes "Attached …" on that record's activity log (BUG-1091 verified it for another workspace's machine), or fails with a database error for an unknown id.
**Example:** A member signs a photo for `purchase_order` 9999, which does not exist. The upload works; confirming it fails with 500 "Failed to confirm upload." and the photo is stuck `pending`, holding one of 25 places of a record nobody can open.
**Rules affected:** `create_pending_attachment` R1a
**Answer:** bug — the parent must be a record of the caller's workspace that exists and is live (Parent-record rule PR-1); otherwise `AttachmentNotFoundError("<entity_type> <entity_id> not found.")` → 404, nothing written. `scratch` is exempt (Q14).
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04) for unknown and deleted parents; HR-16 for another workspace's: 🐞 BUG-2090 (pattern `cross-workspace-link-not-refused`). The sign endpoint must map `AttachmentNotFoundError` to 404 (today it would be 500 "Failed to prepare upload."). Rules: `create_pending_attachment` R1a.

### Q2. Actions by attachment id ignore who may open its record — 🐞 BUG-2091
**Background:** OQ-5 (owner) made attachments follow their record's visibility; BUG-1870 / BUG-1950 cover the list and the sign path and left reads by id to this spec. OQ-18: attached records answer 404, not 403. A private (`invited_only`) project opens only for the workspace owner, an active owner / ground-team-manager, its creator and its members; a help ticket only for its creator, owner / ground-team-manager and platform admins.
**What happens today:** `GET /attachments/{id}/pdf-page`, `POST /attachments/{id}/confirm` and `DELETE /attachments/{id}` find the attachment in the workspace and never look at its record. A `ground-team` member can page through, confirm and delete a private project's drawings by id. Deleted parents are not looked at either.
**Example:** Karim may not open the private project "Tender 7". Attachment ids are sequential; `DELETE /attachments/412` deletes its contract PDF (200).
**Rules affected:** `get_pdf_page_image` R2, `confirm_attachment` R1a, `delete_attachment` R1a
**Answer:** bug — consequence of OQ-5 / OQ-18: an attachment whose record (any of its records) fails PR-1 or PR-2 answers exactly as a missing one (`Attachment <id> not found.`, 404), nothing written (Parent-record rule PR-3). Needs the caller (and their workspace role, for help tickets) as new parameters.
**Resolution:** decided by Claude as a consequence of the owner's OQ-5 / OQ-18 answers (2026-11-04): 🐞 BUG-2091 (pattern `child-ignores-parent-visibility`). Also covers `AttachmentService.get_attachment` (`GET /attachments/{id}`), which reads through `to_response`. Rules: as listed.

### Q3. Confirm never checks the real file size — 🐞 BUG-2092
**Background:** Signing refuses a declared size over 10 MB (10 485 760 bytes). The Cloudinary signature does not limit the size of what is then uploaded. The phone path's confirm (`confirm_staging_upload`) checks Cloudinary's real `bytes` and refuses and deletes an oversized file; this confirm does not.
**What happens today:** A client declares 1 000 bytes, uploads 80 MB, and confirm stores `file_size` = 80 MB with status `ready`.
**Example:** A browser script uploads a 90 MB video renamed `.pdf`… Cloudinary rejects the format, but a 90 MB real PDF goes through and counts against the company's Cloudinary storage.
**Rules affected:** `confirm_attachment` R6a
**Answer:** bug — as the phone path: Cloudinary `bytes` over 10 485 760 → the file is deleted from Cloudinary, the attachment is marked `failed` with a `failed` ledger row (notes = the message), and `AttachmentConfirmError("File too large (<bytes> bytes). Maximum is 10485760 bytes.")` → 400
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04): 🐞 BUG-2092 (pattern `inconsistent-sibling-guard`). Rules: `confirm_attachment` R6a.

### Q4. An upload confirmed after a failed try never says "Attached …" — 🐞 BUG-2093
**Background:** Confirming writes "Attached <file>" on the record's activity log only when the attachment was `pending`. A `failed` attachment can be confirmed again (a retry after a network error); it then becomes `ready`.
**What happens today:** pending → failed (network) → retry → ready: the photo appears on the order but the activity log never says it was attached. Deleting it later writes "Removed …".
**Example:** On a weak connection the first confirm of `receipt.jpg` fails, the retry succeeds. The purchase order's history shows "Removed receipt.jpg" a week later, with no matching "Attached".
**Rules affected:** `confirm_attachment` R8
**Answer:** bug — "Attached …" is written on the first transition to `ready`, from `pending` or `failed`; a confirm of an attachment already `ready` writes nothing (R2)
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04): 🐞 BUG-2093 (pattern `event-skipped-on-retry`). Rules: `confirm_attachment` R8.

### Q7. "Cloudinary not configured" at confirm marks the upload failed — 🐞 BUG-2096
**Background:** Every Cloudinary call first checks the three settings and raises `CloudinaryNotConfiguredError`, which the endpoints turn into 503 "service unavailable". At confirm, every error of the Cloudinary lookup, this one included, is treated as "the file is not there".
**What happens today:** With a missing secret, confirm marks the user's upload `failed`, writes a `failed` ledger row and answers 400 "Cloudinary verification failed: Cloudinary is not configured…". Sign, PDF page and the phone path answer 503 for the same cause.
**Example:** A deploy drops `CLOUDINARY_API_SECRET`. For an hour every confirm answers 400 and every upload of that hour is marked failed, as if the users had done something wrong.
**Rules affected:** `confirm_attachment` R4a
**Answer:** bug — `CloudinaryNotConfiguredError` passes through unchanged (503), the attachment keeps its state, nothing written; other lookup errors keep R4
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04): 🐞 BUG-2096 (pattern `lossy-error-mapping`). Rules: `confirm_attachment` R4a.

### Q9. Deleting an upload that never became ready writes "Removed …" — 🐞 BUG-2098
**Background:** "Attached <file>" is written only when an upload becomes ready (R8). Deleting writes "Removed <file>" on every parent, whatever the upload state.
**What happens today:** A `pending` or `failed` upload (never shown in the list) deleted through the API leaves "Removed scan.pdf" on the order's history with no "Attached".
**Example:** As above: a history line about a file that was never on the order.
**Rules affected:** `delete_attachment` R4
**Answer:** bug — "Removed …" only for an attachment that was `ready` when deleted; the ledger row is written in every state (R3)
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04): 🐞 BUG-2098 (pattern `event-without-matching-action`). Rules: `delete_attachment` R4.

### Q10. Deleting a pending or failed upload leaves its file in Cloudinary — 🐞 BUG-2099
**Background:** The browser uploads straight to Cloudinary; the server learns of it only at confirm. A `pending` row may therefore have a file in Cloudinary (upload done, confirm never called or failed), and a `failed` row usually has one (wrong type or size). Deleting asks Cloudinary to delete the file only for `ready` attachments.
**What happens today:** Deleting a pending or failed attachment soft-deletes the row and leaves its file in storage.
**Example:** A failed 9 MB scan is deleted; the file stays in Cloudinary, in the company's storage, with no row that names it.
**Rules affected:** `delete_attachment` R6
**Answer:** bug — the file is deleted for every state when `public_id` is set; Cloudinary's "not found" answer is not an error; failures follow R7 (BUG-2100)
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04): 🐞 BUG-2099 (pattern `orphaned-external-file`). Pending uploads that are never deleted are a clean-up job, not a rule here (FU-3). Rules: `delete_attachment` R6.

### Q12. With the API key missing, building URLs raises — 🐞 BUG-2101
**Background:** `derive_urls` returns no URLs when the cloud name or the secret is missing, but the Cloudinary helper it then calls requires the API key too.
**What happens today:** Cloud name and secret set, API key empty: `derive_urls` raises `CloudinaryNotConfiguredError`, so `GET /attachments/` answers 500 instead of listing attachments without URLs.
**Example:** A misconfigured staging server: the attachments panel fails completely instead of showing file names without previews.
**Rules affected:** `derive_urls` R3
**Answer:** bug — no URLs (all three `None`) whenever any of cloud name, API key or secret is empty
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04): 🐞 BUG-2101 (pattern `inconsistent-sibling-guard`). Rules: `derive_urls` R3.

### Q13. The note of an upload has no length limit — 🐞 BUG-2102
**Background:** `AttachmentSignRequest.note` is any text (`str | None`, no limit); the column is `Text`. The phone path's promote request limits its note to 500 characters.
**What happens today:** A 5 MB note is stored and returned with every response that shows the attachment.
**Example:** A buggy client sends the file's base64 as the note: every list of that order now carries megabytes.
**Rules affected:** `create_pending_attachment` R4a
**Answer:** bug — `note` at most 500 characters in `AttachmentSignRequest` (422), as `MobileUploadPromoteRequest`; kept as typed otherwise
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04): 🐞 BUG-2102 (pattern `unbounded-text-input`). Fix in `app/schemas/attachment.py`. Rules: `create_pending_attachment` R4a.

### Q14. `scratch` uploads need no record — ✅ intended
**Background:** `scratch` is the upload playground of the web app's `/uploads` page ("Cloudinary signed-upload playground — owner test harness"). It has no record behind it.
**What happens today:** Any `entity_id` is accepted for `scratch`; every member can list, page, confirm and delete scratch files; the label is `scratch-<id>`.
**Answer:** intended — no record to look up, so PR-1 and PR-2 do not apply; whether the playground should be open to every member in production goes to `docs/future/permissions.md`
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04). Rules: `resolve_entity_label` R1 ✅, Parent-record rule PR-1 ✅.

### Q15. The capacity check is not locked — ✅ intended
**Background:** A record holds at most 25 attachments (`MAX_ATTACHMENTS_PER_ENTITY`), counted before the pending row is written (failed ones not counted, BUG-1434).
**What happens today:** Two signs at 24 can both pass, giving 26.
**Answer:** intended — a soft cap against clutter; HR-10 needs a lock only for money, stock, approvals or duplicate side effects
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04). Rules: `assert_entity_attachment_capacity` R2 ✅.

### Q16. Responses show the Cloudinary `public_id` — ✅ intended
**Background:** OQ-11 found that a visible attachment `public_id` could be used to delete the file through the stamp feature. BUG-1864 / BUG-1865 now accept only the user's own stamp ids, and nothing in this module takes an id from the request.
**Answer:** intended — knowing an id grants nothing once BUG-1864 / 1865 are fixed; whether to stop sending it is noted for the permissions feature
**Resolution:** decided by Claude as a consequence of the owner's OQ-11 answer (2026-11-04). Rules: `to_response` R2 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this manager. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Attachment service** (`app/services/attachment_service.py`, no spec yet) | (a) 🐞 BUG-2095: `confirm_upload` must commit the `failed` state and ledger row before re-raising (HR-13). (b) `list_attachments` builds each response with `to_response`, one links query per attachment (up to 200): per BUG-1964 precedent, read the links together. (c) BUG-1870 / BUG-1950 / BUG-2091 need the caller and role passed down: `list_attachments` and `get_attachment` have neither today. (d) `delete_attachment` deletes the Cloudinary file before the commit; if the commit fails the row stays and the file is gone. Suggested: delete the file after the commit. (e) The sign endpoint maps unknown errors to 500 "Failed to prepare upload."; `AttachmentNotFoundError` (BUG-2090) must map to 404. | Q1, Q2, HR-13 line, reading the callers |
| FU-2 | **Production check** | `CLOUDINARY_UPLOAD_ENV` defaults to `"development"`, and the `ENVIRONMENT` fallback is used only when it is empty. Unless Railway sets `CLOUDINARY_UPLOAD_ENV=production`, production files are named `development/ws-<id>/…` and filed under `Dev/…`. Harmless for users; it mixes production and development files in one Cloudinary account. | `build_public_id` R1 |
| FU-3 | **Clean-up job (none exists)** | `pending` attachments never confirmed keep a row, a place (BUG-1434 keeps them counted) and maybe a Cloudinary file; `failed` ones keep a file until deleted (BUG-2099). Suggested: a daily sweep deletes the file and soft-deletes pending rows older than a day (HR-14). Noted in `docs/future/subscription-payments.md` (storage). | Q10, attachment link DAO FU-1 (b) |

## Overview
`AttachmentManager` runs the attachment upload flow: the browser asks to sign an upload, the manager validates the file's name, type and declared size, writes a `pending` attachment linked to its record and returns Cloudinary upload parameters; the browser uploads straight to Cloudinary; confirm asks Cloudinary's Admin API about the file, checks it against the allowlist and marks the attachment `ready` (or `failed`). It also builds signed delivery URLs, PDF page images, the API response, and soft deletes. Every state change writes an append-only ledger row; becoming ready and being deleted also write an entry on the parent record's activity log. Callers: `AttachmentService` (sign, confirm, list, get, PDF page, delete; it commits or rolls back), `MobileUploadSessionManager` (promote), `AttachmentMarkupManager` (its errors). The manager never commits; it flushes.

**Callables:** 19 specified · 3 not specified
**Externals to mock:** Cloudinary, as imported in `app.managers.attachment_manager`: `generate_upload_signature`, `build_signed_delivery_url`, `get_resource`, `destroy_resource`; `time.time` (sign timestamp); `uuid.uuid4` (public id token); `settings` (`CLOUDINARY_*`, `ENVIRONMENT`, `MAX_ATTACHMENTS_PER_ENTITY`). Never call Cloudinary over the network.
**Integration-only behavior:** endpoint error mapping (sign: validation / limit → 400, not configured → 503, anything else → 500; confirm: not found → 404, confirm error → 400, not configured → 503). The caller's role and platform-admin flag are **not** integration-only: the manager reads them itself (PR-5), so help-ticket role cases (active vs suspended membership, BUG-1885) are unit cases here. *(Corrected 2026-11-04, case designer gap 9.)*

### Parent-record rule (intended; cited by the markup and mobile upload specs)
A parent is the `(entity_type, entity_id)` an attachment is linked to.
- **PR-1. Exists, live, same workspace.** The parent must be a row of its type's table with the caller's `workspace_id`. For types with soft delete (`project`, `machine`, `work_order`) it must have `is_deleted = False`; a `project_component` counts only if its project is live. `scratch` has no table and always passes (Q14). Unknown, deleted, or another workspace's → refused, worded as not found. 🐞 BUG-2090 (HR-16).
- **PR-2. The caller may open it** (owner, OQ-5; OQ-18). `project` with visibility `invited_only` → `ProjectManager.can_access_project(session, project, user_id, workspace_id)` (project manager spec); `project_component` → that rule on its project; `support_ticket` → `HelpTicketManager.can_access_ticket(ticket=…, user=…, role=…)` with the caller's role from an **active** membership (help ticket manager spec; BUG-1885 for the role), **plus the workspace owner** (`workspaces.owner_user_id` of the ticket's workspace), who opens every ticket of that workspace whatever their membership role or status. *(Verifier finding 5, decided by Claude under the reviewer's delegation (2026-11-04): it matches the private-project rule, where the workspace owner always may open, and OQ-8's "owner sees every ticket". Today `can_access_ticket` ignores `owner_user_id` → 🐞 BUG-2103.)* Every other type (orders, items, machines, invoices, `scratch`): any member of the workspace. Refused → the same answer as PR-1. **The manager does no membership check of its own** (gap 3): who may enter the workspace at all (an active member, or a platform admin without membership) is decided once, by the API gate `get_current_workspace`, as for discussions and projects. So a caller with no membership passes PR-2 for these types, and for a private project or ticket is judged only by `can_access_project` / `can_access_ticket` (creator, project member, workspace owner; platform admin for tickets only). *(Decided by Claude under the reviewer's delegation (2026-11-04): one gate for membership; OQ-5 is about the record's own visibility, which these rules apply in full.)* 🐞 BUG-1870 (projects, components), BUG-1950 (tickets) on the sign path.
- **PR-3. Actions by attachment id** (read, PDF page, confirm, delete; markup list / save / clear / history): if **any** of the attachment's links fails PR-1 or PR-2 for the caller, the attachment answers exactly as a missing one, `AttachmentNotFoundError("Attachment <id> not found.")` → 404, and nothing is written. 🐞 BUG-2091 here; the markup and mobile specs log their own. **Which links count** (gap: markup 2): only the attachment's links filed under the caller's workspace. A link filed under another workspace is invalid data (HR-16): it is ignored, never shown and never grants access. An attachment with **no** link in the caller's workspace (no writer produces one: signing writes the attachment and its link together) answers 404 as missing: a record that cannot be checked is not shown. *(Decided by Claude under the reviewer's delegation (2026-11-04), consistent with OQ-5 and HR-16; part of BUG-2091's intended behaviour, no new ID.)*
- **PR-4. Refusals come first.** PR-1 to PR-3 are checked before any row is written and before any Cloudinary call, and **before every error or early return that depends on the attachment's state or on the input**, so a hidden attachment never shows that it exists. In particular: `get_pdf_page_image` answers 404 for a hidden attachment even with `page=0` (not "Page number must be at least 1."), not ready, not a PDF or missing metadata; `confirm_attachment` answers 404 for a hidden attachment that has no `public_id` (not R3's 400) and for one already `ready` (R2 must not return it, so its name, `public_id` and URLs never reach the caller); `delete_attachment` likewise before any state test. *(Verifier findings 2, 3, decided by Claude under the reviewer's delegation (2026-11-04); part of BUG-2091, which today has no check at all.)* The QR flow applies PR-1 and PR-2 (with PR-1's message) when a session is opened and again when its file is attached, before the staged file's size, name and type checks and before the file is moved (mobile R2-1, 2026-11-04) (mobile spec BUG-2130, BUG-2131, BUG-2133, BUG-2134).
- **PR-5. Caller parameters (all three attachment specs; gap 1, markup gap 1, mobile gap 1).** No method takes a `role` parameter. The caller is identified by one argument, and the manager reads the rest itself from that id and `workspace_id`: the caller's **role** is the `role` of their `workspace_members` row in that workspace when its `status` is `active`, otherwise `None` (BUG-1885's rule); **platform admin** is `profiles.is_platform_admin`. This is how `ProjectManager.can_access_project` / `_is_privileged` already work (project manager spec) and what the discussion service spec fixed (Facts: "reads the caller's role and platform-admin flag itself from `user_id` and `workspace_id`"). A role handed in by the caller is how BUG-1885 arose. The caller argument per method:
  - `create_pending_attachment`: the existing `user` (`Profile`).
  - `get_pdf_page_image`: a **new keyword-only `user_id: int`, required, no default** *(requires new parameter; as the discussion service's `list` gains a required `user_id`)*.
  - `confirm_attachment`: the existing `performed_by`; when it is `None`, the uploader (`uploaded_by`) is the caller (gap 7: the same fallback the method already uses for the actor of the ledger row and events; both API paths always pass the caller, so `None` is a direct call only). *(Decided by Claude under the reviewer's delegation (2026-11-04).)*
  - `delete_attachment`: the existing `deleted_by`.
  - Markup manager: the existing `current_user_id` (`list_layers`, `list_events`) and `user_id` (`put_own_layer`, `delete_own_layer`); `_get_ready_attachment` gains a required keyword `user_id`.
  - Mobile manager: the existing `user` of `create_session` and `promote_to_attachment`.
  `to_response` stays a mapper: its callers check first. *(Decided by Claude under the reviewer's delegation (2026-11-04); the cards' `role=` argument is dropped.)*

**Facts for the test designer**
- Import: `from app.managers.attachment_manager import AttachmentManager, attachment_manager, AttachmentNotFoundError, AttachmentLimitError, ENTITY_TYPE_FOLDER_LABELS`; errors from the allowlist: `from app.utils.attachment_allowlist import AttachmentValidationError, AttachmentConfirmError, MAX_FILE_SIZE_BYTES` (`10 * 1024 * 1024` = 10 485 760). `CloudinaryNotConfiguredError` from `app.core.cloudinary_client`. All error classes are `ValueError` subclasses except `CloudinaryNotConfiguredError` (`RuntimeError`).
- Every parameter after `session` is keyword-only, except `derive_urls(attachment)`, `build_pdf_page_image_url(attachment, *, page, width)`, `to_response(session, attachment, *, workspace_id)`, `build_display_name(file_name)`, `_extract_entity_label(entity_type, row)`, `_attachment_event_metadata(attachment)`.
- Settings defaults: `CLOUDINARY_UPLOAD_ENV = "development"`, `ENVIRONMENT = "development"`, `CLOUDINARY_CLOUD_NAME / API_KEY / API_SECRET = ""`, `MAX_ATTACHMENTS_PER_ENTITY = 25`. Patch `app.managers.attachment_manager.settings` attributes.
- Upload statuses `pending`, `ready`, `failed` (`UploadStatusEnum`); ledger types `pending`, `ready`, `failed`, `deleted` (`AttachmentLedgerTransactionTypeEnum`). Entity types: `purchase_order`, `sales_order`, `expense_order`, `transfer_order`, `work_order`, `project`, `project_component`, `item`, `machine`, `account_invoice`, `support_ticket`, `scratch`.
- `ENTITY_TYPE_FOLDER_LABELS`: purchase_order "Purchase Orders", sales_order "Sales Orders", expense_order "Expense Orders", transfer_order "Transfer Orders", work_order "Work Orders", project "Projects", project_component "Project Components", item "Items", machine "Machines", account_invoice "Invoices", support_ticket "Help Tickets", scratch "Scratch".
- Model `attachments` (attachment DAO spec Overview): `public_id` String(512) nullable; `resource_type` default `image`; `delivery_type` default **`upload`** in the model (rows written here always say `authenticated`); `format` String(16); `version` BigInteger; `asset_id`, `etag` String(64); `upload_status` default `pending`; unique `(workspace_id, public_id)`. `attachment_ledger`: `attachment_id` FK RESTRICT, `transaction_type` String(16), `entity_type` / `entity_id` nullable, `file_name` String(255), `mime_type` String(128), `notes` Text, `performed_by` nullable, `performed_at` timestamptz default `now()`.
- Schemas: `AttachmentSignRequest(entity_type, entity_id ≥ 1, file_name 1–255, mime_type 1–128, file_size ≥ 1, note: str | None)`. `AttachmentCreateInternal` and `AttachmentUpdateInternal` are plain Pydantic models; the update is dumped with `exclude_unset=True`, so a field given as `None` **is** written (verified).
- Enums (gap 4): every enum here is in `app.models.enums`: `from app.models.enums import AttachmentEntityTypeEnum, AttachmentLedgerTransactionTypeEnum, UploadStatusEnum, MobileUploadSessionStatusEnum, ProjectVisibilityEnum`. All are `str` enums, so `AttachmentEntityTypeEnum.MACHINE == "machine"`.
- Cloudinary calls (gap 5; checked in the code): every helper in `app.core.cloudinary_client` has keyword-only parameters, and this module passes keywords only:
  - `generate_upload_signature(public_id=, asset_folder=, display_name=, timestamp=, delivery_type="authenticated")`;
  - `get_resource(public_id=, resource_type=, delivery_type=)` and `destroy_resource(public_id=, resource_type=, delivery_type=)`;
  - `build_signed_delivery_url(public_id=, resource_type=, delivery_type=, version=, fmt=, …)`: in `derive_urls` the thumb and preview calls add `transformation=` (no `flags`), the two download calls add `flags="attachment"` (no `transformation`); `build_pdf_page_image_url` adds `transformation=` only.
  - (mobile manager) `rename_resource(from_public_id=, to_public_id=, resource_type=, delivery_type=)`, whose return value is not read (mobile gap 2), and `update_resource_metadata(public_id=, resource_type=, delivery_type=, asset_folder=, display_name=)`.
- Shapes (gap 6): `derive_urls` returns `AttachmentDerivedUrls` (`app.schemas.attachment`), a Pydantic model with attributes `thumb_url`, `preview_url`, `download_url`, each `str | None`, default `None`. `to_response(...).links` is a list of `AttachmentLinkInfo` with attributes `entity_type` (an `AttachmentEntityTypeEnum` member) and `entity_id` (int); `.urls` is the `AttachmentDerivedUrls`.
- `deleted_at` clock (gap 8): the attachment DAO's `soft_delete` writes `utcnow()` imported in `app.dao.attachment` (naive UTC; patch `app.dao.attachment.utcnow` for an exact value); BUG-1430 makes it an aware UTC moment (attachment DAO spec). This manager reads no clock.
- **Parent builder columns** (gap 2, markup gap 3; required = NOT NULL with no default, read from the models): 
  | Parent table | Required columns (FK target) | Label column | Activity table, parent-id column |
  |---|---|---|---|
  | `purchase_orders` | `workspace_id`, `po_number`, `destination_type`, `destination_id`, `current_status_id` (`statuses`), `created_by` (`profiles`) | `po_number` | `purchase_order_events.purchase_order_id` |
  | `sales_orders` | `workspace_id`, `sales_order_number`, `account_id` (`accounts`), `factory_id` (`factories`), `current_status_id`, `created_by` | `sales_order_number` | `sales_order_events.sales_order_id` |
  | `expense_orders` | `workspace_id`, `expense_number`, `expense_category`, `created_by` | `expense_number` | `expense_order_events.expense_order_id` |
  | `transfer_orders` | `workspace_id`, `transfer_number`, `source_location_type`, `source_location_id`, `destination_location_type`, `destination_location_id`, `current_status_id`, `created_by` | `transfer_number` | `transfer_order_events.transfer_order_id` |
  | `work_orders` | `workspace_id`, `work_order_number`, `work_order_type_id` (`work_order_types`), `title`, `factory_id` | `work_order_number` | `work_order_events.work_order_id` |
  | `projects` | `workspace_id`, `factory_id`, `name`, `description` | `name` | `project_events.project_id` |
  | `project_components` | `workspace_id`, `project_id`, `name` | `name` | `project_component_activity_events.project_component_id` |
  | `machines` | `workspace_id`, `name`, `factory_id` | `name` | `machine_activity_events.machine_id` |
  | `account_invoices` | `workspace_id`, `account_id`, `invoice_type`, `invoice_amount`, `invoice_date` | `invoice_number` (nullable) | `invoice_events.invoice_id` |
  | `items` | `workspace_id`, `name`, `name_normalized`, `unit` | `sku` or `name` | none |
  | `help_tickets` | `workspace_id`, `ticket_number`, `title`, `description` | `ticket_number` | none |
  Every activity table also requires `workspace_id`, `event_type`, `description`; its `performed_by` is nullable; the metadata column is `metadata` (attribute `metadata_json`) on all of them except `invoice_events`, whose column is `metadata_json`. Status rows for `current_status_id` come from the status DAO spec's builders.
- Soft-deleted parents (mobile gap 5): PR-1 reads **only `is_deleted`**. A real delete writes `is_deleted = True`, `deleted_at` and `deleted_by` (work orders: the work order DAO's `soft_delete` sets `deleted_at` to the database's `now()`; one manager path writes `utcnow()`); building a deleted parent with `is_deleted=True` alone is enough.

**Notes for the test designer**
- Build parents with the columns of the table above (or the factories of their DAO specs); attachments via `create_pending_attachment` or directly (`Attachment(...)` + `AttachmentLink(...)`, flush).
- PR-2 / PR-3 callers: a member is a `WorkspaceMember(workspace_id, user_id, role, status="active")`; a suspended privileged member has `status="suspended"` and counts as no role (PR-5). A platform admin is a profile with `is_platform_admin=True` and needs no membership row.
- Pass cards of `get_pdf_page_image` must keep working before and after BUG-2091: call it through a small helper that adds `user_id=` only when `inspect.signature(attachment_manager.get_pdf_page_image)` has that parameter.
- Patch Cloudinary functions on `app.managers.attachment_manager` (`get_resource` returns a dict such as `{"resource_type": "image", "format": "jpg", "bytes": 1234, "version": 1700000000, "secure_url": "https://…", "width": 800, "height": 600, "asset_id": "a"*32, "etag": "e"*32}`). `build_signed_delivery_url` may be patched to echo its keyword arguments, so URL cases compare arguments, not strings.
- Activity entries: assert on the parent's event table through its DAO (purchase order, sales order, expense order, transfer order, work order, project, project component, machine, invoice events). `item`, `support_ticket`, `scratch` have none.
- BUG-2091, BUG-2090, BUG-1870, BUG-1950 cases use the PR-5 arguments (no `role`): write them to the intended signature, **strict** xfail (`get_pdf_page_image` ones fail with `TypeError` today; the others fail on the missing refusal).
- BUG-2094 needs two sessions and commits: integration-only; give it one case marked so, or skip.
- BUG-2095 is the service's: not a case here.

## Not specified
- `AttachmentNotFoundError`, `AttachmentLimitError` — plain `ValueError` subclasses, no logic.
- `attachment_manager` — module singleton.

---

## `AttachmentManager.normalize_upload_request(payload)`
**Shape:** validator · **Persistence:** pure · **Visibility:** public (used by: `AttachmentService.sign_upload`, `MobileUploadSessionManager`)

**Purpose:** validate a sign request's file name, type and declared size.

**Rules:**
- **R1.** Returns exactly what `normalize_upload_request` of the allowlist returns for the same payload, and raises what it raises (allowlist spec `normalize_upload_request` R1–R…; BUG-120…125 there). No other behaviour.

---

## `AttachmentManager.assert_entity_attachment_capacity(session, *, workspace_id, entity_type, entity_id)`
**Shape:** validator · **Persistence:** reads · **Visibility:** public (used by: `create_pending_attachment`)

**Purpose:** refuse a new attachment when the record already holds the maximum.

**Rules:**
- **R1.** Counts the record's attachments as `count_linked_attachments_for_entity` does (link DAO spec R1–R4: not deleted; `pending` and `ready`; `failed` not counted per BUG-1434), for the caller's workspace and `entity_type.value`.
- **R2.** Count `<` `MAX_ATTACHMENTS_PER_ENTITY` → returns `None`, nothing written. ✅ (Q15: no lock.)
- **R3.** Count `>=` the maximum (24 of 25 passes, 25 of 25 refused) → `AttachmentLimitError("This record already has the maximum of <max> attachments.")` (with the setting's value, e.g. `25`).
- **R4.** The maximum is read from settings at each call; a maximum of `0` refuses every record.
- **R5.** Attachments of the same `entity_id` under another type, or of another workspace, do not count.

**Errors:** `AttachmentLimitError` as R3 (400 at the API).
**Side effects:** none.

---

## `AttachmentManager._upload_env()` / `_is_production()`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `build_public_id`, `build_asset_folder`)

**Rules:**
- **R1.** The upload environment is `CLOUDINARY_UPLOAD_ENV` when non-empty, else `ENVIRONMENT` (FU-2: the first defaults to `"development"`).
- **R2.** Production means the upload environment equals `"production"` exactly (`"Production"` is not).

---

## `AttachmentManager.build_public_id(*, workspace_id)`
**Shape:** compute · **Persistence:** pure · **Visibility:** public (used by: `AttachmentService.sign_upload`, mobile `promote_to_attachment`)

**Purpose:** mint the Cloudinary name a new file is uploaded under.

**Rules:**
- **R1.** Production: `ws-<workspace_id>/<token>`, `<token>` = `uuid4().hex` (32 lowercase hex). Any other environment `<env>`: `<env>/ws-<workspace_id>/<token>` (e.g. `development/ws-7/3ec1…`). Both settings empty → `/ws-<id>/<token>`.
- **R2.** Each call gives a new token. ✅ OQ-11: the id is chosen by the server, never by the client.

---

## `AttachmentManager.build_asset_folder(*, workspace_name, entity_type, entity_label)`
**Shape:** compute · **Persistence:** pure · **Visibility:** public (used by: sign, promote)

**Rules:**
- **R1.** Production: `<workspace_name>/<type label>/<entity_label>`, type label from `ENTITY_TYPE_FOLDER_LABELS`. Other environments: `Dev/` in front (whatever the environment's name). Verified: `Dev/Acme/Items/SKU1`.
- **R2.** Names are used as given: slashes inside a workspace or record name make deeper folders; nothing is trimmed or escaped (the folder affects only Cloudinary's Media Library, not URLs).

---

## `AttachmentManager.build_display_name(file_name)`
**Shape:** compute · **Persistence:** pure · **Visibility:** public (used by: sign, mobile sign and promote)

**Rules:**
- **R1.** Every `/` and `\` becomes `-`; characters `\x00`–`\x1f` and `\x7f` are removed; outer whitespace is removed. Verified: `"  a/b\c\x01.pdf "` → `"a-b-c.pdf"`.
- **R2.** Empty after R1 → `"upload"` (verified for `"\x01 "`).
- **R3.** Cut to the first 255 characters.

---

## `AttachmentManager.resolve_entity_label(session, *, workspace_id, entity_type, entity_id)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (used by: sign, mobile `resolve_entity_label`, promote)

**Purpose:** a human label for the Cloudinary folder.

**Rules:**
- **R1.** `scratch` → `scratch-<entity_id>`, nothing read. ✅ (Q14)
- **R2.** Otherwise the record is found with `get_by_id_and_workspace` of its type's DAO (raw: soft-deleted rows **are** found; another workspace's id is not). Not found → `<entity_type>-<entity_id>` (e.g. `purchase_order-9999`).
- **R3.** Found → the label of `_extract_entity_label`; an empty or `None` label → the fallback of R2.
- **R4.** No check of visibility or deletion here; that is PR-1 / PR-2 at the write (`create_pending_attachment` R1a, R1b).

---

## `AttachmentManager._fetch_entity_row(session, *, workspace_id, entity_type, entity_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `resolve_entity_label`)

**Rules:**
- **R1.** For the eleven types other than `scratch`, returns the type's row of that id in that workspace, or `None` (base DAO `get_by_id_and_workspace`; `support_ticket` uses the help ticket DAO).
- **R2.** `scratch` → `None` (no DAO). Unreachable through `resolve_entity_label`, which answers `scratch` first.

---

## `AttachmentManager._extract_entity_label(entity_type, row)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** internal

**Rules:**
- **R1.** purchase_order → `po_number`; sales_order → `sales_order_number`; expense_order → `expense_number`; transfer_order → `transfer_number`; work_order → `work_order_number`; project, project_component, machine → `name`; account_invoice → `invoice_number`; support_ticket → `ticket_number`.
- **R2.** item → `sku` when truthy, else `name` (an empty `sku` falls back to the name).
- **R3.** scratch → `None`.

---

## `AttachmentManager._attachment_event_metadata(attachment)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** internal (used by: `_log_attachment_entity_events`)

**Rules:**
- **R1.** Returns `{"attachment_id", "file_name", "mime_type", "file_size"}` with the attachment's current values (exactly these four keys).

---

## `AttachmentManager._append_attachment_ledger(session, *, attachment, workspace_id, transaction_type, entity_type=None, entity_id=None, performed_by=None, notes=None)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** internal (used by: `create_pending_attachment`, `confirm_attachment`, `delete_attachment`)

**Rules:**
- **R1.** Writes one `attachment_ledger` row and flushes: `workspace_id`, `attachment_id`, `transaction_type` (an enum member is stored as its value; a string as given), `entity_type`, `entity_id`, the attachment's current `file_name`, `mime_type`, `file_size`, `notes`, `performed_by`. `performed_at` is the database default.
- **R2.** `entity_type` and `entity_id` both given → used as given.
- **R3.** Either missing → taken from the attachment's first link in the caller's workspace (link DAO `get_links_for_attachment`; first = lowest link `id`, BUG-1433). The given one of the two is replaced too.
- **R4.** Missing and the attachment has no link in that workspace → both stored `NULL`.

---

## `AttachmentManager._log_attachment_entity_events(session, *, attachment, workspace_id, event_type, performed_by)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** internal (used by: `confirm_attachment`, `delete_attachment`)

**Purpose:** tell each parent record's activity log that a file was attached or removed.

**Rules:**
- **R1.** Description: `Attached <file_name>` when `event_type == "attachment_added"`, otherwise `Removed <file_name>` (any other value). Metadata: `_attachment_event_metadata`.
- **R2.** One entry per link of the attachment in the caller's workspace (no link → nothing).
- **R3.** purchase_order, sales_order, expense_order, transfer_order, work_order, project, project_component, machine → that manager's `log_event(session, entity_id, workspace_id, event_type, description, performed_by, metadata)`: one event row on that record with these values (rules and the HR-16 refusal: each manager's spec; BUG-1091, BUG-1192).
- **R4.** account_invoice → the invoice is looked up in the workspace; found → one invoice event (`AccountInvoiceManager._log_event` with the invoice); not found → nothing, no error.
- **R5.** item, support_ticket, scratch → nothing (no activity log).

---

## `AttachmentManager.create_pending_attachment(session, *, workspace_id, user, payload, normalized, stored_public_id, asset_folder)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `AttachmentService.sign_upload`, mobile `promote_to_attachment`)

**Purpose:** record a signed upload before the browser sends the file.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `user` | `Profile` | uploader; `user.id` stored |
| `payload` | `AttachmentSignRequest` | parent, declared size, note |
| `normalized` | `NormalizedUploadRequest` | sanitized name, MIME, resource type (from `normalize_upload_request`) |
| `stored_public_id` | str | minted by `build_public_id` (not re-checked) |

**Returns:** the new `Attachment`, flushed, status `pending`.

**Rules:**
- **R1a.** [BUG-2090] The parent must pass PR-1: an unknown id, a soft-deleted project / machine / work order, a component of a deleted project, or another workspace's id → `AttachmentNotFoundError("<entity_type> <entity_id> not found.")` (e.g. `purchase_order 9999 not found.`), nothing written. `scratch` passes with any id. *(Today: nothing is looked up; the attachment and link are written.)*
- **R1b.** [BUG-1870, BUG-1950] The caller must pass PR-2 for the parent: refused → the same error as R1a, nothing written. *(Today: not checked. The role and platform-admin flag are read from `user.id` per PR-5.)*
- **R2.** Then capacity: `assert_entity_attachment_capacity` R1–R5; refused → `AttachmentLimitError`, nothing written. Refusals R1a–R2 come before any write (PR-4).
- **R3.** Writes one attachment: `workspace_id`; `file_name`, `mime_type`, `resource_type` from `normalized`; `file_size` = the declared `payload.file_size`; `uploaded_by` = `user.id`; `note` as sent; `public_id` = `stored_public_id`; `asset_folder`; `delivery_type` `authenticated`; `upload_status` `pending`; `storage_provider` `cloudinary`; `file_url` `NULL`; `is_deleted` false. ✅ OQ-11: `public_id` comes from the server.
- **R4.** Writes one link: same workspace, the attachment, `entity_type.value`, `entity_id`, `linked_by` = `user.id`.
- **R4a.** [BUG-2102] A `note` over 500 characters is refused by `AttachmentSignRequest` (422) before this method. *(Today: any length is stored.)*
- **R5.** Writes one ledger row `pending` with the payload's `entity_type` / `entity_id`, `performed_by` = `user.id` (`_append_attachment_ledger` R1, R2).
- **R6.** A second attachment with the same `(workspace_id, public_id)` fails at the flush with `IntegrityError` (unique constraint; only a reused id can reach it).
- **R7.** No activity entry is written for a pending attachment (it is written at confirm).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R1a / R1b | `AttachmentNotFoundError` | `<entity_type> <entity_id> not found.` |
| R2 | `AttachmentLimitError` | `This record already has the maximum of <max> attachments.` |

**Side effects:** attachment, link and ledger rows flushed; no commit; no Cloudinary call.

---

## `AttachmentManager.build_sign_response(*, attachment, public_id, asset_folder, display_name)`
**Shape:** compute · **Persistence:** pure · **Visibility:** public (used by: `AttachmentService.sign_upload`)

**Rules:**
- **R1.** `CLOUDINARY_CLOUD_NAME` or `CLOUDINARY_API_KEY` empty → `CloudinaryNotConfiguredError("Cloudinary cloud name and API key are required.")`.
- **R2.** Both set, secret empty → `CloudinaryNotConfiguredError` from the client with its own message (cloudinary client spec `_ensure_configured`).
- **R3.** Otherwise returns: `attachment_id` = `attachment.id`; `cloud_name`, `api_key` from settings; `timestamp` = `int(time.time())`; `public_id`, `asset_folder`, `display_name` as given; `type` `authenticated`; `signature` = `generate_upload_signature(public_id, asset_folder, display_name, timestamp, authenticated)`; `resource_type` = the attachment's, or `image` when empty; `upload_url` = `https://api.cloudinary.com/v1_1/<cloud_name>/<resource_type>/upload`.
- **R4.** Nothing is written.

---

## `AttachmentManager.derive_urls(attachment)`
**Shape:** compute · **Persistence:** pure · **Visibility:** public (used by: `to_response`)

**Rules:**
- **R1.** Status other than `ready` → all three URLs `None`.
- **R2.** `public_id`, `version` or `format` empty (`None`, `""`, `0`) → all `None`.
- **R3.** [BUG-2101] Any of cloud name, API key or secret empty → all `None`, nothing raised. *(Today: only cloud name and secret are checked; with the API key empty it raises `CloudinaryNotConfiguredError`.)*
- **R4.** URLs are built by `build_signed_delivery_url` with the attachment's `public_id`, `version` (as int), `resource_type` (empty → `image`) and `delivery_type` (empty → `upload`; signed only when `authenticated`, client spec).
- **R5.** `raw` resources: `thumb_url` and `preview_url` `None`; `download_url` with the stored format and `flags="attachment"`.
- **R6.** PDF (`mime_type` `application/pdf` or format `pdf`), not raw: `thumb_url` as `jpg` with transformation `[{"page": 1, "fetch_format": "jpg", "quality": "auto", "width": 400, "crop": "limit"}]`.
- **R7.** Other non-raw: `thumb_url` with the stored format and `[{"fetch_format": "auto", "quality": "auto", "width": 400, "crop": "limit"}]`.
- **R8.** Non-raw (PDF included): `preview_url` with the stored format and `[{"fetch_format": "auto", "quality": "auto", "width": 1600, "crop": "limit"}]`; `download_url` with the stored format and `flags="attachment"`, no transformation.

---

## `AttachmentManager.build_pdf_page_image_url(attachment, *, page, width=1600)`
**Shape:** compute · **Persistence:** pure · **Visibility:** public (used by: `get_pdf_page_image`)

**Rules (checked in this order):**
- **R1.** `page < 1` → `AttachmentValidationError("Page number must be at least 1.")`.
- **R2.** Not `ready` → `AttachmentConfirmError("Attachment is not ready.")`.
- **R3.** Neither `mime_type` `application/pdf` nor format `pdf` → `AttachmentValidationError("Attachment is not a PDF.")`.
- **R4.** `public_id` or `version` empty → `AttachmentConfirmError("Attachment is missing Cloudinary metadata.")`.
- **R5.** `page_count` known and `page > page_count` → `AttachmentValidationError("Page <page> is out of range (document has <n> pages).")`. `page_count` `NULL` → any page passes; `page == page_count` passes.
- **R6.** Cloud name or secret empty → `CloudinaryNotConfiguredError("Cloudinary is not configured.")`; API key empty → the client's `CloudinaryNotConfiguredError` (its message). Both 503 at the API.
- **R7.** Returns `build_signed_delivery_url(public_id, resource_type or image, delivery_type or upload, int(version), fmt="jpg", transformation=[{"page": page, "fetch_format": "jpg", "quality": "auto:good", "width": width, "crop": "limit"}])`; when `width >= 1200` the transformation also has `"density": 200` (1199 has none, 1200 has it).

---

## `AttachmentManager.get_pdf_page_image(session, *, attachment_id, workspace_id, page, width=1600)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: `AttachmentService.get_pdf_page_image`)

**Rules:**
- **R1.** Attachment missing, deleted, or of another workspace → `AttachmentNotFoundError("Attachment <id> not found.")`.
- **R2.** [BUG-2091] An attachment whose parent fails PR-1 or PR-2 for the caller → the same error, before any `build_pdf_page_image_url` check (PR-4: `page=0` on a hidden attachment gives 404, not 400). *(Today: not checked. Requires the new required `user_id` per PR-5.)*
- **R3.** Otherwise returns `{"url": <build_pdf_page_image_url R1–R7>, "page": page, "page_count": attachment.page_count}`; its errors pass through. Nothing written.

---

## `AttachmentManager.to_response(session, attachment, *, workspace_id=None)`
**Shape:** mapper · **Persistence:** reads · **Visibility:** public (used by: attachment service, mobile service)

**Rules:**
- **R1.** Links are read for `workspace_id`, or the attachment's own workspace when it is `None` or `0`; `links` lists their `(entity_type, entity_id)` in link `id` order (BUG-1433).
- **R2.** Copies `id`, `file_name`, `mime_type`, `file_size`, `note`, `uploaded_by`, `uploaded_at`, `upload_status`, `public_id`, `format`, `version`, `width`, `height`, `page_count`, `file_url`; `urls` = `derive_urls`. ✅ (Q16: `public_id` is shown.)
- **R3.** A deleted attachment is mapped like any other (the delete endpoint returns it).
- **R4.** A link whose `entity_type` is not an `AttachmentEntityTypeEnum` value raises `ValueError` (no writer produces one).

---

## `AttachmentManager.confirm_attachment(session, *, attachment_id, workspace_id, performed_by=None, _payload=None)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `AttachmentService.confirm_upload`, mobile `promote_to_attachment`)

**Purpose:** after the browser's upload, verify the file with Cloudinary and mark the attachment ready.

**Inputs:** `_payload` is ignored (the confirm body carries nothing). `performed_by` `None` → the uploader is the actor (`actor` below) and, for R1a, the caller (PR-5).

**Returns:** the attachment (flushed and refreshed).

**Rules:**
- **R1.** Missing, deleted, or another workspace's → `AttachmentNotFoundError("Attachment <id> not found.")`, nothing written.
- **R1a.** [BUG-2091] Parent fails PR-1 or PR-2 for the caller → the same error, nothing written, no Cloudinary call; checked before R2 and R3 (PR-4): a hidden `ready` attachment is not returned, a hidden one without `public_id` gets 404, not 400. *(Today: not checked.)*
- **R2.** Already `ready` → returned unchanged; no Cloudinary call, no ledger row, no event. ✅
- **R3.** `public_id` empty → `AttachmentConfirmError("Attachment has no public_id.")`, nothing written (only legacy rows; the sign path always sets it).
- **R4.** Cloudinary's lookup of the stored `public_id` (stored `resource_type` or `image`; stored `delivery_type` or `authenticated`) raises → status `failed` (flushed), one `failed` ledger row with `notes` = the error's text and `performed_by` = actor (entity from the first link), then `AttachmentConfirmError("Cloudinary verification failed: <error>")`. ✅ OQ-11: only our stored id is asked about.
- **R4a.** [BUG-2096] When that error is `CloudinaryNotConfiguredError` it passes through unchanged; the attachment keeps its status and nothing is written. *(Today: handled as R4: marked `failed`, 400.)*
- **R5.** The file found but `validate_cloudinary_resource` refuses it (resource type or format not allowed for the stored file name's extension, allowlist spec) → as R4 (`failed`, ledger row with the message), and that same `AttachmentConfirmError` is raised. An `AttachmentValidationError` from that check (extension no longer allowed) is not caught: status stays as it was, nothing written, the error passes (BUG-124, allowlist; its fix makes it an R5 case).
- **R6.** Otherwise the attachment is updated and flushed: `file_url` = `secure_url`, else `url`; `file_size` = `bytes` when truthy, else unchanged; `format`, `version`, `width`, `height`, `page_count` (Cloudinary `pages`), `asset_id`, `etag` = Cloudinary's values, **`None` when Cloudinary sends none** (overwriting); `upload_status` `ready`. When Cloudinary says `resource_type` `image` and format `pdf`, `mime_type` becomes `application/pdf`.
- **R6a.** [BUG-2092] Cloudinary `bytes` over 10 485 760 → the file is deleted from Cloudinary (errors as `delete_attachment` R7), status `failed`, a `failed` ledger row with the message, then `AttachmentConfirmError("File too large (<bytes> bytes). Maximum is 10485760 bytes.")`; exactly 10 485 760 passes. *(Today: any size is accepted.)*
- **R7.** One `ready` ledger row, `performed_by` = actor, entity from the first link.
- **R8.** [BUG-2093] On the first transition to `ready`, from `pending` **or `failed`**, one `attachment_added` entry per parent (`_log_attachment_entity_events`, actor). *(Today: only from `pending`; a retry after `failed` writes none.)*
- **R9.** The failure paths (R4, R5, R6a) leave the session flushed with the `failed` state; the error follows. Keeping it is the service's (BUG-2095).
- **R10.** [BUG-2094] The attachment is read with a row lock; of two confirms at once, the second sees `ready` and is R2. *(Today: no lock; both write `ready` and the event.)*
- **R11.** Any member of the workspace may confirm any pending attachment, not only its uploader (who may is for the permissions feature).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R1, R1a | `AttachmentNotFoundError` | `Attachment <id> not found.` |
| R3 | `AttachmentConfirmError` | `Attachment has no public_id.` |
| R4 | `AttachmentConfirmError` | `Cloudinary verification failed: <error>` |
| R4a | `CloudinaryNotConfiguredError` | the client's message |
| R5 | `AttachmentConfirmError` | allowlist message |
| R6a | `AttachmentConfirmError` | `File too large (<bytes> bytes). Maximum is 10485760 bytes.` |

**Side effects:** attachment updated, ledger row, activity entries; Cloudinary lookup (and delete in R6a). Flush, no commit.

---

## `AttachmentManager.delete_attachment(session, *, attachment_id, workspace_id, deleted_by)`
**Shape:** soft-delete · **Persistence:** writes · **Visibility:** public (used by: `AttachmentService.delete_attachment`)

**Returns:** the deleted attachment, or `None` (the service turns `None` into 404 `Attachment <id> not found.`).

**Rules:**
- **R1.** [BUG-2097] Missing, another workspace's, **or already deleted** → `None`, nothing written, no Cloudinary call. *(Today: an already deleted attachment is deleted again: stamps overwritten, second ledger row, second "Removed" entries, second Cloudinary call.)*
- **R1a.** [BUG-2091] Parent fails PR-1 or PR-2 for the caller → `None`, nothing written. *(Today: not checked.)*
- **R2.** Otherwise soft-deleted as the DAO does (`is_deleted`, `deleted_at`, `deleted_by`; attachment DAO `soft_delete`, BUG-1430). Links and markup layers stay.
- **R3.** One `deleted` ledger row, `performed_by` = `deleted_by`, entity from the first link, in every upload state.
- **R4.** [BUG-2098] `attachment_removed` entries (`Removed <file_name>`) on every parent only when the attachment was `ready`. *(Today: in every state.)*
- **R5.** A `ready` attachment with a `public_id` → Cloudinary delete of that id (stored `resource_type` or `image`, stored `delivery_type` or `authenticated`). ✅ OQ-11: only our stored id.
- **R6.** [BUG-2099] A `pending` or `failed` attachment with a `public_id` → the same delete. *(Today: only `ready`.)*
- **R7.** [BUG-2100] Any error of the delete (not configured included) is swallowed, the method still returns the attachment, and a WARNING naming the `public_id` and the error is logged. *(Today: swallowed with no log.)*
- **R8.** Any member may delete any attachment of a record they may open (who may is for the permissions feature).

**Side effects:** row soft-deleted, ledger row, activity entries, Cloudinary delete; flush, no commit.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 90–91 | delegate to allowlist | `normalize_upload_request` R1 |
| 108 | `current >= max_per_entity` | `assert_entity_attachment_capacity` R2, R3, R4 |
| 114 | `CLOUDINARY_UPLOAD_ENV or ENVIRONMENT` | `_upload_env` R1 |
| 117 | `== "production"` | `_upload_env` R2 |
| 123 | production / not (public id) | `build_public_id` R1 |
| 137 | production / not (folder) | `build_asset_folder` R1 |
| 143–144 | replace slashes, control chars, strip | `build_display_name` R1 |
| 145 | empty → "upload" | `build_display_name` R2 |
| 147 | cut 255 | `build_display_name` R3 |
| 160 | scratch | `resolve_entity_label` R1 |
| 169 | row None | `resolve_entity_label` R2 |
| 173 | `label or fallback` | `resolve_entity_label` R3 |
| 196–199 | dao None / found | `_fetch_entity_row` R1, R2 |
| 206–228 | per-type label; `sku or name`; scratch None | `_extract_entity_label` R1–R3 |
| 250 | entity missing → links | `_append_attachment_ledger` R2, R3 |
| 256 | links empty | `_append_attachment_ledger` R4 |
| 260–264 | enum vs str | `_append_attachment_ledger` R1 |
| 304–308 | added / other | `_log_attachment_entity_events` R1 |
| 316 | loop over links (0 / many) | `_log_attachment_entity_events` R2 |
| 320–399 | eight `log_event` branches | `_log_attachment_entity_events` R3 |
| 400–414 | invoice found / not | `_log_attachment_entity_events` R4 |
| (no branch) | item, support_ticket, scratch | `_log_attachment_entity_events` R5 |
| (missing) | parent lookup / visibility | `create_pending_attachment` R1a, R1b |
| 427 | capacity | `create_pending_attachment` R2 |
| 433–464 | writes | `create_pending_attachment` R3–R7 |
| 475 | name or key empty | `build_sign_response` R1, R2 |
| 487 | `resource_type or "image"` | `build_sign_response` R3 |
| 505 | not ready | `derive_urls` R1 |
| 507 | missing id / version / format | `derive_urls` R2 |
| 510 | config check | `derive_urls` R3 |
| 513–514 | defaults | `derive_urls` R4 |
| 519 | raw | `derive_urls` R5 |
| 534–535 | pdf / not | `derive_urls` R6, R7 |
| 558–575 | preview, download | `derive_urls` R8 |
| 585 | page < 1 | `build_pdf_page_image_url` R1 |
| 587 | not ready | `build_pdf_page_image_url` R2 |
| 589 | not pdf | `build_pdf_page_image_url` R3 |
| 591 | missing id / version | `build_pdf_page_image_url` R4 |
| 594 | page_count known and exceeded | `build_pdf_page_image_url` R5 |
| 599 | config | `build_pdf_page_image_url` R6 |
| 602–603 | defaults | `build_pdf_page_image_url` R7 |
| 611 | `width >= 1200` | `build_pdf_page_image_url` R7 |
| 632 | not found | `get_pdf_page_image` R1, R2 |
| 648 | `workspace_id or attachment.workspace_id` | `to_response` R1 |
| 652–658 | links → infos | `to_response` R1, R4 |
| 690 | not found | `confirm_attachment` R1, R1a |
| 693 | already ready | `confirm_attachment` R2, R10 |
| 696 | was_pending | `confirm_attachment` R8 |
| 698 | no public_id | `confirm_attachment` R3 |
| 701–720 | lookup raises | `confirm_attachment` R4, R4a, R9 |
| 711, 728, 757 | `performed_by` None → uploader | `confirm_attachment` Inputs, R4, R7 |
| 722–737 | validation refuses | `confirm_attachment` R5, R9 |
| (missing) | size check | `confirm_attachment` R6a |
| 740–741 | `secure_url or url`; `bytes or file_size` | `confirm_attachment` R6 |
| 751 | image + pdf → mime | `confirm_attachment` R6 |
| 765 | was_pending → events | `confirm_attachment` R8 |
| 783–786 | soft_delete found / not | `delete_attachment` R1, R1a, R2 |
| 786–800 | ledger + events | `delete_attachment` R3, R4 |
| 801 | ready and public_id | `delete_attachment` R5, R6 |
| 802–811 | not configured / any error swallowed | `delete_attachment` R7 |

## Gap log
- G1 (attachment_manager.cases.md gap 1) — Intent — new **PR-5**: no `role` parameter in any of the three specs; the manager reads the caller's active role and `is_platform_admin` itself (as `ProjectManager._is_privileged` and the discussion service). Caller argument per method listed there; `get_pdf_page_image` gains a required keyword `user_id` (no default, as the discussion service's `list`); a signature-aware call helper keeps today's pass cards valid. Decided by Claude under the reviewer's delegation (2026-11-04).
- G2 (gap 2) — Fact — Facts: parent builder table (required columns, label column, activity table and its parent-id column, metadata column names).
- G3 (gap 3) — Intent — PR-2: the manager does no membership check of its own; the API gate decides who enters the workspace (one gate, as discussions and projects). A non-member passes PR-2 for workspace-wide types; private projects and tickets are judged by their own rules. Decided by Claude under the reviewer's delegation (2026-11-04).
- G4 (gap 4) — Fact — Facts: all enums from `app.models.enums` (str enums).
- G5 (gap 5) — Fact — Facts: Cloudinary helpers are keyword-only; keyword names per call listed.
- G6 (gap 6) — Fact — Facts: `AttachmentDerivedUrls` attributes; `AttachmentLinkInfo(entity_type enum member, entity_id)`; `build_signed_delivery_url` keywords per call.
- G7 (gap 7) — Intent — `confirm_attachment` Inputs and PR-5: with `performed_by=None` the uploader is the caller for R1a (same fallback as the actor). Decided by Claude under the reviewer's delegation (2026-11-04).
- G8 (gap 8) — Fact — Facts: `deleted_at` comes from `app.dao.attachment.utcnow` (naive UTC today; BUG-1430 makes it aware).
- G9 (markup cases gap 2, applied here because PR-3 lives here) — Intent — PR-3: only links in the caller's workspace count; a link under another workspace is ignored (HR-16); no such link → 404 as missing. Folded into BUG-2091's intended text. Decided by Claude under the reviewer's delegation (2026-11-04).
- G10 (attachment_manager.cases.md gap 9) — Contradiction — Overview "Integration-only behavior" corrected: the role lookup is the manager's own under PR-5, so BUG-1885 role cases are unit cases. (2026-11-04)
- G11 (attachment_manager.verify.md finding 5) — Intent — PR-2: the workspace owner opens every help ticket of the workspace; today's `can_access_ticket` differs → BUG-2103. Decided by Claude under the reviewer's delegation (2026-11-04).
- G12 (verify findings 2, 3) — Intent — PR-4, `confirm_attachment` R1a, `get_pdf_page_image` R2: the visibility refusal precedes every state- or input-dependent error and the `ready` early return. Part of BUG-2091. Decided by Claude under the reviewer's delegation (2026-11-04).
- G13 (mobile verify R2-1, 2026-11-04) — Intent — PR-4 wording: at promote the parent-record refusal precedes the staged file's size, name and type checks. Decided by Claude under the reviewer's delegation (2026-11-04).
