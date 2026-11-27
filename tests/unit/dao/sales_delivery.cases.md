# Test cases — `app/dao/sales_delivery.py`

> **Spec:** `tests/unit/dao/sales_delivery.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-10; nothing open). P1, Q1 and the fill-gaps decisions G2, G3 were decided by Claude under the reviewer's delegation; none is the owner's own answer.
> **Revision:** 2 (2026-11-10) — spec fill-gaps G1–G3. G1: Conventions import `SalesDeliveryCreate` from `app.schemas.sales_delivery`. G2: new SDV-CW-25 (unknown workspace, 23503, nothing written; new R6a and its Errors row). G3: new SDV-GN-16 (case-sensitive prefix, new R3a); GN-12 now also cites R3a. Conventions now say model time defaults are never patched (times are checked by window). No card retired.
> **Revision:** 3 (2026-11-10) — `sales_delivery.verify.md` finding 1 (convention). SDV-GN-14 drops the vacuous `lock_part == ""`; its no-lock check is `"FOR UPDATE" not in sql` (Then 2). Conventions gain "No-lock check" and "Clear the session before a one-query check". Counts unchanged; no ID retired.
> **Counts:** 83 cases · 71 expected-to-pass · 12 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Per callable:** `generate_delivery_number` 16 · `create_with_user` 25 (6 bug) · `get_by_sales_order` 14 (3 bug) · `get_by_status` 28 (3 bug).
- **Depth:** full (skill step 1a). The module writes order state (a delivery and its number); numbering and clocks get every boundary.
- **Expected-to-fail:** BUG-726 2 strict (SDV-CW-05 the number is held in W2, CW-06 held in W0) · BUG-2440 2 strict (CW-08 local clock a year ahead of UTC, CW-09 a year behind) · BUG-722 2 strict (CW-13 `"shipped"`, CW-14 `"delivered"`) · BUG-2442 2 non-strict (SO-09, SO-10) + 1 strict SQL alarm (SO-11) · BUG-2443 2 non-strict (ST-23, ST-24) + 1 strict SQL alarm (ST-25).
- **Pending owner questions:** none. The spec has no rule pending OQ-25 … OQ-28, so there is no pending section.
- **Notable design choices:**
  - Numbers are globally unique today (BUG-726). So rows of W0 and W2 in numbering cards carry `DEL-2026-` numbers with a TAG suffix (counted if the workspace filter broke, never colliding); only CW-05 and CW-06 put a real `DEL-2026-001` in another workspace, on purpose.
  - What holds today and after BUG-726 stays in pass cards: a number already used in the *same* workspace fails at flush with 23505 (CW-07; no index name asserted, since the fix renames it), and W2's first number is counted from W2 alone (CW-24).
  - BUG-2440 is tested in both directions (local clock ahead of and behind UTC); CW-10 (both clocks in 2031) keeps "the year comes from the clock" protected while the bug is open.
  - `created_at` is checked in cards with no clock patch (CW-11, and CW-12 under Dhaka): the model default may not see a patched `utcnow`, so a patched card could not assert it.
  - Both lists have no `ORDER BY` today: every passing card compares sets; order cards are non-strict with `Author: claude`, and each query has one strict SQL alarm.
  - Race simulations: none. The race half of BUG-727 is integration-only (spec Overview) and is deferred.
  - SDV-CW-25 runs under clock(`datetime(2091, 6, 1, 12, 0)`, `datetime(2091, 6, 1, 12, 0)`): with the number index global (BUG-726), a committed `DEL-2026-001` elsewhere would answer 23505 before the foreign key (R6a); year 2091 keeps the card on the 23503 path.
- **Needs a decision:** none. Gaps 1 and 2 are closed by the spec's Gap log (2026-11-10).

## Conventions for this module

**IDs.** `SDV` = `app/dao/sales_delivery.py`. `GN` generate_delivery_number · `CW` create_with_user · `SO` get_by_sales_order · `ST` get_by_status.

**Actors and fixed values.**
- `dao` = the singleton `sales_delivery_dao` (`from app.dao.sales_delivery import sales_delivery_dao`). `db` = the test's real session, always the first argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- `SalesDelivery` = `app.models.sales_delivery.SalesDelivery`. `SalesDeliveryCreate` = `app.schemas.sales_delivery.SalesDeliveryCreate`. `Account`, `Factory`, `Status`, `SalesOrder`, `DeliveryMethod` = `app.models.<snake_case>`. `IntegrityError`, `DataError` = `sqlalchemy.exc`. `text`, `select`, `func`, `patch`, `date`, `datetime`, `timezone`, `uuid` = the usual ones. `utcnow` = `app.utils.time.utcnow`.
- MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`, made once per test. DA, DB, DC = `date(2026, 7, 1)`, `date(2026, 7, 2)`, `date(2026, 7, 3)`.

**Externals.** Only in `CW` cards. **clock(L, U)** = for the When, patch `app.dao.sales_delivery.datetime` with a subclass of `datetime` whose `now()` returns L, and patch both `app.dao.sales_delivery.utcnow` (with `create=True`) and `app.utils.time.utcnow` to return U. A `CW` card runs under clock(`datetime(2026, 6, 1, 12, 0)`, `datetime(2026, 6, 1, 12, 0)`) unless it has its own clock line or says **no clock** (nothing patched). Model time defaults (`created_at`) are never patched by module name: they are checked by a window (`before <= value <= after`), only in **no clock** cards.

