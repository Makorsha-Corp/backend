# Execution notes — `app/managers/attachment_manager.py`

> Cases: `tests/unit/managers/attachment_manager.cases.md` (revision 4) · Tests: `tests/unit/managers/test_attachment_manager.py` · Source commit: e48a092
> Result: 213 passed · 130 xfailed (128 strict, 2 non-strict) · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_attachment_manager.py -q -p no:cacheprovider`
> Coverage: `COVERAGE_FILE=<scratch>/.coverage .venv/Scripts/python.exe -m pytest tests/unit/managers/test_attachment_manager.py -q -p no:cacheprovider --cov=app.managers.attachment_manager --cov-branch --cov-report=term-missing`

## How the tests are built
- **Fixed values.** `AM`, `MISSING`, `T0`, `NOW`, `TOKEN`, `BIG`, `RES`, `XID(k)` exactly as Conventions / shared conventions.
- **Settings (every test).** Autouse `cl_settings` monkeypatches `app.managers.attachment_manager.settings` (the shared settings object, so the real Cloudinary client sees the same values). A Given "settings: NAME value" is `setting(monkeypatch, NAME, value)`.
- **Externals (every test).** Autouse `cl` patches `get_resource` (gr, returns a copy of RES), `destroy_resource` (dr), `generate_upload_signature` (gus, "sig-x"), `build_signed_delivery_url` (bsu, side effect `echo`) with `patch.object(app.managers.attachment_manager, ...)`; nothing else from Cloudinary is patched and nothing reaches the network. "real gus" / "real bsu" = `real(cl, "gus")`, which stops that one patcher (SR-05, DU-11, PU-11 sign locally). `fixed_uuid` / `fixed_time` patch `app.managers.attachment_manager.uuid.uuid4` / `.time.time`. The dao clock (`app.dao.attachment.utcnow`) is patched only in D-05.
- **cl_untouched** = `called(cl) == UNTOUCHED` (`.called` of gr, dr, bsu, gus all False) on one Then line.
- **Standing rows.** Fixture `S`: W0, W1, W2 (make_workspace, that order), U1 / U2 / UG / UA (UA `is_platform_admin=True`, no membership), memberships U1 ground-team, U2 owner, UG ground-team, factories F0 / F1 / F9.
- **Given rows.** `member`, `removed` (status "inactive", `left_at T0`), `set_owner`, `parent(kind, label, where=, deleted=, **but)` (real status / account / work-order-type rows of the same workspace, built once per workspace and test), `mach`, `item`, `proj(private=, deleted=)`, `comp`, `pmem`, `ticket`, `att(pid, ready=, pdf=, gone=, **but)`, `link(A, type, P|int, **but)`, `fill`, `REQ`, `NORM`, `ET`. Every builder flushes. `create(db, S, R, user, pid="dev/new-1", folder="Dev/F")` is the When of the C cards (it calls NORM(R) and `create_pending_attachment`).
- **Named checks.** `snap` (after the last Given) / `now_of` (expire, re-read) for unchanged(X); `reread`; `ledger_of`, `links_of`, `events_of` (per parent type, the nine activity tables); `counts` = the three attachment tables plus the nine activity tables (nothing written); `session_state(db) == CLEAN` taken right after the call; `recorder` (context manager, the When only); `stored_utc`; `warnings` fixture + `warning_records`.
- **Caller (PR-5).** `call_uid(fn, *args, user_id=, **kw)` adds `user_id=` only when `inspect.signature(fn)` has it; `pg(db, U, **kw)` uses it for the PDF-page pass cards. Refusal PG cards pass `user_id=` directly (TypeError today, strict xfail).
- **Parametrized cards** (identical setup and assertions, one input differs; every card keeps its own param id): DU-03…08, CF-02…04, D-02/03, D-10/11 (xfail BUG-2098), D-14/15 (xfail BUG-2099).
- **Generated refusals.** The 101 PR-1 / PR-2 / PR-3 refusal cards (C-21…42, C-50…54, C-61…70, PG-21…43, CF-61…79/89/91…96/98/99, D-41…52/57…60/62/63) were generated from a table of their Given lines by the executor's script (`<scratch>/gen.py`); each is a plain test with its own Given, `# Then N` comments and assertions.
- **Gap 9 (closed in Revision 3, spec G10).** The tests follow PR-5: the role comes from `workspace_members` (C-34, C-53, C-54, C-65…68, CF-77, CF-92…94, PG-37/38, D-57/58).
- **Link order (Revision 3).** LG-03, TR-01, CF-08, CF-24, D-06 check the link as a set / pair membership; order is checked only by LG-08 / TR-07 (non-strict BUG-1433: heap order usually returns the first-built link first, but it is not guaranteed) and the strict SQL alarm LG-09 (`recorder` on the When; every SELECT on `attachment_links` must carry ORDER BY).

