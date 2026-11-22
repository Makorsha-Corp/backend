# Test cases — `app/dao/expense_order.py`

> **Spec:** `tests/unit/dao/expense_order.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-11; nothing open). The owner answered OQ-42, OQ-43, OQ-44 (2026-11-11) as BUG-2717, BUG-2718, BUG-2719.
> **Revision:** 2 (2026-11-14) — spec apply-review + fill-gaps (Gap log G1–G4). OQ-42 → BUG-2717: OQ42-01, 02, 04, 05, 06 become strict xfail cards for the intended figures; OQ42-03 (`exclude_voided=True`, R3a) and new HS-11 (`total_count` / `not_invoiced_count` follow `exclude_voided`) are the pass halves; new OQ42-07 (a category with only voided orders). OQ-43 → BUG-2718: OQ43-01, 02, 03, 05 strict xfail; OQ43-04 (voided order) stays pass; new OQ43-06 (locked invoice on a completed order, xfail) and UP-12 (locked on an open order, pass). OQ-44 → BUG-2719: OQ44-01, 03, 04, 05 strict xfail; OQ44-02 stays pass; new OQ44-06 (paid), 07 (0.00 left), 08 (0.01 left), 09 (locked), all xfail, and pass halves SA-11 (count of a partly paid open order), SA-12 (draft and voided invoice → order total). G1: **deleted account** convention with every column a real delete writes (HF-47, HF-48, SF-17); **invvoid** convention as a real invoice void writes it (UP-03, SA-12). G2: new SF-23, the account-id tie-break on equal names (non-strict, BUG-747). G3: NX-26, NX-27 now cite `get_next_number` R4a. G4: closed by the answers; the UP cards stand. No `Pending:` line remains. No ID retired.
> **Revision:** 3 (2026-11-14) — `expense_order.verify.md` findings 1–5, all `case-missing`. F1: exact 0.00 figures — new SF-24 (a 0.00 order: category, stage and open-account totals `Decimal("0.00")`), SA-13 (timeline bucket and sample), UP-13 (confirmed 0.00 invoice, outstanding and sample). F2: new UP-14 (partial bucket, 10.00 and 40.00 left on 100.00 and 50.00 invoices → samples `[OB, OA]`). F3: new SF-25 (five accounts all listed beside a larger account-less order). F4: new HF-50 (`office_rent` found by `"FICE"`). F5: new OQ44-10 (strict xfail BUG-2719: completed order, voided invoice → 70.00 due this week; pass half SA-12). No ID retired.
> **Counts:** 252 cases · 203 expected-to-pass · 49 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** stage key 2 · `_category_label` 9 · `_due_date_bucket` 9 · `_due_window_dates` 7 · hub filters (+ stage filter, through `list_for_hub`) 50 (6 bug) · `get_by_workspace` 18 (2 bug) · `list_for_hub` 6 · `count_for_hub` 6 · `list_recent_for_hub` 9 (3 bug) · `aggregate_hub_stats` 11 · `aggregate_financial_snapshot_filtered` 25 (7 bug) · actionable due timeline 13 · actionable unpaid pipeline 14 (4 bug) · `get_by_id_and_workspace` 7 · `get_next_number` 27 (5 bug) · item `get_by_order` 10 (2 bug) · item `get_by_id_and_workspace` 6 · owner-answered OQ-42 7 (6 bug) · OQ-43 6 (5 bug) · OQ-44 10 (9 bug).
- **Depth:** full (skill 1a): hub money figures, financial dashboard and the order numbering.
- **Expected-to-fail by bug:** BUG-745 3 (HF-42 `_`, HF-43 `%`, HF-44) · BUG-2714 6 (HF-45/46, SF-14/15, UP-08/09; each with W0 and W2) · BUG-2715 1 (HF-47) · BUG-2711 2 (GW-15 non-strict, GW-16 SQL alarm) · BUG-746 3 (RC-01 strict, RC-07 non-strict, RC-08 alarm) · BUG-2712 2 (SF-06 non-strict, SF-07 alarm) · BUG-747 3 (SF-12, SF-23 non-strict, SF-13 alarm) · BUG-748 2 (UP-06 non-strict, UP-07 alarm) · BUG-749 3 (NX-07 999+1000, NX-09 `abc`+004, NX-27 same number in W2) · BUG-2710 2 (NX-21, NX-22 across New Year) · BUG-2713 2 (GO-07 non-strict, GO-08 alarm) · BUG-2717 6 (OQ42-01, 02, 04 … 07) · BUG-2718 5 (OQ43-01, 02, 03, 05, 06) · BUG-2719 9 (OQ44-01, 03 … 10). The owner-answered cards are all strict.
- **Owner answers (OQ-42, OQ-43, OQ-44, 2026-11-11):** each keeps its own section at the end, now `Answered by the owner — OQ-n → BUG-n`: strict xfail cards for the intended rule; what holds today and after the fix is in pass cards (HS-11, OQ42-03; UP-01 … UP-12, OQ43-04; SA-01 … SA-12, OQ44-02). The main UP cards were built on confirmed invoices of open orders, where today's rule and the answer agree; they stand, and UP-12 / OQ43-06 add `locked` on both sides of completion.
- **Notable design choices:**
  - Hub filter rules are tested once through `list_for_hub(limit=1000)`; each other hub method gets one card showing it applies filters and the DAO defaults (`exclude_complete=True`, `exclude_voided=True`).
  - Expense numbers are unique across all workspaces today (BUG-749): every Given stores `GN(N)` (per-process suffix) except the `NX` cards, which need exact numbers. Numbering uses year 2031/2032 through clockN, which patches `datetime.datetime` (the spec's patch target) and `utcnow`.
  - Due windows use TODAY = Tuesday 2031-11-11 (not the real year); every bucket edge is tested on both sides, plus a week running into the next month, Sunday, leap February and the UTC date at 23:30.
  - HR-15: sums are checked exactly (0.10 + 0.20 = 0.30, ten × 0.10 = 1.00, -5.25 + 0 + 5.26 = 0.01); every dashboard figure is also checked at exactly 0.00 (HS-04, SF-24, SA-13, UP-13), so an `or 1` fallback shows; GO-09 checks that line money is stored half up.
  - Cross-workspace cards (HR-16) build the invalid link on purpose, only to check it stays hidden.
  - Nine cards are `Author: claude`: the six non-strict tie cards and the SF-07, SF-13, UP-07 SQL alarms that pick one SELECT out of several.
- **Needs a decision:** None. The four gaps of revision 1 are closed by the spec's Gap log (2026-11-11).

## Conventions for this module

**IDs.** `EXO` = `app/dao/expense_order.py`. `SK` `_expense_order_stage_key_expr` · `CL` `_category_label` · `DB` `_due_date_bucket` · `DW` `_due_window_dates` · `HF` `_apply_expense_order_hub_filters` (with `_apply_expense_order_stage_filter`, through `list_for_hub`) · `GW` get_by_workspace · `LH` list_for_hub · `CH` count_for_hub · `RC` list_recent_for_hub · `HS` aggregate_hub_stats · `SF` aggregate_financial_snapshot_filtered (with `_filtered_orders_query`) · `SA` aggregate_financial_snapshot_actionable, due timeline · `UP` the same, unpaid pipeline · `GI` get_by_id_and_workspace · `NX` get_next_number · `GO` `ExpenseOrderItemDAO.get_by_order` · `II` `ExpenseOrderItemDAO.get_by_id_and_workspace` · `OQ42`/`OQ43`/`OQ44` the owner-answered cards (BUG-2717, BUG-2718, BUG-2719).

**Actors and fixed values.**
- `dao` = `expense_order_dao`, `idao` = `expense_order_item_dao`; `_due_date_bucket`, `_due_window_dates`, `_category_label`, `_expense_order_stage_key_expr` — all `from app.dao.expense_order import ...`. `db` = the test's real session, first argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- `ExpenseOrder`, `ExpenseOrderItem` = `app.models.expense_order`. `Account` = `app.models.account.Account`. `AccountInvoice` = `app.models.account_invoice.AccountInvoice`. `IntegrityError` = `sqlalchemy.exc.IntegrityError`. `text`, `select`, `func` = sqlalchemy's. `Decimal`, `date`, `datetime`, `patch`, `os` = the usual ones.
- MISSING = `999999999`. **GN(n)** = `f"{n}-{os.getpid()}"`. HIGH_ID(table) = `max(greatest id of the table or 0, last_value of <table>_id_seq) + 1000001`, read when the row is built.
- D1 = `date(2031, 3, 1)`, D2 = `date(2031, 3, 10)`, D3 = `date(2031, 3, 20)`. T1 … T5 = `datetime(2031, 3, 4, 9, 0)`, `(…, 10, 0)`, `(…, 11, 0)`, `(…, 12, 0)`, `(…, 13, 0)` (naive).
- TODAY = `date(2031, 11, 11)` (a Tuesday), EOW = `date(2031, 11, 16)` (Sunday), EOM = `date(2031, 11, 30)`. NOWX = `datetime(2031, 11, 11, 12, 0)`.

**Parallel runs.** `expense_number` is unique across **all** workspaces today (global index, BUG-749). Every builder except **numbered** stores `GN(N)` for the card's N, and a Then line that reads such a number back expects `GN(N)`. Only `NX` cards store exact `EXP-2031-…` / `EXP-2032-…` numbers (the computed number must be exact); a parallel run of the same card waits for the other test's rollback and then succeeds.

**Externals.** **clockN(L, U)** (`NX` cards only) = for the When, `patch("datetime.datetime", Fake)` where `Fake` subclasses `datetime` and its `now()` (any arguments) returns L, and patch `app.dao.expense_order.utcnow` to return U. An `NX` card without a clock line runs under clockN(`datetime(2031, 6, 1, 12, 0)`, `datetime(2031, 6, 1, 12, 0)`). **clockD(U)** (`SA`, `UP`, `DW`, `OQ43`, `OQ44` cards) = for the When, patch `app.dao.expense_order.utcnow` to return U; such a card without a clock line runs under clockD(NOWX). Other cards patch nothing.

**Standing rows** (every test, this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` three times (`W0.id < W1.id < W2.id`). U1, U2, U3 = `make_profile(db)` three times.
2. Accounts: A0 = `Account(workspace_id=W0.id, name="Foreign Co")`; K1, K2, K3 = `Account(workspace_id=W1.id, name=…)` with `"Alder Supplies"`, `"Birch Traders"`, `"Cedar Hub"`; A2 = `Account(workspace_id=W2.id, name="Overseas Ltd")`. So `K1.id < K2.id < K3.id`.

**Given rows.** Inserted directly (never through the DAOs), flushed one at a time in the order written. After "but" a line lists every column that differs. A line written as code is a step to run exactly. `db.add(...)` without `db.flush()` leaves the row pending.
- **order N** = `ExpenseOrder(workspace_id=W1.id, expense_number=GN(N), expense_category="factory", expense_date=D2, subtotal=Decimal("0.00"), total_amount=Decimal("10.00"), created_by=U1.id)`; no account, invoice or due date unless given. "order N **of W0**" / "**of W2**" sets only `workspace_id` to W0.id / W2.id.
- **numbered N** = the same as order N but `expense_number=N` exactly (no GN).
- **completed** = `approved_at T2`, `approved_by U1.id`, `completed_at T3`, `completed_by U1.id`. **voided** = `voided True`, `voided_at T4`, `voided_by U1.id`, `void_note "duplicate"`.
- **inv(W, amount)** = `AccountInvoice(workspace_id=W.id, account_id=<A0 for W0, K1 for W1, A2 for W2>.id, invoice_type="payable", invoice_amount=Decimal(amount), invoice_date=D1)`; defaults `invoice_status "draft"`, `payment_status "unpaid"`, `paid_amount 0`. **confirmed** = `invoice_status "confirmed"`. **locked** = `invoice_status "locked"`. **invvoid** = `invoice_status "voided"`, `void_note "duplicate"`, `paid_amount Decimal("0.00")`, `payment_status "unpaid"` (what a real invoice void writes).
- **deleted account** N = `Account(workspace_id=W1.id, name=N, is_deleted=True, is_active=False, deleted_at=T4, deleted_by=U1.id)` (what a real account soft delete writes). Account names are not unique: two accounts of one workspace may share a name.
- **line(O, n)** = `ExpenseOrderItem(workspace_id=W1.id, expense_order_id=O.id, line_number=n, quantity=Decimal("1.00"), description=f"Line {n}")`.
- **seqscan** = `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`, in this order. **bump(X)** = `db.execute(text("UPDATE expense_orders SET description = 'bumped' WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` (order is part of the check). **idset(result)** = `{r.id for r in result}`.
- **bucket(result, part, key)** = the one dict of `result[part]` whose `"key" == key`.
- **nothing written** = the numbers of `expense_orders` and `expense_order_items` rows (all workspaces) equal their values before the call.
- `pending:` lines check the session directly after the call, before anything expires it.
- `raises: IntegrityError` = `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the When. `raises: TypeError` / `AttributeError` = plain `with pytest.raises(<Type>) as exc:`.
- **Statement recorder** = the SQL the session sends during the When is recorded (`before_cursor_execute` listener). `selects` = every recorded `SELECT`; `sql` = the one `SELECT` from `expense_orders` (or `expense_order_items` in `GO`/`II`); `order_part` = text of `sql` after its first `ORDER BY`, before any `LIMIT` (`""` if none); `written` = every recorded `INSERT`, `UPDATE`, `DELETE`.
- **No-lock check** = `"FOR UPDATE" not in sql` (for several SELECTs: `all("FOR UPDATE" not in s for s in selects)`).
- **Clear the session before a one-query check**: a card that counts SELECTs ends its Given with `db.expunge_all()`; ids used in Then come from objects built before it.
- Money is compared as `Decimal` with `==` (`== Decimal("0.30")`), never as float or string.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`, for cards whose result rests on physical row order. Never weaken an assertion.

**Owner-answered cards.** The sections `## Answered by the owner — OQ-n → BUG-n` hold the cards for OQ-42 … OQ-44 (owner, 2026-11-11): strict xfail cards for the intended rule, and pass cards for what holds today and after the fix.

**Race simulations.** None (the race half of BUG-749 is integration-only).

## `_expense_order_stage_key_expr`

### EXO-SK-01 — complete wins over invoice; invoiced without completion; else draft
- **Rules:** `_expense_order_stage_key_expr` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. V1 = inv(W1, "50.00").
2. OA = order "EXP-T-001", but completed (no invoice).
3. OB = order "EXP-T-002", but completed, `invoice_id V1.id`.
4. OC = order "EXP-T-003", but `invoice_id V1.id`.
5. OD = order "EXP-T-004".

**When**
- `result = dict(db.execute(select(ExpenseOrder.id, _expense_order_stage_key_expr()).where(ExpenseOrder.workspace_id == W1.id)).all())`.

**Then**
1. returns: `result[OA.id] == "complete"`.
2. returns: `result[OB.id] == "complete"`.
3. returns: `result[OC.id] == "invoiced"`.
4. returns: `result[OD.id] == "draft"`.

### EXO-SK-02 — voiding does not change the stage
- **Rules:** `_expense_order_stage_key_expr` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V1 = inv(W1, "50.00").
2. OA = order "EXP-T-001", but completed, voided.
3. OB = order "EXP-T-002", but voided, `invoice_id V1.id`.
4. OC = order "EXP-T-003", but voided.

**When**
- `result = dict(db.execute(select(ExpenseOrder.id, _expense_order_stage_key_expr()).where(ExpenseOrder.workspace_id == W1.id)).all())`.

**Then**
1. returns: `result[OA.id] == "complete"`.
2. returns: `result[OB.id] == "invoiced"`.
3. returns: `result[OC.id] == "draft"`.

## `_category_label`

### EXO-CL-01 — factory is Factory
- **Rules:** `_category_label` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _category_label("factory")`.

**Then**
1. returns: `result == "Factory"`.

### EXO-CL-02 — department is Department
- **Rules:** `_category_label` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _category_label("department")`.

**Then**
1. returns: `result == "Department"`.

### EXO-CL-03 — other is Other
- **Rules:** `_category_label` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _category_label("other")`.

**Then**
1. returns: `result == "Other"`.

### EXO-CL-04 — an unknown slug has underscores replaced and is title-cased
- **Rules:** `_category_label` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _category_label("office_rent")`.

**Then**
1. returns: `result == "Office Rent"`.

### EXO-CL-05 — an unknown one-word slug is title-cased
- **Rules:** `_category_label` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _category_label("utilities")`.

**Then**
1. returns: `result == "Utilities"`.

### EXO-CL-06 — an empty slug gives an empty label
- **Rules:** `_category_label` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _category_label("")`.

**Then**
1. returns: `result == ""`.

### EXO-CL-07 — the lookup is case-sensitive: FACTORY is title-cased to Factory
- **Rules:** `_category_label` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _category_label("FACTORY")`.

**Then**
1. returns: `result == "Factory"`.

### EXO-CL-08 — a mixed-case slug with an underscore is title-cased
- **Rules:** `_category_label` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _category_label("oFFICE_rENT")`.

**Then**
1. returns: `result == "Office Rent"`.

### EXO-CL-09 — a non-string raises AttributeError
- **Rules:** `_category_label` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `_category_label(None)` inside `raises: AttributeError`.

**Then**
1. raises: `isinstance(exc.value, AttributeError)`.

## `_due_date_bucket`

### EXO-DB-01 — no due date is no_due_date
- **Rules:** `_due_date_bucket` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _due_date_bucket(None, today=TODAY, end_of_week=EOW, end_of_month=EOM)`.

**Then**
1. returns: `result == "no_due_date"`.

### EXO-DB-02 — yesterday is overdue
- **Rules:** `_due_date_bucket` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _due_date_bucket(date(2031, 11, 10), today=TODAY, end_of_week=EOW, end_of_month=EOM)`.

**Then**
1. returns: `result == "overdue"`.

### EXO-DB-03 — today is due this week, not overdue
- **Rules:** `_due_date_bucket` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _due_date_bucket(TODAY, today=TODAY, end_of_week=EOW, end_of_month=EOM)`.

**Then**
1. returns: `result == "due_this_week"`.

### EXO-DB-04 — the week's last day is due this week
- **Rules:** `_due_date_bucket` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _due_date_bucket(EOW, today=TODAY, end_of_week=EOW, end_of_month=EOM)`.

**Then**
1. returns: `result == "due_this_week"`.

