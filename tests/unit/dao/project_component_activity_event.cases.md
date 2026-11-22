# Test cases — `app/dao/project_component_activity_event.py`

> **Spec:** `tests/unit/dao/project_component_activity_event.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-01; nothing open). Q1 is the owner's answer, Q2 was decided by Claude under the reviewer's delegation; neither moves a rule of this DAO.
> **Revision:** 1 — the spec did not change. Additive, from `project_component_activity_event.verify.md` (case-missing Findings 1 … 4; recipes R-1 … R-4): R-1 → PCE-G-31; R-2 → PCE-G-32; R-3 → PCE-G-30 Then 5, 6 (the old lines 5 … 7 move to 7 … 9) and PCE-G-33; R-4 → PCE-G-30 Then 10. No ID retired.
> **Counts:** 33 cases · 33 expected-to-pass · 0 expected-to-fail (bugs) · 9 deferred

## Reviewer summary
- **Depth:** lighter target (skill step 1a): one list read, no write of its own, and no money, stock or order state written.
- **Per callable:** `get_by_component` 33.
- **Expected-to-fail:** none. This module's query has its full order, and no rule here carries a bug tag.
- **Notable design choices:**
  - "Writes nothing" is PCE-G-30, with PCE-G-33 for the empty result: a newer row added and not flushed must stay pending and alone in the session, no write statement is sent, and no lock clause. Readers have no commit spy.
  - Ties both ways: one tie card with no update (the expected row is physically last), one with the lower row updated (physically first). Neither alone rules out physical order.
  - Every filter negative puts the other row where it would change the result: newer than the expected row, or under `limit=1`.
  - PCE-G-15, G-16 put a hidden row ahead of the skipped row with `skip=1, limit=1`: filtering after paging would count it as skipped.
  - The R4 card deletes the parent with raw SQL in its Given, so it proves the cascade and not who may delete.
  - PCE-G-31 gives each tied row its own `event_type`, `description` and performer, so no other column can pass for `id`. PCE-G-32 has an older row with a higher id, one microsecond apart.
  - PCE-G-30 forbids `project_components` by name, so neither a join nor a subquery can hide a closed parent's log. The check rests on the Branch map line "no join to the parent", not on a numbered rule alone.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `PCE` = `app/dao/project_component_activity_event.py`. `G` = get_by_component.

**Actors and fixed values.**
- `dao` = the singleton `project_component_activity_event_dao` (`from app.dao.project_component_activity_event import project_component_activity_event_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `ProjectComponentActivityEvent` = `app.models.project_component_activity_event.ProjectComponentActivityEvent`. `datetime`, `timedelta` = the `datetime` module's classes. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.
- T1 = `datetime(2026, 3, 4, 10, 0, 0)`, T2 = `datetime(2026, 3, 5, 10, 0, 0)`, T3 = `datetime(2026, 3, 6, 10, 0, 0)`.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces and the profile from `make_workspace`, `make_profile` of `tests/unit/factories.py`; the rest built directly, add + flush):
  - W1, W2 = two `workspaces` rows. U1 = a `profiles` row.
  - F1 = `factories` row (`Factory`): `workspace_id W1.id`, `name "Factory One"`, `abbreviation "F1"`. F9 = the same, but `workspace_id W2.id`, `name "Factory Nine"`, `abbreviation "F9"`.
  - PJ1 = `projects` row (`Project`): `workspace_id W1.id`, `factory_id F1.id`, `name "Project One"`, `description "Main"`. PJ9 = the same, but `workspace_id W2.id`, `factory_id F9.id`, `name "Project Nine"`.
  - CP1 = `project_components` row (`ProjectComponent`): `workspace_id W1.id`, `project_id PJ1.id`, `name "Roof"`. CP2 = the same, but `name "Wall"`. CP9 = the same as CP1, but `workspace_id W2.id`, `project_id PJ9.id`, `name "Floor"`.
