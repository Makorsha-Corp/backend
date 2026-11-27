# Execution notes — `app/services/orders_overview_service.py`

> Cases: `tests/unit/services/orders_overview_service.cases.md` (revision 4) · Tests: `tests/unit/services/test_orders_overview_service.py` · Source commit: e48a092
> Result: 110 passed · 69 xfailed · 1 xpassed (non-strict OOV-TE-05, as designed; 70 xfail cards) · 0 discrepancies · 0 errors — branch coverage 99% (158 statements, 48 branches, 2 partial)
> Run: `COVERAGE_FILE=<private> .venv/Scripts/python.exe -m pytest tests/unit/services/test_orders_overview_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.orders_overview_service --cov-branch --cov-report=term-missing`

## How the tests are built
- **Standing rows**: the autouse fixture `st` builds every Conventions standing row for every test, the pure-helper tests included. Order: W0, W1, W2, U1, U2, then W0's S0, F0, M0, WT0, AC0, I0, then W1's statuses (S1, SD, SP, SR, SC), factories (FA, F1, F2, FD, FI), machines, WT1, accounts, items and PJ1, then W2's rows. Each row is flushed on its own. Card names are lower-case attributes (`F1.id` → `st.f1.id`).
- **Order builders**: `mk` (a `Builder`) has `po`, `to`, `so`, `eo`, `wo`, the lines `pol`, `tol`, `sol`, and the approver rows `poa`, `soa`, `eoa`, `woa`. The number goes first. Keyword arguments are the "but" columns.
  - `ws="w0"` / `ws="w2"` gives "W0 x" / "W2 x": F1, F2 and FA become F0 / F9, S1 becomes S0 / S9, AC1 becomes AC0 / AC9 and WT1 becomes WT0 / WT9. The "but" columns are applied after that, so `mk.po("PO-9", ws="w2", destination_id=st.f1.id)` points at the W1 row as the card says.
  - Closed and stage states are properties spread with `**`: `mk.voided` (po / eo), `mk.voided_wo`, `mk.deleted_wo`, `mk.draft` (po / so) and `mk.draft_wo`. "approved" on an approver row is `**APPROVED`. A deleted account is built with `deleted_account(db, st, name)`.
