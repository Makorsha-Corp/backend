# Execution notes — `app/services/machine_service.py`

> Cases: `tests/unit/services/machine_service.cases.md` (revision 2) · Tests: `tests/unit/services/test_machine_service.py` · Source commit: e48a092
> Result: 113 of 113 cases implemented · 74 passed · 39 xfail as designed (37 strict, all xfailed; 2 non-strict: L-13 xfailed, L-21 XPASSed, in every run) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_machine_service.py -q -p no:cacheprovider` (about 5 s)

## How the tests are built
Same form as `machine_item_service.notes.md` / `department_service.notes.md`.
- **Standing rows:** chained fixtures in Conventions order: `w1`, `w2`, `u1`, `u2`, `f1`, `f2`, `fd`, `f9`, `s1`, `s2`, `sx`, `wt1`, `i1` (autouse `standing_rows`). Factories, sections, WT1 and I1 have `created_by` U1; FD and SX have `is_deleted True` only, as Conventions state.
- **Given rows:** `mk_machine(recipe=None, **but)` holds the recipes M1 … MZ (`mk_machine("M1", model_number="L-200")`; "machine, but name X" = `mk_machine(name="X")`); `bulk(n, p)` (one `insert(Machine)`, returns the names); `mk_link(machine, section)` (then `db.expire_all()`); `mk_status(machine, at, status)`; `mk_event(machine, at, **but)`; `mk_order(machine, given_name, status, planned_date, **but)`; `mk_stock(machine, qty)`; `extra()` after the commit point; `commit_point(db)` = `db.commit()`. MCS-W-07's WT9 is built inline with `_add`.
- **Reading helpers:** `reread(db, row)` (any model), `snap(db, row)` for unchanged(X) (taken right after the commit point, compared after the Then), `count_rows(db, Model, **filters)`, `written(db)` (the five tables of Conventions), `events_of`, `names`, `ids`, `usable`.
- **sql_log** (`sql_logging(db)` context manager around the When): a `before_cursor_execute` listener on `db.connection()`. Two placement choices, both so that only the call's own statements are counted:
  - it starts **after** the commit point (Conventions put "sql_log started" as the last Given line, before the commit point): under the `db` fixture `db.commit()` emits `RELEASE SAVEPOINT`, and `db.connection()` opens the next savepoint before the listener is attached;
  - the call's arguments are evaluated before the log starts (`w1_id = w1.id` …): the commit expired every Given row, and reading `w1.id` inside the log would add a `SELECT … FROM workspaces` (MCS-RS-01 failed that way in the first run). In MCS-R-04 the map's row X is `db.refresh`ed before the log, because a map from `get_latest_status_map` holds loaded rows; an expired X would reload from `machine_activity_events` inside the call.
- **Patches:** the failing commit / refresh wraps (C-06, C-07), the shaping patch (C-08), the manager patch (D-04, values written inline as Conventions give them), the race simulation (C-12). Nothing else.
- `AppValidationError` = `app.core.exceptions.ValidationError`; `PydanticValidationError` = `pydantic.ValidationError`.

## Spec gap and named assumptions
- Spec gap 1 (MCS-A-13: the service's shaping adds no statement beyond `list_events`): holds. In the reference run (performers read in one query) the call makes exactly 3 statements, so the bound of 3 stands.
- `MachineEventResponse.id` exists (`app/schemas/machine_event.py`); the manager sets it to the activity row's id (E-01 Then 4 checks that).

## Fails-today check
`--runxfail`, failing line mapped to its `# Then N` by a scratch plugin (`thenmap.py`), value read:
- Then 1 `DID NOT RAISE`: C-10, C-12, C-13, G-04, G-07, U-08, U-12, D-07, E-06 (`HTTPException`); C-14 (pydantic `ValidationError`); D-05 (`AppValidationError`).
- When (the card's "Then 1 (the call raises …)"): G-05, G-08, L-10, L-20 `TypeError … unexpected keyword argument 'include_deleted'`; L-12 `AttributeError … 'astext'`; U-09 `IntegrityError machines_updated_by_fkey`; U-14 `HTTPException 400 Cannot assign a machine to a deleted factory section`. G-06: the `TypeError` inside Then 1's wrap. U-10: Then 1, `IntegrityError machines_factory_id_fkey`. D-04: Then 1, the `ValueError` escapes unchanged.
- Then 1 values: C-15 `100 == 101`; L-14 `['Alpha', 'Zenith']`; L-15 Alpha returned; L-16 `['Alpha', 'Kiln']`; L-17 `[]`; L-18 `[]`; L-19 `['Alpha', 'Zenith']`; W-12 `[M9.id, M1.id]`; W-13 `[MF.id, M1.id]`.
- Then 2: C-09 `'  Big  PRESS '`; C-11 `' L-200 '`; U-11 `'L-200' is None`; E-05 `0 >= 1` (no `FOR UPDATE`); A-13 `7 <= 3`. Then 3: U-13 `1 == 0`; U-15 the order keeps F1.
- Non-strict: L-13 (BUG-887) Then 1 `['bolt', 'Bolt']` in every run; L-21 (BUG-1090) passes in every run (physical order happens to give the later OFF row).

## Reference run
`refplug.py` (scratch, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2x\machine\`) patches in the intended behaviour of each BUG the cards name and nothing else:
- schemas: `MachineCreate` / `MachineUpdate` trim `name` (blank refused), `model_number`, `manufacturer` (at most 200) — BUG-950, 967, 972;
- manager: name check over every live machine of the factory, case-insensitive after trimming (951, 952); an emulated partial unique index after the flush (953); deleted factory refused on create, edit, delete, status change (963, 964, 965, 974); `get_machine(include_deleted)` hiding deleted machines and machines of deleted factories (955, 966); `search_machines` rebuilt (886 latest status, 887 ties by id, 888 escaped search, 889 deleted section, 890 deleted factory, 892 trimmed search, 957 filters with `include_deleted`, 958 no 10 000 cap, 973 no date horizon); edit rebuilt (954 move into a taken name, 959 no stamp without a change, 961 id 0 → 404, 962 explicit null clears, 970 move clears the section, 971 an unchanged section link is not re-validated, 975 open orders follow); delete raising `ValueError("Machine has stock or open orders", blockers)` (968); status change reading the machine `FOR UPDATE` first (960);
- activity manager: performers in one query (1141); latest status per machine with ties to the higher id (1090);
- machine work service: only the workspace's machines of live factories (1571, 1572);
- service: `include_deleted` on `get_machine` / `get_machines`; `delete_machine` translating the manager's `ValueError` into `AppValidationError` after the rollback (968).

With `--runxfail` all 112 tests passed. Without it all 37 strict cards XPASSed (strict, so they failed) and both non-strict cards XPASSed.

## Stability
5 plain runs, plus `enable_seqscan=off` and `enable_indexscan=off, enable_bitmapscan=off` (scratch plugin `forceplan.py`, checked with `SHOW`): 73 passed, 38 xfailed, 1 xpassed (L-21) in all 7; no test moved. Ruff passes (file header adds `DTZ001, DTZ011` for the naive T0 … T3 and `date.today()` the Conventions prescribe); no unused test arguments (AST pass); LF.

## Big cards
- MCS-L-18 (`bulk(10001, "B")`): about 0.65 s for the whole test.
- MCS-C-15 (101 service creates): about 0.4 s.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (78 statements, 4 branches) of `app/services/machine_service.py`.

## Factories added
None.

## Notes for maintainers
- MCS-L-20 is designed `xfail BUG-956, BUG-957` (revision 2) and fails today on BUG-956's `TypeError` in the When call; its reason names both.
- L-21 (BUG-1090) XPASSes today because Postgres returns the two tied rows in insertion order; it is non-strict by design. L-13 (BUG-887) fails today because the collation sorts `bolt` before `Bolt`.
- When BUG-955 / 956 / 966 add `include_deleted`, G-05, G-06, G-08, L-10, L-20 start failing on their checks instead of the `TypeError`.
- D-04 checks the service's half of BUG-968 with a patched manager; D-05 needs the manager's half too.
- Dates come from `date.today()` read in the test (Conventions: the clock is not patched); a run across midnight can move W- and L-07/L-18/L-19 by a day.

## Revision 2 (2026-11-04)
Cases revision 2 (spec R1a for `get_machine_activity`; verifier Findings 1–3). Only these tests changed:
- **MCS-L-20** (changed) — marker reason now lists `BUG-956: Machine list \`include_deleted\` flag is not reachable from the API; BUG-957: …` in the card's Expect order; docstring Rules gain BUG-956. Strict, xfailed. `--runxfail` fails at the When call (line 1379) with `TypeError: MachineService.get_machines() got an unexpected keyword argument 'include_deleted'` — the card's "Fails today on: Then 1 (the call raises TypeError: BUG-956)".
- **MCS-L-23** (changed) — renamed to the card's new title; new Then 4 `not any("work_orders" in s for s in sql_log)` (default `maintenance_window="all"`). Passes.
- **MCS-A-14** (new) — 100 events at `T0 + k min` (k = 1 … 100), then O at T0 flushed last; default call returns 100, O absent, oldest returned is `T0 + 1 min`. Passes.

Counts: 113 tests · 74 passed · 38 xfailed · 1 xpassed (L-21, non-strict, as before) · 0 errors · 0 discrepancies. Branch coverage `app.services.machine_service` 100% (78 stmts, 4 branches), alone and in the joint run with item and waitlist. 3 runs identical (74 / 38 / 1). Ruff clean; LF endings.