**Standing rows** (every test, this order, each added and flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` three times, so `W0.id < W1.id < W2.id`. U1, U2, U3 = `make_profile(db)` three times.
2. Per workspace Wk (k = 0, 1, 2): ACk = `Account(workspace_id=Wk.id, name="Acme")`, Fk = `Factory(workspace_id=Wk.id, name="Plant", abbreviation=f"P{k}")`, Sk = `Status(workspace_id=Wk.id, name="Draft", comment="Stage")`.
3. Orders, `SalesOrder(workspace_id=…, sales_order_number=…, account_id=…, factory_id=…, order_date=date(2026, 3, 1), total_amount=0, current_status_id=…, created_by=U1.id)`, with the parents of their own workspace: SO0 in W0 `f"SO-{TAG}-0"`; SO1, SO2, SO3 in W1 `f"SO-{TAG}-1"`, `-2`, `-3`; SO9 in W2 `f"SO-{TAG}-9"`. So `SO1.id < SO2.id < SO3.id`.
4. DM1 = `DeliveryMethod(workspace_id=W1.id, name="Courier")`, DM9 = `DeliveryMethod(workspace_id=W2.id, name="Truck")`.

**Given rows.** Inserted directly (never through `dao`), flushed one at a time in the order written, so ids rise in that order. After "but" a line lists every column that differs.
- **delivery** = `SalesDelivery(workspace_id=W1.id, sales_order_id=SO2.id, delivery_number=f"DV-{TAG}-<name>", delivery_status="planned", created_by=U1.id)`, where `<name>` is the row's name in the Given (row B → `f"DV-{TAG}-B"`); every other column left unset. No delivery exists unless the Given lists it.
- **seqscan** = run `db.execute(text("SET LOCAL enable_indexscan = off"))`, then the same for `enable_bitmapscan` and `enable_indexonlyscan`.
- **bump(X)** = `db.execute(text("UPDATE sales_deliveries SET notes = notes WHERE id = :i"), {"i": X.id})`.
- **Dhaka** = `db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))`.
- A Given line written as code is a step to run exactly as written. `db.add(...)` without `db.flush()` leaves the row pending.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` (order is part of the check). **idset(result)** = `{r.id for r in result}`.
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. **unchanged(X)** = after re-read every column of X equals its value before the call.
- **count(Wk)** = `db.scalar(text("SELECT count(*) FROM sales_deliveries WHERE workspace_id = :w"), {"w": Wk.id})`.
- **nothing written** = count(W0), count(W1), count(W2) equal their values before the call.
- `pending:` / `session:` lines check the session right after the call, before anything expires it; they come before `nothing written:` lines.
- `raises: IntegrityError` / `raises: DataError` = `with pytest.raises(E) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards. `raises: TypeError` / `raises: AttributeError` = plain `with pytest.raises(E) as exc:`. Further `raises:` lines assert on `exc.value` or `exc.value.orig`, one per line.
- **commit spy** = `sp = db.begin_nested()` directly before the call, `with patch.object(db, "commit", wraps=db.commit) as cm:` around it; the "inside" lines run before `sp.rollback()`, the "after rollback" lines after it.
- **Statement recorder** = the SQL the session sends during the When is recorded. `sql` = the one `SELECT` from `sales_deliveries`; `order_part` = text of `sql` after its first `ORDER BY`, before any `LIMIT` (`""` if none); `lock_part` = text of `sql` after `FOR UPDATE` (`""` if none); `written` = every recorded `INSERT`, `UPDATE`, `DELETE`.
- **No-lock check** = `"FOR UPDATE" not in sql`. Never use `lock_part == ""` for this: Postgres prints the lock clause last, so the text after `FOR UPDATE` is empty with a lock as well.
- **Clear the session before a one-query check**: a card that counts the SELECTs a call sends (or reads stored values back) ends its Given with `db.expunge_all()` (or `db.expire_all()` where the card says so), so a row the identity map still holds (a profile, a just-inserted value) cannot hide a second read. Ids used in Then come from objects built before it; their loaded attributes stay readable.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`, for cards comparing an order that rests on physical row order. Write the call and checks exactly as shown; never weaken them.

**Race simulations.** None in this module.

## `DAOSalesDelivery.generate_delivery_number`

### SDV-GN-01 — no delivery yet gives DEL-2026-001
- **Rules:** `generate_delivery_number` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no delivery.

**When**
- `result = dao.generate_delivery_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "DEL-2026-001"`.

### SDV-GN-02 — two deliveries give DEL-2026-003
- **Rules:** `generate_delivery_number` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = delivery, but `delivery_number "DEL-2026-001"`.
2. B = delivery, but `delivery_number "DEL-2026-002"`.

**When**
- `result = dao.generate_delivery_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "DEL-2026-003"`.

### SDV-GN-03 — nine deliveries give DEL-2026-010, padded to three digits
- **Rules:** `generate_delivery_number` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(1, 10): db.add(SalesDelivery(workspace_id=W1.id, sales_order_id=SO2.id, delivery_number=f"DEL-2026-{k:03d}", delivery_status="planned", created_by=U1.id))`, then `db.flush()`.

**When**
- `result = dao.generate_delivery_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "DEL-2026-010"`.

### SDV-GN-04 — 999 deliveries give DEL-2026-1000, not cut to three digits
- **Rules:** `generate_delivery_number` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(1, 1000): db.add(SalesDelivery(workspace_id=W1.id, sales_order_id=SO2.id, delivery_number=f"DEL-2026-{k:03d}", delivery_status="planned", created_by=U1.id))`, then `db.flush()`.

**When**
- `result = dao.generate_delivery_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "DEL-2026-1000"`.

### SDV-GN-05 — deliveries of W0 and W2 do not count for W1
- **Rules:** `generate_delivery_number` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = delivery, but `workspace_id W0.id`, `sales_order_id SO0.id`, `delivery_number f"DEL-2026-{TAG}a"`.
2. X1 = delivery, but `workspace_id W0.id`, `sales_order_id SO0.id`, `delivery_number f"DEL-2026-{TAG}b"`.
3. A = delivery, but `delivery_number "DEL-2026-001"`.
4. X2 = delivery, but `workspace_id W2.id`, `sales_order_id SO9.id`, `delivery_number f"DEL-2026-{TAG}c"`.
5. X3 = delivery, but `workspace_id W2.id`, `sales_order_id SO9.id`, `delivery_number f"DEL-2026-{TAG}d"`.

