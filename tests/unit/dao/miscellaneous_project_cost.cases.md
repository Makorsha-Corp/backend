# Test cases — `app/dao/miscellaneous_project_cost.py`

> **Spec:** `tests/unit/dao/miscellaneous_project_cost.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-10; nothing open). Q1 / BUG-2461 was decided by Claude under the reviewer's delegation; OQ-28 was answered by the owner (2026-11-10).
> **Revision:** 2 (2026-11-10) — spec apply-review + Gap log G1–G3 and OQ-28. OQ-28 (owner): projects are revisited after launch and today's behaviour is kept as the new inherited R2a. The five `MPC-OQ28` cards keep their IDs and move under R2a, tagged revisit after launch; the "Pending owner answer" section is gone. The BUG-2460 / BUG-2461 cards stay, tagged revisit after launch in their reason. G1: 13 integer digits fit — new MPC-INH-13, INH-14; INH-07 now uses `10000000000000.00`. G2: new R2b (create through the schema: dump plus `workspace_id`) — new MPC-INH-15 … INH-20, OQ28-06, OQ28-07. G3: `project_id=None` keeps its meaning after the BUG-2461 fix — GP-11, GP-23 stand; new MPC-GP-36. No card retired.
> **Revision:** 3 (2026-11-10) — `miscellaneous_project_cost.verify.md` findings 1–2. F1: MPC-GP-13 and GC-11 check `"FOR UPDATE" not in sql` instead of the vacuous `lock_part == ""`. F2: MPC-GP-25 ends its Given with `db.expire_all()`, as the test already does. Conventions gain "No-lock check" and "Clear the session before a one-query check". Counts unchanged; no ID retired.
> **Counts:** 87 cases · 74 expected-to-pass (7 of them R2a, revisit after launch) · 13 expected-to-fail (bugs) · 5 deferred

## Reviewer summary
- **Per callable:** `get_by_project` 36 (9 bug) · `get_by_component` 24 (3 bug) · inherited `BaseDAO` facts 20 (1 bug) · inherited R2a (negative and zero amounts, OQ-28) 7.
- **Depth:** full. The DAO only reads, but the table holds money: every rounding fact of the `Numeric(15,2)` column is checked with values where half up and half even differ (2.125, 0.005, 1000.005, 0.125, -1.005) and a control (2.124), as exact `Decimal` compares.
- **Revisit after launch (owner 2026-11-10):** the 12 BUG-2460 / BUG-2461 cards and the 7 R2a cards carry the header line `Revisit: after launch`; nothing else about them changes.
- **Expected-to-fail:** BUG-2460 6 (GP-26, GP-27, GC-22, GC-23 non-strict; GP-28, GC-24 strict SQL alarms) · BUG-2461 6 strict (GP-29 … GP-34; each fails because a component-only cost of the project is missing today) · BUG-100 1 strict SQL alarm (INH-01).
- **Notable design choices:**
  - Workspace filters: W0 (before W1) and W2 (after) each hold costs on their own project / component, and W1 asks for that id, so `<=` / `>=` cannot pass. No pass card builds a cross-workspace link; the one invalid shape (GP-33, a W2 component under a W1 project) only proves the fixed BUG-2461 path refuses it.
  - Passing cards never compare an order (no `ORDER BY` today): they compare sets or lengths. Order cards are non-strict, renaming the lowest-id row under **seqscan**; one strict SQL alarm per query.
  - Pass cards of `get_by_project` never put a component-only cost of the asked project in the Given, so they hold before and after the BUG-2461 fix.
  - Negative and zero amounts appear only in the R2a section (OQ-28 answered: stored, no bug, revisit after launch).
  - Create through the schema follows the service's path (R2b): `model_dump()` plus `workspace_id`, then `create` with that dict. MPC-INH-20 pins that the schema object alone fails with 23502.
  - `Numeric(15,2)` bounds: 13 integer digits fit (INH-13, INH-19); 14 fail with 22003, both directly (INH-07) and after rounding (INH-14).
  - Inherited `get_by_id_and_workspace`, `create`, `update`, `remove` mechanics are left to `base.cases.md`; only this table's money facts and clock get cards.
- **Needs a decision:** none. Gaps 1–3 of revision 1 are closed by the spec's Gap log (2026-11-10).

## Conventions for this module

**IDs.** `MPC` = `app/dao/miscellaneous_project_cost.py`. `GP` get_by_project · `GC` get_by_component · `INH` inherited `BaseDAO` facts · `OQ28` inherited R2a (negative and zero amounts; the code keeps the name of the owner question OQ-28 that decided it).

**Actors and fixed values.**
- `dao` = the singleton `miscellaneous_project_cost_dao` (`from app.dao.miscellaneous_project_cost import miscellaneous_project_cost_dao`). `db` = the test's real session, first argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- `MiscellaneousProjectCost` = `app.models.miscellaneous_project_cost.MiscellaneousProjectCost`; `MiscellaneousProjectCostCreate`, `MiscellaneousProjectCostUpdate` = the classes of `app.schemas.miscellaneous_project_cost`. `Factory`, `Project`, `ProjectComponent` = `app.models.factory`, `.project`, `.project_component`. `utcnow` = `app.utils.time.utcnow`. `Decimal`, `datetime`, `text`, `select`, `func` = the usual ones.
- MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`. T0 = `datetime(2026, 3, 1, 9, 0, 0)`, T1 = `datetime(2026, 3, 2, 9, 0, 0)` (naive).

**Externals.** None. Nothing is mocked; no clock is patched.

