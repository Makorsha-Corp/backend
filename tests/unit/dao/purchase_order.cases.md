# Test cases — `app/dao/purchase_order.py`

> **Spec:** `tests/unit/dao/purchase_order.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-11; nothing open). The owner answered OQ-35 … OQ-38 on 2026-11-11: BUG-2639, BUG-2640, BUG-2641; OQ-36 intended.
> **Revision:** 2 (2026-11-14) — owner answers and spec Gap log G1–G6. OQ-35 → BUG-2639: OQ35-01 … 04 are now strict xfail (voided POs add nothing to total / open value, are never open); new pass twin AS-10 (a voided PO still counts in total count and not-invoiced count, R3b). OQ-36 intended: OQ36-01 … 06 are plain passes. OQ-37 → BUG-2640: OQ37-02, 03, 05 strict xfail (draft / voided invoices are not outstanding); OQ37-01, 04, 06 stay pass; new OQ37-07 (locked, partial, overdue kept). OQ-38 → BUG-2641: OQ38-01 … 07 check R2 key by key (pass before and after the fix; 01 and 06 no longer compare the whole dict); new strict xfail OQ38-08 … 10 for `quantity_refunded_total` (R2a). G1 / G2: model module and `current_status` named; new LH-13, LD-10, GI-08 (status loaded). G3: new AL-29, AL-30 patch `_po_number_taken` (xfail BUG-2630); AL-20 / AL-21 stay as today's path, to retire at the BUG-2630 fix. G4: components are hard-deleted — HF-24 redesigned (a removed component no longer matches), new HF-61 (soft-deleted project still counts). G5 / G6: real invoice void and PO void columns in Conventions (VX now resets `paid_amount`, `payment_status`); HF-38 and OQ35-04 say they use legacy data. New Deferred row FU-5. No ID retired.
> **Counts:** 242 cases · 204 expected-to-pass · 38 expected-to-fail (bugs) · 9 deferred

## Reviewer summary
- **Per callable:** hub filters (`HF`, through `list_for_hub`) 61 (6 bug) + outstanding payment (OQ37) 7 (3 bug) · `list_for_hub` 13 · `count_for_hub` 8 · `list_recent_for_hub` 10 (3 bug) · `get_pending_highlights_for_hub` 17 (6 bug) · `aggregate_hub_stats` 10 + voided (OQ35) 4 (4 bug) + open value (OQ36) 6 · `list_for_destination` 10 · `get_by_id_and_workspace` 8 · `get_by_invoice_id` 12 (3 bug) · `allocate_po_number` 30 (7 bug) · item `get_by_order` 8 · item `get_by_purchase_order_ids` 5 · item `get_by_id_and_workspace` 6 · `summarize_by_purchase_order_ids` 4 + sums / refunded (OQ38) 10 (3 bug) · `preview_names_by_purchase_order_ids` 13 (3 bug).
- **Expected-to-fail by bug:** BUG-2633 5 strict (HF-51 … HF-55) · BUG-2634 1 strict (HF-56) · BUG-2635 4 strict + 2 non-strict (RH-01, RH-05, PH-03, PH-05; RH-04, PH-04) · BUG-2636 2 non-strict + 1 strict (PH-10, PH-11; PH-12) · BUG-2637 2 non-strict + 1 strict (GV-07, GV-08; GV-09) · BUG-2638 2 non-strict + 1 strict (IN-10, IN-11; IN-12) · BUG-2630 5 strict (AL-17 … AL-19, AL-29, AL-30) · BUG-2632 2 strict (AL-23, AL-24) · BUG-2639 4 strict (OQ35-01 … 04) · BUG-2640 3 strict (OQ37-02, 03, 05) · BUG-2641 3 strict (OQ38-08 … 10). BUG-2631 0 (race, deferred).
- **Depth:** full (skill step 1a). The DAO computes the PO hub's money tiles, filters orders by payment state and allocates PO numbers.
- **Owner answers (2026-11-11):** the former pending cards keep their `OQ35` … `OQ38` IDs in four sections named after the rule and bug. Each bug rule is split: what holds before and after the fix is a pass card (AS-10; OQ37-01, 04, 06, 07; OQ38-01 … 07), the changed behaviour is a strict xfail card naming its failing line.
- **Notable design choices:**
  - `po_number` is unique **per workspace** (`uq_po_workspace_number`), so Givens store numbers as written (no per-process suffix; AL-27 / AL-28 pin the constraint). But `allocate_po_number` today skips numbers held by **any** workspace (BUG-2630): in pass cards the W0 / W2 numbers are never the number W1 is about to get; only AL-17 … AL-19 put it there.
  - Numbering runs under clock 2031 (not the current year); AL-22 proves the year comes from the clock (2033), AL-23 / AL-24 the UTC-vs-local direction across New Year (BUG-2632, strict).
  - R6 (1000 candidates taken): AL-20 / AL-21 reach it on today's path (W2's numbers, BUG-2630) and pass; they must be retired at the BUG-2630 fix. AL-29 / AL-30 (`Author: claude`, race simulation) patch `_po_number_taken` with `create=True`, the helper the fix keeps (spec G3), and are strict xfail BUG-2630. If BUG-2631's fix replaces the loop with a counter, all four go with it (spec R6).
  - Factory filter: three factories of W1 (FA < F1 < FZ) each with a machine and a project component, plus explicit-id cards (XID) where a machine / component id equals a factory id, so a branch that compares the wrong column fails. Components are hard-deleted (spec G4): HF-24 removes one and its PO no longer matches; HF-61 keeps a soft-deleted project's component POs under the factory.
  - Search: middle of the field, both capitalisations, trimmed text, other workspaces' supplier names; `_`, `%`, `\` literal are strict xfail BUG-2633, the deleted supplier BUG-2634.
  - HR-15: `total_amount` 2.125 / 0.005 / -1.005 are stored half up and summed exactly (AS-08); 9999999999999.99 + 0.01 sums exactly (AS-07).
  - Tie cards (seqscan + bump, explicit `HIGH_ID`) are non-strict, `Author: claude`; each unordered or tie-less query has one strict statement alarm. PH-12 picks one of several SELECTs, so it is `Author: claude`.
  - The fully-closed clause's exact spelling (`complete`, `Complete `) and the exact `Planning` / `Draft` names are BUG-1881 (owner OQ-13, fixed elsewhere): no card pins the misspelling; see Deferred.
  - Voided POs and voided invoices follow the spec's real-write facts (G5, G6). The three cards that need a voided PO marked paid or a voided invoice marked paid (HF-38, OQ35-04, OQ37-04) say they use legacy data.
- **Needs a decision:** None. The six gaps of revision 1 are closed by the spec's Gap log.

## Conventions for this module

**IDs.** `PUO` = `app/dao/purchase_order.py`. `HF` `_apply_purchase_order_hub_filters` + `_purchase_order_is_fully_closed_clause` (through `list_for_hub`) · `LH` list_for_hub · `CH` count_for_hub · `RH` list_recent_for_hub · `PH` get_pending_highlights_for_hub · `AS` aggregate_hub_stats · `LD` list_for_destination · `GI` get_by_id_and_workspace · `GV` get_by_invoice_id · `AL` allocate_po_number · `IO` item get_by_order · `IP` item get_by_purchase_order_ids · `IG` item get_by_id_and_workspace · `IS` summarize_by_purchase_order_ids · `IN` preview_names_by_purchase_order_ids · `OQ35` … `OQ38` the cards of the four owner answers (IDs kept from revision 1).

**Actors and fixed values.**
- `dao` = `purchase_order_dao`, `idao` = `purchase_order_item_dao` (`from app.dao.purchase_order import purchase_order_dao, purchase_order_item_dao`). `db` = the test's real session, first argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- `PurchaseOrder` = `app.models.purchase_order.PurchaseOrder`; `PurchaseOrderItem` = `app.models.purchase_order_item.PurchaseOrderItem`. `sa_inspect` = `sqlalchemy.inspect`. `Status`, `Account`, `Factory`, `Machine`, `Project`, `ProjectComponent`, `Item`, `AccountInvoice` = `app.models.<snake_case>`. `HTTPException` = `fastapi.HTTPException`; `IntegrityError` = `sqlalchemy.exc.IntegrityError`; `text`, `select`, `func` = sqlalchemy's; `Decimal`, `date`, `datetime`, `timedelta`, `patch` the usual ones.
- MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`, once per test. **XID(k)** = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`; "`id XID(k)`" passes `id=XID(k)` to the builder. **HIGH_ID(t)** = `max(greatest id of table t or 0, last_value of <t>_id_seq) + 1000001`, read when the row is built.
- T0 = `datetime(2026, 3, 1, 8, 0)`; T1 … T5 = `datetime(2026, 3, 4, 9, 0)`, `(…, 10, 0)`, `(…, 11, 0)`, `(…, 12, 0)`, `(…, 13, 0)` (naive UTC). DAY = `date(2026, 3, 4)`. D1 = `date(2026, 1, 5)`.

**Externals.** Only `AL` cards. **clock(L, U)** = for the When only: `patch("datetime.datetime", Fake)` where `Fake` subclasses `datetime.datetime` and its `now()` (any arguments) returns L; and patch `app.dao.purchase_order.utcnow` (`create=True`) and `app.utils.time.utcnow` to return U. An `AL` card without a clock line runs under clock(`datetime(2031, 6, 1, 12, 0)`, `datetime(2031, 6, 1, 12, 0)`).

**Standing rows** (every test, this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` ×3 (`W0.id < W1.id < W2.id`); U1, U2, U3 = `make_profile(db)` ×3.
2. W0: SD0, SP0, SR0, SC0 = `Status(workspace_id=W0.id, name=…, comment="po stage")` named `"Draft"`, `"Planning"`, `"Receiving"`, `"Complete"`; A0 = `Account(workspace_id=W0.id, name="Northwind West")`; F0 = `Factory(workspace_id=W0.id, name="Main Plant", abbreviation="MP0")`; I0 = `Item(workspace_id=W0.id, name="Bolt", name_normalized="bolt", unit="pcs")`; V0 = invoice of W0.
3. W1: SD1, SP1, SR1, SC1 (as step 2, W1). AL1, A1, AH1 = `Account(workspace_id=W1.id, name=…)` `"Alpha Parts"`, `"Northwind Traders"`, `"Zenith Tools"`. FA, F1, FZ = `Factory(workspace_id=W1.id, …)` (`"Alpha Plant"`, `"AP"`), (`"Main Plant"`, `"MP"`), (`"Zeta Plant"`, `"ZP"`). MA, M1, MZ = `Machine(workspace_id=W1.id, factory_id=…, name=…)` (FA, `"Press A"`), (F1, `"Press 1"`), (FZ, `"Press Z"`). PJA, PJ1, PJZ = `Project(workspace_id=W1.id, factory_id=…, name=…, description="Main")` (FA, `"Project A"`), (F1, `"Project 1"`), (FZ, `"Project Z"`). CA, C1, CZ = `ProjectComponent(workspace_id=W1.id, project_id=…, name=…)` (PJA, `"Part A"`), (PJ1, `"Part 1"`), (PJZ, `"Part Z"`). Items of W1 (`Item(workspace_id=W1.id, name=…, name_normalized=…, unit=…)`): I1 `"Bolt"`/`"bolt"`/`"pcs"`, IN1 `"Nut"`/`"nut"`/`"pcs"`, IK `"Steel"`/`"steel"`/`"kg"`, IW `"Washer"`/`"washer"`/`"pcs"`, IR `"Rivet"`/`"rivet"`/`"pcs"`, IE `""`/`""`/`"pcs"`. V1, V2, V3 = invoices of W1.
4. W2: SD2, SP2, SR2, SC2; A2 = `Account(workspace_id=W2.id, name="Northwind East")`; F2 (`"Main Plant"`, `"MP2"`); I9 (`"Bolt"`); V9 = invoice of W2.
- **invoice of Wk** = `AccountInvoice(workspace_id=Wk.id, account_id=<A0 / A1 / A2>, invoice_type="payable", invoice_status="confirmed", payment_status="unpaid", invoice_amount=Decimal("100.00"), paid_amount=Decimal("0.00"), invoice_date=D1, allow_payments=True)`. So `V0.id < V1.id < V2.id < V3.id < V9.id`, and every id of a W1 row lies between its W0 and W2 twins.

**Given rows.** Inserted directly (never through the DAOs), flushed one at a time in the order written. After "but" a line lists every column that differs. A line written as code is a step to run exactly, at that place.
- **po N** = `PurchaseOrder(workspace_id=W1.id, po_number=N, account_id=A1.id, destination_type="storage", destination_id=F1.id, subtotal=Decimal("0.00"), total_amount=Decimal("0.00"), current_status_id=SD1.id, created_by=U1.id, created_at=T3)`. "po of W0" uses W0, A0, F0, SD0; "of W2" uses W2, A2, F2, SD2. No PO exists unless the Given lists it.
- **stage S** = `current_status_id S.id`. **closed** = `current_status_id SC1.id` (SC0 / SC2 for W0 / W2), `paid True`. **voided** = `voided True`, `voided_at T4`, `voided_by U1.id`, `void_note "Entered twice"`; `invoice_id`, `invoice_confirmed`, `paid` stay at their defaults (a real void unlinks the invoice and clears both flags; a card that sets them says it is legacy data). **edited at T** = `updated_at T`, `updated_by U1.id`. **no supplier** = `account_id None`.
- **to machine M** = `destination_type "machine"`, `destination_id M.id`. **to component C** = `destination_type "project"`, `destination_id C.id`. **to storage F** = `destination_type "storage"`, `destination_id F.id`.
- **pos(n)** = `for k in range(n): db.add(PurchaseOrder(workspace_id=W1.id, po_number=f"PO-2026-{k + 1:03d}", account_id=A1.id, destination_type="storage", destination_id=F1.id, subtotal=Decimal("0.00"), total_amount=Decimal("0.00"), current_status_id=SD1.id, created_by=U1.id, created_at=T0 + timedelta(minutes=k)))`, then one `db.flush()`. R(k) = the row with `po_number f"PO-2026-{k + 1:03d}"` (R(n-1) is the newest).
- **line of O** = `PurchaseOrderItem(workspace_id=O.workspace_id, purchase_order_id=O.id, line_number=<given>, item_id=I1.id, quantity_ordered=Decimal("1.00"), quantity_received=Decimal("0.00"))` (W0 lines use I0, W2 lines I9); `quantity_returned`, `quantity_refunded` left to their default 0.
- **closed account** = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`. **deleted machine** = the same four columns. **deleted project** = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. Project components have no soft delete: a deleted component is removed with `db.delete(...)`.
- **seqscan** = `SET LOCAL enable_indexscan = off`, `SET LOCAL enable_bitmapscan = off`, `SET LOCAL enable_indexonlyscan = off`, each through `db.execute(text(...))`.
- **bumpP(X)** = `db.execute(text("UPDATE purchase_orders SET po_number = po_number WHERE id = :i"), {"i": X.id})`, then `db.expire_all()` (raw SQL: `updated_at` stays as it was). **bumpL(X)** = the same on `purchase_order_items` with `SET notes = notes`.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` (order is part of the check); **idset(result)** = `{r.id for r in result}`. **eids(L)** = `[e["id"] for e in L]` for a highlights list.
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. Money is compared as `Decimal` (`== Decimal("2.13")`); `Decimal("0") == Decimal("0.00")` is a numeric compare and is what "`== 0`" means here.
- **pocount** = `db.scalar(select(func.count()).select_from(PurchaseOrder))`. **nothing written** = pocount and the number of `purchase_order_items` rows equal their values before the call.
- **edit + pending** (a Given step) = `O1.total_amount = Decimal("5.00")` (not flushed); then `P = PurchaseOrder(workspace_id=W1.id, po_number="PO-2026-950", account_id=A1.id, destination_type="storage", destination_id=F1.id, subtotal=Decimal("0.00"), total_amount=Decimal("0.00"), current_status_id=SD1.id, created_by=U1.id, created_at=T3)` and `db.add(P)` (not flushed). `pending:` lines check the session right after the call: `P in db.new`, `len(db.new) == 1`, `O1 in db.dirty`, `len(db.dirty) == 1`, `not db.deleted`.
- **Statement recorder** = every SQL statement the session sends during the When is recorded (`before_cursor_execute` listener). `sqls` = the recorded SELECTs; `sql` = the first of them whose text contains `FROM purchase_orders` (for `dao`) or `FROM purchase_order_items` (for `idao`); `order_part` = text of `sql` after its first `ORDER BY`, before any `LIMIT` (`""` if none); `written` = every recorded `INSERT`, `UPDATE`, `DELETE`.
- **No-lock check** = `"FOR UPDATE" not in sql` (for every SELECT when the card says `all(...)`). Never `lock_part == ""`.
- **Clear the session before a one-query check**: a card that counts SELECTs ends its Given with `db.expunge_all()`; ids used in Then come from objects built before it.
- `raises: X` = `with pytest.raises(X) as exc:` around the call (`IntegrityError` also inside `with db.begin_nested():`); later `raises:` lines assert on `exc.value` (or `exc.value.orig`), one per line.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`, for cards whose result rests on physical row order (`Author: claude`). Never weaken an assertion.

**Race simulations.** AL-29, AL-30 patch `app.dao.purchase_order._po_number_taken` (`create=True`; the helper the BUG-2630 fix keeps, spec R6 / G3) to answer "taken", the only single-session way to reach R6 once BUG-2630 is fixed. BUG-2631's race half stays integration-only.

**Year patch.** clock(L, U) patches the std `datetime.datetime` (today's target, spec Externals) and `app.dao.purchase_order.utcnow` / `app.utils.time.utcnow` (the target after BUG-2632).

## `_apply_purchase_order_hub_filters` (through `list_for_hub`)

*Every `HF` card calls `dao.list_for_hub(db, workspace_id=…, limit=1000, …)` with the filters it names; filters it does not name are not passed.*

### PUO-HF-01 — only W1's POs, with the same number in W0 and W2
- **Rules:** `_apply…` R1; Model facts (`uq_po_workspace_number`)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-001"`.
2. O1 = po `"PO-2026-001"`.
3. X2 = po of W2 `"PO-2026-001"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {O1.id}`.

