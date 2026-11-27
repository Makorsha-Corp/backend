# Test cases — `app/dao/sales_order.py`

> **Spec:** `tests/unit/dao/sales_order.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-10; nothing open). The owner answered OQ-26 as BUG-2404, a rule of the sales schema / service, so this file has no pending section.
> **Revision:** 2 (2026-11-10) — spec apply-review + fill-gaps (Gap log G1–G3, OQ-26). G1: `total_amount` is `Decimal | None`; new SLO-CW-32 (schema: an int, a float and a numeric string become an unrounded `Decimal`) and CW-33 (an int amount is stored with two decimals). G2: the model's `created_at` default cannot be patched; SLO-CW-18 and CW-19 now check a time window around the call instead of clock(N, N). G3: new `generate_sales_order_number` R3a (case-sensitive prefix); GN-17 now cites R3a, new GN-25 (mixed case `So-`). OQ-26: the Deferred row names BUG-2404. No ID retired.
> **Revision:** 3 (2026-11-10) — `sales_order.verify.md` findings 1–2. F1 (`case-missing`): new SLO-CW-34, both clocks in 2031 → `SO-2031-001` (twin of SDV-CW-10), so a pass card proves the year comes from the clock. F2: the no-lock lines of SLO-GI-18 and GN-23 now check `"FOR UPDATE" not in sql` instead of the vacuous `lock_part == ""`. Conventions gain "No-lock check" and "Clear the session before a one-query check". No ID retired.
> **Counts:** 77 cases · 68 expected-to-pass · 9 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Per callable:** `get_by_invoice_id` 18 (3 bug) · `generate_sales_order_number` 25 · `create_with_user` 34 (6 bug).
- **Depth:** full (skill step 1a). The table holds order and money state (`total_amount`), and its numbering is what every order is known by.
- **Expected-to-fail by bug:** BUG-2441 3 (GI-11, GI-12 non-strict, GI-13 strict SQL alarm) · BUG-2440 4 (CW-06 … CW-08, CW-31, strict, with clock(L, U) across New Year) · BUG-726 2 (CW-20 W0 holds the number, CW-21 W2 holds it; both fail in the call today with `IntegrityError` 23505) · BUG-727 0 here (race half integration-only, deferred).
- **Notable design choices:**
  - Numbering uses W0 (built before W1) and W2 (after) with their own numbers in every isolation card. Because the unique index is global today (BUG-726), the other workspaces' numbers never equal the number W1 is about to get in a pass card; only CW-20 and CW-21 put the same number in another workspace.
  - HR-15: `total_amount` is checked at `2.125` → `2.13` and `0.005` → `0.01`, where half to even would give `2.12` / `0.00`, at `-1.005` → `-1.01`, and the control `2.124` → `2.12`. All pass today (Postgres rounds half up).
  - CW-22 pins today's count rule (spec R4): two numbers that leave a gap make the computed number collide inside W1 → 23505. It holds today and after the BUG-726 fix; the BUG-727 fix (counter or retry) may change it, and the card must be revisited then.
  - Every order lookup that crosses workspaces uses each workspace's own invoice: no card builds an order linked to another workspace's invoice, account or factory (HR-16, such a row is invalid data). So `create_with_user` R6 "links stored without a workspace check" has no card; it is the manager's (BUG-728, BUG-1019), see Deferred.
  - `created_at` cannot be patched (spec R4). CW-18 and CW-19 read the real UTC time before and after the call and check that `created_at` falls between. No card asserts a fixed `created_at`.
  - `total_amount` is `Decimal | None`. CW-32 checks the schema's conversion directly (target `schema`); every DAO card passes `Decimal` values.
  - BUG-2441: GI-10 (pass) keeps what holds today: one of the two orders is returned. The tie cards are non-strict and `Author: claude`; GI-13 is the one strict alarm.
- **Needs a decision:** None. Both gaps of revision 1 are closed by the spec's Gap log (2026-11-10).

## Conventions for this module

**IDs.** `SLO` = `app/dao/sales_order.py`. `GI` get_by_invoice_id · `GN` generate_sales_order_number · `CW` create_with_user.

**Actors and fixed values.**
- `dao` = the singleton `sales_order_dao` (`from app.dao.sales_order import sales_order_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns. The session does not autoflush.
- `SalesOrder` = `app.models.sales_order.SalesOrder`. `SalesOrderCreate` = `app.schemas.sales_order.SalesOrderCreate`. `Account`, `Factory`, `Status`, `AccountInvoice` = `app.models.<snake_case>` (`AccountInvoice` from `app.models.account_invoice`). `IntegrityError` = `sqlalchemy.exc.IntegrityError`. `Decimal`, `date`, `datetime`, `timedelta`, `timezone`, `text`, `select`, `func`, `patch` = the usual ones.
- MISSING = `999999999`: an id that no row of any table has. TAG = `uuid.uuid4().hex[:8]`, made once per test.
- HIGH_ID = `max(greatest sales_orders.id or 0, last_value of sales_orders_id_seq) + 1000001`, read when the row is built.
- D1 = `date(2026, 1, 5)`, D2 = `date(2026, 3, 1)`, D3 = `date(2026, 3, 20)`.

