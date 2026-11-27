# Test cases — `app/dao/machine_activity_event.py`

> **Spec:** `tests/unit/dao/machine_activity_event.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-10-31; nothing open). Q1, Q2, Q3 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `machine_activity_event.verify.md` (case-missing Findings 1, 2; recipes P1 … P3): Finding 1 → MAE-LS-16; Finding 2 → MAE-GM-45, GM-46. No existing card, Convention or ID changed, none retired.
> **Counts:** 81 cases · 79 expected-to-pass · 2 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Depth:** lighter target (skill step 1a). The module has three plain filtered reads and writes no stock, money or order state. Each rule's named inputs still get a card, because a When holds one call.
- **Per callable:** `get_by_machine` 46 · `get_latest_status_by_machine` 16 · `get_latest_status_map` 19 (2 bug).
- **Expected-to-fail:** BUG-1090 2: MAE-LM-14 non-strict (the order itself), MAE-LM-15 strict (the SQL recorder, the alarm that goes off when the bug is fixed). MAE-LM-13 is the passing companion: on a tie, one entry, one of the tied rows.
- **Answers and the cards that rest on them:** Q1 — MAE-GM-11, GM-12. Q2 — MAE-LS-11, LS-12, LM-16. Q3 — MAE-GM-30.
- **Notable design choices:**
  - "Writes nothing" is one card per reader (MAE-GM-44, LS-15, LM-19): a row added and not flushed must stay pending, no write statement is sent, and no `FOR UPDATE`. Readers have no commit spy.
  - Every filter negative puts the other row where it would change the result: newer than the expected row, or under `limit=1`, or with the same `created_at` and a higher id.
  - MAE-GM-30 runs under `Asia/Dhaka`, where the two rows fall on the other local days. New York is not repeated.
  - MAE-LS-03 and MAE-LM-13, LM-14 use the spec's tie recipe. No pass card compares an order produced without `ORDER BY`.
  - The single lookup's tie has two cards: MAE-LS-03 (higher id physically first) and MAE-LS-16 (no update, higher id physically last). Neither alone rules out physical order.
  - MAE-GM-43 reads the stored text to prove both forms of empty metadata are really there.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking. See Spec gap 3 (a BUG-1090 fix with no `ORDER BY` would leave the strict recorder silent).

## Conventions for this module

**IDs.** `MAE` = `app/dao/machine_activity_event.py`. `GM` get_by_machine · `LS` get_latest_status_by_machine · `LM` get_latest_status_map.

**Actors and fixed values.**
- `dao` = the singleton `machine_activity_event_dao` (`from app.dao.machine_activity_event import machine_activity_event_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `MachineActivityEvent` = `app.models.machine_activity_event.MachineActivityEvent`. `date`, `datetime`, `timedelta` = the `datetime` module's classes. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.
- T1 = `datetime(2026, 3, 4, 10, 0, 0)`, T2 = `datetime(2026, 3, 5, 10, 0, 0)`, T3 = `datetime(2026, 3, 6, 10, 0, 0)`.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces and the profile from `make_workspace`, `make_profile`; the rest built directly, `Factory` and `Machine` models):
  - W1, W2 = two `workspaces` rows. U1 = a `profiles` row.
  - F1 = `factories` row: `workspace_id W1.id`, `name "Factory One"`, `abbreviation "F1"`, `is_active True`, `is_deleted False`. FD = the same, but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True` (soft-deleted; `is_active` stays True). F9 = the same as F1, but `name "Factory Nine"`, `abbreviation "F9"`, `workspace_id W2.id`.
  - M1 = `machines` row: `workspace_id W1.id`, `factory_id F1.id`, `name "Press 1"`, `is_active True`, `is_deleted False`. M2 = the same, but `name "Press 2"`.
  - MD = the same as M1, but `name "Press 4"`, `is_active False`, `is_deleted True` (soft-deleted). MF = the same as M1, but `name "Lost Press"`, `factory_id FD.id` (live, in a soft-deleted factory). M9 = the same as M1, but `name "Far Press"`, `workspace_id W2.id`, `factory_id F9.id`.
- **event** = `machine_activity_events` row built with `MachineActivityEvent`: `workspace_id W1.id`, `machine_id M1.id`, `event_type "item_added"`, `description "Logged"`; `metadata_json` and `performed_by` are not passed. The card always gives `created_at`; after the word "but" it lists every other column that differs. `metadata_json None` means the keyword is passed with the value `None`.
- **status row** = an event, but `event_type "status_updated"`, `metadata_json {"status": "RUNNING"}`.
- No `machine_activity_events` row exists unless the card's Given lists it.
- A Given line written as code (`A.description = "Edited"`, then `db.flush()`) is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned; the order is part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `machine_activity_events` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- **stored_json(X)** = `db.scalar(text("SELECT metadata::text FROM machine_activity_events WHERE id = :i"), {"i": X.id})` — `None` for SQL `NULL`, `"null"` for JSON `null`.
- `pending:` lines check the row P after the call, on the object itself.
- `raises: DataError` = `sqlalchemy.exc.DataError`. Wrap the call: `with pytest.raises(DataError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards (the savepoint is rolled back). `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause` = classes of `psycopg2.errors`.
- Further `raises:` lines of the same card are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-1090")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `machine_activity_events`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.


## `MachineActivityEventDAO.get_by_machine`

### MAE-GM-01 — returns a list of the machine's rows of every event type
- **Rules:** `get_by_machine` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `event_type "created"`.
2. B = status row, `created_at T2`.
3. C = event, `created_at T3`, but `event_type "deactivated"`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.
3. returns: `isinstance(result[0], MachineActivityEvent)`.

### MAE-GM-02 — a newer row of another machine is not returned and takes no place in the page
- **Rules:** `get_by_machine` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. C = event, `created_at T2`, but `machine_id M2.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MAE-GM-03 — the right machine under another workspace returns an empty list
- **Rules:** `get_by_machine` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### MAE-GM-04 — a newer W2 row on the same machine is not returned and takes no place in the page
- **Rules:** `get_by_machine` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. Z = event, `created_at T2`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MAE-GM-05 — a W1 row on a machine of W2 is returned for W1: only the row's workspace is compared
- **Rules:** `get_by_machine` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `machine_id M9.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M9.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MAE-GM-06 — a W1 row on a machine of W2 is not returned for W2
- **Rules:** `get_by_machine` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `machine_id M9.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M9.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### MAE-GM-07 — an unknown machine id returns an empty list
- **Rules:** `get_by_machine` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MAE-GM-08 — machine_id=0 returns an empty list
- **Rules:** `get_by_machine` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MAE-GM-09 — an unknown workspace returns an empty list
- **Rules:** `get_by_machine` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### MAE-GM-10 — a machine with no events returns an empty list
- **Rules:** `get_by_machine` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=M2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MAE-GM-11 — every event of a soft-deleted machine is returned
- **Rules:** `get_by_machine` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `machine_id MD.id`, `event_type "created"`.
2. B = event, `created_at T2`, but `machine_id MD.id`, `event_type "deactivated"`.

**When**
- `result = dao.get_by_machine(db, machine_id=MD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### MAE-GM-12 — every event of a live machine in a soft-deleted factory is returned
- **Rules:** `get_by_machine` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `machine_id MF.id`, `event_type "created"`.
2. B = event, `created_at T2`, but `machine_id MF.id`, `event_type "item_added"`.

**When**
- `result = dao.get_by_machine(db, machine_id=MF.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### MAE-GM-13 — rows are ordered by created_at descending, then id descending
- **Rules:** `get_by_machine` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T3`.
3. C = event, `created_at T1`.
4. D = event, `created_at T3`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [D.id, B.id, A.id, C.id]`.

### MAE-GM-14 — with the default limit 101 rows give the newest 100
- **Rules:** `get_by_machine` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 events E1 … E101, built with `add_all`: Ek = event, `created_at` = `T1 + timedelta(minutes=k)`. `newest_first` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest_first[:100]`.

### MAE-GM-15 — limit=1000 returns all 101 rows
- **Rules:** `get_by_machine` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 events E1 … E101, built with `add_all`: Ek = event, `created_at` = `T1 + timedelta(minutes=k)`. `newest_first` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == newest_first`.

### MAE-GM-16 — the first window holds the two newest rows, sorted before paging
- **Rules:** `get_by_machine` R6, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T3`.
3. C = event, `created_at T1`.
4. D = event, `created_at T3`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `ids(result) == [D.id, B.id]`.

### MAE-GM-17 — the next window holds the two other rows: no repeat, no gap
- **Rules:** `get_by_machine` R6, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T3`.
3. C = event, `created_at T1`.
4. D = event, `created_at T3`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `ids(result) == [A.id, C.id]`.

### MAE-GM-18 — limit=0 returns an empty list
- **Rules:** `get_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MAE-GM-19 — limit=1 returns the newest row
- **Rules:** `get_by_machine` R7, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MAE-GM-20 — skip equal to the number of rows returns an empty list
- **Rules:** `get_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### MAE-GM-21 — skip past the number of rows returns an empty list
- **Rules:** `get_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### MAE-GM-22 — skip one below the number of rows returns the oldest row
- **Rules:** `get_by_machine` R7, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MAE-GM-23 — a negative limit is rejected by Postgres
- **Rules:** `get_by_machine` R8, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MAE-GM-24 — a negative skip is rejected by Postgres
- **Rules:** `get_by_machine` R8, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError` when the query runs.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
5. nothing written: nothing written.

### MAE-GM-25 — from_date keeps the first microsecond of the day, not the last of the day before
- **Rules:** `get_by_machine` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at datetime(2026, 3, 4, 23, 59, 59, 999999)`.
2. B = event, `created_at datetime(2026, 3, 5, 0, 0, 0)`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, from_date=date(2026, 3, 5))`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MAE-GM-26 — to_date keeps the last microsecond of the day, not the first of the next day
- **Rules:** `get_by_machine` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at datetime(2026, 3, 5, 23, 59, 59, 999999)`.
2. B = event, `created_at datetime(2026, 3, 6, 0, 0, 0)`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, to_date=date(2026, 3, 5))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MAE-GM-27 — both dates keep the inclusive range
- **Rules:** `get_by_machine` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at datetime(2026, 3, 3, 23, 59, 59, 999999)`.
2. B = event, `created_at datetime(2026, 3, 4, 0, 0, 0)`.
3. C = event, `created_at datetime(2026, 3, 5, 12, 0, 0)`.
4. D = event, `created_at datetime(2026, 3, 6, 23, 59, 59, 999999)`.
5. E = event, `created_at datetime(2026, 3, 7, 0, 0, 0)`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, from_date=date(2026, 3, 4), to_date=date(2026, 3, 6))`.