**When**
- `result = dao.generate_delivery_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "DEL-2026-002"`.

### SDV-GN-06 — asked for W0, the later W1 and W2 deliveries do not count
- **Rules:** `generate_delivery_number` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = delivery, but `delivery_number f"DEL-2026-{TAG}a"`.
2. X2 = delivery, but `workspace_id W2.id`, `sales_order_id SO9.id`, `delivery_number f"DEL-2026-{TAG}c"`.

**When**
- `result = dao.generate_delivery_number(db, workspace_id=W0.id, year=2026)`.

**Then**
1. returns: `result == "DEL-2026-001"`.

### SDV-GN-07 — asked for W2, only W2's deliveries count, not the earlier W0 and W1 ones
- **Rules:** `generate_delivery_number` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = delivery, but `workspace_id W0.id`, `sales_order_id SO0.id`, `delivery_number f"DEL-2026-{TAG}a"`.
2. A = delivery, but `delivery_number f"DEL-2026-{TAG}b"`.
3. X2 = delivery, but `workspace_id W2.id`, `sales_order_id SO9.id`, `delivery_number f"DEL-2026-{TAG}c"`.

**When**
- `result = dao.generate_delivery_number(db, workspace_id=W2.id, year=2026)`.

**Then**
1. returns: `result == "DEL-2026-002"`.

### SDV-GN-08 — delivered, cancelled and other statuses all count
- **Rules:** `generate_delivery_number` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = delivery, but `delivery_number "DEL-2026-001"`, `delivery_status "delivered"`.
2. B = delivery, but `delivery_number "DEL-2026-002"`, `delivery_status "cancelled"`.
3. C = delivery, but `delivery_number "DEL-2026-003"`, `delivery_status "on hold"`.

**When**
- `result = dao.generate_delivery_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "DEL-2026-004"`.

### SDV-GN-09 — deliveries of 2025 and 2027 do not count for 2026
- **Rules:** `generate_delivery_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery, but `delivery_number "DEL-2025-001"`.
2. B = delivery, but `delivery_number "DEL-2025-002"`.
3. C = delivery, but `delivery_number "DEL-2027-001"`.
4. D = delivery, but `delivery_number "DEL-2026-001"`.

**When**
- `result = dao.generate_delivery_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "DEL-2026-002"`.

### SDV-GN-10 — year 202 is printed as given and does not count DEL-2026 numbers
- **Rules:** `generate_delivery_number` R3, Inputs (`year` not padded)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery, but `delivery_number "DEL-2026-001"`.
2. B = delivery, but `delivery_number "DEL-2026-002"`.

**When**
- `result = dao.generate_delivery_number(db, workspace_id=W1.id, year=202)`.

**Then**
1. returns: `result == "DEL-202-001"`.

### SDV-GN-11 — every suffix counts: letters, a gap and a changed number
- **Rules:** `generate_delivery_number` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = delivery, but `delivery_number "DEL-2026-abc"`.
2. B = delivery, but `delivery_number "DEL-2026-009"`.
3. C = delivery, but `delivery_number "DEL-2026-"`.

**When**
- `result = dao.generate_delivery_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "DEL-2026-004"`.

### SDV-GN-12 — only numbers that start with the exact prefix count
- **Rules:** `generate_delivery_number` R1, R3, R3a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery, but `delivery_number "XDEL-2026-001"`.
2. B = delivery, but `delivery_number "del-2026-002"`.
3. C = delivery, but `delivery_number " DEL-2026-003"`.
4. D = delivery, but `delivery_number "DEL-20260-004"`.
5. E = delivery, but `delivery_number "DEL_2026_005"`.

**When**
- `result = dao.generate_delivery_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "DEL-2026-001"`.

### SDV-GN-13 — writes nothing: a pending delivery is not counted and stays pending, an unflushed edit stays unflushed
- **Rules:** `generate_delivery_number` R5, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = delivery, but `delivery_number "DEL-2026-001"`.
2. `B.notes = "Edited"` (not flushed).
3. `P = SalesDelivery(workspace_id=W1.id, sales_order_id=SO2.id, delivery_number="DEL-2026-002", delivery_status="planned", created_by=U1.id)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.generate_delivery_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "DEL-2026-002"`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. nothing written: nothing written.

### SDV-GN-14 — takes no row lock
- **Rules:** `generate_delivery_number` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = delivery, but `delivery_number "DEL-2026-001"`.
2. Statement recorder.

**When**
- `result = dao.generate_delivery_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "DEL-2026-002"`.
2. statement: `"FOR UPDATE" not in sql`.

### SDV-GN-15 — positional arguments raise TypeError
- **Rules:** `generate_delivery_number` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no delivery.

**When**
- `dao.generate_delivery_number(db, W1.id, 2026)`, inside the wrap of `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.
2. nothing written: nothing written.

### SDV-GN-16 — the prefix is case-sensitive: lower- and mixed-case numbers do not count, the upper-case one does
- **Rules:** `generate_delivery_number` R3a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery, but `delivery_number "del-2026-001"`.
2. B = delivery, but `delivery_number "DEL-2026-001"`.
3. C = delivery, but `delivery_number "Del-2026-002"`.
4. D = delivery, but `delivery_number "del-2026-002"`.

**When**
- `result = dao.generate_delivery_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "DEL-2026-002"`.

## `DAOSalesDelivery.create_with_user`

