# Test cases — `app/dao/workspace.py`

> **Spec:** `tests/unit/dao/workspace.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (no questions; nothing open).
> **Revision:** 2 — the spec did not change. Additive, from `workspace.verify.md` (case-missing Findings 1, 2; recipes R-1, R-2): Finding 1 → WSP-GS-17, GS-18; Finding 2 → WSP-GS-19. No existing Given, When, Then or ID changed, none retired; WSP-IN-04 stands as in revision 1.
> **Revision 1:** the spec did not change. From `workspace.notes.md` DISCREPANCY-1 (kind `flaky`, about 1 run in 400): `datetime.now` moves in ticks on Windows, so the insert and the update of WSP-IN-04 can share one and Then 3 fails. WSP-IN-04 gains Given 4, a wait until `utcnow()` has moved past `U0`; Conventions gain `utcnow`. Then 3 and Then 4 stand as written. No When, Then or ID changed, none retired, Counts unchanged.
> **Counts:** 23 cases · 23 expected-to-pass · 0 expected-to-fail (bugs) · 4 deferred

## Reviewer summary
- **Per callable:** `get_by_slug` 19 · `inherited` 4.
- **Depth:** lighter target (skill step 1a). One exact lookup on a unique column; the module writes no stock, money or order state. Each input the rules name still gets a card, because a When holds one call.
- **Expected-to-fail:** none. The spec has no bug.
- **Commit spies:** none. `get_by_slug` only reads, and the inherited writers are spied by BASE-C-05, BASE-U-12, BASE-R-02.
- **Statement recorder:** none for order: an exact match on a unique column has nothing to order.
- **Notable design choices:**
  - WSP-GS-07 and GS-08 use `acme%` and `acme_co` on the slug `acme-co`, so a `LIKE` would match both. Every "finds nothing" card has that row in the table.
  - "Writes nothing" is a miss (GS-14) and a hit (GS-15), each with `len(db.new)`, and GS-19 with an edited row in the session.
  - The keyword-only parameter gets a card (GS-16) because the Inputs table states the error; on the other modules it is a note, so Spec gaps.
  - WSP-IN-04 compares `updated_at` with its value before the call as well as with `created_at`: both come from Python, so `created_at` alone could pass with no update.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `WSP` = `app/dao/workspace.py`. `GS` get_by_slug · `IN` inherited `BaseDAO` methods on this model.

**Actors and fixed values.**
- `dao` = the singleton `workspace_dao` (`from app.dao.workspace import workspace_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword unless the card says otherwise. `result` = what the When call returns.
- `Workspace` = `app.models.workspace.Workspace`. `WorkspaceCreate`, `WorkspaceUpdate` = the schemas of `app.schemas.workspace`. `WorkspaceMember` = `app.models.workspace_member.WorkspaceMember`. `make_workspace` = `tests/unit/factories.py`: it builds a plan too, and leaves every column it is not given to its default. `utcnow` = `app.utils.time.utcnow`, the real clock, not patched.