**Then**
1. returns: `ids(result) == [D.id, C.id, B.id]`.

### MAE-GM-28 — from_date equal to to_date covers that whole day
- **Rules:** `get_by_machine` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at datetime(2026, 3, 4, 23, 59, 59, 999999)`.
2. B = event, `created_at datetime(2026, 3, 5, 0, 0, 0)`.
3. C = event, `created_at datetime(2026, 3, 5, 23, 59, 59, 999999)`.
4. D = event, `created_at datetime(2026, 3, 6, 0, 0, 0)`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, from_date=date(2026, 3, 5), to_date=date(2026, 3, 5))`.

**Then**
1. returns: `ids(result) == [C.id, B.id]`.

### MAE-GM-29 — from_date after to_date returns an empty list, with no error
- **Rules:** `get_by_machine` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at datetime(2026, 3, 4, 12, 0, 0)`.
2. B = event, `created_at datetime(2026, 3, 5, 12, 0, 0)`.
3. C = event, `created_at datetime(2026, 3, 6, 12, 0, 0)`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, from_date=date(2026, 3, 6), to_date=date(2026, 3, 4))`.

**Then**
1. returns: `result == []`.

### MAE-GM-30 — a day is a UTC day, also under a session in another time zone
- **Rules:** `get_by_machine` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. A = event, `created_at datetime(2026, 3, 4, 19, 0, 0)`.
3. B = event, `created_at datetime(2026, 3, 5, 19, 0, 0)`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, from_date=date(2026, 3, 5), to_date=date(2026, 3, 5))`.

**Then**
1. returns: `ids(result) == [B.id]`.

### MAE-GM-31 — a datetime passed as a date counts by its date only
- **Rules:** `get_by_machine` Inputs
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at datetime(2026, 3, 5, 0, 0, 0)`.
2. B = event, `created_at datetime(2026, 3, 5, 23, 59, 59, 999999)`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, from_date=datetime(2026, 3, 5, 15, 30, 0), to_date=datetime(2026, 3, 5, 9, 0, 0))`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### MAE-GM-32 — event_type keeps only the rows of that type
- **Rules:** `get_by_machine` R13
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = status row, `created_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, event_type="item_added")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MAE-GM-33 — event_type: another case does not match
- **Rules:** `get_by_machine` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, event_type="ITEM_ADDED")`.

**Then**
1. returns: `result == []`.

### MAE-GM-34 — event_type: trailing space does not match
- **Rules:** `get_by_machine` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, event_type="item_added ")`.

