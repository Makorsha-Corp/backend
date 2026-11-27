# Test cases — `app/dao/invoice_event.py`

> **Spec:** `tests/unit/dao/invoice_event.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1 was decided by Claude under the reviewer's delegation; BUG-638 is reused from the account invoice manager spec.
> **Counts:** 29 cases · 27 expected-to-pass · 2 expected-to-fail (bugs) · 4 deferred

## Reviewer summary
- **Per callable:** `create_event` 14 · `get_by_invoice` 15 (2 bug).
- **Depth:** lighter target (skill step 1a). An append-only history: one insert, one read. Amounts only travel inside `metadata` as strings; nothing here computes money or changes invoice state.
- **Expected-to-fail:** BUG-638 2: IEV-GI-09 non-strict (tie reordered after an update), IEV-GI-10 strict (SQL recorder: `id` after `created_at` in the `ORDER BY`). IEV-GI-08 is the passing companion: newest first by `created_at`, with an older row holding the higher id and descriptions that do not rise with the time.
- **Commit spies:** `create_event` 1 (IEV-CE-14).
- **Notable design choices:**
  - `created_at` is a Python default bound at import (no patch reaches it). Read cards set `created_at` on the row they build; IEV-CE-02 checks the default against the database's real clock (`clock_timestamp()`), within 5 seconds (Spec gap 1).
  - R5 ("the invoice's state is not looked at"): the spec does not give the invoice's state column, so no voided invoice can be built (Spec gap 2). IEV-GI-13 covers it from the other side: the query does not read `account_invoices` at all.
  - The deleted-performer card deletes the profile row with SQL inside the test transaction; `ON DELETE SET NULL` then clears `performed_by`.
- **Needs a decision:** None blocking. See Spec gaps 1, 2.

## Conventions for this module

**IDs.** `IEV` = `app/dao/invoice_event.py`. `CE` create_event · `GI` get_by_invoice.

**Names.**
- `dao` = the singleton `invoice_event_dao` (`from app.dao.invoice_event import invoice_event_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `InvoiceEvent` = `app.models.invoice_event.InvoiceEvent`. `Account` = `app.models.account.Account`. `AccountInvoice` = the account invoice model (`app.models.account_invoice.AccountInvoice`). `IntegrityError`, `DataError`, `StatementError` = `sqlalchemy.exc` classes. `text` = `sqlalchemy.text`. `Decimal` = `decimal.Decimal`. `date`, `datetime`, `timedelta` = the `datetime` module's classes.
- MISSING = `999999999`: an id that no row of any table has.
- T10, T11, T12 = `datetime(2026, 3, 4, 10, 0, 0)`, `datetime(2026, 3, 4, 11, 0, 0)`, `datetime(2026, 3, 4, 12, 0, 0)` — naive.

**Standing rows** (exist in every test, no Given line; inserted and flushed in this order):
- W1, W2 = two `workspaces` rows (`make_workspace`). U1 = a `profiles` row (`make_profile`) with `name "Rahim"`; U2 = the same, with `name "Karim"`.
- AC1 = `Account(workspace_id=W1.id, name="Acme")`; AC9 = `Account(workspace_id=W2.id, name="Far")`.
- INV1 = `AccountInvoice(workspace_id=W1.id, account_id=AC1.id, invoice_type="payable", invoice_amount=100, invoice_date=date(2026, 3, 1))`; INV2 = the same as INV1; INV9 = the same, but `workspace_id W2.id`, `account_id AC9.id`.

**Given rows.** Inserted directly (never through `dao`), flushed one at a time in the order written, so ids rise in that order. The session does not autoflush.
- **event** = `InvoiceEvent(workspace_id=W1.id, invoice_id=INV1.id, event_type="created", description="Invoice created", performed_by=None, metadata_json=None)`; the card always gives `created_at`; after "but" it lists every other column that differs. No event exists unless the Given lists it.
- **bumpE(X)** = `db.execute(text("UPDATE invoice_events SET description = description || '!' WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`.
- **seqscan** = run `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`, in this order.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.

