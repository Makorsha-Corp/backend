# Test cases — `app/managers/project_component_activity_manager.py`

> **Spec:** `tests/unit/managers/project_component_activity_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Counts:** 52 cases · 45 expected-to-pass · 7 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `log_event` 25 (5 bug) · `list_events` 27 (2 bug)
- **Depth:** light-to-normal (skill step 1a). No stock, money or order state, so no multiplying by value or argument mix; but `log_event` is the only writer of the log and carries HR-16 (BUG-1192), so each of its refusal shapes has its own card, and `list_events` carries the read budget (BUG-1712). The DAO's own detail (tie after an update, windows partition, every filter twice) stays with `project_component_activity_event.cases.md`.
- **Expected-to-fail by bug:** BUG-1192 5 · BUG-1712 2. All strict.
- **Notable design choices:**
  - **Foreign component, both id sides.** The standing rows give W2 a component with a lower id than CP1 (CP8) and one with a higher id (CP9). `log_event` refuses each (PCAM-LE-13, LE-14, xfail); `list_events` answers 404 for each (PCAM-LI-05, LI-06, pass). PCAM-LE-18 is the other side: W2's own component from W2 is accepted.
  - **Refusals in `log_event`.** Foreign component cards use a plain `pytest.raises`, no savepoint, and check `db.new` is empty: a savepoint's rollback would hide a write. Unknown id, `0` and unknown workspace use the savepoint, since today they raise `IntegrityError`. The `Today:` Errors row has no pass card: it would test the buggy path.
  - **Access gate first:** PCAM-LI-10 sends a foreign component with `limit=-1`; the 404 must come before the page read.
  - **Read budget on both sides:** PCAM-LI-24 (one entry, 3 reads today) passes; LI-25, LI-26 (5 entries) fail today with 7 and 6 reads.
  - **"No event is read"** (`list_events` R2) is checked as exactly one statement on the 404 path.
  - The soft-deleted project's columns come from `project_event.cases.md` (Spec gap 2).
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking. Spec gaps 1–2 weaken no rule card.

## Conventions for this module

**IDs.** `PCAM` = `app/managers/project_component_activity_manager.py`. `LE` log_event · `LI` list_events.

**Actors and fixed values.**
- `M` = the singleton `project_component_activity_manager` (`from app.managers.project_component_activity_manager import ProjectComponentActivityManager, project_component_activity_manager`). `db` = the test's real session, always the first argument; the rest by keyword, except where a card writes a positional call. `result` = what the When call returns. The session does not autoflush.
- W1, W2 = two `workspaces` rows; U1, U2 = two `profiles` rows, from `make_workspace`, `make_profile` in `tests/unit/factories.py`.
- Classes: `Factory`, `Project`, `ProjectComponent` as imported by `tests/unit/dao/test_project_component_activity_event.py`; `ProjectComponentActivityEvent` (`app.models.project_component_activity_event`); `HTTPException` (`fastapi`); `Decimal` (`decimal`); `datetime`, `timedelta` (`datetime`); `text` (`sqlalchemy`).
- MISSING = `999999999`: an id no row of any table has.
- T1 = `datetime(2026, 3, 4, 10, 0, 0)`, T2 = `datetime(2026, 3, 5, 10, 0, 0)`, T3 = `datetime(2026, 3, 6, 10, 0, 0)`, T4 = `datetime(2026, 3, 7, 10, 0, 0)`.

**Externals.** None. Nothing is mocked. `created_at` is checked as set, or given in the Given.

**Standing rows.** In every test, built directly (add + flush) one at a time in exactly this order, no Given line needed. So `CP8.id < CP1.id < CP2.id < CPD.id < CP9.id`.
- F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`. F9 = `Factory(workspace_id=W2.id, name="Factory Nine", abbreviation="F9")`.
- PJ1 = `Project(workspace_id=W1.id, factory_id=F1.id, name="Project One", description="Main")`. PJD = the same as PJ1, but `name "Old Project"`, `is_deleted True`, `deleted_at T3`, `deleted_by U1.id` (soft-deleted; `is_active` not passed). PJ9 = `Project(workspace_id=W2.id, factory_id=F9.id, name="Project Nine", description="Main")`.
- Components (`ProjectComponent(workspace_id, project_id, name)`), in this order: CP8 `W2.id`, `PJ9.id`, `"Cellar"`. CP1 `W1.id`, `PJ1.id`, `"Roof"`. CP2 `W1.id`, `PJ1.id`, `"Wall"`. CPD `W1.id`, `PJD.id`, `"Shed"`. CP9 `W2.id`, `PJ9.id`, `"Floor"`.
- No `project_component_activity_events` row exists unless the card's Given builds it.