**Then**
1. returns: `result == []`.

### MAE-GM-35 — event_type: a single space is a filter and matches nothing
- **Rules:** `get_by_machine` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, event_type=" ")`.

**Then**
1. returns: `result == []`.

### MAE-GM-36 — event_type: a wildcard does not match
- **Rules:** `get_by_machine` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, event_type="item%")`.

**Then**
1. returns: `result == []`.

### MAE-GM-37 — event_type: an unknown type matches nothing
- **Rules:** `get_by_machine` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, event_type="scrapped")`.

**Then**
1. returns: `result == []`.

### MAE-GM-38 — event_type=None applies no filter
- **Rules:** `get_by_machine` R14
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = status row, `created_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, event_type=None)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### MAE-GM-39 — an empty event_type applies no filter
- **Rules:** `get_by_machine` R14
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = status row, `created_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, event_type="")`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### MAE-GM-40 — the type filter applies before limit
- **Rules:** `get_by_machine` R15
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, event_type="status_updated", limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MAE-GM-41 — all filters combine and apply before skip and limit
- **Rules:** `get_by_machine` R15
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = status row, `created_at T2`.
3. C = status row, `created_at T2`, but `machine_id M2.id`.
4. D = status row, `created_at T2`, but `workspace_id W2.id`.
5. E = event, `created_at T2`.
6. L = status row, `created_at T3`.
7. O = status row, `created_at datetime(2026, 3, 3, 10, 0, 0)`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, from_date=date(2026, 3, 4), to_date=date(2026, 3, 5), event_type="status_updated", skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MAE-GM-42 — a row comes back as stored, with its performer
- **Rules:** `get_by_machine` R16
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = status row, `created_at T2`, but `description "Press started"`, `metadata_json {"status": "RUNNING", "note": "Shift 1"}`, `performed_by U1.id`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].workspace_id == W1.id`, `result[0].machine_id == M1.id`, `result[0].event_type == "status_updated"`.
3. returns: `result[0].description == "Press started"`, `result[0].created_at == T2`.
4. returns: `result[0].metadata_json == {"status": "RUNNING", "note": "Shift 1"}`.
5. returns: `result[0].performer.id == U1.id`.

### MAE-GM-43 — SQL NULL and JSON null metadata both read back as None, and no performer gives None
- **Rules:** `get_by_machine` R16
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`, but `metadata_json None`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.
2. returns: `result[0].metadata_json is None`.
3. returns: `result[1].metadata_json is None`.
4. re-read A: `stored_json(A) is None`.
5. re-read B: `stored_json(B) == "null"`.
6. returns: `result[0].performer is None`.