**Standing rows** (every test, this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` three times (`W0.id < W1.id < W2.id`). U1, U2, U3 = `make_profile(db)` three times.
2. F0 = `Factory(workspace_id=W0.id, name="Factory Zero", abbreviation="F0")`, F1 = `(W1, "Factory One", "F1")`, F2 = `(W2, "Factory Two", "F2")`.
3. Projects `Project(workspace_id=…, factory_id=…, name=…, description="Main")`: PJ0 (W0, F0, `"Project Zero"`), PJA (W1, F1, `"Project A"`), PJ1 (W1, F1, `"Bridge A"`), PJB (W1, F1, `"Project B"`), PJD (W1, F1, `"Old Bridge"`, `is_deleted=True, deleted_at=T0, deleted_by=U1.id`), PJX (W2, F2, `"Project X"`). So `PJA.id < PJ1.id < PJB.id`.
4. Components `ProjectComponent(workspace_id=…, project_id=…, name=…)`: C0 (W0, PJ0, `"Zero part"`), CA (W1, PJA, `"Arch"`), C1 (W1, PJ1, `"Deck"`), C2 (W1, PJ1, `"Rail"`), CB (W1, PJB, `"Pier"`), CDL (W1, PJD, `"Floor"`), CX (W2, PJX, `"Deck"`). So `CA.id < C1.id < C2.id`.

**Given rows.** Inserted directly (never through `dao`), flushed one at a time in the order written. After "but" a line lists every column that differs. A line written as code is a step to run exactly, at that place.
- **cost** = `MiscellaneousProjectCost(workspace_id=W1.id, project_id=PJ1.id, name="Crane", amount=Decimal("100.00"), created_at=T1)`; `project_component_id` and `description` None. No cost exists unless the Given lists it.
- "component-only on C" = cost, but `project_id None`, `project_component_id C.id`. "unlinked" = cost, but `project_id None`.
- **seqscan** = run `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`, in this order.
- **Dhaka** = `db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))`.
- **dump(S)** = `{**S.model_dump(), "workspace_id": W1.id}` for a `MiscellaneousProjectCostCreate` S: the service's create path (spec R2b).

**Named checks.**
- **ids(result)** = `[r.id for r in result]`, order part of the check. **idset(result)** = `{r.id for r in result}`.
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. **unchanged(X)** = after re-read every column of X equals its value before the call.
- **nothing written** = the number of `miscellaneous_project_costs` rows (all workspaces) equals its value before the call. A pending row is not stored.
- `pending:` / `session:` lines check the session right after the call, before anything expires it; they come before `nothing written:`.
- Amounts are compared as `Decimal` (`Decimal("2.13")`), never as strings or floats.
- `raises: DataError`, `raises: IntegrityError` = the `sqlalchemy.exc` classes: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call; keep using `db`. Later `raises:` lines assert on `exc.value.orig`, one per line.
- **Statement recorder** = the SQL the session sends during the When is recorded. `sql` = the one `SELECT` from `miscellaneous_project_costs`; `order_part` = text of `sql` after its first `ORDER BY`, before any `LIMIT` (`""` if none); `lock_part` = text of `sql` after `FOR UPDATE` (`""` if none); `written` = every recorded `INSERT`, `UPDATE`, `DELETE`.
- **No-lock check** = `"FOR UPDATE" not in sql`. Never use `lock_part == ""` for this: Postgres prints the lock clause last, so the text after `FOR UPDATE` is empty with a lock as well.
- **Clear the session before a one-query check**: a card that counts the SELECTs a call sends (or reads stored values back) ends its Given with `db.expunge_all()` (or `db.expire_all()` where the card says so), so a row the identity map still holds (a profile, a just-inserted value) cannot hide a second read. Ids used in Then come from objects built before it; their loaded attributes stay readable.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`, for an order that rests on physical row order. Write calls and checks exactly; never weaken an assertion.

**Revisit after launch.** A card with the header line `- **Revisit:** after launch (owner 2026-11-10)` is written and run as usual. On an xfail card the reason carries the tag: `pytest.mark.xfail(strict=…, reason="BUG-n (revisit after launch)")`. On a pass card, add `revisit after launch (owner 2026-11-10)` to the docstring.

**Race simulations.** None.

## `DAOMiscellaneousProjectCost.get_by_project`

