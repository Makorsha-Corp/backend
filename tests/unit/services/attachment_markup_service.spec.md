# Spec — `app/services/attachment_markup_service.py`

> **Status:** APPROVED (2026-11-04; nothing open. One item, decided by Claude under the reviewer's delegation (2026-11-04).)
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/help_ticket_service.spec.md`. The **Transaction contract TC1–TC6** is defined in `tests/unit/services/base_service.spec.md` and cited here. Below the service: `tests/unit/managers/attachment_markup_manager.spec.md` (APPROVED, verified PASS), whose rules — and, through it, the **Parent-record rule PR-1 … PR-5** of `tests/unit/managers/attachment_manager.spec.md` — are cited, not restated.
>
> **Routed here:** markup manager FU-1 (a) BUG-2115: the service already passes the caller's id (`current_user_id` / `user_id`); the manager reads the role and platform-admin flag itself (PR-5), so nothing more is passed — checked, no rule change here. (b) the two lists commit after a read → D1 (intended). (c) the 204 for a cleared layer is the endpoint's (integration-only).
>
> **Read, not run.** The service is four pass-throughs; every rule was read in the code. Nothing needed a database run.

## Review
> All items decided; nothing pending.

### D1. Reading layers or history commits the session — ✅ intended
**Background:** A read (`get`, `list`) normally neither commits nor rolls back (TC6). `list_layers` and `list_events` here are wrapped like writes: they commit after the read and roll back on an error. The manager writes nothing on these paths.
**What happens today:** The commit has nothing to save; a refusal (404 / 400) rolls back a session that has nothing pending. In a request, nothing else is pending.
**Example:** `GET /attachments/7/markups` answers the same list either way; only a test that left a row pending in the session would see it saved (or discarded on an error).
**Rules affected:** `list_layers` R2, R3; `list_events` R2
**Answer:** intended — harmless (markup manager FU-1 (b)); the rules state today's behavior so a test does not assume TC6.
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-04). No bug.

Checked and **not** violated: **HR-4, HR-6, HR-9, HR-10, HR-16** — the manager's and DAOs' (markup manager spec: BUG-2115 … BUG-2120, BUG-1435 … BUG-1437). **HR-13** — no external call. **HR-1 … HR-3, HR-5, HR-7, HR-8, HR-11, HR-12, HR-14, HR-15** — none applies.

**Permission checks:** none of its own; PR-3 in the manager (BUG-2115).

## Overview
`AttachmentMarkupService` is the transaction boundary for markup layers (each user's drawing over a ready image or PDF) and their history. `app/api/v1/endpoints/attachments.py` calls it for `GET /attachments/{id}/markups`, `GET …/markups/events`, `PUT …/markups/me` and `DELETE …/markups/me`; the endpoints map `AttachmentNotFoundError` → 404, `AttachmentValidationError` (and, on PUT, any `ValueError`) → 400, and a cleared layer → 204. Every method calls one manager method, commits, and on any error rolls back and re-raises.

**Callables:** 4 specified · 2 not specified
**Externals to mock:** none (the markup manager's stamp URL under BUG-2117 uses the local Cloudinary URL builder, no network).
**Integration-only behavior:** the endpoint mapping above; the 204 for a `None` layer; request-body validation of `AttachmentMarkupPutRequest`; the race of BUG-2120 with two committed transactions.

**Facts for the test designer**
- Import: `from app.services.attachment_markup_service import AttachmentMarkupService, attachment_markup_service`; errors `from app.managers.attachment_manager import AttachmentNotFoundError, AttachmentValidationError`. Every parameter after `db` is keyword-only. The manager is the attribute `manager`.
- `AttachmentMarkupListResponse(items: list[AttachmentMarkupLayerResponse])`, `AttachmentMarkupEventListResponse(items: list[AttachmentMarkupEventResponse])`; item shapes, `MarkupPayload`, building a ready attachment and its link: markup manager spec **Facts** and **Notes**.

**Notes for the test designer**
- Transaction mechanics: `base_service.spec.md` Notes. "Committed": a test-level `db.rollback()` then a re-select still finds the layer / event.
- BUG-2115 / BUG-2118 / BUG-2119 / BUG-2120 are the manager's; here one pass-through card each is enough (strict xfail where the manager's is), with the session rolled back on the refusals.

## Not specified
- `AttachmentMarkupService.__init__` — stores the manager singleton, no logic.
- `attachment_markup_service` — module singleton.

---

## `AttachmentMarkupService.list_layers(db, *, workspace_id, attachment_id, current_user_id)`
**Shape:** list
**Persistence:** reads (commits)
**Visibility:** public (used by: `GET /attachments/{id}/markups`)

**Returns:** `AttachmentMarkupListResponse` whose `items` are manager `list_layers` R1–R4 for the caller (BUG-2115, BUG-2116, BUG-2117, BUG-2119, BUG-1435).

**Rules:**
- **R1.** `items` is exactly the manager's list, in its order; `[]` when the attachment has no layers.
- **R2.** ✅ (D1) After the read the session is committed: anything pending in it is saved (TC1 behavior on a read).
- **R3.** ✅ (D1) Any error of the manager (`AttachmentNotFoundError` — missing, deleted, other workspace, hidden record per BUG-2115; `AttachmentValidationError` — not ready / not markable) rolls the session back and reaches the caller unchanged (TC3).

**Errors:** as R3. **Side effects:** a commit; nothing written.

---

## `AttachmentMarkupService.list_events(db, *, workspace_id, attachment_id, current_user_id)`
**Shape:** list
**Persistence:** reads (commits)
**Visibility:** public (used by: `GET /attachments/{id}/markups/events`)

**Returns:** `AttachmentMarkupEventListResponse` whose `items` are manager `list_events` R1–R4 (BUG-2115, BUG-2119, BUG-1436, BUG-1437).

**Rules:**
- **R1.** `items` is exactly the manager's list, in its order; `[]` with no history.
- **R2.** ✅ (D1) Committed after the read; errors roll back and reach the caller unchanged, as `list_layers` R2, R3.

**Errors:** as `list_layers` R3. **Side effects:** a commit; nothing written.

---

## `AttachmentMarkupService.put_own_layer(db, *, workspace_id, attachment_id, user_id, payload, session_id=None)`
**Shape:** create / update
**Persistence:** writes
**Visibility:** public (used by: `PUT /attachments/{id}/markups/me`)

**Returns:** the manager's `AttachmentMarkupLayerResponse` (built by the manager after its write, before the commit), or `None` when the payload is empty (the endpoint answers 204).

**Rules:**
- **R1.** The save is manager `put_own_layer` R1–R7a (create `markup_saved`, replace `markup_updated`, clear `markup_cleared`, no-op on empty without a layer; BUG-2115, BUG-2118, BUG-2120). Every write of it, layer and event, is committed (TC1): both survive a later rollback.
- **R2.** The returned value is the manager's, unchanged; it is not re-read after the commit (its `updated_at` is the one the manager read after its flush).
- **R3.** Any error rolls back every write of the call and reaches the caller unchanged (TC3): no layer change and no event remain. Today this includes BUG-2120's `IntegrityError` on two concurrent first saves (manager R5a). Commit failure: TC4.

**Errors:** `AttachmentNotFoundError`, `AttachmentValidationError`, `IntegrityError` (today, BUG-2120) — unchanged.

**Side effects:** the caller's layer created / replaced / deleted and one event, committed.

---

## `AttachmentMarkupService.delete_own_layer(db, *, workspace_id, attachment_id, user_id, session_id=None)`
**Shape:** delete
**Persistence:** writes
**Visibility:** public (used by: `DELETE /attachments/{id}/markups/me`, 204)

**Returns:** `None`.

**Rules:**
- **R1.** The delete is manager `delete_own_layer` R1–R4 (the caller's layer hard-deleted with one `markup_cleared` event; no layer → nothing; BUG-2115). It is committed (TC1).
- **R2.** Any error rolls back and reaches the caller unchanged (TC3); commit failure TC4.

**Errors:** `AttachmentNotFoundError`, `AttachmentValidationError` — unchanged.

**Side effects:** layer deleted and one event, committed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 34–41 | manager `list_layers`; commit; wrap | `list_layers` R1, R2 |
| 42–44 | any exception → rollback, re-raise | `list_layers` R3 |
| 55–62 | manager `list_events`; commit; wrap | `list_events` R1, R2 |
| 63–65 | any exception → rollback, re-raise | `list_events` R2 |
| 78–87 | manager `put_own_layer`; commit; return layer or `None` | `put_own_layer` R1, R2 |
| 88–90 | any exception → rollback, re-raise | `put_own_layer` R3 |
| 102–109 | manager `delete_own_layer`; commit | `delete_own_layer` R1 |
| 110–112 | any exception → rollback, re-raise | `delete_own_layer` R2 |
| 115 | singleton | Not specified |
