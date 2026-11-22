# Execution notes — `app/managers/project_component_activity_manager.py`

> Cases: `tests/unit/managers/project_component_activity_manager.cases.md` (revision 0) · Tests: `tests/unit/managers/test_project_component_activity_manager.py` · Source commit: e48a092
> Result: 45 passed · 7 xfailed (all strict) · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_project_component_activity_manager.py -q -p no:cacheprovider`

## How the tests are built
Normal mode, no local model. Every test sits below a `# [claude] <ID>` comment, in card order. Style follows `test_machine_activity_manager.py`. A scratch check (`makorsh-pipeline\mgr5e\check.py`, not kept in the repo) confirmed: each of the 52 IDs exactly once and in card order, `# Then 1..N` matches each card's Then count, and the xfail marker matches each Expect line. `ruff --select ARG` reports no unused test argument; its hits are the fixture chain and the listener signature only.

- **Standing rows:** one fixture each, each depending on the one before, so the rows go in Conventions order: W1, W2, U1, U2, F1, F9, PJ1, PJD, PJ9, CP8, CP1, CP2, CPD, CP9. That gives `CP8.id < CP1.id < CP2.id < CPD.id < CP9.id`. The autouse `standing_rows` requests `cp9`, the end of the chain, so every test has all of them. PJD: `is_deleted=True`, `deleted_at=T3`, `deleted_by=U1.id`, `is_active` not passed (Spec gap 2).
- **Given rows:** `mk_event` (the "event" convention, add and flush one at a time) and `mk_log` (one `add_all`, one flush). If no later line reads a row, it is built without a variable (ruff F841).
- **Snapshots:** `snap` reads the row with a Core `select` and never expires, so the When's own attribute reads issue no SQL inside `sql_log`. `reread_snap` is the "after re-read" side (expire, then select). `event_count` is "nothing written" and `count_events` is "count:". With `autoflush=False`, neither flushes a pending row (PCAM-LI-27).
- **`sql_log`:** `sql_recorder`, a `before_cursor_execute` listener on `db.connection()`, wraps only the When. Snapshots are taken before it. For PCAM-LI-05 and LI-06, the `pytest.raises` sits inside the recorder.
- **Refusals:** a plain `pytest.raises(HTTPException)` for the foreign component cards (LE-13, LE-14) and all `list_events` 404 cards. LE-15, LE-16 and LE-17 ("in a savepoint") add `with db.begin_nested():`, as do every `IntegrityError`, `DataError` and `StatementError` card.
- **Rolled back (PCAM-LE-25):** `sp = db.begin_nested()`, then `patch.object(db, "commit", wraps=db.commit)` around the call. Nothing else is patched.
- **File-level ruff noqa:** `SIM117` and `DTZ001`, since Conventions prescribe the nested `with` and naive datetimes.
- `ProjectComponentActivityManager` (the class) is not imported, because no card uses it and ruff F401 would flag it. `M` is the singleton.

## Where each xfail fails
Read with `--runxfail --tb=line`:

| Card | Then | Failing value |
|---|---|---|
| PCAM-LE-13, LE-14 | 1 | `DID NOT RAISE HTTPException` |
| PCAM-LE-15 | 1 | `IntegrityError` on `project_component_activity_events_project_component_id_fkey` (id 999999999) |
| PCAM-LE-16 | 1 | `IntegrityError` on `project_component_activity_events_project_component_id_fkey` (id 0) |
| PCAM-LE-17 | 1 | `IntegrityError` on `project_component_activity_events_workspace_id_fkey` |
| PCAM-LI-25 | 3 | `assert 7 <= 3` |
| PCAM-LI-26 | 3 | `assert 6 <= 3` |

Each failure matches the card's "Fails today on" line, including the 7 and 6 reads. No setup fails.

**Proof of the lines past each failure point.** The scratch plugin `makorsh-pipeline\mgr5e\pcam_ref.py` (`-p pcam_ref` with that folder on `PYTHONPATH`, nothing in `app/`) changes the class in-process only:
- `log_event` runs `component_dao.get_by_id_and_workspace` first, raises the 404 on a miss, then calls the original. This is the BUG-1192 fix.
- `list_events` reads every performer of the page in one `SELECT … WHERE profiles.id IN (…)`. This is the BUG-1712 fix.

Results with the plugin:
- With `--runxfail`: **52 passed**, so every Then line after the failure point runs and holds.
- With the markers on: the 7 strict cards end as `XPASS(strict)` failures (7 failed, 45 passed). That is the red run they exist for.

## Discrepancies
None. Every card ended as designed, and every "Fails today on" line is right. I found no new defect, so BUG-1720…1729 are unused.

## Coverage gaps
None: 100% branch coverage (23 statements, 2 branches), measured with a private `COVERAGE_FILE` (`makorsh-pipeline\mgr5e\.coverage`).

## Factories added
None.

## Stability
- 3 plain runs plus the coverage run: 45 passed, 7 xfailed each time. Runtime is about 3.5 s.
- `ruff check` on the file: all checks passed.
- Line endings: LF (no CR in the file).

## Notes for maintainers
- **BUG-1192 fixed:** PCAM-LE-13 to LE-17 XPASS(strict); remove their markers. LE-15 to LE-17 keep the savepoint the card asks for. After the fix they raise `HTTPException` before any write.
- **BUG-1712 fixed:** PCAM-LI-25 and LI-26 XPASS(strict); remove their markers. LI-24 and LI-16 (one instance per person) guard the fix.
- `len(sql_log) == 1` in LI-05 and LI-06 depends on `snap`/`event_count` being taken before the recorder and on no `expire_all` before the When. An expired `cp8`/`cp9` would add a refresh SELECT inside the call's argument evaluation.
- "Nothing written" counts committed rows of all workspaces too. A parallel run that commits to this table could break it; none did here.