**Given rows.** Built directly with `ProjectComponentActivityEvent`, never through `M` unless the line is written as code, flushed one at a time in the order written, so ids rise in that order. A line written as code is a step to run exactly, at that place. `db.add(P)` with no flush leaves P pending.
- **event** = `workspace_id W1.id`, `project_component_id CP1.id`, `event_type "attachment_added"`, `description "Logged"`; `metadata_json` and `performed_by` are not passed. The card gives `created_at`; after "but" it lists every other column that differs. `metadata_json None` means the keyword is passed with `None`.
- **log(n)** = n events by one `add_all` and one flush: `created_at = T1 + timedelta(seconds=i)`, `description f"E{i}"`, for i from 0 to n-1. E(n-1) is the newest.
- A row with `project_component_id` of CP8 or CP9 and `workspace_id W1.id` is the invalid row of the spec: built only to prove it is hidden.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. "the returned row" = by `result.id`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call. Snapshot after the last Given line.
- **nothing written** = the row count of `project_component_activity_events` (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- **ids(x)** = `[pair[0].id for pair in x]`, for a `list_events` result; the order is part of the check.
- **stored_meta(X)** = `tuple(db.execute(text("SELECT metadata::text, metadata IS NULL FROM project_component_activity_events WHERE id = :i"), {"i": X.id}).one())`.
- `count:` lines count rows in all workspaces, with the filter stated.
- `raises: HTTPException`: plain `with pytest.raises(HTTPException) as exc:` around the call, no savepoint, unless the line says "in a savepoint".
- `raises: IntegrityError`, `DataError`, `StatementError` (`sqlalchemy.exc`), and any `raises:` line that says "in a savepoint": `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call. `ForeignKeyViolation`, `NotNullViolation`, `StringDataRightTruncation`, `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause` = classes of `psycopg2.errors`.
- Further `raises:` lines are assertions on `exc.value` after the block, one per line.
- `session:` and `pending:` lines run on `db` or the row directly, before any re-read or `expire_all()`. `statement:` lines are checks on `sql_log`.

**sql_log.** The snapshots of `nothing written` and `unchanged` are taken before it starts. A list filled by a `before_cursor_execute` listener on `db.connection()`, started at that Given line, removed after the call. Each entry is the statement text; `len(sql_log)` counts reads and writes alike. `written(sql_log)` = the entries that start with `INSERT`, `UPDATE` or `DELETE` after stripping and upper-casing. `locked(sql_log)` = the entries holding `FOR UPDATE`, upper-cased.

**Rolled back.** `sp = db.begin_nested()` directly before the call, and a spy wrapping `db.commit` (still callable, records calls). The first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**xfail cards.** Write the call and checks as shown. `pytest.mark.xfail(strict=True, reason="BUG-NNN")`.

**Race simulations.** None in this module.

## `ProjectComponentActivityManager.log_event`

### PCAM-LE-01 — one row is stored with every value given
- **Rules:** `log_event` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. CP1 (standing), no events.

**When**
- `result = M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="work_order_item_used", description="Used 40 Bolt", performed_by=U2.id, metadata={"quantity": 40})`.

**Then**
1. returns: `isinstance(result, ProjectComponentActivityEvent)`.
2. returns: `result.id is not None`.
3. re-read the returned row: `workspace_id == W1.id`, `project_component_id == CP1.id`, `event_type == "work_order_item_used"`, `description == "Used 40 Bolt"`, `performed_by == U2.id`.
4. re-read the returned row: `metadata_json == {"quantity": 40}`.
5. count: `project_component_activity_events` with `project_component_id == CP1.id` has exactly 1 row.

### PCAM-LE-02 — positional arguments work, in the order of the signature
- **Rules:** `log_event` R1, Facts (positional-or-keyword)
- **Kind:** happy
- **Expect:** pass

**Given**
1. CP1 (standing), no events.

**When**
- `result = M.log_event(db, CP1.id, W1.id, "attachment_added", "Attached a.png", U2.id, {"attachment_id": 7})`.

**Then**
1. re-read the returned row: `project_component_id == CP1.id`, `workspace_id == W1.id`, `event_type == "attachment_added"`, `description == "Attached a.png"`, `performed_by == U2.id`.
2. re-read the returned row: `metadata_json == {"attachment_id": 7}`.

### PCAM-LE-03 — two identical calls give two rows
- **Rules:** `log_event` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `first = M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="work_order_completed", description="Same")`.

**When**
- `result = M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="work_order_completed", description="Same")`.

**Then**
1. returns: `result.id != first.id`.
2. count: `project_component_activity_events` with `project_component_id == CP1.id` and `description == "Same"` has exactly 2 rows.

### PCAM-LE-04 — the call is one INSERT: no other row and not the component change, no lock
- **Rules:** `log_event` R1, Side effects, Overview
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`, but `project_component_id CP2.id`.
3. sql_log started.

