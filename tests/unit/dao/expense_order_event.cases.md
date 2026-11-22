# Test cases — `app/dao/expense_order_event.py`

> **Spec:** `tests/unit/dao/expense_order_event.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-01; nothing open). Q1 is the owner's answer; it moves no rule of this DAO.
> **Revision:** 1 — the spec did not change. Additive, from `expense_order_event.verify.md` (case-missing Findings 1 … 4; recipes R-1 … R-4): R-1 → EOE-G-19; R-2 → EOE-G-20; R-3 → EOE-G-18 Then 5, 6 (the old lines 5 … 7 move to 7 … 9) and EOE-G-21; R-4 → EOE-G-18 Then 10. No ID retired.
> **Counts:** 21 cases · 21 expected-to-pass · 0 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Depth:** lighter target (skill step 1a): one list read, no write of its own, and no money, stock or order state written.
- **Per callable:** `get_by_order` 21.
- **Expected-to-fail:** none. This module's query has its full order, and no rule here carries a bug tag.
- **Notable design choices:**
  - "Writes nothing" is EOE-G-18, with EOE-G-21 for the empty result: a newer row added and not flushed must stay pending and alone in the session, no write statement is sent, and no lock clause. Readers have no commit spy.
  - Ties both ways: one tie card with no update (the expected row is physically last), one with the lower row updated (physically first). Neither alone rules out physical order.
  - Every filter negative puts the other row where it would change the result: newer than the expected row.
  - The R4 card deletes the parent with raw SQL in its Given, so it proves the cascade and not who may delete.
  - EOE-G-19 gives each tied row its own `event_type`, `description` and performer, so no other column can pass for `id`. EOE-G-20 has an older row with a higher id, one microsecond apart.
  - EOE-G-18 forbids `expense_orders` by name, so neither a join nor a subquery can hide a closed parent's log. The check rests on the Branch map line "no join to the parent", not on a numbered rule alone.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `EOE` = `app/dao/expense_order_event.py`. `G` = get_by_order.

**Actors and fixed values.**
- `dao` = the singleton `expense_order_event_dao` (`from app.dao.expense_order_event import expense_order_event_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `ExpenseOrderEvent` = `app.models.expense_order_event.ExpenseOrderEvent`. `datetime`, `timedelta` = the `datetime` module's classes. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.
- T1 = `datetime(2026, 3, 4, 10, 0, 0)`, T2 = `datetime(2026, 3, 5, 10, 0, 0)`, T3 = `datetime(2026, 3, 6, 10, 0, 0)`.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces and the profile from `make_workspace`, `make_profile` of `tests/unit/factories.py`; the rest built directly, add + flush):
  - W1, W2 = two `workspaces` rows. U1 = a `profiles` row.
  - O1 = `expense_orders` row (`ExpenseOrder`): `workspace_id W1.id`, `expense_number "EO-1"`, `expense_category "factory"`, `created_by U1.id`. O2 = the same, but `expense_number "EO-2"`. O9 = the same as O1, but `workspace_id W2.id`, `expense_number "EO-9"`.
- **event** = `expense_order_events` row built with `ExpenseOrderEvent`: `workspace_id W1.id`, `expense_order_id O1.id`, `event_type "created"`, `description "Logged"`; `metadata_json` and `performed_by` are not passed. The card always gives `created_at`; after the word "but" it lists every other column that differs. `metadata_json None` means the keyword is passed with the value `None`.
- No `expense_order_events` row exists unless the card's Given lists it.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned; the order is part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `expense_order_events` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- **stored_json(X)** = `db.scalar(text("SELECT metadata::text FROM expense_order_events WHERE id = :i"), {"i": X.id})` — `None` for SQL `NULL`, `"null"` for JSON `null`.
- `pending:` lines check the row P after the call, on the object itself; `db.new`, `db.dirty`, `db.deleted` are read from the session after the call, before anything expires it.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `expense_order_events`; `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.


## `ExpenseOrderEventDAO.get_by_order`

### EOE-G-01 — returns a list of the expense order's rows of every event type
- **Rules:** `get_by_order` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T1`, but `event_type "created"`.
2. B = event, `created_at T2`, but `event_type "approved"`.
3. C = event, `created_at T3`, but `event_type "attachment_added"`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.
3. returns: `isinstance(result[0], ExpenseOrderEvent)`.

