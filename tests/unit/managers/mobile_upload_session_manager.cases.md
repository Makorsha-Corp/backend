# Test cases — `app/managers/mobile_upload_session_manager.py`

> **Spec:** `tests/unit/managers/mobile_upload_session_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — spec fill-gaps 2026-11-04 (G1–G5): PR-5 (no `role` parameter; the manager reads the caller's active role and `is_platform_admin` itself) — `role=` dropped from every card, grant cards now pass today, refused cards fail today on the missing refusal; new refused cards for an inactive or suspended privileged membership, privileged rows in W0 / W2 older than the W1 row, and no W1 membership (G3 of the attachment spec: a non-member passes for workspace-wide records); `rename_resource`'s return is not read (canned `{}`); BUG-2135 "."-ending staged name card (G3); BUG-1282 clock named (G4); deleted work order needs only `is_deleted` (G5); `po` now on a real `statuses` row (FK per the attachment spec's parent table). Spec gaps 1–5 closed.
> **Revision:** 3 — executor notes (2026-11-04): PM-27, PM-35, PM-36 Fails-today lines name the IntegrityError raised today after the move (FK on the parent's activity table). No card added or removed.
> **Revision:** 4 — verifier findings 1–4 and spec PR-2 revision (2026-11-04): new C-51 / C-52, PM-69 / PM-70 (a platform admin with no membership is refused a private project and its component; strict xfail BUG-2131 / BUG-2134); new C-53, PM-71 (the workspace owner with a plain role opens another member's ticket, BUG-2103; pass, see summary); PM-19 and every refusal card PM-26 … PM-67 now check `unchanged(S)` (whole row) after the session lines, replacing the `status` / `public_id` re-read (PM-48 and others that had none gained it); every Cloudinary patch is `autospec=True` and `kw(m)` is the bound argument set with defaults, so no card uses `.get(…, default)` (SG-, CF-, DS-, CN-, PM- lines rewritten); new CF-23, PM-68 (a stored `delivery_type "upload"` reaches the lookup and the move: mutants at L345, L450).
> **Revision:** 5 — spec G6 / BUG-2134 (2026-11-04): promote's parent-record 404 (R4) comes after the session-state checks and before size, name, type and limit. New PM-72 (oversized), PM-73 (bad type), PM-74 (record at capacity), each on a hidden private project expecting 404, session row unchanged, Cloudinary untouched; strict xfail BUG-2134.
> **Counts:** 278 cases · 188 expected-to-pass · 90 expected-to-fail (bugs) · 5 deferred

## Reviewer summary
- **Depth:** full. The module moves files in Cloudinary and decides who may attach to a record (OQ-5 / OQ-18, HR-16), so the Parent-record rule and every Cloudinary call get full depth; the pure helpers get one card per rule and boundary.
- **Per callable:** `create_session` 53 (35 bug) · `promote_to_attachment` 74 (39 bug) · `confirm_staging_upload` 23 (1) · `sign_staging_upload` 17 (2) · `_promote_file_name` 14 (5) · `get_for_creator` 12 (1) · `_ensure_active` 11 (2) · `_staging_preview_url` 11 · `resolve_entity_label` 9 (1) · `normalize_public_sign` 9 · `cancel_session` 9 (2) · `_destroy_staging_asset` 7 (1) · `get_by_raw_token` 6 · `_upload_env`/`_is_production` 5 · `build_staging_public_id` 4 · `_naive_utc` 3 (1) · `to_session_response` 3 · `_hash_token`, `build_staging_asset_folder`, `create_session_token` 2 each · `to_create_response`, `to_public_response` 1 each
- **Notable design choices:** every test patches all Cloudinary functions of this module and of `app.managers.attachment_manager` (AttachmentManager is real), so each refusal can assert that none was called (**cl_untouched**). PR-1 / PR-2 are run twice in full: at `create_session` (BUG-2130, BUG-2131) and at `promote_to_attachment` (BUG-2134, before the move, BUG-2133). No method takes a role (spec PR-5): the caller is the existing `user`, and the role comes from UG's W1 membership row, so access cards set that row (role, status) or delete it. Refused cards are strict xfail (today nothing is checked); grant cards pass today and after the fix. The HR-10 lock (BUG-2139) is checked once, on `get_for_creator(for_update=True)`, by a statement recorder; the race itself is deferred. BUG-1282 cards build unsaved sessions with offset times (no database zone involved), except `create_session` R4, which sets the New York zone.
- **BUG-2103 (workspace owner opens every ticket):** C-53 and PM-71 pass today because nothing is checked today (BUG-2131 / BUG-2134), and must keep passing after those fixes; they fail only if the PR-2 fix leaves out the workspace owner, which is BUG-2103. No strict-xfail form exists here: no assertion of the intended behaviour is false today.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `MOBS` = `app/managers/mobile_upload_session_manager.py` (`MUS` is the session DAO's). `N` _naive_utc · `H` _hash_token · `E` _upload_env / _is_production · `PI` build_staging_public_id · `AF` build_staging_asset_folder · `TK` create_session_token · `RL` resolve_entity_label · `C` create_session · `CR` to_create_response · `EA` _ensure_active · `T` get_by_raw_token · `GC` get_for_creator · `PV` _staging_preview_url · `SR` to_session_response · `PB` to_public_response · `NP` normalize_public_sign · `SG` sign_staging_upload · `CF` confirm_staging_upload · `DS` _destroy_staging_asset · `CN` cancel_session · `PF` _promote_file_name · `PM` promote_to_attachment.

**Imports.** The spec's Facts imports; `AttachmentEntityTypeEnum` as `ET` (`app.models.enums`); `AttachmentSignRequest` (`app.schemas.attachment`); `attachment_manager` (`app.managers.attachment_manager`); `hash_refresh_token` (`app.core.security`); models `MobileUploadSession`, `Attachment`, `AttachmentLink`, `Project`, `ProjectComponent`, `ProjectMember`, `ProjectEvent`, `WorkspaceMember`, `Factory`, `Machine`, `WorkOrder`, `WorkOrderType`, `PurchaseOrder`, `HelpTicket` (`app.models.<module>`); `ValidationError` (pydantic); `event`, `text` (sqlalchemy); `MobileUploadSessionStatusEnum` (`app.models.enums`); `hashlib`, `inspect`, `logging`, `os`, `re`, `uuid`; `datetime`, `timedelta`, `timezone`; `patch`.

**Fixed values.** `M` = `mobile_upload_session_manager`. `db` = the real session, first argument; others by keyword. `result` = what the When returns. The session never autoflushes. MISSING = `999999999`. **XID(k)** = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`; "`id XID(k)`" passes `id=XID(k)`. NOW = `datetime(2026, 3, 5, 12, 0, 0)` (naive); NOW_UTC = NOW with `tzinfo=timezone.utc`; PAST = NOW_UTC − 1 day; LATER = NOW_UTC + 1 day; US = `timedelta(microseconds=1)`; T0 = `datetime(2025, 12, 1, 8, 0, 0)`; P6 = `timezone(timedelta(hours=6))`; M5 = `timezone(timedelta(hours=-5))`. **H(x)** = `hashlib.sha256(x.encode("utf-8")).hexdigest()`. RAW1 = `"raw-token-1"`, RAW0 = `"raw-token-0"`, RAW2 = `"raw-token-2"`, RAWT = `"fixed-raw-token"`. TOKEN = `"0123456789abcdef0123456789abcdef"`. STG = `"development/ws-0/mobile-staging/0/" + "f" * 32` (a staged id). OLD = `"development/ws-0/mobile-staging/0/" + "e" * 32`. DEST = `"development/ws-" + str(W1.id) + "/" + TOKEN`. MAXB = `10485760`. **TOO(n)** = `"File too large (" + str(n) + " bytes). Maximum is 10485760 bytes."`. **NF(t, i)** = `t + " " + str(i) + " not found."` (e.g. `NF("project", P1.id)`).

