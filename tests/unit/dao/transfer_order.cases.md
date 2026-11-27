# Test cases — `app/dao/transfer_order.py`

> **Spec:** `tests/unit/dao/transfer_order.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-11; nothing open). The owner answered OQ-39 (→ BUG-2659) and OQ-40 (→ BUG-2660); the five revision-1 gaps are closed by the spec's Gap log.
> **Revision:** 2 (2026-11-14) — spec apply-review + fill-gaps of 2026-11-11.
> - OQ-39 → BUG-2659: OQ39-01, 03 … 10 stay passes (a route with a line, or no route, holds before and after the fix). OQ39-02 becomes strict xfail (a route without lines is a Draft). New: OQ39-11 (pass: the two counts add up), OQ39-12 and OQ39-13 (strict xfail: oldest drafts and pending planned with a route and no line).
> - OQ-40 → BUG-2660: OQ40-01, 02 and 05 … 08 are rewritten to the stage filter, as strict xfail. OQ40-03 and 04 stay passes. New strict xfail: OQ40-09 … 15, 18, 19 (trimmed and case-insensitive names `" planned "` and `"PLANNED"`; another name; a part of a name; an underscore; Completed with the default `exclude_complete`; a route without a line; an unknown id beside a tick; W0 / W2 planned orders). New passes: OQ40-16, 17 (a draft stored as Draft; W0's Draft status). No `Pending:` line remains.
> - G1: the year targets stand. Every NN card now runs under the default clock(NOW31, NOW31), so the current year in NN cards is 2031 and the convention Y is gone. NN-23 moves to 2033; NN-26 uses utconly(2033) with the real local clock.
> - G2 (R0): new HF-53, HF-54 (only `workspace_id` passed).
> - G3 (R2a, R2b): new NN-30, NN-31 (lowercase / mixed-case prefix not counted, pass), NN-32 (strict xfail BUG-2651: `TR-2031-0-5` alone gives -001), NN-33 (pass: `-900` beside `-0-5` gives -901).
> - G4: names confirmed. G5: a project delete writes `is_deleted`, `deleted_at`, `deleted_by` (not `is_active`); components have no soft delete, so HF-43 now uses a component of a deleted project.
> - HF-38 … 40, FF-12, FF-13 kept as HR-16 leak checks (spec review note). No ID retired.
> **Revision:** 3 (2026-11-14) — `transfer_order.verify.md` findings 1–8, all `case-missing`. F1: new HF-55, HF-56 (a factory name matched in its middle and at its end; mutant #23). F2: HF-57, HF-58 (a machine name matched at its start and in its middle; #26). F3: HF-59, HF-60 (a component name at its start and in its middle; #28). F4: HF-61 (the component name at a project source; #31, #41). F5: HF-62 (the factory name at a damaged source; #44). F6: HF-63 (a storage destination's factory name, with no storage source; #45). F7: new strict xfail OQ39-14 (BUG-2659) and OQ40-20 (BUG-2660): a route whose only line belongs to another workspace is a Draft (invalid cross-workspace data on purpose, HR-16). F8: new no-lock cards CH-06, RC-11, MI-08, PH-14, AS-09 (`written == []`, no `FOR UPDATE` in any recorded SELECT). No ID retired.
> **Counts:** 267 cases · 210 expected-to-pass · 57 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** hub filters `HF` 63 (4 bug) · factory filter `FF` 22 (6 bug) · `list_for_hub` 12 · `count_for_hub` 6 · `list_recent_for_hub` 11 (5 bug) · `count_machine_involved_for_hub` 8 · `get_pending_highlights_for_hub` 14 (5 bug) · `aggregate_hub_stats` 9 · `list_touching_location_incomplete` 11 (2 bug) · `list_inbound_to_storage_incomplete` 12 (2 bug) · `get_by_id_and_workspace` 7 · `get_next_number` 33 (9 bug) · item `get_by_order` 11 (2 bug) · `get_by_transfer_order_ids` 10 (2 bug) · item `get_by_id_and_workspace` 4 · stage rule `OQ39` 14 (4 bug, BUG-2659) · status ticks `OQ40` 20 (16 bug, BUG-2660).
- **Depth:** full (skill step 1a). Transfers move stock, the numbering has four bugs (BUG-2650 … 2653), and the hub filters decide what a factory manager sees.
- **Owner answers (2026-11-11).** OQ-39 and OQ-40 keep their card IDs (`TRO-OQ39-*`, `TRO-OQ40-*`) in two sections of their own. A card that holds both today and after the fix is a pass. A card where today differs is strict xfail, with one failing Then line. Outside those sections, every highlight order has a route and a line (planned) or `destination_location_id 0` (draft), and no card passes a non-empty `status_ids`. So the stage fixes change no other card.
- **Notable design choices:**
  - **Parallel runs and numbering.** Today `transfer_number` is unique across all workspaces (BUG-2650). Every card outside `get_next_number` stores **GN(n)** = `n` + `-<pid>`. The `NN` cards cannot use the suffix, because R2b, R3 and R4 parse the text after the last dash. Instead, every `NN` card stores exact numbers and starts with **numlock** (`pg_advisory_xact_lock(2650)`), so two processes never hold the same plain number at once. The lock is released at the rollback.
  - **Year.** Every NN call runs under clock(NOW31, NOW31) unless the card gives its own clock, through the spec's targets: stdlib `datetime.datetime` today, `app.dao.transfer_order.utcnow` and `app.utils.time.utcnow` after BUG-2653. So a hard-coded or real-clock year fails every NN card.
    - NN-23 (pass, 2033) shows the year follows the clock.
    - NN-24 and NN-25 (strict xfail) split the two clocks across New Year, in both directions.
    - NN-26 (strict xfail) patches only `utcnow` and leaves the real local clock.
  - **Text order.** NN-33 pairs `-0-5` with `-900`. `-900` is highest both in byte order and in a locale collation that skips dashes, so the card does not depend on the database collation.
  - **BUG-2650** is tested with direct inserts. NN-27 (the number held by W2) and NN-28 (held by W0) are strict xfail. NN-29 (pass) keeps the same-workspace duplicate as 23505, which holds under every fix. The race in BUG-2652 is deferred to an integration test.
  - **BUG-2651:** NN-07 is a pass (`-999` → `-1000`). NN-08, NN-09, NN-10 and NN-32 are strict xfail.
  - **Factory filter (BUG-2658).** Pass cards cover what holds both today and after the fix: each destination type, the source fallback, the R2 negatives, type mixing, and another workspace's machine or component. Five strict xfail cards are transfers that leave F1, plus one count card.
  - **Search (BUG-2654).** Pass cards: the number in its middle, either case, the type texts, every name kind matched at its start, middle and end (HF-55 … HF-60), every location end (HF-31, 32, 34, 36, 61, 62, 63), blanks, W0 / W2 names, soft-deleted names, an order counted once. Strict xfail: `_`, `%`, `beta_`, `\`.
  - **Cross-workspace rows on purpose.** HF-38 … HF-40, FF-12 and FF-13 build a W1 order whose location id is another workspace's factory, machine or component; OQ39-14 and OQ40-20 give a W1 order a line of W2. That is invalid data (HR-16); the spec keeps these cards as "invalid data must not leak" read checks. Every other isolation card uses each workspace's own rows or `MISSING` ids.
  - **Ties.** BUG-2655, 2656 and 2657 follow the house recipe: seqscan, then a raw `UPDATE` of the lowest id. Those cards are non-strict and `Author: claude`. Each unordered query has one strict statement alarm, and the NULL-first cards of BUG-2655 are strict.
  - **No money here.** IO-10 checks that quantities are stored half up (HR-15 note).
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `TRO` = `app/dao/transfer_order.py`. `HF` hub filters (`_apply_transfer_order_hub_filters`, through `list_for_hub` / `count_for_hub`) · `FF` factory filter · `LH` list_for_hub · `CH` count_for_hub · `RC` list_recent_for_hub · `MI` count_machine_involved_for_hub · `PH` get_pending_highlights_for_hub · `AS` aggregate_hub_stats · `TL` list_touching_location_incomplete · `IB` list_inbound_to_storage_incomplete · `GI` TransferOrderDAO.get_by_id_and_workspace · `NN` get_next_number · `IO` TransferOrderItemDAO.get_by_order · `IT` get_by_transfer_order_ids · `II` TransferOrderItemDAO.get_by_id_and_workspace · `OQ39` stage rule (BUG-2659, owner's answer to OQ-39) · `OQ40` status ticks by stage (BUG-2660, owner's answer to OQ-40).

**Actors and fixed values.**
- `dao` = `transfer_order_dao`, `idao` = `transfer_order_item_dao` (`from app.dao.transfer_order import ...`). `db` = the real session, first argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- Models `app.models.<m>`: `transfer_order.TransferOrder`, `transfer_order_item.TransferOrderItem`, `status.Status`, `factory.Factory`, `machine.Machine`, `project.Project`, `project_component.ProjectComponent`, `item.Item`. `IntegrityError` = `sqlalchemy.exc.IntegrityError`; `text`, `select`, `func`, `inspect` = sqlalchemy's; `Decimal`, `date`, `datetime`, `timedelta`, `patch`, `os`.
- MISSING = `999999999`. **GN(s)** = `f"{s}-{os.getpid()}"`. **XID(k)** = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`.
- **TS(h)** = `datetime(2026, 3, 4, 0, 0) + timedelta(hours=h)` (naive UTC). D = `date(2026, 3, 4)`. DONE = `datetime(2026, 3, 20, 9, 0)`.
- **NOW31** = `datetime(2031, 6, 1, 12, 0)`: the default clock of every NN card (see the NN section intro).
- **F(...)** = `{"date_from": None, "date_to": None, "status_ids": None, "factory_id": None, "source_location_type": None, "destination_location_type": None, "search": None}` with the given keys replaced; written `**F(search="kilo")`. `**F()` = all `None`. `exclude_complete` is passed only when the card writes it. Every keyword may be omitted (R0); a card that calls with `workspace_id` only says so.

**Standing rows** (every test, this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` ×3 (`W0.id < W1.id < W2.id`); U1, U2 = `make_profile(db)` ×2.
2. Statuses `Status(workspace_id=…, name=…, comment="stage")`: S0 (W0, "Draft"), S1 (W1, "Draft"), SP (W1, "Planned"), SC (W1, "Completed"), S2 (W2, "Draft").
3. Factories `Factory(workspace_id=…, name=…, abbreviation=…)`: F0 (W0, "Zulu Depot", "ZD"), F1 (W1, "Alpha Works", "AW"), FB (W1, "Bravo Yard", "BY"), F2 (W2, "Yankee Store", "YS").
4. Machines `Machine(id=…, workspace_id=…, factory_id=…, name=…)`: M1 (XID(1), W1, F1, "Press Kilo"), MB (XID(2), W1, FB, "Lathe Lima"), M0 (XID(3), W0, F0, "Drill Oscar"), M2 (XID(4), W2, F2, "Saw Romeo").
5. Projects `Project(workspace_id=…, factory_id=…, name=…, description="Main")`: PJ1 (W1, F1, "Tower One"), PJB (W1, FB, "Tower Two"), PJ0 (W0, F0, "Tower Zero"), PJ2 (W2, F2, "Tower Nine"). Components `ProjectComponent(id=…, workspace_id=…, project_id=…, name=…)`: C1 (XID(5), W1, PJ1, "Span Delta"), CB (XID(6), W1, PJB, "Beam Echo"), C0 (XID(7), W0, PJ0, "Deck Quebec"), C2 (XID(8), W2, PJ2, "Pier Sierra").
6. Items `Item(workspace_id=…, name="Bolt", name_normalized="bolt", unit="pcs")`: I0 (W0), I1 (W1), I2 (W2).
Machine and component ids are explicit, so no machine or component id equals a factory id or another's.

**Given rows.** Inserted directly (never through the DAOs), flushed one at a time in the order written. After "but" a line lists every column that differs.
- **order n** = `TransferOrder(workspace_id=W1.id, transfer_number=GN(f"TR-2026-{n:03d}"), source_location_type="storage", source_location_id=F1.id, destination_location_type="machine", destination_location_id=M1.id, current_status_id=S1.id, created_by=U1.id, created_at=TS(n))`. "order n **of W0**" uses W0, F0, M0, S0; "**of W2**" uses W2, F2, M2, S2. Every `n` in a card is distinct. `updated_at` stays NULL unless the card gives it.
- **completed** = `completed_at DONE`. **draft** = `destination_location_id 0`. **planned** = a line(T, 1) is inserted right after order T.
- **line(T, k)** = `TransferOrderItem(workspace_id=T.workspace_id, transfer_order_id=T.id, line_number=k, item_id=<I0, I1 or I2 of T's workspace>.id, quantity=Decimal("2.00"))`.
- **num(W, s)** = order 1 of W (W0 / W2 as above), but `transfer_number s` (exact, no GN). NN cards build orders only this way; two num rows of one card use distinct `created_at` (`TS(1)`, `TS(2)` …, in the order written).
- **numlock** = `db.execute(text("SELECT pg_advisory_xact_lock(2650)"))`, the first Given step of every NN card.
- **deleted** factory = `is_deleted True`, `deleted_at TS(0)`, `deleted_by U1.id`; machine = also `is_active False`; project = `is_deleted True`, `deleted_at TS(0)`, `deleted_by U1.id` (`is_active` untouched); a project component has no soft delete (a component "of a deleted project" is a live component whose project is deleted). Applied by `UPDATE` through the ORM and flushed, as a Given step.
- **seqscan** = `SET LOCAL enable_indexscan = off`, `SET LOCAL enable_bitmapscan = off`, `SET LOCAL enable_indexonlyscan = off`, each through `db.execute(text(...))`. **bump(X)** = `db.execute(text("UPDATE transfer_orders SET transfer_number = transfer_number WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`. **bumpL(X)** = the same on `transfer_order_items` with `SET quantity = quantity`.
- **Dhaka** = `db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))`.

**Externals.** None, except in the cards that name these, and in every `NN` card that calls `get_next_number`: it runs under clock(NOW31, NOW31) unless it writes its own clock line (these targets are the spec's, Overview **Clock (G1)**):
- **clock(L, U)** = for the When only, patch the stdlib attribute `datetime.datetime` (`patch("datetime.datetime", FakeDT)`, with FakeDT a subclass of the real `datetime` whose `now(tz=None)` returns L). Also patch `app.dao.transfer_order.utcnow` (with `create=True`) and `app.utils.time.utcnow` to return U. Build every value before entering the patch.
- **utconly(U)** = only the two `utcnow` patches.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` (order is part of the check). **idset(result)** = `{r.id for r in result}`. **hids(lst)** = `[e["id"] for e in lst]`.
- **re-read X** = `db.expire_all()`, then SELECT X by id. **total()** = `db.scalar(select(func.count()).select_from(TransferOrder))`.
- **loaded(X, a)** = `a not in inspect(X).unloaded`, checked before any attribute of X is read.
- `pending:` lines check the session directly after the call, before anything expires it.
- `raises: IntegrityError` = `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards; later lines on `exc.value.orig`. `raises: TypeError` = plain `pytest.raises`.
- **Statement recorder** = the SQL sent during the When (a `before_cursor_execute` listener). `selects` = every recorded `SELECT`; `sql` = the one `SELECT` from the card's table; `order_part` = text of `sql` after its first `ORDER BY`, before any `LIMIT` (`""` if none); `written` = every recorded `INSERT`, `UPDATE`, `DELETE`.
- **No-lock check** = `"FOR UPDATE" not in sql`.
- **Clear the session before a one-query check**: such a card ends its Given with `db.expunge_all()`; ids used in Then are read from objects into local variables before it.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`, always `Author: claude`. Never weaken an assertion.

**Race simulations.** None (BUG-2652 deferred to an integration test).

## `_apply_transfer_order_hub_filters` (through `list_for_hub` / `count_for_hub`)

### TRO-HF-01 — only W1's orders are kept, with orders of W0 and W2 on either side
- **Rules:** `_apply_transfer_order_hub_filters` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order 9 of W0.
2. A = order 1.
3. B = order 2.
4. X2 = order 8 of W2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### TRO-HF-02 — asked for W2, only W2's order is kept, though W0 and W1 come earlier
- **Rules:** `_apply_transfer_order_hub_filters` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order 9 of W0.
2. A = order 1.
3. X2 = order 2 of W2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W2.id, **F())`.

**Then**
1. returns: `ids(result) == [X2.id]`.

### TRO-HF-03 — asked for W0, only W0's order is kept, though W1 and W2 come later
- **Rules:** `_apply_transfer_order_hub_filters` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order 1 of W0.
2. A = order 9.
3. X2 = order 8 of W2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W0.id, **F())`.

**Then**
1. returns: `ids(result) == [X0.id]`.

### TRO-HF-04 — date_from keeps 00:00:00 of that day and drops the last microsecond before it
- **Rules:** `_apply_transfer_order_hub_filters` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `created_at datetime(2026, 3, 3, 23, 59, 59, 999999)`.
2. B = order 2, but `created_at datetime(2026, 3, 4, 0, 0, 0)`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(date_from=date(2026, 3, 4)))`.

**Then**
1. returns: `ids(result) == [B.id]`.

### TRO-HF-05 — date_to keeps 23:59:59.999999 of that day and drops the next midnight
- **Rules:** `_apply_transfer_order_hub_filters` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `created_at datetime(2026, 3, 4, 23, 59, 59, 999999)`.
2. B = order 2, but `created_at datetime(2026, 3, 5, 0, 0, 0)`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(date_to=date(2026, 3, 4)))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-06 — date_from equal to date_to covers that whole day only
- **Rules:** `_apply_transfer_order_hub_filters` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `created_at datetime(2026, 3, 3, 23, 59, 59, 999999)`.
2. B = order 2, but `created_at datetime(2026, 3, 4, 0, 0, 0)`.
3. C = order 3, but `created_at datetime(2026, 3, 4, 12, 0, 0)`.
4. E = order 4, but `created_at datetime(2026, 3, 4, 23, 59, 59, 999999)`.
5. G = order 5, but `created_at datetime(2026, 3, 5, 0, 0, 0)`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(date_from=date(2026, 3, 4), date_to=date(2026, 3, 4)))`.

**Then**
1. returns: `ids(result) == [E.id, C.id, B.id]`.

### TRO-HF-07 — date_from after date_to keeps nothing and raises nothing
- **Rules:** `_apply_transfer_order_hub_filters` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `created_at datetime(2026, 3, 4, 12, 0, 0)`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(date_from=date(2026, 3, 5), date_to=date(2026, 3, 4)))`.

