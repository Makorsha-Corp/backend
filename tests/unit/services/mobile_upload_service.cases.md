# Test cases — `app/services/mobile_upload_service.py`

> **Spec:** `tests/unit/services/mobile_upload_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-04) — spec fill-gaps G1–G4 closed: request schemas imported from `app.schemas.mobile_upload` (Conventions); TC5 not unit-testable on `cancel_session` and `public_confirm` (no card, as before); `destroy_resource` stays patched on `app.managers.mobile_upload_session_manager` (CN-01, CN-08, CN-09, PS-02, PS-04, PS-05 unchanged); new `public_confirm` R3a (HR-13 commits the session as it stands) → new MUSV-PC-09 (strict xfail BUG-2137).
> **Revision:** 3 (2026-11-05) — verifier findings 1–5 and spec `cancel_session` R3a, `public_sign` R3a: CN-06 and PM-14 now use an event log, so the session's first read must carry `FOR UPDATE` and come before any write or Cloudinary call (`Author: claude`); C-07, PM-04, PS-07 gain an unrelated pending row that must be discarded (refusals roll back, never commit); new PM-19 (BUG-2204: the HR-13 commit takes an unrelated pending row); new PS-09 (re-sign with a failing commit keeps the old file, BUG-2205); new CN-10, PS-10 (a raising delete after the commit is swallowed; the change is saved and answered) and CN-11, PS-11 (that error is logged as a WARNING, BUG-2136).
> **Counts:** 72 cases · 49 expected-to-pass · 23 expected-to-fail (bugs, all strict) · 4 deferred (4 cards `Author: claude`: CN-06, CN-09, PM-14, PS-05)

## Reviewer summary
- **Depth:** full for this service's own decisions: what it commits or rolls back (TC1–TC6), the HR-13 "commit then raise" paths (BUG-2137 on the phone's confirm, BUG-2204 on attach), the delete of the staged file only after the commit (BUG-2205), and the row lock it must ask for (BUG-2139). Pass-through depth for the manager's rules: the PR-1 / PR-2 matrix is in `mobile_upload_session_manager.cases.md`. Here `create_session` and `promote_session` each get a refused card, a deleted / other-workspace card, a grant-held-elsewhere card (member of another private project; owner role only in W0) and a granted card.
- **Per callable:** `create_session` 10 (5 bug) · `get_session` 7 · `cancel_session` 11 (4 bug) · `promote_session` 19 (7 bug) · `get_public_session` 5 · `public_sign` 11 (4 bug) · `public_confirm` 9 (3 bug).
- **Notable design choices:** every test commits its Given rows (commit point), so the service's rollback cannot remove them. "Committed" is checked after a test-level `db.rollback()`. Every refusal checks `session: clean` before any re-read. The expired-session cards tell the reads (no rollback: `S in db.dirty`) from the writes (rolled back: clean) apart. Each HR-13 path has a pass card (the error and message reach the caller, Cloudinary was called as today), a strict xfail on the committed failure state, and a strict xfail for "that commit itself fails" (TC4). BUG-2205 has three forms: the session keeps its file pointer (pass), Cloudinary's delete is not called (xfail), and on success the commit comes before the delete (order log, `Author: claude`). BUG-2139 is one event-log card per locked path: the session's first read must be the locked one, before any write or Cloudinary call. The public `token` field needs 16–512 characters, so the tokens here are longer than the manager cases'.
- **HR-13 vs TC3 (spec `promote_session` R4a, `public_confirm` R3a):** the commit of the failure record takes the whole session, unrelated pending changes included. PC-09 checks this on the BUG-2137 path.
- **Needs a decision:** None (gaps 1–4 closed by the spec's 2026-11-04 fill-gaps).

## Conventions for this module

**IDs.** `MUSV` = `app/services/mobile_upload_service.py` (`MOBS` is the manager's, `MUS` the DAO's). `C` create_session · `GS` get_session · `CN` cancel_session · `PM` promote_session · `GP` get_public_session · `PS` public_sign · `PC` public_confirm.

**Imports.** `from app.services.mobile_upload_service import MobileUploadService, mobile_upload_service, MobileUploadSessionError, MobileUploadSessionNotFoundError, AttachmentConfirmError, AttachmentValidationError, CloudinaryNotConfiguredError`; `from app.managers.attachment_manager import AttachmentNotFoundError, AttachmentLimitError`; `from app.schemas.mobile_upload import MobileUploadSessionCreateRequest, MobileUploadPromoteRequest, MobileUploadPublicSignRequest, MobileUploadPublicConfirmRequest`; models `MobileUploadSession`, `Attachment`, `AttachmentLink`, `Project`, `ProjectMember`, `HelpTicket`, `WorkspaceMember`, `Factory` (`app.models.<module>`). `IntegrityError` (`sqlalchemy.exc`); `event`, `text` (`sqlalchemy`); `patch` (`unittest.mock`); `SimpleNamespace`; `hashlib`, `inspect`, `logging`, `uuid`; `datetime`, `timedelta`, `timezone`. Response classes are checked by `type(result).__name__`.

**Fixed values.** `svc` = `mobile_upload_service`. `db` = the real session, first argument; others by keyword. `result` = what the When returns. The session never autoflushes. MISSING = `999999999`. NOW = `datetime(2026, 3, 5, 12, 0, 0)`; NOW_UTC = NOW with `tzinfo=timezone.utc`; PAST = NOW_UTC − 1 day; LATER = NOW_UTC + 1 day; T0 = `datetime(2025, 12, 1, 8, 0, 0)`. **H(x)** = `hashlib.sha256(x.encode("utf-8")).hexdigest()`. RAW1 = `"raw-token-one-0001"`, RAW0 = `"raw-token-zero-0000"`, RAW2 = `"raw-token-two-0002"`, RAWX = `"raw-token-unknown-9"`, RAWT = `"fixed-raw-token-000"`. TOKEN = `"0123456789abcdef0123456789abcdef"`. STG = `"development/ws-0/mobile-staging/0/" + "f" * 32`. OLD = `"development/ws-0/mobile-staging/0/" + "e" * 32`. DEST = `"development/ws-" + str(W1.id) + "/" + TOKEN`. **TOO(n)** = `"File too large (" + str(n) + " bytes). Maximum is 10485760 bytes."`. **NF(t, i)** = `t + " " + str(i) + " not found."`. NOTF = `"Upload session not found."`, EXPD = `"Upload session has expired."`, GONE = `"Upload session is no longer available."`, HASF = `"This session already received a file."`.

**Settings and time (every test).** First statement: `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`. `monkeypatch.setattr` on `app.core.config.settings`: `CLOUDINARY_UPLOAD_ENV "development"`, `ENVIRONMENT "development"`, `CLOUDINARY_CLOUD_NAME "demo-cloud"`, `CLOUDINARY_API_KEY "123456"`, `CLOUDINARY_API_SECRET "s3cret"`, `MAX_ATTACHMENTS_PER_ENTITY 25`; a Given line "settings: NAME value" overrides one. `app.managers.mobile_upload_session_manager.utcnow` and `app.dao.mobile_upload_session.utcnow` both return NOW. **fixed uuid** = `patch("app.managers.mobile_upload_session_manager.uuid.uuid4", return_value=uuid.UUID(TOKEN))` (AttachmentManager's ids get TOKEN too). `time.time` of the mobile manager returns `1767225600.9`; `secrets.token_urlsafe` of the mobile manager returns RAWT. All three in every test.

**Cloudinary (every test, never the network).** Each is `patch(<target>, autospec=True)`. On `app.managers.mobile_upload_session_manager`: **gus** `generate_upload_signature` → `"sig-x"`; **gr** `get_resource` → GR = `{"resource_type": "image", "format": "jpg", "bytes": 2048, "version": 1700000000}`; **dr** `destroy_resource` → `{"result": "ok"}`; **rr** `rename_resource` → `{}`; **um** `update_resource_metadata` → `{"result": "ok"}`; **bsdu** `build_signed_delivery_url` → `"https://signed.example/preview"`. On `app.managers.attachment_manager`: **agr** `get_resource` → GRA = `{"resource_type": "image", "format": "jpg", "bytes": 2048, "version": 1700000001, "secure_url": "https://res.example/a.jpg", "width": 800, "height": 600, "asset_id": "a" * 32, "etag": "e" * 32}`; **adr** `destroy_resource` → `{"result": "ok"}`; **ags** `generate_upload_signature` → `"sig-a"`; **absdu** `build_signed_delivery_url` → `"https://signed.example/a"`. A card may set `return_value` / `side_effect`. **kw(m)** = `ba = inspect.signature(m).bind(*m.call_args.args, **m.call_args.kwargs)`, `ba.apply_defaults()`, `dict(ba.arguments)`. **cl_untouched** = each of gus, gr, dr, rr, um, bsdu, agr, adr, ags, absdu has `.called is False`.

**Standing rows** (every test, in this order, each flushed): W0, W1, W2 = `make_workspace(db)` (W0.id < W1.id < W2.id; no `owner_user_id`). U1 = `make_profile(db, name="Ana Rahman")`, U2 = `make_profile(db, name="Bilal Khan")`, UG = `make_profile(db, name="Mia Khan")`; member(U1, "ground-team"), member(U2, "owner"), MG = member(UG, "ground-team"). F0, F1, F9 = `Factory(workspace_id=<W0|W1|W2>.id, name="Factory Zero|One|Nine", abbreviation="F0|F1|F9")`. P1 = proj "Tender". UG is the caller of every desktop card.

**Given rows** (built directly, flushed one at a time in the order written; after "but" every differing column; a line written as code runs as written):
- **member(U, role, status="active", ws=W1)** = `WorkspaceMember(workspace_id=ws.id, user_id=U.id, role=role, status=status)`.
- **proj "N"** = `Project(workspace_id=W1.id, factory_id=F1.id, name="N", description="Main", created_by=U1.id)`; **W2 proj** = `workspace_id W2.id, factory_id F9.id`; **private** = `visibility "invited_only"`; **deleted** = `is_deleted True, deleted_at T0, deleted_by U1.id`. **pmem(P, U)** = `ProjectMember(workspace_id=P.workspace_id, project_id=P.id, user_id=U.id, assigned_by=U1.id)`. **ticket "N"** = `HelpTicket(workspace_id=W1.id, ticket_number="N", title="Printer jam", description="It jams", created_by=U1.id)`.
- **sess** = `MobileUploadSession(workspace_id=W1.id, created_by=UG.id, entity_type="project", entity_id=P1.id, entity_label="Tender", token_hash=H(RAW1), expires_at=LATER, status="waiting")`. **staged** = sess but `public_id STG, asset_folder "Dev/x/Mobile Staging/session-0", resource_type "image", file_name "photo.jpg", mime_type "image/jpeg", file_size 2048`. **uploaded** = staged but `status "uploaded", format "jpg", version 1700000000`. **W0 sess** / **W2 sess** = `workspace_id W0.id, token_hash H(RAW0)` / `workspace_id W2.id, token_hash H(RAW2)`.
- **full(P)** = 25 rows `Attachment(workspace_id=W1.id, file_name="f<i>.jpg", mime_type="image/jpeg", file_size=1, uploaded_by=U1.id, upload_status="ready", public_id="full/<i>")`, i = 1…25, each with `AttachmentLink(workspace_id=W1.id, attachment_id=<it>.id, entity_type="project", entity_id=P.id, linked_by=U1.id)`.
- **CRQ(t, i, label=None)** = `MobileUploadSessionCreateRequest(entity_type=t, entity_id=i, entity_label=label)`. **PRQ** = `MobileUploadPromoteRequest(file_name=None, note="Front")`. **SRQ(tok)** = `MobileUploadPublicSignRequest(token=tok, file_name="scan.jpg", mime_type="image/jpeg", file_size=3000)`. **CFQ(tok)** = `MobileUploadPublicConfirmRequest(token=tok)`.

**Commit point (every test).** After the last Given line the test runs `db.commit()`. Snapshots are taken there. Then, only where a card lists them:
- **pending X** = `X = Factory(workspace_id=W2.id, name="Factory X", abbreviation="FX")`, `db.add(X)`, `db.flush()`; `X_ID = X.id`. **x_gone** / **x_kept** = `db.scalar(text("SELECT count(*) FROM factories WHERE id = :i"), {"i": X_ID})` `== 0` / `== 1`.
- **pending edit** = `F9.name = "Factory Edited"` (not flushed).

**Named checks.**
- `session:` lines check `db` right after the call, before any re-read. **clean** = `not db.new`, `not db.dirty`, `not db.deleted`.
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its snapshot.
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line then re-reads with a fresh query.
- **nothing written** = row counts of `mobile_upload_sessions`, `attachments`, `attachment_links`, `attachment_ledger`, `project_events` (all workspaces) equal their values at the commit point.
- **count(T, cond)** = `db.scalar(text("SELECT count(*) FROM T WHERE cond"))` with the card's values bound. **ledger_types(pid)** = `[r.transaction_type for r in <attachment_ledger rows of the attachment whose public_id is pid, ordered by id>]`.
- `raises: T` = `with pytest.raises(T) as exc:` around the call, no savepoint; `str(exc.value)` is the message.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **failing commit** = `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When, inside `with pytest.raises(RuntimeError) as exc:`.
- **order log** = `order = []`; dr's `side_effect` = a function that appends `"dr"` and returns `{"result": "ok"}`; `real = db.commit`; `patch.object(db, "commit", side_effect=lambda: (order.append("commit"), real())[1])` around the When.
- **recorder** = `stmts = []`; `event.listen(db.connection(), "before_cursor_execute", rec)` appending each statement; removed right after the When. **locked** = `any("mobile_upload_sessions" in s and "FOR UPDATE" in s for s in stmts)`.
- **event log** = `ev = []`; a `before_cursor_execute` listener on `db.connection()` appends `("sql", statement)`; dr, rr, um and agr each get a `side_effect` that appends `("cl", "<name>")` and returns its canned value; removed right after the When. **first_read** = the index in `ev` of the first `("sql", s)` whose `s.lstrip().upper()` starts with `"SELECT"` and contains `"MOBILE_UPLOAD_SESSIONS"`. **acted_before(i)** = `any(k == "cl" or v.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for k, v in ev[:i])`.
- **warnings** = `caplog.set_level(logging.WARNING)` (root logger) before the When; **warned(p)** = `any(r.levelno == logging.WARNING and p in r.getMessage() for r in caplog.records)`.