### MAE-GM-44 — writes nothing: a pending row stays pending and is not returned
- **Rules:** `get_by_machine` R16, Side effects, Overview
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. `P = MachineActivityEvent(workspace_id=W1.id, machine_id=M1.id, event_type="item_added", description="Pending", created_at=T2)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.

### MAE-GM-45 — event_type: a stored type that ends with the filter does not match
- **Rules:** `get_by_machine` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `event_type "updated"`.
2. B = status row, `created_at T2`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, event_type="updated")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MAE-GM-46 — event_type: a stored type that starts with the filter does not match
- **Rules:** `get_by_machine` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_machine(db, machine_id=M1.id, workspace_id=W1.id, event_type="item")`.

**Then**
1. returns: `result == []`.


## `MachineActivityEventDAO.get_latest_status_by_machine`

### MAE-LS-01 — returns the status row with the newest created_at, whatever its id
- **Rules:** `get_latest_status_by_machine` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = status row, `created_at T2`.
2. B = status row, `created_at T3`.
3. C = status row, `created_at T1`.

**When**
- `result = dao.get_latest_status_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.
2. returns: `isinstance(result, MachineActivityEvent)`.

### MAE-LS-02 — a newer status row of another machine is not returned
- **Rules:** `get_latest_status_by_machine` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. C = status row, `created_at T2`, but `machine_id M2.id`.

**When**
- `result = dao.get_latest_status_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### MAE-LS-03 — on a created_at tie the highest id is returned
- **Rules:** `get_latest_status_by_machine` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T2`.
2. B = status row, `created_at T2`.
3. `A.description = "Edited"`, then `db.flush()`.
4. `db.expire_all()`.

**When**
- `result = dao.get_latest_status_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.

