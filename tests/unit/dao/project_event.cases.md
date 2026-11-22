# Test cases — `app/dao/project_event.py`

> **Spec:** `tests/unit/dao/project_event.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (no questions; nothing open).
> **Revision:** 1 — the spec did not change. Additive, from `project_event.verify.md` (case-missing Findings 1 … 5; recipes R-1 … R-5): R-1 → PJE-G-19; R-2 → PJE-G-20; R-3 → PJE-G-18 Then 5, 6 (the old lines 5 … 7 move to 7 … 9) and PJE-G-21; R-4 → PJE-G-18 Then 10. R-5 → the soft-deleted parent in Conventions, its card unchanged. No ID retired.
> **Counts:** 21 cases · 21 expected-to-pass · 0 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Depth:** lighter target (skill step 1a): one list read, no write of its own, and no money, stock or order state written.
- **Per callable:** `get_by_project` 21.
- **Expected-to-fail:** none. This module's query has its full order, and no rule here carries a bug tag.
- **Notable design choices:**
  - "Writes nothing" is PJE-G-18, with PJE-G-21 for the empty result: a newer row added and not flushed must stay pending and alone in the session, no write statement is sent, and no lock clause. Readers have no commit spy.
  - Ties both ways: one tie card with no update (the expected row is physically last), one with the lower row updated (physically first). Neither alone rules out physical order.
  - Every filter negative puts the other row where it would change the result: newer than the expected row.
  - PJE-G-19 gives each tied row its own `event_type`, `description` and performer, so no other column can pass for `id`. PJE-G-20 has an older row with a higher id, one microsecond apart.
  - PJE-G-18 forbids `projects` by name, so neither a join nor a subquery can hide a closed parent's log.
  - The soft-deleted parent carries `deleted_at` and `deleted_by` too, as the real delete writes them (verify report, Finding 5).
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `PJE` = `app/dao/project_event.py`. `G` = get_by_project.

**Actors and fixed values.**
- `dao` = the singleton `project_event_dao` (`from app.dao.project_event import project_event_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `ProjectEvent` = `app.models.project_event.ProjectEvent`. `datetime`, `timedelta` = the `datetime` module's classes. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.
- T1 = `datetime(2026, 3, 4, 10, 0, 0)`, T2 = `datetime(2026, 3, 5, 10, 0, 0)`, T3 = `datetime(2026, 3, 6, 10, 0, 0)`.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces and the profile from `make_workspace`, `make_profile` of `tests/unit/factories.py`; the rest built directly, add + flush):
  - W1, W2 = two `workspaces` rows. U1 = a `profiles` row.
  - F1 = `factories` row (`Factory`): `workspace_id W1.id`, `name "Factory One"`, `abbreviation "F1"`. F9 = the same, but `workspace_id W2.id`, `name "Factory Nine"`, `abbreviation "F9"`.
  - PJ1 = `projects` row (`Project`): `workspace_id W1.id`, `factory_id F1.id`, `name "Project One"`, `description "Main"`. PJ2 = the same, but `name "Project Two"`. PJD = the same as PJ1, but `name "Project Three"`, `is_deleted True`, `deleted_at T3`, `deleted_by U1.id` (soft-deleted; `is_active` not passed). PJ9 = the same as PJ1, but `workspace_id W2.id`, `factory_id F9.id`, `name "Project Nine"`.
- **event** = `project_events` row built with `ProjectEvent`: `workspace_id W1.id`, `project_id PJ1.id`, `event_type "created"`, `description "Logged"`; `metadata_json` and `performed_by` are not passed. The card always gives `created_at`; after the word "but" it lists every other column that differs. `metadata_json None` means the keyword is passed with the value `None`.
- No `project_events` row exists unless the card's Given lists it.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned; the order is part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `project_events` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- **stored_json(X)** = `db.scalar(text("SELECT metadata::text FROM project_events WHERE id = :i"), {"i": X.id})` — `None` for SQL `NULL`, `"null"` for JSON `null`.
- `pending:` lines check the row P after the call, on the object itself; `db.new`, `db.dirty`, `db.deleted` are read from the session after the call, before anything expires it.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `project_events`; `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.


## `ProjectEventDAO.get_by_project`

### PJE-G-01 — returns a list of the project's rows of every event type
- **Rules:** `get_by_project` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `event_type "created"`.
2. B = event, `created_at T2`, but `event_type "component_deleted"`.
3. C = event, `created_at T3`, but `event_type "attachment_added"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.
3. returns: `isinstance(result[0], ProjectEvent)`.