**Then**
1. returns: `result == []`.

### TRO-HF-08 — days are UTC days, also when the session time zone is Dhaka
- **Rules:** `_apply_transfer_order_hub_filters` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Dhaka.
2. A = order 1, but `created_at datetime(2026, 3, 4, 20, 0, 0)`.
3. B = order 2, but `created_at datetime(2026, 3, 5, 1, 0, 0)`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(date_from=date(2026, 3, 4), date_to=date(2026, 3, 4)))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-09 — status_ids [] is no status filter
- **Rules:** `_apply_transfer_order_hub_filters` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2, but `current_status_id SP.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=[]))`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### TRO-HF-10 — status_ids None is no status filter
- **Rules:** `_apply_transfer_order_hub_filters` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `current_status_id SC.id`.
2. B = order 2, but `current_status_id SP.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=None))`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### TRO-HF-11 — source_location_type keeps only that source type
- **Rules:** `_apply_transfer_order_hub_filters` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_type "damaged"`.
2. B = order 2.
3. C = order 3, but `source_location_type "machine"`, `source_location_id MB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(source_location_type="storage"))`.

**Then**
1. returns: `ids(result) == [B.id]`.

### TRO-HF-12 — source_location_type with a capital letter matches nothing
- **Rules:** `_apply_transfer_order_hub_filters` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(source_location_type="Storage"))`.

**Then**
1. returns: `result == []`.

### TRO-HF-13 — a part of the source type matches nothing
- **Rules:** `_apply_transfer_order_hub_filters` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(source_location_type="stor"))`.

**Then**
1. returns: `result == []`.

### TRO-HF-14 — a leading space in the source type matches nothing
- **Rules:** `_apply_transfer_order_hub_filters` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(source_location_type=" storage"))`.

**Then**
1. returns: `result == []`.

### TRO-HF-15 — an underscore in the source type is not a wildcard
- **Rules:** `_apply_transfer_order_hub_filters` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(source_location_type="st_rage"))`.

**Then**
1. returns: `result == []`.

### TRO-HF-16 — destination_location_type keeps only that destination type
- **Rules:** `_apply_transfer_order_hub_filters` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_type "project"`, `destination_location_id C1.id`.
2. B = order 2.
3. C = order 3, but `destination_location_type "storage"`, `destination_location_id FB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(destination_location_type="project"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-17 — destination_location_type with a capital letter matches nothing
- **Rules:** `_apply_transfer_order_hub_filters` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(destination_location_type="Machine"))`.

**Then**
1. returns: `result == []`.

### TRO-HF-18 — source and destination types together combine with AND
- **Rules:** `_apply_transfer_order_hub_filters` R5, R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2, but `destination_location_type "project"`, `destination_location_id C1.id`.
3. C = order 3, but `source_location_type "damaged"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(source_location_type="storage", destination_location_type="machine"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-19 — empty location types are no filter
- **Rules:** `_apply_transfer_order_hub_filters` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2, but `source_location_type "damaged"`, `destination_location_type "project"`, `destination_location_id C1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(source_location_type="", destination_location_type=""))`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### TRO-HF-20 — factory_id 0 is a filter and keeps nothing
- **Rules:** `_apply_transfer_order_hub_filters` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=0))`.

**Then**
1. returns: `result == []`.

### TRO-HF-21 — by default completed orders are dropped
- **Rules:** `_apply_transfer_order_hub_filters` R7, `list_for_hub` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2, but completed.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F())` (`exclude_complete` not passed).

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-22 — exclude_complete=False keeps completed orders
- **Rules:** `_apply_transfer_order_hub_filters` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2, but completed.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, exclude_complete=False, **F())`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### TRO-HF-23 — search "" is no search filter
- **Rules:** `_apply_transfer_order_hub_filters` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2, but `source_location_type "damaged"`, `source_location_id FB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search=""))`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### TRO-HF-24 — a whitespace-only search is no search filter
- **Rules:** `_apply_transfer_order_hub_filters` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2, but `source_location_type "damaged"`, `source_location_id FB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="   "))`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### TRO-HF-25 — the number is matched by a part in its middle
- **Rules:** `_apply_transfer_order_hub_filters` R8, R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 7.
2. B = order 17.
3. C = order 70.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="6-007"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-26 — a lowercase search finds the uppercase number
- **Rules:** `_apply_transfer_order_hub_filters` R8, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 7.
2. B = order 17.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="tr-2026-007"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-27 — an uppercase search finds a mixed-case machine name
- **Rules:** `_apply_transfer_order_hub_filters` R8, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2, but `destination_location_id MB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="KILO"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-28 — the search text is trimmed before matching
- **Rules:** `_apply_transfer_order_hub_filters` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2, but `destination_location_id MB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="  kilo  "))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-29 — the source type text is searched
- **Rules:** `_apply_transfer_order_hub_filters` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_type "damaged"`.
2. B = order 2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="amag"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-30 — the destination type text is searched
- **Rules:** `_apply_transfer_order_hub_filters` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2, but `destination_location_type "project"`, `destination_location_id C1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="roje"))`.

**Then**
1. returns: `ids(result) == [B.id]`.

### TRO-HF-31 — the factory name at a storage source is searched
- **Rules:** `_apply_transfer_order_hub_filters` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2, but `source_location_id FB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="bravo"))`.

**Then**
1. returns: `ids(result) == [B.id]`.

### TRO-HF-32 — the factory name at a damaged destination is searched
- **Rules:** `_apply_transfer_order_hub_filters` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2, but `destination_location_type "damaged"`, `destination_location_id FB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="bravo"))`.

**Then**
1. returns: `ids(result) == [B.id]`.

### TRO-HF-33 — a factory id under a machine end is not looked up as a factory
- **Rules:** `_apply_transfer_order_hub_filters` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_id FB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="bravo"))`.

**Then**
1. returns: `result == []`.

### TRO-HF-34 — the machine name at a machine source is searched
- **Rules:** `_apply_transfer_order_hub_filters` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_type "machine"`, `source_location_id MB.id`, `destination_location_type "storage"`, `destination_location_id F1.id`.
2. B = order 2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="lima"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-35 — a machine id under a storage end is not looked up as a machine
- **Rules:** `_apply_transfer_order_hub_filters` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id MB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="lima"))`.

**Then**
1. returns: `result == []`.

### TRO-HF-36 — the component name at a project destination is searched
- **Rules:** `_apply_transfer_order_hub_filters` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_type "project"`, `destination_location_id CB.id`.
2. B = order 2, but `destination_location_type "project"`, `destination_location_id C1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="echo"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-37 — a known type whose id resolves to nothing is not found by a name
- **Rules:** `_apply_transfer_order_hub_filters` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id MISSING`, `destination_location_id MISSING`.
2. B = order 2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="alpha"))`.

**Then**
1. returns: `ids(result) == [B.id]`.

### TRO-HF-38 — another workspace's factory name never matches (W2 factory id on a W1 order)
- **Rules:** `_apply_transfer_order_hub_filters` R9; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id F2.id` (invalid cross-workspace data, built on purpose).
2. B = order 2 of W2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="yankee"))`.

**Then**
1. returns: `result == []`.

### TRO-HF-39 — another workspace's machine name never matches (W0 machine id on a W1 order)
- **Rules:** `_apply_transfer_order_hub_filters` R9; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_id M0.id` (invalid cross-workspace data, built on purpose).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="oscar"))`.

**Then**
1. returns: `result == []`.

### TRO-HF-40 — another workspace's component name never matches (W2 component id on a W1 order)
- **Rules:** `_apply_transfer_order_hub_filters` R9; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_type "project"`, `destination_location_id C2.id` (invalid cross-workspace data, built on purpose).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="sierra"))`.

**Then**
1. returns: `result == []`.

### TRO-HF-41 — a soft-deleted factory's name still matches
- **Rules:** `_apply_transfer_order_hub_filters` R9
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FB is deleted (factory).
2. A = order 1, but `source_location_id FB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="bravo"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-42 — a soft-deleted machine's name still matches
- **Rules:** `_apply_transfer_order_hub_filters` R9
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. MB is deleted (machine).
2. A = order 1, but `destination_location_id MB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="lima"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-43 — a component of a soft-deleted project still matches by its name
- **Rules:** `_apply_transfer_order_hub_filters` R9
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. PJB is deleted (project).
2. A = order 1, but `destination_location_type "project"`, `destination_location_id CB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="echo"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-44 — an order matching at both ends is listed once
- **Rules:** `_apply_transfer_order_hub_filters` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_type "storage"`, `destination_location_id F1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="alpha"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-45 — an order matching by type and by name at both ends is counted once
- **Rules:** `_apply_transfer_order_hub_filters` R10, `count_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FA2 = `Factory(workspace_id=W1.id, name="Storage Annex", abbreviation="SA")`.
2. A = order 1, but `source_location_id FA2.id`, `destination_location_type "storage"`, `destination_location_id FA2.id`.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, **F(search="storage"))`.

**Then**
1. returns: `result == 1`.

### TRO-HF-46 — an underscore in the search matches only a literal underscore
- **Rules:** `_apply_transfer_order_hub_filters` R10a [BUG-2654]
- **Kind:** bug
- **Expect:** xfail BUG-2654
- **Fails today on:** Then 1 (today `_` is a wildcard and every order matches)

**Given**
1. FU = `Factory(workspace_id=W1.id, name="Beta_Works", abbreviation="BW")`.
2. A = order 1, but `source_location_id FU.id`.
3. B = order 2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="_"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-47 — an underscore search still finds the name that holds an underscore
- **Rules:** `_apply_transfer_order_hub_filters` R9, R10a
- **Kind:** happy
- **Expect:** pass

**Given**
1. FU = `Factory(workspace_id=W1.id, name="Beta_Works", abbreviation="BW")`.
2. A = order 1, but `source_location_id FU.id`.
3. B = order 2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="_"))`.

**Then**
1. returns: `A.id in idset(result)`.

### TRO-HF-48 — a percent sign in the search matches only a literal percent sign
- **Rules:** `_apply_transfer_order_hub_filters` R10a [BUG-2654]
- **Kind:** bug
- **Expect:** xfail BUG-2654
- **Fails today on:** Then 1 (today `%` matches every order)

**Given**
1. A = order 1.
2. B = order 2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="%"))`.

**Then**
1. returns: `result == []`.

### TRO-HF-49 — "beta_" finds Beta_Works and not Betax Works
- **Rules:** `_apply_transfer_order_hub_filters` R10a [BUG-2654]
- **Kind:** bug
- **Expect:** xfail BUG-2654
- **Fails today on:** Then 1 (today `_` matches the `x` too)

**Given**
1. FU = `Factory(workspace_id=W1.id, name="Beta_Works", abbreviation="BW")`.
2. FX = `Factory(workspace_id=W1.id, name="Betax Works", abbreviation="BX")`.
3. A = order 1, but `source_location_id FU.id`.
4. B = order 2, but `source_location_id FX.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="beta_"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-50 — "beta_" still finds Beta_Works
- **Rules:** `_apply_transfer_order_hub_filters` R9, R10a
- **Kind:** happy
- **Expect:** pass

**Given**
1. FU = `Factory(workspace_id=W1.id, name="Beta_Works", abbreviation="BW")`.
2. FX = `Factory(workspace_id=W1.id, name="Betax Works", abbreviation="BX")`.
3. A = order 1, but `source_location_id FU.id`.
4. B = order 2, but `source_location_id FX.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="beta_"))`.

**Then**
1. returns: `A.id in idset(result)`.

### TRO-HF-51 — a backslash in the search matches a literal backslash
- **Rules:** `_apply_transfer_order_hub_filters` R10a [BUG-2654]
- **Kind:** bug
- **Expect:** xfail BUG-2654
- **Fails today on:** Then 1 (today the backslash escapes the closing `%` of the pattern, so the name is not found)

**Given**
1. FS = `Factory(workspace_id=W1.id, name="Back\\Slash", abbreviation="BS")` (Python literal; the stored name is `Back\Slash`).
2. A = order 1, but `source_location_id FS.id`.
3. B = order 2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="\\"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-52 — search, type and date filters combine with AND
- **Rules:** `_apply_transfer_order_hub_filters` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`, `created_at datetime(2026, 3, 4, 10, 0)`.
2. B = order 2, but `source_location_id FB.id`, `created_at datetime(2026, 3, 6, 10, 0)`.
3. C = order 3, but `source_location_type "damaged"`, `source_location_id FB.id`, `created_at datetime(2026, 3, 4, 11, 0)`.
4. E = order 4, but `created_at datetime(2026, 3, 4, 12, 0)`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="bravo", source_location_type="storage", date_to=date(2026, 3, 4)))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-53 — called with only workspace_id, no filter applies and completed orders are dropped
- **Rules:** `_apply_transfer_order_hub_filters` R0, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X0 = order 1 of W0.
2. A = order 2, but `source_location_type "damaged"`, `destination_location_type "warehouse"`, `destination_location_id 0`, `current_status_id SC.id`.
3. B = order 3, but completed.
4. C = order 4, but `created_at datetime(2020, 1, 1, 0, 0)`.
5. X2 = order 5 of W2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, C.id]`.