**Externals.** **clock(L, U)** = for the When, patch `app.dao.sales_order.datetime` with a subclass of `datetime` whose `now()` (any arguments) returns L, and patch both `app.dao.sales_order.utcnow` (with `create=True`) and `app.utils.time.utcnow` to return U. A `CW` card without a clock line runs under clock(`datetime(2026, 6, 1, 12, 0)`, `datetime(2026, 6, 1, 12, 0)`). `GI` and `GN` cards patch nothing.
- **utc_now()** = `datetime.now(timezone.utc).replace(tzinfo=None)`. No clock patch reaches the model's `created_at` default, so no card relies on one for it.
- **Dhaka** = `db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))` as a Given step.

**Standing rows** (every test, this order, no Given line; each flushed):
1. W0, W1, W2 = `make_workspace(db)` three times (`W0.id < W1.id < W2.id`). U1, U2, U3 = `make_profile(db)` three times.
2. Per workspace k in 0, 1, 2: Ak = `Account(workspace_id=Wk.id, name=f"Acme {TAG}")`, Fk = `Factory(workspace_id=Wk.id, name="Main Plant", abbreviation=f"MP{k}")`, Sk = `Status(workspace_id=Wk.id, name="Open", comment="open")`.
3. Invoices, in this order: V0 of W0, V1, V2, V3 of W1, V9 of W2, each `AccountInvoice(workspace_id=Wk.id, account_id=Ak.id, invoice_type="receivable", invoice_amount=Decimal("100.00"), invoice_date=D1)`. So `V0.id < V1.id < V2.id < V3.id < V9.id`.

**Given rows.** Inserted directly (never through `dao`), flushed one at a time in the order written. After "but" a line lists every column that differs. A line written as code is a step to run exactly as written, at that place in the order.
- **order** = `SalesOrder(workspace_id=W1.id, sales_order_number=<given>, account_id=A1.id, factory_id=F1.id, order_date=D1, current_status_id=S1.id, created_by=U1.id)`; the card always gives `sales_order_number`. An order "of W0" uses W0, A0, F0, S0; "of W2" uses W2, A2, F2, S2. No order exists unless the Given lists it.
- **orders(W, prefix, n)** = `for i in range(1, n + 1):` add an order of W with `sales_order_number f"{prefix}{i:03d}"`, flushing once after the loop.
- **seqscan** = run `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`, in this order.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values. Money is compared as `Decimal` (`== Decimal("2.13")`), never as strings or floats.
- **count(W)** = `db.scalar(select(func.count()).select_from(SalesOrder).where(SalesOrder.workspace_id == W.id))`.
- **nothing written** = count(W0), count(W1), count(W2) equal their values before the call.
- `pending:` lines check the session directly after the call, before anything expires it.
- `raises: IntegrityError` = wrap the call: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. `raises: TypeError` / `raises: AttributeError` = plain `with pytest.raises(<Type>) as exc:` around the call. Further `raises:` lines assert on `exc.value` (or `exc.value.orig`), one `assert` per line.
- **commit spy** = `sp = db.begin_nested()` directly before the call, `with patch.object(db, "commit", wraps=db.commit) as cm:` around it; the "inside the savepoint" checks run first, then `sp.rollback()`, then the "after the savepoint rollback" checks.
- **Statement recorder** = the SQL the session sends during the When is recorded (`before_cursor_execute` listener, as `tests/unit/managers/test_ledger_manager.py`). `sql` = the text of the one `SELECT` from `sales_orders`; `order_part` = text of `sql` after its first `ORDER BY`, before any `LIMIT` (`""` if none); `lock_part` = text of `sql` after `FOR UPDATE` (`""` if none); `written` = every recorded `INSERT`, `UPDATE`, `DELETE`.
- **No-lock check** = `"FOR UPDATE" not in sql`. Never use `lock_part == ""` for this: Postgres prints the lock clause last, so the text after `FOR UPDATE` is empty with a lock as well.
- **Clear the session before a one-query check**: a card that counts the SELECTs a call sends (or reads stored values back) ends its Given with `db.expunge_all()` (or `db.expire_all()` where the card says so), so a row the identity map still holds (a profile, a just-inserted value) cannot hide a second read. Ids used in Then come from objects built before it; their loaded attributes stay readable.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`, for cards whose result rests on physical row order. Write the call and the checks exactly as shown; never weaken an assertion.

**Race simulations.** None (the race half of BUG-727 is integration-only).

## `DAOSalesOrder.get_by_invoice_id`

### SLO-GI-01 — returns the order of the invoice, with the invoice in the middle
- **Rules:** `get_by_invoice_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id`.
2. O2 = order, `sales_order_number f"SO-2026-002-{TAG}"`, but `invoice_id V2.id`.
3. O3 = order, `sales_order_number f"SO-2026-003-{TAG}"`, but `invoice_id V3.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V2.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, SalesOrder)`.
2. returns: `result.id == O2.id`.
3. returns: `result.sales_order_number == f"SO-2026-002-{TAG}"`.

### SLO-GI-02 — an order of the earlier workspace with its own invoice is not returned for W1
- **Rules:** `get_by_invoice_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0, `sales_order_number f"SO-2026-010-{TAG}"`, but `invoice_id V0.id`.
2. O1 = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V0.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### SLO-GI-03 — an order of the later workspace with its own invoice is not returned for W1
- **Rules:** `get_by_invoice_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id`.
2. X2 = order of W2, `sales_order_number f"SO-2026-020-{TAG}"`, but `invoice_id V9.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### SLO-GI-04 — asked for W2, its own order is returned, though W0 and W1 orders come earlier
- **Rules:** `get_by_invoice_id` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0, `sales_order_number f"SO-2026-010-{TAG}"`, but `invoice_id V0.id`.
2. O1 = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id`.
3. X2 = order of W2, `sales_order_number f"SO-2026-020-{TAG}"`, but `invoice_id V9.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V9.id, workspace_id=W2.id)`.

