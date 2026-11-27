# Spec — `app/dao/production_batch.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** **The owner's own answer:** Q1 — batches of a soft-deleted factory are hidden in the query, rows untouched, and `delete_factory` refuses while `draft` or `in_progress` batches exist, listing them (BUG-1330, BUG-1331). **Delegated,** decided by Claude under the reviewer's delegation (2026-11-02): P1 and P2 `remove`, Q2 `bug` (BUG-1333), Q3 `bug` (BUG-1334). None of these is the owner's own answer. The house-rule lines stand.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v_batch.py`, harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\proddao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints, indexes and referencing tables; the order of tied dates after updates under a forced sequential scan, in all four lists; date order; date range bounds, inverted range, `datetime` bounds; status case, unknown status, an odd status stored directly; counts with and without a factory, `factory_id=0`, another workspace; `get_batch_stats`; a batch of a soft-deleted factory in every list and count; a batch of an inactive line and of an inactive formula; `get_batches` with two filters; a row of workspace B on a line of A; 101 rows, the cap, negative values; `generate_batch_number`: empty, next, other year, other workspace, 999, 1000, a non-numeric and an empty suffix, a cancelled batch, `year=0`, the clock patched; `create_batch` after `-1000`; `create` with the schema and with a dict. **Not run:** anything over HTTP; two concurrent transactions; the intended behaviour of the bugs below.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically

- **HR-6** `get_by_workspace` R3, `get_by_production_line` R4, `get_by_formula` R4, `get_by_status` R4 — ordered by `batch_date` only, and many batches share a date. Verified under a forced sequential scan: four batches of one date came back `2, 3, 0, 1` after two updates, and `limit=2` then `skip=2` gave `2, 3` then `0, 1` where it had been `0, 1, 2, 3` before. An update changes which page a batch is on. Intended: `batch_date` newest first, then `id` descending, before `skip` / `limit` (BUG-640 precedent).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1321 (pattern `tied-timestamp-no-tiebreak`), one fix in four lists. Rules: `get_by_workspace` R3, `get_by_production_line` R4, `get_by_formula` R4, `get_by_status` R4.

Checked and **not** a new line here: **HR-3** — `shift` is not grouped or filtered, and `status` is checked by the schema. **HR-4** — the table has no soft-delete column; `cancelled` is a state, not a delete. **HR-5** — every filter is in the query. **HR-7** — `GET /production-batches/` already requires `1 <= limit <= 1000` and `skip >= 0`. **HR-8** — the `LIKE` prefix in `generate_batch_number` is built from an integer year, never from user text. **HR-9** — the DAO writes nothing. **HR-10** — the read behind `start_batch`, `complete_batch`, `cancel_batch` and `delete_batch` has no lock, and the first two move stock: that belongs to the manager (FU-1 (c)). **HR-15** — no money. **HR-16** — the reads follow the row; `create_batch` and `update_batch` check the line and the formula against the workspace.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-11-02))

### P1. "Batches in this date range" is never used — 🗑️ remove
**Background:** `get_by_date_range` has no caller. The calendar reads batches by date with a query of its own (`CalendarService._collect_production_batches`). `machine.spec.md` Q4 and `inventory_ledger.spec.md` Q1 ruled such methods `remove`.
**What happens today:** No API request, job or script reaches it.
**Example:** Deleting the method changes nothing a user can see.
**Rules affected:** `get_by_date_range` (all)
**Answer:** remove — per machine DAO Q4 precedent: no caller anywhere
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): not specified; listed under **Not specified** and in `docs/testing/dead-code-removal-checklist.md` (`app/dao/production_batch.py:148`). Not a bug — no BUG ID.

### P2. The `year` option of the batch number is never used — 🗑️ remove
**Background:** `generate_batch_number` takes an optional `year`. Its only caller, `create_batch`, passes none.
**What happens today:** No request can choose the year. The clock always decides it.
**Example:** No API request reaches a batch number of another year.
**Rules affected:** `generate_batch_number` (the parameter only)
**Answer:** remove — per machine item DAO P7 precedent: the parameter and its `if`
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): the parameter is not specified (the method stays specified); listed under **Not specified** and in `docs/testing/dead-code-removal-checklist.md` (`app/dao/production_batch.py:203,216-217`). The tests pin the year through the clock (BUG-1334). Not a bug — no BUG ID.

