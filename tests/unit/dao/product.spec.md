# Spec — `app/dao/product.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Revision 2026-11-03 (owner's answer to cases gap 2):** the item summary hides stock of a removed item too, so it agrees with the product list. `get_by_item` R3c is rewritten and tagged [BUG-1338]; R3b now also covers the item. Cards to change: PRD-GT-16 (now an xfail), plus new cards for R3b's item parts.

> **Review round 2026-11-02.** **The owner's own answer:** Q1 — stock paths find and restore the deleted row, keeping its `qty`; `POST /products/` answers 409 (BUG-1336). **Delegated,** decided by Claude under the reviewer's delegation (2026-11-02): P1 `bug` (BUG-1335), P2 kept. None of these is the owner's own answer. The house-rule lines stand.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Things of a soft-deleted parent are hidden, their own rows untouched. One stock row per key (BUG-983). HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope; inventory DAO Q6 scope decision, Q8, Q9).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v_prod.py`, `v_more.py`, harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\proddao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints, indexes and referencing tables, including that the unique constraint **covers soft-deleted rows**; no `ORDER BY` in the lists; `get_by_item`'s order changing after an update under a forced sequential scan; the filters alone and together, `factory_id=0`; every read for a soft-deleted row, an inactive row, a row of a soft-deleted factory, a row of a removed item; `soft_delete` and `restore`, twice, on a live row; `deleted_at` under `America/New_York` and `Asia/Dhaka`; `create_product`, `apply_production_output`, `apply_sale_return`, `apply_sale_deduction` and `complete_batch` after a soft delete; `delete_product` with stock; `update_product` onto a taken bucket and with a negative `qty`; negative money through `create_product`; a factory soft-deleted before `create_product`; 101 rows, the cap, `limit=0`, negative values; `create` and `update` on the model. **Not run:** anything over HTTP; two concurrent transactions; the intended behaviour of the bugs below.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically

- **HR-6** `get_by_workspace` R6 — pages with no `ORDER BY`. This is the DAO's own paged query behind `GET /products/`, so the order has to be in the query. Intended: item name case-insensitive ascending, then row `id` ascending, before `skip` / `limit` (the stock page's order, BUG-701).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1325 (pattern `unordered-pagination`). Rules: `get_by_workspace` R6.
- **HR-6** `get_by_item` R4 — no `ORDER BY`. Verified: three rows came back `0, 3, 4`, and `3, 4, 0` after the first was updated. The only caller re-sorts by factory name. Intended: row `id` ascending (BUG-906 precedent).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1326 (pattern `unordered-pagination`). Rules: `get_by_item` R4.
- **Standing decision (soft-deleted parents hide children), HR-4** `get_by_workspace` R5a, R5b — a row of a soft-deleted factory and a row of a removed item are listed and take a place in the page (verified). Intended: not returned, the rows untouched; an inactive-but-live factory hides nothing (BUG-882, BUG-883 precedent).
**Answer:** bug — per HR-4 and BUG-882 / BUG-883 precedent (standing decision)
**Resolution:** BUG-1327 (pattern `join-ignores-soft-deleted`). Rules: `get_by_workspace` R5a, R5b, R5c.
- **Standing decision (soft-deleted parents hide children), HR-4** `get_by_item` R3a — a row of a soft-deleted factory is returned, so the item summary lists and adds up stock in a deleted factory (verified at the DAO). Intended: not returned, the row untouched (BUG-884 precedent). The item's own state was first left unread (inventory DAO Q6 scope decision); the owner overturned that for products on 2026-11-03: R3c, BUG-1338.
**Answer:** bug — per HR-4 and BUG-884 precedent (standing decision)
**Resolution:** BUG-1328 (pattern `join-ignores-soft-deleted`). Own ID: different method, different API surface (same split as BUG-882 / BUG-884). Rules: `get_by_item` R3a, R3b, R3c.

