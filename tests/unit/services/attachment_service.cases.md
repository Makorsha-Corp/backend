# Test cases — `app/services/attachment_service.py`

> **Spec:** `tests/unit/services/attachment_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-04) — spec fill-gaps G1–G3 closed: BUG-2201 limit confirmed ≤ 3 (L-11 unchanged); `destroy_resource` stays patched on `app.managers.attachment_manager` (D-02, D-09, D-10 unchanged); new `confirm_upload` R3a (HR-13 commits the session as it stands) → new ATSV-CF-21 (strict xfail BUG-2095).
> **Revision:** 3 (2026-11-05) — executor notes DISCREPANCY-1 / -2: ATSV-CF-17 now uses the new **failing refresh after commit** (the manager's own refresh before the commit runs normally); ATSV-L-10 Then 3 no longer checks `F9 in db.dirty` (the savepoint flushes it) but that the edit survives in the transaction and is not committed. No card added or removed.
> **Revision:** 4 (2026-11-05) — verifier findings 1–6 and spec rules `confirm_upload` R3b, `delete_attachment` R4a: new D-15 … D-20 (pending / failed file deleted after the commit, BUG-2099; no `public_id` → no call; a delete error is swallowed with a WARNING, BUG-2100; the delete still runs when the re-read fails); L-25 (deleted work order), L-26 (unknown purchase order), L-27 (default `skip`); PG-12 (TC6 on an error); CF-22 (R3b: an unrelated pending row is discarded); PG-01 Then 4 pins the default `width`.
> **Counts:** 110 cases · 69 expected-to-pass · 41 expected-to-fail (bugs, all strict; 1 `Author: claude`) · 3 deferred

## Reviewer summary
- **Depth:** full for this service's own rules: what it commits or rolls back (TC1–TC6), the HR-13 "commit then raise" path (BUG-2095), the post-commit Cloudinary delete (BUG-2202), the record check of the list (BUG-2200, this service's own) and the batched link read (BUG-2201). Pass-through depth for the manager's rules: the access matrix (PR-1 … PR-5) is already in `attachment_manager.cases.md`. Here each access rule gets a refused card, a grant-held-elsewhere card (another project, or a privileged role in W0 / W2 only) and a granted card, so the cards show the caller reaches the manager.
- **Per callable:** `sign_upload` 14 (5 bug) · `confirm_upload` 22 (7 bug) · `list_attachments` 27 (14 bug) · `get_attachment` 15 (4 bug) · `get_pdf_page_image` 12 (3 bug) · `delete_attachment` 20 (8 bug).
- **Notable design choices:** every test commits its Given rows (commit point), so the service's own `rollback()` cannot remove them. "Committed" is checked after a test-level `db.rollback()`. Every refusal checks `session: clean` before any re-read. The HR-13 cards split in two. The pass card checks what holds today and after the fix (the same error object type and message; Cloudinary was asked once). The strict xfail checks the failure record after a test-level rollback. BUG-2202 is checked three ways: a failed commit keeps the row live (pass), a failed commit never calls `destroy_resource` (xfail), and on success the commit comes before the delete (xfail, an order log, `Author: claude`). BUG-2201 is counted as statements naming `attachment_links`, limit 3 (spec R5). Per R3a, CF-21 checks that an unrelated pending row is committed with the failure record (the spec states this; in practice nothing unrelated is pending). List, get and PDF-page pass cards go through `call_uid`, so they hold before and after the new `user_id` exists. BUG-2200 cards use `call_uid` too, so they fail today only on the missing record check.
- **Needs a decision:** None (gaps 1–3 closed by the spec's 2026-11-04 fill-gaps).

## Conventions for this module

**IDs.** `ATSV` = `app/services/attachment_service.py` (`ATCM`, `AMUP`, `MOBS` are the managers'; `ASV` is another module's). `S` sign_upload · `CF` confirm_upload · `L` list_attachments · `G` get_attachment · `PG` get_pdf_page_image · `D` delete_attachment.

**Imports.** `from app.services.attachment_service import AttachmentService, attachment_service, AttachmentNotFoundError, AttachmentConfirmError, AttachmentValidationError`; `from app.managers.attachment_manager import AttachmentLimitError`; `from app.core.cloudinary_client import CloudinaryNotConfiguredError`; `from app.schemas.attachment import AttachmentSignRequest`; `from app.models.enums import AttachmentEntityTypeEnum`; models `Attachment`, `AttachmentLink`, `Project`, `ProjectComponent`, `ProjectMember`, `Machine`, `Item`, `HelpTicket`, `WorkspaceMember`, `Factory`, `WorkOrder`, `WorkOrderType` (`app.models.<module>`). `IntegrityError`, `DataError` (`sqlalchemy.exc`); `event`, `text` (`sqlalchemy`); `patch` (`unittest.mock`); `inspect`, `logging`, `os`, `uuid`, `datetime`. Response classes are checked by `type(result).__name__`.

**Fixed values.** `svc` = `attachment_service`. `db` = the real session, first argument; every other argument by keyword. `result` = what the When returns. The session never autoflushes. MISSING = `999999999`. T0 = `datetime(2025, 12, 1, 8, 0, 0)`. **XID(k)** = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`; "`id XID(k)`" passes `id=XID(k)` to the builder. TOKEN = `"0123456789abcdef0123456789abcdef"`. PID1 = `"development/ws-" + str(W1.id) + "/" + TOKEN`. BSU = `"https://signed.example/a"`. **NFA(i)** = `"Attachment " + str(i) + " not found."`. **NF(t, i)** = `t + " " + str(i) + " not found."`. **ET(t)** = `AttachmentEntityTypeEnum(t)`.