### PUO-HF-02 — asked for W2, only W2's PO, though W0 and W1 POs come earlier
- **Rules:** `_apply…` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-001"`.
2. O1 = po `"PO-2026-001"`.
3. X2 = po of W2 `"PO-2026-001"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {X2.id}`.

### PUO-HF-03 — asked for W0, only W0's PO, though W1 and W2 POs come later
- **Rules:** `_apply…` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-001"`.
2. O1 = po `"PO-2026-001"`.
3. X2 = po of W2 `"PO-2026-001"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W0.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {X0.id}`.

### PUO-HF-04 — account filter keeps that supplier only, with a lower and a higher account id beside it
- **Rules:** `_apply…` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `account_id AL1.id`.
2. O2 = po `"PO-2026-102"`.
3. O3 = po `"PO-2026-103"`, but `account_id AH1.id`.
4. O4 = po `"PO-2026-104"`, but no supplier.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, account_id=A1.id)`.

**Then**
1. returns: `idset(result) == {O2.id}`.

### PUO-HF-05 — account_id 0 is a filter that matches nothing
- **Rules:** `_apply…` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`, but no supplier.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, account_id=0)`.

**Then**
1. returns: `result == []`.

### PUO-HF-06 — account_id None is no filter
- **Rules:** `_apply…` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`, but no supplier.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, account_id=None)`.

**Then**
1. returns: `idset(result) == {O1.id, O2.id}`.

### PUO-HF-07 — invoice filter keeps POs of that invoice, with a lower and a higher invoice beside it
- **Rules:** `_apply…` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.
2. O2 = po `"PO-2026-102"`, but `invoice_id V2.id`.
3. O3 = po `"PO-2026-103"`, but `invoice_id V3.id`.
4. O4 = po `"PO-2026-104"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, invoice_id=V2.id)`.

**Then**
1. returns: `idset(result) == {O2.id}`.

### PUO-HF-08 — invoice_id 0 is a filter that matches nothing
- **Rules:** `_apply…` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.
2. O2 = po `"PO-2026-102"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, invoice_id=0)`.

**Then**
1. returns: `result == []`.

### PUO-HF-09 — date_from keeps the day from 00:00:00, not the microsecond before
- **Rules:** `_apply…` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `created_at datetime(2026, 3, 3, 23, 59, 59, 999999)`.
2. O2 = po `"PO-2026-102"`, but `created_at datetime(2026, 3, 4, 0, 0, 0)`.
3. O3 = po `"PO-2026-103"`, but `created_at datetime(2026, 3, 9, 12, 0, 0)`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, date_from=DAY)`.

**Then**
1. returns: `idset(result) == {O2.id, O3.id}`.

### PUO-HF-10 — date_to keeps the whole end day, to 23:59:59.999999, not the next midnight
- **Rules:** `_apply…` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `created_at datetime(2026, 3, 4, 23, 59, 59, 999999)`.
2. O2 = po `"PO-2026-102"`, but `created_at datetime(2026, 3, 5, 0, 0, 0)`.
3. O3 = po `"PO-2026-103"`, but `created_at datetime(2026, 3, 1, 8, 0, 0)`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, date_to=DAY)`.

**Then**
1. returns: `idset(result) == {O1.id, O3.id}`.

### PUO-HF-11 — date_from and date_to on the same day keep exactly that day
- **Rules:** `_apply…` R3, R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `created_at datetime(2026, 3, 4, 0, 0, 0)`.
2. O2 = po `"PO-2026-102"`, but `created_at datetime(2026, 3, 4, 23, 59, 59, 999999)`.
3. O3 = po `"PO-2026-103"`, but `created_at datetime(2026, 3, 3, 23, 59, 59, 999999)`.
4. O4 = po `"PO-2026-104"`, but `created_at datetime(2026, 3, 5, 0, 0, 0)`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, date_from=DAY, date_to=DAY)`.

**Then**
1. returns: `idset(result) == {O1.id, O2.id}`.

### PUO-HF-12 — date_from after date_to gives nothing, with no error
- **Rules:** `_apply…` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `created_at datetime(2026, 3, 4, 12, 0, 0)`.
2. O2 = po `"PO-2026-102"`, but `created_at datetime(2026, 3, 5, 12, 0, 0)`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, date_from=date(2026, 3, 5), date_to=DAY)`.

**Then**
1. returns: `result == []`.

### PUO-HF-13 — status_ids keeps that stage, with a lower and a higher status id beside it
- **Rules:** `_apply…` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`, but stage SP1.
3. O3 = po `"PO-2026-103"`, but stage SR1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, status_ids=[SP1.id])`.

**Then**
1. returns: `idset(result) == {O2.id}`.

### PUO-HF-14 — two status ids keep both stages
- **Rules:** `_apply…` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`, but stage SP1.
3. O3 = po `"PO-2026-103"`, but stage SR1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, status_ids=[SD1.id, SR1.id])`.

**Then**
1. returns: `idset(result) == {O1.id, O3.id}`.

### PUO-HF-15 — an empty status_ids list is no filter
- **Rules:** `_apply…` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`, but stage SP1.
3. O3 = po `"PO-2026-103"`, but stage SR1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, status_ids=[])`.

**Then**
1. returns: `idset(result) == {O1.id, O2.id, O3.id}`.

### PUO-HF-16 — destination_type keeps that type only
- **Rules:** `_apply…` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`, but to machine M1.
3. O3 = po `"PO-2026-103"`, but to component C1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, destination_type="machine")`.

**Then**
1. returns: `idset(result) == {O2.id}`.

### PUO-HF-17 — destination_type is compared case-sensitively
- **Rules:** `_apply…` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but to machine M1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, destination_type="Machine")`.

**Then**
1. returns: `result == []`.

### PUO-HF-18 — part of a destination type does not match
- **Rules:** `_apply…` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but to machine M1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, destination_type="mach")`.

**Then**
1. returns: `result == []`.

### PUO-HF-19 — an empty destination_type is no filter
- **Rules:** `_apply…` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`, but to machine M1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, destination_type="")`.

**Then**
1. returns: `idset(result) == {O1.id, O2.id}`.

### PUO-HF-20 — factory filter keeps storage POs of that factory, not of a lower or higher factory
- **Rules:** `_apply…` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but to storage FA.
2. O2 = po `"PO-2026-102"`.
3. O3 = po `"PO-2026-103"`, but to storage FZ.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, factory_id=F1.id)`.

**Then**
1. returns: `idset(result) == {O2.id}`.

### PUO-HF-21 — factory filter keeps POs for a machine of that factory
- **Rules:** `_apply…` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but to machine MA.
2. O2 = po `"PO-2026-102"`, but to machine M1.
3. O3 = po `"PO-2026-103"`, but to machine MZ.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, factory_id=F1.id)`.

**Then**
1. returns: `idset(result) == {O2.id}`.

### PUO-HF-22 — factory filter keeps POs for a component of a project of that factory
- **Rules:** `_apply…` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but to component CA.
2. O2 = po `"PO-2026-102"`, but to component C1.
3. O3 = po `"PO-2026-103"`, but to component CZ.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, factory_id=F1.id)`.

**Then**
1. returns: `idset(result) == {O2.id}`.

### PUO-HF-23 — a deleted machine still places its PO under the factory
- **Rules:** `_apply…` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MD = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Press Old")`, but deleted machine.
2. O1 = po `"PO-2026-101"`, but to machine MD.
3. O2 = po `"PO-2026-102"`, but to machine MZ.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, factory_id=F1.id)`.

**Then**
1. returns: `idset(result) == {O1.id}`.

### PUO-HF-24 — a removed component no longer places its PO under the factory
- **Rules:** `_apply…` R6
- **Kind:** boundary
- **Expect:** pass
- **Note:** project components have no soft delete; a real delete removes the row and the PO keeps its `destination_id` (no foreign key).

**Given**
1. CD = `ProjectComponent(workspace_id=W1.id, project_id=PJ1.id, name="Part Old")`.
2. O1 = po `"PO-2026-101"`, but to component CD.
3. O2 = po `"PO-2026-102"`, but to component C1.
4. `cd_id = CD.id`
5. `db.delete(CD)`, then `db.flush()`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, factory_id=F1.id)`.

**Then**
1. returns: `idset(result) == {O2.id}`.
2. re-read O1: `destination_type == "project"`, `destination_id == cd_id`.

### PUO-HF-25 — a machine whose id equals the factory id does not count unless it belongs to it
- **Rules:** `_apply…` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FX = `Factory(workspace_id=W1.id, name="Extra Plant", abbreviation="XP")`, but `id XID(1)`.
2. MX = `Machine(workspace_id=W1.id, factory_id=FZ.id, name="Press X")`, but `id XID(1)`.
3. O1 = po `"PO-2026-101"`, but to machine MX.
4. O2 = po `"PO-2026-102"`, but to storage FX.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, factory_id=FX.id)`.

**Then**
1. returns: `idset(result) == {O2.id}`.

### PUO-HF-26 — a storage PO whose destination id is a machine of the factory is not kept
- **Rules:** `_apply…` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MY = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Press Y")`, but `id XID(2)`.
2. O1 = po `"PO-2026-101"`, but `destination_type "storage"`, `destination_id XID(2)`.
3. O2 = po `"PO-2026-102"`, but to machine MY.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, factory_id=F1.id)`.

**Then**
1. returns: `idset(result) == {O2.id}`.

### PUO-HF-27 — a storage PO whose destination id is a component of the factory is not kept
- **Rules:** `_apply…` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. CX = `ProjectComponent(workspace_id=W1.id, project_id=PJ1.id, name="Part X")`, but `id XID(3)`.
2. O1 = po `"PO-2026-101"`, but `destination_type "storage"`, `destination_id XID(3)`.
3. O2 = po `"PO-2026-102"`, but to component CX.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, factory_id=F1.id)`.

**Then**
1. returns: `idset(result) == {O2.id}`.

### PUO-HF-28 — an unknown destination type pointing at the factory id is not kept
- **Rules:** `_apply…` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `destination_type "warehouse"`, `destination_id F1.id`.
2. O2 = po `"PO-2026-102"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, factory_id=F1.id)`.

**Then**
1. returns: `idset(result) == {O2.id}`.

### PUO-HF-29 — a factory with no PO gives nothing
- **Rules:** `_apply…` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, factory_id=FZ.id)`.

**Then**
1. returns: `result == []`.

### PUO-HF-30 — invoiced keeps POs with an invoice
- **Rules:** `_apply…` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.
2. O2 = po `"PO-2026-102"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, invoice_filter="invoiced")`.

**Then**
1. returns: `idset(result) == {O1.id}`.

### PUO-HF-31 — not_invoiced keeps POs without an invoice
- **Rules:** `_apply…` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.
2. O2 = po `"PO-2026-102"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, invoice_filter="not_invoiced")`.

**Then**
1. returns: `idset(result) == {O2.id}`.

### PUO-HF-32 — an unknown invoice_filter is no filter
- **Rules:** `_apply…` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.
2. O2 = po `"PO-2026-102"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, invoice_filter="bogus")`.

**Then**
1. returns: `idset(result) == {O1.id, O2.id}`.

### PUO-HF-33 — invoice_filter "all" is no filter
- **Rules:** `_apply…` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.
2. O2 = po `"PO-2026-102"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, invoice_filter="all")`.

**Then**
1. returns: `idset(result) == {O1.id, O2.id}`.

### PUO-HF-34 — an empty invoice_filter is no filter
- **Rules:** `_apply…` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.
2. O2 = po `"PO-2026-102"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, invoice_filter="")`.

**Then**
1. returns: `idset(result) == {O1.id, O2.id}`.

### PUO-HF-35 — by default voided and fully closed POs are left out; Complete unpaid and paid Receiving stay
- **Rules:** `_apply…` R10; `_purchase_order_is_fully_closed_clause` R1, R2; `list_for_hub` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`, but closed.
3. O3 = po `"PO-2026-103"`, but voided.
4. O4 = po `"PO-2026-104"`, but stage SC1.
5. O5 = po `"PO-2026-105"`, but stage SR1, `paid True`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {O1.id, O4.id, O5.id}`.

### PUO-HF-36 — exclude_voided=False keeps voided POs; fully closed stay out
- **Rules:** `_apply…` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`, but closed.
3. O3 = po `"PO-2026-103"`, but voided.
4. O4 = po `"PO-2026-104"`, but stage SC1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_voided=False)`.

**Then**
1. returns: `idset(result) == {O1.id, O3.id, O4.id}`.

### PUO-HF-37 — exclude_complete=False keeps fully closed POs; voided stay out
- **Rules:** `_apply…` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`, but closed.
3. O3 = po `"PO-2026-103"`, but voided.
4. O4 = po `"PO-2026-104"`, but stage SC1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False)`.

**Then**
1. returns: `idset(result) == {O1.id, O2.id, O4.id}`.

### PUO-HF-38 — both switches off keep every PO
- **Rules:** `_apply…` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`, but closed.
3. O3 = po `"PO-2026-103"`, but voided.
4. O4 = po `"PO-2026-104"`, but closed, voided (legacy data: a real void sets `paid False`; fine for a filter check).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `idset(result) == {O1.id, O2.id, O3.id, O4.id}`.

### PUO-HF-39 — search finds text in the middle of the PO number
- **Rules:** `_apply…` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-417"`.
2. O2 = po `"PO-2026-520"`, but `account_id AH1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="6-41")`.

**Then**
1. returns: `idset(result) == {O1.id}`.

### PUO-HF-40 — search on the number ignores case
- **Rules:** `_apply…` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-417"`, but `account_id AH1.id`.
2. O2 = po `"XO-2026-520"`, but `account_id AH1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="po-2026")`.

**Then**
1. returns: `idset(result) == {O1.id}`.

### PUO-HF-41 — search finds text in the middle of the supplier name
- **Rules:** `_apply…` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-417"`.
2. O2 = po `"PO-2026-520"`, but `account_id AH1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="wind Tra")`.

**Then**
1. returns: `idset(result) == {O1.id}`.

### PUO-HF-42 — search on the supplier name ignores case
- **Rules:** `_apply…` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-417"`.
2. O2 = po `"PO-2026-520"`, but `account_id AH1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="NORTHWIND TRADERS")`.

**Then**
1. returns: `idset(result) == {O1.id}`.

### PUO-HF-43 — search text is trimmed before matching
- **Rules:** `_apply…` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-417"`, but `account_id AH1.id`.
2. O2 = po `"PO-2026-520"`, but `account_id AH1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="  417  ")`.

**Then**
1. returns: `idset(result) == {O1.id}`.

### PUO-HF-44 — whitespace-only search is no filter
- **Rules:** `_apply…` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-417"`.
2. O2 = po `"PO-2026-520"`, but no supplier.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="   ")`.

**Then**
1. returns: `idset(result) == {O1.id, O2.id}`.

### PUO-HF-45 — empty search is no filter
- **Rules:** `_apply…` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-417"`.
2. O2 = po `"PO-2026-520"`, but no supplier.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="")`.

**Then**
1. returns: `idset(result) == {O1.id, O2.id}`.

### PUO-HF-46 — the earlier workspace's supplier name does not match in W1
- **Rules:** `_apply…` R1, R11; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-417"`.
2. O1 = po `"PO-2026-520"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="West")`.

