# Spec — `app/services/machine_work_service.py`

> **Status:** APPROVED (2026-11-21; no new bugs, no owner questions; decisions D1–D5 decided by Claude under the reviewer's delegation (2026-11-21))
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/machine_service.spec.md`. This service is **read-only**: it never calls `_commit_transaction` / `_rollback_transaction` and calls no manager. TC1–TC5 (`base_service.spec.md`) do not apply; TC6 does (every method). Its outcomes reached from the API were first written as `MachineService.get_upcoming_work` R1–R8 (machine service FU-1); this spec is now their home, and those rules point here. `dates_by_machine` and the three static helpers are reached through `MachineManager.search_machines` (machine manager spec R8–R17, owner O2: overdue counts only `IN_PROGRESS`; BUG-973 date limits live in the manager, not here).
>
> **Existing bugs written as rules here, no new ID:** **BUG-1571** (HR-16, `missing-workspace-scope`) `collect_raw_items` R4, and through it `upcoming_work` and `dates_by_machine`; **BUG-1572** (HR-4, `join-ignores-soft-deleted`) `upcoming_work` R6 only (D2).
>
> **Verified by running** (`v_mws.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2desc\machine_work\`, one outer transaction rolled back against `marker_test`, session as the `db` fixture; nothing persisted): one row per machine, rows by earliest date then name; an empty `title` shows the order number; `COMPLETED`, soft-deleted, undated and machine-less orders and a soft-deleted machine's orders are left out; an inactive machine, a machine of a soft-deleted factory and **another workspace's machine** (W1 order on W2's machine) are listed; a soft-deleted section's name and a soft-deleted work order type's name are shown; `statuses=[]` and `machine_ids=[]` give `[]`; status matching is the exact stored string; `dates_by_machine` keeps duplicate dates, lists the foreign machine and the deleted-factory machine, leaves out the deleted machine and unknown ids, accepts a generator, and gives `{}` for no ids; W2 does not see W1's order on its machine; `end < start` → `[]`; the helpers' boundaries as in their rules; `has_upcoming_in_horizon(..., 10**7)` raises `ValueError` ("year 29405 is out of range"); nothing is left pending and the session's transaction is untouched. **Not run:** the intended behaviour of BUG-1571 / BUG-1572.

## Review
> All items decided by Claude under the reviewer's delegation (2026-11-21). None is the owner's answer; none touches money, stock, an order workflow decision or who may see or do what (BUG-1571 is HR-16, already decided by the owner on 2026-10-30).

### House-rule violations — applied automatically
- **HR-16** `collect_raw_items` R4 — the work order is filtered by workspace, its machine is not. Already logged as **BUG-1571** (machine service spec); applies here to every method built on it, including `dates_by_machine` when given another workspace's machine id.
**Answer:** bug — per HR-16 (house rule) → existing BUG-1571, no new ID
- **HR-4** `upcoming_work` R6 — a live machine of a soft-deleted factory is listed. Already logged as **BUG-1572**.
**Answer:** bug — per HR-4 (house rule) → existing BUG-1572, no new ID; scope per D2

### Decisions
### D1. BUG-1571 also reaches the machines page's date lookup — decided
**Background:** `dates_by_machine` returns, per machine id it is given, the planned dates of that workspace's open work orders. `MachineManager.search_machines` passes only its own workspace's machines.
**What happens today:** called directly with another workspace's machine id, it returns the dates of the caller's orders that name that machine (verified). Through the API this cannot show, because the manager never passes a foreign id.
**Example:** workspace A has a work order dated 21 Nov naming workspace B's machine 77; `dates_by_machine(workspace A, [77])` gives `{77: [21 Nov]}`.
**Rules affected:** `collect_raw_items` R4, `dates_by_machine` R3
**Answer:** bug — same fix as BUG-1571 (the machine must be of `workspace_id`), no new ID. Decided by Claude under the reviewer's delegation (2026-11-21).

### D2. Deleted-factory machines: left out of the upcoming-work panel only — decided
**Background:** BUG-1572 says the upcoming-work panel must leave out machines of a soft-deleted factory, and its register row names `collect_raw_items` as the place to fix it. But `collect_raw_items` also feeds `dates_by_machine`, and the approved machine manager spec R8 / R21 (BUG-957) says a machine of a soft-deleted factory listed with `include_deleted=True` keeps its work dates, like any live machine.
**What happens today:** both paths keep such machines.
**Example:** factory "Old Plant" is deleted; its machine "Press 2" has a draft dated tomorrow. The upcoming-work panel should not show Press 2 (BUG-1572); the machines page with "show deleted" and "next 7 days" should still list it (manager R21).
**Rules affected:** `upcoming_work` R6, `collect_raw_items` R5, `dates_by_machine` R3
**Answer:** the factory-state filter belongs to `upcoming_work` (or a flag of `collect_raw_items` that only `upcoming_work` sets); `collect_raw_items` by default and `dates_by_machine` keep machines of soft-deleted factories. BUG-1572's register row should say so (reported to the caller; `bugs.md` not edited here). Decided by Claude under the reviewer's delegation (2026-11-21).

### D3. A machine in a soft-deleted section shows that section's name — decided
**Background:** a machine's section is an optional label; once BUG-908 is fixed, deleting a section keeps its machines' links (hidden as members, back on restore). `MachineResponse` shows the same section id and name (machine service `_to_machine_response` R1, approved without a bug) and machine manager R19 (BUG-971) keeps such links on edit.
**What happens today:** the upcoming-work row shows `factory_section_id` and `section_name` of the deleted section (verified).
**Example:** section "Line B" is deleted; machine "Lathe 1" still shows "Line B" in the panel, as on its own page.
**Rules affected:** `upcoming_work` R3
**Answer:** intended — same as the machine page; no bug. Decided by Claude under the reviewer's delegation (2026-11-21).

### D4. A work order whose type was soft-deleted still shows the type's name — decided
**Background:** work order types are soft-deleted; an order keeps its `work_order_type_id`.
**What happens today:** the item shows the deleted type's name (verified).
**Example:** type "Servicing" is deleted; a draft of that type still shows "Servicing".
**Rules affected:** `upcoming_work` R4
**Answer:** intended — the order's own label, as history; no bug. Decided by Claude under the reviewer's delegation (2026-11-21).

### D5. Unreachable guards in `upcoming_work` / `dates_by_machine` — decided
**Background:** the query is an inner join with `machine_id IS NOT NULL` and `planned_date IS NOT NULL`, so every returned order has a machine and a date.
**What happens today:** `if machine is None: continue` (line 117–118) and the four `assert`s (lines 99, 167, 168) can never fire.
**Example:** —
**Rules affected:** none (Not specified)
**Answer:** remove — `if machine is None: continue` is dead code; the asserts are harmless type hints, left alone. Decided by Claude under the reviewer's delegation (2026-11-21); the caller adds line 117–118 to `dead-code-removal-checklist.md`.

Checked and **not** violated: **HR-1 … HR-3, HR-8, HR-9** — no names written, no text search, no audit stamps. **HR-5** — every filter is in the query; there is no paging. **HR-6** — rows are sorted by earliest date, then name case-insensitively, then machine id; items by date then order id; dates ascending: all stable. **HR-7** — no `limit`. **HR-10** — read-only. **HR-11 … HR-15** — no external system, no money. **HR-4** — soft-deleted work orders and machines are left out; the factory is BUG-1572; section and type labels per D3, D4.

**Permission checks:** none (any member of the workspace; the endpoint only resolves the workspace).
**Production / projects:** not touched.

## Overview
`MachineWorkService` is the one definition of "upcoming machine work": open work orders (`DRAFT`, `IN_PROGRESS`) with a planned date, on a live machine, in a date window. `MachineService.get_upcoming_work` (`GET /machines/upcoming-work/`) uses `upcoming_work` for the per-machine panel; `MachineManager.search_machines` (`GET /machines/?maintenance_window=…` and `sort_by=maintenance_date`) uses `dates_by_machine` and the three static date helpers. It writes nothing and ends no transaction.

**Callables:** 6 specified · 2 not specified
**Externals to mock:** none. "Today" is never read here: callers pass `start`, `end`, `today`, `from_date`.
**Integration-only behavior:** none.

**Facts for the test designer**
- Import: `from app.services.machine_work_service import MachineWorkService, machine_work_service`. `MachineWorkService()` takes no arguments. Every argument after `db` of the three query methods is keyword-only. The three helpers are `@staticmethod`s, positional.
- Rows: `Factory(workspace_id, name, abbreviation)`, `Machine(workspace_id, factory_id, name)`, `FactorySection(workspace_id, factory_id, name)`, `MachineSectionAssignment(workspace_id, machine_id, factory_section_id)`, `WorkOrderType(workspace_id, name)`, `WorkOrder(workspace_id, work_order_number, work_order_type_id, title, factory_id, machine_id, planned_date, status)`; `title` and `work_order_number` are NOT NULL (`""` is allowed for `title`); `status` is a plain string column (any text can be stored directly).
- Schemas (`app/schemas/machine_work.py`): `MachineUpcomingWorkItem(kind, source_id, date, title, status, work_order_type_name)`, `MachineUpcomingWorkSources(work_orders)`, `MachineUpcomingWorkRow(machine_id, name, factory_id, factory_section_id, section_name, earliest_date, count, sources, items)`.

**Notes for the test designer**
- TC6: assert a row flushed but not committed before the call is still pending after it (`obj in db` / re-select inside the same transaction) and that a raised error (none of its own; e.g. the helper's `ValueError`) is not wrapped.
- BUG-1571: a second workspace W2 with its own factory and machine, and a W1 work order with W2's machine id; assert W2's machine id and name appear nowhere → strict xfail. BUG-1572: a factory with `is_deleted=True` holding a live machine with a `DRAFT` order in the window → strict xfail on `upcoming_work`; on `dates_by_machine` the same machine keeps its date (passes today and after the fix, D2).
- (G1) Soft delete: the service reads only `is_deleted` on `work_orders`, `machines` and (per BUG-1572, intended) `factories`; it reads no soft-delete column of `factory_sections` or `work_order_types` (D3, D4). `deleted_at` / `deleted_by` (nullable, on all five tables) and `is_active` change nothing here, so a case may set them or not. Other NOT NULL columns without a default: `factories.abbreviation`; none on `machines`, `factory_sections`, `work_order_types`, `machine_section_assignments` beyond those listed above (`created_by` is nullable everywhere; `priority`, `uses_inventory`, `is_running`, `is_active`, `is_deleted` have defaults).
- (G2) "Loaded" in `collect_raw_items` Returns means the relationships `Machine.section_assignment` (one or `None`) and `MachineSectionAssignment.factory_section` are filled by the same query: check with `sqlalchemy.inspect(machine).unloaded` not containing `"section_assignment"` and, for an assigned machine, `inspect(machine.section_assignment).unloaded` not containing `"factory_section"`.
- (G3) `has_upcoming_in_horizon` R3: the message is Python's own, `"year <Y> is out of range"`, where `<Y>` depends on `today`; assert the type `ValueError` and that the message contains `"out of range"`.
- The legacy `tests/test_machine_work_service.py` patches `collect_raw_items`; it is not part of this pipeline.

## Not specified
- `MachineWorkService` class body; module constants `_OPEN_WO_STATUSES` (`"DRAFT"`, `"IN_PROGRESS"`) and `_SECTION_EAGER` (eager-loads the section; no observable effect beyond `upcoming_work` R3).
- `upcoming_work` line 117–118 `if machine is None: continue` — dead code, to be removed (D5). The `assert`s at lines 99, 167, 168 — unreachable (D5).
- `has_upcoming_work` — already deleted as dead code (checklist).

---

## `MachineWorkService.collect_raw_items(db, *, workspace_id, start, end, factory_id=None, machine_ids=None, statuses=None)`
**Shape:** list
**Persistence:** reads
**Visibility:** internal (used by: `upcoming_work`, `dates_by_machine`; no other caller)

**Purpose:** The matching work orders, each paired with its machine.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | compared with the work order's `workspace_id` only |
| `start`, `end` | `date` | inclusive window on `planned_date`; not checked (end before start → nothing) |
| `factory_id` | int or `None` | `None` = no filter; compared with the **work order's** `factory_id` |
| `machine_ids` | sequence of int or `None` | `None` = no filter; `[]` → nothing matches |
| `statuses` | sequence of str or `None` | `None` = `("DRAFT", "IN_PROGRESS")`; exact string match; `[]` → nothing matches |

**Returns:** a `list` of SQLAlchemy `Row` objects of two elements `(WorkOrder, Machine)` (G4), in no defined order. Callers may rely on indexing (`row[0]`, `row[1]`), unpacking (`for wo, machine in rows`), `len(row) == 2`, and equality with the plain tuple `(wo, machine)`; they may not rely on `type(row) is tuple` (it is not; the annotation `list[tuple[...]]` is loose, not a promise). Intended, not a bug; the machine's `section_assignment` and that assignment's `factory_section` are loaded by the same query (G2).

**Rules:**
- **R1.** An order is returned when it is of `workspace_id`, `is_deleted = False`, has a `machine_id`, has a `planned_date` with `start <= planned_date <= end`, and its `status` is one of the statuses. Soft-deleted, undated and machine-less orders are never returned. With the default statuses `COMPLETED` / `VOIDED` orders are not returned. `end` before `start` → `[]`.
- **R2.** Statuses are matched as exact stored strings: `statuses=["IN_PROGRESS"]` matches `IN_PROGRESS` only; `statuses=[]` → `[]`. An unknown string raises nothing.
- **R3.** Orders on a soft-deleted machine are never returned. The machine's `is_active` is not looked at (an inactive machine's orders are returned).
- **R4.** [BUG-1571] (HR-16; D1) Only orders whose machine is of `workspace_id` are returned; an order naming another workspace's machine is left out. *(Today: returned with that machine.)* Seen from the machine's own workspace, such an order is never returned (it belongs to the other workspace) — holds today.
- **R5.** (D2) The machine's factory state is not looked at: a live machine of a soft-deleted factory is returned with its orders. (Holds today and stays so; BUG-1572 is applied in `upcoming_work` R6.)
- **R6.** `factory_id` given keeps only orders whose own `factory_id` equals it (an order of factory F1 on a machine now in F2 follows the order; BUG-975 keeps them equal). `machine_ids` given keeps only orders on those machines; unknown ids match nothing and raise nothing.
- **R7.** Read only (TC6).

**Errors:** none of its own.

**Side effects:** none.

---

## `MachineWorkService.upcoming_work(db, *, workspace_id, start, end, factory_id=None, machine_ids=None)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `MachineService.get_upcoming_work` ← `GET /machines/upcoming-work/`, which never passes `machine_ids`)

