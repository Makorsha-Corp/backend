# Spec — `app/managers/attachment_markup_manager.py`

> **Status:** APPROVED (2026-11-04; nothing open. Every item was decided under the reviewer's delegation (2026-11-04) or follows an owner answer: OQ-5 / OQ-18 (visibility), OQ-11 / OQ-12 (stamps).)
> **Source commit:** e48a092
> **Revision 2026-11-04 (cases gap 5):** note on a caller's markup row filed under another workspace (HR-16 invalid data; left untouched, no event; repaired by hand); FU-3 records that the audit script already covers `attachment_markups` and `attachment_markup_events` (corrected 2026-11-04: closed). No rule changed.
> **Revision 2026-11-04 (verifier mutant #61, decided by Claude under the reviewer's delegation (2026-11-04)):** `put_own_layer` R3 states that only the first "Updated marks" becomes "Saved marks". PR-2 now includes the workspace owner for help tickets (attachment manager spec, BUG-2103). Status stays APPROVED.
> **Revision 2026-11-04 (fill-gaps, cases gaps 1–4):** caller parameters fixed by `attachment_manager.spec.md` PR-5 (no `role` parameter; the manager reads the caller's active role and platform-admin flag itself; `_get_ready_attachment` gains a required keyword `user_id`; public methods pass their existing `current_user_id` / `user_id`). PR-3 now says which links count (only the caller's workspace's; none → 404). Parent builder columns: attachment manager Facts. `scribbles` shape stated. No new bug. Status stays APPROVED.

> **Below / beside.** DAOs, cited not restated: `tests/unit/dao/attachment.spec.md` (`get_active`), `tests/unit/dao/attachment_markup.spec.md` (`get_for_attachment`, `get_for_user`, `upsert_for_user`, `delete_for_user`; BUG-1435), `tests/unit/dao/attachment_markup_event.spec.md` (`list_for_attachment`, `create_event`; BUG-1436, BUG-1437), `tests/unit/dao/base.spec.md` (`BaseDAO.get`, used as `profile_dao.get`). Siblings: `tests/unit/managers/attachment_manager.spec.md` (**Parent-record rule PR-1 … PR-3**, defined there), `tests/unit/managers/profile_stamp_manager.spec.md` (the saved stamp: minted `public_id` form, server-built `url`; BUG-1864 … BUG-1866, FU-1 (b)).
>
> **Standing decisions applied here (not asked again):** OQ-5 (owner, 2026-11-04: attachments follow the record's own visibility; who cannot open it gets 404) and OQ-18 (owner: attached records answer 404, project pages keep 403) → BUG-2115. OQ-11 / OQ-12 (owner: a stamp's `public_id` is accepted only in the user's own minted form, and its `url` is built by the server) → BUG-2116, BUG-2117 for stamps already stored before that fix. HR-16: every read and write here is scoped by the caller's workspace through `attachment_dao.get_active`.
>
> **Read, not run.** Behaviour was read in the code and in the approved DAO specs (whose rules were run on `marker_test`). Nothing new needed a database run.

## Review
> All items decided; nothing pending.

### Quick list — all decided
| # | What the code does today, in plain words | Decision | Decided by |
|---|---|---|---|
| D1 | Any member can see, save and clear marks on an attachment of a private project or of another member's help ticket | bug — follows the parent record (PR-3): 404 `Attachment <id> not found.` (BUG-2115) | Claude, as a consequence of OQ-5 / OQ-18 |
| D2 | Each author's saved stamp is sent to every viewer exactly as stored: an old image stamp may name another file and a web address the client chose | bug — an image stamp is sent only in the author's own minted form (BUG-2116), with a server-built `url` (BUG-2117) | Claude, as a consequence of OQ-11 / OQ-12 |
| D3 | Saving the same marks again writes a "markup_updated" history entry | bug — an unchanged save writes no entry (BUG-2118) | Claude, delegated |
| D4 | Listing layers or history reads the author's profile once or twice per row | bug — authors read together (BUG-2119) | Claude, delegated (BUG-1964 precedent) |
| D5 | Two first saves by one user at the same moment: the second answers 500 | bug — both succeed, the second as an update (BUG-2120) | Claude, delegated (BUG-727 precedent) |
| D6 | Old marks show the author's **current** saved stamp, not the one they had when marking | intended | Claude, delegated |
| D7 | A pending (not yet confirmed) image answers 400 "Markup is only available for images and PDFs." | intended | Claude, delegated |
| D8 | Layers and history of people who have since left the workspace are still shown | intended | Claude, delegated |
| D9 | A stroke with no points, or a page key that is not a page of the document, counts as a mark | intended | Claude, delegated |

### House-rule violations — applied automatically
None new. **HR-6** — layer order and history order are the DAO's (BUG-1435, BUG-1436); the manager keeps the DAO's order. The history cap is the DAO's (BUG-1437).

Checked and **not** a line here: **HR-4** — the attachment is found with `get_active`, so a soft-deleted attachment answers 404 before any layer is read (`_get_ready_attachment` R2). Markup rows have no soft delete. **HR-5, HR-7, HR-8** — no paging in the manager, no `LIKE`. **HR-9** — no "changed by" field; D3 is the event-log form of it (BUG-632 precedent). **HR-10** — markup is not money, stock or approvals; D5 is about a 500, not a lock. **HR-16** — the attachment must be in the caller's workspace (`get_active`); markup rows and events are written with the caller's workspace and user. **HR-1 … HR-3, HR-11 … HR-15** — none applies.

### Precedent matches — all applied (decided by Claude under the reviewer's delegation, 2026-11-04)

### D1. Marks on a private record's attachment are open to every member — 🐞 BUG-2115
**Background:** An attachment belongs to a record (purchase order, project, help ticket, …). The owner's OQ-5 answer: attachments follow the record's own visibility, and someone who may not open the record gets 404 (OQ-18: 404, not 403, for attached records). Markup is drawing over an attachment, and the history panel shows who drew what.
**What happens today:** The manager checks only that the attachment is live, ready and in the caller's workspace. It never looks at the record.
**Example:** Rina's help ticket has a screenshot. Karim, a `ground-team` member, gets 403 on the ticket page, but `GET /attachments/<id>/markups` shows Rina's circles and notes, and `PUT …/markups/me` lets him draw on it (200).
**Rules affected:** `_get_ready_attachment` R5; `list_layers` R1a, `list_events` R1a, `put_own_layer` R1a, `delete_own_layer` R1a
**Answer:** bug — per OQ-5 / OQ-18: every markup action follows `attachment_manager.spec.md` Parent-record rule PR-3 (404 `Attachment <id> not found.`, nothing written). The caller is the existing `current_user_id` / `user_id`; the role and platform-admin flag are read by the manager (PR-5).
**Resolution:** decided by Claude as a consequence of the owner's OQ-5 answer (2026-11-04): 🐞 BUG-2115 (pattern `child-ignores-parent-visibility`).

### D2. Stamps saved before the stamp fix reach every viewer as stored — 🐞 BUG-2116, BUG-2117
**Background:** A user's saved stamp lives on their profile (`profiles.saved_stamp`, JSONB). BUG-1864 / BUG-1866 (owner, OQ-11 / OQ-12) make the profile accept an image stamp only when its `public_id` is the user's own minted name (`profiles/<user id>/stamp-` + 32 lowercase hex, with the environment prefix outside production), and make the server build its `url`. Rows saved before that fix keep what the browser sent (profile stamp spec FU-1 (b)). Listing an attachment's layers sends each author's saved stamp with the layer.
**What happens today:** `saved_stamp` is sent exactly as stored, any `public_id` and any `url`.
**Example:** Before the fix, Karim saved `{"kind": "image", "public_id": "ws-3/9f2c…", "url": "https://tracker.example/p.png", …}`. Everyone who opens a drawing Karim marked loads `tracker.example`, which learns their address and when they looked.
**Rules affected:** `_resolve_saved_stamp` R4, R4a, R4b
**Answer:** bug — consistent with OQ-11 / OQ-12: an image stamp is sent only if its `public_id` is exactly the author's own minted form (BUG-2116); its `url` is the one the server builds from that `public_id`, never the stored one (BUG-2117). Otherwise `saved_stamp` is `None`. Vector stamps unchanged.
**Resolution:** decided by Claude as a consequence of the owner's OQ-11 / OQ-12 answers (2026-11-04): 🐞 BUG-2116 (pattern `unverified-client-file-reference`), 🐞 BUG-2117 (pattern `derived-value-accepted-from-client`).

### D3. An unchanged save writes a history entry — 🐞 BUG-2118
**Background:** The markup history (`attachment_markup_events`) is the record of who changed marks. The DAO does not rewrite a layer whose payload is equal to the stored one (`upsert_for_user` R4; DAO FU-1 (b)). The web app saves the whole layer each time.
**What happens today:** Every non-empty save logs `markup_updated` "Updated marks on page 1", even when nothing changed.
**Example:** Anika opens a drawing, changes nothing, the editor saves twice. The history shows two "Updated marks on page 1" by Anika.
**Rules affected:** `put_own_layer` R7a
**Answer:** bug — per BUG-632 precedent: a save whose payload (after validation) equals the stored payload writes no event; the layer is returned as usual.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04): 🐞 BUG-2118 (pattern `audit-event-on-noop`).

### D4. Each layer and history row reads its author's profile — 🐞 BUG-2119
**Background:** `BaseDAO.get` always runs a query (`query().first()`), even for a profile already loaded.
**What happens today:** `list_layers` reads the author's profile twice per layer (name, stamp); `list_events` once per entry, the same person again each time. The history holds every entry (BUG-1437).
**Example:** A drawing with 300 history entries by 3 people makes 300 profile reads.
**Rules affected:** `list_layers` R4, `list_events` R4
**Answer:** bug — per BUG-1964 precedent: authors read together; the result is unchanged.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04): 🐞 BUG-2119 (pattern `n-plus-one-read`).

### D5. Two first saves at once — the second answers 500 — 🐞 BUG-2120
**Background:** One layer per user per attachment (`uq_attachment_markup_user`). The save looks for the user's layer, and inserts one if there is none (DAO `upsert_for_user` R1; DAO FU-1 (a)). The endpoint maps `ValueError` to 400; an `IntegrityError` is not one.
**What happens today:** Two saves from one user in two tabs, both before any layer exists: both see "none", the second insert fails with `IntegrityError` 23505 → 500, its marks lost.
**Example:** Anika has a drawing open in two tabs and saves in both within a moment: one tab shows "Something went wrong".
**Rules affected:** `put_own_layer` R5a
**Answer:** bug — per BUG-727 precedent: the second save is applied as an update of the row the first one created (`markup_updated`), no 500. No lock is needed (HR-10 scope).
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04): 🐞 BUG-2120 (pattern `count-then-insert-race`).

### New questions — all decided

### D6. Old marks show the author's current stamp — ✅ intended
**Background:** A layer's payload stores only where a stamp sits (`MarkupStamp`: `id`, `x`, `y`, `width`, `height`, `rotation`), not the picture. The picture is the author's saved stamp, read at listing time.
**What happens today:** When Karim changes his saved stamp, every drawing he stamped shows the new one; if he removes it, his stamps have no picture (`saved_stamp` `None`).
**Example:** Karim stamped 40 delivery notes in March with his old signature; in May he saves a new one; all 40 now show the May signature.
**Rules affected:** `_resolve_saved_stamp` R1, `_to_layer_response` R1
**Answer:** intended — the stamp is a personal mark placed by the author; the history entries (who saved when) are the record. If stamps ever need to be fixed in time (e.g. approval signatures), that is a new feature (`docs/future/permissions.md` note).
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04). Rules unchanged ✅.

