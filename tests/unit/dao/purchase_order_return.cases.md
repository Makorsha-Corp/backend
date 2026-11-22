# Test cases — `app/dao/purchase_order_return.py`

> **Spec:** `tests/unit/dao/purchase_order_return.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-09; fill-gaps 2026-11-10, nothing open). P1–P3 and D1 were decided by Claude under the reviewer's delegation; none is the owner's own answer. No owner question (OQ-25 … OQ-28) touches this module, so there is no pending section.
> **Revision:** 2 (2026-11-10) — spec fill-gaps G1–G6 (no owner question for this DAO). G2: **voided** now writes `status`, `paid`, `updated_at` and leaves `updated_by` `NULL` (convention only; no card's checks change). G3: the year patch target `app.dao.purchase_order_return.utcnow` is now the spec's; clock(L, U) unchanged. G4 / new R3a [BUG-2427]: PRT-CW-12 now states the intended behaviour (a taken next number never fails the call) as a strict xfail; the 23505 fact moves to the new direct-insert card PRT-CW-18. G5 / new `get_by_invoice_id` R4: PRT-IN-11, IN-12. G6 / new `generate_return_number` R1a: PRT-GN-17. G1: parent-row facts recorded; the unchecked recipe stays (the DAO reads no parent). No ID retired.
> **Revision:** 3 (2026-11-10) — `purchase_order_return.verify.md` findings 1–2, both `case-missing`. F1: new PRT-CW-19, both clocks in 2031 → `PR-2031-001` (twin of SRT-CW-11), the pass half of BUG-2428. F2: PRT-OP-13, PO-15, IN-10, RI-11 gain a last Then line `"FOR UPDATE" not in sql` (no read takes a lock). Conventions gain "No-lock check" and "Clear the session before a one-query check". No ID retired.
> **Counts:** 90 cases · 75 expected-to-pass · 15 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `generate_return_number` 17 · `create_with_user` 19 (5 bug) · `get_by_purchase_order` 17 (4 bug) · `get_open_by_purchase_order` 14 (3 bug) · `get_by_invoice_id` 12 · `DAOPurchaseOrderReturnItem.get_by_return` 11 (3 bug).
- **Depth:** full (skill step 1a). Returns move stock and carry a credit note (money), and the numbering is an order-workflow decision (BUG-726/727 precedents), so every boundary is tested on both sides.
- **Expected-to-fail:** BUG-2426 2 strict (PRT-CW-10 with the number held by W2, CW-11 held by W0) · BUG-2428 2 strict (CW-08, CW-09: the two directions across a new year) · BUG-2429 3 non-strict + 1 strict SQL alarm (PO-10, PO-11, PO-12; PO-13) · BUG-2430 2 non-strict + 1 strict (OP-10, OP-11, OP-12) · BUG-2431 2 non-strict + 1 strict (RI-08, RI-09, RI-10). BUG-2427 1 strict (CW-12, R3a: a taken next number gets a free one); its race half (R3) stays deferred to an integration test.
- **Notable design choices:**
  - The return number is unique across **all** workspaces today (BUG-2426), so in every card other than CW-10 / CW-11 the returns of W0 and W2 carry numbers W1 never computes (`PR-2026-005` …). Isolation of the count is still checked on both sides (W0 built before W1, W2 after).
  - Purchase orders, return lines and credit-note invoice ids are built with foreign-key triggers off (**unchecked**, the recipe of the verified `purchase_order_approver.cases.md` and of the spec's own runs): orders need a status and a destination, lines a PO line, and the DAO reads none of them. Returns themselves are built with triggers on, except where a card sets `invoice_id`.
  - Order filters always sit between a lower and a higher order id of W1 (O1 < O2 < O3, filter O2); invoice filters between IVA < IVB < IVC.
  - Tie cards follow the house recipe (seqscan, then an update of the lowest id; and an explicit `HIGH_ID` row) and are non-strict; each of the three queries has one strict statement alarm, and `get_by_purchase_order` keeps a pass statement card for the `created_at DESC` that holds today.
  - HR-15: the DAO computes no money, but `get_by_return` hands back the stored `Numeric(15,2)` values the credit note is priced from; RI-07 checks half-up storage (2.125 → 2.13, 0.005 → 0.01, -1.005 → -1.01) and RI-11 the control (2.124 → 2.12).
  - The `created_at` card CW-02 runs under Dhaka with no clock patched, so a database `now()` default would show as six hours off.
  - Cards marked `Author: claude`: the seven non-strict tie cards. Race simulations: none.
  - CW-12 asserts only "succeeds, `PR-2026-`, a number unused in W1" (spec R3a), so a counter fix and a retry fix both pass it. CW-18 keeps the database's 23505 for a same-workspace duplicate as a direct insert, true under every fix. Parallel to the sales twin (SRT-CW-14).
- **Needs a decision:** None. Gaps 1–4 of revision 1 are closed by the spec's Gap log (2026-11-10).

## Conventions for this module

**IDs.** `PRT` = `app/dao/purchase_order_return.py`. `GN` generate_return_number · `CW` create_with_user · `PO` get_by_purchase_order · `OP` get_open_by_purchase_order · `IN` get_by_invoice_id · `RI` `DAOPurchaseOrderReturnItem.get_by_return`.

**Actors and fixed values.**
- `dao` = `purchase_order_return_dao`, `idao` = `purchase_order_return_item_dao` (both `from app.dao.purchase_order_return import ...`). `db` = the test's real session, first argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- `PurchaseOrderReturn`, `PurchaseOrderReturnItem` = classes of `app.models.purchase_order_return`. `PurchaseOrder` = `app.models.purchase_order.PurchaseOrder`. `Item` = `app.models.item.Item`. `IntegrityError` = `sqlalchemy.exc.IntegrityError`. `text`, `select`, `func` = sqlalchemy's. `Decimal`, `datetime`, `patch` = the usual ones. `utcnow` = `app.utils.time.utcnow`.
- MISSING = `999999999`. IVA, IVB, IVC = `880000001`, `880000002`, `880000003` (credit-note invoice ids; no `account_invoices` row has them).
- T1 … T5 = `datetime(2026, 3, 4, 9, 0)`, `(…, 10, 0)`, `(…, 11, 0)`, `(…, 12, 0)`, `(…, 13, 0)` (naive).
- HIGH_ID(table) = `max(greatest id of the table or 0, last_value of <table>_id_seq) + 1000001`, read when the row is built.

**Externals.** Only in `CW` cards. **clock(L, U)** = for the When, patch `app.dao.purchase_order_return.datetime` with a subclass of `datetime` whose `now()` returns L, and patch `app.dao.purchase_order_return.utcnow` (with `create=True`) and `app.utils.time.utcnow` to return U. A `CW` card without a clock line runs under clock(`datetime(2026, 6, 1, 12, 0)`, `datetime(2026, 6, 1, 12, 0)`), unless it says "no clock".

**Standing rows** (every test, this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` three times, so `W0.id < W1.id < W2.id`. U1, U2, U3 = `make_profile(db)` three times.
2. I1 = `Item(workspace_id=W1.id, name="Bolt", name_normalized="bolt", unit="pcs")`.
3. unchecked: O0, O1, O2, O3, O9 = `PurchaseOrder(workspace_id=…, po_number=…, destination_type="storage", destination_id=MISSING, subtotal=0, total_amount=0, current_status_id=MISSING, created_by=U1.id)` with (W0, `"PO-T-000"`), (W1, `"PO-T-001"`), (W1, `"PO-T-002"`), (W1, `"PO-T-003"`), (W2, `"PO-T-009"`). So `O1.id < O2.id < O3.id`. Never `UPDATE` an order.

