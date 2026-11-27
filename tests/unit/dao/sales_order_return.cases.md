# Test cases — `app/dao/sales_order_return.py`

> **Spec:** `tests/unit/dao/sales_order_return.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-10; nothing open). P1–P3, D1 and the fill-gaps decisions (R1a, R3a, `get_by_invoice_id` R4) were decided by Claude under the reviewer's delegation. No owner question (OQ-25 … OQ-28) touches this module, so there is no pending section.
> **Revision:** 2 (2026-11-10) — spec fill-gaps G1–G6. G1: Conventions' model modules and parent-row recipes confirmed, unchanged. G2: every voided Given row now carries what a real void writes (`status "voided"`, `updated_at T2`; `paid` stays False, no `updated_by`): GN-03, BS-01, BS-10, OP-01, OP-03, IV-02 changed. G3: the year patch target `app.dao.sales_order_return.utcnow` (already in clock(L, U)), unchanged. G4 / R3a: SRT-CW-14 now states the intended behaviour (a taken next number never fails the call; xfail BUG-2421); new CW-21 keeps 23505 as a direct-insert fact. G5 / `get_by_invoice_id` R4: new IV-10, IV-11. G6 / R1a: new GN-17. No ID retired.
> **Revision:** 3 (2026-11-10) — `sales_order_return.verify.md` finding 1 (convention). SRT-GN-16, BS-14, OP-10, IV-09, RI-10: the no-lock line is now `"FOR UPDATE" not in sql` instead of the vacuous `lock_part == ""`. Conventions gain "No-lock check" and "Clear the session before a one-query check". Counts unchanged; no ID retired.
> **Counts:** 86 cases · 74 expected-to-pass · 12 expected-to-fail (bugs) · 5 deferred

## Reviewer summary
- **Per callable:** `generate_return_number` 17 · `create_with_user` 21 (5 bug) · `get_by_sales_order` 15 (3 bug) · `get_open_by_sales_order` 11 (2 bug) · `get_by_invoice_id` 11 · `DAOSalesOrderReturnItem.get_by_return` 11 (2 bug).
- **Depth:** full. Returns are order workflow (they block an order's completion) and carry money lines and a credit note; numbering is a per-workspace uniqueness question (BUG-726 precedent).
- **Expected-to-fail:** BUG-2420 2 strict (CW-12 holder in W0, CW-13 holder in W2) · BUG-2422 2 strict (CW-09, CW-10: the local and the UTC year differ in both directions) · BUG-2423 3 (BS-09, BS-10 non-strict, BS-11 strict SQL alarm) · BUG-2424 2 (OP-07 non-strict, OP-08 strict alarm) · BUG-2425 2 (RI-07 non-strict, RI-08 strict alarm) · BUG-2421 1 strict (CW-14, R3a: a taken next number must not fail the call). The race half of BUG-2421 (R3) has no card: the spec says it is not unit-testable.
- **Notable design choices:**
  - The number index is global today, so rows of W0 and W2 in numbering cards use their own numbers (`SR-2026-101`, `SR-2026-201` …): they still carry the prefix and must not be counted. Only CW-12 / CW-13 reuse a number across workspaces, on purpose.
  - `create_with_user` cards run under a patched clock (both the module's `datetime.now()` and `utcnow`), so numbers are fixed. CW-11 (both clocks in 2031 → `SR-2031-001`) is the pass half of BUG-2422; CW-07 / CW-08 check `created_at` without any clock patch.
  - R3a / R4: CW-14 asserts only "succeeds, starts `SR-2026-`, number unused in the workspace", so a counter fix and a retry fix both pass it. The database's same-workspace refusal (23505) is CW-21, a direct insert, true under every fix.
  - `get_by_invoice_id(None)` (R4) gets one card per side: the workspace's return with no credit note (made real by deleting its invoice, `ON DELETE SET NULL`) is found; `None` when every return has one.
  - Voided rows carry what `void_return` writes (`status`, `paid`, `updated_at`; never `updated_by`).
  - HR-15 does not apply to the DAO (it computes no money), but the credit note is built from `get_by_return`: RI-05 / RI-06 pin that the `Numeric(15,2)` columns hand back half-up values (2.125 → 2.13, 0.005 → 0.01, -1.005 → -1.01; control 2.124 → 2.12).
  - Tie cards use the spec's recipe (forced sequential scan, update of the lowest id). All tie-order cards are non-strict and `Author: claude`; each query has one strict statement alarm.
  - `get_by_invoice_id` R3 (several returns on one invoice) gets one card that accepts either row, as the spec asks.
  - Race simulations: none.
- **Needs a decision:** None. Gaps 1–4 of revision 1 are closed by the spec's Gap log (G1–G6, 2026-11-10).

## Conventions for this module

**IDs.** `SRT` = `app/dao/sales_order_return.py`. `GN` generate_return_number · `CW` create_with_user · `BS` get_by_sales_order · `OP` get_open_by_sales_order · `IV` get_by_invoice_id · `RI` `DAOSalesOrderReturnItem.get_by_return`.

**Actors and fixed values.**
- `dao` = `sales_order_return_dao`, `idao` = `sales_order_return_item_dao` (both `from app.dao.sales_order_return import ...`). `db` = the test's real session, first argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- `SalesOrderReturn`, `SalesOrderReturnItem` = `app.models.sales_order_return`. `Account`, `Factory`, `Status`, `SalesOrder`, `SalesOrderItem`, `Item`, `AccountInvoice` = `app.models.account`, `.factory`, `.status`, `.sales_order`, `.sales_order_item`, `.item`, `.account_invoice`. `IntegrityError` = `sqlalchemy.exc.IntegrityError`. `Decimal`, `date`, `datetime`, `timedelta`, `text`, `select`, `func`, `patch`, `uuid` = the usual ones. `utcnow` = `app.utils.time.utcnow`.
- MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`, made once per test. T1 … T5 = `datetime(2026, 1, 1, 9, 0)` … `datetime(2026, 1, 1, 13, 0)` (naive, one hour apart).

**Externals.** Only in `CW` cards: **clock(L, U)** = for the When, patch `app.dao.sales_order_return.datetime` with a subclass of `datetime` whose `now()` returns L, and patch both `app.dao.sales_order_return.utcnow` (with `create=True`) and `app.utils.time.utcnow` to return U. A `CW` card without a clock line runs under clock(`datetime(2026, 6, 1, 12, 0)`, `datetime(2026, 6, 1, 12, 0)`); a card that says "no clock" patches nothing.

