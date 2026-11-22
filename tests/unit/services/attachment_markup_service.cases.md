# Test cases — `app/services/attachment_markup_service.py`

> **Spec:** `tests/unit/services/attachment_markup_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-05) — verifier findings 1, 2: new LV-07, PL-12, DL-07 (a not-ready attachment reaches the caller as `AttachmentValidationError`, rolled back, pending row discarded); new LL-12, LV-08 (distinct times: the manager's order is kept, with ids that do not rise with it).
> **Counts:** 39 cases · 28 expected-to-pass · 11 expected-to-fail (bugs, all strict) · 3 deferred (2 cards `Author: claude`: PL-05, PL-10)

## Reviewer summary
- **Depth:** simple module (four pass-throughs, no stock, money or order state). Each rule gets one card, and each writer gets TC1, TC3 and TC4. The two reads that commit (D1) get a "pending change is saved" card and a "refusal discards it" card. The manager's matrix (BUG-2115 and the rest) is in `attachment_markup_manager.cases.md`. Here each public method gets one refused card (a private project), `list_layers` and `put_own_layer` also get a grant-held-elsewhere card (member of another private project; owner role only in W0 / W2), and each method gets one granted card.
- **Per callable:** `list_layers` 12 (4 bug) · `list_events` 8 (2 bug) · `put_own_layer` 12 (4 bug) · `delete_own_layer` 7 (1 bug).
- **Notable design choices:** every test commits its Given rows (commit point), so the service's rollback cannot remove them. "Committed" is checked after a test-level `db.rollback()`. Every refusal checks `session: clean` before any re-read. Lists are compared as sets where times tie (BUG-1435 / BUG-1436, the manager's); LL-12 and LV-08 use distinct times, where the order is defined today (layers oldest `updated_at` first, history newest `created_at` first), and check that the service keeps it. `put_own_layer` R2 ("not re-read after the commit") is checked by an order log of `commit` and `refresh` (`Author: claude`). BUG-2120 uses the manager cases' race simulation (`Author: claude`). Pass-through BUG cards: BUG-2115 (7), BUG-2118 (1), BUG-2119 (2), BUG-2120 (1).
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `AMSV` = `app/services/attachment_markup_service.py` (`AMUP` is the manager's, `AMK` the DAO's). `LL` list_layers · `LV` list_events · `PL` put_own_layer · `DL` delete_own_layer.

**Imports.** `from app.services.attachment_markup_service import AttachmentMarkupService, attachment_markup_service`; `from app.managers.attachment_manager import AttachmentNotFoundError, AttachmentValidationError`; `MarkupPayload` (`app.schemas.attachment_markup`); models `Attachment`, `AttachmentLink`, `AttachmentMarkup`, `AttachmentMarkupEvent`, `Project`, `ProjectMember`, `HelpTicket`, `Factory`, `WorkspaceMember` (`app.models.<module>`). `IntegrityError` (`sqlalchemy.exc`); `event`, `text` (`sqlalchemy`); `patch`, `Mock` (`unittest.mock`); `datetime`. Response classes are checked by `type(result).__name__`.

**Fixed values.** `svc` = `attachment_markup_service`. `db` = the real session, first argument; others by keyword. `result` = what the When returns. The session never autoflushes. MISSING = `999999999`. T0 = `datetime(2025, 12, 1, 8, 0, 0)`, T1 = `datetime(2026, 1, 1, 9, 0, 0)`, T2 = `datetime(2026, 1, 1, 10, 0, 0)`. **NFA(A)** = `"Attachment " + str(A.id) + " not found."`. UNAV = `"Markup is only available for images and PDFs."`.

**Settings (every test)**, `monkeypatch.setattr` on `app.core.config.settings`: `CLOUDINARY_UPLOAD_ENV "development"`, `ENVIRONMENT "development"`, `CLOUDINARY_CLOUD_NAME "demo-cloud"`, `CLOUDINARY_API_KEY "123456"`, `CLOUDINARY_API_SECRET "s3cret"`. **Externals:** none are patched (the spec names none).

**Standing rows** (every test, in this order, flushed): W0, W1, W2 = `make_workspace(db)` (W0.id < W1.id < W2.id; no `owner_user_id`). U1 = `make_profile(db, name="Ana Rahman")`, U2 = `make_profile(db, name="Bilal Khan")`, UG = `make_profile(db, name="Mia Khan")`. member(U1, "ground-team"), member(U2, "owner"), member(UG, "ground-team"). F0 / F1 / F9 = `Factory(workspace_id=W0.id / W1.id / W2.id, name="Factory Zero" / "Factory One" / "Factory Nine", abbreviation="F0" / "F1" / "F9")`. A1 = att("plan.png"), then link(A1, "scratch", 1). UG is the caller of every card.

**Given rows** (added and flushed one at a time in the order written; after "but" every differing column):
- **member(U, role, status="active", ws=W1)** = `WorkspaceMember(workspace_id=ws.id, user_id=U.id, role=role, status=status)`.
- **att(name)** = `Attachment(workspace_id=W1.id, file_name=name, mime_type="image/png", file_size=100, uploaded_by=U1.id, upload_status="ready", format="png")`. **W0 att** = `workspace_id W0.id`.
- **link(A, type, eid)** = `AttachmentLink(workspace_id=A.workspace_id, attachment_id=A.id, entity_type=type, entity_id=eid, linked_by=U1.id)`.
- **proj(name)** = `Project(workspace_id=W1.id, factory_id=F1.id, name=name, description="Main", created_by=U1.id, visibility="workspace")`; **private** = `visibility "invited_only"`. **pmem(P, U)** = `ProjectMember(workspace_id=P.workspace_id, project_id=P.id, user_id=U.id, assigned_by=U1.id)`. **ticket(n)** = `HelpTicket(workspace_id=W1.id, ticket_number=n, title="Printer jam", description="It jams", created_by=U1.id)`.
- **layer(A, U, P)** = `AttachmentMarkup(workspace_id=A.workspace_id, attachment_id=A.id, user_id=U.id, payload=D(P))`. **mev(A, U, at)** = `AttachmentMarkupEvent(workspace_id=A.workspace_id, attachment_id=A.id, user_id=U.id, event_type="markup_saved", description="seed", created_at=at)`.

**Payloads.** PT = `{"x": 0.1, "y": 0.2}`. STROKE = `{"color": "#ff0000", "width": 0.5, "points": [PT]}`. TEXT = `{"x": 0.1, "y": 0.1, "text": "OK", "color": "#000000", "size": 0.05}`. **MP(d)** = `MarkupPayload.model_validate({"pages": d})`; **D(d)** = `MP(d).model_dump()`. P1 = `{"1": {"strokes": [STROKE]}}`. P2 = `{"2": {"texts": [TEXT]}}`. EMPTY = `{}`.

**Commit point (every test).** After the last Given line the test runs `db.commit()`. Snapshots are taken there. Then, only where a card lists them:
- **pending X** = `X = Factory(workspace_id=W2.id, name="Factory X", abbreviation="FX")`, `db.add(X)`, `db.flush()`; `X_ID = X.id`. **x_gone** = `db.scalar(text("SELECT count(*) FROM factories WHERE id = :i"), {"i": X_ID}) == 0`; **x_kept** = that count `== 1`.

**Named checks.**
- `session:` lines check `db` right after the call, before any re-read. **clean** = `not db.new`, `not db.dirty`, `not db.deleted`.
- **re-read X** = `db.expire_all()`, then SELECT X by id.
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line then re-reads with a fresh query.
- **layers_of(A)** / **events_of(A)** = `db.expire_all()`, then every `attachment_markups` / `attachment_markup_events` row with `attachment_id == A.id`, ordered by `id`.
- **nothing written** = row counts of `attachment_markups` and `attachment_markup_events` (all workspaces) equal their values at the commit point.
- `raises: E` = `with pytest.raises(E) as exc:` around the call, no savepoint; `str(exc.value)` is the message.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **failing commit** = `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When, inside `with pytest.raises(RuntimeError) as exc:`.
- **recorder** = `stmts = []`; `event.listen(db.connection(), "before_cursor_execute", rec)` appending `statement`; `event.remove` right after the When. **profile_reads** = the number of recorded statements that start with `SELECT` and contain `FROM profiles`.
- **pairs(r)** = `{(i.user_id, i.is_mine) for i in r.items}`.
- **older(X, h)** = `db.execute(text("UPDATE attachment_markups SET updated_at = now() - make_interval(hours => :h) WHERE id = :i"), {"h": h, "i": X.id})`, then `db.expire_all()`.