### MPC-GP-01 — returns the project's costs with their stored values
- **Rules:** `get_by_project` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = cost.
2. B = cost, but `name "Lift hire"`, `description "Two days"`, `amount Decimal("1200.50")`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {A.id, B.id}`.
3. returns: `len(result) == 2`.
4. returns: `[r for r in result if r.id == B.id][0].amount == Decimal("1200.50")`.
5. returns: `[r for r in result if r.id == B.id][0].description == "Two days"`.

### MPC-GP-02 — costs of a lower-id and a higher-id project are not returned
- **Rules:** `get_by_project` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. XA = cost, but `project_id PJA.id`.
2. A = cost.
3. XB = cost, but `project_id PJB.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MPC-GP-03 — W1 asking for W2's project gets nothing, though W2 has costs on it
- **Rules:** `get_by_project` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = cost.
2. X2 = cost, but `workspace_id W2.id`, `project_id PJX.id`.
3. KX = cost, but `workspace_id W2.id`, `project_id None`, `project_component_id CX.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MPC-GP-04 — W1 asking for W0's project gets nothing, though W0 has costs on it
- **Rules:** `get_by_project` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = cost, but `workspace_id W0.id`, `project_id PJ0.id`.
2. K0 = cost, but `workspace_id W0.id`, `project_id None`, `project_component_id C0.id`.
3. A = cost.

**When**
- `result = dao.get_by_project(db, project_id=PJ0.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MPC-GP-05 — W2 gets its own project's cost, not W0's or W1's
- **Rules:** `get_by_project` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = cost, but `workspace_id W0.id`, `project_id PJ0.id`.
2. A = cost.
3. X2 = cost, but `workspace_id W2.id`, `project_id PJX.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJX.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X2.id]`.

### MPC-GP-06 — an unknown project id returns an empty list
- **Rules:** `get_by_project` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = cost.

**When**
- `result = dao.get_by_project(db, project_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MPC-GP-07 — project_id 0 returns an empty list and raises nothing
- **Rules:** `get_by_project` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = cost.
2. N = unlinked.

**When**
- `result = dao.get_by_project(db, project_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MPC-GP-08 — a project without costs returns an empty list
- **Rules:** `get_by_project` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = cost.

**When**
- `result = dao.get_by_project(db, project_id=PJB.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MPC-GP-09 — an unlinked cost and a cost on another project's component are not returned
- **Rules:** `get_by_project` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. N = unlinked.
2. A = cost.
3. KB = component-only on CB.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### MPC-GP-10 — a cost with both the project and its component is returned once
- **Rules:** `get_by_project` R1a (the "once" part, holds today)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = cost.
2. B = cost, but `project_component_id C1.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == sorted([A.id, B.id])`.

### MPC-GP-11 — project_id None returns this workspace's costs with no project
- **Rules:** `get_by_project` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X0 = unlinked, but `workspace_id W0.id`.
2. K = component-only on C1.
3. N = unlinked.
4. A = cost.
5. X2 = unlinked, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_project(db, project_id=None, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {K.id, N.id}`.
2. returns: `len(result) == 2`.

### MPC-GP-12 — a soft-deleted project's costs are still returned
- **Rules:** `get_by_project` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = cost, but `project_id PJD.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [D.id]`.

### MPC-GP-13 — the query does not read the projects table
- **Rules:** `get_by_project` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = cost.
2. Statement recorder.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"projects." not in sql`.
3. statement: `"FOR UPDATE" not in sql`.

### MPC-GP-14 — limit=0 returns an empty list
- **Rules:** `get_by_project` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = cost.
2. B = cost, but `name "Lift hire"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MPC-GP-15 — limit=1 of three costs returns one of them
- **Rules:** `get_by_project` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = cost.
2. B = cost, but `name "Lift hire"`.
3. C = cost, but `name "Scaffold"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id, C.id}`.

### MPC-GP-16 — skip=2 of three costs returns one of them
- **Rules:** `get_by_project` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = cost.
2. B = cost, but `name "Lift hire"`.
3. C = cost, but `name "Scaffold"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {A.id, B.id, C.id}`.

### MPC-GP-17 — skip past the end returns an empty list
- **Rules:** `get_by_project` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = cost.
2. B = cost, but `name "Lift hire"`.
3. C = cost, but `name "Scaffold"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### MPC-GP-18 — with the default limit 101 costs give 100
- **Rules:** `get_by_project` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(101): db.add(MiscellaneousProjectCost(workspace_id=W1.id, project_id=PJ1.id, name=f"Crane {k}", amount=Decimal("100.00"), created_at=T1)); db.flush()`

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### MPC-GP-19 — limit=1000 gives all 101 costs
- **Rules:** `get_by_project` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(101): db.add(MiscellaneousProjectCost(workspace_id=W1.id, project_id=PJ1.id, name=f"Crane {k}", amount=Decimal("100.00"), created_at=T1)); db.flush()`

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### MPC-GP-20 — a negative limit raises DataError and writes nothing
- **Rules:** `get_by_project` R6, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = cost.

**When**
- `dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201W"`.
2. nothing written: nothing written.

### MPC-GP-21 — a negative skip raises DataError and writes nothing
- **Rules:** `get_by_project` R6, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = cost.

**When**
- `dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201X"`.
2. nothing written: nothing written.

### MPC-GP-22 — the project filter comes before the page: a lower-id cost of another project takes no place
- **Rules:** `get_by_project` R6, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. XA = cost, but `project_id PJA.id`.
2. N = unlinked.
3. A = cost.
4. B = cost, but `name "Lift hire"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `idset(result) == {A.id, B.id}`.

### MPC-GP-23 — the workspace filter comes before the page: W0 and W2 costs take no place
- **Rules:** `get_by_project` R6, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X0 = unlinked, but `workspace_id W0.id`.
2. N1 = unlinked.
3. N2 = unlinked, but `name "Lift hire"`.
4. X2 = unlinked, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_project(db, project_id=None, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `idset(result) == {N1.id, N2.id}`.

### MPC-GP-24 — writes nothing: a pending cost stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_project` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = cost.
2. `A.name = "Edited"` (not flushed).
3. `P = MiscellaneousProjectCost(workspace_id=W1.id, project_id=PJ1.id, name="Pending", amount=Decimal("5.00"), created_at=T1)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `A in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. nothing written: nothing written.

### MPC-GP-25 — stored amounts are returned as exact Decimal values
- **Rules:** `get_by_project` Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = cost, but `amount Decimal("2.125")`.
2. B = cost, but `name "Lift hire"`, `amount Decimal("0.005")`.
3. `db.expire_all()` (so the stored, rounded values are read back, not the inserted ones).

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `{r.id: r.amount for r in result} == {A.id: Decimal("2.13"), B.id: Decimal("0.01")}`.
2. returns: `all(isinstance(r.amount, Decimal) for r in result)`.

### MPC-GP-26 — id ascending, also after the lowest-id cost was edited
- **Rules:** `get_by_project` R4 [BUG-2460]
- **Kind:** bug
- **Expect:** xfail BUG-2460 (non-strict)
- **Revisit:** after launch (owner 2026-11-10)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`; the edited row is read last in heap order)

**Given**
1. A = cost.
2. B = cost, but `name "Lift hire"`.
3. C = cost, but `name "Scaffold"`.
4. `A.name = "Crane two"`, then `db.flush()`.
5. `db.expire_all()`
6. seqscan.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### MPC-GP-27 — pages of one, after an edit, neither repeat nor miss a cost
- **Rules:** `get_by_project` R4, R6 [BUG-2460]
- **Kind:** bug
- **Expect:** xfail BUG-2460 (non-strict)
- **Revisit:** after launch (owner 2026-11-10)
- **Author:** claude
- **Fails today on:** Then 2 (no order before the page; a row can repeat and another be missed)

**Given**
1. A = cost.
2. B = cost, but `name "Lift hire"`.
3. C = cost, but `name "Scaffold"`.
4. `A.name = "Crane two"`, then `db.flush()`.
5. `db.expire_all()`
6. seqscan.

**When**
- `pages = [dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, skip=k, limit=1) for k in range(3)]` (one list comprehension).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [A.id, B.id, C.id]`.

### MPC-GP-28 — the query orders by id ascending
- **Rules:** `get_by_project` R4 [BUG-2460]
- **Kind:** bug
- **Expect:** xfail BUG-2460
- **Revisit:** after launch (owner 2026-11-10)
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = cost.
2. Statement recorder.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"miscellaneous_project_costs.id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### MPC-GP-29 — a cost booked only on a component of the project is returned
- **Rules:** `get_by_project` R1a [BUG-2461]
- **Kind:** bug
- **Expect:** xfail BUG-2461
- **Revisit:** after launch (owner 2026-11-10)
- **Fails today on:** Then 2 (only `project_id` is matched; K is missing)

**Given**
1. A = cost.
2. K = component-only on C1.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `A.id in idset(result)`.
2. returns: `idset(result) == {A.id, K.id}`.
3. returns: `len(result) == 2`.

### MPC-GP-30 — costs of two components and a cost with both are each returned once
- **Rules:** `get_by_project` R1a [BUG-2461]
- **Kind:** bug
- **Expect:** xfail BUG-2461
- **Revisit:** after launch (owner 2026-11-10)
- **Fails today on:** Then 2 (K1 and K2 are missing)

**Given**
1. K1 = component-only on C1.
2. B = cost, but `project_component_id C1.id`.
3. K2 = component-only on C2, but `amount Decimal("300.00")`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `B.id in idset(result)`.
2. returns: `idset(result) == {K1.id, B.id, K2.id}`.
3. returns: `len(result) == 3`.

### MPC-GP-31 — a cost on another project's component is not returned, the project's own component cost is
- **Rules:** `get_by_project` R1a, R2 [BUG-2461]
- **Kind:** bug
- **Expect:** xfail BUG-2461
- **Revisit:** after launch (owner 2026-11-10)
- **Fails today on:** Then 2 (K is missing)

**Given**
1. KA = component-only on CA.
2. K = component-only on C1.
3. KB = component-only on CB.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `KA.id not in idset(result)`.
2. returns: `idset(result) == {K.id}`.

### MPC-GP-32 — a soft-deleted project's component costs are returned
- **Rules:** `get_by_project` R1a, R5 [BUG-2461]
- **Kind:** bug
- **Expect:** xfail BUG-2461
- **Revisit:** after launch (owner 2026-11-10)
- **Fails today on:** Then 2 (KD is missing)

**Given**
1. D = cost, but `project_id PJD.id`.
2. KD = component-only on CDL.

**When**
- `result = dao.get_by_project(db, project_id=PJD.id, workspace_id=W1.id)`.

**Then**
1. returns: `D.id in idset(result)`.
2. returns: `idset(result) == {D.id, KD.id}`.

### MPC-GP-33 — a cost on another workspace's component is not matched through the project
- **Rules:** `get_by_project` R1a ("same workspace") [BUG-2461]
- **Kind:** bug
- **Expect:** xfail BUG-2461
- **Revisit:** after launch (owner 2026-11-10)
- **Fails today on:** Then 2 (K is missing)

**Given**
1. `CY = ProjectComponent(workspace_id=W2.id, project_id=PJ1.id, name="Span")`, then `db.add(CY); db.flush()` (invalid data on purpose).
2. KY = component-only on CY.
3. K = component-only on C1.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `KY.id not in idset(result)`.
2. returns: `idset(result) == {K.id}`.

### MPC-GP-34 — component costs count before the page, a lower-id cost of another project does not
- **Rules:** `get_by_project` R1a, R6 [BUG-2461]
- **Kind:** bug
- **Expect:** xfail BUG-2461
- **Revisit:** after launch (owner 2026-11-10)
- **Fails today on:** Then 2 (K1, K2 are missing, so the page holds A only)

**Given**
1. XA = cost, but `project_id PJA.id`.
2. A = cost.
3. K1 = component-only on C1.
4. K2 = component-only on C2.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id, limit=3)`.

**Then**
1. returns: `XA.id not in idset(result)`.
2. returns: `idset(result) == {A.id, K1.id, K2.id}`.

### MPC-GP-35 — the project's own costs are returned whatever their creation time
- **Rules:** `get_by_project` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = cost, but `created_at T0`.
2. B = cost, but `name "Lift hire"`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id, B.id}`.