**Then**
1. returns: `result.id == X2.id`.

### SLO-GI-05 — asked for W0, its own order is returned, though W1 and W2 orders come later
- **Rules:** `get_by_invoice_id` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0, `sales_order_number f"SO-2026-010-{TAG}"`, but `invoice_id V0.id`.
2. O1 = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id`.
3. X2 = order of W2, `sales_order_number f"SO-2026-020-{TAG}"`, but `invoice_id V9.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V0.id, workspace_id=W0.id)`.

**Then**
1. returns: `result.id == X0.id`.

### SLO-GI-06 — an invoice with no order returns None
- **Rules:** `get_by_invoice_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id`.
2. O3 = order, `sales_order_number f"SO-2026-003-{TAG}"`, but `invoice_id V3.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### SLO-GI-07 — an unknown invoice id returns None
- **Rules:** `get_by_invoice_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### SLO-GI-08 — invoice id 0 returns None
- **Rules:** `get_by_invoice_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id`.
2. O2 = order, `sales_order_number f"SO-2026-002-{TAG}"` (no invoice).

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### SLO-GI-09 — an unknown workspace id returns None
- **Rules:** `get_by_invoice_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result is None`.

### SLO-GI-10 — with two orders on one invoice, one of them is returned
- **Rules:** `get_by_invoice_id` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id`.
2. OB = order, `sales_order_number f"SO-2026-002-{TAG}"`, but `invoice_id V1.id`.
3. OC = order, `sales_order_number f"SO-2026-003-{TAG}"`, but `invoice_id V2.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id in {OA.id, OB.id}`.

### SLO-GI-11 — on two orders of one invoice the lowest id wins, also after the lower one was updated
- **Rules:** `get_by_invoice_id` R3 [BUG-2441]
- **Kind:** bug
- **Expect:** xfail BUG-2441 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`; under a sequential scan the updated lower row moves behind the higher one)

**Given**
1. seqscan.
2. OA = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id`.
3. OB = order, `sales_order_number f"SO-2026-002-{TAG}"`, but `invoice_id V1.id`.
4. `OA.description = "Edited"`, then `db.flush()`.
5. `db.expire_all()`

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is not None`.
2. returns: `result.id == OA.id`.

### SLO-GI-12 — on two orders of one invoice the lowest id wins, when the higher id was inserted first
- **Rules:** `get_by_invoice_id` R3 [BUG-2441]
- **Kind:** bug
- **Expect:** xfail BUG-2441 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`; a sequential scan meets the higher id first)

**Given**
1. seqscan.
2. OB = order, `sales_order_number f"SO-2026-002-{TAG}"`, but `id HIGH_ID`, `invoice_id V1.id`.
3. OA = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id` (sequence id, lower than HIGH_ID).
4. `db.expire_all()`

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is not None`.
2. returns: `result.id == OA.id`.

### SLO-GI-13 — the lookup orders by sales_orders.id ascending
- **Rules:** `get_by_invoice_id` R3 [BUG-2441]
- **Kind:** bug
- **Expect:** xfail BUG-2441
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. O1 = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id`.
2. Statement recorder.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O1.id`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"sales_orders.id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### SLO-GI-14 — invoice_id None returns the workspace's order that has no invoice
- **Rules:** `get_by_invoice_id` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id`.
2. O2 = order, `sales_order_number f"SO-2026-002-{TAG}"` (no invoice).
3. O3 = order, `sales_order_number f"SO-2026-003-{TAG}"`, but `invoice_id V3.id`.
4. X2 = order of W2, `sales_order_number f"SO-2026-020-{TAG}"` (no invoice).

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=None, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O2.id`.

### SLO-GI-15 — invoice_id None returns None when every order of the workspace has an invoice
- **Rules:** `get_by_invoice_id` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X0 = order of W0, `sales_order_number f"SO-2026-010-{TAG}"` (no invoice).
2. O1 = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id`.
3. O2 = order, `sales_order_number f"SO-2026-002-{TAG}"`, but `invoice_id V2.id`.
4. X2 = order of W2, `sales_order_number f"SO-2026-020-{TAG}"` (no invoice).

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=None, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### SLO-GI-16 — positional arguments raise TypeError
- **Rules:** `get_by_invoice_id` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id`.

