# Test cases — `app/dao/work_order.py`

> **Spec:** `tests/unit/dao/work_order.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-10; no owner question, every item delegated). No rule is marked *pending OQ-n*, so this file has no pending section.
> **Revision:** 2 (2026-11-14) — spec fill-gaps 2026-11-11 (Gap log G1–G5, no owner question). G1: the enums come from `app.models.enums` (Conventions). G2: sheet filter defaults are `None`, `exclude_completed=False`; new WKO-LS-08 and CS-06 (no filter sent → completed orders listed / counted); cards may omit keywords they do not use. G3: COMPLETED / VOIDED / IN_PROGRESS Givens now carry what a real complete / void / start writes (Conventions **completed**, **voided**, **started**; 38 Given lines). G4: BUG-2675's new parameters default to `None` / `False` / `None`; new WKO-DC-16 (pass: no new keyword sent → completed counted, holds today and after the fix) and DC-17 (xfail: the defaults sent explicitly count as today). G5: new `get_next_number` R3a → WKO-NN-26 (xfail BUG-2676, `WO-2031-1-2` beside `-005` → `-006`; today `-003`). Year patch target confirmed: clockN already patches `datetime.datetime` and `app.dao.work_order.utcnow`. No ID retired.
> **Revision:** 3 (2026-11-14) — `work_order.verify.md` F1 (case-missing, advisory): new WKO-NN-27, strict xfail BUG-2676 (R4) — `WO-2031-005` beside `WO-2031-1_000` → `WO-2031-006`, so a fix that reads suffixes with a lenient number parse instead of "all ASCII digits" fails. No other case-designer finding; the surviving mutants are equivalent or dead code. No ID retired.
> **Counts:** 189 cases · 167 expected-to-pass · 22 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `_work_order_calendar_date_expr` 3 · `_sheet_base_query` 6 · `_apply_sheet_list_filters` 29 (5 bug) · `get_by_workspace` 30 (2 bug) · `list_future_drafts_for_template_machine` 12 · `list_drafts_outside_range_for_template_machine` 13 · `get_by_machine_date_type` 18 (2 bug) · `list_for_sheet` 8 · `count_for_sheet` 6 · `count_by_calendar_date_for_sheet` 17 (4 bug) · `get_by_id_and_workspace` 11 · `get_next_number` 27 (7 bug) · `soft_delete` 9 (2 bug).
- **Expected-to-fail by bug:** BUG-2672 3 (SF-25 `_`, SF-26 `%`, SF-27 `\`) · BUG-2673 2 (SF-12, SF-13, one per direction) · BUG-2670 1 strict SQL alarm + 1 non-strict (GW-27, GW-28) · BUG-2671 1 strict + 1 non-strict (MD-17, MD-16) · BUG-2675 4 (DC-12 … DC-14, DC-17, the call raises TypeError today) · BUG-2676 5 (NN-07, NN-08, NN-09, NN-26, NN-27) · BUG-2678 2 (NN-20, NN-21) · BUG-2679 2 (SD-08, SD-09). BUG-2674 (endpoint 422) and BUG-2677 (race) are deferred.
- **Depth:** full (skill step 1a). The DAO numbers work orders (order workflow), decides which drafts a recurring program deletes, and which existing order blocks a new draft.
- **Notable design choices:**
  - Helpers `_work_order_calendar_date_expr`, `_apply_sheet_list_filters` and `_sheet_base_query` are tested through `list_for_sheet` / `count_by_calendar_date_for_sheet` (their only callers); revision-1 sheet cards pass `exclude_completed=False` explicitly, which equals the default (spec R4); LS-08 and CS-06 pin the default itself.
  - Work order numbers are unique **per workspace** (`uq_wo_workspace_number`), and every test makes its own workspaces, so numbers are stored as written; no per-process suffix is needed. Numbering runs under clock(L, U) in **2031**, so a hard-coded or real-clock year fails.
  - BUG-2676 is tested three ways: `-999` + `-1000` (text order), `-5` + `-010` (unpadded), and `-abc` as the text-highest. `-999` alone → `-1000` and `-1000` alone → `-1001` hold today and stay pass cards.
  - Every filter on an id has a W1 row with a lower and a higher key (standing rows FA < F1 < FB, TA < T1 < TB, MA < M1 < MB, PA < P1 < PB), and every workspace check asks for W0 (built before W1) and W2 (after) separately.
  - Ties: `created_at` is the transaction start, so rows without an explicit stamp tie. Tie cards (BUG-2670, BUG-2671) are non-strict and `Author: claude`; each query has one strict SQL alarm (`work_orders.id DESC` in the ORDER BY) and one pass card for the `created_at DESC` that holds today.
  - Search: middle-of-field, capitals, a leading space on the argument and on the stored value, NULL columns, title not searched (Q5), whitespace-only; `_`, `%`, `\` literal are strict xfails (BUG-2672).
  - Clocks: BUG-2678 and BUG-2673 each have one card per direction across midnight / New Year; BUG-2679 has a patched-`utcnow` card and a real-clock window card, both under Dhaka.
  - HR-15: the DAO computes no money; GI-08 … GI-11 check that `cost` is stored and read back half up (2.125 → 2.13, 0.005 → 0.01, -1.005 → -1.01, control 2.124 → 2.12).
  - Race simulations: none (BUG-2677 is deferred to an integration test).
  - Real states: completed, voided and started Givens carry the stamps a real complete / void / start writes (spec Overview "What real state changes write"), though the DAO reads only `status`.
- **Needs a decision:** None. The five revision-1 gaps are closed by the spec's Gap log (2026-11-11).

## Conventions for this module

**IDs.** `WKO` = `app/dao/work_order.py`. `CE` `_work_order_calendar_date_expr` · `SF` `_apply_sheet_list_filters` · `SB` `_sheet_base_query` · `GW` `get_by_workspace` · `FD` `list_future_drafts_for_template_machine` · `OR` `list_drafts_outside_range_for_template_machine` · `MD` `get_by_machine_date_type` · `LS` `list_for_sheet` · `CS` `count_for_sheet` · `DC` `count_by_calendar_date_for_sheet` · `GI` `get_by_id_and_workspace` · `NN` `get_next_number` · `SD` `soft_delete`.

**Actors and fixed values.**
- `dao` = `work_order_dao` (`from app.dao.work_order import work_order_dao`). `db` = the test's real session, first argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- `WorkOrder` = `app.models.work_order.WorkOrder`. `WorkOrderStatusEnum`, `WorkOrderPriorityEnum` = `app.models.enums`. `Factory`, `Machine`, `WorkOrderType`, `WorkOrderTemplate` = `app.models.<snake_case>`. `IntegrityError` = `sqlalchemy.exc.IntegrityError`. `Decimal`, `date`, `datetime`, `timedelta`, `timezone`, `text`, `select`, `func`, `patch` = the usual ones. `ST` = `WorkOrderStatusEnum`, `PR` = `WorkOrderPriorityEnum`.
- MISSING = `999999999`. **XID(k)** = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`; "`id XID(k)`" passes `id=XID(k)` to the builder (higher than any sequence id).
- **Dn** = `date(2026, 3, n)` (D9 = 9 March 2026 …). **Cn** = `datetime(2026, 3, 4, n, 0)` (naive; C9 = 4 March 09:00). **KD(n)** = `datetime(2026, 3, n, 9, 0)` (a creation stamp on day Dn). DT0 = `datetime(2026, 3, 5, 9, 0)`. **Yn** = `date(2031, 3, n)`. SDT = `datetime(2031, 1, 2, 3, 4, 5)`.
- **utc_now()** = `datetime.now(timezone.utc).replace(tzinfo=None)`.

**Externals.**
- **clockN(L, U)** (`NN` cards) = for the When, patch `datetime.datetime` with a subclass of `datetime` whose `now()` (any arguments) returns L, and patch `app.utils.time.utcnow` and `app.dao.work_order.utcnow` (`create=True`) to return U. An `NN` card without a clock line runs under clockN(`datetime(2031, 6, 1, 12, 0)`, `datetime(2031, 6, 1, 12, 0)`).
- **clockD(L, U)** = for the When, patch `app.dao.work_order.date` with a subclass of `date` whose `today()` returns L, and patch `app.dao.work_order.utcnow` (`create=True`) and `app.utils.time.utcnow` to return U. Every card that passes `status_scope="planned"` names its clockD.
- **Dhaka** = `db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))` as the first Given step. Nothing else is mocked.

