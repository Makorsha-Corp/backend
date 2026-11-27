# Spec — `app/dao/project_component_item_ledger.py`

> **Status:** APPROVED (2026-11-10; nothing open — OQ-27 answered: projects are skipped until after launch, today's behaviour kept)
> **Source commit:** e48a092

> **Review round 2026-11-10 (apply-review + fill-gaps).** **Owner:** OQ-27 — "projects are skipped for now; revisit after launch. Tests keep today's behaviour, no bug" (owner, 2026-11-10). No writer is added; the read rules stay, tested on hand-made rows. The bugs that only matter once this ledger has rows — BUG-2462, BUG-2463, BUG-2464, and this file's parts of BUG-640, BUG-647, BUG-654 — are tagged *revisit after launch (owner 2026-11-10)*: they stay as rules and their tests stay. BUG-645 is not tagged: the user-transaction report fails on the missing method whether or not rows exist. **Delegated (2026-11-10), decided by Claude, none the owner's own answer:** exact matching of the subtracted types (`calculate_total_cost_for_component` R1b), paging edges of `get_by_performer` (R3–R6), mixed aware / naive bounds (`get_by_date_range` R2b). **Gaps:** the four gaps of `project_component_item_ledger.cases.md` closed (Gap log at the end).

> **Review round 2026-11-09.** No owner answer in this round. **Delegated:** P1–P4 and Q2 decided by Claude under the reviewer's delegation (2026-11-09); none of them is the owner's own answer. The house-rule lines stand. **Owner:** Q1 (OQ-27) is parked in `docs/testing/owner-questions.md`, not blocking: this DAO reads correctly whatever is stored, so no rule here waits on it.
>
> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated. This DAO overrides nothing.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Raw lookups stay raw (HR-4 scope). A ledger is history: entries of a deleted parent stay listed (owner, 2026-10-30; machine item ledger DAO P1–P3, inventory ledger DAO Q3–Q5). HR-16: a row linking to another workspace's row is invalid data. HR-15: money rounds half up (the database's `Numeric(15,2)` does; this DAO does no rounding of its own).
>
> **The ledger manager already covers the reachable reads** (`tests/unit/managers/ledger_manager.spec.md`, approved, tests PASS): `get_project_component_ledger` (R1–R5) and `calculate_project_component_total_cost` (R1–R2), with BUG-640, BUG-642, BUG-645, BUG-647 and BUG-654. This spec states the DAO-level outcome once and points there for the rest.
>
> **Verified by running** (my own scripts `h.py`, `schema.py`, `v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omd\D\`, one transaction on `marker_test`, rolled back, private `COVERAGE_FILE`): the table's columns, types, precision, constraints, foreign-key actions, indexes and triggers (none); the table is empty on `marker_test`; every method for own workspace, other workspace and an unknown id; `get_by_component` with `skip=1, limit=1`, `limit=0` (`[]`), `limit=-1` (`DataError`, pgcode `2201W`); `get_by_transaction_type` exact, different case (`[]`), `None` (`[]`); `get_by_order` for `500` and `None` (rows with an empty `order_id`); `get_by_date_range` exact bounds, a date-only "same day" range (`[]`), `None` bounds (`ArgumentError`), aware UTC bounds under the database time zone `America/New_York` (`[]` for an entry inside the range); `calculate_balance` with no entry, with entries, with an empty `value_after`, for another workspace; `get_latest_entry`; `calculate_total_cost_for_component` with no rows, with three rows (`65.13`), with a sum of exactly zero (`Decimal('0.00')`), for another workspace's component; a stored `0.125` reads back `0.13`; two entries with one `performed_at` under a forced sequential scan after an update; `get_by_performer` is absent. **Read, not run:** `LedgerManager`, `LedgerService`, `GET /ledgers/project-component/`, `GET /ledgers/project-component/{id}/total-cost/`, every writer search across `app/`. **Not run:** anything over HTTP; two concurrent transactions.

## Review
> All answered or parked; applied 2026-11-09.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | **OWNER** — nothing in the application writes this ledger, so the project component ledger page is always empty and its total cost is always 0.00 | intended for now — revisit after launch (owner 2026-11-10); no writer, no bug | **owner** (2026-11-10) — was: owner (pending) |
| Q2 | "Ledger entries of one order" has no caller and its order columns are never filled | remove (dead code) | delegation |
| P1 | Lists still show entries of a deleted project or of an item removed from the catalog | intended, per machine item ledger P1/P2 | delegation; ruling restated by the owner 2026-10-30 |
| P2 | Balance and latest entry ignore a deleted project or removed item | intended, per machine item ledger P3 | delegation |
| P3 | The two unreachable lists (by transaction type, by date range) have the same missing tie-break | bug — BUG-2462 | delegation (HR-6) |
| P4 | A date with a time zone is compared to stored UTC in the database's time zone | bug — BUG-2464, per BUG-992 | delegation |

Decided by house rules: entries with one timestamp come back in no fixed order (BUG-640, existing; BUG-2462); the "latest entry" on a timestamp tie is arbitrary (BUG-2463).

### House-rule violations — applied automatically

- **HR-6** `get_by_component_and_item` R3, `get_by_component` R3 — ordered by `performed_at` newest first only. Verified: two entries of one `performed_at` under a forced sequential scan came back in physical order, which an update changes. Intended: `performed_at` newest first, then `id` descending, before `skip` / `limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-640 (existing; its row names `get_project_component_ledger`, which reaches exactly these two methods; no new ID). Rules: `get_by_component_and_item` R3, `get_by_component` R3.
- **HR-6** `get_by_transaction_type` R3, `get_by_date_range` R4 — same order, same missing tie-break. No caller today (R of each); the BUG-647 fix will reach `get_by_date_range`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2462 (pattern `tied-timestamp-no-tiebreak`, BUG-640 precedent). Rules: `get_by_transaction_type` R3, `get_by_date_range` R4.
- **HR-6** `calculate_balance` R3, `get_latest_entry` R2 — the "latest entry" of a component and item is picked by `performed_at` only. Verified: two entries of one time, the pick followed physical order. Intended: latest = greatest `performed_at`, ties broken by greatest `id`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2463 (pattern `tied-timestamp-no-tiebreak`; BUG-641 / BUG-664 precedent, whose rows name the machine and inventory ledger DAOs, not this file). Rules: `calculate_balance` R3, `get_latest_entry` R2.
- **HR-6** inherited `get_by_workspace` — no sort order. Intended for this raw lookup: `id` ascending. No caller on this DAO.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-100 (existing, fixed in `app/dao/base.py`). Rules: inherited methods R2.

Checked and **not** a new line here: **HR-4** — the table has no soft-delete column; deleted parents are P1, P2. **HR-5** — every filter is in the query before `skip` / `limit`. **HR-7** — the DAO does not validate paging (`limit=0` → `[]`, negative → `DataError`); `GET /ledgers/project-component/` lacks the lower bound, which is **BUG-642** (existing, against the endpoints); R5 of each list records today's DAO behaviour, untagged, as in the machine and inventory ledger specs. **HR-8** — no `LIKE`. **HR-9** — no "last changed by" column. **HR-10** — nothing here changes state. **HR-15** — the DAO adds stored `Numeric(15,2)` values exactly; it rounds nothing. **HR-16** — every method filters on the row's own `workspace_id`; a component id of another workspace gives `[]` / `(0, 0.00)` / `None` / `0.00` (verified). A row whose `project_component_id` or `item_id` belongs to another workspace than its own `workspace_id` is invalid data that no writer can create today (Q1). **Falsy `0`** — no method here tests truthiness of an argument; `0` is an id that matches nothing.

### Existing bugs that land in this file (no new ID)
- **BUG-645** — this DAO has no `get_by_performer`; `GET /ledgers/reports/user-transactions/{user_id}/` raises `AttributeError` (500) on the machine ledger first and would raise it here next. Specified below as a method to add (same shape as the machine ledger DAO's).
- **BUG-647** (with BUG-646, BUG-648) — the item movement report's `project` list needs "entries of one item in the workspace, each given date bound applied on its own, paged". No method here does that: `get_by_date_range` has no `item_id` and raises on a `None` bound (R3). The fix adds an `item_id` filter and lets a `None` bound mean "no bound"; R3 then stops applying and R1 covers one bound alone. R2, R2a, R4 stay.
- **BUG-654** — the total cost is a plain sum; the net (outgoing types subtracted) is decided in the ledger manager spec. The manager only passes through, so the fix lands in this file's sum: `calculate_total_cost_for_component` R1 is tagged with it.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-09)

### P1. Lists still show entries of a deleted project or removed item — ✅ intended
**Background:** Projects are soft-deleted (`is_deleted = True`); components have no soft delete and cannot be removed while ledger rows point at them (`ON DELETE RESTRICT`, BUG-1196). Items are removed with `is_active = False`. No method here looks at the parent rows. For the machine and inventory ledgers the ruling is that a ledger is history and stays complete (owner restated 2026-10-30).
**What happens today:** Entries are returned whatever the state of their project or item (read; the methods never join a parent).
**Example:** Project "Bridge A" is deleted in June. Its component "Deck" received 40 bolts in March. The component's ledger still lists "March: +40 bolts".
**Rules affected:** `get_by_component_and_item` R4, `get_by_component` R4, `get_by_transaction_type` R4, `get_by_date_range` R5
**Answer:** intended — per machine item ledger DAO P1/P2 precedent: a ledger is history
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-09); rules unchanged ✅. Who may open a deleted project's component is `require_component_access` (BUG-1278, existing).

### P2. Balance and latest entry ignore a deleted project or removed item — ✅ intended
**Background:** Same as P1; machine item ledger P3 kept the same two lookups raw, because a caller that hid them would see 0 and could write a false adjustment.
**What happens today:** The balance and latest entry are returned like any other.
**Example:** Component "Deck" of the deleted project holds 30 bolts in the ledger; the balance answers `(30, …)`.
**Rules affected:** `calculate_balance` R5, `get_latest_entry` R4
**Answer:** intended — per machine item ledger DAO P3 precedent
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-09); rules unchanged ✅.