**xfail cards.** `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call exactly as shown. No card passes `role=`.

**Race simulations.** None.

## `MobileUploadService.create_session`

### MUSV-C-01 — a session is created, committed and answered with the raw token
- **Rules:** create_session R1, TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = svc.create_session(db, workspace=W1, user=UG, payload=CRQ("project", P1.id))`

**Then**
1. returns: `type(result).__name__ == "MobileUploadSessionCreateResponse"`.
2. returns: `result.token == RAWT`, `result.entity_label == "Tender"`, `result.session_id is not None`.
3. committed: the mobile_upload_sessions row with `id == result.session_id` has `workspace_id == W1.id`, `created_by == UG.id`, `entity_type == "project"`, `entity_id == P1.id`.
4. committed: that row has `status == "waiting"`, `entity_label == "Tender"`, `token_hash == H(RAWT)`, `public_id is None`.

### MUSV-C-02 — the client's label reaches the manager trimmed
- **Rules:** create_session R1 (payload passed down)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = svc.create_session(db, workspace=W1, user=UG, payload=CRQ("project", P1.id, "  Front door  "))`

**Then**
1. returns: `result.entity_label == "Front door"`.
2. committed: the row with `id == result.session_id` has `entity_label == "Front door"`.

### MUSV-C-03 — a database error rolls back and discards other pending changes
- **Rules:** create_session R2, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. pending X.

**When**
- spies: `svc.create_session(db, workspace=W1, user=SimpleNamespace(id=MISSING, name="Ghost", is_platform_admin=False), payload=CRQ("project", P1.id))`

**Then**
1. raises: `IntegrityError`.
2. session: clean.
3. mock called: `rb.call_count >= 1`.
4. count: x_gone.
5. nothing written.
6. session: `db.execute(text("SELECT 1")).scalar() == 1`.

### MUSV-C-04 — a failing commit saves no session
- **Rules:** create_session R2, TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- failing commit: `svc.create_session(db, workspace=W1, user=UG, payload=CRQ("project", P1.id))`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. nothing written.

### MUSV-C-05 — a deleted project is refused as not found; nothing written
- **Rules:** create_session R2 [BUG-2130]; PR-1
- **Kind:** bug
- **Expect:** xfail BUG-2130
- **Fails today on:** Then 1 (no error is raised: the session is created)

**Given**
1. P2 = proj "Bridge" but deleted.

**When**
- `svc.create_session(db, workspace=W1, user=UG, payload=CRQ("project", P2.id))`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", P2.id)`.
3. session: clean.
4. nothing written.