**Standing rows** (every test, this order, each added and flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` three times (`W0.id < W1.id < W2.id`). U1, U2, U3 = `make_profile(db)` three times.
2. For W0, W1, W2 in turn: AC0 / AC1 / AC9 = `Account(workspace_id=…, name="Acme")`; F0 / F1 / F9 = `Factory(workspace_id=…, name="Factory One", abbreviation="F1")`; S0 / S1 / S9 = `Status(workspace_id=…, name="Draft", comment="Stage")`.
3. Orders, in this order: SO0 (W0), SO1, SO2, SO3 (W1), SO9 (W2) = `SalesOrder(workspace_id=…, sales_order_number=f"SO-{TAG}-<name>", account_id=…, factory_id=…, order_date=date(2026, 3, 1), total_amount=0, current_status_id=…, created_by=U1.id)` with that workspace's account, factory and status. So `SO1.id < SO2.id < SO3.id`.
4. IT1 = `Item(workspace_id=W1.id, name="Bolt", name_normalized="bolt", unit="pcs")`. L1 = `SalesOrderItem(workspace_id=W1.id, sales_order_id=SO1.id, description="Line", quantity_ordered=Decimal("5.00"), unit_price=Decimal("2.00"), line_total=Decimal("10.00"))`.
5. INV1, INV2, INV3 = `AccountInvoice(workspace_id=W1.id, account_id=AC1.id, invoice_type="payable", invoice_amount=100, invoice_date=date(2026, 3, 1))`, in this order (`INV1.id < INV2.id < INV3.id`).

**Given rows.** Inserted directly (never through the DAOs), flushed one at a time in the order written. After "but" a line lists every column that differs. A line written as code is a step to run exactly, at that place.
- **return N** = `SalesOrderReturn(workspace_id=W1.id, sales_order_id=SO2.id, return_number=N, return_type="refund", created_by=U1.id, created_at=T1)`; `status` left to its default `"pending"`. The card always gives N. "**of W0**" adds `workspace_id W0.id`, `sales_order_id SO0.id`; "**of W2**" adds `workspace_id W2.id`, `sales_order_id SO9.id` — unless the line names another `sales_order_id`.
- **line on R** = `SalesOrderReturnItem(workspace_id=W1.id, return_id=R.id, so_item_id=L1.id, item_id=None, quantity_returned=Decimal("1.00"), unit_price=Decimal("2.00"))`.
- **bump(X)** = `db.execute(text("UPDATE sales_order_returns SET notes = 'bumped' WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`. **bumpL(X)** = the same on `sales_order_return_items`.
- **seqscan** = run `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`, in this order.
- **Dhaka** = `db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))`.

**Named checks.**
- **ids(result)** = `[r.id for r in result]`, order part of the check. **idset(result)** = `{r.id for r in result}`.
- A voided return in a Given always carries `status "voided"`, `updated_at T2` (what a real void writes; `paid` stays False, `updated_by` stays NULL).
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. **unchanged(X)** = after re-read every column of X equals its value before the call.
- **n(W)** = `db.scalar(select(func.count()).select_from(SalesOrderReturn).where(SalesOrderReturn.workspace_id == W.id))`.
- **nothing written** = the numbers of `sales_order_returns` and `sales_order_return_items` rows (all workspaces) equal their values before the call.
- `pending:` lines check the session after the call, before anything expires it; they come ahead of `nothing written:` lines.
- `raises: IntegrityError` = `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards. Later `raises:` lines assert on `exc.value.orig`, one per line.
- **commit spy** = `sp = db.begin_nested()` directly before the call, `with patch.object(db, "commit", wraps=db.commit) as cm:` around it; "inside" lines first, then `sp.rollback()`, then the "after" lines.
- **Statement recorder** = the SQL the session sends during the When is recorded. `selects` = every `SELECT`; `sql` = the one `SELECT` sent; `order_part` = text of `sql` after its first `ORDER BY`, before any `LIMIT` (`""` if none); `lock_part` = text of `sql` after `FOR UPDATE` (`""` if none); `written` = every `INSERT`, `UPDATE`, `DELETE`.
- **No-lock check** = `"FOR UPDATE" not in sql`. Never use `lock_part == ""` for this: Postgres prints the lock clause last, so the text after `FOR UPDATE` is empty with a lock as well.
- **Clear the session before a one-query check**: a card that counts the SELECTs a call sends (or reads stored values back) ends its Given with `db.expunge_all()` (or `db.expire_all()` where the card says so), so a row the identity map still holds (a profile, a just-inserted value) cannot hide a second read. Ids used in Then come from objects built before it; their loaded attributes stay readable.
- **close to now** = `before <= value <= after`, where `before = utcnow()` is taken right before the When and `after = utcnow()` right after it.
- Money and quantities are compared as `Decimal` values, never as strings.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. Write the call and the checks exactly as shown; never weaken an assertion.

**Race simulations.** None in this module.

## `DAOSalesOrderReturn.generate_return_number`

### SRT-GN-01 — no return yet gives SR-2026-001
- **Rules:** `generate_return_number` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no return.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SR-2026-001"`.

### SRT-GN-02 — two returns give SR-2026-003
- **Rules:** `generate_return_number` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.
2. B = return `"SR-2026-002"`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SR-2026-003"`.

### SRT-GN-03 — pending, completed and voided returns all count
- **Rules:** `generate_return_number` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.
2. B = return `"SR-2026-002"`, but `status "completed"`, `completed_at T2`, `completed_by U1.id`.
3. C = return `"SR-2026-003"`, but `status "voided"`, `updated_at T2`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SR-2026-004"`.

### SRT-GN-04 — a hand-made number with a non-numeric tail counts as one
- **Rules:** `generate_return_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"SR-2026-XYZ"`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SR-2026-002"`.

### SRT-GN-05 — returns of W0 and of W2 are not counted for W1
- **Rules:** `generate_return_number` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = return `"SR-2026-101"` of W0.
2. Z2 = return `"SR-2026-102"` of W0.
3. A = return `"SR-2026-001"`.
4. X1 = return `"SR-2026-201"` of W2.
5. X2 = return `"SR-2026-202"` of W2.
6. X3 = return `"SR-2026-203"` of W2.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SR-2026-002"`.

### SRT-GN-06 — asked for W2, the returns of W0 and W1 are not counted
- **Rules:** `generate_return_number` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = return `"SR-2026-101"` of W0.
2. A = return `"SR-2026-001"`.
3. B = return `"SR-2026-002"`.
4. X1 = return `"SR-2026-201"` of W2.

**When**
- `result = dao.generate_return_number(db, workspace_id=W2.id, year=2026)`.

**Then**
1. returns: `result == "SR-2026-002"`.

### SRT-GN-07 — asked for W0, the returns of W1 and W2 are not counted
- **Rules:** `generate_return_number` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.
2. X1 = return `"SR-2026-201"` of W2.
3. X2 = return `"SR-2026-202"` of W2.

**When**
- `result = dao.generate_return_number(db, workspace_id=W0.id, year=2026)`.

**Then**
1. returns: `result == "SR-2026-001"`.

### SRT-GN-08 — an unknown workspace gives -001
- **Rules:** `generate_return_number` R3, Inputs (`workspace_id` not checked)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.

**When**
- `result = dao.generate_return_number(db, workspace_id=MISSING, year=2026)`.

**Then**
1. returns: `result == "SR-2026-001"`.

### SRT-GN-09 — the years before and after are not counted
- **Rules:** `generate_return_number` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = return `"SR-2025-001"`.
2. B = return `"SR-2027-001"`.
3. C = return `"SR-2027-002"`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SR-2026-001"`.

### SRT-GN-10 — year 2099 with rows of 2026 gives SR-2099-001
- **Rules:** `generate_return_number` R3, Inputs (`year` not range-checked)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.
2. B = return `"SR-2026-002"`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2099)`.

**Then**
1. returns: `result == "SR-2099-001"`.

### SRT-GN-11 — year 1 is used as written, and SR-10- does not count for it
- **Rules:** `generate_return_number` R1, Inputs (`year`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"SR-10-001"`.
2. B = return `"SR-1-001"`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=1)`.

**Then**
1. returns: `result == "SR-1-002"`.

### SRT-GN-12 — only numbers that start with exactly SR-2026- count
- **Rules:** `generate_return_number` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"XSR-2026-001"`.
2. B = return `"sr-2026-002"`.
3. C = return `" SR-2026-003"`.
4. D = return `"PR-2026-004"`.
5. E = return `"SR_2026-005"`.
6. G = return `"SR-20261-006"`.
7. H = return `"SR-2026-007"`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SR-2026-002"`.

### SRT-GN-13 — eight returns give -009 and nine give -010
- **Rules:** `generate_return_number` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(1, 9): db.add(SalesOrderReturn(workspace_id=W1.id, sales_order_id=SO2.id, return_number=f"SR-2026-{k:03d}", return_type="refund", created_by=U1.id, created_at=T1))`, then `db.flush()` (eight returns, -001 … -008).
2. `r8 = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.
3. `db.add(SalesOrderReturn(workspace_id=W1.id, sales_order_id=SO2.id, return_number="SR-2026-009", return_type="refund", created_by=U1.id, created_at=T1))`, then `db.flush()`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `r8 == "SR-2026-009"`.
2. returns: `result == "SR-2026-010"`.

### SRT-GN-14 — 998 returns give -999 and 999 give -1000
- **Rules:** `generate_return_number` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(1, 999): db.add(SalesOrderReturn(workspace_id=W1.id, sales_order_id=SO2.id, return_number=f"SR-2026-{k:03d}", return_type="refund", created_by=U1.id, created_at=T1))`, then `db.flush()` (998 returns).
2. `r998 = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.
3. `db.add(SalesOrderReturn(workspace_id=W1.id, sales_order_id=SO2.id, return_number="SR-2026-999", return_type="refund", created_by=U1.id, created_at=T1))`, then `db.flush()`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `r998 == "SR-2026-999"`.
2. returns: `result == "SR-2026-1000"`.

### SRT-GN-15 — writes nothing: a pending return is not counted and stays pending, an unflushed edit stays unflushed
- **Rules:** `generate_return_number` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = return `"SR-2025-001"`.
2. `B.notes = "Edited"` (not flushed).
3. `P = SalesOrderReturn(workspace_id=W1.id, sales_order_id=SO2.id, return_number="SR-2026-001", return_type="refund", created_by=U1.id, created_at=T1)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SR-2026-001"`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. nothing written: nothing written.

### SRT-GN-16 — the count reads only the returns table, in one SELECT
- **Rules:** `generate_return_number` R1, R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.
2. Statement recorder.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SR-2026-002"`.
2. statement: `len(selects) == 1`.
3. statement: `"sales_order_returns" in sql`.
4. statement: `"sales_orders" not in sql`.
5. statement: `"FOR UPDATE" not in sql`.

### SRT-GN-17 — the prefix is case-sensitive: lower- and mixed-case numbers do not count
- **Rules:** `generate_return_number` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"sr-2026-001"`.
2. B = return `"Sr-2026-002"`.
3. C = return `"sR-2026-003"`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "SR-2026-001"`.

## `DAOSalesOrderReturn.create_with_user`

### SRT-CW-01 — a return is created pending with the given fields and number -001
- **Rules:** `create_with_user` R1, R2a, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no return.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U2.id, return_type="replace", reason="Damaged", notes="Box torn")`.

**Then**
1. returns: `isinstance(result, SalesOrderReturn)`.
2. returns: `result.id is not None`.
3. re-read result: `workspace_id == W1.id`, `sales_order_id == SO2.id`, `return_number == "SR-2026-001"`, `return_type == "replace"`, `reason == "Damaged"`, `notes == "Box torn"`.
4. re-read result: `created_by == U2.id`, `status == "pending"`, `paid is False`.
5. re-read result: `invoice_id is None`, `completed_at is None`, `completed_by is None`, `updated_by is None`, `updated_at is None`.
6. count: `n(W1) == 1`.
7. count: `db.scalar(select(func.count()).select_from(SalesOrderReturnItem)) == 0`.

### SRT-CW-02 — the second return of the workspace gets -002
- **Rules:** `create_with_user` R2a
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_number == "SR-2026-002"`.
3. count: `n(W1) == 2`.

