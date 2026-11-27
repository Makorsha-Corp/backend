# Test cases — `app/dao/machine_section_assignment.py`

> **Spec:** `tests/unit/dao/machine_section_assignment.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-10-16); every answer (P1, P2, P3, Q1, Q2 and the house-rule lines BUG-906, BUG-909) was decided by Claude under the reviewer's delegation, so nothing is provisional.
> **Counts:** 77 cases · 69 expected-to-pass · 8 expected-to-fail (bugs) · 9 deferred

## Reviewer summary
- **Per callable:** `get_by_machine` 10 · `get_by_section` 22 (3 bug) · `upsert_for_machine` 25 (1 bug) · `clear_for_section` 12 (2 bug) · inherited `BaseDAO` methods on `MachineSectionAssignment` 8 (2 bug).
- **Expected-to-fail by bug:** BUG-906 4 (MSA-GS-20, GS-21, CL-11 non-strict; GS-22 strict, statement recorder) · BUG-907 1 (MSA-CL-06, strict) · BUG-909 1 (MSA-UP-03, strict) · BUG-100 2 (MSA-INH-06 non-strict; INH-07 strict, statement recorder). BUG-908 has no card here (its fix is in the section manager).
- **Delegated answers and the cards that rest on them:** P2 (raw lookups return rows of deleted machines / sections) — MSA-GM-07 … GM-10, GS-04, GS-05, CL-04, CL-05. Q1 (a machine already loaded is not refreshed) — MSA-UP-21 … UP-24, CL-09, CL-10. Q2 (a move writes a new row, `updated_*` stay empty) — MSA-UP-02, UP-05. P1 / BUG-907 — MSA-CL-06. P3 / BUG-908 — no card.
- **Dead code after BUG-908:** `get_by_section` and `clear_for_section` are on the dead-code list "remove together with the fix of BUG-908". The 34 cards MSA-GS-01 … GS-22 and MSA-CL-01 … CL-12 test them as they behave today and are deleted in that change (with them BUG-906's and BUG-907's xfails).
- **Notable design choices:**
  - No order today (BUG-906, BUG-100): every card except the four non-strict xfails (MSA-GS-20, GS-21, CL-11, INH-06) compares ids as sorted lists, sets, sizes or membership. The strict alarm is one statement-recorder card per unordered query: MSA-GS-22 (`get_by_section`, also the query `clear_for_section` runs — no second recorder) and MSA-INH-07 (`get_by_workspace`).
  - "Re-created" is seen only through `id` and `created_by` (two different profiles: U1 wrote the Given row, U2 calls); `created_at` is never compared — it is the same for every row of a test.
  - BUG-909: MSA-UP-03 (strict xfail, fails on the row id) has the pass companion MSA-UP-04 (one row, same section, same machine — holds before and after the fix).
  - `user_id` "is not used" when clearing (R4) is shown with `user_id=MISSING`, which would fail the flush if it were stored (MSA-UP-06, UP-07).
  - Database errors are wrapped in a savepoint (Conventions); "the previous row is back" is a re-read after that rollback (MSA-UP-15, UP-17, UP-18) — no Claude card needed.
  - BUG-907 can only be seen with 10 001 rows: one bulk card (MSA-CL-06), strict (today always exactly 10 000).
  - Cards marked `Author: claude` (14): bulk setup — MSA-GS-10, GS-11 (501 rows), CL-06 (10 001 rows); non-strict xfail — GS-20, GS-21, CL-11, INH-06; statement recorder — GS-22, INH-07; savepoint rollback and commit spy — UP-20, CL-12; a step after the When (expire, edit of the standing row M1, follow-up flush) — UP-22, UP-24, CL-10.
- **Needs a decision:** None blocking. See Spec gaps 1 (constraint names asserted as "contained in"), 2 (keyword-only parameters: no card), 3 (window partition deferred).


## Conventions for this module

**IDs.** `MSA` = `app/dao/machine_section_assignment.py`. `GM` get_by_machine · `GS` get_by_section · `UP` upsert_for_machine · `CL` clear_for_section · `INH` inherited `BaseDAO` methods on `MachineSectionAssignment`.

**Actors and fixed values.**
- `dao` = the singleton `machine_section_assignment_dao` (`from app.dao.machine_section_assignment import machine_section_assignment_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns.
- W1, W2 = two `workspaces` rows. U1, U2 = two `profiles` rows: U1 is `created_by` of every Given assignment, U2 is the acting user of the calls.
- `MachineSectionAssignment` = `app.models.machine_section_assignment.MachineSectionAssignment`. `MachineSectionAssignmentCreate` = the schema of `app.schemas.machine_section_assignment`. `Machine` = `app.models.machine.Machine`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. A card names, by column name, every column that differs from these defaults.
- These fifteen rows exist in every test, inserted in this order, and need no Given line:
  - F1 = `factories` row: `name "Main Plant"`, `abbreviation "MP"`, `workspace_id W1.id`. F2 = the same, but `name "North Yard"`, `abbreviation "NY"`. F9 = the same, but `name "Far Depot"`, `abbreviation "FR"`, `workspace_id W2.id`.
  - S1 = `factory_sections` row: `name "Cutting"`, `factory_id F1.id`, `workspace_id W1.id`, `is_deleted False`. S2 = the same, but `name "Paint"`. S3 = the same, but `name "Welding"`, `factory_id F2.id`. SX = the same, but `name "Old Line"`, `is_deleted True` (a soft-deleted section of F1). S9 = the same, but `name "Packing"`, `factory_id F9.id`, `workspace_id W2.id`.
  - M1 = `machines` row: `name "Lathe"`, `factory_id F1.id`, `workspace_id W1.id`, `is_active True`, `is_deleted False`, `is_running False`. M2 = the same, but `name "Press"`. M3 = the same, but `name "Drill"`. MD = the same, but `name "Old Saw"`, `is_deleted True` (a soft-deleted machine of W1). M9 = the same, but `name "Grinder"`, `factory_id F9.id`, `workspace_id W2.id`.
  - So `M1.id < M2.id < M3.id < MD.id < M9.id`.
