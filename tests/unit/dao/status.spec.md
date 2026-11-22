# Spec — `app/dao/status.py`

> **Status:** APPROVED (2026-11-02; O2 is boxed by the owner: not decided, no rule on it)
> **Source commit:** e48a092

> **Review round 2026-11-02.** O1 and O3 are the owner's answers (owner's answers relayed by the coordinator, 2026-11-02): BUG-1220, BUG-1221. **O2 is boxed:** the owner's words were "box this for later discussion", so it is not an answer, no rule rests on it, and BUG-1018 and BUG-1019 keep their open replacement question. BUG-1220's rule belongs in the status service's spec (FU-1); BUG-1221's is `create` R2a, R2b. Added by running (`ar_1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refdao\`, rolled back): a temporary normalised unique index gives 23505 for the same name and for `" feat "` against `Feat`, and allows the same name in another workspace.

> **No code of its own.** `DAOStatus` has an empty body. The rules below are only what is particular to this model when the base methods run on it; everything else is in `tests/unit/dao/base.spec.md`.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug. Raw lookups stay raw (HR-4 scope; base Q4). HR-16: a row linking to another workspace's row is invalid data.
>
> **Verified by running** (scripts `rd_h.py`, `rd_0.py`, `rd_2.py`, `rd_2b.py`, `rd_5.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\refdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints, indexes, no trigger, its three referencing foreign keys; `create` from `StatusCreate`, directly and through `StatusService`; two rows of one name; a missing `comment`; `StatusService` reading, updating and deleting another workspace's row; `seed_default_statuses` and `seed_po_workflow` (9 + 4 = 13 rows per workspace); deleting a status used by a transfer order and by a purchase order, through the ORM and by raw SQL; renaming `Receiving` and then `PurchaseOrderManager._resolve_po_stage_status_id` and `ensure_po_workflow_record`; deleting `Complete`. **Not run:** anything over HTTP; the intended behavior of any bug.

## Review
> O1 and O3 answered 2026-11-02; O2 boxed.

| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| O1 | The statuses purchase orders depend on can be renamed or deleted | bug — refused with 400 | owner |
| O2 | BUG-1018 and BUG-1019 remove the fixed status ids, and nothing says which status takes their place | **boxed**, for later discussion | not decided |
| O3 | One workspace can hold two statuses of one name | bug — unique per workspace; a script cleans stored duplicates first | owner |

### House-rule violations — applied automatically

No rule of this DAO. Two new bugs were logged for code it leaves to its callers, and their rules belong in the status service's spec (FU-1), so no rule here carries the tags:
- **Owner's refusal rule** (BUG-948) — a status in use cannot be deleted, and the answer is 400 "Required field is missing.", which names nothing. **BUG-1218** (pattern `refused-delete-without-blockers`).
- **HR-7** — `GET /statuses/` has no lower bound on `limit`. **BUG-1217** (pattern `missing-limit-lower-bound`).

Reused, not new: **BUG-035** (statuses API unscoped), **BUG-100** (`get_multi` order), **BUG-101** (`remove` of a missing id), **BUG-1018**, **BUG-1019** (fixed default ids).

Checked and **not** a new line here: **HR-4** — no soft-delete column. **HR-1, HR-2** — names are O3 and FU-1. **HR-5, HR-8, HR-9, HR-10, HR-15** — no filter, `LIKE`, audit column, state change or money in this DAO.

### New questions

### O1. The statuses purchase orders depend on can be renamed or deleted — 🐞 BUG-1220
**Background:** A status is a row of a workspace, with a name and a comment. Purchase orders move through four stages, `Draft`, `Planning`, `Receiving`, `Complete`, and the code finds each stage's row **by that exact name**. The order workflow's `status_sequence` holds the same rows' ids as plain numbers, with no foreign key. `PUT` and `DELETE /statuses/{id}/` have no check of any kind, and BUG-035 makes that true for any workspace's row. The frontend has no screen for either call, so today this takes a direct API call.
**What happens today, verified:**
- Rename `Receiving` to `Goods in`: a move to the stage answers 422 `Purchase order stage status 'Receiving' not found for this workspace`, until something runs `ensure_po_workflow_record`. That creates a **new** `Receiving` row and rewrites the workflow's sequence to it. Orders already on the old row now show `Goods in`, outside the sequence.
- Delete `Complete` while no order uses it: the row goes, and the sequence keeps the id of a row that no longer exists, until the same re-creation.
- Renaming a stage in use, or a default status, gives no warning either.
**Example:** A user renames "Receiving" to "Goods in" with the API. The next receipt on a purchase order fails with a 422. The next new purchase order silently creates a second "Receiving", and old and new orders in the same stage now show different names.
**Rules affected:** none here; the rule would go in the status service's spec.
**Suggested answer:** `bug — a status named in PO_STAGE_STATUSES or listed in a workflow's status_sequence cannot be renamed or deleted: 400, naming the workflow; nothing written`. Alternative: `intended — only a direct API call reaches it`; or remove `PUT` and `DELETE /statuses/{id}/`, which no screen uses.
**Answer:** bug — refuse with 400 for any status that is a purchase order stage or is in a `status_sequence`
**Resolution:** owner's answer 2026-11-02: 🐞 BUG-1220 (pattern `system-row-not-protected`). `PUT` changing the name and `DELETE` of such a status answer 400 naming the workflow, nothing written. The DAO stays raw: `remove` R3 and R4 hold, and the rule goes in the status service's spec, FU-1.

### O2. Which status replaces the fixed ids — 📦 boxed
**Background:** `TransferOrderCreate.current_status_id` defaults to `1`, and `POST /sales-orders/` falls back to `10`, commented `"Started" status for workspace 1`. Both are global ids, so in every other workspace they point at someone else's row (BUG-1018, BUG-1019, already logged). Both bugs say "the status is taken from the caller's workspace" and neither says which one. The column is NOT NULL with `ON DELETE RESTRICT`. Every workspace is seeded with 9 statuses (`Pending` first) plus the 4 purchase stages. `Started` is not among them.
**What happens today:** Neither order type moves through statuses. `TransferOrderManager` refuses a change ("Status is derived from workflow state") and completes by `completed_at`; the sales schema's comment calls the field vestigial. So the value is set once, shown as `current_status_name` on transfer orders, and never changes.
**Example:** In a new workspace a transfer order is created. It shows the status name of id 1, from another company. When it is completed it still shows that name.
**Rules affected:** none here; the rules go in the transfer and sales managers' specs, on BUG-1018 and BUG-1019.
**Suggested answer:** `the row named Pending in the caller's workspace, for both order types; if it is missing (renamed, or an old workspace), the seed creates it, as purchase stages do`. That needs names to be reliable, so it depends on O1 and O3. Alternative: make the column nullable and stop showing it, since nothing uses the value.
**Answer:** boxed — the owner's words, 2026-11-02: "box this for later discussion"
**Resolution:** not decided, and the suggestion above is not accepted. No rule rests on it. BUG-1018 and BUG-1019 keep their open replacement question.

### O3. One workspace can hold two statuses of one name — 🐞 BUG-1221
**Background:** `statuses` has no unique constraint on `(workspace_id, name)`. Code that finds a status by name takes the first row it gets, with no `ORDER BY`: the purchase stage lookup, `ensure_po_stage_statuses`, `seed_default_statuses`.
**What happens today:** Two rows of one name are stored with no error (verified). `POST /statuses/` itself always fails (R1), but `PUT` can rename a row onto another's name, and O1 shows the seed can produce a second row.
**Example:** After O1's rename, renaming `Goods in` back gives two `Receiving` rows. Which one a purchase order moves to depends on physical row order.
**Rules affected:** `create` R2
**Suggested answer:** `bug — per HR-2: unique per workspace, case-insensitive after trimming, with a unique index; a duplicate is 409`. Stored duplicates need a clean-up first, and orders point at them. The missing `ORDER BY`s are a bug either way, logged in the purchase order manager's spec (FU-2).
**Answer:** bug — unique per workspace; stored duplicates are cleaned up by a script first
**Resolution:** owner's answer 2026-11-02: 🐞 BUG-1221 (pattern `python-only-uniqueness`). HR-2 fixes the compare: case-insensitive after trimming. The script runs first and repoints orders and `status_sequence` to the row kept. With the index a name has one row, so the by-name `.first()` calls need no `ORDER BY` and no bug is logged for them (FU-2). Rules: `create` R2, R2a, R2b.

## Overview
`DAOStatus` is the base DAO on `statuses`. Status rows are workspace-owned reference data: seeded with every workspace, used as the current stage of purchase orders and as a label on sales and transfer orders. Callers: `StatusService` (`get_multi`, `get`, `create`, `update`, `remove`), and `PurchaseOrderManager` (`get`, line 688). Most order code queries the table itself.

**Callables:** 0 specified · 2 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `statuses`, class `app.models.status.Status`):** `id` Integer PK. `workspace_id` Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE. `name`, `comment` String NOT NULL, no length, no default, no unique constraint today (BUG-1221 adds one). Referenced with `ON DELETE RESTRICT` by `purchase_orders`, `sales_orders` and `transfer_orders` (`current_status_id`, NOT NULL), each with a relationship and a backref on `Status` that has no `passive_deletes`. No trigger. `order_workflows.status_sequence` holds ids as JSON text: no foreign key.

