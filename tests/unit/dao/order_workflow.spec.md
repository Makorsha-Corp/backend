# Spec — `app/dao/order_workflow.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** O1, O2 and O3 are the owner's answers (owner's answers relayed by the coordinator, 2026-11-02): BUG-1222, BUG-1223, and O3 intended for now. Their API rules belong in the service's spec (FU-1); `remove` N3 is the DAO's part of BUG-1222. Added by running (`ar_1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refdao\`, rolled back): a raw delete of a workflow in use raises 23001.

> **Owner's answer 2026-11-02 on cases gap 2** (relayed by the coordinator): a `status_sequence` changed in place is saved or refused, never silently lost, on workflows other than the read-only `purchase`. Rule N4, BUG-1227. Verified by `ar_2.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refdao\`, rolled back: today's loss, and `MutableList` attached at run time saving an append and an item change while the value stays a `list`, serialises the same and `terminal_status_ids_by_workflow` still reads it.

> **Standing decisions applied here (not asked again):** raw lookups stay raw (HR-4 scope). HR-16: a row linking to another workspace's row is invalid data. Base behaviour is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Verified by running** (scripts `rd_h.py`, `rd_0.py`, `rd_2.py`, `rd_2b.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\refdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints, indexes, no trigger, its one referencing foreign key; every `workflow_type` below; one type in two workspaces; a duplicate type; a `None` sequence; `[]`; another workspace's id, an unknown id and a repeated id through `OrderWorkflowService`; `allowed_reverts_json`; a list changed in place; `seed_po_workflow`; `terminal_status_ids_by_workflow` after `PUT`-style updates; `ensure_po_workflow_record` restoring the sequence; **deleting a workflow a purchase order uses: the delete succeeds and the order's `order_workflow_id` becomes `NULL`**. **Not run:** anything over HTTP; the inventory page and the active orders list themselves (the terminal check was run, not those screens).

## Review
> All answered 2026-11-02.

| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| O1 | Deleting a workflow in use succeeds, and its purchase orders lose it | bug — refused, listing the orders; the seeded `purchase` row is never deleted; stored rows repaired | owner |
| O2 | Editing the purchase workflow's steps changes which orders count as finished, then undoes itself | bug — `status_sequence` read-only for `purchase` | owner |
| O3 | The "allowed reverts" setting is stored and nothing obeys it | intended for now | owner |

### House-rule violations — applied automatically

No rule of this DAO. One new bug was logged for its callers, and its rule belongs in the service's spec (FU-1), so no rule here carries the tag:
- **HR-16** — `POST` and `PUT /order-workflows/` store `status_sequence` unchecked: another workspace's status ids and ids that do not exist (verified through the service). Such a row is invalid. Intended: each id must be a status of the caller's workspace, otherwise 404 `Status with ID {id} not found`, nothing written. **BUG-1215** (pattern `cross-workspace-link-not-refused`).

**BUG-1217** (`GET /order-workflows/` has no lower bound on `limit`) is logged from the status spec and covers this endpoint.

Checked and **not** a new line here: **HR-6** — `.first()` on `(workspace_id, type)`, which `uq_order_workflows_workspace_type` makes one row. **HR-4** — no soft-delete column. **HR-8** — exact match. **HR-9** — no audit column. **HR-10** — this DAO only reads. **HR-15** — no money. **HR-1, HR-2** — names and types are the schema's (FU-1); a duplicate type is 409 through the API's handler, not a 500.

### New questions