**Standing rows** (every test, this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` three times (`W0.id < W1.id < W2.id`). U1, U2, U3 = `make_profile(db)` three times.
2. W0: F0 = `Factory(workspace_id=W0.id, name="Main Plant", abbreviation="MP0")`, T0 = `WorkOrderType(workspace_id=W0.id, name="Repair")`, M0 = `Machine(workspace_id=W0.id, name="Press 0", factory_id=F0.id)`, P0 = `WorkOrderTemplate(workspace_id=W0.id, template_name="Oil change", work_order_type_id=T0.id)`.
3. W1 factories: FA = `Factory(workspace_id=W1.id, name="East Yard", abbreviation="EY")`, F1 = `(…, "Main Plant", "MP1")`, FB = `(…, "North Yard", "NY")`. Types: TA = `WorkOrderType(workspace_id=W1.id, name="Calibration")`, T1 = `"Repair"`, TB = `"Inspection"`. Machines `Machine(workspace_id=W1.id, name=…, factory_id=…)`: MA `("Press A", F1)`, M1 `("Press 1", F1)`, MB `("Press B", F1)`, MX `("Press X", FA)`, MY `("Press Y", FB)`. Templates `WorkOrderTemplate(workspace_id=W1.id, template_name=…, work_order_type_id=T1.id)`: PA `"Belt check"`, P1 `"Oil change"`, PB `"Filter swap"`. So FA < F1 < FB, TA < T1 < TB, MA < M1 < MB, PA < P1 < PB by id.
4. W2: F2, T2, M2 (`"Press 2"`), P2 — as W0's, with `W2`, abbreviation `"MP2"`.

**Given rows.** Inserted directly (never through `dao`), flushed one at a time in the order written. After "but" a line lists every column that differs. A line written as code is a step to run exactly, at that place.
- **order N** = `WorkOrder(workspace_id=W1.id, work_order_number=N, work_order_type_id=T1.id, title="Oil change", factory_id=F1.id, machine_id=M1.id, created_by=U1.id)`; `status` (`"DRAFT"`), `priority` (`MEDIUM`), `description`, `assigned_to`, `planned_date`, `work_order_template_id` (all `NULL`) and `created_at` (database `now()`) left to defaults unless listed. Status is always a plain string (`status "IN_PROGRESS"`). An order "of W0" uses W0, T0, F0, M0 (template P0 where one is listed); "of W2" uses W2, T2, F2, M2 (P2).
- **completed** = `status "COMPLETED"`, `completed_by U1.id`, `completed_by_names "Karim"`, `completed_at DT0` (what a real complete writes). **voided** = `status "VOIDED"`, `void_note "cancelled"`, `voided_at DT0`, `voided_by U1.id`. **started** = `status "IN_PROGRESS"`, `started_at DT0`, `started_by U1.id`.
- **deleted** = `is_deleted True`, `is_active False`, `deleted_at DT0`, `deleted_by U1.id` (what a real soft delete writes).
- **draft of P1 on d, number N** = order N, but `work_order_template_id P1.id`, `planned_date d` (a "but" after it lists further columns).
- **orders(W, prefix, n)** = `for i in range(1, n + 1):` `db.add(` order of W with `work_order_number f"{prefix}{i:03d}"` `)`, then one `db.flush()`.
- **seqscan** = `db.execute(text("SET LOCAL enable_indexscan = off"))`, then the same for `enable_bitmapscan` and `enable_indexonlyscan`.
- **dirty+pending** = two steps after the rows: `O1.title = "Edited"` (O1 is the card's first row) and `P = ` order `"WO-T-900"` with `db.add(P)` and **no** flush.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` (order is part of the check). **idset(result)** = `{r.id for r in result}`.
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. Money compares as `Decimal`.
- **nothing written** = the number of `work_orders` rows (all workspaces) equals its value before the call.
- `session:` lines check the session directly after the call, before anything expires it.
- `raises: IntegrityError` = `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the step; later `raises:` lines assert on `exc.value.orig`, one per line. `raises: TypeError` = plain `pytest.raises`.
- **commit spy** = `sp = db.begin_nested()` directly before the call, `with patch.object(db, "commit", wraps=db.commit) as cm:` around it; "inside" lines first, then `sp.rollback()`, then the rest.
- **Statement recorder** = the SQL sent during the When is recorded (`before_cursor_execute` listener, as `tests/unit/managers/test_ledger_manager.py`). `selects` = recorded `SELECT`s; `sql` = the one `SELECT` that reads `work_orders`; `order_part` = text of `sql` after its first `ORDER BY`, before any `LIMIT` / `OFFSET` (`""` if none); `written` = every recorded `INSERT`, `UPDATE`, `DELETE`.
- **No-lock check** = `"FOR UPDATE" not in sql`. Never `lock_part == ""`.
- **Clear the session before a one-query check**: a card that counts SELECTs ends its Given with `db.expunge_all()`; ids used in Then come from objects built before it.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`, for results resting on physical row order. Write the call and the checks exactly as shown; never weaken an assertion.

**Race simulations.** None.

## `_work_order_calendar_date_expr` (through `count_by_calendar_date_for_sheet` / `list_for_sheet`)

### WKO-CE-01 — a dated order counts on its planned day, an undated one on its creation day
- **Rules:** `_work_order_calendar_date_expr` R1, R2; `count_by_calendar_date_for_sheet` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D12`, `created_at KD(4)`.
2. B = order `"WO-T-002"`, but `created_at KD(4)`.

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {D12: 1, D4: 1}`.

### WKO-CE-02 — the creation day is the date of created_at as stored, also late in the evening under Dhaka
- **Rules:** `_work_order_calendar_date_expr` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Dhaka.
2. A = order `"WO-T-001"`, but `created_at datetime(2026, 3, 4, 23, 30)`.
3. B = order `"WO-T-002"`, but `created_at datetime(2026, 3, 5, 0, 30)`.

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {D4: 1, D5: 1}`.

### WKO-CE-03 — on the sheet a dated order sits on its planned day, not its creation day
- **Rules:** `_work_order_calendar_date_expr` R1; `_apply_sheet_list_filters` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D12`, `created_at KD(4)`.
2. B = order `"WO-T-002"`, but `created_at KD(4)`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, planned_date_from=D4, planned_date_to=D4, exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [B.id]`.

## `_sheet_base_query` (through `list_for_sheet` / `count_for_sheet`)

### WKO-SB-01 — only W1's rows, with rows of W0 built before and W2 after
- **Rules:** `_sheet_base_query` R1; `list_for_sheet` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0 `"WO-T-001"`.
2. A = order `"WO-T-001"`.
3. B = order `"WO-T-002"`.
4. X2 = order of W2 `"WO-T-001"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, exclude_completed=False, limit=100)`.

**Then**
1. returns: `idset(result) == {A.id, B.id}`.

### WKO-SB-02 — asked for W2, only W2's row, though W0 and W1 rows come earlier
- **Rules:** `_sheet_base_query` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0 `"WO-T-001"`.
2. A = order `"WO-T-001"`.
3. X2 = order of W2 `"WO-T-001"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W2.id, exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [X2.id]`.

### WKO-SB-03 — asked for W0, only W0's row, though W1 and W2 rows come later
- **Rules:** `_sheet_base_query` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0 `"WO-T-001"`.
2. A = order `"WO-T-001"`.
3. X2 = order of W2 `"WO-T-001"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W0.id, exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [X0.id]`.

### WKO-SB-04 — a soft-deleted order is not on the sheet
- **Rules:** `_sheet_base_query` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. B = order `"WO-T-002"`, but deleted.
3. C = order `"WO-T-003"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, exclude_completed=False, limit=100)`.

**Then**
1. returns: `idset(result) == {A.id, C.id}`.

### WKO-SB-05 — an order with no machine is not on the sheet
- **Rules:** `_sheet_base_query` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. B = order `"WO-T-002"`, but `machine_id None`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WKO-SB-06 — the count leaves out other workspaces, deleted and machine-less orders
- **Rules:** `_sheet_base_query` R1, R2, R3; `count_for_sheet` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0 `"WO-T-001"`.
2. A = order `"WO-T-001"`.
3. B = order `"WO-T-002"`, but deleted.
4. C = order `"WO-T-003"`, but `machine_id None`.
5. E = order `"WO-T-004"`.
6. X2 = order of W2 `"WO-T-001"`.

**When**
- `result = dao.count_for_sheet(db, workspace_id=W1.id, exclude_completed=False)`.

**Then**
1. returns: `result == 2`.

## `_apply_sheet_list_filters` (through `list_for_sheet`)

### WKO-SF-01 — factory_id keeps that factory only, between a lower and a higher factory
- **Rules:** `_apply_sheet_list_filters` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `factory_id FA.id`, `machine_id MX.id`.
2. B = order `"WO-T-002"`.
3. C = order `"WO-T-003"`, but `factory_id FB.id`, `machine_id MY.id`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, factory_id=F1.id, exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-SF-02 — machine_id keeps that machine only, between a lower and a higher machine
- **Rules:** `_apply_sheet_list_filters` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `machine_id MA.id`.
2. B = order `"WO-T-002"`.
3. C = order `"WO-T-003"`, but `machine_id MB.id`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, machine_id=M1.id, exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-SF-03 — work_order_type_id keeps that type only, between a lower and a higher type
- **Rules:** `_apply_sheet_list_filters` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `work_order_type_id TA.id`.
2. B = order `"WO-T-002"`.
3. C = order `"WO-T-003"`, but `work_order_type_id TB.id`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, work_order_type_id=T1.id, exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-SF-04 — priority keeps that priority only
- **Rules:** `_apply_sheet_list_filters` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `priority PR.LOW`.
2. B = order `"WO-T-002"`, but `priority PR.MEDIUM`.
3. C = order `"WO-T-003"`, but `priority PR.HIGH`.
4. E = order `"WO-T-004"`, but `priority PR.URGENT`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, priority=PR.HIGH, exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### WKO-SF-05 — falsy filters (0 and "") filter nothing
- **Rules:** `_apply_sheet_list_filters` Purpose (a falsy argument is skipped)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `factory_id FA.id`, `machine_id MX.id`, `work_order_type_id TA.id`.
2. B = order `"WO-T-002"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, factory_id=0, machine_id=0, work_order_type_id=0, search="", exclude_completed=False, limit=100)`.

**Then**
1. returns: `idset(result) == {A.id, B.id}`.

### WKO-SF-06 — planned_date_from is inclusive on the calendar day and keeps an undated order created that day
- **Rules:** `_apply_sheet_list_filters` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D9`.
2. B = order `"WO-T-002"`, but `planned_date D10`.
3. C = order `"WO-T-003"`, but `planned_date D11`.
4. E = order `"WO-T-004"`, but `created_at KD(10)`.
5. G = order `"WO-T-005"`, but `created_at KD(9)`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, planned_date_from=D10, exclude_completed=False, limit=100)`.

**Then**
1. returns: `idset(result) == {B.id, C.id, E.id}`.

### WKO-SF-07 — planned_date_to is inclusive on the calendar day
- **Rules:** `_apply_sheet_list_filters` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D9`.
2. B = order `"WO-T-002"`, but `planned_date D10`.
3. C = order `"WO-T-003"`, but `planned_date D11`.
4. E = order `"WO-T-004"`, but `created_at KD(10)`.
5. G = order `"WO-T-005"`, but `created_at KD(11)`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, planned_date_to=D10, exclude_completed=False, limit=100)`.

**Then**
1. returns: `idset(result) == {A.id, B.id, E.id}`.

### WKO-SF-08 — from after to gives nothing
- **Rules:** `_apply_sheet_list_filters` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`.
2. B = order `"WO-T-002"`, but `planned_date D11`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, planned_date_from=D11, planned_date_to=D10, exclude_completed=False, limit=100)`.

**Then**
1. returns: `result == []`.

### WKO-SF-09 — status keeps exactly that status
- **Rules:** `_apply_sheet_list_filters` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. B = order `"WO-T-002"`, but started.
3. C = order `"WO-T-003"`, but completed.
4. E = order `"WO-T-004"`, but voided.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, status=ST.IN_PROGRESS, exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-SF-10 — "planned" keeps drafts planned strictly after today only
- **Rules:** `_apply_sheet_list_filters` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date Y9`.
2. B = order `"WO-T-002"`, but `planned_date Y10`.
3. C = order `"WO-T-003"`, but `planned_date Y11`.
4. E = order `"WO-T-004"` (an undated draft).
5. G = order `"WO-T-005"`, but `planned_date Y11`, started.

**When**
- under clockD(`Y10`, `datetime(2031, 3, 10, 12, 0)`): `result = dao.list_for_sheet(db, workspace_id=W1.id, status_scope="planned", exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### WKO-SF-11 — "planned" replaces a status sent with it
- **Rules:** `_apply_sheet_list_filters` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date Y11`.
2. B = order `"WO-T-002"`, but `planned_date Y11`, completed.

**When**
- under clockD(`Y10`, `datetime(2031, 3, 10, 12, 0)`): `result = dao.list_for_sheet(db, workspace_id=W1.id, status=ST.COMPLETED, status_scope="planned", exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WKO-SF-12 — "planned" uses the UTC date: local 10 Nov, UTC 11 Nov, a draft for 11 Nov is not planned
- **Rules:** `_apply_sheet_list_filters` R6 [BUG-2673]
- **Kind:** bug
- **Expect:** xfail BUG-2673
- **Fails today on:** Then 2 (today the local date 10 Nov is used, so the draft for 11 Nov is kept)

**Given**
1. A = order `"WO-T-001"`, but `planned_date date(2031, 11, 11)`.
2. B = order `"WO-T-002"`, but `planned_date date(2031, 11, 12)`.

**When**
- under clockD(`date(2031, 11, 10)`, `datetime(2031, 11, 11, 3, 0)`): `result = dao.list_for_sheet(db, workspace_id=W1.id, status_scope="planned", exclude_completed=False, limit=100)`.

**Then**
1. returns: `B.id in idset(result)`.
2. returns: `idset(result) == {B.id}`.

### WKO-SF-13 — "planned" uses the UTC date: local 11 Nov, UTC 10 Nov, a draft for 11 Nov is planned
- **Rules:** `_apply_sheet_list_filters` R6 [BUG-2673]
- **Kind:** bug
- **Expect:** xfail BUG-2673
- **Fails today on:** Then 2 (today the local date 11 Nov is used, so the draft for 11 Nov is dropped)

**Given**
1. A = order `"WO-T-001"`, but `planned_date date(2031, 11, 11)`.
2. B = order `"WO-T-002"`, but `planned_date date(2031, 11, 12)`.

**When**
- under clockD(`date(2031, 11, 11)`, `datetime(2031, 11, 10, 22, 0)`): `result = dao.list_for_sheet(db, workspace_id=W1.id, status_scope="planned", exclude_completed=False, limit=100)`.

**Then**
1. returns: `B.id in idset(result)`.
2. returns: `idset(result) == {A.id, B.id}`.

### WKO-SF-14 — an unknown status_scope is ignored and the status filter applies
- **Rules:** `_apply_sheet_list_filters` R7 (the DAO half; the endpoint's 422 is deferred)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date Y9`.
2. B = order `"WO-T-002"` (an undated draft).
3. C = order `"WO-T-003"`, but `planned_date Y11`, started.

**When**
- under clockD(`Y10`, `datetime(2031, 3, 10, 12, 0)`): `result = dao.list_for_sheet(db, workspace_id=W1.id, status=ST.DRAFT, status_scope="bogus", exclude_completed=False, limit=100)`.

**Then**
1. returns: `idset(result) == {A.id, B.id}`.

