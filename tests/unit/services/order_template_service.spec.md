# Spec — `app/services/order_template_service.py`

> **Status:** APPROVED (2026-11-06; revised 2026-11-07: cases gaps 1–2 closed; manager's OQ-22 answered → BUG-2347)
> **Source commit:** e48a092

> **Revision 2026-11-09 (verifier finding; decided by Claude under the reviewer's delegation (2026-11-09)).** `list_templates` R1a states the service's own defaults (`skip=0`, `limit=100`, `is_active=None`, `expense_category=None`), as other service specs do. No other rule changed. Stays APPROVED.

> **Revision 2026-11-07 (fill-gaps, `order_template_service.cases.md` gaps 1–2; verified with `v3_overflow.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tpl\B\`, rolled back).** `create_template` R3a: the lines are committed with the template when the re-read fails. Facts: the line model's module. The manager's OQ-22 is answered (BUG-2347, a 403 that passes through like the other refusals, R2a). Stays APPROVED.

> **Form.** As `tests/unit/services/work_order_type_service.spec.md`: this spec covers what the service adds. The **Transaction contract TC1–TC6 is defined in `tests/unit/services/base_service.spec.md`** and cited here. Below the service: `tests/unit/managers/order_template_manager.spec.md` (APPROVED; OQ-22 answered 2026-11-07 → BUG-2347) and `tests/unit/dao/order_template.spec.md`. The manager's refusals and bugs are named here only as values that must pass through unchanged.
>
> **Verified by running** (`v2.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tpl\B\`, one outer transaction rolled back against `marker_test`, session as the `db` fixture, private `COVERAGE_FILE`; nothing persisted): create committed and re-read (`created_at` loaded); `remove_item` committed, the returned line detached but readable; a 256-character name (`DataError`) rolling back a pending workspace too; `update_template` of an unknown id (404); `delete_template` committed and returning `None`; `add_item`, `update_item` on an inactive template. **Not run:** HTTP; TC4 / TC5 patching (same code as the base service's verified helpers).

## Review
> No questions.

Checked and **not** violated: **HR-1 … HR-16** — the service adds no check, list, money or link of its own; the manager's bugs (BUG-1014, BUG-1216, BUG-1226, BUG-2355 … BUG-2366) and BUG-2347 (OQ-22, owner 2026-11-07), BUG-2349 are its spec's. **HR-7** — `GET /order-templates/` enforces `1 <= limit <= 1000`, `skip >= 0`.

**Permission checks:** none in the service; the manager reads the caller's role for the approval flags (BUG-2347, manager spec Q1) from the `user_id` the service already passes.

## Overview
`OrderTemplateService` is the transaction boundary for expense order templates. The `/order-templates/` endpoints call it; it calls `OrderTemplateManager` and commits, rolls back and re-reads around it. It adds no check, translation or shaping.

**Callables:** 9 specified · 2 not specified
**Externals to mock:** none
**Integration-only behavior:** the endpoint's `is_active` default `True` and the 204 responses of the two deletes.

**Facts for the test designer**
- Import: `from app.services.order_template_service import OrderTemplateService, order_template_service`; `OrderTemplateService()` takes no arguments and is a `BaseService`; the manager is the attribute `manager` (the singleton). Parameters are positional-or-keyword, in source order.
- Schemas: `app.schemas.order_template` (manager spec, Facts).
- Models (gap 2): `OrderTemplate` in `app.models.order_template`, `OrderTemplateItem` in `app.models.order_template_item` (confirmed in the code).

**Notes for the test designer**
- Session, commits, TC4 / TC5 patching: `base_service.spec.md` Notes. TC1 and TC3 get one case per write method; TC2, TC4, TC5 one case each on `create_template` (the five refreshing writes are the same code).
- Pass-through of a manager bug: one case (BUG-1226 through `update_item`) is enough; strict xfail.

## Not specified
- `OrderTemplateService.__init__` — stores the manager.
- `order_template_service` — module-level singleton.

---

## `OrderTemplateService.create_template(db, tpl_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /order-templates/`, 201)

**Rules:**
- **R1.** The manager's `create_template` result (template and lines) is committed (TC1) and returned re-read (TC2).
- **R2.** Any manager or database error (404, 400, `IntegrityError`, `DataError`) reaches the caller unchanged after a rollback; nothing saved, other pending changes discarded (TC3; verified with `DataError`).
- **R2a.** The manager's 403 for a non-owner skipping approval (BUG-2347) passes through unchanged like R2's refusals; nothing saved.
- **R3.** Commit and re-read failures follow TC4, TC5.
- **R3a.** When the re-read fails (TC5), the lines created with the template are committed too: after a test-level `db.rollback()` a fresh select finds them with their `line_number` and `line_subtotal` (verified: one line 2 × 3 → `6.00`). Nothing is returned (the exception reaches the caller), so the case checks the database, not a returned object. (Gap 1.)

---

## `OrderTemplateService.update_template(db, tpl_id, tpl_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PUT /order-templates/{id}/`)

**Rules:**
- **R1.** The manager's change is committed (TC1) and the template returned re-read (TC2).
- **R2.** The manager's 404 `Order template with ID <tpl_id> not found` (and its later refusals) reach the caller unchanged; nothing saved (TC3).
- **R3.** TC4, TC5.

---

## `OrderTemplateService.get_template(db, tpl_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (`GET /order-templates/{id}/`)

**Rules:**
- **R1.** Returns the manager's `get_template` (inactive templates included); its 404 unchanged.
- **R2.** Read only (TC6).

---

## `OrderTemplateService.list_templates(db, workspace_id, is_active=None, expense_category=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /order-templates/`, which passes `is_active` default `True`)

**Rules:**
- **R1.** Returns the manager's list for the same five arguments, unchanged; the service default `is_active=None` lists both states.
- **R1a.** Defaults when a direct caller leaves them out: `skip=0`, `limit=100`, `is_active=None`, `expense_category=None`. With 101 templates and no `limit`, 100 are returned (the DAO's cap per call, order template DAO R7).
- **R2.** Read only (TC6).

---

## `OrderTemplateService.delete_template(db, tpl_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`DELETE /order-templates/{id}/`, 204)

**Returns:** `None` (no re-read).

**Rules:**
- **R1.** The manager's deactivation is committed (TC1); an already inactive template commits nothing new and raises nothing.
- **R2.** The manager's 404 passes unchanged after a rollback (TC3).
- **R3.** A failing commit follows TC4; there is no re-read, so TC5 does not apply.

---

## `OrderTemplateService.add_item(db, tpl_id, item_in, workspace_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /order-templates/{id}/items/`, 201)

**Rules:**
- **R1.** The new line is committed (TC1) and returned re-read (TC2).
- **R2.** The manager's 404 `Order template not found` passes unchanged; nothing saved (TC3).
- **R3.** TC4, TC5.

---

## `OrderTemplateService.update_item(db, item_id, item_in, workspace_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PUT /order-templates/items/{item_id}/`)

**Rules:**
- **R1.** The changed line is committed (TC1) and returned re-read (TC2), with the manager's `line_subtotal`.
- **R2.** The manager's 404 `Template item not found` passes unchanged (TC3).
- **R3.** [BUG-1226] (pass-through) `unit_price: 0` on a 2 × 10.00 line returns subtotal 0.00. *(Today: 20.00.)*
- **R4.** TC4, TC5.

---

## `OrderTemplateService.remove_item(db, item_id, workspace_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (`DELETE /order-templates/items/{item_id}/`, 204)

**Returns:** the removed line, not re-read: detached after the commit, its attributes still readable (verified).

**Rules:**
- **R1.** The delete is committed (TC1): a later rollback does not bring the line back.
- **R2.** The manager's 404 `Template item not found` passes unchanged (TC3).
- **R3.** A failing commit follows TC4; no re-read, so TC5 does not apply.

---

## `OrderTemplateService.get_items(db, tpl_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /order-templates/{id}/items/`)

**Rules:**
- **R1.** Returns the manager's `get_items` unchanged (BUG-2366's 404 included, once fixed).
- **R2.** Read only (TC6).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 28–32 | create: manager → commit → refresh → return | `create_template` R1; TC1, TC2 |
| 33–35 | create: exception → rollback, re-raise | `create_template` R2, R3; TC3–TC5 |
| 41–45 / 46–48 | update: success / exception | `update_template` R1 / R2, R3 |
| 51 | get, positional | `get_template` R1, R2 |
| 59–63 | list pass-through | `list_templates` R1, R2 |
| 66–68 / 69–71 | delete: commit, no refresh / exception | `delete_template` R1 / R2, R3 |
| 78–82 / 83–85 | add_item: success / exception | `add_item` R1 / R2, R3 |
| 91–95 / 96–98 | update_item: success / exception | `update_item` R1, R3 / R2, R4 |
| 101–104 / 105–107 | remove_item: commit, no refresh / exception | `remove_item` R1 / R2, R3 |
| 110 | get_items, positional | `get_items` R1, R2 |
| `base_service.py` | commit / commit fails / rollback | TC1, TC3, TC4 |
| 113 | singleton | Not specified |

## Gap log
G1 (`order_template_service.cases.md` gap 1) — Fact, verified — `create_template` R3a: lines committed with the template when the re-read raises; check by re-select.
G2 (`order_template_service.cases.md` gap 2) — Fact — Facts: `OrderTemplateItem` lives in `app.models.order_template_item`.
V1 (`order_template_service.verify.md`, 2026-11-09) — Fact — `list_templates` R1a: the default `limit=100` (and the other defaults) written as a rule.
