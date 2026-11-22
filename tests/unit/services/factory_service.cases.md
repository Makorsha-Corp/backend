# Test cases — `app/services/factory_service.py`

> **Spec:** `tests/unit/services/factory_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Counts:** 39 cases · 25 expected-to-pass · 14 expected-to-fail (bugs) · 11 deferred

## Reviewer summary
- **Per callable:** `create_factory` 10 (4 bug) · `get_factory` 7 (3 bug) · `get_factories` 10 (4 bug) · `update_factory` 5 (1 bug) · `delete_factory` 7 (2 bug).
- **Depth:** lighter target (skill step 1a). The service writes no stock, money or order state; apart from the BUG-1331 translation it is a transaction wrapper. TC2, TC4, TC5 once (on create: the commit helper is shared), TC1 and TC3 once per write, TC6 once per read, each passed-on status (404, 400, 409) at least once. Manager rules are not re-tested; each manager bug reached gets one pass-through card, strict or non-strict as in `factory_manager.cases.md` (BUG-893, BUG-898, BUG-899 non-strict).
- **The service's own decision, BUG-1331,** gets two cards: a patched-manager card for the translation itself (exact `detail`, exact blocker list with an `other_workspace` entry, the rollback seen through an uncommitted extra row), and one with a real `draft` batch. A third card (C-10) pins the scope: a `ValueError` out of create is not translated.
- **Notable design choices:**
  - Commit point and uncommitted-extra-row device as `department_service.cases.md`.
  - **Race simulation** C-09 (BUG-895) patches the manager's `_check_name_exists`, as the manager's own cards do.
  - The database-error rows are reached through an unknown `user_id` (`created_by` / `deleted_by` foreign keys, factory manager cards FAC-C-34, D-16), not by patching.
- **Needs a decision:** gap 1 (is a `ValueError` with another text from `delete_factory` translated?). No card rests on it.

## Conventions for this module

**IDs.** `FAS` = `app/services/factory_service.py`. `C` create_factory · `G` get_factory · `L` get_factories · `U` update_factory · `D` delete_factory.

**Actors and fixed values.**
- `svc` = the singleton `factory_service` (`from app.services.factory_service import FactoryService, factory_service`). `db` = the test's real session, always the first argument; every other argument by keyword. `result` = what the When call returns.
- `Factory` (`app.models.factory`), `ProductionLine` (`app.models.production_line`), `ProductionBatch` (`app.models.production_batch`), `FactoryCreate`, `FactoryUpdate` (`app.schemas.factory`), `HTTPException` (`fastapi`), `AppValidationError` = `app.core.exceptions.ValidationError`, `IntegrityError` (`sqlalchemy.exc`), `inspect`, `text` (`sqlalchemy`), `patch` (`unittest.mock`), `date` (`datetime`).
- W1, W2 = two `workspaces` rows; U1, U2 = two `profiles` rows (`make_workspace`, `make_profile`). They exist in every test and need no Given line. U1 is the acting user; U2 created the Given rows.
- MISSING = `999999999`: an id no row of any table has. T0 = `datetime(2020, 1, 2, 3, 4, 5)` (naive).

**Externals.** None is mocked. `deleted_at` comes from the DAO's own clock and is checked as not None.

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A Given line written as code is a step to run exactly as written.
- **fac** = `Factory(workspace_id=W1.id, name="Main Plant", abbreviation="MP", created_by=U2.id)`; `is_active`, `is_deleted` left to their defaults `True`, `False`; `updated_by`, `deleted_at`, `deleted_by` NULL. After "but" the card lists every column that differs.
- **gone** (after "but") = `is_deleted True`, `deleted_at T0`, `deleted_by U2.id`.
- **line of F** = `ProductionLine(workspace_id=W1.id, factory_id=F.id, name="Line A", is_active=True)`.
- **batch on L** = `ProductionBatch(workspace_id=W1.id, production_line_id=L.id, batch_number="BATCH-2026-001", batch_date=date(2026, 2, 1))`; the card gives `status`.
- **commit point** = after the last Given line the test runs `db.commit()` (under the `db` fixture it only releases a savepoint). A Given line marked "(after the commit point)" runs after it and stays uncommitted; it is flushed.
- No card builds two live factories of one workspace whose names, or abbreviations, are equal ignoring case and outer spaces (BUG-895), except C-09's race.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; the values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the row counts of `factories`, `production_lines`, `production_batches` (all workspaces) equal their values at the commit point.
- **ids(x)** = `sorted(r.id for r in x)`. `count:` lines count rows with a fresh query, with the filter stated.
- `loaded:` lines run on the returned object first, before any other Then line touches the session: each column named is not in `inspect(result).unloaded`.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query. What it finds was committed by the call.
- `session:` lines are checks on `db` itself; "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: <Type>`: plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint (the service rolls back itself). Further `raises:` lines assert on `exc.value` after the block, one per line.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When. Checks after the block run with the patches gone.