### SRT-CW-03 — returns of W0 and W2 do not count: W1's first return is -001
- **Rules:** `create_with_user` R2a, `generate_return_number` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = return `"SR-2026-101"` of W0.
2. X1 = return `"SR-2026-201"` of W2.
3. X2 = return `"SR-2026-202"` of W2.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_number == "SR-2026-001"`, `workspace_id == W1.id`.

### SRT-CW-04 — reason and notes not passed are stored as NULL
- **Rules:** `create_with_user` R1, Inputs (defaults)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no return.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U1.id, return_type="refund")` (no `reason`, no `notes`).

**Then**
1. returns: `result.id is not None`.
2. re-read result: `reason is None`, `notes is None`.

### SRT-CW-05 — empty reason and notes stay empty strings, spaces are kept
- **Rules:** `create_with_user` R1, Inputs (`reason`, `notes` as given)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no return.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U1.id, return_type="refund", reason="", notes="  Late ")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `reason == ""`, `notes == "  Late "`.

### SRT-CW-06 — any return_type is stored as given
- **Rules:** `create_with_user` R1, Inputs (`return_type` not checked)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no return.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U1.id, return_type="banana")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_type == "banana"`.

### SRT-CW-07 — created_at is naive UTC at flush
- **Rules:** `create_with_user` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No clock (nothing patched). W1 has no return.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U1.id, return_type="refund")`, with `before = utcnow()` right before and `after = utcnow()` right after.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `created_at.tzinfo is None`.
3. re-read result: `before <= created_at <= after`.
4. re-read result: `return_number.endswith("-001")`.