**Settings and time (every test).** First statement: `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))` (a card that says "zone NY" uses `'America/New_York'` instead). `monkeypatch.setattr(settings, …)` on `app.core.config.settings`: `CLOUDINARY_UPLOAD_ENV "development"`, `ENVIRONMENT "development"`, `CLOUDINARY_CLOUD_NAME "demo-cloud"`, `CLOUDINARY_API_KEY "123456"`, `CLOUDINARY_API_SECRET "s3cret"`, `MAX_ATTACHMENTS_PER_ENTITY 25`; a Given line "settings: NAME value" overrides one. `app.managers.mobile_upload_session_manager.utcnow` and `app.dao.mobile_upload_session.utcnow` both return NOW. **fixed uuid** = `patch("app.managers.mobile_upload_session_manager.uuid.uuid4", return_value=uuid.UUID(TOKEN))` (the same `uuid` module: AttachmentManager's ids get TOKEN too). **fixed time** = `time.time` of this module returns `1767225600.9`. **fixed raw** = `secrets.token_urlsafe` of this module returns RAWT. Every test uses fixed uuid, fixed time, fixed raw unless the card says "real uuid" / "real raw".

**Cloudinary (every test, never the network).** Patched on `app.managers.mobile_upload_session_manager`: **gus** `generate_upload_signature` → `"sig-x"`; **gr** `get_resource` → GR = `{"resource_type": "image", "format": "jpg", "bytes": 2048, "version": 1700000000}`; **dr** `destroy_resource` → `{"result": "ok"}`; **rr** `rename_resource` → `{}` (its return is not read); **um** `update_resource_metadata` → `{"result": "ok"}`; **bsdu** `build_signed_delivery_url` → `"https://signed.example/preview"`. Patched on `app.managers.attachment_manager`: **agr** `get_resource` → GRA = `{"resource_type": "image", "format": "jpg", "bytes": 2048, "version": 1700000001, "secure_url": "https://res.example/a.jpg", "width": 800, "height": 600, "asset_id": "a" * 32, "etag": "e" * 32}`; **adr** `destroy_resource`, **ags** `generate_upload_signature`, **absdu** `build_signed_delivery_url` (canned `{"result": "ok"}`, `"sig-a"`, `"https://signed.example/a"`). Every one of these patches is `patch(<target>, autospec=True)`, so a call with a keyword the real function does not have raises `TypeError` as it would for real. A card may set `return_value` / `side_effect`; "real gus" leaves `generate_upload_signature` unpatched. **kw(m)** = the call's arguments by the real parameter names, defaults filled in: `ba = inspect.signature(m).bind(*m.call_args.args, **m.call_args.kwargs)`, `ba.apply_defaults()`, `dict(ba.arguments)`. So `kw(dr)["delivery_type"] == "authenticated"` is exact: it holds when the code passes that value or leaves the parameter at that default, and fails for any other value or a misspelled keyword. Cards never use `.get(…, default)`. **cl_untouched** = each of gus, gr, dr, rr, um, bsdu, agr, adr, ags, absdu has `.called is False`.

**Standing rows** (every test, built in this order, each flushed): W0, W1, W2 = `make_workspace(db)` (W0.id < W1.id < W2.id; no `owner_user_id`). U1 = `make_profile(db, name="Ana Rahman")`, U2 = `make_profile(db, name="Bilal Khan")`, UG = `make_profile(db, name="Mia Khan")`; member(U1, "ground-team"), member(U2, "owner"), MG = member(UG, "ground-team"). UG is the caller of every card; its role is read from MG (active only). F0, F1, F9 = `Factory(workspace_id=<W0|W1|W2>.id, name="Factory Zero|One|Nine", abbreviation="F0|F1|F9")`. WT1 = `WorkOrderType(workspace_id=W1.id, name="Repair")`. P1 = proj "Tender".

**Given rows** (built directly, flushed one at a time in the order written; after "but" every differing column):
- **member(U, role, status="active", ws=W1)** = `WorkspaceMember(workspace_id=ws.id, user_id=U.id, role=role, status=status)`. "UG's W1 membership but X" changes MG and flushes; "`db.delete(MG)`, flush" removes it. **removed** = `status "inactive"`, `left_at T0`. **set_owner(W, U)** = `W.owner_user_id = U.id`, flush.
- **proj "N"** = `Project(workspace_id=W1.id, factory_id=F1.id, name="N", description="Main", created_by=U1.id)`; **W0 proj** / **W2 proj** = `workspace_id W0.id, factory_id F0.id` / `W2.id, F9.id`; **private** = `visibility "invited_only"`; **deleted** = `is_deleted True, deleted_at T0, deleted_by U1.id`. **pmem(P, U)** = `ProjectMember(workspace_id=P.workspace_id, project_id=P.id, user_id=U.id, assigned_by=U1.id)`. **comp(P, "N")** = `ProjectComponent(workspace_id=P.workspace_id, project_id=P.id, name="N")`.
- **machine "N"** = `Machine(workspace_id=W1.id, factory_id=F1.id, name="N")`; deleted = `is_active False, is_deleted True, deleted_at T0, deleted_by U1.id`. **wo "N"** = `WorkOrder(workspace_id=W1.id, work_order_number="N", title="Fix press", factory_id=F1.id, work_order_type_id=WT1.id)`; deleted = `is_deleted True` (PR-1 reads only `is_deleted`). **po "N"** = first ST = `Status(workspace_id=<the po's workspace>.id, name="Draft", comment="Stage")`, flushed, then `PurchaseOrder(workspace_id=W1.id, po_number="N", destination_type="storage", destination_id=MISSING, subtotal=0, total_amount=0, current_status_id=ST.id, created_by=U1.id)`. **ticket "N"** = `HelpTicket(workspace_id=W1.id, ticket_number="N", title="Printer jam", description="It jams", created_by=U1.id)`.
- **sess** = `MobileUploadSession(workspace_id=W1.id, created_by=UG.id, entity_type="project", entity_id=P1.id, entity_label="Tender", token_hash=H(RAW1), expires_at=LATER, status="waiting")`. **staged** = sess but `public_id STG, asset_folder "Dev/x/Mobile Staging/session-0", resource_type "image", file_name "photo.jpg", mime_type "image/jpeg", file_size 2048`. **uploaded** = staged but `status "uploaded", format "jpg", version 1700000000`. "unsaved" = built, never added to `db`.
- **full(P)** = 25 rows `Attachment(workspace_id=W1.id, file_name="f<i>.jpg", mime_type="image/jpeg", file_size=1, uploaded_by=U1.id, upload_status="ready", public_id="full/<i>")`, i = 1…25, each with `AttachmentLink(workspace_id=W1.id, attachment_id=<it>.id, entity_type="project", entity_id=P.id, linked_by=U1.id)`.
- A Given line written as code is run exactly as written, at that place.

**Named checks.**
- `raises: <T>` = `with pytest.raises(<T>) as exc:` around the call; the next `raises:` lines check `exc.value`; `str(exc.value) == …` compares the message. `raises: DataError` = also `with db.begin_nested():` inside.
- `session:` lines check `db` right after the call, before any re-read (`not db.new`, `not db.dirty`, `S in db.dirty`, …).
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its snapshot taken after the last Given line.
- **nothing written** = row counts of `mobile_upload_sessions`, `attachments`, `attachment_links`, `attachment_ledger`, `project_events` (all workspaces) equal their values before the call.
- **count(T, cond)** = `db.scalar(text("SELECT count(*) FROM T WHERE cond"))` with the card's values bound.
- **warnings** = WARNING records of logger `app.managers.mobile_upload_session_manager` (`caplog.set_level(logging.WARNING, logger=…)` before the When).
- **recorder** = `stmts = []`; `event.listen(db.connection(), "before_cursor_execute", rec)` appending each statement; removed right after the When.
- **Rolled back** (commit spy) = `with patch.object(db, "commit", wraps=db.commit) as cm:` around `sp = db.begin_nested()`, the call, `sp.rollback()`; then the Then lines.

**xfail cards.** `pytest.mark.xfail(strict=True, reason="BUG-n")`, `raises` never narrowed. Write the call as shown, `for_update=` included (it does not exist yet). No card passes `role=`.

**Race simulations.** None.

## `_naive_utc`

### MOBS-N-01 — a naive value comes back unchanged
- **Rules:** _naive_utc R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `_naive_utc(NOW)`

**Then**
1. returns: `result == datetime(2026, 3, 5, 12, 0, 0)` and `result.tzinfo is None`.

### MOBS-N-02 — a UTC value keeps its clock time
- **Rules:** _naive_utc R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `_naive_utc(NOW_UTC)`

**Then**
1. returns: `result == datetime(2026, 3, 5, 12, 0, 0)` and `result.tzinfo is None`.

### MOBS-N-03 — a +06:00 value is converted to UTC
- **Rules:** _naive_utc R2 [BUG-1282]
- **Kind:** bug
- **Expect:** xfail BUG-1282
- **Fails today on:** Then 2 (the zone is removed without conversion)

**Given**
1. Nothing beyond the standing rows.

**When**
- `_naive_utc(datetime(2026, 1, 1, 0, 0, 0, tzinfo=P6))`

**Then**
1. returns: `result.tzinfo is None`.
2. returns: `result == datetime(2025, 12, 31, 18, 0, 0)`.

## `MobileUploadSessionManager._hash_token`

### MOBS-H-01 — the token's SHA-256 hex, as the refresh-token hash
- **Rules:** _hash_token R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M._hash_token("Abc-123_x")`

**Then**
1. returns: `result == H("Abc-123_x")`.
2. returns: `result == hash_refresh_token("Abc-123_x")`.
3. returns: `len(result) == 64` and `result == result.lower()`.

### MOBS-H-02 — the empty token is hashed too
- **Rules:** _hash_token R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M._hash_token("")`

**Then**
1. returns: `result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"`.

## `MobileUploadSessionManager._upload_env` / `._is_production`

### MOBS-E-01 — a non-empty upload environment wins over ENVIRONMENT
- **Rules:** _upload_env R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "staging"; ENVIRONMENT "production".

**When**
- `M._upload_env()`

**Then**
1. returns: `result == "staging"`.

### MOBS-E-02 — an empty upload environment falls back to ENVIRONMENT
- **Rules:** _upload_env R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV ""; ENVIRONMENT "qa".

**When**
- `M._upload_env()`

**Then**
1. returns: `result == "qa"`.

### MOBS-E-03 — "production" exactly is production
- **Rules:** _is_production R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "production".

**When**
- `M._is_production()`

**Then**
1. returns: `result is True`.

### MOBS-E-04 — "Production" with a capital is not production
- **Rules:** _is_production R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "Production".

**When**
- `M._is_production()`

**Then**
1. returns: `result is False`.

### MOBS-E-05 — " production" with a leading space is not production
- **Rules:** _is_production R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV " production".

**When**
- `M._is_production()`

**Then**
1. returns: `result is False`.

## `MobileUploadSessionManager.build_staging_public_id`

### MOBS-PI-01 — outside production the id has the environment in front
- **Rules:** build_staging_public_id R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows (fixed uuid).

**When**
- `M.build_staging_public_id(workspace_id=7, session_id=12)`

**Then**
1. returns: `result == "development/ws-7/mobile-staging/12/0123456789abcdef0123456789abcdef"`.

### MOBS-PI-02 — in production the id has no prefix
- **Rules:** build_staging_public_id R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "production".

**When**
- `M.build_staging_public_id(workspace_id=7, session_id=12)`

**Then**
1. returns: `result == "ws-7/mobile-staging/12/0123456789abcdef0123456789abcdef"`.

### MOBS-PI-03 — the environment comes from ENVIRONMENT when the upload one is empty
- **Rules:** build_staging_public_id R2, _upload_env R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV ""; ENVIRONMENT "qa".

**When**
- `M.build_staging_public_id(workspace_id=7, session_id=12)`

**Then**
1. returns: `result == "qa/ws-7/mobile-staging/12/0123456789abcdef0123456789abcdef"`.

### MOBS-PI-04 — each call gives a new 32-character lowercase hex token
- **Rules:** build_staging_public_id R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. real uuid. `first = M.build_staging_public_id(workspace_id=7, session_id=12)`.

**When**
- `M.build_staging_public_id(workspace_id=7, session_id=12)`

**Then**
1. returns: `result != first`.
2. returns: `re.fullmatch(r"development/ws-7/mobile-staging/12/[0-9a-f]{32}", result) is not None`.

## `MobileUploadSessionManager.build_staging_asset_folder`

### MOBS-AF-01 — production folder, the name used as given
- **Rules:** build_staging_asset_folder R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "production".

**When**
- `M.build_staging_asset_folder(workspace_name=" Acme/East ", session_id=12)`

**Then**
1. returns: `result == " Acme/East /Mobile Staging/session-12"`.

### MOBS-AF-02 — any other environment gets "Dev/", whatever its name
- **Rules:** build_staging_asset_folder R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "staging".

**When**
- `M.build_staging_asset_folder(workspace_name="Acme", session_id=12)`

**Then**
1. returns: `result == "Dev/Acme/Mobile Staging/session-12"`.

## `MobileUploadSessionManager.create_session_token`

### MOBS-TK-01 — the raw token is token_urlsafe(32) and the hash is its hash
- **Rules:** create_session_token R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows (fixed raw).

**When**
- `M.create_session_token()`

**Then**
1. returns: `result == ("fixed-raw-token", H("fixed-raw-token"))`.
2. mock called: the patched `token_urlsafe` was called once with `32`.

### MOBS-TK-02 — real tokens are 43 URL-safe characters and differ
- **Rules:** create_session_token R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. real raw. `first = M.create_session_token()`.

**When**
- `M.create_session_token()`

**Then**
1. returns: `re.fullmatch(r"[A-Za-z0-9_-]{43}", result[0]) is not None`.
2. returns: `result[0] != first[0]`.
3. returns: `result[1] == H(result[0])`.

## `MobileUploadSessionManager.resolve_entity_label`

### MOBS-RL-01 — a client label is trimmed
- **Rules:** resolve_entity_label R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.resolve_entity_label(db, workspace=W1, entity_type=ET.project, entity_id=P1.id, entity_label="  Box 7 ")`

**Then**
1. returns: `result == "Box 7"`.

### MOBS-RL-02 — a client label is cut to 80 after trimming
- **Rules:** resolve_entity_label R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.resolve_entity_label(db, workspace=W1, entity_type=ET.project, entity_id=P1.id, entity_label="   " + "a" * 79 + "bc ")`

**Then**
1. returns: `result == "a" * 79 + "b"`.

### MOBS-RL-03 — None uses the record's name
- **Rules:** resolve_entity_label R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.resolve_entity_label(db, workspace=W1, entity_type=ET.project, entity_id=P1.id, entity_label=None)`

**Then**
1. returns: `result == "Tender"`.

### MOBS-RL-04 — an empty label uses the record's name
- **Rules:** resolve_entity_label R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MA = machine "Press 1".

**When**
- `M.resolve_entity_label(db, workspace=W1, entity_type=ET.machine, entity_id=MA.id, entity_label="")`

**Then**
1. returns: `result == "Press 1"`.

### MOBS-RL-05 — a whitespace-only label uses the record's number
- **Rules:** resolve_entity_label R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TK = ticket "HELP-2026-001".

**When**
- `M.resolve_entity_label(db, workspace=W1, entity_type=ET.support_ticket, entity_id=TK.id, entity_label=" \t ")`

**Then**
1. returns: `result == "HELP-2026-001"`.

### MOBS-RL-06 — an unknown record gives "<type>-<id>"
- **Rules:** resolve_entity_label R2
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.resolve_entity_label(db, workspace=W1, entity_type=ET.project, entity_id=MISSING, entity_label=None)`

**Then**
1. returns: `result == "project-999999999"`.

### MOBS-RL-07 — scratch gives "scratch-<id>"
- **Rules:** resolve_entity_label R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.resolve_entity_label(db, workspace=W1, entity_type=ET.scratch, entity_id=777, entity_label=None)`

**Then**
1. returns: `result == "scratch-777"`.

### MOBS-RL-08 — a looked-up name of exactly 80 characters is kept whole
- **Rules:** resolve_entity_label R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. PL = proj with `name "L" * 80`.

**When**
- `M.resolve_entity_label(db, workspace=W1, entity_type=ET.project, entity_id=PL.id, entity_label=None)`

**Then**
1. returns: `result == "L" * 80`.

### MOBS-RL-09 — a looked-up name of 120 characters is cut to 80
- **Rules:** resolve_entity_label R3 [BUG-2132]
- **Kind:** bug
- **Expect:** xfail BUG-2132
- **Fails today on:** Then 1 (the whole name is returned)

**Given**
1. PL = proj with `name "L" * 79 + "M" * 41`.

**When**
- `M.resolve_entity_label(db, workspace=W1, entity_type=ET.project, entity_id=PL.id, entity_label=None)`

**Then**
1. returns: `result == "L" * 79 + "M"`.

## `MobileUploadSessionManager.create_session`

### MOBS-C-01 — the row is written as stated and the raw token returned
- **Rules:** create_session R1, R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows (fixed raw).

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=P1.id, entity_label=None)`

**Then**
1. returns: `result[1] == "fixed-raw-token"`.
2. re-read result[0]: `workspace_id == W1.id`, `created_by == UG.id`, `entity_type == "project"`, `entity_id == P1.id`, `entity_label == "Tender"`.
3. re-read result[0]: `token_hash == H("fixed-raw-token")`, `status == "waiting"`, `delivery_type == "authenticated"`.
4. re-read result[0]: `public_id`, `asset_folder`, `resource_type`, `format`, `version`, `file_name`, `mime_type`, `file_size` are all None.
5. re-read result[0]: `created_at is not None`, `updated_at is not None`.
6. re-read result[0]: `expires_at == NOW_UTC + timedelta(minutes=10)`.
7. count(`mobile_upload_sessions`, `token_hash = 'fixed-raw-token'`) == 0.

### MOBS-C-02 — the stored expiry is a true moment in any database zone
- **Rules:** create_session R4 [BUG-1282]
- **Kind:** bug
- **Expect:** xfail BUG-1282
- **Fails today on:** Then 2 (stored 5 hours late under New York)

**Given**
1. zone NY.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=P1.id, entity_label=None)`

**Then**
1. returns: `result[1] == "fixed-raw-token"`.
2. re-read result[0]: `expires_at == datetime(2026, 3, 5, 12, 10, 0, tzinfo=timezone.utc)`.

### MOBS-C-03 — a client label is stored trimmed
- **Rules:** create_session R1, resolve_entity_label R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=P1.id, entity_label=" Box 7 ")`

**Then**
1. returns: `result[0].id is not None`.
2. re-read result[0]: `entity_label == "Box 7"`.

### MOBS-C-04 — a second session for the same user and record is a new row
- **Rules:** create_session R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. S0 = sess.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=P1.id, entity_label=None)`

**Then**
1. returns: `result[0].id != S0.id`.
2. count(`mobile_upload_sessions`, `created_by = UG.id AND entity_id = P1.id`) == 2.
3. re-read S0: `token_hash == H("raw-token-1")`, `status == "waiting"`.

### MOBS-C-05 — scratch needs no record
- **Rules:** create_session R5 (scratch)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.scratch, entity_id=777, entity_label=None)`

**Then**
1. returns: `result[0].id is not None`.
2. re-read result[0]: `entity_type == "scratch"`, `entity_id == 777`, `entity_label == "scratch-777"`.

### MOBS-C-06 — a 120-character record name no longer fails the write
- **Rules:** create_session (label), resolve_entity_label R3 [BUG-2132]
- **Kind:** bug
- **Expect:** xfail BUG-2132
- **Fails today on:** Then 1 (the call raises DataError at the flush)