### MPC-GP-36 — project_id None does not match through components: a cost with a project and a component is left out
- **Rules:** `get_by_project` R3 (unchanged by the BUG-2461 fix)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = cost, but `project_component_id C1.id`.
2. K = component-only on C2.
3. B = cost, but `project_id PJB.id`, `project_component_id CB.id`.

**When**
- `result = dao.get_by_project(db, project_id=None, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [K.id]`.

## `DAOMiscellaneousProjectCost.get_by_component`

### MPC-GC-01 — returns the component's costs, with or without the project set
- **Rules:** `get_by_component` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = cost.
2. K = component-only on C1, but `amount Decimal("1200.50")`.
3. B = cost, but `project_component_id C1.id`, `name "Lift hire"`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {K.id, B.id}`.
3. returns: `len(result) == 2`.
4. returns: `[r for r in result if r.id == K.id][0].amount == Decimal("1200.50")`.

### MPC-GC-02 — costs of a lower-id and a higher-id component are not returned
- **Rules:** `get_by_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. KA = component-only on CA.
2. K = component-only on C1.
3. K2 = component-only on C2.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [K.id]`.

### MPC-GC-03 — W1 asking for W2's component gets nothing, though W2 has costs on it
- **Rules:** `get_by_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. K = component-only on C1.
2. KX = cost, but `workspace_id W2.id`, `project_id PJX.id`, `project_component_id CX.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=CX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MPC-GC-04 — W1 asking for W0's component gets nothing, though W0 has costs on it
- **Rules:** `get_by_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. K0 = cost, but `workspace_id W0.id`, `project_id None`, `project_component_id C0.id`.
2. K = component-only on C1.