**xfail cards.** `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call exactly as shown.

**Race simulations.** AMSV-PL-10 (put_own_layer R3, manager R5a, BUG-2120): `patch("app.dao.attachment_markup.AttachmentMarkupDAO.get_for_user", return_value=None)` around the When, so the save takes the insert path while the caller's layer exists.

## `AttachmentMarkupService.list_layers`

### AMSV-LL-01 — every author's layer, only the caller's marked mine
- **Rules:** list_layers R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. layer(A1, U1, P1).
2. layer(A1, UG, P2).

**When**
- `result = svc.list_layers(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=UG.id)`

**Then**
1. returns: `type(result).__name__ == "AttachmentMarkupListResponse"`.
2. returns: `pairs(result) == {(U1.id, False), (UG.id, True)}`.
3. returns: `{i.user_name for i in result.items} == {"Ana Rahman", "Mia Khan"}`.
4. returns: `len(result.items) == 2`.

### AMSV-LL-02 — no layers gives []
- **Rules:** list_layers R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = svc.list_layers(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=UG.id)`

**Then**
1. returns: `result.items == []`.

### AMSV-LL-03 — the read commits: a change pending in the session is saved
- **Rules:** list_layers R2 (D1)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. layer(A1, U1, P1).
2. pending X.

**When**
- spies: `result = svc.list_layers(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=UG.id)`