**Settings (every test).** `monkeypatch.setattr` on `app.core.config.settings`, and the same names on `app.managers.attachment_manager.settings` and `app.services.attachment_service.settings` (the spec's targets; setting one object twice is harmless): `CLOUDINARY_UPLOAD_ENV "development"`, `ENVIRONMENT "development"`, `CLOUDINARY_CLOUD_NAME "demo-cloud"`, `CLOUDINARY_API_KEY "123456"`, `CLOUDINARY_API_SECRET "s3cret"`, `MAX_ATTACHMENTS_PER_ENTITY 25`. A Given line "settings: NAME value" overrides one the same way.

**Cloudinary (every test, never the network).** Each is `patch("app.managers.attachment_manager.<name>", autospec=True)`: **gus** `generate_upload_signature` → `"sig-x"`; **gr** `get_resource` → **RES** = `{"resource_type": "image", "format": "jpg", "bytes": 1234, "version": 1700000000, "secure_url": "https://res.example/s.jpg", "url": "http://res.example/u.jpg", "width": 800, "height": 600, "asset_id": "a" * 32, "etag": "e" * 32}`; **dr** `destroy_resource` → `{"result": "ok"}`; **bsu** `build_signed_delivery_url` → BSU. A card may set `return_value` / `side_effect`. **fixed uuid** = `patch("app.managers.attachment_manager.uuid.uuid4", return_value=uuid.UUID(TOKEN))` and **fixed time** = `patch("app.managers.attachment_manager.time.time", return_value=1767225600.9)`, in every test. **kw(m)** = `ba = inspect.signature(m).bind(*m.call_args.args, **m.call_args.kwargs)`, `ba.apply_defaults()`, `dict(ba.arguments)`. **cl_untouched** = `gus.called is False`, `gr.called is False`, `dr.called is False`, `bsu.called is False`.

**Standing rows** (every test, built in this order, each flushed): W0, W1, W2 = `make_workspace(db)` (W0.id < W1.id < W2.id; no `owner_user_id`). U1 = `make_profile(db, name="Ana Rahman")`, U2 = `make_profile(db, name="Bilal Khan")`, UG = `make_profile(db, name="Mia Khan")`. member(U1, "ground-team"), member(U2, "owner"), MG = member(UG, "ground-team"). F0, F1, F9 = `Factory(workspace_id=<W0|W1|W2>.id, name="Factory Zero|One|Nine", abbreviation="F0|F1|F9")`. UG is the caller of every card unless the When says otherwise.

**Given rows** (added and flushed one at a time in the order written; after "but" every differing column; a line written as code runs as written):
- **member(U, role, status="active", ws=W1)** = `WorkspaceMember(workspace_id=ws.id, user_id=U.id, role=role, status=status)`.
- **mach("L")** = `Machine(workspace_id=W1.id, factory_id=F1.id, name="L")`; **W0 mach** / **W2 mach** = `workspace_id W0.id, factory_id F0.id` / `W2.id, F9.id`; **deleted** = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`. **item("L", sku)** = `Item(workspace_id=W1.id, name="L", name_normalized="L".lower(), unit="pcs", sku=sku)`. **wo("N")** = first `WT = WorkOrderType(workspace_id=W1.id, name="Repair")`, flushed, then `WorkOrder(workspace_id=W1.id, work_order_number="N", title="Fix press", factory_id=F1.id, work_order_type_id=WT.id)`; **deleted** (work order) = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
- **proj("L")** = `Project(workspace_id=W1.id, factory_id=F1.id, name="L", description="Main", created_by=U1.id)`; **private** = `visibility "invited_only"`; **deleted** = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. **pmem(P, U)** = `ProjectMember(workspace_id=P.workspace_id, project_id=P.id, user_id=U.id, assigned_by=U1.id)`. **comp(P, "L")** = `ProjectComponent(workspace_id=P.workspace_id, project_id=P.id, name="L")`. **ticket("N")** = `HelpTicket(workspace_id=W1.id, ticket_number="N", title="Printer jam", description="It jams", created_by=U1.id)`.
- **att("pid")** = `Attachment(workspace_id=W1.id, file_name="photo.jpg", mime_type="image/jpeg", file_size=1000, uploaded_by=U1.id, upload_status="pending", public_id="pid", resource_type="image", delivery_type="authenticated", note="Front")`. **ready** = `upload_status "ready"`, `format "jpg"`, `version 1700000000`. **failed** = `upload_status "failed"`. **pdf** = `file_name "plan.pdf"`, `mime_type "application/pdf"`, `format "pdf"`. **gone** = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. **W0 att** / **W2 att** = `workspace_id W0.id` / `W2.id`.
- **link(A, "type", P)** = `AttachmentLink(workspace_id=A.workspace_id, attachment_id=A.id, entity_type="type", entity_id=P.id, linked_by=U1.id)`; `P` may be a number.
- **fill(P, n, "status")** = n rows att(f"fill-{i}") but `upload_status "status"` (`format "jpg"`, `version 1700000000` when "ready"), each with link(·, P's type, P), i = 1…n; it returns the list of attachments it built ("FL = fill(…)").
- **REQ("type", id)** = `AttachmentSignRequest(entity_type="type", entity_id=id, file_name="plan.pdf", mime_type="application/pdf", file_size=1000, note="Site plan")`.

**Commit point (every test).** After the last Given line the test runs `db.commit()` (releases a savepoint under the `db` fixture), so the service's own rollback cannot remove Given rows. Snapshots for `unchanged` and `nothing written` are taken there. Then, only where a card lists them:
- **pending X** = `X = Factory(workspace_id=W2.id, name="Factory X", abbreviation="FX")`, `db.add(X)`, `db.flush()`; `X_ID = X.id`. **x_gone** = `db.scalar(text("SELECT count(*) FROM factories WHERE id = :i"), {"i": X_ID}) == 0`; **x_kept** = the same count `== 1`.
- **pending edit** = `F9.name = "Factory Edited"` (not flushed).

**Named checks.**
- `session:` lines check `db` right after the call, before any re-read. **clean** = `not db.new`, `not db.dirty`, `not db.deleted`.
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its snapshot.
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line then re-reads with a fresh query.
- **ledger_of(A)** / **links_of(A)** = `db.expire_all()`, then rows of `attachment_ledger` / `attachment_links` with `attachment_id == A.id` (or the id given), ordered by `id`. **events_of(M)** = `db.execute(text("SELECT event_type, description, performed_by FROM machine_activity_events WHERE machine_id = :i ORDER BY id"), {"i": M.id}).all()`.
- **nothing written** = row counts of `attachments`, `attachment_links`, `attachment_ledger`, `machine_activity_events`, `project_events` (all workspaces) equal their values at the commit point.
- `raises: T` = `with pytest.raises(T) as exc:` around the call, no savepoint unless the card says "in a savepoint" (then `with db.begin_nested():` inside); `str(exc.value)` is the message.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **failing commit** = `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When, inside `with pytest.raises(RuntimeError) as exc:`. **failing refresh** = the same with `patch.object(db, "refresh", side_effect=RuntimeError("boom"))` (no rollback spy). **failing refresh after commit** = `real_r = db.refresh`; inside `with pytest.raises(RuntimeError) as exc:`, `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "refresh", side_effect=late) as rf:` around the When, where `late(*a, **k)` raises `RuntimeError("boom")` when `cm.called` is True and otherwise returns `real_r(*a, **k)` (refreshes before the commit, e.g. the manager's own, run normally).
- **order log** = `order = []`; dr's `side_effect` = a function that appends `"dr"` and returns `{"result": "ok"}`; `real = db.commit`; `patch.object(db, "commit", side_effect=lambda: (order.append("commit"), real())[1])` around the When.
- **recorder** = `stmts = []`; `event.listen(db.connection(), "before_cursor_execute", rec)` appending each `statement`; `event.remove` right after the When. **link_stmts** = the number of `stmts` containing `"attachment_links"`.
- **warnings** = `caplog.set_level(logging.WARNING)` (root logger) before the When; **warned(p)** = `any(r.levelno == logging.WARNING and p in r.getMessage() for r in caplog.records)`.
- **ids(r)** = `{i.id for i in r.items}`. **lk(x)** = `[(l.entity_type.value, l.entity_id) for l in x.links]`.

**Caller (PR-5).** `list_attachments`, `get_attachment`, `get_pdf_page_image` gain a required keyword `user_id` (BUG-1870, BUG-1950, BUG-2091). **call_uid(fn, U, **kw)** = `fn(db, **kw, user_id=U.id)` when `"user_id" in inspect.signature(fn).parameters`, else `fn(db, **kw)`. **la** / **ga** / **pg** = call_uid with `svc.list_attachments` / `svc.get_attachment` / `svc.get_pdf_page_image`. xfail cards that need the caller write `user_id=UG.id` directly (TypeError today).

**xfail cards.** `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call exactly as shown.

**Race simulations.** None.

## `AttachmentService.sign_upload`

### ATSV-S-01 — sign answers the upload parameters and commits a pending attachment
- **Rules:** sign_upload R3, TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").

**When**
- `result = svc.sign_upload(db, workspace=W1, user=UG, payload=REQ("machine", M1.id))`

**Then**
1. returns: `type(result).__name__ == "AttachmentSignResponse"`.
2. returns: `result.public_id == PID1`.
3. returns: `result.asset_folder == "Dev/" + W1.name + "/Machines/Lathe"`, `result.display_name == "plan.pdf"`.
4. returns: `result.timestamp == 1767225600`, `result.signature == "sig-x"`, `result.type == "authenticated"`.
5. returns: `result.resource_type == "image"`, `result.upload_url == "https://api.cloudinary.com/v1_1/demo-cloud/image/upload"`.
6. returns: `result.cloud_name == "demo-cloud"`, `result.api_key == "123456"`.
7. mock called: `gus.call_count == 1`, `kw(gus)["public_id"] == PID1`.
8. mock called: `gr.called is False`, `dr.called is False`.
9. committed: the attachments row with `id == result.attachment_id` has `upload_status == "pending"`, `public_id == PID1`, `workspace_id == W1.id`, `uploaded_by == UG.id`, `file_name == "plan.pdf"`, `note == "Site plan"`.

### ATSV-S-02 — the link and the pending ledger row are committed with the caller
- **Rules:** sign_upload R3, TC1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").

**When**
- `result = svc.sign_upload(db, workspace=W1, user=UG, payload=REQ("machine", M1.id))`

**Then**
1. returns: `result.attachment_id is not None`.
2. committed: links_of(result.attachment_id) has exactly 1 row: `workspace_id == W1.id`, `entity_type == "machine"`, `entity_id == M1.id`, `linked_by == UG.id`.
3. committed: ledger_of(result.attachment_id) has exactly 1 row: `transaction_type == "pending"`, `performed_by == UG.id`, `entity_type == "machine"`, `entity_id == M1.id`.
4. committed: `events_of(M1) == []`.

### ATSV-S-03 — an invalid file is refused first; nothing written
- **Rules:** sign_upload R1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").

**When**
- `svc.sign_upload(db, workspace=W1, user=UG, payload=AttachmentSignRequest(entity_type="machine", entity_id=M1.id, file_name="plan.pdf", mime_type="application/pdf", file_size=10485761))`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == "File too large (10485761 bytes). Maximum is 10485760 bytes."`
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATSV-S-04 — a full record is refused; nothing written
- **Rules:** sign_upload R2
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. fill(M1, 25, "ready").

**When**
- `svc.sign_upload(db, workspace=W1, user=UG, payload=REQ("machine", M1.id))`

**Then**
1. raises: `AttachmentLimitError`.
2. raises: `str(exc.value) == "This record already has the maximum of 25 attachments."`
3. session: clean.
4. nothing written.

### ATSV-S-05 — Cloudinary not configured after the flush: everything rolled back
- **Rules:** sign_upload R4, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_API_KEY "".
2. M1 = mach("Lathe").

**When**
- spies: `svc.sign_upload(db, workspace=W1, user=UG, payload=REQ("machine", M1.id))`

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. raises: `str(exc.value) == "Cloudinary cloud name and API key are required."`
3. session: clean.
4. mock called: `rb.call_count >= 1`.
5. nothing written.
6. count: `db.scalar(text("SELECT count(*) FROM attachments WHERE public_id = :p"), {"p": PID1}) == 0`.

### ATSV-S-06 — any other error reaches the caller as the same object and discards other pending changes
- **Rules:** sign_upload R6, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. `E = RuntimeError("sig down")`; gus `side_effect = E`.
3. pending X.

**When**
- `svc.sign_upload(db, workspace=W1, user=UG, payload=REQ("machine", M1.id))`

**Then**
1. raises: `RuntimeError`.
2. raises: `exc.value is E`.
3. session: clean.
4. count: x_gone.
5. nothing written.
6. session: `db.execute(text("SELECT 1")).scalar() == 1`.

### ATSV-S-07 — a failing commit rolls back; nothing saved
- **Rules:** sign_upload R5, TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").

**When**
- failing commit: `svc.sign_upload(db, workspace=W1, user=UG, payload=REQ("machine", M1.id))`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. nothing written.

### ATSV-S-08 — a failing re-read after the commit leaves the attachment saved
- **Rules:** sign_upload R5, TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").

**When**
- failing refresh: `svc.sign_upload(db, workspace=W1, user=UG, payload=REQ("machine", M1.id))`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: exactly 1 attachments row has `public_id == PID1`, with `upload_status == "pending"`, `uploaded_by == UG.id`.
3. committed: exactly 1 attachment_links row has `entity_type == "machine"` and `entity_id == M1.id`.

### ATSV-S-09 — a deleted machine is refused as not found; nothing written
- **Rules:** sign_upload R2 [BUG-2090]
- **Kind:** bug
- **Expect:** xfail BUG-2090
- **Fails today on:** Then 1 (no error is raised: the record is not looked up)

**Given**
1. M1 = mach("Lathe") but deleted.

**When**
- `svc.sign_upload(db, workspace=W1, user=UG, payload=REQ("machine", M1.id))`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("machine", M1.id)`.
3. session: clean.
4. nothing written.
5. mock called: cl_untouched.

### ATSV-S-10 — a W0 machine is refused as not found; nothing written
- **Rules:** sign_upload R2 [BUG-2090]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-2090
- **Fails today on:** Then 1 (no error is raised: the record is not looked up)

**Given**
1. M0 = mach("Lathe") but W0 mach.

**When**
- `svc.sign_upload(db, workspace=W1, user=UG, payload=REQ("machine", M0.id))`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("machine", M0.id)`.
3. session: clean.
4. nothing written.

### ATSV-S-11 — a private project the caller may not open is refused
- **Rules:** sign_upload R2 [BUG-1870]; PR-2, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: visibility is not checked)

**Given**
1. P1 = proj("Tender") but private.

**When**
- `svc.sign_upload(db, workspace=W1, user=UG, payload=REQ("project", P1.id))`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", P1.id)`.
3. session: clean.
4. nothing written.

### ATSV-S-12 — membership of another private project does not open this one
- **Rules:** sign_upload R2 [BUG-1870]; PR-2 (grant held on a different record)
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (no error is raised: visibility is not checked)

**Given**
1. P1 = proj("Tender") but private.
2. P2 = proj("Bridge") but private.
3. pmem(P2, UG).

**When**
- `svc.sign_upload(db, workspace=W1, user=UG, payload=REQ("project", P1.id))`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", P1.id)`.
3. session: clean.
4. nothing written.

### ATSV-S-13 — an owner role held only in W2 does not open another member's W1 ticket
- **Rules:** sign_upload R2 [BUG-1950]; PR-2, PR-5 (grant held in a different workspace)
- **Kind:** bug
- **Expect:** xfail BUG-1950
- **Fails today on:** Then 1 (no error is raised: visibility is not checked)

**Given**
1. member(UG, "owner", ws=W2).
2. T1 = ticket("HT-1").

**When**
- `svc.sign_upload(db, workspace=W1, user=UG, payload=REQ("support_ticket", T1.id))`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", T1.id)`.
3. session: clean.
4. nothing written.

### ATSV-S-14 — a member of the private project signs; the caller is the uploader
- **Rules:** sign_upload R2, R3; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender") but private.
2. pmem(P1, UG).

**When**
- `result = svc.sign_upload(db, workspace=W1, user=UG, payload=REQ("project", P1.id))`

**Then**
1. returns: `result.public_id == PID1`, `result.asset_folder == "Dev/" + W1.name + "/Projects/Tender"`.
2. committed: the attachments row with `id == result.attachment_id` has `uploaded_by == UG.id`, `upload_status == "pending"`.
3. committed: links_of(result.attachment_id) has exactly 1 row: `entity_type == "project"`, `entity_id == P1.id`.

## `AttachmentService.confirm_upload`

### ATSV-CF-01 — confirm marks ready, commits, and answers the re-read row
- **Rules:** confirm_upload R1, TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1"); link(A1, "machine", M1).

**When**
- `result = svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. returns: `type(result).__name__ == "AttachmentResponse"`, `result.id == A1.id`.
2. returns: `result.upload_status == "ready"`, `result.format == "jpg"`, `result.version == 1700000000`.
3. returns: `result.file_url == "https://res.example/s.jpg"`, `result.urls.preview_url == BSU`.
4. returns: `result.uploaded_at is not None`, `lk(result) == [("machine", M1.id)]`.
5. mock called: `gr.call_count == 1`, `kw(gr)["public_id"] == "pid-1"`.
6. committed: re-read A1: `upload_status == "ready"`, `file_url == "https://res.example/s.jpg"`, `width == 800`, `height == 600`.

### ATSV-CF-02 — the ready ledger row and the activity entry carry the caller
- **Rules:** confirm_upload R1, TC1; PR-5 (caller passed down)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1"); link(A1, "machine", M1).

**When**
- `result = svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. committed: ledger_of(A1) has exactly 1 row: `transaction_type == "ready"`, `performed_by == UG.id`, `entity_type == "machine"`, `entity_id == M1.id`.
3. committed: `events_of(M1) == [("attachment_added", "Attached photo.jpg", UG.id)]`.

### ATSV-CF-03 — performed_by None: the uploader is the actor
- **Rules:** confirm_upload Inputs (`performed_by` None → uploader), R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1"); link(A1, "machine", M1).

**When**
- `result = svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. committed: ledger_of(A1) has exactly 1 row: `transaction_type == "ready"`, `performed_by == U1.id`.

### ATSV-CF-04 — an already ready attachment is answered unchanged; nothing written
- **Rules:** confirm_upload R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready; link(A1, "machine", M1).

**When**
- `result = svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. returns: `result.id == A1.id`, `result.upload_status == "ready"`.
2. mock called: `gr.called is False`.
3. unchanged: unchanged(A1).
4. nothing written.

### ATSV-CF-05 — a failed Cloudinary lookup reaches the caller as the confirm error
- **Rules:** confirm_upload R3 (part that holds today)
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1"); link(A1, "machine", M1).
3. gr `side_effect = RuntimeError("boom")`.

**When**
- `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Cloudinary verification failed: boom"`.
3. session: clean.
4. mock called: `gr.call_count == 1`.
5. count: `events_of(M1) == []`.

### ATSV-CF-06 — the failure record of a failed lookup is committed, then the error returned
- **Rules:** confirm_upload R3 [BUG-2095]; HR-13
- **Kind:** bug
- **Expect:** xfail BUG-2095
- **Fails today on:** Then 3 (rolled back: the attachment is still pending)

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1"); link(A1, "machine", M1).
3. gr `side_effect = RuntimeError("boom")`.

**When**
- `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Cloudinary verification failed: boom"`.
3. committed: re-read A1: `upload_status == "failed"`.
4. committed: ledger_of(A1) has exactly 1 row: `transaction_type == "failed"`, `notes == "boom"`, `performed_by == UG.id`.

### ATSV-CF-07 — a file Cloudinary describes wrongly reaches the caller as the confirm error
- **Rules:** confirm_upload R3 (part that holds today)
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1"); link(A1, "machine", M1).
3. gr `return_value` = RES but `"resource_type": "raw"`, `"format": "exe"`.

**When**
- `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentConfirmError`.
2. session: clean.
3. mock called: `gr.call_count == 1`.

### ATSV-CF-08 — the failure record of a refused file is committed, then the error returned
- **Rules:** confirm_upload R3 [BUG-2095]; HR-13
- **Kind:** bug
- **Expect:** xfail BUG-2095
- **Fails today on:** Then 2 (rolled back: the attachment is still pending)

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1"); link(A1, "machine", M1).
3. gr `return_value` = RES but `"resource_type": "raw"`, `"format": "exe"`.

**When**
- `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentConfirmError`.
2. committed: re-read A1: `upload_status == "failed"`.
3. committed: ledger_of(A1) has exactly 1 row: `transaction_type == "failed"`, `performed_by == UG.id`.

### ATSV-CF-09 — when the commit of the failure record fails, the commit's error reaches the caller
- **Rules:** confirm_upload R3 [BUG-2095], TC4
- **Kind:** bug
- **Expect:** xfail BUG-2095
- **Fails today on:** Then 1 (the call raises AttachmentConfirmError: no commit is attempted on this path)

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1"); link(A1, "machine", M1).
3. gr `side_effect = RuntimeError("lookup")`.

**When**
- failing commit: `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read A1: `upload_status == "pending"`.
4. nothing written.

### ATSV-CF-10 — no public_id: the refusal wrote nothing, nothing committed
- **Rules:** confirm_upload R3 (refusal that wrote nothing)
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but `public_id None`; link(A1, "machine", M1).

**When**
- `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Attachment has no public_id."`
3. session: clean.
4. unchanged: unchanged(A1).
5. nothing written.
6. mock called: `gr.called is False`.

### ATSV-CF-11 — an unknown id rolls back and discards other pending changes
- **Rules:** confirm_upload R4, TC3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1"); link(A1, "machine", M1).
3. pending X.

**When**
- spies: `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=MISSING, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(MISSING)`.
3. session: clean.
4. mock called: `rb.call_count >= 1`.
5. count: x_gone.
6. nothing written.
7. mock called: cl_untouched.

### ATSV-CF-12 — a W0 attachment is not found
- **Rules:** confirm_upload R4; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = att("pid-0") but W0 att; link(A0, "scratch", 1).

**When**
- `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A0.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A0.id)`.
3. session: clean.
4. unchanged: unchanged(A0).
5. nothing written.

### ATSV-CF-13 — a W2 attachment is not found
- **Rules:** confirm_upload R4; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A2 = att("pid-2") but W2 att; link(A2, "scratch", 1).

**When**
- `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A2.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A2.id)`.
3. session: clean.
4. unchanged: unchanged(A2).
5. nothing written.

### ATSV-CF-14 — a soft-deleted attachment is not found
- **Rules:** confirm_upload R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but gone; link(A1, "machine", M1).

**When**
- `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A1.id)`.
3. session: clean.
4. nothing written.

### ATSV-CF-15 — Cloudinary not configured passes through unchanged; nothing written
- **Rules:** confirm_upload R4 [BUG-2096]
- **Kind:** bug
- **Expect:** xfail BUG-2096
- **Fails today on:** Then 1 (the call raises AttachmentConfirmError: the error is wrapped)

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1"); link(A1, "machine", M1).
3. gr `side_effect = CloudinaryNotConfiguredError("not set")`.

**When**
- `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. raises: `str(exc.value) == "not set"`.
3. session: clean.
4. unchanged: unchanged(A1).
5. nothing written.

### ATSV-CF-16 — a failing commit after a good confirm leaves the attachment pending
- **Rules:** confirm_upload R5, TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1"); link(A1, "machine", M1).

**When**
- failing commit: `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read A1: `upload_status == "pending"`, `file_url is None`.
4. nothing written.

### ATSV-CF-17 — a failing re-read after the commit leaves the attachment ready
- **Rules:** confirm_upload R5, TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1"); link(A1, "machine", M1).

**When**
- failing refresh after commit: `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read A1: `upload_status == "ready"`.
3. committed: ledger_of(A1) has exactly 1 row: `transaction_type == "ready"`.

### ATSV-CF-18 — an attachment of a private project the caller may not open is not found
- **Rules:** confirm_upload R1 [BUG-2091]; PR-3, PR-5 (`performed_by` is the caller)
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the record is not checked)

**Given**
1. P1 = proj("Tender") but private.
2. A1 = att("pid-1"); link(A1, "project", P1).

**When**
- `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A1.id)`.
3. session: clean.
4. unchanged: unchanged(A1).
5. nothing written.
6. mock called: cl_untouched.

### ATSV-CF-19 — membership of another private project does not open this attachment
- **Rules:** confirm_upload R1 [BUG-2091]; PR-2 (grant held on a different record)
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the record is not checked)

**Given**
1. P1 = proj("Tender") but private.
2. P2 = proj("Bridge") but private.
3. pmem(P2, UG).
4. A1 = att("pid-1"); link(A1, "project", P1).

**When**
- `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A1.id)`.
3. session: clean.
4. unchanged: unchanged(A1).
5. nothing written.

### ATSV-CF-20 — a project member confirms the private project's attachment
- **Rules:** confirm_upload R1; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender") but private.
2. pmem(P1, UG).
3. A1 = att("pid-1"); link(A1, "project", P1).

**When**
- `result = svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. committed: re-read A1: `upload_status == "ready"`.
3. committed: ledger_of(A1) has exactly 1 row: `transaction_type == "ready"`, `performed_by == UG.id`.

