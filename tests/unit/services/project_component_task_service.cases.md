# Test cases — `app/services/project_component_task_service.py`

> **Spec:** `tests/unit/services/project_component_task_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 3 (2026-11-06) — from `project_component_task_service.verify.md`: Finding 1 → new PCTS-L-29 (spied successful one-component read). Also new PCTS-G-10 (spied successful one-row read, requested with the revision). Surviving mutant #40 is equivalent: no card. No card changed or retired.
> Revision 2 (2026-11-05) — spec fill-gaps G1, G2: schema module and `TaskPriorityEnum` (`app.models.enums`: LOW, MEDIUM, HIGH, URGENT) named in Conventions. New PCTS-U-28 (HIGH → URGENT, `update_task` R2, R4). No card changed or retired.
> **Counts:** 88 cases · 61 expected-to-pass · 27 expected-to-fail (bugs) · 2 deferred

## Reviewer summary
- **Per callable:** `get_tasks` 29 (11 bug) · `get_by_id` 10 (1 bug) · `create_task` 15 (4 bug) · `update_task` 28 (10 bug) · `delete_task` 6 (1 bug). `_guard_component` and `_filter_accessible_tasks` are internal and covered through these.
- **Depth:** lighter (skill step 1a): tasks write no stock, money or order state; access is the project manager's guard. One card per rule and Errors row, one negative per filter, one paging boundary per rule, one recorder per unordered query. Full depth on BUG-2298 (filter after paging): three hidden tasks on a private project sort ahead of the visible ones both by insertion order (today) and by name (intended): `limit=2` strict, `skip=1` non-strict (`Author: claude`, today's order is physical until BUG-100).
- **Event choice (`update_task` R4–R6):** one card each for completed, reopened, complete + rename (only `task_completed`), completion sent but unchanged (`task_updated`), task → note (BUG-2305), note → note (none), note → task (`task_updated`), and no change (BUG-2303). The stored `is_note` of a task turned into a note has its own passing card beside the BUG-2305 card.
- **Transactions (T-TC1–T-TC6):** per writer a success card with spies, a guard refusal that discards an uncommitted extra row (one rollback), a failing commit and (create, update) a failing refresh; not-found update/delete and every read keep an unflushed pending row (no commit, no rollback).
- **Pass-through:** BUG-1278 (a deleted project's component → 404) xfail on the guard paths, as `PRJM-RC-09`.
- **Notable design choices:** PJ1 and C1 have explicit ids (XID) so an event's `project_id` can never equal the component id by chance. BUG-2298's "statements do not grow" is "at most one statement reads `project_components`" over five components.
- **Revision 3:** every read path, success included, now has a spy card.
- **Needs a decision:** None. Gaps 1–2 closed (spec G1, G2); the set-to-set priority change is PCTS-U-28.

## Conventions for this module

**IDs.** `PCTS` = `app/services/project_component_task_service.py`. `L` get_tasks · `G` get_by_id · `C` create_task · `U` update_task · `D` delete_task.

**Actors and fixed values.**
- `svc` = `project_component_task_service` (`from app.services.project_component_task_service import ProjectComponentTaskService, project_component_task_service`). `db` = the test's real session, first positional argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- Models from `app.models.<module>`: `factory.Factory`, `project.Project`, `project_component.ProjectComponent`, `project_component_task.ProjectComponentTask`, `project_event.ProjectEvent`, `workspace_member.WorkspaceMember`, `project_member.ProjectMember`. `ProjectComponentTaskCreate`, `ProjectComponentTaskUpdate` (`app.schemas.project_component_task`). `TaskPriorityEnum` (`app.models.enums`; members LOW, MEDIUM, HIGH, URGENT, values equal names): HIGH = `TaskPriorityEnum.HIGH`, URGENT = `TaskPriorityEnum.URGENT`. `HTTPException` (`fastapi`); `PydanticValidationError` = `pydantic.ValidationError`; `DataError` (`sqlalchemy.exc`); `event`, `insert`, `select`, `func` (`sqlalchemy`); `patch` (`unittest.mock`); `os`, `datetime`.
- MISSING = `999999999`. T0 = `datetime(2025, 12, 1, 8, 0, 0)`. XID(k) = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`.
- NOCOMP = `"Project component not found"`. NOACCESS = `"You do not have access to this project"`.

**Standing rows** (every test, built in this order, each added and flushed, no Given line):
- W0, W1, W2 = `make_workspace(db)` (so `W0.id < W1.id < W2.id`). U1 = `make_profile(db, name="Ana Rahman")`, U2 = `make_profile(db, name="Bilal Khan")`, UG = `make_profile(db, name="Mia Khan")`. In W1: `WorkspaceMember(workspace_id=W1.id, user_id=…, role=…, status="active")` for U1 `"ground-team"`, U2 `"owner"`, UG `"ground-team"`. U2 is privileged; UG is the plain caller.
- F0, F1, F9 = `Factory(workspace_id=W0.id / W1.id / W2.id, name="Factory Zero" / "Factory One" / "Factory Nine", abbreviation="F0" / "F1" / "F9")`.
- Projects, all `description="Main"`, `created_by=U1.id`: PJ0 = (W0, F0, `"Project Zero"`); PJ1 = (W1, F1, `"Project One"`, `id=XID(1)`); PJP = (W1, F1, `"Secret"`, `visibility="invited_only"`); PJD = (W1, F1, `"Gone"`, `is_deleted=True`, `deleted_at=T0`, `deleted_by=U1.id`); PJ9 = (W2, F9, `"Project Nine"`).
- Components `ProjectComponent(workspace_id, project_id, name)`: C0 = (W0, PJ0, `"Cellar"`); C1 = (W1, PJ1, `"Roof"`, `id=XID(5)`); C2 = (W1, PJ1, `"Wall"`); CP = (W1, PJP, `"Vault"`); CD = (W1, PJD, `"Floor"`); C9 = (W2, PJ9, `"Deck"`).
- No task, note or event row exists unless the Given builds it.