### P3. The two unreachable lists have the same missing tie-break — 🐞 BUG-2462
See the HR-6 line above. Listed here because neither method has a caller: they stay specified, not removed, because the BUG-647 fix needs `get_by_date_range`, and `get_by_transaction_type` is the same one-line fix. **Answer:** bug — per HR-6. **Resolution:** BUG-2462.

### P4. A date with a time zone gives a result that depends on the server — 🐞 BUG-2464
**Background:** `performed_at` holds UTC with no time-zone mark (`timestamp without time zone`, default `utcnow`). An aware datetime is compared after Postgres reads the stored value in the session's `TimeZone`. Ruled a bug for the machine ledger (BUG-992).
**What happens today:** Verified: an entry at 10:00 UTC, range 09:30Z–10:30Z, database time zone `America/New_York` → `[]`.
**Example:** Once the item movement report reads project entries (BUG-647), a client asking for 09:30Z–10:30Z misses the 10:00 entry on a server not set to UTC.
**Rules affected:** `get_by_date_range` R2a
**Answer:** bug — per BUG-992 precedent: aware datetimes are converted to UTC and made naive before the comparison
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-09): 🐞 BUG-2464 (pattern `aware-datetime-against-naive-column`; best fixed in the same shared helper as BUG-992). Rules: `get_by_date_range` R2a.