### ATSV-CF-21 — the failure record's commit also commits an unrelated pending row
- **Rules:** confirm_upload R3a [BUG-2095]; HR-13
- **Kind:** bug
- **Expect:** xfail BUG-2095
- **Fails today on:** Then 4 (rolled back: X is discarded)

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1"); link(A1, "machine", M1).
3. gr `side_effect = RuntimeError("boom")`.
4. pending X.

**When**
- `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Cloudinary verification failed: boom"`.
3. session: clean.
4. committed: x_kept.
5. committed: re-read A1: `upload_status == "failed"`.

### ATSV-CF-22 — the no-public_id refusal discards an unrelated pending row
- **Rules:** confirm_upload R3b, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but `public_id None`; link(A1, "machine", M1).
3. pending X.

**When**
- spies: `svc.confirm_upload(db, workspace_id=W1.id, attachment_id=A1.id, performed_by=UG.id)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Attachment has no public_id."`
3. session: clean.
4. mock called: `rb.call_count >= 1`.
5. count: x_gone.
6. nothing written.

## `AttachmentService.list_attachments`

### ATSV-L-01 — the record's ready live attachments, the used places and the maximum
- **Rules:** list_attachments R1, R3, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. R1 = att("r-1") but ready; link(R1, "machine", M1).
3. R2 = att("r-2") but ready; link(R2, "machine", M1).
4. R3 = att("r-3") but ready; link(R3, "machine", M1).
5. P4 = att("p-4"); link(P4, "machine", M1).
6. G5 = att("g-5") but ready, gone; link(G5, "machine", M1).

