# Execution notes — `app/services/item_orders_service.py`

> Cases: `tests/unit/services/item_orders_service.cases.md` (revision 3) · Tests: `tests/unit/services/test_item_orders_service.py` · Source commit: e48a092
> Result: 92 passed · 36 xfailed (33 strict, 3 non-strict) · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `COVERAGE_FILE=<private> .venv/Scripts/python.exe -m pytest tests/unit/services/test_item_orders_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.item_orders_service --cov-branch --cov-report=term-missing`

## How the tests are built
- **Standing rows**: the autouse fixture `st` builds W0, W1, W2, U1. Then, for each workspace in the order W0, W1, W2, it builds Fx, Sx, ACx, WTx, Ix, Mx, PJx and Cx. It ends with I2 and S2 in W1. Each row is flushed on its own, so in every table the W0 ids are below the W1 ids, which are below the W2 ids. Card names map to lower case: `F1` is `st.f1`, `AC9` is `st.ac9`, `I0` is `st.i0`.
- **Order builders**: `mk` (a `Builder`) has `po`, `pl`, `to`, `tl`, `so`, `sl`, `wo` and `wl`, with the Conventions defaults.
  - "W0 x" is `w0=True` and "W2 x" is `w2=True`. `Builder._v` swaps in that workspace's W, F, S, AC and WT.
  - Keyword arguments are the card's "but" columns.
  - `pl` and `tl` number their lines 1, 2, … per order. `sl(S, None, …)` makes a free-text line.
  - The voided PO and the deleted work order are the dicts `mk.voided` and `mk.deleted_wo`, spread with `**`.
  - `seven_pos` builds the seven POs of G-24 … G-28. `_four_types` builds Given 1–8 of G-07 … G-10, and `_pre_post_pos` the Given of G-13 and G-14.
- **Calls**: `orders(db, st, **kw)` is the standard `get_orders_for_item(workspace_id=W1, item_id=I1, limit=1000)`. Cards that name `skip` or `limit`, or another item, call `svc.get_orders_for_item` directly.
- **Named checks**: `nums`, `numset` and `row(result, n)` follow Conventions and read numbers through `base(x)`, which drops the `GN` suffix. `row` unpacks exactly one match. The direct helper cards that read a sales or transfer `order_number` (S-11), and the G-05 list check, compare `base(...)`.
- **GN(n)** = `f"{n}-{os.getpid()}"` (Conventions, Parallel runs): the `to` and `so` builders store `GN(n)` for the card's number. PO and work order numbers are stored as written.
- **recorder**: `recorder(db)` returns `(stmts, stop)` and listens with `before_cursor_execute` on `db.connection()`. `stop()` runs right after the When; in G-02 that is right after the `pytest.raises` block.
- **spies** (G-34): `patch.object(db, "commit"/"rollback", wraps=…)` around the When. The commit point is `db.commit()`, which only releases a savepoint under the `db` fixture.
- **Fixed-input patch** (G-37 only): `patch.object(ItemOrdersService, "_purchase_rows", return_value=[RK(1), RK(2), RK(3)])`. Nothing else is patched. The spec lists no externals.
- **xfail markers**: `bug(*ids, strict=True)` sets the reason to "BUG-NNN: <title from bugs.md>".
  - The six BUG-2550-only cards (G-06, G-10, G-23, W-03, W-04, W-08) use `BUG_2550 = xfail(strict=True, raises=AttributeError)`. Today the When raises `AttributeError: 'str' object has no attribute 'value'` (source line 460), which is what their "Fails today on" says. `raises=` pins the xfail to that cause.
  - W-05 (BUG-2552) and W-06 (BUG-2553) also crash today with that `AttributeError`, but they carry no `raises=`. With BUG-2550 fixed alone they must stay xfail, failing on Then 1, and not become hard failures.
- **Lint**: the file carries `# ruff: noqa: DTZ001, FURB157, RUF032`, because the cards prescribe naive datetimes, `Decimal("3")`-style string literals and `Decimal(0.1)` (DC-03).

## Verification runs
- **10 plain runs**: 92 passed and 36 xfailed in every run. No XPASS of the non-strict G-21/G-22/G-36 and no flake.
- **`--runxfail`**: all 36 fail. A check script (scratch `check_then.py`) maps each failing line to its `# Then N` block and compares it with the card:
  - 28 fail on the exact Then line their card names (WP-07…09, DL-11…14, G-21, G-22, G-36, G-37, P-13…19, T-06, S-07…09, OQ33-01/02/03/05/07/09).
  - 8 fail in the When call itself with the `AttributeError` at `item_orders_service.py:460`, before Then 1: G-06, G-10, G-23, W-03, W-04, W-05, W-06, W-08. Their cards say "Then 1 (the call raises AttributeError…)".
