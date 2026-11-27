# Spec — `app/dao/miscellaneous_project_cost.py`

> **Status:** APPROVED (2026-11-10; nothing open — OQ-28 answered: projects are skipped until after launch, today's behaviour kept)
> **Source commit:** e48a092

> **Review round 2026-11-10 (apply-review + fill-gaps).** **Owner:** OQ-28 — "projects are skipped for now; revisit after launch. Tests keep today's behaviour (negative and zero stored), no bug" (owner, 2026-11-10); inherited R2a states it, tagged *revisit after launch (owner 2026-11-10)*. The owner also put this module's bugs (BUG-2460, BUG-2461) on *revisit after launch*: they stay as tagged rules and their tests stay. **Delegated (2026-11-10):** what `project_id=None` means once BUG-2461 is fixed (`get_by_project` R3). **Gaps:** the three gaps of `miscellaneous_project_cost.cases.md` closed (Gap log at the end); gap 1–2 facts checked on `marker_test` (own script `g3.py` in `C:/Users/User/AppData/Local/Temp/makorsh-pipeline/omd/G/`, rolled back, private `COVERAGE_FILE`).

> **Review round 2026-11-09.** No owner answer in this round. **Delegated:** Q1 decided by Claude under the reviewer's delegation (2026-11-09, filters); it is not the owner's own answer. The house-rule line stands. **Owner:** Q2 (OQ-28) is parked in `docs/testing/owner-questions.md`, not blocking: the amount is validated (or not) by `MiscellaneousProjectCostCreate` / `Update`, and no rule of this DAO depends on it.
>
> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated. This DAO overrides nothing; the service uses the inherited `get_by_workspace`, `get_by_id_and_workspace`, `create`, `update`, `remove`.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Raw lookups stay raw (HR-4 scope); access to a deleted project is refused by `require_project_access` / `require_component_access` (BUG-1278, existing). HR-16: a row linking to another workspace's row is invalid data. HR-15: money rounds half up (the `Numeric(15,2)` column does).
>
> **Verified by running** (my own scripts `h.py`, `schema.py`, `v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\omd\D\`, one transaction on `marker_test`, rolled back, private `COVERAGE_FILE`): the table's columns, precision, constraints, foreign-key actions, indexes and triggers (none); both methods for a project-only cost, a component-only cost, a cost with both, another workspace's cost and a cost with neither; another workspace's project / component id (`[]`); `None` (rows where that column is empty) and `0` (`[]`); order before and after an `UPDATE` (changed: `[48, 50]` → `[50, 48]`); a soft-deleted project (still listed); inherited `create` through `MiscellaneousProjectCostCreate` with `1000.005` (stored `1000.01`), `0.125` (`0.13`), `-5` (stored), name `"  "` (stored), another workspace's `project_id` (stored); `10^13` (`DataError` 22003); inherited `update` with `description=None` (kept) and `amount=2.5`. **Read, not run:** `MiscellaneousProjectCostService`, `app/api/v1/endpoints/miscellaneous_project_costs.py`, the web app's cost dialog and component panel. **Not run:** anything over HTTP.

## Review
> All answered or parked; applied 2026-11-09.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | A project's cost list leaves out every cost booked on one of its components — which is every cost the web app creates | bug — BUG-2461 | delegation (filter) |
| Q2 | **OWNER** — a miscellaneous cost may be negative or zero | intended for now — revisit after launch (owner 2026-11-10); negative and zero stored, no bug | **owner** |

Decided by house rules: both lists have no sort order (BUG-2460).

### House-rule violations — applied automatically

- **HR-6** `get_by_project` R4, `get_by_component` R3 — no `ORDER BY`. Verified: two costs of one project came back `[48, 50]`, then `[50, 48]` after the first was updated, so editing a cost moves it in the list and pages can repeat or skip rows. Intended: `id` ascending (order of entry), before `skip` / `limit` (BUG-1276 precedent: a component's item lines).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2460 (pattern `unordered-pagination`; one bug for both methods). Rules: `get_by_project` R4, `get_by_component` R3.
- **HR-6** inherited `get_by_workspace` — no sort order; used by the service for the workspace-wide list.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-100 (existing, fixed in `app/dao/base.py`). Rules: inherited methods R1.

Checked and **not** a new line here: **HR-4** — the table has no soft-delete column (costs are hard-deleted by the inherited `remove`); a soft-deleted project's costs are still returned (verified), which is right for a raw lookup: the service's access check refuses the deleted project (BUG-1278, existing). **HR-5** — both filters are in the query; the service's workspace-wide list pages first and then drops costs in Python (FU-1 (c)). **HR-7** — the DAO does not validate paging (`limit=0` → `[]`, negative → `DataError`); the endpoint's bounds are FU-1 (d). **HR-8** — no `LIKE`. **HR-9** — no "last changed by" column. **HR-10** — nothing here changes state. **HR-15** — the column rounds half up (verified `0.125` → `0.13`). **HR-16** — both methods filter on the row's own `workspace_id` (another workspace's id → `[]`, verified); the service can still *store* a cross-workspace link (FU-1 (b)). **HR-1** — the name is not trimmed and may be blank: a schema matter (FU-1 (a)). **Falsy `0`** — the methods test nothing for truthiness; `0` matches no row. `None` is R3 of each.

### New questions

### Q1. A project's cost list leaves out costs booked on its components — 🐞 BUG-2461
**Background:** A cost row carries `project_id` and `project_component_id`, both optional. The web app's "Add misc cost" dialog (component panel) sends only `project_component_id`, so every cost made in the app has an empty `project_id`. `GET /miscellaneous-project-costs/?project_id=…` goes to `get_by_project`, which matches `project_id` only.
**What happens today:** Asking for a project's costs returns only the costs typed directly against the project through the API; costs of its components are missing. (Verified: project P with cost A (project only), cost B (component of P only), cost C (both) → `[A, C]`; B missing.)
**Example:** Component "Deck" of project "Bridge A" has misc costs of 1,200.00 and 300.00, added in the app. A report or client asking for "Bridge A"'s costs gets an empty list.
**Rules affected:** `get_by_project` R1a
**Suggested answer:** bug — a project's list holds the costs with that `project_id` **and** the costs whose component belongs to the project (same workspace), each cost once.
**Answer:** bug — a project's list holds the costs with that `project_id` and the costs booked on any of its components (same workspace), each once
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-09; a filter, no money value changes): 🐞 BUG-2461 (pattern `parent-filter-ignores-child-links`). Components of the project count whatever their own state (components have no soft delete). Rules: `get_by_project` R1a.

### Q2. **OWNER** — A miscellaneous cost may be negative or zero — ⏸ OQ-28, revisit after launch (owner 2026-11-10)
**Background:** `MiscellaneousProjectCostCreate.amount` and `Update.amount` are a plain `float` with no bound; the column is `Numeric(15,2)` NOT NULL. The web dialog refuses an amount of 0 or less before sending, but the API does not. For other money and stock inputs, negatives were refused (project budget BUG-1962, inventory BUG-711). Whether a negative misc cost (a credit, a refund) is meant to exist is a money decision.
**What happens today:** `-5` and `0` are stored as given (verified at DAO level through the schema: `-5.00`).
**Example:** A user posting `{"project_component_id": 7, "name": "Crane", "amount": -1200}` through the API gets 201, and the component's cost list shows −1,200.00, lowering any total built from it.
**Rules affected:** none in this DAO (the rule belongs to `MiscellaneousProjectCostCreate` / `Update`, reached through `MiscellaneousProjectCostService`, not yet specified).
**Suggested answer:** bug — the amount must be greater than 0 (422, nothing written), as the web form already requires; a credit is booked some other way. Rows already stored are left alone.
**Alternatives:** (a) `>= 0` (zero allowed as a placeholder); (b) intended — negative costs are credits.
**Answer:** owner, 2026-11-10: projects are skipped for now; revisit after launch. Tests keep today's behaviour (negative and zero stored), no bug.
**Resolution:** no bug. Inherited R2a states today's behaviour, tagged *revisit after launch (owner 2026-11-10)*; the service spec (FU-1) states it the same way.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Miscellaneous project cost service / schemas / endpoint** (`app/services/miscellaneous_project_cost_service.py`, `app/schemas/miscellaneous_project_cost.py`, `app/api/v1/endpoints/miscellaneous_project_costs.py`; not yet specified) | (a) **HR-1:** `name` is not trimmed and `"  "` is stored (verified). (b) **HR-16:** `create_cost` checks only `project_id` when it is given; `project_component_id` is then not checked at all, so another workspace's component (or a component of a different project) can be linked; and a `project_id` of another workspace was stored by the DAO (verified; whether `require_project_access` refuses it first is the service's rule). (c) **HR-5:** the workspace-wide list (no project or component given) pages with `get_by_workspace` first and then drops inaccessible and unlinked costs in Python, so pages come back short. (d) **HR-7:** check the endpoint's `limit` bounds. (e) **Money input:** `amount: float` — more than 2 decimals is rounded silently (`1000.005` → `1000.01`, verified) and 13 or more integer digits fails at the flush (`DataError` 22003 → 500); BUG-2274 precedent (component budget: decimal, at most 2 places and 13 integer digits, 422). Sign: OQ-28. (f) Update cannot clear `description` (`null` is dropped, base spec `update` Q1, intended). (g) Access for a cost with neither project nor component: `get_by_id` returns it to anyone in the workspace; the workspace-wide list hides it. | reading the callers |

## Overview
`DAOMiscellaneousProjectCost` reads `miscellaneous_project_costs`: hand-typed extra costs (name, description, amount) booked on a project, on a project component, or both. Its only caller is `MiscellaneousProjectCostService` (`GET /miscellaneous-project-costs/?project_id=` → `get_by_project`; `?project_component_id=` → `get_by_component`; otherwise the inherited `get_by_workspace`; plus inherited `get_by_id_and_workspace`, `create`, `update`, `remove`). The service checks project access before calling. Both methods filter on the row's `workspace_id`; nothing flushes, commits or locks.

**Callables:** 2 specified, + inherited `BaseDAO` behaviour · 1 not specified
**Externals to mock:** none (`created_at` defaults to `app.utils.time.utcnow` in Python)
**Integration-only behavior:** none.

**Model facts (table `miscellaneous_project_costs`, class `app.models.miscellaneous_project_cost.MiscellaneousProjectCost`), verified on `marker_test`:**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `created_at` | `timestamp without time zone` NOT NULL | Python `utcnow()` |
| `project_id` | Integer nullable, FK `projects.id` (no action) | `NULL` |
| `project_component_id` | Integer nullable, FK `project_components.id` (no action) | `NULL` |
| `name` | String NOT NULL (no length) | — |
| `description` | Text nullable | `NULL` |
| `amount` | Numeric(15,2) NOT NULL | — |

Indexes: primary key, `ix_miscellaneous_project_costs_id`, `ix_miscellaneous_project_costs_workspace_id`. No unique constraint, no check constraint, no trigger. No index on `project_id` or `project_component_id`.

**Notes for the test designer:** build rows directly (`MiscellaneousProjectCost(...)`, add + flush); a project needs a factory (`factory_id`, `description` NOT NULL), a component needs its project. To show an unstable order, `UPDATE` the lower-id row and read again (verified to reorder).

## Not specified
- `miscellaneous_project_cost_dao` — module-level instance, no logic.

---

## `DAOMiscellaneousProjectCost.get_by_project(db, *, project_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `MiscellaneousProjectCostService.get_costs` when `project_id` is truthy)

**Purpose:** The misc costs of one project.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| project_id | int \| None | Exact match; existence and state not checked. |
| workspace_id | int | Scope. |
| skip, limit | int | Default 0 / 100; not validated. |

**Returns:** list of `MiscellaneousProjectCost` rows (possibly empty).

**Rules:**
- **R1.** Only rows of this workspace. Another workspace's project id → `[]`, even though that workspace has costs on it (verified).
- **R1a.** [BUG-2461] (revisit after launch (owner 2026-11-10)) Rows with `project_id` = the argument, **and** rows whose `project_component_id` is a component (same workspace) whose `project_id` is the argument; a row matching both ways is returned once. *(Today: `project_id` match only; a component-only cost of the project is missing, verified.)*
- **R2.** Costs of other projects, and costs with neither project nor component, are not returned.
- **R3.** `project_id=None` returns this workspace's costs with an empty `project_id` (SQL `IS NULL`; verified: the component-only cost and the unlinked cost). The service never passes `None` (it tests truthiness first). `0` → `[]`. **Unchanged by the BUG-2461 fix** (decided under the reviewer's delegation, 2026-11-10): the component half of R1a matches only components whose `project_id` equals the argument, and `project_components.project_id` is NOT NULL, so `None` adds nothing through components; the result stays "costs with an empty `project_id`". Why: `None` is unreachable from the service, and keeping one meaning before and after the fix keeps its cards stable.
- **R4.** [BUG-2460] (revisit after launch (owner 2026-11-10)) Order `id` ascending, before `skip` / `limit`. *(Today: no `ORDER BY`; verified to change after an update.)*
- **R5.** A soft-deleted project's costs are still returned (verified); refusing a deleted project is the caller's access check (BUG-1278).
- **R6.** `skip` / `limit` after filtering and ordering; `limit=0` → `[]`; negative → `sqlalchemy.exc.DataError`.

**Errors:** negative `skip` / `limit` → `sqlalchemy.exc.DataError` (Postgres' own message).
**Side effects:** none

---

## `DAOMiscellaneousProjectCost.get_by_component(db, *, project_component_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `MiscellaneousProjectCostService.get_costs` when `project_id` is falsy and `project_component_id` truthy; the web app's component panel)

**Purpose:** The misc costs of one project component.

**Inputs:** as `get_by_project` with `project_component_id` instead of `project_id`.

**Returns:** list of rows.

**Rules:**
- **R1.** Only rows of this workspace with `project_component_id` = the argument, whether or not `project_id` is also set (verified: component-only and both → returned; project-only → not). Another workspace's component id → `[]`.
- **R2.** `project_component_id=None` returns this workspace's costs with an empty `project_component_id` (`IS NULL`; verified). Not reachable from the service. `0` → `[]`.
- **R3.** [BUG-2460] (revisit after launch (owner 2026-11-10)) Order `id` ascending, before paging. *(Today: no `ORDER BY`.)*
- **R4.** Paging as `get_by_project` R6; the state of the component's project does not matter (as `get_by_project` R5).

**Errors:** as `get_by_project`.
**Side effects:** none

---

## Inherited `BaseDAO` methods (`tests/unit/dao/base.spec.md`)
- **R1.** [BUG-100] `get_by_workspace` orders by `id` ascending before paging. *(Today: no order.)*
- **R2.** `get_by_id_and_workspace`, `create`, `update`, `remove` behave as the base spec says. Facts for this table (verified): `create` with a dict stores `amount` rounded half up to 2 places by the column (`0.125` → `0.13`); up to **13** integer digits fit (`9999999999999.99` is stored) and a value that needs **14 or more** (`10000000000000`, or `9999999999999.995` after rounding) fails at flush with `DataError` (22003) (corrected 2026-11-10: the earlier "13 or more" miscounted; verified on `marker_test`); `update` from `MiscellaneousProjectCostUpdate` drops `null` fields (description cannot be cleared, base `update` Q1); `remove` hard-deletes by id with no workspace filter (the service looks the row up with its workspace first).
- **R2a.** (OQ-28, revisit after launch (owner 2026-11-10)) Any amount the column can hold is stored, negative and zero included (`-5` → `-5.00`, `0` → `0.00`); neither the DAO nor `MiscellaneousProjectCostCreate` / `Update` bounds it. Today's behaviour, kept by the owner; no bug.
- **R2b.** Creating through the schema (fact, verified 2026-11-10): `MiscellaneousProjectCostCreate` (`app.schemas.miscellaneous_project_cost`) has `project_id: int | None = None`, `project_component_id: int | None = None`, `name: str` (required), `description: str | None = None`, `amount: float` (required); it has **no** `workspace_id`. Passing the schema object straight to `create` therefore fails at flush with `IntegrityError` 23502 (`workspace_id` NOT NULL). The service's path is `model_dump()` plus `workspace_id`, then `create` with that dict: `1000.005` → `1000.01`, `2.675` → `2.68`, `-1.005` → `-1.01`, `0.125` → `0.13` (the float reaches Postgres as its shortest decimal text, so it rounds half up as typed, HR-15), and `9999999999999.99` is stored as is.

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 40 | workspace filter | `get_by_project` R1 |
| 41 | `project_id ==` (`None` → `IS NULL`) | `get_by_project` R1a, R2, R3 |
| 38-45 | no order; offset / limit | `get_by_project` R4, R6 |
| 67 | workspace filter | `get_by_component` R1 |
| 68 | `project_component_id ==` (`None` → `IS NULL`) | `get_by_component` R1, R2 |
| 65-72 | no order; offset / limit | `get_by_component` R3, R4 |

## Gap log
- G1 (miscellaneous_project_cost.cases.md gap 1) — Fact / contradiction — inherited R2 corrected: 13 integer digits fit (`9999999999999.99` stores), 14 fail with 22003; verified on `marker_test`.
- G2 (miscellaneous_project_cost.cases.md gap 2) — Fact — new inherited R2b: the `Create` schema's fields (no `workspace_id`; schema straight to `create` → 23502) and the service path's half-up rounding of float input; verified.
- G3 (miscellaneous_project_cost.cases.md gap 3) — Intent, decided under delegation (2026-11-10) — `get_by_project` R3: `project_id=None` keeps its meaning after the BUG-2461 fix; GP-11 / GP-23 stand.
- OQ-28 (owner, 2026-11-10) — new inherited R2a, today's behaviour, revisit after launch; BUG-2460 / BUG-2461 rules tagged revisit after launch (tests stay).