**When**
- `result = la(UG, workspace_id=W1.id, entity_type=ET("machine"), entity_id=M1.id, skip=0, limit=1000)`

**Then**
1. returns: `type(result).__name__ == "AttachmentListResponse"`.
2. returns: `ids(result) == {R1.id, R2.id, R3.id}`.
3. returns: `all(lk(i) == [("machine", M1.id)] for i in result.items)`.
4. returns: `all(i.urls.preview_url == BSU for i in result.items)`.
5. returns: `result.slot_count == 4`.
6. returns: `result.max_per_entity == 25`.

### ATSV-L-02 — links of the same record id in W0 and W2 are neither listed nor counted
- **Rules:** list_attachments R1, R3; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A0 = att("w0-1") but W0 att, ready; link(A0, "machine", M1.id).
3. A1 = att("w1-1") but ready; link(A1, "machine", M1).
4. A2 = att("w2-1") but W2 att, ready; link(A2, "machine", M1.id).

**When**
- `result = la(UG, workspace_id=W1.id, entity_type=ET("machine"), entity_id=M1.id, skip=0, limit=1000)`

**Then**
1. returns: `ids(result) == {A1.id}`.
2. returns: `result.slot_count == 1`.

### ATSV-L-03 — other records with a lower and a higher id, and the same id under another type, do not count
- **Rules:** list_attachments R1, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. MA = mach("Alpha") but `id XID(1)`.
2. M1 = mach("Lathe") but `id XID(2)`.
3. MB = mach("Beta") but `id XID(3)`.
4. I1 = item("Bolt", "B-1") but `id XID(2)`.
5. AA = att("a-1") but ready; link(AA, "machine", MA).
6. A1 = att("m-1") but ready; link(A1, "machine", M1).
7. AB = att("b-1") but ready; link(AB, "machine", MB).
8. AI = att("i-1") but ready; link(AI, "item", I1).

**When**
- `result = la(UG, workspace_id=W1.id, entity_type=ET("machine"), entity_id=XID(2), skip=0, limit=1000)`

**Then**
1. returns: `ids(result) == {A1.id}`.
2. returns: `result.slot_count == 1`.

### ATSV-L-04 — slot_count does not depend on the page
- **Rules:** list_attachments R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. FL = fill(M1, 3, "ready").

**When**
- `result = la(UG, workspace_id=W1.id, entity_type=ET("machine"), entity_id=M1.id, skip=0, limit=2)`

**Then**
1. returns: `len(result.items) == 2`.
2. returns: `ids(result) <= {a.id for a in FL}`.
3. returns: `result.slot_count == 3`.