**Then**
1. returns: `pairs(result) == {(U1.id, False)}`.
2. mock called: `cm.call_count == 1`, `rb.called is False`.
3. committed: x_kept.
4. nothing written.

### AMSV-LL-04 — an unknown attachment rolls back and discards pending changes
- **Rules:** list_layers R3, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. pending X.

**When**
- spies: `svc.list_layers(db, workspace_id=W1.id, attachment_id=MISSING, current_user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == "Attachment 999999999 not found."`
3. session: clean.
4. mock called: `rb.call_count >= 1`, `cm.called is False`.
5. count: x_gone.

### AMSV-LL-05 — a pending attachment raises unavailable and rolls back
- **Rules:** list_layers R3, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = att("draft.png") but `upload_status "pending"`; link(A2, "scratch", 1).
2. pending X.

**When**
- `svc.list_layers(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=UG.id)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == UNAV`.
3. session: clean.
4. count: x_gone.

### AMSV-LL-06 — a W0 attachment is not found
- **Rules:** list_layers R3; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = att("w0.png") but W0 att; link(A0, "scratch", 1).
2. layer(A0, UG, P1).

**When**
- `svc.list_layers(db, workspace_id=W1.id, attachment_id=A0.id, current_user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A0)`.
3. session: clean.

### AMSV-LL-07 — layers on a private project's attachment are hidden from a plain member
- **Rules:** list_layers R3 [BUG-2115]; PR-3, PR-5 (`current_user_id` is the caller)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. P = proj("Tender") but private.
2. A2 = att("site.png"); link(A2, "project", P.id).
3. layer(A2, U1, P1).
4. pending X.

**When**
- `svc.list_layers(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A2)`.
3. session: clean.
4. count: x_gone.

### AMSV-LL-08 — membership of another private project does not open this one
- **Rules:** list_layers R3 [BUG-2115]; PR-2 (grant held on a different record)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. P = proj("Tender") but private.
2. Q = proj("Bridge") but private.
3. pmem(Q, UG).
4. A2 = att("site.png"); link(A2, "project", P.id).

**When**
- `svc.list_layers(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A2)`.
3. session: clean.

### AMSV-LL-09 — an owner role held only in W2 does not open another member's W1 ticket
- **Rules:** list_layers R3 [BUG-2115]; PR-2, PR-5 (grant held in a different workspace)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. member(UG, "owner", ws=W2).
2. T = ticket("HT-1").
3. A2 = att("ticket.png"); link(A2, "support_ticket", T.id).

**When**
- `svc.list_layers(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A2)`.
3. session: clean.