### WKO-SF-15 — status_scope "Planned" (capital P) is not "planned" and filters nothing
- **Rules:** `_apply_sheet_list_filters` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date Y9`.
2. B = order `"WO-T-002"`, but `planned_date Y11`, completed.

**When**
- under clockD(`Y10`, `datetime(2031, 3, 10, 12, 0)`): `result = dao.list_for_sheet(db, workspace_id=W1.id, status_scope="Planned", exclude_completed=False, limit=100)`.

**Then**
1. returns: `idset(result) == {A.id, B.id}`.

### WKO-SF-16 — exclude_completed drops COMPLETED only
- **Rules:** `_apply_sheet_list_filters` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. B = order `"WO-T-002"`, but started.
3. C = order `"WO-T-003"`, but completed.
4. E = order `"WO-T-004"`, but voided.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, exclude_completed=True, limit=100)`.

**Then**
1. returns: `idset(result) == {A.id, B.id, E.id}`.

### WKO-SF-17 — exclude_completed with status COMPLETED leaves nothing
- **Rules:** `_apply_sheet_list_filters` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but completed.
2. B = order `"WO-T-002"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, status=ST.COMPLETED, exclude_completed=True, limit=100)`.

**Then**
1. returns: `result == []`.

### WKO-SF-18 — search finds a part in the middle of the number, any case, with NULL description and assignee
- **Rules:** `_apply_sheet_list_filters` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-731"`.
2. B = order `"WO-T-845"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, search="t-73", exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WKO-SF-19 — search finds a part in the middle of the description, typed in capitals
- **Rules:** `_apply_sheet_list_filters` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `description "Replace hydraulic seal"`.
2. B = order `"WO-T-002"`, but `description "Replace belt"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, search="HYDRAULIC", exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WKO-SF-20 — search finds a part in the middle of assigned_to
- **Rules:** `_apply_sheet_list_filters` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `assigned_to "Karim Uddin"`.
2. B = order `"WO-T-002"`, but `assigned_to "Rahim Ali"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, search="rim ud", exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WKO-SF-21 — the search text is trimmed; a stored value with a leading space still matches
- **Rules:** `_apply_sheet_list_filters` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `description " hydraulic seal"`.
2. B = order `"WO-T-002"`, but `description "Replace belt"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, search="  hydraulic  ", exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WKO-SF-22 — a match in any one of number, description or assignee is enough
- **Rules:** `_apply_sheet_list_filters` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-ZETA-1"`.
2. B = order `"WO-T-002"`, but `description "zeta drive"`.
3. C = order `"WO-T-003"`, but `assigned_to "Zeta Team"`.
4. E = order `"WO-T-004"`, but `description "belt"`, `assigned_to "Ali"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, search="Zeta", exclude_completed=False, limit=100)`.

**Then**
1. returns: `idset(result) == {A.id, B.id, C.id}`.

### WKO-SF-23 — the title is not searched
- **Rules:** `_apply_sheet_list_filters` R9 (Q5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"` (its title is `"Oil change"`).
2. B = order `"WO-T-002"`, but `title "Belt swap"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, search="Oil", exclude_completed=False, limit=100)`.

**Then**
1. returns: `result == []`.

### WKO-SF-24 — a whitespace-only search keeps every row
- **Rules:** `_apply_sheet_list_filters` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. B = order `"WO-T-002"`, but `description "belt"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, search="   ", exclude_completed=False, limit=100)`.

**Then**
1. returns: `idset(result) == {A.id, B.id}`.

### WKO-SF-25 — `_` in the search matches only a real underscore
- **Rules:** `_apply_sheet_list_filters` R10 [BUG-2672]
- **Kind:** bug
- **Expect:** xfail BUG-2672
- **Fails today on:** Then 2 (today `_` matches any one character, so B comes back too)

**Given**
1. A = order `"WO-T-001"`, but `description "belt_a"`.
2. B = order `"WO-T-002"`, but `description "beltxa"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, search="t_a", exclude_completed=False, limit=100)`.

**Then**
1. returns: `A.id in idset(result)`.
2. returns: `idset(result) == {A.id}`.

### WKO-SF-26 — `%` in the search matches only a real percent sign
- **Rules:** `_apply_sheet_list_filters` R10 [BUG-2672]
- **Kind:** bug
- **Expect:** xfail BUG-2672
- **Fails today on:** Then 2 (today `%` matches anything, so B comes back too)

**Given**
1. A = order `"WO-T-001"`, but `description "50% wear"`.
2. B = order `"WO-T-002"`, but `description "50 mm wear"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, search="50% w", exclude_completed=False, limit=100)`.

**Then**
1. returns: `A.id in idset(result)`.
2. returns: `idset(result) == {A.id}`.

### WKO-SF-27 — a backslash in the search matches a real backslash
- **Rules:** `_apply_sheet_list_filters` R10 [BUG-2672]
- **Kind:** bug
- **Expect:** xfail BUG-2672
- **Fails today on:** Then 1 (today `\` escapes the next character, so A is not found and B is)

**Given**
1. A = order `"WO-T-001"`, but `description "C:\\tmp"` (Python literal; the stored text is `C:\tmp`).
2. B = order `"WO-T-002"`, but `description "C:tmp"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, search="C:\\tmp", exclude_completed=False, limit=100)`.

**Then**
1. returns: `idset(result) == {A.id}`.

### WKO-SF-28 — plain letters next to an underscore in the stored text still match
- **Rules:** `_apply_sheet_list_filters` R9, R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `description "belt_a"`.
2. B = order `"WO-T-002"`, but `description "gear"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, search="belt", exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WKO-SF-29 — filters combine with AND
- **Rules:** `_apply_sheet_list_filters` Purpose (AND); `_sheet_base_query` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `description "seal"`.
2. B = order `"WO-T-002"`, but `description "seal"`, `machine_id MB.id`.
3. C = order `"WO-T-003"`, but `description "seal"`, started.
4. E = order `"WO-T-004"`, but `description "belt"`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, machine_id=M1.id, status=ST.DRAFT, search="seal", exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [A.id]`.

## `WorkOrderDAO.get_by_workspace`

### WKO-GW-01 — the workspace's orders, newest first, with an older row holding a higher id
- **Rules:** `get_by_workspace` R1, R11 (the part that holds today), Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `created_at C10`.
2. B = order `"WO-T-002"`, but `created_at C12`.
3. C = order `"WO-T-003"`, but `created_at C9`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `all(isinstance(r, WorkOrder) for r in result)`.
2. returns: `ids(result) == [B.id, A.id, C.id]`.

### WKO-GW-02 — only W1's rows, with W0 built before and W2 after
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0 `"WO-T-001"`.
2. A = order `"WO-T-001"`.
3. X2 = order of W2 `"WO-T-001"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WKO-GW-03 — asked for W2, only W2's row
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0 `"WO-T-001"`.
2. A = order `"WO-T-001"`.
3. X2 = order of W2 `"WO-T-001"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X2.id]`.

### WKO-GW-04 — asked for W0, only W0's row
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0 `"WO-T-001"`.
2. A = order `"WO-T-001"`.
3. X2 = order of W2 `"WO-T-001"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W0.id)`.

**Then**
1. returns: `ids(result) == [X0.id]`.

### WKO-GW-05 — soft-deleted orders are left out
- **Rules:** `get_by_workspace` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `created_at C9`.
2. B = order `"WO-T-002"`, but `created_at C10`, deleted.
3. C = order `"WO-T-003"`, but `created_at C11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id, A.id]`.

### WKO-GW-06 — an order with no machine is included
- **Rules:** `get_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `created_at C9`.
2. B = order `"WO-T-002"`, but `created_at C10`, `machine_id None`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### WKO-GW-07 — work_order_type_id keeps that type only, between a lower and a higher type
- **Rules:** `get_by_workspace` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `work_order_type_id TA.id`.
2. B = order `"WO-T-002"`.
3. C = order `"WO-T-003"`, but `work_order_type_id TB.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, work_order_type_id=T1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-GW-08 — falsy type, factory and machine ids filter nothing
- **Rules:** `get_by_workspace` R2, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `work_order_type_id TA.id`, `factory_id FA.id`, `machine_id MX.id`.
2. B = order `"WO-T-002"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, work_order_type_id=0, factory_id=0, machine_id=0)`.

**Then**
1. returns: `idset(result) == {A.id, B.id}`.

### WKO-GW-09 — status keeps that status only
- **Rules:** `get_by_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. B = order `"WO-T-002"`, but started.
3. C = order `"WO-T-003"`, but completed.
4. E = order `"WO-T-004"`, but voided.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, status=ST.IN_PROGRESS)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-GW-10 — no status gives every status, VOIDED included
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. B = order `"WO-T-002"`, but started.
3. C = order `"WO-T-003"`, but completed.
4. E = order `"WO-T-004"`, but voided.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, status=None)`.

**Then**
1. returns: `idset(result) == {A.id, B.id, C.id, E.id}`.

### WKO-GW-11 — priority keeps that priority only
- **Rules:** `get_by_workspace` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `priority PR.LOW`.
2. B = order `"WO-T-002"`, but `priority PR.MEDIUM`.
3. C = order `"WO-T-003"`, but `priority PR.HIGH`.
4. E = order `"WO-T-004"`, but `priority PR.URGENT`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, priority=PR.URGENT)`.

**Then**
1. returns: `ids(result) == [E.id]`.

### WKO-GW-12 — factory_id keeps that factory only, between a lower and a higher factory
- **Rules:** `get_by_workspace` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `factory_id FA.id`, `machine_id MX.id`.
2. B = order `"WO-T-002"`.
3. C = order `"WO-T-003"`, but `factory_id FB.id`, `machine_id MY.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-GW-13 — machine_id keeps that machine only, between a lower and a higher machine
- **Rules:** `get_by_workspace` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `machine_id MA.id`.
2. B = order `"WO-T-002"`.
3. C = order `"WO-T-003"`, but `machine_id MB.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-GW-14 — work_order_template_id keeps that template only, between a lower and a higher template
- **Rules:** `get_by_workspace` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `work_order_template_id PA.id`.
2. B = order `"WO-T-002"`, but `work_order_template_id P1.id`.
3. C = order `"WO-T-003"`, but `work_order_template_id PB.id`.
4. E = order `"WO-T-004"` (no template).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, work_order_template_id=P1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-GW-15 — work_order_template_id 0 filters and matches nothing
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `work_order_template_id P1.id`.
2. B = order `"WO-T-002"` (no template).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, work_order_template_id=0)`.

**Then**
1. returns: `result == []`.

### WKO-GW-16 — no template filter keeps orders with and without a template
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `work_order_template_id P1.id`.
2. B = order `"WO-T-002"` (no template).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, work_order_template_id=None)`.

**Then**
1. returns: `idset(result) == {A.id, B.id}`.

### WKO-GW-17 — filters combine with AND
- **Rules:** `get_by_workspace` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. B = order `"WO-T-002"`, but started.
3. C = order `"WO-T-003"`, but `work_order_type_id TB.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, work_order_type_id=T1.id, status=ST.DRAFT)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WKO-GW-18 — planned_date_from is inclusive and drops undated orders
- **Rules:** `get_by_workspace` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D9`.
2. B = order `"WO-T-002"`, but `planned_date D10`.
3. C = order `"WO-T-003"`, but `planned_date D11`.
4. E = order `"WO-T-004"`, but `created_at KD(10)` (undated, created on D10).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, planned_date_from=D10)`.

**Then**
1. returns: `idset(result) == {B.id, C.id}`.

### WKO-GW-19 — planned_date_to is inclusive and drops undated orders
- **Rules:** `get_by_workspace` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D9`.
2. B = order `"WO-T-002"`, but `planned_date D10`.
3. C = order `"WO-T-003"`, but `planned_date D11`.
4. E = order `"WO-T-004"`, but `created_at KD(10)` (undated, created on D10).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, planned_date_to=D10)`.

**Then**
1. returns: `idset(result) == {A.id, B.id}`.