**Externals.** None. Nothing is mocked. `created_at`, `updated_at` and `last_usage_reset_at` use the model's own `utcnow`.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from the defaults below. A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.
- **W(s)** = `make_workspace(db, slug=s)`. No workspace exists in a test unless its Given lists it.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line). **unchanged(X) except `c`, …** = the same, leaving out the columns named.
- **nothing written** = the number of `workspaces` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P after the call, on the object itself. `pending: len(db.new) == 1` checks that P is the only object waiting in the session.
- `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the When: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line.
- A `session:` line is a check on the session object.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on it.

**Race simulations.** None in this module.

## `WorkspaceDAO.get_by_slug`

### WSP-GS-01 — returns the workspace with that slug, not the first workspace
- **Rules:** `get_by_slug` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = W("beta-co").
2. A = W("acme-co").

**When**
- `result = dao.get_by_slug(db, slug="acme-co")`.

**Then**
1. returns: `isinstance(result, Workspace)`.
2. returns: `result.id == A.id`.
3. returns: `result.slug == "acme-co"`.

### WSP-GS-02 — capitals do not find a lower-case slug
- **Rules:** `get_by_slug` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = W("acme-co").

**When**
- `result = dao.get_by_slug(db, slug="ACME-CO")`.

**Then**
1. returns: `result is None`.

### WSP-GS-03 — a leading space finds nothing
- **Rules:** `get_by_slug` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = W("acme-co").

**When**
- `result = dao.get_by_slug(db, slug=" acme-co")`.

**Then**
1. returns: `result is None`.

### WSP-GS-04 — a trailing space finds nothing
- **Rules:** `get_by_slug` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = W("acme-co").

**When**
- `result = dao.get_by_slug(db, slug="acme-co ")`.

**Then**
1. returns: `result is None`.

### WSP-GS-05 — a mixed-case slug is found as typed
- **Rules:** `get_by_slug` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = W("MiXeD").

**When**
- `result = dao.get_by_slug(db, slug="MiXeD")`.

**Then**
1. returns: `result.id == A.id`.

### WSP-GS-06 — a mixed-case slug is not found in lower case
- **Rules:** `get_by_slug` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = W("MiXeD").

**When**
- `result = dao.get_by_slug(db, slug="mixed")`.

**Then**
1. returns: `result is None`.

### WSP-GS-07 — % is no wildcard
- **Rules:** `get_by_slug` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = W("acme-co").

**When**
- `result = dao.get_by_slug(db, slug="acme%")`.

**Then**
1. returns: `result is None`.

### WSP-GS-08 — _ is no wildcard
- **Rules:** `get_by_slug` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = W("acme-co").

**When**
- `result = dao.get_by_slug(db, slug="acme_co")`.

**Then**
1. returns: `result is None`.

### WSP-GS-09 — an unknown slug returns None
- **Rules:** `get_by_slug` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = W("acme-co").

**When**
- `result = dao.get_by_slug(db, slug="no-such-slug")`.

**Then**
1. returns: `result is None`.

### WSP-GS-10 — an empty slug returns None
- **Rules:** `get_by_slug` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = W("acme-co").

**When**
- `result = dao.get_by_slug(db, slug="")`.

**Then**
1. returns: `result is None`.

### WSP-GS-11 — a None slug returns None
- **Rules:** `get_by_slug` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = W("acme-co").

**When**
- `result = dao.get_by_slug(db, slug=None)`.

**Then**
1. returns: `result is None`.

### WSP-GS-12 — a workspace nobody belongs to is found
- **Rules:** `get_by_slug` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = W("acme-co").

**When**
- `result = dao.get_by_slug(db, slug="acme-co")`.

**Then**
1. returns: `result.id == A.id`.
2. count: `workspace_members` has exactly 0 rows with `workspace_id == A.id`.

### WSP-GS-13 — a workspace whose subscription ended is found
- **Rules:** `get_by_slug` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = make_workspace(db, slug="acme-co", subscription_status="cancelled").

**When**
- `result = dao.get_by_slug(db, slug="acme-co")`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.subscription_status == "cancelled"`.

### WSP-GS-14 — writes nothing: a pending row stays pending and is not found
- **Rules:** `get_by_slug` R4, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = W("acme-co").
2. `P = Workspace(name="Pending", slug="pending-co", subscription_plan_id=A.subscription_plan_id)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_slug(db, slug="pending-co")`.

**Then**
1. returns: `result is None`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. nothing written: nothing written.
6. unchanged: unchanged(A).
7. statement: `written == []`.

### WSP-GS-15 — writes nothing: a read that finds its row leaves the session as it was
- **Rules:** `get_by_slug` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = W("acme-co").
2. `P = Workspace(name="Pending", slug="pending-co", subscription_plan_id=A.subscription_plan_id)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_slug(db, slug="acme-co")`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. nothing written: nothing written.
5. statement: `written == []`.

### WSP-GS-16 — a positional slug raises TypeError
- **Rules:** `get_by_slug` Inputs
- **Kind:** error
- **Expect:** pass

**Given**
1. A = W("acme-co").

**When**
- `dao.get_by_slug(db, "acme-co")`, wrapped in `with pytest.raises(TypeError):`.

**Then**
1. raises: `TypeError`.
2. nothing written: nothing written.

### WSP-GS-17 — the start of a slug finds nothing
- **Rules:** `get_by_slug` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = W("acme-co").

**When**
- `result = dao.get_by_slug(db, slug="acme")`.

**Then**
1. returns: `result is None`.

### WSP-GS-18 — the end of a slug finds nothing
- **Rules:** `get_by_slug` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = W("acme-co").

**When**
- `result = dao.get_by_slug(db, slug="co")`.

**Then**
1. returns: `result is None`.

### WSP-GS-19 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_slug` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = W("acme-co").
2. B = W("beta-co").
3. `B.name = "Edited"` (not flushed).

**When**
- `result = dao.get_by_slug(db, slug="acme-co")`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.

## Inherited methods on `workspaces`

### WSP-IN-01 — create from a WorkspaceCreate raises TypeError and adds nothing
- **Rules:** `inherited` N1
- **Kind:** error
- **Expect:** pass

**Given**
1. No workspace has the slug `acme-co`.