### O1. Deleting a workflow in use succeeds, and its purchase orders lose it — 🐞 BUG-1222
**Background:** Each purchase order points at its workspace's `purchase` workflow (`purchase_orders.order_workflow_id`, `ON DELETE RESTRICT`). The workflow's last status is what makes an order "finished": open-order counts on the inventory page and the active orders list skip an order whose status is the last one. `DELETE /order-workflows/{id}/` checks nothing.
**What happens today, verified:** The database's `RESTRICT` never fires. SQLAlchemy loads the orders through the relationship and sets each `order_workflow_id` to `NULL` first, then deletes the workflow, with a 204. Afterwards a finished order is no longer terminal: `is_order_terminal` went from true to false, so it counts as open. The next new purchase order recreates the workflow with a new id. An order is re-linked only when its stage is next synced, which a finished order may never be.
**Example:** A workspace has 40 finished purchase orders. Someone calls `DELETE /order-workflows/7/`. It answers 204. The 40 orders now count as open wherever the terminal check is used, and their stored status has not changed.
**Rules affected:** none here; the rule would go in the service's spec. See `tests/unit/dao/status.spec.md` FU-3 on base `remove` R4.
**Suggested answer:** `bug — refused while any purchase order uses it: 400 with the orders listed (the owner's refusal rule, BUG-948), nothing written; the seeded purchase workflow cannot be deleted at all`. The ORM's nulling has to be turned off too (`passive_deletes="all"` on the relationship). Stored orders with `NULL` need a repair. Alternative: `intended — it recreates itself`, with the terminal check treating `NULL` as the workspace's current workflow.
**Answer:** bug — refuse, listing the blocking orders; never delete the seeded `purchase` row; repair stored rows
**Resolution:** owner's answer 2026-11-02: 🐞 BUG-1222 (pattern `delete-ignores-dependents`). A workflow any purchase order uses answers 400 with the orders listed; the `purchase` row answers 400 even with no orders; nothing written. A script restores `order_workflow_id` on rows left `NULL`. Rules: `remove` N3 here, the rest in the service's spec, FU-1.

### O2. Editing the purchase workflow's steps changes which orders count as finished — 🐞 BUG-1223
**Background:** The API lets a user edit `status_sequence`. `ensure_po_workflow_record` also sets it, to the four stages, every time a purchase order is created or its stage is synced. The order stages themselves are hard-coded in `PurchaseOrderManager`, not read from this list; only "the last id is the finished one" is read from it.
**What happens today, verified:** `PUT` with `[<Draft>]` makes `Draft` the terminal status, so draft orders count as finished and finished ones as open. `PUT` with `[]` leaves no terminal status at all. Neither is refused, and the next purchase order write silently puts the four stages back. Repeated ids and any integers are accepted (BUG-1215 stops foreign and unknown ones).
**Example:** Someone edits the workflow to remove "Planning". The change appears to work, the stages do not change, and it is gone after the next purchase order.
**Rules affected:** none here.
**Suggested answer:** `bug — status_sequence of the purchase workflow is read-only through the API: 400, nothing written; other types need a non-empty list with no repeats`. No other type exists in code: the docstring's `PFM`, `STM`, `MTM` appear nowhere else. Alternative: remove `POST`, `PUT` and `DELETE /order-workflows/`, which no frontend screen calls.
**Answer:** bug — `status_sequence` is read-only for `purchase`
**Resolution:** owner's answer 2026-11-02: 🐞 BUG-1223 (pattern `system-row-not-protected`). `PUT` carrying `status_sequence` on a `purchase` row answers 400, nothing written; `ensure_po_workflow_record` stays the only writer. The answer covers `purchase` only: the suggestion's clause on other types is not adopted. Rule in the service's spec, FU-1.

### O3. "Allowed reverts" is stored and nothing obeys it — ✅ intended
**Background:** `allowed_reverts_json` is accepted by `POST` and `PUT /order-workflows/` and returned. A search of `app/` finds no reader.
**What happens today:** Whatever is sent is stored and has no effect on any order. Left out, it is JSON `null`, not SQL `NULL`; both read back as `None`.
**Example:** A manager sets "Received may revert to Purchased". The order page still does what it did.
**Rules affected:** Model facts
**Suggested answer:** `intended for now — a reserved field; nothing to test beyond storing it`. Alternative: `bug — remove the field`.
**Answer:** intended for now
**Resolution:** owner's answer 2026-11-02: a reserved field. Nothing to test beyond storing it. Rules: none changed.

## Overview
`DAOOrderWorkflow` is the base DAO plus a lookup of one workspace's workflow by type. In practice a workspace has one row, type `purchase`, seeded with four stage status ids. Callers: `OrderWorkflowService` (reached by `/order-workflows/`), and `app/db/seed_po_workflow.py` (`get_by_type`). Two places read the table directly for the terminal status: `app/utils/order_workflow_terminal.py` and `PurchaseOrderService`.

**Callables:** 1 specified · 2 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `order_workflows`, class `app.models.order_workflow.OrderWorkflow`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `name`, `type` | String NOT NULL; `(workspace_id, type)` unique, `uq_order_workflows_workspace_type` | — |
| `description` | String nullable | `NULL` |
| `status_sequence` | `text` NOT NULL, holding JSON; the model's `JSONEncodedList` turns a list into text and back | — |
| `allowed_reverts_json` | generic `JSON` nullable | `NULL` |