**When**
- `dao.get_by_invoice_id(db, V1.id, W1.id)` inside `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.
2. nothing written: nothing written.

### SLO-GI-17 — writes nothing: a pending order stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_invoice_id` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number f"SO-2026-001-{TAG}"`, but `invoice_id V1.id`.
2. `O1.description = "Edited"` (not flushed).
3. `P = SalesOrder(workspace_id=W1.id, sales_order_number=f"SO-2026-009-{TAG}", account_id=A1.id, factory_id=F1.id, order_date=D1, current_status_id=S1.id, created_by=U1.id, invoice_id=V2.id)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O1.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `O1 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.

### SLO-GI-18 — the pending order is not found, and no row lock is taken
- **Rules:** `get_by_invoice_id` R2, Side effects (Overview: takes no lock)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `P = SalesOrder(workspace_id=W1.id, sales_order_number=f"SO-2026-009-{TAG}", account_id=A1.id, factory_id=F1.id, order_date=D1, current_status_id=S1.id, created_by=U1.id, invoice_id=V2.id)`
2. `db.add(P)` (not flushed).
3. Statement recorder.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. statement: `"FOR UPDATE" not in sql`.
3. pending: `P in db.new`.

## `DAOSalesOrder.generate_sales_order_number`

### SLO-GN-01 — no order yet gives SO-2026-001
- **Rules:** `generate_sales_order_number` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `isinstance(result, str)`.
2. returns: `result == "SO-2026-001"`.

### SLO-GN-02 — two orders give SO-2026-003
- **Rules:** `generate_sales_order_number` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "SO-2026-001"`.
2. O2 = order, `sales_order_number "SO-2026-002"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-003"`.

### SLO-GN-03 — nine orders give SO-2026-010
- **Rules:** `generate_sales_order_number` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. orders(W1, "SO-2026-", 9).

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-010"`.

### SLO-GN-04 — 99 orders give SO-2026-100
- **Rules:** `generate_sales_order_number` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. orders(W1, "SO-2026-", 99).

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-100"`.

### SLO-GN-05 — 998 orders give SO-2026-999
- **Rules:** `generate_sales_order_number` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. orders(W1, "SO-2026-", 998).

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-999"`.

### SLO-GN-06 — 999 orders give SO-2026-1000, not cut to three digits
- **Rules:** `generate_sales_order_number` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. orders(W1, "SO-2026-", 999).

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-1000"`.

### SLO-GN-07 — only W1's orders count, with more orders in W0 and W2
- **Rules:** `generate_sales_order_number` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0a = order of W0, `sales_order_number "SO-2026-001"`.
2. A0b = order of W0, `sales_order_number "SO-2026-002"`.
3. A0c = order of W0, `sales_order_number "SO-2026-003"`.
4. O1 = order, `sales_order_number "SO-2026-006"`.
5. A2a = order of W2, `sales_order_number "SO-2026-004"`.
6. A2b = order of W2, `sales_order_number "SO-2026-005"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-002"`.

### SLO-GN-08 — asked for W2, only W2's orders count
- **Rules:** `generate_sales_order_number` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0a = order of W0, `sales_order_number "SO-2026-001"`.
2. A0b = order of W0, `sales_order_number "SO-2026-002"`.
3. A0c = order of W0, `sales_order_number "SO-2026-003"`.
4. O1 = order, `sales_order_number "SO-2026-006"`.
5. A2a = order of W2, `sales_order_number "SO-2026-004"`.
6. A2b = order of W2, `sales_order_number "SO-2026-005"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W2.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-003"`.

### SLO-GN-09 — an unknown workspace gets SO-2026-001
- **Rules:** `generate_sales_order_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "SO-2026-001"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=MISSING, year=2026)`.

**Then**
1. returns: `result == "SO-2026-001"`.

### SLO-GN-10 — orders of the year before and the year after do not count
- **Rules:** `generate_sales_order_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "SO-2025-001"`.
2. O2 = order, `sales_order_number "SO-2027-001"`.
3. O3 = order, `sales_order_number "SO-2026-001"`.
4. O4 = order, `sales_order_number "SO-2025-002"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-002"`.

### SLO-GN-11 — year 202 does not count SO-2026 numbers
- **Rules:** `generate_sales_order_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "SO-2026-001"`.
2. O2 = order, `sales_order_number "SO-2026-002"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=202)`.

**Then**
1. returns: `result == "SO-202-001"`.

### SLO-GN-12 — year 1 is printed as is, and SO-10 numbers do not count for it
- **Rules:** `generate_sales_order_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "SO-10-001"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=1)`.

**Then**
1. returns: `result == "SO-1-001"`.

### SLO-GN-13 — year 1 counts its own SO-1 numbers
- **Rules:** `generate_sales_order_number` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "SO-1-001"`.
2. O2 = order, `sales_order_number "SO-10-001"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=1)`.

**Then**
1. returns: `result == "SO-1-002"`.

### SLO-GN-14 — a number with a longer year (SO-20261-) does not count for 2026
- **Rules:** `generate_sales_order_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "SO-20261-001"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-001"`.