### New questions

### Q1. **OWNER** — Nothing writes the project component item ledger — ⏸ OQ-27, revisit after launch (owner 2026-11-10)
**Background:** This table is meant to record every item movement into, out of and within a project component (types `purchase_order`, `manual_add`, `transfer_in`, `transfer_out`, `consumption`, `damaged`, `inventory_adjustment`, `cost_adjustment`), with cost, value and average price before and after. Searched across `app/` (2026-11-09): no code creates a row: no `ProjectComponentItemLedger(...)`, no `project_component_item_ledger_dao.create`, no raw SQL. Work orders linked to a component, transfer orders and project component items (planned quantities, which move no stock) write nothing here. `marker_test` holds no rows. The project component item service spec says this ledger "is written by work orders"; that is not so.
**What happens today:** `GET /ledgers/project-component/` always returns `[]` and `GET /ledgers/project-component/{id}/total-cost/` always returns `0.0`. The item movement report's `project` list will stay empty after BUG-647 is fixed. Everything a component consumes is invisible as project cost; only miscellaneous costs (typed by hand) carry money onto a project.
**Example:** A work order on component "Deck" uses 40 bolts at 2.50 from storage. Storage stock drops by 40 and the storage ledger shows it, but "Deck"'s ledger is empty and its item cost reads 0.00.
**Rules affected:** none in this DAO (every rule reads what is stored; tests build rows by hand). It decides whether a writer is a missing feature or a bug, and which movements must write here.
**Suggested answer:** intended for now — project item costing is not built yet; the read paths stay and are tested on hand-made rows. When it is built, decide which movements write here (e.g. a transfer to a project component, or work-order consumption on a component) and price them at the source's average cost, half up.
**Alternative:** bug — work orders on a project component (and transfers to one) must write a ledger row now, so component cost is real.
**Answer:** owner, 2026-11-10: projects are skipped for now; revisit after launch. Tests keep today's behaviour, no bug.
**Resolution:** no bug, no rule change: every rule reads what is stored. The bugs that only matter once rows exist are tagged *revisit after launch (owner 2026-11-10)* (see the round note at the top).

