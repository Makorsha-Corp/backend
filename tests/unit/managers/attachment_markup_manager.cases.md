# Test cases — `app/managers/attachment_markup_manager.py`

> **Spec:** `tests/unit/managers/attachment_markup_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — spec fill-gaps 2026-11-04 (gaps 1–4 closed): PR-5 (no `role` parameter; the manager reads the active role and `is_platform_admin`; `_get_ready_attachment` gains required `user_id`) → `role=` dropped from every card, pass cards of the helper call it through `call_uid`, scratch links added to pass cards that reach R3 / R4; granted callers on public methods (LL-11, PL-20, DL-11) now pass today; GR-37 / 40 / 45 callers hold their role in the database; new GR-46…63 (machine / item parents, suspended / inactive / other-workspace roles, PR-3 link rule, non-member caller), SP-11 (scribbles), LL-13, PL-28, PL-29, DL-13.
> **Revision:** 3 — executor notes (2026-11-04): Conventions import fixed (`MARKUP_UNAVAILABLE_MSG` is a class attribute of `AttachmentMarkupManager`); PL-21 Fails-today line names the `AttachmentValidationError` raised today. No card added or removed.
> **Revision:** 4 — verifier findings 1–3 and spec G5 / BUG-2103 (2026-11-04). New cards:
> - GR-64 / GR-65: a platform admin is refused a private project and its component; LL-14 checks the same through a public method.
> - GR-66 / GR-67: a W1-filed link to a W2 / W0 help ticket is hidden.
> - GR-68: the workspace owner with a plain role opens another member's ticket (BUG-2103).
> - PL-30 / DL-14: the caller's W2-filed markup row is neither replaced nor deleted.
> - PL-31 (G5): page "Updated marks" gives "Saved marks on page Updated marks".
>
> One new spec gap (5).
> **Counts:** 202 cases · 97 expected-to-pass · 105 expected-to-fail (bugs: 103 strict, 2 non-strict) · 4 deferred

## Reviewer summary
- **Depth:** full. The module writes no stock or money, but it holds the visibility rule for marks (BUG-2115) and the stamp check (BUG-2116 / BUG-2117), both with real decisions.
- **Per callable:** `_get_ready_attachment` 68 (58 bug) · `_is_markupable` 10 · `_resolve_user_name` 3 · `_resolve_saved_stamp` 33 (20 bug) · `_summarize_payload` 11 · `_log_markup_event` 2 · `_to_layer_response` 3 · `_to_event_response` 2 · `list_layers` 14 (7 bug) · `list_events` 11 (5 bug) · `put_own_layer` 31 (11 bug) · `delete_own_layer` 14 (4 bug).
- **Notable design choices:**
  - The full PR-1 / PR-2 matrix (each refused shape, each grant, each refused-grant shape, both workspace sides, ids that exist only in another table) is on `_get_ready_attachment`, where R5 puts the check. Each public method gets the five most telling shapes (private project, other member's ticket, deleted parent, W2 parent, same id in another table), one granted caller, and its own `session:` checks.
  - PR-5: no card passes a role; the caller's role is whatever their `workspace_members` row in W1 says when `active`. The helper's new required `user_id` makes its BUG-2115 cards fail today with `TypeError`; its pass cards call it through `call_uid` so they hold before and after the fix. Public methods keep their signatures: their refusal cards fail today because nothing is refused, and their granted-caller cards (LL-11, PL-20, DL-11) pass today and after.
  - Every pass card that must reach R3 / R4 gives its attachment a `scratch` link, so the fix (no own-workspace link → 404) does not turn it into a not-found.
  - Machine and item parents are built as real rows (spec Facts); orders and invoices still appear only as unknown ids (they need status / account rows, and the machine cards already test the workspace-wide branch).
  - The BUG-2120 card patches the markup DAO's `get_for_user` (a race simulation, Author: claude).
  - Order cards with ties are non-strict xfail (BUG-1435, BUG-1436). The strict `ORDER BY` alarms already sit in the DAO cases, so none are repeated here.
- **BUG-2103:** only the helper card GR-68 checks it. A public-method card would pass today, because nothing is checked, so a strict xfail would XPASS.
- **Needs a decision:** Spec gap 5 (the caller's W2-filed markup row and the unique constraint). PL-30 checks only that the row is never replaced.

## Conventions for this module

**IDs.** `AMUP` = `app/managers/attachment_markup_manager.py` (`AMK` is the markup DAO's; `ATCM` / `MOBS` are the sibling managers'). `GR` _get_ready_attachment · `IM` _is_markupable · `UN` _resolve_user_name · `SS` _resolve_saved_stamp · `SP` _summarize_payload · `LE` _log_markup_event · `TL` _to_layer_response · `TE` _to_event_response · `LL` list_layers · `LV` list_events · `PL` put_own_layer · `DL` delete_own_layer.

**Imports.** `from app.managers.attachment_markup_manager import AttachmentMarkupManager, attachment_markup_manager`; the message constant is the class attribute `AttachmentMarkupManager.MARKUP_UNAVAILABLE_MSG` (not a module name); `from app.managers.attachment_manager import AttachmentNotFoundError, AttachmentValidationError`. Models (`app.models.<module>`): `attachment.Attachment`, `attachment_link.AttachmentLink`, `attachment_markup.AttachmentMarkup`, `attachment_markup_event.AttachmentMarkupEvent`, `project.Project`, `project_member.ProjectMember`, `project_component.ProjectComponent`, `help_ticket.HelpTicket`, `factory.Factory`, `workspace_member.WorkspaceMember`, `machine.Machine`, `item.Item`. `MarkupPayload` (`app.schemas.attachment_markup`). `ValidationError` (`pydantic`), `IntegrityError` (`sqlalchemy.exc`), `event`, `text` (`sqlalchemy`), `patch` (`unittest.mock`), `datetime`, `os`, `inspect`.

**Fixed values.** `M` = `attachment_markup_manager`. `db` = the real session, always first; other arguments by keyword except `_resolve_user_name(db, uid)` / `_resolve_saved_stamp(db, uid)` (positional). The session does not autoflush. `result` = what the When returns. MISSING = `999999999`. XID(k) = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`; "`id XID(k)`" passes `id=XID(k)` to the builder. T0 = `datetime(2025, 12, 1, 8, 0, 0)`, T1 = `datetime(2026, 1, 1, 9, 0, 0)`, T2 = `datetime(2026, 1, 1, 10, 0, 0)`. NF(A) = `f"Attachment {A.id} not found."`. UNAV = `"Markup is only available for images and PDFs."`.

**Settings (every test)**, `monkeypatch.setattr(settings, …)` on `app.core.config.settings`: `CLOUDINARY_UPLOAD_ENV "development"`, `ENVIRONMENT "development"`, `CLOUDINARY_CLOUD_NAME "demo-cloud"`, `CLOUDINARY_API_KEY "123456"`, `CLOUDINARY_API_SECRET "s3cret"`. A Given line "settings: NAME value" overrides one. **Externals:** none are patched (the spec names none; the URL builder makes no network call).

**Standing rows** (every test, in this order, flushed, no Given line): W0, W1, W2 = `make_workspace(db)` (W0.id < W1.id < W2.id). U1 = `make_profile(db, name="Ana Rahman")`, U2 = `make_profile(db, name="Bilal Khan")`, UG = `make_profile(db, name="Mia Khan")` (U1.id < U2.id < UG.id). member(U1, "ground-team"), member(U2, "owner"), member(UG, "ground-team"). F0 / F1 / F9 = `Factory(workspace_id=W0.id / W1.id / W2.id, name="Factory Zero" / "Factory One" / "Factory Nine", abbreviation="F0" / "F1" / "F9")`. A1 = att("plan.png"), then link(A1, "scratch", 1). No workspace has `owner_user_id`.

**Given rows** (built directly, added and flushed one at a time in the order written; after "but" every differing column):
- **member(U, role, status="active", ws=W1)** = `WorkspaceMember(workspace_id=ws.id, user_id=U.id, role=role, status=status)`. A removed member is `status "inactive"`.
- **att(name)** = `Attachment(workspace_id=W1.id, file_name=name, mime_type="image/png", file_size=100, uploaded_by=U1.id, upload_status="ready", format="png")`. **deleted att** = also `is_deleted True`, `deleted_by U1.id`.
- **link(A, type, eid)** = `AttachmentLink(workspace_id=A.workspace_id, attachment_id=A.id, entity_type=type, entity_id=eid, linked_by=U1.id)`.
- **proj(name)** = `Project(workspace_id=W1.id, factory_id=F1.id, name=name, description="Main", created_by=U1.id, visibility="workspace")`. **private** = `visibility "invited_only"`. **deleted** = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. **W0 proj** = `workspace_id W0.id`, `factory_id F0.id`; **W2 proj** = `workspace_id W2.id`, `factory_id F9.id`.
- **pmem(P, U)** = `ProjectMember(workspace_id=P.workspace_id, project_id=P.id, user_id=U.id, assigned_by=U1.id)`. **comp(P, name)** = `ProjectComponent(workspace_id=P.workspace_id, project_id=P.id, name=name)`.
- **mach(name)** = `Machine(workspace_id=W1.id, name=name, factory_id=F1.id)`. **W0 mach** = `workspace_id W0.id`, `factory_id F0.id`; **W2 mach** = `workspace_id W2.id`, `factory_id F9.id`; **deleted mach** = `is_deleted True`. **item(name)** = `Item(workspace_id=W1.id, name=name, name_normalized=name.lower(), unit="pcs")`.
- **ticket(n)** = `HelpTicket(workspace_id=W1.id, ticket_number=n, title="Printer jam", description="It jams", created_by=U1.id)`.
- **set_owner(W, U)** = `W.owner_user_id = U.id`, `db.flush()`. **admin(U)** = `U.is_platform_admin = True`, `db.flush()`. **stamp(U, v)** = `U.saved_stamp = v`, `db.flush()`.
- **layer(A, U, P)** = `AttachmentMarkup(workspace_id=A.workspace_id, attachment_id=A.id, user_id=U.id, payload=D(P))`. **mev(A, U, at)** = `AttachmentMarkupEvent(workspace_id=A.workspace_id, attachment_id=A.id, user_id=U.id, event_type="markup_saved", description="seed", created_at=at)`.
- **older(X, h)** = `db.execute(text("UPDATE attachment_markups SET updated_at = now() - make_interval(hours => :h) WHERE id = :i"), {"h": h, "i": X.id})`, then `db.expire_all()`. **seqscan** = `SET LOCAL enable_indexscan = off`, `SET LOCAL enable_bitmapscan = off`, `SET LOCAL enable_indexonlyscan = off` (each `db.execute(text(...))`). **touchL(X)** / **touchE(X)** = `UPDATE attachment_markups SET user_id = user_id WHERE id = :i` / `UPDATE attachment_markup_events SET description = 'seed' WHERE id = :i`, then `db.expire_all()`.

**Payloads.** PT = `{"x": 0.1, "y": 0.2}`. STROKE = `{"color": "#ff0000", "width": 0.5, "points": [PT]}`. BARE = STROKE but `"points": []`. TEXT = `{"x": 0.1, "y": 0.1, "text": "OK", "color": "#000000", "size": 0.05}`. STAMPM = `{"id": None, "x": 0.5, "y": 0.5, "width": 0.1, "height": 0.1}`. SCRIB = `{"color": "#f00", "width": 0.01, "points": [PT]}` (a scribble is a MarkupStroke); SCRIB0 = SCRIB but `"points": []`. **MP(d)** = `MarkupPayload.model_validate({"pages": d})`; **D(d)** = `MP(d).model_dump()`. P1 = `{"1": {"strokes": [STROKE]}}`. P2 = `{"2": {"texts": [TEXT]}}`. P12 = `{"1": {"strokes": [STROKE]}, "2": {"stamps": [STAMPM]}}`. EMPTY = `{}`. EMPTYPAGE = `{"1": {"strokes": [], "texts": [], "scribbles": [], "stamps": []}}`.