- **event** = `project_component_activity_events` row built with `ProjectComponentActivityEvent`: `workspace_id W1.id`, `project_component_id CP1.id`, `event_type "attachment_added"`, `description "Logged"`; `metadata_json` and `performed_by` are not passed. The card always gives `created_at`; after the word "but" it lists every other column that differs. `metadata_json None` means the keyword is passed with the value `None`.
- No `project_component_activity_events` row exists unless the card's Given lists it.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned; the order is part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `project_component_activity_events` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- **stored_json(X)** = `db.scalar(text("SELECT metadata::text FROM project_component_activity_events WHERE id = :i"), {"i": X.id})` — `None` for SQL `NULL`, `"null"` for JSON `null`.
- `pending:` lines check the row P after the call, on the object itself; `db.new`, `db.dirty`, `db.deleted` are read from the session after the call, before anything expires it.
- `raises: DataError` = `sqlalchemy.exc.DataError`. Wrap the call: `with pytest.raises(DataError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards (the savepoint is rolled back).
- Further `raises:` lines of the same card are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `project_component_activity_events`; `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.


## `ProjectComponentActivityEventDAO.get_by_component`

### PCE-G-01 — returns a list of the project component's rows of every event type
- **Rules:** `get_by_component` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `event_type "attachment_added"`.
2. B = event, `created_at T2`, but `event_type "work_order_item_used"`.
3. C = event, `created_at T3`, but `event_type "work_order_completed"`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.
3. returns: `isinstance(result[0], ProjectComponentActivityEvent)`.

### PCE-G-02 — a newer row of another project component is not returned and takes no place in the page
- **Rules:** `get_by_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. C = event, `created_at T2`, but `project_component_id CP2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PCE-G-03 — the right project component under another workspace returns an empty list
- **Rules:** `get_by_component` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PCE-G-04 — a newer W2 row on the same project component is not returned and takes no place in the page
- **Rules:** `get_by_component` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. Z = event, `created_at T2`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PCE-G-05 — a W2 row on a project component of W1 is returned for W2: only the row's workspace is compared
- **Rules:** `get_by_component` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = event, `created_at T1`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [Z.id]`.

### PCE-G-06 — a W2 row on a project component of W1 is not returned for W1
- **Rules:** `get_by_component` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = event, `created_at T1`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCE-G-07 — an unknown project component id returns an empty list
- **Rules:** `get_by_component` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_component(db, project_component_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCE-G-08 — project_component_id=0 returns an empty list
- **Rules:** `get_by_component` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_component(db, project_component_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCE-G-09 — an unknown workspace returns an empty list
- **Rules:** `get_by_component` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PCE-G-10 — a project component with no events returns an empty list
- **Rules:** `get_by_component` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCE-G-11 — after a hard delete of the project component its rows are gone and the call returns an empty list
- **Rules:** `get_by_component` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.
3. C = event, `created_at T3`, but `project_component_id CP2.id`.
4. `db.execute(text("DELETE FROM project_components WHERE id = :i"), {"i": CP1.id})`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.
2. count: `db.scalar(text("SELECT count(*) FROM project_component_activity_events WHERE project_component_id = :i"), {"i": CP1.id}) == 0`.
3. count: `db.scalar(text("SELECT count(*) FROM project_component_activity_events WHERE project_component_id = :i"), {"i": CP2.id}) == 1`.

### PCE-G-12 — rows are ordered by created_at descending, then id descending
- **Rules:** `get_by_component` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T3`.
3. C = event, `created_at T1`.
4. D = event, `created_at T3`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [D.id, B.id, A.id, C.id]`.

### PCE-G-13 — on a created_at tie with no update the higher id comes first
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### PCE-G-14 — on a created_at tie the higher id still comes first after the lower row is updated
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T2`.
3. `A.description = "Edited"`, then `db.flush()`.
4. `db.expire_all()`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### PCE-G-15 — a row of another component ahead of the skipped row does not count as skipped
- **Rules:** `get_by_component` R1, R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.
3. Z = event, `created_at T3`, but `project_component_id CP2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PCE-G-16 — a W2 row ahead of the skipped row does not count as skipped
- **Rules:** `get_by_component` R2, R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.
3. Z = event, `created_at T3`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PCE-G-17 — with the default limit 101 rows give the newest 100
- **Rules:** `get_by_component` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 events E1 … E101, built with `add_all`: Ek = event, `created_at` = `T1 + timedelta(minutes=k)`. `newest_first` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest_first[:100]`.

