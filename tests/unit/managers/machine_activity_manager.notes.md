# Execution notes — `app/managers/machine_activity_manager.py`

> Cases: `tests/unit/managers/machine_activity_manager.cases.md` (revision 1) · Tests: `tests/unit/managers/test_machine_activity_manager.py` · Source commit: e48a092
> Result: 156 passed · 14 expected-to-fail (12 strict xfailed; 2 non-strict, XPASS on the default plan) · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_activity_manager.py -q -p no:cacheprovider`

## How the tests are built
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept; `scratchpad\macx\`), so values are the card's own text. The fixtures and helpers were written by hand. An AST pass checked: each ID exactly once and in card order, `# Then 1..N` matches the card's Then count in order, marker and bug match the Expect line, no unused argument, no fixture used without being an argument.

- **Standing rows:** one fixture each, each depending on the one before, so rows are inserted in Conventions order. The autouse `standing_rows` requests `m9`, the end of the chain, in every test that uses `db`, so all of them exist there as Conventions say. Pure cards (no `db`) build none: `format_field_value`, `collect_field_changes` except CF-18, the unsaved `status_from_activity` cards.
- **Given rows:** `mk_event`, `mk_status`, `mk_log`, flushing as Conventions say. A row name no later line reads is built without a variable (ruff F841).
- **Snapshots:** `snap` reads the table with a Core `select` and never expires. An `expire_all` before the When would make the When's own `M1.id` a logged statement, and every `sql_log` count would be off. `reread_snap` is the "after re-read" side.
- **`sql_log`:** `sql_recorder`, a listener on `db.connection()`, wraps the When alone. Snapshots come before it, as Conventions say.
- **Refusals:** `with pytest.raises(...)`, adding `with db.begin_nested():` for `IntegrityError`, `DataError`, `StatementError` and any "in a savepoint" line. MAC-LE-18 and LE-19 have no savepoint, as the cases' design note asks.
- **Rolled back (MAC-LE-32):** `sp = db.begin_nested()`, then `patch.object(db, "commit", wraps=db.commit)` around the call. Nothing else is patched in the file.
- **File-level ruff:** `SIM117`, `DTZ001` as the Conventions prescribe, and `FURB157`, since MAC-FV-11 and CF-07 need `Decimal("100")` as written.
- **Clock:** no tick. The only real-clock pair is MAC-LE-03, which checks two ids and a count, no order. Every card that checks an order gives `created_at`.

## Where each xfail fails
Read with `--runxfail --tb=short`, default plan.

| Card | Then | Failing value |
|---|---|---|
| MAC-LE-18, LE-19 | 1 | `DID NOT RAISE HTTPException` |
| MAC-LE-20, LE-21 | 1 | `IntegrityError` on `machine_activity_events_machine_id_fkey` |
| MAC-LE-22 | 1 | `IntegrityError` on `machine_activity_events_workspace_id_fkey` |
| MAC-LI-44 | 3 | `assert 7 <= 3` |
| MAC-LI-45 | 3 | `assert 6 <= 3` |
| MAC-GS-12, GS-13, GS-14, GS-15 | 1 | `DID NOT RAISE HTTPException` |
| MAC-SM-14 | 3 | `'ORDER BY' in <the statement>` is false |

The 7 and 6 reads the spec's formula gives are what the run shows; only `<= 3` binds. The setup of none of them fails.

**Proof that the non-strict cards can fail on Then 3.** Scratch plugin `scratchpad\macx\macx_wrong.py` (`-p macx_wrong`) appends `ORDER BY machine_activity_events.id DESC` to the map's statement in a `before_cursor_execute` rewrite: legal for a query that asks for no order, independent of plan and heap. It rewrote all 16 of the file's map statements. With `--runxfail`, 14 failed, 156 passed: the 12 above, plus MAC-SM-12 and SM-13 at Then 3, `assert <lower id> == <higher id>`. MAC-SM-11 passed.