### AMSV-LL-10 — a project member lists the private project's layers
- **Rules:** list_layers R1; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj("Tender") but private.
2. pmem(P, UG).
3. A2 = att("site.png"); link(A2, "project", P.id).
4. layer(A2, U1, P1).

**When**
- `result = svc.list_layers(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=UG.id)`

**Then**
1. returns: `pairs(result) == {(U1.id, False)}`.

### AMSV-LL-11 — authors' profiles are read together
- **Rules:** list_layers Returns (manager R4) [BUG-2119]
- **Kind:** bug
- **Expect:** xfail BUG-2119
- **Fails today on:** Then 2 (two profile reads per layer)

**Given**
1. U3 = `make_profile(db, name="Lena Roy")`, U4 = `make_profile(db, name="Omar Ali")`, U5 = `make_profile(db, name="Nila Sen")`.
2. layer(A1, U1, P1). layer(A1, U2, P1). layer(A1, U3, P1). layer(A1, U4, P1). layer(A1, U5, P1).
3. recorder.

**When**
- `result = svc.list_layers(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=U1.id)`

**Then**
1. returns: `sorted(i.user_name for i in result.items) == ["Ana Rahman", "Bilal Khan", "Lena Roy", "Nila Sen", "Omar Ali"]`.
2. statement: `profile_reads <= 2`.

### AMSV-LL-12 — the manager's order (oldest update first) is kept
- **Rules:** list_layers R1 (in its order)
- **Kind:** happy
- **Expect:** pass

**Given**
1. L1 = layer(A1, U1, P1).
2. L2 = layer(A1, U2, P1).
3. L3 = layer(A1, UG, P1).
4. older(L1, 2). older(L2, 3). older(L3, 1).

**When**
- `result = svc.list_layers(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=UG.id)`

**Then**
1. returns: `[i.user_id for i in result.items] == [U2.id, U1.id, UG.id]`.

## `AttachmentMarkupService.list_events`

### AMSV-LV-01 — every history entry, only the caller's marked mine
- **Rules:** list_events R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = mev(A1, U1, T1).
2. E2 = mev(A1, UG, T2).

**When**
- `result = svc.list_events(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=UG.id)`

**Then**
1. returns: `type(result).__name__ == "AttachmentMarkupEventListResponse"`.
2. returns: `{(i.id, i.is_mine) for i in result.items} == {(E1.id, False), (E2.id, True)}`.
3. returns: `{i.event_type for i in result.items} == {"markup_saved"}`.

