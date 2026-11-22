# Spec — `app/services/product_service.py`

> **Status:** APPROVED (2026-11-21; no open questions — D1, D2 decided by Claude under the reviewer's delegation, 2026-11-21). Stays APPROVED after fill-gaps (Gap log at the end).
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md` and `machine_item_service.spec.md`: this spec covers only what the service adds. The **Transaction contract TC1–TC6 is defined in `tests/unit/services/base_service.spec.md`** (same rules as the department spec) and cited here. Below the service, not restated: `tests/unit/managers/product_manager.spec.md` (APPROVED; OQ-50, OQ-51, OQ-52, BUG-2793, BUG-2811 applied), `tests/unit/dao/product.spec.md`, `tests/unit/dao/product_ledger.spec.md` (both APPROVED).

> **Routed here and written as rules (existing bugs, no new ID):** **BUG-2772** — its register row names `ProductService.get_product` and `GET /products/{id}/`: the service passes the new `include_deleted` on (`get_product` R2). **BUG-2793** (owner, OQ-51) — the new manager method `make_sellable` needs a transaction boundary; written here as a new callable (`make_sellable` S1–S4). **BUG-2774** — the manager's refused delete is an `app.core.exceptions.ValidationError` carrying the blockers; the service passes it on unchanged after the rollback (`delete_product` R2), so no translation is needed (unlike `machine_item_service`).
>
> **Production deferred** (`docs/future/production-revamp.md`, owner 2026-11-19). `POST /products/receive-from-batch/{batch_id}/` lives in the same router but calls `production_batch_service`, not this service: not specified here. The production-only manager paths (`apply_production_output`, OQ-50 "revisit after launch", BUG-2811) are not reached through this service. The ledger list returns `production` rows like any other (R-rules of `list_ledger` are type-blind).
>
> **Verified:** read, not run. Read: this file; `app/api/v1/endpoints/products.py` (every caller); `app/dao/product_ledger.py`; `app/models/product_ledger.py`; the manager, DAO and base-service specs above. No behaviour here needed a run: every rule is either the TC contract (verified in `base_service.spec.md`) or a pass-through whose outcome is verified in the layer below.

## Review
> No new questions. Two service-level choices decided under delegation, below.

### D1. What `make_sellable` returns — ✅ decided
**Background:** The owner decided (OQ-51, BUG-2793) that a "make N units sellable" move exists; the manager spec returns the for-sale (target) row. The service only commits and re-reads.
**What happens today:** the method does not exist.
**Example:** 40 bales of "Yarn" sit in the not-for-sale bucket; the user makes 10 sellable. The response is the for-sale row, now 10 bales (or its old quantity + 10); the not-for-sale row (30) is re-read by the page through `GET /products/`.
**Rules affected:** `make_sellable` S1
**Answer:** decided by Claude under the reviewer's delegation (2026-11-21): return the target row, re-read after the commit, as the manager does. No new ID (part of BUG-2793).

### D2. `include_deleted` on the ledger list — ✅ decided: none
**Background:** Ledgers are history: rows stay listed whatever happened to the factory, item or product (standing decision of `product_ledger.spec.md`). Ledger rows have no soft-delete column.
**What happens today:** `list_ledger` lists every row of the workspace matching the filters.
**Example:** A product row of "Yarn" in Factory 1 is deleted after being emptied to 0; its `manual_add` and `inventory_adjustment` rows are still listed.
**Rules affected:** `list_ledger` R1
**Answer:** decided by Claude under the reviewer's delegation (2026-11-21): intended; no parameter. Not a bug.

Reached through the manager and cited, one pass-through case each, strict or non-strict exactly as in `tests/unit/managers/product_manager.cases.md`: BUG-1011, BUG-1336, BUG-2771, BUG-2772, BUG-2773, BUG-2774, BUG-2775, BUG-2776, BUG-2777, BUG-2778, BUG-2779, BUG-2780, BUG-2781 (the update half only — the create race is not unit-testable), BUG-2793. Through the ledger DAO: BUG-640 (order), BUG-992 (aware bounds). Not reached through this service: BUG-1040, BUG-2811 (production deferred), BUG-2782, BUG-2783, BUG-2794 (sales paths), BUG-2770 (locks, not unit-testable). BUG-991 is the endpoint's, integration-only.

Checked and **not** violated: **HR-1 … HR-3, HR-8** — no names or search text. **HR-4** — BUG-2772 / BUG-2773 (above). **HR-5, HR-6** — filters and order are the DAOs' (BUG-640, BUG-1325, BUG-1327 there). **HR-7** — both `GET /products/` and `GET /products/ledger/` require `1 <= limit <= 1000`, `skip >= 0`; the service defaults (`skip 0`, `limit 100`) match. **HR-9, HR-15** — the manager's (BUG-2771; money stored through `Numeric(15,2)`). **HR-10** — locks are the manager's (BUG-2770); the service holds them until its commit, since manager and commit share one transaction. **HR-11 … HR-14** — no externals. **HR-16** — the manager checks the factory (BUG-1011 for the item); the ledger list filters by `workspace_id` first, so another workspace's `factory_id` or `item_id` returns `[]` and nothing of that workspace is shown.

**Permission checks:** none; any active member may create, edit, delete finished goods, change their cost, and read the cost ledger (manager FU-4, already a note for `docs/future/permissions.md`; `make_sellable` belongs on the same list).

## Overview
`ProductService` is the transaction boundary for finished goods (`products` buckets and their `product_ledger` rows). The `/products/` endpoints call it. It adds nothing of its own beyond commit, rollback and re-read around the manager's writes, and plain reads: the product get and list from the manager, and the ledger list straight from the ledger DAO.

**Callables:** 7 specified (one of them new: `make_sellable`) · 2 not specified
**Externals to mock:** none (no notifications, no email).
**Integration-only behavior:** as `department_service.spec.md`; the `include_deleted` query parameter on `GET /products/{id}/` (BUG-2772); the new route for `make_sellable` (BUG-2793); the 400 body of `app.core.exceptions.ValidationError` for BUG-2774 (`tests/unit/core/exceptions.spec.md`); the date-only `end_date` (BUG-991); `IntegrityError` → the global handler's 409; `DataError` → 500.

**Facts for the test designer**
- Import: `from app.services.product_service import ProductService, product_service`. Attributes: `manager` (the `product_manager` singleton of `app.managers.product_manager`), `ledger_dao` (the `product_ledger_dao` singleton of `app.dao.product_ledger`).
- Signatures (the endpoints pass everything after `db` by keyword): `create_product(db, prod_in, workspace_id, user_id)`, `update_product(db, prod_id, prod_in, workspace_id, user_id)`, `get_product(db, prod_id, workspace_id)`, `list_products(db, workspace_id, factory_id=None, is_available_for_sale=None, skip=0, limit=100)`, `delete_product(db, prod_id, workspace_id, user_id)`, `list_ledger(db, workspace_id, factory_id=None, item_id=None, start_date=None, end_date=None, transaction_type=None, skip=0, limit=100)`.
- Inputs are `app.schemas.product.ProductCreate` / `ProductUpdate` (fields in the manager spec Overview).
- How to build factories, items, product rows and ledger rows: the Facts / Notes of `product_manager.spec.md` and `product_ledger.spec.md`.

**Notes for the test designer**
- Session, commits, setup before error paths, TC4 / TC5 patching: as the Notes of `department_service.spec.md`. **TC1 here includes the ledger rows** the manager writes in the same call (create with `qty > 0`; update changing `qty`): after a successful write and a test-level `db.rollback()` the product row and its ledger row are both there; after an error neither is.
- TC3 per write: `create_product` with an unknown `factory_id` (404) and with a taken key (409); `update_product` on a soft-deleted row (400); `delete_product` already deleted (400). Each: same `HTTPException` object out, an uncommitted extra row discarded.
- **BUG-2772:** the parameter does not exist today: `include_deleted=` raises `TypeError` → strict xfail. R2's default (404 for a soft-deleted row) needs no new parameter: today the row is returned → strict xfail.
- **BUG-2774 (`delete_product` R2):** today a row holding stock is deleted (200) → strict xfail for the end-to-end case. Test the pass-through on its own too, as an ordinary pass: `unittest.mock.patch.object(product_service.manager, "delete_product", side_effect=ValidationError("Product record still holds stock", errors=[{"type": "product_stock", "id": 5, "qty": 4}]))` (`app.core.exceptions`); assert the same object is raised and the rollback ran.
- **BUG-2793 (`make_sellable`):** the method does not exist on the service (`AttributeError`) → strict xfail for every case.
- **Rollback count (gap 1, code fact):** on a failing commit, today `db.rollback` runs **twice** — once inside `_commit_transaction` (base B2) and once in the service's `except`. The contract is "at least one" (TC4, as `department_service.spec.md` Notes); assert `>= 1`, never an exact count. On a manager refusal it runs once.
- **Ledger list:** set `performed_at` by hand on every ledger row (`product_ledger.spec.md` Notes); compare sets of ids except in the one order case.

## Not specified
- `ProductService.__init__` — stores the manager and the ledger DAO, no logic.
- `product_service` — module-level singleton, no logic.
- `POST /products/receive-from-batch/{batch_id}/` — not this service (`production_batch_service`); production deferred.

---

## `ProductService.create_product(db, prod_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /products/`)

**Purpose:** Create a finished-goods bucket by hand, with its opening ledger row, and save it.

**Returns:** the new `Product`, committed and re-read.

**Rules:**
- **R1.** TC1–TC5 apply. The saved outcome is the manager's (`create_product` R0–R7a): the row, and its `manual_add` ledger row when `qty > 0` (and, after BUG-2778, when `qty` is 0 with a cost), all committed together.
- **R2.** Every refusal of the manager reaches the caller unchanged after the rollback (TC3): 404 factory / [BUG-1011, BUG-2780] item, 409 key taken (live, [BUG-1336] deleted), and the `IntegrityError` / `DataError` cases that remain today (e.g. an unknown `item_id` fails the foreign key at flush today — BUG-1011's case, assert the intended 404). Nothing is saved, neither row nor ledger row.

**Errors:** as the manager's `create_product`, unchanged. **Side effects:** commit; rollback on any error.

---

## `ProductService.update_product(db, prod_id, prod_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /products/{id}/`)

**Purpose:** Edit a bucket by hand (quantity, cost, price, minimum order, note, for-sale flag) and save it.

**Returns:** the `Product`, committed and re-read.

**Rules:**
- **R1.** TC1–TC5 apply. The saved outcome is the manager's (`update_product` R1–R10a): the changed row and, when `qty` (or after BUG-2778 `avg_cost`) changes, its `inventory_adjustment` ledger row, committed together. [BUG-2771] A call that changes nothing still commits, but writes nothing (no `updated_by`, no ledger row).
- **R2.** Every refusal reaches the caller unchanged after the rollback, nothing saved: 404, 400 deleted, [BUG-2793] 400 flag change on a row holding stock, [BUG-2781] 409 flag onto a taken key (today `IntegrityError` 23505, also passed on unchanged with nothing saved).

**Errors:** as the manager's `update_product`, unchanged. **Side effects:** commit; rollback on any error.

---

## `ProductService.get_product(db, prod_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: `GET /products/{id}/`)

**Inputs:** `include_deleted` — [BUG-2772] new, default `False`, passed on to the manager, reachable from the API. *(Today: no such parameter.)*

**Rules:**
- **R1.** Returns the manager's result unchanged: the workspace's row; unknown id or another workspace's row → 404 `Product record with ID {prod_id} not found`. TC6 applies (no commit, no rollback).
- **R2.** [BUG-2772, BUG-2773] A soft-deleted row, or a row of a soft-deleted factory or removed item → the same 404 by default; `include_deleted=True` returns it. *(Today: returned.)*

**Errors:** 404, unchanged. **Side effects:** none.

---

## `ProductService.list_products(db, workspace_id, factory_id=None, is_available_for_sale=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /products/`)

**Rules:**
- **R1.** Returns exactly the manager's `list_products` with the same arguments (filters, soft-delete hiding, paging, order per `product.spec.md` `get_by_workspace`; BUG-1325, BUG-1327 there). Defaults `skip 0`, `limit 100`; `is_available_for_sale=False` filters (it is not treated as "no filter"). TC6 applies.

**Errors:** none. **Side effects:** none.

---

## `ProductService.delete_product(db, prod_id, workspace_id, user_id)`
**Shape:** soft-delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /products/{id}/`)

**Returns:** the soft-deleted `Product`, committed and re-read (`is_deleted True`, `deleted_by = user_id`, `qty` and costs kept).

**Rules:**
- **R1.** TC1–TC5 apply. The saved outcome is the manager's `delete_product` R4.
- **R2.** Refusals reach the caller unchanged after the rollback, nothing saved: 404, 400 `Product record is already deleted`, and [BUG-2774] the `app.core.exceptions.ValidationError("Product record still holds stock", errors=[{"type": "product_stock", "id": prod_id, "qty": qty}])` (400 at the API) for a row with `qty ≠ 0` — the same object, `detail` and `errors` intact, no translation. *(Today: a row holding stock is deleted.)*

**Errors:** as the manager's `delete_product`, unchanged. **Side effects:** commit; rollback on any error.

---

## `ProductService.list_ledger(db, workspace_id, factory_id=None, item_id=None, start_date=None, end_date=None, transaction_type=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /products/ledger/`)

**Purpose:** The finished-goods movement history, filtered.

**Rules:**
- **R1.** Returns exactly `ProductLedgerDAO.get_by_workspace` with the same arguments (`product_ledger.spec.md` R1–R11): only this workspace's rows; filters AND-combined; `factory_id` / `item_id` `0` filter (give `[]`); blank `transaction_type` means no filter; dates inclusive ([BUG-992] aware bounds); rows of a deleted factory, removed item or deleted product stay listed (D2, history). Defaults `skip 0`, `limit 100`. TC6 applies.
- **R2.** [BUG-640] (HR-6) Newest `performed_at` first, then `id` descending, before paging. *(Today: `performed_at` only.)*
- **R3.** A `factory_id` or `item_id` of another workspace returns `[]` (HR-16: nothing of that workspace is shown).

**Errors:** a negative `skip` / `limit` makes Postgres reject the query (DAO R10; unreachable from the API). **Side effects:** none.

---

## `ProductService.make_sellable(db, prod_id, quantity, workspace_id, user_id)` *(requires new method — BUG-2793)*
**Shape:** state-transition (stock move) · **Persistence:** writes · **Visibility:** public (new; for a new route such as `POST /products/{id}/make-sellable/`)

**Purpose:** Move N units from the not-for-sale bucket to the for-sale bucket of the same item and factory, and save the move (owner, OQ-51).

**Returns:** the for-sale (target) row, committed and re-read (D1).

**Rules:**
- **S1.** [BUG-2793] TC1–TC5 apply. The saved outcome is the manager's `make_sellable` M3–M8: both buckets changed (target created or restored if needed) and the two linked `transfer` ledger rows, committed together; the returned row is the target.
- **S2.** [BUG-2793] Every refusal (M1 404 / 400, M2 400 / 422) reaches the caller unchanged after the rollback; neither bucket nor any ledger row is saved.
- **S3.** [BUG-2793] A failure after the source was reduced (e.g. a patched failing commit, TC4) saves nothing: the source's `qty` is as before and no ledger row exists. The sum of the two buckets' `qty` is the same before and after any call, successful or not.
- **S4.** [BUG-2793] The locks the manager takes (M7) are held until this commit or rollback (one transaction). The clause (gap 2, decided by Claude under the reviewer's delegation, 2026-11-21): each bucket read is `SELECT … FOR UPDATE OF products` — `with_for_update(of=Product)`, because `Product.item` is joined-loaded (`lazy="joined"`, `app/models/product.py`) and a plain `FOR UPDATE` on that outer join is refused by Postgres (manager HR-10 fix note; BUG-029 form) — with no `SKIP LOCKED` and no `NOWAIT` (a concurrent move waits). Exactly one commit per call. The race itself is not unit-testable; the clause is checked through the recorded SQL.

**Errors:** as the manager's `make_sellable`, unchanged. **Side effects:** commit; rollback on any error.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 26–30 | create: manager, commit, refresh | `create_product` R1; TC1, TC2, TC4, TC5 |
| 31–33 | create: any exception → rollback, re-raise | `create_product` R2; TC3 |
| 39–43 | update: manager, commit, refresh | `update_product` R1 |
| 44–46 | update: exception → rollback, re-raise | `update_product` R2 |
| 48–49 | get: pass-through, no `include_deleted` | `get_product` R1, R2 (BUG-2772) |
| 57–62 | list: pass-through | `list_products` R1 |
| 65–69 | delete: manager, commit, refresh | `delete_product` R1 |
| 70–72 | delete: exception → rollback, re-raise | `delete_product` R2 |
| 84–92 | ledger: DAO pass-through (DAO 34–44 filters, order, paging) | `list_ledger` R1–R3 |
| — (missing) | `make_sellable` wrapper | `make_sellable` S1–S4 (BUG-2793) |

## Gap log
- G1 (`product_service.cases.md` gap 1) — fact — today a failing commit rolls back twice (inside `_commit_transaction`, then the service's `except`); a refusal from the manager rolls back once. Contract stays "at least one"; added to Notes. No rule change.
- G2 (`product_service.cases.md` gap 2) — fact + delegated decision (2026-11-21) — `make_sellable` S4 now states the clause: `FOR UPDATE OF products` (`with_for_update(of=Product)`, joined `item`; BUG-029 form), no `SKIP LOCKED` / `NOWAIT`, one commit per call. Applies equally to manager M7.
