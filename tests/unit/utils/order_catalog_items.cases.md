# Test cases — `app/utils/order_catalog_items.py`

> **Spec:** `tests/unit/utils/order_catalog_items.spec.md` (source commit `e48a092`)
> **Status:** READY
> **Counts:** 47 cases · 45 expected-to-pass · 2 expected-to-fail (bugs) · 0 deferred
> **Revision:** 4 — re-run on unchanged spec (Gap log still G1, G2; verifier PASS, no findings). Added OCI-M-24: direct check of the MOQ R3 "same `item_id`" filter (a product for another item in the same factory must not apply), previously covered only indirectly by OCI-M-20.
> **Revision 3:** verifier Finding 1 (case-missing, MOQ R2 free-text `continue` → `return`/`break` survivor): added OCI-M-23, a free-text line BEFORE a catalog line that must still be checked. Spec unchanged since revision 2.
> **Revision 2:** spec Gap log G1 (`products.min_order_qty` is `Integer`, renders as a plain integer) and G2 (BUG-220: empty item name falls back to `Item #<id>` in the duplicate and "already on order" messages). MIN(p) replaced by literal integers; added OCI-U-15/16 and OCI-D-06/07.

## Reviewer summary
- **Per callable:** `assert_unique_catalog_item_ids` 16 cases (1 bug) · `catalog_item_already_on_order_detail` 7 cases (1 bug) · `assert_meets_minimum_order_quantities` 24 cases (0 bug).
- **Notable design choices:**
  - "Lines after the failing one are not examined" (unique R4, MOQ R8) is checked with a sentinel line whose accessor raises `AssertionError` if it is ever read; the expected `HTTPException` must surface instead.
  - "Consumed once" is exercised by passing generators (not lists) in several cases.
  - The `<min_order_qty>` part of the 422 detail is now a literal plain integer (e.g. `5`), per spec R7 / G1.
  - Cross-workspace MOQ isolation is done by calling with W2 while the product lives in W1 (same factory id and item id), not by building a cross-workspace product.
  - BUG-220 (empty item name) is split: xfail cases assert the `Item #<id>` fallback (OCI-U-15, OCI-D-06); passing cases keep regression protection for what holds today and after the fix — the 409 is still raised / a string is still returned, with the fixed suffix (OCI-U-16, OCI-D-07).
  - The dead `detail_template` parameter is never passed (spec "Not specified").
  - OCI-M-24 (rev 4) isolates the product lookup's item filter: only another item's product exists in the factory, so the line must pass.
  - OCI-M-23 (rev 3) puts a free-text line before a catalog line so "skip" cannot be implemented as "stop" (mirrors OCI-U-14 for the unique check).
- **Needs a decision:** None.

## Conventions for this module
- **Abbreviations:** `OCI` = `order_catalog_items`; `U` = `assert_unique_catalog_item_ids`; `D` = `catalog_item_already_on_order_detail`; `M` = `assert_meets_minimum_order_quantities`.
- **W1, W2** = two workspaces. **F1, F2** = two factories in W1 (F2 only where stated).
- **Items** (catalog `items` rows, flushed so ids exist; other required columns any value):
  - **SR** = item `"Steel Rod"` in W1, `is_active=True`.
  - **OB** = item `"Old Bolt"` in W1, `is_active=False`.
  - **A** = item `"Alpha"` in W1; **B** = item `"Bravo"` in W1 (both active).
  - **SW** = item `"Secret Widget"` in W2 (active).
  - **EN** = item with name `""` (empty string) in W1.
  - **UNKNOWN** = `987654321`, an id with no item in any workspace.