- **Unique order numbers**: `transfer_number` and `sales_order_number` are unique across all workspaces, so `to` / `so` store the Conventions **GN(n)** = `f"{n}-{os.getpid()}"` (module helper `GN`; `"TO-1"` → `"TO-1-<pid>"`). No card reads an order number. PO, expense and work order numbers are unique per workspace only. The workspaces are new in every test, so those numbers are kept exactly as the cards write them.
- **Calls**: `stats(db, st, **kw)` is the Conventions default `get_stats` call, with any keyword the card changes. `top_factories(db, st, limit=10)` is the positional `_build_top_factories` call. `poq` / `toq` follow Conventions.
- **Named checks**: `item_ids`, `vendor_ids`, `customer_ids`, `cats`, `fids`, `irow`, `vrow`, `crow`, `erow`, `frow` and `ids`. The `…row` helpers assert that exactly one row matches, as Conventions say. `recorder(db)` is a context manager on `before_cursor_execute` of `db.connection()`, removed when the When block ends. The spies are written inline as Conventions give them.
- **xfail markers**: `bug(n, strict=True)` gives `reason="BUG-n: <bugs.md title>"`. `bugs(n1, n2, …)` (revision 4) is one strict xfail whose reason names every bug a card needs (OQ29-06, 07, 12, 13, 16, 17 and OQ30-08, in the card's order). FV-08 / FV-09 use `BUG_2502_2504` (revision 3, see Revision history). FV-01 … FV-07 use `BUG_2502 = bug(2502, raises=InvalidRequestError)`. Today the When call raises before Then 1, as the cards' "Fails today on" says. `raises=` pins the xfail to that cause. OOV-TC-06 and OOV-TE-05 are `strict=False`, as their Expect line says.
- **Nothing is patched** except the Conventions spies and OOV-GS-13's failing `db.query`. The spec lists no externals.
- `# ruff: noqa: FURB157` at the top: the cards write `Decimal("0")`, and the tests keep that literal.

## Verification runs (2026-11-10, revision 4)
- **3 plain runs**: 110 passed, 69 xfailed and 1 xpassed every time. The XPASS is the non-strict OOV-TE-05: Postgres happened to return the three tied categories in text order.
- **`--runxfail`**: 69 failed, 111 passed. All 68 strict xfails (and the non-strict TC-06) fail on the Then line their card names. The check script is scratch `check_xfail.py`. It maps each failure's first frame in the test file to the `# Then N` block holding it.
  - FV-01 … FV-07 fail in the When call, before Then 1, with `InvalidRequestError` ("Query.filter() being called on a Query which already has LIMIT…").
  - The OQ29 split cards fail on the first `…_committed` / `…_projected` read, with `AttributeError`.
  - Every other card fails on the value its card names. Examples: TI-12 `55.00 == 5.00`; TV-08 `1010.00 == 10.00`; OQ30-03 `22005.00 == 10000.00`; OQ30-08 `24000.00 == 12000.00`; TC-07 / TE-06 `ORDER BY` with the sum only.
  - The non-strict OOV-TC-06 fails today on Then 1. OOV-TE-05 holds by chance.
- **Reference plugin**: scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsupe\oo\oo_ref_fix.py`. It is loaded with `PYTHONPATH=<scratch> -p oo_ref_fix`, and `OO_FIX` selects the bugs (default all). It replaces `get_stats`, `_build_top_factories`, `_filter_po_by_factory` and `_filter_transfer_by_factory` on the class, in process only.
  - It adds the new fields with `pydantic.create_model` subclasses of the four row schemas.
  - The customers and categories cuts stay in SQL (`ORDER BY sum DESC, lower(accounts.name), account_id` / `…, expense_category`, then `LIMIT`). The committed / projected split is read with separate per-order queries that have no `GROUP BY`.
  - **With all fixes and `--runxfail`: 180 passed** (revision 4; 165 at revision 3, 163 at revision 2).
  - **With `OO_FIX=0`** (no fix), the reference reproduces today's results: 110 passed, 69 xfailed, 1 xpassed, and the same `--runxfail` failure set.
  - **Each fix on its own** flips only its own cards and breaks no pass card:
    - 2480 → OQ29-05, 08, 09, 10, 11, 14
    - 2481 → OQ30-01, 02, 03, 07, 09 … 13
    - 2500 → TE-04, TF-20, TF-21, TI-12, TV-08, TV-09
    - 2501 → TF-22
    - 2502 → FV-01 … FV-07 (FV-08 / FV-09 then fail on Then 1, the BUG-2504 check, and stay xfailed)
    - 2503 → FP-07, FP-08, FT-06, TF-30 … TF-32
    - 2504 → FP-06, FT-07, TC-05, TF-23 … TF-29, TI-13 … TI-15, TV-10, TV-11
    - 2505 → TC-06, TC-07, TE-06, TF-33, TF-34, TI-16, TI-17, TV-12, TV-13
    - 2506 → TF-19
  - **Cards that need two fixes** (by design: they read the split of a measure that only exists after another fix, or the split with voided rows left out):
    - OQ29-06, 16, 17 need 2480 + 2500.
    - OQ29-07, 12 and OQ30-08 need 2480 + 2481.
    - OQ29-13 needs 2480 + 2481 + 2500 + 2501.
    - FV-08, FV-09 need 2502 + 2504 (revision 3).
    - Revision 4 names these combinations on the cards' Expect lines; the markers (`bugs(...)`) list them.
    - With 2480, 2481, 2500 and 2501 together, all 29 BUG-2480 / 2481 / 2500 / 2501 cards flip.
  - The per-fix runs are scripted in scratch `per_fix4.py` (one `--runxfail` run per `OO_FIX` setting, compared with `OO_FIX=0`).
- **Verifier survivors** (scratch `oo_variants.py`, `OO_VARIANT` picks one; it edits the module source in memory and binds the edited methods on the class, never on disk). Plain run per variant:
  - `vendor_plus_sales` (sales merged into vendors): fails TV-14 only.
  - `deleted_po_account` (PO vendor rows of a deleted account dropped): fails TV-15 only.
  - `float_items`: fails TI-21 only (`0.30000000000000004 == 0.30`).
  - `float_vendors`: fails TV-17 only.
  - `float_customers` (SQL sum over float8): fails TC-08 only.
  - `float_factories`: fails AF-07, TF-01 (scale) and TF-35 (exact sum).
  - So each survivor is now caught, by the revision 4 card written for it.
- `ruff check`: clean. The file is LF only (0 CR bytes).
- Under `--cov` only, 15 SQLAlchemy "GenericFunction already registered" `SAWarning`s appear (seen for other files too). Plain runs are clean.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 518->542 | unreachable (today) | The `factory_id is not None` arm of the categories block. Every call with a `factory_id` raises at line 506 first (BUG-2502), so this arm is never reached. FV-06 / FV-07 cover it once BUG-2502 is fixed. |
| 543->548 | unreachable (today) | The same for the top-factories block (`factory_id is not None` → `[]`). |

## Factories added
None. The builders are local.

## Notes for maintainers
- **When a BUG is fixed**, its cards XPASS (strict → fail). Remove their markers, using the per-fix list above. For BUG-2502, remove `BUG_2502` from FV-01 … FV-07; FV-08 / FV-09 (`BUG_2502_2504`) then xfail on Then 1 until BUG-2504 is fixed too.
  - The BUG-2480 split fields are read from the row objects. A fix that adds them to `TopItemRow`, `TopAccountRow`, `TopExpenseCategoryRow` and `TopFactoryRow` turns the OQ29 cards green only together with the fixes listed under "Cards that need two fixes".
- TC-07 / TE-06 find the cut by its text: exactly one statement with `sales_orders` / `expense_orders`, `GROUP BY` and `LIMIT`. A fix that reads the split with another grouped `LIMIT` query on those tables would trip Then 2. Read the split per order, or without `LIMIT`.
- Explicit ids `XID(k)` come from the process id (Machine `XID(1)`, components `XID(2)`, `XID(4)`, project / component `XID(3)` and `XID(5)`). Two runs of this file in one process are fine. Runs in separate processes never share ids.
- The standing rows cost about 35 inserts per test. The whole file runs in about 11 s.

## Revision history
- **2026-11-10 — cases revision 2.** First implementation: 163 cases; at that revision 95 passed, 67 xfailed, 1 xpassed (non-strict TE-05), 99% branch.
- **2026-11-10 — cases revision 3** (coordinator follow-up; spec gap 1, factory view on another workspace's factory):
  - New OOV-FV-08 (factory view on W2's F9) and OOV-FV-09 (on W0's F0): W1 orders linking that factory and that workspace's own orders show in no list; every list `== []`. Marker `BUG_2502_2504` = strict xfail, `reason` names BUG-2502 and BUG-2504, `raises=(InvalidRequestError, AssertionError)`: today the When raises (BUG-2502, before Then 1); with BUG-2502 alone fixed, Then 1 fails on the W1 orders linking the foreign factory (BUG-2504). Both stay xfailed until both bugs are fixed.
  - The per-process suffix is now the Conventions helper `GN(n)` (was an inline `f"{number}-{TAG}"`; same value).
  - Reference plugin: BUG-2504 now also maps a `factory_id` of another workspace to an id that names no factory (0), so every list is empty and the answer is 200 (R8b). The rest of the call runs unchanged, so the BUG-2502 crash still shows when only 2504 is on.
  - Runs: 3 plain runs 95 passed, 69 xfailed, 1 xpassed. `--runxfail`: 69 failed, 96 passed (TE-05); check script: all 68 strict cards and the non-strict TC-06 fail where their card says, FV-08 / FV-09 in the When with `InvalidRequestError`. Plugin: all fixes + `--runxfail` 165 passed; `OO_FIX=0` reproduces today; each fix alone flips only its own cards (lists above), 95 pass cards green in every run.
  - No discrepancy. Coverage unchanged (99%; both gaps still behind BUG-2502).
- **2026-11-10 — cases revision 4** (`orders_overview_service.verify.md` findings 1–8, 10, 11; spec R8c):
  - 15 new pass cards, in card order: FP-10, FP-11, FT-08, FT-09, TF-35, TF-36, TI-18 … TI-21, TV-14 … TV-17, TC-08. In TI-19 the card's row `IS` is the variable `is_` (`is` is a Python keyword).
  - F11: OQ29-06, 07, 12, 13, 16, 17 and OQ30-08 now carry `bugs(...)` with every bug their Expect line names; they still fail today on the same Then line (no `raises=` pin, as before).
  - F10: FV-08 / FV-09 docstrings cite `_build_top_factories` R8b; expectation unchanged.
  - Reference plugin unchanged (no new bug named): all fixes + `--runxfail` 180 passed; `OO_FIX=0` reproduces today; each fix alone flips only its own cards; the multi-bug cards flip only with all their bugs.
  - Verifier survivors `vendor_plus_sales`, `float_sum` (four measures) and the deleted-account drop are each killed by their new card (see Verification runs).
  - Runs: 3 plain runs 110 passed, 69 xfailed, 1 xpassed. Coverage unchanged (99%; both gaps behind BUG-2502). Stale counts (67 xfailed, 165 passed) corrected. No discrepancy.