**When**
- `dao.create(db, obj_in=WorkspaceCreate(name="Acme", slug="acme-co", billing_email="owner@example.com"))`, wrapped in `with pytest.raises(TypeError) as exc:`.

**Then**
1. raises: `TypeError`.
2. raises: `"'owner_position' is an invalid keyword argument for Workspace" in str(exc.value)`.
3. session: `len(db.new) == 0`.
4. count: `workspaces` has exactly 0 rows with `slug == "acme-co"`.

### WSP-IN-02 — a second row with one slug is refused
- **Rules:** `inherited` N2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = W("acme-co").

**When**
- `dao.create(db, obj_in={"name": "Other", "slug": "acme-co", "subscription_plan_id": A.subscription_plan_id})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. raises: `"ix_workspaces_slug" in str(exc.value.orig)`.
4. count: `workspaces` has exactly 1 row with `slug == "acme-co"`.
5. unchanged: unchanged(A).

### WSP-IN-03 — a row with another slug is stored
- **Rules:** `inherited` N2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = W("acme-co").

**When**
- `result = dao.create(db, obj_in={"name": "Other", "slug": "acme-co-2", "subscription_plan_id": A.subscription_plan_id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `slug == "acme-co-2"`, `name == "Other"`.
3. unchanged: unchanged(A).

### WSP-IN-04 — update of settings replaces the whole value and moves updated_at
- **Rules:** `inherited` N3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = make_workspace(db, slug="acme-co", settings={"a": 1}).
2. `db.refresh(A)`
3. `U0 = A.updated_at`
4. `while utcnow() <= U0: pass` (the clock moves in ticks, so the update must not share the insert's).

**When**
- `result = dao.update(db, db_obj=A, obj_in=WorkspaceUpdate(settings={"b": 2}))`.

**Then**
1. returns: `result is A`.
2. re-read A: `settings == {"b": 2}`.
3. re-read A: `updated_at != U0`.
4. re-read A: `updated_at > created_at`.
5. unchanged: unchanged(A) except `settings`, `updated_at`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Generic behavior of inherited `get`, `get_multi`, `create`, `update`, `remove` | `tests/unit/dao/base.spec.md` / `base.cases.md` | Commit spies of the writers: BASE-C-05, BASE-U-12, BASE-R-02. |
| `get_by_workspace`, `get_by_id_and_workspace` raise `AttributeError` on this model | `tests/unit/dao/base.spec.md` R7, R5 | No `workspace_id` on this table; base covers it. |
| Refusing a taken slug, and the 409 past a race | `WorkspaceManager.create_workspace` | This DAO only finds the row; the refusal and the API's integrity handler belong there. |
| Module singleton `workspace_dao` | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | N1 | The arguments of `WorkspaceCreate` are not in the spec. `name`, `slug`, `billing_email` come from `tests/test_register_timezone.py`. | WSP-IN-01 uses them. A wrong field fails with `ValidationError` before the call. |
| 2 | N3 | The spec names `WorkspaceUpdate` without a module, and does not say what `updated_at` holds at insert. | `app.schemas.workspace` is assumed from `WorkspaceCreate`. WSP-IN-04 uses `!= U0`, which also holds for `None`. |
| 3 | R5 | Names no value for a state that is not `trial`. `"cancelled"` comes from `tests/unit/core/test_deps.py`. "Owner" has no column in the spec. | WSP-GS-13 uses the value. The owner half of R5 has no card of its own: GS-12 has no membership row. |
| 4 | Model facts | Defaults and `ON DELETE CASCADE` are facts of the table, not rules of this DAO. | No card, as in `work_order_approver.cases.md` gap 3. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_slug` | Returns | WSP-GS-01 |
| `get_by_slug` | R1 | WSP-GS-01 |
| `get_by_slug` | R2 | WSP-GS-02, WSP-GS-03, WSP-GS-04, WSP-GS-05, WSP-GS-06, WSP-GS-17, WSP-GS-18 |
| `get_by_slug` | R3 | WSP-GS-07, WSP-GS-08 |
| `get_by_slug` | R4 | WSP-GS-09, WSP-GS-10, WSP-GS-11, WSP-GS-14 |
| `get_by_slug` | R5 | WSP-GS-12, WSP-GS-13 |
| `get_by_slug` | Inputs | WSP-GS-16 |
| `get_by_slug` | Side effects | WSP-GS-14, WSP-GS-15, WSP-GS-19 |
| `inherited` | N1 | WSP-IN-01 |
| `inherited` | N2 | WSP-IN-02, WSP-IN-03 |
| `inherited` | N3 | WSP-IN-04 |