### SLO-GN-15 — a non-numeric suffix counts as one order
- **Rules:** `generate_sales_order_number` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "SO-2026-abc"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-002"`.

### SLO-GN-16 — the count, not the highest number, decides: SO-2026-009 alone gives 002
- **Rules:** `generate_sales_order_number` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "SO-2026-009"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-002"`.

### SLO-GN-17 — a lowercase stored prefix does not count
- **Rules:** `generate_sales_order_number` R1, R3, R3a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "so-2026-001"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-001"`.

### SLO-GN-18 — a stored number with a leading space does not count
- **Rules:** `generate_sales_order_number` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number " SO-2026-001"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-001"`.

### SLO-GN-19 — the prefix in the middle of a stored number does not count
- **Rules:** `generate_sales_order_number` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "XSO-2026-001"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-001"`.

### SLO-GN-20 — a stored _ where the prefix has a dash does not count
- **Rules:** `generate_sales_order_number` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "SO_2026-001"`.
2. O2 = order, `sales_order_number "SO-2026_001"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-001"`.

### SLO-GN-21 — the prefix without its closing dash does not count
- **Rules:** `generate_sales_order_number` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "SO-2026"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-001"`.

### SLO-GN-22 — writes nothing: a pending order stays pending and is not counted, an unflushed edit stays unflushed
- **Rules:** `generate_sales_order_number` R5, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = order, `sales_order_number "SO-2025-001"`.
2. `B.description = "Edited"` (not flushed).
3. `P = SalesOrder(workspace_id=W1.id, sales_order_number="SO-2026-001", account_id=A1.id, factory_id=F1.id, order_date=D1, current_status_id=S1.id, created_by=U1.id)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-001"`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.

### SLO-GN-23 — reads with no row lock
- **Rules:** `generate_sales_order_number` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "SO-2026-001"`.
2. Statement recorder.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-002"`.
2. statement: `"FOR UPDATE" not in sql`.
3. statement: `written == []`.

### SLO-GN-24 — positional arguments raise TypeError
- **Rules:** `generate_sales_order_number` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `dao.generate_sales_order_number(db, W1.id, 2026)` inside `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.
2. nothing written: nothing written.

### SLO-GN-25 — a mixed-case stored prefix (So-) does not count
- **Rules:** `generate_sales_order_number` R3a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "So-2026-001"`.
2. O2 = order, `sales_order_number "SO-2026-002"`.

**When**
- `result = dao.generate_sales_order_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SO-2026-002"`.

## `DAOSalesOrder.create_with_user`

### SLO-CW-01 — stores every given field, the workspace, the creator and the first number
- **Rules:** `create_with_user` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, expected_delivery_date=D3, contact_name="Rahim", contact_phone="01711000000", description="Ten chairs", total_amount=Decimal("1500.00"), current_status_id=S1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, SalesOrder)`.
2. returns: `result.id is not None`.
3. re-read result: `workspace_id == W1.id`, `created_by == U2.id`, `sales_order_number == "SO-2026-001"`.
4. re-read result: `account_id == A1.id`, `factory_id == F1.id`, `current_status_id == S1.id`.
5. re-read result: `order_date == D2`, `expected_delivery_date == D3`.
6. re-read result: `contact_name == "Rahim"`, `contact_phone == "01711000000"`, `description == "Ten chairs"`.
7. re-read result: `total_amount == Decimal("1500.00")`.
8. count: `count(W1) == 1`.

### SLO-CW-02 — unset optional fields are stored as NULL
- **Rules:** `create_with_user` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)` (`expected_delivery_date`, `contact_name`, `contact_phone`, `description`, `total_amount` not sent).

**Then**
1. returns: `result.id is not None`.
2. re-read result: `expected_delivery_date is None`, `contact_name is None`, `contact_phone is None`, `description is None`.

### SLO-CW-03 — the second and third orders of the year get the next number
- **Rules:** `create_with_user` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "SO-2026-001"`.
2. O2 = order, `sales_order_number "SO-2026-002"`.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `sales_order_number == "SO-2026-003"`.
3. count: `count(W1) == 3`.

### SLO-CW-04 — the number counts this workspace only, with more orders in W0 and W2
- **Rules:** `create_with_user` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0a = order of W0, `sales_order_number "SO-2026-007"`.
2. A0b = order of W0, `sales_order_number "SO-2026-008"`.
3. O1 = order, `sales_order_number "SO-2026-001"`.
4. A2a = order of W2, `sales_order_number "SO-2026-009"`.
5. A2b = order of W2, `sales_order_number "SO-2026-010"`.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `sales_order_number == "SO-2026-002"`, `workspace_id == W1.id`.
3. count: `count(W0) == 2`.
4. count: `count(W2) == 2`.

### SLO-CW-05 — the number takes the current year, and last year's orders do not count
- **Rules:** `create_with_user` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "SO-2025-001"`.
2. O2 = order, `sales_order_number "SO-2025-002"`.
3. clock(`datetime(2026, 6, 1, 12, 0)`, `datetime(2026, 6, 1, 12, 0)`).

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `sales_order_number == "SO-2026-001"`.

