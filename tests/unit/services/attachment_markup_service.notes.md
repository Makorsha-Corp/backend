# Execution notes — `app/services/attachment_markup_service.py`

> Cases: `tests/unit/services/attachment_markup_service.cases.md` (revision 2) · Tests: `tests/unit/services/test_attachment_markup_service.py` · Source commit: e48a092
> Result: 39 of 39 cases implemented · 28 passed · 11 xfailed (all strict) · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `COVERAGE_FILE=<private> .venv/Scripts/python.exe -m pytest tests/unit/services/test_attachment_markup_service.py -q -p no:cacheprovider --cov=app.services.attachment_markup_service --cov-branch --cov-report=term-missing`

## How the tests are built
Same form as `test_help_ticket_service.py` and `test_attachment_markup_manager.py`: one test per card, in card order, `# [claude] <ID>` above each, `# Then N` before the checks of Then line N.
- **Settings:** autouse `amsv_settings` (monkeypatch on `app.core.config.settings`, the five Conventions values).
- **Standing rows:** fixture `S` (W0, W1, W2; U1 "Ana Rahman", U2 "Bilal Khan", UG "Mia Khan" with their W1 memberships; F0 / F1 / F9; A1 = att("plan.png") with link(A1, "scratch", 1)), built exactly as in the markup manager tests.
- **Given rows:** local helpers named as in Conventions: `member`, `att` (`ws=` = "W0 att", keywords = the "but" columns), `link`, `proj` (`private=True`), `pmem`, `ticket`, `layer`, `mev`, `older` (revision 2: raw `UPDATE … updated_at = now() - make_interval(hours => h)`, then `expire_all`). One flush per row.
- **Commit point:** `commit_point(db)` = `db.commit()` (releases the fixture's savepoint) and returns the "nothing written" snapshot `counts(db)` (rows of `attachment_markups`, `attachment_markup_events`, all workspaces). `pending_x` adds Factory X after it and returns `X_ID`; `x_gone` / `x_kept` count it with raw SQL.
- **Checks:** `session: clean` = three `not db.new / dirty / deleted` asserts right after the call. `committed:` lines run `db.rollback()` once, then `layers_of` / `events_of` / `reread_layer` (expire_all + fresh SELECT). Ids of rows re-read after a rollback (L in PL-02, DL-04, DL-05) are copied at the commit point.
- **Patches (only those the Conventions name):** `spies` (commit / rollback wrap the real methods), `failing_commit` (commit raises `RuntimeError("boom")`, rollback spied), PL-05's order log (commit / refresh wrapped as the card writes them), PL-10's race simulation `patch("app.dao.attachment_markup.AttachmentMarkupDAO.get_for_user", return_value=None)`. Nothing external is patched; no Cloudinary call is reachable here (no network).
- **recorder** (LL-11, LV-06): `event.listen(db.connection(), "before_cursor_execute", …)`, removed right after the When; `profile_reads` counts statements starting with `SELECT` that contain `FROM profiles`. The recorder starts after the commit point, and the ids used in the When are read into locals before it starts: the commit expires the standing rows, so evaluating `S.U1.id` inside the call would add one profile SELECT that is not the service's (seen in a first run: 11 instead of 10). The recorded window is exactly the When; the card's bound (`<= 2`) is unchanged.

## Fails-today check
`--runxfail` with scratch `thenmap_mk.py` (maps the failing test-file line to its `# Then N`). All 11 fail where their card says:
- LL-07, LL-08, LL-09, LV-05, PL-08, PL-09, DL-05 (BUG-2115): Then 1, `DID NOT RAISE AttachmentNotFoundError`.
- LL-11 (BUG-2119): Then 2, `10 <= 2` (two profile reads per layer). LV-06: Then 2, `5 <= 2` (one per entry).
- PL-11 (BUG-2118): Then 2, one `markup_updated` event instead of none.
- PL-10 (BUG-2120): the When call raises `IntegrityError` (`uq_attachment_markup_user`, 23505), before Then 1's check — this is exactly the card's "Fails today on: Then 1 (the call raises IntegrityError 23505)".

## Reference run
Scratch `ref_amsv.py` (loaded with `-p ref_amsv`, PYTHONPATH = scratch folder; replaces the four public manager methods in-process, never edits `app/`): BUG-2115 (every link's record checked for the caller before the ready / markable checks — project via `can_access_project`, ticket via the workspace owner or `can_access_ticket` with the active W1 role — refusal = `Attachment <id> not found.`), BUG-2118 (equal payload → no event), BUG-2119 (authors read with one `IN` query), BUG-2120 (insert in a savepoint; `IntegrityError` → update the existing row, `markup_updated`). With `--runxfail`: **34 passed**. Without it the 11 strict cards XPASS (strict → failed).

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (40 statements; the service has no branches of its own).

## Factories added
None.

## New bugs
None (range BUG-2222 … BUG-2229 unused).

## Notes for maintainers
- When BUG-2115 is fixed (manager `_get_ready_attachment` gains `user_id`), the seven BUG-2115 cards XPASS → remove `@X2115`. LL-10 and DL-06 (project member allowed) keep passing.
- When BUG-2120 is fixed, PL-10 XPASSes; it runs without a test savepoint as its card says, so the fix must catch the unique violation inside the manager (a savepoint) or the service's rollback will discard the earlier rows.
- LL-11 / LV-06 count statements on the session's connection; keep the recorder window around the When only.
- PL-05 depends on the manager refreshing the row before the service commits and the service not refreshing after; `updated_at` equality holds because `now()` is constant inside the test transaction.
- For the future notes: markup events (`markup_saved` / `markup_updated` / `markup_cleared`, with `session_id`) are committed here, so a notification hook belongs after this service's commit (BUG-2118 first, or no-op saves would notify). The permission side is BUG-2115 (shared PR-3 parent-record check). Nothing touches money.

## Revision history
- **Revision 1 (2026-11-05)** — first execution: 34 cases, 23 passed / 11 xfailed; `--runxfail` all 11 on their named Then; reference 34 passed.
- **Revision 2 (2026-11-05)** — cases revision 2 (verifier findings 1, 2). Added LV-07, PL-12, DL-07 (pending attachment → `AttachmentValidationError` UNAV, session clean, pending X discarded; PL-12 / DL-07 also nothing written, DL-07 layer kept) and LL-12, LV-08 (distinct times: layers oldest `updated_at` first `[U2, U1, UG]`, history newest first `[E3, E1, E2]`); all pass. New helper `older`. No existing test changed; module docstring now says revision 2. Checks: 3 plain runs 28 passed / 11 xfailed each; `--runxfail` 11 failed, each on its card's named Then (PL-10 at the When with `IntegrityError` 23505, as its card says), 28 passed; reference plugin `ref_amsv.py` unchanged, `--runxfail` **39 passed** (no Cloudinary delete or `FOR UPDATE` read exists on this module's paths; the plugin's refusals are raised in the manager and rolled back by the service); branch coverage 100%; ruff check and format clean; LF.
