# Execution notes — `app/services/mobile_upload_service.py`

> Cases: `tests/unit/services/mobile_upload_service.cases.md` (revision 3) · Tests: `tests/unit/services/test_mobile_upload_service.py` · Source commit: e48a092
> Result: 72 of 72 cases implemented · 49 passed · 23 xfailed (all strict) · 0 discrepancies · 0 errors — branch coverage 97% (only the not-unit-testable line 156)
> Run: `COVERAGE_FILE=<private> .venv/Scripts/python.exe -m pytest tests/unit/services/test_mobile_upload_service.py -q -p no:cacheprovider --cov=app.services.mobile_upload_service --cov-branch --cov-report=term-missing`

## How the tests are built
Same form as `test_mobile_upload_session_manager.py` and `test_help_ticket_service.py`: one test per card, in card order, `# [claude] <ID>` above each, `# Then N` before the checks of Then line N (for a `raises:` line, before the `with pytest.raises(...)` line).
- **Externals** (autouse fixture `CL`, Conventions "Settings and time" and "Cloudinary"): `settings` via `monkeypatch.setattr`; `utcnow` of `app.managers.mobile_upload_session_manager` and of `app.dao.mobile_upload_session` → NOW; `uuid.uuid4` (through the manager module, so AttachmentManager's ids get TOKEN too), `time.time`, `secrets.token_urlsafe` through the manager module. The ten Cloudinary functions are patched with `autospec=True` exactly at the targets the Conventions name (six on the mobile manager module, four on `app.managers.attachment_manager`); nothing touches the network. `CL.setting(name, value)` is a Given "settings:" line. `kw(m)` binds a mock's call to the real signature.
- **Standing rows** = fixture `R` (`SET LOCAL TIME ZONE 'UTC'` first, then W0, W1, W2, U1, U2, UG, the three W1 memberships (`R.MG` = UG's), F0, F1, F9, P1 "Tender").
- **Given rows**: `sess(db, R, kind, where, **but)` builds sess / staged / uploaded (W0 / W2 sess via `where`); `proj`, `pmem`, `ticket`, `member`, `full` as in the Conventions; each row flushed on its own.
- **Commit point**: `commit_point(db)` = `db.commit()` (releases a savepoint under the `db` fixture). Snapshots (`snap`, `counts`) and ids are taken right after it; `pending_x` / the F9 pending edit are added after it.
- **Checks**: `unchanged(db, Model, before)` (expire_all + get, every column), `counts` ("nothing written", five tables), `x_count` (x_gone = 0, x_kept = 1), `reread`, `att_by_pid`, `ledger_types`, `count`. "committed:" lines run one test-level `db.rollback()` before the first of them. `session: clean` is three asserts on `db.new`, `db.dirty`, `db.deleted`, always before any re-read.
- **Context managers**: `spies(db)` (wrapping `commit` / `rollback`), `failing_commit(db)` (always inside `pytest.raises(RuntimeError)`, written as one `with` with the raises outermost), `order_log(db, CL)` (dr's `side_effect` and a commit wrapper append to one list), `event_log(db, CL)` (revision 3: a `before_cursor_execute` listener on `db.connection()` appends `("sql", statement)`; dr, rr, um, agr get a `side_effect` that appends `("cl", name)` and returns the canned value; removed on exit) with `first_read(ev)` and `acted_before(ev, i)`; `warned(caplog, p)` for the Conventions' **warnings** (`caplog.set_level(logging.WARNING)` before the When).
- **DB error (C-03)**: the unknown user fails at the FK on flush; no test savepoint, since the card checks the service's own rollback and then `SELECT 1`.
- No helpers like `call_uid` are named by these cards; none used.

## Fails-today check
`--runxfail` with scratch plugin `thenmap_mob.py` (maps the last failing test-file line to its `# Then N`). All 19 fail on the Then line their card names, with the value described:
- C-05 … C-09, PM-15 … PM-17: Then 1, `DID NOT RAISE AttachmentNotFoundError`.
- CN-06, PM-14 (revision 3, event log): Then 2, the first `mobile_upload_sessions` SELECT has no `FOR UPDATE`.
- CN-08, PS-04: Then 3, `dr.called` is True. CN-09, PS-05: Then 3, `order == ["dr", "commit"]` (`1 < 0`).
- PM-09: Then 2, the session's `public_id` is STG again, not DEST. PM-10: Then 1, `AttachmentConfirmError: Cloudinary verification failed: lookup` escapes `pytest.raises(RuntimeError)`.
- PC-03: Then 2, `public_id` is still STG. PC-04: Then 1, `AttachmentConfirmError` (TOO(10485761)) escapes `pytest.raises(RuntimeError)`. PC-09: Then 4, X count 0 (rolled back).

## Reference run
`refplug_mob.py` (scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attsvce\mob\`, loaded with `-p`, PYTHONPATH = that folder; nothing under `app/` touched) replaces five `MobileUploadService` methods in memory with the spec's intended behaviour:
- `create_session` checks the record first (PR-1: exists, same workspace, not deleted; PR-2: an `invited_only` project needs creator, project member or W1 owner; a ticket needs creator or a W1 owner / ground-team-manager role) — BUG-2130, BUG-2131;
- `cancel_session` / `promote_session` read the session with `with_for_update()` — BUG-2139; promote re-checks the record before the move — BUG-2134;
- `cancel_session` / `public_sign` collect the manager's `destroy_resource` calls and replay them through the (patched) module function only after the commit succeeded — BUG-2205;
- `promote_session` commits, then re-raises, an `AttachmentConfirmError` raised after the move (session `public_id` changed) — BUG-2204;
- `public_confirm` commits, then re-raises, an `AttachmentConfirmError` that left the session cleared (`public_id` None) — BUG-2137.

With `--runxfail`: **66 passed**; test-file line coverage 100% (1046/1046), so every check past each failure point runs and holds (today 63 lines of the test file are never reached). Without `--runxfail`: all 19 strict cards XPASS (strict → failed), 47 passed.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 156 (branch 155→156) | unreachable | `public_sign`: the session's workspace is missing → `MobileUploadSessionNotFoundError`. The spec's Not specified marks it not unit-testable: `workspace_id` is a NOT NULL FK with `ON DELETE CASCADE`, reachable only by patching the workspace DAO (not an external). |

## Factories added
None.

## Notes for maintainers
- When a bug is fixed its cards XPASS: remove the marker. BUG-2130 / BUG-2131 / BUG-2134 / BUG-2139 live mostly in `app/managers/mobile_upload_session_manager.py` (+ the service passing `for_update=True`); BUG-2137, BUG-2204, BUG-2205 in this service (BUG-2205's fix spans the manager).
- BUG-2205's fix must keep calling `destroy_resource` through `app.managers.mobile_upload_session_manager` (spec gap 3), or CN-01, CN-09, PS-02, PS-05 will miss the call.
- The tokens here (RAW1, RAW0, RAW2) are fixed: `mobile_upload_sessions.token_hash` is unique, so a parallel run of another file inserting the same hash in an open transaction would wait on it. The manager tests use different (shorter) tokens.
- PM-01 / PM-03 rely on `uuid.uuid4` being patched through the manager module: that is the `uuid` module object, so AttachmentManager's `build_public_id` gets TOKEN too (DEST).
- Checks run: 3 plain runs, 47 passed / 19 xfailed each; `ruff check` and `ruff format --check` clean; LF only.

## Revision history
- **Revision 3 (2026-11-05)** — cases revision 3 (verifier findings 1–5; spec `cancel_session` R3a, `public_sign` R3a). 72 cases: 49 passed, 23 xfailed (all strict), 0 discrepancies, 0 errors.
  - Reworked: CN-06 and PM-14 now use the event log (Then 2 `FOR UPDATE` on the first session read; new Then 3 `acted_before(first_read) is False`); `recorder` / `locked` removed, `event_log`, `first_read`, `acted_before` added. C-07, PM-04, PS-07 add a pending X after the commit point and check `x_gone` (new last Then line).
  - New: CN-10, PS-10 (pass: a raising `dr` after the commit is swallowed; change saved and answered), CN-11, PS-11 (strict xfail BUG-2136, new marker `XF2136`; `caplog`, `warned`), PM-19 (strict xfail BUG-2204: the HR-13 commit keeps pending X), PS-09 (strict xfail BUG-2205: re-sign with a failing commit never calls `dr`). Import added: `logging`.
  - `--runxfail` (`thenmap_mob.py`): all 23 fail on their card's named Then line — new ones: CN-11 Then 2 and PS-11 Then 2 (`warned` False), PM-19 Then 4 (`0 == 1`, X discarded), PS-09 Then 4 (`dr.called` True), CN-06 / PM-14 Then 2 (no `FOR UPDATE`); C-07 still Then 1 (DID NOT RAISE).
  - Reference plugin `refplug_mob.py` extended: the deferred Cloudinary delete runs right after the commit, before any re-read, and a delete error is logged as a WARNING naming the file (BUG-2136) and swallowed; the locked read stays the first statement of cancel / promote; refusals roll back. With `--runxfail`: **72 passed**; without it the 23 strict cards XPASS (strict → failed).
  - 3 plain runs: 49 passed / 23 xfailed each. Branch coverage 97% (line 156 only, unchanged: `unreachable`). Ruff check and format clean; LF.