### WKO-GW-20 — both bounds on one day give that day only
- **Rules:** `get_by_workspace` R8, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D9`.
2. B = order `"WO-T-002"`, but `planned_date D10`.
3. C = order `"WO-T-003"`, but `planned_date D11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, planned_date_from=D10, planned_date_to=D10)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-GW-21 — from after to gives nothing
- **Rules:** `get_by_workspace` R8, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`.
2. B = order `"WO-T-002"`, but `planned_date D11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, planned_date_from=D11, planned_date_to=D10)`.

**Then**
1. returns: `result == []`.

### WKO-GW-22 — skip and limit page the newest-first order
- **Rules:** `get_by_workspace` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `created_at C9`.
2. B = order `"WO-T-002"`, but `created_at C10`.
3. C = order `"WO-T-003"`, but `created_at C11`.
4. E = order `"WO-T-004"`, but `created_at C12`.
5. G = order `"WO-T-005"`, but `created_at C13`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [E.id, C.id]`.

### WKO-GW-23 — by default the first 100 rows come back
- **Rules:** `get_by_workspace` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. orders(W1, "WO-T-", 101).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### WKO-GW-24 — limit=1000 returns 1000 of 1001 rows
- **Rules:** `get_by_workspace` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. orders(W1, "WO-T-", 1001).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 1000`.

### WKO-GW-25 — filters apply before paging: a newer deleted row and a newer W2 row do not take a place
- **Rules:** `get_by_workspace` R1, R7, R10 (HR-5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `created_at C9`.
2. B = order `"WO-T-002"`, but `created_at C10`.
3. C = order `"WO-T-003"`, but `created_at C11`.
4. E = order `"WO-T-004"`, but `created_at C13`, deleted.
5. X2 = order of W2 `"WO-T-001"`, but `created_at C14`.
6. G = order `"WO-T-005"`, but `created_at C12`, started.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, status=ST.DRAFT, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-GW-26 — the SQL orders by created_at descending first
- **Rules:** `get_by_workspace` R11 (the part that holds today and after the fix)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. `db.expunge_all()`.

**When**
- Statement recorder: `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `order_part.startswith("work_orders.created_at DESC")`.

### WKO-GW-27 — the SQL breaks a created_at tie by id descending
- **Rules:** `get_by_workspace` R11 [BUG-2670]
- **Kind:** bug
- **Expect:** xfail BUG-2670
- **Fails today on:** Then 2 (today the ORDER BY is `work_orders.created_at DESC` only)

**Given**
1. A = order `"WO-T-001"`.
2. `db.expunge_all()`.

**When**
- Statement recorder: `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `"work_orders.id DESC" in order_part`.

### WKO-GW-28 — two orders made in one transaction come back higher id first
- **Rules:** `get_by_workspace` R11 [BUG-2670]
- **Kind:** bug
- **Expect:** xfail BUG-2670 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (today the tie comes back in physical order, lower id first)

**Given**
1. A = order `"WO-T-001"` (`created_at` left to the database default).
2. B = order `"WO-T-002"` (same transaction, so the same `created_at`).
3. seqscan.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### WKO-GW-29 — one SELECT, no lock, nothing written
- **Rules:** `get_by_workspace` Side effects (none); Overview (no lock)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. `db.expunge_all()`.

**When**
- Statement recorder: `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `len(selects) == 1`.
3. returns: `"FOR UPDATE" not in sql`.
4. returns: `written == []`.

### WKO-GW-30 — a pending order stays pending and unlisted; an unflushed edit stays unflushed
- **Rules:** `get_by_workspace` Side effects (none)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = order `"WO-T-001"`.
2. dirty+pending.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. session: `len(db.new) == 1`.
2. session: `P in db.new`.
3. session: `O1 in db.dirty`.
4. session: `len(db.dirty) == 1`.
5. session: `not db.deleted`.
6. returns: `ids(result) == [O1.id]`.

## `WorkOrderDAO.list_future_drafts_for_template_machine`

### WKO-FD-01 — the template's future drafts on the machine, by planned date, whatever the insert order
- **Rules:** `list_future_drafts_for_template_machine` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = draft of P1 on D13, number `"WO-T-001"`.
2. B = draft of P1 on D11, number `"WO-T-002"`.
3. C = draft of P1 on D12, number `"WO-T-003"`.

**When**
- `result = dao.list_future_drafts_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, after_date=D10)`.

**Then**
1. returns: `ids(result) == [B.id, C.id, A.id]`.

### WKO-FD-02 — a draft on after_date itself or before is left out; the next day is in
- **Rules:** `list_future_drafts_for_template_machine` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = draft of P1 on D9, number `"WO-T-001"`.
2. B = draft of P1 on D10, number `"WO-T-002"`.
3. C = draft of P1 on D11, number `"WO-T-003"`.

**When**
- `result = dao.list_future_drafts_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, after_date=D10)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### WKO-FD-03 — IN_PROGRESS, COMPLETED and VOIDED orders are left out
- **Rules:** `list_future_drafts_for_template_machine` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = draft of P1 on D12, number `"WO-T-001"`, but started.
2. B = draft of P1 on D12, number `"WO-T-002"`, but completed.
3. C = draft of P1 on D12, number `"WO-T-003"`, but voided.
4. E = draft of P1 on D12, number `"WO-T-004"`.

**When**
- `result = dao.list_future_drafts_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, after_date=D10)`.

**Then**
1. returns: `ids(result) == [E.id]`.

### WKO-FD-04 — an undated draft is left out
- **Rules:** `list_future_drafts_for_template_machine` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `work_order_template_id P1.id` (no planned date).
2. B = draft of P1 on D12, number `"WO-T-002"`.

**When**
- `result = dao.list_future_drafts_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, after_date=D10)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-FD-05 — drafts of a lower and a higher template, and of no template, are left out
- **Rules:** `list_future_drafts_for_template_machine` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = draft of P1 on D12, number `"WO-T-001"`, but `work_order_template_id PA.id`.
2. B = draft of P1 on D12, number `"WO-T-002"`.
3. C = draft of P1 on D12, number `"WO-T-003"`, but `work_order_template_id PB.id`.
4. E = order `"WO-T-004"`, but `planned_date D12` (no template).

**When**
- `result = dao.list_future_drafts_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, after_date=D10)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-FD-06 — drafts on a lower and a higher machine are left out
- **Rules:** `list_future_drafts_for_template_machine` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = draft of P1 on D12, number `"WO-T-001"`, but `machine_id MA.id`.
2. B = draft of P1 on D12, number `"WO-T-002"`.
3. C = draft of P1 on D12, number `"WO-T-003"`, but `machine_id MB.id`.

**When**
- `result = dao.list_future_drafts_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, after_date=D10)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-FD-07 — asked for W0 with W1's template and machine, nothing comes back
- **Rules:** `list_future_drafts_for_template_machine` R2 (other workspaces)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0 `"WO-T-001"`, but `work_order_template_id P0.id`, `planned_date D12`.
2. B = draft of P1 on D12, number `"WO-T-002"`.

**When**
- `result = dao.list_future_drafts_for_template_machine(db, workspace_id=W0.id, work_order_template_id=P1.id, machine_id=M1.id, after_date=D10)`.

**Then**
1. returns: `result == []`.

### WKO-FD-08 — asked for W2 with W1's template and machine, nothing comes back
- **Rules:** `list_future_drafts_for_template_machine` R2 (other workspaces)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = draft of P1 on D12, number `"WO-T-002"`.
2. X2 = order of W2 `"WO-T-001"`, but `work_order_template_id P2.id`, `planned_date D12`.

**When**
- `result = dao.list_future_drafts_for_template_machine(db, workspace_id=W2.id, work_order_template_id=P1.id, machine_id=M1.id, after_date=D10)`.

**Then**
1. returns: `result == []`.

### WKO-FD-09 — a soft-deleted draft is left out
- **Rules:** `list_future_drafts_for_template_machine` R1, R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = draft of P1 on D11, number `"WO-T-001"`, but deleted.
2. B = draft of P1 on D12, number `"WO-T-002"`.

**When**
- `result = dao.list_future_drafts_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, after_date=D10)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-FD-10 — on one planned date the lower id comes first, also when the higher id was inserted first
- **Rules:** `list_future_drafts_for_template_machine` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. H = draft of P1 on D12, number `"WO-T-001"`, but `id XID(1)`.
2. L = draft of P1 on D12, number `"WO-T-002"`.
3. seqscan.

**When**
- `result = dao.list_future_drafts_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, after_date=D10)`.

**Then**
1. returns: `ids(result) == [L.id, H.id]`.

### WKO-FD-11 — no limit: all 150 future drafts come back
- **Rules:** `list_future_drafts_for_template_machine` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for i in range(150):` `db.add(` draft of P1 on D12, number `f"WO-T-{i:03d}"` `)`, then one `db.flush()`.

**When**
- `result = dao.list_future_drafts_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, after_date=D10)`.

**Then**
1. returns: `len(result) == 150`.

### WKO-FD-12 — one SELECT, no lock, nothing written
- **Rules:** `list_future_drafts_for_template_machine` Side effects (none)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = draft of P1 on D12, number `"WO-T-001"`.
2. `db.expunge_all()`.

**When**
- Statement recorder: `result = dao.list_future_drafts_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, after_date=D10)`.

**Then**
1. returns: `ids(result) == [B.id]`.
2. returns: `len(selects) == 1`.
3. returns: `"FOR UPDATE" not in sql`.
4. returns: `written == []`.

## `WorkOrderDAO.list_drafts_outside_range_for_template_machine`

### WKO-OR-01 — drafts before the start and after the end, by date; the range's inside and both edges stay out
- **Rules:** `list_drafts_outside_range_for_template_machine` R1, R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = draft of P1 on D13, number `"WO-T-001"`.
2. B = draft of P1 on D10, number `"WO-T-002"`.
3. C = draft of P1 on D11, number `"WO-T-003"`.
4. E = draft of P1 on D12, number `"WO-T-004"`.
5. G = draft of P1 on D9, number `"WO-T-005"`.

**When**
- `result = dao.list_drafts_outside_range_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, range_start=D10, range_end=D12)`.

**Then**
1. returns: `ids(result) == [G.id, A.id]`.

### WKO-OR-02 — IN_PROGRESS, COMPLETED and VOIDED orders outside the range are left out
- **Rules:** `list_drafts_outside_range_for_template_machine` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = draft of P1 on D9, number `"WO-T-001"`, but started.
2. B = draft of P1 on D9, number `"WO-T-002"`, but completed.
3. C = draft of P1 on D9, number `"WO-T-003"`, but voided.
4. E = draft of P1 on D9, number `"WO-T-004"`.

**When**
- `result = dao.list_drafts_outside_range_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, range_start=D10, range_end=D12)`.

**Then**
1. returns: `ids(result) == [E.id]`.

### WKO-OR-03 — an undated draft is left out
- **Rules:** `list_drafts_outside_range_for_template_machine` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `work_order_template_id P1.id` (no planned date).
2. B = draft of P1 on D13, number `"WO-T-002"`.

**When**
- `result = dao.list_drafts_outside_range_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, range_start=D10, range_end=D12)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-OR-04 — drafts of a lower and a higher template, and of no template, are left out
- **Rules:** `list_drafts_outside_range_for_template_machine` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = draft of P1 on D13, number `"WO-T-001"`, but `work_order_template_id PA.id`.
2. B = draft of P1 on D13, number `"WO-T-002"`.
3. C = draft of P1 on D13, number `"WO-T-003"`, but `work_order_template_id PB.id`.
4. E = order `"WO-T-004"`, but `planned_date D13` (no template).

**When**
- `result = dao.list_drafts_outside_range_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, range_start=D10, range_end=D12)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-OR-05 — drafts on a lower and a higher machine are left out
- **Rules:** `list_drafts_outside_range_for_template_machine` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = draft of P1 on D13, number `"WO-T-001"`, but `machine_id MA.id`.
2. B = draft of P1 on D13, number `"WO-T-002"`.
3. C = draft of P1 on D13, number `"WO-T-003"`, but `machine_id MB.id`.