**Given**
1. PL = proj with `name "L" * 120`.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PL.id, entity_label=None)`

**Then**
1. returns: `result[0].id is not None`.
2. re-read result[0]: `entity_label == "L" * 80`.

### MOBS-C-07 — create flushes and never commits
- **Rules:** create_session (Side effects)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- Rolled back: `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=P1.id, entity_label=None)`

**Then**
1. mock called: `cm.call_count == 0`.
2. count(`mobile_upload_sessions`, `created_by = UG.id`) == 0 after the rollback.

### MOBS-C-08 — PR-1: an unknown project is refused
- **Rules:** create_session R5 [BUG-2130]
- **Kind:** bug
- **Expect:** xfail BUG-2130
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=MISSING, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == "project 999999999 not found."`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-09 — PR-1: a W0 project (lower workspace id) is refused
- **Rules:** create_session R5 [BUG-2130]
- **Kind:** bug
- **Expect:** xfail BUG-2130
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PX = W0 proj "Zero Job".

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PX.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PX.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-10 — PR-1: a W2 project (higher workspace id) is refused
- **Rules:** create_session R5 [BUG-2130]
- **Kind:** bug
- **Expect:** xfail BUG-2130
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PX = W2 proj "Nine Job".

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PX.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PX.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-11 — PR-1: a soft-deleted project is refused
- **Rules:** create_session R5 [BUG-2130]
- **Kind:** bug
- **Expect:** xfail BUG-2130
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PD = proj "Old Job", deleted.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PD.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PD.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-12 — PR-1: a soft-deleted machine is refused
- **Rules:** create_session R5 [BUG-2130]
- **Kind:** bug
- **Expect:** xfail BUG-2130
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. MD = machine "Press 4", deleted.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.machine, entity_id=MD.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("machine", MD.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-13 — PR-1: a soft-deleted work order is refused
- **Rules:** create_session R5 [BUG-2130]
- **Kind:** bug
- **Expect:** xfail BUG-2130
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. WD = wo "WO-3", deleted.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.work_order, entity_id=WD.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("work_order", WD.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-14 — PR-1: a live component of a deleted project is refused
- **Rules:** create_session R5 [BUG-2130]
- **Kind:** bug
- **Expect:** xfail BUG-2130
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PD = proj "Old Job", deleted.
2. CD = comp(PD, "Frame").

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project_component, entity_id=CD.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project_component", CD.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-15 — PR-1: a W2 purchase order is refused
- **Rules:** create_session R5 [BUG-2130]
- **Kind:** bug
- **Expect:** xfail BUG-2130
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. O9 = po "PO-T-009", but `workspace_id W2.id`.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.purchase_order, entity_id=O9.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("purchase_order", O9.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-16 — PR-1: a W0 help ticket is refused, even to a W1 owner-role member
- **Rules:** create_session R5 [BUG-2130]
- **Kind:** bug
- **Expect:** xfail BUG-2130
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. UG's W1 membership but `role "owner"`.
2. T0X = ticket "HELP-2026-001", but `workspace_id W0.id`.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.support_ticket, entity_id=T0X.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", T0X.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-17 — PR-1: a purchase-order id that only a W1 machine has is refused
- **Rules:** create_session R5 [BUG-2130]
- **Kind:** bug
- **Expect:** xfail BUG-2130
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. MX = machine "Press 7", but `id XID(1)`. No purchase order has id XID(1).

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.purchase_order, entity_id=XID(1), entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("purchase_order", XID(1))`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-18 — PR-1: a component id that only a live W1 project has is refused
- **Rules:** create_session R5 [BUG-2130]
- **Kind:** bug
- **Expect:** xfail BUG-2130
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PY = proj "Yard", but `id XID(2)`. No project component has id XID(2).

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project_component, entity_id=XID(2), entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project_component", XID(2))`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-19 — PR-1 passes: a live W1 machine
- **Rules:** create_session R5 [BUG-2130]
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA = machine "Press 1".

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.machine, entity_id=MA.id, entity_label=None)`

**Then**
1. returns: `result[0].id is not None`.
2. re-read result[0]: `entity_type == "machine"`, `entity_id == MA.id`, `entity_label == "Press 1"`.

### MOBS-C-20 — PR-1 passes: a live component of a live project
- **Rules:** create_session R5 [BUG-2130]
- **Kind:** happy
- **Expect:** pass

**Given**
1. CA = comp(P1, "Frame").

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project_component, entity_id=CA.id, entity_label=None)`

**Then**
1. returns: `result[0].id is not None`.
2. re-read result[0]: `entity_type == "project_component"`, `entity_id == CA.id`, `entity_label == "Frame"`.

### MOBS-C-21 — PR-1 passes: scratch with an id no table has
- **Rules:** create_session R5 [BUG-2130]
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.scratch, entity_id=MISSING, entity_label=None)`

**Then**
1. returns: `result[0].id is not None`.
2. re-read result[0]: `entity_label == "scratch-999999999"`.

### MOBS-C-22 — PR-2 passes: a plain member opens a W1 purchase order
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po "PO-T-001".

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.purchase_order, entity_id=O1.id, entity_label=None)`

**Then**
1. returns: `result[0].id is not None`.
2. re-read result[0]: `entity_label == "PO-T-001"`.

### MOBS-C-23 — PR-2: a plain member is refused a private project
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PV = proj "Tender 2027", private.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PV.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-24 — PR-2: owning W0 does not open a W1 private project
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. set_owner(W0, UG).
2. PV = proj "Tender 2027", private.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PV.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.new`.
4. nothing written.

### MOBS-C-25 — PR-2: owning W2 does not open a W1 private project
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. set_owner(W2, UG).
2. PV = proj "Tender 2027", private.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PV.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.new`.
4. nothing written.

### MOBS-C-26 — PR-2: privileged only in W0 does not open it
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. member(UG, "owner", ws=W0).
2. PV = proj "Tender 2027", private.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PV.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.new`.
4. nothing written.

### MOBS-C-27 — PR-2: privileged only in W2 does not open it
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. member(UG, "ground-team-manager", ws=W2).
2. PV = proj "Tender 2027", private.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PV.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.new`.
4. nothing written.

### MOBS-C-28 — PR-2: membership of other private projects (lower and higher id) does not open it
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PA = proj "Alpha", private. pmem(PA, UG).
2. PV = proj "Tender 2027", private.
3. PB = proj "Beta", private. pmem(PB, UG).

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PV.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.new`.
4. nothing written.

### MOBS-C-29 — PR-2: having created another private project does not open this one
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PA = proj "Alpha", private, but `created_by UG.id`.
2. PV = proj "Tender 2027", private.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PV.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.new`.
4. nothing written.

### MOBS-C-30 — PR-2: a private project with no creator is closed to a plain member
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PV = proj "Tender 2027", private, but `created_by None`.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PV.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.new`.
4. nothing written.

### MOBS-C-31 — PR-2: a suspended W1 owner membership does not open it
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. UG's W1 membership but `role "owner"`, `status "suspended"`.
2. PV = proj "Tender 2027", private.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PV.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.new`.
4. nothing written.

### MOBS-C-32 — PR-2: a component of a private project is closed to a plain member
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PV = proj "Tender 2027", private.
2. CV = comp(PV, "Frame").

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project_component, entity_id=CV.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project_component", CV.id)`.
3. session: `not db.new`.
4. nothing written.

### MOBS-C-33 — PR-2: another member's help ticket is closed to a plain role
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. TK = ticket "HELP-2026-001".

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.support_ticket, entity_id=TK.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", TK.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-34 — PR-2: creating other tickets (lower and higher id) does not open this one
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. TA = ticket "HELP-2026-001", but `created_by UG.id`.
2. TK = ticket "HELP-2026-002".
3. TB = ticket "HELP-2026-003", but `created_by UG.id`.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.support_ticket, entity_id=TK.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", TK.id)`.
3. session: `not db.new`.
4. nothing written.

### MOBS-C-35 — PR-2: a ticket with no creator is closed to a plain role
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. TK = ticket "HELP-2026-001", but `created_by None`.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.support_ticket, entity_id=TK.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", TK.id)`.
3. session: `not db.new`.
4. nothing written.

### MOBS-C-36 — PR-2: a W1 membership role "Owner" with a capital does not open a ticket
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. UG's W1 membership but `role "Owner"`.
2. TK = ticket "HELP-2026-001".

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.support_ticket, entity_id=TK.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", TK.id)`.
3. session: `not db.new`.
4. nothing written.

### MOBS-C-37 — PR-2 grant: the W1 owner opens a private project
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** happy
- **Expect:** pass

**Given**
1. set_owner(W1, UG).
2. PV = proj "Tender 2027", private.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PV.id, entity_label=None)`

**Then**
1. returns: `result[0].id is not None`.
2. re-read result[0]: `entity_id == PV.id`, `entity_label == "Tender 2027"`.

### MOBS-C-38 — PR-2 grant: an active ground-team-manager opens a private project
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** happy
- **Expect:** pass

**Given**
1. UG's W1 membership but `role "ground-team-manager"`.
2. PV = proj "Tender 2027", private.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PV.id, entity_label=None)`

**Then**
1. returns: `result[0].id is not None`.
2. re-read result[0]: `entity_id == PV.id`.

### MOBS-C-39 — PR-2 grant: the creator opens their private project
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** happy
- **Expect:** pass

**Given**
1. PV = proj "Tender 2027", private, but `created_by UG.id`.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PV.id, entity_label=None)`

**Then**
1. returns: `result[0].id is not None`.
2. re-read result[0]: `entity_id == PV.id`.

### MOBS-C-40 — PR-2 grant: a project member opens a component of a private project
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** happy
- **Expect:** pass

**Given**
1. PV = proj "Tender 2027", private. pmem(PV, UG).
2. CV = comp(PV, "Frame").

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project_component, entity_id=CV.id, entity_label=None)`

**Then**
1. returns: `result[0].id is not None`.
2. re-read result[0]: `entity_id == CV.id`, `entity_label == "Frame"`.

### MOBS-C-41 — PR-2 grant: the ticket's creator opens it
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** happy
- **Expect:** pass

**Given**
1. TK = ticket "HELP-2026-001", but `created_by UG.id`.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.support_ticket, entity_id=TK.id, entity_label=None)`

**Then**
1. returns: `result[0].id is not None`.
2. re-read result[0]: `entity_label == "HELP-2026-001"`.

### MOBS-C-42 — PR-2 grant: an active ground-team-manager opens another member's ticket
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** happy
- **Expect:** pass

**Given**
1. UG's W1 membership but `role "ground-team-manager"`.
2. TK = ticket "HELP-2026-001".

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.support_ticket, entity_id=TK.id, entity_label=None)`

**Then**
1. returns: `result[0].id is not None`.
2. re-read result[0]: `entity_id == TK.id`.

### MOBS-C-43 — PR-2 grant: a platform admin opens a ticket with no creator
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UG.is_platform_admin = True`, flush.
2. TK = ticket "HELP-2026-001", but `created_by None`.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.support_ticket, entity_id=TK.id, entity_label=None)`

**Then**
1. returns: `result[0].id is not None`.
2. re-read result[0]: `entity_id == TK.id`.

### MOBS-C-44 — PR-2: a removed (inactive) W1 owner membership does not open a private project
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. UG's W1 membership but `role "owner"`, removed.
2. PV = proj "Tender 2027", private.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PV.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-45 — PR-2: a suspended W1 ground-team-manager membership does not open another member's ticket
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. UG's W1 membership but `role "ground-team-manager"`, `status "suspended"`.
2. TK = ticket "HELP-2026-001".

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.support_ticket, entity_id=TK.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", TK.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-46 — PR-2: a removed (inactive) W1 owner membership does not open another member's ticket
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. UG's W1 membership but `role "owner"`, removed.
2. TK = ticket "HELP-2026-001".

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.support_ticket, entity_id=TK.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", TK.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-47 — PR-2: privileged rows in W0 and W2 older than the W1 row do not open a private project
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. `db.delete(MG)`, flush.
2. member(UG, "owner", ws=W0).
3. member(UG, "ground-team-manager", ws=W2).
4. member(UG, "ground-team") (the W1 row, now the newest).
5. PV = proj "Tender 2027", private.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PV.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-48 — PR-2: an owner role only in W0 does not open another member's W1 ticket
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. member(UG, "owner", ws=W0).
2. TK = ticket "HELP-2026-001".

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.support_ticket, entity_id=TK.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", TK.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-49 — PR-2 passes: a caller with no W1 membership opens a workspace-wide machine
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** happy
- **Expect:** pass

**Given**
1. `db.delete(MG)`, flush.
2. MA = machine "Press 1".

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.machine, entity_id=MA.id, entity_label=None)`

**Then**
1. returns: `result[0].id is not None`.
2. re-read result[0]: `entity_type == "machine"`, `entity_id == MA.id`, `entity_label == "Press 1"`.

### MOBS-C-50 — PR-2: no W1 membership at all: a private project stays closed
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. `db.delete(MG)`, flush.
2. PV = proj "Tender 2027", private.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PV.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-51 — PR-2: a platform admin with no W1 membership is refused a private project
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. `db.delete(MG)`, flush.
2. `UG.is_platform_admin = True`, flush.
3. PV = proj "Tender 2027", private.

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project, entity_id=PV.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-52 — PR-2: a platform admin with no W1 membership is refused a component of a private project
- **Rules:** create_session R6 [BUG-2131]
- **Kind:** bug
- **Expect:** xfail BUG-2131
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. `db.delete(MG)`, flush.
2. `UG.is_platform_admin = True`, flush.
3. PV = proj "Tender 2027", private.
4. CV = comp(PV, "Frame").

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.project_component, entity_id=CV.id, entity_label=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project_component", CV.id)`.
3. session: `not db.new`.
4. nothing written.
5. mock called: cl_untouched.

### MOBS-C-53 — PR-2 grant: the workspace owner with a plain role opens another member's ticket
- **Rules:** create_session R6 [BUG-2131, BUG-2103]
- **Kind:** happy
- **Expect:** pass

