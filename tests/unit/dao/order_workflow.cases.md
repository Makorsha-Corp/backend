# Test cases — `app/dao/order_workflow.py`

> **Spec:** `tests/unit/dao/order_workflow.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open). O1, O2, O3 are the owner's answers.
> **Revision:** 2 — the spec gained N4, BUG-1227 (the owner's answer on Spec gap 2). Additive: OWF-IN-07. Spec gap 2 now names it. No existing Given, When, Then or ID changed, none retired.
> **Revision 1:** the spec did not change. Additive, from `order_workflow.verify.md` (case-missing Findings 1, 2, 3; recipes R-1, R-2, R-3): Finding 1 → OWF-GT-20, GT-21, GT-22; Finding 2 → OWF-GT-23; Finding 3 → OWF-GT-24. Conventions gain the `session:` line. No existing Given, When, Then or ID changed, none retired.
> **Counts:** 31 cases · 29 expected-to-pass · 2 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Per callable:** `get_by_type` 24 · `inherited` 7 (2 bug).
- **Depth:** lighter target (skill step 1a). The DAO only reads and takes no order action; the writes are the base's. The rules that can change an order's meaning are the service's, so they are Deferred (BUG-1215, BUG-1222, BUG-1223), and only N3, the DAO's part of BUG-1222, is carded here. Each input the rules name still gets a card.
- **Expected-to-fail:** BUG-1222 1, strict (OWF-IN-05). IN-06 is its passing half: the spec's Today note says raw SQL already raises 23001. BUG-1227 1, strict (OWF-IN-07): an `append` on type `PFM`.
- **Commit spies:** none. `get_by_type` only reads; the inherited writers are spied by BASE-C-05, BASE-R-02.
- **Notable design choices:**
  - GT-02 is the real row, from `seed_po_workflow`, next to the built ones: the type is `purchase` and its four ids name the workspace's own stages.
  - GT-03 puts the other workspace's row first in `id` order, so a lookup by type alone fails it.
  - GT-15 names status ids that do not exist because R5 says so. The standing `[11, 22, 33]` is plain numbers on purpose: the column has no foreign key and R5 says the contents are not looked at.
  - O3: storing only, as the owner said: GT-16, GT-17 read `allowed_reverts_json` back and nothing obeys it.
  - No order card: `(workspace_id, type)` is unique, so `.first()` has one candidate.
  - No `Author:` lines. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `OWF` = `app/dao/order_workflow.py`. `GT` get_by_type · `IN` inherited `BaseDAO` methods on this model.

**Actors and fixed values.**
- `dao` = the singleton `order_workflow_dao` (`from app.dao.order_workflow import order_workflow_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `OrderWorkflow` = `app.models.order_workflow.OrderWorkflow`. `Status` = `app.models.status.Status`. `PurchaseOrder` = `app.models.purchase_order.PurchaseOrder`. `seed_po_workflow` = `app.db.seed_po_workflow.seed_po_workflow`. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from the defaults below. A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.
- W1, W2 = two `workspaces` rows; U1 = a `profiles` row, from `make_workspace`, `make_profile`. They exist in every test and need no Given line. `make_workspace` seeds nothing: a workspace has no workflow and no status unless the card's Given lists one.
- **workflow** = `OrderWorkflow(workspace_id=W1.id, name="Flow", type="PFM", status_sequence=[11, 22, 33])`; `description` and `allowed_reverts_json` are not passed. After the word "but" the card lists every column that differs.
- **order on F** = a `Status(workspace_id=W1.id, name="Draft", comment="Stage")` S, flushed, then `PurchaseOrder(workspace_id=W1.id, po_number="PO-1", destination_type="storage", destination_id=1, current_status_id=S.id, created_by=U1.id, order_workflow_id=F.id)`.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line). **unchanged(X) except `c`, …** = the same, leaving out the columns named.
- **nothing written** = the number of `order_workflows` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P after the call, on the object itself. `pending: len(db.new) == 1` checks that P is the only object waiting in the session.
- A `session:` line is a check on the session object.
- `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the When: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line.
- `count:` = `SELECT count(*)` through `db.scalar(text(...))`, with the filter stated.
- `remove` emits `LegacyAPIWarning`; warnings are not errors here.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on it.

**Race simulations.** None in this module.

## `DAOOrderWorkflow.get_by_type`

### OWF-GT-01 — returns the row of that type, with the sequence as a list of ints
- **Rules:** `get_by_type` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = workflow, but `type "STM"`.
2. A = workflow.

**When**
- `result = dao.get_by_type(db, workflow_type="PFM", workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, OrderWorkflow)`.
2. returns: `result.id == A.id`.
3. returns: `result.type == "PFM"`, `result.workspace_id == W1.id`.
4. returns: `result.status_sequence == [11, 22, 33]`.
5. returns: `isinstance(result.status_sequence, list)`.
6. returns: `all(isinstance(x, int) for x in result.status_sequence)`.

### OWF-GT-02 — the seeded purchase workflow comes back with its four stages in order
- **Rules:** `get_by_type` R1, Overview
- **Kind:** happy
- **Expect:** pass

**Given**
1. `seed_po_workflow(db, W1.id)`
2. `db.flush()`

**When**
- `result = dao.get_by_type(db, workflow_type="purchase", workspace_id=W1.id)`.

**Then**
1. returns: `result.type == "purchase"`, `result.workspace_id == W1.id`.
2. returns: `len(result.status_sequence) == 4`.
3. returns: `[db.get(Status, i).name for i in result.status_sequence] == ["Draft", "Planning", "Receiving", "Complete"]`.
4. returns: `{db.get(Status, i).workspace_id for i in result.status_sequence} == {W1.id}`.

### OWF-GT-03 — two workspaces with one type: the first gets its own, past an earlier row
- **Rules:** `get_by_type` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = workflow, but `workspace_id W2.id`, `status_sequence [44]`.
2. A = workflow.

**When**
- `result = dao.get_by_type(db, workflow_type="PFM", workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.status_sequence == [11, 22, 33]`.

### OWF-GT-04 — two workspaces with one type: the second gets its own
- **Rules:** `get_by_type` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = workflow.
2. Z = workflow, but `workspace_id W2.id`, `status_sequence [44]`.

**When**
- `result = dao.get_by_type(db, workflow_type="PFM", workspace_id=W2.id)`.

**Then**
1. returns: `result.id == Z.id`.
2. returns: `result.status_sequence == [44]`.

### OWF-GT-05 — a workspace without the type returns None
- **Rules:** `get_by_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow, but `type "STM"`.

**When**
- `result = dao.get_by_type(db, workflow_type="PFM", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OWF-GT-06 — the type under another workspace returns None
- **Rules:** `get_by_type` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = workflow.

**When**
- `result = dao.get_by_type(db, workflow_type="PFM", workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### OWF-GT-07 — workspace_id=0 returns None
- **Rules:** `get_by_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow.

**When**
- `result = dao.get_by_type(db, workflow_type="PFM", workspace_id=0)`.

**Then**
1. returns: `result is None`.

### OWF-GT-08 — lower case does not find an upper-case type
- **Rules:** `get_by_type` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow.

**When**
- `result = dao.get_by_type(db, workflow_type="pfm", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OWF-GT-09 — a leading space finds nothing
- **Rules:** `get_by_type` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow.

**When**
- `result = dao.get_by_type(db, workflow_type=" PFM", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OWF-GT-10 — a trailing space finds nothing
- **Rules:** `get_by_type` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow.

**When**
- `result = dao.get_by_type(db, workflow_type="PFM ", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OWF-GT-11 — % is no wildcard
- **Rules:** `get_by_type` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow.

**When**
- `result = dao.get_by_type(db, workflow_type="P%", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OWF-GT-12 — an empty type returns None
- **Rules:** `get_by_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow.

**When**
- `result = dao.get_by_type(db, workflow_type="", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OWF-GT-13 — a None type returns None
- **Rules:** `get_by_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow.

**When**
- `result = dao.get_by_type(db, workflow_type=None, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OWF-GT-14 — an empty sequence is returned as stored
- **Rules:** `get_by_type` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow, but `status_sequence []`.

**When**
- `result = dao.get_by_type(db, workflow_type="PFM", workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.status_sequence == []`.

### OWF-GT-15 — ids of statuses that do not exist are returned as stored
- **Rules:** `get_by_type` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow, but `status_sequence [999999999, 999999998]`.

**When**
- `result = dao.get_by_type(db, workflow_type="PFM", workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.status_sequence == [999999999, 999999998]`.
3. count: `statuses` has exactly 0 rows with `id == 999999999`.

### OWF-GT-16 — allowed reverts are stored and returned
- **Rules:** `get_by_type` O3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = workflow, but `allowed_reverts_json {"Received": ["Purchased"]}`.

**When**
- `result = dao.get_by_type(db, workflow_type="PFM", workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.allowed_reverts_json == {"Received": ["Purchased"]}`.

### OWF-GT-17 — allowed reverts left out read back as None
- **Rules:** `get_by_type` O3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow.

**When**
- `result = dao.get_by_type(db, workflow_type="PFM", workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.allowed_reverts_json is None`.

### OWF-GT-18 — writes nothing: a pending row stays pending and is not found
- **Rules:** `get_by_type` R2, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = workflow.
2. `P = OrderWorkflow(workspace_id=W1.id, name="Pending", type="PEND", status_sequence=[1])`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_type(db, workflow_type="PEND", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. nothing written: nothing written.
6. unchanged: unchanged(A).
7. statement: `written == []`.

### OWF-GT-19 — writes nothing: a read that finds its row leaves the session as it was
- **Rules:** `get_by_type` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = workflow.
2. `P = OrderWorkflow(workspace_id=W1.id, name="Pending", type="PEND", status_sequence=[1])`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_type(db, workflow_type="PFM", workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. nothing written: nothing written.
5. statement: `written == []`.

### OWF-GT-20 — the start of a type finds nothing
- **Rules:** `get_by_type` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow.

**When**
- `result = dao.get_by_type(db, workflow_type="PF", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OWF-GT-21 — the end of a type finds nothing
- **Rules:** `get_by_type` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow.

**When**
- `result = dao.get_by_type(db, workflow_type="FM", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OWF-GT-22 — _ is no wildcard
- **Rules:** `get_by_type` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow.

**When**
- `result = dao.get_by_type(db, workflow_type="P_M", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OWF-GT-23 — a stored type with a space is not found: the stored side is not trimmed
- **Rules:** `get_by_type` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow, but `type " PFM"`.

**When**
- `result = dao.get_by_type(db, workflow_type="PFM", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OWF-GT-24 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_type` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = workflow.
2. B = workflow, but `type "STM"`.
3. `B.description = "Edited"` (not flushed).

**When**
- `result = dao.get_by_type(db, workflow_type="PFM", workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.

## Inherited methods on `order_workflows`

### OWF-IN-01 — a second row of one workspace and type is refused
- **Rules:** `inherited` N1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = workflow.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": "New", "type": "PFM", "status_sequence": [1]})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. raises: `"uq_order_workflows_workspace_type" in str(exc.value.orig)`.
4. count: `order_workflows` has exactly 1 row with `workspace_id == W1.id` and `type == "PFM"`.
5. unchanged: unchanged(A).

### OWF-IN-02 — one type in another workspace is stored
- **Rules:** `inherited` N1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = workflow.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W2.id, "name": "New", "type": "PFM", "status_sequence": [1]})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W2.id`, `type == "PFM"`, `status_sequence == [1]`.
3. unchanged: unchanged(A).

### OWF-IN-03 — a second type in one workspace is stored
- **Rules:** `inherited` N1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = workflow.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "New", "type": "STM", "status_sequence": [1]})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W1.id`, `type == "STM"`.
3. unchanged: unchanged(A).

### OWF-IN-04 — status_sequence=None is refused
- **Rules:** `inherited` N2
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no workflow.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": "New", "type": "PFM", "status_sequence": None})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23502"`.
3. raises: `"status_sequence" in str(exc.value.orig)`.
4. count: `order_workflows` has exactly 0 rows with `workspace_id == W1.id`.

### OWF-IN-05 — removing a workflow a purchase order uses is refused
- **Rules:** `inherited` N3 [BUG-1222]
- **Kind:** bug
- **Expect:** xfail BUG-1222
- **Fails today on:** Then 1 (no error is raised: the ORM empties `order_workflow_id`, then the delete succeeds)

**Given**
1. F = workflow.
2. O = order on F.
3. `db.expire_all()`

**When**
- `dao.remove(db, id=F.id)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23001"`.
3. count: `order_workflows` has exactly 1 row with `id == F.id`.
4. re-read O: `order_workflow_id == F.id`.

### OWF-IN-06 — the same delete in raw SQL raises 23001 and changes nothing
- **Rules:** `inherited` N3
- **Kind:** error
- **Expect:** pass

**Given**
1. F = workflow.
2. O = order on F.

**When**
- `db.execute(text("DELETE FROM order_workflows WHERE id = :id"), {"id": F.id})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23001"`.
3. count: `order_workflows` has exactly 1 row with `id == F.id`.
4. re-read O: `order_workflow_id == F.id`.

### OWF-IN-07 — a status_sequence changed in place is saved by the next flush
- **Rules:** `inherited` N4 [BUG-1227]
- **Kind:** bug
- **Expect:** xfail BUG-1227
- **Fails today on:** Then 1 (no error is raised and nothing is saved: the list reads back `[1, 2]`)

**Given**
1. A = workflow, but `status_sequence [1, 2]`.
2. `db.refresh(A)`

**When**
- `A.status_sequence.append(3)`, then `db.flush()`.

**Then**
1. re-read A: `status_sequence == [1, 2, 3]`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-1222 (O1) — `DELETE` of a workflow in use answers 400 with the orders listed; the `purchase` row answers 400 even with no orders; the ORM's nulling is turned off; a script restores `order_workflow_id` | `OrderWorkflowService`, `DELETE /order-workflows/{id}/`; the repair script | **Order.** N3 here is the DAO's part only. |
| BUG-1223 (O2) — `PUT` carrying `status_sequence` on a `purchase` row answers 400, nothing written | `OrderWorkflowService` | **Order.** `ensure_po_workflow_record` stays the only writer. |
| BUG-1215 (HR-16) — each id of `status_sequence` must be a status of the caller's workspace, otherwise 404 | `OrderWorkflowService` | **Order.** R5 here stays raw. |
| BUG-1217 — no lower bound on `limit` | `GET /order-workflows/` | Endpoint rule. |
| HR-1 on `name`; `type` is unvalidated text; HR-6 list order | `OrderWorkflowService`, `app/schemas/order_workflow.py` | FU-1. |
| FU-2 — a copy of `terminal_status_ids_by_workflow` | `PurchaseOrderService`, `app/utils/order_workflow_terminal.py` | **Order.** A fix to one must reach the other. |
| Generic behavior of inherited methods | `tests/unit/dao/base.spec.md` / `base.cases.md` | Commit spies: BASE-C-05, BASE-U-12, BASE-R-02. |
| Module singleton `order_workflow_dao` | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes: keyword-only parameters | Stated as a note, not as a rule. | No card, as in `work_order_approver.cases.md` gap 1. |
| 2 | Model facts | **Order.** "A list changed in place is not saved" was verified and stated as a fact, not a rule. The sequence decides which orders count as finished. | Closed by the owner: rule N4, BUG-1227, OWF-IN-07. The rule's other named change, item assignment, has no card of its own. |
| 3 | Notes, N3 | **Order.** The spec gives `PurchaseOrder`'s columns, not its module or a `destination_type` value. `app.models.purchase_order` and `"storage"` come from `tests/unit/dao/test_purchase_order_event.py`. | The `order on F` line of Conventions uses them. |
| 4 | Overview, O1 | **Order.** The four stage names and their order are in `status.spec.md` O1, not here. The spec does not say whether `seed_po_workflow` flushes. | OWF-GT-02 takes the names from there and flushes itself. |
| 5 | O3 | No rule number; the resolution says "nothing to test beyond storing it". | Listed as O3 in the matrix. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_type` | Returns | OWF-GT-01 |
| `get_by_type` | R1 | OWF-GT-01, OWF-GT-02 |
| `get_by_type` | R2 | OWF-GT-03, OWF-GT-04, OWF-GT-05, OWF-GT-06, OWF-GT-07, OWF-GT-18 |
| `get_by_type` | R3 | OWF-GT-08, OWF-GT-09, OWF-GT-10, OWF-GT-11, OWF-GT-20, OWF-GT-21, OWF-GT-22, OWF-GT-23 |
| `get_by_type` | R4 | OWF-GT-12, OWF-GT-13 |
| `get_by_type` | R5 | OWF-GT-14, OWF-GT-15 |
| `get_by_type` | O3 | OWF-GT-16, OWF-GT-17 |
| `get_by_type` | Overview | OWF-GT-02 |
| `get_by_type` | Side effects | OWF-GT-18, OWF-GT-19, OWF-GT-24 |
| `inherited` | N1 | OWF-IN-01, OWF-IN-02, OWF-IN-03 |
| `inherited` | N2 | OWF-IN-04 |
| `inherited` | N3 | OWF-IN-06 |
| `inherited` | N3 [BUG-1222] | OWF-IN-05 |
| `inherited` | N4 [BUG-1227] | OWF-IN-07 |