- **Products** (`products` rows): written as `P(item, factory, min, for_sale=True, deleted=False, active=True)` in W1 unless stated; other required columns any value. The DB unique constraint on (`workspace_id`, `item_id`, `factory_id`, `is_available_for_sale`) is respected by every setup.
- `products.min_order_qty` is an `Integer` column; in expected 422 details it appears as a plain integer literal (e.g. `5`, never `5.00`).
- **EN** rows (empty name) are inserted directly into the DB (legacy/unguarded rows; HR-1 is a schema-level guard and does not stop a direct insert).
- **Lines:** unique-check lines are dicts `{"item_id": <id or None>}` with `get_item_id=lambda e: e["item_id"]`. MOQ lines are dicts `{"item_id": ..., "qty": ...}` with `get_item_id=lambda e: e["item_id"]`, `get_quantity=lambda e: e["qty"]`. Quantities are `Decimal` unless stated.
- **SENTINEL** = a line object whose `get_item_id` (and `get_quantity`) access raises `AssertionError("sentinel read")` — implemented by making the accessor raise when it receives that object. A case using it records every line passed to the accessor.
- **"DB unchanged"** = row counts and field values of `items` and `products` in W1/W2 equal those recorded before the call.
- **409/422 checks**: `exc.status_code` and exact `exc.detail` string.
- Externals mocked: none. Race simulations: none. Time: not mocked.

## `assert_unique_catalog_item_ids`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| OCI-U-01 | R1 | boundary | W1, no setup rows | `assert_unique_catalog_item_ids(session, W1, [], get_item_id=...)` | returns `None`; no exception | pass |
| OCI-U-02 | R1 | boundary | W1 | entries = empty generator `(x for x in [])` | returns `None` | pass |
| OCI-U-03 | R2 | boundary | W1 | entries = `[{"item_id": None}] * 3` (three free-text lines) | returns `None` (free-text lines never duplicates of each other) | pass |
| OCI-U-04 | R2, R3 | happy | W1 | entries = `[None, 101, None, 102, None]` as lines (ids need no rows) | returns `None` | pass |
| OCI-U-05 | R2, R5, R6 | boundary | W1, no item with id 0 | entries = `[{"item_id": 0}, {"item_id": 0}]` | raises `HTTPException`, status 409, detail `"Item #0 appears more than once on this order"` (0 is not skipped) | pass |
| OCI-U-06 | R3 | happy | W1 | entries = generator of 50 lines with ids 1..50 (all distinct); accessor records calls | returns `None`; accessor called exactly 50 times, with each id once | pass |
| OCI-U-07 | R4, R5, R6, Errors row | error | SR in W1 | entries = `[SR, SR]` | raises `HTTPException` 409, detail exactly `"Steel Rod appears more than once on this order"`; DB unchanged (SR still name "Steel Rod", active) | pass |
| OCI-U-08 | R4 | boundary | A, B in W1 | entries = `[A, B, B, A]` | raises 409, detail `"Bravo appears more than once on this order"` (B's second occurrence, index 2, precedes A's at index 3) | pass |
| OCI-U-09 | R4 | boundary | A in W1 | entries = generator yielding `A, A, SENTINEL` | raises `HTTPException` 409 (not `AssertionError`), detail `"Alpha appears more than once on this order"`; recorded accessor calls are exactly the two A lines — SENTINEL never read | pass |
| OCI-U-10 | R5 | boundary | OB in W1 (`is_active=False`) | entries = `[OB, OB]` | raises 409, detail `"Old Bolt appears more than once on this order"` | pass |
| OCI-U-11 | R5 | boundary | W1; no item UNKNOWN | entries = `[UNKNOWN, UNKNOWN]` | raises 409, detail `"Item #987654321 appears more than once on this order"` | pass |
| OCI-U-12 | R5 | isolation | SW in W2 | call with workspace **W1**, entries = `[SW.id, SW.id]` | raises 409, detail `f"Item #{SW.id} appears more than once on this order"`; `"Secret Widget"` not a substring of detail | pass |
| OCI-U-13 | R5 | isolation | SW in W2 | call with workspace **W2**, entries = `[SW.id, SW.id]` | raises 409, detail `"Secret Widget appears more than once on this order"` | pass |
| OCI-U-14 | R2, R4 | boundary | SR in W1 | entries = `[SR, None, SR]` | raises 409, detail `"Steel Rod appears more than once on this order"` (free-text line between does not break duplicate detection) | pass |
| OCI-U-15 | R5a [BUG-220], R6 | bug | EN (name `""`) in W1 | call with W1, entries = `[EN, EN]` | raises `HTTPException` 409, detail exactly `f"Item #{EN.id} appears more than once on this order"`; detail does not start with a space; DB unchanged (EN name still `""`) | xfail BUG-220 — fails today on: detail is `" appears more than once on this order"` |
| OCI-U-16 | R4, R5a, R6 | boundary | EN (name `""`) in W1 | call with W1, entries = `[EN, EN]` | raises `HTTPException` with status 409 (not another exception); detail ends with `" appears more than once on this order"`; DB unchanged (EN name still `""`) — assertions independent of BUG-220 | pass |