**Given rows.** Inserted directly (never through the DAOs), flushed one at a time in the order written. After "but" a line lists every column that differs. A line written as code is a step to run exactly. `db.add(...)` without `db.flush()` leaves the row pending.
- **unchecked: …** = run `db.execute(text("SET LOCAL session_replication_role = replica"))`, then the rows named, then `db.execute(text("SET LOCAL session_replication_role = origin"))`.
- **return N** = `PurchaseOrderReturn(workspace_id=W1.id, purchase_order_id=O2.id, return_number=N, return_type="refund", created_by=U1.id)`; `status` left to its default `"pending"`, `created_at` left to its default unless the card gives it. A return with `invoice_id` set is built unchecked.
- **completed** (on a return) = `status "completed"`, `completed_at T4`, `completed_by U1.id`. **voided** = `status "voided"`, `paid False`, `updated_at T4`; `updated_by` stays `NULL` (a real void does not write it).
- **line of R** = unchecked: `PurchaseOrderReturnItem(workspace_id=W1.id, return_id=R.id, po_item_id=MISSING, item_id=I1.id, quantity_returned=Decimal("2.00"))`.
- **seqscan** = `SET LOCAL enable_indexscan = off`, `SET LOCAL enable_bitmapscan = off`, `SET LOCAL enable_indexonlyscan = off`, each through `db.execute(text(...))`.
- **bumpR(X)** = `db.execute(text("UPDATE purchase_order_returns SET reason = reason WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`. **bumpL(X)** = unchecked: `db.execute(text("UPDATE purchase_order_return_items SET notes = notes WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`.

**Named checks.**
- **ids(result)** = `[r.id for r in result]`, order part of the check. **idset(result)** = `{r.id for r in result}`.
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. **unchanged(X)** = after re-read every column of X equals its value before the call.
- **wcount(W)** = `db.scalar(text("SELECT count(*) FROM purchase_order_returns WHERE workspace_id = :w"), {"w": W.id})`.
- **nothing written** = the numbers of `purchase_order_returns` and `purchase_order_return_items` rows (all workspaces) equal their values before the call.
- `pending:` lines check the session directly after the call, before anything expires it.
- `raises: IntegrityError` = `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards. Later `raises:` lines assert on `exc.value.orig`, one per line.
- **commit spy** = `sp = db.begin_nested()` directly before the call, `with patch.object(db, "commit", wraps=db.commit) as cm:` around it; "inside the savepoint" lines first, then `sp.rollback()`, then the later lines.
- **Statement recorder** = the SQL the session sends during the When is recorded. `sql` = the one `SELECT` sent; `order_part` = text of `sql` after its first `ORDER BY`, before any `LIMIT` (`""` if none); `lock_part` = text of `sql` after `FOR UPDATE` (`""` if none); `written` = every recorded `INSERT`, `UPDATE`, `DELETE`.
- **No-lock check** = `"FOR UPDATE" not in sql`. Never use `lock_part == ""` for this: Postgres prints the lock clause last, so the text after `FOR UPDATE` is empty with a lock as well.
- **Clear the session before a one-query check**: a card that counts the SELECTs a call sends (or reads stored values back) ends its Given with `db.expunge_all()` (or `db.expire_all()` where the card says so), so a row the identity map still holds (a profile, a just-inserted value) cannot hide a second read. Ids used in Then come from objects built before it; their loaded attributes stay readable.
- **Dhaka** = `db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))` as the first Given step.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. Write the call and the checks exactly as shown; never weaken a non-strict assertion.

**Race simulations.** None (BUG-2427 is deferred to an integration test).

## `DAOPurchaseOrderReturn.generate_return_number`

### PRT-GN-01 — no return yet gives PR-2026-001, whatever the other workspaces hold
- **Rules:** `generate_return_number` R1, R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A0 = return `"PR-2026-005"`, but `workspace_id W0.id`, `purchase_order_id O0.id`.
2. B0 = return `"PR-2026-006"`, but `workspace_id W0.id`, `purchase_order_id O0.id`.
3. A9 = return `"PR-2026-007"`, but `workspace_id W2.id`, `purchase_order_id O9.id`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "PR-2026-001"`.

### PRT-GN-02 — one return gives PR-2026-002
- **Rules:** `generate_return_number` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"PR-2026-001"`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "PR-2026-002"`.

### PRT-GN-03 — only W1's returns count, with more returns in W0 and W2 than in W1
- **Rules:** `generate_return_number` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0, B0, C0 = return `"PR-2026-011"`, `"PR-2026-012"`, `"PR-2026-013"`, each but `workspace_id W0.id`, `purchase_order_id O0.id`.
2. A = return `"PR-2026-001"`.
3. B = return `"PR-2026-002"`.
4. A9, B9, C9 = return `"PR-2026-021"`, `"PR-2026-022"`, `"PR-2026-023"`, each but `workspace_id W2.id`, `purchase_order_id O9.id`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "PR-2026-003"`.

### PRT-GN-04 — asked for W2, the earlier W1 and W0 returns do not count
- **Rules:** `generate_return_number` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = return `"PR-2026-011"`, but `workspace_id W0.id`, `purchase_order_id O0.id`.
2. A = return `"PR-2026-001"`.
3. B = return `"PR-2026-002"`.
4. A9 = return `"PR-2026-021"`, but `workspace_id W2.id`, `purchase_order_id O9.id`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W2.id, year=2026)`.

**Then**
1. returns: `result == "PR-2026-002"`.