### New questions

### Q1. OWNER, stock — Batches of a soft-deleted factory — 🐞 BUG-1330, BUG-1331 (owner)
**Background:** A batch belongs to a production line, and the line to a factory. Starting a batch takes its inputs out of storage; completing it posts its outputs to `products`. `delete_factory` checks nothing, so a factory with a running batch can be deleted. The standing decision hides things of a soft-deleted parent, and ledgers are exempt because they are history. A batch is both: a `completed` or `cancelled` batch is a record, while a `draft` or `in_progress` batch is live work, and its inputs may already be gone from storage.
**What happens today:** Every list here, and `count_by_status`, ignores the factory. A batch of a deleted factory is listed, opened and counted (verified: the dashboard's in-progress count went from 1 to 2), and it can still be completed, because the line lookup is raw.
**Example:** Factory 9 is deleted while batch `BATCH-2026-014` is `in_progress`, with 500 kg of cotton already taken out of storage. Today it stays on the batches page, and completing it posts the yarn to a product row in deleted Factory 9. If hidden, nobody can find it to complete or cancel it until the factory is restored, and the 500 kg stay consumed with nothing to show for them.
**Rules affected:** `get_by_workspace` R2, `get_by_production_line` R2, `get_by_formula` R2, `get_by_status` R2, `count_by_status` R4
**Suggested answer:** `bug — hidden, rows untouched, per the standing decision`: the four lists and the count leave out a batch whose line's factory is soft-deleted, inside the query, so paging stays right, and it is back unchanged when the factory returns. `get_by_id_and_workspace` and `generate_batch_number` stay raw: the number must still see those rows or it would repeat one. An inactive line, formula or factory hides nothing. **Pair it with** `delete_factory` refusing while the factory has `draft` or `in_progress` batches, listing them as blockers, so no live batch is ever hidden (FU-2). Alternative: `intended` — a batch is a production record, like a ledger, and stays listed.
**Answer:** bug — hidden in the query, rows untouched; `delete_factory` refuses while `draft` or `in_progress` batches exist, listing them (owner, 2026-11-02)
**Resolution:** 🐞 BUG-1330 (pattern `join-ignores-soft-deleted`): the four lists and `count_by_status`. An inactive line, formula or factory hides nothing. `get_by_id_and_workspace` and `generate_batch_number` stay raw. 🐞 BUG-1331 (pattern `delete-ignores-dependents`): the refusal is not a rule of this DAO; it is routed to `factory_manager` (FU-2), and **that module reopens**. BUG-1332 is its frontend note. Rules: `get_by_workspace` R2, R2a, R2b; `get_by_production_line` R2, R2a; `get_by_formula` R2, R2a; `get_by_status` R2, R2a; `count_by_status` R4, R4a, R4b; `get_by_id_and_workspace` R4 ✅; `generate_batch_number` R6 ✅.

### Q2. Batch numbers stop working after 999 in a year — 🐞 BUG-1333
**Background:** `BATCH-2026-001` is built by finding the workspace's highest number for the year and adding one. "Highest" is decided by sorting the numbers **as text**. The database allows each number once per workspace.
**What happens today:** As text, `BATCH-2026-999` sorts above `BATCH-2026-1000`. After 1000 exists, the next number is computed from 999 again, so it is `1000` again, and the insert fails with a unique violation. `create_batch` does not catch it (verified: `IntegrityError` 23505 on `uq_batch_workspace_number`).
**Example:** A busy factory creates its 1000th batch of the year in October. From then on every "new batch" answers 500, until the new year.
**Rules affected:** `generate_batch_number` R5
**Suggested answer:** `bug — the next number is the numerically highest suffix of that workspace and year, plus one`: after `1000` comes `1001`, still padded to at least three digits. Pattern `text-sorted-sequence-number`. This needs a new ordering in the query, not a change of format. A suffix that is not all digits is ignored rather than raising (R7): no path writes one, so only stored bad data could stop batch creation.
**Answer:** bug — the next number is the numerically highest suffix of that workspace and year, plus one
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): 🐞 BUG-1333 (pattern `text-sorted-sequence-number`). A suffix that is not all digits is ignored, not raised on. Rules: `generate_batch_number` R5, R7, Errors.

