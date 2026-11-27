# Test cases — `app/dao/account_invoice.py`

> **Spec:** `tests/unit/dao/account_invoice.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-11; OQ-41 answered by the owner → BUG-2692; both revision-1 gaps closed by the spec's Gap log).
> **Revision:** 2 (2026-11-14) — spec apply-review + fill-gaps of 2026-11-11. OQ-41 → BUG-2692 (`summarize_invoices` R5: one 7-tuple, a payable and a receivable triple, never summed across types): the section **Pending owner — OQ-41** becomes **`summarize_invoices` R5 — BUG-2692**; OQ41-01, 02, 04 become strict xfail cards for the split, OQ41-03 stays a pass (count + payable triple hold before and after); new OQ41-05 … 07 (xfail) and SI-14, SI-15 (pass: the count, which holds before and after). Every other `SI` card now checks `result[:4]` or single positions instead of the whole 4-tuple, so it survives the new shape. G1: "today" is a keyword `today=` — FQ-19, AH-03, HS-08 now pass `today=TD` (fail today in the call), new day-boundary cards FQ-44, AH-33, AH-34, HS-14 (strict xfail BUG-635); the Deferred row for the DAO day boundary is replaced by the manager's half. G2: **voided** also resets `paid_amount 0.00` and `payment_status "unpaid"`. No ID retired.
> **Revision:** 3 (2026-11-14) — executor notes DISCREPANCY-1 … 3 (card typos, a backslash lost): AIV-ES-01 now expects `a\%b\_c\\d` (spec `_escape_ilike` R1's own example), AIV-ES-02 `\\\%\\\_` (R1: every `\` is doubled first, then `%` / `_` are escaped), AIV-ST-03 `%Ab\_c\\D%` (`_invoice_number_search_ilike_term` R2 applies R1). No card added or retired; counts unchanged.
> **Revision:** 4 (2026-11-14) — `account_invoice.verify.md` findings 1–3 (all `case-missing`). F1 (mutant #57): new AIV-PF-19, `list_invoices_page_filtered` without `open_balance_only` lists and counts paid, voided and draft invoices. F2 (mutants #118, #135): new AIV-AH-35, the receivable twin of AH-18 (0.00 left out, 0.01 kept). F3 (mutant #128): new AIV-UP-26, a 0.01 payment on an unpaid invoice gives `partial`. No ID retired.
> **Counts:** 219 cases · 177 expected-to-pass · 42 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `_escape_ilike` 4 · `_invoice_number_search_ilike_term` 5 · `_outstanding_amount_expr` 3 · `_reshape_accounts_hub_row` 4 · `_order_number_search_conditions` 19 (2 bug) · `_build_filtered_query` 44 (11 bug) · `list_invoices` 8 · `list_invoices_page` 9 (2 bug) · `list_invoices_page_filtered` 19 (2 bug) · `list_accounts_hub_page` with `_open_balance_subquery` 35 (10 bug) · `summarize_open_hub_type` 14 (5 bug) · `count_accounts_with_any_open_balance` 7 (2 bug) · `summarize_invoices` 15 (2 bug) + R5 split 7 (6 bug) · `update_paid_amount` 26.
- **Expected-to-fail by bug (all strict):** BUG-2690 9 (FQ-06, FQ-07, FQ-08, LP-09, PF-17, HS-10, HS-11, CA-07, SI-09) · BUG-622 8 (FQ-36, FQ-37, FQ-40 … FQ-42, AH-20 … AH-22) · BUG-634 6 (LP-03, PF-15, AH-02, HS-07, CA-05, SI-07) · BUG-635 7 (FQ-19, FQ-44, AH-03, AH-33, AH-34, HS-08, HS-14) · BUG-2692 6 (OQ41-01, 02, 04 … 07) · BUG-2691 2 (ON-14, ON-15) · BUG-623 2 (AH-25 data, AH-26 SQL alarm) · BUG-637 1 (FQ-33) · BUG-636 1 (AH-05).
- **Depth:** full (skill step 1a). This DAO holds the money views: open balances, hub KPIs, account totals, and the one money write, `update_paid_amount`. Every amount is an exact `Decimal`.
- **OQ-41 answered (BUG-2692):** R5 is covered only by AIV-OQ41-01 … 07 (IDs kept from the pending section). The new shape is `(count, payable triple, receivable triple)`. With `invoice_type="payable"` positions 0–3 are the count and the payable triple both today and after the fix, so every other `SI` card passes `invoice_type="payable"`, holds payable rows only and checks `result[:4]` or one position — none checks the tuple length. OQ41-03 (pass) pins that; OQ41-05 pins the zero receivable triple (xfail). SI-14 / SI-15 keep the count, the part of R5 that holds today, in pass cards.
- **Notable design choices:**
  - The private helpers `_order_number_search_conditions` and `_build_filtered_query` are tested through `list_invoices`, the public caller with every filter (cards `ON-` and `FQ-`). The paged list, the KPIs and the summary each get their own cards for the rules they add, plus one HR-16 card and one BUG-634 card each.
  - HR-16 (BUG-2690): a W1 invoice is put on a W2 account, and in a second card on a W0 account. That is the one cross-workspace shape the spec's R2a names (the database checks only that the account exists). No card builds an order linked across workspaces. So `_order_number_search_conditions` R2, the workspace scope of the order sub-selects, is pinned on its visible side (ON-17: other workspaces' orders sit on their own invoices) and by a statement card (ON-19: each of the four sub-selects names its `workspace_id`). A missing filter would otherwise show only through an invalid cross-workspace link.
  - HR-15: the DAO rounds nothing. The cards store `33.335` / `0.005` / `2.125` / `-1.005` (values where half up and half to even differ) and the control `2.124`, then check the sums and the stored paid amount. `update_paid_amount` R6 (status decided on the unrounded sum) is pinned with `999.995`.
  - Overdue (BUG-635): after the fix the DAO takes `today=` (spec G1) and reads no clock. Every overdue card passes `today=TD` (15 June 2031, not the current year, so a `CURRENT_DATE` implementation fails) and so fails today in the call. FQ-44, AH-33, AH-34, HS-14 put invoices due TD − 1, TD, TD + 1 and undated on both sides of the boundary; FQ-19, AH-03, HS-08 keep PASTDUE / FARDUE. AH-04 (pass) keeps "far ahead or undated is never overdue" without `today`.
  - BUG-623 (hub order): the test database's collation already sorts almost case-insensitively. AH-25 therefore uses `Bravo` / `bravo` / `BRAVO`, built in that id order. Both byte order and lower-case-first order disagree with the intended "lower(name), then id". AH-26 is the strict SQL alarm.
  - Hub cards first make the standing account AC1 inactive (**hubclean**). AC1 has no invoices, so it is out of the hub both today and after BUG-636.
  - Only the bulk cards with 101 or 1001 rows (LI-02, LI-04, PF-10) carry `Author: claude`. No card compares an order that rests on physical row order: every query here ends its `ORDER BY` in `id`, so there are no non-strict cards. Race simulations: none.
- **Needs a decision:** None that blocks. Revision-1 gaps 1 and 2 are closed by the spec's Gap log; one new non-blocking note (Spec gaps 3: is `today` required?).

## Conventions for this module

**IDs.** `AIV` = `app/dao/account_invoice.py`. `ES` _escape_ilike · `ST` _invoice_number_search_ilike_term · `OE` _outstanding_amount_expr · `ON` _order_number_search_conditions (through `list_invoices`) · `FQ` _build_filtered_query (through `list_invoices`) · `LI` list_invoices · `LP` list_invoices_page · `PF` list_invoices_page_filtered · `AH` list_accounts_hub_page with `_open_balance_subquery` · `RH` _reshape_accounts_hub_row · `HS` summarize_open_hub_type · `CA` count_accounts_with_any_open_balance · `SI` summarize_invoices · `UP` update_paid_amount · `OQ41` `summarize_invoices` R5 split cards (BUG-2692; the ID kept from the former pending section).

**Actors and fixed values.**
- `dao` = `account_invoice_dao` (`from app.dao.account_invoice import account_invoice_dao`). `db` = the test's real session, always the first argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- `AccountInvoice` = `app.models.account_invoice.AccountInvoice`, `Account` = `app.models.account.Account`, `PurchaseOrder` / `ExpenseOrder` / `SalesOrder` / `WorkOrder` = `app.models.<snake_case>`. `select`, `text`, `func` = sqlalchemy's. `Decimal`, `date`, `datetime`, `timedelta`, `patch`, `pytest` = the usual ones.
- MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`, made once per test. XID(k) = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`; "`id XID(k)`" passes `id=XID(k)`. GN(n) = `f"{n}-{os.getpid()}"` (sales and expense numbers are unique across all workspaces today, so those builders store GN(n)). AR(n) = `"".join(chr(0x660 + int(c)) for c in str(n))` (n in Arabic-Indic digits).
- D1 … D5 = `date(2026, 3, 1)` … `date(2026, 3, 5)`. PASTDUE = `date(2020, 1, 1)`, FARDUE = `date(2099, 12, 31)`. T1 = `datetime(2026, 3, 6, 9, 0)` (naive).
- TD = `date(2031, 6, 15)` (the `today=` passed to overdue cards). TDM1 = `TD - timedelta(days=1)`, TDP1 = `TD + timedelta(days=1)`.

**Externals.** None. No clock is patched: the DAO reads no clock; overdue cards pass `today=TD`.

**Standing rows** (every test, this order, each flushed, no Given line):
1. W0, W1, W2 = `make_workspace(db)` three times (`W0.id < W1.id < W2.id`). U1, U2, U3 = `make_profile(db)` three times.
2. AC0, AC1, AC2 = `Account(workspace_id=Wk.id, name=f"Acme {TAG}", is_active=True, is_deleted=False)` for W0, W1, W2.

**Given rows.** Inserted directly (never through `dao`), flushed one at a time in the order written, so ids rise in that order. After "but", a line lists every column that differs. A line written as code is a step to run exactly as written.
- **acct(name)** = `Account(workspace_id=W1.id, name=name, is_active=True, is_deleted=False)`. **inactive** = `is_active False`. **closed** = `is_deleted True`, `is_active False`, `deleted_at T1`, `deleted_by U1.id`. **half-closed** = `is_deleted True` only.
- **inv** = `AccountInvoice(workspace_id=W1.id, account_id=AC1.id, invoice_type="payable", invoice_status="confirmed", payment_status="unpaid", invoice_amount=Decimal("100.00"), paid_amount=Decimal("0.00"), invoice_date=D2, created_by=U1.id)`. "inv of W0" uses W0 and AC0; "of W2" uses W2 and AC2. **partial(p)** = `payment_status "partial"`, `paid_amount p`. **paid** = `payment_status "paid"`, `paid_amount` equal to its `invoice_amount`. **draft** = `invoice_status "draft"`. **voided** = `invoice_status "voided"`, `void_note "Wrong amount"`, `paid_amount Decimal("0.00")`, `payment_status "unpaid"`, `updated_by U1.id`, `updated_at T1` (what a real void writes; `allow_payments` untouched).
- **invs(n)** = `for i in range(n):` add inv, but `invoice_number f"BULK-{i:04d}"`, then one flush after the loop (ids rise with i). **accts(n)** = `for i in range(n):` add acct(f"Bulk {i:04d} {TAG}"), one flush.
- **unchecked: …** = `db.execute(text("SET LOCAL session_replication_role = replica"))`, then the rows named, then `db.execute(text("SET LOCAL session_replication_role = origin"))`.
- Orders (workspace W1 unless "of W0" / "of W2"; `invoice_id` only when given):
  - **po(n)** = unchecked: `PurchaseOrder(workspace_id=W1.id, po_number=n, destination_type="storage", destination_id=MISSING, subtotal=0, total_amount=0, current_status_id=MISSING, created_by=U1.id)`.
  - **eo(n)** = unchecked: `ExpenseOrder(workspace_id=W1.id, expense_number=GN(n), expense_category="other", expense_date=D1, created_by=U1.id)`.
  - **so(n)** = unchecked: `SalesOrder(workspace_id=W1.id, sales_order_number=GN(n), account_id=AC1.id, factory_id=MISSING, order_date=D1, current_status_id=MISSING, created_by=U1.id)`.
  - **wo(n)** = unchecked: `WorkOrder(workspace_id=W1.id, work_order_number=n, work_order_type_id=MISSING, title="Oil change", factory_id=MISSING, created_by=U1.id)`.
  - **voided order** (po / eo) = `voided True`, `void_note "Cancelled"`, `voided_at T1`, `voided_by U1.id`. **deleted wo** = `is_active False`, `is_deleted True`, `deleted_at T1`, `deleted_by U1.id`.
- **hubclean** = `AC1.is_active = False`, then `db.flush()` (AC1 has no invoices, so it is in no hub result).

**Named checks.**
- **ids(x)** = `[r.id for r in x]` (order is part of the check); **idset(x)** = `{r.id for r in x}`. For `(items, total)` results: `items = result[0]`, `total = result[1]`.
- Hub: **hids(result)** = `[row[0].id for row in result[0]]`; **pay(result, A)** / **rec(result, A)** = `row[1]` / `row[2]` of the row whose `row[0].id == A.id`.
- Money is compared as `Decimal` with `==` (`== Decimal("0.30")`), never as float or string.
- `summarize_invoices` results: `result[0]` = count; `result[1:4]` = invoiced, paid, outstanding (today: of the whole selection; after BUG-2692: of the payables); `result[4:7]` = the receivable triple (after BUG-2692 only). `result[:4]` is a tuple slice.
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. **unchanged(X)** = after re-read, every column of X equals its value before the call.
- **nothing written** = the number of `account_invoices` rows (all workspaces) equals its value before the call, and `not db.dirty`, `not db.new`, `not db.deleted` right after the call.
- `pending:` / `session:` lines check the session directly after the call, before anything expires it.
- `raises: TypeError` = `with pytest.raises(TypeError):` around the call.
- **commit spy** = `sp = db.begin_nested()` directly before the call, `with patch.object(db, "commit", wraps=db.commit) as cm:` around it; "inside the savepoint" lines first, then `sp.rollback()`, then the rest.
- **Statement recorder** = the SQL sent during the When is recorded (`before_cursor_execute`). `sql` = the main `SELECT` (the card names its table); `order_part` = text of `sql` after its last top-level `ORDER BY`, before any `LIMIT` / `OFFSET` (`""` if none); `written` = every recorded `INSERT`, `UPDATE`, `DELETE`.
- **No-lock check** = `"FOR UPDATE" not in sql` (never `lock_part == ""`).
- **Clear the session before a one-query check**: such a card ends its Given with `db.expunge_all()`; ids in Then come from objects built before it.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. Write the call and the checks exactly as shown; never weaken an assertion.

**Race simulations.** None.

## `AccountInvoiceDAO._escape_ilike`

### AIV-ES-01 — backslash, percent and underscore are escaped, backslash first
- **Rules:** `_escape_ilike` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = dao._escape_ilike(r"a%b_c\d")`.

**Then**
1. returns: `result == r"a\%b\_c\\d"`.

### AIV-ES-02 — an escaped percent in the input gets its backslash doubled, not reused
- **Rules:** `_escape_ilike` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = dao._escape_ilike(r"\%\_")`.

**Then**
1. returns: `result == r"\\\%\\\_"`.

### AIV-ES-03 — case, inner and outer whitespace are kept
- **Rules:** `_escape_ilike` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = dao._escape_ilike(" Ab  Cd ")`.

**Then**
1. returns: `result == " Ab  Cd "`.