### PRT-GN-05 — asked for W0, the later W1 and W2 returns do not count
- **Rules:** `generate_return_number` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = return `"PR-2026-011"`, but `workspace_id W0.id`, `purchase_order_id O0.id`.
2. A = return `"PR-2026-001"`.
3. B = return `"PR-2026-002"`.
4. A9 = return `"PR-2026-021"`, but `workspace_id W2.id`, `purchase_order_id O9.id`.
5. B9 = return `"PR-2026-022"`, but `workspace_id W2.id`, `purchase_order_id O9.id`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W0.id, year=2026)`.

**Then**
1. returns: `result == "PR-2026-002"`.

### PRT-GN-06 — pending, completed and voided returns all count
- **Rules:** `generate_return_number` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"PR-2026-001"`.
2. B = return `"PR-2026-002"`, but completed.
3. C = return `"PR-2026-003"`, but voided.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "PR-2026-004"`.

### PRT-GN-07 — a hand-made PR-2026-XYZ counts as one
- **Rules:** `generate_return_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"PR-2026-XYZ"`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "PR-2026-002"`.

### PRT-GN-08 — returns of the year before and after do not count
- **Rules:** `generate_return_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"PR-2025-001"`.
2. B = return `"PR-2027-001"`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "PR-2026-001"`.

### PRT-GN-09 — year 2099 starts at 001 while 2026 has returns
- **Rules:** `generate_return_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"PR-2026-001"`.
2. B = return `"PR-2026-002"`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2099)`.

**Then**
1. returns: `result == "PR-2099-001"`.

### PRT-GN-10 — year 1 is used as given, and PR-10- does not count for it
- **Rules:** `generate_return_number` Inputs (`year`), R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"PR-1-005"`.
2. B = return `"PR-10-001"`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=1)`.

**Then**
1. returns: `result == "PR-1-002"`.

### PRT-GN-11 — only numbers that start with the prefix count
- **Rules:** `generate_return_number` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"XPR-2026-001"`.
2. B = return `" PR-2026-002"` (leading space).
3. C = return `"PR-2026003"` (no dash after the year).
4. D = return `"OLD-PR-2026-004"`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "PR-2026-001"`.

### PRT-GN-12 — a count of 8 gives 009
- **Rules:** `generate_return_number` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(1, 9): db.add(PurchaseOrderReturn(workspace_id=W1.id, purchase_order_id=O2.id, return_number=f"PR-2026-{k:03d}", return_type="refund", created_by=U1.id)); db.flush()`

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "PR-2026-009"`.

### PRT-GN-13 — a count of 9 gives 010
- **Rules:** `generate_return_number` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(1, 10): db.add(PurchaseOrderReturn(workspace_id=W1.id, purchase_order_id=O2.id, return_number=f"PR-2026-{k:03d}", return_type="refund", created_by=U1.id)); db.flush()`

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "PR-2026-010"`.

### PRT-GN-14 — a count of 998 gives 999
- **Rules:** `generate_return_number` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(1, 999): db.add(PurchaseOrderReturn(workspace_id=W1.id, purchase_order_id=O2.id, return_number=f"PR-2026-{k:03d}", return_type="refund", created_by=U1.id))`, then `db.flush()` once.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "PR-2026-999"`.

### PRT-GN-15 — a count of 999 gives 1000
- **Rules:** `generate_return_number` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(1, 1000): db.add(PurchaseOrderReturn(workspace_id=W1.id, purchase_order_id=O2.id, return_number=f"PR-2026-{k:03d}", return_type="refund", created_by=U1.id))`, then `db.flush()` once.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "PR-2026-1000"`.

### PRT-GN-16 — writes nothing: a pending return stays pending and is not counted, an unflushed edit stays unflushed
- **Rules:** `generate_return_number` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = return `"PR-2025-001"`.
2. `B.reason = "Edited"` (not flushed).
3. `P = PurchaseOrderReturn(workspace_id=W1.id, purchase_order_id=O2.id, return_number="PR-2026-001", return_type="refund", created_by=U1.id)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "PR-2026-001"`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. nothing written: nothing written.

### PRT-GN-17 — lower- and mixed-case pr-2026- numbers do not count (the prefix is case-sensitive)
- **Rules:** `generate_return_number` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"pr-2026-001"`.
2. B = return `"Pr-2026-002"`.
3. C = return `"PR-2026-003"`.

**When**
- `result = dao.generate_return_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "PR-2026-002"`.

## `DAOPurchaseOrderReturn.create_with_user`

### PRT-CW-01 — a return is created pending with the given fields and the first number
- **Rules:** `create_with_user` R1, R2a, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no return.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=O2.id, user_id=U2.id, return_type="replace", reason="Damaged", notes="Box crushed")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W1.id`, `purchase_order_id == O2.id`, `return_type == "replace"`, `reason == "Damaged"`, `notes == "Box crushed"`.
3. re-read result: `created_by == U2.id`, `status == "pending"`, `paid is False`, `return_number == "PR-2026-001"`.
4. re-read result: `invoice_id is None`, `completed_at is None`, `completed_by is None`, `updated_by is None`, `updated_at is None`.

### PRT-CW-02 — created_at is naive UTC at the flush, not the database's local clock
- **Rules:** `create_with_user` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Dhaka.
2. No clock: this card patches nothing.
3. `before = utcnow()`.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=O2.id, user_id=U1.id, return_type="refund"); after = utcnow()` (one step).

**Then**
1. re-read result: `result.created_at.tzinfo is None`.
2. re-read result: `before <= result.created_at <= after`.

### PRT-CW-03 — reason and notes default to None
- **Rules:** `create_with_user` Inputs (`reason`, `notes`), R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no return.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=O2.id, user_id=U1.id, return_type="refund")` (`reason`, `notes` not sent).

**Then**
1. returns: `result.id is not None`.
2. re-read result: `reason is None`, `notes is None`, `return_type == "refund"`.

### PRT-CW-04 — empty reason and notes are stored as empty strings
- **Rules:** `create_with_user` Inputs (`reason`, `notes`), R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no return.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=O2.id, user_id=U1.id, return_type="refund", reason="", notes="")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `reason == ""`, `notes == ""`.

### PRT-CW-05 — an unknown return_type is stored as given
- **Rules:** `create_with_user` Inputs (`return_type`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no return.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=O2.id, user_id=U1.id, return_type="banana")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_type == "banana"`.

### PRT-CW-06 — the second return gets the next number
- **Rules:** `create_with_user` R2a
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"PR-2026-001"`.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=O2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id != A.id`.
2. re-read result: `return_number == "PR-2026-002"`.
3. count: `wcount(W1) == 2`.

### PRT-CW-07 — returns of W0 and W2 do not count toward W1's number
- **Rules:** `create_with_user` R2a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A0 = return `"PR-2026-005"`, but `workspace_id W0.id`, `purchase_order_id O0.id`.
2. A9 = return `"PR-2026-006"`, but `workspace_id W2.id`, `purchase_order_id O9.id`.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=O2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_number == "PR-2026-001"`, `workspace_id == W1.id`.

