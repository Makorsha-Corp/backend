# Execution notes — `app/dao/account_invoice.py`

> Cases: `tests/unit/dao/account_invoice.cases.md` (Revision 4, READY, 219 cases) · Tests: `tests/unit/dao/test_account_invoice.py` · Source commit: e48a092
> Result: **219 tests for 219 cases — 177 passed · 42 xfailed (strict bug xfails) · 0 discrepancies · 0 errors** — branch coverage 99% (134 statements, 46 branches; the one missed line is dead code).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_account_invoice.py -q -p no:cacheprovider -o addopts=""`

## Who wrote what
Normal mode, no local model (full Claude): every test sits below a `# [claude] <ID>` comment, in card order, and every numbered Then line is a `# Then N` comment directly before its assertions (before the `with pytest.raises(...)` line for UP-24). The three `Author: claude` cards (LI-02, LI-04, PF-10) use `invs(101)` / `invs(1001)` exactly as written; they take well under a second each.

## How the tests are built
- **Standing rows:** fixture `st` (class `Standing`) builds W0, W1, W2 (`make_workspace`), U1–U3 (`make_profile`), TAG (`uuid4().hex[:8]`), then AC0, AC1, AC2 (`Acme {TAG}` in W0, W1, W2), each flushed. Every test asks for `st`, including the pure-helper cards (ES, ST, RH), because the standing rows are part of every card.
- **Given builders:** `st.inv(**but)` = **inv** (W1, AC1); `st.inv0` / `st.inv2` = "inv of W0 / of W2". The Conventions' state words are keywords: `partial=p`, `paid=True` (paid amount = the final `invoice_amount`), `draft=True`, `voided=True` (void note, paid 0.00, unpaid, `updated_by` U1, `updated_at` T1 — what a real void writes). `st.acct(name, inactive= | closed= | half_closed=)`; FQ-08's W2 account uses `st._account(W2.id, …)`. `st.invs(n)` / `st.accts(n)` add n rows and flush once.
- **Orders** (`st.po`, `st.eo`, `st.so`, `st.wo`) are always built **unchecked** (`SET LOCAL session_replication_role = replica` … `origin`) because their status / type / factory / destination ids are MISSING. `of=0` / `of=2` = "of W0 / of W2"; `voided=True` = "voided order"; `deleted=True` = "deleted wo". Expense and sales numbers go through `GN(n)` (global unique indexes `ix_expense_orders_expense_number`, `ix_sales_orders_sales_order_number`); purchase and work order numbers are unique per workspace only, and the workspaces are new per test. `XID(k)` is used for ON-11's explicit purchase-order id and the polymorphic `order_id` values of LP-06 / PF-03 / PF-04 / PF-06 / PF-08.
- **Reading helpers (no expected values inside):** `st.reread(id)` (expire_all, then SELECT), `st.snap(id)` ("unchanged": every column after re-read), `ids`, `idset`, `hids`, `pay`, `rec`, `order_part(sql)`.
- **Statement recorder:** `before_cursor_execute` listener on the session's connection. `rec.sql(table)` / `rec.sql(table, ordered=True)` return the one SELECT reading that table (with an `ORDER BY`), and fail unless there is exactly one. Two cards name "the SELECT from `account_invoices`" for a method that sends several (`summarize_open_hub_type`: 4, `summarize_invoices`: 2): HS-13 and SI-13 check the no-lock line on **every** such SELECT (`rec.sqls`), which is at least as strict as the card. Cards that start the recorder end the Given with `db.expunge_all()` (Conventions); the ids and workspace ids they use later are read into locals before it.
- **Commit spy (UP-25):** `sp = db.begin_nested()`, `patch.object(db, "commit", wraps=db.commit)`, Then 1–2 inside the savepoint, `sp.rollback()`, Then 3 after.
- **Overdue cards (BUG-635)** pass `today=TD` (2031-06-15) as written; today the call raises `TypeError`, which is what every such card's "Fails today on" says. No clock is patched (Externals: none).
- **Sharing the test database with other runs:** nothing is committed; account names carry TAG; the only globally unique values (expense / sales numbers) carry the process id; explicit ids come from `XID(k)` (process id based, 800 000 000 range).