## `catalog_item_already_on_order_detail`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| OCI-D-01 | R1 | happy | SR in W1 | `catalog_item_already_on_order_detail(session, item_id=SR.id, workspace_id=W1)` | returns exactly `"Steel Rod is already on this order"`; DB unchanged | pass |
| OCI-D-02 | R1 | boundary | OB in W1 (`is_active=False`) | `item_id=OB.id, workspace_id=W1` | returns `"Old Bolt is already on this order"` | pass |
| OCI-D-03 | R2 | boundary | W1; no item UNKNOWN | `item_id=987654321, workspace_id=W1` | returns `"Item #987654321 is already on this order"`; no exception | pass |
| OCI-D-04 | R2 | isolation | SW in W2 | `item_id=SW.id, workspace_id=W1` | returns `f"Item #{SW.id} is already on this order"`; `"Secret Widget"` not in result | pass |
| OCI-D-05 | R1 | isolation | SW in W2 | `item_id=SW.id, workspace_id=W2` | returns `"Secret Widget is already on this order"` | pass |
| OCI-D-06 | R3 [BUG-220] | bug | EN (name `""`) in W1 | `item_id=EN.id, workspace_id=W1` | returns exactly `f"Item #{EN.id} is already on this order"`; result does not start with a space; DB unchanged | xfail BUG-220 — fails today on: returns `" is already on this order"` |
| OCI-D-07 | R1, R3 | boundary | EN (name `""`) in W1 | `item_id=EN.id, workspace_id=W1` | returns a `str` (no exception) ending with `" is already on this order"` — assertions independent of BUG-220 | pass |

## `assert_meets_minimum_order_quantities`

