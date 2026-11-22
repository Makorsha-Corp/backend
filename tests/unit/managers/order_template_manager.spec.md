# Spec — `app/managers/order_template_manager.py`

> **Status:** APPROVED (2026-11-06; revised 2026-11-07: OQ-22 answered → BUG-2347; cases gaps 1–9 closed, BUG-2349)
> **Source commit:** e48a092

> **Revision 2026-11-07.** Apply-review: OQ-22 answered by the owner (bug, as suggested) → 🐞 BUG-2347; `create_template` R9 and `update_template` R9 rewritten to the intended behaviour, with the caller's role read by the manager itself (as attachment manager spec PR-5). Fill-gaps (`order_template_manager.cases.md` gaps 1–9), decided by Claude under the reviewer's delegation (2026-11-07) where not a fact: Facts give field types, the soft-delete columns and the minimal expense order row; R3 / update R4 name `recurrence_type`'s limit; new 🐞 BUG-2349 (a line total that overflows `Numeric(15, 2)` is refused with 422, `create_template` R8a, `update_item` R4a); `update_template` R5 / R8: a `null` `cost_center_id` on a factory / department template gets BUG-2361's 400; R8a: the merged cost centre must be of the merged category's kind; R11: order of checks. Verified on `marker_test` (`v3_overflow.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tpl\B\`, rolled back): a product of 10^13 or more raises `DataError` 22003 at flush. Stays APPROVED.