**Given rows.** Built directly (never through `svc`), added and flushed one at a time in the order written, so ids rise in that order. After "but" a line names every other column that differs.
- **task(C, "N")** = `ProjectComponentTask(workspace_id=C.workspace_id, project_component_id=C.id, name="N", description="Text", is_note=False)` (`is_completed` default `False`, `task_priority` default `NULL`). **note(C, "N")** = the same with `is_note=True`.
- **pmem(P, U)** = `ProjectMember(workspace_id=P.workspace_id, project_id=P.id, user_id=U.id, assigned_by=U1.id)`.
- **commit point** = after the last Given line the test runs `db.commit()` (releases a savepoint). Snapshots for `unchanged` and `nothing written` are taken there.
- **extra row X** (after the commit point) = `X = ProjectComponentTask(workspace_id=W2.id, project_component_id=C9.id, name="Extra", description="Extra")`, `db.add(X)`, `db.flush()`, `X_ID = X.id`; not committed.
- **pending P** (after the commit point) = `P = ProjectComponentTask(workspace_id=W2.id, project_component_id=C9.id, name="Pending", description="Pending")`, `db.add(P)`, **no flush**.
- A Given line written as code is a step run exactly as written.

**Externals.** None. Nothing is mocked except where a card says so.

**Named checks.**
- **re-read X** = `db.expire_all()`, then `db.get(<model>, X.id)`. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the numbers of `project_component_tasks` rows and of `project_events` rows (all workspaces) equal their values at the commit point.
- **x_gone** = `db.scalar(select(func.count()).select_from(ProjectComponentTask).where(ProjectComponentTask.id == X_ID)) == 0`.
- **events(P, t)** = `db.expire_all()`, then the `ProjectEvent` rows with `project_id == P.id` and `event_type == t`, ordered by `id`. **all_events(P)** = the same without the type filter. "that event" = the one row just counted.
- **META(T, "n")** = `{"task_id": T.id, "task_name": "n", "component_id": C1.id, "component_name": "Roof"}`.
- **idset(r)** = `{x.id for x in r}`. **names(r)** = `[x.name for x in r]` (order is part of the check).
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the call only (inside any `raises` block).
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the call. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the call.
- `raises: HTTPException` = plain `with pytest.raises(HTTPException) as exc:` around the call, **no** savepoint; then `exc.value.status_code`, `exc.value.detail`, one per line. `raises: DataError in a savepoint` = `with pytest.raises(DataError):` then `with db.begin_nested():` then the call. A `schema` card wraps only building the schema.
- `session:` lines check `db.new` / `db.dirty` / `db.deleted` right after the call, before any re-read or `expire_all`.
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line then reads with a fresh query.
- **recorder** = a Given step: `stmts = []`, `event.listen(db.connection(), "before_cursor_execute", rec)` where `rec` appends `statement`; `event.remove` right after the When. `sql` = the recorded `SELECT` whose text contains `FROM project_component_tasks`; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT` (`""` when none).

**xfail cards.** Strict unless the Expect line says `(non-strict)`: `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call and checks exactly as shown, also when the call uses something that does not exist yet.

**Race simulations.** None.

## `ProjectComponentTaskService.get_tasks`

### PCTS-L-01 — with a component and no filter: its tasks and notes, open and done
- **Rules:** `get_tasks` R1, R2; `_guard_component` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = task(C1, "Alpha").
2. TD = task(C1, "Done"), but `is_completed True`.
3. NN = note(C1, "Remark").
4. TW = task(C2, "Wall task").

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=UG.id, project_component_id=C1.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {TA.id, TD.id, NN.id}`.

### PCTS-L-02 — with a component and is_note False: tasks only
- **Rules:** `get_tasks` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = task(C1, "Alpha").
2. TD = task(C1, "Done"), but `is_completed True`.
3. NN = note(C1, "Remark").

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=UG.id, project_component_id=C1.id, is_note=False, limit=1000)`.

**Then**
1. returns: `idset(result) == {TA.id, TD.id}`.

### PCTS-L-03 — open only, kind not given: open tasks, no notes
- **Rules:** `get_tasks` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = task(C1, "Alpha").
2. TD = task(C1, "Done"), but `is_completed True`.
3. NN = note(C1, "Remark").

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=UG.id, project_component_id=C1.id, incomplete_only=True, limit=1000)`.

**Then**
1. returns: `idset(result) == {TA.id}`.

### PCTS-L-04 — open only with is_note True: open notes
- **Rules:** `get_tasks` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = task(C1, "Alpha").
2. NN = note(C1, "Remark").
3. ND = note(C1, "Closed remark"), but `is_completed True`.

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=UG.id, project_component_id=C1.id, incomplete_only=True, is_note=True, limit=1000)`.

**Then**
1. returns: `idset(result) == {NN.id}`.

### PCTS-L-05 — component id 0 is a component id: 404
- **Rules:** `get_tasks` R1 [BUG-2301]
- **Kind:** bug
- **Expect:** xfail BUG-2301
- **Fails today on:** Then 1 (no error: the workspace-wide list is returned)

**Given**
1. TA = task(C1, "Alpha").