### AIV-ES-04 — the empty string stays empty
- **Rules:** `_escape_ilike` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = dao._escape_ilike("")`.

**Then**
1. returns: `result == ""`.

## `AccountInvoiceDAO._invoice_number_search_ilike_term`

### AIV-ST-01 — a padded term is trimmed and wrapped in percent signs, case kept
- **Rules:** `_invoice_number_search_ilike_term` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = dao._invoice_number_search_ilike_term(" PO-1 ")`.

**Then**
1. returns: `result == "%PO-1%"`.

### AIV-ST-02 — a percent sign in the term is escaped inside the wrapper
- **Rules:** `_invoice_number_search_ilike_term` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = dao._invoice_number_search_ilike_term("50%")`.

**Then**
1. returns: `result == r"%50\%%"`.

### AIV-ST-03 — underscore and backslash are escaped too
- **Rules:** `_invoice_number_search_ilike_term` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = dao._invoice_number_search_ilike_term(r"Ab_c\D")`.

**Then**
1. returns: `result == r"%Ab\_c\\D%"`.

### AIV-ST-04 — whitespace only gives the empty pattern, not %%
- **Rules:** `_invoice_number_search_ilike_term` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = dao._invoice_number_search_ilike_term("  \t ")`.

**Then**
1. returns: `result == ""`.

### AIV-ST-05 — the empty string gives the empty pattern
- **Rules:** `_invoice_number_search_ilike_term` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = dao._invoice_number_search_ilike_term("")`.

**Then**
1. returns: `result == ""`.

## `AccountInvoiceDAO._outstanding_amount_expr`

### AIV-OE-01 — amount minus paid, exact
- **Rules:** `_outstanding_amount_expr` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. N = inv, but partial(`Decimal("30.05")`).

**When**
- `result = db.scalar(select(dao._outstanding_amount_expr()).where(AccountInvoice.id == N.id))`.

**Then**
1. returns: `result == Decimal("69.95")`.

### AIV-OE-02 — a voided invoice is not treated as zero
- **Rules:** `_outstanding_amount_expr` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv, but voided.

**When**
- `result = db.scalar(select(dao._outstanding_amount_expr()).where(AccountInvoice.id == N.id))`.

**Then**
1. returns: `result == Decimal("100.00")`.

### AIV-OE-03 — an overpaid invoice gives a negative value
- **Rules:** `_outstanding_amount_expr` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv, but `invoice_amount Decimal("10.00")`, `paid_amount Decimal("15.00")`, `payment_status "paid"`.

**When**
- `result = db.scalar(select(dao._outstanding_amount_expr()).where(AccountInvoice.id == N.id))`.

**Then**
1. returns: `result == Decimal("-5.00")`.

## `AccountInvoiceDAO._reshape_accounts_hub_row`

### AIV-RH-01 — every position lands in its own attribute
- **Rules:** `_reshape_accounts_hub_row` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `row = (AC1, AC1.id, Decimal("12.50"), 2, 1, AC1.id, Decimal("7.25"), 3, 0)`.

**When**
- `result = dao._reshape_accounts_hub_row(row)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `result[0] is AC1`.
3. returns: `result[1].outstanding_total == Decimal("12.50")`, `result[1].open_count == 2`, `result[1].has_overdue is True`.
4. returns: `result[2].outstanding_total == Decimal("7.25")`, `result[2].open_count == 3`, `result[2].has_overdue is False`.
5. returns: `isinstance(result[1].outstanding_total, Decimal)`.

### AIV-RH-02 — no payable sub-row gives 0, 0, False on the payable side only
- **Rules:** `_reshape_accounts_hub_row` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `row = (AC1, None, None, None, None, AC1.id, Decimal("7.25"), 3, 1)`.

**When**
- `result = dao._reshape_accounts_hub_row(row)`.

**Then**
1. returns: `result[1].outstanding_total == 0`, `result[1].open_count == 0`, `result[1].has_overdue is False`.
2. returns: `result[2].outstanding_total == Decimal("7.25")`, `result[2].open_count == 3`, `result[2].has_overdue is True`.

### AIV-RH-03 — no receivable sub-row gives 0, 0, False on the receivable side only
- **Rules:** `_reshape_accounts_hub_row` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `row = (AC1, AC1.id, Decimal("12.50"), 2, 0, None, None, None, None)`.

**When**
- `result = dao._reshape_accounts_hub_row(row)`.

**Then**
1. returns: `result[1].outstanding_total == Decimal("12.50")`, `result[1].open_count == 2`, `result[1].has_overdue is False`.
2. returns: `result[2].outstanding_total == 0`, `result[2].open_count == 0`, `result[2].has_overdue is False`.

### AIV-RH-04 — a zero outstanding total is passed through, not replaced
- **Rules:** `_reshape_accounts_hub_row` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `row = (AC1, AC1.id, Decimal("0.00"), 1, 0, AC1.id, Decimal("-5.00"), 1, 0)`.

**When**
- `result = dao._reshape_accounts_hub_row(row)`.

**Then**
1. returns: `result[1].outstanding_total == Decimal("0.00")`, `result[1].open_count == 1`.
2. returns: `result[2].outstanding_total == Decimal("-5.00")`.

## `AccountInvoiceDAO._order_number_search_conditions` (through `list_invoices`)

### AIV-ON-01 — a purchase order's number finds its invoice through the forward link
- **Rules:** `_order_number_search_conditions` R1; `_build_filtered_query` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = po("PO-SRCH-77").
2. N1 = inv.
3. N2 = inv, but `order_type "purchase_order"`, `order_id P.id`.
4. N3 = inv.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="srch-7")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-ON-02 — an expense order's number finds its invoice through the forward link
- **Rules:** `_order_number_search_conditions` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E = eo("EX-SRCH-77").
2. N1 = inv.
3. N2 = inv, but `order_type "expense_order"`, `order_id E.id`.
4. N3 = inv.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="srch-7")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-ON-03 — a sales order's number finds its invoice through the forward link
- **Rules:** `_order_number_search_conditions` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = so("SO-SRCH-77").
2. N1 = inv.
3. N2 = inv, but `invoice_type "receivable"`, `order_type "sales_order"`, `order_id S.id`.
4. N3 = inv.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="srch-7")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-ON-04 — a work order's number finds its invoice through the forward link
- **Rules:** `_order_number_search_conditions` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. O = wo("WO-SRCH-77").
2. N1 = inv.
3. N2 = inv, but `order_type "work_order"`, `order_id O.id`.
4. N3 = inv.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="srch-7")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-ON-05 — a purchase order pointing at the invoice finds it (reverse link)
- **Rules:** `_order_number_search_conditions` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv.
3. N3 = inv.
4. P = po("PO-SRCH-77"), but `invoice_id N2.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="SRCH-77")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-ON-06 — an expense order pointing at the invoice finds it (reverse link)
- **Rules:** `_order_number_search_conditions` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv.
3. N3 = inv.
4. E = eo("EX-SRCH-77"), but `invoice_id N2.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="SRCH-77")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-ON-07 — a sales order pointing at the invoice finds it (reverse link)
- **Rules:** `_order_number_search_conditions` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv, but `invoice_type "receivable"`.
3. N3 = inv.
4. S = so("SO-SRCH-77"), but `invoice_id N2.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="SRCH-77")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-ON-08 — a work order pointing at the invoice finds it (reverse link)
- **Rules:** `_order_number_search_conditions` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv.
3. N3 = inv.
4. O = wo("WO-SRCH-77"), but `invoice_id N2.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="SRCH-77")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-ON-09 — a matching order with no invoice and no forward link finds nothing
- **Rules:** `_order_number_search_conditions` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv.
3. P = po("PO-SRCH-77").

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="SRCH-77")`.

**Then**
1. returns: `result == []`.

### AIV-ON-10 — a forward link whose order_type has other letter case does not match
- **Rules:** `_order_number_search_conditions` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = po("PO-SRCH-77").
2. N1 = inv, but `order_type "Purchase_Order"`, `order_id P.id`.
3. N2 = inv, but `order_type "purchase_order"`, `order_id P.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="SRCH-77")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-ON-11 — a forward link of another kind with the same order id does not match
- **Rules:** `_order_number_search_conditions` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = po("PO-SRCH-77"), but `id XID(1)`.
2. N1 = inv, but `order_type "expense_order"`, `order_id XID(1)`.
3. N2 = inv, but `order_type "work_order"`, `order_id XID(1)`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="SRCH-77")`.

**Then**
1. returns: `result == []`.

### AIV-ON-12 — a voided purchase order's number still finds its invoice
- **Rules:** `_order_number_search_conditions` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = po("PO-SRCH-77"), but voided order.
2. N1 = inv.
3. N2 = inv, but `order_type "purchase_order"`, `order_id P.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="SRCH-77")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-ON-13 — a voided expense order's number still finds its invoice
- **Rules:** `_order_number_search_conditions` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv.
3. E = eo("EX-SRCH-77"), but voided order, `invoice_id N2.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="SRCH-77")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-ON-14 — a deleted work order's number does not find its invoice (forward link)
- **Rules:** `_order_number_search_conditions` R4 [BUG-2691]
- **Kind:** bug
- **Expect:** xfail BUG-2691
- **Fails today on:** Then 1 (the deleted work order's number still matches)

**Given**
1. O = wo("WO-DEL-77"), but deleted wo.
2. N1 = inv, but `order_type "work_order"`, `order_id O.id`.
3. N2 = inv.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="wo-del-7")`.

**Then**
1. returns: `result == []`.

### AIV-ON-15 — a deleted work order's number does not find its invoice (reverse link)
- **Rules:** `_order_number_search_conditions` R4 [BUG-2691]
- **Kind:** bug
- **Expect:** xfail BUG-2691
- **Fails today on:** Then 1 (the deleted work order's number still matches)

**Given**
1. N1 = inv.
2. N2 = inv.
3. O = wo("WO-DEL-77"), but deleted wo, `invoice_id N1.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="wo-del-7")`.

**Then**
1. returns: `result == []`.

### AIV-ON-16 — an invoice linked to a deleted work order is still found by its own number
- **Rules:** `_order_number_search_conditions` R4; `_build_filtered_query` R9
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. O = wo("WO-DEL-77"), but deleted wo.
2. N1 = inv, but `invoice_number "INV-KEEP-5"`, `order_type "work_order"`, `order_id O.id`.
3. N2 = inv.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="keep-5")`.

**Then**
1. returns: `ids(result) == [N1.id]`.

### AIV-ON-17 — orders of W0 and W2 with the number, on their own invoices, add nothing to W1
- **Rules:** `_order_number_search_conditions` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = inv of W0.
2. P0 = po("PO-SRCH-77") of W0, but `invoice_id X0.id`.
3. N1 = inv.
4. P2 = po("PO-SRCH-77") of W2.
5. X2 = inv of W2, but `order_type "purchase_order"`, `order_id P2.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="SRCH-77")`.

**Then**
1. returns: `result == []`.

### AIV-ON-18 — an underscore in an order-number search is literal
- **Rules:** `_order_number_search_conditions` R1; `_build_filtered_query` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv.
3. P1 = po("PO_77"), but `invoice_id N1.id`.
4. P2 = po("POX77"), but `invoice_id N2.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="PO_7")`.

**Then**
1. returns: `ids(result) == [N1.id]`.

### AIV-ON-19 — every order sub-select of the search is scoped to the workspace
- **Rules:** `_order_number_search_conditions` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. N1 = inv.
2. `db.expunge_all()`.

**When**
- Statement recorder on: `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="SRCH")`; `sql` = the SELECT from `account_invoices`.

**Then**
1. returns: `result == []`.
2. returns: `"purchase_orders.workspace_id" in sql`.
3. returns: `"expense_orders.workspace_id" in sql`.
4. returns: `"sales_orders.workspace_id" in sql`.
5. returns: `"work_orders.workspace_id" in sql`.
6. returns: `"FOR UPDATE" not in sql`.

## `AccountInvoiceDAO._build_filtered_query` (through `list_invoices`)

### AIV-FQ-01 — only W1's invoices, with invoices of W0 and W2 on both sides
- **Rules:** `_build_filtered_query` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = inv of W0.
2. N1 = inv.
3. N2 = inv.
4. X2 = inv of W2.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {N1.id, N2.id}`.

### AIV-FQ-02 — asked for W2, only W2's invoice, though W0 and W1 come earlier
- **Rules:** `_build_filtered_query` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = inv of W0.
2. N1 = inv.
3. X2 = inv of W2.

**When**
- `result = dao.list_invoices(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X2.id]`.

### AIV-FQ-03 — asked for W0, only W0's invoice, though W1 and W2 come later
- **Rules:** `_build_filtered_query` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = inv of W0.
2. N1 = inv.
3. X2 = inv of W2.

**When**
- `result = dao.list_invoices(db, workspace_id=W0.id)`.

**Then**
1. returns: `ids(result) == [X0.id]`.

### AIV-FQ-04 — an invoice of a closed account is left out, one of an inactive account is kept
- **Rules:** `_build_filtered_query` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AX = acct(f"Gone {TAG}"), but closed.
2. AI = acct(f"Idle {TAG}"), but inactive.
3. N1 = inv.
4. N2 = inv, but `account_id AX.id`.
5. N3 = inv, but `account_id AI.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {N1.id, N3.id}`.

### AIV-FQ-05 — an invoice of a deleted but still active account is left out
- **Rules:** `_build_filtered_query` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AX = acct(f"Half {TAG}"), but half-closed.
2. N1 = inv.
3. N2 = inv, but `account_id AX.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {N1.id}`.

### AIV-FQ-06 — a W1 invoice on W2's account is not listed
- **Rules:** `_build_filtered_query` R2a [BUG-2690]
- **Kind:** bug
- **Expect:** xfail BUG-2690
- **Fails today on:** Then 2 (the invoice on the foreign account is listed)

**Given**
1. N1 = inv.
2. X = inv, but `account_id AC2.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id)`.

**Then**
1. returns: `N1.id in idset(result)`.
2. returns: `idset(result) == {N1.id}`.

### AIV-FQ-07 — a W1 invoice on W0's account is not listed
- **Rules:** `_build_filtered_query` R2a [BUG-2690]
- **Kind:** bug
- **Expect:** xfail BUG-2690
- **Fails today on:** Then 2 (the invoice on the foreign account is listed)

**Given**
1. N1 = inv.
2. X = inv, but `account_id AC0.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id)`.

**Then**
1. returns: `N1.id in idset(result)`.
2. returns: `idset(result) == {N1.id}`.

### AIV-FQ-08 — a foreign account's name does not find a W1 invoice placed on it
- **Rules:** `_build_filtered_query` R2a, R11 [BUG-2690]
- **Kind:** bug
- **Expect:** xfail BUG-2690
- **Fails today on:** Then 1 (the name of W2's account matches)

**Given**
1. AZ = `Account(workspace_id=W2.id, name=f"Zulu {TAG}", is_active=True, is_deleted=False)`.
2. N1 = inv.
3. X = inv, but `account_id AZ.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, account_name_search="zulu")`.

**Then**
1. returns: `result == []`.

### AIV-FQ-09 — draft, confirmed and voided invoices are all listed with no filter
- **Rules:** `_build_filtered_query` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv, but draft.
2. N2 = inv.
3. N3 = inv, but voided.
4. N4 = inv, but paid.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {N1.id, N2.id, N3.id, N4.id}`.