### MUSV-C-06 — a W2 project is refused as not found; nothing written
- **Rules:** create_session R2 [BUG-2130]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-2130
- **Fails today on:** Then 1 (no error is raised: the session is created)

**Given**
1. P2 = proj "Bridge" but W2 proj.

**When**
- `svc.create_session(db, workspace=W1, user=UG, payload=CRQ("project", P2.id))`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", P2.id)`.
3. session: clean.
4. nothing written.

### MUSV-C-07 — a private project the caller may not open is refused
- **Rules:** create_session R2 [BUG-2131]; PR-2, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised: the session is created)

**Given**
1. P2 = proj "Bridge" but private.
2. pending X.

**When**
- `svc.create_session(db, workspace=W1, user=UG, payload=CRQ("project", P2.id))`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", P2.id)`.
3. session: clean.
4. nothing written.
5. count: x_gone.

### MUSV-C-08 — membership of another private project does not open this one
- **Rules:** create_session R2 [BUG-2131]; PR-2 (grant held on a different record)
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised: the session is created)

**Given**
1. P2 = proj "Bridge" but private.
2. P3 = proj "Canal" but private.
3. pmem(P3, UG).

**When**
- `svc.create_session(db, workspace=W1, user=UG, payload=CRQ("project", P2.id))`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", P2.id)`.
3. session: clean.
4. nothing written.

### MUSV-C-09 — an owner role held only in W0 does not open another member's W1 ticket
- **Rules:** create_session R2 [BUG-2131]; PR-2, PR-5 (grant held in a different workspace)
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised: the session is created)

**Given**
1. member(UG, "owner", ws=W0).
2. T1 = ticket "HT-1".

**When**
- `svc.create_session(db, workspace=W1, user=UG, payload=CRQ("support_ticket", T1.id))`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", T1.id)`.
3. session: clean.
4. nothing written.

### MUSV-C-10 — a project member opens a session for the private project
- **Rules:** create_session R1; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P2 = proj "Bridge" but private.
2. pmem(P2, UG).

**When**
- `result = svc.create_session(db, workspace=W1, user=UG, payload=CRQ("project", P2.id))`

**Then**
1. returns: `result.entity_label == "Bridge"`.
2. committed: the row with `id == result.session_id` has `created_by == UG.id`, `entity_id == P2.id`.

## `MobileUploadService.get_session`

### MUSV-GS-01 — the caller's own session is answered without a Cloudinary id
- **Rules:** get_session R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = sess.

**When**
- `result = svc.get_session(db, workspace_id=W1.id, user_id=UG.id, session_id=S.id)`

**Then**
1. returns: `type(result).__name__ == "MobileUploadSessionResponse"`.
2. returns: `result.id == S.id`, `result.status == "waiting"`, `result.entity_label == "Tender"`, `result.entity_id == P1.id`.
3. returns: `result.preview_url is None`, `"public_id" not in result.model_dump()`.

### MUSV-GS-02 — an unknown id is not found
- **Rules:** get_session R2
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `svc.get_session(db, workspace_id=W1.id, user_id=UG.id, session_id=MISSING)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == NOTF`.
3. session: clean.