**When**
- `svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id, project_component_id=0)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.

### PCTS-L-06 — a private component the caller may not open is 403, with no rollback
- **Rules:** `get_tasks` R1, R7; T-TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. TP = task(CP, "Plan") (commit point after this line).
2. pending P.

**When**
- spies: `svc.get_tasks(db, workspace_id=W1.id, user_id=UG.id, project_component_id=CP.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. mock called: `rb.call_count == 0`.
5. session: `P in db.new`.

### PCTS-L-07 — a W0 component is 404 in W1
- **Rules:** `get_tasks` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. TK0 = task(C0, "Zero").

**When**
- `svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id, project_component_id=C0.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.

### PCTS-L-08 — a deleted project's component is 404 for the project (pass-through)
- **Rules:** `get_tasks` R1 (manager `require_component_access` R2 [BUG-1278])
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the tasks are listed)

**Given**
1. TG = task(CD, "Gone task").

**When**
- `svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id, project_component_id=CD.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {PJD.id} not found"`.

### PCTS-L-09 — without a component: every W1 task and note a privileged caller may open
- **Rules:** `get_tasks` R3; `_filter_accessible_tasks` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TK0 = task(C0, "Zero").
2. TA = task(C1, "Alpha").
3. NN = note(C2, "Remark").
4. TP = task(CP, "Plan").
5. T9 = task(C9, "Nine").

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {TA.id, NN.id, TP.id}`.

### PCTS-L-10 — without a component: a plain caller does not see a private project's tasks
- **Rules:** `_filter_accessible_tasks` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TP = task(CP, "Plan").
2. TA = task(C1, "Alpha").

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {TA.id}`.

### PCTS-L-11 — membership of another private project does not open this one
- **Rules:** `_filter_accessible_tasks` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. PJQ = `Project(workspace_id=W1.id, factory_id=F1.id, name="Other secret", description="Main", created_by=U1.id, visibility="invited_only")`.
2. CQ = `ProjectComponent(workspace_id=W1.id, project_id=PJQ.id, name="Annex")`.
3. pmem(PJQ, UG).
4. TQ = task(CQ, "Annex task").
5. TP = task(CP, "Plan").

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {TQ.id}`.

### PCTS-L-12 — a W1 task on a W2 component is left out
- **Rules:** `_filter_accessible_tasks` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. TA = task(C1, "Alpha").
2. TX = task(C9, "Cross"), but `workspace_id W1.id` (invalid data).

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {TA.id}`.

### PCTS-L-13 — a task on a W1 component whose project is in W2 is left out
- **Rules:** `_filter_accessible_tasks` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. CX = `ProjectComponent(workspace_id=W1.id, project_id=PJ9.id, name="Stray")` (invalid data).
2. TA = task(C1, "Alpha").
3. TO = task(CX, "Odd").

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {TA.id}`.

### PCTS-L-14 — tasks of a deleted project are not listed
- **Rules:** `get_tasks` R6; `_filter_accessible_tasks` R2 [BUG-2302]
- **Kind:** bug
- **Expect:** xfail BUG-2302
- **Fails today on:** Then 1 (TG is listed)

**Given**
1. TG = task(CD, "Gone task").
2. TA = task(C1, "Alpha").

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {TA.id}`.

### PCTS-L-15 — without a component, is_note False leaves notes out
- **Rules:** `get_tasks` R3 [BUG-2300]
- **Kind:** bug
- **Expect:** xfail BUG-2300
- **Fails today on:** Then 1 (NN is listed)

**Given**
1. NN = note(C1, "Remark").
2. TA = task(C1, "Alpha").

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id, is_note=False, limit=1000)`.

**Then**
1. returns: `idset(result) == {TA.id}`.

### PCTS-L-16 — without a component, open only leaves done tasks and notes out
- **Rules:** `get_tasks` R3 [BUG-2300]
- **Kind:** bug
- **Expect:** xfail BUG-2300
- **Fails today on:** Then 1 (TD and NN are listed)

**Given**
1. TD = task(C1, "Done"), but `is_completed True`.
2. NN = note(C1, "Remark").
3. TA = task(C1, "Alpha").

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id, incomplete_only=True, limit=1000)`.

**Then**
1. returns: `idset(result) == {TA.id}`.

### PCTS-L-17 — hidden tasks ahead of the page do not shorten it (limit)
- **Rules:** `get_tasks` R5 [BUG-2298]
- **Kind:** bug
- **Expect:** xfail BUG-2298
- **Fails today on:** Then 1 (the page is two hidden tasks, filtered away: `[]`)

**Given**
1. H1 = task(CP, "Alpha").
2. H2 = task(CP, "Bravo").
3. H3 = task(CP, "Charlie").
4. VD = task(C1, "Delta").
5. VE = task(C1, "Echo").

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=UG.id, skip=0, limit=2)`.

**Then**
1. returns: `idset(result) == {VD.id, VE.id}`.

### PCTS-L-18 — hidden tasks ahead of the page do not shift it (skip)
- **Rules:** `get_tasks` R5 [BUG-2298]
- **Kind:** bug
- **Expect:** xfail BUG-2298 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (skip 1 removes a hidden task: VD and VE both come back)

**Given**
1. H1 = task(CP, "Alpha").
2. H2 = task(CP, "Bravo").
3. H3 = task(CP, "Charlie").
4. VD = task(C1, "Delta").
5. VE = task(C1, "Echo").

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=UG.id, skip=1, limit=1000)`.

**Then**
1. returns: `idset(result) == {VE.id}`.

### PCTS-L-19 — the access filter does not read one component per row
- **Rules:** `get_tasks` R5 [BUG-2298]
- **Kind:** bug
- **Expect:** xfail BUG-2298
- **Fails today on:** Then 2 (one `project_components` read per task: 5)

**Given**
1. K1 … K5 = five `ProjectComponent(workspace_id=W1.id, project_id=PJ1.id, name=…)`, names `"K1"` … `"K5"`.
2. one task(Kn, "Kn task") on each of K1 … K5.
3. recorder.

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `len(result) == 5`.
2. statement: `sum(1 for s in stmts if "project_components" in s) <= 1`.

### PCTS-L-20 — the workspace-wide list is ordered by name, any case
- **Rules:** `get_tasks` R4 [BUG-2299]
- **Kind:** bug
- **Expect:** xfail BUG-2299 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (insertion / `id` order "Zulu", "apple", "Banana")