### SRT-CW-08 — created_at is naive UTC also when the database runs in Asia/Dhaka
- **Rules:** `create_with_user` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Dhaka.
2. No clock (nothing patched). W1 has no return.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U1.id, return_type="refund")`, with `before = utcnow()` right before and `after = utcnow()` right after.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `created_at.tzinfo is None`.
3. re-read result: `before <= created_at <= after`.

### SRT-CW-09 — the year is UTC's, when the local clock is already in the next year
- **Rules:** `create_with_user` R2 [BUG-2422]
- **Kind:** bug
- **Expect:** xfail BUG-2422
- **Fails today on:** Then 2 (the local year is used: `SR-2027-001`)

**Given**
1. W1 has no return.
2. clock(`datetime(2027, 1, 1, 5, 0)`, `datetime(2026, 12, 31, 23, 0)`).

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_number == "SR-2026-001"`.

### SRT-CW-10 — the year is UTC's, when the local clock is still in the old year
- **Rules:** `create_with_user` R2 [BUG-2422]
- **Kind:** bug
- **Expect:** xfail BUG-2422
- **Fails today on:** Then 2 (the local year is used: `SR-2026-001`)

**Given**
1. A = return `"SR-2026-001"`.
2. clock(`datetime(2026, 12, 31, 23, 0)`, `datetime(2027, 1, 1, 1, 0)`).

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_number == "SR-2027-001"`.

### SRT-CW-11 — the current year goes into the number: both clocks in 2031 give SR-2031-001
- **Rules:** `create_with_user` R2, R2a
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.
2. clock(`datetime(2031, 1, 1, 5, 0)`, `datetime(2031, 1, 1, 5, 0)`).

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_number == "SR-2031-001"`.

### SRT-CW-12 — W1's first return is -001 although W0 already has SR-2026-001
- **Rules:** `create_with_user` R4 [BUG-2420]
- **Kind:** bug
- **Expect:** xfail BUG-2420
- **Fails today on:** Then 1 (the call raises IntegrityError 23505: the number index is global)

**Given**
1. Z1 = return `"SR-2026-001"` of W0.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_number == "SR-2026-001"`, `workspace_id == W1.id`.
3. count: `n(W1) == 1`.
4. count: `n(W0) == 1`.

### SRT-CW-13 — W1's first return is -001 although W2 already has SR-2026-001
- **Rules:** `create_with_user` R4 [BUG-2420]
- **Kind:** bug
- **Expect:** xfail BUG-2420
- **Fails today on:** Then 1 (the call raises IntegrityError 23505: the number index is global)

**Given**
1. X1 = return `"SR-2026-001"` of W2.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_number == "SR-2026-001"`, `workspace_id == W1.id`.
3. count: `n(W1) == 1`.
4. count: `n(W2) == 1`.

### SRT-CW-14 — a computed number already taken in the same workspace does not fail the call: a free number is used
- **Rules:** `create_with_user` R3a [BUG-2421]
- **Kind:** bug
- **Expect:** xfail BUG-2421
- **Fails today on:** Then 1 (the call raises IntegrityError 23505: the count gives -004, which C already has)

**Given**
1. A = return `"SR-2026-001"`.
2. B = return `"SR-2026-002"`.
3. C = return `"SR-2026-004"`.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_number.startswith("SR-2026-")`.
3. re-read result: `return_number not in {"SR-2026-001", "SR-2026-002", "SR-2026-004"}`.
4. count: `db.scalar(select(func.count()).select_from(SalesOrderReturn).where(SalesOrderReturn.workspace_id == W1.id, SalesOrderReturn.return_number == result.return_number)) == 1`.
5. count: `n(W1) == 4`.

### SRT-CW-15 — user_id None fails NOT NULL at the flush and saves nothing
- **Rules:** `create_with_user` R5, Errors (`user_id is None`)
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no return.

**When**
- `dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=None, return_type="refund")`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23502"`.
2. raises: `"created_by" in str(exc.value.orig)`.
3. count: `n(W1) == 0`.
4. nothing written: nothing written.

### SRT-CW-16 — an unknown sales order fails the foreign key at the flush
- **Rules:** `create_with_user` R5, Errors (unknown `sales_order_id`)
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no return.

**When**
- `dao.create_with_user(db, workspace_id=W1.id, sales_order_id=MISSING, user_id=U1.id, return_type="refund")`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. raises: `"sales_order_id" in str(exc.value.orig)`.
3. count: `n(W1) == 0`.
4. nothing written: nothing written.

### SRT-CW-17 — an unknown workspace fails the foreign key at the flush
- **Rules:** `create_with_user` R5, Errors (unknown `workspace_id`)
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no return.

**When**
- `dao.create_with_user(db, workspace_id=MISSING, sales_order_id=SO2.id, user_id=U1.id, return_type="refund")`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. raises: `"workspace_id" in str(exc.value.orig)`.
3. nothing written: nothing written.

### SRT-CW-18 — flushed, not committed: a rollback removes the return
- **Rules:** `create_with_user` R5, Returns
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no return.
2. commit spy.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None` (inside).
2. count: `n(W1) == 1` (inside).
3. mock called: `cm.call_count == 0`.
4. count: `n(W1) == 0` (after `sp.rollback()`).

### SRT-CW-19 — one INSERT into the returns table and nothing else is written
- **Rules:** `create_with_user` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = return `"SR-2025-001"`.
2. Statement recorder.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. statement: `len(written) == 1`.
3. statement: `written[0].upper().startswith("INSERT INTO SALES_ORDER_RETURNS")`.
4. unchanged: unchanged(B).

### SRT-CW-20 — the status is pending whatever the database default, and paid is False
- **Rules:** `create_with_user` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`, but `status "completed"`, `paid True`.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, sales_order_id=SO2.id, user_id=U3.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `status == "pending"`, `paid is False`, `created_by == U3.id`, `return_number == "SR-2026-002"`.