### Q3. The batch number's year comes from the server's local clock — 🐞 BUG-1334
**Background:** Nearly everything else in the app uses `utcnow()`. `generate_batch_number` uses `datetime.now()`, the local time of the machine running the API. A batch also has its own `batch_date`, which the user picks.
**What happens today:** The year in the number is the server's local year at the moment of creation, whatever the `batch_date`. (The clock source is read from the code; the patched clock was verified.)
**Example:** On 2 January 2027 a user logs the batch run on 30 December 2026. It gets `BATCH-2027-002` with `batch_date` 2026-12-30. And two API servers in different time zones would disagree around midnight on 31 December.
**Rules affected:** `generate_batch_number` R2
**Suggested answer:** `bug — the year comes from utcnow()`, the project's clock (BUG-1102 precedent). `batch_date` stays out of it: a number records when the batch was entered, and numbering by `batch_date` would make numbers run backwards inside a year. Alternative: `bug — the year of batch_date`, if the owner prefers the number to match the production year; `generate_batch_number` then needs the date passed in.
**Answer:** bug — the year comes from `utcnow()`
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): 🐞 BUG-1334 (pattern `local-clock-instead-of-utc`). `batch_date` stays out of it. Rules: `generate_batch_number` R2.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Production batch manager, service, endpoint** (`app/managers/production_batch_manager.py`, not yet specified) | (a) **Verified:** `get_batches` applies only the first filter, in the order line, formula, status: `?production_line_id=1&status=in_progress` returned 6 batches, none of them in progress. Pattern `silently-ignored-input`. (b) **Verified:** `get_batch_stats` returns `total_count` equal to `in_progress_count`, so "total" is not a total. `count_by_status` has only this one caller. (c) **OWNER, stock (HR-10):** `start_batch`, `complete_batch`, `cancel_batch` read the row without a lock, then move stock: two starts at once take the inputs twice. Needs a locked variant of `get_by_id_and_workspace`. The default read here stays unlocked. (d) **OWNER, stock:** `cancel_batch` on an `in_progress` batch does not return the inputs `start_batch` took (read, not run). (e) A lost race on `generate_batch_number` raises `IntegrityError`: it must retry or lock, never answer 500. (f) `delete_batch` writes no `updated_by`. (g) `update_batch` cannot clear any field, and stamps `updated_by` when nothing changes (HR-9, read, not run). (h) `output_variance_percentage` and `efficiency_percentage` are `Numeric(5, 2)`: a batch with output 1000 times the expected one overflows at completion (read, not run). | HR-10, Q1, reading the callers |
| FU-2 | **Factory manager** (`app/managers/factory_manager.py`), **reopened** | **BUG-1331, logged; owner's answer 2026-11-02.** `delete_factory` refuses while the factory has `draft` or `in_progress` batches, listing them. This overturns `delete_factory` R5 of that spec for batches. Note left at the top of `tests/unit/managers/factory_manager.spec.md`; the rule is written in that module's own pass. BUG-1332 is the frontend note. | Q1 |
| FU-3 | **Calendar service** (`app/services/calendar_service.py`) | `_collect_production_batches` has its own query with no `ORDER BY`, and shows batches of a soft-deleted factory: BUG-1330's rule applies there too, to be logged in that module's own review. | P1, Q1 |

## Overview
`ProductionBatchDAO` reads `production_batches`, one row per production run, and numbers new batches. A batch moves `draft` → `in_progress` → `completed`, or to `cancelled`; those moves, and the stock they post, are in `ProductionBatchManager`. Its only caller is that manager (`/production-batches/`, `/products/receive-from-batch/{id}/`). It protects workspace isolation on its reads and per-workspace, per-year numbering. It validates nothing, writes nothing, and never commits. `get_by_id_and_workspace` is a line-for-line copy of the base method: it is specified here because it is what runs.

**Callables:** 7 specified · 3 not specified
**Externals to mock:** the clock in `generate_batch_number`: `utcnow` after BUG-1334, `app.dao.production_batch.datetime` (`.now()`) today; see Notes. `utcnow` through the model's timestamps only if a case asserts their value.
**Integration-only behavior:** none. (`skip >= 0`, `1 <= limit <= 1000` are enforced by `GET /production-batches/`, not here.)