### TRO-HF-54 — the KPI totals called with only workspace_id drop completed orders
- **Rules:** `_apply_transfer_order_hub_filters` R0, R7; `aggregate_hub_stats` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X0 = order 1 of W0.
2. A = order 2.
3. B = order 3, but completed.
4. X2 = order 4 of W2.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == (1, 1, 0)`.

### TRO-HF-55 — a factory name is matched by a part in its middle
- **Rules:** `_apply_transfer_order_hub_filters` R8, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`.
2. B = order 2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="avo ya"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-56 — a factory name is matched by its end
- **Rules:** `_apply_transfer_order_hub_filters` R8, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`.
2. B = order 2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="yard"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-57 — a machine name is matched by its start
- **Rules:** `_apply_transfer_order_hub_filters` R8, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_id MB.id`.
2. B = order 2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="lathe"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-58 — a machine name is matched by a part in its middle
- **Rules:** `_apply_transfer_order_hub_filters` R8, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_id MB.id`.
2. B = order 2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="the li"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-59 — a component name is matched by its start
- **Rules:** `_apply_transfer_order_hub_filters` R8, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_type "project"`, `destination_location_id CB.id`.
2. B = order 2, but `destination_location_type "project"`, `destination_location_id C1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="beam"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-60 — a component name is matched by a part in its middle
- **Rules:** `_apply_transfer_order_hub_filters` R8, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_type "project"`, `destination_location_id CB.id`.
2. B = order 2, but `destination_location_type "project"`, `destination_location_id C1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="am ec"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-61 — the component name at a project source is searched
- **Rules:** `_apply_transfer_order_hub_filters` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_type "project"`, `source_location_id CB.id`.
2. B = order 2, but `destination_location_type "project"`, `destination_location_id C1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="echo"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-62 — the factory name at a damaged source is searched
- **Rules:** `_apply_transfer_order_hub_filters` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_type "damaged"`, `source_location_id FB.id`.
2. B = order 2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="bravo"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-HF-63 — the factory name at a storage destination is searched, with no storage source
- **Rules:** `_apply_transfer_order_hub_filters` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_type "machine"`, `source_location_id M1.id`, `destination_location_type "storage"`, `destination_location_id FB.id`.
2. B = order 2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(search="bravo"))`.

**Then**
1. returns: `ids(result) == [A.id]`.

## `_apply_transfer_factory_filter` (through `list_for_hub`)

### TRO-FF-01 — a storage destination of F1 is kept for F1
- **Rules:** `_apply_transfer_factory_filter` R1, R1a
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`, `destination_location_type "storage"`, `destination_location_id F1.id`.
2. B = order 2, but `source_location_id FB.id`, `destination_location_type "storage"`, `destination_location_id FB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-FF-02 — a damaged destination of F1 is kept for F1
- **Rules:** `_apply_transfer_factory_filter` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`, `destination_location_type "damaged"`, `destination_location_id F1.id`.
2. B = order 2, but `source_location_id FB.id`, `destination_location_type "damaged"`, `destination_location_id FB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-FF-03 — a machine destination in F1 is kept for F1, one in FB is not
- **Rules:** `_apply_transfer_factory_filter` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`.
2. B = order 2, but `source_location_id FB.id`, `destination_location_id MB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-FF-04 — a project destination whose project is in F1 is kept for F1, one in FB is not
- **Rules:** `_apply_transfer_factory_filter` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`, `destination_location_type "project"`, `destination_location_id C1.id`.
2. B = order 2, but `source_location_id FB.id`, `destination_location_type "project"`, `destination_location_id CB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-FF-05 — with an unknown destination type the source decides (machine of F1 → "warehouse")
- **Rules:** `_apply_transfer_factory_filter` R1, R1a
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_type "machine"`, `source_location_id M1.id`, `destination_location_type "warehouse"`, `destination_location_id F1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-FF-06 — with an empty destination type the source decides (storage F1 → "")
- **Rules:** `_apply_transfer_factory_filter` R1, R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_type ""`, `destination_location_id M1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-FF-07 — a transfer between two locations of F1 appears once
- **Rules:** `_apply_transfer_factory_filter` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-FF-08 — a transfer between two locations of F1 is counted once
- **Rules:** `_apply_transfer_factory_filter` R3, `count_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_type "project"`, `destination_location_id C1.id`.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `result == 1`.

### TRO-FF-09 — unknown types at both ends belong to no factory
- **Rules:** `_apply_transfer_factory_filter` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_type "warehouse"`, `source_location_id F1.id`, `destination_location_type "warehouse"`, `destination_location_id F1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `result == []`.

### TRO-FF-10 — known types whose ids resolve to nothing belong to no factory
- **Rules:** `_apply_transfer_factory_filter` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_type "machine"`, `source_location_id MISSING`, `destination_location_type "project"`, `destination_location_id MISSING`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `result == []`.

### TRO-FF-11 — a machine id under a storage destination is not read as a machine
- **Rules:** `_apply_transfer_factory_filter` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_type "warehouse"`, `destination_location_type "storage"`, `destination_location_id M1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `result == []`.

### TRO-FF-12 — another workspace's machine never makes an end belong (W2 machine on a W1 order)
- **Rules:** `_apply_transfer_factory_filter` R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_type "warehouse"`, `destination_location_id M2.id` (invalid cross-workspace data, built on purpose).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F2.id))`.

**Then**
1. returns: `result == []`.

### TRO-FF-13 — another workspace's component never makes an end belong (W0 component on a W1 order)
- **Rules:** `_apply_transfer_factory_filter` R1; HR-16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_type "warehouse"`, `destination_location_type "project"`, `destination_location_id C0.id` (invalid cross-workspace data, built on purpose).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F0.id))`.

**Then**
1. returns: `result == []`.

### TRO-FF-14 — a soft-deleted machine of F1 still makes the destination belong
- **Rules:** `_apply_transfer_factory_filter` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. M1 is deleted (machine).
2. A = order 1, but `source_location_id FB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-FF-15 — a component of a soft-deleted project of F1 still makes the destination belong
- **Rules:** `_apply_transfer_factory_filter` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. PJ1 is deleted (project).
2. A = order 1, but `source_location_id FB.id`, `destination_location_type "project"`, `destination_location_id C1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-FF-16 — a transfer leaving F1's storage for FB's machine is still kept for FB
- **Rules:** `_apply_transfer_factory_filter` R1, R1a
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_id MB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=FB.id))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-FF-17 — a transfer leaving F1's storage for FB's machine is kept for F1
- **Rules:** `_apply_transfer_factory_filter` R1a [BUG-2658]
- **Kind:** bug
- **Expect:** xfail BUG-2658
- **Fails today on:** Then 1 (today only the destination's factory FB keeps it)

**Given**
1. A = order 1, but `destination_location_id MB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-FF-18 — a transfer from F1's damaged stock to FB's storage is kept for F1
- **Rules:** `_apply_transfer_factory_filter` R1a [BUG-2658]
- **Kind:** bug
- **Expect:** xfail BUG-2658
- **Fails today on:** Then 1 (today the destination decides)

**Given**
1. A = order 1, but `source_location_type "damaged"`, `destination_location_type "storage"`, `destination_location_id FB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-FF-19 — a transfer from F1's machine to FB's component is kept for F1
- **Rules:** `_apply_transfer_factory_filter` R1a [BUG-2658]
- **Kind:** bug
- **Expect:** xfail BUG-2658
- **Fails today on:** Then 1 (today the destination decides)

**Given**
1. A = order 1, but `source_location_type "machine"`, `source_location_id M1.id`, `destination_location_type "project"`, `destination_location_id CB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-FF-20 — a transfer from F1's component to FB's storage is kept for F1
- **Rules:** `_apply_transfer_factory_filter` R1a [BUG-2658]
- **Kind:** bug
- **Expect:** xfail BUG-2658
- **Fails today on:** Then 1 (today the destination decides)

**Given**
1. A = order 1, but `source_location_type "project"`, `source_location_id C1.id`, `destination_location_type "storage"`, `destination_location_id FB.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-FF-21 — a known destination type resolving to nothing does not hide F1's source
- **Rules:** `_apply_transfer_factory_filter` R1a [BUG-2658]
- **Kind:** bug
- **Expect:** xfail BUG-2658
- **Fails today on:** Then 1 (today the source is read only when the destination type is unknown)

**Given**
1. A = order 1, but `destination_location_type "storage"`, `destination_location_id MISSING`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-FF-22 — the count for F1 includes the transfer leaving F1
- **Rules:** `_apply_transfer_factory_filter` R1a [BUG-2658], `count_for_hub` R1
- **Kind:** bug
- **Expect:** xfail BUG-2658
- **Fails today on:** Then 1 (today 1: only A)

**Given**
1. A = order 1.
2. B = order 2, but `destination_location_id MB.id`.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, **F(factory_id=F1.id))`.

**Then**
1. returns: `result == 2`.

## `TransferOrderDAO.list_for_hub`

### TRO-LH-01 — newest created first, with an older order holding the higher id
- **Rules:** `list_for_hub` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 2.
2. B = order 3.
3. C = order 1.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `isinstance(result[0], TransferOrder)`.
3. returns: `ids(result) == [B.id, A.id, C.id]`.

### TRO-LH-02 — equal created_at is broken by id descending, after the lowest id was rewritten
- **Rules:** `list_for_hub` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. seqscan.
2. A = order 1, but `created_at TS(5)`.
3. B = order 2, but `created_at TS(5)`.
4. C = order 3, but `created_at TS(5)`.
5. E = order 4, but `created_at TS(1)`.
6. bump(A).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id, E.id]`.

### TRO-LH-03 — the list query orders by created_at DESC, then id DESC
- **Rules:** `list_for_hub` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1.
2. `db.expunge_all()`.

**When**
- Statement recorder on: `result = dao.list_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. statement: `"created_at DESC" in order_part`.
2. statement: `order_part.rstrip().endswith("transfer_orders.id DESC")`.
3. statement: `order_part.index("created_at DESC") < order_part.index("transfer_orders.id DESC")`.

### TRO-LH-04 — skip and limit cut the sorted list
- **Rules:** `list_for_hub` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 … O5 = order 1, order 2, order 3, order 4, order 5.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, skip=1, limit=2, **F())`.

**Then**
1. returns: `ids(result) == [O4.id, O3.id]`.

### TRO-LH-05 — the default page is skip 0 and 50 rows
- **Rules:** `list_for_hub` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for n in range(1, 52):` add order n (51 orders, flushed once after the loop); O1 = order 1, O51 = order 51.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `len(result) == 50`.
2. returns: `result[0].id == O51.id`.
3. returns: `O1.id not in idset(result)`.

### TRO-LH-06 — skip past the end returns []
- **Rules:** `list_for_hub` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2.
3. C = order 3.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, skip=3, limit=10, **F())`.

**Then**
1. returns: `result == []`.

### TRO-LH-07 — limit=1000 returns every row
- **Rules:** `list_for_hub` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2.
3. C = order 3.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, skip=0, limit=1000, **F())`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.

### TRO-LH-08 — filters apply before paging: hidden newer rows do not take a page slot
- **Rules:** `list_for_hub` R3, `_apply_transfer_order_hub_filters` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2.
3. E = order 3.
4. C = order 9, but completed.
5. X2 = order 8 of W2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, skip=1, limit=1, **F())`.

**Then**
1. returns: `ids(result) == [B.id]`.

### TRO-LH-09 — current_status comes loaded
- **Rules:** `list_for_hub` Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `current_status_id SP.id`.
2. `db.expunge_all()`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `loaded(result[0], "current_status")`.
2. returns: `result[0].current_status.name == "Planned"`.

### TRO-LH-10 — an unknown filter keyword raises TypeError
- **Rules:** `list_for_hub` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- `dao.list_for_hub(db, workspace_id=W1.id, colour="red", **F())`.

**Then**
1. raises: `TypeError`.
2. count: `total()` equals its value before the call.

### TRO-LH-11 — writes nothing and takes no lock: a pending order stays pending, an unflushed edit stays unflushed
- **Rules:** `list_for_hub` Side effects; HR-10 note
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = order 1.
2. `E.destination_location_id = MB.id` (not flushed).
3. P = order 5, added with `db.add(P)` and not flushed.

**When**
- Statement recorder on: `result = dao.list_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `ids(result) == [E.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `E in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `"FOR UPDATE" not in sql`.

### TRO-LH-12 — a workspace with no orders gives []
- **Rules:** `list_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X0 = order 1 of W0.
2. X2 = order 2 of W2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result == []`.

## `TransferOrderDAO.count_for_hub`

### TRO-CH-01 — counts W1's open orders only, as an int
- **Rules:** `count_for_hub` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. X0 = order 9 of W0.
2. A = order 1.
3. B = order 2.
4. C = order 3, but completed.
5. X2 = order 8 of W2.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `type(result) is int`.
2. returns: `result == 2`.

### TRO-CH-02 — nothing matching gives 0, not None
- **Rules:** `count_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X0 = order 1 of W0.
2. X2 = order 2 of W2.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result == 0`.
2. returns: `type(result) is int`.

### TRO-CH-03 — the count ignores the list's page size
- **Rules:** `count_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for n in range(1, 56):` add order n (55 orders, flushed once after the loop).

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result == 55`.

### TRO-CH-04 — exclude_complete=False counts completed orders too
- **Rules:** `count_for_hub` R1, `_apply_transfer_order_hub_filters` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2.
3. C = order 3, but completed.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, exclude_complete=False, **F())`.

**Then**
1. returns: `result == 3`.

### TRO-CH-05 — an unknown filter keyword raises TypeError
- **Rules:** `count_for_hub` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- `dao.count_for_hub(db, workspace_id=W1.id, colour="red", **F())`.

**Then**
1. raises: `TypeError`.
2. count: `total()` equals its value before the call.

### TRO-CH-06 — writes nothing and takes no lock
- **Rules:** `count_for_hub` Side effects; HR-10 note
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- Statement recorder on: `result = dao.count_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result == 1`.
2. statement: `written == []`.
3. statement: `all("FOR UPDATE" not in s for s in selects)`.

## `TransferOrderDAO.list_recent_for_hub`

### TRO-RC-01 — the default is the 10 most recently edited open orders of W1
- **Rules:** `list_recent_for_hub` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 … O12 = order 1 … order 12, inserted in that order, with `updated_at` TS(53), TS(61), TS(57), TS(51), TS(62), TS(55), TS(59), TS(52), TS(60), TS(56), TS(54), TS(58) respectively.
2. C = order 13, but completed, `updated_at TS(99)`.
3. X2 = order 14 of W2, but `updated_at TS(98)`.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `ids(result) == [O5.id, O2.id, O9.id, O7.id, O12.id, O3.id, O10.id, O6.id, O11.id, O1.id]`.