### D7. A pending image gets the "only images and PDFs" message — ✅ intended
**What happens today:** Not ready and not markable give the same 400 `Markup is only available for images and PDFs.`
**Example:** A photo whose upload is not yet confirmed answers that it is not an image.
**Rules affected:** `_get_ready_attachment` R3
**Answer:** intended — the web app offers markup only on ready attachments; the message is never seen there.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04). Rules unchanged ✅.

### D8. Layers of people who left are still shown — ✅ intended
**What happens today:** Layers and history entries are never filtered by the author's membership; the author's name and stamp are still sent.
**Answer:** intended — marks are part of the document's history (as discussion messages are).
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04). Rules unchanged ✅ (`list_layers` R2, `list_events` R2).

### D9. Empty strokes and any page key count as marks — ✅ intended
**What happens today:** A page with one stroke of zero points counts as content (the layer is saved, the page is named in the summary). Page keys are any strings; they are not compared with the document's page count.
**Answer:** intended — the schema bounds the size (50,000 points); what a page key means is the web app's.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04). Rules unchanged ✅ (`_summarize_payload` R1, `put_own_layer` R3).

## Follow-ups for other reviews
| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Attachment markup service / endpoints** (`app/services/attachment_markup_service.py`, `app/api/v1/endpoints/attachments.py`; no spec yet) | (a) BUG-2115: the service already passes the caller's id; the manager reads the active role and platform-admin flag itself (attachment manager PR-5), so nothing more is passed down. (b) `list_layers` and `list_events` commit after a read: harmless. (c) `put_own_layer`'s endpoint returns 204 for a cleared layer. | D1, reading the callers |
| FU-2 | **Profile stamp fix (BUG-1864 … BUG-1866)** | The minted-form test and the url builder should be one shared helper, used both on save (profile) and on display (here, BUG-2116 / BUG-2117). | D2 |
| FU-3 | **Cross-workspace audit script** (`scripts/find_cross_workspace_rows.py`) | ✅ Closed (2026-11-04): already covered. The script checks every foreign key between two tables that both have `workspace_id`; `attachment_markups.attachment_id` and `attachment_markup_events.attachment_id` both point at `attachments`, so rows whose `workspace_id` differs from their attachment's are already listed for repair by hand (gap 5 note below). Nothing to change. | cases gap 5 |