### AIV-FQ-10 — account_id keeps one account, with accounts of lower and higher id
- **Rules:** `_build_filtered_query` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. AL = acct(f"Lima {TAG}").
2. AM = acct(f"Mike {TAG}").
3. AN = acct(f"Nova {TAG}").
4. N1 = inv, but `account_id AL.id`.
5. N2 = inv, but `account_id AM.id`.
6. N3 = inv, but `account_id AN.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, account_id=AM.id)`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-FQ-11 — account_id 0 is a filter, not "no filter"
- **Rules:** `_build_filtered_query` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, account_id=0)`.

**Then**
1. returns: `result == []`.

### AIV-FQ-12 — invoice_type is exact equality
- **Rules:** `_build_filtered_query` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv, but `invoice_type "receivable"`.
3. N3 = inv.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_type="receivable")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-FQ-13 — invoice_type is case-sensitive
- **Rules:** `_build_filtered_query` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv, but `invoice_type "receivable"`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_type="Payable")`.

**Then**
1. returns: `result == []`.

### AIV-FQ-14 — an unknown invoice_type matches nothing
- **Rules:** `_build_filtered_query` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv, but `invoice_type "receivable"`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_type="bogus")`.

**Then**
1. returns: `result == []`.

### AIV-FQ-15 — empty strings for type, payment status and invoice status are no filter
- **Rules:** `_build_filtered_query` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv, but `invoice_type "receivable"`, partial(`Decimal("1.00")`), draft.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_type="", payment_status="", invoice_status="")`.

**Then**
1. returns: `idset(result) == {N1.id, N2.id}`.

### AIV-FQ-16 — payment_status is exact equality
- **Rules:** `_build_filtered_query` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv, but partial(`Decimal("10.00")`).
3. N3 = inv, but paid.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, payment_status="partial")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-FQ-17 — payment_status in capitals matches nothing
- **Rules:** `_build_filtered_query` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but partial(`Decimal("10.00")`).

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, payment_status="PARTIAL")`.

**Then**
1. returns: `result == []`.

### AIV-FQ-18 — invoice_status is exact equality
- **Rules:** `_build_filtered_query` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv, but draft.
2. N2 = inv.
3. N3 = inv, but voided.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_status="voided")`.

**Then**
1. returns: `ids(result) == [N3.id]`.

### AIV-FQ-19 — "overdue" lists confirmed open invoices due before today
- **Rules:** `_build_filtered_query` R5a [BUG-635]
- **Kind:** bug
- **Expect:** xfail BUG-635
- **Fails today on:** Then 1 (the call raises TypeError: `list_invoices` has no `today` parameter yet; without it the filter compares the stored status and the list is empty)

**Given**
1. N1 = inv, but `due_date PASTDUE`.
2. N2 = inv, but partial(`Decimal("10.00")`), `due_date PASTDUE`.
3. N3 = inv, but `due_date FARDUE`.
4. N4 = inv, but paid, `due_date PASTDUE`.
5. N5 = inv, but draft, `due_date PASTDUE`.
6. N6 = inv.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, payment_status="overdue", today=TD)`.

**Then**
1. returns: `idset(result) == {N1.id, N2.id}`.

### AIV-FQ-20 — invoice date bounds are inclusive on both sides
- **Rules:** `_build_filtered_query` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_date D1`.
2. N2 = inv, but `invoice_date D2`.
3. N3 = inv, but `invoice_date D3`.
4. N4 = inv, but `invoice_date D4`.
5. N5 = inv, but `invoice_date D5`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_date_from=D2, invoice_date_to=D4)`.

**Then**
1. returns: `idset(result) == {N2.id, N3.id, N4.id}`.

### AIV-FQ-21 — a lower due-date bound keeps the bound day and drops undated invoices
- **Rules:** `_build_filtered_query` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `due_date D1`.
2. N2 = inv, but `due_date D2`.
3. N3 = inv, but `due_date D3`.
4. N4 = inv.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, due_date_from=D2)`.

**Then**
1. returns: `idset(result) == {N2.id, N3.id}`.

### AIV-FQ-22 — an upper due-date bound keeps the bound day and drops undated invoices
- **Rules:** `_build_filtered_query` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `due_date D1`.
2. N2 = inv, but `due_date D2`.
3. N3 = inv, but `due_date D3`.
4. N4 = inv.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, due_date_to=D2)`.

**Then**
1. returns: `idset(result) == {N1.id, N2.id}`.

### AIV-FQ-23 — amount bounds are inclusive, one cent outside is out
- **Rules:** `_build_filtered_query` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_amount Decimal("99.99")`.
2. N2 = inv, but `invoice_amount Decimal("100.00")`.
3. N3 = inv, but `invoice_amount Decimal("200.00")`.
4. N4 = inv, but `invoice_amount Decimal("200.01")`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, amount_min=Decimal("100.00"), amount_max=Decimal("200.00"))`.

**Then**
1. returns: `idset(result) == {N2.id, N3.id}`.

### AIV-FQ-24 — amount_max 0 is a bound, not "no filter"
- **Rules:** `_build_filtered_query` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_amount Decimal("0.00")`.
2. N2 = inv, but `invoice_amount Decimal("0.01")`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, amount_max=Decimal("0"))`.

**Then**
1. returns: `ids(result) == [N1.id]`.

### AIV-FQ-25 — amount_min 0 is a bound, not "no filter"
- **Rules:** `_build_filtered_query` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_amount Decimal("-0.01")`.
2. N2 = inv, but `invoice_amount Decimal("0.00")`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, amount_min=Decimal("0"))`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-FQ-26 — invoice number search matches the middle of the number, any case
- **Rules:** `_build_filtered_query` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_number "INV-Beta-1"`.
2. N2 = inv, but `invoice_number "INV-Alpha-77"`.
3. N3 = inv, but `invoice_number "INV-Gamma-3"`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="aLPHA-7")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-FQ-27 — the vendor invoice number is searched too
- **Rules:** `_build_filtered_query` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_number "INV-1"`.
2. N2 = inv, but `vendor_invoice_number "VEND-Kilo-9"`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="kilo")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-FQ-28 — the invoice number search is trimmed
- **Rules:** `_build_filtered_query` R9; `_invoice_number_search_ilike_term` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_number "INV-Alpha-77"`.
2. N2 = inv, but `invoice_number "INV-Beta-1"`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="  alpha ")`.

**Then**
1. returns: `ids(result) == [N1.id]`.

### AIV-FQ-29 — a percent sign in the number search is literal
- **Rules:** `_build_filtered_query` R9 (HR-8)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_number "50%OFF"`.
2. N2 = inv, but `invoice_number "50XOFF"`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="50%o")`.

**Then**
1. returns: `ids(result) == [N1.id]`.

### AIV-FQ-30 — an underscore in the number search is literal
- **Rules:** `_build_filtered_query` R9 (HR-8)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_number "A_B-7"`.
2. N2 = inv, but `invoice_number "AXB-7"`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="a_b")`.

**Then**
1. returns: `ids(result) == [N1.id]`.

### AIV-FQ-31 — a backslash in the number search is literal
- **Rules:** `_build_filtered_query` R9 (HR-8)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_number r"A\B-7"`.
2. N2 = inv, but `invoice_number "AB-7"`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search=r"a\b")`.

**Then**
1. returns: `ids(result) == [N1.id]`.

### AIV-FQ-32 — invoices with no numbers simply do not match
- **Rules:** `_build_filtered_query` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv, but `invoice_number "INV-Alpha-77"`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="alpha")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-FQ-33 — a whitespace-only number search is no filter
- **Rules:** `_build_filtered_query` R9a [BUG-637]
- **Kind:** bug
- **Expect:** xfail BUG-637
- **Fails today on:** Then 1 (the empty pattern matches no invoice)

**Given**
1. N1 = inv, but `invoice_number "INV-1"`.
2. N2 = inv.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="   ")`.

**Then**
1. returns: `idset(result) == {N1.id, N2.id}`.

### AIV-FQ-34 — an empty number search is no filter
- **Rules:** `_build_filtered_query` R9a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_number "INV-1"`.
2. N2 = inv.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="")`.

**Then**
1. returns: `idset(result) == {N1.id, N2.id}`.

### AIV-FQ-35 — an ASCII-digit search also matches the invoice id
- **Rules:** `_build_filtered_query` R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv.
3. N3 = inv.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search=str(N2.id))`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-FQ-36 — a superscript digit is searched as text and never raises
- **Rules:** `_build_filtered_query` R10 [BUG-622]
- **Kind:** bug
- **Expect:** xfail BUG-622
- **Fails today on:** Then 1 (the call raises ValueError: `int("²")`)

**Given**
1. N1 = inv, but `invoice_number "INV-²"`.
2. N2 = inv, but `invoice_number "INV-2"`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search="²")`.

**Then**
1. returns: `ids(result) == [N1.id]`.

### AIV-FQ-37 — Arabic-Indic digits do not match the invoice id
- **Rules:** `_build_filtered_query` R10 [BUG-622]
- **Kind:** bug
- **Expect:** xfail BUG-622
- **Fails today on:** Then 1 (the Unicode digits are read as the id and N2 is returned)

**Given**
1. N1 = inv.
2. N2 = inv.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, invoice_number_search=AR(N2.id))`.

**Then**
1. returns: `result == []`.

### AIV-FQ-38 — account name search matches the middle of the name, any case
- **Rules:** `_build_filtered_query` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. AB = acct(f"Big Bravo Traders {TAG}").
2. N1 = inv.
3. N2 = inv, but `account_id AB.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, account_name_search="bRAVO tr")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-FQ-39 — account name search is not trimmed: a leading space is part of the text
- **Rules:** `_build_filtered_query` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. AB = acct(f"Big Acme {TAG}").
2. N1 = inv.
3. N2 = inv, but `account_id AB.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, account_name_search=" acme")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-FQ-40 — a percent sign in the account name search is literal
- **Rules:** `_build_filtered_query` R11 [BUG-622]
- **Kind:** bug
- **Expect:** xfail BUG-622
- **Fails today on:** Then 1 (an unescaped `%` matches every account)

**Given**
1. AP = acct(f"50% Off {TAG}").
2. N1 = inv.
3. N2 = inv, but `account_id AP.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, account_name_search="%")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-FQ-41 — an underscore in the account name search is literal
- **Rules:** `_build_filtered_query` R11 [BUG-622]
- **Kind:** bug
- **Expect:** xfail BUG-622
- **Fails today on:** Then 1 (an unescaped `_` matches every account)

**Given**
1. AU = acct(f"A_B {TAG}").
2. N1 = inv.
3. N2 = inv, but `account_id AU.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, account_name_search="_")`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-FQ-42 — a backslash in the account name search is literal
- **Rules:** `_build_filtered_query` R11 [BUG-622]
- **Kind:** bug
- **Expect:** xfail BUG-622
- **Fails today on:** Then 1 (an unescaped `\S` means `S`, so the name without the backslash matches instead)

**Given**
1. AS = acct(r"Back\Slash " + TAG).
2. AT = acct(f"BackSlash {TAG}").
3. N1 = inv, but `account_id AS.id`.
4. N2 = inv, but `account_id AT.id`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, account_name_search=r"k\S")`.

**Then**
1. returns: `ids(result) == [N1.id]`.

### AIV-FQ-43 — all filters combine with AND
- **Rules:** `_build_filtered_query` R13
- **Kind:** happy
- **Expect:** pass

**Given**
1. AB = acct(f"Beta {TAG}").
2. N1 = inv, but `invoice_type "receivable"`, `invoice_date D3`.
3. N2 = inv, but `invoice_type "receivable"`, `invoice_date D1`.
4. N3 = inv, but `invoice_date D3`.
5. N4 = inv, but `account_id AB.id`, `invoice_type "receivable"`, `invoice_date D3`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, account_id=AC1.id, invoice_type="receivable", invoice_date_from=D2)`.

**Then**
1. returns: `ids(result) == [N1.id]`.

### AIV-FQ-44 — "overdue" day boundary: due the day before today is overdue, due today or tomorrow is not
- **Rules:** `_build_filtered_query` R5a [BUG-635]
- **Kind:** bug
- **Expect:** xfail BUG-635
- **Fails today on:** Then 1 (the call raises TypeError: `list_invoices` has no `today` parameter yet)

**Given**
1. N1 = inv, but `due_date TDM1`.
2. N2 = inv, but `due_date TD`.
3. N3 = inv, but `due_date TDP1`.
4. N4 = inv.
5. N5 = inv, but partial(`Decimal("10.00")`), `due_date TDM1`.
6. N6 = inv, but paid, `due_date TDM1`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, payment_status="overdue", today=TD)`.

**Then**
1. returns: `idset(result) == {N1.id, N5.id}`.

## `AccountInvoiceDAO.list_invoices`

### AIV-LI-01 — newest invoice date first, ties by higher id, an older invoice with the highest id last
- **Rules:** `list_invoices` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_date D2`.
2. N2 = inv, but `invoice_date D3`.
3. N3 = inv, but `invoice_date D2`.
4. N4 = inv, but `invoice_date D1`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id)`.

**Then**
1. returns: `type(result) is list`.
2. returns: `ids(result) == [N2.id, N3.id, N1.id, N4.id]`.

### AIV-LI-02 — the default limit is 100
- **Rules:** `list_invoices` R3
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. invs(101).

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `result[0].invoice_number == "BULK-0100"`.
3. returns: `result[-1].invoice_number == "BULK-0001"`.

### AIV-LI-03 — skip and limit cut the ordered list
- **Rules:** `list_invoices` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. invs(6).

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, skip=2, limit=3)`.

**Then**
1. returns: `[r.invoice_number for r in result] == ["BULK-0003", "BULK-0002", "BULK-0001"]`.

### AIV-LI-04 — limit 1000 returns 1000 of 1001 rows
- **Rules:** `list_invoices` R3
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. invs(1001).

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 1000`.
2. returns: `result[-1].invoice_number == "BULK-0001"`.

### AIV-LI-05 — filtering happens before paging
- **Rules:** `list_invoices` R3; `_build_filtered_query` R2 (HR-5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. AX = acct(f"Gone {TAG}"), but closed.
2. H = inv, but `account_id AX.id`, `invoice_date D5`.
3. N1 = inv, but `invoice_date D4`.
4. N2 = inv, but `invoice_date D3`.
5. N3 = inv, but `invoice_date D2`.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [N2.id]`.

### AIV-LI-06 — a skip past the end returns an empty list
- **Rules:** `list_invoices` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.
2. returns: `type(result) is list`.

### AIV-LI-07 — the query orders by date then id, both descending, with no row lock
- **Rules:** `list_invoices` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. N1 = inv.
2. `db.expunge_all()`.

**When**
- Statement recorder on: `result = dao.list_invoices(db, workspace_id=W1.id)`; `sql` = the SELECT from `account_invoices`.

**Then**
1. returns: `ids(result) == [N1.id]`.
2. returns: `"account_invoices.invoice_date DESC, account_invoices.id DESC" in order_part`.
3. returns: `"FOR UPDATE" not in sql`.
4. returns: `written == []`.

### AIV-LI-08 — writes nothing: a pending invoice stays pending, an unflushed edit stays unflushed
- **Rules:** `list_invoices` R1 (reader)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. X = inv, but `notes "before"`.
2. `X.notes = "edited"` (not flushed).
3. P = inv, but `invoice_number "PEND-1"`, added with `db.add(P)` and not flushed.

**When**
- `result = dao.list_invoices(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [X.id]`.
2. pending: `P in db.new`, `len(db.new) == 1`.
3. session: `X in db.dirty`, `len(db.dirty) == 1`.
4. session: `not db.deleted`.
5. session: `X.notes == "edited"`.

## `AccountInvoiceDAO.list_invoices_page`

### AIV-LP-01 — without open_balance_only, every invoice of the account and the total
- **Rules:** `list_invoices_page` R1; `list_invoices_page_filtered` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. AL = acct(f"Lima {TAG}").
2. N1 = inv, but `invoice_date D1`.
3. N2 = inv, but voided, `invoice_date D3`.
4. N3 = inv, but paid, `invoice_date D2`.
5. N4 = inv, but `account_id AL.id`.
6. AN = acct(f"Nova {TAG}").
7. N5 = inv, but `account_id AN.id`.

