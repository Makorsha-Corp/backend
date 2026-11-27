# Spec — `app/utils/work_order_generation.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically
- **HR-6** `resolve_template_machine_ids` R5, R7 — the machine list taken from a section or factory is capped (1000) and has no sort order, so which machines are returned, and in what order, is not stable. Intended: machines ordered by name case-insensitive ascending, then `id` ascending (applied before any cap). — 🐞 BUG-343
**Answer:** bug — per HR-6 (house rule)
**Resolution:** section and factory results are ordered by machine name case-insensitive ascending, then `id` ascending. Since BUG-342 removes the cap, the order applies to the full list. Rules: R5a, R7.

### New questions

### Q1. Template's default machine is used even if it is deleted or not in the workspace — 🐞 BUG-340
**Background:** A work order template can name one default machine. Machines are soft-deleted (deleting sets `is_deleted = True`; the row stays and the template's link is not cleared — the link is only cleared if the machine row is physically removed). When drafts are generated, this function decides which machines get a draft work order.
**What happens today:** If the template has a default machine id, that id is returned as-is. Nothing checks that the machine is not soft-deleted or that it belongs to the workspace being generated for.
**Example:** Template "Daily oil check" has default machine #12. Machine #12 is deleted. Tomorrow's generation run still produces a draft work order for machine #12, a machine that no longer shows in any list. If the id belonged to another workspace, the downstream work-order creation raises 404 "Machine with ID 12 not found" and the whole generation run fails.
**Rules affected:** `resolve_template_machine_ids` R2
**Suggested answer:** bug — a default machine that is soft-deleted or not in `workspace_id` is ignored and the function returns `[]` (no drafts for that template)
**Answer:** bug — a default machine that is soft-deleted or not in `workspace_id` is ignored and the function returns `[]` (no drafts for that template) (reviewer accepted suggestion)
**Resolution:** a soft-deleted or other-workspace default machine yields `[]`; the function does not fall back to the template's section or the run's section/factory. An inactive (`is_active = False`) but not deleted machine is still returned, consistent with R5 (best-practice default, delegated by reviewer). A default machine id that no longer matches any row also yields `[]` (best-practice default, delegated by reviewer). Rules: R2, R2a, R2b.

### Q2. Template's default machine ignores the factory/section the run was asked for — 🐞 BUG-341
**Background:** Generation can be scoped to one factory (`factory_id`) or one section (`factory_section_id`). Templates without a default section pass a factory-scoped run's template filter. A machine belongs to exactly one factory.
**What happens today:** When the template has a default machine, that machine is returned regardless of the requested `factory_id` / `factory_section_id`; the scope arguments are not compared with the machine's factory or section.
**Example:** Template "Belt inspection" has default machine #40 (in Factory B) and no default section. A manager runs generation for Factory A only. A draft for machine #40 in Factory B is created, although the run was meant to touch Factory A only.
**Rules affected:** `resolve_template_machine_ids` R2
**Suggested answer:** bug — when `factory_id` (or `factory_section_id`) is given and the default machine is not in that factory (or section), return `[]`
**Answer:** bug — when `factory_id` (or `factory_section_id`) is given and the default machine is not in that factory (or section), return `[]` (reviewer accepted suggestion)
**Resolution:** the run's scope filters the default machine. When both `factory_id` and `factory_section_id` are given, the machine must satisfy both (best-practice default, delegated by reviewer). "In the section" means the machine has a section assignment to that section (a machine with no section assignment is not in any section). The template's own default section is not compared with the default machine; the default machine still takes priority over it (best-practice default, delegated by reviewer — not raised in review, today's behavior kept). Rules: R2c, R2d.

### Q3. At most 1000 machines per section or factory get a draft — 🐞 BUG-342
**Background:** When a template targets a whole section or factory, the machines are fetched with a hard cap of 1000 rows and no sort order.
**What happens today:** Only the first 1000 live machines found (in whatever order Postgres returns them) are returned; any further machines silently get no draft work order.
**Example:** Factory A has 1,200 live machines and a factory-wide template "Weekly lubrication". Generation creates 1,000 drafts; 200 machines (possibly a different 200 on each run) get none, and no error or warning is shown.
**Rules affected:** `resolve_template_machine_ids` R5, R7
**Suggested answer:** bug — all live machines of the section/factory are returned, with no cap
**Answer:** bug — all live machines of the section/factory are returned, with no cap (reviewer accepted suggestion)
**Resolution:** every live, in-workspace machine of the section/factory is returned. Rules: R5b, R7.

### Q4. Unreachable "caller section" branch — dead code
**Background:** The function first computes the effective section as "template's default section, otherwise the caller's `factory_section_id`", then has a separate later branch that runs only when the caller's `factory_section_id` is set.
**What happens today:** That later branch can never run: whenever the caller passes a section id, the effective section is already set and the earlier section branch returns first. It duplicates the earlier branch's query exactly.
**Example:** Calling with no template section and `factory_section_id=5` returns section 5's machines via the first section branch; the second branch (source lines 27–31) is never executed by any input.
**Rules affected:** Branch map row L27
**Suggested answer:** remove
**Answer:** remove (reviewer accepted suggestion)
**Resolution:** dead branch listed for removal (see Not specified); Branch-map row removed. No rule changes — observable behavior is unaffected.

## Overview
Expands one work order template into the list of machine ids that should receive a draft work order in a generate/stage run. Called only by `WorkOrderTemplateManager.generate_drafts` (endpoint `POST /work-order-templates/generate` via `WorkOrderTemplateService.generate_drafts`), once per due template, passing the run's optional `factory_section_id` / `factory_id` scope. Priority: template's default machine → template's default section (or the run's section) → the run's factory → nothing. Intended invariant: only live machines of `workspace_id` that lie inside the run's requested scope are returned.

**Callables:** 1 specified · 1 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Notes for the test designer:**
- Read-only helper: call it directly with a real session and a `WorkOrderTemplate` instance (it only reads `default_machine_id` and `default_factory_section_id`; the template need not be flushed, but machines, sections and `MachineSectionAssignment` rows must exist in the DB).
- A machine is "in a section" only through a `MachineSectionAssignment` row (unique per machine, so at most one section per machine). A machine is "in a factory" through `Machine.factory_id` (mandatory).
- Ids are positive integers from Postgres, so "not set" in the rules means `None`.
- The no-cap rule (R5b/R7, BUG-342) can be tested with 1001 machines. Order (R5a, BUG-343) can be tested with machines whose names differ only in case and machines with equal names.
- A default machine id with no matching row (R2b) can be produced by building an unflushed `WorkOrderTemplate` with `default_machine_id` set to an id that does not exist.

## Not specified
- L27–31 second `if factory_section_id:` branch inside `resolve_template_machine_ids` — dead code, to be removed (reviewer)

---

## `resolve_template_machine_ids(session, *, template, workspace_id, factory_section_id=None, factory_id=None)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderTemplateManager.generate_drafts`)

**Purpose:** Decide which machines a template applies to for one generation run.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | Open DB session. |
| `template` | `WorkOrderTemplate` | Reads `default_machine_id` (nullable FK to `machines`, `ON DELETE SET NULL`) and `default_factory_section_id` (nullable FK to `factory_sections`, `ON DELETE SET NULL`). |
| `workspace_id` | `int` | Scopes every machine lookup, including the default machine (R2a). |
| `factory_section_id` | `int \| None` | Run's section scope; used for the section lookup only when the template has no default section (R3), and as a filter on the default machine (R2c). Default `None`. |
| `factory_id` | `int \| None` | Run's factory scope; used for the factory lookup only when neither the template nor the run gives a section (R7), and as a filter on the default machine (R2c). Default `None`. |

**Returns:** `list[int]` of machine ids (possibly empty). No rows written.

**Rules:**
- **R1.** Priority order: default machine (R2) beats any section (R3–R6), which beats factory (R7). Exactly one source is used; results are never combined. A default machine that is rejected (R2a–R2d) yields `[]` — it does not fall through to the section or factory source.
- **R2.** If the template has a default machine that is live, in `workspace_id`, and inside the run's scope (R2c), the result is exactly `[template.default_machine_id]`, whatever the template's default section is. An inactive (`is_active = False`) but not deleted machine counts as live.
- **R2a.** [BUG-340] If the template's default machine is soft-deleted (`is_deleted = True`) or belongs to another workspace, the result is `[]`. *(Today: the id is returned unchecked.)*
- **R2b.** [BUG-340] If the template's default machine id matches no machine row at all, the result is `[]`. (best-practice default, delegated by reviewer) *(Today: the id is returned unchecked.)*
- **R2c.** [BUG-341] When `factory_id` is given and the default machine's `factory_id` differs, the result is `[]`. When `factory_section_id` is given and the default machine has no section assignment to that section (assigned elsewhere or unassigned), the result is `[]`. When both are given, the machine must satisfy both (best-practice default, delegated by reviewer). *(Today: the scope arguments are ignored and the id is returned.)*
- **R2d.** With a default machine and neither `factory_id` nor `factory_section_id` given, the run's scope does not filter the machine (only R2a/R2b apply). The template's own default section is never compared with the default machine.
- **R3.** Otherwise (no default machine), the effective section is the template's default section if set; the run's `factory_section_id` is used only when the template has none. When both are set and differ, the template's section wins and the run's section is ignored.
- **R4.** With an effective section, the result is the ids of machines that have a section assignment to that section **and** belong to `workspace_id`. Machines assigned to the section but in another workspace are not returned. `factory_id` is ignored in this case (machines are not checked against it).
- **R5.** Soft-deleted machines (`is_deleted = True`) are excluded from section and factory results. Machines with `is_active = False` but `is_deleted = False` are included.
- **R5a.** [BUG-343] Section and factory results are ordered by machine name case-insensitive ascending, then `id` ascending (HR-6). *(Today: no sort order; order is whatever Postgres returns.)*
- **R5b.** [BUG-342] Section and factory results contain every matching live machine — no cap (e.g. 1001 live machines in a section → 1001 ids). *(Today: at most 1000 machines are returned; which ones is unspecified.)*
- **R6.** A section with no live, in-workspace assigned machines yields `[]` — the factory fallback is NOT attempted even if `factory_id` is given.
- **R7.** With no default machine and no effective section, but `factory_id` given, the result is the ids of machines whose `factory_id` equals it and that belong to `workspace_id`, with the same soft-delete (R5), ordering (R5a) and no-cap (R5b) behavior as section results. A factory with no live machines (or a factory of another workspace) yields `[]`.
- **R8.** With no default machine, no section (template or run) and no `factory_id`, the result is `[]`.
- **R9.** Each machine id appears at most once in the result.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| none | — | — |

**Side effects:** none (read-only queries; nothing written or flushed).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| L19 | `template.default_factory_section_id or factory_section_id` — template section set / only run section set / neither | R3 |
| L20 | `template.default_machine_id` set → return it (intended: validated live / workspace / scope first) | R1, R2, R2a, R2b, R2c, R2d |
| L22 | effective section set → section lookup | R3, R4 |
| L23–25 (`get_by_section`) | workspace filter; `include_deleted=False` → exclude deleted; `limit=1000`, no order | R4, R5, R5a, R5b |
| L26 | empty / one / many machines in section | R4, R6, R9 |
| L32 | `factory_id` set → factory lookup | R7 |
| L33–35 (`get_by_factory`) | workspace filter; `include_deleted=False` → exclude deleted; `limit=1000`, no order | R5, R5a, R5b, R7 |
| L36 | empty / one / many machines in factory | R7, R9 |
| L37 | nothing set → `[]` | R8 |