**Given**
1. set_owner(W1, UG) (UG's W1 membership stays `role "ground-team"`, active).
2. TK = ticket "HELP-2026-001" (created by U1).

**When**
- `M.create_session(db, workspace=W1, user=UG, entity_type=ET.support_ticket, entity_id=TK.id, entity_label=None)`

**Then**
1. returns: `result[0].id is not None`.
2. re-read result[0]: `entity_type == "support_ticket"`, `entity_id == TK.id`, `created_by == UG.id`.

## `MobileUploadSessionManager.to_create_response`

### MOBS-CR-01 — the create response carries id, token, expiry and label
- **Rules:** to_create_response R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = sess.

**When**
- `M.to_create_response(S, "raw-token-1")`

**Then**
1. returns: `result.session_id == S.id`, `result.token == "raw-token-1"`.
2. returns: `result.expires_at == LATER`, `result.entity_label == "Tender"`.

## `MobileUploadSessionManager._ensure_active`

### MOBS-EA-01 — consumed is no longer available, even before its time
- **Rules:** _ensure_active R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = sess, unsaved, but `status "consumed"`.

**When**
- `M._ensure_active(S)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session is no longer available."`.
3. returns: `S.status == "consumed"`.

### MOBS-EA-02 — cancelled is no longer available
- **Rules:** _ensure_active R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = sess, unsaved, but `status "cancelled"`.

**When**
- `M._ensure_active(S)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session is no longer available."`.
3. returns: `S.status == "cancelled"`.

### MOBS-EA-03 — expired past its time keeps the "no longer available" answer
- **Rules:** _ensure_active R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = sess, unsaved, but `status "expired"`, `expires_at PAST`.

**When**
- `M._ensure_active(S)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session is no longer available."`.
3. returns: `S.status == "expired"`.

### MOBS-EA-04 — waiting exactly at its time is expired
- **Rules:** _ensure_active R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = sess, unsaved, but `expires_at NOW_UTC`.

**When**
- `M._ensure_active(S)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session has expired."`.
3. returns: `S.status == "expired"`.

### MOBS-EA-05 — waiting one microsecond before its time is returned
- **Rules:** _ensure_active R2, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = sess, unsaved, but `expires_at NOW_UTC + US`.

**When**
- `M._ensure_active(S)`

**Then**
1. returns: `result is S`.
2. returns: `S.status == "waiting"`.

### MOBS-EA-06 — uploaded past its time is expired on the phone path
- **Rules:** _ensure_active R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = uploaded, unsaved, but `expires_at PAST`.

**When**
- `M._ensure_active(S)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session has expired."`.
3. returns: `S.status == "expired"`.

### MOBS-EA-07 — a naive expiry is compared as UTC
- **Rules:** _ensure_active R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = sess, unsaved, but `expires_at NOW` (naive).

**When**
- `M._ensure_active(S)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session has expired."`.

### MOBS-EA-08 — +06:00 one second past its true moment is expired
- **Rules:** _ensure_active R3 [BUG-1282]
- **Kind:** bug
- **Expect:** xfail BUG-1282
- **Fails today on:** Then 1 (compared by clock time 17:59:59, not expired)

**Given**
1. S = sess, unsaved, but `expires_at datetime(2026, 3, 5, 17, 59, 59, tzinfo=P6)` (11:59:59 UTC).

**When**
- `M._ensure_active(S)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session has expired."`.

### MOBS-EA-09 — −05:00 one hour ahead of now is still active
- **Rules:** _ensure_active R3 [BUG-1282]
- **Kind:** bug
- **Expect:** xfail BUG-1282
- **Fails today on:** Then 1 (the call raises MobileUploadSessionNotFoundError: compared by clock time 08:00)

**Given**
1. S = sess, unsaved, but `expires_at datetime(2026, 3, 5, 8, 0, 0, tzinfo=M5)` (13:00 UTC).

**When**
- `M._ensure_active(S)`

**Then**
1. returns: `result is S`.
2. returns: `S.status == "waiting"`.

### MOBS-EA-10 — "expired" stays in memory; the stored row still says waiting
- **Rules:** _ensure_active R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = sess, but `expires_at PAST`.

**When**
- `M._ensure_active(S)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. session: `S in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. count(`mobile_upload_sessions`, `id = S.id AND status = 'waiting'`) == 1 (a `text` SELECT, no flush before it).

### MOBS-EA-11 — an active stored row is returned untouched
- **Rules:** _ensure_active R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- `M._ensure_active(S)`

**Then**
1. returns: `result is S`.
2. session: `not db.dirty`.

## `MobileUploadSessionManager.get_by_raw_token`

### MOBS-T-01 — the session of that token is found among others, in any workspace
- **Rules:** get_by_raw_token R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. S0 = sess but `token_hash H(RAW0)`.
2. S9 = sess but `workspace_id W2.id`, `token_hash H(RAW1)`.
3. S2 = sess but `token_hash H(RAW2)`.

**When**
- `M.get_by_raw_token(db, raw_token="raw-token-1")`

**Then**
1. returns: `result is S9`.
2. session: `not db.dirty`.

### MOBS-T-02 — an unknown token is not found
- **Rules:** get_by_raw_token R2
- **Kind:** error
- **Expect:** pass

**Given**
1. S = sess.

**When**
- `M.get_by_raw_token(db, raw_token="raw-token-9")`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session not found."`.

### MOBS-T-03 — the token compares exactly (capitals do not match)
- **Rules:** get_by_raw_token R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = sess.

**When**
- `M.get_by_raw_token(db, raw_token="RAW-TOKEN-1")`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session not found."`.

### MOBS-T-04 — the hash itself is not accepted as a token
- **Rules:** get_by_raw_token R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = sess.

**When**
- `M.get_by_raw_token(db, raw_token=H("raw-token-1"))`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session not found."`.

### MOBS-T-05 — a found cancelled session is no longer available
- **Rules:** get_by_raw_token R3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = sess but `status "cancelled"`.

**When**
- `M.get_by_raw_token(db, raw_token="raw-token-1")`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session is no longer available."`.

### MOBS-T-06 — a found waiting session past its time is expired
- **Rules:** get_by_raw_token R3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = sess but `expires_at PAST`.

**When**
- `M.get_by_raw_token(db, raw_token="raw-token-1")`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session has expired."`.
3. session: `S.status == "expired"`.
4. session: `S in db.dirty`.

## `MobileUploadSessionManager.get_for_creator`

### MOBS-GC-01 — the caller's own session is returned among others
- **Rules:** get_for_creator R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. SA = sess but `token_hash H(RAW0)`.
2. S = sess.
3. SB = sess but `token_hash H(RAW2)`.

**When**
- `M.get_for_creator(db, session_id=S.id, workspace_id=W1.id, user_id=UG.id)`

**Then**
1. returns: `result is S`.
2. session: `not db.dirty`.

### MOBS-GC-02 — a W0 session of the caller is not found from W1
- **Rules:** get_for_creator R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S0 = sess but `workspace_id W0.id`.

**When**
- `M.get_for_creator(db, session_id=S0.id, workspace_id=W1.id, user_id=UG.id)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session not found."`.

### MOBS-GC-03 — a W2 session of the caller is not found from W1
- **Rules:** get_for_creator R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S9 = sess but `workspace_id W2.id`.

**When**
- `M.get_for_creator(db, session_id=S9.id, workspace_id=W1.id, user_id=UG.id)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session not found."`.

### MOBS-GC-04 — another member's session (lower user id) is not found
- **Rules:** get_for_creator R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = sess but `created_by U1.id`.

**When**
- `M.get_for_creator(db, session_id=S.id, workspace_id=W1.id, user_id=UG.id)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session not found."`.

### MOBS-GC-05 — another member's session (higher user id) is not found
- **Rules:** get_for_creator R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `UH = make_profile(db, name="Zed Ali")`; member(UH, "ground-team").
2. S = sess but `created_by UH.id`.

**When**
- `M.get_for_creator(db, session_id=S.id, workspace_id=W1.id, user_id=UG.id)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session not found."`.

### MOBS-GC-06 — an unknown id is not found
- **Rules:** get_for_creator R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = sess.

**When**
- `M.get_for_creator(db, session_id=MISSING, workspace_id=W1.id, user_id=UG.id)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session not found."`.

### MOBS-GC-07 — waiting exactly at its time is expired, in memory only
- **Rules:** get_for_creator R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = sess but `expires_at NOW_UTC`.

**When**
- `M.get_for_creator(db, session_id=S.id, workspace_id=W1.id, user_id=UG.id)`

**Then**
1. raises: `MobileUploadSessionNotFoundError`.
2. raises: `str(exc.value) == "Upload session has expired."`.
3. session: `S in db.dirty`.
4. count(`mobile_upload_sessions`, `id = S.id AND status = 'waiting'`) == 1 (a `text` SELECT, no flush before it).

### MOBS-GC-08 — waiting one microsecond before its time is returned
- **Rules:** get_for_creator R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = sess but `expires_at NOW_UTC + US`.

**When**
- `M.get_for_creator(db, session_id=S.id, workspace_id=W1.id, user_id=UG.id)`

**Then**
1. returns: `result is S`.
2. returns: `S.status == "waiting"`.

### MOBS-GC-09 — uploaded past its time is still returned to the desktop
- **Rules:** get_for_creator R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = uploaded but `expires_at PAST`.

**When**
- `M.get_for_creator(db, session_id=S.id, workspace_id=W1.id, user_id=UG.id)`

**Then**
1. returns: `result is S`.
2. returns: `S.status == "uploaded"`.

### MOBS-GC-10 — consumed and past its time is returned
- **Rules:** get_for_creator R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = sess but `status "consumed"`, `expires_at PAST`.

**When**
- `M.get_for_creator(db, session_id=S.id, workspace_id=W1.id, user_id=UG.id)`

**Then**
1. returns: `result is S`.
2. returns: `S.status == "consumed"`.

### MOBS-GC-11 — cancelled is returned
- **Rules:** get_for_creator R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = sess but `status "cancelled"`.

**When**
- `M.get_for_creator(db, session_id=S.id, workspace_id=W1.id, user_id=UG.id)`

**Then**
1. returns: `result is S`.
2. returns: `S.status == "cancelled"`.

### MOBS-GC-12 — the promote / cancel read locks the row
- **Rules:** get_for_creator R5, cancel_session R6, promote_to_attachment R11 [BUG-2139]
- **Kind:** bug
- **Expect:** xfail BUG-2139
- **Fails today on:** Then 1 (the call raises TypeError: no `for_update` option yet)
- **Author:** claude

**Given**
1. S = uploaded. `db.expire_all()`. recorder.

**When**
- `M.get_for_creator(db, session_id=S.id, workspace_id=W1.id, user_id=UG.id, for_update=True)`

**Then**
1. returns: `result.id == S.id`.
2. statement: some recorded SELECT names `mobile_upload_sessions` and contains `FOR UPDATE`.

## `MobileUploadSessionManager._staging_preview_url`

### MOBS-PV-01 — a staged image gives a signed 400-px preview
- **Rules:** _staging_preview_url R4
- **Kind:** external
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- `M._staging_preview_url(S)`

**Then**
1. returns: `result == "https://signed.example/preview"`.
2. mock called: bsdu once; kw(bsdu) `public_id == STG`, `resource_type == "image"`, `delivery_type == "authenticated"`.
3. mock called: kw(bsdu) `version == 1700000000` and `type(kw(bsdu)["version"]) is int`.
4. mock called: kw(bsdu) `fmt == "jpg"`, `transformation == [{"width": 400, "crop": "limit"}]`.

### MOBS-PV-02 — missing resource and delivery types default to image / authenticated
- **Rules:** _staging_preview_url R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded but `resource_type None`, `delivery_type None`.

**When**
- `M._staging_preview_url(S)`

**Then**
1. returns: `result == "https://signed.example/preview"`.
2. mock called: kw(bsdu) `resource_type == "image"`, `delivery_type == "authenticated"`.

### MOBS-PV-03 — a waiting session has no preview
- **Rules:** _staging_preview_url R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded but `status "waiting"`.

**When**
- `M._staging_preview_url(S)`

**Then**
1. returns: `result is None`.
2. mock called: `bsdu.called is False`.

### MOBS-PV-04 — an empty public_id gives no preview
- **Rules:** _staging_preview_url R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded but `public_id ""`.

**When**
- `M._staging_preview_url(S)`

**Then**
1. returns: `result is None`.
2. mock called: `bsdu.called is False`.

### MOBS-PV-05 — version 0 gives no preview
- **Rules:** _staging_preview_url R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded but `version 0`.

**When**
- `M._staging_preview_url(S)`

**Then**
1. returns: `result is None`.
2. mock called: `bsdu.called is False`.

### MOBS-PV-06 — a missing format gives no preview
- **Rules:** _staging_preview_url R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded but `format None`.

**When**
- `M._staging_preview_url(S)`

**Then**
1. returns: `result is None`.
2. mock called: `bsdu.called is False`.

### MOBS-PV-07 — a PDF gives no preview
- **Rules:** _staging_preview_url R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded but `file_name "scan.pdf"`, `mime_type "application/pdf"`, `format "pdf"`.

**When**
- `M._staging_preview_url(S)`

**Then**
1. returns: `result is None`.
2. mock called: `bsdu.called is False`.

### MOBS-PV-08 — a missing MIME type gives no preview
- **Rules:** _staging_preview_url R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded but `mime_type None`.

**When**
- `M._staging_preview_url(S)`

**Then**
1. returns: `result is None`.

### MOBS-PV-09 — "IMAGE/JPEG" in capitals is an image
- **Rules:** _staging_preview_url R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded but `mime_type "IMAGE/JPEG"`.

**When**
- `M._staging_preview_url(S)`

**Then**
1. returns: `result == "https://signed.example/preview"`.

### MOBS-PV-10 — "not configured" while building gives None
- **Rules:** _staging_preview_url R5
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded. bsdu `side_effect CloudinaryNotConfiguredError("Cloudinary is not configured.")`.

**When**
- `M._staging_preview_url(S)`

**Then**
1. returns: `result is None`.

### MOBS-PV-11 — any other error while building gives None
- **Rules:** _staging_preview_url R5
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded. bsdu `side_effect RuntimeError("boom")`.

**When**
- `M._staging_preview_url(S)`

**Then**
1. returns: `result is None`.

## `MobileUploadSessionManager.to_session_response`

### MOBS-SR-01 — the desktop response carries the row's fields and no Cloudinary id
- **Rules:** to_session_response R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- `M.to_session_response(S)`

**Then**
1. returns: `result.id == S.id`, `result.status == MobileUploadSessionStatusEnum.uploaded`, `result.entity_type == ET.project`.
2. returns: `result.entity_id == P1.id`, `result.entity_label == "Tender"`, `result.expires_at == LATER`.
3. returns: `result.file_name == "photo.jpg"`, `result.mime_type == "image/jpeg"`, `result.file_size == 2048`.
4. returns: `result.preview_url == "https://signed.example/preview"`.
5. returns: `"public_id" not in result.model_dump()` and `STG not in str(result.model_dump())`.

### MOBS-SR-02 — a waiting session has no preview
- **Rules:** to_session_response R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = sess.

**When**
- `M.to_session_response(S)`

**Then**
1. returns: `result.status == MobileUploadSessionStatusEnum.waiting`, `result.preview_url is None`, `result.file_name is None`.

### MOBS-SR-03 — a status outside the enum raises ValueError
- **Rules:** to_session_response (Errors)
- **Kind:** error
- **Expect:** pass

**Given**
1. S = sess, unsaved, but `id 5`, `status "bogus"`.

**When**
- `M.to_session_response(S)`

**Then**
1. raises: `ValueError`.

## `MobileUploadSessionManager.to_public_response`

### MOBS-PB-01 — the phone sees status, label and expiry only
- **Rules:** to_public_response R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- `M.to_public_response(S)`

**Then**
1. returns: `set(result.model_dump()) == {"status", "entity_label", "expires_at"}`.
2. returns: `result.status == MobileUploadSessionStatusEnum.uploaded`, `result.entity_label == "Tender"`, `result.expires_at == LATER`.

## `MobileUploadSessionManager.normalize_public_sign`

### MOBS-NP-01 — the result is the desktop normalizer's for a scratch request
- **Rules:** normalize_public_sign R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `expected = attachment_manager.normalize_upload_request(AttachmentSignRequest(entity_type="scratch", entity_id=1, file_name=" photo.jpg ", mime_type="image/jpeg", file_size=1234))`.

**When**
- `M.normalize_public_sign(file_name=" photo.jpg ", mime_type="image/jpeg", file_size=1234)`

**Then**
1. returns: `result == expected`.
2. returns: `result.file_name == "photo.jpg"`, `result.resource_type == "image"`.

### MOBS-NP-02 — exactly 10 485 760 bytes is accepted
- **Rules:** normalize_public_sign R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.normalize_public_sign(file_name="scan.pdf", mime_type="application/pdf", file_size=10485760)`

**Then**
1. returns: `result.file_name == "scan.pdf"`, `result.resource_type == "image"`.

### MOBS-NP-03 — 10 485 761 bytes is too large
- **Rules:** normalize_public_sign R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.normalize_public_sign(file_name="scan.pdf", mime_type="application/pdf", file_size=10485761)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == "File too large (10485761 bytes). Maximum is 10485760 bytes."`.

### MOBS-NP-04 — a MIME type that does not match the extension is refused
- **Rules:** normalize_public_sign R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.normalize_public_sign(file_name="photo.png", mime_type="image/jpeg", file_size=10)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == "MIME type 'image/jpeg' does not match .png (expected one of: image/png)."`.

### MOBS-NP-05 — an unsupported extension is refused
- **Rules:** normalize_public_sign R1
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.normalize_public_sign(file_name="archive.ZIP", mime_type="application/zip", file_size=10)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == "Unsupported file extension: .zip"`.

### MOBS-NP-06 — size 0 is outside the request schema
- **Rules:** normalize_public_sign R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.normalize_public_sign(file_name="photo.jpg", mime_type="image/jpeg", file_size=0)`

**Then**
1. raises: `ValidationError`.

### MOBS-NP-07 — an empty file name is outside the request schema
- **Rules:** normalize_public_sign R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.normalize_public_sign(file_name="", mime_type="image/jpeg", file_size=10)`

**Then**
1. raises: `ValidationError`.

### MOBS-NP-08 — a 256-character name is outside the schema; 255 is not
- **Rules:** normalize_public_sign R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `ok = M.normalize_public_sign(file_name="a" * 251 + ".jpg", mime_type="image/jpeg", file_size=10)` (255 characters, accepted).

**When**
- `M.normalize_public_sign(file_name="a" * 252 + ".jpg", mime_type="image/jpeg", file_size=10)`

**Then**
1. raises: `ValidationError`.
2. returns: `ok.file_name == "a" * 251 + ".jpg"`.

### MOBS-NP-09 — an empty MIME type is outside the schema
- **Rules:** normalize_public_sign R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `M.normalize_public_sign(file_name="photo.jpg", mime_type="", file_size=10)`

**Then**
1. raises: `ValidationError`.

## `MobileUploadSessionManager.sign_staging_upload`

### MOBS-SG-01 — an accepted request stages a server-minted id on the session
- **Rules:** sign_staging_upload R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = sess.

**When**
- `M.sign_staging_upload(db, session=S, workspace=W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)`

**Then**
1. returns: `result.public_id == "development/ws-" + str(W1.id) + "/mobile-staging/" + str(S.id) + "/" + TOKEN`.
2. re-read S: `public_id == "development/ws-" + str(W1.id) + "/mobile-staging/" + str(S.id) + "/" + TOKEN`.
3. re-read S: `asset_folder == "Dev/" + W1.name + "/Mobile Staging/session-" + str(S.id)`.
4. re-read S: `resource_type == "image"`, `file_name == "photo.jpg"`, `mime_type == "image/jpeg"`, `file_size == 1234`, `status == "waiting"`.
5. mock called: `dr.called is False`, `gr.called is False`, `rr.called is False`.

### MOBS-SG-02 — the response holds every field as stated
- **Rules:** sign_staging_upload R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = sess.

**When**
- `M.sign_staging_upload(db, session=S, workspace=W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)`

**Then**
1. returns: `result.cloud_name == "demo-cloud"`, `result.api_key == "123456"`, `result.timestamp == 1767225600`.
2. returns: `result.asset_folder == "Dev/" + W1.name + "/Mobile Staging/session-" + str(S.id)`, `result.display_name == "photo.jpg"`.
3. returns: `result.type == "authenticated"`, `result.signature == "sig-x"`, `result.resource_type == "image"`.
4. returns: `result.upload_url == "https://api.cloudinary.com/v1_1/demo-cloud/image/upload"`.

### MOBS-SG-03 — the signer receives the response's own values
- **Rules:** sign_staging_upload R7
- **Kind:** external
- **Expect:** pass

**Given**
1. S = sess.

**When**
- `M.sign_staging_upload(db, session=S, workspace=W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)`

**Then**
1. returns: `result.signature == "sig-x"`.
2. mock called: gus once; kw(gus) `public_id == result.public_id`, `asset_folder == result.asset_folder`, `display_name == "photo.jpg"`.
3. mock called: kw(gus) `timestamp == 1767225600`, `kw(gus)["delivery_type"] == "authenticated"`.

### MOBS-SG-04 — a document is staged as raw with a raw upload URL
- **Rules:** sign_staging_upload R4, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = sess.

**When**
- `M.sign_staging_upload(db, session=S, workspace=W1, file_name="notes.docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", file_size=50)`

**Then**
1. returns: `result.resource_type == "raw"`, `result.upload_url == "https://api.cloudinary.com/v1_1/demo-cloud/raw/upload"`.
2. re-read S: `resource_type == "raw"`, `file_name == "notes.docx"`.

### MOBS-SG-05 — the file name is stored sanitized, the MIME type as sent
- **Rules:** sign_staging_upload R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = sess.

**When**
- `M.sign_staging_upload(db, session=S, workspace=W1, file_name="  my/scan.pdf ", mime_type="application/pdf", file_size=77)`

**Then**
1. returns: `result.display_name == "my-scan.pdf"`.
2. re-read S: `file_name == "my-scan.pdf"`, `mime_type == "application/pdf"`, `file_size == 77`, `resource_type == "image"`.

### MOBS-SG-06 — an uploaded session refuses a new sign
- **Rules:** sign_staging_upload R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- `M.sign_staging_upload(db, session=S, workspace=W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "This session already received a file."`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-SG-07 — a consumed session refuses a sign
- **Rules:** sign_staging_upload R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = sess but `status "consumed"`.

**When**
- `M.sign_staging_upload(db, session=S, workspace=W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "This session already received a file."`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.

### MOBS-SG-08 — a cancelled session refuses a sign
- **Rules:** sign_staging_upload R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged but `status "cancelled"`.

**When**
- `M.sign_staging_upload(db, session=S, workspace=W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "This session already received a file."`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. re-read S: `public_id == STG`.

### MOBS-SG-09 — an expired session refuses a sign
- **Rules:** sign_staging_upload R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = sess but `status "expired"`.

**When**
- `M.sign_staging_upload(db, session=S, workspace=W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "This session already received a file."`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.

### MOBS-SG-10 — a re-sign deletes the earlier staged file and replaces its id
- **Rules:** sign_staging_upload R2
- **Kind:** external
- **Expect:** pass

**Given**
1. S = staged but `public_id OLD`, `resource_type "raw"`, `delivery_type "authenticated"`, `file_name "notes.docx"`.

**When**
- `M.sign_staging_upload(db, session=S, workspace=W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)`

**Then**
1. returns: `result.public_id == "development/ws-" + str(W1.id) + "/mobile-staging/" + str(S.id) + "/" + TOKEN`.
2. mock called: dr once; kw(dr) `public_id == OLD`, `resource_type == "raw"`, `kw(dr)["delivery_type"] == "authenticated"`.
3. re-read S: `public_id == "development/ws-" + str(W1.id) + "/mobile-staging/" + str(S.id) + "/" + TOKEN`, `resource_type == "image"`, `file_name == "photo.jpg"`.

### MOBS-SG-11 — a refused request with no earlier file stages nothing
- **Rules:** sign_staging_upload R3, (Errors: invalid file)
- **Kind:** error
- **Expect:** pass

**Given**
1. S = sess.

**When**
- `M.sign_staging_upload(db, session=S, workspace=W1, file_name="photo.png", mime_type="image/jpeg", file_size=10)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == "MIME type 'image/jpeg' does not match .png (expected one of: image/png)."`.
3. mock called: cl_untouched.
4. returns: `S.public_id is None`.

### MOBS-SG-12 — a refused re-sign keeps the earlier file (MIME mismatch)
- **Rules:** sign_staging_upload R3 [BUG-2140]
- **Kind:** bug
- **Expect:** xfail BUG-2140
- **Fails today on:** Then 3 (the earlier file is deleted before validation)

**Given**
1. S = staged but `public_id OLD`, `asset_folder "Dev/x/Mobile Staging/session-0"`.

**When**
- `M.sign_staging_upload(db, session=S, workspace=W1, file_name="notes.docx", mime_type="application/pdf", file_size=10)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value).startswith("MIME type 'application/pdf' does not match .docx")`.
3. mock called: `dr.called is False`.
4. session: `S.public_id == OLD`, `S.asset_folder == "Dev/x/Mobile Staging/session-0"`.
5. mock called: cl_untouched.

### MOBS-SG-13 — a refused re-sign keeps the earlier file (too large)
- **Rules:** sign_staging_upload R3 [BUG-2140]
- **Kind:** bug
- **Expect:** xfail BUG-2140
- **Fails today on:** Then 3 (the earlier file is deleted before validation)

**Given**
1. S = staged but `public_id OLD`.

**When**
- `M.sign_staging_upload(db, session=S, workspace=W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=10485761)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == "File too large (10485761 bytes). Maximum is 10485760 bytes."`.
3. mock called: `dr.called is False`.
4. session: `S.public_id == OLD`.

### MOBS-SG-14 — an empty cloud name refuses after the flush, without signing
- **Rules:** sign_staging_upload R6
- **Kind:** error
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_CLOUD_NAME "".
2. S = sess.

**When**
- `M.sign_staging_upload(db, session=S, workspace=W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)`

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. raises: `str(exc.value) == "Cloudinary cloud name and API key are required."`.
3. mock called: `gus.called is False`.
4. re-read S: `public_id == "development/ws-" + str(W1.id) + "/mobile-staging/" + str(S.id) + "/" + TOKEN`, `file_name == "photo.jpg"`.

### MOBS-SG-15 — an empty API key refuses the same way
- **Rules:** sign_staging_upload R6
- **Kind:** error
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_API_KEY "".
2. S = sess.

**When**
- `M.sign_staging_upload(db, session=S, workspace=W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)`

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. raises: `str(exc.value) == "Cloudinary cloud name and API key are required."`.
3. mock called: `gus.called is False`.

### MOBS-SG-16 — an empty secret raises from the real signer
- **Rules:** sign_staging_upload R6
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. settings: CLOUDINARY_API_SECRET "". real gus.
2. S = sess.

**When**
- `M.sign_staging_upload(db, session=S, workspace=W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)`

**Then**
1. raises: `CloudinaryNotConfiguredError`.

### MOBS-SG-17 — sign flushes and never commits
- **Rules:** sign_staging_upload (Side effects)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = sess.

**When**
- Rolled back: `M.sign_staging_upload(db, session=S, workspace=W1, file_name="photo.jpg", mime_type="image/jpeg", file_size=1234)`

**Then**
1. mock called: `cm.call_count == 0`.
2. re-read S: `public_id is None`.

## `MobileUploadSessionManager.confirm_staging_upload`

### MOBS-CF-01 — a verified file makes the session uploaded
- **Rules:** confirm_staging_upload R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = staged.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. returns: `result is S`.
2. re-read S: `status == "uploaded"`, `format == "jpg"`, `version == 1700000000`, `file_size == 2048`, `mime_type == "image/jpeg"`, `public_id == STG`.
3. mock called: `dr.called is False`.

### MOBS-CF-02 — Cloudinary is asked about the session's own id and types
- **Rules:** confirm_staging_upload R2
- **Kind:** external
- **Expect:** pass

**Given**
1. S = staged but `resource_type "image"`, `delivery_type "authenticated"`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. returns: `result.status == "uploaded"`.
2. mock called: gr once; kw(gr) `public_id == STG`, `kw(gr)["resource_type"] == "image"`, `kw(gr)["delivery_type"] == "authenticated"`.

### MOBS-CF-03 — missing types default to image / authenticated in the lookup
- **Rules:** confirm_staging_upload R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = staged but `resource_type None`, `delivery_type None`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. returns: `result.status == "uploaded"`.
2. mock called: `kw(gr)["resource_type"] == "image"`, `kw(gr)["delivery_type"] == "authenticated"`.

### MOBS-CF-04 — a raw document keeps its stored type and MIME
- **Rules:** confirm_staging_upload R2, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = staged but `resource_type "raw"`, `file_name "notes.docx"`, `mime_type "application/vnd.openxmlformats-officedocument.wordprocessingml.document"`. gr returns `{"resource_type": "raw", "format": "docx", "bytes": 900, "version": 1700000002}`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. returns: `result is S`.
2. mock called: kw(gr) `resource_type == "raw"`.
3. re-read S: `status == "uploaded"`, `format == "docx"`, `file_size == 900`, `mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"`.

### MOBS-CF-05 — bytes 0 keeps the declared size
- **Rules:** confirm_staging_upload R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = staged but `file_size 1234`. gr returns GR but `bytes 0`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. returns: `result is S`.
2. re-read S: `file_size == 1234`, `status == "uploaded"`.

### MOBS-CF-06 — no bytes key keeps the declared size
- **Rules:** confirm_staging_upload R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = staged but `file_size 1234`. gr returns `{"resource_type": "image", "format": "jpg", "version": 1700000000}`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. returns: `result is S`.
2. re-read S: `file_size == 1234`.

### MOBS-CF-07 — Cloudinary image + pdf sets the PDF MIME type
- **Rules:** confirm_staging_upload R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = staged but `file_name "scan.pdf"`, `mime_type "application/octet-stream"`. gr returns GR but `format "pdf"`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. returns: `result is S`.
2. re-read S: `mime_type == "application/pdf"`, `format == "pdf"`, `status == "uploaded"`.

### MOBS-CF-08 — format "JPG" in capitals is accepted
- **Rules:** confirm_staging_upload R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = staged. gr returns GR but `format "JPG"`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. returns: `result.status == "uploaded"`.

### MOBS-CF-09 — exactly 10 485 760 bytes passes
- **Rules:** confirm_staging_upload R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = staged. gr returns GR but `bytes 10485760`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. returns: `result is S`.
2. re-read S: `status == "uploaded"`, `file_size == 10485760`, `public_id == STG`.
3. mock called: `dr.called is False`.

### MOBS-CF-10 — 10 485 761 bytes deletes the file and clears the session
- **Rules:** confirm_staging_upload R5 (BUG-2137, manager part)
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged. gr returns GR but `bytes 10485761`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "File too large (10485761 bytes). Maximum is 10485760 bytes."`.
3. mock called: dr once; kw(dr) `public_id == STG`, `kw(dr)["resource_type"] == "image"`, `kw(dr)["delivery_type"] == "authenticated"`.
4. re-read S: `public_id is None`, `asset_folder is None`, `status == "waiting"`.

### MOBS-CF-11 — an uploaded session refuses a second confirm
- **Rules:** confirm_staging_upload R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "This session already received a file."`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.

### MOBS-CF-12 — a consumed session refuses a confirm
- **Rules:** confirm_staging_upload R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged but `status "consumed"`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "This session already received a file."`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.

### MOBS-CF-13 — a cancelled session refuses a confirm
- **Rules:** confirm_staging_upload R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged but `status "cancelled"`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "This session already received a file."`.
3. mock called: cl_untouched.

### MOBS-CF-14 — no public_id: "Upload was not prepared."
- **Rules:** confirm_staging_upload R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged but `public_id None`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "Upload was not prepared."`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.

### MOBS-CF-15 — an empty public_id: "Upload was not prepared."
- **Rules:** confirm_staging_upload R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = staged but `public_id ""`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "Upload was not prepared."`.
3. mock called: cl_untouched.

### MOBS-CF-16 — no file name: "Upload was not prepared."
- **Rules:** confirm_staging_upload R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged but `file_name None`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "Upload was not prepared."`.
3. mock called: cl_untouched.

### MOBS-CF-17 — an empty file name: "Upload was not prepared."
- **Rules:** confirm_staging_upload R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = staged but `file_name ""`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "Upload was not prepared."`.
3. mock called: cl_untouched.

### MOBS-CF-18 — a lookup error leaves the session waiting
- **Rules:** confirm_staging_upload R3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged. gr `side_effect RuntimeError("boom")`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Cloudinary verification failed: boom"`.
3. session: `not db.dirty`.
4. mock called: `dr.called is False`.
5. unchanged: unchanged(S).

### MOBS-CF-19 — "not configured" during the lookup passes through
- **Rules:** confirm_staging_upload R3 [BUG-2141]
- **Kind:** bug
- **Expect:** xfail BUG-2141
- **Fails today on:** Then 1 (the call raises AttachmentConfirmError: the error is wrapped)

**Given**
1. S = staged. gr `side_effect CloudinaryNotConfiguredError("Cloudinary is not configured.")`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. raises: `str(exc.value) == "Cloudinary is not configured."`.
3. session: `not db.dirty`.
4. unchanged: unchanged(S).

### MOBS-CF-20 — a resource of the wrong type is refused, the session unchanged
- **Rules:** confirm_staging_upload R4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged. gr returns GR but `resource_type "raw"`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Cloudinary resource_type 'raw' does not match .jpg (expected 'image')."`.
3. session: `not db.dirty`.
4. mock called: `dr.called is False`.
5. unchanged: unchanged(S).

### MOBS-CF-21 — a resource of the wrong format is refused
- **Rules:** confirm_staging_upload R4
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged. gr returns GR but `format "png"`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Cloudinary format 'png' is not allowed for .jpg (expected one of: jpeg, jpg)."`.
3. session: `not db.dirty`.
4. unchanged: unchanged(S).

### MOBS-CF-22 — confirm flushes and never commits
- **Rules:** confirm_staging_upload (Side effects)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = staged.

**When**
- Rolled back: `M.confirm_staging_upload(db, session=S)`

**Then**
1. mock called: `cm.call_count == 0`.
2. re-read S: `status == "waiting"`.

### MOBS-CF-23 — a stored non-default delivery type is used for the lookup
- **Rules:** confirm_staging_upload R2
- **Kind:** external
- **Expect:** pass

**Given**
1. S = staged but `delivery_type "upload"`.

**When**
- `M.confirm_staging_upload(db, session=S)`

**Then**
1. returns: `result.status == "uploaded"`.
2. mock called: gr once; kw(gr) `public_id == STG`, `kw(gr)["delivery_type"] == "upload"`, `kw(gr)["resource_type"] == "image"`.

## `MobileUploadSessionManager._destroy_staging_asset`

### MOBS-DS-01 — the session's own id is deleted with its types; the session is not changed
- **Rules:** _destroy_staging_asset R1
- **Kind:** external
- **Expect:** pass

**Given**
1. S = staged but `resource_type "raw"`, `delivery_type "authenticated"`.

**When**
- `M._destroy_staging_asset(S)`

**Then**
1. mock called: dr once; kw(dr) `public_id == STG`, `resource_type == "raw"`, `kw(dr)["delivery_type"] == "authenticated"`.
2. session: `not db.dirty`.
3. returns: `S.public_id == STG`.

### MOBS-DS-02 — missing types default to image / authenticated
- **Rules:** _destroy_staging_asset R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = staged but `resource_type None`, `delivery_type None`.

**When**
- `M._destroy_staging_asset(S)`

**Then**
1. mock called: `kw(dr)["resource_type"] == "image"`, `kw(dr)["delivery_type"] == "authenticated"`.

### MOBS-DS-03 — no public_id: no call
- **Rules:** _destroy_staging_asset R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = sess.

**When**
- `M._destroy_staging_asset(S)`

**Then**
1. mock called: `dr.called is False`.

### MOBS-DS-04 — an empty public_id: no call
- **Rules:** _destroy_staging_asset R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = staged but `public_id ""`.

**When**
- `M._destroy_staging_asset(S)`

**Then**
1. mock called: `dr.called is False`.

### MOBS-DS-05 — a delete error is swallowed
- **Rules:** _destroy_staging_asset R3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged. dr `side_effect RuntimeError("down")`.

**When**
- `M._destroy_staging_asset(S)` (no error expected)

**Then**
1. mock called: dr once.
2. session: `not db.dirty`.

### MOBS-DS-06 — "not configured" is swallowed too
- **Rules:** _destroy_staging_asset R3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged. dr `side_effect CloudinaryNotConfiguredError("Cloudinary is not configured.")`.

**When**
- `M._destroy_staging_asset(S)` (no error expected)

**Then**
1. mock called: dr once.

### MOBS-DS-07 — a failed delete logs a WARNING naming the id and the error
- **Rules:** _destroy_staging_asset R3 [BUG-2136]
- **Kind:** bug
- **Expect:** xfail BUG-2136
- **Fails today on:** Then 2 (no log line)

**Given**
1. S = staged. dr `side_effect RuntimeError("down")`.

**When**
- `M._destroy_staging_asset(S)`

**Then**
1. mock called: dr once.
2. warnings: exactly 1 record; its `getMessage()` contains STG and contains `"down"`.

## `MobileUploadSessionManager.cancel_session`

### MOBS-CN-01 — a consumed session is returned untouched
- **Rules:** cancel_session R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = staged but `status "consumed"`.

**When**
- `M.cancel_session(db, session=S)`

**Then**
1. returns: `result is S`.
2. session: `not db.dirty`.
3. mock called: cl_untouched.
4. re-read S: `status == "consumed"`, `public_id == STG`.

### MOBS-CN-02 — a waiting session with no file ends cancelled
- **Rules:** cancel_session R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = sess.

**When**
- `M.cancel_session(db, session=S)`

**Then**
1. returns: `result is S`.
2. re-read S: `status == "cancelled"`.
3. mock called: `dr.called is False`.

### MOBS-CN-03 — a cancelled session is cancelled again without error
- **Rules:** cancel_session R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = sess but `status "cancelled"`.

**When**
- `M.cancel_session(db, session=S)`

**Then**
1. returns: `result is S`.
2. re-read S: `status == "cancelled"`.

### MOBS-CN-04 — an expired session ends cancelled
- **Rules:** cancel_session R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = sess but `status "expired"`.

**When**
- `M.cancel_session(db, session=S)`

**Then**
1. returns: `result is S`.
2. re-read S: `status == "cancelled"`.

### MOBS-CN-05 — an uploaded session's staged file is deleted
- **Rules:** cancel_session R3
- **Kind:** external
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- `M.cancel_session(db, session=S)`

**Then**
1. returns: `result is S`.
2. mock called: dr once; kw(dr) `public_id == STG`.
3. re-read S: `status == "cancelled"`.

### MOBS-CN-06 — cancelling an uploaded session clears its staged id
- **Rules:** cancel_session R4 [BUG-2138]
- **Kind:** bug
- **Expect:** xfail BUG-2138
- **Fails today on:** Then 3 (`public_id` is never cleared)

**Given**
1. S = uploaded.

**When**
- `M.cancel_session(db, session=S)`

**Then**
1. returns: `result is S`.
2. mock called: dr once.
3. re-read S: `public_id is None`, `asset_folder is None`, `status == "cancelled"`.

### MOBS-CN-07 — cancelling a waiting session deletes its signed file
- **Rules:** cancel_session R4 [BUG-2138]
- **Kind:** bug
- **Expect:** xfail BUG-2138
- **Fails today on:** Then 2 (a waiting session's file is not deleted)

**Given**
1. S = staged.

**When**
- `M.cancel_session(db, session=S)`

**Then**
1. returns: `result is S`.
2. mock called: dr once; kw(dr) `public_id == STG`.
3. re-read S: `public_id is None`, `asset_folder is None`, `status == "cancelled"`.

### MOBS-CN-08 — a failed delete does not stop the cancel
- **Rules:** cancel_session R5
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded. dr `side_effect RuntimeError("down")`.

**When**
- `M.cancel_session(db, session=S)`

**Then**
1. returns: `result is S`.
2. re-read S: `status == "cancelled"`.

### MOBS-CN-09 — cancel flushes and never commits
- **Rules:** cancel_session (Side effects)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = sess.

**When**
- Rolled back: `M.cancel_session(db, session=S)`

**Then**
1. mock called: `cm.call_count == 0`.
2. re-read S: `status == "waiting"`.

## `MobileUploadSessionManager._promote_file_name`

### MOBS-PF-01 — no new name keeps the staged name
- **Rules:** _promote_file_name R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = uploaded, unsaved, but `file_name "photo.JPG"`.

**When**
- `M._promote_file_name(S, None)`

**Then**
1. returns: `result == "photo.JPG"`.

### MOBS-PF-02 — an empty new name keeps the staged name
- **Rules:** _promote_file_name R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded, unsaved, but `file_name "photo.JPG"`.

**When**
- `M._promote_file_name(S, "")`

**Then**
1. returns: `result == "photo.JPG"`.

### MOBS-PF-03 — a whitespace-only new name keeps the staged name
- **Rules:** _promote_file_name R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded, unsaved, but `file_name "photo.JPG"`.

**When**
- `M._promote_file_name(S, "  \t ")`

**Then**
1. returns: `result == "photo.JPG"`.

### MOBS-PF-04 — no staged name gives "upload.jpg"
- **Rules:** _promote_file_name R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded, unsaved, but `file_name None`.

**When**
- `M._promote_file_name(S, None)`

**Then**
1. returns: `result == "upload.jpg"`.

### MOBS-PF-05 — the new name's extension is replaced by the staged one, case kept
- **Rules:** _promote_file_name R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = uploaded, unsaved, but `file_name "photo.JPG"`.

**When**
- `M._promote_file_name(S, "x.png")`

**Then**
1. returns: `result == "x.JPG"`.

### MOBS-PF-06 — a staged name with no dot gives "jpg"
- **Rules:** _promote_file_name R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded, unsaved, but `file_name "README"`.

**When**
- `M._promote_file_name(S, "new")`

**Then**
1. returns: `result == "new.jpg"`.

### MOBS-PF-07 — only the last dot of the new name is dropped
- **Rules:** _promote_file_name R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = uploaded, unsaved, but `file_name "scan.v2.pdf"`.

**When**
- `M._promote_file_name(S, "a.b.c")`

**Then**
1. returns: `result == "a.b.pdf"`.

### MOBS-PF-08 — the new name is trimmed and sanitized
- **Rules:** _promote_file_name R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = uploaded, unsaved, but `file_name "photo.JPG"`.

**When**
- `M._promote_file_name(S, "  dir/na<me> Q ")`

**Then**
1. returns: `result == "dir-name Q.JPG"`.

### MOBS-PF-09 — a base of exactly 251 characters gives 255 with the extension
- **Rules:** _promote_file_name R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded, unsaved, but `file_name "photo.JPG"`.

**When**
- `M._promote_file_name(S, "a" * 251)`

**Then**
1. returns: `result == "a" * 251 + ".JPG"`.

### MOBS-PF-10 — a longer base is shortened so the extension survives
- **Rules:** _promote_file_name R5 [BUG-2135]
- **Kind:** bug
- **Expect:** xfail BUG-2135
- **Fails today on:** Then 1 (the cut at 255 loses ".JPG")

**Given**
1. S = uploaded, unsaved, but `file_name "photo.JPG"`.

**When**
- `M._promote_file_name(S, "a" * 252)`

**Then**
1. returns: `result == "a" * 251 + ".JPG"`.

### MOBS-PF-11 — "." gives the staged name
- **Rules:** _promote_file_name R6 [BUG-2135]
- **Kind:** bug
- **Expect:** xfail BUG-2135
- **Fails today on:** Then 1 (today "JPG")

**Given**
1. S = uploaded, unsaved, but `file_name "photo.JPG"`.

**When**
- `M._promote_file_name(S, ".")`

**Then**
1. returns: `result == "photo.JPG"`.

### MOBS-PF-12 — "  .x" gives the staged name
- **Rules:** _promote_file_name R6 [BUG-2135]
- **Kind:** bug
- **Expect:** xfail BUG-2135
- **Fails today on:** Then 1 (today "JPG")

**Given**
1. S = uploaded, unsaved, but `file_name "photo.JPG"`.

**When**
- `M._promote_file_name(S, "  .x")`

**Then**
1. returns: `result == "photo.JPG"`.

### MOBS-PF-13 — a base that cleans to nothing ("<>") gives the staged name
- **Rules:** _promote_file_name R6 [BUG-2135]
- **Kind:** bug
- **Expect:** xfail BUG-2135
- **Fails today on:** Then 1 (today "JPG")

**Given**
1. S = uploaded, unsaved, but `file_name "photo.JPG"`.

**When**
- `M._promote_file_name(S, "<>")`

**Then**
1. returns: `result == "photo.JPG"`.

### MOBS-PF-14 — a staged name ending in "." with a name that cleans to nothing gives the staged name
- **Rules:** _promote_file_name R4, R6 [BUG-2135]
- **Kind:** bug
- **Expect:** xfail BUG-2135
- **Fails today on:** Then 1 (the call raises AttachmentValidationError: "Invalid file name.")

**Given**
1. S = uploaded, unsaved, but `file_name "photo."`.

**When**
- `M._promote_file_name(S, "?")`

**Then**
1. returns: `result == "photo."`.

## `MobileUploadSessionManager.promote_to_attachment`

### MOBS-PM-01 — a staged file becomes a ready attachment and the session is consumed
- **Rules:** promote_to_attachment R9, R10, R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = uploaded but `entity_label "Phone label"`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note="Receipt")`

**Then**
1. returns: `result.upload_status == "ready"`, `result.public_id == DEST`.
2. re-read S: `status == "consumed"`, `public_id is None`.
3. re-read S: `asset_folder == "Dev/" + W1.name + "/Projects/Tender"`.
4. re-read result: `file_name == "photo.jpg"`, `mime_type == "image/jpeg"`, `uploaded_by == UG.id`, `note == "Receipt"`, `file_size == 2048`, `asset_folder == "Dev/" + W1.name + "/Projects/Tender"`.
5. count(`attachment_links`, `attachment_id = result.id AND entity_type = 'project' AND entity_id = P1.id`) == 1.

### MOBS-PM-02 — the file is moved from the staged id to a server-minted id
- **Rules:** promote_to_attachment R7, R9
- **Kind:** external
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.public_id == DEST`.
2. mock called: rr once; kw(rr) `from_public_id == STG`, `to_public_id == DEST`, `kw(rr)["resource_type"] == "image"`, `kw(rr)["delivery_type"] == "authenticated"`.
3. mock called: um once; kw(um) `public_id == DEST`, `asset_folder == "Dev/" + W1.name + "/Projects/Tender"`, `display_name == "photo.jpg"`.
4. mock called: agr once; kw(agr) `public_id == DEST`.
5. mock called: `dr.called is False`, `adr.called is False`.

### MOBS-PM-03 — missing types fall back to the normalized type and authenticated
- **Rules:** promote_to_attachment R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded but `resource_type None`, `delivery_type None`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. mock called: `kw(rr)["resource_type"] == "image"`, `kw(rr)["delivery_type"] == "authenticated"`.

### MOBS-PM-04 — a raw document is moved as raw
- **Rules:** promote_to_attachment R7
- **Kind:** external
- **Expect:** pass

**Given**
1. S = uploaded but `resource_type "raw"`, `file_name "notes.docx"`, `mime_type "application/vnd.openxmlformats-officedocument.wordprocessingml.document"`, `format "docx"`. agr returns GRA but `resource_type "raw"`, `format "docx"`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.file_name == "notes.docx"`.
2. mock called: kw(rr) `resource_type == "raw"`.

### MOBS-PM-05 — ledger and activity: pending + ready by the caller, "Attached …" on the project
- **Rules:** promote_to_attachment R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. count(`attachment_ledger`, `attachment_id = result.id AND transaction_type = 'pending' AND performed_by = UG.id`) == 1.
3. count(`attachment_ledger`, `attachment_id = result.id AND transaction_type = 'ready' AND performed_by = UG.id`) == 1.
4. count(`project_events`, `project_id = P1.id AND event_type = 'attachment_added' AND description = 'Attached photo.jpg' AND performed_by = UG.id`) == 1.

### MOBS-PM-06 — a new name keeps the staged extension
- **Rules:** promote_to_attachment R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name="Invoice 7.png", note=None)`

**Then**
1. returns: `result.file_name == "Invoice 7.jpg"`.
2. mock called: kw(um) `display_name == "Invoice 7.jpg"`.

### MOBS-PM-07 — a missing size is sent as 1
- **Rules:** promote_to_attachment R3, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded but `file_size None`. agr returns GRA but `bytes 0`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. re-read result: `file_size == 1`.

### MOBS-PM-08 — exactly 10 485 760 stored bytes passes
- **Rules:** promote_to_attachment R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = uploaded but `file_size 10485760`. agr returns GRA but `bytes 10485760`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. re-read S: `status == "consumed"`.

### MOBS-PM-09 — 10 485 761 stored bytes is refused before any call
- **Rules:** promote_to_attachment R3
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded but `file_size 10485761`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == "File too large (10485761 bytes). Maximum is 10485760 bytes."`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. nothing written.

### MOBS-PM-10 — a waiting session has no file to attach
- **Rules:** promote_to_attachment R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = staged.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "No file is ready on this session."`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. nothing written.

### MOBS-PM-11 — a consumed session refuses a second promote
- **Rules:** promote_to_attachment R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded but `status "consumed"`, `public_id None`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "No file is ready on this session."`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. nothing written.

### MOBS-PM-12 — a cancelled session refuses a promote
- **Rules:** promote_to_attachment R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded but `status "cancelled"`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "No file is ready on this session."`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. nothing written.

### MOBS-PM-13 — an expired session refuses a promote
- **Rules:** promote_to_attachment R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded but `status "expired"`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "No file is ready on this session."`.
3. mock called: cl_untouched.
4. nothing written.

### MOBS-PM-14 — no public_id: staging metadata is incomplete
- **Rules:** promote_to_attachment R2
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded but `public_id None`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "Staging metadata is incomplete."`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. nothing written.

### MOBS-PM-15 — no file name: staging metadata is incomplete
- **Rules:** promote_to_attachment R2
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded but `file_name ""`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "Staging metadata is incomplete."`.
3. mock called: cl_untouched.
4. nothing written.

### MOBS-PM-16 — no MIME type: staging metadata is incomplete
- **Rules:** promote_to_attachment R2
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded but `mime_type None`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `MobileUploadSessionError`.
2. raises: `str(exc.value) == "Staging metadata is incomplete."`.
3. mock called: cl_untouched.
4. nothing written.

### MOBS-PM-17 — a MIME type that no longer matches is refused before the move
- **Rules:** promote_to_attachment R5, R6 (name / type)
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded but `mime_type "image/png"`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == "MIME type 'image/png' does not match .jpg (expected one of: image/jpeg)."`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. nothing written.

### MOBS-PM-18 — a full record is refused (the error itself)
- **Rules:** promote_to_attachment (Errors: record full)
- **Kind:** error
- **Expect:** pass

**Given**
1. full(P1).
2. S = uploaded.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentLimitError`.
2. raises: `str(exc.value) == "This record already has the maximum of 25 attachments."`.

### MOBS-PM-19 — a full record is refused before the file is moved
- **Rules:** promote_to_attachment R5 [BUG-2133]
- **Kind:** bug
- **Expect:** xfail BUG-2133
- **Fails today on:** Then 3 (the move runs before the limit check)

**Given**
1. full(P1).
2. S = uploaded.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentLimitError`.
2. raises: `str(exc.value) == "This record already has the maximum of 25 attachments."`.
3. mock called: `rr.called is False`.
4. mock called: cl_untouched.
5. session: `not db.dirty`.
6. session: `not db.new`.
7. unchanged: unchanged(S).

### MOBS-PM-20 — a failed move leaves the session as it was
- **Rules:** promote_to_attachment R8
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded. rr `side_effect RuntimeError("gone")`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Cloudinary move failed: gone"`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: `um.called is False`, `agr.called is False`.
6. re-read S: `status == "uploaded"`, `public_id == STG`.

### MOBS-PM-21 — "not configured" during the move passes through
- **Rules:** promote_to_attachment R8 [BUG-2141]
- **Kind:** bug
- **Expect:** xfail BUG-2141
- **Fails today on:** Then 1 (the call raises AttachmentConfirmError: the error is wrapped)

**Given**
1. S = uploaded. rr `side_effect CloudinaryNotConfiguredError("Cloudinary is not configured.")`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `CloudinaryNotConfiguredError`.
2. session: `not db.dirty`.
3. session: `not db.new`.
4. re-read S: `status == "uploaded"`, `public_id == STG`.

### MOBS-PM-22 — a failed metadata update does not stop the promote
- **Rules:** promote_to_attachment R9
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded. um `side_effect RuntimeError("meta")`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. re-read S: `status == "consumed"`.

### MOBS-PM-23 — a failed metadata update logs a WARNING naming the new id
- **Rules:** promote_to_attachment R9 [BUG-2136]
- **Kind:** bug
- **Expect:** xfail BUG-2136
- **Fails today on:** Then 2 (no log line)

**Given**
1. S = uploaded. um `side_effect RuntimeError("meta")`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. warnings: exactly 1 record; its `getMessage()` contains DEST and contains `"meta"`.

### MOBS-PM-24 — a confirm refusal of the moved file is raised as it is
- **Rules:** promote_to_attachment R10 (Errors: confirm fails)
- **Kind:** error
- **Expect:** pass

**Given**
1. S = uploaded. agr returns GRA but `format "png"`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentConfirmError`.
2. raises: `str(exc.value) == "Cloudinary format 'png' is not allowed for .jpg (expected one of: jpeg, jpg)."`.

### MOBS-PM-25 — promote flushes and never commits
- **Rules:** promote_to_attachment (Side effects)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S = uploaded.

**When**
- Rolled back: `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. mock called: `cm.call_count == 0`.
2. re-read S: `status == "uploaded"`.

### MOBS-PM-26 — PR-1: the session's project was deleted since
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PD = proj "Old Job", deleted.
2. S = uploaded but `entity_id PD.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PD.id)`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).
7. nothing written.