### SDV-CW-01 — a delivery is stored with every field of the schema, its workspace, creator and number
- **Rules:** `create_with_user` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no delivery.

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id, scheduled_date=DA, tracking_number="TRK-1", notes="Fragile"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, SalesDelivery)`.
2. returns: `result.id is not None`.
3. re-read result: `workspace_id == W1.id`, `sales_order_id == SO2.id`, `delivery_method_id == DM1.id`, `created_by == U2.id`.
4. re-read result: `scheduled_date == DA`, `tracking_number == "TRK-1"`, `notes == "Fragile"`.
5. re-read result: `delivery_number == "DEL-2026-001"`, `delivery_status == "planned"`.
6. count: `count(W1) == 1`.

### SDV-CW-02 — unset fields are NULL and the defaults are set
- **Rules:** `create_with_user` R1, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no delivery.

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `scheduled_date is None`, `tracking_number is None`, `notes is None`.
3. re-read result: `actual_delivery_date is None`, `completion_code is None`, `updated_by is None`, `updated_at is None`.
4. re-read result: `delivery_status == "planned"`.
5. re-read result: `created_at is not None`.

### SDV-CW-03 — after two deliveries of the year the third gets DEL-2026-003
- **Rules:** `create_with_user` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = delivery, but `delivery_number "DEL-2026-001"`.
2. B = delivery, but `delivery_number "DEL-2026-002"`.

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `delivery_number == "DEL-2026-003"`.
3. count: `count(W1) == 3`.

### SDV-CW-04 — deliveries of W0 and W2 do not move W1's number
- **Rules:** `create_with_user` R1, R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = delivery, but `workspace_id W0.id`, `sales_order_id SO0.id`, `delivery_number f"DEL-2026-{TAG}a"`.
2. X2 = delivery, but `workspace_id W2.id`, `sales_order_id SO9.id`, `delivery_number f"DEL-2026-{TAG}c"`.

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `delivery_number == "DEL-2026-001"`, `workspace_id == W1.id`.

### SDV-CW-05 — W2 holding DEL-2026-001 does not stop W1's first delivery
- **Rules:** `create_with_user` R5 [BUG-726]
- **Kind:** bug
- **Expect:** xfail BUG-726
- **Fails today on:** Then 1 (the call raises IntegrityError: the unique index on the number is global)

**Given**
1. X2 = delivery, but `workspace_id W2.id`, `sales_order_id SO9.id`, `delivery_number "DEL-2026-001"`.

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `delivery_number == "DEL-2026-001"`, `workspace_id == W1.id`.
3. count: `count(W1) == 1`.

### SDV-CW-06 — W0 holding DEL-2026-001 does not stop W1's first delivery
- **Rules:** `create_with_user` R5 [BUG-726]
- **Kind:** bug
- **Expect:** xfail BUG-726
- **Fails today on:** Then 1 (the call raises IntegrityError: the unique index on the number is global)

**Given**
1. X0 = delivery, but `workspace_id W0.id`, `sales_order_id SO0.id`, `delivery_number "DEL-2026-001"`.

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `delivery_number == "DEL-2026-001"`, `workspace_id == W1.id`.
3. count: `count(W1) == 1`.

### SDV-CW-07 — a computed number already used in the same workspace fails at flush and saves nothing
- **Rules:** `create_with_user` R5, Errors (number already used)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = delivery, but `delivery_number "DEL-2026-001"`.
2. B = delivery, but `delivery_number "DEL-2026-002"`.
3. C = delivery, but `delivery_number "DEL-2026-004"`.

**When**
- `dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id), workspace_id=W1.id, user_id=U1.id)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23505"`.
2. session: `len(db.new) == 0`.
3. count: `count(W1) == 3`.

### SDV-CW-08 — the year is UTC's when the local clock is already in the next year
- **Rules:** `create_with_user` R2 [BUG-2440]
- **Kind:** bug
- **Expect:** xfail BUG-2440
- **Fails today on:** Then 2 (the local year is used: `DEL-2027-001`)

**Given**
1. W1 has no delivery.
2. clock(`datetime(2027, 1, 1, 5, 0)`, `datetime(2026, 12, 31, 23, 0)`).

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `delivery_number == "DEL-2026-001"`.

### SDV-CW-09 — the year is UTC's when the local clock is still in the old year
- **Rules:** `create_with_user` R2 [BUG-2440]
- **Kind:** bug
- **Expect:** xfail BUG-2440
- **Fails today on:** Then 2 (the local year is used: `DEL-2026-001`)

**Given**
1. W1 has no delivery.
2. clock(`datetime(2026, 12, 31, 20, 0)`, `datetime(2027, 1, 1, 1, 0)`).

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `delivery_number == "DEL-2027-001"`.

### SDV-CW-10 — the year comes from the clock: both clocks in 2031 give DEL-2031-001
- **Rules:** `create_with_user` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = delivery, but `delivery_number "DEL-2026-001"`.
2. clock(`datetime(2031, 1, 1, 0, 30)`, `datetime(2031, 1, 1, 0, 30)`).

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `delivery_number == "DEL-2031-001"`.

### SDV-CW-11 — created_at is the current time in UTC, naive
- **Rules:** `create_with_user` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. no clock.
2. `before = datetime.now(timezone.utc).replace(tzinfo=None)`.

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id), workspace_id=W1.id, user_id=U1.id); after = datetime.now(timezone.utc).replace(tzinfo=None)` (one step).

**Then**
1. returns: `result.id is not None`.
2. re-read result: `created_at.tzinfo is None`.
3. re-read result: `before <= created_at <= after`.

### SDV-CW-12 — created_at stays UTC when the database runs in Asia/Dhaka
- **Rules:** `create_with_user` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. no clock.
2. Dhaka.
3. `before = datetime.now(timezone.utc).replace(tzinfo=None)`.

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id), workspace_id=W1.id, user_id=U1.id); after = datetime.now(timezone.utc).replace(tzinfo=None)` (one step).