### TRO-RC-02 — limit=3 keeps the three most recent edits
- **Rules:** `list_recent_for_hub` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `updated_at TS(52)`.
2. B = order 2, but `updated_at TS(55)`.
3. C = order 3, but `updated_at TS(51)`.
4. E = order 4, but `updated_at TS(54)`.
5. G = order 5, but `updated_at TS(53)`.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, limit=3, **F())`.

**Then**
1. returns: `ids(result) == [B.id, E.id, G.id]`.

### TRO-RC-03 — limit=1000 returns every row
- **Rules:** `list_recent_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `updated_at TS(52)`.
2. B = order 2, but `updated_at TS(53)`.
3. C = order 3, but `updated_at TS(51)`.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, limit=1000, **F())`.

**Then**
1. returns: `ids(result) == [B.id, A.id, C.id]`.

### TRO-RC-04 — current_status comes loaded
- **Rules:** `list_recent_for_hub` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `current_status_id SP.id`.
2. `db.expunge_all()`.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `loaded(result[0], "current_status")`.
2. returns: `result[0].current_status.name == "Planned"`.

### TRO-RC-05 — an order edited later comes before an old never-edited one
- **Rules:** `list_recent_for_hub` R2 [BUG-2655]
- **Kind:** bug
- **Expect:** xfail BUG-2655
- **Fails today on:** Then 1 (today the never-edited A comes first)

**Given**
1. A = order 1.
2. B = order 2, but `updated_at TS(30)`.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### TRO-RC-06 — a never-edited order sorts by its created_at among edited ones
- **Rules:** `list_recent_for_hub` R2 [BUG-2655]
- **Kind:** bug
- **Expect:** xfail BUG-2655
- **Fails today on:** Then 1 (today A comes first)

**Given**
1. C = order 1, but `updated_at TS(4)`.
2. B = order 2, but `updated_at TS(8)`.
3. A = order 6.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `ids(result) == [B.id, A.id, C.id]`.

### TRO-RC-07 — never-edited orders with equal created_at come by id descending
- **Rules:** `list_recent_for_hub` R2 [BUG-2656]
- **Kind:** bug
- **Expect:** xfail BUG-2656 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no tie-break; physical order after the bump)

**Given**
1. seqscan.
2. A = order 1, but `created_at TS(5)`.
3. B = order 2, but `created_at TS(5)`.
4. C = order 3, but `created_at TS(5)`.
5. bump(A).

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.

### TRO-RC-08 — orders edited at the same moment come by id descending
- **Rules:** `list_recent_for_hub` R2 [BUG-2656]
- **Kind:** bug
- **Expect:** xfail BUG-2656 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no tie-break; physical order after the bump)

**Given**
1. seqscan.
2. A = order 1, but `created_at TS(5)`, `updated_at TS(9)`.
3. B = order 2, but `created_at TS(5)`, `updated_at TS(9)`.
4. C = order 3, but `created_at TS(5)`, `updated_at TS(9)`.
5. bump(A).

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.

### TRO-RC-09 — the recent query ends its ORDER BY with id DESC
- **Rules:** `list_recent_for_hub` R2 [BUG-2656]
- **Kind:** bug
- **Expect:** xfail BUG-2656
- **Fails today on:** Then 1 (today the order ends with `created_at DESC`)

**Given**
1. A = order 1.
2. `db.expunge_all()`.

**When**
- Statement recorder on: `result = dao.list_recent_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. statement: `order_part.rstrip().endswith("transfer_orders.id DESC")`.

### TRO-RC-10 — an unknown filter keyword raises TypeError
- **Rules:** `list_recent_for_hub` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- `dao.list_recent_for_hub(db, workspace_id=W1.id, colour="red", **F())`.

**Then**
1. raises: `TypeError`.
2. count: `total()` equals its value before the call.

### TRO-RC-11 — writes nothing and takes no lock
- **Rules:** `list_recent_for_hub` Side effects; HR-10 note
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- Statement recorder on: `result = dao.list_recent_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `written == []`.
3. statement: `all("FOR UPDATE" not in s for s in selects)`.

## `TransferOrderDAO.count_machine_involved_for_hub`

### TRO-MI-01 — counts orders with a machine at either end, once each, in W1's open orders
- **Rules:** `count_machine_involved_for_hub` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. X0 = order 9 of W0.
2. A = order 1, but `source_location_type "machine"`, `source_location_id MB.id`, `destination_location_type "storage"`, `destination_location_id F1.id`.
3. B = order 2.
4. C = order 3, but `source_location_type "machine"`, `source_location_id M1.id`, `destination_location_id MB.id`.
5. E = order 4, but `destination_location_type "project"`, `destination_location_id C1.id`.
6. G = order 5, but completed.
7. X2 = order 8 of W2.

**When**
- `result = dao.count_machine_involved_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `type(result) is int`.
2. returns: `result == 3`.

### TRO-MI-02 — the type is compared exactly ("Machine", "machines" do not count)
- **Rules:** `count_machine_involved_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_type "Machine"`.
2. B = order 2, but `destination_location_type "machines"`.

**When**
- `result = dao.count_machine_involved_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result == 0`.

### TRO-MI-03 — the machine id is not checked
- **Rules:** `count_machine_involved_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_id MISSING`.

**When**
- `result = dao.count_machine_involved_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result == 1`.

### TRO-MI-04 — no machine order gives 0
- **Rules:** `count_machine_involved_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_type "storage"`, `destination_location_id FB.id`.

**When**
- `result = dao.count_machine_involved_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result == 0`.
2. returns: `type(result) is int`.

### TRO-MI-05 — exclude_complete=False counts a completed machine order
- **Rules:** `count_machine_involved_for_hub` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but completed.
2. B = order 2.

**When**
- `result = dao.count_machine_involved_for_hub(db, workspace_id=W1.id, exclude_complete=False, **F())`.

**Then**
1. returns: `result == 2`.

### TRO-MI-06 — the search filter narrows the count
- **Rules:** `count_machine_involved_for_hub` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 7.
2. B = order 17.

**When**
- `result = dao.count_machine_involved_for_hub(db, workspace_id=W1.id, **F(search="6-007"))`.

**Then**
1. returns: `result == 1`.

### TRO-MI-07 — an unknown filter keyword raises TypeError
- **Rules:** `count_machine_involved_for_hub` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- `dao.count_machine_involved_for_hub(db, workspace_id=W1.id, colour="red", **F())`.

**Then**
1. raises: `TypeError`.
2. count: `total()` equals its value before the call.

### TRO-MI-08 — writes nothing and takes no lock
- **Rules:** `count_machine_involved_for_hub` Side effects; HR-10 note
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- Statement recorder on: `result = dao.count_machine_involved_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result == 1`.
2. statement: `written == []`.
3. statement: `all("FOR UPDATE" not in s for s in selects)`.

## `TransferOrderDAO.get_pending_highlights_for_hub`

*In this section a route-defined order is always planned (it has a line), a draft has `destination_location_id 0`, and no card checks `status_name`. The stage rule itself (BUG-2659: a route and a line make Planned) has its own section, cards `TRO-OQ39-*`.*

### TRO-PH-01 — returns the five keys and entries of id, number, label and created_at
- **Rules:** `get_pending_highlights_for_hub` Returns, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = order 1, planned.
2. R = order 2, but draft.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `set(result.keys()) == {"pending_planned_count", "pending_planned", "awaiting_setup_count", "awaiting_setup", "oldest_drafts"}`.
2. returns: `result["pending_planned_count"] == 1`.
3. returns: `result["awaiting_setup_count"] == 1`.
4. returns: `hids(result["pending_planned"]) == [P.id]`.
5. returns: `hids(result["awaiting_setup"]) == [R.id]`.
6. returns: `hids(result["oldest_drafts"]) == [R.id]`.
7. returns: `set(result["pending_planned"][0].keys()) == {"id", "order_number", "status_name", "created_at"}`.
8. returns: `result["pending_planned"][0]["order_number"] == GN("TR-2026-001")`.
9. returns: `result["pending_planned"][0]["created_at"] == TS(1)`.
10. returns: `result["oldest_drafts"][0]["order_number"] == GN("TR-2026-002")`.

### TRO-PH-02 — completed orders are left out even with exclude_complete=False
- **Rules:** `get_pending_highlights_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, planned.
2. B = order 2, but completed; planned.
3. C = order 3, but draft, completed.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, exclude_complete=False, **F())`.

**Then**
1. returns: `result["pending_planned_count"] == 1`.
2. returns: `hids(result["pending_planned"]) == [A.id]`.
3. returns: `result["awaiting_setup_count"] == 0`.
4. returns: `result["oldest_drafts"] == []`.

### TRO-PH-03 — the hub filters and the workspace apply
- **Rules:** `get_pending_highlights_for_hub` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order 9 of W0, but `source_location_type "damaged"`; planned.
2. A = order 1, but `source_location_type "damaged"`; planned.
3. B = order 2, planned.
4. X2 = order 8 of W2, but `source_location_type "damaged"`, draft.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F(source_location_type="damaged"))`.

**Then**
1. returns: `result["pending_planned_count"] == 1`.
2. returns: `hids(result["pending_planned"]) == [A.id]`.
3. returns: `result["awaiting_setup_count"] == 0`.

### TRO-PH-04 — pending_planned is the 3 most recently edited planned orders
- **Rules:** `get_pending_highlights_for_hub` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 … O5 = order 1 … order 5, each planned, inserted in that order, with `updated_at` TS(52), TS(55), TS(51), TS(54), TS(53) respectively.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["pending_planned_count"] == 5`.
2. returns: `hids(result["pending_planned"]) == [O2.id, O4.id, O5.id]`.

### TRO-PH-05 — awaiting_setup is the 3 most recently edited drafts
- **Rules:** `get_pending_highlights_for_hub` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 … O4 = order 1 … order 4, each draft, inserted in that order, with `updated_at` TS(53), TS(51), TS(54), TS(52) respectively.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["awaiting_setup_count"] == 4`.
2. returns: `hids(result["awaiting_setup"]) == [O3.id, O1.id, O4.id]`.

### TRO-PH-06 — oldest_drafts is the 5 oldest drafts, oldest first, planned orders left out
- **Rules:** `get_pending_highlights_for_hub` R5, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = order 7, but `created_at TS(0)`; planned.
2. O1 … O6 = order 1 … order 6, each draft, inserted in that order, with `created_at` TS(6), TS(2), TS(9), TS(1), TS(5), TS(3) respectively.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["awaiting_setup_count"] == 6`.
2. returns: `hids(result["oldest_drafts"]) == [O4.id, O2.id, O6.id, O5.id, O1.id]`.

### TRO-PH-07 — nothing matching gives zero counts and empty lists
- **Rules:** `get_pending_highlights_for_hub` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X0 = order 1 of W0, planned.
2. X2 = order 2 of W2, but draft.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result == {"pending_planned_count": 0, "pending_planned": [], "awaiting_setup_count": 0, "awaiting_setup": [], "oldest_drafts": []}`.

### TRO-PH-08 — pending_planned sorts a never-edited order by its created_at
- **Rules:** `get_pending_highlights_for_hub` R4 [BUG-2655]
- **Kind:** bug
- **Expect:** xfail BUG-2655
- **Fails today on:** Then 2 (today the never-edited A comes first)

**Given**
1. C = order 1, but `updated_at TS(4)`; planned.
2. B = order 2, but `updated_at TS(8)`; planned.
3. A = order 6, planned.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["pending_planned_count"] == 3`.
2. returns: `hids(result["pending_planned"]) == [B.id, A.id, C.id]`.

### TRO-PH-09 — awaiting_setup sorts a never-edited draft by its created_at
- **Rules:** `get_pending_highlights_for_hub` R4 [BUG-2655]
- **Kind:** bug
- **Expect:** xfail BUG-2655
- **Fails today on:** Then 2 (today the never-edited A comes first)

**Given**
1. C = order 1, but draft, `updated_at TS(4)`.
2. B = order 2, but draft, `updated_at TS(8)`.
3. A = order 6, but draft.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["awaiting_setup_count"] == 3`.
2. returns: `hids(result["awaiting_setup"]) == [B.id, A.id, C.id]`.

### TRO-PH-10 — tied planned orders come by id descending
- **Rules:** `get_pending_highlights_for_hub` R4 [BUG-2656]
- **Kind:** bug
- **Expect:** xfail BUG-2656 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no tie-break; physical order after the bump)

**Given**
1. seqscan.
2. A = order 1, but `created_at TS(5)`, `updated_at TS(9)`; planned.
3. B = order 2, but `created_at TS(5)`, `updated_at TS(9)`; planned.
4. C = order 3, but `created_at TS(5)`, `updated_at TS(9)`; planned.
5. bump(A).

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `hids(result["pending_planned"]) == [C.id, B.id, A.id]`.

### TRO-PH-11 — oldest drafts with equal created_at come by id ascending
- **Rules:** `get_pending_highlights_for_hub` R6 [BUG-2656]
- **Kind:** bug
- **Expect:** xfail BUG-2656 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no tie-break; physical order after the bump)

**Given**
1. seqscan.
2. A = order 1, but draft, `created_at TS(5)`.
3. B = order 2, but draft, `created_at TS(5)`.
4. C = order 3, but draft, `created_at TS(5)`.
5. bump(A).

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `hids(result["oldest_drafts"]) == [A.id, B.id, C.id]`.

### TRO-PH-12 — every ordered highlight query ends with an id tie-break
- **Rules:** `get_pending_highlights_for_hub` R4, R6 [BUG-2656]
- **Kind:** bug
- **Expect:** xfail BUG-2656
- **Author:** claude
- **Fails today on:** Then 2 (today no ordered query ends with `id`)

**Given**
1. A = order 1, planned.
2. R = order 2, but draft.
3. `db.expunge_all()`.

**When**
- Statement recorder on: `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. statement: `ordered` = the recorded SELECTs from `transfer_orders` that contain `ORDER BY`; `len(ordered) >= 1`.
2. statement: every one of them has an order part (text after `ORDER BY`, before `LIMIT`) whose stripped text ends with `"transfer_orders.id DESC"`, `"transfer_orders.id ASC"` or `"transfer_orders.id"`.

### TRO-PH-13 — an unknown filter keyword raises TypeError
- **Rules:** `get_pending_highlights_for_hub` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = order 1, planned.

**When**
- `dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, colour="red", **F())`.

**Then**
1. raises: `TypeError`.
2. count: `total()` equals its value before the call.

### TRO-PH-14 — writes nothing and takes no lock in any of its queries
- **Rules:** `get_pending_highlights_for_hub` Side effects; HR-10 note
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = order 1, planned.
2. R = order 2, but draft.

**When**
- Statement recorder on: `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["pending_planned_count"] + result["awaiting_setup_count"] == 2`.
2. statement: `len(selects) >= 1`.
3. statement: `written == []`.
4. statement: `all("FOR UPDATE" not in s for s in selects)`.

## `TransferOrderDAO.aggregate_hub_stats`

### TRO-AS-01 — by default completed orders are dropped: (4, 4, 0)
- **Rules:** `aggregate_hub_stats` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2.
3. C = order 3.
4. E = order 4.
5. G = order 5, but completed.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `isinstance(result, tuple)`.
2. returns: `result == (4, 4, 0)`.
3. returns: `all(type(v) is int for v in result)`.

### TRO-AS-02 — exclude_complete=False splits open and completed: (5, 4, 1)
- **Rules:** `aggregate_hub_stats` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2.
3. C = order 3.
4. E = order 4.
5. G = order 5, but completed.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, **F())`.

**Then**
1. returns: `result == (5, 4, 1)`.

### TRO-AS-03 — no orders gives (0, 0, 0)
- **Rules:** `aggregate_hub_stats` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X0 = order 1 of W0.
2. X2 = order 2 of W2, but completed.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, **F())`.

**Then**
1. returns: `result == (0, 0, 0)`.
2. returns: `all(type(v) is int for v in result)`.