### AMSV-LV-02 — no history gives []
- **Rules:** list_events R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = svc.list_events(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=UG.id)`

**Then**
1. returns: `result.items == []`.

### AMSV-LV-03 — the read commits: a change pending in the session is saved
- **Rules:** list_events R2 (D1)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. mev(A1, U1, T1).
2. pending X.

**When**
- spies: `result = svc.list_events(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=UG.id)`

**Then**
1. returns: `len(result.items) == 1`.
2. mock called: `cm.call_count == 1`, `rb.called is False`.
3. committed: x_kept.

### AMSV-LV-04 — an unknown attachment rolls back and discards pending changes
- **Rules:** list_events R2, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. pending X.

**When**
- spies: `svc.list_events(db, workspace_id=W1.id, attachment_id=MISSING, current_user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == "Attachment 999999999 not found."`
3. session: clean.
4. mock called: `rb.call_count >= 1`, `cm.called is False`.
5. count: x_gone.

### AMSV-LV-05 — history of a private project's attachment is hidden from a plain member
- **Rules:** list_events R2 [BUG-2115]; PR-3, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. P = proj("Tender") but private.
2. A2 = att("site.png"); link(A2, "project", P.id).
3. mev(A2, U1, T1).
4. pending X.

**When**
- `svc.list_events(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A2)`.
3. session: clean.
4. count: x_gone.

### AMSV-LV-06 — authors' profiles are read together
- **Rules:** list_events Returns (manager R4) [BUG-2119]
- **Kind:** bug
- **Expect:** xfail BUG-2119
- **Fails today on:** Then 2 (one profile read per entry)

**Given**
1. mev(A1, U1, T1). mev(A1, U2, T1). mev(A1, UG, T1). mev(A1, U1, T2). mev(A1, U2, T2).
2. recorder.

**When**
- `result = svc.list_events(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=UG.id)`

**Then**
1. returns: `len(result.items) == 5`.
2. statement: `profile_reads <= 2`.

### AMSV-LV-07 — a pending attachment raises unavailable and rolls back
- **Rules:** list_events R2, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = att("draft.png") but `upload_status "pending"`; link(A2, "scratch", 1).
2. pending X.

**When**
- `svc.list_events(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=UG.id)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == UNAV`.
3. session: clean.
4. count: x_gone.

### AMSV-LV-08 — the manager's order (newest first) is kept
- **Rules:** list_events R1 (in its order)
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = mev(A1, U1, T2).
2. E2 = mev(A1, U2, T1).
3. E3 = mev(A1, UG, datetime(2026, 1, 1, 11, 0, 0)).

**When**
- `result = svc.list_events(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=UG.id)`

**Then**
1. returns: `[i.id for i in result.items] == [E3.id, E1.id, E2.id]`.

## `AttachmentMarkupService.put_own_layer`

### AMSV-PL-01 — a first save is committed with a markup_saved event
- **Rules:** put_own_layer R1, R2, TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = svc.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=UG.id, payload=MP(P1), session_id="s-1")`

**Then**
1. returns: `type(result).__name__ == "AttachmentMarkupLayerResponse"`.
2. returns: `result.user_id == UG.id`, `result.is_mine is True`, `result.payload == MP(P1)`.
3. committed: layers_of(A1) has exactly 1 row: `user_id == UG.id`, `payload == D(P1)`.
4. committed: events_of(A1) has exactly 1 row: `event_type == "markup_saved"`, `user_id == UG.id`, `session_id == "s-1"`, `description == "Saved marks on page 1"`.

### AMSV-PL-02 — saving over an existing layer is committed with markup_updated
- **Rules:** put_own_layer R1, TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. L = layer(A1, UG, P1).

**When**
- `result = svc.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=UG.id, payload=MP(P2))`

**Then**
1. returns: `result.payload == MP(P2)`.
2. committed: re-read L: `payload == D(P2)`.
3. committed: events_of(A1) has exactly 1 row: `event_type == "markup_updated"`, `description == "Updated marks on page 2"`.

### AMSV-PL-03 — an empty payload clears the layer, commits markup_cleared and returns None
- **Rules:** put_own_layer R1, Returns (None), TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. layer(A1, UG, P1).

**When**
- `result = svc.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=UG.id, payload=MP(EMPTY), session_id="s-2")`

**Then**
1. returns: `result is None`.
2. committed: layers_of(A1) has 0 rows.
3. committed: events_of(A1) has exactly 1 row: `event_type == "markup_cleared"`, `description == "Cleared marks"`, `metadata_json == {"pages": []}`, `session_id == "s-2"`.

### AMSV-PL-04 — an empty payload with no layer returns None and writes nothing
- **Rules:** put_own_layer R1, Returns (None)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. layer(A1, U1, P1).

**When**
- `result = svc.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=UG.id, payload=MP(EMPTY))`

**Then**
1. returns: `result is None`.
2. nothing written.
3. committed: layers_of(A1) has exactly 1 row: `user_id == U1.id`.

### AMSV-PL-05 — the returned layer is not re-read after the commit
- **Rules:** put_own_layer R2
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. Nothing beyond the standing rows.
2. Order log: `calls = []`; `real_c, real_r = db.commit, db.refresh`; around the When `patch.object(db, "commit", side_effect=lambda: (calls.append("commit"), real_c())[1])` and `patch.object(db, "refresh", side_effect=lambda *a, **k: (calls.append("refresh"), real_r(*a, **k))[1])`.

**When**
- `result = svc.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=UG.id, payload=MP(P1))`

**Then**
1. returns: `result.payload == MP(P1)`.
2. mock called: `calls.count("commit") == 1`.
3. mock called: `"refresh" not in calls[calls.index("commit"):]`.
4. committed: `result.updated_at == layers_of(A1)[0].updated_at`.

### AMSV-PL-06 — an unknown attachment rolls back and discards pending changes
- **Rules:** put_own_layer R3, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. pending X.

**When**
- spies: `svc.put_own_layer(db, workspace_id=W1.id, attachment_id=MISSING, user_id=UG.id, payload=MP(P1))`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == "Attachment 999999999 not found."`
3. session: clean.
4. mock called: `rb.call_count >= 1`, `cm.called is False`.
5. count: x_gone.
6. nothing written.

### AMSV-PL-07 — a failing commit leaves no layer and no event
- **Rules:** put_own_layer R3, TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- failing commit: `svc.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=UG.id, payload=MP(P1))`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. nothing written.

### AMSV-PL-08 — a private project's attachment refuses a plain member; nothing written
- **Rules:** put_own_layer R1, R3 [BUG-2115]; PR-3, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the layer is saved)

**Given**
1. P = proj("Tender") but private.
2. A2 = att("site.png"); link(A2, "project", P.id).

**When**
- `svc.put_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id, payload=MP(P1))`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A2)`.
3. session: clean.
4. nothing written.

