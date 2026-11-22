# Test cases — `app/services/project_service.py`

> **Spec:** `tests/unit/services/project_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 4 (2026-11-06) — verifier finding 1 (`project_service.verify.md`): new PJS-L-15 (status filter with `limit=2`, two PLANNING rows with the lowest ids and names ahead) and PJS-L-16 (factory filter, two F1 rows ahead), both pass; a service that filters after the manager pages returns a short page. No card changed or retired.
> Revision 3 (2026-11-05) — executor discrepancy DISCREPANCY-1 (`project_service.notes.md`): the re-read check in PJS-C-01 (Then 3), U-01 (Then 2), D-01 (Then 2), AM-01 (Then 3), SV-01 (Then 2) now covers column attributes only: `not ({c.key for c in inspect(result).mapper.column_attrs} & inspect(result).expired_attributes)`, because `db.refresh()` leaves lazy relationships expired. Counts unchanged.
> Revision 2 (2026-11-05) — spec fill-gaps G1: BUG-2271's endpoint function named (`app.api.v1.endpoints.projects.list_project_members`). New PJS-LM-05 (strict statement count, xfail BUG-2271), LM-06 (the enriched response, pass), LM-07 (the endpoint passes the 403 on, pass). BUG-2271 removed from Deferred. No card changed or retired.
> **Counts:** 79 cases · 64 expected-to-pass · 15 expected-to-fail (bugs) · 3 deferred

## Reviewer summary
- **Per callable:** `create_project` 7 (1 bug) · `get_project` 7 (1 bug) · `list_projects` 16 (6 bug) · `update_project` 9 (2 bug) · `delete_project` 6 · `list_events` 5 (1 bug) · `list_members` 7 (2 bug; LM-05 … LM-07 call the endpoint function `list_project_members`) · `add_member` 8 (1 bug) · `remove_member` 7 (1 bug) · `set_visibility` 7.
- **Depth:** lighter (skill step 1a) on the service's own work: a thin `BaseService` wrapper with no check of its own. What it adds is the transaction (TC1–TC6), so every writer gets committed / refused-and-rolled-back / failing commit / failing re-read cards, every refusal row of the spec one pass-through card (exact status and text, the session clean, an uncommitted extra row discarded, nothing written), and every reader a TC6 card. The manager's matrices (`project_manager.cases.md`) are not repeated: one or two pass-through cards per manager rule or bug.
- **Filter after paging:** pass cards L-15 (status) and L-16 (factory): two hidden rows with the lowest ids and names, so ahead today and after BUG-1957, and the page of 2 must still be full. BUG-1958 twice (`limit=2` with three hidden private rows ahead; `skip=1` with one hidden row ahead) and BUG-1955 once (a deleted row ahead of the skipped one). The hidden rows have the lowest ids **and** the lowest names, so they sort first both today (id) and after BUG-1957 (name).
- **Other xfail (all strict):** BUG-1951, 1952, 1953, 1954, 1957, 1959, 1960, 1964, 1278 (×3: members list, add, remove), each one pass-through card mirroring the manager's.
- **Notable design choices:** "returned re-read" (TC2) is checked on column attributes only (lazy relationships stay expired after `db.refresh()`). the non-HTTP TC3 card (C-04) builds `ProjectCreate.model_construct(...)` with a budget of `1e20`, so it still reaches the database after BUG-1963 makes the schema refuse it. Readers' error paths check that a pending row survives (no rollback), the opposite of the writers'. `remove_member` checks that nothing is re-read.
- **BUG-2271:** tested on the endpoint function itself (spec G1): LM-05 counts the statements after the last `project_members` read (5 members, ≤ 2 intended, 10 today); LM-06 pins the response the fix must keep (name, email, position, `None` without a membership).
- **Needs a decision:** None. Gap 1 closed by the spec's Gap log (G1).

## Conventions for this module

**IDs.** `PJS` = `app/services/project_service.py`. `C` create_project · `G` get_project · `L` list_projects · `U` update_project · `D` delete_project · `EV` list_events · `LM` list_members · `AM` add_member · `RM` remove_member · `SV` set_visibility.

**Imports.** `from app.services.project_service import ProjectService, project_service`. Models from `app.models.<module>`: `factory.Factory`, `project.Project`, `project_member.ProjectMember`, `project_event.ProjectEvent`, `workspace_member.WorkspaceMember`. `ProjectStatusEnum`, `ProjectVisibilityEnum` (`app.models.enums`). `ProjectCreate`, `ProjectUpdate`, `ProjectMembersListResponse` (`app.schemas.project`). `list_project_members` (`app.api.v1.endpoints.projects`), called directly with keywords `project_id`, `workspace` (the `Workspace` row), `current_user` (the caller's `Profile`), `db`. `HTTPException` (`fastapi`); `DataError` (`sqlalchemy.exc`); `event`, `insert`, `select`, `func`, `inspect` (`sqlalchemy`); `Decimal`; `datetime`; `patch` (`unittest.mock`); `signature` (`inspect` module, as `from inspect import signature`).

**Fixed values.** `svc` = `project_service`. `db` = the test's real session, always the first argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush. MISSING = `999999999`. T1 = `datetime(2026, 1, 1, 9, 0, 0)`, T2 = `datetime(2026, 1, 1, 10, 0, 0)`, T3 = `datetime(2026, 1, 1, 11, 0, 0)`, NOW = `datetime(2026, 3, 1, 10, 0, 0)` (all naive). DENIED = `"You do not have access to this project"`.

**Externals.** `app.managers.project_manager.utcnow` is patched to return NOW in every test (the test helper does it). Nothing else is mocked except the failure patches below.

**Standing rows** (every test, no Given line; built in this order, each flushed):
- W0, W1, W2 = `make_workspace(db)` (`W0.id < W1.id < W2.id`).
- U1 = `make_profile(db, name="Ana Rahman")`; U2 = `make_profile(db, name="Bilal Khan")`; UG = `make_profile(db, name="Mia Khan")`. Memberships of W1: U1 `ground-team`, U2 `owner`, UG `ground-team`, all `active`. U2 is privileged; UG is the plain caller. U1 is `created_by` of every Given project.
- F0 = `Factory(workspace_id=W0.id, name="Factory Zero", abbreviation="F0")`. F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`. F2 = F1 but `name "Factory Two"`, `abbreviation "F2"`. FD = F1 but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True`. F9 = `Factory(workspace_id=W2.id, name="Factory Nine", abbreviation="F9")`.

**Given rows.** Built directly (never through `svc`), added and flushed one at a time in the order written, so ids rise in that order. After "but" a line lists every column that differs. A line written as code is a step run exactly.
- **member(U, role, status="active")** = `WorkspaceMember(workspace_id=W1.id, user_id=U.id, role=role, status=status)`.
- **proj** = `Project(workspace_id=W1.id, factory_id=F1.id, name=…, description="Main", created_by=U1.id)`; the card gives `name`. **W0 proj** = `workspace_id W0.id`, `factory_id F0.id`; **W2 proj** = `workspace_id W2.id`, `factory_id F9.id`. **private** = `visibility "invited_only"`. **deleted** = `is_deleted True`, `deleted_at T1`, `deleted_by U1.id`.
- **pmem(P, U)** = `ProjectMember(workspace_id=P.workspace_id, project_id=P.id, user_id=U.id, assigned_by=U1.id)`; a card may add `assigned_at`.
- **ev(P, "type", at, by)** = `ProjectEvent(workspace_id=P.workspace_id, project_id=P.id, event_type="type", description="seed", performed_by=by, created_at=at, metadata_json=None)`.
- **bulk(n)** = n live projects of F1 in W1 by one `db.execute(insert(Project), [...])`, named `P00000` … (5 digits), `description "Main"`, `created_by U1.id`, `visibility "workspace"`; then `db.expire_all()`.
- **commit point** = after the last Given line the test runs `db.commit()` (releases a savepoint under the `db` fixture). Snapshots for `unchanged` and `nothing written` are taken there.
- **extra row X** (after the commit point) = `X = Project(workspace_id=W2.id, factory_id=F9.id, name="Extra", description="Extra", created_by=U2.id)`, `db.add(X)`, `db.flush()`; `X_ID = X.id`. **x_gone** = `db.scalar(select(func.count()).select_from(Project).where(Project.id == X_ID)) == 0`. **x_kept** = the same count `== 1`, checked before any rollback by the test.
- **edit A** = `A.description = "Edited"` on the row A the card names, not flushed.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; database values. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the numbers of rows of `projects`, `project_members`, `project_events` (all workspaces) equal their values at the commit point.
- **events_of(P)** = `db.expire_all()`, then every `project_events` row with `project_id == P.id`, ordered by `id`. **members_of(P)** = the same on `project_members`.
- **idset(x)** = `{r.id for r in x}`. **names(x)** = `[r.name for r in x]` (order is part of the check). **val(x)** = `getattr(x, "value", x)`.
- `raises: HTTPException` = `with pytest.raises(HTTPException) as exc:` around the call, no savepoint; then `exc.value.status_code`, `exc.value.detail`, one per line. `raises: ValueError` the same. `raises: DataError` = plain `pytest.raises(DataError)` (the service rolls back itself).
- `session:` lines check `db` directly, right after the call, before any re-read.
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line then re-reads with a fresh query.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb, patch.object(db, "refresh", wraps=db.refresh) as rf:` around the When.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When.
- **recorder** = a Given step: `stmts = []`, `event.listen(db.connection(), "before_cursor_execute", rec)` where `rec(conn, cursor, statement, params, context, executemany)` appends `statement`; removed with `event.remove` right after the When.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`. All strict.

**Race simulations.** None.

## `ProjectService.create_project`

### PJS-C-01 — the project, its creator's membership and the created event are committed; the project is returned re-read
- **Rules:** `create_project` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No projects exist (commit point after this line).

**When**
- `result = svc.create_project(db, project_in=ProjectCreate(factory_id=F1.id, name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, Project)`.
2. returns: `result.id is not None`, `result.created_at is not None`.
3. returns: `not ({c.key for c in inspect(result).mapper.column_attrs} & inspect(result).expired_attributes)`.
4. committed: the project with id `result.id` exists, `name == "Roof job"`, `workspace_id == W1.id`, `created_by == U2.id`.
5. committed: `project_members` has exactly 1 row with `project_id == result.id`, `user_id == U2.id`.
6. committed: `project_events` has exactly 1 row with `project_id == result.id`, `event_type == "created"`.

### PJS-C-02 — an unknown factory is 404, rolled back with every pending change
- **Rules:** `create_project` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. No projects exist (commit point after this line).
2. extra row X.

**When**
- `svc.create_project(db, project_in=ProjectCreate(factory_id=MISSING, name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. session: `not db.new and not db.dirty`.
5. count: x_gone.
6. nothing written.

### PJS-C-03 — a soft-deleted factory is 400, rolled back with every pending change
- **Rules:** `create_project` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. No projects exist (commit point after this line).
2. extra row X.

**When**
- `svc.create_project(db, project_in=ProjectCreate(factory_id=FD.id, name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create project for deleted factory"`.
4. session: `not db.new and not db.dirty`.
5. count: x_gone.
6. nothing written.

### PJS-C-04 — a database error passes unchanged, rolled back, and the session stays usable
- **Rules:** `create_project` R3, R4 (the service re-raises unchanged); TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. No projects exist (commit point after this line).
2. extra row X.

**When**
- `svc.create_project(db, project_in=ProjectCreate.model_construct(factory_id=F1.id, name="Roof job", description="Main", budget=Decimal("100000000000000000000")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `DataError`.
2. count: x_gone.
3. nothing written.
4. session: `db.scalar(select(func.count()).select_from(Project).where(Project.workspace_id == W1.id)) == 0`.

### PJS-C-05 — a failing commit rolls back and nothing is saved
- **Rules:** `create_project` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. No projects exist (commit point after this line).

**When**
- failing commit: `svc.create_project(db, project_in=ProjectCreate(factory_id=F1.id, name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. nothing written.

### PJS-C-06 — a failing re-read after the commit leaves the project, member and event saved
- **Rules:** `create_project` R3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. No projects exist (commit point after this line).

**When**
- failing refresh: `svc.create_project(db, project_in=ProjectCreate(factory_id=F1.id, name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: W1 has exactly 1 project, `name == "Roof job"`.
3. committed: that project has exactly 1 `project_members` row and exactly 1 `project_events` row.

### PJS-C-07 — the name is stored trimmed (pass-through)
- **Rules:** `create_project` R1 (manager R4 [BUG-1951])
- **Kind:** bug
- **Expect:** xfail BUG-1951
- **Fails today on:** Then 2 (stored as typed, with the spaces)

**Given**
1. No projects exist (commit point after this line).

**When**
- `result = svc.create_project(db, project_in=ProjectCreate(factory_id=F1.id, name="  Line 3 refit ", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the project with id `result.id` has `name == "Line 3 refit"`.

## `ProjectService.get_project`

### PJS-G-01 — returns the workspace's project
- **Rules:** `get_project` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P0 = W0 proj `name "Zero"`.
2. P = proj `name "Roof job"`.
3. P9 = W2 proj `name "Nine"`.

**When**
- `result = svc.get_project(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == P.id`.
2. returns: `result.name == "Roof job"`.

### PJS-G-02 — a private project the caller may not open: the manager's 403 passes unchanged
- **Rules:** `get_project` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.

**When**
- `svc.get_project(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENIED`.

### PJS-G-03 — another workspace's project is 404, and a pending change survives (no rollback)
- **Rules:** `get_project` R1, R2; TC6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. P9 = W2 proj `name "Nine"` (commit point after this line).
3. extra row X.

**When**
- spies: `svc.get_project(db, project_id=P9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P9.id} not found"`.
4. mock called: `rb.call_count == 0`.
5. count: x_kept.

### PJS-G-04 — a soft-deleted project is 404 (pass-through)
- **Rules:** `get_project` R1 [BUG-1954]
- **Kind:** bug
- **Expect:** xfail BUG-1954
- **Fails today on:** Then 1 (no error: the deleted project is returned)

**Given**
1. P = deleted proj `name "Gone"`.

**When**
- `svc.get_project(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P.id} not found"`.

### PJS-G-05 — a get neither commits nor rolls back; the caller's edit stays
- **Rules:** `get_project` R2; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = proj `name "Alpha"`.
2. edit A.

**When**
- spies: `result = svc.get_project(db, project_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == A.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `A in db.dirty`.
5. session: `A.description == "Edited"`.

### PJS-G-06 — the service takes no include_deleted argument
- **Rules:** `get_project` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No Given rows needed.

**When**
- `params = signature(svc.get_project).parameters`.

**Then**
1. returns: `"include_deleted" not in params`.
2. returns: `list(params) == ["db", "project_id", "workspace_id", "user_id"]`.

### PJS-G-07 — a W0 project (lower id) is 404 in W1
- **Rules:** `get_project` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 proj `name "Zero"`.
2. P = proj `name "Roof job"`.

**When**
- `svc.get_project(db, project_id=P0.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P0.id} not found"`.

## `ProjectService.list_projects`

### PJS-L-01 — a privileged caller gets the workspace's live projects, private ones included
- **Rules:** `list_projects` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P0 = W0 proj `name "Zero"`.
2. PA = proj `name "Alpha"`.
3. PV = private proj `name "Vault"`.
4. P9 = W2 proj `name "Nine"`.

**When**
- `result = svc.list_projects(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {PA.id, PV.id}`.

### PJS-L-02 — with nothing after user_id the page holds 100
- **Rules:** `list_projects` R1 (default `limit=100`, `skip=0`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101).

**When**
- `result = svc.list_projects(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `len(result) == 100`.

### PJS-L-03 — limit 1000 returns all 101
- **Rules:** `list_projects` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101).

**When**
- `result = svc.list_projects(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### PJS-L-04 — skip is passed on: 100 of 101 leaves one
- **Rules:** `list_projects` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101).

**When**
- `result = svc.list_projects(db, workspace_id=W1.id, user_id=U2.id, skip=100, limit=1000)`.

**Then**
1. returns: `len(result) == 1`.

### PJS-L-05 — factory_id is passed on
- **Rules:** `list_projects` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = proj `name "Alpha"`.
2. B = proj `name "Beta"`, but `factory_id F2.id`.

**When**
- `result = svc.list_projects(db, workspace_id=W1.id, user_id=U2.id, factory_id=F2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {B.id}`.

### PJS-L-06 — status is passed on
- **Rules:** `list_projects` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. AP = proj `name "Alpha"`.
2. AC = proj `name "Beta"`, but `status ProjectStatusEnum.COMPLETED`.

**When**
- `result = svc.list_projects(db, workspace_id=W1.id, user_id=U2.id, status="COMPLETED", limit=1000)`.

**Then**
1. returns: `idset(result) == {AC.id}`.

### PJS-L-07 — hidden private projects ahead of the page do not use its places (pass-through)
- **Rules:** `list_projects` R1 (manager R7 [BUG-1958])
- **Kind:** bug
- **Expect:** xfail BUG-1958
- **Fails today on:** Then 1 (the page of the first two rows is filtered after paging: `[]`)

**Given**
1. H1 = private proj `name "Aa"`.
2. H2 = private proj `name "Ab"`.
3. H3 = private proj `name "Ac"`.
4. V1 = proj `name "Ba"`.
5. V2 = proj `name "Bb"`.

**When**
- `result = svc.list_projects(db, workspace_id=W1.id, user_id=UG.id, skip=0, limit=2)`.

**Then**
1. returns: `idset(result) == {V1.id, V2.id}`.

### PJS-L-08 — a hidden private project ahead of the skipped row is not counted by skip (pass-through)
- **Rules:** `list_projects` R1 (manager R7 [BUG-1958])
- **Kind:** bug
- **Expect:** xfail BUG-1958
- **Fails today on:** Then 1 (skip drops the hidden row, then the filter: both visible rows come back)

**Given**
1. H = private proj `name "Aa"`.
2. V1 = proj `name "Ba"`.
3. V2 = proj `name "Bb"`.

**When**
- `result = svc.list_projects(db, workspace_id=W1.id, user_id=UG.id, skip=1, limit=10)`.

**Then**
1. returns: `idset(result) == {V2.id}`.

### PJS-L-09 — a soft-deleted project ahead of the skipped row takes no place (pass-through)
- **Rules:** `list_projects` R1 (manager R3 [BUG-1955])
- **Kind:** bug
- **Expect:** xfail BUG-1955
- **Fails today on:** Then 1 (skip drops the deleted row: both live rows come back)

**Given**
1. X = deleted proj `name "Aa"`.
2. V1 = proj `name "Ba"`.
3. V2 = proj `name "Bb"`.

**When**
- `result = svc.list_projects(db, workspace_id=W1.id, user_id=U2.id, skip=1, limit=10)`.

**Then**
1. returns: `idset(result) == {V2.id}`.

### PJS-L-10 — without filters the list is ordered by name, case-insensitive (pass-through)
- **Rules:** `list_projects` R1 (manager R5 [BUG-1957])
- **Kind:** bug
- **Expect:** xfail BUG-1957
- **Fails today on:** Then 1 (ordered by id: Zulu, apple, Banana)

**Given**
1. Z = proj `name "Zulu"`.
2. A = proj `name "apple"`.
3. B = proj `name "Banana"`.

**When**
- `result = svc.list_projects(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `names(result) == ["apple", "Banana", "Zulu"]`.

### PJS-L-11 — factory_id 0 filters and returns nothing (pass-through)
- **Rules:** `list_projects` R1 (manager R1 [BUG-1959])
- **Kind:** bug
- **Expect:** xfail BUG-1959
- **Fails today on:** Then 1 (0 is taken as no filter: every project is returned)

**Given**
1. A = proj `name "Alpha"`.
2. B = proj `name "Beta"`, but `factory_id F2.id`.

**When**
- `result = svc.list_projects(db, workspace_id=W1.id, user_id=U2.id, factory_id=0, limit=1000)`.

**Then**
1. returns: `result == []`.

### PJS-L-12 — factory and status together apply both (pass-through)
- **Rules:** `list_projects` R1 (manager R1a [BUG-1960])
- **Kind:** bug
- **Expect:** xfail BUG-1960
- **Fails today on:** Then 1 (the status is ignored: AC of F1 is returned too)

**Given**
1. AP = proj `name "Alpha"`.
2. AC = proj `name "Beta"`, but `status ProjectStatusEnum.COMPLETED`.
3. BP = proj `name "Gamma"`, but `factory_id F2.id`.

**When**
- `result = svc.list_projects(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, status="PLANNING", limit=1000)`.

**Then**
1. returns: `idset(result) == {AP.id}`.

### PJS-L-13 — an unknown status: the manager's ValueError passes unchanged, no rollback
- **Rules:** `list_projects` R2; TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. AP = proj `name "Alpha"` (commit point after this line).
2. extra row X.

**When**
- spies: `svc.list_projects(db, workspace_id=W1.id, user_id=U2.id, status="planning")`.

**Then**
1. raises: `ValueError`.
2. mock called: `rb.call_count == 0`.
3. mock called: `cm.call_count == 0`.
4. count: x_kept.

### PJS-L-14 — a list neither commits nor rolls back; the caller's edit stays
- **Rules:** `list_projects` R2; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = proj `name "Alpha"`.
2. edit A.

**When**
- spies: `result = svc.list_projects(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `A in db.dirty`.
5. session: `len(db.dirty) == 1`.

### PJS-L-15 — a status filter with paging: rows of another status ahead of the page take no place
- **Rules:** `list_projects` R1 (filter passed on, applied before paging, HR-5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. AP1 = proj `name "Aa"` (PLANNING; lowest id and lowest name).
2. AP2 = proj `name "Ab"` (PLANNING).
3. AC1 = proj `name "Ca"`, but `status ProjectStatusEnum.COMPLETED`.
4. AC2 = proj `name "Cb"`, but `status ProjectStatusEnum.COMPLETED`.

**When**
- `result = svc.list_projects(db, workspace_id=W1.id, user_id=U2.id, status="COMPLETED", skip=0, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `idset(result) == {AC1.id, AC2.id}`.

### PJS-L-16 — a factory filter with paging: rows of another factory ahead of the page take no place
- **Rules:** `list_projects` R1 (filter passed on, applied before paging, HR-5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = proj `name "Aa"` (F1; lowest id and lowest name).
2. A2 = proj `name "Ab"` (F1).
3. B1 = proj `name "Ba"`, but `factory_id F2.id`.
4. B2 = proj `name "Bb"`, but `factory_id F2.id`.

**When**
- `result = svc.list_projects(db, workspace_id=W1.id, user_id=U2.id, factory_id=F2.id, skip=0, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `idset(result) == {B1.id, B2.id}`.

## `ProjectService.update_project`

### PJS-U-01 — changes the fields, logs the event, commits, returns the row re-read
- **Rules:** `update_project` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"` (commit point after this line).

**When**
- `result = svc.update_project(db, project_id=P.id, project_in=ProjectUpdate(name="Roof refit"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. returns: `not ({c.key for c in inspect(result).mapper.column_attrs} & inspect(result).expired_attributes)`.
3. returns: `result.updated_at == NOW`.
4. committed: re-read P: `name == "Roof refit"`, `updated_by == U2.id`.
5. committed: events_of(P) has exactly 1 row, `event_type == "updated"`, `performed_by == U2.id`.

### PJS-U-02 — a soft-deleted project is 400, rolled back with every pending change
- **Rules:** `update_project` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = deleted proj `name "Gone"` (commit point after this line).
2. extra row X.

**When**
- `svc.update_project(db, project_id=P.id, project_in=ProjectUpdate(name="Back"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted project"`.
4. session: `not db.new and not db.dirty`.
5. count: x_gone.
6. unchanged: unchanged(P).
7. nothing written.

### PJS-U-03 — a private project the caller may not open is 403, rolled back
- **Rules:** `update_project` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"` (commit point after this line).
2. extra row X.

**When**
- `svc.update_project(db, project_id=P.id, project_in=ProjectUpdate(name="Mine"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENIED`.
4. session: `not db.new and not db.dirty`.
5. count: x_gone.
6. unchanged: unchanged(P).

### PJS-U-04 — a W0 project (lower id) is 404 in W1, rolled back
- **Rules:** `update_project` R2; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 proj `name "Zero"`.
2. P = proj `name "Roof job"` (commit point after this line).
3. extra row X.

**When**
- `svc.update_project(db, project_id=P0.id, project_in=ProjectUpdate(name="Mine"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P0.id} not found"`.
4. session: `not db.new and not db.dirty`.
5. count: x_gone.
6. unchanged: unchanged(P0).

### PJS-U-05 — a failing commit rolls back and nothing is saved
- **Rules:** `update_project` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"` (commit point after this line).

**When**
- failing commit: `svc.update_project(db, project_id=P.id, project_in=ProjectUpdate(name="Roof refit"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(P).
4. nothing written.

### PJS-U-06 — a failing re-read after the commit leaves the change saved
- **Rules:** `update_project` R3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"` (commit point after this line).

**When**
- failing refresh: `svc.update_project(db, project_id=P.id, project_in=ProjectUpdate(name="Roof refit"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read P: `name == "Roof refit"`.
3. committed: events_of(P) has exactly 1 row.

### PJS-U-07 — the same values: no event (pass-through)
- **Rules:** `update_project` R1 (manager R4)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"` (commit point after this line).

**When**
- `result = svc.update_project(db, project_id=P.id, project_in=ProjectUpdate(name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. committed: events_of(P) has exactly 0 rows.

### PJS-U-08 — the same values do not stamp the project (pass-through)
- **Rules:** `update_project` R1 (manager R9 [BUG-1952])
- **Kind:** bug
- **Expect:** xfail BUG-1952
- **Fails today on:** Then 2 (stamped although nothing changed)

**Given**
1. P = proj `name "Roof job"` (commit point after this line).

**When**
- `result = svc.update_project(db, project_id=P.id, project_in=ProjectUpdate(name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. committed: re-read P: `updated_by is None`, `updated_at is None`.

### PJS-U-09 — an explicit null clears the budget (pass-through)
- **Rules:** `update_project` R1 (manager R2a [BUG-1953])
- **Kind:** bug
- **Expect:** xfail BUG-1953
- **Fails today on:** Then 2 (the null is dropped: the budget stays 1000.00)

**Given**
1. P = proj `name "Roof job"`, but `budget Decimal("1000.00")` (commit point after this line).

**When**
- `result = svc.update_project(db, project_id=P.id, project_in=ProjectUpdate(budget=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. committed: re-read P: `budget is None`.

## `ProjectService.delete_project`

### PJS-D-01 — soft-deletes, logs deleted, commits, returns the row re-read
- **Rules:** `delete_project` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"` (commit point after this line).

**When**
- `result = svc.delete_project(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. returns: `not ({c.key for c in inspect(result).mapper.column_attrs} & inspect(result).expired_attributes)`.
3. returns: `result.is_deleted is True`, `result.deleted_at == NOW`, `result.deleted_by == U2.id`.
4. committed: re-read P: `is_deleted is True`, `deleted_by == U2.id`.
5. committed: events_of(P) has exactly 1 row, `event_type == "deleted"`.

### PJS-D-02 — an already deleted project is 400, rolled back with every pending change
- **Rules:** `delete_project` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = deleted proj `name "Gone"` (commit point after this line).
2. extra row X.

**When**
- `svc.delete_project(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Project is already deleted"`.
4. session: `not db.new and not db.dirty`.
5. count: x_gone.
6. unchanged: unchanged(P).
7. nothing written.

### PJS-D-03 — a private project the caller may not open is 403, rolled back
- **Rules:** `delete_project` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"` (commit point after this line).
2. extra row X.

**When**
- `svc.delete_project(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENIED`.
4. session: `not db.new and not db.dirty`.
5. count: x_gone.
6. unchanged: unchanged(P).

### PJS-D-04 — a W2 project (higher id) is 404 in W1, rolled back
- **Rules:** `delete_project` R2; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. P9 = W2 proj `name "Nine"` (commit point after this line).
3. extra row X.

**When**
- `svc.delete_project(db, project_id=P9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P9.id} not found"`.
4. session: `not db.new and not db.dirty`.
5. count: x_gone.
6. unchanged: unchanged(P9).

### PJS-D-05 — a failing commit rolls back and nothing is saved
- **Rules:** `delete_project` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"` (commit point after this line).

**When**
- failing commit: `svc.delete_project(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read P: `is_deleted is False`.
4. nothing written.

### PJS-D-06 — a failing re-read after the commit leaves the delete saved
- **Rules:** `delete_project` R3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"` (commit point after this line).

**When**
- failing refresh: `svc.delete_project(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read P: `is_deleted is True`.
3. committed: events_of(P) has exactly 1 row.

## `ProjectService.list_events`

### PJS-EV-01 — the manager's log, newest first with each performer's profile
- **Rules:** `list_events` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. EA = ev(P, "a", T1, U1.id).
3. EB = ev(P, "b", T3, None).
4. EC = ev(P, "c", T2, U2.id).

**When**
- `result = svc.list_events(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `[e.id for e, _ in result] == [EB.id, EC.id, EA.id]`.
2. returns: `[(p.id if p is not None else None) for _, p in result] == [None, U2.id, U1.id]`.

### PJS-EV-02 — a soft-deleted project's log is still answered
- **Rules:** `list_events` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P = deleted proj `name "Gone"`.
2. E1 = ev(P, "deleted", T1, U1.id).

**When**
- `result = svc.list_events(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `[e.id for e, _ in result] == [E1.id]`.

### PJS-EV-03 — a private project's log: the 403 passes unchanged, no rollback
- **Rules:** `list_events` R1, R2; TC6
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"` (commit point after this line).
2. extra row X.

**When**
- spies: `svc.list_events(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENIED`.
4. mock called: `rb.call_count == 0`.
5. count: x_kept.

### PJS-EV-04 — a read neither commits nor rolls back; the caller's edit stays
- **Rules:** `list_events` R2; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. E1 = ev(P, "a", T1, U1.id).
3. edit P.

**When**
- spies: `result = svc.list_events(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `len(result) == 1`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.dirty`.

### PJS-EV-05 — performers are read together (pass-through)
- **Rules:** `list_events` R1 (manager R4 [BUG-1964])
- **Kind:** bug
- **Expect:** xfail BUG-1964
- **Fails today on:** Then 2 (one profile read per performer)

**Given**
1. P = proj `name "Roof job"`.
2. `UX = make_profile(db, name="Omar Ali")`; `UY = make_profile(db, name="Rina Das")`.
3. Five events, one per performer: ev(P, "a", T1, U1.id), ev(P, "b", T1, U2.id), ev(P, "c", T2, UG.id), ev(P, "d", T2, UX.id), ev(P, "e", T3, UY.id).
4. `db.expire_all()`.
5. recorder.

**When**
- `result = svc.list_events(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: `len([s for s in stmts if "FROM projects" not in s]) <= 3`.

## `ProjectService.list_members`

### PJS-LM-01 — the manager's members, in order of assigned_at
- **Rules:** `list_members` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. MA = pmem(P, U1), but `assigned_at T2`.
3. MB = pmem(P, U2), but `assigned_at T1`.
4. MC = pmem(P, UG), but `assigned_at T3`.

**When**
- `result = svc.list_members(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `[m.id for m in result] == [MB.id, MA.id, MC.id]`.

### PJS-LM-02 — a soft-deleted project's members are 404 (pass-through)
- **Rules:** `list_members` R1 [BUG-1278]
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the members are returned)

**Given**
1. P = deleted proj `name "Gone"`.
2. pmem(P, U1).

**When**
- `svc.list_members(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P.id} not found"`.

### PJS-LM-03 — another workspace's project is 404, no rollback
- **Rules:** `list_members` R1, R2; TC6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P9 = W2 proj `name "Nine"` (commit point after this line).
2. extra row X.

**When**
- spies: `svc.list_members(db, project_id=P9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P9.id} not found"`.
4. mock called: `rb.call_count == 0`.
5. count: x_kept.

### PJS-LM-04 — a read neither commits nor rolls back; the caller's edit stays
- **Rules:** `list_members` R2; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. M = pmem(P, UG).
3. edit P.

**When**
- spies: `result = svc.list_members(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `[m.id for m in result] == [M.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `P in db.dirty`.

### PJS-LM-05 — the members endpoint reads profiles and positions together: at most two statements after the member list
- **Rules:** `list_members` R3 [BUG-2271]
- **Kind:** bug
- **Expect:** xfail BUG-2271
- **Fails today on:** Then 2 (two statements per member after the list: 10)

**Given**
1. `UA = make_profile(db, name="Omar Ali")`; `UB = make_profile(db, name="Rina Das")`; `UC = make_profile(db, name="Sami Haq")`; `UD = make_profile(db, name="Tania Roy")`; `UE = make_profile(db, name="Uma Sen")`.
2. member(UA, "ground-team"), member(UB, "ground-team"), member(UC, "finance"), member(UD, "ground-team"), member(UE, "ground-team").
3. P = proj `name "Roof job"`.
4. pmem(P, UA), but `assigned_at T1`; pmem(P, UB), but `assigned_at T1`; pmem(P, UC), but `assigned_at T2`; pmem(P, UD), but `assigned_at T2`; pmem(P, UE), but `assigned_at T3`.
5. `db.expire_all()`.
6. recorder.

**When**
- `result = list_project_members(project_id=P.id, workspace=W1, current_user=U2, db=db)`.

**Then**
1. returns: `len(result.members) == 5`.
2. returns: `len(stmts) - 1 - max(i for i, s in enumerate(stmts) if "FROM project_members" in s) <= 2`.

### PJS-LM-06 — the members endpoint answers each member's name, email and workspace position
- **Rules:** `list_members` R3 (the response the fix must keep)
- **Kind:** happy
- **Expect:** pass

**Given**
1. `m1 = db.scalar(select(WorkspaceMember).where(WorkspaceMember.workspace_id == W1.id, WorkspaceMember.user_id == U1.id))`; `m1.position = "Foreman"`; `db.flush()`.
2. `UX = make_profile(db, name="Omar Ali")` (no membership of W1).
3. P = proj `name "Roof job"`.
4. MA = pmem(P, U1), but `assigned_at T1`.
5. MX = pmem(P, UX), but `assigned_at T2`.

**When**
- `result = list_project_members(project_id=P.id, workspace=W1, current_user=U2, db=db)`.

**Then**
1. returns: `isinstance(result, ProjectMembersListResponse)`.
2. returns: `[m.id for m in result.members] == [MA.id, MX.id]`.
3. returns: `result.members[0].user_id == U1.id`, `result.members[0].user_name == "Ana Rahman"`, `result.members[0].user_email == U1.email`, `result.members[0].user_position == "Foreman"`.
4. returns: `result.members[1].user_name == "Omar Ali"`, `result.members[1].user_email == UX.email`, `result.members[1].user_position is None`.
5. returns: `result.members[0].project_id == P.id`, `result.members[0].workspace_id == W1.id`, `result.members[0].assigned_by == U1.id`, `result.members[0].assigned_at == T1`.

### PJS-LM-07 — the members endpoint passes the service's 403 on unchanged
- **Rules:** `list_members` R1, R3 (endpoint errors pass unchanged)
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.
2. pmem(P, U1).

**When**
- `list_project_members(project_id=P.id, workspace=W1, current_user=UG, db=db)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENIED`.

## `ProjectService.add_member`

### PJS-AM-01 — adds the member, logs member_added, commits, returns the row re-read
- **Rules:** `add_member` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team").
2. P = proj `name "Roof job"` (commit point after this line).

**When**
- `result = svc.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. returns: `isinstance(result, ProjectMember)`.
2. returns: `result.assigned_at is not None`.
3. returns: `not ({c.key for c in inspect(result).mapper.column_attrs} & inspect(result).expired_attributes)`.
4. committed: members_of(P) has exactly 1 row, `user_id == UX.id`, `assigned_by == U2.id`.
5. committed: events_of(P) has exactly 1 row, `event_type == "member_added"`, `description == "Added Omar Ali to the project"`.

### PJS-AM-02 — a person who is not an active member of the workspace is 400, rolled back
- **Rules:** `add_member` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team", status="suspended").
2. P = proj `name "Roof job"` (commit point after this line).
3. extra row X.

**When**
- `svc.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.
4. session: `not db.new`.
5. count: x_gone.
6. nothing written.

### PJS-AM-03 — someone already a member is 409, rolled back
- **Rules:** `add_member` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team").
2. P = proj `name "Roof job"`.
3. MX = pmem(P, UX) (commit point after this line).
4. extra row X.

**When**
- `svc.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "User is already a member of this project"`.
4. session: `not db.new`.
5. count: x_gone.
6. unchanged: unchanged(MX).
7. nothing written.

### PJS-AM-04 — a caller who may not open the private project is 403, rolled back
- **Rules:** `add_member` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team").
2. P = private proj `name "Secret"` (commit point after this line).
3. extra row X.

**When**
- `svc.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENIED`.
4. session: `not db.new`.
5. count: x_gone.
6. nothing written.

### PJS-AM-05 — a W0 project (lower id) is 404 in W1, rolled back
- **Rules:** `add_member` R2; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team").
2. P0 = W0 proj `name "Zero"` (commit point after this line).
3. extra row X.

**When**
- `svc.add_member(db, project_id=P0.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P0.id} not found"`.
4. session: `not db.new`.
5. count: x_gone.
6. nothing written.

### PJS-AM-06 — a soft-deleted project is 404 and nobody is added (pass-through)
- **Rules:** `add_member` R2 [BUG-1278]
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the member is added and committed)

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team").
2. P = deleted proj `name "Gone"` (commit point after this line).

**When**
- `svc.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P.id} not found"`.
4. session: `not db.new`.
5. nothing written.

### PJS-AM-07 — a failing commit rolls back and nobody is added
- **Rules:** `add_member` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team").
2. P = proj `name "Roof job"` (commit point after this line).

**When**
- failing commit: `svc.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. nothing written.

### PJS-AM-08 — a failing re-read after the commit leaves the member saved
- **Rules:** `add_member` R3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team").
2. P = proj `name "Roof job"` (commit point after this line).

**When**
- failing refresh: `svc.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: members_of(P) has exactly 1 row, `user_id == UX.id`.
3. committed: events_of(P) has exactly 1 row.

## `ProjectService.remove_member`

### PJS-RM-01 — removes the member, logs member_removed, commits, returns None without a re-read
- **Rules:** `remove_member` R1; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team").
2. P = proj `name "Roof job"`.
3. MU = pmem(P, U2).
4. MX = pmem(P, UX) (commit point after this line).

**When**
- spies: `result = svc.remove_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count >= 1`.
3. mock called: `rf.call_count == 0`.
4. committed: `[m.id for m in members_of(P)] == [MU.id]`.
5. committed: events_of(P) has exactly 1 row, `event_type == "member_removed"`, `description == "Removed Omar Ali from the project"`.

### PJS-RM-02 — removing the creator is 400, rolled back
- **Rules:** `remove_member` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"` (creator U1).
2. M1 = pmem(P, U1) (commit point after this line).
3. extra row X.

**When**
- `svc.remove_member(db, project_id=P.id, member_user_id=U1.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot remove the project creator from members"`.
4. session: `not db.deleted and not db.new`.
5. count: x_gone.
6. unchanged: unchanged(M1).
7. nothing written.

### PJS-RM-03 — someone not on the project is 404 "Project member not found", rolled back
- **Rules:** `remove_member` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. M2 = pmem(P, U2) (commit point after this line).
3. extra row X.

**When**
- `svc.remove_member(db, project_id=P.id, member_user_id=UG.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project member not found"`.
4. session: `not db.deleted and not db.new`.
5. count: x_gone.
6. unchanged: unchanged(M2).

### PJS-RM-04 — a caller who may not open the private project is 403, rolled back
- **Rules:** `remove_member` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.
2. M2 = pmem(P, U2) (commit point after this line).
3. extra row X.

**When**
- `svc.remove_member(db, project_id=P.id, member_user_id=U2.id, workspace_id=W1.id, performed_by=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENIED`.
4. session: `not db.deleted and not db.new`.
5. count: x_gone.
6. unchanged: unchanged(M2).

### PJS-RM-05 — a W2 project (higher id) is 404 in W1, rolled back
- **Rules:** `remove_member` R2; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P9 = W2 proj `name "Nine"`.
2. M9 = pmem(P9, U2) (commit point after this line).
3. extra row X.

**When**
- `svc.remove_member(db, project_id=P9.id, member_user_id=U2.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P9.id} not found"`.
4. session: `not db.deleted and not db.new`.
5. count: x_gone.
6. unchanged: unchanged(M9).

### PJS-RM-06 — a soft-deleted project is 404 and nobody is removed (pass-through)
- **Rules:** `remove_member` R2 [BUG-1278]
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the member is removed and committed)

**Given**
1. P = deleted proj `name "Gone"`.
2. MG = pmem(P, UG) (commit point after this line).

**When**
- `svc.remove_member(db, project_id=P.id, member_user_id=UG.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P.id} not found"`.
4. session: `not db.deleted`.
5. unchanged: unchanged(MG).
6. nothing written.

### PJS-RM-07 — a failing commit rolls back and the member stays
- **Rules:** `remove_member` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. MG = pmem(P, UG) (commit point after this line).

**When**
- failing commit: `svc.remove_member(db, project_id=P.id, member_user_id=UG.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(MG).
4. nothing written.

## `ProjectService.set_visibility`

### PJS-SV-01 — makes the project private, logs the change, commits, returns the row re-read
- **Rules:** `set_visibility` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"` (commit point after this line).

**When**
- `result = svc.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.INVITED_ONLY, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. returns: `not ({c.key for c in inspect(result).mapper.column_attrs} & inspect(result).expired_attributes)`.
3. committed: re-read P: `visibility == "invited_only"`, `updated_by == U2.id`.
4. committed: events_of(P) has exactly 1 row, `event_type == "visibility_updated"`.

### PJS-SV-02 — the same visibility: no event, no stamp, the commit still runs
- **Rules:** `set_visibility` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"` (commit point after this line).

**When**
- spies: `result = svc.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.INVITED_ONLY, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. mock called: `cm.call_count >= 1`.
3. unchanged: unchanged(P).
4. count: events_of(P) has exactly 0 rows.

### PJS-SV-03 — a soft-deleted project is 400, rolled back
- **Rules:** `set_visibility` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = deleted proj `name "Gone"` (commit point after this line).
2. extra row X.

**When**
- `svc.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.INVITED_ONLY, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted project"`.
4. session: `not db.new and not db.dirty`.
5. count: x_gone.
6. unchanged: unchanged(P).
7. nothing written.

### PJS-SV-04 — a caller who may not open the private project is 403, rolled back
- **Rules:** `set_visibility` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"` (commit point after this line).
2. extra row X.

**When**
- `svc.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.WORKSPACE, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == DENIED`.
4. session: `not db.new and not db.dirty`.
5. count: x_gone.
6. unchanged: unchanged(P).

### PJS-SV-05 — a W0 project (lower id) is 404 in W1, rolled back
- **Rules:** `set_visibility` R2; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 proj `name "Zero"`.
2. P = proj `name "Roof job"` (commit point after this line).
3. extra row X.

**When**
- `svc.set_visibility(db, project_id=P0.id, visibility=ProjectVisibilityEnum.INVITED_ONLY, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P0.id} not found"`.
4. session: `not db.new and not db.dirty`.
5. count: x_gone.
6. unchanged: unchanged(P0).

### PJS-SV-06 — a failing commit rolls back and the visibility is not saved
- **Rules:** `set_visibility` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"` (commit point after this line).

**When**
- failing commit: `svc.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.INVITED_ONLY, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. re-read P: `visibility == "workspace"`.
4. nothing written.

### PJS-SV-07 — a failing re-read after the commit leaves the change saved
- **Rules:** `set_visibility` R3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"` (commit point after this line).

**When**
- failing refresh: `svc.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.INVITED_ONLY, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read P: `visibility == "invited_only"`.
3. committed: events_of(P) has exactly 1 row.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `create_project` R4 [BUG-2270] | `POST /projects/` (integration) | a database error during create answers the global handler's 500 / 409, never 400 with `str(e)` |
| `list_projects` R2 (BUG-1961, query type) | `GET /projects/` | an unknown `project_status` → 422 |
| `skip` / `limit` bounds (HR-7) | `GET /projects/` | `limit=0` → 422 |

## Spec gaps
None. Gap 1 of revision 1 closed by the spec's Gap log G1 (2026-11-04).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_project` | R1; TC1, TC2 | PJS-C-01 |
| `create_project` | R1 (manager BUG-1951) | PJS-C-07 |
| `create_project` | R2 (404, 400); TC3 | PJS-C-02, C-03 |
| `create_project` | R3; TC3 non-HTTP, TC4, TC5 | PJS-C-04, C-05, C-06 |
| `create_project` | R4 [BUG-2270] | Deferred (service side: PJS-C-04) |
| `get_project` | R1 (200, 403, 404) | PJS-G-01, G-02, G-03, G-07 |
| `get_project` | R1 [BUG-1954] | PJS-G-04 |
| `get_project` | R2; TC6 | PJS-G-03, G-05, G-06 |
| `list_projects` | R1 (arguments, defaults, filters before paging) | PJS-L-01 … L-06, L-15, L-16 |
| `list_projects` | R1 (BUG-1955, 1957, 1958, 1959, 1960) | PJS-L-09, L-10, L-07, L-08, L-11, L-12 |
| `list_projects` | R2; TC6 | PJS-L-13, L-14 |
| `update_project` | R1; TC1, TC2 | PJS-U-01, U-07 |
| `update_project` | R1 (BUG-1952, 1953) | PJS-U-08, U-09 |
| `update_project` | R2 (400, 403, 404); TC3 | PJS-U-02, U-03, U-04 |
| `update_project` | R3; TC4, TC5 | PJS-U-05, U-06 |
| `delete_project` | R1; TC1, TC2 | PJS-D-01 |
| `delete_project` | R2 (400, 403, 404); TC3 | PJS-D-02, D-03, D-04 |
| `delete_project` | R3; TC4, TC5 | PJS-D-05, D-06 |
| `list_events` | R1 (BUG-1964) | PJS-EV-01, EV-02, EV-05 |
| `list_events` | R2; TC6 | PJS-EV-03, EV-04 |
| `list_members` | R1 [BUG-1278] | PJS-LM-01, LM-02 |
| `list_members` | R2; TC6 | PJS-LM-03, LM-04 |
| `list_members` | R3 [BUG-2271] | PJS-LM-05, LM-06, LM-07 |
| `add_member` | R1; TC1, TC2 | PJS-AM-01 |
| `add_member` | R2 (400, 409, 403, 404, [BUG-1278]); TC3 | PJS-AM-02 … AM-06 |
| `add_member` | R3; TC4, TC5 | PJS-AM-07, AM-08 |
| `remove_member` | R1; TC1 (no re-read) | PJS-RM-01 |
| `remove_member` | R2 (400, 404 member, 403, 404 project, [BUG-1278]); TC3 | PJS-RM-02 … RM-06 |
| `remove_member` | R3; TC4 | PJS-RM-07 |
| `set_visibility` | R1; TC1, TC2 | PJS-SV-01, SV-02 |
| `set_visibility` | R2 (400, 403, 404); TC3 | PJS-SV-03, SV-04, SV-05 |
| `set_visibility` | R3; TC4, TC5 | PJS-SV-06, SV-07 |
