# Test cases — `app/services/factory_section_service.py`

> **Spec:** `tests/unit/services/factory_section_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Counts:** 51 cases · 27 expected-to-pass · 24 expected-to-fail (bugs) · 10 deferred

## Reviewer summary
- **Per callable:** `create_factory_section` 11 (4 bug) · `get_factory_section` 9 (5 bug) · `get_factory_sections` 15 (8 bug) · `update_factory_section` 11 (5 bug) · `delete_factory_section` 5 (2 bug).
- **Depth:** lighter target (skill step 1a). The service writes no stock, money or order state and adds no check, translation or shaping of its own: it is a transaction wrapper. TC4, TC5 once (on create; the commit helper is shared), TC1, TC2, TC3 once per write, TC6 once per read, every refusal status the spec lists once. Manager rules are not re-tested.
- **Own bugs:** BUG-916 3 (G-04 … G-06), BUG-925 2 (G-07, G-08), BUG-920 1 (L-07).
- **Pass-through bugs (one card each, strictness as `factory_section_manager.cases.md`):** BUG-911 (C-10, non-strict), BUG-912 (C-09), BUG-913 (C-11), BUG-915 (C-08), BUG-903 (L-09, non-strict), BUG-904 (L-10), BUG-917 (L-11, non-strict), BUG-918 (L-12, non-strict), BUG-921 (L-13), BUG-922 (L-14), BUG-924 (L-15), BUG-914 (U-07), BUG-919 (U-08), BUG-923 (U-09), BUG-926 (U-10), BUG-928 (U-11), BUG-908 (D-04), BUG-927 (D-05).
- **Notable design choices:**
  - Commit point and uncommitted-extra-row device as `department_service.cases.md`; here the extra row is a section "Extra" of F2.
  - **Race simulation** C-11 (BUG-913) patches the manager's `_check_name_exists_in_factory`, as the manager's own C-29 does.
  - The database-error row is reached through an unknown `user_id` (`created_by` FK, manager C-30), not by patching.
  - BUG-905, BUG-906, BUG-907 get no card here: BUG-905 is the section DAO's (the manager's cards say BUG-917's cards also pass once it alone is fixed), BUG-906 / BUG-907 are the assignment layer's and go away with BUG-908's fix. Deferred with owners.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `FSS` = `app/services/factory_section_service.py`. `C` create_factory_section · `G` get_factory_section · `L` get_factory_sections · `U` update_factory_section · `D` delete_factory_section.

**Actors and fixed values.**
- `svc` = the singleton `factory_section_service` (`from app.services.factory_section_service import FactorySectionService, factory_section_service`). `db` = the test's real session, always the first argument; every other argument by keyword. `result` = what the When call returns.
- W1, W2 = two `workspaces` rows; U1, U2 = two `profiles` rows (`make_workspace`, `make_profile`). U1 created every Given row, U2 is the acting user.
- Classes: `Factory` (`app.models.factory`), `FactorySection` (`app.models.factory_section`), `Machine` (`app.models.machine`), `MachineSectionAssignment` (`app.models.machine_section_assignment`). `FactorySectionCreate`, `FactorySectionUpdate` (`app.schemas.factory_section`). `HTTPException` (`fastapi`); `IntegrityError` (`sqlalchemy.exc`); `inspect`, `text`, `select` (`sqlalchemy`); `patch` (`unittest.mock`).
- MISSING = `999999999`: an id no row of any table has. T0 = `datetime(2025, 12, 1, 8, 0, 0)` (naive).

**Externals.** None is mocked. `deleted_at` comes from the DAO's own clock and is checked as not None.

**Standing rows.** In every test, in this order, no Given line needed: W1, W2, U1, U2 and five `Factory(workspace_id=…, name=…, abbreviation=…, created_by=U1.id)` rows, `is_active True`, `is_deleted False` unless stated:
- F1 `"Main Plant"` / `"MP"`, W1. F2 `"North Yard"` / `"NY"`, W1. F9 `"Far Depot"` / `"FR"`, `workspace_id W2.id`. FD `"Old Plant"` / `"OP"`, W1, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. FI `"Idle Plant"` / `"IP"`, W1, `is_active False`.

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written, so ids rise in that order. A Given line written as code is a step to run exactly as written.
- **section** = `FactorySection(workspace_id=W1.id, factory_id=F1.id, name=…, created_by=U1.id)`; `is_active True`, `is_deleted False`, `updated_by`, `updated_at`, `deleted_at`, `deleted_by` NULL. The card gives `name`; after "but" it lists every other column that differs. A section of W2 is always "but `factory_id F9.id`, `workspace_id W2.id`".
- **gone** (after "but") = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
- **machine of F** = `Machine(workspace_id=F.workspace_id, factory_id=F.id, name=…, is_active=True, is_deleted=False)`. **assignment of MA to S** = `MachineSectionAssignment(workspace_id=MA.workspace_id, machine_id=MA.id, factory_section_id=S.id, created_by=U1.id)`.
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). A Given line marked "(after the commit point)" runs after it, is flushed, and stays uncommitted.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the row counts of `factory_sections`, `factories`, `machines`, `machine_section_assignments` (all workspaces) equal their values at the commit point.
- **ids(x)** = `sorted(r.id for r in x)`. **names(x)** = `[r.name for r in x]` (order kept). **rows_of_section(S)** = a fresh SELECT of `machine_section_assignments` with `factory_section_id == S.id`. `count:` lines count with a fresh query, with the filter stated.
- `loaded:` lines run on the returned object first, before any other Then line touches the session: each column named is not in `inspect(result).unloaded`.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `session:` lines check `db` itself; "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: <Type>`: plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint (the service rolls back itself). Further `raises:` lines assert on `exc.value` after the block, one per line.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When. Checks after the block run with the patches gone.