**Purpose:** Per machine, its open work orders in the window.

**Inputs:** as `collect_raw_items`, without `statuses` (always `DRAFT`, `IN_PROGRESS`).

**Returns:** a `list` of `MachineUpcomingWorkRow`.

**Rules:**
- **R1.** The orders considered are those of `collect_raw_items` R1–R6 with the default statuses, plus R6 below. No order → `[]`.
- **R2.** One row per machine with at least one such order. `count` and `sources.work_orders` both equal the number of its orders.
- **R3.** The row shows the machine's own values: `machine_id`, `name`, `factory_id` (the machine's, not the order's), `factory_section_id` and `section_name` of its section assignment, both `None` when it has none; a soft-deleted section is still shown (D3).
- **R4.** Each order is one item: `kind = "work_order"`, `source_id` = order id, `date` = `planned_date`, `title` = the order's `title`, or its `work_order_number` when `title` is `""`, `status` = the stored status, `work_order_type_name` = the type's name (also when the type is soft-deleted, D4).
- **R5.** Items are sorted by date, then order id; `earliest_date` is the first item's date. Rows are sorted by `earliest_date`, then `name` case-insensitively, then `machine_id`. Every row is returned (no paging).
- **R6.** [BUG-1572] (HR-4; per BUG-890; D2) A live machine whose factory is soft-deleted is left out with all its orders; an inactive-but-live factory hides nothing. *(Today: listed.)*
- **R7.** Read only (TC6).