## Overview
`AttachmentMarkupManager` keeps each user's drawing layer ("markup") over a ready image or PDF attachment, and an append-only history of changes. A user may save or clear only their own layer; every member who may see the attachment sees every layer, with the author's name and saved stamp. Its only caller is `AttachmentMarkupService` (`GET /attachments/{id}/markups`, `GET …/markups/events`, `PUT …/markups/me`, `DELETE …/markups/me`), which commits or rolls back. The manager never commits. It protects: the attachment must be live, ready, markable and in the caller's workspace before anything is read or written.

**Callables:** 12 specified · 0 not specified
**Externals to mock:** none today. The stamp `url` built under BUG-2117 uses the Cloudinary URL builder (`build_signed_delivery_url`, no network call); set `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` in settings for those cases. `utcnow` only through the event DAO (`created_at`).
**Integration-only behavior:** the 404 / 400 / 204 mapping in the endpoints; the race of D5 needs two committed transactions (see Notes).

**Facts for the test designer**
- Import: `from app.managers.attachment_markup_manager import AttachmentMarkupManager, attachment_markup_manager`; errors `from app.managers.attachment_manager import AttachmentNotFoundError, AttachmentValidationError` (both `ValueError`). Every parameter after `session` is keyword-only, except `_resolve_user_name(session, user_id)` and `_resolve_saved_stamp(session, user_id)` (positional).
- `MARKUP_UNAVAILABLE_MSG == "Markup is only available for images and PDFs."`; not found: `Attachment <id> not found.`
- Schemas (`app/schemas/attachment_markup.py`): `MarkupPayload(pages: dict[str, PageMarks] = {})`; `PageMarks(strokes, texts, scribbles, stamps)` lists, default empty; total of stroke + scribble points + texts + stamps ≤ 50,000 (else `ValueError` "Markup exceeds maximum of 50000 points."); `MarkupPoint x, y ∈ [0, 1]`; `MarkupStroke(color 1–32, width (0, 1], points: list[MarkupPoint] = [])` — **a `scribbles` item has exactly this shape** (gap 4), e.g. `{"color": "#f00", "width": 0.01, "points": [{"x": 0.1, "y": 0.2}]}`; a scribble with an empty `points` list still makes its page count (`_summarize_payload` R1); `MarkupText(x, y, text 1–500, color 1–32, size (0, 1])`; `MarkupStamp(id ≤ 36 or None, x, y, width (0, 1], height (0, 1], rotation [-360, 360] default 0)`. `is_markup_payload_empty`: no pages, or every page has all four lists empty.
- `AttachmentMarkupLayerResponse(user_id, user_name, is_mine, updated_at, payload, saved_stamp: dict | None)`; `AttachmentMarkupEventResponse(id, user_id, user_name, is_mine, session_id, event_type, description, metadata_json, created_at)`.
- Event types written: `markup_saved`, `markup_updated`, `markup_cleared`.
- Stamp shapes (profile stamp spec): vector `{"kind": "vector", "strokes": […], "viewBox": {…}}`; image `{"kind": "image", "public_id", "url", "width", "height"}`. Minted image `public_id`: `profiles/<user id>/stamp-` + exactly 32 lowercase hex, prefixed `<env>/` outside production (`profile_stamp_manager.spec.md` `validate_saved_stamp_payload` R4a).
- `Profile.saved_stamp` is JSONB, nullable; `Profile.name` NOT NULL. Markup and event rows cascade when the profile is deleted.