**Stamps.** TOKEN = `"0123456789abcdef0123456789abcdef"`; TOKEN31 = `TOKEN[:31]`; TOKEN33 = `TOKEN + "0"`; TOKENU = `TOKEN.upper()`; TOKENG = `TOKEN[:31] + "g"`. OWN(U) = `f"development/profiles/{U.id}/stamp-" + TOKEN` (the profile_stamp_manager cases' minted form); PROD(U) = `f"profiles/{U.id}/stamp-" + TOKEN`. IMG(pid) = `{"kind": "image", "public_id": pid, "url": "https://tracker.example/p.png", "width": 10, "height": 10}`. VEC = `{"kind": "vector", "strokes": [{"color": "#000000", "width": 0.5, "points": []}], "viewBox": {"width": 100, "height": 50}}`. URLP = `"https://res.cloudinary.com/demo-cloud/image/authenticated/"`.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **NOW_DB** = `db.scalar(text("SELECT now()"))`.
- **layers_of(A)** / **events_of(A)** = `db.expire_all()`, then every `attachment_markups` / `attachment_markup_events` row with `attachment_id == A.id`, ordered by `id`.
- **nothing written** = the numbers of rows of `attachment_markups` and `attachment_markup_events` (all workspaces) equal their values before the call.
- `session:` lines check `db` right after the call, before any re-read or count: `not db.new`, `not db.dirty`, `not db.deleted`.
- `raises: E` = `with pytest.raises(E) as exc:` around the call; then `str(exc.value) == …`. `type(exc.value) is E` where stated.
- **recorder** = Given step `stmts = []`, `event.listen(db.connection(), "before_cursor_execute", rec)` appending `statement`; `event.remove` right after the When. **profile_reads** = number of recorded statements that start with `SELECT` and contain `FROM profiles`. **markup_reads** = number of recorded statements that contain `attachment_markups`.
- **uids(x)** = `[r.user_id for r in x]`; **eids(x)** = `[r.id for r in x]`; order is part of the check.
- **Rolled back** (one per writer) = `with patch.object(db, "commit", wraps=db.commit) as cm:` around `sp = db.begin_nested()`, the call, `sp.rollback()`; then the Then lines.

**PR calls** (PR-5; no method takes a role). The manager reads the caller's role from their W1 `workspace_members` row when `status "active"` (else none) and `profiles.is_platform_admin`. `_get_ready_attachment` gains a required keyword `user_id` (BUG-2115, strict xfail: `TypeError` today); the public methods pass their existing `current_user_id` / `user_id`. **call_uid(fn, uid, **kw)** = `fn(db, user_id=uid, **kw)` when `"user_id" in inspect.signature(fn).parameters`, else `fn(db, **kw)`; used by the helper's pass cards so they hold before and after the fix.

**xfail cards.** Strict: `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. Write the call as shown.

**Race simulations.** AMUP-PL-25 (put_own_layer R5a, BUG-2120): `patch("app.dao.attachment_markup.AttachmentMarkupDAO.get_for_user", return_value=None)` around the When, so the save takes the insert path while the user's layer exists.

## `AttachmentMarkupManager._get_ready_attachment`

### AMUP-GR-01 — a ready image of the caller's workspace is returned
- **Rules:** _get_ready_attachment R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A2 = att("photo.png"), then link(A2, "scratch", 2). A3 = att("other.png") (built after A2).

**When**
- `result = call_uid(M._get_ready_attachment, UG.id, workspace_id=W1.id, attachment_id=A2.id)`

**Then**
1. returns: `result.id == A2.id`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.

### AMUP-GR-02 — a ready PDF known only by its format is returned
- **Rules:** _get_ready_attachment R1; _is_markupable R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A2 = att("scan.bin") but `mime_type "application/octet-stream"`, `format "PDF"`, then link(A2, "scratch", 2).

**When**
- `result = call_uid(M._get_ready_attachment, UG.id, workspace_id=W1.id, attachment_id=A2.id)`

**Then**
1. returns: `result.id == A2.id`.

### AMUP-GR-03 — an unknown id is not found
- **Rules:** _get_ready_attachment R2; Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No extra rows.

**When**
- `call_uid(M._get_ready_attachment, UG.id, workspace_id=W1.id, attachment_id=MISSING)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == "Attachment 999999999 not found."`.

### AMUP-GR-04 — a soft-deleted attachment is not found
- **Rules:** _get_ready_attachment R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AD = deleted att("gone.png").

**When**
- `call_uid(M._get_ready_attachment, UG.id, workspace_id=W1.id, attachment_id=AD.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(AD)`.

### AMUP-GR-05 — an attachment of W0 (lower workspace id) is not found from W1
- **Rules:** _get_ready_attachment R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = att("zero.png") but `workspace_id W0.id`.

**When**
- `call_uid(M._get_ready_attachment, UG.id, workspace_id=W1.id, attachment_id=A0.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A0)`.

### AMUP-GR-06 — an attachment of W2 (higher workspace id) is not found from W1
- **Rules:** _get_ready_attachment R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A9 = att("far.png") but `workspace_id W2.id`.

**When**
- `call_uid(M._get_ready_attachment, UG.id, workspace_id=W1.id, attachment_id=A9.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A9)`.

### AMUP-GR-07 — a pending image is refused as unavailable
- **Rules:** _get_ready_attachment R3; Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = att("wait.png") but `upload_status "pending"`, then link(A2, "scratch", 2).

**When**
- `call_uid(M._get_ready_attachment, UG.id, workspace_id=W1.id, attachment_id=A2.id)`

**Then**
1. raises: `AttachmentValidationError`, `str(exc.value) == "Markup is only available for images and PDFs."`.

### AMUP-GR-08 — a failed PDF is refused as unavailable
- **Rules:** _get_ready_attachment R3
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = att("bad.pdf") but `mime_type "application/pdf"`, `format "pdf"`, `upload_status "failed"`, then link(A2, "scratch", 2).

**When**
- `call_uid(M._get_ready_attachment, UG.id, workspace_id=W1.id, attachment_id=A2.id)`

**Then**
1. raises: `AttachmentValidationError`, `str(exc.value) == UNAV`.

### AMUP-GR-09 — a ready CSV is refused as unavailable
- **Rules:** _get_ready_attachment R4
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = att("data.csv") but `mime_type "text/csv"`, `format "csv"`, then link(A2, "scratch", 2).

**When**
- `call_uid(M._get_ready_attachment, UG.id, workspace_id=W1.id, attachment_id=A2.id)`

**Then**
1. raises: `AttachmentValidationError`, `str(exc.value) == UNAV`.

### AMUP-GR-10 — a ready .docx is refused as unavailable
- **Rules:** _get_ready_attachment R4
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = att("spec.docx") but `mime_type "application/vnd.openxmlformats-officedocument.wordprocessingml.document"`, `format "docx"`, then link(A2, "scratch", 2).

**When**
- `call_uid(M._get_ready_attachment, UG.id, workspace_id=W1.id, attachment_id=A2.id)`

**Then**
1. raises: `AttachmentValidationError`, `str(exc.value) == UNAV`.

### AMUP-GR-11 — a private project's attachment is hidden from a plain member
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-2
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. P = proj("Tender 7"), private.
2. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-12 — the private project's creator opens its attachment
- **Rules:** _get_ready_attachment R5 [BUG-2115], R1
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. P = proj("Tender 7"), private (`created_by U1.id`).
2. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `result = M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U1.id)`

**Then**
1. returns: `result.id == A2.id`.

### AMUP-GR-13 — a project member opens the private project's attachment
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. P = proj("Tender 7"), private.
2. pmem(P, UG).
3. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `result = M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. returns: `result.id == A2.id`.

### AMUP-GR-14 — an active workspace owner-role member opens it
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. P = proj("Tender 7"), private.
2. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `result = M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. returns: `result.id == A2.id`.

### AMUP-GR-15 — an active ground-team-manager opens it
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. U3 = `make_profile(db, name="Rafi Das")`; member(U3, "ground-team-manager").
2. P = proj("Tender 7"), private.
3. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `result = M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U3.id)`

**Then**
1. returns: `result.id == A2.id`.

### AMUP-GR-16 — the workspace owner with no membership opens it
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. U3 = `make_profile(db, name="Rafi Das")` (no membership row); set_owner(W1, U3).
2. P = proj("Tender 7"), private.
3. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `result = M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U3.id)`

**Then**
1. returns: `result.id == A2.id`.

### AMUP-GR-17 — owning W0 does not open a W1 private project's attachment
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. set_owner(W0, UG).
2. P = proj("Tender 7"), private.
3. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-18 — owning W2 does not open a W1 private project's attachment
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. set_owner(W2, UG).
2. P = proj("Tender 7"), private.
3. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-19 — owner role only in W0 does not open it
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. member(UG, "owner", ws=W0).
2. P = proj("Tender 7"), private.
3. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-20 — ground-team-manager only in W2 does not open it
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. member(UG, "ground-team-manager", ws=W2).
2. P = proj("Tender 7"), private.
3. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-21 — a suspended owner-role member does not open it
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. U3 = `make_profile(db, name="Rafi Das")`; member(U3, "owner", status="suspended").
2. P = proj("Tender 7"), private.
3. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U3.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-22 — membership of other private projects (lower and higher id) does not open this one
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. PA = proj("Alpha"), private; pmem(PA, UG).
2. P = proj("Tender 7"), private.
3. PB = proj("Beta"), private; pmem(PB, UG).
4. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-23 — having created other projects (lower and higher id) does not open this one
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. PA = proj("Alpha"), private, but `created_by UG.id`.
2. P = proj("Tender 7"), private.
3. PB = proj("Beta"), private, but `created_by UG.id`.
4. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-24 — a private project with no creator stays closed to a plain member
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. P = proj("Tender 7"), private, but `created_by None`.
2. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-25 — a workspace-visible project's attachment is open to a plain member
- **Rules:** _get_ready_attachment R5 [BUG-2115], R1
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. P = proj("Open Job").
2. A2 = att("open.png"), then link(A2, "project", P.id).

**When**
- `result = M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. returns: `result.id == A2.id`.

