# Execution notes — `app/services/ledger_service.py`

> Cases: `tests/unit/services/ledger_service.cases.md` (revision 3, 2026-11-22) · Tests: `tests/unit/services/test_ledger_service.py` · Source commit: e48a092
> Result: 82 passed · 24 xfailed · 0 discrepancies · 0 errors — branch coverage 99% (76 statements, 12 branches; 1 line missed, dead code)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_ledger_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.ledger_service --cov-branch --cov-report=term-missing`

## How the tests are built
- **Actors.** Fixture `s` (a `SimpleNamespace`) builds every Conventions row in each test: U1, U2, U3, U9 profiles; W0, W1, W2 in that order (`W1.owner_user_id = U1.id`); `workspace_members` rows U1 owner, U2 and U3 ground-team (W1), U9 ground-team (W2); items I1 "Bolt", I2 "Nut", I0, I9; factories F1, F2, F0, F9; machines M1, M2 (F1), M0, M9; attachments A1, A2, A0, A9; projects PA (workspace), PP (`invited_only`), PD (deleted, `deleted_at T(1)`, `deleted_by U1`) with components C1, C2, CP, CD, plus C0 (W0 project) and C9 (W2 project). Card names are attributes (`s.M1`, `s.PD`).
- **Given rows.** `mentry`, `ientry`, `pentry`, `aentry`, `msnap`, `isnap` take the card's "but" columns as keywords and flush. "Other NOT NULL columns any valid value": `source_type "manual"` (machine / project ledger), `unit_cost 10.00, qty_before 0, qty_after 1` (project ledger). Named rows RE1/RE2, G0…G9 and L0…L9 are small functions. `T(d)` is naive (the machine, inventory and project ledgers have naive `performed_at`); `TA(d)` is the same wall clock in aware UTC for the attachment ledger (`DateTime(timezone=True)`), also for the dates passed to `get_attachment_ledger`. `TM(d, k)` = `datetime(2025, 6, d) + timedelta(minutes=k)` for the 101-row cards.
- **Commit point.** Every test calls `commit_point(db)` (`db.commit()`, releases the fixture savepoint) after its last Given row, also when the card has no "(after the commit point)" line, so the rollback cards (RMI-10/12, RINV-12/14) keep the Given rows. Extra X / pending Q / edit E(r) are made after it. `committed:` blocks start with one `db.rollback()`, then fresh `select(...)` counts / `db.get` after `expire_all()`.
- **Patches** (only those Conventions name): commit / rollback spies (`wraps=`), the failing commit, the patched manager (`patch.object(svc.ledger_manager, ...)`) and "writes then raises" (the real manager method wrapped, `ERR = RuntimeError("after write")` raised after it wrote and flushed). The project access check is the real one; nothing is patched for projects.
- **Recorder** = `before_cursor_execute` on `db.connection()`. "The <table> SELECT" = recorded SELECTs whose `FROM` names the table (`\bFROM\s+<table>\b(?!_)`, so `inventory` never matches `inventory_ledger`); the helper asserts at least one was recorded and the test checks every one. ORDER BY is compared after collapsing whitespace / case and stripping table qualifiers.
- **xfails whose "Fails today on" says "the call raises …"** (RMI-14 TypeError, GIB-06 / RINV-16 AttributeError `value_after`, IMS-04 TypeError `skip`, TBU-01/02 AttributeError `get_by_performer`): the exception leaves at the When call, before the `# Then 1` block; the card's named exception type was confirmed under `--runxfail`. Every other strict xfail fails inside its card's named Then line under `--runxfail` (checked line by line: GML-10 T2, GML-11 T1, GMB-02 T2, GMB-04 T2, GMB-08 T2, RMI-09 T2, RMI-13 T2, PCL-10 T1 "DID NOT RAISE", PCT-07 T1, GIB-02 T2, GIB-05 T2, RINV-05 T2, RINV-11 T2, RINV-15 T2, RINV-17 T1, RINV-18 T2, IMS-02 T2, IMS-03 T2).
- **Reference check.** An in-process plugin (scratch, not in the repo) that implements the approved spec — combined filters and `performed_at DESC, id DESC` ordering, `FOR UPDATE OF machine_items` / `OF inventory`, BUG-649/650/652/653/655 fixes, deleted-project 404, Decimal `total_value`, the price-only message, `skip`/`limit` on the item movement report, a working user report — makes all 104 tests pass with `--runxfail`. 3 plain runs: identical (80 passed, 24 xfailed).

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 361 | dead | `LedgerService.get_transactions_by_order` body — spec Not specified (Q2: dead code, on the dead-code removal checklist). |

## Factories added
None (all builders are local; the ledger builders mirror `tests/unit/managers/test_ledger_manager.py`).

## Notes for maintainers
- When a BUG is fixed its strict xfails XPASS → remove the marker: BUG-640 (GML-10), BUG-341 (GML-11, IMS-02), BUG-3043 (GMB-02, GMB-04, GIB-02, GIB-05), BUG-641 (GMB-08), BUG-649 (RMI-09, RINV-11), BUG-643 (RMI-13), BUG-650 (RMI-14), BUG-1278 / BUG-1954 (PCL-10, PCT-07), BUG-655 (GIB-06, RINV-16), BUG-3042 (RINV-05), BUG-644 (RINV-15), BUG-653 + BUG-3042 (RINV-17 needs both), BUG-652 (RINV-18), BUG-646 (IMS-03), BUG-648 (IMS-04), BUG-645 (TBU-01, TBU-02).
- Once BUG-649 is fixed, RMI-08 / RINV-10 still pass (they only check `ledger_qty`, `adjustment_created` and one message); RMI-05 keeps the error path (ledger 15, no snapshot).
- Once BUG-3043 is fixed, the pass cards comparing `total_value == Decimal(...)` keep passing; LSV-PCT-01/02 assert `float` on purpose (projects deferred).
- RINV-03 Then 6 counts **all** `machine_activity_events` rows (the card says "rows: exactly 0"). It relies on the shared test database holding no committed events; if another suite ever commits some, this check fails for a reason outside this module.
- The lock checks (RMI-13, RINV-15) depend on the eager `items` join staying in the snapshot query: with it, the intended SQL ends `… LIMIT … FOR UPDATE OF machine_items`.
- New-bug block BUG-2978, BUG-2979: unused (no new bug found).

## Revision history
- 2026-11-22 — cases rev 3 (verifier findings 1–3): GIB-01 and GIB-04 gain Then 4 `type(result["inventory_type"]) is str` (GIB-01's old Then 4–5 renumbered 5–6). New TBU-04: the manager is patched and its one call is bound with `inspect.signature` to a stub of the card's signature `(session, user_id, workspace_id, start_date, end_date, skip, limit)` without defaults, so an argument the service stops passing fails the bind instead of taking the manager's default. New PCL-11 (allowed read: no commit, no rollback, pending Q in `db.new`, only P1 dirty). Result: 3 runs 82 passed / 24 xfailed, 99% branch (gap unchanged, dead code); `--runxfail` 24/24 on the named Then line; reference plugin + `--runxfail` 106 passed; ruff clean, LF.