**Notes for the test designer**
- **A caller's markup row filed under another workspace** (cases gap 5; decided by Claude under the reviewer's delegation (2026-11-04)): for an attachment of this workspace, a row of the same `(attachment_id, user_id)` carrying another `workspace_id` is invalid data under HR-16 and no valid path writes it. The unique key `uq_attachment_markup_user` has no workspace, so it is that user's only row for the attachment. No behaviour is designed for it beyond this: the manager leaves the foreign row untouched and writes no event about it (case PL-30). It is repaired by hand from the audit script (FU-3).
- Build a ready attachment directly: `Attachment(workspace_id, file_name, mime_type, file_size, uploaded_by, upload_status="ready", format=…)`, flush; a link (`AttachmentLink`) to its parent for the PR-3 cases.
- **BUG-2115:** build an `invited_only` project (`ProjectManager.can_access_project` false for a plain `ground-team` member who is not creator or project member) and a help ticket by another member; call each public method with that member → `AttachmentNotFoundError` `Attachment <id> not found.`, no row or event written. New parameters: follow the attachment manager spec's PR-3 signature. Strict xfail.
- **BUG-2116 / BUG-2117:** set `profile.saved_stamp` directly (bypassing the profile manager) to a foreign `public_id`, or to a minted one with `url` `"https://tracker.example/p.png"`. Strict xfail.
- **BUG-2118:** save payload P, then P again → events count stays 1. Strict xfail.
- **BUG-2119:** count statements with a SQLAlchemy `before_cursor_execute` listener: 5 layers by 2 authors → at most a fixed number of profile statements (≤ 2), result unchanged. Strict xfail.
- **BUG-2120:** simulate by patching `app.dao.attachment_markup.AttachmentMarkupDAO.get_for_user` to return `None` while the user's row already exists → today `IntegrityError` (23505); intended: no error, one row with the new payload, one `markup_updated` event. Use a savepoint so the failed flush does not poison the test transaction. Strict xfail.
- Layer order / history order / history cap: assert as the DAO specs (BUG-1435, BUG-1436, BUG-1437 tags carry over; compare sets of ids elsewhere).