**Named checks.**
- **ids(result)** = `[r["id"] for r in result]` — in the order returned; the order is part of the check.
- **KEYS** = `{"id", "workspace_id", "invoice_id", "event_type", "description", "metadata_json", "performed_by", "performed_by_name", "created_at"}`.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **stored_json(X)** = `db.scalar(text("SELECT metadata_json::text FROM invoice_events WHERE id = :i"), {"i": X.id})`. **is_sql_null(X)** = `db.scalar(text("SELECT metadata_json IS NULL FROM invoice_events WHERE id = :i"), {"i": X.id})`.
- **UTC_CLOCK** = `db.scalar(text("SELECT clock_timestamp() AT TIME ZONE 'UTC'"))`, read after the call: the real moment in UTC, naive.
- **nothing written** = the number of `invoice_events` rows (all workspaces) equals its value before the call.
- `pending:` lines check the session after the call, before anything expires it; they come before `nothing written:` lines.
- `raises: E` = wrap the call: `with pytest.raises(E) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. Further `raises:` lines are assertions on `exc.value`, one per line.
- **rolled back** = `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); "inside the savepoint" checks first; then `sp.rollback()` and the "after the savepoint rollback" checks.

**xfail cards.** `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. The assertion is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `invoice_events`; `order_part` = the text of `sql` after its `ORDER BY`; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`.

**Externals.** None. Nothing is mocked. **Race simulations.** None.

## `InvoiceEventDAO.create_event`

### IEV-CE-01 — a row is created with every given value
- **Rules:** `create_event` R1, R2, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. No event exists.

**When**
- `result = dao.create_event(db, workspace_id=W1.id, invoice_id=INV1.id, event_type="payment_recorded", description="Payment recorded", performed_by=U1.id, metadata={"amount": "40.00", "method": "cash"})`.

**Then**
1. returns: `isinstance(result, InvoiceEvent)`.
2. returns: `result.id is not None`.
3. re-read result: `workspace_id == W1.id`, `invoice_id == INV1.id`, `performed_by == U1.id`.
4. re-read result: `event_type == "payment_recorded"`, `description == "Payment recorded"`.
5. re-read result: `metadata_json == {"amount": "40.00", "method": "cash"}`.
6. count: `invoice_events` has exactly 1 row with `invoice_id == INV1.id`.

### IEV-CE-02 — created_at is the real moment in UTC, naive
- **Rules:** `create_event` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`

**When**
- `result = dao.create_event(db, workspace_id=W1.id, invoice_id=INV1.id, event_type="created", description="Invoice created")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `created_at.tzinfo is None`.
3. re-read result: `abs(UTC_CLOCK - created_at) < timedelta(seconds=5)`.

### IEV-CE-03 — performed_by and metadata default to None; None is stored as JSON null
- **Rules:** `create_event` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No event exists.

**When**
- `result = dao.create_event(db, workspace_id=W1.id, invoice_id=INV1.id, event_type="created", description="Invoice created")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `performed_by is None`, `metadata_json is None`.
3. re-read result: `stored_json(result) == "null"`.
4. re-read result: `is_sql_null(result) is False`.

### IEV-CE-04 — a list in metadata is stored and read back as given
- **Rules:** `create_event` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No event exists.

**When**
- `result = dao.create_event(db, workspace_id=W1.id, invoice_id=INV1.id, event_type="items_synced", description="Items synced", metadata=[{"line": 1}, "x", 2])`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `metadata_json == [{"line": 1}, "x", 2]`.

### IEV-CE-05 — an empty description and a 50-character event type are stored
- **Rules:** `create_event` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No event exists.

**When**
- `result = dao.create_event(db, workspace_id=W1.id, invoice_id=INV1.id, event_type="e" * 50, description="")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `event_type == "e" * 50`, `description == ""`.

### IEV-CE-06 — an empty event type is stored
- **Rules:** `create_event` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No event exists.