### SRT-CW-21 — the database refuses a second row with the same number in one workspace (direct insert)
- **Rules:** `create_with_user` R4 (database fact), R3a, Errors (number already used)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.

**When**
- `db.add(SalesOrderReturn(workspace_id=W1.id, sales_order_id=SO2.id, return_number="SR-2026-001", return_type="refund", created_by=U1.id, created_at=T2)); db.flush()` (one step), inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23505"`.
2. count: `n(W1) == 1`.
3. re-read A: `return_number == "SR-2026-001"`, `created_at == T1`.

## `DAOSalesOrderReturn.get_by_sales_order`

### SRT-BS-01 — every return of the order is returned, whatever its status, newest first
- **Rules:** `get_by_sales_order` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`, but `created_at T2`.
2. B = return `"SR-2026-002"`, but `created_at T3`, `status "completed"`, `completed_at T4`, `completed_by U1.id`.
3. C = return `"SR-2026-003"`, but `created_at T1`, `status "voided"`, `updated_at T2`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id, C.id]`.

### SRT-BS-02 — returns of the orders with a lower and a higher id are not returned
- **Rules:** `get_by_sales_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`, but `sales_order_id SO1.id`, `created_at T3`.
2. B = return `"SR-2026-002"`, but `created_at T1`.
3. C = return `"SR-2026-003"`, but `sales_order_id SO3.id`, `created_at T4`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### SRT-BS-03 — returns of W0 and W2 on the same order id are not returned
- **Rules:** `get_by_sales_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = return `"SR-2026-101"` of W0, but `sales_order_id SO2.id`, `created_at T4`.
2. A = return `"SR-2026-001"`, but `created_at T1`.
3. X1 = return `"SR-2026-201"` of W2, but `sales_order_id SO2.id`, `created_at T5`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### SRT-BS-04 — the right order with another workspace's id returns an empty list
- **Rules:** `get_by_sales_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### SRT-BS-05 — asked for W0, only W0's return on the order is returned
- **Rules:** `get_by_sales_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = return `"SR-2026-101"` of W0, but `sales_order_id SO2.id`, `created_at T1`.
2. A = return `"SR-2026-001"`, but `created_at T2`.
3. X1 = return `"SR-2026-201"` of W2, but `sales_order_id SO2.id`, `created_at T3`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W0.id)`.

**Then**
1. returns: `ids(result) == [Z1.id]`.

### SRT-BS-06 — an order without returns and an unknown order return empty lists
- **Rules:** `get_by_sales_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.

**When**
- `result = (dao.get_by_sales_order(db, sales_order_id=SO3.id, workspace_id=W1.id), dao.get_by_sales_order(db, sales_order_id=MISSING, workspace_id=W1.id))` (one tuple).

**Then**
1. returns: `result[0] == []`.
2. returns: `result[1] == []`.

### SRT-BS-07 — newest first whatever the ids: an older return with a higher id comes last
- **Rules:** `get_by_sales_order` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"SR-2026-009"`, but `created_at T3`.
2. B = return `"SR-2026-002"`, but `created_at T4`, `created_by U3.id`.
3. C = return `"SR-2026-003"`, but `created_at T1 + timedelta(minutes=30)`, `created_by U2.id`.
4. D = return `"SR-2026-004"`, but `created_at T1`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id, C.id, D.id]`.

### SRT-BS-08 — on a tie both returns sit between the newer and the older one
- **Rules:** `get_by_sales_order` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`, but `created_at T2`.
2. N = return `"SR-2026-002"`, but `created_at T3`.
3. B = return `"SR-2026-003"`, but `created_at T2`.
4. O = return `"SR-2026-004"`, but `created_at T1`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == N.id`.
3. returns: `{result[1].id, result[2].id} == {A.id, B.id}`.
4. returns: `result[3].id == O.id`.

### SRT-BS-09 — on a tie the highest id comes first, when the lowest id was updated
- **Rules:** `get_by_sales_order` R3 [BUG-2423]
- **Kind:** bug
- **Expect:** xfail BUG-2423 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no tie-break; the result rests on physical row order)

**Given**
1. A = return `"SR-2026-001"`, but `created_at T2`.
2. B = return `"SR-2026-002"`, but `created_at T2`.
3. C = return `"SR-2026-003"`, but `created_at T2`.
4. D = return `"SR-2026-004"`, but `created_at T3`.
5. seqscan.
6. bump(A).

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [D.id, C.id, B.id, A.id]`.

### SRT-BS-10 — on a tie the id decides, not the number, status or creator
- **Rules:** `get_by_sales_order` R3 [BUG-2423]
- **Kind:** bug
- **Expect:** xfail BUG-2423 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no tie-break; the result rests on physical row order)

**Given**
1. A = return `"SR-2026-009"`, but `created_at T2`, `status "voided"`, `updated_at T2`, `created_by U3.id`.
2. B = return `"SR-2026-001"`, but `created_at T2`, `created_by U1.id`.
3. C = return `"SR-2026-005"`, but `created_at T2`, `status "completed"`, `created_by U2.id`.
4. seqscan.
5. bump(A).

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### SRT-BS-11 — the query orders by created_at, then id, both descending
- **Rules:** `get_by_sales_order` R3 [BUG-2423]
- **Kind:** bug
- **Expect:** xfail BUG-2423
- **Fails today on:** Then 4 (the query orders by `created_at` alone)

**Given**
1. A = return `"SR-2026-001"`.
2. Statement recorder.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"created_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("created_at") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.

### SRT-BS-12 — no paging: 101 returns all come back
- **Rules:** `get_by_sales_order` R1 (no paging)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(1, 102): db.add(SalesOrderReturn(workspace_id=W1.id, sales_order_id=SO2.id, return_number=f"SR-2026-{k:03d}", return_type="refund", created_by=U1.id, created_at=T1 + timedelta(minutes=k)))`, then `db.flush()`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `result[0].return_number == "SR-2026-101"`.
3. returns: `result[100].return_number == "SR-2026-001"`.

### SRT-BS-13 — writes nothing: a pending return is not listed and stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_sales_order` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.
2. `A.notes = "Edited"` (not flushed).
3. `P = SalesOrderReturn(workspace_id=W1.id, sales_order_id=SO2.id, return_number="SR-2026-002", return_type="refund", created_by=U1.id, created_at=T2)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `A in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. nothing written: nothing written.