### EXO-DB-05 — the day after the week's end is due later this month
- **Rules:** `_due_date_bucket` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _due_date_bucket(date(2031, 11, 17), today=TODAY, end_of_week=EOW, end_of_month=EOM)`.

**Then**
1. returns: `result == "due_later_this_month"`.

### EXO-DB-06 — the month's last day is due later this month
- **Rules:** `_due_date_bucket` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _due_date_bucket(EOM, today=TODAY, end_of_week=EOW, end_of_month=EOM)`.

**Then**
1. returns: `result == "due_later_this_month"`.

### EXO-DB-07 — the day after the month's end is beyond_scope
- **Rules:** `_due_date_bucket` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _due_date_bucket(date(2031, 12, 1), today=TODAY, end_of_week=EOW, end_of_month=EOM)`.

**Then**
1. returns: `result == "beyond_scope"`.

### EXO-DB-08 — a week ending in the next month puts that month's first days in due this week
- **Rules:** `_due_date_bucket` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = _due_date_bucket(date(2031, 8, 2), today=date(2031, 7, 31), end_of_week=date(2031, 8, 3), end_of_month=date(2031, 7, 31))`.

**Then**
1. returns: `result == "due_this_week"`.

### EXO-DB-09 — positional window dates raise TypeError
- **Rules:** `_due_date_bucket` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `_due_date_bucket(TODAY, TODAY, EOW, EOM)` inside `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.

## `_due_window_dates`

### EXO-DW-01 — a Tuesday gives today, the coming Sunday and the month's last day
- **Rules:** `_due_window_dates` R1, R2, R3, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. clockD(`datetime(2031, 11, 11, 12, 0)`).

**When**
- `result = _due_window_dates()`.

**Then**
1. returns: `result == (date(2031, 11, 11), date(2031, 11, 16), date(2031, 11, 30))`.
2. returns: `type(result[0]) is date`.

### EXO-DW-02 — on a Sunday the week ends today
- **Rules:** `_due_window_dates` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. clockD(`datetime(2031, 11, 16, 8, 0)`).

**When**
- `result = _due_window_dates()`.

**Then**
1. returns: `result == (date(2031, 11, 16), date(2031, 11, 16), date(2031, 11, 30))`.

### EXO-DW-03 — on a Monday the week ends six days later (Monday-based week)
- **Rules:** `_due_window_dates` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. clockD(`datetime(2031, 11, 10, 8, 0)`).

**When**
- `result = _due_window_dates()`.

**Then**
1. returns: `result == (date(2031, 11, 10), date(2031, 11, 16), date(2031, 11, 30))`.

### EXO-DW-04 — February of a leap year ends on the 29th
- **Rules:** `_due_window_dates` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. clockD(`datetime(2032, 2, 10, 12, 0)`).

**When**
- `result = _due_window_dates()`.

**Then**
1. returns: `result == (date(2032, 2, 10), date(2032, 2, 15), date(2032, 2, 29))`.

### EXO-DW-05 — February of a common year ends on the 28th
- **Rules:** `_due_window_dates` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. clockD(`datetime(2031, 2, 10, 12, 0)`).

**When**
- `result = _due_window_dates()`.

**Then**
1. returns: `result == (date(2031, 2, 10), date(2031, 2, 16), date(2031, 2, 28))`.

### EXO-DW-06 — the week can end in the next month
- **Rules:** `_due_window_dates` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. clockD(`datetime(2031, 7, 31, 12, 0)`).

**When**
- `result = _due_window_dates()`.

**Then**
1. returns: `result == (date(2031, 7, 31), date(2031, 8, 3), date(2031, 7, 31))`.

### EXO-DW-07 — today is the UTC date, also late in the UTC evening of New Year's Eve
- **Rules:** `_due_window_dates` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Dhaka = `db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))`.
2. clockD(`datetime(2031, 12, 31, 23, 30)`).

**When**
- `result = _due_window_dates()`.

**Then**
1. returns: `result == (date(2031, 12, 31), date(2032, 1, 4), date(2031, 12, 31))`.

## `_apply_expense_order_hub_filters` (through `list_for_hub`)

*Every hub method passes its filters to this helper (and through it to `_apply_expense_order_stage_filter`); the rules are tested once, here, through `list_for_hub` with `limit=1000`. The other hub methods each get a card showing they apply the filters. Unless a card is about them, `exclude_complete=False, exclude_voided=False` are passed explicitly.*

### EXO-HF-01 — only W1's orders, with orders of W0 and W2 on both sides
- **Rules:** `_apply_expense_order_hub_filters` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order "EXP-T-900" of W0.
2. O1 = order "EXP-T-001".
3. O2 = order "EXP-T-002".
4. X2 = order "EXP-T-902" of W2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `idset(result) == {O1.id, O2.id}`.

### EXO-HF-02 — asked for W0, only W0's order, though W1 and W2 orders come later
- **Rules:** `_apply_expense_order_hub_filters` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order "EXP-T-900" of W0.
2. O1 = order "EXP-T-001".
3. X2 = order "EXP-T-902" of W2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W0.id, limit=1000, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `idset(result) == {X0.id}`.

### EXO-HF-03 — asked for W2, only W2's order, though W0 and W1 orders come earlier
- **Rules:** `_apply_expense_order_hub_filters` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order "EXP-T-900" of W0.
2. O1 = order "EXP-T-001".
3. X2 = order "EXP-T-902" of W2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W2.id, limit=1000, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `idset(result) == {X2.id}`.

### EXO-HF-04 — expense_category is an exact match
- **Rules:** `_apply_expense_order_hub_filters` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001" (factory).
2. OB = order "EXP-T-002", but `expense_category "department"`.
3. OC = order "EXP-T-003", but `expense_category "other"`.
4. X2 = order "EXP-T-902" of W2, but `expense_category "department"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, expense_category="department")`.

**Then**
1. returns: `idset(result) == {OB.id}`.

### EXO-HF-05 — expense_category is case-sensitive: "Department" keeps nothing
- **Rules:** `_apply_expense_order_hub_filters` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001" (factory).
2. OB = order "EXP-T-002", but `expense_category "department"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, expense_category="Department")`.

**Then**
1. returns: `result == []`.

### EXO-HF-06 — expense_category does not match a part of the value
- **Rules:** `_apply_expense_order_hub_filters` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OB = order "EXP-T-002", but `expense_category "department"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, expense_category="depart")`.

**Then**
1. returns: `result == []`.

### EXO-HF-07 — expense_category with a leading space keeps nothing
- **Rules:** `_apply_expense_order_hub_filters` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001" (factory).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, expense_category=" factory")`.

**Then**
1. returns: `result == []`.

### EXO-HF-08 — expense_category "_" is not a wildcard
- **Rules:** `_apply_expense_order_hub_filters` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `expense_category "office-rent"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, expense_category="office_rent")`.

**Then**
1. returns: `result == []`.

### EXO-HF-09 — expense_category "" applies no filter
- **Rules:** `_apply_expense_order_hub_filters` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001" (factory).
2. OB = order "EXP-T-002", but `expense_category "department"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, expense_category="")`.

**Then**
1. returns: `idset(result) == {OA.id, OB.id}`.

### EXO-HF-10 — account_id keeps the middle account's orders only
- **Rules:** `_apply_expense_order_hub_filters` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `account_id K1.id`.
2. OB = order "EXP-T-002", but `account_id K2.id`.
3. OC = order "EXP-T-003", but `account_id K3.id`.
4. OD = order "EXP-T-004" (no account).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, account_id=K2.id)`.

**Then**
1. returns: `idset(result) == {OB.id}`.

### EXO-HF-11 — account_id 0 keeps nothing
- **Rules:** `_apply_expense_order_hub_filters` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `account_id K1.id`.
2. OD = order "EXP-T-004" (no account).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, account_id=0)`.

**Then**
1. returns: `result == []`.

### EXO-HF-12 — invoice_id keeps the middle invoice's order only
- **Rules:** `_apply_expense_order_hub_filters` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. V1 = inv(W1, "10.00").
2. V2 = inv(W1, "20.00").
3. V3 = inv(W1, "30.00") (so `V1.id < V2.id < V3.id`).
4. OA = order "EXP-T-001", but `invoice_id V1.id`.
5. OB = order "EXP-T-002", but `invoice_id V2.id`.
6. OC = order "EXP-T-003", but `invoice_id V3.id`.
7. OD = order "EXP-T-004" (no invoice).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, invoice_id=V2.id)`.

**Then**
1. returns: `idset(result) == {OB.id}`.

### EXO-HF-13 — date_from includes its own day and later days
- **Rules:** `_apply_expense_order_hub_filters` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `expense_date date(2031, 3, 9)`.
2. OB = order "EXP-T-002", but `expense_date date(2031, 3, 10)`.
3. OC = order "EXP-T-003", but `expense_date date(2031, 3, 11)`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, date_from=date(2031, 3, 10))`.

**Then**
1. returns: `idset(result) == {OB.id, OC.id}`.

### EXO-HF-14 — date_to includes its own day and earlier days
- **Rules:** `_apply_expense_order_hub_filters` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `expense_date date(2031, 3, 9)`.
2. OB = order "EXP-T-002", but `expense_date date(2031, 3, 10)`.
3. OC = order "EXP-T-003", but `expense_date date(2031, 3, 11)`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, date_to=date(2031, 3, 10))`.

**Then**
1. returns: `idset(result) == {OA.id, OB.id}`.

### EXO-HF-15 — stage 1 keeps orders neither completed nor invoiced
- **Rules:** `_apply_expense_order_hub_filters` R6; `_apply_expense_order_stage_filter` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. V1 = inv(W1, "10.00").
2. OA = order "EXP-T-001" (draft).
3. OB = order "EXP-T-002", but `invoice_id V1.id`.
4. OC = order "EXP-T-003", but completed (no invoice).
5. OD = order "EXP-T-004", but completed, `invoice_id V1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, status_ids=[1])`.

**Then**
1. returns: `idset(result) == {OA.id}`.

### EXO-HF-16 — stage 2 keeps invoiced orders that are not completed
- **Rules:** `_apply_expense_order_hub_filters` R6; `_apply_expense_order_stage_filter` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. V1 = inv(W1, "10.00").
2. OA = order "EXP-T-001" (draft).
3. OB = order "EXP-T-002", but `invoice_id V1.id`.
4. OC = order "EXP-T-003", but completed (no invoice).
5. OD = order "EXP-T-004", but completed, `invoice_id V1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, status_ids=[2])`.

**Then**
1. returns: `idset(result) == {OB.id}`.

### EXO-HF-17 — stage 3 keeps completed orders, with or without an invoice
- **Rules:** `_apply_expense_order_hub_filters` R6; `_apply_expense_order_stage_filter` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. V1 = inv(W1, "10.00").
2. OA = order "EXP-T-001" (draft).
3. OB = order "EXP-T-002", but `invoice_id V1.id`.
4. OC = order "EXP-T-003", but completed (no invoice).
5. OD = order "EXP-T-004", but completed, `invoice_id V1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, status_ids=[3])`.

**Then**
1. returns: `idset(result) == {OC.id, OD.id}`.

### EXO-HF-18 — two stage ids are alternatives (OR)
- **Rules:** `_apply_expense_order_stage_filter` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. V1 = inv(W1, "10.00").
2. OA = order "EXP-T-001" (draft).
3. OB = order "EXP-T-002", but `invoice_id V1.id`.
4. OC = order "EXP-T-003", but completed (no invoice).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, status_ids=[1, 3])`.

**Then**
1. returns: `idset(result) == {OA.id, OC.id}`.

### EXO-HF-19 — only unknown stage ids apply no stage filter
- **Rules:** `_apply_expense_order_stage_filter` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V1 = inv(W1, "10.00").
2. OA = order "EXP-T-001" (draft).
3. OB = order "EXP-T-002", but `invoice_id V1.id`.
4. OC = order "EXP-T-003", but completed.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, status_ids=[9])`.

**Then**
1. returns: `idset(result) == {OA.id, OB.id, OC.id}`.

### EXO-HF-20 — an unknown id beside a known one is ignored
- **Rules:** `_apply_expense_order_stage_filter` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V1 = inv(W1, "10.00").
2. OA = order "EXP-T-001" (draft).
3. OB = order "EXP-T-002", but `invoice_id V1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, status_ids=[2, 9])`.

**Then**
1. returns: `idset(result) == {OB.id}`.

### EXO-HF-21 — a repeated stage id behaves like one
- **Rules:** `_apply_expense_order_stage_filter` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V1 = inv(W1, "10.00").
2. OA = order "EXP-T-001" (draft).
3. OB = order "EXP-T-002", but `invoice_id V1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, status_ids=[1, 1])`.

**Then**
1. returns: `ids(result) == [OA.id]`.

### EXO-HF-22 — an empty status_ids list applies no filter
- **Rules:** `_apply_expense_order_hub_filters` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V1 = inv(W1, "10.00").
2. OA = order "EXP-T-001" (draft).
3. OB = order "EXP-T-002", but `invoice_id V1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, status_ids=[])`.

**Then**
1. returns: `idset(result) == {OA.id, OB.id}`.

### EXO-HF-23 — stage 3 with exclude_complete true keeps nothing
- **Rules:** `_apply_expense_order_hub_filters` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001" (draft).
2. OC = order "EXP-T-003", but completed.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=True, exclude_voided=False, status_ids=[3])`.

**Then**
1. returns: `result == []`.

### EXO-HF-24 — voiding is not a stage: a voided draft passes stage 1
- **Rules:** `_apply_expense_order_stage_filter` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but voided.
2. OB = order "EXP-T-002", but completed.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, status_ids=[1])`.

**Then**
1. returns: `idset(result) == {OA.id}`.

### EXO-HF-25 — invoice_filter "invoiced" keeps orders with an invoice
- **Rules:** `_apply_expense_order_hub_filters` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. V1 = inv(W1, "10.00").
2. OA = order "EXP-T-001".
3. OB = order "EXP-T-002", but `invoice_id V1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, invoice_filter="invoiced")`.

**Then**
1. returns: `idset(result) == {OB.id}`.

### EXO-HF-26 — invoice_filter "not_invoiced" keeps orders with no invoice
- **Rules:** `_apply_expense_order_hub_filters` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. V1 = inv(W1, "10.00").
2. OA = order "EXP-T-001".
3. OB = order "EXP-T-002", but `invoice_id V1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, invoice_filter="not_invoiced")`.

**Then**
1. returns: `idset(result) == {OA.id}`.

### EXO-HF-27 — invoice_filter "Invoiced" (capital) applies no filter
- **Rules:** `_apply_expense_order_hub_filters` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V1 = inv(W1, "10.00").
2. OA = order "EXP-T-001".
3. OB = order "EXP-T-002", but `invoice_id V1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, invoice_filter="Invoiced")`.

**Then**
1. returns: `idset(result) == {OA.id, OB.id}`.

### EXO-HF-28 — invoice_filter "all" applies no filter
- **Rules:** `_apply_expense_order_hub_filters` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V1 = inv(W1, "10.00").
2. OA = order "EXP-T-001".
3. OB = order "EXP-T-002", but `invoice_id V1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, invoice_filter="all")`.

**Then**
1. returns: `idset(result) == {OA.id, OB.id}`.

### EXO-HF-29 — exclude_voided true leaves voided orders out
- **Rules:** `_apply_expense_order_hub_filters` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001".
2. OB = order "EXP-T-002", but voided.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=True)`.

**Then**
1. returns: `idset(result) == {OA.id}`.

### EXO-HF-30 — exclude_voided false includes voided orders
- **Rules:** `_apply_expense_order_hub_filters` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001".
2. OB = order "EXP-T-002", but voided.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `idset(result) == {OA.id, OB.id}`.

### EXO-HF-31 — exclude_complete true leaves completed orders out
- **Rules:** `_apply_expense_order_hub_filters` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001".
2. OB = order "EXP-T-002", but completed.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=True, exclude_voided=False)`.

**Then**
1. returns: `idset(result) == {OA.id}`.

### EXO-HF-32 — with neither flag passed, completed and voided orders are both left out
- **Rules:** `list_for_hub` R1 (DAO defaults); `_apply_expense_order_hub_filters` R8, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001".
2. OB = order "EXP-T-002", but completed.
3. OC = order "EXP-T-003", but voided.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {OA.id}`.

### EXO-HF-33 — search matches the middle of the number, case-insensitively
- **Rules:** `_apply_expense_order_hub_filters` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order "EXP-Q7Z-1".
2. OB = order "EXP-T-002".
3. X2 = order "EXP-Q7Z-9" of W2.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="q7z")`.

**Then**
1. returns: `idset(result) == {OA.id}`.

### EXO-HF-34 — search matches the middle of the account's name, case-insensitively
- **Rules:** `_apply_expense_order_hub_filters` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `account_id K1.id`.
2. OB = order "EXP-T-002", but `account_id K2.id`.
3. OC = order "EXP-T-003" (no account).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="RCH TR")`.

**Then**
1. returns: `idset(result) == {OB.id}`.

### EXO-HF-35 — search matches the middle of the category, case-insensitively
- **Rules:** `_apply_expense_order_hub_filters` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001" (factory).
2. OB = order "EXP-T-002", but `expense_category "department"`.
3. OC = order "EXP-T-003", but `expense_category "other"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="PARTM")`.

**Then**
1. returns: `idset(result) == {OB.id}`.

### EXO-HF-36 — search "o" matches the factory and other orders, not department
- **Rules:** `_apply_expense_order_hub_filters` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001" (factory).
2. OB = order "EXP-T-002", but `expense_category "department"`.
3. OC = order "EXP-T-003", but `expense_category "other"`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="o")`.

**Then**
1. returns: `idset(result) == {OA.id, OC.id}`.

### EXO-HF-37 — the search text is trimmed
- **Rules:** `_apply_expense_order_hub_filters` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-Q7Z-1".
2. OB = order "EXP-T-002".

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="  Q7Z  ")`.

**Then**
1. returns: `idset(result) == {OA.id}`.

### EXO-HF-38 — a whitespace-only search applies no filter
- **Rules:** `_apply_expense_order_hub_filters` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-Q7Z-1".
2. OB = order "EXP-T-002", but `account_id K2.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="   ")`.

**Then**
1. returns: `idset(result) == {OA.id, OB.id}`.

