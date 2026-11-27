# Test cases — `app/services/delivery_method_service.py`

> **Spec:** `tests/unit/services/delivery_method_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 1 — spec Gap log G1 (schemas named) and G2 (the manager's search described). New: DMS-L-08 (a case-insensitive substring reaches the manager). Changed: Conventions and Reviewer summary lines only (the schema note). No other card changed, none retired.
> **Counts:** 28 cases · 24 expected-to-pass · 4 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `create_delivery_method` 6 · `get_delivery_method` 7 (3 bug) · `get_delivery_methods` 8 (1 bug) · `update_delivery_method` 4 · `delete_delivery_method` 3.
- **Depth:** lighter target (skill step 1a): a transaction wrapper over reference data, the same code as `department_service`. TC2, TC4, TC5 once (on create), TC1 and TC3 once per write, TC6 once per read, each refusal status once or more.
- **Expected-to-fail:** BUG-1523 3 (G-04 … G-06), BUG-1522 1 (L-06). All strict.
- **Notable design choices:**
  - Same commit point and uncommitted-extra-row device as `department_service.cases.md`.
  - The manager has no spec: cards assert only the refusal values the spec lists as pass-through. List cards use the search the spec's Facts describe (case-insensitive substring, applied after the page is cut), on rows that all fit in one page; counts, not orders.
  - The database-error row is reached through an unknown `user_id` (`created_by` FK; the table is as `departments` except where the delivery method DAO spec says it differs). C-05 is today's behavior and stays a pass card: the table has no unique constraint.
  - Input schemas `DeliveryMethodCreate(name=…)`, `DeliveryMethodUpdate(name=…)` from `app.schemas.delivery_method` (spec Facts, G1).
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `DMS` = `app/services/delivery_method_service.py`. `C` create_delivery_method · `G` get_delivery_method · `L` get_delivery_methods · `U` update_delivery_method · `D` delete_delivery_method.

**Actors and fixed values.**
- `svc` = the singleton `delivery_method_service` (`from app.services.delivery_method_service import DeliveryMethodService, delivery_method_service`). `db` = the test's real session, always the first argument; every other argument by keyword. `result` = what the When call returns.
- `DeliveryMethod` (`app.models.delivery_method`), `DeliveryMethodCreate`, `DeliveryMethodUpdate` (`app.schemas.delivery_method`), `HTTPException` (`fastapi`), `IntegrityError` (`sqlalchemy.exc`), `inspect`, `text` (`sqlalchemy`), `patch` (`unittest.mock`).
- W1, W2 = two `workspaces` rows; U1, U2 = two `profiles` rows, from `make_workspace`, `make_profile`. They exist in every test and need no Given line. U1 is the acting user; U2 created the Given rows.
- MISSING = `999999999`. T0 = `datetime(2020, 1, 2, 3, 4, 5)` (naive).

**Externals.** None is mocked. `deleted_at` is the DAO's clock, checked as not None.

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A Given line written as code is a step to run exactly as written.
- **method** = `DeliveryMethod(workspace_id=W1.id, name="Courier", created_by=U2.id)`; `is_active`, `is_deleted` left to `True`, `False`; `updated_by`, `deleted_at`, `deleted_by` NULL. After "but" the card lists every column that differs.
- **gone** (after "but") = `is_deleted True`, `deleted_at T0`, `deleted_by U2.id`.
- Two live rows of one workspace never share a name, except where a card says otherwise.
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). A Given line marked "(after the commit point)" runs after it, is flushed, and stays uncommitted.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the number of `delivery_methods` rows (all workspaces) equals its value at the commit point.
- `count:` lines count `delivery_methods` rows with a fresh query, with the filter stated.
- `loaded:` lines run on the returned object first, before any other Then line touches the session: each column named is not in `inspect(result).unloaded`.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `session:` lines check `db` itself; "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: HTTPException`, `raises: IntegrityError`: plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint (the service rolls back itself). Further `raises:` lines assert on `exc.value` after the block.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When. Checks after the block run with the patches gone.