### AMSV-PL-09 — an owner role held only in W0 does not open another member's W1 ticket
- **Rules:** put_own_layer R3 [BUG-2115]; PR-2, PR-5 (grant held in a different workspace)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the layer is saved)

**Given**
1. member(UG, "owner", ws=W0).
2. T = ticket("HT-1").
3. A2 = att("ticket.png"); link(A2, "support_ticket", T.id).

**When**
- `svc.put_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id, payload=MP(P1))`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A2)`.
3. session: clean.
4. nothing written.

### AMSV-PL-10 — a concurrent first save becomes an update, committed, no error
- **Rules:** put_own_layer R3 (manager R5a) [BUG-2120]
- **Kind:** bug
- **Expect:** xfail BUG-2120
- **Author:** claude
- **Fails today on:** Then 1 (the call raises IntegrityError 23505)

**Given**
1. L = layer(A1, UG, P1).
2. Race simulation (see Conventions) around the When.

**When**
- `result = svc.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=UG.id, payload=MP(P2))`

**Then**
1. returns: `result.payload == MP(P2)`.
2. committed: layers_of(A1) has exactly 1 row: `payload == D(P2)`.
3. committed: events_of(A1) has exactly 1 row: `event_type == "markup_updated"`.

### AMSV-PL-11 — saving the stored payload again commits no event
- **Rules:** put_own_layer R1 (manager R7a) [BUG-2118]
- **Kind:** bug
- **Expect:** xfail BUG-2118
- **Fails today on:** Then 2 (a markup_updated event is written)

**Given**
1. layer(A1, UG, P1).

**When**
- `result = svc.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=UG.id, payload=MP(P1))`

**Then**
1. returns: `result.payload == MP(P1)`.
2. committed: events_of(A1) has 0 rows.

### AMSV-PL-12 — a pending attachment raises unavailable; nothing written, rolled back
- **Rules:** put_own_layer R3, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = att("draft.png") but `upload_status "pending"`; link(A2, "scratch", 1).
2. pending X.

**When**
- `svc.put_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id, payload=MP(P1))`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == UNAV`.
3. session: clean.
4. count: x_gone.
5. nothing written.

## `AttachmentMarkupService.delete_own_layer`

### AMSV-DL-01 — the caller's layer is deleted and markup_cleared committed
- **Rules:** delete_own_layer R1, TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. layer(A1, U1, P1).
2. layer(A1, UG, P2).

**When**
- `result = svc.delete_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=UG.id, session_id="s-3")`

**Then**
1. returns: `result is None`.
2. committed: layers_of(A1) has exactly 1 row: `user_id == U1.id`.
3. committed: events_of(A1) has exactly 1 row: `event_type == "markup_cleared"`, `user_id == UG.id`, `session_id == "s-3"`, `description == "Cleared marks"`.

### AMSV-DL-02 — no own layer: nothing deleted, no event, no error
- **Rules:** delete_own_layer R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. layer(A1, U1, P1).

**When**
- `result = svc.delete_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=UG.id)`

**Then**
1. returns: `result is None`.
2. nothing written.
3. committed: layers_of(A1) has exactly 1 row: `user_id == U1.id`.

### AMSV-DL-03 — an unknown attachment rolls back and discards pending changes
- **Rules:** delete_own_layer R2, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. layer(A1, UG, P1).
2. pending X.