**When**
- `result = dao.list_drafts_outside_range_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, range_start=D10, range_end=D12)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-OR-06 — asked for W0 with W1's template and machine, nothing comes back
- **Rules:** `list_drafts_outside_range_for_template_machine` R2 (other workspaces)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0 `"WO-T-001"`, but `work_order_template_id P0.id`, `planned_date D13`.
2. B = draft of P1 on D13, number `"WO-T-002"`.

**When**
- `result = dao.list_drafts_outside_range_for_template_machine(db, workspace_id=W0.id, work_order_template_id=P1.id, machine_id=M1.id, range_start=D10, range_end=D12)`.

**Then**
1. returns: `result == []`.

### WKO-OR-07 — asked for W2 with W1's template and machine, nothing comes back
- **Rules:** `list_drafts_outside_range_for_template_machine` R2 (other workspaces)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = draft of P1 on D13, number `"WO-T-002"`.
2. X2 = order of W2 `"WO-T-001"`, but `work_order_template_id P2.id`, `planned_date D13`.

**When**
- `result = dao.list_drafts_outside_range_for_template_machine(db, workspace_id=W2.id, work_order_template_id=P1.id, machine_id=M1.id, range_start=D10, range_end=D12)`.

**Then**
1. returns: `result == []`.

### WKO-OR-08 — a soft-deleted draft outside the range is left out
- **Rules:** `list_drafts_outside_range_for_template_machine` R1, R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = draft of P1 on D9, number `"WO-T-001"`, but deleted.
2. B = draft of P1 on D13, number `"WO-T-002"`.

**When**
- `result = dao.list_drafts_outside_range_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, range_start=D10, range_end=D12)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-OR-09 — start after end returns every dated draft
- **Rules:** `list_drafts_outside_range_for_template_machine` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = draft of P1 on D9, number `"WO-T-001"`.
2. B = draft of P1 on D10, number `"WO-T-002"`.
3. C = draft of P1 on D11, number `"WO-T-003"`.
4. E = draft of P1 on D12, number `"WO-T-004"`.
5. G = draft of P1 on D13, number `"WO-T-005"`.

**When**
- `result = dao.list_drafts_outside_range_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, range_start=D12, range_end=D10)`.

**Then**
1. returns: `ids(result) == [A.id, B.id, C.id, E.id, G.id]`.

### WKO-OR-10 — a one-day range keeps that day out and returns the days around it
- **Rules:** `list_drafts_outside_range_for_template_machine` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = draft of P1 on D10, number `"WO-T-001"`.
2. B = draft of P1 on D11, number `"WO-T-002"`.
3. C = draft of P1 on D12, number `"WO-T-003"`.

**When**
- `result = dao.list_drafts_outside_range_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, range_start=D11, range_end=D11)`.

**Then**
1. returns: `ids(result) == [A.id, C.id]`.

### WKO-OR-11 — on one planned date the lower id comes first, also when the higher id was inserted first
- **Rules:** `list_drafts_outside_range_for_template_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. H = draft of P1 on D13, number `"WO-T-001"`, but `id XID(1)`.
2. L = draft of P1 on D13, number `"WO-T-002"`.
3. seqscan.

**When**
- `result = dao.list_drafts_outside_range_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, range_start=D10, range_end=D12)`.

**Then**
1. returns: `ids(result) == [L.id, H.id]`.

### WKO-OR-12 — no limit: all 150 drafts outside the range come back
- **Rules:** `list_drafts_outside_range_for_template_machine` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for i in range(150):` `db.add(` draft of P1 on D13, number `f"WO-T-{i:03d}"` `)`, then one `db.flush()`.

**When**
- `result = dao.list_drafts_outside_range_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, range_start=D10, range_end=D12)`.

**Then**
1. returns: `len(result) == 150`.

### WKO-OR-13 — one SELECT, no lock, nothing written
- **Rules:** `list_drafts_outside_range_for_template_machine` Side effects (none)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = draft of P1 on D13, number `"WO-T-001"`.
2. `db.expunge_all()`.

**When**
- Statement recorder: `result = dao.list_drafts_outside_range_for_template_machine(db, workspace_id=W1.id, work_order_template_id=P1.id, machine_id=M1.id, range_start=D10, range_end=D12)`.

**Then**
1. returns: `ids(result) == [B.id]`.
2. returns: `len(selects) == 1`.
3. returns: `"FOR UPDATE" not in sql`.
4. returns: `written == []`.

## `WorkOrderDAO.get_by_machine_date_type`

### WKO-MD-01 — a draft of the same machine, day and type is found
- **Rules:** `get_by_machine_date_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = draft of P1 on D9, number `"WO-T-001"`.
2. B = draft of P1 on D10, number `"WO-T-002"`.
3. C = draft of P1 on D11, number `"WO-T-003"`.

**When**
- `result = dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `isinstance(result, WorkOrder)`.
2. returns: `result.id == B.id`.

### WKO-MD-02 — a manual order (no template) counts
- **Rules:** `get_by_machine_date_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10` (no template).

**When**
- `result = dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result.id == A.id`.

### WKO-MD-03 — an IN_PROGRESS order counts
- **Rules:** `get_by_machine_date_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, started.

**When**
- `result = dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result.id == A.id`.

### WKO-MD-04 — a COMPLETED order counts
- **Rules:** `get_by_machine_date_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, completed.

**When**
- `result = dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result.id == A.id`.

### WKO-MD-05 — a VOIDED order alone gives None
- **Rules:** `get_by_machine_date_type` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, voided.

**When**
- `result = dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result is None`.

### WKO-MD-06 — next to a newer VOIDED order, the COMPLETED one is returned
- **Rules:** `get_by_machine_date_type` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, completed, `created_at C9`.
2. B = order `"WO-T-002"`, but `planned_date D10`, voided, `created_at C12`.

**When**
- `result = dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result.id == A.id`.

### WKO-MD-07 — a soft-deleted match alone gives None
- **Rules:** `get_by_machine_date_type` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, deleted.

**When**
- `result = dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result is None`.

### WKO-MD-08 — orders on a lower and a higher machine give None
- **Rules:** `get_by_machine_date_type` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, `machine_id MA.id`.
2. B = order `"WO-T-002"`, but `planned_date D10`, `machine_id MB.id`.

**When**
- `result = dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result is None`.

### WKO-MD-09 — orders on the day before and the day after give None
- **Rules:** `get_by_machine_date_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D9`.
2. B = order `"WO-T-002"`, but `planned_date D11`.

**When**
- `result = dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result is None`.

### WKO-MD-10 — orders of a lower and a higher type give None
- **Rules:** `get_by_machine_date_type` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, `work_order_type_id TA.id`.
2. B = order `"WO-T-002"`, but `planned_date D10`, `work_order_type_id TB.id`.

**When**
- `result = dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result is None`.