**Errors:** none of its own.

**Side effects:** none.

---

## `MachineWorkService.dates_by_machine(db, *, workspace_id, machine_ids, start, end, statuses=None)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `MachineManager.search_machines`, twice: default statuses, and `("IN_PROGRESS",)` for overdue)

**Purpose:** Each machine's planned work dates in the window.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `machine_ids` | any iterable of int | read once (a generator works); empty → `{}` |
| others | | as `collect_raw_items` (`factory_id` not available) |

**Returns:** a `dict` machine id → `list` of `date`, ascending.

**Rules:**
- **R1.** No machine ids → `{}`, without reading the database.
- **R2.** Otherwise the dates are the `planned_date`s of `collect_raw_items` R1–R6 for those machines and statuses, one entry per order: two orders on the same day give that date twice. Each list is sorted ascending.
- **R3.** Only machines with at least one date are keys: unknown ids, soft-deleted machines and machines with no matching order are absent. A machine of a soft-deleted factory keeps its dates (D2). [BUG-1571] Another workspace's machine is absent (D1). *(Today: present with the caller's orders on it.)*
- **R4.** Read only (TC6).

**Errors:** none of its own.

**Side effects:** none.

---

## `MachineWorkService.earliest_upcoming_on_or_after(dates, from_date)`
**Shape:** compute · **Persistence:** pure · **Visibility:** public (used by: `MachineManager.search_machines`)

