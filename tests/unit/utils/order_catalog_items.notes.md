# Execution notes — `app/utils/order_catalog_items.py`

> Cases: `tests/unit/utils/order_catalog_items.cases.md` (revision 4) · Tests: `tests/unit/utils/test_order_catalog_items.py` · Source commit: e48a092
> Result: 45 passed · 2 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/utils/test_order_catalog_items.py -q -p no:cacheprovider --cov=app.utils.order_catalog_items --cov-branch --cov-report=term-missing`

## How the tests are built
- **Conventions → helpers** (top of the test file, each commented with its convention):
  - W1/W2 → fixtures `w1`, `w2` (`make_workspace`).
  - F1/F2 → fixtures `f1`, `f2` via local builder `mk_factory(db, ws, name)` (both in W1).
  - Items SR/OB/A/B/SW/EN → fixtures of the same names via local `mk_item(db, ws, name, active=)` (insert + flush). EN is inserted with `name=""` directly, as the cases require (legacy/unguarded row).
  - UNKNOWN → module constant `987654321`.
  - `P(item, factory, min, for_sale, deleted, active)` → local builder `P(db, ...)`; workspace = the item's workspace (W1 unless stated). `qty=0`.
  - Lines → `uline(item_or_id)` / `mline(item_or_id, qty)` dicts; accessors `get_item_id` / `get_quantity`.
  - SENTINEL → module `object()`; `Recorder` accessors record every line passed and raise `AssertionError("sentinel read")` on SENTINEL (OCI-U-06, U-09, M-21).
  - "DB unchanged" → `snap(db, w1, w2)`: `expire_all()` then re-query of all `items` and `products` columns relevant to the module in W1/W2, compared before vs after. Item fields are also re-read with `reread_item` where the case names them (U-07, U-15, U-16).
- **Parametrized:** OCI-M-04 / OCI-M-05 (same setup, quantity differs), each its own `pytest.param` id.
- **OCI-M-23 (rev 3):** uses a local `recording_quantity` accessor (records lines, no sentinel) plus the plain `get_item_id`, with a generator input; asserts the only line passed to `get_quantity` is the SR line.
- **OCI-M-24 (rev 4):** builds only `P(A, F1, min=5)` (no product for B), calls with a single B line of qty 1 and asserts `None` plus DB unchanged via `snap()` — isolates the product lookup's `item_id` filter.
- **Mocks:** none (spec: no externals, no races, time not mocked).
- **DB-error cases:** none in this module (OCI-M-22's `TypeError` is raised in Python before any write, so no savepoint is needed).
- **xfail honesty:** checked with `--runxfail`: OCI-U-15 fails on the detail equality (`' appears more than once on this order'`), OCI-D-06 on the return equality (`' is already on this order'`) — the "fails today on" assertions.
- Stability: 3 of 3 runs gave 45 passed · 2 xfailed.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage. (The dead `detail_template` branch is an `or` expression, not a coverage branch, so it shows as covered even though no test passes it; it is listed as dead in the spec's Not specified.)

## Factories added
None (batch mode: `tests/unit/factories.py` is not edited). Candidates to promote later: `mk_factory` → `make_factory`, `mk_item` → `make_item` (also used locally in `tests/unit/dao/test_item.py` as `mk`), and `P` → `make_product`.

## Notes for maintainers
- **When BUG-220 is fixed**, OCI-U-15 and OCI-D-06 will XPASS (strict) → remove their markers. OCI-U-16 and OCI-D-07 stay green before and after the fix.
- **When the `detail_template` parameter is removed** (dead code, `order_catalog_items.deadcode-staging.md`), no test changes are needed; none passes it.
- Warning noise: the source uses `status.HTTP_422_UNPROCESSABLE_ENTITY`, which Starlette reports as deprecated; the numeric status is still 422 and the tests compare `422`.

## Revision history
- **Revision 3 (cases rev 3, 2026-09-29):** added `test_oci_m_23__free_text_before_catalog_line_is_skipped_not_stop` for new case OCI-M-23 (verifier Finding 1, case-missing: MOQ free-text `continue` → `return`/`break` survivor at source L60). No existing test changed; no retired IDs; no test-weakness findings were routed to the executor. Result 44 passed · 2 xfailed, 100% branch coverage, stable over 3 runs.
- **Revision 4 (cases rev 4, 2026-09-29):** added `test_oci_m_24__other_items_product_not_applied` for new case OCI-M-24 (MOQ R3 "same `item_id`" filter checked directly). Module docstring revision reference corrected (was "revision 2", cosmetic note from the verifier). No existing test changed; no retired IDs; no test-weakness findings routed. Result 45 passed · 2 xfailed, 0 discrepancies, 100% branch coverage (31 stmts, 12 branches, 0 missed), stable over 3 runs; `--runxfail` still fails only OCI-U-15 and OCI-D-06 on their documented assertions.
