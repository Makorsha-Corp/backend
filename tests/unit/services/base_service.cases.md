# Test cases — `app/services/base_service.py`

> **Spec:** `tests/unit/services/base_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Counts:** 8 cases · 8 expected-to-pass · 0 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `_commit_transaction` 5 · `_rollback_transaction` 3.
- **Depth:** lighter target (skill step 1a). Two helpers that end a transaction; no stock, money or order state, no decision beyond "commit failed → roll back". One card per rule; B2 has two (a flushed row and an edited row are discarded; the session is usable after).
- **Expected-to-fail:** none; the spec has no bug.
- **Notable design choices:**
  - TC1–TC6 are not tested here: the spec puts them in each service's own cases (Deferred).
  - "Same object" is checked with `is` on an exception instance the card builds before the call (`E`, `E1`, `E2`).
  - The rollback spy wraps the real rollback (`wraps=db.rollback`), so B2 counts the calls and still really rolls back.
  - Each kind of pending change named by B1 and B5 (added only, flushed, an edited committed row) is its own Given row in one card.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `BSV` = `app/services/base_service.py`. `C` _commit_transaction · `R` _rollback_transaction.

**Actors and fixed values.**
- `svc = BaseService()` (`from app.services.base_service import BaseService`); no arguments. Both helpers take `db` positionally: `svc._commit_transaction(db)`, `svc._rollback_transaction(db)`. `result` = what the When call returns.
- `Workspace` (`app.models.workspace`); `make_workspace`, `make_subscription_plan` (`tests/unit/factories.py`; both flush, neither commits). `text`, `select` (`sqlalchemy`); `patch` (`unittest.mock`).

**Externals.** None is mocked. The cards that name **failing commit**, **failing rollback** or **spies** patch the session itself, as the spec's Notes say.

**Given rows.** Workspaces only, built with `make_workspace(db, name=…)` (flushed). A Given line written as code is a step to run exactly as written, in order.
- **commit point** = after the Given lines above it the test runs `db.commit()` (under the `db` fixture it only releases a savepoint). Lines marked "(after the commit point)" run after it and stay uncommitted.
- **added only** = a `Workspace` built with `Workspace(name=…, slug=…, subscription_plan_id=P.id)` and `db.add(...)`, never flushed by the test.

**Named checks.**
- **found(name)** = `db.scalar(select(func.count()).select_from(Workspace).where(Workspace.name == name))`, a fresh query (`func` from `sqlalchemy`).
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then runs a fresh query. What it finds was committed by the call.
- `count:` lines run a fresh query without any test-level rollback.
- `session:` "usable" = `make_workspace(db, name="After")` runs and returns a row whose `id is not None`.
- **failing commit** = `with patch.object(db, "commit", side_effect=E1), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When, inside `with pytest.raises(type(E1)) as exc:`. Checks after the block run with the patches gone.
- **failing rollback** = `with patch.object(db, "rollback", side_effect=E2):` around the When, inside `with pytest.raises(type(E2)) as exc:`.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.

**Race simulations.** None.

## `BaseService._commit_transaction`

### BSV-C-01 — added, flushed and edited changes are all committed
- **Rules:** B1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `P = make_subscription_plan(db)`.
2. `M = make_workspace(db, name="Before")`.
3. commit point.
4. `M.name = "Edited"` (after the commit point; not flushed).
5. `F = make_workspace(db, name="Flushed")` (after the commit point).
6. `N = Workspace(name="Added", slug=f"bsv-added-{P.id}", subscription_plan_id=P.id)`, `db.add(N)` (after the commit point; added only).

**When**
- `result = svc._commit_transaction(db)`.

**Then**
1. returns: `result is None`.
2. committed: `found("Flushed") == 1`.
3. committed: `found("Added") == 1`.
4. committed: `found("Edited") == 1`.
5. committed: `found("Before") == 0`.

### BSV-C-02 — a failing commit rolls back once and re-raises the same exception
- **Rules:** B2; Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. `M = make_workspace(db, name="Before")`.
2. commit point.
3. `M.name = "Edited"` (after the commit point), then `db.flush()`.
4. `F = make_workspace(db, name="Pending")` (after the commit point).
5. `E1 = RuntimeError("boom")`.

**When**
- `svc._commit_transaction(db)`, inside **failing commit**.

**Then**
1. raises: `exc.value is E1`.
2. mock called: `rb.call_count == 1`.
3. count: `found("Pending") == 0`.
4. count: `found("Edited") == 0`.
5. count: `found("Before") == 1`.