**Rules:**
- **R1.** Returns the earliest date that is on or after `from_date` (a date equal to `from_date` counts); earlier dates are ignored.
- **R2.** No such date (or `dates` empty) → `None`.

---

## `MachineWorkService.has_overdue(dates, today)`
**Shape:** compute · **Persistence:** pure · **Visibility:** public (used by: `MachineManager.search_machines`, with `IN_PROGRESS` dates only, owner O2)

**Rules:**
- **R1.** `True` when any date is strictly before `today`; a date equal to `today` is not overdue; empty → `False`.

---

## `MachineWorkService.has_upcoming_in_horizon(dates, today, horizon_days)`
**Shape:** compute · **Persistence:** pure · **Visibility:** public (used by: `MachineManager.search_machines`, with 7 and 30)

**Rules:**
- **R1.** `True` when any date is from `today` to `today + horizon_days` inclusive (horizon 7: +7 yes, +8 no; a past date no); empty → `False`.
- **R2.** `horizon_days = 0` → only `today` counts; a negative horizon → `False`.
- **R3.** A horizon that takes the end past the last representable date raises `ValueError` with a message containing `out of range` (e.g. `10**7` days; exact text varies with `today`, G3; unreachable from the callers, which pass 7 and 30).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 46 | `statuses is None` → default open statuses / given list | `collect_raw_items` R1, R2 |
| 48–49 | inner join to the machine, no machine-workspace check | `collect_raw_items` R4 |
| 52–59 | workspace, not deleted, machine set, status, date set, window, machine not deleted | `collect_raw_items` R1, R3 |
| — | no factory-state filter | `collect_raw_items` R5; `upcoming_work` R6 |
| 62–63 | `factory_id is not None` | `collect_raw_items` R6 |
| 64–65 | `machine_ids is not None` (incl. `[]`) | `collect_raw_items` R6, R2 |
| 97 | loop over no / one / many orders | `upcoming_work` R1, R2 |
| 99 | `assert mid is not None` — unreachable | Not specified (D5) |
| 108 | `title or work_order_number` | `upcoming_work` R4 |
| 117–118 | `machine is None` — dead | Not specified (D5) |
| 120–121 | item sort, earliest | `upcoming_work` R5 |
| 138 | row sort | `upcoming_work` R5 |
| 153–154 | no ids → `{}` | `dates_by_machine` R1 |
| 166–169 | loop over orders; asserts unreachable | `dates_by_machine` R2; D5 |
| 171–172 | sort each list | `dates_by_machine` R2 |
| 177–178 | some / no date on or after | `earliest_upcoming_on_or_after` R1, R2 |
| 182 | any strictly before | `has_overdue` R1 |
| 186 | end date; overflow | `has_upcoming_in_horizon` R1–R3 |
| 187 | any in `[today, end]` | `has_upcoming_in_horizon` R1, R2 |

## Gap log
G1 (machine_work_service.cases.md gap 1) — fact — Notes: only `is_deleted` is read (work orders, machines; factories per BUG-1572); `deleted_at` / `deleted_by` / `is_active` irrelevant; the only extra NOT NULL column without default is `factories.abbreviation`.
G2 (machine_work_service.cases.md gap 2) — fact — Returns of `collect_raw_items` names `Machine.section_assignment` and `MachineSectionAssignment.factory_section`; Notes give the `sqlalchemy.inspect(...).unloaded` check.
G3 (machine_work_service.cases.md gap 3) — fact — `has_upcoming_in_horizon` R3 fixes the assertion: `ValueError`, message contains `out of range` (Python's text, varies with `today`).
G4 (executor notes, MWS-CR-01) — fact — `collect_raw_items` Returns: the items are SQLAlchemy `Row`s, not `tuple`s; restated as what callers can rely on (indexing, unpacking, length 2, equality with the plain tuple). Both callers only unpack. Intended, no bug; decided by Claude under the reviewer's delegation (2026-11-22).
