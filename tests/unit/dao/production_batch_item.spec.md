# Spec — `app/dao/production_batch_item.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** **Delegated,** decided by Claude under the reviewer's delegation (2026-11-02): P1 `remove`. The house-rule lines stand.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v_batch.py`, harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\proddao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints and indexes; the order changing after an update under a forced sequential scan, in all three lists; unknown ids and roles, role case, another workspace; an odd role and a zero or negative quantity stored directly; a line of a removed item; 101 lines, the cap of `get_by_item`, `limit=0`; a row of workspace B on a batch of A; `create` with the schema and with a dict; `update` with `None`; `complete_batch` posting an output line to another workspace's factory. **Not run:** anything over HTTP; the intended behaviour of the bugs below.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically

- **HR-6** `get_by_batch` R3 — no `ORDER BY`. Verified: three lines came back `0, 1, 2`, and `1, 2, 0` after the first was updated. This read also decides the order in which `start_batch` takes stock and `complete_batch` posts it, so ledger rows of one batch come out in no fixed order. Intended: `id` ascending (BUG-906 precedent: no name of its own to sort by).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1322 (pattern `unordered-pagination`). Rules: `get_by_batch` R3.
- **HR-6** `get_by_batch_and_role` R3 — no `ORDER BY`, same evidence. Intended: `id` ascending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1323 (pattern `unordered-pagination`). Rules: `get_by_batch_and_role` R3.
- **HR-16** `add_batch_item`, `update_batch_item`, `complete_batch` — `destination_location_id` and `source_location_id` are plain integers, and no write checks them against the workspace. `complete_batch` then posts an output line to that id. Verified: an output line of workspace C with destination `inventory` and a factory of workspace B created a `products` row of workspace C in B's factory, with quantity 3. Intended: a location of another workspace is refused as "not found", nothing written. The DAO rules do not change; the check belongs to the manager.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** BUG-1324 (pattern `cross-workspace-link-not-refused`). No rule of this DAO changes.

Checked and **not** a new line here: **HR-3** — the location types are not grouped or filtered, and `item_role` is checked by the schema. **HR-4** — no soft-delete column here or on the batch. The **standing decision on soft-deleted parents** does not hide lines here: a batch line is what a batch consumed or produced, the batch lists are the place where a batch is shown or hidden (`production_batch.spec.md` Q1), and `start_batch` and `complete_batch` must read every line to post the right stock. A removed item stays on a batch line for the same reason, and `delete_item` refuses while a line sits on a `draft` or `in_progress` batch (BUG-948). **HR-5, HR-7, HR-8** — no filter after paging, no list endpoint with paging, no `LIKE`. **HR-9, HR-10** — the DAO only reads; the table has no audit columns. **HR-15** — no money.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-11-02))

### P1. "Batch lines of this item" is never used — 🗑️ remove
**Background:** `get_by_item` lists every batch line of one catalog item, paged. A search of `app/`, `scripts/` and `tests/` finds no caller; `delete_item` will need its own check (BUG-948), which looks at the batch status. `machine.spec.md` Q4 ruled the same case `remove`.
**What happens today:** No API request, job or script reaches it.
**Example:** Deleting the method changes nothing a user can see.
**Rules affected:** `get_by_item` (all)
**Answer:** remove — per machine DAO Q4 precedent: no caller anywhere
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): not specified; listed under **Not specified** and in `docs/testing/dead-code-removal-checklist.md` (`app/dao/production_batch_item.py:67`). Not a bug — no BUG ID.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Production batch manager** (`app/managers/production_batch_manager.py`, not yet specified) | (a) `add_batch_item` accepts a removed item (read, not run), and a soft-deleted factory as a location. (b) `start_batch` takes `actual_quantity or expected_quantity`, so `0` falls through to the expected one (pattern `falsy-zero-treated-as-missing`); the schema refuses `0`, but `post_outputs_to_finished_goods` tests `is not None` for the same choice, so the two disagree. (c) `update_batch_item` and `remove_batch_item` work on an `in_progress` batch after `start_batch` already took the inputs, so a changed or removed input line never gives stock back. **OWNER, stock.** (d) `update_batch_item` cannot clear a field. (e) `_calculate_batch_item_variances` overflows `Numeric(5, 2)` at about 1000 % (read, not run). | HR-16, reading the callers |