### WKO-MD-11 — an undated order created that day gives None
- **Rules:** `get_by_machine_date_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `created_at KD(10)` (no planned date).

**When**
- `result = dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result is None`.

### WKO-MD-12 — asked for W0 with W1's machine and type, None
- **Rules:** `get_by_machine_date_type` R2 (other workspace)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0 `"WO-T-001"`, but `planned_date D10`.
2. A = order `"WO-T-001"`, but `planned_date D10`.

**When**
- `result = dao.get_by_machine_date_type(db, workspace_id=W0.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result is None`.

### WKO-MD-13 — asked for W2 with W1's machine and type, None
- **Rules:** `get_by_machine_date_type` R2 (other workspace)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`.
2. X2 = order of W2 `"WO-T-001"`, but `planned_date D10`.

**When**
- `result = dao.get_by_machine_date_type(db, workspace_id=W2.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result is None`.

### WKO-MD-14 — of two matches the newer one is returned, though the older has the higher id
- **Rules:** `get_by_machine_date_type` R3 (the part that holds today)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, `created_at C12`.
2. B = order `"WO-T-002"`, but `planned_date D10`, `created_at C9`.

**When**
- `result = dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result.id == A.id`.

### WKO-MD-15 — of two matches made in one transaction, one of them is returned
- **Rules:** `get_by_machine_date_type` R1, R3 (the part that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10` (`created_at` left to the default).
2. B = order `"WO-T-002"`, but `planned_date D10` (same `created_at`).

**When**
- `result = dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result.id in {A.id, B.id}`.

### WKO-MD-16 — of two matches made in one transaction, the higher id is returned
- **Rules:** `get_by_machine_date_type` R3 [BUG-2671]
- **Kind:** bug
- **Expect:** xfail BUG-2671 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (today the tie gives the row first in physical order, the lower id)

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10` (`created_at` left to the default).
2. B = order `"WO-T-002"`, but `planned_date D10` (same `created_at`).
3. seqscan.

**When**
- `result = dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result.id == B.id`.

### WKO-MD-17 — the SQL orders by created_at descending, then id descending
- **Rules:** `get_by_machine_date_type` R3 [BUG-2671]
- **Kind:** bug
- **Expect:** xfail BUG-2671
- **Fails today on:** Then 3 (today the ORDER BY is `work_orders.created_at DESC` only)

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`.
2. `db.expunge_all()`.

**When**
- Statement recorder: `result = dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `order_part.startswith("work_orders.created_at DESC")`.
3. returns: `"work_orders.id DESC" in order_part`.

### WKO-MD-18 — one SELECT, no lock, nothing written
- **Rules:** `get_by_machine_date_type` Side effects (none)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`.
2. `db.expunge_all()`.

**When**
- Statement recorder: `result = dao.get_by_machine_date_type(db, workspace_id=W1.id, machine_id=M1.id, planned_date=D10, work_order_type_id=T1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `order_part.startswith("work_orders.created_at DESC")`.
3. returns: `len(selects) == 1`.
4. returns: `"FOR UPDATE" not in sql`.
5. returns: `written == []`.

## `WorkOrderDAO.list_for_sheet`

### WKO-LS-01 — ordered by calendar day, then created_at, then id, all descending
- **Rules:** `list_for_sheet` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. G = order `"WO-T-001"`, but `planned_date D10`, `created_at C11`.
2. C = order `"WO-T-002"`, but `planned_date D10`, `created_at C11`.
3. B = order `"WO-T-003"`, but `created_at KD(12)` (undated; calendar day D12).
4. A = order `"WO-T-004"`, but `planned_date D10`, `created_at C9`.
5. E = order `"WO-T-005"`, but `planned_date D10`, `created_at C11`, `id XID(1)`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [B.id, E.id, C.id, G.id, A.id]`.

### WKO-LS-02 — skip and limit page that order
- **Rules:** `list_for_sheet` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D9`.
2. B = order `"WO-T-002"`, but `planned_date D10`.
3. C = order `"WO-T-003"`, but `planned_date D11`.
4. E = order `"WO-T-004"`, but `planned_date D12`.
5. G = order `"WO-T-005"`, but `planned_date D13`.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, exclude_completed=False, skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [E.id, C.id]`.

### WKO-LS-03 — without a limit the first 50 rows come back
- **Rules:** `list_for_sheet` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. orders(W1, "WO-T-", 51).

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, exclude_completed=False)`.

**Then**
1. returns: `len(result) == 50`.

### WKO-LS-04 — limit=1000 returns 1000 of 1001 rows
- **Rules:** `list_for_sheet` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. orders(W1, "WO-T-", 1001).

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, exclude_completed=False, limit=1000)`.

**Then**
1. returns: `len(result) == 1000`.

### WKO-LS-05 — filters apply before paging: hidden rows that sort first take no place
- **Rules:** `list_for_sheet` R1, R3 (HR-5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D9`.
2. B = order `"WO-T-002"`, but `planned_date D10`.
3. C = order `"WO-T-003"`, but `planned_date D11`.
4. E = order `"WO-T-004"`, but `planned_date D20`, deleted.
5. G = order `"WO-T-005"`, but `planned_date D20`, `machine_id None`.
6. X2 = order of W2 `"WO-T-001"`, but `planned_date D20`.
7. H = order `"WO-T-006"`, but `planned_date D20`, completed.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, exclude_completed=True, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WKO-LS-06 — one SELECT, no lock, nothing written
- **Rules:** `list_for_sheet` Side effects (none)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. `db.expunge_all()`.

**When**
- Statement recorder: `result = dao.list_for_sheet(db, workspace_id=W1.id, exclude_completed=False, limit=100)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `len(selects) == 1`.
3. returns: `"FOR UPDATE" not in sql`.
4. returns: `written == []`.

### WKO-LS-07 — a pending order stays pending and unlisted; an unflushed edit stays unflushed
- **Rules:** `list_for_sheet` Side effects (none)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = order `"WO-T-001"`.
2. dirty+pending.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id, exclude_completed=False, limit=100)`.

**Then**
1. session: `len(db.new) == 1`.
2. session: `P in db.new`.
3. session: `O1 in db.dirty`.
4. session: `len(db.dirty) == 1`.
5. session: `not db.deleted`.
6. returns: `ids(result) == [O1.id]`.

### WKO-LS-08 — with no filter sent, completed orders are listed (exclude_completed defaults to False)
- **Rules:** `list_for_sheet` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, completed.
2. B = order `"WO-T-002"`, but `planned_date D11`.
3. C = order `"WO-T-003"`, but `planned_date D12`, started.

**When**
- `result = dao.list_for_sheet(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.

## `WorkOrderDAO.count_for_sheet`

### WKO-CS-01 — counts what the list shows over all pages, past the list's default page of 50
- **Rules:** `count_for_sheet` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. orders(W1, "WO-T-", 60).

**When**
- `result = dao.count_for_sheet(db, workspace_id=W1.id, exclude_completed=False)`.

**Then**
1. returns: `isinstance(result, int)`.
2. returns: `result == 60`.

### WKO-CS-02 — nothing matches gives the int 0
- **Rules:** `count_for_sheet` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `description "belt"`.

**When**
- `result = dao.count_for_sheet(db, workspace_id=W1.id, search="seal", exclude_completed=False)`.

**Then**
1. returns: `isinstance(result, int)`.
2. returns: `result == 0`.

### WKO-CS-03 — the list's filters apply: search, hide completed, status and machine
- **Rules:** `count_for_sheet` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `description "seal"`.
2. B = order `"WO-T-002"`, but `description "seal"`, started.
3. C = order `"WO-T-003"`, but `description "seal"`, completed.
4. E = order `"WO-T-004"`, but `description "seal"`, `machine_id MB.id`.
5. G = order `"WO-T-005"`, but `description "belt"`.

**When**
- `result = dao.count_for_sheet(db, workspace_id=W1.id, machine_id=M1.id, search="seal", exclude_completed=True)`.

**Then**
1. returns: `result == 2`.

### WKO-CS-04 — "planned" counts only future drafts
- **Rules:** `count_for_sheet` R1; `_apply_sheet_list_filters` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date Y10`.
2. B = order `"WO-T-002"`, but `planned_date Y11`.
3. C = order `"WO-T-003"`, but `planned_date Y12`.

**When**
- under clockD(`Y10`, `datetime(2031, 3, 10, 12, 0)`): `result = dao.count_for_sheet(db, workspace_id=W1.id, status_scope="planned", exclude_completed=False)`.

**Then**
1. returns: `result == 2`.

### WKO-CS-05 — one SELECT, no lock, nothing written
- **Rules:** `count_for_sheet` Side effects (none)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. `db.expunge_all()`.

**When**
- Statement recorder: `result = dao.count_for_sheet(db, workspace_id=W1.id, exclude_completed=False)`.

**Then**
1. returns: `result == 1`.
2. returns: `len(selects) == 1`.
3. returns: `"FOR UPDATE" not in sql`.
4. returns: `written == []`.

### WKO-CS-06 — with no filter sent, completed orders are counted (exclude_completed defaults to False)
- **Rules:** `count_for_sheet` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, completed.
2. B = order `"WO-T-002"`, but `planned_date D11`.

**When**
- `result = dao.count_for_sheet(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 2`.

## `WorkOrderDAO.count_by_calendar_date_for_sheet`

### WKO-DC-01 — counts per calendar day; days without orders are absent
- **Rules:** `count_by_calendar_date_for_sheet` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`.
2. B = order `"WO-T-002"`, but `planned_date D10`.
3. C = order `"WO-T-003"`, but `planned_date D12`.
4. E = order `"WO-T-004"`, but `created_at KD(13)` (undated).

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, dict)`.
2. returns: `result == {D10: 2, D12: 1, D13: 1}`.

### WKO-DC-02 — nothing matches gives {}
- **Rules:** `count_by_calendar_date_for_sheet` Returns
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no work order.

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {}`.

### WKO-DC-03 — other workspaces, deleted and machine-less orders are not counted
- **Rules:** `count_by_calendar_date_for_sheet` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0 `"WO-T-001"`, but `planned_date D10`.
2. A = order `"WO-T-001"`, but `planned_date D10`.
3. B = order `"WO-T-002"`, but `planned_date D10`, deleted.
4. C = order `"WO-T-003"`, but `planned_date D10`, `machine_id None`.
5. X2 = order of W2 `"WO-T-001"`, but `planned_date D10`.

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {D10: 1}`.

### WKO-DC-04 — asked for W2, only W2's orders are counted
- **Rules:** `count_by_calendar_date_for_sheet` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0 `"WO-T-001"`, but `planned_date D9`.
2. A = order `"WO-T-001"`, but `planned_date D10`.
3. X2 = order of W2 `"WO-T-001"`, but `planned_date D11`.

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == {D11: 1}`.

### WKO-DC-05 — factory_id counts that factory only
- **Rules:** `count_by_calendar_date_for_sheet` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, `factory_id FA.id`, `machine_id MX.id`.
2. B = order `"WO-T-002"`, but `planned_date D11`.
3. C = order `"WO-T-003"`, but `planned_date D12`, `factory_id FB.id`, `machine_id MY.id`.

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `result == {D11: 1}`.

### WKO-DC-06 — machine_id counts that machine only
- **Rules:** `count_by_calendar_date_for_sheet` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, `machine_id MA.id`.
2. B = order `"WO-T-002"`, but `planned_date D11`.
3. C = order `"WO-T-003"`, but `planned_date D12`, `machine_id MB.id`.

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id, machine_id=M1.id)`.

**Then**
1. returns: `result == {D11: 1}`.

### WKO-DC-07 — work_order_type_id counts that type only
- **Rules:** `count_by_calendar_date_for_sheet` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, `work_order_type_id TA.id`.
2. B = order `"WO-T-002"`, but `planned_date D11`.
3. C = order `"WO-T-003"`, but `planned_date D12`, `work_order_type_id TB.id`.

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id, work_order_type_id=T1.id)`.

**Then**
1. returns: `result == {D11: 1}`.

### WKO-DC-08 — priority counts that priority only
- **Rules:** `count_by_calendar_date_for_sheet` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, `priority PR.LOW`.
2. B = order `"WO-T-002"`, but `planned_date D11`, `priority PR.HIGH`.
3. C = order `"WO-T-003"`, but `planned_date D12`, `priority PR.URGENT`.

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id, priority=PR.HIGH)`.

**Then**
1. returns: `result == {D11: 1}`.

### WKO-DC-09 — status counts that status only
- **Rules:** `count_by_calendar_date_for_sheet` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`.
2. B = order `"WO-T-002"`, but `planned_date D11`, started.
3. C = order `"WO-T-003"`, but `planned_date D12`, voided.

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id, status=ST.IN_PROGRESS)`.

**Then**
1. returns: `result == {D11: 1}`.

### WKO-DC-10 — date bounds are inclusive on the calendar day, an undated order on its creation day
- **Rules:** `count_by_calendar_date_for_sheet` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D9`.
2. B = order `"WO-T-002"`, but `planned_date D10`.
3. C = order `"WO-T-003"`, but `created_at KD(11)` (undated).
4. E = order `"WO-T-004"`, but `planned_date D12`.

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id, planned_date_from=D10, planned_date_to=D11)`.

**Then**
1. returns: `result == {D10: 1, D11: 1}`.

### WKO-DC-11 — no date bound counts every day, years apart, and has no row limit
- **Rules:** `count_by_calendar_date_for_sheet` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-A01"`, but `planned_date date(2025, 1, 2)`.
2. B = order `"WO-T-A02"`, but `planned_date date(2027, 12, 30)`.
3. `for i in range(120):` `db.add(` order `f"WO-T-{i:03d}"`, but `planned_date D10` `)`, then one `db.flush()`.

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {date(2025, 1, 2): 1, date(2027, 12, 30): 1, D10: 120}`.

### WKO-DC-12 — exclude_completed drops completed orders from the dots
- **Rules:** `count_by_calendar_date_for_sheet` R3 [BUG-2675]
- **Kind:** bug
- **Expect:** xfail BUG-2675
- **Fails today on:** Then 1 (the call raises TypeError: no `exclude_completed` parameter)

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, completed.
2. B = order `"WO-T-002"`, but `planned_date D11`.

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id, exclude_completed=True)`.

**Then**
1. returns: `result == {D11: 1}`.

### WKO-DC-13 — search narrows the dots as it narrows the list
- **Rules:** `count_by_calendar_date_for_sheet` R3 [BUG-2675]
- **Kind:** bug
- **Expect:** xfail BUG-2675
- **Fails today on:** Then 1 (the call raises TypeError: no `search` parameter)

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, `description "seal"`.
2. B = order `"WO-T-002"`, but `planned_date D11`, `description "belt"`.

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id, search="SEAL")`.

**Then**
1. returns: `result == {D10: 1}`.

### WKO-DC-14 — status_scope "planned" narrows the dots to future drafts
- **Rules:** `count_by_calendar_date_for_sheet` R3 [BUG-2675]
- **Kind:** bug
- **Expect:** xfail BUG-2675
- **Fails today on:** Then 1 (the call raises TypeError: no `status_scope` parameter)

**Given**
1. A = order `"WO-T-001"`, but `planned_date Y9`.
2. B = order `"WO-T-002"`, but `planned_date Y11`.
3. C = order `"WO-T-003"`, but `planned_date Y12`, started.

**When**
- under clockD(`Y10`, `datetime(2031, 3, 10, 12, 0)`): `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id, status_scope="planned")`.

**Then**
1. returns: `result == {Y11: 1}`.

### WKO-DC-15 — one SELECT, no lock, nothing written
- **Rules:** `count_by_calendar_date_for_sheet` Side effects (none)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`.
2. `db.expunge_all()`.

**When**
- Statement recorder: `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {D10: 1}`.
2. returns: `len(selects) == 1`.
3. returns: `"FOR UPDATE" not in sql`.
4. returns: `written == []`.

### WKO-DC-16 — with none of the new keywords sent, completed, non-planned and every-text orders are counted
- **Rules:** `count_by_calendar_date_for_sheet` R3 (defaults; holds today and after the BUG-2675 fix)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, completed.
2. B = order `"WO-T-002"`, but `planned_date D11`, started, `description "belt"`.
3. C = order `"WO-T-003"`, but `planned_date D11`, `description "seal"`.

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {D10: 1, D11: 2}`.

### WKO-DC-17 — the new keywords sent at their defaults count exactly as no keyword
- **Rules:** `count_by_calendar_date_for_sheet` R3 [BUG-2675]
- **Kind:** bug
- **Expect:** xfail BUG-2675
- **Fails today on:** Then 1 (the call raises TypeError: no `status_scope`, `exclude_completed` or `search` parameter)

**Given**
1. A = order `"WO-T-001"`, but `planned_date D10`, completed.
2. B = order `"WO-T-002"`, but `planned_date D11`, started, `description "belt"`.
3. C = order `"WO-T-003"`, but `planned_date D11`, `description "seal"`.

**When**
- `result = dao.count_by_calendar_date_for_sheet(db, workspace_id=W1.id, status_scope=None, exclude_completed=False, search=None)`.

**Then**
1. returns: `result == {D10: 1, D11: 2}`.

## `WorkOrderDAO.get_by_id_and_workspace`

### WKO-GI-01 — returns the row by id, between a lower and a higher id
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. B = order `"WO-T-002"`.
3. C = order `"WO-T-003"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=B.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, WorkOrder)`.
2. returns: `result.id == B.id`.
3. returns: `result.work_order_number == "WO-T-002"`.

### WKO-GI-02 — a soft-deleted row is returned
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but deleted.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.is_deleted is True`.