### EXO-HF-39 — an empty search applies no filter
- **Rules:** `_apply_expense_order_hub_filters` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-Q7Z-1".
2. OB = order "EXP-T-002".

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="")`.

**Then**
1. returns: `idset(result) == {OA.id, OB.id}`.

### EXO-HF-40 — a search matching another workspace's own account name finds nothing for W1
- **Rules:** `_apply_expense_order_hub_filters` R1, R10
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order "EXP-T-900" of W0, but `account_id A0.id`.
2. OA = order "EXP-T-001", but `account_id K1.id`.
3. X2 = order "EXP-T-902" of W2, but `account_id A2.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="Overseas")`.

**Then**
1. returns: `result == []`.

### EXO-HF-41 — a search with "_" finds the order whose number has it
- **Rules:** `_apply_expense_order_hub_filters` R10 [BUG-745] (the part that holds today)
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order "EXP-T_9".
2. OB = order "EXP-T-002".

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="T_9")`.

**Then**
1. returns: `OA.id in idset(result)`.

### EXO-HF-42 — "_" matches only a literal underscore
- **Rules:** `_apply_expense_order_hub_filters` R10 [BUG-745]
- **Kind:** bug
- **Expect:** xfail BUG-745
- **Fails today on:** Then 2 (`_` is a one-character wildcard today and matches every order)

**Given**
1. OA = order "EXP-T_9".
2. OB = order "EXP-T-002".
3. OC = order "EXP-T-003", but `account_id K1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="_")`.

**Then**
1. returns: `OA.id in idset(result)`.
2. returns: `idset(result) == {OA.id}`.

### EXO-HF-43 — "%" matches only a literal percent sign
- **Rules:** `_apply_expense_order_hub_filters` R10 [BUG-745]
- **Kind:** bug
- **Expect:** xfail BUG-745
- **Fails today on:** Then 2 (`%` is a wildcard today and matches every order)

**Given**
1. OA = order "EXP-50%-1".
2. OB = order "EXP-T-002".

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="%")`.

**Then**
1. returns: `OA.id in idset(result)`.
2. returns: `idset(result) == {OA.id}`.

### EXO-HF-44 — "T_0" does not match "T-0"
- **Rules:** `_apply_expense_order_hub_filters` R10 [BUG-745]
- **Kind:** bug
- **Expect:** xfail BUG-745
- **Fails today on:** Then 1 (`_` matches the dash today, so OB is found)

**Given**
1. OB = order "EXP-T-002".

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="T_0")`.

**Then**
1. returns: `result == []`.

### EXO-HF-45 — an account of W0 linked to a W1 order: its name does not match
- **Rules:** `_apply_expense_order_hub_filters` R11 [BUG-2714] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-2714
- **Fails today on:** Then 1 (the account join compares ids only, so "Foreign" finds OA)

**Given**
1. OA = order "EXP-T-001", but `account_id A0.id` (invalid data: W0's account).
2. OB = order "EXP-T-002", but `account_id K1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="Foreign")`.

**Then**
1. returns: `result == []`.

### EXO-HF-46 — an account of W2 linked to a W1 order: its name does not match
- **Rules:** `_apply_expense_order_hub_filters` R11 [BUG-2714] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-2714
- **Fails today on:** Then 1 (the account join compares ids only, so "Overseas" finds OA)

**Given**
1. OA = order "EXP-T-001", but `account_id A2.id` (invalid data: W2's account).
2. OB = order "EXP-T-002", but `account_id K1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="Overseas")`.

**Then**
1. returns: `result == []`.

### EXO-HF-47 — a soft-deleted account's name does not match
- **Rules:** `_apply_expense_order_hub_filters` R12 [BUG-2715] (HR-4)
- **Kind:** bug
- **Expect:** xfail BUG-2715
- **Fails today on:** Then 1 (the join ignores `accounts.is_deleted`, so "Gone" finds OA)

**Given**
1. KG = deleted account "Gone Ltd".
2. OA = order "EXP-T-001", but `account_id KG.id`.
3. OB = order "EXP-T-002", but `account_id K1.id`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="Gone")`.

**Then**
1. returns: `result == []`.

### EXO-HF-48 — an order of a soft-deleted account still matches on its number
- **Rules:** `_apply_expense_order_hub_filters` R12, R10
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. KG = deleted account "Gone Ltd".
2. OA = order "EXP-Q7Z-1", but `account_id KG.id`.
3. OB = order "EXP-T-002".

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="Q7Z")`.

**Then**
1. returns: `idset(result) == {OA.id}`.

### EXO-HF-49 — an unknown filter keyword raises TypeError
- **Rules:** `_apply_expense_order_hub_filters` R13; `list_for_hub` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001".

**When**
- `dao.list_for_hub(db, workspace_id=W1.id, limit=1000, colour="red")` inside `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.

### EXO-HF-50 — a search finds a category outside the three labels in the middle of its slug, ignoring case
- **Rules:** `_apply_expense_order_hub_filters` R10 (category substring)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `expense_category "office_rent"`.
2. OB = order "EXP-T-002" (factory).

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False, search="FICE")`.

**Then**
1. returns: `idset(result) == {OA.id}`.

## `ExpenseOrderDAO.get_by_workspace`

### EXO-GW-01 — returns W1's orders, voided and completed included, not W0's or W2's
- **Rules:** `get_by_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. X0 = order "EXP-T-900" of W0.
2. OA = order "EXP-T-001".
3. OB = order "EXP-T-002", but completed.
4. OC = order "EXP-T-003", but voided.
5. X2 = order "EXP-T-902" of W2.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {OA.id, OB.id, OC.id}`.

### EXO-GW-02 — asked for W0, only W0's order
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order "EXP-T-900" of W0.
2. OA = order "EXP-T-001".
3. X2 = order "EXP-T-902" of W2.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W0.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {X0.id}`.

### EXO-GW-03 — asked for W2, only W2's order
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order "EXP-T-900" of W0.
2. OA = order "EXP-T-001".
3. X2 = order "EXP-T-902" of W2.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {X2.id}`.

### EXO-GW-04 — expense_category is an exact match
- **Rules:** `get_by_workspace` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001" (factory).
2. OB = order "EXP-T-002", but `expense_category "department"`.
3. X2 = order "EXP-T-902" of W2, but `expense_category "department"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, expense_category="department", limit=1000)`.

**Then**
1. returns: `idset(result) == {OB.id}`.

### EXO-GW-05 — expense_category "Department" (capital) keeps nothing
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OB = order "EXP-T-002", but `expense_category "department"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, expense_category="Department", limit=1000)`.

**Then**
1. returns: `result == []`.

### EXO-GW-06 — expense_category "" applies no filter
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001" (factory).
2. OB = order "EXP-T-002", but `expense_category "department"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, expense_category="", limit=1000)`.

**Then**
1. returns: `idset(result) == {OA.id, OB.id}`.

### EXO-GW-07 — account_id keeps the middle account's orders only
- **Rules:** `get_by_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `account_id K1.id`.
2. OB = order "EXP-T-002", but `account_id K2.id`.
3. OC = order "EXP-T-003", but `account_id K3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, account_id=K2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {OB.id}`.

### EXO-GW-08 — account_id 0 applies no filter (unlike the hub)
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `account_id K1.id`.
2. OB = order "EXP-T-002" (no account).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, account_id=0, limit=1000)`.

**Then**
1. returns: `idset(result) == {OA.id, OB.id}`.

### EXO-GW-09 — invoice_id keeps the middle invoice's order only
- **Rules:** `get_by_workspace` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. V1 = inv(W1, "10.00").
2. V2 = inv(W1, "20.00").
3. V3 = inv(W1, "30.00").
4. OA = order "EXP-T-001", but `invoice_id V1.id`.
5. OB = order "EXP-T-002", but `invoice_id V2.id`.
6. OC = order "EXP-T-003", but `invoice_id V3.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, invoice_id=V2.id, limit=1000)`.

**Then**
1. returns: `idset(result) == {OB.id}`.

### EXO-GW-10 — invoice_id 0 keeps nothing
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V1 = inv(W1, "10.00").
2. OA = order "EXP-T-001", but `invoice_id V1.id`.
3. OB = order "EXP-T-002" (no invoice).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, invoice_id=0, limit=1000)`.

**Then**
1. returns: `result == []`.

### EXO-GW-11 — newest created_at first, ids not rising with the stamps
- **Rules:** `get_by_workspace` R6 (the part that holds today)
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `created_at T2`.
2. OB = order "EXP-T-002", but `created_at T5`.
3. OC = order "EXP-T-003", but `created_at T1`.
4. OD = order "EXP-T-004", but `created_at T4`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `ids(result) == [OB.id, OD.id, OA.id, OC.id]`.

### EXO-GW-12 — skip and limit take the second and third newest of five
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `created_at T2`.
2. OB = order "EXP-T-002", but `created_at T5`.
3. OC = order "EXP-T-003", but `created_at T1`.
4. OD = order "EXP-T-004", but `created_at T4`.
5. OE = order "EXP-T-005", but `created_at T3`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [OD.id, OE.id]`.

### EXO-GW-13 — the default limit is 100
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for i in range(1, 102):` add order f"EXP-L-{i:03d}" (101 orders), flushing once after the loop.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### EXO-GW-14 — the invoice filter runs before paging
- **Rules:** `get_by_workspace` R4, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V1 = inv(W1, "10.00").
2. V2 = inv(W1, "20.00").
3. OB = order "EXP-T-002", but `invoice_id V2.id`, `created_at T5`.
4. OA = order "EXP-T-001", but `invoice_id V1.id`, `created_at T3`.
5. OC = order "EXP-T-003", but `invoice_id V1.id`, `created_at T1`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, invoice_id=V1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [OC.id]`.

### EXO-GW-15 — equal created_at: the higher id comes first
- **Rules:** `get_by_workspace` R6 [BUG-2711]
- **Kind:** bug
- **Expect:** xfail BUG-2711 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no `id` tie-breaker; a sequential scan meets the lower id first)

**Given**
1. seqscan.
2. OA = order "EXP-T-001", but `created_at T3`.
3. OB = order "EXP-T-002", but `created_at T3` (so `OA.id < OB.id`).
4. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `ids(result) == [OB.id, OA.id]`.

### EXO-GW-16 — the query orders by created_at, then id, both descending
- **Rules:** `get_by_workspace` R6 [BUG-2711]
- **Kind:** bug
- **Expect:** xfail BUG-2711
- **Fails today on:** Then 3 (the `ORDER BY` has `created_at` only)

**Given**
1. OA = order "EXP-T-001".
2. Statement recorder.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `ids(result) == [OA.id]`.
2. statement: `"expense_orders.created_at DESC" in order_part`.
3. statement: `"expense_orders.id DESC" in order_part`.

### EXO-GW-17 — positional arguments raise TypeError
- **Rules:** `get_by_workspace` R7
- **Kind:** error
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001".

**When**
- `dao.get_by_workspace(db, W1.id)` inside `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.

### EXO-GW-18 — writes nothing and takes no lock; a pending order and an unflushed edit stay
- **Rules:** `get_by_workspace` Side effects; Overview (no lock)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001".
2. `OA.description = "Edited"` (not flushed).
3. `P = ExpenseOrder(workspace_id=W1.id, expense_number=GN("EXP-T-009"), expense_category="factory", expense_date=D2, subtotal=Decimal("0.00"), total_amount=Decimal("10.00"), created_by=U1.id)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `ids(result) == [OA.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `OA in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `"FOR UPDATE" not in sql`.

## `ExpenseOrderDAO.list_for_hub`

### EXO-LH-01 — ordered by expense_date, then created_at, then id, all descending
- **Rules:** `list_for_hub` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. R1 = order "EXP-T-001", but `expense_date D2`, `created_at T3`.
2. R2 = order "EXP-T-002", but `expense_date D3`, `created_at T1`.
3. R3 = order "EXP-T-003", but `expense_date D2`, `created_at T5`.
4. R4 = order "EXP-T-004", but `expense_date D2`, `created_at T3`.
5. R5 = order "EXP-T-005", but `expense_date D1`, `created_at T5`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `ids(result) == [R2.id, R3.id, R4.id, R1.id, R5.id]`.

### EXO-LH-02 — skip 1, limit 2 of five
- **Rules:** `list_for_hub` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. R1 = order "EXP-T-001", but `expense_date D2`, `created_at T3`.
2. R2 = order "EXP-T-002", but `expense_date D3`, `created_at T1`.
3. R3 = order "EXP-T-003", but `expense_date D2`, `created_at T5`.
4. R4 = order "EXP-T-004", but `expense_date D2`, `created_at T3`.
5. R5 = order "EXP-T-005", but `expense_date D1`, `created_at T5`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, skip=1, limit=2, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `ids(result) == [R3.id, R4.id]`.

### EXO-LH-03 — the default limit is 50
- **Rules:** `list_for_hub` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for i in range(1, 52):` add order f"EXP-L-{i:03d}" (51 orders), flushing once after the loop.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `len(result) == 50`.

### EXO-LH-04 — skip past the end gives []
- **Rules:** `list_for_hub` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for i in range(1, 6):` add order f"EXP-L-{i:03d}" (5 orders), flushing once after the loop.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, skip=5, limit=10, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result == []`.

### EXO-LH-05 — the filters run before paging; the hidden order sorts first
- **Rules:** `list_for_hub` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. H = order "EXP-T-001", but `expense_category "department"`, `expense_date D3`.
2. F1 = order "EXP-T-002", but `expense_date D2`.
3. F2 = order "EXP-T-003", but `expense_date D1`.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, skip=1, limit=1, exclude_complete=False, exclude_voided=False, expense_category="factory")`.

**Then**
1. returns: `ids(result) == [F2.id]`.

### EXO-LH-06 — writes nothing and takes no lock
- **Rules:** `list_for_hub` Side effects; Overview (no lock)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001".
2. `OA.description = "Edited"` (not flushed).
3. Statement recorder.

**When**
- `result = dao.list_for_hub(db, workspace_id=W1.id, limit=1000, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `ids(result) == [OA.id]`.
2. pending: `OA in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. statement: `written == []`.
5. statement: `"FOR UPDATE" not in sql`.

## `ExpenseOrderDAO.count_for_hub`

### EXO-CH-01 — counts W1's orders only, as an int
- **Rules:** `count_for_hub` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. X0 = order "EXP-T-900" of W0.
2. OA = order "EXP-T-001".
3. OB = order "EXP-T-002".
4. OC = order "EXP-T-003".
5. X2 = order "EXP-T-902" of W2.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `isinstance(result, int)`.
2. returns: `result == 3`.

### EXO-CH-02 — no order passing gives 0, not None
- **Rules:** `count_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X2 = order "EXP-T-902" of W2.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `isinstance(result, int)`.
2. returns: `result == 0`.

### EXO-CH-03 — no paging: 60 orders count 60
- **Rules:** `count_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for i in range(1, 61):` add order f"EXP-L-{i:03d}" (60 orders), flushing once after the loop.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result == 60`.

### EXO-CH-04 — an order matching the search on number and account is counted once
- **Rules:** `count_for_hub` R1 (distinct)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-BIRCH-1", but `account_id K2.id`.
2. OB = order "EXP-T-002", but `account_id K2.id`.
3. OC = order "EXP-T-003", but `account_id K1.id`.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False, search="birch")`.

**Then**
1. returns: `result == 2`.

### EXO-CH-05 — applies the filters and the DAO defaults
- **Rules:** `count_for_hub` R1; `_apply_expense_order_hub_filters` R2, R8, R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001" (factory).
2. OB = order "EXP-T-002", but `expense_category "department"`.
3. OC = order "EXP-T-003", but completed.
4. OD = order "EXP-T-004", but voided.

**When**
- `result = dao.count_for_hub(db, workspace_id=W1.id, expense_category="factory")`.

**Then**
1. returns: `result == 1`.

### EXO-CH-06 — an unknown filter keyword raises TypeError
- **Rules:** `count_for_hub` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001".

**When**
- `dao.count_for_hub(db, workspace_id=W1.id, colour="red")` inside `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.

## `ExpenseOrderDAO.list_recent_for_hub`

### EXO-RC-01 — the last change decides: an edited order beats a newer never-edited one
- **Rules:** `list_recent_for_hub` R2 [BUG-746]
- **Kind:** bug
- **Expect:** xfail BUG-746
- **Fails today on:** Then 1 (today `updated_at DESC` puts the never-edited B first: `[B, A, C]`)

**Given**
1. A = order "EXP-T-001", but `created_at T1`, `updated_at T5`.
2. B = order "EXP-T-002", but `created_at T3` (never edited).
3. C = order "EXP-T-003", but `created_at T2`, `updated_at T4`.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `ids(result) == [A.id, C.id, B.id]`.

### EXO-RC-02 — among edited orders, the latest edit first
- **Rules:** `list_recent_for_hub` R2 (the part that holds today)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = order "EXP-T-001", but `created_at T1`, `updated_at T5`.
2. C = order "EXP-T-002", but `created_at T3`, `updated_at T4`.
3. D = order "EXP-T-003", but `created_at T2`, `updated_at T3`.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `ids(result) == [A.id, C.id, D.id]`.

### EXO-RC-03 — among never-edited orders, the newest created first
- **Rules:** `list_recent_for_hub` R2 (the part that holds today)
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = order "EXP-T-001", but `created_at T3`.
2. F = order "EXP-T-002", but `created_at T1`.
3. G = order "EXP-T-003", but `created_at T2`.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `ids(result) == [B.id, G.id, F.id]`.

### EXO-RC-04 — the default limit is 10: of 11, the oldest is left out
- **Rules:** `list_recent_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Z = order "EXP-L-000", but `created_at datetime(2031, 3, 4, 8, 0)`.
2. `for i in range(1, 11):` add order f"EXP-L-{i:03d}", but `created_at datetime(2031, 3, 4, 9, i)` (10 orders), flushing once after the loop.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `len(result) == 10`.
2. returns: `Z.id not in idset(result)`.

### EXO-RC-05 — limit 2 gives the two newest
- **Rules:** `list_recent_for_hub` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = order "EXP-T-001", but `created_at T3`.
2. F = order "EXP-T-002", but `created_at T1`.
3. G = order "EXP-T-003", but `created_at T2`.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, limit=2, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `ids(result) == [B.id, G.id]`.

### EXO-RC-06 — applies the filters and the DAO defaults; newer hidden orders do not take places
- **Rules:** `list_recent_for_hub` R1; `_apply_expense_order_hub_filters` R1, R8, R9
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order "EXP-T-900" of W0, but `created_at T5`.
2. OA = order "EXP-T-001", but `created_at T1`.
3. OC = order "EXP-T-003", but completed, `created_at T4`.
4. OD = order "EXP-T-004", but voided, `created_at T3`.
5. X2 = order "EXP-T-902" of W2, but `created_at T5`.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [OA.id]`.