### BSV-C-03 — after a failed commit the session is usable
- **Rules:** B2
- **Kind:** error
- **Expect:** pass

**Given**
1. commit point.
2. `F = make_workspace(db, name="Pending")` (after the commit point).
3. `E1 = RuntimeError("boom")`.

**When**
- `svc._commit_transaction(db)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. count: `found("Pending") == 0`.
3. session: usable.
4. count: `found("After") == 1`.

### BSV-C-04 — commit and rollback both fail: the rollback's exception wins, the commit's is its context
- **Rules:** B3; Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. commit point.
2. `F = make_workspace(db, name="Pending")` (after the commit point).
3. `E1 = RuntimeError("boom")`.
4. `E2 = ValueError("rb")`.

**When**
- inside `with pytest.raises(ValueError) as exc:`, inside `with patch.object(db, "commit", side_effect=E1), patch.object(db, "rollback", side_effect=E2):`, call `svc._commit_transaction(db)`.

**Then**
1. raises: `exc.value is E2`.
2. raises: `exc.value.__context__ is E1`.

### BSV-C-05 — a commit with nothing pending returns None and commits once
- **Rules:** B4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `K = make_workspace(db, name="Kept")`.
2. commit point.

**When**
- `result = svc._commit_transaction(db)`, inside **spies**.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 1`.
3. mock called: `rb.call_count == 0`.
4. committed: `found("Kept") == 1`.

## `BaseService._rollback_transaction`

### BSV-R-01 — flushed, added and edited changes are discarded; committed rows stay
- **Rules:** B5
- **Kind:** happy
- **Expect:** pass

**Given**
1. `P = make_subscription_plan(db)`.
2. `K = make_workspace(db, name="Kept")`.
3. commit point.
4. `K.name = "Changed"` (after the commit point), then `db.flush()`.
5. `F = make_workspace(db, name="Flushed")` (after the commit point).
6. `N = Workspace(name="Added", slug=f"bsv-added-{P.id}", subscription_plan_id=P.id)`, `db.add(N)` (after the commit point; added only).

**When**
- `result = svc._rollback_transaction(db)`.

**Then**
1. returns: `result is None`.
2. count: `found("Flushed") == 0`.
3. count: `found("Added") == 0`.
4. count: `found("Changed") == 0`.
5. count: `found("Kept") == 1`.

### BSV-R-02 — a rollback on a clean session does nothing, rolls back once and never commits
- **Rules:** B6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `K = make_workspace(db, name="Kept")`.
2. commit point.

**When**
- `result = svc._rollback_transaction(db)`, inside **spies**.

**Then**
1. returns: `result is None`.
2. mock called: `rb.call_count == 1`.
3. mock called: `cm.call_count == 0`.
4. count: `found("Kept") == 1`.
5. session: usable.

### BSV-R-03 — a failing rollback's exception reaches the caller unchanged
- **Rules:** B7; Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. commit point.
2. `E2 = ValueError("rb")`.

**When**
- `svc._rollback_transaction(db)`, inside **failing rollback**.

**Then**
1. raises: `exc.value is E2`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| TC1 | each `BaseService` subclass spec | a successful write survives a later rollback |
| TC2 | each subclass spec | the returned row is re-read after the commit (`created_at` loaded, not expired) |
| TC3 | each subclass spec | a manager exception rolls back, reaches the caller as the same object, discards other pending changes; session usable |
| TC4 | each subclass spec | a failing commit rolls back and re-raises; nothing saved |
| TC5 | each subclass spec | a failing re-read after the commit re-raises; the change stays saved |
| TC6 | each subclass spec (incl. `calendar_service.cases.md` CAL-GE-13) | a read neither commits nor rolls back |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_commit_transaction` | B1 | BSV-C-01 |
| `_commit_transaction` | B2 | BSV-C-02, BSV-C-03 |
| `_commit_transaction` | B3 | BSV-C-04 |
| `_commit_transaction` | B4 | BSV-C-05 |
| `_commit_transaction` | Errors row 1 (commit fails) | BSV-C-02 |
| `_commit_transaction` | Errors row 2 (commit and rollback fail) | BSV-C-04 |
| `_rollback_transaction` | B5 | BSV-R-01 |
| `_rollback_transaction` | B6 | BSV-R-02 |
| `_rollback_transaction` | B7; Errors | BSV-R-03 |
| `BaseService` | TC1–TC6 | Deferred |