### MUSV-GS-03 — another member's session is not found
- **Rules:** get_session R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = sess but `created_by U1.id`.

**When**
- `svc.get_session(db, workspace_id=W1.id, user_id=UG.id, session_id=S.id)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == NOTF`.
3. session: clean.

### MUSV-GS-04 — the caller's W0 session is not found from W1
- **Rules:** get_session R2; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = sess but W0 sess.

**When**
- `svc.get_session(db, workspace_id=W1.id, user_id=UG.id, session_id=S.id)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == NOTF`.
3. session: clean.

### MUSV-GS-05 — the caller's W2 session is not found from W1
- **Rules:** get_session R2; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = sess but W2 sess.

**When**
- `svc.get_session(db, workspace_id=W1.id, user_id=UG.id, session_id=S.id)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == NOTF`.
3. session: clean.

### MUSV-GS-06 — an expired waiting session: "expired" in memory only, nothing rolled back or saved
- **Rules:** get_session R2 (D6), TC6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = sess but `expires_at PAST`.

**When**
- spies: `svc.get_session(db, workspace_id=W1.id, user_id=UG.id, session_id=S.id)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == EXPD`.
3. mock called: `cm.called is False`, `rb.called is False`.
4. session: `S in db.dirty`, `S.status == "expired"`.
5. committed: re-read S: `status == "waiting"`.

### MUSV-GS-07 — a poll neither commits nor rolls back; pending changes stay
- **Rules:** get_session R2, TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = sess.
2. pending X.
3. pending edit.

**When**
- spies: `result = svc.get_session(db, workspace_id=W1.id, user_id=UG.id, session_id=S.id)`

**Then**
1. returns: `result.id == S.id`.
2. mock called: `cm.called is False`, `rb.called is False`.
3. session: `F9 in db.dirty`, `len(db.dirty) == 1`.
4. count: x_kept.
5. committed: x_gone.

## `MobileUploadService.cancel_session`

### MUSV-CN-01 — an uploaded session is cancelled and committed; its staged file deleted
- **Rules:** cancel_session R3, TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- `result = svc.cancel_session(db, workspace_id=W1.id, user_id=UG.id, session_id=S.id)`

**Then**
1. returns: `type(result).__name__ == "MobileUploadSessionResponse"`, `result.id == S.id`, `result.status == "cancelled"`.
2. mock called: `dr.call_count == 1`, `kw(dr)["public_id"] == STG`.
3. committed: re-read S: `status == "cancelled"`.

### MUSV-CN-02 — a consumed session is answered unchanged; nothing deleted
- **Rules:** cancel_session R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded but `status "consumed"`, `public_id None`.

**When**
- `result = svc.cancel_session(db, workspace_id=W1.id, user_id=UG.id, session_id=S.id)`

**Then**
1. returns: `result.status == "consumed"`.
2. mock called: `dr.called is False`.
3. unchanged: unchanged(S).

### MUSV-CN-03 — an unknown id rolls back and discards pending changes
- **Rules:** cancel_session R2, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. pending X.

**When**
- spies: `svc.cancel_session(db, workspace_id=W1.id, user_id=UG.id, session_id=MISSING)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == NOTF`.
3. session: clean.
4. mock called: `rb.call_count >= 1`, `cm.called is False`.
5. count: x_gone.
6. nothing written.

### MUSV-CN-04 — another member's session is not found and stays as it was
- **Rules:** cancel_session R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = uploaded but `created_by U1.id`.

**When**
- `svc.cancel_session(db, workspace_id=W1.id, user_id=UG.id, session_id=S.id)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == NOTF`.
3. session: clean.
4. unchanged: unchanged(S).
5. mock called: cl_untouched.

### MUSV-CN-05 — an expired waiting session is refused and "expired" is rolled back
- **Rules:** cancel_session R2 (D6)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = sess but `expires_at PAST`.

**When**
- spies: `svc.cancel_session(db, workspace_id=W1.id, user_id=UG.id, session_id=S.id)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == EXPD`.
3. session: clean.
4. mock called: `rb.call_count >= 1`, `cm.called is False`.
5. committed: re-read S: `status == "waiting"`.

### MUSV-CN-06 — cancel's first read of the session is locked, before anything acts
- **Rules:** cancel_session R1 [BUG-2139]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2139
- **Author:** claude
- **Fails today on:** Then 2 (the session is read without `FOR UPDATE`)

**Given**
1. S = uploaded.
2. event log.

**When**
- `result = svc.cancel_session(db, workspace_id=W1.id, user_id=UG.id, session_id=S.id)`

**Then**
1. returns: `result.status == "cancelled"`.
2. statement: `"FOR UPDATE" in ev[first_read][1].upper()`.
3. statement: `acted_before(first_read) is False`.

### MUSV-CN-07 — a failing commit keeps the session uploaded with its file
- **Rules:** cancel_session R3, R4, TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- failing commit: `svc.cancel_session(db, workspace_id=W1.id, user_id=UG.id, session_id=S.id)`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read S: `status == "uploaded"`, `public_id == STG`.
4. nothing written.

### MUSV-CN-08 — a failing commit never deletes the staged file
- **Rules:** cancel_session R3 [BUG-2205]
- **Kind:** bug
- **Expect:** xfail BUG-2205
- **Fails today on:** Then 3 (the manager deleted the file before the commit)

**Given**
1. S = uploaded.

**When**
- failing commit: `svc.cancel_session(db, workspace_id=W1.id, user_id=UG.id, session_id=S.id)`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. re-read S: `public_id == STG`.
3. mock called: `dr.called is False`.

### MUSV-CN-09 — on success the commit comes before the staged file's delete
- **Rules:** cancel_session R3 [BUG-2205]
- **Kind:** bug
- **Expect:** xfail BUG-2205
- **Author:** claude
- **Fails today on:** Then 3 (order is ["dr", "commit"])

**Given**
1. S = uploaded.
2. order log.

**When**
- `result = svc.cancel_session(db, workspace_id=W1.id, user_id=UG.id, session_id=S.id)`

**Then**
1. returns: `result.status == "cancelled"`.
2. mock called: `order.count("dr") == 1`, `"commit" in order`.
3. mock called: `order.index("commit") < order.index("dr")`.

### MUSV-CN-10 — a raising delete after the commit is swallowed; the cancel is saved and answered
- **Rules:** cancel_session R3a [BUG-2205] (part that holds today)
- **Kind:** external
- **Expect:** pass

**Given**
1. S = uploaded.
2. dr `side_effect = RuntimeError("down")`.

**When**
- `result = svc.cancel_session(db, workspace_id=W1.id, user_id=UG.id, session_id=S.id)`

**Then**
1. returns: `result.status == "cancelled"`.
2. mock called: `dr.call_count == 1`.
3. committed: re-read S: `status == "cancelled"`.