### ATSV-L-05 — the default page holds 100 items
- **Rules:** list_attachments R1 (default `limit=100`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: MAX_ATTACHMENTS_PER_ENTITY 500.
2. M1 = mach("Lathe").
3. fill(M1, 101, "ready").

**When**
- `result = la(UG, workspace_id=W1.id, entity_type=ET("machine"), entity_id=M1.id)`

**Then**
1. returns: `len(result.items) == 100`.
2. returns: `result.slot_count == 101`.
3. returns: `result.max_per_entity == 500`.

### ATSV-L-06 — max_per_entity is read from settings at the call
- **Rules:** list_attachments R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: MAX_ATTACHMENTS_PER_ENTITY 7.
2. M1 = mach("Lathe").

**When**
- `result = la(UG, workspace_id=W1.id, entity_type=ET("machine"), entity_id=M1.id, skip=0, limit=1000)`

**Then**
1. returns: `result.max_per_entity == 7`.
2. returns: `result.items == []`, `result.slot_count == 0`.

### ATSV-L-07 — failed attachments are not listed
- **Rules:** list_attachments R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("r-1") but ready; link(A1, "machine", M1).
3. AF = att("f-1") but failed; link(AF, "machine", M1).

**When**
- `result = la(UG, workspace_id=W1.id, entity_type=ET("machine"), entity_id=M1.id, skip=0, limit=1000)`

**Then**
1. returns: `ids(result) == {A1.id}`.

### ATSV-L-08 — failed attachments do not use a place
- **Rules:** list_attachments R3 [BUG-1434]
- **Kind:** bug
- **Expect:** xfail BUG-1434
- **Fails today on:** Then 2 (the count includes the failed attachment: 2)

**Given**
1. M1 = mach("Lathe").
2. A1 = att("r-1") but ready; link(A1, "machine", M1).
3. AF = att("f-1") but failed; link(AF, "machine", M1).

**When**
- `result = la(UG, workspace_id=W1.id, entity_type=ET("machine"), entity_id=M1.id, skip=0, limit=1000)`

**Then**
1. returns: `ids(result) == {A1.id}`.
2. returns: `result.slot_count == 1`.

### ATSV-L-09 — a list neither commits nor rolls back; pending changes stay pending
- **Rules:** list_attachments R6, TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("r-1") but ready; link(A1, "machine", M1).
3. pending X.
4. pending edit.

**When**
- spies: `result = la(UG, workspace_id=W1.id, entity_type=ET("machine"), entity_id=M1.id, skip=0, limit=1000)`

**Then**
1. returns: `ids(result) == {A1.id}`.
2. mock called: `cm.called is False`, `rb.called is False`.
3. session: `F9 in db.dirty`, `len(db.dirty) == 1`.
4. count: x_kept.
5. committed: x_gone.

### ATSV-L-10 — a negative skip raises DataError without a rollback
- **Rules:** list_attachments R6
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. pending edit.

**When**
- spies: in a savepoint, `la(UG, workspace_id=W1.id, entity_type=ET("machine"), entity_id=M1.id, skip=-1, limit=100)`

**Then**
1. raises: `DataError`.
2. mock called: `cm.called is False`, `rb.called is False`.
3. re-read F9: `name == "Factory Edited"` (the savepoint flushed the edit; no session rollback discarded it).
4. committed: re-read F9: `name == "Factory Nine"`.

### ATSV-L-11 — the links of all listed attachments are read together
- **Rules:** list_attachments R5 [BUG-2201]
- **Kind:** bug
- **Expect:** xfail BUG-2201
- **Fails today on:** Then 2 (one links query per item: 7 statements)

**Given**
1. M1 = mach("Lathe").
2. fill(M1, 5, "ready").
3. recorder.

**When**
- `result = la(UG, workspace_id=W1.id, entity_type=ET("machine"), entity_id=M1.id, skip=0, limit=1000)`

**Then**
1. returns: `len(result.items) == 5`, `all(lk(i) == [("machine", M1.id)] for i in result.items)`.
2. statement: `link_stmts <= 3`.

### ATSV-L-12 — an unknown record is not found
- **Rules:** list_attachments R1a [BUG-2200]; PR-1
- **Kind:** bug
- **Expect:** xfail BUG-2200
- **Fails today on:** Then 1 (no error is raised: an empty list is returned)

**Given**
1. Nothing beyond the standing rows.

**When**
- `la(UG, workspace_id=W1.id, entity_type=ET("machine"), entity_id=MISSING, skip=0, limit=100)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("machine", MISSING)`.
3. session: clean.

### ATSV-L-13 — a deleted machine's files are not listed
- **Rules:** list_attachments R1a [BUG-2200]; PR-1, HR-4
- **Kind:** bug
- **Expect:** xfail BUG-2200
- **Fails today on:** Then 1 (no error is raised: the photos are listed)

**Given**
1. M1 = mach("Lathe") but deleted.
2. A1 = att("r-1") but ready; link(A1, "machine", M1).

**When**
- `la(UG, workspace_id=W1.id, entity_type=ET("machine"), entity_id=M1.id, skip=0, limit=100)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("machine", M1.id)`.
3. session: clean.
4. mock called: `bsu.called is False`.

### ATSV-L-14 — a deleted project's files are not listed
- **Rules:** list_attachments R1a [BUG-2200]; PR-1
- **Kind:** bug
- **Expect:** xfail BUG-2200
- **Fails today on:** Then 1 (no error is raised: the files are listed)

**Given**
1. P1 = proj("Tender") but deleted.
2. A1 = att("r-1") but ready; link(A1, "project", P1).

**When**
- `la(UG, workspace_id=W1.id, entity_type=ET("project"), entity_id=P1.id, skip=0, limit=100)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", P1.id)`.
3. session: clean.

### ATSV-L-15 — a component of a deleted project is not found
- **Rules:** list_attachments R1a [BUG-2200]; PR-1
- **Kind:** bug
- **Expect:** xfail BUG-2200
- **Fails today on:** Then 1 (no error is raised: the files are listed)

**Given**
1. P1 = proj("Tender") but deleted.
2. C1 = comp(P1, "Roof").
3. A1 = att("r-1") but ready; link(A1, "project_component", C1).

**When**
- `la(UG, workspace_id=W1.id, entity_type=ET("project_component"), entity_id=C1.id, skip=0, limit=100)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project_component", C1.id)`.
3. session: clean.

### ATSV-L-16 — a W0 machine is not found from W1
- **Rules:** list_attachments R1a [BUG-2200]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-2200
- **Fails today on:** Then 1 (no error is raised: an empty list is returned)

**Given**
1. M0 = mach("Lathe") but W0 mach.
2. A0 = att("w0-1") but W0 att, ready; link(A0, "machine", M0).

**When**
- `la(UG, workspace_id=W1.id, entity_type=ET("machine"), entity_id=M0.id, skip=0, limit=100)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("machine", M0.id)`.
3. session: clean.

### ATSV-L-17 — a W2 machine is not found from W1
- **Rules:** list_attachments R1a [BUG-2200]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-2200
- **Fails today on:** Then 1 (no error is raised: an empty list is returned)

**Given**
1. M2 = mach("Lathe") but W2 mach.
2. A2 = att("w2-1") but W2 att, ready; link(A2, "machine", M2).

**When**
- `la(UG, workspace_id=W1.id, entity_type=ET("machine"), entity_id=M2.id, skip=0, limit=100)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("machine", M2.id)`.
3. session: clean.

### ATSV-L-18 — a project id that exists only as a machine is not found, though links name it
- **Rules:** list_attachments R1a [BUG-2200]; PR-1
- **Kind:** bug
- **Expect:** xfail BUG-2200
- **Fails today on:** Then 1 (no error is raised: the linked file is listed)

**Given**
1. M1 = mach("Lathe") but `id XID(4)`.
2. No project has `id XID(4)`.
3. A1 = att("r-1") but ready; link(A1, "project", XID(4)).

**When**
- `la(UG, workspace_id=W1.id, entity_type=ET("project"), entity_id=XID(4), skip=0, limit=100)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", XID(4))`.
3. session: clean.

### ATSV-L-25 — a deleted work order's files are not listed
- **Rules:** list_attachments R1a [BUG-2200]; PR-1
- **Kind:** bug
- **Expect:** xfail BUG-2200
- **Fails today on:** Then 1 (no error is raised: the files are listed)

**Given**
1. WO1 = wo("WO-1") but deleted.
2. A1 = att("r-1") but ready; link(A1, "work_order", WO1).

**When**
- `la(UG, workspace_id=W1.id, entity_type=ET("work_order"), entity_id=WO1.id, skip=0, limit=100)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("work_order", WO1.id)`.
3. session: clean.

### ATSV-L-26 — an unknown purchase order (no soft delete) is not found, though a link names it
- **Rules:** list_attachments R1a [BUG-2200]; PR-1
- **Kind:** bug
- **Expect:** xfail BUG-2200
- **Fails today on:** Then 1 (no error is raised: the linked file is listed)

**Given**
1. A1 = att("r-1") but ready; link(A1, "purchase_order", MISSING).

**When**
- `la(UG, workspace_id=W1.id, entity_type=ET("purchase_order"), entity_id=MISSING, skip=0, limit=100)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("purchase_order", MISSING)`.
3. session: clean.

### ATSV-L-27 — the default skip is 0
- **Rules:** list_attachments R1 (default `skip=0`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. FL = fill(M1, 3, "ready").

**When**
- `result = la(UG, workspace_id=W1.id, entity_type=ET("machine"), entity_id=M1.id, limit=1000)`

**Then**
1. returns: `len(result.items) == 3`.
2. returns: `ids(result) == {a.id for a in FL}`.

### ATSV-L-19 — scratch passes with any id
- **Rules:** list_attachments R1a (scratch)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = att("s-1") but ready; link(A1, "scratch", 77).

**When**
- `result = la(UG, workspace_id=W1.id, entity_type=ET("scratch"), entity_id=77, skip=0, limit=1000)`

**Then**
1. returns: `ids(result) == {A1.id}`.
2. returns: `result.slot_count == 1`.

### ATSV-L-20 — a private project the caller may not open is not found
- **Rules:** list_attachments R2 [BUG-1870]; PR-2, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (the call raises TypeError: `user_id` does not exist yet)

**Given**
1. P1 = proj("Tender") but private.
2. A1 = att("r-1") but ready; link(A1, "project", P1).

**When**
- `svc.list_attachments(db, workspace_id=W1.id, entity_type=ET("project"), entity_id=P1.id, skip=0, limit=100, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", P1.id)`.
3. session: clean.
4. mock called: `bsu.called is False`.

### ATSV-L-21 — membership of another private project does not open this one
- **Rules:** list_attachments R2 [BUG-1870]; PR-2 (grant held on a different record)
- **Kind:** bug
- **Expect:** xfail BUG-1870
- **Fails today on:** Then 1 (the call raises TypeError: `user_id` does not exist yet)

**Given**
1. P1 = proj("Tender") but private.
2. P2 = proj("Bridge") but private.
3. pmem(P2, UG).
4. A1 = att("r-1") but ready; link(A1, "project", P1).

**When**
- `svc.list_attachments(db, workspace_id=W1.id, entity_type=ET("project"), entity_id=P1.id, skip=0, limit=100, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", P1.id)`.
3. session: clean.

### ATSV-L-22 — an owner role held only in W0 does not open another member's W1 ticket
- **Rules:** list_attachments R2 [BUG-1950]; PR-2, PR-5 (grant held in a different workspace)
- **Kind:** bug
- **Expect:** xfail BUG-1950
- **Fails today on:** Then 1 (the call raises TypeError: `user_id` does not exist yet)

**Given**
1. member(UG, "owner", ws=W0).
2. T1 = ticket("HT-1").
3. A1 = att("r-1") but ready; link(A1, "support_ticket", T1).

**When**
- `svc.list_attachments(db, workspace_id=W1.id, entity_type=ET("support_ticket"), entity_id=T1.id, skip=0, limit=100, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", T1.id)`.
3. session: clean.

### ATSV-L-23 — a project member lists the private project's files
- **Rules:** list_attachments R1, R2; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender") but private.
2. pmem(P1, UG).
3. A1 = att("r-1") but ready; link(A1, "project", P1).

**When**
- `result = la(UG, workspace_id=W1.id, entity_type=ET("project"), entity_id=P1.id, skip=0, limit=1000)`

**Then**
1. returns: `ids(result) == {A1.id}`.
2. returns: `result.slot_count == 1`.

### ATSV-L-24 — the ticket's creator lists its files
- **Rules:** list_attachments R1, R2; PR-2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = ticket("HT-1") but `created_by UG.id`.
2. A1 = att("r-1") but ready; link(A1, "support_ticket", T1).

**When**
- `result = la(UG, workspace_id=W1.id, entity_type=ET("support_ticket"), entity_id=T1.id, skip=0, limit=1000)`

**Then**
1. returns: `ids(result) == {A1.id}`.

## `AttachmentService.get_attachment`

### ATSV-G-01 — a ready attachment is answered with its URLs; neighbours by id are not
- **Rules:** get_attachment R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. AL = att("pid-l") but ready, `file_name "low.jpg"`; link(AL, "machine", M1).
3. A1 = att("pid-1") but ready; link(A1, "machine", M1).
4. AH = att("pid-h") but ready, `file_name "high.jpg"`; link(AH, "machine", M1).

**When**
- `result = ga(UG, workspace_id=W1.id, attachment_id=A1.id)`

**Then**
1. returns: `type(result).__name__ == "AttachmentResponse"`, `result.id == A1.id`.
2. returns: `result.file_name == "photo.jpg"`, `result.upload_status == "ready"`, `result.public_id == "pid-1"`.
3. returns: `result.urls.preview_url == BSU`, `result.urls.download_url == BSU`.
4. returns: `lk(result) == [("machine", M1.id)]`.

### ATSV-G-02 — a pending attachment is answered without URLs
- **Rules:** get_attachment R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1"); link(A1, "machine", M1).

**When**
- `result = ga(UG, workspace_id=W1.id, attachment_id=A1.id)`

**Then**
1. returns: `result.id == A1.id`, `result.upload_status == "pending"`.
2. returns: `result.urls.thumb_url is None`, `result.urls.preview_url is None`, `result.urls.download_url is None`.
3. mock called: `bsu.called is False`.

### ATSV-G-03 — a failed attachment is answered without URLs
- **Rules:** get_attachment R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but failed; link(A1, "machine", M1).

**When**
- `result = ga(UG, workspace_id=W1.id, attachment_id=A1.id)`

**Then**
1. returns: `result.id == A1.id`, `result.upload_status == "failed"`.
2. returns: `result.urls.preview_url is None`.

### ATSV-G-04 — an unknown id is not found
- **Rules:** get_attachment R1a
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `ga(UG, workspace_id=W1.id, attachment_id=MISSING)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(MISSING)`.
3. session: clean.

### ATSV-G-05 — id 0 is not found
- **Rules:** get_attachment R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `ga(UG, workspace_id=W1.id, attachment_id=0)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(0)`.
3. session: clean.

### ATSV-G-06 — a soft-deleted attachment is not found
- **Rules:** get_attachment R1a; HR-4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready, gone; link(A1, "machine", M1).

**When**
- `ga(UG, workspace_id=W1.id, attachment_id=A1.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A1.id)`.
3. session: clean.

### ATSV-G-07 — a W0 attachment is not found
- **Rules:** get_attachment R1a; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = att("pid-0") but W0 att, ready; link(A0, "scratch", 1).

**When**
- `ga(UG, workspace_id=W1.id, attachment_id=A0.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A0.id)`.
3. session: clean.

### ATSV-G-08 — a W2 attachment is not found
- **Rules:** get_attachment R1a; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A2 = att("pid-2") but W2 att, ready; link(A2, "scratch", 1).

**When**
- `ga(UG, workspace_id=W1.id, attachment_id=A2.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A2.id)`.
3. session: clean.

### ATSV-G-09 — a read neither commits nor rolls back; pending changes stay
- **Rules:** get_attachment R3, TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready; link(A1, "machine", M1).
3. pending X.
4. pending edit.

**When**
- spies: `result = ga(UG, workspace_id=W1.id, attachment_id=A1.id)`

**Then**
1. returns: `result.id == A1.id`.
2. mock called: `cm.called is False`, `rb.called is False`.
3. session: `F9 in db.dirty`, `len(db.dirty) == 1`.
4. count: x_kept.
5. committed: x_gone.

### ATSV-G-10 — a not-found refusal does not roll back the caller's pending edit
- **Rules:** get_attachment R1a, R3, TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. pending edit.

**When**
- spies: `ga(UG, workspace_id=W1.id, attachment_id=MISSING)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. mock called: `rb.called is False`, `cm.called is False`.
3. session: `F9 in db.dirty`, `len(db.dirty) == 1`.

### ATSV-G-11 — an attachment of a private project the caller may not open is not found
- **Rules:** get_attachment R2 [BUG-2091]; PR-3, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: `user_id` does not exist yet)

**Given**
1. P1 = proj("Tender") but private.
2. A1 = att("pid-1") but ready; link(A1, "project", P1).

**When**
- `svc.get_attachment(db, workspace_id=W1.id, attachment_id=A1.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A1.id)`.
3. session: clean.
4. mock called: `bsu.called is False`.

### ATSV-G-12 — membership of another private project does not open this attachment
- **Rules:** get_attachment R2 [BUG-2091]; PR-2 (grant held on a different record)
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: `user_id` does not exist yet)

**Given**
1. P1 = proj("Tender") but private.
2. P2 = proj("Bridge") but private.
3. pmem(P2, UG).
4. A1 = att("pid-1") but ready; link(A1, "project", P1).

**When**
- `svc.get_attachment(db, workspace_id=W1.id, attachment_id=A1.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A1.id)`.
3. session: clean.

### ATSV-G-13 — an attachment whose only link is filed under W2 is not found
- **Rules:** get_attachment R2 [BUG-2091]; PR-3 (only own-workspace links count)
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: `user_id` does not exist yet)

**Given**
1. M2 = mach("Lathe") but W2 mach.
2. A1 = att("pid-1") but ready.
3. `db.add(AttachmentLink(workspace_id=W2.id, attachment_id=A1.id, entity_type="machine", entity_id=M2.id, linked_by=U1.id))`, flush.

**When**
- `svc.get_attachment(db, workspace_id=W1.id, attachment_id=A1.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A1.id)`.
3. session: clean.

### ATSV-G-14 — a link to a project id that exists only as a machine hides the attachment
- **Rules:** get_attachment R2 [BUG-2091]; PR-1, PR-3
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: `user_id` does not exist yet)

**Given**
1. M1 = mach("Lathe") but `id XID(5)`.
2. No project has `id XID(5)`.
3. A1 = att("pid-1") but ready; link(A1, "project", XID(5)).

**When**
- `svc.get_attachment(db, workspace_id=W1.id, attachment_id=A1.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A1.id)`.
3. session: clean.

### ATSV-G-15 — a project member reads the private project's attachment
- **Rules:** get_attachment R1, R2; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender") but private.
2. pmem(P1, UG).
3. A1 = att("pid-1") but ready; link(A1, "project", P1).

**When**
- `result = ga(UG, workspace_id=W1.id, attachment_id=A1.id)`

**Then**
1. returns: `result.id == A1.id`, `lk(result) == [("project", P1.id)]`.

## `AttachmentService.get_pdf_page_image`

### ATSV-PG-01 — a ready PDF answers the page image
- **Rules:** get_pdf_page_image R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready, pdf, `page_count 5`; link(A1, "machine", M1).

**When**
- `result = pg(UG, workspace_id=W1.id, attachment_id=A1.id, page=2)`

**Then**
1. returns: `type(result).__name__ == "AttachmentPdfPageResponse"`.
2. returns: `result.url == BSU`, `result.page == 2`, `result.page_count == 5`.
3. mock called: `bsu.call_count == 1`, `kw(bsu)["public_id"] == "pid-1"`, `kw(bsu)["fmt"] == "jpg"`.
4. mock called: `kw(bsu)["transformation"] == [{"page": 2, "fetch_format": "jpg", "quality": "auto:good", "width": 1600, "crop": "limit", "density": 200}]` (default `width` 1600).

### ATSV-PG-02 — page 0 reaches the caller as the manager's validation error
- **Rules:** get_pdf_page_image R1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready, pdf; link(A1, "machine", M1).

**When**
- `pg(UG, workspace_id=W1.id, attachment_id=A1.id, page=0)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == "Page number must be at least 1."`
3. session: clean.

### ATSV-PG-03 — a pending PDF reaches the caller as "not ready"
- **Rules:** get_pdf_page_image R1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but pdf; link(A1, "machine", M1).

**When**
- `pg(UG, workspace_id=W1.id, attachment_id=A1.id, page=1)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Attachment is not ready."`
3. session: clean.

### ATSV-PG-04 — a ready image reaches the caller as "not a PDF"
- **Rules:** get_pdf_page_image R1
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready; link(A1, "machine", M1).

**When**
- `pg(UG, workspace_id=W1.id, attachment_id=A1.id, page=1)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == "Attachment is not a PDF."`
3. session: clean.

### ATSV-PG-05 — an unknown id is not found
- **Rules:** get_pdf_page_image R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `pg(UG, workspace_id=W1.id, attachment_id=MISSING, page=1)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(MISSING)`.
3. session: clean.

### ATSV-PG-06 — Cloudinary not configured reaches the caller unchanged
- **Rules:** get_pdf_page_image R1
- **Kind:** error
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_CLOUD_NAME "".
2. M1 = mach("Lathe").
3. A1 = att("pid-1") but ready, pdf; link(A1, "machine", M1).

**When**
- `pg(UG, workspace_id=W1.id, attachment_id=A1.id, page=1)`

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. raises: `str(exc.value) == "Cloudinary is not configured."`
3. session: clean.

### ATSV-PG-07 — a page read neither commits nor rolls back; pending changes stay
- **Rules:** get_pdf_page_image R3, TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready, pdf; link(A1, "machine", M1).
3. pending X.
4. pending edit.

**When**
- spies: `result = pg(UG, workspace_id=W1.id, attachment_id=A1.id, page=1)`

**Then**
1. returns: `result.page == 1`.
2. mock called: `cm.called is False`, `rb.called is False`.
3. session: `F9 in db.dirty`, `len(db.dirty) == 1`.
4. count: x_kept.

### ATSV-PG-08 — a private project's PDF the caller may not open is not found
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-3, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: `user_id` does not exist yet)

**Given**
1. P1 = proj("Tender") but private.
2. A1 = att("pid-1") but ready, pdf; link(A1, "project", P1).

**When**
- `svc.get_pdf_page_image(db, workspace_id=W1.id, attachment_id=A1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A1.id)`.
3. session: clean.
4. mock called: `bsu.called is False`.

### ATSV-PG-09 — a hidden PDF answers not found before the page check
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-4
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: `user_id` does not exist yet)