### MOBS-PM-27 — PR-1: an unknown project
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (the error raised is IntegrityError, not AttachmentNotFoundError: the record is not checked, the file is moved and the attachment written, then the activity row for a parent that does not exist breaks the FK project_events.project_id)

**Given**
1. S = uploaded but `entity_id MISSING`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == "project 999999999 not found."`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).

### MOBS-PM-28 — PR-1: a W0 project (lower workspace id)
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PX = W0 proj "Zero Job".
2. S = uploaded but `entity_id PX.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PX.id)`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).

### MOBS-PM-29 — PR-1: a W2 project (higher workspace id)
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PX = W2 proj "Nine Job".
2. S = uploaded but `entity_id PX.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PX.id)`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).

### MOBS-PM-30 — PR-1: a deleted machine
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. MD = machine "Press 4", deleted.
2. S = uploaded but `entity_type "machine"`, `entity_id MD.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("machine", MD.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-31 — PR-1: a deleted work order
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. WD = wo "WO-3", deleted.
2. S = uploaded but `entity_type "work_order"`, `entity_id WD.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("work_order", WD.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-32 — PR-1: a component of a deleted project
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PD = proj "Old Job", deleted.
2. CD = comp(PD, "Frame").
3. S = uploaded but `entity_type "project_component"`, `entity_id CD.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project_component", CD.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-33 — PR-1: a W2 purchase order
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. O9 = po "PO-T-009", but `workspace_id W2.id`.
2. S = uploaded but `entity_type "purchase_order"`, `entity_id O9.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("purchase_order", O9.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-34 — PR-1: a W0 help ticket, even for a W1 owner-role member
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. UG's W1 membership but `role "owner"`.
2. T0X = ticket "HELP-2026-001", but `workspace_id W0.id`.
3. S = uploaded but `entity_type "support_ticket"`, `entity_id T0X.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", T0X.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-35 — PR-1: a purchase-order id that only a W1 machine has
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (the error raised is IntegrityError, not AttachmentNotFoundError: the record is not checked, the file is moved and the attachment written, then the activity row for a parent that does not exist breaks the FK purchase_order_events.purchase_order_id)

**Given**
1. MX = machine "Press 7", but `id XID(1)`. No purchase order has id XID(1).
2. S = uploaded but `entity_type "purchase_order"`, `entity_id XID(1)`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("purchase_order", XID(1))`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-36 — PR-1: a component id that only a live W1 project has
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (the error raised is IntegrityError, not AttachmentNotFoundError: the record is not checked, the file is moved and the attachment written, then the activity row for a parent that does not exist breaks the FK project_component_activity_events.project_component_id)

**Given**
1. PY = proj "Yard", but `id XID(2)`. No project component has id XID(2).
2. S = uploaded but `entity_type "project_component"`, `entity_id XID(2)`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project_component", XID(2))`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-37 — PR-1 passes: a live machine
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** happy
- **Expect:** pass

**Given**
1. MA = machine "Press 1".
2. S = uploaded but `entity_type "machine"`, `entity_id MA.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. re-read S: `status == "consumed"`, `asset_folder == "Dev/" + W1.name + "/Machines/Press 1"`.

### MOBS-PM-38 — PR-1 passes: scratch
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = uploaded but `entity_type "scratch"`, `entity_id 777`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. re-read S: `asset_folder == "Dev/" + W1.name + "/Scratch/scratch-777"`.

### MOBS-PM-39 — PR-2: a plain member, private project
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PV = proj "Tender 2027", private.
2. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).

### MOBS-PM-40 — PR-2: owning W0 does not open the private project
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. set_owner(W0, UG).
2. PV = proj "Tender 2027", private.
3. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-41 — PR-2: owning W2 does not open the private project
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. set_owner(W2, UG).
2. PV = proj "Tender 2027", private.
3. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-42 — PR-2: privileged only in W0 does not open it
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. member(UG, "owner", ws=W0).
2. PV = proj "Tender 2027", private.
3. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-43 — PR-2: privileged only in W2 does not open it
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. member(UG, "ground-team-manager", ws=W2).
2. PV = proj "Tender 2027", private.
3. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-44 — PR-2: membership of other private projects (lower and higher id)
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PA = proj "Alpha", private. pmem(PA, UG).
2. PV = proj "Tender 2027", private.
3. PB = proj "Beta", private. pmem(PB, UG).
4. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-45 — PR-2: having created another private project
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PA = proj "Alpha", private, but `created_by UG.id`.
2. PV = proj "Tender 2027", private.
3. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-46 — PR-2: a private project with no creator, plain member
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PV = proj "Tender 2027", private, but `created_by None`.
2. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-47 — PR-2: a suspended W1 owner membership
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. UG's W1 membership but `role "owner"`, `status "suspended"`.
2. PV = proj "Tender 2027", private.
3. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-48 — PR-2: a component of a private project, plain member
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. PV = proj "Tender 2027", private.
2. CV = comp(PV, "Frame").
3. S = uploaded but `entity_type "project_component"`, `entity_id CV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project_component", CV.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-49 — PR-2: another member's ticket, plain role
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. TK = ticket "HELP-2026-001".
2. S = uploaded but `entity_type "support_ticket"`, `entity_id TK.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", TK.id)`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).