### PRT-CW-08 — the year comes from UTC when the local clock is already in the next year
- **Rules:** `create_with_user` R2 [BUG-2428]
- **Kind:** bug
- **Expect:** xfail BUG-2428
- **Fails today on:** Then 2 (the local year is used: `PR-2027-001`)

**Given**
1. W1 has no return.
2. clock(`datetime(2027, 1, 1, 5, 0)`, `datetime(2026, 12, 31, 23, 0)`).

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=O2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_number == "PR-2026-001"`.

### PRT-CW-09 — the year comes from UTC when the local clock is still in the year before
- **Rules:** `create_with_user` R2 [BUG-2428]
- **Kind:** bug
- **Expect:** xfail BUG-2428
- **Fails today on:** Then 2 (the local year is used: `PR-2026-001`)

**Given**
1. W1 has no return.
2. clock(`datetime(2026, 12, 31, 22, 0)`, `datetime(2027, 1, 1, 3, 0)`).

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=O2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_number == "PR-2027-001"`.

### PRT-CW-10 — W1's first return succeeds while W2 already has PR-2026-001
- **Rules:** `create_with_user` R4 [BUG-2426]
- **Kind:** bug
- **Expect:** xfail BUG-2426
- **Fails today on:** Then 1 (the call raises IntegrityError 23505: the unique index is global)

**Given**
1. A9 = return `"PR-2026-001"`, but `workspace_id W2.id`, `purchase_order_id O9.id`.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=O2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_number == "PR-2026-001"`, `workspace_id == W1.id`.
3. count: `wcount(W2) == 1`.

### PRT-CW-11 — W1's first return succeeds while W0 already has PR-2026-001
- **Rules:** `create_with_user` R4 [BUG-2426]
- **Kind:** bug
- **Expect:** xfail BUG-2426
- **Fails today on:** Then 1 (the call raises IntegrityError 23505: the unique index is global)

**Given**
1. A0 = return `"PR-2026-001"`, but `workspace_id W0.id`, `purchase_order_id O0.id`.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=O2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_number == "PR-2026-001"`, `workspace_id == W1.id`.
3. count: `wcount(W0) == 1`.

### PRT-CW-12 — a taken next number never fails the call: the return gets a free number
- **Rules:** `create_with_user` R3a [BUG-2427], R2a
- **Kind:** bug
- **Expect:** xfail BUG-2427
- **Fails today on:** Then 1 (the call raises IntegrityError 23505: the count gives `PR-2026-004`, which is taken)

**Given**
1. A = return `"PR-2026-001"`.
2. B = return `"PR-2026-002"`.
3. C = return `"PR-2026-004"`.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=O2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_number.startswith("PR-2026-")`.
3. re-read result: `return_number not in {"PR-2026-001", "PR-2026-002", "PR-2026-004"}`.
4. count: `wcount(W1) == 4`.
5. count: `db.scalar(text("SELECT count(*) FROM purchase_order_returns WHERE workspace_id = :w AND return_number = :n"), {"w": W1.id, "n": result.return_number}) == 1`.

### PRT-CW-13 — user_id None fails NOT NULL at the flush and saves nothing
- **Rules:** `create_with_user` Inputs (`user_id`), R5, Errors (`user_id is None`)
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no return.

**When**
- `dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=O2.id, user_id=None, return_type="refund")`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23502"`.
2. count: `wcount(W1) == 0`.

### PRT-CW-14 — an unknown purchase order fails the foreign key at the flush and saves nothing
- **Rules:** `create_with_user` Inputs (`purchase_order_id`), R5, Errors (unknown order)
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no return.

**When**
- `dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=MISSING, user_id=U1.id, return_type="refund")`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. count: `wcount(W1) == 0`.

### PRT-CW-15 — an unknown workspace fails the foreign key at the flush and saves nothing
- **Rules:** `create_with_user` R5, Errors (unknown workspace)
- **Kind:** error
- **Expect:** pass

**Given**
1. `before = db.scalar(text("SELECT count(*) FROM purchase_order_returns"))`.

**When**
- `dao.create_with_user(db, workspace_id=MISSING, purchase_order_id=O2.id, user_id=U1.id, return_type="refund")`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. count: `db.scalar(text("SELECT count(*) FROM purchase_order_returns")) == before`.

### PRT-CW-16 — flushed, not committed: a rollback removes the return
- **Rules:** `create_with_user` R5, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no return.
2. commit spy.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=O2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `wcount(W1) == 1`.
3. count: after the savepoint rollback, `wcount(W1) == 0`.
4. mock called: `cm.call_count == 0`.

### PRT-CW-17 — writes one return row and nothing else
- **Rules:** `create_with_user` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = return `"PR-2026-001"`.
2. `items_before = db.scalar(text("SELECT count(*) FROM purchase_order_return_items"))`.
3. Statement recorder.

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=O2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. statement: `len(written) == 1`.
3. statement: `written[0].lstrip().upper().startswith("INSERT INTO PURCHASE_ORDER_RETURNS")`.
4. count: `wcount(W1) == 2`.
5. count: `db.scalar(text("SELECT count(*) FROM purchase_order_return_items")) == items_before`.
6. unchanged: unchanged(A).

### PRT-CW-18 — the database refuses a second row with the same number in one workspace (direct insert)
- **Rules:** `create_with_user` R4 (database fact kept under R3a), Errors (number already used)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = return `"PR-2026-001"`.

**When**
- `db.add(PurchaseOrderReturn(workspace_id=W1.id, purchase_order_id=O2.id, return_number="PR-2026-001", return_type="refund", created_by=U1.id)); db.flush()` (one step; the DAO is not called), inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23505"`.
2. count: `wcount(W1) == 1`.
3. unchanged: unchanged(A).

### PRT-CW-19 — the current year goes into the number: both clocks in 2031 give PR-2031-001
- **Rules:** `create_with_user` R2, R2a
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"PR-2026-001"`.
2. clock(`datetime(2031, 1, 1, 5, 0)`, `datetime(2031, 1, 1, 5, 0)`).

**When**
- `result = dao.create_with_user(db, workspace_id=W1.id, purchase_order_id=O2.id, user_id=U1.id, return_type="refund")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `return_number == "PR-2031-001"`.

## `DAOPurchaseOrderReturn.get_by_purchase_order`