### MUSV-CN-11 — that delete error is logged as a WARNING naming the staged file
- **Rules:** cancel_session R3a [BUG-2205] with manager `_destroy_staging_asset` R3 [BUG-2136]
- **Kind:** bug
- **Expect:** xfail BUG-2136
- **Fails today on:** Then 2 (the error is swallowed with no log)

**Given**
1. S = uploaded.
2. dr `side_effect = RuntimeError("down")`.
3. warnings.

**When**
- `result = svc.cancel_session(db, workspace_id=W1.id, user_id=UG.id, session_id=S.id)`

**Then**
1. returns: `result.status == "cancelled"`.
2. warnings: `warned(STG) is True`.

## `MobileUploadService.promote_session`

### MUSV-PM-01 — the phone's file becomes a ready attachment; all committed together
- **Rules:** promote_session R2, TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- `result = svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. returns: `type(result).__name__ == "AttachmentResponse"`.
2. returns: `result.public_id == DEST`, `result.upload_status == "ready"`, `result.file_name == "photo.jpg"`, `result.note == "Front"`.
3. returns: `[(l.entity_type.value, l.entity_id) for l in result.links] == [("project", P1.id)]`.
4. committed: re-read S: `status == "consumed"`, `public_id is None`.
5. committed: the attachments row with `public_id == DEST` has `workspace_id == W1.id`, `upload_status == "ready"`, `uploaded_by == UG.id`, `version == 1700000001`.

### MUSV-PM-02 — ledger rows and the project's activity entry are committed with the caller
- **Rules:** promote_session R2, TC1; PR-5 (caller passed down)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- `result = svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. returns: `result.public_id == DEST`.
2. committed: `ledger_types(DEST) == ["pending", "ready"]`.
3. committed: every attachment_ledger row of that attachment has `performed_by == UG.id`.
4. committed: count(`project_events`, `project_id = P1.id AND event_type = 'attachment_added' AND performed_by = UG.id AND description = 'Attached photo.jpg'`) `== 1`.

### MUSV-PM-03 — the file is moved from the staging id to the server's new id
- **Rules:** promote_session R2 (manager R7)
- **Kind:** external
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- `result = svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. returns: `result.public_id == DEST`.
2. mock called: `rr.call_count == 1`, `kw(rr)["from_public_id"] == STG`, `kw(rr)["to_public_id"] == DEST`.
3. mock called: `kw(rr)["resource_type"] == "image"`, `kw(rr)["delivery_type"] == "authenticated"`.
4. mock called: `agr.call_count == 1`, `kw(agr)["public_id"] == DEST`.

### MUSV-PM-04 — a session with no file yet is refused before any move; nothing written
- **Rules:** promote_session R3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged.
2. pending X.

**When**
- `svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "No file is ready on this session."`
3. session: clean.
4. unchanged: unchanged(S).
5. nothing written.
6. mock called: cl_untouched.
7. count: x_gone.

### MUSV-PM-05 — an oversized staged file is refused before any move
- **Rules:** promote_session R3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded but `file_size 10485761`.

**When**
- `svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == TOO(10485761)`.
3. session: clean.
4. unchanged: unchanged(S).
5. nothing written.
6. mock called: `rr.called is False`.

### MUSV-PM-06 — an unknown session id rolls back and discards pending changes
- **Rules:** promote_session R1, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. pending X.

**When**
- spies: `svc.promote_session(db, workspace=W1, user=UG, session_id=MISSING, payload=PRQ)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == NOTF`.
3. session: clean.
4. mock called: `rb.call_count >= 1`, `cm.called is False`.
5. count: x_gone.
6. nothing written.

### MUSV-PM-07 — another member's session is not found and not moved
- **Rules:** promote_session R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = uploaded but `created_by U1.id`.

**When**
- `svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == NOTF`.
3. session: clean.
4. unchanged: unchanged(S).
5. mock called: cl_untouched.

### MUSV-PM-08 — a failed check of the moved file reaches the caller as the confirm error
- **Rules:** promote_session R4 (part that holds today)
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded.
2. agr `side_effect = RuntimeError("boom")`.

**When**
- `svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Cloudinary verification failed: boom"`.
3. session: clean.
4. mock called: `rr.call_count == 1`, `agr.call_count == 1`.

### MUSV-PM-09 — after a failed check, the moved file's pointer and the failed attachment are committed
- **Rules:** promote_session R4 [BUG-2204]; HR-13
- **Kind:** bug
- **Expect:** xfail BUG-2204
- **Fails today on:** Then 2 (rolled back: the session names the staging id again)

**Given**
1. S = uploaded.
2. agr `side_effect = RuntimeError("boom")`.

**When**
- `svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. raises: `AttachmentConfirmError`.
2. committed: re-read S: `public_id == DEST`, `status == "uploaded"`.
3. committed: the attachments row with `public_id == DEST` has `upload_status == "failed"`, `uploaded_by == UG.id`.
4. committed: `ledger_types(DEST) == ["pending", "failed"]`.
5. committed: count(`attachment_links`, `entity_type = 'project' AND entity_id = P1.id`) `== 1`.

### MUSV-PM-10 — when the commit of that failure record fails, the commit's error reaches the caller
- **Rules:** promote_session R4 [BUG-2204], TC4
- **Kind:** bug
- **Expect:** xfail BUG-2204
- **Fails today on:** Then 1 (the call raises AttachmentConfirmError: no commit is attempted on this path)

**Given**
1. S = uploaded.
2. agr `side_effect = RuntimeError("lookup")`.

**When**
- failing commit: `svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(S).
4. nothing written.

### MUSV-PM-11 — a failed move writes nothing and keeps the session
- **Rules:** promote_session R4 (failed move)
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded.
2. rr `side_effect = RuntimeError("down")`.

**When**
- `svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Cloudinary move failed: down"`.
3. session: clean.
4. unchanged: unchanged(S).
5. nothing written.

### MUSV-PM-12 — a full record rolls back: no attachment, session unchanged
- **Rules:** promote_session R5, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. full(P1).
2. S = uploaded.

**When**
- `svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. raises: `AttachmentLimitError`.
2. raises: `str(exc.value) == "This record already has the maximum of 25 attachments."`
3. session: clean.
4. unchanged: unchanged(S).
5. nothing written.

### MUSV-PM-13 — a failing commit after a good promote keeps the session uploaded
- **Rules:** promote_session R5, TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- failing commit: `svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read S: `status == "uploaded"`, `public_id == STG`.
4. nothing written.

### MUSV-PM-14 — promote's first read of the session is locked, before anything acts
- **Rules:** promote_session R1 [BUG-2139]; HR-10
- **Kind:** bug
- **Expect:** xfail BUG-2139
- **Author:** claude
- **Fails today on:** Then 2 (the session is read without `FOR UPDATE`)