### SLO-CW-06 — the year comes from UTC when the local clock is already in the next year
- **Rules:** `create_with_user` R2 [BUG-2440]
- **Kind:** bug
- **Expect:** xfail BUG-2440
- **Fails today on:** Then 2 (the local year is used: `SO-2027-001`)

**Given**
1. W1 has no order.
2. clock(`datetime(2027, 1, 1, 5, 0)`, `datetime(2026, 12, 31, 23, 0)`).

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `sales_order_number == "SO-2026-001"`.

### SLO-CW-07 — the year comes from UTC when the local clock is still in the old year
- **Rules:** `create_with_user` R2 [BUG-2440]
- **Kind:** bug
- **Expect:** xfail BUG-2440
- **Fails today on:** Then 2 (the local year is used: `SO-2026-001`)

**Given**
1. W1 has no order.
2. clock(`datetime(2026, 12, 31, 20, 0)`, `datetime(2027, 1, 1, 2, 0)`).

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `sales_order_number == "SO-2027-001"`.

### SLO-CW-08 — on New Year's Eve in UTC the UTC year's orders are counted
- **Rules:** `create_with_user` R1, R2 [BUG-2440]
- **Kind:** bug
- **Expect:** xfail BUG-2440
- **Fails today on:** Then 2 (the local year 2027 has no orders: `SO-2027-001`)

**Given**
1. O1 = order, `sales_order_number "SO-2026-001"`.
2. O2 = order, `sales_order_number "SO-2026-002"`.
3. clock(`datetime(2027, 1, 1, 5, 0)`, `datetime(2026, 12, 31, 23, 0)`).

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `sales_order_number == "SO-2026-003"`.

### SLO-CW-31 — on New Year's Day in UTC the old year's orders are not counted
- **Rules:** `create_with_user` R1, R2 [BUG-2440]
- **Kind:** bug
- **Expect:** xfail BUG-2440
- **Fails today on:** Then 2 (the local year 2026 is used and its two orders counted: `SO-2026-003`)

**Given**
1. O1 = order, `sales_order_number "SO-2026-001"`.
2. O2 = order, `sales_order_number "SO-2026-002"`.
3. clock(`datetime(2026, 12, 31, 20, 0)`, `datetime(2027, 1, 1, 2, 0)`).

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `sales_order_number == "SO-2027-001"`.

### SLO-CW-09 — total_amount omitted is stored as 0.00
- **Rules:** `create_with_user` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)` (`total_amount` not sent).

**Then**
1. returns: `result.id is not None`.
2. re-read result: `total_amount == Decimal("0.00")`.

### SLO-CW-10 — 2.125 is stored as 2.13 (half up, not half to even)
- **Rules:** `create_with_user` R3 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, total_amount=Decimal("2.125"), current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `total_amount == Decimal("2.13")`.

### SLO-CW-11 — 0.005 is stored as 0.01 (half up, not half to even)
- **Rules:** `create_with_user` R3 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, total_amount=Decimal("0.005"), current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `total_amount == Decimal("0.01")`.

### SLO-CW-12 — -1.005 is stored as -1.01 (half away from zero)
- **Rules:** `create_with_user` R3 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, total_amount=Decimal("-1.005"), current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `total_amount == Decimal("-1.01")`.

### SLO-CW-13 — 2.124 is stored as 2.12 (below the half rounds down)
- **Rules:** `create_with_user` R3 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, total_amount=Decimal("2.124"), current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `total_amount == Decimal("2.12")`.

### SLO-CW-14 — 1.005 is stored as 1.01
- **Rules:** `create_with_user` R3 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, total_amount=Decimal("1.005"), current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `total_amount == Decimal("1.01")`.

### SLO-CW-15 — a zero amount is accepted and stored as 0.00
- **Rules:** `create_with_user` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, total_amount=Decimal("0"), current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `total_amount == Decimal("0.00")`.
3. count: `count(W1) == 1`.

### SLO-CW-16 — a negative amount is accepted and stored as given
- **Rules:** `create_with_user` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, total_amount=Decimal("-50.00"), current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `total_amount == Decimal("-50.00")`.

### SLO-CW-17 — the new order's flags are false and its later fields empty
- **Rules:** `create_with_user` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `is_fully_delivered is False`, `is_invoiced is False`, `paid is False`, `order_info_confirmed is False`.
3. re-read result: `items_confirmed is False`, `invoice_confirmed is False`, `order_completed is False`.
4. re-read result: `invoice_id is None`, `required_approvals is None`, `completed_at is None`, `completed_by is None`.
5. re-read result: `updated_by is None`, `updated_at is None`, `items_updated_at is None`.

### SLO-CW-18 — created_at is the current UTC time, naive
- **Rules:** `create_with_user` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no order.
2. `before = utc_now()`.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`, then `after = utc_now()` (one step).

**Then**
1. returns: `result.id is not None`.
2. re-read result: `created_at.tzinfo is None`.
3. re-read result: `before <= created_at <= after`.

