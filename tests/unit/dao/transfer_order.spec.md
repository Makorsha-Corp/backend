# Spec — `app/dao/transfer_order.py`

> **Status:** APPROVED (2026-11-11; nothing open — OQ-39, OQ-40 answered by the owner: BUG-2659, BUG-2660; case designer's gaps closed, Gap log at the end)
> **Source commit:** e48a092

> **Review round 2026-11-10 (describe + delegated decisions).** No owner answer in this round. Everything below the owner questions is **decided by Claude under the reviewer's delegation (2026-11-10)** (filters, ordering, numbering mechanics, clocks, dead code) and none of it is the owner's own answer. Precedents reused: BUG-726 (numbers unique per workspace), BUG-727 (race-free numbering), BUG-1333 (numbers sorted as text), BUG-1334 (year from the local clock), BUG-1211 / BUG-638 (line-number ties), the machine activity event spec Q3 (date filters use UTC days, intended), the item orders service spec (order history names deleted locations, intended), the orders overview service spec `_filter_transfer_by_factory` R1 (a transfer belongs to the factory at either end).

> **Review round 2026-11-11 (apply-review + fill-gaps).** **Owner (2026-11-11):** OQ-39 — suggested answer: "Planned" needs a route **and** at least one line, otherwise Draft, as the order page → 🐞 BUG-2659; OQ-40 — suggested answer: the hub's status ticks match the order's current stage → 🐞 BUG-2660. **Delegated (decided by Claude under the reviewer's delegation, 2026-11-11):** the number prefix is matched case-sensitively, intended (G3; as the sales order / delivery / return specs); the stage ticks of BUG-2660 compare status names trimmed and case-insensitively (a filter detail). The cards that build a workspace-1 order pointing at another workspace's rows (HF-38…40, FF-12/13) stay as "invalid data must not leak" read checks (HR-16: such rows are invalid data, and the reads must not let them match or show). **Gaps:** all five gaps of `transfer_order.cases.md` closed from the code (Gap log at the end).

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated (`create`, `update`, `remove`, `get` are inherited and used by `TransferOrderManager`; `TransferOrderItemDAO` inherits `create`, `update`, `remove`).
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Raw lookups stay raw (HR-4 scope; neither table has a soft-delete column). HR-16: every query here filters on the row's own `workspace_id`, and the name lookups used by the factory filter and the search are scoped to the same workspace; refusing a foreign link on write is the manager's job (BUG-1018). HR-10: this DAO reads without a row lock; the completion lock is BUG-821 (manager), not a rule here. HR-15: no money here; quantities are `Numeric(15, 2)` and Postgres rounds half away from zero (verified `1.005` → `1.01`).
>
> **Verified by running** (my own scripts `hc.py`, `v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdao\transfer_order\`, one transaction on `marker_test`, rolled back, private `COVERAGE_FILE`; nothing committed): the tables' indexes (a **global** unique index `ix_transfer_orders_transfer_number`; no unique index on line numbers); numbering in an empty workspace (`TR-2026-001`), after five orders (`-006`), in a second workspace (`TR-2026-001` again, whose insert then fails with `IntegrityError` 23505 on the global index), after `-999` and `-1000` (`-1000` again), after a suffix `abc` (`-001`); the factory filter (destination factory wins; source only when the destination type is not a known one); the search over number, location type, factory / machine / component names, trimmed, case-insensitive, `_` and `%` matching everything, a name of another workspace not matching, whitespace-only = no search; `exclude_complete` default and off; hub stats with and without completed orders and for an empty workspace (`(0, 0, 0)`); "recent" with one edited order (never-edited orders come **first**); pending highlights (labels `Planned` / `Draft`, an order with no lines counted `Planned`); a `date_to` covering 23:59:59.999999; `status_ids = []` = no filter; `source_location_type` case-sensitive; touching / inbound lists; `get_by_id_and_workspace` from another workspace (`None`); item lines with tied line numbers, another workspace, empty id list. **Read, not run:** `TransferOrderManager`, `TransferOrderService`, `InventoryManager.get_incoming_summary_for_factory`, `PurchaseOrderService` (location's active orders), `AttachmentManager`, `GET /transfer-orders/`, `GET /transfer-orders/stats/`, the web app's transfer hub (`TransferOrdersPage.tsx`, `transferOrderHubApiParams.ts`, `TransferOrderPendingActions.tsx`, `transferOrderMilestones.ts`). **Not run:** anything over HTTP; two concurrent transactions; a patched clock (the year is read through a function-local `from datetime import datetime`).

## Review
> Delegated items applied 2026-11-10. Owner questions OQ-39, OQ-40 answered and applied 2026-11-11.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| OQ-39 | The hub counts an order with a route but no lines as "Planned"; the order page calls it "Draft" | bug — Planned needs a route **and** a line (BUG-2659) | owner, 2026-11-11 |
| OQ-40 | The hub's status filter compares the status stored at creation, which never changes | bug — filter by the order's stage (BUG-2660) | owner, 2026-11-11 |
| P1 | Transfer numbers are unique across all workspaces | bug — per workspace (BUG-2650) | Claude, delegated |
| P2 | The "last" number is found by text order: numbering breaks after 999 | bug — numerically highest (BUG-2651) | Claude, delegated |
| P3 | Two creates at once can compute the same number | bug — race-free (BUG-2652) | Claude, delegated |
| P4 | The year in a number comes from the server's local clock | bug — from UTC (BUG-2653) | Claude, delegated |
| Q1 | The factory filter shows a transfer only under its destination's factory | bug — either end (BUG-2658) | Claude, delegated |
| Q2 | "Recent" and the pending samples put never-edited orders first | bug — by last activity (BUG-2655) | Claude, delegated |
| Q3 | `get_by_workspace` has no caller | remove | Claude, delegated |

Decided by house rules: hub search wildcards (BUG-2654), timestamp ties with no `id` tie-break (BUG-2656), line-number ties (BUG-2657).

### House-rule violations — applied automatically

- **HR-8** `_apply_transfer_order_hub_filters` R10 — the trimmed search text goes into `ILIKE '%…%'` unescaped: `_` or `%` alone matches every order (verified: five of five); `beta_` matches `Beta_Works` and would match `Betax…`. Intended: `%`, `_` and `\` match literally.
**Answer:** bug — per HR-8 (house rule)
**Resolution:** 🐞 BUG-2654 (pattern `unescaped-like-wildcards`, as BUG-745 for the expense hub). Rules: `_apply_transfer_order_hub_filters` R10a.
- **HR-6** `list_recent_for_hub` R2, `get_pending_highlights_for_hub` R4, R6, `list_touching_location_incomplete` R3, `list_inbound_to_storage_incomplete` R3 — sorted by a timestamp with no `id` tie-break; orders created in one transaction or one clock tick come back in no fixed order (the top-3 / top-5 / top-10 cut can then change between calls). Intended: ties broken by `id`, in the same direction as the timestamp (newest first → `id` descending; oldest first → `id` ascending).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2656 (pattern `tied-timestamp-no-tiebreak`, as BUG-1200). Rules: those listed (tagged).
- **HR-6** `TransferOrderItemDAO.get_by_order` R2, `get_by_transfer_order_ids` R3 — ordered by `line_number` only; line numbers are not unique (no index; `add_item` takes max + 1 with no lock, so two concurrent adds give one number twice; verified two rows with line 1 are both returned in no fixed order). Intended: ties broken by `id` ascending (BUG-1211 precedent).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2657 (pattern `unordered-pagination`). Rules: those listed (tagged).

Checked and **not** a new line here: **HR-4** — neither table has a soft-delete column. The factory filter and the search still match a soft-deleted factory, machine or project's component: they name the order's own route, which is order history (item orders service precedent, orders overview `_filter_transfer_by_factory` R3); decided by Claude under the reviewer's delegation (2026-11-10), intended. **HR-5** — all filters are in the query before `OFFSET` / `LIMIT`. **HR-7** — `GET /transfer-orders/` requires `1 <= limit <= 100`; the stats call uses fixed limits. **HR-9** — no audit stamp written here (`updated_at` is the model's `onupdate`; `updated_by` is the manager's). **HR-10** — reads only; the completion race is BUG-821 (manager). **HR-15** — no money; quantities rounded by Postgres half away from zero. **HR-16** — every query filters on its own `workspace_id`; the subqueries for machines, components and names are scoped to the same workspace (verified: another workspace's factory name finds nothing).

### Owner questions — answered by the owner (2026-11-11), recorded in `docs/testing/owner-questions.md`

### OQ-39. The hub counts an order with a route but no lines as "Planned" — 🐞 BUG-2659
**Background:** A transfer order has no real workflow status (OQ-40). Its stage is worked out from the order: the web app's order page (`deriveTransferOrderStage`) says **Draft** until the route (both ends) is set **and** at least one line is added, then **Planned**, then **Completed** once marked complete. The hub's "Pending actions" box (`get_pending_highlights_for_hub`) only looks at the route.
**What happens today:** An order with a route and no lines is counted and listed under "In Planned"; only an order with no route is "Awaiting setup" / "Oldest draft". (Verified: three orders with a route and no lines all `Planned`.)
**Example:** A storekeeper creates TR-2026-014 from Factory A storage to Press 9 and is called away before adding lines. The order page shows it as **Draft**; the hub's "In Planned" box counts it and lists it with the label "Planned", and "Awaiting setup" does not mention it, although it cannot be approved or completed ("Add at least one item before completing").
**Rules affected:** `get_pending_highlights_for_hub` R2a, R3, R5
**Suggested answer:** bug — "Planned" needs a route **and** at least one line, as the order page; an order lacking either is "Draft" (awaiting setup, oldest drafts).
**Answer:** owner, 2026-11-11: suggested answer → BUG-2659
**Resolution:** 🐞 BUG-2659 (pattern `stage-rule-differs-from-page`). An order counts as Planned when its route is defined and it has at least one line of its own workspace; otherwise it is Draft (awaiting setup, oldest drafts). Rules: `get_pending_highlights_for_hub` R2a (tagged), R3, R5.

### OQ-40. The hub's status filter compares the status stored at creation, which never changes — 🐞 BUG-2660
**Background:** Every transfer order stores `current_status_id`. It is set once at creation (today the fixed id 1, BUG-1018) and never changes: an edit that sends it is refused ("Status is derived from workflow state — use Mark complete instead"), and marking complete sets `completed_at` only. The web app's status filter offers the workspace's statuses named Draft, Planned and Completed and sends their ids as `status_ids`. Which status a new order should get is the owner's boxed question O2 (status DAO spec); this question is only about the filter.
**What happens today:** `status_ids` keeps orders whose stored status id is in the list (R4), so the filter has nothing to do with the stage the page shows.
**Example:** A workspace has statuses Draft (id 31), Planned (id 32), Completed (id 33). All its orders were created with status id 1. The user ticks "Planned" on the hub: the list, the counts and the KPI tiles all go to 0, although eight orders show "Planned" on their pages. Ticking "Completed" with "show complete orders" on also shows nothing.
**Rules affected:** `_apply_transfer_order_hub_filters` R4, R4a
**Suggested answer:** bug — the filter matches the order's stage: a ticked status named Draft / Planned / Completed keeps orders in that stage (Draft and Planned as OQ-39; Completed = `completed_at` set); a ticked status of any other name matches nothing. When O2 is decided and the system keeps `current_status_id` in step with the stage, the filter can go back to the stored id.
**Answer:** owner, 2026-11-11: suggested answer → BUG-2660
**Resolution:** 🐞 BUG-2660 (pattern `dead-status-value`, as BUG-635: the stored value never moves, so the filter derives the stage at query time). Name comparison trimmed and case-insensitive, decided by Claude under the reviewer's delegation (2026-11-11). Rules: `_apply_transfer_order_hub_filters` R4 (tagged), R4a (tagged).

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-10)

### P1. Transfer numbers are unique across all workspaces — 🐞 BUG-2650
**Background:** Numbers are counted per workspace (each workspace starts at `TR-<year>-001`), but the table has a unique index on `transfer_number` alone. BUG-726 ruled the same a bug for sales orders.
**What happens today:** The first transfer order of the year in any workspace but the first one to number is computed as `TR-2026-001`, which already exists in the other workspace; the insert fails with `IntegrityError` 23505 (verified). The next attempt computes the same number, so the workspace can never create a transfer order that year.
**Example:** Workspace A has TR-2026-001…007. Workspace B creates its first transfer order: 500 (until the global index is fixed) — every time.
**Rules affected:** `get_next_number` R5
**Answer:** bug — per BUG-726 precedent: numbers are unique per workspace (unique index on `(workspace_id, transfer_number)` instead of the global one)
**Resolution:** 🐞 BUG-2650 (pattern `unscoped-uniqueness-constraint`; fix is a migration). Rules: `get_next_number` R5 (tagged).

### P2. The "last" number is found by text order — 🐞 BUG-2651
**Background:** The next number is the highest existing number of the workspace and year, by `ORDER BY transfer_number DESC`, plus one. Numbers are text, so `TR-2026-999` sorts above `TR-2026-1000`, and a suffix with letters sorts above all digits. BUG-1333 ruled the same a bug for batch numbers.
**What happens today:** After `-999` and `-1000` exist, the next number is `-1000` again (verified) and every create fails on the unique index until the new year. With a stored `TR-2026-abc` the next number is `-001` (verified), which also exists.
**Example:** A busy workspace makes its 1001st transfer order of 2026: rejected, and so is every one after it.
**Rules affected:** `get_next_number` R3, R4
**Answer:** bug — per BUG-1333 precedent: the next number is the numerically highest all-digit suffix of that workspace and year, plus one; a suffix that is not all digits is ignored
**Resolution:** 🐞 BUG-2651 (pattern `text-sorted-sequence-number`). Rules: `get_next_number` R3, R4 (tagged).

### P3. Two creates at once can compute the same number — 🐞 BUG-2652
**Background:** The number is read, then the order is inserted later by the manager, with no lock or sequence. BUG-727 ruled the same a bug.
**What happens today:** Two transfer orders created at the same moment in one workspace both get `TR-2026-008`; the second fails at flush with `IntegrityError`.
**Example:** Two storekeepers press "Create" together; one of them gets an error and loses the form.
**Rules affected:** `get_next_number` R6
**Answer:** bug — per BUG-727 precedent: number generation is race-free (e.g. a per-workspace, per-year counter row read `FOR UPDATE`, or a retry on unique violation); both creates succeed with distinct numbers
**Resolution:** 🐞 BUG-2652 (pattern `count-then-insert-race`). Rules: `get_next_number` R6 (tagged).

### P4. The year in a number comes from the server's local clock — 🐞 BUG-2653
**Background:** The year is `datetime.now().year`, the local time of the machine running the API; `created_at` is UTC. BUG-1334 / BUG-2440 ruled the same a bug.
**What happens today:** Around New Year a server in another time zone than UTC numbers with its local year.
**Example:** Server on `Asia/Dhaka`; an order saved at 20:00 UTC on 31 December 2026 is `TR-2027-001` while its `created_at` says 2026.
**Rules affected:** `get_next_number` R1
**Answer:** bug — per BUG-1334 precedent: the year comes from `utcnow()`
**Resolution:** 🐞 BUG-2653 (pattern `local-clock-instead-of-utc`). Rules: `get_next_number` R1 (tagged).

### New questions — decided by Claude under the reviewer's delegation (2026-11-10)

### Q1. The factory filter shows a transfer only under its destination's factory — 🐞 BUG-2658
**Background:** The hub's factory filter (`factory_id`, also used by the hub KPI tiles) decides which factory a transfer belongs to: storage / damaged → that factory; machine → the machine's factory; project → the factory of the component's project. Today it uses the **destination** only, and falls back to the source only when the destination type is not one of the four known types. The orders overview (`_filter_transfer_by_factory` R1, approved) keeps a transfer at either end.
**What happens today:** A transfer from Factory A's storage to a machine in Factory B is shown under B, not under A (verified). Factory A's hub does not show stock leaving it.
**Example:** Factory A's manager filters the hub on A to see what is leaving the store this week: none of the outgoing transfers appear; the overview page, filtered on A, counts them.
**Rules affected:** `_apply_transfer_factory_filter` R1–R3
**Answer:** bug — a transfer is kept when **either** end belongs to the factory (same mapping per location type), once
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): 🐞 BUG-2658 (pattern `filter-ignores-one-end`). It is a filter, not a stock rule; counts per factory on the hub then match the overview. Rules: `_apply_transfer_factory_filter` R1a (tagged), R2, R3.

### Q2. "Recent" and the pending samples put never-edited orders first — 🐞 BUG-2655
**Background:** `updated_at` is empty until an order is first edited (`onupdate` only). Postgres sorts empty values **first** in a descending sort.
**What happens today:** "Recent orders" (`ORDER BY updated_at DESC, created_at DESC`) lists every never-edited order before any edited one, so an order edited a minute ago comes after one created last year and never touched (verified). The "In Planned" and "Awaiting setup" samples (top 3 by `updated_at DESC`) do the same.
**Example:** The hub's "Recent" box shows ten old untouched drafts; the order the user just completed is not in it.
**Rules affected:** `list_recent_for_hub` R2, `get_pending_highlights_for_hub` R4
**Answer:** bug — sort by last activity, `updated_at` or else `created_at` (`COALESCE`), newest first, then `id` descending
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): 🐞 BUG-2655 (pattern `unordered-pagination`). Rules: `list_recent_for_hub` R2, `get_pending_highlights_for_hub` R4 (tagged).

### Q3. `get_by_workspace` has no caller — 🗑️ removed
**Background:** `TransferOrderDAO.get_by_workspace` overrides the base method (status loaded, newest `created_at` first, no `id` tie-break). Its only caller is `TransferOrderManager.list_transfer_orders`, which nothing calls (`GET /transfer-orders/` goes through the hub list).
**What happens today:** Unreachable from the API, `app/`, `scripts/` and `tests/`.
**Example:** Deleting the override changes no response.
**Rules affected:** none (moved to Not specified)
**Answer:** remove — per the subscription plan DAO precedent: no caller, dead code
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-10): Not specified, dead-code checklist. No bug ID. The manager's `list_transfer_orders` is FU-2.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | `transfer_order_manager.spec.md` (`create_transfer_order`) | The number comes from `get_next_number` (BUG-2650…2653); the manager must not catch and hide the unique violation until BUG-2652 is fixed. | P1–P3 |
| FU-2 | `transfer_order_manager.spec.md` (`list_transfer_orders`) | No caller — candidate for the dead-code list together with Q3. | Q3 |
| FU-3 | `transfer_order_service.spec.md` (`list_transfer_orders_page`, `get_transfer_order_hub_stats`) | The service defaults `exclude_complete` to `False` (the DAO's own default is `True`); the web app sends it explicitly. `"all"` for a location type means no filter (service). | R7 |

## Overview
Data access for transfer orders (internal stock moves between factory storage, damaged stock, machines and project components) and their lines. It numbers new orders (`TR-<year>-<nnn>`), serves the transfer hub (filtered page, count, KPI totals, recent orders, machine-involved count, pending-action highlights), and answers two lookups for other screens: incomplete transfers touching a location (a location's active orders, `PurchaseOrderService`) and incomplete transfers into a factory's storage (incoming stock, `InventoryManager`). Callers: `TransferOrderManager` (through `TransferOrderService` and `GET /transfer-orders/`, `GET /transfer-orders/stats/`), `InventoryManager`, `PurchaseOrderService`, `AttachmentManager` (lookup by id). Transfers carry no money. An order is **complete** when `completed_at` is set; nothing here reads approvals or the status for completeness.

**Callables:** 15 specified · 4 not specified
**Externals to mock:** the clock of `get_next_number` — see the **Clock (G1)** note below
**Integration-only behavior:** none

**Notes for the test designer:**
- Location ids are polymorphic (no foreign key): `storage` / `damaged` → a `factories.id`; `machine` → a `machines.id`; `project` → a `project_components.id` (whose `project_id` → `projects.factory_id`). Any string and any integer can be stored in the type / id columns (BUG-823 is the schema fix), so rows with `warehouse`, `""` or id `0` can be built directly.
- `created_at` defaults to Python `utcnow()` at insert; set it explicitly for ordering and date cases. `updated_at` is `NULL` until an update flushes (`onupdate`).
- `transfer_number` has a global unique index today (P1): give every row of every workspace a distinct number when building fixtures.
- **Clock (G1).** Today `get_next_number` runs `from datetime import datetime` **inside the function**, so the module-level name `app.dao.transfer_order.datetime` is shadowed and patching it changes nothing. The function-local import re-reads the attribute `datetime` of the stdlib module `datetime` on every call, so today's year is patched with `monkeypatch.setattr(datetime, "datetime", Fake)` on the stdlib module (`import datetime`; `Fake` subclasses `datetime.datetime` with `now()` overridden), kept to the call under test. After BUG-2653 the year comes from `utcnow()` imported at module level from `app.utils.time`: target `app.dao.transfer_order.utcnow` (`create=True`, the module does not import it today) and also `app.utils.time.utcnow`. These four targets match the cases file's **clock** / **utconly** conventions.
- **Names (G4).** Models: `app.models.transfer_order.TransferOrder` (relationship `current_status` → `Status`), `app.models.transfer_order_item.TransferOrderItem`; also used: `app.models.factory.Factory`, `app.models.machine.Machine`, `app.models.project.Project`, `app.models.project_component.ProjectComponent`, `app.models.status.Status` (own `workspace_id`, `name`, `comment`, all NOT NULL). DAO singletons at the end of `app/dao/transfer_order.py`: `transfer_order_dao = TransferOrderDAO(TransferOrder)` and `transfer_order_item_dao = TransferOrderItemDAO(TransferOrderItem)`.
- **Real soft deletes (G5).** Factory (`FactoryDAO.soft_delete`): `is_deleted=True`, `deleted_at=utcnow()`, `deleted_by`; `is_active` untouched. Machine (`MachineDAO.soft_delete`): `is_deleted=True`, `is_active=False`, `deleted_at`, `deleted_by`. Project (`ProjectManager.delete_project`): `is_deleted=True`, `deleted_at=utcnow()`, `deleted_by`; `is_active` untouched. Project components have **no** soft-delete column (no `is_deleted`, `deleted_at`, `deleted_by`, `is_active`); a component "of a deleted project" is a live component whose project has `is_deleted=True`. None of these flags is read by this DAO (R9, factory filter R1); a realistic card sets the columns above.
- Minimal parents: workspace, profile (`created_by`, NOT NULL), status (`current_status_id`, NOT NULL), factory; machine needs `factory_id`; project needs `factory_id`, `name`, `description`; component needs `project_id`, `name`. Lines need an `items` row and `quantity`.

## Not specified
- `TransferOrderDAO.get_by_workspace` — dead code, to be removed (reviewer; Q3, decided by Claude under the reviewer's delegation 2026-11-10)
- `_transfer_order_is_complete_clause` — one-line expression (`completed_at IS NOT NULL`); its outcome is `aggregate_hub_stats` R2
- `_location_resolvable_clause` — one-line expression (type in the four known types); its outcome is `_apply_transfer_factory_filter` R2
- `_hub_base_query` — builds the base query (status eager-loaded) and applies `_apply_transfer_order_hub_filters`; outcomes are each hub method's R1

---

## `_apply_transfer_order_hub_filters(query, *, workspace_id, date_from=None, date_to=None, status_ids=None, factory_id=None, source_location_type=None, destination_location_type=None, search=None, exclude_complete=True)`
**Shape:** helper (filter) · **Persistence:** reads · **Visibility:** internal (used by: every `*_for_hub` method through `_hub_base_query`)

**Purpose:** narrow a transfer-order query to the hub's filters. Tested through `list_for_hub` / `count_for_hub`.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | always applied |
| `date_from`, `date_to` | date \| None | inclusive bounds on `created_at` (UTC) |
| `status_ids` | list[int] \| None | empty / `None` = no filter |
| `factory_id` | int \| None | `None` = no filter; `0` is a filter (matches nothing real) |
| `source_location_type`, `destination_location_type` | str \| None | exact, case-sensitive; `""` / `None` = no filter |
| `search` | str \| None | trimmed; blank = no filter |
| `exclude_complete` | bool | default `True` |

**Returns:** the narrowed query.

**Rules:**
- **R0.** Every filter keyword is optional: all default to `None` except `exclude_complete=True`, so any hub method may be called with only `workspace_id`; an omitted keyword behaves exactly as passing its default — no date, status, factory, type or search filter, and completed orders dropped (G2).
- **R1.** Only orders of `workspace_id` are kept; an order of another workspace never appears, whatever the other filters.
- **R2.** `date_from` keeps orders with `created_at` at or after `date_from` 00:00:00; `date_to` keeps orders with `created_at` at or before `date_to` 23:59:59.999999, so `date_from = date_to` covers that whole day. Days are UTC days (stored `created_at` is UTC; intended, machine activity event precedent). `date_from` after `date_to` → nothing, no error.
- **R3.** `status_ids` `None` or `[]` → no status filter.
- **R4.** [BUG-2660] A non-empty `status_ids` keeps orders by **stage**, not by stored status: each id is looked up among the statuses of `workspace_id`; a status whose name, trimmed and case-insensitive, is `draft` keeps Draft orders, `planned` keeps Planned orders, `completed` keeps Completed orders (several ticks combine with OR). Stages: **Completed** = `completed_at` set; **Planned** = not complete, route defined (`get_pending_highlights_for_hub` R2) and at least one line of `workspace_id`; **Draft** = any other not-complete order. The stored `current_status_id` plays no part. *(Today: keeps orders whose stored `current_status_id` is in the list; every order keeps the status it was created with (BUG-1018), so ticking the workspace's Draft / Planned / Completed status finds nothing.)*
- **R4a.** [BUG-2660] An id of no status, of a status of another workspace (HR-16), or of a status with any other name matches nothing; when no ticked id names a stage, the result is empty. The stage filter combines with AND with the rest, so `Completed` with `exclude_complete=True` gives nothing. *(Today: an id of another status matches the orders stored with it.)*
- **R5.** `source_location_type` / `destination_location_type`, when non-empty, keep orders whose stored type equals the value exactly (`"Storage"` does not match `storage`, verified). Both may be given (AND). `""` / `None` → no filter.
- **R6.** `factory_id` not `None` → `_apply_transfer_factory_filter` R1–R4.
- **R7.** `exclude_complete=True` (the DAO's default) drops orders with `completed_at` set; `False` keeps them.
- **R8.** `search` `None`, `""` or whitespace-only → no search filter (verified). Otherwise the text is trimmed and matched case-insensitively as a substring.
- **R9.** A trimmed search keeps an order when **any** of these contains the text: its `transfer_number`; its source or destination **type** text (e.g. `mach` finds every order with a machine at either end); the **name** of the factory at a `storage` / `damaged` end; the name of the machine at a `machine` end; the name of the project component at a `project` end. Names are looked up in `workspace_id` only — another workspace's factory / machine / component of the same id or name never matches (verified). A location of a known type whose id resolves to nothing matches only by number / type text. Soft-deleted factories and machines, and components of a soft-deleted project, still match (order history; HR-4 note above). Components have no soft-delete column of their own (G5).
- **R10.** Each order appears once, however many of the conditions it matches.
- **R10a.** [BUG-2654] `%`, `_` and `\` in the search text match literally (HR-8). *(Today: placed in `ILIKE '%…%'` unescaped; `_` or `%` alone matches every order, verified.)*
- **R11.** All filters combine with AND and are applied before any paging (HR-5).

**Errors:** none.

**Side effects:** none.

---

## `_apply_transfer_factory_filter(query, session, *, workspace_id, factory_id)` (with `_location_factory_match`, `_location_resolvable_clause`)
**Shape:** helper (filter) · **Persistence:** reads · **Visibility:** internal (used by: `_apply_transfer_order_hub_filters` R6)

**Purpose:** keep transfers that belong to a factory.

**Rules:**
- **R1.** An end (source or destination) **belongs to** factory F when: its type is `storage` or `damaged` and its id = F; or its type is `machine` and its id is a machine of `workspace_id` whose `factory_id` = F; or its type is `project` and its id is a project component of `workspace_id` whose project has `factory_id` = F. A machine / component of another workspace never makes an end belong (HR-16). The machine's / project's `is_deleted` is not looked at (order history).
- **R1a.** [BUG-2658] A transfer is kept when **either** end belongs to F (decided by Claude under the reviewer's delegation, 2026-11-10; as orders overview `_filter_transfer_by_factory` R1). *(Today: kept when the destination belongs to F, or — only when the destination type is none of `storage`, `damaged`, `machine`, `project` — when the source belongs to F. Verified: storage A → machine of factory B is shown under B only; machine of B → `warehouse` is shown under B.)*
- **R2.** A transfer whose ends both belong to no factory F (unknown types, ids resolving to nothing) is never kept for any F.
- **R3.** Each kept transfer appears once (a transfer between two locations of F appears once).

**Errors:** none. **Side effects:** none.

---

## `TransferOrderDAO.list_for_hub(db, *, workspace_id, skip=0, limit=50, **filters)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `TransferOrderManager.list_transfer_orders_for_hub` ← `GET /transfer-orders/`)

**Purpose:** one page of the hub's transfer list.

**Returns:** list of `TransferOrder`, `current_status` loaded.

**Rules:**
- **R1.** The orders are those kept by `_apply_transfer_order_hub_filters` R1–R11 with the given filters (`exclude_complete` defaults to `True` here).
- **R2.** Sorted by `created_at` newest first, then `id` descending (deterministic).
- **R3.** `skip` rows are skipped, then at most `limit` returned (defaults 0 and 50). `skip` past the end → `[]`.
- **R4.** An unknown filter keyword raises `TypeError` (the filters are keyword-only parameters of the helper).

**Errors:** `TypeError` for an unknown filter keyword. **Side effects:** none.

---

## `TransferOrderDAO.count_for_hub(db, *, workspace_id, **filters)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (used by: `TransferOrderManager.count_transfer_orders_for_hub` ← `GET /transfer-orders/` `total`)

**Rules:**
- **R1.** Returns the number of distinct orders kept by the same filters as `list_for_hub` R1, ignoring paging; `0` when none (an `int`, never `None`).

**Errors:** as `list_for_hub` R4. **Side effects:** none.

---

## `TransferOrderDAO.list_recent_for_hub(db, *, workspace_id, limit=10, **filters)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: hub stats `recent_orders`, `limit=10`)

**Rules:**
- **R1.** The orders are those kept by the hub filters (`list_for_hub` R1), at most `limit` (default 10), `current_status` loaded.
- **R2.** [BUG-2655, BUG-2656] Sorted by last activity — `updated_at`, or `created_at` when never updated — newest first, then `id` descending. *(Today: `updated_at DESC, created_at DESC` — never-edited orders (empty `updated_at`) all come before every edited one (verified), and equal timestamps have no tie-break.)*

**Errors:** as `list_for_hub` R4. **Side effects:** none.

---

## `TransferOrderDAO.count_machine_involved_for_hub(db, *, workspace_id, **filters)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (used by: hub stats `machine_involved_count`)

**Rules:**
- **R1.** Returns how many of the orders kept by the hub filters have `machine` as source type or destination type (type text only, exact; the machine id is not checked). An order with a machine at both ends counts once. `0` when none.

**Errors:** as `list_for_hub` R4. **Side effects:** none.

---

## `TransferOrderDAO.get_pending_highlights_for_hub(db, *, workspace_id, **filters)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (used by: hub stats "Pending actions" box)

**Purpose:** count and sample the open orders still being set up or ready.

**Returns:** dict with keys `pending_planned_count` (int), `pending_planned` (list), `awaiting_setup_count` (int), `awaiting_setup` (list), `oldest_drafts` (list); each list entry `{"id", "order_number" (= transfer number), "status_name", "created_at"}`.

**Rules:**
- **R1.** Only orders kept by the hub filters **and** not complete are considered — completed orders are left out even when `exclude_complete=False` is passed.
- **R2.** An order's **route is defined** when source id > 0, destination id > 0, and both types are non-null and non-empty. An id of `0` or below, or an empty type, makes the route undefined.
- **R2a.** [BUG-2659] An order is **Planned**, counted in `pending_planned_count`, when its route is defined **and** it has at least one line of `workspace_id`; every other not-complete order is **Draft**, counted in `awaiting_setup_count`. `pending_planned_count + awaiting_setup_count` = number of not-complete orders kept by the filters. *(Today: the route alone decides; an order with a route and no lines is counted as planned, verified.)*
- **R3.** `status_name` is the fixed label `"Planned"` in `pending_planned` and `"Draft"` in `awaiting_setup` and `oldest_drafts` — never the order's stored status. (With R2a the label is the order's stage.)
- **R4.** [BUG-2655, BUG-2656] `pending_planned` and `awaiting_setup` are at most 3 orders each, by last activity (`updated_at`, else `created_at`) newest first, then `id` descending. *(Today: `updated_at DESC` only — never-edited first, no tie-break.)*
- **R5.** `oldest_drafts` is at most 5 orders of the Draft set (the same set as `awaiting_setup_count`; with BUG-2659 that includes orders with a route but no line).
- **R6.** [BUG-2656] `oldest_drafts` is sorted by `created_at` oldest first, then `id` ascending. *(Today: no tie-break.)*
- **R7.** No matching orders → both counts `0`, all three lists `[]`.

**Errors:** as `list_for_hub` R4. **Side effects:** none.

---

## `TransferOrderDAO.aggregate_hub_stats(db, *, workspace_id, **filters)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (used by: hub stats `total_count`, `open_count`, `completed_count`)

**Rules:**
- **R1.** Returns `(total, open, completed)` as ints over the orders kept by the hub filters; `(0, 0, 0)` when none (verified).
- **R2.** `open` = orders with no `completed_at`; `completed` = orders with `completed_at` set; `open + completed = total`. Status and approvals play no part.
- **R3.** With `exclude_complete=True` (DAO default), `completed` is `0` and `open = total` (verified `(4, 4, 0)` vs `(5, 4, 1)`).

**Errors:** as `list_for_hub` R4. **Side effects:** none.

---

## `TransferOrderDAO.list_touching_location_incomplete(db, *, workspace_id, location_type, location_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `PurchaseOrderService` active orders of a factory storage / project component)

**Rules:**
- **R1.** Returns every not-complete order of `workspace_id` whose source **or** destination has exactly this type and id (each once); `current_status` loaded. Type compared exactly (case-sensitive). No limit.
- **R2.** Completed orders, other workspaces and other locations are left out; nothing matching → `[]`.
- **R3.** [BUG-2656] Sorted by `created_at` newest first, then `id` descending. *(Today: no tie-break.)*

**Errors:** none. **Side effects:** none.

---

## `TransferOrderDAO.list_inbound_to_storage_incomplete(db, *, workspace_id, factory_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `InventoryManager.get_incoming_summary_for_factory` R6)

**Rules:**
- **R1.** Returns every not-complete order of `workspace_id` whose destination type is exactly `storage` and destination id = `factory_id`; `current_status` loaded. Status and approvals do not matter (as the approved inventory manager spec R6). No limit.
- **R2.** A `damaged` destination of the factory, a storage **source**, completed orders, other factories and other workspaces are left out; nothing → `[]`.
- **R3.** [BUG-2656] Sorted by `created_at` newest first, then `id` descending. *(Today: no tie-break; the inventory manager re-sorts, so only direct callers see it.)*

**Errors:** none. **Side effects:** none.

---

## `TransferOrderDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `TransferOrderManager` get / update / delete / complete, `AttachmentManager`)

**Rules:**
- **R1.** Returns the order with this id in this workspace, `current_status` loaded.
- **R2.** Unknown id, or an id of another workspace → `None` (verified).
- **R3.** No row lock is taken (HR-10 completion lock is BUG-821, manager).

**Errors:** none. **Side effects:** none.

---

## `TransferOrderDAO.get_next_number(db, *, workspace_id)`
**Shape:** helper (numbering) · **Persistence:** reads · **Visibility:** public (used by: `TransferOrderManager.create_transfer_order`)

**Purpose:** the next transfer number for the workspace and year, `TR-<year>-<nnn>`.

**Returns:** a string; nothing written.

**Rules:**
- **R1.** [BUG-2653] The year is the current **UTC** year (`utcnow()`). *(Today: `datetime.now()`, the server's local year.)*
- **R2.** No number of this workspace with the prefix `TR-<year>-` → `TR-<year>-001` (verified). Numbers of other years and of other workspaces are not counted (verified: a second workspace gets `-001`).
- **R2a.** The prefix match is case-sensitive (`LIKE`, not `ILIKE`): a stored `tr-2026-009` or `Tr-2026-009` is not counted. Intended, decided by Claude under the reviewer's delegation (2026-11-11), as the sales order / delivery / return numbering specs: numbers are made only here, always upper-case, and `TransferOrderUpdate` has no `transfer_number`, so a lower-case number is foreign data and must not shift the sequence (G3).
- **R2b.** The suffix is the text after the **last** dash: `TR-2026-0-5` is read as `5`. Today such a row, if it is the text-highest, gives `-006`; after BUG-2651 its suffix `0-5` is not all digits and it is ignored (R4).
- **R3.** [BUG-2651] Otherwise the result is the numerically highest all-digit suffix of this workspace and year, plus one, zero-padded to at least 3 digits (`-006` after `-005`; `-1001` after `-999` and `-1000`). *(Today: the highest number **by text order** — after `-999` and `-1000` it returns `-1000` again, verified.)*
- **R4.** [BUG-2651] A number whose suffix is not all digits (e.g. `TR-2026-abc`) is ignored; if it is the only one, the result is `-001`. *(Today: when the text-highest number has a non-numeric suffix the result falls back to `-001`, verified, even if `-001` exists.)*
- **R5.** [BUG-2650] A workspace's number never collides with another workspace's same number: uniqueness is per workspace (unique index on `(workspace_id, transfer_number)`; fix is a migration). *(Today: a global unique index — the second workspace's `TR-2026-001` fails at insert with `IntegrityError` 23505, verified.)*
- **R6.** [BUG-2652] Two creates at the same time in one workspace get distinct numbers and both succeed. *(Today: read-then-insert with no lock; the second fails at flush.)*

**Errors:** none raised here (the unique violation of R5 / R6 surfaces at the manager's insert).

**Side effects:** none.

---

## `TransferOrderItemDAO.get_by_order(db, *, transfer_order_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `TransferOrderManager` lines, `add_item` next line number, completion)

**Rules:**
- **R1.** Returns every line of this order whose own `workspace_id` matches; lines of another workspace (even on this order id) never appear (verified `[]`). No limit. Unknown order → `[]`.
- **R2.** [BUG-2657] Sorted by `line_number` ascending, then `id` ascending. *(Today: `line_number` only; two lines with one number come in no fixed order.)*

**Errors:** none. **Side effects:** none.

---

## `TransferOrderItemDAO.get_by_transfer_order_ids(db, *, workspace_id, transfer_order_ids)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `InventoryManager.get_incoming_summary_for_factory`)

**Rules:**
- **R1.** Empty list → `[]` with no query (verified).
- **R2.** Otherwise every line of `workspace_id` whose order id is in the list; ids of orders of another workspace match nothing.
- **R3.** [BUG-2657] Sorted by order id ascending, then `line_number` ascending, then `id` ascending. *(Today: no `id` tie-break.)*

**Errors:** none. **Side effects:** none.

---

## `TransferOrderItemDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `TransferOrderManager.update_item`, `remove_item`)

**Rules:**
- **R1.** Returns the line with this id whose own `workspace_id` matches; unknown id or another workspace → `None`.

**Errors:** none. **Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 34–45 | machine / component subqueries scoped to workspace and factory | `_apply_transfer_factory_filter` R1 |
| 46–53 | storage/damaged id = factory; machine in factory; component in factory's project | `_apply_transfer_factory_filter` R1, R2 |
| 57 | destination type is one of four known | `_apply_transfer_factory_filter` R1a |
| 78–83 | destination match, else (unresolvable destination) source match | `_apply_transfer_factory_filter` R1a, R2, R3 |
| 99 | workspace filter | `_apply_transfer_order_hub_filters` R1 |
| 101 | `date_from` given / not | `_apply_transfer_order_hub_filters` R2 |
| 105 | `date_to` given / not | `_apply_transfer_order_hub_filters` R2 |
| 86–98 | keyword defaults | `_apply_transfer_order_hub_filters` R0 |
| 109 | `status_ids` truthy / `None` / `[]` | `_apply_transfer_order_hub_filters` R3, R4, R4a |
| 111 | `source_location_type` truthy / not | `_apply_transfer_order_hub_filters` R5 |
| 113 | `destination_location_type` truthy / not | `_apply_transfer_order_hub_filters` R5 |
| 118 | `factory_id is not None` | `_apply_transfer_order_hub_filters` R6 |
| 123 | `exclude_complete` true / false | `_apply_transfer_order_hub_filters` R7 |
| 126 | `search` truthy and non-blank after strip | `_apply_transfer_order_hub_filters` R8 |
| 129–171 | number / type text / factory / machine / component name at either end | `_apply_transfer_order_hub_filters` R9, R10, R10a |
| 178–185 | route defined: ids > 0, types non-null and non-empty | `get_pending_highlights_for_hub` R2, R2a |
| 189 | status eager-loaded, filters applied | `list_for_hub` R1, R4 |
| 194–202 | `get_by_workspace` override | Not specified (dead code) |
| 215–218 | order, offset, limit | `list_for_hub` R2, R3 |
| 222–228 | distinct count, `or 0` | `count_for_hub` R1 |
| 240–242 | recent order and limit | `list_recent_for_hub` R1, R2 |
| 254–263 | machine at either end | `count_machine_involved_for_hub` R1 |
| 269–271 | base forced to not complete | `get_pending_highlights_for_hub` R1 |
| 273–274 | planned vs draft split | `get_pending_highlights_for_hub` R2, R2a |
| 276–288 | counts, top 3 by `updated_at`, oldest 5 | `get_pending_highlights_for_hub` R4, R5, R6, R7 |
| 290–303 | fixed stage labels | `get_pending_highlights_for_hub` R3 |
| 317–332 | complete vs open case sums, `coalesce`, `or 0` | `aggregate_hub_stats` R1, R2, R3 |
| 342–361 | source or destination equals location; incomplete; order | `list_touching_location_incomplete` R1–R3 |
| 372–382 | storage destination = factory; incomplete; order | `list_inbound_to_storage_incomplete` R1–R3 |
| 388–392 | id + workspace, `.first()` | `TransferOrderDAO.get_by_id_and_workspace` R1–R3 |
| 398 | local year | `get_next_number` R1 |
| 400–408 | text-highest number of workspace and year (case-sensitive `LIKE`) | `get_next_number` R2, R2a, R3, R5 |
| 409 | a number found / none | `get_next_number` R2, R3 |
| 410–413 | suffix after the last dash parses / `ValueError` → fall back | `get_next_number` R2b, R3, R4 |
| 414 | `-001` | `get_next_number` R2, R4 |
| 423–431 | order + workspace, by line number | `TransferOrderItemDAO.get_by_order` R1, R2 |
| 440 | empty id list | `get_by_transfer_order_ids` R1 |
| 442–450 | workspace + ids, order | `get_by_transfer_order_ids` R2, R3 |
| 455–459 | id + workspace | `TransferOrderItemDAO.get_by_id_and_workspace` R1 |

## Gap log
- G1 (`transfer_order.cases.md` gap 1) — Fact — Overview "Externals to mock" and the new **Clock (G1)** note: today's year is patched on the stdlib attribute `datetime.datetime` (the function-local import shadows `app.dao.transfer_order.datetime`); after BUG-2653 the targets are `app.dao.transfer_order.utcnow` (`create=True`) and `app.utils.time.utcnow`. The cards' four targets stand.
- G2 (gap 2) — Fact — every filter keyword of `_apply_transfer_order_hub_filters` defaults to `None` (`exclude_complete=True`); signature corrected, new R0.
- G3 (gap 3) — Intent, decided by Claude under the reviewer's delegation (2026-11-11) — new `get_next_number` R2a: the prefix match is case-sensitive, intended (system-made upper-case numbers, not editable; as the other numbering specs). Also new R2b (suffix = text after the last dash), from the code.
- G4 (gap 4) — Fact — Overview **Names (G4)**: model modules, the `current_status` relationship, the `Status` columns, and the singletons `transfer_order_dao`, `transfer_order_item_dao`.
- G5 (gap 5) — Fact — Overview **Real soft deletes (G5)**: what factory, machine and project deletes write; project components have no soft-delete column. R9 wording corrected ("components of a soft-deleted project").
- Coordinator note (2026-11-11) — the HR-16 cards HF-38…40 and FF-12/13 that build a workspace-1 order pointing at another workspace's rows stay, as "invalid data must not leak" read checks; no spec change.
- Owner answers (2026-11-11) — OQ-39 → BUG-2659 (`get_pending_highlights_for_hub` R2a, R3, R5); OQ-40 → BUG-2660 (`_apply_transfer_order_hub_filters` R4, R4a). The cases file's OQ39-* and OQ40-* cards must be re-designed to the intended rules (strict xfail where today differs).