### TRO-AS-04 — only completed orders: (2, 0, 2)
- **Rules:** `aggregate_hub_stats` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but completed.
2. B = order 2, but completed.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, **F())`.

**Then**
1. returns: `result == (2, 0, 2)`.

### TRO-AS-05 — orders of W0 and W2 are not counted
- **Rules:** `aggregate_hub_stats` R1, `_apply_transfer_order_hub_filters` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0a = order 8 of W0.
2. X0b = order 9 of W0, but completed.
3. A = order 1.
4. X2a = order 7 of W2.
5. X2b = order 6 of W2, but completed.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, **F())`.

**Then**
1. returns: `result == (1, 1, 0)`.

### TRO-AS-06 — the stored status plays no part
- **Rules:** `aggregate_hub_stats` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2, but `current_status_id SC.id`.
3. C = order 3, but completed.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, **F())`.

**Then**
1. returns: `result == (3, 2, 1)`.

### TRO-AS-07 — the hub filters apply
- **Rules:** `aggregate_hub_stats` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`.
2. B = order 2.
3. C = order 3, but `source_location_id FB.id`, completed.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, **F(search="bravo"))`.

**Then**
1. returns: `result == (2, 1, 1)`.

### TRO-AS-08 — an unknown filter keyword raises TypeError
- **Rules:** `aggregate_hub_stats` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- `dao.aggregate_hub_stats(db, workspace_id=W1.id, colour="red", **F())`.

**Then**
1. raises: `TypeError`.
2. count: `total()` equals its value before the call.

### TRO-AS-09 — writes nothing and takes no lock
- **Rules:** `aggregate_hub_stats` Side effects; HR-10 note
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- Statement recorder on: `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result == (1, 1, 0)`.
2. statement: `written == []`.
3. statement: `all("FOR UPDATE" not in s for s in selects)`.

## `TransferOrderDAO.list_touching_location_incomplete`

### TRO-TL-01 — orders with the location at either end, newest first, each once
- **Rules:** `list_touching_location_incomplete` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`.
2. B = order 3, but `destination_location_type "storage"`, `destination_location_id FB.id`.
3. C = order 2, but `source_location_id FB.id`, `destination_location_type "storage"`, `destination_location_id FB.id`.
4. E = order 4.

**When**
- `result = dao.list_touching_location_incomplete(db, workspace_id=W1.id, location_type="storage", location_id=FB.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, C.id, A.id]`.

### TRO-TL-02 — completed orders are left out
- **Rules:** `list_touching_location_incomplete` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`, completed.
2. B = order 2, but `source_location_id FB.id`.

**When**
- `result = dao.list_touching_location_incomplete(db, workspace_id=W1.id, location_type="storage", location_id=FB.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### TRO-TL-03 — orders of W0 and W2 at the same type and id are left out
- **Rules:** `list_touching_location_incomplete` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order 9 of W0, but `source_location_id MISSING`.
2. A = order 1, but `source_location_id MISSING`.
3. X2 = order 8 of W2, but `destination_location_type "storage"`, `destination_location_id MISSING`.

**When**
- `result = dao.list_touching_location_incomplete(db, workspace_id=W1.id, location_type="storage", location_id=MISSING)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-TL-04 — the type is compared exactly ("Storage" finds nothing)
- **Rules:** `list_touching_location_incomplete` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`.

**When**
- `result = dao.list_touching_location_incomplete(db, workspace_id=W1.id, location_type="Storage", location_id=FB.id)`.

**Then**
1. returns: `result == []`.

### TRO-TL-05 — the same id under another type is not this location
- **Rules:** `list_touching_location_incomplete` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`.

**When**
- `result = dao.list_touching_location_incomplete(db, workspace_id=W1.id, location_type="damaged", location_id=FB.id)`.

**Then**
1. returns: `result == []`.

### TRO-TL-06 — current_status comes loaded
- **Rules:** `list_touching_location_incomplete` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `current_status_id SP.id`.
2. `db.expunge_all()`.

**When**
- `result = dao.list_touching_location_incomplete(db, workspace_id=W1.id, location_type="machine", location_id=M1.id)`.

**Then**
1. returns: `loaded(result[0], "current_status")`.
2. returns: `result[0].current_status.name == "Planned"`.

### TRO-TL-07 — there is no limit
- **Rules:** `list_touching_location_incomplete` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for n in range(1, 56):` add order n (55 orders, flushed once after the loop).

**When**
- `result = dao.list_touching_location_incomplete(db, workspace_id=W1.id, location_type="machine", location_id=M1.id)`.

**Then**
1. returns: `len(result) == 55`.

### TRO-TL-08 — orders with equal created_at come by id descending
- **Rules:** `list_touching_location_incomplete` R3 [BUG-2656]
- **Kind:** bug
- **Expect:** xfail BUG-2656 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no tie-break; physical order after the bump)

**Given**
1. seqscan.
2. A = order 1, but `created_at TS(5)`.
3. B = order 2, but `created_at TS(5)`.
4. C = order 3, but `created_at TS(5)`.
5. bump(A).

**When**
- `result = dao.list_touching_location_incomplete(db, workspace_id=W1.id, location_type="machine", location_id=M1.id)`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.

### TRO-TL-09 — the query ends its ORDER BY with id DESC
- **Rules:** `list_touching_location_incomplete` R3 [BUG-2656]
- **Kind:** bug
- **Expect:** xfail BUG-2656
- **Fails today on:** Then 2 (today the order is `created_at DESC` alone)

**Given**
1. A = order 1.
2. `db.expunge_all()`.

**When**
- Statement recorder on: `result = dao.list_touching_location_incomplete(db, workspace_id=W1.id, location_type="machine", location_id=M1.id)`.

**Then**
1. statement: `"created_at DESC" in order_part`.
2. statement: `order_part.rstrip().endswith("transfer_orders.id DESC")`.

### TRO-TL-10 — writes nothing and takes no lock
- **Rules:** `list_touching_location_incomplete` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = order 1.
2. `E.source_location_id = FB.id` (not flushed).
3. P = order 5, added with `db.add(P)` and not flushed.

**When**
- Statement recorder on: `result = dao.list_touching_location_incomplete(db, workspace_id=W1.id, location_type="machine", location_id=M1.id)`.

**Then**
1. returns: `ids(result) == [E.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `E in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql`.

### TRO-TL-11 — nothing matching gives []
- **Rules:** `list_touching_location_incomplete` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- `result = dao.list_touching_location_incomplete(db, workspace_id=W1.id, location_type="machine", location_id=MB.id)`.

**Then**
1. returns: `result == []`.

## `TransferOrderDAO.list_inbound_to_storage_incomplete`

### TRO-IB-01 — open orders into F1's storage, newest first
- **Rules:** `list_inbound_to_storage_incomplete` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`, `destination_location_type "storage"`, `destination_location_id F1.id`.
2. B = order 3, but `source_location_id FB.id`, `destination_location_type "storage"`, `destination_location_id F1.id`.
3. C = order 2, but `source_location_type "machine"`, `source_location_id MB.id`, `destination_location_type "storage"`, `destination_location_id F1.id`.
4. E = order 4.

**When**
- `result = dao.list_inbound_to_storage_incomplete(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, C.id, A.id]`.