### EXO-RC-07 — equal last change: the higher id first
- **Rules:** `list_recent_for_hub` R2 [BUG-746]
- **Kind:** bug
- **Expect:** xfail BUG-746 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no `id` tie-breaker; a sequential scan meets the lower id first)

**Given**
1. seqscan.
2. OA = order "EXP-T-001", but `created_at T3`.
3. OB = order "EXP-T-002", but `created_at T3` (so `OA.id < OB.id`).
4. `db.expire_all()`

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `ids(result) == [OB.id, OA.id]`.

### EXO-RC-08 — the query orders by coalesce(updated_at, created_at), then id, descending
- **Rules:** `list_recent_for_hub` R2 [BUG-746]
- **Kind:** bug
- **Expect:** xfail BUG-746
- **Fails today on:** Then 2 (no `coalesce` in the `ORDER BY` today)

**Given**
1. OA = order "EXP-T-001".
2. Statement recorder.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `ids(result) == [OA.id]`.
2. statement: `"coalesce" in order_part.lower()`.
3. statement: `order_part.strip().endswith("expense_orders.id DESC")`.

### EXO-RC-09 — takes no lock and writes nothing
- **Rules:** `list_recent_for_hub` Side effects; Overview (no lock)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001".
2. Statement recorder.

**When**
- `result = dao.list_recent_for_hub(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `ids(result) == [OA.id]`.
2. statement: `written == []`.
3. statement: `"FOR UPDATE" not in sql`.

## `ExpenseOrderDAO.aggregate_hub_stats`

*Voided orders in the money figures are BUG-2717 (owner, OQ-42); their cards are in the section "Answered by the owner — OQ-42". No Given here holds a voided order, except HS-11 (the counts that follow `exclude_voided`).*

### EXO-HS-01 — totals, open and not-invoiced over draft, invoiced and completed orders
- **Rules:** `aggregate_hub_stats` R1, R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. V1 = inv(W1, "1000.05").
2. OA = order "EXP-T-001", but `total_amount Decimal("0.10")`.
3. OB = order "EXP-T-002", but `total_amount Decimal("0.20")`, `invoice_id V1.id`.
4. OC = order "EXP-T-003", but `total_amount Decimal("1000.05")`, completed, `invoice_id V1.id`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result == (3, Decimal("1000.35"), 2, Decimal("0.30"), 1)`.
2. returns: `isinstance(result[1], Decimal)`.
3. returns: `isinstance(result[3], Decimal)`.

### EXO-HS-02 — W0's and W2's amounts are not counted
- **Rules:** `aggregate_hub_stats` R1; `_apply_expense_order_hub_filters` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order "EXP-T-900" of W0, but `total_amount Decimal("500.00")`.
2. OA = order "EXP-T-001", but `total_amount Decimal("0.10")`.
3. X2 = order "EXP-T-902" of W2, but `total_amount Decimal("700.00")`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result == (1, Decimal("0.10"), 1, Decimal("0.10"), 1)`.

### EXO-HS-03 — no order passing gives zeros with Decimal values
- **Rules:** `aggregate_hub_stats` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X2 = order "EXP-T-902" of W2, but `total_amount Decimal("700.00")`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result == (0, Decimal("0"), 0, Decimal("0"), 0)`.
2. returns: `isinstance(result[1], Decimal)`.
3. returns: `isinstance(result[3], Decimal)`.

### EXO-HS-04 — negative and zero totals are added as they are
- **Rules:** `aggregate_hub_stats` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("-5.25")`.
2. OB = order "EXP-T-002", but `total_amount Decimal("0.00")`.
3. OC = order "EXP-T-003", but `total_amount Decimal("5.26")`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result == (3, Decimal("0.01"), 3, Decimal("0.01"), 3)`.

### EXO-HS-05 — ten amounts of 0.10 add up to exactly 1.00
- **Rules:** `aggregate_hub_stats` R4 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `for i in range(1, 11):` add order f"EXP-L-{i:03d}", but `total_amount Decimal("0.10")` (10 orders), flushing once after the loop.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result[1] == Decimal("1.00")`.
2. returns: `result[3] == Decimal("1.00")`.

### EXO-HS-06 — a completed order without an invoice is not open but is not invoiced
- **Rules:** `aggregate_hub_stats` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V1 = inv(W1, "3.00").
2. OA = order "EXP-T-001", but `total_amount Decimal("7.00")`, completed.
3. OB = order "EXP-T-002", but `total_amount Decimal("3.00")`, `invoice_id V1.id`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result == (2, Decimal("10.00"), 1, Decimal("3.00"), 1)`.

### EXO-HS-07 — with no flags passed, completed orders are left out (DAO default)
- **Rules:** `aggregate_hub_stats` R1; `_apply_expense_order_hub_filters` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("1.00")`.
2. OB = order "EXP-T-002", but `total_amount Decimal("2.00")`, completed.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == (1, Decimal("1.00"), 1, Decimal("1.00"), 1)`.

### EXO-HS-08 — a category filter limits every figure
- **Rules:** `aggregate_hub_stats` R1; `_apply_expense_order_hub_filters` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("1.00")` (factory).
2. OB = order "EXP-T-002", but `total_amount Decimal("2.00")`, `expense_category "department"`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False, expense_category="department")`.

**Then**
1. returns: `result == (1, Decimal("2.00"), 1, Decimal("2.00"), 1)`.

### EXO-HS-09 — an unknown filter keyword raises TypeError
- **Rules:** `aggregate_hub_stats` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001".

**When**
- `dao.aggregate_hub_stats(db, workspace_id=W1.id, colour="red")` inside `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.

### EXO-HS-10 — takes no lock and writes nothing
- **Rules:** `aggregate_hub_stats` Side effects; Overview (no lock)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001".
2. Statement recorder.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result[0] == 1`.
2. statement: `written == []`.
3. statement: `all("FOR UPDATE" not in s for s in selects)`.