---

## `AttachmentMarkupManager._get_ready_attachment(session, *, workspace_id, attachment_id)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** internal (used by: `list_layers`, `list_events`, `put_own_layer`, `delete_own_layer`)

**Purpose:** Find the attachment a markup action is about, and refuse it unless markup is possible.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | caller's workspace |
| `attachment_id` | int | any int |
| `user_id` | int | *(intended, BUG-2115; new keyword-only, required, no default — attachment manager PR-5)* the caller; the public methods pass their `current_user_id` / `user_id` |

**Returns:** the `Attachment` row.

**Rules:**
- **R1.** A live attachment of the caller's workspace that is `ready` and markable (`_is_markupable` R1–R4) is returned.
- **R2.** An unknown id, a soft-deleted attachment, or one of another workspace → `AttachmentNotFoundError("Attachment <id> not found.")` (`attachment_dao.get_active`, attachment DAO spec).
- **R3.** ✅ (D7) An attachment whose `upload_status` is not `ready` (`pending`, `failed`) → `AttachmentValidationError(MARKUP_UNAVAILABLE_MSG)`, whatever its type.
- **R4.** A ready attachment that is not markable (e.g. `text/csv`, a `.docx`) → `AttachmentValidationError(MARKUP_UNAVAILABLE_MSG)`.
- **R5.** [BUG-2115] (D1, OQ-5) An attachment whose linked record the caller may not open, or whose record is missing, deleted or of another workspace (`attachment_manager.spec.md` Parent-record rule PR-1 … PR-3) → `AttachmentNotFoundError("Attachment <id> not found.")`, exactly as R2; checked before R3 / R4, so a hidden attachment never reveals its state. *(Today: the record is never looked at. Requires the new required `user_id`; role and platform-admin flag read per PR-5.)* Which links count: only those in the caller's workspace; an attachment with none answers as R2 (PR-3).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing / deleted / other workspace (R2); hidden parent (R5, BUG-2115) | `AttachmentNotFoundError` | `Attachment <id> not found.` |
| not ready (R3) or not markable (R4) | `AttachmentValidationError` | `Markup is only available for images and PDFs.` |

**Side effects:** none.

---

## `AttachmentMarkupManager._is_markupable(attachment)` (static)
**Shape:** compute
**Persistence:** pure
**Visibility:** internal (used by: `_get_ready_attachment`)

**Purpose:** Say whether an attachment can carry markup: images and PDFs.

**Rules:**
- **R1.** `mime_type == "application/pdf"` → `True`.
- **R2.** `format` equal to `"pdf"` ignoring case (`"PDF"`, `"pdf"`) → `True`, whatever the MIME type.
- **R3.** Otherwise `True` exactly when `mime_type` starts with `image/` (case-sensitive: `image/png`, `image/heic` yes; `Image/png` no).
- **R4.** `mime_type` `None` and `format` `None` → `False` (both read as `""`).

**Side effects:** none.

---

## `AttachmentMarkupManager._resolve_user_name(session, user_id)`
**Shape:** helper
**Persistence:** reads
**Visibility:** internal (used by: `_to_layer_response`, `_to_event_response`)

**Rules:**
- **R1.** Returns the profile's `name` for an existing profile, whatever its workspaces or membership (D8).
- **R2.** No profile with that id → `"User #<id>"` (e.g. `"User #999"`). Through the API unreachable: layer and event rows cascade with the profile.

**Side effects:** none.

---

## `AttachmentMarkupManager._resolve_saved_stamp(session, user_id)`
**Shape:** helper
**Persistence:** reads
**Visibility:** internal (used by: `_to_layer_response`)

**Purpose:** The author's saved stamp, sent with their layer so stamps on the drawing have a picture.

