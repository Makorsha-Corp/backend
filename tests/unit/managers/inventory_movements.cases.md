# Test cases — `app/managers/inventory_movements.py`

> **Spec:** `tests/unit/managers/inventory_movements.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — spec Gap log G1–G5 closed: `utcnow` patch target named (Time convention rewritten); BUG-664 tie rows now inserted in id order with the correct row LAST (SO-18, SI-15, MUC-05 re-set; Id reservation convention dropped) and the Q1 three-postings scenario added (SO-19 xfail, SO-20 pass); check order `qty → location_type → location → item → stock` added (PSO-19–23, PSI-16–18) and item-check-before-bucket-write made observable (SO-15, SO-16, SI-13, SI-14, MO-16, MI-13, MI-14 now flush before re-reading); inactive items accepted (SO-21, SI-16, MO-17, MI-15); free `String(50)` columns (SO-22, SO-23, MO-18, MO-19).
> **Revision:** 3 — no spec change since revision 2; full self-check re-run. Added the missing `item_name` R4 Coverage-matrix row (statement of fact, no case possible). Aligned the dest_id/source_loc_id convention with the spec (`transfer_destination_id` has no FK). No cases added, changed or retired.
> **Revision:** 4 — spec Gap log G6 (addresses verify.md finding 2, case designer part): today's tie result is plan-dependent (physically first OR highest TID), so the Tie insertion convention is rewritten to the spec's B → C (explicit id above the sequence) → A order, and SO-18, SI-15, MUC-05 are re-set so today's code returns a wrong row under either plan. SO-19 (Q1 three-postings example as a strict xfail) is retired: the spec now forbids it as a strict xfail because it is non-deterministic today. The Error-path flush convention now says plainly that a "(flush)" case does not wrap the call in `begin_nested()` (clarifies verify.md finding 3; fix itself is executor-side). Findings 1, 3, 4 and 5 are routed to the executor/verifier and need no case change.
> **Revision:** 5 — 2026-10-30, owner ruling BUG-1040 (all money rounds half up, HR-15); spec R2 split into R2 and R2a [BUG-1040]. WAP-04 now expects `0.03` as a strict xfail. WAP-05 keeps `0.04` and stays `pass`: 0.035 gives `0.04` under half up and half even alike, so a strict xfail would XPASS; it remains the half-down guard. No cases added or retired.
> **Counts:** 151 cases · 121 expected-to-pass · 30 expected-to-fail (bugs) · 2 deferred

## Reviewer summary
- **Per callable:** `item_name` 5 · `weighted_avg_price` 15 (1 bug) · `inventory_type_for_location` 6 · `_storage_out` 22 (5 bug) · `_storage_in` 16 (5 bug) · `ensure_machine_item` 7 · `get_machine_unit_cost` 5 (1 bug) · `_machine_out` 19 (4 bug) · `_machine_in` 15 (4 bug) · `post_stock_out` 23 (6 bug) · `post_stock_in` 18 (4 bug).
- **Notable design choices:**
  - Factory stock is always set up as a stock row plus one matching ledger row dated in the past (T0). R3a re-syncs stock from the ledger, so a stock row with no ledger row counts as empty. The past date also keeps setup rows from tying with the row the call writes (BUG-664).
  - The row-lock rules (BUG-660/661) are unit-tested by capturing the SQL the call runs and looking for `FOR UPDATE`, as `payment_transaction_manager` RR-08 does. The spec's "second connection with NOWAIT" idea cannot work here: setup rows are never committed, so another connection cannot see them. The real two-session race is Deferred to integration tests.
  - The BUG-664 tie cases (SO-18, SI-15, MUC-05) insert three rows with one timestamp in the order B, C, A, where C (the intended latest) gets an explicit id far above the sequence. Today's code may return the physically first tied row (B) or the highest-TID one (A), depending on the query plan; both are wrong, and only the fixed `performed_at DESC, id DESC` order returns C. So each strict xfail fails today under every plan (best-practice default, delegated by reviewer; spec G6).
  - The spec's real-world Q1 example (three stock-outs of 5 from 20 in one save) is not a case: today it ends at 10 or 5 depending on the plan, so it cannot be a strict xfail (SO-19 retired). Re-add it as a plain pass case once BUG-664 is fixed.
  - Where a 400/404 might leave a bucket row created, restored or re-synced, the test calls `flush()` itself before re-reading. That makes an in-memory change observable (best-practice default, delegated by reviewer).
  - Over-long strings (SO-23, MO-19) are expected to raise the database's `DataError`, as the spec states. They pin today's behavior and are not a bug.
  - Race simulations: none.
- **Needs a decision:** none.

## Conventions for this module

**ID prefixes:** `INVM` = inventory_movements. Methods: `IN` = `item_name`, `WAP` = `weighted_avg_price`, `ITL` = `inventory_type_for_location`, `SO` = `_storage_out`, `SI` = `_storage_in`, `EMI` = `ensure_machine_item`, `MUC` = `get_machine_unit_cost`, `MO` = `_machine_out`, `MI` = `_machine_in`, `PSO` = `post_stock_out`, `PSI` = `post_stock_in`. IDs below omit the `INVM-` prefix; the full ID is e.g. `INVM-SO-01`.

**Actors and rows:**
- W1, W2 = two workspaces. U1, U2 = two profiles. U1 is the acting user in every call unless stated; U2 is the "earlier" user stamped on setup rows.
- F1, F1b = two live factories in W1; F2 = a live factory in W2; F3 = a factory in W1 with `is_deleted = True`.
- M1, M1b = two live machines in W1; M2 = a live machine in W2; M3 = a machine in W1 with `is_deleted = True`.
- I1 = item "Bearing 6204" in W1, I2 = item "V-Belt A42" in W1, IX = item "Foreign Gasket" in W2, I_OFF = item "Old Pulley" in W1 with `is_active = False`.
- `NOID` = `999999999`, an id that exists in no table used here.
- T0 = `datetime(2025, 1, 1, 8, 0, 0)`, T1 = `datetime(2025, 2, 1, 8, 0, 0)`: past timestamps set explicitly on setup ledger rows (both earlier than the DB `now()` of the test transaction, and than NOW).

**Stock shorthands:**
- **S(F, I, TYPE, q, p)** = a factory stock bucket: one `inventory` row (workspace = F's workspace unless stated, factory F, item I, `inventory_type` TYPE, `qty = q`, `avg_price = p`, `is_deleted = False`, `is_active = True`, `created_by = updated_by = U2`) **plus** one matching `inventory_ledger` row for the same (workspace, TYPE, factory, item): `transaction_type "opening"`, `quantity q`, `qty_before 0`, `qty_after q`, `avg_price_before None`, `avg_price_after p`, `unit_cost p or 0`, `total_cost q×(p or 0)`, `source_type "manual"`, `source_id 1`, `performed_by U2`, `performed_at T0`. "Bucket B" = that inventory row.
- **MS(M, I, q, p)** = a machine stock: one `machine_items` row (workspace W1, machine M, item I, `qty = q`) **plus** one `machine_item_ledger` row for (W1, M, I): `transaction_type "opening"`, `quantity q`, `qty_before 0`, `qty_after q`, `avg_price_before 0`, `avg_price_after p`, `unit_cost p`, `total_cost q×p`, `value_before 0`, `value_after q×p`, `source_type "manual"`, `source_id 1`, `performed_by U2`, `performed_at T0`. "Row MI" = that machine_items row.
- "Setup ledger row" = the ledger row inserted by S/MS; "the new ledger row" = the one ledger row for that key whose id is not a setup row's id. "Ledger count" = number of ledger rows for that bucket/machine-item key, re-read from the DB.
- "No events" = zero `machine_activity_events` rows in W1 and W2, re-read.

**Default call arguments** (the case states only what differs):
- `_storage_out`: `inventory_type=STORAGE`, `transaction_type="consumption"`, `source_type="work_order"`, `source_id=17`, `notes="WO-17 line 1"`, `workspace_id=W1`, `user_id=U1`, `dest_type=None`, `dest_id=None`.
- `_storage_in`: `inventory_type=STORAGE`, `transaction_type="transfer_in"`, `source_type="transfer_order"`, `source_id=31`, `notes="TO-31"`, `workspace_id=W1`, `user_id=U1`, `source_loc_type=None`, `source_loc_id=None`.
- `_machine_out`: `transaction_type="consumption"`, `source_type="work_order"`, `source_id=17`, `notes="WO-17 line 1"`, `workspace_id=W1`, `user_id=U1`, `dest_type=None`, `dest_id=None`, `activity_event_type="consumption"`, `activity_description=None`.
- `_machine_in`: `transaction_type="transfer_in"`, `source_type="transfer_order"`, `source_id=31`, `notes="TO-31"`, `workspace_id=W1`, `user_id=U1`, `source_loc_type=None`, `source_loc_id=None`, `activity_event_type="transfer_in"`, `activity_description=None`.
- `post_stock_out`: as `_machine_out`, with `activity_event_type` / `activity_description` left at their defaults (None) unless stated.
- `post_stock_in`: as `_machine_in`, with `unit_cost` given per case and `activity_event_type` / `activity_description` left at None unless stated.
- `dest_id` / `source_loc_id`, when set, use real ids (F1b.id, M1.id). The spec says `transfer_destination_id` is a plain integer with no FK; real ids keep the values meaningful anyway (best-practice default, delegated by reviewer).

**Time:** every test freezes **NOW = `datetime(2026, 9, 27, 12, 0, 0)`** at the patch target the spec's Notes give: `patch.object(MachineItemLedger.__table__.c.performed_at.default, "arg", lambda ctx: NOW)` and `patch.object(MachineActivityEvent.__table__.c.created_at.default, "arg", lambda ctx: NOW)` (the spec's alternative, patching `app.utils.time.datetime`, is equally acceptable). Do NOT patch `app.managers.inventory_movements.utcnow` (it does not exist). Machine ledger `performed_at` and event `created_at` are asserted `== NOW`. Factory ledger `performed_at` is DB `now()` and cannot be frozen: asserted as "not None and > T1", and equal across all rows written by the action.

**Numbers:** all money values are compared as `Decimal` after re-reading (Postgres returns 2 decimals). "returns 5.00" means `== Decimal("5.00")` and `isinstance(result, Decimal)`.

**Errors:** "400 D" / "404 D" = raises `HTTPException` with that `status_code` and exact `detail` D. Cases that expect a database `IntegrityError`, and every xfail case whose today-behavior is an `IntegrityError`, run the action inside `db.begin_nested()` so the session stays usable for the re-reads.

**Error-path flush:** in a case marked "(flush)", the test calls `db.flush()` after catching the exception and before re-reading, so the bucket create/restore/sync that the spec says may already have happened is visible (best-practice default, delegated by reviewer). A "(flush)" case does NOT wrap the call in `db.begin_nested()`: a savepoint rollback would discard exactly the rows the re-read must look for. Only cases whose When says "inside `begin_nested()`" use a savepoint.

**SQL capture:** a SQLAlchemy `before_cursor_execute` listener on the test connection records every statement run during the action only (not the setup). "Locks inventory" = at least one captured statement is a SELECT from `inventory` containing `FOR UPDATE`; "locks machine_items" likewise for `machine_items`.

**Tie insertion (BUG-664 tie cases only; spec Notes / G6, best-practice default, delegated by reviewer):** the three tied ledger rows share one `performed_at` and are inserted one after another, each flushed, in this exact order:
1. row **B** (wrong values) with a database-assigned id;
2. row **C** (the intended "latest", distinct values) with an **explicit id** = `nextval(pg_get_serial_sequence('<ledger table>', 'id')) + 1000000`, read from the database just before the insert;
3. row **A** (wrong values) with a database-assigned id, so id(B) < id(A) < id(C).
Today the tie result depends on the plan: physically first-inserted gives B, a backward index scan (highest TID) gives A. Only the intended `ORDER BY performed_at DESC, id DESC` gives C. Never insert C first or last, and never leave C's id to the sequence. Each tie case's "fails today on" names both possible wrong rows.

**Long strings:** `S50` = `"x" * 50`, `S51` = `"x" * 51`. A `DataError` case runs the action inside `db.begin_nested()`, then issues `db.flush()` inside the same block if the call itself returned; it expects `sqlalchemy.exc.DataError` from either point.

**Race simulations:** none.

## `item_name`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| IN-01 | R1 | happy | I1 | `item_name(db, I1.id, W1.id)` | returns `"Bearing 6204"` | pass |
| IN-02 | R2 | boundary | no item with id NOID | `item_name(db, NOID, W1.id)` | returns `"Item #999999999"`; no exception | pass |
| IN-03 | R2 | isolation | IX (in W2) | `item_name(db, IX.id, W1.id)` | returns `f"Item #{IX.id}"` | pass |
| IN-04 | R1 | isolation | IX (in W2) | `item_name(db, IX.id, W2.id)` | returns `"Foreign Gasket"` | pass |
| IN-05 | R3 | boundary | I_OFF (`is_active = False`) | `item_name(db, I_OFF.id, W1.id)` | returns `"Old Pulley"` | pass |

## `weighted_avg_price`

All values are `Decimal` unless shown as int. Every case asserts `isinstance(result, Decimal)` too.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| WAP-01 | R2 | happy | — | `(10, Decimal("5.00"), 10, Decimal("7.00"))` | returns `Decimal("6.00")` | pass |
| WAP-02 | R2 | happy | — | `(1, Decimal("1.00"), 2, Decimal("1.00"))` | returns `Decimal("1.00")` | pass |
| WAP-03 | R2 | boundary | — | `(2, Decimal("1.00"), 1, Decimal("2.00"))` | returns `Decimal("1.33")`, `str(result) == "1.33"` (rounded to 2 dp) | pass |
| WAP-04 | R2a [BUG-1040] | bug | — | `(1, Decimal("0.01"), 1, Decimal("0.04"))` (exact 0.025) | returns `Decimal("0.03")` (half away from zero) | xfail BUG-1040 — fails today on: returns `Decimal("0.02")` (half to even), not `0.03` |
| WAP-05 | R2a | boundary | — | `(1, Decimal("0.01"), 1, Decimal("0.06"))` (exact 0.035) | returns `Decimal("0.04")` (half away from zero; half down would give 0.03; holds today too, half even also gives 0.04) | pass |
| WAP-06 | R1 | boundary | — | `(10, Decimal("5.00"), 0, Decimal("9.00"))` | returns `Decimal("5.00")` | pass |
| WAP-07 | R1 | boundary | — | `(10, Decimal("5.00"), -3, Decimal("9.00"))` | returns `Decimal("5.00")` | pass |
| WAP-08 | R1 | boundary | — | `(10, None, 0, Decimal("9.00"))` | returns `Decimal(0)` (not None) | pass |
| WAP-09 | R1 | boundary | — | `(10, Decimal("0"), 0, Decimal("9.00"))` | returns `Decimal(0)` | pass |
| WAP-10 | R1, R2 | boundary | — | `(10, Decimal("5.00"), 1, Decimal("16.00"))` (add_qty = 1, other side of R1) | returns `Decimal("6.00")` | pass |
| WAP-11 | R3 | happy | — | `(0, Decimal("5.00"), 4, Decimal("3.337"))` | returns `Decimal("3.337")`, `str(result) == "3.337"` (not rounded, old avg ignored) | pass |
| WAP-12 | R3 | boundary | — | `(-2, Decimal("5.00"), 3, Decimal("4.00"))` | returns `Decimal("4.00")` (not the weighted 0.67) | pass |
| WAP-13 | R2, R3 | boundary | — | `(1, Decimal("5.00"), 1, Decimal("7.00"))` (old_qty = 1, other side of R3) | returns `Decimal("6.00")` | pass |
| WAP-14 | R4 | happy | — | `(5, None, 5, Decimal("2.345"))` | returns `Decimal("2.345")`, `str(result) == "2.345"` (not rounded; existing units ignored) | pass |
| WAP-15 | R5 | boundary | — | `(10, Decimal("0"), 10, Decimal("4.00"))` | returns `Decimal("2.00")` (R2, not R4's 4.00) | pass |

## `inventory_type_for_location`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| ITL-01 | R1 | happy | — | `"damaged"` | returns `InventoryTypeEnum.DAMAGED` | pass |
| ITL-02 | R2 | happy | — | `"storage"` | returns `InventoryTypeEnum.STORAGE` | pass |
| ITL-03 | R2 | boundary | — | `"machine"` | returns `InventoryTypeEnum.STORAGE` | pass |
| ITL-04 | R2 | boundary | — | `"Damaged"` | returns `InventoryTypeEnum.STORAGE` (case-sensitive) | pass |
| ITL-05 | R2 | boundary | — | `""` | returns `InventoryTypeEnum.STORAGE` | pass |
| ITL-06 | R2 | boundary | — | `"damaged "` (trailing space) | returns `InventoryTypeEnum.STORAGE` | pass |

## `_storage_out`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SO-01 | R7, R8, R3 | happy | S(F1, I1, STORAGE, 10, 5.00) | `factory_id=F1`, `item_id=I1`, `qty=4`, `dest_type="machine"`, `dest_id=M1.id` | returns `Decimal("5.00")`; re-read bucket B (same id): `qty == 6`, `avg_price == 5.00`, `updated_by == U1`, `created_by == U2`, `is_deleted False`; exactly 1 `inventory` row for (W1, F1, I1, STORAGE); ledger count 2; the new ledger row: `workspace_id W1`, `inventory_type STORAGE`, `factory_id F1`, `item_id I1`, `transaction_type "consumption"`, `quantity 4`, `unit_cost 5.00`, `total_cost 20.00`, `qty_before 10`, `qty_after 6`, `avg_price_before 5.00`, `avg_price_after 5.00`, `source_type "work_order"`, `source_id 17`, `transfer_destination_type "machine"`, `transfer_destination_id M1.id`, `transfer_source_type None`, `transfer_source_id None`, `notes "WO-17 line 1"`, `performed_by U1`, `performed_at` not None and > T1; no events | pass |
| SO-02 | R6 | boundary | S(F1, I1, STORAGE, 5, 5.00) | `qty=5` | returns `Decimal("5.00")`; bucket `qty == 0`; new ledger row `qty_before 5`, `qty_after 0`, `total_cost 25.00` | pass |
| SO-03 | R5, R3a; Errors row 3 | error | S(F1, I1, STORAGE, 5, 5.00) | `qty=6` (flush) | 400 `Insufficient stock (5 available, 6 requested)`; ledger count 1; bucket `qty == 5`, `avg_price == 5.00`, `updated_by == U2` (sync found nothing to change, so no stamp) | pass |
| SO-04 | R5, R3a | error | bucket B for (W1, F1, I1, STORAGE) with `qty 10`, `avg_price 5.00`, `updated_by U2`; its only ledger row has `qty_after 3`, `avg_price_after 4.00` (performed_at T0) | `qty=5` (flush) | 400 `Insufficient stock (3 available, 5 requested)` (the ledger figure, not 10); ledger count 1; bucket `qty == 3`, `avg_price == 4.00`, `updated_by == U1` | pass |
| SO-05 | R3a, R7, R8 | side-effect | bucket B `qty 10`, `avg_price 5.00`; its only ledger row `qty_after 8`, `avg_price_after 6.00` (T0) | `qty=2` | returns `Decimal("6.00")`; bucket `qty == 6`, `avg_price == 6.00`, `updated_by == U1`; new ledger row `qty_before 8`, `qty_after 6`, `unit_cost 6.00`, `total_cost 12.00`, `avg_price_before 6.00`, `avg_price_after 6.00` | pass |
| SO-06 | R3a, R5 | boundary | bucket B `qty 10`, `avg_price 5.00`, `updated_by U2`; **no** ledger rows for the bucket | `qty=1` (flush) | 400 `Insufficient stock (0 available, 1 requested)`; ledger count 0; bucket `qty == 0`, `avg_price is None`, `updated_by == U1` | pass |
| SO-07 | R3, R5 | side-effect | no `inventory` row and no ledger rows for (W1, F1, I1, STORAGE) | `qty=1` (flush) | 400 `Insufficient stock (0 available, 1 requested)`; ledger count 0; exactly 1 `inventory` row for (W1, F1, I1, STORAGE): `qty == 0`, `avg_price is None`, `created_by == U1` | pass |
| SO-08 | R3, R3a, R8 | side-effect | no `inventory` row for (W1, F1, I1, STORAGE); one ledger row for that bucket with `qty_after 7`, `avg_price_after 3.00` (T0) | `qty=2` | returns `Decimal("3.00")`; exactly 1 `inventory` row for the key: `qty == 5`, `avg_price == 3.00`, `created_by == U1`, `updated_by == U1`, `is_deleted False`; new ledger row `qty_before 7`, `qty_after 5` | pass |
| SO-09 | R3 | soft-delete | S(F1, I1, STORAGE, 4, 2.50) where bucket B is soft-deleted: `is_deleted True`, `is_active False`, `deleted_at T1`, `deleted_by U2` | `qty=1` | returns `Decimal("2.50")`; exactly 1 `inventory` row for the key, id == B.id; B: `is_deleted False`, `is_active True`, `deleted_at None`, `deleted_by None`, `qty == 3`; new ledger row `qty_before 4`, `qty_after 3` | pass |
| SO-10 | R3, R3a | isolation | S(F1, I1, DAMAGED, 10, 5.00); S(F1b, I1, STORAGE, 10, 5.00); S(F1, I2, STORAGE, 10, 5.00); and an `inventory` row + matching ledger row with workspace **W2**, factory F1, item I1, STORAGE, qty 10 (T0) | `factory_id=F1`, `item_id=I1`, STORAGE, `qty=1` | 400 `Insufficient stock (0 available, 1 requested)`; each of the four other buckets re-read: `qty == 10`, ledger count 1 | pass |
| SO-11 | R1; Errors row 1 | error | S(F1, I1, STORAGE, 10, 5.00) | `factory_id=NOID`, `item_id=I1`, `qty=1` | 404 `Factory with ID 999999999 not found`; no `inventory` or `inventory_ledger` row with `factory_id` NOID; bucket B `qty == 10`, ledger count 1 | pass |
| SO-12 | R1; Errors row 1 | isolation | F2 in W2; no rows for (W1, F2, I1) | `factory_id=F2`, `item_id=I1`, `qty=1` | 404 `Factory with ID {F2.id} not found`; no `inventory` or `inventory_ledger` row with `factory_id` F2 | pass |
| SO-13 | R2 [BUG-662]; Errors row 1 | bug | S(F3, I1, STORAGE, 10, 5.00) (F3 soft-deleted) | `factory_id=F3`, `item_id=I1`, `qty=1` | 404 `Factory with ID {F3.id} not found`; bucket `qty == 10`; ledger count 1 | xfail BUG-662 — fails today on: no exception raised (movement posted) |
| SO-14 | R4 [BUG-660] | bug | S(F1, I1, STORAGE, 10, 5.00); SQL capture on | `qty=1` | returns `Decimal("5.00")`; captured SQL locks inventory; bucket `qty == 9` | xfail BUG-660 — fails today on: no captured SELECT on `inventory` contains `FOR UPDATE` |
| SO-15 | R9 [BUG-666]; Errors row 2 | bug | an `inventory` row (W1, F1, **IX**, STORAGE) `qty 7`, `avg_price 5.00`, `updated_by U2` + one ledger row for that bucket `qty_after 10`, `avg_price_after 5.00` (T0) — stock and ledger disagree, so a sync would change the row | `factory_id=F1`, `item_id=IX`, `qty=2` (flush) | 404 `Item with ID {IX.id} not found`; that bucket `qty == 7`, `updated_by == U2` (item check ran before the sync); its ledger count 1 | xfail BUG-666 — fails today on: no exception raised (foreign item accepted) |
| SO-16 | R9 [BUG-666]; Errors row 2 | bug | no rows for item NOID | inside `begin_nested()`: `factory_id=F1`, `item_id=NOID`, `qty=1`; on 404, `db.flush()` inside the same block | 404 `Item with ID 999999999 not found`; the flush raises nothing; no `inventory` / `inventory_ledger` row with `item_id` NOID (item check ran before bucket create) | xfail BUG-666 — fails today on: raises `IntegrityError` (or 400) instead of 404 |
| SO-17 | R7, R8 | boundary | S(F1, I1, STORAGE, 5, None) (bucket and ledger `avg_price(_after) None`, ledger `unit_cost 0`) | `qty=2` | returns `Decimal(0)`; new ledger row `unit_cost 0`, `total_cost 0`, `avg_price_before None`, `avg_price_after None`, `qty_after 3`; bucket `qty == 3`, `avg_price is None` | pass |
| SO-18 | R3a [BUG-664] | bug | an `inventory` row (W1, F1, I1, STORAGE) `qty 10`, `avg_price 5.00`, `updated_by U2`; three ledger rows for that bucket, all `performed_at T0`, inserted per Tie insertion: row B (`qty_after 12`, `avg_price_after 4.50`), then row C with the explicit high id (`qty_after 10`, `avg_price_after 5.00`), then row A (`qty_after 15`, `avg_price_after 4.00`) | `qty=5` | returns `Decimal("5.00")`; bucket `qty == 5`, `avg_price == 5.00`; new ledger row `qty_before 10`, `qty_after 5`, `unit_cost 5.00` | xfail BUG-664 — fails today on: bucket synced from row B (returns 4.50, `qty_before 12`, bucket `qty == 7`) or from row A (returns 4.00, `qty_before 15`, bucket `qty == 10`), depending on the plan |
| SO-20 | R3a, R8 | side-effect | S(F1, I1, STORAGE, 20, 5.00) | two calls in the same transaction, each `qty=5` (only the second has one same-transaction row to sync from — no tie) | each returns `Decimal("5.00")`; bucket `qty == 10`; ledger count 3; the two new ledger rows in id order: `qty_before` 20, 15; `qty_after` 15, 10; both `performed_at` equal, not None and > T1 | pass |
| SO-21 | R9 (inactive item accepted) | boundary | S(F1, I_OFF, STORAGE, 5, 2.00) (I_OFF `is_active = False`) | `factory_id=F1`, `item_id=I_OFF`, `qty=2` | returns `Decimal("2.00")`; no exception; bucket `qty == 3`; new ledger row `item_id I_OFF`, `qty_before 5`, `qty_after 3` | pass |
| SO-22 | Inputs (free `String(50)`) | boundary | S(F1, I1, STORAGE, 10, 5.00) | `qty=1`, `transaction_type=S50`, `source_type=S50`, `dest_type=S50`, `dest_id=M1.id` | returns `Decimal("5.00")`; new ledger row `transaction_type == S50`, `source_type == S50`, `transfer_destination_type == S50`; bucket `qty == 9` | pass |
| SO-23 | Inputs (over-long value → `DataError`) | error | S(F1, I1, STORAGE, 10, 5.00) | per Long strings: `qty=1`, `transaction_type=S51` | raises `sqlalchemy.exc.DataError`; after the savepoint rollback: ledger count 1, no ledger row with `transaction_type` S51; bucket `qty == 10` | pass |

## `_storage_in`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SI-01 | R5, R6, R7 | happy | S(F1, I1, STORAGE, 10, 5.00) | `factory_id=F1`, `item_id=I1`, `qty=10`, `unit_cost=Decimal("7.00")`, `source_loc_type="factory"`, `source_loc_id=F1b.id` | returns `None`; bucket B (same id): `qty == 20`, `avg_price == 6.00`, `updated_by == U1`; exactly 1 `inventory` row for the key; ledger count 2; new ledger row: `workspace_id W1`, `inventory_type STORAGE`, `factory_id F1`, `item_id I1`, `transaction_type "transfer_in"`, `quantity 10`, `unit_cost 7.00`, `total_cost 70.00`, `qty_before 10`, `qty_after 20`, `avg_price_before 5.00`, `avg_price_after 6.00`, `source_type "transfer_order"`, `source_id 31`, `transfer_source_type "factory"`, `transfer_source_id F1b.id`, `transfer_destination_type None`, `transfer_destination_id None`, `notes "TO-31"`, `performed_by U1`, `performed_at` not None and > T1; no events | pass |
| SI-02 | R3, R5, R6, R7 | side-effect | no `inventory` row and no ledger rows for (W1, F1, I1, STORAGE) | `qty=4`, `unit_cost=Decimal("3.50")` | returns `None`; exactly 1 `inventory` row for the key: `qty == 4`, `avg_price == 3.50`, `created_by == U1`, `updated_by == U1`, `is_deleted False`; ledger count 1: `qty_before 0`, `qty_after 4`, `avg_price_before None`, `avg_price_after 3.50`, `unit_cost 3.50`, `total_cost 14.00` | pass |
| SI-03 | R3, R5 | soft-delete | S(F1, I1, STORAGE, 2, 1.00) with bucket B soft-deleted (`is_deleted True`, `is_active False`, `deleted_at T1`, `deleted_by U2`) | `qty=1`, `unit_cost=Decimal("2.00")` | returns `None`; exactly 1 `inventory` row for the key, id == B.id: `is_deleted False`, `is_active True`, `deleted_at None`, `deleted_by None`, `qty == 3`, `avg_price == 1.33`; new ledger row `avg_price_before 1.00`, `avg_price_after 1.33`, `qty_before 2`, `qty_after 3` | pass |
| SI-04 | R3 (sync), R5 | side-effect | bucket B `qty 10`, `avg_price 5.00`; its only ledger row `qty_after 0`, `avg_price_after 5.00` (T0) | `qty=2`, `unit_cost=Decimal("8.00")` | returns `None`; bucket `qty == 2`, `avg_price == 8.00` (synced qty 0 → unit cost wins); new ledger row `qty_before 0`, `qty_after 2`, `avg_price_before 5.00`, `avg_price_after 8.00` | pass |
| SI-05 | R3 (sync), R5 | boundary | bucket B `qty 6`, `avg_price 3.00`; **no** ledger rows for the bucket | `qty=2`, `unit_cost=Decimal("4.00")` | returns `None`; bucket `qty == 2`, `avg_price == 4.00`; ledger count 1: `qty_before 0`, `qty_after 2`, `avg_price_before None`, `avg_price_after 4.00` | pass |
| SI-06 | R4 | boundary | no rows for (W1, F1, I1, STORAGE) | `qty=100000`, `unit_cost=Decimal("1.00")` | returns `None`; no exception; bucket `qty == 100000`; new ledger row `qty_after 100000`, `total_cost 100000.00` | pass |
| SI-07 | R5, R6 (Inputs: negative unit_cost accepted) | boundary | no rows for (W1, F1, I1, STORAGE) | `qty=2`, `unit_cost=Decimal("-1.00")` | returns `None`; bucket `qty == 2`, `avg_price == -1.00`; ledger row `unit_cost -1.00`, `total_cost -2.00` | pass |
| SI-08 | R3 | isolation | S(F1, I1, DAMAGED, 10, 9.00) | STORAGE, `qty=5`, `unit_cost=Decimal("1.00")` | returns `None`; new STORAGE bucket for (W1, F1, I1): `qty == 5`, `avg_price == 1.00`; DAMAGED bucket `qty == 10`, `avg_price == 9.00`, its ledger count 1 | pass |
| SI-09 | R1; Errors row 1 | error | — | `factory_id=NOID`, `item_id=I1`, `qty=1`, `unit_cost=Decimal("1.00")` | 404 `Factory with ID 999999999 not found`; no `inventory` / `inventory_ledger` row with `factory_id` NOID | pass |
| SI-10 | R1; Errors row 1 | isolation | F2 in W2 | `factory_id=F2`, `item_id=I1`, `qty=1`, `unit_cost=Decimal("1.00")` | 404 `Factory with ID {F2.id} not found`; no `inventory` / `inventory_ledger` row with `factory_id` F2 | pass |
| SI-11 | R2 [BUG-662]; Errors row 1 | bug | F3 (soft-deleted); no rows for (W1, F3, I1) | `factory_id=F3`, `item_id=I1`, `qty=1`, `unit_cost=Decimal("1.00")` | 404 `Factory with ID {F3.id} not found`; no `inventory` / `inventory_ledger` row with `factory_id` F3 | xfail BUG-662 — fails today on: no exception raised (stock posted) |
| SI-12 | R3 [BUG-660] | bug | S(F1, I1, STORAGE, 10, 5.00); SQL capture on | `qty=1`, `unit_cost=Decimal("5.00")` | returns `None`; captured SQL locks inventory; bucket `qty == 11` | xfail BUG-660 — fails today on: no captured SELECT on `inventory` contains `FOR UPDATE` |
| SI-13 | R8 [BUG-666]; Errors row 2 | bug | no rows for (W1, F1, IX) | `factory_id=F1`, `item_id=IX`, `qty=3`, `unit_cost=Decimal("2.00")` (flush) | 404 `Item with ID {IX.id} not found`; no `inventory` / `inventory_ledger` row with `item_id` IX (item check ran before bucket create) | xfail BUG-666 — fails today on: no exception raised (foreign item stocked) |
| SI-14 | R8 [BUG-666]; Errors row 2 | bug | — | inside `begin_nested()`: `factory_id=F1`, `item_id=NOID`, `qty=1`, `unit_cost=Decimal("1.00")`; on 404, `db.flush()` inside the same block | 404 `Item with ID 999999999 not found`; the flush raises nothing; no `inventory` / `inventory_ledger` row with `item_id` NOID | xfail BUG-666 — fails today on: raises `IntegrityError` instead of 404 |
| SI-15 | R3 (sync) [BUG-664] | bug | an `inventory` row (W1, F1, I1, STORAGE) `qty 10`, `avg_price 5.00`; three tied ledger rows for that bucket at T0 per Tie insertion: row B (`qty_after 12`, `avg_price_after 4.50`), then row C with the explicit high id (`10`, `5.00`), then row A (`15`, `4.00`) | `qty=10`, `unit_cost=Decimal("7.00")` | returns `None`; bucket `qty == 20`, `avg_price == 6.00`; new ledger row `qty_before 10`, `avg_price_before 5.00`, `avg_price_after 6.00` | xfail BUG-664 — fails today on: synced from row B (`qty_before 12`, `avg_price_before 4.50`, bucket `qty == 22`) or from row A (`qty_before 15`, `avg_price_before 4.00`, bucket `qty == 25`), depending on the plan |
| SI-16 | R8 (inactive item accepted) | boundary | no rows for (W1, F1, I_OFF) | `factory_id=F1`, `item_id=I_OFF`, `qty=3`, `unit_cost=Decimal("2.00")` | returns `None`; no exception; STORAGE bucket for (W1, F1, I_OFF): `qty == 3`, `avg_price == 2.00`; ledger count 1, `item_id I_OFF` | pass |

## `ensure_machine_item`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EMI-01 | R1 | happy | `machine_items` row R (W1, M1, I1) `qty 7`, `req_qty 3`, `defective_qty 1` | `machine_id=M1`, `item_id=I1`, `workspace_id=W1` | returns an object with `id == R.id`; re-read R: `qty 7`, `req_qty 3`, `defective_qty 1`; exactly 1 `machine_items` row for (W1, M1, I1) | pass |
| EMI-02 | R1, R2 | isolation | `machine_items` rows (W1, M1b, I1) qty 5, (W1, M1, I2) qty 5, (W2, M1, I1) qty 5 | `machine_id=M1`, `item_id=I1`, `workspace_id=W1` | returns a row whose id is none of the three; re-read by that id: `workspace_id W1`, `machine_id M1`, `item_id I1`, `qty 0`; the three other rows still `qty 5`; exactly 1 row for (W1, M1, I1) | pass |
| EMI-03 | R2 | happy | no `machine_items` rows | `machine_id=M1`, `item_id=I1`, `workspace_id=W1` | returns a row with `id` not None (flushed); re-read by id: `workspace_id W1`, `machine_id M1`, `item_id I1`, `qty 0`, `req_qty None`, `defective_qty None` | pass |
| EMI-04 | R3 | boundary | M2 (in W2); no rows | `machine_id=M2`, `item_id=I1`, `workspace_id=W1` | no exception; returns a row with id; re-read: `workspace_id W1`, `machine_id M2`, `item_id I1`, `qty 0` | pass |
| EMI-05 | R3; Errors | error | — | inside `begin_nested()`: `machine_id=NOID`, `item_id=I1`, `workspace_id=W1` | raises `IntegrityError`; after the savepoint rollback no `machine_items` row with `machine_id` NOID | pass |
| EMI-06 | R3; Errors | error | — | inside `begin_nested()`: `machine_id=M1`, `item_id=NOID`, `workspace_id=W1` | raises `IntegrityError`; no `machine_items` row with `item_id` NOID | pass |
| EMI-07 | R4 | boundary | two `machine_items` rows for (W1, M1, I1): R_a qty 2, R_b qty 3 | `machine_id=M1`, `item_id=I1`, `workspace_id=W1` | returned `id in {R_a.id, R_b.id}`; still exactly 2 rows for the key; R_a `qty 2`, R_b `qty 3` | pass |

## `get_machine_unit_cost`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| MUC-01 | R1 | happy | two `machine_item_ledger` rows for (W1, M1, I1), inserted in this order: A `performed_at T1`, `avg_price_after 12.00`; B `performed_at T0`, `avg_price_after 9.00` (B has the higher id but is older) | `machine_id=M1`, `item_id=I1`, `workspace_id=W1` | returns `Decimal("12.00")` (`isinstance Decimal`) | pass |
| MUC-02 | R2 | boundary | no ledger rows | same | returns `Decimal(0)` (`isinstance Decimal`, not None) | pass |
| MUC-03 | R2 | isolation | ledger rows with `avg_price_after 8.00` (T0) for (W2, M1, I1), (W1, M1b, I1) and (W1, M1, I2) | same | returns `Decimal(0)` | pass |
| MUC-04 | R3 | boundary | ledger rows for (W1, M1, I1): newest `performed_at T1`, `avg_price_after None`; older `performed_at T0`, `avg_price_after 7.00` | same | returns `Decimal(0)` (older row not consulted) | pass |
| MUC-05 | R1 [BUG-664] | bug | three tied `machine_item_ledger` rows for (W1, M1, I1) at T0 per Tie insertion: row B (`avg_price_after 4.00`), then row C with the explicit high id (`10.00`), then row A (`3.00`) | same | returns `Decimal("10.00")` | xfail BUG-664 — fails today on: returns 4.00 (row B) or 3.00 (row A), depending on the plan |

## `_machine_out`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| MO-01 | R3, R6–R9 | happy | MS(M1, I1, 10, 4.00) | `machine_id=M1`, `item_id=I1`, `qty=3`, `dest_type="factory"`, `dest_id=F1.id` | returns `Decimal("4.00")`; row MI (same id) `qty == 7`; exactly 1 `machine_items` row for (W1, M1, I1); ledger count 2; new ledger row: `workspace_id W1`, `machine_id M1`, `item_id I1`, `transaction_type "consumption"`, `quantity 3`, `unit_cost 4.00`, `total_cost 12.00`, `qty_before 10`, `qty_after 7`, `value_before 40.00`, `value_after 28.00`, `avg_price_before 4.00`, `avg_price_after 4.00`, `source_type "work_order"`, `source_id 17`, `transfer_destination_type "factory"`, `transfer_destination_id F1.id`, `transfer_source_type None`, `transfer_source_id None`, `order_type None`, `order_id None`, `invoice_id None`, `notes "WO-17 line 1"`, `performed_by U1`, `performed_at == NOW`; exactly 1 activity event for M1: `workspace_id W1`, `event_type "consumption"`, `performed_by U1`, `created_at == NOW`, `description "consumption: 3 units of Bearing 6204"`, metadata `== {"item_id": I1.id, "item_name": "Bearing 6204", "quantity": 3, "work_order_id": 17}` | pass |
| MO-02 | R6 | boundary | MS(M1, I1, 5, 4.00) | `qty=5` | returns `Decimal("4.00")`; row MI `qty == 0`; new ledger row `qty_before 5`, `qty_after 0`, `value_after 0.00`; 1 event | pass |
| MO-03 | R5; Errors row 3 | error | MS(M1, I1, 5, 4.00) | `qty=6` | 400 `Insufficient machine stock (5 available, 6 requested)`; row MI `qty == 5`; ledger count 1; no events | pass |
| MO-04 | R3, R5 | error | no `machine_items` row and no ledger for (W1, M1, I1) | `qty=1` | 400 `Insufficient machine stock (0 available, 1 requested)`; no `machine_item_ledger` rows for (W1, M1, I1); no events | pass |
| MO-05 | R3 | side-effect | row MI (W1, M1, I1) `qty 10`; its only ledger row `qty_after 2`, `avg_price_after 4.00` (T0) | `qty=5` | returns `Decimal("4.00")` (no 400: machine qty is not re-synced from the ledger); row MI `qty == 5`; new ledger row `qty_before 10`, `qty_after 5` | pass |
| MO-06 | R7, R8 | boundary | row MI (W1, M1, I1) `qty 5`; no ledger rows | `qty=2` | returns `Decimal(0)`; row MI `qty == 3`; ledger count 1: `unit_cost 0`, `total_cost 0`, `value_before 0`, `value_after 0`, `avg_price_before 0`, `avg_price_after 0`, `qty_before 5`, `qty_after 3` | pass |
| MO-07 | R9 | side-effect | MS(M1, I1, 10, 4.00) | `qty=3`, `activity_description="Loaded for WO-17"` | returns `Decimal("4.00")`; exactly 1 event, `description "Loaded for WO-17"` | pass |
| MO-08 | R9 | boundary | MS(M1, I1, 10, 4.00) | `qty=3`, `activity_description=""` | returns `Decimal("4.00")`; exactly 1 event, `description "consumption: 3 units of Bearing 6204"` | pass |
| MO-09 | R9 | side-effect | MS(M1, I1, 10, 4.00) | `qty=3`, `source_type="transfer_order"`, `source_id=31` | returns `Decimal("4.00")`; exactly 1 event, metadata `== {"item_id": I1.id, "item_name": "Bearing 6204", "quantity": 3}` (no `work_order_id` key); new ledger row `source_type "transfer_order"`, `source_id 31` | pass |
| MO-10 | R9 | boundary | MS(M1, I1, 10, 4.00) | `qty=3`, `source_type="Work_Order"`, `source_id=17` | returns `Decimal("4.00")`; event metadata has no `work_order_id` key (case-sensitive) | pass |
| MO-11 | R1; Errors row 1 | error | MS(M1, I1, 10, 4.00) | `machine_id=NOID`, `qty=1` | 404 `Machine with ID 999999999 not found`; no `machine_items` / `machine_item_ledger` row with `machine_id` NOID; row MI `qty == 10`; no events | pass |
| MO-12 | R1; Errors row 1 | isolation | M2 (in W2); no rows | `machine_id=M2`, `qty=1` | 404 `Machine with ID {M2.id} not found`; no `machine_items` / `machine_item_ledger` row with `machine_id` M2; no events | pass |
| MO-13 | R2 [BUG-663]; Errors row 1 | bug | MS(M3, I1, 10, 4.00) (M3 soft-deleted) | `machine_id=M3`, `qty=1` | 404 `Machine with ID {M3.id} not found`; row MI `qty == 10`; ledger count 1; no events | xfail BUG-663 — fails today on: no exception raised |
| MO-14 | R4 [BUG-661] | bug | MS(M1, I1, 10, 4.00); SQL capture on | `qty=1` | returns `Decimal("4.00")`; captured SQL locks machine_items; row MI `qty == 9` | xfail BUG-661 — fails today on: no captured SELECT on `machine_items` contains `FOR UPDATE` |
| MO-15 | R10 [BUG-666]; Errors row 2 | bug | MS(M1, IX, 10, 4.00) (machine_items row W1 pointing at W2's item) | `item_id=IX`, `qty=2` | 404 `Item with ID {IX.id} not found`; that row `qty == 10`; ledger count 1; no events | xfail BUG-666 — fails today on: no exception raised (event names it `Item #<id>`) |
| MO-16 | R10 [BUG-666]; Errors row 2 | bug | — | inside `begin_nested()`: `item_id=NOID`, `qty=1`; on 404, `db.flush()` inside the same block | 404 `Item with ID 999999999 not found`; the flush raises nothing; no `machine_items` / `machine_item_ledger` row with `item_id` NOID (item check ran before machine-item create); no events | xfail BUG-666 — fails today on: raises `IntegrityError` instead of 404 |
| MO-17 | R10 (inactive item accepted), R9 | boundary | MS(M1, I_OFF, 5, 2.00) | `item_id=I_OFF`, `qty=2` | returns `Decimal("2.00")`; no exception; row MI `qty == 3`; new ledger row `item_id I_OFF`; exactly 1 event: `description "consumption: 2 units of Old Pulley"`, metadata `item_name "Old Pulley"` | pass |
| MO-18 | R9 (free `event_type` string), R8 | boundary | MS(M1, I1, 10, 4.00) | `qty=1`, `activity_event_type=S50`, `transaction_type=S50`, `source_type=S50` | returns `Decimal("4.00")`; exactly 1 event, `event_type == S50`; new ledger row `transaction_type == S50`, `source_type == S50`; row MI `qty == 9` | pass |
| MO-19 | R9 (over-long `event_type` → `DataError`) | error | MS(M1, I1, 10, 4.00) | per Long strings: `qty=1`, `activity_event_type=S51` | raises `sqlalchemy.exc.DataError`; after the savepoint rollback: row MI `qty == 10`; machine ledger count 1; no events | pass |