### PJE-G-02 — a newer row of another project is not returned
- **Rules:** `get_by_project` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. C = event, `created_at T2`, but `project_id PJ2.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PJE-G-03 — the right project under another workspace returns an empty list
- **Rules:** `get_by_project` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PJE-G-04 — a newer W2 row on the same project is not returned
- **Rules:** `get_by_project` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. Z = event, `created_at T2`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PJE-G-05 — a W2 row on a project of W1 is returned for W2: only the row's workspace is compared
- **Rules:** `get_by_project` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = event, `created_at T1`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [Z.id]`.

### PJE-G-06 — a W2 row on a project of W1 is not returned for W1
- **Rules:** `get_by_project` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = event, `created_at T1`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PJE-G-07 — an unknown project id returns an empty list
- **Rules:** `get_by_project` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_project(db, project_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PJE-G-08 — project_id=0 returns an empty list
- **Rules:** `get_by_project` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_project(db, project_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PJE-G-09 — an unknown workspace returns an empty list
- **Rules:** `get_by_project` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PJE-G-10 — a project with no events returns an empty list
- **Rules:** `get_by_project` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_project(db, project_id=PJ2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PJE-G-11 — every event of a soft-deleted project is returned
- **Rules:** `get_by_project` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `project_id PJD.id`, `event_type "created"`.
2. B = event, `created_at T2`, but `project_id PJD.id`, `event_type "component_deleted"`.

**When**
- `result = dao.get_by_project(db, project_id=PJD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### PJE-G-12 — rows are ordered by created_at descending, then id descending
- **Rules:** `get_by_project` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T3`.
3. C = event, `created_at T1`.
4. D = event, `created_at T3`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [D.id, B.id, A.id, C.id]`.

### PJE-G-13 — on a created_at tie with no update the higher id comes first
- **Rules:** `get_by_project` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### PJE-G-14 — on a created_at tie the higher id still comes first after the lower row is updated
- **Rules:** `get_by_project` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T2`.
3. `A.description = "Edited"`, then `db.flush()`.
4. `db.expire_all()`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### PJE-G-15 — every matching row is returned: 158 rows give 158
- **Rules:** `get_by_project` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 158 events E1 … E158, built with `add_all`: Ek = event, `created_at` = `T1 + timedelta(minutes=k)`. `newest_first` = the ids of E158, E157, … E1, in that order.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 158`.
2. returns: `ids(result) == newest_first`.

### PJE-G-16 — a row comes back as stored, with its performer
- **Rules:** `get_by_project` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T2`, but `event_type "component_deleted"`, `description "Step done"`, `metadata_json {"status": "DONE", "note": "Shift 1"}`, `performed_by U1.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].workspace_id == W1.id`, `result[0].project_id == PJ1.id`, `result[0].event_type == "component_deleted"`.
3. returns: `result[0].description == "Step done"`, `result[0].created_at == T2`.
4. returns: `result[0].metadata_json == {"status": "DONE", "note": "Shift 1"}`.
5. returns: `result[0].performer.id == U1.id`.

### PJE-G-17 — SQL NULL and JSON null metadata both read back as None, and no performer gives None
- **Rules:** `get_by_project` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`, but `metadata_json None`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.
2. returns: `result[0].metadata_json is None`.
3. returns: `result[1].metadata_json is None`.
4. re-read A: `stored_json(A) is None`.
5. re-read B: `stored_json(B) == "null"`.
6. returns: `result[0].performer is None`.

### PJE-G-18 — writes nothing: a newer pending row stays pending and is not returned
- **Rules:** `get_by_project` R7, Side effects, Overview, R1, R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. `P = ProjectEvent(workspace_id=W1.id, project_id=PJ1.id, event_type="created", description="Pending", created_at=T2)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

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
10. statement: `"projects" not in sql`.

### PJE-G-19 — on a created_at tie id decides, not event_type, description or performer
- **Rules:** `get_by_project` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `U2`, `U3` = two more `profiles` rows (`make_profile`), made after U1, in that order.
2. A = event, `created_at T2`, but `event_type "b"`, `description "b"`, `performed_by U2.id`.
3. B = event, `created_at T2`, but `event_type "a"`, `description "a"`, `performed_by U1.id`.
4. C = event, `created_at T2`, but `event_type "c"`, `description "c"`, `performed_by U3.id`.
5. `db.expire_all()`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.


### PJE-G-20 — one microsecond inside one day decides the order, against id
- **Rules:** `get_by_project` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2 + timedelta(microseconds=1)`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.


### PJE-G-21 — writes nothing: with an empty result the pending row is still alone in the session
- **Rules:** `get_by_project` R7, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. `P = ProjectEvent(workspace_id=W1.id, project_id=PJ1.id, event_type="created", description="Pending", created_at=T2)`
3. `db.add(P)` (not flushed).

**When**
- `result = dao.get_by_project(db, project_id=PJ2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.
2. pending: `len(db.new) == 1`.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| R2 — the caller answers 404 for a project of another workspace before this method runs | `ProjectManager.list_events` | This DAO returns the row for its own workspace; the 404 is what keeps it out of a response. |
| FU-1 — BUG-1192 (HR-16): `log_event` refuses another workspace's project, 404 `Project with ID <id> not found`, nothing written | `ProjectManager.log_event` | The rule and the tag belong to that spec. No card here. |
| FU-2 — one profile read per event with a performer (pattern of BUG-1141) | `ProjectManager.list_events` | Not a rule of this DAO. |
| FU-3 — stored metadata validated by `ProjectEventMetadata` | `GET /projects/{id}/events/` | Not a rule of this DAO. |
| R4 — `ProjectManager.list_events` keeps answering for a soft-deleted project | `ProjectManager.list_events` | Here only the DAO's read. |
| Overview — writes through `log_event` and `log_for_component` | `ProjectManager` | No write of this DAO. |
| Generic behavior of inherited `BaseDAO` methods | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not specified here. |
| Notes: keyword-only parameters | none (no rule) | Spec gap 1. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes ("every parameter after `db` is keyword-only") | Stated as a note, not as a rule. | No card, as in `machine_activity_event.cases.md`. |
| 2 | Overview ("takes no lock") | Stands outside the numbered rules. | Covered anyway, as the Overview row of the matrix, by the "writes nothing" card. Its check looks for the word `FOR`, so it covers every lock form. Drop the line if it is not meant as a contract. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_project` | Returns | PJE-G-01 |
| `get_by_project` | R1 | PJE-G-01, PJE-G-02, PJE-G-18 |
| `get_by_project` | R2 | PJE-G-03, PJE-G-04, PJE-G-05, PJE-G-06 |
| `get_by_project` | R3 | PJE-G-07, PJE-G-08, PJE-G-09, PJE-G-10 |
| `get_by_project` | R4 | PJE-G-11, PJE-G-18 |
| `get_by_project` | R5 | PJE-G-12, PJE-G-13, PJE-G-14, PJE-G-19, PJE-G-20 |
| `get_by_project` | R6 | PJE-G-15 |
| `get_by_project` | R7 | PJE-G-16, PJE-G-17, PJE-G-18, PJE-G-21 |
| `get_by_project` | Overview | PJE-G-18 |
| `get_by_project` | Side effects | PJE-G-18, PJE-G-21 |
