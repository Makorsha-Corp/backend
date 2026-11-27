# Spec — `app/services/machine_service.py`

> **Status:** APPROVED (2026-11-04; nothing open). Stays APPROVED after fill-gaps (Gap log at the end; decided by Claude under the reviewer's delegation (2026-11-04)).
> **Source commit:** e48a092
> **Revision (2026-11-04):** fill-gaps from `machine_service.verify.md` Finding 3 (surviving mutant `limit` 100 → 101): new rule `get_machine_activity` R1a (default `limit`). No existing rule changed.

> **Form.** As `tests/unit/services/department_service.spec.md`: this spec covers only what the service adds. The **Transaction contract TC1–TC6 is defined there** and cited here, not restated. Below the service: `tests/unit/managers/machine_manager.spec.md`, `tests/unit/managers/machine_activity_manager.spec.md` (both APPROVED), `tests/unit/dao/machine.spec.md`, `tests/unit/dao/machine_activity_event.spec.md`. `app/services/machine_work_service.py` (`upcoming_work`, reached through `get_upcoming_work`) has no spec yet: its outcomes needed here are written as rules of `get_upcoming_work` (FU-1).

> **Routed here and written as rules:** machine manager FU-1 (a) BUG-968, the translation of the in-use refusal into a 400 carrying the blockers (`delete_machine` R2, R3); (b) BUG-955, BUG-966 (`include_deleted` on `get_machine`) and BUG-956 (on `get_machines`); (c) Q1 below, BUG-1570; (d) D1 below. Machine activity manager FU-1 (Q5, Q6 answered `intended` there): `get_machine_activity` R3–R6. No other spec was edited; the register rows of BUG-955, BUG-956, BUG-966 now name this service (BUG-968's already does).
>
> **Decided by Claude under the reviewer's delegation (2026-11-04):** Q1 (BUG-1570), D1 (intended), D2 (default `limit` of `get_machine_activity` as a rule, fill-gaps). The translation scope of FU-1 (a) follows `machine_item_service.spec.md` Q1, applied as precedent. House-rule lines: BUG-1571, BUG-1572. None of this is the owner's answer; none touches money, stock, an order workflow or who may see or do what.
>
> **Standing decisions applied here (not asked again):** HR-4 (hidden unless asked for; `include_deleted` reachable from the API). A refused delete lists what blocks it, in the 400 body (`app.core.exceptions.ValidationError(detail, errors)`). Every other refusal stays the manager's `HTTPException`, passed on unchanged. Things of a soft-deleted factory are hidden by the factory's state (factory manager standing decision 2). A log of activity is history and stays readable for a deleted machine (machine activity manager standing decision 1).
>
> **Verified by running** (`h.py`, `v2_mach.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2\`, one outer transaction rolled back against `marker_test`, session as the `db` fixture; HTTP through `TestClient` with overridden dependencies; nothing persisted): `create_machine` returns a `MachineResponse` with `latest_status_type` / `latest_status_at` `None` and survives a later rollback; `create_machine_event` returns a `MachineEventResponse` and the event survives a later rollback; `get_machine` and `get_machines` then show `RUNNING` with its time; an empty workspace lists `[]`; a newer `maintenance_logged` row carrying `"status": "OFF"` does not change the shown status; a `status_updated` row whose stored status is `"running"` (not a member) makes `get_machine` **and the whole list** raise `ValueError`; a machine with stock is deleted today and returned with `is_deleted = True`; a deleted machine is returned by id (HTTP 200); a machine of a deleted factory is returned by id; `include_deleted=` raises `TypeError` on both reads; `GET /machines/?include_deleted=true` answers 200 without the deleted machine; a patched manager `ValueError` on delete answers **500** over HTTP; `maintenance_window=bogus` and `sort_by=createdAt&sort_dir=DESC` answer 200; an event body without `machine_id` answers 400 (BUG-461), and a body `machine_id` other than the path's is replaced by the path's (201); upcoming work: default window today … today + 7 (+8 excluded, yesterday excluded), `within_days=8, include_overdue=True` adds the overdue `IN_PROGRESS` order and +8, `within_days=0` only today, `-1` gives `[]`, `GET /machines/upcoming-work/?within_days=0` answers 400; a machine of a deleted factory and **another workspace's machine** (a W1 work order on W2's machine "SecretMachine") are listed in W1's upcoming work, also over HTTP; activity: metadata `{}` → `metadata None`, unknown keys dropped (`note`), performer name shown; an unknown machine's activity → 404; a deleted machine's activity is returned. **Not run:** two concurrent requests; the intended behavior of the bug rules.

## Review
> All answered; nothing pending.

### House-rule violations — applied automatically

- **HR-16** `get_upcoming_work` R6 — upcoming work joins each work order of the workspace to its machine without checking the machine's workspace. A work order of W1 that names W2's machine (invalid data, BUG-1016 lets it be created) shows W2's machine id, name, factory id and section in W1's answer (verified, also over HTTP). Intended: only machines of the caller's workspace are joined; such an order is left out, and nothing of W2 is shown.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-1571 (pattern `missing-workspace-scope`). Fix in `MachineWorkService.collect_raw_items` (`Machine.workspace_id == workspace_id`). Rules: `get_upcoming_work` R6.
- **HR-4** (third bullet; factory manager standing decision 2) `get_upcoming_work` R7 — a live machine of a soft-deleted factory is listed with its open work (verified), although the machines page hides it (BUG-890) and opening it gives 404 (BUG-966). Intended: machines whose factory is soft-deleted are left out, as on the machines page.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-1572 (pattern `join-ignores-soft-deleted`; per BUG-890). Fix in `MachineWorkService.collect_raw_items`. Rules: `get_upcoming_work` R7.

### New questions — answered (decided by Claude under the reviewer's delegation (2026-11-04))

### Q1. A misspelt filter or sort on the machines page is silently ignored — 🐞 BUG-1570
**Background:** `GET /machines/` takes `maintenance_window` (`all`, `overdue`, `next_7_days`, `next_30_days`, `none_scheduled`), `sort_by` (`name`, `created_at`, `maintenance_date`) and `sort_dir` (`asc`, `desc`) as free text. Below it, any other value means "all" / "name" / "ascending" (machine DAO Q2, machine manager P8: intended there, the decision left to the endpoint review, machine manager FU-1 (c)). The web app's filter dialog sends exactly the listed values (`MachinesFiltersDialog.tsx`).
**What happens today:** `maintenance_window=bogus` answers 200 with every machine; `sort_by=createdAt&sort_dir=DESC` answers 200 sorted by name ascending (verified).
**Example:** An integration asks for `maintenance_window=OVERDUE` and believes the 40 machines it gets are all overdue.
**Rules affected:** `get_machines` R4 (integration-only)
**Suggested answer:** `bug — the endpoint accepts only the listed values for the three parameters (exact, lower case); anything else is refused by request validation (422; 400 today per BUG-461)`. The layers below keep their lenient fallback (already decided `intended`). Alternative: `intended`, documented.
**Answer:** bug — as suggested.
**Resolution:** 🐞 BUG-1570 (pattern `unvalidated-code-input`; per BUG-681). Fix in `app/api/v1/endpoints/machines.py` (`Literal` types). Rules: `get_machines` R4.

### D1. The event body must carry a `machine_id` the path overrides — ✅ intended
**Background:** `POST /machines/{id}/events/` validates `MachineEventCreate`, whose `machine_id` is required, then replaces it with the path's id (machine manager FU-1 (d)). The web app always sends it (`CreateMachineEventRequest`).
**What happens today:** a body without `machine_id` answers 400 (BUG-461); a body with another machine's id records the event on the path's machine (verified).
**Example:** A client posts to `/machines/12/events/` with `machine_id: 99`: the event is on machine 12.
**Rules affected:** `create_machine_event` R1 (integration-only)
**Answer:** intended — the path always wins, so the field can do no harm, and the only client sends it. No bug.

### D2. The default page size of `get_machine_activity` is a rule — decided by Claude under the reviewer's delegation (2026-11-04)
**Background:** `get_machine_activity` has its own default `limit=100`. `GET /machines/{id}/activity/` always passes `limit` (`Query(100)`), so the default is reached only by direct callers; the verifier found no rule for it (`machine_service.verify.md` Finding 3).
**Answer:** written as a rule, following the `app_settings_service` precedent (default limit as a rule, card ASV-L-09): a caller who omits `limit` gets at most 100 entries, the 100 newest of the manager's order. Read from the source (line 383); not a bug, no ID. Rules: `get_machine_activity` R1a.

Existing bugs written as rules here, no new ID: **BUG-955** `get_machine` R2, R3; **BUG-966** `get_machine` R4; **BUG-956** `get_machines` R2; **BUG-968** `delete_machine` R2, R3. Reached through the managers and cited, one pass-through case each, strict or non-strict exactly as in `machine_manager.cases.md` and `machine_activity_manager.cases.md`: BUG-886 … BUG-892, BUG-950 … BUG-954, BUG-957 … BUG-965, BUG-967, BUG-970 … BUG-975, BUG-1000, BUG-1090, BUG-1140, BUG-1141. BUG-969 is the frontend's.

Checked and **not** violated: **HR-1 … HR-3, HR-8, HR-9** — decided in the manager and schemas. **HR-5, HR-6** — the list is the manager's (BUG-957, BUG-958, BUG-887); upcoming work is filtered in the query and sorted by earliest date, then name case-insensitively, then machine id (stable; R5). **HR-7** — `GET /machines/` and `/activity/` enforce `1 <= limit <= 1000`; `/upcoming-work/` enforces `1 <= within_days <= 365`. **HR-10** — the status change is BUG-960 (manager); delete and edit need no lock. **HR-11 … HR-15** — none applies. **HR-16** — everything except upcoming work looks up by the caller's workspace, in the managers; the translated 400 carries the manager's blockers as they are.

**Permission checks:** none; any active member may create, edit, delete machines and change their status (as `department_service.spec.md`).

## Follow-ups for other reviews
> Nothing below is a rule of this service. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Machine work service** (`app/services/machine_work_service.py`, not yet specified) | `get_upcoming_work` R3–R8 here state the outcomes of `upcoming_work` / `collect_raw_items` reached from the API; BUG-1571 and BUG-1572 are fixed there. `dates_by_machine` and the three static helpers are reached through `MachineManager.search_machines` (machine manager spec R8–R17), which passes only its own machines, so BUG-1571 does not show there; BUG-1572 does not either (the manager hides those machines itself). The legacy `tests/test_machine_work_service.py` patches `collect_raw_items`. | `get_upcoming_work` |
| FU-2 | **Product-wide** (machine manager FU-9) | `get_upcoming_work` takes "today" from the server's `date.today()`, as `search_machines` does. | R1 |

## Overview
`MachineService` is the transaction boundary for machines and their status, and it shapes every machine answer: a `MachineResponse` carries the machine's current status (`latest_status_type`, `latest_status_at`), read from the activity log. The `/machines/` endpoints call it. It calls `MachineManager` for machines and status changes, `MachineActivityManager` for the status and the activity log, and `machine_work_service` for upcoming work. Besides commit, rollback and re-read, it has two jobs of its own: building the responses, and (intended, BUG-968) turning the manager's "this machine still has stock or open orders" `ValueError` into a 400 carrying the blocker list.

**Callables:** 10 specified · 2 not specified
**Externals to mock:** none. `get_upcoming_work` reads `date.today()` (not mocked: build dates from `date.today()` read in the test, as machine manager Notes). `deleted_at`: machine DAO `utcnow`.
**Integration-only behavior:** as `department_service.spec.md`; the 400 body of `app.core.exceptions.ValidationError`; the `include_deleted` query parameter on `GET /machines/` and `GET /machines/{id}/`; the endpoint's own checks (`skip`, `limit`, `within_days`, BUG-1570); the path id replacing the event body's `machine_id` (D1); response-model serialisation.

**Facts for the test designer**
- Import: `from app.services.machine_service import MachineService, machine_service`. `MachineService()` takes no arguments; attributes `machine_manager` (singleton of `app.managers.machine_manager`) and `activity_manager` (singleton of `app.managers.machine_activity_manager`). `machine_work_service` is the module-level name `app.services.machine_service.machine_work_service`. `get_upcoming_work` takes everything after `db` keyword-only; the other methods are positional-or-keyword.
- `MachineResponse` (`app/schemas/machine.py`): `id`, `workspace_id`, `name`, `is_running`, `factory_id`, `factory_section_id`, `factory_section_name`, `model_number`, `manufacturer`, `note`, `created_at`, `created_by`, `updated_at`, `updated_by`, `is_active`, `is_deleted`, `deleted_at`, `deleted_by`, `latest_status_type` (`MachineEventTypeEnum` or `None`), `latest_status_at`.
- `MachineEventResponse`, `MachineActivityEventResponse`, `MachineActivityEventMetadata` (10 keys: `changes`, `item_id`, `item_name`, `machine_item_id`, `maintenance_log_id`, `transfer_order_id`, `purchase_order_id`, `work_order_id`, `quantity`, `status`; no `extra` setting), `MachineUpcomingWorkRow`: `app/schemas/machine_event.py`, `machine_activity_event.py`, `machine_work.py`.
- `HTTPException` is `fastapi.HTTPException`. The translated refusal is `app.core.exceptions.ValidationError` (`.status_code == 400`, `.detail`, `.errors`).

**Notes for the test designer**
- Transaction mechanics (TC1–TC6): exactly as `department_service.spec.md` Notes.
- **Status rows:** build `MachineActivityEvent(workspace_id, machine_id, event_type="status_updated", description, metadata_json={"status": "RUNNING"})`, with `created_at` explicit when order matters, or call `create_machine_event`.
- **BUG-955, BUG-956, BUG-966:** the parameter does not exist today (`TypeError`) → strict xfail.
- **BUG-968 translation:** as `factory_service.spec.md` Notes for BUG-1331: one case with real rows (a `machine_items` row with `qty` 5), one with `patch.object(machine_service.machine_manager, "delete_machine", side_effect=ValueError("Machine has stock or open orders", [...]))`; both strict xfail.
- **Upcoming work:** `WorkOrderType(workspace_id, name)`, `WorkOrder(workspace_id, work_order_number, work_order_type_id, title, factory_id, machine_id, planned_date, status)`. BUG-1571: a second workspace with its own factory and machine, and a W1 work order with that machine's id; assert the W2 machine id and name appear nowhere in the result → strict xfail. BUG-1572: a factory with `is_deleted=True` holding a live machine with a `DRAFT` order tomorrow → strict xfail.
- **Pass-through cases:** one per manager bug reached, intended behavior, strict / non-strict as in the managers' cases files.

## Not specified
- `MachineService.__init__` — stores the two managers, no logic.
- `machine_service` — module-level singleton, no logic.

---

## `MachineService._to_machine_response(db, machine, status_map=None)`
**Shape:** mapper
**Persistence:** reads
**Visibility:** internal (used by: `create_machine`, `get_machine`, `update_machine`, `delete_machine`, `_to_machine_responses`)

**Purpose:** One machine as the API shows it, with its current status.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `machine` | `Machine` | a loaded row |
| `status_map` | `dict[int, MachineActivityEvent]` or `None` | `None`: the status is read for this machine alone |

**Returns:** a `MachineResponse`.

**Rules:**
- **R1.** Every column field of the response is the machine's value; `factory_section_id` / `factory_section_name` are the machine's read-only section properties (`None` without a section).
- **R2.** With `status_map=None` the status row is the activity manager's `get_latest_status(db, machine.id, machine.workspace_id)` (its R1–R6, BUG-1140): the newest `status_updated` row; other event types are ignored even when newer and carrying a `status` key (verified with a newer `maintenance_logged` row).
- **R3.** With a `status_map`, the status row is `status_map.get(machine.id)`; a machine missing from the map has none. No read is made.
- **R4.** `latest_status_type` = the stored `status` of that row (activity manager `status_from_activity` R1–R5) as a `MachineEventTypeEnum` member; `None` when there is no row, no metadata, no `status` key, or a falsy status (`""`, `None`). `latest_status_at` = that row's `created_at`, or `None` without a row (also when the row has no usable status: the time is then shown with no type).
- **R5.** A stored status that is not exactly a member value (`"running"`, `"bogus"`) raises `ValueError`, so the whole call fails; in a list one such row fails the whole list (verified). No writer stores one (`create_machine_event` writes members only); not tested beyond one case.

**Errors:** `ValueError` for R5; from R2, BUG-1140's intended 404 never applies here (the machine is in its workspace).

**Side effects:** none

---

## `MachineService._to_machine_responses(db, machines, workspace_id)`
**Shape:** mapper
**Persistence:** reads
**Visibility:** internal (used by: `get_machines`)

**Purpose:** Many machines as the API shows them, with one read for all their statuses.

**Rules:**
- **R1.** An empty list → `[]`, with no read.
- **R2.** Otherwise the statuses come from one `get_latest_status_map(db, workspace_id=…, machine_ids=[ids in list order])` (activity manager R1–R4; on a `created_at` tie BUG-1090 applies), and each machine is shaped by `_to_machine_response` R1, R3–R5. The output has one response per machine, in the input order.

**Errors:** as `_to_machine_response` R5.

**Side effects:** none

---

## `MachineService.create_machine(db, machine_in, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `POST /machines/`, 201)

**Purpose:** Create a machine, save it, and answer with its response.

**Returns:** a `MachineResponse` of the new machine, committed (TC1) and re-read before shaping (TC2): `created_at` set, `latest_status_type` and `latest_status_at` `None` (verified).

**Rules:**
- **R1.** The machine is created exactly as `MachineManager.create_machine` creates it (manager spec R1–R15: section link, `created` activity entry, BUG-950 … BUG-953, BUG-963, BUG-967, BUG-972); everything it flushed is committed. Verified.
- **R2.** The manager's refusals reach the caller unchanged and nothing is saved (TC3), also when the manager had already flushed the machine before a section refusal (manager R12): 404 `Factory with ID <factory_id> not found`, [BUG-963] 400 `Cannot create machine for deleted factory`, 409 `Machine with name '<name>' already exists in this factory`, the section's 404 / 400.
- **R3.** Commit and re-read failures follow TC4, TC5. A failure while shaping the response after the commit (`_to_machine_response`) reaches the caller and the machine stays saved, as TC5.

**Errors:** as R2; database errors unchanged.

**Side effects:** the manager's rows, committed. On any error: rolled back.

---

## `MachineService.get_machine(db, machine_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `GET /machines/{id}/`)

**Purpose:** One machine with its current status.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `include_deleted` | bool, default `False` | [BUG-955, BUG-966] new; passed to the manager; reachable from the API |

**Returns:** a `MachineResponse` (`_to_machine_response` with no map).

**Rules:**
- **R1.** A live machine of the workspace in a live factory → its response, as `_to_machine_response` R1, R2, R4. Verified.
- **R2.** [BUG-955] (HR-4) A soft-deleted machine → 404 `Machine with ID <machine_id> not found` by default. *(Today: returned, `is_deleted = True`, HTTP 200. Verified.)*
- **R3.** [BUG-955] With `include_deleted=True` a soft-deleted machine of the workspace is returned with `is_deleted = True` and its last status (a log is history: activity manager `get_latest_status` R5); another workspace's id is still 404. *(Today: `TypeError`. Verified.)*
- **R4.** [BUG-966] A live machine of a soft-deleted factory → the same 404 by default; returned with `include_deleted=True`. *(Today: returned. Verified.)*
- **R5.** Unknown id or another workspace's id → the manager's 404, unchanged. Read only (TC6).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing / other workspace; [BUG-955, BUG-966] hidden without `include_deleted` | `HTTPException` 404 | `Machine with ID <machine_id> not found` |
| R5 of `_to_machine_response` | `ValueError` | — |

**Side effects:** none

---

## `MachineService.get_machines(db, workspace_id, factory_id=None, factory_section_id=None, is_running=None, search=None, maintenance_window="all", has_model_number=None, has_manufacturer=None, latest_event_type=None, sort_by="name", sort_dir="asc", skip=0, limit=100, include_deleted=False)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `GET /machines/`, which passes every parameter except `include_deleted`)

**Purpose:** The machines page.

**Returns:** a `list` of `MachineResponse` (`_to_machine_responses`).

**Rules:**
- **R1.** The machines, their order and paging are exactly `MachineManager.search_machines` for these arguments, all passed through unchanged (manager R1–R21 with their bugs); each is shaped by `_to_machine_responses`. An empty result → `[]` (verified for an empty workspace). With no arguments after `workspace_id` the manager gets the defaults shown in the signature.
- **R2.** [BUG-956] (HR-4) `include_deleted=True` reaches the manager (manager R20, R21, BUG-957): deleted machines are listed with `is_deleted = True`; the default leaves them out. *(Today: no such parameter, `TypeError`; `GET /machines/?include_deleted=true` answers 200 without them. Verified.)*
- **R3.** Read only (TC6).
- **R4.** [BUG-1570] (Q1) At the API, `maintenance_window`, `sort_by` and `sort_dir` accept only their listed values (exact, lower case); anything else is refused by request validation and the service is not called. The service passes whatever it gets (integration-only). *(Today: free text; `bogus`, `createdAt`, `DESC` answer 200. Verified.)*

**Errors:** as the manager (negative `skip` / `limit` → `DataError` when called directly; `latest_event_type` → `AttributeError` until BUG-886 is fixed); `_to_machine_response` R5.

**Side effects:** none

---

## `MachineService.get_upcoming_work(db, *, workspace_id, within_days=7, factory_id=None, include_overdue=False)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `GET /machines/upcoming-work/`, which enforces `1 <= within_days <= 365`)

**Purpose:** Per machine, the open work orders planned within the next days, optionally with overdue ones.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `within_days` | int, default `7` | horizon; not checked here |
| `factory_id` | int or `None` | compared with the **work order's** `factory_id` |
| `include_overdue` | bool, default `False` | `True` moves the window's start back to 1 January 1970 |

**Returns:** a `list` of `MachineUpcomingWorkRow`.

**Rules:**
- **R1.** The window is from `start` to `end` inclusive: `end` = today + `within_days`; `start` = today, or 1970-01-01 with `include_overdue=True`. "Today" is the server's `date.today()` (FU-2). With the default 7: an order planned today and one at +7 count, +8 and yesterday do not (verified). `within_days=0` → only today; a negative `within_days` → `[]` (end before start; verified).
- **R2.** A work order counts when it is of `workspace_id`, not soft-deleted, has a machine and a `planned_date` in the window, and its `status` is `DRAFT` or `IN_PROGRESS`. `COMPLETED` / `VOIDED` orders and orders without a date or machine never count. With `include_overdue=True` an overdue order of either open status counts (unlike the machines page's `overdue`, which counts only `IN_PROGRESS`: machine manager R10).
- **R3.** Orders on a soft-deleted machine never count. `factory_id` given (not `None`) keeps only orders whose own `factory_id` equals it.
- **R4.** One row per machine with at least one counting order: `machine_id`, `name`, `factory_id`, `factory_section_id`, `section_name` (the machine's section, `None` without), `earliest_date`, `count` and `sources.work_orders` (both the number of its counting orders), `items`. Each item: `kind = "work_order"`, `source_id` = the order id, `date` = `planned_date`, `title` = the order's title, or its number when the title is empty, `status`, `work_order_type_name`. Items are sorted by date, then id.
- **R5.** Rows are sorted by `earliest_date`, then name case-insensitively, then `machine_id`. No paging: every counting machine is returned.
- **R6.** [BUG-1571] (HR-16) Only machines of `workspace_id` are joined: a work order of the workspace that names another workspace's machine is left out, and no id, name, factory or section of the other workspace appears. *(Today: listed with the other workspace's machine id, name, factory id and section. Verified, also over HTTP.)*
- **R7.** [BUG-1572] (HR-4; per BUG-890) A live machine whose factory is soft-deleted is left out with all its orders. *(Today: listed. Verified.)*
- **R8.** Read only (TC6); nothing is committed or rolled back.

**Errors:** none of its own.

**Side effects:** none

---

## `MachineService.update_machine(db, machine_id, machine_in, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `PUT /machines/{id}/`)

**Purpose:** Edit or move a machine, save it, and answer with its response.

**Returns:** a `MachineResponse`, committed and re-read before shaping (TC1, TC2), with its current status.

**Rules:**
- **R1.** The machine is changed exactly as `MachineManager.update_machine` changes it (manager spec R1–R30: fields, section, move with its open work orders and their events, activity entry, BUG-950 … BUG-954, BUG-959, BUG-961 … BUG-964, BUG-967, BUG-970 … BUG-972, BUG-975); everything it flushed is committed in one transaction.
- **R2.** The manager's refusals reach the caller unchanged and nothing is saved, also changes the manager flushed before refusing (manager R21) (TC3): 404 `Machine with ID <machine_id> not found`, 400 `Cannot update a deleted machine`, 404 `Factory with ID <factory_id> not found`, [BUG-963] 400 `Cannot move machine to deleted factory`, 409 `Machine with name '<name>' already exists in this factory`, the section's 404 / 400.
- **R3.** Commit and re-read failures follow TC4, TC5; a shaping failure after the commit as `create_machine` R3.

**Errors:** as R2; database errors unchanged.

**Side effects:** the manager's writes, committed. On any error: rolled back.

---

## `MachineService.delete_machine(db, machine_id, workspace_id, user_id)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `DELETE /machines/{id}/`, 200 with the response)

**Purpose:** Soft-delete a machine and answer with it, or tell the user what stops it.

**Returns:** a `MachineResponse` of the soft-deleted machine, committed and re-read: `is_deleted = True`, `is_active = False`, `deleted_by`, `deleted_at` set, its last status kept (verified).

**Rules:**
- **R1.** A machine the manager deletes (manager spec R1–R10, with its `deactivated` activity entry) is committed (TC1), re-read and shaped. The manager's `HTTPException`s reach the caller unchanged, nothing saved (TC3): 404 `Machine with ID <machine_id> not found`, 400 `Machine is already deleted`, [BUG-965] 400 `Cannot delete a machine of a deleted factory`.
- **R2.** [BUG-968] (machine manager FU-1 (a), R4, R4a) When the manager refuses with `ValueError("Machine has stock or open orders", blockers)`, the session is rolled back first (TC3) and the caller gets `app.core.exceptions.ValidationError` with `status_code == 400`, `detail == "Machine has stock or open orders"` (`args[0]`) and `errors` == the blockers (`args[1]`), unchanged: entries `machine_stock`, `purchase_order`, `work_order`, `transfer_order` with their ids, and at most one `{"type": "other_workspace"}`, last. *(Today: a machine with stock is deleted (verified); a `ValueError` would answer 500 (verified with a patched manager).)*
- **R3.** [BUG-968] Only a `ValueError` from the manager's `delete_machine` is translated; anything else, on any method of the service, reaches the caller unchanged (scope per `machine_item_service.spec.md` Q1).
- **R4.** Commit and re-read failures follow TC4, TC5; a shaping failure after the commit as `create_machine` R3.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing / other workspace | `HTTPException` 404 | `Machine with ID <machine_id> not found` |
| already deleted | `HTTPException` 400 | `Machine is already deleted` |
| [BUG-965] factory soft-deleted | `HTTPException` 400 | `Cannot delete a machine of a deleted factory` |
| [BUG-968] in use | `app.core.exceptions.ValidationError` (400) | `Machine has stock or open orders`; `.errors` = blockers |

**Side effects:** the soft delete and its activity entry, committed. On any error: rolled back.

---

## `MachineService.create_machine_event(db, event_in, workspace_id, user_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `POST /machines/{id}/events/`, 201; the endpoint puts the path id into `event_in.machine_id`, D1)

**Purpose:** Record a manual status change and save it.

**Returns:** the manager's `MachineEventResponse`, as built before the commit (no re-read; every field is already set).

**Rules:**
- **R1.** The status change is made exactly as `MachineManager.create_machine_event` makes it with `work_order_id=None` (manager spec R1–R16: activity row, `is_running`, BUG-960, BUG-974); it is committed: the event survives a later rollback (verified). The service never passes a `work_order_id`, so manager R2a / R3a / R9 are reached only through work orders.
- **R2.** The manager's refusals reach the caller unchanged, nothing saved (TC3): 404 `Machine with ID <machine_id> not found`, 400 `Cannot create event for a deleted machine`, [BUG-974] 400 `Cannot create event for a machine of a deleted factory`, 400 `Machine is already in '<STATUS>' state` (verified).
- **R3.** A failing commit follows TC4. There is no re-read, so TC5 does not apply.

**Errors:** as R2; database errors unchanged.

**Side effects:** one activity row and, when it changes, `is_running` / `updated_by` / `updated_at`, committed. On any error: rolled back.

---

## `MachineService.get_machine_activity(db, machine_id, workspace_id, skip=0, limit=100, from_date=None, to_date=None, event_type=None)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `GET /machines/{id}/activity/`, passing every argument)

**Purpose:** A machine's history as the API shows it.

**Returns:** a `list` of `MachineActivityEventResponse`, in the manager's order.

**Rules:**
- **R1.** The entries, their order, filters and paging are exactly `MachineActivityManager.list_events` for these arguments (its R1–R10, BUG-1141), all passed through; one response per entry, in that order.
- **R1a.** (D2) A caller who omits `limit` gets at most **100** entries: with 101 events on the machine and no `skip` / `limit` given, exactly 100 come back, the 100 newest (the oldest is left out). The service's own default is 100, independent of the manager's.
- **R2.** A machine not in the workspace → the manager's 404 `Machine with ID <id> not found`, unchanged (verified). A soft-deleted machine's activity is returned (verified; a log is history).
- **R3.** Each response: `id`, `workspace_id`, `machine_id`, `event_type`, `description`, `performed_by`, `created_at` from the row; `performer_name` = the performer's `name`, `None` without a performer.
- **R4.** ✅ (activity manager Q5) `metadata` is `None` when the stored metadata is falsy (`None`, `{}`; verified for `{}`); otherwise `MachineActivityEventMetadata` built from it: the 10 listed keys, absent ones `None`, any other key dropped (verified: `note` dropped, `quantity` kept). The stored row is not changed.
- **R5.** ✅ (activity manager Q6) A stored metadata the schema cannot read (`quantity: 2.5`, `status: 5`, a list) raises `pydantic.ValidationError`, and the whole call fails. No writer stores one.
- **R6.** Read only (TC6).

**Errors:** the manager's 404; `DataError` for negative `skip` / `limit` when called directly; R5.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 60–70 | `status_map is not None` → map lookup / else `get_latest_status` | `_to_machine_response` R2, R3 |
| 72 | `status_from_activity` | `_to_machine_response` R4 |
| 74–81 | `MachineEventTypeEnum(status_str) if status_str else None`; invalid value raises; `latest.created_at if latest else None` | `_to_machine_response` R4, R5 |
| 91–93 | empty list → `[]`, no read | `_to_machine_responses` R1 |
| 95–107 | one map read; shape each in order | `_to_machine_responses` R2 |
| 125–139 | create: manager → commit → refresh → shape | `create_machine` R1, R3 |
| 141–145 | create: any exception → rollback, re-raise | `create_machine` R2, R3 |
| 157–159 | get: manager positional, no `include_deleted` (BUG-955, BUG-966); shape | `get_machine` R1–R5 |
| 193–219 | list: manager with every argument but `include_deleted` (BUG-956); shape | `get_machines` R1–R4 |
| 243–247 | today; end = today + days; start = 1970-01-01 if `include_overdue` else today | `get_upcoming_work` R1 |
| 249–261 | `machine_work_service.upcoming_work` (open statuses, dated, live machine, workspace on the order only — BUG-1571; factory state not looked at — BUG-1572; `factory_id` on the order; group, sort) | `get_upcoming_work` R2–R8 |
| 275–291 | update: manager → commit → refresh → shape | `update_machine` R1, R3 |
| 293–297 | update: any exception → rollback, re-raise | `update_machine` R2, R3 |
| 311–325 | delete: manager → commit → refresh → shape | `delete_machine` R1, R4 |
| 327–331 | delete: any exception → rollback, re-raise; no `ValueError` translation (BUG-968) | `delete_machine` R1–R4 |
| 349–361 | event: manager (no `work_order_id`) → commit → return | `create_machine_event` R1, R3 |
| 363–367 | event: any exception → rollback, re-raise | `create_machine_event` R2, R3 |
| 381–383 | activity: defaults `skip=0`, `limit=100` | `get_machine_activity` R1a |
| 395–413 | activity: `list_events` with every argument | `get_machine_activity` R1, R2 |
| 415–449 | map each row; `metadata` only if truthy; `performer_name` if profile | `get_machine_activity` R3–R5 |
| 457 | module singleton | Not specified |

## Gap log
G1 (machine_service.verify.md Finding 3) — Fact — the default `limit=100` of `get_machine_activity` written as rule R1a (D2, decided by Claude under the reviewer's delegation (2026-11-04), app_settings precedent ASV-L-09); Branch-map row 381–383 added. No other rule changed.
