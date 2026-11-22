# Spec — `app/services/order_workflow_service.py`

> **Status:** APPROVED (2026-11-06; revised 2026-11-07: OQ-24 answered → BUG-2348; cases gaps 1–3 closed)
> **Source commit:** e48a092

> **Revision 2026-11-09 (verifier finding; decided by Claude under the reviewer's delegation (2026-11-09)).** `get_workflows` R1 split: the order part is now R1a, tagged [BUG-100] with today's behaviour (no `ORDER BY`: storage order, so after an update paging can skip the updated row; the verifier's probe is recorded on BUG-100). Q1's "id order" was the intended order, not today's. Stays APPROVED.

> **Revision 2026-11-07.** Apply-review: OQ-24 answered by the owner (bug, as suggested) → 🐞 BUG-2348, `create_workflow` R6 rewritten to the intended behavior. Fill-gaps (`order_workflow_service.cases.md` gaps 1–3; decided by Claude under the reviewer's delegation (2026-11-07)): Notes for the test designer gain the patch target for TC3 on update / delete; `delete_workflow` R4 states the blocker list order (orders by id, the generic entry last, as BUG-948 R9b) and how a voided order is built. Stays APPROVED.

> **Form.** As `tests/unit/services/work_order_type_service.spec.md`. Below the service: `tests/unit/dao/order_workflow.spec.md` (APPROVED 2026-11-02), whose FU-1 is settled here, and `tests/unit/dao/base.spec.md`. **This service is not a `BaseService`:** it calls `db.commit()` / `db.rollback()` itself. Its outcomes match the Transaction contract **TC1–TC6** of `tests/unit/services/base_service.spec.md`, cited per method, with one difference stated in `update_workflow` R3 and `delete_workflow` R3 (a not-found answer ends the call without commit or rollback).

> **Review round 2026-11-06.** The owner's answers of 2026-11-02 on the DAO spec (O1 → BUG-1222, O2 → BUG-1223, O3 intended) and the HR-16 line BUG-1215 are turned into this service's rules. New: BUG-2385 (HR-1), BUG-2386 (precedent BUG-608), decided by Claude under the reviewer's delegation (2026-11-06), as are Q1 and the design of the refusal bodies. One order-workflow question for the owner: **OQ-24** (Q2), not blocking — its rule is written to today's behavior in its own rule.
>
> **Verified by running** (`v1_ows.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tpl\D\`, one outer transaction rolled back against `marker_test`, private `COVERAGE_FILE`; nothing persisted): the class has no base but `object`; create commits (survives `db.rollback()`), stores `name="  "` and `status_sequence=[1, 1, 999999]` as sent, `allowed_reverts_json` left out is JSON `null`; a duplicate type raises `IntegrityError` 23505 and the session is usable; the same type in another workspace is accepted; update sets `description` / `allowed_reverts_json`, and an explicit `null` for them (and for `name`) changes nothing; update and delete in another workspace or of id `0` return `None` / `False`; **a pending change stays pending (not committed, not rolled back) after a not-found update**; a failing commit gives exactly one rollback and nothing saved; delete commits; list order on three rows was id order; `get_by_type` is exact. BUG-1222 and BUG-1223 were verified in the DAO review. **Not run:** HTTP; the intended behavior of any bug.

## Review

### House-rule violations — applied automatically

- **HR-1** `create_workflow` R2, `update_workflow` R5 — `name` is a plain `str`: `""`, `"  "` and `" Purchase "` are stored as typed (verified with `"  "`). Intended: stored trimmed; blank or whitespace-only refused by `OrderWorkflowCreate` / `OrderWorkflowUpdate` (422), nothing written.
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-2385 (pattern `blank-name-accepted`). Fix in `app/schemas/order_workflow.py`.
- **HR-16** `create_workflow` R4, `update_workflow` R6 — already logged from the DAO review: **BUG-1215** (status ids of another workspace, or unknown, are stored). Its rules are written here.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-1215 (existing). Rules: `create_workflow` R4, `update_workflow` R6.

### Precedent matches — confirmed under the delegation

- **BUG-608 / BUG-942 precedent** `update_workflow` R7 — the update drops explicit `null`s (`exclude_none`), so `description` and `allowed_reverts_json`, once set, can never be emptied (verified).
**Answer:** bug — per BUG-608 precedent: an explicit `null` clears `description` and `allowed_reverts_json`; `null` for `name` or `status_sequence` is refused with 422; omitted fields stay unchanged (precedent — confirmed by Claude under the reviewer's delegation (2026-11-06))
**Resolution:** 🐞 BUG-2386 (pattern `exclude-none-blocks-clear`). Fix in this service (pass a dict built with `exclude_unset=True` only) and the update schema (non-nullable `name`, `status_sequence`). `allowed_reverts_json` stays a reserved field (owner O3): clearing it is storing it.

### Owner's answers of 2026-11-02 (DAO spec O1–O3), applied here

- **O1 → BUG-1222** `delete_workflow` R4, R5: refused while a purchase order uses it, with the orders listed; the `purchase` row is never deleted. **Body design** (decided by Claude under the reviewer's delegation (2026-11-06), following the item delete refusal BUG-948 and the owner's rule that a refusal lists its blockers): `app.core.exceptions.ValidationError` (400) with `detail` and `errors`, as R4 and R5 state.
- **O2 → BUG-1223** `update_workflow` R8: `status_sequence` read-only on the `purchase` row. Detail message chosen by Claude under the delegation (2026-11-06).
- **O3** intended: `allowed_reverts_json` is stored and nothing reads it.

Cited, not this service's rule: **BUG-1217** (`GET /order-workflows/` has no lower bound on `limit`, an endpoint line). **BUG-1227** (an in-place list change is lost; nothing in this service changes a list in place: `update_workflow` assigns a new list).

Checked and **not** violated here: **HR-2** — a second workflow of one type in a workspace is refused by `uq_order_workflows_workspace_type`; the `IntegrityError` reaches the API's global handler, 409, not 500 (integration). **HR-3** — Q1. **HR-4** — no soft delete. **HR-5, HR-8** — no filter, no `LIKE`. **HR-6** — Q1. **HR-7** — BUG-1217. **HR-9** — no audit column. **HR-10** — after BUG-1222 the database's `RESTRICT` catches an order linked between the check and the delete (`IntegrityError`, rolled back), so no lock is needed. **HR-11 … HR-15** — no external system, no money.

**Permission checks:** none: any active member may create, change and delete workflows (endpoints use `get_current_workspace`). No web page calls `/order-workflows/`. Noted in `docs/future/permissions.md`; not asked (the owner reviewed these endpoints on 2026-11-02 without restricting them).

### New questions

### Q1. List order and the `type` code — ✅ intended
**Background:** A workspace normally holds one workflow, type `purchase`, seeded with it. The list is the base DAO's `get_by_workspace`, which after BUG-100 orders by `id`. `type` is free text compared exactly; only `purchase` is read by any code.
**What happens today:** The list comes back in storage order, which matched `id` order on three fresh rows (verified) but is not guaranteed: the base DAO has no `ORDER BY` until BUG-100 is fixed (verifier, 2026-11-09: after updating row A the list returned [B, A]). Any `type` text is accepted; a type other than `purchase` is stored and has no effect.
**Example:** `POST` with `type: "Purchase"` creates a second, inert row; the purchase orders keep using `purchase`.
**Rules affected:** `get_workflows` R1, `create_workflow` R3
**Suggested answer:** `intended — id order is a stable order for a list of one or a few system rows (HR-6's name order adds nothing here); type is a code, exact as the DAO's R3, and an unknown code is inert`.
**Answer:** intended
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-06). Rules unchanged, marked ✅.

### Q2. `POST` can create the `purchase` workflow with any steps — 🐞 BUG-2348 (owner, OQ-24)
**Background:** Your O2 answer made the purchase workflow's steps read-only through `PUT`; the system writes them (`ensure_po_workflow_record`, on every purchase order write). `POST /order-workflows/` was not part of that answer. Every workspace is seeded with its `purchase` row, so a `POST` with `type: "purchase"` is normally refused as a duplicate (409). It succeeds only where the row is missing: an old workspace, or one whose row was deleted (BUG-1222 stops that from now on).
**What happens today:** In such a workspace `POST {"type": "purchase", "status_sequence": [<Draft>]}` is stored as sent. Until the next purchase order write puts the four stages back, `Draft` counts as the finished stage: draft orders read as finished, finished orders as open.
**Example:** In a workspace without the row, someone posts `[<Draft>]`. The inventory page's open-order counts change until a purchase order is next created or moved.
**Rules affected:** `create_workflow` R6
**Suggested answer:** `bug — creating a workflow of type purchase through the API is refused (400 "The purchase workflow is managed by the system", nothing written), as O2 did for PUT; the system creates the row itself on the next purchase order write`.
**Alternatives:** (a) intended — accept it; the next purchase order write repairs the steps. (b) accept the row but ignore the sent `status_sequence`, filling in the four stages.
**Answer:** owner, 2026-11-07: suggested answer (creating the purchase workflow through the API is refused with 400, as for PUT under BUG-1223).
**Resolution:** 🐞 BUG-2348 (pattern `system-row-not-protected`, as BUG-1223). Rules: `create_workflow` R6, Errors.

## Overview
`OrderWorkflowService` is the transaction boundary for order workflows: per workspace, the ordered list of status ids an order passes through. In practice one row per workspace, type `purchase`, whose last status is what makes a purchase order "finished" for the open-order counts (`app/utils/order_workflow_terminal.py`). The `/order-workflows/` endpoints call it; it calls `order_workflow_dao` directly (no manager) and commits or rolls back. "Not found" is returned as `None` / `False`, which the endpoints turn into 404 `Order workflow not found`.

**Callables:** 6 specified · 1 not specified
**Externals to mock:** none
**Integration-only behavior:** 404 `Order workflow not found` for `None` / `False` (endpoints); 409 for `IntegrityError` (global handler); 201 / 204 status codes; BUG-1217; the `ValidationError` 400 body format (`api_exception_handler`).

**Facts for the test designer**
- Import: `from app.services.order_workflow_service import OrderWorkflowService, order_workflow_service`. `OrderWorkflowService()` takes no arguments and inherits nothing. Parameters are positional-or-keyword.
- Schemas, `app/schemas/order_workflow.py`: `OrderWorkflowCreate(name: str, type: str, description: str | None = None, status_sequence: list[int], allowed_reverts_json: dict | None = None)`, no validators. `OrderWorkflowUpdate(name, description, status_sequence, allowed_reverts_json)`, all optional, default `None`; **no `type`**: the type of a row never changes.
- Table and model facts: `tests/unit/dao/order_workflow.spec.md` (Model facts, N1–N4). Statuses: build `Status` rows of the workspace for valid ids; `seed_po_workflow(db, workspace_id)` from `app/db/seed_po_workflow.py` makes the `purchase` row and its four stage statuses.
- Purchase orders for BUG-1222: as the DAO spec's Notes (`PurchaseOrder(workspace_id, po_number, destination_type, destination_id, current_status_id, created_by, order_workflow_id)`).

**Notes for the test designer**
- Session and commits: as `base_service.spec.md` Notes. "Committed" = survives a test-level `db.rollback()`. Commit the setup before an error path, since the service's rollback discards everything pending.
- One case per TC rule on one write method is enough for TC2, TC4, TC5 (the three writes share the pattern); TC1 and TC3 get one case per write method.
- `update_workflow` R3 / `delete_workflow` R3 (no commit, no rollback on not-found): flush a pending row (`make_workspace`), call with id `0`, check the row is still in the session, then `db.rollback()` and check it is gone.
- Bug rules (BUG-1215, BUG-1222, BUG-1223, BUG-2348, BUG-2385, BUG-2386) are strict xfail. For BUG-2348 use a workspace with no `purchase` row (plain `make_workspace`, no `seed_po_workflow`), so today's result is a created row, not an error.
- **TC3 on update and delete without a bug (gap 1):** patch the DAO the service imports, `app.services.order_workflow_service.order_workflow_dao`: `patch.object(order_workflow_dao, "update", side_effect=RuntimeError("boom"))` (or `"remove"` for delete), after flushing an unrelated pending row. The same exception object reaches the caller, the pending row is gone, the workflow is unchanged, and the session is usable. *(Test mechanics, decided by Claude under the reviewer's delegation (2026-11-07).)*
- **Voided purchase order (gap 3):** a `PurchaseOrder` (columns as in Facts) with `voided=True`; `voided_at`, `voided_by`, `void_note` may stay `NULL` (nullable, nothing checks them). A finished one has `current_status_id` = the last id of the workflow's `status_sequence`.

## Not specified
- `order_workflow_service` — module-level singleton, no logic.

---

## `OrderWorkflowService.get_workflows(db, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /order-workflows/`, `limit <= 100`)

**Rules:**
- **R1.** Returns the workspace's workflows, `skip` / `limit` applied (defaults 0, 100). Another workspace's rows are never returned.
- **R1a.** [BUG-100] ✅ (Q1: `id` order is enough here) Rows come in `id` ascending order before `skip` / `limit`, so pages neither repeat nor miss a row. *(Today: no `ORDER BY` in the base DAO; rows come in storage order. Verifier probe 2026-11-09: workflows A, B; after updating A the list returns [B, A], and paging with `limit=1` (skip 0, 1) never shows A.)* Non-strict xfail (physical order).
- **R2.** Read only (TC6).

---

## `OrderWorkflowService.get_by_id(db, workflow_id, workspace_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `GET /order-workflows/{id}/`)

**Rules:**
- **R1.** Returns the workflow with that id in that workspace; another workspace's id, an unknown id or `0` returns `None`.
- **R2.** Read only (TC6).

---

## `OrderWorkflowService.get_by_type(db, workflow_type, workspace_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `GET /order-workflows/type/{workflow_type}/`)

**Rules:**
- **R1.** Returns the DAO's `get_by_type` unchanged (DAO spec R1–R5: exact type, own workspace, `None` otherwise).
- **R2.** Read only (TC6).

---

## `OrderWorkflowService.create_workflow(db, workflow_in, workspace_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /order-workflows/`)

**Purpose:** Add a workflow to the workspace and save it.

**Returns:** the new `OrderWorkflow`, committed and re-read (TC1, TC2).

**Rules:**
- **R1.** A row is created with every field of `workflow_in` and the given `workspace_id`; committed (TC1); returned re-read (TC2). `allowed_reverts_json` left out is stored as JSON `null` and reads back `None`.
- **R2.** [BUG-2385] (HR-1) `name` is stored trimmed; `""` or whitespace-only is refused by `OrderWorkflowCreate` (`pydantic.ValidationError`, 422), nothing written. *(Today: stored as typed. Verified with `"  "`.)*
- **R3.** ✅ (Q1) `type` is stored as sent and compared exactly; one type per workspace: a second row of the same type in the workspace raises `IntegrityError` 23505 (`uq_order_workflows_workspace_type`), rolled back, re-raised (TC3; 409 at the API). The same type in another workspace is accepted.
- **R4.** [BUG-1215] (HR-16) Every id in `status_sequence` must be a status of the caller's workspace; the first that is not (another workspace's, or unknown) → `HTTPException` 404 `Status with ID {id} not found`, nothing written. *(Today: stored unchecked. Verified in the DAO review.)*
- **R5.** ✅ (owner O2: only `purchase` was restricted) Apart from R4, the list is stored as sent for types other than `purchase`: `[]` and repeated ids are accepted.
- **R6.** [BUG-2348] (owner, OQ-24) A `workflow_in` whose `type` is exactly `purchase` (the system's `PO_WORKFLOW_TYPE`) is refused before anything is written: `HTTPException` 400 `The purchase workflow is managed by the system`, whatever its `status_sequence` and whether or not the workspace already has a `purchase` row (so this 400 comes before R3's duplicate and R4's status check). Rolled back, nothing saved. Other spellings (`Purchase`, ` purchase`) are ordinary inert types (R3, ✅ Q1). *(Today: where the workspace has no `purchase` row the row is created with the sent steps, and the terminal check reads them until the next purchase order write replaces them; where one exists, R3's `IntegrityError`. Verified in the DAO review.)*
- **R7.** Any exception (R2's, R3's, R4's, a database error) rolls back and reaches the caller unchanged; nothing saved (TC3). Commit and re-read failures follow TC4, TC5.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| duplicate type in the workspace | `IntegrityError`, `.orig.pgcode == "23505"` | — |
| [BUG-1215] foreign or unknown status id | `HTTPException` 404 | `Status with ID {id} not found` |
| [BUG-2385] blank `name` | `pydantic.ValidationError` (schema) | — |
| [BUG-2348] `type` `purchase` | `HTTPException` 400 | `The purchase workflow is managed by the system` |

**Side effects:** one `order_workflows` row, committed; on error, rolled back.

---

## `OrderWorkflowService.update_workflow(db, workflow_id, workflow_in, workspace_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /order-workflows/{id}/`)

**Purpose:** Change a workflow's name, description, steps or reserved revert settings, and save.

**Returns:** the `OrderWorkflow`, committed and re-read; or `None` when not found.

**Rules:**
- **R1.** The workflow is found by id **and** workspace; another workspace's id, an unknown id or `0` → returns `None` (404 at the API), nothing written.
- **R2.** Fields sent with a value are set on the row; fields left out stay. Committed (TC1); returned re-read (TC2).
- **R3.** On `None` (R1) nothing is committed and nothing is rolled back: changes already pending in the session stay pending. *(Differs from TC: there is no exception, so no rollback.)* Verified.
- **R4.** `type` cannot be changed (not in the schema).
- **R5.** [BUG-2385] (HR-1) A sent `name` is stored trimmed; blank is refused (422), nothing written. *(Today: stored as typed.)*
- **R6.** [BUG-1215] (HR-16) A sent `status_sequence` is checked as `create_workflow` R4; refused → 404, nothing written. *(Today: stored unchecked.)*
- **R7.** [BUG-2386] An explicit `null` clears `description` (→ SQL `NULL`) and `allowed_reverts_json` (→ `None`); `null` for `name` or `status_sequence` is refused by the schema (422), nothing written; omitted fields stay. *(Today: every `null` is dropped and the field keeps its value. Verified.)*
- **R8.** [BUG-1223] (owner O2) On the workflow of type `purchase`, a request that carries `status_sequence` (any value, even the current one) is refused: `HTTPException` 400 `The purchase workflow's steps are managed by the system`, nothing written, the other fields of the same request included. `name`, `description` and `allowed_reverts_json` alone may still be changed. *(Today: stored; `[<Draft>]` makes Draft terminal and `[]` leaves none, until the next purchase order write restores the four stages. Verified in the DAO review.)*
- **R9.** For other types, a sent `status_sequence` replaces the list as sent, `[]` and repeats included (✅ owner O2), subject to R6.
- **R10.** Any exception rolls back and reaches the caller unchanged; nothing saved (TC3). Commit and re-read failures follow TC4, TC5: a failing commit gives exactly one rollback (verified).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| [BUG-1215] foreign or unknown status id | `HTTPException` 404 | `Status with ID {id} not found` |
| [BUG-1223] `status_sequence` sent on `purchase` | `HTTPException` 400 | `The purchase workflow's steps are managed by the system` |
| [BUG-2385] / [BUG-2386] blank `name`, `null` name or sequence | `pydantic.ValidationError` (schema) | — |

**Side effects:** changed columns, committed; on error, rolled back; on not-found, nothing.

---

## `OrderWorkflowService.delete_workflow(db, workflow_id, workspace_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /order-workflows/{id}/`, 204)

**Purpose:** Remove a workflow nothing uses.

**Returns:** `True` when deleted; `False` when not found.

**Rules:**
- **R1.** Not found by id and workspace (another workspace's, unknown, `0`) → `False` (404 at the API), nothing written.
- **R2.** A workflow of a type other than `purchase` that no purchase order uses is deleted (hard delete) and committed: it is gone after a test-level `db.rollback()`. Returns `True`.
- **R3.** On `False` nothing is committed or rolled back, as `update_workflow` R3.
- **R4.** [BUG-1222] (owner O1) A workflow any purchase order points at (`purchase_orders.order_workflow_id`, voided and finished orders included) is not deleted: `app.core.exceptions.ValidationError` (400), `detail` `Order workflow is in use by purchase orders`, `errors` = one `{"type": "purchase_order", "id": <order id>}` per such order, in ascending order id; nothing written: the workflow stays and every order keeps its `order_workflow_id`. An order of another workspace pointing at it (invalid data, HR-16) is covered by one `{"type": "other_workspace"}` entry with no id, **always last**, once however many such orders exist (as BUG-948 R9b; gap 2, decided by Claude under the reviewer's delegation (2026-11-07)). A workflow used only by such orders gives `[{"type": "other_workspace"}]`. Voided and finished orders block like any other (gap 3: a voided order is `voided = True`). *(Today: deleted with 204; the ORM sets each order's `order_workflow_id` to `NULL` first. Verified in the DAO review.)*
- **R5.** [BUG-1222] (owner O1) The workflow of type `purchase` is never deleted, even with no orders: `ValidationError` (400), `detail` `The purchase workflow cannot be deleted`, `errors` `[]`, nothing written. When it also has orders, this answer is given, not R4's (clearing the orders would not make it deletable). *(Today: deleted.)*
- **R6.** Any exception rolls back and reaches the caller unchanged; nothing saved (TC3). A failing commit follows TC4. There is no re-read (TC2 and TC5 do not apply).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| [BUG-1222] in use | `ValidationError` 400, `errors` listing orders | `Order workflow is in use by purchase orders` |
| [BUG-1222] type `purchase` | `ValidationError` 400, `errors` `[]` | `The purchase workflow cannot be deleted` |

**Side effects:** the row deleted, committed; on refusal or error, nothing.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 8 | no `BaseService` | header; TC notes |
| 11–13 | list via base DAO, defaults; no `ORDER BY` (BUG-100) | `get_workflows` R1, R1a, R2 |
| 15–17 | by id and workspace | `get_by_id` R1, R2 |
| 19–21 | by type | `get_by_type` R1, R2 |
| 25–31 | create: dump, workspace, flush, commit, refresh | `create_workflow` R1–R6 |
| 32–34 | create: any exception → rollback, re-raise | `create_workflow` R3, R7 |
| 39–41 | update: not found → `None`, no commit / rollback | `update_workflow` R1, R3 |
| 42 | update: base `update` with the schema (`exclude_unset`, `exclude_none`; BUG-2386) | `update_workflow` R2, R4–R9 |
| 43–45 | commit, refresh, return | `update_workflow` R2 |
| 46–48 | update: exception → rollback, re-raise | `update_workflow` R10 |
| 53–55 | delete: not found → `False` | `delete_workflow` R1, R3 |
| 56–58 | delete: base `remove` (no dependents check, BUG-1222), commit, `True` | `delete_workflow` R2, R4, R5 |
| 59–61 | delete: exception → rollback, re-raise | `delete_workflow` R6 |
| 64 | module singleton | Not specified |

## Gap log
G1 (`order_workflow_service.cases.md` gap 1) — Test mechanics — Notes: TC3 on update / delete is reached by patching `order_workflow_dao.update` / `remove` on the module the service imports. No rule changed.
G2 (`order_workflow_service.cases.md` gap 2) — Intent, decided under the delegation (2026-11-07) — `delete_workflow` R4: order entries by id ascending, the single `other_workspace` entry last (BUG-948 R9b's order).
G3 (`order_workflow_service.cases.md` gap 3) — Fact — Notes and R4: a voided purchase order is `voided = True` (other void columns nullable); it blocks the delete.
V1 (`order_workflow_service.verify.md`, 2026-11-09) — Contradiction — `get_workflows` R1 claimed `id` order as today's; the order is now R1a, tagged [BUG-100] with today's storage order and the verifier's probe.