## xfail location (`--runxfail`)
Own plugin `failson_ai.py` plus checker `check_failson.py` (scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaoe\ai\`). With `--runxfail`: 42 failed, 177 passed. **All 42 strict bug xfails fail where their card says** (checker: `BAD: 0 cards: 42`):

| Fails at | Cards |
|---|---|
| the When call, `TypeError` (no `today` parameter) — card: "Then 1 (the call raises TypeError)" | FQ-19, FQ-44, AH-03, AH-33, AH-34, HS-08, HS-14 |
| the When call, `ValueError: int("²")` — card: "Then 1 (the call raises ValueError)" | FQ-36 |
| Then 1 | ON-14, ON-15, FQ-08, FQ-33, FQ-37, FQ-40, FQ-41, FQ-42, LP-03, LP-09, PF-15, AH-05, AH-20, AH-21, AH-22, AH-25, HS-07, HS-10, HS-11, CA-05, CA-07, SI-09 |
| Then 2 | FQ-06, FQ-07, PF-17, AH-02, AH-26, SI-07, OQ41-01, OQ41-02, OQ41-04, OQ41-05, OQ41-06, OQ41-07 |

Spot values: AH-25 today `[B2, B1, B3]` (the collation puts `bravo` first) vs `[B1, B2, B3]`; AH-26 `order_part` is `accounts.name ASC, accounts.id ASC`; OQ41-01 `len == 4`, `(2, 1200.00, 0.00, 1200.00)`; HS-10 / HS-11 `(2, 50.00, 0, 2)`; FQ-42 returns the `BackSlash` account (`\S` read as `S`).

**Reference plugin** `ref_ai.py` (same folder, `-p ref_ai`, folder on `PYTHONPATH`) swaps `AccountInvoiceDAO` methods in-process for the intended behaviour: account joined on id **and** workspace (BUG-2690, in the filter and the hub sub-select); work-order sub-selects skip `is_deleted` (BUG-2691); escaped account-name / hub search and an ASCII-only id shortcut (BUG-622); hub order `lower(name), id` (BUG-623); open balances confirmed + unpaid/partial, money totals confirmed only (BUG-634); a `today=None` keyword on the eight methods, overdue = confirmed, unpaid/partial, `due_date < today` (BUG-635); inactive accounts with an open balance on the hub (BUG-636); whitespace-only search = no filter (BUG-637); `summarize_invoices` → `(count, payable triple, receivable triple)` (BUG-2692). With `--runxfail`: **219 of 219 passed** (Revision 4, no change to the plugin needed; Revision 3: 216 / 216; under Revision 2 it was 213 / 3, the three being DISCREPANCY-1 … 3). Every pass card also passes under the reference, so none of them pins today's buggy behaviour. Nothing in `app/` changes.

## Discrepancies
None open. DISCREPANCY-1 … 3 (Revision 2: AIV-ES-01, ES-02, ST-03 card typos, a backslash lost) are **resolved by cases Revision 3 (2026-11-14)**: the three Then lines now read `r"a\%b\_c\\d"`, `r"\\\%\\\_"`, `r"%Ab\_c\\D%"`, as spec `_escape_ilike` R1 and the code give; the tests carry those values and no marker.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 472 (`get_by_order` body) | dead | `get_by_order` is listed under Not specified as dead code (Q1, to be removed; in `docs/testing/dead-code-removal-checklist.md`). |

Branch coverage of everything else: 100% (46 of 46 branches). Private `COVERAGE_FILE`: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaoe\ai\.coverage`.

## Factories added
None (all builders are local; `factories.py` untouched).

## Stability
Revision 4 (2026-11-14):

| Run | Passed | xfailed | Not as designed |
|---|---|---|---|
| plain 1 | 177 | 42 | 0 |
| plain 2 | 177 | 42 | 0 |
| plain 3 | 177 | 42 | 0 |
| with `--cov` (branch) | 177 | 42 | 0 |
| `--runxfail` | 177 | — (42 failed, all on the designed line) | 0 |
| `--runxfail` with the reference plugin | 219 of 219 | — | 0 |

Revision 3 had 174 / 42 in each run and 216 / 216 under the reference plugin. Revision 2 had 171 / 45 in each run (3 DISCREPANCY xfails) and 213 / 216 under the reference plugin. A joint run with the four other big-DAO files (five concurrent processes) gave 171 / 45 then, with no clashes.

`ruff check`: all checks passed (file-level `noqa: DTZ001, FURB157` for the Conventions' naive datetimes and the cards' `Decimal("0")` literals); `ruff check --select F841,F811`: clean; `ruff format`: formatted. Line endings: LF.

## Notes for maintainers
- **BUG-635 fix:** adds `today` to eight methods. Spec gap 3 (cases file) is still open: if `today` becomes **required**, every pass card on those methods raises `TypeError` and must gain `today=TD`; with a default (`None`, as in the reference) nothing else changes. FQ-19, FQ-44, AH-03, AH-33, AH-34, HS-08, HS-14 then XPASS — remove their markers.
- **BUG-2692 fix:** OQ41-01, 02, 04 … 07 XPASS; SI-14, SI-15, OQ41-03 and every `SI` card (which read `result[:4]` or single positions) keep passing.
- **BUG-2690 / 2691 / 622 / 623 / 634 / 636 / 637:** their cards XPASS (strict → fail) when fixed; remove the markers in the same change.
- AH-25 depends on the database collation only in that *any* case-sensitive order fails it; the reference (`lower(name), id`) passes on this database.
- Orders are inserted with foreign keys off (`session_replication_role`, needs the superuser `postgres` test role); never touch their relationships in a test.

## Revision history
- **Revision 2 (2026-11-14):** first execution of this cases file (no earlier test file existed).
- **Revision 3 (2026-11-14) — fix in:** cases Revision 3 corrected AIV-ES-01, ES-02 and ST-03 (DISCREPANCY-1 … 3). Those three tests now assert `r"a\%b\_c\\d"`, `r"\\\%\\\_"` and `r"%Ab\_c\\D%"`, and their `DISCREPANCY` xfail markers (and the `DISC1` … `DISC3` reason constants) are removed; no other test changed. Re-run: 3 plain runs 174 passed / 42 xfailed each; `--runxfail` 42 failed / 174 passed; reference plugin `ref_ai` with `--runxfail` 216 / 216; branch coverage 99% (line 472, dead); ruff check and format clean; LF. Ready for the verifier.
- **Revision 4 (2026-11-14) — verify findings 1–3 (`case-missing`):** cases Revision 4 added AIV-PF-19 (`list_invoices_page_filtered` without `open_balance_only` lists and counts paid, voided and draft), AIV-AH-35 (receivable twin of AH-18: 0.00 left out, 0.01 kept, `rec(...).outstanding_total == 0.01`) and AIV-UP-26 (a 0.01 payment on an unpaid invoice gives `partial`), each inserted in card order (after PF-18, AH-34, UP-25); all three are plain passes. Existing tests unchanged; the module docstring now names Revision 4. `ref_ai.py` needed no change. Re-run: 3 plain runs 177 passed / 42 xfailed each; `--runxfail` 42 failed / 177 passed, all 42 on their designed line (checker `BAD: 0`); reference plugin with `--runxfail` 219 / 219; branch coverage 99% (line 472, dead); ruff check and format clean; LF. No discrepancies.