**When**
- `result = dao.list_invoices_page(db, workspace_id=W1.id, account_id=AC1.id)`.

**Then**
1. returns: `ids(result[0]) == [N2.id, N3.id, N1.id]`.
2. returns: `result[1] == 3`.

### AIV-LP-02 — open_balance_only keeps confirmed unpaid and partial invoices only
- **Rules:** `list_invoices_page` R1; `_build_filtered_query` R12
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv, but partial(`Decimal("10.00")`).
3. N3 = inv, but paid.
4. N4 = inv, but voided.

**When**
- `result = dao.list_invoices_page(db, workspace_id=W1.id, account_id=AC1.id, open_balance_only=True)`.

**Then**
1. returns: `ids(result[0]) == [N2.id, N1.id]`.
2. returns: `result[1] == 2`.

### AIV-LP-03 — open_balance_only leaves drafts out
- **Rules:** `list_invoices_page` R1; `_build_filtered_query` R12 [BUG-634]
- **Kind:** bug
- **Expect:** xfail BUG-634
- **Fails today on:** Then 1 (the draft is listed)

**Given**
1. N1 = inv.
2. N2 = inv, but draft.

**When**
- `result = dao.list_invoices_page(db, workspace_id=W1.id, account_id=AC1.id, open_balance_only=True)`.

**Then**
1. returns: `ids(result[0]) == [N1.id]`.
2. returns: `result[1] == 1`.

### AIV-LP-04 — the default page is 10 rows, the total counts all 11
- **Rules:** `list_invoices_page` R1; `list_invoices_page_filtered` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. invs(11).

**When**
- `result = dao.list_invoices_page(db, workspace_id=W1.id, account_id=AC1.id)`.

**Then**
1. returns: `len(result[0]) == 10`.
2. returns: `result[0][-1].invoice_number == "BULK-0001"`.
3. returns: `result[1] == 11`.

### AIV-LP-05 — skip and limit cut the page, the total ignores them
- **Rules:** `list_invoices_page` R1; `list_invoices_page_filtered` R2, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. invs(6).

**When**
- `result = dao.list_invoices_page(db, workspace_id=W1.id, account_id=AC1.id, skip=2, limit=3)`.

**Then**
1. returns: `[r.invoice_number for r in result[0]] == ["BULK-0003", "BULK-0002", "BULK-0001"]`.
2. returns: `result[1] == 6`.

### AIV-LP-06 — prioritize_purchase_order_id puts that order's invoices first
- **Rules:** `list_invoices_page` R1; `list_invoices_page_filtered` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_date D5`.
2. N2 = inv, but `invoice_date D1`, `order_type "purchase_order"`, `order_id XID(1)`.
3. N3 = inv, but `invoice_date D3`.

**When**
- `result = dao.list_invoices_page(db, workspace_id=W1.id, account_id=AC1.id, prioritize_purchase_order_id=XID(1))`.

**Then**
1. returns: `ids(result[0]) == [N2.id, N1.id, N3.id]`.
2. returns: `result[1] == 3`.

### AIV-LP-07 — W1 does not see W2's invoice when asking for W2's account
- **Rules:** `list_invoices_page` R1; `_build_filtered_query` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = inv of W0.
2. N1 = inv.
3. X2 = inv of W2.

**When**
- `result = dao.list_invoices_page(db, workspace_id=W1.id, account_id=AC2.id)`.

**Then**
1. returns: `result[0] == []`.
2. returns: `result[1] == 0`.

### AIV-LP-08 — W1 does not see W0's invoice when asking for W0's account
- **Rules:** `list_invoices_page` R1; `_build_filtered_query` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = inv of W0.
2. N1 = inv.
3. X2 = inv of W2.

**When**
- `result = dao.list_invoices_page(db, workspace_id=W1.id, account_id=AC0.id)`.

**Then**
1. returns: `result[0] == []`.
2. returns: `result[1] == 0`.

### AIV-LP-09 — a W1 invoice placed on W2's account is not listed under that account
- **Rules:** `list_invoices_page` R1; `_build_filtered_query` R2a [BUG-2690]
- **Kind:** bug
- **Expect:** xfail BUG-2690
- **Fails today on:** Then 1 (the invoice is listed under the foreign account)

**Given**
1. N1 = inv.
2. X = inv, but `account_id AC2.id`.

**When**
- `result = dao.list_invoices_page(db, workspace_id=W1.id, account_id=AC2.id)`.

**Then**
1. returns: `result[0] == []`.
2. returns: `result[1] == 0`.

## `AccountInvoiceDAO.list_invoices_page_filtered`

### AIV-PF-01 — total counts every match, the page is cut after ordering
- **Rules:** `list_invoices_page_filtered` R1, R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_date D1`.
2. N2 = inv, but `invoice_date D2`.
3. N3 = inv, but `invoice_date D3`.
4. N4 = inv, but `invoice_date D4`.
5. N5 = inv, but `invoice_date D5`.

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `ids(result[0]) == [N4.id, N3.id]`.
2. returns: `result[1] == 5`.

### AIV-PF-02 — newest date first, ties by higher id, an older invoice with the highest id last
- **Rules:** `list_invoices_page_filtered` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_date D2`.
2. N2 = inv, but `invoice_date D3`.
3. N3 = inv, but `invoice_date D2`.
4. N4 = inv, but `invoice_date D1`.

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id, account_id=AC1.id)`.

**Then**
1. returns: `ids(result[0]) == [N2.id, N3.id, N1.id, N4.id]`.

### AIV-PF-03 — prioritised invoices come first, each group by date then id, both descending
- **Rules:** `list_invoices_page_filtered` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_date D5`.
2. N2 = inv, but `invoice_date D1`, `order_type "purchase_order"`, `order_id XID(1)`.
3. N3 = inv, but `invoice_date D2`, `order_type "purchase_order"`, `order_id XID(1)`.
4. N4 = inv, but `invoice_date D1`, `order_type "purchase_order"`, `order_id XID(1)`.
5. N5 = inv, but `invoice_date D3`.
6. N6 = inv, but `invoice_date D3`, `order_type "purchase_order"`, `order_id XID(2)`.

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id, account_id=AC1.id, prioritize_purchase_order_id=XID(1))`.

**Then**
1. returns: `ids(result[0]) == [N3.id, N4.id, N2.id, N1.id, N6.id, N5.id]`.
2. returns: `result[1] == 6`.

### AIV-PF-04 — a receivable credit note of the prioritised order is prioritised too
- **Rules:** `list_invoices_page_filtered` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_date D5`.
2. N2 = inv, but `invoice_type "receivable"`, `invoice_date D1`, `order_type "purchase_order"`, `order_id XID(1)`.

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id, account_id=AC1.id, prioritize_purchase_order_id=XID(1))`.

**Then**
1. returns: `ids(result[0]) == [N2.id, N1.id]`.

### AIV-PF-05 — an invoice linked only through the order's invoice_id is not prioritised
- **Rules:** `list_invoices_page_filtered` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_date D5`.
2. N2 = inv, but `invoice_date D1`.
3. P = po("PO-PRIO-1"), but `invoice_id N2.id`.

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id, account_id=AC1.id, prioritize_purchase_order_id=P.id)`.

**Then**
1. returns: `ids(result[0]) == [N1.id, N2.id]`.

### AIV-PF-06 — an expense-order link with the same order id is not prioritised
- **Rules:** `list_invoices_page_filtered` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_date D5`.
2. N2 = inv, but `invoice_date D1`, `order_type "expense_order"`, `order_id XID(1)`.
3. N3 = inv, but `invoice_date D2`, `order_type "Purchase_Order"`, `order_id XID(1)`.

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id, account_id=AC1.id, prioritize_purchase_order_id=XID(1))`.

**Then**
1. returns: `ids(result[0]) == [N1.id, N3.id, N2.id]`.

### AIV-PF-07 — prioritize_purchase_order_id 0 is given, not "none"
- **Rules:** `list_invoices_page_filtered` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_date D5`.
2. N2 = inv, but `invoice_date D1`, `order_type "purchase_order"`, `order_id 0`.

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id, account_id=AC1.id, prioritize_purchase_order_id=0)`.

**Then**
1. returns: `ids(result[0]) == [N2.id, N1.id]`.

### AIV-PF-08 — prioritised rows are paged after ordering
- **Rules:** `list_invoices_page_filtered` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_date D5`.
2. N2 = inv, but `invoice_date D1`, `order_type "purchase_order"`, `order_id XID(1)`.
3. N3 = inv, but `invoice_date D2`, `order_type "purchase_order"`, `order_id XID(1)`.
4. N4 = inv, but `invoice_date D4`.

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id, account_id=AC1.id, prioritize_purchase_order_id=XID(1), skip=1, limit=2)`.

**Then**
1. returns: `ids(result[0]) == [N2.id, N1.id]`.
2. returns: `result[1] == 4`.

### AIV-PF-09 — the default page is 10 rows
- **Rules:** `list_invoices_page_filtered` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. invs(11).

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result[0]) == 10`.
2. returns: `result[0][-1].invoice_number == "BULK-0001"`.
3. returns: `result[1] == 11`.

### AIV-PF-10 — limit 1000 returns 1000 of 1001 rows, total 1001
- **Rules:** `list_invoices_page_filtered` R2, R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. invs(1001).

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id, account_id=AC1.id, limit=1000)`.

**Then**
1. returns: `len(result[0]) == 1000`.
2. returns: `result[1] == 1001`.

### AIV-PF-11 — filtering happens before paging and before the total
- **Rules:** `list_invoices_page_filtered` R1, R2 (HR-5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. AX = acct(f"Gone {TAG}"), but closed.
2. H = inv, but `account_id AX.id`, `invoice_date D5`.
3. N1 = inv, but `invoice_date D4`.
4. N2 = inv, but `invoice_date D3`.
5. N3 = inv, but `invoice_date D2`.

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result[0]) == [N2.id]`.
2. returns: `result[1] == 3`.

### AIV-PF-12 — every filter is passed through: payment status and number search together
- **Rules:** `list_invoices_page_filtered` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv, but partial(`Decimal("5.00")`), `invoice_number "INV-Alpha-1"`.
2. N2 = inv, but `invoice_number "INV-Alpha-2"`.
3. N3 = inv, but partial(`Decimal("5.00")`), `invoice_number "INV-Beta-3"`.

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id, account_id=AC1.id, payment_status="partial", invoice_number_search="alpha")`.

**Then**
1. returns: `ids(result[0]) == [N1.id]`.
2. returns: `result[1] == 1`.

### AIV-PF-13 — amount bounds and account name search are passed through
- **Rules:** `list_invoices_page_filtered` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. AB = acct(f"Bravo {TAG}").
2. N1 = inv, but `account_id AB.id`, `invoice_amount Decimal("50.00")`.
3. N2 = inv, but `account_id AB.id`, `invoice_amount Decimal("500.00")`.
4. N3 = inv, but `invoice_amount Decimal("50.00")`.

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id, account_name_search="bravo", amount_max=Decimal("100.00"))`.

**Then**
1. returns: `ids(result[0]) == [N1.id]`.
2. returns: `result[1] == 1`.

### AIV-PF-14 — open_balance_only leaves paid and voided invoices out
- **Rules:** `list_invoices_page_filtered` R1; `_build_filtered_query` R12
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv, but paid.
3. N3 = inv, but voided.
4. N4 = inv, but partial(`Decimal("99.99")`).

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id, open_balance_only=True)`.

**Then**
1. returns: `ids(result[0]) == [N4.id, N1.id]`.
2. returns: `result[1] == 2`.

### AIV-PF-15 — open_balance_only leaves drafts out
- **Rules:** `list_invoices_page_filtered` R1; `_build_filtered_query` R12 [BUG-634]
- **Kind:** bug
- **Expect:** xfail BUG-634
- **Fails today on:** Then 1 (the draft is listed)

**Given**
1. N1 = inv.
2. N2 = inv, but draft, partial(`Decimal("10.00")`).

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id, open_balance_only=True)`.

**Then**
1. returns: `ids(result[0]) == [N1.id]`.
2. returns: `result[1] == 1`.

### AIV-PF-16 — W0's and W2's invoices are neither listed nor counted
- **Rules:** `list_invoices_page_filtered` R1, R2; `_build_filtered_query` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = inv of W0.
2. N1 = inv.
3. X2 = inv of W2.

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result[0]) == [N1.id]`.
2. returns: `result[1] == 1`.

### AIV-PF-17 — a W1 invoice on W0's account is neither listed nor counted
- **Rules:** `list_invoices_page_filtered` R1, R2; `_build_filtered_query` R2a [BUG-2690]
- **Kind:** bug
- **Expect:** xfail BUG-2690
- **Fails today on:** Then 2 (the total counts the invoice on the foreign account)

**Given**
1. N1 = inv.
2. X = inv, but `account_id AC0.id`.

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id)`.

**Then**
1. returns: `N1.id in idset(result[0])`.
2. returns: `result[1] == 1`.
3. returns: `ids(result[0]) == [N1.id]`.

### AIV-PF-18 — the page query ends its order in id, with no row lock
- **Rules:** `list_invoices_page_filtered` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. N1 = inv.
2. `db.expunge_all()`.

**When**
- Statement recorder on: `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id, account_id=AC1.id)`; `sql` = the SELECT from `account_invoices` that has an `ORDER BY`.

**Then**
1. returns: `ids(result[0]) == [N1.id]`.
2. returns: `order_part.rstrip().endswith("account_invoices.id DESC")`.
3. returns: `"FOR UPDATE" not in sql`.
4. returns: `written == []`.

### AIV-PF-19 — open_balance_only not sent: paid, voided and draft invoices are all listed and counted
- **Rules:** `list_invoices_page_filtered` R1 (default `open_balance_only=False`); `_build_filtered_query` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv, but paid.
3. N3 = inv, but voided.
4. N4 = inv, but draft.

**When**
- `result = dao.list_invoices_page_filtered(db, workspace_id=W1.id, account_id=AC1.id)` (`open_balance_only` not sent).

**Then**
1. returns: `ids(result[0]) == [N4.id, N3.id, N2.id, N1.id]`.
2. returns: `result[1] == 4`.

## `AccountInvoiceDAO.list_accounts_hub_page` (with `_open_balance_subquery`)

### AIV-AH-01 — each account comes with its payable and receivable open balances
- **Rules:** `list_accounts_hub_page` R1, R2; `_open_balance_subquery` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. hubclean.
2. AB = acct(f"Bravo {TAG}").
3. AC = acct(f"Charlie {TAG}").
4. N1 = inv, but `account_id AB.id`, `invoice_amount Decimal("100.10")`.
5. N2 = inv, but `account_id AB.id`, `invoice_amount Decimal("200.20")`, partial(`Decimal("0.05")`).
6. N3 = inv, but `account_id AB.id`, `invoice_amount Decimal("50.00")`, paid.
7. N4 = inv, but `account_id AB.id`, `invoice_amount Decimal("70.00")`, voided.
8. N5 = inv, but `account_id AB.id`, `invoice_type "receivable"`, `invoice_amount Decimal("0.10")`.
9. N6 = inv, but `account_id AB.id`, `invoice_type "receivable"`, `invoice_amount Decimal("0.20")`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `hids(result) == [AB.id, AC.id]`.
2. returns: `result[1] == 2`.
3. returns: `pay(result, AB).outstanding_total == Decimal("300.25")`, `pay(result, AB).open_count == 2`, `pay(result, AB).has_overdue is False`.
4. returns: `rec(result, AB).outstanding_total == Decimal("0.30")`, `rec(result, AB).open_count == 2`, `rec(result, AB).has_overdue is False`.
5. returns: `pay(result, AC).outstanding_total == 0`, `pay(result, AC).open_count == 0`, `pay(result, AC).has_overdue is False`.
6. returns: `rec(result, AC).outstanding_total == 0`, `rec(result, AC).open_count == 0`.
7. returns: `isinstance(pay(result, AB).outstanding_total, Decimal)`.

### AIV-AH-02 — a draft adds nothing to the open balance
- **Rules:** `_open_balance_subquery` R1 [BUG-634]
- **Kind:** bug
- **Expect:** xfail BUG-634
- **Fails today on:** Then 2 (the draft is counted)

**Given**
1. hubclean.
2. AB = acct(f"Bravo {TAG}").
3. N1 = inv, but `account_id AB.id`, `invoice_amount Decimal("40.00")`.
4. N2 = inv, but `account_id AB.id`, draft.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `hids(result) == [AB.id]`.
2. returns: `pay(result, AB).outstanding_total == Decimal("40.00")`.
3. returns: `pay(result, AB).open_count == 1`.

### AIV-AH-03 — an open invoice due before today sets has_overdue
- **Rules:** `_open_balance_subquery` R2 [BUG-635]
- **Kind:** bug
- **Expect:** xfail BUG-635
- **Fails today on:** Then 1 (the call raises TypeError: no `today` parameter yet; without it has_overdue reads a stored "overdue" status and stays False)

**Given**
1. hubclean.
2. AB = acct(f"Bravo {TAG}").
3. N1 = inv, but `account_id AB.id`, `due_date PASTDUE`.
4. N2 = inv, but `account_id AB.id`, `due_date FARDUE`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, today=TD)`.