**Then**
1. returns: `result.id is not None`.
2. re-read result: `before <= created_at <= after`.

### SDV-CW-13 — a schema carrying status "shipped" still makes a planned delivery
- **Rules:** `create_with_user` R3 [BUG-722]
- **Kind:** bug
- **Expect:** xfail BUG-722
- **Fails today on:** Then 2 (the schema's `"shipped"` is stored)

**Given**
1. W1 has no delivery.

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id, delivery_status="shipped"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `delivery_status == "planned"`.

### SDV-CW-14 — a schema carrying status "delivered" still makes a planned delivery
- **Rules:** `create_with_user` R3 [BUG-722]
- **Kind:** bug
- **Expect:** xfail BUG-722
- **Fails today on:** Then 2 (the schema's `"delivered"` is stored)

**Given**
1. W1 has no delivery.

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id, delivery_status="delivered"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `delivery_status == "planned"`.

### SDV-CW-15 — an order of another workspace is stored as given
- **Rules:** `create_with_user` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. W1 has no delivery.

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO9.id, delivery_method_id=DM1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `sales_order_id == SO9.id`, `workspace_id == W1.id`.

### SDV-CW-16 — another workspace's delivery method is stored as given
- **Rules:** `create_with_user` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. W1 has no delivery.

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM9.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `delivery_method_id == DM9.id`, `workspace_id == W1.id`.

### SDV-CW-17 — an unknown order fails at flush with 23503 and saves nothing
- **Rules:** `create_with_user` R6, Errors (unknown order)
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no delivery.

**When**
- `dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=MISSING, delivery_method_id=DM1.id), workspace_id=W1.id, user_id=U1.id)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. session: `len(db.new) == 0`.
3. nothing written: nothing written.

### SDV-CW-18 — an unknown delivery method fails at flush with 23503 and saves nothing
- **Rules:** `create_with_user` R6, Errors (unknown delivery method)
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no delivery.

**When**
- `dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=MISSING), workspace_id=W1.id, user_id=U1.id)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. session: `len(db.new) == 0`.
3. nothing written: nothing written.

### SDV-CW-19 — an unknown user fails at flush with 23503 and saves nothing
- **Rules:** `create_with_user` R6, Errors (unknown user)
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no delivery.

**When**
- `dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id), workspace_id=W1.id, user_id=MISSING)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. session: `len(db.new) == 0`.
3. nothing written: nothing written.

### SDV-CW-20 — text values are stored exactly as the schema gives them
- **Rules:** `create_with_user` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no delivery.

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id, tracking_number=" Trk_1 ", notes=" Leave_At Gate"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `tracking_number == " Trk_1 "`, `notes == " Leave_At Gate"`.

### SDV-CW-21 — flushed, not committed: a rollback removes the delivery
- **Rules:** `create_with_user` Returns, Side effects (flush only)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no delivery.
2. commit spy.

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `count(W1) == 1`.
3. mock called: `cm.call_count == 0`.
4. count: after rollback, `count(W1) == 0`.

### SDV-CW-22 — positional arguments raise TypeError and save nothing
- **Rules:** `create_with_user` R7
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no delivery.

**When**
- `dao.create_with_user(db, SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id), W1.id, U1.id)`, inside the wrap of `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.
2. session: `len(db.new) == 0`.
3. nothing written: nothing written.

### SDV-CW-23 — a plain dict as obj_in raises AttributeError and saves nothing
- **Rules:** `create_with_user` R7
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no delivery.

**When**
- `dao.create_with_user(db, obj_in={"sales_order_id": SO2.id, "delivery_method_id": DM1.id}, workspace_id=W1.id, user_id=U1.id)`, inside the wrap of `raises: AttributeError`.

**Then**
1. raises: `isinstance(exc.value, AttributeError)`.
2. session: `len(db.new) == 0`.
3. nothing written: nothing written.

### SDV-CW-24 — created in W2, the number counts W2's deliveries only
- **Rules:** `create_with_user` R1, R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = delivery, but `delivery_number f"DEL-2026-{TAG}a"`.
2. B = delivery, but `delivery_number f"DEL-2026-{TAG}b"`.
3. X2 = delivery, but `workspace_id W2.id`, `sales_order_id SO9.id`, `delivery_number "DEL-2026-001"`.

**When**
- `result = dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO9.id, delivery_method_id=DM9.id), workspace_id=W2.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `delivery_number == "DEL-2026-002"`, `workspace_id == W2.id`.
3. count: `count(W2) == 2`.

### SDV-CW-25 — an unknown workspace fails at flush with 23503 and saves nothing
- **Rules:** `create_with_user` R6a, Errors (unknown workspace)
- **Kind:** error
- **Expect:** pass

**Given**
1. clock(`datetime(2091, 6, 1, 12, 0)`, `datetime(2091, 6, 1, 12, 0)`).
2. `db.scalar(text("SELECT count(*) FROM sales_deliveries WHERE delivery_number = 'DEL-2091-001'")) == 0` is asserted (a precondition, not a numbered check).

**When**
- `dao.create_with_user(db, obj_in=SalesDeliveryCreate(sales_order_id=SO2.id, delivery_method_id=DM1.id), workspace_id=MISSING, user_id=U1.id)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. session: `len(db.new) == 0`.
3. count: `db.scalar(text("SELECT count(*) FROM sales_deliveries WHERE workspace_id = :w"), {"w": MISSING}) == 0`.
4. nothing written: nothing written.

## `DAOSalesDelivery.get_by_sales_order`

