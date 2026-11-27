# Execution notes — `app/dao/base.py`

> Cases: `tests/unit/dao/base.cases.md` (revision 5) · Tests: `tests/unit/dao/test_base.py` · Source commit: e48a092
> Result: 62 passed · 3 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_base.py -q -p no:cacheprovider --cov=app.dao.base --cov-branch --cov-report=term-missing`

## How the tests are built
- **Conventions → helpers** (top of the test file, each commented with its convention):
  - DAOs → module-level `dao = BaseDAO(Department)`, `wdao = BaseDAO(Workspace)`.
  - W1/W2/W3 → fixtures `w1`, `w2`, `w3` (`make_workspace`); P1 → `p1` (`make_profile`).
  - `D "Sales" (W1)` / `(deleted)` → `mk(db, ws, name, deleted=False, **cols)`, one insert + flush each (ids ascend in insertion order). `k own rows` → `own_rows(db, ws, k)` (`"R001"`…).
  - MISSING / MISSING_PROFILE → `missing(db)` / `missing_profile(db)` (raw `max(id) + 1000`). W404 in GW-08 is computed inline the same way.
  - `N0` → fixture `n0`: raw `SELECT count(*) FROM departments`. It is listed **first** in each test's arguments so it runs before any workspace/row setup (workspaces don't add departments anyway).
  - Re-read → `reread(db, id)`: `db.expire_all()` then raw `SELECT * FROM departments WHERE id = :i` (mapping, or `None` = "no row"). `raw_row()` is the same SELECT without expiring, used for the "before rollback" checks.
  - Counts → `count_all`, `count_ws`, `count_named` (raw SQL).
  - Ad-hoc schemas `DeptIn`, `DeptPatch`, `CreatorIn`, `DeptNested` and the test-local mapped class `NoIdThing` (own `DeclarativeBase`, never created) are defined exactly as in Conventions.
  - "Not committed" → `commit_spy(db)` = `patch.object(db, "commit", wraps=db.commit)`; `sp = db.begin_nested()` before the call, `spy.assert_not_called()`, `sp.rollback()`, then re-read.
  - Error cases (IntegrityError / DataError / TypeError) → `with pytest.raises(X), db.begin_nested():` — the savepoint is rolled back by the context manager when the error propagates; re-read afterwards. BASE-C-09 uses an explicit `sp = db.begin_nested()` because it must inspect `db.new` **before** the rollback.
  - Planner settings (GM-04, GW-05) → `force_seqscan(db)` (three `SET LOCAL … = off`), run after the setup, right before the calls. `heap_disorder()` inserts A "Zeta", B "Alpha", C "Mid", then renames A to "Zulu" with a flushed UPDATE.
  - SQL statement counter (GW-13) → `StatementCounter(engine)`, a `before_cursor_execute` listener on the session-scoped `engine` fixture, attached only around the call.
  - Temporary tables (R-04, R-05) → **regular** tables `tmp_restrict_child` / `tmp_cascade_child` created by raw SQL inside the test transaction after `SET LOCAL lock_timeout = '10s'`; they vanish on the test rollback. A real `CREATE TEMP TABLE` cannot be used: Postgres refuses FKs from a temporary table to a permanent one ("constraints on temporary tables may reference only temporary tables"). The table is uncommitted and so invisible to other sessions.
- **Mocks:** none (spec: no externals, no race simulations). The commit spy wraps, it does not replace.
- **Warnings:** `remove` tests carry `filterwarnings("ignore::sqlalchemy.exc.LegacyAPIWarning")`.
- **Parametrized:** GM-09/GM-10 and GW-11/GW-12 (same setup, differ only in `skip`/`limit` and message); each case ID is its own `pytest.param` id.
- **xfail honesty:** verified with `--runxfail`: GM-04 and GW-05 fail on (a) with ids `[B, C, A]` (heap order); R-03 raises `UnmappedInstanceError`. Three runs gave identical outcomes (62 passed · 3 xfailed).
- **BASE-G-05 (revision 4+):** adds a `Department` with explicit `id = MISSING` and does not flush; (a) `dao.get` → `None` and `raw_row` → `None` (a raw `text()` SELECT does not autoflush because `autoflush=False`, so it proves `get` did not flush); then `db.flush()`; (b) `dao.get` returns the same object via the identity map, `raw_row` finds it.

## Discrepancies
None. (DISCREPANCY-1 of revision 3 — BASE-G-05 vs. old `get` R5 — was resolved by spec Gap log G6 and the cases revision 4 redesign; its xfail marker is removed.)

## Coverage gaps
None — 100% branch coverage of `app/dao/base.py` (41 statements, 8 branches).

(Coverage output may also list unrelated modules such as `app/utils/item_name_normalize.py`; that comes from other agents' coverage data files in the shared working directory, not from this test file.)

## Factories added
None (batch mode: `tests/unit/factories.py` not edited). Worth promoting later:
- `mk(db, ws, name, deleted=False, **cols)` → a `make_department(db, workspace=…, **overrides)` builder; also used in spirit by the department manager tests.
- `StatementCounter` is now duplicated in `test_item.py` and `test_base.py` → move to a shared test helper (e.g. `tests/unit/helpers.py`).
- `commit_spy(db)` is generic and would fit the same shared helper module.

## Notes for maintainers
- **When BUG-100 is fixed** (`ORDER BY id`): GM-04 and GW-05 will XPASS → remove the markers. They depend on a sequential scan returning heap order (A's updated tuple after C); the `SET LOCAL` planner settings pin that.
- **When BUG-101 is fixed** (`remove` returns `None` for a missing id): R-03 will XPASS → remove the marker.
- BASE-G-05 depends on the session running with `autoflush=False` (harness mirrors `SessionLocal`); if autoflush is ever turned on, (a) will fail and spec `get` R5 must change first.
- R-04 / R-05 take a `SHARE ROW EXCLUSIVE` lock on `departments` for the rest of the test (FK creation). Tests of other agents inserting departments wait at most the duration of those two short tests; `lock_timeout = '10s'` bounds our own wait if another session holds a conflicting lock.
- `get_multi` cases use `N0`-relative assertions; they assume no other session **commits** department rows during the test (all pipeline tests roll back, so none do).

## Revision history
- **Cases revision 4/5 (2026-09-29):** BASE-G-05 redesigned (spec G6): test renamed `test_base_g_05__pending_row_not_found_until_flushed`, now asserts pending → `None` (no flush by `get`), then after `db.flush()` → same object, `name "Unflushed"`, row present. DISCREPANCY-1 xfail removed (verify.md finding 1 closed on the executor side). No other case changed; no IDs added or retired. Result 62 passed · 3 xfailed, 100% branch coverage, 3 identical runs; `--runxfail` still fails exactly GM-04, GW-05, R-03 on the designed assertions.