### AMUP-GR-26 — a component of a private project is hidden from a plain member
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-2 (component)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. P = proj("Tender 7"), private.
2. C = comp(P, "Roof").
3. A2 = att("roof.png"), then link(A2, "project_component", C.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-27 — a member of the private project opens its component's attachment
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. P = proj("Tender 7"), private.
2. pmem(P, UG).
3. C = comp(P, "Roof").
4. A2 = att("roof.png"), then link(A2, "project_component", C.id).

**When**
- `result = M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. returns: `result.id == A2.id`.

### AMUP-GR-28 — a deleted project's attachment is hidden even from its creator
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-1
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. P = proj("Old Job"), deleted.
2. A2 = att("old.png"), then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U1.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-29 — a live component of a deleted project is hidden
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-1
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. P = proj("Old Job"), deleted.
2. C = comp(P, "Roof").
3. A2 = att("roof.png"), then link(A2, "project_component", C.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-30 — a link to a W0 project is hidden
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-1, HR-16
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. P0 = proj("Zero Job"), W0 proj.
2. A2 = att("zero.png"), then link(A2, "project", P0.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-31 — a link to a W2 project is hidden
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-1, HR-16
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. P9 = proj("Far Job"), W2 proj.
2. A2 = att("far.png"), then link(A2, "project", P9.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-32 — a project id that exists only as a W1 help ticket is hidden
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-1
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. T = ticket("HT-1") but `id XID(1)` (no project has id XID(1)).
2. A2 = att("x.png"), then link(A2, "project", XID(1)).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-33 — a ticket id that exists only as a W1 project is hidden
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-1
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. P = proj("Open Job") but `id XID(2)` (no help ticket has id XID(2)).
2. A2 = att("x.png"), then link(A2, "support_ticket", XID(2)).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-34 — an unknown purchase order id is hidden
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-1
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. A2 = att("po.png"), then link(A2, "purchase_order", MISSING).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-35 — another member's help ticket is hidden from a plain member
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-2 (ticket)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. T = ticket("HT-1") (`created_by U1.id`).
2. A2 = att("shot.png"), then link(A2, "support_ticket", T.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-36 — the ticket's creator opens its attachment
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. T = ticket("HT-1").
2. A2 = att("shot.png"), then link(A2, "support_ticket", T.id).

**When**
- `result = M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U1.id)`

**Then**
1. returns: `result.id == A2.id`.

### AMUP-GR-37 — an active owner-role member opens another member's ticket
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. T = ticket("HT-1") (`created_by U1.id`; U2 is member(U2, "owner")).
2. A2 = att("shot.png"), then link(A2, "support_ticket", T.id).

**When**
- `result = M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. returns: `result.id == A2.id`.

### AMUP-GR-38 — a platform admin opens another member's ticket
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. admin(UG).
2. T = ticket("HT-1").
3. A2 = att("shot.png"), then link(A2, "support_ticket", T.id).

**When**
- `result = M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. returns: `result.id == A2.id`.

### AMUP-GR-39 — creating other tickets (lower and higher id) does not open this one
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. TA = ticket("HT-1") but `created_by UG.id`.
2. T = ticket("HT-2").
3. TB = ticket("HT-3") but `created_by UG.id`.
4. A2 = att("shot.png"), then link(A2, "support_ticket", T.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-40 — a ticket with no creator is hidden from a member whose role is "Owner" (capital O)
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. U3 = `make_profile(db, name="Rafi Das")`; member(U3, "Owner").
2. T = ticket("HT-1") but `created_by None`.
3. A2 = att("shot.png"), then link(A2, "support_ticket", T.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U3.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-41 — one hidden link among two hides the attachment (hidden link first)
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-3 "any link"
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. PP = proj("Tender 7"), private. PO = proj("Open Job").
2. A2 = att("both.png"), then link(A2, "project", PP.id), then link(A2, "project", PO.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-42 — one hidden link among two hides the attachment (hidden link second)
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-3 "any link"
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. PP = proj("Tender 7"), private. PO = proj("Open Job").
2. A2 = att("both.png"), then link(A2, "project", PO.id), then link(A2, "project", PP.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-43 — a hidden attachment that is also pending answers not found, not unavailable
- **Rules:** _get_ready_attachment R5 [BUG-2115] (checked before R3)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. P = proj("Tender 7"), private.
2. A2 = att("wait.png") but `upload_status "pending"`, then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `type(exc.value) is AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-44 — a hidden CSV answers not found, not unavailable
- **Rules:** _get_ready_attachment R5 [BUG-2115] (checked before R4)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. P = proj("Tender 7"), private.
2. A2 = att("data.csv") but `mime_type "text/csv"`, `format "csv"`, then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `type(exc.value) is AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-45 — an active ground-team-manager opens another member's ticket
- **Rules:** _get_ready_attachment R5 [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. U3 = `make_profile(db, name="Rafi Das")`; member(U3, "ground-team-manager").
2. T = ticket("HT-1").
3. A2 = att("shot.png"), then link(A2, "support_ticket", T.id).

**When**
- `result = M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U3.id)`

**Then**
1. returns: `result.id == A2.id`.

### AMUP-GR-46 — a live W1 machine's attachment is open to a plain member
- **Rules:** _get_ready_attachment R5 [BUG-2115], R1; PR-2 (workspace-wide type)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. MC = mach("Lathe 1").
2. A2 = att("lathe.png"), then link(A2, "machine", MC.id).

**When**
- `result = M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. returns: `result.id == A2.id`.