**Given**
1. P1 = proj("Tender") but private.
2. A1 = att("pid-1") but ready, pdf; link(A1, "project", P1).

**When**
- `svc.get_pdf_page_image(db, workspace_id=W1.id, attachment_id=A1.id, page=0, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A1.id)`.
3. session: clean.

### ATSV-PG-10 — membership of another private project does not open this PDF
- **Rules:** get_pdf_page_image R2 [BUG-2091]; PR-2 (grant held on a different record)
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (the call raises TypeError: `user_id` does not exist yet)

**Given**
1. P1 = proj("Tender") but private.
2. P2 = proj("Bridge") but private.
3. pmem(P2, UG).
4. A1 = att("pid-1") but ready, pdf; link(A1, "project", P1).

**When**
- `svc.get_pdf_page_image(db, workspace_id=W1.id, attachment_id=A1.id, page=1, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A1.id)`.
3. session: clean.

### ATSV-PG-11 — a project member gets the private project's PDF page
- **Rules:** get_pdf_page_image R1, R2; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender") but private.
2. pmem(P1, UG).
3. A1 = att("pid-1") but ready, pdf, `page_count 3`; link(A1, "project", P1).

**When**
- `result = pg(UG, workspace_id=W1.id, attachment_id=A1.id, page=3)`

