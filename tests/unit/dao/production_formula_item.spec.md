# Spec — `app/dao/production_formula_item.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** **The owner's own answer:** Q1 — a line of a removed item stays visible, `intended`, stated as an exception to hide-children. The house-rule lines stand.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v_formula.py`, harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\proddao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints and indexes; the order changing after an update under a forced sequential scan; two lines with one item and role; unknown ids and roles, role case, another workspace; an odd role and a zero or negative quantity stored directly; a deactivated formula through both reads and `get_formula_items`; a removed item through `get_by_formula` and `add_formula_item`; 101 lines; `create` with the schema and with a dict; `update` with `None`; `post_outputs_to_finished_goods` posting from a deactivated formula, and refusing a formula with two outputs. **Not run:** anything over HTTP; the behaviour Q1 asks about under the alternative answer (described from the code).

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically

- **HR-6** `get_by_formula` R3 — no `ORDER BY`. Verified: four lines came back `0, 1, 2, 3`, and `1, 2, 3, 0` after the first was updated. Intended: `id` ascending (BUG-906 precedent: no name of its own to sort by).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1319 (pattern `unordered-pagination`). Rules: `get_by_formula` R3.
- **HR-6** `get_by_formula_and_role` R3 — no `ORDER BY`, same evidence. Intended: `id` ascending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1320 (pattern `unordered-pagination`). Rules: `get_by_formula_and_role` R3.

Checked and **not** a new line here: **HR-3** — `unit` is informational and is neither grouped nor filtered; `item_role` is checked by the schema. **HR-5, HR-7, HR-8** — no paging, no `LIKE`. **HR-9, HR-10** — the DAO only reads, and the table has no audit columns. **HR-15** — `tolerance_percentage` is not money. **HR-16** — the reads follow the row; `add_formula_item` checks the formula and the item against the workspace. A **deactivated formula** does not hide its lines here, on purpose: `post_outputs_to_finished_goods` reads the output line of a completed batch's formula through `get_by_formula_and_role` to post stock, and the formula may have been deactivated since (verified: it posted). `get_formula_items` answers for such a formula too: an inactive formula is a normal state (`production_formula.spec.md` Q1).

### New questions

### Q1. OWNER, stock — A recipe line for an item removed from the catalog — ✅ intended (owner)
**Background:** A catalog item is removed by setting `is_active = False`. Removing an item does not touch recipes, and `delete_item` does not count a recipe line as a blocker (BUG-948 lists open batches, not formulas). The standing decision is that things of a soft-deleted parent are hidden; for stock rows that was ruled in BUG-883 and BUG-980. A recipe line is different in one way: one code path reads it to post stock. `post_outputs_to_finished_goods`, for a completed batch with no output lines of its own, reads the formula's output lines. With **exactly one** it posts the whole `actual_output_quantity` to that item; with two or more it refuses, "No quantities to post".
**What happens today:** Both reads return the line of a removed item like any other, and `add_formula_item` accepts a removed item (verified).
**Example:** Formula "Yarn" has two outputs, Yarn A and Yarn B, and Yarn B is removed from the catalog. A batch with `actual_output_quantity` 7 is completed with no output lines. Today posting is refused, so nothing goes wrong (verified). If the removed line were hidden, one output would remain and all 7 would be booked to Yarn A (from the code, not run). With a single output that is removed, hiding gives "No quantities to post" instead of 7 units of the removed item.
**Rules affected:** `get_by_formula` R5, `get_by_formula_and_role` R5
**Suggested answer:** `intended` — a recipe line is a definition, not a stock row: the reads stay raw and the line stays visible, so the user sees what the recipe calls for and can replace it. This is an exception to the standing decision, because hiding it silently changes which item receives stock. What `add_formula_item` should do with a removed item, and whether the page marks such a line, is for the manager (FU-1 (a)). Alternative: `bug — hidden, rows untouched`, with `post_outputs_to_finished_goods` moved onto a raw read of its own.
**Answer:** intended (owner, 2026-11-02): the line stays visible
**Resolution:** **an exception to the standing decision that soft-deleted parents hide children.** Reason: a recipe line is a definition, not a stock row, and `post_outputs_to_finished_goods` decides from the number of output lines whether and where stock is posted, so hiding a line would silently change which item receives stock. Rules: `get_by_formula` R5 ✅, `get_by_formula_and_role` R5 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Production formula manager** (`app/managers/production_formula_manager.py`, not yet specified) | (a) `add_formula_item` accepts a removed item (verified) and a deactivated formula (read, not run). (b) `get_formula_items` answers for a deactivated formula (verified: 7 lines): intended, `production_formula.spec.md` Q1. (c) Nothing stops the same item and role twice in one formula (stored directly, verified). Two output lines of one item count as two outputs, so `post_outputs_to_finished_goods` refuses to post (read, not run). (d) `update_formula_item` drops `null`, so `unit` and `tolerance_percentage` cannot be cleared (base spec `update` R3). (e) In `add_formula_item` and `update_formula_item`, `VALID_ITEM_ROLES` repeats what the schema's pattern already enforces, so those "Invalid item_role" branches cannot be reached from the API. The one in `get_formula_items` can: the role there is a query parameter. | Q1, reading the callers |

