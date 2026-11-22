# Execution notes — `app/services/account_invoice_service.py`

> Cases: `tests/unit/services/account_invoice_service.cases.md` (revision 3, 2026-11-22) · Tests: `tests/unit/services/test_account_invoice_service.py` · Source commit: e48a092
> Result: 106 passed · 43 xfailed · 0 open discrepancies (DISCREPANCY-1 resolved in cases rev 2a) · 0 errors — branch coverage 98%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_account_invoice_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.account_invoice_service --cov-branch --cov-report=term-missing`

## How the tests are built
- **One test per card, in card order**, named `test_ais_<x>_<nn>__<slug>`, each with a `# [claude] <ID>` comment; `# Then N` marks the checks of Then line N (before the `with pytest.raises` line for a `raises:` line). No parametrize (S-11 … S-13 differ in setup, so they are three tests).
- **Standing rows** are the namespace fixture `s` (`s.W1`, `s.U2`, `s.SR1`, `s.A9`, `s.I1`, `s.TAG` …), built in the Conventions order. A workspace key `"0" / "1" / "9"` (builder argument `ws=`) selects "of W0" / W1 / "of W9" and that workspace's A, F, WT, SD, WF (`_ws`).
- **Given rows**: one builder per Conventions name (`inv`, `invl`, `pay`, `po`, `poline`, `poappr`, `so`, `soline`, `soappr`, `eo`, `eoline`, `eoappr`, `wo`, `ievent`, `po_return`, `inv_many` for the `add_all` batches). Shorthands are flags applied before the card's "but" keywords: `confirmed=True`, `ready=True`, `of=V`, `locked_by=V`, `so_ready=True`, `finalized_by=V`, `approved=True`, `voided=True` ("voided pay"). Every builder flushes. `CRT(s, **k)` adds `invoice_amount=0.00` because the field exists on `AccountInvoiceCreate`.
- **Commit point** = `commit_point(db)` (`db.commit()`, a savepoint release) which returns the "nothing written" counts; `snap(db, R)` snapshots (all columns, Core `SELECT` on the row's table) are taken right after it. X = `mk_x(db)` after the commit point. `committed:` lines start with one `db.rollback()`; every re-read (`reread`, `snap`, `EV`, `IEV`, `LINES`, `notes`, `count_where`) expires the session first.
- **Ids are captured** right after the commit point where a later step rolls the session back or expunges it (failing commit / refresh, notify, recorder cards).
- **Mocks**, only those the Conventions name: commit / rollback spies, failing commit, failing refresh (`patch.object(db, …)`), and for the `Author: claude` card K-13 `patch("app.services.account_invoice_service.notify_invoice_action", side_effect=RuntimeError("boom"))`. No SSLCommerz or other external is reached by this service.
- **Lock cards** (S-25, K-15, K-38, X-08, X-25): `Recorder` listens to `after_cursor_execute` on the session's connection during the When only, after `db.expunge_all()`. `lock(T)` = first recorded SELECT whose FROM clause (text between `FROM` and `WHERE`/`ORDER BY`/`LIMIT`/`FOR UPDATE`) names T and that contains `FOR UPDATE`; `row_lock`, `line_lock`, `before`, `lock_before_lock` implement the Conventions wording.
- **X-09 setup** (now the card's own steps 6 and 7 since cases rev 3; kept for the record): the card's old step 6 (`O.current_status_id = SD1.id`, delete SP1 / SR1 / SC1, one flush) is done with a flush right after the `current_status_id` change. In one flush the ORM's `Status.purchase_orders` backref nulls O's `current_status_id` when SR1 is deleted (NOT NULL violation). The end state is the same as the card's.
- **Checks done** (scratch folder `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc1e\aisvc\`, all my own files):
  - `--runxfail` with my plugin `thencheck.py`: each of the 43 strict xfails fails inside the `# Then N` block that its card's "Fails today on" names (43/43). The failures are the ones the cards describe: `DID NOT RAISE`, `AttributeError … get_sales_order`, metadata `{"invoice_id": None}`, `is_invoiced True`, missing `FOR UPDATE`, and so on.
  - Reference plugin `aisref.py`, loaded in-process with `-p aisref`: it replaces the service's delete / revert / resync / confirm / void with the approved behaviour (all the bugs fixed, locks included) and `VoidInvoiceRequest` with one that rejects a blank note. Under it, with `--runxfail`: **142 passed**.
  - 3 plain runs: 106 passed, 43 xfailed each time (rev 3). Not flaky.
  - `ruff check` and `ruff format --check` clean; LF line endings; no unused test arguments (X-22 takes the standing rows through `usefixtures`).

## Discrepancies
| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
| DISCREPANCY-1 (**resolved**, cases rev 2a: L-12 now reads `e["id"]`, as the test already did) | AIS-L-12 | pass, `[e.id for e in result]` | `AttributeError: 'dict' object has no attribute 'id'`: `get_events` returns dicts (`invoice_event_dao.get_by_invoice` builds `{"id": …, "event_type": …, "performed_by_name": …}`) | the code matches the spec ("the manager's lists"); only the card's attribute syntax is wrong | Card wording. The test reads `e["id"]` and compares the same values the card gives, so it is still a `pass` test with no marker. **Route to the case designer**: write `e["id"]` in L-12 Then 1–2. |

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 198 | dead | `list_accounts_hub_page` body. The spec's Q8 says remove it (dead-code checklist); there is no card. |
| 399–400 | unreachable (today) | The sales-order item mapping in `resync_items`. The line before it (`sales_manager.get_sales_order`) always raises `AttributeError` (BUG-2963), so the mapping never runs. S-17 covers it once BUG-2963 is fixed. |

Branch coverage: 151 statements, 3 missed; 30 branches, 0 partial.

## Factories added
None. No changes are needed to `factories.py` or `conftest.py`.

## Proposed bugs
None. No new bug found (BUG-2970 and BUG-2971 are unused).

## Notes for maintainers
- **When a bug is fixed**, its strict xfails XPASS (and fail). Remove the marker for: BUG-2962 (S-25, K-15, K-38, X-08, X-25), BUG-2963 (S-17…19), BUG-2964 (S-20…24), BUG-2965 (K-30…33, K-35), BUG-2966 (X-17, X-18, X-20), BUG-2967 (X-15, X-23, X-24), BUG-2968 (D-04), BUG-2969 (K-18…23), BUG-2732 (D-10…12), BUG-639 (D-07), BUG-1202 (K-09), BUG-2730 (D-09, V-05), BUG-2731 (X-13), BUG-2733 (V-06), BUG-2736 (V-04), BUG-2788 (X-14), BUG-626 (X-22).
- **Notification preview (K-35)**: `approval_notification_service.ORDER_PREFIX` has no `sales_order` entry today, so `notify_invoice_action` would write `sales order #<id>`, not `SO-<id>`, and it does not add a sales order's approvers. The BUG-2965 / BUG-1205 fix has to cover both. The reference plugin writes these notifications itself.
- **`x_gone` after `committed:` is weak (card-design note; answered in cases rev 3 by `X not in db` on C-02, C-03, U-03, V-02, X-26).** The test's own `db.rollback()` runs before x_gone. It drops the uncommitted X even when the service forgot to roll back, so `x_gone` alone cannot catch a missing rollback. In the error cards it is the `session clean` and `nothing written` checks that can catch it. Worth raising with the case designer when TC3 is next revised.
- **Lock-card parser**: `_from_names` reads only the first top-level `FROM`. A SELECT with a subquery in its column list could be misread. Today's statements have none.
- **Shared database**: the counts and `notes()` cover all workspaces. This is safe while other agents roll back too; one committed row from another run would break `notes() == []` and the counts.
- `StarletteDeprecationWarning` (`HTTP_422_UNPROCESSABLE_ENTITY`) comes from `purchase_order_manager.py`, not from the tests.

## Revision history
- 2026-11-22 — cases rev 2a (wording only): L-12 reads `e["id"]`. The test already did, so no test change; DISCREPANCY-1 marked resolved. Re-checked: 3 runs 99 passed / 43 xfailed, `--runxfail` 43/43 on the named Then line, reference plugin `aisref` + `--runxfail` 142 passed, ruff clean, LF.
- 2026-11-22 — cases rev 3 (verifier findings 1–5). C-02, C-03, U-03, V-02 gain Then 4 `x not in db` right after the call (later Then lines renumbered; `mk_x` now keeps the object). New D-16 / S-29 (spies: one commit, no rollback), D-17 / D-18 (W0 / W2 PO pointing at the draft keeps its flags, no event), X-26 (**failing unconfirm**: `patch.object(ais_mod.purchase_order_manager, "unconfirm_sections_after_invoice_void", side_effect=E)` with a rollback spy; `ais_mod` = `import app.services.account_invoice_service`), X-27 / X-28 (W0 / W2 PO with a received line neither blocks nor is touched). K-35 marker `@xfail(2965, 1205)` (`xfail()` now takes several bug numbers and names them all). K-31: one approved + one pending approver, expects `Requires 2 approval(s); 1 so far`. K-38: two approved approvers, new Then 4 `rec.reads("sales_order_approvers")`. `Recorder.before` now fails when U is never read. X-09 comment names steps 6 and 7. Result: 3 runs 106 passed / 43 xfailed, 98% branch (gaps unchanged); `--runxfail` 43/43 on the named Then line (K-31 Then 1, K-35 Then 2, K-38 Then 2); reference plugin `aisref` + `--runxfail` 149 passed; ruff clean, LF.
- 2026-11-22 — verifier item: S-29 now calls `db.rollback()` before Then 4, so the `committed:` line count reads committed state; S-29 passes plainly and under `aisref`.