### WKO-GI-03 — an unknown id gives None
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### WKO-GI-04 — W0's row asked with W1 gives None
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0 `"WO-T-001"`.
2. A = order `"WO-T-001"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=X0.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### WKO-GI-05 — W2's row asked with W1 gives None
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. X2 = order of W2 `"WO-T-001"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=X2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### WKO-GI-06 — asked with W2, W2's own row comes back, though a W1 row comes earlier
- **Rules:** `get_by_id_and_workspace` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. X2 = order of W2 `"WO-T-001"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=X2.id, workspace_id=W2.id)`.

**Then**
1. returns: `result.id == X2.id`.

### WKO-GI-07 — one SELECT, no lock, nothing written
- **Rules:** `get_by_id_and_workspace` Side effects (none)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. `db.expunge_all()`.

**When**
- Statement recorder: `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `len(selects) == 1`.
3. returns: `"FOR UPDATE" not in sql`.
4. returns: `written == []`.

### WKO-GI-08 — cost 2.125 is stored and read back as 2.13 (half up)
- **Rules:** Overview model facts (`cost` Numeric(15, 2)); HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `cost Decimal("2.125")`.
2. `db.expunge_all()`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.cost == Decimal("2.13")`.

### WKO-GI-09 — cost 0.005 is stored and read back as 0.01 (half up)
- **Rules:** Overview model facts (`cost`); HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `cost Decimal("0.005")`.
2. `db.expunge_all()`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.cost == Decimal("0.01")`.

### WKO-GI-10 — cost -1.005 is stored and read back as -1.01 (half away from zero)
- **Rules:** Overview model facts (`cost`); HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `cost Decimal("-1.005")`.
2. `db.expunge_all()`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.cost == Decimal("-1.01")`.

### WKO-GI-11 — cost 2.124 is stored and read back as 2.12 (control)
- **Rules:** Overview model facts (`cost`); HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`, but `cost Decimal("2.124")`.
2. `db.expunge_all()`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.cost == Decimal("2.12")`.

## `WorkOrderDAO.get_next_number`

### WKO-NN-01 — no number of the year yet gives WO-2031-001
- **Rules:** `get_next_number` R1, R2 (both clocks agree), Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no work order.

**When**
- under clockN(`datetime(2031, 6, 1, 12, 0)`, `datetime(2031, 6, 1, 12, 0)`): `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, str)`.
2. returns: `result == "WO-2031-001"`.

### WKO-NN-02 — after -041 comes -042
- **Rules:** `get_next_number` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order `"WO-2031-040"`.
2. B = order `"WO-2031-041"`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "WO-2031-042"`.

### WKO-NN-03 — after -009 comes -010
- **Rules:** `get_next_number` R3 (padding)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. orders(W1, "WO-2031-", 9).

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "WO-2031-010"`.

### WKO-NN-04 — after -998 comes -999
- **Rules:** `get_next_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-2031-998"`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "WO-2031-999"`.

### WKO-NN-05 — after -999 comes -1000, not cut to three digits
- **Rules:** `get_next_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-2031-998"`.
2. B = order `"WO-2031-999"`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "WO-2031-1000"`.

### WKO-NN-06 — after -1000 alone comes -1001
- **Rules:** `get_next_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-2031-1000"`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "WO-2031-1001"`.

### WKO-NN-07 — with -999 and -1000 both present the next is -1001
- **Rules:** `get_next_number` R3 [BUG-2676]
- **Kind:** bug
- **Expect:** xfail BUG-2676
- **Fails today on:** Then 2 (today the text-highest `-999` is taken, giving `-1000` again)

**Given**
1. A = order `"WO-2031-999"`.
2. B = order `"WO-2031-1000"`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.startswith("WO-2031-")`.
2. returns: `result == "WO-2031-1001"`.

### WKO-NN-08 — an unpadded -5 does not outrank -010
- **Rules:** `get_next_number` R3 [BUG-2676]
- **Kind:** bug
- **Expect:** xfail BUG-2676
- **Fails today on:** Then 2 (today `WO-2031-5` is the text-highest, giving `-006`)

**Given**
1. A = order `"WO-2031-010"`.
2. B = order `"WO-2031-5"`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.startswith("WO-2031-")`.
2. returns: `result == "WO-2031-011"`.

### WKO-NN-09 — a suffix that is not all digits never resets numbering
- **Rules:** `get_next_number` R4 [BUG-2676]
- **Kind:** bug
- **Expect:** xfail BUG-2676
- **Fails today on:** Then 2 (today `WO-2031-abc` is the text-highest, giving `-001`)

**Given**
1. A = order `"WO-2031-005"`.
2. B = order `"WO-2031-abc"`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.startswith("WO-2031-")`.
2. returns: `result == "WO-2031-006"`.

### WKO-NN-10 — a non-digit suffix alone gives -001
- **Rules:** `get_next_number` R1, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-2031-abc"`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "WO-2031-001"`.

### WKO-NN-11 — a soft-deleted -005 still counts
- **Rules:** `get_next_number` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = order `"WO-2031-004"`.
2. B = order `"WO-2031-005"`, but deleted.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "WO-2031-006"`.

### WKO-NN-12 — numbers of the year before and the year after do not count
- **Rules:** `get_next_number` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-2030-050"`.
2. B = order `"WO-2031-003"`.
3. C = order `"WO-2032-070"`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "WO-2031-004"`.

### WKO-NN-13 — only W1's numbers count, with higher numbers in W0 and W2
- **Rules:** `get_next_number` R5, R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0 `"WO-2031-020"`.
2. A = order `"WO-2031-003"`.
3. X2 = order of W2 `"WO-2031-030"`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "WO-2031-004"`.

### WKO-NN-14 — asked for W2, only W2's numbers count
- **Rules:** `get_next_number` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0 `"WO-2031-020"`.
2. A = order `"WO-2031-040"`.
3. X2 = order of W2 `"WO-2031-007"`.

**When**
- `result = dao.get_next_number(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == "WO-2031-008"`.

### WKO-NN-15 — asked for W0, only W0's numbers count
- **Rules:** `get_next_number` R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order of W0 `"WO-2031-007"`.
2. A = order `"WO-2031-040"`.
3. X2 = order of W2 `"WO-2031-050"`.

**When**
- `result = dao.get_next_number(db, workspace_id=W0.id)`.

**Then**
1. returns: `result == "WO-2031-008"`.

### WKO-NN-16 — another workspace may hold the number W1 gets, and W1 can store it
- **Rules:** `get_next_number` R6 (unique per workspace)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X2 = order of W2 `"WO-2031-001"`.
2. `n = dao.get_next_number(db, workspace_id=W1.id)` under clockN(`datetime(2031, 6, 1, 12, 0)`, `datetime(2031, 6, 1, 12, 0)`).

**When**
- `db.add(` order `n` `)` then `db.flush()` (A = that order).

**Then**
1. returns: `n == "WO-2031-001"`.
2. re-read A: `work_order_number == "WO-2031-001"`, `workspace_id == W1.id`.

### WKO-NN-17 — the same number twice in one workspace is refused by the database
- **Rules:** `get_next_number` R6; Overview model facts (`uq_wo_workspace_number`)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = order `"WO-2031-001"`.

**When**
- `db.add(` order `"WO-2031-001"` `)` then `db.flush()`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. raises: `exc.value.orig.diag.constraint_name == "uq_wo_workspace_number"`.
4. count: `db.scalar(text("SELECT count(*) FROM work_orders WHERE workspace_id = :w"), {"w": W1.id}) == 1`.

### WKO-NN-18 — the prefix match is case-sensitive: lowercase and mixed-case numbers do not count
- **Rules:** `get_next_number` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"wo-2031-050"`.
2. B = order `"Wo-2031-060"`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "WO-2031-001"`.

### WKO-NN-19 — the prefix in the middle, after a leading space, or with a longer year does not count
- **Rules:** `get_next_number` R3 ("numbers starting `WO-<year>-`")
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"XWO-2031-050"`.
2. B = order `" WO-2031-060"`.
3. C = order `"WO-20310-070"`.
4. E = order `"WO-2031_080"`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "WO-2031-001"`.

### WKO-NN-20 — the year comes from UTC when the local clock is already in the next year
- **Rules:** `get_next_number` R2 [BUG-2678]
- **Kind:** bug
- **Expect:** xfail BUG-2678
- **Fails today on:** Then 2 (today the local year 2032 is used, giving `WO-2032-001`)

**Given**
1. A = order `"WO-2031-007"`.

**When**
- under clockN(`datetime(2032, 1, 1, 5, 0)`, `datetime(2031, 12, 31, 23, 0)`): `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.startswith("WO-")`.
2. returns: `result == "WO-2031-008"`.

### WKO-NN-21 — the year comes from UTC when the local clock is still in the old year
- **Rules:** `get_next_number` R2 [BUG-2678]
- **Kind:** bug
- **Expect:** xfail BUG-2678
- **Fails today on:** Then 2 (today the local year 2031 is used, giving `WO-2031-008`)

**Given**
1. A = order `"WO-2031-007"`.

**When**
- under clockN(`datetime(2031, 12, 31, 19, 0)`, `datetime(2032, 1, 1, 0, 30)`): `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.startswith("WO-")`.
2. returns: `result == "WO-2032-001"`.

### WKO-NN-22 — with both clocks in 2032, last year's numbers do not count
- **Rules:** `get_next_number` R1, R2, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = order `"WO-2031-007"`.

**When**
- under clockN(`datetime(2032, 3, 1, 12, 0)`, `datetime(2032, 3, 1, 12, 0)`): `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "WO-2032-001"`.

### WKO-NN-23 — writes nothing: a pending number is not counted and stays pending, an unflushed edit stays unflushed
- **Rules:** `get_next_number` Side effects (reads only)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = order `"WO-2031-001"`.
2. `O1.title = "Edited"`.
3. `P = ` order `"WO-2031-009"`, then `db.add(P)` with no flush.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "WO-2031-002"`.
2. session: `len(db.new) == 1`.
3. session: `P in db.new`.
4. session: `O1 in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. session: `not db.deleted`.

### WKO-NN-24 — one SELECT, no lock, nothing written
- **Rules:** `get_next_number` Side effects; Overview (no lock)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = order `"WO-2031-001"`.
2. `db.expunge_all()`.

**When**
- Statement recorder: `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "WO-2031-002"`.
2. returns: `len(selects) == 1`.
3. returns: `"FOR UPDATE" not in sql`.
4. returns: `written == []`.

### WKO-NN-25 — positional arguments raise TypeError
- **Rules:** `get_next_number` signature (keyword-only)
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no work order.

**When**
- `dao.get_next_number(db, W1.id)`.

**Then**
1. raises: `TypeError`.

### WKO-NN-26 — a suffix with an inner dash is not all digits and is ignored
- **Rules:** `get_next_number` R3a, R4 [BUG-2676]
- **Kind:** bug
- **Expect:** xfail BUG-2676
- **Fails today on:** Then 2 (today `WO-2031-1-2` is the text-highest; the part after its last dash, `2`, is read, giving `WO-2031-003`)

**Given**
1. A = order `"WO-2031-005"`.
2. B = order `"WO-2031-1-2"`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.startswith("WO-2031-")`.
2. returns: `result == "WO-2031-006"`.

### WKO-NN-27 — a suffix with an underscore between digits is not all digits and is ignored
- **Rules:** `get_next_number` R4 [BUG-2676]
- **Kind:** bug
- **Expect:** xfail BUG-2676
- **Fails today on:** Then 2 (the result is not `WO-2031-006`: today `1_000`, the text-highest suffix, is read as a number)

**Given**
1. A = order `"WO-2031-005"`.
2. B = order `"WO-2031-1_000"`.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result.startswith("WO-2031-")`.
2. returns: `result == "WO-2031-006"`.

## `WorkOrderDAO.soft_delete`

### WKO-SD-01 — sets the four delete fields and returns the same object
- **Rules:** `soft_delete` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = order `"WO-T-001"`.

**When**
- `result = dao.soft_delete(db, db_obj=O, deleted_by=U2.id)`.

**Then**
1. returns: `result is O`.
2. re-read O: `is_active is False`, `is_deleted is True`, `deleted_by == U2.id`.
3. re-read O: `deleted_at is not None`.
4. re-read O: `isinstance(deleted_at, datetime)`.

### WKO-SD-02 — the change is flushed: a raw SELECT sees it with no flush by the test
- **Rules:** `soft_delete` R1 (flushes)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order `"WO-T-001"`.