**When**
- `result = M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="attachment_removed", description="Removed a.png")`.

**Then**
1. returns: `result.id not in {A.id, B.id}`.
2. statement: `len(written(sql_log)) == 1`.
3. statement: `written(sql_log)[0].strip().upper().startswith("INSERT INTO PROJECT_COMPONENT_ACTIVITY_EVENTS")`.
4. statement: `locked(sql_log) == []`.
5. unchanged: unchanged(A).
6. unchanged: unchanged(B).
7. unchanged: unchanged(CP1).

### PCAM-LE-05 — left out, metadata is stored as JSON null and performer as NULL
- **Rules:** `log_event` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CP1 (standing), no events.

**When**
- `result = M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="attachment_added", description="Attached")`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `metadata_json is None`, `performed_by is None`.
3. re-read the returned row: `stored_meta(result) == ("null", False)`.

### PCAM-LE-06 — metadata None passed explicitly is stored as JSON null
- **Rules:** `log_event` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CP1 (standing), no events.

**When**
- `result = M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="attachment_added", description="Attached", metadata=None)`.

**Then**
1. re-read the returned row: `metadata_json is None`.
2. re-read the returned row: `stored_meta(result) == ("null", False)`.

### PCAM-LE-07 — empty metadata is stored as an empty object, not as null
- **Rules:** `log_event` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CP1 (standing), no events.

**When**
- `result = M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="attachment_added", description="Attached", metadata={})`.

**Then**
1. re-read the returned row: `metadata_json == {}`.
2. re-read the returned row: `stored_meta(result) == ("{}", False)`.

### PCAM-LE-08 — nested metadata with None and a float comes back equal
- **Rules:** `log_event` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CP1 (standing), no events.

**When**
- `result = M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="work_order_item_used", description="Used", metadata={"lines": [1, {"note": None}], "quantity": 2.5})`.

**Then**
1. re-read the returned row: `metadata_json == {"lines": [1, {"note": None}], "quantity": 2.5}`.

### PCAM-LE-09 — an empty event type and an empty description are stored
- **Rules:** `log_event` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CP1 (standing), no events.

**When**
- `result = M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="", description="")`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `event_type == ""`, `description == ""`.

### PCAM-LE-10 — an event type of exactly 50 characters is stored
- **Rules:** `log_event` R4, Inputs
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CP1 (standing), no events.

**When**
- `result = M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="x" * 50, description="Attached")`.

**Then**
1. re-read the returned row: `event_type == "x" * 50`.

### PCAM-LE-11 — an event type of 51 characters is refused by the database, no row
- **Rules:** `log_event` Errors row 5, Inputs
- **Kind:** error
- **Expect:** pass

**Given**
1. CP1 (standing), no events.