### MAE-LS-04 — newer rows of other types are ignored, even with a status key
- **Rules:** `get_latest_status_by_machine` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = event, `created_at T2`.
3. C = event, `created_at T3`, but `event_type "updated"`, `metadata_json {"status": "OFF"}`.
4. D = event, `created_at T3`, but `event_type "STATUS_UPDATED"`, `metadata_json {"status": "OFF"}`.

**When**
- `result = dao.get_latest_status_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### MAE-LS-05 — a machine with only rows of other types returns None and nothing is created
- **Rules:** `get_latest_status_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `metadata_json {"status": "OFF"}`.

**When**
- `result = dao.get_latest_status_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### MAE-LS-06 — an unknown machine id returns None
- **Rules:** `get_latest_status_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.

**When**
- `result = dao.get_latest_status_by_machine(db, machine_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MAE-LS-07 — machine_id=0 returns None
- **Rules:** `get_latest_status_by_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.

**When**
- `result = dao.get_latest_status_by_machine(db, machine_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### MAE-LS-08 — a newer status row of another workspace on the same machine is ignored
- **Rules:** `get_latest_status_by_machine` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. Z = status row, `created_at T2`, but `workspace_id W2.id`, `metadata_json {"status": "OFF"}`.

**When**
- `result = dao.get_latest_status_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### MAE-LS-09 — the right machine under another workspace returns None
- **Rules:** `get_latest_status_by_machine` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.

**When**
- `result = dao.get_latest_status_by_machine(db, machine_id=M1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### MAE-LS-10 — a W1 status row on a machine of W2 is returned for W1: only the row's workspace is compared
- **Rules:** `get_latest_status_by_machine` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`, but `machine_id M9.id`.

**When**
- `result = dao.get_latest_status_by_machine(db, machine_id=M9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### MAE-LS-11 — the status row of a soft-deleted machine is returned
- **Rules:** `get_latest_status_by_machine` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`, but `machine_id MD.id`.

**When**
- `result = dao.get_latest_status_by_machine(db, machine_id=MD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### MAE-LS-12 — the status row of a live machine in a soft-deleted factory is returned
- **Rules:** `get_latest_status_by_machine` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`, but `machine_id MF.id`.

**When**
- `result = dao.get_latest_status_by_machine(db, machine_id=MF.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### MAE-LS-13 — a newest status row with no metadata is returned, older rows are not consulted
- **Rules:** `get_latest_status_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = event, `created_at T2`, but `event_type "status_updated"`.

**When**
- `result = dao.get_latest_status_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.

### MAE-LS-14 — a newest status row with no status key is returned, older rows are not consulted
- **Rules:** `get_latest_status_by_machine` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = status row, `created_at T2`, but `metadata_json {"note": "Shift 1"}`.

**When**
- `result = dao.get_latest_status_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.

### MAE-LS-15 — writes nothing: a newer pending row stays pending and is not returned
- **Rules:** `get_latest_status_by_machine` Side effects, Overview
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. `P = MachineActivityEvent(workspace_id=W1.id, machine_id=M1.id, event_type="status_updated", description="Pending", created_at=T2)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_latest_status_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.

### MAE-LS-16 — on a created_at tie with no update the highest id is returned
- **Rules:** `get_latest_status_by_machine` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T2`.
2. B = status row, `created_at T2`.

**When**
- `result = dao.get_latest_status_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.


## `MachineActivityEventDAO.get_latest_status_map`

### MAE-LM-01 — an empty list returns an empty dict
- **Rules:** `get_latest_status_map` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[])`.

**Then**
1. returns: `result == {}`.