**xfail cards.** Write the call and checks as shown, also when a parameter does not exist yet. `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` when the Expect line says `(non-strict)`. A non-strict card's assertion is never weakened.

**Race simulations.** FSS-C-11 only (`create_factory_section` R1, R2; manager BUG-913): `with patch.object(svc.factory_section_manager, "_check_name_exists_in_factory", return_value=False):` around the When, inside the `raises:` wrap.

## `FactorySectionService.create_factory_section`

### FSS-C-01 — a new section is committed and returned re-read
- **Rules:** `create_factory_section` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `result = svc.create_factory_section(db, section_in=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `created_at`, `name`, `factory_id`, `created_by`.
2. returns: `isinstance(result, FactorySection)`.
3. returns: `result.id is not None`, `result.created_at is not None`.
4. returns: `result.name == "Paint"`, `result.factory_id == F1.id`, `result.created_by == U2.id`.
5. committed: the row with `id == result.id` exists: `name == "Paint"`, `factory_id == F1.id`, `workspace_id == W1.id`, `is_deleted is False`.
6. committed: `factory_sections` has exactly 1 row.

### FSS-C-02 — an unknown factory: the 404 passes unchanged and the session is rolled back
- **Rules:** `create_factory_section` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = section, `name "Cutting"`.
2. X = section, `name "Extra"`, but `factory_id F2.id` (after the commit point).

**When**
- `svc.create_factory_section(db, section_in=FactorySectionCreate(name="Paint", factory_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. count: `factory_sections` rows with `name == "Extra"`: exactly 0.
5. nothing written: nothing written.
6. unchanged: unchanged(A).
7. session: usable.

### FSS-C-03 — a soft-deleted factory: the 400 passes unchanged, nothing saved
- **Rules:** `create_factory_section` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `svc.create_factory_section(db, section_in=FactorySectionCreate(name="Paint", factory_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create section for deleted factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(FD).

### FSS-C-04 — a name taken in the factory: the 409 passes unchanged, nothing saved
- **Rules:** `create_factory_section` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = section, `name "Paint"`.

**When**
- `svc.create_factory_section(db, section_in=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Paint' already exists in this factory"`.
4. count: `factory_sections` rows with `name == "Paint"`: exactly 1.
5. unchanged: unchanged(A).
6. nothing written: nothing written.

### FSS-C-05 — a database error at the flush passes unchanged and nothing is saved
- **Rules:** `create_factory_section` Errors (database errors unchanged); TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = section, `name "Cutting"`.
2. X = section, `name "Extra"`, but `factory_id F2.id` (after the commit point).

**When**
- `svc.create_factory_section(db, section_in=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. count: `factory_sections` rows with `name == "Paint"`: exactly 0.
4. count: `factory_sections` rows with `name == "Extra"`: exactly 0.
5. nothing written: nothing written.
6. session: usable.

### FSS-C-06 — a failing commit is rolled back and re-raised
- **Rules:** `create_factory_section` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `svc.create_factory_section(db, section_in=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `factory_sections` rows: exactly 0.
4. nothing written: nothing written.

### FSS-C-07 — a failing re-read after the commit leaves the section saved
- **Rules:** `create_factory_section` R3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `svc.create_factory_section(db, section_in=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `factory_sections` has exactly 1 row.
3. committed: that row has `name == "Paint"`, `created_by == U2.id`.

### FSS-C-08 — pass-through BUG-915: a padded name is stored trimmed
- **Rules:** `create_factory_section` R1 [BUG-915]
- **Kind:** bug
- **Expect:** xfail BUG-915
- **Fails today on:** Then 2 (the name is stored with its spaces)

**Given**
1. No sections exist.
2. `data = FactorySectionCreate(name="  Paint ", factory_id=F1.id)` (two spaces before, one after).

**When**
- `result = svc.create_factory_section(db, section_in=data, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the row with `id == result.id` has `name == "Paint"`.

### FSS-C-09 — pass-through BUG-912: a name in another case is refused with the submitted name
- **Rules:** `create_factory_section` R1, R2 [BUG-912]
- **Kind:** bug
- **Expect:** xfail BUG-912
- **Fails today on:** Then 1 (no error is raised: "paint" is created)

**Given**
1. A = section, `name "Paint"`.

**When**
- `svc.create_factory_section(db, section_in=FactorySectionCreate(name="paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'paint' already exists in this factory"`.
4. count: `factory_sections` has exactly 1 row.
5. unchanged: unchanged(A).

### FSS-C-10 — pass-through BUG-911: a duplicate that is the 101st live section is still refused
- **Rules:** `create_factory_section` R1, R2 [BUG-911]
- **Kind:** bug
- **Expect:** xfail BUG-911 (non-strict)
- **Fails today on:** Then 1 (usually no error: the duplicate check reads 100 sections, so a second "Late" is created)

**Given**
1. 100 rows, by `add_all`: k = 1 … 100, section, `name f"Bay {k:03d}"`.
2. L = section, `name "Late"`.

**When**
- `svc.create_factory_section(db, section_in=FactorySectionCreate(name="Late", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Late' already exists in this factory"`.
4. count: `factory_sections` rows with `name == "Late"`: exactly 1.
5. count: `factory_sections` has exactly 101 rows.

### FSS-C-11 — pass-through BUG-913: a create that loses the race gets the 409, nothing saved
- **Rules:** `create_factory_section` R1, R2 [BUG-913]
- **Kind:** bug
- **Expect:** xfail BUG-913
- **Fails today on:** Then 1 (no error is raised: no unique index exists and the second "Paint" is saved)

**Given**
1. A = section, `name "Paint"`.

**When**
- `svc.create_factory_section(db, section_in=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`, with the race simulation active.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Paint' already exists in this factory"`.
4. count: `factory_sections` rows with `name == "Paint"`: exactly 1.
5. unchanged: unchanged(A).
6. session: usable.

## `FactorySectionService.get_factory_section`

### FSS-G-01 — a live section of the workspace in a live factory is returned
- **Rules:** `get_factory_section` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.
2. A = section, `name "Paint"`.

**When**
- `result = svc.get_factory_section(db, section_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, FactorySection)`.
2. returns: `result.id == A.id`, `result.name == "Paint"`, `result.factory_id == F1.id`.

### FSS-G-02 — another workspace's id: the 404 passes unchanged
- **Rules:** `get_factory_section` R5, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = section, `name "Paint"`.
2. Z = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.

**When**
- `svc.get_factory_section(db, section_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory section with ID {Z.id} not found"`.
4. unchanged: unchanged(Z).

### FSS-G-03 — an unknown id: the 404 passes unchanged
- **Rules:** `get_factory_section` R5, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = section, `name "Paint"`.

**When**
- `svc.get_factory_section(db, section_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory section with ID 999999999 not found"`.

### FSS-G-04 — a soft-deleted section is hidden by default
- **Rules:** `get_factory_section` R2 [BUG-916], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-916
- **Fails today on:** Then 1 (no error is raised: the deleted section is returned)

**Given**
1. A = section, `name "Old Line"`, but gone.

**When**
- `svc.get_factory_section(db, section_id=A.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory section with ID {A.id} not found"`.
4. unchanged: unchanged(A).

### FSS-G-05 — include_deleted=True returns a soft-deleted section
- **Rules:** `get_factory_section` R3 [BUG-916]
- **Kind:** bug
- **Expect:** xfail BUG-916
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = section, `name "Old Line"`, but gone.

**When**
- `result = svc.get_factory_section(db, section_id=A.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.is_deleted is True`, `result.name == "Old Line"`.

### FSS-G-06 — include_deleted=True does not reach another workspace
- **Rules:** `get_factory_section` R3 [BUG-916], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-916
- **Fails today on:** Then 1 (the call raises TypeError, not HTTPException: the parameter does not exist)

**Given**
1. Z = section, `name "Old Bin"`, but `factory_id F9.id`, `workspace_id W2.id`, gone.

**When**
- `svc.get_factory_section(db, section_id=Z.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory section with ID {Z.id} not found"`.

### FSS-G-07 — a live section of a soft-deleted factory is hidden by default
- **Rules:** `get_factory_section` R4 [BUG-925], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-925
- **Fails today on:** Then 1 (no error is raised: the factory is not looked at and the section is returned)

**Given**
1. H = section, `name "Paint"`, but `factory_id FD.id`.

**When**
- `svc.get_factory_section(db, section_id=H.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory section with ID {H.id} not found"`.
4. unchanged: unchanged(H).

### FSS-G-08 — include_deleted=True returns a live section of a soft-deleted factory
- **Rules:** `get_factory_section` R4 [BUG-925]
- **Kind:** bug
- **Expect:** xfail BUG-925
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. H = section, `name "Paint"`, but `factory_id FD.id`.

**When**
- `result = svc.get_factory_section(db, section_id=H.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == H.id`.
2. returns: `result.factory_id == FD.id`, `result.is_deleted is False`.

### FSS-G-09 — the read neither commits nor rolls back
- **Rules:** `get_factory_section` R5; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = section, `name "Paint"`.
2. B = section, `name "Cutting"`.
3. P = section, `name "Pending"`, but `factory_id F2.id` (after the commit point).
4. `B.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_factory_section(db, section_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. count: `factory_sections` rows with `name == "Pending"`: exactly 1.
5. committed: `factory_sections` rows with `name == "Pending"`: exactly 0.
6. committed: re-read B: `name == "Cutting"`.

## `FactorySectionService.get_factory_sections`

### FSS-L-01 — factory_id reaches the manager
- **Rules:** `get_factory_sections` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = section, `name "Paint"`.
2. B = section, `name "Cutting"`, but `factory_id F2.id`.
3. Z = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.

**When**
- `result = svc.get_factory_sections(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id]`.

### FSS-L-02 — the search reaches the manager and only the workspace's matches come back
- **Rules:** `get_factory_sections` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = section, `name "Paint"`.
2. B = section, `name "Cutting"`.
3. C = section, `name "Main Hall"`, but `factory_id F2.id`.
4. Z = section, `name "Drain Bay"`, but `factory_id F9.id`, `workspace_id W2.id`.

**When**
- `result = svc.get_factory_sections(db, workspace_id=W1.id, search="ain")`.

**Then**
1. returns: `ids(result) == [A.id, C.id]`.

### FSS-L-03 — with the defaults 101 live sections give 100
- **Rules:** `get_factory_sections` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows, by `add_all`: k = 1 … 101, section, `name f"Bay {k:03d}"`.

**When**
- `result = svc.get_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### FSS-L-04 — limit reaches the manager
- **Rules:** `get_factory_sections` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, in this order: section, `name` `"Alpha"`, `"Bravo"`, `"Charlie"`, `"Delta"`, `"Echo"`.

**When**
- `result = svc.get_factory_sections(db, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `len(result) == 2`.

### FSS-L-05 — skip reaches the manager, limit=1000 takes the rest
- **Rules:** `get_factory_sections` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, in this order: section, `name` `"Alpha"`, `"Bravo"`, `"Charlie"`, `"Delta"`, `"Echo"`.

**When**
- `result = svc.get_factory_sections(db, workspace_id=W1.id, skip=4, limit=1000)`.

**Then**
1. returns: `len(result) == 1`.

### FSS-L-06 — by default a soft-deleted section is left out
- **Rules:** `get_factory_sections` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = section, `name "Paint"`.
2. D = section, `name "Old Line"`, but gone.

**When**
- `result = svc.get_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [A.id]`.

### FSS-L-07 — include_deleted=True lists soft-deleted sections too
- **Rules:** `get_factory_sections` R2 [BUG-920]
- **Kind:** bug
- **Expect:** xfail BUG-920
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = section, `name "Paint"`.
2. D = section, `name "Old Line"`, but gone.

**When**
- `result = svc.get_factory_sections(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `ids(result) == [A.id, D.id]`.

### FSS-L-08 — the list neither commits nor rolls back
- **Rules:** `get_factory_sections` R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = section, `name "Paint"`.
2. B = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.
3. P = section, `name "Pending"` (after the commit point).
4. `B.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == sorted([A.id, P.id])`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. committed: `factory_sections` rows with `name == "Pending"`: exactly 0.
5. committed: re-read B: `name == "Packing"`.

### FSS-L-09 — pass-through BUG-903: with a factory, names come case-insensitive ascending
- **Rules:** `get_factory_sections` R1 [BUG-903]
- **Kind:** bug
- **Expect:** xfail BUG-903 (non-strict)
- **Fails today on:** Then 2 (no order is asked for; insertion order usually comes back)

**Given**
1. section, `name "Delta"`.
2. section, `name "alpha"`.
3. section, `name "echo"`.
4. section, `name "Bravo"`.
5. section, `name "charlie"`.

**When**
- `result = svc.get_factory_sections(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: `names(result) == ["alpha", "Bravo", "charlie", "Delta", "echo"]`.

### FSS-L-10 — pass-through BUG-904: filtered by a soft-deleted factory, its live section is hidden
- **Rules:** `get_factory_sections` R1 [BUG-904]
- **Kind:** bug
- **Expect:** xfail BUG-904
- **Fails today on:** Then 1 (the factory is not looked at; H is returned)

**Given**
1. H = section, `name "Cutting"`, but `factory_id FD.id`.

**When**
- `result = svc.get_factory_sections(db, workspace_id=W1.id, factory_id=FD.id)`.

**Then**
1. returns: `result == []`.
2. unchanged: unchanged(H).

### FSS-L-11 — pass-through BUG-917: a deleted section takes no place in the page
- **Rules:** `get_factory_sections` R1 [BUG-917]
- **Kind:** bug
- **Expect:** xfail BUG-917 (non-strict)
- **Fails today on:** Then 1 (usually one section: the deleted row fills a place of the page before it is dropped)

**Given**
1. D = section, `name "Old Line"`, but gone.
2. A = section, `name "Paint"`.
3. B = section, `name "Welding"`, but `factory_id F2.id`.

**When**
- `result = svc.get_factory_sections(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### FSS-L-12 — pass-through BUG-918: without a factory, names come case-insensitive ascending
- **Rules:** `get_factory_sections` R1 [BUG-918]
- **Kind:** bug
- **Expect:** xfail BUG-918 (non-strict)
- **Fails today on:** Then 2 (no order is asked for; insertion order usually comes back)

**Given**
1. section, `name "Delta"`.
2. section, `name "alpha"`, but `factory_id F2.id`.
3. section, `name "echo"`.
4. section, `name "Bravo"`, but `factory_id F2.id`.
5. section, `name "charlie"`.

**When**
- `result = svc.get_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: `names(result) == ["alpha", "Bravo", "charlie", "Delta", "echo"]`.

### FSS-L-13 — pass-through BUG-921: a search of only spaces applies no filter
- **Rules:** `get_factory_sections` R1 [BUG-921]
- **Kind:** bug
- **Expect:** xfail BUG-921
- **Fails today on:** Then 1 (the text is used as typed; no name contains three spaces, so the list is empty)

**Given**
1. A = section, `name "Main Hall"`.
2. B = section, `name "Paint"`.

**When**
- `result = svc.get_factory_sections(db, workspace_id=W1.id, search="   ")` (three spaces).

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### FSS-L-14 — pass-through BUG-922: factory_id 0 filters like any id
- **Rules:** `get_factory_sections` R1 [BUG-922]
- **Kind:** bug
- **Expect:** xfail BUG-922
- **Fails today on:** Then 1 (0 counts as no filter: both sections come back)

**Given**
1. A = section, `name "Paint"`.
2. B = section, `name "Cutting"`, but `factory_id F2.id`.

**When**
- `result = svc.get_factory_sections(db, workspace_id=W1.id, factory_id=0)`.

**Then**
1. returns: `result == []`.

### FSS-L-15 — pass-through BUG-924: without a factory, a section of a soft-deleted factory is hidden
- **Rules:** `get_factory_sections` R1 [BUG-924]
- **Kind:** bug
- **Expect:** xfail BUG-924
- **Fails today on:** Then 2 (the factory is not looked at; H is listed too)

**Given**
1. A = section, `name "Paint"`.
2. H = section, `name "Cutting"`, but `factory_id FD.id`.

**When**
- `result = svc.get_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `A.id in [r.id for r in result]`.
2. returns: `ids(result) == [A.id]`.

## `FactorySectionService.update_factory_section`

### FSS-U-01 — a rename is committed and returned re-read with updated_at
- **Rules:** `update_factory_section` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = section, `name "Paint"`.

**When**
- `result = svc.update_factory_section(db, section_id=A.id, section_in=FactorySectionUpdate(name="Spray"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `updated_at`, `updated_by`, `name`.
2. returns: `result.id == A.id`.
3. returns: `result.name == "Spray"`, `result.updated_by == U2.id`, `result.updated_at is not None`.
4. committed: re-read A: `name == "Spray"`, `updated_by == U2.id`, `updated_at is not None`.
5. committed: re-read A: `factory_id == F1.id`, `created_by == U1.id`, `is_deleted is False`.

### FSS-U-02 — another workspace's id: the 404 passes unchanged and the session is rolled back
- **Rules:** `update_factory_section` R2; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = section, `name "Paint"`.
2. Z = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.
3. X = section, `name "Extra"`, but `factory_id F2.id` (after the commit point).

**When**
- `svc.update_factory_section(db, section_id=Z.id, section_in=FactorySectionUpdate(name="Hacked"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory section with ID {Z.id} not found"`.
4. count: `factory_sections` rows with `name == "Extra"`: exactly 0.
5. unchanged: unchanged(Z).
6. nothing written: nothing written.
7. session: usable.

### FSS-U-03 — a deleted section: the 400 passes unchanged, nothing saved
- **Rules:** `update_factory_section` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = section, `name "Old Line"`, but gone.

**When**
- `svc.update_factory_section(db, section_id=A.id, section_in=FactorySectionUpdate(name="Spray"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted factory section"`.
4. unchanged: unchanged(A).

### FSS-U-04 — a move to an unknown factory: the 404 passes unchanged, nothing saved
- **Rules:** `update_factory_section` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = section, `name "Paint"`.

**When**
- `svc.update_factory_section(db, section_id=A.id, section_in=FactorySectionUpdate(factory_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. unchanged: unchanged(A).

### FSS-U-05 — a move to a soft-deleted factory: the 400 passes unchanged, nothing saved
- **Rules:** `update_factory_section` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = section, `name "Paint"`.

**When**
- `svc.update_factory_section(db, section_id=A.id, section_in=FactorySectionUpdate(factory_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot move section to deleted factory"`.
4. unchanged: unchanged(A).

### FSS-U-06 — a name taken in the factory: the 409 passes unchanged, nothing saved
- **Rules:** `update_factory_section` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = section, `name "Paint"`.
2. B = section, `name "Cutting"`.

**When**
- `svc.update_factory_section(db, section_id=B.id, section_in=FactorySectionUpdate(name="Paint"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Paint' already exists in this factory"`.
4. unchanged: unchanged(B).

### FSS-U-07 — pass-through BUG-914: a plain move into a factory where the name is taken is refused
- **Rules:** `update_factory_section` R1, R2 [BUG-914]
- **Kind:** bug
- **Expect:** xfail BUG-914
- **Fails today on:** Then 1 (no error is raised: the move is saved and F2 has two live "Paint")

**Given**
1. A = section, `name "Paint"`.
2. B = section, `name "Paint"`, but `factory_id F2.id`.

**When**
- `svc.update_factory_section(db, section_id=A.id, section_in=FactorySectionUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Paint' already exists in this factory"`.
4. re-read A: `factory_id == F1.id`.
5. unchanged: unchanged(B).

### FSS-U-08 — pass-through BUG-919: an empty update does not stamp updated_by
- **Rules:** `update_factory_section` R1 [BUG-919]
- **Kind:** bug
- **Expect:** xfail BUG-919
- **Fails today on:** Then 2 (`updated_by` becomes U2)

**Given**
1. A = section, `name "Paint"`.

**When**
- `result = svc.update_factory_section(db, section_id=A.id, section_in=FactorySectionUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == A.id`.
2. committed: re-read A: `updated_by is None`.

### FSS-U-09 — pass-through BUG-923: factory_id 0 gets the 404
- **Rules:** `update_factory_section` R2 [BUG-923]
- **Kind:** bug
- **Expect:** xfail BUG-923
- **Fails today on:** Then 1 (the call raises IntegrityError: 0 skips the factory check and the flush fails on the foreign key)

**Given**
1. A = section, `name "Paint"`.

**When**
- `svc.update_factory_section(db, section_id=A.id, section_in=FactorySectionUpdate(factory_id=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 0 not found"`.
4. unchanged: unchanged(A).

### FSS-U-10 — pass-through BUG-926: a section of a soft-deleted factory cannot be renamed
- **Rules:** `update_factory_section` R1, R2 [BUG-926]
- **Kind:** bug
- **Expect:** xfail BUG-926
- **Fails today on:** Then 1 (no error is raised: the rename is saved)

**Given**
1. H = section, `name "Paint"`, but `factory_id FD.id`.

**When**
- `svc.update_factory_section(db, section_id=H.id, section_in=FactorySectionUpdate(name="Spray"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted factory section"`.
4. unchanged: unchanged(H).

### FSS-U-11 — pass-through BUG-928: a section with an assigned machine cannot be moved
- **Rules:** `update_factory_section` R2 [BUG-928]
- **Kind:** bug
- **Expect:** xfail BUG-928
- **Fails today on:** Then 1 (no error is raised: the move is saved and the machine of F1 is linked to a section of F2)

**Given**
1. A = section, `name "Paint"`.
2. MA = machine of F1, `name "Lathe"`.
3. AS = assignment of MA to A.

**When**
- `svc.update_factory_section(db, section_id=A.id, section_in=FactorySectionUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot move a section that has machines assigned"`.
4. re-read A: `factory_id == F1.id`.
5. unchanged: unchanged(AS).

## `FactorySectionService.delete_factory_section`

### FSS-D-01 — a soft delete is committed and returned re-read
- **Rules:** `delete_factory_section` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = section, `name "Paint"`.

**When**
- `result = svc.delete_factory_section(db, section_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `is_deleted`, `deleted_at`, `deleted_by`.
2. returns: `result.id == A.id`.
3. returns: `result.is_deleted is True`, `result.deleted_by == U2.id`, `result.deleted_at is not None`.
4. committed: re-read A: `is_deleted is True`, `deleted_by == U2.id`, `deleted_at is not None`.
5. committed: re-read A: `name == "Paint"`, `factory_id == F1.id`.

### FSS-D-02 — an already deleted section: the 400 passes unchanged and the session is rolled back
- **Rules:** `delete_factory_section` R2; TC3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = section, `name "Old Line"`, but gone.
2. X = section, `name "Extra"`, but `factory_id F2.id` (after the commit point).

**When**
- `svc.delete_factory_section(db, section_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Factory section is already deleted"`.
4. count: `factory_sections` rows with `name == "Extra"`: exactly 0.
5. unchanged: unchanged(A).
6. session: usable.

### FSS-D-03 — an unknown id: the 404 passes unchanged
- **Rules:** `delete_factory_section` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = section, `name "Paint"`.

**When**
- `svc.delete_factory_section(db, section_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory section with ID 999999999 not found"`.
4. unchanged: unchanged(A).

### FSS-D-04 — pass-through BUG-908: the machine assignments of the deleted section are kept
- **Rules:** `delete_factory_section` R1 [BUG-908]
- **Kind:** bug
- **Expect:** xfail BUG-908
- **Fails today on:** Then 3 (every assignment row of the section is deleted and the delete committed)

**Given**
1. A = section, `name "Paint"`.
2. MA1 = machine of F1, `name "Lathe"`.
3. MA2 = machine of F1, `name "Press"`.
4. AS1 = assignment of MA1 to A.
5. AS2 = assignment of MA2 to A.

**When**
- `result = svc.delete_factory_section(db, section_id=A.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == A.id`.
2. committed: re-read A: `is_deleted is True`.
3. committed: rows_of_section(A) has exactly 2 rows.
4. committed: unchanged(AS1).

### FSS-D-05 — pass-through BUG-927: a section of a soft-deleted factory cannot be deleted
- **Rules:** `delete_factory_section` R2 [BUG-927]
- **Kind:** bug
- **Expect:** xfail BUG-927
- **Fails today on:** Then 1 (no error is raised: the section is deleted)

**Given**
1. H = section, `name "Paint"`, but `factory_id FD.id`.

**When**
- `svc.delete_factory_section(db, section_id=H.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot delete a section of a deleted factory"`.
4. unchanged: unchanged(H).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| HTTP status and body of a passed-on `HTTPException` | `/factory-sections/` endpoints (integration) | 404 / 400 / 409 bodies as the manager's detail. |
| BUG-916, BUG-920, BUG-925 — the `include_deleted` query parameter; D1 `is_deleted` in `FactorySectionResponse` | `GET /factory-sections/{id}/`, `GET /factory-sections/` (integration) | The parameter is accepted and reaches the service; the response carries `is_deleted`. |
| HR-7 — `skip >= 0`, `1 <= limit <= 1000` | `GET /factory-sections/` | Endpoint bounds; called directly, negative values reach the database (`DataError`, spec `get_factory_sections` Errors). |
| BUG-461 — schema errors answer 422 (400 today); BUG-915 blank-name schema cards | `POST`, `PUT /factory-sections/` (integration); `factory_section_manager.cases.md` FSM-C-18 … C-20, U-39, U-40 | Integration-only / schema cards live in the manager file. |
| Global `IntegrityError` handler (409) | `app/main.py` handlers | Integration-only. |
| BUG-905 — the section DAO's by-factory page includes deleted sections | `tests/unit/dao/factory_section.cases.md` | The DAO's bug; through the service it shows only inside BUG-917's list cards. |
| BUG-906, BUG-907 — no order / 10 000 cap of the assignment read used by the delete | `tests/unit/dao/machine_section_assignment.cases.md`, `tests/unit/managers/machine_section_assignment_manager.cases.md` | Assignment layer; the call goes away with the BUG-908 fix (manager spec, standing note 3). |
| Strict statement recorders BUG-911 (CN-17), BUG-917 (S-58, S-59), BUG-918 (S-65), BUG-903 (S-66) | `factory_section_manager.cases.md` | The queries are the manager's; L-09, L-11, L-12, C-10 here are pass-throughs only. |
| Manager rules beyond one pass-through per bug | `factory_section_manager.cases.md` | Not re-tested here. |
| Session closed by the request dependency | `get_db` | Integration-only. |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_factory_section` | R1 | FSS-C-01 |
| `create_factory_section` | R1 [BUG-911] | FSS-C-10 |
| `create_factory_section` | R1 [BUG-912] | FSS-C-09 |
| `create_factory_section` | R1 [BUG-913] | FSS-C-11 |
| `create_factory_section` | R1 [BUG-915] | FSS-C-08 |
| `create_factory_section` | R2 | FSS-C-02, FSS-C-03, FSS-C-04 |
| `create_factory_section` | R3 | FSS-C-06, FSS-C-07 |
| `create_factory_section` | Errors (database error) | FSS-C-05 |
| `create_factory_section` | Returns | FSS-C-01 |
| `get_factory_section` | R1 | FSS-G-01 |
| `get_factory_section` | R2 [BUG-916] | FSS-G-04 |
| `get_factory_section` | R3 [BUG-916] | FSS-G-05, FSS-G-06 |
| `get_factory_section` | R4 [BUG-925] | FSS-G-07, FSS-G-08 |
| `get_factory_section` | R5 | FSS-G-02, FSS-G-03, FSS-G-09 |
| `get_factory_section` | Errors row 1 | FSS-G-02, FSS-G-03, FSS-G-04, FSS-G-06, FSS-G-07 |
| `get_factory_sections` | R1 | FSS-L-01, FSS-L-02, FSS-L-03, FSS-L-04, FSS-L-05 |
| `get_factory_sections` | R1 [BUG-903] | FSS-L-09 |
| `get_factory_sections` | R1 [BUG-904] | FSS-L-10 |
| `get_factory_sections` | R1 [BUG-905] | Deferred (section DAO) |
| `get_factory_sections` | R1 [BUG-917] | FSS-L-11 |
| `get_factory_sections` | R1 [BUG-918] | FSS-L-12 |
| `get_factory_sections` | R1 [BUG-921] | FSS-L-13 |
| `get_factory_sections` | R1 [BUG-922] | FSS-L-14 |
| `get_factory_sections` | R1 [BUG-924] | FSS-L-15 |
| `get_factory_sections` | R2 | FSS-L-06 |
| `get_factory_sections` | R2 [BUG-920] | FSS-L-07 |
| `get_factory_sections` | R3 | FSS-L-08 |
| `update_factory_section` | R1 | FSS-U-01 |
| `update_factory_section` | R1 [BUG-914] | FSS-U-07 |
| `update_factory_section` | R1 [BUG-919] | FSS-U-08 |
| `update_factory_section` | R1 [BUG-926] | FSS-U-10 |
| `update_factory_section` | R2 | FSS-U-02, FSS-U-03, FSS-U-04, FSS-U-05, FSS-U-06 |
| `update_factory_section` | R2 [BUG-923] | FSS-U-09 |
| `update_factory_section` | R2 [BUG-928] | FSS-U-11 |
| `update_factory_section` | R3 | FSS-C-06, FSS-C-07 (TC4, TC5 once per service: the commit helper is shared) |
| `update_factory_section` | Returns | FSS-U-01 |
| `delete_factory_section` | R1 | FSS-D-01 |
| `delete_factory_section` | R1 [BUG-906, BUG-907] | Deferred (assignment layer) |
| `delete_factory_section` | R1 [BUG-908] | FSS-D-04 |
| `delete_factory_section` | R2 | FSS-D-02, FSS-D-03 |
| `delete_factory_section` | R2 [BUG-927] | FSS-D-05 |
| `delete_factory_section` | R3 | FSS-C-06, FSS-C-07 (TC4, TC5 once per service) |
| `delete_factory_section` | Returns | FSS-D-01 |
| Transaction contract | TC1 | FSS-C-01, FSS-U-01, FSS-D-01 |
| Transaction contract | TC2 | FSS-C-01, FSS-U-01, FSS-D-01 |
| Transaction contract | TC3 | FSS-C-02, FSS-C-05, FSS-U-02, FSS-D-02 |
| Transaction contract | TC4 | FSS-C-06 |
| Transaction contract | TC5 | FSS-C-07 |
| Transaction contract | TC6 | FSS-G-09, FSS-L-08 |