Checked and **not** a new line here: **HR-2, HR-3, HR-8** — no names, no free text used for grouping, no `LIKE`. **HR-5** — every filter is in the query; the fixes of BUG-1327 and BUG-1328 must stay in the query. **HR-7** — `GET /products/` already requires `1 <= limit <= 1000` and `skip >= 0`. **HR-9** — `soft_delete` writes `deleted_by`, and `updated_at` moves with it; neither is `updated_by`, as for machines. **HR-10** — `get_by_factory_item_available` reads without a lock and four callers then change stock: that belongs to the product manager (FU-1 (a)). The plain read stays for callers that change nothing. **HR-15** — this DAO does no arithmetic; the half-even `quantize` in `apply_production_output` is BUG-1040. **HR-16** — the reads follow the row; `create_product` is BUG-1011.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-11-02))

### P1. A product's delete time comes from the database's clock — 🐞 BUG-1335
**Background:** `soft_delete` sets `deleted_at` to the database's `now()`, written into a column with no time zone. `deleted_at` on machines comes from `utcnow()`. BUG-1102 ruled this for maintenance logs.
**What happens today:** The value is local time in the session's `TimeZone`. Verified: 15:26 under `America/New_York`, 02:26 the next day under `Asia/Dhaka`, for one moment.
**Example:** A product deleted at 20:26 UTC records 02:26 on a database set to Dhaka time, while a machine deleted at that moment records 20:26.
**Rules affected:** `soft_delete` R3, R3a
**Answer:** bug — per BUG-1102 precedent: `deleted_at` is written from `utcnow()`, naive UTC
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): 🐞 BUG-1335 (pattern `database-clock-timestamp`). `created_at` and `updated_at` stay with the database clock, as in BUG-1102. Rules: `soft_delete` R3, R3a.

### P2. "Restore a product" has no caller — ✅ kept
**Background:** `restore` undoes a soft delete. No endpoint or manager calls it today. `machine.spec.md` Q5 ruled the same case "keep restore": no caller yet, but kept, specified and tested.
**What happens today:** A soft-deleted product cannot be brought back through the API.
**Example:** No request reaches it. The inventory equivalent is called from get-or-create, and Q1 below would give this one a caller.
**Rules affected:** `restore` (all)
**Answer:** intended — per machine DAO Q5 precedent: kept and specified
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): not dead code; BUG-1336 gives it two callers. Rules: `restore` R1–R4 ✅.

### New questions