**When**
- `result = dao.get_by_component(db, project_component_id=C0.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MPC-GC-05 — W2 gets its own component's cost
- **Rules:** `get_by_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. K0 = cost, but `workspace_id W0.id`, `project_id None`, `project_component_id C0.id`.
2. K = component-only on C1.
3. KX = cost, but `workspace_id W2.id`, `project_id None`, `project_component_id CX.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=CX.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [KX.id]`.

### MPC-GC-06 — an unknown component id returns an empty list
- **Rules:** `get_by_component` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K = component-only on C1.

**When**
- `result = dao.get_by_component(db, project_component_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MPC-GC-07 — project_component_id 0 returns an empty list and raises nothing
- **Rules:** `get_by_component` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K = component-only on C1.
2. A = cost.

**When**
- `result = dao.get_by_component(db, project_component_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MPC-GC-08 — a component without costs returns an empty list
- **Rules:** `get_by_component` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K = component-only on C1.

**When**
- `result = dao.get_by_component(db, project_component_id=C2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### MPC-GC-09 — project_component_id None returns this workspace's costs with no component
- **Rules:** `get_by_component` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X0 = unlinked, but `workspace_id W0.id`.
2. A = cost.
3. K = component-only on C1.
4. N = unlinked.
5. X2 = unlinked, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=None, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id, N.id}`.
2. returns: `len(result) == 2`.

### MPC-GC-10 — costs of a component of a soft-deleted project are returned
- **Rules:** `get_by_component` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. KD = component-only on CDL.

**When**
- `result = dao.get_by_component(db, project_component_id=CDL.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [KD.id]`.

### MPC-GC-11 — the query reads neither projects nor components
- **Rules:** `get_by_component` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. K = component-only on C1.
2. Statement recorder.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [K.id]`.
2. statement: `"projects." not in sql`.
3. statement: `"project_components." not in sql`.
4. statement: `"FOR UPDATE" not in sql`.

### MPC-GC-12 — limit=0 returns an empty list
- **Rules:** `get_by_component` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = component-only on C1.
2. K2 = component-only on C1, but `name "Lift hire"`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### MPC-GC-13 — limit=1 of three costs returns one of them
- **Rules:** `get_by_component` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = component-only on C1.
2. K2 = component-only on C1, but `name "Lift hire"`.
3. K3 = component-only on C1, but `name "Scaffold"`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {K1.id, K2.id, K3.id}`.

### MPC-GC-14 — skip=2 of three costs returns one of them
- **Rules:** `get_by_component` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = component-only on C1.
2. K2 = component-only on C1, but `name "Lift hire"`.
3. K3 = component-only on C1, but `name "Scaffold"`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in {K1.id, K2.id, K3.id}`.

### MPC-GC-15 — skip past the end returns an empty list
- **Rules:** `get_by_component` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = component-only on C1.
2. K2 = component-only on C1, but `name "Lift hire"`.
3. K3 = component-only on C1, but `name "Scaffold"`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### MPC-GC-16 — with the default limit 101 costs give 100
- **Rules:** `get_by_component` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(101): db.add(MiscellaneousProjectCost(workspace_id=W1.id, project_id=None, project_component_id=C1.id, name=f"Crane {k}", amount=Decimal("100.00"), created_at=T1)); db.flush()`

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### MPC-GC-17 — limit=1000 gives all 101 costs
- **Rules:** `get_by_component` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(101): db.add(MiscellaneousProjectCost(workspace_id=W1.id, project_id=None, project_component_id=C1.id, name=f"Crane {k}", amount=Decimal("100.00"), created_at=T1)); db.flush()`

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### MPC-GC-18 — a negative limit raises DataError and writes nothing
- **Rules:** `get_by_component` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. K = component-only on C1.

**When**
- `dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201W"`.
2. nothing written: nothing written.

### MPC-GC-19 — a negative skip raises DataError and writes nothing
- **Rules:** `get_by_component` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. K = component-only on C1.

**When**
- `dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201X"`.
2. nothing written: nothing written.

### MPC-GC-20 — the component filter comes before the page: a lower-id cost of another component takes no place
- **Rules:** `get_by_component` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. KA = component-only on CA.
2. A = cost.
3. K1 = component-only on C1.
4. K2 = component-only on C1, but `name "Lift hire"`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `idset(result) == {K1.id, K2.id}`.

### MPC-GC-21 — writes nothing: a pending cost stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_component` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. K = component-only on C1.
2. `K.name = "Edited"` (not flushed).
3. `P = MiscellaneousProjectCost(workspace_id=W1.id, project_id=None, project_component_id=C1.id, name="Pending", amount=Decimal("5.00"), created_at=T1)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [K.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `K in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. nothing written: nothing written.

### MPC-GC-22 — id ascending, also after the lowest-id cost was edited
- **Rules:** `get_by_component` R3 [BUG-2460]
- **Kind:** bug
- **Expect:** xfail BUG-2460 (non-strict)
- **Revisit:** after launch (owner 2026-11-10)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`; the edited row is read last in heap order)

**Given**
1. K1 = component-only on C1.
2. K2 = component-only on C1, but `name "Lift hire"`.
3. K3 = component-only on C1, but `name "Scaffold"`.
4. `K1.name = "Crane two"`, then `db.flush()`.
5. `db.expire_all()`
6. seqscan.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [K1.id, K2.id, K3.id]`.

### MPC-GC-23 — pages of one, after an edit, neither repeat nor miss a cost
- **Rules:** `get_by_component` R3, R4 [BUG-2460]
- **Kind:** bug
- **Expect:** xfail BUG-2460 (non-strict)
- **Revisit:** after launch (owner 2026-11-10)
- **Author:** claude
- **Fails today on:** Then 2 (no order before the page; a row can repeat and another be missed)

**Given**
1. K1 = component-only on C1.
2. K2 = component-only on C1, but `name "Lift hire"`.
3. K3 = component-only on C1, but `name "Scaffold"`.
4. `K1.name = "Crane two"`, then `db.flush()`.
5. `db.expire_all()`
6. seqscan.

**When**
- `pages = [dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=k, limit=1) for k in range(3)]` (one list comprehension).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [K1.id, K2.id, K3.id]`.

### MPC-GC-24 — the query orders by id ascending
- **Rules:** `get_by_component` R3 [BUG-2460]
- **Kind:** bug
- **Expect:** xfail BUG-2460
- **Revisit:** after launch (owner 2026-11-10)
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. K = component-only on C1.
2. Statement recorder.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [K.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"miscellaneous_project_costs.id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

## Inherited `BaseDAO` facts for this table

### MPC-INH-01 — the workspace list orders by id ascending
- **Rules:** inherited R1 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 2 (`get_by_workspace` has no `ORDER BY`)

**Given**
1. A = cost.
2. Statement recorder.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"miscellaneous_project_costs.id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.

### MPC-INH-02 — create stores 2.125 as 2.13 (half up, not half even)
- **Rules:** inherited R2 (create rounding), HR-15
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no cost.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "project_id": PJ1.id, "name": "Crane", "amount": Decimal("2.125")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("2.13")`.

### MPC-INH-03 — create stores 0.005 as 0.01
- **Rules:** inherited R2 (create rounding), HR-15
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no cost.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "project_id": PJ1.id, "name": "Crane", "amount": Decimal("0.005")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("0.01")`.

### MPC-INH-04 — create stores 2.124 as 2.12 (control: below the half)
- **Rules:** inherited R2 (create rounding), HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no cost.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "project_id": PJ1.id, "name": "Crane", "amount": Decimal("2.124")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("2.12")`.

### MPC-INH-05 — create stores 1000.005 as 1000.01
- **Rules:** inherited R2 (create rounding), HR-15
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no cost.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "project_component_id": C1.id, "name": "Crane", "amount": Decimal("1000.005")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("1000.01")`.
3. re-read result: `project_id is None`, `project_component_id == C1.id`, `workspace_id == W1.id`.

### MPC-INH-06 — a 12-digit amount is stored exactly
- **Rules:** inherited R2 (integer-digit limit, the side that fits)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no cost.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "project_id": PJ1.id, "name": "Crane", "amount": Decimal("999999999999.99")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("999999999999.99")`.

### MPC-INH-07 — an amount of 10000000000000.00 (14 integer digits) raises DataError 22003 and stores nothing
- **Rules:** inherited R2 (integer-digit limit, the side that fails)
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no cost.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "project_id": PJ1.id, "name": "Crane", "amount": Decimal("10000000000000.00")})`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "22003"`.
2. count: `db.scalar(select(func.count()).select_from(MiscellaneousProjectCost).where(MiscellaneousProjectCost.workspace_id == W1.id)) == 0`.

