# Test cases — `app/services/miscellaneous_project_cost_service.py`

> **Spec:** `tests/unit/services/miscellaneous_project_cost_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-10) — spec Fill-gaps 2026-11-10 (Gap log G1–G3). G1: BUG-100 is still open; MPCSV-L-14 stays the one **strict** `ORDER BY` alarm (it compares no order, so it cannot pass by accident), and MPCSV-L-15 stays the **non-strict** order card, built as the spec's Notes say (three rows inserted, then the first one updated). G2: MPCSV-C-13 now asserts exactly 403 `You do not have access to this project` (component visibility before the 400). G3: MPCSV-LA-04 now asserts the detail `Project with ID <PJ9.id> not found`. No ID added or retired; counts unchanged. All gaps closed.
> **Counts:** 89 cases · 61 expected-to-pass · 28 expected-to-fail (bugs; 27 strict, 1 non-strict) · 4 deferred

## Reviewer summary
- **Per callable:** `_log_cost_activity` 6 (1 bug) · `_filter_accessible_costs` 6 (1 bug) · `get_costs` 19 (8 bug) · `get_by_id` 12 (2 bug) · `create_cost` 24 (10 bug) · `update_cost` 15 (5 bug) · `delete_cost` 7 (1 bug).
- **Depth:** lighter (skill step 1a). A misc cost is a hand-typed figure: no stock, no balance, no order state, and every access decision is the project manager's guard. One card per rule and guard outcome; W0 (lower id) and W2 (higher id) negatives on the by-id reads; one paging boundary each for `limit=0`, a negative limit, the default 100 and `skip`; one recorder per unordered query. Projects are deferred until after launch: 12 cards carry `Revisit: after launch (owner 2026-11-10)` (unlinked costs, id 0, sign and rounding of `amount`), as the spec tags them.
- **Transactions (M-TC1–M-TC6):** every writer has a spied success card, a guard refusal that discards an uncommitted extra row (rolled back once), and a failing commit; create and update also a failing re-read (the change stays). Not-found paths of update/delete and every read keep the extra row pending (no commit, no rollback).
- **House-rule and precedent bugs (strict):** HR-1 BUG-2613 4 · HR-16 BUG-2616 3 (+ BUG-1013 1) · HR-5 BUG-2611 2 (the hidden rows ahead of the page with `limit=2`, and the statement count on five components) · BUG-2614 4 · BUG-1278 3 · BUG-2612, BUG-2615, BUG-2617, BUG-2618 2 each · BUG-1192 1. HR-7 BUG-2610 is the endpoint's (deferred). BUG-100 (HR-6): one strict `ORDER BY` recorder card and one non-strict order card (`Author: claude`).
- **Notable design choices:** PJ1 and C1 carry explicit ids (XID) so an event's `project_id` cannot equal the component id by chance. The schema bugs (blank name, 14 integer digits) are schema cards; 13 digits pass today and stay passing.
- **Needs a decision:** None. Gaps 1–3 of Revision 1 are closed by the spec's Gap log (G1–G3).

## Conventions for this module

**IDs.** `MPCSV` = `app/services/miscellaneous_project_cost_service.py` (`MPC` is the DAO's, `MCS` the machine service's). `LA` _log_cost_activity · `FA` _filter_accessible_costs · `L` get_costs · `G` get_by_id · `C` create_cost · `U` update_cost · `D` delete_cost.

**Actors and fixed values.**
- `svc` = `miscellaneous_project_cost_service` (`from app.services.miscellaneous_project_cost_service import MiscellaneousProjectCostService, miscellaneous_project_cost_service`). `db` = the test's real session, first positional argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- Models from `app.models.<module>`: `factory.Factory`, `project.Project`, `project_component.ProjectComponent`, `project_event.ProjectEvent`, `workspace_member.WorkspaceMember`, `miscellaneous_project_cost.MiscellaneousProjectCost`. `MiscellaneousProjectCostCreate`, `MiscellaneousProjectCostUpdate` (`app.schemas.miscellaneous_project_cost`). `HTTPException` (`fastapi`); `PydanticValidationError` = `pydantic.ValidationError`; `DataError` (`sqlalchemy.exc`); `event`, `select`, `func` (`sqlalchemy`); `patch` (`unittest.mock`); `Decimal`, `os`, `datetime`.
- MISSING = `999999999`. T0 = `datetime(2025, 12, 1, 8, 0, 0)`. XID(k) = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`.
- NOCOMP = `"Project component not found"`. NOACCESS = `"You do not have access to this project"`. NOTPART = `"Project component does not belong to this project"`.

**Standing rows** (every test, in this order, each added and flushed, no Given line):
- W0, W1, W2 = `make_workspace(db)` (`W0.id < W1.id < W2.id`). U1 = `make_profile(db, name="Ana Rahman")`, U2 = `make_profile(db, name="Bilal Khan")`, UG = `make_profile(db, name="Mia Khan")`. In W1: `WorkspaceMember(workspace_id=W1.id, user_id=…, role=…, status="active")` for U1 `"ground-team"`, U2 `"owner"`, UG `"ground-team"`. U2 is privileged; UG is the plain caller.
- F0, F1, F9 = `Factory(workspace_id=W0.id / W1.id / W2.id, name="Factory Zero" / "Factory One" / "Factory Nine", abbreviation="F0" / "F1" / "F9")`.
- Projects, all `description="Main"`, `created_by=U1.id`: PJ0 = (W0, F0, `"Project Zero"`); PJ1 = (W1, F1, `"Project One"`, `id=XID(1)`); PJ2 = (W1, F1, `"Yard"`); PJP = (W1, F1, `"Secret"`, `visibility="invited_only"`); PJD = (W1, F1, `"Gone"`, `is_deleted=True`, `deleted_at=T0`, `deleted_by=U1.id`); PJ9 = (W2, F9, `"Project Nine"`).
- Components `ProjectComponent(workspace_id, project_id, name)`: C0 = (W0, PJ0, `"Cellar"`); C1 = (W1, PJ1, `"Roof"`, `id=XID(5)`); C2 = (W1, PJ2, `"Gate"`); CP = (W1, PJP, `"Vault"`); CD = (W1, PJD, `"Floor"`); C9 = (W2, PJ9, `"Deck"`).
- No cost or event row exists unless the Given builds it.

**Given rows.** Built directly (never through `svc`), added and flushed one at a time in the order written. After "but" a line names every column that differs.
- **cost** = `MiscellaneousProjectCost(workspace_id=W1.id, project_id=PJ1.id, project_component_id=None, name="Crane", description=None, amount=Decimal("100.00"))`. "on C only" = cost, but `project_id None`, `project_component_id C.id`. "unlinked" = cost, but `project_id None`.
- **commit point** = after the last Given line the test runs `db.commit()` (releases a savepoint). Snapshots for `unchanged` and `nothing written` are taken there.
- **extra row X** (after the commit point) = `X = MiscellaneousProjectCost(workspace_id=W2.id, project_id=PJ9.id, name="Extra", amount=Decimal("1.00"))`, `db.add(X)`, `db.flush()`, `X_ID = X.id`; not committed.
- A Given line written as code is a step run exactly as written.