### SRT-BS-14 — the list does not join the sales order
- **Rules:** `get_by_sales_order` R1, R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.
2. Statement recorder.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `len(selects) == 1`.
3. statement: `"sales_orders" not in sql`.
4. statement: `"FOR UPDATE" not in sql`.

### SRT-BS-15 — a return with an invoice and paid is listed like any other
- **Rules:** `get_by_sales_order` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`, but `invoice_id INV1.id`, `paid True`, `created_at T2`.
2. B = return `"SR-2026-002"`, but `created_at T1`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

## `DAOSalesOrderReturn.get_open_by_sales_order`

### SRT-OP-01 — only the pending returns are returned
- **Rules:** `get_open_by_sales_order` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.
2. B = return `"SR-2026-002"`, but `status "completed"`, `completed_at T2`, `completed_by U1.id`.
3. C = return `"SR-2026-003"`, but `status "voided"`, `updated_at T2`.
4. D = return `"SR-2026-004"`, but `created_at T2`.

**When**
- `result = dao.get_open_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id, D.id}`.
2. returns: `len(result) == 2`.

### SRT-OP-02 — the status must be exactly "pending": case, spaces and look-alikes do not match
- **Rules:** `get_open_by_sales_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`, but `status "Pending"`.
2. B = return `"SR-2026-002"`, but `status "PENDING"`.
3. C = return `"SR-2026-003"`, but `status " pending"`.
4. D = return `"SR-2026-004"`, but `status "pending "`.
5. E = return `"SR-2026-005"`, but `status "pend"`.
6. G = return `"SR-2026-006"`, but `status "xpendingx"`.
7. H = return `"SR-2026-007"`, but `status "pending_old"`.
8. K = return `"SR-2026-008"`.

**When**
- `result = dao.get_open_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [K.id]`.

### SRT-OP-03 — no pending return gives an empty list
- **Rules:** `get_open_by_sales_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = return `"SR-2026-002"`, but `status "completed"`, `completed_at T2`, `completed_by U1.id`.
2. C = return `"SR-2026-003"`, but `status "voided"`, `updated_at T2`.

**When**
- `result = dao.get_open_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SRT-OP-04 — pending returns of the orders with a lower and a higher id are not returned
- **Rules:** `get_open_by_sales_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`, but `sales_order_id SO1.id`.
2. B = return `"SR-2026-002"`.
3. C = return `"SR-2026-003"`, but `sales_order_id SO3.id`.

**When**
- `result = dao.get_open_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### SRT-OP-05 — pending returns of W0 and W2 on the same order id are not returned
- **Rules:** `get_open_by_sales_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = return `"SR-2026-101"` of W0, but `sales_order_id SO2.id`.
2. A = return `"SR-2026-001"`.
3. X1 = return `"SR-2026-201"` of W2, but `sales_order_id SO2.id`.

**When**
- `result = dao.get_open_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### SRT-OP-06 — another workspace's id or an unknown order returns empty lists
- **Rules:** `get_open_by_sales_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.

**When**
- `result = (dao.get_open_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W2.id), dao.get_open_by_sales_order(db, sales_order_id=MISSING, workspace_id=W1.id))` (one tuple).

**Then**
1. returns: `result[0] == []`.
2. returns: `result[1] == []`.

### SRT-OP-07 — pending returns come back by id ascending, when the lowest id was updated
- **Rules:** `get_open_by_sales_order` R3 [BUG-2424]
- **Kind:** bug
- **Expect:** xfail BUG-2424 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`; the result rests on physical row order)

**Given**
1. A = return `"SR-2026-001"`, but `created_at T3`.
2. B = return `"SR-2026-002"`, but `created_at T1`.
3. C = return `"SR-2026-003"`, but `created_at T2`.
4. seqscan.
5. bump(A).

**When**
- `result = dao.get_open_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### SRT-OP-08 — the query orders by id ascending
- **Rules:** `get_open_by_sales_order` R3 [BUG-2424]
- **Kind:** bug
- **Expect:** xfail BUG-2424
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = return `"SR-2026-001"`.
2. Statement recorder.

**When**
- `result = dao.get_open_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `"created_at" not in order_part`.

### SRT-OP-09 — writes nothing: a pending new return is not listed, an unflushed edit stays unflushed
- **Rules:** `get_open_by_sales_order` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.
2. `A.status = "voided"` (not flushed).
3. `P = SalesOrderReturn(workspace_id=W1.id, sales_order_id=SO2.id, return_number="SR-2026-002", return_type="refund", created_by=U1.id, created_at=T2)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.get_open_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `A in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. nothing written: nothing written.

### SRT-OP-10 — the list does not join the sales order and takes no lock
- **Rules:** `get_open_by_sales_order` R1, R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`.
2. Statement recorder.

**When**
- `result = dao.get_open_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `len(selects) == 1`.
3. statement: `"sales_orders" not in sql`.
4. statement: `"FOR UPDATE" not in sql`.

### SRT-OP-11 — asked for W0, only W0's pending return on the order is returned
- **Rules:** `get_open_by_sales_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = return `"SR-2026-101"` of W0, but `sales_order_id SO2.id`.
2. A = return `"SR-2026-001"`.
3. X1 = return `"SR-2026-201"` of W2, but `sales_order_id SO2.id`.

**When**
- `result = dao.get_open_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W0.id)`.

**Then**
1. returns: `ids(result) == [Z1.id]`.

## `DAOSalesOrderReturn.get_by_invoice_id`

### SRT-IV-01 — the return whose credit note is the invoice is returned
- **Rules:** `get_by_invoice_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`, but `invoice_id INV1.id`.
2. B = return `"SR-2026-002"`, but `invoice_id INV2.id`, `status "completed"`, `completed_at T2`, `completed_by U1.id`.
3. C = return `"SR-2026-003"`, but `invoice_id INV3.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=INV2.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, SalesOrderReturn)`.
2. returns: `result.id == B.id`.

### SRT-IV-02 — a voided return is still found by its credit note
- **Rules:** `get_by_invoice_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`, but `invoice_id INV2.id`, `status "voided"`, `updated_at T2`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=INV2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### SRT-IV-03 — returns on the invoices with a lower and a higher id do not answer
- **Rules:** `get_by_invoice_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`, but `invoice_id INV1.id`.
2. C = return `"SR-2026-003"`, but `invoice_id INV3.id`.
3. D = return `"SR-2026-004"` (no invoice).

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=INV2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### SRT-IV-04 — returns of W0 and W2 holding the invoice do not answer for W1
- **Rules:** `get_by_invoice_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = return `"SR-2026-101"` of W0, but `invoice_id INV2.id`.
2. X1 = return `"SR-2026-201"` of W2, but `invoice_id INV2.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=INV2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### SRT-IV-05 — with W0, W1 and W2 returns on the invoice, W1 gets its own
- **Rules:** `get_by_invoice_id` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = return `"SR-2026-101"` of W0, but `invoice_id INV2.id`.
2. A = return `"SR-2026-001"`, but `invoice_id INV2.id`.
3. X1 = return `"SR-2026-201"` of W2, but `invoice_id INV2.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=INV2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### SRT-IV-06 — an invoice no return points to, and an unknown invoice, give None
- **Rules:** `get_by_invoice_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`, but `invoice_id INV1.id`.