- No `machine_section_assignments` row exists unless the card's Given lists it.
- **assignment of M to S** = `machine_section_assignments` row built with `MachineSectionAssignment`: `workspace_id` = M's `workspace_id`, `machine_id M.id`, `factory_section_id S.id`, `created_by U1.id`, `updated_by None`, `updated_at None`, `created_at` left to the database. After the word "but" the card lists every column that differs.
- A Given line written as code (`a1_id = A1.id`) is a step to run exactly as written, at that place in the order.

**Named checks.**
- **ids(result)** = `[a.id for a in result]` — the list in the order returned (the order is part of the check). `sorted(ids(result)) == [A1.id, A2.id]` is used where the order is not part of the check; the right-hand ids are written in Given order, which is ascending id order. `clear_for_section` returns machine ids (integers): `sorted(result) == [M1.id, M2.id]`.
- **rows_of(M)** = `db.expire_all()`, then SELECT every `machine_section_assignments` row with `machine_id == M.id` (any workspace), as a list.
- **re-read X** = `db.expire_all()`, then SELECT X by id from its own table; the listed values are database values. "the returned row" = re-read by `result.id`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line, before the call). X may be an assignment, a machine, a section or a factory.
- **nothing written** = the numbers of rows in `machine_section_assignments`, `machines`, `factory_sections` and `factories` (all workspaces) equal their values before the call.
- `count:` lines count the rows of the named table in all workspaces, with the filter stated. Assert `created_at` / `updated_at` only as `is None` / `is not None`; never compare `created_at` values.
- `raises: DataError` = `sqlalchemy.exc.DataError`; `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the call for both: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards (the savepoint is rolled back). `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause`, `ForeignKeyViolation`, `UniqueViolation`, `NotNullViolation` = classes of `psycopg2.errors`.
- Further `raises:` lines of the same card are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; the harness adds the marker. Every xfail in this module is strict, except the four cards that rest on physical row order — MSA-GS-20, GS-21, CL-11, INH-06 — marked `(non-strict)` on their Expect line (`pytest.mark.xfail(strict=False, …)`).

**Rolled back** (cards marked Author: claude only). `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**Statement recorder** (cards marked Author: claude only). The SQL statements the session sends during the When are recorded; a `statement:` line is a check on the recorded text.

**Race simulations.** None in this module.


## `DAOMachineSectionAssignment.get_by_machine`