### PRT-PO-01 — every return of the order is returned, whatever its status, newest first
- **Rules:** `get_by_purchase_order` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"PR-T-01"`, but `created_at T1`.
2. B = return `"PR-T-02"`, but `created_at T2`, completed.
3. C = return `"PR-T-03"`, but `created_at T3`, voided.

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.

### PRT-PO-02 — returns of the orders just below and above are not returned
- **Rules:** `get_by_purchase_order` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X1 = return `"PR-T-01"`, but `purchase_order_id O1.id`, `created_at T5`.
2. A = return `"PR-T-02"`, but `created_at T2`.
3. X3 = return `"PR-T-03"`, but `purchase_order_id O3.id`, `created_at T4`.

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PRT-PO-03 — a return of the same order id under W0 or W2 is not returned
- **Rules:** `get_by_purchase_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = return `"PR-T-00"`, but `workspace_id W0.id`, `created_at T5`. (Order O2 of W1, on purpose: invalid data, HR-16.)
2. A = return `"PR-T-01"`, but `created_at T2`.
3. X9 = return `"PR-T-09"`, but `workspace_id W2.id`, `created_at T4`. (Order O2, on purpose.)

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PRT-PO-04 — asked for W2, only the W2 return is returned, though the W1 and W0 returns are earlier
- **Rules:** `get_by_purchase_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = return `"PR-T-00"`, but `workspace_id W0.id`, `created_at T5`.
2. A = return `"PR-T-01"`, but `created_at T4`.
3. X9 = return `"PR-T-09"`, but `workspace_id W2.id`, `created_at T2`.

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X9.id]`.

### PRT-PO-05 — the right order with another workspace's id returns an empty list
- **Rules:** `get_by_purchase_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = return `"PR-T-01"`, but `created_at T2`.

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PRT-PO-06 — an unknown order returns an empty list
- **Rules:** `get_by_purchase_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"PR-T-01"`, but `created_at T2`.

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PRT-PO-07 — an order without returns returns an empty list
- **Rules:** `get_by_purchase_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"PR-T-01"`, but `created_at T2`.

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=O3.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PRT-PO-08 — newest first, whatever the ids
- **Rules:** `get_by_purchase_order` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"PR-T-01"`, but `created_at T2`.
2. B = return `"PR-T-02"`, but `created_at T4`.
3. C = return `"PR-T-03"`, but `created_at T1`.
4. D = return `"PR-T-04"`, but `created_at T3`.

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, D.id, A.id, C.id]`.

### PRT-PO-09 — on a tie both returns sit between the newer and the older one
- **Rules:** `get_by_purchase_order` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"PR-T-01"`, but `created_at T1`.
2. B = return `"PR-T-02"`, but `created_at T2`.
3. C = return `"PR-T-03"`, but `created_at T2`.
4. D = return `"PR-T-04"`, but `created_at T3`.

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == D.id`.
3. returns: `{result[1].id, result[2].id} == {B.id, C.id}`.
4. returns: `result[3].id == A.id`.

### PRT-PO-10 — on a tie the highest id comes first, when the lowest id was updated
- **Rules:** `get_by_purchase_order` R3 [BUG-2429]
- **Kind:** bug
- **Expect:** xfail BUG-2429 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no tie-break; physical row order decides)

**Given**
1. A = return `"PR-T-01"`, but `created_at T2`.
2. B = return `"PR-T-02"`, but `created_at T2`.
3. C = return `"PR-T-03"`, but `created_at T2`.
4. D = return `"PR-T-04"`, but `created_at T2`.
5. seqscan.
6. bumpR(A).

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [D.id, C.id, B.id, A.id]`.

### PRT-PO-11 — on a tie the id decides, when number, type, status, creator and reason would sort otherwise
- **Rules:** `get_by_purchase_order` R3 [BUG-2429]
- **Kind:** bug
- **Expect:** xfail BUG-2429 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no tie-break; physical row order decides)

**Given**
1. A = return `"PR-T-09"`, but `created_at T2`, `return_type "replace"`, `created_by U3.id`, `reason "Zinc"`.
2. B = return `"PR-T-01"`, but `created_at T2`, completed, `created_by U2.id`, `reason "Alpha"`.
3. C = return `"PR-T-05"`, but `created_at T2`, voided, `reason "Mid"`.
4. seqscan.
5. bumpR(A).

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### PRT-PO-12 — on a tie a row with a high explicit id comes first
- **Rules:** `get_by_purchase_order` R3 [BUG-2429]
- **Kind:** bug
- **Expect:** xfail BUG-2429 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no tie-break; physical row order decides)

**Given**
1. EB = return `"PR-T-01"`, but `created_at T2`.
2. EC = return `"PR-T-02"`, but `created_at T2`, `id HIGH_ID(purchase_order_returns)`.
3. EA = return `"PR-T-03"`, but `created_at T2`.

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [EC.id, EA.id, EB.id]`.

### PRT-PO-13 — the query orders by created_at, then id, both descending
- **Rules:** `get_by_purchase_order` R3 [BUG-2429]
- **Kind:** bug
- **Expect:** xfail BUG-2429
- **Fails today on:** Then 3 (the query orders by `created_at` alone)

**Given**
1. A = return `"PR-T-01"`, but `created_at T2`.
2. Statement recorder.

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"created_at" in order_part`.
3. statement: `".id" in order_part`.
4. statement: `order_part.index("created_at") < order_part.index(".id")`.
5. statement: `order_part.upper().count("DESC") == 2`.
6. statement: `order_part.count(",") == 1`.

### PRT-PO-14 — the query orders by created_at descending first
- **Rules:** `get_by_purchase_order` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"PR-T-01"`, but `created_at T2`.
2. Statement recorder.

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `order_part.lstrip().split()[0].endswith("created_at")`.
3. statement: `order_part.upper().split()[1].rstrip(",") == "DESC"`.

### PRT-PO-15 — writes nothing and does not read the purchase order
- **Rules:** `get_by_purchase_order` Side effects, R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = return `"PR-T-01"`, but `created_at T2`.
2. `A.reason = "Edited"` (not flushed).
3. `P = PurchaseOrderReturn(workspace_id=W1.id, purchase_order_id=O2.id, return_number="PR-T-02", return_type="refund", created_by=U1.id)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `A in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"purchase_orders" not in sql`.
8. nothing written: nothing written.
9. statement: `"FOR UPDATE" not in sql`.

### PRT-PO-16 — no paging: 101 returns are all returned
- **Rules:** `get_by_purchase_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(101): db.add(PurchaseOrderReturn(workspace_id=W1.id, purchase_order_id=O2.id, return_number=f"PR-T-{k:03d}", return_type="refund", created_by=U1.id, created_at=T1 + timedelta(minutes=k)))`, then `db.flush()` once.

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `result[0].return_number == "PR-T-100"`.
3. returns: `result[100].return_number == "PR-T-000"`.