**Given**
1. S = uploaded.
2. event log.

**When**
- `result = svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. statement: `"FOR UPDATE" in ev[first_read][1].upper()`.
3. statement: `acted_before(first_read) is False`.

### MUSV-PM-15 — a private project the caller may not open is refused before the move
- **Rules:** promote_session R2, R3 [BUG-2134]; PR-2, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised: the file is attached)

**Given**
1. P2 = proj "Bridge" but private.
2. S = uploaded but `entity_id P2.id`, `entity_label "Bridge"`.

**When**
- `svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", P2.id)`.
3. session: clean.
4. unchanged: unchanged(S).
5. nothing written.
6. mock called: `rr.called is False`.

### MUSV-PM-16 — membership of another private project does not open this one
- **Rules:** promote_session R3 [BUG-2134]; PR-2 (grant held on a different record)
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised: the file is attached)

**Given**
1. P2 = proj "Bridge" but private.
2. P3 = proj "Canal" but private.
3. pmem(P3, UG).
4. S = uploaded but `entity_id P2.id`, `entity_label "Bridge"`.

**When**
- `svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", P2.id)`.
3. session: clean.
4. unchanged: unchanged(S).
5. nothing written.

### MUSV-PM-17 — a project deleted after the session opened is refused before the move
- **Rules:** promote_session R3 [BUG-2134]; PR-1
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised: the file is attached)

**Given**
1. P2 = proj "Bridge" but deleted.
2. S = uploaded but `entity_id P2.id`, `entity_label "Bridge"`.

**When**
- `svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", P2.id)`.
3. session: clean.
4. unchanged: unchanged(S).
5. mock called: `rr.called is False`.

### MUSV-PM-18 — a project member attaches to the private project
- **Rules:** promote_session R2; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P2 = proj "Bridge" but private.
2. pmem(P2, UG).
3. S = uploaded but `entity_id P2.id`, `entity_label "Bridge"`.

**When**
- `result = svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. returns: `result.upload_status == "ready"`, `result.public_id == DEST`.
2. committed: re-read S: `status == "consumed"`.

### MUSV-PM-19 — the HR-13 commit after a failed check also commits an unrelated pending row
- **Rules:** promote_session R4a [BUG-2204]; HR-13
- **Kind:** bug
- **Expect:** xfail BUG-2204
- **Fails today on:** Then 4 (rolled back: X is discarded)

**Given**
1. S = uploaded.
2. agr `side_effect = RuntimeError("boom")`.
3. pending X.

**When**
- `svc.promote_session(db, workspace=W1, user=UG, session_id=S.id, payload=PRQ)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Cloudinary verification failed: boom"`.
3. session: clean.
4. committed: x_kept.
5. committed: re-read S: `public_id == DEST`.

## `MobileUploadService.get_public_session`

### MUSV-GP-01 — a W2 session is found by its token and answered with three fields only
- **Rules:** get_public_session R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = sess but W2 sess.

**When**
- `result = svc.get_public_session(db, raw_token=RAW2)`

**Then**
1. returns: `type(result).__name__ == "MobileUploadPublicSessionResponse"`.
2. returns: `set(result.model_dump()) == {"status", "entity_label", "expires_at"}`.
3. returns: `result.status == "waiting"`, `result.entity_label == "Tender"`.

### MUSV-GP-02 — an unknown token is not found
- **Rules:** get_public_session R2
- **Kind:** error
- **Expect:** pass

**Given**
1. S = sess.

**When**
- `svc.get_public_session(db, raw_token=RAWX)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == NOTF`.
3. session: clean.

### MUSV-GP-03 — a consumed session is no longer available
- **Rules:** get_public_session R2
- **Kind:** error
- **Expect:** pass

**Given**
1. S = sess but `status "consumed"`.

**When**
- `svc.get_public_session(db, raw_token=RAW1)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == GONE`.
3. session: clean.

### MUSV-GP-04 — an expired session: "expired" in memory only, nothing rolled back or saved
- **Rules:** get_public_session R2 (D6), TC6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = sess but `expires_at PAST`.

**When**
- spies: `svc.get_public_session(db, raw_token=RAW1)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == EXPD`.
3. mock called: `cm.called is False`, `rb.called is False`.
4. session: `S in db.dirty`.
5. committed: re-read S: `status == "waiting"`.

### MUSV-GP-05 — a public read neither commits nor rolls back; pending changes stay
- **Rules:** get_public_session R2, TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = sess.
2. pending edit.

**When**
- spies: `result = svc.get_public_session(db, raw_token=RAW1)`

**Then**
1. returns: `result.status == "waiting"`.
2. mock called: `cm.called is False`, `rb.called is False`.
3. session: `F9 in db.dirty`, `len(db.dirty) == 1`.

## `MobileUploadService.public_sign`

### MUSV-PS-01 — a W2 session is signed in its own workspace and committed
- **Rules:** public_sign R1, R2, TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = sess but W2 sess.

**When**
- `result = svc.public_sign(db, payload=SRQ(RAW2))`

**Then**
1. returns: `type(result).__name__ == "MobileUploadPublicSignResponse"`.
2. returns: `result.public_id == "development/ws-" + str(W2.id) + "/mobile-staging/" + str(S.id) + "/" + TOKEN`.
3. returns: `result.asset_folder == "Dev/" + W2.name + "/Mobile Staging/session-" + str(S.id)`.
4. returns: `result.signature == "sig-x"`, `result.timestamp == 1767225600`.
5. committed: re-read S: `public_id == result.public_id`, `file_name == "scan.jpg"`, `mime_type == "image/jpeg"`, `file_size == 3000`, `resource_type == "image"`, `status == "waiting"`.

### MUSV-PS-02 — a second sign deletes the earlier staged file
- **Rules:** public_sign R2, R3 (part that holds today and after)
- **Kind:** external
- **Expect:** pass

**Given**
1. S = sess but `public_id OLD`, `asset_folder "Dev/x/old"`.

**When**
- `result = svc.public_sign(db, payload=SRQ(RAW1))`

**Then**
1. returns: `result.public_id != OLD`.
2. mock called: `dr.call_count == 1`, `kw(dr)["public_id"] == OLD`.
3. committed: re-read S: `public_id == result.public_id`.

### MUSV-PS-03 — a failure after the flush keeps the session's earlier file pointer
- **Rules:** public_sign R3, R4, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_CLOUD_NAME "".
2. S = sess but `public_id OLD`, `asset_folder "Dev/x/old"`.

**When**
- `svc.public_sign(db, payload=SRQ(RAW1))`

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. raises: `str(exc.value) == "Cloudinary cloud name and API key are required."`
3. session: clean.
4. re-read S: `public_id == OLD`, `asset_folder == "Dev/x/old"`, `file_name is None`.