### MSA-GM-01 — returns the assignment row of the machine and writes nothing
- **Rules:** `get_by_machine` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S2.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, MachineSectionAssignment)`.
2. returns: `result.id == A1.id`.
3. returns: `result.factory_section_id == S1.id`.
4. nothing written: nothing written.
5. unchanged: unchanged(A1).

### MSA-GM-02 — a machine without an assignment gives None
- **Rules:** `get_by_machine` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A2 = assignment of M2 to S1. (M1 has no assignment.)

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MSA-GM-03 — an unknown machine id gives None
- **Rules:** `get_by_machine` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `result = dao.get_by_machine(db, machine_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MSA-GM-04 — the machine's row is not returned for another workspace id
- **Rules:** `get_by_machine` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### MSA-GM-05 — the row's own workspace_id decides, not the machine's: asked in the machine's workspace gives None
- **Rules:** `get_by_machine` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1, but `workspace_id W2.id`. (M1 belongs to W1; the row says W2.)

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MSA-GM-06 — the row's own workspace_id decides: asked in the row's workspace returns it
- **Rules:** `get_by_machine` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1, but `workspace_id W2.id`. (M1 belongs to W1; the row says W2.)

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result.id == A1.id`.
2. returns: `result.workspace_id == W2.id`.

### MSA-GM-07 — the row of a soft-deleted machine is returned
- **Rules:** `get_by_machine` R2 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AD = assignment of MD to S1. (MD is the soft-deleted machine.)

**When**
- `result = dao.get_by_machine(db, machine_id=MD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == AD.id`.
2. returns: `result.factory_section_id == S1.id`.

### MSA-GM-08 — a row pointing at a soft-deleted section is returned
- **Rules:** `get_by_machine` R2 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to SX. (SX is the soft-deleted section.)

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A1.id`.
2. returns: `result.factory_section_id == SX.id`.

### MSA-GM-09 — a row pointing at a section of another factory is returned
- **Rules:** `get_by_machine` R2 (P2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S3. (M1 is in F1; S3 belongs to F2.)

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A1.id`.
2. returns: `result.factory_section_id == S3.id`.

### MSA-GM-10 — a row pointing at a section of another workspace is returned
- **Rules:** `get_by_machine` R2 (P2)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S9. (S9 belongs to W2; the row says W1.)

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A1.id`.
2. returns: `result.factory_section_id == S9.id`.
3. returns: `result.workspace_id == W1.id`.


## `DAOMachineSectionAssignment.get_by_section`

### MSA-GS-01 — returns a list of the rows of that section and writes nothing
- **Rules:** `get_by_section` R1, R7, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1.
3. A3 = assignment of M3 to S2. (A row of another section.)

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A1.id, A2.id]`.
3. returns: `len(result) == 2`.
4. returns: `isinstance(result[0], MachineSectionAssignment)`.
5. nothing written: nothing written.
6. unchanged: unchanged(A1).

### MSA-GS-02 — a row of another workspace pointing at the same section is not returned
- **Rules:** `get_by_section` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A9 = assignment of M9 to S1. (M9 belongs to W2, so the row says W2; it points at S1 of W1.)

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### MSA-GS-03 — the other workspace gets only its own row for the same section id
- **Rules:** `get_by_section` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A9 = assignment of M9 to S1. (M9 belongs to W2, so the row says W2; it points at S1 of W1.)

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [A9.id]`.
2. returns: `result[0].machine_id == M9.id`.

### MSA-GS-04 — the row of a soft-deleted machine is returned and left as it was
- **Rules:** `get_by_section` R2 (P2), R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. AD = assignment of MD to S1. (MD is the soft-deleted machine.)

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A1.id, AD.id]`.
2. nothing written: nothing written.
3. unchanged: unchanged(AD).
4. unchanged: unchanged(MD).

### MSA-GS-05 — the rows of a soft-deleted section are returned
- **Rules:** `get_by_section` R2 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to SX. (SX is the soft-deleted section.)
2. A2 = assignment of M2 to SX.

**When**
- `result = dao.get_by_section(db, factory_section_id=SX.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A1.id, A2.id]`.
2. unchanged: unchanged(SX).

### MSA-GS-06 — an unknown section id returns an empty list
- **Rules:** `get_by_section` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MSA-GS-07 — a section with no rows returns an empty list
- **Rules:** `get_by_section` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1. (S2 has no rows.)

**When**
- `result = dao.get_by_section(db, factory_section_id=S2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MSA-GS-08 — a section whose rows are all in another workspace returns an empty list
- **Rules:** `get_by_section` R3, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A9 = assignment of M9 to S9. (A row of W2.)

**When**
- `result = dao.get_by_section(db, factory_section_id=S9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MSA-GS-09 — rows of other sections and other workspaces do not use up a place in the page
- **Rules:** `get_by_section` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = assignment of M1 to S2. (Another section.)
2. O2 = assignment of M9 to S1. (Another workspace, same section id.)
3. A3 = assignment of M2 to S1.
4. A4 = assignment of M3 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `sorted(ids(result)) == [A3.id, A4.id]`.

### MSA-GS-10 — default limit returns exactly 500 of 501 rows
- **Rules:** `get_by_section` R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (501 machines and 501 assignments) outside the Conventions vocabulary

**Given**
1. 501 machines N1 … N501, inserted in that order; machine Nk (k = 1 … 501) is M1 but `name` = `f"Unit {k:03d}"` (so "Unit 001" … "Unit 501").
2. For every Nk: assignment of Nk to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 500`.
2. returns: `len(set(ids(result))) == 500`.
3. returns: `set(ids(result)) <= ` the set of the 501 assignment ids.

### MSA-GS-11 — an explicit limit of 501 returns all 501 rows
- **Rules:** `get_by_section` R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (501 machines and 501 assignments) outside the Conventions vocabulary

**Given**
1. 501 machines N1 … N501, inserted in that order; machine Nk (k = 1 … 501) is M1 but `name` = `f"Unit {k:03d}"` (so "Unit 001" … "Unit 501").
2. For every Nk: assignment of Nk to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, limit=501)`.

**Then**
1. returns: `len(result) == 501`.
2. returns: `sorted(ids(result)) ==` the 501 assignment ids, ascending.

### MSA-GS-12 — limit 2 of three rows returns two different rows of the section
- **Rules:** `get_by_section` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1.
3. A3 = assignment of M3 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `len(set(ids(result))) == 2`.
3. returns: `set(ids(result)) <= {A1.id, A2.id, A3.id}`.

### MSA-GS-13 — the last window is short
- **Rules:** `get_by_section` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1.
3. A3 = assignment of M3 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in [A1.id, A2.id, A3.id]`.

### MSA-GS-14 — limit 0 returns an empty list
- **Rules:** `get_by_section` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MSA-GS-15 — skip equal to the number of rows returns an empty list
- **Rules:** `get_by_section` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MSA-GS-16 — skip one below the number of rows returns one row
- **Rules:** `get_by_section` R5, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in [A1.id, A2.id]`.

### MSA-GS-17 — skip past the number of rows returns an empty list
- **Rules:** `get_by_section` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, skip=5)`.

**Then**
1. returns: `result == []`.

### MSA-GS-18 — negative limit is rejected by the database and nothing changes
- **Rules:** `get_by_section` R5, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(A1).

### MSA-GS-19 — negative skip is rejected by the database and nothing changes
- **Rules:** `get_by_section` R5, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(A1).

### MSA-GS-20 — rows come back by id ascending
- **Rules:** `get_by_section` R6 [BUG-906]
- **Kind:** bug
- **Expect:** xfail BUG-906 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the updated row A1 usually comes back last, giving [A2, A3, A1] — but the physical row order can match the intended order by accident)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-906")`); the assertion is never weakened

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1.
3. A3 = assignment of M3 to S1.
4. A1 is changed after A3 was created: `A1.created_by = U2.id`, then `db.flush()`. (This usually moves A1 physically behind A3 in the table.)

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A1.id, A2.id, A3.id]`.
2. returns: `ids(result) == [A1.id, A2.id, A3.id]`.

### MSA-GS-21 — a middle window holds the second and third row by id
- **Rules:** `get_by_section` R6 [BUG-906], R4
- **Kind:** bug
- **Expect:** xfail BUG-906 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested; the database usually answers [A2, A3, A1], giving the window [A3, A1] — but a page of the physical row order can equal the intended page by accident)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-906")`)

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1.
3. A3 = assignment of M3 to S1.
4. A1 is changed after A3 was created: `A1.created_by = U2.id`, then `db.flush()`.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [A2.id, A3.id]`.

### MSA-GS-22 — the by-section query asks the database for an order
- **Rules:** `get_by_section` R6 [BUG-906]; `clear_for_section` R7 [BUG-906] (same query)
- **Kind:** bug
- **Expect:** xfail BUG-906
- **Fails today on:** Then 2 (the query has no `ORDER BY`)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order)

**Given**
1. A1 = assignment of M1 to S1.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A1.id]`.
2. statement: the one `SELECT` sent has an `ORDER BY`.


## `DAOMachineSectionAssignment.upsert_for_machine`