**Then**
1. returns: `result.url == BSU`, `result.page == 3`, `result.page_count == 3`.

### ATSV-PG-12 — an error neither rolls back nor commits; the caller's pending edit stays
- **Rules:** get_pdf_page_image R1, R3, TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready, pdf; link(A1, "machine", M1).
3. pending edit.

**When**
- spies: `pg(UG, workspace_id=W1.id, attachment_id=A1.id, page=0)`

**Then**
1. raises: `AttachmentValidationError`.
2. mock called: `rb.called is False`, `cm.called is False`.
3. session: `F9 in db.dirty`, `len(db.dirty) == 1`.

## `AttachmentService.delete_attachment`

### ATSV-D-01 — delete soft-deletes, commits, and answers the re-read row
- **Rules:** delete_attachment R1, TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready; link(A1, "machine", M1).

**When**
- `result = svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=UG.id)`

**Then**
1. returns: `type(result).__name__ == "AttachmentResponse"`, `result.id == A1.id`.
2. returns: `result.file_name == "photo.jpg"`, `lk(result) == [("machine", M1.id)]`.
3. committed: re-read A1: `is_deleted is True`, `deleted_by == UG.id`, `deleted_at is not None`.
4. committed: ledger_of(A1) has exactly 1 row: `transaction_type == "deleted"`, `performed_by == UG.id`.
5. committed: `events_of(M1) == [("attachment_removed", "Removed photo.jpg", UG.id)]`.
6. committed: links_of(A1) has exactly 1 row.

### ATSV-D-02 — the Cloudinary file of a ready attachment is deleted by its stored id
- **Rules:** delete_attachment R1, R4 (part that holds today and after)
- **Kind:** external
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready; link(A1, "machine", M1).

**When**
- `result = svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=UG.id)`

**Then**
1. returns: `result.id == A1.id`.
2. mock called: `dr.call_count == 1`.
3. mock called: `kw(dr)["public_id"] == "pid-1"`, `kw(dr)["resource_type"] == "image"`, `kw(dr)["delivery_type"] == "authenticated"`.

### ATSV-D-03 — an unknown id: not found, rolled back, other pending changes discarded
- **Rules:** delete_attachment R2, R3, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready; link(A1, "machine", M1).
3. pending X.

**When**
- spies: `svc.delete_attachment(db, workspace_id=W1.id, attachment_id=MISSING, deleted_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(MISSING)`.
3. session: clean.
4. mock called: `rb.call_count >= 1`.
5. count: x_gone.
6. unchanged: unchanged(A1).
7. nothing written.
8. mock called: `dr.called is False`.

### ATSV-D-04 — a W0 attachment is not found; nothing written
- **Rules:** delete_attachment R2; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = att("pid-0") but W0 att, ready; link(A0, "scratch", 1).

**When**
- `svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A0.id, deleted_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A0.id)`.
3. session: clean.
4. unchanged: unchanged(A0).
5. nothing written.
6. mock called: `dr.called is False`.

### ATSV-D-05 — a W2 attachment is not found; nothing written
- **Rules:** delete_attachment R2; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A2 = att("pid-2") but W2 att, ready; link(A2, "scratch", 1).

**When**
- `svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A2.id, deleted_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A2.id)`.
3. session: clean.
4. unchanged: unchanged(A2).
5. nothing written.
6. mock called: `dr.called is False`.

### ATSV-D-06 — an already deleted attachment is not found; nothing written
- **Rules:** delete_attachment R2 [BUG-2097]
- **Kind:** bug
- **Expect:** xfail BUG-2097
- **Fails today on:** Then 1 (no error is raised: the attachment is deleted again)

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready, gone; link(A1, "machine", M1).

**When**
- `svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A1.id)`.
3. session: clean.
4. unchanged: unchanged(A1).
5. nothing written.
6. mock called: `dr.called is False`.

### ATSV-D-07 — a database error rolls back: the attachment stays live
- **Rules:** delete_attachment R3, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready; link(A1, "machine", M1).
3. pending X.

**When**
- `svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=MISSING)`

**Then**
1. raises: `IntegrityError`.
2. session: clean.
3. count: x_gone.
4. re-read A1: `is_deleted is False`, `deleted_by is None`, `upload_status == "ready"`.
5. nothing written.
6. session: `db.execute(text("SELECT 1")).scalar() == 1`.

### ATSV-D-08 — a failing commit leaves the attachment live and ready
- **Rules:** delete_attachment R3, R4, TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready; link(A1, "machine", M1).

**When**
- failing commit: `svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=UG.id)`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read A1: `is_deleted is False`, `upload_status == "ready"`, `public_id == "pid-1"`.
4. nothing written.

### ATSV-D-09 — a failing commit never deletes the Cloudinary file
- **Rules:** delete_attachment R4 [BUG-2202]
- **Kind:** bug
- **Expect:** xfail BUG-2202
- **Fails today on:** Then 3 (the manager deleted the file before the commit)

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready; link(A1, "machine", M1).

**When**
- failing commit: `svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=UG.id)`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. re-read A1: `is_deleted is False`.
3. mock called: `dr.called is False`.

### ATSV-D-10 — on success the commit comes before the Cloudinary delete
- **Rules:** delete_attachment R4 [BUG-2202]
- **Kind:** bug
- **Expect:** xfail BUG-2202
- **Author:** claude
- **Fails today on:** Then 3 (order is ["dr", "commit"])

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready; link(A1, "machine", M1).
3. order log.

**When**
- `result = svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=UG.id)`

**Then**
1. returns: `result.id == A1.id`.
2. mock called: `order.count("dr") == 1`, `"commit" in order`.
3. mock called: `order.index("commit") < order.index("dr")`.

### ATSV-D-11 — a failing re-read after the commit leaves the delete saved
- **Rules:** delete_attachment R3, TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready; link(A1, "machine", M1).

**When**
- failing refresh: `svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=UG.id)`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read A1: `is_deleted is True`, `deleted_by == UG.id`.
3. committed: ledger_of(A1) has exactly 1 row: `transaction_type == "deleted"`.

### ATSV-D-12 — an attachment of a private project the caller may not open is not found
- **Rules:** delete_attachment R1, R2 [BUG-2091]; PR-3, PR-5 (`deleted_by` is the caller)
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the attachment is deleted)

**Given**
1. P1 = proj("Tender") but private.
2. A1 = att("pid-1") but ready; link(A1, "project", P1).

**When**
- `svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A1.id)`.
3. session: clean.
4. unchanged: unchanged(A1).
5. nothing written.
6. mock called: `dr.called is False`.

### ATSV-D-13 — membership of another private project does not open this attachment
- **Rules:** delete_attachment R2 [BUG-2091]; PR-2 (grant held on a different record)
- **Kind:** bug
- **Expect:** xfail BUG-2091
- **Fails today on:** Then 1 (no error is raised: the attachment is deleted)

**Given**
1. P1 = proj("Tender") but private.
2. P2 = proj("Bridge") but private.
3. pmem(P2, UG).
4. A1 = att("pid-1") but ready; link(A1, "project", P1).