### MUSV-PS-04 — a failed sign never deletes the earlier staged file
- **Rules:** public_sign R3 [BUG-2205]
- **Kind:** bug
- **Expect:** xfail BUG-2205
- **Fails today on:** Then 3 (the earlier file was deleted inside the manager)

**Given**
1. settings: CLOUDINARY_CLOUD_NAME "".
2. S = sess but `public_id OLD`, `asset_folder "Dev/x/old"`.

**When**
- `svc.public_sign(db, payload=SRQ(RAW1))`

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. re-read S: `public_id == OLD`.
3. mock called: `dr.called is False`.

### MUSV-PS-05 — on success the commit comes before the earlier file's delete
- **Rules:** public_sign R3 [BUG-2205]
- **Kind:** bug
- **Expect:** xfail BUG-2205
- **Author:** claude
- **Fails today on:** Then 3 (order is ["dr", "commit"])

**Given**
1. S = sess but `public_id OLD`, `asset_folder "Dev/x/old"`.
2. order log.

**When**
- `result = svc.public_sign(db, payload=SRQ(RAW1))`

**Then**
1. returns: `result.public_id != OLD`.
2. mock called: `order.count("dr") == 1`, `"commit" in order`.
3. mock called: `order.index("commit") < order.index("dr")`.

### MUSV-PS-06 — an unknown token rolls back and discards pending changes
- **Rules:** public_sign R1, R4, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = sess.
2. pending X.

**When**
- spies: `svc.public_sign(db, payload=SRQ(RAWX))`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == NOTF`.
3. session: clean.
4. mock called: `rb.call_count >= 1`, `cm.called is False`.
5. count: x_gone.
6. unchanged: unchanged(S).

### MUSV-PS-07 — a session that already has a file is refused; nothing changed
- **Rules:** public_sign R2, R4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded.
2. pending X.

**When**
- `svc.public_sign(db, payload=SRQ(RAW1))`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == HASF`.
3. session: clean.
4. unchanged: unchanged(S).
5. mock called: cl_untouched.
6. count: x_gone.

### MUSV-PS-08 — a failing commit saves none of the new staging columns
- **Rules:** public_sign R4, TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = sess.

**When**
- failing commit: `svc.public_sign(db, payload=SRQ(RAW1))`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(S).

### MUSV-PS-09 — a re-sign whose commit fails never deletes the earlier file
- **Rules:** public_sign R3 [BUG-2205], R4, TC4
- **Kind:** bug
- **Expect:** xfail BUG-2205
- **Fails today on:** Then 4 (the manager deleted the earlier file before the commit)

**Given**
1. S = sess but `public_id OLD`, `asset_folder "Dev/x/old"`.

**When**
- failing commit: `svc.public_sign(db, payload=SRQ(RAW1))`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read S: `public_id == OLD`, `asset_folder == "Dev/x/old"`.
4. mock called: `dr.called is False`.

### MUSV-PS-10 — a raising delete of the earlier file after the commit is swallowed; the sign is saved and answered
- **Rules:** public_sign R3a [BUG-2205] (part that holds today)
- **Kind:** external
- **Expect:** pass

**Given**
1. S = sess but `public_id OLD`, `asset_folder "Dev/x/old"`.
2. dr `side_effect = RuntimeError("down")`.

**When**
- `result = svc.public_sign(db, payload=SRQ(RAW1))`

**Then**
1. returns: `result.public_id != OLD`, `result.signature == "sig-x"`.
2. mock called: `dr.call_count == 1`.
3. committed: re-read S: `public_id == result.public_id`, `file_name == "scan.jpg"`.

### MUSV-PS-11 — that delete error is logged as a WARNING naming the earlier file
- **Rules:** public_sign R3a [BUG-2205] with manager `_destroy_staging_asset` R3 [BUG-2136]
- **Kind:** bug
- **Expect:** xfail BUG-2136
- **Fails today on:** Then 2 (the error is swallowed with no log)

**Given**
1. S = sess but `public_id OLD`, `asset_folder "Dev/x/old"`.
2. dr `side_effect = RuntimeError("down")`.
3. warnings.

**When**
- `result = svc.public_sign(db, payload=SRQ(RAW1))`

**Then**
1. returns: `result.public_id != OLD`.
2. warnings: `warned(OLD) is True`.

## `MobileUploadService.public_confirm`

### MUSV-PC-01 — a verified file makes the session uploaded, committed
- **Rules:** public_confirm R1, R2, TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = staged.

**When**
- `result = svc.public_confirm(db, payload=CFQ(RAW1))`

**Then**
1. returns: `type(result).__name__ == "MobileUploadPublicSessionResponse"`, `result.status == "uploaded"`.
2. mock called: `gr.call_count == 1`, `kw(gr)["public_id"] == STG`.
3. committed: re-read S: `status == "uploaded"`, `format == "jpg"`, `version == 1700000000`, `file_size == 2048`.

### MUSV-PC-02 — an oversized phone file reaches the caller as the confirm error
- **Rules:** public_confirm R3 (part that holds today)
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged.
2. gr `return_value` = GR but `"bytes": 10485761`.

**When**
- `svc.public_confirm(db, payload=CFQ(RAW1))`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == TOO(10485761)`.
3. session: clean.
4. mock called: `dr.call_count == 1`, `kw(dr)["public_id"] == STG`.

### MUSV-PC-03 — the cleared session of an oversized file is committed, then the error returned
- **Rules:** public_confirm R3 [BUG-2137]; HR-13
- **Kind:** bug
- **Expect:** xfail BUG-2137
- **Fails today on:** Then 2 (rolled back: the session still names the deleted file)

**Given**
1. S = staged.
2. gr `return_value` = GR but `"bytes": 10485761`.

**When**
- `svc.public_confirm(db, payload=CFQ(RAW1))`

**Then**
1. raises: `AttachmentConfirmError`.
2. committed: re-read S: `public_id is None`, `asset_folder is None`.
3. committed: re-read S: `status == "waiting"`.

### MUSV-PC-04 — when the commit of the cleared session fails, the commit's error reaches the caller
- **Rules:** public_confirm R3 [BUG-2137], TC4
- **Kind:** bug
- **Expect:** xfail BUG-2137
- **Fails today on:** Then 1 (the call raises AttachmentConfirmError: no commit is attempted on this path)

**Given**
1. S = staged.
2. gr `return_value` = GR but `"bytes": 10485761`.

**When**
- failing commit: `svc.public_confirm(db, payload=CFQ(RAW1))`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(S).

### MUSV-PC-05 — a failed lookup changes nothing; nothing saved
- **Rules:** public_confirm R3 (other refusals)
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged.
2. gr `side_effect = RuntimeError("boom")`.

**When**
- `svc.public_confirm(db, payload=CFQ(RAW1))`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Cloudinary verification failed: boom"`.
3. session: clean.
4. unchanged: unchanged(S).
5. mock called: `dr.called is False`.