**Then**
1. returns: `result == []`.

### PUO-HF-47 — the later workspace's supplier name does not match in W1
- **Rules:** `_apply…` R1, R11; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-520"`.
2. X2 = po of W2 `"PO-2026-417"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="East")`.

**Then**
1. returns: `result == []`.

### PUO-HF-48 — a PO with no supplier is found by its number
- **Rules:** `_apply…` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-417"`, but no supplier.
2. O2 = po `"PO-2026-520"`, but no supplier.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="417")`.

**Then**
1. returns: `idset(result) == {O1.id}`.

### PUO-HF-49 — a name search skips a PO with no supplier, with no error
- **Rules:** `_apply…` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-417"`, but no supplier.
2. O2 = po `"PO-2026-520"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="Northwind")`.

**Then**
1. returns: `idset(result) == {O2.id}`.

### PUO-HF-50 — a search with `_` finds the PO whose number has it
- **Rules:** `_apply…` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-5_1"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="5_1")`.

**Then**
1. returns: `O1.id in idset(result)`.

### PUO-HF-51 — `_` in the search matches only a literal underscore
- **Rules:** `_apply…` R11 [BUG-2633]
- **Kind:** bug
- **Expect:** xfail BUG-2633
- **Fails today on:** Then 2 (unescaped `_` also matches `PO-2026-501`)

**Given**
1. O1 = po `"PO-2026-5_1"`.
2. O2 = po `"PO-2026-501"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="5_1")`.

**Then**
1. returns: `O1.id in idset(result)`.
2. returns: `idset(result) == {O1.id}`.

### PUO-HF-52 — `%` in the search matches only a literal percent sign
- **Rules:** `_apply…` R11 [BUG-2633]
- **Kind:** bug
- **Expect:** xfail BUG-2633
- **Fails today on:** Then 2 (unescaped `%` also matches `PO-2026-700`)

**Given**
1. O1 = po `"PO-2026-7%0"`.
2. O2 = po `"PO-2026-700"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="7%0")`.

**Then**
1. returns: `O1.id in idset(result)`.
2. returns: `idset(result) == {O1.id}`.

### PUO-HF-53 — a backslash in the search matches a literal backslash
- **Rules:** `_apply…` R11 [BUG-2633]
- **Kind:** bug
- **Expect:** xfail BUG-2633
- **Fails today on:** Then 2 (`\9` escapes the 9: today only `PO-2026-89` matches)

**Given**
1. O1 = po `"PO-2026-8\\9"` (Python literal; the stored text is `PO-2026-8\9`).
2. O2 = po `"PO-2026-89"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="8\\9")`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {O1.id}`.

### PUO-HF-54 — a search of `_` alone matches no PO without an underscore
- **Rules:** `_apply…` R11 [BUG-2633]
- **Kind:** bug
- **Expect:** xfail BUG-2633
- **Fails today on:** Then 2 (`_` alone matches every PO)

**Given**
1. O1 = po `"PO-2026-001"`.
2. O2 = po `"PO-2026-002"`, but no supplier.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="_")`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `result == []`.

### PUO-HF-55 — a search of `%` alone matches no PO without a percent sign
- **Rules:** `_apply…` R11 [BUG-2633]
- **Kind:** bug
- **Expect:** xfail BUG-2633
- **Fails today on:** Then 2 (`%` alone matches every PO)

**Given**
1. O1 = po `"PO-2026-001"`.
2. O2 = po `"PO-2026-002"`, but no supplier.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="%")`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `result == []`.

### PUO-HF-56 — a soft-deleted supplier's name does not match
- **Rules:** `_apply…` R12 [BUG-2634]
- **Kind:** bug
- **Expect:** xfail BUG-2634
- **Fails today on:** Then 2 (the deleted account's name matches)

**Given**
1. DA = `Account(workspace_id=W1.id, name="Delta Freight")`, but closed account.
2. O1 = po `"PO-2026-417"`, but `account_id DA.id`.
3. O2 = po `"PO-2026-520"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="Delta")`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `result == []`.

### PUO-HF-57 — a PO of a soft-deleted supplier is still found by its number
- **Rules:** `_apply…` R12, R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. DA = `Account(workspace_id=W1.id, name="Delta Freight")`, but closed account.
2. O1 = po `"PO-2026-417"`, but `account_id DA.id`.
3. O2 = po `"PO-2026-520"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="417")`.

**Then**
1. returns: `idset(result) == {O1.id}`.

### PUO-HF-58 — filters combine with AND
- **Rules:** `_apply…` R13
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but stage SP1.
2. O2 = po `"PO-2026-102"`.
3. O3 = po `"PO-2026-103"`, but stage SP1, `account_id AL1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, account_id=A1.id, status_ids=[SP1.id])`.

**Then**
1. returns: `idset(result) == {O1.id}`.

### PUO-HF-59 — supplier, invoice and status joins together add no duplicate row
- **Rules:** `_apply…` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-417"`, but stage SP1, `invoice_id V1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, search="Northwind", invoice_filter="invoiced", exclude_complete=True)`.

**Then**
1. returns: `ids(result) == [O1.id]`.

### PUO-HF-60 — an unknown filter keyword raises TypeError
- **Rules:** `_apply…` R14
- **Kind:** error
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, supplier_id=A1.id)`.

**Then**
1. raises: `TypeError`.
2. nothing written: nothing written.

### PUO-HF-61 — a soft-deleted project still places its components' POs under its factory
- **Rules:** `_apply…` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. PJD = `Project(workspace_id=W1.id, factory_id=F1.id, name="Project Old", description="Main")`, but deleted project.
2. CPD = `ProjectComponent(workspace_id=W1.id, project_id=PJD.id, name="Part Old")`.
3. O1 = po `"PO-2026-101"`, but to component CPD.
4. O2 = po `"PO-2026-102"`, but to component CZ.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, factory_id=F1.id)`.

**Then**
1. returns: `idset(result) == {O1.id}`.

## `PurchaseOrderDAO.list_for_hub`

### PUO-LH-01 — newest created_at first, though ids, numbers and suppliers run otherwise
- **Rules:** `list_for_hub` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-004"`, but `created_at T2`, `account_id AH1.id`.
2. O2 = po `"PO-2026-001"`, but `created_at T4`.
3. O3 = po `"PO-2026-003"`, but `created_at T1`, `account_id AL1.id`.
4. O4 = po `"PO-2026-002"`, but `created_at T3`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [O2.id, O4.id, O1.id, O3.id]`.

### PUO-LH-02 — on a created_at tie the higher id comes first, also after the lowest id was updated
- **Rules:** `list_for_hub` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = po `"PO-2026-003"`, but `created_at T2`, `account_id AH1.id`.
2. B = po `"PO-2026-001"`, but `created_at T2`.
3. C = po `"PO-2026-002"`, but `created_at T2`, `account_id AL1.id`.
4. seqscan.
5. bumpP(A).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.

### PUO-LH-03 — on a created_at tie a row with a high explicit id comes first
- **Rules:** `list_for_hub` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. EB = po `"PO-2026-001"`, but `created_at T2`.
2. EH = po `"PO-2026-002"`, but `created_at T2`, `id HIGH_ID(purchase_orders)`.
3. EA = po `"PO-2026-003"`, but `created_at T2`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [EH.id, EA.id, EB.id]`.

### PUO-LH-04 — the query orders by created_at, then id, both descending
- **Rules:** `list_for_hub` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-001"`.
2. Statement recorder.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [O1.id]`.
2. statement: `"created_at" in order_part`.
3. statement: `"purchase_orders.id" in order_part`.
4. statement: `order_part.index("created_at") < order_part.index("purchase_orders.id")`.
5. statement: `order_part.upper().count("DESC") == 2`.

### PUO-LH-05 — skip and limit select the middle of the list
- **Rules:** `list_for_hub` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. pos(7).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, skip=2, limit=3)`.

**Then**
1. returns: `ids(result) == [R(4).id, R(3).id, R(2).id]`.

### PUO-LH-06 — the default limit is 50
- **Rules:** `list_for_hub` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. pos(51).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 50`.
2. returns: `R(0).id not in idset(result)`.

### PUO-LH-07 — the default skip is 0
- **Rules:** `list_for_hub` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. pos(3).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [R(2).id, R(1).id]`.

### PUO-LH-08 — limit=1000 returns all 51 rows
- **Rules:** `list_for_hub` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. pos(51).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 51`.

### PUO-LH-09 — filters apply before paging: a newer hidden PO does not use a page slot
- **Rules:** `list_for_hub` R3; HR-5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O0 = po `"PO-2026-001"`, but `created_at T1`.
2. H = po `"PO-2026-002"`, but `created_at T5`, voided.
3. O1 = po `"PO-2026-003"`, but `created_at T4`.
4. O2 = po `"PO-2026-004"`, but `created_at T3`.
5. O3 = po `"PO-2026-005"`, but `created_at T2`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [O2.id, O3.id]`.

### PUO-LH-10 — a page is full when enough POs match, though hidden POs exist
- **Rules:** `list_for_hub` R3; HR-5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. pos(5).
2. H1 = po `"PO-2026-901"`, but `created_at T5`, voided.
3. H2 = po `"PO-2026-902"`, but `created_at T4`, closed.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, skip=0, limit=5)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: `idset(result) == {R(0).id, R(1).id, R(2).id, R(3).id, R(4).id}`.

### PUO-LH-11 — writes nothing, keeps the caller's pending row and edit, takes no lock
- **Rules:** `list_for_hub` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-001"`.
2. edit + pending.
3. Statement recorder.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [O1.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `O1 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `all("FOR UPDATE" not in s for s in sqls)`.
8. nothing written: nothing written.

### PUO-LH-12 — a workspace with no PO gives an empty list
- **Rules:** `list_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-001"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PUO-LH-13 — the current status comes loaded with each PO
- **Rules:** `list_for_hub` R1 (Returns: current status loaded)
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`, but stage SP1.
3. `db.expunge_all()`

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `all("current_status" not in sa_inspect(r).unloaded for r in result)`.
2. returns: `{r.current_status.name for r in result} == {"Draft", "Planning"}`.

## `PurchaseOrderDAO.count_for_hub`

### PUO-CH-01 — counts the POs matching the filters, as an int
- **Rules:** `count_for_hub` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but stage SP1.
2. O2 = po `"PO-2026-102"`, but stage SP1.
3. O3 = po `"PO-2026-103"`.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, status_ids=[SP1.id])`.

**Then**
1. returns: `isinstance(result, int)`.
2. returns: `result == 2`.

### PUO-CH-02 — no match gives 0
- **Rules:** `count_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, account_id=0)`.

**Then**
1. returns: `isinstance(result, int)`.
2. returns: `result == 0`.

### PUO-CH-03 — by default voided and fully closed POs are not counted
- **Rules:** `count_for_hub` R1; `_apply…` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`, but closed.
3. O3 = po `"PO-2026-103"`, but voided.
4. O4 = po `"PO-2026-104"`, but stage SC1.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 2`.

### PUO-CH-04 — the count is not capped by the list's page size
- **Rules:** `count_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. pos(60).

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 60`.

### PUO-CH-05 — only W1's POs are counted, with more POs in W0 and W2
- **Rules:** `count_for_hub` R1; `_apply…` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0a = po of W0 `"PO-2026-001"`.
2. X0b = po of W0 `"PO-2026-002"`.
3. O1 = po `"PO-2026-001"`.
4. X2a = po of W2 `"PO-2026-001"`.
5. X2b = po of W2 `"PO-2026-002"`.
6. X2c = po of W2 `"PO-2026-003"`.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.

### PUO-CH-06 — asked for W2, W2's POs are counted
- **Rules:** `count_for_hub` R1; `_apply…` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0a = po of W0 `"PO-2026-001"`.
2. O1 = po `"PO-2026-001"`.
3. X2a = po of W2 `"PO-2026-001"`.
4. X2b = po of W2 `"PO-2026-002"`.
5. X2c = po of W2 `"PO-2026-003"`.

**When**
- `result = dao.count_for_hub(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == 3`.

### PUO-CH-07 — the joins of search, invoice filter and stage count each PO once
- **Rules:** `count_for_hub` R1; `_apply…` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-417"`, but stage SP1, `invoice_id V1.id`.
2. O2 = po `"PO-2026-418"`, but stage SR1, `invoice_id V2.id`.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, search="Northwind", invoice_filter="invoiced", exclude_complete=True)`.

**Then**
1. returns: `result == 2`.

### PUO-CH-08 — writes nothing and takes no lock
- **Rules:** `count_for_hub` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-001"`.
2. edit + pending.
3. Statement recorder.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `O1 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `all("FOR UPDATE" not in s for s in sqls)`.

## `PurchaseOrderDAO.list_recent_for_hub`

### PUO-RH-01 — an edited PO with the latest activity comes before never-edited newer ones
- **Rules:** `list_recent_for_hub` R1 [BUG-2635]
- **Kind:** bug
- **Expect:** xfail BUG-2635
- **Fails today on:** Then 2 (`updated_at` desc puts the never-edited POs first)

**Given**
1. E = po `"PO-2026-001"`, but `created_at T1`, edited at T5.
2. N1 = po `"PO-2026-002"`, but `created_at T4`.
3. N2 = po `"PO-2026-003"`, but `created_at T2`.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [E.id, N1.id, N2.id]`.

### PUO-RH-02 — never-edited POs come newest created_at first
- **Rules:** `list_recent_for_hub` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = po `"PO-2026-003"`, but `created_at T2`.
2. N2 = po `"PO-2026-001"`, but `created_at T4`.
3. N3 = po `"PO-2026-002"`, but `created_at T1`.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [N2.id, N1.id, N3.id]`.

### PUO-RH-03 — edited POs come latest edit first, whatever their created_at
- **Rules:** `list_recent_for_hub` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = po `"PO-2026-001"`, but `created_at T1`, edited at T3.
2. E2 = po `"PO-2026-002"`, but `created_at T4`, edited at `datetime(2026, 3, 4, 12, 30)`.
3. E3 = po `"PO-2026-003"`, but `created_at T2`, edited at T5.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E3.id, E2.id, E1.id]`.

### PUO-RH-04 — on an activity tie the higher id comes first
- **Rules:** `list_recent_for_hub` R1 [BUG-2635]
- **Kind:** bug
- **Expect:** xfail BUG-2635 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `id` tie-break; physical row order decides)

**Given**
1. A = po `"PO-2026-003"`, but `created_at T2`.
2. B = po `"PO-2026-001"`, but `created_at T2`.
3. C = po `"PO-2026-002"`, but `created_at T2`.
4. seqscan.
5. bumpP(A).

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### PUO-RH-05 — the query orders by coalesce(updated_at, created_at), then id
- **Rules:** `list_recent_for_hub` R1 [BUG-2635]
- **Kind:** bug
- **Expect:** xfail BUG-2635
- **Fails today on:** Then 2 (the query orders by `updated_at`, then `created_at`)

