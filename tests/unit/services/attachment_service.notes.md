# Execution notes — `app/services/attachment_service.py`

> Cases: `tests/unit/services/attachment_service.cases.md` (revision 4) · Tests: `tests/unit/services/test_attachment_service.py` · Source commit: e48a092
> Result: 110 of 110 cases implemented · 69 passed · 41 xfailed (all strict, as designed) · 0 errors · 0 open discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_attachment_service.py -q -p no:cacheprovider`
> Coverage: `COVERAGE_FILE=<scratch>/.coverage .venv/Scripts/python.exe -m pytest tests/unit/services/test_attachment_service.py -q -p no:cacheprovider --cov=app.services.attachment_service --cov-branch --cov-report=term-missing`

## How the tests are built
One test per card, in card order, `# [claude] <ID>` above each, `# Then N` before the checks of Then line N (for a `raises:` line, before the `with pytest.raises(...)` that wraps the When).
- **Settings (autouse `cl_settings`):** the six Conventions values set with `monkeypatch.setattr` on `app.core.config.settings`, `app.managers.attachment_manager.settings` and `app.services.attachment_service.settings` (one object; set through each name as the card says). `setting(monkeypatch, NAME, value)` = a Given line "settings: NAME value".
- **Cloudinary (autouse `cl`):** `patch("app.managers.attachment_manager.<name>", autospec=True)` for `generate_upload_signature` (gus → `"sig-x"`), `get_resource` (gr → `dict(RES)`), `destroy_resource` (dr → `{"result": "ok"}`), `build_signed_delivery_url` (bsu → BSU); plus fixed uuid (`…attachment_manager.uuid.uuid4` → `UUID(TOKEN)`) and fixed time (`…attachment_manager.time.time` → `1767225600.9`). Nothing else is patched. `kw(m)` binds `call_args` to the autospec signature; `cl_untouched(cl)` = the four `.called` flags compared with `UNTOUCHED`.
- **Standing rows (`S`):** W0, W1, W2, U1 "Ana Rahman", U2 "Bilal Khan", UG "Mia Khan", members (MG = UG ground-team), F0 / F1 / F9.
- **Given builders:** `mach`, `item`, `proj` (`private`, `deleted`), `pmem`, `comp`, `ticket`, `att` (`ready`, `failed`, `pdf`, `gone`, `where="W0"/"W2"`, other columns as keywords = "but"), `link`, `fill` (returns the list; `format`/`version` set for "ready"), `REQ`. `member(db, U, role, ws)`.
- **Commit point:** `commit_point(db)` = `db.commit()` after the last Given line; snapshots (`snap`, `counts`) taken there; `pending_x` / `pending_edit` after it. `committed:` lines start with one `db.rollback()`. Ids are copied to locals before calls that roll back where later reads need them.
- **Checks:** `reread`, `snap` (every mapped column), `counts` (five tables, all workspaces), `ledger_of`, `links_of`, `events_of` (the card's raw SQL), `att_rows`, `ids`, `lk`, `x_count`, `spies`, `failing_commit`, `failing_refresh`, `order_log` (dr side effect + wrapped commit), `recorder` (`before_cursor_execute` on `db.connection()`; L-11 records from its Given line 3, i.e. over the commit point and the When), `link_stmts`.
- **Caller:** `call_uid(db, fn, U, **kw)`, `la` / `ga` / `pg` for every pass card of list, get and PDF page; the xfail cards that need the caller write `user_id=S.UG.id` directly.
- L-18 and G-14 write Given line 2 ("No project has id XID(k)") as a precondition `assert db.get(Project, XID(k)) is None` before the commit point.

## Fails-today check
`--runxfail` with scratch plugin `thenmap_att.py` (failing test-file line → its `# Then N`). All 36 strict bug cards fail on the Then line their card names, with the value the card describes:
- Then 1, `DID NOT RAISE AttachmentNotFoundError`: S-09 … S-13, CF-18, CF-19, L-12 … L-18, D-06, D-12, D-13.
- Then 1, `TypeError … unexpected keyword argument 'user_id'`: L-20 … L-22, G-11 … G-14, PG-08 … PG-10.
- CF-06 Then 3 and CF-08 Then 2: `'pending' == 'failed'`. CF-09 Then 1: `AttachmentConfirmError: Cloudinary verification failed: lookup` (no commit attempted). CF-15 Then 1: `AttachmentConfirmError: … not set` (wrapped). CF-21 Then 4: `x_count == 0` (X discarded).
- L-08 Then 2: `slot_count` 2. L-11 Then 2: `7 <= 3` (one links query per item, 7 statements, as the card says).
- D-09 Then 3: `dr.called` True. D-10 Then 3: `order == ["dr", "commit"]` (`1 < 0`).
- Discrepancy markers: CF-17 fails at Then 2 (`'pending' == 'ready'`), L-10 at Then 3 (`F9 in IdentitySet([])`).

## Reference run
`ref_attsvc.py` (scratch, `-p ref_attsvc`, PYTHONPATH = scratch folder) replaces in memory, before collection: manager `create_pending_attachment` (PR-1 / PR-2 first: BUG-2090, BUG-1870, BUG-1950), `confirm_attachment` (PR-3 with the caller first, BUG-2091; `CloudinaryNotConfiguredError` passes through untouched, BUG-2096; no inner `session.refresh`), `delete_attachment` (get_active first, BUG-2097; PR-3, BUG-2091; no Cloudinary call, BUG-2202), `get_pdf_page_image` (required `user_id`, visibility before the page check); link DAO count without failed uploads (BUG-1434); service `confirm_upload` (commit the session on `AttachmentConfirmError`, then raise; a failing commit there rolls back and raises the commit's error — BUG-2095, R3a), `list_attachments` (required `user_id`, record check PR-1 / PR-2 — BUG-2200, BUG-1870, BUG-1950 — and one links query for the page, BUG-2201), `get_attachment` / `get_pdf_page_image` (required `user_id`, BUG-2091), `delete_attachment` (commit, then delete the Cloudinary file of a ready attachment, BUG-2202).
- With `--runxfail`: **98 passed, 1 failed** — the one is L-10 (DISCREPANCY-2), which no implementation can pass. CF-17 passes under the reference because its manager confirm no longer calls `session.refresh` itself.
- Without `--runxfail`: 36 strict bug cards XPASS (strict → failed) and CF-17 XPASS (strict → failed); L-10 stays xfailed.

## Discrepancies
None open. Both below were card-mechanism errors, closed by cases revision 3 (2026-11-05); kept for the record.

| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
| DISCREPANCY-1 (closed by cases revision 3) | ATSV-CF-17 | pass | fails Then 2 (revision 2) | "boom" is raised, but A1 re-reads `pending`, no ledger row | Card mechanism: "failing refresh" patches `db.refresh` on the session, and `AttachmentManager.confirm_attachment` itself calls `session.refresh(attachment)` (manager line 756) before the service's commit. The failure happens before the commit, so TC5 ("after the commit") is never reached; the rollback is correct. The card needs a refresh that fails only after the commit (e.g. a side effect that fails from the second call on). Back to the case designer. |
| DISCREPANCY-2 (closed by cases revision 3) | ATSV-L-10 | pass | fails Then 3 (revision 2) | `F9 in db.dirty` → `IdentitySet([])`; Then 1, 2 hold (DataError; no commit, no rollback) | Card mechanism: "in a savepoint" = `db.begin_nested()`, which flushes the session before the SAVEPOINT, so the pending edit is written and F9 is no longer dirty. The service is not involved. Then 3 cannot hold with a savepoint; it needs dropping or another check (e.g. F9's name still "Factory Edited" in the transaction). Back to the case designer. |

## Coverage gaps
None — 100% branch coverage (64 statements, 4 branches).

## Factories added
None.

## Notes for maintainers
- When a bug is fixed its cards XPASS: remove the marker. BUG-2090 / 1870 / 1950 (sign) and BUG-2091, BUG-2096, BUG-2097 live in `app/managers/attachment_manager.py`; BUG-1434 in `app/dao/attachment_link.py`; BUG-2095, BUG-2200, BUG-2201 in this service; BUG-2202 spans manager and service.
- Once `user_id` exists on list / get / PDF page, the `la` / `ga` / `pg` pass cards start passing it through `call_uid` automatically.
- BUG-2202's fix must keep calling `destroy_resource` as looked up on `app.managers.attachment_manager` (the patch target), or D-02 / D-10 lose sight of it.
- Fixed uuid patches `uuid.uuid4` globally for the test (as the card says); every PID1 carries W1.id, so concurrent runs do not collide.

## Revision history
- **Revision 2 (2026-11-05)** — first execution, at cases revision 2 (99 cards incl. CF-21). 3 plain runs: 61 passed / 38 xfailed each; `--runxfail` 38 failed, each on its card's Then line; reference 98 / 99 under `--runxfail`; ruff check and format clean; LF.
- **Revision 3 (2026-11-05)** — cases revision 3 closes DISCREPANCY-1 / -2; no card added or removed.
  - ATSV-CF-17: new helper `failing_refresh_after_commit(db)` (Conventions "failing refresh after commit": `db.commit` wrapped as `cm`, `db.refresh` side effect `late` raises `RuntimeError("boom")` only once `cm.called`, otherwise calls the real refresh, so the manager's own refresh before the commit runs). Marker `XD1` removed; the test passes (boom; A1 committed `ready`; one `ready` ledger row).
  - ATSV-L-10: Then 3 is now `reread(db, Factory, F9.id).name == "Factory Edited"` (the savepoint flushed the edit, nothing rolled it back); new Then 4 runs `db.rollback()` and re-reads `"Factory Nine"` (not committed). Marker `XD2` removed; the test passes.
  - Fails-today and Reference sections above describe revision 2; at revision 3 the discrepancy lines no longer apply.
  - Checks: 3 plain runs 63 passed / 36 xfailed each; `--runxfail` 36 failed (the strict bug cards, unchanged), 63 passed; reference plugin `ref_attsvc.py` with `--runxfail` **99 passed** (unchanged plugin; CF-17 no longer depends on it dropping the manager's refresh); branch coverage 100%; ruff check and format clean; LF.
- **Revision 4 (2026-11-05)** — cases revision 4 (verifier findings 1–6; spec `confirm_upload` R3b, `delete_attachment` R4a): 110 cards, 69 pass / 41 strict xfail. No existing test changed except PG-01 (new Then 4); none retired.
  - New tests: CF-22 (R3b: no-`public_id` refusal rolls back, X discarded, nothing written; pass), L-25 (deleted work order, xfail BUG-2200), L-26 (unknown purchase order, xfail BUG-2200), L-27 (default `skip`; pass), PG-12 (TC6 on an error; pass), D-15 / D-16 (pending / failed file deleted after the commit, xfail BUG-2099), D-17 (no `public_id` → no Cloudinary call; pass), D-18 (delete error swallowed, delete saved; pass), D-19 (WARNING naming `pid-1`, xfail BUG-2100), D-20 (delete still runs when the re-read after the commit fails; pass — today the manager deletes before the commit, so the call has happened either way).
  - PG-01 Then 4: `kw(bsu)["transformation"]` with the default width 1600.
  - Helpers added: `wo(db, S, number, deleted=False)` (Conventions `wo("N")`: WorkOrderType "Repair" then the work order), `warnings_on(caplog)` / `warned(caplog, p)` (Conventions "warnings" / "warned(p)"); markers `X2099`, `X2100`; imports `logging`, `WorkOrder`, `WorkOrderType`. Module docstring now names revision 4.
  - `--runxfail` (scratch `thenmap_att.py` + `cmp_then.py`): 41 failed, every one on its card's named Then line (0 mismatches); new ones: L-25 / L-26 Then 1 `DID NOT RAISE AttachmentNotFoundError`, D-15 / D-16 Then 3 `dr.call_count` 0, D-19 Then 2 `warned(...) is False`.
  - Reference plugin `ref_attsvc.py` extended: the service's delete reads `public_id` / resource / delivery type before the commit, then right after the commit (before the re-read) deletes the file in every state when `public_id` is set (BUG-2099, BUG-2202 / R4a), and logs a WARNING `Cloudinary delete of <public_id> failed: <error>` and swallows the error (BUG-2100); the no-`public_id` refusal of confirm is marked a plain refusal and rolled back instead of committed (R3b). With `--runxfail`: **110 passed**. (No FOR UPDATE read exists in this module's cards or spec.)
  - Checks: 3 plain runs 69 passed / 41 xfailed each; branch coverage 100% (64 statements, 4 branches); ruff check and format clean; LF (0 CR bytes).