**Then**
1. returns: `pay(result, AB).open_count == 2`.
2. returns: `pay(result, AB).has_overdue is True`.

### AIV-AH-04 — open invoices due far ahead or undated never set has_overdue
- **Rules:** `_open_balance_subquery` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. hubclean.
2. AB = acct(f"Bravo {TAG}").
3. N1 = inv, but `account_id AB.id`, `due_date FARDUE`.
4. N2 = inv, but `account_id AB.id`, `invoice_type "receivable"`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `pay(result, AB).has_overdue is False`.
2. returns: `rec(result, AB).has_overdue is False`.

### AIV-AH-05 — an inactive account with an open balance is shown
- **Rules:** `list_accounts_hub_page` R1 [BUG-636]
- **Kind:** bug
- **Expect:** xfail BUG-636
- **Fails today on:** Then 1 (only active accounts are listed)

**Given**
1. hubclean.
2. AB = acct(f"Bravo {TAG}").
3. AI = acct(f"Idle {TAG}"), but inactive.
4. N1 = inv, but `account_id AI.id`, `invoice_amount Decimal("12.34")`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `hids(result) == [AB.id, AI.id]`.
2. returns: `pay(result, AI).outstanding_total == Decimal("12.34")`.

### AIV-AH-06 — an inactive account with nothing open is not shown
- **Rules:** `list_accounts_hub_page` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. hubclean.
2. AB = acct(f"Bravo {TAG}").
3. AI = acct(f"Idle {TAG}"), but inactive.
4. N1 = inv, but `account_id AI.id`, paid.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `hids(result) == [AB.id]`.
2. returns: `result[1] == 1`.

### AIV-AH-07 — a closed account is not shown, even with an open invoice
- **Rules:** `list_accounts_hub_page` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. hubclean.
2. AB = acct(f"Bravo {TAG}").
3. AX = acct(f"Gone {TAG}"), but closed.
4. N1 = inv, but `account_id AX.id`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `hids(result) == [AB.id]`.
2. returns: `result[1] == 1`.

### AIV-AH-08 — a deleted but still active account is not shown
- **Rules:** `list_accounts_hub_page` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. hubclean.
2. AB = acct(f"Bravo {TAG}").
3. AX = acct(f"Half {TAG}"), but half-closed.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `hids(result) == [AB.id]`.

### AIV-AH-09 — W1's hub has none of W0's or W2's accounts
- **Rules:** `list_accounts_hub_page` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. hubclean.
2. AB = acct(f"Bravo {TAG}").
3. X0 = inv of W0.
4. X2 = inv of W2.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `hids(result) == [AB.id]`.
2. returns: `result[1] == 1`.

### AIV-AH-10 — asked for W2, only W2's account, with its own balance
- **Rules:** `list_accounts_hub_page` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = inv of W0.
2. N1 = inv.
3. X2 = inv of W2, but `invoice_amount Decimal("7.00")`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W2.id)`.

**Then**
1. returns: `hids(result) == [AC2.id]`.
2. returns: `pay(result, AC2).outstanding_total == Decimal("7.00")`, `pay(result, AC2).open_count == 1`.

### AIV-AH-11 — asked for W0, only W0's account, with its own balance
- **Rules:** `list_accounts_hub_page` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = inv of W0, but `invoice_amount Decimal("8.00")`.
2. N1 = inv.
3. X2 = inv of W2.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W0.id)`.

**Then**
1. returns: `hids(result) == [AC0.id]`.
2. returns: `pay(result, AC0).outstanding_total == Decimal("8.00")`, `pay(result, AC0).open_count == 1`.

### AIV-AH-12 — a W1 invoice on W2's account shows on no W1 hub row
- **Rules:** `_open_balance_subquery` R1a; `list_accounts_hub_page` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. hubclean.
2. AB = acct(f"Bravo {TAG}").
3. N1 = inv, but `account_id AB.id`, `invoice_amount Decimal("10.00")`.
4. X = inv, but `account_id AC2.id`, `invoice_amount Decimal("90.00")`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `hids(result) == [AB.id]`.
2. returns: `pay(result, AB).outstanding_total == Decimal("10.00")`, `pay(result, AB).open_count == 1`.

### AIV-AH-13 — section "payable" keeps accounts with a payable balance only
- **Rules:** `list_accounts_hub_page` R3, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. hubclean.
2. AP = acct(f"Papa {TAG}").
3. AR = acct(f"Romeo {TAG}").
4. AN = acct(f"November {TAG}").
5. N1 = inv, but `account_id AP.id`, `invoice_amount Decimal("10.00")`.
6. N2 = inv, but `account_id AR.id`, `invoice_type "receivable"`, `invoice_amount Decimal("10.00")`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, section="payable")`.

**Then**
1. returns: `hids(result) == [AP.id]`.
2. returns: `result[1] == 1`.

### AIV-AH-14 — section "receivable" keeps accounts with a receivable balance only
- **Rules:** `list_accounts_hub_page` R3, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. hubclean.
2. AP = acct(f"Papa {TAG}").
3. AR = acct(f"Romeo {TAG}").
4. AN = acct(f"November {TAG}").
5. N1 = inv, but `account_id AP.id`, `invoice_amount Decimal("10.00")`.
6. N2 = inv, but `account_id AR.id`, `invoice_type "receivable"`, `invoice_amount Decimal("10.00")`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, section="receivable")`.

**Then**
1. returns: `hids(result) == [AR.id]`.
2. returns: `result[1] == 1`.

### AIV-AH-15 — section "overview" has no balance filter
- **Rules:** `list_accounts_hub_page` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. hubclean.
2. AP = acct(f"Papa {TAG}").
3. AN = acct(f"November {TAG}").
4. N1 = inv, but `account_id AP.id`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, section="overview")`.

**Then**
1. returns: `hids(result) == [AN.id, AP.id]`.
2. returns: `result[1] == 2`.

### AIV-AH-16 — an unknown section has no balance filter
- **Rules:** `list_accounts_hub_page` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. hubclean.
2. AP = acct(f"Papa {TAG}").
3. AN = acct(f"November {TAG}").
4. N1 = inv, but `account_id AP.id`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, section="Payable")`.

**Then**
1. returns: `hids(result) == [AN.id, AP.id]`.

### AIV-AH-17 — an empty section has no balance filter
- **Rules:** `list_accounts_hub_page` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. hubclean.
2. AP = acct(f"Papa {TAG}").
3. AN = acct(f"November {TAG}").
4. N1 = inv, but `account_id AP.id`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, section="")`.

**Then**
1. returns: `hids(result) == [AN.id, AP.id]`.

### AIV-AH-18 — a payable balance of 0.00 is not "> 0", one of 0.01 is
- **Rules:** `list_accounts_hub_page` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. hubclean.
2. AZ = acct(f"Zero {TAG}").
3. AO = acct(f"One {TAG}").
4. N1 = inv, but `account_id AZ.id`, `invoice_amount Decimal("0.00")`.
5. N2 = inv, but `account_id AO.id`, `invoice_amount Decimal("0.01")`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, section="payable")`.

**Then**
1. returns: `hids(result) == [AO.id]`.
2. returns: `result[1] == 1`.

### AIV-AH-19 — search matches the middle of the account name, any case
- **Rules:** `list_accounts_hub_page` R4, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. hubclean.
2. AB = acct(f"Big Bravo Traders {TAG}").
3. AC = acct(f"Charlie {TAG}").

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, search="bRAVO tr")`.

**Then**
1. returns: `hids(result) == [AB.id]`.
2. returns: `result[1] == 1`.

### AIV-AH-20 — a percent sign in the hub search is literal
- **Rules:** `list_accounts_hub_page` R4 [BUG-622]
- **Kind:** bug
- **Expect:** xfail BUG-622
- **Fails today on:** Then 1 (an unescaped `%` matches every account)

**Given**
1. hubclean.
2. AP = acct(f"50% Off {TAG}").
3. AC = acct(f"Charlie {TAG}").

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, search="%")`.

**Then**
1. returns: `hids(result) == [AP.id]`.

### AIV-AH-21 — an underscore in the hub search is literal
- **Rules:** `list_accounts_hub_page` R4 [BUG-622]
- **Kind:** bug
- **Expect:** xfail BUG-622
- **Fails today on:** Then 1 (an unescaped `_` matches every account)

**Given**
1. hubclean.
2. AU = acct(f"A_B {TAG}").
3. AC = acct(f"Charlie {TAG}").

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, search="_")`.

**Then**
1. returns: `hids(result) == [AU.id]`.

### AIV-AH-22 — a backslash in the hub search is literal
- **Rules:** `list_accounts_hub_page` R4 [BUG-622]
- **Kind:** bug
- **Expect:** xfail BUG-622
- **Fails today on:** Then 1 (an unescaped `\S` means `S`, so the name without the backslash matches instead)

**Given**
1. hubclean.
2. AS = acct(r"Back\Slash " + TAG).
3. AT = acct(f"BackSlash {TAG}").

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, search=r"k\S")`.

**Then**
1. returns: `hids(result) == [AS.id]`.

### AIV-AH-23 — accounts are ordered by name, not by id
- **Rules:** `list_accounts_hub_page` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. hubclean.
2. AD = acct(f"Delta {TAG}").
3. AC = acct(f"Charlie {TAG}").
4. AB = acct(f"Bravo {TAG}").

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `hids(result) == [AB.id, AC.id, AD.id]`.

### AIV-AH-24 — accounts with the same name are ordered by id ascending
- **Rules:** `list_accounts_hub_page` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. hubclean.
2. E1 = acct(f"Echo {TAG}").
3. E2 = acct(f"Echo {TAG}").
4. E3 = acct(f"Echo {TAG}").
5. bump: `db.execute(text("UPDATE accounts SET name = name WHERE id = :i"), {"i": E1.id})`, then `db.expire_all()`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `hids(result) == [E1.id, E2.id, E3.id]`.

### AIV-AH-25 — names that differ only in case are ordered case-insensitively, then by id
- **Rules:** `list_accounts_hub_page` R5 [BUG-623]
- **Kind:** bug
- **Expect:** xfail BUG-623
- **Fails today on:** Then 1 (today's `ORDER BY accounts.name` is case-sensitive)

**Given**
1. hubclean.
2. B1 = acct(f"Bravo {TAG}").
3. B2 = acct(f"bravo {TAG}").
4. B3 = acct(f"BRAVO {TAG}").

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `hids(result) == [B1.id, B2.id, B3.id]`.

### AIV-AH-26 — the hub query orders by the lower-cased name
- **Rules:** `list_accounts_hub_page` R5 [BUG-623]
- **Kind:** bug
- **Expect:** xfail BUG-623
- **Fails today on:** Then 2 (the order uses `accounts.name` as stored)

**Given**
1. hubclean.
2. AB = acct(f"Bravo {TAG}").
3. `db.expunge_all()`.

**When**
- Statement recorder on: `result = dao.list_accounts_hub_page(db, workspace_id=W1.id)`; `sql` = the SELECT from `accounts` that has an `ORDER BY`.

**Then**
1. returns: `hids(result) == [AB.id]`.
2. returns: `"lower(accounts.name)" in order_part.lower()`.

### AIV-AH-27 — the hub query ends its order in accounts.id and takes no row lock
- **Rules:** `list_accounts_hub_page` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. hubclean.
2. AB = acct(f"Bravo {TAG}").
3. `db.expunge_all()`.

**When**
- Statement recorder on: `result = dao.list_accounts_hub_page(db, workspace_id=W1.id)`; `sql` = the SELECT from `accounts` that has an `ORDER BY`.

**Then**
1. returns: `hids(result) == [AB.id]`.
2. returns: `order_part.rstrip().endswith("accounts.id ASC")`.
3. returns: `"FOR UPDATE" not in sql`.
4. returns: `written == []`.

### AIV-AH-28 — total counts every account, the page is cut after ordering
- **Rules:** `list_accounts_hub_page` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. hubclean.
2. AD = acct(f"Delta {TAG}").
3. AB = acct(f"Bravo {TAG}").
4. AC = acct(f"Charlie {TAG}").

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `hids(result) == [AC.id]`.
2. returns: `result[1] == 3`.

### AIV-AH-29 — the default page is 50 accounts, the total counts all 51
- **Rules:** `list_accounts_hub_page` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. hubclean.
2. accts(51).

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result[0]) == 50`.
2. returns: `result[0][-1][0].name == f"Bulk 0049 {TAG}"`.
3. returns: `result[1] == 51`.

### AIV-AH-30 — limit 1000 returns all 60 accounts
- **Rules:** `list_accounts_hub_page` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. hubclean.
2. accts(60).

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result[0]) == 60`.
2. returns: `result[1] == 60`.

### AIV-AH-31 — the section filter runs before paging and before the total
- **Rules:** `list_accounts_hub_page` R3, R6 (HR-5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. hubclean.
2. AA = acct(f"Bravo {TAG}").
3. AP = acct(f"Charlie {TAG}").
4. AQ = acct(f"Delta {TAG}").
5. AR = acct(f"Echo {TAG}").
6. N1 = inv, but `account_id AP.id`.
7. N2 = inv, but `account_id AQ.id`.
8. N3 = inv, but `account_id AR.id`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, section="payable", skip=1, limit=1)`.

**Then**
1. returns: `hids(result) == [AQ.id]`.
2. returns: `result[1] == 3`.

### AIV-AH-32 — writes nothing: a pending account stays pending, an unflushed edit stays unflushed
- **Rules:** `list_accounts_hub_page` R1 (reader)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. hubclean.
2. AB = acct(f"Bravo {TAG}").
3. `AB.name = f"Bravo edited {TAG}"` (not flushed).
4. P = acct(f"Pending {TAG}"), added with `db.add(P)` and not flushed.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `hids(result) == [AB.id]`.
2. pending: `P in db.new`, `len(db.new) == 1`.
3. session: `AB in db.dirty`, `len(db.dirty) == 1`.
4. session: `not db.deleted`.
5. session: `AB.name == f"Bravo edited {TAG}"`.

### AIV-AH-33 — the hub: an open invoice due the day before today sets has_overdue, on either side
- **Rules:** `_open_balance_subquery` R2 [BUG-635]
- **Kind:** bug
- **Expect:** xfail BUG-635
- **Fails today on:** Then 1 (the call raises TypeError: `list_accounts_hub_page` has no `today` parameter yet)

**Given**
1. hubclean.
2. AB = acct(f"Bravo {TAG}").
3. AC = acct(f"Charlie {TAG}").
4. N1 = inv, but `account_id AB.id`, `due_date TDM1`.
5. N2 = inv, but `account_id AC.id`, `invoice_type "receivable"`, `due_date TDM1`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, today=TD)`.