**When**
- `result = dao.soft_delete(db, db_obj=O, deleted_by=U2.id)`.

**Then**
1. session: `O not in db.dirty`.
2. returns: `db.scalar(text("SELECT is_deleted FROM work_orders WHERE id = :i"), {"i": O.id}) is True`.
3. returns: `db.scalar(text("SELECT deleted_by FROM work_orders WHERE id = :i"), {"i": O.id}) == U2.id`.

### WKO-SD-03 — status and every other field are unchanged; updated_by is not written
- **Rules:** `soft_delete` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order `"WO-T-001"`, but `status "IN_PROGRESS"`, `description "seal"`, `assigned_to "Karim"`, `planned_date D10`, `cost Decimal("12.50")`, `priority PR.HIGH`, `work_order_template_id P1.id`, `created_at C9`, `updated_by U3.id`.

**When**
- `result = dao.soft_delete(db, db_obj=O, deleted_by=U2.id)`.

**Then**
1. returns: `result is O`.
2. re-read O: `status == "IN_PROGRESS"`, `description == "seal"`, `assigned_to == "Karim"`, `title == "Oil change"`.
3. re-read O: `planned_date == D10`, `cost == Decimal("12.50")`, `priority == PR.HIGH`.
4. re-read O: `work_order_number == "WO-T-001"`, `machine_id == M1.id`, `factory_id == F1.id`, `work_order_template_id == P1.id`.
5. re-read O: `created_at == C9`, `created_by == U1.id`.
6. re-read O: `updated_by == U3.id`.

### WKO-SD-04 — only the work order row is written: one UPDATE of work_orders, no DELETE
- **Rules:** `soft_delete` R2 (lines and approvers untouched)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order `"WO-T-001"`.

**When**
- Statement recorder: `result = dao.soft_delete(db, db_obj=O, deleted_by=U2.id)`.

**Then**
1. returns: `result is O`.
2. returns: `len(written) == 1`.
3. returns: `written[0].lstrip().upper().startswith("UPDATE WORK_ORDERS")`.

### WKO-SD-05 — an already deleted row is stamped again
- **Rules:** `soft_delete` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = order `"WO-T-001"`, but deleted.

**When**
- `result = dao.soft_delete(db, db_obj=O, deleted_by=U2.id)`.

**Then**
1. returns: `result is O`.
2. re-read O: `deleted_by == U2.id`, `is_deleted is True`, `is_active is False`.
3. re-read O: `deleted_at != DT0`.

### WKO-SD-06 — another order is not touched
- **Rules:** `soft_delete` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = order `"WO-T-001"`.
2. O = order `"WO-T-002"`.
3. C = order `"WO-T-003"`.

**When**
- `result = dao.soft_delete(db, db_obj=O, deleted_by=U2.id)`.

**Then**
1. returns: `result is O`.
2. re-read A: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.
3. re-read C: `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`.

### WKO-SD-07 — does not commit
- **Rules:** Overview (never commits)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O = order `"WO-T-001"`.

**When**
- commit spy: `result = dao.soft_delete(db, db_obj=O, deleted_by=U2.id)`.

**Then**
1. returns: `result is O`.
2. mock called: inside the savepoint, `cm.call_count == 0`.
3. re-read O (after `sp.rollback()`): `is_deleted is False`, `deleted_by is None`, `deleted_at is None`.

### WKO-SD-08 — deleted_at is utcnow(), not the database clock, under Dhaka
- **Rules:** `soft_delete` R1a [BUG-2679]
- **Kind:** bug
- **Expect:** xfail BUG-2679
- **Fails today on:** Then 3 (today `deleted_at` is the database's `now()` in Dhaka time)

**Given**
1. Dhaka.
2. O = order `"WO-T-001"`.

**When**
- with `app.dao.work_order.utcnow` (`create=True`) and `app.utils.time.utcnow` patched to return SDT: `result = dao.soft_delete(db, db_obj=O, deleted_by=U2.id)`.

**Then**
1. returns: `result is O`.
2. re-read O: `is_deleted is True`.
3. re-read O: `deleted_at == SDT`.

### WKO-SD-09 — deleted_at falls between the UTC times read before and after the call, under Dhaka
- **Rules:** `soft_delete` R1a [BUG-2679]
- **Kind:** bug
- **Expect:** xfail BUG-2679
- **Fails today on:** Then 3 (today `deleted_at` is six hours ahead of UTC under Dhaka)

**Given**
1. Dhaka.
2. O = order `"WO-T-001"`.
3. `before = utc_now() - timedelta(seconds=1)`.

**When**
- `result = dao.soft_delete(db, db_obj=O, deleted_by=U2.id)`, then `after = utc_now() + timedelta(seconds=1)`.

**Then**
1. returns: `result is O`.
2. re-read O: `deleted_at is not None`.
3. re-read O: `before <= deleted_at <= after`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_next_number` R7 [BUG-2677] | integration test (two transactions) | Two concurrent creates in one workspace never get the same number; neither fails with 23505. |
| `_apply_sheet_list_filters` R7 [BUG-2674] | `GET /work-orders/sheet/` (`app/api/v1/endpoints/work_orders.py`) | `status_scope` other than `planned` (`Planned`, `bogus`) → 422, DAO not reached. |
| `count_by_calendar_date_for_sheet` R3 [BUG-2675] pass-through | `WorkOrderManager.sheet_daily_counts`, its service, `GET /work-orders/sheet/daily-counts/`, web app `buildWorkOrderSheetDailyCountsParams` | The new `status_scope`, `exclude_completed`, `search` reach the DAO; the dots add up to the sheet's `total`. |
| `get_by_id_and_workspace` R1 exposure (HR-4, BUG-1279) | `WorkOrderManager.get_work_order` | A soft-deleted order → 404 by default. |
| foreign links (HR-16, BUG-1016) | `WorkOrderManager` create / update | A machine, component, factory or template of another workspace is refused as "not found". |
| FU-1 (HR-5) | `PurchaseOrderService` active-orders panel | In-flight orders beyond the newest 1000 are not missed; filtering is in SQL. |
| FU-2 (BUG-2333 pattern) | work order model / manager | `created_at` / `updated_at` are UTC, not the database's session-zone `now()`. |

## Spec gaps
None. The five gaps of revision 1 (enum import path, sheet filter defaults, real-state stamp columns, BUG-2675 parameter defaults, the inner-dash suffix) are closed by the spec's Gap log G1–G5 (2026-11-11).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_work_order_calendar_date_expr` | R1 | WKO-CE-01, CE-03 |
| | R2 | WKO-CE-01, CE-02, SF-06, SF-07, DC-01, DC-10, LS-01 |
| `_apply_sheet_list_filters` | Purpose (falsy skipped, AND) | WKO-SF-05, SF-29 |
| | R1 | WKO-SF-01, SF-02 |
| | R2 | WKO-SF-03, SF-04 |
| | R3 | WKO-SF-06, CE-03 |
| | R4 | WKO-SF-07, SF-08, CE-03 |
| | R5 | WKO-SF-09 |
| | R6 | WKO-SF-10, SF-11, CS-04 |
| | R6 [BUG-2673] | WKO-SF-12, SF-13 |
| | R7 (DAO half) | WKO-SF-14, SF-15 |
| | R7 [BUG-2674] endpoint | Deferred |
| | R8 | WKO-SF-16, SF-17, LS-05 |
| | R9 | WKO-SF-18 … SF-24, SF-28 |
| | R10 [BUG-2672] | WKO-SF-25, SF-26, SF-27 |
| `_sheet_base_query` | R1 | WKO-SB-01, SB-02, SB-03, SB-06 |
| | R2 | WKO-SB-04, SB-06 |
| | R3 | WKO-SB-05, SB-06 |
| | R4 | WKO-SF-29, CS-03 |
| | R5 | WKO-LS-01 (ordering by calendar day) |
| `get_by_workspace` | R1 | WKO-GW-01 … GW-06 |
| | R2 | WKO-GW-07, GW-08 |
| | R3 | WKO-GW-09, GW-10 |
| | R4 | WKO-GW-11 |
| | R5 | WKO-GW-08, GW-12, GW-13 |
| | R6 | WKO-GW-14, GW-15, GW-16 |
| | R7 | WKO-GW-17, GW-25 |
| | R8 | WKO-GW-18, GW-20, GW-21 |
| | R9 | WKO-GW-19, GW-20, GW-21 |
| | R10 | WKO-GW-22, GW-23, GW-24, GW-25 |
| | R11 (holds today) | WKO-GW-01, GW-26 |
| | R11 [BUG-2670] | WKO-GW-27 (strict), GW-28 (non-strict) |
| | Side effects none | WKO-GW-29, GW-30 |
| `list_future_drafts_for_template_machine` | R1 | WKO-FD-01, FD-02, FD-09 |
| | R2 | WKO-FD-02 … FD-09 |
| | R3 | WKO-FD-01, FD-10, FD-11 |
| | Side effects none | WKO-FD-12 |
| `list_drafts_outside_range_for_template_machine` | R1 | WKO-OR-01, OR-08, OR-10 |
| | R2 | WKO-OR-01 … OR-08, OR-10 |
| | R3 | WKO-OR-09 |
| | R4 | WKO-OR-01, OR-11, OR-12 |
| | Side effects none | WKO-OR-13 |
| `get_by_machine_date_type` | R1 | WKO-MD-01 … MD-06, MD-15 |
| | R2 | WKO-MD-05 … MD-13 |
| | R3 (holds today) | WKO-MD-14, MD-15, MD-18 |
| | R3 [BUG-2671] | WKO-MD-16 (non-strict), MD-17 (strict) |
| | Side effects none | WKO-MD-18 |
| `list_for_sheet` | R1 | WKO-SB-01 … SB-05, LS-05 |
| | R2 | WKO-LS-01 |
| | R3 | WKO-LS-02, LS-03, LS-04, LS-05 |
| | R4 (defaults) | WKO-LS-03, LS-08 |
| | Side effects none | WKO-LS-06, LS-07 |
| `count_for_sheet` | R1 | WKO-CS-01, CS-03, CS-04, SB-06 |
| | R2 | WKO-CS-02 |
| | R3 (defaults) | WKO-CS-06 |
| | Side effects none | WKO-CS-05 |
| `count_by_calendar_date_for_sheet` | R1, Returns | WKO-DC-01, DC-02, DC-03, DC-04, CE-01 |
| | R2 | WKO-DC-05 … DC-11 |
| | R3 defaults (holds today) | WKO-DC-16 |
| | R3 [BUG-2675] | WKO-DC-12, DC-13, DC-14, DC-17; pass-through Deferred |
| | Side effects none | WKO-DC-15 |
| `get_by_id_and_workspace` | R1 | WKO-GI-01, GI-02, GI-06 |
| | R2 | WKO-GI-03, GI-04, GI-05 |
| | Side effects none | WKO-GI-07 |
| | model fact `cost` Numeric(15, 2), HR-15 | WKO-GI-08 … GI-11 |
| `get_next_number` | R1 | WKO-NN-01, NN-10, NN-22 |
| | R2 (both clocks agree) | WKO-NN-01, NN-22 |
| | R2 [BUG-2678] | WKO-NN-20, NN-21 |
| | R3 (holds today) | WKO-NN-02 … NN-06 |
| | R3 [BUG-2676] | WKO-NN-07, NN-08 |
| | R3a [BUG-2676] | WKO-NN-26 |
| | R4 [BUG-2676] | WKO-NN-09, NN-27; R4 pass half NN-10 |
| | R5 | WKO-NN-11, NN-12, NN-13, NN-18, NN-19 |
| | R6 | WKO-NN-13 … NN-17 |
| | R7 [BUG-2677] | Deferred (integration) |
| | Side effects / signature | WKO-NN-23, NN-24, NN-25 |
| `soft_delete` | R1 | WKO-SD-01, SD-02 |
| | R1a [BUG-2679] | WKO-SD-08, SD-09 |
| | R2 | WKO-SD-03, SD-04, SD-06 |
| | R3 | WKO-SD-05 |
| | no commit | WKO-SD-07 |