**Notes for the test designer:**
- Use the module singleton `status_dao`. Create rows from a dict with `workspace_id`.
- R2a and R2b are written to the index: strict xfail on BUG-1221.
- For R4, build a `TransferOrder(workspace_id, transfer_number, source_location_type, source_location_id, destination_location_type, destination_location_id, current_status_id, created_by)`, flush and `db.expire_all()` first. Call in `with db.begin_nested():`.

## Not specified
- `DAOStatus` — empty class. `status_dao` — module-level singleton.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Status service and endpoint** (`app/services/status_service.py`, `app/api/v1/endpoints/statuses.py`, not yet specified) | BUG-035, whose "create likely 500s" is now verified: `IntegrityError` 23502, which the API's handler answers as 400 "Required field is missing.". BUG-1217, BUG-1218, and the rule of **BUG-1220** (O1): rename and delete of a stage status or a status in a `status_sequence` answer 400 naming the workflow; a `comment` edit is allowed; this check runs before BUG-1218's. Consequence of BUG-035 worth a test: 13 rows per workspace and a cap of 100, and the order pages load this list (`useOrdersScopeData.ts`), so from the eighth workspace on a workspace's own statuses fall outside the page. HR-1: `StatusCreate` has no trim or blank check. | R1, reading the callers |
| FU-2 | **Purchase order manager** (`app/managers/purchase_order_manager.py`, no spec yet) | Read, not run: `_format_field_value` (line 688) reads the status raw with `status_dao.get`, so a row linking to another workspace's status puts that name in the order's change event (HR-16; all four `current_status_id` writers here use the workspace's own row, so only stored rows reach it). `_resolve_po_stage_status_id`, `_ensure_po_stage_statuses`: `.first()` by name, as in `app/db/seed_po_workflow.py` and `app/db/seed_default_statuses.py`; one candidate once BUG-1221's index exists, so no bug is needed. | O3, reading the callers |
| FU-3 | **Base spec** (`tests/unit/dao/base.spec.md`, `remove` R4) | R4 holds where no ORM relationship exists, and it was tested on temporary tables. On real models with a backref and no `passive_deletes`, SQLAlchemy nulls the children first: on `statuses` that fails differently (R4 of this spec), and on `order_workflows` the delete **succeeds** (`tests/unit/dao/order_workflow.spec.md` O1). | R4 |

---

## Inherited methods, what is particular to this model
- **R1.** `create` from a `StatusCreate` raises `IntegrityError`, `.orig.pgcode == "23502"`, on `workspace_id`: the schema has no such field and base `create` adds none (base R8). Nothing is stored. A dict with `workspace_id` works.
- **R2.** `create` from a dict needs `workspace_id`, `name` and `comment`; without `comment`, `IntegrityError` 23502. The same name in another workspace is stored.
- **R2a.** [BUG-1221] (O3, HR-2) A second row with the same workspace and name raises `IntegrityError`, `.orig.pgcode == "23505"`, nothing stored. *(Today: stored with no error. Verified.)*
- **R2b.** [BUG-1221] (O3, HR-2) The compare is case-insensitive after trimming: `" feat "` collides with `Feat`. *(Today: both stored.)*
- **R3.** Removing a status no order uses deletes the row. An id listed in an `order_workflows.status_sequence` stays there: the row is gone and nothing else changes. (The DAO stays raw; the service refuses this, BUG-1220.)
- **R4.** Removing a status an order uses raises `IntegrityError`, `.orig.pgcode == "23502"`, on `current_status_id`, not the `RESTRICT` error of base `remove` R4: the ORM tries to empty the order's link first. Nothing is deleted. The same delete in raw SQL raises 23001.

`get`, `get_multi` and `remove` have no workspace filter on this workspace-owned table: base `get` R4, `get_multi` R4, `remove` R5, ✅ intended at the base, with the service's leak in BUG-035.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 7–8 | empty class: no branch of its own | R1–R4 describe the base on this model |
| 11 | module singleton | Not specified |