### MSA-UP-01 — a machine without an assignment gets one new row
- **Rules:** `upsert_for_machine` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. No assignment exists.

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, MachineSectionAssignment)`.
2. returns: `result.id is not None`.
3. re-read the returned row: `workspace_id == W1.id`, `machine_id == M1.id`, `factory_section_id == S1.id`.
4. re-read the returned row: `created_by == U2.id`.
5. re-read the returned row: `created_at is not None`.
6. re-read the returned row: `updated_at is None`, `updated_by is None`.
7. count: rows_of(M1) has exactly 1 row.
8. count: `machine_section_assignments` has exactly 1 row.

### MSA-UP-02 — moving to another section replaces the row with a new one
- **Rules:** `upsert_for_machine` R2 (Q2)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. `a1_id = A1.id`

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=S2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.factory_section_id == S2.id`.
2. returns: `result.id != a1_id`.
3. count: rows_of(M1) has exactly 1 row.
4. re-read rows_of(M1)[0]: `id == result.id`, `factory_section_id == S2.id`.
5. re-read rows_of(M1)[0]: `created_by == U2.id`.
6. re-read rows_of(M1)[0]: `updated_at is None`, `updated_by is None`.
7. count: `machine_section_assignments` rows with `id == a1_id`: exactly 0.

### MSA-UP-03 — re-saving the section the machine already has leaves its row untouched
- **Rules:** `upsert_for_machine` R3 [BUG-909]
- **Kind:** bug
- **Expect:** xfail BUG-909
- **Fails today on:** Then 3 (the row is deleted and a new one inserted, so the returned id is new)

**Given**
1. A1 = assignment of M1 to S1. (`created_by U1.id`.)
2. `a1_id = A1.id`

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.factory_section_id == S1.id`.
2. count: rows_of(M1) has exactly 1 row.
3. returns: `result.id == a1_id`.
4. re-read rows_of(M1)[0]: `id == a1_id`.
5. re-read rows_of(M1)[0]: `created_by == U1.id`.

### MSA-UP-04 — re-saving the same section keeps exactly one row of that machine for that section
- **Rules:** `upsert_for_machine` R3 (the part that holds today and after the BUG-909 fix)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.factory_section_id == S1.id`.
2. returns: `result.machine_id == M1.id`.
3. count: rows_of(M1) has exactly 1 row.
4. re-read rows_of(M1)[0]: `factory_section_id == S1.id`, `workspace_id == W1.id`.
5. count: `machine_section_assignments` has exactly 1 row.

### MSA-UP-05 — clearing a machine's section deletes its row and returns None
- **Rules:** `upsert_for_machine` R4 (Q2)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=None, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: rows_of(M1) has exactly 0 rows.
3. count: `machine_section_assignments` has exactly 0 rows.

### MSA-UP-06 — clearing a machine without an assignment writes nothing and does not use user_id
- **Rules:** `upsert_for_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A2 = assignment of M2 to S1. (M1 has no assignment.)

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=None, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.
3. unchanged: unchanged(A2).
4. count: rows_of(M1) has exactly 0 rows.

### MSA-UP-07 — clearing with a user_id that is no profile still deletes the row
- **Rules:** `upsert_for_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=None, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. returns: `result is None`.
2. count: rows_of(M1) has exactly 0 rows.

### MSA-UP-08 — a move touches only the machine's own row
- **Rules:** `upsert_for_machine` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1. (Another machine, same section.)
3. A3 = assignment of M3 to S2. (Another machine, the target section.)

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=S2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.machine_id == M1.id`.
2. unchanged: unchanged(A2).
3. unchanged: unchanged(A3).
4. count: `machine_section_assignments` has exactly 3 rows.
5. unchanged: unchanged(M1).
6. unchanged: unchanged(S1).
7. unchanged: unchanged(S2).
8. unchanged: unchanged(F1).

### MSA-UP-09 — clearing touches only the machine's own row
- **Rules:** `upsert_for_machine` R5, R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1. (Another machine, same section.)

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=None, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(A2).
3. count: `machine_section_assignments` has exactly 1 row.
4. unchanged: unchanged(M1).
5. unchanged: unchanged(S1).

### MSA-UP-10 — a section of another factory is accepted
- **Rules:** `upsert_for_machine` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No assignment exists. (M1 is in F1; S3 belongs to F2.)

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=S3.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == M1.id`, `factory_section_id == S3.id`.
3. count: rows_of(M1) has exactly 1 row.

### MSA-UP-11 — a soft-deleted section is accepted
- **Rules:** `upsert_for_machine` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. No assignment exists. (SX is the soft-deleted section.)

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=SX.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `factory_section_id == SX.id`.
3. unchanged: unchanged(SX).

### MSA-UP-12 — a section of another workspace is accepted and the row gets the given workspace
- **Rules:** `upsert_for_machine` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No assignment exists. (S9 belongs to W2.)

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=S9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `factory_section_id == S9.id`.
3. re-read the returned row: `workspace_id == W1.id`.

### MSA-UP-13 — a soft-deleted machine is accepted
- **Rules:** `upsert_for_machine` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. No assignment exists. (MD is the soft-deleted machine.)

**When**
- `result = dao.upsert_for_machine(db, machine_id=MD.id, factory_section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == MD.id`, `factory_section_id == S1.id`.
3. unchanged: unchanged(MD).

### MSA-UP-14 — a machine of another workspace is accepted and stored with the given workspace
- **Rules:** `upsert_for_machine` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No assignment exists. (M9 belongs to W2.)

**When**
- `result = dao.upsert_for_machine(db, machine_id=M9.id, factory_section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == M9.id`, `factory_section_id == S1.id`.
3. re-read the returned row: `workspace_id == W1.id`.

### MSA-UP-15 — a machine whose row has another workspace_id hits the one-row-per-machine constraint and nothing changes
- **Rules:** `upsert_for_machine` R7, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1, but `workspace_id W2.id`. (M1 belongs to W1; the row says W2.)