## Overview
`ProductionFormulaItemDAO` reads `production_formula_items`, the lines of a recipe: which item a formula consumes, produces or leaves behind, and how much. Callers: `ProductionFormulaManager` (`/production-formulas/{id}/items/`, `/production-formulas/items/{id}/`) and `ProductionBatchManager.post_outputs_to_finished_goods`. It protects workspace isolation on those reads. It validates nothing, writes nothing of its own, and never commits. `get_by_id_and_workspace` is a line-for-line copy of the base method: it is specified here because it is what runs.

**Callables:** 3 specified · 2 not specified
**Externals to mock:** none. The table has no timestamps.
**Integration-only behavior:** none

**Model facts (table `production_formula_items`, class `app.models.production_formula_item.ProductionFormulaItem`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `formula_id` | Integer NOT NULL, FK `production_formulas.id` ON DELETE CASCADE | — |
| `item_id` | Integer NOT NULL, FK `items.id` ON DELETE RESTRICT | — |
| `item_role` | String(20) NOT NULL, no check constraint | — |
| `quantity` | Integer NOT NULL, no check constraint | — |
| `unit` | String(20) nullable | `NULL` |
| `is_optional` | Boolean NOT NULL | `False` (Python default only) |
| `tolerance_percentage` | Numeric(5, 2) nullable | `NULL` |

- No soft delete, no audit columns, no unique constraint, no trigger; nothing references it. Plain indexes on `id`, `workspace_id`, `formula_id`, `item_id`, `item_role`.
- Schemas (`app/schemas/production_formula_item.py`): `ProductionFormulaItemCreate` = `formula_id`, `item_id`, `item_role` (pattern `input|output|waste|byproduct`), `quantity > 0`, `unit` (max 20), `is_optional = False`, `tolerance_percentage` 0–100 (no `workspace_id`). `ProductionFormulaItemUpdate` = the same without the two ids, all optional.

**Notes for the test designer:**
- `from app.dao.production_formula_item import production_formula_item_dao`. Every parameter after `db` is keyword-only.
- Parents: `ProductionFormula(workspace_id, formula_code, name)`, `Item(workspace_id, name, name_normalized, unit)`. A row of workspace B on a formula of A is invalid data (HR-16) and is built directly.
- **Row order (BUG-1319, BUG-1320):** intended order, **non-strict** xfail, forced sequential scan, as `production_line.spec.md`. Every other case compares **sets** of ids.

## Not specified
- `production_formula_item_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods `get`, `get_by_workspace`, `get_multi`, `create`, `update`, `remove` — not overridden; covered by the base spec. Only what this model changes is under "Inherited `BaseDAO` methods on `ProductionFormulaItem`".

---

## `ProductionFormulaItemDAO.get_by_formula(db, *, formula_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProductionFormulaManager.get_formula_items` without a role)

**Purpose:** Every line of one formula.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `formula_id` | int | equality on the row's `formula_id`; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** a `list` of `ProductionFormulaItem` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `formula_id` and that `workspace_id`, of every role. Another workspace returns `[]`; a row of workspace B on a formula of A is returned only for B.
- **R2.** An unknown formula, `formula_id=0`, or a formula with no lines returns `[]`.
- **R3.** [BUG-1319] (HR-6) Rows are ordered by `id` ascending. *(Today: no ordering is requested.)*
- **R4.** No paging and no cap: 101 lines give 101 rows.
- **R5.** ✅ (Q1) The state of the formula and of the item is not looked at: the lines of a deactivated formula, and a line of a removed item (`items.is_active = False`), are returned. The removed item is an exception to hide-children (owner, 2026-11-02): a recipe line is a definition, and the number of output lines decides where stock goes.
- **R6.** Two lines with one item and role are both returned: nothing makes them unique.

**Errors:** none of its own.

**Side effects:** none

---

## `ProductionFormulaItemDAO.get_by_formula_and_role(db, *, formula_id, item_role, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProductionFormulaManager.get_formula_items` with a role; `ProductionBatchManager.post_outputs_to_finished_goods`, with `"output"`, where the number of rows decides whether stock is posted)

**Purpose:** The lines of one formula with one role.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `formula_id` | int | equality on the row's `formula_id`; not validated |
| `item_role` | str | exact equality; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** a `list` of `ProductionFormulaItem` (possibly empty).

**Rules:**
- **R1.** Returns the rows matching all three. Lines of another role or formula are never returned. Another workspace returns `[]`.
- **R2.** The role is compared exactly: `"INPUT"` and an unknown role return `[]`, with no error. An unknown formula or `0` returns `[]`.
- **R3.** [BUG-1320] (HR-6) Rows are ordered by `id` ascending. *(Today: no ordering is requested.)*
- **R4.** No paging and no cap.
- **R5.** ✅ (Q1) The state of the formula and of the item is not looked at, as `get_by_formula` R5.

**Errors:** none of its own.

**Side effects:** none

---

## `ProductionFormulaItemDAO.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (override identical to `BaseDAO.get_by_id_and_workspace`. Used by: `ProductionFormulaManager.update_formula_item`, `remove_formula_item`)

**Purpose:** One line by id, inside one workspace.

**Returns:** the `ProductionFormulaItem`, or `None`.

**Rules:**
- **R1.** Given a row with that id in that workspace, it is returned.
- **R2.** Given a row with that id in another workspace, `None` is returned (indistinguishable from not found).
- **R3.** An unknown id or `id=0` returns `None`, with no error.
- **R4.** The state of the formula and of the item is not looked at.

**Errors:** none.

**Side effects:** none

---

## Inherited `BaseDAO` methods on `ProductionFormulaItem`
**Shape:** create / update / delete
**Persistence:** writes
**Visibility:** public (`create` with a dict ← `add_formula_item`; `update` with a dict ← `update_formula_item`; `remove` ← `remove_formula_item`)

**Purpose:** `ProductionFormulaItemDAO` does not override these; the base spec applies. Only what this model changes is stated.

**Rules:**
- **R1.** `create` with a dict holding `workspace_id`, `formula_id`, `item_id`, `item_role`, `quantity` gives `is_optional = False`, `unit = None`, `tolerance_percentage = None`.
- **R2.** `create` with a `ProductionFormulaItemCreate` always fails: the schema has no `workspace_id`, so the flush raises `IntegrityError` (`NotNullViolation`, pgcode `23502`) and nothing is saved.
- **R3.** With no check constraint, the DAO stores what the schema would refuse: `item_role="zzz"`, `quantity=0`, `quantity=-3`.
- **R4.** `update` with a `ProductionFormulaItemUpdate` applies only fields set to a value: `quantity=5, unit=None` changes `quantity` and keeps `unit`.
- **R5.** `remove` hard-deletes the row (base spec `remove` R1); nothing references it.

**Errors:** as in the base spec.

**Side effects:** as in the base spec.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 33–40 | `workspace_id` AND `formula_id`; no state read; no paging, no `ORDER BY` (BUG-1319); empty / many | `get_by_formula` R1–R6 |
| 57–65 | `workspace_id` AND `formula_id` AND `item_role`; no state read; no paging, no `ORDER BY` (BUG-1320) | `get_by_formula_and_role` R1–R5 |
| 81–88 | id AND `workspace_id`; `.first()` on the primary key: row / `None` | `get_by_id_and_workspace` R1–R4 |
| 91 | module singleton | Not specified |
| `base.py` 76–84 | `create`: dict / schema (no `workspace_id`); Python default for `is_optional` | inherited R1, R2, R3 |
| `base.py` 108–119 | `update`: schema drops `None` | inherited R4 |
| `base.py` 136–139 | `remove`: found | inherited R5 |
