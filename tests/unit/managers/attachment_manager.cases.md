# Test cases — `app/managers/attachment_manager.py`

> **Spec:** `tests/unit/managers/attachment_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — spec fill-gaps 2026-11-04 (G1–G9): new PR-5 (no `role` parameter; role from an active membership and `is_platform_admin` read by the manager; `get_pdf_page_image` gains a required `user_id`), PR-2 no membership check of its own (G3), PR-3 only W1 links count (G9), `performed_by=None` → the uploader is the caller (G7), Facts (parent columns, enums, keyword-only Cloudinary calls, result shapes, `deleted_at` clock). Every `role=` dropped; allowed-access cards on create / confirm / delete / PDF page now pass today; new C-59…70, PG-36…43, CF-87…99, D-56…63; CF-08 and D-05 rebuilt; all 8 spec gaps closed.
> **Revision:** 3 — executor notes (2026-11-04): link order is BUG-1433 (link DAO unordered), so LG-03, TR-01, CF-08, CF-24, D-06 now check the link as a set / pair membership; order moved to new LG-08, TR-07 (non-strict) with the strict alarm LG-09 (ORDER BY on the links query). CP-03 is strict xfail BUG-1434 (failed uploads still counted). D-41, D-47: Fails-today lines name the IntegrityError at the call. Card mechanics: `bsu` echo is a JSON string read by `args_of`; SR cards read the sign response by attribute; `fill` numbers on across calls.
> **Revision:** 4 — verifier findings 1–5 and spec G11 / G12 / BUG-2103 (2026-11-04): platform admin refused a private project and a private project's component on every path (C-71, C-72, PG-44, PG-45, CF-100, CF-101, D-64, D-65; finding 1); workspace owner with a plain role opens another member's ticket on every path (C-73, PG-46, CF-102, D-66; BUG-2103, pass cards: nothing is checked today, so no card can fail on it); a hidden ready attachment answers 404 on confirm and leaks no name, public_id or URL (CF-103, CF-104; finding 2); refusal before validation: hidden + page 0, hidden + pending on PDF page, hidden + no public_id on confirm (PG-47, PG-48, CF-105; finding 3, G12); PDF by MIME type alone (PU-15; finding 4, mutant #232).
> **Counts:** 343 cases · 213 expected-to-pass · 130 expected-to-fail (bugs: 128 strict, 2 non-strict) · 5 deferred

## Reviewer summary
- **Depth:** full. The module writes no stock or money, but the Parent-record rule (OQ-5 / OQ-18, HR-16) and every Cloudinary call were asked for at full depth; the pure helpers got one card per rule and boundary.
- **Per callable:** `normalize_upload_request` 2 · `assert_entity_attachment_capacity` 8 (1 bug) · `build_public_id` / `_upload_env` 7 · `build_asset_folder` 4 · `build_display_name` 6 · `resolve_entity_label` / `_fetch_entity_row` 19 · `_extract_entity_label` 3 · `_attachment_event_metadata` 1 · `_append_attachment_ledger` 9 (2 bug) · `_log_attachment_entity_events` 15 · `create_pending_attachment` 67 (40 bug) · `build_sign_response` 6 · `derive_urls` 16 (1 bug) · `build_pdf_page_image_url` 15 · `to_response` 7 (1 bug) · `get_pdf_page_image` 35 (22 bug) · `confirm_attachment` 76 (37 bug) · `delete_attachment` 47 (26 bug).
- **Parent-record rule:** PR-1 shapes (unknown, deleted machine / work order / project, component of a deleted project, W0 and W2 parents, a same-id row in another table via XID, one bad link among two) are run on sign, PDF page, confirm and delete. PR-2 grants and every refused-grant shape (owner / privileged / member / creator held elsewhere; privileged only in W0 or only in W2; suspended or removed (`inactive`) privileged member; project or ticket without creator; membership role "Owner" and "ground-team-manage"; a caller with no membership) are run in full on sign and confirm; PDF page and delete get the core set. PR-3 link rule: a W2-filed link is ignored; no W1 link → 404. PR-4 order (G12): a hidden attachment answers 404 before page 0, not ready, no public_id and the ready early return, and the 404 carries no file name, public_id or URL. The platform admin is refused private projects and their components; the workspace owner opens every ticket (BUG-2103; those cards pass today because nothing is checked yet). Refusals are strict xfail (BUG-2090, BUG-1870, BUG-1950, BUG-2091) and check the session, `nothing written` and that no Cloudinary mock was called. Allowed shapes hold today too, so they are pass cards.
- **Notable design choices:** PR-5: no card passes a role; the role comes from the caller's W1 `workspace_members` row. `get_pdf_page_image` refusal cards pass the new required `user_id` (TypeError today, strict xfail); its pass cards go through `pg`, which adds `user_id` only once the parameter exists. BUG-2094 is checked as "the attachment SELECT carries FOR UPDATE" (ATCM-CF-31); the two-session race is deferred to integration. `build_signed_delivery_url` is patched to echo its arguments, so URL cards compare arguments, not strings. Cards that need missing-key behaviour (`SR-05`, `DU-11`, `PU-11`) run the real signer or URL builder, which work locally with no network.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `ATCM` = `app/managers/attachment_manager.py`. `NU` normalize_upload_request · `CP` assert_entity_attachment_capacity · `PI` build_public_id (+ `_upload_env` / `_is_production`) · `AF` build_asset_folder · `DN` build_display_name · `RL` resolve_entity_label (+ `_fetch_entity_row`) · `XL` _extract_entity_label · `EM` _attachment_event_metadata · `LG` _append_attachment_ledger · `EV` _log_attachment_entity_events · `C` create_pending_attachment · `SR` build_sign_response · `DU` derive_urls · `PU` build_pdf_page_image_url · `PG` get_pdf_page_image · `TR` to_response · `CF` confirm_attachment · `D` delete_attachment. Shared with the markup (`AMUP`) and mobile (`MOBS`) cases: every name below that those files also use means the same thing.

**Imports.** `from app.managers.attachment_manager import AttachmentManager, attachment_manager, AttachmentNotFoundError, AttachmentLimitError, ENTITY_TYPE_FOLDER_LABELS`; `from app.utils.attachment_allowlist import AttachmentValidationError, AttachmentConfirmError, MAX_FILE_SIZE_BYTES, normalize_upload_request`; `from app.core.cloudinary_client import CloudinaryNotConfiguredError`; `from app.schemas.attachment import AttachmentSignRequest`; `from app.models.enums import AttachmentEntityTypeEnum, AttachmentLedgerTransactionTypeEnum, UploadStatusEnum, ProjectVisibilityEnum` (all `str` enums); `from app.schemas.attachment import AttachmentDerivedUrls`; `inspect`; models `Attachment`, `AttachmentLink`, `AttachmentLedger`, `AttachmentMarkup`, `Project`, `ProjectComponent`, `ProjectMember`, `Machine`, `Item`, `HelpTicket`, `WorkspaceMember`, `Factory` from `app.models.<module>`. `ValidationError` (pydantic), `IntegrityError` (sqlalchemy.exc), `event`, `text` (sqlalchemy), `patch` (unittest.mock), `SimpleNamespace`, `uuid`, `logging`, `re`, `os`, `datetime`.

**Fixed values.** `AM` = `attachment_manager`. `db` = the test's real session, first argument; every other argument by keyword unless the spec says positional. `result` = what the When returns. The session never autoflushes. MISSING = `999999999`. T0 = `datetime(2025, 12, 1, 8, 0, 0)`. NOW = `datetime(2026, 3, 1, 10, 0, 0)` (naive). **XID(k)** = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`; "`id XID(k)`" passes `id=XID(k)` to the builder (used when a card relies on ids across tables). TOKEN = `"0123456789abcdef0123456789abcdef"`. BIG = `MAX_FILE_SIZE_BYTES` = `10485760`.

**Settings (every test).** `monkeypatch.setattr` on `app.managers.attachment_manager.settings`: `CLOUDINARY_UPLOAD_ENV "development"`, `ENVIRONMENT "development"`, `CLOUDINARY_CLOUD_NAME "demo-cloud"`, `CLOUDINARY_API_KEY "123456"`, `CLOUDINARY_API_SECRET "s3cret"`, `MAX_ATTACHMENTS_PER_ENTITY 25`. A Given line "settings: NAME value" overrides one the same way.

**Externals (every test, patched on `app.managers.attachment_manager`; never the network).**
- **gr** = `get_resource`, `return_value` = **RES** = `{"resource_type": "image", "format": "jpg", "bytes": 1234, "version": 1700000000, "secure_url": "https://res.example/s.jpg", "url": "http://res.example/u.jpg", "width": 800, "height": 600, "asset_id": "a" * 32, "etag": "e" * 32}`.
- **dr** = `destroy_resource`, `return_value {"result": "ok"}`. **gus** = `generate_upload_signature`, `return_value "sig-x"`.
- **bsu** = `build_signed_delivery_url`, `side_effect` = **echo**: `echo(*a, **k)` returns the string `"echo:" + json.dumps(dict(zip(["public_id", "resource_type", "delivery_type", "version"], a), **k))` (a string, so it passes the `str | None` URL fields). **args_of(u)** = `json.loads(u[len("echo:"):])`. In a card, `u["fmt"]`, `u["transformation"]`, `u.get("flags")` on a URL `u` mean `args_of(u)["fmt"]` etc.; `result["…"]` on a result of `build_pdf_page_image_url` and `result["url"]["…"]` on `get_pdf_page_image` read the URL the same way.
- A Given line "**real bsu**" / "**real gus**" = that function is not patched in this test (it signs locally; no network).
- **fixed uuid** = `patch("app.managers.attachment_manager.uuid.uuid4", return_value=uuid.UUID(TOKEN))`. **fixed time** = `patch("app.managers.attachment_manager.time.time", return_value=1767225600.9)`.
- Every Cloudinary helper is called with keywords only: `gus(public_id=, asset_folder=, display_name=, timestamp=, delivery_type=)`, `gr` / `dr(public_id=, resource_type=, delivery_type=)`, `bsu(public_id=, resource_type=, delivery_type=, version=, fmt=, transformation= | flags=)`.
- **dao clock** (only where a card names it) = `patch("app.dao.attachment.utcnow", return_value=NOW)` around the When. **stored_utc(X)** = `db.scalar(text("SELECT deleted_at AT TIME ZONE 'UTC' FROM attachments WHERE id = :i"), {"i": X.id})`.
- **cl_untouched** = `gr.called is False`, `dr.called is False`, `bsu.called is False`, `gus.called is False` (four asserts on one Then line).

**Standing rows** (every test, no Given line, built in this order, each flushed): W0, W1, W2 = `make_workspace(db)` (`W0.id < W1.id < W2.id`; no `owner_user_id`). U1 = `make_profile(db, name="Ana Rahman")`, U2 = `make_profile(db, name="Bilal Khan")`, UG = `make_profile(db, name="Mia Khan")`, UA = `make_profile(db, name="Sam Admin", is_platform_admin=True)`. Memberships: member(U1, "ground-team"), member(U2, "owner"), member(UG, "ground-team"); UA has none. F0 = `Factory(workspace_id=W0.id, name="Factory Zero", abbreviation="F0")`, F1 = the same in W1 (`name "Factory One"`, `abbreviation "F1"`), F9 = the same in W2 (`name "Factory Nine"`, `abbreviation "F9"`).

**Given rows** (added and flushed one at a time in the order written; after "but" every column that differs; a line written as code runs as written).
- **member(U, role, status="active", ws=W1)** = `WorkspaceMember(workspace_id=ws.id, user_id=U.id, role=role, status=status)`. **removed(U, role)** = member(U, role, status="inactive") with `left_at T0` (what a removal writes). **set_owner(W, U)** = `W.owner_user_id = U.id`, `db.flush()`.
- **parent(type, "L")** = a live row of that type's table in W1 whose label column is "L", with the required columns of the spec's Facts table set as that table's DAO spec builder sets them (purchase orders: `po_number`, `destination_type`, `destination_id`, `current_status_id`, `created_by U1.id`; sales orders: `sales_order_number`, `account_id`, `factory_id F1.id`, `current_status_id`, `created_by U1.id`; expense orders: `expense_number`, `expense_category`, `created_by U1.id`; transfer orders: `transfer_number`, the four location columns, `current_status_id`, `created_by U1.id`; work orders: `work_order_number`, `work_order_type_id`, `title`, `factory_id F1.id`; account invoices: `invoice_number`, `account_id`, `invoice_type`, `invoice_amount`, `invoice_date`). `current_status_id` is a real `statuses` row of the same workspace (status DAO spec builder), never a placeholder; `account_id` / `work_order_type_id` are real rows of the same workspace built just before. "of W0" / "of W2" = that workspace (factories, statuses, accounts and types then of that workspace).
  - **mach("L")** = `Machine(workspace_id=W1.id, factory_id=F1.id, name="L")`. **item("L", sku)** = `Item(workspace_id=W1.id, name="L", name_normalized="L".lower(), unit="pcs", sku=sku)`.
  - **proj("L")** = `Project(workspace_id=W1.id, factory_id=F1.id, name="L", description="Main", created_by=U1.id)`; **private** = `visibility "invited_only"`. **comp(P, "L")** = `ProjectComponent(workspace_id=P.workspace_id, project_id=P.id, name="L")`. **pmem(P, U)** = `ProjectMember(workspace_id=P.workspace_id, project_id=P.id, user_id=U.id, assigned_by=U1.id)`.
  - **ticket("N")** = `HelpTicket(workspace_id=W1.id, ticket_number="N", title="Printer jam", description="It jams", created_by=U1.id)`.
  - **deleted** (machine, work order) = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`; (project) = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. PR-1 reads only `is_deleted` (Facts).
- **att("pid")** = `Attachment(workspace_id=W1.id, file_name="photo.jpg", mime_type="image/jpeg", file_size=1000, uploaded_by=U1.id, upload_status="pending", public_id="pid", resource_type="image", delivery_type="authenticated", note="Front")`. **ready** = `upload_status "ready"`, `format "jpg"`, `version 1700000000`. **pdf** = `file_name "plan.pdf"`, `mime_type "application/pdf"`, `format "pdf"`. **gone** = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
- **link(A, "type", P)** = `AttachmentLink(workspace_id=A.workspace_id, attachment_id=A.id, entity_type="type", entity_id=P.id, linked_by=U1.id)`; `P` may be a number (`entity_id` = it).
- **REQ("type", id)** = `AttachmentSignRequest(entity_type="type", entity_id=id, file_name="plan.pdf", mime_type="application/pdf", file_size=1000, note="Site plan")`. **NORM(r)** = `AM.normalize_upload_request(r)`. **ET("type")** = `REQ("type", 1).entity_type` (the enum member).
- **fill(P, n, "status")** = n attachments `att(f"fill-{i}")` but `upload_status "status"`, each with link(·, P's type, P), built in one loop. `i` numbers on across every `fill` call of one test (a second call starts after the last number of the first), so `public_id`s never repeat.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column equals its snapshot taken after the last Given line.
- **ledger_of(A)** / **links_of(A)** = `db.expire_all()`, then rows of `attachment_ledger` / `attachment_links` with `attachment_id == A.id`, ordered by `id`.
- **events_of(P)** = `db.expire_all()`, then rows of P's activity table whose parent column equals `P.id`, ordered by `id`: `purchase_order_events.purchase_order_id`, `sales_order_events.sales_order_id`, `expense_order_events.expense_order_id`, `transfer_order_events.transfer_order_id`, `work_order_events.work_order_id`, `project_events.project_id`, `project_component_activity_events.project_component_id`, `machine_activity_events.machine_id`, `invoice_events.invoice_id`; attributes `event_type`, `description`, `performed_by`, `metadata_json`.
- **nothing written** = row counts of `attachments`, `attachment_links`, `attachment_ledger` and the nine activity tables (all workspaces) equal their values before the call.
- `session:` lines check `db` right after the call, before any re-read. **clean** = `not db.new`, `not db.dirty`, `not db.deleted`.
- `raises: T` = `with pytest.raises(T) as exc:` around the call; further `raises:` lines on `exc.value` (`str(exc.value)` is the message). `IntegrityError` on flush: `with pytest.raises(IntegrityError):` then `with db.begin_nested():` then the call.
- **warnings** = records of logger `"app.managers.attachment_manager"` at WARNING (`caplog.set_level(logging.WARNING, logger="app.managers.attachment_manager")` before the When).
- **recorder** = `stmts` filled by a `before_cursor_execute` listener on `db.connection()` during the When only.
- **Rolled back** (commit spy) = `with patch.object(db, "commit", wraps=db.commit) as cm:` around `sp = db.begin_nested()`, the call, `sp.rollback()`.

**Caller (PR-5).** No method takes a role. The caller is `user` (create), `performed_by` (confirm; `None` → the attachment's `uploaded_by`), `deleted_by` (delete), and the new required keyword `user_id` (PDF page). The manager reads the caller's role from their W1 `workspace_members` row when `status` is `active` (else no role) and `profiles.is_platform_admin` itself. **pg(U, **kw)** = `AM.get_pdf_page_image(db, **kw, user_id=U.id)` when `"user_id" in inspect.signature(AM.get_pdf_page_image).parameters`, else `AM.get_pdf_page_image(db, **kw)`.

**xfail cards.** Strict: `pytest.mark.xfail(strict=True, reason="BUG-NNN")`; "(non-strict)" = `strict=False`. **Link order (BUG-1433):** the link DAO's links-of-an-attachment query has no `ORDER BY`, so a pass card never depends on which link comes first; it checks the set. Only ATCM-LG-08 and ATCM-TR-07 (non-strict) compare the order, and ATCM-LG-09 (strict) is the alarm. Write the call exactly as shown, also with a parameter that does not exist yet (`user_id=` on `get_pdf_page_image`).

**Race simulations.** None (BUG-2094 is integration-only, ATCM-CF-50).

## `AttachmentManager.normalize_upload_request`

### ATCM-NU-01 — a valid request gives exactly the allowlist's result
- **Rules:** normalize_upload_request R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `r = AttachmentSignRequest(entity_type="purchase_order", entity_id=5, file_name="  Site Plan.PDF ", mime_type="application/pdf", file_size=2048)`.

**When**
- `result = AM.normalize_upload_request(r)`

**Then**
1. returns: `result == normalize_upload_request(r)`.
2. returns: `result.file_name == "Site Plan.PDF"`, `result.resource_type == "image"`.

### ATCM-NU-02 — an invalid request raises the allowlist's error unchanged
- **Rules:** normalize_upload_request R1
- **Kind:** error
- **Expect:** pass

**Given**
1. `r = AttachmentSignRequest(entity_type="purchase_order", entity_id=5, file_name="plan.pdf", mime_type="application/pdf", file_size=10485761)`.

**When**
- `AM.normalize_upload_request(r)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == "File too large (10485761 bytes). Maximum is 10485760 bytes."`

## `AttachmentManager.assert_entity_attachment_capacity`

### ATCM-CP-01 — 24 live attachments pass, nothing written
- **Rules:** assert_entity_attachment_capacity R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. fill(PO1, 12, "pending").
3. fill(PO1, 12, "ready").

**When**
- `result = AM.assert_entity_attachment_capacity(db, workspace_id=W1.id, entity_type=ET("purchase_order"), entity_id=PO1.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.

### ATCM-CP-02 — 25 live attachments are refused with the maximum in the message
- **Rules:** assert_entity_attachment_capacity R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. fill(PO1, 13, "pending").
3. fill(PO1, 12, "ready").

**When**
- `AM.assert_entity_attachment_capacity(db, workspace_id=W1.id, entity_type=ET("purchase_order"), entity_id=PO1.id)`

**Then**
1. raises: `AttachmentLimitError`.
2. raises: `str(exc.value) == "This record already has the maximum of 25 attachments."`
3. session: clean.

### ATCM-CP-03 — failed attachments are not counted
- **Rules:** assert_entity_attachment_capacity R1 [BUG-1434]
- **Kind:** bug
- **Expect:** xfail BUG-1434
- **Fails today on:** Then 1 (the call raises AttachmentLimitError: the link DAO count still includes failed attachments, 27 ≥ 25)

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. fill(PO1, 24, "ready").
3. fill(PO1, 3, "failed").

**When**
- `result = AM.assert_entity_attachment_capacity(db, workspace_id=W1.id, entity_type=ET("purchase_order"), entity_id=PO1.id)`

**Then**
1. returns: `result is None`.

### ATCM-CP-04 — deleted attachments are not counted
- **Rules:** assert_entity_attachment_capacity R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. fill(PO1, 24, "ready").
3. A9 = att("gone-1") but ready, gone; link(A9, "purchase_order", PO1).

**When**
- `result = AM.assert_entity_attachment_capacity(db, workspace_id=W1.id, entity_type=ET("purchase_order"), entity_id=PO1.id)`

**Then**
1. returns: `result is None`.

### ATCM-CP-05 — the maximum is read from settings at each call; 0 refuses an empty record
- **Rules:** assert_entity_attachment_capacity R4, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: MAX_ATTACHMENTS_PER_ENTITY 0.
2. PO1 = parent("purchase_order", "PO-1") with no attachments.

**When**
- `AM.assert_entity_attachment_capacity(db, workspace_id=W1.id, entity_type=ET("purchase_order"), entity_id=PO1.id)`

**Then**
1. raises: `AttachmentLimitError`.
2. raises: `str(exc.value) == "This record already has the maximum of 0 attachments."`

### ATCM-CP-06 — a maximum of 3: 2 pass
- **Rules:** assert_entity_attachment_capacity R4, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: MAX_ATTACHMENTS_PER_ENTITY 3.
2. PO1 = parent("purchase_order", "PO-1").
3. fill(PO1, 2, "pending").

**When**
- `result = AM.assert_entity_attachment_capacity(db, workspace_id=W1.id, entity_type=ET("purchase_order"), entity_id=PO1.id)`

**Then**
1. returns: `result is None`.

### ATCM-CP-07 — the same entity_id under another type does not count
- **Rules:** assert_entity_attachment_capacity R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1") but `id XID(1)`.
2. M1 = mach("Lathe") but `id XID(1)`.
3. fill(PO1, 24, "ready").
4. fill(M1, 5, "ready").

**When**
- `result = AM.assert_entity_attachment_capacity(db, workspace_id=W1.id, entity_type=ET("purchase_order"), entity_id=XID(1))`

**Then**
1. returns: `result is None`.

### ATCM-CP-08 — links of W0 and W2 to the same type and id do not count
- **Rules:** assert_entity_attachment_capacity R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. Three attachments att("w0-1"), att("w0-2"), att("w0-3") but `workspace_id W0.id`, each with link(·, "purchase_order", PO1) (link `workspace_id W0.id`).
3. fill(PO1, 24, "ready").
4. Three attachments att("w2-1"), att("w2-2"), att("w2-3") but `workspace_id W2.id`, each with link(·, "purchase_order", PO1) (link `workspace_id W2.id`).

**When**
- `result = AM.assert_entity_attachment_capacity(db, workspace_id=W1.id, entity_type=ET("purchase_order"), entity_id=PO1.id)`

**Then**
1. returns: `result is None`.

## `AttachmentManager.build_public_id` / `_upload_env` / `_is_production`

### ATCM-PI-01 — outside production the id is `<env>/ws-<id>/<token>`
- **Rules:** build_public_id R1; _upload_env R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. fixed uuid.

**When**
- `result = AM.build_public_id(workspace_id=7)`

**Then**
1. returns: `result == "development/ws-7/0123456789abcdef0123456789abcdef"`.

### ATCM-PI-02 — in production there is no environment prefix
- **Rules:** build_public_id R1; _upload_env R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "production".
2. fixed uuid.

**When**
- `result = AM.build_public_id(workspace_id=7)`

**Then**
1. returns: `result == "ws-7/0123456789abcdef0123456789abcdef"`.

### ATCM-PI-03 — an empty upload environment falls back to ENVIRONMENT
- **Rules:** _upload_env R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "".
2. settings: ENVIRONMENT "production".
3. fixed uuid.

**When**
- `result = AM.build_public_id(workspace_id=7)`

**Then**
1. returns: `result == "ws-7/0123456789abcdef0123456789abcdef"`.

### ATCM-PI-04 — a non-empty upload environment wins over ENVIRONMENT
- **Rules:** _upload_env R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "staging".
2. settings: ENVIRONMENT "production".
3. fixed uuid.

**When**
- `result = AM.build_public_id(workspace_id=7)`

**Then**
1. returns: `result == "staging/ws-7/0123456789abcdef0123456789abcdef"`.

### ATCM-PI-05 — "Production" with a capital is not production
- **Rules:** _upload_env R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "Production".
2. fixed uuid.

**When**
- `result = AM.build_public_id(workspace_id=7)`

**Then**
1. returns: `result == "Production/ws-7/0123456789abcdef0123456789abcdef"`.

### ATCM-PI-06 — both settings empty give a leading slash
- **Rules:** build_public_id R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "".
2. settings: ENVIRONMENT "".
3. fixed uuid.

**When**
- `result = AM.build_public_id(workspace_id=7)`

**Then**
1. returns: `result == "/ws-7/0123456789abcdef0123456789abcdef"`.

### ATCM-PI-07 — each call mints a new 32-character lowercase hex token
- **Rules:** build_public_id R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No uuid patch. `first = AM.build_public_id(workspace_id=7)`.

**When**
- `result = AM.build_public_id(workspace_id=7)`

**Then**
1. returns: `re.fullmatch(r"development/ws-7/[0-9a-f]{32}", result) is not None`.
2. returns: `re.fullmatch(r"development/ws-7/[0-9a-f]{32}", first) is not None`.
3. returns: `result != first`.

## `AttachmentManager.build_asset_folder`

### ATCM-AF-01 — production folder is `<workspace>/<type label>/<record label>`
- **Rules:** build_asset_folder R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "production".

**When**
- `result = AM.build_asset_folder(workspace_name="Acme", entity_type=ET("account_invoice"), entity_label="INV-9")`

**Then**
1. returns: `result == "Acme/Invoices/INV-9"`.

### ATCM-AF-02 — any other environment gets "Dev/" whatever its name
- **Rules:** build_asset_folder R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "staging".

**When**
- `result = AM.build_asset_folder(workspace_name="Acme", entity_type=ET("item"), entity_label="SKU1")`

**Then**
1. returns: `result == "Dev/Acme/Items/SKU1"`.

### ATCM-AF-03 — names are used as given: slashes and outer spaces kept
- **Rules:** build_asset_folder R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing settings (development).

**When**
- `result = AM.build_asset_folder(workspace_name=" Acme/East ", entity_type=ET("support_ticket"), entity_label="HT/1 ")`

**Then**
1. returns: `result == "Dev/ Acme/East /Help Tickets/HT/1 "`.

### ATCM-AF-04 — the type-label table holds exactly the twelve labels
- **Rules:** build_asset_folder R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = {getattr(k, "value", k): v for k, v in ENTITY_TYPE_FOLDER_LABELS.items()}`

**Then**
1. returns: `result == {"purchase_order": "Purchase Orders", "sales_order": "Sales Orders", "expense_order": "Expense Orders", "transfer_order": "Transfer Orders", "work_order": "Work Orders", "project": "Projects", "project_component": "Project Components", "item": "Items", "machine": "Machines", "account_invoice": "Invoices", "support_ticket": "Help Tickets", "scratch": "Scratch"}`.

## `AttachmentManager.build_display_name`

### ATCM-DN-01 — slashes become dashes, control characters go, outer space is trimmed
- **Rules:** build_display_name R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = AM.build_display_name("  a/b\\c\x01.pdf ")`

**Then**
1. returns: `result == "a-b-c.pdf"`.

### ATCM-DN-02 — \x00, \x1f and \x7f are removed; \x20 inside and other characters stay
- **Rules:** build_display_name R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = AM.build_display_name("A\x00b\x1fc\x7fd e~.PDF")`

**Then**
1. returns: `result == "Abcd e~.PDF"`.

### ATCM-DN-03 — empty after cleaning becomes "upload"
- **Rules:** build_display_name R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = AM.build_display_name("\x01 ")`

**Then**
1. returns: `result == "upload"`.

### ATCM-DN-04 — "" becomes "upload"; "-" is kept
- **Rules:** build_display_name R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `other = AM.build_display_name("/")`.

**When**
- `result = AM.build_display_name("")`

**Then**
1. returns: `result == "upload"`.
2. returns: `other == "-"`.

### ATCM-DN-05 — 256 characters are cut to 255; 255 stay
- **Rules:** build_display_name R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `kept = AM.build_display_name("b" * 255)`.

**When**
- `result = AM.build_display_name("a" * 256)`

**Then**
1. returns: `result == "a" * 255`.
2. returns: `kept == "b" * 255`.

### ATCM-DN-06 — trimming happens before the cut
- **Rules:** build_display_name R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = AM.build_display_name("   " + "a" * 254 + "z")`

**Then**
1. returns: `result == "a" * 254 + "z"`.

## `AttachmentManager.resolve_entity_label` / `_fetch_entity_row`

### ATCM-RL-01 — scratch gives scratch-<id> and reads nothing
- **Rules:** resolve_entity_label R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. recorder.

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("scratch"), entity_id=5)`

**Then**
1. returns: `result == "scratch-5"`.
2. statement: `stmts == []`.

### ATCM-RL-02 — purchase order label is po_number
- **Rules:** resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = mach("Lathe") but `id XID(1)` (same id in another table).
2. PO1 = parent("purchase_order", "PO-77") but `id XID(1)`.

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("purchase_order"), entity_id=XID(1))`

**Then**
1. returns: `result == "PO-77"`.

### ATCM-RL-03 — sales order label is sales_order_number
- **Rules:** resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-77") but `id XID(2)`.
2. S1 = parent("sales_order", "SO-12") but `id XID(2)`.

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("sales_order"), entity_id=XID(2))`