### MOBS-PM-50 — PR-2: creating other tickets (lower and higher id)
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. TA = ticket "HELP-2026-001", but `created_by UG.id`.
2. TK = ticket "HELP-2026-002".
3. TB = ticket "HELP-2026-003", but `created_by UG.id`.
4. S = uploaded but `entity_type "support_ticket"`, `entity_id TK.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", TK.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-51 — PR-2: a ticket with no creator, plain role
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. TK = ticket "HELP-2026-001", but `created_by None`.
2. S = uploaded but `entity_type "support_ticket"`, `entity_id TK.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", TK.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-52 — PR-2: a W1 membership role "Owner" with a capital does not open a ticket
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. UG's W1 membership but `role "Owner"`.
2. TK = ticket "HELP-2026-001".
3. S = uploaded but `entity_type "support_ticket"`, `entity_id TK.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", TK.id)`.
3. session: `not db.dirty`.
4. mock called: cl_untouched.
5. unchanged: unchanged(S).

### MOBS-PM-53 — PR-2 grant: the W1 owner, private project
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** happy
- **Expect:** pass

**Given**
1. set_owner(W1, UG).
2. PV = proj "Tender 2027", private.
3. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. re-read S: `status == "consumed"`.

### MOBS-PM-54 — PR-2 grant: an active owner-role member, private project
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** happy
- **Expect:** pass