**Rules:**
- **R1.** ✅ (D6) The stamp read is the author's **current** `profiles.saved_stamp`, at the time of listing.
- **R2.** No profile, or `saved_stamp` `None` or empty (`{}`) → `None`.
- **R3.** A stored value that is not a JSON object (a list, a string, a number) → `None`.
- **R4.** A vector stamp (`kind` `"vector"`) is returned as stored.
- **R4a.** [BUG-2116] (D2, OQ-11) An image stamp (`kind` `"image"`) is returned only when its `public_id` is exactly the **author's** own minted form (`profile_stamp_manager.spec.md` `validate_saved_stamp_payload` R4a: prefix `profiles/<author id>/stamp-`, `<env>/` before it outside production, then exactly 32 lowercase hex, nothing after). Otherwise `None`: another user's stamp, an attachment's `ws-3/9f2c…`, the bare prefix, a missing `public_id`. *(Today: returned as stored.)*
- **R4b.** [BUG-2117] (D2, OQ-12) For an image stamp returned by R4a, `url` is built by the server from the `public_id` (authenticated Cloudinary delivery address of this cloud, starting `https://res.cloudinary.com/<CLOUDINARY_CLOUD_NAME>/image/authenticated/` and containing the `public_id`, as profile stamp R4b); the stored `url` never appears. `kind`, `public_id`, `width`, `height` are returned as stored. *(Today: the stored `url`, e.g. `https://tracker.example/p.png`, is sent.)*
- **R5.** Any other stored object (no `kind`, an unknown `kind`) is returned as stored today. *(Not reachable through the profile API, which accepts only the two kinds; no change decided.)*

**Side effects:** none.

---

## `AttachmentMarkupManager._summarize_payload(payload)` (static)
**Shape:** compute
**Persistence:** pure
**Visibility:** internal (used by: `put_own_layer`)

**Purpose:** Build the history entry's page list and description for a save.

**Returns:** `(metadata, description)` where `metadata == {"pages": [...]}`.

**Rules:**
- **R1.** ✅ (D9) A page counts when at least one of its four lists (strokes, texts, scribbles, stamps) is non-empty; a stroke with no points counts.
- **R2.** A counted page key that Python's `int()` accepts becomes that integer: `"3"` → `3`, `"03"` → `3`, `" 2"` → `2`, `"-1"` → `-1`, `"1_0"` → `10`. Any other key stays a string (`"cover"`, `"1.5"`).
- **R3.** Pages are sorted integers first (ascending), then strings (ascending): `{"b", "10", "2", "a"}` → `[2, 10, "a", "b"]`. Two keys giving the same integer (`"1"`, `"01"`) both appear: `[1, 1]`.
- **R4.** One page → description `"Updated marks on page <p>"`; more → `"Updated marks on pages <p1>, <p2>, …"` in R3 order (e.g. `"Updated marks on pages 1, 3, cover"`).
- **R5.** No counted page → `({"pages": []}, "Updated marks")`.

**Side effects:** none.

---

## `AttachmentMarkupManager._log_markup_event(session, *, workspace_id, attachment_id, user_id, event_type, description, session_id=None, metadata_json=None)`
**Shape:** event-log
**Persistence:** writes
**Visibility:** internal (used by: `put_own_layer`, `delete_own_layer`)

**Rules:**
- **R1.** One history row is written and flushed with exactly the given values (`create_event` R1–R4 of the event DAO spec; `created_at` naive UTC now).

**Side effects:** one `attachment_markup_events` row, flushed.

---

## `AttachmentMarkupManager._to_layer_response(session, *, row, current_user_id)`
**Shape:** mapper
**Persistence:** reads
**Visibility:** internal (used by: `list_layers`, `put_own_layer`)

**Rules:**
- **R1.** Returns `user_id` = the row's user, `user_name` per `_resolve_user_name`, `is_mine` = (`row.user_id == current_user_id`), `updated_at` = the row's, `payload` = the stored payload validated as `MarkupPayload`, `saved_stamp` per `_resolve_saved_stamp`.
- **R2.** A stored payload that is not a valid `MarkupPayload` (e.g. JSON `null`) raises Pydantic `ValidationError`. Unreachable through the manager, which stores only validated payloads.

**Side effects:** none.

---

## `AttachmentMarkupManager._to_event_response(session, *, row, current_user_id)`
**Shape:** mapper
**Persistence:** reads
**Visibility:** internal (used by: `list_events`)

**Rules:**
- **R1.** Returns `id`, `user_id`, `session_id`, `event_type`, `description`, `metadata_json`, `created_at` as stored; `user_name` per `_resolve_user_name`; `is_mine` = (`row.user_id == current_user_id`).

**Side effects:** none.

---

## `AttachmentMarkupManager.list_layers(session, *, workspace_id, attachment_id, current_user_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public

**Purpose:** Every user's layer on one attachment, for display.

**Returns:** list of `AttachmentMarkupLayerResponse`.

**Rules:**
- **R1.** The attachment must pass `_get_ready_attachment` (R2–R4); otherwise its error, nothing read.
- **R1a.** [BUG-2115] Hidden parent → 404 per `_get_ready_attachment` R5.
- **R2.** One response per layer of that attachment in the caller's workspace, every author included (D8), mapped per `_to_layer_response`; `is_mine` true only on the caller's own.
- **R3.** Order as the DAO's `get_for_attachment` R4 (BUG-1435). No layers → `[]`.
- **R4.** [BUG-2119] (D4) Authors' profiles are read together: the number of profile statements does not grow with the number of layers; the result is unchanged. *(Today: two profile reads per layer.)*

