# Test cases — `app/services/project_component_note_service.py`

> **Spec:** `tests/unit/services/project_component_note_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 3 (2026-11-06) — from `project_component_note_service.verify.md`: Finding 1 → new PCNS-L-22 (spied successful one-component read); Finding 2 → new PCNS-L-23 (W0 and W2 notes ahead of the page by id and by name; `limit=2` still gives the two W1 notes). Also new PCNS-G-10 (spied successful one-row read, requested with the revision). No card changed or retired.
> Revision 2 (2026-11-05) — spec fill-gaps G1: the schema module is named in Conventions. No card changed, added or retired.
> **Counts:** 64 cases · 44 expected-to-pass · 20 expected-to-fail (bugs) · 2 deferred

## Reviewer summary
- **Per callable:** `get_notes` 23 (8 bug) · `get_by_id_and_workspace` 10 (2 bug) · `create_note` 13 (4 bug) · `update_note` 13 (5 bug) · `delete_note` 5 (1 bug). `_guard_component` and `_filter_accessible_notes` are internal and covered through these.
- **Depth:** lighter (skill step 1a): notes write no stock, money or order state and every check is the project manager's guard. One card per rule and Errors row, one negative per filter (W0 lower id and W2 higher id on the by-id read), one paging boundary per rule, one recorder per unordered query. Full depth only on BUG-2293 (filter after paging): three hidden notes on a private project sort ahead of the visible ones by today's insertion order and by the intended name order (`limit=2` strict; `skip=1` non-strict, `Author: claude`, since today's order is physical).
- **Transactions (N-TC1–N-TC6):** every writer has a success card with commit/rollback spies, a guard refusal that discards an uncommitted extra row (rolled back once), a failing commit and (create, update) a failing refresh. Not-found paths of update/delete and every read keep an unflushed pending row in `db.new` (no commit, no rollback).
- **Pass-through:** BUG-1278 (a deleted project's component answers 404) is xfail on the guard paths, as `PRJM-RC-09`; it is today's behaviour of the manager.
- **Notable design choices:** PJ1 and C1 carry explicit ids (XID) so an event's `project_id` cannot equal the component id by chance. BUG-2293's "statements do not grow" is checked as "at most one statement reads `project_components`", with five notes on five components. Order cards for BUG-2292 are non-strict; one strict recorder card asserts an `ORDER BY` on `name`.
- **Revision 3:** every read path, success included, now has a spy card; L-23 pages across other workspaces' notes so the query's workspace filter is visible.
- **Needs a decision:** None. Gap 1 closed (spec G1).

## Conventions for this module

**IDs.** `PCNS` = `app/services/project_component_note_service.py`. `L` get_notes · `G` get_by_id_and_workspace · `C` create_note · `U` update_note · `D` delete_note.

**Actors and fixed values.**
- `svc` = `project_component_note_service` (`from app.services.project_component_note_service import ProjectComponentNoteService, project_component_note_service`). `db` = the test's real session, first positional argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- Models from `app.models.<module>`: `factory.Factory`, `project.Project`, `project_component.ProjectComponent`, `project_component_task.ProjectComponentTask`, `project_event.ProjectEvent`, `workspace_member.WorkspaceMember`, `project_member.ProjectMember`. `ProjectComponentNoteCreate`, `ProjectComponentNoteUpdate` (`app.schemas.project_component_note`). `HTTPException` (`fastapi`); `PydanticValidationError` = `pydantic.ValidationError`; `DataError` (`sqlalchemy.exc`); `event`, `insert`, `select`, `func` (`sqlalchemy`); `patch` (`unittest.mock`); `os`, `datetime`.
- MISSING = `999999999`. T0 = `datetime(2025, 12, 1, 8, 0, 0)`. XID(k) = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`.
- NOCOMP = `"Project component not found"`. NOACCESS = `"You do not have access to this project"`.

**Standing rows** (every test, built in this order, each added and flushed, no Given line):
- W0, W1, W2 = `make_workspace(db)` (so `W0.id < W1.id < W2.id`). U1 = `make_profile(db, name="Ana Rahman")`, U2 = `make_profile(db, name="Bilal Khan")`, UG = `make_profile(db, name="Mia Khan")`. In W1: `WorkspaceMember(workspace_id=W1.id, user_id=…, role=…, status="active")` for U1 `"ground-team"`, U2 `"owner"`, UG `"ground-team"`. U2 is privileged; UG is the plain caller.
- F0, F1, F9 = `Factory(workspace_id=W0.id / W1.id / W2.id, name="Factory Zero" / "Factory One" / "Factory Nine", abbreviation="F0" / "F1" / "F9")`.
- Projects, all `description="Main"`, `created_by=U1.id`: PJ0 = (W0, F0, `"Project Zero"`); PJ1 = (W1, F1, `"Project One"`, `id=XID(1)`); PJP = (W1, F1, `"Secret"`, `visibility="invited_only"`); PJD = (W1, F1, `"Gone"`, `is_deleted=True`, `deleted_at=T0`, `deleted_by=U1.id`); PJ9 = (W2, F9, `"Project Nine"`).
- Components `ProjectComponent(workspace_id, project_id, name)`: C0 = (W0, PJ0, `"Cellar"`); C1 = (W1, PJ1, `"Roof"`, `id=XID(5)`); C2 = (W1, PJ1, `"Wall"`); CP = (W1, PJP, `"Vault"`); CD = (W1, PJD, `"Floor"`); C9 = (W2, PJ9, `"Deck"`).
- No note, task or event row exists unless the Given builds it.