**Then**
1. returns: `pay(result, AB).has_overdue is True`.
2. returns: `rec(result, AC).has_overdue is True`.

### AIV-AH-34 — the hub: due today, due tomorrow or undated never sets has_overdue
- **Rules:** `_open_balance_subquery` R2 [BUG-635]
- **Kind:** bug
- **Expect:** xfail BUG-635
- **Fails today on:** Then 1 (the call raises TypeError: `list_accounts_hub_page` has no `today` parameter yet)

**Given**
1. hubclean.
2. AB = acct(f"Bravo {TAG}").
3. N1 = inv, but `account_id AB.id`, `due_date TD`.
4. N2 = inv, but `account_id AB.id`, `due_date TDP1`.
5. N3 = inv, but `account_id AB.id`.
6. N4 = inv, but `account_id AB.id`, `invoice_type "receivable"`, `due_date TD`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, today=TD)`.

**Then**
1. returns: `pay(result, AB).has_overdue is False`.
2. returns: `rec(result, AB).has_overdue is False`.
3. returns: `pay(result, AB).open_count == 3`.

### AIV-AH-35 — a receivable balance of 0.00 is not "> 0", one of 0.01 is
- **Rules:** `list_accounts_hub_page` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. hubclean.
2. AZ = acct(f"Zero {TAG}").
3. AO = acct(f"One {TAG}").
4. N1 = inv, but `account_id AZ.id`, `invoice_type "receivable"`, `invoice_amount Decimal("0.00")`.
5. N2 = inv, but `account_id AO.id`, `invoice_type "receivable"`, `invoice_amount Decimal("0.01")`.

**When**
- `result = dao.list_accounts_hub_page(db, workspace_id=W1.id, section="receivable")`.

**Then**
1. returns: `hids(result) == [AO.id]`.
2. returns: `result[1] == 1`.
3. returns: `rec(result, AO).outstanding_total == Decimal("0.01")`.

## `AccountInvoiceDAO.summarize_open_hub_type`

### AIV-HS-01 — open count, exact outstanding sum and distinct accounts of the payables
- **Rules:** `summarize_open_hub_type` R1, R2; `_outstanding_amount_expr` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. AI = acct(f"Idle {TAG}"), but inactive.
2. N1 = inv.
3. N2 = inv, but `invoice_amount Decimal("200.20")`, partial(`Decimal("50.05")`).
4. N3 = inv, but `account_id AI.id`, `invoice_amount Decimal("0.10")`.
5. N4 = inv, but `account_id AI.id`, `invoice_amount Decimal("0.20")`.
6. N5 = inv, but paid.
7. N6 = inv, but voided.
8. N7 = inv, but `invoice_type "receivable"`, `invoice_amount Decimal("999.00")`.

**When**
- `result = dao.summarize_open_hub_type(db, workspace_id=W1.id, invoice_type="payable")`.

**Then**
1. returns: `result[0] == 4`.
2. returns: `result[1] == Decimal("250.45")`.
3. returns: `result[2] == 0`.
4. returns: `result[3] == 2`.
5. returns: `isinstance(result[1], Decimal)`.

### AIV-HS-02 — the receivable type counts receivables only
- **Rules:** `summarize_open_hub_type` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv, but `invoice_type "receivable"`, `invoice_amount Decimal("30.00")`.

**When**
- `result = dao.summarize_open_hub_type(db, workspace_id=W1.id, invoice_type="receivable")`.

**Then**
1. returns: `result == (1, Decimal("30.00"), 0, 1)`.

### AIV-HS-03 — nothing open gives zeros, the total as a Decimal
- **Rules:** `summarize_open_hub_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but paid.

**When**
- `result = dao.summarize_open_hub_type(db, workspace_id=W1.id, invoice_type="payable")`.

**Then**
1. returns: `result == (0, Decimal("0"), 0, 0)`.
2. returns: `isinstance(result[1], Decimal)`.
3. returns: `type(result[0]) is int`, `type(result[3]) is int`.

### AIV-HS-04 — an unknown type gives (0, 0, 0, 0)
- **Rules:** `summarize_open_hub_type` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv.

**When**
- `result = dao.summarize_open_hub_type(db, workspace_id=W1.id, invoice_type="Payable")`.

**Then**
1. returns: `result == (0, 0, 0, 0)`.

### AIV-HS-05 — invoices of a closed account and of a deleted active account are not counted
- **Rules:** `summarize_open_hub_type` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AX = acct(f"Gone {TAG}"), but closed.
2. AH = acct(f"Half {TAG}"), but half-closed.
3. N1 = inv.
4. N2 = inv, but `account_id AX.id`.
5. N3 = inv, but `account_id AH.id`.

**When**
- `result = dao.summarize_open_hub_type(db, workspace_id=W1.id, invoice_type="payable")`.

**Then**
1. returns: `result == (1, Decimal("100.00"), 0, 1)`.

### AIV-HS-06 — several invoices of one account count it once
- **Rules:** `summarize_open_hub_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. AB = acct(f"Bravo {TAG}").
2. N1 = inv.
3. N2 = inv.
4. N3 = inv.
5. N4 = inv, but `account_id AB.id`.

**When**
- `result = dao.summarize_open_hub_type(db, workspace_id=W1.id, invoice_type="payable")`.

**Then**
1. returns: `result[0] == 4`.
2. returns: `result[3] == 2`.

### AIV-HS-07 — a draft is not counted
- **Rules:** `summarize_open_hub_type` R1 [BUG-634]
- **Kind:** bug
- **Expect:** xfail BUG-634
- **Fails today on:** Then 1 (the draft is counted)

**Given**
1. N1 = inv.
2. N2 = inv, but draft, `invoice_amount Decimal("50.00")`.

**When**
- `result = dao.summarize_open_hub_type(db, workspace_id=W1.id, invoice_type="payable")`.

**Then**
1. returns: `result == (1, Decimal("100.00"), 0, 1)`.

### AIV-HS-08 — overdue counts open invoices due before today
- **Rules:** `summarize_open_hub_type` R3 [BUG-635]
- **Kind:** bug
- **Expect:** xfail BUG-635
- **Fails today on:** Then 1 (the call raises TypeError: no `today` parameter yet; without it the count reads a stored "overdue" status, which is 0)

**Given**
1. N1 = inv, but `due_date PASTDUE`.
2. N2 = inv, but `due_date FARDUE`.
3. N3 = inv.

**When**
- `result = dao.summarize_open_hub_type(db, workspace_id=W1.id, invoice_type="payable", today=TD)`.

**Then**
1. returns: `result[0] == 3`.
2. returns: `result[2] == 1`.

### AIV-HS-09 — W0's and W2's open invoices are not counted
- **Rules:** `summarize_open_hub_type` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = inv of W0.
2. N1 = inv, but `invoice_amount Decimal("10.00")`.
3. X2 = inv of W2.

**When**
- `result = dao.summarize_open_hub_type(db, workspace_id=W1.id, invoice_type="payable")`.

**Then**
1. returns: `result == (1, Decimal("10.00"), 0, 1)`.

### AIV-HS-10 — a W1 invoice on W2's account is not counted
- **Rules:** `summarize_open_hub_type` R1; `_build_filtered_query` R2a [BUG-2690]
- **Kind:** bug
- **Expect:** xfail BUG-2690
- **Fails today on:** Then 1 (the invoice on the foreign account is counted)

**Given**
1. N1 = inv, but `invoice_amount Decimal("10.00")`.
2. X = inv, but `account_id AC2.id`, `invoice_amount Decimal("40.00")`.

**When**
- `result = dao.summarize_open_hub_type(db, workspace_id=W1.id, invoice_type="payable")`.

**Then**
1. returns: `result == (1, Decimal("10.00"), 0, 1)`.

### AIV-HS-11 — a W1 invoice on W0's account is not counted
- **Rules:** `summarize_open_hub_type` R1; `_build_filtered_query` R2a [BUG-2690]
- **Kind:** bug
- **Expect:** xfail BUG-2690
- **Fails today on:** Then 1 (the invoice on the foreign account is counted)

**Given**
1. N1 = inv, but `invoice_amount Decimal("10.00")`.
2. X = inv, but `account_id AC0.id`, `invoice_amount Decimal("40.00")`.

**When**
- `result = dao.summarize_open_hub_type(db, workspace_id=W1.id, invoice_type="payable")`.

**Then**
1. returns: `result == (1, Decimal("10.00"), 0, 1)`.

### AIV-HS-12 — the sum adds stored half-up amounts: 33.335 and 0.005 give 33.35
- **Rules:** `summarize_open_hub_type` R2 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_amount Decimal("33.335")`.
2. N2 = inv, but `invoice_amount Decimal("0.005")`.

**When**
- `result = dao.summarize_open_hub_type(db, workspace_id=W1.id, invoice_type="payable")`.

**Then**
1. returns: `result[1] == Decimal("33.35")`.

### AIV-HS-13 — the KPI query takes no row lock
- **Rules:** `summarize_open_hub_type` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. N1 = inv.
2. `db.expunge_all()`.

**When**
- Statement recorder on: `result = dao.summarize_open_hub_type(db, workspace_id=W1.id, invoice_type="payable")`; `sql` = the SELECT from `account_invoices`.

**Then**
1. returns: `result[0] == 1`.
2. returns: `"FOR UPDATE" not in sql`.
3. returns: `written == []`.

### AIV-HS-14 — the KPI: overdue day boundary, due the day before today counts, due today or tomorrow does not
- **Rules:** `summarize_open_hub_type` R3 [BUG-635]
- **Kind:** bug
- **Expect:** xfail BUG-635
- **Fails today on:** Then 1 (the call raises TypeError: `summarize_open_hub_type` has no `today` parameter yet)

**Given**
1. N1 = inv, but `due_date TDM1`.
2. N2 = inv, but `due_date TD`.
3. N3 = inv, but `due_date TDP1`.
4. N4 = inv.
5. N5 = inv, but partial(`Decimal("10.00")`), `due_date TDM1`.

**When**
- `result = dao.summarize_open_hub_type(db, workspace_id=W1.id, invoice_type="payable", today=TD)`.

**Then**
1. returns: `result[0] == 5`.
2. returns: `result[2] == 2`.

## `AccountInvoiceDAO.count_accounts_with_any_open_balance`

### AIV-CA-01 — an account open on both types counts once
- **Rules:** `count_accounts_with_any_open_balance` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. AB = acct(f"Bravo {TAG}").
2. N1 = inv.
3. N2 = inv, but `invoice_type "receivable"`.
4. N3 = inv, but `account_id AB.id`.
5. N4 = inv, but `account_id AB.id`, partial(`Decimal("1.00")`).

**When**
- `result = dao.count_accounts_with_any_open_balance(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 2`.

### AIV-CA-02 — no open invoice gives 0, an int
- **Rules:** `count_accounts_with_any_open_balance` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = dao.count_accounts_with_any_open_balance(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 0`.
2. returns: `type(result) is int`.

### AIV-CA-03 — an inactive account counts, a closed one does not
- **Rules:** `count_accounts_with_any_open_balance` R1; `_build_filtered_query` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AI = acct(f"Idle {TAG}"), but inactive.
2. AX = acct(f"Gone {TAG}"), but closed.
3. N1 = inv, but `account_id AI.id`.
4. N2 = inv, but `account_id AX.id`.

**When**
- `result = dao.count_accounts_with_any_open_balance(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.

### AIV-CA-04 — accounts with only paid or voided invoices do not count
- **Rules:** `count_accounts_with_any_open_balance` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. AB = acct(f"Bravo {TAG}").
2. AD = acct(f"Delta {TAG}").
3. N1 = inv, but paid.
4. N2 = inv, but `account_id AB.id`, voided.
5. N3 = inv, but `account_id AD.id`.

**When**
- `result = dao.count_accounts_with_any_open_balance(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.

### AIV-CA-05 — an account with only a draft does not count
- **Rules:** `count_accounts_with_any_open_balance` R1; `_build_filtered_query` R12 [BUG-634]
- **Kind:** bug
- **Expect:** xfail BUG-634
- **Fails today on:** Then 1 (the draft makes the account count)

**Given**
1. N1 = inv, but draft.

**When**
- `result = dao.count_accounts_with_any_open_balance(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 0`.

### AIV-CA-06 — W0's and W2's accounts do not count for W1
- **Rules:** `count_accounts_with_any_open_balance` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = inv of W0.
2. N1 = inv.
3. X2 = inv of W2.

**When**
- `result = dao.count_accounts_with_any_open_balance(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.

### AIV-CA-07 — a W1 invoice on W2's account does not make that account count
- **Rules:** `count_accounts_with_any_open_balance` R1; `_build_filtered_query` R2a [BUG-2690]
- **Kind:** bug
- **Expect:** xfail BUG-2690
- **Fails today on:** Then 1 (the foreign account is counted)

**Given**
1. N1 = inv.
2. X = inv, but `account_id AC2.id`.

**When**
- `result = dao.count_accounts_with_any_open_balance(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.

## `AccountInvoiceDAO.summarize_invoices`

*Every card here except SI-14 / SI-15 passes `invoice_type="payable"` and holds payable rows only, and checks `result[:4]` or single positions — the count and the payable triple, both today and after BUG-2692. No card here checks the tuple length or the receivable triple; R5 (the split) has its own section below.*

### AIV-SI-01 — count of all, exact money totals of the non-voided
- **Rules:** `summarize_invoices` R1, R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_amount Decimal("100.05")`.
2. N2 = inv, but `invoice_amount Decimal("0.10")`, partial(`Decimal("0.05")`).
3. N3 = inv, but `invoice_amount Decimal("0.20")`, paid.
4. N4 = inv, but `invoice_amount Decimal("70.00")`, voided.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id, invoice_type="payable")`.

**Then**
1. returns: `result[0] == 4`.
2. returns: `result[1] == Decimal("100.35")`.
3. returns: `result[2] == Decimal("0.25")`.
4. returns: `result[3] == Decimal("100.10")`.

### AIV-SI-02 — nothing matching gives a zero count and three Decimal zeros
- **Rules:** `summarize_invoices` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id, invoice_type="payable")`.

**Then**
1. returns: `result[:4] == (0, Decimal("0"), Decimal("0"), Decimal("0"))`.
2. returns: `isinstance(result[1], Decimal)`, `isinstance(result[2], Decimal)`, `isinstance(result[3], Decimal)`.

### AIV-SI-03 — only a voided invoice: counted, but every total is zero
- **Rules:** `summarize_invoices` R2, R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but voided.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id, invoice_type="payable")`.

**Then**
1. returns: `result[:4] == (1, Decimal("0"), Decimal("0"), Decimal("0"))`.

### AIV-SI-04 — an overpaid invoice lowers the outstanding total
- **Rules:** `summarize_invoices` R3; `_outstanding_amount_expr` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_amount Decimal("10.00")`, `paid_amount Decimal("15.00")`, `payment_status "paid"`.
2. N2 = inv.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id, invoice_type="payable")`.

**Then**
1. returns: `result[:4] == (2, Decimal("110.00"), Decimal("15.00"), Decimal("95.00"))`.

### AIV-SI-05 — account_id keeps one account, with accounts of lower and higher id
- **Rules:** `summarize_invoices` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. AL = acct(f"Lima {TAG}").
2. AM = acct(f"Mike {TAG}").
3. AN = acct(f"Nova {TAG}").
4. N1 = inv, but `account_id AL.id`, `invoice_amount Decimal("1.00")`.
5. N2 = inv, but `account_id AM.id`, `invoice_amount Decimal("2.00")`.
6. N3 = inv, but `account_id AN.id`, `invoice_amount Decimal("4.00")`.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AM.id, invoice_type="payable")`.

**Then**
1. returns: `result[:4] == (1, Decimal("2.00"), Decimal("0.00"), Decimal("2.00"))`.

### AIV-SI-06 — drafts are counted in invoice_count
- **Rules:** `summarize_invoices` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv, but draft.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id, invoice_type="payable")`.

**Then**
1. returns: `result[0] == 2`.

### AIV-SI-07 — drafts add nothing to the money totals
- **Rules:** `summarize_invoices` R3 [BUG-634]
- **Kind:** bug
- **Expect:** xfail BUG-634
- **Fails today on:** Then 2 (the draft's amount is summed)

**Given**
1. N1 = inv.
2. N2 = inv, but draft, `invoice_amount Decimal("50.00")`.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id, invoice_type="payable")`.