**Given**
1. O1 = po `"PO-2026-001"`.
2. Statement recorder.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [O1.id]`.
2. statement: `"coalesce" in order_part.lower()`.
3. statement: `"purchase_orders.id" in order_part`.

### PUO-RH-06 — the default limit is 10
- **Rules:** `list_recent_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. pos(11).

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 10`.
2. returns: `R(0).id not in idset(result)`.

### PUO-RH-07 — limit=2 gives the two latest
- **Rules:** `list_recent_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. pos(3).

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [R(2).id, R(1).id]`.

### PUO-RH-08 — limit=1000 returns all 11 rows
- **Rules:** `list_recent_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. pos(11).

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 11`.

### PUO-RH-09 — the hub filters and defaults apply
- **Rules:** `list_recent_for_hub` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-001"`, but `created_at T5`.
2. O1 = po `"PO-2026-001"`, but `created_at T1`.
3. OV = po `"PO-2026-002"`, but `created_at T4`, voided.
4. OC = po `"PO-2026-003"`, but `created_at T4`, closed.
5. OA = po `"PO-2026-004"`, but `created_at T2`, `account_id AL1.id`.
6. X2 = po of W2 `"PO-2026-001"`, but `created_at T5`.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, account_id=A1.id)`.

**Then**
1. returns: `ids(result) == [O1.id]`.

### PUO-RH-10 — writes nothing and takes no lock
- **Rules:** `list_recent_for_hub` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-001"`.
2. edit + pending.
3. Statement recorder.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [O1.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `O1 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `all("FOR UPDATE" not in s for s in sqls)`.

## `PurchaseOrderDAO.get_pending_highlights_for_hub`

### PUO-PH-01 — Planning POs are counted and listed with their fields; Draft and Receiving are not
- **Rules:** `get_pending_highlights_for_hub` R2, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po `"PO-2026-001"`, but stage SP1, `created_at T2`, `invoice_id V1.id`.
2. D1o = po `"PO-2026-002"`, but `created_at T1`.
3. R1o = po `"PO-2026-003"`, but stage SR1.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result["pending_planning_count"] == 1`.
2. returns: `result["pending_planning"] == [{"id": P1.id, "order_number": "PO-2026-001", "status_name": "Planning", "created_at": T2}]`.

### PUO-PH-02 — at most 3 Planning POs are listed, all 4 are counted
- **Rules:** `get_pending_highlights_for_hub` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P1 = po `"PO-2026-001"`, but stage SP1, `created_at T1`.
2. P2 = po `"PO-2026-002"`, but stage SP1, `created_at T2`.
3. P3 = po `"PO-2026-003"`, but stage SP1, `created_at T3`.
4. P4 = po `"PO-2026-004"`, but stage SP1, `created_at T4`.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result["pending_planning_count"] == 4`.
2. returns: `len(result["pending_planning"]) == 3`.
3. returns: `set(eids(result["pending_planning"])) <= {P1.id, P2.id, P3.id, P4.id}`.

### PUO-PH-03 — Planning samples come latest activity first
- **Rules:** `get_pending_highlights_for_hub` R2 [BUG-2635]
- **Kind:** bug
- **Expect:** xfail BUG-2635
- **Fails today on:** Then 2 (`updated_at` desc alone puts the never-edited POs first)

**Given**
1. E = po `"PO-2026-001"`, but stage SP1, `created_at T1`, edited at T5.
2. N1 = po `"PO-2026-002"`, but stage SP1, `created_at T4`.
3. N2 = po `"PO-2026-003"`, but stage SP1, `created_at T2`.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result["pending_planning_count"] == 3`.
2. returns: `eids(result["pending_planning"]) == [E.id, N1.id, N2.id]`.

### PUO-PH-04 — Planning samples tied on activity come higher id first
- **Rules:** `get_pending_highlights_for_hub` R2 [BUG-2635]
- **Kind:** bug
- **Expect:** xfail BUG-2635 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no tie-break; physical row order decides)

**Given**
1. A = po `"PO-2026-003"`, but stage SP1, `created_at T2`.
2. B = po `"PO-2026-001"`, but stage SP1, `created_at T2`.
3. C = po `"PO-2026-002"`, but stage SP1, `created_at T2`.
4. seqscan.
5. bumpP(A).

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result["pending_planning_count"] == 3`.
2. returns: `eids(result["pending_planning"]) == [C.id, B.id, A.id]`.

### PUO-PH-05 — missing-invoice samples come latest activity first
- **Rules:** `get_pending_highlights_for_hub` R3 [BUG-2635]
- **Kind:** bug
- **Expect:** xfail BUG-2635
- **Fails today on:** Then 2 (`updated_at` desc alone puts the never-edited POs first)

**Given**
1. E = po `"PO-2026-001"`, but stage SP1, `created_at T1`, edited at T5.
2. N1 = po `"PO-2026-002"`, but stage SP1, `created_at T4`.
3. N2 = po `"PO-2026-003"`, but stage SP1, `created_at T2`.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result["missing_invoice_count"] == 3`.
2. returns: `eids(result["missing_invoice"]) == [E.id, N1.id, N2.id]`.

### PUO-PH-06 — "missing invoice" is a Planning PO with a supplier and no invoice
- **Rules:** `get_pending_highlights_for_hub` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. M1 = po `"PO-2026-001"`, but stage SP1.
2. M2 = po `"PO-2026-002"`, but stage SP1, `invoice_id V1.id`.
3. M3 = po `"PO-2026-003"`, but stage SP1, no supplier.
4. M4 = po `"PO-2026-004"`.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result["pending_planning_count"] == 3`.
2. returns: `result["missing_invoice_count"] == 1`.
3. returns: `eids(result["missing_invoice"]) == [M1.id]`.
4. returns: `result["missing_invoice"][0] == {"id": M1.id, "order_number": "PO-2026-001", "status_name": "Planning", "created_at": T3}`.

### PUO-PH-07 — at most 3 missing-invoice POs are listed, all 4 are counted
- **Rules:** `get_pending_highlights_for_hub` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = po `"PO-2026-001"`, but stage SP1, `created_at T1`.
2. M2 = po `"PO-2026-002"`, but stage SP1, `created_at T2`.
3. M3 = po `"PO-2026-003"`, but stage SP1, `created_at T3`.
4. M4 = po `"PO-2026-004"`, but stage SP1, `created_at T4`.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result["missing_invoice_count"] == 4`.
2. returns: `len(result["missing_invoice"]) == 3`.
3. returns: `set(eids(result["missing_invoice"])) <= {M1.id, M2.id, M3.id, M4.id}`.

### PUO-PH-08 — oldest drafts: the 5 oldest Draft POs, oldest first
- **Rules:** `get_pending_highlights_for_hub` R4, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. D3 = po `"PO-2026-001"`, but `created_at T3`.
2. D1 = po `"PO-2026-002"`, but `created_at T1`.
3. D6 = po `"PO-2026-003"`, but `created_at T5`.
4. D2 = po `"PO-2026-004"`, but `created_at T2`.
5. D5 = po `"PO-2026-005"`, but `created_at datetime(2026, 3, 4, 12, 30)`.
6. D4 = po `"PO-2026-006"`, but `created_at T4`.
7. PL = po `"PO-2026-007"`, but stage SP1, `created_at T0`.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `eids(result["oldest_drafts"]) == [D1.id, D2.id, D3.id, D4.id, D5.id]`.
2. returns: `result["oldest_drafts"][0] == {"id": D1.id, "order_number": "PO-2026-002", "status_name": "Draft", "created_at": T1}`.

### PUO-PH-09 — 4 Draft POs are all listed
- **Rules:** `get_pending_highlights_for_hub` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. D1 = po `"PO-2026-001"`, but `created_at T1`.
2. D2 = po `"PO-2026-002"`, but `created_at T2`.
3. D3 = po `"PO-2026-003"`, but `created_at T3`.
4. D4 = po `"PO-2026-004"`, but `created_at T4`.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `eids(result["oldest_drafts"]) == [D1.id, D2.id, D3.id, D4.id]`.

### PUO-PH-10 — oldest drafts tied on created_at come lower id first, after the lowest id was updated
- **Rules:** `get_pending_highlights_for_hub` R5 [BUG-2636]
- **Kind:** bug
- **Expect:** xfail BUG-2636 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no tie-break; physical row order puts A last)

**Given**
1. A = po `"PO-2026-003"`, but `created_at T2`, `account_id AH1.id`.
2. B = po `"PO-2026-001"`, but `created_at T2`.
3. C = po `"PO-2026-002"`, but `created_at T2`, `account_id AL1.id`.
4. seqscan.
5. bumpP(A).

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result["oldest_drafts"]) == 3`.
2. returns: `eids(result["oldest_drafts"]) == [A.id, B.id, C.id]`.

### PUO-PH-11 — oldest drafts tied on created_at: a high explicit id comes last
- **Rules:** `get_pending_highlights_for_hub` R5 [BUG-2636]
- **Kind:** bug
- **Expect:** xfail BUG-2636 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no tie-break; physical row order decides)

**Given**
1. EB = po `"PO-2026-001"`, but `created_at T2`.
2. EH = po `"PO-2026-002"`, but `created_at T2`, `id HIGH_ID(purchase_orders)`.
3. EA = po `"PO-2026-003"`, but `created_at T2`.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result["oldest_drafts"]) == 3`.
2. returns: `eids(result["oldest_drafts"]) == [EB.id, EA.id, EH.id]`.

### PUO-PH-12 — the oldest-drafts query orders by created_at, then id, both ascending
- **Rules:** `get_pending_highlights_for_hub` R4, R5 [BUG-2636]
- **Kind:** bug
- **Expect:** xfail BUG-2636
- **Author:** claude
- **Fails today on:** Then 3 (the drafts query orders by `created_at` alone)

**Given**
1. D1 = po `"PO-2026-001"`, but `created_at T1`.
2. Statement recorder.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `eids(result["oldest_drafts"]) == [D1.id]`.
2. statement: in the one recorded SELECT that reads the Draft sample (bound parameters include `"Draft"`, and it has a `LIMIT`), `"created_at" in order_part`.
3. statement: in that SELECT, `"purchase_orders.id" in order_part` after `created_at`, and `"DESC" not in order_part.upper()`.

### PUO-PH-13 — no matching PO gives zero counts and empty lists
- **Rules:** `get_pending_highlights_for_hub` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-001"`, but stage SP0.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {"pending_planning_count": 0, "pending_planning": [], "missing_invoice_count": 0, "missing_invoice": [], "oldest_drafts": []}`.

### PUO-PH-14 — W0's and W2's POs and voided POs are left out by default
- **Rules:** `get_pending_highlights_for_hub` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-001"`, but stage SP0.
2. XD0 = po of W0 `"PO-2026-002"`.
3. P1 = po `"PO-2026-001"`, but stage SP1.
4. PV = po `"PO-2026-002"`, but stage SP1, voided.
5. DV = po `"PO-2026-003"`, but voided.
6. X2 = po of W2 `"PO-2026-001"`, but stage SP2.
7. XD2 = po of W2 `"PO-2026-002"`.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result["pending_planning_count"] == 1`.
2. returns: `eids(result["pending_planning"]) == [P1.id]`.
3. returns: `result["missing_invoice_count"] == 1`.
4. returns: `result["oldest_drafts"] == []`.

### PUO-PH-15 — the account filter narrows every part
- **Rules:** `get_pending_highlights_for_hub` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po `"PO-2026-001"`, but stage SP1.
2. PA = po `"PO-2026-002"`, but stage SP1, `account_id AL1.id`.
3. D1 = po `"PO-2026-003"`, but `account_id AH1.id`.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, account_id=A1.id)`.

**Then**
1. returns: `result["pending_planning_count"] == 1`.
2. returns: `result["missing_invoice_count"] == 1`.
3. returns: `eids(result["missing_invoice"]) == [P1.id]`.
4. returns: `result["oldest_drafts"] == []`.

### PUO-PH-16 — exclude_voided=False counts a voided Planning PO; exclude_complete=True works with the status join
- **Rules:** `get_pending_highlights_for_hub` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P1 = po `"PO-2026-001"`, but stage SP1.
2. PV = po `"PO-2026-002"`, but stage SP1, voided.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, exclude_voided=False, exclude_complete=True)`.

**Then**
1. returns: `result["pending_planning_count"] == 2`.
2. returns: `set(eids(result["pending_planning"])) == {P1.id, PV.id}`.

### PUO-PH-17 — writes nothing and takes no lock
- **Rules:** `get_pending_highlights_for_hub` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-001"`, but stage SP1.
2. edit + pending.
3. Statement recorder.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `result["pending_planning_count"] == 1`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `O1 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `all("FOR UPDATE" not in s for s in sqls)`.

## `PurchaseOrderDAO.aggregate_hub_stats`

*Voided POs in the money figures are BUG-2639 (section "voided POs" below; AS-10 is its pass twin); open count / value are in the OQ-36 section below.*

### PUO-AS-01 — total count, exact total value and not-invoiced count
- **Rules:** `aggregate_hub_stats` R1, R4, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-001"`, but `total_amount Decimal("0.10")`, `invoice_id V1.id`.
2. O2 = po `"PO-2026-002"`, but `total_amount Decimal("0.20")`.
3. O3 = po `"PO-2026-003"`, but `total_amount Decimal("0.30")`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, tuple)`.
2. returns: `len(result) == 5`.
3. returns: `result[0] == 3`.
4. returns: `result[1] == Decimal("0.60")`.
5. returns: `isinstance(result[1], Decimal)`.
6. returns: `result[4] == 2`.

### PUO-AS-02 — no matching PO gives zeros
- **Rules:** `aggregate_hub_stats` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-001"`, but `total_amount Decimal("50.00")`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, Decimal("0"), 0, Decimal("0"), 0)`.
2. returns: `isinstance(result[1], Decimal)`.
3. returns: `isinstance(result[3], Decimal)`.

### PUO-AS-03 — only W1's POs count, with larger POs in W0 and W2
- **Rules:** `aggregate_hub_stats` R1, R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-001"`, but `total_amount Decimal("1000.00")`.
2. O1 = po `"PO-2026-001"`, but `total_amount Decimal("25.50")`.
3. X2 = po of W2 `"PO-2026-001"`, but `total_amount Decimal("700.00")`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 1`.
2. returns: `result[1] == Decimal("25.50")`.
3. returns: `result[4] == 1`.

### PUO-AS-04 — by default voided and fully closed POs add nothing
- **Rules:** `aggregate_hub_stats` R1; `_apply…` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-001"`, but `total_amount Decimal("10.00")`.
2. OC = po `"PO-2026-002"`, but `total_amount Decimal("20.00")`, closed.
3. OV = po `"PO-2026-003"`, but `total_amount Decimal("40.00")`, voided.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 1`.
2. returns: `result[1] == Decimal("10.00")`.
3. returns: `result[4] == 1`.

### PUO-AS-05 — the account filter applies, with a lower and a higher account beside it
- **Rules:** `aggregate_hub_stats` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-001"`, but `total_amount Decimal("20.00")`, `account_id AL1.id`.
2. O2 = po `"PO-2026-002"`, but `total_amount Decimal("10.00")`.
3. O3 = po `"PO-2026-003"`, but `total_amount Decimal("40.00")`, `account_id AH1.id`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, account_id=A1.id)`.

**Then**
1. returns: `result[0] == 1`.
2. returns: `result[1] == Decimal("10.00")`.

### PUO-AS-06 — with search, invoice and stage joins each PO counts once
- **Rules:** `aggregate_hub_stats` R1; `_apply…` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-417"`, but `total_amount Decimal("10.00")`, stage SP1, `invoice_id V1.id`.
2. O2 = po `"PO-2026-418"`, but `total_amount Decimal("20.00")`, stage SR1, `invoice_id V2.id`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, search="Northwind", invoice_filter="invoiced", exclude_complete=True)`.

**Then**
1. returns: `result[0] == 2`.
2. returns: `result[1] == Decimal("30.00")`.
3. returns: `result[4] == 0`.

### PUO-AS-07 — the largest stored amounts sum exactly
- **Rules:** `aggregate_hub_stats` R6; HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-001"`, but `total_amount Decimal("9999999999999.99")`.
2. O2 = po `"PO-2026-002"`, but `total_amount Decimal("0.01")`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[1] == Decimal("10000000000000.00")`.

### PUO-AS-08 — amounts are stored half up and summed exactly
- **Rules:** `aggregate_hub_stats` R6; Model facts (`total_amount` Numeric(15, 2)); HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-001"`, but `total_amount Decimal("2.125")`.
2. O2 = po `"PO-2026-002"`, but `total_amount Decimal("0.005")`.
3. O3 = po `"PO-2026-003"`, but `total_amount Decimal("-1.005")`.
4. `db.expire_all()`

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[1] == Decimal("1.13")`.
2. re-read O1: `total_amount == Decimal("2.13")`.
3. re-read O2: `total_amount == Decimal("0.01")`.
4. re-read O3: `total_amount == Decimal("-1.01")`.

### PUO-AS-09 — writes nothing and takes no lock
- **Rules:** `aggregate_hub_stats` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-001"`, but `total_amount Decimal("10.00")`.
2. edit + pending.
3. Statement recorder.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 1`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `O1 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `all("FOR UPDATE" not in s for s in sqls)`.

### PUO-AS-10 — a shown voided PO counts in total count and, with no invoice, in not-invoiced count
- **Rules:** `aggregate_hub_stats` R1, R3b, R4
- **Kind:** happy
- **Expect:** pass
- **Note:** pass twin of the BUG-2639 cards: these two counts include voided POs today and after the fix.