### MUSV-PC-06 — an already uploaded session is refused, rolled back, pending changes discarded
- **Rules:** public_confirm R4, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded.
2. pending X.

**When**
- spies: `svc.public_confirm(db, payload=CFQ(RAW1))`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == HASF`.
3. session: clean.
4. mock called: `rb.call_count >= 1`, `cm.called is False`.
5. count: x_gone.
6. unchanged: unchanged(S).
7. mock called: `gr.called is False`.

### MUSV-PC-07 — an unknown token is not found
- **Rules:** public_confirm R1, R4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged.

**When**
- `svc.public_confirm(db, payload=CFQ(RAWX))`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == NOTF`.
3. session: clean.
4. unchanged: unchanged(S).

### MUSV-PC-08 — a failing commit after a good confirm keeps the session waiting
- **Rules:** public_confirm R2, TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged.

**When**
- failing commit: `svc.public_confirm(db, payload=CFQ(RAW1))`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read S: `status == "waiting"`, `format is None`.

### MUSV-PC-09 — the cleared session's commit also commits an unrelated pending row
- **Rules:** public_confirm R3a [BUG-2137]; HR-13
- **Kind:** bug
- **Expect:** xfail BUG-2137
- **Fails today on:** Then 4 (rolled back: X is discarded)

**Given**
1. S = staged.
2. gr `return_value` = GR but `"bytes": 10485761`.
3. pending X.

**When**
- `svc.public_confirm(db, payload=CFQ(RAW1))`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == TOO(10485761)`.
3. session: clean.
4. committed: x_kept.
5. committed: re-read S: `public_id is None`, `status == "waiting"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| create_session R2, promote_session R3 [BUG-2203] | `POST /mobile-upload/sessions`, `…/promote` (integration) | `AttachmentNotFoundError` answers 404 with its message, not 500 |
| Overview: endpoint mapping | `app/api/v1/endpoints/mobile_upload.py` (integration) | not-found → 404 "Upload session not found."; session / validation / confirm / limit errors → 400; not configured → 503 |
| Overview: rate limits, request-schema bounds | integration | create 10/min, public 30 or 20/min; `token` 16–512, `file_name` ≤ 255, `note` ≤ 500, `entity_label` ≤ 80 |
| cancel_session R1, promote_session R1 [BUG-2139] (the race itself) | integration (two committed sessions) | a second promote waits, then sees `consumed` |

## Spec gaps
None. Gaps 1–4 of Revision 1 are closed by the spec's 2026-11-04 fill-gaps: G1 (import module, Conventions), G2 (TC5 not unit-testable on `cancel_session` R4 and `public_confirm` R4), G3 (`destroy_resource` patched on `app.managers.mobile_upload_session_manager`), G4 (`promote_session` R4a, `public_confirm` R3a → MUSV-PC-09).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_session` | R1, TC1 | MUSV-C-01, MUSV-C-02, MUSV-C-10 |
| | R2, TC3 | MUSV-C-03 |
| | R2, TC4 | MUSV-C-04 |
| | R2 [BUG-2130] | MUSV-C-05, MUSV-C-06 |
| | R2 [BUG-2131] | MUSV-C-07 (with TC3 pending row), MUSV-C-08, MUSV-C-09 |
| | R2 [BUG-2203] | Deferred |
| `get_session` | R1 | MUSV-GS-01 |
| | R2 | MUSV-GS-02 … MUSV-GS-05 |
| | R2 (D6), TC6 | MUSV-GS-06, MUSV-GS-07 |
| `cancel_session` | R1 | MUSV-CN-04 |
| | R1 [BUG-2139] | MUSV-CN-06 |
| | R2 (D6) | MUSV-CN-03, MUSV-CN-05 |
| | R3, TC1 | MUSV-CN-01, MUSV-CN-02 |
| | R3 [BUG-2205] | MUSV-CN-07 (holds today), MUSV-CN-08, MUSV-CN-09 |
| | R3a [BUG-2205] | MUSV-CN-10 |
| | R3a with manager R3 [BUG-2136] | MUSV-CN-11 |
| | R4, TC3 / TC4 | MUSV-CN-03, MUSV-CN-07 |
| | R4, TC5 | not unit-testable (spec R4) |
| `promote_session` | R1 | MUSV-PM-06, MUSV-PM-07 |
| | R1 [BUG-2139] | MUSV-PM-14 |
| | R2, TC1 | MUSV-PM-01, MUSV-PM-02, MUSV-PM-03, MUSV-PM-18 |
| | R3, TC3 | MUSV-PM-04 (with pending row), MUSV-PM-05 |
| | R3 [BUG-2134] | MUSV-PM-15, MUSV-PM-16, MUSV-PM-17 |
| | R3 [BUG-2203] | Deferred |
| | R4 (holds today) | MUSV-PM-08, MUSV-PM-11 |
| | R4 [BUG-2204] | MUSV-PM-09, MUSV-PM-10 |
| | R4a [BUG-2204] | MUSV-PM-19 |
| | R5, TC3 | MUSV-PM-12 |
| | R5, TC4 | MUSV-PM-13 |
| `get_public_session` | R1 | MUSV-GP-01 |
| | R2 | MUSV-GP-02, MUSV-GP-03 |
| | R2 (D6), TC6 | MUSV-GP-04, MUSV-GP-05 |
| `public_sign` | R1 | MUSV-PS-06 |
| | R2, TC1 | MUSV-PS-01, MUSV-PS-02 |
| | R3 (holds today) | MUSV-PS-02, MUSV-PS-03 |
| | R3 [BUG-2205] | MUSV-PS-04, MUSV-PS-05, MUSV-PS-09 |
| | R3a [BUG-2205] | MUSV-PS-10 |
| | R3a with manager R3 [BUG-2136] | MUSV-PS-11 |
| | R4, TC3 / TC4 | MUSV-PS-03, MUSV-PS-06, MUSV-PS-07 (with pending row), MUSV-PS-08, MUSV-PS-09 |
| `public_confirm` | R1 | MUSV-PC-07 |
| | R2, TC1 | MUSV-PC-01 |
| | R2, TC4 | MUSV-PC-08 |
| | R3 (holds today) | MUSV-PC-02, MUSV-PC-05 |
| | R3 [BUG-2137] | MUSV-PC-03, MUSV-PC-04 |
| | R3a [BUG-2137] | MUSV-PC-09 |
| | R4, TC5 | not unit-testable (spec R4) |
| | R4, TC3 | MUSV-PC-06 |