**Given**
1. TZ = task(C1, "Zulu").
2. TA = task(C2, "apple").
3. TB = task(C1, "Banana").

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `names(result) == ["apple", "Banana", "Zulu"]`.

### PCTS-L-21 — names equal but for case tie on id
- **Rules:** `get_tasks` R4 [BUG-2299]
- **Kind:** bug
- **Expect:** xfail BUG-2299 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (insertion order "pump", "Pump", "Axle")

**Given**
1. TL = task(C1, "pump").
2. TU = task(C1, "Pump").
3. TA = task(C1, "Axle").

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `[x.id for x in result] == [TA.id, TL.id, TU.id]`.

### PCTS-L-22 — the workspace-wide query orders by name
- **Rules:** `get_tasks` R4 [BUG-2299]
- **Kind:** bug
- **Expect:** xfail BUG-2299
- **Fails today on:** Then 2 (no `ORDER BY` on `name` in the SQL)

**Given**
1. TA = task(C1, "Alpha").
2. recorder.

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {TA.id}`.
2. statement: `"name" in order_part`.

### PCTS-L-23 — limit 0 gives an empty list
- **Rules:** `get_tasks` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TA = task(C1, "Alpha").

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PCTS-L-24 — the default limit is 100
- **Rules:** `get_tasks` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(insert(ProjectComponentTask), [dict(workspace_id=W1.id, project_component_id=C1.id, name=f"T{i:03d}", description="Text", is_note=False) for i in range(101)])`, then `db.expire_all()`.

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `len(result) == 100`.

### PCTS-L-25 — a negative limit fails in the database
- **Rules:** `get_tasks` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TA = task(C1, "Alpha").

**When**
- `svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id, limit=-1)`.

**Then**
1. raises: `DataError` in a savepoint.

### PCTS-L-26 — a negative skip fails in the database
- **Rules:** `get_tasks` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TA = task(C1, "Alpha").

**When**
- `svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id, skip=-1)`.

**Then**
1. raises: `DataError` in a savepoint.