**Proof of the lines past each failure point.** Scratch plugin `scratchpad\macx\macx_ref.py` (`-p macx_ref`, nothing in `app/`) replaces in-process `log_event` (machine check, then the original), `get_latest_status` (404), `list_events` (performers in one read) and the DAO's `get_latest_status_map` (the same query plus `.order_by(created_at, id)`). With `--runxfail`: **170 passed**. With the markers on: the 12 strict cards are `XPASS(strict)` failures, the red run they exist for, and SM-12, SM-13 XPASS.

## Discrepancies
None. Every card ended as designed; every `Fails today on` line is right. No new defect, so no new BUG number.

## Coverage gaps
None — 100% branch coverage (59 statements, 18 branches), with a private `COVERAGE_FILE`.

## Factories added
None.

## Stability
| Run | Result | MAC-SM-12 | MAC-SM-13 |
|---|---|---|---|
| Default, 5 runs and the coverage run | 156 passed, 12 xfailed, 2 XPASS | XPASS | XPASS |
| `PGOPTIONS="-c enable_seqscan=off"` | 156 passed, 12 xfailed, 2 XPASS | XPASS | XPASS |
| `… enable_seqscan=off, enable_hashjoin=off, enable_nestloop=off` | 156 passed, 12 xfailed, 2 XPASS | XPASS | XPASS |
| `… enable_hashjoin=off` | 156 passed, 12 xfailed, 2 XPASS | XPASS | XPASS |
| `… enable_indexscan=off, enable_bitmapscan=off, enable_indexonlyscan=off` | 156 passed, 13 xfailed, 1 XPASS | xfailed, Then 3 (revision 0: 4 runs) | XPASS |
| The line above + `enable_hashjoin=off, enable_mergejoin=off` | 156 passed, 13 xfailed, 1 XPASS | xfailed | XPASS |

`PGOPTIONS` reaches the connection (`SHOW enable_seqscan` → `off`). No pass card and no strict xfail changed outcome. `ruff check` on the file: all checks passed. Line endings: LF. Runtime about 6 s.

## Revision history
- **Finding M1 of `machine_activity_manager.verify.md` (executor):** the first delivery built only the rows a test named, against "In every test" in Conventions: 108 of 119 database tests had fewer rows, and 5 cards (LI-21, LI-22, LI-23, GS-12, GS-13) had no machine at all. The notes described the chain without saying so. Added the autouse `standing_rows`. A diff shows that fixture and its header comment only; no test changed, and no outcome moved.
- **Revision 1 of the cases (finding M2):** added MAC-LE-33 and MAC-GS-21, both `pass`, after the last card of their sections. A diff shows additions only. Scratch plugin `scratchpad\macx\macx_inactive.py` (the reference, plus a refusal of an inactive, live machine on both methods; nothing in `app/`) fails exactly these 2 with `--runxfail`: 2 failed, 168 passed.
- All checks re-run after both changes: 5 default runs, `--runxfail`, both plugins, 5 forced plans, ruff, coverage.

## Notes for maintainers
- Never read an SM-12 or SM-13 XPASS as BUG-1090 being gone: they follow the plan and the heap. The proof is MAC-SM-14 and the explicit wrong order above.
- When BUG-1090 is fixed with an `ORDER BY`, SM-14 XPASSES and turns the run red: remove the three markers. A fix with no `ORDER BY` leaves SM-14 xfailing and no alarm sounds, so that card is rewritten with the fix (cases file, Spec gap 2).
- BUG-1091, BUG-1140, BUG-1141: each fix turns its cards `XPASS(strict)`; remove those markers.
- `macx_wrong` rewrites below the connection listener order, so `sql_log` still holds the unrewritten text. It has no effect on MAC-SM-14, which fails at Then 3 either way. A check of `ORDER BY` needs a query-level change, as `macx_ref` does.
- "Nothing written" counts committed rows of all workspaces too. A run beside something that commits to this table could break it; nothing did here.