**Then**
1. returns: `result[0] == 2`.
2. returns: `result[1] == Decimal("100.00")`.
3. returns: `result[3] == Decimal("100.00")`.

### AIV-SI-08 — W0's and W2's invoices are not summed
- **Rules:** `summarize_invoices` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = inv of W0.
2. N1 = inv, but `invoice_amount Decimal("10.00")`.
3. X2 = inv of W2.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, invoice_type="payable")`.

**Then**
1. returns: `result[:4] == (1, Decimal("10.00"), Decimal("0.00"), Decimal("10.00"))`.

### AIV-SI-09 — a W1 invoice placed on W2's account is not summed for that account
- **Rules:** `summarize_invoices` R1; `_build_filtered_query` R2a [BUG-2690]
- **Kind:** bug
- **Expect:** xfail BUG-2690
- **Fails today on:** Then 1 (the invoice on the foreign account is summed)

**Given**
1. N1 = inv.
2. X = inv, but `account_id AC2.id`.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC2.id, invoice_type="payable")`.

**Then**
1. returns: `result[:4] == (0, Decimal("0"), Decimal("0"), Decimal("0"))`.

### AIV-SI-10 — a closed account's invoices are not summed
- **Rules:** `summarize_invoices` R1; `_build_filtered_query` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AX = acct(f"Gone {TAG}"), but closed.
2. N1 = inv, but `account_id AX.id`.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AX.id, invoice_type="payable")`.

**Then**
1. returns: `result[:4] == (0, Decimal("0"), Decimal("0"), Decimal("0"))`.

### AIV-SI-11 — other filters are passed through: the number search
- **Rules:** `summarize_invoices` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_number "INV-Alpha-1"`, `invoice_amount Decimal("11.00")`.
2. N2 = inv, but `invoice_number "INV-Beta-2"`, `invoice_amount Decimal("22.00")`.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id, invoice_type="payable", invoice_number_search="alpha")`.

**Then**
1. returns: `result[:4] == (1, Decimal("11.00"), Decimal("0.00"), Decimal("11.00"))`.

### AIV-SI-12 — totals add stored half-up amounts: 33.335 and 0.005 give 33.35
- **Rules:** `summarize_invoices` R3 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_amount Decimal("33.335")`.
2. N2 = inv, but `invoice_amount Decimal("0.005")`.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id, invoice_type="payable")`.

**Then**
1. returns: `result[1] == Decimal("33.35")`.
2. returns: `result[3] == Decimal("33.35")`.

### AIV-SI-13 — the summary query takes no row lock
- **Rules:** `summarize_invoices` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. N1 = inv.
2. `db.expunge_all()`.

**When**
- Statement recorder on: `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id, invoice_type="payable")`; `sql` = the SELECT from `account_invoices`.

**Then**
1. returns: `result[0] == 1`.
2. returns: `"FOR UPDATE" not in sql`.
3. returns: `written == []`.

### AIV-SI-14 — with no type, invoice_count counts payables and receivables together
- **Rules:** `summarize_invoices` R2, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_amount Decimal("1000.00")`.
2. N2 = inv, but `invoice_type "receivable"`, `invoice_amount Decimal("200.00")`.
3. N3 = inv, but `invoice_type "receivable"`, voided.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id)`.

**Then**
1. returns: `result[0] == 3`.

### AIV-SI-15 — with invoice_type "receivable", invoice_count counts the receivables only
- **Rules:** `summarize_invoices` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_amount Decimal("1000.00")`.
2. N2 = inv, but `invoice_type "receivable"`, `invoice_amount Decimal("200.00")`.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id, invoice_type="receivable")`.

**Then**
1. returns: `result[0] == 1`.

## `AccountInvoiceDAO.update_paid_amount`

### AIV-UP-01 — a first payment is added, the row flushed and marked partial
- **Rules:** `update_paid_amount` R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. N = inv.

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("20.50"))`.

**Then**
1. returns: `result.id == N.id`.
2. returns: `result.payment_status == "partial"`.
3. session: `db.scalar(text("SELECT paid_amount FROM account_invoices WHERE id = :i"), {"i": N.id}) == Decimal("20.50")` (flushed, read before any expire).
4. re-read N: `paid_amount == Decimal("20.50")`, `payment_status == "partial"`.

### AIV-UP-02 — a payment adds to what was already paid
- **Rules:** `update_paid_amount` R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. N = inv, but partial(`Decimal("30.00")`).

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("20.50"))`.

**Then**
1. returns: `result.payment_status == "partial"`.
2. re-read N: `paid_amount == Decimal("50.50")`, `payment_status == "partial"`.

### AIV-UP-03 — paying exactly the rest marks the invoice paid
- **Rules:** `update_paid_amount` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv, but partial(`Decimal("60.00")`).

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("40.00"))`.

**Then**
1. returns: `result.payment_status == "paid"`.
2. re-read N: `paid_amount == Decimal("100.00")`, `payment_status == "paid"`.

### AIV-UP-04 — one cent short of the amount stays partial
- **Rules:** `update_paid_amount` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv, but partial(`Decimal("60.00")`).

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("39.99"))`.

**Then**
1. returns: `result.payment_status == "partial"`.
2. re-read N: `paid_amount == Decimal("99.99")`, `payment_status == "partial"`.

### AIV-UP-05 — paying more than the rest is stored and marks the invoice paid
- **Rules:** `update_paid_amount` R3, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv, but partial(`Decimal("60.00")`).

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("40.01"))`.

**Then**
1. returns: `result.payment_status == "paid"`.
2. re-read N: `paid_amount == Decimal("100.01")`, `payment_status == "paid"`.

### AIV-UP-06 — a zero payment on a 0.00 invoice marks it paid
- **Rules:** `update_paid_amount` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv, but `invoice_amount Decimal("0.00")`.

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("0"))`.

**Then**
1. returns: `result.payment_status == "paid"`.
2. re-read N: `paid_amount == Decimal("0.00")`, `payment_status == "paid"`.

### AIV-UP-07 — a zero payment on an unpaid invoice leaves the status as it was
- **Rules:** `update_paid_amount` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv.

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("0"))`.

**Then**
1. returns: `result.payment_status == "unpaid"`.
2. re-read N: `paid_amount == Decimal("0.00")`, `payment_status == "unpaid"`.

### AIV-UP-08 — a negative payment back to zero on a paid invoice keeps "paid"
- **Rules:** `update_paid_amount` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv, but paid.

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("-100"))`.

**Then**
1. returns: `result.payment_status == "paid"`.
2. re-read N: `paid_amount == Decimal("0.00")`, `payment_status == "paid"`.

### AIV-UP-09 — a negative payment back to zero on a partial invoice keeps "partial"
- **Rules:** `update_paid_amount` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv, but partial(`Decimal("30.00")`).

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("-30.00"))`.

**Then**
1. returns: `result.payment_status == "partial"`.
2. re-read N: `paid_amount == Decimal("0.00")`, `payment_status == "partial"`.

### AIV-UP-10 — the status is decided on the unrounded sum: 999.995 stays partial, stored 1000.00
- **Rules:** `update_paid_amount` R2, R6 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv, but `invoice_amount Decimal("1000.00")`.

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("999.995"))`.

**Then**
1. returns: `result.paid_amount == Decimal("999.995")`.
2. returns: `result.payment_status == "partial"`.
3. re-read N: `paid_amount == Decimal("1000.00")`, `payment_status == "partial"`.

### AIV-UP-11 — 10.00 plus 0.005 is stored as 10.01 (half up, not half to even)
- **Rules:** `update_paid_amount` R2 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv, but partial(`Decimal("10.00")`).

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("0.005"))`.

**Then**
1. returns: `result.payment_status == "partial"`.
2. re-read N: `paid_amount == Decimal("10.01")`.

### AIV-UP-12 — 2.125 is stored as 2.13 (half up, not half to even)
- **Rules:** `update_paid_amount` R2 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv.

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("2.125"))`.

**Then**
1. returns: `result.payment_status == "partial"`.
2. re-read N: `paid_amount == Decimal("2.13")`.

### AIV-UP-13 — 2.124 is stored as 2.12 (the control)
- **Rules:** `update_paid_amount` R2 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv.

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("2.124"))`.

**Then**
1. returns: `result.payment_status == "partial"`.
2. re-read N: `paid_amount == Decimal("2.12")`.

### AIV-UP-14 — -1.005 is stored as -1.01 (half away from zero), the status kept
- **Rules:** `update_paid_amount` R2, R5 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv.

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("-1.005"))`.

**Then**
1. returns: `result.payment_status == "unpaid"`.
2. re-read N: `paid_amount == Decimal("-1.01")`, `payment_status == "unpaid"`.

### AIV-UP-15 — an unknown id returns None and writes nothing
- **Rules:** `update_paid_amount` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. N = inv.

**When**
- `result = dao.update_paid_amount(db, invoice_id=MISSING, workspace_id=W1.id, additional_payment=Decimal("10.00"))`.

**Then**
1. returns: `result is None`.
2. session: `not db.dirty`, `not db.new`.
3. unchanged: unchanged(N).

### AIV-UP-16 — W0's invoice asked from W1 returns None and is not touched
- **Rules:** `update_paid_amount` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = inv of W0.
2. N = inv.
3. X2 = inv of W2.

**When**
- `result = dao.update_paid_amount(db, invoice_id=X0.id, workspace_id=W1.id, additional_payment=Decimal("10.00"))`.

**Then**
1. returns: `result is None`.
2. session: `not db.dirty`.
3. re-read X0: `paid_amount == Decimal("0.00")`, `payment_status == "unpaid"`.

### AIV-UP-17 — W2's invoice asked from W1 returns None and is not touched
- **Rules:** `update_paid_amount` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = inv of W0.
2. N = inv.
3. X2 = inv of W2.

**When**
- `result = dao.update_paid_amount(db, invoice_id=X2.id, workspace_id=W1.id, additional_payment=Decimal("10.00"))`.

**Then**
1. returns: `result is None`.
2. session: `not db.dirty`.
3. re-read X2: `paid_amount == Decimal("0.00")`, `payment_status == "unpaid"`.

### AIV-UP-18 — only the named invoice changes, not its neighbours of lower and higher id
- **Rules:** `update_paid_amount` R2, R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. N1 = inv.
2. N2 = inv.
3. N3 = inv.

**When**
- `result = dao.update_paid_amount(db, invoice_id=N2.id, workspace_id=W1.id, additional_payment=Decimal("5.00"))`.

**Then**
1. returns: `result.id == N2.id`.
2. re-read N1: `paid_amount == Decimal("0.00")`, `payment_status == "unpaid"`.
3. re-read N3: `paid_amount == Decimal("0.00")`, `payment_status == "unpaid"`.
4. re-read N2: `paid_amount == Decimal("5.00")`.

### AIV-UP-19 — a voided invoice is updated too
- **Rules:** `update_paid_amount` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv, but voided.

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("10.00"))`.

**Then**
1. returns: `result.payment_status == "partial"`.
2. re-read N: `paid_amount == Decimal("10.00")`, `payment_status == "partial"`, `invoice_status == "voided"`.

### AIV-UP-20 — allow_payments False is not looked at
- **Rules:** `update_paid_amount` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv, but `allow_payments False`, `payment_locked_reason "Disputed"`.

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("10.00"))`.

**Then**
1. returns: `result.payment_status == "partial"`.
2. re-read N: `paid_amount == Decimal("10.00")`, `allow_payments is False`.

### AIV-UP-21 — no other field is written: updated_by, amount, status, notes stay
- **Rules:** `update_paid_amount` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. N = inv, but `updated_by U2.id`, `notes "keep"`, `invoice_number "INV-7"`.

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("10.00"))`.

**Then**
1. returns: `result.id == N.id`.
2. re-read N: `updated_by == U2.id`, `notes == "keep"`, `invoice_number == "INV-7"`.
3. re-read N: `invoice_amount == Decimal("100.00")`, `invoice_status == "confirmed"`, `invoice_type == "payable"`.
4. re-read N: `updated_at is not None`.

### AIV-UP-22 — one UPDATE of the invoice and no row lock of its own
- **Rules:** `update_paid_amount` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. N = inv.
2. `db.expunge_all()`.

**When**
- Statement recorder on: `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("10.00"))`; `sql` = the SELECT from `account_invoices`.

**Then**
1. returns: `result.id == N.id`.
2. returns: `"FOR UPDATE" not in sql`.
3. returns: `len(written) == 1`.
4. returns: `written[0].startswith("UPDATE account_invoices")`.

### AIV-UP-23 — the caller's locked row is the one updated and returned
- **Rules:** `update_paid_amount` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. N = inv.
2. `L = db.execute(select(AccountInvoice).where(AccountInvoice.id == N.id).with_for_update()).scalar_one()`.

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("10.00"))`.

**Then**
1. returns: `result is L`.
2. re-read N: `paid_amount == Decimal("10.00")`.

### AIV-UP-24 — positional arguments raise TypeError, nothing written
- **Rules:** `update_paid_amount` R8
- **Kind:** error
- **Expect:** pass

**Given**
1. N = inv.

**When**
- `dao.update_paid_amount(db, N.id, W1.id, Decimal("10.00"))`.

**Then**
1. raises: `TypeError`.
2. session: `not db.dirty`.
3. re-read N: `paid_amount == Decimal("0.00")`.

### AIV-UP-25 — flushes but never commits
- **Rules:** `update_paid_amount` R2 (Overview: never commits)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. N = inv.

**When**
- commit spy: `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("10.00"))`.

**Then**
1. returns (inside the savepoint): `result.payment_status == "partial"`.
2. mock called (inside the savepoint): `cm.call_count == 0`.
3. re-read N (after the savepoint rollback): `paid_amount == Decimal("0.00")`, `payment_status == "unpaid"`.

### AIV-UP-26 — a 0.01 payment on an unpaid invoice marks it partial
- **Rules:** `update_paid_amount` R2, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = inv.

**When**
- `result = dao.update_paid_amount(db, invoice_id=N.id, workspace_id=W1.id, additional_payment=Decimal("0.01"))`.

**Then**
1. returns: `result.id == N.id`.
2. returns: `result.payment_status == "partial"`.
3. re-read N: `paid_amount == Decimal("0.01")`, `payment_status == "partial"`.

## `summarize_invoices` R5 — split by invoice type (BUG-2692)

*The owner answered OQ-41 (2026-11-11): money is never added across invoice types. The result is `(invoice_count, payable_invoiced, payable_paid, payable_outstanding, receivable_invoiced, receivable_paid, receivable_outstanding)`, one shape whether or not `invoice_type` is given; the type not asked for sums to `Decimal` 0. Today it is a 4-tuple summed over the whole selection. The count (SI-14, SI-15) and, with `invoice_type="payable"`, the first four positions (OQ41-03) hold both ways and are pass cards.*

### AIV-OQ41-01 — with no type, a 1,000.00 payable and a 200.00 receivable are two separate triples
- **Rules:** `summarize_invoices` R5 [BUG-2692]
- **Kind:** bug
- **Expect:** xfail BUG-2692
- **Fails today on:** Then 2 (the result is a 4-tuple with one triple of 1200.00)

**Given**
1. N1 = inv, but `invoice_amount Decimal("1000.00")`.
2. N2 = inv, but `invoice_type "receivable"`, `invoice_amount Decimal("200.00")`.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id)`.