**Given**
1. O1 = po `"PO-2026-001"`, but `total_amount Decimal("10.00")`, `invoice_id V1.id`.
2. OV = po `"PO-2026-002"`, but `total_amount Decimal("40.00")`, voided.
3. O3 = po `"PO-2026-003"`, but `total_amount Decimal("5.00")`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_voided=False)`.

**Then**
1. returns: `result[0] == 3`.
2. returns: `result[4] == 2`.

## `PurchaseOrderDAO.list_for_destination`

### PUO-LD-01 — exactly that type and id, not a lower or higher factory, not another type with the same id
- **Rules:** `list_for_destination` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but to storage FA.
2. O2 = po `"PO-2026-102"`.
3. O3 = po `"PO-2026-103"`, but to storage FZ.
4. O4 = po `"PO-2026-104"`, but `destination_type "machine"`, `destination_id F1.id`.

**When**
- `result = dao.list_for_destination(db, workspace_id=W1.id, destination_type="storage", destination_id=F1.id)`.

**Then**
1. returns: `ids(result) == [O2.id]`.

### PUO-LD-02 — every status is returned, voided and fully closed included
- **Rules:** `list_for_destination` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but closed.
2. O2 = po `"PO-2026-102"`, but voided.
3. O3 = po `"PO-2026-103"`, but stage SR1.

**When**
- `result = dao.list_for_destination(db, workspace_id=W1.id, destination_type="storage", destination_id=F1.id)`.

**Then**
1. returns: `idset(result) == {O1.id, O2.id, O3.id}`.

### PUO-LD-03 — newest created_at first, though ids run otherwise
- **Rules:** `list_for_destination` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `created_at T2`, to machine M1.
2. O2 = po `"PO-2026-102"`, but `created_at T4`, to machine M1.
3. O3 = po `"PO-2026-103"`, but `created_at T1`, to machine M1.

**When**
- `result = dao.list_for_destination(db, workspace_id=W1.id, destination_type="machine", destination_id=M1.id)`.

**Then**
1. returns: `ids(result) == [O2.id, O1.id, O3.id]`.

### PUO-LD-04 — asked in W1 for W2's destination, W2's PO is not returned
- **Rules:** `list_for_destination` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. X2 = po of W2 `"PO-2026-101"`.

**When**
- `result = dao.list_for_destination(db, workspace_id=W1.id, destination_type="storage", destination_id=F2.id)`.

**Then**
1. returns: `result == []`.

### PUO-LD-05 — asked in W1 for W0's destination, W0's PO is not returned
- **Rules:** `list_for_destination` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-101"`.
2. O1 = po `"PO-2026-101"`.

**When**
- `result = dao.list_for_destination(db, workspace_id=W1.id, destination_type="storage", destination_id=F0.id)`.

**Then**
1. returns: `result == []`.

### PUO-LD-06 — asked in W2, W2's own PO is returned
- **Rules:** `list_for_destination` R1, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-101"`.
2. O1 = po `"PO-2026-101"`.
3. X2 = po of W2 `"PO-2026-101"`.

**When**
- `result = dao.list_for_destination(db, workspace_id=W2.id, destination_type="storage", destination_id=F2.id)`.

**Then**
1. returns: `ids(result) == [X2.id]`.

### PUO-LD-07 — destination_type is compared exactly
- **Rules:** `list_for_destination` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.

**When**
- `result = dao.list_for_destination(db, workspace_id=W1.id, destination_type="Storage", destination_id=F1.id)`.

**Then**
1. returns: `result == []`.

### PUO-LD-08 — not paged: 101 POs are all returned
- **Rules:** `list_for_destination` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. pos(101).

**When**
- `result = dao.list_for_destination(db, workspace_id=W1.id, destination_type="storage", destination_id=F1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `result[0].id == R(100).id`.

### PUO-LD-09 — writes nothing and takes no lock
- **Rules:** `list_for_destination` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-001"`.
2. edit + pending.
3. Statement recorder.

**When**
- `result = dao.list_for_destination(db, workspace_id=W1.id, destination_type="storage", destination_id=F1.id)`.

**Then**
1. returns: `ids(result) == [O1.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `O1 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `all("FOR UPDATE" not in s for s in sqls)`.

### PUO-LD-10 — the current status comes loaded with each PO
- **Rules:** `list_for_destination` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but stage SR1.
2. `db.expunge_all()`

**When**
- `result = dao.list_for_destination(db, workspace_id=W1.id, destination_type="storage", destination_id=F1.id)`.

**Then**
1. returns: `"current_status" not in sa_inspect(result[0]).unloaded`.
2. returns: `result[0].current_status.name == "Receiving"`.

## `PurchaseOrderDAO.get_by_id_and_workspace`

### PUO-GI-01 — returns the PO, with lower and higher ids beside it
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`.
3. O3 = po `"PO-2026-103"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, PurchaseOrder)`.
2. returns: `result.id == O2.id`.
3. returns: `result.po_number == "PO-2026-102"`.

### PUO-GI-02 — a voided PO is returned
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but voided.

**When**
- `result = dao.get_by_id_and_workspace(db, id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O1.id`.
2. returns: `result.voided is True`.

### PUO-GI-03 — W0's PO is not returned for W1
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-101"`.
2. O1 = po `"PO-2026-101"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=X0.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PUO-GI-04 — W2's PO is not returned for W1
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. X2 = po of W2 `"PO-2026-101"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=X2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PUO-GI-05 — asked for W2, W2's PO is returned
- **Rules:** `get_by_id_and_workspace` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. X2 = po of W2 `"PO-2026-101"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=X2.id, workspace_id=W2.id)`.

**Then**
1. returns: `result.id == X2.id`.

### PUO-GI-06 — an unknown id returns None
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PUO-GI-07 — no row lock, writes nothing
- **Rules:** `get_by_id_and_workspace` R3, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. `db.expunge_all()`
3. Statement recorder.

**When**
- `result = dao.get_by_id_and_workspace(db, id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O1.id`.
2. statement: `"FOR UPDATE" not in sql`.
3. statement: `written == []`.

### PUO-GI-08 — the current status comes loaded
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but stage SP1.
2. `db.expunge_all()`

**When**
- `result = dao.get_by_id_and_workspace(db, id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `"current_status" not in sa_inspect(result).unloaded`.
2. returns: `result.current_status.name == "Planning"`.

## `PurchaseOrderDAO.get_by_invoice_id`

### PUO-GV-01 — returns the PO of the invoice, with the invoice in the middle
- **Rules:** `get_by_invoice_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.
2. O2 = po `"PO-2026-102"`, but `invoice_id V2.id`.
3. O3 = po `"PO-2026-103"`, but `invoice_id V3.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V2.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, PurchaseOrder)`.
2. returns: `result.id == O2.id`.

### PUO-GV-02 — W0's PO on its own invoice is not returned for W1
- **Rules:** `get_by_invoice_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-101"`, but `invoice_id V0.id`.
2. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V0.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PUO-GV-03 — W2's PO on its own invoice is not returned for W1
- **Rules:** `get_by_invoice_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.
2. X2 = po of W2 `"PO-2026-101"`, but `invoice_id V9.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PUO-GV-04 — asked for W2, its own PO is returned
- **Rules:** `get_by_invoice_id` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-101"`, but `invoice_id V0.id`.
2. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.
3. X2 = po of W2 `"PO-2026-101"`, but `invoice_id V9.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V9.id, workspace_id=W2.id)`.

**Then**
1. returns: `result.id == X2.id`.

### PUO-GV-05 — an invoice with no PO returns None
- **Rules:** `get_by_invoice_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PUO-GV-06 — with two POs on one invoice, one of them is returned
- **Rules:** `get_by_invoice_id` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `invoice_id V2.id`.
2. O2 = po `"PO-2026-102"`, but `invoice_id V2.id`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id in {O1.id, O2.id}`.

### PUO-GV-07 — on two POs of one invoice the lowest id wins, also after the lower one was updated
- **Rules:** `get_by_invoice_id` R3 [BUG-2637]
- **Kind:** bug
- **Expect:** xfail BUG-2637 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`; physical row order returns O2)

**Given**
1. O1 = po `"PO-2026-102"`, but `invoice_id V2.id`.
2. O2 = po `"PO-2026-101"`, but `invoice_id V2.id`.
3. seqscan.
4. bumpP(O1).

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is not None`.
2. returns: `result.id == O1.id`.

### PUO-GV-08 — on two POs of one invoice the lowest id wins, when the higher id was inserted first
- **Rules:** `get_by_invoice_id` R3 [BUG-2637]
- **Kind:** bug
- **Expect:** xfail BUG-2637 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`; physical row order returns OH)

**Given**
1. OH = po `"PO-2026-101"`, but `invoice_id V2.id`, `id HIGH_ID(purchase_orders)`.
2. OL = po `"PO-2026-102"`, but `invoice_id V2.id`.
3. seqscan.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is not None`.
2. returns: `result.id == OL.id`.

### PUO-GV-09 — the lookup orders by purchase_orders.id ascending
- **Rules:** `get_by_invoice_id` R3 [BUG-2637]
- **Kind:** bug
- **Expect:** xfail BUG-2637
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. O1 = po `"PO-2026-101"`, but `invoice_id V2.id`.
2. Statement recorder.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O1.id`.
2. statement: `"purchase_orders.id" in order_part`.
3. statement: `"DESC" not in order_part.upper()`.

### PUO-GV-10 — invoice_id None returns the workspace's PO without an invoice
- **Rules:** `get_by_invoice_id` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.
2. O2 = po `"PO-2026-102"`.
3. O3 = po `"PO-2026-103"`, but `invoice_id V3.id`.
4. X2 = po of W2 `"PO-2026-101"`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=None, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O2.id`.

### PUO-GV-11 — invoice_id None returns None when every PO of the workspace has an invoice
- **Rules:** `get_by_invoice_id` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-101"`.
2. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.
3. X2 = po of W2 `"PO-2026-101"`.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=None, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PUO-GV-12 — no row lock, writes nothing, keeps the caller's pending row and edit
- **Rules:** `get_by_invoice_id` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-001"`, but `invoice_id V1.id`.
2. edit + pending.
3. Statement recorder.

**When**
- `result = dao.get_by_invoice_id(db, invoice_id=V1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O1.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `O1 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `"FOR UPDATE" not in sql`.
7. statement: `written == []`.

## `PurchaseOrderDAO.allocate_po_number`

*Every `AL` card runs under the default clock (2031) unless it names one. PO numbers of W0 and W2 in pass cards are never the number W1 is about to get (BUG-2630).*

### PUO-AL-01 — no PO yet gives PO-2031-001
- **Rules:** `allocate_po_number` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no PO.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, str)`.
2. returns: `result == "PO-2031-001"`.

### PUO-AL-02 — after PO-2031-007 comes PO-2031-008
- **Rules:** `allocate_po_number` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2031-007"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-008"`.

### PUO-AL-03 — the highest suffix decides, not the count or the last inserted
- **Rules:** `allocate_po_number` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2031-003"`.
2. O2 = po `"PO-2031-007"`.
3. O3 = po `"PO-2031-005"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-008"`.

### PUO-AL-04 — suffixes compare as numbers: 1000 beats 999
- **Rules:** `allocate_po_number` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2031-999"`.
2. O2 = po `"PO-2031-1000"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-1001"`.

### PUO-AL-05 — after 998 comes 999
- **Rules:** `allocate_po_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2031-998"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-999"`.

### PUO-AL-06 — after 999 comes 1000, not cut to three digits
- **Rules:** `allocate_po_number` R2, Returns
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2031-999"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-1000"`.

### PUO-AL-07 — after 9999 comes 10000
- **Rules:** `allocate_po_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2031-9999"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-10000"`.

### PUO-AL-08 — a non-numeric suffix alone is ignored
- **Rules:** `allocate_po_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2031-abc"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-001"`.

### PUO-AL-09 — a non-numeric suffix beside a numeric one is ignored
- **Rules:** `allocate_po_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2031-004"`.
2. O2 = po `"PO-2031-abc"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-005"`.

### PUO-AL-10 — the suffix is the text after the last dash: PO-2031-1-2 counts as 2
- **Rules:** `allocate_po_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2031-1-2"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-003"`.

### PUO-AL-11 — numbers of the year before and the year after do not count
- **Rules:** `allocate_po_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2030-050"`.
2. O2 = po `"PO-2032-060"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-001"`.

### PUO-AL-12 — a lowercase stored prefix does not count
- **Rules:** `allocate_po_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"po-2031-050"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-001"`.

### PUO-AL-13 — the prefix in the middle of a stored number does not count
- **Rules:** `allocate_po_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"X-PO-2031-050"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-001"`.

### PUO-AL-14 — a longer year (PO-20311-) does not count for 2031
- **Rules:** `allocate_po_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-20311-050"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-001"`.

### PUO-AL-15 — W0's and W2's higher numbers do not raise W1's next number
- **Rules:** `allocate_po_number` R2, R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2031-020"`.
2. O1 = po `"PO-2031-004"`.
3. X2 = po of W2 `"PO-2031-030"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-005"`.

### PUO-AL-16 — asked for W2, W2's own numbers count
- **Rules:** `allocate_po_number` R2, R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2031-007"`.
2. O1 = po `"PO-2031-010"`.
3. X2 = po of W2 `"PO-2031-003"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == "PO-2031-004"`.

### PUO-AL-17 — W2 holding PO-2031-001 does not move W1's first number
- **Rules:** `allocate_po_number` R5 [BUG-2630]
- **Kind:** bug
- **Expect:** xfail BUG-2630
- **Fails today on:** Then 2 (today every number taken in any workspace is skipped: `PO-2031-002`)

**Given**
1. X2 = po of W2 `"PO-2031-001"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.startswith("PO-2031-")`.
2. returns: `result == "PO-2031-001"`.

### PUO-AL-18 — W0 holding PO-2031-001 does not move W1's first number
- **Rules:** `allocate_po_number` R5 [BUG-2630]
- **Kind:** bug
- **Expect:** xfail BUG-2630
- **Fails today on:** Then 2 (today `PO-2031-002`)

**Given**
1. X0 = po of W0 `"PO-2031-001"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.startswith("PO-2031-")`.
2. returns: `result == "PO-2031-001"`.

### PUO-AL-19 — W2 holding W1's next number does not skip it
- **Rules:** `allocate_po_number` R5 [BUG-2630]
- **Kind:** bug
- **Expect:** xfail BUG-2630
- **Fails today on:** Then 2 (today `PO-2031-006`)

**Given**
1. O1 = po `"PO-2031-004"`.
2. X2 = po of W2 `"PO-2031-005"`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.startswith("PO-2031-")`.
2. returns: `result == "PO-2031-005"`.

### PUO-AL-20 — 1000 taken candidates raise 500 (today's path through W2's numbers)
- **Rules:** `allocate_po_number` R6; Errors row 1
- **Kind:** error
- **Expect:** pass
- **Note:** today's path (spec R6, G3: while BUG-2630 is open, R6 is reached through other workspaces' numbers). Retire this card when BUG-2630 is fixed; AL-29 / AL-30 take over.

**Given**
1. `for i in range(1, 1001): db.add(PurchaseOrder(workspace_id=W2.id, po_number=f"PO-2031-{i:03d}", account_id=A2.id, destination_type="storage", destination_id=F2.id, subtotal=Decimal("0.00"), total_amount=Decimal("0.00"), current_status_id=SD2.id, created_by=U1.id, created_at=T3))`, then one `db.flush()`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 500`.
3. raises: `exc.value.detail == "Could not allocate a unique purchase order number"`.
4. nothing written: nothing written.

### PUO-AL-21 — 999 taken candidates still give a number (today's path through W2's numbers)
- **Rules:** `allocate_po_number` R6
- **Kind:** boundary
- **Expect:** pass
- **Note:** today's path (spec R6, G3: while BUG-2630 is open, R6 is reached through other workspaces' numbers). Retire this card when BUG-2630 is fixed; AL-29 / AL-30 take over.

**Given**
1. `for i in range(1, 1000): db.add(PurchaseOrder(workspace_id=W2.id, po_number=f"PO-2031-{i:03d}", account_id=A2.id, destination_type="storage", destination_id=F2.id, subtotal=Decimal("0.00"), total_amount=Decimal("0.00"), current_status_id=SD2.id, created_by=U1.id, created_at=T3))`, then one `db.flush()`.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-1000"`.

### PUO-AL-22 — the year comes from the clock: 2033 gives PO-2033-001, 2031 numbers do not count
- **Rules:** `allocate_po_number` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2031-005"`.
2. clock(`datetime(2033, 3, 1, 12, 0)`, `datetime(2033, 3, 1, 12, 0)`).

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2033-001"`.

### PUO-AL-23 — the year is UTC's when the local clock is already in the next year
- **Rules:** `allocate_po_number` R1 [BUG-2632]
- **Kind:** bug
- **Expect:** xfail BUG-2632
- **Fails today on:** Then 2 (today the local year: `PO-2032-001`)