### AMUP-GR-47 — a deleted machine's attachment is hidden even from an owner-role member
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-1
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. MC = mach("Lathe 1"), deleted mach.
2. A2 = att("lathe.png"), then link(A2, "machine", MC.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-48 — a link to a W0 machine is hidden
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-1, HR-16
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. M0 = mach("Zero Lathe"), W0 mach.
2. A2 = att("lathe.png"), then link(A2, "machine", M0.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-49 — a link to a W2 machine is hidden
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-1, HR-16
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. M9 = mach("Far Lathe"), W2 mach.
2. A2 = att("lathe.png"), then link(A2, "machine", M9.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-50 — a machine id that exists only as a W1 item is hidden
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-1
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. IT = item("Bolt") but `id XID(5)` (no machine has id XID(5)).
2. A2 = att("bolt.png"), then link(A2, "machine", XID(5)).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-51 — a live W1 item's attachment is open to a plain member
- **Rules:** _get_ready_attachment R5 [BUG-2115], R1; PR-2 (workspace-wide type)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. IT = item("Bolt").
2. A2 = att("bolt.png"), then link(A2, "item", IT.id).

**When**
- `result = M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. returns: `result.id == A2.id`.

### AMUP-GR-52 — a suspended ground-team-manager does not open a private project's attachment
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-5 (active membership only)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. U3 = `make_profile(db, name="Rafi Das")`; member(U3, "ground-team-manager", status="suspended").
2. P = proj("Tender 7"), private.
3. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U3.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-53 — a removed (inactive) owner-role member does not open a private project's attachment
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-5 (active membership only)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. U3 = `make_profile(db, name="Rafi Das")`; member(U3, "owner", status="inactive").
2. P = proj("Tender 7"), private.
3. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U3.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-54 — owner role only in W2 does not open a private project's attachment
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-5 (role of this workspace)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. member(UG, "owner", ws=W2).
2. P = proj("Tender 7"), private.
3. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-55 — a suspended owner-role member does not open another member's ticket
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-5 (active membership only)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. U3 = `make_profile(db, name="Rafi Das")`; member(U3, "owner", status="suspended").
2. T = ticket("HT-1") (`created_by U1.id`).
3. A2 = att("shot.png"), then link(A2, "support_ticket", T.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U3.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-56 — a removed (inactive) ground-team-manager does not open another member's ticket
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-5 (active membership only)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. U3 = `make_profile(db, name="Rafi Das")`; member(U3, "ground-team-manager", status="inactive").
2. T = ticket("HT-1") (`created_by U1.id`).
3. A2 = att("shot.png"), then link(A2, "support_ticket", T.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U3.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-57 — owner role only in W0 does not open a W1 ticket
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-5 (role of this workspace)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. member(UG, "owner", ws=W0).
2. T = ticket("HT-1") (`created_by U1.id`).
3. A2 = att("shot.png"), then link(A2, "support_ticket", T.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-58 — ground-team-manager only in W2 does not open a W1 ticket
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-5 (role of this workspace)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. member(UG, "ground-team-manager", ws=W2).
2. T = ticket("HT-1") (`created_by U1.id`).
3. A2 = att("shot.png"), then link(A2, "support_ticket", T.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-59 — an attachment whose only link is filed under W2 answers not found
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-3 (only own-workspace links count)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. A2 = att("stray.png").
2. `AttachmentLink(workspace_id=W2.id, attachment_id=A2.id, entity_type="scratch", entity_id=2, linked_by=U1.id)`, flushed.

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-60 — an attachment with no link at all answers not found
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-3 (no own-workspace link)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. A2 = att("lonely.png") (no link row).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-61 — a link filed under W2 to a private W2 project is ignored; the W1 link decides
- **Rules:** _get_ready_attachment R5 [BUG-2115], R1; PR-3 (other-workspace links ignored)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. P9 = proj("Far Job"), W2 proj, private.
2. A2 = att("mixed.png"), then link(A2, "scratch", 2).
3. `AttachmentLink(workspace_id=W2.id, attachment_id=A2.id, entity_type="project", entity_id=P9.id, linked_by=U1.id)`, flushed.

**When**
- `result = M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. returns: `result.id == A2.id`.

### AMUP-GR-62 — a caller with no W1 membership opens a workspace-visible project's attachment
- **Rules:** _get_ready_attachment R5 [BUG-2115], R1; PR-2 (no membership check of its own)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. U3 = `make_profile(db, name="Rafi Das")` (no membership row anywhere).
2. P = proj("Open Job").
3. A2 = att("open.png"), then link(A2, "project", P.id).

**When**
- `result = M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U3.id)`

**Then**
1. returns: `result.id == A2.id`.

### AMUP-GR-63 — a caller with no W1 membership is still judged on a private project
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-2 (private records judged in full)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. U3 = `make_profile(db, name="Rafi Das")` (no membership row anywhere).
2. P = proj("Tender 7"), private.
3. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U3.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-64 — a platform admin with a plain role does not open a private project's attachment
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-2 (platform admin counts for help tickets only)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. admin(UG) (UG keeps member(UG, "ground-team")).
2. P = proj("Tender 7"), private.
3. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-65 — a platform admin with a plain role does not open a private project's component attachment
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-2 (component → its project's rule)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. admin(UG) (UG keeps member(UG, "ground-team")).
2. P = proj("Tender 7"), private. C = comp(P, "Frame").
3. A2 = att("frame.png"), then link(A2, "project_component", C.id).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-66 — a W1-filed link to a W2 help ticket is hidden, even from a W1 owner-role member
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-1, HR-16
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. T9 = ticket("HT-9") but `workspace_id W2.id`.
2. A2 = att("far.png"), then link(A2, "support_ticket", T9.id) (filed under W1).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-67 — a W1-filed link to a W0 help ticket is hidden, even from a W1 owner-role member
- **Rules:** _get_ready_attachment R5 [BUG-2115]; PR-1, HR-16
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id)

**Given**
1. T0 = ticket("HT-0") but `workspace_id W0.id`.
2. A2 = att("zero.png"), then link(A2, "support_ticket", T0.id) (filed under W1).

**When**
- `M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-GR-68 — the workspace owner with a plain role opens another member's ticket
- **Rules:** _get_ready_attachment R5 [BUG-2103, BUG-2115]; PR-2 (workspace owner opens every ticket of the workspace)
- **Kind:** bug
- **Expect:** xfail BUG-2103
- **Fails today on:** Then 1 (the call raises TypeError: no parameter user_id; after BUG-2115 alone it raises AttachmentNotFoundError until BUG-2103 is fixed)

**Given**
1. set_owner(W1, UG) (UG keeps member(UG, "ground-team")).
2. T = ticket("HT-1") (`created_by U1.id`).
3. A2 = att("shot.png"), then link(A2, "support_ticket", T.id).

**When**
- `result = M._get_ready_attachment(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. returns: `result.id == A2.id`.

## `AttachmentMarkupManager._is_markupable`

(Pure: `a = Attachment(mime_type=…, format=…)` built, never added. `result = AttachmentMarkupManager._is_markupable(a)`.)

### AMUP-IM-01 — mime application/pdf is markable whatever the format
- **Rules:** _is_markupable R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `a = Attachment(mime_type="application/pdf", format="bin")`.

**When**
- `result = AttachmentMarkupManager._is_markupable(a)`

**Then**
1. returns: `result is True`.

### AMUP-IM-02 — format "PDF" or "pdf" is markable with a non-image mime
- **Rules:** _is_markupable R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `a1 = Attachment(mime_type="text/plain", format="PDF")`; `a2 = Attachment(mime_type="text/plain", format="pdf")`.

**When**
- `result = [AttachmentMarkupManager._is_markupable(a) for a in (a1, a2)]`

**Then**
1. returns: `result == [True, True]`.

### AMUP-IM-03 — format "pd", " pdf" and "pdfx" are not PDF
- **Rules:** _is_markupable R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `xs = [Attachment(mime_type="text/plain", format=f) for f in ("pd", " pdf", "pdfx")]`.

**When**
- `result = [AttachmentMarkupManager._is_markupable(a) for a in xs]`

**Then**
1. returns: `result == [False, False, False]`.

### AMUP-IM-04 — mime "application/PDF", "application/pd" and " application/pdf" are not PDF
- **Rules:** _is_markupable R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `xs = [Attachment(mime_type=m, format="bin") for m in ("application/PDF", "application/pd", " application/pdf")]`.

**When**
- `result = [AttachmentMarkupManager._is_markupable(a) for a in xs]`

**Then**
1. returns: `result == [False, False, False]`.

### AMUP-IM-05 — image/png and image/heic are markable
- **Rules:** _is_markupable R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. `xs = [Attachment(mime_type=m, format="bin") for m in ("image/png", "image/heic")]`.

**When**
- `result = [AttachmentMarkupManager._is_markupable(a) for a in xs]`

**Then**
1. returns: `result == [True, True]`.

### AMUP-IM-06 — "Image/png", " image/png", "x-image/png" and "image" are not markable
- **Rules:** _is_markupable R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `xs = [Attachment(mime_type=m, format="bin") for m in ("Image/png", " image/png", "x-image/png", "image")]`.

**When**
- `result = [AttachmentMarkupManager._is_markupable(a) for a in xs]`

**Then**
1. returns: `result == [False, False, False, False]`.

### AMUP-IM-07 — text/csv is not markable
- **Rules:** _is_markupable R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. `a = Attachment(mime_type="text/csv", format="csv")`.

**When**
- `result = AttachmentMarkupManager._is_markupable(a)`

**Then**
1. returns: `result is False`.

### AMUP-IM-08 — mime None and format None is not markable, without error
- **Rules:** _is_markupable R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = Attachment(mime_type=None, format=None)`.

**When**
- `result = AttachmentMarkupManager._is_markupable(a)`

**Then**
1. returns: `result is False`.

### AMUP-IM-09 — mime None with format "pdf" is markable
- **Rules:** _is_markupable R2, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = Attachment(mime_type=None, format="pdf")`.

**When**
- `result = AttachmentMarkupManager._is_markupable(a)`

**Then**
1. returns: `result is True`.

### AMUP-IM-10 — format None with mime image/jpeg is markable
- **Rules:** _is_markupable R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `a = Attachment(mime_type="image/jpeg", format=None)`.

**When**
- `result = AttachmentMarkupManager._is_markupable(a)`

**Then**
1. returns: `result is True`.

## `AttachmentMarkupManager._resolve_user_name`

### AMUP-UN-01 — an existing profile's name, between lower and higher profile ids
- **Rules:** _resolve_user_name R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No extra rows (U1 below and UG above U2).

**When**
- `result = M._resolve_user_name(db, U2.id)`

**Then**
1. returns: `result == "Bilal Khan"`.

### AMUP-UN-02 — a profile with no membership anywhere still gives its name
- **Rules:** _resolve_user_name R1 (D8)
- **Kind:** happy
- **Expect:** pass

**Given**
1. U3 = `make_profile(db, name="Lena Roy")` (no membership row).

**When**
- `result = M._resolve_user_name(db, U3.id)`

**Then**
1. returns: `result == "Lena Roy"`.

### AMUP-UN-03 — an unknown id gives "User #<id>"
- **Rules:** _resolve_user_name R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No extra rows.

**When**
- `result = M._resolve_user_name(db, MISSING)`

**Then**
1. returns: `result == "User #999999999"`.

## `AttachmentMarkupManager._resolve_saved_stamp`

### AMUP-SS-01 — no profile gives None
- **Rules:** _resolve_saved_stamp R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No extra rows.

**When**
- `result = M._resolve_saved_stamp(db, MISSING)`

**Then**
1. returns: `result is None`.

### AMUP-SS-02 — saved_stamp None gives None
- **Rules:** _resolve_saved_stamp R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stamp(U1, None).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-03 — saved_stamp {} gives None
- **Rules:** _resolve_saved_stamp R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stamp(U1, {}).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-04 — a stored list gives None
- **Rules:** _resolve_saved_stamp R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stamp(U1, [VEC]).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-05 — a stored string gives None
- **Rules:** _resolve_saved_stamp R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stamp(U1, "image").

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-06 — a stored number gives None
- **Rules:** _resolve_saved_stamp R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. stamp(U1, 7).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-07 — a vector stamp is returned as stored
- **Rules:** _resolve_saved_stamp R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. stamp(U1, VEC).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result == VEC`.

### AMUP-SS-08 — the author's own stamp is read, not a neighbour's (lower and higher ids)
- **Rules:** _resolve_saved_stamp R1, R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. stamp(U1, {"kind": "vector", "strokes": [], "viewBox": {"width": 1, "height": 1}}).
2. stamp(U2, VEC).
3. stamp(UG, {"kind": "vector", "strokes": [], "viewBox": {"width": 9, "height": 9}}).

**When**
- `result = M._resolve_saved_stamp(db, U2.id)`

**Then**
1. returns: `result == VEC`.

### AMUP-SS-09 — a stamp with no kind is returned as stored
- **Rules:** _resolve_saved_stamp R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. stamp(U1, {"shape": "x"}).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result == {"shape": "x"}`.

### AMUP-SS-33 — a stamp with an unknown kind is returned as stored
- **Rules:** _resolve_saved_stamp R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. stamp(U1, {"kind": "text", "text": "OK"}).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result == {"kind": "text", "text": "OK"}`.

### AMUP-SS-10 — the author's own minted image stamp keeps kind, public_id, width and height
- **Rules:** _resolve_saved_stamp R4a (accepted side), R4b (fields kept)
- **Kind:** happy
- **Expect:** pass

**Given**
1. stamp(U1, IMG(OWN(U1))).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result["kind"] == "image"`, `result["public_id"] == OWN(U1)`, `result["width"] == 10`, `result["height"] == 10`.

### AMUP-SS-11 — in production the bare own form keeps its fields
- **Rules:** _resolve_saved_stamp R4a (production)
- **Kind:** happy
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "production".
2. stamp(U1, IMG(PROD(U1))).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result["kind"] == "image"`, `result["public_id"] == PROD(U1)`, `result["width"] == 10`, `result["height"] == 10`.

### AMUP-SS-12 — the server builds the url of an own stamp; the stored url never appears
- **Rules:** _resolve_saved_stamp R4b [BUG-2117]
- **Kind:** bug
- **Expect:** xfail BUG-2117
- **Fails today on:** Then 2 (the stored url is returned)

**Given**
1. stamp(U1, IMG(OWN(U1))).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result["public_id"] == OWN(U1)`.
2. returns: `result["url"].startswith(URLP)`.
3. returns: `OWN(U1) in result["url"]`.
4. returns: `"tracker.example" not in result["url"]`.

### AMUP-SS-13 — the url follows the configured cloud name
- **Rules:** _resolve_saved_stamp R4b [BUG-2117]
- **Kind:** bug
- **Expect:** xfail BUG-2117
- **Fails today on:** Then 1 (the stored url is returned)

**Given**
1. settings: CLOUDINARY_CLOUD_NAME "acme-cloud".
2. stamp(U1, IMG(OWN(U1))).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result["url"].startswith("https://res.cloudinary.com/acme-cloud/image/authenticated/")`.

### AMUP-SS-14 — in production the url is built from the bare own id
- **Rules:** _resolve_saved_stamp R4b [BUG-2117]
- **Kind:** bug
- **Expect:** xfail BUG-2117
- **Fails today on:** Then 1 (the stored url is returned)

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "production".
2. stamp(U1, IMG(PROD(U1))).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result["url"].startswith(URLP)`.
2. returns: `PROD(U1) in result["url"]`.

### AMUP-SS-15 — a higher-id user's stamp id on a lower-id author is dropped
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. stamp(U1, IMG(OWN(U2))).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-16 — a lower-id user's stamp id on a higher-id author is dropped
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. stamp(UG, IMG(OWN(U1))).

**When**
- `result = M._resolve_saved_stamp(db, UG.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-17 — an attachment's public id is dropped
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. stamp(U1, IMG(f"development/ws-{W1.id}/" + TOKEN)).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-18 — the bare prefix is dropped
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. stamp(U1, IMG(f"development/profiles/{U1.id}/stamp-")).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-19 — a 31-character token is dropped
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. stamp(U1, IMG(f"development/profiles/{U1.id}/stamp-" + TOKEN31)).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-20 — a 33-character token is dropped
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. stamp(U1, IMG(f"development/profiles/{U1.id}/stamp-" + TOKEN33)).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-21 — an upper-case token is dropped
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. stamp(U1, IMG(f"development/profiles/{U1.id}/stamp-" + TOKENU)).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-22 — a token with a non-hex letter is dropped
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. stamp(U1, IMG(f"development/profiles/{U1.id}/stamp-" + TOKENG)).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-23 — anything after a valid token (".png") is dropped
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. stamp(U1, IMG(OWN(U1) + ".png")).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-24 — a trailing newline after a valid token is dropped
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. stamp(U1, IMG(OWN(U1) + "\n")).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-25 — the production form is dropped in development
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. stamp(U1, IMG(PROD(U1))).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-26 — the development form is dropped in production
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "production".
2. stamp(U1, IMG(OWN(U1))).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-27 — with the upload environment empty, an own "staging" stamp keeps its fields
- **Rules:** _resolve_saved_stamp R4a (accepted side, ENVIRONMENT fallback)
- **Kind:** happy
- **Expect:** pass

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "". settings: ENVIRONMENT "staging".
2. stamp(U1, IMG(f"staging/profiles/{U1.id}/stamp-" + TOKEN)).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result["public_id"] == f"staging/profiles/{U1.id}/stamp-" + TOKEN`, `result["width"] == 10`.

### AMUP-SS-32 — with the upload environment empty and ENVIRONMENT "staging", the development form is dropped
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. settings: CLOUDINARY_UPLOAD_ENV "". settings: ENVIRONMENT "staging".
2. stamp(U1, IMG(OWN(U1))).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-28 — a capitalised environment prefix is dropped
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. stamp(U1, IMG(f"Development/profiles/{U1.id}/stamp-" + TOKEN)).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-29 — a leading space makes the id foreign
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. stamp(U1, IMG(" " + OWN(U1))).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-30 — an image stamp without public_id is dropped
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. stamp(U1, {"kind": "image", "url": "https://tracker.example/p.png", "width": 10, "height": 10}).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

### AMUP-SS-31 — the own prefix in the middle of the id is dropped
- **Rules:** _resolve_saved_stamp R4a [BUG-2116]
- **Kind:** bug
- **Expect:** xfail BUG-2116
- **Fails today on:** Then 1 (the stored stamp is returned)

**Given**
1. stamp(U1, IMG("x/" + OWN(U1))).

**When**
- `result = M._resolve_saved_stamp(db, U1.id)`

**Then**
1. returns: `result is None`.

## `AttachmentMarkupManager._summarize_payload`

(Pure. `result = AttachmentMarkupManager._summarize_payload(MP(d))` for the card's `d`.)

### AMUP-SP-01 — one page with one stroke
- **Rules:** _summarize_payload R1, R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing (pure call).

**When**
- `result = AttachmentMarkupManager._summarize_payload(MP({"3": {"strokes": [STROKE]}}))`

**Then**
1. returns: `result == ({"pages": [3]}, "Updated marks on page 3")`.

### AMUP-SP-02 — a stroke with no points counts; an all-empty page does not
- **Rules:** _summarize_payload R1 (D9)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing (pure call).

**When**
- `result = AttachmentMarkupManager._summarize_payload(MP({"1": {"strokes": [BARE]}, "2": {"strokes": [], "texts": [], "scribbles": [], "stamps": []}}))`

**Then**
1. returns: `result == ({"pages": [1]}, "Updated marks on page 1")`.

### AMUP-SP-03 — a page with only a text, and one with only a stamp, both count
- **Rules:** _summarize_payload R1, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing (pure call).

**When**
- `result = AttachmentMarkupManager._summarize_payload(MP({"4": {"texts": [TEXT]}, "5": {"stamps": [STAMPM]}}))`

**Then**
1. returns: `result == ({"pages": [4, 5]}, "Updated marks on pages 4, 5")`.

### AMUP-SP-04 — keys accepted by int() become integers
- **Rules:** _summarize_payload R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing (pure call).

**When**
- `result = AttachmentMarkupManager._summarize_payload(MP({k: {"strokes": [STROKE]} for k in ("03", " 2", "-1", "1_0")}))`

**Then**
1. returns: `result[0] == {"pages": [-1, 2, 3, 10]}`.

### AMUP-SP-05 — "cover" and "1.5" stay strings
- **Rules:** _summarize_payload R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing (pure call).

**When**
- `result = AttachmentMarkupManager._summarize_payload(MP({k: {"strokes": [STROKE]} for k in ("cover", "1.5")}))`

**Then**
1. returns: `result == ({"pages": ["1.5", "cover"]}, "Updated marks on pages 1.5, cover")`.

### AMUP-SP-06 — integers first numerically, then strings
- **Rules:** _summarize_payload R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing (pure call).

**When**
- `result = AttachmentMarkupManager._summarize_payload(MP({k: {"strokes": [STROKE]} for k in ("b", "10", "2", "a")}))`

**Then**
1. returns: `result[0] == {"pages": [2, 10, "a", "b"]}`.

### AMUP-SP-07 — "1" and "01" both appear
- **Rules:** _summarize_payload R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing (pure call).

**When**
- `result = AttachmentMarkupManager._summarize_payload(MP({k: {"strokes": [STROKE]} for k in ("01", "1")}))`

**Then**
1. returns: `result == ({"pages": [1, 1]}, "Updated marks on pages 1, 1")`.

### AMUP-SP-08 — several pages are named in sort order
- **Rules:** _summarize_payload R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing (pure call).

**When**
- `result = AttachmentMarkupManager._summarize_payload(MP({k: {"strokes": [STROKE]} for k in ("cover", "3", "1")}))`

**Then**
1. returns: `result == ({"pages": [1, 3, "cover"]}, "Updated marks on pages 1, 3, cover")`.

### AMUP-SP-09 — no pages gives "Updated marks"
- **Rules:** _summarize_payload R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing (pure call).

**When**
- `result = AttachmentMarkupManager._summarize_payload(MP(EMPTY))`

**Then**
1. returns: `result == ({"pages": []}, "Updated marks")`.

### AMUP-SP-10 — only all-empty pages gives "Updated marks"
- **Rules:** _summarize_payload R5, R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing (pure call).

**When**
- `result = AttachmentMarkupManager._summarize_payload(MP(EMPTYPAGE))`

**Then**
1. returns: `result == ({"pages": []}, "Updated marks")`.

### AMUP-SP-11 — a page with only a scribble counts, also one with no points
- **Rules:** _summarize_payload R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing (pure call).

**When**
- `result = AttachmentMarkupManager._summarize_payload(MP({"1": {"scribbles": [SCRIB]}, "2": {"scribbles": [SCRIB0]}}))`

**Then**
1. returns: `result == ({"pages": [1, 2]}, "Updated marks on pages 1, 2")`.

## `AttachmentMarkupManager._log_markup_event`

### AMUP-LE-01 — one row with exactly the given values
- **Rules:** _log_markup_event R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No extra rows.

**When**
- `M._log_markup_event(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U2.id, event_type="markup_saved", description="Saved marks on page 1", session_id="tab-1", metadata_json={"pages": [1]})`

**Then**
1. count: events_of(A1) has exactly 1 row.
2. re-read that row: `workspace_id == W1.id`, `attachment_id == A1.id`, `user_id == U2.id`, `event_type == "markup_saved"`, `description == "Saved marks on page 1"`, `session_id == "tab-1"`, `metadata_json == {"pages": [1]}`, `created_at is not None`.

### AMUP-LE-02 — the event is flushed, not committed
- **Rules:** _log_markup_event R1 (no commit)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No extra rows.

**When**
- Rolled back: `M._log_markup_event(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, event_type="markup_cleared", description="Cleared marks")`

**Then**
1. mock called: `cm.call_count == 0`.
2. count: events_of(A1) has exactly 0 rows.

## `AttachmentMarkupManager._to_layer_response`

### AMUP-TL-01 — the caller's own layer maps every field
- **Rules:** _to_layer_response R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. stamp(U1, VEC).
2. L = layer(A1, U1, P1).

**When**
- `result = M._to_layer_response(db, row=L, current_user_id=U1.id)`

**Then**
1. returns: `result.user_id == U1.id`, `result.user_name == "Ana Rahman"`, `result.is_mine is True`.
2. returns: `result.updated_at == L.updated_at` (after `db.refresh(L)`).
3. returns: `result.payload == MP(P1)`.
4. returns: `result.saved_stamp == VEC`.

### AMUP-TL-02 — another user's layer is not mine
- **Rules:** _to_layer_response R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. L = layer(A1, U2, P2).

**When**
- `result = M._to_layer_response(db, row=L, current_user_id=U1.id)`

**Then**
1. returns: `result.user_id == U2.id`, `result.user_name == "Bilal Khan"`, `result.is_mine is False`, `result.saved_stamp is None`.

### AMUP-TL-03 — a stored JSON null payload raises ValidationError
- **Rules:** _to_layer_response R2
- **Kind:** error
- **Expect:** pass

**Given**
1. L = `AttachmentMarkup(workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, payload=None)`, flushed.

**When**
- `M._to_layer_response(db, row=L, current_user_id=U1.id)`

**Then**
1. raises: `ValidationError`.

## `AttachmentMarkupManager._to_event_response`

### AMUP-TE-01 — an event maps every stored field; mine
- **Rules:** _to_event_response R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = `AttachmentMarkupEvent(workspace_id=W1.id, attachment_id=A1.id, user_id=U2.id, event_type="markup_updated", description="Updated marks on page 2", session_id="tab-9", metadata_json={"pages": [2]}, created_at=T1)`, flushed.

**When**
- `result = M._to_event_response(db, row=E, current_user_id=U2.id)`

**Then**
1. returns: `result.id == E.id`, `result.user_id == U2.id`, `result.user_name == "Bilal Khan"`, `result.is_mine is True`.
2. returns: `result.session_id == "tab-9"`, `result.event_type == "markup_updated"`, `result.description == "Updated marks on page 2"`.
3. returns: `result.metadata_json == {"pages": [2]}`, `result.created_at == T1`.

### AMUP-TE-02 — another user's event is not mine
- **Rules:** _to_event_response R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = mev(A1, UG, T1).

**When**
- `result = M._to_event_response(db, row=E, current_user_id=U1.id)`

**Then**
1. returns: `result.user_name == "Mia Khan"`, `result.is_mine is False`.

## `AttachmentMarkupManager.list_layers`

### AMUP-LL-01 — every author's layer, only the caller's is mine
- **Rules:** list_layers R2; D8
- **Kind:** happy
- **Expect:** pass

**Given**
1. U3 = `make_profile(db, name="Lena Roy")` (no membership: has left).
2. layer(A1, U2, P1). layer(A1, U3, P2). layer(A1, U1, P12).

**When**
- `result = M.list_layers(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=U1.id)`

**Then**
1. returns: `sorted(uids(result)) == sorted([U1.id, U2.id, U3.id])`.
2. returns: `{r.user_id: r.is_mine for r in result} == {U1.id: True, U2.id: False, U3.id: False}`.
3. returns: `{r.user_id: r.user_name for r in result}[U3.id] == "Lena Roy"`.

### AMUP-LL-02 — layers of other attachments (lower and higher id) and other workspaces are not listed
- **Rules:** list_layers R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. AL = att("low.png"); A2 = att("mid.png"), link(A2, "scratch", 2); AH = att("high.png").
2. layer(AL, U1, P1). layer(A2, U2, P1). layer(AH, UG, P1).
3. `AttachmentMarkup(workspace_id=W0.id, attachment_id=A2.id, user_id=U1.id, payload=D(P1))`, flushed. `AttachmentMarkup(workspace_id=W2.id, attachment_id=A2.id, user_id=UG.id, payload=D(P1))`, flushed.

**When**
- `result = M.list_layers(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=U1.id)`

**Then**
1. returns: `uids(result) == [U2.id]`.

### AMUP-LL-03 — no layers gives []
- **Rules:** list_layers R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No layers.

**When**
- `result = M.list_layers(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=U1.id)`

**Then**
1. returns: `result == []`.

### AMUP-LL-04 — layers come oldest updated first
- **Rules:** list_layers R3 (DAO R4, distinct times)
- **Kind:** happy
- **Expect:** pass

**Given**
1. LA = layer(A1, U2, P1); LB = layer(A1, UG, P1); LC = layer(A1, U1, P1).
2. older(LA, 1). older(LB, 2).

**When**
- `result = M.list_layers(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=U1.id)`

**Then**
1. returns: `uids(result) == [UG.id, U2.id, U1.id]`.

### AMUP-LL-05 — layers with one time come in id order, also after an update
- **Rules:** list_layers R3 [BUG-1435]
- **Kind:** bug
- **Expect:** xfail BUG-1435 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (the touched layer comes last)

**Given**
1. seqscan.
2. LA = layer(A1, UG, P1); LB = layer(A1, U1, P1); LC = layer(A1, U2, P1).
3. touchL(LA).

**When**
- `result = M.list_layers(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=U1.id)`

**Then**
1. returns: `uids(result) == [UG.id, U1.id, U2.id]`.

### AMUP-LL-06 — an unknown attachment raises not found and no layer is read
- **Rules:** list_layers R1
- **Kind:** error
- **Expect:** pass

**Given**
1. layer(A1, U1, P1). recorder.

**When**
- `M.list_layers(db, workspace_id=W1.id, attachment_id=MISSING, current_user_id=U1.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == "Attachment 999999999 not found."`.
2. statement: `markup_reads == 0`.

### AMUP-LL-07 — a pending attachment raises unavailable and no layer is read
- **Rules:** list_layers R1
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = att("wait.png") but `upload_status "pending"`, then link(A2, "scratch", 2). layer(A2, U1, P1). recorder.

**When**
- `M.list_layers(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=U1.id)`

**Then**
1. raises: `AttachmentValidationError`, `str(exc.value) == UNAV`.
2. statement: `markup_reads == 0`.

### AMUP-LL-08 — layers on a private project's attachment are hidden from a plain member
- **Rules:** list_layers R1a [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. P = proj("Tender 7"), private.
2. A2 = att("contract.png"), then link(A2, "project", P.id). layer(A2, U1, P1). recorder.

**When**
- `M.list_layers(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.
2. statement: `markup_reads == 0`.

### AMUP-LL-09 — layers on another member's ticket attachment are hidden
- **Rules:** list_layers R1a [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. T = ticket("HT-1").
2. A2 = att("shot.png"), then link(A2, "support_ticket", T.id). layer(A2, U1, P1).

**When**
- `M.list_layers(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-LL-10 — layers on a W2 project's attachment are hidden
- **Rules:** list_layers R1a [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. P9 = proj("Far Job"), W2 proj.
2. A2 = att("far.png"), then link(A2, "project", P9.id). layer(A2, U1, P1).

**When**
- `M.list_layers(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-LL-11 — a project member lists the private project's layers
- **Rules:** list_layers R1a (granted side of BUG-2115), R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P = proj("Tender 7"), private. pmem(P, UG).
2. A2 = att("contract.png"), then link(A2, "project", P.id). layer(A2, U1, P1).

**When**
- `result = M.list_layers(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=UG.id)`

**Then**
1. returns: `uids(result) == [U1.id]`.

### AMUP-LL-12 — authors' profiles are read together
- **Rules:** list_layers R4 [BUG-2119]
- **Kind:** bug
- **Expect:** xfail BUG-2119
- **Fails today on:** Then 2 (ten profile reads)

**Given**
1. U3 = `make_profile(db, name="Lena Roy")`, U4 = `make_profile(db, name="Omar Ali")`, U5 = `make_profile(db, name="Nila Sen")`.
2. layer(A1, U1, P1). layer(A1, U2, P1). layer(A1, U3, P1). layer(A1, U4, P1). layer(A1, U5, P1).
3. recorder.

**When**
- `result = M.list_layers(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=U1.id)`

**Then**
1. returns: `sorted(r.user_name for r in result) == ["Ana Rahman", "Bilal Khan", "Lena Roy", "Nila Sen", "Omar Ali"]`.
2. statement: `profile_reads <= 2`.

### AMUP-LL-13 — layers of an attachment whose only link is filed under W2 are hidden
- **Rules:** list_layers R1a [BUG-2115]; PR-3 (only own-workspace links count)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. A2 = att("stray.png").
2. `AttachmentLink(workspace_id=W2.id, attachment_id=A2.id, entity_type="scratch", entity_id=2, linked_by=U1.id)`, flushed.
3. layer(A2, U1, P1). recorder.

**When**
- `M.list_layers(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.
2. statement: `markup_reads == 0`.

### AMUP-LL-14 — a platform admin with a plain role sees no layers of a private project's attachment
- **Rules:** list_layers R1a [BUG-2115]; PR-2
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. admin(UG) (UG keeps member(UG, "ground-team")).
2. P = proj("Tender 7"), private.
3. A2 = att("contract.png"), then link(A2, "project", P.id). layer(A2, U1, P1).
4. recorder.

**When**
- `M.list_layers(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.
2. count: `markup_reads == 0`.

## `AttachmentMarkupManager.list_events`

### AMUP-LV-01 — every author's entry, mapped, only the caller's mine
- **Rules:** list_events R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. EA = mev(A1, U2, T1). EB = mev(A1, U1, T0).

**When**
- `result = M.list_events(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=U1.id)`

**Then**
1. returns: `sorted(eids(result)) == sorted([EA.id, EB.id])`.
2. returns: `{r.id: r.is_mine for r in result} == {EA.id: False, EB.id: True}`.
3. returns: `{r.id: r.user_name for r in result} == {EA.id: "Bilal Khan", EB.id: "Ana Rahman"}`.

### AMUP-LV-02 — entries of other attachments (lower and higher id) and other workspaces are not listed
- **Rules:** list_events R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. AL = att("low.png"); A2 = att("mid.png"), link(A2, "scratch", 2); AH = att("high.png").
2. mev(AL, U1, T1). E = mev(A2, U2, T1). mev(AH, UG, T1).
3. `AttachmentMarkupEvent(workspace_id=W0.id, attachment_id=A2.id, user_id=U1.id, event_type="markup_saved", description="seed", created_at=T1)`, flushed; the same with `workspace_id W2.id`, `user_id UG.id`.

**When**
- `result = M.list_events(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=U1.id)`

**Then**
1. returns: `eids(result) == [E.id]`.

### AMUP-LV-03 — entries come newest first
- **Rules:** list_events R3 (distinct times)
- **Kind:** happy
- **Expect:** pass

**Given**
1. EA = mev(A1, UG, T1). EB = mev(A1, U1, T0). EC = mev(A1, U2, T2).

**When**
- `result = M.list_events(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=U1.id)`

**Then**
1. returns: `eids(result) == [EC.id, EA.id, EB.id]`.

### AMUP-LV-04 — entries of one time come highest id first, also after an update
- **Rules:** list_events R3 [BUG-1436]
- **Kind:** bug
- **Expect:** xfail BUG-1436 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (the touched entry comes last)

**Given**
1. seqscan.
2. EA = mev(A1, UG, T1). EB = mev(A1, U1, T1). EC = mev(A1, U2, T1).
3. touchE(EC).

**When**
- `result = M.list_events(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=U1.id)`

**Then**
1. returns: `eids(result) == [EC.id, EB.id, EA.id]`.

### AMUP-LV-05 — no entries gives []
- **Rules:** list_events R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No events.

**When**
- `result = M.list_events(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=U1.id)`

**Then**
1. returns: `result == []`.

### AMUP-LV-06 — all 201 entries are returned
- **Rules:** list_events R3 [BUG-1437]
- **Kind:** bug
- **Expect:** xfail BUG-1437
- **Fails today on:** Then 1 (200 returned)

**Given**
1. `db.add_all([AttachmentMarkupEvent(workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, event_type="markup_saved", description="seed", created_at=T1) for _ in range(201)])`, `db.flush()`.

**When**
- `result = M.list_events(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=U1.id)`

**Then**
1. returns: `len(result) == 201`.

### AMUP-LV-07 — a soft-deleted attachment raises not found
- **Rules:** list_events R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AD = deleted att("gone.png"). mev(AD, U1, T1).

**When**
- `M.list_events(db, workspace_id=W1.id, attachment_id=AD.id, current_user_id=U1.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(AD)`.

### AMUP-LV-08 — a ready CSV raises unavailable
- **Rules:** list_events R1
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = att("data.csv") but `mime_type "text/csv"`, `format "csv"`, then link(A2, "scratch", 2).

**When**
- `M.list_events(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=U1.id)`

**Then**
1. raises: `AttachmentValidationError`, `str(exc.value) == UNAV`.

### AMUP-LV-09 — history of a private project's attachment is hidden from a plain member
- **Rules:** list_events R1a [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. P = proj("Tender 7"), private.
2. A2 = att("contract.png"), then link(A2, "project", P.id). mev(A2, U1, T1).

**When**
- `M.list_events(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-LV-10 — history of a deleted project's attachment is hidden
- **Rules:** list_events R1a [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. P = proj("Old Job"), deleted.
2. A2 = att("old.png"), then link(A2, "project", P.id). mev(A2, U1, T1).

**When**
- `M.list_events(db, workspace_id=W1.id, attachment_id=A2.id, current_user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.

### AMUP-LV-11 — authors' profiles are read together
- **Rules:** list_events R4 [BUG-2119]
- **Kind:** bug
- **Expect:** xfail BUG-2119
- **Fails today on:** Then 2 (one profile read per entry)

**Given**
1. mev(A1, U1, T1), mev(A1, U2, T1), mev(A1, U1, T0), mev(A1, U2, T0), mev(A1, U1, T2), in that order.
2. recorder.

**When**
- `result = M.list_events(db, workspace_id=W1.id, attachment_id=A1.id, current_user_id=U1.id)`

**Then**
1. returns: `sorted(r.user_name for r in result) == ["Ana Rahman", "Ana Rahman", "Ana Rahman", "Bilal Khan", "Bilal Khan"]`.
2. statement: `profile_reads <= 2`.

## `AttachmentMarkupManager.put_own_layer`

### AMUP-PL-01 — a first save creates the layer and a markup_saved event
- **Rules:** put_own_layer R3, R6, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. No layers, no events.

**When**
- `result = M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U2.id, payload=MP(P1), session_id="tab-1")`

**Then**
1. returns: `result.user_id == U2.id`, `result.user_name == "Bilal Khan"`, `result.is_mine is True`, `result.payload == MP(P1)`.
2. returns: `result.updated_at == NOW_DB`.
3. count: layers_of(A1) has exactly 1 row.
4. re-read that layer: `workspace_id == W1.id`, `user_id == U2.id`, `payload == D(P1)`.
5. count: events_of(A1) has exactly 1 row.
6. re-read that event: `workspace_id == W1.id`, `attachment_id == A1.id`, `user_id == U2.id`, `event_type == "markup_saved"`, `description == "Saved marks on page 1"`, `metadata_json == {"pages": [1]}`, `session_id == "tab-1"`.

### AMUP-PL-02 — a first save of two pages says "Saved marks on pages 1, 2"
- **Rules:** put_own_layer R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. No layers, no events.

**When**
- `result = M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, payload=MP(P12))`

**Then**
1. returns: `result.is_mine is True`.
2. re-read the one row of events_of(A1): `event_type == "markup_saved"`, `description == "Saved marks on pages 1, 2"`, `metadata_json == {"pages": [1, 2]}`, `session_id is None`.

### AMUP-PL-03 — the stored payload is the dump: defaults filled in, unknown keys dropped
- **Rules:** put_own_layer R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `pl = MarkupPayload.model_validate({"pages": {"1": {"stamps": [STAMPM], "junk": 1}}, "extra": 2})`.

**When**
- `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, payload=pl)`

**Then**
1. re-read the one row of layers_of(A1): `payload == pl.model_dump()`.
2. re-read the one row of layers_of(A1): `payload["pages"]["1"]["strokes"] == []`, `payload["pages"]["1"]["stamps"][0]["rotation"] == 0`, `"junk" not in payload["pages"]["1"]`, `"extra" not in payload`.

### AMUP-PL-04 — saving over an existing layer replaces it and logs markup_updated
- **Rules:** put_own_layer R4, R6, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. L = layer(A1, U1, P1). older(L, 1).

**When**
- `result = M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, payload=MP(P2), session_id="tab-2")`

**Then**
1. returns: `result.payload == MP(P2)`, `result.updated_at == NOW_DB`.
2. count: layers_of(A1) has exactly 1 row.
3. re-read L: `payload == D(P2)`.
4. re-read the one row of events_of(A1): `event_type == "markup_updated"`, `description == "Updated marks on page 2"`, `metadata_json == {"pages": [2]}`, `session_id == "tab-2"`, `user_id == U1.id`.

### AMUP-PL-05 — other users' layers (lower and higher user id) are untouched
- **Rules:** put_own_layer R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. LA = layer(A1, U1, P1). LG = layer(A1, UG, P1). AH = att("high.png"); LX = layer(AH, U2, P1).

**When**
- `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U2.id, payload=MP(P2))`

**Then**
1. re-read LA: `payload == D(P1)`.
2. re-read LG: `payload == D(P1)`.
3. re-read LX: `payload == D(P1)`.
4. count: layers_of(A1) has exactly 3 rows.

### AMUP-PL-06 — an empty payload deletes the caller's layer and logs markup_cleared
- **Rules:** put_own_layer R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. LA = layer(A1, U1, P1). L = layer(A1, U2, P1). LG = layer(A1, UG, P1).

**When**
- `result = M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U2.id, payload=MP(EMPTY), session_id="tab-3")`

**Then**
1. returns: `result is None`.
2. count: layers_of(A1) has exactly 2 rows.
3. returns: `uids(layers_of(A1)) == [U1.id, UG.id]`.
4. re-read the one row of events_of(A1): `event_type == "markup_cleared"`, `description == "Cleared marks"`, `metadata_json == {"pages": []}`, `session_id == "tab-3"`, `user_id == U2.id`.

### AMUP-PL-07 — only all-empty pages also clear the layer
- **Rules:** put_own_layer R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. layer(A1, U1, P1).

**When**
- `result = M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, payload=MP(EMPTYPAGE))`

**Then**
1. returns: `result is None`.
2. count: layers_of(A1) has exactly 0 rows.
3. re-read the one row of events_of(A1): `event_type == "markup_cleared"`.

### AMUP-PL-08 — an empty payload with no layer writes nothing
- **Rules:** put_own_layer R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. layer(A1, U2, P1) (another user's).

**When**
- `result = M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, payload=MP(EMPTY))`

**Then**
1. returns: `result is None`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-PL-09 — a stroke with no points is a non-empty save
- **Rules:** put_own_layer R3 (D9)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No layers.

**When**
- `result = M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, payload=MP({"1": {"strokes": [BARE]}}))`

**Then**
1. returns: `result.is_mine is True`.
2. re-read the one row of events_of(A1): `description == "Saved marks on page 1"`.

### AMUP-PL-10 — an unknown attachment writes nothing
- **Rules:** put_own_layer R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No extra rows.

**When**
- `M.put_own_layer(db, workspace_id=W1.id, attachment_id=MISSING, user_id=U1.id, payload=MP(P1))`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == "Attachment 999999999 not found."`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-PL-11 — a W0 attachment writes nothing
- **Rules:** put_own_layer R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = att("zero.png") but `workspace_id W0.id`.

**When**
- `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A0.id, user_id=U1.id, payload=MP(P1))`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A0)`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-PL-12 — a W2 attachment writes nothing
- **Rules:** put_own_layer R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A9 = att("far.png") but `workspace_id W2.id`.

**When**
- `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A9.id, user_id=U1.id, payload=MP(P1))`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A9)`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-PL-13 — a pending attachment writes nothing
- **Rules:** put_own_layer R1
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = att("wait.png") but `upload_status "pending"`, then link(A2, "scratch", 2).

**When**
- `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U1.id, payload=MP(P1))`

**Then**
1. raises: `AttachmentValidationError`, `str(exc.value) == UNAV`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-PL-14 — a not-markable attachment does not clear an existing layer
- **Rules:** put_own_layer R1
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = att("data.csv") but `mime_type "text/csv"`, `format "csv"`, then link(A2, "scratch", 2). layer(A2, U1, P1).

**When**
- `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U1.id, payload=MP(EMPTY))`

**Then**
1. raises: `AttachmentValidationError`, `str(exc.value) == UNAV`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-PL-15 — a private project's attachment refuses a plain member, nothing written
- **Rules:** put_own_layer R1a [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. P = proj("Tender 7"), private.
2. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id, payload=MP(P1))`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-PL-16 — another member's ticket attachment refuses a plain member, nothing written
- **Rules:** put_own_layer R1a [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. T = ticket("HT-1").
2. A2 = att("shot.png"), then link(A2, "support_ticket", T.id).

**When**
- `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id, payload=MP(P1))`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-PL-17 — a deleted project's attachment refuses its creator, layer kept
- **Rules:** put_own_layer R1a [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. P = proj("Old Job"), deleted.
2. A2 = att("old.png"), then link(A2, "project", P.id). layer(A2, U1, P1).

**When**
- `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U1.id, payload=MP(EMPTY))`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-PL-18 — a W2 project's attachment refuses, nothing written
- **Rules:** put_own_layer R1a [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. P9 = proj("Far Job"), W2 proj.
2. A2 = att("far.png"), then link(A2, "project", P9.id).

**When**
- `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id, payload=MP(P1))`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-PL-19 — a project id that exists only as a W1 ticket refuses, nothing written
- **Rules:** put_own_layer R1a [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. T = ticket("HT-1") but `id XID(3)` (no project has id XID(3)).
2. A2 = att("x.png"), then link(A2, "project", XID(3)).

**When**
- `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id, payload=MP(P1))`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-PL-20 — a project member saves on the private project's attachment
- **Rules:** put_own_layer R1a (granted side of BUG-2115), R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P = proj("Tender 7"), private. pmem(P, UG).
2. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `result = M.put_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id, payload=MP(P1))`

**Then**
1. returns: `result.user_id == UG.id`.
2. count: layers_of(A2) has exactly 1 row.

### AMUP-PL-21 — a hidden attachment that is also pending answers not found
- **Rules:** put_own_layer R1a [BUG-2115] (before R3 / R4 of the helper)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (the error raised is AttachmentValidationError "Markup is only available for images and PDFs." for the pending state, not AttachmentNotFoundError: the record is not looked at)

**Given**
1. P = proj("Tender 7"), private.
2. A2 = att("wait.png") but `upload_status "pending"`, then link(A2, "project", P.id).

**When**
- `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id, payload=MP(P1))`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.

### AMUP-PL-22 — saving the stored payload again returns the layer unchanged
- **Rules:** put_own_layer R6, R7a (part that holds today)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. L = layer(A1, U1, P1). older(L, 1). `t0 = L.updated_at` after `db.refresh(L)`.

**When**
- `result = M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, payload=MP(P1))`

**Then**
1. returns: `result.payload == MP(P1)`, `result.updated_at == t0`.
2. count: layers_of(A1) has exactly 1 row.

### AMUP-PL-23 — saving the stored payload again writes no event
- **Rules:** put_own_layer R7a [BUG-2118]
- **Kind:** bug
- **Expect:** xfail BUG-2118
- **Fails today on:** Then 2 (a markup_updated event is written)

**Given**
1. L = layer(A1, U1, P1).

**When**
- `result = M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, payload=MP(P1))`

**Then**
1. returns: `result.user_id == U1.id`.
2. count: events_of(A1) has exactly 0 rows.

### AMUP-PL-24 — a save then the same save again leaves one event
- **Rules:** put_own_layer R7a [BUG-2118]
- **Kind:** bug
- **Expect:** xfail BUG-2118
- **Fails today on:** Then 2 (two events)

**Given**
1. `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, payload=MP(P1))` (first save, run as a Given step).

**When**
- `result = M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, payload=MP(P1))`

**Then**
1. returns: `result.payload == MP(P1)`.
2. count: events_of(A1) has exactly 1 row.

### AMUP-PL-25 — a concurrent first save becomes an update, no error
- **Rules:** put_own_layer R5a [BUG-2120]
- **Kind:** bug
- **Expect:** xfail BUG-2120
- **Author:** claude
- **Fails today on:** Then 1 (the call raises IntegrityError 23505)

**Given**
1. L = layer(A1, U1, P1).
2. Race simulation: `patch("app.dao.attachment_markup.AttachmentMarkupDAO.get_for_user", return_value=None)` around the When; the When runs inside `sp = db.begin_nested()` and `sp.commit()` if it returns (`sp.rollback()` if it raises), so a failed flush does not poison the test transaction.

**When**
- `result = M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, payload=MP(P2))`

**Then**
1. returns: `result.payload == MP(P2)`.
2. count: layers_of(A1) has exactly 1 row.
3. re-read L: `payload == D(P2)`.
4. re-read the one row of events_of(A1): `event_type == "markup_updated"`.

### AMUP-PL-26 — put_own_layer flushes, never commits
- **Rules:** put_own_layer Side effects (no commit)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No layers.

**When**
- Rolled back: `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, payload=MP(P1))`

**Then**
1. mock called: `cm.call_count == 0`.
2. count: layers_of(A1) has exactly 0 rows.
3. count: events_of(A1) has exactly 0 rows.

### AMUP-PL-27 — the returned layer carries the author's current stamp
- **Rules:** put_own_layer R6; _resolve_saved_stamp R1 (D6)
- **Kind:** happy
- **Expect:** pass

**Given**
1. stamp(U1, VEC).

**When**
- `result = M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, payload=MP(P1))`

**Then**
1. returns: `result.saved_stamp == VEC`, `result.user_name == "Ana Rahman"`.

### AMUP-PL-28 — an attachment with no link writes nothing
- **Rules:** put_own_layer R1a [BUG-2115]; PR-3 (no own-workspace link)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the layer is saved)

**Given**
1. A2 = att("lonely.png") (no link row).

**When**
- `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id, payload=MP(P1))`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-PL-29 — a suspended owner-role member is refused a private project's attachment, nothing written
- **Rules:** put_own_layer R1a [BUG-2115]; PR-5 (active membership only)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the layer is saved)

**Given**
1. U3 = `make_profile(db, name="Rafi Das")`; member(U3, "owner", status="suspended").
2. P = proj("Tender 7"), private.
3. A2 = att("contract.png"), then link(A2, "project", P.id).

**When**
- `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U3.id, payload=MP(P1))`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-PL-30 — the caller's markup row filed under W2 on the same attachment is never replaced
- **Rules:** put_own_layer R5, R4; HR-16
- **Kind:** isolation
- **Expect:** pass
- **Author:** claude

**Given**
1. LW = layer(A1, U1, P2) but `workspace_id W2.id`.
2. No events.

**When**
- `sp = db.begin_nested()`; `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id, payload=MP(P1))`; if it raises `IntegrityError`, `sp.rollback()`, else `sp.commit()` (today's insert can fail on the unique `(attachment_id, user_id)` constraint; see Spec gap 5).

**Then**
1. re-read LW: `workspace_id == W2.id`, `payload == D(P2)`.
2. count: `attachment_markups` rows with `attachment_id == A1.id` and `workspace_id == W2.id` is exactly 1.
3. count: events_of(A1) rows with `event_type == "markup_updated"` is exactly 0.

### AMUP-PL-31 — only the leading "Updated marks" becomes "Saved marks"
- **Rules:** put_own_layer R3 (G5); _summarize_payload R2, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No layers, no events.

**When**
- `M.put_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U2.id, payload=MP({"Updated marks": {"strokes": [STROKE]}}))`

**Then**
1. count: events_of(A1) has exactly 1 row.
2. re-read that event: `event_type == "markup_saved"`, `description == "Saved marks on page Updated marks"`, `metadata_json == {"pages": ["Updated marks"]}`.

## `AttachmentMarkupManager.delete_own_layer`

### AMUP-DL-01 — the caller's layer is deleted and markup_cleared is logged
- **Rules:** delete_own_layer R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. LA = layer(A1, U1, P1). L = layer(A1, U2, P1). LG = layer(A1, UG, P1).

**When**
- `result = M.delete_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U2.id, session_id="tab-4")`

**Then**
1. returns: `result is None`.
2. returns: `uids(layers_of(A1)) == [U1.id, UG.id]`.
3. re-read LA: `payload == D(P1)`.
4. re-read the one row of events_of(A1): `workspace_id == W1.id`, `user_id == U2.id`, `event_type == "markup_cleared"`, `description == "Cleared marks"`, `metadata_json == {"pages": []}`, `session_id == "tab-4"`.

### AMUP-DL-02 — no own layer: nothing deleted, no event, no error
- **Rules:** delete_own_layer R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. layer(A1, U1, P1). layer(A1, UG, P1).

**When**
- `result = M.delete_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U2.id)`

**Then**
1. returns: `result is None`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-DL-03 — the caller's layer on another attachment is not deleted
- **Rules:** delete_own_layer R2, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. AH = att("high.png"). LX = layer(AH, U1, P1).

**When**
- `result = M.delete_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id)`

**Then**
1. returns: `result is None`.
2. re-read LX: `payload == D(P1)`.
3. count: events_of(A1) has exactly 0 rows.

### AMUP-DL-04 — an unknown attachment deletes nothing
- **Rules:** delete_own_layer R1
- **Kind:** error
- **Expect:** pass

**Given**
1. layer(A1, U1, P1).

**When**
- `M.delete_own_layer(db, workspace_id=W1.id, attachment_id=MISSING, user_id=U1.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == "Attachment 999999999 not found."`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-DL-05 — a soft-deleted attachment keeps its layer
- **Rules:** delete_own_layer R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AD = deleted att("gone.png"). layer(AD, U1, P1).

**When**
- `M.delete_own_layer(db, workspace_id=W1.id, attachment_id=AD.id, user_id=U1.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(AD)`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-DL-06 — a W2 attachment keeps its layer
- **Rules:** delete_own_layer R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A9 = att("far.png") but `workspace_id W2.id`. `AttachmentMarkup(workspace_id=W2.id, attachment_id=A9.id, user_id=U1.id, payload=D(P1))`, flushed.

**When**
- `M.delete_own_layer(db, workspace_id=W1.id, attachment_id=A9.id, user_id=U1.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A9)`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-DL-07 — a failed attachment keeps its layer
- **Rules:** delete_own_layer R1
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = att("bad.png") but `upload_status "failed"`, then link(A2, "scratch", 2). layer(A2, U1, P1).

**When**
- `M.delete_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U1.id)`

**Then**
1. raises: `AttachmentValidationError`, `str(exc.value) == UNAV`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-DL-08 — a private project's attachment refuses a plain member, layer kept
- **Rules:** delete_own_layer R1a [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. P = proj("Tender 7"), private.
2. A2 = att("contract.png"), then link(A2, "project", P.id). layer(A2, UG, P1) (from before the project became private).

**When**
- `M.delete_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-DL-09 — another member's ticket attachment refuses, layer kept
- **Rules:** delete_own_layer R1a [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. T = ticket("HT-1").
2. A2 = att("shot.png"), then link(A2, "support_ticket", T.id). layer(A2, UG, P1).

**When**
- `M.delete_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=UG.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-DL-10 — a component of a deleted project refuses, layer kept
- **Rules:** delete_own_layer R1a [BUG-2115]
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the record is not looked at)

**Given**
1. P = proj("Old Job"), deleted. C = comp(P, "Roof").
2. A2 = att("roof.png"), then link(A2, "project_component", C.id). layer(A2, U2, P1).

**When**
- `M.delete_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U2.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-DL-11 — the ticket's creator clears their layer on its attachment
- **Rules:** delete_own_layer R1a (granted side of BUG-2115), R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = ticket("HT-1").
2. A2 = att("shot.png"), then link(A2, "support_ticket", T.id). layer(A2, U1, P1).

**When**
- `result = M.delete_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U1.id)`

**Then**
1. returns: `result is None`.
2. count: layers_of(A2) has exactly 0 rows.

### AMUP-DL-12 — delete_own_layer flushes, never commits
- **Rules:** delete_own_layer Side effects (no commit)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. layer(A1, U1, P1).

**When**
- Rolled back: `M.delete_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id)`

**Then**
1. mock called: `cm.call_count == 0`.
2. count: layers_of(A1) has exactly 1 row.
3. count: events_of(A1) has exactly 0 rows.

### AMUP-DL-13 — a removed (inactive) owner-role member is refused another member's ticket, layer kept
- **Rules:** delete_own_layer R1a [BUG-2115]; PR-5 (active membership only)
- **Kind:** bug
- **Expect:** xfail BUG-2115
- **Fails today on:** Then 1 (no error is raised: the layer is deleted)

**Given**
1. U3 = `make_profile(db, name="Rafi Das")`; member(U3, "owner", status="inactive").
2. T = ticket("HT-1") (`created_by U1.id`).
3. A2 = att("shot.png"), then link(A2, "support_ticket", T.id). layer(A2, U3, P1).

**When**
- `M.delete_own_layer(db, workspace_id=W1.id, attachment_id=A2.id, user_id=U3.id)`

**Then**
1. raises: `AttachmentNotFoundError`, `str(exc.value) == NF(A2)`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. nothing written.

### AMUP-DL-14 — the caller's markup row filed under W2 on the same attachment is not deleted
- **Rules:** delete_own_layer R3, R4; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. LW = layer(A1, U1, P2) but `workspace_id W2.id`.
2. No events.

**When**
- `result = M.delete_own_layer(db, workspace_id=W1.id, attachment_id=A1.id, user_id=U1.id)`

**Then**
1. returns: `result is None`.
2. session: `not db.new`, `not db.dirty`, `not db.deleted`.
3. re-read LW: `workspace_id == W2.id`, `payload == D(P2)`.
4. count: events_of(A1) has exactly 0 rows.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 (a) | `AttachmentMarkupService` / endpoints | the caller's user id is passed down; the role is read by the manager from the active membership (PR-5, BUG-2115, BUG-1885) |
| Errors mapping | endpoints (integration) | `AttachmentNotFoundError` → 404, `AttachmentValidationError` → 400, cleared layer → 204 |
| D5 real race | integration | two committed first saves of one user: both succeed, second as update (BUG-2120) |
| FU-2 | profile stamp fix | one shared minted-form helper used by profile save and by `_resolve_saved_stamp` |

## Spec gaps
Revision 1 gaps 1–4 were closed by the spec's fill-gaps revision (2026-11-04): 1 → PR-5, 2 → PR-3 link rule (AMUP-GR-59…61, LL-13, PL-28), 3 → parent builder columns (GR-46…51), 4 → scribble shape (SP-11).

| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 5 | `put_own_layer` R3 / R5 / R5a [BUG-2120] vs markup DAO `uq_attachment_markup_user` on `(attachment_id, user_id)` without `workspace_id` (DAO R6) | When the caller already has a markup row on the attachment that is filed under another workspace, the spec does not say what `put_own_layer` should do. A W1 `markup_saved` insert cannot succeed under the unique constraint. BUG-2120's "apply the save to that row" would update the foreign row. Today the save raises `IntegrityError`. | AMUP-PL-30 (Author: claude) asserts only that the W2 row is never replaced and no `markup_updated` event is written. It accepts an `IntegrityError` inside a savepoint. Neither the error nor a new W1 layer is asserted. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_get_ready_attachment` | R1 | AMUP-GR-01, 02, 12, 25, 46, 51, 61, 62 |
| | R2 / Errors 1 | AMUP-GR-03, 04, 05, 06 |
| | R3 / Errors 2 | AMUP-GR-07, 08 |
| | R4 | AMUP-GR-09, 10 |
| | R5 [BUG-2115] | AMUP-GR-11 … 67 (PR-3 links: 59, 60, 61; PR-5 roles: 21, 52 … 58; PR-2 non-member: 62, 63; admin on private project / component: 64, 65; W2 / W0 ticket: 66, 67) |
| | R5 [BUG-2103] (workspace owner, tickets) | AMUP-GR-68 |
| `_is_markupable` | R1 | AMUP-IM-01, 04 |
| | R2 | AMUP-IM-02, 03, 09 |
| | R3 | AMUP-IM-05, 06, 07, 10 |
| | R4 | AMUP-IM-08, 09, 10 |
| `_resolve_user_name` | R1 | AMUP-UN-01, 02 |
| | R2 | AMUP-UN-03 |
| `_resolve_saved_stamp` | R1 | AMUP-SS-08, AMUP-PL-27 |
| | R2 | AMUP-SS-01, 02, 03 |
| | R3 | AMUP-SS-04, 05, 06 |
| | R4 | AMUP-SS-07, 08 |
| | R4a [BUG-2116] | AMUP-SS-10, 11, 27 (pass); AMUP-SS-15 … 26, 28 … 32 (xfail) |
| | R4b [BUG-2117] | AMUP-SS-10 (fields kept); AMUP-SS-12, 13, 14 |
| | R5 | AMUP-SS-09, 33 |
| `_summarize_payload` | R1 | AMUP-SP-02, 03, 10, 11 |
| | R2 | AMUP-SP-01, 04, 05 |
| | R3 | AMUP-SP-04, 06, 07 |
| | R4 | AMUP-SP-01, 03, 05, 07, 08, 11 |
| | R5 | AMUP-SP-09, 10 |
| `_log_markup_event` | R1 | AMUP-LE-01, 02 |
| `_to_layer_response` | R1 | AMUP-TL-01, 02 |
| | R2 | AMUP-TL-03 |
| `_to_event_response` | R1 | AMUP-TE-01, 02 |
| `list_layers` | R1 | AMUP-LL-06, 07 |
| | R1a [BUG-2115] | AMUP-LL-08, 09, 10, 13, 14; granted side AMUP-LL-11 (pass) |
| | R2 | AMUP-LL-01, 02 |
| | R3 [BUG-1435] | AMUP-LL-03, 04, 05 |
| | R4 [BUG-2119] | AMUP-LL-12 |
| `list_events` | R1 | AMUP-LV-07, 08 |
| | R1a [BUG-2115] | AMUP-LV-09, 10 |
| | R2 | AMUP-LV-01, 02, 05 |
| | R3 [BUG-1436, BUG-1437] | AMUP-LV-03, 04, 06 |
| | R4 [BUG-2119] | AMUP-LV-11 |
| `put_own_layer` | R1 / Errors 1 | AMUP-PL-10, 11, 12, 13, 14 |
| | R1a [BUG-2115] | AMUP-PL-15 … 19, 21, 28, 29; granted side AMUP-PL-20 (pass) |
| | R2 | AMUP-PL-06, 07 |
| | R2a | AMUP-PL-08 |
| | R3 | AMUP-PL-01, 02, 03, 09, 31 |
| | R4 | AMUP-PL-04 |
| | R5 | AMUP-PL-05, 06, 30 |
| | R5a [BUG-2120] / Errors 2 | AMUP-PL-25 |
| | R6 | AMUP-PL-01, 04, 22, 27 |
| | R7 | AMUP-PL-01, 04 |
| | R7a [BUG-2118] | AMUP-PL-22 (pass part), 23, 24 |
| | no commit | AMUP-PL-26 |
| `delete_own_layer` | R1 | AMUP-DL-04, 05, 06, 07 |
| | R1a [BUG-2115] | AMUP-DL-08, 09, 10, 13; granted side AMUP-DL-11 (pass) |
| | R2 | AMUP-DL-01, 03 |
| | R3 | AMUP-DL-02, 03, 14 |
| | R4 | AMUP-DL-01, 02, 14 |
| | no commit | AMUP-DL-12 |