All calls: `assert_meets_minimum_order_quantities(session, <ws>, <factory>, entries, get_item_id=..., get_quantity=...)`; `<ws>` = W1 and `<factory>` = F1 unless stated.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| OCI-M-01 | R1 | boundary | W1, F1 | entries = `[]` | returns `None` | pass |
| OCI-M-02 | R2 | boundary | W1, F1 | entries = `[{"item_id": None, "qty": Decimal("-3")}, {"item_id": None, "qty": Decimal("0")}]`; `get_quantity` raises `AssertionError` if called | returns `None`; `get_quantity` never called | pass |
| OCI-M-03 | R3, R6, R7, Errors row | error | SR; `P(SR, F1, min=5)` | entries = `[{SR, Decimal("4.5")}]` | raises `HTTPException` 422, detail exactly `"Minimum order quantity for Steel Rod is 5 (requested 4.5)"` (min rendered `5`, not `5.00`); DB unchanged | pass |
| OCI-M-04 | R6 | boundary | SR; `P(SR, F1, min=5)` | entries = `[{SR, Decimal("5")}]` | returns `None` (equal passes) | pass |
| OCI-M-05 | R6 | boundary | SR; `P(SR, F1, min=5)` | entries = `[{SR, Decimal("6")}]` | returns `None` | pass |
| OCI-M-06 | R6 | boundary | SR; `P(SR, F1, min=5)` | entries = `[{SR, Decimal("4.99")}]` | raises 422, detail `f"Minimum order quantity for Steel Rod is 5 (requested 4.99)"` | pass |
| OCI-M-07 | R4 | boundary | SR; no product for SR anywhere | entries = `[{SR, Decimal("1")}]` | returns `None` | pass |
| OCI-M-08 | R3, R4 | isolation | SR; `P(SR, F2, min=5)` only | call with factory **F1**, entries = `[{SR, Decimal("1")}]` | returns `None` (other side: OCI-M-03) | pass |
| OCI-M-09 | R3, R4 | isolation | SR; `P(SR, F1, min=5)` in W1 | call with workspace **W2**, factory F1, entries = `[{SR, Decimal("1")}]` | returns `None` | pass |
| OCI-M-10 | R3, R4 | boundary | SR; `P(SR, F1, min=5, for_sale=False)` only | entries = `[{SR, Decimal("1")}]` | returns `None` | pass |
| OCI-M-11 | R3, R4 | soft-delete | SR; `P(SR, F1, min=5, deleted=True)` only | entries = `[{SR, Decimal("1")}]` | returns `None` | pass |
| OCI-M-12 | R3 | boundary | SR; `P(SR, F1, min=5, active=False)` | entries = `[{SR, Decimal("1")}]` | raises 422, detail `f"Minimum order quantity for Steel Rod is 5 (requested 1)"` (`is_active` ignored) | pass |
| OCI-M-13 | R3 | boundary | SR; `P(SR, F1, min=100, for_sale=False)` and `P(SR, F1, min=5, for_sale=True)` | entries = `[{SR, Decimal("10")}]` | returns `None` (the not-for-sale product's 100 is not used) | pass |
| OCI-M-14 | R3, R7 | boundary | same as OCI-M-13; `p` = the for-sale product | entries = `[{SR, Decimal("4")}]` | raises 422, detail `f"Minimum order quantity for Steel Rod is 5 (requested 4)"` where `p` is the for-sale product (min 5, not 100) | pass |
| OCI-M-15 | R5 | boundary | SR; `P(SR, F1, min=None)` | entries = `[{SR, Decimal("0")}]` | returns `None` | pass |
| OCI-M-16 | R5 | boundary | SR; `P(SR, F1, min=0)` | entries = `[{SR, Decimal("-1")}]` | returns `None` | pass |
| OCI-M-17 | R5, R6 | boundary | SR; `P(SR, F1, min=1)` | entries = `[{SR, Decimal("0")}]` | raises 422, detail `f"Minimum order quantity for Steel Rod is 1 (requested 0)"` (other side of OCI-M-16: smallest positive min is enforced) | pass |
| OCI-M-18 | R7 | boundary | EN (name `""`); `P(EN, F1, min=5)` | entries = `[{EN, Decimal("1")}]` | raises 422, detail `f"Minimum order quantity for Item #{EN.id} is 5 (requested 1)"` | pass |
| OCI-M-19 | R7 | boundary | SR; `P(SR, F1, min=5)` | entries = `[{SR, Decimal("4.50")}]` | raises 422, detail ends with `"(requested 4.50)"` and equals `f"Minimum order quantity for Steel Rod is 5 (requested 4.50)"` (quantity rendered with `str()`, trailing zero kept) | pass |
| OCI-M-20 | R8 | boundary | A with `pA = P(A, F1, min=5)`; B with `pB = P(B, F1, min=10)` | entries = generator yielding `[{A, Decimal("6")}, {B, Decimal("1")}, {A, Decimal("1")}]` | raises 422, detail `f"Minimum order quantity for Bravo is 10 (requested 1)"` (first failing line, not the later A line) | pass |
| OCI-M-21 | R8 | boundary | A; `P(A, F1, min=5)` | entries = generator yielding `{A, Decimal("1")}`, then SENTINEL | raises `HTTPException` 422 (not `AssertionError`); recorded accessor calls include only the A line — SENTINEL never read | pass |
| OCI-M-22 | R9 | error | SR; `P(SR, F1, min=5)` | entries = `[{"item_id": SR.id, "qty": None}]` | raises `TypeError` (not `HTTPException`); DB unchanged | pass |
| OCI-M-23 | R2, R6, R8 | boundary | SR; `P(SR, F1, min=5)` | entries = generator yielding `{"item_id": None, "qty": Decimal("1")}` then `{"item_id": SR.id, "qty": Decimal("1")}`; `get_quantity` records the lines it receives | raises `HTTPException` 422, detail exactly `"Minimum order quantity for Steel Rod is 5 (requested 1)"` (the free-text line is skipped and checking continues to the catalog line after it); `get_quantity` received only the SR line; DB unchanged | pass |
| OCI-M-24 | R3, R4 | isolation | A, B in W1; `P(A, F1, min=5)` only (no product for B) | entries = `[{"item_id": B.id, "qty": Decimal("1")}]` | returns `None` (A's product in the same factory is not used for B; other side: OCI-M-20, where B's own min 10 applies); DB unchanged | pass |

## Deferred to other specs
None.

## Spec gaps
None. (Previous gaps 1–2 closed by spec Gap log G1, G2.)

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `assert_unique_catalog_item_ids` | R1 | OCI-U-01, OCI-U-02 |
| `assert_unique_catalog_item_ids` | R2 | OCI-U-03, OCI-U-04, OCI-U-05, OCI-U-14 |
| `assert_unique_catalog_item_ids` | R3 | OCI-U-04, OCI-U-06 |
| `assert_unique_catalog_item_ids` | R4 | OCI-U-07, OCI-U-08, OCI-U-09, OCI-U-14 |
| `assert_unique_catalog_item_ids` | R5 | OCI-U-05, OCI-U-07, OCI-U-10, OCI-U-11, OCI-U-12, OCI-U-13 |
| `assert_unique_catalog_item_ids` | R5a [BUG-220] | OCI-U-15 (xfail), OCI-U-16 |
| `assert_unique_catalog_item_ids` | R6 | OCI-U-05, OCI-U-07, OCI-U-15, OCI-U-16 |
| `assert_unique_catalog_item_ids` | Errors: duplicate → 409 | OCI-U-07 |
| `catalog_item_already_on_order_detail` | R1 | OCI-D-01, OCI-D-02, OCI-D-05 |
| `catalog_item_already_on_order_detail` | R2 | OCI-D-03, OCI-D-04 |
| `catalog_item_already_on_order_detail` | R3 [BUG-220] | OCI-D-06 (xfail), OCI-D-07 |
| `assert_meets_minimum_order_quantities` | R1 | OCI-M-01 |
| `assert_meets_minimum_order_quantities` | R2 | OCI-M-02, OCI-M-23 |
| `assert_meets_minimum_order_quantities` | R3 | OCI-M-03, OCI-M-08, OCI-M-09, OCI-M-10, OCI-M-11, OCI-M-12, OCI-M-13, OCI-M-14, OCI-M-24 |
| `assert_meets_minimum_order_quantities` | R4 | OCI-M-07, OCI-M-08, OCI-M-09, OCI-M-10, OCI-M-11, OCI-M-24 |
| `assert_meets_minimum_order_quantities` | R5 | OCI-M-15, OCI-M-16, OCI-M-17 |
| `assert_meets_minimum_order_quantities` | R6 | OCI-M-03, OCI-M-04, OCI-M-05, OCI-M-06, OCI-M-17, OCI-M-23 |
| `assert_meets_minimum_order_quantities` | R7 | OCI-M-03, OCI-M-14, OCI-M-18, OCI-M-19 |
| `assert_meets_minimum_order_quantities` | R8 | OCI-M-20, OCI-M-21, OCI-M-23 |
| `assert_meets_minimum_order_quantities` | R9 | OCI-M-22 |
| `assert_meets_minimum_order_quantities` | Errors: below min → 422 | OCI-M-03 |