### EXO-HS-11 — with exclude_voided false, a voided order counts in total and not invoiced
- **Rules:** `aggregate_hub_stats` R1, R3 (the counts that follow `exclude_voided`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("100.00")`.
2. OC = order "EXP-T-003", but `total_amount Decimal("30.00")`, voided.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result[0] == 2`.
2. returns: `result[4] == 2`.

## `ExpenseOrderDAO.aggregate_financial_snapshot_filtered` (with `_filtered_orders_query`)

*No Given here holds a voided order; voided orders are BUG-2717 (section "Answered by the owner — OQ-42"). **Z3** = the stage pipeline with nothing in it: `[{"key": "draft", "label": "Draft", "count": 0, "total_value": Decimal("0")}, {"key": "invoiced", "label": "Invoiced", "count": 0, "total_value": Decimal("0")}, {"key": "complete", "label": "Complete", "count": 0, "total_value": Decimal("0")}]`.*

### EXO-SF-01 — category breakdown: one entry per category, by total descending
- **Rules:** `aggregate_financial_snapshot_filtered` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("0.10")` (factory).
2. OB = order "EXP-T-002", but `total_amount Decimal("0.20")` (factory).
3. OC = order "EXP-T-003", but `total_amount Decimal("5.00")`, `expense_category "department"`.
4. OD = order "EXP-T-004", but `total_amount Decimal("0.05")`, `expense_category "other"`.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result["category_breakdown"] == [{"key": "department", "label": "Department", "count": 1, "total_value": Decimal("5.00")}, {"key": "factory", "label": "Factory", "count": 2, "total_value": Decimal("0.30")}, {"key": "other", "label": "Other", "count": 1, "total_value": Decimal("0.05")}]`.

### EXO-SF-02 — nothing passing: empty breakdown, three zero stages, empty open by account
- **Rules:** `aggregate_financial_snapshot_filtered` R4, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X2 = order "EXP-T-902" of W2, but `account_id A2.id`.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result["category_breakdown"] == []`.
2. returns: `result["stage_pipeline"] == Z3`.
3. returns: `result["open_by_account"] == []`.
4. returns: `set(result) == {"category_breakdown", "stage_pipeline", "open_by_account"}`.

### EXO-SF-03 — six categories are kept as they are
- **Rules:** `aggregate_financial_snapshot_filtered` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Six orders "EXP-C-001" … "EXP-C-006" with (`expense_category`, `total_amount`) = ("rent", `Decimal("7.00")`), ("water", `Decimal("6.00")`), ("power", `Decimal("5.00")`), ("fuel", `Decimal("4.00")`), ("tax", `Decimal("3.00")`), ("fees", `Decimal("2.00")`).

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `[e["key"] for e in result["category_breakdown"]] == ["rent", "water", "power", "fuel", "tax", "fees"]`.
2. returns: `[e["label"] for e in result["category_breakdown"]] == ["Rent", "Water", "Power", "Fuel", "Tax", "Fees"]`.

### EXO-SF-04 — a seventh category is merged into a trailing Other entry
- **Rules:** `aggregate_financial_snapshot_filtered` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Seven orders "EXP-C-001" … "EXP-C-007" with (`expense_category`, `total_amount`) = ("rent", `Decimal("7.00")`), ("water", `Decimal("6.00")`), ("power", `Decimal("5.00")`), ("fuel", `Decimal("4.00")`), ("tax", `Decimal("3.00")`), ("fees", `Decimal("2.00")`), ("misc", `Decimal("1.00")`).

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `len(result["category_breakdown"]) == 7`.
2. returns: `result["category_breakdown"][5] == {"key": "fees", "label": "Fees", "count": 1, "total_value": Decimal("2.00")}`.
3. returns: `result["category_breakdown"][6] == {"key": "other", "label": "Other", "count": 1, "total_value": Decimal("1.00")}`.

### EXO-SF-05 — the seventh and eighth categories are added together
- **Rules:** `aggregate_financial_snapshot_filtered` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Eight orders "EXP-C-001" … "EXP-C-008" with (`expense_category`, `total_amount`) = ("rent", `Decimal("7.00")`), ("water", `Decimal("6.00")`), ("power", `Decimal("5.00")`), ("fuel", `Decimal("4.00")`), ("tax", `Decimal("3.00")`), ("fees", `Decimal("2.00")`), ("misc", `Decimal("1.00")`), ("tolls", `Decimal("0.50")`).

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `len(result["category_breakdown"]) == 7`.
2. returns: `result["category_breakdown"][6] == {"key": "other", "label": "Other", "count": 2, "total_value": Decimal("1.50")}`.

### EXO-SF-06 — equal category totals: key ascending
- **Rules:** `aggregate_financial_snapshot_filtered` R2 [BUG-2712]
- **Kind:** bug
- **Expect:** xfail BUG-2712 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (ties are unordered; the factory group, seen first, can come first)

**Given**
1. seqscan.
2. OA = order "EXP-T-001", but `total_amount Decimal("5.00")` (factory).
3. OB = order "EXP-T-002", but `total_amount Decimal("5.00")`, `expense_category "department"`.
4. `db.expire_all()`

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `[e["key"] for e in result["category_breakdown"]] == ["department", "factory"]`.

### EXO-SF-07 — the category query breaks ties by the category
- **Rules:** `aggregate_financial_snapshot_filtered` R2 [BUG-2712]
- **Kind:** bug
- **Expect:** xfail BUG-2712
- **Author:** claude
- **Fails today on:** Then 2 (the category `ORDER BY` has the sum only)

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("5.00")`.
2. Statement recorder.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `len(result["category_breakdown"]) == 1`.
2. statement: in the recorded SELECT that groups by `expense_orders.expense_category`, the text after `ORDER BY` contains `expense_orders.expense_category`.

### EXO-SF-08 — stage pipeline: draft, invoiced, complete with counts and exact sums
- **Rules:** `aggregate_financial_snapshot_filtered` R5; `_expense_order_stage_key_expr` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. V1 = inv(W1, "7.00").
2. OA = order "EXP-T-001", but `total_amount Decimal("0.10")`.
3. OB = order "EXP-T-002", but `total_amount Decimal("0.20")`.
4. OC = order "EXP-T-003", but `total_amount Decimal("7.00")`, `invoice_id V1.id`.
5. OD = order "EXP-T-004", but `total_amount Decimal("3.00")`, completed (no invoice).

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result["stage_pipeline"] == [{"key": "draft", "label": "Draft", "count": 2, "total_value": Decimal("0.30")}, {"key": "invoiced", "label": "Invoiced", "count": 1, "total_value": Decimal("7.00")}, {"key": "complete", "label": "Complete", "count": 1, "total_value": Decimal("3.00")}]`.

### EXO-SF-09 — a stage with no orders is still listed, with zeros
- **Rules:** `aggregate_financial_snapshot_filtered` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V1 = inv(W1, "7.00").
2. OC = order "EXP-T-003", but `total_amount Decimal("7.00")`, `invoice_id V1.id`.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result["stage_pipeline"] == [{"key": "draft", "label": "Draft", "count": 0, "total_value": Decimal("0")}, {"key": "invoiced", "label": "Invoiced", "count": 1, "total_value": Decimal("7.00")}, {"key": "complete", "label": "Complete", "count": 0, "total_value": Decimal("0")}]`.

### EXO-SF-10 — open by account: per account, completed and account-less orders left out
- **Rules:** `aggregate_financial_snapshot_filtered` R6, R7, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("0.10")`, `account_id K1.id`.
2. OB = order "EXP-T-002", but `total_amount Decimal("0.20")`, `account_id K1.id`.
3. OC = order "EXP-T-003", but `total_amount Decimal("5.00")`, `account_id K2.id`.
4. OD = order "EXP-T-004", but `total_amount Decimal("9.00")` (no account).
5. OE = order "EXP-T-005", but `total_amount Decimal("50.00")`, `account_id K3.id`, completed.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result["open_by_account"] == [{"account_id": K2.id, "account_name": "Birch Traders", "count": 1, "total_value": Decimal("5.00")}, {"account_id": K1.id, "account_name": "Alder Supplies", "count": 2, "total_value": Decimal("0.30")}]`.

### EXO-SF-11 — at most five accounts, the smallest sixth dropped
- **Rules:** `aggregate_financial_snapshot_filtered` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. KD = `Account(workspace_id=W1.id, name="Dune Mart")`. KE = `Account(workspace_id=W1.id, name="Elm Yard")`. KF = `Account(workspace_id=W1.id, name="Fern Bay")`.
2. Orders "EXP-A-001" … "EXP-A-006" with (`account_id`, `total_amount`) = (K3, `Decimal("6.00")`), (KF, `Decimal("1.00")`), (K1, `Decimal("5.00")`), (KD, `Decimal("4.00")`), (K2, `Decimal("3.00")`), (KE, `Decimal("2.00")`).

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `[e["account_id"] for e in result["open_by_account"]] == [K3.id, K1.id, KD.id, K2.id, KE.id]`.

### EXO-SF-12 — equal account totals: name case-insensitive ascending
- **Rules:** `aggregate_financial_snapshot_filtered` R8 [BUG-747]
- **Kind:** bug
- **Expect:** xfail BUG-747 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (ties are unordered; a case-sensitive or id order puts "Beta Supply" first)

**Given**
1. seqscan.
2. KB = `Account(workspace_id=W1.id, name="Beta Supply")`.
3. KA = `Account(workspace_id=W1.id, name="alpha supply")` (so `KB.id < KA.id`).
4. OB = order "EXP-T-001", but `total_amount Decimal("5.00")`, `account_id KB.id`.
5. OA = order "EXP-T-002", but `total_amount Decimal("5.00")`, `account_id KA.id`.
6. `db.expire_all()`

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `[e["account_name"] for e in result["open_by_account"]] == ["alpha supply", "Beta Supply"]`.

### EXO-SF-13 — the open-by-account query breaks ties by name, then account id
- **Rules:** `aggregate_financial_snapshot_filtered` R8 [BUG-747]
- **Kind:** bug
- **Expect:** xfail BUG-747
- **Author:** claude
- **Fails today on:** Then 2 (the account `ORDER BY` has the sum only)

**Given**
1. OA = order "EXP-T-001", but `account_id K1.id`.
2. Statement recorder.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `len(result["open_by_account"]) == 1`.
2. statement: in the recorded SELECT that groups by account, the text after `ORDER BY` contains `accounts.name`.
3. statement: in that SELECT, the text after `ORDER BY` contains `accounts.id`.

### EXO-SF-14 — a W1 order linked to W0's account is left out of open by account
- **Rules:** `aggregate_financial_snapshot_filtered` R9 [BUG-2714] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-2714
- **Fails today on:** Then 2 (the join compares ids only; "Foreign Co" with W0's account id is listed)

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("4.00")`, `account_id A0.id` (invalid data).
2. OB = order "EXP-T-002", but `total_amount Decimal("1.00")`, `account_id K1.id`.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result["category_breakdown"] == [{"key": "factory", "label": "Factory", "count": 2, "total_value": Decimal("5.00")}]`.
2. returns: `result["open_by_account"] == [{"account_id": K1.id, "account_name": "Alder Supplies", "count": 1, "total_value": Decimal("1.00")}]`.

### EXO-SF-15 — a W1 order linked to W2's account is left out of open by account
- **Rules:** `aggregate_financial_snapshot_filtered` R9 [BUG-2714] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-2714
- **Fails today on:** Then 1 (the join compares ids only; "Overseas Ltd" with W2's account id is listed)

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("4.00")`, `account_id A2.id` (invalid data).
2. OB = order "EXP-T-002", but `total_amount Decimal("1.00")`, `account_id K1.id`.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result["open_by_account"] == [{"account_id": K1.id, "account_name": "Alder Supplies", "count": 1, "total_value": Decimal("1.00")}]`.

### EXO-SF-16 — an order linked to another workspace's account still counts in the category breakdown
- **Rules:** `aggregate_financial_snapshot_filtered` R1, R9 (the part that holds today)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("4.00")`, `account_id A0.id` (invalid data).
2. OB = order "EXP-T-002", but `total_amount Decimal("1.00")`, `account_id K1.id`.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result["category_breakdown"] == [{"key": "factory", "label": "Factory", "count": 2, "total_value": Decimal("5.00")}]`.
2. returns: `{"account_id": K1.id, "account_name": "Alder Supplies", "count": 1, "total_value": Decimal("1.00")} in result["open_by_account"]`.

### EXO-SF-17 — an order of a soft-deleted own account still counts under its name
- **Rules:** `aggregate_financial_snapshot_filtered` R10
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. KG = deleted account "Gone Ltd".
2. OA = order "EXP-T-001", but `total_amount Decimal("4.00")`, `account_id KG.id`.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result["open_by_account"] == [{"account_id": KG.id, "account_name": "Gone Ltd", "count": 1, "total_value": Decimal("4.00")}]`.

### EXO-SF-18 — a search through the account join counts each order once in every part
- **Rules:** `_filtered_orders_query` R1; `aggregate_financial_snapshot_filtered` R1, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-BIRCH-1", but `total_amount Decimal("2.00")`, `account_id K2.id`.
2. OB = order "EXP-T-002", but `total_amount Decimal("3.00")`, `account_id K2.id`.
3. OC = order "EXP-T-003", but `total_amount Decimal("9.00")`, `account_id K1.id`.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False, search="birch")`.

**Then**
1. returns: `result["open_by_account"] == [{"account_id": K2.id, "account_name": "Birch Traders", "count": 2, "total_value": Decimal("5.00")}]`.
2. returns: `result["category_breakdown"] == [{"key": "factory", "label": "Factory", "count": 2, "total_value": Decimal("5.00")}]`.
3. returns: `result["stage_pipeline"][0] == {"key": "draft", "label": "Draft", "count": 2, "total_value": Decimal("5.00")}`.

### EXO-SF-19 — W0's and W2's orders count in no part
- **Rules:** `_filtered_orders_query` R1; `_apply_expense_order_hub_filters` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order "EXP-T-900" of W0, but `total_amount Decimal("50.00")`, `account_id A0.id`.
2. OA = order "EXP-T-001", but `total_amount Decimal("1.00")`, `account_id K1.id`.
3. X2 = order "EXP-T-902" of W2, but `total_amount Decimal("70.00")`, `account_id A2.id`.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result["category_breakdown"] == [{"key": "factory", "label": "Factory", "count": 1, "total_value": Decimal("1.00")}]`.
2. returns: `result["stage_pipeline"][0] == {"key": "draft", "label": "Draft", "count": 1, "total_value": Decimal("1.00")}`.
3. returns: `result["open_by_account"] == [{"account_id": K1.id, "account_name": "Alder Supplies", "count": 1, "total_value": Decimal("1.00")}]`.

### EXO-SF-20 — with no flags passed, completed orders are left out of every part
- **Rules:** `_filtered_orders_query` R1 (DAO defaults)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("1.00")`.
2. OB = order "EXP-T-002", but `total_amount Decimal("2.00")`, completed.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `result["category_breakdown"] == [{"key": "factory", "label": "Factory", "count": 1, "total_value": Decimal("1.00")}]`.
2. returns: `result["stage_pipeline"][2] == {"key": "complete", "label": "Complete", "count": 0, "total_value": Decimal("0")}`.

### EXO-SF-21 — an unknown filter keyword raises TypeError
- **Rules:** `aggregate_financial_snapshot_filtered` Errors; `_filtered_orders_query` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001".

**When**
- `dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, colour="red")` inside `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.

### EXO-SF-22 — takes no lock and writes nothing
- **Rules:** `aggregate_financial_snapshot_filtered` Side effects; Overview (no lock)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `account_id K1.id`.
2. Statement recorder.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `len(result["open_by_account"]) == 1`.
2. statement: `written == []`.
3. statement: `all("FOR UPDATE" not in s for s in selects)`.

### EXO-SF-23 — two accounts with the same name and equal totals: the lower account id first
- **Rules:** `aggregate_financial_snapshot_filtered` R8 [BUG-747]
- **Kind:** bug
- **Expect:** xfail BUG-747 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (ties are unordered; insertion order puts the higher id first)

**Given**
1. seqscan.
2. KH = `Account(workspace_id=W1.id, name="Twin Co", id=HIGH_ID(accounts))`.
3. KL = `Account(workspace_id=W1.id, name="Twin Co")` (so `KL.id < KH.id`).
4. OH = order "EXP-T-001", but `total_amount Decimal("5.00")`, `account_id KH.id`.
5. OL = order "EXP-T-002", but `total_amount Decimal("5.00")`, `account_id KL.id`.
6. `db.expire_all()`

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `[e["account_id"] for e in result["open_by_account"]] == [KL.id, KH.id]`.

### EXO-SF-24 — a 0.00 order gives exactly 0.00 in its category, its stage and its open account
- **Rules:** `aggregate_financial_snapshot_filtered` R1, R5, R6 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("0.00")`, `expense_category "department"`, `account_id K1.id`.
2. OB = order "EXP-T-002", but `total_amount Decimal("10.00")`, `account_id K2.id`, completed.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result["category_breakdown"] == [{"key": "factory", "label": "Factory", "count": 1, "total_value": Decimal("10.00")}, {"key": "department", "label": "Department", "count": 1, "total_value": Decimal("0.00")}]`.
2. returns: `result["stage_pipeline"] == [{"key": "draft", "label": "Draft", "count": 1, "total_value": Decimal("0.00")}, {"key": "invoiced", "label": "Invoiced", "count": 0, "total_value": Decimal("0")}, {"key": "complete", "label": "Complete", "count": 1, "total_value": Decimal("10.00")}]`.
3. returns: `result["open_by_account"] == [{"account_id": K1.id, "account_name": "Alder Supplies", "count": 1, "total_value": Decimal("0.00")}]`.

### EXO-SF-25 — five accounts are all listed although a larger open order has no account
- **Rules:** `aggregate_financial_snapshot_filtered` R7, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K4 = `Account(workspace_id=W1.id, name="Dogwood Co")`. K5 = `Account(workspace_id=W1.id, name="Elm Works")`.
2. OA = order "EXP-T-001", but `total_amount Decimal("5.00")`, `account_id K1.id`.
3. OB = order "EXP-T-002", but `total_amount Decimal("4.00")`, `account_id K2.id`.
4. OC = order "EXP-T-003", but `total_amount Decimal("3.00")`, `account_id K3.id`.
5. OD = order "EXP-T-004", but `total_amount Decimal("2.00")`, `account_id K4.id`.
6. OE = order "EXP-T-005", but `total_amount Decimal("1.00")`, `account_id K5.id`.
7. ON = order "EXP-T-006", but `total_amount Decimal("100.00")` (no account).

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `[e["account_id"] for e in result["open_by_account"]] == [K1.id, K2.id, K3.id, K4.id, K5.id]`.
2. returns: `[e["total_value"] for e in result["open_by_account"]] == [Decimal("5.00"), Decimal("4.00"), Decimal("3.00"), Decimal("2.00"), Decimal("1.00")]`.

## `ExpenseOrderDAO.aggregate_financial_snapshot_actionable` — due timeline

*Every order here is not completed and not voided; it has no invoice, or (SA-11, SA-12) one on which today's rule and BUG-2719's intended rule agree. Completed orders and what-is-still-to-pay amounts are BUG-2719 (section "Answered by the owner — OQ-44"). Default clock: clockD(NOWX) — TODAY Tuesday 2031-11-11, EOW 2031-11-16, EOM 2031-11-30.*

### EXO-SA-01 — an empty workspace gives four empty timeline buckets and three empty pipeline buckets
- **Rules:** `aggregate_financial_snapshot_actionable` R1, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X2 = order "EXP-T-902" of W2, but `due_date TODAY`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `result["due_timeline"] == [{"key": "overdue", "label": "Overdue", "count": 0, "total_value": Decimal("0"), "samples": []}, {"key": "due_this_week", "label": "Due this week", "count": 0, "total_value": Decimal("0"), "samples": []}, {"key": "due_later_this_month", "label": "Due later this month", "count": 0, "total_value": Decimal("0"), "samples": []}, {"key": "no_due_date", "label": "No due date", "count": 0, "total_value": Decimal("0"), "samples": []}]`.
2. returns: `result["unpaid_pipeline"] == [{"key": "unpaid", "label": "Unpaid", "count": 0, "outstanding_value": Decimal("0"), "samples": []}, {"key": "partial", "label": "Partial", "count": 0, "outstanding_value": Decimal("0"), "samples": []}, {"key": "overdue", "label": "Overdue", "count": 0, "outstanding_value": Decimal("0"), "samples": []}]`.
3. returns: `set(result) == {"due_timeline", "unpaid_pipeline"}`.

### EXO-SA-02 — every bucket boundary on both sides; an order due next month is in none
- **Rules:** `aggregate_financial_snapshot_actionable` R2; `_due_date_bucket` R1–R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OY = order "EXP-T-001", but `due_date date(2031, 11, 10)`, `total_amount Decimal("1.00")`.
2. OT = order "EXP-T-002", but `due_date date(2031, 11, 11)`, `total_amount Decimal("2.00")`.
3. OE = order "EXP-T-003", but `due_date date(2031, 11, 16)`, `total_amount Decimal("4.00")`.
4. ON = order "EXP-T-004", but `due_date date(2031, 11, 17)`, `total_amount Decimal("8.00")`.
5. OM = order "EXP-T-005", but `due_date date(2031, 11, 30)`, `total_amount Decimal("16.00")`.
6. OX = order "EXP-T-006", but `due_date date(2031, 12, 1)`, `total_amount Decimal("64.00")`.
7. OZ = order "EXP-T-007", `total_amount Decimal("32.00")` (no due date).

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `(bucket(result, "due_timeline", "overdue")["count"], bucket(result, "due_timeline", "overdue")["total_value"]) == (1, Decimal("1.00"))`.
2. returns: `(bucket(result, "due_timeline", "due_this_week")["count"], bucket(result, "due_timeline", "due_this_week")["total_value"]) == (2, Decimal("6.00"))`.
3. returns: `(bucket(result, "due_timeline", "due_later_this_month")["count"], bucket(result, "due_timeline", "due_later_this_month")["total_value"]) == (2, Decimal("24.00"))`.
4. returns: `(bucket(result, "due_timeline", "no_due_date")["count"], bucket(result, "due_timeline", "no_due_date")["total_value"]) == (1, Decimal("32.00"))`.
5. returns: `[b["key"] for b in result["due_timeline"]] == ["overdue", "due_this_week", "due_later_this_month", "no_due_date"]`.

### EXO-SA-03 — samples: the first three by due date, then number as text
- **Rules:** `aggregate_financial_snapshot_actionable` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. SA = order "EXP-S-999", but `due_date date(2031, 11, 20)`, `total_amount Decimal("1.00")`.
2. SB = order "EXP-S-500", but `due_date date(2031, 11, 18)`, `total_amount Decimal("2.00")`.
3. SC = order "EXP-S-1000", but `due_date date(2031, 11, 20)`, `total_amount Decimal("3.00")`.
4. SD = order "EXP-S-100", but `due_date date(2031, 11, 25)`, `total_amount Decimal("4.00")`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "due_later_this_month")["count"] == 4`.
2. returns: `bucket(result, "due_timeline", "due_later_this_month")["total_value"] == Decimal("10.00")`.
3. returns: `bucket(result, "due_timeline", "due_later_this_month")["samples"] == [{"id": SB.id, "order_number": GN("EXP-S-500"), "total_value": Decimal("2.00"), "sublabel": "2031-11-18"}, {"id": SC.id, "order_number": GN("EXP-S-1000"), "total_value": Decimal("3.00"), "sublabel": "2031-11-20"}, {"id": SA.id, "order_number": GN("EXP-S-999"), "total_value": Decimal("1.00"), "sublabel": "2031-11-20"}]`.

### EXO-SA-04 — a no-due-date sample has sublabel None
- **Rules:** `aggregate_financial_snapshot_actionable` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OZ = order "EXP-T-007", but `total_amount Decimal("32.00")` (no due date).

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "no_due_date")["samples"] == [{"id": OZ.id, "order_number": GN("EXP-T-007"), "total_value": Decimal("32.00"), "sublabel": None}]`.

### EXO-SA-05 — a week ending in the next month: its first days are due this week, later days in none
- **Rules:** `aggregate_financial_snapshot_actionable` R2; `_due_date_bucket` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. clockD(`datetime(2031, 7, 31, 12, 0)`).
2. OA = order "EXP-T-001", but `due_date date(2031, 8, 3)`, `total_amount Decimal("1.00")`.
3. OB = order "EXP-T-002", but `due_date date(2031, 8, 4)`, `total_amount Decimal("2.00")`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "due_this_week")["count"] == 1`.
2. returns: `bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal("1.00")`.
3. returns: `bucket(result, "due_timeline", "due_later_this_month")["count"] == 0`.

### EXO-SA-06 — orders of W0 and W2 never count
- **Rules:** `aggregate_financial_snapshot_actionable` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order "EXP-T-900" of W0, but `due_date date(2031, 11, 10)`, `total_amount Decimal("50.00")`.
2. OA = order "EXP-T-001", but `due_date date(2031, 11, 10)`, `total_amount Decimal("1.00")`.
3. X2 = order "EXP-T-902" of W2, but `due_date date(2031, 11, 10)`, `total_amount Decimal("70.00")`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "overdue")["count"] == 1`.
2. returns: `bucket(result, "due_timeline", "overdue")["total_value"] == Decimal("1.00")`.

### EXO-SA-07 — amounts add exactly: 0.10 + 0.20 = 0.30
- **Rules:** `aggregate_financial_snapshot_actionable` R5 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `due_date date(2031, 11, 1)`, `total_amount Decimal("0.10")`.
2. OB = order "EXP-T-002", but `due_date date(2031, 11, 2)`, `total_amount Decimal("0.20")`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "overdue")["total_value"] == Decimal("0.30")`.
2. returns: `isinstance(bucket(result, "due_timeline", "overdue")["total_value"], Decimal)`.

### EXO-SA-08 — today is the UTC date: late on 10 November UTC, an order due that day is not overdue
- **Rules:** `_due_window_dates` R1; `aggregate_financial_snapshot_actionable` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Dhaka = `db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))`.
2. clockD(`datetime(2031, 11, 10, 23, 30)`).
3. OA = order "EXP-T-001", but `due_date date(2031, 11, 10)`, `total_amount Decimal("1.00")`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "due_this_week")["count"] == 1`.
2. returns: `bucket(result, "due_timeline", "overdue")["count"] == 0`.

### EXO-SA-09 — takes no filters: a filter keyword raises TypeError
- **Rules:** `aggregate_financial_snapshot_actionable` Purpose (no filters)
- **Kind:** error
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001".

**When**
- `dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id, search="x")` inside `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.

### EXO-SA-10 — takes no lock and writes nothing
- **Rules:** `aggregate_financial_snapshot_actionable` Side effects; Overview (no lock)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `due_date TODAY`.
2. Statement recorder.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "due_this_week")["count"] == 1`.
2. statement: `written == []`.
3. statement: `all("FOR UPDATE" not in s for s in selects)`.

### EXO-SA-11 — open orders with a partly paid confirmed or locked invoice are counted once each
- **Rules:** `aggregate_financial_snapshot_actionable` R4 (count; holds before and after BUG-2719)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. VA = inv(W1, "300.00"), but confirmed, `payment_status "partial"`, `paid_amount Decimal("100.00")`.
2. OA = order "EXP-T-001", but `total_amount Decimal("300.00")`, `due_date date(2031, 11, 12)`, `invoice_id VA.id`.
3. VB = inv(W1, "300.00"), but locked, `payment_status "partial"`, `paid_amount Decimal("299.99")`.
4. OB = order "EXP-T-002", but `total_amount Decimal("300.00")`, `due_date date(2031, 11, 13)`, `invoice_id VB.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "due_this_week")["count"] == 2`.

### EXO-SA-12 — open orders with a draft or a voided invoice count at the order total, not the invoice amount
- **Rules:** `aggregate_financial_snapshot_actionable` R4, R5 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. VA = inv(W1, "80.00") (draft, unpaid).
2. VB = inv(W1, "20.00"), but invvoid.
3. OA = order "EXP-T-001", but `total_amount Decimal("100.10")`, `due_date date(2031, 11, 12)`, `invoice_id VA.id`.
4. OB = order "EXP-T-002", but `total_amount Decimal("50.20")`, `due_date date(2031, 11, 13)`, `invoice_id VB.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "due_this_week")["count"] == 2`.
2. returns: `bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal("150.30")`.

### EXO-SA-13 — a 0.00 order gives exactly 0.00 in its timeline bucket and its sample
- **Rules:** `aggregate_financial_snapshot_actionable` R5, R6 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("0.00")`, `due_date date(2031, 11, 12)`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "due_this_week")["count"] == 1`.
2. returns: `bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal("0.00")`.
3. returns: `bucket(result, "due_timeline", "due_this_week")["samples"] == [{"id": OA.id, "order_number": GN("EXP-T-001"), "total_value": Decimal("0.00"), "sublabel": "2031-11-12"}]`.

## `ExpenseOrderDAO.aggregate_financial_snapshot_actionable` — unpaid pipeline

*Every order here is not completed and not voided, and its invoice is **confirmed** or **locked**: today's rule and BUG-2718's intended rule (owner, OQ-43) agree on these. Draft invoices and completed orders are BUG-2718 (section "Answered by the owner — OQ-43").*

### EXO-UP-01 — confirmed invoices go to the bucket of their payment status, at amount minus paid
- **Rules:** `aggregate_financial_snapshot_actionable` R7, R8, R9, R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. VA = inv(W1, "100.00"), but confirmed.
2. VB = inv(W1, "50.00"), but confirmed, `payment_status "partial"`, `paid_amount Decimal("20.10")`.
3. VC = inv(W1, "70.00"), but confirmed, `payment_status "overdue"`, `paid_amount Decimal("0.05")`.
4. OA = order "EXP-T-001", but `invoice_id VA.id`.
5. OB = order "EXP-T-002", but `invoice_id VB.id`.
6. OC = order "EXP-T-003", but `invoice_id VC.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `result["unpaid_pipeline"][0] == {"key": "unpaid", "label": "Unpaid", "count": 1, "outstanding_value": Decimal("100.00"), "samples": [{"id": OA.id, "order_number": GN("EXP-T-001"), "total_value": Decimal("100.00"), "sublabel": "unpaid"}]}`.
2. returns: `result["unpaid_pipeline"][1] == {"key": "partial", "label": "Partial", "count": 1, "outstanding_value": Decimal("29.90"), "samples": [{"id": OB.id, "order_number": GN("EXP-T-002"), "total_value": Decimal("29.90"), "sublabel": "partial"}]}`.
3. returns: `result["unpaid_pipeline"][2] == {"key": "overdue", "label": "Overdue", "count": 1, "outstanding_value": Decimal("69.95"), "samples": [{"id": OC.id, "order_number": GN("EXP-T-003"), "total_value": Decimal("69.95"), "sublabel": "overdue"}]}`.

