# Spec — `app/services/attachment_service.py`

> **Status:** APPROVED (2026-11-04; nothing open. Every item decided by Claude under the reviewer's delegation (2026-11-04), or already settled upstream: OQ-5, OQ-18, HR-13, HR-16, attachment manager PR-1 … PR-5.)
> **Source commit:** e48a092
> **Revision 2026-11-04 (fill-gaps, `attachment_service.cases.md` gaps 1–3; decided by Claude under the reviewer's delegation (2026-11-04)):** HR-13 vs TC3 stated (`confirm_upload` R3a); the post-commit Cloudinary delete of BUG-2202 is patched on `app.managers.attachment_manager.destroy_resource`; BUG-2201's statement bound corrected to ≤ 3 on `attachment_links`. No new bug; status stays APPROVED.
> **Revision 2026-11-05 (verifier, `attachment_service.verify.md` findings 5, 6; decided by Claude under the reviewer's delegation (2026-11-05)):** `confirm_upload` R3b: the no-`public_id` refusal is a plain validation refusal under TC3 (rolled back, nothing recorded), not HR-13. `delete_attachment` R4a: the Cloudinary delete runs right after the commit, before the re-read; a delete error is logged and swallowed. Folded into BUG-2202's intended text. No new bug; status stays APPROVED.

> **Form.** As `tests/unit/services/help_ticket_service.spec.md`. The **Transaction contract TC1–TC6** is defined in `tests/unit/services/base_service.spec.md` and cited here. Below the service: `tests/unit/managers/attachment_manager.spec.md` (APPROVED, verified PASS; its **Parent-record rule PR-1 … PR-5** and every manager rule are cited, not restated), `tests/unit/dao/attachment.spec.md` (`get_active`), `tests/unit/dao/attachment_link.spec.md` (`get_attachments_for_entity`, `count_linked_attachments_for_entity`).
>
> **Routed here and written as rules:** attachment manager FU-1 (a) BUG-2095 → `confirm_upload` R3; (b) one links query per listed attachment → BUG-2201; (c) the caller passed down for BUG-1870 / BUG-1950 / BUG-2091 → `list_attachments` R2, `get_attachment` R2, `get_pdf_page_image` R2 (no new ID: those bugs' intended text already needs the caller); (d) Cloudinary file deleted before the commit → BUG-2202; (e) `AttachmentNotFoundError` → 404 on sign → BUG-2203. Attachment link DAO FU-1 (a) (the list must look at the record) → BUG-2200.
>
> **Read, not run.** Every rule was read in the code and in the approved manager and DAO specs (which were run on `marker_test`). Nothing here needed a new database run.

## Review
> All items decided; nothing pending.

### Quick list — all decided
| # | What the code does today, in plain words | Decision | Decided by |
|---|---|---|---|
| D1 | A failed confirm is recorded by the manager, then rolled back here | bug — BUG-2095 (already logged): the failure record is committed, the error still returned | HR-13 (house rule), manager spec |
| D2 | The attachment list of an unknown or deleted record answers 200 with its files | bug — 404 `<entity_type> <entity_id> not found.`, as PR-1 → BUG-2200 | Claude, delegated (link DAO P2 / FU-1 (a)) |
| D3 | The list reads each attachment's links one query at a time | bug — read together → BUG-2201 | Claude, delegated (BUG-1964 precedent) |
| D4 | Deleting an attachment deletes its Cloudinary file before the delete is saved | bug — the file is deleted only after the commit → BUG-2202 | Claude, delegated (manager FU-1 (d)) |
| D5 | A record refused as not found answers 500 on sign and on the list | bug — 404 → BUG-2203 (endpoints) | Claude, delegated (manager FU-1 (e)) |
| D6 | List, single read and PDF page get no caller, so they cannot apply the record's visibility | bug — already BUG-1870 / BUG-1950 / BUG-2091: each takes a required `user_id` | owner, OQ-5 / OQ-18 (applied) |

### House-rule violations — applied automatically
- **HR-13** `confirm_upload` R3 — the manager marks the attachment `failed` and writes a `failed` ledger row with Cloudinary's reason, then raises `AttachmentConfirmError`; this service rolls everything back, so no trace of the failed attempt survives. Intended: the failure record is committed, then the error is raised.
**Answer:** bug — per HR-13 (house rule)
**Resolution:** 🐞 BUG-2095 (already logged from the attachment manager spec, pattern `failure-record-rolled-back`). Rules: `confirm_upload` R3.

Checked and **not** violated: **HR-4** — `get_attachment` uses `get_active` (deleted → 404); the list leaves deleted attachments out (link DAO R3); deleted *records* are PR-1 (D2). **HR-5, HR-6** — filtering and order are the link DAO's (BUG-1432). **HR-7** — the list endpoint requires `1 <= limit <= 200`, `skip >= 0`. **HR-9, HR-10** — the manager's (BUG-2094). **HR-11** — confirm trusts only Cloudinary's Admin API (manager R4 ✅). **HR-16** — every read and write is scoped by the caller's workspace; another workspace's attachment id is "not found". **HR-1 … HR-3, HR-8, HR-12, HR-14, HR-15** — none applies.

**Permission checks (this service and its manager):** membership is the API gate's (`get_current_workspace`); the record's own visibility is PR-2 / PR-3, applied in the manager, with the caller passed from here (PR-5).

### Decided items (Claude, under the reviewer's delegation, 2026-11-04)

### D2. The list of an unknown or deleted record answers with its files — 🐞 BUG-2200
**Background:** The list (`GET /attachments/?entity_type=…&entity_id=…`) reads attachments through their links and never looks at the record (link DAO P2: intended at the DAO, the service must check, FU-1 (a)). Projects, machines and work orders are soft-deleted; a deleted record hides its children (PR-1).
**What happens today:** A soft-deleted machine's photos are listed (200) with their signed URLs; an unknown id answers `{"items": [], "slot_count": 0, …}`; another workspace's id answers an empty list.
**Example:** A machine is deleted; a member with an old link opens its attachment panel and still downloads every photo of it.
**Rules affected:** `list_attachments` R1a
**Answer:** bug — PR-1 for the list: an unknown, deleted, or another workspace's record → `AttachmentNotFoundError("<entity_type> <entity_id> not found.")`, 404 at the API; `scratch` passes. Same wording as sign (BUG-2090).
**Resolution:** 🐞 BUG-2200 (pattern `child-ignores-parent-visibility`, as BUG-2091 for deleted parents).

### D3. One links query per listed attachment — 🐞 BUG-2201
**Background:** Each item of the list is built by `AttachmentManager.to_response`, which reads that attachment's links with its own query. A page holds up to 200 items.
**What happens today:** A page of 200 attachments makes 200 link queries after the list and the count.
**Example:** A purchase order with 25 photos makes 27 queries to show its panel.
**Rules affected:** `list_attachments` R5
**Answer:** bug — per BUG-1964 precedent: the links of every listed attachment are read together; the number of statements does not grow with the page; the result is unchanged.
**Resolution:** 🐞 BUG-2201 (pattern `n-plus-one-read`).

### D4. The Cloudinary file is deleted before the delete is saved — 🐞 BUG-2202
**Background:** `DELETE /attachments/{id}` soft-deletes the row and asks Cloudinary to delete the file, both inside the manager; this service commits afterwards. Cloudinary cannot be rolled back.
**What happens today:** If anything after the Cloudinary delete fails (the commit, a database error in the activity entries), the row is rolled back and stays live and `ready`, while its file is gone: the attachment shows in the list and every preview or download fails.
**Example:** The database connection drops during the commit of a delete. The photo is still listed on the order, but opening it gives Cloudinary's "not found".
**Rules affected:** `delete_attachment` R4
**Answer:** bug — the Cloudinary delete runs only after the commit succeeded (with the manager's rules R5–R7 unchanged: which states, swallowed errors, the WARNING of BUG-2100); a failed transaction calls Cloudinary not at all.
**Resolution:** 🐞 BUG-2202 (pattern `external-delete-before-commit`, new). Fix spans `AttachmentManager.delete_attachment` (return what to delete instead of deleting) and this service.

### D5. A record refused as not found answers 500 — 🐞 BUG-2203
**Background:** After BUG-2090 / BUG-2200 the manager refuses a missing, deleted or hidden record with `AttachmentNotFoundError`. The sign endpoint maps every unknown error to 500 "Failed to prepare upload."; the list endpoint maps nothing. The QR endpoints have the same gap (mobile upload service spec).
**What happens today:** Not reachable yet (nothing raises it there); once the bugs above are fixed, the refusals would answer 500.
**Example:** A member signs an upload for a deleted project and sees "Failed to prepare upload." instead of "project 12 not found.".
**Rules affected:** `sign_upload` R2, `list_attachments` R1a (integration-only)
**Answer:** bug — `AttachmentNotFoundError` → 404 with its message on `POST /attachments/sign` and `GET /attachments/` (and the two QR endpoints, mobile spec).
**Resolution:** 🐞 BUG-2203 (pattern `wrong-error-type-uncaught`). Fix in `app/api/v1/endpoints/attachments.py` and `mobile_upload.py`; integration-only, not a unit case.

## Follow-ups for other reviews
| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Attachments endpoint** (`app/api/v1/endpoints/attachments.py`) | (a) BUG-2203. (b) `GET /attachments/`, `GET /attachments/{id}` and `GET …/pdf-page` do not take `current_user` today; BUG-1870 / BUG-1950 / BUG-2091 need it passed as `user_id`. | D5, D6 |

## Overview
`AttachmentService` is the transaction boundary of the desktop attachment flow: sign an upload, confirm it, list a record's attachments, read one, get a PDF page image, delete. `app/api/v1/endpoints/attachments.py` calls it; the endpoint maps the manager's plain errors (`AttachmentNotFoundError` → 404, `AttachmentValidationError` / `AttachmentLimitError` / `AttachmentConfirmError` → 400, `CloudinaryNotConfiguredError` → 503, anything else on sign / confirm / delete → 500). Every rule about what is written, checked and shown is the manager's; this service decides what is committed, passes the caller down, and builds the list and PDF-page answers.

**Callables:** 6 specified · 2 not specified
**Externals to mock:** Cloudinary, as imported in `app.managers.attachment_manager` (`generate_upload_signature`, `build_signed_delivery_url`, `get_resource`, `destroy_resource`); `time.time`, `uuid.uuid4` there; `settings` (`app.services.attachment_service.settings.MAX_ATTACHMENTS_PER_ENTITY`, and the manager's `CLOUDINARY_*`). Never call Cloudinary over the network.
**Integration-only behavior:** the endpoint error mapping above (BUG-2203); the role lookup and membership gate (`get_current_workspace`); query bounds of `GET /attachments/` (`entity_id >= 1`, `0 <= skip`, `1 <= limit <= 200`) and of `pdf-page` (`page >= 1`, `400 <= width <= 3200`).

**Facts for the test designer**
- Import: `from app.services.attachment_service import AttachmentService, attachment_service, AttachmentNotFoundError, AttachmentConfirmError, AttachmentValidationError` (the last three re-exported from the manager / allowlist). `AttachmentLimitError` from `app.managers.attachment_manager`; `CloudinaryNotConfiguredError` from `app.core.cloudinary_client`. Every parameter after `db` is keyword-only. The manager is the attribute `manager`.
- Responses: `AttachmentSignResponse` (manager `build_sign_response` R3); `AttachmentResponse` (manager `to_response` R1–R4); `AttachmentListResponse(items, slot_count, max_per_entity)`; `AttachmentPdfPageResponse(url: str, page: int, page_count: int | None)`.
- Parent builders, enums, Cloudinary keyword names, stub shapes: attachment manager spec **Facts**.
- New parameters (intended, BUG-1870 / BUG-1950 / BUG-2091; PR-5): `list_attachments`, `get_attachment` and `get_pdf_page_image` gain a keyword-only `user_id: int`, required, no default, passed to the manager. Write pass cards through a helper that adds `user_id=` only when `inspect.signature` has it (as the manager spec's Notes).

**Notes for the test designer**
- Transaction mechanics (TC1–TC6): `base_service.spec.md` Notes.
- **BUG-2095:** stub `get_resource` to raise `RuntimeError("boom")`; call `confirm_upload`, expect `AttachmentConfirmError`; then `db.rollback()` at test level and re-select: intended `upload_status == "failed"` and one `failed` ledger row survive → strict xfail.
- **BUG-2201:** count statements touching `attachment_links` with a `before_cursor_execute` listener: 5 listed attachments → at most **3** such statements (the list R1, the count R3, one batched links read R5) → strict xfail (today 7). *(Corrected 2026-11-04, cases gap 1; was "≤ 2".)*
- **BUG-2202:** patch target, before and after the fix: `app.managers.attachment_manager.destroy_resource`. The fixed code keeps calling it through that module's import, whichever layer (manager or service) calls it after the commit (cases gap 2). Patch `db.commit` to raise; intended: `destroy_resource` not called; today it is called → strict xfail. Also: the row stays live after the failed commit (holds today).
- **BUG-2200:** a machine with `is_deleted=True` holding one ready attachment → `AttachmentNotFoundError("machine <id> not found.")` → strict xfail.

## Not specified
- `AttachmentService.__init__` — stores the manager singleton, no logic.
- `attachment_service`, `__all__` — module singleton and re-exports, no logic.

---

## `AttachmentService.sign_upload(db, *, workspace, user, payload)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `POST /attachments/sign`, 201)

**Purpose:** Record a pending upload for a record and answer the Cloudinary upload parameters.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace` | `Workspace` | its `id` scopes everything; its `name` is the first folder level |
| `user` | `Profile` | the uploader and the caller (PR-5) |
| `payload` | `AttachmentSignRequest` | `entity_type`, `entity_id ≥ 1`, `file_name` 1–255, `mime_type` 1–128, `file_size ≥ 1`, `note` (BUG-2102: ≤ 500 intended) |

**Returns:** the `AttachmentSignResponse` of manager `build_sign_response` R3, built before the commit.

**Rules:**
- **R1.** The file is validated first (manager `normalize_upload_request` R1: allowlist errors, e.g. too large, unsupported extension → `AttachmentValidationError`); a refusal writes nothing.
- **R2.** The record and the caller's right to it are checked when the attachment is written (manager `create_pending_attachment` R1a [BUG-2090], R1b [BUG-1870, BUG-1950]: `AttachmentNotFoundError("<entity_type> <entity_id> not found.")`); then capacity (R2: `AttachmentLimitError`). A refusal writes nothing (TC3). [BUG-2203] At the API the not-found refusal answers 404 with its message. *(Today: 500 "Failed to prepare upload."; integration-only.)*
- **R3.** On success one `pending` attachment, its link and a `pending` ledger row are written as manager `create_pending_attachment` R3–R7, with `public_id` = a fresh `build_public_id(workspace_id=workspace.id)`, `asset_folder` = `build_asset_folder(workspace.name, payload.entity_type, <label of resolve_entity_label>)`; the response carries the same `public_id`, `asset_folder`, and `display_name = build_display_name(<normalized file name>)`. All committed (TC1).
- **R4.** With Cloudinary not configured (manager `build_sign_response` R1, R2) `CloudinaryNotConfiguredError` is raised after the attachment was flushed; it is rolled back: no attachment, link or ledger row remains (TC3).
- **R5.** After the commit the attachment is re-read (`db.refresh`); the response is not changed by it. A failure of that re-read reaches the caller and the attachment stays saved (TC5). Commit failure: TC4.
- **R6.** Any other error rolls back and reaches the caller unchanged (TC3).

**Errors:** `AttachmentValidationError`, `AttachmentNotFoundError` (intended), `AttachmentLimitError`, `CloudinaryNotConfiguredError`, database errors — all unchanged.

**Side effects:** attachment, link, ledger rows, committed. No Cloudinary network call (the signature is computed locally).

---

## `AttachmentService.confirm_upload(db, *, workspace_id, attachment_id, performed_by=None, payload=None)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `POST /attachments/{id}/confirm`; the endpoint always passes `performed_by = current_user.id`)

**Purpose:** After the browser's upload, verify the file with Cloudinary, mark the attachment ready and save.

**Inputs:** `payload` (`AttachmentConfirmRequest`, an empty model) is passed on and ignored. `performed_by` is the caller (PR-5; `None` → the uploader, manager Inputs).

**Returns:** the attachment's `AttachmentResponse` (manager `to_response` with the caller's `workspace_id`), built after the commit and re-read.

**Rules:**
- **R1.** The transition is manager `confirm_attachment` R1–R11 (including BUG-2091, BUG-2092, BUG-2093, BUG-2094, BUG-2096). On success it is committed (TC1) and the answer shows `upload_status = ready` and the Cloudinary columns as the manager wrote them.
- **R2.** An attachment already `ready` (manager R2) is answered unchanged; nothing written.
- **R3.** [BUG-2095] (HR-13) When the manager raises `AttachmentConfirmError` (Cloudinary lookup failed, R4; file refused, R5; too large, R6a), what it flushed — `upload_status = failed` and the `failed` ledger row with the reason — is **committed**, then that same error reaches the caller. The no-`public_id` refusal is not one of these (R3b). *(Today: rolled back; the attachment stays `pending` and no ledger row survives.)* If that commit itself fails, TC4.
- **R3a.** HR-13 versus TC3 (cases gap 3, decided by Claude under the reviewer's delegation (2026-11-04)): "commit, then raise" commits the session **as it stands**, so a change pending in the session that is unrelated to the confirm is committed with the failure record. Each request owns its session, so in practice nothing unrelated is pending. TC3 (discard everything on an error) applies only to the errors where HR-13 does not, R3b and R4.
- **R3b.** (verify finding 5, decided by Claude under the reviewer's delegation (2026-11-05)) The no-`public_id` refusal (manager R3, `AttachmentConfirmError("Attachment has no public_id.")`) is a plain validation refusal, not a failed upload: nothing was uploaded, so there is no failure to keep and HR-13 does not apply. TC3 applies: the session is rolled back, nothing is recorded, and unrelated pending changes are discarded; the error reaches the caller unchanged. Under PR-4 the visibility refusal comes first: an attachment without `public_id` whose record the caller may not open answers `AttachmentNotFoundError` (404, BUG-2091, manager R1a), not this 400.
- **R4.** Every other error (`AttachmentNotFoundError`, `CloudinaryNotConfiguredError` per BUG-2096, `AttachmentValidationError` per BUG-124, database errors) rolls back and reaches the caller unchanged (TC3).
- **R5.** Commit failure on success: TC4. A failure of the re-read or of the response after the commit: TC5 (the `ready` state stays saved).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing / hidden attachment | `AttachmentNotFoundError` | `Attachment <id> not found.` |
| verification failed | `AttachmentConfirmError` | manager messages |
| Cloudinary not configured (BUG-2096) | `CloudinaryNotConfiguredError` | client message |

**Side effects:** attachment updated, ledger row, activity entries (manager), committed; on R3 the failure record committed; one Cloudinary Admin API lookup (manager).

---

## `AttachmentService.list_attachments(db, *, workspace_id, entity_type, entity_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `GET /attachments/`)

**Purpose:** The record's ready attachments, with how many of its places are used.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `entity_type` | `AttachmentEntityTypeEnum` | its `.value` is matched |
| `entity_id` | int | not looked up today (BUG-2200) |
| `skip`, `limit` | int | passed to the link DAO; bounded only at the endpoint |
| `user_id` | int | *(intended, BUG-1870 / BUG-1950; new keyword-only, required)* the caller |

**Returns:** `AttachmentListResponse(items, slot_count, max_per_entity)`.

**Rules:**
- **R1.** `items` are the record's attachments as link DAO `get_attachments_for_entity` R1–R6 returns them for the caller's workspace (ready and live only, newest first, paged; BUG-1432), each mapped by manager `to_response` with `workspace_id` = the caller's.
- **R1a.** [BUG-2200] PR-1: an unknown record, a soft-deleted project / machine / work order, a component of a deleted project, or another workspace's record → `AttachmentNotFoundError("<entity_type> <entity_id> not found.")`, nothing returned; `scratch` passes with any id. *(Today: the record is not looked at; a deleted record's files are listed, unknown and other-workspace ids give an empty list.)*
- **R2.** [BUG-1870, BUG-1950] PR-2: a record the caller may not open (private project, its component, a help ticket `can_access_ticket` refuses, with the workspace owner's exception of BUG-2103) → the same error as R1a. The caller is the new `user_id`; the role and platform-admin flag are read by the manager (PR-5). Checked before anything is read (PR-4). *(Today: no caller; any member lists them.)*
- **R3.** `slot_count` is link DAO `count_linked_attachments_for_entity` R1–R4 for the same record and workspace (`pending` and `ready`, not deleted; `failed` excluded per BUG-1434), independent of `skip` / `limit`.
- **R4.** `max_per_entity` = `settings.MAX_ATTACHMENTS_PER_ENTITY` at the call (default 25).
- **R5.** [BUG-2201] (D3) The links of all listed attachments are read together: the number of statements does not grow with the number of items; the result is unchanged. *(Today: one links query per item.)*
- **R6.** Read only (TC6): no commit, no rollback; an error reaches the caller unchanged. A negative `skip` / `limit` (direct call) raises `DataError` (link DAO R5).

**Errors:** `AttachmentNotFoundError` (intended, R1a / R2); `DataError` (R6).

**Side effects:** none

---

## `AttachmentService.get_attachment(db, *, workspace_id, attachment_id)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `GET /attachments/{id}`)

**Rules:**
- **R1.** A live attachment of the caller's workspace, in any upload state (`pending`, `ready`, `failed`; attachment DAO `get_active` R1), is answered by manager `to_response` with the caller's `workspace_id` (URLs only when `ready`, `derive_urls`).
- **R1a.** Unknown id, `0`, soft-deleted, or another workspace's → `AttachmentNotFoundError("Attachment <id> not found.")` (404 at the API).
- **R2.** [BUG-2091] PR-3: an attachment whose linked record fails PR-1 or PR-2 for the caller, or with no link in the caller's workspace, → the same error as R1a, before anything about it is shown. *(Today: not checked; requires a new keyword-only `user_id`, required, PR-5.)*
- **R3.** Read only (TC6).

**Errors:** R1a, R2. **Side effects:** none

---

## `AttachmentService.get_pdf_page_image(db, *, workspace_id, attachment_id, page, width=1600)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `GET /attachments/{id}/pdf-page`)

**Rules:**
- **R1.** The answer is manager `get_pdf_page_image` R1–R3 as an `AttachmentPdfPageResponse` (`url`, `page`, `page_count`); its errors (`AttachmentNotFoundError`, `AttachmentValidationError`, `AttachmentConfirmError`, `CloudinaryNotConfiguredError`) reach the caller unchanged.
- **R2.** [BUG-2091] The caller is passed to the manager as its new required `user_id` (PR-5), so a hidden attachment answers 404 before any page or state check (PR-4). *(Today: the service has no caller to pass; requires a new keyword-only `user_id` here too.)*
- **R3.** Read only (TC6).

**Errors:** as R1. **Side effects:** none

---

## `AttachmentService.delete_attachment(db, *, workspace_id, attachment_id, deleted_by)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `DELETE /attachments/{id}`)

**Returns:** the deleted attachment's `AttachmentResponse` (re-read after the commit; `urls` from `derive_urls`).

**Rules:**
- **R1.** The delete is manager `delete_attachment` R1–R8 (BUG-2091, BUG-2097 … BUG-2100), committed (TC1); `deleted_by` is the caller.
- **R2.** When the manager finds nothing to delete (returns `None`: unknown, another workspace's, already deleted per BUG-2097, hidden per BUG-2091) → `AttachmentNotFoundError("Attachment <id> not found.")`, rolled back, nothing written (404 at the API).
- **R3.** Any other error rolls back and reaches the caller unchanged (TC3); commit failure TC4; re-read or response failure after the commit TC5 (the delete stays saved).
- **R4.** [BUG-2202] (D4) The Cloudinary file is deleted only after the commit succeeded; when the transaction fails (an error, or the commit itself), Cloudinary is not called and the attachment stays live with its file. Which states delete a file, and the swallowed-error WARNING, are manager R5–R7 (BUG-2099, BUG-2100). *(Today: the manager deletes the file before the commit; a failed commit leaves a live row without a file.)*
- **R4a.** [BUG-2202] (verify finding 6, decided by Claude under the reviewer's delegation (2026-11-05)) The Cloudinary delete runs right after the commit succeeded and **before** the re-read and the response, so a failing re-read or response (TC5: the delete stays saved) still has the file deleted and leaves no orphan. An error of that delete is logged as a WARNING naming the `public_id` and the error, and swallowed (BUG-2100): the call still answers the deleted attachment, never a 500 because of it. *(Today: the delete runs before the commit, inside the manager.)*

**Errors:** `AttachmentNotFoundError` (R2); others unchanged.

**Side effects:** row soft-deleted, ledger row, activity entries, committed; one Cloudinary delete (after the commit, intended).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 41–42 | normalize (raises on invalid file) | `sign_upload` R1 |
| 43–64 | label, folder, public id, display name; `create_pending_attachment` (PR-1 / PR-2 missing: BUG-2090, BUG-1870, BUG-1950; capacity) | `sign_upload` R2, R3 |
| 65–70 | `build_sign_response` (may raise not configured) | `sign_upload` R3, R4 |
| 71–73 | commit; refresh; return response | `sign_upload` R3, R5 |
| 74–76 | any exception → rollback, re-raise | `sign_upload` R2, R4, R6 |
| 88–94 | `confirm_attachment` | `confirm_upload` R1, R2 |
| 95–97 | commit; refresh; `to_response` | `confirm_upload` R1, R5 |
| 98–100 | any exception → rollback (failure record lost: BUG-2095) | `confirm_upload` R3, R3a, R3b, R4 |
| 112–119 | link DAO list (no record check: BUG-2200; no caller: BUG-1870 / BUG-1950) | `list_attachments` R1, R1a, R2 |
| 120–125 | link DAO count | `list_attachments` R3 |
| 126–133 | response; `to_response` per item (BUG-2201); max from settings | `list_attachments` R1, R4, R5, R6 |
| 144–146 | `get_active` → `None` → not found | `get_attachment` R1a |
| 147 | `to_response` (no visibility check: BUG-2091) | `get_attachment` R1, R2, R3 |
| 160–167 | manager PDF page (no caller: BUG-2091); wrap in response | `get_pdf_page_image` R1–R3 |
| 178–183 | manager delete (Cloudinary delete inside: BUG-2202) | `delete_attachment` R1, R4 |
| 184–185 | `None` → not found | `delete_attachment` R2 |
| 186–188 | commit; refresh; `to_response` | `delete_attachment` R1, R3, R4a |
| 189–191 | any exception → rollback, re-raise | `delete_attachment` R2, R3 |
| 194–202 | singleton, re-exports | Not specified |

## Gap log
- G1 (attachment_service.cases.md gap 1) — Contradiction — Notes BUG-2201: the bound is ≤ 3 statements on `attachment_links` (list, count, one batched links read), not ≤ 2. Decided by Claude under the reviewer's delegation (2026-11-04).
- G2 (gap 2) — Fact / Intent — Notes BUG-2202: `destroy_resource` stays imported in `app.managers.attachment_manager` after the fix, whichever layer calls it; tests patch it there. Decided by Claude under the reviewer's delegation (2026-11-04).
- G3 (gap 3) — Intent — `confirm_upload` R3a: HR-13's commit takes the session as it stands (unrelated pending changes included; none in practice, one session per request); TC3 applies to the non-HR-13 errors only. Decided by Claude under the reviewer's delegation (2026-11-04).
- G4 (attachment_service.verify.md finding 5) — Intent — `confirm_upload` R3b: no-`public_id` refusal follows TC3 (rolled back, nothing recorded, unrelated pending changes discarded); HR-13 does not apply; PR-4's 404 precedes it. Decided by Claude under the reviewer's delegation (2026-11-05).
- G5 (verify finding 6) — Intent — `delete_attachment` R4a: Cloudinary delete right after the commit, before the re-read; its error logged as WARNING and swallowed (BUG-2100), never 500. Folded into BUG-2202. Decided by Claude under the reviewer's delegation (2026-11-05).
