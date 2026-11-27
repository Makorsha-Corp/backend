# Test cases — `app/dao/status.py`

> **Spec:** `tests/unit/dao/status.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02). O1 and O3 are the owner's answers. **O2 is boxed, not decided: no card rests on it.**
> **Counts:** 12 cases · 10 expected-to-pass · 2 expected-to-fail (bugs) · 11 deferred

## Reviewer summary
- **Per callable:** `create` 8 (2 bug) · `remove` 4.
- **Depth:** lighter target (skill step 1a). An empty class on a reference table. It writes no stock, money or order state of its own; R4 is what the base does on this model.
- **Boxed:** O2 is not decided, and **no card rests on it**. No card reads a default status id; RM-03, RM-04 name their own status row. BUG-1018 and BUG-1019 are Deferred entries that keep their open question.
- **Expected-to-fail:** BUG-1221 2, both strict (STS-CR-07, CR-08). BUG-1220's rule is the service's, so Deferred.
- **Commit spies:** none. `create` and `remove` are spied by BASE-C-05, BASE-R-02, and this class adds no code.
- **Notable design choices:**
  - CR-05, CR-06 are the other sides of BUG-1221: the same name elsewhere and another name here, stored today and with the index.
  - RM-03, RM-04 hold both error codes of R4, ORM and raw SQL. Only one kind of order is built, the one the spec's Notes give: purchase and sales orders have the same foreign key.
  - No `Author:` lines. Race simulations: none.
- **Needs a decision:** None here. O2 stays with the owner.

## Conventions for this module

**IDs.** `STS` = `app/dao/status.py`, an empty class. `CR` inherited `create` · `RM` inherited `remove`. The rules of this spec have no method of their own, so a Rules line names the inherited method.

**Actors and fixed values.**
- `dao` = the singleton `status_dao` (`from app.dao.status import status_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `Status` = `app.models.status.Status`. `StatusCreate` = the schema of `app.schemas.status`. `OrderWorkflow` = `app.models.order_workflow.OrderWorkflow`. `TransferOrder` = `app.models.transfer_order.TransferOrder`. `text` = `sqlalchemy.text`.

**Externals.** None. Nothing is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from the defaults below. A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.
- W1, W2 = two `workspaces` rows, U1 = a `profiles` row, from `make_workspace`, `make_profile`; they exist in every test and need no Given line. Neither is seeded: a workspace has no status unless the card's Given lists one.
- **status** = `Status(workspace_id=W1.id, name="Feat", comment="A note")`. After the word "but" the card lists every column that differs.
- **Never** give two rows of one workspace one name, or names that differ only in case or outer spaces, except in the cards about exactly that: BUG-1221's index would make the Given fail.
- **transfer on S** = `TransferOrder(workspace_id=W1.id, transfer_number="TO-1", source_location_type="storage", source_location_id=1, destination_location_type="storage", destination_location_id=2, current_status_id=S.id, created_by=U1.id)`. `current_status_id` is always the card's own row, never a default.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line). **unchanged(X) except `c`, …** = the same, leaving out the columns named.
- `re-read result` = the same, for the row the call returned.
- `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the When: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line.
- `count:` = `SELECT count(*)` through `db.scalar(text(...))`, with the filter stated.
- `remove` emits `LegacyAPIWarning`; warnings are not errors here.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Race simulations.** None in this module.

## Inherited `create` on `statuses`

### STS-CR-01 — a StatusCreate cannot create: no workspace_id
- **Rules:** `create` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No `statuses` row has `name "Feat"`.

**When**
- `dao.create(db, obj_in=StatusCreate(name="Feat", comment="A note"))`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23502"`.
3. raises: `"workspace_id" in str(exc.value.orig)`.
4. count: `statuses` has exactly 0 rows with `name == "Feat"`.

### STS-CR-02 — a dict with workspace_id, name and comment is stored
- **Rules:** `create` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no status.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "Feat", "comment": "A note"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W1.id`, `name == "Feat"`, `comment == "A note"`.
3. count: `statuses` has exactly 1 row with `workspace_id == W1.id`.

### STS-CR-03 — a dict without comment is refused
- **Rules:** `create` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no status.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": "Feat"})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23502"`.
3. raises: `"comment" in str(exc.value.orig)`.
4. count: `statuses` has exactly 0 rows with `workspace_id == W1.id`.

### STS-CR-04 — a dict without name is refused
- **Rules:** `create` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no status.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "comment": "A note"})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23502"`.
3. raises: `"name" in str(exc.value.orig)`.
4. count: `statuses` has exactly 0 rows with `workspace_id == W1.id`.

### STS-CR-05 — the same name in another workspace is stored
- **Rules:** `create` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W2.id, "name": "Feat", "comment": "Other"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W2.id`, `name == "Feat"`.
3. unchanged: unchanged(A).

### STS-CR-06 — another name in the same workspace is stored
- **Rules:** `create` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "Feat two", "comment": "Other"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W1.id`, `name == "Feat two"`.
3. unchanged: unchanged(A).

### STS-CR-07 — a second row of one name in one workspace is refused
- **Rules:** `create` R2a [BUG-1221]
- **Kind:** bug
- **Expect:** xfail BUG-1221
- **Fails today on:** Then 1 (no error is raised: the second row is stored)

**Given**
1. A = status.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": "Feat", "comment": "Other"})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `statuses` has exactly 1 row with `workspace_id == W1.id` and `name == "Feat"`.
4. unchanged: unchanged(A).