**When**
- `dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=S2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, UniqueViolation)`.
3. raises: `"uq_machine_section_assignment_machine" in str(exc.value.orig)`.
4. unchanged: unchanged(A1).
5. re-read A1: `workspace_id == W2.id`, `factory_section_id == S1.id`.
6. count: rows_of(M1) has exactly 1 row.
7. nothing written: nothing written.

### MSA-UP-16 — a machine_id that is no machine fails on flush and nothing changes
- **Rules:** `upsert_for_machine` R8, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = assignment of M2 to S1.

**When**
- `dao.upsert_for_machine(db, machine_id=MISSING, factory_section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machine_section_assignments_machine_id_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. unchanged: unchanged(A2).

### MSA-UP-17 — a factory_section_id that is no section fails on flush and the machine's previous row is back
- **Rules:** `upsert_for_machine` R8, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machine_section_assignments_factory_section_id_fkey" in str(exc.value.orig)`.
4. unchanged: unchanged(A1).
5. re-read A1: `factory_section_id == S1.id`, `created_by == U1.id`.
6. count: rows_of(M1) has exactly 1 row.
7. nothing written: nothing written.

### MSA-UP-18 — a user_id that is no profile fails on flush and the machine's previous row is back
- **Rules:** `upsert_for_machine` R8, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=S2.id, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machine_section_assignments_created_by_fkey" in str(exc.value.orig)`.
4. unchanged: unchanged(A1).
5. re-read A1: `factory_section_id == S1.id`, `created_by == U1.id`.
6. count: rows_of(M1) has exactly 1 row.
7. nothing written: nothing written.

### MSA-UP-19 — a workspace_id that is no workspace fails on flush and nothing changes
- **Rules:** `upsert_for_machine` R8, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1. (M2 has no assignment.)

**When**
- `dao.upsert_for_machine(db, machine_id=M2.id, factory_section_id=S1.id, workspace_id=MISSING, user_id=U2.id)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machine_section_assignments_workspace_id_fkey" in str(exc.value.orig)`.
4. count: rows_of(M2) has exactly 0 rows.
5. unchanged: unchanged(A1).
6. nothing written: nothing written.

### MSA-UP-20 — the move is flushed but not committed: visible to get_by_machine in the session, undone by a rollback
- **Rules:** `upsert_for_machine` R9
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback, a commit spy, and a follow-up DAO call after the When

**Given**
1. A1 = assignment of M1 to S1.
2. `a1_id = A1.id`
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=S2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.factory_section_id == S2.id`.
2. returns: after the call, `dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id).id == result.id`.
3. count: after the savepoint rollback, rows_of(M1) has exactly 1 row.
4. re-read rows_of(M1)[0] after the savepoint rollback: `id == a1_id`, `factory_section_id == S1.id`.
5. re-read rows_of(M1)[0] after the savepoint rollback: `created_by == U1.id`.
6. mock called: the `db.commit` spy was never called.

### MSA-UP-21 — a machine whose section was already read still reports the old section after a move
- **Rules:** `upsert_for_machine` R10 (Q1)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. `loaded = M1.factory_section_id` (loads M1's assignment into the session; `loaded == S1.id`).

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=S2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.factory_section_id == S2.id`.
2. returns: `M1.factory_section_id == S1.id` (read on the same M1 object, before any re-read).
3. re-read rows_of(M1)[0]: `factory_section_id == S2.id`.

### MSA-UP-22 — once the machine is expired it reports the new section
- **Rules:** `upsert_for_machine` R10 (Q1)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — a step (`db.expire(M1)`) between the call and the checks