## `_machine_in`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| MI-01 | R3–R7 | happy | MS(M1, I1, 4, 10.00) | `machine_id=M1`, `item_id=I1`, `qty=4`, `unit_cost=Decimal("20.00")`, `source_loc_type="factory"`, `source_loc_id=F1.id` | returns `None`; row MI (same id) `qty == 8`; ledger count 2; new ledger row: `workspace_id W1`, `machine_id M1`, `item_id I1`, `transaction_type "transfer_in"`, `quantity 4`, `unit_cost 20.00`, `total_cost 80.00`, `qty_before 4`, `qty_after 8`, `value_before 40.00`, `value_after 120.00`, `avg_price_before 10.00`, `avg_price_after 15.00`, `source_type "transfer_order"`, `source_id 31`, `transfer_source_type "factory"`, `transfer_source_id F1.id`, `transfer_destination_type None`, `transfer_destination_id None`, `order_type None`, `order_id None`, `invoice_id None`, `notes "TO-31"`, `performed_by U1`, `performed_at == NOW`; exactly 1 event for M1: `workspace_id W1`, `event_type "transfer_in"`, `performed_by U1`, `created_at == NOW`, `description "transfer_in: 4 units of Bearing 6204"`, metadata `== {"item_id": I1.id, "item_name": "Bearing 6204", "quantity": 4}` | pass |
| MI-02 | R5 | boundary | row MI (W1, M1, I1) `qty 0`; its only ledger row `qty_after 0`, `avg_price_after 10.00` (T0) | `qty=2`, `unit_cost=Decimal("20.00")` | returns `None`; row MI `qty == 2`; new ledger row `avg_price_before 10.00`, `avg_price_after 20.00`, `value_before 0.00`, `value_after 40.00` | pass |
| MI-03 | R3, R5 | side-effect | no `machine_items` row, no ledger for (W1, M1, I1) | `qty=3`, `unit_cost=Decimal("2.50")` | returns `None`; exactly 1 `machine_items` row for (W1, M1, I1), `qty == 3`; ledger count 1: `qty_before 0`, `qty_after 3`, `avg_price_before 0`, `avg_price_after 2.50`, `value_before 0.00`, `value_after 7.50`; 1 event | pass |
| MI-04 | R8 | boundary | row MI (W1, M1, I1) `qty 5`; no ledger rows | `qty=5`, `unit_cost=Decimal("10.00")` | returns `None`; row MI `qty == 10`; ledger count 1: `avg_price_before 0`, `avg_price_after 5.00`, `value_before 0.00`, `value_after 50.00` | pass |
| MI-05 | R7 | side-effect | MS(M1, I1, 4, 10.00) | `qty=1`, `unit_cost=Decimal("10.00")`, `source_type="work_order"`, `source_id=17`, `activity_description="Returned from WO-17"` | returns `None`; exactly 1 event: `description "Returned from WO-17"`, metadata `== {"item_id": I1.id, "item_name": "Bearing 6204", "quantity": 1, "work_order_id": 17}` | pass |
| MI-06 | R7 | boundary | MS(M1, I1, 4, 10.00) | `qty=1`, `unit_cost=Decimal("10.00")`, `source_type="Work_Order"`, `source_id=17`, `activity_description=""` | returns `None`; exactly 1 event: `description "transfer_in: 1 units of Bearing 6204"`; metadata has no `work_order_id` key | pass |
| MI-07 | R5 | boundary | row MI (W1, M1, I1) `qty -2`; its only ledger row `qty_after -2`, `avg_price_after 10.00` (T0) | `qty=3`, `unit_cost=Decimal("20.00")` | returns `None`; row MI `qty == 1`; new ledger row `avg_price_after 20.00` | pass |
| MI-08 | R5 | boundary | MS(M1, I1, 1, 10.00) | `qty=1`, `unit_cost=Decimal("20.00")` | returns `None`; row MI `qty == 2`; new ledger row `avg_price_after 15.00` (qty_before 1 → weighted) | pass |
| MI-09 | R1; Errors row 1 | error | — | `machine_id=NOID`, `qty=1`, `unit_cost=Decimal("1.00")` | 404 `Machine with ID 999999999 not found`; no `machine_items` / `machine_item_ledger` row with `machine_id` NOID; no events | pass |
| MI-10 | R1; Errors row 1 | isolation | M2 (in W2) | `machine_id=M2`, `qty=1`, `unit_cost=Decimal("1.00")` | 404 `Machine with ID {M2.id} not found`; no `machine_items` / `machine_item_ledger` row with `machine_id` M2; no events | pass |
| MI-11 | R2 [BUG-663]; Errors row 1 | bug | M3 (soft-deleted); no rows | `machine_id=M3`, `qty=1`, `unit_cost=Decimal("1.00")` | 404 `Machine with ID {M3.id} not found`; no `machine_items` / `machine_item_ledger` row with `machine_id` M3; no events | xfail BUG-663 — fails today on: no exception raised |
| MI-12 | R3 [BUG-661] | bug | MS(M1, I1, 4, 10.00); SQL capture on | `qty=1`, `unit_cost=Decimal("10.00")` | returns `None`; captured SQL locks machine_items; row MI `qty == 5` | xfail BUG-661 — fails today on: no captured SELECT on `machine_items` contains `FOR UPDATE` |
| MI-13 | R9 [BUG-666]; Errors row 2 | bug | no rows for (W1, M1, IX) | `item_id=IX`, `qty=2`, `unit_cost=Decimal("1.00")` (flush) | 404 `Item with ID {IX.id} not found`; no `machine_items` / `machine_item_ledger` row with `item_id` IX (item check ran before machine-item create); no events | xfail BUG-666 — fails today on: no exception raised |
| MI-14 | R9 [BUG-666]; Errors row 2 | bug | — | inside `begin_nested()`: `item_id=NOID`, `qty=1`, `unit_cost=Decimal("1.00")`; on 404, `db.flush()` inside the same block | 404 `Item with ID 999999999 not found`; the flush raises nothing; no rows with `item_id` NOID; no events | xfail BUG-666 — fails today on: raises `IntegrityError` instead of 404 |
| MI-15 | R9 (inactive item accepted), R7 | boundary | no rows for (W1, M1, I_OFF) | `item_id=I_OFF`, `qty=2`, `unit_cost=Decimal("3.00")` | returns `None`; no exception; exactly 1 `machine_items` row for (W1, M1, I_OFF), `qty == 2`; ledger count 1, `avg_price_after 3.00`; exactly 1 event, `description "transfer_in: 2 units of Old Pulley"` | pass |