### EXO-UP-02 — a paid invoice puts its order in no bucket
- **Rules:** `aggregate_financial_snapshot_actionable` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. VA = inv(W1, "40.00"), but confirmed, `payment_status "paid"`, `paid_amount Decimal("40.00")`.
2. OA = order "EXP-T-001", but `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `[b["count"] for b in result["unpaid_pipeline"]] == [0, 0, 0]`.

### EXO-UP-03 — a voided invoice puts its order in no bucket
- **Rules:** `aggregate_financial_snapshot_actionable` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. VA = inv(W1, "40.00"), but invvoid.
2. OA = order "EXP-T-001", but `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `[b["count"] for b in result["unpaid_pipeline"]] == [0, 0, 0]`.

### EXO-UP-04 — an overpaid invoice adds a negative outstanding
- **Rules:** `aggregate_financial_snapshot_actionable` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. VA = inv(W1, "10.00"), but confirmed, `payment_status "partial"`, `paid_amount Decimal("12.50")`.
2. VB = inv(W1, "5.00"), but confirmed, `payment_status "partial"`, `paid_amount Decimal("1.00")`.
3. OA = order "EXP-T-001", but `invoice_id VA.id`.
4. OB = order "EXP-T-002", but `invoice_id VB.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "unpaid_pipeline", "partial")["count"] == 2`.
2. returns: `bucket(result, "unpaid_pipeline", "partial")["outstanding_value"] == Decimal("1.50")`.

### EXO-UP-05 — samples: the three largest outstanding amounts first
- **Rules:** `aggregate_financial_snapshot_actionable` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. VA = inv(W1, "5.00"), but confirmed. VB = inv(W1, "40.00"), but confirmed. VC = inv(W1, "20.00"), but confirmed. VD = inv(W1, "30.00"), but confirmed.
2. OA = order "EXP-T-001", but `invoice_id VA.id`.
3. OB = order "EXP-T-002", but `invoice_id VB.id`.
4. OC = order "EXP-T-003", but `invoice_id VC.id`.
5. OD = order "EXP-T-004", but `invoice_id VD.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "unpaid_pipeline", "unpaid")["count"] == 4`.
2. returns: `bucket(result, "unpaid_pipeline", "unpaid")["outstanding_value"] == Decimal("95.00")`.
3. returns: `[s["id"] for s in bucket(result, "unpaid_pipeline", "unpaid")["samples"]] == [OB.id, OD.id, OC.id]`.

### EXO-UP-06 — equal outstanding amounts: the lower order id first
- **Rules:** `aggregate_financial_snapshot_actionable` R11 [BUG-748]
- **Kind:** bug
- **Expect:** xfail BUG-748 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (ties are unordered; a sequential scan meets OB, the higher id, first)

**Given**
1. seqscan.
2. VA = inv(W1, "30.00"), but confirmed. VB = inv(W1, "30.00"), but confirmed.
3. OB = order "EXP-T-002", but `id HIGH_ID("expense_orders")`, `invoice_id VB.id`.
4. OA = order "EXP-T-001", but `invoice_id VA.id` (sequence id, lower than OB's).
5. `db.expire_all()`

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `[s["id"] for s in bucket(result, "unpaid_pipeline", "unpaid")["samples"]] == [OA.id, OB.id]`.

### EXO-UP-07 — the pipeline query breaks ties by order id ascending
- **Rules:** `aggregate_financial_snapshot_actionable` R11 [BUG-748]
- **Kind:** bug
- **Expect:** xfail BUG-748
- **Author:** claude
- **Fails today on:** Then 2 (the pipeline `ORDER BY` has the outstanding amount only)

**Given**
1. VA = inv(W1, "30.00"), but confirmed.
2. OA = order "EXP-T-001", but `invoice_id VA.id`.
3. Statement recorder.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "unpaid_pipeline", "unpaid")["count"] == 1`.
2. statement: `pipe = next(s for s in selects if "account_invoices" in s)`; the text of `pipe` after its first `ORDER BY` ends with `expense_orders.id` or `expense_orders.id ASC` (after `.strip()`).

### EXO-UP-08 — a W1 order linked to W0's invoice is left out of the pipeline
- **Rules:** `aggregate_financial_snapshot_actionable` R10 [BUG-2714] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-2714
- **Fails today on:** Then 1 (the join compares ids only; W0's 50.00 is counted in W1's "Partial")

**Given**
1. V0 = inv(W0, "80.00"), but confirmed, `payment_status "partial"`, `paid_amount Decimal("30.00")`.
2. OA = order "EXP-T-001", but `invoice_id V0.id` (invalid data).

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "unpaid_pipeline", "partial")["count"] == 0`.
2. returns: `bucket(result, "unpaid_pipeline", "partial")["samples"] == []`.

### EXO-UP-09 — a W1 order linked to W2's invoice is left out of the pipeline
- **Rules:** `aggregate_financial_snapshot_actionable` R10 [BUG-2714] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-2714
- **Fails today on:** Then 1 (the join compares ids only; W2's 50.00 is counted in W1's "Partial")

**Given**
1. V9 = inv(W2, "80.00"), but confirmed, `payment_status "partial"`, `paid_amount Decimal("30.00")`.
2. OA = order "EXP-T-001", but `invoice_id V9.id` (invalid data).

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "unpaid_pipeline", "partial")["count"] == 0`.
2. returns: `bucket(result, "unpaid_pipeline", "partial")["samples"] == []`.

### EXO-UP-10 — two orders sharing one invoice each count its full outstanding
- **Rules:** `aggregate_financial_snapshot_actionable` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. VA = inv(W1, "30.00"), but confirmed.
2. OA = order "EXP-T-001", but `invoice_id VA.id`.
3. OB = order "EXP-T-002", but `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "unpaid_pipeline", "unpaid")["count"] == 2`.
2. returns: `bucket(result, "unpaid_pipeline", "unpaid")["outstanding_value"] == Decimal("60.00")`.

### EXO-UP-11 — W0's and W2's own orders and invoices do not count for W1
- **Rules:** `aggregate_financial_snapshot_actionable` R8 (of this workspace)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. V0 = inv(W0, "10.00"), but confirmed.
2. X0 = order "EXP-T-900" of W0, but `invoice_id V0.id`.
3. VA = inv(W1, "1.00"), but confirmed.
4. OA = order "EXP-T-001", but `invoice_id VA.id`.
5. V9 = inv(W2, "20.00"), but confirmed.
6. X2 = order "EXP-T-902" of W2, but `invoice_id V9.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "unpaid_pipeline", "unpaid")["count"] == 1`.
2. returns: `bucket(result, "unpaid_pipeline", "unpaid")["outstanding_value"] == Decimal("1.00")`.

### EXO-UP-12 — an open order with a locked partial invoice is in Partial at amount minus paid
- **Rules:** `aggregate_financial_snapshot_actionable` R8, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. VA = inv(W1, "100.00"), but locked, `payment_status "partial"`, `paid_amount Decimal("40.00")`.
2. OA = order "EXP-T-001", but `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "unpaid_pipeline", "partial")["count"] == 1`.
2. returns: `bucket(result, "unpaid_pipeline", "partial")["outstanding_value"] == Decimal("60.00")`.

### EXO-UP-13 — a confirmed 0.00 invoice with nothing paid gives exactly 0.00 outstanding
- **Rules:** `aggregate_financial_snapshot_actionable` R8, R9, R11 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. VA = inv(W1, "0.00"), but confirmed.
2. OA = order "EXP-T-001", but `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "unpaid_pipeline", "unpaid")["count"] == 1`.
2. returns: `bucket(result, "unpaid_pipeline", "unpaid")["outstanding_value"] == Decimal("0.00")`.
3. returns: `bucket(result, "unpaid_pipeline", "unpaid")["samples"] == [{"id": OA.id, "order_number": GN("EXP-T-001"), "total_value": Decimal("0.00"), "sublabel": "unpaid"}]`.

### EXO-UP-14 — samples are ordered by what is still owed, not by the invoice amount
- **Rules:** `aggregate_financial_snapshot_actionable` R9, R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. VA = inv(W1, "100.00"), but confirmed, `payment_status "partial"`, `paid_amount Decimal("90.00")`.
2. VB = inv(W1, "50.00"), but confirmed, `payment_status "partial"`, `paid_amount Decimal("10.00")`.
3. OA = order "EXP-T-001", but `invoice_id VA.id`.
4. OB = order "EXP-T-002", but `invoice_id VB.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "unpaid_pipeline", "partial")["outstanding_value"] == Decimal("50.00")`.
2. returns: `[s["id"] for s in bucket(result, "unpaid_pipeline", "partial")["samples"]] == [OB.id, OA.id]`.
3. returns: `[s["total_value"] for s in bucket(result, "unpaid_pipeline", "partial")["samples"]] == [Decimal("40.00"), Decimal("10.00")]`.

## `ExpenseOrderDAO.get_by_id_and_workspace`

### EXO-GI-01 — returns the order of this workspace, the middle of three
- **Rules:** `ExpenseOrderDAO.get_by_id_and_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".
2. O2 = order "EXP-T-002".
3. O3 = order "EXP-T-003".

**When**
- `result = dao.get_by_id_and_workspace(db, id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, ExpenseOrder)`.
2. returns: `result.id == O2.id`.
3. returns: `result.expense_number == GN("EXP-T-002")`.