### STS-CR-08 — the compare is case-insensitive after trimming
- **Rules:** `create` R2b [BUG-1221]
- **Kind:** bug
- **Expect:** xfail BUG-1221
- **Fails today on:** Then 1 (no error is raised: both rows are stored)

**Given**
1. A = status.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": " feat ", "comment": "Other"})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `statuses` has exactly 1 row with `workspace_id == W1.id`.
4. unchanged: unchanged(A).

## Inherited `remove` on `statuses`

### STS-RM-01 — a status no order uses is deleted
- **Rules:** `remove` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = status.
2. B = status, but `name "Done"`.

**When**
- `result = dao.remove(db, id=A.id)`.

**Then**
1. returns: `result.id == A.id`.
2. count: `statuses` has exactly 0 rows with `id == A.id`.
3. unchanged: unchanged(B).

### STS-RM-02 — an id listed in a status_sequence stays there, and nothing else changes
- **Rules:** `remove` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = status.
2. B = status, but `name "Done"`.
3. `F = OrderWorkflow(workspace_id=W1.id, name="Flow", type="purchase", status_sequence=[A.id, B.id])`, added and flushed.
4. `seq = [A.id, B.id]`

**When**
- `result = dao.remove(db, id=A.id)`.

**Then**
1. returns: `result.id == A.id`.
2. count: `statuses` has exactly 0 rows with `id == A.id`.
3. re-read F: `status_sequence == seq`.
4. unchanged: unchanged(F).
5. unchanged: unchanged(B).

### STS-RM-03 — a status an order uses raises 23502 on current_status_id, and nothing is deleted
- **Rules:** `remove` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. A = status.
2. T = transfer on A.
3. `db.expire_all()`

**When**
- `dao.remove(db, id=A.id)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23502"`.
3. raises: `"current_status_id" in str(exc.value.orig)`.
4. count: `statuses` has exactly 1 row with `id == A.id`.
5. re-read T: `current_status_id == A.id`.

### STS-RM-04 — the same delete in raw SQL raises 23001
- **Rules:** `remove` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. A = status.
2. T = transfer on A.

**When**
- `db.execute(text("DELETE FROM statuses WHERE id = :id"), {"id": A.id})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23001"`.
3. count: `statuses` has exactly 1 row with `id == A.id`.
4. re-read T: `current_status_id == A.id`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-1220 (O1) — rename or delete of a stage status, or one in a `status_sequence`, answers 400 naming the workflow; a `comment` edit is allowed; this check runs before BUG-1218's | `StatusService`, `/statuses/` (not yet specified) | `remove` R3 here stays raw: the row goes and the sequence keeps the id. |
| BUG-1221 — a duplicate through the API answers 409; a script cleans stored duplicates and repoints orders and `status_sequence` | `StatusService`; the clean-up script | The DAO raises `IntegrityError`; the rest is not this DAO's. |
| BUG-1018, BUG-1019 — **O2 boxed, not decided**: which status replaces the fixed ids | `TransferOrderManager`, `POST /sales-orders/` | No rule yet. Nothing can be tested until the owner decides. |
| BUG-035 — statuses API unscoped; 13 rows per workspace against a cap of 100 | `StatusService` | FU-1 of the spec. |
| BUG-1217 — `GET /statuses/` has no lower bound on `limit` (HR-7) | `/statuses/` | Endpoint rule. |
| BUG-1218 — a refused delete names nothing | `StatusService` | The owner's refusal rule. |
| HR-1 — `StatusCreate` has no trim or blank check | `app/schemas/status.py` | Schema rule, FU-1. |
| FU-2 — `_format_field_value` reads the status raw (HR-16); `.first()` by name | `PurchaseOrderManager` | Read, not run; no bug needed once BUG-1221's index exists. |
| BUG-100, BUG-101, and `get`, `get_multi`, `remove` with no workspace filter | `tests/unit/dao/base.spec.md` / `base.cases.md` | Base rules, intended at the base. |
| FU-3 — base `remove` R4 on real models with a backref | `tests/unit/dao/base.spec.md` | For that spec's owner: RM-03 shows the different error here. |
| Module singleton `status_dao` | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | R1 | The spec names `StatusCreate` without a module or fields. `app.schemas.status` is assumed; `name`, `comment` come from R2. No test uses the class yet. | STS-CR-01 only. A wrong path fails at import, in every test of the file. |
| 2 | Notes, R4 | **Order.** The spec gives `TransferOrder`'s columns, not its module or the location values. `app.models.transfer_order` and `"storage"` come from `tests/unit/dao/test_transfer_order_event.py`. | The `transfer on S` line of Conventions uses them. |
| 3 | R2 | Only a missing `comment` is spelled out. A missing `name` is read from "needs `workspace_id`, `name` and `comment`" and the Model facts. | STS-CR-04 rests on that reading. |
| 4 | O2 | **Order.** Boxed by the owner, so BUG-1018 and BUG-1019 have no intended value. | No card, by instruction. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create` | R1 | STS-CR-01, STS-CR-02 |
| `create` | R2 | STS-CR-02, STS-CR-03, STS-CR-04, STS-CR-05, STS-CR-06 |
| `create` | R2a [BUG-1221] | STS-CR-07 |
| `create` | R2b [BUG-1221] | STS-CR-08 |
| `remove` | R3 | STS-RM-01, STS-RM-02 |
| `remove` | R4 | STS-RM-03, STS-RM-04 |