### MPC-INH-08 — created_at defaults to naive UTC, whatever the database's time zone
- **Rules:** Model facts (`created_at` Python `utcnow()`)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Dhaka.
2. `before = utcnow()`.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "project_id": PJ1.id, "name": "Crane", "amount": Decimal("100.00")}); after = utcnow()` (one step).

**Then**
1. returns: `result.id is not None`.
2. re-read result: `result.created_at.tzinfo is None`.
3. re-read result: `before <= result.created_at <= after`.

### MPC-INH-09 — update from the schema stores amount 0.125 as 0.13 and keeps the other fields
- **Rules:** inherited R2 (update), HR-15
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = cost, but `name "Lift hire"`, `description "Two days"`.

**When**
- `result = dao.update(db, db_obj=B, obj_in=MiscellaneousProjectCostUpdate(amount=0.125))`.

**Then**
1. returns: `result is B`.
2. re-read B: `amount == Decimal("0.13")`.
3. re-read B: `name == "Lift hire"`, `description == "Two days"`, `project_id == PJ1.id`.

### MPC-INH-10 — update from the schema with amount 2.5 stores 2.50
- **Rules:** inherited R2 (update)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = cost.

**When**
- `result = dao.update(db, db_obj=B, obj_in=MiscellaneousProjectCostUpdate(amount=2.5))`.

**Then**
1. returns: `result is B`.
2. re-read B: `amount == Decimal("2.50")`.

### MPC-INH-11 — update from the schema with description None keeps the description
- **Rules:** inherited R2 (update drops `null` fields)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = cost, but `description "Two days"`.

**When**
- `result = dao.update(db, db_obj=B, obj_in=MiscellaneousProjectCostUpdate(description=None))`.

**Then**
1. returns: `result is B`.
2. re-read B: `description == "Two days"`, `amount == Decimal("100.00")`.

### MPC-INH-12 — remove hard-deletes the row
- **Rules:** inherited R2 (remove)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = cost.
2. B = cost, but `name "Lift hire"`.

**When**
- `dao.remove(db, id=A.id)`, then `db.flush()`.

**Then**
1. count: `db.scalar(select(func.count()).select_from(MiscellaneousProjectCost).where(MiscellaneousProjectCost.id == A.id)) == 0`.
2. count: `db.scalar(select(func.count()).select_from(MiscellaneousProjectCost).where(MiscellaneousProjectCost.id == B.id)) == 1`.

### MPC-INH-13 — a 13-digit amount, 9999999999999.99, is stored exactly
- **Rules:** inherited R2 (integer-digit limit, the largest value that fits)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no cost.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "project_id": PJ1.id, "name": "Crane", "amount": Decimal("9999999999999.99")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("9999999999999.99")`.