### SDV-SO-01 — only the order's deliveries, not those of a lower or a higher order id
- **Rules:** `get_by_sales_order` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = delivery, but `sales_order_id SO1.id`.
2. B = delivery.
3. C = delivery, but `sales_order_id SO3.id`.
4. D = delivery.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {B.id, D.id}`.
3. returns: `len(result) == 2`.

### SDV-SO-02 — deliveries in every status are returned
- **Rules:** `get_by_sales_order` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = delivery.
2. B = delivery, but `delivery_status "delivered"`.
3. C = delivery, but `delivery_status "cancelled"`.
4. D = delivery, but `delivery_status "on hold"`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id, B.id, C.id, D.id}`.

### SDV-SO-03 — rows of W0 and W2 on the same order are not returned for W1
- **Rules:** `get_by_sales_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X2 = delivery, but `workspace_id W2.id`.
2. B = delivery.
3. X0 = delivery, but `workspace_id W0.id`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### SDV-SO-04 — a row recorded under W2 on W1's order is returned only for W2
- **Rules:** `get_by_sales_order` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = delivery, but `workspace_id W0.id`.
2. B = delivery.
3. X2 = delivery, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X2.id]`.

### SDV-SO-05 — an unknown order returns an empty list
- **Rules:** `get_by_sales_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SDV-SO-06 — order id 0 returns an empty list
- **Rules:** `get_by_sales_order` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SDV-SO-07 — an order without deliveries returns an empty list
- **Rules:** `get_by_sales_order` R1, Returns
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO3.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SDV-SO-08 — no cap: 102 deliveries give 102 rows
- **Rules:** `get_by_sales_order` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(102): db.add(SalesDelivery(workspace_id=W1.id, sales_order_id=SO2.id, delivery_number=f"DV-{TAG}-{k}", delivery_status="planned", created_by=U1.id))`, then `db.flush()`.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 102`.
2. returns: `len(idset(result)) == 102`.

### SDV-SO-09 — id ascending, also after the lowest id was updated
- **Rules:** `get_by_sales_order` R3 [BUG-2442]
- **Kind:** bug
- **Expect:** xfail BUG-2442 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`; under a sequential scan the updated row comes last)

**Given**
1. A = delivery.
2. B = delivery.
3. C = delivery.
4. seqscan.
5. bump(A).
6. `db.expire_all()`

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### SDV-SO-10 — id decides, when number, date, creator and status would each sort otherwise
- **Rules:** `get_by_sales_order` R3 [BUG-2442]
- **Kind:** bug
- **Expect:** xfail BUG-2442 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`; under a sequential scan the updated row comes last)

**Given**
1. A = delivery, but `delivery_number f"DV-{TAG}-3"`, `scheduled_date DC`, `created_by U3.id`, `delivery_status "planned"`.
2. B = delivery, but `delivery_number f"DV-{TAG}-2"`, `scheduled_date DB`, `created_by U2.id`, `delivery_status "delivered"`.
3. C = delivery, but `delivery_number f"DV-{TAG}-1"`, `scheduled_date DA`, `created_by U1.id`, `delivery_status "cancelled"`.
4. seqscan.
5. bump(A).
6. `db.expire_all()`

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### SDV-SO-11 — the query orders by sales_deliveries.id ascending
- **Rules:** `get_by_sales_order` R3 [BUG-2442]
- **Kind:** bug
- **Expect:** xfail BUG-2442
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = delivery.
2. Statement recorder.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"sales_deliveries.id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### SDV-SO-12 — writes nothing: a pending delivery stays pending and is not returned, an unflushed edit stays unflushed
- **Rules:** `get_by_sales_order` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = delivery.
2. B = delivery.
3. `B.notes = "Edited"` (not flushed).
4. `P = SalesDelivery(workspace_id=W1.id, sales_order_id=SO2.id, delivery_number=f"DV-{TAG}-P", delivery_status="planned", created_by=U1.id)`
5. `db.add(P)` (not flushed).
6. Statement recorder.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id, B.id}`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `B.notes == "Edited"`.
7. statement: `written == []`.
8. nothing written: nothing written.

### SDV-SO-13 — the query does not join the order table
- **Rules:** `get_by_sales_order` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = delivery.
2. Statement recorder.

**When**
- `result = dao.get_by_sales_order(db, sales_order_id=SO2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"sales_orders" not in sql`.

### SDV-SO-14 — positional arguments raise TypeError
- **Rules:** `get_by_sales_order` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. A = delivery.

**When**
- `dao.get_by_sales_order(db, SO2.id, W1.id)`, inside the wrap of `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.

## `DAOSalesDelivery.get_by_status`

### SDV-ST-01 — "planned" keeps the planned deliveries only
- **Rules:** `get_by_status` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = delivery, but `delivery_status "delivered"`.
2. B = delivery.
3. C = delivery, but `delivery_status "cancelled"`.
4. D = delivery.

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {B.id, D.id}`.
3. returns: `len(result) == 2`.