**Given rows.** Built directly (never through `svc`), added and flushed one at a time in the order written, so ids rise in that order. After "but" a line names every other column that differs.
- **note(C, "N")** = `ProjectComponentTask(workspace_id=C.workspace_id, project_component_id=C.id, name="N", description="Text", is_note=True)`. **task(C, "N")** = the same with `is_note=False`.
- **pmem(P, U)** = `ProjectMember(workspace_id=P.workspace_id, project_id=P.id, user_id=U.id, assigned_by=U1.id)`.
- **commit point** = after the last Given line the test runs `db.commit()` (releases a savepoint). Snapshots for `unchanged` and `nothing written` are taken there.
- **extra row X** (after the commit point) = `X = ProjectComponentTask(workspace_id=W2.id, project_component_id=C9.id, name="Extra", description="Extra", is_note=True)`, `db.add(X)`, `db.flush()`, `X_ID = X.id`; not committed.
- **pending P** (after the commit point) = `P = ProjectComponentTask(workspace_id=W2.id, project_component_id=C9.id, name="Pending", description="Pending", is_note=True)`, `db.add(P)`, **no flush**.
- A Given line written as code is a step run exactly as written.

**Externals.** None. Nothing is mocked except where a card says so.

**Named checks.**
- **re-read X** = `db.expire_all()`, then `db.get(<model>, X.id)`. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the numbers of `project_component_tasks` rows and of `project_events` rows (all workspaces) equal their values at the commit point.
- **x_gone** = `db.scalar(select(func.count()).select_from(ProjectComponentTask).where(ProjectComponentTask.id == X_ID)) == 0`.
- **events(P, t)** = `db.expire_all()`, then the `ProjectEvent` rows with `project_id == P.id` and `event_type == t`, ordered by `id`. **all_events(P)** = the same without the type filter. "that event" = the one row just counted.
- **idset(r)** = `{x.id for x in r}`. **names(r)** = `[x.name for x in r]` (order is part of the check).
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the call only (inside any `raises` block).
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the call. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the call.
- `raises: HTTPException` = plain `with pytest.raises(HTTPException) as exc:` around the call, **no** savepoint; then `exc.value.status_code`, `exc.value.detail`, one per line. `raises: DataError in a savepoint` = `with pytest.raises(DataError):` then `with db.begin_nested():` then the call. A `schema` card wraps only building the schema.
- `session:` lines check `db.new` / `db.dirty` / `db.deleted` right after the call, before any re-read or `expire_all`.
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line then reads with a fresh query.
- **recorder** = a Given step: `stmts = []`, `event.listen(db.connection(), "before_cursor_execute", rec)` where `rec` appends `statement`; `event.remove` right after the When. `sql` = the recorded `SELECT` whose text contains `FROM project_component_tasks`; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT` (`""` when none).

**xfail cards.** Strict unless the Expect line says `(non-strict)`: `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call and checks exactly as shown, also when the call uses something that does not exist yet.

**Race simulations.** None.

## `ProjectComponentNoteService.get_notes`

### PCNS-L-01 — with a component: that component's notes only, no tasks
- **Rules:** `get_notes` R1; `_guard_component` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. NA = note(C1, "Alpha").
2. TB = task(C1, "Beta").
3. NW = note(C2, "Wall note").

**When**
- `result = svc.get_notes(db, workspace_id=W1.id, user_id=UG.id, project_component_id=C1.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {NA.id}`.
2. returns: `all(x.is_note is True for x in result)`.

### PCNS-L-02 — component id 0 is 404, and the read neither commits nor rolls back
- **Rules:** `get_notes` R1, R7; N-TC6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. NA = note(C1, "Alpha") (commit point after this line).
2. pending P.