### MAE-LM-02 — None returns an empty dict
- **Rules:** `get_latest_status_map` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=None)`.

**Then**
1. returns: `result == {}`.

### MAE-LM-03 — each machine asked for gets its newest status row
- **Rules:** `get_latest_status_map` R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = status row, `created_at T3`.
2. A = status row, `created_at T2`.
3. D = status row, `created_at T2`, but `machine_id M2.id`.
4. C = status row, `created_at T1`, but `machine_id M2.id`.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id, M2.id])`.

**Then**
1. returns: `isinstance(result, dict)`.
2. returns: `set(result) == {M1.id, M2.id}`.
3. returns: `result[M1.id].id == B.id`.
4. returns: `result[M2.id].id == D.id`.
5. returns: `isinstance(result[M1.id], MachineActivityEvent)`.

### MAE-LM-04 — no status row, an unknown id and 0 give no entry
- **Rules:** `get_latest_status_map` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = event, `created_at T2`, but `machine_id M2.id`, `metadata_json {"status": "OFF"}`.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id, M2.id, MISSING, 0])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id].id == A.id`.

### MAE-LM-05 — a machine not asked for has no entry
- **Rules:** `get_latest_status_map` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = status row, `created_at T2`, but `machine_id M2.id`.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id].id == A.id`.

### MAE-LM-06 — an id listed twice gives one entry
- **Rules:** `get_latest_status_map` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id, M1.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id].id == A.id`.

### MAE-LM-07 — newer rows of other types are ignored, even with a status key
- **Rules:** `get_latest_status_map` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = event, `created_at T2`, but `event_type "updated"`, `metadata_json {"status": "OFF"}`.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id].id == A.id`.

### MAE-LM-08 — a later row of another type with the same created_at is ignored
- **Rules:** `get_latest_status_map` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = event, `created_at T1`, but `event_type "updated"`, `metadata_json {"status": "OFF"}`.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id].id == A.id`.

### MAE-LM-09 — a newer status row of another workspace on the same machine is ignored
- **Rules:** `get_latest_status_map` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. Z = status row, `created_at T2`, but `workspace_id W2.id`, `metadata_json {"status": "OFF"}`.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id].id == A.id`.

### MAE-LM-10 — a later status row of another workspace with the same created_at is ignored
- **Rules:** `get_latest_status_map` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. Z = status row, `created_at T1`, but `workspace_id W2.id`, `metadata_json {"status": "OFF"}`.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id].id == A.id`.

### MAE-LM-11 — the right machine under another workspace gives no entry
- **Rules:** `get_latest_status_map` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W2.id, machine_ids=[M1.id])`.

**Then**
1. returns: `result == {}`.

### MAE-LM-12 — a W1 status row on a machine of W2 is the entry for W1: only the row's workspace is compared
- **Rules:** `get_latest_status_map` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`, but `machine_id M9.id`.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M9.id])`.

**Then**
1. returns: `set(result) == {M9.id}`.
2. returns: `result[M9.id].id == A.id`.

### MAE-LM-13 — on a tie the machine gets one entry, one of the tied rows
- **Rules:** `get_latest_status_map` R6, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T2`.
2. B = status row, `created_at T2`.
3. C = status row, `created_at T1`.
4. `A.description = "Edited"`, then `db.flush()`.
5. `db.expire_all()`.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id].id in {A.id, B.id}`.

### MAE-LM-14 — on a tie the entry is the highest id, the row the single lookup returns
- **Rules:** `get_latest_status_map` R6 [BUG-1090]
- **Kind:** bug
- **Expect:** xfail BUG-1090 (non-strict)
- **Fails today on:** Then 3 (no order is requested among the tied rows, so the updated lower-id row usually wins — but that rests on physical row order, which can match the intended result by accident)

**Given**
1. A = status row, `created_at T2`.
2. B = status row, `created_at T2`.
3. `A.description = "Edited"`, then `db.flush()`.
4. `db.expire_all()`.
5. `single = dao.get_latest_status_by_machine(db, machine_id=M1.id, workspace_id=W1.id)`.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `single.id == B.id`.
3. returns: `result[M1.id].id == B.id`.
4. returns: `result[M1.id].id == single.id`.