**Given**
1. UG's W1 membership but `role "owner"`.
2. PV = proj "Tender 2027", private.
3. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. re-read S: `status == "consumed"`.

### MOBS-PM-55 — PR-2 grant: the creator, private project
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** happy
- **Expect:** pass

**Given**
1. PV = proj "Tender 2027", private, but `created_by UG.id`.
2. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. re-read S: `status == "consumed"`.

### MOBS-PM-56 — PR-2 grant: a project member, private project
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** happy
- **Expect:** pass

**Given**
1. PV = proj "Tender 2027", private. pmem(PV, UG).
2. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. re-read S: `status == "consumed"`.

### MOBS-PM-57 — PR-2 grant: a privileged member, private project with no creator
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** happy
- **Expect:** pass

**Given**
1. UG's W1 membership but `role "ground-team-manager"`.
2. PV = proj "Tender 2027", private, but `created_by None`.
3. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. re-read S: `status == "consumed"`.

### MOBS-PM-58 — PR-2 grant: the ticket's creator
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** happy
- **Expect:** pass

**Given**
1. TK = ticket "HELP-2026-001", but `created_by UG.id`.
2. S = uploaded but `entity_type "support_ticket"`, `entity_id TK.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. re-read S: `status == "consumed"`.

### MOBS-PM-59 — PR-2 grant: an active owner-role member opens another member's ticket
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** happy
- **Expect:** pass

**Given**
1. UG's W1 membership but `role "owner"`.
2. TK = ticket "HELP-2026-001".
3. S = uploaded but `entity_type "support_ticket"`, `entity_id TK.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. re-read S: `status == "consumed"`.

### MOBS-PM-60 — PR-2 grant: a platform admin opens a ticket with no creator
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UG.is_platform_admin = True`, flush.
2. TK = ticket "HELP-2026-001", but `created_by None`.
3. S = uploaded but `entity_type "support_ticket"`, `entity_id TK.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. re-read S: `status == "consumed"`.

### MOBS-PM-61 — PR-2: a removed (inactive) W1 owner membership does not open a private project
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. UG's W1 membership but `role "owner"`, removed.
2. PV = proj "Tender 2027", private.
3. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).
7. nothing written.

### MOBS-PM-62 — PR-2: a suspended W1 ground-team-manager membership does not open another member's ticket
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. UG's W1 membership but `role "ground-team-manager"`, `status "suspended"`.
2. TK = ticket "HELP-2026-001".
3. S = uploaded but `entity_type "support_ticket"`, `entity_id TK.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", TK.id)`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).
7. nothing written.

### MOBS-PM-63 — PR-2: a removed (inactive) W1 owner membership does not open another member's ticket
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. UG's W1 membership but `role "owner"`, removed.
2. TK = ticket "HELP-2026-001".
3. S = uploaded but `entity_type "support_ticket"`, `entity_id TK.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", TK.id)`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).
7. nothing written.

### MOBS-PM-64 — PR-2: privileged rows in W0 and W2 older than the W1 row do not open a private project
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. `db.delete(MG)`, flush.
2. member(UG, "owner", ws=W0).
3. member(UG, "ground-team-manager", ws=W2).
4. member(UG, "ground-team") (the W1 row, now the newest).
5. PV = proj "Tender 2027", private.
6. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).
7. nothing written.