**When**
- `result = (dao.get_by_invoice_id(db, invoice_id=INV3.id, workspace_id=W1.id), dao.get_by_invoice_id(db, invoice_id=MISSING, workspace_id=W1.id))` (one tuple).

**Then**
1. returns: `result[0] is None`.
2. returns: `result[1] is None`.

### SRT-IV-07 — two returns on one invoice: one of them is returned
- **Rules:** `get_by_invoice_id` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`, but `invoice_id INV2.id`.
2. B = return `"SR-2026-002"`, but `invoice_id INV2.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=INV2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is not None`.
2. returns: `result.id in {A.id, B.id}`.

### SRT-IV-08 — writes nothing: a pending return is not found, an unflushed edit stays unflushed
- **Rules:** `get_by_invoice_id` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`, but `invoice_id INV1.id`.
2. `A.paid = True` (not flushed).
3. `P = SalesOrderReturn(workspace_id=W1.id, sales_order_id=SO2.id, return_number="SR-2026-002", return_type="refund", created_by=U1.id, created_at=T1, invoice_id=INV2.id)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=INV2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `A in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. nothing written: nothing written.

### SRT-IV-09 — the lookup reads only the returns table and takes no lock
- **Rules:** `get_by_invoice_id` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = return `"SR-2026-001"`, but `invoice_id INV2.id`.
2. Statement recorder.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=INV2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. statement: `len(selects) == 1`.
3. statement: `"account_invoices" not in sql`.
4. statement: `"FOR UPDATE" not in sql`.

### SRT-IV-10 — invoice_id None finds the workspace's return whose credit note was deleted
- **Rules:** `get_by_invoice_id` R4, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = return `"SR-2026-101"` of W0 (no `invoice_id`).
2. A = return `"SR-2026-001"`, but `invoice_id INV1.id`.
3. B = return `"SR-2026-002"`, but `invoice_id INV3.id`, `status "completed"`, `completed_at T2`, `completed_by U1.id`.
4. X = return `"SR-2026-201"` of W2 (no `invoice_id`).
5. `db.execute(text("DELETE FROM account_invoices WHERE id = :i"), {"i": INV3.id})`, then `db.expire_all()`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=None, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.
2. returns: `result.invoice_id is None`.

### SRT-IV-11 — invoice_id None gives None when every return of the workspace has a credit note
- **Rules:** `get_by_invoice_id` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = return `"SR-2026-101"` of W0 (no `invoice_id`).
2. A = return `"SR-2026-001"`, but `invoice_id INV1.id`.
3. B = return `"SR-2026-002"`, but `invoice_id INV2.id`.
4. X = return `"SR-2026-201"` of W2 (no `invoice_id`).

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=None, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

## `DAOSalesOrderReturnItem.get_by_return`

### SRT-RI-01 — every line of the return is returned, with and without a catalog item
- **Rules:** `get_by_return` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. R = return `"SR-2026-001"`.
2. A = line on R.
3. B = line on R, but `item_id IT1.id`, `quantity_returned Decimal("3.00")`, `unit_price None`, `notes "Cracked"`.

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id, B.id}`.
2. returns: `len(result) == 2`.
3. returns: `all(isinstance(r, SalesOrderReturnItem) for r in result)`.

### SRT-RI-02 — lines of the returns with a lower and a higher id are not returned
- **Rules:** `get_by_return` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. RA = return `"SR-2026-001"`.
2. RB = return `"SR-2026-002"`.
3. RC = return `"SR-2026-003"`.
4. A = line on RA.
5. B = line on RB.
6. C = line on RC.

**When**
- `result = idao.get_by_return(db, return_id=RB.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### SRT-RI-03 — lines of W0 and W2 on the same return are not returned
- **Rules:** `get_by_return` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R = return `"SR-2026-001"`.
2. Z = line on R, but `workspace_id W0.id`.
3. A = line on R.
4. X = line on R, but `workspace_id W2.id`.

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### SRT-RI-04 — another workspace's id, a return without lines and an unknown return give empty lists
- **Rules:** `get_by_return` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. R = return `"SR-2026-001"`.
2. R2 = return `"SR-2026-002"`.
3. A = line on R.

**When**
- `result = (idao.get_by_return(db, return_id=R.id, workspace_id=W2.id), idao.get_by_return(db, return_id=R2.id, workspace_id=W1.id), idao.get_by_return(db, return_id=MISSING, workspace_id=W1.id))` (one tuple).

**Then**
1. returns: `result[0] == []`.
2. returns: `result[1] == []`.
3. returns: `result[2] == []`.

### SRT-RI-05 — quantities and prices come back half up, as the columns store them
- **Rules:** `get_by_return` R1; model facts (`Numeric(15,2)`); HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. R = return `"SR-2026-001"`.
2. A = line on R, but `quantity_returned Decimal("2.125")`, `unit_price Decimal("0.005")`.
3. `db.expire_all()`

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].quantity_returned == Decimal("2.13")`.
3. returns: `result[0].unit_price == Decimal("0.01")`.

### SRT-RI-06 — a negative price rounds away from zero, and 2.124 rounds down
- **Rules:** `get_by_return` R1; model facts (`Numeric(15,2)`); HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. R = return `"SR-2026-001"`.
2. A = line on R, but `quantity_returned Decimal("2.124")`, `unit_price Decimal("-1.005")`.
3. `db.expire_all()`

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `result[0].quantity_returned == Decimal("2.12")`.
3. returns: `result[0].unit_price == Decimal("-1.01")`.

### SRT-RI-07 — lines come back by id ascending, when the lowest id was updated
- **Rules:** `get_by_return` R3 [BUG-2425]
- **Kind:** bug
- **Expect:** xfail BUG-2425 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`; the result rests on physical row order)