## `post_stock_out`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PSO-01 | R1, R3 (factory: no event) | happy | S(F1, I1, STORAGE, 10, 5.00) | `location_type="storage"`, `location_id=F1`, `item_id=I1`, `qty=3`, `activity_event_type="item_used"`, `activity_description="ignored"` (dest_type/dest_id omitted) | returns `Decimal("5.00")`; STORAGE bucket `qty == 7`; new ledger row `inventory_type STORAGE`, `quantity 3`, `transfer_destination_type None`, `transfer_destination_id None`; no events | pass |
| PSO-02 | R2 | happy | S(F1, I1, DAMAGED, 6, 2.00); S(F1, I1, STORAGE, 10, 5.00) | `"damaged"`, `location_id=F1`, `qty=2` | returns `Decimal("2.00")`; DAMAGED bucket `qty == 4`, its new ledger row `inventory_type DAMAGED`; STORAGE bucket `qty == 10`, ledger count 1; no events | pass |
| PSO-03 | R2 | isolation | S(F1, I1, STORAGE, 10, 5.00) only | `"damaged"`, `location_id=F1`, `qty=1` | 400 `Insufficient stock (0 available, 1 requested)`; STORAGE bucket `qty == 10`, ledger count 1; no DAMAGED ledger rows for (W1, F1, I1) | pass |
| PSO-04 | R2 | isolation | S(F1, I1, DAMAGED, 10, 5.00) only | `"storage"`, `location_id=F1`, `qty=1` | 400 `Insufficient stock (0 available, 1 requested)`; DAMAGED bucket `qty == 10`, ledger count 1; no STORAGE ledger rows for (W1, F1, I1) | pass |
| PSO-05 | R3 | happy | MS(M1, I1, 10, 4.00) | `"machine"`, `location_id=M1`, `qty=2`, `activity_event_type="item_used"`, `activity_description="Used on line 2"` | returns `Decimal("4.00")`; row MI `qty == 8`; new machine ledger row `quantity 2`; exactly 1 event for M1: `event_type "item_used"`, `description "Used on line 2"` | pass |
| PSO-06 | R3 | side-effect | MS(M1, I1, 10, 4.00) | `"machine"`, `location_id=M1`, `qty=2`, `activity_event_type=None` | returns `Decimal("4.00")`; exactly 1 event: `event_type "consumption"`, `description "consumption: 2 units of Bearing 6204"` | pass |
| PSO-07 | R3 | boundary | MS(M1, I1, 10, 4.00) | `"machine"`, `location_id=M1`, `qty=2`, `activity_event_type=""` | returns `Decimal("4.00")`; exactly 1 event, `event_type "consumption"` | pass |
| PSO-08 | R4; Errors row 2 | error | S(F1, I1, STORAGE, 10, 5.00); MS(M1, I1, 10, 4.00) | `"project"`, `location_id=F1`, `qty=1` | 400 `Unsupported source location type: project`; bucket `qty == 10`, ledger count 1; row MI `qty == 10`, machine ledger count 1; no events | pass |
| PSO-09 | R4; Errors row 2 | boundary | S(F1, I1, STORAGE, 10, 5.00) | `"Storage"`, `location_id=F1`, `qty=1` | 400 `Unsupported source location type: Storage`; bucket `qty == 10`, ledger count 1 | pass |
| PSO-10 | R4; Errors row 2 | boundary | S(F1, I1, STORAGE, 10, 5.00) | `""`, `location_id=F1`, `qty=1` | 400 `Unsupported source location type: ` (empty after the colon-space); bucket `qty == 10`, ledger count 1 | pass |
| PSO-11 | R5 [BUG-665]; Errors row 1 | bug | S(F1, I1, STORAGE, 10, 5.00) | `"storage"`, `location_id=F1`, `qty=0` | 400 `Quantity must be at least 1, got 0`; bucket `qty == 10`; ledger count 1 | xfail BUG-665 — fails today on: no exception raised (zero-quantity ledger row written) |
| PSO-12 | R5 [BUG-665]; Errors row 1 | bug | S(F1, I1, STORAGE, 10, 5.00) | `"storage"`, `location_id=F1`, `qty=-5` | 400 `Quantity must be at least 1, got -5`; bucket `qty == 10`; ledger count 1 | xfail BUG-665 — fails today on: no exception raised (stock rises to 15) |
| PSO-13 | R5 [BUG-665]; Errors row 1 | bug | MS(M1, I1, 10, 4.00) | `"machine"`, `location_id=M1`, `qty=0` | 400 `Quantity must be at least 1, got 0`; row MI `qty == 10`; machine ledger count 1; no events | xfail BUG-665 — fails today on: no exception raised ("0 units" event written) |
| PSO-14 | R5 [BUG-665] (checked first) | bug | — | `"project"`, `location_id=F1`, `qty=0` | 400 with detail `Quantity must be at least 1, got 0` (not the unsupported-location message) | xfail BUG-665 — fails today on: detail is `Unsupported source location type: project` |
| PSO-15 | R5, R1 | boundary | S(F1, I1, STORAGE, 10, 5.00) | `"storage"`, `location_id=F1`, `qty=1` | returns `Decimal("5.00")`; bucket `qty == 9`; ledger count 2 | pass |
| PSO-16 | R1; Errors row 3 (propagated) | error | — | `"storage"`, `location_id=NOID`, `qty=1` | 404 `Factory with ID 999999999 not found`; no `inventory_ledger` row with `factory_id` NOID | pass |
| PSO-17 | R3; Errors row 3 (propagated) | error | — | `"machine"`, `location_id=NOID`, `qty=1` | 404 `Machine with ID 999999999 not found`; no `machine_item_ledger` row with `machine_id` NOID; no events | pass |
| PSO-18 | R3; Errors row 3 (propagated) | error | MS(M1, I1, 1, 4.00) | `"machine"`, `location_id=M1`, `qty=2` | 400 `Insufficient machine stock (1 available, 2 requested)`; row MI `qty == 1`; machine ledger count 1; no events | pass |
| PSO-19 | R6 (location before item) | error | — | inside `begin_nested()`: `"storage"`, `location_id=NOID`, `item_id=NOID`, `qty=1` | 404 `Factory with ID 999999999 not found` (not the item message); no `inventory` / `inventory_ledger` row with `factory_id` NOID or `item_id` NOID | pass |
| PSO-20 | R6 (item before stock) [BUG-666] | bug | no rows for (W1, F1, IX) | `"storage"`, `location_id=F1`, `item_id=IX`, `qty=1` (flush) | 404 `Item with ID {IX.id} not found` (not `Insufficient stock`); no `inventory` / `inventory_ledger` row with `item_id` IX | xfail BUG-666 — fails today on: 400 `Insufficient stock (0 available, 1 requested)` |
| PSO-21 | R6 (location_type before location) | error | — | `"project"`, `location_id=NOID`, `qty=1` | 400 `Unsupported source location type: project` (not a 404); no `inventory_ledger` / `machine_item_ledger` row with `factory_id` / `machine_id` NOID; no events | pass |
| PSO-22 | R6 (location before item, machine) | error | — | inside `begin_nested()`: `"machine"`, `location_id=NOID`, `item_id=NOID`, `qty=1` | 404 `Machine with ID 999999999 not found`; no `machine_items` / `machine_item_ledger` row with `machine_id` NOID; no events | pass |
| PSO-23 | R6 (item before stock, machine) [BUG-666] | bug | no rows for (W1, M1, IX) | `"machine"`, `location_id=M1`, `item_id=IX`, `qty=1` (flush) | 404 `Item with ID {IX.id} not found` (not `Insufficient machine stock`); no `machine_items` / `machine_item_ledger` row with `item_id` IX; no events | xfail BUG-666 — fails today on: 400 `Insufficient machine stock (0 available, 1 requested)` |