> **Form.** Below this manager: `tests/unit/dao/order_template.spec.md` (APPROVED; its rules are not restated) and `tests/unit/dao/base.spec.md` (`create`, `update`). Above it: `tests/unit/services/order_template_service.spec.md`. The one consumer outside the service is `ExpenseOrderManager.create_expense_order_from_template` (`tests/unit/managers/expense_order_manager.spec.md`, R1–R9 of that method): it reads `get_template` and `get_items` and copies the template into a real expense order.
>
> **Order template DAO FU-1 settled here:** (a) BUG-1014, BUG-1216 → `create_template` R6, R7, `update_template` R7; (b) `expense_category` → BUG-2359; (c) HR-9 → BUG-2356; (d) BUG-1226 → `update_item` R5; (e) HR-1 → BUG-2355.
>
> **Decisions:** every question below except Q1 decided by Claude under the reviewer's delegation (2026-11-06). Q1 is an OWNER question, parked as **OQ-22** in `docs/testing/owner-questions.md`; its rule is written to today's behaviour in its own rule, so it does not block.
>
> **Verified by running** (`v1.py`, `v2.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tpl\B\`, one outer transaction rolled back against `marker_test`, private `COVERAGE_FILE`; nothing persisted): a template named `"  "` with category `"garbage"` and four lines (1.5 × 0.25 → subtotal 0.38; 1.005 × 10 → quantity stored 1.01, subtotal 10.05; no price → 0.00; −2 × −3 → 6.00); an empty update stamping `updated_by`; `description: null` and `template_name: null` ignored; another workspace's template (404 on get / add_item / delete, `[]` on get_items); `get_items` of an unknown id (`[]`); line numbers after removing the last and the first line; `update_item` with quantity only, price 0 (BUG-1226), price `null`, description only, and 3 × 0.125 (price stored 0.13, subtotal 0.38); a second delete keeping the first `updated_by`; an unknown `cost_center_id` and a non-member approver stored; a 256-character name (`DataError`). **Not run:** HTTP; concurrency; the intended behaviour of any bug.

## Review

### House-rule violations — applied automatically

- **HR-1** `create_template` R3, `update_template` R4 — `template_name` is stored as typed: `"  "` was accepted (verified), and `"  Rent "` keeps its spaces. Intended: `OrderTemplateCreate` / `OrderTemplateUpdate` trim it and refuse blank or whitespace-only with 422.
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-2355 (pattern `blank-name-accepted`). Rules: `create_template` R3, `update_template` R4.
- **HR-9** `update_template` R6 — `updated_by` is written on every call, an empty payload included (verified). Intended: only when at least one field actually changes value.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-2356 (pattern `audit-stamp-on-noop`). Rules: `update_template` R6.

Logged earlier and carried here as tagged rules: **BUG-1014** (another workspace's account), **BUG-1216** (another workspace's department, unknown cost centre, non-member approver), **BUG-1226** (price 0 leaves the old subtotal).

Checked and **not** violated: **HR-2** — template names need not be unique (nothing says so; two "Office rent" templates are allowed). **HR-3** — line `unit` is display text, never grouped or filtered; `expense_category` is a code (Q3). **HR-4** — no soft-delete column; `is_active` is an on/off switch (order template DAO Q1, intended). **HR-5, HR-6, HR-7, HR-8** — the list is the DAO's (BUG-1210) and the endpoint's (`1 <= limit <= 1000`). **HR-10** — a template moves no money and no stock; concurrent `add_item` can repeat a line number, which BUG-1211's `id` tie-break already orders. **HR-15** — no rounding in Python; the subtotal is the exact product and the `Numeric(15, 2)` column rounds half away from zero (1.50 × 0.25 = 0.375 → 0.38, verified). **HR-16** — rows are found by the caller's workspace; links are BUG-1014, BUG-1216.

**Permission checks:** none; any active member may create, change and delete templates and their lines (Q1, `docs/future/permissions.md`).

### Precedent matches — decided under the delegation (2026-11-06)

### Q2. `null` cannot clear a template field or a line field — 🐞 BUG-2357, BUG-2358
**Background:** Both updates use `exclude_unset=True, exclude_none=True`, so an explicit `null` counts as "not sent".
**What happens today, verified:** a template with description "d" sent `{"description": null}` keeps "d" (200). `{"template_name": null}` is ignored too. A line sent `{"unit_price": null}` keeps its price.
**Example:** a manager empties a template's default approver and saves; the approver stays and every new expense order still gets them.
**Rules affected:** `update_template` R5, `update_item` R3
**Answer:** bug — per BUG-753 precedent: an explicit `null` clears nullable fields; `null` for a required field is refused with 422 (precedent — decided by Claude under the reviewer's delegation (2026-11-06))
**Resolution:** 🐞 BUG-2357 (template; pattern `exclude-none-blocks-clear`), 🐞 BUG-2358 (line; same pattern). Template: `null` clears `description`, `account_id`, `expense_category`, `cost_center_id`, `recurrence_type`, `recurrence_interval`, `recurrence_day`, `start_date`, `end_date`, `next_generation_date`, `default_approver_id`, `notes`; `null` for `template_name`, `is_recurring`, `is_active`, `auto_approve`, `requires_approval` → 422. Line: `null` clears `description`, `unit`, `unit_price`, `notes` (a cleared price gives subtotal 0, R4); `quantity: null` → 422. Rules: `update_template` R5, `update_item` R3.

### Q3. `expense_category` takes any text — 🐞 BUG-2359
**Background:** An expense order's category must be `factory`, `department` or `other` (`ExpenseOrderManager._validate_order_allocation`, 400 `Invalid category: <x>. Must be factory, department, or other.`). The template stores whatever is sent; `None` becomes `other` when an order is made.
**What happens today, verified:** `"garbage"` is stored. Making an expense order from it then fails with that 400.
**Example:** a template saved with `"Factory "` looks fine, and every "Create from template" on it fails.
**Rules affected:** `create_template` R4, `update_template` R8
**Answer:** bug — per BUG-360 precedent: the schemas trim and lower-case `expense_category` and accept only `factory`, `department`, `other` (422 otherwise); `None` stays allowed (decided by Claude under the reviewer's delegation (2026-11-06))
**Resolution:** 🐞 BUG-2359 (pattern `unvalidated-code-input`). Rules: `create_template` R4, `update_template` R8.

### Q4. Category `other` keeps a cost centre — 🐞 BUG-2360
**Background:** BUG-752 (owner-confirmed precedent) stores `cost_center_id = null` on an expense order whose category is `other`, including one made from a template.
**What happens today:** a template with category `other` (or none) and `cost_center_id` 7 stores 7; `update_template` changing the category to `other` keeps it.
**Example:** a template moved from "Factory 7" to "Other" still shows factory 7's id.
**Rules affected:** `create_template` R5, `update_template` R8
**Answer:** bug — per BUG-752 precedent: when the resulting category is `other` or `None`, `cost_center_id` is stored `null` (create; update on the merged state) (decided by Claude under the reviewer's delegation (2026-11-06))
**Resolution:** 🐞 BUG-2360 (pattern `stale-cross-field-value`). Rules: `create_template` R5, `update_template` R8.

### Q5. A factory or department template without a cost centre cannot make an order — 🐞 BUG-2361
**Background:** An expense order of category `factory` or `department` needs a cost centre (400 `Select a factory for this expense order`). "Create from template" has no field to supply one.
**What happens today:** such a template is stored; every order made from it fails with that 400.
**Example:** "Monthly power — Factory" saved without choosing the factory; the button that uses it never works.
**Rules affected:** `create_template` R5, `update_template` R8
**Answer:** bug — the template is checked as the order would be: category `factory` or `department` (merged state on update) needs a `cost_center_id`, else 400 `Select a <category> for this template`, nothing written (decided by Claude under the reviewer's delegation (2026-11-06); pattern of BUG-361)
**Resolution:** 🐞 BUG-2361 (pattern `missing-conditional-required-field`). Rules: `create_template` R5, `update_template` R8.

### Q6. A deleted account, factory or department can be put on a template — 🐞 BUG-2362
**Background:** Accounts, factories and departments are soft-deleted. The expense order refuses a deleted cost centre (BUG-340, owner-confirmed) and a deleted account (expense order manager Q, "live account"). BUG-1014 / BUG-1216 cover other workspaces only.
**What happens today:** a deleted account or cost centre of the workspace is stored on the template, and each order made from it then fails.
**Example:** department 4 was deleted last month; a template still lists it and "Create from template" answers 404 `Selected department not found`.
**Rules affected:** `create_template` R6, `update_template` R7
**Answer:** bug — per BUG-340 / BUG-1228 precedent: a soft-deleted account, factory or department is treated as not found, with BUG-1014 / BUG-1216's 404, nothing written; a template already holding one keeps it when an update does not send that field (decided by Claude under the reviewer's delegation (2026-11-06))
**Resolution:** 🐞 BUG-2362 (pattern `reference-to-soft-deleted-row-accepted`). Rules: `create_template` R6, `update_template` R7.

### Q7. Line quantity and price accept more than 2 decimals — 🐞 BUG-2363
**Background:** `quantity`, `unit_price`, `line_subtotal` are `Numeric(15, 2)`. The subtotal is computed from the values as sent, then each is rounded by the database.
**What happens today, verified:** 3 × 0.125 stores price 0.13 and subtotal 0.38 (3 × 0.13 = 0.39); 1.005 × 10 stores quantity 1.01 and subtotal 10.05. 14 integer digits fail at flush.
**Example:** the line reads "3 × 0.13 = 0.38".
**Rules affected:** `create_template` R8, `add_item` R4, `update_item` R4
**Answer:** bug — per BUG-021 precedent (applied to expense order lines, expense order manager Q2): `OrderTemplateItemCreate` / `Update` refuse `quantity` / `unit_price` with more than 2 decimals or more than 13 integer digits (422) (precedent — decided by Claude under the reviewer's delegation (2026-11-06))
**Resolution:** 🐞 BUG-2363 (pattern `unbounded-decimal-input`). Rules: `create_template` R8, `add_item` R4, `update_item` R4.

### Q8. Line quantity can be 0 or negative, price negative — 🐞 BUG-2364
**Background:** The expense order's lines must have `quantity > 0` and `unit_price >= 0` (BUG-362 precedent, expense order manager Q3). The order made from a template builds its lines through `ExpenseOrderItemCreate`, so a bad template line will make "Create from template" fail.
**What happens today, verified:** −2 × −3 is stored with subtotal 6.00.
**Example:** a "Refund" line of −500 on a template.
**Rules affected:** `create_template` R8, `add_item` R4, `update_item` R4
**Answer:** bug — per BUG-362 precedent: the line schemas require `quantity > 0` and `unit_price >= 0` (422), nothing written (precedent — decided by Claude under the reviewer's delegation (2026-11-06))
**Resolution:** 🐞 BUG-2364 (pattern `unvalidated-numeric-range`). Rules: `create_template` R8, `add_item` R4, `update_item` R4.

### Q9. Over-long text fails with a database error — 🐞 BUG-2365
**Background:** `template_name` is `String(255)`, line `unit` `String(50)`, `recurrence_type` `String(50)`; the schemas have no length limits.
**What happens today, verified:** a 256-character name raises `DataError` at flush (500 over HTTP).
**Rules affected:** `create_template` R3, `update_template` R4, `add_item` R4
**Answer:** bug — per BUG-144 precedent (`unchecked-column-length`): the schemas refuse longer values with 422 (decided by Claude under the reviewer's delegation (2026-11-06))
**Resolution:** 🐞 BUG-2365 (pattern `unchecked-column-length`). Rules: `create_template` R3, `update_template` R4, `add_item` R4.

### New questions

### Q1. Any member can make a template that creates expense orders already approved — 🐞 BUG-2347 (owner, OQ-22)
**Background:** A template has `requires_approval` (default true) and `auto_approve` (default false). An expense order made from a template with `requires_approval = false`, or with `auto_approve = true`, gets `required_approvals = 0` (expense order manager, `create_expense_order_from_template` R5, R6), so it counts as approved at once and can move on to its draft invoice. Templates have no role check: any active member may create one or switch these flags.
**What happens today:** both flags are stored as sent, by anyone.
**Example:** a `ground-team` member creates "Misc supplies" with `requires_approval: false`, then makes a 50,000 expense order from it; no approver ever sees it.
**Rules affected:** `create_template` R9, `update_template` R9
**Suggested answer:** bug — only the workspace owner may create a template with `requires_approval = false` or `auto_approve = true`, or switch either flag on an existing template (403 `Only the workspace owner can skip approval on a template`, nothing written); other fields stay open to every member. Alternatives: (a) intended — templates are trusted; (b) keep the flags but make the expense order honour them only when the person creating the order is the owner.
**Answer:** owner, 2026-11-07: suggested answer (only the workspace owner may set or switch approval-off / auto-approve on expense templates; 403 otherwise).
**Resolution:** 🐞 BUG-2347 (pattern `missing-role-check-on-write`). **How the caller reaches the manager** (decided by Claude under the reviewer's delegation (2026-11-07), following attachment manager spec PR-5): no new parameter. `create_template` and `update_template` already receive the caller as `user_id` (the service passes the endpoint's `current_user.id`); the manager reads the caller's role itself from that id and `workspace_id`: the caller **is the owner** when `workspaces.owner_user_id == user_id`, or their `workspace_members` row in that workspace has `status = 'active'` and `role = 'owner'`. Any other caller (another role, a suspended owner row, no row) is not. Rules: `create_template` R9, `update_template` R9.

### Q10. Lines of a missing template answer an empty list — 🐞 BUG-2366
**Background:** `get_template` answers 404 for an unknown id or another workspace's id.
**What happens today, verified:** `get_items` (`GET /order-templates/{id}/items/`) answers `[]` for both.
**Example:** a typo in the id shows "no lines" instead of "not found".
**Rules affected:** `get_items` R2
**Answer:** bug — 404 `Order template with ID <id> not found`, as `get_template`; another workspace's id gives the same 404 (HR-16: nothing disclosed) (decided by Claude under the reviewer's delegation (2026-11-06))
**Resolution:** 🐞 BUG-2366 (pattern `missing-parent-lists-empty`). Rules: `get_items` R2. `ExpenseOrderManager.create_expense_order_from_template` calls `get_template` first, so it is unaffected.

### Q11. Recurrence settings are stored and nothing uses them — ✅ intended
**Background:** `is_recurring`, `recurrence_type`, `recurrence_interval`, `recurrence_day`, `start_date`, `end_date`, `next_generation_date`, `generate_days_before` are accepted and returned. A search of `app/` finds no reader: nothing generates expense orders from templates on a schedule (unlike work order templates). `last_generated_date` is never written.
**What happens today:** any values are stored as sent, with no check (`end_date` before `start_date`, negative `generate_days_before`, any `recurrence_type` text).
**Answer:** intended for now — reserved fields, as `allowed_reverts_json` (order workflow DAO O3); nothing to test beyond storing them. When a generator is built, its spec validates them (decided by Claude under the reviewer's delegation (2026-11-06)).
**Resolution:** rules `create_template` R2, `update_template` R3 ✅.

## Overview
Business rules for expense order templates: a named preset (account, category, cost centre, approval settings, lines) from which a member makes an expense order in one click. Called by `OrderTemplateService` (which commits) behind `/order-templates/`, and by `ExpenseOrderManager.create_expense_order_from_template` (`get_template`, `get_items`). It protects workspace isolation and keeps each line's `line_subtotal = quantity × unit_price`. It never commits; the base DAO flushes (`create`, `update`), and `remove_item` flushes itself.

**Callables:** 9 specified · 2 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Facts for the test designer**
- Import `from app.managers.order_template_manager import order_template_manager, OrderTemplateManager`; schemas from `app.schemas.order_template`. Positional parameters are `session, …` in source order; the service passes them by keyword.
- `OrderTemplateCreate`: `template_name: str` (required), `description`, `account_id`, `expense_category`, `cost_center_id`, `recurrence_type`, `recurrence_interval`, `recurrence_day`, `start_date`, `end_date`, `default_approver_id`, `notes` (all optional, `None`), `is_recurring=False`, `generate_days_before=0`, `auto_approve=False`, `requires_approval=True`, `items: list[OrderTemplateItemCreate] | None`. No `next_generation_date`, no `is_active`.
- `OrderTemplateUpdate`: every field optional `None`; adds `next_generation_date`, `is_active`; no `items`, no `generate_days_before`.
- `OrderTemplateItemCreate`: `description`, `unit`, `unit_price`, `notes` (`None`), `quantity: Decimal = 1` (not nullable). `OrderTemplateItemUpdate`: all `None`.
- Field types (gap 1): `start_date`, `end_date`, `next_generation_date` are `date`; `recurrence_interval`, `recurrence_day`, `generate_days_before` are `int`; `recurrence_type` `str`; `unit_price`, `quantity` `Decimal`.
- Soft delete of references (gap 2): `accounts`, `factories`, `departments` each have `is_active`, `is_deleted` (Boolean NOT NULL) and `deleted_at`. "Deleted" for BUG-2362 means `is_deleted = True`; `is_active = False` alone is **not** deleted and is accepted (as BUG-1228's reading).
- Owner (BUG-2347): `workspaces.owner_user_id` (nullable FK to `profiles`), or a `WorkspaceMember(workspace_id, user_id, role='owner', status='active')`.
- Minimal expense order row (gap 3): `ExpenseOrder(workspace_id, expense_number, expense_category, created_by, order_template_id)`; every other NOT NULL column has a Python default (`expense_date`, `subtotal`, `total_amount`, `voided`, `created_at`).
- Tables and columns: order template DAO spec, Model facts. `created_at` is set by Python (`utcnow`), `updated_at` by `onupdate`.
- Rows for references: `make_workspace`, `make_profile` from `tests/unit/factories.py`; accounts, factories, departments, members built directly (`Account`, `Factory`, `Department`, `WorkspaceMember(status='active')`).

**Notes for the test designer**
- Bug rules are strict xfail, except the BUG-2355, BUG-2357 / 2358 (422 parts), BUG-2359, BUG-2363, BUG-2364, BUG-2365 checks that live in the schema: build the schema in the test (`pytest.raises(ValidationError)`), strict xfail today.
- BUG-2347 (R9): strict xfail for the non-owner refusals; the owner's own create / switch passes today and after the fix. Build the owner both ways (`owner_user_id`, and an active `owner` member row) and a suspended `owner` row as non-owner.
- HR-15's negative side (−0.125 → −0.13) has no input here once BUG-2364 refuses negative lines (gap 9): no card; the half-up rule is covered on positive values and in the order template DAO spec.

## Not specified
- `OrderTemplateManager.__init__` — stores the two DAOs, no logic.
- `order_template_manager` — module-level singleton.

## Follow-ups for other reviews
| # | Where | What | Came from |
|---|---|---|---|
| FU-1 | **Expense order manager** (`tests/unit/managers/expense_order_manager.spec.md`, `create_expense_order_from_template`) | Read, not run: the order copies `quantity`, `unit_price`, `description`, `unit`, `notes` of each line, not `line_subtotal`, and sorts by `line_number` alone (BUG-1211 applies there too). An inactive template answers 400 `Template is inactive`. Nothing to change there for this spec's bugs: BUG-2359 … BUG-2364 only make templates valid orders. | reading the consumer |

---

## `OrderTemplateManager.create_template(session, data, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `OrderTemplateService.create_template` ← `POST /order-templates/`)

**Purpose:** Create a template with its lines.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `data` | `OrderTemplateCreate` | see Facts; no cross-field check today |
| `workspace_id` | int | the template and every line get it |
| `user_id` | int | stored as `created_by` |

**Returns:** the new `OrderTemplate`, flushed, not committed.

**Rules:**
- **R1.** A template row is created with every schema field except `items`, `workspace_id` and `created_by = user_id`; `is_active = True`, `updated_by = None`, `updated_at = None`, `next_generation_date = None`, `last_generated_date = None`.
- **R2.** ✅ (Q11) The recurrence fields and `generate_days_before` are stored as sent, unchecked.
- **R3.** [BUG-2355] (HR-1) `template_name` is stored trimmed; blank or whitespace-only is refused with 422 by `OrderTemplateCreate`, nothing written. [BUG-2365] Over 255 characters is refused with 422; so is a `recurrence_type` over 50 characters (column `String(50)`; gap 4). *(Today: `"  "` stored as typed; 256 characters raise `DataError` at flush. Verified.)*
- **R4.** [BUG-2359] `expense_category` is stored trimmed and lower-cased and must be `factory`, `department` or `other`, else 422; `None` is allowed. *(Today: any text, `"garbage"` stored. Verified.)*
- **R5.** [BUG-2360] With category `other` or `None`, `cost_center_id` is stored `null`. [BUG-2361] With `factory` or `department` and no `cost_center_id`, 400 `Select a <category> for this template`, nothing written. *(Today: stored as sent in both cases.)*
- **R6.** [BUG-1014, BUG-1216, BUG-2362] (HR-16) `account_id` must be a live account of the workspace (404 `Account with ID <id> not found`); `cost_center_id` a live factory (category `factory`) or department (`department`) of the workspace (404 `Factory with ID <id> not found` / `Department with ID <id> not found`); `default_approver_id` an active member of the workspace (404 `Profile with ID <id> not found`). Nothing is written on refusal. *(Today: all stored unchecked; an unknown `cost_center_id` and a non-member approver verified. An unknown `account_id` fails at flush with `IntegrityError`.)*
- **R7.** `None` for any of the three references is accepted.
- **R8.** Lines are created in the given order with `line_number` 1, 2, 3 …, `workspace_id` and `order_template_id` set, and `line_subtotal = quantity × unit_price`, unit price `None` counting as 0 (subtotal `0.00`, price stays `null`). The product is not rounded in Python; the column rounds half away from zero (1.50 × 0.25 → 0.38, HR-15). [BUG-2363, BUG-2364] A line with more than 2 decimals or 13 integer digits in `quantity` / `unit_price`, `quantity <= 0`, or `unit_price < 0` is refused with 422 by the schema, nothing written. *(Today: stored; 1.005 × 10 → quantity 1.01, subtotal 10.05; −2 × −3 → 6.00. Verified.)* [BUG-2365] `unit` over 50 characters → 422.
- **R8a.** [BUG-2349] A line whose `quantity × unit_price`, rounded half up to 2 decimals, has more than 13 integer digits (10^13 or more in absolute value) is refused with 422 by `OrderTemplateItemCreate` (a model validator), nothing written, even when each input is within BUG-2363's bounds. *(Today: `DataError` 22003 `numeric field overflow` at flush, a 500. Verified with 10 000 × 1 000 000 000.)* (Gap 5, decided by Claude under the reviewer's delegation (2026-11-07).)
- **R9.** [BUG-2347] (owner, OQ-22) A template that skips approval — `requires_approval = False` or `auto_approve = True` — is created only when the caller is the workspace owner (owner as Q1's Resolution). Anyone else → `HTTPException` 403 `Only the workspace owner can skip approval on a template`, nothing written (no template, no line). The defaults (`requires_approval = True`, `auto_approve = False`) need no role. *(Today: stored as sent, whoever the caller is. Verified.)*
- **R10.** `items` `None` or `[]` creates no line.
- **R11.** Order of refusals (gap 8, decided by Claude under the reviewer's delegation (2026-11-07)): 403 (R9); 400 missing cost centre (R5); 404 for references in the order `account_id`, `cost_center_id`, `default_approver_id` (R6). Only the first refusal is reported; schema 422s (R3, R4, R8, R8a) come before the manager is called.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R6 references (after fix) | `HTTPException` 404 | as R6 |
| R5 missing cost centre (after fix) | `HTTPException` 400 | `Select a <category> for this template` |
| [BUG-2347] non-owner skips approval | `HTTPException` 403 | `Only the workspace owner can skip approval on a template` |
| unknown `account_id` / `default_approver_id` (today) | `IntegrityError` at flush | — |

**Side effects:** one `order_templates` row and 0..n `order_template_items` rows, flushed.

---

## `OrderTemplateManager.update_template(session, tpl_id, data, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `OrderTemplateService.update_template` ← `PUT /order-templates/{id}/`)

**Returns:** the updated template, flushed.

**Rules:**
- **R1.** An unknown id, or another workspace's, → 404 `Order template with ID <tpl_id> not found`, nothing written.
- **R2.** Fields sent are applied; fields not sent are unchanged. An inactive template can be updated, and `is_active: true` switches it back on (order template DAO Q1 ✅).
- **R3.** ✅ (Q11) Recurrence fields and `next_generation_date` are applied unchecked.
- **R4.** [BUG-2355, BUG-2365] A sent `template_name` is stored trimmed; blank → 422; over 255 → 422. [BUG-2365] A sent `recurrence_type` over 50 characters → 422.
- **R5.** [BUG-2357] An explicit `null` clears the nullable fields listed in Q2's Resolution — except that `cost_center_id: null` on a template whose merged category is `factory` or `department` gets BUG-2361's 400 (R8; gap 6: the category rule wins); `null` for `template_name`, `is_recurring`, `is_active`, `auto_approve`, `requires_approval` → 422. *(Today: every `null` is ignored. Verified for `description`, `template_name`.)*
- **R6.** [BUG-2356] (HR-9) `updated_by = user_id` only when at least one field changes value; an empty payload, or values equal to the stored ones, write nothing (`updated_by`, `updated_at` unchanged). *(Today: `updated_by` written on every call; an empty payload also set `updated_at`. Verified.)*
- **R7.** [BUG-1014, BUG-1216, BUG-2362] A sent `account_id`, `cost_center_id`, `default_approver_id` is checked as `create_template` R6. A reference not sent is not checked again.
- **R8.** [BUG-2359, BUG-2360, BUG-2361] The category rules of `create_template` R4, R5 hold on the merged state (stored values overlaid with those sent).
- **R8a.** [BUG-1216, BUG-2362] When `expense_category` or `cost_center_id` is sent, the merged `cost_center_id` is checked against the merged category as `create_template` R6: a department id kept while the category moves to `factory` → 404 `Factory with ID <id> not found` (and the reverse), nothing written. (Gap 7, decided by Claude under the reviewer's delegation (2026-11-07).) *(Today: stored unchecked.)*
- **R9.** [BUG-2347] (owner, OQ-22) A request that **changes** `requires_approval` or `auto_approve` (a sent value different from the stored one, either direction) is applied only when the caller is the workspace owner (Q1's Resolution); anyone else → 403 `Only the workspace owner can skip approval on a template`, nothing written, the other fields of the request included. Sending the stored value is not a change and needs no role. A non-owner may still change every other field of a template that already skips approval. *(Today: applied as sent, whoever the caller is.)*
- **R10.** Lines are not touched.
- **R11.** Order of refusals (gap 8, decided by Claude under the reviewer's delegation (2026-11-07)): 404 for the template (R1); 403 (R9); 400 missing cost centre (R8); 404 for references, in the order `account_id`, `cost_center_id`, `default_approver_id` (R7, R8a). Only the first refusal is reported. Schema 422s come before the manager is called.

**Errors:** 404 (R1); after fixes as `create_template`.

**Side effects:** fields changed, `updated_by`, `updated_at`; flushed.

---

## `OrderTemplateManager.get_template(session, tpl_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: `OrderTemplateService.get_template` ← `GET /order-templates/{id}/`; `create_expense_order_from_template`)

**Rules:**
- **R1.** The template of the workspace is returned, active or inactive.
- **R2.** Unknown id or another workspace's → 404 `Order template with ID <tpl_id> not found`.

---

## `OrderTemplateManager.list_templates(session, workspace_id, is_active=None, expense_category=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `OrderTemplateService.list_templates`)

**Rules:**
- **R1.** Returns `OrderTemplateDAO.get_by_workspace` for the same arguments, unchanged (order template DAO spec R1–R8, BUG-1210). The manager's default `is_active=None` lists active and inactive templates; the endpoint passes `True` by default.

---

## `OrderTemplateManager.delete_template(session, tpl_id, workspace_id, user_id)`
**Shape:** state-transition (deactivate) · **Persistence:** writes · **Visibility:** public (used by: `OrderTemplateService.delete_template` ← `DELETE /order-templates/{id}/`, 204)

**Returns:** `None`.

**Rules:**
- **R1.** Unknown id or another workspace's → 404 `Order template with ID <tpl_id> not found`.
- **R2.** An active template gets `is_active = False`, `updated_by = user_id` (and `updated_at`). The row and its lines stay.
- **R3.** An already inactive template: nothing is written, no error; `updated_by` keeps the first deleter (verified).
- **R4.** Expense orders already made from it are not touched.

**Side effects:** R2 fields, flushed.

---

## `OrderTemplateManager.add_item(session, tpl_id, data, workspace_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `OrderTemplateService.add_item` ← `POST /order-templates/{id}/items/`)

**Returns:** the new `OrderTemplateItem`, flushed.

**Rules:**
- **R1.** Unknown template or another workspace's → 404 `Order template not found` (no id in the message), nothing written.
- **R2.** `line_number` = highest existing line number of the template + 1; 1 for a template with no lines. Numbers of removed lines are not filled: lines 1–4, remove 4, add → 4; then remove 1, add → 5 (verified).
- **R3.** `workspace_id` and `order_template_id` are set from the arguments; an inactive template accepts lines.
- **R4.** `line_subtotal` as `create_template` R8, with BUG-2363, BUG-2364, BUG-2365 (`unit`) applying to `data`.

---

## `OrderTemplateManager.update_item(session, item_id, data, workspace_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `OrderTemplateService.update_item` ← `PUT /order-templates/items/{item_id}/`)

**Returns:** the line, flushed.

**Rules:**
- **R1.** Unknown line or another workspace's → 404 `Template item not found`.
- **R2.** Fields sent are applied; others unchanged. The template's state is not checked.
- **R3.** [BUG-2358] An explicit `null` clears `description`, `unit`, `unit_price`, `notes`; `quantity: null` → 422. *(Today: ignored. Verified for `unit_price`.)*
- **R4.** When `quantity` or `unit_price` is sent, `line_subtotal` = (sent or stored quantity) × (sent or stored price, `None` → 0), rounded by the column (3 × 0.125 → price 0.13, subtotal 0.38 today; BUG-2363 refuses 0.125). BUG-2363, BUG-2364 apply to `data`. When neither is sent, `line_subtotal` is unchanged (description-only update kept 30.00, verified).
- **R4a.** [BUG-2349] When the new subtotal (merged quantity × merged price) would have more than 13 integer digits, the update is refused: `HTTPException` 422 `Line total is too large`, nothing written (the schema cannot see the stored value). *(Today: `DataError` 22003 at flush.)*
- **R5.** [BUG-1226] A sent `unit_price` of 0 gives subtotal quantity × 0 = 0. *(Today: 0 counts as not sent and the stored price is used: 3 × 10.00 with `unit_price: 0` stored price 0.00, subtotal 30.00. Verified.)*
- **R6.** [BUG-2358] A price cleared with `null` gives subtotal 0.

---

## `OrderTemplateManager.remove_item(session, item_id, workspace_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: `OrderTemplateService.remove_item` ← `DELETE /order-templates/items/{item_id}/`, 204)

**Rules:**
- **R1.** Unknown line or another workspace's → 404 `Template item not found`, nothing deleted.
- **R2.** The line is physically deleted and flushed; other lines keep their numbers (no renumbering). The removed instance is returned, its attributes still readable.

---

## `OrderTemplateManager.get_items(session, tpl_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `OrderTemplateService.get_items` ← `GET /order-templates/{id}/items/`; `create_expense_order_from_template`)

**Rules:**
- **R1.** Returns `OrderTemplateItemDAO.get_by_template` (all lines, ordered per BUG-1211), lines of inactive templates included.
- **R2.** [BUG-2366] An unknown template, or another workspace's, → 404 `Order template with ID <tpl_id> not found`. *(Today: `[]`. Verified.)*

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 32 | `data.items or []` | `create_template` R10 |
| 33–37 | template dict, workspace, creator; DAO create; no role check (BUG-2347) | `create_template` R1–R7, R9, R11 |
| 39 | loop, `enumerate(start=1)` | `create_template` R8, R10 |
| 45–47 | quantity; `unit_price or 0`; product (overflow BUG-2349) | `create_template` R8, R8a |
| 58–60 | lookup / 404 | `update_template` R1 |
| 62 | `exclude_unset`, `exclude_none` | `update_template` R2, R5 (BUG-2357) |
| 63–64 | `updated_by` always (BUG-2356); DAO update; no role check (BUG-2347), no merged-state checks | `update_template` R2, R3, R6–R11 |
| 67–70 | lookup / 404 / return | `get_template` R1, R2 |
| 78–82 | DAO list | `list_templates` R1 |
| 85–87 | lookup / 404 | `delete_template` R1 |
| 88–89 | already inactive → return | `delete_template` R3 |
| 90 | deactivate + stamp | `delete_template` R2, R4 |
| 98–100 | lookup / 404 | `add_item` R1 |
| 102–103 | `max(..., default=0) + 1` | `add_item` R2 |
| 105–114 | dict, subtotal, create | `add_item` R3, R4 |
| 121–123 | lookup / 404 | `update_item` R1 |
| 124 | `exclude_none` | `update_item` R2, R3 (BUG-2358) |
| 126 | quantity or price sent / neither | `update_item` R4 |
| 127–129 | stored quantity fallback; `or` chain (BUG-1226); product (overflow BUG-2349) | `update_item` R4, R4a, R5, R6 |
| 135–140 | lookup / 404; delete; flush; return | `remove_item` R1, R2 |
| 142–143 | DAO list, no parent check (BUG-2366) | `get_items` R1, R2 |
| 146 | singleton | Not specified |

## Gap log
G1 (`order_template_manager.cases.md` gap 1) — Fact — Facts: types of the date and integer fields.
G2 (gap 2) — Fact — Facts: `is_active`, `is_deleted`, `deleted_at` on accounts, factories, departments; "deleted" = `is_deleted`.
G3 (gap 3) — Fact — Facts: the minimal `ExpenseOrder` row.
G4 (gap 4) — Fact — `create_template` R3, `update_template` R4 name `recurrence_type` (String(50)) under BUG-2365.
G5 (gap 5) — Intent, decided under the delegation (2026-11-07) — new 🐞 BUG-2349: `create_template` R8a (schema 422), `update_item` R4a (manager 422 `Line total is too large`). Verified: `DataError` 22003 today.
G6 (gap 6) — Contradiction — `update_template` R5: `cost_center_id: null` on a factory / department template gets BUG-2361's 400 (the category rule wins).
G7 (gap 7) — Intent, decided under the delegation (2026-11-07) — `update_template` R8a: merged cost centre checked against the merged category (BUG-1216 / BUG-2362 scope).
G8 (gap 8) — Intent, decided under the delegation (2026-11-07) — `create_template` R11, `update_template` R11: order of refusals.
G9 (gap 9) — Test mechanics — Notes: no card for HR-15's negative side here; no rule changed.
