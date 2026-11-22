# Spec — `app/services/status_service.py`

> **Status:** APPROVED (2026-11-04: the two pre-filled house-rule lines confirmed — decided by Claude under the reviewer's delegation (2026-11-04); no questions). Stays APPROVED after fill-gaps 2026-11-04 (Gap log at the end): BUG-1218 refusal shape, BUG-1220 detail text and stage-name match, rollback of both refusals — decided by Claude under the reviewer's delegation (2026-11-04); OQ-13 answered by the owner (2026-11-04) → BUG-1880 (rules here), BUG-1881, BUG-1882 (order code); O2 stays boxed.
> **Revision 2026-11-04 (apply-review, OQ-13):** the owner answered OQ-13 with the suggested answer: stage rows are found and protected ignoring capitals and outer spaces, as BUG-1221 compares names; a migration renames such rows to the exact stage name. `update_status` R4b rewritten (and with it `delete_status` R3, which points to it) and tagged BUG-1880; nothing else changed. Cards to revise: SSV-U-24 and SSV-D-16 (now protected: strict xfail on BUG-1220 / BUG-1880), plus cards for a stage name differing only in capitals and in outer spaces on both rename and delete; SSV-U-12, SSV-D-12 (`"Receiving Bay"`, `"Completed"`) stay as they are.
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md`. This service has **no manager** and does **not** inherit `BaseService`: it calls `status_dao` (inherited `BaseDAO` methods only) and commits and rolls back itself. Its writes have the same outcomes as **TC1–TC5** of `department_service.spec.md`, its reads **TC6**; the differences are listed under **Transaction rules** below. Below it: `tests/unit/dao/status.spec.md` (APPROVED; O2 boxed) and `tests/unit/dao/base.spec.md`.

> **Routed here and written as rules:** status DAO FU-1: **BUG-035** (the API is not scoped by workspace; create always fails), **BUG-1217** (`limit` lower bound, the endpoint's, cited), **BUG-1218** (a status in use cannot be deleted and the answer names nothing), **BUG-1220** (owner O1: stage statuses and statuses of a `status_sequence` refuse rename and delete), **BUG-1221** (owner O3: one name per workspace), HR-1 on `StatusCreate`. No new rule rests on **O2** (boxed by the owner: which status replaces the fixed ids of BUG-1018 / BUG-1019); this service sets no default status and is not where that answer would land.
>
> **Standing decisions applied here (not asked again):** HR-16: a row of another workspace is "not found", never read, changed or deleted. A refused delete lists what blocks it (owner's refusal rule, BUG-948 format). Input limits go on the input schemas, never on the response schema (BUG-915).
>
> **Verified by running** (`h.py`, `v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3d\`, one outer transaction rolled back against `marker_test`, session as the `db` fixture; nothing persisted): `create_status(StatusCreate(...))` raises `IntegrityError` 23502 on `workspace_id`; `get_by_id` returns another workspace's status and `None` for `0`; `update_status` of `0` → `None`; `{"name": null, "comment": null}` → unchanged; a rename to `"   "` is stored; `delete_status` of `0` → `False`; `delete_status` of another workspace's status → `True` and the row is gone. From the status DAO spec (verified there): a delete of a status an order uses → `IntegrityError` 23502; two rows of one name are stored. **Not run:** anything over HTTP; the intended behavior of any bug rule.

## Review

### House-rule violations — applied automatically

- **HR-1** `create_status` R4, `update_status` R6 — status names are stored as typed: `StatusCreate` and `StatusUpdate` have no trim and no blank check (verified: a rename to `"   "` is stored). Intended: both input schemas trim `name` and refuse a blank or whitespace-only one (`pydantic.ValidationError`, 422 at the API), nothing written; not on `StatusBase`, which `StatusResponse` inherits (per BUG-915).
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-1680 (pattern `blank-name-accepted`). Rules: `create_status` R4, `update_status` R6. Confirmed — decided by Claude under the reviewer's delegation (2026-11-04).
- **HR-6** `get_statuses` R3 — the list has no display order of its own (BUG-100 gives only `id` at the DAO, and not today). Intended: name case-insensitive ascending, then `id` ascending, before `skip` / `limit` (per BUG-1525).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-1681 (pattern `unordered-pagination`). Rules: `get_statuses` R3. Confirmed — decided by Claude under the reviewer's delegation (2026-11-04).

Existing bugs written as rules here, no new ID: **BUG-035** (every method), **BUG-1218** `delete_status` R4, **BUG-1220** `update_status` R4, `delete_status` R3, **BUG-1221** `create_status` R5, `update_status` R7. Cited, not a rule here: **BUG-1217** (`GET /statuses/` accepts `limit <= 0`, endpoint), **BUG-100** (DAO order), **BUG-1018 / BUG-1019** with the boxed **O2**.

Checked and **not** violated: **HR-2** — BUG-1221 (owner O3). **HR-3, HR-8** — no categorical filter, no `LIKE`. **HR-4** — `statuses` has no soft delete; a delete is a hard delete. **HR-5** — no filter. **HR-7** — BUG-1217. **HR-9** — no audit column. **HR-10** — a rename or delete of reference data; BUG-1220 refuses the harmful ones. **HR-11 … HR-15** — none applies. **HR-16** — violated today, already BUG-035 (HIGH).

**Permission checks:** none, and today not even workspace membership: the endpoints take only `get_current_active_user`, so any signed-in user reaches any workspace's statuses (BUG-035). After BUG-035 any active member of the caller's workspace may create, rename and delete its statuses, as for departments. No screen calls `POST`, `PUT` or `DELETE /statuses/` (status DAO O1); the order pages read `GET /statuses/`.

No questions.

## Overview
`StatusService` is the transaction boundary for statuses, the workspace's named stages (seeded with 9 general statuses and the 4 purchase order stages `Draft`, `Planning`, `Receiving`, `Complete`). The `/statuses/` endpoints call it. It calls the generic DAO methods directly and has no rule of its own today: no workspace, no protection of the purchase stages, no check before a delete. It answers "not found" with `None` (get, update) or `False` (delete); the endpoint turns each into 404 `Status not found`.

**Callables:** 5 specified · 2 not specified
**Externals to mock:** none.
**Integration-only behavior:** the 404 `{"detail": "Status not found"}` the endpoint makes of `None` / `False`; the endpoints' workspace dependency (none today; BUG-035 adds it); `skip >= 0`, `limit <= 100` (BUG-1217); schema validation (400 today, BUG-461; 422 intended); the global `IntegrityError` handler (23505 → 409 for BUG-1221; 23502 → 400 "Required field is missing." today for create and BUG-1218).

**Facts for the test designer**
- Import: `from app.services.status_service import StatusService, status_service`. `StatusService()` takes no arguments. Parameters are positional-or-keyword; the endpoints pass all after `db` by keyword.
- Schemas (`app/schemas/status.py`): `StatusCreate(name: str, comment: str)`, both required, no other check. `StatusUpdate(name: str | None = None, comment: str | None = None)`. `StatusResponse` = `StatusBase` + `id`. No `workspace_id` anywhere.
- Table `statuses` and its foreign keys: status DAO spec, Model facts. Build rows as `Status(workspace_id, name, comment)`.
- `PO_STAGE_STATUSES` (the four stage names) and `order_workflows.status_sequence` (JSON text of ids): status DAO spec O1.
- **BUG-035** adds a required parameter `workspace_id` to every method (after `db`; the endpoints pass the current workspace). Its rules below are written with it.

**Notes for the test designer**
- Session and commits: as the Notes of `department_service.spec.md` (the `db` fixture makes `db.commit()` a savepoint release; commit setup rows before an error path, since the rollback discards uncommitted ones).
- **BUG-035:** calling with `workspace_id=` raises `TypeError` today → strict xfail. Today's leak is shown by a status of workspace B read, changed and deleted with no workspace at all (verified) — a plain passing case each, marked as documenting BUG-035.
- **BUG-1681:** names `"zeta"`, `"Alpha"`, `"beta"` in that order; today's order rests on physical order → **non-strict** xfail. The `id` tie-break is shown on the statement only (BUG-1221 forbids equal names), as for app settings.
- **BUG-1220:** build a status `Receiving` (a stage name) and one whose id is in a committed `OrderWorkflow.status_sequence`; strict xfail. **BUG-1218:** a status used by a `TransferOrder` (status DAO spec Notes); strict xfail.
- **BUG-1221:** a rename onto another status's name raises `IntegrityError` 23505 after the rollback once the index exists; strict xfail.
- **BUG-1218 blockers (G1):** purchase orders normally sit on a stage status, which BUG-1220 refuses first; to reach R4 with a purchase order, point it at a status that is neither a stage name nor in any `status_sequence`. Builders (required columns without a default): `PurchaseOrder(workspace_id, po_number, destination_type, destination_id, current_status_id, created_by)`; `SalesOrder(workspace_id, sales_order_number, account_id, factory_id, current_status_id, created_by)` (`sales_order_number` unique across all workspaces; needs an `Account` and a `Factory`); `TransferOrder` as in the status DAO spec Notes. The other-workspace blocker: an order of workspace B whose `current_status_id` is workspace A's status (invalid data, built directly).
- **Rollback of the refusals (G3):** add an uncommitted extra row (`db.add` + `flush`) before the refused call; after it the extra row is gone (S2a).

## Not specified
- `StatusService` has no `__init__`. `status_service` — module-level singleton, no logic.

---

### Transaction rules of this service
- **S1.** A write that succeeds is committed (TC1). `create_status` and `update_status` return the row re-read after the commit (TC2); if the re-read raises, the change stays saved (TC5). `delete_status` re-reads nothing.
- **S2.** Any exception inside a write (database error at the flush or the commit, anything) rolls the session back and reaches the caller unchanged; nothing saved, and other uncommitted changes of the session are discarded too (TC3, TC4).
- **S2a.** (G3) The BUG-1220 and BUG-1218 refusals follow S2: the session is rolled back **before** the refusal is raised, so nothing the call did is saved and other uncommitted changes in the session are discarded too (precedent: refusals roll back before raising — department spec TC3 / TC4, `item_service.spec.md` R2, R4, `factory_service.spec.md` R2; decided by Claude under the reviewer's delegation (2026-11-04)). This differs on purpose from the tag services' S3, whose refusals stand before the `try` in today's code.
- **S3.** A "not found" answer (`None`, `False`) neither commits nor rolls back.
- **S4.** The reads neither commit nor roll back (TC6).

---

## `StatusService.get_statuses(db, skip=0, limit=100)` → [BUG-035] `get_statuses(db, workspace_id, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /statuses/`, always with `skip`, `limit`; read by the order pages)

**Rules:**
- **R1.** [BUG-035] (HR-16) Only the caller's workspace's statuses are listed; another workspace's never appear. *(Today: no workspace parameter; every workspace's statuses are listed, a page of the whole table.)*
- **R2.** At most `limit` after skipping `skip` (base `get_multi`); `limit=0` gives `[]`; a negative `skip` or `limit` raises `DataError`.
- **R3.** [BUG-1681] (HR-6) Ordered by name case-insensitive ascending, then `id` ascending, before `skip` / `limit`. *(Today: no order of its own.)*
- **R4.** Read only (S4).

**Errors:** `DataError` on negative paging. **Side effects:** none

---

## `StatusService.get_by_id(db, status_id)` → [BUG-035] `get_by_id(db, status_id, workspace_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `GET /statuses/{id}/`, 404 for `None`)

**Rules:**
- **R1.** The status with that id is returned.
- **R2.** Unknown id or `0` → `None`, no error.
- **R3.** [BUG-035] (HR-16) Another workspace's status → `None`, exactly as an unknown id. *(Today: returned. Verified.)*
- **R4.** Read only (S4).

**Errors:** none. **Side effects:** none

---

## `StatusService.create_status(db, status_in)` → [BUG-035] `create_status(db, status_in, workspace_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /statuses/`, 201; no screen calls it)

**Returns:** the new `Status`, committed and re-read (S1).

**Rules:**
- **R1.** [BUG-035] One row is stored with `workspace_id` = the caller's workspace and `name`, `comment` as given (after R4); committed (S1); returned re-read with its `id`. *(Today: `StatusCreate` has no `workspace_id`, so every create raises `IntegrityError` 23502 on `workspace_id` after the rollback, nothing saved — 400 "Required field is missing." at the API. Verified.)*
- **R2.** No acting user is recorded: the table has no such column.
- **R3.** `comment` is required by the schema; an empty string `""` is stored.
- **R4.** [BUG-1680] (HR-1) `name` is stored trimmed; a blank or whitespace-only name is refused by `StatusCreate` (`pydantic.ValidationError`; 422 at the API), nothing written.
- **R5.** [BUG-1221] (owner O3, HR-2) A name already used by a status of the workspace, compared case-insensitively after trimming, is refused: `IntegrityError` 23505 reaches the caller after the rollback, nothing saved (409 at the API). The same name in another workspace is stored. *(Today: no index; stored.)*
- **R6.** Any other error follows S2.

**Errors:** `pydantic.ValidationError` (schema, BUG-1680); `IntegrityError` (today 23502 always; BUG-1221 23505); database errors unchanged.

**Side effects:** one `statuses` row, committed; on error, rolled back.

---

## `StatusService.update_status(db, status_id, status_in)` → [BUG-035] `update_status(db, status_id, status_in, workspace_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /statuses/{id}/`, 404 for `None`; no screen calls it)

**Returns:** the `Status`, committed and re-read; or `None`.

**Rules:**
- **R1.** Unknown id or `0` → `None`; nothing written, no commit (S3).
- **R2.** [BUG-035] (HR-16) Another workspace's status → `None`, exactly as R1; the row stays unchanged. *(Today: changed and committed.)*
- **R3.** A found status gets each field sent with a value (`name`, `comment`); a field omitted or sent as `null` stays unchanged (verified). Committed (S1), returned re-read.
- **R4.** [BUG-1220] (owner O1) A status whose name is one of the purchase order stages (`Draft`, `Planning`, `Receiving`, `Complete`) or whose id is in a `status_sequence` of an order workflow of its workspace refuses a **name change**: `HTTPException` 400 whose detail names the workflow (R4a), nothing written, rolled back (S2a). Sending its current name, or changing only `comment`, is allowed. A stage name matches **exactly** (R4b). *(Today: renamed. Verified at the DAO / manager.)*
- **R4a.** [BUG-1220] (G2) The refusal's detail is exactly `Status '<name>' is used by order workflow <workflows> and cannot be renamed`, where `<name>` is the status's stored (current) name and `<workflows>` names each workflow of the status's workspace whose `status_sequence` holds its id, by its stored `name` in single quotes, ordered by workflow `id`, joined by `", "` (with `order workflows` instead of `order workflow` when more than one). A stage-named status in no sequence names the workspace's purchase workflow (`order_workflows.type = 'purchase'`) by its stored name; if the workspace has no purchase workflow row it names `'Purchase Order'`, the name the seed gives that workflow (`app/db/seed_po_workflow.py`). A stage-named status that is also in the purchase sequence names that workflow once. Example: `Status 'Receiving' is used by order workflow 'Purchase Order' and cannot be renamed`. Another workspace's workflow is never named (HR-16). (Decided by Claude under the reviewer's delegation (2026-11-04).)
- **R4b.** [BUG-1220] [BUG-1880] (G4; OQ-13) "One of the purchase order stages" means the stored name equals `Draft`, `Planning`, `Receiving` or `Complete` **ignoring capitals and leading / trailing spaces** (the comparison of BUG-1221: lower-cased after trimming). `"receiving"`, `" Complete"`, `"DRAFT "` are stage statuses and are protected like the exact spellings; `"Receiving Bay"`, `"Completed"`, `"Re ceiving"` are not, and are protected only if their id is in a sequence. *(Today: no protection at all (BUG-1220); before OQ-13 this spec matched exactly. Answered by the owner (2026-11-04), OQ-13.)* The order code is to find stage rows the same way (BUG-1881) and a migration renames such rows to the exact stage name (BUG-1882); neither is a rule of this service.
- **R5.** No audit column exists; nothing else is written.
- **R6.** [BUG-1680] (HR-1) A new name is stored trimmed; blank is refused by `StatusUpdate` (`pydantic.ValidationError`), nothing written. *(Today: `"   "` stored. Verified.)*
- **R7.** [BUG-1221] (owner O3) A rename onto another status's name of the workspace (case-insensitive, trimmed) → `IntegrityError` 23505 after the rollback, nothing saved (409 at the API). *(Today: stored.)*
- **R8.** Any other error follows S2.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| [BUG-1220] rename of a stage / sequence status | `HTTPException` 400 | `Status '<name>' is used by order workflow '<workflow>' and cannot be renamed` (R4a) |
| [BUG-1221] name taken | `IntegrityError` 23505 | — |
| [BUG-1680] blank name | `pydantic.ValidationError` (schema) | — |

**Side effects:** the changed fields, committed; on error, rolled back.

---

## `StatusService.delete_status(db, status_id)` → [BUG-035] `delete_status(db, status_id, workspace_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /statuses/{id}/`, 204; 404 for `False`; no screen calls it)

**Returns:** `True` when deleted, `False` when not found.

**Rules:**
- **R1.** Unknown id or `0` → `False`; nothing written, no commit (S3).
- **R2.** [BUG-035] (HR-16) Another workspace's status → `False`; the row stays. *(Today: deleted, `True`. Verified.)*
- **R3.** [BUG-1220] (owner O1) A purchase order stage status, or one in a `status_sequence` of its workspace, is refused: `HTTPException` 400, detail exactly `Status '<name>' is used by order workflow <workflows> and cannot be deleted`, `<name>` and `<workflows>` as `update_status` R4a; stage names match as `update_status` R4b; nothing deleted, rolled back (S2a). Checked before R4, used or not. *(Today: deleted when no order uses it, leaving its id in the sequence.)*
- **R4.** [BUG-1218] (owner's refusal rule, BUG-948) A status that orders use (`purchase_orders`, `sales_orders`, `transfer_orders` with that `current_status_id`) is refused, nothing deleted, rolled back first (S2a). Shape (G1; BUG-948 format, as `item_service.spec.md` R4 for the service layer; decided by Claude under the reviewer's delegation (2026-11-04)):
  - raises `app.core.exceptions.ValidationError` (an `APIException`, **not** `fastapi.HTTPException`): `.status_code == 400`, `.detail == "Status is used by orders"`, `.errors` == the blocker list; 400 at the API with the list in the RFC 7807 `errors` member;
  - one blocker per order whose `current_status_id` is this status, whatever the order's state (voided, completed, delivered: none of these tables has a soft delete, and every such row keeps the database from deleting the status): `{"type": "purchase_order", "id": <purchase_orders.id>}`, `{"type": "sales_order", "id": <sales_orders.id>}`, `{"type": "transfer_order", "id": <transfer_orders.id>}`;
  - sorted by type in that order (purchase, sales, transfer), then `id` ascending;
  - then, if any order of another workspace uses the status, exactly one `{"type": "other_workspace"}` with no `id`, last, once however many such orders (HR-16, BUG-968 precedent); such an order is never listed with its id or type. *(Today: `IntegrityError` 23502 after the rollback, nothing deleted; 400 "Required field is missing." at the API.)*
- **R5.** A status nothing uses and nothing protects is hard-deleted: the row is gone, committed (S1); `True`.
- **R6.** Any other error follows S2.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| [BUG-1220] stage / sequence status | `HTTPException` 400 | `Status '<name>' is used by order workflow '<workflow>' and cannot be deleted` (R3, `update_status` R4a) |
| [BUG-1218] in use | `app.core.exceptions.ValidationError` (400) | `.detail` `Status is used by orders`; `.errors` = blockers (R4) |

**Side effects:** one row deleted, committed; on error, rolled back.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 13 | list: base `get_multi`, no workspace (BUG-035), no order (BUG-1681) | `get_statuses` R1–R4 |
| 17 | base `get` by id, no workspace (BUG-035) | `get_by_id` R1–R4 |
| 21–25 | create: DAO create (no `workspace_id`, BUG-035), commit, refresh, return | `create_status` R1–R5; S1 |
| 26–28 | create: any exception → rollback, re-raise | `create_status` R1, R5, R6; S2 |
| 33–35 | update: `if not status` → `None` | `update_status` R1, R2; S3 |
| 36–39 | update: DAO update (only fields with a value), commit, refresh; no protection (BUG-1220) | `update_status` R3–R7 |
| 40–42 | update: any exception → rollback, re-raise | `update_status` R7, R8; S2 |
| 47–49 | delete: `if not status` → `False` | `delete_status` R1, R2; S3 |
| 50–52 | delete: DAO remove (in use → 23502, BUG-1218; no protection, BUG-1220), commit, `True` | `delete_status` R3–R5 |
| 53–55 | delete: any exception → rollback, re-raise | `delete_status` R4, R6; S2 |
| 58 | module singleton | Not specified |

## Gap log
G1 (status_service.cases.md gap 1) — Intent, decided by precedent — `delete_status` R4 now gives the BUG-1218 refusal's shape: `app.core.exceptions.ValidationError`, 400, `detail` `Status is used by orders`, `errors` = `purchase_order` / `sales_order` / `transfer_order` blockers with `id`, by type then id, any order state, then one `{"type": "other_workspace"}` last (refusals list their blockers: BUG-948, BUG-968, `item_service` R4; decided by Claude under the reviewer's delegation (2026-11-04)). Errors table updated; order builders added to Notes.
G2 (gap 2) — Intent, decided — exact BUG-1220 detail text and the workflow it names: new rule `update_status` R4a, used by `delete_status` R3; a stage status with no workflow row names `'Purchase Order'` (decided by Claude under the reviewer's delegation (2026-11-04)). Errors tables updated.
G3 (gap 3) — Intent, decided by precedent — new S2a: both refusals roll the session back before raising (department TC3 / TC4, `item_service` R2 / R4, `factory_service` R2; decided by Claude under the reviewer's delegation (2026-11-04)). Note added.
G4 (gap 4) — Fact — new rule `update_status` R4b: stage names match exactly (case-sensitive, untrimmed), as the order code looks them up. The owner-level consequence with BUG-1221 parked as OQ-13 (not blocking). O2 stays boxed; no rule rests on it.
OQ-13 (apply-review 2026-11-04, not a gap) — owner's answer applied: `update_status` R4b now matches stage names ignoring capitals and outer spaces → BUG-1880; order-code lookup BUG-1881 and rename migration BUG-1882 logged against `app/managers/purchase_order_manager.py` and siblings.