### SLO-CW-19 — created_at is UTC also when the database's time zone is Asia/Dhaka
- **Rules:** `create_with_user` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Dhaka.
2. W1 has no order.
3. `before = utc_now()`.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`, then `after = utc_now()` (one step).

**Then**
1. returns: `result.id is not None`.
2. re-read result: `created_at.tzinfo is None`.
3. re-read result: `before <= created_at <= after`.

### SLO-CW-20 — W0's SO-2026-001 does not stop W1's first order of 2026
- **Rules:** `create_with_user` R5 [BUG-726]
- **Kind:** bug
- **Expect:** xfail BUG-726
- **Fails today on:** Then 1 (the call raises IntegrityError: the unique index on the number is global)

**Given**
1. X0 = order of W0, `sales_order_number "SO-2026-001"`.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`, wrapped in `with db.begin_nested():`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `sales_order_number == "SO-2026-001"`, `workspace_id == W1.id`.
3. count: `count(W0) == 1`.

### SLO-CW-21 — W2's SO-2026-001 does not stop W1's first order of 2026
- **Rules:** `create_with_user` R5 [BUG-726]
- **Kind:** bug
- **Expect:** xfail BUG-726
- **Fails today on:** Then 1 (the call raises IntegrityError: the unique index on the number is global)

**Given**
1. X2 = order of W2, `sales_order_number "SO-2026-001"`.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`, wrapped in `with db.begin_nested():`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `sales_order_number == "SO-2026-001"`, `workspace_id == W1.id`.
3. count: `count(W2) == 1`.

### SLO-CW-22 — a computed number already used in the workspace fails at the flush and saves nothing
- **Rules:** `generate_sales_order_number` R4, `create_with_user` Errors (number already used)
- **Kind:** error
- **Expect:** pass

**Given**
1. O2 = order, `sales_order_number "SO-2026-002"`.
2. O3 = order, `sales_order_number "SO-2026-003"`.

**When**
- `dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)` inside `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23505"`.
2. count: `count(W1) == 2`.
3. nothing written: nothing written.

### SLO-CW-23 — an unknown account fails at the flush with 23503 and saves nothing
- **Rules:** `create_with_user` R6, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=MISSING, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)` inside `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. count: `count(W1) == 0`.
3. nothing written: nothing written.

### SLO-CW-24 — an unknown factory fails at the flush with 23503 and saves nothing
- **Rules:** `create_with_user` R6, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=MISSING, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)` inside `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. count: `count(W1) == 0`.
3. nothing written: nothing written.

### SLO-CW-25 — an unknown status fails at the flush with 23503 and saves nothing
- **Rules:** `create_with_user` R6, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=MISSING), workspace_id=W1.id, user_id=U1.id)` inside `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. count: `count(W1) == 0`.
3. nothing written: nothing written.

### SLO-CW-26 — an unknown user fails at the flush with 23503 and saves nothing
- **Rules:** `create_with_user` R6, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=MISSING)` inside `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. count: `count(W1) == 0`.
3. nothing written: nothing written.