### PRT-PO-17 — asked for the higher order O3, the returns of O2 below it are not mixed in
- **Rules:** `get_by_purchase_order` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = return `"PR-T-01"`, but `created_at T2`.
2. B = return `"PR-T-02"`, but `created_at T3`.
3. X3 = return `"PR-T-03"`, but `purchase_order_id O3.id`, `created_at T1`.

**When**
- `result = dao.get_by_purchase_order(db, purchase_order_id=O3.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [X3.id]`.

## `DAOPurchaseOrderReturn.get_open_by_purchase_order`

### PRT-OP-01 — only the pending return is returned, not the completed or voided one
- **Rules:** `get_open_by_purchase_order` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = return `"PR-T-01"`, but completed.
2. A = return `"PR-T-02"`.
3. C = return `"PR-T-03"`, but voided.

**When**
- `result = dao.get_open_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PRT-OP-02 — two pending returns are both returned
- **Rules:** `get_open_by_purchase_order` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = return `"PR-T-01"`.
2. C = return `"PR-T-02"`, but completed.
3. B = return `"PR-T-03"`.

**When**
- `result = dao.get_open_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `idset(result) == {A.id, B.id}`.

### PRT-OP-03 — a hand-set "Pending" in capitals is not open
- **Rules:** `get_open_by_purchase_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"PR-T-01"`, but `status "Pending"`.
2. B = return `"PR-T-02"`.

**When**
- `result = dao.get_open_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### PRT-OP-04 — a status with a leading space or a trailing letter is not open
- **Rules:** `get_open_by_purchase_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"PR-T-01"`, but `status " pending"`.
2. B = return `"PR-T-02"`, but `status "pendings"`.
3. C = return `"PR-T-03"`, but `status "pend"`.

**When**
- `result = dao.get_open_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PRT-OP-05 — pending returns of the orders just below and above are not returned
- **Rules:** `get_open_by_purchase_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X1 = return `"PR-T-01"`, but `purchase_order_id O1.id`.
2. A = return `"PR-T-02"`.
3. X3 = return `"PR-T-03"`, but `purchase_order_id O3.id`.

**When**
- `result = dao.get_open_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PRT-OP-06 — a pending return of the same order id under W0 or W2 is not returned
- **Rules:** `get_open_by_purchase_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = return `"PR-T-00"`, but `workspace_id W0.id`. (Order O2, on purpose: invalid data, HR-16.)
2. A = return `"PR-T-01"`.
3. X9 = return `"PR-T-09"`, but `workspace_id W2.id`. (Order O2, on purpose.)

**When**
- `result = dao.get_open_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PRT-OP-07 — asked for W2, only the W2 pending return is returned
- **Rules:** `get_open_by_purchase_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = return `"PR-T-00"`, but `workspace_id W0.id`.
2. A = return `"PR-T-01"`.
3. X9 = return `"PR-T-09"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_open_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X9.id]`.

### PRT-OP-08 — an unknown order returns an empty list
- **Rules:** `get_open_by_purchase_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"PR-T-01"`.

**When**
- `result = dao.get_open_by_purchase_order(db, purchase_order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PRT-OP-09 — an order whose returns are all completed or voided returns an empty list
- **Rules:** `get_open_by_purchase_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = return `"PR-T-01"`, but completed.
2. B = return `"PR-T-02"`, but voided.

**When**
- `result = dao.get_open_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PRT-OP-10 — ids ascending, when the lowest id was updated
- **Rules:** `get_open_by_purchase_order` R3 [BUG-2430]
- **Kind:** bug
- **Expect:** xfail BUG-2430 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`; physical row order puts A last)

**Given**
1. A = return `"PR-T-01"`, but `created_at T1`.
2. B = return `"PR-T-02"`, but `created_at T3`.
3. C = return `"PR-T-03"`, but `created_at T2`.
4. seqscan.
5. bumpR(A).

**When**
- `result = dao.get_open_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PRT-OP-11 — a row with a high explicit id comes last
- **Rules:** `get_open_by_purchase_order` R3 [BUG-2430]
- **Kind:** bug
- **Expect:** xfail BUG-2430 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`; physical row order decides)

**Given**
1. EB = return `"PR-T-01"`.
2. EC = return `"PR-T-02"`, but `id HIGH_ID(purchase_order_returns)`.
3. EA = return `"PR-T-03"`.

**When**
- `result = dao.get_open_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [EB.id, EA.id, EC.id]`.

### PRT-OP-12 — the query orders by id ascending
- **Rules:** `get_open_by_purchase_order` R3 [BUG-2430]
- **Kind:** bug
- **Expect:** xfail BUG-2430
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = return `"PR-T-01"`.
2. Statement recorder.

**When**
- `result = dao.get_open_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### PRT-OP-13 — writes nothing and does not read the purchase order
- **Rules:** `get_open_by_purchase_order` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = return `"PR-T-01"`.
2. `A.notes = "Edited"` (not flushed).
3. `P = PurchaseOrderReturn(workspace_id=W1.id, purchase_order_id=O2.id, return_number="PR-T-02", return_type="refund", created_by=U1.id)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.get_open_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `A in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"purchase_orders" not in sql`.
8. nothing written: nothing written.
9. statement: `"FOR UPDATE" not in sql`.

### PRT-OP-14 — the right order with another workspace's id returns an empty list
- **Rules:** `get_open_by_purchase_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = return `"PR-T-01"`.

**When**
- `result = dao.get_open_by_purchase_order(db, purchase_order_id=O2.id, workspace_id=W0.id)`.

**Then**
1. returns: `result == []`.

## `DAOPurchaseOrderReturn.get_by_invoice_id`

### PRT-IN-01 — the return whose credit note is the invoice is returned, between neighbours below and above
- **Rules:** `get_by_invoice_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. unchecked: XA = return `"PR-T-01"`, but `invoice_id IVA`.
2. unchecked: A = return `"PR-T-02"`, but `invoice_id IVB`.
3. unchecked: XC = return `"PR-T-03"`, but `invoice_id IVC`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PRT-IN-02 — a completed return is found by its credit note
- **Rules:** `get_by_invoice_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. unchecked: A = return `"PR-T-01"`, but `invoice_id IVB`, completed.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.status == "completed"`.

### PRT-IN-03 — a voided return is found by its credit note
- **Rules:** `get_by_invoice_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. unchecked: A = return `"PR-T-01"`, but `invoice_id IVB`, voided.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.status == "voided"`.

### PRT-IN-04 — an invoice no return holds returns None, with returns on the invoices below and above
- **Rules:** `get_by_invoice_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. unchecked: XA = return `"PR-T-01"`, but `invoice_id IVA`.
2. unchecked: XC = return `"PR-T-03"`, but `invoice_id IVC`.
3. B = return `"PR-T-02"` (no invoice).

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRT-IN-05 — an unknown invoice id returns None
- **Rules:** `get_by_invoice_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. unchecked: A = return `"PR-T-01"`, but `invoice_id IVB`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRT-IN-06 — the credit note of a W2 return is not found from W1
- **Rules:** `get_by_invoice_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. unchecked: X9 = return `"PR-T-09"`, but `workspace_id W2.id`, `purchase_order_id O9.id`, `invoice_id IVB`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRT-IN-07 — the credit note of a W0 return is not found from W1
- **Rules:** `get_by_invoice_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. unchecked: X0 = return `"PR-T-00"`, but `workspace_id W0.id`, `purchase_order_id O0.id`, `invoice_id IVB`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PRT-IN-08 — asked for W2, the W2 return is found, though W0 and W1 hold the same invoice id earlier
- **Rules:** `get_by_invoice_id` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. unchecked: X0 = return `"PR-T-00"`, but `workspace_id W0.id`, `purchase_order_id O0.id`, `invoice_id IVB`.
2. unchecked: A = return `"PR-T-01"`, but `invoice_id IVB`.
3. unchecked: X9 = return `"PR-T-09"`, but `workspace_id W2.id`, `purchase_order_id O9.id`, `invoice_id IVB`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=W2.id)`.

**Then**
1. returns: `result.id == X9.id`.

### PRT-IN-09 — two returns on one invoice: one of them is returned
- **Rules:** `get_by_invoice_id` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. unchecked: A = return `"PR-T-01"`, but `invoice_id IVB`.
2. unchecked: B = return `"PR-T-02"`, but `invoice_id IVB`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=W1.id)`.

**Then**
1. returns: `result.id in {A.id, B.id}`.

### PRT-IN-10 — writes nothing: a pending return stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_invoice_id` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. unchecked: A = return `"PR-T-01"`, but `invoice_id IVB`.
2. `A.reason = "Edited"` (not flushed).
3. `P = PurchaseOrderReturn(workspace_id=W1.id, purchase_order_id=O2.id, return_number="PR-T-02", return_type="refund", created_by=U1.id)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=IVB, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `A in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. nothing written: nothing written.
8. statement: `"FOR UPDATE" not in sql`.