**Given**
1. A1 = assignment of M1 to S1.
2. `loaded = M1.factory_section_id` (loads M1's assignment into the session).

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=S2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.factory_section_id == S2.id`.
2. returns: after `db.expire(M1)`, `M1.factory_section_id == S2.id`.

### MSA-UP-23 — a machine whose section was already read still reports it after clearing
- **Rules:** `upsert_for_machine` R10 (Q1), R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. `loaded = M1.factory_section_id` (loads M1's assignment into the session; `loaded == S1.id`).

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=None, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. returns: `M1.factory_section_id == S1.id` (read on the same M1 object, before any re-read).
3. count: rows_of(M1) has exactly 0 rows.

### MSA-UP-24 — a later flush of the loaded machine does not bring the deleted row back
- **Rules:** `upsert_for_machine` R10 (Q1)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — changes the standing row M1 and flushes between the call and the checks

**Given**
1. A1 = assignment of M1 to S1.
2. `loaded = M1.factory_section_id` (loads M1's assignment into the session).

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=None, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: after `M1.name = "Renamed Unit"` and `db.flush()`, rows_of(M1) has exactly 0 rows.
3. count: `machine_section_assignments` has exactly 0 rows.

### MSA-UP-25 — user_id None is stored as NULL
- **Rules:** `upsert_for_machine` R1 (Inputs: `None` is stored as `NULL`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No assignment exists.

**When**
- `result = dao.upsert_for_machine(db, machine_id=M1.id, factory_section_id=S1.id, workspace_id=W1.id, user_id=None)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `created_by is None`.
3. re-read the returned row: `factory_section_id == S1.id`.


## `DAOMachineSectionAssignment.clear_for_section`

### MSA-CL-01 — every row of the section is deleted and its machine ids are returned
- **Rules:** `clear_for_section` R1, R2, R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1.
3. A3 = assignment of M3 to S2. (A row of another section.)

**When**
- `result = dao.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(result) == [M1.id, M2.id]`.
3. returns: `len(result) == 2`.
4. count: `machine_section_assignments` rows with `factory_section_id == S1.id`: exactly 0.
5. count: `machine_section_assignments` has exactly 1 row.
6. unchanged: unchanged(A3).
7. unchanged: unchanged(S1).
8. unchanged: unchanged(M1).
9. unchanged: unchanged(F1).

### MSA-CL-02 — a row of another workspace pointing at the same section is not touched
- **Rules:** `clear_for_section` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A9 = assignment of M9 to S1. (M9 belongs to W2, so the row says W2; it points at S1 of W1.)

**When**
- `result = dao.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == [M1.id]`.
2. unchanged: unchanged(A9).
3. count: `machine_section_assignments` has exactly 1 row.

### MSA-CL-03 — the other workspace's call removes only its own row
- **Rules:** `clear_for_section` R2, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A9 = assignment of M9 to S1. (M9 belongs to W2, so the row says W2; it points at S1 of W1.)

**When**
- `result = dao.clear_for_section(db, factory_section_id=S1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == [M9.id]`.
2. unchanged: unchanged(A1).
3. count: rows_of(M9) has exactly 0 rows.

### MSA-CL-04 — the row of a soft-deleted machine is deleted and listed too
- **Rules:** `clear_for_section` R3 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. AD = assignment of MD to S1. (MD is the soft-deleted machine.)

**When**
- `result = dao.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(result) == [M1.id, MD.id]`.
2. count: `machine_section_assignments` has exactly 0 rows.
3. unchanged: unchanged(MD).
4. re-read MD: `is_deleted is True`.

### MSA-CL-05 — the rows of a soft-deleted section are deleted and the section is not touched
- **Rules:** `clear_for_section` R3 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to SX. (SX is the soft-deleted section.)

**When**
- `result = dao.clear_for_section(db, factory_section_id=SX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == [M1.id]`.
2. count: rows_of(M1) has exactly 0 rows.
3. unchanged: unchanged(SX).
4. re-read SX: `is_deleted is True`.

### MSA-CL-06 — all 10 001 rows of a section are deleted and listed
- **Rules:** `clear_for_section` R4 [BUG-907] (P1)
- **Kind:** bug
- **Expect:** xfail BUG-907
- **Fails today on:** Then 3 (at most 10 000 rows are handled: 10 000 ids come back and 1 row is left)
- **Author:** claude — bulk setup (10 001 machines and 10 001 assignments, bulk `insert(...)`) outside the Conventions vocabulary

**Given**
1. 10 001 machines N1 … N10001, bulk-inserted; machine Nk (k = 1 … 10001) is M1 but `name` = `f"Bulk {k:05d}"` (so "Bulk 00001" … "Bulk 10001").
2. For every Nk: assignment of Nk to S1 (bulk-inserted).

**When**
- `result = dao.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(set(result)) == len(result)`.
2. returns: `set(result) <=` the set of the 10 001 machine ids.
3. returns: `len(result) == 10001`.
4. count: `machine_section_assignments` rows with `factory_section_id == S1.id`: exactly 0.

### MSA-CL-07 — an unknown section id returns an empty list and writes nothing
- **Rules:** `clear_for_section` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `result = dao.clear_for_section(db, factory_section_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.
2. nothing written: nothing written.
3. unchanged: unchanged(A1).

### MSA-CL-08 — a section with no rows returns an empty list and writes nothing
- **Rules:** `clear_for_section` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1. (S2 has no rows.)

**When**
- `result = dao.clear_for_section(db, factory_section_id=S2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.
2. nothing written: nothing written.
3. unchanged: unchanged(A1).

### MSA-CL-09 — a machine whose section was already read still reports the removed section
- **Rules:** `clear_for_section` R6 (Q1)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. `loaded = M1.factory_section_id` (loads M1's assignment into the session; `loaded == S1.id`).

**When**
- `result = dao.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == [M1.id]`.
2. returns: `M1.factory_section_id == S1.id` (read on the same M1 object, before any re-read).
3. count: rows_of(M1) has exactly 0 rows.

### MSA-CL-10 — once the machine is expired it reports no section
- **Rules:** `clear_for_section` R6 (Q1)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — a step (`db.expire(M1)`) between the call and the checks

**Given**
1. A1 = assignment of M1 to S1.
2. `loaded = M1.factory_section_id` (loads M1's assignment into the session).

**When**
- `result = dao.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == [M1.id]`.
2. returns: after `db.expire(M1)`, `M1.factory_section_id is None`.

### MSA-CL-11 — the machine ids come back in the order of the row ids
- **Rules:** `clear_for_section` R7 [BUG-906]
- **Kind:** bug
- **Expect:** xfail BUG-906 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the updated row A1 usually comes back last, giving [M1, M2, M3] — but the physical row order can match the intended order by accident)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-906")`); the assertion is never weakened

**Given**
1. A1 = assignment of M3 to S1. (Row ids and machine ids rise in different orders.)
2. A2 = assignment of M1 to S1.
3. A3 = assignment of M2 to S1.
4. A1 is changed after A3 was created: `A1.created_by = U2.id`, then `db.flush()`. (This usually moves A1 physically behind A3 in the table.)

**When**
- `result = dao.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(result) == [M1.id, M2.id, M3.id]`.
2. returns: `result == [M3.id, M1.id, M2.id]`.

### MSA-CL-12 — the removal is flushed but not committed: get_by_section sees no row in the session, a rollback brings every row back
- **Rules:** `clear_for_section` R8
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback, a commit spy, and a follow-up DAO call after the When

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1.
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(result) == [M1.id, M2.id]`.
2. returns: after the call, `dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id) == []`.
3. count: after the savepoint rollback, `machine_section_assignments` rows with `factory_section_id == S1.id`: exactly 2.
4. re-read A1 after the savepoint rollback: `machine_id == M1.id`, `created_by == U1.id`.
5. mock called: the `db.commit` spy was never called.


## Inherited `BaseDAO` methods on `MachineSectionAssignment`

### MSA-INH-01 — create with a MachineSectionAssignmentCreate schema fails on flush and saves nothing
- **Rules:** inherited R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No assignment exists.

**When**
- `dao.create(db, obj_in=MachineSectionAssignmentCreate(machine_id=M1.id, factory_section_id=S1.id))`. (The schema has no `workspace_id`.)

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `"workspace_id" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. count: `machine_section_assignments` has exactly 0 rows.

### MSA-INH-02 — create with a dict stores a row with the model defaults
- **Rules:** inherited R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No assignment exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "factory_section_id": S1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `machine_id == M1.id`, `factory_section_id == S1.id`.
3. re-read the returned row: `created_at is not None`.
4. re-read the returned row: `created_by is None`, `updated_by is None`.
5. re-read the returned row: `updated_at is None`.
6. count: `machine_section_assignments` has exactly 1 row.

### MSA-INH-03 — create of a second row for the same machine fails on flush and the first row stays
- **Rules:** inherited R1, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "machine_id": M1.id, "factory_section_id": S2.id})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, UniqueViolation)`.
3. raises: `"uq_machine_section_assignment_machine" in str(exc.value.orig)`.
4. unchanged: unchanged(A1).
5. count: rows_of(M1) has exactly 1 row.
6. nothing written: nothing written.

### MSA-INH-04 — update with a dict sets the given columns and updated_at
- **Rules:** inherited R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1. (`updated_at None`, `updated_by None`.)

**When**
- `result = dao.update(db, db_obj=A1, obj_in={"factory_section_id": S2.id, "updated_by": U2.id})`.

**Then**
1. returns: `result.id == A1.id`.
2. re-read A1: `factory_section_id == S2.id`.
3. re-read A1: `updated_by == U2.id`.
4. re-read A1: `updated_at is not None`.
5. re-read A1: `created_by == U1.id`, `machine_id == M1.id`.
6. count: `machine_section_assignments` has exactly 1 row.

### MSA-INH-05 — get_by_workspace returns the rows of that workspace only
- **Rules:** inherited R3 (the part that holds today)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S2.
3. A9 = assignment of M9 to S9. (A row of W2.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A1.id, A2.id]`.
2. returns: `len(result) == 2`.