### Q2. "Ledger entries of one order" has no caller, and its column is never filled — 🗑️ remove (dead code)
**Background:** `get_by_order` filters on `order_id` only. Nothing in `app/` or `tests/` calls it; nothing writes the table at all (Q1). The machine ledger's identical method was removed for the same reason (machine item ledger DAO Q5).
**What happens today:** Reachable by nobody. Verified facts if kept: same-workspace rows with that `order_id`, oldest first by `performed_at`, no tie-break, no limit; it ignores `order_type`, so purchase order 500 and work order 500 mix; `order_id=None` returns every row with an empty `order_id` (verified: 2 of 3).
**Example:** No endpoint, job or script lists project ledger entries by order; deleting it changes nothing a user can see.
**Rules affected:** `get_by_order` (all)
**Answer:** remove — per machine item ledger DAO Q5 precedent
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-09); not specified; listed under **Not specified** and for `docs/testing/dead-code-removal-checklist.md` (`app/dao/project_component_item_ledger.py:107`). Not a bug, no BUG ID.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Project component item ledger schema** (`app/schemas/project_component_item_ledger.py:12-15`) | `ProjectComponentItemLedgerResponse` inherits the eight-type `transaction_type` pattern and `ge=0` on `quantity`, `unit_cost`, `total_cost`, so `GET /ledgers/project-component/` would answer 500 on any other stored type or a negative cost (BUG-990 precedent, machine ledger FU-3). Latent while nothing writes rows (Q1 / OQ-27); decide with the writer. | machine ledger FU-3, Q1 |
| FU-2 | **Project component item service spec** (`tests/unit/services/project_component_item_service.spec.md`, "Stock and money") | States that this ledger "is written by work orders". It is not written by anything (Q1). Correct the sentence; no rule there changes. | Q1 |
| FU-3 | **Profile deletion** | `performed_by` is `NOT NULL` with `ON DELETE SET NULL`: hard-deleting a profile with entries would fail (`NotNullViolation`). No code hard-deletes a profile today (machine ledger FU-5). | model check |

## Overview
`ProjectComponentItemLedgerDAO` reads `project_component_item_ledger`: the history of item movements on a project component, one row per movement of one component and item, with quantity, cost, value and average price before and after. Callers: `LedgerManager.get_project_component_ledger` (`get_by_component_and_item` when an item is given, otherwise `get_by_component`), `LedgerManager.calculate_project_component_total_cost` (`calculate_total_cost_for_component`), and `LedgerManager.get_transactions_by_user` (calls `get_by_performer`, which does not exist: BUG-645). Every other method has no caller. Nothing in the application writes the table (Q1). Every method filters on the row's `workspace_id`; nothing flushes, commits or locks.

**Callables:** 7 specified, 1 to add (`get_by_performer`, BUG-645), + inherited `BaseDAO` behaviour · 2 not specified
**Externals to mock:** none (`performed_at` defaults to `app.utils.time.utcnow` in Python; tests set it explicitly)
**Integration-only behavior:** none.