### PCE-G-18 — limit=1000 returns all 101 rows
- **Rules:** `get_by_component` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 events E1 … E101, built with `add_all`: Ek = event, `created_at` = `T1 + timedelta(minutes=k)`. `newest_first` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == newest_first`.

### PCE-G-19 — the first window holds the two newest rows, sorted before paging
- **Rules:** `get_by_component` R6, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T3`.
3. C = event, `created_at T1`.
4. D = event, `created_at T3`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `ids(result) == [D.id, B.id]`.

### PCE-G-20 — the next window holds the two other rows: no repeat, no gap
- **Rules:** `get_by_component` R6, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T3`.
3. C = event, `created_at T1`.
4. D = event, `created_at T3`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `ids(result) == [A.id, C.id]`.

### PCE-G-21 — limit=0 returns an empty list
- **Rules:** `get_by_component` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PCE-G-22 — limit=1 returns the newest row
- **Rules:** `get_by_component` R7, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### PCE-G-23 — skip equal to the number of rows returns an empty list
- **Rules:** `get_by_component` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PCE-G-24 — skip past the number of rows returns an empty list
- **Rules:** `get_by_component` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### PCE-G-25 — skip one below the number of rows returns the oldest row
- **Rules:** `get_by_component` R7, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PCE-G-26 — a negative limit is rejected by Postgres
- **Rules:** `get_by_component` R8, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PCE-G-27 — a negative skip is rejected by Postgres
- **Rules:** `get_by_component` R8, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### PCE-G-28 — a row comes back as stored, with its performer
- **Rules:** `get_by_component` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T2`, but `event_type "work_order_item_used"`, `description "Step done"`, `metadata_json {"status": "DONE", "note": "Shift 1"}`, `performed_by U1.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].workspace_id == W1.id`, `result[0].project_component_id == CP1.id`, `result[0].event_type == "work_order_item_used"`.
3. returns: `result[0].description == "Step done"`, `result[0].created_at == T2`.
4. returns: `result[0].metadata_json == {"status": "DONE", "note": "Shift 1"}`.
5. returns: `result[0].performer.id == U1.id`.

### PCE-G-29 — SQL NULL and JSON null metadata both read back as None, and no performer gives None
- **Rules:** `get_by_component` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`, but `metadata_json None`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.
2. returns: `result[0].metadata_json is None`.
3. returns: `result[1].metadata_json is None`.
4. re-read A: `stored_json(A) is None`.
5. re-read B: `stored_json(B) == "null"`.
6. returns: `result[0].performer is None`.

### PCE-G-30 — writes nothing: a newer pending row stays pending and is not returned
- **Rules:** `get_by_component` R9, Side effects, Overview, R1, Branch map
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. `P = ProjectComponentActivityEvent(workspace_id=W1.id, project_component_id=CP1.id, event_type="attachment_added", description="Pending", created_at=T2)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. nothing written: nothing written.
5. pending: `len(db.new) == 1`.
6. pending: `not db.dirty and not db.deleted`.
7. unchanged: unchanged(A).
8. statement: `written == []`.
9. statement: `"FOR" not in sql.upper().split()`.
10. statement: `"project_components" not in sql`.

### PCE-G-31 — on a created_at tie id decides, not event_type, description or performer
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `U2`, `U3` = two more `profiles` rows (`make_profile`), made after U1, in that order.
2. A = event, `created_at T2`, but `event_type "b"`, `description "b"`, `performed_by U2.id`.
3. B = event, `created_at T2`, but `event_type "a"`, `description "a"`, `performed_by U1.id`.
4. C = event, `created_at T2`, but `event_type "c"`, `description "c"`, `performed_by U3.id`.
5. `db.expire_all()`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.