### PCTS-L-27 — the workspace-wide read neither commits nor rolls back
- **Rules:** `get_tasks` R7; T-TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. TA = task(C1, "Alpha") (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.get_tasks(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {TA.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.

### PCTS-L-28 — a project member opens a private project's tasks
- **Rules:** `_filter_accessible_tasks` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. pmem(PJP, UG).
2. TP = task(CP, "Plan").

**When**
- `result = svc.get_tasks(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {TP.id}`.

### PCTS-L-29 — a successful one-component read neither commits nor rolls back
- **Rules:** `get_tasks` R2, R7; T-TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. TA = task(C1, "Alpha") (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.get_tasks(db, workspace_id=W1.id, user_id=UG.id, project_component_id=C1.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {TA.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.

## `ProjectComponentTaskService.get_by_id`

### PCTS-G-01 — a task the caller may open is returned
- **Rules:** `get_by_id` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = task(C1, "Alpha").

**When**
- `result = svc.get_by_id(db, task_id=TA.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == TA.id`.

### PCTS-G-02 — a note id is returned too
- **Rules:** `get_by_id` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. NN = note(C1, "Remark").

**When**
- `result = svc.get_by_id(db, task_id=NN.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == NN.id`.
2. returns: `result.is_note is True`.

### PCTS-G-03 — an unknown id is None, with no commit and no rollback
- **Rules:** `get_by_id` R1, R3; T-TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. TA = task(C1, "Alpha") (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.get_by_id(db, task_id=MISSING, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.

### PCTS-G-04 — id 0 is None
- **Rules:** `get_by_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TA = task(C1, "Alpha").

**When**
- `result = svc.get_by_id(db, task_id=0, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.

### PCTS-G-05 — a W0 task (lower id) is None in W1
- **Rules:** `get_by_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. TK0 = task(C0, "Zero").
2. TA = task(C1, "Alpha").

**When**
- `result = svc.get_by_id(db, task_id=TK0.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.

### PCTS-G-06 — a W2 task (higher id) is None in W1
- **Rules:** `get_by_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. TA = task(C1, "Alpha").
2. T9 = task(C9, "Nine").

**When**
- `result = svc.get_by_id(db, task_id=T9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.

### PCTS-G-07 — a private project's task is 403 for a plain caller, with no rollback
- **Rules:** `get_by_id` R2, R3
- **Kind:** error
- **Expect:** pass

**Given**
1. TP = task(CP, "Plan") (commit point after this line).
2. pending P.

**When**
- `svc.get_by_id(db, task_id=TP.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. session: `P in db.new`.

### PCTS-G-08 — a privileged caller opens a private project's task
- **Rules:** `get_by_id` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. TP = task(CP, "Plan").

**When**
- `result = svc.get_by_id(db, task_id=TP.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == TP.id`.

### PCTS-G-09 — a deleted project's task is 404 (pass-through)
- **Rules:** `get_by_id` R2 (manager `require_component_access` R2 [BUG-1278])
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the task is returned)

**Given**
1. TG = task(CD, "Gone task").

**When**
- `svc.get_by_id(db, task_id=TG.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {PJD.id} not found"`.

### PCTS-G-10 — a successful one-row read neither commits nor rolls back
- **Rules:** `get_by_id` R2, R3; T-TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. TA = task(C1, "Alpha") (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.get_by_id(db, task_id=TA.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == TA.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.

## `ProjectComponentTaskService.create_task`

### PCTS-C-01 — the task is stored with its defaults, committed once and returned re-read
- **Rules:** `create_task` R3, R5; T-TC1, T-TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No task in W1 (commit point after this line).

**When**
- spies: `result = svc.create_task(db, task_in=ProjectComponentTaskCreate(project_component_id=C1.id, name="Weld frame", description="Do it"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`, `result.created_at is not None`.
2. mock called: `cm.call_count == 1`.
3. mock called: `rb.call_count == 0`.
4. committed: the row `result.id` has `workspace_id == W1.id`, `project_component_id == C1.id`, `name == "Weld frame"`, `description == "Do it"`.
5. committed: that row has `is_note is False`, `is_completed is False`, `task_priority is None`.

### PCTS-C-02 — creating a task logs task_created
- **Rules:** `create_task` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No task in W1 (commit point after this line).

**When**
- `result = svc.create_task(db, task_in=ProjectComponentTaskCreate(project_component_id=C1.id, name="Weld frame", description="Do it"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: events(PJ1, "task_created") has exactly 1 row.
3. event: that event `workspace_id == W1.id`, `performed_by == UG.id`, `description == 'Added task "Weld frame"'`.
4. event: that event `metadata_json == {"task_id": result.id, "task_name": "Weld frame", "component_id": C1.id, "component_name": "Roof"}`.

### PCTS-C-03 — a priority sent is stored
- **Rules:** `create_task` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. No task in W1 (commit point after this line).

**When**
- `result = svc.create_task(db, task_in=ProjectComponentTaskCreate(project_component_id=C1.id, name="Order bolts", description="Do it", task_priority=HIGH), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.task_priority == HIGH`.
2. re-read the row `result.id`: `task_priority == HIGH`.

### PCTS-C-04 — a note created on the task pages writes no event
- **Rules:** `create_task` R3, R4 (D3)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No task in W1 (commit point after this line).

**When**
- `result = svc.create_task(db, task_in=ProjectComponentTaskCreate(project_component_id=C1.id, name="Remark", description="Text", is_note=True), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.is_note is True`.
2. committed: the row `result.id` exists, `is_note is True`.
3. event: all_events(PJ1) has exactly 0 rows.

### PCTS-C-05 — a private component: 403, rolled back once, pending changes discarded
- **Rules:** `create_task` R1; T-TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. No task in W1 (commit point after this line).
2. extra row X.

**When**
- spies: `svc.create_task(db, task_in=ProjectComponentTaskCreate(project_component_id=CP.id, name="Plan", description="Text"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. mock called: `rb.call_count == 1`.
5. session: `not db.new`.
6. count: x_gone.
7. nothing written.

### PCTS-C-06 — an unknown component is 404, nothing written
- **Rules:** `create_task` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No task in W1 (commit point after this line).

**When**
- `svc.create_task(db, task_in=ProjectComponentTaskCreate(project_component_id=MISSING, name="Plan", description="Text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.
4. session: `not db.new`.
5. nothing written.

### PCTS-C-07 — a W2 component is 404 in W1
- **Rules:** `create_task` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No task in W1 (commit point after this line).

**When**
- `svc.create_task(db, task_in=ProjectComponentTaskCreate(project_component_id=C9.id, name="Plan", description="Text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == NOCOMP`.
4. nothing written.

### PCTS-C-08 — a deleted project's component is 404, nothing written (pass-through)
- **Rules:** `create_task` R1 (manager `require_component_access` R2 [BUG-1278])
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the task is created)

**Given**
1. No task in W1 (commit point after this line).

**When**
- `svc.create_task(db, task_in=ProjectComponentTaskCreate(project_component_id=CD.id, name="Plan", description="Text"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {PJD.id} not found"`.
4. nothing written.

### PCTS-C-09 — a whitespace-only name is refused by the schema
- **Rules:** `create_task` R2 [BUG-2297]
- **Kind:** bug
- **Expect:** xfail BUG-2297
- **Fails today on:** Then 1 (the schema accepts `"  "`)

**Given**
1. No task in W1.

**When**
- build `ProjectComponentTaskCreate(project_component_id=C1.id, name="  ", description="Text")` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCTS-C-10 — an empty name is refused by the schema
- **Rules:** `create_task` R2 [BUG-2297]
- **Kind:** bug
- **Expect:** xfail BUG-2297
- **Fails today on:** Then 1 (the schema accepts `""`)

**Given**
1. No task in W1.

**When**
- build `ProjectComponentTaskCreate(project_component_id=C1.id, name="", description="Text")` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCTS-C-11 — the name is stored trimmed
- **Rules:** `create_task` R2 [BUG-2297]
- **Kind:** bug
- **Expect:** xfail BUG-2297
- **Fails today on:** Then 2 (stored as typed)

**Given**
1. No task in W1 (commit point after this line).

**When**
- `result = svc.create_task(db, task_in=ProjectComponentTaskCreate(project_component_id=C1.id, name="  Weld  frame  ", description="Do it"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the row `result.id`: `name == "Weld  frame"`.

### PCTS-C-12 — the description is kept as typed, empty included
- **Rules:** `create_task` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No task in W1 (commit point after this line).

**When**
- `result = svc.create_task(db, task_in=ProjectComponentTaskCreate(project_component_id=C1.id, name="Weld", description=""), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.description == ""`.
2. re-read the row `result.id`: `description == ""`, `name == "Weld"`.

### PCTS-C-13 — the description is required by the schema
- **Rules:** `create_task` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No task in W1.

**When**
- build `ProjectComponentTaskCreate(project_component_id=C1.id, name="Weld")` (target `schema`; `description` not sent).

**Then**
1. raises: `PydanticValidationError`.

### PCTS-C-14 — a failing commit rolls back once and nothing is saved
- **Rules:** `create_task` R5; T-TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. No task in W1 (commit point after this line).

**When**
- failing commit: `svc.create_task(db, task_in=ProjectComponentTaskCreate(project_component_id=C1.id, name="Weld", description="Do it"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. nothing written.

### PCTS-C-15 — a failing re-read after the commit leaves the task and its event saved
- **Rules:** `create_task` R5; T-TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. No task in W1 (commit point after this line).

**When**
- failing refresh: `svc.create_task(db, task_in=ProjectComponentTaskCreate(project_component_id=C1.id, name="Weld", description="Do it"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: C1 has exactly 1 `project_component_tasks` row, `name == "Weld"`.
3. committed: events(PJ1, "task_created") has exactly 1 row.

## `ProjectComponentTaskService.update_task`

### PCTS-U-01 — a rename is stored, committed and returned
- **Rules:** `update_task` R2, R7; T-TC1, T-TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = task(C1, "Weld frame") (commit point after this line).

**When**
- spies: `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(name="Weld base"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == T.id`, `result.name == "Weld base"`.
2. mock called: `cm.call_count == 1`.
3. committed: the row T has `name == "Weld base"`, `description == "Text"`, `project_component_id == C1.id`.
4. committed: the row T has `is_completed is False`, `is_note is False`, `task_priority is None`.

### PCTS-U-02 — a rename logs task_updated with the new name
- **Rules:** `update_task` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = task(C1, "Weld frame") (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(name="Weld base"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.name == "Weld base"`.
2. event: events(PJ1, "task_updated") has exactly 1 row.
3. event: that event `performed_by == UG.id`, `description == 'Updated task "Weld base"'`.
4. event: that event `metadata_json == META(T, "Weld base")`.
5. count: all_events(PJ1) has exactly 1 row.

### PCTS-U-03 — completing an open task logs task_completed
- **Rules:** `update_task` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = task(C1, "Weld frame") (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(is_completed=True), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.is_completed is True`.
2. re-read T: `is_completed is True`.
3. event: events(PJ1, "task_completed") has exactly 1 row, `description == 'Completed task "Weld frame"'`, `metadata_json == META(T, "Weld frame")`.
4. count: all_events(PJ1) has exactly 1 row.

### PCTS-U-04 — completing and renaming at once logs only task_completed, with the new name
- **Rules:** `update_task` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = task(C1, "Weld frame") (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(name="Weld base", is_completed=True), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.name == "Weld base"`.
2. event: events(PJ1, "task_completed") has exactly 1 row, `description == 'Completed task "Weld base"'`.
3. count: all_events(PJ1) has exactly 1 row.

### PCTS-U-05 — reopening a done task logs task_reopened
- **Rules:** `update_task` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = task(C1, "Weld frame"), but `is_completed True` (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(is_completed=False), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.is_completed is False`.
2. event: events(PJ1, "task_reopened") has exactly 1 row, `description == 'Reopened task "Weld frame"'`.
3. count: all_events(PJ1) has exactly 1 row.

### PCTS-U-06 — completion sent but unchanged, with a rename, logs task_updated
- **Rules:** `update_task` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = task(C1, "Weld frame"), but `is_completed True` (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(name="Weld base", is_completed=True), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.name == "Weld base"`.
2. event: events(PJ1, "task_updated") has exactly 1 row, `description == 'Updated task "Weld base"'`.
3. count: all_events(PJ1) has exactly 1 row.

### PCTS-U-07 — a priority sent is stored
- **Rules:** `update_task` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = task(C1, "Order bolts") (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(task_priority=HIGH), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.task_priority == HIGH`.
2. re-read T: `task_priority == HIGH`.

### PCTS-U-08 — an explicit null clears the priority
- **Rules:** `update_task` R2a [BUG-2304]
- **Kind:** bug
- **Expect:** xfail BUG-2304
- **Fails today on:** Then 2 (the priority stays HIGH)

**Given**
1. T = task(C1, "Order bolts"), but `task_priority HIGH` (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(task_priority=None), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `task_priority is None`.

### PCTS-U-09 — an omitted priority is left as it is
- **Rules:** `update_task` R2, R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = task(C1, "Order bolts"), but `task_priority HIGH` (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(name="Order nuts"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.name == "Order nuts"`.
2. re-read T: `task_priority == HIGH`.

### PCTS-U-10 — a null name is refused by the update schema
- **Rules:** `update_task` R2a [BUG-2304]
- **Kind:** bug
- **Expect:** xfail BUG-2304
- **Fails today on:** Then 1 (the schema accepts `None`)

**Given**
1. No task in W1.

**When**
- build `ProjectComponentTaskUpdate(name=None)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCTS-U-11 — a null completion flag is refused by the update schema
- **Rules:** `update_task` R2a [BUG-2304]
- **Kind:** bug
- **Expect:** xfail BUG-2304
- **Fails today on:** Then 1 (the schema accepts `None`)

**Given**
1. No task in W1.

**When**
- build `ProjectComponentTaskUpdate(is_completed=None)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCTS-U-12 — an empty update writes no event
- **Rules:** `update_task` R6 [BUG-2303]
- **Kind:** bug
- **Expect:** xfail BUG-2303
- **Fails today on:** Then 2 (one `task_updated` event is written)

**Given**
1. T = task(C1, "Weld frame") (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == T.id`.
2. event: all_events(PJ1) has exactly 0 rows.

### PCTS-U-13 — sending the same values writes no event
- **Rules:** `update_task` R6 [BUG-2303]
- **Kind:** bug
- **Expect:** xfail BUG-2303
- **Fails today on:** Then 2 (one `task_updated` event is written)

**Given**
1. T = task(C1, "Weld frame") (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(name="Weld frame", is_completed=False), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.name == "Weld frame"`.
2. event: all_events(PJ1) has exactly 0 rows.

### PCTS-U-14 — a task turned into a note is stored as a note
- **Rules:** `update_task` R2, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = task(C1, "Inspect weld") (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(is_note=True), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.is_note is True`.
2. committed: the row T has `is_note is True`.

### PCTS-U-15 — a task turned into a note is logged as a task update
- **Rules:** `update_task` R5 [BUG-2305]
- **Kind:** bug
- **Expect:** xfail BUG-2305
- **Fails today on:** Then 2 (no event is written)

**Given**
1. T = task(C1, "Inspect weld") (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(is_note=True), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.is_note is True`.
2. event: events(PJ1, "task_updated") has exactly 1 row, `description == 'Updated task "Inspect weld"'`.
3. count: all_events(PJ1) has exactly 1 row.

### PCTS-U-16 — a note that stays a note writes no event
- **Rules:** `update_task` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. N = note(C1, "Remark") (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=N.id, task_in=ProjectComponentTaskUpdate(name="Remark two"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.name == "Remark two"`.
2. re-read N: `name == "Remark two"`, `is_note is True`.
3. event: all_events(PJ1) has exactly 0 rows.

### PCTS-U-17 — a note turned into a task logs task_updated
- **Rules:** `update_task` R4, R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. N = note(C1, "Remark") (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=N.id, task_in=ProjectComponentTaskUpdate(is_note=False), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.is_note is False`.
2. event: events(PJ1, "task_updated") has exactly 1 row, `description == 'Updated task "Remark"'`, `metadata_json == META(N, "Remark")`.

### PCTS-U-18 — an unknown id returns None with no commit and no rollback
- **Rules:** `update_task` R1; T-TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. T = task(C1, "Weld frame") (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.update_task(db, task_id=MISSING, task_in=ProjectComponentTaskUpdate(name="New"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.
5. session: `not db.dirty`.
6. unchanged: unchanged(T).

### PCTS-U-19 — a private project's task: 403, rolled back once, pending changes discarded
- **Rules:** `update_task` R1; T-TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. TP = task(CP, "Plan") (commit point after this line).
2. extra row X.

**When**
- spies: `svc.update_task(db, task_id=TP.id, task_in=ProjectComponentTaskUpdate(is_completed=True), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. mock called: `rb.call_count == 1`.
5. session: `not db.dirty`.
6. count: x_gone.
7. unchanged: unchanged(TP).
8. nothing written.

### PCTS-U-20 — a W2 task is not found in W1
- **Rules:** `update_task` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T9 = task(C9, "Nine") (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T9.id, task_in=ProjectComponentTaskUpdate(name="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(T9).

### PCTS-U-21 — a sent name is stored trimmed
- **Rules:** `update_task` R3 [BUG-2297]
- **Kind:** bug
- **Expect:** xfail BUG-2297
- **Fails today on:** Then 2 (stored `"  Weld base  "`)

**Given**
1. T = task(C1, "Weld frame") (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(name="  Weld base  "), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `name == "Weld base"`.

### PCTS-U-22 — a blank name is refused by the update schema
- **Rules:** `update_task` R3 [BUG-2297]
- **Kind:** bug
- **Expect:** xfail BUG-2297
- **Fails today on:** Then 1 (the schema accepts `"  "`)

**Given**
1. No task in W1.

**When**
- build `ProjectComponentTaskUpdate(name="  ")` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### PCTS-U-23 — a failing commit rolls back once and the task is unchanged
- **Rules:** `update_task` R7; T-TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = task(C1, "Weld frame") (commit point after this line).

**When**
- failing commit: `svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(is_completed=True), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. unchanged: unchanged(T).
4. nothing written.

### PCTS-U-24 — a failing re-read after the commit leaves the change saved
- **Rules:** `update_task` R7; T-TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = task(C1, "Weld frame") (commit point after this line).

**When**
- failing refresh: `svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(is_completed=True), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: the row T has `is_completed is True`.
3. committed: events(PJ1, "task_completed") has exactly 1 row.

### PCTS-U-25 — a deleted project's task is 404 and unchanged (pass-through)
- **Rules:** `update_task` R1 (manager `require_component_access` R2 [BUG-1278])
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the task is updated)

**Given**
1. TG = task(CD, "Gone task") (commit point after this line).

**When**
- `svc.update_task(db, task_id=TG.id, task_in=ProjectComponentTaskUpdate(name="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {PJD.id} not found"`.
4. unchanged: unchanged(TG).

### PCTS-U-26 — a description change alone logs task_updated
- **Rules:** `update_task` R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = task(C1, "Weld frame") (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(description="Use 6 mm rod"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.description == "Use 6 mm rod"`.
2. re-read T: `description == "Use 6 mm rod"`, `name == "Weld frame"`.
3. event: events(PJ1, "task_updated") has exactly 1 row.

### PCTS-U-27 — a done task turned into a note while reopened logs task_reopened
- **Rules:** `update_task` R5 [BUG-2305]
- **Kind:** bug
- **Expect:** xfail BUG-2305
- **Fails today on:** Then 2 (no event is written)

**Given**
1. T = task(C1, "Inspect weld"), but `is_completed True` (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(is_note=True, is_completed=False), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.is_note is True`.
2. event: events(PJ1, "task_reopened") has exactly 1 row.
3. count: all_events(PJ1) has exactly 1 row.

### PCTS-U-28 — a priority changes from one set value to another
- **Rules:** `update_task` R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = task(C1, "Order bolts"), but `task_priority HIGH` (commit point after this line).

**When**
- `result = svc.update_task(db, task_id=T.id, task_in=ProjectComponentTaskUpdate(task_priority=URGENT), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.task_priority == URGENT`.
2. re-read T: `task_priority == URGENT`, `name == "Order bolts"`.
3. event: events(PJ1, "task_updated") has exactly 1 row, `description == 'Updated task "Order bolts"'`.
4. count: all_events(PJ1) has exactly 1 row.

## `ProjectComponentTaskService.delete_task`

### PCTS-D-01 — a task is deleted after its task_deleted event, committed, True
- **Rules:** `delete_task` R2, R3; T-TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = task(C1, "Weld frame").
2. TK = task(C1, "Keep") (commit point after this line).

**When**
- spies: `result = svc.delete_task(db, task_id=T.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is True`.
2. mock called: `cm.call_count == 1`.
3. committed: no `project_component_tasks` row has id `T.id`.
4. committed: the row TK exists.
5. committed: events(PJ1, "task_deleted") has exactly 1 row, `performed_by == UG.id`, `description == 'Deleted task "Weld frame"'`.
6. committed: that event `metadata_json == META(T, "Weld frame")`.

### PCTS-D-02 — a note deleted through the task pages writes no event
- **Rules:** `delete_task` R2 (D3)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. N = note(C1, "Remark") (commit point after this line).

**When**
- `result = svc.delete_task(db, task_id=N.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is True`.
2. committed: no `project_component_tasks` row has id `N.id`.
3. committed: all_events(PJ1) has exactly 0 rows.

### PCTS-D-03 — an unknown id returns False with no commit and no rollback
- **Rules:** `delete_task` R1; T-TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. T = task(C1, "Weld frame") (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.delete_task(db, task_id=MISSING, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is False`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.new`.
5. session: `not db.deleted`.
6. unchanged: unchanged(T).

### PCTS-D-04 — a private project's task: 403, rolled back once, the task stays
- **Rules:** `delete_task` R1; T-TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. TP = task(CP, "Plan") (commit point after this line).
2. extra row X.

**When**
- spies: `svc.delete_task(db, task_id=TP.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == NOACCESS`.
4. mock called: `rb.call_count == 1`.
5. session: `not db.deleted`.
6. count: x_gone.
7. unchanged: unchanged(TP).
8. nothing written.

### PCTS-D-05 — a failing commit rolls back once; the task and no event remain
- **Rules:** `delete_task` R3; T-TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = task(C1, "Weld frame") (commit point after this line).

**When**
- failing commit: `svc.delete_task(db, task_id=T.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. unchanged: unchanged(T).
4. nothing written.

### PCTS-D-06 — a deleted project's task is 404 and stays (pass-through)
- **Rules:** `delete_task` R1 (manager `require_component_access` R2 [BUG-1278])
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the task is deleted)

**Given**
1. TG = task(CD, "Gone task") (commit point after this line).

**When**
- `svc.delete_task(db, task_id=TG.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {PJD.id} not found"`.
4. unchanged: unchanged(TG).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_tasks` R8 [BUG-2296] | `GET /project-component-tasks/` | `limit=0` → 422; `limit` 1 and 100 accepted |
| Integration-only | `/project-component-tasks/` endpoints | `None` / `False` → 404 `Project component task not found`; schema errors → 422 (BUG-461) |

## Spec gaps
None. Gaps 1–2 closed by spec Gap log G1, G2 (2026-11-04).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_guard_component` | R1 | PCTS-L-05 … L-08, G-07, G-09, C-05 … C-08, U-19, U-25, D-04, D-06 |
| `_filter_accessible_tasks` | R1 | PCTS-L-09 … L-13, L-28 |
| `_filter_accessible_tasks` | R2 [BUG-2302] | PCTS-L-14 |
| `get_tasks` | R1 | PCTS-L-01, L-06, L-07; L-05 [BUG-2301]; L-08 [BUG-1278] |
| `get_tasks` | R2 | PCTS-L-01 … L-04 |
| `get_tasks` | R3 | PCTS-L-09; L-15, L-16 [BUG-2300] |
| `get_tasks` | R4 [BUG-2299] | PCTS-L-20, L-21, L-22 |
| `get_tasks` | R5 [BUG-2298] | PCTS-L-17, L-18, L-19 |
| `get_tasks` | R6 [BUG-2302] | PCTS-L-14 |
| `get_tasks` | R7 / T-TC6 | PCTS-L-06, L-27, L-29 |
| `get_tasks` | R8 | PCTS-L-23 … L-26; endpoint part deferred |
| `get_by_id` | R1 | PCTS-G-03 … G-06 |
| `get_by_id` | R2 | PCTS-G-01, G-02, G-07, G-08; G-09 [BUG-1278] |
| `get_by_id` | R3 / T-TC6 | PCTS-G-03, G-07, G-10 |
| `create_task` | R1 | PCTS-C-05, C-06, C-07; C-08 [BUG-1278] |
| `create_task` | R2 [BUG-2297] | PCTS-C-09, C-10, C-11; description C-12, C-13 |
| `create_task` | R3 | PCTS-C-01, C-03, C-04 |
| `create_task` | R4 | PCTS-C-02, C-04 |
| `create_task` | R5 / T-TC1–T-TC5 | PCTS-C-01, C-05, C-14, C-15 |
| `update_task` | R1 | PCTS-U-18, U-19, U-20; U-25 [BUG-1278] |
| `update_task` | R2 | PCTS-U-01, U-07, U-09, U-14, U-26, U-28 |
| `update_task` | R2a [BUG-2304] | PCTS-U-08, U-10, U-11; omitted U-09 |
| `update_task` | R3 [BUG-2297] | PCTS-U-21, U-22 |
| `update_task` | R4 | PCTS-U-02 … U-06, U-17, U-26, U-28 |
| `update_task` | R5 | PCTS-U-14, U-16, U-17; U-15, U-27 [BUG-2305] |
| `update_task` | R6 [BUG-2303] | PCTS-U-12, U-13 |
| `update_task` | R7 / T-TC1–T-TC5 | PCTS-U-01, U-19, U-23, U-24 |
| `delete_task` | R1 | PCTS-D-03, D-04; D-06 [BUG-1278] |
| `delete_task` | R2 | PCTS-D-01, D-02 |
| `delete_task` | R3 / T-TC1, T-TC3, T-TC4 | PCTS-D-01, D-04, D-05 |