**Model facts (table `project_component_item_ledger`, class `app.models.project_component_item_ledger.ProjectComponentItemLedger`), verified on `marker_test`:**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `project_component_id` | Integer NOT NULL, FK `project_components.id` ON DELETE RESTRICT | — |
| `item_id` | Integer NOT NULL, FK `items.id` ON DELETE RESTRICT | — |
| `transaction_type` | String(50) NOT NULL; no check constraint | — |
| `quantity`, `qty_before`, `qty_after` | Integer NOT NULL | — |
| `unit_cost`, `total_cost` | Numeric(15,2) NOT NULL | — |
| `value_before`, `value_after`, `avg_price_before`, `avg_price_after` | Numeric(15,2) nullable | `NULL` |
| `source_type` | String(50) NOT NULL | — |
| `source_id`, `order_id`, `transfer_source_id`, `transfer_destination_id` | Integer nullable, no FK | `NULL` |
| `order_type` | String(30) nullable | `NULL` |
| `invoice_id` | Integer nullable, FK `account_invoices.id` ON DELETE SET NULL | `NULL` |
| `transfer_source_type`, `transfer_destination_type` | String(50) nullable | `NULL` |
| `notes` | Text nullable | `NULL` |
| `performed_by` | Integer NOT NULL, FK `profiles.id` ON DELETE SET NULL (FU-3) | — |
| `performed_at` | `timestamp without time zone` NOT NULL | Python `utcnow()` (no server default) |

Indexes: primary key, and single-column indexes on `id`, `workspace_id`, `project_component_id`, `item_id`, `transaction_type`, `source_type`, `order_id`, `invoice_id`, `performed_at`, `performed_by`. No unique constraint, no trigger. Values outside `Numeric(15,2)` scale are rounded half up by the database (verified: `0.125` → `0.13`).

**Notes for the test designer:** build rows directly (`ProjectComponentItemLedger(...)`, add + flush) with an explicit `performed_at`; the project component, item and profile must exist (FKs). For a tie, give two rows the same `performed_at`; physical order can be changed with an `UPDATE` of the lower id. The methods take keyword-only arguments after `db`.

## Not specified
- `ProjectComponentItemLedgerDAO.get_by_order` — dead code, to be removed (Q2).
- `project_component_item_ledger_dao` — module-level instance, no logic.

---

## `ProjectComponentItemLedgerDAO.get_by_component_and_item(db, *, project_component_id, item_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `LedgerManager.get_project_component_ledger` when `item_id` is truthy)

**Purpose:** One component's entries for one item.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| project_component_id, item_id, workspace_id | int | Exact match on the row's columns; existence not checked. |
| skip, limit | int | Default 0 / 100; not validated. |

**Returns:** list of `ProjectComponentItemLedger` rows (possibly empty).

**Rules:**
- **R1.** Only rows with this `workspace_id`, `project_component_id` and `item_id`. The same component and item ids under another workspace are never returned (verified: `[]`).
- **R2.** Rows of other items of the same component, and of the same item on other components, are not returned.
- **R3.** [BUG-640] (revisit after launch (owner 2026-11-10)) Order: `performed_at` newest first, then `id` descending, before `skip` / `limit`. *(Today: `performed_at` only; ties in no fixed order.)*
- **R4.** ✅ Entries are returned whatever the state of their project (soft-deleted) or item (inactive) (P1).
- **R5.** `skip` / `limit` apply after filtering and ordering; `limit=0` → `[]`; a negative `limit` or `skip` → `sqlalchemy.exc.DataError` (pgcode `2201W` / `2201X`) (verified for `limit=-1`). The API bound is BUG-642 (endpoint, existing).

**Errors:** as R5.
**Side effects:** none

---

## `ProjectComponentItemLedgerDAO.get_by_component(db, *, project_component_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `LedgerManager.get_project_component_ledger` when `item_id` is falsy)

**Purpose:** All entries of one component.

**Inputs:** as `get_by_component_and_item` without `item_id`.

**Returns:** list of rows.

**Rules:**
- **R1.** Only rows with this `workspace_id` and `project_component_id`, every item (verified: three rows of two items).
- **R2.** Another workspace's component id → `[]`.
- **R3.** [BUG-640] (revisit after launch (owner 2026-11-10)) Order `performed_at` newest first, then `id` descending, before paging. *(Today: `performed_at` only.)*
- **R4.** ✅ As `get_by_component_and_item` R4 (P1).
- **R5.** Paging as `get_by_component_and_item` R5 (verified: `skip=1, limit=1` returns the second newest).