### EOE-G-02 — a newer row of another expense order is not returned
- **Rules:** `get_by_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. C = event, `created_at T2`, but `expense_order_id O2.id`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### EOE-G-03 — the right expense order under another workspace returns an empty list
- **Rules:** `get_by_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### EOE-G-04 — a newer W2 row on the same expense order is not returned
- **Rules:** `get_by_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. Z = event, `created_at T2`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### EOE-G-05 — a W2 row on an expense order of W1 is returned for W2: only the row's workspace is compared
- **Rules:** `get_by_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = event, `created_at T1`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [Z.id]`.

### EOE-G-06 — a W2 row on an expense order of W1 is not returned for W1
- **Rules:** `get_by_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = event, `created_at T1`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### EOE-G-07 — an unknown expense order id returns an empty list
- **Rules:** `get_by_order` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_order(db, expense_order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### EOE-G-08 — expense_order_id=0 returns an empty list
- **Rules:** `get_by_order` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_order(db, expense_order_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### EOE-G-09 — an unknown workspace returns an empty list
- **Rules:** `get_by_order` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### EOE-G-10 — an expense order with no events returns an empty list
- **Rules:** `get_by_order` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### EOE-G-11 — after a hard delete of the expense order its rows are gone and the call returns an empty list
- **Rules:** `get_by_order` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`.
3. C = event, `created_at T3`, but `expense_order_id O2.id`.
4. `db.execute(text("DELETE FROM expense_orders WHERE id = :i"), {"i": O1.id})`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.
2. count: `db.scalar(text("SELECT count(*) FROM expense_order_events WHERE expense_order_id = :i"), {"i": O1.id}) == 0`.
3. count: `db.scalar(text("SELECT count(*) FROM expense_order_events WHERE expense_order_id = :i"), {"i": O2.id}) == 1`.

### EOE-G-12 — rows are ordered by created_at descending, then id descending
- **Rules:** `get_by_order` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T3`.
3. C = event, `created_at T1`.
4. D = event, `created_at T3`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [D.id, B.id, A.id, C.id]`.

### EOE-G-13 — on a created_at tie with no update the higher id comes first
- **Rules:** `get_by_order` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### EOE-G-14 — on a created_at tie the higher id still comes first after the lower row is updated
- **Rules:** `get_by_order` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2`.
2. B = event, `created_at T2`.
3. `A.description = "Edited"`, then `db.flush()`.
4. `db.expire_all()`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### EOE-G-15 — every matching row is returned: 158 rows give 158
- **Rules:** `get_by_order` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 158 events E1 … E158, built with `add_all`: Ek = event, `created_at` = `T1 + timedelta(minutes=k)`. `newest_first` = the ids of E158, E157, … E1, in that order.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 158`.
2. returns: `ids(result) == newest_first`.

### EOE-G-16 — a row comes back as stored, with its performer
- **Rules:** `get_by_order` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T2`, but `event_type "approved"`, `description "Step done"`, `metadata_json {"status": "DONE", "note": "Shift 1"}`, `performed_by U1.id`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].workspace_id == W1.id`, `result[0].expense_order_id == O1.id`, `result[0].event_type == "approved"`.
3. returns: `result[0].description == "Step done"`, `result[0].created_at == T2`.
4. returns: `result[0].metadata_json == {"status": "DONE", "note": "Shift 1"}`.
5. returns: `result[0].performer.id == U1.id`.

### EOE-G-17 — SQL NULL and JSON null metadata both read back as None, and no performer gives None
- **Rules:** `get_by_order` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. B = event, `created_at T2`, but `metadata_json None`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.
2. returns: `result[0].metadata_json is None`.
3. returns: `result[1].metadata_json is None`.
4. re-read A: `stored_json(A) is None`.
5. re-read B: `stored_json(B) == "null"`.
6. returns: `result[0].performer is None`.

### EOE-G-18 — writes nothing: a newer pending row stays pending and is not returned
- **Rules:** `get_by_order` R7, Side effects, Overview, R1, Branch map
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. `P = ExpenseOrderEvent(workspace_id=W1.id, expense_order_id=O1.id, event_type="created", description="Pending", created_at=T2)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. nothing written: nothing written.
5. pending: `len(db.new) == 1`.
6. pending: `not db.dirty and not db.deleted`.
7. unchanged: unchanged(A).
8. statement: `written == []`.
9. statement: `"FOR" not in sql.upper().split()`.
10. statement: `"expense_orders" not in sql`.

### EOE-G-19 — on a created_at tie id decides, not event_type, description or performer
- **Rules:** `get_by_order` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `U2`, `U3` = two more `profiles` rows (`make_profile`), made after U1, in that order.
2. A = event, `created_at T2`, but `event_type "b"`, `description "b"`, `performed_by U2.id`.
3. B = event, `created_at T2`, but `event_type "a"`, `description "a"`, `performed_by U1.id`.
4. C = event, `created_at T2`, but `event_type "c"`, `description "c"`, `performed_by U3.id`.
5. `db.expire_all()`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.


### EOE-G-20 — one microsecond inside one day decides the order, against id
- **Rules:** `get_by_order` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T2 + timedelta(microseconds=1)`.
2. B = event, `created_at T2`.

**When**
- `result = dao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.


### EOE-G-21 — writes nothing: with an empty result the pending row is still alone in the session
- **Rules:** `get_by_order` R7, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = event, `created_at T1`.
2. `P = ExpenseOrderEvent(workspace_id=W1.id, expense_order_id=O1.id, event_type="created", description="Pending", created_at=T2)`
3. `db.add(P)` (not flushed).

**When**
- `result = dao.get_by_order(db, expense_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.
2. pending: `len(db.new) == 1`.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| R2 — the caller answers 404 for an expense order of another workspace before this method runs | `ExpenseOrderManager.list_events` | This DAO returns the row for its own workspace; the 404 is what keeps it out of a response. |
| FU-1a, Q1 — BUG-1193: the delete writes one `workspace_audit_logs` row; a refused delete writes none; `user_id` is required | `tests/unit/managers/expense_order_manager.spec.md` `delete_expense_order` | The rule and the tag belong to that spec. Here R4 only checks that the rows go with the order. |
| FU-1 — BUG-1192 (HR-16): `log_event` refuses another workspace's expense order, 404 `Expense order with ID <id> not found`, nothing written | `ExpenseOrderManager.log_event` | The rule and the tag belong to that spec. No card here. |
| FU-2 — one profile read per event with a performer (pattern of BUG-1141) | `ExpenseOrderManager.list_events` | Not a rule of this DAO. |
| FU-3 — stored metadata validated by `ExpenseOrderEventMetadata` | `GET /expense-orders/{id}/events/` | Not a rule of this DAO. |
| Generic behavior of inherited `BaseDAO` methods | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not specified here. |
| Notes: keyword-only parameters | none (no rule) | Spec gap 1. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes ("every parameter after `db` is keyword-only") | Stated as a note, not as a rule. | No card, as in `machine_activity_event.cases.md`. |
| 2 | Overview ("takes no lock") | Stands outside the numbered rules. | Covered anyway, as the Overview row of the matrix, by the "writes nothing" card. Its check looks for the word `FOR`, so it covers every lock form. Drop the line if it is not meant as a contract. |
| 3 | Notes, parent `ExpenseOrder` | **Order.** No value for `expense_category`. | `"factory"` is taken from `tests/unit/managers/expense_order_manager.cases.md`, a test-side file, not from this spec. No card depends on it. |
| 4 | `get_by_order` R4 | **Money, order.** The rule names `ExpenseOrderManager.delete_expense_order`, which is not this DAO's, and which changes under its own bug. | The card runs a raw `DELETE` in the Given, so it proves the database's cascade only. It says nothing about who may delete. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_order` | Returns | EOE-G-01 |
| `get_by_order` | R1 | EOE-G-01, EOE-G-02, EOE-G-18 |
| `get_by_order` | R2 | EOE-G-03, EOE-G-04, EOE-G-05, EOE-G-06 |
| `get_by_order` | R3 | EOE-G-07, EOE-G-08, EOE-G-09, EOE-G-10 |
| `get_by_order` | R4 | EOE-G-11 |
| `get_by_order` | R5 | EOE-G-12, EOE-G-13, EOE-G-14, EOE-G-19, EOE-G-20 |
| `get_by_order` | R6 | EOE-G-15 |
| `get_by_order` | R7 | EOE-G-16, EOE-G-17, EOE-G-18, EOE-G-21 |
| `get_by_order` | Overview | EOE-G-18 |
| `get_by_order` | Side effects | EOE-G-18, EOE-G-21 |
| `get_by_order` | Branch map | EOE-G-18 |