**Externals.** None. Nothing is mocked except where a card says so.

**Named checks.**
- **re-read X** = `db.expire_all()`, then `db.get(<model>, X.id)`. **unchanged(X)** = after re-read, every column of X equals its value at the commit point. Amounts compare as `Decimal`.
- **nothing written** = the numbers of `miscellaneous_project_costs` rows and of `project_events` rows (all workspaces) equal their values at the commit point.
- **x_kept** / **x_gone** = `db.scalar(select(func.count()).select_from(MiscellaneousProjectCost).where(MiscellaneousProjectCost.id == X_ID)) == 1` / `== 0`.
- **events(P, t)** = `db.expire_all()`, then the `ProjectEvent` rows with `project_id == P.id` and `event_type == t`, ordered by `id`; "that event" = the one row just counted; metadata is `metadata_json`. **all_events()** = every `ProjectEvent` row in W1.
- **idset(r)** = `{x.id for x in r}`. **ids(r)** = `[x.id for x in r]` (order is part of the check).
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the call (inside any `raises` block).
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the call. **failing refresh** = the same with `patch.object(db, "refresh", side_effect=RuntimeError("boom"))` and no `rb`.
- **flush only** = `sp = db.begin_nested()` directly before the When, which runs inside `patch.object(db, "commit", wraps=db.commit) as cm`; "inside" lines first, then `sp.rollback()` and the "after" lines.
- `raises: HTTPException` = plain `with pytest.raises(HTTPException) as exc:`, **no** savepoint; then `exc.value.status_code`, `exc.value.detail`. `raises: DataError in a savepoint` = `with pytest.raises(DataError):` then `with db.begin_nested():` then the call. A `schema` card wraps only building the schema.
- `session:` lines check `db.new` / `db.dirty` / `db.deleted` right after the call, before any re-read.
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line then reads with a fresh query.
- **recorder** = a Given step run last: `stmts = []`, `event.listen(db.connection(), "before_cursor_execute", rec)` where `rec` appends `statement`; `event.remove` right after the When. `sql` = the recorded `SELECT` whose text contains `FROM miscellaneous_project_costs`; `order_part` = its text after the first `ORDER BY` and before any `LIMIT` (`""` when none).

**xfail cards.** Strict unless the Expect line says `(non-strict)`: `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call and checks exactly as shown.

**Revisit after launch.** A card with the header line `- **Revisit:** after launch (owner 2026-11-10)` is written and run as usual. On an xfail card the reason carries the tag: `reason="BUG-n (revisit after launch)"`. On a pass card, the docstring carries `revisit after launch (owner 2026-11-10)`.

**Race simulations.** None.

## `MiscellaneousProjectCostService._log_cost_activity`

### MPCSV-LA-01 — a cost with a component logs on the component's project, even with another project_id
- **Rules:** `_log_cost_activity` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. K = cost, but `project_id PJ2.id`, `project_component_id C1.id`.

**When**
- `result = svc._log_cost_activity(db, cost=K, workspace_id=W1.id, user_id=UG.id, event_type="cost_added", description='Added cost "Crane"')`.

**Then**
1. returns: `result is None`.
2. event: events(PJ1, "cost_added") has exactly 1 row.
3. event: that event `performed_by == UG.id`, `description == 'Added cost "Crane"'`, `metadata_json == {"cost_id": K.id, "cost_name": "Crane", "component_id": C1.id, "component_name": "Roof"}`.
4. count: events(PJ2, "cost_added") has 0 rows.

### MPCSV-LA-02 — a component outside the workspace writes nothing and raises nothing
- **Rules:** `_log_cost_activity` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. K = cost on C9 only.

**When**
- `result = svc._log_cost_activity(db, cost=K, workspace_id=W1.id, user_id=UG.id, event_type="cost_added", description='Added cost "Crane"')`.

**Then**
1. returns: `result is None`.
2. count: `db.scalar(select(func.count()).select_from(ProjectEvent)) == 0`.

### MPCSV-LA-03 — a project-only cost logs on that project with component_id None
- **Rules:** `_log_cost_activity` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. K = cost.

**When**
- `result = svc._log_cost_activity(db, cost=K, workspace_id=W1.id, user_id=UG.id, event_type="cost_added", description='Added cost "Crane"')`.

**Then**
1. returns: `result is None`.
2. event: events(PJ1, "cost_added") has exactly 1 row.
3. event: that event `performed_by == UG.id`, `metadata_json == {"cost_id": K.id, "cost_name": "Crane", "component_id": None}`.

### MPCSV-LA-04 — a project of another workspace is refused as not found
- **Rules:** `_log_cost_activity` R2 (BUG-1192 of the project manager)
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (no error: the event is written)

**Given**
1. K = cost, but `project_id PJ9.id`.

**When**
- `svc._log_cost_activity(db, cost=K, workspace_id=W1.id, user_id=UG.id, event_type="cost_added", description='Added cost "Crane"')`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`, `exc.value.detail == f"Project with ID {PJ9.id} not found"`.
2. count: events(PJ9, "cost_added") has 0 rows.

### MPCSV-LA-05 — a cost with neither link logs nothing
- **Rules:** `_log_cost_activity` R3
- **Kind:** boundary
- **Expect:** pass
- **Revisit:** after launch (owner 2026-11-10)

**Given**
1. K = cost unlinked.

**When**
- `result = svc._log_cost_activity(db, cost=K, workspace_id=W1.id, user_id=UG.id, event_type="cost_added", description='Added cost "Crane"')`.

**Then**
1. returns: `result is None`.
2. count: `db.scalar(select(func.count()).select_from(ProjectEvent)) == 0`.

### MPCSV-LA-06 — the event is flushed, never committed
- **Rules:** `_log_cost_activity` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. K = cost (commit point after this line).

**When**
- flush only: `svc._log_cost_activity(db, cost=K, workspace_id=W1.id, user_id=UG.id, event_type="cost_added", description='Added cost "Crane"')`.

**Then**
1. count (inside): events(PJ1, "cost_added") has exactly 1 row.
2. mock called (inside): `cm.call_count == 0`.
3. count (after `sp.rollback()`): events(PJ1, "cost_added") has 0 rows.

## `MiscellaneousProjectCostService._filter_accessible_costs`