**xfail cards.** Write the call and checks as shown, also when a parameter does not exist yet. All strict: `pytest.mark.xfail(strict=True, reason="BUG-NNN")`.

**Race simulations.** None in this module.

## `DeliveryMethodService.create_delivery_method`

### DMS-C-01 — a new method is committed and returned re-read
- **Rules:** `create_delivery_method` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no delivery methods.

**When**
- `result = svc.create_delivery_method(db, delivery_method_in=DeliveryMethodCreate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `created_at`, `name`, `workspace_id`, `created_by`.
2. returns: `isinstance(result, DeliveryMethod)`.
3. returns: `result.id is not None`, `result.created_at is not None`.
4. returns: `result.name == "Courier"`, `result.workspace_id == W1.id`, `result.created_by == U1.id`.
5. committed: the row with `id == result.id` exists: `name == "Courier"`, `workspace_id == W1.id`, `created_by == U1.id`, `is_deleted is False`.
6. committed: W1 has exactly 1 `delivery_methods` row.

### DMS-C-02 — a live duplicate: the manager's 409 passes unchanged and the session is rolled back
- **Rules:** `create_delivery_method` R2, Errors; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = method.
2. X = method, but `name "Extra"` (after the commit point).

**When**
- `svc.create_delivery_method(db, delivery_method_in=DeliveryMethodCreate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Delivery method with name 'Courier' already exists"`.
4. count: `delivery_methods` rows with `name == "Extra"`: exactly 0.
5. nothing written: nothing written.
6. unchanged: unchanged(A).
7. session: usable.

### DMS-C-03 — a failing commit is rolled back and re-raised
- **Rules:** `create_delivery_method` R4; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no delivery methods.

**When**
- `svc.create_delivery_method(db, delivery_method_in=DeliveryMethodCreate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `delivery_methods` rows of W1: exactly 0.

### DMS-C-04 — a failing re-read after the commit leaves the method saved
- **Rules:** `create_delivery_method` R4; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no delivery methods.

**When**
- `svc.create_delivery_method(db, delivery_method_in=DeliveryMethodCreate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: W1 has exactly 1 `delivery_methods` row.
3. committed: that row has `name == "Courier"`, `created_by == U1.id`.

### DMS-C-05 — a name used only by a soft-deleted method is accepted
- **Rules:** `create_delivery_method` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = method, gone.

**When**
- `result = svc.create_delivery_method(db, delivery_method_in=DeliveryMethodCreate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id != A.id`.
2. returns: `result.name == "Courier"`, `result.is_deleted is False`.
3. committed: `delivery_methods` rows of W1 with `name == "Courier"`: exactly 2.
4. committed: re-read A: `is_deleted is True`.

### DMS-C-06 — a database error at the flush passes unchanged and nothing is saved
- **Rules:** `create_delivery_method` Errors; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = method, but `name "Pickup"`.

**When**
- `svc.create_delivery_method(db, delivery_method_in=DeliveryMethodCreate(name="Courier"), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. count: `delivery_methods` rows with `name == "Courier"`: exactly 0.
4. nothing written: nothing written.
5. session: usable.

## `DeliveryMethodService.get_delivery_method`

### DMS-G-01 — a live method of the workspace is returned
- **Rules:** `get_delivery_method` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z = method, but `workspace_id W2.id`, `name "Far"`.
2. A = method.

**When**
- `result = svc.get_delivery_method(db, delivery_method_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, DeliveryMethod)`.
2. returns: `result.id == A.id`, `result.name == "Courier"`.

### DMS-G-02 — another workspace's id: the 404 passes unchanged
- **Rules:** `get_delivery_method` R4, Errors
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = method.
2. Z = method, but `workspace_id W2.id`, `name "Far"`.

**When**
- `svc.get_delivery_method(db, delivery_method_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Delivery method with ID {Z.id} not found"`.

### DMS-G-03 — id 0 gets the 404
- **Rules:** `get_delivery_method` R4, Errors
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = method.

**When**
- `svc.get_delivery_method(db, delivery_method_id=0, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Delivery method with ID 0 not found"`.

### DMS-G-04 — a soft-deleted method is hidden by default
- **Rules:** `get_delivery_method` R2 [BUG-1523], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1523
- **Fails today on:** Then 1 (no error is raised: the deleted method is returned)

**Given**
1. A = method, gone.

**When**
- `svc.get_delivery_method(db, delivery_method_id=A.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Delivery method with ID {A.id} not found"`.

### DMS-G-05 — include_deleted=True returns a soft-deleted method
- **Rules:** `get_delivery_method` R3 [BUG-1523]
- **Kind:** bug
- **Expect:** xfail BUG-1523
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = method, gone.

**When**
- `result = svc.get_delivery_method(db, delivery_method_id=A.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.is_deleted is True`.

### DMS-G-06 — include_deleted=True does not reach another workspace
- **Rules:** `get_delivery_method` R3 [BUG-1523], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1523
- **Fails today on:** Then 1 (the call raises TypeError, not HTTPException)

**Given**
1. Z = method, but `workspace_id W2.id`, `name "Far"`, gone.

**When**
- `svc.get_delivery_method(db, delivery_method_id=Z.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Delivery method with ID {Z.id} not found"`.

### DMS-G-07 — the read neither commits nor rolls back
- **Rules:** `get_delivery_method` R5; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = method.
2. B = method, but `name "Pickup"`.
3. P = method, but `name "Pending"` (after the commit point).
4. `B.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_delivery_method(db, delivery_method_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. count: `delivery_methods` rows with `name == "Pending"`: exactly 1.
5. committed: `delivery_methods` rows with `name == "Pending"`: exactly 0.
6. committed: re-read B: `name == "Pickup"`.

## `DeliveryMethodService.get_delivery_methods`

### DMS-L-01 — the search reaches the manager and only the workspace's match comes back
- **Rules:** `get_delivery_methods` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = method.
2. B = method, but `name "Pickup"`.
3. Z = method, but `workspace_id W2.id`.

**When**
- `result = svc.get_delivery_methods(db, workspace_id=W1.id, search="Courier")`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `[r.id for r in result] == [A.id]`.

### DMS-L-02 — with the defaults 101 live methods give 100
- **Rules:** `get_delivery_methods` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows, by `add_all`: k = 1 … 101, method, but `name f"Method {k:03d}"`.

**When**
- `result = svc.get_delivery_methods(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### DMS-L-03 — limit reaches the manager
- **Rules:** `get_delivery_methods` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, in this order: method, but `name` `"Alpha"`, `"Bravo"`, `"Charlie"`, `"Delta"`, `"Echo"`.

**When**
- `result = svc.get_delivery_methods(db, workspace_id=W1.id, skip=0, limit=2)`.

**Then**
1. returns: `len(result) == 2`.

### DMS-L-04 — skip reaches the manager, limit=1000 takes the rest
- **Rules:** `get_delivery_methods` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 rows, in this order: method, but `name` `"Alpha"`, `"Bravo"`, `"Charlie"`, `"Delta"`, `"Echo"`.

**When**
- `result = svc.get_delivery_methods(db, workspace_id=W1.id, skip=4, limit=1000)`.

**Then**
1. returns: `len(result) == 1`.

### DMS-L-05 — by default a soft-deleted method is left out
- **Rules:** `get_delivery_methods` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = method.
2. D = method, but `name "Old Method"`, gone.

**When**
- `result = svc.get_delivery_methods(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result] == [A.id]`.

### DMS-L-06 — include_deleted=True lists soft-deleted methods too
- **Rules:** `get_delivery_methods` R2 [BUG-1522]
- **Kind:** bug
- **Expect:** xfail BUG-1522
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. A = method.
2. D = method, but `name "Old Method"`, gone.

**When**
- `result = svc.get_delivery_methods(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `sorted(r.id for r in result) == [A.id, D.id]`.

### DMS-L-07 — the list neither commits nor rolls back
- **Rules:** `get_delivery_methods` R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = method.
2. B = method, but `workspace_id W2.id`, `name "Pickup"`.
3. P = method, but `name "Pending"` (after the commit point).
4. `B.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_delivery_methods(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(r.id for r in result) == sorted([A.id, P.id])`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. committed: `delivery_methods` rows with `name == "Pending"`: exactly 0.
5. committed: re-read B: `name == "Pickup"`.

### DMS-L-08 — a case-insensitive part of the name reaches the manager as the search
- **Rules:** `get_delivery_methods` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = method.
2. B = method, but `name "Pickup"`.

**When**
- `result = svc.get_delivery_methods(db, workspace_id=W1.id, search="OURI")`.

**Then**
1. returns: `[r.id for r in result] == [A.id]`.

## `DeliveryMethodService.update_delivery_method`

### DMS-U-01 — a rename is committed and returned re-read with updated_at
- **Rules:** `update_delivery_method` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = method.

**When**
- `result = svc.update_delivery_method(db, delivery_method_id=A.id, delivery_method_in=DeliveryMethodUpdate(name="Own Fleet"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `updated_at`, `updated_by`, `name`.
2. returns: `result.id == A.id`.
3. returns: `result.name == "Own Fleet"`, `result.updated_by == U1.id`, `result.updated_at is not None`.
4. committed: re-read A: `name == "Own Fleet"`, `updated_by == U1.id`, `updated_at is not None`.

### DMS-U-02 — another workspace's id: the 404 passes unchanged and the session is rolled back
- **Rules:** `update_delivery_method` R2, Errors; TC3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = method.
2. Z = method, but `workspace_id W2.id`, `name "Far"`.
3. X = method, but `name "Extra"` (after the commit point).

**When**
- `svc.update_delivery_method(db, delivery_method_id=Z.id, delivery_method_in=DeliveryMethodUpdate(name="Hacked"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Delivery method with ID {Z.id} not found"`.
4. count: `delivery_methods` rows with `name == "Extra"`: exactly 0.
5. unchanged: unchanged(Z).
6. nothing written: nothing written.

### DMS-U-03 — a deleted method: the 400 passes unchanged, nothing saved
- **Rules:** `update_delivery_method` R2, Errors
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = method, gone.

**When**
- `svc.update_delivery_method(db, delivery_method_id=A.id, delivery_method_in=DeliveryMethodUpdate(name="Revived"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted delivery method"`.
4. unchanged: unchanged(A).

### DMS-U-04 — a name taken: the 409 passes unchanged, nothing saved
- **Rules:** `update_delivery_method` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = method.
2. B = method, but `name "Pickup"`.

**When**
- `svc.update_delivery_method(db, delivery_method_id=B.id, delivery_method_in=DeliveryMethodUpdate(name="Courier"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Delivery method with name 'Courier' already exists"`.
4. unchanged: unchanged(B).

## `DeliveryMethodService.delete_delivery_method`

### DMS-D-01 — a soft delete is committed and returned re-read
- **Rules:** `delete_delivery_method` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = method.

**When**
- `result = svc.delete_delivery_method(db, delivery_method_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `is_deleted`, `deleted_at`, `deleted_by`.
2. returns: `result.id == A.id`.
3. returns: `result.is_deleted is True`, `result.deleted_by == U1.id`, `result.deleted_at is not None`.
4. committed: re-read A: `is_deleted is True`, `deleted_by == U1.id`, `deleted_at is not None`.

### DMS-D-02 — an already deleted method: the 400 passes unchanged and the session is rolled back
- **Rules:** `delete_delivery_method` R2, Errors; TC3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = method, gone.
2. X = method, but `name "Extra"` (after the commit point).

**When**
- `svc.delete_delivery_method(db, delivery_method_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Delivery method is already deleted"`.
4. count: `delivery_methods` rows with `name == "Extra"`: exactly 0.
5. unchanged: unchanged(A).
6. session: usable.

### DMS-D-03 — an unknown id: the 404 passes unchanged
- **Rules:** `delete_delivery_method` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = method.

**When**
- `svc.delete_delivery_method(db, delivery_method_id=MISSING, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Delivery method with ID 999999999 not found"`.
4. unchanged: unchanged(A).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| The manager's own rules (search, paging, order, names, stamps); FU-1 (b) `include_deleted` before paging (HR-5) | `DeliveryMethodManager` (no spec yet) | Its own cases. L-01 … L-04 here pass through only. |
| BUG-1523 manager half (`get_delivery_method` gains `include_deleted`) | `DeliveryMethodManager`, FU-1 (a) | The manager's 404 by default and with the flag. |
| BUG-1522, BUG-1523 — the `include_deleted` query parameters | `GET /delivery-methods/`, `GET /delivery-methods/{id}/` | Integration-only. |
| HR-7 — `skip >= 0`, `1 <= limit <= 1000` | `GET /delivery-methods/` | Endpoint bounds. |
| BUG-730 — a deleted method chosen on a delivery | sales delivery code | Not reached here. |
| Schema validation (400 today, BUG-461) | `POST`, `PUT /delivery-methods/` | Integration-only. |

## Spec gaps
None. Revision 0's gaps 1 and 2 are closed by spec Gap log G1, G2.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_delivery_method` | R1 | DMS-C-01 |
| `create_delivery_method` | R2 | DMS-C-02 |
| `create_delivery_method` | R3 | DMS-C-05 |
| `create_delivery_method` | R4 | DMS-C-03, DMS-C-04 |
| `create_delivery_method` | Errors | DMS-C-02, DMS-C-06 |
| `create_delivery_method` | Returns | DMS-C-01 |
| `get_delivery_method` | R1 | DMS-G-01 |
| `get_delivery_method` | R2 [BUG-1523] | DMS-G-04 |
| `get_delivery_method` | R3 [BUG-1523] | DMS-G-05, DMS-G-06 |
| `get_delivery_method` | R4 | DMS-G-02, DMS-G-03 |
| `get_delivery_method` | R5 | DMS-G-07 |
| `get_delivery_method` | Errors | DMS-G-02, DMS-G-03, DMS-G-04, DMS-G-06 |
| `get_delivery_methods` | R1 | DMS-L-01, DMS-L-02, DMS-L-03, DMS-L-04, DMS-L-08 |
| `get_delivery_methods` | R2 | DMS-L-05 |
| `get_delivery_methods` | R2 [BUG-1522] | DMS-L-06 |
| `get_delivery_methods` | R3 | DMS-L-07 |
| `update_delivery_method` | R1 | DMS-U-01 |
| `update_delivery_method` | R2 | DMS-U-02, DMS-U-03, DMS-U-04 |
| `update_delivery_method` | R3 | DMS-C-03, DMS-C-04 (TC4, TC5 once per service, as the spec's Notes allow) |
| `update_delivery_method` | Errors | DMS-U-02, DMS-U-03, DMS-U-04 |
| `update_delivery_method` | Returns | DMS-U-01 |
| `delete_delivery_method` | R1 | DMS-D-01 |
| `delete_delivery_method` | R2 | DMS-D-02, DMS-D-03 |
| `delete_delivery_method` | R3 | DMS-C-03, DMS-C-04 (TC4, TC5 once per service) |
| `delete_delivery_method` | Errors | DMS-D-02, DMS-D-03 |
| `delete_delivery_method` | Returns | DMS-D-01 |
| Transaction contract | TC1 | DMS-C-01, DMS-U-01, DMS-D-01 |
| Transaction contract | TC2 | DMS-C-01 (also DMS-U-01, DMS-D-01) |
| Transaction contract | TC3 | DMS-C-02, DMS-C-06, DMS-U-02, DMS-D-02 |
| Transaction contract | TC4 | DMS-C-03 |
| Transaction contract | TC5 | DMS-C-04 |
| Transaction contract | TC6 | DMS-G-07, DMS-L-07 |