## `post_stock_in`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| PSI-01 | R1, R3 (factory: no event) | happy | S(F1, I1, STORAGE, 10, 5.00) | `location_type="storage"`, `location_id=F1`, `item_id=I1`, `qty=10`, `unit_cost=Decimal("7.00")`, `activity_event_type="item_returned"`, `activity_description="ignored"` (source_loc_* omitted) | returns `None`; STORAGE bucket `qty == 20`, `avg_price == 6.00`; new ledger row `inventory_type STORAGE`, `transfer_source_type None`, `transfer_source_id None`; no events | pass |
| PSI-02 | R2 | happy | S(F1, I1, STORAGE, 10, 5.00) | `"damaged"`, `location_id=F1`, `qty=4`, `unit_cost=Decimal("3.50")` | returns `None`; DAMAGED bucket for (W1, F1, I1): `qty == 4`, `avg_price == 3.50`, its ledger row `inventory_type DAMAGED`; STORAGE bucket `qty == 10`, `avg_price == 5.00`, ledger count 1 | pass |
| PSI-03 | R3 | happy | MS(M1, I1, 4, 10.00) | `"machine"`, `location_id=M1`, `qty=4`, `unit_cost=Decimal("20.00")`, `source_loc_type="factory"`, `source_loc_id=F1.id`, `activity_event_type="item_returned"` | returns `None`; row MI `qty == 8`; new machine ledger row `avg_price_after 15.00`, `transfer_source_type "factory"`, `transfer_source_id F1.id`; exactly 1 event: `event_type "item_returned"`, `description "transfer_in: 4 units of Bearing 6204"` | pass |
| PSI-04 | R3 | side-effect | MS(M1, I1, 4, 10.00) | `"machine"`, `location_id=M1`, `qty=1`, `unit_cost=Decimal("10.00")`, `activity_event_type=None` | returns `None`; exactly 1 event, `event_type "transfer_in"` | pass |
| PSI-05 | R3 | boundary | MS(M1, I1, 4, 10.00) | same, `activity_event_type=""` | returns `None`; exactly 1 event, `event_type "transfer_in"` | pass |
| PSI-06 | R4; Errors row 2 | error | S(F1, I1, STORAGE, 10, 5.00); MS(M1, I1, 10, 4.00) | `"project"`, `location_id=F1`, `qty=1`, `unit_cost=Decimal("1.00")` | 400 `Unsupported destination location type: project`; bucket `qty == 10`, ledger count 1; row MI `qty == 10`, machine ledger count 1; no events | pass |
| PSI-07 | R4; Errors row 2 | boundary | S(F1, I1, DAMAGED, 10, 5.00) | `"Damaged"`, `location_id=F1`, `qty=1`, `unit_cost=Decimal("1.00")` | 400 `Unsupported destination location type: Damaged`; DAMAGED bucket `qty == 10`, ledger count 1; no STORAGE ledger rows for (W1, F1, I1) | pass |
| PSI-08 | R4; Errors row 2 | boundary | — | `""`, `location_id=F1`, `qty=1`, `unit_cost=Decimal("1.00")` | 400 `Unsupported destination location type: `; no `inventory_ledger` rows for (W1, F1, I1) | pass |
| PSI-09 | R5 [BUG-665]; Errors row 1 | bug | S(F1, I1, STORAGE, 10, 5.00) | `"storage"`, `location_id=F1`, `qty=0`, `unit_cost=Decimal("1.00")` | 400 `Quantity must be at least 1, got 0`; bucket `qty == 10`; ledger count 1 | xfail BUG-665 — fails today on: no exception raised |
| PSI-10 | R5 [BUG-665]; Errors row 1 | bug | S(F1, I1, STORAGE, 10, 5.00) | `"storage"`, `location_id=F1`, `qty=-5`, `unit_cost=Decimal("1.00")` | 400 `Quantity must be at least 1, got -5`; bucket `qty == 10`; ledger count 1 | xfail BUG-665 — fails today on: no exception raised (stock drops to 5) |
| PSI-11 | R5 [BUG-665]; Errors row 1 | bug | MS(M1, I1, 10, 4.00) | `"machine"`, `location_id=M1`, `qty=0`, `unit_cost=Decimal("1.00")` | 400 `Quantity must be at least 1, got 0`; row MI `qty == 10`; machine ledger count 1; no events | xfail BUG-665 — fails today on: no exception raised |
| PSI-12 | R5 [BUG-665] (checked first) | bug | — | `"project"`, `location_id=F1`, `qty=0`, `unit_cost=Decimal("1.00")` | 400 with detail `Quantity must be at least 1, got 0` | xfail BUG-665 — fails today on: detail is `Unsupported destination location type: project` |
| PSI-13 | R5, R1 | boundary | S(F1, I1, STORAGE, 10, 5.00) | `"storage"`, `location_id=F1`, `qty=1`, `unit_cost=Decimal("5.00")` | returns `None`; bucket `qty == 11`, `avg_price == 5.00`; ledger count 2 | pass |
| PSI-14 | R1; Errors row 3 (propagated) | error | — | `"storage"`, `location_id=NOID`, `qty=1`, `unit_cost=Decimal("1.00")` | 404 `Factory with ID 999999999 not found`; no `inventory_ledger` row with `factory_id` NOID | pass |
| PSI-15 | R3; Errors row 3 (propagated) | error | — | `"machine"`, `location_id=NOID`, `qty=1`, `unit_cost=Decimal("1.00")` | 404 `Machine with ID 999999999 not found`; no `machine_item_ledger` row with `machine_id` NOID; no events | pass |
| PSI-16 | R6 (location before item) | error | — | inside `begin_nested()`: `"storage"`, `location_id=NOID`, `item_id=NOID`, `qty=1`, `unit_cost=Decimal("1.00")` | 404 `Factory with ID 999999999 not found`; no `inventory` / `inventory_ledger` row with `factory_id` NOID or `item_id` NOID | pass |
| PSI-17 | R6 (location_type before location) | error | — | `"project"`, `location_id=NOID`, `qty=1`, `unit_cost=Decimal("1.00")` | 400 `Unsupported destination location type: project` (not a 404); no `inventory_ledger` / `machine_item_ledger` row with `factory_id` / `machine_id` NOID; no events | pass |
| PSI-18 | R6 (location before item, machine) | error | — | inside `begin_nested()`: `"machine"`, `location_id=NOID`, `item_id=NOID`, `qty=1`, `unit_cost=Decimal("1.00")` | 404 `Machine with ID 999999999 not found`; no `machine_items` / `machine_item_ledger` row with `machine_id` NOID; no events | pass |

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `_storage_out` R4 / `_storage_in` R3 [BUG-660] (concurrency) | integration tests (two committed sessions) | Two concurrent stock-outs of 8 from a committed bucket of 10: one succeeds, the other waits and then gets 400 `Insufficient stock (2 available, 8 requested)`; final qty 2, exactly one new ledger row. (The lock clause itself is unit-tested by SO-14 / SI-12.) |
| `_machine_out` R4 / `_machine_in` R3 [BUG-661] (concurrency) | integration tests (two committed sessions) | Same for a machine: the loser gets 400 `Insufficient machine stock (…)`; one ledger row, one event. (Lock clause unit-tested by MO-14 / MI-12.) |

