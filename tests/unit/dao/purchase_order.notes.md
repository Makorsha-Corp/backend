# Execution notes — `app/dao/purchase_order.py`

> Cases: `tests/unit/dao/purchase_order.cases.md` (revision 2) · Tests: `tests/unit/dao/test_purchase_order.py` · Source commit: e48a092
> Result: 204 passed · 38 xfailed · 0 discrepancies · 0 errors — branch coverage 94% (every miss is dead code)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_purchase_order.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
- Built in normal mode (no local model): one test per card, in card order, each under a `# [claude] <ID>` comment, with a `# Then N` comment before the assertions of each Then line. Parametrized (one input differs, each case keeps its own id): HF-32 … 34 (`invoice_filter`), HF-44 / 45 (blank search), AL-02 … AL-14 (W1's stored numbers → expected next number), IN-02 / 03 (limit 0 / -1).
- **Standing rows** → fixture `s` (SimpleNamespace), built in the Conventions' order (W0, W1, W2, U1 … U3; then W0's, W1's, W2's stages, accounts, factories, machines, projects, components, items, invoices), each flushed. `s.SP1`, `s.V2`, `s.IE`, … are the Conventions names.
- **Given rows** → `po(db, s, number, **cols)` (W1), `po0` / `po2` (W0 / W2 twins); the "but" columns are keyword arguments, `id="HIGH"` means HIGH_ID. Shorthands are dict helpers spread into the call: `stage(S)`, `closed(s)`, `voided(s)`, `edited(s, T)`, `NO_SUPPLIER`, `to_machine(M)`, `to_component(C)`, `to_storage(F)`, `closed_account(s)` (also "deleted machine"), `deleted_project(s)`. `pos(db, s, n)` returns the list R (R[k] = `PO-2026-<k+1>`), one flush. `line(db, s, O, line_number, **cols)` picks I0 / I1 / I9 by the PO's workspace. `inv1(db, s, **cols)` builds the OQ37 extra invoices (VP, VD, VX, VXP, VL, VPA, VO). `xid(k)` and `high_id(db, table)` implement XID / HIGH_ID.
- **Named checks**: `ids`, `idset`, `eids`, `reread_po` (expire, then SELECT by id), `totals` ("nothing written": PO count and line count), `order_part`. `Recorder` is the statement recorder (`before_cursor_execute` on the session's connection, statement and parameters): `sqls`, `written`, `sql` (first SELECT with `FROM purchase_orders`), `isql` (first with `FROM purchase_order_items`). PH-12 picks the Draft-sample SELECT as the single recorded SELECT whose bound parameters contain `"Draft"` and that has a `LIMIT` (it asserts there is exactly one).
- **Externals**: `clock(L, U)` patches the std `datetime.datetime` (subclass whose `now()` returns L — `allocate_po_number` imports `datetime` inside the function), `app.dao.purchase_order.utcnow` (`create=True`) and `app.utils.time.utcnow`; every AL card's When runs under it (default 2031-06-01 12:00 for both). **Race simulation**: AL-29 / AL-30 patch `app.dao.purchase_order._po_number_taken` with `create=True`; nothing else is mocked.
- AL-27's duplicate insert runs inside `db.begin_nested()` under `pytest.raises(IntegrityError)`.
- Tie cards (LH-02, RH-04, PH-04, PH-10, GV-07, IN-10) use `seqscan` + `bumpP` / `bumpL` (raw SQL update, then `expire_all`); ids are captured before the bump because the expire would otherwise reload them lazily.
- Unique values: `po_number` is unique per workspace and every test makes fresh workspaces, so numbers are written as carded. XID depends on the pid, so parallel runs do not share explicit ids. AL cards see only committed PO numbers of other sessions; the test database has none in `PO-2031-*` / `PO-2033-*`.

## `--runxfail` check
All 38 xfail tests fail under `--runxfail`, each inside the Then block its card names in "Fails today on" (checked mechanically by mapping the failing line to the preceding `# Then N` comment, and by reading the values): e.g. AL-17 `'PO-2031-002' == 'PO-2031-001'`, AL-19 `-006`, AL-23 `PO-2032-001`, AL-24 `PO-2031-005`, AL-29 `DID NOT RAISE`, AL-30 `PO-2031-001`, OQ35-01 `1006.00`, OQ35-03 open count `2`, OQ37-05 `3`, HF-53 only `PO-2026-89` matched, OQ38-08 … 10 `KeyError: 'quantity_refunded_total'`, RH-05 order part `updated_at desc, created_at desc`, PH-12 `created_at ASC` only, GV-09 no `ORDER BY`, IN-12 no line id.

## Reference plugin
`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaoe\po\ref_po.py` (in-process, `-p ref_po` with that folder on `PYTHONPATH`; nothing in `app/` changes) applies the intended behaviour of BUG-2630, 2632 … 2641 (escaped search, deleted supplier left out of the name join, `coalesce(updated_at, created_at) DESC, id DESC`, drafts `created_at, id` ascending, `get_by_invoice_id` lowest id, preview tie-break by line id, voided POs out of the money figures, outstanding = confirmed / locked and not paid, `quantity_refunded_total`, workspace-scoped `_po_number_taken`, UTC year).
- With `--runxfail`: **240 passed, 2 failed** — AL-20 and AL-21. That is what their cards say: they reach R6 through other workspaces' numbers, a path the BUG-2630 fix removes ("Retire this card when BUG-2630 is fixed; AL-29 / AL-30 take over").
- Variant `REF_PO_KEEP_2630=1` (every fix except the workspace scope of the taken check), `--runxfail`: **239 passed, 3 failed** — exactly AL-17, AL-18, AL-19 (BUG-2630 cards); AL-20, AL-21, AL-29, AL-30 pass. So every test passes under the fix it belongs to.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 148-157 | dead | `PurchaseOrderDAO.get_by_workspace` — spec Not specified (Q1, dead code, to be removed) |
| 330 | dead | `PurchaseOrderDAO.get_next_number` — spec Not specified (Q1, alias of `allocate_po_number`, no caller) |

144 statements, 46 branches, 0 partial branches; 94% only because of the two dead callables (private `COVERAGE_FILE`). Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None (all builders are local).

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| plain 1 | 204 | 38 | 0 | 0 |
| plain 2 | 204 | 38 | 0 | 0 |
| plain 3 | 204 | 38 | 0 | 0 |
| `--runxfail` | 204 | — (38 failed, each on its carded Then) | — | 0 |
| `--runxfail` + reference plugin | 240 | — | — | AL-20, AL-21 (retire at BUG-2630 fix, as carded) |
| `--runxfail` + reference plugin, `REF_PO_KEEP_2630=1` | 239 | — | — | AL-17 … 19 (BUG-2630 kept on purpose) |

`ruff check` (incl. `F841,F811`): all checks passed; `ruff format`: formatted. Line endings: LF.

## Notes for maintainers
- When BUG-2630 is fixed: AL-17 … AL-19, AL-29, AL-30 XPASS (strict) → remove their markers; **retire AL-20 and AL-21** (their path is gone). The fix must keep the module-level helper `_po_number_taken(db, *, workspace_id, po_number)` and call it once per candidate with keyword arguments (AL-29 checks `call_args_list[0].kwargs`). If BUG-2631's fix replaces the loop with a counter, AL-20, 21, 29, 30 go with the loop.
- BUG-2632: AL-23 / AL-24 XPASS → remove markers. BUG-2633 (HF-51 … 55), BUG-2634 (HF-56), BUG-2635 (RH-01, RH-05, PH-03, PH-05 strict; RH-04, PH-04 non-strict), BUG-2636 (PH-12 strict; PH-10, PH-11 non-strict), BUG-2637 (GV-09 strict; GV-07, GV-08 non-strict), BUG-2638 (IN-12 strict; IN-10, IN-11 non-strict), BUG-2639 (OQ35-01 … 04), BUG-2640 (OQ37-02, 03, 05), BUG-2641 (OQ38-08 … 10): remove the markers at each fix; remove the non-strict ones at the same time as the strict alarm of the same bug.
- The clock patches `datetime.datetime` globally for the AL Whens only; keep it narrow (a Fake `datetime` in place during unrelated code breaks `isinstance` checks elsewhere).
- Don't add `-W ignore::sqlalchemy.exc.SAWarning` to the coverage command: importing `sqlalchemy.exc` for the warning filter before pytest-cov starts makes SQLAlchemy import twice ("Type <class 'object'> is already registered"). The 20 warnings are the app's `SAWarning: Coercing Subquery object into a select() for use in IN()` in `aggregate_hub_stats` (line 258) — harmless today, but a future SQLAlchemy may turn it into an error (pass `filtered_ids.select()`).

## Revision history
- **Revision 2 (2026-11-14):** first execution of this cases file (no earlier test file existed).