**When**
- spies: `svc.delete_own_layer(db, workspace_id=W1.id, attachment_id=MISSING, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == "Attachment 999999999 not found."`
3. session: clean.
4. mock called: `rb.call_count >= 1`, `cm.called is False`.
5. count: x_gone.
6. nothing written.

### AMSV-DL-04 — a failing commit keeps the layer and writes no event
- **Rules:** delete_own_layer R2, TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. L = layer(A1, UG, P1).

**When**
- failing commit: `svc.delete_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=UG.id)`

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read L: `payload == D(P1)`.
4. nothing written.

### AMSV-DL-05 — a private project's attachment refuses a plain member; layer kept
- **Rules:** delete_own_layer R1, R2 [BUG-2115]; PR-3, PR-5
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the layer is deleted)

**Given**
1. P = proj("Tender") but private.
2. A2 = att("site.png"); link(A2, "project", P.id).
3. L = layer(A2, UG, P1).

**When**
- `svc.delete_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`.
2. raises: `str(exc.value) == NFA(A2)`.
3. session: clean.
4. re-read L: `payload == D(P1)`.
5. nothing written.

### AMSV-DL-06 — a project member clears their layer on the private project's attachment
- **Rules:** delete_own_layer R1; PR-2, PR-5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj("Tender") but private.
2. pmem(P, UG).
3. A2 = att("site.png"); link(A2, "project", P.id).
4. layer(A2, UG, P1).

**When**
- `result = svc.delete_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. returns: `result is None`.
2. committed: layers_of(A2) has 0 rows.
3. committed: events_of(A2) has exactly 1 row: `event_type == "markup_cleared"`.

### AMSV-DL-07 — a pending attachment raises unavailable; layer kept, rolled back
- **Rules:** delete_own_layer R2, TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = att("draft.png") but `upload_status "pending"`; link(A2, "scratch", 1).
2. L = layer(A2, UG, P1).
3. pending X.

**When**
- `svc.delete_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentValidationError`.
2. raises: `str(exc.value) == UNAV`.
3. session: clean.
4. count: x_gone.
5. re-read L: `payload == D(P1)`.
6. nothing written.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview: endpoint mapping | `app/api/v1/endpoints/attachments.py` (integration) | `AttachmentNotFoundError` → 404, `AttachmentValidationError` / `ValueError` on PUT → 400 |
| put_own_layer Returns (None → 204) | `PUT …/markups/me` (integration) | a cleared layer answers 204 |
| put_own_layer R3 (BUG-2120 race) | integration | two committed concurrent first saves |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `list_layers` | R1 | AMSV-LL-01, AMSV-LL-02, AMSV-LL-10, AMSV-LL-12 |
| | R2 (D1) | AMSV-LL-03 |
| | R3, TC3 | AMSV-LL-04, AMSV-LL-05, AMSV-LL-06 |
| | R3 [BUG-2115] | AMSV-LL-07, AMSV-LL-08, AMSV-LL-09 |
| | Returns [BUG-2119] | AMSV-LL-11 |
| `list_events` | R1 | AMSV-LV-01, AMSV-LV-02, AMSV-LV-08 |
| | R2 (commit, D1) | AMSV-LV-03 |
| | R2 (errors), TC3 | AMSV-LV-04, AMSV-LV-07 |
| | R2 [BUG-2115] | AMSV-LV-05 |
| | Returns [BUG-2119] | AMSV-LV-06 |
| `put_own_layer` | R1, TC1 | AMSV-PL-01, AMSV-PL-02, AMSV-PL-03, AMSV-PL-04 |
| | R1 [BUG-2118] | AMSV-PL-11 |
| | R2 | AMSV-PL-01, AMSV-PL-05 |
| | R3, TC3 | AMSV-PL-06, AMSV-PL-12 |
| | R3 [BUG-2115] | AMSV-PL-08, AMSV-PL-09 |
| | R3 [BUG-2120] | AMSV-PL-10 |
| | R3, TC4 | AMSV-PL-07 |
| `delete_own_layer` | R1, TC1 | AMSV-DL-01, AMSV-DL-02, AMSV-DL-06 |
| | R1 [BUG-2115] | AMSV-DL-05 |
| | R2, TC3 | AMSV-DL-03, AMSV-DL-07 |
| | R2, TC4 | AMSV-DL-04 |
