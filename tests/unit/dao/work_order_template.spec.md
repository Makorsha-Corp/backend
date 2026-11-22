# Spec — `app/dao/work_order_template.py`

> **Status:** APPROVED (2026-11-06; nothing open). Stays APPROVED after fill-gaps 2026-11-07 (Gap log at the end).
> **Source commit:** e48a092

> **Revision 2026-11-07 (fill-gaps of `work_order_template.cases.md` gaps 1–4).** Facts only: model modules (M2, M3), the base `create` signature (Notes), keyword-only calls (Notes, no rule), `factory_id = 0` (`list_recurring_due` R5b, read from the code). No rule changed; no question; no new bug.

> **Review round 2026-11-06.** No owner question here. Four house-rule / precedent lines, decided by Claude under the reviewer's delegation (2026-11-06): BUG-2330, BUG-2331, BUG-2332, BUG-2333. Base behaviour is in `tests/unit/dao/base.spec.md` and is not restated. The sibling `tests/unit/dao/order_template.spec.md` (APPROVED) settled the same shapes for expense order templates; its Q1 (`is_active` is an on/off switch, not a soft delete) is applied here unchanged.
>
> **Verified by running** (`v1.py`, `v2.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tpl\A\`, one outer transaction rolled back against `marker_test`; nothing committed): the three tables' columns, defaults, constraints, no trigger; database `TimeZone` = `America/New_York`; two templates created in one transaction have **the same `created_at`**, and it is the database's local time (18:07 while `utcnow()` gave 23:07); `list_recurring_due` with `factory_id` still returns a template whose default section is soft-deleted. **Not run:** HTTP; concurrent transactions; the intended behaviour of any bug.

## Review
> All answered 2026-11-06 (delegated).

| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| HR-6 | Template list ordered by `created_at` alone | bug — `created_at` desc, then `id` desc | house rule |
| HR-6 | A template's approvers come back in no fixed order | bug — `id` ascending | house rule (standing decision) |
| HR-4 | A factory-scoped run still matches templates through a deleted section | bug — the deleted section neither filters nor matches | house rule (factory section DAO FU-4) |
| P1 | `created_at` / `updated_at` are the database's local time | bug — `utcnow()` (BUG-1102 precedent) | Claude, delegated |

### House-rule violations — applied automatically

- **HR-6** `WorkOrderTemplateDAO.get_by_workspace` R5 — a page ordered by `created_at` alone. `created_at` is the database's `now()`, the **transaction's** start time, so every template made in one request (or one test) has the same value (verified), and paging over a tie can repeat one row and miss another (BUG-1210, same code in the expense template DAO). Intended: `created_at` descending, then `id` descending, before `skip` / `limit`. Newest first stays.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2330 (pattern `tied-timestamp-no-tiebreak`). Rules: `get_by_workspace` R5.
- **HR-6** `WorkOrderTemplateApproverDAO.get_by_template` R2 — no `ORDER BY`. The list is shown at `GET /work-order-templates/{id}/approvers/` and is the order in which a generated work order receives its approvers (and their `approver_added` events). Standing decision (order template DAO spec): a missing `ORDER BY` is a bug. Intended: `id` ascending, which is the order the approvers were chosen in (`_replace_approvers` inserts them in the order sent).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2331 (pattern `unordered-pagination`). Rules: `WorkOrderTemplateApproverDAO.get_by_template` R2.
- **HR-4** `list_recurring_due` R5 — the `factory_id` scope joins `factory_sections` without looking at `is_deleted` (factory section DAO FU-4 routed it here). A template whose default section is soft-deleted is still matched through that section's factory (verified). HR-4, third bullet: a soft-deleted related row neither filters nor matches. Intended: in a factory-scoped run a template matches only through a **live** default section (or by having no section); a template whose default section is deleted does not match, and a section-scoped run naming a deleted section matches nothing.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-2332 (pattern `join-ignores-soft-deleted`). Rules: `list_recurring_due` R5, R5a. The template rows are untouched; they match again if the section is restored. The machine side (machines of a deleted section) is `resolve_template_machine_ids`', FU-2.

### Precedent matches

### P1. A template's creation time is the database's local time — 🐞 BUG-2333
**Background:** `work_order_templates.created_at` has the database default `now()` and `updated_at` the ORM's `onupdate=func.now()`. Both columns are `timestamp without time zone`. The rest of the app writes naive UTC from `utcnow()`.
**What happens today, verified:** under the test database's `America/New_York`, a template created at 23:07 UTC has `created_at` 18:07. The value moves with the server's `TimeZone` setting.
**Example:** On a database set to `Asia/Dhaka` the same template would read 05:07 the next day; the web app, which treats every timestamp as UTC, shows it 6 hours off.
**Rules affected:** Model facts; `get_by_workspace` R5 (the sort key).
**Answer:** bug — per BUG-1102 precedent: `created_at` defaults to `utcnow()` and `updated_at` is set from `utcnow()` on update, naive UTC (precedent — confirm)
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-06): 🐞 BUG-2333 (pattern `database-clock-timestamp`). The fix is in `app/models/work_order_template.py`; existing rows keep their values. Rules: Model facts M1. Note: with `utcnow()` two rows made in one request no longer share a timestamp by construction, but BUG-2330's tie-break is still needed.

Checked and **not** a new line here: **HR-5** — every filter is in the query, except `list_recurring_due`'s date filter, which runs in Python over an **unpaged** result, so nothing is cut first. **HR-7** — `GET /work-order-templates/` requires `1 <= limit <= 1000`, `skip >= 0`. **HR-8** — no `LIKE`. **HR-1, HR-2** — `template_name` is the manager's / schema's (manager spec); names are not unique by design (no constraint, like expense templates). **HR-9** — the DAO writes no stamp. **HR-10** — locking is the manager's (manager spec BUG-2343). **HR-15** — `cost` and `quantity` are `Numeric(15, 2)`: the database rounds half away from zero (verified through the manager: `0.125` → `0.13`). **HR-16** — every read compares the row's own `workspace_id` (R1 of each method); links written across workspaces are BUG-1015 (manager). **HR-4** (by-id reads) — `is_active` is a switch with a restore endpoint, not a soft delete (order template DAO Q1, applied); `get_by_id_and_workspace` stays raw.

## Overview
Three DAOs for work order templates ("Monthly oil change"): `WorkOrderTemplateDAO` (templates), `WorkOrderTemplateItemDAO` (preset part lines) and `WorkOrderTemplateApproverDAO` (default approvers). They are used only by `WorkOrderTemplateManager` (reached through `/work-order-templates/` and by `WorkOrderManager` when a work order is made from a template). Each read is scoped by the row's own `workspace_id`. Creates and updates are the base's. There is no `is_deleted`: `DELETE /work-order-templates/{id}/` sets `is_active = False` and `POST …/restore/` sets it back.

**Callables:** 7 specified · 4 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts**
- **M1.** `work_order_templates` (`app.models.work_order_template.WorkOrderTemplate`): `workspace_id` NOT NULL FK CASCADE; `template_name` String(255) NOT NULL, no unique constraint; `work_order_type_id` NOT NULL FK `work_order_types` RESTRICT; `priority` varchar NOT NULL default `'MEDIUM'`; `uses_inventory`, `requires_approval`, `is_recurring`, `auto_generate` Boolean NOT NULL default false; `is_active` NOT NULL default true; `account_id` FK `accounts` RESTRICT; `cost` `Numeric(15, 2)` nullable; recurrence columns `recurrence_type` String(50), `recurrence_day` Integer, `next_generation_date`, `recurrence_start_date`, `recurrence_end_date` Date, all nullable; `default_factory_section_id` FK SET NULL, `default_machine_id` FK SET NULL; `created_by`, `updated_by` FK `profiles` SET NULL. [BUG-2333] `created_at` NOT NULL defaults to `utcnow()` (naive UTC) and `updated_at` is set from `utcnow()` on update. *(Today: database `now()`, the transaction start in the server's `TimeZone`. Verified: 18:07 for 23:07 UTC.)* `updated_at` is `NULL` until the first update. No trigger.
- **M2.** `work_order_template_items` (`app.models.work_order_template_item.WorkOrderTemplateItem`): `workspace_id`, `work_order_template_id` (CASCADE) NOT NULL; `item_id` NOT NULL FK `items` (no action); `quantity` `Numeric(15, 2)` NOT NULL default 1; `action_type` String(20) NOT NULL default `'CONSUME'`, no check constraint (the schema allows `CONSUME`, `INSTALL`, `REPLACE`, `BORROW`); `replaced_item_id` nullable FK `items`; `notes` Text. No unique constraint: one item can appear twice.
- **M3.** `work_order_template_approvers` (`app.models.work_order_template_approver.WorkOrderTemplateApprover`): `workspace_id`, `work_order_template_id` (CASCADE), `user_id` (FK `profiles` CASCADE) NOT NULL; `approver_slot` String(32) nullable, **never written by any code** (always `NULL`); unique `uq_wo_template_approver (work_order_template_id, user_id)`.
- **M4.** Nothing in the database requires an item's or approver's `workspace_id` to be its template's (the manager always sets both from the caller).
- **M5.** `auto_generate` is stored and returned; nothing in `app/` reads it.

**Notes for the test designer**
- Singletons `work_order_template_dao`, `work_order_template_item_dao`, `work_order_template_approver_dao`. Every parameter after `db` is keyword-only; a positional call raises `TypeError`. This is a note, not a rule: no card is needed (as `order_template.cases.md` gap 1).
- Build rows directly. A template needs `workspace_id`, `template_name`, `work_order_type_id` (a `WorkOrderType(workspace_id, name)`); give `created_at` explicitly, distinct unless the case is about a tie. An item line needs an `Item(workspace_id, name, name_normalized, unit)`. Factories / sections / machines as `tests/unit/dao/test_factory_section.py`.
- **The ties (BUG-2330, BUG-2331):** rows of one `created_at` (or approvers inserted out of id order via explicit ids), update an early one, flush, `db.expire_all()`. Today's order rests on physical row order: write to the intended result, **non-strict** xfail.
- **BUG-2333:** create through the base `create(db, *, obj_in)` (a dict or a schema; `self.model(**obj_in)`, `add`, `flush`, returns the row) or with `db.add(...)` directly: both leave `created_at` to the model's default, so either proves the rule. Then flush, refresh; compare with a patched-free `utcnow()` window. Strict xfail today (5 h off under `America/New_York`). If the test database runs in `UTC` the case passes by accident: set `SET LOCAL TimeZone = 'Asia/Dhaka'` first.
- Negative paging values: wrap in `with db.begin_nested():` inside `pytest.raises(DataError)`.

## Not specified
- `work_order_template_dao`, `work_order_template_item_dao`, `work_order_template_approver_dao` — module singletons.
- Inherited `BaseDAO` methods of all three (`create`, `update`, `remove`, `get`, `get_multi`) — `tests/unit/dao/base.spec.md`. `WorkOrderTemplateDAO.get_by_workspace` and both `get_by_id_and_workspace` replace the base ones (line-for-line copies apart from the filters below), so BUG-100's fix does not reach `get_by_workspace`. Base `remove` has no caller on any of the three; items are removed by the manager with `session.delete`.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Work order template manager** (spec written alongside) | BUG-1015, BUG-1228, BUG-360…363 and everything about what a template puts into a work order. | reading the callers |
| FU-2 | **Work order generation util** (`tests/unit/utils/work_order_generation.spec.md`, APPROVED) | Read, not run: with BUG-2332, a template whose default section is deleted is no longer chosen by a factory run, but a section run for that template's section, or a template with a deleted section reached another way, still asks `resolve_template_machine_ids` for that section's machines, which does not look at the section's `is_deleted`. Decide there whether a deleted section yields `[]` (HR-4 suggests yes). | HR-4 line |

---

## `WorkOrderTemplateDAO.get_by_workspace(db, *, workspace_id, is_active=None, work_order_type_id=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `WorkOrderTemplateManager.list_templates` ← `GET /work-order-templates/`, which passes `is_active` default `True`; `WorkOrderTemplateManager.generate_drafts` with `is_active=True, limit=1000`)

**Purpose:** One workspace's templates, newest first, with two optional filters.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality on the row's `workspace_id` |
| `is_active` | `bool` \| `None` | `None` = both |
| `work_order_type_id` | `int` \| `None` | `None` or `0` = no filter; otherwise equality |
| `skip`, `limit` | int, defaults 0 / 100 | not validated |

**Returns:** a `list` of `WorkOrderTemplate` (possibly empty).

**Rules:**
- **R1.** Only rows of that workspace are returned. An unknown workspace, or one with no templates, returns `[]`.
- **R2.** `is_active=None` returns active and inactive rows; `True` / `False` only those.
- **R3.** A non-zero `work_order_type_id` keeps rows of that type only. A type of another workspace returns `[]`.
- **R4.** `work_order_type_id=None` and `0` apply no filter.
- **R5.** [BUG-2330] (HR-6) Rows are ordered by `created_at` descending, then `id` descending, before `skip` / `limit`; consecutive pages neither repeat nor miss a row. *(Today: `created_at` only, and rows made in one transaction share it.)*
- **R6.** Filters combine (AND) and apply before `skip` / `limit`.
- **R7.** At most `limit` rows after `skip`; with the defaults at most 100 (101 rows → 100; `limit=1000` → 101).
- **R8.** `limit=0` or `skip` past the end returns `[]`; a negative `limit` raises `DataError` pgcode `2201W`, a negative `skip` `2201X`.

**Errors:** as R8. **Side effects:** none

---

## `WorkOrderTemplateDAO.list_recurring_due(db, *, workspace_id, target_date, factory_section_id=None, factory_id=None)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `WorkOrderTemplateManager.generate_drafts`)

**Purpose:** The active recurring templates of a workspace whose next run is due on `target_date`, optionally limited to a section or factory.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality |
| `target_date` | `date` | the day being planned |
| `factory_section_id` | `int` \| `None` | `None` = no section filter; any other value (`0` included) = equality on `default_factory_section_id` |
| `factory_id` | `int` \| `None` | `None` = no factory filter; any other value (`0` included) = R5, R5b |

**Returns:** a `list` of `WorkOrderTemplate`, unpaged, **in no guaranteed order**.

**Rules:**
- **R1.** Only rows of that workspace, with `is_active = True` and `is_recurring = True`. An inactive or non-recurring template is never returned.
- **R2.** Due means: `next_generation_date` is set **and** on or before `target_date`. Equal → returned; one day after → not; `NULL` → not. An overdue template (date long past) is returned.
- **R3.** And the program has not ended: `recurrence_end_date` is `NULL`, or `target_date` is on or before it. `target_date` equal to the end date → returned; one day after → not.
- **R4.** With `factory_section_id`, only templates whose `default_factory_section_id` equals it. A template with no section is not returned.
- **R5.** With `factory_id`, a template is returned if it has **no** default section, or its default section belongs to that factory. A template whose section is in another factory is not returned.
- **R5a.** [BUG-2332] (HR-4) A soft-deleted default section neither matches nor filters: with `factory_id`, a template whose default section has `is_deleted = True` is **not** returned (whatever factory the section had); with `factory_section_id` naming a deleted section, nothing is returned. A template with no section still matches a factory run. *(Today: the deleted section's factory still matches and the section id still filters. Verified for the factory case.)*
- **R5b.** `factory_id = 0` (or any id that is no factory) is a filter, not "no filter": only due templates with **no** default section are returned (the check is `is not None`). Likewise `factory_section_id = 0` returns `[]` (R4). (Read from the code, gap 4.)
- **R6.** Both scopes given: both apply (AND).
- **R7.** All matching rows are returned, no cap. The due / end checks of R2, R3 run after loading every active recurring template of the scope; nothing is cut before them.

**Errors:** none. **Side effects:** none

---

## `WorkOrderTemplateDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by every by-id method of `WorkOrderTemplateManager`)

**Returns:** the row, or `None`.

**Rules:**
- **R1.** The row with that id in that workspace is returned.
- **R2.** Another workspace's id, or an unknown id, returns `None`.
- **R3.** `is_active` is not looked at: an inactive template is returned (order template DAO Q1, applied).

**Errors:** none. **Side effects:** none

---

## `WorkOrderTemplateItemDAO.get_by_template(db, *, work_order_template_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `WorkOrderTemplateManager.get_items` ← `GET /work-order-templates/{id}/items/`, `WorkOrderManager.create_work_order_from_template`)

**Returns:** a `list` of `WorkOrderTemplateItem`, all of them, unpaged.

**Rules:**
- **R1.** The rows with that template id and that `workspace_id`, ordered by `id` ascending (the order they were added). An unknown template, or one with no lines, returns `[]`.
- **R2.** A call with another workspace returns `[]`.
- **R3.** Isolation follows the line's own `workspace_id`, not the template's (M4): a line with workspace B on a template of A is returned for B, not for A.
- **R4.** The template's `is_active` is not looked at: lines of an inactive template are returned.

**Errors:** none. **Side effects:** none

---

## `WorkOrderTemplateItemDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `WorkOrderTemplateManager.update_item`, `remove_item`)

**Rules:**
- **R1.** The line with that id in that workspace is returned; another workspace's id or an unknown id returns `None`.
- **R2.** The template's state is not looked at.

**Errors:** none. **Side effects:** none

---

## `WorkOrderTemplateApproverDAO.get_by_template(db, *, work_order_template_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `WorkOrderTemplateManager.get_approvers` ← `GET /work-order-templates/{id}/approvers/`, `WorkOrderManager.create_work_order_from_template`)

**Returns:** a `list` of `WorkOrderTemplateApprover`, unpaged.

**Rules:**
- **R1.** The rows with that template id and that `workspace_id`; an unknown template, or another workspace, returns `[]`. Isolation follows the row's own `workspace_id` (M4).
- **R2.** [BUG-2331] (HR-6) Ordered by `id` ascending. *(Today: no `ORDER BY`.)*
- **R3.** The template's `is_active` and the approver's membership are not looked at: a row for a user who has since left the workspace is returned.

**Errors:** none. **Side effects:** none

---

## `WorkOrderTemplateApproverDAO.delete_all_for_template(db, *, work_order_template_id, workspace_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** internal (used by: `WorkOrderTemplateManager._replace_approvers`)

**Returns:** `None`.

**Rules:**
- **R1.** Every approver row with that template id and that `workspace_id` is deleted at once, in the database (a bulk `DELETE`, executed immediately, no separate flush needed); a following `get_by_template` returns `[]`.
- **R2.** Rows of other templates, and rows of that template carrying another `workspace_id`, are untouched.
- **R3.** No matching rows: nothing happens, no error.

**Errors:** none. **Side effects:** hard delete of the matched rows; nothing committed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 21–26 | keyword-only parameters; defaults | Notes; `get_by_workspace` R2, R4, R7 |
| 27 | workspace | `get_by_workspace` R1 |
| 28–29 | `is_active is not None` | `get_by_workspace` R2, R6 |
| 30–31 | `if work_order_type_id:` `None` / `0` skip | `get_by_workspace` R3, R4 |
| 32 | `created_at` desc, no tie-break (BUG-2330); offset / limit | `get_by_workspace` R5, R7, R8 |
| 39–43 | workspace, active, recurring | `list_recurring_due` R1 |
| 44–45 | `factory_section_id is not None` (no section liveness, BUG-2332) | `list_recurring_due` R4, R5a, R6 |
| 46–53 | `factory_id is not None`: outer join, no section / section's factory (no liveness, BUG-2332) | `list_recurring_due` R5, R5a, R6 |
| 54 | `.all()`, no limit, no order | `list_recurring_due` R7, Returns |
| 57 | `next_generation_date is not None` | `list_recurring_due` R2 |
| 58 | `next_generation_date <= target_date` | `list_recurring_due` R2 |
| 59 | end `None` or `target_date <= end` | `list_recurring_due` R3 |
| 63–65 | id AND workspace, `.first()` | `WorkOrderTemplateDAO.get_by_id_and_workspace` R1–R3 |
| 70–73 | template AND workspace, `id` order | item `get_by_template` R1–R4 |
| 76–78 | id AND workspace | item `get_by_id_and_workspace` R1, R2 |
| 83–86 | template AND workspace, no order (BUG-2331) | approver `get_by_template` R1–R3 |
| 89–92 | bulk delete | `delete_all_for_template` R1–R3 |
| 95–97 | singletons | Not specified |
| model | `created_at` `server_default=now()`, `updated_at` `onupdate=now()` (BUG-2333) | M1 |

## Gap log
G1 (`work_order_template.cases.md` gap 1) — Fact — modules of `WorkOrderTemplateItem`, `WorkOrderTemplateApprover` added to M2, M3.
G2 (gap 2) — Fact — the base `create` signature; a direct `db.add` proves BUG-2333 the same way (Notes).
G3 (gap 3) — Fact — keyword-only calls stay a note, no card (Notes).
G4 (gap 4) — Fact — `factory_id = 0` and `factory_section_id = 0` are filters (`list_recurring_due` R5b, Inputs).