### SDV-ST-02 — "Planned" in capitals keeps none
- **Rules:** `get_by_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery.

**When**
- `result = dao.get_by_status(db, delivery_status="Planned", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SDV-ST-03 — a trailing space keeps none
- **Rules:** `get_by_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery.

**When**
- `result = dao.get_by_status(db, delivery_status="planned ", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SDV-ST-04 — a leading space keeps none
- **Rules:** `get_by_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery.

**When**
- `result = dao.get_by_status(db, delivery_status=" planned", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SDV-ST-05 — stored look-alikes are not kept by "planned"
- **Rules:** `get_by_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery, but `delivery_status "Planned"`.
2. B = delivery, but `delivery_status " planned"`.
3. C = delivery, but `delivery_status "planned_x"`.
4. D = delivery.

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [D.id]`.

### SDV-ST-06 — part of the status keeps none
- **Rules:** `get_by_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery.

**When**
- `result = dao.get_by_status(db, delivery_status="lann", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SDV-ST-07 — _ in the status is no wildcard
- **Rules:** `get_by_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery.

**When**
- `result = dao.get_by_status(db, delivery_status="plann_d", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SDV-ST-08 — % in the status is no wildcard
- **Rules:** `get_by_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery.

**When**
- `result = dao.get_by_status(db, delivery_status="%", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SDV-ST-09 — an empty status keeps none
- **Rules:** `get_by_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery.
2. B = delivery, but `delivery_status "delivered"`.

**When**
- `result = dao.get_by_status(db, delivery_status="", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### SDV-ST-10 — any text is accepted: "shipped" keeps the shipped delivery
- **Rules:** `get_by_status` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = delivery.
2. B = delivery, but `delivery_status "shipped"`.

**When**
- `result = dao.get_by_status(db, delivery_status="shipped", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### SDV-ST-11 — planned deliveries of W0 and W2 are not returned for W1
- **Rules:** `get_by_status` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = delivery, but `workspace_id W0.id`, `sales_order_id SO0.id`.
2. B = delivery.
3. X2 = delivery, but `workspace_id W2.id`, `sales_order_id SO9.id`.

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### SDV-ST-12 — asked for W2, only W2's planned delivery is returned
- **Rules:** `get_by_status` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = delivery, but `workspace_id W0.id`, `sales_order_id SO0.id`.
2. B = delivery.
3. X2 = delivery, but `workspace_id W2.id`, `sales_order_id SO9.id`.

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X2.id]`.

### SDV-ST-13 — with the defaults 102 matching deliveries give 100
- **Rules:** `get_by_status` R4 (default limit)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(102): db.add(SalesDelivery(workspace_id=W1.id, sales_order_id=SO2.id, delivery_number=f"DV-{TAG}-{k}", delivery_status="planned", created_by=U1.id))`, then `db.flush()`.
2. `ALL = set(db.scalars(select(SalesDelivery.id).where(SalesDelivery.workspace_id == W1.id)))`

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len(idset(result)) == 100`.
3. returns: `idset(result) <= ALL`.

### SDV-ST-14 — limit=1000 gives all 102
- **Rules:** `get_by_status` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for k in range(102): db.add(SalesDelivery(workspace_id=W1.id, sales_order_id=SO2.id, delivery_number=f"DV-{TAG}-{k}", delivery_status="planned", created_by=U1.id))`, then `db.flush()`.

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 102`.
2. returns: `len(idset(result)) == 102`.

### SDV-ST-15 — limit=0 returns an empty list
- **Rules:** `get_by_status` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery.

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### SDV-ST-16 — a negative limit raises DataError 2201W
- **Rules:** `get_by_status` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = delivery.

**When**
- `dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201W"`.
2. nothing written: nothing written.

### SDV-ST-17 — a negative skip raises DataError 2201X
- **Rules:** `get_by_status` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = delivery.

**When**
- `dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201X"`.
2. nothing written: nothing written.

### SDV-ST-18 — skip past the end returns an empty list
- **Rules:** `get_by_status` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery.
2. B = delivery.

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### SDV-ST-19 — skip=2, limit=2 of five gives two rows
- **Rules:** `get_by_status` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery.
2. B = delivery.
3. C = delivery.
4. D = delivery.
5. E = delivery.

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id, skip=2, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `idset(result) <= {A.id, B.id, C.id, D.id, E.id}`.

### SDV-ST-20 — skip=4 of five gives one row
- **Rules:** `get_by_status` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = delivery.
2. B = delivery.
3. C = delivery.
4. D = delivery.
5. E = delivery.

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id, skip=4)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `idset(result) <= {A.id, B.id, C.id, D.id, E.id}`.

### SDV-ST-21 — the status filter comes before the page: earlier delivered rows take no place
- **Rules:** `get_by_status` R1, R4 (HR-5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. H1 = delivery, but `delivery_status "delivered"`.
2. H2 = delivery, but `delivery_status "cancelled"`.
3. B = delivery.
4. C = delivery.

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `idset(result) == {B.id, C.id}`.

### SDV-ST-22 — the workspace filter comes before the page: earlier rows of W0 and W2 take no place
- **Rules:** `get_by_status` R2, R4 (HR-5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X0 = delivery, but `workspace_id W0.id`, `sales_order_id SO0.id`.
2. X2 = delivery, but `workspace_id W2.id`, `sales_order_id SO9.id`.
3. B = delivery.
4. C = delivery.

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `idset(result) == {B.id, C.id}`.

### SDV-ST-23 — id ascending, when the lowest id was updated and the other columns sort otherwise
- **Rules:** `get_by_status` R3 [BUG-2443]
- **Kind:** bug
- **Expect:** xfail BUG-2443 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`; under a sequential scan the updated row comes last)

**Given**
1. A = delivery, but `delivery_number f"DV-{TAG}-3"`, `scheduled_date DC`, `created_by U3.id`, `sales_order_id SO3.id`.
2. B = delivery, but `delivery_number f"DV-{TAG}-2"`, `scheduled_date DB`, `created_by U2.id`.
3. C = delivery, but `delivery_number f"DV-{TAG}-1"`, `scheduled_date DA`, `created_by U1.id`, `sales_order_id SO1.id`.
4. seqscan.
5. bump(A).
6. `db.expire_all()`

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### SDV-ST-24 — skip=1, limit=1 gives the second delivery by id
- **Rules:** `get_by_status` R3, R4 [BUG-2443]
- **Kind:** bug
- **Expect:** xfail BUG-2443 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no `ORDER BY`; under a sequential scan the updated row A comes last, so C is second)

**Given**
1. A = delivery.
2. B = delivery.
3. C = delivery.
4. seqscan.
5. bump(A).
6. `db.expire_all()`

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `ids(result) == [B.id]`.

### SDV-ST-25 — the query orders by sales_deliveries.id ascending, before LIMIT
- **Rules:** `get_by_status` R3 [BUG-2443]
- **Kind:** bug
- **Expect:** xfail BUG-2443
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = delivery.
2. Statement recorder.

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"sales_deliveries.id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.
6. statement: `sql.index("ORDER BY") < sql.index("LIMIT")`.

### SDV-ST-26 — writes nothing: a pending delivery stays pending and is not returned, an unflushed edit stays unflushed
- **Rules:** `get_by_status` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = delivery.
2. B = delivery.
3. `B.notes = "Edited"` (not flushed).
4. `P = SalesDelivery(workspace_id=W1.id, sales_order_id=SO2.id, delivery_number=f"DV-{TAG}-P", delivery_status="planned", created_by=U1.id)`
5. `db.add(P)` (not flushed).
6. Statement recorder.

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id, B.id}`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `B.notes == "Edited"`.
7. statement: `written == []`.
8. nothing written: nothing written.

### SDV-ST-27 — the query does not join the order table
- **Rules:** `get_by_status` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = delivery.
2. Statement recorder.

**When**
- `result = dao.get_by_status(db, delivery_status="planned", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"sales_orders" not in sql`.

### SDV-ST-28 — positional arguments raise TypeError
- **Rules:** `get_by_status` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. A = delivery.

**When**
- `dao.get_by_status(db, "planned", W1.id)`, inside the wrap of `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `create_with_user` R5 [BUG-727] race half | integration tests | two concurrent creates in one workspace both succeed with distinct numbers |
| `create_with_user` R6 (foreign order) | `SalesManager.create_delivery_with_items` R2 | an order of another workspace is refused as not found |
| `create_with_user` R6 (foreign / deleted method) [BUG-730] | `SalesManager` | another workspace's delivery method is refused |
| FU-1 (a) | `SalesService.get_deliveries`, `GET /sales-deliveries/` | `delivery_status=""` and unknown codes: filter or 422 |
| FU-1 (b) HR-7 | `GET /sales-deliveries/` | `limit < 1` gives 422, never reaches Postgres |
| FU-1 (c) | `GET /sales-orders/{id}/deliveries/` | unknown or foreign order: 404 vs `[]` |
| FU-2 | `tests/unit/managers/sales_manager.spec.md` | `create_delivery_with_items` R4 wording: UTC year after BUG-2440 |
| inherited `get_by_id_and_workspace`, `get_by_workspace`, `update` | `tests/unit/dao/base.cases.md` | base behaviour, not repeated |

## Spec gaps
None. Revision 1 gaps closed by the spec's Gap log (2026-11-10): 1 (import path) → G1, Conventions; 2 (unknown workspace) → G2, SDV-CW-25.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `generate_delivery_number` | R1 | SDV-GN-01, GN-02, GN-03, GN-04, GN-12 |
| `generate_delivery_number` | R2 | SDV-GN-05, GN-06, GN-07, GN-08 |
| `generate_delivery_number` | R3 | SDV-GN-09, GN-10, GN-12 |
| `generate_delivery_number` | R3a | SDV-GN-12, GN-16 |
| `generate_delivery_number` | R4 | SDV-GN-11 |
| `generate_delivery_number` | R5 | SDV-GN-13, GN-14 |
| `generate_delivery_number` | R6 | SDV-GN-15 |
| `generate_delivery_number` | Side effects | SDV-GN-13 |
| `create_with_user` | R1 | SDV-CW-01, CW-02, CW-03, CW-04, CW-10, CW-20, CW-24 |
| `create_with_user` | R2 [BUG-2440] | SDV-CW-08, CW-09 (xfail); CW-10 |
| `create_with_user` | R3 [BUG-722] | SDV-CW-13, CW-14 (xfail); CW-01, CW-02 (planned by default) |
| `create_with_user` | R4 | SDV-CW-02, CW-11, CW-12 |
| `create_with_user` | R5 [BUG-726] | SDV-CW-05, CW-06 (xfail); CW-04, CW-07, CW-24 |
| `create_with_user` | R5 [BUG-727] | Deferred (race) |
| `create_with_user` | R6 | SDV-CW-15, CW-16, CW-17, CW-18, CW-19 |
| `create_with_user` | R6a | SDV-CW-25 |
| `create_with_user` | R7 | SDV-CW-22, CW-23 |
| `create_with_user` | Errors: number already used | SDV-CW-07 |
| `create_with_user` | Errors: unknown order / method / user / workspace | SDV-CW-17, CW-18, CW-19, CW-25 |
| `create_with_user` | Side effects (flush only) | SDV-CW-21 |
| `get_by_sales_order` | R1 | SDV-SO-01, SO-02, SO-07, SO-13 |
| `get_by_sales_order` | R2 | SDV-SO-03, SO-04, SO-05, SO-06 |
| `get_by_sales_order` | R3 [BUG-2442] | SDV-SO-09, SO-10 (non-strict), SO-11 (strict) |
| `get_by_sales_order` | R4 | SDV-SO-08 |
| `get_by_sales_order` | R5 | SDV-SO-14 |
| `get_by_sales_order` | Side effects | SDV-SO-12 |
| `get_by_status` | R1 | SDV-ST-01 … ST-10, ST-21, ST-27 |
| `get_by_status` | R2 | SDV-ST-11, ST-12, ST-22 |
| `get_by_status` | R3 [BUG-2443] | SDV-ST-23, ST-24 (non-strict), ST-25 (strict) |
| `get_by_status` | R4 | SDV-ST-13 … ST-20, ST-24 |
| `get_by_status` | R5 | SDV-ST-28 |
| `get_by_status` | Errors: negative limit / skip | SDV-ST-16, ST-17 |
| `get_by_status` | Side effects | SDV-ST-26 |
