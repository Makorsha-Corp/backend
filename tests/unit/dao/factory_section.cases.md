# Test cases — `app/dao/factory_section.py`

> **Spec:** `tests/unit/dao/factory_section.spec.md` (source commit e48a092)
> **Status:** READY — the spec is APPROVED (2026-10-16). The cards were designed on the suggested answers of P1, P2, P3, P4, Q1, Q2 and on the house-rule reading behind BUG-905; all seven were accepted as suggested (decided by Claude under the reviewer's delegation (2026-10-16)), so no existing card changed.
> **Revision:** 2 — spec APPROVED (review round 2026-10-16, delegated) and new rule `get_by_factory` R1a (fill-gaps, closes Spec gap 3). New cards: FSD-GF-39, GF-40 (R1a, verifier H2), FSD-GF-41 (verifier H1: machines do not use up places in the page). Reworded: FSD-INH-18 "Fails today on" (fails under a sequential scan only; verifier finding 6). Spec gap 1 and gap 3 closed; Spec gap 16 added (no second R6 tie-break card is possible).
> **Counts:** 95 cases · 82 expected-to-pass · 13 expected-to-fail (bugs) · 10 deferred

## Reviewer summary
- **Per callable:** `get_by_factory` 41 (10 bug) · `soft_delete` 13 · `restore` 22 (1 bug) · inherited `BaseDAO` methods on `FactorySection` 19 (2 bug).
- **Expected-to-fail by bug:** BUG-905 4 (FSD-GF-10, GF-11, GF-12, GF-13 — strict) · BUG-904 2 (FSD-GF-15, FSD-RS-16 — strict) · BUG-903 5 (FSD-GF-32, GF-33, GF-34, GF-35 non-strict; GF-36 strict, statement recorder) · BUG-100 2 (FSD-INH-18 non-strict; INH-19 strict, statement recorder). No new bug.
- **Answers accepted 2026-10-16 (decided by Claude under the reviewer's delegation (2026-10-16)) and the cards that rest on them** (kept as the record of which cards change if an answer is ever revisited; every other card is independent of them):
  - **P1** (sections of a soft-deleted factory are hidden — BUG-904): FSD-GF-15 and FSD-RS-16, both xfail. If the answer becomes "intended", both flip to "returned" pass cards. The cards around them hold under either answer: FSD-GF-16, GF-17, GF-18, GF-19, FSD-RS-15, RS-17.
  - **P2** (the raw lookups also return deleted sections and sections of deleted factories): FSD-INH-11, INH-12, INH-13, INH-14, INH-15, INH-17. One line of another card also assumes it: FSD-SD-08 Then 3. If the answer becomes "hide them", these become "not returned" cards.
  - **P3** (restore records nobody): FSD-RS-03, RS-04. One line of each round-trip card assumes it: FSD-RS-18 Then 4, FSD-RS-19 Then 4 (`updated_by == U1.id`). If the answer becomes "restore takes the acting user", every `restore` call in the file gains an argument.
  - **P4** (restore makes no name check): FSD-RS-20 (two live sections named "Paint" afterwards), with the neighbours FSD-RS-21, RS-22 that hold under either answer.
  - **Q1** (delete leaves `is_active` as it was): FSD-SD-04, SD-05. The round-trip cards FSD-RS-18, RS-19 run `soft_delete` in their Given and so depend on it together with Q2. The Conventions sentence "deleted … `is_active` stays True" describes the state Q1 leaves behind.
  - **Q2** (restore does not touch `is_active`; exact undo): FSD-RS-06, RS-07, RS-09, RS-18, RS-19.
  - **BUG-905 reading** (HR-4: this DAO's own list hides soft-deleted sections; kept 2026-10-16 — it stays a bug): FSD-GF-10, GF-11, GF-12, GF-13, all xfail. If overwritten, the four become pass cards "returned / counts toward the page". FSD-GF-38 (deleted row left untouched by the lookup) holds under either reading.
- **Notable design choices:**
  - No card except the five non-strict order cards compares an order produced today. Every other list card compares `sorted(ids(result))`, a size, membership, an empty list or a one-row list. Each strict xfail fails today on a size or on membership, never on order: FSD-GF-12 puts three deleted sections against `limit=2` so today's page always has 2 rows; FSD-GF-13 expects `[]` where today one row is left.
  - BUG-903 and BUG-100: the order cards are non-strict; the strict alarm for each query is a statement-recorder card (FSD-GF-36, FSD-INH-19) that asserts only that an `ORDER BY` is present, not its columns.
  - One call per card, so the spec's "hidden factory and live factory in the same case" is two cards with the same Given: FSD-GF-15 (xfail) and FSD-GF-16 (pass).
  - "Flushed, not committed": one savepoint and commit-spy card per writer — FSD-SD-08, FSD-RS-10. FSD-SD-08 uses the raw by-id lookup, not `get_by_factory`, so it does not depend on BUG-905.
  - "The clock is not read" (`restore` R2a) has its own spy card, FSD-RS-05.
  - FSD-RS-20 and FSD-GF-33 stop working once a unique index on live section names exists (spec FU-2 e); neither is the only card for its rule (FSD-RS-21, RS-22; FSD-GF-32).
  - FSD-GF-39 / GF-40 (R1a): a section of W1 that names F9 of W2 is listed for W1 and not for W2 — holds today and after BUG-904, so both are plain pass cards. FSD-GF-41 repeats FSD-GF-37's Given with `limit=2`: two sections, three assignment rows, both sections expected — a join to the assignment rows would use up a place. All three were added after verification (`Author: claude`).
  - Cards marked `Author: claude` (19, now 22 with FSD-GF-39, GF-40, GF-41): bulk setup of about 100 rows — FSD-GF-11, GF-22, GF-23; edit of the standing row FD — FSD-GF-19, FSD-RS-17; non-strict xfail — FSD-GF-32, GF-33, GF-34, GF-35, FSD-INH-18; statement recorder — FSD-GF-36, FSD-INH-19; savepoint rollback and commit spy — FSD-SD-08, FSD-RS-10; clock spy — FSD-RS-05; follow-up call after the When — FSD-RS-16 (also RS-10, RS-13, RS-17); a Given that runs `dao.soft_delete` and a snapshot before it — FSD-RS-13, RS-18, RS-19.
- **Needs a decision:** nothing blocks a card. Worth a look: gap 2 (no work-order-template card), gap 5 (FSD-GF-33 against a future unique index), gap 16 (no second tie-break card is possible).


## Conventions for this module

**IDs.** `FSD` = `app/dao/factory_section.py`. `GF` get_by_factory · `SD` soft_delete · `RS` restore · `INH` inherited `BaseDAO` methods on `FactorySection`.

**Actors and fixed values.**
- `dao` = the singleton `factory_section_dao` (`from app.dao.factory_section import factory_section_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns.
- W1, W2 = two `workspaces` rows. U1, U2 = two `profiles` rows: U1 is `created_by` of every Given section, U2 is the acting user of the calls.
- `FactorySection` = `app.models.factory_section.FactorySection`. `FactorySectionCreate`, `FactorySectionUpdate` = the schemas of `app.schemas.factory_section`. `Machine` = `app.models.machine.Machine`. `MachineSectionAssignment` = `app.models.machine_section_assignment.MachineSectionAssignment`.
- MISSING = `999999999`: an id that no row of any table has.
- T0 = `datetime(2025, 12, 1, 8, 0, 0)` (naive). NOW = `datetime(2026, 3, 1, 10, 0, 0)` (naive).

**Externals.** In every test `app.dao.factory_section.utcnow` is patched to return NOW (the helper file does it; a card never patches anything itself). Nothing else is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. A card names, by column name, every column that differs from these defaults.
- These nine rows exist in every test and need no Given line: W1, W2, U1, U2 and five `factories` rows:
  - F1 = `name "Main Plant"`, `abbreviation "MP"`, `workspace_id W1.id`, `is_active True`, `is_deleted False`, `deleted_at None`, `deleted_by None`.
  - F2 = the same as F1, but `name "North Yard"`, `abbreviation "NY"`. (A second live factory of W1.)
  - F9 = the same as F1, but `name "Far Depot"`, `abbreviation "FR"`, `workspace_id W2.id`. (The factory of W2.)
  - FD = the same as F1, but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. (A soft-deleted factory of W1; `is_active` stays True.)
  - FI = the same as F1, but `name "Idle Plant"`, `abbreviation "IP"`, `is_active False`. (A live but inactive factory of W1.)
- No `factory_sections`, `machines` or `machine_section_assignments` row exists unless the card's Given lists it.
- **section** = `factory_sections` row built with `FactorySection`: `workspace_id W1.id`, `factory_id F1.id`, `created_by U1.id`, `updated_by None`, `updated_at None`, `is_active True`, `is_deleted False`, `deleted_at None`, `deleted_by None`, `created_at` left to the database. The card always gives `name`; after the word "but" it lists every other column that differs.
- **deleted** (said of a section) = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. (`is_active` stays True unless the card says `is_active False`.)
- **machine of F** = `machines` row built with `Machine`: `workspace_id` = F's `workspace_id`, `factory_id F.id`. The card always gives `name`.
- **assignment of M to S** = `machine_section_assignments` row built with `MachineSectionAssignment`: `workspace_id` = M's `workspace_id`, `machine_id M.id`, `factory_section_id S.id`.
- A Given line written as code (`db.refresh(S1)`) is a step to run exactly as written, at that place in the order.

**Named checks.**
- **ids(result)** = `[s.id for s in result]` and **names(result)** = `[s.name for s in result]` — lists in the order returned (the order is part of the check). `sorted(ids(result)) == [S1.id, S2.id]` is used where the order is not part of the check; the right-hand ids are written in Given order, which is ascending id order.
- **by_id(result, X)** = the one element of `result` whose `id == X.id`.
- **re-read X** = `db.expire_all()`, then SELECT X by id from its own table; the listed values are database values. (Expiring discards unflushed changes, so a re-read that shows a new value also proves the change was flushed.) "the returned row" = re-read by `result.id`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line, before the call). X may be a section, a factory, a machine or an assignment.
- **nothing written** = the numbers of rows in `factory_sections`, `factories`, `machines` and `machine_section_assignments` (all workspaces) equal their values before the call.
- `count:` lines count the rows of the named table in all workspaces. Assert `updated_at` only as `is None` / `is not None`.
- `raises: DataError` = `sqlalchemy.exc.DataError`; `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the call for both: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause`, `ForeignKeyViolation`, `NotNullViolation` = classes of `psycopg2.errors`.
- Further `raises:` lines of the same card are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; the harness adds the marker. Every xfail in this module is strict, except the five cards that rest on physical row order — FSD-GF-32, GF-33, GF-34, GF-35, FSD-INH-18 — marked `(non-strict)` on their Expect line (`pytest.mark.xfail(strict=False, …)`).

**Rolled back** (cards marked Author: claude only). `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**FD made live again** (cards marked Author: claude only). `FD.is_deleted = False`, `FD.deleted_at = None`, `FD.deleted_by = None`, set directly on the standing row FD, then `db.flush()` — never through a factory DAO.

**Statement recorder** (cards marked Author: claude only). The SQL statements the session sends during the When are recorded; a `statement:` line is a check on the recorded text.

**Machine lookup** (FSD-RS-13 only, Author: claude). `machine_dao` = the singleton of `app.dao.machine` (`from app.dao.machine import machine_dao`).

**Race simulations.** None in this module.


## `DAOFactorySection.get_by_factory`

### FSD-GF-01 — returns a list of the sections of that factory
- **Rules:** `get_by_factory` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. S2 = section, `name "Paint"`.
3. S3 = section, `name "Welding"`, but `factory_id F2.id`. (A section of the other factory of W1.)

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [S1.id, S2.id]`.
3. returns: `len(result) == 2`.
4. returns: `isinstance(result[0], FactorySection)`.

### FSD-GF-02 — a call for the other factory returns only that factory's section
- **Rules:** `get_by_factory` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. S2 = section, `name "Paint"`.
3. S3 = section, `name "Welding"`, but `factory_id F2.id`. (A section of the other factory of W1.)

**When**
- `result = dao.get_by_factory(db, factory_id=F2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S3.id]`.
2. returns: `result[0].name == "Welding"`.

### FSD-GF-03 — another workspace's section is not returned when its factory id is given
- **Rules:** `get_by_factory` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`. (A section of W2.)

**When**
- `result = dao.get_by_factory(db, factory_id=F9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FSD-GF-04 — the other workspace gets its own section
- **Rules:** `get_by_factory` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`. (A section of W2.)

**When**
- `result = dao.get_by_factory(db, factory_id=F9.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [S9.id]`.
2. returns: `result[0].workspace_id == W2.id`.

### FSD-GF-05 — a factory id asked for with another workspace id returns an empty list
- **Rules:** `get_by_factory` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`. (A section of W2.)

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### FSD-GF-06 — a factory with no sections returns an empty list
- **Rules:** `get_by_factory` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`. (F2 has no sections.)

**When**
- `result = dao.get_by_factory(db, factory_id=F2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FSD-GF-07 — an unknown factory id returns an empty list
- **Rules:** `get_by_factory` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.

**When**
- `result = dao.get_by_factory(db, factory_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FSD-GF-08 — factory id 0 returns an empty list
- **Rules:** `get_by_factory` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.

**When**
- `result = dao.get_by_factory(db, factory_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FSD-GF-09 — an unknown workspace id returns an empty list
- **Rules:** `get_by_factory` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### FSD-GF-10 — a soft-deleted section is not returned
- **Rules:** `get_by_factory` R2 [BUG-905]
- **Kind:** bug
- **Expect:** xfail BUG-905
- **Fails today on:** Then 2 (`is_deleted` is not looked at; the deleted section SX is returned too, so the list has two rows)

**Given**
1. S1 = section, `name "Cutting"`.
2. SX = section, `name "Old Line"`, but deleted. (A soft-deleted section of F1.)

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `S1.id in ids(result)`.
2. returns: `ids(result) == [S1.id]`.

### FSD-GF-11 — 100 soft-deleted sections in front of one live section do not fill the default page
- **Rules:** `get_by_factory` R2 [BUG-905]
- **Kind:** bug
- **Expect:** xfail BUG-905
- **Fails today on:** Then 1 (deleted sections count toward the page; 100 rows come back, at least 99 of them deleted)
- **Author:** claude — bulk setup (a loop over 100 sections) outside the Conventions vocabulary

**Given**
1. 100 deleted sections D1 … D100, inserted in that order; section Dk (k = 1 … 100) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 100") and is deleted.
2. L = section, `name "Late"`. (Live; row number 101 of F1.)

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [L.id]`.

### FSD-GF-12 — soft-deleted sections do not use up a place under limit
- **Rules:** `get_by_factory` R2 [BUG-905], R4
- **Kind:** bug
- **Expect:** xfail BUG-905
- **Fails today on:** Then 1 (deleted sections count toward `limit`; four rows match, so two rows come back, at least one of them deleted)

**Given**
1. SX1 = section, `name "Old Line"`, but deleted.
2. SX2 = section, `name "Shut Bay"`, but deleted.
3. SX3 = section, `name "Scrap Row"`, but deleted.
4. L1 = section, `name "Cutting"`. (The only live section of F1.)

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [L1.id]`.

### FSD-GF-13 — a soft-deleted section does not count toward skip
- **Rules:** `get_by_factory` R2 [BUG-905], R5
- **Kind:** bug
- **Expect:** xfail BUG-905
- **Fails today on:** Then 1 (the deleted section counts toward `skip`; two rows match, so one row is left after skipping one)

**Given**
1. SX = section, `name "Old Line"`, but deleted.
2. L1 = section, `name "Cutting"`. (The only live section of F1.)

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `result == []`.

### FSD-GF-14 — a live section with is_active False is returned
- **Rules:** `get_by_factory` R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. SI = section, `name "Idle Bay"`, but `is_active False`. (Still `is_deleted False`.)

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, SI.id]`.
2. returns: `by_id(result, SI).is_active is False`.
3. returns: `by_id(result, SI).is_deleted is False`.

### FSD-GF-15 — the live section of a soft-deleted factory is hidden
- **Rules:** `get_by_factory` R3a [BUG-904] (P1)
- **Kind:** bug
- **Expect:** xfail BUG-904
- **Fails today on:** Then 1 (the factory row is never looked at; the live section SH of the soft-deleted factory FD is returned)

**Given**
1. SH = section, `name "Cutting"`, but `factory_id FD.id`. (FD is the soft-deleted factory; SH itself is live.)
2. S1 = section, `name "Paint"`. (A live section of the live factory F1.)

**When**
- `result = dao.get_by_factory(db, factory_id=FD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FSD-GF-16 — the section of a live factory is returned while another factory of the workspace is soft-deleted
- **Rules:** `get_by_factory` R1, R3a (the side that holds today)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SH = section, `name "Cutting"`, but `factory_id FD.id`. (FD is the soft-deleted factory; SH itself is live.)
2. S1 = section, `name "Paint"`. (A live section of the live factory F1.)

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.
2. returns: `result[0].name == "Paint"`.

### FSD-GF-17 — a lookup leaves the sections of a soft-deleted factory exactly as they were
- **Rules:** `get_by_factory` R3b (1), R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. SH = section, `name "Cutting"`, but `factory_id FD.id`. (FD is the soft-deleted factory; SH itself is live.)
2. SHI = section, `name "Paint"`, but `factory_id FD.id`, `is_active False`. (Live but inactive, in FD.)

**When**
- `result = dao.get_by_factory(db, factory_id=FD.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `set(ids(result)) <= {SH.id, SHI.id}`.
3. unchanged: unchanged(SH).
4. re-read SH: `is_deleted is False`, `is_active is True`.
5. re-read SH: `deleted_at is None`, `deleted_by is None`.
6. re-read SH: `updated_at is None`.
7. unchanged: unchanged(SHI).
8. re-read SHI: `is_deleted is False`, `is_active is False`.
9. unchanged: unchanged(FD).
10. nothing written: nothing written.

### FSD-GF-18 — a live but inactive factory hides nothing
- **Rules:** `get_by_factory` R3b (2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SF = section, `name "Cutting"`, but `factory_id FI.id`. (FI is the live but inactive factory.)
2. S1 = section, `name "Paint"`. (A section of F1.)

**When**
- `result = dao.get_by_factory(db, factory_id=FI.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [SF.id]`.
2. returns: `result[0].is_deleted is False`.

### FSD-GF-19 — once the factory is no longer deleted its section is returned again, unchanged
- **Rules:** `get_by_factory` R3b (3)
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — changes the standing row FD directly, with a snapshot taken before that step

**Given**
1. SH = section, `name "Cutting"`, but `factory_id FD.id`, `updated_by U2.id`. (FD is the soft-deleted factory; SH itself is live.)
2. S1 = section, `name "Paint"`. (A section of F1.)
3. BEFORE = every column of SH, taken now.
4. FD made live again (Conventions). Nothing is done to SH.

**When**
- `result = dao.get_by_factory(db, factory_id=FD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [SH.id]`.
2. unchanged: after re-read, every column of SH equals its value in BEFORE.
3. re-read SH: `is_deleted is False`, `is_active is True`.
4. re-read SH: `deleted_at is None`, `deleted_by is None`.
5. re-read SH: `updated_by == U2.id`.
6. re-read SH: `updated_at is None`.
7. nothing written: nothing written.

### FSD-GF-20 — sections of other factories and workspaces do not use up a place in the page
- **Rules:** `get_by_factory` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = section, `name "Welding"`, but `factory_id F2.id`. (Another factory of W1.)
2. O2 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`. (A section of W2.)
3. L1 = section, `name "Cutting"`.
4. L2 = section, `name "Paint"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `sorted(ids(result)) == [L1.id, L2.id]`.

### FSD-GF-21 — skip counts only the sections of that factory
- **Rules:** `get_by_factory` R4, R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = section, `name "Welding"`, but `factory_id F2.id`. (Another factory of W1.)
2. L1 = section, `name "Cutting"`. (The only section of F1.)

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `result == []`.

### FSD-GF-22 — default limit returns exactly 100 of 101 sections
- **Rules:** `get_by_factory` R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 sections) outside the Conventions vocabulary

**Given**
1. 101 sections N1 … N101, inserted in that order; section Nk (k = 1 … 101) has `name` = `f"N{k:03d}"` (so "N001" … "N101") and is otherwise the default section.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len(set(ids(result))) == 100`.
3. returns: `set(ids(result)) <= {N1.id, …, N101.id}` (the set of all 101 ids).

### FSD-GF-23 — an explicit limit of 101 returns all 101 sections
- **Rules:** `get_by_factory` R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 sections) outside the Conventions vocabulary

**Given**
1. 101 sections N1 … N101, inserted in that order; section Nk (k = 1 … 101) has `name` = `f"N{k:03d}"` (so "N001" … "N101") and is otherwise the default section.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == [N1.id, …, N101.id]` (all 101 ids, ascending).

### FSD-GF-24 — limit 2 of three sections returns two different sections
- **Rules:** `get_by_factory` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. S2 = section, `name "Paint"`.
3. S3 = section, `name "Welding"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `len(set(ids(result))) == 2`.
3. returns: `set(ids(result)) <= {S1.id, S2.id, S3.id}`.

### FSD-GF-25 — the last window is short
- **Rules:** `get_by_factory` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. S2 = section, `name "Paint"`.
3. S3 = section, `name "Welding"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in [S1.id, S2.id, S3.id]`.

### FSD-GF-26 — limit 0 returns an empty list
- **Rules:** `get_by_factory` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### FSD-GF-27 — skip equal to the number of sections returns an empty list
- **Rules:** `get_by_factory` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. S2 = section, `name "Paint"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### FSD-GF-28 — skip one below the number of sections returns one section
- **Rules:** `get_by_factory` R5, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. S2 = section, `name "Paint"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in [S1.id, S2.id]`.

### FSD-GF-29 — skip past the number of sections returns an empty list
- **Rules:** `get_by_factory` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. S2 = section, `name "Paint"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=5)`.

**Then**
1. returns: `result == []`.

### FSD-GF-30 — negative limit is rejected by the database and nothing changes
- **Rules:** `get_by_factory` R5, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.

**When**
- `dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(S1).

### FSD-GF-31 — negative skip is rejected by the database and nothing changes
- **Rules:** `get_by_factory` R5, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.

**When**
- `dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(S1).

### FSD-GF-32 — sections come back by name, case-insensitive ascending
- **Rules:** `get_by_factory` R6 [BUG-903]
- **Kind:** bug
- **Expect:** xfail BUG-903 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the rows usually come back in insertion order ["Zulu", "bolt", "apple", "Banana"])
- **Author:** claude — non-strict xfail (physical row order can match the intended order by accident); the assertion is never weakened

**Given**
1. S1 = section, `name "Zulu"`.
2. S2 = section, `name "bolt"`.
3. S3 = section, `name "apple"`.
4. S4 = section, `name "Banana"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, S2.id, S3.id, S4.id]`.
2. returns: `names(result) == ["apple", "Banana", "bolt", "Zulu"]`.

### FSD-GF-33 — names that differ only in case come back in id order
- **Rules:** `get_by_factory` R6 [BUG-903]
- **Kind:** bug
- **Expect:** xfail BUG-903 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the rows usually come back in insertion order [S1, S2, S3, S4, S5])
- **Author:** claude — non-strict xfail (physical row order can match the intended order by accident); the assertion is never weakened

**Given**
1. S1 = section, `name "Zulu"`.
2. S2 = section, `name "bolt"`. (Lower-case b.)
3. S3 = section, `name "apple"`.
4. S4 = section, `name "Bolt"`. (Capital B; the same name as S2 except for the case, on purpose — the only card with such a pair. Once a unique index on live section names exists this row will be refused and the card must be retired; FSD-GF-32 carries the order rule without such a pair.)
5. S5 = section, `name "Banana"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, S2.id, S3.id, S4.id, S5.id]`.
2. returns: `ids(result) == [S3.id, S5.id, S2.id, S4.id, S1.id]`.

### FSD-GF-34 — a middle window holds the second and third section by name
- **Rules:** `get_by_factory` R6 [BUG-903], R4
- **Kind:** bug
- **Expect:** xfail BUG-903 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested; the database usually answers in insertion order, giving ["bolt", "apple"], but a page of the physical row order can equal the intended page by accident)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-903")`)

**Given**
1. S1 = section, `name "Zulu"`.
2. S2 = section, `name "bolt"`.
3. S3 = section, `name "apple"`.
4. S4 = section, `name "Banana"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `names(result) == ["Banana", "bolt"]`.

### FSD-GF-35 — the first window holds the first two sections by name
- **Rules:** `get_by_factory` R6 [BUG-903], R4
- **Kind:** bug
- **Expect:** xfail BUG-903 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested; the database usually answers in insertion order, giving ["Zulu", "bolt"], but a page of the physical row order can equal the intended page by accident)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-903")`)

**Given**
1. S1 = section, `name "Zulu"`.
2. S2 = section, `name "bolt"`.
3. S3 = section, `name "apple"`.
4. S4 = section, `name "Banana"`.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `names(result) == ["apple", "Banana"]`.

### FSD-GF-36 — the by-factory query asks the database for an order
- **Rules:** `get_by_factory` R6 [BUG-903]
- **Kind:** bug
- **Expect:** xfail BUG-903
- **Fails today on:** Then 2 (the query has no `ORDER BY`)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order)

**Given**
1. S1 = section, `name "Cutting"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.
2. statement: the one `SELECT` sent has an `ORDER BY`.

### FSD-GF-37 — a section with machines assigned and one without are each returned once, and nothing is written
- **Rules:** `get_by_factory` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. M1 = machine of F1, `name "Lathe"`.
3. A1 = assignment of M1 to S1.
4. M2 = machine of F1, `name "Press"`.
5. A2 = assignment of M2 to S1. (Two machines in S1.)
6. S2 = section, `name "Paint"`. (No machines.)

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `sorted(ids(result)) == [S1.id, S2.id]`.
3. nothing written: nothing written.
4. unchanged: unchanged(S1).
5. unchanged: unchanged(A1).
6. count: `machine_section_assignments` has exactly 2 rows.

### FSD-GF-38 — the lookup writes nothing and leaves a soft-deleted section as it was
- **Rules:** `get_by_factory` R7, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. SX = section, `name "Old Line"`, but deleted. (`deleted_at T0`, `deleted_by U1.id`.)

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `S1.id in ids(result)`.
2. returns: `set(ids(result)) <= {S1.id, SX.id}`.
3. nothing written: nothing written.
4. unchanged: unchanged(S1).
5. re-read S1: `updated_at is None`.
6. unchanged: unchanged(SX).
7. re-read SX: `is_deleted is True`.
8. re-read SX: `deleted_at == T0`, `deleted_by == U1.id`.

### FSD-GF-39 — a section of the workspace that names a factory of another workspace is listed for its own workspace
- **Rules:** `get_by_factory` R1a
- **Kind:** isolation
- **Expect:** pass
- **Author:** claude — added after verification

**Given**
1. SX = section, `name "Cutting"`, but `factory_id F9.id`. (`workspace_id` stays W1.id: a section of W1 that names the factory of W2.)

**When**
- `result = dao.get_by_factory(db, factory_id=F9.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [SX.id]`.
2. returns: `by_id(result, SX).workspace_id == W1.id`.
3. returns: `by_id(result, SX).factory_id == F9.id`.

### FSD-GF-40 — a section that names a factory of another workspace is not listed for the factory's workspace
- **Rules:** `get_by_factory` R1a, R1
- **Kind:** isolation
- **Expect:** pass
- **Author:** claude — added after verification

**Given**
1. SX = section, `name "Cutting"`, but `factory_id F9.id`. (`workspace_id` stays W1.id: a section of W1 that names the factory of W2.)

**When**
- `result = dao.get_by_factory(db, factory_id=F9.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### FSD-GF-41 — assigned machines do not use up places in the page
- **Rules:** `get_by_factory` R7, R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — added after verification

**Given**
1. S1 = section, `name "Cutting"`.
2. M1 = machine of F1, `name "Lathe"`.
3. A1 = assignment of M1 to S1.
4. M2 = machine of F1, `name "Press"`.
5. A2 = assignment of M2 to S1. (Two machines in S1.)
6. S2 = section, `name "Paint"`. (No machines.)

**When**
- `result = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `sorted(ids(result)) == [S1.id, S2.id]`.


## `DAOFactorySection.soft_delete`

### FSD-SD-01 — a live section is marked deleted with the clock value and the acting user
- **Rules:** `soft_delete` R1, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.

**When**
- `result = dao.soft_delete(db, db_obj=S1, deleted_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `is_deleted is True`.
3. re-read S1: `deleted_at == NOW`.
4. re-read S1: `deleted_by == U2.id`.
5. count: `factory_sections` has exactly 1 row.

### FSD-SD-02 — no other column of the section is changed by the delete
- **Rules:** `soft_delete` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`, but `updated_by U1.id`.

**When**
- `result = dao.soft_delete(db, db_obj=S1, deleted_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `name == "Cutting"`, `factory_id == F1.id`.
3. re-read S1: `workspace_id == W1.id`, `created_by == U1.id`.
4. re-read S1: `updated_by == U1.id`.
5. re-read S1: `updated_at is not None`.
6. re-read S1: `created_at == created_before`, where `created_before` is `S1.created_at` read after the last Given line and before the call.
7. re-read S1: `is_deleted is True`.

### FSD-SD-03 — the delete does not stamp updated_by
- **Rules:** `soft_delete` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`. (`updated_by None`.)

**When**
- `result = dao.soft_delete(db, db_obj=S1, deleted_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `updated_by is None`.
3. re-read S1: `updated_at is not None`.
4. re-read S1: `is_deleted is True`.

### FSD-SD-04 — an active section still says active after the delete
- **Rules:** `soft_delete` R2a (Q1)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`. (`is_active True`.)

**When**
- `result = dao.soft_delete(db, db_obj=S1, deleted_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `is_deleted is True`.
3. re-read S1: `is_active is True`.

### FSD-SD-05 — a live section with is_active False is deleted and stays inactive
- **Rules:** `soft_delete` R2a (Q1), R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SI = section, `name "Idle Bay"`, but `is_active False`. (Still `is_deleted False`.)

**When**
- `result = dao.soft_delete(db, db_obj=SI, deleted_by=U2.id)`.

**Then**
1. returns: `result is SI` (the very object that was passed in).
2. re-read SI: `is_deleted is True`.
3. re-read SI: `is_active is False`.
4. re-read SI: `deleted_at == NOW`, `deleted_by == U2.id`.

### FSD-SD-06 — the machine, its assignment row and the factory of the deleted section are left exactly as they were
- **Rules:** `soft_delete` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. M1 = machine of F1, `name "Lathe"`.
3. A1 = assignment of M1 to S1.

**When**
- `result = dao.soft_delete(db, db_obj=S1, deleted_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `is_deleted is True`.
3. unchanged: unchanged(A1).
4. re-read A1: `machine_id == M1.id`, `factory_section_id == S1.id`.
5. count: `machine_section_assignments` has exactly 1 row.
6. unchanged: unchanged(M1).
7. count: `machines` has exactly 1 row.
8. unchanged: unchanged(F1).
9. re-read F1: `is_deleted is False`, `is_active is True`.
10. nothing written: nothing written.

### FSD-SD-07 — an already deleted section gets a new deletion stamp without an error
- **Rules:** `soft_delete` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SX = section, `name "Old Line"`, but deleted. (`deleted_at T0`, `deleted_by U1.id`.)

**When**
- `result = dao.soft_delete(db, db_obj=SX, deleted_by=U2.id)`.

**Then**
1. returns: `result is SX` (the very object that was passed in).
2. re-read SX: `deleted_at == NOW`.
3. re-read SX: `deleted_by == U2.id`.
4. re-read SX: `is_deleted is True`.

### FSD-SD-08 — the delete is flushed but not committed: visible to the by-id lookup in the session, undone by a rollback
- **Rules:** `soft_delete` R5
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback, a commit spy, and a follow-up DAO call after the When

**Given**
1. S1 = section, `name "Cutting"`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.soft_delete(db, db_obj=S1, deleted_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `is_deleted is True`.
3. returns: after the call, `dao.get_by_id_and_workspace(db, id=S1.id, workspace_id=W1.id).is_deleted is True`.
4. re-read S1 after the savepoint rollback: `is_deleted is False`, `is_active is True`.
5. re-read S1 after the savepoint rollback: `deleted_at is None`, `deleted_by is None`.
6. mock called: the `db.commit` spy was never called.

### FSD-SD-09 — a section of another workspace is deleted all the same
- **Rules:** `soft_delete` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`. (A section of W2.)

**When**
- `result = dao.soft_delete(db, db_obj=S9, deleted_by=U2.id)`.

**Then**
1. returns: `result is S9` (the very object that was passed in).
2. re-read S9: `is_deleted is True`.
3. re-read S9: `deleted_at == NOW`, `deleted_by == U2.id`.
4. re-read S9: `workspace_id == W2.id`.
5. unchanged: unchanged(S1).

### FSD-SD-10 — a section of a soft-deleted factory is deleted all the same and the factory is not touched
- **Rules:** `soft_delete` R6, R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SH = section, `name "Cutting"`, but `factory_id FD.id`. (FD is the soft-deleted factory; SH itself is live.)

**When**
- `result = dao.soft_delete(db, db_obj=SH, deleted_by=U2.id)`.

**Then**
1. returns: `result is SH` (the very object that was passed in).
2. re-read SH: `is_deleted is True`.
3. re-read SH: `deleted_at == NOW`, `deleted_by == U2.id`.
4. unchanged: unchanged(FD).
5. re-read FD: `is_deleted is True`.
6. re-read FD: `deleted_at == T0`, `deleted_by == U1.id`.

### FSD-SD-11 — only that section row is touched
- **Rules:** `soft_delete` R6, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. S2 = section, `name "Paint"`.
3. SX = section, `name "Old Line"`, but deleted. (`deleted_at T0`, `deleted_by U1.id`.)

**When**
- `result = dao.soft_delete(db, db_obj=S1, deleted_by=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `is_deleted is True`.
3. unchanged: unchanged(S2).
4. re-read S2: `is_deleted is False`, `updated_at is None`.
5. unchanged: unchanged(SX).
6. re-read SX: `deleted_at == T0`, `deleted_by == U1.id`.
7. nothing written: nothing written.
8. count: `factory_sections` has exactly 3 rows.

### FSD-SD-12 — a deleted_by that is no profile id fails on flush and the section stays live
- **Rules:** `soft_delete` R7, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.

**When**
- `dao.soft_delete(db, db_obj=S1, deleted_by=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"factory_sections_deleted_by_fkey" in str(exc.value.orig)`.
4. unchanged: unchanged(S1).
5. re-read S1: `is_deleted is False`.
6. re-read S1: `deleted_at is None`, `deleted_by is None`.
7. re-read S1: `updated_at is None`.
8. nothing written: nothing written.

### FSD-SD-13 — deleted_by None is stored as NULL and the section is deleted
- **Rules:** `soft_delete` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.

**When**
- `result = dao.soft_delete(db, db_obj=S1, deleted_by=None)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `deleted_by is None`.
3. re-read S1: `is_deleted is True`.
4. re-read S1: `deleted_at == NOW`.


## `DAOFactorySection.restore`

### FSD-RS-01 — a deleted section is made live again and its deletion stamp is cleared
- **Rules:** `restore` R1, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. SX = section, `name "Old Line"`, but deleted. (`deleted_at T0`, `deleted_by U1.id`.)

**When**
- `result = dao.restore(db, db_obj=SX)`.

**Then**
1. returns: `result is SX` (the very object that was passed in).
2. re-read SX: `is_deleted is False`.
3. re-read SX: `deleted_at is None`.
4. re-read SX: `deleted_by is None`.
5. count: `factory_sections` has exactly 1 row.

### FSD-RS-02 — no other column of the section is changed by the restore
- **Rules:** `restore` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. SX = section, `name "Old Line"`, but deleted.

**When**
- `result = dao.restore(db, db_obj=SX)`.

**Then**
1. returns: `result is SX` (the very object that was passed in).
2. re-read SX: `name == "Old Line"`, `factory_id == F1.id`.
3. re-read SX: `workspace_id == W1.id`, `created_by == U1.id`.
4. re-read SX: `created_at == created_before`, where `created_before` is `SX.created_at` read after the last Given line and before the call.
5. re-read SX: `updated_at is not None`.
6. re-read SX: `is_deleted is False`.

### FSD-RS-03 — updated_by keeps the value it had
- **Rules:** `restore` R2a (P3)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. SX = section, `name "Old Line"`, but `updated_by U2.id`, deleted. (`deleted_by U1.id`.)

**When**
- `result = dao.restore(db, db_obj=SX)`.

**Then**
1. returns: `result is SX` (the very object that was passed in).
2. re-read SX: `updated_by == U2.id`.
3. re-read SX: `is_deleted is False`.

### FSD-RS-04 — an empty updated_by stays empty: nobody is recorded as having restored
- **Rules:** `restore` R2a (P3)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. SX = section, `name "Old Line"`, but deleted. (`updated_by None`, `deleted_by U1.id`.)

**When**
- `result = dao.restore(db, db_obj=SX)`.

**Then**
1. returns: `result is SX` (the very object that was passed in).
2. re-read SX: `updated_by is None`.
3. re-read SX: `is_deleted is False`.
4. re-read SX: `deleted_by is None`.

### FSD-RS-05 — the restore does not read the clock
- **Rules:** `restore` R2a ("The clock is not read")
- **Kind:** external
- **Expect:** pass
- **Author:** claude — inspects the helper's patch of `app.dao.factory_section.utcnow` (a card of the local model may not touch a mock)

**Given**
1. SX = section, `name "Old Line"`, but deleted.
2. The mock that the helper file put in place of `app.dao.factory_section.utcnow` is at hand, and its number of calls is noted now.

**When**
- `result = dao.restore(db, db_obj=SX)`.

**Then**
1. returns: `result is SX` (the very object that was passed in).
2. re-read SX: `is_deleted is False`.
3. mock called: the patched `utcnow` was not called during the When (its number of calls is the one noted before).
4. re-read SX: `deleted_at is None`.

### FSD-RS-06 — a section deleted while active comes back active
- **Rules:** `restore` R3 (Q2)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. SX = section, `name "Old Line"`, but deleted. (`is_active True`.)

**When**
- `result = dao.restore(db, db_obj=SX)`.

**Then**
1. returns: `result is SX` (the very object that was passed in).
2. re-read SX: `is_active is True`.
3. re-read SX: `is_deleted is False`.

### FSD-RS-07 — a deleted section with is_active False comes back live and still inactive
- **Rules:** `restore` R3 (Q2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SXI = section, `name "Shut Bay"`, but `is_active False`, deleted. (Inactive and soft-deleted.)

**When**
- `result = dao.restore(db, db_obj=SXI)`.

**Then**
1. returns: `result is SXI` (the very object that was passed in).
2. re-read SXI: `is_active is False`.
3. re-read SXI: `is_deleted is False`.
4. re-read SXI: `deleted_at is None`, `deleted_by is None`.

### FSD-RS-08 — a section that is already live, loaded from the database, is left exactly as it is with no UPDATE
- **Rules:** `restore` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`. (Live and active; `updated_at None`.)
2. S1 is loaded from the database before the call: `db.refresh(S1)`. (Without this step the call would issue an UPDATE.)

**When**
- `result = dao.restore(db, db_obj=S1)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. unchanged: unchanged(S1).
3. re-read S1: `updated_at is None`.
4. re-read S1: `is_deleted is False`, `is_active is True`.
5. re-read S1: `deleted_at is None`, `deleted_by is None`.
6. count: `factory_sections` has exactly 1 row.

### FSD-RS-09 — a live but inactive section, loaded from the database, stays inactive with no UPDATE
- **Rules:** `restore` R4, R3 (Q2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SI = section, `name "Idle Bay"`, but `is_active False`. (Still `is_deleted False`, no deletion stamp, `updated_at None`.)
2. SI is loaded from the database before the call: `db.refresh(SI)`. (Without this step the call would issue an UPDATE.)

**When**
- `result = dao.restore(db, db_obj=SI)`.

**Then**
1. returns: `result is SI` (the very object that was passed in).
2. unchanged: unchanged(SI).
3. re-read SI: `updated_at is None`.
4. re-read SI: `is_active is False`.
5. re-read SI: `is_deleted is False`.

### FSD-RS-10 — the restore is flushed but not committed: visible to the by-factory list in the session, undone by a rollback
- **Rules:** `restore` R5
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback, a commit spy, and a follow-up DAO call after the When

**Given**
1. SX = section, `name "Old Line"`, but deleted. (`deleted_at T0`, `deleted_by U1.id`; in the live factory F1.)
2. S2 = section, `name "Cutting"`.
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.restore(db, db_obj=SX)`.

**Then**
1. returns: `result is SX` (the very object that was passed in).
2. re-read SX: `is_deleted is False`.
3. returns: after the call, with `listed = dao.get_by_factory(db, factory_id=F1.id, workspace_id=W1.id)`: `sorted(ids(listed)) == [SX.id, S2.id]`.
4. returns: `by_id(listed, SX).is_deleted is False`.
5. re-read SX after the savepoint rollback: `is_deleted is True`.
6. re-read SX after the savepoint rollback: `deleted_at == T0`.
7. re-read SX after the savepoint rollback: `deleted_by == U1.id`.
8. mock called: the `db.commit` spy was never called.

### FSD-RS-11 — a section of another workspace is restored all the same
- **Rules:** `restore` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. SX9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`, deleted. (A soft-deleted section of W2.)

**When**
- `result = dao.restore(db, db_obj=SX9)`.

**Then**
1. returns: `result is SX9` (the very object that was passed in).
2. re-read SX9: `is_deleted is False`.
3. re-read SX9: `deleted_at is None`, `deleted_by is None`.
4. re-read SX9: `workspace_id == W2.id`.
5. unchanged: unchanged(S1).

### FSD-RS-12 — other deleted sections stay deleted and a live one is not touched
- **Rules:** `restore` R6, Side effects
- **Kind:** isolation
- **Expect:** pass

**Given**
1. SX1 = section, `name "Old Line"`, but deleted.
2. SX2 = section, `name "Shut Bay"`, but deleted. (Same factory; `deleted_at T0`, `deleted_by U1.id`.)
3. S3 = section, `name "Cutting"`. (Live, same factory.)
4. SX4 = section, `name "Scrap Row"`, but `factory_id F2.id`, deleted. (A deleted section of another factory.)

**When**
- `result = dao.restore(db, db_obj=SX1)`.

**Then**
1. returns: `result is SX1` (the very object that was passed in).
2. re-read SX1: `is_deleted is False`.
3. unchanged: unchanged(SX2).
4. re-read SX2: `is_deleted is True`.
5. re-read SX2: `deleted_at == T0`, `deleted_by == U1.id`.
6. unchanged: unchanged(S3).
7. re-read S3: `is_deleted is False`, `updated_at is None`.
8. unchanged: unchanged(SX4).
9. re-read SX4: `is_deleted is True`.
10. nothing written: nothing written.
11. count: `factory_sections` has exactly 4 rows.

### FSD-RS-13 — after delete and restore the machine and its assignment are as before and the machine lookup returns the machine
- **Rules:** `restore` R7; `soft_delete` R3
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — a Given step that runs `dao.soft_delete`, snapshots taken before it, and a follow-up call of another DAO (`machine_dao.get_by_section`) after the When

**Given**
1. S1 = section, `name "Cutting"`.
2. M1 = machine of F1, `name "Lathe"`.
3. A1 = assignment of M1 to S1.
4. BEFORE_M = every column of M1 and BEFORE_A = every column of A1, taken now.
5. S1 is soft-deleted through the DAO: `dao.soft_delete(db, db_obj=S1, deleted_by=U2.id)`. (`soft_delete` alone — no assignment is removed.)

**When**
- `result = dao.restore(db, db_obj=S1)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. re-read S1: `is_deleted is False`.
3. unchanged: after re-read, every column of M1 equals its value in BEFORE_M.
4. unchanged: after re-read, every column of A1 equals its value in BEFORE_A.
5. re-read A1: `machine_id == M1.id`, `factory_section_id == S1.id`.
6. count: `machine_section_assignments` has exactly 1 row.
7. returns: after the call, `sorted(m.id for m in machine_dao.get_by_section(db, factory_section_id=S1.id, workspace_id=W1.id)) == [M1.id]`.

### FSD-RS-14 — the restore writes nothing to the machine or the assignment row of the section
- **Rules:** `restore` R7, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. SX = section, `name "Old Line"`, but deleted.
2. M1 = machine of F1, `name "Lathe"`.
3. A1 = assignment of M1 to SX. (The assignment was kept while the section was deleted.)

**When**
- `result = dao.restore(db, db_obj=SX)`.

**Then**
1. returns: `result is SX` (the very object that was passed in).
2. re-read SX: `is_deleted is False`.
3. unchanged: unchanged(A1).
4. re-read A1: `machine_id == M1.id`, `factory_section_id == SX.id`.
5. unchanged: unchanged(M1).
6. count: `machine_section_assignments` has exactly 1 row.
7. nothing written: nothing written.

### FSD-RS-15 — a deleted section of a soft-deleted factory is restored and the factory row stays as it was
- **Rules:** `restore` R7b
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SHX = section, `name "Old Line"`, but `factory_id FD.id`, deleted. (FD is the soft-deleted factory.)

**When**
- `result = dao.restore(db, db_obj=SHX)`.

**Then**
1. returns: `result is SHX` (the very object that was passed in).
2. re-read SHX: `is_deleted is False`.
3. re-read SHX: `deleted_at is None`, `deleted_by is None`.
4. re-read SHX: `factory_id == FD.id`.
5. unchanged: unchanged(FD).
6. re-read FD: `is_deleted is True`.
7. re-read FD: `deleted_at == T0`, `deleted_by == U1.id`.

### FSD-RS-16 — a section restored inside a soft-deleted factory stays hidden from the by-factory list
- **Rules:** `restore` R7c [BUG-904] (P1); `get_by_factory` R3a
- **Kind:** bug
- **Expect:** xfail BUG-904
- **Fails today on:** Then 3 (the factory row is never looked at; the restored section is listed although FD is still deleted)
- **Author:** claude — a follow-up DAO call after the When

**Given**
1. SHX = section, `name "Old Line"`, but `factory_id FD.id`, deleted. (FD is the soft-deleted factory.)

**When**
- `result = dao.restore(db, db_obj=SHX)`.

**Then**
1. returns: `result is SHX` (the very object that was passed in).
2. re-read SHX: `is_deleted is False`.
3. returns: after the call, `dao.get_by_factory(db, factory_id=FD.id, workspace_id=W1.id) == []`.

### FSD-RS-17 — a section restored inside a soft-deleted factory is listed once the factory is no longer deleted
- **Rules:** `restore` R7c (second sentence — holds today); `get_by_factory` R3b (3)
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — changes the standing row FD directly between the call and the checks, and a follow-up DAO call

**Given**
1. SHX = section, `name "Old Line"`, but `factory_id FD.id`, deleted. (FD is the soft-deleted factory.)

**When**
- `result = dao.restore(db, db_obj=SHX)`.

**Then**
1. returns: `result is SHX` (the very object that was passed in).
2. re-read SHX: `is_deleted is False`.
3. returns: after the step "FD made live again" (Conventions; nothing is done to SHX), `ids(dao.get_by_factory(db, factory_id=FD.id, workspace_id=W1.id)) == [SHX.id]`.
4. re-read SHX: `deleted_at is None`, `deleted_by is None`.

### FSD-RS-18 — delete then restore gives back the same value in every column except updated_at
- **Rules:** `restore` R8 (Q2); `soft_delete` R5
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — a Given step that runs `dao.soft_delete`, and a snapshot taken before it

**Given**
1. S1 = section, `name "Cutting"`, but `updated_by U1.id`. (Live and active.)
2. BEFORE = every column of S1, taken now.
3. S1 is soft-deleted through the DAO: `dao.soft_delete(db, db_obj=S1, deleted_by=U2.id)`.

**When**
- `result = dao.restore(db, db_obj=S1)`.

**Then**
1. returns: `result is S1` (the very object that was passed in).
2. unchanged: after re-read, every column of S1 except `updated_at` equals its value in BEFORE.
3. re-read S1: `name == "Cutting"`, `factory_id == F1.id`.
4. re-read S1: `updated_by == U1.id`.
5. re-read S1: `is_active is True`.
6. re-read S1: `is_deleted is False`.
7. re-read S1: `deleted_at is None`, `deleted_by is None`.
8. re-read S1: `updated_at is not None`.

### FSD-RS-19 — delete then restore of an inactive section gives back an inactive section
- **Rules:** `restore` R8 (Q2), R3 (Q2); `soft_delete` R2a (Q1)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — a Given step that runs `dao.soft_delete`, and a snapshot taken before it

**Given**
1. SI = section, `name "Idle Bay"`, but `is_active False`, `updated_by U1.id`. (Live and inactive.)
2. BEFORE = every column of SI, taken now.
3. SI is soft-deleted through the DAO: `dao.soft_delete(db, db_obj=SI, deleted_by=U2.id)`.

**When**
- `result = dao.restore(db, db_obj=SI)`.

**Then**
1. returns: `result is SI` (the very object that was passed in).
2. unchanged: after re-read, every column of SI except `updated_at` equals its value in BEFORE.
3. re-read SI: `is_active is False`.
4. re-read SI: `updated_by == U1.id`.
5. re-read SI: `is_deleted is False`.
6. re-read SI: `deleted_at is None`, `deleted_by is None`.

### FSD-RS-20 — a section is restored although a live section of the same factory has its name
- **Rules:** `restore` R9 (P4)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SX = section, `name "Paint"`, but deleted.
2. S2 = section, `name "Paint"`. (Live, same factory; the same name as SX on purpose — the only card with two sections of one factory that share a name and are both live afterwards. Once a unique index on live section names exists the restore will be refused and this card must be replaced; FSD-RS-21 and FSD-RS-22 carry "no name check" without such a collision.)

**When**
- `result = dao.restore(db, db_obj=SX)`.

**Then**
1. returns: `result is SX` (the very object that was passed in).
2. re-read SX: `is_deleted is False`.
3. re-read SX: `name == "Paint"`.
4. unchanged: unchanged(S2).
5. re-read S2: `is_deleted is False`, `updated_at is None`.
6. re-read S2: `name == "Paint"`.
7. count: `factory_sections` has exactly 2 rows.

### FSD-RS-21 — a section is restored although another soft-deleted section of the factory has its name
- **Rules:** `restore` R9 (P4), R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SX = section, `name "Paint"`, but deleted.
2. SX2 = section, `name "Paint"`, but deleted. (The same name as SX on purpose; also soft-deleted, same factory.)

**When**
- `result = dao.restore(db, db_obj=SX)`.

**Then**
1. returns: `result is SX` (the very object that was passed in).
2. re-read SX: `is_deleted is False`.
3. re-read SX: `name == "Paint"`.
4. unchanged: unchanged(SX2).
5. re-read SX2: `is_deleted is True`.
6. count: `factory_sections` has exactly 2 rows.

### FSD-RS-22 — a section is restored although a live section of another factory has its name
- **Rules:** `restore` R9 (P4)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. SX = section, `name "Paint"`, but deleted.
2. S2 = section, `name "Paint"`, but `factory_id F2.id`. (The same name as SX on purpose; live, in the other factory of W1.)

**When**
- `result = dao.restore(db, db_obj=SX)`.

**Then**
1. returns: `result is SX` (the very object that was passed in).
2. re-read SX: `is_deleted is False`.
3. re-read SX: `name == "Paint"`, `factory_id == F1.id`.
4. unchanged: unchanged(S2).
5. re-read S2: `is_deleted is False`, `updated_at is None`.


## Inherited `BaseDAO` methods on `FactorySection`

### FSD-INH-01 — create with a dict of the three required values stores a section with the model defaults
- **Rules:** inherited R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "Cutting", "factory_id": F1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name == "Cutting"`, `factory_id == F1.id`, `workspace_id == W1.id`.
3. re-read the returned row: `is_active is True`, `is_deleted is False`.
4. re-read the returned row: `created_at is not None`.
5. re-read the returned row: `created_by is None`, `updated_by is None`.
6. re-read the returned row: `updated_at is None`.
7. re-read the returned row: `deleted_at is None`, `deleted_by is None`.
8. count: `factory_sections` has exactly 1 row.

### FSD-INH-02 — create with a FactorySectionCreate schema fails on flush and saves no section
- **Rules:** inherited R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `dao.create(db, obj_in=FactorySectionCreate(name="Cutting", factory_id=F1.id))`. (The schema has no `workspace_id`.)

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `"workspace_id" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. count: `factory_sections` has exactly 0 rows.

### FSD-INH-03 — create with a dict that has no factory_id fails on flush and saves no section
- **Rules:** inherited R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": "Cutting"})`. (`factory_id` is not in the dict.)

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `"factory_id" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. count: `factory_sections` has exactly 0 rows.

### FSD-INH-04 — create with a dict that has no name fails on flush and saves no section
- **Rules:** inherited R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "factory_id": F1.id})`. (`name` is not in the dict.)

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "name"' in str(exc.value.orig)`.
4. nothing written: nothing written.
5. count: `factory_sections` has exactly 0 rows.

### FSD-INH-05 — create with a factory_id that is no factory id fails on flush and saves no section
- **Rules:** inherited R2, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": "Cutting", "factory_id": MISSING})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"factory_sections_factory_id_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. count: `factory_sections` has exactly 0 rows.

### FSD-INH-06 — create with a workspace_id that is no workspace id fails on flush and saves no section
- **Rules:** inherited R2, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `dao.create(db, obj_in={"workspace_id": MISSING, "name": "Cutting", "factory_id": F1.id})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"factory_sections_workspace_id_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. count: `factory_sections` has exactly 0 rows.

### FSD-INH-07 — create saves a section whose factory belongs to another workspace as given
- **Rules:** inherited R2a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "Cutting", "factory_id": F9.id})`. (F9 is the factory of W2.)

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`.
3. re-read the returned row: `factory_id == F9.id`.
4. re-read the returned row: `name == "Cutting"`.
5. count: `factory_sections` has exactly 1 row.

### FSD-INH-08 — update with a FactorySectionUpdate that sets only the name changes only the name
- **Rules:** inherited R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.

**When**
- `result = dao.update(db, db_obj=S1, obj_in=FactorySectionUpdate(name="B"))`. `factory_id` is not sent.

**Then**
1. returns: `result.id == S1.id`.
2. re-read S1: `name == "B"`.
3. re-read S1: `factory_id == F1.id`.
4. re-read S1: `is_active is True`, `is_deleted is False`.

### FSD-INH-09 — update with an explicit null name changes only the factory
- **Rules:** inherited R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.

**When**
- `result = dao.update(db, db_obj=S1, obj_in=FactorySectionUpdate(name=None, factory_id=F2.id))`.

**Then**
1. returns: `result.id == S1.id`.
2. re-read S1: `factory_id == F2.id`.
3. re-read S1: `name == "Cutting"`.
4. re-read S1: `workspace_id == W1.id`.

### FSD-INH-10 — update with a dict can switch is_active off and changes nothing else
- **Rules:** inherited R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.

**When**
- `result = dao.update(db, db_obj=S1, obj_in={"is_active": False})`.

**Then**
1. returns: `result.id == S1.id`.
2. re-read S1: `is_active is False`.
3. re-read S1: `is_deleted is False`.
4. re-read S1: `name == "Cutting"`, `factory_id == F1.id`.
5. re-read S1: `deleted_at is None`, `deleted_by is None`.

### FSD-INH-11 — get returns the section of another workspace
- **Rules:** inherited R4 (P2)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`. (A section of W2.)

**When**
- `result = dao.get(db, S9.id)`.

**Then**
1. returns: `result.id == S9.id`.
2. returns: `result.workspace_id == W2.id`.
3. returns: `result.name == "Packing"`.

### FSD-INH-12 — get returns a soft-deleted section
- **Rules:** inherited R4 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SX = section, `name "Old Line"`, but deleted.

**When**
- `result = dao.get(db, SX.id)`.

**Then**
1. returns: `result.id == SX.id`.
2. returns: `result.is_deleted is True`.

### FSD-INH-13 — get returns the section of a soft-deleted factory
- **Rules:** inherited R4 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SH = section, `name "Cutting"`, but `factory_id FD.id`. (FD is the soft-deleted factory; SH itself is live.)

**When**
- `result = dao.get(db, SH.id)`.

**Then**
1. returns: `result.id == SH.id`.
2. returns: `result.factory_id == FD.id`.
3. returns: `result.is_deleted is False`.

### FSD-INH-14 — get_by_id_and_workspace returns a soft-deleted section of the workspace
- **Rules:** inherited R4 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SX = section, `name "Old Line"`, but deleted. (`deleted_at T0`, `deleted_by U1.id`.)

**When**
- `result = dao.get_by_id_and_workspace(db, id=SX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == SX.id`.
2. returns: `result.is_deleted is True`.
3. returns: `result.deleted_at == T0`.
4. returns: `result.deleted_by == U1.id`.

### FSD-INH-15 — get_by_id_and_workspace returns the section of a soft-deleted factory
- **Rules:** inherited R4 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SH = section, `name "Cutting"`, but `factory_id FD.id`. (FD is the soft-deleted factory; SH itself is live.)

**When**
- `result = dao.get_by_id_and_workspace(db, id=SH.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == SH.id`.
2. returns: `result.factory_id == FD.id`.

### FSD-INH-16 — get_by_id_and_workspace returns None for a section of another workspace
- **Rules:** inherited R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`. (A section of W2.)

**When**
- `result = dao.get_by_id_and_workspace(db, id=S9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### FSD-INH-17 — get_by_workspace returns deleted sections and sections of a deleted factory along with the rest
- **Rules:** inherited R4 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`.
2. SX = section, `name "Old Line"`, but deleted.
3. SH = section, `name "Paint"`, but `factory_id FD.id`. (FD is the soft-deleted factory; SH itself is live.)
4. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`. (A section of W2.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, SX.id, SH.id]`.
2. returns: `len(result) == 3`.
3. returns: `by_id(result, SX).is_deleted is True`.
4. returns: `by_id(result, SH).factory_id == FD.id`.

### FSD-INH-18 — get_by_workspace returns the sections in id order, not in name order
- **Rules:** inherited R5 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; only when the planner reads the table with a sequential scan does the updated row S1 come back after S2, giving [S2.id, S1.id]; under a bitmap or index scan — every whole-file run so far — the list is [S1.id, S2.id] and the test xpasses. Non-strict on purpose. Kept because once BUG-100 is fixed it is the only card that tells `ORDER BY id` from other orders: the name order would give [S2.id, S1.id])
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-100")`); the assertion is never weakened

**Given**
1. S1 = section, `name "Zulu"`.
2. S2 = section, `name "apple"`.
3. S1 is changed after S2 was created: `S1.updated_by = U2.id`, then `db.flush()`. (This usually moves S1 physically behind S2 in the table.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, S2.id]`.
2. returns: `ids(result) == [S1.id, S2.id]`.

### FSD-INH-19 — the workspace list query on sections asks the database for an order
- **Rules:** inherited R5 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 2 (the query has no `ORDER BY`)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order)

**Given**
1. S1 = section, `name "Cutting"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.
2. statement: the one `SELECT` sent has an `ORDER BY`.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview "Integration-only behavior": `skip >= 0`, `1 <= limit <= 1000` | `GET /factory-sections/` (endpoint) | 422 for `skip=-1`, `limit=0`, `limit=1001`. Here the DAO lets Postgres reject negatives (FSD-GF-30, GF-31) and `limit=0` returns `[]` by rule (FSD-GF-26). |
| FU-1 — the "restore section" feature (`restore` has no caller) | factory section manager / service / endpoint (feature to build) | 404 for a missing / other-workspace section; the answer for a section that is not deleted; who restored (P3); 409 when the name now belongs to another live section of the factory (P4); the answer for a section whose factory is soft-deleted; an inactive section comes back inactive (Q2). Here the DAO restores whatever it is given (FSD-RS-08, RS-09, RS-11, RS-15), records nobody (FSD-RS-03, RS-04) and checks no name (FSD-RS-20 … RS-22). |
| FU-2 (a) — "delete section" also deletes the assignment rows | factory section manager spec | Whether the manager's cascade stays. Here `soft_delete` alone keeps them (FSD-SD-06) and `restore` brings them back untouched (FSD-RS-13, RS-14). |
| FU-2 (b), (c), (d), (f), (g), (h) — the manager's list, search, `factory_id=0`, by-id lookup, `include_deleted`, rename inside a deleted factory | factory section manager spec | Page before filter, the list without a factory filter, the falsy zero, deleted sections shown by id, the unreachable option, the rename. Here only the DAO's own filter and paging (FSD-GF-08, GF-10 … GF-13, GF-20 … GF-29) and the raw lookups (FSD-INH-11 … INH-17). |
| FU-2 (e), P4 note — duplicate-name check capped at 100 rows, exact `==`, no unique index (HR-2) | factory section manager spec | Uniqueness per factory among live sections, enforced in the database; then `restore` gets a rule R9a and FSD-RS-20 and FSD-GF-33 are replaced. |
| FU-3 — sections and factories leave `is_active` alone at delete / restore, machines switch it | product decision / machine DAO | Whether to align them. No card. |
| FU-4 — joins to `factory_sections` that ignore `is_deleted` | work-order template DAO and item summary service reviews | Whether a soft-deleted section still matches / is still named. No card. |
| `soft_delete` R3, `restore` R7 — `work_order_templates.default_factory_section_id` rows that point at a section | integration tests of `DELETE /factory-sections/{id}/` (or this spec once it gives that model's required columns — Spec gap 2) | The template row is left untouched by both writes. Here machines, assignment rows and the factory only (FSD-SD-06, SD-10, RS-13, RS-14, RS-15). |
| `get_by_factory` R6 — which columns the order uses, and that consecutive windows partition the list | a test written with the BUG-903 fix (emitted SQL has `ORDER BY lower(name), id`; several windows in one test) | Here FSD-GF-36 is strict but asserts only that an `ORDER BY` is present; FSD-GF-32 … GF-35 state the intended order and windows and are non-strict (Spec gap 10). |
| Inherited `get`, `get_multi`, `create`, `update`, `remove`, `get_by_workspace`, `get_by_id_and_workspace` — generic behaviour (paging of `get_by_workspace`, "flushed, not committed" of `create` / `update`, `get` for a missing id) | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not repeated here; only what the `FactorySection` model and its schemas change has cards (FSD-INH-01 … INH-19). |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Status line | *(Closed 2026-10-16.)* The spec was IN REVIEW when the cards were designed; P1, P2, P3, P4, Q1, Q2 and the BUG-905 house-rule reading carried suggested answers only. | Designed on the suggestions by instruction of the project owner. All were accepted as suggested (decided by Claude under the reviewer's delegation (2026-10-16)); the spec is APPROVED and no existing card changed. |
| 2 | `soft_delete` R3, `restore` R7; Model facts | "Nothing that belongs to the section" includes `work_order_templates.default_factory_section_id`, but the Model facts give no required columns of that model. | No work-order-template card; deferred. |
| 3 | `get_by_factory` Inputs ("the factory's workspace is not looked at"); Model facts (a section may name a factory of another workspace) | Not a numbered rule, and it is not said whether such a section is still returned once BUG-904 makes the query look at the factory row. | *(Closed 2026-10-16 by spec fill-gaps: `get_by_factory` R1a — the section's own workspace is filtered on, today and after BUG-904.)* Cards FSD-GF-39 (listed for W1) and FSD-GF-40 (not listed for W2). |
| 4 | Inherited Errors rows; `soft_delete` Errors row | "Detail message: — (not asserted)", while the rules name the column (`NotNullViolation` on `workspace_id` / `factory_id` / `name`) and the constraints. | Designed as a loose check: the column or constraint name is contained in `str(exc.value.orig)` (FSD-INH-02 … INH-06, SD-12). For `name` the check is `'column "name"'` so that it cannot match another word. Drop those six lines if the text is not meant to be asserted. |
| 5 | `get_by_factory` R6 × FU-2 (e); Notes "Distinct names" | The tie-break example needs "bolt" and "Bolt" live in one factory, which a unique index on live section names will refuse. The note names only the `restore` R9 case as an allowed collision. | FSD-GF-33 keeps the spec's five names and says so in its Given; once the index exists the card must be retired. FSD-GF-32 (no such pair) carries the order rule on its own. |
| 6 | `restore` R9 | The rule "is replaced" when the unique index is added; the replacement (R9a) is not written yet. | FSD-RS-20 is designed to today's rule and marked in its Given; FSD-RS-21 and RS-22 survive the index. No xfail card for the future refusal (no bug is logged for sections). |
| 7 | `restore` R1 / R4 | Not specified: a section in a mixed state (`is_deleted True` with an empty stamp, or `is_deleted False` with a stamp left over). | No card. |
| 8 | Model facts (`created_at`) | Whether `created_at` is naive or timezone-aware is not stated. | Not blocking: compared with a value read before the call (FSD-SD-02, RS-02); no Given sets it. |
| 9 | Notes ("every parameter after `db` is keyword-only — a positional call raises `TypeError`") | Stated as a note, not as a rule of any callable. | No card. |
| 10 | `get_by_factory` R6 ("consecutive windows … partition … with no repeats or gaps") | Needs several calls in one test, and the result today cannot be told (the order is unspecified). | Two single-window cards (FSD-GF-34, GF-35), non-strict. No partition card; deferred to the fix. |
| 11 | `get_by_factory` R2 × R3a | Not stated: a soft-deleted section inside a soft-deleted factory (both rules hide it), and whether the fix adds an `include_deleted` option (left to FU-2 g). | No card for the combination; no card uses an `include_deleted` argument. |
| 12 | Inherited R3 | The return value of `update` (same instance or not) is not restated; "such a section is still returned by `get_by_factory`" is a composition of two rules. | FSD-INH-08 … INH-10 assert `result.id == S1.id` only. The composition has no card of its own: FSD-INH-10 shows the flag is stored, FSD-GF-14 that such a row is returned. |
| 13 | Inherited R5 [BUG-100] | The query is `BaseDAO`'s and its fix is in `app/dao/base.py`; the spec does not say whether the base cases already hold the strict proof. | One non-strict order card and one strict statement-recorder card are kept here (FSD-INH-18, INH-19) so that sections are covered whatever the base file has. Drop FSD-INH-19 if it duplicates a base card. |
| 14 | `restore` R2a ("The clock is not read") | No observable is given other than `deleted_at` becoming `None`. | Worked around: FSD-RS-05 (Author: claude) inspects the helper's patch of `utcnow`. It assumes the helper file exposes that mock. |
| 15 | `soft_delete` R5 ("That the section then disappears from `get_by_factory`") | Depends on BUG-905; today the section is still returned. | No follow-up `get_by_factory` call in any `soft_delete` card; the intended effect is carried by FSD-GF-10 (a section in the state `soft_delete` leaves behind). |
| 16 | `get_by_factory` R6 (tie-break "then `id` ascending") × FU-2 (e) | The `id` tie-break decides only between two returned sections whose names are equal under `lower()`. `get_by_factory` returns the sections of one factory, so such a pair is either a case-only pair ("bolt" / "Bolt", FSD-GF-33) or an exact duplicate ("Paint" / "Paint") — both break HR-2 (unique per factory, case-insensitive, trimmed) and both will be refused by the unique index on live section names that HR-2 asks for (FU-2 e). Names differing only in surrounding whitespace do not tie under `lower()`. A soft-deleted twin is no way out: after BUG-905 it is not returned, and today it would mix two bugs in one card. | No second tie-break card can be designed (checked 2026-10-16). FSD-GF-33 stays the only one; once a unique index exists the tie-break cannot be observed in this method and needs no card — the strict alarm for the missing order is FSD-GF-36. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_factory` | Returns (a list of `FactorySection`) | FSD-GF-01 |
| `get_by_factory` | R1 | FSD-GF-01, GF-02, GF-03, GF-04, GF-05, GF-16, GF-40 |
| `get_by_factory` | R1a | FSD-GF-39, GF-40 |
| `get_by_factory` | R2 [BUG-905] | FSD-GF-10, GF-11, GF-12, GF-13 (strict xfail); GF-38 (pass companion) |
| `get_by_factory` | R2a | FSD-GF-14 |
| `get_by_factory` | R3 | FSD-GF-06, GF-07, GF-08, GF-09 |
| `get_by_factory` | R3a [BUG-904] (P1) | FSD-GF-15 (strict xfail); GF-16 (pass companion); FSD-RS-16 (strict xfail) |
| `get_by_factory` | R3b (1) | FSD-GF-17 |
| `get_by_factory` | R3b (2) | FSD-GF-18 |
| `get_by_factory` | R3b (3) | FSD-GF-19; FSD-RS-17 |
| `get_by_factory` | R4 | FSD-GF-20, GF-21, GF-22, GF-23, GF-24, GF-25, GF-28, GF-41; GF-12, GF-34, GF-35 (xfail) |
| `get_by_factory` | R5 | FSD-GF-21, GF-26, GF-27, GF-28, GF-29, GF-30, GF-31; GF-13 (xfail) |
| `get_by_factory` | R6 [BUG-903] | FSD-GF-32, GF-33, GF-34, GF-35 (non-strict xfail); GF-36 (strict xfail, statement recorder) |
| `get_by_factory` | R7 | FSD-GF-17, GF-37, GF-38, GF-41 |
| `get_by_factory` | Errors row 1 (negative `limit`) | FSD-GF-30 |
| `get_by_factory` | Errors row 2 (negative `skip`) | FSD-GF-31 |
| `get_by_factory` | Side effects (none) | FSD-GF-17, GF-19, GF-37, GF-38 |
| `soft_delete` | R1 | FSD-SD-01, SD-05 |
| `soft_delete` | R2 | FSD-SD-02, SD-03 |
| `soft_delete` | R2a (Q1) | FSD-SD-04, SD-05; FSD-RS-19 |
| `soft_delete` | R3 | FSD-SD-06, SD-10; FSD-RS-13 (work-order templates: deferred, Spec gap 2) |
| `soft_delete` | R4 | FSD-SD-07 |
| `soft_delete` | R5 | FSD-SD-01, SD-08; "`restore` undoes the delete": FSD-RS-18, RS-19; "disappears from `get_by_factory`": FSD-GF-10 (Spec gap 15) |
| `soft_delete` | R6 | FSD-SD-09, SD-10, SD-11 |
| `soft_delete` | R7 | FSD-SD-12 |
| `soft_delete` | R8 | FSD-SD-13 |
| `soft_delete` | Errors row 1 (`deleted_by` references no profile) | FSD-SD-12 |
| `soft_delete` | Side effects (one row, no other table, no commit) | FSD-SD-06, SD-08, SD-11 |
| `restore` | R1 | FSD-RS-01 |
| `restore` | R2 | FSD-RS-02 |
| `restore` | R2a (P3) | FSD-RS-03, RS-04; "the clock is not read": FSD-RS-05 |
| `restore` | R3 (Q2) | FSD-RS-06, RS-07, RS-09, RS-19 |
| `restore` | R4 | FSD-RS-08, RS-09 |
| `restore` | R5 | FSD-RS-01, RS-10 |
| `restore` | R6 | FSD-RS-11, RS-12, RS-21 |
| `restore` | R7 | FSD-RS-13, RS-14 (work-order templates: deferred, Spec gap 2) |
| `restore` | R7b | FSD-RS-15 |
| `restore` | R7c [BUG-904] (P1) | FSD-RS-16 (strict xfail); RS-15 (pass companion); second sentence: RS-17 |
| `restore` | R8 (Q2) | FSD-RS-18, RS-19 |
| `restore` | R9 (P4) | FSD-RS-20, RS-21, RS-22 |
| `restore` | Errors (none) | FSD-RS-08, RS-09, RS-15, RS-20 are the "no error" paths |
| `restore` | Side effects (at most one row, no UPDATE when live, no other table, no commit) | FSD-RS-08, RS-09, RS-10, RS-12, RS-14 |
| inherited | R1 | FSD-INH-01 |
| inherited | R2 | FSD-INH-02, INH-03, INH-04, INH-05, INH-06 |
| inherited | R2a | FSD-INH-07 |
| inherited | R3 | FSD-INH-08, INH-09, INH-10 ("still returned by `get_by_factory`": INH-10 + FSD-GF-14, Spec gap 12) |
| inherited | R4 (P2) | FSD-INH-11, INH-12, INH-13, INH-14, INH-15, INH-16, INH-17 |
| inherited | R5 [BUG-100] | FSD-INH-18 (non-strict xfail); INH-19 (strict xfail, statement recorder); INH-17 (pass companion) |
| inherited | Errors row 1 (`NotNullViolation`) | FSD-INH-02, INH-03, INH-04 |
| inherited | Errors row 2 (`ForeignKeyViolation`) | FSD-INH-05, INH-06 |
| BUG-903 | `get_by_factory` R6 | FSD-GF-32, GF-33, GF-34, GF-35 (non-strict); FSD-GF-36 (strict) |
| BUG-904 | `get_by_factory` R3a, `restore` R7c | FSD-GF-15, FSD-RS-16 |
| BUG-905 | `get_by_factory` R2 | FSD-GF-10, GF-11, GF-12, GF-13 |
| BUG-100 | inherited R5 | FSD-INH-18 (non-strict); FSD-INH-19 (strict) |