**When**
- `result = dao.create_event(db, workspace_id=W1.id, invoice_id=INV1.id, event_type="", description="Invoice created")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `event_type == ""`.

### IEV-CE-07 — the invoice's workspace is not compared: a row is stored under another workspace
- **Rules:** `create_event` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No event exists.

**When**
- `result = dao.create_event(db, workspace_id=W2.id, invoice_id=INV1.id, event_type="created", description="Invoice created")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W2.id`, `invoice_id == INV1.id`.

### IEV-CE-08 — an event type of 51 characters raises DataError 22001 and saves nothing
- **Rules:** `create_event` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No event exists.

**When**
- `dao.create_event(db, workspace_id=W1.id, invoice_id=INV1.id, event_type="e" * 51, description="Invoice created")`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "22001"`.
2. nothing written: nothing written.

### IEV-CE-09 — description None raises IntegrityError 23502 and saves nothing
- **Rules:** `create_event` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No event exists.

**When**
- `dao.create_event(db, workspace_id=W1.id, invoice_id=INV1.id, event_type="created", description=None)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23502"`.
2. nothing written: nothing written.

### IEV-CE-10 — an unknown invoice raises IntegrityError 23503 and saves nothing
- **Rules:** `create_event` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No event exists.

**When**
- `dao.create_event(db, workspace_id=W1.id, invoice_id=MISSING, event_type="created", description="Invoice created")`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

### IEV-CE-11 — an unknown performer raises IntegrityError 23503 and saves nothing
- **Rules:** `create_event` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No event exists.

**When**
- `dao.create_event(db, workspace_id=W1.id, invoice_id=INV1.id, event_type="created", description="Invoice created", performed_by=MISSING)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

### IEV-CE-12 — an unknown workspace raises IntegrityError 23503 and saves nothing
- **Rules:** `create_event` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No event exists.

**When**
- `dao.create_event(db, workspace_id=MISSING, invoice_id=INV1.id, event_type="created", description="Invoice created")`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

### IEV-CE-13 — a Decimal in metadata raises StatementError wrapping TypeError and saves nothing
- **Rules:** `create_event` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No event exists.

**When**
- `dao.create_event(db, workspace_id=W1.id, invoice_id=INV1.id, event_type="payment_recorded", description="Payment recorded", metadata={"amount": Decimal("40.00")})`, inside the wrap of `raises: StatementError`.

**Then**
1. raises: `isinstance(exc.value.orig, TypeError)`.
2. nothing written: nothing written.

### IEV-CE-14 — flushed, not committed: a rollback removes the row
- **Rules:** `create_event` R5, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No event exists.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.create_event(db, workspace_id=W1.id, invoice_id=INV1.id, event_type="created", description="Invoice created")`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `invoice_events` has exactly 1 row with `invoice_id == INV1.id`.
3. count: after the savepoint rollback, `invoice_events` has 0 rows with `invoice_id == INV1.id`.
4. mock called: the `db.commit` spy was never called.

## `InvoiceEventDAO.get_by_invoice`

### IEV-GI-01 — returns a list of dicts with exactly the stated keys and the stored values
- **Rules:** `get_by_invoice` R1, R4, R6, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T10`, but `event_type "payment_recorded"`, `description "Payment recorded"`, `performed_by U1.id`, `metadata_json {"amount": "40.00"}`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=INV1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id]`.
3. returns: `set(result[0].keys()) == KEYS`.
4. returns: `result[0]["workspace_id"] == W1.id`, `result[0]["invoice_id"] == INV1.id`.
5. returns: `result[0]["event_type"] == "payment_recorded"`, `result[0]["description"] == "Payment recorded"`.
6. returns: `result[0]["metadata_json"] == {"amount": "40.00"}`.
7. returns: `result[0]["performed_by"] == U1.id`, `result[0]["performed_by_name"] == "Rahim"`.
8. returns: `result[0]["created_at"] == T10`.
9. returns: `result[0]["created_at"].tzinfo is None`.