**When**
- spies: `svc.get_notes(db, workspace_id=W1.id, user_id=UG.id, project_component_id=0)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.
4. mock called: `rb.call_count == 0`.
5. mock called: `cm.call_count == 0`.
6. session: `P in db.new`.

### PCNS-L-03 — a component of a private project the caller may not open is 403
- **Rules:** `get_notes` R1; `_guard_component` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. NP = note(CP, "Plan") (commit point after this line).
2. pending P.

**When**
- `svc.get_notes(db, workspace_id=W1.id, user_id=UG.id, project_component_id=CP.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. session: `P in db.new`.

### PCNS-L-04 — a W0 component is 404 in W1
- **Rules:** `get_notes` R1; `_guard_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. N0 = note(C0, "Zero").

**When**
- `svc.get_notes(db, workspace_id=W1.id, user_id=U2.id, project_component_id=C0.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.

### PCNS-L-05 — a component of a deleted project is 404 for the project (pass-through)
- **Rules:** `get_notes` R1; `_guard_component` R1 (manager `require_component_access` R2 [BUG-1278])
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the notes are listed)

**Given**
1. ND = note(CD, "Gone note").

**When**
- `svc.get_notes(db, workspace_id=W1.id, user_id=U2.id, project_component_id=CD.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {PJD.id} not found"`.

### PCNS-L-06 — without a component: every W1 note a privileged caller may open, no tasks, no other workspace
- **Rules:** `get_notes` R2; `_filter_accessible_notes` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. N0 = note(C0, "Zero").
2. NA = note(C1, "Alpha").
3. NP = note(CP, "Plan").
4. TB = task(C1, "Beta").
5. N9 = note(C9, "Nine").

**When**
- `result = svc.get_notes(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {NA.id, NP.id}`.

### PCNS-L-07 — without a component: a plain caller does not see a private project's notes
- **Rules:** `get_notes` R2; `_filter_accessible_notes` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. NP = note(CP, "Plan").
2. NA = note(C1, "Alpha").

**When**
- `result = svc.get_notes(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {NA.id}`.

### PCNS-L-08 — membership of another private project does not open this one
- **Rules:** `_filter_accessible_notes` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. PJQ = `Project(workspace_id=W1.id, factory_id=F1.id, name="Other secret", description="Main", created_by=U1.id, visibility="invited_only")`.
2. CQ = `ProjectComponent(workspace_id=W1.id, project_id=PJQ.id, name="Annex")`.
3. pmem(PJQ, UG).
4. NQ = note(CQ, "Annex note").
5. NP = note(CP, "Plan").

**When**
- `result = svc.get_notes(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {NQ.id}`.

### PCNS-L-09 — a W1 note on a W2 component is left out
- **Rules:** `_filter_accessible_notes` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. NA = note(C1, "Alpha").
2. NX = note(C9, "Cross"), but `workspace_id W1.id` (invalid data, built only to prove the skip).

**When**
- `result = svc.get_notes(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {NA.id}`.

### PCNS-L-10 — a note on a W1 component whose project is in W2 is left out
- **Rules:** `_filter_accessible_notes` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. CX = `ProjectComponent(workspace_id=W1.id, project_id=PJ9.id, name="Stray")` (invalid data).
2. NA = note(C1, "Alpha").
3. NO = note(CX, "Odd").

**When**
- `result = svc.get_notes(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {NA.id}`.

### PCNS-L-11 — notes of a deleted project are not listed
- **Rules:** `get_notes` R5; `_filter_accessible_notes` R3 [BUG-2294]
- **Kind:** bug
- **Expect:** xfail BUG-2294
- **Fails today on:** Then 1 (ND is listed)

**Given**
1. ND = note(CD, "Gone note").
2. NA = note(C1, "Alpha").

**When**
- `result = svc.get_notes(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {NA.id}`.

### PCNS-L-12 — hidden notes ahead of the page do not shorten it (limit) *(revised 2026-11-27, order sweep)*
- **Rules:** `get_notes` R4 [BUG-2293]
- **Kind:** bug
- **Expect:** xfail BUG-2293 (non-strict): fails only when physical order puts the filtered-out row on the page; strict proof is PCNS-L-14, which checks the statement count only; no strict card proves the paging itself.
- **Fails today on:** Then 1 (the page is the three hidden notes' first two, filtered away: `[]`)

**Given**
1. H1 = note(CP, "Alpha").
2. H2 = note(CP, "Bravo").
3. H3 = note(CP, "Charlie").
4. VD = note(C1, "Delta").
5. VE = note(C1, "Echo").

**When**
- `result = svc.get_notes(db, workspace_id=W1.id, user_id=UG.id, skip=0, limit=2)`.

**Then**
1. returns: `idset(result) == {VD.id, VE.id}`.

### PCNS-L-13 — hidden notes ahead of the page do not shift it (skip)
- **Rules:** `get_notes` R4 [BUG-2293]
- **Kind:** bug
- **Expect:** xfail BUG-2293 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (skip 1 removes a hidden note: both VD and VE come back)

**Given**
1. H1 = note(CP, "Alpha").
2. H2 = note(CP, "Bravo").
3. H3 = note(CP, "Charlie").
4. VD = note(C1, "Delta").
5. VE = note(C1, "Echo").

**When**
- `result = svc.get_notes(db, workspace_id=W1.id, user_id=UG.id, skip=1, limit=1000)`.

**Then**
1. returns: `idset(result) == {VE.id}`.

### PCNS-L-14 — the access filter does not read one component per row
- **Rules:** `get_notes` R4 [BUG-2293]
- **Kind:** bug
- **Expect:** xfail BUG-2293
- **Fails today on:** Then 2 (one `project_components` read per note: 5)

**Given**
1. K1 … K5 = five `ProjectComponent(workspace_id=W1.id, project_id=PJ1.id, name=…)`, names `"K1"` … `"K5"`.
2. one note(Kn, "Kn note") on each of K1 … K5.
3. recorder.

**When**
- `result = svc.get_notes(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `len(result) == 5`.
2. statement: `sum(1 for s in stmts if "project_components" in s) <= 1`.

### PCNS-L-15 — the workspace-wide list is ordered by name, any case
- **Rules:** `get_notes` R3 [BUG-2292]
- **Kind:** bug
- **Expect:** xfail BUG-2292 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no `ORDER BY`: physical order "Zulu", "apple", "Banana")

**Given**
1. NZ = note(C1, "Zulu").
2. NA = note(C2, "apple").
3. NB = note(C1, "Banana").

**When**
- `result = svc.get_notes(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `names(result) == ["apple", "Banana", "Zulu"]`.

### PCNS-L-16 — names equal but for case tie on id
- **Rules:** `get_notes` R3 [BUG-2292]
- **Kind:** bug
- **Expect:** xfail BUG-2292 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no `ORDER BY`)

**Given**
1. NL = note(C1, "pump").
2. NU = note(C1, "Pump").
3. NA = note(C1, "Axle").

**When**
- `result = svc.get_notes(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `[x.id for x in result] == [NA.id, NL.id, NU.id]`.

### PCNS-L-17 — the workspace-wide query orders by name
- **Rules:** `get_notes` R3 [BUG-2292]
- **Kind:** bug
- **Expect:** xfail BUG-2292
- **Fails today on:** Then 2 (no `ORDER BY` in the SQL)

**Given**
1. NA = note(C1, "Alpha").
2. recorder.

**When**
- `result = svc.get_notes(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {NA.id}`.
2. statement: `"name" in order_part`.

### PCNS-L-18 — limit 0 gives an empty list
- **Rules:** `get_notes` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. NA = note(C1, "Alpha").

**When**
- `result = svc.get_notes(db, workspace_id=W1.id, user_id=U2.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PCNS-L-19 — the default limit is 100
- **Rules:** `get_notes` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(insert(ProjectComponentTask), [dict(workspace_id=W1.id, project_component_id=C1.id, name=f"N{i:03d}", description="Text", is_note=True) for i in range(101)])`, then `db.expire_all()`.

**When**
- `result = svc.get_notes(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `len(result) == 100`.

### PCNS-L-20 — a negative limit fails in the database
- **Rules:** `get_notes` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. NA = note(C1, "Alpha").

**When**
- `svc.get_notes(db, workspace_id=W1.id, user_id=U2.id, limit=-1)`.

**Then**
1. raises: `DataError` in a savepoint.

### PCNS-L-21 — the workspace-wide read neither commits nor rolls back
- **Rules:** `get_notes` R7; N-TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. NA = note(C1, "Alpha") (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.get_notes(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {NA.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.

### PCNS-L-22 — a successful one-component read neither commits nor rolls back
- **Rules:** `get_notes` R1, R7; N-TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. NA = note(C1, "Alpha") (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.get_notes(db, workspace_id=W1.id, user_id=UG.id, project_component_id=C1.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {NA.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.

### PCNS-L-23 — other workspaces' notes ahead of the page do not shorten it
- **Rules:** `get_notes` R2 ("`workspace_id` match")
- **Kind:** isolation
- **Expect:** pass

**Given**
1. N0 = note(C0, "Aa zero").
2. N9 = note(C9, "Ab nine").
3. NC = note(C1, "Ca one").
4. ND = note(C2, "Cb two").

**When**
- `result = svc.get_notes(db, workspace_id=W1.id, user_id=U2.id, skip=0, limit=2)`.

**Then**
1. returns: `idset(result) == {NC.id, ND.id}`.

## `ProjectComponentNoteService.get_by_id_and_workspace`

### PCNS-G-01 — a note the caller may open is returned
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. NA = note(C1, "Alpha").

**When**
- `result = svc.get_by_id_and_workspace(db, note_id=NA.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == NA.id`.
2. returns: `result.name == "Alpha"`.

### PCNS-G-02 — an unknown id is None, and the read neither commits nor rolls back
- **Rules:** `get_by_id_and_workspace` R1, R4; N-TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. NA = note(C1, "Alpha") (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.get_by_id_and_workspace(db, note_id=MISSING, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.

### PCNS-G-03 — id 0 is None
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. NA = note(C1, "Alpha").

**When**
- `result = svc.get_by_id_and_workspace(db, note_id=0, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.

### PCNS-G-04 — a W0 note (lower id) is None in W1
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. N0 = note(C0, "Zero").
2. NA = note(C1, "Alpha").

**When**
- `result = svc.get_by_id_and_workspace(db, note_id=N0.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.

### PCNS-G-05 — a W2 note (higher id) is None in W1
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. NA = note(C1, "Alpha").
2. N9 = note(C9, "Nine").

**When**
- `result = svc.get_by_id_and_workspace(db, note_id=N9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.

### PCNS-G-06 — a task id is not a note
- **Rules:** `get_by_id_and_workspace` R2 [BUG-2291]
- **Kind:** bug
- **Expect:** xfail BUG-2291
- **Fails today on:** Then 1 (the task is returned)

**Given**
1. TB = task(C1, "Weld frame").

**When**
- `result = svc.get_by_id_and_workspace(db, note_id=TB.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.

### PCNS-G-07 — a note of a private project the caller may not open is 403, with no rollback
- **Rules:** `get_by_id_and_workspace` R3, R4; N-TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. NP = note(CP, "Plan") (commit point after this line).
2. pending P.

**When**
- `svc.get_by_id_and_workspace(db, note_id=NP.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. session: `P in db.new`.

### PCNS-G-08 — a privileged caller opens a private project's note
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. NP = note(CP, "Plan").

**When**
- `result = svc.get_by_id_and_workspace(db, note_id=NP.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == NP.id`.

### PCNS-G-09 — a note of a deleted project is 404 (pass-through)
- **Rules:** `get_by_id_and_workspace` R3 (manager `require_component_access` R2 [BUG-1278])
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the note is returned)

**Given**
1. ND = note(CD, "Gone note").

**When**
- `svc.get_by_id_and_workspace(db, note_id=ND.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {PJD.id} not found"`.

### PCNS-G-10 — a successful one-row read neither commits nor rolls back
- **Rules:** `get_by_id_and_workspace` R3, R4; N-TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. NA = note(C1, "Alpha") (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.get_by_id_and_workspace(db, note_id=NA.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == NA.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.

## `ProjectComponentNoteService.create_note`

### PCNS-C-01 — the note is stored, committed once and returned re-read
- **Rules:** `create_note` R3, R5; N-TC1, N-TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No note in W1 (commit point after this line).

**When**
- spies: `result = svc.create_note(db, note_in=ProjectComponentNoteCreate(project_component_id=C1.id, name="Supplier call", description="Ring Monday"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`, `result.created_at is not None`.
2. returns: `result.is_note is True`, `result.name == "Supplier call"`.
3. mock called: `cm.call_count == 1`.
4. mock called: `rb.call_count == 0`.
5. committed: the row with id `result.id` has `workspace_id == W1.id`, `project_component_id == C1.id`, `name == "Supplier call"`, `description == "Ring Monday"`.
6. committed: that row has `is_note is True`, `is_completed is False`, `task_priority is None`.

### PCNS-C-02 — creating a note logs note_created on the component's project
- **Rules:** `create_note` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No note in W1 (commit point after this line).

**When**
- `result = svc.create_note(db, note_in=ProjectComponentNoteCreate(project_component_id=C1.id, name="Supplier call", description="Ring Monday"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: events(PJ1, "note_created") has exactly 1 row.
3. event: that event `workspace_id == W1.id`, `performed_by == UG.id`, `description == 'Added note "Supplier call"'`.
4. event: that event `metadata_json == {"note_id": result.id, "note_name": "Supplier call", "component_id": C1.id, "component_name": "Roof"}`.
5. count: all_events(PJ1) has exactly 1 row.

### PCNS-C-03 — a private component the caller may not open: 403, rolled back once, pending changes discarded
- **Rules:** `create_note` R1; N-TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. No note in W1 (commit point after this line).
2. extra row X.

**When**
- spies: `svc.create_note(db, note_in=ProjectComponentNoteCreate(project_component_id=CP.id, name="Plan", description="Text"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. mock called: `rb.call_count == 1`.
5. session: `not db.new`.
6. count: x_gone.
7. nothing written.

### PCNS-C-04 — an unknown component is 404, nothing written
- **Rules:** `create_note` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No note in W1 (commit point after this line).

**When**
- `svc.create_note(db, note_in=ProjectComponentNoteCreate(project_component_id=MISSING, name="Plan", description="Text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.
4. session: `not db.new`.
5. nothing written.

### PCNS-C-05 — a W2 component is 404 in W1, nothing written
- **Rules:** `create_note` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No note in W1 (commit point after this line).

**When**
- `svc.create_note(db, note_in=ProjectComponentNoteCreate(project_component_id=C9.id, name="Plan", description="Text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.
4. nothing written.

### PCNS-C-06 — a deleted project's component is 404, nothing written (pass-through)
- **Rules:** `create_note` R1 (manager `require_component_access` R2 [BUG-1278])
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the note is created)

**Given**
1. No note in W1 (commit point after this line).

**When**
- `svc.create_note(db, note_in=ProjectComponentNoteCreate(project_component_id=CD.id, name="Plan", description="Text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {PJD.id} not found"`.
4. nothing written.

### PCNS-C-07 — a whitespace-only name is refused by the schema
- **Rules:** `create_note` R2 [BUG-2290]
- **Kind:** bug
- **Expect:** xfail BUG-2290
- **Fails today on:** Then 1 (the schema accepts `"   "`)

**Given**
1. No note in W1.

**When**
- build `ProjectComponentNoteCreate(project_component_id=C1.id, name="   ", description="Text")` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCNS-C-08 — an empty name is refused by the schema
- **Rules:** `create_note` R2 [BUG-2290]
- **Kind:** bug
- **Expect:** xfail BUG-2290
- **Fails today on:** Then 1 (the schema accepts `""`)

**Given**
1. No note in W1.

**When**
- build `ProjectComponentNoteCreate(project_component_id=C1.id, name="", description="Text")` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCNS-C-09 — the name is stored trimmed
- **Rules:** `create_note` R2 [BUG-2290]
- **Kind:** bug
- **Expect:** xfail BUG-2290
- **Fails today on:** Then 2 (stored as typed: `"  Supplier  call  "`)

**Given**
1. No note in W1 (commit point after this line).

**When**
- `result = svc.create_note(db, note_in=ProjectComponentNoteCreate(project_component_id=C1.id, name="  Supplier  call  ", description="Text"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the row `result.id`: `name == "Supplier  call"`.

### PCNS-C-10 — the description is kept as typed, empty included
- **Rules:** `create_note` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No note in W1 (commit point after this line).

**When**
- `result = svc.create_note(db, note_in=ProjectComponentNoteCreate(project_component_id=C1.id, name="Call", description=""), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.description == ""`.
2. re-read the row `result.id`: `description == ""`, `name == "Call"`.

### PCNS-C-11 — the description is required by the schema
- **Rules:** `create_note` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No note in W1.

**When**
- build `ProjectComponentNoteCreate(project_component_id=C1.id, name="Call")` (target `schema`; `description` not sent).

**Then**
1. raises: `PydanticValidationError`.

### PCNS-C-12 — a failing commit rolls back once and nothing is saved
- **Rules:** `create_note` R5; N-TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. No note in W1 (commit point after this line).

**When**
- failing commit: `svc.create_note(db, note_in=ProjectComponentNoteCreate(project_component_id=C1.id, name="Call", description="Text"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. nothing written.

### PCNS-C-13 — a failing re-read after the commit leaves the note and its event saved
- **Rules:** `create_note` R5; N-TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. No note in W1 (commit point after this line).

**When**
- failing refresh: `svc.create_note(db, note_in=ProjectComponentNoteCreate(project_component_id=C1.id, name="Call", description="Text"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: C1 has exactly 1 `project_component_tasks` row, `name == "Call"`.
3. committed: events(PJ1, "note_created") has exactly 1 row.

## `ProjectComponentNoteService.update_note`

### PCNS-U-01 — a rename is stored, committed and returned; the description stays
- **Rules:** `update_note` R2, R5; N-TC1, N-TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. N = note(C1, "Old") (commit point after this line).

**When**
- spies: `result = svc.update_note(db, note_id=N.id, note_in=ProjectComponentNoteUpdate(name="New"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == N.id`, `result.name == "New"`.
2. mock called: `cm.call_count == 1`.
3. committed: the row N has `name == "New"`, `description == "Text"`.
4. committed: the row N has `is_note is True`, `project_component_id == C1.id`.

### PCNS-U-02 — an update logs note_updated with the new name
- **Rules:** `update_note` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. N = note(C1, "Old") (commit point after this line).

**When**
- `result = svc.update_note(db, note_id=N.id, note_in=ProjectComponentNoteUpdate(name="New"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.name == "New"`.
2. event: events(PJ1, "note_updated") has exactly 1 row.
3. event: that event `performed_by == UG.id`, `description == 'Updated note "New"'`.
4. event: that event `metadata_json == {"note_id": N.id, "note_name": "New", "component_id": C1.id, "component_name": "Roof"}`.

### PCNS-U-03 — a null name leaves the name; the description changes
- **Rules:** `update_note` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = note(C1, "Old") (commit point after this line).

**When**
- `result = svc.update_note(db, note_id=N.id, note_in=ProjectComponentNoteUpdate(name=None, description="Changed"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.name == "Old"`.
2. re-read N: `name == "Old"`, `description == "Changed"`.

### PCNS-U-04 — an unknown id returns None with no commit and no rollback
- **Rules:** `update_note` R1; N-TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. N = note(C1, "Old") (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.update_note(db, note_id=MISSING, note_in=ProjectComponentNoteUpdate(name="New"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.
5. session: `not db.dirty`.
6. unchanged: unchanged(N).

### PCNS-U-05 — a task id is not found through the note pages
- **Rules:** `update_note` R1 [BUG-2291]
- **Kind:** bug
- **Expect:** xfail BUG-2291
- **Fails today on:** Then 1 (the task is renamed and returned)

**Given**
1. TB = task(C1, "Weld frame") (commit point after this line).

**When**
- `result = svc.update_note(db, note_id=TB.id, note_in=ProjectComponentNoteUpdate(name="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(TB).
3. nothing written.

### PCNS-U-06 — a private project's note: 403, rolled back once, pending changes discarded
- **Rules:** `update_note` R1; N-TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. NP = note(CP, "Plan") (commit point after this line).
2. extra row X.

**When**
- spies: `svc.update_note(db, note_id=NP.id, note_in=ProjectComponentNoteUpdate(name="New"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. mock called: `rb.call_count == 1`.
5. session: `not db.dirty`.
6. count: x_gone.
7. unchanged: unchanged(NP).
8. nothing written.

### PCNS-U-07 — an empty update writes no event
- **Rules:** `update_note` R4 [BUG-2295]
- **Kind:** bug
- **Expect:** xfail BUG-2295
- **Fails today on:** Then 2 (one `note_updated` event is written)

**Given**
1. N = note(C1, "Old") (commit point after this line).

**When**
- `result = svc.update_note(db, note_id=N.id, note_in=ProjectComponentNoteUpdate(), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == N.id`.
2. event: all_events(PJ1) has exactly 0 rows.

### PCNS-U-08 — sending the same values writes no event
- **Rules:** `update_note` R4 [BUG-2295]
- **Kind:** bug
- **Expect:** xfail BUG-2295
- **Fails today on:** Then 2 (one `note_updated` event is written)

**Given**
1. N = note(C1, "Old") (commit point after this line).

**When**
- `result = svc.update_note(db, note_id=N.id, note_in=ProjectComponentNoteUpdate(name="Old", description="Text"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.name == "Old"`.
2. event: all_events(PJ1) has exactly 0 rows.

### PCNS-U-09 — a sent name is stored trimmed
- **Rules:** `update_note` R3 [BUG-2290]
- **Kind:** bug
- **Expect:** xfail BUG-2290
- **Fails today on:** Then 2 (stored `"  New  "`)

**Given**
1. N = note(C1, "Old") (commit point after this line).

**When**
- `result = svc.update_note(db, note_id=N.id, note_in=ProjectComponentNoteUpdate(name="  New  "), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == N.id`.
2. re-read N: `name == "New"`.

### PCNS-U-10 — a blank name is refused by the update schema
- **Rules:** `update_note` R3 [BUG-2290]
- **Kind:** bug
- **Expect:** xfail BUG-2290
- **Fails today on:** Then 1 (the schema accepts `"  "`)

**Given**
1. No note in W1.

**When**
- build `ProjectComponentNoteUpdate(name="  ")` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCNS-U-11 — a failing commit rolls back once and the note is unchanged
- **Rules:** `update_note` R5; N-TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. N = note(C1, "Old") (commit point after this line).

**When**
- failing commit: `svc.update_note(db, note_id=N.id, note_in=ProjectComponentNoteUpdate(name="New"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. unchanged: unchanged(N).
4. nothing written.

### PCNS-U-12 — a failing re-read after the commit leaves the rename saved
- **Rules:** `update_note` R5; N-TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. N = note(C1, "Old") (commit point after this line).

**When**
- failing refresh: `svc.update_note(db, note_id=N.id, note_in=ProjectComponentNoteUpdate(name="New"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: the row N has `name == "New"`.

### PCNS-U-13 — a W2 note is not found in W1
- **Rules:** `update_note` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. N9 = note(C9, "Nine") (commit point after this line).

**When**
- `result = svc.update_note(db, note_id=N9.id, note_in=ProjectComponentNoteUpdate(name="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(N9).

## `ProjectComponentNoteService.delete_note`

### PCNS-D-01 — the note is deleted after its note_deleted event, committed, True
- **Rules:** `delete_note` R2, R3; N-TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. N = note(C1, "Old").
2. NK = note(C1, "Keep") (commit point after this line).

**When**
- spies: `result = svc.delete_note(db, note_id=N.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is True`.
2. mock called: `cm.call_count == 1`.
3. committed: no `project_component_tasks` row has id `N.id`.
4. committed: the row NK exists.
5. committed: events(PJ1, "note_deleted") has exactly 1 row, `performed_by == UG.id`, `description == 'Deleted note "Old"'`.
6. committed: that event `metadata_json == {"note_id": N.id, "note_name": "Old", "component_id": C1.id, "component_name": "Roof"}`.

### PCNS-D-02 — an unknown id returns False with no commit and no rollback
- **Rules:** `delete_note` R1; N-TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. N = note(C1, "Old") (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.delete_note(db, note_id=MISSING, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is False`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.
5. session: `not db.deleted`.
6. unchanged: unchanged(N).

### PCNS-D-03 — a task id is not deleted through the note pages
- **Rules:** `delete_note` R1 [BUG-2291]
- **Kind:** bug
- **Expect:** xfail BUG-2291
- **Fails today on:** Then 1 (the task is deleted: `True`)

**Given**
1. TB = task(C1, "Weld frame") (commit point after this line).

**When**
- `result = svc.delete_note(db, note_id=TB.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is False`.
2. unchanged: unchanged(TB).
3. nothing written.

### PCNS-D-04 — a private project's note: 403, rolled back once, the note stays
- **Rules:** `delete_note` R1; N-TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. NP = note(CP, "Plan") (commit point after this line).
2. extra row X.

**When**
- spies: `svc.delete_note(db, note_id=NP.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. mock called: `rb.call_count == 1`.
5. session: `not db.deleted`.
6. count: x_gone.
7. unchanged: unchanged(NP).
8. nothing written.

### PCNS-D-05 — a failing commit rolls back once; the note and no event remain
- **Rules:** `delete_note` R3; N-TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. N = note(C1, "Old") (commit point after this line).

**When**
- failing commit: `svc.delete_note(db, note_id=N.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. unchanged: unchanged(N).
4. nothing written.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_notes` R6 [BUG-2296] | `GET /project-component-notes/` | `limit=0` → 422; `limit` 1 and 100 accepted |
| Integration-only | `/project-component-notes/` endpoints | `None` / `False` → 404 `Project component note not found`; schema errors → 422 (BUG-461) |

## Spec gaps
None. Gap 1 closed by spec Gap log G1 (2026-11-04): schema module named.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_guard_component` | R1 | PCNS-L-01 … L-05, G-07, G-09, C-03 … C-06 |
| `_filter_accessible_notes` | R1 | PCNS-L-09 |
| `_filter_accessible_notes` | R2 | PCNS-L-06, L-07, L-08, L-10 |
| `_filter_accessible_notes` | R3 [BUG-2294] | PCNS-L-11 |
| `_filter_accessible_notes` | R4 (empty input) | PCNS-L-18 (indirect: nothing to filter) |
| `get_notes` | R1 | PCNS-L-01 … L-04; L-05 [BUG-1278] |
| `get_notes` | R2 | PCNS-L-06, L-07, L-23 |
| `get_notes` | R3 [BUG-2292] | PCNS-L-15, L-16, L-17 |
| `get_notes` | R4 [BUG-2293] | PCNS-L-12, L-13, L-14 |
| `get_notes` | R5 [BUG-2294] | PCNS-L-11 |
| `get_notes` | R6 | PCNS-L-18, L-19, L-20; endpoint part deferred |
| `get_notes` | R7 / N-TC6 | PCNS-L-02, L-03, L-21, L-22 |
| `get_by_id_and_workspace` | R1 | PCNS-G-02 … G-05 |
| `get_by_id_and_workspace` | R2 [BUG-2291] | PCNS-G-06 |
| `get_by_id_and_workspace` | R3 | PCNS-G-01, G-07, G-08; G-09 [BUG-1278] |
| `get_by_id_and_workspace` | R4 / N-TC6 | PCNS-G-02, G-07, G-10 |
| `create_note` | R1 / Errors | PCNS-C-03, C-04, C-05; C-06 [BUG-1278] |
| `create_note` | R2 [BUG-2290] | PCNS-C-07, C-08, C-09; description C-10, C-11 |
| `create_note` | R3 | PCNS-C-01 |
| `create_note` | R4 | PCNS-C-02 |
| `create_note` | R5 / N-TC1–N-TC5 | PCNS-C-01, C-03, C-12, C-13 |
| `update_note` | R1 | PCNS-U-04, U-06, U-13; U-05 [BUG-2291] |
| `update_note` | R2 | PCNS-U-01, U-03 |
| `update_note` | R3 [BUG-2290] | PCNS-U-09, U-10 |
| `update_note` | R4 | PCNS-U-02; U-07, U-08 [BUG-2295] |
| `update_note` | R5 / N-TC1–N-TC5 | PCNS-U-01, U-06, U-11, U-12 |
| `delete_note` | R1 | PCNS-D-02, D-04; D-03 [BUG-2291] |
| `delete_note` | R2 | PCNS-D-01 |
| `delete_note` | R3 / N-TC1, N-TC3, N-TC4 | PCNS-D-01, D-04, D-05 |