### MPC-INH-14 — 9999999999999.995 rounds up to 14 integer digits and raises DataError 22003
- **Rules:** inherited R2 (integer-digit limit after rounding), HR-15
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no cost.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "project_id": PJ1.id, "name": "Crane", "amount": Decimal("9999999999999.995")})`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "22003"`.
2. count: `db.scalar(select(func.count()).select_from(MiscellaneousProjectCost).where(MiscellaneousProjectCost.workspace_id == W1.id)) == 0`.

### MPC-INH-15 — create through the schema (dump plus workspace_id) stores the cost, 1000.005 as 1000.01
- **Rules:** inherited R2b, HR-15
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no cost.
2. `S = MiscellaneousProjectCostCreate(project_component_id=C1.id, name="Crane", amount=1000.005)`.

**When**
- `result = dao.create(db, obj_in=dump(S))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("1000.01")`.
3. re-read result: `workspace_id == W1.id`, `project_id is None`, `project_component_id == C1.id`, `name == "Crane"`, `description is None`.

### MPC-INH-16 — create through the schema stores the float 2.675 as 2.68 (half up as typed)
- **Rules:** inherited R2b, HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no cost.
2. `S = MiscellaneousProjectCostCreate(project_id=PJ1.id, name="Crane", amount=2.675)`.

**When**
- `result = dao.create(db, obj_in=dump(S))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("2.68")`.

### MPC-INH-17 — create through the schema stores 0.125 as 0.13
- **Rules:** inherited R2b, HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no cost.
2. `S = MiscellaneousProjectCostCreate(project_id=PJ1.id, name="Crane", description="Two days", amount=0.125)`.

**When**
- `result = dao.create(db, obj_in=dump(S))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("0.13")`.
3. re-read result: `description == "Two days"`, `project_id == PJ1.id`, `project_component_id is None`.

### MPC-INH-18 — create through the schema stores 2.124 as 2.12 (control)
- **Rules:** inherited R2b, HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no cost.
2. `S = MiscellaneousProjectCostCreate(project_id=PJ1.id, name="Crane", amount=2.124)`.

**When**
- `result = dao.create(db, obj_in=dump(S))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("2.12")`.

### MPC-INH-19 — create through the schema stores 9999999999999.99 as is
- **Rules:** inherited R2b, R2 (integer-digit limit)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no cost.
2. `S = MiscellaneousProjectCostCreate(project_id=PJ1.id, name="Crane", amount=9999999999999.99)`.

**When**
- `result = dao.create(db, obj_in=dump(S))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("9999999999999.99")`.

### MPC-INH-20 — the schema object alone has no workspace_id: create fails with IntegrityError 23502 and stores nothing
- **Rules:** inherited R2b
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no cost.
2. `S = MiscellaneousProjectCostCreate(project_id=PJ1.id, name="Crane", amount=100.0)`.

**When**
- `dao.create(db, obj_in=S)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23502"`.
2. raises: `"workspace_id" in str(exc.value.orig)`.
3. count: `db.scalar(select(func.count()).select_from(MiscellaneousProjectCost).where(MiscellaneousProjectCost.project_id == PJ1.id)) == 0`.

## Inherited R2a — negative and zero amounts are stored (OQ-28, revisit after launch)

*The owner answered OQ-28 on 2026-11-10: projects are revisited after launch, and today's behaviour is kept (negative and zero stored, no bug). The IDs keep the `OQ28` code.*

### MPC-OQ28-01 — create stores -1.005 as -1.01 (half away from zero)
- **Rules:** inherited R2a, R2 (create rounding), HR-15
- **Kind:** side-effect
- **Expect:** pass
- **Revisit:** after launch (owner 2026-11-10)

**Given**
1. W1 has no cost.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "project_id": PJ1.id, "name": "Credit", "amount": Decimal("-1.005")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("-1.01")`.

### MPC-OQ28-02 — create stores an amount of 0 as 0.00
- **Rules:** inherited R2a
- **Kind:** boundary
- **Expect:** pass
- **Revisit:** after launch (owner 2026-11-10)

**Given**
1. W1 has no cost.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "project_id": PJ1.id, "name": "Placeholder", "amount": Decimal("0")})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("0.00")`.

### MPC-OQ28-03 — the update schema accepts a negative amount
- **Rules:** inherited R2a (schema, target `schema`)
- **Kind:** boundary
- **Expect:** pass
- **Revisit:** after launch (owner 2026-11-10)

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = MiscellaneousProjectCostUpdate(amount=-5)` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.amount == -5`.