### Q1. OWNER, stock — After a product row is deleted, nothing can use its key again — 🐞 BUG-1336 (owner)
**Background:** A `products` row is one stock bucket: workspace + item + factory + for-sale or not. The unique constraint `uq_product_workspace_item_factory_available` covers **every** row, so a soft-deleted row keeps its key for good (the standing one-row-per-key rule). But `get_by_factory_item_available`, the "find the bucket" step, skips soft-deleted rows, so every get-or-create believes the key is free and inserts. Factory stock had the same trap and solved it: `InventoryDAO.ensure_for_factory_item_type` looks at deleted rows too, restores the row, and re-syncs it from the ledger.
**What happens today:** Each of these fails with `IntegrityError`, `UniqueViolation` 23505, so a 500 (verified): `POST /products/` for that key, `apply_production_output` (so `complete_batch` and `post_outputs_to_finished_goods`), and `apply_sale_return`. `complete_batch` is the worst: the batch stays `in_progress` (verified) with its inputs already taken, and it cannot be completed until someone fixes the row by hand, because `restore` has no caller. `apply_sale_deduction` answers 422 "available 0", which is correct.
**Example:** The not-for-sale row of Yarn in Factory 1 is deleted, still holding 5. A batch producing Yarn in Factory 1 is then completed: 500 error, every time. A customer returning Yarn from the for-sale bucket gets the same, if that row was deleted.
**Rules affected:** `get_by_factory_item_available` R3; `_get_any_by_factory_item_available` R1–R3
**Suggested answer:** `bug — per the inventory precedent`: a new lookup finds the key's row including deleted ones, and the stock paths (production output, sale return) restore that row and carry on, so one key keeps one row. `get_by_factory_item_available` keeps hiding deleted rows, because `apply_sale_deduction`, the minimum-order check and the duplicate check need that. **The owner must decide the quantity:** the deleted row still holds its 5, and `soft_delete` wrote no ledger row, so the books still say 5. Suggestion: keep it, so the row comes back with 5 and the output adds to it (`qty_before` 5), which matches the ledger. `POST /products/` on a deleted key answers 409 with the existing message rather than restoring: a manual create should not silently bring old stock back. Alternatives: reset `qty` to 0 with a ledger row, or a partial unique index on live rows, which would give one key two rows and break the standing rule.
**Answer:** bug — stock paths find and restore the deleted row, keeping its `qty`; `POST /products/` answers 409 (owner, 2026-11-02)
**Resolution:** 🐞 BUG-1336 (pattern `soft-deleted-conflict-not-restored`, as BUG-714). One key keeps one row. `get_by_factory_item_available` keeps hiding deleted rows; a new lookup sees them. `apply_production_output` and `apply_sale_return` restore the row and carry on from its kept `qty`, with no ledger row for the restore itself. `create_product` answers 409 with its existing message, which is deliberately not what BUG-714 does for inventory: a manual create must not bring old stock back. The manager's part is tested in its own module (FU-1 (i)). Rules: `get_by_factory_item_available` R3 ✅; `_get_any_by_factory_item_available` R1–R3.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Product manager, service, endpoint** (`app/managers/product_manager.py`, not yet specified) | (a) **OWNER, stock (HR-10):** `apply_production_output`, `apply_sale_deduction`, `apply_sale_return`, `update_product` read the row unlocked and write an absolute `qty`: two movements at once lose one, and two deliveries can both pass the stock check. (b) **OWNER, stock — verified:** `delete_product` deletes a row holding stock: the 4 units leave every list, the row keeps `qty` 4 and no ledger row is written. Factory stock precedent: BUG-948 style refusal with blockers, or a final adjustment. (c) **Verified:** `get_product` returns a soft-deleted row (pattern `get-returns-soft-deleted`, BUG-966 precedent: 404 by default); the same read serves `update_product` and `delete_product`, which answer 400. (d) **OWNER, stock — verified:** `ProductCreate` / `ProductUpdate` have no minimums: `qty` -5 is stored with no ledger row at all (`data.qty > 0` skips it), `qty` -1 on update, and `selling_price` -1.00, `avg_cost` -2.00 (BUG-711 precedent). (e) **OWNER, stock — verified:** `PUT` moving `is_available_for_sale` onto a key that already has a row is an `IntegrityError` (500). Moving stock between the two buckets by this flag writes no ledger row (read, not run). (f) **Verified:** `create_product` accepts a soft-deleted factory (BUG-822 precedent) and is BUG-1011 for the item. A removed item is accepted too (read, not run), then hidden by BUG-1327, the same conflict as BUG-883 with `create_inventory`. (g) `update_product` cannot clear `avg_cost`, `selling_price`, `min_order_qty` or `note`. An `avg_cost` change alone writes no ledger row (read, not run). (h) **Money:** `total_cost` in `create_product` and `update_product` is skipped when `avg_cost` is `0` (`if data.avg_cost`, `if new_avg`), where `apply_production_output` tests `is not None`. (i) **BUG-1336, logged; owner's answer 2026-11-02:** `apply_production_output` and `apply_sale_return` find the key through `_get_any_by_factory_item_available`, restore a deleted row, and carry on from its kept `qty` (`qty_before` is that `qty`), with no ledger row for the restore. `create_product` on a deleted key answers 409 `Product record already exists for this item/factory/availability combination`, nothing written. `apply_sale_deduction` keeps answering 422, and does not restore. | HR-10, Q1, reading the callers |
| FU-2 | **Item summary service** (`app/services/item_summary_service.py`) | `_product_rows` tests `prod.is_deleted`, which `get_by_item` already excludes: that branch cannot run. **BUG-1338 (owner, 2026-11-03):** the summary of a removed item then shows no finished goods, while factory stock (`inventory.spec.md` `get_by_item` R3) and machine placements (`machine_item.spec.md` `get_by_item` R4) of that item are still shown. **BUG-1339, logged (owner, 2026-11-03):** the summary of a removed item hides factory, machine and finished-goods stock alike, the rows untouched. The factory and machine halves are checked in the service, because those two DAO reads stay raw; the product half is BUG-1338 here. To be specified and tested in the item summary service's review. | `get_by_item` R2, R3c |
| FU-3 | **Sales order flows** (`app/utils/order_catalog_items.py`) | `assert_meets_minimum_order_quantities` reads through `get_by_factory_item_available`: a soft-deleted bucket no longer has a minimum, while a bucket in a deleted factory or of a removed item keeps enforcing one although it is hidden elsewhere (`get_by_factory_item_available` R3, R4). Check that this is wanted. | `get_by_factory_item_available` R4 |