**Given**
1. R = return `"SR-2026-001"`.
2. A = line on R, but `quantity_returned Decimal("3.00")`.
3. B = line on R, but `quantity_returned Decimal("1.00")`.
4. C = line on R, but `quantity_returned Decimal("2.00")`.
5. seqscan.
6. bumpL(A).

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### SRT-RI-08 — the query orders by id ascending
- **Rules:** `get_by_return` R3 [BUG-2425]
- **Kind:** bug
- **Expect:** xfail BUG-2425
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. R = return `"SR-2026-001"`.
2. A = line on R.
3. Statement recorder.

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.

### SRT-RI-09 — writes nothing: a pending line is not listed, an unflushed edit stays unflushed
- **Rules:** `get_by_return` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. R = return `"SR-2026-001"`.
2. A = line on R.
3. `A.notes = "Edited"` (not flushed).
4. `P = SalesOrderReturnItem(workspace_id=W1.id, return_id=R.id, so_item_id=L1.id, item_id=None, quantity_returned=Decimal("1.00"), unit_price=Decimal("2.00"))`
5. `db.add(P)` (not flushed).
6. Statement recorder.

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `A in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. nothing written: nothing written.

### SRT-RI-10 — the list does not join the return
- **Rules:** `get_by_return` R1, R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. R = return `"SR-2026-001"`.
2. A = line on R.
3. Statement recorder.

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `len(selects) == 1`.
3. statement: `"sales_order_returns" not in sql`.
4. statement: `"FOR UPDATE" not in sql`.

### SRT-RI-11 — asked for W2, only the W2 line on the return is returned
- **Rules:** `get_by_return` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R = return `"SR-2026-001"`.
2. Z = line on R, but `workspace_id W0.id`.
3. A = line on R.
4. X = line on R, but `workspace_id W2.id`.

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X.id]`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `create_with_user` R3 [BUG-2421] | integration test / `SalesService.start_return` | Two concurrent `start_return` calls in one workspace both succeed with distinct numbers (two transactions; the spec says not unit-testable). |
| Inputs (`return_type` allowed values) | `SalesOrderReturnCreate` schema / sales service spec | Only `replace` / `refund` are accepted; the DAO stores anything. |
| Overview (callers) | `SalesOrderReturnManager.has_open_return`, `SalesManager.complete_order` | An order with a pending return cannot be completed. |
| FU-1 (a)–(d) | sales service / return manager spec | `ret.items` order, HR-10 locks in `complete_return` / `void_return` / `start_return`, unique `invoice_id`, unit-price fallback. |
| Inherited `BaseDAO` methods | `tests/unit/dao/base.cases.md` | `get_by_id_and_workspace`, `create` of both classes. |

## Spec gaps
None. Revision 1's gaps 1–4 are closed by the spec's Gap log (G1, G4, G5; G2, G3 and G6 came from the coordinator), 2026-11-10.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `generate_return_number` | R1 | SRT-GN-01, GN-02, GN-11, GN-12, GN-16 |
| `generate_return_number` | R1a | SRT-GN-12, GN-17 |
| `generate_return_number` | R2 | SRT-GN-03, GN-04 |
| `generate_return_number` | R3 | SRT-GN-05, GN-06, GN-07, GN-08, GN-09, GN-10 |
| `generate_return_number` | R4 | SRT-GN-13, GN-14 |
| `generate_return_number` | R5 | SRT-GN-15, GN-16 |
| `create_with_user` | R1 | SRT-CW-01, CW-04, CW-05, CW-06, CW-07, CW-08, CW-20 |
| `create_with_user` | R2 [BUG-2422] | SRT-CW-09, CW-10 (xfail); CW-11 (pass) |
| `create_with_user` | R2a | SRT-CW-01, CW-02, CW-03, CW-11, CW-20 |
| `create_with_user` | R3 [BUG-2421] | Deferred (not unit-testable) |
| `create_with_user` | R3a [BUG-2421] | SRT-CW-14 (xfail); CW-21 (pass, direct insert) |
| `create_with_user` | R4 [BUG-2420] | SRT-CW-12, CW-13 (xfail); CW-21 (pass) |
| `create_with_user` | R5 | SRT-CW-15, CW-16, CW-17, CW-18 |
| `create_with_user` | Errors: number used (23505) | SRT-CW-21 (through the call only today; CW-14 is the fixed path) |
| `create_with_user` | Errors: `user_id None` (23502) | SRT-CW-15 |
| `create_with_user` | Errors: unknown order / workspace (23503) | SRT-CW-16, CW-17 |
| `create_with_user` | Side effects | SRT-CW-01, CW-19 |
| `get_by_sales_order` | R1 | SRT-BS-01, BS-12, BS-14, BS-15 |
| `get_by_sales_order` | R2 | SRT-BS-02, BS-03, BS-04, BS-05, BS-06 |
| `get_by_sales_order` | R3 [BUG-2423] | SRT-BS-01, BS-07, BS-08 (pass); BS-09, BS-10 (non-strict), BS-11 (strict) |
| `get_by_sales_order` | Side effects none | SRT-BS-13 |
| `get_open_by_sales_order` | R1 | SRT-OP-01, OP-02, OP-03, OP-10 |
| `get_open_by_sales_order` | R2 | SRT-OP-04, OP-05, OP-06, OP-11 |
| `get_open_by_sales_order` | R3 [BUG-2424] | SRT-OP-07 (non-strict), OP-08 (strict) |
| `get_open_by_sales_order` | Side effects none | SRT-OP-09 |
| `get_by_invoice_id` | R1 | SRT-IV-01, IV-02, IV-05, IV-09 |
| `get_by_invoice_id` | R2 | SRT-IV-03, IV-04, IV-05, IV-06 |
| `get_by_invoice_id` | R3 | SRT-IV-07 |
| `get_by_invoice_id` | R4 | SRT-IV-10, IV-11 |
| `get_by_invoice_id` | Side effects none | SRT-IV-08 |
| `get_by_return` | R1 | SRT-RI-01, RI-02, RI-05, RI-06, RI-10 |
| `get_by_return` | R2 | SRT-RI-03, RI-04, RI-11 |
| `get_by_return` | R3 [BUG-2425] | SRT-RI-07 (non-strict), RI-08 (strict) |
| `get_by_return` | Side effects none | SRT-RI-09 |