### EXO-GI-02 — W0's order asked for W1 is None
- **Rules:** `ExpenseOrderDAO.get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order "EXP-T-900" of W0.
2. O1 = order "EXP-T-001".

**When**
- `result = dao.get_by_id_and_workspace(db, id=X0.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### EXO-GI-03 — W2's order asked for W1 is None
- **Rules:** `ExpenseOrderDAO.get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".
2. X2 = order "EXP-T-902" of W2.

**When**
- `result = dao.get_by_id_and_workspace(db, id=X2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### EXO-GI-04 — a completed and voided order is still returned
- **Rules:** `ExpenseOrderDAO.get_by_id_and_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001", but completed, voided.

**When**
- `result = dao.get_by_id_and_workspace(db, id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O1.id`.

### EXO-GI-05 — an unknown id is None
- **Rules:** `ExpenseOrderDAO.get_by_id_and_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### EXO-GI-06 — positional arguments raise TypeError
- **Rules:** `ExpenseOrderDAO.get_by_id_and_workspace` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".

**When**
- `dao.get_by_id_and_workspace(db, O1.id, W1.id)` inside `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.

### EXO-GI-07 — one SELECT, no lock
- **Rules:** `ExpenseOrderDAO.get_by_id_and_workspace` Side effects; Overview (no lock)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".
2. `db.expunge_all()`
3. Statement recorder.

**When**
- `result = dao.get_by_id_and_workspace(db, id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == O1.id`.
2. statement: `len(selects) == 1`.
3. statement: `"FOR UPDATE" not in sql`.
4. statement: `written == []`.

## `ExpenseOrderDAO.get_next_number`

*Stored numbers here are exact (builder **numbered**). Default clock: clockN(`datetime(2031, 6, 1, 12, 0)`, `datetime(2031, 6, 1, 12, 0)`).*

### EXO-NX-01 — no number yet gives EXP-2031-001
- **Rules:** `get_next_number` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, str)`.
2. returns: `result == "EXP-2031-001"`.

### EXO-NX-02 — after 002 comes 003
- **Rules:** `get_next_number` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = numbered "EXP-2031-002".

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-003"`.

### EXO-NX-03 — the highest number decides, not the count
- **Rules:** `get_next_number` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. O9 = numbered "EXP-2031-009".
2. O1 = numbered "EXP-2031-001".
3. O2 = numbered "EXP-2031-002".

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-010"`.

### EXO-NX-04 — after 998 comes 999
- **Rules:** `get_next_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = numbered "EXP-2031-998".

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-999"`.

### EXO-NX-05 — after 999 comes 1000, not cut to three digits
- **Rules:** `get_next_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = numbered "EXP-2031-999".

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-1000"`.

### EXO-NX-06 — after 1000 alone comes 1001
- **Rules:** `get_next_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = numbered "EXP-2031-1000".

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-1001"`.

### EXO-NX-07 — with 999 and 1000 stored, the numeric maximum gives 1001
- **Rules:** `get_next_number` R3 [BUG-749]
- **Kind:** bug
- **Expect:** xfail BUG-749
- **Fails today on:** Then 1 (the text maximum `999` wins today, so it returns `EXP-2031-1000` again)

**Given**
1. O1 = numbered "EXP-2031-999".
2. O2 = numbered "EXP-2031-1000".

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-1001"`.

### EXO-NX-08 — a non-numeric suffix alone gives 001
- **Rules:** `get_next_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = numbered "EXP-2031-abc".

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-001"`.

### EXO-NX-09 — a non-numeric suffix beside 004 is ignored: 005
- **Rules:** `get_next_number` R3 [BUG-749]
- **Kind:** bug
- **Expect:** xfail BUG-749
- **Fails today on:** Then 1 (`abc` is the text maximum today and is not a number, so it returns `EXP-2031-001`)

**Given**
1. O1 = numbered "EXP-2031-004".
2. O2 = numbered "EXP-2031-abc".

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-005"`.

### EXO-NX-10 — only W1's numbers count, with higher numbers in W0 and W2
- **Rules:** `get_next_number` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = numbered "EXP-2031-050" of W0.
2. O1 = numbered "EXP-2031-003".
3. X2 = numbered "EXP-2031-070" of W2.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-004"`.

### EXO-NX-11 — asked for W2, only W2's numbers count
- **Rules:** `get_next_number` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = numbered "EXP-2031-090" of W0.
2. O1 = numbered "EXP-2031-080".
3. X2 = numbered "EXP-2031-070" of W2.

**When**
- `result = dao.get_next_number(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == "EXP-2031-071"`.

### EXO-NX-12 — asked for W0, only W0's numbers count
- **Rules:** `get_next_number` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = numbered "EXP-2031-050" of W0.
2. O1 = numbered "EXP-2031-080".
3. X2 = numbered "EXP-2031-090" of W2.

**When**
- `result = dao.get_next_number(db, workspace_id=W0.id)`.

**Then**
1. returns: `result == "EXP-2031-051"`.

### EXO-NX-13 — an unknown workspace gets 001
- **Rules:** `get_next_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = numbered "EXP-2031-005".

**When**
- `result = dao.get_next_number(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == "EXP-2031-001"`.

### EXO-NX-14 — numbers of the year before and after do not count
- **Rules:** `get_next_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = numbered "EXP-2030-500".
2. O2 = numbered "EXP-2032-600".

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-001"`.

### EXO-NX-15 — a lowercase stored prefix does not count
- **Rules:** `get_next_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = numbered "exp-2031-005".

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-001"`.

### EXO-NX-16 — a stored number with a leading space does not count
- **Rules:** `get_next_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = numbered " EXP-2031-005".

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-001"`.

### EXO-NX-17 — the prefix in the middle of a stored number does not count
- **Rules:** `get_next_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = numbered "XEXP-2031-005".

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-001"`.

### EXO-NX-18 — a number with a longer year (EXP-20311-) does not count
- **Rules:** `get_next_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = numbered "EXP-20311-005".

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-001"`.

### EXO-NX-19 — voided and completed orders keep their numbers counted
- **Rules:** `get_next_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = numbered "EXP-2031-006", but completed.
2. O2 = numbered "EXP-2031-007", but voided.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-008"`.

### EXO-NX-20 — the year comes from the clock: both clocks in 2032, last year's numbers ignored
- **Rules:** `get_next_number` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = numbered "EXP-2031-005".
2. clockN(`datetime(2032, 3, 1, 12, 0)`, `datetime(2032, 3, 1, 12, 0)`).

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2032-001"`.

### EXO-NX-21 — the year is UTC's when the local clock is already in the next year
- **Rules:** `get_next_number` R1 [BUG-2710]
- **Kind:** bug
- **Expect:** xfail BUG-2710
- **Fails today on:** Then 1 (the year comes from `datetime.now()` today, giving `EXP-2032-001`)

**Given**
1. O1 = numbered "EXP-2031-005".
2. clockN(`datetime(2032, 1, 1, 5, 0)`, `datetime(2031, 12, 31, 23, 0)`).

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-006"`.

### EXO-NX-22 — the year is UTC's when the local clock is still in the old year
- **Rules:** `get_next_number` R1 [BUG-2710]
- **Kind:** bug
- **Expect:** xfail BUG-2710
- **Fails today on:** Then 1 (the year comes from `datetime.now()` today, giving `EXP-2031-006`)

**Given**
1. O1 = numbered "EXP-2031-005".
2. clockN(`datetime(2031, 12, 31, 23, 0)`, `datetime(2032, 1, 1, 1, 0)`).

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2032-001"`.

### EXO-NX-23 — writes nothing: a pending order is not counted and stays pending
- **Rules:** `get_next_number` R4, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = numbered "EXP-2031-002".
2. `O1.description = "Edited"` (not flushed).
3. `P = ExpenseOrder(workspace_id=W1.id, expense_number="EXP-2031-009", expense_category="factory", expense_date=D2, subtotal=Decimal("0.00"), total_amount=Decimal("10.00"), created_by=U1.id)`
4. `db.add(P)` (not flushed).
5. Statement recorder.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-003"`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `O1 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.

### EXO-NX-24 — reads with no row lock
- **Rules:** `get_next_number` R4 [BUG-749] (no lock — the part that holds today)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = numbered "EXP-2031-002".
2. `db.expunge_all()`
3. Statement recorder.

**When**
- `result = dao.get_next_number(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == "EXP-2031-003"`.
2. statement: `"FOR UPDATE" not in sql`.

### EXO-NX-25 — positional arguments raise TypeError
- **Rules:** `get_next_number` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no order.

**When**
- `dao.get_next_number(db, W1.id)` inside `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.

### EXO-NX-26 — the same number twice in one workspace is refused by the database
- **Rules:** `get_next_number` R4a (`uq_eo_workspace_number`)
- **Kind:** error
- **Expect:** pass

**Given**
1. O1 = numbered "EXP-2031-001".

**When**
- `db.add(ExpenseOrder(workspace_id=W1.id, expense_number="EXP-2031-001", expense_category="factory", expense_date=D2, subtotal=Decimal("0.00"), total_amount=Decimal("10.00"), created_by=U1.id)); db.flush()` inside `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23505"`.

### EXO-NX-27 — the same number in another workspace is accepted
- **Rules:** `get_next_number` R4a [BUG-749] (per-workspace uniqueness)
- **Kind:** bug
- **Expect:** xfail BUG-749
- **Fails today on:** Then 1 (the call raises IntegrityError: 23505 on the global index `ix_expense_orders_expense_number`)

**Given**
1. O1 = numbered "EXP-2031-001".

**When**
- `X2 = ExpenseOrder(workspace_id=W2.id, expense_number="EXP-2031-001", expense_category="factory", expense_date=D2, subtotal=Decimal("0.00"), total_amount=Decimal("10.00"), created_by=U1.id)`, then `with db.begin_nested(): db.add(X2); db.flush()`.

**Then**
1. returns: `X2.id is not None`.
2. count: `db.scalar(text("SELECT count(*) FROM expense_orders WHERE expense_number = 'EXP-2031-001'")) == 2`.

## `ExpenseOrderItemDAO.get_by_order`

### EXO-GO-01 — lines by line number ascending, inserted out of order
- **Rules:** `get_by_order` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".
2. L3 = line(O1, 3).
3. L1 = line(O1, 1).
4. L2 = line(O1, 2).

**When**
- `result = idao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [L1.id, L2.id, L3.id]`.

### EXO-GO-02 — only the asked order's lines, with lower and higher orders around it
- **Rules:** `get_by_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001". O2 = order "EXP-T-002". O3 = order "EXP-T-003".
2. LA = line(O1, 1).
3. LB = line(O2, 1).
4. LC = line(O3, 1).

**When**
- `result = idao.get_by_order(db, expense_order_id=O2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [LB.id]`.

### EXO-GO-03 — a line stored with W0's workspace_id is left out
- **Rules:** `get_by_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".
2. LA = line(O1, 1).
3. LX = line(O1, 2), but `workspace_id W0.id` (invalid data).

**When**
- `result = idao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [LA.id]`.

### EXO-GO-04 — a line stored with W2's workspace_id is left out
- **Rules:** `get_by_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".
2. LA = line(O1, 1).
3. LX = line(O1, 2), but `workspace_id W2.id` (invalid data).

**When**
- `result = idao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [LA.id]`.

### EXO-GO-05 — W1's order asked for W2 gives []
- **Rules:** `get_by_order` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".
2. LA = line(O1, 1).

**When**
- `result = idao.get_by_order(db, expense_order_id=O1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### EXO-GO-06 — an unknown order gives []
- **Rules:** `get_by_order` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".
2. LA = line(O1, 1).

**When**
- `result = idao.get_by_order(db, expense_order_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### EXO-GO-07 — equal line numbers: the lower id first
- **Rules:** `get_by_order` R2 [BUG-2713]
- **Kind:** bug
- **Expect:** xfail BUG-2713 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no `id` tie-breaker; a sequential scan meets the higher id first)

**Given**
1. seqscan.
2. O1 = order "EXP-T-001".
3. LH = line(O1, 3), but `id HIGH_ID("expense_order_items")`.
4. LL = line(O1, 3) (sequence id, lower than LH's).
5. `db.expire_all()`

**When**
- `result = idao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [LL.id, LH.id]`.

### EXO-GO-08 — the query orders by line number, then id
- **Rules:** `get_by_order` R2 [BUG-2713]
- **Kind:** bug
- **Expect:** xfail BUG-2713
- **Fails today on:** Then 3 (the `ORDER BY` has `line_number` only)

**Given**
1. O1 = order "EXP-T-001".
2. LA = line(O1, 1).
3. Statement recorder.

**When**
- `result = idao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [LA.id]`.
2. statement: `"expense_order_items.line_number" in order_part`.
3. statement: `"expense_order_items.id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.

### EXO-GO-09 — line money comes back as stored, rounded half up
- **Rules:** `get_by_order` R1 (HR-15, `Numeric(15, 2)`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".
2. LA = line(O1, 1), but `unit_price Decimal("2.125")`, `line_subtotal Decimal("0.005")`.
3. LB = line(O1, 2), but `unit_price Decimal("-1.005")`, `line_subtotal Decimal("2.124")`.
4. `db.expunge_all()`

**When**
- `result = idao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result[0].unit_price == Decimal("2.13")`.
2. returns: `result[0].line_subtotal == Decimal("0.01")`.
3. returns: `result[1].unit_price == Decimal("-1.01")`.
4. returns: `result[1].line_subtotal == Decimal("2.12")`.

### EXO-GO-10 — one SELECT, no lock, no parent join
- **Rules:** `get_by_order` Side effects; Overview (no lock)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".
2. LA = line(O1, 1).
3. `db.expunge_all()`
4. Statement recorder.

**When**
- `result = idao.get_by_order(db, expense_order_id=O1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [LA.id]`.
2. statement: `len(selects) == 1`.
3. statement: `"FOR UPDATE" not in sql`.
4. statement: `"JOIN" not in sql.upper()`.

## `ExpenseOrderItemDAO.get_by_id_and_workspace`

### EXO-II-01 — returns the line of this workspace, the middle of three
- **Rules:** `ExpenseOrderItemDAO.get_by_id_and_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".
2. LA = line(O1, 1). LB = line(O1, 2). LC = line(O1, 3).

**When**
- `result = idao.get_by_id_and_workspace(db, id=LB.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, ExpenseOrderItem)`.
2. returns: `result.id == LB.id`.

### EXO-II-02 — a line of W0 asked for W1 is None
- **Rules:** `ExpenseOrderItemDAO.get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = order "EXP-T-900" of W0.
2. LX = line(X0, 1), but `workspace_id W0.id`.
3. O1 = order "EXP-T-001".
4. LA = line(O1, 1).

**When**
- `result = idao.get_by_id_and_workspace(db, id=LX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### EXO-II-03 — a line of W2 asked for W1 is None
- **Rules:** `ExpenseOrderItemDAO.get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".
2. LA = line(O1, 1).
3. X2 = order "EXP-T-902" of W2.
4. LX = line(X2, 1), but `workspace_id W2.id`.

**When**
- `result = idao.get_by_id_and_workspace(db, id=LX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### EXO-II-04 — an unknown id is None
- **Rules:** `ExpenseOrderItemDAO.get_by_id_and_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".
2. LA = line(O1, 1).

**When**
- `result = idao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### EXO-II-05 — positional arguments raise TypeError
- **Rules:** `ExpenseOrderItemDAO.get_by_id_and_workspace` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".
2. LA = line(O1, 1).

**When**
- `idao.get_by_id_and_workspace(db, LA.id, W1.id)` inside `raises: TypeError`.

**Then**
1. raises: `isinstance(exc.value, TypeError)`.

### EXO-II-06 — one SELECT, no lock, the parent order not read
- **Rules:** `ExpenseOrderItemDAO.get_by_id_and_workspace` R1 (parent not looked at); Overview (no lock)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. O1 = order "EXP-T-001".
2. LA = line(O1, 1).
3. `db.expunge_all()`
4. Statement recorder.

**When**
- `result = idao.get_by_id_and_workspace(db, id=LA.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == LA.id`.
2. statement: `len(selects) == 1`.
3. statement: `"FOR UPDATE" not in sql`.
4. statement: `"expense_orders." not in sql`.

## Answered by the owner — OQ-42 → BUG-2717

*Owner, 2026-11-11 (BUG-2717): voided orders never count in the hub's money figures (`aggregate_hub_stats` `total_value`, `open_count`, `open_value`; the category breakdown; the stage pipeline; open by account), whatever `exclude_voided` says. `total_count` and `not_invoiced_count` keep following `exclude_voided` (R1, R3; pass card EXO-HS-11). With `exclude_voided=True` nothing changes (R3a, pass card EXO-OQ42-03). Today a voided order counts everywhere when `exclude_voided` is false. The xfail cards assert the intended figures.*

### EXO-OQ42-01 — stats leave a voided order out of total value and open, but count it in total and not invoiced
- **Rules:** `aggregate_hub_stats` R1, R2, R3 [BUG-2717]
- **Kind:** bug
- **Expect:** xfail BUG-2717
- **Fails today on:** Then 3 (today the voided 30.00 is added: 180.00)

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("100.00")`.
2. OB = order "EXP-T-002", but `total_amount Decimal("50.00")`.
3. OC = order "EXP-T-003", but `total_amount Decimal("30.00")`, voided.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result[0] == 3`.
2. returns: `result[4] == 3`.
3. returns: `result[1] == Decimal("150.00")`.
4. returns: `result[2] == 2`.
5. returns: `result[3] == Decimal("150.00")`.

### EXO-OQ42-02 — a voided invoiced order is not open and adds no value
- **Rules:** `aggregate_hub_stats` R1, R2, R3 [BUG-2717]
- **Kind:** bug
- **Expect:** xfail BUG-2717
- **Fails today on:** Then 3 (today the voided 30.00 is added: 130.00)

**Given**
1. V1 = inv(W1, "30.00").
2. OA = order "EXP-T-001", but `total_amount Decimal("100.00")`.
3. OC = order "EXP-T-003", but `total_amount Decimal("30.00")`, voided, `invoice_id V1.id`.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result[0] == 2`.
2. returns: `result[4] == 1`.
3. returns: `result[1] == Decimal("100.00")`.
4. returns: `result[2] == 1`.
5. returns: `result[3] == Decimal("100.00")`.

### EXO-OQ42-03 — with exclude_voided true, stats leave the voided order out
- **Rules:** `aggregate_hub_stats` R3a; `_apply_expense_order_hub_filters` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("100.00")`.
2. OB = order "EXP-T-002", but `total_amount Decimal("50.00")`.
3. OC = order "EXP-T-003", but `total_amount Decimal("30.00")`, voided.

**When**
- `result = dao.aggregate_hub_stats(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=True)`.

**Then**
1. returns: `result == (2, Decimal("150.00"), 2, Decimal("150.00"), 2)`.

### EXO-OQ42-04 — the category breakdown leaves a voided order out of its category
- **Rules:** `aggregate_financial_snapshot_filtered` R1 [BUG-2717]
- **Kind:** bug
- **Expect:** xfail BUG-2717
- **Fails today on:** Then 1 (today count 2, total 15.00)

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("10.00")`.
2. OB = order "EXP-T-002", but `total_amount Decimal("5.00")`, voided.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result["category_breakdown"] == [{"key": "factory", "label": "Factory", "count": 1, "total_value": Decimal("10.00")}]`.

### EXO-OQ42-05 — the stage pipeline counts no voided order in any stage
- **Rules:** `aggregate_financial_snapshot_filtered` R5 [BUG-2717]; `_expense_order_stage_key_expr` R1
- **Kind:** bug
- **Expect:** xfail BUG-2717
- **Fails today on:** Then 1 (today each voided order counts 1 in its own stage)

**Given**
1. V1 = inv(W1, "2.00").
2. OA = order "EXP-T-001", but `total_amount Decimal("1.00")`, voided.
3. OB = order "EXP-T-002", but `total_amount Decimal("2.00")`, voided, `invoice_id V1.id`.
4. OC = order "EXP-T-003", but `total_amount Decimal("4.00")`, voided, completed.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result["stage_pipeline"] == [{"key": "draft", "label": "Draft", "count": 0, "total_value": Decimal("0")}, {"key": "invoiced", "label": "Invoiced", "count": 0, "total_value": Decimal("0")}, {"key": "complete", "label": "Complete", "count": 0, "total_value": Decimal("0")}]`.

### EXO-OQ42-06 — open by account leaves a voided order of the account out
- **Rules:** `aggregate_financial_snapshot_filtered` R6a [BUG-2717]
- **Kind:** bug
- **Expect:** xfail BUG-2717
- **Fails today on:** Then 1 (today count 2, total 15.00)

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("10.00")`, `account_id K1.id`.
2. OB = order "EXP-T-002", but `total_amount Decimal("5.00")`, `account_id K1.id`, voided.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result["open_by_account"] == [{"account_id": K1.id, "account_name": "Alder Supplies", "count": 1, "total_value": Decimal("10.00")}]`.

### EXO-OQ42-07 — a category with only voided orders has no entry
- **Rules:** `aggregate_financial_snapshot_filtered` R1 [BUG-2717]
- **Kind:** bug
- **Expect:** xfail BUG-2717
- **Fails today on:** Then 1 (today a "department" entry with count 1, 7.00 is listed)

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("10.00")`.
2. OB = order "EXP-T-002", but `total_amount Decimal("7.00")`, `expense_category "department"`, voided.

**When**
- `result = dao.aggregate_financial_snapshot_filtered(db, workspace_id=W1.id, exclude_complete=False, exclude_voided=False)`.

**Then**
1. returns: `result["category_breakdown"] == [{"key": "factory", "label": "Factory", "count": 1, "total_value": Decimal("10.00")}]`.

## Answered by the owner — OQ-43 → BUG-2718

*Owner, 2026-11-11 (BUG-2718): the unpaid pipeline lists not-voided orders, **completed or not**, whose invoice is `confirmed` or `locked` with `payment_status` `unpaid` / `partial` / `overdue`, at `invoice_amount − paid_amount`. Draft and voided invoices are left out. Today the pipeline takes only orders that are not completed, with any invoice that is not voided: a draft invoice counts as Unpaid at its full amount, and a completed order is never listed. Open orders with a confirmed or locked invoice hold both today and after the fix (cards EXO-UP-01 … UP-12). Default clock clockD(NOWX).*

### EXO-OQ43-01 — a draft invoice is not in the pipeline
- **Rules:** `aggregate_financial_snapshot_actionable` R8 [BUG-2718]
- **Kind:** bug
- **Expect:** xfail BUG-2718
- **Fails today on:** Then 1 (today the draft invoice counts as Unpaid, count 1)

**Given**
1. VA = inv(W1, "100.00") (draft, unpaid).
2. OA = order "EXP-T-001", but `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "unpaid_pipeline", "unpaid")["count"] == 0`.
2. returns: `bucket(result, "unpaid_pipeline", "unpaid")["outstanding_value"] == Decimal("0")`.
3. returns: `bucket(result, "unpaid_pipeline", "unpaid")["samples"] == []`.

### EXO-OQ43-02 — a completed order with 60.00 still owed is in Partial
- **Rules:** `aggregate_financial_snapshot_actionable` R8, R9, R11 [BUG-2718]
- **Kind:** bug
- **Expect:** xfail BUG-2718
- **Fails today on:** Then 1 (today a completed order is never listed, count 0)

**Given**
1. VA = inv(W1, "100.00"), but confirmed, `payment_status "partial"`, `paid_amount Decimal("40.00")`.
2. OA = order "EXP-T-001", but completed, `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `result["unpaid_pipeline"][1] == {"key": "partial", "label": "Partial", "count": 1, "outstanding_value": Decimal("60.00"), "samples": [{"id": OA.id, "order_number": GN("EXP-T-001"), "total_value": Decimal("60.00"), "sublabel": "partial"}]}`.

### EXO-OQ43-03 — a completed order with an unpaid confirmed invoice adds to Unpaid
- **Rules:** `aggregate_financial_snapshot_actionable` R8, R9 [BUG-2718]
- **Kind:** bug
- **Expect:** xfail BUG-2718
- **Fails today on:** Then 1 (today only OB counts: count 1)

**Given**
1. VA = inv(W1, "100.00"), but confirmed.
2. OA = order "EXP-T-001", but completed, `invoice_id VA.id`.
3. VB = inv(W1, "7.00"), but confirmed.
4. OB = order "EXP-T-002", but `invoice_id VB.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "unpaid_pipeline", "unpaid")["count"] == 2`.
2. returns: `bucket(result, "unpaid_pipeline", "unpaid")["outstanding_value"] == Decimal("107.00")`.

### EXO-OQ43-04 — a voided order with a confirmed partial invoice is left out
- **Rules:** `aggregate_financial_snapshot_actionable` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. VA = inv(W1, "50.00"), but confirmed, `payment_status "partial"`, `paid_amount Decimal("10.00")`.
2. OA = order "EXP-T-001", but voided, `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `[b["count"] for b in result["unpaid_pipeline"]] == [0, 0, 0]`.

### EXO-OQ43-05 — beside a confirmed 0.20, a draft 0.10 adds nothing
- **Rules:** `aggregate_financial_snapshot_actionable` R8, R9 [BUG-2718]
- **Kind:** bug
- **Expect:** xfail BUG-2718
- **Fails today on:** Then 1 (today both count: count 2, 0.30)

**Given**
1. VA = inv(W1, "0.10") (draft, unpaid).
2. VB = inv(W1, "0.20"), but confirmed.
3. OA = order "EXP-T-001", but `invoice_id VA.id`.
4. OB = order "EXP-T-002", but `invoice_id VB.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "unpaid_pipeline", "unpaid")["count"] == 1`.
2. returns: `bucket(result, "unpaid_pipeline", "unpaid")["outstanding_value"] == Decimal("0.20")`.

### EXO-OQ43-06 — a completed order with a locked partial invoice is in Partial
- **Rules:** `aggregate_financial_snapshot_actionable` R8, R9 [BUG-2718]
- **Kind:** bug
- **Expect:** xfail BUG-2718
- **Fails today on:** Then 1 (today a completed order is never listed, count 0)

**Given**
1. VA = inv(W1, "100.00"), but locked, `payment_status "partial"`, `paid_amount Decimal("40.00")`.
2. OA = order "EXP-T-001", but completed, `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "unpaid_pipeline", "partial")["count"] == 1`.
2. returns: `bucket(result, "unpaid_pipeline", "partial")["outstanding_value"] == Decimal("60.00")`.

## Answered by the owner — OQ-44 → BUG-2719

*Owner, 2026-11-11 (BUG-2719): the due timeline counts not-voided orders, **completed or not**, that are not fully paid, at what is still to pay, bucketed by the order's `due_date`. With no invoice, a draft invoice or a voided invoice that is the order's `total_amount`. With a confirmed or `locked` invoice it is `invoice_amount − paid_amount`, and the order is left out when that is 0 or less or the invoice is `paid`. Samples show the same amount. Today the timeline takes orders that are not voided and not completed, at `total_amount` whatever is paid. What holds both today and after the fix (open orders; no, draft or voided invoice; the count of a partly paid open order) is in pass cards EXO-SA-01 … SA-12. Default clock clockD(NOWX).*

### EXO-OQ44-01 — a completed order due yesterday, nothing paid, is overdue
- **Rules:** `aggregate_financial_snapshot_actionable` R4, R5 [BUG-2719]
- **Kind:** bug
- **Expect:** xfail BUG-2719
- **Fails today on:** Then 1 (today a completed order is never in the timeline, count 0)

**Given**
1. VA = inv(W1, "500.00"), but confirmed.
2. OA = order "EXP-T-001", but `total_amount Decimal("500.00")`, `due_date date(2031, 11, 10)`, completed, `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "overdue")["count"] == 1`.
2. returns: `bucket(result, "due_timeline", "overdue")["total_value"] == Decimal("500.00")`.

### EXO-OQ44-02 — a voided order due tomorrow is not due this week
- **Rules:** `aggregate_financial_snapshot_actionable` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("300.00")`, `due_date date(2031, 11, 12)`, voided.
2. OB = order "EXP-T-002", but `total_amount Decimal("1.00")`, `due_date date(2031, 11, 12)`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "due_this_week")["count"] == 1`.
2. returns: `bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal("1.00")`.

### EXO-OQ44-03 — a partly paid confirmed invoice: the timeline counts what is still to pay
- **Rules:** `aggregate_financial_snapshot_actionable` R5 [BUG-2719]
- **Kind:** bug
- **Expect:** xfail BUG-2719
- **Fails today on:** Then 2 (today the full order total 300.00 is counted)

**Given**
1. VA = inv(W1, "300.00"), but confirmed, `payment_status "partial"`, `paid_amount Decimal("100.00")`.
2. OA = order "EXP-T-001", but `total_amount Decimal("300.00")`, `due_date date(2031, 11, 12)`, `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "due_this_week")["count"] == 1`.
2. returns: `bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal("200.00")`.

### EXO-OQ44-04 — the sample of a partly paid order shows what is still to pay
- **Rules:** `aggregate_financial_snapshot_actionable` R6 [BUG-2719]
- **Kind:** bug
- **Expect:** xfail BUG-2719
- **Fails today on:** Then 1 (today the sample shows the order total 300.00)

**Given**
1. VA = inv(W1, "300.00"), but confirmed, `payment_status "partial"`, `paid_amount Decimal("100.00")`.
2. OA = order "EXP-T-001", but `total_amount Decimal("300.00")`, `due_date date(2031, 11, 12)`, `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "due_this_week")["samples"] == [{"id": OA.id, "order_number": GN("EXP-T-001"), "total_value": Decimal("200.00"), "sublabel": "2031-11-12"}]`.

### EXO-OQ44-05 — a completed order with no invoice and no due date is in No due date
- **Rules:** `aggregate_financial_snapshot_actionable` R4, R5 [BUG-2719]
- **Kind:** bug
- **Expect:** xfail BUG-2719
- **Fails today on:** Then 1 (today the completed order is left out: count 1)

**Given**
1. OA = order "EXP-T-001", but `total_amount Decimal("40.00")`, completed.
2. OB = order "EXP-T-002", but `total_amount Decimal("2.00")`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "no_due_date")["count"] == 2`.
2. returns: `bucket(result, "due_timeline", "no_due_date")["total_value"] == Decimal("42.00")`.

### EXO-OQ44-06 — an open order whose invoice is paid is in no bucket
- **Rules:** `aggregate_financial_snapshot_actionable` R4 [BUG-2719]
- **Kind:** bug
- **Expect:** xfail BUG-2719
- **Fails today on:** Then 1 (today the open order counts at 300.00, count 1)

**Given**
1. VA = inv(W1, "300.00"), but confirmed, `payment_status "paid"`, `paid_amount Decimal("300.00")`.
2. OA = order "EXP-T-001", but `total_amount Decimal("300.00")`, `due_date date(2031, 11, 12)`, `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "due_this_week")["count"] == 0`.
2. returns: `bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal("0")`.

### EXO-OQ44-07 — nothing left to pay (0.00) with status partial is in no bucket
- **Rules:** `aggregate_financial_snapshot_actionable` R4 [BUG-2719]
- **Kind:** bug
- **Expect:** xfail BUG-2719
- **Fails today on:** Then 1 (today the open order counts at 300.00, count 1)

**Given**
1. VA = inv(W1, "300.00"), but confirmed, `payment_status "partial"`, `paid_amount Decimal("300.00")`.
2. OA = order "EXP-T-001", but `total_amount Decimal("300.00")`, `due_date date(2031, 11, 12)`, `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "due_this_week")["count"] == 0`.

### EXO-OQ44-08 — 0.01 left to pay counts as 0.01
- **Rules:** `aggregate_financial_snapshot_actionable` R4, R5 [BUG-2719] (HR-15)
- **Kind:** bug
- **Expect:** xfail BUG-2719
- **Fails today on:** Then 2 (today the order total 300.00 is counted)

**Given**
1. VA = inv(W1, "300.00"), but confirmed, `payment_status "partial"`, `paid_amount Decimal("299.99")`.
2. OA = order "EXP-T-001", but `total_amount Decimal("300.00")`, `due_date date(2031, 11, 12)`, `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "due_this_week")["count"] == 1`.
2. returns: `bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal("0.01")`.

### EXO-OQ44-09 — a locked partly paid invoice counts what is still to pay
- **Rules:** `aggregate_financial_snapshot_actionable` R5 [BUG-2719]
- **Kind:** bug
- **Expect:** xfail BUG-2719
- **Fails today on:** Then 2 (today the order total 300.00 is counted)

**Given**
1. VA = inv(W1, "300.00"), but locked, `payment_status "partial"`, `paid_amount Decimal("100.00")`.
2. OA = order "EXP-T-001", but `total_amount Decimal("300.00")`, `due_date date(2031, 11, 12)`, `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "due_this_week")["count"] == 1`.
2. returns: `bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal("200.00")`.

### EXO-OQ44-10 — a completed order whose invoice is voided counts at its full order total
- **Rules:** `aggregate_financial_snapshot_actionable` R4, R5 [BUG-2719]
- **Kind:** bug
- **Expect:** xfail BUG-2719
- **Fails today on:** Then 1 (today a completed order is never in the timeline, count 0)

**Given**
1. VA = inv(W1, "30.00"), but invvoid.
2. OA = order "EXP-T-001", but `total_amount Decimal("70.00")`, `due_date date(2031, 11, 12)`, completed, `invoice_id VA.id`.

**When**
- `result = dao.aggregate_financial_snapshot_actionable(db, workspace_id=W1.id)`.

**Then**
1. returns: `bucket(result, "due_timeline", "due_this_week")["count"] == 1`.
2. returns: `bucket(result, "due_timeline", "due_this_week")["total_value"] == Decimal("70.00")`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_next_number` R4 [BUG-749] race half | integration test (two transactions) | two concurrent creates never both get the same number; the loser retries or gets a clean error |
| FU-1 [BUG-2716] `expense_date` default from the local date | `ExpenseOrderManager.create_expense_order` R4 (manager spec) / model | an order created without `expense_date` gets the UTC date |
| FU-2 hub rules (BUG-2712, BUG-2714, BUG-2715, BUG-2717, BUG-2718, BUG-2719) | `ExpenseOrderManager` hub methods | the manager's pointers follow this DAO's rules |
| FU-3 `exclude_voided: false` hard-coded | web app (`expenseOrderHubApiParams.ts`) | frontend note: a "show voided" toggle, off by default (owner, OQ-42); the money figures leave voided orders out either way (BUG-2717) |
| BUG-750 / BUG-751 links not checked for workspace | `ExpenseOrderManager` create / update | another workspace's `account_id` / `order_template_id` / `invoice_id` is refused as not found (HR-16) |
| Inherited `create`, `update`, `get` | `tests/unit/dao/base.cases.md` | already covered |

## Spec gaps
None. The four gaps of revision 1 (account soft-delete columns, shared account names, the same number in another workspace, the OQ-43 / OQ-44 answers) are closed by the spec's Gap log G1–G4 (2026-11-11).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_expense_order_stage_key_expr` | R1 | EXO-SK-01, SK-02, OQ42-05 |
| `_category_label` | R1 | EXO-CL-01, CL-02, CL-03 |
| `_category_label` | R2 | EXO-CL-04, CL-05, CL-06, CL-07, CL-08 |
| `_category_label` | Errors (AttributeError) | EXO-CL-09 |
| `_due_date_bucket` | R1 | EXO-DB-01 |
| `_due_date_bucket` | R2 | EXO-DB-02, DB-03 |
| `_due_date_bucket` | R3 | EXO-DB-03, DB-04, DB-05 |
| `_due_date_bucket` | R4 | EXO-DB-05, DB-06 |
| `_due_date_bucket` | R5 | EXO-DB-07, DB-08, SA-05 |
| `_due_date_bucket` | R6 | EXO-DB-09 |
| `_due_window_dates` | R1 | EXO-DW-01, DW-07, SA-08 |
| `_due_window_dates` | R2 | EXO-DW-01, DW-02, DW-03, DW-06, DW-07 |
| `_due_window_dates` | R3 | EXO-DW-01, DW-04, DW-05, DW-06 |
| `_due_window_dates` | R4 | EXO-DW-01 |
| `_apply_expense_order_stage_filter` | R1 | EXO-HF-15, HF-16, HF-17, HF-18, HF-24 |
| `_apply_expense_order_stage_filter` | R2 | EXO-HF-19, HF-20 |
| `_apply_expense_order_stage_filter` | R3 | EXO-HF-21 |
| `_apply_expense_order_hub_filters` | R1 | EXO-HF-01, HF-02, HF-03, HF-40, HS-02, RC-06, SF-19 |
| `_apply_expense_order_hub_filters` | R2 | EXO-HF-04 … HF-09, CH-05, HS-08 |
| `_apply_expense_order_hub_filters` | R3 | EXO-HF-10, HF-11 |
| `_apply_expense_order_hub_filters` | R4 | EXO-HF-12 |
| `_apply_expense_order_hub_filters` | R5 | EXO-HF-13, HF-14 |
| `_apply_expense_order_hub_filters` | R6 | EXO-HF-15 … HF-17, HF-22 |
| `_apply_expense_order_hub_filters` | R7 | EXO-HF-25 … HF-28 |
| `_apply_expense_order_hub_filters` | R8 | EXO-HF-29, HF-30, HF-32, CH-05, RC-06 |
| `_apply_expense_order_hub_filters` | R9 | EXO-HF-23, HF-31, HF-32, CH-05, RC-06, HS-07 |
| `_apply_expense_order_hub_filters` | R10 | EXO-HF-33 … HF-39, HF-41, HF-48, HF-50, CH-04 |
| `_apply_expense_order_hub_filters` | R10 [BUG-745] | EXO-HF-42, HF-43, HF-44 |
| `_apply_expense_order_hub_filters` | R11 [BUG-2714] | EXO-HF-45, HF-46 |
| `_apply_expense_order_hub_filters` | R12 [BUG-2715] | EXO-HF-47 (HF-48 pass half) |
| `_apply_expense_order_hub_filters` | R13 | EXO-HF-49 |
| `get_by_workspace` | R1 | EXO-GW-01, GW-02, GW-03 |
| `get_by_workspace` | R2 | EXO-GW-04, GW-05, GW-06 |
| `get_by_workspace` | R3 | EXO-GW-07, GW-08 |
| `get_by_workspace` | R4 | EXO-GW-09, GW-10, GW-14 |
| `get_by_workspace` | R5 | EXO-GW-12, GW-13, GW-14 |
| `get_by_workspace` | R6 [BUG-2711] | EXO-GW-11 (pass half), GW-15, GW-16 |
| `get_by_workspace` | R7 | EXO-GW-17 |
| `get_by_workspace` | Side effects | EXO-GW-18 |
| `list_for_hub` | R1 | EXO-HF-*, HF-32, LH-05 |
| `list_for_hub` | R2 | EXO-LH-01 |
| `list_for_hub` | R3 | EXO-LH-02, LH-03, LH-04, LH-05 |
| `list_for_hub` | Errors, Side effects | EXO-HF-49, LH-06 |
| `count_for_hub` | R1 | EXO-CH-01 … CH-05 |
| `count_for_hub` | Errors | EXO-CH-06 |
| `list_recent_for_hub` | R1 | EXO-RC-04, RC-05, RC-06 |
| `list_recent_for_hub` | R2 [BUG-746] | EXO-RC-01, RC-07, RC-08 (pass halves RC-02, RC-03) |
| `list_recent_for_hub` | Side effects | EXO-RC-09 |
| `aggregate_hub_stats` | R1–R3 (non-voided) | EXO-HS-01, HS-02, HS-06, HS-07, HS-08 |
| `aggregate_hub_stats` | R1, R3 counts with voided orders (follow `exclude_voided`) | EXO-HS-11, OQ42-03 |
| `aggregate_hub_stats` | R1, R2 voided [BUG-2717] | EXO-OQ42-01, OQ42-02 |
| `aggregate_hub_stats` | R3a | EXO-OQ42-03 |
| `aggregate_hub_stats` | R4 | EXO-HS-03, HS-04, HS-05 |
| `aggregate_hub_stats` | Errors, Side effects | EXO-HS-09, HS-10 |
| `_filtered_orders_query` | R1 | EXO-SF-18, SF-19, SF-20, SF-21 |
| `aggregate_financial_snapshot_filtered` | R1 (non-voided) | EXO-SF-01, SF-16, SF-24 |
| `aggregate_financial_snapshot_filtered` | R1 voided [BUG-2717] | EXO-OQ42-04, OQ42-07 |
| `aggregate_financial_snapshot_filtered` | R2 [BUG-2712] | EXO-SF-01 (pass half), SF-06, SF-07 |
| `aggregate_financial_snapshot_filtered` | R3 | EXO-SF-03, SF-04, SF-05 |
| `aggregate_financial_snapshot_filtered` | R4 | EXO-SF-02 |
| `aggregate_financial_snapshot_filtered` | R5 (non-voided) | EXO-SF-02, SF-08, SF-09, SF-20, SF-24 |
| `aggregate_financial_snapshot_filtered` | R5 voided [BUG-2717] | EXO-OQ42-05 |
| `aggregate_financial_snapshot_filtered` | R6, R7 | EXO-SF-10, SF-18, SF-24, SF-25 |
| `aggregate_financial_snapshot_filtered` | R8 | EXO-SF-10, SF-11, SF-25 |
| `aggregate_financial_snapshot_filtered` | R8 [BUG-747] | EXO-SF-12, SF-13, SF-23 |
| `aggregate_financial_snapshot_filtered` | R6a [BUG-2717] | EXO-OQ42-06 |
| `aggregate_financial_snapshot_filtered` | R9 [BUG-2714] | EXO-SF-14, SF-15 (SF-16 pass half) |
| `aggregate_financial_snapshot_filtered` | R10 | EXO-SF-17 |
| `aggregate_financial_snapshot_filtered` | Errors, Side effects | EXO-SF-21, SF-22 |
| `aggregate_financial_snapshot_actionable` | R1 | EXO-SA-01, SA-02 |
| `aggregate_financial_snapshot_actionable` | R2 | EXO-SA-02, SA-05, SA-08 |
| `aggregate_financial_snapshot_actionable` | R3 | EXO-SA-06 |
| `aggregate_financial_snapshot_actionable` | R4 (open orders; voided left out) | EXO-SA-02, SA-11, SA-12, OQ44-02 |
| `aggregate_financial_snapshot_actionable` | R4 [BUG-2719] | EXO-OQ44-01, OQ44-05, OQ44-06, OQ44-07, OQ44-08, OQ44-10 |
| `aggregate_financial_snapshot_actionable` | R5 [BUG-2719] | EXO-OQ44-01, OQ44-03, OQ44-05, OQ44-08, OQ44-09, OQ44-10 |
| `aggregate_financial_snapshot_actionable` | R6 [BUG-2719] (which orders, which amount) | EXO-OQ44-04 |
| `aggregate_financial_snapshot_actionable` | R6 sample order | EXO-SA-03, SA-04, SA-13 |
| `aggregate_financial_snapshot_actionable` | R5 exact sums on no-, draft- and voided-invoice orders | EXO-SA-02, SA-07, SA-12, SA-13 |
| `aggregate_financial_snapshot_actionable` | R7 | EXO-SA-01, UP-01 |
| `aggregate_financial_snapshot_actionable` | R8, R9 [BUG-2718] | EXO-OQ43-01, OQ43-02, OQ43-03, OQ43-05, OQ43-06 |
| `aggregate_financial_snapshot_actionable` | R8, R9 (open orders, confirmed / locked / paid / voided invoices; hold before and after BUG-2718) | EXO-UP-01 … UP-05, UP-11 … UP-14, OQ43-04 |
| `aggregate_financial_snapshot_actionable` | R10 [BUG-2714] | EXO-UP-08, UP-09 |
| `aggregate_financial_snapshot_actionable` | R11 [BUG-748] | EXO-UP-05, UP-13, UP-14 (pass halves), UP-06, UP-07 |
| `aggregate_financial_snapshot_actionable` | R12 | EXO-UP-10 |
| `aggregate_financial_snapshot_actionable` | no filters, Side effects | EXO-SA-09, SA-10 |
| `ExpenseOrderDAO.get_by_id_and_workspace` | R1 | EXO-GI-01 … GI-05 |
| `ExpenseOrderDAO.get_by_id_and_workspace` | R2 | EXO-GI-06 |
| `ExpenseOrderDAO.get_by_id_and_workspace` | Side effects | EXO-GI-07 |
| `get_next_number` | R1 | EXO-NX-01, NX-20 |
| `get_next_number` | R1 [BUG-2710] | EXO-NX-21, NX-22 |
| `get_next_number` | R2 | EXO-NX-01, NX-10 … NX-18, NX-20 |
| `get_next_number` | R3 | EXO-NX-02 … NX-06, NX-08, NX-19 |
| `get_next_number` | R3 [BUG-749] | EXO-NX-07, NX-09 |
| `get_next_number` | R4 [BUG-749] | EXO-NX-23, NX-24 (race half deferred) |
| `get_next_number` | R4a [BUG-749] | EXO-NX-26, NX-27 |
| `get_next_number` | R5 | EXO-NX-25 |
| `ExpenseOrderItemDAO.get_by_order` | R1 | EXO-GO-01 … GO-06, GO-09 |
| `ExpenseOrderItemDAO.get_by_order` | R2 [BUG-2713] | EXO-GO-01 (pass half), GO-07, GO-08 |
| `ExpenseOrderItemDAO.get_by_order` | Side effects | EXO-GO-10 |
| `ExpenseOrderItemDAO.get_by_id_and_workspace` | R1 | EXO-II-01 … II-04, II-06 |
| `ExpenseOrderItemDAO.get_by_id_and_workspace` | R2 | EXO-II-05 |