### IEV-GI-02 — another invoice's events are not returned
- **Rules:** `get_by_invoice` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T10`.
2. B = event, `created_at T12`, but `invoice_id INV2.id`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=INV1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### IEV-GI-03 — an event of this invoice stored under another workspace is not returned
- **Rules:** `get_by_invoice` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = event, `created_at T12`, but `workspace_id W2.id`.
2. A = event, `created_at T10`.
3. Z2 = event, `created_at T11`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=INV1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### IEV-GI-04 — asking with that other workspace returns only the event stored under it
- **Rules:** `get_by_invoice` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = event, `created_at T10`.
2. Z = event, `created_at T11`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=INV1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [Z.id]`.

### IEV-GI-05 — the other workspace's own invoice is not returned when asking with W1
- **Rules:** `get_by_invoice` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = event, `created_at T10`, but `workspace_id W2.id`, `invoice_id INV9.id`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=INV9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### IEV-GI-06 — an unknown invoice id returns an empty list
- **Rules:** `get_by_invoice` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T10`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### IEV-GI-07 — invoice id 0 returns an empty list
- **Rules:** `get_by_invoice` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T10`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### IEV-GI-08 — newest first by created_at, also when the older event has the higher id
- **Rules:** `get_by_invoice` R3 (the part that holds today)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = event, `created_at T11`, but `description "b"`.
2. B = event, `created_at T12`, but `description "a"`.
3. C = event, `created_at T10`, but `description "c"`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=INV1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id, C.id]`.

### IEV-GI-09 — events of one time come back highest id first, also after the lowest was updated
- **Rules:** `get_by_invoice` R3 [BUG-638]
- **Kind:** bug
- **Expect:** xfail BUG-638 (non-strict)
- **Fails today on:** Then 2 (no tie-break; the updated lowest id moves by physical order)

**Given**
1. A = event, `created_at T11`.
2. B = event, `created_at T11`.
3. C = event, `created_at T11`.
4. D = event, `created_at T12`.
5. seqscan.
6. bumpE(A).

**When**
- `result = dao.get_by_invoice(db, invoice_id=INV1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [D.id, C.id, B.id, A.id]`.

### IEV-GI-10 — the query orders by created_at, then id, both descending
- **Rules:** `get_by_invoice` R3 [BUG-638]
- **Kind:** bug
- **Expect:** xfail BUG-638
- **Fails today on:** Then 3 (the query orders by `created_at` alone)

**Given**
1. A = event, `created_at T10`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_invoice(db, invoice_id=INV1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"invoice_events.created_at" in order_part`.
3. statement: `"invoice_events.id" in order_part`.
4. statement: `order_part.index("invoice_events.created_at") < order_part.index("invoice_events.id")`.
5. statement: `order_part.upper().count("DESC") == 2`.

### IEV-GI-11 — every event is returned: 201 give 201
- **Rules:** `get_by_invoice` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 201 events E1 … E201, built with `add_all` and flushed: Ek = event, `created_at` = `T10 + timedelta(minutes=k)`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=INV1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 201`.
2. returns: `result[0]["id"] == E201.id`.

### IEV-GI-12 — no performer: performed_by and performed_by_name are None
- **Rules:** `get_by_invoice` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = event, `created_at T10`. (`performed_by None`.)

**When**
- `result = dao.get_by_invoice(db, invoice_id=INV1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0]["performed_by"] is None`.
3. returns: `result[0]["performed_by_name"] is None`.

### IEV-GI-13 — the performer's current name is shown; a deleted performer gives None
- **Rules:** `get_by_invoice` R4 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = event, `created_at T11`, but `performed_by U1.id`.
2. B = event, `created_at T10`, but `performed_by U2.id`.
3. `db.execute(text("UPDATE profiles SET name = 'Rahim Uddin' WHERE id = :i"), {"i": U1.id})`
4. `db.execute(text("DELETE FROM profiles WHERE id = :i"), {"i": U2.id})`, then `db.expire_all()`.

**When**
- `result = dao.get_by_invoice(db, invoice_id=INV1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.
2. returns: `result[0]["performed_by"] == U1.id`, `result[0]["performed_by_name"] == "Rahim Uddin"`.
3. returns: `result[1]["performed_by"] is None`, `result[1]["performed_by_name"] is None`.

### IEV-GI-14 — the invoice row is not read: no join to account_invoices
- **Rules:** `get_by_invoice` R5 (P1; Spec gap 2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = event, `created_at T10`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_invoice(db, invoice_id=INV1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"account_invoices" not in sql`.

### IEV-GI-15 — writes nothing: a pending event stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_invoice` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = event, `created_at T10`.
2. B = event, `created_at T10`, but `invoice_id INV2.id`.
3. `B.description = "Edited"` (not flushed).
4. `P = InvoiceEvent(workspace_id=W1.id, invoice_id=INV1.id, event_type="created", description="Pending", created_at=T12)`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_invoice(db, invoice_id=INV1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. nothing written: nothing written.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| HR-16 — `_log_event` passes the invoice's own workspace | `AccountInvoiceManager._log_event` (account invoice manager spec) | `create_event` stores what it is given (IEV-CE-07). |
| P1 — the events endpoint answers 404 for an invoice not in the workspace | `AccountInvoiceManager.get_events` | The DAO returns whatever matches. |
| BUG-638 at the manager level (`get_events` order) | account invoice manager cases | The fix sits in this file (IEV-GI-09, GI-10). |
| Inherited `BaseDAO` methods; module singleton | `tests/unit/dao/base.cases.md` / none | No caller on this DAO. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `create_event` R1 ("within a second of the database's `now() AT TIME ZONE 'UTC'`") | `now()` is the transaction's start time, which can be more than a second before the call in a long test transaction. | IEV-CE-02 uses `clock_timestamp()` and 5 seconds, under `Asia/Dhaka` so a local-time default would be six hours off. |
| 2 | `get_by_invoice` R5 ("voided, draft, confirmed alike") | The invoice's state column and its values are not given, so a voided or confirmed invoice cannot be built from the spec. | R5 is covered by IEV-GI-14 (the query does not read `account_invoices`), not by a voided invoice. |
| 3 | Notes ("An invoice needs an account: … `AccountInvoice(…)`") | The module of `AccountInvoice` is not named. | Conventions assume `app.models.account_invoice.AccountInvoice`. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_event` | Returns | IEV-CE-01 |
| `create_event` | R1 | IEV-CE-01, IEV-CE-02 |
| `create_event` | R2 | IEV-CE-01, IEV-CE-03, IEV-CE-04 |
| `create_event` | R3 | IEV-CE-05, IEV-CE-06, IEV-CE-07 |
| `create_event` | R4 | IEV-CE-08, IEV-CE-09, IEV-CE-10, IEV-CE-11, IEV-CE-12, IEV-CE-13 |
| `create_event` | R5 | IEV-CE-14 |
| `create_event` | Errors | IEV-CE-08, IEV-CE-09, IEV-CE-10, IEV-CE-11, IEV-CE-12, IEV-CE-13 |
| `create_event` | Side effects | IEV-CE-01, IEV-CE-14 |
| `get_by_invoice` | Returns | IEV-GI-01 |
| `get_by_invoice` | R1 | IEV-GI-01, IEV-GI-02, IEV-GI-03, IEV-GI-04, IEV-GI-05, IEV-GI-06, IEV-GI-07 |
| `get_by_invoice` | R2 | IEV-GI-11 |
| `get_by_invoice` | R3 | IEV-GI-08 |
| `get_by_invoice` | R3 [BUG-638] | IEV-GI-09, IEV-GI-10 |
| `get_by_invoice` | R4 | IEV-GI-01, IEV-GI-12, IEV-GI-13 |
| `get_by_invoice` | R5 | IEV-GI-14 |
| `get_by_invoice` | R6 | IEV-GI-01 |
| `get_by_invoice` | Side effects | IEV-GI-15 |