## Spec gaps
None. (Revision 1 gaps 1–5 were closed by spec Gap log G1–G5; the tie-order fact was corrected by G6.)

## Retired IDs
- INVM-SO-19 — the spec's Q1 three-postings example as a strict xfail. Spec G6: today's result is plan-dependent (ends at 10 or at the correct 5), so a strict xfail would be flaky. Restore this ID as a plain `pass` case (final bucket `qty == 5`, the three new rows `qty_before` 20, 15, 10) once BUG-664 is fixed (best-practice default, delegated by reviewer).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `item_name` | R1 | IN-01, IN-04 |
| `item_name` | R2 | IN-02, IN-03 |
| `item_name` | R3 | IN-05 |
| `item_name` | R4 (statement of fact: items have no soft-delete column) | no case possible (nothing to soft-delete); the nearest state, inactive, is covered by IN-05, SO-21, SI-16, MO-17, MI-15 |
| `weighted_avg_price` | R1 | WAP-06, WAP-07, WAP-08, WAP-09, WAP-10 |
| `weighted_avg_price` | R2 | WAP-01, WAP-02, WAP-03, WAP-10, WAP-13 |
| `weighted_avg_price` | R2a [BUG-1040] | WAP-04 (xfail), WAP-05 (pass) |
| `weighted_avg_price` | R3 | WAP-11, WAP-12, WAP-13 |
| `weighted_avg_price` | R4 | WAP-14 |
| `weighted_avg_price` | R5 | WAP-15, WAP-09 |
| `inventory_type_for_location` | R1 | ITL-01 |
| `inventory_type_for_location` | R2 | ITL-02, ITL-03, ITL-04, ITL-05, ITL-06 |
| `_storage_out` | R1 / Errors row 1 | SO-11, SO-12 |
| `_storage_out` | R2 [BUG-662] | SO-13 |
| `_storage_out` | R3 | SO-01, SO-07, SO-08, SO-09, SO-10 |
| `_storage_out` | R3a [BUG-664] | SO-03, SO-04, SO-05, SO-06, SO-08, SO-10, SO-20 (pass); SO-18 (xfail) |
| `_storage_out` | R4 [BUG-660] | SO-14; concurrency Deferred |
| `_storage_out` | R5 / Errors row 3 | SO-03, SO-04, SO-06, SO-07, SO-10 |
| `_storage_out` | R6 | SO-02 |
| `_storage_out` | R7 | SO-01, SO-05, SO-17 |
| `_storage_out` | R8 | SO-01, SO-05, SO-08, SO-17, SO-20 |
| `_storage_out` | R9 [BUG-666] / Errors row 2 | SO-15, SO-16 (xfail); SO-21 (pass, inactive item accepted) |
| `_storage_out` | Inputs: free `String(50)` strings / over-long → `DataError` | SO-22, SO-23 |
| `_storage_in` | R1 / Errors row 1 | SI-09, SI-10 |
| `_storage_in` | R2 [BUG-662] | SI-11 |
| `_storage_in` | R3 (get/restore/create) | SI-01, SI-02, SI-03, SI-08 |
| `_storage_in` | R3 (sync) [BUG-664] | SI-04, SI-05 (pass); SI-15 (xfail) |
| `_storage_in` | R3 (lock) [BUG-660] | SI-12; concurrency Deferred |
| `_storage_in` | R4 | SI-06 |
| `_storage_in` | R5 | SI-01, SI-02, SI-03, SI-04, SI-05 |
| `_storage_in` | R6 | SI-01, SI-02, SI-07 |
| `_storage_in` | R7 | SI-01, SI-02, SI-03 |
| `_storage_in` | R8 [BUG-666] / Errors row 2 | SI-13, SI-14 (xfail); SI-16 (pass, inactive item accepted) |
| `_storage_in` | Inputs: negative unit_cost accepted | SI-07 |
| `ensure_machine_item` | R1 | EMI-01, EMI-02 |
| `ensure_machine_item` | R2 | EMI-02, EMI-03 |
| `ensure_machine_item` | R3 / Errors | EMI-04, EMI-05, EMI-06 |
| `ensure_machine_item` | R4 | EMI-07 |
| `get_machine_unit_cost` | R1 [BUG-664] | MUC-01 (pass); MUC-05 (xfail) |
| `get_machine_unit_cost` | R2 | MUC-02, MUC-03 |
| `get_machine_unit_cost` | R3 | MUC-04 |
| `_machine_out` | R1 / Errors row 1 | MO-11, MO-12 |
| `_machine_out` | R2 [BUG-663] | MO-13 |
| `_machine_out` | R3 | MO-01, MO-04, MO-05 |
| `_machine_out` | R4 [BUG-661] | MO-14; concurrency Deferred |
| `_machine_out` | R5 / Errors row 3 | MO-03, MO-04 |
| `_machine_out` | R6 | MO-02 |
| `_machine_out` | R7 | MO-01, MO-06 |
| `_machine_out` | R8 | MO-01, MO-02, MO-06, MO-18 |
| `_machine_out` | R9 | MO-01, MO-07, MO-08, MO-09, MO-10, MO-17, MO-18, MO-19 |
| `_machine_out` | R10 [BUG-666] / Errors row 2 | MO-15, MO-16 (xfail); MO-17 (pass, inactive item accepted) |
| `_machine_in` | R1 / Errors row 1 | MI-09, MI-10 |
| `_machine_in` | R2 [BUG-663] | MI-11 |
| `_machine_in` | R3 (get/create, no stock check) | MI-01, MI-03 |
| `_machine_in` | R3 (lock) [BUG-661] | MI-12; concurrency Deferred |
| `_machine_in` | R4 | MI-01, MI-02, MI-04 |
| `_machine_in` | R5 | MI-01, MI-02, MI-03, MI-07, MI-08 |
| `_machine_in` | R6 | MI-01, MI-02, MI-03, MI-04 |
| `_machine_in` | R7 | MI-01, MI-05, MI-06, MI-15 |
| `_machine_in` | R8 | MI-04 |
| `_machine_in` | R9 [BUG-666] / Errors row 2 | MI-13, MI-14 (xfail); MI-15 (pass, inactive item accepted) |
| `post_stock_out` | R1 | PSO-01, PSO-15, PSO-16 |
| `post_stock_out` | R2 | PSO-02, PSO-03, PSO-04 |
| `post_stock_out` | R3 | PSO-01, PSO-05, PSO-06, PSO-07, PSO-17, PSO-18 |
| `post_stock_out` | R4 / Errors row 2 | PSO-08, PSO-09, PSO-10 |
| `post_stock_out` | R5 [BUG-665] / Errors row 1 | PSO-11, PSO-12, PSO-13, PSO-14 (xfail); PSO-15 (pass, qty 1) |
| `post_stock_out` | Errors row 3 (propagated) | PSO-03, PSO-16, PSO-17, PSO-18 |
| `post_stock_out` | R6 (check order) | PSO-14 (qty→type, xfail); PSO-21 (type→location); PSO-19, PSO-22 (location→item); PSO-20, PSO-23 (item→stock, xfail) |
| `post_stock_in` | R1 | PSI-01, PSI-13, PSI-14 |
| `post_stock_in` | R2 | PSI-02, PSI-07 |
| `post_stock_in` | R3 | PSI-01, PSI-03, PSI-04, PSI-05, PSI-15 |
| `post_stock_in` | R4 / Errors row 2 | PSI-06, PSI-07, PSI-08 |
| `post_stock_in` | R5 [BUG-665] / Errors row 1 | PSI-09, PSI-10, PSI-11, PSI-12 (xfail); PSI-13 (pass, qty 1) |
| `post_stock_in` | Errors row 3 (propagated) | PSI-14, PSI-15 |
| `post_stock_in` | R6 (check order) | PSI-12 (qty→type, xfail); PSI-17 (type→location); PSI-16, PSI-18 (location→item) |
| BUG tags | BUG-660 | SO-14, SI-12; two-session race Deferred |
| BUG tags | BUG-661 | MO-14, MI-12; two-session race Deferred |
| BUG tags | BUG-662 | SO-13, SI-11 |
| BUG tags | BUG-663 | MO-13, MI-11 |
| BUG tags | BUG-664 | SO-18, SI-15, MUC-05 |
| BUG tags | BUG-665 | PSO-11, PSO-12, PSO-13, PSO-14, PSI-09, PSI-10, PSI-11, PSI-12 |
| BUG tags | BUG-666 | SO-15, SO-16, SI-13, SI-14, MO-15, MO-16, MI-13, MI-14, PSO-20, PSO-23 |
| BUG tags | BUG-1040 | WAP-04 |