### TRO-IB-02 — a damaged destination of the factory is left out
- **Rules:** `list_inbound_to_storage_incomplete` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`, `destination_location_type "damaged"`, `destination_location_id F1.id`.

**When**
- `result = dao.list_inbound_to_storage_incomplete(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `result == []`.

### TRO-IB-03 — the factory's storage as source is left out
- **Rules:** `list_inbound_to_storage_incomplete` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- `result = dao.list_inbound_to_storage_incomplete(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `result == []`.

### TRO-IB-04 — completed orders are left out
- **Rules:** `list_inbound_to_storage_incomplete` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`, `destination_location_type "storage"`, `destination_location_id F1.id`, completed.
2. B = order 2, but `source_location_id FB.id`, `destination_location_type "storage"`, `destination_location_id F1.id`.

**When**
- `result = dao.list_inbound_to_storage_incomplete(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### TRO-IB-05 — another factory's storage is left out
- **Rules:** `list_inbound_to_storage_incomplete` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_type "storage"`, `destination_location_id FB.id`.

**When**
- `result = dao.list_inbound_to_storage_incomplete(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `result == []`.

### TRO-IB-06 — orders of W0 and W2 into the same storage id are left out
- **Rules:** `list_inbound_to_storage_incomplete` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order 9 of W0, but `destination_location_type "storage"`, `destination_location_id MISSING`.
2. A = order 1, but `destination_location_type "storage"`, `destination_location_id MISSING`.
3. X2 = order 8 of W2, but `destination_location_type "storage"`, `destination_location_id MISSING`.

**When**
- `result = dao.list_inbound_to_storage_incomplete(db, workspace_id=W1.id, factory_id=MISSING)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-IB-07 — the type is compared exactly ("Storage" is left out)
- **Rules:** `list_inbound_to_storage_incomplete` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`, `destination_location_type "Storage"`, `destination_location_id F1.id`.

**When**
- `result = dao.list_inbound_to_storage_incomplete(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `result == []`.

### TRO-IB-08 — the stored status does not matter
- **Rules:** `list_inbound_to_storage_incomplete` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id FB.id`, `destination_location_type "storage"`, `destination_location_id F1.id`, `current_status_id SC.id`.
2. B = order 2, but `source_location_id FB.id`, `destination_location_type "storage"`, `destination_location_id F1.id`, `current_status_id SP.id`.

**When**
- `result = dao.list_inbound_to_storage_incomplete(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### TRO-IB-09 — current_status comes loaded, and there is no limit
- **Rules:** `list_inbound_to_storage_incomplete` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for n in range(1, 56):` add order n, but `source_location_id FB.id`, `destination_location_type "storage"`, `destination_location_id F1.id` (55 orders, flushed once after the loop).
2. `db.expunge_all()`.

**When**
- `result = dao.list_inbound_to_storage_incomplete(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `loaded(result[0], "current_status")`.
2. returns: `len(result) == 55`.

### TRO-IB-10 — orders with equal created_at come by id descending
- **Rules:** `list_inbound_to_storage_incomplete` R3 [BUG-2656]
- **Kind:** bug
- **Expect:** xfail BUG-2656 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no tie-break; physical order after the bump)

**Given**
1. seqscan.
2. A = order 1, but `source_location_id FB.id`, `destination_location_type "storage"`, `destination_location_id F1.id`, `created_at TS(5)`.
3. B = order 2, but `source_location_id FB.id`, `destination_location_type "storage"`, `destination_location_id F1.id`, `created_at TS(5)`.
4. C = order 3, but `source_location_id FB.id`, `destination_location_type "storage"`, `destination_location_id F1.id`, `created_at TS(5)`.
5. bump(A).

**When**
- `result = dao.list_inbound_to_storage_incomplete(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.

### TRO-IB-11 — the query ends its ORDER BY with id DESC
- **Rules:** `list_inbound_to_storage_incomplete` R3 [BUG-2656]
- **Kind:** bug
- **Expect:** xfail BUG-2656
- **Fails today on:** Then 2 (today the order is `created_at DESC` alone)

**Given**
1. A = order 1, but `source_location_id FB.id`, `destination_location_type "storage"`, `destination_location_id F1.id`.
2. `db.expunge_all()`.

**When**
- Statement recorder on: `result = dao.list_inbound_to_storage_incomplete(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. statement: `"created_at DESC" in order_part`.
2. statement: `order_part.rstrip().endswith("transfer_orders.id DESC")`.

### TRO-IB-12 — writes nothing and takes no lock
- **Rules:** `list_inbound_to_storage_incomplete` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E = order 1, but `source_location_id FB.id`, `destination_location_type "storage"`, `destination_location_id F1.id`.
2. `E.source_location_id = MISSING` (not flushed).
3. P = order 5, but `destination_location_type "storage"`, `destination_location_id F1.id`; added with `db.add(P)` and not flushed.

**When**
- Statement recorder on: `result = dao.list_inbound_to_storage_incomplete(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `ids(result) == [E.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `E in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql`.

## `TransferOrderDAO.get_by_id_and_workspace`

### TRO-GI-01 — returns the asked order, with current_status loaded
- **Rules:** `TransferOrderDAO.get_by_id_and_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2, but `current_status_id SP.id`.
3. C = order 3.
4. `bid = B.id`, then `db.expunge_all()`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=bid, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, TransferOrder)`.
2. returns: `loaded(result, "current_status")`.
3. returns: `result.id == bid`.
4. returns: `result.current_status.name == "Planned"`.

### TRO-GI-02 — an order of the earlier workspace W0 is None for W1
- **Rules:** `TransferOrderDAO.get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order 1 of W0.
2. A = order 2.

**When**
- `result = dao.get_by_id_and_workspace(db, id=X0.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### TRO-GI-03 — an order of the later workspace W2 is None for W1
- **Rules:** `TransferOrderDAO.get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = order 1.
2. X2 = order 2 of W2.

**When**
- `result = dao.get_by_id_and_workspace(db, id=X2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### TRO-GI-04 — asked for W2, its own order is returned
- **Rules:** `TransferOrderDAO.get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = order 1.
2. X2 = order 2 of W2.

**When**
- `result = dao.get_by_id_and_workspace(db, id=X2.id, workspace_id=W2.id)`.

**Then**
1. returns: `result.id == X2.id`.

### TRO-GI-05 — an unknown id is None
- **Rules:** `TransferOrderDAO.get_by_id_and_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### TRO-GI-06 — a completed order is still returned
- **Rules:** `TransferOrderDAO.get_by_id_and_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but completed.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.completed_at == DONE`.

### TRO-GI-07 — no row lock is taken and nothing is written
- **Rules:** `TransferOrderDAO.get_by_id_and_workspace` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = order 1.
2. `aid = A.id`, then `db.expunge_all()`.

**When**
- Statement recorder on: `result = dao.get_by_id_and_workspace(db, id=aid, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == aid`.
2. statement: `all("FOR UPDATE" not in s for s in selects)`.
3. statement: `written == []`.

## `TransferOrderDAO.get_next_number`

*Every card starts with numlock and stores exact numbers through num(W, s). Every call to `get_next_number` runs under **clock(NOW31, NOW31)** unless the card gives its own clock line, so the current year in these cards is 2031, never the real one (a hard-coded or real-clock year fails).*

### TRO-NN-01 — no number yet gives TR-2031-001
- **Rules:** `get_next_number` R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. numlock.
2. W1 has no order.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, str)`.
2. returns: `result == "TR-2031-001"`.

### TRO-NN-02 — after -001 … -005 comes -006
- **Rules:** `get_next_number` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. numlock.
2. `for k in range(1, 6):` num(W1, f"TR-2031-{k:03d}") with `created_at TS(k)`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-006"`.

### TRO-NN-03 — the highest number decides, not the count (-007 alone gives -008)
- **Rules:** `get_next_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. numlock.
2. num(W1, "TR-2031-007").

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-008"`.

### TRO-NN-04 — after -009 comes -010
- **Rules:** `get_next_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. numlock.
2. num(W1, "TR-2031-009").

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-010"`.

### TRO-NN-05 — after -099 comes -100
- **Rules:** `get_next_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. numlock.
2. num(W1, "TR-2031-099").

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-100"`.

### TRO-NN-06 — after -998 comes -999
- **Rules:** `get_next_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. numlock.
2. num(W1, "TR-2031-998").

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-999"`.

### TRO-NN-07 — after -999 comes -1000, not cut to three digits
- **Rules:** `get_next_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. numlock.
2. num(W1, "TR-2031-999").

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-1000"`.

### TRO-NN-08 — with -999 and -1000 stored the next is -1001
- **Rules:** `get_next_number` R3 [BUG-2651]
- **Kind:** bug
- **Expect:** xfail BUG-2651
- **Fails today on:** Then 1 (today `-999` sorts highest as text and the result is `-1000` again)

**Given**
1. numlock.
2. num(W1, "TR-2031-999"), `created_at TS(1)`.
3. num(W1, "TR-2031-1000"), `created_at TS(2)`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-1001"`.

### TRO-NN-09 — with -1005 and -999 stored the next is -1006
- **Rules:** `get_next_number` R3 [BUG-2651]
- **Kind:** bug
- **Expect:** xfail BUG-2651
- **Fails today on:** Then 1 (today the result is `-1000`)

**Given**
1. numlock.
2. num(W1, "TR-2031-1005"), `created_at TS(1)`.
3. num(W1, "TR-2031-999"), `created_at TS(2)`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-1006"`.

### TRO-NN-10 — a non-numeric suffix is ignored beside -005
- **Rules:** `get_next_number` R4 [BUG-2651]
- **Kind:** bug
- **Expect:** xfail BUG-2651
- **Fails today on:** Then 1 (today `-abc` sorts highest as text and the result falls back to `-001`)

**Given**
1. numlock.
2. num(W1, "TR-2031-005"), `created_at TS(1)`.
3. num(W1, "TR-2031-abc"), `created_at TS(2)`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-006"`.

### TRO-NN-11 — a non-numeric suffix alone gives -001
- **Rules:** `get_next_number` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. numlock.
2. num(W1, "TR-2031-abc").

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-001"`.

### TRO-NN-12 — only W1's numbers count, with higher numbers in W0 and W2
- **Rules:** `get_next_number` R2, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. numlock.
2. num(W0, "TR-2031-011"), `created_at TS(1)`.
3. num(W0, "TR-2031-012"), `created_at TS(2)`.
4. num(W1, "TR-2031-010"), `created_at TS(3)`.
5. num(W2, "TR-2031-013"), `created_at TS(4)`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-011"`.

### TRO-NN-13 — asked for W2, only W2's numbers count, with higher ones in W0 and W1
- **Rules:** `get_next_number` R2, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. numlock.
2. num(W0, "TR-2031-008"), `created_at TS(1)`.
3. num(W1, "TR-2031-007"), `created_at TS(2)`.
4. num(W2, "TR-2031-003"), `created_at TS(3)`.

**When**
- `result = dao.get_next_number(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == "TR-2031-004"`.

### TRO-NN-14 — asked for W0, only W0's numbers count, with higher ones in W1 and W2
- **Rules:** `get_next_number` R2, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. numlock.
2. num(W0, "TR-2031-002"), `created_at TS(1)`.
3. num(W1, "TR-2031-005"), `created_at TS(2)`.
4. num(W2, "TR-2031-006"), `created_at TS(3)`.

**When**
- `result = dao.get_next_number(db, workspace_id=W0.id)`.

**Then**
1. returns: `result == "TR-2031-003"`.

### TRO-NN-15 — an empty W1 gets -001 although W2 holds -001 … -003
- **Rules:** `get_next_number` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. numlock.
2. `for k in range(1, 4):` num(W2, f"TR-2031-{k:03d}") with `created_at TS(k)`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-001"`.

### TRO-NN-16 — numbers of the year before and the year after are not counted
- **Rules:** `get_next_number` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. numlock.
2. num(W1, "TR-2030-050"), `created_at TS(1)`.
3. num(W1, "TR-2032-060"), `created_at TS(2)`.
4. num(W1, "TR-2031-004"), `created_at TS(3)`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-005"`.

### TRO-NN-17 — only other years' numbers give -001
- **Rules:** `get_next_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. numlock.
2. num(W1, "TR-2030-050"), `created_at TS(1)`.
3. num(W1, "TR-2032-060"), `created_at TS(2)`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-001"`.

### TRO-NN-18 — a longer year (TR-20311-) is not this year's prefix
- **Rules:** `get_next_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. numlock.
2. num(W1, "TR-20311-009").

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-001"`.

### TRO-NN-19 — the prefix in the middle of a number does not count
- **Rules:** `get_next_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. numlock.
2. num(W1, "XTR-2031-009").

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-001"`.

### TRO-NN-20 — an unknown workspace gets -001
- **Rules:** `get_next_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. numlock.
2. num(W1, "TR-2031-004").

**When**
- `result = dao.get_next_number(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == "TR-2031-001"`.

### TRO-NN-21 — writes nothing: a pending order is not counted and stays pending, an unflushed edit stays unflushed
- **Rules:** `get_next_number` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. numlock.
2. E = num(W1, "TR-2031-002").
3. `E.destination_location_id = MB.id` (not flushed).
4. P = num(W1, "TR-2031-009"), but `created_at TS(2)`; added with `db.add(P)` and not flushed.

**When**
- Statement recorder on: `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-003"`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `E in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.

### TRO-NN-22 — one query, no row lock
- **Rules:** `get_next_number` Side effects; HR-10 note
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. numlock.
2. num(W1, "TR-2031-004").
3. `db.expunge_all()`.

**When**
- Statement recorder on: `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-005"`.
2. statement: `len(selects) == 1`.
3. statement: `"FOR UPDATE" not in sql`.

### TRO-NN-23 — with both clocks in 2033 the number is TR-2033-…, and 2031's numbers do not count
- **Rules:** `get_next_number` R1, R2, R3
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. numlock.
2. num(W1, "TR-2031-004"), `created_at TS(1)`.
3. num(W1, "TR-2033-002"), `created_at TS(2)`.

**When**
- under clock(`datetime(2033, 6, 1, 12, 0)`, `datetime(2033, 6, 1, 12, 0)`): `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2033-003"`.

### TRO-NN-24 — the year is the UTC year when the local clock is already in the next year
- **Rules:** `get_next_number` R1 [BUG-2653]
- **Kind:** bug
- **Expect:** xfail BUG-2653
- **Author:** claude
- **Fails today on:** Then 1 (today the local year 2031 gives `TR-2031-008`)

**Given**
1. numlock.
2. num(W1, "TR-2030-004"), `created_at TS(1)`.
3. num(W1, "TR-2031-007"), `created_at TS(2)`.

**When**
- under clock(`datetime(2031, 1, 1, 2, 0)`, `datetime(2030, 12, 31, 20, 0)`): `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2030-005"`.

### TRO-NN-25 — the year is the UTC year when the local clock is still in the old year
- **Rules:** `get_next_number` R1 [BUG-2653]
- **Kind:** bug
- **Expect:** xfail BUG-2653
- **Author:** claude
- **Fails today on:** Then 1 (today the local year 2030 gives `TR-2030-005`)

**Given**
1. numlock.
2. num(W1, "TR-2030-004"), `created_at TS(1)`.
3. num(W1, "TR-2031-007"), `created_at TS(2)`.

**When**
- under clock(`datetime(2030, 12, 31, 18, 0)`, `datetime(2031, 1, 1, 0, 30)`): `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-008"`.

### TRO-NN-26 — the year follows utcnow(), not the local clock
- **Rules:** `get_next_number` R1 [BUG-2653]
- **Kind:** bug
- **Expect:** xfail BUG-2653
- **Author:** claude
- **Fails today on:** Then 1 (today the unpatched real local year is used, giving `TR-<real year>-001`)

**Given**
1. numlock.
2. num(W1, "TR-2033-004"), `created_at TS(1)`.
3. num(W1, "TR-2031-007"), `created_at TS(2)`.

**When**
- under utconly(`datetime(2033, 6, 1, 12, 0)`) only — no default clock, the stdlib `datetime.datetime` is not patched: `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2033-005"`.

### TRO-NN-27 — W1 can store TR-2031-001 while the later workspace W2 holds it
- **Rules:** `get_next_number` R5 [BUG-2650]
- **Kind:** bug
- **Expect:** xfail BUG-2650
- **Fails today on:** Then 1 (the call raises IntegrityError: 23505 on the global unique index)

**Given**
1. numlock.
2. X2 = num(W2, "TR-2031-001").
3. T = num(W1, "TR-2031-001"), built but not added.

**When**
- `with db.begin_nested(): db.add(T); db.flush()`.

**Then**
1. returns: `T.id is not None`.
2. count: `db.scalar(select(func.count()).select_from(TransferOrder).where(TransferOrder.transfer_number == "TR-2031-001"))` == 2.

### TRO-NN-28 — W1 can store TR-2031-001 while the earlier workspace W0 holds it
- **Rules:** `get_next_number` R5 [BUG-2650]
- **Kind:** bug
- **Expect:** xfail BUG-2650
- **Fails today on:** Then 1 (the call raises IntegrityError: 23505 on the global unique index)

**Given**
1. numlock.
2. X0 = num(W0, "TR-2031-001").
3. T = num(W1, "TR-2031-001"), built but not added.

**When**
- `with db.begin_nested(): db.add(T); db.flush()`.

**Then**
1. returns: `T.id is not None`.
2. count: `db.scalar(select(func.count()).select_from(TransferOrder).where(TransferOrder.transfer_number == "TR-2031-001"))` == 2.

### TRO-NN-29 — the same number twice in one workspace is refused by the database
- **Rules:** `get_next_number` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. numlock.
2. A = num(W1, "TR-2031-001"), `created_at TS(1)`.
3. T = num(W1, "TR-2031-001"), but `created_at TS(2)`; built but not added.

**When**
- `db.add(T); db.flush()`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `db.scalar(select(func.count()).select_from(TransferOrder).where(TransferOrder.workspace_id == W1.id))` == 1.

### TRO-NN-30 — a lowercase prefix (tr-2031-) is not counted
- **Rules:** `get_next_number` R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. numlock.
2. num(W1, "TR-2031-003"), `created_at TS(1)`.
3. num(W1, "tr-2031-009"), `created_at TS(2)`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-004"`.

### TRO-NN-31 — a mixed-case prefix (Tr-2031-) is not counted
- **Rules:** `get_next_number` R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. numlock.
2. num(W1, "TR-2031-003"), `created_at TS(1)`.
3. num(W1, "Tr-2031-009"), `created_at TS(2)`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-004"`.

### TRO-NN-32 — a suffix with an inner dash (TR-2031-0-5) alone is ignored and gives -001
- **Rules:** `get_next_number` R2b, R4 [BUG-2651]
- **Kind:** bug
- **Expect:** xfail BUG-2651
- **Fails today on:** Then 1 (today the text after the last dash, `5`, is read and the result is `TR-2031-006`)

**Given**
1. numlock.
2. num(W1, "TR-2031-0-5").

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-001"`.

### TRO-NN-33 — beside TR-2031-0-5, a higher plain number still decides (-900 gives -901)
- **Rules:** `get_next_number` R2b, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. numlock.
2. num(W1, "TR-2031-0-5"), `created_at TS(1)`.
3. num(W1, "TR-2031-900"), `created_at TS(2)`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "TR-2031-901"`.

## `TransferOrderItemDAO.get_by_order`

### TRO-IO-01 — returns the order's lines by line_number, with ids not in that order
- **Rules:** `TransferOrderItemDAO.get_by_order` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = order 1.
2. L2 = line(T, 2).
3. L1 = line(T, 1).
4. L3 = line(T, 3).

**When**
- `result = idao.get_by_order(db, transfer_order_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result[0], TransferOrderItem)`.
2. returns: `ids(result) == [L1.id, L2.id, L3.id]`.

### TRO-IO-02 — lines of the orders just below and above are left out
- **Rules:** `TransferOrderItemDAO.get_by_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T0 = order 1.
2. T = order 2.
3. T3 = order 3.
4. K0 = line(T0, 1).
5. K = line(T, 1).
6. K3 = line(T3, 1).

**When**
- `result = idao.get_by_order(db, transfer_order_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [K.id]`.

### TRO-IO-03 — asked for the later workspace W2, W1's lines are not returned
- **Rules:** `TransferOrderItemDAO.get_by_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = order 1.
2. K = line(T, 1).

**When**
- `result = idao.get_by_order(db, transfer_order_id=T.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### TRO-IO-04 — asked for the earlier workspace W0, W1's lines are not returned
- **Rules:** `TransferOrderItemDAO.get_by_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = order 1.
2. K = line(T, 1).

**When**
- `result = idao.get_by_order(db, transfer_order_id=T.id, workspace_id=W0.id)`.

**Then**
1. returns: `result == []`.

### TRO-IO-05 — an unknown order gives []
- **Rules:** `TransferOrderItemDAO.get_by_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = order 1.
2. K = line(T, 1).

**When**
- `result = idao.get_by_order(db, transfer_order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### TRO-IO-06 — there is no limit
- **Rules:** `TransferOrderItemDAO.get_by_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = order 1.
2. `for k in range(1, 56):` line(T, k) (55 lines, flushed once after the loop).

**When**
- `result = idao.get_by_order(db, transfer_order_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 55`.

### TRO-IO-07 — two lines with one number are both returned, before the higher number
- **Rules:** `TransferOrderItemDAO.get_by_order` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = order 1.
2. LX = line(T, 2).
3. LA = line(T, 1).
4. LB = line(T, 1).

**When**
- `result = idao.get_by_order(db, transfer_order_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `{result[0].id, result[1].id} == {LA.id, LB.id}`.
2. returns: `result[2].id == LX.id`.

### TRO-IO-08 — lines with one number come by id ascending
- **Rules:** `TransferOrderItemDAO.get_by_order` R2 [BUG-2657]
- **Kind:** bug
- **Expect:** xfail BUG-2657 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no tie-break; physical order after the bump)

**Given**
1. seqscan.
2. T = order 1.
3. LA = line(T, 1).
4. LB = line(T, 1).
5. LC = line(T, 1).
6. bumpL(LA).

**When**
- `result = idao.get_by_order(db, transfer_order_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [LA.id, LB.id, LC.id]`.

### TRO-IO-09 — the line query ends its ORDER BY with the line id
- **Rules:** `TransferOrderItemDAO.get_by_order` R2 [BUG-2657]
- **Kind:** bug
- **Expect:** xfail BUG-2657
- **Fails today on:** Then 2 (today the order is `line_number` alone)

**Given**
1. T = order 1.
2. K = line(T, 1).
3. `tid = T.id`, then `db.expunge_all()`.

**When**
- Statement recorder on: `result = idao.get_by_order(db, transfer_order_id=tid, workspace_id=W1.id)` (`sql` = the SELECT from `transfer_order_items`).

**Then**
1. statement: `"line_number" in order_part`.
2. statement: `order_part.rstrip().endswith("transfer_order_items.id") or order_part.rstrip().endswith("transfer_order_items.id ASC")`.

### TRO-IO-10 — quantities come back stored half up to two decimals
- **Rules:** Standing decisions (HR-15 note: quantities `Numeric(15, 2)`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = order 1.
2. Q1 = line(T, 1), but `quantity Decimal("1.005")`.
3. Q2 = line(T, 2), but `quantity Decimal("2.125")`.
4. Q3 = line(T, 3), but `quantity Decimal("2.124")`.
5. `db.expire_all()`.

**When**
- `result = idao.get_by_order(db, transfer_order_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `result[0].quantity == Decimal("1.01")`.
2. returns: `result[1].quantity == Decimal("2.13")`.
3. returns: `result[2].quantity == Decimal("2.12")`.

### TRO-IO-11 — writes nothing and takes no lock
- **Rules:** `TransferOrderItemDAO.get_by_order` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = order 1.
2. K = line(T, 1).
3. `K.quantity = Decimal("9.00")` (not flushed).
4. P = line(T, 2), added with `db.add(P)` and not flushed.

**When**
- Statement recorder on: `result = idao.get_by_order(db, transfer_order_id=T.id, workspace_id=W1.id)` (`sql` = the SELECT from `transfer_order_items`).

**Then**
1. returns: `ids(result) == [K.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `K in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql`.

## `TransferOrderItemDAO.get_by_transfer_order_ids`

### TRO-IT-01 — an empty id list gives [] without a query
- **Rules:** `get_by_transfer_order_ids` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = order 1.
2. K = line(T, 1).

**When**
- Statement recorder on: `result = idao.get_by_transfer_order_ids(db, workspace_id=W1.id, transfer_order_ids=[])`.

**Then**
1. returns: `result == []`.
2. statement: `len(selects) == 0`.

### TRO-IT-02 — lines sorted by order id, then line number, with ids in neither order
- **Rules:** `get_by_transfer_order_ids` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2.
3. LB2 = line(B, 2).
4. LA2 = line(A, 2).
5. LB1 = line(B, 1).
6. LA1 = line(A, 1).

**When**
- `result = idao.get_by_transfer_order_ids(db, workspace_id=W1.id, transfer_order_ids=[B.id, A.id])`.

**Then**
1. returns: `ids(result) == [LA1.id, LA2.id, LB1.id, LB2.id]`.

### TRO-IT-03 — lines of orders not in the list are left out, below and above
- **Rules:** `get_by_transfer_order_ids` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T0 = order 1.
2. T = order 2.
3. T3 = order 3.
4. K0 = line(T0, 1).
5. K = line(T, 1).
6. K3 = line(T3, 1).

**When**
- `result = idao.get_by_transfer_order_ids(db, workspace_id=W1.id, transfer_order_ids=[T.id])`.

**Then**
1. returns: `ids(result) == [K.id]`.

### TRO-IT-04 — ids of W0's and W2's orders match nothing in W1
- **Rules:** `get_by_transfer_order_ids` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order 1 of W0.
2. K0 = line(X0, 1).
3. T = order 2.
4. K = line(T, 1).
5. X2 = order 3 of W2.
6. K2 = line(X2, 1).

**When**
- `result = idao.get_by_transfer_order_ids(db, workspace_id=W1.id, transfer_order_ids=[X0.id, X2.id])`.

**Then**
1. returns: `result == []`.

### TRO-IT-05 — asked for W2, W1's order id matches nothing
- **Rules:** `get_by_transfer_order_ids` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = order 1.
2. K = line(T, 1).

**When**
- `result = idao.get_by_transfer_order_ids(db, workspace_id=W2.id, transfer_order_ids=[T.id])`.

**Then**
1. returns: `result == []`.

### TRO-IT-06 — asked for W0, W1's order id matches nothing
- **Rules:** `get_by_transfer_order_ids` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = order 1.
2. K = line(T, 1).

**When**
- `result = idao.get_by_transfer_order_ids(db, workspace_id=W0.id, transfer_order_ids=[T.id])`.

**Then**
1. returns: `result == []`.

### TRO-IT-07 — two lines with one number of one order are both returned, before the next order
- **Rules:** `get_by_transfer_order_ids` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1.
2. B = order 2.
3. LX = line(B, 1).
4. LA = line(A, 1).
5. LB = line(A, 1).

**When**
- `result = idao.get_by_transfer_order_ids(db, workspace_id=W1.id, transfer_order_ids=[A.id, B.id])`.

**Then**
1. returns: `{result[0].id, result[1].id} == {LA.id, LB.id}`.
2. returns: `result[2].id == LX.id`.

### TRO-IT-08 — lines with one order and number come by id ascending
- **Rules:** `get_by_transfer_order_ids` R3 [BUG-2657]
- **Kind:** bug
- **Expect:** xfail BUG-2657 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no tie-break; physical order after the bump)

**Given**
1. seqscan.
2. T = order 1.
3. LA = line(T, 1).
4. LB = line(T, 1).
5. LC = line(T, 1).
6. bumpL(LA).

**When**
- `result = idao.get_by_transfer_order_ids(db, workspace_id=W1.id, transfer_order_ids=[T.id])`.

**Then**
1. returns: `ids(result) == [LA.id, LB.id, LC.id]`.

### TRO-IT-09 — the query ends its ORDER BY with the line id
- **Rules:** `get_by_transfer_order_ids` R3 [BUG-2657]
- **Kind:** bug
- **Expect:** xfail BUG-2657
- **Fails today on:** Then 2 (today the order ends with `line_number`)

**Given**
1. T = order 1.
2. K = line(T, 1).
3. `tid = T.id`, then `db.expunge_all()`.

**When**
- Statement recorder on: `result = idao.get_by_transfer_order_ids(db, workspace_id=W1.id, transfer_order_ids=[tid])` (`sql` = the SELECT from `transfer_order_items`).

**Then**
1. statement: `"line_number" in order_part`.
2. statement: `order_part.rstrip().endswith("transfer_order_items.id") or order_part.rstrip().endswith("transfer_order_items.id ASC")`.

### TRO-IT-10 — writes nothing and takes no lock
- **Rules:** `get_by_transfer_order_ids` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = order 1.
2. K = line(T, 1).
3. `K.quantity = Decimal("9.00")` (not flushed).
4. P = line(T, 2), added with `db.add(P)` and not flushed.

**When**
- Statement recorder on: `result = idao.get_by_transfer_order_ids(db, workspace_id=W1.id, transfer_order_ids=[T.id])` (`sql` = the SELECT from `transfer_order_items`).

**Then**
1. returns: `ids(result) == [K.id]`.
2. pending: `P in db.new`.
3. pending: `K in db.dirty`.
4. pending: `len(db.dirty) == 1`.
5. statement: `written == []`.
6. statement: `"FOR UPDATE" not in sql`.

## `TransferOrderItemDAO.get_by_id_and_workspace`

### TRO-II-01 — returns the asked line
- **Rules:** `TransferOrderItemDAO.get_by_id_and_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = order 1.
2. K1 = line(T, 1).
3. K2 = line(T, 2).
4. K3 = line(T, 3).

**When**
- `result = idao.get_by_id_and_workspace(db, id=K2.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, TransferOrderItem)`.
2. returns: `result.id == K2.id`.

### TRO-II-02 — asked for W2, W1's line is None
- **Rules:** `TransferOrderItemDAO.get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = order 1.
2. K = line(T, 1).

**When**
- `result = idao.get_by_id_and_workspace(db, id=K.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### TRO-II-03 — asked for W0, W1's line is None
- **Rules:** `TransferOrderItemDAO.get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = order 1.
2. K = line(T, 1).

**When**
- `result = idao.get_by_id_and_workspace(db, id=K.id, workspace_id=W0.id)`.

**Then**
1. returns: `result is None`.

### TRO-II-04 — an unknown id is None
- **Rules:** `TransferOrderItemDAO.get_by_id_and_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = order 1.
2. K = line(T, 1).

**When**
- `result = idao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

## `get_pending_highlights_for_hub` — Planned / Draft stage (BUG-2659, owner's answer to OQ-39)

*The owner answered OQ-39 on 2026-11-11 (BUG-2659): an order is **Planned** when its route is defined (both ids > 0, both types non-empty) **and** it has at least one line of its own workspace; every other not-complete order is **Draft** (awaiting setup, oldest drafts). Labels are `"Planned"` / `"Draft"`, never the stored status. Today the route alone decides, so a route with no line is counted Planned. Cards with a line on a route, or with no route, hold both today and after the fix and pass; the route-without-line cards are strict xfail.*

### TRO-OQ39-01 — a route with a line is planned and labelled "Planned"
- **Rules:** `get_pending_highlights_for_hub` R2, R2a, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, planned.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["pending_planned_count"] == 1`.
2. returns: `result["pending_planned"][0]["status_name"] == "Planned"`.
3. returns: `result["awaiting_setup_count"] == 0`.

### TRO-OQ39-02 — a route with no lines is a Draft, awaiting setup
- **Rules:** `get_pending_highlights_for_hub` R2a, R3 [BUG-2659]
- **Kind:** bug
- **Expect:** xfail BUG-2659
- **Fails today on:** Then 1 (today the route alone counts it planned: `awaiting_setup_count == 0`)

**Given**
1. A = order 1 (no line).

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["awaiting_setup_count"] == 1`.
2. returns: `result["pending_planned_count"] == 0`.
3. returns: `hids(result["awaiting_setup"]) == [A.id]`.
4. returns: `result["awaiting_setup"][0]["status_name"] == "Draft"`.
5. returns: `result["pending_planned"] == []`.

### TRO-OQ39-03 — source id 0 is awaiting setup, labelled "Draft" in both lists
- **Rules:** `get_pending_highlights_for_hub` R2, R2a, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id 0`; planned.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["pending_planned_count"] == 0`.
2. returns: `result["awaiting_setup_count"] == 1`.
3. returns: `result["awaiting_setup"][0]["status_name"] == "Draft"`.
4. returns: `result["oldest_drafts"][0]["status_name"] == "Draft"`.

### TRO-OQ39-04 — destination id 0 is awaiting setup, even with a line
- **Rules:** `get_pending_highlights_for_hub` R2, R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_id 0`; planned.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["awaiting_setup_count"] == 1`.
2. returns: `result["pending_planned_count"] == 0`.

### TRO-OQ39-05 — a negative source id is awaiting setup
- **Rules:** `get_pending_highlights_for_hub` R2, R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_id -1`; planned.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["awaiting_setup_count"] == 1`.
2. returns: `result["pending_planned_count"] == 0`.

### TRO-OQ39-06 — an empty source type is awaiting setup
- **Rules:** `get_pending_highlights_for_hub` R2, R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_type ""`; planned.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["awaiting_setup_count"] == 1`.
2. returns: `result["pending_planned_count"] == 0`.

### TRO-OQ39-07 — an empty destination type is awaiting setup
- **Rules:** `get_pending_highlights_for_hub` R2, R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_type ""`; planned.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["awaiting_setup_count"] == 1`.
2. returns: `result["pending_planned_count"] == 0`.

### TRO-OQ39-08 — ids of 1 with any non-empty types are a defined route
- **Rules:** `get_pending_highlights_for_hub` R2, R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `source_location_type "warehouse"`, `source_location_id 1`, `destination_location_type "warehouse"`, `destination_location_id 1`; planned.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["pending_planned_count"] == 1`.
2. returns: `result["awaiting_setup_count"] == 0`.

### TRO-OQ39-09 — a one-space type is non-empty, so the route is defined
- **Rules:** `get_pending_highlights_for_hub` R2, R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, but `destination_location_type " "`; planned.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["pending_planned_count"] == 1`.
2. returns: `result["awaiting_setup_count"] == 0`.

### TRO-OQ39-10 — the label ignores the stored status
- **Rules:** `get_pending_highlights_for_hub` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, planned (stored status S1, named "Draft").
2. R = order 2, but draft, `current_status_id SP.id` (named "Planned").

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["pending_planned"][0]["status_name"] == "Planned"`.
2. returns: `result["awaiting_setup"][0]["status_name"] == "Draft"`.
3. returns: `result["oldest_drafts"][0]["status_name"] == "Draft"`.

### TRO-OQ39-11 — the two counts add up to the open orders, a route without a line included
- **Rules:** `get_pending_highlights_for_hub` R1, R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1 (no line).
2. P = order 2, planned.
3. R = order 3, but draft.
4. C = order 4, but completed; planned.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["pending_planned_count"] + result["awaiting_setup_count"] == 3`.

### TRO-OQ39-12 — oldest_drafts includes an older route without a line, oldest first
- **Rules:** `get_pending_highlights_for_hub` R5, R6 [BUG-2659]
- **Kind:** bug
- **Expect:** xfail BUG-2659
- **Fails today on:** Then 1 (today the route-without-line order is not a draft: `oldest_drafts` holds R only)

**Given**
1. A = order 1 (no line).
2. R = order 2, but draft.

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `hids(result["oldest_drafts"]) == [A.id, R.id]`.
2. returns: `result["oldest_drafts"][0]["status_name"] == "Draft"`.

### TRO-OQ39-13 — beside a planned order, a route without a line is left out of pending_planned
- **Rules:** `get_pending_highlights_for_hub` R2a, R4 [BUG-2659]
- **Kind:** bug
- **Expect:** xfail BUG-2659
- **Fails today on:** Then 1 (today both orders are counted planned: `pending_planned_count == 2`)

**Given**
1. P = order 1, planned.
2. A = order 2 (no line).

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["pending_planned_count"] == 1`.
2. returns: `hids(result["pending_planned"]) == [P.id]`.
3. returns: `hids(result["awaiting_setup"]) == [A.id]`.

### TRO-OQ39-14 — a route whose only line belongs to another workspace is a Draft
- **Rules:** `get_pending_highlights_for_hub` R2a [BUG-2659]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-2659
- **Fails today on:** Then 2 (today the route alone counts it planned: `awaiting_setup_count == 0`)

**Given**
1. A = order 1.
2. `TransferOrderItem(workspace_id=W2.id, transfer_order_id=A.id, line_number=1, item_id=I2.id, quantity=Decimal("2.00"))` is inserted and flushed (invalid cross-workspace data, built on purpose).

**When**
- `result = dao.get_pending_highlights_for_hub(db, workspace_id=W1.id, **F())`.

**Then**
1. returns: `result["pending_planned_count"] + result["awaiting_setup_count"] == 1`.
2. returns: `result["awaiting_setup_count"] == 1`.
3. returns: `result["pending_planned_count"] == 0`.
4. returns: `hids(result["awaiting_setup"]) == [A.id]`.
5. returns: `result["pending_planned"] == []`.

## `_apply_transfer_order_hub_filters` — status ticks by stage (BUG-2660, owner's answer to OQ-40)

*The owner answered OQ-40 on 2026-11-11 (BUG-2660): a non-empty `status_ids` keeps orders by **stage**. Each id is looked up among the statuses of `workspace_id`; a name that is, trimmed and case-insensitive, `draft` / `planned` / `completed` keeps Draft / Planned / Completed orders (OR between ticks). Completed = `completed_at` set; Planned = not complete, route defined and at least one line; Draft = any other not-complete order. The stored `current_status_id` plays no part. An id of no status, of another workspace's status, or of a status with another name matches nothing; the stage filter combines with AND with the rest (`exclude_complete` included). Today the stored `current_status_id` is compared, so cards where stage and stored status disagree are strict xfail; cards where both readings give the same answer pass. Standing statuses: S1 "Draft", SP "Planned", SC "Completed" (W1); S0, S2 "Draft" (W0, W2). Every order here is stored with a real status row.*

### TRO-OQ40-01 — ticking Planned keeps the Planned orders, not the one stored as Planned
- **Rules:** `_apply_transfer_order_hub_filters` R4 [BUG-2660]
- **Kind:** bug
- **Expect:** xfail BUG-2660
- **Fails today on:** Then 1 (today the stored status is compared, so only B is kept)

**Given**
1. A = order 1, planned (stored S1).
2. B = order 2, but draft, `current_status_id SP.id`.
3. C = order 3, but `current_status_id SC.id`; planned.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=[SP.id]))`.

**Then**
1. returns: `ids(result) == [C.id, A.id]`.

### TRO-OQ40-02 — ticking Draft and Planned keeps both stages, a completed order is left out
- **Rules:** `_apply_transfer_order_hub_filters` R4 [BUG-2660]
- **Kind:** bug
- **Expect:** xfail BUG-2660
- **Fails today on:** Then 1 (today the stored status is compared, so only C is kept)

**Given**
1. A = order 1, but `current_status_id SC.id`; planned.
2. B = order 2, but draft, `current_status_id SC.id`.
3. C = order 3, but completed; planned (stored S1).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, exclude_complete=False, **F(status_ids=[S1.id, SP.id]))`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### TRO-OQ40-03 — an id of no status matches nothing
- **Rules:** `_apply_transfer_order_hub_filters` R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order 1, planned.
2. B = order 2, but draft.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=[MISSING]))`.

**Then**
1. returns: `result == []`.

### TRO-OQ40-04 — the later workspace's "Draft" status matches nothing in W1, though W1 has a draft
- **Rules:** `_apply_transfer_order_hub_filters` R4a, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = order 1, but draft.
2. X2 = order 2 of W2, but draft.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=[S2.id]))`.

**Then**
1. returns: `result == []`.

### TRO-OQ40-05 — ticking Completed finds a completed order stored as Draft
- **Rules:** `_apply_transfer_order_hub_filters` R4 [BUG-2660]
- **Kind:** bug
- **Expect:** xfail BUG-2660
- **Fails today on:** Then 1 (today no order is stored with SC, so the result is empty)

**Given**
1. A = order 1, but completed (stored S1).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, exclude_complete=False, **F(status_ids=[SC.id]))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-OQ40-06 — ticking Draft leaves out a completed order stored as Draft and keeps a draft stored as Completed
- **Rules:** `_apply_transfer_order_hub_filters` R4 [BUG-2660]
- **Kind:** bug
- **Expect:** xfail BUG-2660
- **Fails today on:** Then 1 (today the stored status is compared, so only A is kept)

**Given**
1. A = order 1, but completed (stored S1).
2. B = order 2, but draft, `current_status_id SC.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, exclude_complete=False, **F(status_ids=[S1.id]))`.

**Then**
1. returns: `ids(result) == [B.id]`.

### TRO-OQ40-07 — the count keeps orders by stage
- **Rules:** `_apply_transfer_order_hub_filters` R4 [BUG-2660], `count_for_hub` R1
- **Kind:** bug
- **Expect:** xfail BUG-2660
- **Fails today on:** Then 1 (today only B is stored with SP, so the count is 1)

**Given**
1. A = order 1, planned (stored S1).
2. B = order 2, but draft, `current_status_id SP.id`.
3. C = order 3, planned (stored S1).

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, **F(status_ids=[SP.id]))`.

**Then**
1. returns: `result == 2`.

### TRO-OQ40-08 — the KPI totals keep orders by stage
- **Rules:** `_apply_transfer_order_hub_filters` R4 [BUG-2660], `aggregate_hub_stats` R1
- **Kind:** bug
- **Expect:** xfail BUG-2660
- **Fails today on:** Then 1 (today only C is stored with SP or SC, giving `(1, 1, 0)`)

**Given**
1. A = order 1, but completed; planned (stored S1).
2. B = order 2, planned (stored S1).
3. C = order 3, but draft, `current_status_id SP.id`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, **F(status_ids=[SP.id, SC.id]))`.

**Then**
1. returns: `result == (2, 1, 1)`.

### TRO-OQ40-09 — a status named " planned " (blanks around, lowercase) ticks the Planned stage
- **Rules:** `_apply_transfer_order_hub_filters` R4 [BUG-2660]
- **Kind:** bug
- **Expect:** xfail BUG-2660
- **Fails today on:** Then 1 (today no order is stored with ST, so the result is empty)

**Given**
1. ST = `Status(workspace_id=W1.id, name=" planned ", comment="stage")`.
2. A = order 1, planned (stored S1).
3. B = order 2, but draft.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=[ST.id]))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-OQ40-10 — a status named "PLANNED" ticks the Planned stage
- **Rules:** `_apply_transfer_order_hub_filters` R4 [BUG-2660]
- **Kind:** bug
- **Expect:** xfail BUG-2660
- **Fails today on:** Then 1 (today no order is stored with ST, so the result is empty)

**Given**
1. ST = `Status(workspace_id=W1.id, name="PLANNED", comment="stage")`.
2. A = order 1, planned (stored S1).
3. B = order 2, but draft.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=[ST.id]))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-OQ40-11 — a status of another name ("Review") matches nothing, even for the order stored with it
- **Rules:** `_apply_transfer_order_hub_filters` R4a [BUG-2660]
- **Kind:** bug
- **Expect:** xfail BUG-2660
- **Fails today on:** Then 1 (today the order stored with ST is kept)

**Given**
1. ST = `Status(workspace_id=W1.id, name="Review", comment="stage")`.
2. A = order 1, but `current_status_id ST.id`; planned.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=[ST.id]))`.

**Then**
1. returns: `result == []`.

### TRO-OQ40-12 — a part of a stage name ("Plan") matches nothing
- **Rules:** `_apply_transfer_order_hub_filters` R4a [BUG-2660]
- **Kind:** bug
- **Expect:** xfail BUG-2660
- **Fails today on:** Then 1 (today the order stored with ST is kept)

**Given**
1. ST = `Status(workspace_id=W1.id, name="Plan", comment="stage")`.
2. A = order 1, but `current_status_id ST.id`; planned.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=[ST.id]))`.