**Given**
1. O1 = po `"PO-2031-004"`.
2. clock(`datetime(2032, 1, 1, 0, 30)`, `datetime(2031, 12, 31, 18, 30)`).

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.startswith("PO-")`.
2. returns: `result == "PO-2031-005"`.

### PUO-AL-24 — the year is UTC's when the local clock is still in the old year
- **Rules:** `allocate_po_number` R1 [BUG-2632]
- **Kind:** bug
- **Expect:** xfail BUG-2632
- **Fails today on:** Then 2 (today the local year: `PO-2031-005`)

**Given**
1. O1 = po `"PO-2031-004"`.
2. clock(`datetime(2031, 12, 31, 20, 0)`, `datetime(2032, 1, 1, 2, 0)`).

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.startswith("PO-")`.
2. returns: `result == "PO-2032-001"`.

### PUO-AL-25 — stores nothing: a pending PO is not counted and stays pending, an edit stays unflushed, no lock
- **Rules:** `allocate_po_number` R4, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = po `"PO-2031-002"`.
2. `O1.total_amount = Decimal("5.00")` (not flushed).
3. `P = PurchaseOrder(workspace_id=W1.id, po_number="PO-2031-050", account_id=A1.id, destination_type="storage", destination_id=F1.id, subtotal=Decimal("0.00"), total_amount=Decimal("0.00"), current_status_id=SD1.id, created_by=U1.id, created_at=T3)`, then `db.add(P)` (not flushed).
4. Statement recorder.

**When**
- `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-003"`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `O1 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `all("FOR UPDATE" not in s for s in sqls)`.

### PUO-AL-26 — keyword-only: a positional workspace id raises TypeError
- **Rules:** `allocate_po_number` signature
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no PO.

**When**
- `result = dao.allocate_po_number(db, W1.id)`.

**Then**
1. raises: `TypeError`.

### PUO-AL-27 — the same number twice in one workspace is refused by the database
- **Rules:** Model facts (`uq_po_workspace_number`); `allocate_po_number` R7 (today half)
- **Kind:** error
- **Expect:** pass

**Given**
1. O1 = po `"PO-2031-008"`.

**When**
- insert O2 = po `"PO-2031-008"` and flush (`db.add(O2); db.flush()`).

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. raises: `"uq_po_workspace_number" in str(exc.value.orig)`.

### PUO-AL-28 — the same number in two workspaces is accepted
- **Rules:** Model facts (`uq_po_workspace_number` is per workspace)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = po `"PO-2031-008"`.

**When**
- insert X2 = po of W2 `"PO-2031-008"` and flush (`db.add(X2); db.flush()`).

**Then**
1. returns: `X2.id is not None`.
2. count: `db.scalar(select(func.count()).select_from(PurchaseOrder).where(PurchaseOrder.po_number == "PO-2031-008"))` `== 2`.

### PUO-AL-29 — with the taken check always answering taken, 1000 candidates raise 500
- **Rules:** `allocate_po_number` R6 [BUG-2630]; Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-2630
- **Author:** claude
- **Fails today on:** Then 1 (no error is raised: today the helper does not exist and `PO-2031-001` is returned)
- **Race simulation:** patches `_po_number_taken` (spec R6, G3).

**Given**
1. W1 has no PO; W0 and W2 have no PO.

**When**
- `with patch("app.dao.purchase_order._po_number_taken", return_value=True, create=True) as taken:` `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 500`.
3. raises: `exc.value.detail == "Could not allocate a unique purchase order number"`.
4. mock called: `taken.call_count == 1000`.
5. mock called: `taken.call_args_list[0].kwargs["workspace_id"] == W1.id`.
6. mock called: `taken.call_args_list[0].kwargs["po_number"] == "PO-2031-001"`.
7. nothing written: nothing written.

### PUO-AL-30 — with 999 candidates taken, the 1000th is returned
- **Rules:** `allocate_po_number` R6 [BUG-2630]
- **Kind:** bug
- **Expect:** xfail BUG-2630
- **Author:** claude
- **Fails today on:** Then 1 (today the helper is not called and `PO-2031-001` is returned)
- **Race simulation:** patches `_po_number_taken` (spec R6, G3).

**Given**
1. W1 has no PO; W0 and W2 have no PO.

**When**
- `with patch("app.dao.purchase_order._po_number_taken", side_effect=[True] * 999 + [False], create=True) as taken:` `result = dao.allocate_po_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "PO-2031-1000"`.
2. mock called: `taken.call_count == 1000`.

## `PurchaseOrderItemDAO.get_by_order`

### PUO-IO-01 — lines by line_number, though inserted out of order
- **Rules:** `get_by_order` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L3 = line of O1, `line_number 3`, but `item_id IN1.id`.
3. L1 = line of O1, `line_number 1`.
4. L2 = line of O1, `line_number 2`, but `item_id IK.id`.

**When**
- `result = idao.get_by_order(db, purchase_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [L1.id, L2.id, L3.id]`.

### PUO-IO-02 — lines of a lower and a higher PO are not mixed in
- **Rules:** `get_by_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`.
3. O3 = po `"PO-2026-103"`.
4. LA = line of O1, `line_number 1`.
5. LB = line of O2, `line_number 2`.
6. LC = line of O3, `line_number 1`.

**When**
- `result = idao.get_by_order(db, purchase_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [LB.id]`.

### PUO-IO-03 — W0's PO asked in W1 gives nothing
- **Rules:** `get_by_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-101"`.
2. LX = line of X0, `line_number 1`.
3. O1 = po `"PO-2026-101"`.
4. L1 = line of O1, `line_number 1`.

**When**
- `result = idao.get_by_order(db, purchase_order_id=X0.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PUO-IO-04 — W2's PO asked in W1 gives nothing
- **Rules:** `get_by_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.
3. X2 = po of W2 `"PO-2026-101"`.
4. LX = line of X2, `line_number 1`.

**When**
- `result = idao.get_by_order(db, purchase_order_id=X2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PUO-IO-05 — asked in W2, W2's lines are returned
- **Rules:** `get_by_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.
3. X2 = po of W2 `"PO-2026-101"`.
4. LX = line of X2, `line_number 1`.

**When**
- `result = idao.get_by_order(db, purchase_order_id=X2.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [LX.id]`.

### PUO-IO-06 — an unknown PO gives nothing
- **Rules:** `get_by_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.

**When**
- `result = idao.get_by_order(db, purchase_order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PUO-IO-07 — not paged: 101 lines are all returned
- **Rules:** `get_by_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. `for k in range(1, 102): db.add(PurchaseOrderItem(workspace_id=W1.id, purchase_order_id=O1.id, line_number=k, item_id=I1.id, quantity_ordered=Decimal("1.00"), quantity_received=Decimal("0.00")))`, then one `db.flush()`.

**When**
- `result = idao.get_by_order(db, purchase_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `[r.line_number for r in result] == list(range(1, 102))`.

### PUO-IO-08 — orders by line_number, does not join the PO, takes no lock, writes nothing
- **Rules:** `get_by_order` R1, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.
3. `db.expunge_all()`
4. Statement recorder.

**When**
- `result = idao.get_by_order(db, purchase_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [L1.id]`.
2. statement: `"line_number" in order_part`.
3. statement: `"purchase_orders" not in sql`.
4. statement: `"FOR UPDATE" not in sql`.
5. statement: `written == []`.

## `PurchaseOrderItemDAO.get_by_purchase_order_ids`

### PUO-IP-01 — an empty id list gives [] without a query
- **Rules:** `get_by_purchase_order_ids` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.
3. Statement recorder.

**When**
- `result = idao.get_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[])`.

**Then**
1. returns: `result == []`.
2. statement: `sqls == []`.

### PUO-IP-02 — lines ordered by PO id, then line_number; an unasked PO in between is left out
- **Rules:** `get_by_purchase_order_ids` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`.
3. O3 = po `"PO-2026-103"`.
4. C1 = line of O3, `line_number 1`.
5. A2 = line of O1, `line_number 2`.
6. B1 = line of O2, `line_number 1`.
7. A1 = line of O1, `line_number 1`.
8. C2 = line of O3, `line_number 2`.

**When**
- `result = idao.get_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O3.id, O1.id])`.

**Then**
1. returns: `ids(result) == [A1.id, A2.id, C1.id, C2.id]`.

### PUO-IP-03 — ids of W0's and W2's POs contribute nothing
- **Rules:** `get_by_purchase_order_ids` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-101"`.
2. LX0 = line of X0, `line_number 1`.
3. O2 = po `"PO-2026-102"`.
4. L2 = line of O2, `line_number 1`.
5. X2 = po of W2 `"PO-2026-101"`.
6. LX2 = line of X2, `line_number 1`.

**When**
- `result = idao.get_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[X0.id, O2.id, X2.id])`.

**Then**
1. returns: `ids(result) == [L2.id]`.

### PUO-IP-04 — an unknown id gives []
- **Rules:** `get_by_purchase_order_ids` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.

**When**
- `result = idao.get_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[MISSING])`.

**Then**
1. returns: `result == []`.

### PUO-IP-05 — takes no lock and writes nothing
- **Rules:** `get_by_purchase_order_ids` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.
3. `db.expunge_all()`
4. Statement recorder.

**When**
- `result = idao.get_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `ids(result) == [L1.id]`.
2. statement: `"FOR UPDATE" not in sql`.
3. statement: `written == []`.

## `PurchaseOrderItemDAO.get_by_id_and_workspace`

### PUO-IG-01 — returns the line, with lower and higher line ids beside it
- **Rules:** `PurchaseOrderItemDAO.get_by_id_and_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.
3. L2 = line of O1, `line_number 2`, but `item_id IN1.id`.
4. L3 = line of O1, `line_number 3`.

**When**
- `result = idao.get_by_id_and_workspace(db, id=L2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L2.id`.
2. returns: `result.item_id == IN1.id`.

### PUO-IG-02 — W0's line is not returned for W1
- **Rules:** `PurchaseOrderItemDAO.get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-101"`.
2. LX = line of X0, `line_number 1`.

**When**
- `result = idao.get_by_id_and_workspace(db, id=LX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PUO-IG-03 — W2's line is not returned for W1
- **Rules:** `PurchaseOrderItemDAO.get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X2 = po of W2 `"PO-2026-101"`.
2. LX = line of X2, `line_number 1`.

**When**
- `result = idao.get_by_id_and_workspace(db, id=LX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PUO-IG-04 — asked in W2, W2's line is returned
- **Rules:** `PurchaseOrderItemDAO.get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X2 = po of W2 `"PO-2026-101"`.
2. LX = line of X2, `line_number 1`.

**When**
- `result = idao.get_by_id_and_workspace(db, id=LX.id, workspace_id=W2.id)`.

**Then**
1. returns: `result.id == LX.id`.

### PUO-IG-05 — an unknown id returns None
- **Rules:** `PurchaseOrderItemDAO.get_by_id_and_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.

**When**
- `result = idao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PUO-IG-06 — no row lock, writes nothing
- **Rules:** `PurchaseOrderItemDAO.get_by_id_and_workspace` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.
3. `db.expunge_all()`
4. Statement recorder.

**When**
- `result = idao.get_by_id_and_workspace(db, id=L1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L1.id`.
2. statement: `"FOR UPDATE" not in sql`.
3. statement: `written == []`.

## `PurchaseOrderItemDAO.summarize_by_purchase_order_ids`

*The sums (R2) and the refunded total (R2a, BUG-2641) are in the section "sums and refunded total" below. These cards check which keys appear.*

### PUO-IS-01 — an empty id list gives {}
- **Rules:** `summarize_by_purchase_order_ids` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.

**When**
- `result = idao.summarize_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[])`.

**Then**
1. returns: `result == {}`.

### PUO-IS-02 — only asked POs of W1 with lines get a key
- **Rules:** `summarize_by_purchase_order_ids` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-101"`.
2. LX0 = line of X0, `line_number 1`.
3. O1 = po `"PO-2026-101"`.
4. L1 = line of O1, `line_number 1`.
5. O2 = po `"PO-2026-102"`.
6. O3 = po `"PO-2026-103"`.
7. L3 = line of O3, `line_number 1`.
8. X2 = po of W2 `"PO-2026-101"`.
9. LX2 = line of X2, `line_number 1`.

**When**
- `result = idao.summarize_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[X0.id, O1.id, O2.id, X2.id])`.

**Then**
1. returns: `set(result.keys()) == {O1.id}`.

### PUO-IS-03 — an unknown id gives {}
- **Rules:** `summarize_by_purchase_order_ids` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.

**When**
- `result = idao.summarize_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[MISSING])`.

**Then**
1. returns: `result == {}`.

### PUO-IS-04 — takes no lock and writes nothing
- **Rules:** `summarize_by_purchase_order_ids` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.
3. Statement recorder.

**When**
- `result = idao.summarize_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `set(result.keys()) == {O1.id}`.
2. statement: `all("FOR UPDATE" not in s for s in sqls)`.
3. statement: `written == []`.

## `PurchaseOrderItemDAO.preview_names_by_purchase_order_ids`

### PUO-IN-01 — an empty id list gives {}
- **Rules:** `preview_names_by_purchase_order_ids` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.

**When**
- `result = idao.preview_names_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[])`.

**Then**
1. returns: `result == {}`.

### PUO-IN-02 — limit 0 gives {}
- **Rules:** `preview_names_by_purchase_order_ids` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.

**When**
- `result = idao.preview_names_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id], limit=0)`.

**Then**
1. returns: `result == {}`.

### PUO-IN-03 — a negative limit gives {}
- **Rules:** `preview_names_by_purchase_order_ids` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.

**When**
- `result = idao.preview_names_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id], limit=-1)`.

**Then**
1. returns: `result == {}`.

### PUO-IN-04 — limit 1 gives the first line's name
- **Rules:** `preview_names_by_purchase_order_ids` R1, R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L2 = line of O1, `line_number 2`, but `item_id IN1.id`.
3. L1 = line of O1, `line_number 1`.

**When**
- `result = idao.preview_names_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id], limit=1)`.

**Then**
1. returns: `result == {O1.id: ["Bolt"]}`.

### PUO-IN-05 — by default the first 4 names in line order
- **Rules:** `preview_names_by_purchase_order_ids` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L5 = line of O1, `line_number 5`, but `item_id IR.id`.
3. L3 = line of O1, `line_number 3`, but `item_id IK.id`.
4. L1 = line of O1, `line_number 1`.
5. L4 = line of O1, `line_number 4`, but `item_id IW.id`.
6. L2 = line of O1, `line_number 2`, but `item_id IN1.id`.

**When**
- `result = idao.preview_names_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `result == {O1.id: ["Bolt", "Nut", "Steel", "Washer"]}`.

### PUO-IN-06 — limit=1000 gives every name
- **Rules:** `preview_names_by_purchase_order_ids` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L5 = line of O1, `line_number 5`, but `item_id IR.id`.
3. L3 = line of O1, `line_number 3`, but `item_id IK.id`.
4. L1 = line of O1, `line_number 1`.
5. L4 = line of O1, `line_number 4`, but `item_id IW.id`.
6. L2 = line of O1, `line_number 2`, but `item_id IN1.id`.

**When**
- `result = idao.preview_names_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id], limit=1000)`.

**Then**
1. returns: `result == {O1.id: ["Bolt", "Nut", "Steel", "Washer", "Rivet"]}`.

### PUO-IN-07 — the same item on two lines gives its name twice
- **Rules:** `preview_names_by_purchase_order_ids` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.
3. L2 = line of O1, `line_number 2`.

**When**
- `result = idao.preview_names_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `result == {O1.id: ["Bolt", "Bolt"]}`.

### PUO-IN-08 — an item with an empty name shows as Item #id
- **Rules:** `preview_names_by_purchase_order_ids` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`, but `item_id IE.id`.
3. L2 = line of O1, `line_number 2`.

**When**
- `result = idao.preview_names_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `result == {O1.id: [f"Item #{IE.id}", "Bolt"]}`.

### PUO-IN-09 — the limit applies per PO; POs without lines and other workspaces' POs get no key
- **Rules:** `preview_names_by_purchase_order_ids` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-101"`.
2. LX0 = line of X0, `line_number 1`.
3. O1 = po `"PO-2026-101"`.
4. A1L = line of O1, `line_number 1`.
5. A2L = line of O1, `line_number 2`, but `item_id IN1.id`.
6. A3L = line of O1, `line_number 3`, but `item_id IK.id`.
7. O2 = po `"PO-2026-102"`.
8. O3 = po `"PO-2026-103"`.
9. C1L = line of O3, `line_number 1`, but `item_id IW.id`.
10. C2L = line of O3, `line_number 2`, but `item_id IR.id`.
11. C3L = line of O3, `line_number 3`.
12. X2 = po of W2 `"PO-2026-101"`.
13. LX2 = line of X2, `line_number 1`.