### MPCSV-FA-01 — a plain caller keeps open-project costs, in input order
- **Rules:** `_filter_accessible_costs` R1, R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. KA = cost.
2. KP = cost, but `project_id PJP.id`.
3. KC = cost on C2 only.
4. KU = cost unlinked.
5. K9 = cost on C9 only.

**When**
- `result = svc._filter_accessible_costs(db, costs=[KC, K9, KU, KP, KA], workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `ids(result) == [KC.id, KA.id]`.

### MPCSV-FA-02 — a privileged caller keeps the private project's cost too
- **Rules:** `_filter_accessible_costs` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. KA = cost.
2. KP = cost, but `project_id PJP.id`.
3. KU = cost unlinked.

**When**
- `result = svc._filter_accessible_costs(db, costs=[KP, KU, KA], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `ids(result) == [KP.id, KA.id]`.

### MPCSV-FA-03 — a cost with both links is judged by its project only
- **Rules:** `_filter_accessible_costs` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. KB = cost, but `project_component_id CP.id`.

**When**
- `result = svc._filter_accessible_costs(db, costs=[KB], workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `ids(result) == [KB.id]`.

### MPCSV-FA-04 — a cost naming another workspace's project is dropped
- **Rules:** `_filter_accessible_costs` R4 (project found in the workspace)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. K9 = cost, but `project_id PJ9.id`.
2. KA = cost.

**When**
- `result = svc._filter_accessible_costs(db, costs=[K9, KA], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `ids(result) == [KA.id]`.

### MPCSV-FA-05 — a deleted project's cost is dropped
- **Rules:** `_filter_accessible_costs` R3 [BUG-2612]
- **Kind:** bug
- **Expect:** xfail BUG-2612
- **Fails today on:** Then 1 (the deleted project's cost is kept)

**Given**
1. KD = cost, but `project_id PJD.id`.
2. KA = cost.

**When**
- `result = svc._filter_accessible_costs(db, costs=[KD, KA], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `ids(result) == [KA.id]`.

### MPCSV-FA-06 — an empty list gives an empty list
- **Rules:** `_filter_accessible_costs` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No cost (standing rows only).

**When**
- `result = svc._filter_accessible_costs(db, costs=[], workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result == []`.

## `MiscellaneousProjectCostService.get_costs`

### MPCSV-L-01 — with a project: that project's costs, the component ignored, nothing committed
- **Rules:** `get_costs` R1, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. KA = cost.
2. KB = cost, but `project_id PJ2.id`.
3. KC = cost on C2 only (commit point after this line).
4. extra row X.

**When**
- spies: `result = svc.get_costs(db, workspace_id=W1.id, user_id=UG.id, project_id=PJ1.id, project_component_id=C2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {KA.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### MPCSV-L-02 — a private project is 403 and nothing is rolled back
- **Rules:** `get_costs` R1, R6
- **Kind:** error
- **Expect:** pass

**Given**
1. KP = cost, but `project_id PJP.id` (commit point after this line).
2. extra row X.

**When**
- spies: `svc.get_costs(db, workspace_id=W1.id, user_id=UG.id, project_id=PJP.id, limit=1000)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 403`, `exc.value.detail == NOACCESS`.
2. mock called: `rb.call_count == 0`.
3. session: `X in db`.

### MPCSV-L-03 — another workspace's project is 404
- **Rules:** `get_costs` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. K9 = cost, but `workspace_id W2.id`, `project_id PJ9.id`.

**When**
- `svc.get_costs(db, workspace_id=W1.id, user_id=U2.id, project_id=PJ9.id, limit=1000)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`, `exc.value.detail == f"Project with ID {PJ9.id} not found"`.

### MPCSV-L-04 — a deleted project is 404
- **Rules:** `get_costs` R1 (BUG-1278)
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the deleted project's costs are listed)

**Given**
1. KD = cost, but `project_id PJD.id`.

**When**
- `svc.get_costs(db, workspace_id=W1.id, user_id=U2.id, project_id=PJD.id, limit=1000)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`, `exc.value.detail == f"Project with ID {PJD.id} not found"`.

### MPCSV-L-05 — project id 0 is a project that does not exist
- **Rules:** `get_costs` R1 [BUG-2614]
- **Kind:** bug
- **Expect:** xfail BUG-2614 (revisit after launch)
- **Revisit:** after launch (owner 2026-11-10)
- **Fails today on:** Then 1 (no error: the workspace-wide list is returned)

**Given**
1. KA = cost.

**When**
- `svc.get_costs(db, workspace_id=W1.id, user_id=U2.id, project_id=0, limit=1000)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`, `exc.value.detail == "Project with ID 0 not found"`.

### MPCSV-L-06 — with a component: that component's costs only
- **Rules:** `get_costs` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. KA = cost, but `project_component_id C1.id`.
2. KB = cost.
3. KC = cost on C2 only.

**When**
- `result = svc.get_costs(db, workspace_id=W1.id, user_id=UG.id, project_component_id=C1.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {KA.id}`.

### MPCSV-L-07 — a component of a private project is 403
- **Rules:** `get_costs` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. KP = cost on CP only.

**When**
- `svc.get_costs(db, workspace_id=W1.id, user_id=UG.id, project_component_id=CP.id, limit=1000)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 403`, `exc.value.detail == NOACCESS`.

### MPCSV-L-08 — another workspace's component is 404
- **Rules:** `get_costs` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. K9 = cost, but `workspace_id W2.id`, `project_id None`, `project_component_id C9.id`.

**When**
- `svc.get_costs(db, workspace_id=W1.id, user_id=U2.id, project_component_id=C9.id, limit=1000)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`, `exc.value.detail == NOCOMP`.

### MPCSV-L-09 — component id 0 is a component that does not exist
- **Rules:** `get_costs` R2 [BUG-2614]
- **Kind:** bug
- **Expect:** xfail BUG-2614 (revisit after launch)
- **Revisit:** after launch (owner 2026-11-10)
- **Fails today on:** Then 1 (no error: the workspace-wide list is returned)

**Given**
1. KA = cost.

**When**
- `svc.get_costs(db, workspace_id=W1.id, user_id=U2.id, project_component_id=0, limit=1000)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`, `exc.value.detail == NOCOMP`.

### MPCSV-L-10 — workspace-wide: only W1's costs the caller may see
- **Rules:** `get_costs` R3; `_filter_accessible_costs` R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. K0 = cost, but `workspace_id W0.id`, `project_id PJ0.id`.
2. KA = cost.
3. KP = cost, but `project_id PJP.id`.
4. KC = cost on C2 only.
5. KU = cost unlinked.
6. KX = cost on C9 only.
7. K9 = cost, but `workspace_id W2.id`, `project_id PJ9.id`.

**When**
- `result = svc.get_costs(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {KA.id, KC.id}`.

### MPCSV-L-11 — workspace-wide leaves out a deleted project's costs
- **Rules:** `get_costs` R5 [BUG-2612]
- **Kind:** bug
- **Expect:** xfail BUG-2612
- **Fails today on:** Then 1 (the deleted project's cost is listed)

**Given**
1. KD = cost, but `project_id PJD.id`.
2. KA = cost.

**When**
- `result = svc.get_costs(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {KA.id}`.

### MPCSV-L-12 — hidden costs take no place on the page *(revised 2026-11-27, order sweep)*
- **Rules:** `get_costs` R4 [BUG-2611]
- **Kind:** bug
- **Expect:** xfail BUG-2611 (non-strict): fails only when physical order puts the filtered-out row on the page; strict proof is MPCSV-L-13, which checks the statement count only; no strict card proves the paging itself.
- **Fails today on:** Then 1 (the page is taken first: `[]`)

**Given**
1. KP1, KP2, KP3 = cost, but `project_id PJP.id`, `name "Hidden"` (three rows).
2. KA = cost, but `name "Open one"`.
3. KB = cost, but `project_id PJ2.id`, `name "Open two"`.

**When**
- `result = svc.get_costs(db, workspace_id=W1.id, user_id=UG.id, skip=0, limit=2)`.

**Then**
1. returns: `idset(result) == {KA.id, KB.id}`.

### MPCSV-L-13 — the statements do not grow with the rows
- **Rules:** `get_costs` R4 [BUG-2611]
- **Kind:** bug
- **Expect:** xfail BUG-2611
- **Fails today on:** Then 2 (up to two reads per cost)

**Given**
1. `for k in range(5): db.add(ProjectComponent(workspace_id=W1.id, project_id=PJ2.id, name=f"Part {k}")); db.flush()`, then one "cost on C only" per new component (five costs) (commit point after this line).
2. recorder.

**When**
- `result = svc.get_costs(db, workspace_id=W1.id, user_id=UG.id, limit=1000)`.

**Then**
1. returns: `len(result) == 5`.
2. count: at most 1 recorded statement contains `FROM project_components`.

### MPCSV-L-14 — the workspace-wide query orders by id
- **Rules:** `get_costs` R3 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 2 (no `ORDER BY`: BUG-100 is still open)

**Given**
1. KA = cost.
2. recorder.

**When**
- `result = svc.get_costs(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {KA.id}`.
2. count: `"id" in order_part`.

### MPCSV-L-15 — the workspace-wide list comes in id order
- **Rules:** `get_costs` R3 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (physical row order)

**Given**
1. KA = cost, but `name "Aa"`.
2. KB = cost, but `name "Bb"`.
3. KC = cost, but `name "Cc"`.
4. `KA.name = "Zz"; db.flush()` (the first row is updated after the three inserts, as the spec's Notes say, so it moves physically).

**When**
- `result = svc.get_costs(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `ids(result) == [KA.id, KB.id, KC.id]`.

### MPCSV-L-16 — limit 0 gives an empty list
- **Rules:** `get_costs` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. KA = cost.

**When**
- `result = svc.get_costs(db, workspace_id=W1.id, user_id=U2.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MPCSV-L-17 — a negative limit is a database error
- **Rules:** `get_costs` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. KA = cost.

**When**
- `svc.get_costs(db, workspace_id=W1.id, user_id=U2.id, limit=-1)`.

**Then**
1. raises: `DataError` in a savepoint.

### MPCSV-L-18 — the default limit is 100
- **Rules:** `get_costs` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows: `for k in range(101): db.add(MiscellaneousProjectCost(workspace_id=W1.id, project_id=PJ1.id, name=f"Cost {k}", amount=Decimal("1.00")))`, then `db.flush()`.

**When**
- `result = svc.get_costs(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `len(result) == 100`.

### MPCSV-L-19 — skip and limit page the visible costs
- **Rules:** `get_costs` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. KA, KB, KC, KD = cost, but `name "A"`, `"B"`, `"C"`, `"D"` (four rows).

**When**
- `result = svc.get_costs(db, workspace_id=W1.id, user_id=U2.id, skip=1, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `idset(result) <= {KA.id, KB.id, KC.id, KD.id}`.

## `MiscellaneousProjectCostService.get_by_id`

### MPCSV-G-01 — a cost on an open project is returned, nothing committed
- **Rules:** `get_by_id` R2, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. KA = cost (commit point after this line).
2. extra row X.

**When**
- spies: `result = svc.get_by_id(db, cost_id=KA.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == KA.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.

### MPCSV-G-02 — an unknown id gives None
- **Rules:** `get_by_id` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. KA = cost.

**When**
- `result = svc.get_by_id(db, cost_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.

### MPCSV-G-03 — id 0 gives None
- **Rules:** `get_by_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. KA = cost.

**When**
- `result = svc.get_by_id(db, cost_id=0, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.

### MPCSV-G-04 — a W0 cost (lower id) is not found in W1
- **Rules:** `get_by_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. K0 = cost, but `workspace_id W0.id`, `project_id PJ0.id`.
2. KA = cost.

**When**
- `result = svc.get_by_id(db, cost_id=K0.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.

### MPCSV-G-05 — a W2 cost (higher id) is not found in W1
- **Rules:** `get_by_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. KA = cost.
2. K9 = cost, but `workspace_id W2.id`, `project_id PJ9.id`.

**When**
- `result = svc.get_by_id(db, cost_id=K9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.

### MPCSV-G-06 — a private project's cost is 403, no rollback
- **Rules:** `get_by_id` R2, R5
- **Kind:** error
- **Expect:** pass

**Given**
1. KP = cost, but `project_id PJP.id` (commit point after this line).
2. extra row X.

**When**
- spies: `svc.get_by_id(db, cost_id=KP.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 403`, `exc.value.detail == NOACCESS`.
2. mock called: `rb.call_count == 0`.
3. session: `X in db`.

### MPCSV-G-07 — a component-only cost is checked against the component's project
- **Rules:** `get_by_id` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. KC = cost on C1 only.

**When**
- `result = svc.get_by_id(db, cost_id=KC.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == KC.id`.

### MPCSV-G-08 — a component-only cost on a private project is 403
- **Rules:** `get_by_id` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. KC = cost on CP only.

**When**
- `svc.get_by_id(db, cost_id=KC.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 403`, `exc.value.detail == NOACCESS`.

### MPCSV-G-09 — a cost with both links is checked against its project only
- **Rules:** `get_by_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. KB = cost, but `project_component_id CP.id`.

**When**
- `result = svc.get_by_id(db, cost_id=KB.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == KB.id`.

### MPCSV-G-10 — a deleted project's cost is 404
- **Rules:** `get_by_id` R2 (BUG-1278)
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the cost is returned)

**Given**
1. KD = cost, but `project_id PJD.id`.

**When**
- `svc.get_by_id(db, cost_id=KD.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`, `exc.value.detail == f"Project with ID {PJD.id} not found"`.

### MPCSV-G-11 — a stored cost naming another workspace's component is not found
- **Rules:** `get_by_id` R3 [BUG-2616]
- **Kind:** bug
- **Expect:** xfail BUG-2616
- **Fails today on:** Then 1 (the cost is returned to any member)

**Given**
1. KX = cost on C9 only.

**When**
- `result = svc.get_by_id(db, cost_id=KX.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is None`.

### MPCSV-G-12 — an unlinked cost is returned to any member
- **Rules:** `get_by_id` R4
- **Kind:** boundary
- **Expect:** pass
- **Revisit:** after launch (owner 2026-11-10)

**Given**
1. KU = cost unlinked.

**When**
- `result = svc.get_by_id(db, cost_id=KU.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == KU.id`.

## `MiscellaneousProjectCostService.create_cost`

### MPCSV-C-01 — a cost on a project is stored, committed once and re-read
- **Rules:** `create_cost` R1, R6, R8 (M-TC1, M-TC2)
- **Kind:** happy
- **Expect:** pass

**Given**
1. No cost (commit point after this line).

**When**
- spies: `result = svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_id=PJ1.id, name="Crane hire", description="Two days", amount=50.0), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`, `result.created_at is not None`.
2. mock called: `cm.call_count == 1`.
3. mock called: `rb.call_count == 0`.
4. committed: the row with id `result.id` has `workspace_id == W1.id`, `project_id == PJ1.id`, `project_component_id is None`.
5. committed: that row has `name == "Crane hire"`, `description == "Two days"`, `amount == Decimal("50.00")`.

### MPCSV-C-02 — creating on a project logs cost_added with component_id None
- **Rules:** `create_cost` R7; `_log_cost_activity` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No cost (commit point after this line).

**When**
- `result = svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_id=PJ1.id, name="Crane hire", amount=50.0), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`.
2. event: events(PJ1, "cost_added") has exactly 1 row.
3. event: that event `workspace_id == W1.id`, `performed_by == UG.id`, `description == 'Added cost "Crane hire"'`.
4. event: that event `metadata_json == {"cost_id": result.id, "cost_name": "Crane hire", "component_id": None}`.

### MPCSV-C-03 — creating on a component logs on the component's project
- **Rules:** `create_cost` R1, R7; `_log_cost_activity` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No cost (commit point after this line).

**When**
- `result = svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_component_id=C1.id, name="Scaffold", amount=20.0), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.project_component_id == C1.id`, `result.project_id is None`.
2. event: events(PJ1, "cost_added") has exactly 1 row.
3. event: that event `metadata_json == {"cost_id": result.id, "cost_name": "Scaffold", "component_id": C1.id, "component_name": "Roof"}`.

### MPCSV-C-04 — a component of the named project is accepted with both ids
- **Rules:** `create_cost` R2 (the side that holds today and after BUG-2615)
- **Kind:** happy
- **Expect:** pass

**Given**
1. No cost (commit point after this line).

**When**
- `result = svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_id=PJ1.id, project_component_id=C1.id, name="Scaffold", amount=20.0), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.project_id == PJ1.id`, `result.project_component_id == C1.id`.
2. event: events(PJ1, "cost_added") has exactly 1 row.

### MPCSV-C-05 — a private project is 403, rolled back once, pending changes discarded
- **Rules:** `create_cost` R1, R8 (M-TC3)
- **Kind:** error
- **Expect:** pass

**Given**
1. No cost (commit point after this line).
2. extra row X.

**When**
- spies: `svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_id=PJP.id, name="Crane hire", amount=50.0), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 403`, `exc.value.detail == NOACCESS`.
2. mock called: `rb.call_count == 1`.
3. count: x_gone.
4. nothing written.

### MPCSV-C-06 — a component of a private project is 403
- **Rules:** `create_cost` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No cost (commit point after this line).

**When**
- `svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_component_id=CP.id, name="Crane hire", amount=50.0), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 403`, `exc.value.detail == NOACCESS`.
2. nothing written.

### MPCSV-C-07 — another workspace's project is 404
- **Rules:** `create_cost` R1 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No cost (commit point after this line).

**When**
- `svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_id=PJ9.id, name="Crane hire", amount=50.0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`, `exc.value.detail == f"Project with ID {PJ9.id} not found"`.
2. nothing written.

### MPCSV-C-08 — another workspace's component alone is 404
- **Rules:** `create_cost` R1 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No cost (commit point after this line).

**When**
- `svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_component_id=C9.id, name="Crane hire", amount=50.0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`, `exc.value.detail == NOCOMP`.
2. nothing written.

### MPCSV-C-09 — a deleted project is 404
- **Rules:** `create_cost` R1 (BUG-1278)
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the cost is created)

**Given**
1. No cost (commit point after this line).

**When**
- `svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_id=PJD.id, name="Crane hire", amount=50.0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`, `exc.value.detail == f"Project with ID {PJD.id} not found"`.
2. nothing written.

### MPCSV-C-10 — project id 0 is refused as not found
- **Rules:** `create_cost` R1 [BUG-2614]
- **Kind:** bug
- **Expect:** xfail BUG-2614 (revisit after launch)
- **Revisit:** after launch (owner 2026-11-10)
- **Fails today on:** Then 1 (the call raises IntegrityError: the guard is skipped)

**Given**
1. No cost (commit point after this line).

**When**
- `svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_id=0, name="Crane hire", amount=50.0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`, `exc.value.detail == "Project with ID 0 not found"`.
2. nothing written.

### MPCSV-C-11 — component id 0 is refused as not found
- **Rules:** `create_cost` R1 [BUG-2614]
- **Kind:** bug
- **Expect:** xfail BUG-2614 (revisit after launch)
- **Revisit:** after launch (owner 2026-11-10)
- **Fails today on:** Then 1 (the call raises IntegrityError: the guard is skipped)

**Given**
1. No cost (commit point after this line).

**When**
- `svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_component_id=0, name="Crane hire", amount=50.0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`, `exc.value.detail == NOCOMP`.
2. nothing written.

### MPCSV-C-12 — a component of another open project is refused
- **Rules:** `create_cost` R2 [BUG-2615]
- **Kind:** bug
- **Expect:** xfail BUG-2615
- **Fails today on:** Then 1 (no error: the cost is stored)

**Given**
1. No cost (commit point after this line).

**When**
- `svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_id=PJ2.id, project_component_id=C1.id, name="Crane hire", amount=50.0), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`, `exc.value.detail == NOTPART`.
2. nothing written.

### MPCSV-C-13 — a private project's component named with an open project is 403, never 400
- **Rules:** `create_cost` R2 [BUG-2615]
- **Kind:** bug
- **Expect:** xfail BUG-2615
- **Fails today on:** Then 1 (no error: the cost is stored and logged on the private project)

**Given**
1. No cost (commit point after this line).

**When**
- `svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_id=PJ2.id, project_component_id=CP.id, name="Crane hire", amount=50.0), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 403`, `exc.value.detail == NOACCESS`.
2. nothing written.

### MPCSV-C-14 — another workspace's component named with an own project is 404
- **Rules:** `create_cost` R2 [BUG-1013]
- **Kind:** bug
- **Expect:** xfail BUG-1013
- **Fails today on:** Then 1 (no error: the cost is stored)

**Given**
1. No cost (commit point after this line).

**When**
- `svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_id=PJ1.id, project_component_id=C9.id, name="Crane hire", amount=50.0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`, `exc.value.detail == NOCOMP`.
2. nothing written.

### MPCSV-C-15 — neither id: stored unlinked, no event
- **Rules:** `create_cost` R3
- **Kind:** boundary
- **Expect:** pass
- **Revisit:** after launch (owner 2026-11-10)

**Given**
1. No cost (commit point after this line).

**When**
- `result = svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(name="Crane hire", amount=50.0), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.project_id is None`, `result.project_component_id is None`.
2. committed: the row with id `result.id` exists in W1.
3. count: all_events() has 0 rows.

### MPCSV-C-16 — a whitespace-only name is refused by the schema
- **Rules:** `create_cost` R4 [BUG-2613]
- **Kind:** bug
- **Expect:** xfail BUG-2613
- **Fails today on:** Then 1 (no error: the schema accepts it)

**Given**
1. Nothing (target `schema`).

**When**
- build `MiscellaneousProjectCostCreate(project_id=PJ1.id, name="  ", amount=50.0)`.

**Then**
1. raises: `PydanticValidationError`.

### MPCSV-C-17 — an empty name is refused by the schema
- **Rules:** `create_cost` R4 [BUG-2613]
- **Kind:** bug
- **Expect:** xfail BUG-2613
- **Fails today on:** Then 1 (no error: the schema accepts it)

**Given**
1. Nothing (target `schema`).

**When**
- build `MiscellaneousProjectCostCreate(project_id=PJ1.id, name="", amount=50.0)`.

**Then**
1. raises: `PydanticValidationError`.

### MPCSV-C-18 — the name is stored trimmed
- **Rules:** `create_cost` R4 [BUG-2613]
- **Kind:** bug
- **Expect:** xfail BUG-2613
- **Fails today on:** Then 2 (stored as typed)

**Given**
1. No cost (commit point after this line).

**When**
- `result = svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_id=PJ1.id, name="  Crane  hire ", amount=50.0), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the row with id `result.id` has `name == "Crane  hire"`.

### MPCSV-C-19 — the amount is rounded half up to 2 places
- **Rules:** `create_cost` R5
- **Kind:** boundary
- **Expect:** pass
- **Revisit:** after launch (owner 2026-11-10)

**Given**
1. No cost (commit point after this line).

**When**
- `result = svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_id=PJ1.id, name="Crane hire", amount=10.125), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.amount == Decimal("10.13")`.
2. committed: the row with id `result.id` has `amount == Decimal("10.13")`.

### MPCSV-C-20 — a negative amount is stored
- **Rules:** `create_cost` R5 (OQ-28)
- **Kind:** boundary
- **Expect:** pass
- **Revisit:** after launch (owner 2026-11-10)

**Given**
1. No cost (commit point after this line).

**When**
- `result = svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_id=PJ1.id, name="Refund", amount=-5), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.amount == Decimal("-5.00")`.
2. committed: the row with id `result.id` has `amount == Decimal("-5.00")`.

### MPCSV-C-21 — 13 integer digits fit
- **Rules:** `create_cost` R5 [BUG-2618] (the side that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No cost (commit point after this line).

**When**
- `result = svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_id=PJ1.id, name="Big", amount=9999999999999.0), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the row with id `result.id` has `amount == Decimal("9999999999999.00")`.

### MPCSV-C-22 — 14 integer digits are refused by the schema
- **Rules:** `create_cost` R5 [BUG-2618]
- **Kind:** bug
- **Expect:** xfail BUG-2618
- **Fails today on:** Then 1 (no error: the schema accepts it)

**Given**
1. Nothing (target `schema`).

**When**
- build `MiscellaneousProjectCostCreate(project_id=PJ1.id, name="Big", amount=10000000000000.0)`.

**Then**
1. raises: `PydanticValidationError`.

### MPCSV-C-23 — a failing commit rolls back once and saves nothing
- **Rules:** `create_cost` R8 (M-TC4)
- **Kind:** error
- **Expect:** pass

**Given**
1. No cost (commit point after this line).

**When**
- failing commit: `svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_id=PJ1.id, name="Crane hire", amount=50.0), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. nothing written.

### MPCSV-C-24 — a failing re-read after the commit keeps the cost
- **Rules:** `create_cost` R8 (M-TC5)
- **Kind:** error
- **Expect:** pass

**Given**
1. No cost (commit point after this line).

**When**
- failing refresh: `svc.create_cost(db, cost_in=MiscellaneousProjectCostCreate(project_id=PJ1.id, name="Crane hire", amount=50.0), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: exactly one `MiscellaneousProjectCost` row in W1 with `name == "Crane hire"`.

## `MiscellaneousProjectCostService.update_cost`

### MPCSV-U-01 — a rename is saved, committed once, and logged
- **Rules:** `update_cost` R2, R5, R6 (M-TC1, M-TC2)
- **Kind:** happy
- **Expect:** pass

**Given**
1. K = cost, but `description "Old"` (commit point after this line).

**When**
- spies: `result = svc.update_cost(db, cost_id=K.id, cost_in=MiscellaneousProjectCostUpdate(name="Crane hire"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == K.id`, `result.name == "Crane hire"`, `result.created_at is not None`.
2. mock called: `cm.call_count == 1`.
3. committed: K has `name == "Crane hire"`, `description == "Old"`, `amount == Decimal("100.00")`.
4. event: events(PJ1, "cost_updated") has exactly 1 row.
5. event: that event `performed_by == UG.id`, `description == 'Updated cost "Crane hire"'`, `metadata_json == {"cost_id": K.id, "cost_name": "Crane hire", "component_id": None}`.

### MPCSV-U-02 — null fields stay, a sent amount is applied
- **Rules:** `update_cost` R2, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K = cost, but `description "Old"` (commit point after this line).

**When**
- `result = svc.update_cost(db, cost_id=K.id, cost_in=MiscellaneousProjectCostUpdate(name=None, description=None, amount=7.5), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.amount == Decimal("7.50")`.
2. committed: K has `name == "Crane"`, `description == "Old"`, `amount == Decimal("7.50")`.

### MPCSV-U-03 — an unknown id gives None, no commit, no rollback
- **Rules:** `update_cost` R1 (M-TC6)
- **Kind:** error
- **Expect:** pass

**Given**
1. K = cost (commit point after this line).
2. extra row X.

**When**
- spies: `result = svc.update_cost(db, cost_id=MISSING, cost_in=MiscellaneousProjectCostUpdate(name="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.
5. unchanged: unchanged(K).

### MPCSV-U-04 — a W2 cost is not found in W1
- **Rules:** `update_cost` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. K9 = cost, but `workspace_id W2.id`, `project_id PJ9.id` (commit point after this line).

**When**
- `result = svc.update_cost(db, cost_id=K9.id, cost_in=MiscellaneousProjectCostUpdate(name="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(K9).

### MPCSV-U-05 — a private project's cost is 403, rolled back, unchanged
- **Rules:** `update_cost` R1 (M-TC3)
- **Kind:** error
- **Expect:** pass

**Given**
1. KP = cost, but `project_id PJP.id` (commit point after this line).
2. extra row X.

**When**
- spies: `svc.update_cost(db, cost_id=KP.id, cost_in=MiscellaneousProjectCostUpdate(name="New"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 403`, `exc.value.detail == NOACCESS`.
2. mock called: `rb.call_count == 1`.
3. count: x_gone.
4. unchanged: unchanged(KP).

### MPCSV-U-06 — a stored cost naming another workspace's component is not found
- **Rules:** `update_cost` R1 [BUG-2616]
- **Kind:** bug
- **Expect:** xfail BUG-2616
- **Fails today on:** Then 1 (the cost is found and renamed)

**Given**
1. KX = cost on C9 only (commit point after this line).

**When**
- `result = svc.update_cost(db, cost_id=KX.id, cost_in=MiscellaneousProjectCostUpdate(name="New"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(KX).

### MPCSV-U-07 — an empty update returns the cost unchanged
- **Rules:** `update_cost` R2, R6 (the side independent of BUG-2617)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K = cost (commit point after this line).

**When**
- `result = svc.update_cost(db, cost_id=K.id, cost_in=MiscellaneousProjectCostUpdate(), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == K.id`.
2. unchanged: unchanged(K).

### MPCSV-U-08 — an empty update writes no event
- **Rules:** `update_cost` R5 [BUG-2617]
- **Kind:** bug
- **Expect:** xfail BUG-2617
- **Fails today on:** Then 2 (one `cost_updated` event is written)

**Given**
1. K = cost (commit point after this line).

**When**
- `result = svc.update_cost(db, cost_id=K.id, cost_in=MiscellaneousProjectCostUpdate(), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == K.id`.
2. count: events(PJ1, "cost_updated") has 0 rows.

### MPCSV-U-09 — the same values again write no event
- **Rules:** `update_cost` R5 [BUG-2617]
- **Kind:** bug
- **Expect:** xfail BUG-2617
- **Fails today on:** Then 2 (one `cost_updated` event is written)

**Given**
1. K = cost (commit point after this line).

**When**
- `result = svc.update_cost(db, cost_id=K.id, cost_in=MiscellaneousProjectCostUpdate(name="Crane", amount=100.0), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.name == "Crane"`.
2. count: events(PJ1, "cost_updated") has 0 rows.

### MPCSV-U-10 — a component cost's update logs on the component's project
- **Rules:** `update_cost` R5; `_log_cost_activity` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. K = cost on C1 only (commit point after this line).

**When**
- `result = svc.update_cost(db, cost_id=K.id, cost_in=MiscellaneousProjectCostUpdate(name="Scaffold"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.name == "Scaffold"`.
2. event: events(PJ1, "cost_updated") has exactly 1 row.
3. event: that event `metadata_json == {"cost_id": K.id, "cost_name": "Scaffold", "component_id": C1.id, "component_name": "Roof"}`.

### MPCSV-U-11 — an unlinked cost's update writes no event
- **Rules:** `update_cost` R5
- **Kind:** boundary
- **Expect:** pass
- **Revisit:** after launch (owner 2026-11-10)

**Given**
1. KU = cost unlinked (commit point after this line).

**When**
- `result = svc.update_cost(db, cost_id=KU.id, cost_in=MiscellaneousProjectCostUpdate(name="Scaffold"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.name == "Scaffold"`.
2. count: all_events() has 0 rows.

### MPCSV-U-12 — a blank name is refused by the update schema
- **Rules:** `update_cost` R3 [BUG-2613]
- **Kind:** bug
- **Expect:** xfail BUG-2613
- **Fails today on:** Then 1 (no error: the schema accepts it)

**Given**
1. Nothing (target `schema`).

**When**
- build `MiscellaneousProjectCostUpdate(name="  ")`.

**Then**
1. raises: `PydanticValidationError`.

### MPCSV-U-13 — 14 integer digits are refused by the update schema
- **Rules:** `update_cost` R4 [BUG-2618]
- **Kind:** bug
- **Expect:** xfail BUG-2618
- **Fails today on:** Then 1 (no error: the schema accepts it)

**Given**
1. Nothing (target `schema`).

**When**
- build `MiscellaneousProjectCostUpdate(amount=10000000000000.0)`.

**Then**
1. raises: `PydanticValidationError`.

### MPCSV-U-14 — a failing commit rolls back once and the cost is unchanged
- **Rules:** `update_cost` R6 (M-TC4)
- **Kind:** error
- **Expect:** pass

**Given**
1. K = cost (commit point after this line).

**When**
- failing commit: `svc.update_cost(db, cost_id=K.id, cost_in=MiscellaneousProjectCostUpdate(name="New"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. unchanged: unchanged(K).
4. nothing written.

### MPCSV-U-15 — a failing re-read after the commit keeps the rename
- **Rules:** `update_cost` R6 (M-TC5)
- **Kind:** error
- **Expect:** pass

**Given**
1. K = cost (commit point after this line).

**When**
- failing refresh: `svc.update_cost(db, cost_id=K.id, cost_in=MiscellaneousProjectCostUpdate(name="New"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: K has `name == "New"`.

## `MiscellaneousProjectCostService.delete_cost`

### MPCSV-D-01 — delete removes the row, keeps the event, commits once
- **Rules:** `delete_cost` R2, R3 (M-TC1)
- **Kind:** happy
- **Expect:** pass

**Given**
1. K = cost (commit point after this line).

**When**
- spies: `result = svc.delete_cost(db, cost_id=K.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is True`.
2. mock called: `cm.call_count == 1`.
3. committed: no `MiscellaneousProjectCost` row with id `K.id`.
4. committed: events(PJ1, "cost_deleted") has exactly 1 row.
5. committed: that event `performed_by == UG.id`, `description == 'Deleted cost "Crane"'`, `metadata_json == {"cost_id": K.id, "cost_name": "Crane", "component_id": None}`.

### MPCSV-D-02 — an unknown id gives False, no commit, no rollback
- **Rules:** `delete_cost` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. K = cost (commit point after this line).
2. extra row X.

**When**
- spies: `result = svc.delete_cost(db, cost_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is False`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `X in db`.
5. unchanged: unchanged(K).

### MPCSV-D-03 — a W0 cost is not found in W1
- **Rules:** `delete_cost` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. K0 = cost, but `workspace_id W0.id`, `project_id PJ0.id` (commit point after this line).

**When**
- `result = svc.delete_cost(db, cost_id=K0.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is False`.
2. unchanged: unchanged(K0).

### MPCSV-D-04 — a private project's cost is 403, rolled back, kept
- **Rules:** `delete_cost` R1, R3 (M-TC3)
- **Kind:** error
- **Expect:** pass

**Given**
1. KP = cost, but `project_id PJP.id` (commit point after this line).
2. extra row X.

**When**
- spies: `svc.delete_cost(db, cost_id=KP.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 403`, `exc.value.detail == NOACCESS`.
2. mock called: `rb.call_count == 1`.
3. count: x_gone.
4. unchanged: unchanged(KP).

### MPCSV-D-05 — a stored cost naming another workspace's component is not found
- **Rules:** `delete_cost` R1 [BUG-2616]
- **Kind:** bug
- **Expect:** xfail BUG-2616
- **Fails today on:** Then 1 (the cost is deleted)

**Given**
1. KX = cost on C9 only (commit point after this line).

**When**
- `result = svc.delete_cost(db, cost_id=KX.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is False`.
2. unchanged: unchanged(KX).

### MPCSV-D-06 — an unlinked cost is deleted with no event
- **Rules:** `delete_cost` R2
- **Kind:** boundary
- **Expect:** pass
- **Revisit:** after launch (owner 2026-11-10)

**Given**
1. KU = cost unlinked (commit point after this line).

**When**
- `result = svc.delete_cost(db, cost_id=KU.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result is True`.
2. committed: no `MiscellaneousProjectCost` row with id `KU.id`.
3. count: all_events() has 0 rows.

### MPCSV-D-07 — a failing commit keeps the cost and writes no event
- **Rules:** `delete_cost` R3 (M-TC4)
- **Kind:** error
- **Expect:** pass

**Given**
1. K = cost (commit point after this line).

**When**
- failing commit: `svc.delete_cost(db, cost_id=K.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 1`.
3. unchanged: unchanged(K).
4. nothing written.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_costs` R7 [BUG-2610] (HR-7) | `GET /miscellaneous-project-costs/` | `limit=0` and negative → 422; `limit` 1 and 100 accepted; 101 → 422; `skip >= 0` |
| Integration-only | `/miscellaneous-project-costs/` endpoints | `None` / `False` → 404 `Miscellaneous project cost not found`; schema errors → 422; create answers 201, delete 204 |
| `require_project_access` / `require_component_access` details, BUG-1278, BUG-1192 | `tests/unit/managers/project_manager.cases.md` | the guard itself; here only pass-through cards |
| DAO lists `get_by_project` / `get_by_component` (BUG-2460, BUG-2461), column rounding | `tests/unit/dao/miscellaneous_project_cost.cases.md` | order, filters, `Numeric(15,2)` half-up rounding |

## Spec gaps
None. Gaps 1–3 of Revision 1 are closed by the spec's Gap log (G1–G3, 2026-11-10).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_log_cost_activity` | R1 | MPCSV-LA-01, LA-02; C-03, U-10 |
| | R2 | LA-03, LA-04 (xfail BUG-1192); C-02 |
| | R3 | LA-05; C-15, U-11, D-06 |
| | R4 | LA-06 |
| `_filter_accessible_costs` | R1 | FA-01 |
| | R2 | FA-01; L-10 |
| | R3 [BUG-2612] | FA-05 (xfail) |
| | R4 | FA-01, FA-02, FA-03, FA-04 |
| | R5 | FA-06 |
| `get_costs` | R1 | L-01, L-02, L-03, L-04 (xfail BUG-1278) |
| | R1, R2 [BUG-2614] | L-05, L-09 (xfail) |
| | R2 | L-06, L-07, L-08 |
| | R3 [BUG-100] | L-10; L-14 (strict), L-15 (non-strict) |
| | R4 [BUG-2611] | L-12, L-13 (xfail) |
| | R5 [BUG-2612] | L-11 (xfail) |
| | R6 (M-TC6) | L-01, L-02 |
| | R7 | L-16, L-17, L-18, L-19; BUG-2610 deferred |
| `get_by_id` | R1 | G-02, G-03, G-04, G-05 |
| | R2 | G-01, G-06, G-07, G-08, G-09, G-10 (xfail BUG-1278) |
| | R3 [BUG-2616] | G-11 (xfail) |
| | R4 | G-12 |
| | R5 (M-TC6) | G-01, G-06 |
| `create_cost` | R1 | C-01, C-03, C-05 … C-08, C-09 (xfail BUG-1278) |
| | R1 [BUG-2614] | C-10, C-11 (xfail) |
| | R2 [BUG-1013, BUG-2615] | C-12, C-13, C-14 (xfail); C-04 (pass) |
| | R3 | C-15 |
| | R4 [BUG-2613] | C-16, C-17, C-18 (xfail) |
| | R5 [BUG-2618] | C-19, C-20, C-21 (pass); C-22 (xfail) |
| | R6 | C-01 |
| | R7 | C-02, C-03 |
| | R8 (M-TC1–M-TC5) | C-01, C-05, C-23, C-24 |
| `update_cost` | R1 | U-03, U-04, U-05; [BUG-2616] U-06 (xfail) |
| | R2 | U-01, U-02, U-07 |
| | R3 [BUG-2613] | U-12 (xfail) |
| | R4 [BUG-2618] | U-02 (pass); U-13 (xfail) |
| | R5 [BUG-2617] | U-01, U-10, U-11 (pass); U-08, U-09 (xfail) |
| | R6 (M-TC1–M-TC5) | U-01, U-05, U-14, U-15 |
| `delete_cost` | R1 | D-02, D-03, D-04; [BUG-2616] D-05 (xfail) |
| | R2 | D-01, D-06 |
| | R3 (M-TC1, M-TC3, M-TC4) | D-01, D-04, D-07 |