- `status_sequence` is tracked by assignment only today: a list changed in place is **not** saved (verified; N4, BUG-1227). `[]` is stored as `[]`.
- Referenced by `purchase_orders.order_workflow_id` (nullable, `ON DELETE RESTRICT`, relationship `workflow`, backref `purchase_orders`, no `passive_deletes`). No trigger.

**Notes for the test designer:** Use the module singleton `order_workflow_dao`. Every parameter after `db` is keyword-only. Build `OrderWorkflow(workspace_id, name, type, status_sequence=[...])` directly. `make_workspace` seeds nothing, so an empty workspace has no workflow; `seed_po_workflow(db, workspace_id)` from `app/db/seed_po_workflow.py` makes the `purchase` row. N3 is strict xfail on BUG-1222: build `PurchaseOrder(workspace_id, po_number, destination_type, destination_id, current_status_id, created_by, order_workflow_id)`, flush and `db.expire_all()` first, and call in `with db.begin_nested():`. N4 is strict xfail on BUG-1227: change the list, flush, `db.expire(row)`, read it back.

## Not specified
- `order_workflow_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — `tests/unit/dao/base.spec.md`, apart from N1, N2. The header says every query must filter by workspace; `get`, `get_multi` and `remove` do not. `OrderWorkflowService` looks the row up by workspace before `remove`.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Order workflow service and schema** (`app/services/order_workflow_service.py`, `app/schemas/order_workflow.py`) | The rules of BUG-1215, BUG-1222 and BUG-1223; BUG-1217; HR-1 on `name`, and `type` is unvalidated text; list order after BUG-100 is `id` only, so HR-6's display order is the service's. | reading the callers |
| FU-2 | **Purchase order service** (`app/services/purchase_order_service.py`, lines 1113–1128) | Read, not run: a copy of `terminal_status_ids_by_workflow`. A fix to one must reach the other. | reading the callers |

---

## `DAOOrderWorkflow.get_by_type(db, *, workflow_type, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `OrderWorkflowService.get_by_type` ← `GET /order-workflows/type/{workflow_type}/`; `ensure_po_workflow_record`)

**Purpose:** One workspace's workflow of a type.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `workflow_type` | str | exact compare with `type` |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** the row, or `None`.

**Rules:**
- **R1.** The row of that workspace with exactly that type is returned, with `status_sequence` as a list of ints.
- **R2.** Workspace isolation: two workspaces can each have type `PFM`, and each gets its own. A workspace without the type, another workspace's id, or `0` returns `None`.
- **R3.** The compare is exact: `"pfm"`, `" PFM"`, `"PFM "` and `"P%"` find nothing for `PFM`.
- **R4.** `""` and `None` return `None`, with no error.
- **R5.** The contents of the row are not looked at: a row with `status_sequence` `[]`, or with ids of statuses that do not exist, is returned as stored.

**Errors:** none. **Side effects:** none

---

## Inherited methods, what is particular to this model
- **N1.** A second row with the same workspace and type raises `IntegrityError`, `.orig.pgcode == "23505"`, constraint `uq_order_workflows_workspace_type`.
- **N2.** `status_sequence=None` raises `IntegrityError` 23502.
- **N3.** [BUG-1222] (O1) Removing a workflow a purchase order uses raises `IntegrityError`, `.orig.pgcode == "23001"`, the workflow and the order's `order_workflow_id` unchanged. *(requires `passive_deletes="all"` on the relationship.)* *(Today: the delete succeeds and `order_workflow_id` becomes `NULL`. Verified; raw SQL already raises 23001.)*
- **N4.** [BUG-1227] (owner, cases gap 2) On a workflow of a type other than `purchase`, a `status_sequence` changed in place (`append`, item assignment) is saved by the next flush: read back after expiry, the change is there. *(requires `MutableList.as_mutable(JSONEncodedList)` on the column in `app/models/order_workflow.py`; the DAO does not change.)* *(Today: the change is lost with no error: `[1, 2]` after `append(3)` reads back `[1, 2]`. Verified.)*

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 18–20 | keyword-only parameters | Notes for the test designer |
| 35–36 | workspace AND exact type | R1, R2, R3, R4, R5 |
| 38 | `.first()`: row / `None` | R1, R2, R4 |
| 42 | module singleton | Not specified |

## Gap log
G2 (`order_workflow.cases.md` gap 2) — intent, the owner's answer 2026-11-02 — fact turned into rule N4, BUG-1227. The other gaps of that file are unchanged. The case designer needs a card for N4.