### MAE-LM-15 — the map's query asks the database for an order that includes id
- **Rules:** `get_latest_status_map` R6 [BUG-1090]
- **Kind:** bug
- **Expect:** xfail BUG-1090
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = status row, `created_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `result[M1.id].id == A.id`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.

### MAE-LM-16 — the status rows of a soft-deleted machine and of a machine in a soft-deleted factory are the entries
- **Rules:** `get_latest_status_map` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`, but `machine_id MD.id`.
2. B = status row, `created_at T1`, but `machine_id MF.id`.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[MD.id, MF.id])`.

**Then**
1. returns: `set(result) == {MD.id, MF.id}`.
2. returns: `result[MD.id].id == A.id`.
3. returns: `result[MF.id].id == B.id`.

### MAE-LM-17 — a newest status row with no metadata is the entry
- **Rules:** `get_latest_status_map` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = event, `created_at T2`, but `event_type "status_updated"`.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `set(result) == {M1.id}`.
2. returns: `result[M1.id].id == B.id`.

### MAE-LM-18 — many machines are answered in one read
- **Rules:** `get_latest_status_map` Purpose
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. B = status row, `created_at T1`, but `machine_id M2.id`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id, M2.id])`.

**Then**
1. returns: `set(result) == {M1.id, M2.id}`.
2. statement: `len(selects) == 1`.

### MAE-LM-19 — writes nothing: a newer pending row stays pending and is not the entry
- **Rules:** `get_latest_status_map` Side effects, Overview
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = status row, `created_at T1`.
2. `P = MachineActivityEvent(workspace_id=W1.id, machine_id=M1.id, event_type="status_updated", description="Pending", created_at=T2)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_latest_status_map(db, workspace_id=W1.id, machine_ids=[M1.id])`.