**When**
- `M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="x" * 51, description="Attached")`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, StringDataRightTruncation)`.
3. raises: `exc.value.orig.pgcode == "22001"`.
4. nothing written: nothing written.

### PCAM-LE-12 — created_at is set on the row, with no time zone
- **Rules:** `log_event` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CP1 (standing), no events.

**When**
- `result = M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="attachment_added", description="Attached")`.

**Then**
1. returns: `result.created_at is not None`.
2. re-read the returned row: `created_at is not None`, `created_at.tzinfo is None`.

### PCAM-LE-13 — another workspace's component with a lower id is refused, nothing written
- **Rules:** `log_event` R6 [BUG-1192], Errors row 1, HR-16
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (no error is raised: the row is stored under W1 on W2's component)

**Given**
1. CP8 (standing; W2's component, `CP8.id < CP1.id`), no events.

**When**
- `M.log_event(db, project_component_id=CP8.id, workspace_id=W1.id, event_type="attachment_added", description="Attached a.png", performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project component with ID {CP8.id} not found"`.
4. session: `len(db.new) == 0`.
5. nothing written: nothing written.
6. count: `project_component_activity_events` with `project_component_id == CP8.id` has exactly 0 rows.

### PCAM-LE-14 — another workspace's component with a higher id is refused, nothing written
- **Rules:** `log_event` R6 [BUG-1192], Errors row 1, HR-16
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (no error is raised: the row is stored under W1 on W2's component)

**Given**
1. CP9 (standing; W2's component, `CP9.id > CP1.id`), no events.

**When**
- `M.log_event(db, project_component_id=CP9.id, workspace_id=W1.id, event_type="work_order_completed", description="Completed WO-1", performed_by=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project component with ID {CP9.id} not found"`.
4. session: `len(db.new) == 0`.
5. nothing written: nothing written.
6. count: `project_component_activity_events` with `project_component_id == CP9.id` has exactly 0 rows.

### PCAM-LE-15 — an unknown component gets the same 404
- **Rules:** `log_event` R6 [BUG-1192], Errors rows 1, 2
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (the call raises IntegrityError: foreign key on `project_component_id`, no component check runs)

**Given**
1. No project component has id MISSING.

**When**
- `M.log_event(db, project_component_id=MISSING, workspace_id=W1.id, event_type="attachment_added", description="Attached")`.

**Then**
1. raises: `HTTPException`, in a savepoint.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project component with ID 999999999 not found"`.
4. nothing written: nothing written.

### PCAM-LE-16 — component id 0 gets the same 404
- **Rules:** `log_event` R6 [BUG-1192], Errors rows 1, 2
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (the call raises IntegrityError: foreign key on `project_component_id`, no component check runs)

**Given**
1. No project component has id 0.

**When**
- `M.log_event(db, project_component_id=0, workspace_id=W1.id, event_type="attachment_added", description="Attached")`.

**Then**
1. raises: `HTTPException`, in a savepoint.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project component with ID 0 not found"`.
4. nothing written: nothing written.

### PCAM-LE-17 — an unknown workspace gets the same 404, naming the component
- **Rules:** `log_event` R6 [BUG-1192], Errors rows 1, 2
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (the call raises IntegrityError: foreign key on `workspace_id`, no component check runs)

**Given**
1. CP1 (standing). No workspace has id MISSING.

**When**
- `M.log_event(db, project_component_id=CP1.id, workspace_id=MISSING, event_type="attachment_added", description="Attached")`.

**Then**
1. raises: `HTTPException`, in a savepoint.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project component with ID {CP1.id} not found"`.
4. nothing written: nothing written.

### PCAM-LE-18 — W2's own component is accepted from W2
- **Rules:** `log_event` R1, R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. CP9 (standing; W2's component), no events.

**When**
- `result = M.log_event(db, project_component_id=CP9.id, workspace_id=W2.id, event_type="attachment_added", description="Attached b.png")`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `project_component_id == CP9.id`, `workspace_id == W2.id`, `description == "Attached b.png"`.
3. count: `project_component_activity_events` with `project_component_id == CP9.id` has exactly 1 row.

### PCAM-LE-19 — a component of a soft-deleted project is accepted
- **Rules:** `log_event` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. CPD (standing; its project PJD is soft-deleted), no events.

**When**
- `result = M.log_event(db, project_component_id=CPD.id, workspace_id=W1.id, event_type="attachment_removed", description="Removed a.png", performed_by=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `project_component_id == CPD.id`, `workspace_id == W1.id`, `event_type == "attachment_removed"`.
3. count: `project_component_activity_events` with `project_component_id == CPD.id` has exactly 1 row.

### PCAM-LE-20 — an unknown performer is refused by the database, no row
- **Rules:** `log_event` R8, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. CP1 (standing), no events. No profile has id MISSING.

**When**
- `M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="attachment_added", description="Attached", performed_by=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.pgcode == "23503"`.
4. nothing written: nothing written.

### PCAM-LE-21 — performer 0 is refused, not read as no performer
- **Rules:** `log_event` R8, Errors row 3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CP1 (standing), no events. No profile has id 0.

**When**
- `M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="attachment_added", description="Attached", performed_by=0)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `exc.value.orig.pgcode == "23503"`.
4. nothing written: nothing written.

### PCAM-LE-22 — a performer is not checked against the workspace
- **Rules:** `log_event` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `outsider = make_profile(db)`: a third profile, a member of no workspace.

**When**
- `result = M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="attachment_added", description="Attached", performed_by=outsider.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `performed_by == outsider.id`.

### PCAM-LE-23 — a Decimal in metadata fails at the flush, no row
- **Rules:** `log_event` R9, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. CP1 (standing), no events.

**When**
- `M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="work_order_item_used", description="Used", metadata={"quantity": Decimal("1.50")})`.

**Then**
1. raises: `StatementError`.
2. raises: `isinstance(exc.value.orig, TypeError)`.
3. raises: `getattr(exc.value.orig, "pgcode", None) is None`.
4. nothing written: nothing written.

### PCAM-LE-24 — event type None is refused by the database, no row
- **Rules:** `log_event` Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. CP1 (standing), no events.

**When**
- `M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type=None, description="Attached")`.

**Then**
1. raises: `IntegrityError`.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `exc.value.orig.pgcode == "23502"`.
4. nothing written: nothing written.

### PCAM-LE-25 — flushed, not committed: a savepoint's rollback removes the row
- **Rules:** `log_event` R10, Returns, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. CP1 (standing), no events.
2. Rolled back: `sp` opened and the commit spy set, directly before the call.

**When**
- `result = M.log_event(db, project_component_id=CP1.id, workspace_id=W1.id, event_type="attachment_added", description="Attached")`.

**Then**
1. returns: `result.id is not None`.
2. count: `project_component_activity_events` with `project_component_id == CP1.id` has exactly 1 row, inside the savepoint.
3. mock called: the commit spy was not called.
4. count: after the savepoint rollback, `project_component_activity_events` with `project_component_id == CP1.id` has exactly 0 rows.

## `ProjectComponentActivityManager.list_events`

### PCAM-LI-01 — the component's events come back newest first, as 2-tuples
- **Rules:** `list_events` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T3`, but `event_type "work_order_completed"`.
3. C = event, `created_at T1`, but `event_type "work_order_item_used"`.

**When**
- `result = M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, A.id, C.id]`.
3. returns: `isinstance(result[0], tuple)`, `len(result[0]) == 2`.
4. returns: `isinstance(result[0][0], ProjectComponentActivityEvent)`.

### PCAM-LI-02 — created_at decides first, then the higher id; no other column does
- **Rules:** `list_events` R1 (DAO `get_by_component` R5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2`, but `event_type "work_order_completed"`, `description "Zeta"`, `performed_by U2.id`.
2. B = event, `created_at datetime(2026, 3, 5, 9, 0, 0)`, but `event_type "attachment_added"`, `description "Alpha"`, `performed_by U1.id`.
3. C = event, `created_at T2`, but `event_type "work_order_item_used"`, `description "Mid"`.

**When**
- `result = M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id, A.id, B.id]`.

### PCAM-LI-03 — skip and limit reach the read by position, not swapped
- **Rules:** `list_events` R1, Facts (positional-or-keyword)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.
3. C = event, `created_at T3`.
4. D = event, `created_at T4`.

**When**
- `result = M.list_events(db, CP1.id, W1.id, 1, 2)`.

**Then**
1. returns: `ids(result) == [C.id, B.id]`.

### PCAM-LI-04 — another component's row ahead of the skipped row takes no place
- **Rules:** `list_events` R1 (DAO `get_by_component` R1), HR-5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R = event, `created_at T1`.
2. S = event, `created_at T2`.
3. H = event, `created_at T3`, but `project_component_id CP2.id`.

**When**
- `result = M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [R.id]`.

### PCAM-LI-05 — another workspace's component with a lower id gets 404, and no event is read
- **Rules:** `list_events` R2, Errors row 1, HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `workspace_id W2.id`, `project_component_id CP8.id` (`CP8.id < CP1.id`).
2. sql_log started.

**When**
- `M.list_events(db, project_component_id=CP8.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project component with ID {CP8.id} not found"`.
4. statement: `len(sql_log) == 1`.
5. nothing written: nothing written.

### PCAM-LI-06 — another workspace's component with a higher id gets 404, and no event is read
- **Rules:** `list_events` R2, Errors row 1, HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `workspace_id W2.id`, `project_component_id CP9.id` (`CP9.id > CP1.id`).
2. sql_log started.

**When**
- `M.list_events(db, project_component_id=CP9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project component with ID {CP9.id} not found"`.
4. statement: `len(sql_log) == 1`.
5. nothing written: nothing written.

### PCAM-LI-07 — an unknown component gets the same 404
- **Rules:** `list_events` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No project component has id MISSING.

**When**
- `M.list_events(db, project_component_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project component with ID 999999999 not found"`.
4. nothing written: nothing written.

### PCAM-LI-08 — component id 0 gets the same 404
- **Rules:** `list_events` R2, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No project component has id 0.

**When**
- `M.list_events(db, project_component_id=0, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project component with ID 0 not found"`.
4. nothing written: nothing written.

### PCAM-LI-09 — a negative component id gets the same 404
- **Rules:** `list_events` R2, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No project component has id -1.

**When**
- `M.list_events(db, project_component_id=-1, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project component with ID -1 not found"`.
4. nothing written: nothing written.

### PCAM-LI-10 — the component check comes before the page: a foreign component with a negative limit gets 404
- **Rules:** `list_events` R2, R9, Errors rows 1, 2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `workspace_id W2.id`, `project_component_id CP9.id`.

**When**
- `M.list_events(db, project_component_id=CP9.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project component with ID {CP9.id} not found"`.

### PCAM-LI-11 — a W1 row on W2's component does not reach W1: it gets the 404
- **Rules:** `list_events` R3, HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `project_component_id CP9.id` (the invalid row: `workspace_id W1.id`).

**When**
- `M.list_events(db, project_component_id=CP9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project component with ID {CP9.id} not found"`.
4. unchanged: unchanged(A).

### PCAM-LI-12 — W2's page leaves out the W1 row on its component, and it takes no place
- **Rules:** `list_events` R3, R1, HR-16, HR-5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R = event, `created_at T1`, but `workspace_id W2.id`, `project_component_id CP9.id`.
2. S = event, `created_at T2`, but `workspace_id W2.id`, `project_component_id CP9.id`.
3. H = event, `created_at T3`, but `project_component_id CP9.id` (the invalid row: `workspace_id W1.id`).

**When**
- `result = M.list_events(db, project_component_id=CP9.id, workspace_id=W2.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [R.id]`.

### PCAM-LI-13 — a component of a soft-deleted project returns every event
- **Rules:** `list_events` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `project_component_id CPD.id`.
2. B = event, `created_at T2`, but `project_component_id CPD.id`, `event_type "work_order_completed"`.

**When**
- `result = M.list_events(db, project_component_id=CPD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### PCAM-LI-14 — a component with no events gives an empty list
- **Rules:** `list_events` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `project_component_id CP2.id`.

**When**
- `result = M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCAM-LI-15 — the first element holds the stored metadata whole, or None
- **Rules:** `list_events` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `description "Attached a.png"`, `metadata_json {"attachment_id": 7, "file_name": "a.png", "sizes": [1, 2.5], "note": None}`.
2. B = event, `created_at T2`, but `metadata_json None`.

**When**
- `result = M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.
2. returns: `result[1][0].description == "Attached a.png"`.
3. returns: `result[1][0].metadata_json == {"attachment_id": 7, "file_name": "a.png", "sizes": [1, 2.5], "note": None}`.
4. returns: `result[0][0].metadata_json is None`.

### PCAM-LI-16 — each entry holds its own performer or None; one person is one instance
- **Rules:** `list_events` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `performed_by U2.id`.
2. B = event, `created_at T2`.
3. C = event, `created_at T3`, but `performed_by U1.id`.
4. D = event, `created_at T4`, but `performed_by U1.id`.

**When**
- `result = M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [D.id, C.id, B.id, A.id]`.
2. returns: `result[0][1].id == U1.id`.
3. returns: `result[1][1] is result[0][1]`.
4. returns: `result[2][1] is None`.
5. returns: `result[3][1].id == U2.id`.

### PCAM-LI-17 — with the defaults 100 of 101 entries come back, the newest
- **Rules:** `list_events` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. log(101).

**When**
- `result = M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `result[0][0].description == "E100"`.
3. returns: `result[99][0].description == "E1"`.

### PCAM-LI-18 — limit 1000 gives 1000 of 1000
- **Rules:** `list_events` R9, R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. log(1000).

**When**
- `result = M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 1000`.
2. returns: `result[0][0].description == "E999"`.
3. returns: `result[999][0].description == "E0"`.

### PCAM-LI-19 — limit 0 gives an empty list
- **Rules:** `list_events` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PCAM-LI-20 — skip at the number of rows gives an empty list
- **Rules:** `list_events` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.

**When**
- `result = M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PCAM-LI-21 — skip one below the number of rows gives the oldest row
- **Rules:** `list_events` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.

**When**
- `result = M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PCAM-LI-22 — a negative limit raises DataError
- **Rules:** `list_events` R9, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. nothing written: nothing written.

### PCAM-LI-23 — a negative skip raises DataError
- **Rules:** `list_events` R9, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. nothing written: nothing written.

### PCAM-LI-24 — one entry with a performer stays within three reads
- **Rules:** `list_events` R8, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `performed_by U1.id`.
2. sql_log started.

**When**
- `result = M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0][1].id == U1.id`.
3. statement: `len(sql_log) <= 3`.

### PCAM-LI-25 — five entries by one person make at most three reads
- **Rules:** `list_events` R8 [BUG-1712], R7
- **Kind:** bug
- **Expect:** xfail BUG-1712
- **Fails today on:** Then 3 (one read per entry: 7 reads)

**Given**
1. A = event, `created_at datetime(2026, 3, 1, 10, 0, 0)`, but `performed_by U1.id`.
2. B = event, `created_at datetime(2026, 3, 2, 10, 0, 0)`, but `performed_by U1.id`.
3. C = event, `created_at datetime(2026, 3, 3, 10, 0, 0)`, but `performed_by U1.id`.
4. D = event, `created_at datetime(2026, 3, 4, 10, 0, 0)`, but `performed_by U1.id`.
5. E = event, `created_at datetime(2026, 3, 5, 10, 0, 0)`, but `performed_by U1.id`.
6. sql_log started.

**When**
- `result = M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E.id, D.id, C.id, B.id, A.id]`.
2. returns: `[pair[1].id for pair in result] == [U1.id] * 5`.
3. statement: `len(sql_log) <= 3`.

### PCAM-LI-26 — entries by two people and by nobody make at most three reads
- **Rules:** `list_events` R8 [BUG-1712], R7
- **Kind:** bug
- **Expect:** xfail BUG-1712
- **Fails today on:** Then 3 (one read per entry with a performer: 6 reads)

**Given**
1. A = event, `created_at datetime(2026, 3, 1, 10, 0, 0)`, but `performed_by U1.id`.
2. B = event, `created_at datetime(2026, 3, 2, 10, 0, 0)`, but `performed_by U2.id`.
3. C = event, `created_at datetime(2026, 3, 3, 10, 0, 0)`.
4. D = event, `created_at datetime(2026, 3, 4, 10, 0, 0)`, but `performed_by U1.id`.
5. E = event, `created_at datetime(2026, 3, 5, 10, 0, 0)`, but `performed_by U2.id`.
6. sql_log started.

**When**
- `result = M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E.id, D.id, C.id, B.id, A.id]`.
2. returns: `[pair[1].id if pair[1] else None for pair in result] == [U2.id, U1.id, None, U2.id, U1.id]`.
3. statement: `len(sql_log) <= 3`.

### PCAM-LI-27 — writes nothing: a pending row stays pending, a caller's edit stays dirty
- **Rules:** `list_events` R10, Side effects, Overview
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. `P = ProjectComponentActivityEvent(workspace_id=W1.id, project_component_id=CP1.id, event_type="attachment_added", description="Pending", created_at=T2)`.
3. `db.add(P)` (not flushed).
4. `CP2.name = "Wall 2"` (not flushed).
5. sql_log started.

**When**
- `result = M.list_events(db, project_component_id=CP1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `P.id is None`.
5. session: `CP2 in db.dirty`.
6. session: `len(db.dirty) == 1`.
7. session: `not db.deleted`.
8. session: `CP2.name == "Wall 2"`.
9. statement: `written(sql_log) == []`.
10. statement: `locked(sql_log) == []`.
11. nothing written: nothing written.
12. unchanged: unchanged(A).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `list_events` R1, the DAO's detail: order after an update of the lower tied row, windows partition (DAO `get_by_component` R5–R7) | `tests/unit/dao/project_component_activity_event.cases.md` | Covered there. Here one order card (PCAM-LI-02) and one other-component negative, per the lighter target. |
| `log_event` R6, `list_events` R2 — the HTTP status | integration | the 404 reaches the client |
| `list_events` R9; HR-7; BUG-1198 | `GET /project-components/{id}/activity/` (endpoint and service, DAO spec FU-3) | `skip >= 0`, `1 <= limit <= 1000` (422 below 1), `require_component_access` first, response shape with `performer_name` |
| `log_event` R6; FU-1; OQ-10 | `WorkOrderManager._consume_item`, `finalize_completion` | what an order naming another workspace's component does after BUG-1192 (owner question OQ-10) |
| `log_event` R6; FU-2; BUG-1192 | `AttachmentManager` (`create_pending_attachment`, `confirm_attachment`, `_log_attachment_entity_events`) | sign and confirm refuse a foreign component; a delete skips the event for such a link and proceeds |
| Overview: two real concurrent transactions | integration | none here |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `log_event` R6, R8, R9 | After BUG-1192 the order of the component check against the performer, metadata and NOT NULL refusals is not stated (a foreign component with an unknown performer, say). Same gap as machine activity manager Spec gap 3. | No card combines two faults. Each refusal has its own card. |
| 2 | Facts; `log_event` R7, `list_events` R4 | The spec says "soft-deleted project" without naming the columns the real delete writes. `is_deleted`, `deleted_at`, `deleted_by` come from `project_event.cases.md`; whether the delete also changes `is_active` differs between the project and project event specs. | PJD uses the three columns, `is_active` not passed. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `log_event` | R1 | PCAM-LE-01, LE-02, LE-03, LE-04, LE-18 |
| `log_event` | R2 | PCAM-LE-05, LE-06, LE-07 |
| `log_event` | R3 | PCAM-LE-08 |
| `log_event` | R4 | PCAM-LE-09, LE-10 |
| `log_event` | R5 | PCAM-LE-12 |
| `log_event` | R6 [BUG-1192] | PCAM-LE-13, LE-14, LE-15, LE-16, LE-17 (xfail); LE-18 (own component of W2, pass) |
| `log_event` | R7 | PCAM-LE-19 |
| `log_event` | R8 | PCAM-LE-20, LE-21, LE-22 |
| `log_event` | R9 | PCAM-LE-23 |
| `log_event` | R10 | PCAM-LE-25 |
| `log_event` | Errors row 1 (404) [BUG-1192] | PCAM-LE-13, LE-14, LE-15, LE-16, LE-17 |
| `log_event` | Errors row 2 (Today: `IntegrityError` on unknown component / workspace) | no pass card (buggy path); LE-15, LE-16, LE-17 assert the intended 404 |
| `log_event` | Errors row 3 (unknown performer) | PCAM-LE-20, LE-21 |
| `log_event` | Errors row 4 (`None` type / description) | PCAM-LE-24 |
| `log_event` | Errors row 5 (over 50 characters) | PCAM-LE-11 |
| `log_event` | Errors row 6 (not JSON-serialisable) | PCAM-LE-23 |
| `log_event` | Side effects (one row, no commit, no lock) | PCAM-LE-04, LE-25 |
| `list_events` | R1 | PCAM-LI-01, LI-02, LI-03, LI-04, LI-12 |
| `list_events` | R2 | PCAM-LI-05, LI-06, LI-07, LI-08, LI-09, LI-10 |
| `list_events` | R3 | PCAM-LI-11, LI-12 |
| `list_events` | R4 | PCAM-LI-13 |
| `list_events` | R5 | PCAM-LI-14 |
| `list_events` | R6 | PCAM-LI-15 |
| `list_events` | R7 | PCAM-LI-16, LI-24 |
| `list_events` | R8 [BUG-1712] | PCAM-LI-24 (pass); LI-25, LI-26 (xfail) |
| `list_events` | R9 | PCAM-LI-17, LI-18, LI-19, LI-20, LI-21, LI-22, LI-23, LI-10 |
| `list_events` | R10 | PCAM-LI-27 |
| `list_events` | Errors row 1 (404) | PCAM-LI-05, LI-06, LI-07, LI-08, LI-09, LI-10, LI-11 |
| `list_events` | Errors row 2 (negative paging) | PCAM-LI-22, LI-23 |