### Verification beyond the plain runs
- **3 plain runs**: 213 passed · 130 xfailed each time (the 2 non-strict BUG-1433 cards xfailed in every run).
- **`--runxfail`** (executor's plugin `failson.py` maps the failing line of the test function to its `# Then N` comment): all 130 xfail cards fail. 127 fail inside the Then line their card names; CP-03, D-41 and D-47 fail at the When call directly above `# Then 1`, which is what their cards' Then 1 "Fails today" line describes ("the call raises AttachmentLimitError" / "the call raises IntegrityError").
- **Reference plugin** `<scratch>/ref_atcm.py` (in-process; replaces `AttachmentManager.create_pending_attachment`, `get_pdf_page_image` (required `user_id`), `confirm_attachment`, `delete_attachment`, `derive_urls`, the `note` field of `AttachmentSignRequest`, and `AttachmentLinkDAO.get_links_for_attachment` (ORDER BY id, BUG-1433) / `count_linked_attachments_for_entity` (failed uploads excluded, BUG-1434); since Revision 4 also the BUG-2103 grant (the workspace's `owner_user_id` opens every ticket). Its visibility check runs before any validation and before confirm's ready return (G12); a platform admin gets no project grant, so private projects and their components refuse it): `-p ref_atcm --runxfail` → **343 passed**, so every line after each failure point runs and holds.

## Discrepancies
None open. DISCREPANCY-1…6 of revision 2 are closed by cases Revision 3 (see Revision history).

## Coverage gaps
None — 100% branch coverage (269 statements, 104 branches).

## Factories added
None (all builders are local to the test file, as agreed for the three attachment modules).

## New bugs
None. Every failure is an existing bug (BUG-1433, BUG-1434, BUG-1870, BUG-1950, BUG-2090…2102). IDs BUG-2150…2159 were not needed.

## Notes for maintainers
- When BUG-1433 is fixed in the link DAO, LG-09 XPASSes (strict → fail): remove its marker and those of LG-08 / TR-07 (non-strict). When BUG-1434 is fixed, CP-03 XPASSes: remove its marker.
- When BUG-2091 adds `user_id` to `get_pdf_page_image`, the 18 PG refusal tests stop failing with TypeError; `pg()` / `call_uid` then pass `user_id` to the pass cards automatically.
- `delete_attachment` of an attachment linked to a missing purchase order raises IntegrityError today (FK on the event table); the service turns that into 500. BUG-2091's fix (PR-3 refusal before any write) removes it.
- The reference plugin is a usable sketch of the intended code (PR-1/2/3 helper `_parent_ok` / `_links_ok`, PR-5 `_role`), see `<scratch>/ref_atcm.py`.
- Sales order numbers are unique across all workspaces: concurrent test runs that build "SO-12" wait for each other's rollback (no failure).

## Useful for the coming permissions / notifications / payment features
- **PR-5 caller role**: the role is the caller's `workspace_members.role` in *this* workspace only when `status == "active"`; suspended, removed (`inactive`) and other-workspace memberships give no role; roles are compared exactly ("Owner", "ground-team-manage" are not privileged). Platform admin = `profiles.is_platform_admin` and opens help tickets only (not private projects). A caller with no membership is not refused by the manager (the API gate decides); `can_access_project` / `can_access_ticket` still judge private projects / tickets.
- **Permissions**: `scratch` uploads are open to every member (Q14) and `public_id` is in every response (Q16); confirm and delete are open to any member who can open the record (R11, R8) — all listed for the permissions feature.
- **Notifications**: "Attached …" / "Removed …" go to the parent's activity table through each manager's `log_event` (items, tickets and scratch have none); after BUG-2093 / BUG-2098 they become one-to-one with real ready / removed transitions, which is what a notification hook should listen to.
- **Payments / storage**: failed uploads still hold a place (BUG-1434) and keep their Cloudinary file until deleted (BUG-2099); the service rolls back the `failed` record (BUG-2095, HR-13) — relevant to any per-plan storage quota.
- **Reusable test patterns**: `call_uid` for parameters added by a fix; `echo`-as-JSON for patched URL builders whose result passes a pydantic `str` field; the `failson.py` plugin (failing line → `# Then N`) and a per-module reference plugin.

## Revision history
- **2026-11-04 — Revision 2** (first execution): 322 cases → 203 passed · 119 xfailed (113 designed + 6 DISCREPANCY xfails); DISCREPANCY-1…6 recorded.
- **2026-11-04 — Revision 3** (cases updated from these notes): 325 cases → 208 passed · 117 xfailed (115 strict, 2 non-strict).
  - LG-03, TR-01, CF-08, CF-24, D-06: DISCREPANCY-4 markers removed; Then lines rewritten to the cards' set / pair membership checks (CF-08 gains Then 7, CF-24 Then 4, D-06 Then 4). Closes DISCREPANCY-4.
  - New LG-08, TR-07 (xfail BUG-1433 non-strict) and LG-09 (xfail BUG-1433 strict, ORDER BY alarm).
  - CP-03: marker is now `xfail BUG-1434` (strict). Closes DISCREPANCY-5.
  - D-41, D-47: no code change; the cards' Fails-today line now names the IntegrityError. Closes DISCREPANCY-6.
  - echo-as-JSON-string, attribute access on the sign response and `fill` numbering across calls are now card wording; no code change. Closes DISCREPANCY-1…3.
  - Gap 9 closed in the spec (G10); nothing to change in the tests.
  - Reference plugin already carried the BUG-1433 / BUG-1434 link-DAO fixes; re-run → 325 passed.
- **2026-11-04 — Revision 4** (verifier findings 1–5, spec G11 / G12 / BUG-2103): 343 cases → 213 passed · 130 xfailed (128 strict, 2 non-strict); no existing card changed, 18 tests added, none removed.
  - Platform admin (`S.UA`, `is_platform_admin`, no membership) refused a private project and its component: C-71, C-72 (xfail BUG-1870), PG-44, PG-45, CF-100, CF-101, D-64, D-65 (xfail BUG-2091).
  - Workspace owner with a plain role on another member's ticket (`member(UX, "ground-team")` + `set_owner(W1, UX)`): C-73, PG-46, CF-102, D-66 — pass today (nothing is checked yet); under the reference plugin they pass only because of the BUG-2103 owner grant.
  - Hidden attachment refused before validation / before the ready return (G12): PG-47 (page 0), PG-48 (pending), CF-103 / CF-104 (ready; Then 3 checks the 404 leaks no file name, public_id or "http"), CF-105 (no public_id; today raises AttachmentConfirmError inside the Then 1 `pytest.raises`).
  - PU-15: PDF identified by MIME type alone (`format "jpg"`), pass.
  - `--runxfail`: every new xfail fails on Then 1 with the error its card names (DID NOT RAISE, TypeError on `user_id`, AttachmentConfirmError, D-64/65 `result is None`).
  - Reference plugin: added the BUG-2103 grant; 343 passed. Coverage 100%, ruff clean, LF.
