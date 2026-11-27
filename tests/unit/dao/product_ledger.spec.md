# Spec — `app/dao/product_ledger.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** **Delegated,** decided by Claude under the reviewer's delegation (2026-11-02): P1, P2 and P3 `bug`, P4 `remove`, Q1 `intended`. None of these is the owner's own answer. The house-rule line stands.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Ledgers are history: their rows stay listed whatever happened to the factory or the item (inventory ledger DAO Q3, Q4). HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v_prod.py`, harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\proddao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints and indexes; newest first; tied `performed_at` after an update under a forced sequential scan, including a row seen on two pages; every filter alone and together, `0`, blank, case, spaces, inverted range; another workspace; midnight as `end_date`; an aware range under `UTC`, `America/New_York`, `Asia/Dhaka`; `exists_for_production_batch` with a match, another workspace, another batch, `0`, another `source_type`, two rows; the row of a soft-deleted factory and of a removed item; `performed_at` default under `UTC` and `Asia/Dhaka`; 101 rows, the cap, `limit=0`, negative values; `create`, `update` with a dict and a schema, `remove`. **Not run:** anything over HTTP; two concurrent transactions; the intended behaviour of the bugs below.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically

- **HR-6** `get_by_workspace` R7 — ordered by `performed_at` only, and rows written in one save share one timestamp. Verified: three tied rows came back `0, 1, 2`, and `1, 2, 0` after one update; and page by page, `limit=2` then `skip=2` gave `3, 2` and `2, 0`: row 2 twice, row 1 never. Intended: `performed_at` newest first, then `id` descending, before `skip` / `limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-640 (existing, pattern `tied-timestamp-no-tiebreak`) — no new ID; its Module cell now names this method too. Rules: `get_by_workspace` R7.

Checked and **not** a new line here: **HR-3** — `transaction_type` is a code the system writes, not free text. **HR-4** — no soft-delete column; rows of a deleted factory or removed item stay listed (standing decision). **HR-5** — every filter is in the query. **HR-7** — `GET /products/ledger/` already requires `1 <= limit <= 1000` and `skip >= 0`. **HR-8** — no `LIKE`. **HR-9, HR-10** — the DAO only reads. **HR-15** — no arithmetic here. **HR-16** — the reads follow the row. `factory_id` and `item_id` use `is not None`, so `0` filters: the BUG-885 trap is not here (verified). Blank `transaction_type` means "no filter" (R5a): a blank box in a filter form, which is what a client that sends `?transaction_type=` means.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-11-02))

### P1. The end date leaves out that whole day — 🐞 BUG-991 (existing)
**Background:** `GET /products/ledger/` takes `end_date` as a `datetime`, and a date with no time becomes midnight at the start of that day. BUG-991 ruled this for `/ledgers/*`.
**What happens today:** Entries of the last day are missing. Verified: entries at 12:00 on 1 March, with `start_date` and `end_date` both `2026-03-01`, return `[]`.
**Example:** A user asks for finished goods movements of 30 September and gets none, although the day had 12.
**Rules affected:** `get_by_workspace` R4
**Answer:** bug — per BUG-991 precedent: an `end_date` with no time means the end of that day; a value with a time stays exact. Integration-only, the fix is at the endpoint
**Resolution:** BUG-991 (existing, pattern `date-only-upper-bound-excludes-day`) — no new ID; its Module cell now names this endpoint too.

### P2. A date filter with a time zone depends on the database's setting — 🐞 BUG-992 (existing)
**Background:** `performed_at` has no time zone. A bound with one is compared through the session's `TimeZone`. BUG-992 ruled this for the machine and inventory ledgers.
**What happens today:** Verified: entries at 12:00, range 11:30Z–12:30Z: found under `UTC`, nothing under `America/New_York` or `Asia/Dhaka`.
**Example:** The same request with `…Z` bounds gives different answers on two databases.
**Rules affected:** `get_by_workspace` R4a
**Answer:** bug — per BUG-992 precedent: aware bounds are converted to UTC and made naive before the comparison
**Resolution:** BUG-992 (existing, pattern `aware-datetime-against-naive-column`) — no new ID; its Module cell now names this method too.

### P3. A ledger entry's time comes from the database's clock — 🐞 BUG-1337
**Background:** `performed_at` is filled by the database's `now()`, into a column with no time zone. `machine_item_ledger` uses `utcnow`. BUG-1102 ruled the same root cause for a delete time. `inventory_ledger` has the same default and was not raised then.
**What happens today:** The value is local time in the session's `TimeZone`. Verified: 20:26 under `UTC`, 02:26 the next day under `Asia/Dhaka`, for one moment.
**Example:** On a database set to Dhaka time, an entry made at 20:26 UTC is stored as 02:26, so a date filter sent in UTC misses it or picks up the wrong day.
**Rules affected:** inherited R2
**Answer:** bug — per BUG-1102 precedent: `performed_at` defaults to `utcnow()`, naive UTC
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): 🐞 BUG-1337 (pattern `database-clock-timestamp`). The fix is in `app/models/product_ledger.py`, as `machine_item_ledger` has it. Rules: inherited R2, R2a.

### P4. "One ledger entry by id" has no caller — 🗑️ remove
**Background:** `get_by_id_and_workspace` here is a line-for-line copy of the inherited method, and no endpoint shows a single entry. `inventory_ledger.spec.md` Q2 ruled the same case `remove`, for the override only.
**What happens today:** It can never run in production. Deleting it leaves the identical inherited method.
**Example:** No API request reaches it.
**Rules affected:** `get_by_id_and_workspace` (all)
**Answer:** remove — per inventory ledger DAO Q2 precedent: the override only
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): the override is not specified (the inherited `BaseDAO.get_by_id_and_workspace` stays); listed under **Not specified** and in `docs/testing/dead-code-removal-checklist.md` (`app/dao/product_ledger.py:61`). Not a bug — no BUG ID.

### New questions

### Q1. The "only notes can be updated" promise is not enforced — ✅ intended
**Background:** The model calls the ledger an "immutable audit trail - only notes can be updated", and `ProductLedgerUpdate` has only `notes`. The DAO inherits `update` and `remove`, which accept anything. Today no code calls either on this DAO, so the ledger is in fact append-only.
**What happens today:** `update` with a dict changed `quantity` to 9, and `remove` deleted the row (verified at the DAO). No API request reaches either.
**Example:** A future endpoint passes a dict to `product_ledger_dao.update`, and a row of history changes with no trace.
**Rules affected:** inherited R4, R5
**Suggested answer:** `intended` — the promise holds because no caller breaks it, as for `inventory_ledger`, and the tests below pin what the generic methods do. Alternative: `remove` for `ProductLedgerUpdate`, which nothing uses, plus overriding both methods to refuse.
**Answer:** intended
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): the promise holds because no caller breaks it. Rules: inherited R4 ✅, R5 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Production batch manager** (`app/managers/production_batch_manager.py`, not yet specified) | (a) **OWNER, stock (HR-10):** `exists_for_production_batch` is the only guard against posting a batch twice, and it is a read before the writes, with no lock and no index. Two `POST /production-batches/{id}/post-finished-goods/` at once both pass, and the output is booked twice. Precedent BUG-680, but a batch writes one row per line, so the key needs thought: `complete_batch` writes one row per line, two lines of one item included, while `post_outputs_to_finished_goods` merges them. (b) `complete_batch` already posts outputs, so afterwards `post_outputs_to_finished_goods` refuses "already been posted". Only a batch completed with no output lines reaches the fallback. Check that this is the intended flow, and that the two routes `/production-batches/{id}/post-finished-goods/` and `/products/receive-from-batch/{id}/` are both needed.  | `exists_for_production_batch` |
| FU-2 | **Inventory ledger** (`app/models/inventory_ledger.py`) | `performed_at` has the same database-clock default as BUG-1337. Not logged: that spec is approved and pins nothing about it. Whoever fixes BUG-1337 should fix it there too, or log it. | P3 |

## Overview
`ProductLedgerDAO` reads `product_ledger`, the append-only history of finished goods: one row per movement of one item in one factory, with the quantity and average cost before and after. It writes nothing of its own: `ProductManager` writes rows through the inherited `create`. Callers: `ProductService.list_ledger` (`GET /products/ledger/`), `ItemSummaryService` (recent activity), and `exists_for_production_batch`, the guard against posting a batch twice, used by `ProductionBatchManager` and both batch response builders. It never commits.

**Callables:** 2 specified · 3 not specified
**Externals to mock:** none. `performed_at` is captured as a column default, so patching `utcnow` does not reach it: compare with the real clock (Notes).
**Integration-only behavior:** the date-only end date (BUG-991), which needs the endpoint's parsing.

**Model facts (table `product_ledger`, class `app.models.product_ledger.ProductLedger`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `factory_id` | Integer NOT NULL, FK `factories.id` ON DELETE RESTRICT | — |
| `item_id` | Integer NOT NULL, FK `items.id` ON DELETE RESTRICT | — |
| `transaction_type` | String(50) NOT NULL, no check constraint | — |
| `quantity`, `qty_before`, `qty_after` | Integer NOT NULL | — |
| `unit_cost`, `total_cost`, `avg_cost_before`, `avg_cost_after` | Numeric(15, 2) nullable | `NULL` |
| `source_type` | String(50) nullable, indexed | `NULL` |
| `source_id` | Integer nullable, **no foreign key** | `NULL` |
| `transfer_source_type`, `transfer_destination_type` | String(50) nullable | `NULL` |
| `transfer_source_id`, `transfer_destination_id` | Integer nullable | `NULL` |
| `notes` | Text nullable | `NULL` |
| `performed_by` | Integer nullable, FK `profiles.id` ON DELETE SET NULL | `NULL` |
| `performed_at` | DateTime (no time zone) NOT NULL | database `now()` today; Python `utcnow` after BUG-1337 |

- No soft delete, no unique constraint, no check constraint, no trigger; nothing references it.
- Schemas (`app/schemas/product_ledger.py`): `ProductLedgerCreate` has no `workspace_id` and no `performed_by`, and no code uses it. `ProductLedgerUpdate` = `notes`.

**Notes for the test designer:**
- `from app.dao.product_ledger import product_ledger_dao`. Every parameter after `db` is keyword-only.
- Build `Factory`, `Item`, then `ProductLedger(workspace_id, factory_id, item_id, transaction_type, quantity, qty_before, qty_after, performed_at)` directly. Set `performed_at` by hand for order and range cases: today the default gives every row of one test the same time, and after BUG-1337 it does not, so no case may rely on either.
- **Tied timestamps (BUG-640):** three rows with one `performed_at`, then update the lowest `id` under a forced sequential scan. Intended order, **non-strict** xfail. Different timestamps are ordered today: plain pass cases. Every other case compares **sets** of ids.
- **BUG-1337:** `SET LOCAL TIME ZONE 'Asia/Dhaka'`, create a row with no `performed_at`, `db.refresh`, and assert it is within a minute of `utcnow()`. Today it is six hours off → **strict** xfail.
- **BUG-992:** `SET LOCAL TIME ZONE 'Asia/Dhaka'` inside the test; entry at 12:00; aware bounds 11:30Z and 12:30Z. Today `[]` deterministically → **strict** xfail.
- Wrap negative paging in `db.begin_nested()`.

## Not specified
- `product_ledger_dao` — module-level singleton, no logic.
- `ProductLedgerDAO.get_by_id_and_workspace` (override identical to the inherited one) — dead code, to be removed (decided by Claude under the reviewer's delegation (2026-11-02); P4). The inherited method stays (base spec R1–R5).
- Inherited `BaseDAO` methods `get`, `get_multi`, `create`, `update`, `remove` — not overridden; covered by the base spec. Only what this model changes is under "Inherited `BaseDAO` methods on `ProductLedger`".

---

## `ProductLedgerDAO.get_by_workspace(db, *, workspace_id, factory_id=None, item_id=None, start_date=None, end_date=None, transaction_type=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProductService.list_ledger` ← `GET /products/ledger/`; `ItemSummaryService`, with `item_id` and its own `limit`). An override with its own filters, not a copy of the base method.

**Purpose:** Ledger entries of a workspace, newest first, with optional filters.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality on the row's `workspace_id` |
| `factory_id` | int or `None` | `None` = every factory; otherwise equality, so `0` matches nothing |
| `item_id` | int or `None` | `None` = every item; otherwise equality, so `0` matches nothing |
| `start_date` | datetime or `None` | `performed_at >=`, inclusive |
| `end_date` | datetime or `None` | `performed_at <=`, inclusive |
| `transaction_type` | str or `None` | see R5, R5a |
| `skip` | int, default `0` | not validated |
| `limit` | int, default `100` | not validated |

**Returns:** a `list` of `ProductLedger` (possibly empty).

**Rules:**
- **R1.** With no filters, returns the rows with that `workspace_id`. Rows of another workspace never appear.
- **R2.** `factory_id` narrows to that factory; `factory_id=0` returns `[]`.
- **R3.** `item_id` narrows to that item; `item_id=0` returns `[]`.
- **R4.** `start_date` and `end_date` are inclusive to the instant: a row at exactly either bound is returned. Either can be given alone. An inverted range returns `[]`, with no error. A naive bound is compared as given. *(A date with no time reaches this DAO as midnight; the end-of-day rule is BUG-991, at the endpoint, integration-only.)*
- **R4a.** [BUG-992] A bound with a time zone is converted to UTC and made naive before the comparison: entries at 12:00, range 11:30Z–12:30Z, are found under any session `TimeZone`. *(Today: found under `UTC`, `[]` under `America/New_York` and `Asia/Dhaka`.)*
- **R5.** `transaction_type` is compared exactly: `"SALE"` and `" sale"` do not match `sale`.
- **R5a.** A blank `transaction_type` (`""`) applies no filter, like `None`.
- **R6.** Filters combine with AND: two that no row meets together return `[]`.
- **R7.** [BUG-640] (HR-6) Rows are ordered by `performed_at` newest first, then `id` descending, before `skip` / `limit`. *(Today: `performed_at` only; tied rows come back in no fixed order.)*
- **R7a.** Holding today: of two rows with different times, the later one comes first.
- **R8.** At most `limit` rows after skipping `skip`; with the defaults at most 100: given 101 rows, exactly 100. Consecutive windows partition the rows (relies on R7).
- **R9.** `limit=0`, or `skip` past the end, returns `[]`.
- **R10.** A negative `limit` or `skip` makes Postgres reject the query (see Errors).
- **R11.** Ledgers are history: the row of a soft-deleted factory or of a removed item is returned, also when filtered by that factory or item.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## `ProductLedgerDAO.exists_for_production_batch(db, *, workspace_id, batch_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `ProductionBatchManager.post_outputs_to_finished_goods`, as the guard against posting twice; `_batch_response` and `_production_batch_response_with_fg` in the endpoints, for `finished_goods_posted`)

**Purpose:** Whether finished goods were already posted from one batch.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality on the row's `workspace_id` |
| `batch_id` | int | equality on the row's `source_id`; not validated |

**Returns:** `True` or `False`.

**Rules:**
- **R1.** `True` when a row has that `workspace_id`, `source_type = "production_batch"` and `source_id = batch_id`. One row or several give `True`.
- **R2.** `False` when no row matches: another batch, `batch_id=0`, an unknown batch.
- **R3.** The same `source_id` under another `source_type` does not count: a `sales_delivery` row with `source_id` 88 gives `False` for batch 88.
- **R4.** Workspace isolation follows the row: the matching row under another workspace gives `False`.

**Errors:** none.

**Side effects:** none

---

## Inherited `BaseDAO` methods on `ProductLedger`
**Shape:** create / update / delete
**Persistence:** writes
**Visibility:** public (`create` with a dict ← `ProductManager`; `get`, `get_multi`, `update`, `remove`: no caller on this DAO)

**Purpose:** `ProductLedgerDAO` does not override these; the base spec applies. Only what this model changes is stated.

**Rules:**
- **R1.** `create` with a `ProductLedgerCreate` always fails: the schema has no `workspace_id`, so the flush raises `IntegrityError` (`NotNullViolation`, pgcode `23502`) and nothing is saved.
- **R2.** `create` with a dict holding the seven NOT NULL values but no `performed_at` gives a row with `performed_at` set.
- **R2a.** [BUG-1337] (P3) That `performed_at` is `utcnow()`, naive UTC, whatever the session's `TimeZone`: under `Asia/Dhaka` it is within a minute of the real UTC time. *(Today: the database's `now()`, local time in the session's `TimeZone`, six hours ahead under `Asia/Dhaka`.)*
- **R3.** `update` with a `ProductLedgerUpdate` changes `notes`.
- **R4.** ✅ (Q1) `update` with a dict changes any column: `{"quantity": 9}` is saved.
- **R5.** ✅ (Q1) `remove` hard-deletes the row (base spec `remove` R1).

**Errors:** as in the base spec.

**Side effects:** as in the base spec. No stock row changes: the callers do that.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 18–26 | keyword-only parameters; defaults | Notes; `get_by_workspace` R8 |
| 31–33 | `workspace_id` | `get_by_workspace` R1, R11 |
| 34–35 | `factory_id is not None` | `get_by_workspace` R2 |
| 36–37 | `item_id is not None` | `get_by_workspace` R3 |
| 38–39 | `start_date is not None` | `get_by_workspace` R4, R4a |
| 40–41 | `end_date is not None` | `get_by_workspace` R4, R4a |
| 42–43 | `if transaction_type:`: `None`, `""` / a value | `get_by_workspace` R5, R5a |
| 44 | `performed_at` desc, no tie-break (BUG-640); offset, limit; negative values | `get_by_workspace` R6–R10, Errors |
| 50–59 | three-part match; `.first() is not None` | `exists_for_production_batch` R1–R4 |
| 71 | module singleton | Not specified |
| `base.py` 76–84 | `create`: dict / schema (no `workspace_id`); database default for `performed_at` (BUG-1337) | inherited R1, R2, R2a |
| `base.py` 108–119 | `update`: dict / schema | inherited R3, R4 |
| `base.py` 136–139 | `remove`: found | inherited R5 |