**Then**
1. returns: `result == "SO-12"`.

### ATCM-RL-04 — expense order label is expense_number
- **Rules:** resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = parent("sales_order", "SO-12") but `id XID(3)`.
2. E1 = parent("expense_order", "EXP-3") but `id XID(3)`.

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("expense_order"), entity_id=XID(3))`

**Then**
1. returns: `result == "EXP-3"`.

### ATCM-RL-05 — transfer order label is transfer_number
- **Rules:** resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = parent("expense_order", "EXP-3") but `id XID(4)`.
2. T1 = parent("transfer_order", "TR-4") but `id XID(4)`.

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("transfer_order"), entity_id=XID(4))`

**Then**
1. returns: `result == "TR-4"`.

### ATCM-RL-06 — work order label is work_order_number
- **Rules:** resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = parent("transfer_order", "TR-4") but `id XID(5)`.
2. WO1 = parent("work_order", "WO-5") but `id XID(5)`.

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("work_order"), entity_id=XID(5))`

**Then**
1. returns: `result == "WO-5"`.

### ATCM-RL-07 — project label is its name
- **Rules:** resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. WO1 = parent("work_order", "WO-5") but `id XID(6)`.
2. P1 = proj("Tower") but `id XID(6)`.

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("project"), entity_id=XID(6))`

**Then**
1. returns: `result == "Tower"`.

### ATCM-RL-08 — project component label is its name
- **Rules:** resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tower") but `id XID(7)`.
2. C1 = comp(P1, "Frame") but `id XID(7)`.

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("project_component"), entity_id=XID(7))`

**Then**
1. returns: `result == "Frame"`.

### ATCM-RL-09 — machine label is its name
- **Rules:** resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P0 = proj("Tower").
2. C0 = comp(P0, "Frame") but `id XID(8)`.
3. M1 = mach("Lathe") but `id XID(8)`.

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("machine"), entity_id=XID(8))`

**Then**
1. returns: `result == "Lathe"`.

### ATCM-RL-10 — item label is its sku
- **Rules:** resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = mach("Lathe") but `id XID(9)`.
2. I1 = item("Bolt", "SKU-9") but `id XID(9)`.

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("item"), entity_id=XID(9))`

**Then**
1. returns: `result == "SKU-9"`.

### ATCM-RL-11 — invoice label is invoice_number
- **Rules:** resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1 = item("Bolt", "SKU-9") but `id XID(10)`.
2. N1 = parent("account_invoice", "INV-10") but `id XID(10)`.

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("account_invoice"), entity_id=XID(10))`

**Then**
1. returns: `result == "INV-10"`.

### ATCM-RL-12 — help ticket label is ticket_number (help ticket DAO)
- **Rules:** resolve_entity_label R3; _fetch_entity_row R1; _extract_entity_label R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = parent("account_invoice", "INV-10") but `id XID(11)`.
2. H1 = ticket("HT-11") but `id XID(11)`.

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("support_ticket"), entity_id=XID(11))`

**Then**
1. returns: `result == "HT-11"`.

### ATCM-RL-13 — an unknown id falls back to <type>-<id>
- **Rules:** resolve_entity_label R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No purchase order with id MISSING.

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("purchase_order"), entity_id=MISSING)`

**Then**
1. returns: `result == "purchase_order-999999999"`.

### ATCM-RL-14 — a W0 or W2 record is not found (both sides of W1)
- **Rules:** resolve_entity_label R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = parent("purchase_order", "PO-ZERO") of W0.
2. P9 = parent("purchase_order", "PO-NINE") of W2.
3. `low = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("purchase_order"), entity_id=P0.id)`.

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("purchase_order"), entity_id=P9.id)`

**Then**
1. returns: `result == f"purchase_order-{P9.id}"`.
2. returns: `low == f"purchase_order-{P0.id}"`.

### ATCM-RL-15 — a soft-deleted machine is still found (raw)
- **Rules:** resolve_entity_label R2, R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MD = mach("Old Lathe") but deleted.

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("machine"), entity_id=MD.id)`

**Then**
1. returns: `result == "Old Lathe"`.

### ATCM-RL-16 — an empty label falls back
- **Rules:** resolve_entity_label R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1 = item("", "").

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("item"), entity_id=I1.id)`

**Then**
1. returns: `result == f"item-{I1.id}"`.

### ATCM-RL-17 — a private project the caller cannot open still gives its label
- **Rules:** resolve_entity_label R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender 7") but private.

**When**
- `result = AM.resolve_entity_label(db, workspace_id=W1.id, entity_type=ET("project"), entity_id=P1.id)`

**Then**
1. returns: `result == "Tender 7"`.

### ATCM-RL-18 — _fetch_entity_row for scratch is None
- **Rules:** _fetch_entity_row R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").

**When**
- `result = AM._fetch_entity_row(db, workspace_id=W1.id, entity_type=ET("scratch"), entity_id=PO1.id)`

**Then**
1. returns: `result is None`.

### ATCM-RL-19 — _fetch_entity_row returns the row itself
- **Rules:** _fetch_entity_row R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. H1 = ticket("HT-1").

**When**
- `result = AM._fetch_entity_row(db, workspace_id=W1.id, entity_type=ET("support_ticket"), entity_id=H1.id)`

**Then**
1. returns: `result is H1`.

## `AttachmentManager._extract_entity_label`

### ATCM-XL-01 — item with an empty sku gives its name
- **Rules:** _extract_entity_label R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `row = SimpleNamespace(sku="", name="Bolt", po_number="PO-7")`.

**When**
- `result = AM._extract_entity_label(ET("item"), row)`

**Then**
1. returns: `result == "Bolt"`.

### ATCM-XL-02 — item with sku None gives its name
- **Rules:** _extract_entity_label R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `row = SimpleNamespace(sku=None, name="Bolt")`.

**When**
- `result = AM._extract_entity_label(ET("item"), row)`

**Then**
1. returns: `result == "Bolt"`.

### ATCM-XL-03 — scratch gives None
- **Rules:** _extract_entity_label R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `row = SimpleNamespace(name="Bolt", sku="S")`.

**When**
- `result = AM._extract_entity_label(ET("scratch"), row)`

**Then**
1. returns: `result is None`.

## `AttachmentManager._attachment_event_metadata`

### ATCM-EM-01 — exactly the four keys with current values
- **Rules:** _attachment_event_metadata R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `a = SimpleNamespace(id=41, file_name="plan.pdf", mime_type="application/pdf", file_size=2048, note="x", public_id="p")`.

**When**
- `result = AM._attachment_event_metadata(a)`

**Then**
1. returns: `result == {"attachment_id": 41, "file_name": "plan.pdf", "mime_type": "application/pdf", "file_size": 2048}`.

## `AttachmentManager._append_attachment_ledger`

### ATCM-LG-01 — an enum type is stored as its value with every column, flushed
- **Rules:** _append_attachment_ledger R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but `file_size 2048`.
2. `from app.models.enums import AttachmentLedgerTransactionTypeEnum`.

**When**
- `result = AM._append_attachment_ledger(db, attachment=A1, workspace_id=W1.id, transaction_type=AttachmentLedgerTransactionTypeEnum.READY, entity_type="machine", entity_id=55, performed_by=U2.id, notes="ok")`

**Then**
1. session: `not db.new` (the row is flushed).
2. count: ledger_of(A1) has exactly 1 row.
3. re-read that row: `workspace_id == W1.id`, `attachment_id == A1.id`, `transaction_type == "ready"`, `entity_type == "machine"`, `entity_id == 55`.
4. re-read that row: `file_name == "photo.jpg"`, `mime_type == "image/jpeg"`, `file_size == 2048`, `notes == "ok"`, `performed_by == U2.id`, `performed_at is not None`.

### ATCM-LG-02 — a string type is stored as given
- **Rules:** _append_attachment_ledger R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = att("dev/a1").

**When**
- `AM._append_attachment_ledger(db, attachment=A1, workspace_id=W1.id, transaction_type="failed", entity_type="item", entity_id=3)`

**Then**
1. count: ledger_of(A1) has exactly 1 row.
2. re-read that row: `transaction_type == "failed"`, `notes is None`, `performed_by is None`.

### ATCM-LG-03 — entity missing: taken from one of the W1 links, as a pair
- **Rules:** _append_attachment_ledger R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = att("dev/a1").
2. link(A1, "machine", 70) but `id XID(2)`.
3. link(A1, "purchase_order", 60) but `id XID(1)`.

**When**
- `AM._append_attachment_ledger(db, attachment=A1, workspace_id=W1.id, transaction_type="pending")`

**Then**
1. count: ledger_of(A1) has exactly 1 row.
2. re-read that row: `(row.entity_type, row.entity_id) in {("purchase_order", 60), ("machine", 70)}`.

### ATCM-LG-04 — only entity_type given: both are replaced from the link
- **Rules:** _append_attachment_ledger R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1").
2. link(A1, "machine", 70).

**When**
- `AM._append_attachment_ledger(db, attachment=A1, workspace_id=W1.id, transaction_type="pending", entity_type="item")`

**Then**
1. re-read the one row of ledger_of(A1): `entity_type == "machine"`, `entity_id == 70`.

### ATCM-LG-05 — only entity_id given: both are replaced from the link
- **Rules:** _append_attachment_ledger R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1").
2. link(A1, "machine", 70).

**When**
- `AM._append_attachment_ledger(db, attachment=A1, workspace_id=W1.id, transaction_type="pending", entity_id=5)`

**Then**
1. re-read the one row of ledger_of(A1): `entity_type == "machine"`, `entity_id == 70`.

### ATCM-LG-06 — links filed under W0 and W2 are not used
- **Rules:** _append_attachment_ledger R3, R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 = att("dev/a1").
2. link(A1, "item", 11) but `workspace_id W0.id`, `id XID(1)`.
3. link(A1, "item", 12) but `workspace_id W2.id`, `id XID(2)`.

**When**
- `AM._append_attachment_ledger(db, attachment=A1, workspace_id=W1.id, transaction_type="deleted")`

**Then**
1. re-read the one row of ledger_of(A1): `entity_type is None`, `entity_id is None`.

### ATCM-LG-07 — no link at all: both NULL
- **Rules:** _append_attachment_ledger R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") with no link.

**When**
- `AM._append_attachment_ledger(db, attachment=A1, workspace_id=W1.id, transaction_type="deleted")`

**Then**
1. re-read the one row of ledger_of(A1): `entity_type is None`, `entity_id is None`, `transaction_type == "deleted"`.

### ATCM-LG-08 — entity missing: the first link is the lowest link id, not the first built
- **Rules:** _append_attachment_ledger R3 [BUG-1433]
- **Kind:** bug
- **Expect:** xfail BUG-1433 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (the link query has no ORDER BY; the machine link, built first, usually comes back first)

**Given**
1. A1 = att("dev/a1").
2. link(A1, "machine", 70) but `id XID(2)`.
3. link(A1, "purchase_order", 60) but `id XID(1)`.

**When**
- `AM._append_attachment_ledger(db, attachment=A1, workspace_id=W1.id, transaction_type="pending")`

**Then**
1. count: ledger_of(A1) has exactly 1 row.
2. re-read that row: `entity_type == "purchase_order"`, `entity_id == 60`.

### ATCM-LG-09 — the links query of an attachment is ordered
- **Rules:** _append_attachment_ledger R3 [BUG-1433]; to_response R1
- **Kind:** bug
- **Expect:** xfail BUG-1433
- **Author:** claude
- **Fails today on:** Then 2 (the SELECT on attachment_links has no ORDER BY)

**Given**
1. A1 = att("dev/a1").
2. link(A1, "machine", 70).
3. recorder.

**When**
- `AM._append_attachment_ledger(db, attachment=A1, workspace_id=W1.id, transaction_type="pending")`

**Then**
1. count: `sel = [s for s in stmts if s.lstrip().upper().startswith("SELECT") and "attachment_links" in s]`; `len(sel) >= 1`.
2. returns: `all("ORDER BY" in s.upper() for s in sel)`.

## `AttachmentManager._log_attachment_entity_events`

### ATCM-EV-01 — "attachment_added" on a purchase order writes "Attached <file>"
- **Rules:** _log_attachment_entity_events R1, R2, R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. A1 = att("dev/a1") but ready; link(A1, "purchase_order", PO1).

**When**
- `AM._log_attachment_entity_events(db, attachment=A1, workspace_id=W1.id, event_type="attachment_added", performed_by=U2.id)`

**Then**
1. event: events_of(PO1) has exactly 1 row.
2. event: `event_type == "attachment_added"`, `description == "Attached photo.jpg"`, `performed_by == U2.id`.
3. event: `metadata_json == {"attachment_id": A1.id, "file_name": "photo.jpg", "mime_type": "image/jpeg", "file_size": 1000}`.

### ATCM-EV-02 — "attachment_removed" writes "Removed <file>"
- **Rules:** _log_attachment_entity_events R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. A1 = att("dev/a1") but ready; link(A1, "purchase_order", PO1).

**When**
- `AM._log_attachment_entity_events(db, attachment=A1, workspace_id=W1.id, event_type="attachment_removed", performed_by=U2.id)`

**Then**
1. event: events_of(PO1) has exactly 1 row.
2. event: `event_type == "attachment_removed"`, `description == "Removed photo.jpg"`.

### ATCM-EV-03 — any other event type also writes "Removed"
- **Rules:** _log_attachment_entity_events R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. A1 = att("dev/a1"); link(A1, "purchase_order", PO1).

**When**
- `AM._log_attachment_entity_events(db, attachment=A1, workspace_id=W1.id, event_type="Attachment_Added", performed_by=U2.id)`

**Then**
1. event: events_of(PO1) has exactly 1 row.
2. event: `description == "Removed photo.jpg"`.

### ATCM-EV-04 — sales order gets one entry
- **Rules:** _log_attachment_entity_events R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = parent("sales_order", "SO-1").
2. A1 = att("dev/a1"); link(A1, "sales_order", S1).

**When**
- `AM._log_attachment_entity_events(db, attachment=A1, workspace_id=W1.id, event_type="attachment_added", performed_by=U2.id)`

**Then**
1. event: events_of(S1) has exactly 1 row.
2. event: `description == "Attached photo.jpg"`, `performed_by == U2.id`.

### ATCM-EV-05 — expense order gets one entry
- **Rules:** _log_attachment_entity_events R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = parent("expense_order", "EXP-1").
2. A1 = att("dev/a1"); link(A1, "expense_order", E1).

**When**
- `AM._log_attachment_entity_events(db, attachment=A1, workspace_id=W1.id, event_type="attachment_added", performed_by=U2.id)`

**Then**
1. event: events_of(E1) has exactly 1 row.
2. event: `description == "Attached photo.jpg"`, `performed_by == U2.id`.

### ATCM-EV-06 — transfer order gets one entry
- **Rules:** _log_attachment_entity_events R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = parent("transfer_order", "TR-1").
2. A1 = att("dev/a1"); link(A1, "transfer_order", T1).

**When**
- `AM._log_attachment_entity_events(db, attachment=A1, workspace_id=W1.id, event_type="attachment_added", performed_by=U2.id)`

**Then**
1. event: events_of(T1) has exactly 1 row.
2. event: `description == "Attached photo.jpg"`, `performed_by == U2.id`.

### ATCM-EV-07 — work order gets one entry
- **Rules:** _log_attachment_entity_events R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. WO1 = parent("work_order", "WO-1").
2. A1 = att("dev/a1"); link(A1, "work_order", WO1).

**When**
- `AM._log_attachment_entity_events(db, attachment=A1, workspace_id=W1.id, event_type="attachment_added", performed_by=U2.id)`

**Then**
1. event: events_of(WO1) has exactly 1 row.
2. event: `description == "Attached photo.jpg"`, `performed_by == U2.id`.

### ATCM-EV-08 — project gets one entry
- **Rules:** _log_attachment_entity_events R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P1 = proj("Tower").
2. A1 = att("dev/a1"); link(A1, "project", P1).

**When**
- `AM._log_attachment_entity_events(db, attachment=A1, workspace_id=W1.id, event_type="attachment_added", performed_by=U2.id)`

**Then**
1. event: events_of(P1) has exactly 1 row.
2. event: `description == "Attached photo.jpg"`, `performed_by == U2.id`.

### ATCM-EV-09 — project component gets one entry on its activity table
- **Rules:** _log_attachment_entity_events R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P1 = proj("Tower").
2. C1 = comp(P1, "Frame").
3. A1 = att("dev/a1"); link(A1, "project_component", C1).

**When**
- `AM._log_attachment_entity_events(db, attachment=A1, workspace_id=W1.id, event_type="attachment_added", performed_by=U2.id)`

**Then**
1. event: events_of(C1) has exactly 1 row.
2. event: `description == "Attached photo.jpg"`, `performed_by == U2.id`.

### ATCM-EV-10 — machine gets one entry
- **Rules:** _log_attachment_entity_events R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("dev/a1"); link(A1, "machine", M1).

**When**
- `AM._log_attachment_entity_events(db, attachment=A1, workspace_id=W1.id, event_type="attachment_added", performed_by=U2.id)`

**Then**
1. event: events_of(M1) has exactly 1 row.
2. event: `description == "Attached photo.jpg"`, `performed_by == U2.id`.

### ATCM-EV-11 — an invoice found in the workspace gets one invoice event
- **Rules:** _log_attachment_entity_events R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. N1 = parent("account_invoice", "INV-1").
2. A1 = att("dev/a1"); link(A1, "account_invoice", N1).

**When**
- `AM._log_attachment_entity_events(db, attachment=A1, workspace_id=W1.id, event_type="attachment_added", performed_by=U2.id)`

**Then**
1. event: events_of(N1) has exactly 1 row.
2. event: `description == "Attached photo.jpg"`, `performed_by == U2.id`.

### ATCM-EV-12 — an invoice not found (W2's id) writes nothing and raises nothing
- **Rules:** _log_attachment_entity_events R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. N9 = parent("account_invoice", "INV-9") of W2.
2. A1 = att("dev/a1"); link(A1, "account_invoice", N9).

**When**
- `result = AM._log_attachment_entity_events(db, attachment=A1, workspace_id=W1.id, event_type="attachment_added", performed_by=U2.id)`

**Then**
1. returns: `result is None`.
2. event: events_of(N9) has exactly 0 rows.

### ATCM-EV-13 — item, ticket and scratch parents get nothing
- **Rules:** _log_attachment_entity_events R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1 = item("Bolt", "SKU-1"). H1 = ticket("HT-1").
2. A1 = att("dev/a1"); link(A1, "item", I1); link(A1, "support_ticket", H1); link(A1, "scratch", 5).

**When**
- `result = AM._log_attachment_entity_events(db, attachment=A1, workspace_id=W1.id, event_type="attachment_added", performed_by=U2.id)`

**Then**
1. returns: `result is None`.
2. nothing written.

### ATCM-EV-14 — one entry per W1 link; W2-filed link ignored
- **Rules:** _log_attachment_entity_events R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1"). M1 = mach("Lathe"). PO2 = parent("purchase_order", "PO-2").
2. A1 = att("dev/a1"); link(A1, "purchase_order", PO1); link(A1, "machine", M1); link(A1, "purchase_order", PO2) but `workspace_id W2.id`.

**When**
- `AM._log_attachment_entity_events(db, attachment=A1, workspace_id=W1.id, event_type="attachment_added", performed_by=U2.id)`

**Then**
1. event: events_of(PO1) has exactly 1 row.
2. event: events_of(M1) has exactly 1 row.
3. event: events_of(PO2) has exactly 0 rows.

### ATCM-EV-15 — no link writes nothing
- **Rules:** _log_attachment_entity_events R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") with no link.

**When**
- `result = AM._log_attachment_entity_events(db, attachment=A1, workspace_id=W1.id, event_type="attachment_added", performed_by=U2.id)`

**Then**
1. returns: `result is None`.
2. nothing written.

## `AttachmentManager.create_pending_attachment`

### ATCM-C-01 — writes one pending attachment with the server's public id
- **Rules:** create_pending_attachment R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. R = `AttachmentSignRequest(entity_type="purchase_order", entity_id=PO1.id, file_name="  Site Plan.pdf", mime_type="application/pdf", file_size=4096, note="  Site plan ")`. N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="development/ws-7/abc", asset_folder="Dev/Acme/Purchase Orders/PO-1")`

