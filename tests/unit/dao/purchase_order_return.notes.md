# Execution notes — `app/dao/purchase_order_return.py`

> Cases: `tests/unit/dao/purchase_order_return.cases.md` (Revision 3, READY, 90 cases) · Tests: `tests/unit/dao/test_purchase_order_return.py` · Source commit: e48a092
> Result: **90 tests for 90 cases — 75 passed · 15 xfailed (8 strict, 7 non-strict) · 0 discrepancies · 0 errors** — line and branch coverage 100% (27 statements, 0 branches).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_purchase_order_return.py -q -p no:cacheprovider -o addopts=""`

## Who wrote what
Normal mode, no local model (full Claude): every test sits below a `# [claude] <ID>` comment, in card order. The `Author: claude` cards (PO-10, PO-11, PO-12, OP-10, OP-11, RI-08, RI-09) use the Conventions' recipes as written: `seqscan` then `bumpR` / `bumpL` of the lowest id, or one row with an explicit `HIGH_ID(table)` built between two ordinary rows.

## How the tests are built
- **Standing rows:** fixture `s` builds W0, W1, W2, U1–U3, I1, then O0, O1, O2, O3, O9 **unchecked** (`SET LOCAL session_replication_role = replica` … `origin`), since `destination_id` and `current_status_id` name no row.
- **Builders:** `mk_return(db, s, N, **but)` = "return N"; `created_at` is left to the model default unless the card gives it; a return with `invoice_id` set is built unchecked (IVA/IVB/IVC name no invoice). `mk_line(db, s, R, **but)` = "line of R", always unchecked (`po_item_id` = MISSING). `id="HIGH"` in either builder = `HIGH_ID(table)`, read when the row is built. `completed(s)` and `VOIDED` hold the Conventions' "completed" / "voided" columns; `_w0(s)` / `_w2(s)` the "but `workspace_id W0.id`, `purchase_order_id O0.id`" pairs.
- **Clock:** `clock(L, U)` patches `app.dao.purchase_order_return.datetime` (a `datetime` subclass whose `now()` returns L), `app.dao.purchase_order_return.utcnow` (`create=True`) and `app.utils.time.utcnow`. Every `CW` card without a clock line runs under `clock(JUNE, JUNE)`; CW-02 patches nothing and runs under Dhaka.
- **Reading helpers (no expected values inside):** `reread`, `snap` ("unchanged": every mapped column after re-read), `wcount(W)` (the carded `text` count), `totals` ("nothing written"), `ids`, `idset`.
- **Statement recorder:** as in the sales twin; `sql` fails loudly unless exactly one SELECT was sent.
- **RI-11:** the Given ends with `db.expire_all()` and then edits R, so `R.id` and `W1.id` are read just before the recorder starts (`r_id, w1_id`). Otherwise their lazy reloads would show up as extra SELECTs inside the When. The call itself is the card's.
- **Cards whose Then 1 is the When itself** (CW-10, CW-11, CW-12): the `# Then 1` comment sits directly above the call.