**Model facts (table `production_batches`, class `app.models.production_batch.ProductionBatch`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `batch_number` | String(50) NOT NULL, plain index | — |
| `production_line_id` | Integer NOT NULL, FK `production_lines.id` ON DELETE RESTRICT | — |
| `formula_id` | Integer nullable, FK `production_formulas.id` ON DELETE SET NULL | `NULL` |
| `batch_date` | Date NOT NULL | — |
| `shift` | String(20) nullable | `NULL` |
| `status` | String(20) NOT NULL, no check constraint | `'draft'` (Python default only) |
| `expected_output_quantity`, `expected_duration_minutes`, `actual_output_quantity`, `actual_duration_minutes`, `output_variance_quantity` | Integer nullable | `NULL` |
| `actual_start_time`, `actual_end_time`, `started_at`, `completed_at` | DateTime nullable | `NULL` |
| `output_variance_percentage`, `efficiency_percentage` | Numeric(5, 2) nullable | `NULL` |
| `notes` | Text nullable | `NULL` |
| `created_by`, `updated_by`, `started_by`, `completed_by` | Integer nullable, FK `profiles.id` ON DELETE SET NULL | `NULL` |
| `created_at`, `updated_at` | DateTime NOT NULL | Python `utcnow`; `updated_at` also on update |

- `uq_batch_workspace_number`: UNIQUE `(workspace_id, batch_number)`. No soft delete, no check constraint, no trigger.
- Referenced by `production_batch_items.batch_id` and `production_batch_stage_logs.batch_id` (CASCADE).
- Schemas (`app/schemas/production_batch.py`): `ProductionBatchCreate` = `production_line_id`, `formula_id`, `batch_date`, `shift` (max 20), `status` (pattern, default `draft`), expected and actual values, `notes` (no `workspace_id`, no `batch_number`). `ProductionBatchUpdate` = the same without `production_line_id`, all optional.
- The test database's collation is `English_United States.1252` (libc).

**Notes for the test designer:**
- `from app.dao.production_batch import production_batch_dao`. Every parameter after `db` is keyword-only.
- Parents, built directly: `Factory(workspace_id, name, abbreviation)`, `ProductionLine(workspace_id, factory_id, name)`, `ProductionFormula(workspace_id, formula_code, name)`, then `ProductionBatch(workspace_id, batch_number, production_line_id, batch_date, status)`. Give each row its own `batch_number` (`uq_batch_workspace_number`).
- **Tied dates (BUG-1321):** several batches of one date, then update the lower `id`s under a forced sequential scan (`SET LOCAL enable_indexscan = off; SET LOCAL enable_bitmapscan = off; SET LOCAL enable_indexonlyscan = off`). Intended order, **non-strict** xfail. Date order alone holds today: plain pass cases with distinct dates. Every other case compares **sets** of ids.
- **The 1000th number (BUG-1333):** insert rows numbered `BATCH-2026-999` and `BATCH-2026-1000` directly; no need for 1000 rows. Today's result is deterministic → **strict** xfail, also for R7.
- **The clock (BUG-1334, P2):** no case passes `year`. Every case of `generate_batch_number` patches both clocks, so it runs today and after the fix: `patch("app.dao.production_batch.datetime", create=True)` with `.now()` set, and `patch("app.dao.production_batch.utcnow", create=True, return_value=…)`, the module does not import `utcnow` yet. Same moment in both → a plain case. For R2, the two sides of New Year as in the rule → **strict** xfail.
- **Hidden batches (BUG-1330):** soft-deleted factory = `is_deleted=True`, with a live line and a batch in it, plus a batch of a live factory in the same case. Today's result is deterministic → **strict** xfail, compared as **sets** of ids. "Back once the factory is live" is a plain pass case.
- Wrap negative paging in `db.begin_nested()`. The DAO's bare `.scalar()` result is never `None`: the `or 0` in `count_by_status` cannot be reached from a real query, and a mutation there is an equivalent mutant.

## Not specified
- `production_batch_dao` — module-level singleton, no logic.
- `ProductionBatchDAO.get_by_date_range` — dead code, to be removed (decided by Claude under the reviewer's delegation (2026-11-02); P1).
- (`generate_batch_number`'s `year` parameter — dead parameter, to be removed (decided by Claude under the reviewer's delegation (2026-11-02); P2).)
- Inherited `BaseDAO` methods `get`, `get_multi`, `create`, `update`, `remove` — not overridden; covered by the base spec. Only what this model changes is under "Inherited `BaseDAO` methods on `ProductionBatch`".

---

## `ProductionBatchDAO.get_by_workspace(db, *, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProductionBatchManager.get_batches` ← `GET /production-batches/` with no filter). Not a copy of the base method: it has an order of its own.

**Purpose:** All batches of a workspace, newest first, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality on the row's `workspace_id` |
| `skip` | int, default `0` | not validated |
| `limit` | int, default `100` | not validated |

**Returns:** a `list` of `ProductionBatch` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `workspace_id`, of every status. Rows of another workspace never appear.
- **R2.** The state of the line and of the formula is not looked at: a batch of an inactive line or of an inactive formula is returned.
- **R2a.** [BUG-1330] (Q1) A batch whose line's factory is soft-deleted (`factories.is_deleted = True`) is not returned and takes no place in the page, whatever its status. *(Today: it is returned.)*
- **R2b.** What surrounds R2a, holding today and after the fix: (1) the call changes nothing: the batch and its lines stay as they were; (2) a factory with `is_active = False`, `is_deleted = False` hides nothing; (3) once the factory is no longer deleted, the batch is returned again, unchanged.
- **R3.** [BUG-1321] (HR-6) Rows are ordered by `batch_date` newest first, then `id` descending, before `skip` / `limit`. *(Today: `batch_date` only; rows of one date come back in no fixed order.)*
- **R3a.** Holding today: of two batches with different dates, the later one comes first.
- **R4.** At most `limit` rows after skipping `skip`; with the defaults at most 100: given 101 rows, exactly 100. Consecutive windows partition the rows (relies on R3).
- **R5.** An unknown workspace, a workspace with no rows, `skip` past the end, or `limit=0` returns `[]`.
- **R6.** A negative `limit` or `skip` makes Postgres reject the query (see Errors).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## `ProductionBatchDAO.get_by_production_line(db, *, production_line_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `get_batches` ← `GET /production-batches/?production_line_id=…`)

**Purpose:** The batches of one line, newest first.

**Inputs:** `production_line_id` (int, equality, not validated), then as `get_by_workspace`.

**Returns:** a `list` of `ProductionBatch` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `production_line_id` and that `workspace_id`. Only the row's own `workspace_id` is compared: a row of workspace B on a line of A is returned for B and not for A.
- **R2.** The line's own state is not looked at, as `get_by_workspace` R2.
- **R2a.** [BUG-1330] (Q1) When the line's factory is soft-deleted, `[]` is returned. *(Today: its batches are returned.)* What surrounds it: as `get_by_workspace` R2b.
- **R3.** An unknown line, `0`, a line with no batches, `skip` past the end, or `limit=0` returns `[]`.
- **R4.** [BUG-1321] (HR-6) Ordered as `get_by_workspace` R3. Date order alone holds today, as R3a there.
- **R5.** At most `limit` rows after skipping `skip`; with the defaults at most 100.
- **R6.** A negative `limit` or `skip` makes Postgres reject the query, as in `get_by_workspace`.

**Errors:** as `get_by_workspace`.

**Side effects:** none

---

## `ProductionBatchDAO.get_by_formula(db, *, formula_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `get_batches` ← `GET /production-batches/?formula_id=…`, when no line is given)

**Purpose:** The batches made with one formula, newest first.

**Inputs:** `formula_id` (int, equality, not validated), then as `get_by_workspace`.

**Returns:** a `list` of `ProductionBatch` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `formula_id` and that `workspace_id`. A batch with no formula is never returned. Another workspace returns `[]`.
- **R2.** The formula's own state is not looked at, as `get_by_workspace` R2.
- **R2a.** [BUG-1330] (Q1) A batch whose line's factory is soft-deleted is not returned and takes no place in the page. *(Today: it is returned.)* What surrounds it: as `get_by_workspace` R2b.
- **R3.** An unknown formula, `0`, `skip` past the end, or `limit=0` returns `[]`.
- **R4.** [BUG-1321] (HR-6) Ordered as `get_by_workspace` R3. Date order alone holds today.
- **R5.** At most `limit` rows after skipping `skip`; with the defaults at most 100.
- **R6.** A negative `limit` or `skip` makes Postgres reject the query, as in `get_by_workspace`.

**Errors:** as `get_by_workspace`.

**Side effects:** none

---

## `ProductionBatchDAO.get_by_status(db, *, status, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `get_batches` ← `GET /production-batches/?status=…`, when neither a line nor a formula is given)

**Purpose:** The batches in one status, newest first.

**Inputs:** `status` (str, exact equality, not validated), then as `get_by_workspace`.

**Returns:** a `list` of `ProductionBatch` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `status` and that `workspace_id`. Rows of another status or workspace are never returned.
- **R2.** The state of the line and of the formula is not looked at, as `get_by_workspace` R2.
- **R2a.** [BUG-1330] (Q1) A batch whose line's factory is soft-deleted is not returned and takes no place in the page. *(Today: it is returned.)* What surrounds it: as `get_by_workspace` R2b.
- **R3.** The status is compared exactly: `"DRAFT"`, an unknown status, and `""` return `[]`, with no error. A status outside the four is matched like any other: the column has no check constraint.
- **R4.** [BUG-1321] (HR-6) Ordered as `get_by_workspace` R3. Date order alone holds today.
- **R5.** At most `limit` rows after skipping `skip`; with the defaults at most 100.
- **R6.** A negative `limit` or `skip` makes Postgres reject the query, as in `get_by_workspace`.

**Errors:** as `get_by_workspace`.

**Side effects:** none

---

## `ProductionBatchDAO.count_by_status(db, *, workspace_id, status, factory_id=None)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `ProductionBatchManager.get_batch_stats` ← `GET /production-batches/stats/`, always with `in_progress`)

**Purpose:** How many batches of a workspace are in one status, optionally in one factory.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality on the batch's `workspace_id` |
| `status` | str | exact equality; not validated |
| `factory_id` | int or `None`, default `None` | `None` = every factory; otherwise equality on the factory of the batch's line |

**Returns:** an `int`, `0` when nothing matches.

**Rules:**
- **R1.** With `factory_id=None`, counts the rows with that `workspace_id` and `status`. No cap: 101 rows give 101.
- **R2.** With a `factory_id`, counts only the batches whose production line is in that factory. `factory_id=0`, an unknown factory, or a factory with no matching batch gives `0`: `0` is a filter, not "no filter".
- **R3.** No match, an unknown workspace, or an unknown status gives `0`, never `None`.
- **R4.** The line's own state is not looked at: a batch of an inactive line is counted, with and without `factory_id`.
- **R4a.** [BUG-1330] (Q1) A batch whose line's factory is soft-deleted is not counted, with or without `factory_id`: given 1 live and 1 hidden in-progress batch, `1`; with the deleted factory's id, `0`. *(Today: `2` and `1`.)*
- **R4b.** What surrounds R4a: as `get_by_workspace` R2b.
- **R5.** With a `factory_id`, only the batch's own `workspace_id` is compared: a row of workspace B on a line of A is counted for B under A's factory.

**Errors:** none of its own.

**Side effects:** none

---

## `ProductionBatchDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (override identical to `BaseDAO.get_by_id_and_workspace`. Used by every single-batch method of `ProductionBatchManager`)

**Purpose:** One batch by id, inside one workspace.

**Returns:** the `ProductionBatch`, or `None`.

**Rules:**
- **R1.** Given a row with that id in that workspace, it is returned.
- **R2.** Given a row with that id in another workspace, `None` is returned (indistinguishable from not found).
- **R3.** An unknown id or `id=0` returns `None`, with no error.
- **R4.** ✅ (Q1) A cancelled batch, and a batch of a soft-deleted factory, are returned. A raw lookup: the manager answers on the status.

**Errors:** none.

**Side effects:** none

---

## `ProductionBatchDAO.generate_batch_number(db, *, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `ProductionBatchManager.create_batch`)

**Purpose:** The next batch number of a workspace and year, as `BATCH-<year>-<3 digits or more>`.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** a `str`. Nothing is reserved or saved.

**Rules:**
- **R1.** With no rows for that workspace and year, the result is `BATCH-<year>-001`.
- **R2.** [BUG-1334] (Q3) The year is the UTC year of `utcnow()`: with `utcnow()` at 2030-12-31 23:30 and the server's local clock at 2031-01-01 00:30, the result is `BATCH-2030-001`. *(Today: the year of `datetime.now()`, so `BATCH-2031-001`.)*
- **R3.** With rows, the result is the highest number plus one, padded to at least three digits: after `-001` and `-007`, `-008`. After `-999`, `-1000`.
- **R4.** Each workspace and year has its own sequence: rows of another year or workspace do not count. Rows of every status count, `cancelled` included, so a number is never reused: after a cancelled `-004`, `-005`.
- **R5.** [BUG-1333] (Q2) "Highest" is numeric: with `-999` and `-1000` both present, the result is `-1001`. *(Today: `-1000` again, by text order, and inserting it raises `IntegrityError`, pgcode `23505`, on `uq_batch_workspace_number`.)*
- **R6.** ✅ (Q1) The state of the line and the factory is not looked at: batches of a soft-deleted factory count, or a number would repeat.
- **R7.** [BUG-1333] (Q2) A row whose suffix is not all digits is ignored: with only `BATCH-<year>-ABC` or `BATCH-<year>-`, the result is `-001`; with `-005` as well, `-006`. No path writes such a number. *(Today: when that row sorts highest, `ValueError`, `invalid literal for int()`.)*
- **R9.** Calling it twice with no insert between gives the same number twice.

**Errors:** none of its own. *(Today: `ValueError` in the case of R7.)*

**Side effects:** none

---

## Inherited `BaseDAO` methods on `ProductionBatch`
**Shape:** create / update
**Persistence:** writes
**Visibility:** public (`create`, `update` with a dict ← `ProductionBatchManager`; `get`, `get_multi`, `remove`: no caller on this DAO)

**Purpose:** `ProductionBatchDAO` does not override these; the base spec applies. Only what this model changes is stated.

**Rules:**
- **R1.** `create` with a dict holding `workspace_id`, `batch_number`, `production_line_id`, `batch_date` gives `status = "draft"`, and `created_at`, `updated_at` set.
- **R2.** `create` with a `ProductionBatchCreate` always fails: the schema has no `workspace_id`, so the flush raises `IntegrityError` (`NotNullViolation`, pgcode `23502`) and nothing is saved.
- **R3.** A second row with one `batch_number` in one workspace raises `IntegrityError` (`UniqueViolation`, pgcode `23505`) at the flush. The same number in another workspace is accepted.
- **R4.** With no check constraint, the DAO stores a status outside the four: `"weird"`.

**Errors:** as in the base spec, plus R3.

**Side effects:** as in the base spec.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 19–20, 43–45, 72–74, 101–103 | keyword-only parameters; defaults `skip=0`, `limit=100` | Notes; R4 / R5 of each list |
| 34–41 | `workspace_id`; factory state not read (BUG-1330); `batch_date` desc, no tie-break (BUG-1321); `limit=0`; negative values; empty / many | `get_by_workspace` R1–R6, Errors |
| 60–70 | `workspace_id` AND `production_line_id`; order as above | `get_by_production_line` R1–R6 |
| 89–99 | `workspace_id` AND `formula_id`; order as above | `get_by_formula` R1–R6 |
| 118–128 | `workspace_id` AND `status`; order as above | `get_by_status` R1–R6 |
| 138–141 | count with `workspace_id` AND `status`; factory state not read (BUG-1330) | `count_by_status` R1, R3, R4, R4a, R4b |
| 142–145 | `factory_id is not None`: join to the line / no join | `count_by_status` R1, R2, R5 |
| 146 | `or 0`: `count` is never `None`, the right side cannot run | `count_by_status` R3; Notes |
| 193–200 | id AND `workspace_id`; `.first()` on the primary key: row / `None` | `get_by_id_and_workspace` R1–R4 |
| 216–217 | `year is None`: always true, parameter removed (P2); local clock (BUG-1334) | `generate_batch_number` R2 |
| 220–229 | prefix `LIKE`, workspace; text order desc, top 1 (BUG-1333) | `generate_batch_number` R1, R3, R4, R5, R6, R7 |
| 231–236 | row found: suffix + 1, `int()` may raise / none: 1 | `generate_batch_number` R1, R3, R7 |
| 238 | padded to three digits | `generate_batch_number` R1, R3 |
| 241 | module singleton | Not specified |
| `base.py` 76–84 | `create`: dict / schema (no `workspace_id`); Python default for `status`; unique constraint | inherited R1–R4 |