**When**
- `result = idao.preview_names_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[X0.id, O1.id, O2.id, O3.id, X2.id], limit=2)`.

**Then**
1. returns: `result == {O1.id: ["Bolt", "Nut"], O3.id: ["Washer", "Rivet"]}`.

### PUO-IN-10 — lines sharing a line number come lower id first, after the lowest id was updated
- **Rules:** `preview_names_by_purchase_order_ids` R3 [BUG-2638]
- **Kind:** bug
- **Expect:** xfail BUG-2638 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `id` tie-break; physical row order puts LA last)

**Given**
1. O1 = po `"PO-2026-101"`.
2. LA = line of O1, `line_number 1`, but `item_id IN1.id`.
3. LB = line of O1, `line_number 1`.
4. LC = line of O1, `line_number 1`, but `item_id IK.id`.
5. seqscan.
6. bumpL(LA).

**When**
- `result = idao.preview_names_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `len(result[O1.id]) == 3`.
2. returns: `result[O1.id] == ["Nut", "Bolt", "Steel"]`.

### PUO-IN-11 — lines sharing a line number: a high explicit id comes last
- **Rules:** `preview_names_by_purchase_order_ids` R3 [BUG-2638]
- **Kind:** bug
- **Expect:** xfail BUG-2638 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `id` tie-break; physical row order decides)

**Given**
1. O1 = po `"PO-2026-101"`.
2. EB = line of O1, `line_number 1`.
3. EH = line of O1, `line_number 1`, but `item_id IN1.id`, `id HIGH_ID(purchase_order_items)`.
4. EA = line of O1, `line_number 1`, but `item_id IK.id`.

**When**
- `result = idao.preview_names_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `len(result[O1.id]) == 3`.
2. returns: `result[O1.id] == ["Bolt", "Steel", "Nut"]`.

### PUO-IN-12 — the preview query breaks line-number ties by line id
- **Rules:** `preview_names_by_purchase_order_ids` R3 [BUG-2638]
- **Kind:** bug
- **Expect:** xfail BUG-2638
- **Fails today on:** Then 3 (the query orders by PO and `line_number` only)

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.
3. Statement recorder.

**When**
- `result = idao.preview_names_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `result == {O1.id: ["Bolt"]}`.
2. statement: `"line_number" in order_part`.
3. statement: `"purchase_order_items.id" in order_part`.
4. statement: `order_part.index("line_number") < order_part.index("purchase_order_items.id")`.

### PUO-IN-13 — takes no lock and writes nothing
- **Rules:** `preview_names_by_purchase_order_ids` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.
3. Statement recorder.

**When**
- `result = idao.preview_names_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `result == {O1.id: ["Bolt"]}`.
2. statement: `all("FOR UPDATE" not in s for s in sqls)`.
3. statement: `written == []`.

## `aggregate_hub_stats` — voided POs (BUG-2639, owner OQ-35)

*Owner, 2026-11-11 (OQ-35 → BUG-2639): a voided PO kept by `exclude_voided=False` adds nothing to total value, open count or open value; it still counts in total count and, with no invoice, in not-invoiced count (R3b; AS-10 is the pass twin). Today it adds its `total_amount` to total value and, unless Complete and paid, counts as open with its full total. The IDs keep their `OQ35` prefix.*

### PUO-OQ35-01 — the verified example: (6, 606.00, 4, 506.00, 3) with a voided 400.00
- **Rules:** `aggregate_hub_stats` R1, R2 [BUG-2639], R3, R3a [BUG-2639], R4
- **Kind:** bug
- **Expect:** xfail BUG-2639
- **Fails today on:** Then 3 (today the voided 400.00 is added: `1006.00`)

**Given**
1. OA = po `"PO-2026-001"`, but `total_amount Decimal("100.00")`, closed, `invoice_id V1.id`.
2. OB = po `"PO-2026-002"`, but `total_amount Decimal("200.00")`, stage SC1, `invoice_id V2.id`.
3. OC = po `"PO-2026-003"`, but `total_amount Decimal("300.00")`, `invoice_id V3.id`.
4. OD = po `"PO-2026-004"`, but `total_amount Decimal("400.00")`, voided.
5. OE = po `"PO-2026-005"`, but `total_amount Decimal("1.00")`.
6. OF = po `"PO-2026-006"`, but `total_amount Decimal("5.00")`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result[0] == 6`.
2. returns: `result[4] == 3`.
3. returns: `result[1] == Decimal("606.00")`.
4. returns: `result[2] == 4`.
5. returns: `result[3] == Decimal("506.00")`.

### PUO-OQ35-02 — a shown voided PO counts in total count but adds nothing to total value
- **Rules:** `aggregate_hub_stats` R1, R2 [BUG-2639], R3b
- **Kind:** bug
- **Expect:** xfail BUG-2639
- **Fails today on:** Then 2 (today the voided 40.00 is added: `50.00`)

**Given**
1. O1 = po `"PO-2026-001"`, but `total_amount Decimal("10.00")`.
2. OV = po `"PO-2026-002"`, but `total_amount Decimal("40.00")`, voided.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_voided=False)`.

**Then**
1. returns: `result[0] == 2`.
2. returns: `result[1] == Decimal("10.00")`.

### PUO-OQ35-03 — a shown voided PO is never open
- **Rules:** `aggregate_hub_stats` R3a [BUG-2639]
- **Kind:** bug
- **Expect:** xfail BUG-2639
- **Fails today on:** Then 2 (today the voided PO counts as open: `2`)

**Given**
1. O1 = po `"PO-2026-001"`, but `total_amount Decimal("10.00")`.
2. OV = po `"PO-2026-002"`, but `total_amount Decimal("40.00")`, voided.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_voided=False)`.

**Then**
1. returns: `result[0] == 2`.
2. returns: `result[2] == 1`.
3. returns: `result[3] == Decimal("10.00")`.

### PUO-OQ35-04 — a voided PO marked Complete and paid adds nothing either (legacy data)
- **Rules:** `aggregate_hub_stats` R2 [BUG-2639], R3; `_purchase_order_is_fully_closed_clause` R1
- **Kind:** bug
- **Expect:** xfail BUG-2639
- **Fails today on:** Then 3 (today the voided 40.00 is added to total value: `50.00`)
- **Note:** a real void sets `paid False` (spec Notes, G6), so OV is legacy data; the card checks that such a row is still not open and adds no value.

**Given**
1. O1 = po `"PO-2026-001"`, but `total_amount Decimal("10.00")`.
2. OV = po `"PO-2026-002"`, but `total_amount Decimal("40.00")`, closed, voided.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result[2] == 1`.
2. returns: `result[3] == Decimal("10.00")`.
3. returns: `result[1] == Decimal("10.00")`.

## `aggregate_hub_stats` — open count and open value (owner OQ-36, intended)

*Owner, 2026-11-11 (OQ-36, intended): open count / open value cover every non-voided PO that is not both Complete and paid, at its full `total_amount` — a Complete unpaid PO and a paid PO still in Receiving each add their whole total. No card here keeps a voided PO (that is BUG-2639, above).*

### PUO-OQ36-01 — a Complete unpaid PO is open with its full total
- **Rules:** `aggregate_hub_stats` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. OB = po `"PO-2026-001"`, but `total_amount Decimal("200.00")`, stage SC1, `invoice_id V1.id`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False)`.

**Then**
1. returns: `result[2] == 1`.
2. returns: `result[3] == Decimal("200.00")`.

### PUO-OQ36-02 — a paid PO still in Receiving is open with its full total
- **Rules:** `aggregate_hub_stats` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. OR = po `"PO-2026-001"`, but `total_amount Decimal("300.00")`, stage SR1, `paid True`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False)`.

**Then**
1. returns: `result[2] == 1`.
2. returns: `result[3] == Decimal("300.00")`.

### PUO-OQ36-03 — a Complete and paid PO counts in the totals but is not open
- **Rules:** `aggregate_hub_stats` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = po `"PO-2026-001"`, but `total_amount Decimal("100.00")`, closed.
2. OE = po `"PO-2026-002"`, but `total_amount Decimal("5.00")`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False)`.

**Then**
1. returns: `result[0] == 2`.
2. returns: `result[1] == Decimal("105.00")`.
3. returns: `result[2] == 1`.
4. returns: `result[3] == Decimal("5.00")`.

### PUO-OQ36-04 — open value is an exact sum
- **Rules:** `aggregate_hub_stats` R3, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-001"`, but `total_amount Decimal("0.10")`.
2. O2 = po `"PO-2026-002"`, but `total_amount Decimal("0.20")`, stage SP1.
3. O3 = po `"PO-2026-003"`, but `total_amount Decimal("0.30")`, stage SR1.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[2] == 3`.
2. returns: `result[3] == Decimal("0.60")`.
3. returns: `isinstance(result[3], Decimal)`.

### PUO-OQ36-05 — with the default filters every counted PO is open
- **Rules:** `aggregate_hub_stats` R3; `_apply…` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-001"`, but `total_amount Decimal("10.00")`.
2. O2 = po `"PO-2026-002"`, but `total_amount Decimal("20.00")`, stage SC1.
3. OA = po `"PO-2026-003"`, but `total_amount Decimal("100.00")`, closed.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[0] == 2`.
2. returns: `result[2] == 2`.
3. returns: `result[3] == Decimal("30.00")`.

### PUO-OQ36-06 — no open PO gives open count 0 and open value 0
- **Rules:** `aggregate_hub_stats` R3, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = po `"PO-2026-001"`, but `total_amount Decimal("100.00")`, closed.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False)`.

**Then**
1. returns: `result[0] == 1`.
2. returns: `result[2] == 0`.
3. returns: `result[3] == Decimal("0")`.

## `_apply_purchase_order_hub_filters` — outstanding payment (BUG-2640, owner OQ-37)

*Owner, 2026-11-11 (OQ-37 → BUG-2640): `invoice_filter="outstanding_payment"` keeps only POs whose invoice is `confirmed` or `locked` and whose `payment_status` is not `paid` (`unpaid`, `partial`, `overdue`). A draft or voided invoice is not outstanding; a PO with no invoice is not kept. Today any `invoice_status` counts. The IDs keep their `OQ37` prefix.*

*Extra invoice rows used here (each = invoice of W1, but the columns named):* **VP** = `payment_status "paid"`, `paid_amount Decimal("100.00")`. **VD** = `invoice_status "draft"`. **VX** = a real void: `invoice_status "voided"`, `void_note "Entered twice"`, `paid_amount Decimal("0.00")`, `payment_status "unpaid"`. **VXP** = `invoice_status "voided"`, `payment_status "paid"`, `paid_amount Decimal("100.00")` (legacy data: a real void resets `payment_status` to `unpaid`).

### PUO-OQ37-01 — a confirmed unpaid invoice is outstanding; a paid invoice and no invoice are not
- **Rules:** `_apply…` R9 [BUG-2640]
- **Kind:** happy
- **Expect:** pass

**Given**
1. VP = invoice of W1, but `payment_status "paid"`, `paid_amount Decimal("100.00")`.
2. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.
3. O2 = po `"PO-2026-102"`, but `invoice_id VP.id`.
4. O3 = po `"PO-2026-103"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, invoice_filter="outstanding_payment")`.

**Then**
1. returns: `idset(result) == {O1.id}`.

### PUO-OQ37-02 — a PO whose invoice is a draft is not outstanding
- **Rules:** `_apply…` R9 [BUG-2640]
- **Kind:** bug
- **Expect:** xfail BUG-2640
- **Fails today on:** Then 2 (today the draft-invoice PO O1 is kept)

**Given**
1. VD = invoice of W1, but `invoice_status "draft"`.
2. O1 = po `"PO-2026-101"`, but `invoice_id VD.id`.
3. O2 = po `"PO-2026-102"`.
4. O3 = po `"PO-2026-103"`, but `invoice_id V1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, invoice_filter="outstanding_payment")`.

**Then**
1. returns: `O3.id in idset(result)`.
2. returns: `idset(result) == {O3.id}`.

### PUO-OQ37-03 — a PO whose invoice was voided (reset to unpaid) is not outstanding
- **Rules:** `_apply…` R9 [BUG-2640]
- **Kind:** bug
- **Expect:** xfail BUG-2640
- **Fails today on:** Then 2 (today the voided-invoice PO O1 is kept)

**Given**
1. VX = invoice of W1, but `invoice_status "voided"`, `void_note "Entered twice"`, `paid_amount Decimal("0.00")`, `payment_status "unpaid"`.
2. O1 = po `"PO-2026-101"`, but `invoice_id VX.id`.
3. O2 = po `"PO-2026-102"`.
4. O3 = po `"PO-2026-103"`, but `invoice_id V1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, invoice_filter="outstanding_payment")`.

**Then**
1. returns: `O3.id in idset(result)`.
2. returns: `idset(result) == {O3.id}`.

### PUO-OQ37-04 — a PO whose voided invoice is marked paid is not outstanding (legacy data)
- **Rules:** `_apply…` R9 [BUG-2640]
- **Kind:** boundary
- **Expect:** pass
- **Note:** VXP is legacy data (a real void resets `payment_status`); it is left out today and after the fix.

**Given**
1. VXP = invoice of W1, but `invoice_status "voided"`, `payment_status "paid"`, `paid_amount Decimal("100.00")`.
2. O1 = po `"PO-2026-101"`, but `invoice_id VXP.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, invoice_filter="outstanding_payment")`.

**Then**
1. returns: `result == []`.

### PUO-OQ37-05 — count_for_hub counts only the confirmed unpaid PO
- **Rules:** `_apply…` R9 [BUG-2640]; `count_for_hub` R1
- **Kind:** bug
- **Expect:** xfail BUG-2640
- **Fails today on:** Then 2 (today the draft and voided invoices count too: `3`)

**Given**
1. VD = invoice of W1, but `invoice_status "draft"`.
2. VX = invoice of W1, but `invoice_status "voided"`, `void_note "Entered twice"`, `paid_amount Decimal("0.00")`, `payment_status "unpaid"`.
3. VP = invoice of W1, but `payment_status "paid"`, `paid_amount Decimal("100.00")`.
4. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.
5. O2 = po `"PO-2026-102"`, but `invoice_id VD.id`.
6. O3 = po `"PO-2026-103"`, but `invoice_id VX.id`.
7. O4 = po `"PO-2026-104"`, but `invoice_id VP.id`.
8. O5 = po `"PO-2026-105"`.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, invoice_filter="outstanding_payment")`.

**Then**
1. returns: `isinstance(result, int)`.
2. returns: `result == 1`.

### PUO-OQ37-06 — W0's and W2's outstanding POs are not listed for W1
- **Rules:** `_apply…` R9 [BUG-2640], R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = po of W0 `"PO-2026-101"`, but `invoice_id V0.id`.
2. O1 = po `"PO-2026-101"`, but `invoice_id V1.id`.
3. X2 = po of W2 `"PO-2026-101"`, but `invoice_id V9.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, invoice_filter="outstanding_payment")`.

**Then**
1. returns: `idset(result) == {O1.id}`.

### PUO-OQ37-07 — locked unpaid, confirmed partial and confirmed overdue are outstanding; confirmed paid is not
- **Rules:** `_apply…` R9 [BUG-2640]
- **Kind:** boundary
- **Expect:** pass

**Given**
1. VL = invoice of W1, but `invoice_status "locked"`.
2. VPA = invoice of W1, but `payment_status "partial"`, `paid_amount Decimal("40.00")`.
3. VO = invoice of W1, but `payment_status "overdue"`.
4. VP = invoice of W1, but `payment_status "paid"`, `paid_amount Decimal("100.00")`.
5. O1 = po `"PO-2026-101"`, but `invoice_id VL.id`.
6. O2 = po `"PO-2026-102"`, but `invoice_id VPA.id`.
7. O3 = po `"PO-2026-103"`, but `invoice_id VO.id`.
8. O4 = po `"PO-2026-104"`, but `invoice_id VP.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, invoice_filter="outstanding_payment")`.

**Then**
1. returns: `idset(result) == {O1.id, O2.id, O3.id}`.

## `summarize_by_purchase_order_ids` — sums (R2) and refunded total (BUG-2641, owner OQ-38)

*Owner, 2026-11-11 (OQ-38 → BUG-2641): `item_count`, `quantity_ordered_total` and `quantity_received_total` stay the raw sums (R2, intended; refunded and returned quantities play no part, different items' units are added together). Each summary also gets `quantity_refunded_total` = sum of `quantity_refunded` (R2a; today missing). OQ38-01 … 07 check R2 key by key, so they hold before and after the fix; OQ38-08 … 10 are the R2a xfail cards. The IDs keep their `OQ38` prefix.*

### PUO-OQ38-01 — the verified example: 3 lines, 16.50 ordered, 8.00 received, refunded not subtracted
- **Rules:** `summarize_by_purchase_order_ids` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`, but stage SR1.
2. LA = line of O1, `line_number 1`, but `quantity_ordered Decimal("10.00")`, `quantity_received Decimal("7.00")`, `quantity_refunded Decimal("3.00")`.
3. LB = line of O1, `line_number 2`, but `item_id IN1.id`, `quantity_ordered Decimal("5.50")`.
4. LC = line of O1, `line_number 3`, but `item_id IK.id`, `quantity_received Decimal("1.00")`.