### PRT-IN-11 — invoice_id None returns W1's return without a credit note, not those of W0 or W2
- **Rules:** `get_by_invoice_id` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A0 = return `"PR-T-90"`, but `workspace_id W0.id`, `purchase_order_id O0.id`.
2. unchecked: B = return `"PR-T-01"`, but `invoice_id IVB`.
3. A = return `"PR-T-02"`.
4. A9 = return `"PR-T-99"`, but `workspace_id W2.id`, `purchase_order_id O9.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=None, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.invoice_id is None`.

### PRT-IN-12 — invoice_id None returns None when every W1 return has a credit note
- **Rules:** `get_by_invoice_id` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A0 = return `"PR-T-90"`, but `workspace_id W0.id`, `purchase_order_id O0.id`.
2. unchecked: A = return `"PR-T-01"`, but `invoice_id IVA`.
3. unchecked: B = return `"PR-T-02"`, but `invoice_id IVB`.
4. A9 = return `"PR-T-99"`, but `workspace_id W2.id`, `purchase_order_id O9.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=None, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

## `DAOPurchaseOrderReturnItem.get_by_return`

### PRT-RI-01 — every line of the return is returned, not the lines of the returns just below and above
- **Rules:** `get_by_return` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. RA = return `"PR-T-01"`.
2. R = return `"PR-T-02"`.
3. RC = return `"PR-T-03"`.
4. XA = line of RA.
5. L1 = line of R.
6. L2 = line of R, but `quantity_returned Decimal("3.00")`.
7. L3 = line of R, but `unit_price Decimal("4.50")`, `notes "Cracked"`.
8. XC = line of RC.

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `idset(result) == {L1.id, L2.id, L3.id}`.

### PRT-RI-02 — a line of W0 or W2 on the same return is not returned
- **Rules:** `get_by_return` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R = return `"PR-T-01"`.
2. X0 = line of R, but `workspace_id W0.id`. (Invalid data, HR-16, on purpose.)
3. L1 = line of R.
4. X9 = line of R, but `workspace_id W2.id`.

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [L1.id]`.

### PRT-RI-03 — asked for W2, only the W2 line is returned
- **Rules:** `get_by_return` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. R = return `"PR-T-01"`.
2. X0 = line of R, but `workspace_id W0.id`.
3. L1 = line of R.
4. X9 = line of R, but `workspace_id W2.id`.

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X9.id]`.

### PRT-RI-04 — an unknown return returns an empty list
- **Rules:** `get_by_return` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. R = return `"PR-T-01"`.
2. L1 = line of R.

**When**
- `result = idao.get_by_return(db, return_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PRT-RI-05 — a return without lines returns an empty list
- **Rules:** `get_by_return` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. R = return `"PR-T-01"`.
2. RB = return `"PR-T-02"`.
3. L1 = line of R.

**When**
- `result = idao.get_by_return(db, return_id=RB.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PRT-RI-06 — no paging: 101 lines are all returned
- **Rules:** `get_by_return` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. R = return `"PR-T-01"`.
2. unchecked: `for k in range(101): db.add(PurchaseOrderReturnItem(workspace_id=W1.id, return_id=R.id, po_item_id=MISSING, item_id=I1.id, quantity_returned=Decimal("2.00")))`, then `db.flush()` once.

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.

### PRT-RI-07 — stored quantities and prices come back rounded half up, as exact Decimals
- **Rules:** `get_by_return` R1; Model facts (`quantity_returned`, `unit_price` Numeric(15,2)); HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. R = return `"PR-T-01"`.
2. LA = line of R, but `quantity_returned Decimal("2.125")`, `unit_price Decimal("0.005")`.
3. LB = line of R, but `quantity_returned Decimal("1.00")`, `unit_price Decimal("-1.005")`.
4. `db.expire_all()`

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {LA.id, LB.id}`.
2. returns: `{r.id: r.quantity_returned for r in result}[LA.id] == Decimal("2.13")`.
3. returns: `{r.id: r.unit_price for r in result}[LA.id] == Decimal("0.01")`.
4. returns: `{r.id: r.unit_price for r in result}[LB.id] == Decimal("-1.01")`.
5. returns: `isinstance({r.id: r.quantity_returned for r in result}[LA.id], Decimal)`.

### PRT-RI-08 — ids ascending, when the lowest id was updated
- **Rules:** `get_by_return` R3 [BUG-2431]
- **Kind:** bug
- **Expect:** xfail BUG-2431 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`; physical row order puts A last)

**Given**
1. R = return `"PR-T-01"`.
2. A = line of R, but `quantity_returned Decimal("9.00")`.
3. B = line of R, but `quantity_returned Decimal("1.00")`.
4. C = line of R, but `quantity_returned Decimal("5.00")`.
5. seqscan.
6. bumpL(A).

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### PRT-RI-09 — a line with a high explicit id comes last
- **Rules:** `get_by_return` R3 [BUG-2431]
- **Kind:** bug
- **Expect:** xfail BUG-2431 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`; physical row order decides)