**Errors:** as `get_by_component_and_item` R5.
**Side effects:** none

---

## `ProjectComponentItemLedgerDAO.get_by_transaction_type(db, *, transaction_type, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public — **no caller** in `app/` or `tests/` (kept, P3)

**Purpose:** The workspace's entries of one transaction type.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| transaction_type | str | Exact, case-sensitive equality; no validation. |
| workspace_id | int | Scope. |
| skip, limit | int | Default 0 / 100. |

**Returns:** list of rows.

**Rules:**
- **R1.** Only rows of this workspace whose `transaction_type` equals the argument exactly: `"Transfer_In"` does not match `transfer_in` (verified); `None` matches nothing (the column is NOT NULL; verified `[]`).
- **R2.** Every component and item of the workspace; another workspace's rows never.
- **R3.** [BUG-2462] (revisit after launch (owner 2026-11-10)) Order `performed_at` newest first, then `id` descending, before paging. *(Today: `performed_at` only.)*
- **R4.** ✅ Deleted project / inactive item as `get_by_component_and_item` R4.
- **R5.** Paging as `get_by_component_and_item` R5.

**Errors:** as `get_by_component_and_item` R5.
**Side effects:** none

---

## `ProjectComponentItemLedgerDAO.get_by_date_range(db, *, workspace_id, start_date, end_date, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public — **no caller** today; the BUG-647 fix will use it (see "Existing bugs")

**Purpose:** The workspace's entries with `performed_at` inside a closed range.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| workspace_id | int | Scope. |
| start_date, end_date | datetime | Both bounds inclusive, compared exactly to the microsecond. Not checked for order. |
| skip, limit | int | Default 0 / 100. |

**Returns:** list of rows.

**Rules:**
- **R1.** Only rows of this workspace with `start_date <= performed_at <= end_date` (verified: entries at exactly both bounds are included).
- **R2.** A bound given as a date at midnight is midnight exactly: `2026-09-30 00:00` to `2026-09-30 00:00` misses an entry at 10:00 that day (verified `[]`). A reversed range returns `[]`. (A date-only end bound meaning "whole day" is an endpoint concern, BUG-991.)
- **R2a.** [BUG-2464] (revisit after launch (owner 2026-11-10)) An aware bound is converted to UTC and made naive before the comparison, so the result does not depend on the database's `TimeZone`. *(Today: compared in the session time zone; verified: entry at 10:00 UTC, range 09:30Z–10:30Z, `America/New_York` → `[]`.)*
- **R2b.** [BUG-2464] (revisit after launch (owner 2026-11-10)) One aware and one naive bound: each bound is normalised on its own — the aware one converted to UTC and made naive, the naive one taken as UTC as given — and the query runs; no error. Entries at 07:00, 12:00 and 18:00 UTC, start `11:30Z` (aware), end `12:30` (naive), any session zone → only 12:00. *(Today: the aware bound is read in the session zone; under `America/New_York` the window becomes 07:00…12:30, so 07:00 and 12:00 come back.)* Decided under the reviewer's delegation (2026-11-10): normalise, not refuse — the machine item ledger DAO's `get_by_date_range` R3a (BUG-992) already says "a naive bound next to an aware one stays as given", and both ledgers are fixed in one shared helper; refusing would need a new error the API does not have.
- **R3.** A `None` bound raises `sqlalchemy.exc.ArgumentError` before any query (verified). *(Stops applying with the BUG-647 fix; see "Existing bugs".)*
- **R4.** [BUG-2462] (revisit after launch (owner 2026-11-10)) Order `performed_at` newest first, then `id` descending, before paging. *(Today: `performed_at` only.)*
- **R5.** ✅ Deleted project / inactive item as `get_by_component_and_item` R4; every component and item of the workspace.
- **R6.** Paging as `get_by_component_and_item` R5.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `start_date` or `end_date` is `None` | `sqlalchemy.exc.ArgumentError` | SQLAlchemy's own |
| negative `skip` / `limit` | `sqlalchemy.exc.DataError` | Postgres' own |

**Side effects:** none

---

## `ProjectComponentItemLedgerDAO.calculate_balance(db, *, project_component_id, item_id, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public — **no caller** today