### MSA-INH-06 — get_by_workspace returns the rows in id order
- **Rules:** inherited R3 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the updated row A1 usually comes back after A2, so the list is [A2.id, A1.id] — but the physical row order can match the intended order by accident)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-100")`); the assertion is never weakened

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S2.
3. A1 is changed after A2 was created: `A1.created_by = U2.id`, then `db.flush()`. (This usually moves A1 physically behind A2 in the table.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [A1.id, A2.id]`.
2. returns: `ids(result) == [A1.id, A2.id]`.

### MSA-INH-07 — the workspace list query on assignments asks the database for an order
- **Rules:** inherited R3 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 2 (the query has no `ORDER BY`)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order)

**Given**
1. A1 = assignment of M1 to S1.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A1.id]`.
2. statement: the one `SELECT` sent has an `ORDER BY`.

### MSA-INH-08 — get returns a row of another workspace
- **Rules:** inherited R3 ("`get` … has no workspace filter")
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A9 = assignment of M9 to S9. (A row of W2.)

**When**
- `result = dao.get(db, A9.id)`.

**Then**
1. returns: `result.id == A9.id`.
2. returns: `result.workspace_id == W2.id`.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| P3 / BUG-908 — "delete section" must leave the assignment rows untouched (FU-1) | factory section manager spec (`delete_factory_section`) | Deleting a section keeps its assignment rows; restoring it brings the machines back. No card here: this DAO's `clear_for_section` does what its name says. |
| Dead code after BUG-908 — `get_by_section`, `clear_for_section`, `MachineSectionAssignmentManager.clear_for_section` | the change that fixes BUG-908 (`docs/testing/dead-code-removal-checklist.md`) | Delete MSA-GS-01 … GS-22 and MSA-CL-01 … CL-12 with the methods; close BUG-906 and BUG-907 then. |
| FU-2 (b) — the manager's checks before `upsert_for_machine` (404 / 400 for a missing, other-workspace, deleted or other-factory section; nothing about the machine or a deleted factory) | machine section assignment manager spec | Here the DAO accepts every target (MSA-UP-10 … UP-14). |
| FU-2 (a), (d) — the manager's `clear_for_section` expires each machine itself | machine section assignment manager spec | Here the DAO does not refresh loaded machines (MSA-UP-21 … UP-24, CL-09, CL-10). |
| FU-2 (c) — a no-op `set_assignment` (same section) | machine section assignment manager spec | Follows from BUG-909 here (MSA-UP-03, UP-04). |
| FU-3 — changing a machine's factory keeps its assignment to a section of the old factory; every edit re-stamps the link | machine manager spec (`update_machine`) | No card here. |
| `get_by_section` R6 — that consecutive windows partition the rows, and which column the order uses | a test written with the BUG-906 fix (several windows in one test; emitted SQL has `ORDER BY id`) | Here MSA-GS-22 is strict but asserts only that an `ORDER BY` is present; GS-20, GS-21 state the intended order and one window and are non-strict (Spec gap 3). |
| Inherited `get`, `get_multi`, `create`, `update`, `remove`, `get_by_workspace`, `get_by_id_and_workspace` — generic behaviour (paging, "flushed, not committed", missing ids, `get_multi` without workspace filter) | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not repeated here; only what the `MachineSectionAssignment` model and its schema change has cards (MSA-INH-01 … INH-08). |
| Notes "keyword-only parameters" | none (no rule) | Spec gap 2. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `upsert_for_machine` Errors; inherited Errors | "Detail message: — (not asserted)", while the Raises column names the constraint of each violation. | Designed as a loose check: the constraint (or column) name is contained in `str(exc.value.orig)` (MSA-UP-15 … UP-19, INH-01, INH-03). Drop those lines if the text is not meant to be asserted. |
| 2 | Notes for the test designer ("every parameter after `db` is keyword-only — a positional call raises `TypeError`") | Stated as a note, not as a rule of any callable. | No card. |
| 3 | `get_by_section` R6 ("consecutive windows … partition the section's rows") | Needs several calls in one test, and today's result cannot be told (the order is unspecified). | One full-order card and one window card, both non-strict (MSA-GS-20, GS-21); no partition card, deferred to the fix. |
| 4 | `clear_for_section` R7 | The order comes from the same query as `get_by_section` R6; the spec does not say whether `clear_for_section` needs its own strict alarm. | No second statement recorder: MSA-GS-22 covers the query both methods run; MSA-CL-11 is the non-strict order card. |
| 5 | `upsert_for_machine` R4 ("`user_id` is not used") | No observable is named. | Shown by passing `user_id=MISSING`, which would fail the flush if it were stored (MSA-UP-06, UP-07). |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_machine` | Returns | MSA-GM-01, GM-02 |
| `get_by_machine` | R1 | MSA-GM-01, GM-02, GM-03, GM-04, GM-05, GM-06 |
| `get_by_machine` | R2 (P2) | MSA-GM-07, GM-08, GM-09, GM-10 |
| `get_by_machine` | R3 | MSA-GM-01 |
| `get_by_section` | Returns (a list) | MSA-GS-01 |
| `get_by_section` | R1 | MSA-GS-01, GS-02, GS-03, GS-08 |
| `get_by_section` | R2 (P2) | MSA-GS-04, GS-05 |
| `get_by_section` | R3 | MSA-GS-06, GS-07, GS-08 |
| `get_by_section` | R4 | MSA-GS-09, GS-10, GS-11, GS-12, GS-13, GS-16; GS-21 (xfail) |
| `get_by_section` | R5 | MSA-GS-14, GS-15, GS-16, GS-17, GS-18, GS-19 |
| `get_by_section` | R6 [BUG-906] | MSA-GS-20, GS-21 (non-strict xfail); GS-22 (strict xfail, statement recorder) |
| `get_by_section` | R7 | MSA-GS-01, GS-04 |
| `get_by_section` | Errors row 1 (negative `limit`) | MSA-GS-18 |
| `get_by_section` | Errors row 2 (negative `skip`) | MSA-GS-19 |
| `upsert_for_machine` | Returns | MSA-UP-01, UP-05 |
| `upsert_for_machine` | R1 | MSA-UP-01, UP-25 |
| `upsert_for_machine` | R2 (Q2) | MSA-UP-02 |
| `upsert_for_machine` | R3 [BUG-909] | MSA-UP-03 (strict xfail); UP-04 (pass companion) |
| `upsert_for_machine` | R4 (Q2) | MSA-UP-05, UP-06, UP-07, UP-09 |
| `upsert_for_machine` | R5 | MSA-UP-08, UP-09 |
| `upsert_for_machine` | R6 | MSA-UP-10, UP-11, UP-12, UP-13, UP-14 |
| `upsert_for_machine` | R7 | MSA-UP-15 |
| `upsert_for_machine` | R8 | MSA-UP-16, UP-17, UP-18, UP-19 |
| `upsert_for_machine` | R9 | MSA-UP-20 |
| `upsert_for_machine` | R10 (Q1) | MSA-UP-21, UP-22, UP-23, UP-24 |
| `upsert_for_machine` | Errors row 1 (unique, row in another workspace) | MSA-UP-15 |
| `upsert_for_machine` | Errors row 2 (unknown `machine_id`) | MSA-UP-16 |
| `upsert_for_machine` | Errors row 3 (unknown `factory_section_id`) | MSA-UP-17 |
| `upsert_for_machine` | Errors row 4 (unknown `user_id`) | MSA-UP-18 |
| `upsert_for_machine` | Errors row 5 (unknown `workspace_id`) | MSA-UP-19 |
| `upsert_for_machine` | Side effects (at most one delete and one insert, no other table, no commit) | MSA-UP-08, UP-09, UP-20 |
| `clear_for_section` | Returns | MSA-CL-01, CL-07 |
| `clear_for_section` | R1 | MSA-CL-01, CL-03 |
| `clear_for_section` | R2 | MSA-CL-01, CL-02, CL-03 |
| `clear_for_section` | R3 (P2) | MSA-CL-01, CL-04, CL-05 |
| `clear_for_section` | R4 [BUG-907] (P1) | MSA-CL-06 (strict xfail) |
| `clear_for_section` | R5 | MSA-CL-07, CL-08 |
| `clear_for_section` | R6 (Q1) | MSA-CL-09, CL-10 |
| `clear_for_section` | R7 [BUG-906] | MSA-CL-11 (non-strict xfail); strict alarm MSA-GS-22 (same query) |
| `clear_for_section` | R8 | MSA-CL-12 |
| `clear_for_section` | Errors (none) | MSA-CL-07, CL-08 are the "nothing to do" paths |
| `clear_for_section` | Side effects (rows deleted, no other table, no commit) | MSA-CL-01, CL-12 |
| inherited | R1 | MSA-INH-01, INH-02, INH-03 |
| inherited | R2 | MSA-INH-04 |
| inherited | R3 [BUG-100] | MSA-INH-06 (non-strict xfail); INH-07 (strict xfail, statement recorder); INH-05 (pass companion); `get` without workspace filter: INH-08 |
| inherited | Errors row 1 (`NotNullViolation`) | MSA-INH-01 |
| inherited | Errors row 2 (`UniqueViolation`) | MSA-INH-03 |
| BUG-906 | `get_by_section` R6, `clear_for_section` R7 | MSA-GS-20, GS-21, GS-22, CL-11 |
| BUG-907 | `clear_for_section` R4 | MSA-CL-06 |
| BUG-909 | `upsert_for_machine` R3 | MSA-UP-03 |
| BUG-100 | inherited R3 | MSA-INH-06, INH-07 |
