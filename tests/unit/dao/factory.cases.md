# Test cases — `app/dao/factory.py`

> **Spec:** `tests/unit/dao/factory.spec.md` (source commit e48a092)
> **Status:** READY — the spec is APPROVED (2026-10-16). The cards were designed on the suggested answers of P1, P2, P3, Q1, Q2, Q3, Q4; all seven were accepted as suggested (decided by Claude under the reviewer's delegation (2026-10-16)), so no card changed.
> **Revision:** 2 — spec APPROVED (review round 2026-10-16, delegated): no rule changed, no card changed. Wording only: the "physically behind" / "Fails today on" sentences of FCD-GW-21…24 now say the row move holds only under some query plans (non-strict); the BUG-100 / BUG-706 coverage rows list the strict statement-recorder cards; Spec gap 1 closed; Spec gap 13 added (the R6 id tie-break cannot be observed without a case-only name pair).
> **Counts:** 110 cases · 100 expected-to-pass · 10 expected-to-fail (bugs) · 10 deferred

## Reviewer summary
- **Per callable:** `get_by_workspace` 26 (4 bug) · `get_by_id_and_workspace` 13 · `get_active_factories` 28 (4 bug) · `soft_delete` 13 · `restore` 20 (2 bug) · inherited `BaseDAO` methods on `Factory` 10.
- **Expected-to-fail by bug:** BUG-100 4 (FCD-GW-22, GW-23, GW-24 non-strict; GW-26 strict) · BUG-706 4 (FCD-GA-24, GA-25, GA-26 non-strict; GA-28 strict) · BUG-895 2 (FCD-RS-19, RS-20 — strict). No new bug.
- **Answers accepted 2026-10-16 (decided by Claude under the reviewer's delegation (2026-10-16)) and the cards that rest on them** (kept as the record of which cards change if an answer is ever revisited; every other card is independent of them):
  - **P1** (the two raw lookups also return deleted factories): FCD-GW-05, GW-06, GW-07, GW-08, GW-10, FCD-GI-09, GI-12. Two lines of other cards also assume it: FCD-SD-09 Then 4 and 5, FCD-RS-07 Then 3 and 4. If the answer becomes "hide deleted", these become "not returned" cards.
  - **P2** (restore records nobody): FCD-RS-03, RS-04. One line of each round-trip card assumes it: FCD-RS-15 Then 4, FCD-RS-16 Then 4 (`updated_by == U1.id`). If the answer becomes "restore takes the acting user", every `restore` call in the file gains an argument.
  - **P3** (restore makes no name / abbreviation check of its own): FCD-RS-17, RS-18. The two BUG-895 cards FCD-RS-19, RS-20 expect the *database* error (`IntegrityError`); if the answer becomes "the DAO refuses in Python", their expected error changes too.
  - **Q1** (delete leaves `is_active` as it was): FCD-SD-04, SD-05. The round-trip cards FCD-RS-15, RS-16 run `soft_delete` in their Given and so depend on it together with Q2 (RS-15 Then 5, RS-16 Then 3). The Conventions sentence "deleted … `is_active` stays True" and FCD-GA-05 describe the state Q1 leaves behind; if the answer becomes "delete also switches `is_active` off", the Q2 cards change with it.
  - **Q2** (restore does not touch `is_active`; exact undo): FCD-RS-05, RS-06, RS-07, RS-09, RS-15, RS-16.
  - **Q3** (the active list leaves out live factories with `is_active False`): FCD-GA-07, GA-08, GA-09, GA-11, GA-13, and FCD-RS-07 Then 5. If the answer becomes "every live factory is returned", these flip to "returned"; FCD-GA-06 (deleted and inactive) stays.
  - **Q4** (the inherited unscoped `get` stays raw): FCD-INH-08, INH-09, INH-10.
- **Notable design choices:**
  - BUG-100 (raw list has no order): the spec's recipe is written into the Given rows of four cards — "Zulu" is created, then "apple", then a column of "Zulu" is changed and flushed, which — under some query plans and row placements only — moves "Zulu" physically behind "apple". FCD-GW-22, GW-23, GW-24 are **strict** xfail on it; FCD-GW-21 is the pass companion (both rows still returned once). The same two names also carry "no name ordering": the intended order is by id, which is the opposite of the name order. **Changed after finishing (2026-10-11):** all five order cards that rest on physical row order (FCD-GW-22, GW-23, GW-24, GA-24, GA-25) are now **non-strict** like GA-26 — GW-22…24 passed by accident in 6 of 9 whole-file runs once autovacuum let Postgres reuse freed row places. The strict alarm for each bug is a statement-recorder card instead: FCD-GW-26 (BUG-100) and FCD-GA-28 (BUG-706).
  - BUG-706 (active list has no order): two **strict** full-list cards — FCD-GA-24 (four names, none differing only in case) and FCD-GA-25 (the spec's own five names with the "bolt" / "Bolt" tie decided by id). The one window card, FCD-GA-26, is **non-strict**: a page of the physical row order can equal the intended page by accident (the factory manager's BUG-899 window cards had to be loosened for that reason after verification). **Changed after finishing (2026-10-11):** GA-24 and GA-25 are non-strict too; see the BUG-100 line.
  - Every other list card compares `sorted(ids(result))`, sizes or membership, so none depends on today's row order.
  - "No UPDATE issued" (`restore` R4) is seen as `updated_at is None`, and both cards (FCD-RS-08, RS-09) load the row from the database first (`db.refresh`), as the spec notes require; no statement counting.
  - "Flushed, not committed": one savepoint and commit-spy card per writer — FCD-SD-09, FCD-RS-10. They also carry the same-session lookups of R5, so no extra follow-up card is needed for them.
  - BUG-895 (`restore` R9a): one card for the name, one for the abbreviation, both strict; the passing neighbours are FCD-RS-17 (same name on another *deleted* factory) and FCD-RS-18 (same name in *another workspace*).
  - Cards marked `Author: claude` (13): bulk setup of about 100 rows — FCD-GW-08, GW-11, GW-12, GA-13, GA-14, GA-15; non-strict xfail — FCD-GA-26; savepoint rollback and commit spy — FCD-SD-09, FCD-RS-10; follow-up calls after the When — FCD-RS-07, RS-14; a Given that runs `dao.soft_delete` and a snapshot before it — FCD-RS-15, RS-16. No direct insert as the When, no statement counting, no standing factory row to edit. **After finishing: 20** — also the non-strict xfails FCD-GW-22, GW-23, GW-24, GA-24, GA-25 (bodies by the local model or exemplar; marker loosened) and the statement-recorder cards FCD-GW-26, GA-28.
- **Needs a decision:** nothing blocks a card. Worth a look: Spec gap 2 (no stock-row card), gap 3 ("the clock is not read" has no card of its own), gap 6 (FCD-GA-25 cannot be set up once the BUG-895 name index exists), gap 13 (no second tie-break card is possible).


## Conventions for this module

**IDs.** `FCD` = `app/dao/factory.py`. `GW` get_by_workspace · `GI` get_by_id_and_workspace · `GA` get_active_factories · `SD` soft_delete · `RS` restore · `INH` inherited `BaseDAO` methods on `Factory`.

**Actors and fixed values.**
- `dao` = the singleton `factory_dao` (`from app.dao.factory import factory_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns.
- W1, W2 = two `workspaces` rows. U1, U2 = two `profiles` rows: U1 is `created_by` of every Given factory, U2 is the acting user of the calls.
- `Factory` = `app.models.factory.Factory`. `FactoryCreate`, `FactoryUpdate` = the schemas of `app.schemas.factory`. `Machine` = `app.models.machine.Machine`. `FactorySection` = `app.models.factory_section.FactorySection`.
- MISSING = `999999999`: an id that no row of any table has.
- T0 = `datetime(2025, 12, 1, 8, 0, 0)` (naive). NOW = `datetime(2026, 3, 1, 10, 0, 0)` (naive).

**Externals.** In every test `app.dao.factory.utcnow` is patched to return NOW (the helper file does it; a card never patches anything itself). Nothing else is mocked.

**Given rows.** W1, W2, U1 and U2 exist in every test and need no Given line. No `factories`, `machines` or `factory_sections` row exists unless the card's Given lists it. Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. A card names, by column name, every column that differs from these defaults.
- **factory** = `factories` row: `workspace_id W1.id`, `created_by U1.id`, `updated_by None`, `updated_at None`, `is_active True`, `is_deleted False`, `deleted_at None`, `deleted_by None`, `created_at` left to the database. The card always gives `name` and `abbreviation`; after the word "but" it lists every other column that differs.
- **deleted** (said of a factory) = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. (`is_active` stays True unless the card says `is_active False`.)
- **machine of F** = `machines` row built with `Machine`: `workspace_id` = F's `workspace_id`, `factory_id F.id`, `is_active True`, `is_deleted False`, `deleted_at None`, `deleted_by None`. The card always gives `name`; after the word "but" it lists every other column that differs.
- **section of F** = `factory_sections` row built with `FactorySection`: `workspace_id` = F's `workspace_id`, `factory_id F.id`, `is_active True`, `is_deleted False`, `deleted_at None`, `deleted_by None`. The card always gives `name`; after the word "but" it lists every other column that differs.
- A Given line written as code (`db.refresh(F1)`, or `F1.abbreviation = "ZX"` followed by `db.flush()`) is a step to run exactly as written, at that place in the order.

**Named checks.**
- **ids(result)** = `[f.id for f in result]` and **names(result)** = `[f.name for f in result]` — lists in the order returned (the order is part of the check). `sorted(ids(result)) == [F1.id, F2.id]` is used where the order is not part of the check; the right-hand ids are written in Given order, which is ascending id order.
- **by_id(result, X)** = the one element of `result` whose `id == X.id`.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values. (Expiring discards unflushed changes, so a re-read that shows a new value also proves the change was flushed.) "the returned row" = re-read by `result.id`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line, before the call).
- **nothing written** = the numbers of rows in `factories`, `machines` and `factory_sections` (all workspaces) equal their values before the call.
- `count:` lines count the rows of the named table in all workspaces. Assert `updated_at` only as `is None` / `is not None`.
- `raises: DataError` = `sqlalchemy.exc.DataError`; `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the call for both: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause`, `ForeignKeyViolation`, `NotNullViolation`, `UniqueViolation` = classes of `psycopg2.errors`.
- Further `raises:` lines of the same card are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; the harness adds the marker. Every xfail in this module is strict, except the six cards that rest on physical row order — FCD-GW-22, GW-23, GW-24, GA-24, GA-25, GA-26 — marked `(non-strict)` on their Expect line (`pytest.mark.xfail(strict=False, …)`).

**Rolled back** (cards marked Author: claude only). `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**Machine lookup** (FCD-RS-14 only, Author: claude). `machine_dao` = the singleton of `app.dao.machine` (`from app.dao.machine import machine_dao`).

**Race simulations.** None in this module.


## `DAOFactory.get_by_workspace`

### FCD-GW-01 — returns a list of the factories of that workspace
- **Rules:** `get_by_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.
3. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [F1.id, F2.id]`.
3. returns: `len(result) == 2`.
4. returns: `isinstance(result[0], Factory)`.

### FCD-GW-02 — a call for the other workspace returns only that workspace's factory
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.
3. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [F9.id]`.

### FCD-GW-03 — a workspace with no factories returns an empty list
- **Rules:** `get_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`. (W2 has no factories.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### FCD-GW-04 — an unknown workspace id returns an empty list
- **Rules:** `get_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### FCD-GW-05 — a soft-deleted factory is returned along with a live one
- **Rules:** `get_by_workspace` R4 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [F1.id, FD.id]`.
2. returns: `by_id(result, FD).is_deleted is True`.
3. returns: `by_id(result, F1).is_deleted is False`.

### FCD-GW-06 — soft-deleted factories count toward limit
- **Rules:** `get_by_workspace` R4 (P1), R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD1 = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted.
2. FD2 = factory, `name "Shut Mill"`, `abbreviation "SM"`, but deleted.
3. F3 = factory, `name "Main Plant"`, `abbreviation "MP"`. (The only live factory of W1.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `sum(1 for f in result if f.is_deleted) >= 1`.
3. returns: `set(ids(result)) <= {FD1.id, FD2.id, F3.id}`.

### FCD-GW-07 — soft-deleted factories count toward skip
- **Rules:** `get_by_workspace` R4 (P1), R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD1 = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted.
2. FD2 = factory, `name "Shut Mill"`, `abbreviation "SM"`, but deleted.
3. F3 = factory, `name "Main Plant"`, `abbreviation "MP"`. (The only live factory of W1.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `len(set(ids(result))) == 2`.
3. returns: `set(ids(result)) <= {FD1.id, FD2.id, F3.id}`.

### FCD-GW-08 — 100 deleted factories in front of one live factory fill the default page
- **Rules:** `get_by_workspace` R4 (P1), R2
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 100 factories) outside the Conventions vocabulary

**Given**
1. 100 deleted factories D1 … D100, inserted in that order; factory Dk (k = 1 … 100) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 100"), `abbreviation` = `f"O{k:03d}"` (so "O001" … "O100"), and is deleted.
2. L = factory, `name "Late"`, `abbreviation "LT"`. (Live; row number 101 of W1.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `sum(1 for f in result if f.is_deleted) >= 99`.
3. returns: `set(ids(result)) <= {D1.id, …, D100.id, L.id}` (the set of all 101 ids).

### FCD-GW-09 — a live factory with is_active False is returned
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. FI = factory, `name "Idle Plant"`, `abbreviation "IP"`, but `is_active False`. (Still `is_deleted False`.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [F1.id, FI.id]`.
2. returns: `by_id(result, FI).is_active is False`.

### FCD-GW-10 — all four combinations of active and deleted are returned
- **Rules:** `get_by_workspace` R4 (P1), R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`. (Active, live.)
2. FI = factory, `name "Idle Plant"`, `abbreviation "IP"`, but `is_active False`. (Inactive, live.)
3. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (Active, deleted.)
4. FX = factory, `name "Shut Mill"`, `abbreviation "SM"`, but `is_active False`, deleted. (Inactive, deleted.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [F1.id, FI.id, FD.id, FX.id]`.
2. returns: `len(result) == 4`.

### FCD-GW-11 — default limit returns exactly 100 of 101 factories
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 factories) outside the Conventions vocabulary

**Given**
1. 101 factories N1 … N101, inserted in that order; factory Nk (k = 1 … 101) has `name` = `f"N{k:03d}"` (so "N001" … "N101"), `abbreviation` = `f"A{k:03d}"` (so "A001" … "A101"), and is otherwise the default factory.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len(set(ids(result))) == 100`.
3. returns: `set(ids(result)) <= {N1.id, …, N101.id}` (the set of all 101 ids).

### FCD-GW-12 — an explicit limit of 101 returns all 101 factories
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 factories) outside the Conventions vocabulary

**Given**
1. 101 factories N1 … N101, inserted in that order; factory Nk (k = 1 … 101) has `name` = `f"N{k:03d}"` (so "N001" … "N101"), `abbreviation` = `f"A{k:03d}"` (so "A001" … "A101"), and is otherwise the default factory.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == [N1.id, …, N101.id]` (all 101 ids, ascending).

### FCD-GW-13 — limit 2 of three factories returns two different factories
- **Rules:** `get_by_workspace` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.
3. F3 = factory, `name "South Dock"`, `abbreviation "SD"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `len(set(ids(result))) == 2`.
3. returns: `set(ids(result)) <= {F1.id, F2.id, F3.id}`.

### FCD-GW-14 — the last window is short
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.
3. F3 = factory, `name "South Dock"`, `abbreviation "SD"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in [F1.id, F2.id, F3.id]`.

### FCD-GW-15 — limit 0 returns an empty list
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### FCD-GW-16 — skip equal to the number of factories returns an empty list
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### FCD-GW-17 — skip one below the number of factories returns one factory
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in [F1.id, F2.id]`.

### FCD-GW-18 — skip past the number of factories returns an empty list
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=5)`.

**Then**
1. returns: `result == []`.

### FCD-GW-19 — negative limit is rejected by the database and nothing changes
- **Rules:** `get_by_workspace` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `dao.get_by_workspace(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(F1).

### FCD-GW-20 — negative skip is rejected by the database and nothing changes
- **Rules:** `get_by_workspace` R2, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `dao.get_by_workspace(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(F1).

### FCD-GW-21 — a factory that was updated after a later one was created is still returned exactly once
- **Rules:** `get_by_workspace` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Zulu"`, `abbreviation "ZU"`.
2. F2 = factory, `name "apple"`, `abbreviation "AP"`.
3. F1 is changed after F2 was created: `F1.abbreviation = "ZX"`, then `db.flush()`. (Under some query plans and row placements this moves F1 physically behind F2 in the table — not guaranteed, which is why the order cards are non-strict.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `sorted(ids(result)) == [F1.id, F2.id]`.
3. returns: `by_id(result, F1).abbreviation == "ZX"`.

### FCD-GW-22 — factories come back in id order, not in name order and not in the table's physical order
- **Rules:** `get_by_workspace` R3 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; under some query plans the updated row F1 comes back after F2, giving [F2.id, F1.id] — not guaranteed, hence non-strict)
- **Author:** claude — non-strict xfail (physical row order can match the intended order by accident); body as written, only the marker differs

**Given**
1. F1 = factory, `name "Zulu"`, `abbreviation "ZU"`.
2. F2 = factory, `name "apple"`, `abbreviation "AP"`.
3. F1 is changed after F2 was created: `F1.abbreviation = "ZX"`, then `db.flush()`. (Under some query plans and row placements this moves F1 physically behind F2 in the table — not guaranteed, which is why the order cards are non-strict.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [F1.id, F2.id]`.
2. returns: `ids(result) == [F1.id, F2.id]`.

### FCD-GW-23 — the first window of one holds the factory with the lowest id
- **Rules:** `get_by_workspace` R3 [BUG-100], R2
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; under some query plans the updated row F1 lies behind F2, giving the first window [F2.id] — not guaranteed, hence non-strict)
- **Author:** claude — non-strict xfail (physical row order can match the intended order by accident); body as written, only the marker differs

**Given**
1. F1 = factory, `name "Zulu"`, `abbreviation "ZU"`.
2. F2 = factory, `name "apple"`, `abbreviation "AP"`.
3. F1 is changed after F2 was created: `F1.abbreviation = "ZX"`, then `db.flush()`. (Under some query plans and row placements this moves F1 physically behind F2 in the table — not guaranteed, which is why the order cards are non-strict.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=0, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `ids(result) == [F1.id]`.

### FCD-GW-24 — the second window of one holds the factory with the next id
- **Rules:** `get_by_workspace` R3 [BUG-100], R2
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; under some query plans the updated row F1 lies behind F2, giving the second window [F1.id] — not guaranteed, hence non-strict)
- **Author:** claude — non-strict xfail (physical row order can match the intended order by accident); body as written, only the marker differs

**Given**
1. F1 = factory, `name "Zulu"`, `abbreviation "ZU"`.
2. F2 = factory, `name "apple"`, `abbreviation "AP"`.
3. F1 is changed after F2 was created: `F1.abbreviation = "ZX"`, then `db.flush()`. (Under some query plans and row placements this moves F1 physically behind F2 in the table — not guaranteed, which is why the order cards are non-strict.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `ids(result) == [F2.id]`.

### FCD-GW-25 — the lookup writes nothing
- **Rules:** `get_by_workspace` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. nothing written: nothing written.
3. unchanged: unchanged(F1).
4. unchanged: unchanged(FD).
5. re-read F1: `updated_at is None`.
6. re-read FD: `deleted_at == T0`, `deleted_by == U1.id`.

### FCD-GW-26 — the list query asks the database for an order
- **Rules:** `get_by_workspace` R3 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 2 (the query has no `ORDER BY`)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [F1.id]`.
2. statement: the one `SELECT` sent has an `ORDER BY`.


## `DAOFactory.get_by_id_and_workspace`

### FCD-GI-01 — a factory of the workspace is returned by its id
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Factory)`.
2. returns: `result.id == F1.id`.
3. returns: `result.name == "Main Plant"`.
4. returns: `result.abbreviation == "MP"`.

### FCD-GI-02 — of two factories the one with the given id is returned
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=F2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == F2.id`.
2. returns: `result.name == "North Yard"`.

### FCD-GI-03 — a factory of another workspace is not found
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = dao.get_by_id_and_workspace(db, id=F9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### FCD-GI-04 — a factory of the first workspace is not found from the second
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = dao.get_by_id_and_workspace(db, id=F1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### FCD-GI-05 — a factory of the second workspace is found from its own workspace
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = dao.get_by_id_and_workspace(db, id=F9.id, workspace_id=W2.id)`.

**Then**
1. returns: `result.id == F9.id`.
2. returns: `result.workspace_id == W2.id`.

### FCD-GI-06 — an id that no factory has returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### FCD-GI-07 — id 0 returns None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### FCD-GI-08 — an unknown workspace id returns None for an existing factory id
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=F1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result is None`.

### FCD-GI-09 — a soft-deleted factory of the workspace is returned
- **Rules:** `get_by_id_and_workspace` R4 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)

**When**
- `result = dao.get_by_id_and_workspace(db, id=FD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == FD.id`.
2. returns: `result.is_deleted is True`.
3. returns: `result.deleted_at == T0`.
4. returns: `result.deleted_by == U1.id`.

### FCD-GI-10 — a soft-deleted factory of another workspace is not found
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. FD9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`, deleted. (A soft-deleted factory of W2.)

**When**
- `result = dao.get_by_id_and_workspace(db, id=FD9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### FCD-GI-11 — a live factory with is_active False is returned
- **Rules:** `get_by_id_and_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FI = factory, `name "Idle Plant"`, `abbreviation "IP"`, but `is_active False`. (Still `is_deleted False`.)

**When**
- `result = dao.get_by_id_and_workspace(db, id=FI.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == FI.id`.
2. returns: `result.is_active is False`.
3. returns: `result.is_deleted is False`.

### FCD-GI-12 — a soft-deleted factory with is_active False is returned
- **Rules:** `get_by_id_and_workspace` R4 (P1), R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FX = factory, `name "Shut Mill"`, `abbreviation "SM"`, but `is_active False`, deleted. (Inactive and soft-deleted.)

**When**
- `result = dao.get_by_id_and_workspace(db, id=FX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == FX.id`.
2. returns: `result.is_deleted is True`.
3. returns: `result.is_active is False`.

### FCD-GI-13 — the lookup writes nothing
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted.

**When**
- `result = dao.get_by_id_and_workspace(db, id=FD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == FD.id`.
2. nothing written: nothing written.
3. unchanged: unchanged(FD).
4. unchanged: unchanged(F1).
5. re-read FD: `updated_at is None`.


## `DAOFactory.get_active_factories`

### FCD-GA-01 — returns a list of the active live factories of that workspace
- **Rules:** `get_active_factories` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.
3. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [F1.id, F2.id]`.
3. returns: `len(result) == 2`.
4. returns: `isinstance(result[0], Factory)`.

### FCD-GA-02 — a call for the other workspace returns only that workspace's factory
- **Rules:** `get_active_factories` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.
3. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = dao.get_active_factories(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [F9.id]`.

### FCD-GA-03 — a workspace with no factories returns an empty list
- **Rules:** `get_active_factories` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`. (W2 has no factories.)

**When**
- `result = dao.get_active_factories(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### FCD-GA-04 — an unknown workspace id returns an empty list
- **Rules:** `get_active_factories` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = dao.get_active_factories(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### FCD-GA-05 — a soft-deleted factory that still says active is not returned
- **Rules:** `get_active_factories` R1a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (`is_active` is still True — the state `soft_delete` leaves behind.)

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [F1.id]`.

### FCD-GA-06 — a soft-deleted factory with is_active False is not returned
- **Rules:** `get_active_factories` R1a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. FX = factory, `name "Shut Mill"`, `abbreviation "SM"`, but `is_active False`, deleted. (Inactive and soft-deleted.)

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [F1.id]`.

### FCD-GA-07 — a live factory with is_active False is not returned
- **Rules:** `get_active_factories` R2 (Q3)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. FI = factory, `name "Idle Plant"`, `abbreviation "IP"`, but `is_active False`. (Still `is_deleted False`.)

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [F1.id]`.

### FCD-GA-08 — of the four combinations of active and deleted only the active live factory is returned
- **Rules:** `get_active_factories` R1a, R2 (Q3)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FI = factory, `name "Idle Plant"`, `abbreviation "IP"`, but `is_active False`. (Inactive, live.)
2. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (Active, deleted.)
3. FX = factory, `name "Shut Mill"`, `abbreviation "SM"`, but `is_active False`, deleted. (Inactive, deleted.)
4. F4 = factory, `name "Main Plant"`, `abbreviation "MP"`. (Active, live.)

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [F4.id]`.
2. returns: `result[0].is_active is True`.
3. returns: `result[0].is_deleted is False`.

### FCD-GA-09 — a workspace whose factories are all inactive or deleted returns an empty list
- **Rules:** `get_active_factories` R1, R1a, R2 (Q3)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FI = factory, `name "Idle Plant"`, `abbreviation "IP"`, but `is_active False`. (Inactive, live.)
2. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (Active, deleted.)

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FCD-GA-10 — soft-deleted factories in front do not use up a place in the page
- **Rules:** `get_active_factories` R3, R1a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD1 = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted.
2. FD2 = factory, `name "Shut Mill"`, `abbreviation "SM"`, but deleted.
3. L1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
4. L2 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `sorted(ids(result)) == [L1.id, L2.id]`.

### FCD-GA-11 — inactive factories in front do not use up a place in the page
- **Rules:** `get_active_factories` R3, R2 (Q3)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FI1 = factory, `name "Idle Plant"`, `abbreviation "IP"`, but `is_active False`.
2. FI2 = factory, `name "Quiet Works"`, `abbreviation "QW"`, but `is_active False`.
3. L1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
4. L2 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `sorted(ids(result)) == [L1.id, L2.id]`.

### FCD-GA-12 — skip counts only the matching factories
- **Rules:** `get_active_factories` R3, R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted.
2. L1 = factory, `name "Main Plant"`, `abbreviation "MP"`. (The only matching factory.)

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `result == []`.

### FCD-GA-13 — one active live factory behind 100 deleted and 100 inactive ones is returned by the default call
- **Rules:** `get_active_factories` R3, R2 (Q3)
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (two loops over 100 factories each) outside the Conventions vocabulary

**Given**
1. 100 deleted factories D1 … D100, inserted in that order; factory Dk (k = 1 … 100) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 100"), `abbreviation` = `f"O{k:03d}"` (so "O001" … "O100"), and is deleted.
2. 100 inactive factories I1 … I100, inserted in that order after the deleted ones; factory Ik (k = 1 … 100) has `name` = `f"Idle {k:03d}"` (so "Idle 001" … "Idle 100"), `abbreviation` = `f"I{k:03d}"` (so "I001" … "I100"), `is_active False`, and is not deleted.
3. L = factory, `name "Late"`, `abbreviation "LT"`. (Active and live; row number 201 of W1.)

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [L.id]`.

### FCD-GA-14 — default limit returns exactly 100 of 101 active live factories
- **Rules:** `get_active_factories` R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 factories) outside the Conventions vocabulary

**Given**
1. 101 factories N1 … N101, inserted in that order; factory Nk (k = 1 … 101) has `name` = `f"N{k:03d}"` (so "N001" … "N101"), `abbreviation` = `f"A{k:03d}"` (so "A001" … "A101"), and is otherwise the default factory.

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len(set(ids(result))) == 100`.
3. returns: `set(ids(result)) <= {N1.id, …, N101.id}` (the set of all 101 ids).

### FCD-GA-15 — a limit of 500 returns all 101 active live factories
- **Rules:** `get_active_factories` R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 factories) outside the Conventions vocabulary

**Given**
1. 101 factories N1 … N101, inserted in that order; factory Nk (k = 1 … 101) has `name` = `f"N{k:03d}"` (so "N001" … "N101"), `abbreviation` = `f"A{k:03d}"` (so "A001" … "A101"), and is otherwise the default factory.

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id, limit=500)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == [N1.id, …, N101.id]` (all 101 ids, ascending).

### FCD-GA-16 — limit 2 of three factories returns two different factories
- **Rules:** `get_active_factories` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.
3. F3 = factory, `name "South Dock"`, `abbreviation "SD"`.

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `len(set(ids(result))) == 2`.
3. returns: `set(ids(result)) <= {F1.id, F2.id, F3.id}`.

### FCD-GA-17 — the last window is short
- **Rules:** `get_active_factories` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.
3. F3 = factory, `name "South Dock"`, `abbreviation "SD"`.

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in [F1.id, F2.id, F3.id]`.

### FCD-GA-18 — limit 0 returns an empty list
- **Rules:** `get_active_factories` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### FCD-GA-19 — skip equal to the number of matching factories returns an empty list
- **Rules:** `get_active_factories` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### FCD-GA-20 — skip one below the number of matching factories returns one factory
- **Rules:** `get_active_factories` R5, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in [F1.id, F2.id]`.

### FCD-GA-21 — skip past the number of matching factories returns an empty list
- **Rules:** `get_active_factories` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id, skip=5)`.

**Then**
1. returns: `result == []`.

### FCD-GA-22 — negative limit is rejected by the database and nothing changes
- **Rules:** `get_active_factories` R5, Errors (negative `limit`, as `get_by_workspace`)
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `dao.get_active_factories(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(F1).

### FCD-GA-23 — negative skip is rejected by the database and nothing changes
- **Rules:** `get_active_factories` R5, Errors (negative `skip`, as `get_by_workspace`)
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `dao.get_active_factories(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.
6. unchanged: unchanged(F1).

### FCD-GA-24 — factories come back by name, case-insensitive ascending
- **Rules:** `get_active_factories` R6 [BUG-706]
- **Kind:** bug
- **Expect:** xfail BUG-706 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the rows come back in insertion order ["Zulu", "bolt", "apple", "Banana"])
- **Author:** claude — non-strict xfail (physical row order can match the intended order by accident); body as written, only the marker differs

**Given**
1. F1 = factory, `name "Zulu"`, `abbreviation "ZU"`.
2. F2 = factory, `name "bolt"`, `abbreviation "BO"`.
3. F3 = factory, `name "apple"`, `abbreviation "AP"`.
4. F4 = factory, `name "Banana"`, `abbreviation "BA"`.

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [F1.id, F2.id, F3.id, F4.id]`.
2. returns: `names(result) == ["apple", "Banana", "bolt", "Zulu"]`.

### FCD-GA-25 — names that differ only in case come back in id order
- **Rules:** `get_active_factories` R6 [BUG-706]
- **Kind:** bug
- **Expect:** xfail BUG-706 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the rows come back in insertion order [F1, F2, F3, F4, F5])
- **Author:** claude — non-strict xfail (physical row order can match the intended order by accident); body as written, only the marker differs

**Given**
1. F1 = factory, `name "Zulu"`, `abbreviation "ZU"`.
2. F2 = factory, `name "bolt"`, `abbreviation "BO"`. (Lower-case b.)
3. F3 = factory, `name "apple"`, `abbreviation "AP"`.
4. F4 = factory, `name "Bolt"`, `abbreviation "BT"`. (Capital B; the same name as F2 except for the case, on purpose — the only card with such a pair.)
5. F5 = factory, `name "Banana"`, `abbreviation "BA"`.

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [F1.id, F2.id, F3.id, F4.id, F5.id]`.
2. returns: `ids(result) == [F3.id, F5.id, F2.id, F4.id, F1.id]`.

### FCD-GA-26 — a middle window holds the second and third factory by name
- **Rules:** `get_active_factories` R6 [BUG-706], R4
- **Kind:** bug
- **Expect:** xfail BUG-706 (non-strict)
- **Fails today on:** Then 1 (no ordering is requested; the database usually answers in insertion order, giving ["bolt", "apple"], but a page of the physical row order can equal the intended page by accident — non-strict xfail, the assertion is never weakened)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-706")`)

**Given**
1. F1 = factory, `name "Zulu"`, `abbreviation "ZU"`.
2. F2 = factory, `name "bolt"`, `abbreviation "BO"`.
3. F3 = factory, `name "apple"`, `abbreviation "AP"`.
4. F4 = factory, `name "Banana"`, `abbreviation "BA"`.

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `names(result) == ["Banana", "bolt"]`.

### FCD-GA-27 — a factory with machines and sections and one without are each returned once, and nothing is written
- **Rules:** `get_active_factories` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. MA1 = machine of F1, `name "Lathe"`.
3. MA2 = machine of F1, `name "Press"`.
4. SC1 = section of F1, `name "Assembly"`.
5. F2 = factory, `name "North Yard"`, `abbreviation "NY"`. (No machines, no sections.)

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `sorted(ids(result)) == [F1.id, F2.id]`.
3. nothing written: nothing written.
4. unchanged: unchanged(F1).
5. unchanged: unchanged(MA1).
6. unchanged: unchanged(SC1).

### FCD-GA-28 — the active-list query asks the database for an order
- **Rules:** `get_active_factories` R6 [BUG-706]
- **Kind:** bug
- **Expect:** xfail BUG-706
- **Fails today on:** Then 2 (the query has no `ORDER BY`)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_active_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [F1.id]`.
2. statement: the one `SELECT` sent has an `ORDER BY`.


## `DAOFactory.soft_delete`

### FCD-SD-01 — a live factory is marked deleted with the clock value and the acting user
- **Rules:** `soft_delete` R1, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = dao.soft_delete(db, db_obj=F1, deleted_by=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was passed in).
2. re-read F1: `is_deleted is True`.
3. re-read F1: `deleted_at == NOW`.
4. re-read F1: `deleted_by == U2.id`.
5. count: `factories` has exactly 1 row.

### FCD-SD-02 — no other column of the factory is changed by the delete
- **Rules:** `soft_delete` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`, but `updated_by U1.id`.

**When**
- `result = dao.soft_delete(db, db_obj=F1, deleted_by=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was passed in).
2. re-read F1: `name == "Main Plant"`, `abbreviation == "MP"`.
3. re-read F1: `workspace_id == W1.id`, `created_by == U1.id`.
4. re-read F1: `updated_by == U1.id`.
5. re-read F1: `updated_at is not None`.
6. re-read F1: `created_at == created_before`, where `created_before` is `F1.created_at` read after the last Given line and before the call.
7. re-read F1: `is_deleted is True`.

### FCD-SD-03 — the delete does not stamp updated_by
- **Rules:** `soft_delete` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`. (`updated_by None`.)

**When**
- `result = dao.soft_delete(db, db_obj=F1, deleted_by=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was passed in).
2. re-read F1: `updated_by is None`.
3. re-read F1: `updated_at is not None`.
4. re-read F1: `is_deleted is True`.

### FCD-SD-04 — an active factory still says active after the delete
- **Rules:** `soft_delete` R2a (Q1)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`. (`is_active True`.)

**When**
- `result = dao.soft_delete(db, db_obj=F1, deleted_by=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was passed in).
2. re-read F1: `is_deleted is True`.
3. re-read F1: `is_active is True`.

### FCD-SD-05 — a live factory with is_active False is deleted and stays inactive
- **Rules:** `soft_delete` R2a (Q1), R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FI = factory, `name "Idle Plant"`, `abbreviation "IP"`, but `is_active False`. (Still `is_deleted False`.)

**When**
- `result = dao.soft_delete(db, db_obj=FI, deleted_by=U2.id)`.

**Then**
1. returns: `result is FI` (the very object that was passed in).
2. re-read FI: `is_deleted is True`.
3. re-read FI: `is_active is False`.
4. re-read FI: `deleted_at == NOW`, `deleted_by == U2.id`.

### FCD-SD-06 — the machines of the deleted factory are left exactly as they were
- **Rules:** `soft_delete` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. MA1 = machine of F1, `name "Lathe"`.
3. MA2 = machine of F1, `name "Press"`, but `is_active False`.

**When**
- `result = dao.soft_delete(db, db_obj=F1, deleted_by=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was passed in).
2. re-read F1: `is_deleted is True`.
3. unchanged: unchanged(MA1).
4. re-read MA1: `is_deleted is False`, `is_active is True`.
5. re-read MA1: `deleted_at is None`, `deleted_by is None`.
6. unchanged: unchanged(MA2).
7. re-read MA2: `is_deleted is False`, `is_active is False`.
8. count: `machines` has exactly 2 rows.

### FCD-SD-07 — the sections of the deleted factory are left exactly as they were
- **Rules:** `soft_delete` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. SC1 = section of F1, `name "Assembly"`.
3. SC2 = section of F1, `name "Paint"`, but `is_active False`.

**When**
- `result = dao.soft_delete(db, db_obj=F1, deleted_by=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was passed in).
2. re-read F1: `is_deleted is True`.
3. unchanged: unchanged(SC1).
4. re-read SC1: `is_deleted is False`, `is_active is True`.
5. re-read SC1: `deleted_at is None`, `deleted_by is None`.
6. unchanged: unchanged(SC2).
7. re-read SC2: `is_deleted is False`, `is_active is False`.
8. count: `factory_sections` has exactly 2 rows.

### FCD-SD-08 — an already deleted factory gets a new deletion stamp without an error
- **Rules:** `soft_delete` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (`deleted_at T0`, `deleted_by U1.id`.)

**When**
- `result = dao.soft_delete(db, db_obj=FD, deleted_by=U2.id)`.

**Then**
1. returns: `result is FD` (the very object that was passed in).
2. re-read FD: `deleted_at == NOW`.
3. re-read FD: `deleted_by == U2.id`.
4. re-read FD: `is_deleted is True`.

### FCD-SD-09 — the delete is flushed but not committed: visible to the lookups in the session, undone by a rollback
- **Rules:** `soft_delete` R5
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback, a commit spy, and follow-up DAO calls after the When

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.soft_delete(db, db_obj=F1, deleted_by=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was passed in).
2. re-read F1: `is_deleted is True`.
3. returns: after the call, `ids(dao.get_active_factories(db, workspace_id=W1.id)) == [F2.id]`.
4. returns: after the call, `sorted(ids(dao.get_by_workspace(db, workspace_id=W1.id))) == [F1.id, F2.id]`.
5. returns: after the call, `dao.get_by_id_and_workspace(db, id=F1.id, workspace_id=W1.id).is_deleted is True`.
6. re-read F1 after the savepoint rollback: `is_deleted is False`, `is_active is True`.
7. re-read F1 after the savepoint rollback: `deleted_at is None`, `deleted_by is None`.
8. mock called: the `db.commit` spy was never called.

### FCD-SD-10 — a factory of another workspace is deleted all the same
- **Rules:** `soft_delete` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = dao.soft_delete(db, db_obj=F9, deleted_by=U2.id)`.

**Then**
1. returns: `result is F9` (the very object that was passed in).
2. re-read F9: `is_deleted is True`.
3. re-read F9: `deleted_at == NOW`, `deleted_by == U2.id`.
4. re-read F9: `workspace_id == W2.id`.
5. unchanged: unchanged(F1).

### FCD-SD-11 — only that factory row is touched
- **Rules:** `soft_delete` R6, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.
3. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (`deleted_at T0`, `deleted_by U1.id`.)

**When**
- `result = dao.soft_delete(db, db_obj=F1, deleted_by=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was passed in).
2. re-read F1: `is_deleted is True`.
3. unchanged: unchanged(F2).
4. re-read F2: `is_deleted is False`, `updated_at is None`.
5. unchanged: unchanged(FD).
6. re-read FD: `deleted_at == T0`, `deleted_by == U1.id`.
7. nothing written: nothing written.
8. count: `factories` has exactly 3 rows.

### FCD-SD-12 — a deleted_by that is no profile id fails on flush and the factory stays live
- **Rules:** `soft_delete` R7, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `dao.soft_delete(db, db_obj=F1, deleted_by=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"factories_deleted_by_fkey" in str(exc.value.orig)`.
4. unchanged: unchanged(F1).
5. re-read F1: `is_deleted is False`.
6. re-read F1: `deleted_at is None`, `deleted_by is None`.
7. re-read F1: `updated_at is None`.
8. nothing written: nothing written.

### FCD-SD-13 — deleted_by None is stored as NULL and the factory is deleted
- **Rules:** `soft_delete` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = dao.soft_delete(db, db_obj=F1, deleted_by=None)`.

**Then**
1. returns: `result is F1` (the very object that was passed in).
2. re-read F1: `deleted_by is None`.
3. re-read F1: `is_deleted is True`.
4. re-read F1: `deleted_at == NOW`.


## `DAOFactory.restore`

### FCD-RS-01 — a deleted factory is made live again and its deletion stamp is cleared
- **Rules:** `restore` R1, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (`deleted_at T0`, `deleted_by U1.id`.)

**When**
- `result = dao.restore(db, db_obj=FD)`.

**Then**
1. returns: `result is FD` (the very object that was passed in).
2. re-read FD: `is_deleted is False`.
3. re-read FD: `deleted_at is None`.
4. re-read FD: `deleted_by is None`.
5. count: `factories` has exactly 1 row.

### FCD-RS-02 — no other column of the factory is changed by the restore
- **Rules:** `restore` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted.

**When**
- `result = dao.restore(db, db_obj=FD)`.

**Then**
1. returns: `result is FD` (the very object that was passed in).
2. re-read FD: `name == "Old Plant"`, `abbreviation == "OP"`.
3. re-read FD: `workspace_id == W1.id`, `created_by == U1.id`.
4. re-read FD: `created_at == created_before`, where `created_before` is `FD.created_at` read after the last Given line and before the call.
5. re-read FD: `updated_at is not None`.
6. re-read FD: `is_deleted is False`.

### FCD-RS-03 — updated_by keeps the value it had
- **Rules:** `restore` R2a (P2)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but `updated_by U2.id`, deleted. (`deleted_by U1.id`.)

**When**
- `result = dao.restore(db, db_obj=FD)`.

**Then**
1. returns: `result is FD` (the very object that was passed in).
2. re-read FD: `updated_by == U2.id`.
3. re-read FD: `is_deleted is False`.

### FCD-RS-04 — an empty updated_by stays empty: nobody is recorded as having restored
- **Rules:** `restore` R2a (P2)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (`updated_by None`, `deleted_by U1.id`.)

**When**
- `result = dao.restore(db, db_obj=FD)`.

**Then**
1. returns: `result is FD` (the very object that was passed in).
2. re-read FD: `updated_by is None`.
3. re-read FD: `is_deleted is False`.
4. re-read FD: `deleted_by is None`.

### FCD-RS-05 — a factory deleted while active comes back active
- **Rules:** `restore` R3 (Q2)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (`is_active True`.)

**When**
- `result = dao.restore(db, db_obj=FD)`.

**Then**
1. returns: `result is FD` (the very object that was passed in).
2. re-read FD: `is_active is True`.
3. re-read FD: `is_deleted is False`.

### FCD-RS-06 — a deleted factory with is_active False comes back live and still inactive
- **Rules:** `restore` R3 (Q2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FX = factory, `name "Shut Mill"`, `abbreviation "SM"`, but `is_active False`, deleted. (Inactive and soft-deleted.)

**When**
- `result = dao.restore(db, db_obj=FX)`.

**Then**
1. returns: `result is FX` (the very object that was passed in).
2. re-read FX: `is_active is False`.
3. re-read FX: `is_deleted is False`.
4. re-read FX: `deleted_at is None`, `deleted_by is None`.

### FCD-RS-07 — a restored inactive factory is found by the two raw lookups and not by the active list
- **Rules:** `restore` R3 (Q2); `get_active_factories` R2 (Q3)
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — follow-up DAO calls after the When

**Given**
1. FX = factory, `name "Shut Mill"`, `abbreviation "SM"`, but `is_active False`, deleted. (Inactive and soft-deleted.)
2. F2 = factory, `name "Main Plant"`, `abbreviation "MP"`. (Active and live.)

**When**
- `result = dao.restore(db, db_obj=FX)`.

**Then**
1. returns: `result is FX` (the very object that was passed in).
2. re-read FX: `is_deleted is False`, `is_active is False`.
3. returns: after the call, `sorted(ids(dao.get_by_workspace(db, workspace_id=W1.id))) == [FX.id, F2.id]`.
4. returns: after the call, `dao.get_by_id_and_workspace(db, id=FX.id, workspace_id=W1.id).id == FX.id`.
5. returns: after the call, `ids(dao.get_active_factories(db, workspace_id=W1.id)) == [F2.id]`.

### FCD-RS-08 — a factory that is already live, loaded from the database, is left exactly as it is with no UPDATE
- **Rules:** `restore` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`. (Live and active; `updated_at None`.)
2. F1 is loaded from the database before the call: `db.refresh(F1)`. (Without this step the call would issue an UPDATE.)

**When**
- `result = dao.restore(db, db_obj=F1)`.

**Then**
1. returns: `result is F1` (the very object that was passed in).
2. unchanged: unchanged(F1).
3. re-read F1: `updated_at is None`.
4. re-read F1: `is_deleted is False`, `is_active is True`.
5. re-read F1: `deleted_at is None`, `deleted_by is None`.
6. count: `factories` has exactly 1 row.

### FCD-RS-09 — a live but inactive factory, loaded from the database, stays inactive with no UPDATE
- **Rules:** `restore` R4, R3 (Q2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FI = factory, `name "Idle Plant"`, `abbreviation "IP"`, but `is_active False`. (Still `is_deleted False`, no deletion stamp, `updated_at None`.)
2. FI is loaded from the database before the call: `db.refresh(FI)`. (Without this step the call would issue an UPDATE.)

**When**
- `result = dao.restore(db, db_obj=FI)`.

**Then**
1. returns: `result is FI` (the very object that was passed in).
2. unchanged: unchanged(FI).
3. re-read FI: `updated_at is None`.
4. re-read FI: `is_active is False`.
5. re-read FI: `is_deleted is False`.

### FCD-RS-10 — the restore is flushed but not committed: visible to the active list in the session, undone by a rollback
- **Rules:** `restore` R5
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback, a commit spy, and a follow-up DAO call after the When

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (`deleted_at T0`, `deleted_by U1.id`.)
2. F2 = factory, `name "Main Plant"`, `abbreviation "MP"`.
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.restore(db, db_obj=FD)`.

**Then**
1. returns: `result is FD` (the very object that was passed in).
2. re-read FD: `is_deleted is False`.
3. returns: after the call, `sorted(ids(dao.get_active_factories(db, workspace_id=W1.id))) == [FD.id, F2.id]`.
4. re-read FD after the savepoint rollback: `is_deleted is True`.
5. re-read FD after the savepoint rollback: `deleted_at == T0`.
6. re-read FD after the savepoint rollback: `deleted_by == U1.id`.
7. mock called: the `db.commit` spy was never called.

### FCD-RS-11 — a factory of another workspace is restored all the same
- **Rules:** `restore` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. FD9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`, deleted. (A soft-deleted factory of W2.)

**When**
- `result = dao.restore(db, db_obj=FD9)`.

**Then**
1. returns: `result is FD9` (the very object that was passed in).
2. re-read FD9: `is_deleted is False`.
3. re-read FD9: `deleted_at is None`, `deleted_by is None`.
4. re-read FD9: `workspace_id == W2.id`.
5. unchanged: unchanged(F1).

### FCD-RS-12 — a second deleted factory stays deleted and a live one is not touched
- **Rules:** `restore` R6, Side effects
- **Kind:** isolation
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted.
2. FD2 = factory, `name "Shut Mill"`, `abbreviation "SM"`, but deleted. (Same workspace; `deleted_at T0`, `deleted_by U1.id`.)
3. F3 = factory, `name "Main Plant"`, `abbreviation "MP"`. (Live.)

**When**
- `result = dao.restore(db, db_obj=FD)`.

**Then**
1. returns: `result is FD` (the very object that was passed in).
2. re-read FD: `is_deleted is False`.
3. unchanged: unchanged(FD2).
4. re-read FD2: `is_deleted is True`.
5. re-read FD2: `deleted_at == T0`, `deleted_by == U1.id`.
6. unchanged: unchanged(F3).
7. re-read F3: `is_deleted is False`, `updated_at is None`.
8. nothing written: nothing written.
9. count: `factories` has exactly 3 rows.

### FCD-RS-13 — the machine and the section of the restored factory are exactly as they were
- **Rules:** `restore` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted.
2. MA1 = machine of FD, `name "Lathe"`. (The machine row itself is live and active.)
3. SC1 = section of FD, `name "Assembly"`. (The section row itself is live and active.)

**When**
- `result = dao.restore(db, db_obj=FD)`.

**Then**
1. returns: `result is FD` (the very object that was passed in).
2. re-read FD: `is_deleted is False`.
3. unchanged: unchanged(MA1).
4. re-read MA1: `is_deleted is False`, `is_active is True`.
5. re-read MA1: `deleted_at is None`, `deleted_by is None`.
6. unchanged: unchanged(SC1).
7. re-read SC1: `is_deleted is False`, `is_active is True`.
8. re-read SC1: `deleted_at is None`, `deleted_by is None`.
9. nothing written: nothing written.

### FCD-RS-14 — after the restore the machine lookup returns the factory's live machines
- **Rules:** `restore` R7
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — a follow-up call of another DAO (`machine_dao.get_by_factory`) after the When

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted.
2. MA1 = machine of FD, `name "Lathe"`.
3. MA2 = machine of FD, `name "Press"`.
4. MA3 = machine of FD, `name "Drill"`, but `is_deleted True`, `is_active False`. (A soft-deleted machine; it must not come back.)

**When**
- `result = dao.restore(db, db_obj=FD)`.

**Then**
1. returns: `result is FD` (the very object that was passed in).
2. re-read FD: `is_deleted is False`.
3. returns: after the call, `sorted(m.id for m in machine_dao.get_by_factory(db, factory_id=FD.id, workspace_id=W1.id)) == [MA1.id, MA2.id]`.
4. unchanged: unchanged(MA3).
5. count: `machines` has exactly 3 rows.

### FCD-RS-15 — delete then restore gives back the same value in every column except updated_at
- **Rules:** `restore` R8 (Q2); `soft_delete` R5
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — a Given step that runs `dao.soft_delete`, and a snapshot taken before it

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`, but `updated_by U1.id`. (Live and active.)
2. BEFORE = every column of F1, taken now.
3. F1 is soft-deleted through the DAO: `dao.soft_delete(db, db_obj=F1, deleted_by=U2.id)`.

**When**
- `result = dao.restore(db, db_obj=F1)`.

**Then**
1. returns: `result is F1` (the very object that was passed in).
2. unchanged: after re-read, every column of F1 except `updated_at` equals its value in BEFORE.
3. re-read F1: `name == "Main Plant"`, `abbreviation == "MP"`.
4. re-read F1: `updated_by == U1.id`.
5. re-read F1: `is_active is True`.
6. re-read F1: `is_deleted is False`.
7. re-read F1: `deleted_at is None`, `deleted_by is None`.
8. re-read F1: `updated_at is not None`.

### FCD-RS-16 — delete then restore of an inactive factory gives back an inactive factory
- **Rules:** `restore` R8 (Q2), R3 (Q2); `soft_delete` R2a (Q1)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — a Given step that runs `dao.soft_delete`, and a snapshot taken before it

**Given**
1. FI = factory, `name "Idle Plant"`, `abbreviation "IP"`, but `is_active False`, `updated_by U1.id`. (Live and inactive.)
2. BEFORE = every column of FI, taken now.
3. FI is soft-deleted through the DAO: `dao.soft_delete(db, db_obj=FI, deleted_by=U2.id)`.

**When**
- `result = dao.restore(db, db_obj=FI)`.

**Then**
1. returns: `result is FI` (the very object that was passed in).
2. unchanged: after re-read, every column of FI except `updated_at` equals its value in BEFORE.
3. re-read FI: `is_active is False`.
4. re-read FI: `updated_by == U1.id`.
5. re-read FI: `is_deleted is False`.
6. re-read FI: `deleted_at is None`, `deleted_by is None`.

### FCD-RS-17 — a factory is restored although another soft-deleted factory of the workspace has its name and abbreviation
- **Rules:** `restore` R9 (P3)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = factory, `name "Main Plant"`, `abbreviation "MP"`, but deleted.
2. FD2 = factory, `name "Main Plant"`, `abbreviation "MP"`, but deleted. (The same name and abbreviation as FD on purpose; also soft-deleted.)

**When**
- `result = dao.restore(db, db_obj=FD)`.

**Then**
1. returns: `result is FD` (the very object that was passed in).
2. re-read FD: `is_deleted is False`.
3. re-read FD: `name == "Main Plant"`, `abbreviation == "MP"`.
4. unchanged: unchanged(FD2).
5. re-read FD2: `is_deleted is True`.
6. count: `factories` has exactly 2 rows.

### FCD-RS-18 — a factory is restored although a live factory of another workspace has its name and abbreviation
- **Rules:** `restore` R9 (P3)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. FD = factory, `name "Main Plant"`, `abbreviation "MP"`, but deleted.
2. F9 = factory, `name "Main Plant"`, `abbreviation "MP"`, but `workspace_id W2.id`. (The same name and abbreviation as FD on purpose; live, in W2.)

**When**
- `result = dao.restore(db, db_obj=FD)`.

**Then**
1. returns: `result is FD` (the very object that was passed in).
2. re-read FD: `is_deleted is False`.
3. re-read FD: `name == "Main Plant"`, `abbreviation == "MP"`.
4. unchanged: unchanged(F9).
5. re-read F9: `is_deleted is False`, `updated_at is None`.

### FCD-RS-19 — the database refuses a restore whose name is used by another live factory of the workspace
- **Rules:** `restore` R9a [BUG-895], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-895
- **Fails today on:** Then 1 (no error is raised: the table has no unique index, so the restore succeeds and two live factories share the name)

**Given**
1. FD = factory, `name "Main Plant"`, `abbreviation "MP"`, but deleted. (`deleted_at T0`, `deleted_by U1.id`.)
2. F2 = factory, `name "main plant"`, `abbreviation "XX"`. (Live; the name is FD's name in lower case — the collision on purpose. The abbreviation is different.)

**When**
- `dao.restore(db, db_obj=FD)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, UniqueViolation)`.
3. re-read FD: `is_deleted is True`.
4. re-read FD: `deleted_at == T0`, `deleted_by == U1.id`.
5. unchanged: unchanged(F2).

### FCD-RS-20 — the database refuses a restore whose abbreviation is used by another live factory of the workspace
- **Rules:** `restore` R9a [BUG-895], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-895
- **Fails today on:** Then 1 (no error is raised: the table has no unique index, so the restore succeeds and two live factories share the abbreviation)

**Given**
1. FD = factory, `name "Old Site"`, `abbreviation "MP"`, but deleted. (`deleted_at T0`, `deleted_by U1.id`.)
2. F2 = factory, `name "New Site"`, `abbreviation " mp"`. (Live; the abbreviation is one space followed by lower-case mp — FD's abbreviation after trimming and lower-casing, the collision on purpose. The name is different.)

**When**
- `dao.restore(db, db_obj=FD)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, UniqueViolation)`.
3. re-read FD: `is_deleted is True`.
4. re-read FD: `deleted_at == T0`, `deleted_by == U1.id`.
5. unchanged: unchanged(F2).


## Inherited `BaseDAO` methods on `Factory`

### FCD-INH-01 — create with a dict of the three required values stores a factory with the model defaults
- **Rules:** inherited R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No factories exist.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "Main Plant", "abbreviation": "MP"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name == "Main Plant"`, `abbreviation == "MP"`, `workspace_id == W1.id`.
3. re-read the returned row: `is_active is True`, `is_deleted is False`.
4. re-read the returned row: `created_at is not None`.
5. re-read the returned row: `created_by is None`, `updated_by is None`.
6. re-read the returned row: `updated_at is None`.
7. re-read the returned row: `deleted_at is None`, `deleted_by is None`.
8. count: `factories` has exactly 1 row.

### FCD-INH-02 — create with a FactoryCreate schema fails on flush and saves no factory
- **Rules:** inherited R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No factories exist.

**When**
- `dao.create(db, obj_in=FactoryCreate(name="Main Plant", abbreviation="MP"))`. (The schema has no `workspace_id`.)

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `"workspace_id" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. count: `factories` has exactly 0 rows.

### FCD-INH-03 — create with a dict that has no abbreviation fails on flush and saves no factory
- **Rules:** inherited R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No factories exist.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": "Main Plant"})`. (`abbreviation` is not in the dict.)

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `"abbreviation" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. count: `factories` has exactly 0 rows.

### FCD-INH-04 — create with a workspace_id that is no workspace id fails on flush and saves no factory
- **Rules:** inherited R2, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. No factories exist.

**When**
- `dao.create(db, obj_in={"workspace_id": MISSING, "name": "Main Plant", "abbreviation": "MP"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"factories_workspace_id_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. count: `factories` has exactly 0 rows.

### FCD-INH-05 — update with a FactoryUpdate that sets only the name changes only the name
- **Rules:** inherited R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = dao.update(db, db_obj=F1, obj_in=FactoryUpdate(name="B"))`. `abbreviation` is not sent.

**Then**
1. returns: `result.id == F1.id`.
2. re-read F1: `name == "B"`.
3. re-read F1: `abbreviation == "MP"`.
4. re-read F1: `is_active is True`, `is_deleted is False`.

### FCD-INH-06 — update with an explicit null name changes only the abbreviation
- **Rules:** inherited R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = dao.update(db, db_obj=F1, obj_in=FactoryUpdate(name=None, abbreviation="U2"))`.

**Then**
1. returns: `result.id == F1.id`.
2. re-read F1: `abbreviation == "U2"`.
3. re-read F1: `name == "Main Plant"`.

### FCD-INH-07 — update with a dict can switch is_active off and changes nothing else
- **Rules:** inherited R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = dao.update(db, db_obj=F1, obj_in={"is_active": False})`.

**Then**
1. returns: `result.id == F1.id`.
2. re-read F1: `is_active is False`.
3. re-read F1: `is_deleted is False`.
4. re-read F1: `name == "Main Plant"`, `abbreviation == "MP"`.
5. re-read F1: `deleted_at is None`, `deleted_by is None`.

### FCD-INH-08 — get returns the factory of another workspace
- **Rules:** inherited R4 (Q4)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = dao.get(db, F9.id)`.

**Then**
1. returns: `result.id == F9.id`.
2. returns: `result.workspace_id == W2.id`.
3. returns: `result.name == "Far Depot"`.

### FCD-INH-09 — get returns a soft-deleted factory
- **Rules:** inherited R4 (Q4)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted.

**When**
- `result = dao.get(db, FD.id)`.

**Then**
1. returns: `result.id == FD.id`.
2. returns: `result.is_deleted is True`.

### FCD-INH-10 — get returns a soft-deleted factory of another workspace
- **Rules:** inherited R4 (Q4)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`, deleted. (A soft-deleted factory of W2.)

**When**
- `result = dao.get(db, FD9.id)`.

**Then**
1. returns: `result.id == FD9.id`.
2. returns: `result.is_deleted is True`.
3. returns: `result.workspace_id == W2.id`.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview "Integration-only behavior": `skip >= 0`, `1 <= limit <= 1000` | `GET /factories/` (endpoint) | 422 for `skip=-1`, `limit=0`, `limit=1001`. Here the DAO lets Postgres reject negatives (FCD-GW-19, GW-20, GA-22, GA-23) and `limit=0` returns `[]` by rule (FCD-GW-15, GA-18). |
| FU-1 — the "restore factory" feature (`restore` has no caller) | factory manager / service / endpoint (feature to build) | 404 for a missing / other-workspace factory; the answer for a factory that is not deleted; who restored (P2); 409 when the name or abbreviation now belongs to another live factory (P3); an inactive factory comes back inactive (Q2). Here the DAO restores whatever it is given (FCD-RS-08, RS-09, RS-11), records nobody (FCD-RS-03, RS-04) and checks no name (FCD-RS-17, RS-18). |
| FU-2 — factories and machines differ on `is_active` at delete / restore | product decision / machine DAO | Whether to align them. No card. |
| FU-3 (Q4) — the production-line code uses the unscoped `get` and compares the workspace afterwards | production line manager review | Foreign factory rejected without confirming it exists; soft-deleted factory refused. Here only "the raw lookup stays raw" (FCD-INH-08 … INH-10). |
| FU-4 (Q3) — what an inactive-but-live factory means | product decision / inventory manager | The workspace-wide incoming-stock summary against the per-factory one. Here only the list's own filter (FCD-GA-07 … GA-09). |
| FU-5 — the caller of `get_active_factories` passes `limit=500` (BUG-709) | inventory manager spec | No silent cap of the summary. Here the paging itself (FCD-GA-14, GA-15). |
| Cross-spec note — `search_factories` and the duplicate checks read through `get_by_workspace` (BUG-893, BUG-898, BUG-899) | factory manager spec / cases (`FAC-…`) | Cap of the duplicate checks, page before filter, display order. Here the raw lookup's default limit and raw result are correct by rule (FCD-GW-08, GW-11). |
| `soft_delete` R3, `restore` R7 — stock rows (`inventory`) and the other seven tables that point at a factory | integration tests of `DELETE /factories/{id}/` and of the future restore endpoint (or this spec once it gives those models' columns — Spec gap 2) | Each kind of row is left untouched by both writes and none blocks the delete. Here machines and sections only (FCD-SD-06, SD-07, RS-13, RS-14). |
| `get_active_factories` R6 — strict proof of the `ORDER BY` for a paged window | a test with a statement recorder (emitted SQL has `ORDER BY lower(name), id`), e.g. in the incoming-summary tests | Done here after finishing: FCD-GA-28 records the statement and is strict (it asserts only that an `ORDER BY` is present, not its columns); FCD-GA-24, GA-25, GA-26 are non-strict. |
| Inherited `get`, `get_multi`, `create`, `update`, `remove` — generic behaviour (including "flushed, not committed" of `create` / `update`, and `get` for a missing id) | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not repeated here; only what the `Factory` model and its schemas change has cards (FCD-INH-01 … INH-10). |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Status line | *(Closed 2026-10-16.)* The spec was IN REVIEW when the cards were designed; P1, P2, P3, Q1, Q2, Q3, Q4 carried suggested answers only. | Designed on the suggestions by instruction of the project owner. All seven were accepted as suggested (decided by Claude under the reviewer's delegation (2026-10-16)); the spec is APPROVED and no card changed. |
| 2 | `soft_delete` R3, `restore` R7; Model facts | The rules name "machines, sections, stock", but the Model facts give the required columns of `Machine` and `FactorySection` only, and the spec itself says the stock case was not run. | No stock-row card; deferred. |
| 3 | `restore` R2a ("The clock is not read") | No observable effect is given beyond `deleted_at` becoming `None`; `utcnow` is patched by the helper file, and a card may not patch or inspect it. | No card of its own. Indirectly covered: every restore card asserts `deleted_at is None`, and no column takes the value NOW. |
| 4 | Inherited R3 | The return value of `update` (same instance or not) is not restated; the sentence "such a factory then drops out of `get_active_factories`" is a composition of two rules. | FCD-INH-05 … INH-07 assert `result.id == F1.id` only. The "drops out" sentence has no card of its own: FCD-INH-07 shows the flag is stored, FCD-GA-07 that such a row is left out. |
| 5 | Inherited Errors rows; `soft_delete` Errors row | "Detail message: — (not asserted)", while the rules name the column (`NotNullViolation` on `workspace_id` / `abbreviation`) and the constraints. | Designed as a loose check: the column or constraint name is contained in `str(exc.value.orig)` (FCD-INH-02, INH-03, INH-04, SD-12). Drop those four lines if the text is not meant to be asserted. |
| 6 | `get_active_factories` R6 × BUG-895; Notes "Active-list order" | The tie-break example needs "bolt" and "Bolt" live in one workspace, which the BUG-895 name index will refuse. | FCD-GA-25 keeps the spec's five names; once BUG-895 is fixed its setup fails and the card must be retired or rebuilt. FCD-GA-24 (no such pair) carries the order rule on its own. |
| 7 | Notes "Raw-list order" / "Active-list order" | The spec calls both recipes verified and strict, but says nothing about windows; the factory manager's window cards of the same kind had to be made non-strict after verification. The BUG-100 recipe is verified for two rows only. | The three BUG-100 cards use exactly the verified two rows and stay strict (the windows are of size 1). The one BUG-706 window card (FCD-GA-26) is non-strict. If FCD-GW-23 or GW-24 ever passes today, it must become non-strict too. **Outcome:** they did pass by accident; all order cards are non-strict now, FCD-GW-26 / GA-28 are the strict proof. |
| 8 | `restore` R1 / R4 | Not specified: a factory in a mixed state (`is_deleted True` with an empty stamp, or `is_deleted False` with a stamp left over). | No card. |
| 9 | Model facts (`created_at`) | Whether `created_at` is naive or timezone-aware is not stated. | Not blocking: compared with a value read before the call (FCD-SD-02, RS-02); no Given sets it. |
| 10 | `restore` R9a | Not stated: which of the two rows a collision on *both* name and abbreviation reports, and whether the constraint names are to be asserted. | One card per field; only `IntegrityError` and `UniqueViolation` are asserted. |
| 11 | `get_by_workspace` R4 ("at least 99 of them deleted") | The exact content of the page depends on the order, which is BUG-100. | FCD-GW-08 asserts `len == 100` and `>= 99` deleted, as the rule words it. |
| 12 | Notes ("every parameter after `db` is keyword-only — a positional call raises `TypeError`") | Stated as a note, not as a rule of any callable. | No card. |
| 13 | `get_active_factories` R6 (tie-break "then `id` ascending") × BUG-895 | The `id` tie-break only decides between two returned factories whose names are equal under `lower()`. `get_active_factories` returns only live factories of one workspace, and two live factories of one workspace with names equal under `lower()` are either a case-only pair ("bolt" / "Bolt") or an exact duplicate — both refused by the BUG-895 index (lower-case and trimmed: anything equal under `lower()` is also equal after trimming). Names differing only in surrounding whitespace (" apple" / "apple") do not tie under `lower()`, so they test the name order, not the tie-break. | No second tie-break card can be designed (checked 2026-10-16). Today the tie-break is observable only through FCD-GA-25 (non-strict); once BUG-895 is fixed it cannot be observed at all in this method and needs no card — the strict alarm for the missing order is FCD-GA-28. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_workspace` | Returns (a list of `Factory`) | FCD-GW-01 |
| `get_by_workspace` | R1 | FCD-GW-01, GW-02, GW-03, GW-04, GW-21 |
| `get_by_workspace` | R2 | FCD-GW-06, GW-07, GW-08, GW-11, GW-12, GW-13, GW-14, GW-15, GW-16, GW-17, GW-18, GW-19, GW-20, GW-23 (xfail), GW-24 (xfail) |
| `get_by_workspace` | R3 [BUG-100] | FCD-GW-22, GW-23, GW-24 (non-strict xfail); GW-26 (strict xfail, statement recorder); GW-21 (pass companion) |
| `get_by_workspace` | R4 (P1) | FCD-GW-05, GW-06, GW-07, GW-08, GW-10 |
| `get_by_workspace` | R5 | FCD-GW-09, GW-10 |
| `get_by_workspace` | R6 | FCD-GW-25 |
| `get_by_workspace` | Errors row 1 (negative `limit`) | FCD-GW-19 |
| `get_by_workspace` | Errors row 2 (negative `skip`) | FCD-GW-20 |
| `get_by_id_and_workspace` | R1 | FCD-GI-01, GI-02, GI-05 |
| `get_by_id_and_workspace` | R2 | FCD-GI-03, GI-04, GI-08, GI-10 |
| `get_by_id_and_workspace` | R3 | FCD-GI-06, GI-07 |
| `get_by_id_and_workspace` | R4 (P1) | FCD-GI-09, GI-12 |
| `get_by_id_and_workspace` | R5 | FCD-GI-11, GI-12 |
| `get_by_id_and_workspace` | Errors (none) / Side effects (none) | FCD-GI-13; GI-03, GI-06, GI-07 are the "no error" paths |
| `get_active_factories` | Returns (a list of `Factory`) | FCD-GA-01 |
| `get_active_factories` | R1 | FCD-GA-01, GA-02, GA-03, GA-04, GA-09 |
| `get_active_factories` | R1a | FCD-GA-05, GA-06, GA-08, GA-09, GA-10 |
| `get_active_factories` | R2 (Q3) | FCD-GA-07, GA-08, GA-09, GA-11, GA-13; FCD-RS-07 |
| `get_active_factories` | R3 | FCD-GA-10, GA-11, GA-12, GA-13 |
| `get_active_factories` | R4 | FCD-GA-14, GA-15, GA-16, GA-17, GA-20, GA-26 (xfail) |
| `get_active_factories` | R5 | FCD-GA-12, GA-18, GA-19, GA-20, GA-21, GA-22, GA-23 |
| `get_active_factories` | R6 [BUG-706] | FCD-GA-24, GA-25, GA-26 (non-strict xfail); GA-28 (strict xfail, statement recorder) |
| `get_active_factories` | R7 | FCD-GA-27 |
| `get_active_factories` | Errors (negative `limit`) | FCD-GA-22 |
| `get_active_factories` | Errors (negative `skip`) | FCD-GA-23 |
| `soft_delete` | R1 | FCD-SD-01, SD-05 |
| `soft_delete` | R2 | FCD-SD-02, SD-03 |
| `soft_delete` | R2a (Q1) | FCD-SD-04, SD-05; FCD-RS-16 |
| `soft_delete` | R3 | FCD-SD-06, SD-07 (stock rows: deferred, Spec gap 2) |
| `soft_delete` | R4 | FCD-SD-08 |
| `soft_delete` | R5 | FCD-SD-01, SD-09; "`restore` undoes the delete": FCD-RS-15, RS-16 |
| `soft_delete` | R6 | FCD-SD-10, SD-11 |
| `soft_delete` | R7 | FCD-SD-12 |
| `soft_delete` | R8 | FCD-SD-13 |
| `soft_delete` | Errors row 1 (`deleted_by` references no profile) | FCD-SD-12 |
| `soft_delete` | Side effects (one row, no other table, no commit) | FCD-SD-09, SD-11 |
| `restore` | R1 | FCD-RS-01 |
| `restore` | R2 | FCD-RS-02 |
| `restore` | R2a (P2) | FCD-RS-03, RS-04 ("the clock is not read": no card, Spec gap 3) |
| `restore` | R3 (Q2) | FCD-RS-05, RS-06, RS-07, RS-09, RS-16 |
| `restore` | R4 | FCD-RS-08, RS-09 |
| `restore` | R5 | FCD-RS-01, RS-10 |
| `restore` | R6 | FCD-RS-11, RS-12 |
| `restore` | R7 | FCD-RS-13, RS-14 (stock rows: deferred, Spec gap 2) |
| `restore` | R8 (Q2) | FCD-RS-15, RS-16 |
| `restore` | R9 (P3) | FCD-RS-17, RS-18 |
| `restore` | R9a [BUG-895] | FCD-RS-19 (name), RS-20 (abbreviation) — strict xfail |
| `restore` | Errors row 1 [BUG-895] (`IntegrityError`, `UniqueViolation`) | FCD-RS-19, RS-20 (xfail) |
| `restore` | Side effects (at most one row, no UPDATE when live, no other table, no commit) | FCD-RS-08, RS-09, RS-10, RS-12, RS-13 |
| inherited | R1 | FCD-INH-01 |
| inherited | R2 | FCD-INH-02, INH-03, INH-04 |
| inherited | R3 | FCD-INH-05, INH-06, INH-07 ("drops out of `get_active_factories`": INH-07 + FCD-GA-07, Spec gap 4) |
| inherited | R4 (Q4) | FCD-INH-08, INH-09, INH-10 |
| inherited | Errors row 1 (`NotNullViolation`) | FCD-INH-02, INH-03 |
| inherited | Errors row 2 (`ForeignKeyViolation`) | FCD-INH-04 |
| BUG-100 | `get_by_workspace` R3 | FCD-GW-22, GW-23, GW-24 (non-strict); FCD-GW-26 (strict) |
| BUG-706 | `get_active_factories` R6 | FCD-GA-24, GA-25, GA-26 (non-strict); FCD-GA-28 (strict) |
| BUG-895 | `restore` R9a | FCD-RS-19, RS-20 |