### MPC-OQ28-04 — the update schema accepts an amount of 0
- **Rules:** inherited R2a (schema, target `schema`)
- **Kind:** boundary
- **Expect:** pass
- **Revisit:** after launch (owner 2026-11-10)

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = MiscellaneousProjectCostUpdate(amount=0)` (target `schema`; the DAO is not called).

**Then**
1. returns: `result.amount == 0`.

### MPC-OQ28-05 — update from the schema stores -5 as -5.00
- **Rules:** inherited R2a, R2 (update)
- **Kind:** side-effect
- **Expect:** pass
- **Revisit:** after launch (owner 2026-11-10)

**Given**
1. B = cost.

**When**
- `result = dao.update(db, db_obj=B, obj_in=MiscellaneousProjectCostUpdate(amount=-5))`.

**Then**
1. returns: `result is B`.
2. re-read B: `amount == Decimal("-5.00")`.

### MPC-OQ28-06 — create through the schema stores -1.005 as -1.01
- **Rules:** inherited R2a, R2b, HR-15
- **Kind:** boundary
- **Expect:** pass
- **Revisit:** after launch (owner 2026-11-10)

**Given**
1. W1 has no cost.
2. `S = MiscellaneousProjectCostCreate(project_id=PJ1.id, name="Credit", amount=-1.005)`.

**When**
- `result = dao.create(db, obj_in=dump(S))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("-1.01")`.

### MPC-OQ28-07 — create through the schema stores an amount of 0 as 0.00
- **Rules:** inherited R2a, R2b
- **Kind:** boundary
- **Expect:** pass
- **Revisit:** after launch (owner 2026-11-10)

**Given**
1. W1 has no cost.
2. `S = MiscellaneousProjectCostCreate(project_component_id=C1.id, name="Placeholder", amount=0)`.

**When**
- `result = dao.create(db, obj_in=dump(S))`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `amount == Decimal("0.00")`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 (a) HR-1 name trimmed / not blank | `MiscellaneousProjectCostCreate` / `Update`, service | `"  "` refused (422), names stored trimmed. |
| FU-1 (b) HR-16 cross-workspace / cross-project component link | `MiscellaneousProjectCostService.create_cost` | Another workspace's project or component, or a component of another project, refused as "not found"; nothing written. |
| FU-1 (c) HR-5 workspace-wide list pages before filtering | `MiscellaneousProjectCostService.get_costs` | A full page when more accessible costs exist. |
| FU-1 (d), (e) HR-7 limit bounds; amount decimal input (2 places, 13 integer digits, 422) | endpoint / schema | `limit=0` → 422; `1000.005` and `10^13` refused (BUG-2274 precedent). |
| R2a / OQ-28 amount sign | `MiscellaneousProjectCostCreate` / `Update`, service | Revisit after launch (owner 2026-11-10): today negative and zero are accepted and stored, as the R2a cards here pin. |

## Spec gaps
None. Revision 1's gaps 1–3 are closed by the spec's Gap log (2026-11-10): G1 → MPC-INH-13, INH-14 (INH-07 kept); G2 → MPC-INH-15 … INH-20, OQ28-06, OQ28-07; G3 → GP-11, GP-23 stand, MPC-GP-36 added.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_project` | R1 | MPC-GP-01, GP-03, GP-04, GP-05, GP-06, GP-08, GP-35 |
| `get_by_project` | R1a [BUG-2461] | MPC-GP-29, GP-30, GP-31, GP-32, GP-33, GP-34; pass part GP-10 |
| `get_by_project` | R2 | MPC-GP-02, GP-09, GP-22 |
| `get_by_project` | R3 | MPC-GP-07, GP-11, GP-23, GP-36 |
| `get_by_project` | R4 [BUG-2460] | MPC-GP-26, GP-27 (non-strict), GP-28 (strict) |
| `get_by_project` | R5 | MPC-GP-12, GP-13 |
| `get_by_project` | R6 | MPC-GP-14 … GP-19, GP-22, GP-23 |
| `get_by_project` | Errors (negative skip / limit) | MPC-GP-20, GP-21 |
| `get_by_project` | Side effects none | MPC-GP-24 |
| `get_by_project` | Returns (Decimal amounts) | MPC-GP-01, GP-25 |
| `get_by_component` | R1 | MPC-GC-01 … GC-06, GC-08, GC-20 |
| `get_by_component` | R2 | MPC-GC-07, GC-09 |
| `get_by_component` | R3 [BUG-2460] | MPC-GC-22, GC-23 (non-strict), GC-24 (strict) |
| `get_by_component` | R4 | MPC-GC-10 … GC-17, GC-20 |
| `get_by_component` | Errors | MPC-GC-18, GC-19 |
| `get_by_component` | Side effects none | MPC-GC-21 |
| inherited | R1 [BUG-100] | MPC-INH-01 (strict alarm); order behaviour in `base.cases.md` BASE-GW-05 |
| inherited | R2 create rounding (HR-15) | MPC-INH-02 … INH-05; negative side MPC-OQ28-01 |
| inherited | R2b create through the schema | MPC-INH-15 … INH-20, OQ28-06, OQ28-07 |
| inherited | R2 integer-digit limit (13 fit, 14 fail) | MPC-INH-06, INH-07, INH-13, INH-14, INH-19 |
| inherited | R2 update (drops null, amount) | MPC-INH-09, INH-10, INH-11 |
| inherited | R2 remove (hard delete) | MPC-INH-12; workspace-free id lookup in `base.cases.md` |
| inherited | R2 `get_by_id_and_workspace` | `base.cases.md` (no table-specific fact) |
| Model facts | `created_at` Python `utcnow()` | MPC-INH-08 |
| inherited | R2a (OQ-28, revisit after launch): negative and zero stored | MPC-OQ28-01 … OQ28-07 |