**Then**
1. returns: `result == []`.

### TRO-OQ40-13 — an underscore in a status name is not a wildcard ("Plann_d" matches nothing)
- **Rules:** `_apply_transfer_order_hub_filters` R4a [BUG-2660]
- **Kind:** bug
- **Expect:** xfail BUG-2660
- **Fails today on:** Then 1 (today the order stored with ST is kept)

**Given**
1. ST = `Status(workspace_id=W1.id, name="Plann_d", comment="stage")`.
2. A = order 1, but `current_status_id ST.id`; planned.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=[ST.id]))`.

**Then**
1. returns: `result == []`.

### TRO-OQ40-14 — ticking Completed with the default exclude_complete gives nothing
- **Rules:** `_apply_transfer_order_hub_filters` R4a, R7 [BUG-2660]
- **Kind:** bug
- **Expect:** xfail BUG-2660
- **Fails today on:** Then 1 (today the open order B, stored with SC, is kept)

**Given**
1. A = order 1, but completed; planned (stored S1).
2. B = order 2, but `current_status_id SC.id`; planned.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=[SC.id]))`.

**Then**
1. returns: `result == []`.

### TRO-OQ40-15 — a route without a line is in the Draft stage for the tick
- **Rules:** `_apply_transfer_order_hub_filters` R4 [BUG-2660]
- **Kind:** bug
- **Expect:** xfail BUG-2660
- **Fails today on:** Then 1 (today the stored status is compared, so only B is kept)