**Purpose:** The current quantity and value of one item on one component, as recorded by its latest entry.

**Inputs:** `project_component_id`, `item_id`, `workspace_id` (int), exact match.

**Returns:** `tuple[int, Decimal]` = (`qty_after`, value) of the latest entry.

**Rules:**
- **R1.** No entry for this workspace, component and item → `(0, Decimal('0.00'))` (verified; also for another workspace's ids).
- **R2.** Otherwise → (`qty_after`, `value_after`) of the latest entry, as stored; an empty `value_after` (`NULL`) → `Decimal('0.00')` (verified: `(0, Decimal('0.00'))` for an entry with `qty_after 0`, `value_after NULL`). A stored `0.00` is returned as `Decimal('0.00')` either way.
- **R3.** [BUG-2463] (revisit after launch (owner 2026-11-10)) Latest = greatest `performed_at`, ties broken by greatest `id`. *(Today: `performed_at` only; on a tie an arbitrary entry decides.)*
- **R4.** The balance is read from the latest entry only; earlier entries are not summed (verified: entries `qty_after 10` then `7` → `(7, 35.00)`).
- **R5.** ✅ A deleted project or inactive item does not change the result (P2).

**Errors:** none
**Side effects:** none

---

## `ProjectComponentItemLedgerDAO.get_latest_entry(db, *, project_component_id, item_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public — **no caller** today

**Purpose:** The newest entry of one item on one component.

**Inputs:** as `calculate_balance`.

**Returns:** `ProjectComponentItemLedger | None`.

**Rules:**
- **R1.** No entry for this workspace, component and item → `None` (another workspace's ids included).
- **R2.** [BUG-2463] (revisit after launch (owner 2026-11-10)) Latest = greatest `performed_at`, ties broken by greatest `id`. *(Today: `performed_at` only.)*
- **R3.** Returns the same entry `calculate_balance` reads (one shared definition of "latest").
- **R4.** ✅ A deleted project or inactive item does not change the result (P2).

**Errors:** none
**Side effects:** none

---

## `ProjectComponentItemLedgerDAO.calculate_total_cost_for_component(db, *, project_component_id, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `LedgerManager.calculate_project_component_total_cost`)

**Purpose:** The total item cost booked to a component.

**Inputs:** `project_component_id`, `workspace_id` (int).

**Returns:** `Decimal`.

**Rules:**
- **R1.** [BUG-654] (revisit after launch (owner 2026-11-10)) Result = net cost: `total_cost` of `transfer_out` and `damaged` rows subtracted, every other transaction type added (the ledger manager spec's R1 lists the types and the default for future types). *(Today: plain sum of `total_cost` over every row, whatever the type; verified `50.00 + 15.00 (transfer_out) + 0.13 = 65.13`.)*
- **R1a.** Only rows of this workspace and component count; another workspace's component id → `Decimal('0.00')` (verified).
- **R1b.** [BUG-654] (revisit after launch (owner 2026-11-10)) The outgoing types are matched exactly, case- and space-sensitive: only `transfer_out` and `damaged` are subtracted. A stored `Transfer_Out`, `DAMAGED` or ` transfer_out` is an unknown type and, like every other type, is **added** (the ledger manager spec's default for types not in the outgoing list). Decided under the reviewer's delegation (2026-11-10): transaction types are code-set constants, not user text (HR-3 does not apply), `get_by_transaction_type` R1 matches them exactly too, and the response schema allows only the eight lower-case values; a variant can only come from hand-made data.
- **R2.** No rows, or a result of exactly zero → `Decimal('0.00')` (verified for both: `+1` and `-1` → `Decimal('0.00')`).
- **R3.** Values are added exactly as stored (`Numeric(15,2)`); the DAO rounds nothing (HR-15 is the writer's concern).

**Errors:** none
**Side effects:** none

---

## `ProjectComponentItemLedgerDAO.get_by_performer(db, *, performed_by, workspace_id, skip=0, limit=100)` — to add (BUG-645)
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `LedgerManager.get_transactions_by_user`)

**Purpose:** One user's entries in the workspace.

**Rules:**
- **R1.** [BUG-645] Rows of this workspace with `performed_by` = the argument; another workspace's rows never. *(Today: the method does not exist; the caller raises `AttributeError`.)*
- **R2.** [BUG-645] Order `performed_at` newest first, then `id` descending, before `skip` / `limit` (default 0 / 100). *(Today: does not exist.)*
- **R3.** [BUG-645] `skip` / `limit` apply after filtering and ordering, as `get_by_component` R5: `limit=0` → `[]`; a negative `skip` or `limit` → `sqlalchemy.exc.DataError` (Postgres' own). *(Today: does not exist.)*
- **R4.** [BUG-645] `performed_by=None` → `[]` (the column is NOT NULL, so nothing matches); `0` or an unknown profile id → `[]`; no error. *(Today: does not exist.)*
- **R5.** [BUG-645] Entries of a deleted project or of an inactive item are still listed, as `get_by_component_and_item` R4 (P1). *(Today: does not exist.)*
- **R6.** [BUG-645] Reads only: no row is written and no lock is taken. *(Today: does not exist.)*
  Decided under the reviewer's delegation (2026-11-10) for R3–R6: paging and filter edges follow this DAO's other lists exactly, so the new method behaves like its siblings.

**Errors:** negative `skip` / `limit` → `sqlalchemy.exc.DataError` (Postgres' own). Today: `AttributeError` at the caller.
**Side effects:** none

---

## Inherited `BaseDAO` methods (`tests/unit/dao/base.spec.md`)
- **R1.** `get`, `get_by_id_and_workspace`, `get_multi`, `create`, `update`, `remove` behave as the base spec says; nothing in `app/` calls them on this DAO.
- **R2.** [BUG-100] `get_by_workspace` orders by `id` ascending before paging (base spec). *(Today: no order.)*

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 39-41 | workspace + component + item filter | `get_by_component_and_item` R1, R2 |
| 43 | order `performed_at` desc | `get_by_component_and_item` R3 |
| 44-45 | offset / limit | `get_by_component_and_item` R5 |
| 69-70 | workspace + component filter | `get_by_component` R1, R2 |
| 72-74 | order, paging | `get_by_component` R3, R5 |
| 98-99 | exact transaction type | `get_by_transaction_type` R1, R2 |
| 101-103 | order, paging | `get_by_transaction_type` R3, R5 |
| 107-129 | `get_by_order` | Not specified (Q2, remove) |
| 152-154 | inclusive bounds, `None` bound | `get_by_date_range` R1, R2, R2a, R3 |
| 156-158 | order, paging | `get_by_date_range` R4, R6 |
| 184-185 | latest by `performed_at` | `calculate_balance` R3 |
| 188 | `if entry` | `calculate_balance` R1, R2 |
| 189 | `entry.value_after or Decimal('0.00')` (a `Decimal`, not a float) | `calculate_balance` R2 |
| 190 | no entry | `calculate_balance` R1 |
| 214-215 | latest by `performed_at`, `.first()` | `get_latest_entry` R1, R2 |
| 235-240 | sum of `total_cost`, workspace + component | `calculate_total_cost_for_component` R1, R1a |
| 243 | `result if result else Decimal('0.00')` (a `Decimal`; no rows → `None`; zero → falsy) | `calculate_total_cost_for_component` R2 |
| — | `get_by_performer` missing | `get_by_performer` R1, R2 |

## Gap log
- G1 (project_component_item_ledger.cases.md gap 1) — Fact — Branch map misquoted the code: both fallbacks are `Decimal('0.00')` (lines 190, 243), so R2 of `calculate_balance` and `calculate_total_cost_for_component` stand and the `isinstance(..., Decimal)` cards are right.
- G2 (gap 2) — Intent, decided under delegation (2026-11-10) — new `calculate_total_cost_for_component` R1b: outgoing types matched exactly; variants count as incoming.
- G3 (gap 3) — Intent, decided under delegation (2026-11-10) — new `get_by_performer` R3–R6 (paging, `None` / `0` / unknown performer, deleted parents, no side effects) and its Errors row, matching the sibling lists.
- G4 (gap 4) — Intent, decided under delegation (2026-11-10) — new `get_by_date_range` R2b: mixed bounds normalised one by one, never refused (machine item ledger R3a precedent).
- OQ-27 (owner, 2026-11-10) — no rule change; bug rules that only matter once rows exist tagged revisit after launch (tests stay).