**Then**
1. returns: `result.id is not None`, `result.upload_status == "pending"`.
2. re-read result: `workspace_id == W1.id`, `file_name == "Site Plan.pdf"`, `mime_type == "application/pdf"`, `resource_type == "image"`, `file_size == 4096`.
3. re-read result: `uploaded_by == UG.id`, `note == "  Site plan "`, `public_id == "development/ws-7/abc"`, `asset_folder == "Dev/Acme/Purchase Orders/PO-1"`.
4. re-read result: `delivery_type == "authenticated"`, `upload_status == "pending"`, `storage_provider == "cloudinary"`, `file_url is None`, `is_deleted is False`.

### ATCM-C-02 — writes one link to the parent
- **Rules:** create_pending_attachment R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. R = REQ("purchase_order", PO1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.id is not None`.
2. count: links_of(result) has exactly 1 row.
3. re-read that link: `workspace_id == W1.id`, `entity_type == "purchase_order"`, `entity_id == PO1.id`, `linked_by == UG.id`.

### ATCM-C-03 — writes one pending ledger row
- **Rules:** create_pending_attachment R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. R = REQ("machine", M1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.id is not None`.
2. count: ledger_of(result) has exactly 1 row.
3. re-read that row: `transaction_type == "pending"`, `entity_type == "machine"`, `entity_id == M1.id`, `performed_by == UG.id`, `file_name == "plan.pdf"`, `file_size == 1000`.

### ATCM-C-04 — no activity entry and no Cloudinary call
- **Rules:** create_pending_attachment R7; Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. R = REQ("purchase_order", PO1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`.
2. event: events_of(PO1) has exactly 0 rows.
3. mock called: cl_untouched.

### ATCM-C-05 — a note of None is stored as None
- **Rules:** create_pending_attachment R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. R = REQ("purchase_order", PO1.id) but `note=None`. N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.id is not None`.
2. re-read result: `note is None`.

### ATCM-C-06 — a full record is refused before any write
- **Rules:** create_pending_attachment R2; PR-4
- **Kind:** error
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. fill(PO1, 25, "pending").
3. R = REQ("purchase_order", PO1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentLimitError`.
2. raises: `str(exc.value) == "This record already has the maximum of 25 attachments."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-07 — 24 attachments: the 25th is written
- **Rules:** create_pending_attachment R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. fill(PO1, 24, "ready").
3. R = REQ("purchase_order", PO1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`.
2. count: W1 has exactly 25 `attachment_links` rows with `entity_type "purchase_order"`, `entity_id PO1.id`.

### ATCM-C-08 — a reused public id in the same workspace fails at the flush
- **Rules:** create_pending_attachment R6
- **Kind:** error
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. A1 = att("dev/dup").
3. R = REQ("purchase_order", PO1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/dup", asset_folder="Dev/F")`

**Then**
1. raises: `IntegrityError` on flush.
2. count: exactly 1 `attachments` row has `public_id "dev/dup"`.

### ATCM-C-09 — the same public id in W0 and W2 does not block W1
- **Rules:** create_pending_attachment R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. A0 = att("dev/dup") but `workspace_id W0.id`.
3. A9 = att("dev/dup") but `workspace_id W2.id`.
4. R = REQ("purchase_order", PO1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/dup", asset_folder="Dev/F")`

**Then**
1. returns: `result.id is not None`.
2. count: exactly 3 `attachments` rows have `public_id "dev/dup"`.

### ATCM-C-10 — scratch passes with any id
- **Rules:** create_pending_attachment R1a; PR-1 (Q14)
- **Kind:** happy
- **Expect:** pass

**Given**
1. R = REQ("scratch", MISSING). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`.
2. re-read the one row of links_of(result): `entity_type == "scratch"`, `entity_id == 999999999`.

### ATCM-C-11 — a live component of a live project is accepted
- **Rules:** create_pending_attachment R1a; PR-1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tower").
2. C1 = comp(P1, "Frame").
3. R = REQ("project_component", C1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`.
2. count: links_of(result) has exactly 1 row.

### ATCM-C-12 — never commits
- **Rules:** create_pending_attachment Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. R = REQ("purchase_order", PO1.id). N = NORM(R).

**When**
- Rolled back: `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/spy", asset_folder="Dev/F")`

**Then**
1. mock called: `cm.call_count == 0`.
2. count: no `attachments` row has `public_id "dev/spy"`.

### ATCM-C-13 — a 501-character note is refused by the sign schema
- **Rules:** create_pending_attachment R4a [BUG-2102]
- **Kind:** bug
- **Expect:** xfail BUG-2102
- **Fails today on:** Then 1 (no error is raised: the note has no limit)

**Given**
1. Nothing (target `schema`; the manager is not called).

**When**
- `AttachmentSignRequest(entity_type="purchase_order", entity_id=1, file_name="plan.pdf", mime_type="application/pdf", file_size=1000, note="n" * 501)`

**Then**
1. raises: `ValidationError`.

### ATCM-C-14 — a 500-character note is accepted and kept as typed
- **Rules:** create_pending_attachment R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing (target `schema`).

**When**
- `result = AttachmentSignRequest(entity_type="purchase_order", entity_id=1, file_name="plan.pdf", mime_type="application/pdf", file_size=1000, note=" " + "n" * 499)`

**Then**
1. returns: `result.note == " " + "n" * 499`.

### ATCM-C-21 — an unknown purchase order id is refused as not found
- **Rules:** create_pending_attachment R1a [BUG-2090]; PR-1, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2090
- **Fails today on:** Then 1 (no error is raised: the parent is never looked up)

**Given**
1. R = REQ("purchase_order", MISSING). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == "purchase_order 999999999 not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-22 — a soft-deleted machine is refused
- **Rules:** create_pending_attachment R1a [BUG-2090]; PR-1, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2090
- **Fails today on:** Then 1 (no error is raised: the parent is never looked up)

**Given**
1. MD = mach("Old Lathe") but deleted.
2. R = REQ("machine", MD.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"machine {MD.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-23 — a soft-deleted work order is refused
- **Rules:** create_pending_attachment R1a [BUG-2090]; PR-1, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2090
- **Fails today on:** Then 1 (no error is raised: the parent is never looked up)

**Given**
1. WD = parent("work_order", "WO-9") but deleted.
2. R = REQ("work_order", WD.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"work_order {WD.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-24 — a soft-deleted project is refused
- **Rules:** create_pending_attachment R1a [BUG-2090]; PR-1, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2090
- **Fails today on:** Then 1 (no error is raised: the parent is never looked up)

**Given**
1. PD = proj("Old Tower") but deleted.
2. R = REQ("project", PD.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {PD.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-25 — a component of a deleted project is refused
- **Rules:** create_pending_attachment R1a [BUG-2090]; PR-1, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2090
- **Fails today on:** Then 1 (no error is raised: the parent is never looked up)

**Given**
1. PD = proj("Old Tower") but deleted.
2. C1 = comp(PD, "Frame").
3. R = REQ("project_component", C1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project_component {C1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-26 — a W0 purchase order (workspace before W1) is refused
- **Rules:** create_pending_attachment R1a [BUG-2090]; PR-1, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2090
- **Fails today on:** Then 1 (no error is raised: the parent is never looked up)

**Given**
1. P0 = parent("purchase_order", "PO-ZERO") of W0.
2. R = REQ("purchase_order", P0.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"purchase_order {P0.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-27 — a W2 purchase order (workspace after W1) is refused
- **Rules:** create_pending_attachment R1a [BUG-2090]; PR-1, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2090
- **Fails today on:** Then 1 (no error is raised: the parent is never looked up)

**Given**
1. P9 = parent("purchase_order", "PO-NINE") of W2.
2. R = REQ("purchase_order", P9.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"purchase_order {P9.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-28 — a W1 machine holding the asked id does not make a purchase order exist
- **Rules:** create_pending_attachment R1a [BUG-2090]; PR-1, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2090
- **Fails today on:** Then 1 (no error is raised: the parent is never looked up)

**Given**
1. M1 = mach("Lathe") but `id XID(1)`.
2. No purchase order has id XID(1).
3. R = REQ("purchase_order", XID(1)). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"purchase_order {XID(1)} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-29 — a W2 help ticket is refused
- **Rules:** create_pending_attachment R1a [BUG-2090]; PR-1, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2090
- **Fails today on:** Then 1 (no error is raised: the parent is never looked up)

**Given**
1. H9 = ticket("HT-9") but `workspace_id W2.id`.
2. R = REQ("support_ticket", H9.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"support_ticket {H9.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-30 — a W2 machine is refused next to a live W1 machine
- **Rules:** create_pending_attachment R1a [BUG-2090]; PR-1, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2090
- **Fails today on:** Then 1 (no error is raised: the parent is never looked up)

**Given**
1. M1 = mach("Lathe").
2. M9 = mach("Far Press") but `workspace_id W2.id`, `factory_id F9.id`.
3. R = REQ("machine", M9.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"machine {M9.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-31 — an unknown parent is refused as not found before the capacity check
- **Rules:** create_pending_attachment R1a [BUG-2090], R2; PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2090
- **Fails today on:** Then 1 (AttachmentLimitError is raised instead: the parent is never looked up)

**Given**
1. settings: MAX_ATTACHMENTS_PER_ENTITY 0.
2. R = REQ("purchase_order", MISSING). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == "purchase_order 999999999 not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-32 — a plain member is refused a private project
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. P1 = proj("Tender 7") but private.
2. R = REQ("project", P1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {P1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-33 — a plain member is refused a component of a private project
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. P1 = proj("Tender 7") but private.
2. C1 = comp(P1, "Frame").
3. R = REQ("project_component", C1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project_component {C1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-34 — a suspended member with role owner is refused
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "owner", status="suspended").
3. P1 = proj("Tender 7") but private.
4. R = REQ("project", P1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {P1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-35 — owning W0 does not open a private project of W1
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. set_owner(W0, UG).
2. P1 = proj("Tender 7") but private.
3. R = REQ("project", P1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {P1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-36 — owning W2 does not open a private project of W1
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. set_owner(W2, UG).
2. P1 = proj("Tender 7") but private.
3. R = REQ("project", P1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {P1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-37 — privileged only in W0 and W2 does not open it
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. member(UG, "owner", ws=W0).
2. member(UG, "ground-team-manager", ws=W2).
3. P1 = proj("Tender 7") but private.
4. R = REQ("project", P1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {P1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-38 — membership of other private projects (lower and higher id) does not open this one
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. PA = proj("Alpha") but private.
2. P1 = proj("Tender 7") but private.
3. PB = proj("Beta") but private.
4. pmem(PA, UG).
5. pmem(PB, UG).
6. R = REQ("project", P1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {P1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-39 — other users' membership of this project does not open it
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. P1 = proj("Tender 7") but private.
2. pmem(P1, U1) (lower user id than UG).
3. UZ = make_profile(db, name="Zed Ali").
4. pmem(P1, UZ).
5. R = REQ("project", P1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {P1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-40 — having created other projects (lower and higher id) does not open this one
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. PA = proj("Alpha") but `created_by UG.id`.
2. P1 = proj("Tender 7") but private.
3. PB = proj("Beta") but `created_by UG.id`.
4. R = REQ("project", P1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {P1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-41 — a private project with no creator is closed to a plain member
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. P1 = proj("Tender 7") but private, `created_by None`.
2. R = REQ("project", P1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {P1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-42 — the hidden-project refusal comes before the capacity check
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. P1 = proj("Tender 7") but private.
2. fill(P1, 25, "ready").
3. R = REQ("project", P1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {P1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-43 — the W1 owner opens a private project
- **Rules:** create_pending_attachment R1b; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. set_owner(W1, UG).
2. P1 = proj("Tender 7") but private.
3. R = REQ("project", P1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`, `result.uploaded_by == UG.id`.
2. count: links_of(result) has exactly 1 row.

### ATCM-C-44 — an active member with role owner opens it
- **Rules:** create_pending_attachment R1b; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender 7") but private.
2. R = REQ("project", P1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=U2, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`, `result.uploaded_by == U2.id`.
2. count: links_of(result) has exactly 1 row.

### ATCM-C-45 — an active ground-team-manager opens it
- **Rules:** create_pending_attachment R1b; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. UX = make_profile(db, name="Gita Rao").
2. member(UX, "ground-team-manager").
3. P1 = proj("Tender 7") but private.
4. R = REQ("project", P1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`, `result.uploaded_by == UX.id`.
2. count: links_of(result) has exactly 1 row.

### ATCM-C-46 — the creator opens their private project
- **Rules:** create_pending_attachment R1b; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender 7") but private.
2. R = REQ("project", P1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=U1, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`, `result.uploaded_by == U1.id`.
2. count: links_of(result) has exactly 1 row.

### ATCM-C-47 — a project member opens it
- **Rules:** create_pending_attachment R1b; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender 7") but private.
2. pmem(P1, UG).
3. R = REQ("project", P1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`, `result.uploaded_by == UG.id`.
2. count: links_of(result) has exactly 1 row.

### ATCM-C-48 — a project member opens a component of it
- **Rules:** create_pending_attachment R1b; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender 7") but private.
2. pmem(P1, UG).
3. C1 = comp(P1, "Frame").
4. R = REQ("project_component", C1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`, `result.uploaded_by == UG.id`.
2. count: links_of(result) has exactly 1 row.

### ATCM-C-49 — a workspace-visible project is open to a plain member
- **Rules:** create_pending_attachment R1b; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tower").
2. R = REQ("project", P1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`, `result.uploaded_by == UG.id`.
2. count: links_of(result) has exactly 1 row.

### ATCM-C-50 — a plain member is refused another member's ticket
- **Rules:** create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1950
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. H1 = ticket("HT-1").
2. R = REQ("support_ticket", H1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"support_ticket {H1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-51 — creating other tickets (lower and higher id) does not open this one
- **Rules:** create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1950
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. HA = ticket("HT-A") but `created_by UG.id`.
2. H1 = ticket("HT-1").
3. HB = ticket("HT-B") but `created_by UG.id`.
4. R = REQ("support_ticket", H1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"support_ticket {H1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-52 — a ticket with no creator is closed to a plain member
- **Rules:** create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1950
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. H1 = ticket("HT-1") but `created_by None`.
2. R = REQ("support_ticket", H1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"support_ticket {H1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-53 — a membership role "Owner" with a capital is not a view-all role
- **Rules:** create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1950
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "Owner").
3. H1 = ticket("HT-1").
4. R = REQ("support_ticket", H1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"support_ticket {H1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-54 — a membership role "ground-team-manage" (part of the word) is not a view-all role
- **Rules:** create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1950
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "ground-team-manage").
3. H1 = ticket("HT-1").
4. R = REQ("support_ticket", H1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"support_ticket {H1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-55 — the ticket's creator may attach
- **Rules:** create_pending_attachment R1b; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. H1 = ticket("HT-1") but `created_by UG.id`.
2. R = REQ("support_ticket", H1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UG, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`, `result.uploaded_by == UG.id`.
2. count: links_of(result) has exactly 1 row.

### ATCM-C-56 — an active member with role owner may attach to any ticket
- **Rules:** create_pending_attachment R1b; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. H1 = ticket("HT-1").
2. R = REQ("support_ticket", H1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=U2, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`, `result.uploaded_by == U2.id`.
2. count: links_of(result) has exactly 1 row.

### ATCM-C-57 — an active ground-team-manager may attach to any ticket
- **Rules:** create_pending_attachment R1b; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. UX = make_profile(db, name="Gita Rao").
2. member(UX, "ground-team-manager").
3. H1 = ticket("HT-1").
4. R = REQ("support_ticket", H1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`, `result.uploaded_by == UX.id`.
2. count: links_of(result) has exactly 1 row.

### ATCM-C-58 — a platform admin with no membership may attach
- **Rules:** create_pending_attachment R1b; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. H1 = ticket("HT-1").
2. R = REQ("support_ticket", H1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UA, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`, `result.uploaded_by == UA.id`.
2. count: links_of(result) has exactly 1 row.

### ATCM-C-59 — a caller with no membership may attach to a purchase order (no membership check here)
- **Rules:** create_pending_attachment R1b; PR-2 (G3), PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. UX = make_profile(db, name="Nia Shah").
2. PO1 = parent("purchase_order", "PO-1").
3. R = REQ("purchase_order", PO1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`, `result.uploaded_by == UX.id`.
2. count: links_of(result) has exactly 1 row.

### ATCM-C-60 — a caller with no membership who created a private project may attach to it
- **Rules:** create_pending_attachment R1b; PR-2 (G3), PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. UX = make_profile(db, name="Nia Shah").
2. P1 = proj("Tender 7") but private, `created_by UX.id`.
3. R = REQ("project", P1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`, `result.uploaded_by == UX.id`.
2. count: links_of(result) has exactly 1 row.

### ATCM-C-61 — a caller with no membership is still judged on a private project
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. UX = make_profile(db, name="Nia Shah").
2. P1 = proj("Tender 7") but private.
3. R = REQ("project", P1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {P1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-62 — a caller with no membership is still judged on another member's ticket
- **Rules:** create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1950
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. UX = make_profile(db, name="Nia Shah").
2. H1 = ticket("HT-1").
3. R = REQ("support_ticket", H1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"support_ticket {H1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-63 — privileged (owner) only in W0 does not open a private project of W1
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "owner", ws=W0).
3. P1 = proj("Tender 7") but private.
4. R = REQ("project", P1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {P1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-64 — privileged (ground-team-manager) only in W2 does not open a private project of W1
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "ground-team-manager", ws=W2).
3. P1 = proj("Tender 7") but private.
4. R = REQ("project", P1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {P1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-65 — a removed (inactive) owner is refused a private project
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. removed(UX, "owner").
3. P1 = proj("Tender 7") but private.
4. R = REQ("project", P1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {P1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-66 — a suspended ground-team-manager is refused a private project
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "ground-team-manager", status="suspended").
3. P1 = proj("Tender 7") but private.
4. R = REQ("project", P1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {P1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-67 — a suspended owner is refused another member's ticket
- **Rules:** create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1950
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "owner", status="suspended").
3. H1 = ticket("HT-1").
4. R = REQ("support_ticket", H1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"support_ticket {H1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-68 — a removed (inactive) ground-team-manager is refused another member's ticket
- **Rules:** create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1950
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. removed(UX, "ground-team-manager").
3. H1 = ticket("HT-1").
4. R = REQ("support_ticket", H1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"support_ticket {H1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-69 — owner only in W0 does not open a W1 ticket
- **Rules:** create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1950
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "owner", ws=W0).
3. H1 = ticket("HT-1").
4. R = REQ("support_ticket", H1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"support_ticket {H1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-70 — ground-team-manager only in W2 does not open a W1 ticket
- **Rules:** create_pending_attachment R1b [BUG-1950]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1950
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "ground-team-manager", ws=W2).
3. H1 = ticket("HT-1").
4. R = REQ("support_ticket", H1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"support_ticket {H1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-71 — a platform admin with no membership is refused a private project
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. P1 = proj("Tender 7") but private.
2. R = REQ("project", P1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UA, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project {P1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-72 — a platform admin with no membership is refused a component of a private project
- **Rules:** create_pending_attachment R1b [BUG-1870]; PR-2, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: the caller is not checked)

**Given**
1. P1 = proj("Tender 7") but private.
2. C1 = comp(P1, "Frame").
3. R = REQ("project_component", C1.id). N = NORM(R).

**When**
- `AM.create_pending_attachment(db, workspace_id=W1.id, user=UA, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"project_component {C1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-C-73 — the workspace owner with a plain role may attach to another member's ticket (BUG-2103; passes today because nothing is checked)
- **Rules:** create_pending_attachment R1b [BUG-2103]; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. UX = make_profile(db, name="Nia Shah").
2. member(UX, "ground-team").
3. set_owner(W1, UX).
4. H1 = ticket("HT-1") (created by U1).
5. R = REQ("support_ticket", H1.id). N = NORM(R).

**When**
- `result = AM.create_pending_attachment(db, workspace_id=W1.id, user=UX, payload=R, normalized=N, stored_public_id="dev/new-1", asset_folder="Dev/F")`

**Then**
1. returns: `result.upload_status == "pending"`, `result.uploaded_by == UX.id`.
2. count: links_of(result) has exactly 1 row.

## `AttachmentManager.build_sign_response`

### ATCM-SR-01 — returns every field and signs the response's own values
- **Rules:** build_sign_response R3
- **Kind:** external
- **Expect:** pass

**Given**
1. fixed time.
2. A1 = att("dev/a1") but `resource_type "raw"`.

**When**
- `result = AM.build_sign_response(attachment=A1, public_id="dev/a1", asset_folder="Dev/Acme/Items/SKU1", display_name="plan.pdf")`

**Then**
1. returns: `result.attachment_id == A1.id`, `result.cloud_name == "demo-cloud"`, `result.api_key == "123456"`, `result.timestamp == 1767225600`.
2. returns: `result.public_id == "dev/a1"`, `result.asset_folder == "Dev/Acme/Items/SKU1"`, `result.display_name == "plan.pdf"`, `result.type == "authenticated"`.
3. returns: `result.signature == "sig-x"`, `result.resource_type == "raw"`, `result.upload_url == "https://api.cloudinary.com/v1_1/demo-cloud/raw/upload"`.
4. mock called: `gus.call_count == 1`, `gus.call_args.args == ()`, `gus.call_args.kwargs == {"public_id": "dev/a1", "asset_folder": "Dev/Acme/Items/SKU1", "display_name": "plan.pdf", "timestamp": 1767225600, "delivery_type": "authenticated"}`.

### ATCM-SR-02 — an empty resource type gives image
- **Rules:** build_sign_response R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. fixed time.
2. A1 = att("dev/a1") but `resource_type ""`.

**When**
- `result = AM.build_sign_response(attachment=A1, public_id="dev/a1", asset_folder="Dev/F", display_name="plan.pdf")`

**Then**
1. returns: `result.resource_type == "image"`.
2. returns: `result.upload_url == "https://api.cloudinary.com/v1_1/demo-cloud/image/upload"`.

### ATCM-SR-03 — an empty cloud name raises before signing
- **Rules:** build_sign_response R1
- **Kind:** error
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_CLOUD_NAME "".
2. A1 = att("dev/a1").

**When**
- `AM.build_sign_response(attachment=A1, public_id="dev/a1", asset_folder="Dev/F", display_name="plan.pdf")`

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. raises: `str(exc.value) == "Cloudinary cloud name and API key are required."`
3. mock called: `gus.called is False`.

### ATCM-SR-04 — an empty API key raises before signing
- **Rules:** build_sign_response R1
- **Kind:** error
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_API_KEY "".
2. A1 = att("dev/a1").

**When**
- `AM.build_sign_response(attachment=A1, public_id="dev/a1", asset_folder="Dev/F", display_name="plan.pdf")`

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. raises: `str(exc.value) == "Cloudinary cloud name and API key are required."`
3. mock called: `gus.called is False`.

### ATCM-SR-05 — an empty secret raises the client's error from the real signer
- **Rules:** build_sign_response R2
- **Kind:** error
- **Expect:** pass

**Given**
1. real gus.
2. settings: CLOUDINARY_API_SECRET "".
3. A1 = att("dev/a1").

**When**
- `AM.build_sign_response(attachment=A1, public_id="dev/a1", asset_folder="Dev/F", display_name="plan.pdf")`

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. raises: `str(exc.value) != "Cloudinary cloud name and API key are required."` (the client's own message).

### ATCM-SR-06 — writes nothing
- **Rules:** build_sign_response R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = att("dev/a1").

**When**
- `result = AM.build_sign_response(attachment=A1, public_id="dev/a1", asset_folder="Dev/F", display_name="plan.pdf")`

**Then**
1. returns: `result.attachment_id == A1.id`.
2. session: clean.
3. nothing written.

## `AttachmentManager.derive_urls`

### ATCM-DU-01 — a pending attachment has no URLs
- **Rules:** derive_urls R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but `format "jpg"`, `version 1700000000` (status pending).

**When**
- `result = AM.derive_urls(A1)`

**Then**
1. returns: `result.thumb_url is None`, `result.preview_url is None`, `result.download_url is None`.
2. mock called: `bsu.called is False`.

### ATCM-DU-02 — a failed attachment has no URLs
- **Rules:** derive_urls R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but `upload_status "failed"`, `format "jpg"`, `version 1700000000`.

**When**
- `result = AM.derive_urls(A1)`

**Then**
1. returns: `result.thumb_url is None`, `result.preview_url is None`, `result.download_url is None`.

### ATCM-DU-03 — public_id None gives no URLs
- **Rules:** derive_urls R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `public_id None`.

**When**
- `result = AM.derive_urls(A1)`

**Then**
1. returns: `result.thumb_url is None`, `result.preview_url is None`, `result.download_url is None`.

### ATCM-DU-04 — public_id "" gives no URLs
- **Rules:** derive_urls R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `public_id ""`.

**When**
- `result = AM.derive_urls(A1)`

**Then**
1. returns: `result.thumb_url is None`, `result.preview_url is None`, `result.download_url is None`.

### ATCM-DU-05 — version 0 gives no URLs
- **Rules:** derive_urls R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `version 0`.

**When**
- `result = AM.derive_urls(A1)`

**Then**
1. returns: `result.thumb_url is None`, `result.preview_url is None`, `result.download_url is None`.

### ATCM-DU-06 — version None gives no URLs
- **Rules:** derive_urls R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `version None`.

**When**
- `result = AM.derive_urls(A1)`

**Then**
1. returns: `result.thumb_url is None`, `result.preview_url is None`, `result.download_url is None`.

### ATCM-DU-07 — format "" gives no URLs
- **Rules:** derive_urls R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `format ""`.

**When**
- `result = AM.derive_urls(A1)`

**Then**
1. returns: `result.thumb_url is None`, `result.preview_url is None`, `result.download_url is None`.

### ATCM-DU-08 — format None gives no URLs
- **Rules:** derive_urls R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `format None`.

**When**
- `result = AM.derive_urls(A1)`

**Then**
1. returns: `result.thumb_url is None`, `result.preview_url is None`, `result.download_url is None`.

### ATCM-DU-09 — an empty cloud name gives no URLs and raises nothing
- **Rules:** derive_urls R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_CLOUD_NAME "".
2. A1 = att("dev/a1") but ready.

**When**
- `result = AM.derive_urls(A1)`

**Then**
1. returns: `result.thumb_url is None`, `result.preview_url is None`, `result.download_url is None`.
2. mock called: `bsu.called is False`.

### ATCM-DU-10 — an empty secret gives no URLs
- **Rules:** derive_urls R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_API_SECRET "".
2. A1 = att("dev/a1") but ready.

**When**
- `result = AM.derive_urls(A1)`

**Then**
1. returns: `result.thumb_url is None`, `result.preview_url is None`, `result.download_url is None`.

### ATCM-DU-11 — an empty API key gives no URLs instead of raising
- **Rules:** derive_urls R3 [BUG-2101]
- **Kind:** bug
- **Expect:** xfail BUG-2101
- **Fails today on:** Then 1 (the call raises CloudinaryNotConfiguredError from the real URL builder)

**Given**
1. real bsu.
2. settings: CLOUDINARY_API_KEY "".
3. A1 = att("dev/a1") but ready.

**When**
- `result = AM.derive_urls(A1)`

**Then**
1. returns: `result.thumb_url is None`, `result.preview_url is None`, `result.download_url is None`.

### ATCM-DU-12 — a ready image: thumb, preview and download with their arguments
- **Rules:** derive_urls R4, R7, R8
- **Kind:** external
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `format "png"`, `version 1700000001`.

**When**
- `result = AM.derive_urls(A1)`

**Then**
1. returns: `result.thumb_url["public_id"] == "dev/a1"`, `result.thumb_url["resource_type"] == "image"`, `result.thumb_url["delivery_type"] == "authenticated"`, `result.thumb_url["version"] == 1700000001`.
2. returns: `result.thumb_url["fmt"] == "png"`, `result.thumb_url["transformation"] == [{"fetch_format": "auto", "quality": "auto", "width": 400, "crop": "limit"}]`.
3. returns: `result.preview_url["fmt"] == "png"`, `result.preview_url["transformation"] == [{"fetch_format": "auto", "quality": "auto", "width": 1600, "crop": "limit"}]`.
4. returns: `result.download_url["fmt"] == "png"`, `result.download_url.get("flags") == "attachment"`, `result.download_url.get("transformation") is None`.
5. mock called: `bsu.call_count == 3`.

### ATCM-DU-13 — empty resource and delivery types fall back to image / upload
- **Rules:** derive_urls R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `resource_type ""`, `delivery_type ""`.

**When**
- `result = AM.derive_urls(A1)`

**Then**
1. returns: `result.preview_url["resource_type"] == "image"`, `result.preview_url["delivery_type"] == "upload"`.

### ATCM-DU-14 — a raw file has only a download URL
- **Rules:** derive_urls R5
- **Kind:** external
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `file_name "sheet.xlsx"`, `mime_type "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"`, `resource_type "raw"`, `format "xlsx"`.

**When**
- `result = AM.derive_urls(A1)`

**Then**
1. returns: `result.thumb_url is None`, `result.preview_url is None`.
2. returns: `result.download_url["resource_type"] == "raw"`, `result.download_url["fmt"] == "xlsx"`, `result.download_url.get("flags") == "attachment"`.
3. mock called: `bsu.call_count == 1`.

### ATCM-DU-15 — a PDF by MIME type gets a page-1 jpg thumbnail
- **Rules:** derive_urls R6, R8
- **Kind:** external
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `file_name "plan.pdf"`, `mime_type "application/pdf"`, `format "PDF"`.

**When**
- `result = AM.derive_urls(A1)`

**Then**
1. returns: `result.thumb_url["fmt"] == "jpg"`, `result.thumb_url["transformation"] == [{"page": 1, "fetch_format": "jpg", "quality": "auto", "width": 400, "crop": "limit"}]`.
2. returns: `result.preview_url["fmt"] == "PDF"`, `result.download_url["fmt"] == "PDF"`, `result.download_url.get("flags") == "attachment"`.

### ATCM-DU-16 — a PDF by format with another MIME type also gets the page thumbnail
- **Rules:** derive_urls R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `mime_type "image/jpeg"`, `format "pdf"`.

**When**
- `result = AM.derive_urls(A1)`

**Then**
1. returns: `result.thumb_url["fmt"] == "jpg"`, `result.thumb_url["transformation"][0]["page"] == 1`.

## `AttachmentManager.build_pdf_page_image_url`

### ATCM-PU-01 — page 0 is refused first, even on a pending non-PDF
- **Rules:** build_pdf_page_image_url R1
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") (pending, a jpg).

**When**
- `AM.build_pdf_page_image_url(A1, page=0)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == "Page number must be at least 1."`
3. mock called: `bsu.called is False`.

### ATCM-PU-02 — not ready is refused before "not a PDF"
- **Rules:** build_pdf_page_image_url R2
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") (pending, a jpg).

**When**
- `AM.build_pdf_page_image_url(A1, page=1)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Attachment is not ready."`

### ATCM-PU-03 — a ready non-PDF is refused
- **Rules:** build_pdf_page_image_url R3
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `public_id None`.

**When**
- `AM.build_pdf_page_image_url(A1, page=1)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == "Attachment is not a PDF."`

### ATCM-PU-04 — a PDF without public_id is refused
- **Rules:** build_pdf_page_image_url R4
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, pdf, `public_id ""`, `page_count 1`.

**When**
- `AM.build_pdf_page_image_url(A1, page=2)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Attachment is missing Cloudinary metadata."`

### ATCM-PU-05 — a PDF without version is refused
- **Rules:** build_pdf_page_image_url R4
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, pdf, `version None`.

**When**
- `AM.build_pdf_page_image_url(A1, page=1)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Attachment is missing Cloudinary metadata."`

### ATCM-PU-06 — a page past page_count is refused
- **Rules:** build_pdf_page_image_url R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, pdf, `page_count 3`.

**When**
- `AM.build_pdf_page_image_url(A1, page=4)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == "Page 4 is out of range (document has 3 pages)."`

### ATCM-PU-07 — page == page_count passes
- **Rules:** build_pdf_page_image_url R5, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, pdf, `page_count 3`.

**When**
- `result = AM.build_pdf_page_image_url(A1, page=3)`

**Then**
1. returns: `result["transformation"][0]["page"] == 3`.

### ATCM-PU-08 — page_count NULL lets any page pass
- **Rules:** build_pdf_page_image_url R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, pdf, `page_count None`.

**When**
- `result = AM.build_pdf_page_image_url(A1, page=500)`

**Then**
1. returns: `result["transformation"][0]["page"] == 500`.

### ATCM-PU-09 — an empty cloud name raises "not configured"
- **Rules:** build_pdf_page_image_url R6
- **Kind:** error
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_CLOUD_NAME "".
2. A1 = att("dev/a1") but ready, pdf.

**When**
- `AM.build_pdf_page_image_url(A1, page=1)`

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. raises: `str(exc.value) == "Cloudinary is not configured."`
3. mock called: `bsu.called is False`.

### ATCM-PU-10 — an empty secret raises "not configured"
- **Rules:** build_pdf_page_image_url R6
- **Kind:** error
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_API_SECRET "".
2. A1 = att("dev/a1") but ready, pdf.

**When**
- `AM.build_pdf_page_image_url(A1, page=1)`

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. raises: `str(exc.value) == "Cloudinary is not configured."`

### ATCM-PU-11 — an empty API key raises the client's error
- **Rules:** build_pdf_page_image_url R6
- **Kind:** error
- **Expect:** pass

**Given**
1. real bsu.
2. settings: CLOUDINARY_API_KEY "".
3. A1 = att("dev/a1") but ready, pdf.

**When**
- `AM.build_pdf_page_image_url(A1, page=1)`

**Then**
1. raises: `CloudinaryNotConfiguredError`.

### ATCM-PU-12 — default width 1600: full arguments with density 200
- **Rules:** build_pdf_page_image_url R7
- **Kind:** external
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, pdf, `resource_type ""`, `delivery_type ""`.

**When**
- `result = AM.build_pdf_page_image_url(A1, page=2)`

**Then**
1. returns: `result["public_id"] == "dev/a1"`, `result["resource_type"] == "image"`, `result["delivery_type"] == "upload"`, `result["version"] == 1700000000`, `result["fmt"] == "jpg"`.
2. returns: `result["transformation"] == [{"page": 2, "fetch_format": "jpg", "quality": "auto:good", "width": 1600, "crop": "limit", "density": 200}]`.
3. mock called: `bsu.call_count == 1`.

### ATCM-PU-13 — width 1200 has density
- **Rules:** build_pdf_page_image_url R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, pdf.

**When**
- `result = AM.build_pdf_page_image_url(A1, page=1, width=1200)`

**Then**
1. returns: `result["transformation"][0]["density"] == 200`, `result["transformation"][0]["width"] == 1200`.

### ATCM-PU-14 — width 1199 has no density
- **Rules:** build_pdf_page_image_url R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `mime_type "image/jpeg"`, `format "pdf"`.

**When**
- `result = AM.build_pdf_page_image_url(A1, page=1, width=1199)`

**Then**
1. returns: `"density" not in result["transformation"][0]`, `result["transformation"][0]["width"] == 1199`.

### ATCM-PU-15 — a PDF by MIME type alone (format "jpg") is accepted
- **Rules:** build_pdf_page_image_url R3, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `file_name "plan.pdf"`, `mime_type "application/pdf"`, `format "jpg"`, `page_count None`.

**When**
- `result = AM.build_pdf_page_image_url(A1, page=1)`

**Then**
1. returns: `result["public_id"] == "dev/a1"`, `result["fmt"] == "jpg"`.
2. returns: `result["transformation"][0]["page"] == 1`.

## `AttachmentManager.to_response`

### ATCM-TR-01 — copies every field and lists exactly the W1 links
- **Rules:** to_response R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `width 800`, `height 600`, `page_count None`, `file_url "https://res.example/s.jpg"`.
2. link(A1, "machine", 70) but `id XID(2)`.
3. link(A1, "purchase_order", 60) but `id XID(1)`.
4. link(A1, "item", 80) but `workspace_id W2.id`, `id XID(3)`.

**When**
- `result = AM.to_response(db, A1, workspace_id=W1.id)`

**Then**
1. returns: `sorted((l.entity_type.value, l.entity_id) for l in result.links) == [("machine", 70), ("purchase_order", 60)]`.
2. returns: `result.id == A1.id`, `result.file_name == "photo.jpg"`, `result.mime_type == "image/jpeg"`, `result.file_size == 1000`, `result.note == "Front"`, `result.uploaded_by == U1.id`.
3. returns: `result.uploaded_at == A1.uploaded_at`, `result.upload_status` value `"ready"`, `result.public_id == "dev/a1"`, `result.format == "jpg"`, `result.version == 1700000000`.
4. returns: `result.width == 800`, `result.height == 600`, `result.page_count is None`, `result.file_url == "https://res.example/s.jpg"`.
5. returns: `result.urls.preview_url["public_id"] == "dev/a1"`.

### ATCM-TR-02 — workspace_id None reads the attachment's own workspace
- **Rules:** to_response R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A9 = att("dev/a9") but `workspace_id W2.id`.
2. link(A9, "item", 81) but `workspace_id W2.id`.
3. link(A9, "item", 82) (W1-filed).

**When**
- `result = AM.to_response(db, A9, workspace_id=None)`

**Then**
1. returns: `[l.entity_id for l in result.links] == [81]`.

### ATCM-TR-03 — workspace_id 0 reads the attachment's own workspace
- **Rules:** to_response R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A0 = att("dev/a0") but `workspace_id W0.id`.
2. link(A0, "item", 81) but `workspace_id W0.id`.
3. link(A0, "item", 82) (W1-filed).

**When**
- `result = AM.to_response(db, A0, workspace_id=0)`

**Then**
1. returns: `[l.entity_id for l in result.links] == [81]`.

### ATCM-TR-04 — a deleted attachment is mapped like any other
- **Rules:** to_response R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, gone.
2. link(A1, "item", 81).

**When**
- `result = AM.to_response(db, A1, workspace_id=W1.id)`

**Then**
1. returns: `result.id == A1.id`, `[l.entity_id for l in result.links] == [81]`.

### ATCM-TR-05 — an unknown link type raises ValueError
- **Rules:** to_response R4
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = att("dev/a1").
2. link(A1, "Purchase_Order", 81).

**When**
- `AM.to_response(db, A1, workspace_id=W1.id)`

**Then**
1. raises: `ValueError`.

### ATCM-TR-06 — a pending attachment's urls are all None
- **Rules:** to_response R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = att("dev/a1").

**When**
- `result = AM.to_response(db, A1, workspace_id=W1.id)`

**Then**
1. returns: `result.urls.thumb_url is None`, `result.urls.preview_url is None`, `result.urls.download_url is None`, `result.links == []`.

### ATCM-TR-07 — W1 links are listed in link id order, not build order
- **Rules:** to_response R1 [BUG-1433]
- **Kind:** bug
- **Expect:** xfail BUG-1433 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (the link query has no ORDER BY; the machine link, built first, usually comes back first)

**Given**
1. A1 = att("dev/a1") but ready.
2. link(A1, "machine", 70) but `id XID(2)`.
3. link(A1, "purchase_order", 60) but `id XID(1)`.

**When**
- `result = AM.to_response(db, A1, workspace_id=W1.id)`

**Then**
1. returns: `[(l.entity_type.value, l.entity_id) for l in result.links] == [("purchase_order", 60), ("machine", 70)]`.

## `AttachmentManager.get_pdf_page_image`

### ATCM-PG-01 — returns the page URL, the page and the page count; writes nothing
- **Rules:** get_pdf_page_image R3; PR-5 (via pg)
- **Kind:** happy
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. A1 = att("dev/a1") but ready, pdf, `page_count 3`; link(A1, "purchase_order", PO1).

**When**
- `result = pg(UG, attachment_id=A1.id, workspace_id=W1.id, page=2)`

**Then**
1. returns: `result["page"] == 2`, `result["page_count"] == 3`.
2. returns: `result["url"]["public_id"] == "dev/a1"`, `result["url"]["transformation"] == [{"page": 2, "fetch_format": "jpg", "quality": "auto:good", "width": 1600, "crop": "limit", "density": 200}]`.
3. session: clean.
4. nothing written.

### ATCM-PG-02 — the width is passed on
- **Rules:** get_pdf_page_image R3; PR-5 (via pg)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, pdf; link(A1, "scratch", 5).

**When**
- `result = pg(UG, attachment_id=A1.id, workspace_id=W1.id, page=1, width=800)`

**Then**
1. returns: `result["url"]["transformation"][0]["width"] == 800`, `"density" not in result["url"]["transformation"][0]`.

### ATCM-PG-03 — an unknown id is not found
- **Rules:** get_pdf_page_image R1; PR-5 (via pg)
- **Kind:** error
- **Expect:** pass

**Given**
1. No attachment has id MISSING.

**When**
- `pg(UG, attachment_id=MISSING, workspace_id=W1.id, page=1)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == "Attachment 999999999 not found."`
3. mock called: cl_untouched.

### ATCM-PG-04 — a deleted attachment is not found
- **Rules:** get_pdf_page_image R1; PR-5 (via pg)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, pdf, gone.

**When**
- `pg(UG, attachment_id=A1.id, workspace_id=W1.id, page=1)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. mock called: cl_untouched.

### ATCM-PG-05 — a W0 attachment is not found from W1
- **Rules:** get_pdf_page_image R1; PR-5 (via pg)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = att("dev/a0") but ready, pdf, `workspace_id W0.id`.

**When**
- `pg(UG, attachment_id=A0.id, workspace_id=W1.id, page=1)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A0.id} not found."`
3. mock called: cl_untouched.

### ATCM-PG-06 — a W2 attachment is not found from W1
- **Rules:** get_pdf_page_image R1; PR-5 (via pg)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A9 = att("dev/a9") but ready, pdf, `workspace_id W2.id`.

**When**
- `pg(UG, attachment_id=A9.id, workspace_id=W1.id, page=1)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A9.id} not found."`
3. mock called: cl_untouched.

### ATCM-PG-07 — a page error of the URL builder passes through
- **Rules:** get_pdf_page_image R3; PR-5 (via pg)
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, pdf, `page_count 3`; link(A1, "scratch", 5).

**When**
- `pg(UG, attachment_id=A1.id, workspace_id=W1.id, page=4)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == "Page 4 is out of range (document has 3 pages)."`
3. session: clean.

### ATCM-PG-21 — refused: its purchase order does not exist
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. A1 = att("dev/a1") but ready, pdf.
2. link(A1, "purchase_order", MISSING).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-22 — refused: its machine is soft-deleted
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. MD = mach("Old Lathe") but deleted.
2. A1 = att("dev/a1") but ready, pdf.
3. link(A1, "machine", MD).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-23 — refused: its work order is soft-deleted
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. WD = parent("work_order", "WO-9") but deleted.
2. A1 = att("dev/a1") but ready, pdf.
3. link(A1, "work_order", WD).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-24 — refused: its component's project is deleted
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. PD = proj("Old Tower") but deleted.
2. C1 = comp(PD, "Frame").
3. A1 = att("dev/a1") but ready, pdf.
4. link(A1, "project_component", C1).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-25 — refused: its purchase order belongs to W0
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. P0 = parent("purchase_order", "PO-ZERO") of W0.
2. A1 = att("dev/a1") but ready, pdf.
3. link(A1, "purchase_order", P0).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-26 — refused: its purchase order belongs to W2
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. P9 = parent("purchase_order", "PO-NINE") of W2.
2. A1 = att("dev/a1") but ready, pdf.
3. link(A1, "purchase_order", P9).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-27 — refused: only a W1 machine holds its purchase-order id
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. M1 = mach("Lathe") but `id XID(1)`.
2. No purchase order has id XID(1).
3. A1 = att("dev/a1") but ready, pdf.
4. link(A1, "purchase_order", XID(1)).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-28 — refused: one of its two links is a deleted machine
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. MD = mach("Old Lathe") but deleted.
3. A1 = att("dev/a1") but ready, pdf.
4. link(A1, "purchase_order", PO1).
5. link(A1, "machine", MD).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-29 — refused: its private project is hidden from a plain member
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. P1 = proj("Tender 7") but private.
2. A1 = att("dev/a1") but ready, pdf.
3. link(A1, "project", P1).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-30 — refused: its component's private project is hidden
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. P1 = proj("Tender 7") but private.
2. C1 = comp(P1, "Frame").
3. A1 = att("dev/a1") but ready, pdf.
4. link(A1, "project_component", C1).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-31 — refused: a ticket of another member is hidden
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. H1 = ticket("HT-1").
2. A1 = att("dev/a1") but ready, pdf.
3. link(A1, "support_ticket", H1).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-32 — refused: one hidden link among an open one refuses (any link)
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. P1 = proj("Tender 7") but private.
3. A1 = att("dev/a1") but ready, pdf.
4. link(A1, "purchase_order", PO1).
5. link(A1, "project", P1).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-33 — allowed: a project member reaches its private project's attachment
- **Rules:** get_pdf_page_image R2; PR-3, PR-5 (via pg)
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender 7") but private.
2. pmem(P1, UG).
3. A1 = att("dev/a1") but ready, pdf.
4. link(A1, "project", P1).

**When**
- `result = pg(UG, attachment_id=A1.id, workspace_id=W1.id, page=1)`

**Then**
1. returns: `result["page"] == 1`, `result["page_count"] is None`.
2. mock called: `bsu.call_count == 1`.

### ATCM-PG-34 — allowed: a platform admin reaches a ticket's attachment
- **Rules:** get_pdf_page_image R2; PR-3, PR-5 (via pg)
- **Kind:** happy
- **Expect:** pass

**Given**
1. H1 = ticket("HT-1").
2. A1 = att("dev/a1") but ready, pdf.
3. link(A1, "support_ticket", H1).

**When**
- `result = pg(UA, attachment_id=A1.id, workspace_id=W1.id, page=1)`

**Then**
1. returns: `result["page"] == 1`, `result["page_count"] is None`.
2. mock called: `bsu.call_count == 1`.

### ATCM-PG-35 — allowed: a scratch attachment is open to a plain member
- **Rules:** get_pdf_page_image R2; PR-3, PR-5 (via pg)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, pdf.
2. link(A1, "scratch", 5).

**When**
- `result = pg(UG, attachment_id=A1.id, workspace_id=W1.id, page=1)`

**Then**
1. returns: `result["page"] == 1`, `result["page_count"] is None`.
2. mock called: `bsu.call_count == 1`.

### ATCM-PG-36 — allowed: a caller with no membership reaches a purchase order's attachment
- **Rules:** get_pdf_page_image R2; PR-2 (G3), PR-3, PR-5 (via pg)
- **Kind:** happy
- **Expect:** pass

**Given**
1. UX = make_profile(db, name="Nia Shah").
2. PO1 = parent("purchase_order", "PO-1").
3. A1 = att("dev/a1") but ready, pdf.
4. link(A1, "purchase_order", PO1).

**When**
- `result = pg(UX, attachment_id=A1.id, workspace_id=W1.id, page=1)`

**Then**
1. returns: `result["page"] == 1`, `result["page_count"] is None`.
2. mock called: `bsu.call_count == 1`.

### ATCM-PG-37 — refused: a suspended owner is refused a private project
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "owner", status="suspended").
3. P1 = proj("Tender 7") but private.
4. A1 = att("dev/a1") but ready, pdf.
5. link(A1, "project", P1).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UX.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-38 — refused: a removed (inactive) owner is refused a private project
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. removed(UX, "owner").
3. P1 = proj("Tender 7") but private.
4. A1 = att("dev/a1") but ready, pdf.
5. link(A1, "project", P1).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UX.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-39 — refused: privileged (owner) only in W0 does not open a private project of W1
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "owner", ws=W0).
3. P1 = proj("Tender 7") but private.
4. A1 = att("dev/a1") but ready, pdf.
5. link(A1, "project", P1).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UX.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-40 — refused: privileged (ground-team-manager) only in W2 does not open a private project of W1
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "ground-team-manager", ws=W2).
3. P1 = proj("Tender 7") but private.
4. A1 = att("dev/a1") but ready, pdf.
5. link(A1, "project", P1).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UX.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-41 — allowed: a link filed under W2 to a missing purchase order is ignored
- **Rules:** get_pdf_page_image R2; PR-3 (only W1 links count), PR-5 (via pg)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, pdf.
2. link(A1, "scratch", 5).
3. link(A1, "purchase_order", MISSING) but `workspace_id W2.id`.

**When**
- `result = pg(UG, attachment_id=A1.id, workspace_id=W1.id, page=1)`

**Then**
1. returns: `result["page"] == 1`, `result["page_count"] is None`.
2. mock called: `bsu.call_count == 1`.

### ATCM-PG-42 — refused: its only link is filed under W2 (no W1 link)
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3 (no W1 link → 404), PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. A1 = att("dev/a1") but ready, pdf.
2. link(A1, "scratch", 5) but `workspace_id W2.id`.

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-43 — refused: it has no link at all
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3 (no W1 link → 404), PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. A1 = att("dev/a1") but ready, pdf; no link row is built.

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-44 — refused: a platform admin does not open a private project's attachment
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-2, PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. P1 = proj("Tender 7") but private.
2. A1 = att("dev/a1") but ready, pdf.
3. link(A1, "project", P1).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UA.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-45 — refused: a platform admin does not open a private project's component attachment
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-2, PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. P1 = proj("Tender 7") but private.
2. C1 = comp(P1, "Frame").
3. A1 = att("dev/a1") but ready, pdf.
4. link(A1, "project_component", C1).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UA.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-PG-46 — allowed: the workspace owner with a plain role reaches another member's ticket (BUG-2103; passes today because nothing is checked)
- **Rules:** get_pdf_page_image R2 [BUG-2103]; PR-2, PR-3, PR-5 (via pg)
- **Kind:** happy
- **Expect:** pass

**Given**
1. UX = make_profile(db, name="Nia Shah").
2. member(UX, "ground-team").
3. set_owner(W1, UX).
4. H1 = ticket("HT-1") (created by U1).
5. A1 = att("dev/a1") but ready, pdf.
6. link(A1, "support_ticket", H1).

**When**
- `result = pg(UX, attachment_id=A1.id, workspace_id=W1.id, page=1)`

**Then**
1. returns: `result["page"] == 1`, `result["page_count"] is None`.
2. mock called: `bsu.call_count == 1`.

### ATCM-PG-47 — refused before validation: a hidden attachment with page 0 answers not found, not the page error
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4 (G12)
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. P1 = proj("Tender 7") but private.
2. A1 = att("dev/a1") but ready, pdf.
3. link(A1, "project", P1).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=0, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. mock called: cl_untouched.

### ATCM-PG-48 — refused before validation: a hidden pending PDF answers not found, not "not ready"
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-4 (G12)
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id yet)

**Given**
1. H1 = ticket("HT-1") (created by U1).
2. A1 = att("dev/a1") but pdf (status stays pending).
3. link(A1, "support_ticket", H1).

**When**
- `AM.get_pdf_page_image(db, attachment_id=A1.id, workspace_id=W1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. mock called: cl_untouched.

## `AttachmentManager.confirm_attachment`

### ATCM-CF-01 — an unknown id is not found, nothing asked of Cloudinary
- **Rules:** confirm_attachment R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No attachment has id MISSING.

**When**
- `AM.confirm_attachment(db, attachment_id=MISSING, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == "Attachment 999999999 not found."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-CF-02 — a deleted attachment is not found
- **Rules:** confirm_attachment R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but gone.

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-CF-03 — a W0 attachment is not found from W1
- **Rules:** confirm_attachment R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = att("dev/a0") but `workspace_id W0.id`.

**When**
- `AM.confirm_attachment(db, attachment_id=A0.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A0.id} not found."`
3. session: clean.
4. unchanged: unchanged(A0).
5. mock called: cl_untouched.

### ATCM-CF-04 — a W2 attachment is not found from W1
- **Rules:** confirm_attachment R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A9 = att("dev/a9") but `workspace_id W2.id`.

**When**
- `AM.confirm_attachment(db, attachment_id=A9.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A9.id} not found."`
3. session: clean.
4. unchanged: unchanged(A9).
5. mock called: cl_untouched.

### ATCM-CF-05 — an attachment already ready is returned unchanged
- **Rules:** confirm_attachment R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. A1 = att("dev/a1") but ready; link(A1, "purchase_order", PO1).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`.
2. session: clean.
3. unchanged: unchanged(A1).
4. count: ledger_of(A1) has exactly 0 rows.
5. event: events_of(PO1) has exactly 0 rows.
6. mock called: cl_untouched.

### ATCM-CF-06 — no public_id is refused before Cloudinary
- **Rules:** confirm_attachment R3
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but `public_id None`; link(A1, "scratch", 5).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Attachment has no public_id."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATCM-CF-07 — public_id "" is refused the same way
- **Rules:** confirm_attachment R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but `public_id ""`; link(A1, "scratch", 5).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Attachment has no public_id."`
3. session: clean.
4. mock called: `gr.called is False`.

### ATCM-CF-08 — a lookup error marks the upload failed, records it, then raises
- **Rules:** confirm_attachment R4, R9
- **Kind:** error
- **Expect:** pass

**Given**
1. `gr.side_effect = RuntimeError("timeout")`.
2. A1 = att("dev/a1").
3. M1 = mach("Press"). PO1 = parent("purchase_order", "PO-1").
4. link(A1, "machine", M1) but `id XID(2)`. link(A1, "purchase_order", PO1) but `id XID(1)` (built second, lower id).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Cloudinary verification failed: timeout"`.
3. session: `not db.new`, `not db.dirty` (the failed state is flushed).
4. re-read A1: `upload_status == "failed"`, `file_url is None`.
5. count: ledger_of(A1) has exactly 1 row.
6. re-read that row: `transaction_type == "failed"`, `notes == "timeout"`, `performed_by == U2.id`.
7. re-read that row: `(row.entity_type, row.entity_id) in {("purchase_order", PO1.id), ("machine", M1.id)}`.

### ATCM-CF-09 — with no actor, the uploader is recorded
- **Rules:** confirm_attachment Inputs, R4; PR-5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `gr.side_effect = RuntimeError("timeout")`.
2. A1 = att("dev/a1"); link(A1, "scratch", 5).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=None)`

**Then**
1. raises: `AttachmentConfirmError`.
2. re-read the one row of ledger_of(A1): `performed_by == U1.id`.

### ATCM-CF-10 — the lookup asks only about the stored id, with the stored types
- **Rules:** confirm_attachment R4 (OQ-11)
- **Kind:** external
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but `file_name "notes.txt"`, `mime_type "text/plain"`, `resource_type "raw"`, `delivery_type "upload"`; link(A1, "scratch", 5).
2. `gr.return_value = {"resource_type": "raw", "format": "txt", "bytes": 10, "version": 1, "secure_url": "https://res.example/n.txt"}`.

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. mock called: `gr.call_count == 1`, `gr.call_args.args == ()`, `gr.call_args.kwargs == {"public_id": "dev/a1", "resource_type": "raw", "delivery_type": "upload"}`.

### ATCM-CF-11 — empty stored types are asked as image / authenticated
- **Rules:** confirm_attachment R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but `resource_type ""`, `delivery_type ""`; link(A1, "scratch", 5).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. mock called: `gr.call_count == 1`, `gr.call_args.args == ()`, `gr.call_args.kwargs == {"public_id": "dev/a1", "resource_type": "image", "delivery_type": "authenticated"}`.

### ATCM-CF-12 — "not configured" passes through and nothing is written
- **Rules:** confirm_attachment R4a [BUG-2096]
- **Kind:** bug
- **Expect:** xfail BUG-2096
- **Fails today on:** Then 1 (AttachmentConfirmError is raised instead)

**Given**
1. `gr.side_effect = CloudinaryNotConfiguredError("Cloudinary is not configured.")`.
2. A1 = att("dev/a1"); link(A1, "scratch", 5).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. session: clean.
3. unchanged: unchanged(A1).
4. count: ledger_of(A1) has exactly 0 rows.

### ATCM-CF-13 — a format the file name does not allow marks it failed
- **Rules:** confirm_attachment R5, R9
- **Kind:** error
- **Expect:** pass

**Given**
1. `gr.return_value` = RES but `"format": "png"`.
2. A1 = att("dev/a1"); link(A1, "scratch", 5).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Cloudinary format 'png' is not allowed for .jpg (expected one of: jpeg, jpg)."`
3. re-read A1: `upload_status == "failed"`, `format is None`.
4. re-read the one row of ledger_of(A1): `transaction_type == "failed"`, `notes == "Cloudinary format 'png' is not allowed for .jpg (expected one of: jpeg, jpg)."`, `performed_by == U2.id`.

### ATCM-CF-14 — a wrong resource type marks it failed
- **Rules:** confirm_attachment R5
- **Kind:** error
- **Expect:** pass

**Given**
1. `gr.return_value` = RES but `"resource_type": "raw"`.
2. A1 = att("dev/a1"); link(A1, "scratch", 5).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Cloudinary resource_type 'raw' does not match .jpg (expected 'image')."`
3. re-read A1: `upload_status == "failed"`.
4. count: ledger_of(A1) has exactly 1 row.

### ATCM-CF-15 — an extension no longer allowed passes its error and writes nothing
- **Rules:** confirm_attachment R5 (BUG-124)
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but `file_name "tool.exe"`; link(A1, "scratch", 5).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == "Unsupported file extension: .exe"`
3. session: clean.
4. unchanged: unchanged(A1).
5. count: ledger_of(A1) has exactly 0 rows.

### ATCM-CF-16 — success stores Cloudinary's values and marks it ready
- **Rules:** confirm_attachment R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = att("dev/a1"); link(A1, "scratch", 5).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`, `result.upload_status` value `"ready"`.
2. re-read A1: `upload_status == "ready"`, `file_url == "https://res.example/s.jpg"`, `file_size == 1234`, `format == "jpg"`, `version == 1700000000`.
3. re-read A1: `width == 800`, `height == 600`, `page_count is None`, `asset_id == "a" * 32`, `etag == "e" * 32`, `mime_type == "image/jpeg"`.
4. mock called: `dr.called is False`.

### ATCM-CF-17 — without secure_url the plain url is stored
- **Rules:** confirm_attachment R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `gr.return_value` = RES but without the key `"secure_url"`.
2. A1 = att("dev/a1"); link(A1, "scratch", 5).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. re-read A1: `file_url == "http://res.example/u.jpg"`.

### ATCM-CF-18 — bytes 0 keeps the declared size
- **Rules:** confirm_attachment R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `gr.return_value` = RES but `"bytes": 0`.
2. A1 = att("dev/a1"); link(A1, "scratch", 5).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. re-read A1: `file_size == 1000`.

### ATCM-CF-19 — values Cloudinary does not send overwrite with None
- **Rules:** confirm_attachment R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `gr.return_value = {"resource_type": "image", "format": "jpg", "bytes": 1234, "version": 1700000000, "secure_url": "https://res.example/s.jpg"}`.
2. A1 = att("dev/a1") but `width 10`, `height 20`, `page_count 5`, `asset_id "old-asset"`, `etag "old-etag"`; link(A1, "scratch", 5).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. re-read A1: `width is None`, `height is None`, `page_count is None`, `asset_id is None`, `etag is None`.

### ATCM-CF-20 — an image resource of format pdf sets the PDF MIME type and page count
- **Rules:** confirm_attachment R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `gr.return_value` = RES but `"format": "pdf"`, `"pages": 4`.
2. A1 = att("dev/a1") but `file_name "plan.pdf"`, `mime_type "application/octet-stream"`; link(A1, "scratch", 5).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. re-read A1: `mime_type == "application/pdf"`, `page_count == 4`, `format == "pdf"`.

### ATCM-CF-21 — a raw file keeps its MIME type
- **Rules:** confirm_attachment R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `gr.return_value = {"resource_type": "raw", "format": "txt", "bytes": 10, "version": 1, "secure_url": "https://res.example/n.txt"}`.
2. A1 = att("dev/a1") but `file_name "notes.txt"`, `mime_type "text/plain"`, `resource_type "raw"`; link(A1, "scratch", 5).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. re-read A1: `mime_type == "text/plain"`, `format == "txt"`, `file_size == 10`.

### ATCM-CF-22 — exactly 10 485 760 bytes is accepted
- **Rules:** confirm_attachment R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `gr.return_value` = RES but `"bytes": 10485760`.
2. A1 = att("dev/a1"); link(A1, "scratch", 5).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. re-read A1: `file_size == 10485760`.
3. mock called: `dr.called is False`.

### ATCM-CF-23 — 10 485 761 bytes: file deleted, failed, refused
- **Rules:** confirm_attachment R6a [BUG-2092]
- **Kind:** bug
- **Expect:** xfail BUG-2092
- **Fails today on:** Then 1 (no error is raised: the size is not checked)

**Given**
1. `gr.return_value` = RES but `"bytes": 10485761`.
2. A1 = att("dev/a1"); link(A1, "scratch", 5).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "File too large (10485761 bytes). Maximum is 10485760 bytes."`
3. mock called: `dr.call_count == 1`, `dr.call_args.kwargs["public_id"] == "dev/a1"`.
4. re-read A1: `upload_status == "failed"`.
5. re-read the one row of ledger_of(A1): `transaction_type == "failed"`, `notes == "File too large (10485761 bytes). Maximum is 10485760 bytes."`

### ATCM-CF-24 — one ready ledger row with the actor and one of the links
- **Rules:** confirm_attachment R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = mach("Lathe"). PO1 = parent("purchase_order", "PO-1").
2. A1 = att("dev/a1").
3. link(A1, "machine", M1) but `id XID(2)`. link(A1, "purchase_order", PO1) but `id XID(1)`.

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. count: ledger_of(A1) has exactly 1 row.
3. re-read that row: `transaction_type == "ready"`, `performed_by == U2.id`, `file_size == 1234`.
4. re-read that row: `(row.entity_type, row.entity_id) in {("purchase_order", PO1.id), ("machine", M1.id)}`.

### ATCM-CF-25 — from pending, every parent gets "Attached …" by the actor
- **Rules:** confirm_attachment R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1"). M1 = mach("Lathe").
2. A1 = att("dev/a1"); link(A1, "purchase_order", PO1); link(A1, "machine", M1).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. event: events_of(PO1) has exactly 1 row: `event_type == "attachment_added"`, `description == "Attached photo.jpg"`, `performed_by == U2.id`.
3. event: events_of(M1) has exactly 1 row: `description == "Attached photo.jpg"`, `performed_by == U2.id`.

### ATCM-CF-26 — with no actor the events name the uploader
- **Rules:** confirm_attachment Inputs, R7, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. A1 = att("dev/a1"); link(A1, "purchase_order", PO1).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=None)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. event: events_of(PO1) has exactly 1 row with `performed_by == U1.id`.
3. re-read the one row of ledger_of(A1): `performed_by == U1.id`.

### ATCM-CF-27 — a failed upload confirmed again becomes ready with a ready ledger row
- **Rules:** confirm_attachment R6, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. A1 = att("dev/a1") but `upload_status "failed"`; link(A1, "purchase_order", PO1).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. re-read the one row of ledger_of(A1): `transaction_type == "ready"`.

### ATCM-CF-28 — a failed upload confirmed again writes "Attached …"
- **Rules:** confirm_attachment R8 [BUG-2093]
- **Kind:** bug
- **Expect:** xfail BUG-2093
- **Fails today on:** Then 2 (no event is written from failed)

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. A1 = att("dev/a1") but `upload_status "failed"`; link(A1, "purchase_order", PO1).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. event: events_of(PO1) has exactly 1 row: `description == "Attached photo.jpg"`, `performed_by == U2.id`.

### ATCM-CF-29 — a member other than the uploader may confirm
- **Rules:** confirm_attachment R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. A1 = att("dev/a1") (uploaded by U1); link(A1, "purchase_order", PO1).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. re-read the one row of ledger_of(A1): `performed_by == UG.id`.
3. re-read A1: `uploaded_by == U1.id`.

### ATCM-CF-30 — never commits
- **Rules:** confirm_attachment Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = att("dev/a1"); link(A1, "scratch", 5).

**When**
- Rolled back: `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. mock called: `cm.call_count == 0`.
2. re-read A1: `upload_status == "pending"`.

### ATCM-CF-31 — the attachment is read with a row lock
- **Rules:** confirm_attachment R10 [BUG-2094]
- **Kind:** bug
- **Expect:** xfail BUG-2094
- **Fails today on:** Then 2 (the attachment is read without FOR UPDATE)

**Given**
1. A1 = att("dev/a1"); link(A1, "scratch", 5).
2. recorder.

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U2.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. statement: some recorded `SELECT` reading `attachments` contains `"FOR UPDATE"`.

### ATCM-CF-61 — refused: its purchase order does not exist
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the parent is never looked at: no AttachmentNotFoundError is raised)

**Given**
1. A1 = att("dev/a1").
2. link(A1, "purchase_order", MISSING).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-62 — refused: its machine is soft-deleted
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the parent is never looked at: no AttachmentNotFoundError is raised)

**Given**
1. MD = mach("Old Lathe") but deleted.
2. A1 = att("dev/a1").
3. link(A1, "machine", MD).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-63 — refused: its work order is soft-deleted
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the parent is never looked at: no AttachmentNotFoundError is raised)

**Given**
1. WD = parent("work_order", "WO-9") but deleted.
2. A1 = att("dev/a1").
3. link(A1, "work_order", WD).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-64 — refused: its component's project is deleted
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the parent is never looked at: no AttachmentNotFoundError is raised)

**Given**
1. PD = proj("Old Tower") but deleted.
2. C1 = comp(PD, "Frame").
3. A1 = att("dev/a1").
4. link(A1, "project_component", C1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-65 — refused: its purchase order belongs to W0
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the parent is never looked at: no AttachmentNotFoundError is raised)

**Given**
1. P0 = parent("purchase_order", "PO-ZERO") of W0.
2. A1 = att("dev/a1").
3. link(A1, "purchase_order", P0).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-66 — refused: its purchase order belongs to W2
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the parent is never looked at: no AttachmentNotFoundError is raised)

**Given**
1. P9 = parent("purchase_order", "PO-NINE") of W2.
2. A1 = att("dev/a1").
3. link(A1, "purchase_order", P9).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-67 — refused: only a W1 machine holds its purchase-order id
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the parent is never looked at: no AttachmentNotFoundError is raised)

**Given**
1. M1 = mach("Lathe") but `id XID(1)`.
2. No purchase order has id XID(1).
3. A1 = att("dev/a1").
4. link(A1, "purchase_order", XID(1)).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-68 — refused: one of its two links is a deleted machine
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the parent is never looked at: no AttachmentNotFoundError is raised)

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. MD = mach("Old Lathe") but deleted.
3. A1 = att("dev/a1").
4. link(A1, "purchase_order", PO1).
5. link(A1, "machine", MD).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-69 — refused: its private project is hidden from a plain member
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. P1 = proj("Tender 7") but private.
2. A1 = att("dev/a1").
3. link(A1, "project", P1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-70 — refused: its component's private project is hidden
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. P1 = proj("Tender 7") but private.
2. C1 = comp(P1, "Frame").
3. A1 = att("dev/a1").
4. link(A1, "project_component", C1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-71 — refused: a ticket of another member is hidden
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. H1 = ticket("HT-1").
2. A1 = att("dev/a1").
3. link(A1, "support_ticket", H1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-72 — refused: one hidden link among an open one refuses (any link)
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. P1 = proj("Tender 7") but private.
3. A1 = att("dev/a1").
4. link(A1, "purchase_order", PO1).
5. link(A1, "project", P1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-73 — refused: owning W0 does not open its private project
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. set_owner(W0, UG).
2. P1 = proj("Tender 7") but private.
3. A1 = att("dev/a1").
4. link(A1, "project", P1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-74 — refused: privileged only in W2 does not open its private project
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. member(UG, "owner", ws=W2).
2. P1 = proj("Tender 7") but private.
3. A1 = att("dev/a1").
4. link(A1, "project", P1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-75 — refused: membership of other private projects (lower and higher id) does not open it
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. PA = proj("Alpha") but private.
2. P1 = proj("Tender 7") but private.
3. PB = proj("Beta") but private.
4. pmem(PA, UG).
5. pmem(PB, UG).
6. A1 = att("dev/a1").
7. link(A1, "project", P1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-76 — refused: a private project with no creator is hidden from a plain member
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. P1 = proj("Tender 7") but private, `created_by None`.
2. A1 = att("dev/a1").
3. link(A1, "project", P1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-77 — refused: a suspended owner is refused its private project
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "owner", status="suspended").
3. P1 = proj("Tender 7") but private.
4. A1 = att("dev/a1").
5. link(A1, "project", P1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UX.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-78 — refused: creating other tickets (lower and higher id) does not open this one
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. HA = ticket("HT-A") but `created_by UG.id`.
2. H1 = ticket("HT-1").
3. HB = ticket("HT-B") but `created_by UG.id`.
4. A1 = att("dev/a1").
5. link(A1, "support_ticket", H1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-79 — refused: a ticket with no creator is hidden from a plain member
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. H1 = ticket("HT-1") but `created_by None`.
2. A1 = att("dev/a1").
3. link(A1, "support_ticket", H1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-80 — allowed: a project member reaches its private project's attachment
- **Rules:** confirm_attachment R1a; PR-3, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender 7") but private.
2. pmem(P1, UG).
3. A1 = att("dev/a1").
4. link(A1, "project", P1).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. count: ledger_of(A1) has exactly 1 row.

### ATCM-CF-81 — allowed: a platform admin reaches a ticket's attachment
- **Rules:** confirm_attachment R1a; PR-3, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. H1 = ticket("HT-1").
2. A1 = att("dev/a1").
3. link(A1, "support_ticket", H1).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UA.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. count: ledger_of(A1) has exactly 1 row.

### ATCM-CF-82 — allowed: a scratch attachment is open to a plain member
- **Rules:** confirm_attachment R1a; PR-3, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = att("dev/a1").
2. link(A1, "scratch", 5).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. count: ledger_of(A1) has exactly 1 row.

### ATCM-CF-83 — allowed: the creator reaches their private project's attachment
- **Rules:** confirm_attachment R1a; PR-3, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender 7") but private.
2. A1 = att("dev/a1").
3. link(A1, "project", P1).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U1.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. count: ledger_of(A1) has exactly 1 row.

### ATCM-CF-84 — allowed: the W1 owner reaches a private project's attachment
- **Rules:** confirm_attachment R1a; PR-3, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. set_owner(W1, UG).
2. P1 = proj("Tender 7") but private.
3. A1 = att("dev/a1").
4. link(A1, "project", P1).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. count: ledger_of(A1) has exactly 1 row.

### ATCM-CF-85 — allowed: an active ground-team-manager reaches any ticket's attachment
- **Rules:** confirm_attachment R1a; PR-3, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. UX = make_profile(db, name="Gita Rao").
2. member(UX, "ground-team-manager").
3. H1 = ticket("HT-1").
4. A1 = att("dev/a1").
5. link(A1, "support_ticket", H1).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UX.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. count: ledger_of(A1) has exactly 1 row.

### ATCM-CF-86 — allowed: the ticket's creator reaches its attachment
- **Rules:** confirm_attachment R1a; PR-3, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. H1 = ticket("HT-1") but `created_by UG.id`.
2. A1 = att("dev/a1").
3. link(A1, "support_ticket", H1).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. count: ledger_of(A1) has exactly 1 row.

### ATCM-CF-87 — allowed: a caller with no membership reaches a purchase order's attachment
- **Rules:** confirm_attachment R1a; PR-2 (G3), PR-3, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. UX = make_profile(db, name="Nia Shah").
2. PO1 = parent("purchase_order", "PO-1").
3. A1 = att("dev/a1").
4. link(A1, "purchase_order", PO1).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UX.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. count: ledger_of(A1) has exactly 1 row.

### ATCM-CF-88 — allowed: with performed_by None the uploader is the caller: the creator-uploader reaches the private project
- **Rules:** confirm_attachment R1a; Inputs, PR-5 (G7), PR-3
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender 7") but private.
2. A1 = att("dev/a1") (uploaded by U1, the creator).
3. link(A1, "project", P1).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=None)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. count: ledger_of(A1) has exactly 1 row.

### ATCM-CF-89 — refused: with performed_by None the uploader is the caller: a plain uploader is refused the private project
- **Rules:** confirm_attachment R1a [BUG-2091]; Inputs, PR-3, PR-4, PR-5 (G7)
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. P1 = proj("Tender 7") but private.
2. A1 = att("dev/a1") but `uploaded_by UG.id`.
3. link(A1, "project", P1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-90 — allowed: the caller is performed_by, not the uploader: the creator confirms a plain member's upload
- **Rules:** confirm_attachment R1a; Inputs, PR-5 (G7), PR-3
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender 7") but private.
2. A1 = att("dev/a1") but `uploaded_by UG.id`.
3. link(A1, "project", P1).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=U1.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. count: ledger_of(A1) has exactly 1 row.

### ATCM-CF-91 — refused: privileged (owner) only in W0 does not open a private project of W1
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "owner", ws=W0).
3. P1 = proj("Tender 7") but private.
4. A1 = att("dev/a1").
5. link(A1, "project", P1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UX.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-92 — refused: a removed (inactive) owner is refused a private project
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. removed(UX, "owner").
3. P1 = proj("Tender 7") but private.
4. A1 = att("dev/a1").
5. link(A1, "project", P1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UX.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-93 — refused: a suspended ground-team-manager is refused another member's ticket
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "ground-team-manager", status="suspended").
3. H1 = ticket("HT-1").
4. A1 = att("dev/a1").
5. link(A1, "support_ticket", H1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UX.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-94 — refused: a removed (inactive) owner is refused another member's ticket
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. removed(UX, "owner").
3. H1 = ticket("HT-1").
4. A1 = att("dev/a1").
5. link(A1, "support_ticket", H1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UX.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-95 — refused: owner only in W0 does not open a W1 ticket
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "owner", ws=W0).
3. H1 = ticket("HT-1").
4. A1 = att("dev/a1").
5. link(A1, "support_ticket", H1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UX.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-96 — refused: ground-team-manager only in W2 does not open a W1 ticket
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "ground-team-manager", ws=W2).
3. H1 = ticket("HT-1").
4. A1 = att("dev/a1").
5. link(A1, "support_ticket", H1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UX.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-97 — allowed: a link filed under W2 to a missing purchase order is ignored
- **Rules:** confirm_attachment R1a; PR-3 (only W1 links count), PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = att("dev/a1").
2. link(A1, "scratch", 5).
3. link(A1, "purchase_order", MISSING) but `workspace_id W2.id`.

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. count: ledger_of(A1) has exactly 1 row.

### ATCM-CF-98 — refused: its only link is filed under W2 (no W1 link)
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3 (no W1 link → 404), PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. A1 = att("dev/a1").
2. link(A1, "scratch", 5) but `workspace_id W2.id`.

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-99 — refused: it has no link at all
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-3 (no W1 link → 404), PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. A1 = att("dev/a1"); no link row is built.

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-100 — refused: a platform admin does not confirm a private project's attachment
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-2, PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. P1 = proj("Tender 7") but private.
2. A1 = att("dev/a1").
3. link(A1, "project", P1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UA.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-101 — refused: a platform admin does not confirm a private project's component attachment
- **Rules:** confirm_attachment R1a [BUG-2091]; PR-2, PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the parent is never looked at)

**Given**
1. P1 = proj("Tender 7") but private.
2. C1 = comp(P1, "Frame").
3. A1 = att("dev/a1").
4. link(A1, "project_component", C1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UA.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

### ATCM-CF-102 — allowed: the workspace owner with a plain role confirms on another member's ticket (BUG-2103; passes today because nothing is checked)
- **Rules:** confirm_attachment R1a [BUG-2103]; PR-2, PR-3, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. UX = make_profile(db, name="Nia Shah").
2. member(UX, "ground-team").
3. set_owner(W1, UX).
4. H1 = ticket("HT-1") (created by U1).
5. A1 = att("dev/a1").
6. link(A1, "support_ticket", H1).

**When**
- `result = AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UX.id)`

**Then**
1. returns: `result.upload_status` value `"ready"`.
2. count: ledger_of(A1) has exactly 1 row.

### ATCM-CF-103 — refused before the ready return: a private project's ready attachment answers not found and leaks nothing
- **Rules:** confirm_attachment R1a, R2 [BUG-2091]; PR-3, PR-4 (G12)
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: R2 returns the ready attachment, name and public_id included, before any parent check)

**Given**
1. P1 = proj("Tender 7") but private.
2. A1 = att("dev/a1") but ready.
3. link(A1, "project", P1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. raises: `"photo.jpg" not in str(exc.value)`, `"dev/a1" not in str(exc.value)`, `"http" not in str(exc.value)`.
4. session: clean.
5. nothing written.
6. unchanged: unchanged(A1).
7. mock called: cl_untouched.

### ATCM-CF-104 — refused before the ready return: another member's ticket's ready attachment answers not found and leaks nothing
- **Rules:** confirm_attachment R1a, R2 [BUG-2091]; PR-3, PR-4 (G12)
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: R2 returns the ready attachment before any parent check)

**Given**
1. H1 = ticket("HT-1") (created by U1).
2. A1 = att("dev/a1") but ready.
3. link(A1, "support_ticket", H1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. raises: `"photo.jpg" not in str(exc.value)`, `"dev/a1" not in str(exc.value)`, `"http" not in str(exc.value)`.
4. session: clean.
5. nothing written.
6. unchanged: unchanged(A1).
7. mock called: cl_untouched.

### ATCM-CF-105 — refused before validation: a hidden attachment with no public_id answers not found, not "no public_id"
- **Rules:** confirm_attachment R1a, R3 [BUG-2091]; PR-3, PR-4 (G12)
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the error raised is AttachmentConfirmError "Attachment has no public_id.", not AttachmentNotFoundError: the parent is never looked at)

**Given**
1. P1 = proj("Tender 7") but private.
2. A1 = att("dev/a1") but `public_id None`.
3. link(A1, "project", P1).

**When**
- `AM.confirm_attachment(db, attachment_id=A1.id, workspace_id=W1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == f"Attachment {A1.id} not found."`
3. session: clean.
4. nothing written.
5. unchanged: unchanged(A1).
6. mock called: cl_untouched.

## `AttachmentManager.delete_attachment`

### ATCM-D-01 — an unknown id gives None, nothing written, no Cloudinary call
- **Rules:** delete_attachment R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No attachment has id MISSING.

**When**
- `result = AM.delete_attachment(db, attachment_id=MISSING, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. mock called: cl_untouched.

### ATCM-D-02 — a W0 attachment gives None
- **Rules:** delete_attachment R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = att("dev/a0") but ready, `workspace_id W0.id`.

**When**
- `result = AM.delete_attachment(db, attachment_id=A0.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. unchanged: unchanged(A0).
4. mock called: cl_untouched.

### ATCM-D-03 — a W2 attachment gives None
- **Rules:** delete_attachment R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A9 = att("dev/a9") but ready, `workspace_id W2.id`.

**When**
- `result = AM.delete_attachment(db, attachment_id=A9.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. unchanged: unchanged(A9).
4. mock called: cl_untouched.

### ATCM-D-04 — an attachment already deleted answers as missing
- **Rules:** delete_attachment R1 [BUG-2097]
- **Kind:** bug
- **Expect:** xfail BUG-2097
- **Fails today on:** Then 1 (the attachment is deleted again and returned)

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. A1 = att("dev/a1") but ready, gone; link(A1, "purchase_order", PO1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. unchanged: unchanged(A1).
4. count: ledger_of(A1) has exactly 0 rows.
5. event: events_of(PO1) has exactly 0 rows.
6. mock called: cl_untouched.

### ATCM-D-05 — a member soft-deletes a ready attachment; links and markup stay
- **Rules:** delete_attachment R2, R8; Facts (deleted_at clock)
- **Kind:** happy
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`; dao clock.
2. PO1 = parent("purchase_order", "PO-1").
3. A1 = att("dev/a1") but ready (uploaded by U1); link(A1, "purchase_order", PO1).
4. `AttachmentMarkup(workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, payload={"shapes": [1]})`.

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result.id == A1.id`.
2. re-read A1: `is_deleted is True`, `deleted_by == UG.id`.
3. re-read A1: `stored_utc(A1) == NOW`.
4. count: links_of(A1) has exactly 1 row.
5. count: `attachment_markups` has exactly 1 row with `attachment_id == A1.id`.

### ATCM-D-06 — a deleted ledger row with the deleter and one of the links
- **Rules:** delete_attachment R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = mach("Lathe"). PO1 = parent("purchase_order", "PO-1").
2. A1 = att("dev/a1") but ready.
3. link(A1, "machine", M1) but `id XID(2)`. link(A1, "purchase_order", PO1) but `id XID(1)`.

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`.
2. count: ledger_of(A1) has exactly 1 row.
3. re-read that row: `transaction_type == "deleted"`, `performed_by == U2.id`.
4. re-read that row: `(row.entity_type, row.entity_id) in {("purchase_order", PO1.id), ("machine", M1.id)}`.

### ATCM-D-07 — a pending attachment also gets the deleted ledger row
- **Rules:** delete_attachment R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") (pending); link(A1, "scratch", 5).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`.
2. re-read the one row of ledger_of(A1): `transaction_type == "deleted"`, `performed_by == U2.id`.

### ATCM-D-08 — a failed attachment also gets the deleted ledger row
- **Rules:** delete_attachment R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but `upload_status "failed"`; link(A1, "scratch", 5).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`.
2. re-read the one row of ledger_of(A1): `transaction_type == "deleted"`.

### ATCM-D-09 — a ready attachment writes "Removed …" on every parent
- **Rules:** delete_attachment R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. PO1 = parent("purchase_order", "PO-1"). M1 = mach("Lathe").
2. A1 = att("dev/a1") but ready; link(A1, "purchase_order", PO1); link(A1, "machine", M1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`.
2. event: events_of(PO1) has exactly 1 row: `event_type == "attachment_removed"`, `description == "Removed photo.jpg"`, `performed_by == U2.id`.
3. event: events_of(M1) has exactly 1 row: `description == "Removed photo.jpg"`.

### ATCM-D-10 — a pending attachment writes no "Removed …"
- **Rules:** delete_attachment R4 [BUG-2098]
- **Kind:** bug
- **Expect:** xfail BUG-2098
- **Fails today on:** Then 2 (a "Removed" entry is written in every state)

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. A1 = att("dev/a1") (pending); link(A1, "purchase_order", PO1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`.
2. event: events_of(PO1) has exactly 0 rows.

### ATCM-D-11 — a failed attachment writes no "Removed …"
- **Rules:** delete_attachment R4 [BUG-2098]
- **Kind:** bug
- **Expect:** xfail BUG-2098
- **Fails today on:** Then 2 (a "Removed" entry is written in every state)

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. A1 = att("dev/a1") but `upload_status "failed"`; link(A1, "purchase_order", PO1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`.
2. event: events_of(PO1) has exactly 0 rows.

### ATCM-D-12 — a ready file is deleted from Cloudinary by its stored id and types
- **Rules:** delete_attachment R5 (OQ-11)
- **Kind:** external
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `resource_type "raw"`, `delivery_type "upload"`, `file_name "notes.txt"`, `mime_type "text/plain"`, `format "txt"`; link(A1, "scratch", 5).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`.
2. mock called: `dr.call_count == 1`, `dr.call_args.args == ()`, `dr.call_args.kwargs == {"public_id": "dev/a1", "resource_type": "raw", "delivery_type": "upload"}`.

### ATCM-D-13 — empty stored types are deleted as image / authenticated
- **Rules:** delete_attachment R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready, `resource_type ""`, `delivery_type ""`; link(A1, "scratch", 5).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`.
2. mock called: `dr.call_count == 1`, `dr.call_args.args == ()`, `dr.call_args.kwargs == {"public_id": "dev/a1", "resource_type": "image", "delivery_type": "authenticated"}`.

### ATCM-D-14 — a pending file is deleted from Cloudinary too
- **Rules:** delete_attachment R6 [BUG-2099]
- **Kind:** bug
- **Expect:** xfail BUG-2099
- **Fails today on:** Then 2 (Cloudinary is asked only for ready attachments)

**Given**
1. A1 = att("dev/a1") (pending); link(A1, "scratch", 5).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`.
2. mock called: `dr.call_count == 1`, `dr.call_args.kwargs["public_id"] == "dev/a1"`.

### ATCM-D-15 — a failed file is deleted from Cloudinary too
- **Rules:** delete_attachment R6 [BUG-2099]
- **Kind:** bug
- **Expect:** xfail BUG-2099
- **Fails today on:** Then 2 (Cloudinary is asked only for ready attachments)

**Given**
1. A1 = att("dev/a1") but `upload_status "failed"`; link(A1, "scratch", 5).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`.
2. mock called: `dr.call_count == 1`, `dr.call_args.kwargs["public_id"] == "dev/a1"`.

### ATCM-D-16 — no public_id: nothing is asked of Cloudinary
- **Rules:** delete_attachment R5, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but `public_id None`; link(A1, "scratch", 5).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`.
2. mock called: `dr.called is False`.

### ATCM-D-17 — a Cloudinary error is swallowed; the delete still happens
- **Rules:** delete_attachment R7
- **Kind:** external
- **Expect:** pass

**Given**
1. `dr.side_effect = RuntimeError("boom")`.
2. A1 = att("dev/a1") but ready; link(A1, "scratch", 5).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`.
2. re-read A1: `is_deleted is True`.
3. count: ledger_of(A1) has exactly 1 row.

### ATCM-D-18 — "not configured" from Cloudinary is swallowed too
- **Rules:** delete_attachment R7
- **Kind:** external
- **Expect:** pass

**Given**
1. `dr.side_effect = CloudinaryNotConfiguredError("Cloudinary is not configured.")`.
2. A1 = att("dev/a1") but ready; link(A1, "scratch", 5).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`.
2. re-read A1: `is_deleted is True`.

### ATCM-D-19 — a failed Cloudinary delete logs one warning naming the id and the error
- **Rules:** delete_attachment R7 [BUG-2100]
- **Kind:** bug
- **Expect:** xfail BUG-2100
- **Fails today on:** Then 2 (nothing is logged)

**Given**
1. `dr.side_effect = RuntimeError("boom")`.
2. A1 = att("dev/a1") but ready; link(A1, "scratch", 5).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`.
2. count: warnings has exactly 1 record.
3. returns: that record's message contains `"dev/a1"` and contains `"boom"`.

### ATCM-D-20 — a successful delete logs no warning
- **Rules:** delete_attachment R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready; link(A1, "scratch", 5).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. returns: `result.id == A1.id`.
2. count: warnings has exactly 0 records.

### ATCM-D-21 — never commits
- **Rules:** delete_attachment Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready; link(A1, "scratch", 5).

**When**
- Rolled back: `AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=U2.id)`

**Then**
1. mock called: `cm.call_count == 0`.
2. re-read A1: `is_deleted is False`.

### ATCM-D-41 — refused: its purchase order does not exist
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises IntegrityError: the parent is never looked at, and the "Removed" event for a purchase order that does not exist breaks the FK purchase_order_events.purchase_order_id)

**Given**
1. A1 = att("dev/a1") but ready.
2. link(A1, "purchase_order", MISSING).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-42 — refused: its machine is soft-deleted
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. MD = mach("Old Lathe") but deleted.
2. A1 = att("dev/a1") but ready.
3. link(A1, "machine", MD).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-43 — refused: its work order is soft-deleted
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. WD = parent("work_order", "WO-9") but deleted.
2. A1 = att("dev/a1") but ready.
3. link(A1, "work_order", WD).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-44 — refused: its component's project is deleted
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. PD = proj("Old Tower") but deleted.
2. C1 = comp(PD, "Frame").
3. A1 = att("dev/a1") but ready.
4. link(A1, "project_component", C1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-45 — refused: its purchase order belongs to W0
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. P0 = parent("purchase_order", "PO-ZERO") of W0.
2. A1 = att("dev/a1") but ready.
3. link(A1, "purchase_order", P0).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-46 — refused: its purchase order belongs to W2
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. P9 = parent("purchase_order", "PO-NINE") of W2.
2. A1 = att("dev/a1") but ready.
3. link(A1, "purchase_order", P9).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-47 — refused: only a W1 machine holds its purchase-order id
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises IntegrityError: the parent is never looked at, and the "Removed" event for a purchase order that does not exist breaks the FK purchase_order_events.purchase_order_id)

**Given**
1. M1 = mach("Lathe") but `id XID(1)`.
2. No purchase order has id XID(1).
3. A1 = att("dev/a1") but ready.
4. link(A1, "purchase_order", XID(1)).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-48 — refused: one of its two links is a deleted machine
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3, PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. MD = mach("Old Lathe") but deleted.
3. A1 = att("dev/a1") but ready.
4. link(A1, "purchase_order", PO1).
5. link(A1, "machine", MD).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-49 — refused: its private project is hidden from a plain member
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. P1 = proj("Tender 7") but private.
2. A1 = att("dev/a1") but ready.
3. link(A1, "project", P1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-50 — refused: its component's private project is hidden
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. P1 = proj("Tender 7") but private.
2. C1 = comp(P1, "Frame").
3. A1 = att("dev/a1") but ready.
4. link(A1, "project_component", C1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-51 — refused: a ticket of another member is hidden
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. H1 = ticket("HT-1").
2. A1 = att("dev/a1") but ready.
3. link(A1, "support_ticket", H1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-52 — refused: one hidden link among an open one refuses (any link)
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. PO1 = parent("purchase_order", "PO-1").
2. P1 = proj("Tender 7") but private.
3. A1 = att("dev/a1") but ready.
4. link(A1, "purchase_order", PO1).
5. link(A1, "project", P1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-53 — allowed: a project member reaches its private project's attachment
- **Rules:** delete_attachment R1a; PR-3, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender 7") but private.
2. pmem(P1, UG).
3. A1 = att("dev/a1") but ready.
4. link(A1, "project", P1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is A1`.
2. re-read A1: `is_deleted is True`, `deleted_by == UG.id`.

### ATCM-D-54 — allowed: a platform admin reaches a ticket's attachment
- **Rules:** delete_attachment R1a; PR-3, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. H1 = ticket("HT-1").
2. A1 = att("dev/a1") but ready.
3. link(A1, "support_ticket", H1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UA.id)`

**Then**
1. returns: `result is A1`.
2. re-read A1: `is_deleted is True`, `deleted_by == UA.id`.

### ATCM-D-55 — allowed: a scratch attachment is open to a plain member
- **Rules:** delete_attachment R1a; PR-3, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready.
2. link(A1, "scratch", 5).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is A1`.
2. re-read A1: `is_deleted is True`, `deleted_by == UG.id`.

### ATCM-D-56 — allowed: a caller with no membership reaches a purchase order's attachment
- **Rules:** delete_attachment R1a; PR-2 (G3), PR-3, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. UX = make_profile(db, name="Nia Shah").
2. PO1 = parent("purchase_order", "PO-1").
3. A1 = att("dev/a1") but ready.
4. link(A1, "purchase_order", PO1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UX.id)`

**Then**
1. returns: `result is A1`.
2. re-read A1: `is_deleted is True`, `deleted_by == UX.id`.

### ATCM-D-57 — refused: a suspended owner is refused a private project
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "owner", status="suspended").
3. P1 = proj("Tender 7") but private.
4. A1 = att("dev/a1") but ready.
5. link(A1, "project", P1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UX.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-58 — refused: a removed (inactive) owner is refused a private project
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. removed(UX, "owner").
3. P1 = proj("Tender 7") but private.
4. A1 = att("dev/a1") but ready.
5. link(A1, "project", P1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UX.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-59 — refused: privileged (owner) only in W0 does not open a private project of W1
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "owner", ws=W0).
3. P1 = proj("Tender 7") but private.
4. A1 = att("dev/a1") but ready.
5. link(A1, "project", P1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UX.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-60 — refused: privileged (ground-team-manager) only in W2 does not open a private project of W1
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. UX = make_profile(db, name="Sue Park").
2. member(UX, "ground-team-manager", ws=W2).
3. P1 = proj("Tender 7") but private.
4. A1 = att("dev/a1") but ready.
5. link(A1, "project", P1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UX.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-61 — allowed: a link filed under W2 to a missing purchase order is ignored
- **Rules:** delete_attachment R1a; PR-3 (only W1 links count), PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = att("dev/a1") but ready.
2. link(A1, "scratch", 5).
3. link(A1, "purchase_order", MISSING) but `workspace_id W2.id`.

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is A1`.
2. re-read A1: `is_deleted is True`, `deleted_by == UG.id`.

### ATCM-D-62 — refused: its only link is filed under W2 (no W1 link)
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3 (no W1 link → 404), PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. A1 = att("dev/a1") but ready.
2. link(A1, "scratch", 5) but `workspace_id W2.id`.

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-63 — refused: it has no link at all
- **Rules:** delete_attachment R1a [BUG-2091]; PR-3 (no W1 link → 404), PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. A1 = att("dev/a1") but ready; no link row is built.

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UG.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-64 — refused: a platform admin does not delete a private project's attachment
- **Rules:** delete_attachment R1a [BUG-2091]; PR-2, PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. P1 = proj("Tender 7") but private.
2. A1 = att("dev/a1") but ready.
3. link(A1, "project", P1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UA.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-65 — refused: a platform admin does not delete a private project's component attachment
- **Rules:** delete_attachment R1a [BUG-2091]; PR-2, PR-3, PR-4, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the attachment is deleted and returned: the parent is never looked at)

**Given**
1. P1 = proj("Tender 7") but private.
2. C1 = comp(P1, "Frame").
3. A1 = att("dev/a1") but ready.
4. link(A1, "project_component", C1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UA.id)`

**Then**
1. returns: `result is None`.
2. session: clean.
3. nothing written.
4. unchanged: unchanged(A1).
5. mock called: cl_untouched.

### ATCM-D-66 — allowed: the workspace owner with a plain role deletes on another member's ticket (BUG-2103; passes today because nothing is checked)
- **Rules:** delete_attachment R1a [BUG-2103]; PR-2, PR-3, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. UX = make_profile(db, name="Nia Shah").
2. member(UX, "ground-team").
3. set_owner(W1, UX).
4. H1 = ticket("HT-1") (created by U1).
5. A1 = att("dev/a1") but ready.
6. link(A1, "support_ticket", H1).

**When**
- `result = AM.delete_attachment(db, attachment_id=A1.id, workspace_id=W1.id, deleted_by=UX.id)`

**Then**
1. returns: `result is A1`.
2. re-read A1: `is_deleted is True`, `deleted_by == UX.id`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| confirm_attachment R9 / BUG-2095 (HR-13) | `AttachmentService.confirm_upload` | the `failed` state and its ledger row are committed before the error is re-raised |
| confirm_attachment R10 / BUG-2094 (race) | integration tests | two sessions confirm at once: one `ready` ledger row and one "Attached …" per parent; the loser returns the row unchanged (the unit card ATCM-CF-31 only checks FOR UPDATE) |
| Integration-only error mapping | attachment endpoints | sign: validation / limit → 400, not configured → 503, `AttachmentNotFoundError` → 404 (FU-1 e); confirm: not found → 404, confirm error → 400, not configured → 503 |
| BUG-2091 on `GET /attachments/{id}` and lists (FU-1 c) | `AttachmentService.get_attachment`, `list_attachments` | a hidden parent's attachment answers 404 / is left out; `to_response` stays a mapper |
| FU-1 (d) delete order | `AttachmentService.delete_attachment` | the Cloudinary file is deleted only after the commit |

## Spec gaps
None. Revision 1 gaps 1–8 were closed by the spec's Gap log G1–G8, gap 9 by G10; verifier finding 5 (workspace owner and tickets) by G11, findings 2 and 3 (refusal order) by G12.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `normalize_upload_request` | R1 | ATCM-NU-01, ATCM-NU-02 |
| `assert_entity_attachment_capacity` | R1 | ATCM-CP-01, ATCM-CP-02, ATCM-CP-03, ATCM-CP-04 |
| `assert_entity_attachment_capacity` | R2 | ATCM-CP-01, ATCM-CP-06 |
| `assert_entity_attachment_capacity` | R3 | ATCM-CP-02, ATCM-CP-05 |
| `assert_entity_attachment_capacity` | R4 | ATCM-CP-05, ATCM-CP-06 |
| `assert_entity_attachment_capacity` | R5 | ATCM-CP-07, ATCM-CP-08 |
| `assert_entity_attachment_capacity` | BUG-1434 (failed not counted) | ATCM-CP-03 |
| `assert_entity_attachment_capacity` | Errors: AttachmentLimitError | ATCM-CP-02, ATCM-CP-05 |
| `_upload_env` | R1 | ATCM-PI-01, ATCM-PI-03, ATCM-PI-04 |
| `_upload_env` | R2 | ATCM-PI-02, ATCM-PI-03, ATCM-PI-05 |
| `build_public_id` | R1 | ATCM-PI-01, ATCM-PI-02, ATCM-PI-06 |
| `build_public_id` | R2 | ATCM-PI-07 |
| `build_asset_folder` | R1 | ATCM-AF-01, ATCM-AF-02, ATCM-AF-04 |
| `build_asset_folder` | R2 | ATCM-AF-03 |
| `build_display_name` | R1 | ATCM-DN-01, ATCM-DN-02, ATCM-DN-06 |
| `build_display_name` | R2 | ATCM-DN-03, ATCM-DN-04 |
| `build_display_name` | R3 | ATCM-DN-05, ATCM-DN-06 |
| `resolve_entity_label` | R1 | ATCM-RL-01 |
| `resolve_entity_label` | R2 | ATCM-RL-13, ATCM-RL-14, ATCM-RL-15 |
| `resolve_entity_label` | R3 | ATCM-RL-02, ATCM-RL-03, ATCM-RL-04, ATCM-RL-05, ATCM-RL-06, ATCM-RL-07, ATCM-RL-08, ATCM-RL-09, ATCM-RL-10, ATCM-RL-11, ATCM-RL-12, ATCM-RL-16 |
| `resolve_entity_label` | R4 | ATCM-RL-15, ATCM-RL-17 |
| `_fetch_entity_row` | R1 | ATCM-RL-02, ATCM-RL-03, ATCM-RL-04, ATCM-RL-05, ATCM-RL-06, ATCM-RL-07, ATCM-RL-08, ATCM-RL-09, ATCM-RL-10, ATCM-RL-11, ATCM-RL-12, ATCM-RL-19 |
| `_fetch_entity_row` | R2 | ATCM-RL-18 |
| `_extract_entity_label` | R1 | ATCM-RL-02, ATCM-RL-03, ATCM-RL-04, ATCM-RL-05, ATCM-RL-06, ATCM-RL-07, ATCM-RL-08, ATCM-RL-09, ATCM-RL-11, ATCM-RL-12 |
| `_extract_entity_label` | R2 | ATCM-RL-10, ATCM-XL-01, ATCM-XL-02 |
| `_extract_entity_label` | R3 | ATCM-XL-03 |
| `_attachment_event_metadata` | R1 | ATCM-EM-01 |
| `_append_attachment_ledger` | R1 | ATCM-LG-01, ATCM-LG-02 |
| `_append_attachment_ledger` | R2 | ATCM-LG-01 |
| `_append_attachment_ledger` | R3 | ATCM-LG-03, ATCM-LG-04, ATCM-LG-05, ATCM-LG-06, ATCM-LG-08, ATCM-LG-09 |
| `_append_attachment_ledger` | BUG-1433 (link order) | ATCM-LG-08, ATCM-LG-09, ATCM-TR-07 |
| `_append_attachment_ledger` | R4 | ATCM-LG-06, ATCM-LG-07 |
| `_log_attachment_entity_events` | R1 | ATCM-EV-01, ATCM-EV-02, ATCM-EV-03 |
| `_log_attachment_entity_events` | R2 | ATCM-EV-01, ATCM-EV-14, ATCM-EV-15 |
| `_log_attachment_entity_events` | R3 | ATCM-EV-01, ATCM-EV-04, ATCM-EV-05, ATCM-EV-06, ATCM-EV-07, ATCM-EV-08, ATCM-EV-09, ATCM-EV-10 |
| `_log_attachment_entity_events` | R4 | ATCM-EV-11, ATCM-EV-12 |
| `_log_attachment_entity_events` | R5 | ATCM-EV-13 |
| `create_pending_attachment` | R1a | ATCM-C-10, ATCM-C-11, ATCM-C-21, ATCM-C-22, ATCM-C-23, ATCM-C-24, ATCM-C-25, ATCM-C-26, ATCM-C-27, ATCM-C-28, ATCM-C-29, ATCM-C-30, ATCM-C-31 |
| `create_pending_attachment` | R1b | ATCM-C-32, ATCM-C-33, ATCM-C-34, ATCM-C-35, ATCM-C-36, ATCM-C-37, ATCM-C-38, ATCM-C-39, ATCM-C-40, ATCM-C-41, ATCM-C-42, ATCM-C-43, ATCM-C-44, ATCM-C-45, ATCM-C-46, ATCM-C-47, ATCM-C-48, ATCM-C-49, ATCM-C-50, ATCM-C-51, ATCM-C-52, ATCM-C-53, ATCM-C-54, ATCM-C-55, ATCM-C-56, ATCM-C-57, ATCM-C-58, ATCM-C-59, ATCM-C-60, ATCM-C-61, ATCM-C-62, ATCM-C-63, ATCM-C-64, ATCM-C-65, ATCM-C-66, ATCM-C-67, ATCM-C-68, ATCM-C-69, ATCM-C-70, ATCM-C-71, ATCM-C-72, ATCM-C-73 |
| `create_pending_attachment` | R2 | ATCM-C-06, ATCM-C-07, ATCM-C-31 |
| `create_pending_attachment` | R3 | ATCM-C-01, ATCM-C-05 |
| `create_pending_attachment` | R4 | ATCM-C-02 |
| `create_pending_attachment` | R4a | ATCM-C-13, ATCM-C-14 |
| `create_pending_attachment` | R5 | ATCM-C-03 |
| `create_pending_attachment` | R6 | ATCM-C-08, ATCM-C-09 |
| `create_pending_attachment` | R7 | ATCM-C-04 |
| `create_pending_attachment` | Side effects | ATCM-C-12 |
| `create_pending_attachment` | Errors: AttachmentNotFoundError (R1a / R1b) | ATCM-C-21 … ATCM-C-42, ATCM-C-50 … ATCM-C-54 |
| `create_pending_attachment` | Errors: AttachmentLimitError (R2) | ATCM-C-06 |
| `build_sign_response` | R1 | ATCM-SR-03, ATCM-SR-04 |
| `build_sign_response` | R2 | ATCM-SR-05 |
| `build_sign_response` | R3 | ATCM-SR-01, ATCM-SR-02 |
| `build_sign_response` | R4 | ATCM-SR-06 |
| `derive_urls` | R1 | ATCM-DU-01, ATCM-DU-02 |
| `derive_urls` | R2 | ATCM-DU-03, ATCM-DU-04, ATCM-DU-05, ATCM-DU-06, ATCM-DU-07, ATCM-DU-08 |
| `derive_urls` | R3 | ATCM-DU-09, ATCM-DU-10, ATCM-DU-11 |
| `derive_urls` | R4 | ATCM-DU-12, ATCM-DU-13 |
| `derive_urls` | R5 | ATCM-DU-14 |
| `derive_urls` | R6 | ATCM-DU-15, ATCM-DU-16 |
| `derive_urls` | R7 | ATCM-DU-12 |
| `derive_urls` | R8 | ATCM-DU-12, ATCM-DU-15 |
| `build_pdf_page_image_url` | R1 | ATCM-PU-01 |
| `build_pdf_page_image_url` | R2 | ATCM-PU-02 |
| `build_pdf_page_image_url` | R3 | ATCM-PU-03, ATCM-PU-15 |
| `build_pdf_page_image_url` | R4 | ATCM-PU-04, ATCM-PU-05 |
| `build_pdf_page_image_url` | R5 | ATCM-PU-06, ATCM-PU-07, ATCM-PU-08 |
| `build_pdf_page_image_url` | R6 | ATCM-PU-09, ATCM-PU-10, ATCM-PU-11 |
| `build_pdf_page_image_url` | R7 | ATCM-PU-07, ATCM-PU-12, ATCM-PU-13, ATCM-PU-14, ATCM-PU-15 |
| `get_pdf_page_image` | R1 | ATCM-PG-03, ATCM-PG-04, ATCM-PG-05, ATCM-PG-06 |
| `get_pdf_page_image` | R2 | ATCM-PG-21, ATCM-PG-22, ATCM-PG-23, ATCM-PG-24, ATCM-PG-25, ATCM-PG-26, ATCM-PG-27, ATCM-PG-28, ATCM-PG-29, ATCM-PG-30, ATCM-PG-31, ATCM-PG-32, ATCM-PG-33, ATCM-PG-34, ATCM-PG-35, ATCM-PG-36, ATCM-PG-37, ATCM-PG-38, ATCM-PG-39, ATCM-PG-40, ATCM-PG-41, ATCM-PG-42, ATCM-PG-43, ATCM-PG-44, ATCM-PG-45, ATCM-PG-46, ATCM-PG-47, ATCM-PG-48 |
| `get_pdf_page_image` | R3 | ATCM-PG-01, ATCM-PG-02, ATCM-PG-07 |
| `to_response` | R1 | ATCM-TR-01, ATCM-TR-02, ATCM-TR-03, ATCM-TR-07 |
| `to_response` | R2 | ATCM-TR-01, ATCM-TR-06 |
| `to_response` | R3 | ATCM-TR-04 |
| `to_response` | R4 | ATCM-TR-05 |
| `confirm_attachment` | R1 | ATCM-CF-01, ATCM-CF-02, ATCM-CF-03, ATCM-CF-04 |
| `confirm_attachment` | R1a | ATCM-CF-61, ATCM-CF-62, ATCM-CF-63, ATCM-CF-64, ATCM-CF-65, ATCM-CF-66, ATCM-CF-67, ATCM-CF-68, ATCM-CF-69, ATCM-CF-70, ATCM-CF-71, ATCM-CF-72, ATCM-CF-73, ATCM-CF-74, ATCM-CF-75, ATCM-CF-76, ATCM-CF-77, ATCM-CF-78, ATCM-CF-79, ATCM-CF-80, ATCM-CF-81, ATCM-CF-82, ATCM-CF-83, ATCM-CF-84, ATCM-CF-85, ATCM-CF-86, ATCM-CF-87, ATCM-CF-88, ATCM-CF-89, ATCM-CF-90, ATCM-CF-91, ATCM-CF-92, ATCM-CF-93, ATCM-CF-94, ATCM-CF-95, ATCM-CF-96, ATCM-CF-97, ATCM-CF-98, ATCM-CF-99, ATCM-CF-100, ATCM-CF-101, ATCM-CF-102, ATCM-CF-103, ATCM-CF-104, ATCM-CF-105 |
| `confirm_attachment` | R2 | ATCM-CF-05, ATCM-CF-103, ATCM-CF-104 |
| `confirm_attachment` | R3 | ATCM-CF-06, ATCM-CF-07, ATCM-CF-105 |
| `confirm_attachment` | R4 | ATCM-CF-08, ATCM-CF-09, ATCM-CF-10, ATCM-CF-11 |
| `confirm_attachment` | R4a | ATCM-CF-12 |
| `confirm_attachment` | R5 | ATCM-CF-13, ATCM-CF-14, ATCM-CF-15 |
| `confirm_attachment` | R6 | ATCM-CF-16, ATCM-CF-17, ATCM-CF-18, ATCM-CF-19, ATCM-CF-20, ATCM-CF-21, ATCM-CF-27 |
| `confirm_attachment` | R6a | ATCM-CF-22, ATCM-CF-23 |
| `confirm_attachment` | R7 | ATCM-CF-24, ATCM-CF-26, ATCM-CF-27 |
| `confirm_attachment` | R8 | ATCM-CF-25, ATCM-CF-26, ATCM-CF-28 |
| `confirm_attachment` | R9 | ATCM-CF-08, ATCM-CF-13 |
| `confirm_attachment` | R10 | ATCM-CF-31 |
| `confirm_attachment` | R11 | ATCM-CF-29 |
| `confirm_attachment` | Inputs | ATCM-CF-09, ATCM-CF-26, ATCM-CF-88, ATCM-CF-89, ATCM-CF-90 |
| `confirm_attachment` | Side effects | ATCM-CF-30 |
| `confirm_attachment` | Errors: AttachmentNotFoundError | ATCM-CF-01 … ATCM-CF-04, ATCM-CF-61 … ATCM-CF-79 |
| `confirm_attachment` | Errors: Attachment has no public_id. | ATCM-CF-06, ATCM-CF-07 |
| `confirm_attachment` | Errors: Cloudinary verification failed | ATCM-CF-08 |
| `confirm_attachment` | Errors: CloudinaryNotConfiguredError (R4a) | ATCM-CF-12 |
| `confirm_attachment` | Errors: allowlist message (R5) | ATCM-CF-13, ATCM-CF-14 |
| `confirm_attachment` | Errors: File too large (R6a) | ATCM-CF-23 |
| `delete_attachment` | R1 | ATCM-D-01, ATCM-D-02, ATCM-D-03, ATCM-D-04 |
| `delete_attachment` | R1a | ATCM-D-41, ATCM-D-42, ATCM-D-43, ATCM-D-44, ATCM-D-45, ATCM-D-46, ATCM-D-47, ATCM-D-48, ATCM-D-49, ATCM-D-50, ATCM-D-51, ATCM-D-52, ATCM-D-53, ATCM-D-54, ATCM-D-55, ATCM-D-56, ATCM-D-57, ATCM-D-58, ATCM-D-59, ATCM-D-60, ATCM-D-61, ATCM-D-62, ATCM-D-63, ATCM-D-64, ATCM-D-65, ATCM-D-66 |
| `delete_attachment` | R2 | ATCM-D-05 |
| `delete_attachment` | R3 | ATCM-D-06, ATCM-D-07, ATCM-D-08 |
| `delete_attachment` | R4 | ATCM-D-09, ATCM-D-10, ATCM-D-11 |
| `delete_attachment` | R5 | ATCM-D-12, ATCM-D-13, ATCM-D-16 |
| `delete_attachment` | R6 | ATCM-D-14, ATCM-D-15, ATCM-D-16 |
| `delete_attachment` | R7 | ATCM-D-17, ATCM-D-18, ATCM-D-19, ATCM-D-20 |
| `delete_attachment` | R8 | ATCM-D-05 |
| `delete_attachment` | Side effects | ATCM-D-21 |
| Parent-record rule | PR-1 | ATCM-C-10, ATCM-C-11, ATCM-C-21, ATCM-C-22, ATCM-C-23, ATCM-C-24, ATCM-C-25, ATCM-C-26, ATCM-C-27, ATCM-C-28, ATCM-C-29, ATCM-C-30 |
| Parent-record rule | PR-2 | ATCM-C-32, ATCM-C-33, ATCM-C-34, ATCM-C-35, ATCM-C-36, ATCM-C-37, ATCM-C-38, ATCM-C-39, ATCM-C-40, ATCM-C-41, ATCM-C-42, ATCM-C-43, ATCM-C-44, ATCM-C-45, ATCM-C-46, ATCM-C-47, ATCM-C-48, ATCM-C-49, ATCM-C-50, ATCM-C-51, ATCM-C-52, ATCM-C-53, ATCM-C-54, ATCM-C-55, ATCM-C-56, ATCM-C-57, ATCM-C-58, ATCM-C-59, ATCM-C-60, ATCM-C-61, ATCM-C-62, ATCM-C-63, ATCM-C-64, ATCM-C-65, ATCM-C-66, ATCM-C-67, ATCM-C-68, ATCM-C-69, ATCM-C-70, ATCM-PG-36, ATCM-CF-87, ATCM-D-56, ATCM-C-71, ATCM-C-72, ATCM-C-73, ATCM-PG-44, ATCM-PG-45, ATCM-PG-46, ATCM-CF-100, ATCM-CF-101, ATCM-CF-102, ATCM-D-64, ATCM-D-65, ATCM-D-66 |
| Parent-record rule | PR-3 | ATCM-PG-21, ATCM-PG-22, ATCM-PG-23, ATCM-PG-24, ATCM-PG-25, ATCM-PG-26, ATCM-PG-27, ATCM-PG-28, ATCM-PG-29, ATCM-PG-30, ATCM-PG-31, ATCM-PG-32, ATCM-PG-33, ATCM-PG-34, ATCM-PG-35, ATCM-PG-36, ATCM-PG-37, ATCM-PG-38, ATCM-PG-39, ATCM-PG-40, ATCM-PG-41, ATCM-PG-42, ATCM-PG-43, ATCM-CF-61, ATCM-CF-62, ATCM-CF-63, ATCM-CF-64, ATCM-CF-65, ATCM-CF-66, ATCM-CF-67, ATCM-CF-68, ATCM-CF-69, ATCM-CF-70, ATCM-CF-71, ATCM-CF-72, ATCM-CF-73, ATCM-CF-74, ATCM-CF-75, ATCM-CF-76, ATCM-CF-77, ATCM-CF-78, ATCM-CF-79, ATCM-CF-80, ATCM-CF-81, ATCM-CF-82, ATCM-CF-83, ATCM-CF-84, ATCM-CF-85, ATCM-CF-86, ATCM-CF-87, ATCM-CF-88, ATCM-CF-89, ATCM-CF-90, ATCM-CF-91, ATCM-CF-92, ATCM-CF-93, ATCM-CF-94, ATCM-CF-95, ATCM-CF-96, ATCM-CF-97, ATCM-CF-98, ATCM-CF-99, ATCM-D-41, ATCM-D-42, ATCM-D-43, ATCM-D-44, ATCM-D-45, ATCM-D-46, ATCM-D-47, ATCM-D-48, ATCM-D-49, ATCM-D-50, ATCM-D-51, ATCM-D-52, ATCM-D-53, ATCM-D-54, ATCM-D-55, ATCM-D-56, ATCM-D-57, ATCM-D-58, ATCM-D-59, ATCM-D-60, ATCM-D-61, ATCM-D-62, ATCM-D-63 |
| Parent-record rule | PR-4 | ATCM-C-06, ATCM-C-21, ATCM-C-22, ATCM-C-23, ATCM-C-24, ATCM-C-25, ATCM-C-26, ATCM-C-27, ATCM-C-28, ATCM-C-29, ATCM-C-30, ATCM-C-31, ATCM-C-32, ATCM-C-33, ATCM-C-34, ATCM-C-35, ATCM-C-36, ATCM-C-37, ATCM-C-38, ATCM-C-39, ATCM-C-40, ATCM-C-41, ATCM-C-42, ATCM-C-50, ATCM-C-51, ATCM-C-52, ATCM-C-53, ATCM-C-54, ATCM-C-61, ATCM-C-62, ATCM-C-63, ATCM-C-64, ATCM-C-65, ATCM-C-66, ATCM-C-67, ATCM-C-68, ATCM-C-69, ATCM-C-70, ATCM-PG-21, ATCM-PG-22, ATCM-PG-23, ATCM-PG-24, ATCM-PG-25, ATCM-PG-26, ATCM-PG-27, ATCM-PG-28, ATCM-PG-29, ATCM-PG-30, ATCM-PG-31, ATCM-PG-32, ATCM-PG-37, ATCM-PG-38, ATCM-PG-39, ATCM-PG-40, ATCM-PG-42, ATCM-PG-43, ATCM-CF-61, ATCM-CF-62, ATCM-CF-63, ATCM-CF-64, ATCM-CF-65, ATCM-CF-66, ATCM-CF-67, ATCM-CF-68, ATCM-CF-69, ATCM-CF-70, ATCM-CF-71, ATCM-CF-72, ATCM-CF-73, ATCM-CF-74, ATCM-CF-75, ATCM-CF-76, ATCM-CF-77, ATCM-CF-78, ATCM-CF-79, ATCM-CF-89, ATCM-CF-91, ATCM-CF-92, ATCM-CF-93, ATCM-CF-94, ATCM-CF-95, ATCM-CF-96, ATCM-CF-98, ATCM-CF-99, ATCM-D-41, ATCM-D-42, ATCM-D-43, ATCM-D-44, ATCM-D-45, ATCM-D-46, ATCM-D-47, ATCM-D-48, ATCM-D-49, ATCM-D-50, ATCM-D-51, ATCM-D-52, ATCM-D-57, ATCM-D-58, ATCM-D-59, ATCM-D-60, ATCM-D-62, ATCM-D-63, ATCM-PG-47, ATCM-PG-48, ATCM-CF-103, ATCM-CF-104, ATCM-CF-105 |
| Parent-record rule | PR-5 | ATCM-C-32, ATCM-C-33, ATCM-C-34, ATCM-C-35, ATCM-C-36, ATCM-C-37, ATCM-C-38, ATCM-C-39, ATCM-C-40, ATCM-C-41, ATCM-C-42, ATCM-C-43, ATCM-C-44, ATCM-C-45, ATCM-C-46, ATCM-C-47, ATCM-C-48, ATCM-C-49, ATCM-C-50, ATCM-C-51, ATCM-C-52, ATCM-C-53, ATCM-C-54, ATCM-C-55, ATCM-C-56, ATCM-C-57, ATCM-C-58, ATCM-C-59, ATCM-C-60, ATCM-C-61, ATCM-C-62, ATCM-C-63, ATCM-C-64, ATCM-C-65, ATCM-C-66, ATCM-C-67, ATCM-C-68, ATCM-C-69, ATCM-C-70, ATCM-PG-01, ATCM-PG-02, ATCM-PG-03, ATCM-PG-04, ATCM-PG-05, ATCM-PG-06, ATCM-PG-07, ATCM-PG-21, ATCM-PG-22, ATCM-PG-23, ATCM-PG-24, ATCM-PG-25, ATCM-PG-26, ATCM-PG-27, ATCM-PG-28, ATCM-PG-29, ATCM-PG-30, ATCM-PG-31, ATCM-PG-32, ATCM-PG-33, ATCM-PG-34, ATCM-PG-35, ATCM-PG-36, ATCM-PG-37, ATCM-PG-38, ATCM-PG-39, ATCM-PG-40, ATCM-PG-41, ATCM-PG-42, ATCM-PG-43, ATCM-CF-09, ATCM-CF-69, ATCM-CF-70, ATCM-CF-71, ATCM-CF-72, ATCM-CF-73, ATCM-CF-74, ATCM-CF-75, ATCM-CF-76, ATCM-CF-77, ATCM-CF-78, ATCM-CF-79, ATCM-CF-80, ATCM-CF-81, ATCM-CF-82, ATCM-CF-83, ATCM-CF-84, ATCM-CF-85, ATCM-CF-86, ATCM-CF-87, ATCM-CF-88, ATCM-CF-89, ATCM-CF-90, ATCM-CF-91, ATCM-CF-92, ATCM-CF-93, ATCM-CF-94, ATCM-CF-95, ATCM-CF-96, ATCM-CF-97, ATCM-CF-98, ATCM-CF-99, ATCM-D-49, ATCM-D-50, ATCM-D-51, ATCM-D-52, ATCM-D-53, ATCM-D-54, ATCM-D-55, ATCM-D-56, ATCM-D-57, ATCM-D-58, ATCM-D-59, ATCM-D-60, ATCM-D-61, ATCM-D-62, ATCM-D-63, ATCM-C-71, ATCM-C-72, ATCM-C-73, ATCM-PG-44, ATCM-PG-45, ATCM-PG-46, ATCM-CF-100, ATCM-CF-101, ATCM-CF-102, ATCM-D-64, ATCM-D-65, ATCM-D-66 |
| Parent-record rule | Link rule (only W1 links; none → 404, G9) | ATCM-PG-41, ATCM-PG-42, ATCM-PG-43, ATCM-CF-97, ATCM-CF-98, ATCM-CF-99, ATCM-D-61, ATCM-D-62, ATCM-D-63 |
| Parent-record rule | PR-2 workspace owner opens every ticket (G11) [BUG-2103] | ATCM-C-73, ATCM-PG-46, ATCM-CF-102, ATCM-D-66 |
| Parent-record rule | PR-4 refusal before state / input errors and the ready return (G12) | ATCM-PG-47, ATCM-PG-48, ATCM-CF-103, ATCM-CF-104, ATCM-CF-105 |
| Facts | deleted_at clock | ATCM-D-05 |
| [BUG-1870] | xfail | ATCM-C-32, ATCM-C-33, ATCM-C-34, ATCM-C-35, ATCM-C-36, ATCM-C-37, ATCM-C-38, ATCM-C-39, ATCM-C-40, ATCM-C-41, ATCM-C-42, ATCM-C-61, ATCM-C-63, ATCM-C-64, ATCM-C-65, ATCM-C-66 |
| [BUG-1950] | xfail | ATCM-C-50, ATCM-C-51, ATCM-C-52, ATCM-C-53, ATCM-C-54, ATCM-C-62, ATCM-C-67, ATCM-C-68, ATCM-C-69, ATCM-C-70 |
| [BUG-2090] | xfail | ATCM-C-21, ATCM-C-22, ATCM-C-23, ATCM-C-24, ATCM-C-25, ATCM-C-26, ATCM-C-27, ATCM-C-28, ATCM-C-29, ATCM-C-30, ATCM-C-31 |
| [BUG-2091] | xfail | ATCM-PG-21, ATCM-PG-22, ATCM-PG-23, ATCM-PG-24, ATCM-PG-25, ATCM-PG-26, ATCM-PG-27, ATCM-PG-28, ATCM-PG-29, ATCM-PG-30, ATCM-PG-31, ATCM-PG-32, ATCM-PG-37, ATCM-PG-38, ATCM-PG-39, ATCM-PG-40, ATCM-PG-42, ATCM-PG-43, ATCM-CF-61, ATCM-CF-62, ATCM-CF-63, ATCM-CF-64, ATCM-CF-65, ATCM-CF-66, ATCM-CF-67, ATCM-CF-68, ATCM-CF-69, ATCM-CF-70, ATCM-CF-71, ATCM-CF-72, ATCM-CF-73, ATCM-CF-74, ATCM-CF-75, ATCM-CF-76, ATCM-CF-77, ATCM-CF-78, ATCM-CF-79, ATCM-CF-89, ATCM-CF-91, ATCM-CF-92, ATCM-CF-93, ATCM-CF-94, ATCM-CF-95, ATCM-CF-96, ATCM-CF-98, ATCM-CF-99, ATCM-D-41, ATCM-D-42, ATCM-D-43, ATCM-D-44, ATCM-D-45, ATCM-D-46, ATCM-D-47, ATCM-D-48, ATCM-D-49, ATCM-D-50, ATCM-D-51, ATCM-D-52, ATCM-D-57, ATCM-D-58, ATCM-D-59, ATCM-D-60, ATCM-D-62, ATCM-D-63 |
| [BUG-2092] | xfail | ATCM-CF-23 |
| [BUG-2093] | xfail | ATCM-CF-28 |
| [BUG-2094] | xfail | ATCM-CF-31 |
| [BUG-2096] | xfail | ATCM-CF-12 |
| [BUG-2097] | xfail | ATCM-D-04 |
| [BUG-2098] | xfail | ATCM-D-10, ATCM-D-11 |
| [BUG-2099] | xfail | ATCM-D-14, ATCM-D-15 |
| [BUG-2100] | xfail | ATCM-D-19 |
| [BUG-2101] | xfail | ATCM-DU-11 |
| [BUG-2102] | xfail | ATCM-C-13 |