**Side effects:** none.

---

## `AttachmentMarkupManager.list_events(session, *, workspace_id, attachment_id, current_user_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public

**Purpose:** The markup history of one attachment.

**Returns:** list of `AttachmentMarkupEventResponse`.

**Rules:**
- **R1.** The attachment must pass `_get_ready_attachment` (R2–R4).
- **R1a.** [BUG-2115] Hidden parent → 404 per `_get_ready_attachment` R5.
- **R2.** Every history entry of that attachment in the caller's workspace, every author included, mapped per `_to_event_response`.
- **R3.** Order and completeness as the event DAO's `list_for_attachment` R3, R4 (BUG-1436; BUG-1437: no 200 cap).
- **R4.** [BUG-2119] (D4) Authors' profiles are read together, as `list_layers` R4. *(Today: one profile read per entry.)*

**Side effects:** none.

---

## `AttachmentMarkupManager.put_own_layer(session, *, workspace_id, attachment_id, user_id, payload, session_id=None)`
**Shape:** create / update / delete (by payload)
**Persistence:** writes
**Visibility:** public

**Purpose:** Save the caller's own layer; an empty payload clears it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `user_id` | int | the caller; only their own layer is touched |
| `payload` | `MarkupPayload` | validated by the schema (Facts) |
| `session_id` | str \| None | editor session tag, ≤ 36 by the request schema; stored on the event as given |

**Returns:** the saved layer (`AttachmentMarkupLayerResponse`, `is_mine` true), or `None` when the payload is empty.