## xfail location (`--runxfail`)
Plugin `failson.py` (`-p failson`, scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omde\B\`). Result: 15 failed, 74 passed. Each xfail fails on the Then line its card names:

| Card | Strict | Card says | Fails on | Actual |
|---|---|---|---|---|
| CW-08 | yes | Then 2 | Then 2 | `'PR-2027-001' == 'PR-2026-001'` |
| CW-09 | yes | Then 2 | Then 2 | `'PR-2026-001' == 'PR-2027-001'` |
| CW-10 | yes | Then 1 | Then 1 | `UniqueViolation` on `purchase_order_returns_return_number_key` |
| CW-11 | yes | Then 1 | Then 1 | the same |
| CW-12 | yes | Then 1 | Then 1 | `UniqueViolation`: the count gives -004, which C holds |
| PO-10 | no | Then 2 | Then 2 | `[B, C, D, A]` vs `[D, C, B, A]` |
| PO-11 | no | Then 2 | Then 2 | `[B, C, A]` vs `[C, B, A]` |
| PO-12 | no | Then 2 | Then 2 | `[EB, EC, EA]` vs `[EC, EA, EB]` |
| PO-13 | yes | Then 3 | Then 3 | `'.id' in ' purchase_order_returns.created_at DESC'` |
| OP-10 | no | Then 2 | Then 2 | `[B, C, A]` vs `[A, B, C]` |
| OP-11 | no | Then 2 | Then 2 | `[EB, EC, EA]` vs `[EB, EA, EC]` |
| OP-12 | yes | Then 2 | Then 2 | no `ORDER BY` |
| RI-08 | no | Then 2 | Then 2 | `[A, C, B]` vs `[A, B, C]` |
| RI-09 | no | Then 2 | Then 2 | `[EA, EC, EB]` vs `[EB, EA, EC]` |
| RI-10 | yes | Then 2 | Then 2 | no `ORDER BY` |

**Reference plugin** `ref_prt.py` (same folder, `-p ref_prt`): year from `utcnow()` (BUG-2428); skip a number already taken in the workspace (BUG-2427 R3a); `ORDER BY created_at DESC, id DESC` (BUG-2429); `ORDER BY id` (BUG-2430, BUG-2431). For BUG-2426 an autouse fixture swaps `purchase_order_returns_return_number_key` for a unique index on `(workspace_id, return_number)` inside the test's own transaction (undone by the rollback). With `--runxfail`: **89 passed**. That includes PO-14 (`created_at` then `DESC,` holds with the tie-break) and CW-18 (same-workspace 23505). Nothing in `app/` changes.

## Discrepancies
None.

## Coverage gaps
None — 100% line and branch coverage (private `COVERAGE_FILE`). Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None (all builders are local).

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| Default, runs 1–3 | 74 | 15 | 0 | 0 |
| Database `TimeZone` `America/New_York` | 74 | 15 | 0 | 0 |
| Database `TimeZone` `Asia/Dhaka` | 74 | 15 | 0 | 0 |
| `enable_seqscan=off` | 74 | 14 | 1 (OP-10) | 0 |
| `enable_sort=off` | 74 | 15 | 0 | 0 |
| index and bitmap scans off | 74 | 15 | 0 | 0 |
| `--runxfail` | 74 | — | — | 15 failed, each at its card's Then |
| `--runxfail` with the reference plugin | 89 of 89 | — | — | 0 |

`ruff check`: all checks passed; `ruff format`: formatted. Line endings: LF.

## Notes for maintainers
- When BUG-2426/2427 (R3a)/2428 are fixed, CW-08 … CW-12 XPASS and fail strict: remove their markers. BUG-2426 needs a migration.
- When BUG-2429/2430/2431 are fixed, PO-13, OP-12 and RI-10 XPASS (strict): remove their markers. Remove the non-strict markers of PO-10, PO-11, PO-12, OP-10, OP-11, RI-08 and RI-09 at the same time.
- `session_replication_role` needs a superuser, which the test role `postgres` is. Unchecked rows (orders with `current_status_id` MISSING, lines with `po_item_id` MISSING) are invalid on purpose; never `UPDATE` an order (Conventions).
- `PurchaseOrderReturnItem.item` is `lazy="joined"` (`LEFT OUTER JOIN items` in the line query).

## Revision history
- **Revision 2 (2026-11-10):** first execution of this cases file (written fresh against Revision 2; no earlier test file existed).
- **Revision 3 (2026-11-10):** patched, not regenerated (verify findings 1–2). Added PRT-CW-19 (both clocks 2031 → `PR-2031-001`), inserted after CW-18. PRT-PO-15 and OP-13 gain Then 9, IN-10 Then 8, RI-11 Then 10: `"FOR UPDATE" not in rec.sql`. Other tests unchanged. Re-run: 3 plain runs 75 passed / 15 xfailed each; `--runxfail` 15 failed on the same Thens as Revision 2; reference plugin `ref_prt.py` with `--runxfail` 90 / 90; coverage 100%; ruff check and format clean; LF. Lock-everything variant (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omde\B\var_b.py`, `VARIANT=lockall`): exactly the four new no-lock lines fail (4 failed, 71 passed, 15 xfailed). Hard-coded-2026 variant (`VARIANT=year2026`, the verifier's `pr-year-hard2026`): PRT-CW-19 fails at Then 2 (and strict CW-08 XPASSes, since that bug case wants 2026).