**Given**
1. A = order 1, but `current_status_id SP.id` (no line).
2. B = order 2, planned (stored S1).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=[S1.id]))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-OQ40-16 — ticking Draft keeps a draft stored as Draft and leaves out a planned order stored as Planned
- **Rules:** `_apply_transfer_order_hub_filters` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order 1, but draft (stored S1).
2. B = order 2, but `current_status_id SP.id`; planned.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=[S1.id]))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-OQ40-17 — the earlier workspace's "Draft" status matches nothing in W1, though W1 has a draft
- **Rules:** `_apply_transfer_order_hub_filters` R4a, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order 1 of W0, but draft.
2. A = order 2, but draft.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=[S0.id]))`.

**Then**
1. returns: `result == []`.

### TRO-OQ40-18 — an unknown id beside the Planned tick does not empty the result
- **Rules:** `_apply_transfer_order_hub_filters` R4, R4a [BUG-2660]
- **Kind:** bug
- **Expect:** xfail BUG-2660
- **Fails today on:** Then 1 (today no order is stored with SP or MISSING, so the result is empty)

**Given**
1. A = order 1, planned (stored S1).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=[MISSING, SP.id]))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-OQ40-19 — ticking Planned in W1 keeps W1's planned order, not W0's or W2's
- **Rules:** `_apply_transfer_order_hub_filters` R4, R1 [BUG-2660]
- **Kind:** bug
- **Expect:** xfail BUG-2660
- **Fails today on:** Then 1 (today no W1 order is stored with SP, so the result is empty)

**Given**
1. X0 = order 1 of W0; planned.
2. A = order 2, planned (stored S1).
3. X2 = order 3 of W2; planned.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=[SP.id]))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### TRO-OQ40-20 — a route whose only line belongs to another workspace is in the Draft stage for the tick
- **Rules:** `_apply_transfer_order_hub_filters` R4 [BUG-2660]; HR-16
- **Kind:** bug
- **Expect:** xfail BUG-2660
- **Fails today on:** Then 1 (today the stored status is compared, so only B is kept)

**Given**
1. A = order 1, but `current_status_id SP.id`.
2. `TransferOrderItem(workspace_id=W2.id, transfer_order_id=A.id, line_number=1, item_id=I2.id, quantity=Decimal("2.00"))` is inserted and flushed (invalid cross-workspace data, built on purpose).
3. B = order 2, planned (stored S1).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, **F(status_ids=[S1.id]))`.

**Then**
1. returns: `ids(result) == [A.id]`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_next_number` R6 [BUG-2652] | integration tests (transfer order manager spec) | two concurrent creates in one workspace both succeed with distinct numbers |
| FU-1 | `TransferOrderManager.create_transfer_order` | the unique violation of BUG-2650 / 2652 is not caught and hidden |
| FU-2 | transfer order manager spec / dead-code list | `list_transfer_orders` and `get_by_workspace` have no caller |
| FU-3 | `TransferOrderService.list_transfer_orders_page`, `get_transfer_order_hub_stats` | the service's `exclude_complete=False` default; `"all"` location type = no filter |
| HR-7 note | `GET /transfer-orders/` | `1 <= limit <= 100` (422 otherwise) |
| BUG-1018 / HR-16 on write | `TransferOrderManager` | a location or status of another workspace is refused as "not found"; the DAO stores what it is given |

## Spec gaps
None. The five gaps of revision 1 (year patch target, filter defaults, prefix case, names, real soft deletes) are closed by the spec's Gap log (2026-11-11, G1 … G5).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_apply_transfer_order_hub_filters` | R0 | HF-53, HF-54 |
| | R1 | HF-01, HF-02, HF-03, AS-05, OQ40-04, OQ40-17, OQ40-19 |
| | R2 | HF-04, HF-05, HF-06, HF-07, HF-08 |
| | R3 | HF-09, HF-10 |
| | R4 [BUG-2660] | OQ40-01, 02, 05 … 10, 15, 18, 19, 20 (xfail); OQ40-16 (pass) |
| | R4a [BUG-2660] | OQ40-11 … 14 (xfail); OQ40-03, 04, 17 (pass) |
| | R5 | HF-11 … HF-19 |
| | R6 | HF-20, FF-* |
| | R7 | HF-21, HF-22, CH-04, HF-53, OQ40-14 |
| | R8 | HF-23, HF-24, HF-25 … HF-28, HF-55 … HF-60 |
| | R9 | HF-25 … HF-43, HF-47, HF-50, HF-55 … HF-63 |
| | R10 | HF-44, HF-45 |
| | R10a [BUG-2654] | HF-46, HF-48, HF-49, HF-51 (xfail); HF-47, HF-50 (pass) |
| | R11 | HF-18, HF-52, LH-08 |
| `_apply_transfer_factory_filter` | R1 | FF-01 … FF-06, FF-11 … FF-16 |
| | R1a [BUG-2658] | FF-17 … FF-22 (xfail); FF-01, FF-05, FF-06, FF-16 (pass) |
| | R2 | FF-09, FF-10 |
| | R3 | FF-07, FF-08 |
| `list_for_hub` | R1 | HF-21, LH-01, LH-12 |
| | R2 | LH-01, LH-02, LH-03 |
| | R3 | LH-04 … LH-08 |
| | R4 / Errors | LH-10 |
| | Returns / side effects | LH-01, LH-09, LH-11 |
| `count_for_hub` | R1 | CH-01 … CH-04, HF-45, FF-08, FF-22, OQ40-07 |
| | Errors | CH-05 |
| | Side effects / HR-10 | CH-06 |
| `list_recent_for_hub` | R1 | RC-01 … RC-04 |
| | R2 [BUG-2655, BUG-2656] | RC-05, RC-06 (2655); RC-07, RC-08, RC-09 (2656); RC-01, RC-02 (pass) |
| | Errors | RC-10 |
| | Side effects / HR-10 | RC-11 |
| `count_machine_involved_for_hub` | R1 | MI-01 … MI-06 |
| | Errors | MI-07 |
| | Side effects / HR-10 | MI-08 |
| `get_pending_highlights_for_hub` | R1 | PH-02, PH-03, OQ39-11 |
| | R2 | OQ39-01, OQ39-03 … OQ39-09 |
| | R2a [BUG-2659] | OQ39-02, 12, 13, 14 (xfail); OQ39-01, 03 … 09, 11 (pass) |
| | R3 | OQ39-01, OQ39-03, OQ39-10 (pass); OQ39-02 (xfail) |
| | R4 [BUG-2655, BUG-2656] | PH-08, PH-09 (2655); PH-10, PH-12 (2656); PH-04, PH-05 (pass) |
| | R5 [BUG-2659 part] | PH-01, PH-06 (pass); OQ39-12 (xfail) |
| | R6 [BUG-2656] | PH-11, PH-12 (xfail); PH-06 (pass) |
| | R7 | PH-07 |
| | Returns / Errors | PH-01 / PH-13 |
| | Side effects / HR-10 | PH-14 |
| `aggregate_hub_stats` | R1 | AS-01, AS-03, AS-05, AS-07, HF-54, OQ40-08 |
| | R2 | AS-02, AS-04, AS-06 |
| | R3 | AS-01 |
| | Errors | AS-08 |
| | Side effects / HR-10 | AS-09 |
| `list_touching_location_incomplete` | R1 | TL-01, TL-04, TL-05, TL-06, TL-07 |
| | R2 | TL-02, TL-03, TL-05, TL-11 |
| | R3 [BUG-2656] | TL-08, TL-09 (xfail); TL-01 (pass) |
| | Side effects | TL-10 |
| `list_inbound_to_storage_incomplete` | R1 | IB-01, IB-07, IB-08, IB-09 |
| | R2 | IB-02 … IB-06 |
| | R3 [BUG-2656] | IB-10, IB-11 (xfail); IB-01 (pass) |
| | Side effects | IB-12 |
| `TransferOrderDAO.get_by_id_and_workspace` | R1 | GI-01, GI-04, GI-06 |
| | R2 | GI-02, GI-03, GI-05 |
| | R3 | GI-07 |
| `get_next_number` | R1 [BUG-2653] | NN-24, NN-25, NN-26 (xfail); NN-23 and every NN card under clock(NOW31, NOW31) (pass) |
| | R2 | NN-01, NN-11 … NN-20 |
| | R2a | NN-30, NN-31 |
| | R2b | NN-33 (pass); NN-32 (xfail) |
| | R3 [BUG-2651] | NN-08, NN-09 (xfail); NN-02 … NN-07 (pass) |
| | R4 [BUG-2651] | NN-10, NN-32 (xfail); NN-11 (pass) |
| | R5 [BUG-2650] | NN-27, NN-28 (xfail); NN-15, NN-29 (pass) |
| | R6 [BUG-2652] | Deferred |
| | Side effects | NN-21, NN-22 |
| `TransferOrderItemDAO.get_by_order` | R1 | IO-01 … IO-07 |
| | R2 [BUG-2657] | IO-08, IO-09 (xfail); IO-01, IO-07 (pass) |
| | HR-15 note | IO-10 |
| | Side effects | IO-11 |
| `get_by_transfer_order_ids` | R1 | IT-01 |
| | R2 | IT-02 … IT-07 |
| | R3 [BUG-2657] | IT-08, IT-09 (xfail); IT-02, IT-07 (pass) |
| | Side effects | IT-10 |
| `TransferOrderItemDAO.get_by_id_and_workspace` | R1 | II-01 … II-04 |