**When**
- `svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A1.id)`.
3. session: clean.
4. unchanged: unchanged(A1).
5. nothing written.

### ATSV-D-14 — a project member deletes the private project's attachment
- **Rules:** delete_attachment R1; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = proj("Tender") but private.
2. pmem(P1, UG).
3. A1 = att("pid-1") but ready; link(A1, "project", P1).

**When**
- `result = svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=UG.id)`

**Then**
1. returns: `result.id == A1.id`.
2. committed: re-read A1: `is_deleted is True`, `deleted_by == UG.id`.

### ATSV-D-15 — a pending attachment's file is deleted after the commit
- **Rules:** delete_attachment R4 [BUG-2202] with manager R6 [BUG-2099]
- **Kind:** bug
- **Expect:** xfail BUG-2099
- **Fails today on:** Then 3 (only ready attachments' files are deleted)

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1"); link(A1, "machine", M1).

**When**
- `result = svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=UG.id)`

**Then**
1. returns: `result.id == A1.id`.
2. committed: re-read A1: `is_deleted is True`.
3. mock called: `dr.call_count == 1`, `kw(dr)["public_id"] == "pid-1"`.

### ATSV-D-16 — a failed attachment's file is deleted after the commit
- **Rules:** delete_attachment R4 [BUG-2202] with manager R6 [BUG-2099]
- **Kind:** bug
- **Expect:** xfail BUG-2099
- **Fails today on:** Then 3 (only ready attachments' files are deleted)

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but failed; link(A1, "machine", M1).

**When**
- `result = svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=UG.id)`

**Then**
1. returns: `result.id == A1.id`.
2. committed: re-read A1: `is_deleted is True`.
3. mock called: `dr.call_count == 1`, `kw(dr)["public_id"] == "pid-1"`.

### ATSV-D-17 — no public_id: the delete is saved and Cloudinary is not called
- **Rules:** delete_attachment R4 (manager R5, R6)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready, `public_id None`; link(A1, "machine", M1).

**When**
- `result = svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=UG.id)`

**Then**
1. returns: `result.id == A1.id`.
2. committed: re-read A1: `is_deleted is True`, `deleted_by == UG.id`.
3. mock called: `dr.called is False`.

### ATSV-D-18 — a Cloudinary delete error is swallowed: the delete is saved and answered
- **Rules:** delete_attachment R4a [BUG-2202] (part that holds today)
- **Kind:** external
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready; link(A1, "machine", M1).
3. dr `side_effect = RuntimeError("down")`.

**When**
- `result = svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=UG.id)`

**Then**
1. returns: `result.id == A1.id`.
2. mock called: `dr.call_count == 1`.
3. committed: re-read A1: `is_deleted is True`, `deleted_by == UG.id`.
4. committed: ledger_of(A1) has exactly 1 row: `transaction_type == "deleted"`.

### ATSV-D-19 — a Cloudinary delete error is logged as a WARNING naming the file
- **Rules:** delete_attachment R4a [BUG-2202] with manager R7 [BUG-2100]
- **Kind:** bug
- **Expect:** xfail BUG-2100
- **Fails today on:** Then 2 (the error is swallowed with no log)

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready; link(A1, "machine", M1).
3. dr `side_effect = RuntimeError("down")`.
4. warnings.

**When**
- `result = svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=UG.id)`

**Then**
1. returns: `result.id == A1.id`.
2. warnings: `warned("pid-1") is True`.

### ATSV-D-20 — the file is deleted even when the re-read after the commit fails
- **Rules:** delete_attachment R4a [BUG-2202], R3, TC5
- **Kind:** external
- **Expect:** pass

**Given**
1. M1 = mach("Lathe").
2. A1 = att("pid-1") but ready; link(A1, "machine", M1).

**When**
- failing refresh after commit: `svc.delete_attachment(db, workspace_id=W1.id, attachment_id=A1.id, deleted_by=UG.id)`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `dr.call_count == 1`, `kw(dr)["public_id"] == "pid-1"`.
3. committed: re-read A1: `is_deleted is True`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| sign_upload R2, list_attachments R1a [BUG-2203] | `POST /attachments/sign`, `GET /attachments/` (integration) | `AttachmentNotFoundError` answers 404 with its message, not 500 |
| Overview: endpoint error mapping, query bounds | `app/api/v1/endpoints/attachments.py` (integration) | 404 / 400 / 503 / 500 mapping; `entity_id >= 1`, `0 <= skip`, `1 <= limit <= 200`; `page >= 1`, `400 <= width <= 3200` |
| FU-1 (b) | attachments endpoint (integration) | `current_user.id` is passed as `user_id` to list, get and PDF page |

## Spec gaps
None. Gaps 1–3 of Revision 1 are closed by the spec's 2026-11-04 fill-gaps: G1 (BUG-2201 bound ≤ 3, R5), G2 (`destroy_resource` patched on `app.managers.attachment_manager`), G3 (`confirm_upload` R3a → ATSV-CF-21).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `sign_upload` | R1 | ATSV-S-03 |
| | R2 (capacity) | ATSV-S-04 |
| | R2 [BUG-2090] | ATSV-S-09, ATSV-S-10 |
| | R2 [BUG-1870] | ATSV-S-11, ATSV-S-12, ATSV-S-14 |
| | R2 [BUG-1950] | ATSV-S-13 |
| | R2 [BUG-2203] | Deferred |
| | R3, TC1 | ATSV-S-01, ATSV-S-02, ATSV-S-14 |
| | R4 | ATSV-S-05 |
| | R5, TC4 | ATSV-S-07 |
| | R5, TC5 | ATSV-S-08 |
| | R6, TC3 | ATSV-S-06 |
| | Errors (all unchanged) | ATSV-S-03, S-04, S-05, S-06 |
| `confirm_upload` | R1, TC1, TC2 | ATSV-CF-01, ATSV-CF-02, ATSV-CF-20 |
| | Inputs (`performed_by` None) | ATSV-CF-03 |
| | R1 [BUG-2091] | ATSV-CF-18, ATSV-CF-19 |
| | R2 | ATSV-CF-04 |
| | R3 (holds today) | ATSV-CF-05, ATSV-CF-07, ATSV-CF-10 |
| | R3 [BUG-2095] | ATSV-CF-06, ATSV-CF-08, ATSV-CF-09 |
| | R3a [BUG-2095] | ATSV-CF-21 |
| | R3b, TC3 | ATSV-CF-10, ATSV-CF-22 |
| | R4, TC3; Errors row 1 | ATSV-CF-11, ATSV-CF-12, ATSV-CF-13, ATSV-CF-14 |
| | R4 [BUG-2096]; Errors row 3 | ATSV-CF-15 |
| | Errors row 2 | ATSV-CF-05, ATSV-CF-07, ATSV-CF-10 |
| | R5, TC4 | ATSV-CF-16 |
| | R5, TC5 | ATSV-CF-17 |
| `list_attachments` | R1 | ATSV-L-01, L-02, L-03, L-05, L-07 |
| | R1a [BUG-2200] | ATSV-L-12 … ATSV-L-18, ATSV-L-25, ATSV-L-26 |
| | R1 (default `skip`) | ATSV-L-27 |
| | R1a (scratch) | ATSV-L-19 |
| | R1a [BUG-2203] | Deferred |
| | R2 [BUG-1870] | ATSV-L-20, ATSV-L-21 |
| | R2 [BUG-1950] | ATSV-L-22 |
| | R2 (granted) | ATSV-L-23, ATSV-L-24 |
| | R3 | ATSV-L-01, L-02, L-03, L-04 |
| | R3 [BUG-1434] | ATSV-L-08 |
| | R4 | ATSV-L-01, ATSV-L-05, ATSV-L-06 |
| | R5 [BUG-2201] | ATSV-L-11 |
| | R6, TC6 | ATSV-L-09, ATSV-L-10 |
| `get_attachment` | R1 | ATSV-G-01, G-02, G-03 |
| | R1a | ATSV-G-04 … ATSV-G-08 |
| | R2 [BUG-2091] | ATSV-G-11 … ATSV-G-14 |
| | R2 (granted) | ATSV-G-15 |
| | R3, TC6 | ATSV-G-09, ATSV-G-10 |
| `get_pdf_page_image` | R1 | ATSV-PG-01 … ATSV-PG-06 |
| | R2 [BUG-2091] | ATSV-PG-08, ATSV-PG-09, ATSV-PG-10 |
| | R2 (granted) | ATSV-PG-11 |
| | R3, TC6 | ATSV-PG-07, ATSV-PG-12 |
| `delete_attachment` | R1, TC1, TC2 | ATSV-D-01, ATSV-D-02, ATSV-D-14 |
| | R1, R2 [BUG-2091] | ATSV-D-12, ATSV-D-13 |
| | R2 | ATSV-D-03, ATSV-D-04, ATSV-D-05 |
| | R2 [BUG-2097] | ATSV-D-06 |
| | R3, TC3 | ATSV-D-03, ATSV-D-07 |
| | R3, TC4 | ATSV-D-08 |
| | R3, TC5 | ATSV-D-11 |
| | R4 [BUG-2202] | ATSV-D-08 (holds today), ATSV-D-09, ATSV-D-10, ATSV-D-17 |
| | R4 with manager R6 [BUG-2099] | ATSV-D-15, ATSV-D-16 |
| | R4a [BUG-2202] | ATSV-D-18, ATSV-D-20 |
| | R4a with manager R7 [BUG-2100] | ATSV-D-19 |