**Manager patches** (not race simulations; they isolate the service's own translation).
- **delete patch** (D-04): `with patch.object(svc.factory_manager, "delete_factory", side_effect=ValueError("Factory has open production batches", [{"type": "production_batch", "id": 7}, {"type": "other_workspace"}])):` around the When, inside the `raises:` wrap.
- **create patch** (C-10): `with patch.object(svc.factory_manager, "create_factory", side_effect=ValueError("x", [])):` around the When, inside the `raises:` wrap.

**xfail cards.** Write the call and checks as shown, also when a parameter does not exist yet. `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` when the Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Race simulations.** FAS-C-09 only (`create_factory` R2, manager BUG-895): `with patch.object(svc.factory_manager, "_check_name_exists", return_value=False):` around the When, inside the `raises:` wrap.

## `FactoryService.create_factory`

### FAS-C-01 — a new factory is committed and returned re-read
- **Rules:** `create_factory` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no factories.

**When**
- `result = svc.create_factory(db, factory_in=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `created_at`, `name`, `abbreviation`, `workspace_id`, `created_by`.
2. returns: `isinstance(result, Factory)`.
3. returns: `result.id is not None`, `result.created_at is not None`.
4. returns: `result.name == "Main Plant"`, `result.abbreviation == "MP"`, `result.created_by == U1.id`.
5. committed: the row with `id == result.id` exists: `name == "Main Plant"`, `abbreviation == "MP"`, `workspace_id == W1.id`, `created_by == U1.id`, `is_deleted is False`.
6. committed: W1 has exactly 1 `factories` row.

### FAS-C-02 — a duplicate name: the manager's 409 passes unchanged and the session is rolled back
- **Rules:** `create_factory` R2, Errors row 1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = fac.
2. X = fac, but `name "Extra"`, `abbreviation "EX"` (after the commit point).

**When**
- `svc.create_factory(db, factory_in=FactoryCreate(name="Main Plant", abbreviation="NP"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'Main Plant' already exists"`.
4. count: `factories` rows with `name == "Extra"`: exactly 0.
5. count: `factories` rows of W1 with `name == "Main Plant"`: exactly 1.
6. nothing written: nothing written.
7. unchanged: unchanged(A).
8. session: usable.

### FAS-C-03 — a database error at the flush passes unchanged and nothing is saved
- **Rules:** `create_factory` Errors row 2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = fac, but `name "Ops Yard"`, `abbreviation "OY"`.
2. X = fac, but `name "Extra"`, `abbreviation "EX"` (after the commit point).

**When**
- `svc.create_factory(db, factory_in=FactoryCreate(name="North Yard", abbreviation="NY"), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. count: `factories` rows with `name == "North Yard"`: exactly 0.
4. count: `factories` rows with `name == "Extra"`: exactly 0.
5. nothing written: nothing written.
6. session: usable.

### FAS-C-04 — a failing commit is rolled back and re-raised
- **Rules:** `create_factory` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no factories.

**When**
- `svc.create_factory(db, factory_in=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=W1.id, user_id=U1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `factories` rows of W1: exactly 0.
4. nothing written: nothing written.

### FAS-C-05 — a failing re-read after the commit leaves the factory saved
- **Rules:** `create_factory` R3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no factories.

**When**
- `svc.create_factory(db, factory_in=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=W1.id, user_id=U1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: W1 has exactly 1 `factories` row.
3. committed: that row has `name == "Main Plant"`, `abbreviation == "MP"`, `created_by == U1.id`.

### FAS-C-06 — pass-through BUG-896: a padded name is stored trimmed
- **Rules:** `create_factory` R1 [BUG-896]
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 2 (the name is stored with its spaces)

**Given**
1. W1 has no factories.
2. `data = FactoryCreate(name=" Main Plant ", abbreviation="MP")`.

**When**
- `result = svc.create_factory(db, factory_in=data, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the row with `id == result.id` has `name == "Main Plant"`.

### FAS-C-07 — pass-through BUG-894: a name in another case is refused with the submitted name
- **Rules:** `create_factory` R1, R2 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-894
- **Fails today on:** Then 1 (no error is raised: "main plant" is created)

**Given**
1. A = fac.

**When**
- `svc.create_factory(db, factory_in=FactoryCreate(name="main plant", abbreviation="MX"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'main plant' already exists"`.
4. nothing written: nothing written.
5. unchanged: unchanged(A).

### FAS-C-08 — pass-through BUG-893: a duplicate behind 100 deleted rows is still refused
- **Rules:** `create_factory` R1, R2 [BUG-893]
- **Kind:** bug
- **Expect:** xfail BUG-893 (non-strict)
- **Fails today on:** Then 1 (usually no error: the duplicate check reads a capped page of 100 rows, so a second "Late" is created)

**Given**
1. 100 rows, by `add_all`: k = 1 … 100, fac, but `name f"Old {k:03d}"`, `abbreviation f"O{k:03d}"`, gone.
2. L = fac, but `name "Late"`, `abbreviation "LT"`.

**When**
- `svc.create_factory(db, factory_in=FactoryCreate(name="Late", abbreviation="LX"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'Late' already exists"`.
4. count: `factories` rows of W1 with `name == "Late"`: exactly 1.
5. count: `factories` rows of W1: exactly 101.

### FAS-C-09 — pass-through BUG-895: a create that loses the race gets the 409, nothing saved
- **Rules:** `create_factory` R2 [BUG-895]
- **Kind:** bug
- **Expect:** xfail BUG-895
- **Fails today on:** Then 1 (no error is raised: no unique index exists and the second "Main Plant" is saved)

**Given**
1. A = fac.

**When**
- `svc.create_factory(db, factory_in=FactoryCreate(name="Main Plant", abbreviation="MX"), workspace_id=W1.id, user_id=U1.id)`, with the race simulation active.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'Main Plant' already exists"`.
4. count: `factories` rows of W1 with `name == "Main Plant"`: exactly 1.
5. session: usable.

### FAS-C-10 — a ValueError from create is not translated: only delete translates
- **Rules:** `create_factory` R2; `delete_factory` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = fac.
2. X = fac, but `name "Extra"`, `abbreviation "EX"` (after the commit point).

**When**
- `svc.create_factory(db, factory_in=FactoryCreate(name="North Yard", abbreviation="NY"), workspace_id=W1.id, user_id=U1.id)`, with the create patch active, inside `raises: ValueError`.

**Then**
1. raises: `type(exc.value) is ValueError`.
2. raises: `exc.value.args == ("x", [])`.
3. count: `factories` rows with `name == "Extra"`: exactly 0.
4. nothing written: nothing written.

## `FactoryService.get_factory`

### FAS-G-01 — a live factory of the workspace is returned
- **Rules:** `get_factory` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z = fac, but `workspace_id W2.id`, `name "Far Depot"`, `abbreviation "FD"`.
2. A = fac.

**When**
- `result = svc.get_factory(db, factory_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Factory)`.
2. returns: `result.id == A.id`, `result.name == "Main Plant"`, `result.workspace_id == W1.id`.

### FAS-G-02 — another workspace's id: the manager's 404 passes unchanged
- **Rules:** `get_factory` R4, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = fac.
2. Z = fac, but `workspace_id W2.id`, `name "Far Depot"`, `abbreviation "FD"`.

**When**
- `svc.get_factory(db, factory_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {Z.id} not found"`.
4. unchanged: unchanged(Z).

### FAS-G-03 — id 0 gets the 404
- **Rules:** `get_factory` R4, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = fac.

**When**
- `svc.get_factory(db, factory_id=0, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 0 not found"`.

### FAS-G-04 — a soft-deleted factory is hidden by default
- **Rules:** `get_factory` R2 [BUG-897], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-897
- **Fails today on:** Then 1 (no error is raised: the deleted factory is returned)

**Given**
1. A = fac, but `name "Old Plant"`, `abbreviation "OP"`, gone.

**When**
- `svc.get_factory(db, factory_id=A.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {A.id} not found"`.
4. unchanged: unchanged(A).

### FAS-G-05 — include_deleted=True returns a soft-deleted factory
- **Rules:** `get_factory` R3 [BUG-897]
- **Kind:** bug
- **Expect:** xfail BUG-897
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = fac, but `name "Old Plant"`, `abbreviation "OP"`, gone.

**When**
- `result = svc.get_factory(db, factory_id=A.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.is_deleted is True`, `result.name == "Old Plant"`.

### FAS-G-06 — include_deleted=True does not reach another workspace
- **Rules:** `get_factory` R3 [BUG-897], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-897
- **Fails today on:** Then 1 (the call raises TypeError, not HTTPException: the parameter does not exist)

**Given**
1. Z = fac, but `workspace_id W2.id`, `name "Far Depot"`, `abbreviation "FD"`, gone.

**When**
- `svc.get_factory(db, factory_id=Z.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {Z.id} not found"`.

### FAS-G-07 — the read neither commits nor rolls back
- **Rules:** `get_factory` R5; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = fac.
2. B = fac, but `name "North Yard"`, `abbreviation "NY"`.
3. P = fac, but `name "Pending"`, `abbreviation "PD"` (after the commit point).
4. `B.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_factory(db, factory_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. count: `factories` rows with `name == "Pending"`: exactly 1.
5. committed: `factories` rows with `name == "Pending"`: exactly 0.
6. committed: re-read B: `name == "North Yard"`.

## `FactoryService.get_factories`

### FAS-L-01 — the search reaches the manager and only the workspace's matches come back
- **Rules:** `get_factories` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = fac.
2. B = fac, but `name "North Yard"`, `abbreviation "NY"`.
3. C = fac, but `name "Plant Two"`, `abbreviation "PT"`.
4. Z = fac, but `workspace_id W2.id`, `name "Far Plant"`, `abbreviation "FP"`.

**When**
- `result = svc.get_factories(db, workspace_id=W1.id, search="plant")`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id, C.id]`.

### FAS-L-02 — with the defaults 101 live factories give 100
- **Rules:** `get_factories` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows, by `add_all`: k = 1 … 101, fac, but `name f"Plant {k:03d}"`, `abbreviation f"P{k:03d}"`.

**When**
- `result = svc.get_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### FAS-L-03 — limit reaches the manager
- **Rules:** `get_factories` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, in this order: fac, but `name` / `abbreviation` `"Alpha"` / `"AL"`, `"Bravo"` / `"BR"`, `"Charlie"` / `"CH"`, `"Delta"` / `"DL"`, `"Echo"` / `"EC"`.

**When**
- `result = svc.get_factories(db, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `len(result) == 2`.

### FAS-L-04 — skip reaches the manager, limit=1000 takes the rest
- **Rules:** `get_factories` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, in this order: fac, but `name` / `abbreviation` `"Alpha"` / `"AL"`, `"Bravo"` / `"BR"`, `"Charlie"` / `"CH"`, `"Delta"` / `"DL"`, `"Echo"` / `"EC"`.

**When**
- `result = svc.get_factories(db, workspace_id=W1.id, skip=4, limit=1000)`.

**Then**
1. returns: `len(result) == 1`.

### FAS-L-05 — by default a soft-deleted factory is left out
- **Rules:** `get_factories` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = fac.
2. D = fac, but `name "Old Plant"`, `abbreviation "OP"`, gone.

**When**
- `result = svc.get_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [A.id]`.

### FAS-L-06 — include_deleted=True lists soft-deleted factories too
- **Rules:** `get_factories` R2 [BUG-901]
- **Kind:** bug
- **Expect:** xfail BUG-901
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = fac.
2. D = fac, but `name "Old Plant"`, `abbreviation "OP"`, gone.

**When**
- `result = svc.get_factories(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `ids(result) == [A.id, D.id]`.

### FAS-L-07 — the list neither commits nor rolls back
- **Rules:** `get_factories` R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = fac.
2. B = fac, but `workspace_id W2.id`, `name "North Yard"`, `abbreviation "NY"`.
3. P = fac, but `name "Pending"`, `abbreviation "PD"` (after the commit point).
4. `B.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == sorted([A.id, P.id])`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. committed: `factories` rows with `name == "Pending"`: exactly 0.
5. committed: re-read B: `name == "North Yard"`.

### FAS-L-08 — pass-through BUG-898: deleted rows take no place in the page
- **Rules:** `get_factories` R1 [BUG-898]
- **Kind:** bug
- **Expect:** xfail BUG-898 (non-strict)
- **Fails today on:** Then 1 (usually `[]`: the deleted rows fill the page before they are dropped)

**Given**
1. fac, but `name "Old A"`, `abbreviation "OA"`, gone.
2. fac, but `name "Old B"`, `abbreviation "OB"`, gone.
3. fac, but `name "Old C"`, `abbreviation "OC"`, gone.
4. A = fac, but `name "North Yard"`, `abbreviation "NY"`.
5. B = fac.

**When**
- `result = svc.get_factories(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### FAS-L-09 — pass-through BUG-899: names come case-insensitive ascending
- **Rules:** `get_factories` R1 [BUG-899]
- **Kind:** bug
- **Expect:** xfail BUG-899 (non-strict)
- **Fails today on:** Then 2 (no order is asked for; insertion order usually comes back)

**Given**
1. fac, but `name "Delta"`, `abbreviation "DL"`.
2. fac, but `name "alpha"`, `abbreviation "AL"`.
3. fac, but `name "echo"`, `abbreviation "EC"`.
4. fac, but `name "Bravo"`, `abbreviation "BR"`.

**When**
- `result = svc.get_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `[r.name for r in result] == ["alpha", "Bravo", "Delta", "echo"]`.

### FAS-L-10 — pass-through BUG-902: a search of only spaces applies no filter
- **Rules:** `get_factories` R1 [BUG-902]
- **Kind:** bug
- **Expect:** xfail BUG-902
- **Fails today on:** Then 1 (the spaces are searched as text and nothing matches: `[]`)

**Given**
1. A = fac.
2. B = fac, but `name "Camp Site"`, `abbreviation "CS"`.
3. C = fac, but `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = svc.get_factories(db, workspace_id=W1.id, search="   ")`. The text is three spaces.

**Then**
1. returns: `ids(result) == [A.id, B.id, C.id]`.

## `FactoryService.update_factory`

### FAS-U-01 — a rename is committed and returned re-read with updated_at
- **Rules:** `update_factory` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = fac, but `name "Ops Yard"`, `abbreviation "OY"`.

**When**
- `result = svc.update_factory(db, factory_id=A.id, factory_in=FactoryUpdate(name="Operations Yard"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `updated_at`, `updated_by`, `name`.
2. returns: `result.id == A.id`.
3. returns: `result.name == "Operations Yard"`, `result.updated_by == U1.id`, `result.updated_at is not None`.
4. committed: re-read A: `name == "Operations Yard"`, `updated_by == U1.id`, `updated_at is not None`.
5. committed: re-read A: `abbreviation == "OY"`, `created_by == U2.id`, `is_deleted is False`.

### FAS-U-02 — another workspace's id: the 404 passes unchanged and the session is rolled back
- **Rules:** `update_factory` R2, Errors; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = fac.
2. Z = fac, but `workspace_id W2.id`, `name "Far Depot"`, `abbreviation "FD"`.
3. X = fac, but `name "Extra"`, `abbreviation "EX"` (after the commit point).

**When**
- `svc.update_factory(db, factory_id=Z.id, factory_in=FactoryUpdate(name="Hacked"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {Z.id} not found"`.
4. count: `factories` rows with `name == "Extra"`: exactly 0.
5. unchanged: unchanged(Z).
6. nothing written: nothing written.
7. session: usable.

### FAS-U-03 — a deleted factory: the 400 passes unchanged, nothing saved
- **Rules:** `update_factory` R2, Errors
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = fac, but `name "Old Plant"`, `abbreviation "OP"`, gone.

**When**
- `svc.update_factory(db, factory_id=A.id, factory_in=FactoryUpdate(name="Revived"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted factory"`.
4. unchanged: unchanged(A).

### FAS-U-04 — a name taken: the 409 passes unchanged, nothing saved
- **Rules:** `update_factory` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = fac.
2. B = fac, but `name "North Yard"`, `abbreviation "NY"`.

**When**
- `svc.update_factory(db, factory_id=B.id, factory_in=FactoryUpdate(name="Main Plant"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'Main Plant' already exists"`.
4. unchanged: unchanged(B).

### FAS-U-05 — pass-through BUG-900: an empty update does not stamp updated_by
- **Rules:** `update_factory` R1 [BUG-900]
- **Kind:** bug
- **Expect:** xfail BUG-900
- **Fails today on:** Then 2 (`updated_by` becomes U1)

**Given**
1. A = fac, but `updated_by U2.id`.

**When**
- `result = svc.update_factory(db, factory_id=A.id, factory_in=FactoryUpdate(), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. committed: re-read A: `updated_by == U2.id`.

## `FactoryService.delete_factory`

### FAS-D-01 — a soft delete is committed and returned re-read
- **Rules:** `delete_factory` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = fac, but `name "Ops Yard"`, `abbreviation "OY"`.

**When**
- `result = svc.delete_factory(db, factory_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `is_deleted`, `deleted_at`, `deleted_by`.
2. returns: `result.id == A.id`.
3. returns: `result.is_deleted is True`, `result.deleted_by == U1.id`, `result.deleted_at is not None`, `result.is_active is True`.
4. committed: re-read A: `is_deleted is True`, `deleted_by == U1.id`, `deleted_at is not None`.
5. committed: re-read A: `is_active is True`, `name == "Ops Yard"`.

### FAS-D-02 — an already deleted factory: the 400 passes unchanged and the session is rolled back
- **Rules:** `delete_factory` R1, Errors row 2; TC3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = fac, but `name "Old Plant"`, `abbreviation "OP"`, gone.
2. X = fac, but `name "Extra"`, `abbreviation "EX"` (after the commit point).

**When**
- `svc.delete_factory(db, factory_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Factory is already deleted"`.
4. count: `factories` rows with `name == "Extra"`: exactly 0.
5. unchanged: unchanged(A).
6. session: usable.

### FAS-D-03 — an unknown id: the 404 passes unchanged
- **Rules:** `delete_factory` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = fac.

**When**
- `svc.delete_factory(db, factory_id=MISSING, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. unchanged: unchanged(A).

### FAS-D-04 — the manager's open-batch ValueError becomes the 400 with the blockers as given, after a rollback
- **Rules:** `delete_factory` R2 [BUG-1331], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (the `ValueError` escapes unchanged)

**Given**
1. A = fac.
2. X = fac, but `name "Extra"`, `abbreviation "EX"` (after the commit point).

**When**
- `svc.delete_factory(db, factory_id=A.id, workspace_id=W1.id, user_id=U1.id)`, with the delete patch active, inside `raises: AppValidationError`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Factory has open production batches"`.
4. raises: `exc.value.errors == [{"type": "production_batch", "id": 7}, {"type": "other_workspace"}]`.
5. count: `factories` rows with `name == "Extra"`: exactly 0.
6. unchanged: unchanged(A).
7. session: usable.

### FAS-D-05 — end to end: a draft batch blocks the delete with a 400 that lists it
- **Rules:** `delete_factory` R2 [BUG-1331], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (no error is raised: the manager does not look at batches and the factory is deleted)

**Given**
1. A = fac.
2. L1 = line of A.
3. B1 = batch on L1, `status "draft"`.

**When**
- `svc.delete_factory(db, factory_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Factory has open production batches"`.
4. raises: `exc.value.errors == [{"type": "production_batch", "id": B1.id}]`.
5. unchanged: unchanged(A).
6. unchanged: unchanged(B1).
7. nothing written: nothing written.

### FAS-D-06 — a database error at the flush passes unchanged; the factory stays live
- **Rules:** `delete_factory` R1, Errors row 4; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = fac.

**When**
- `svc.delete_factory(db, factory_id=A.id, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. unchanged: unchanged(A).
4. re-read A: `is_deleted is False`, `deleted_by is None`.
5. session: usable.

### FAS-D-07 — a factory with a completed batch is deleted: only open batches block
- **Rules:** `delete_factory` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = fac.
2. L1 = line of A.
3. B1 = batch on L1, `status "completed"`.

**When**
- `result = svc.delete_factory(db, factory_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`, `result.is_deleted is True`.
2. committed: re-read A: `is_deleted is True`, `deleted_by == U1.id`.
3. committed: re-read B1: `status == "completed"`, `production_line_id == L1.id`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| HTTP status and body of a passed-on `HTTPException` | `/factories/` endpoints (integration) | 404 / 400 / 409 bodies as the manager's detail. |
| `delete_factory` R2 [BUG-1331] — the 400 body over HTTP (`detail`, `errors`) | `DELETE /factories/{id}/` with the application's exception handler (integration; `tests/unit/core/exceptions.spec.md`) | 400 with the blocker list, not 500. |
| BUG-1331 manager half — the `ValueError` with blockers (R5a, R5b), every blocking status, closed batches, cross-workspace shapes | `tests/unit/managers/factory_manager.cases.md` FAC-D-18 … D-42 | Full depth there. |
| BUG-897, BUG-901 — the `include_deleted` query parameter; D1 `is_deleted` in `FactoryResponse` | `GET /factories/{id}/`, `GET /factories/` (integration) | Accepted, reaches the service; the flag is in the body. |
| HR-7 — `skip >= 0`, `1 <= limit <= 1000` | `GET /factories/` | Endpoint bounds; called directly, negative values reach the database (`get_factories` Errors). |
| Schema errors answer 422 (BUG-461) | `POST`, `PUT /factories/` | Integration-only. |
| Global `IntegrityError` handler (409) | `app/main.py` handlers | Integration-only. |
| Manager rules (abbreviation 409, R1–R16 edge cases) beyond one pass-through per bug | `tests/unit/managers/factory_manager.cases.md` | Not re-tested here. |
| BUG-899 strict `ORDER BY` recorder | `factory_manager.cases.md` FAC-S-53 | The query is the manager's; L-09 here is the pass-through only. |
| BUG-898 strict statement recorders | `factory_manager.cases.md` FAC-S-52, S-54 | Order-independent alarms live with the query. |
| BUG-1332 | frontend | No backend case. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `delete_factory` R2, R3 | Whether a `ValueError` from the manager's `delete_factory` with **another** text (or a single argument) is translated. R3 says "only a `ValueError` raised by the manager's `delete_factory` is translated" (any such error?), R2 describes only "Factory has open production batches"; `item_service.spec.md` D1 translates known messages only. | No card for an unknown-text `ValueError` out of delete; C-10 covers the other-method side of R3 only. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_factory` | R1 | FAS-C-01 |
| `create_factory` | R1 [BUG-893] | FAS-C-08 |
| `create_factory` | R1 [BUG-894] | FAS-C-07 |
| `create_factory` | R1 [BUG-896] | FAS-C-06 |
| `create_factory` | R2 | FAS-C-02, FAS-C-10 |
| `create_factory` | R2 [BUG-895] | FAS-C-09 |
| `create_factory` | R3 | FAS-C-04, FAS-C-05 |
| `create_factory` | Errors row 1 | FAS-C-02 |
| `create_factory` | Errors row 2 | FAS-C-03 |
| `create_factory` | Returns | FAS-C-01 |
| `get_factory` | R1 | FAS-G-01 |
| `get_factory` | R2 [BUG-897] | FAS-G-04 |
| `get_factory` | R3 [BUG-897] | FAS-G-05, FAS-G-06 |
| `get_factory` | R4 | FAS-G-02, FAS-G-03 |
| `get_factory` | R5 | FAS-G-07 |
| `get_factory` | Errors row 1 | FAS-G-02, FAS-G-03, FAS-G-04, FAS-G-06 |
| `get_factories` | R1 | FAS-L-01, FAS-L-02, FAS-L-03, FAS-L-04 |
| `get_factories` | R1 [BUG-898] | FAS-L-08 |
| `get_factories` | R1 [BUG-899] | FAS-L-09 |
| `get_factories` | R1 [BUG-902] | FAS-L-10 |
| `get_factories` | R2 | FAS-L-05 |
| `get_factories` | R2 [BUG-901] | FAS-L-06 |
| `get_factories` | R3 | FAS-L-07 |
| `update_factory` | R1 | FAS-U-01 |
| `update_factory` | R1 [BUG-900] | FAS-U-05 |
| `update_factory` | R2 | FAS-U-02, FAS-U-03, FAS-U-04 |
| `update_factory` | R3 | FAS-C-04, FAS-C-05 (TC4, TC5 once per service: the commit helper is shared) |
| `update_factory` | Errors | FAS-U-02, FAS-U-03, FAS-U-04; database error as FAS-C-03 |
| `update_factory` | Returns | FAS-U-01 |
| `delete_factory` | R1 | FAS-D-01, FAS-D-02, FAS-D-03, FAS-D-06, FAS-D-07 |
| `delete_factory` | R2 [BUG-1331] | FAS-D-04, FAS-D-05 |
| `delete_factory` | R2 | FAS-D-07 (a closed batch does not reach the translation) |
| `delete_factory` | R3 | FAS-C-10 (other methods); FAS-D-02, FAS-D-06 (other exceptions on delete pass unchanged) |
| `delete_factory` | R4 | FAS-C-04, FAS-C-05 (TC4, TC5 once per service) |
| `delete_factory` | Errors row 1 | FAS-D-03 |
| `delete_factory` | Errors row 2 | FAS-D-02 |
| `delete_factory` | Errors row 3 | FAS-D-04, FAS-D-05 |
| `delete_factory` | Errors row 4 | FAS-D-06 |
| `delete_factory` | Returns | FAS-D-01 |
| Transaction contract | TC1 | FAS-C-01, FAS-U-01, FAS-D-01 |
| Transaction contract | TC2 | FAS-C-01, FAS-U-01, FAS-D-01 |
| Transaction contract | TC3 | FAS-C-02, FAS-C-03, FAS-U-02, FAS-D-02, FAS-D-04, FAS-D-06 |
| Transaction contract | TC4 | FAS-C-04 |
| Transaction contract | TC5 | FAS-C-05 |
| Transaction contract | TC6 | FAS-G-07, FAS-L-07 |