**When**
- `result = idao.summarize_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `set(result.keys()) == {O1.id}`.
2. returns: `result[O1.id]["item_count"] == 3`.
3. returns: `result[O1.id]["quantity_ordered_total"] == Decimal("16.50")`.
4. returns: `result[O1.id]["quantity_received_total"] == Decimal("8.00")`.

### PUO-OQ38-02 — a returned quantity plays no part
- **Rules:** `summarize_by_purchase_order_ids` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`, but `quantity_ordered Decimal("4.00")`, `quantity_received Decimal("4.00")`, `quantity_returned Decimal("2.00")`.

**When**
- `result = idao.summarize_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `result[O1.id]["quantity_ordered_total"] == Decimal("4.00")`.
2. returns: `result[O1.id]["quantity_received_total"] == Decimal("4.00")`.

### PUO-OQ38-03 — quantities of items in different units are added together
- **Rules:** `summarize_by_purchase_order_ids` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`, but `quantity_ordered Decimal("2.00")`.
3. L2 = line of O1, `line_number 2`, but `item_id IK.id`, `quantity_ordered Decimal("1.50")`, `quantity_received Decimal("0.75")`.

**When**
- `result = idao.summarize_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `result[O1.id]["quantity_ordered_total"] == Decimal("3.50")`.
2. returns: `result[O1.id]["quantity_received_total"] == Decimal("0.75")`.

### PUO-OQ38-04 — sums are exact Decimals
- **Rules:** `summarize_by_purchase_order_ids` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`, but `quantity_ordered Decimal("0.10")`, `quantity_received Decimal("0.05")`.
3. L2 = line of O1, `line_number 2`, but `quantity_ordered Decimal("0.20")`, `quantity_received Decimal("0.05")`.

**When**
- `result = idao.summarize_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `result[O1.id]["quantity_ordered_total"] == Decimal("0.30")`.
2. returns: `isinstance(result[O1.id]["quantity_ordered_total"], Decimal)`.
3. returns: `result[O1.id]["quantity_received_total"] == Decimal("0.10")`.

### PUO-OQ38-05 — stored quantities are rounded half up before they are summed
- **Rules:** `summarize_by_purchase_order_ids` R2; Model facts (`quantity_ordered` Numeric(15, 2)); HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`, but `quantity_ordered Decimal("2.125")`.
3. L2 = line of O1, `line_number 2`, but `quantity_ordered Decimal("0.005")`.

**When**
- `result = idao.summarize_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `result[O1.id]["quantity_ordered_total"] == Decimal("2.14")`.

### PUO-OQ38-06 — each asked PO gets its own sums
- **Rules:** `summarize_by_purchase_order_ids` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`.
3. O3 = po `"PO-2026-103"`.
4. A1L = line of O1, `line_number 1`, but `quantity_ordered Decimal("2.00")`.
5. B1L = line of O2, `line_number 1`, but `quantity_ordered Decimal("50.00")`.
6. C1L = line of O3, `line_number 1`, but `quantity_ordered Decimal("3.00")`, `quantity_received Decimal("1.00")`.
7. A2L = line of O1, `line_number 2`, but `quantity_ordered Decimal("4.00")`, `quantity_received Decimal("4.00")`.

**When**
- `result = idao.summarize_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O3.id, O1.id])`.

**Then**
1. returns: `set(result.keys()) == {O1.id, O3.id}`.
2. returns: `result[O1.id]["item_count"] == 2`.
3. returns: `result[O1.id]["quantity_ordered_total"] == Decimal("6.00")`.
4. returns: `result[O1.id]["quantity_received_total"] == Decimal("4.00")`.
5. returns: `result[O3.id]["item_count"] == 1`.
6. returns: `result[O3.id]["quantity_ordered_total"] == Decimal("3.00")`.
7. returns: `result[O3.id]["quantity_received_total"] == Decimal("1.00")`.

### PUO-OQ38-07 — the same item on two lines counts as two lines
- **Rules:** `summarize_by_purchase_order_ids` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`.
3. L2 = line of O1, `line_number 2`.

**When**
- `result = idao.summarize_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `result[O1.id]["item_count"] == 2`.
2. returns: `result[O1.id]["quantity_ordered_total"] == Decimal("2.00")`.

### PUO-OQ38-08 — the verified example also carries 3.00 refunded
- **Rules:** `summarize_by_purchase_order_ids` R2a [BUG-2641]
- **Kind:** bug
- **Expect:** xfail BUG-2641
- **Fails today on:** Then 3 (today the summary has no `quantity_refunded_total` key: KeyError)

**Given**
1. O1 = po `"PO-2026-101"`, but stage SR1.
2. LA = line of O1, `line_number 1`, but `quantity_ordered Decimal("10.00")`, `quantity_received Decimal("7.00")`, `quantity_refunded Decimal("3.00")`.
3. LB = line of O1, `line_number 2`, but `item_id IN1.id`, `quantity_ordered Decimal("5.50")`.
4. LC = line of O1, `line_number 3`, but `item_id IK.id`, `quantity_received Decimal("1.00")`.

**When**
- `result = idao.summarize_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `result[O1.id]["quantity_ordered_total"] == Decimal("16.50")`.
2. returns: `result[O1.id]["quantity_received_total"] == Decimal("8.00")`.
3. returns: `result[O1.id]["quantity_refunded_total"] == Decimal("3.00")`.
4. returns: `set(result[O1.id].keys()) == {"item_count", "quantity_ordered_total", "quantity_received_total", "quantity_refunded_total"}`.

### PUO-OQ38-09 — nothing refunded gives 0, and a returned quantity is not refunded
- **Rules:** `summarize_by_purchase_order_ids` R2a [BUG-2641]
- **Kind:** bug
- **Expect:** xfail BUG-2641
- **Fails today on:** Then 2 (today the summary has no `quantity_refunded_total` key: KeyError)

**Given**
1. O1 = po `"PO-2026-101"`.
2. L1 = line of O1, `line_number 1`, but `quantity_ordered Decimal("4.00")`, `quantity_received Decimal("4.00")`, `quantity_returned Decimal("2.00")`.

**When**
- `result = idao.summarize_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id])`.

**Then**
1. returns: `result[O1.id]["item_count"] == 1`.
2. returns: `result[O1.id]["quantity_refunded_total"] == 0`.
3. returns: `isinstance(result[O1.id]["quantity_refunded_total"], Decimal)`.

### PUO-OQ38-10 — refunded totals are exact and kept per order
- **Rules:** `summarize_by_purchase_order_ids` R1, R2a [BUG-2641]
- **Kind:** bug
- **Expect:** xfail BUG-2641
- **Fails today on:** Then 2 (today the summary has no `quantity_refunded_total` key: KeyError)

**Given**
1. O1 = po `"PO-2026-101"`.
2. O2 = po `"PO-2026-102"`.
3. L1 = line of O1, `line_number 1`, but `quantity_ordered Decimal("1.00")`, `quantity_refunded Decimal("0.10")`.
4. L2 = line of O2, `line_number 1`, but `quantity_ordered Decimal("9.00")`, `quantity_refunded Decimal("5.00")`.
5. L3 = line of O1, `line_number 2`, but `quantity_ordered Decimal("1.00")`, `quantity_refunded Decimal("0.20")`.

**When**
- `result = idao.summarize_by_purchase_order_ids(db, workspace_id=W1.id, purchase_order_ids=[O1.id, O2.id])`.

**Then**
1. returns: `set(result.keys()) == {O1.id, O2.id}`.
2. returns: `result[O1.id]["quantity_refunded_total"] == Decimal("0.30")`.
3. returns: `result[O2.id]["quantity_refunded_total"] == Decimal("5.00")`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `allocate_po_number` R7 [BUG-2631] — race half | integration test (two transactions) | Two concurrent creates in one workspace both succeed with distinct numbers. AL-27 keeps the 23505 fact for a same-workspace duplicate. |
| `_purchase_order_is_fully_closed_clause` R1 — `complete` / `Complete ` not closed; `get_pending_highlights_for_hub` R2, R4 — exact `Planning` / `Draft` | BUG-1881 (owner OQ-13), status-name fix | Stage names compared by exact spelling are a bug fixed there; no card here pins the misspelling. |
| FU-1 — no `FOR UPDATE` read for state changes | `PurchaseOrderManager` spec | HR-10 lock on receive / void / complete / reopen / approval / invoice link. |
| FU-2 — `invoice_id` settable through `PurchaseOrderUpdate` | `PurchaseOrderManager` / service spec | A client cannot link another order's or another workspace's invoice (HR-16). |
| FU-3 — line numbers max + 1 without a lock | `PurchaseOrderManager.add_item` / `replace_items` | Concurrent adds give distinct line numbers. |
| FU-4 — unique violation on create after BUG-2630 / BUG-2631 | `PurchaseOrderManager.create_purchase_order` | Retry or counter; no dependence on the 1000-attempt loop. |
| FU-5 — BUG-2641 wording and "done" test | `PurchaseOrderService._attach_item_summaries`, web app `PurchaseOrderListRow.tsx` | Pass `quantity_refunded_total` through; row reads "7 received of 10 ordered · 3 refunded"; a line is done when received + refunded = ordered. |
| `list_for_destination` R1 — voided POs in the stock page's incoming list | `InventoryManager.get_incoming_summary_for_factory` (BUG-717) | The manager leaves voided POs out. |
| HR-7 — `limit >= 1` | `GET /purchase-orders/` | 422 for `limit=0`. |

## Spec gaps
None. The six gaps of revision 1 are closed by the spec's Gap log (G1–G6, 2026-11-11): model module and status relationship named (LH-13, LD-10, GI-08), `_po_number_taken` patch for R6 (AL-29, AL-30), components hard-deleted (HF-24 redesigned, HF-61), real invoice void and real PO void columns (Conventions, OQ37-03).

## Retired IDs
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_purchase_order_is_fully_closed_clause` | R1 | HF-35, HF-36, HF-37, HF-38, OQ35-04, OQ36-03; misspellings deferred (BUG-1881) |
| | R2 (status joined) | HF-35, HF-59, PH-16 |
| `_apply_purchase_order_hub_filters` | R1 | HF-01, HF-02, HF-03, CH-05, CH-06, RH-09, PH-14, AS-03 |
| | R2 | HF-04 … HF-08, AS-05, PH-15 |
| | R3 | HF-09 … HF-12 |
| | R4 | HF-13, HF-14, HF-15, CH-01 |
| | R5 | HF-16 … HF-19 |
| | R6 | HF-20 … HF-29, HF-61 |
| | R7 | HF-30, HF-31, HF-59 |
| | R8 | HF-32, HF-33, HF-34 |
| | R9 [BUG-2640] | OQ37-01, OQ37-04, OQ37-06, OQ37-07 (pass); OQ37-02, OQ37-03, OQ37-05 (xfail) |
| | R10 | HF-35 … HF-38, CH-03, AS-04, RH-09, PH-14, PH-16 |
| | R11 [BUG-2633] | HF-39 … HF-50 (pass); HF-51 … HF-55 (xfail) |
| | R12 [BUG-2634] | HF-56 (xfail), HF-57 |
| | R13 | HF-11, HF-58, HF-59, CH-07, AS-06 |
| | R14 | HF-60 |
| `list_for_hub` | R1 | HF-01 … HF-61 (all through `list_for_hub`), LH-12, LH-13 |
| | R2 | LH-01 … LH-04 |
| | R3 | LH-05 … LH-10 |
| | Returns (status loaded) | LH-13 |
| | Side effects | LH-11 |
| `count_for_hub` | R1 | CH-01 … CH-07; OQ37-05 (xfail) |
| | Side effects | CH-08 |
| `list_recent_for_hub` | R1 [BUG-2635] | RH-02, RH-03, RH-06, RH-07, RH-08 (pass); RH-01, RH-04, RH-05 (xfail) |
| | R2 | RH-09 |
| | Side effects | RH-10 |
| `get_pending_highlights_for_hub` | R1 | PH-14, PH-15, PH-16 |
| | R2 [BUG-2635] | PH-01, PH-02 (pass); PH-03, PH-04 (xfail) |
| | R3 [BUG-2635] | PH-06, PH-07 (pass); PH-05 (xfail) |
| | R4 | PH-08, PH-09 |
| | R5 [BUG-2636] | PH-10, PH-11, PH-12 (xfail) |
| | R6 | PH-01, PH-06, PH-08 |
| | R7 | PH-13 |
| | Side effects | PH-17 |
| `aggregate_hub_stats` | R1 | AS-01, AS-03, AS-04, AS-05, AS-06, AS-10 |
| | R2 [BUG-2639] | AS-01, AS-03, AS-04 (pass, no voided PO); OQ35-01, OQ35-02, OQ35-04 (xfail) |
| | R3 (OQ-36, intended) | OQ36-01 … OQ36-06, OQ35-04 |
| | R3a [BUG-2639] | OQ35-01, OQ35-03 (xfail) |
| | R3b | AS-10 |
| | R4 | AS-01, AS-03, AS-06, AS-10 |
| | R5 | AS-02 |
| | R6 / HR-15 | AS-01, AS-07, AS-08 |
| | Side effects | AS-09 |
| `list_for_destination` | R1 | LD-01, LD-02, LD-06, LD-07 |
| | R2 | LD-03, LD-08 |
| | R3 | LD-04, LD-05, LD-06 |
| | Side effects | LD-09 |
| | R1 (status loaded) | LD-10 |
| `get_by_id_and_workspace` | R1 | GI-01, GI-02, GI-05 |
| | R2 | GI-03, GI-04, GI-06 |
| | R3 | GI-07 |
| | R1 (status loaded) | GI-08 |
| `get_by_invoice_id` | R1 | GV-01, GV-04, GV-06 |
| | R2 | GV-02, GV-03, GV-05 |
| | R3 [BUG-2637] | GV-06 (pass); GV-07, GV-08, GV-09 (xfail) |
| | R4 | GV-10, GV-11 |
| | Side effects | GV-12 |
| `allocate_po_number` | R1 [BUG-2632] | AL-01, AL-22 (pass); AL-23, AL-24 (xfail) |
| | R2 | AL-01 … AL-07, AL-11, AL-13, AL-14, AL-15, AL-16, AL-22 |
| | R3 | AL-04, AL-08, AL-09, AL-10, AL-12 |
| | R4 / Side effects | AL-25 |
| | R5 [BUG-2630] | AL-15, AL-16 (pass); AL-17, AL-18, AL-19 (xfail) |
| | R6 / Errors row 1 | AL-20, AL-21 (today's path, pass); AL-29, AL-30 (`_po_number_taken` patch, xfail BUG-2630) |
| | R7 [BUG-2631] | AL-27, AL-28 (model facts); race deferred |
| | Signature (keyword-only) | AL-26 |
| `PurchaseOrderItemDAO.get_by_order` | R1 | IO-01, IO-02, IO-05, IO-07, IO-08 |
| | R2 | IO-03, IO-04, IO-06 |
| `PurchaseOrderItemDAO.get_by_purchase_order_ids` | R1 | IP-01 |
| | R2 | IP-02, IP-03, IP-04 |
| | Side effects | IP-05 |
| `PurchaseOrderItemDAO.get_by_id_and_workspace` | R1 | IG-01 … IG-06 |
| `summarize_by_purchase_order_ids` | R1 | IS-01, IS-02, IS-03, OQ38-06, OQ38-10 |
| | R2 | OQ38-01 … OQ38-07 |
| | R2a [BUG-2641] | OQ38-08, OQ38-09, OQ38-10 (xfail) |
| | Side effects | IS-04 |
| `preview_names_by_purchase_order_ids` | R1 | IN-01, IN-02, IN-03, IN-04 |
| | R2 | IN-04 … IN-09 |
| | R3 [BUG-2638] | IN-04, IN-05 (pass); IN-10, IN-11, IN-12 (xfail) |
| | Side effects | IN-13 |