## Overview
`ProductDAO` reads `products`, the finished goods stock: one row per item, factory and sale state, holding the quantity, average cost, selling price and minimum order. The ledger (`product_ledger`) is the record of movements; this row is the current figure. Callers: `ProductManager` (`/products/`, and the production and sales movements), `ItemSummaryService` (product rows on the item summary page) and `assert_meets_minimum_order_quantities` (sales order lines). It is meant to protect workspace isolation, and it adds a soft delete. It validates nothing and never commits. `get_by_id_and_workspace` is a line-for-line copy of the base method; `get_by_workspace` is **not**: it has filters of its own and hides soft-deleted rows, so the base method's raw behaviour does not apply to it.

**Callables:** 7 specified (1 to be written, BUG-1336) · 2 not specified
**Externals to mock:** `utcnow`, patched at `app.dao.product.utcnow`, used by `soft_delete` only (BUG-1335). `restore` does not read the clock.
**Integration-only behavior:** none. (`skip >= 0`, `1 <= limit <= 1000` are enforced by `GET /products/`, not here.)

**Model facts (table `products`, class `app.models.product.Product`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `item_id` | Integer NOT NULL, FK `items.id`, no cascade | — |
| `factory_id` | Integer NOT NULL, FK `factories.id`, no cascade | — |
| `qty` | Integer NOT NULL, no check constraint | `0` (Python default only) |
| `avg_cost`, `selling_price` | Numeric(15, 2) nullable | `NULL` |
| `min_order_qty` | Integer nullable | `NULL` |
| `is_available_for_sale` | Boolean NOT NULL | `False` (Python default only) |
| `note` | Text nullable | `NULL` |
| `created_at` | DateTime NOT NULL | database `now()` |
| `updated_at` | DateTime nullable, set on update by `now()` | `NULL` |
| `created_by`, `updated_by`, `deleted_by` | Integer nullable, FK `profiles.id` | `NULL` |
| `is_active` | Boolean NOT NULL | `True` (Python default only) |
| `is_deleted` | Boolean NOT NULL | `False` (Python default only) |
| `deleted_at` | DateTime nullable | `NULL` |

- `uq_product_workspace_item_factory_available`: UNIQUE `(workspace_id, item_id, factory_id, is_available_for_sale)`, **not partial**: soft-deleted rows count. No check constraint, no trigger; nothing references the table.
- Relationships: `item` is `lazy="joined"`: every query here also reads the item, through a `LEFT OUTER JOIN`. Properties `item_name` and `item_unit` read it.
- Parents, as used by the bug rules: `Factory`: soft delete = `is_deleted = True`, `is_active` unchanged. `Item`: no `is_deleted`; removed = `is_active = False`.
- Schemas (`app/schemas/product.py`): `ProductCreate` = `item_id`, `factory_id`, `qty = 0`, `avg_cost`, `selling_price`, `min_order_qty`, `is_available_for_sale = False`, `note` (no `workspace_id`). `ProductUpdate` = `qty`, `avg_cost`, `selling_price`, `min_order_qty`, `is_available_for_sale`, `note`, all optional. No validators, no minimums.

**Notes for the test designer:**
- `from app.dao.product import product_dao`. Every parameter after `db` is keyword-only.
- Workspaces from `tests/unit/factories.py` (`make_workspace`), profiles from `make_profile`. Build `Factory`, `Item(workspace_id, name, name_normalized, unit)`, `Product(workspace_id, item_id, factory_id, qty)` directly. The session runs with `autoflush=False`.
- **One key, one row:** never build two rows of one key: `uq_product_workspace_item_factory_available` refuses it, soft-deleted or not. To have a row of "another bucket", flip `is_available_for_sale`.
- **Soft-deleted parents (BUG-1327, BUG-1328, BUG-1338):** as `machine_item.spec.md`: keep a row under live parents in the same case, compare **sets** of ids, **strict** xfail; "back once the parent is live" is a plain pass case.
- **Row order (BUG-1325, BUG-1326):** intended order, **non-strict** xfail, forced sequential scan. Names `"Zulu"`, `"apple"`, `"Banana"`, inserted in that order.
- **The clock (BUG-1335):** the module does not import `utcnow` today, so patch with `create=True`: `patch("app.dao.product.utcnow", create=True, return_value=NOW)`, with `NOW` a fixed naive datetime far from today. `db.refresh(row)` before reading `deleted_at`. Today the patch is unused and the value is the database's `now()`, which never equals `NOW` → **strict** xfail.
- **The new lookup (BUG-1336):** every call raises `AttributeError` today → **strict** xfail.
- Wrap calls expected to raise in `with db.begin_nested():`.

## Not specified
- `product_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods `get`, `get_multi`, `create`, `update`, `remove` — not overridden; covered by the base spec. Only what this model changes is under "Inherited `BaseDAO` methods on `Product`".

---

## `ProductDAO.get_by_workspace(db, *, workspace_id, factory_id=None, is_available_for_sale=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProductManager.list_products` ← `GET /products/`). An override with its own filters, not a copy of the base method.

**Purpose:** The live stock rows of a workspace, optionally of one factory or sale state, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality on the row's `workspace_id` |
| `factory_id` | int or `None`, default `None` | `None` = every factory; otherwise equality, so `0` matches nothing |
| `is_available_for_sale` | bool or `None`, default `None` | `None` = both; `False` is a filter, not "no filter" |
| `skip` | int, default `0` | not validated |
| `limit` | int, default `100` | not validated |

**Returns:** a `list` of `Product` (possibly empty), each with its item loaded.

**Rules:**
- **R1.** Returns the rows of that workspace with `is_deleted = False`. Rows of another workspace never appear.
- **R2.** A soft-deleted row is not returned and takes no place in the page. A row with `is_active = False`, `is_deleted = False` is returned.
- **R3.** `factory_id` narrows to that factory; `factory_id=0` returns `[]`.
- **R4.** `is_available_for_sale=True` returns only the for-sale rows, `False` only the others, `None` both. The two filters combine with AND.
- **R4a.** Rows are returned whatever their quantities: `0` and negative `qty` included.
- **R5.** An unknown workspace, a workspace with no rows, `skip` past the end, or `limit=0` returns `[]`.
- **R5a.** [BUG-1327] A row whose factory is soft-deleted (`factories.is_deleted = True`) is not returned and takes no place in the page. *(Today: it is returned.)*
- **R5b.** [BUG-1327] A row whose item is removed (`items.is_active = False`) is not returned and takes no place in the page. *(Today: it is returned.)*
- **R5c.** What surrounds R5a and R5b, holding today and after the fix: (1) the call changes nothing; (2) a factory with `is_active = False`, `is_deleted = False` hides nothing; (3) once the factory is live and the item active, the rows are returned again, unchanged.
- **R6.** [BUG-1325] (HR-6) Rows are ordered by item name case-insensitive ascending, then row `id` ascending, before `skip` / `limit`: items "Zulu", "apple", "Banana" come back "apple", "Banana", "Zulu". *(Today: no ordering is requested.)*
- **R7.** At most `limit` rows after skipping `skip`; with the defaults at most 100: given 101 rows, exactly 100. Consecutive windows partition the rows (relies on R6).
- **R8.** A negative `limit` or `skip` makes Postgres reject the query (see Errors).
- **R9.** Each row carries its item's data: `item_name` and `item_unit` give the item's `name` and `unit`, with no further query.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## `ProductDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (override identical to `BaseDAO.get_by_id_and_workspace`. Used by: `ProductManager.get_product`, `update_product`, `delete_product`)

**Purpose:** One stock row by id, inside one workspace.

**Returns:** the `Product`, or `None`.

**Rules:**
- **R1.** Given a row with that id in that workspace, it is returned.
- **R2.** Given a row with that id in another workspace, `None` is returned (indistinguishable from not found).
- **R3.** An unknown id or `id=0` returns `None`, with no error.
- **R4.** A soft-deleted row is returned: `update_product` and `delete_product` read it to answer 400 (HR-4 scope). A row of a soft-deleted factory or of a removed item is returned too (inventory DAO Q9).

**Errors:** none.

**Side effects:** none

---

## `ProductDAO.get_by_factory_item_available(db, *, factory_id, item_id, is_available_for_sale, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `ProductManager.create_product`, as the duplicate check; `apply_production_output`, `apply_sale_return`, as the find step of get-or-create; `apply_sale_deduction`; `assert_meets_minimum_order_quantities`)

**Purpose:** The live stock row of one bucket, if any.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `factory_id` | int | equality; not validated |
| `item_id` | int | equality; not validated |
| `is_available_for_sale` | bool | equality; required |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** the `Product`, or `None`.

**Rules:**
- **R1.** Given a live row with exactly that key, it is returned. The for-sale and not-for-sale rows of one item and factory are told apart.
- **R2.** All four must match: another factory, item, sale state or workspace is not matched. No match, including `factory_id=0`, returns `None`, with no error. No row is created.
- **R3.** ✅ (Q1) A soft-deleted row is not found, although it still holds the key: `apply_sale_deduction`, the minimum-order check and the duplicate check rely on that. `_get_any_by_factory_item_available` sees it.
- **R4.** The state of the parents is not looked at: a row of a soft-deleted factory or of a removed item is found. A raw lookup: get-or-create must still see the bucket, or it would hit the unique constraint (inventory DAO Q6 scope decision, Q8).
- **R5.** A row with `is_active = False`, `is_deleted = False` is found.
- **R6.** The constraint allows one row per key, so there is nothing to choose between and no order is needed.

**Errors:** none.

**Side effects:** none

---

## `ProductDAO._get_any_by_factory_item_available(db, *, factory_id, item_id, is_available_for_sale, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** internal, **to be written** (BUG-1336; used by: `apply_production_output`, `apply_sale_return`, `create_product`). Same name and job as `InventoryDAO._get_any_by_factory_item_type`.

**Purpose:** The stock row of one bucket, deleted or not.

**Inputs:** as `get_by_factory_item_available`.

**Returns:** the `Product`, or `None`.

**Rules:**
- **R1.** [BUG-1336] Given a row with exactly that key, it is returned, also when it is soft-deleted. *(Today: the method does not exist.)*
- **R2.** [BUG-1336] All four must match, as `get_by_factory_item_available` R2. No match returns `None`, with no error, and no row is created. *(Today: the method does not exist.)*
- **R3.** [BUG-1336] The call changes nothing: a soft-deleted row stays soft-deleted. *(Today: the method does not exist.)*

**Errors:** none.

**Side effects:** none

---

## `ProductDAO.get_by_item(db, *, item_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ItemSummaryService._product_rows` ← the item summary page)

**Purpose:** Every live stock row of one catalog item, across factories.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `item_id` | int | equality on the row's `item_id`; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** a `list` of `Product` (possibly empty), each with its item loaded.

**Rules:**
- **R1.** Returns the rows with that `item_id` and that `workspace_id`, for sale or not, whatever their quantities. Another workspace returns `[]`.
- **R2.** A soft-deleted row is not returned.
- **R2a.** A row with `is_active = False` and `is_deleted = False` is returned: `products.is_active` is not looked at (decided by Claude under the reviewer's delegation (2026-11-03), following item manager R9 (g); as `get_by_workspace` R2).
- **R3.** An unknown item, `item_id=0`, or an item with no rows returns `[]`.
- **R3a.** [BUG-1328] A row whose factory is soft-deleted is not returned. Given the item in live Factory 1 and deleted Factory 2, only the Factory 1 rows come back. *(Today: both are returned.)*
- **R3b.** What surrounds R3a and R3c, holding today and after the fix: (1) the call changes nothing, to the stock rows or to the item; (2) a factory with `is_active = False`, `is_deleted = False` hides nothing; (3) once the factory is live and the item active again, the row is returned again, unchanged.
- **R3c.** [BUG-1338] (owner, 2026-11-03) When the item is removed (`items.is_active = False`), `[]` is returned, the rows untouched, as on the product list (`get_by_workspace` R5b). *(Today: its rows are returned.)*
- **R4.** [BUG-1326] (HR-6) Rows are ordered by row `id` ascending. *(Today: no ordering is requested.)*
- **R5.** No paging and no cap: 101 rows give 101.

**Errors:** none of its own.

**Side effects:** none

---

## `ProductDAO.soft_delete(db, *, db_obj, deleted_by)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `ProductManager.delete_product`, after it has refused a row already deleted)

**Purpose:** Mark one stock row deleted, keeping it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db_obj` | `Product` | the row; not checked |
| `deleted_by` | int | a `profiles.id`; an unknown id fails at the flush |

**Returns:** the same `db_obj`, flushed, not committed.

**Rules:**
- **R1.** Sets `is_deleted = True`, `is_active = False`, `deleted_by` to the given id.
- **R2.** `qty`, `avg_cost` and every other column keep their values. No ledger row is written: the stock stays on the row (FU-1 (b)).
- **R3.** `updated_at` moves, by the database's clock; `updated_by` does not change.
- **R3a.** [BUG-1335] (P1) `deleted_at` is set from `utcnow()`, naive UTC, whatever the session's `TimeZone`. *(Today: the database's `now()`, stored as local time in the session's `TimeZone`.)*
- **R4.** The row stops being found by `get_by_workspace`, `get_by_item`, `get_by_factory_item_available`, and is still found by `get_by_id_and_workspace`.
- **R5.** Called on a row already deleted, it raises nothing and overwrites `deleted_at` and `deleted_by`.
- **R6.** Not committed: rolling back a savepoint around the call restores the row.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| unknown `deleted_by` | `sqlalchemy.exc.IntegrityError`, pgcode `23503` | — |

**Side effects:** one row updated and flushed.

---

## `ProductDAO.restore(db, *, db_obj)`
**Shape:** update
**Persistence:** writes
**Visibility:** public, no caller today; BUG-1336 makes `apply_production_output` and `apply_sale_return` its callers (P2)

**Purpose:** Undo a soft delete.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db_obj` | `Product` | the row; not checked |

**Returns:** the same `db_obj`, flushed, not committed.

**Rules:**
- **R1.** ✅ (P2) Sets `is_active = True`, `is_deleted = False`, `deleted_at = None`, `deleted_by = None`.
- **R2.** ✅ (P2, Q1) `qty` and every other column keep their values: the row comes back with its stock. `updated_at` moves; `updated_by` does not change.
- **R3.** ✅ (P2) The row is found again by `get_by_factory_item_available`, `get_by_workspace`, `get_by_item`.
- **R4.** ✅ (P2) Called on a live row, it raises nothing, and a row with `is_active = False` becomes active.

**Errors:** none of its own.

**Side effects:** one row updated and flushed.

---

## Inherited `BaseDAO` methods on `Product`
**Shape:** create / update
**Persistence:** writes
**Visibility:** public (`create`, `update` with a dict ← `ProductManager`; `get`, `get_multi`, `remove`: no caller on this DAO)

**Purpose:** `ProductDAO` does not override these; the base spec applies. Only what this model changes is stated.

**Rules:**
- **R1.** `create` with a dict holding `workspace_id`, `item_id`, `factory_id` gives `qty = 0`, `is_available_for_sale = False`, `is_active = True`, `is_deleted = False`, `avg_cost = None`, `updated_at = None`, `created_at` set.
- **R2.** `create` with a `ProductCreate` always fails: the schema has no `workspace_id`, so the flush raises `IntegrityError` (`NotNullViolation`, pgcode `23502`) and nothing is saved.
- **R3.** A second row of one key raises `IntegrityError` (`UniqueViolation`, pgcode `23505`) at the flush, also when the first row is soft-deleted. The same item and factory with the other `is_available_for_sale` is accepted.
- **R4.** No range check: `qty` stores `-4`. A value beyond 32 bits raises `DataError`, pgcode `22003`.
- **R5.** `avg_cost` set to `0.125` reads back `0.13` after a refresh: the column rounds half away from zero (HR-15).
- **R6.** `update` with a `ProductUpdate` applies only fields set to a value: `qty=0, note=None` sets `qty` to `0` and keeps `note`.
- **R7.** `update` does not look at `is_deleted`: a soft-deleted row is changed like any other.

**Errors:** as in the base spec, plus R3 and R4.

**Side effects:** as in the base spec.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 16–20 | keyword-only parameters; defaults | Notes; `get_by_workspace` R7 |
| 23–26 | `workspace_id` AND `is_deleted = False`; parents not read (BUG-1327) | `get_by_workspace` R1, R2, R5a–R5c |
| 27–28 | `factory_id is not None` | `get_by_workspace` R3 |
| 29–30 | `is_available_for_sale is not None`: `True` / `False` / `None` | `get_by_workspace` R4 |
| 31 | offset, limit, no `ORDER BY` (BUG-1325); empty / many | `get_by_workspace` R4a, R5, R6, R7, R8, Errors |
| 37–40 | id AND `workspace_id`; `.first()`: row / `None`; no state read | `get_by_id_and_workspace` R1–R4 |
| 47–53 | four-part key AND `is_deleted = False`; `.first()`: row / `None` | `get_by_factory_item_available` R1–R6 |
| — | to be written (BUG-1336): four-part key, no `is_deleted` filter | `_get_any_by_factory_item_available` R1–R3 |
| 59–63 | `workspace_id` AND `item_id` AND `is_deleted = False`; no factory state (BUG-1328); no item state (BUG-1338); no `ORDER BY` (BUG-1326) | `get_by_item` R1–R5 |
| 67–74 | four fields set; `func.now()` (BUG-1335); flush | `soft_delete` R1–R3a, R4–R6 |
| 78–84 | four fields set; flush | `restore` R1–R4 |
| 87 | module singleton | Not specified |
| `models/product.py` 55–61 | `if self.item` | `get_by_workspace` R9 |
| `base.py` 76–84 | `create`: dict / schema (no `workspace_id`); Python defaults; unique constraint, range | inherited R1–R5 |
| `base.py` 108–119 | `update`: schema drops `None`; no state read | inherited R6, R7 |