### MOBS-PM-65 — PR-2: an owner role only in W0 does not open another member's W1 ticket
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. member(UG, "owner", ws=W0).
2. TK = ticket "HELP-2026-001".
3. S = uploaded but `entity_type "support_ticket"`, `entity_id TK.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("support_ticket", TK.id)`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).
7. nothing written.

### MOBS-PM-66 — PR-2 passes: a caller with no W1 membership attaches to a workspace-wide machine
- **Rules:** promote_to_attachment R4 [BUG-2134]
- **Kind:** happy
- **Expect:** pass

**Given**
1. `db.delete(MG)`, flush.
2. MA = machine "Press 1".
3. S = uploaded but `entity_type "machine"`, `entity_id MA.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. re-read S: `status == "consumed"`.

### MOBS-PM-67 — PR-2: no W1 membership at all: a private project stays closed
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. `db.delete(MG)`, flush.
2. PV = proj "Tender 2027", private.
3. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).
7. nothing written.

### MOBS-PM-68 — a stored non-default delivery type is used for the move
- **Rules:** promote_to_attachment R7
- **Kind:** external
- **Expect:** pass

**Given**
1. S = uploaded but `delivery_type "upload"`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.public_id == DEST`.
2. mock called: rr once; kw(rr) `from_public_id == STG`, `to_public_id == DEST`, `kw(rr)["delivery_type"] == "upload"`, `kw(rr)["resource_type"] == "image"`.

### MOBS-PM-69 — PR-2: a platform admin with no W1 membership is refused a private project
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. `db.delete(MG)`, flush.
2. `UG.is_platform_admin = True`, flush.
3. PV = proj "Tender 2027", private.
4. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).
7. nothing written.

### MOBS-PM-70 — PR-2: a platform admin with no W1 membership is refused a component of a private project
- **Rules:** promote_to_attachment R4, R5 [BUG-2134]
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (no error is raised today: the record is not checked)

**Given**
1. `db.delete(MG)`, flush.
2. `UG.is_platform_admin = True`, flush.
3. PV = proj "Tender 2027", private.
4. CV = comp(PV, "Frame").
5. S = uploaded but `entity_type "project_component"`, `entity_id CV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project_component", CV.id)`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).
7. nothing written.

### MOBS-PM-71 — PR-2 grant: the workspace owner with a plain role attaches to another member's ticket
- **Rules:** promote_to_attachment R4 [BUG-2134, BUG-2103]
- **Kind:** happy
- **Expect:** pass

**Given**
1. set_owner(W1, UG) (UG's W1 membership stays `role "ground-team"`, active).
2. TK = ticket "HELP-2026-001" (created by U1).
3. S = uploaded but `entity_type "support_ticket"`, `entity_id TK.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. returns: `result.upload_status == "ready"`.
2. re-read S: `status == "consumed"`.

### MOBS-PM-72 — PR-2 before the size check: a hidden private project with an oversized file answers 404
- **Rules:** promote_to_attachment R4 [BUG-2134] (G6: R4 after the session-state checks, before size / name / type / limit)
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (the error raised is AttachmentValidationError "File too large …": the size is checked and the record is not)

**Given**
1. PV = proj "Tender 2027", private.
2. S = uploaded but `entity_id PV.id`, `file_size 10485761`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).

### MOBS-PM-73 — PR-2 before the type check: a hidden private project with a mismatched MIME type answers 404
- **Rules:** promote_to_attachment R4 [BUG-2134] (G6: R4 after the session-state checks, before size / name / type / limit)
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (the error raised is AttachmentValidationError "MIME type 'image/png' does not match …": the type is checked and the record is not)

**Given**
1. PV = proj "Tender 2027", private.
2. S = uploaded but `entity_id PV.id`, `mime_type "image/png"`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).

### MOBS-PM-74 — PR-2 before the limit check: a hidden private project at its capacity answers 404
- **Rules:** promote_to_attachment R4 [BUG-2134] (G6: R4 after the session-state checks, before size / name / type / limit)
- **Kind:** bug
- **Expect:** xfail BUG-2134
- **Fails today on:** Then 1 (the error raised is AttachmentLimitError "This record already has the maximum of 25 attachments.": the limit is checked and the record is not)

**Given**
1. PV = proj "Tender 2027", private.
2. full(PV).
3. S = uploaded but `entity_id PV.id`.

**When**
- `M.promote_to_attachment(db, session=S, workspace=W1, user=UG, file_name=None, note=None)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NF("project", PV.id)`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. mock called: cl_untouched.
6. unchanged: unchanged(S).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| HTTP mapping (Overview) | `app/api/v1/endpoints/mobile_upload.py` | NotFound → 404 "Upload session not found."; session / validation / confirm / limit errors → 400; not configured → 503; `AttachmentNotFoundError` → 404 on create and promote (FU-1 b) |
| confirm_staging_upload R5 / BUG-2137 | `MobileUploadService.public_confirm` | the cleared session (no `public_id`) is committed although the request fails |
| BUG-2139 (cancel R6, promote R11) race | `MobileUploadService` / integration | two committed transactions: second promote waits then gets "No file is ready on this session."; the service passes `for_update=True` on promote and cancel |
| create_session R7 rate limit; public_sign `workspace_dao.get` | endpoint / service | 10 per minute; workspace lookup |
| _ensure_active R4 / get_for_creator R3 (D13) | `MobileUploadService` | "expired" is never committed |

## Spec gaps
None. Revision-1 gaps 1–5 were closed by the spec's fill-gaps revision (Gap log G1–G5).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_naive_utc` | R1 | MOBS-N-01 |
| `_naive_utc` | R2 [BUG-1282] | MOBS-N-02, MOBS-N-03 |
| `_hash_token` | R1 | MOBS-H-01, MOBS-H-02 |
| `_upload_env` | R1 | MOBS-E-01, MOBS-E-02, MOBS-PI-03 |
| `_is_production` | R2 | MOBS-E-03, MOBS-E-04, MOBS-E-05 |
| `build_staging_public_id` | R1 | MOBS-PI-02, MOBS-PI-04 |
| `build_staging_public_id` | R2 | MOBS-PI-01, MOBS-PI-03 |
| `build_staging_asset_folder` | R1 | MOBS-AF-01 |
| `build_staging_asset_folder` | R2 | MOBS-AF-02 |
| `create_session_token` | R1 | MOBS-TK-01, MOBS-TK-02 |
| `resolve_entity_label` | R1 | MOBS-RL-01, MOBS-RL-02, MOBS-C-03 |
| `resolve_entity_label` | R2 | MOBS-RL-03 … MOBS-RL-07 |
| `resolve_entity_label` | R3 [BUG-2132] | MOBS-RL-08, MOBS-RL-09, MOBS-C-06 |
| `create_session` | R1 | MOBS-C-01, MOBS-C-03 |
| `create_session` | R2 | MOBS-C-01 |
| `create_session` | R3 | MOBS-C-01 |
| `create_session` | R4 [BUG-1282] | MOBS-C-02 |
| `create_session` | R5 [BUG-2130] | MOBS-C-05, MOBS-C-08 … MOBS-C-21 |
| `create_session` | R6 [BUG-2131] | MOBS-C-22 … MOBS-C-53 |
| `create_session` | PR-2 [BUG-2103] | MOBS-C-53 |
| `create_session` | R7 | MOBS-C-04 |
| `create_session` | Errors: R5/R6 | MOBS-C-08 … MOBS-C-18, MOBS-C-23 … MOBS-C-36, MOBS-C-44 … MOBS-C-48, MOBS-C-50 |
| `create_session` | Errors: label > 80 (today DataError) | MOBS-C-06 |
| `create_session` | Side effects (flush, no commit) | MOBS-C-07 |
| `to_create_response` | R1 | MOBS-CR-01 |
| `_ensure_active` | R1 | MOBS-EA-01, MOBS-EA-02, MOBS-EA-03 |
| `_ensure_active` | R2 | MOBS-EA-04, MOBS-EA-05, MOBS-EA-06 |
| `_ensure_active` | R3 [BUG-1282] | MOBS-EA-07, MOBS-EA-08, MOBS-EA-09 |
| `_ensure_active` | R4 | MOBS-EA-10 |
| `_ensure_active` | R5 | MOBS-EA-05, MOBS-EA-11 |
| `get_by_raw_token` | R1 | MOBS-T-01, MOBS-T-04 |
| `get_by_raw_token` | R2 | MOBS-T-02, MOBS-T-03, MOBS-T-04 |
| `get_by_raw_token` | R3 | MOBS-T-01, MOBS-T-05, MOBS-T-06 |
| `get_for_creator` | R1 | MOBS-GC-01 … MOBS-GC-06 |
| `get_for_creator` | R2 | MOBS-GC-07, MOBS-GC-08 |
| `get_for_creator` | R3 | MOBS-GC-07 |
| `get_for_creator` | R4 | MOBS-GC-09, MOBS-GC-10, MOBS-GC-11 |
| `get_for_creator` | R5 [BUG-2139] | MOBS-GC-12 |
| `_staging_preview_url` | R1 | MOBS-PV-03 |
| `_staging_preview_url` | R2 | MOBS-PV-04, MOBS-PV-05, MOBS-PV-06 |
| `_staging_preview_url` | R3 | MOBS-PV-07, MOBS-PV-08, MOBS-PV-09 |
| `_staging_preview_url` | R4 | MOBS-PV-01, MOBS-PV-02 |
| `_staging_preview_url` | R5 | MOBS-PV-10, MOBS-PV-11 |
| `to_session_response` | R1 | MOBS-SR-01, MOBS-SR-02 |
| `to_session_response` | Errors (ValueError) | MOBS-SR-03 |
| `to_public_response` | R1 | MOBS-PB-01 |
| `to_public_response` | Errors (as to_session_response) | MOBS-SR-03 (same enum mapping) |
| `normalize_public_sign` | R1 | MOBS-NP-01 … MOBS-NP-05 |
| `normalize_public_sign` | R2 | MOBS-NP-06 … MOBS-NP-09 |
| `sign_staging_upload` | R1 | MOBS-SG-06 … MOBS-SG-09 |
| `sign_staging_upload` | R2 | MOBS-SG-10 |
| `sign_staging_upload` | R3 [BUG-2140] | MOBS-SG-11, MOBS-SG-12, MOBS-SG-13 |
| `sign_staging_upload` | R4 | MOBS-SG-01, MOBS-SG-04, MOBS-SG-05 |
| `sign_staging_upload` | R5 | MOBS-SG-01, MOBS-SG-10 |
| `sign_staging_upload` | R6 | MOBS-SG-14, MOBS-SG-15, MOBS-SG-16 |
| `sign_staging_upload` | R7 | MOBS-SG-02, MOBS-SG-03, MOBS-SG-04 |
| `sign_staging_upload` | Errors: invalid file | MOBS-SG-11 |
| `sign_staging_upload` | Side effects (flush, no commit) | MOBS-SG-17 |
| `confirm_staging_upload` | R1 | MOBS-CF-11 … MOBS-CF-17 |
| `confirm_staging_upload` | R2 | MOBS-CF-02, MOBS-CF-03, MOBS-CF-04, MOBS-CF-23 |
| `confirm_staging_upload` | R3 [BUG-2141] | MOBS-CF-18, MOBS-CF-19 |
| `confirm_staging_upload` | R4 | MOBS-CF-08, MOBS-CF-20, MOBS-CF-21 |
| `confirm_staging_upload` | R5 (BUG-2137 manager part) | MOBS-CF-09, MOBS-CF-10 |
| `confirm_staging_upload` | R6 | MOBS-CF-01, MOBS-CF-04 … MOBS-CF-07 |
| `confirm_staging_upload` | Side effects (flush, no commit) | MOBS-CF-22 |
| `_destroy_staging_asset` | R1 | MOBS-DS-01, MOBS-DS-02 |
| `_destroy_staging_asset` | R2 | MOBS-DS-03, MOBS-DS-04 |
| `_destroy_staging_asset` | R3 [BUG-2136] | MOBS-DS-05, MOBS-DS-06, MOBS-DS-07 |
| `cancel_session` | R1 | MOBS-CN-01 |
| `cancel_session` | R2 | MOBS-CN-02, MOBS-CN-03, MOBS-CN-04 |
| `cancel_session` | R3 | MOBS-CN-05 |
| `cancel_session` | R4 [BUG-2138] | MOBS-CN-06, MOBS-CN-07 |
| `cancel_session` | R5 | MOBS-CN-08 |
| `cancel_session` | R6 [BUG-2139] | MOBS-GC-12; race deferred |
| `cancel_session` | Side effects (flush, no commit) | MOBS-CN-09 |
| `_promote_file_name` | R1 | MOBS-PF-01 … MOBS-PF-04 |
| `_promote_file_name` | R2 | MOBS-PF-05, MOBS-PF-06 |
| `_promote_file_name` | R3 | MOBS-PF-05, MOBS-PF-07, MOBS-PF-08 |
| `_promote_file_name` | R4 [BUG-2135] | MOBS-PF-14 |
| `_promote_file_name` | R5 [BUG-2135] | MOBS-PF-09, MOBS-PF-10 |
| `_promote_file_name` | R6 [BUG-2135] | MOBS-PF-11, MOBS-PF-12, MOBS-PF-13, MOBS-PF-14 |
| `promote_to_attachment` | R1 | MOBS-PM-10 … MOBS-PM-13 |
| `promote_to_attachment` | R2 | MOBS-PM-14, MOBS-PM-15, MOBS-PM-16 |
| `promote_to_attachment` | R3 | MOBS-PM-07, MOBS-PM-08, MOBS-PM-09 |
| `promote_to_attachment` | R4 [BUG-2134] | MOBS-PM-26 … MOBS-PM-67, MOBS-PM-69 … MOBS-PM-74 |
| `promote_to_attachment` | PR-2 [BUG-2103] | MOBS-PM-71 |
| `promote_to_attachment` | R5 [BUG-2133] | MOBS-PM-17, MOBS-PM-18, MOBS-PM-19, MOBS-PM-26 … MOBS-PM-36, MOBS-PM-61 … MOBS-PM-65, MOBS-PM-67, MOBS-PM-69, MOBS-PM-70 |
| `promote_to_attachment` | R6 | MOBS-PM-06, MOBS-PM-07, MOBS-PM-17 |
| `promote_to_attachment` | R7 | MOBS-PM-02, MOBS-PM-03, MOBS-PM-04, MOBS-PM-68 |
| `promote_to_attachment` | R8 [BUG-2141] | MOBS-PM-20, MOBS-PM-21 |
| `promote_to_attachment` | R9 [BUG-2136] | MOBS-PM-01, MOBS-PM-02, MOBS-PM-22, MOBS-PM-23 |
| `promote_to_attachment` | R10 | MOBS-PM-01, MOBS-PM-05, MOBS-PM-24 |
| `promote_to_attachment` | R11 [BUG-2139] | MOBS-PM-01; lock MOBS-GC-12; race deferred |
| `promote_to_attachment` | Errors: record full | MOBS-PM-18, MOBS-PM-19 |
| `promote_to_attachment` | Errors: confirm fails | MOBS-PM-24 |
| `promote_to_attachment` | Side effects (flush, no commit) | MOBS-PM-25 |