**Then**
1. returns: `result[0] == 2`.
2. returns: `len(result) == 7`.
3. returns: `result[1:4] == (Decimal("1000.00"), Decimal("0.00"), Decimal("1000.00"))`.
4. returns: `result[4:7] == (Decimal("200.00"), Decimal("0.00"), Decimal("200.00"))`.

### AIV-OQ41-02 — with no type, paid amounts stay on their own side too
- **Rules:** `summarize_invoices` R5 [BUG-2692]
- **Kind:** bug
- **Expect:** xfail BUG-2692
- **Fails today on:** Then 2 (the result is a 4-tuple; paid 450.00 is summed across both types)

**Given**
1. N1 = inv, but `invoice_amount Decimal("1000.00")`, partial(`Decimal("400.00")`).
2. N2 = inv, but `invoice_type "receivable"`, `invoice_amount Decimal("200.00")`, partial(`Decimal("50.00")`).

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id)`.

**Then**
1. returns: `result[0] == 2`.
2. returns: `len(result) == 7`.
3. returns: `result[1:4] == (Decimal("1000.00"), Decimal("400.00"), Decimal("600.00"))`.
4. returns: `result[4:7] == (Decimal("200.00"), Decimal("50.00"), Decimal("150.00"))`.

### AIV-OQ41-03 — with invoice_type "payable", the count and the payable triple are the first four values
- **Rules:** `summarize_invoices` R5 [BUG-2692] (the part that holds before and after the fix)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N1 = inv, but `invoice_amount Decimal("1000.00")`, partial(`Decimal("400.00")`).
2. N2 = inv, but `invoice_type "receivable"`, `invoice_amount Decimal("200.00")`, partial(`Decimal("50.00")`).

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id, invoice_type="payable")`.

**Then**
1. returns: `result[:4] == (1, Decimal("1000.00"), Decimal("400.00"), Decimal("600.00"))`.

### AIV-OQ41-04 — with invoice_type "receivable", the payable triple is zero and the receivable triple holds the sums
- **Rules:** `summarize_invoices` R4, R5 [BUG-2692]
- **Kind:** bug
- **Expect:** xfail BUG-2692
- **Fails today on:** Then 2 (today positions 1–3 hold the receivable sums 200.00, 50.00, 150.00)

**Given**
1. N1 = inv, but `invoice_amount Decimal("1000.00")`, partial(`Decimal("400.00")`).
2. N2 = inv, but `invoice_type "receivable"`, `invoice_amount Decimal("200.00")`, partial(`Decimal("50.00")`).

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id, invoice_type="receivable")`.

**Then**
1. returns: `result[0] == 1`.
2. returns: `result[1:4] == (Decimal("0"), Decimal("0"), Decimal("0"))`.
3. returns: `result[4:7] == (Decimal("200.00"), Decimal("50.00"), Decimal("150.00"))`.

### AIV-OQ41-05 — with invoice_type "payable", the receivable triple is three Decimal zeros
- **Rules:** `summarize_invoices` R4, R5 [BUG-2692]
- **Kind:** bug
- **Expect:** xfail BUG-2692
- **Fails today on:** Then 2 (the result has only four values, so `result[4:7]` is empty)

**Given**
1. N1 = inv, but `invoice_amount Decimal("1000.00")`.
2. N2 = inv, but `invoice_type "receivable"`, `invoice_amount Decimal("200.00")`.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id, invoice_type="payable")`.

**Then**
1. returns: `result[:4] == (1, Decimal("1000.00"), Decimal("0.00"), Decimal("1000.00"))`.
2. returns: `result[4:7] == (Decimal("0"), Decimal("0"), Decimal("0"))`.
3. returns: `isinstance(result[4], Decimal)`.

### AIV-OQ41-06 — each triple is an exact Decimal sum of stored half-up amounts
- **Rules:** `summarize_invoices` R3, R5 [BUG-2692] (HR-15)
- **Kind:** bug
- **Expect:** xfail BUG-2692
- **Fails today on:** Then 2 (the result is a 4-tuple summed across both types)

**Given**
1. N1 = inv, but `invoice_amount Decimal("0.10")`, partial(`Decimal("0.05")`).
2. N2 = inv, but `invoice_amount Decimal("0.20")`.
3. N3 = inv, but `invoice_type "receivable"`, `invoice_amount Decimal("33.335")`.
4. N4 = inv, but `invoice_type "receivable"`, `invoice_amount Decimal("0.005")`.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id)`.

**Then**
1. returns: `result[0] == 4`.
2. returns: `len(result) == 7`.
3. returns: `result[1:4] == (Decimal("0.30"), Decimal("0.05"), Decimal("0.25"))`.
4. returns: `result[4:7] == (Decimal("33.35"), Decimal("0.00"), Decimal("33.35"))`.

### AIV-OQ41-07 — voided invoices of either type are counted but add nothing to their own triple
- **Rules:** `summarize_invoices` R2, R3, R5 [BUG-2692]
- **Kind:** bug
- **Expect:** xfail BUG-2692
- **Fails today on:** Then 2 (the result is a 4-tuple summed across both types)

**Given**
1. N1 = inv.
2. N2 = inv, but `invoice_amount Decimal("70.00")`, voided.
3. N3 = inv, but `invoice_type "receivable"`, `invoice_amount Decimal("40.00")`.
4. N4 = inv, but `invoice_type "receivable"`, `invoice_amount Decimal("25.00")`, voided.

**When**
- `result = dao.summarize_invoices(db, workspace_id=W1.id, account_id=AC1.id)`.

**Then**
1. returns: `result[0] == 4`.
2. returns: `len(result) == 7`.
3. returns: `result[1:4] == (Decimal("100.00"), Decimal("0.00"), Decimal("100.00"))`.
4. returns: `result[4:7] == (Decimal("40.00"), Decimal("0.00"), Decimal("40.00"))`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `update_paid_amount` R7 (lock is the caller's) / HR-10 | `InvoicePaymentManager.create_payment`; integration test | `create_payment` locks the invoice `FOR UPDATE` before calling here; the real two-session race. |
| BUG-604 (more than 2 decimals reach `update_paid_amount`) | payment schema (`InvoicePaymentCreate`) | Amounts with more than 2 decimals are refused or rounded half up before the DAO. |
| BUG-635: where `today` comes from | `AccountInvoiceManager` (manager cases patch `app.managers.account_invoice_manager.utcnow`) | The manager passes `today=utcnow().date()` to every overdue-aware DAO call (list filter, hub flag, KPI). The DAO day boundary itself is covered here (FQ-44, AH-33, AH-34, HS-14). |
| FU-1 (BUG-2690 wording in the manager spec) | `tests/unit/managers/account_invoice_manager.spec.md` | The manager's shared filter rules name BUG-2690; one HR-16 card there if wanted. |
| FU-2 / BUG-2692 response shape | `AccountInvoiceManager.summarize_invoices`, `AccountInvoiceService`, `GET /accounts/{id}/invoice-summary/`, `AccountInvoiceSummaryResponse` | The endpoint takes the 7-tuple; the response has `invoice_count` and the six `payable_*` / `receivable_*` totals, no combined fields. |
| BUG-624 (`order_type` free text) | schema / `AccountInvoiceManager` | `order_type` limited to the four names; ON-10 here pins only that a different spelling does not match. |
| HR-7 (`limit >= 1`) | endpoints `GET /invoices/`, `/accounts/hub/`, `/accounts/{id}/open-invoices/`, `/accounts/{id}/invoices/` | 422 on `limit=0`. |

## Spec gaps
Revision-1 gaps 1 ("today" after BUG-635) and 2 (what a real void writes) are closed by the spec's Gap log (G1, G2, 2026-11-11).

| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 3 | Overview *Externals* (G1), the eight methods that gain `today` | Whether the new `today` keyword is required or has a default. | Not blocking. Pass cards cannot pass `today` (it does not exist yet), so they call without it. If the fix makes `today` required, every pass card on those eight methods raises TypeError and must gain `today=TD`. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_escape_ilike` | R1 | ES-01, ES-02, ES-03, ES-04 |
| `_invoice_number_search_ilike_term` | R1 | ST-01, ST-04, ST-05, FQ-28 |
| `_invoice_number_search_ilike_term` | R2 | ST-01, ST-02, ST-03 |
| `_outstanding_amount_expr` | R1 | OE-01, OE-02, OE-03, HS-01, SI-04 |
| `_order_number_search_conditions` | R1 | ON-01, ON-02, ON-03, ON-04, ON-05, ON-06, ON-07, ON-08, ON-09, ON-11, ON-18 |
| `_order_number_search_conditions` | R2 | ON-17, ON-19 |
| `_order_number_search_conditions` | R3 | ON-10 |
| `_order_number_search_conditions` | R4 [BUG-2691] | ON-12, ON-13, ON-14, ON-15, ON-16 |
| `_build_filtered_query` | R1 | FQ-01, FQ-02, FQ-03, LP-07, LP-08, PF-16 |
| `_build_filtered_query` | R2 | FQ-04, FQ-05, LI-05, CA-03, SI-10 |
| `_build_filtered_query` | R2a [BUG-2690] | FQ-06, FQ-07, FQ-08, LP-09, PF-17, HS-10, HS-11, CA-07, SI-09 |
| `_build_filtered_query` | R3 | FQ-09 |
| `_build_filtered_query` | R4 | FQ-10, FQ-11 |
| `_build_filtered_query` | R5 | FQ-12, FQ-13, FQ-14, FQ-15, FQ-16, FQ-17, FQ-18 |
| `_build_filtered_query` | R5a [BUG-635] | FQ-19, FQ-44 |
| `_build_filtered_query` | R6 | FQ-20 |
| `_build_filtered_query` | R7 | FQ-21, FQ-22 |
| `_build_filtered_query` | R8 | FQ-23, FQ-24, FQ-25 |
| `_build_filtered_query` | R9 | ON-01, ON-16, ON-18, FQ-26, FQ-27, FQ-28, FQ-29, FQ-30, FQ-31, FQ-32 |
| `_build_filtered_query` | R9a [BUG-637] | FQ-33, FQ-34 |
| `_build_filtered_query` | R10 [BUG-622] | FQ-35, FQ-36, FQ-37 |
| `_build_filtered_query` | R11 [BUG-622] | FQ-08, FQ-38, FQ-39, FQ-40, FQ-41, FQ-42 |
| `_build_filtered_query` | R12 [BUG-634] | LP-02, LP-03, PF-14, PF-15, PF-19, CA-05 |
| `_build_filtered_query` | R13 | FQ-43 |
| `list_invoices` | R1 | LI-01, LI-08 |
| `list_invoices` | R2 | LI-01, LI-07 |
| `list_invoices` | R3 | LI-02, LI-03, LI-04, LI-05, LI-06 |
| `list_invoices_page` | R1 | LP-01, LP-02, LP-03, LP-04, LP-05, LP-06, LP-07, LP-08, LP-09 |
| `_open_balance_subquery` | R1 [BUG-634] | AH-01, AH-02 |
| `_open_balance_subquery` | R1a [BUG-2690] | AH-12 |
| `_open_balance_subquery` | R2 [BUG-635] | AH-01, AH-03, AH-04, AH-33, AH-34 |
| `list_accounts_hub_page` | R1 [BUG-636] | AH-01, AH-05, AH-06, AH-07, AH-08, AH-09, AH-10, AH-11, AH-12, AH-32 |
| `list_accounts_hub_page` | R2 | AH-01, AH-10, AH-11 |
| `list_accounts_hub_page` | R3 | AH-13, AH-14, AH-15, AH-16, AH-17, AH-18, AH-31, AH-35 |
| `list_accounts_hub_page` | R4 [BUG-622] | AH-19, AH-20, AH-21, AH-22 |
| `list_accounts_hub_page` | R5 [BUG-623] | AH-23, AH-24, AH-25, AH-26, AH-27 |
| `list_accounts_hub_page` | R6 | AH-13, AH-14, AH-19, AH-28, AH-29, AH-30, AH-31 |
| `_reshape_accounts_hub_row` | R1 | RH-01 |
| `_reshape_accounts_hub_row` | R2 | RH-01, RH-02, RH-03, RH-04 |
| `summarize_open_hub_type` | R1 | HS-01, HS-02, HS-05, HS-07, HS-09, HS-10, HS-11, HS-13 |
| `summarize_open_hub_type` | R2 | HS-01, HS-02, HS-03, HS-06, HS-12 |
| `summarize_open_hub_type` | R3 [BUG-635] | HS-08, HS-14 |
| `summarize_open_hub_type` | R4 | HS-04 |
| `count_accounts_with_any_open_balance` | R1 | CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07 |
| `list_invoices_page_filtered` | R1 | LP-01, PF-01, PF-11, PF-12, PF-13, PF-14, PF-15, PF-16, PF-17, PF-19 |
| `list_invoices_page_filtered` | R2 | LP-01, LP-05, PF-01, PF-10, PF-11, PF-16, PF-17 |
| `list_invoices_page_filtered` | R3 | LP-06, PF-02, PF-03, PF-04, PF-05, PF-06, PF-07, PF-08, PF-18 |
| `list_invoices_page_filtered` | R4 | LP-04, LP-05, PF-01, PF-08, PF-09, PF-10 |
| `summarize_invoices` | R1 | SI-01, SI-05, SI-08, SI-09, SI-10, SI-11, SI-13, SI-15 |
| `summarize_invoices` | R2 | SI-01, SI-03, SI-06, SI-14, SI-15 |
| `summarize_invoices` | R3 | SI-01, SI-03, SI-04, SI-07, SI-12, OQ41-06 |
| `summarize_invoices` | R4 | SI-02, SI-03, OQ41-04, OQ41-05 |
| `summarize_invoices` | R5 [BUG-2692] | SI-14, OQ41-01, OQ41-02, OQ41-03, OQ41-04, OQ41-05, OQ41-06, OQ41-07 |
| `update_paid_amount` | R1 | UP-15, UP-16, UP-17 |
| `update_paid_amount` | R2 | UP-01, UP-02, UP-10, UP-11, UP-12, UP-13, UP-14, UP-18, UP-25, UP-26 |
| `update_paid_amount` | R3 | UP-03, UP-04, UP-05, UP-06 |
| `update_paid_amount` | R4 | UP-01, UP-02, UP-04, UP-26 |
| `update_paid_amount` | R5 | UP-07, UP-08, UP-09, UP-14 |
| `update_paid_amount` | R6 | UP-10 |
| `update_paid_amount` | R7 | UP-05, UP-19, UP-20, UP-22, UP-23 |
| `update_paid_amount` | R8 | UP-18, UP-21, UP-24 |