- **Reference plugin** (scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsupe\io\ios_ref_fix.py`):
  - It is loaded with `PYTHONPATH=<scratch> -p ios_ref_fix`, with `IOS_FIX=all` or a comma list of bug numbers. In `pytest_configure`, before the test module is imported, it replaces `_weighted_unit_price`, `_build_po_destination_labels`, the four row helpers and `get_orders_for_item`.
  - BUG-2554: `quantize(0.01, ROUND_HALF_UP)`.
  - BUG-2490: divide by the priced quantity.
  - BUG-2491: the line total is shown whenever a line is priced, and always for sales.
  - BUG-2550: `status_name` = the stored text. BUG-2552: drops `VOIDED`. BUG-2553: drops deleted work orders.
  - BUG-2551: sort key `(date, created_at, -type_rank, order_id)`, reversed.
  - BUG-2555: foreign account or status drops the order. A foreign factory, machine, component, or component under a foreign project gets no label and drops the PO. A missing id keeps the fallback label.
- **All fixes with `--runxfail`**: 128 passed.
- **Each fix alone, plain run**: 92 pass cards pass every time. The flipped cards are:
  - 2550 → G-06, G-10, G-23, W-03, W-04, W-08
  - 2551 → G-37, plus XPASS of the non-strict G-21, G-22, G-36
  - 2552 → W-05; 2553 → W-06
  - 2554 → WP-07…09, P-19, S-09
  - 2555 → DL-11…14, P-13…18, T-06, S-07, S-08
  - 2490 → OQ33-03 only; 2491 → OQ33-05 only. The pairs are below.
- **`ruff check`**: clean. The file is LF only (0 CR bytes). A check script confirms that all 128 card IDs appear exactly once, in card order, with matching docstring IDs, and that no test argument goes unused.

## Discrepancies
None. DISCREPANCY-1…3 (OQ33-01, 02 and 09 each needed a second bug fixed) were closed by cases revision 3, which names both bugs on each Expect line. The markers now read `BUG-2490; BUG-2554`, `BUG-2491; BUG-2554` and `BUG-2490; BUG-2491`.

## Coverage gaps
None — 100% branch coverage (131 statements, 56 branches). The `date.min` fallback in the sort key is an `or` expression. coverage.py does not count it as a branch. The spec records it as unreachable, because all four date expressions are non-null.

## Factories added
None. The builders are local (`Builder` in the test file).

## Notes for maintainers
- **Parallel runs**: `transfer_number` and `sales_order_number` are unique across **all** workspaces. Since revision 3 they are stored with the per-process `GN` suffix, so two processes never insert the same number. `po_number` and `work_order_number` are unique per workspace only.
- **Explicit ids** `XID(k)` go into `purchase_orders`, `transfer_orders` and `sales_orders` (G-18, G-21, G-22, G-35, G-36). They are per process and rolled back.
- **When a BUG is fixed**, its strict cards XPASS and fail the run. Remove the marker then:
  - BUG-2550 → G-06, G-10, G-23, W-03, W-04, W-08. Also drop `BUG_2550`'s `raises=`.
  - BUG-2551 → G-37. Also remove the non-strict marker of G-21, G-22 and G-36.
  - BUG-2552 → W-05; BUG-2553 → W-06.
  - BUG-2554 → WP-07…09, P-19, S-09.
  - BUG-2555 → DL-11…14, P-13…18, T-06, S-07, S-08.
  - BUG-2490 → OQ33-03; BUG-2491 → OQ33-05.
  - BUG-2490 with BUG-2554 → OQ33-01, OQ33-07. BUG-2491 with BUG-2554 → OQ33-02. BUG-2490 with BUG-2491 → OQ33-09.
- **BUG-2551 fix**: the tie-break must go in the Python sort key, not in an `ORDER BY` (spec R13). G-37 fails on every run until then, while G-21, G-22 and G-36 may pass by chance today.
- **BUG-937 fix** (spec FU-1): G-04 guards that a deleted item still answers. If `get_item` starts hiding deleted items, G-04 fails until this service passes `include_deleted=True`.

## Revision history
- **2026-11-10 — cases revision 2.** First implementation: 128 cases, 92 passed and 36 xfailed, 100% branch coverage.
- **2026-11-10 — cases revision 3.** Changes:
  - The OQ33-01, 02 and 09 markers now name both bugs, as their new Expect lines do (2490+2554, 2491+2554, 2490+2491). This closes DISCREPANCY-1…3.
  - Added the `GN(n)` and `base(x)` helpers. The `to` and `so` builders store `GN(n)`.
  - `nums`, `numset` and `row` read through `base()`, and so do the G-05 list check and the S-11 direct check.
  - Re-checked:
    - 3 plain runs gave 92 passed and 36 xfailed each time.
    - `--runxfail` gave 36 failed, on the same Then lines as before (the 8 crash-in-When cards included).
    - The reference plugin with all fixes and `--runxfail` gave 128 passed. Each OQ33 card flips only when both of its bugs are fixed: 2490 alone, 2491 alone, 2554 alone and every pair were checked.
    - Branch coverage is 100%. ruff is clean and the file is LF only.