**Then**
1. returns: `result[M1.id].id == A.id`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_by_machine` R2 — `list_events` answers 404 for a machine of another workspace | `MachineActivityManager.list_events` | This DAO returns the row for its own workspace (MAE-GM-05); the 404 is what keeps it out of a response. |
| FU-1 (a), (b) — `get_latest_status` "404 if missing" comment; one `profile_dao.get` per event | `MachineActivityManager` | Not rules of this DAO. |
| FU-1 (c) — BUG-1091: `log_event` must refuse another workspace's machine (404, nothing written) | `MachineActivityManager.log_event` | The rule and the tag belong to that spec. No card here. |
| FU-1 (d) — `metadata=None` stored as JSON `null` | `MachineActivityManager.log_event`, machine DAO `search_advanced` R12c | Here both forms read back as `None` (MAE-GM-43). |
| FU-2 (a), (b) — dropped metadata keys; a non-integer `quantity` makes the page a 500 | `MachineService.get_machine_activity` | No card here. |
| `skip >= 0`, `1 <= limit <= 1000`, date parsing (HR-7) | `GET /machines/{id}/activity/` | Here negative values reach Postgres (MAE-GM-23, GM-24). |
| Generic behavior of inherited `get`, `get_multi`, `get_by_workspace`, `get_by_id_and_workspace`, `create`, `update`, `remove` | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not specified here, no caller on this DAO. |
| Notes: keyword-only parameters | none (no rule) | Spec gap 1. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes ("every parameter after `db` is keyword-only") | Stated as a note, not as a rule. | No card, as in `machine_item.cases.md` and `item_tag.cases.md`. |
| 2 | `get_latest_status_map` R6, Notes ("Compare with `get_latest_status_by_machine` in the same case") | The comparison needs a second call; the card format allows one call in When. | MAE-LM-14 runs the single lookup as its last Given line, so the When is still the map. |
| 3 | `get_latest_status_map` R6 | How the fix must look is not stated. Ascending order with last-row-wins, descending order with first-row-wins, `DISTINCT ON`, or a window all contain `ORDER BY`; a `max(id)` subquery or a Python tie-break has none. | MAE-LM-15 asserts only `ORDER BY` and `.id`, not a direction. Under a fix with no `ORDER BY`, LM-15 keeps failing as xfail and only the non-strict LM-14 passes, so no alarm sounds: that card must then be rewritten with the fix. |
| 4 | Header, "one statement per call and no join" against Branch map 86–94 ("join on machine and timestamp") | Read here as: one SQL statement holding a self-join, no join to machines or factories. | MAE-LM-18 counts statements only, no card asserts the absence of a join. `get_by_machine` R4 and `get_latest_status_by_machine` R6 cover the behavior. |
| 5 | Overview ("takes no lock"), `get_latest_status_map` Purpose ("in one read") | Each stands outside the numbered rules. | Covered anyway, as Overview and Purpose rows of the matrix: MAE-GM-44, LS-15, LM-19 and MAE-LM-18. Drop those lines if they are not meant as a contract. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_machine` | Inputs | MAE-GM-31 |
| `get_by_machine` | Returns | MAE-GM-01 |
| `get_by_machine` | R1 | MAE-GM-01, MAE-GM-02 |
| `get_by_machine` | R2 | MAE-GM-03, MAE-GM-04, MAE-GM-05, MAE-GM-06 |
| `get_by_machine` | R3 | MAE-GM-07, MAE-GM-08, MAE-GM-09, MAE-GM-10 |
| `get_by_machine` | R4 | MAE-GM-11, MAE-GM-12 |
| `get_by_machine` | R5 | MAE-GM-13, MAE-GM-16, MAE-GM-17 |
| `get_by_machine` | R6 | MAE-GM-14, MAE-GM-15, MAE-GM-16, MAE-GM-17, MAE-GM-19, MAE-GM-22 |
| `get_by_machine` | R7 | MAE-GM-18, MAE-GM-19, MAE-GM-20, MAE-GM-21, MAE-GM-22 |
| `get_by_machine` | R8 | MAE-GM-23, MAE-GM-24 |
| `get_by_machine` | R9 | MAE-GM-25 |
| `get_by_machine` | R10 | MAE-GM-26 |
| `get_by_machine` | R11 | MAE-GM-27, MAE-GM-28, MAE-GM-29 |
| `get_by_machine` | R12 | MAE-GM-30 |
| `get_by_machine` | R13 | MAE-GM-32, MAE-GM-33, MAE-GM-34, MAE-GM-35, MAE-GM-36, MAE-GM-37, MAE-GM-45, MAE-GM-46 |
| `get_by_machine` | R14 | MAE-GM-38, MAE-GM-39 |
| `get_by_machine` | R15 | MAE-GM-40, MAE-GM-41 |
| `get_by_machine` | R16 | MAE-GM-42, MAE-GM-43, MAE-GM-44 |
| `get_by_machine` | Errors row 1 | MAE-GM-23 |
| `get_by_machine` | Errors row 2 | MAE-GM-24 |
| `get_by_machine` | Overview | MAE-GM-44 |
| `get_by_machine` | Side effects | MAE-GM-44 |
| `get_latest_status_by_machine` | Returns | MAE-LS-01 |
| `get_latest_status_by_machine` | R1 | MAE-LS-01, MAE-LS-02 |
| `get_latest_status_by_machine` | R2 | MAE-LS-03, MAE-LS-16 |
| `get_latest_status_by_machine` | R3 | MAE-LS-04 |
| `get_latest_status_by_machine` | R4 | MAE-LS-05, MAE-LS-06, MAE-LS-07 |
| `get_latest_status_by_machine` | R5 | MAE-LS-08, MAE-LS-09, MAE-LS-10 |
| `get_latest_status_by_machine` | R6 | MAE-LS-11, MAE-LS-12 |
| `get_latest_status_by_machine` | R7 | MAE-LS-13, MAE-LS-14 |
| `get_latest_status_by_machine` | Overview | MAE-LS-15 |
| `get_latest_status_by_machine` | Side effects | MAE-LS-15 |
| `get_latest_status_map` | Purpose | MAE-LM-18 |
| `get_latest_status_map` | Returns | MAE-LM-03 |
| `get_latest_status_map` | R1 | MAE-LM-01, MAE-LM-02 |
| `get_latest_status_map` | R2 | MAE-LM-03, MAE-LM-13 |
| `get_latest_status_map` | R3 | MAE-LM-04, MAE-LM-05, MAE-LM-06 |
| `get_latest_status_map` | R4 | MAE-LM-07, MAE-LM-08 |
| `get_latest_status_map` | R5 | MAE-LM-09, MAE-LM-10, MAE-LM-11, MAE-LM-12 |
| `get_latest_status_map` | R6 | MAE-LM-13 |
| `get_latest_status_map` | R6 [BUG-1090] | MAE-LM-14, MAE-LM-15 |
| `get_latest_status_map` | R7 | MAE-LM-16 |
| `get_latest_status_map` | R8 | MAE-LM-17 |
| `get_latest_status_map` | Overview | MAE-LM-19 |
| `get_latest_status_map` | Side effects | MAE-LM-19 |