## Overview
`ProductionBatchItemDAO` reads `production_batch_items`, the lines of a batch: what it consumed or produced, expected and actual, and where the stock came from or goes to. Its only caller is `ProductionBatchManager`, which reaches it through `/production-batches/{id}/items/` and `/production-batches/items/{id}/`, and which reads these lines to take stock at start and post it at completion. It protects workspace isolation on those reads. It validates nothing, writes nothing of its own, and never commits. `get_by_id_and_workspace` is a line-for-line copy of the base method: it is specified here because it is what runs.

**Callables:** 3 specified · 3 not specified
**Externals to mock:** none. The table has no timestamps.
**Integration-only behavior:** none

**Model facts (table `production_batch_items`, class `app.models.production_batch_item.ProductionBatchItem`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `batch_id` | Integer NOT NULL, FK `production_batches.id` ON DELETE CASCADE | — |
| `item_id` | Integer NOT NULL, FK `items.id` ON DELETE RESTRICT | — |
| `item_role` | String(20) NOT NULL, no check constraint | — |
| `expected_quantity`, `actual_quantity`, `variance_quantity` | Integer nullable, no check constraint | `NULL` |
| `source_location_type`, `destination_location_type` | String(50) nullable | `NULL` |
| `source_location_id`, `destination_location_id` | Integer nullable, **no foreign key** | `NULL` |
| `variance_percentage` | Numeric(5, 2) nullable | `NULL` |
| `notes` | Text nullable | `NULL` |

- No soft delete, no audit columns, no unique constraint, no trigger; nothing references it. Plain indexes on `id`, `workspace_id`, `batch_id`, `item_id`, `item_role`.
- Schemas (`app/schemas/production_batch_item.py`): `ProductionBatchItemCreate` = `batch_id`, `item_id`, `item_role` (pattern `input|output|waste|byproduct`), `expected_quantity > 0`, `actual_quantity > 0`, the four location fields, `notes` (no `workspace_id`). `ProductionBatchItemUpdate` = the same without the two ids, all optional.

**Notes for the test designer:**
- `from app.dao.production_batch_item import production_batch_item_dao`. Every parameter after `db` is keyword-only.
- Parents, built directly: `Factory`, `ProductionLine(workspace_id, factory_id, name)`, `ProductionBatch(workspace_id, batch_number, production_line_id, batch_date)`, `Item(workspace_id, name, name_normalized, unit)`. A row of workspace B on a batch of A is invalid data (HR-16) and is built directly.
- **Row order (BUG-1322, BUG-1323):** intended order, **non-strict** xfail, forced sequential scan, as `production_line.spec.md`. Every other case compares **sets** of ids.

## Not specified
- `production_batch_item_dao` — module-level singleton, no logic.
- `ProductionBatchItemDAO.get_by_item` — dead code, to be removed (decided by Claude under the reviewer's delegation (2026-11-02); P1).
- Inherited `BaseDAO` methods `get`, `get_by_workspace`, `get_multi`, `create`, `update`, `remove` — not overridden; covered by the base spec. Only what this model changes is under "Inherited `BaseDAO` methods on `ProductionBatchItem`".

---

## `ProductionBatchItemDAO.get_by_batch(db, *, batch_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `get_batch_items` without a role; `start_batch`; `complete_batch`; `_calculate_batch_item_variances`; `post_outputs_to_finished_goods`)

**Purpose:** Every line of one batch.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `batch_id` | int | equality on the row's `batch_id`; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** a `list` of `ProductionBatchItem` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `batch_id` and that `workspace_id`, of every role. Another workspace returns `[]`; a row of workspace B on a batch of A is returned only for B.
- **R2.** An unknown batch, `batch_id=0`, or a batch with no lines returns `[]`.
- **R3.** [BUG-1322] (HR-6) Rows are ordered by `id` ascending. *(Today: no ordering is requested.)*
- **R4.** No paging and no cap: 101 lines give 101 rows.
- **R5.** The state of the batch and of the item is not looked at: the lines of a cancelled batch, and a line of a removed item (`items.is_active = False`), are returned.

**Errors:** none of its own.

**Side effects:** none

---

## `ProductionBatchItemDAO.get_by_batch_and_role(db, *, batch_id, item_role, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProductionBatchManager.get_batch_items` with a role)

**Purpose:** The lines of one batch with one role.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `batch_id` | int | equality on the row's `batch_id`; not validated |
| `item_role` | str | exact equality; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** a `list` of `ProductionBatchItem` (possibly empty).

**Rules:**
- **R1.** Returns the rows matching all three. Lines of another role or batch are never returned. Another workspace returns `[]`.
- **R2.** The role is compared exactly: `"INPUT"` and an unknown role return `[]`, with no error. An unknown batch or `0` returns `[]`.
- **R3.** [BUG-1323] (HR-6) Rows are ordered by `id` ascending. *(Today: no ordering is requested.)*
- **R4.** No paging and no cap: 101 lines give 101 rows.
- **R5.** The state of the batch and of the item is not looked at, as `get_by_batch` R5.

**Errors:** none of its own.

**Side effects:** none

---

## `ProductionBatchItemDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (override identical to `BaseDAO.get_by_id_and_workspace`. Used by: `ProductionBatchManager.update_batch_item`, `remove_batch_item`)

**Purpose:** One line by id, inside one workspace.

**Returns:** the `ProductionBatchItem`, or `None`.

**Rules:**
- **R1.** Given a row with that id in that workspace, it is returned.
- **R2.** Given a row with that id in another workspace, `None` is returned (indistinguishable from not found).
- **R3.** An unknown id or `id=0` returns `None`, with no error.
- **R4.** The state of the batch and of the item is not looked at.

**Errors:** none.

**Side effects:** none

---

## Inherited `BaseDAO` methods on `ProductionBatchItem`
**Shape:** create / update / delete
**Persistence:** writes
**Visibility:** public (`create` with a dict ← `add_batch_item`; `update` with a dict ← `update_batch_item`, `_calculate_batch_item_variances`; `remove` ← `remove_batch_item`)

**Purpose:** `ProductionBatchItemDAO` does not override these; the base spec applies. Only what this model changes is stated.

**Rules:**
- **R1.** `create` with a dict holding `workspace_id`, `batch_id`, `item_id`, `item_role` gives `None` for both quantities, the locations and `notes`.
- **R2.** `create` with a `ProductionBatchItemCreate` always fails: the schema has no `workspace_id`, so the flush raises `IntegrityError` (`NotNullViolation`, pgcode `23502`) and nothing is saved.
- **R3.** With no check constraint, the DAO stores what the schema would refuse: `item_role="zz"`, `expected_quantity=-1`, `actual_quantity=0`.
- **R4.** `update` with a `ProductionBatchItemUpdate` applies only fields set to a value: `actual_quantity=5, notes=None` changes the quantity and keeps `notes`.
- **R5.** `remove` hard-deletes the row (base spec `remove` R1); nothing references it.

**Errors:** as in the base spec.

**Side effects:** as in the base spec.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 33–40 | `workspace_id` AND `batch_id`; no state read; no paging, no `ORDER BY` (BUG-1322); empty / many | `get_by_batch` R1–R5 |
| 57–65 | `workspace_id` AND `batch_id` AND `item_role`; no paging, no `ORDER BY` (BUG-1323) | `get_by_batch_and_role` R1–R5 |
| 109–116 | id AND `workspace_id`; `.first()` on the primary key: row / `None` | `get_by_id_and_workspace` R1–R4 |
| 119 | module singleton | Not specified |
| `base.py` 76–84 | `create`: dict / schema (no `workspace_id`) | inherited R1, R2, R3 |
| `base.py` 108–119 | `update`: schema drops `None` | inherited R4 |
| `base.py` 136–139 | `remove`: found | inherited R5 |