### PCE-G-32 — one microsecond inside one day decides the order, against id
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2 + timedelta(microseconds=1)`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_component(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.


### PCE-G-33 — writes nothing: with an empty result the pending row is still alone in the session
- **Rules:** `get_by_component` R9, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. `P = ProjectComponentActivityEvent(workspace_id=W1.id, project_component_id=CP1.id, event_type="attachment_added", description="Pending", created_at=T2)`
3. `db.add(P)` (not flushed).

**When**
- `result = dao.get_by_component(db, project_component_id=CP2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.
2. pending: `len(db.new) == 1`.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| R2 — the endpoint answers 404 for a component of another workspace before this method runs | `GET /project-components/{id}/activity/` (BUG-1198) | This DAO returns the row for its own workspace; the 404 is what keeps it out of a response. |
| FU-1 — BUG-1192 (HR-16): `log_event` refuses another workspace's project component, 404 `Project component with ID <id> not found`, nothing written | `ProjectComponentActivityManager.log_event` | The rule and the tag belong to that spec. No card here. |
| FU-2, Q1 — BUG-1196: a component with history is refused with 400 and the blocker list, before anything is written. Also the `work_orders` and misc-cost links today's delete clears | `ProjectComponentService.delete_component` | The rule and the tag belong to that spec. Here R4 only checks that the rows go with the component. Stock history. |
| FU-2, Q1 — BUG-1197: the refusal list is shown to the user | Frontend delete flow, `ProjectsPage.tsx` (note in `docs/testing/bugs.md`) | No unit case in this pipeline. |
| FU-3, Q2 — BUG-1198: new `GET /project-components/{id}/activity/`, with access check and response schema | Project component endpoint and service | No card here: R1–R9 stay as they are. |
| `skip >= 0`, `1 <= limit <= 1000` (HR-7) | `GET /project-components/{id}/activity/` (BUG-1198) | Here negative values reach Postgres. |
| `ProjectComponentActivityManager.list_events` adds the performer's profile; nothing calls it | `ProjectComponentActivityManager.list_events` | Not a rule of this DAO. |
| Generic behavior of inherited `BaseDAO` methods | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not specified here. |
| Notes: keyword-only parameters | none (no rule) | Spec gap 1. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes ("every parameter after `db` is keyword-only") | Stated as a note, not as a rule. | No card, as in `machine_activity_event.cases.md`. |
| 2 | Overview ("takes no lock") | Stands outside the numbered rules. | Covered anyway, as the Overview row of the matrix, by the "writes nothing" card. Its check looks for the word `FOR`, so it covers every lock form. Drop the line if it is not meant as a contract. |
| 3 | `get_by_component` R4 | **Stock.** The rule names `ProjectComponentService.delete_component`, which is not this DAO's, and which changes under its own bug. | The card runs a raw `DELETE` in the Given, so it proves the database's cascade only. It says nothing about who may delete. |
| 4 | `get_by_component` R1, R2, R6 | Filtering before paging is not stated in a rule: R5 says it of the order only, and the Review section cites HR-5 only as "not a new line". | PCE-G-15, G-16 rest on R1, R2 ("never returned") and HR-5. |
| 5 | `get_by_component` Errors | The table gives `pgcode` and message, no `psycopg2.errors` class. | The error cards assert those two only. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_component` | Returns | PCE-G-01 |
| `get_by_component` | R1 | PCE-G-01, PCE-G-02, PCE-G-15, PCE-G-30 |
| `get_by_component` | R2 | PCE-G-03, PCE-G-04, PCE-G-05, PCE-G-06, PCE-G-16 |
| `get_by_component` | R3 | PCE-G-07, PCE-G-08, PCE-G-09, PCE-G-10 |
| `get_by_component` | R4 | PCE-G-11 |
| `get_by_component` | R5 | PCE-G-12, PCE-G-13, PCE-G-14, PCE-G-19, PCE-G-20, PCE-G-31, PCE-G-32 |
| `get_by_component` | R6 | PCE-G-15, PCE-G-16, PCE-G-17, PCE-G-18, PCE-G-19, PCE-G-20, PCE-G-22, PCE-G-25 |
| `get_by_component` | R7 | PCE-G-21, PCE-G-22, PCE-G-23, PCE-G-24, PCE-G-25 |
| `get_by_component` | R8 | PCE-G-26, PCE-G-27 |
| `get_by_component` | R9 | PCE-G-28, PCE-G-29, PCE-G-30, PCE-G-33 |
| `get_by_component` | Errors row 1 | PCE-G-26 |
| `get_by_component` | Errors row 2 | PCE-G-27 |
| `get_by_component` | Overview | PCE-G-30 |
| `get_by_component` | Side effects | PCE-G-30, PCE-G-33 |
| `get_by_component` | Branch map | PCE-G-30 |