**Rules:**
- **R1.** The attachment must pass `_get_ready_attachment` (R2–R4); otherwise its error, nothing written.
- **R1a.** [BUG-2115] Hidden parent → 404 per `_get_ready_attachment` R5, nothing written.
- **R2.** Empty payload (`is_markup_payload_empty`: no pages, or only pages with four empty lists) and the caller has a layer → the layer is deleted, one event `markup_cleared`, description `"Cleared marks"`, `metadata_json == {"pages": []}`, the given `session_id`; returns `None`.
- **R2a.** Empty payload and no layer → nothing written, no event; returns `None`.
- **R3.** Non-empty payload, no layer yet → a layer is created with `payload.model_dump()` (defaults filled in, unknown keys dropped); one event `markup_saved` with `metadata_json` per `_summarize_payload` and description with only the **leading** `"Updated marks"` replaced by `"Saved marks"` (first occurrence only: a page key that itself contains "Updated marks", e.g. page `"Updated marks"`, keeps it: `"Saved marks on page Updated marks"`) (e.g. `"Saved marks on page 1"`, `"Saved marks on pages 1, 2"`; a non-empty payload always names at least one page).
- **R4.** Non-empty payload, layer exists → its payload is replaced (DAO `upsert_for_user` R2, R4); one event `markup_updated`, description and metadata per `_summarize_payload`.
- **R5.** Only the caller's layer is created, replaced or deleted; other users' layers are untouched.
- **R5a.** [BUG-2120] (D5) When the caller's first layer was created by a concurrent save after this call looked (insert hits `uq_attachment_markup_user`), the save is applied to that row as R4 (`markup_updated`) and no error is raised. *(Today: `IntegrityError` 23505, 500 at the API.)*
- **R6.** The returned layer is re-read after the write (fresh `updated_at`), mapped per `_to_layer_response` with `current_user_id = user_id`.
- **R7.** The event carries `workspace_id`, `attachment_id`, `user_id` of the call.
- **R7a.** [BUG-2118] (D3) When the validated payload equals the stored one, no event is written; the layer is returned as R6 with its `updated_at` unchanged. *(Today: a `markup_updated` event is written.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| per `_get_ready_attachment` | see there | |
| concurrent first save (today, R5a) | `IntegrityError` | — |

**Side effects:** layer row inserted / updated / deleted; one event row (R2, R3, R4); flushed, not committed.

---

## `AttachmentMarkupManager.delete_own_layer(session, *, workspace_id, attachment_id, user_id, session_id=None)`
**Shape:** delete
**Persistence:** writes
**Visibility:** public

**Purpose:** Remove the caller's own layer.

**Returns:** `None`.

**Rules:**
- **R1.** The attachment must pass `_get_ready_attachment` (R2–R4); otherwise its error, nothing deleted.
- **R1a.** [BUG-2115] Hidden parent → 404 per `_get_ready_attachment` R5, nothing deleted.
- **R2.** The caller has a layer → it is hard-deleted (DAO `delete_for_user` R1) and one event `markup_cleared`, `"Cleared marks"`, `{"pages": []}`, the given `session_id` is written.
- **R3.** No layer → nothing deleted, no event, no error.
- **R4.** Other users' layers are never touched.

**Side effects:** layer row deleted and one event row (R2); flushed, not committed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 49–53 | `get_active` returns nothing → not found | `_get_ready_attachment` R2 |
| — | parent record not looked at (BUG-2115) | `_get_ready_attachment` R5 |
| 55–57 | not `ready` | `_get_ready_attachment` R3 |
| 59–61 | not markable | `_get_ready_attachment` R4, R1 |
| 71–73 | `mime_type or ""`, `(format or "").lower()` | `_is_markupable` R2, R4 |
| 75–77 | PDF by MIME or format | `_is_markupable` R1, R2 |
| 79 | `startswith("image/")` | `_is_markupable` R3 |
| 85–87 | profile found / not | `_resolve_user_name` R1, R2 |
| 93–97 | no profile / falsy stamp | `_resolve_saved_stamp` R2 |
| 99–101 | not a dict | `_resolve_saved_stamp` R3 |
| 103 | returned as stored (BUG-2116, BUG-2117) | `_resolve_saved_stamp` R4, R4a, R4b, R5 |
| 115 | loop over pages (none / one / many) | `_summarize_payload` R5, R4 |
| 117–123 | page has content | `_summarize_payload` R1 |
| 125–131 | `int()` ok / `ValueError` | `_summarize_payload` R2 |
| 135 | sort ints then strings | `_summarize_payload` R3 |
| 141–151 | pages / no pages; singular / plural | `_summarize_payload` R4, R5 |
| 183 | write event | `_log_markup_event` R1 |
| 219 | payload validated | `_to_layer_response` R2 |
| 227, 261 | `is_mine` comparison | `_to_layer_response` R1, `_to_event_response` R1 |
| 293, 331 | attachment check | `list_layers` R1, `list_events` R1 |
| 299–309 | loop over layers (zero / many); per-row profile reads | `list_layers` R2, R3, R4 |
| 337–347 | loop over events; per-row profile read | `list_events` R2, R3, R4 |
| 373 | attachment check | `put_own_layer` R1 |
| 393 | payload empty | `put_own_layer` R2, R2a |
| 395–427 | had a layer → delete + `markup_cleared` | `put_own_layer` R2 |
| 429 | return `None` | `put_own_layer` R2, R2a |
| 433 | upsert (race → IntegrityError, BUG-2120) | `put_own_layer` R3, R4, R5a |
| 449–453 | `markup_saved` vs `markup_updated`; "Saved marks" | `put_own_layer` R3, R4 |
| 457 | event always written (BUG-2118) | `put_own_layer` R7, R7a |
| 477–479 | refresh and map | `put_own_layer` R6 |
| 501 | attachment check | `delete_own_layer` R1 |
| 507–521 | deleted → event / not → nothing | `delete_own_layer` R2, R3 |

## Gap log
- G1 (attachment_markup_manager.cases.md gap 1) — Intent — `attachment_manager.spec.md` PR-5: no `role` parameter; `_get_ready_attachment` gains a required keyword `user_id`; public methods keep `current_user_id` / `user_id` and pass it on; the manager reads the active role and `is_platform_admin`. Cards drop `role=`. Decided by Claude under the reviewer's delegation (2026-11-04), consistent with the project manager and discussion service.
- G2 (gap 2) — Intent — `attachment_manager.spec.md` PR-3: only links filed under the caller's workspace count; a link under another workspace is ignored (HR-16); an attachment with no such link answers 404 `Attachment <id> not found.` (`_get_ready_attachment` R5). Part of BUG-2115's intended behaviour, no new ID. Decided by Claude under the reviewer's delegation (2026-11-04).
- G3 (gap 3) — Fact — builder columns of every parent type and its activity table: `attachment_manager.spec.md` Facts, "Parent builder columns".
- G4 (gap 4) — Fact — Overview schemas: a `scribbles` item is a `MarkupStroke` (`color`, `width`, `points`).
- G5 (attachment_markup_manager.verify.md mutant #61) — Intent — `put_own_layer` R3: only the leading "Updated marks" is replaced, a page key containing the phrase keeps it. Decided by Claude under the reviewer's delegation (2026-11-04).
- G6 (attachment_markup_manager.cases.md gap 5, 2026-11-04) — Intent — a caller's markup row under another workspace for this workspace's attachment is HR-16 invalid data: left untouched, no event (PL-30), repaired by hand via the audit script; FU-3: the audit script already covers `attachment_markups` and `attachment_markup_events` (closed, corrected 2026-11-04). Decided by Claude under the reviewer's delegation (2026-11-04).