### SLO-CW-27 — positional arguments raise TypeError and save nothing
- **Rules:** `create_with_user` R7
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `dao.create_with_user(db, SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), W1.id, U1.id)` inside `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.
2. session: `not db.new`.
3. nothing written: nothing written.

### SLO-CW-28 — a plain dict as obj_in raises AttributeError and saves nothing
- **Rules:** `create_with_user` R7
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `dao.create_with_user(db, obj_in={"account_id": A1.id, "factory_id": F1.id, "order_date": D2, "current_status_id": S1.id}, workspace_id=W1.id, user_id=U1.id)` inside `raises: AttributeError`.

**Then**
1. raises: `isinstance(exc.value, AttributeError)`.
2. session: `not db.new`.
3. nothing written: nothing written.

### SLO-CW-29 — flushed, not committed: a rollback removes the order
- **Rules:** `create_with_user` Returns, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no order.
2. commit spy.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `count(W1) == 1`.
3. count: after the savepoint rollback, `count(W1) == 0`.
4. mock called: `cm.call_count == 0`.

### SLO-CW-30 — inserts exactly one row and touches no other order
- **Rules:** `create_with_user` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. X0 = order of W0, `sales_order_number "SO-2026-011"`.
2. O1 = order, `sales_order_number "SO-2026-001"`.
3. X2 = order of W2, `sales_order_number "SO-2026-012"`.
4. Statement recorder.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. statement: `len(written) == 1`.
3. statement: `written[0].lstrip().upper().startswith("INSERT INTO SALES_ORDERS")`.
4. count: `count(W0) == 1`.
5. count: `count(W1) == 2`.
6. count: `count(W2) == 1`.
7. unchanged: unchanged(O1).

### SLO-CW-32 — the schema turns an int, a float and a numeric string into an unrounded Decimal
- **Rules:** `create_with_user` Inputs (`total_amount` is `Decimal | None`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `result = [SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, total_amount=v).total_amount for v in (990, 2.5, "2.125")]` (one list comprehension; target `schema`, the DAO is not called).

**Then**
1. returns: `[type(v) for v in result] == [Decimal, Decimal, Decimal]`.
2. returns: `result[0] == Decimal("990")`.
3. returns: `result[1] == Decimal("2.5")`.
4. returns: `result[2] == Decimal("2.125")`.
5. nothing written: nothing written.

### SLO-CW-33 — an int amount is stored as a Decimal with two decimals
- **Rules:** `create_with_user` R3, HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id, total_amount=990), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `total_amount == Decimal("990.00")`.
3. re-read result: `str(total_amount) == "990.00"`.

### SLO-CW-34 — the year comes from the clock: both clocks in 2031 give SO-2031-001
- **Rules:** `create_with_user` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = order, `sales_order_number "SO-2026-001"`.
2. clock(`datetime(2031, 1, 1, 0, 30)`, `datetime(2031, 1, 1, 0, 30)`).

**When**
- `result = dao.create_with_user(db, obj_in=SalesOrderCreate(account_id=A1.id, factory_id=F1.id, order_date=D2, current_status_id=S1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `sales_order_number == "SO-2031-001"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `create_with_user` R5 [BUG-727] race half | integration tests (sales manager spec) | two concurrent creates in one workspace both succeed with distinct numbers |
| `create_with_user` R6 links stored without a workspace check | `SalesManager.create_sales_order_with_items` (BUG-728, BUG-1019) | another workspace's customer, factory or status is refused as "not found" (HR-16); no DAO card builds such a link |
| FU-1 (a), OQ-26 → BUG-2404 | `SalesService.update_sales_order` / `SalesOrderUpdate` | `total_amount`, `is_fully_delivered`, `is_invoiced` are system-only: an edit that sends them gets 422 and nothing is written (owner, 2026-11-10) |
| FU-1 (b) | `GET /sales-orders/` | `limit` needs `ge=1` (HR-7) |
| FU-1 (c) | `SalesService.update_sales_order` | edit checked against `is_so_financially_locked` |
| FU-2 | sales manager spec | "local year" wording follows BUG-2440 |
| Not specified: `get_by_factory`, `get_by_status` | dead-code removal checklist | removed (Q1); no cards |
| Inherited `BaseDAO` methods | `tests/unit/dao/base.cases.md` | already covered |

## Spec gaps
None. The spec's Gap log (2026-11-10) closes both gaps of revision 1: gap 1 (type of `total_amount`) → G1, cards SLO-CW-32 and CW-33; gap 2 (`created_at` default and the clock patch) → G2, cards SLO-CW-18 and CW-19 rewritten to a time window.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_invoice_id` | R1 | SLO-GI-01, GI-04, GI-05, GI-10 |
| `get_by_invoice_id` | R2 | SLO-GI-02, GI-03, GI-04, GI-05, GI-06, GI-07, GI-08, GI-09, GI-18 |
| `get_by_invoice_id` | R3 [BUG-2441] | SLO-GI-10 (pass), GI-11, GI-12 (non-strict), GI-13 (strict) |
| `get_by_invoice_id` | R4 | SLO-GI-14, GI-15 |
| `get_by_invoice_id` | R5 | SLO-GI-16 |
| `get_by_invoice_id` | Side effects none / no lock | SLO-GI-17, GI-18 |
| `generate_sales_order_number` | R1 | SLO-GN-01 … GN-06, GN-13, GN-17 … GN-21 |
| `generate_sales_order_number` | R2 | SLO-GN-07, GN-08, GN-09 |
| `generate_sales_order_number` | R3 | SLO-GN-10 … GN-14, GN-17 … GN-21 |
| `generate_sales_order_number` | R3a | SLO-GN-17, GN-25 |
| `generate_sales_order_number` | R4 | SLO-GN-15, GN-16 |
| `generate_sales_order_number` | R5 / Side effects | SLO-GN-22, GN-23 |
| `generate_sales_order_number` | R6 | SLO-GN-24 |
| `create_with_user` | R1 | SLO-CW-01 … CW-05, CW-08, CW-31 |
| `create_with_user` | R2 [BUG-2440] | SLO-CW-05 (pass), CW-06, CW-07, CW-08, CW-31 |
| `create_with_user` | Inputs (`total_amount` `Decimal \| None`) | SLO-CW-32 |
| `create_with_user` | R3 (HR-15) | SLO-CW-09 … CW-16, CW-33 |
| `create_with_user` | R4 | SLO-CW-17, CW-18, CW-19 |
| `create_with_user` | R5 [BUG-726] | SLO-CW-20, CW-21 |
| `create_with_user` | R5 [BUG-727] | Deferred (integration) |
| `create_with_user` | R6 | SLO-CW-23 … CW-26; workspace half Deferred |
| `create_with_user` | R7 | SLO-CW-27, CW-28 |
| `create_with_user` | Errors: number already used | SLO-CW-22 (same workspace); CW-20, CW-21 (other workspace, bug) |
| `create_with_user` | Errors: unknown account / factory / status / user | SLO-CW-23, CW-24, CW-25, CW-26 |
| `create_with_user` | Returns / Side effects (flush, no commit, one insert) | SLO-CW-01, CW-29, CW-30 |
| `create_with_user` | R1, R2 (year from the clock, pass half of BUG-2440) | SLO-CW-34 |