**Given**
1. R = return `"PR-T-01"`.
2. EB = line of R.
3. EC = line of R, but `id HIGH_ID(purchase_order_return_items)`.
4. EA = line of R.

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [EB.id, EA.id, EC.id]`.

### PRT-RI-10 — the query orders by id ascending
- **Rules:** `get_by_return` R3 [BUG-2431]
- **Kind:** bug
- **Expect:** xfail BUG-2431
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. R = return `"PR-T-01"`.
2. L1 = line of R.
3. Statement recorder.

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [L1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### PRT-RI-11 — writes nothing, does not read the return, and a 2.124 quantity comes back as 2.12
- **Rules:** `get_by_return` Side effects, R1; HR-15 (control)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. R = return `"PR-T-01"`.
2. L1 = line of R, but `quantity_returned Decimal("2.124")`.
3. `db.expire_all()`
4. `R.notes = "Edited"` (not flushed).
5. `P = PurchaseOrderReturn(workspace_id=W1.id, purchase_order_id=O2.id, return_number="PR-T-02", return_type="refund", created_by=U1.id)`
6. `db.add(P)` (not flushed).
7. Statement recorder.

**When**
- `result = idao.get_by_return(db, return_id=R.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [L1.id]`.
2. returns: `result[0].quantity_returned == Decimal("2.12")`.
3. pending: `P in db.new`.
4. pending: `len(db.new) == 1`.
5. pending: `R in db.dirty`.
6. pending: `len(db.dirty) == 1`.
7. statement: `written == []`.
8. statement: `"purchase_order_returns" not in sql`.
9. nothing written: nothing written.
10. statement: `"FOR UPDATE" not in sql`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `create_with_user` R3 [BUG-2427] | integration test (two transactions) | Two concurrent creates in one workspace both succeed with distinct numbers; spec: not unit-testable. |
| `create_with_user` Inputs (`return_type`) | `PurchaseOrderReturnCreate` schema / `PurchaseOrderService.start_return` | Only `replace` / `refund` accepted (422 otherwise). |
| FU-1 (a), (b), (d) | `PurchaseOrderService` return methods, `PurchaseOrderReturnManager` | `ret.items` order; HR-10 locks on complete / void / start; unit price fallback. |
| FU-1 (c) / D1 | return-flow spec (migration) | Unique index on `invoice_id` where not null. |
| FU-2 | `PurchaseOrderManager.mark_order_complete` | `has_open_return` reads only `pending`. |
| Inherited `BaseDAO` methods | `tests/unit/dao/base.cases.md` | `get_by_id_and_workspace`, `create` of the return and its lines. |

## Spec gaps
None. The revision 1 gaps are closed by the spec's Gap log (2026-11-10): 1 → `generate_return_number` R1a (PRT-GN-17); 2 → Externals name `app.dao.purchase_order_return.utcnow` (clock(L, U) already patches it); 3 → parent-row facts in Notes (the unchecked recipe stays: no card reads a parent); 4 → a void writes `status`, `paid`, `updated_at`, not `updated_by` (**voided** updated).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `generate_return_number` | R1 | PRT-GN-01, GN-02, GN-10, GN-11 |
| | R1a | PRT-GN-17 |
| | R2 | PRT-GN-06, GN-07 |
| | R3 | PRT-GN-01, GN-03, GN-04, GN-05, GN-08, GN-09 |
| | R4 | PRT-GN-12, GN-13, GN-14, GN-15 |
| | R5 | PRT-GN-16 |
| | Inputs (`year`) | PRT-GN-10 |
| `create_with_user` | R1 | PRT-CW-01, CW-02, CW-03, CW-04 |
| | R2 [BUG-2428] | PRT-CW-08, CW-09 (xfail); CW-01 (same-year control) |
| | R2a | PRT-CW-01, CW-06, CW-07 |
| | R3 [BUG-2427] | Deferred (not unit-testable) |
| | R3a [BUG-2427] | PRT-CW-12 (xfail) |
| | R4 [BUG-2426] | PRT-CW-10, CW-11 (xfail); CW-18 (same workspace refused, direct insert) |
| | R5 | PRT-CW-13, CW-14, CW-15, CW-16 |
| | Inputs (`return_type`) | PRT-CW-05; schema half deferred |
| | Errors: number used (23505) | PRT-CW-18 |
| | Errors: `user_id None` (23502) | PRT-CW-13 |
| | Errors: unknown order / workspace (23503) | PRT-CW-14, CW-15 |
| | Side effects | PRT-CW-16, CW-17 |
| `get_by_purchase_order` | R1 | PRT-PO-01, PO-02, PO-16, PO-17 |
| | R2 | PRT-PO-02 … PO-07, PO-17 |
| | R3 [BUG-2429] | PRT-PO-01, PO-08, PO-09, PO-14 (pass); PO-10, PO-11, PO-12 (non-strict), PO-13 (strict) |
| | Side effects | PRT-PO-15 |
| `get_open_by_purchase_order` | R1 | PRT-OP-01, OP-02, OP-03, OP-04, OP-09 |
| | R2 | PRT-OP-05, OP-06, OP-07, OP-08, OP-14 |
| | R3 [BUG-2430] | PRT-OP-10, OP-11 (non-strict), OP-12 (strict) |
| | Side effects | PRT-OP-13 |
| `get_by_invoice_id` | R1 | PRT-IN-01, IN-02, IN-03, IN-08 |
| | R2 | PRT-IN-04, IN-05, IN-06, IN-07, IN-08 |
| | R3 (D1) | PRT-IN-09 |
| | R4 | PRT-IN-11, IN-12 |
| | Side effects | PRT-IN-10 |
| `get_by_return` | R1 | PRT-RI-01, RI-05, RI-06, RI-07, RI-11 |
| | R2 | PRT-RI-01, RI-02, RI-03, RI-04 |
| | R3 [BUG-2431] | PRT-RI-08, RI-09 (non-strict), RI-10 (strict) |
| | Side effects | PRT-RI-11 |
| | Model facts / HR-15 | PRT-RI-07, RI-11 |
| `create_with_user` | R2, R2a (year from the clock, pass half of BUG-2428) | PRT-CW-19 |
| reads | Overview "takes no lock" | PRT-OP-13, PO-15, IN-10, RI-11 |
