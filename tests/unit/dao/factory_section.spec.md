# Spec — `app/dao/factory_section.py`

> **Status:** APPROVED (2026-10-16: P1–P4, Q1, Q2 and the BUG-905 house-rule reading accepted as suggested; one fill-gaps rule added, `get_by_factory` R1a; nothing provisional remains)
> **Source commit:** e48a092

> **Standing reviewer decisions applied here (not asked again):**
> 1. Soft-deleted rows are kept but must not show up in lists or be counted (inventory DAO Q2, 2026-10-10).
> 2. Things belonging to a soft-deleted factory (machines, sections, stock) are **hidden by the factory's state, their own rows untouched**, so that restoring the factory brings them back ("hidden, not cascaded" — machine DAO P1 / P2; confirmed 2026-10-11). Applied here in both directions: to a **section whose factory is soft-deleted** (`get_by_factory` R3a / R3b, `restore` R7b / R7c), and to **what belongs to a soft-deleted section** — the machine assignments (`soft_delete` R3, `restore` R7).
> 3. "Whitespace" means what Python's `str.strip()` removes (machine DAO P3, 2026-10-10). (No rule of this DAO handles text; recorded for the follow-ups.)
> 4. A `restore` method with no caller is **kept** and specified in full: "restore" is a feature to build (factory manager Q3, machine DAO Q5). `DAOFactorySection.restore` is specified below and is **not** on the dead-code list.
> 5. Restore records nobody and makes no name check at the DAO level — intended there; the future feature must do both (machine DAO Q8, Q9; accepted 2026-10-11).
>
> **Review round 2026-10-16 (delegated).** The reviewer (project owner) delegated the open answers ("just do all of the steps you think makes sense"). P1 (BUG-904), P2, P3, P4, Q1, Q2 were accepted as suggested, and the house-rule reading behind BUG-905 (this DAO's own list hides soft-deleted sections) was kept: it stays a bug — decided by Claude under the reviewer's delegation (2026-10-16); these are not the reviewer's own words. The "(pilot default — awaiting reviewer)" markers were removed; no rule changed.
>
> **Fill-gaps 2026-10-16** (cases Spec gap 3, verifier H2): new rule `get_by_factory` R1a — the workspace filter is on the section's own `workspace_id`, today and after the BUG-904 fix (verified by a rolled-back script). Not a bug; no new BUG ID. See the Gap log.
>
> **Verified by running** (throwaway script against the test database, rolled back): every "Today:" note below; the table's indexes, constraints and column defaults; workspace and factory filtering of `get_by_factory`, its 100-row default, `limit=0`, `skip` past the end, negative `limit` / `skip` with their error classes and codes; that it returns soft-deleted sections (100 deleted sections created first, then one live one → the default call returned 100 rows, all deleted), inactive sections, the sections of a soft-deleted factory and of an inactive factory; every column written and not written by `soft_delete` and `restore`, including `is_active` (both values) and `updated_by`; the already-deleted and already-live cases; the foreign-key error on `deleted_by` and its constraint name; `deleted_by=None`; savepoint roll-back of both writes; that a machine, its assignment row and the factory row are untouched by both; that `restore` does not read the clock; a restore inside a soft-deleted factory; a restore onto a name already used by a live section of the same factory (succeeds, two live rows); the delete → restore round trip for an active and an inactive section; the inherited `create` / `update` / `get` / `get_by_id_and_workspace` / `get_by_workspace` behavior on `FactorySection`. **Not run:** anything at the manager / HTTP level; the *intended* behavior of the three bug rules (it does not exist yet). **Row order:** one run returned five never-updated sections in insertion order; that is an observation, not a guarantee — today's order is unspecified (see Notes for the test designer).

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list — all accepted as suggested (decided by Claude under the reviewer's delegation (2026-10-16))
| # | What the code does today | Answer (accepted) |
|---|---|---|
| P1 | Asking for "the sections of factory X" still returns them when factory X itself has been deleted | bug — sections of a deleted factory are hidden (not returned). Their own rows are never touched, so they are back as soon as the factory is restored (same decision as for machines of a deleted factory) — BUG-904 |
| P2 | The two basic lookups ("one section by id", "all sections of a workspace") also return deleted sections, and sections of deleted factories | intended — these are the raw lookups; the manager decides what to hide (same decision as for every other DAO) |
| P3 | Restoring a section records nobody: no "restored by", no trace that it was ever deleted | intended for the DAO — the future "restore section" feature must record who did it (same as machines) |
| P4 | Restoring a section does not look whether its name was given to another section of the same factory in the meantime | intended for the DAO — the future "restore section" feature must refuse it (same as machines) |
| Q1 | Deleting a section leaves its "active" flag as it was (a deleted section still says active = yes). Deleting a machine switches the flag off; deleting a factory leaves it (factory DAO Q1, accepted as intended 2026-10-16) | intended — "deleted" and "active" are two separate things; delete only marks deleted (same suggestion as for factories) |
| Q2 | Restoring a section does not touch its "active" flag either. Restoring a machine always switches it on | intended — the section comes back exactly as it was before the delete (same suggestion as for factories) |

Already decided by house rules / existing bugs (all three kept 2026-10-16, decided by Claude under the reviewer's delegation (2026-10-16)):
- "the sections of factory X" has **no sort order** → BUG-903 (new; fix in this file);
- "the sections of factory X" **also returns deleted sections**, and they use up places in the page → BUG-905 (new; fix in this file). *This one is a reading of HR-4 plus standing decision 1 — the lookup is this DAO's own list, not one of the generic raw lookups of P2. The reading was kept on 2026-10-16 (decided by Claude under the reviewer's delegation (2026-10-16)): it stays a bug.*
- "all sections of a workspace" (the generic list, inherited) has no sort order → BUG-100 (already logged; the fix in `app/dao/base.py` reaches sections, nothing to do in this file).

### House-rule violations — applied automatically
> Overwrite an answer only if the house rule should NOT apply here.

- **HR-6** `get_by_factory` R6 — no sort order; paging with `skip` / `limit` can repeat or skip sections, and the section list of a factory (`GET /factory-sections/?factory_id=…`) comes back in whatever order the database produces. Intended: name case-insensitive ascending, then `id` ascending, before `skip` / `limit`. This is the DAO's own query (not inherited, not a copy of a `BaseDAO` method), so BUG-100 does not cover it — same situation as the machine DAO's `get_by_factory` (BUG-343) and the factory DAO's `get_active_factories` (BUG-706).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-903 (new, pattern `unordered-pagination`; the fix is in `app/dao/factory_section.py`). Rules: `get_by_factory` R6.
- **HR-4** (second bullet: lists exclude soft-deleted rows by default; scope: "module-specific DAO query methods") and standing decision 1 — `get_by_factory` R2 — soft-deleted sections are returned like live ones and count toward `skip` / `limit`. Intended: a soft-deleted section is never returned and never uses up a place in the page (which also keeps HR-5 true: the filter is in the query, before paging). Both callers already want only live sections: the section list drops deleted ones in Python *after* paging, and the duplicate-name check skips them; the manager's `include_deleted=True` option cannot be reached from the API. Whether an `include_deleted` option is added here for that manager option is for the section manager review (Follow-ups FU-2).
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-905 (new, pattern `get-returns-soft-deleted`; the fix is in `app/dao/factory_section.py`; reading kept 2026-10-16, decided by Claude under the reviewer's delegation (2026-10-16)). Rules: `get_by_factory` R2. The user-visible effects — a section list page that is short or empty although live sections exist, and a duplicate-name check that only sees the first 100 rows, deleted included — are the manager's and will be logged in its own review (FU-2); this fix removes the cause of the first.
- **HR-6** inherited `get_by_workspace` (inherited methods R5) — no sort order. Intended for this raw lookup (HR-6: "generic `BaseDAO` lists only guarantee `id` ascending"): `id` ascending before `skip` / `limit`. `DAOFactorySection` does **not** override `get_by_workspace` (unlike `DAOFactory`), so the BUG-100 fix in `app/dao/base.py` reaches sections with nothing to change in this file.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-100 (existing, pattern `unordered-pagination`, logged against `app/dao/base.py`) — no new ID. Rules: inherited methods R5.

Checked and **not** violated: **HR-5** — `get_by_factory` applies its workspace and factory filters in the query before `skip` / `limit` (R4); the soft-delete filter it lacks is BUG-905. **HR-9** — neither write stamps `updated_by` (P3). **HR-10** — plain soft delete / restore need no row lock. **HR-2** — the DAO makes no uniqueness check at all (create and rename rely on the manager); that `factory_sections` has no unique index is noted for the section manager review (FU-2), see P4.

### Precedent matches — confirmed (2026-10-16, delegated)

### P1. Sections of a deleted factory are still returned — 🐞 BUG-904
**Background:** Factories are soft-deleted (`is_deleted = True`, the row stays). Every section belongs to exactly one factory. Deleting a factory does not touch its sections, and `get_by_factory` never looks at the factory row. The reviewer ruled for stock (BUG-882) and for machines (BUG-890, BUG-891) that things inside a soft-deleted factory are hidden by the factory's state alone, their own rows untouched, so that restoring the factory brings them back; the same reading was ordered for sections.
**What happens today:** The live sections of a soft-deleted factory are returned by `get_by_factory`. Through the API: `GET /factory-sections/?factory_id=9` lists the sections of the deleted factory 9.
**Example:** Factory 9 "Old Plant" is deleted while it still has the sections "Cutting" and "Paint". A screen that asks for the sections of factory 9 still gets both, although no factory "Old Plant" exists in the UI any more.
**Rules affected:** `get_by_factory` R3a (tagged); R3b (untagged — what already holds); `restore` R7c (tagged)
**Answer:** bug — per BUG-891 precedent (`join-ignores-soft-deleted`) and standing decision 2: a section whose factory has `is_deleted = True` is hidden — not returned by `get_by_factory`. Hidden by the factory's state only; the section row is never deleted or changed, so it is returned again, unchanged, once the factory is no longer deleted. A factory that is live but inactive hides nothing. (precedent — confirmed; decided by Claude under the reviewer's delegation (2026-10-16))
**Resolution:** 🐞 BUG-904 (new, pattern `join-ignores-soft-deleted`; the fix is in `app/dao/factory_section.py`). The same gap in the section list *without* a factory filter (which reads through the raw `get_by_workspace`) is the manager's and is noted as FU-2.

### P2. The basic lookups also return deleted sections and sections of deleted factories — ✅ intended
**Background:** Every DAO inherits generic lookups — "one row by id", "one row by id inside a workspace", "all rows of a workspace". The reviewer decided for the base class that these stay raw and return soft-deleted rows, because "already deleted → 400" checks and restore need to see them (base DAO spec, HR-4 scope). `DAOFactorySection` inherits all of them unchanged. (The question is formally still open for the factory DAO's copies — factory DAO P1, suggested `intended`.)
**What happens today:** `get_by_id_and_workspace` returns a deleted section by id; `get_by_workspace` returns deleted sections and the sections of deleted factories along with the rest (and they count toward `skip` / `limit`); `get` returns a section of any workspace, deleted or not. The class comment says "all query methods MUST filter by workspace_id"; the inherited `get`, `get_multi` and `remove` do not, and none of the three has a caller on this DAO.
**Example:** A workspace has the sections "Cutting" (live) and "Old Line" (deleted). The raw workspace list returns both. The section list page hides "Old Line" only because the manager drops it afterwards; `GET /factory-sections/{id}/` shows a deleted section because the manager returns what the raw lookup gives it.
**Rules affected:** inherited methods R4
**Answer:** intended — per base DAO precedent (HR-4 scope) and factory DAO P1: the inherited lookups stay raw; hiding deleted sections, and sections of deleted factories, is the calling manager's job (to be logged in the section manager review, FU-2) (precedent — confirmed; decided by Claude under the reviewer's delegation (2026-10-16))

### P3. Restoring a section records nobody — ✅ intended
**Background:** Deleting a section records who did it (`deleted_by`) and when. `restore` takes only the section — it has no "who" argument — clears the deletion stamp and writes nothing else. Sections have no activity log. For machines the reviewer accepted exactly this on 2026-10-11 (machine DAO Q8).
**What happens today:** After a restore nothing on the row shows that the section was ever deleted or who brought it back: `deleted_at` / `deleted_by` are empty, `updated_by` keeps its old value.
**Example:** Rahim deletes "Cutting" on Monday; Karim restores it on Tuesday (once the feature exists). The row shows neither.
**Rules affected:** `restore` R2a
**Answer:** intended — per machine DAO Q8 precedent: intended for the DAO; recording who restored (`updated_by`, HR-9) is the job of the manager method that will call it (follow-up FU-1) (precedent — confirmed; decided by Claude under the reviewer's delegation (2026-10-16))

### P4. Restoring a section does not check its name — ✅ intended
**Background:** Section names must be unique per factory among live sections; the check is made by the manager on create and rename, and a deleted section's name can be given to a new section (HR-2). There is no database constraint on section names (verified: the only indexes of `factory_sections` are the primary key and plain indexes on `id` and `workspace_id`). `restore` checks nothing. For machines the reviewer accepted "no name check at the DAO; the feature must refuse" on 2026-10-11 (machine DAO Q9).
**What happens today:** Restoring a deleted section whose name was reused in the meantime succeeds, and the factory has two live sections with the same name.
**Example:** "Paint" is deleted; a new section "Paint" is created in the same factory; the old one is restored. The factory's section list shows "Paint" twice.
**Rules affected:** `restore` R9
**Answer:** intended — per machine DAO Q9 precedent: no check in the DAO (it has none anywhere — create and rename rely on the manager too); the manager method that will call `restore` must refuse with 409 (follow-up FU-1). (precedent — confirmed; decided by Claude under the reviewer's delegation (2026-10-16))
**Note:** HR-2 also asks for a database unique index on live section names. None exists and none is ordered yet (no bug is logged for sections — unlike factories, BUG-895). It belongs to the section manager review (FU-2); once that index exists, a blind restore onto a taken name will fail in the database, and a rule `restore` R9a must be added here then.

### New questions

### Q1. Deleting a section leaves its "active" flag as it was — ✅ intended
**Background:** A section row has two flags: `is_deleted` (set by delete) and `is_active` (yes on creation). The machine DAO's delete sets both (`is_deleted = True`, `is_active = False`). The factory DAO's delete sets only `is_deleted` — the same question is open there (factory DAO Q1, suggested `intended`). The section DAO's delete behaves like the factory's.
**What happens today:** A deleted section has `is_deleted = True` and still `is_active = True`. Nothing visible depends on it: no code reads or changes a section's `is_active`, and the API does not show it.
**Example:** "Old Line" is deleted. In the database it reads "deleted: yes, active: yes"; the same delete on a machine reads "deleted: yes, active: no".
**Rules affected:** `soft_delete` R2a
**Suggested answer:** `intended` — "deleted" and "active" are separate facts, and delete should change only the first; it is also what makes an exact undo possible (Q2). Answer `bug — soft_delete also sets is_active = False` if sections should behave like machines; then Q2 must become "restore sets it back to True". Whatever is decided for factories (factory DAO Q1) should be decided the same way here.
**Answer:** intended — as suggested (decided by Claude under the reviewer's delegation (2026-10-16))

### Q2. Restoring a section does not touch its "active" flag — ✅ intended
**Background:** As Q1. The machine DAO's restore always sets `is_active = True`. The section DAO's restore clears only `is_deleted` and the deletion stamp — like the factory DAO's (factory DAO Q2, suggested `intended`).
**What happens today:** A restored section has whatever `is_active` it had while deleted — which, given Q1, is what it had before the delete. A section that was inactive when deleted comes back inactive. (Nothing in the application can make a section inactive; it takes a direct database change.)
**Example:** "Cutting" (active) is deleted and restored: it is active again, because the flag never changed. A section that support had marked inactive in the database, then deleted, then restored, is still inactive.
**Rules affected:** `restore` R3, R8
**Suggested answer:** `intended` — restore is an exact undo: every column is back to its value before the delete. Answer `bug — restore sets is_active = True` only together with a `bug` on Q1.
**Answer:** intended — as suggested (decided by Claude under the reviewer's delegation (2026-10-16))

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Factory section manager / service / endpoint** (feature to build) | `DAOFactorySection.restore` is specified here and has no caller: there is no "restore section" endpoint, service or manager method. When it is built it must decide: 404 for a missing / other-workspace section; the answer for a section that is not deleted (`restore` R4 — the DAO silently does nothing); who restored (`updated_by`, HR-9 — P3); refusing with 409 when the name now belongs to another live section of the factory (P4); what to answer for a section whose factory is soft-deleted (`restore` R7b — the DAO restores it and it stays hidden, R7c); and that an inactive section comes back inactive (Q2). | P3, P4, Q2; standing decision 4 |
| FU-2 | **Factory section manager** review (`app/managers/factory_section_manager.py`; no spec yet) | (a) **Delete cascades to assignments:** `delete_factory_section` soft-deletes the section and then *deletes* every machine-assignment row pointing at it (`clear_for_section`, at most 10 000). That is a cascade, not "hidden": a later restore of the section cannot bring the machines back into it. It contradicts standing decision 2 as applied to sections (and BUG-889's "assignment rows are kept"); the DAO side — `soft_delete` R3, `restore` R7 — already keeps and returns them. (b) The section list filters deleted sections and applies the name search in Python **after** paging (`paginate-before-filter`); with BUG-905 fixed the deleted part disappears for the by-factory list, the search part does not. (c) The list **without** a factory filter reads through the raw `get_by_workspace`: deleted sections after paging, sections of deleted factories shown, BUG-100 order — it needs a filtered, ordered query in this DAO, which gets its own rules then. (d) `if factory_id:` treats `factory_id=0` as "no filter" (`falsy-zero-treated-as-missing`). (e) The duplicate-name check reads only the first 100 rows of `get_by_factory` and compares with exact `==` (`capped-uniqueness-scan`, `unnormalised-uniqueness-compare`), and there is no database unique index (`python-only-uniqueness`, HR-2) — see P4. (f) `get_factory_section` returns deleted sections (`get-returns-soft-deleted`). (g) `include_deleted` is unreachable from the API; if it is kept, `get_by_factory` needs an `include_deleted` option after BUG-905. (h) Renaming or moving a section whose own factory is soft-deleted is not refused; after BUG-904 its duplicate-name check would see no sections at all. | HR-4 line, P1, P2, P4 |
| FU-3 | **Machine DAO** (`tests/unit/dao/machine.spec.md`, APPROVED) and **factory DAO** (`tests/unit/dao/factory.spec.md`) | No change is asked of either. Recorded: `restore` R7 here relies on machine `get_by_section` returning the machines of a live section (holds today and after BUG-889 / BUG-891). If Q1 / Q2 are accepted, sections and factories leave `is_active` alone on delete / restore while machines switch it — on purpose. | Q1, Q2 |
| FU-4 | **Work-order template DAO** (`app/dao/work_order_template.py:47`) and **item summary service** (`app/services/item_summary_service.py:208`) reviews | Both join `factory_sections` without looking at `is_deleted` (a template's default section; the section name shown next to a machine). Whether a soft-deleted section should still match / still be named is to be decided there (HR-4, third bullet). | standing decision 1 |

## Overview
`DAOFactorySection` reads and soft-deletes rows of the `factory_sections` table — the named areas of a factory ("Cutting", "Paint") that machines can optionally be assigned to. It serves the factory section manager: `get_by_factory` for the section list of one factory (`GET /factory-sections/?factory_id=…`) and for the duplicate-name check on create / rename; `soft_delete` for "delete section" (`DELETE /factory-sections/{id}/`); and, through the inherited generic methods, create, update, the by-id lookup (also used by the machine-assignment manager) and the workspace-wide list. It also holds `restore`, the undo of "delete section", which is kept although nothing calls it yet. It is meant to protect workspace isolation and soft-delete semantics: a deleted section keeps its row and is not listed; a section inside a soft-deleted factory is hidden by the factory's state and comes back with it; and nothing that belongs to a section (its machine assignments) is touched by delete or restore. It never commits; writes are flushed.

The class comment ("all query methods MUST filter by workspace_id") describes a requirement, not the code: the inherited `get`, `get_multi` and `remove` take no workspace. None of the three is called on this DAO (P2).

**Callables:** 3 specified (+ 1 section on inherited `BaseDAO` behavior specific to `FactorySection`) · 1 not specified
**Externals to mock:** `utcnow` (patch `app.dao.factory_section.utcnow`; used by `soft_delete` only — `restore` does not read the clock)
**Integration-only behavior:** none. (`skip >= 0`, `1 <= limit <= 1000` for the section list are enforced by `GET /factory-sections/`, not here.)

**Model facts (table `factory_sections`, class `app.models.factory_section.FactorySection`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` (ON DELETE CASCADE; constraint `factory_sections_workspace_id_fkey`) | — |
| `name` | String NOT NULL, no length limit, no unique constraint | — |
| `factory_id` | Integer NOT NULL, FK `factories.id` (constraint `factory_sections_factory_id_fkey`) | — |
| `created_at` | DateTime NOT NULL | `now()` (database default) |
| `created_by`, `updated_by`, `deleted_by` | Integer nullable, FK `profiles.id` (constraints `factory_sections_created_by_fkey`, `factory_sections_updated_by_fkey`, `factory_sections_deleted_by_fkey`) | `NULL` |
| `updated_at` | DateTime nullable | `NULL`; set to `now()` by the database whenever an UPDATE is issued |
| `is_active` | Boolean NOT NULL | `True` (set by the ORM model) |
| `is_deleted` | Boolean NOT NULL | `False` (set by the ORM model) |
| `deleted_at` | DateTime nullable (naive UTC) | `NULL` |

- **No uniqueness in the database** (verified): the only indexes are the primary key and plain indexes on `id` and `workspace_id`. Two live sections with the same name in the same factory can be inserted directly.
- Nothing in the database ties a section's `workspace_id` to its factory's workspace: a section row may name a factory of another workspace (the manager prevents it; the DAO does not — inherited methods R2a).
- Soft delete of a section = `is_deleted = True` + `deleted_at` + `deleted_by`. `is_active` is a separate flag that neither `soft_delete` nor `restore` writes. Nothing in the application reads or sets a section's `is_active`; a test builds an inactive section directly.
- Schemas (`app/schemas/factory_section.py`): `FactorySectionCreate` = `name: str`, `factory_id: int` (no `workspace_id`); `FactorySectionUpdate` = `name: str | None = None`, `factory_id: int | None = None`. No validators, no trimming.
- Rows that point at a section: `machine_section_assignments.factory_section_id` (FK, ON DELETE CASCADE) and `work_order_templates.default_factory_section_id` (FK, ON DELETE SET NULL). Assignment table (class `app.models.machine_section_assignment.MachineSectionAssignment`): NOT NULL `workspace_id`, `machine_id` (FK `machines.id`), `factory_section_id`; unique on `machine_id` (a machine has at most one section); no soft-delete column.
- `Factory` (`app.models.factory.Factory`): NOT NULL `workspace_id`, `name`, `abbreviation`; `is_active` (default `True`), `is_deleted` (default `False`), `deleted_at`, `deleted_by`. `Machine` (`app.models.machine.Machine`): NOT NULL `workspace_id`, `name`, `factory_id`.

**Cross-spec notes (not rules of this DAO, not logged here):**
- "Delete section" in the application = this DAO's `soft_delete` **followed by** the manager deleting the section's assignment rows. The second step is not this DAO's and is questioned in FU-2 (a). Tests of this DAO call `soft_delete` alone.
- The machine DAO's `get_by_section` returns the machines assigned to a section; today it also does so while the section is soft-deleted (BUG-889, logged there).
- No test outside the pipeline exercises this DAO: the legacy tests that mention `FactorySection` build rows directly.

**Notes for the test designer:**
- Use the module singleton `factory_section_dao` (`from app.dao.factory_section import factory_section_dao`). In the three methods specified here every parameter after `db` is keyword-only (a positional call raises `TypeError`). The inherited `get` takes the id positionally or as `id=`.
- Workspaces and profiles come from `tests/unit/factories.py` (`make_workspace`, `make_profile`). Build `Factory`, `FactorySection`, `Machine` and `MachineSectionAssignment` rows directly (add + flush) with the NOT NULL columns listed above. The session runs with `autoflush=False`: flush before calling the DAO.
- **Distinct names.** Within one factory give every *live* section a name that differs in more than case and surrounding whitespace, so no setup collides with a unique index once one exists (FU-2 e). Only the `restore` R9 case builds a collision on purpose.
- **Load before asserting "nothing written".** Call `db.refresh(section)` after building a row and before a call that is expected to issue no UPDATE (`restore` R4): on a just-inserted, never-refreshed object SQLAlchemy has not loaded the nullable columns and writes them anyway (verified: `updated_at` then becomes non-null). After any call that writes, `db.refresh(section)` before asserting database-set columns.
- `updated_at`: assert `None` → not `None` (or still `None`), never "later than". `deleted_at` is compared with the mocked `utcnow` value (a naive `datetime`, e.g. `datetime(2026, 1, 1, 10, 0)`).
- **Row order is unspecified today (BUG-903 `get_by_factory` R6; BUG-100 inherited R5).** No `ORDER BY` is requested and the table's physical order is **not** deterministic on the test database (a freed row place can be reused, so neither "insertion order" nor "an updated row moves to the end" can be relied on). There is no recipe that makes today's order certainly wrong. Write the order cases to the intended order and mark them **non-strict** xfail (`strict=False`); never weaken the assertion. Suggested data for R6: sections named "Zulu", "bolt", "apple", "Bolt", "Banana" in one live factory → intended `["apple", "Banana", "bolt", "Bolt", "Zulu"]` when "bolt" was created before "Bolt" (lower `id` first on the case-only tie). Keep "bolt" / "Bolt" in that case only. **Every other case compares results as sets of ids**, or as counts.
- **Soft-deleted sections in the list (BUG-905, `get_by_factory` R2):** today a deleted section of the factory is returned (verified) → as a set comparison this is deterministic → **strict** xfail. For the paging half: 100 soft-deleted sections created first, then one live one, default paging → intended exactly that one; today 100 rows of which at least 99 are deleted → **strict** xfail (the assertion "exactly the one live section" cannot hold with 100 rows).
- **Soft-deleted factory (BUG-904, `get_by_factory` R3a, `restore` R7c):** build the factory with `is_deleted=True, deleted_at=<fixed naive datetime>, deleted_by=<existing profile id>` and `is_active=True`; the "inactive but live" factory of R3b is `is_active=False, is_deleted=False`. The section inside must itself be live. Today the section is returned (verified) → **strict** xfail, compared as sets. Keep a live section in a live factory of the same workspace in the same case, asked for separately, so "hidden" is not confused with "nothing works".
- **Factory no longer deleted (`get_by_factory` R3b (3)):** start from a soft-deleted factory with a live section, set the factory's `is_deleted = False`, `deleted_at = None`, `deleted_by = None` directly on the row and flush (or use `factory_dao.restore`), then call the list. Holds today → plain pass case. Snapshot the section's columns before and compare after.
- **Soft-deleted section fixtures:** build directly with `is_deleted=True, deleted_at=<fixed naive datetime>, deleted_by=<existing profile id>`; `is_active` as the case needs.
- **Not committed (`soft_delete` R5, `restore` R5):** use a savepoint — `sp = db.begin_nested()`, call, `sp.rollback()`, `db.refresh(section)`.
- **Database errors** (foreign key, NOT NULL, negative `limit` / `skip`): a failing statement aborts the Postgres transaction — wrap the call in `with db.begin_nested():` inside `pytest.raises(...)`.
- **`restore` R7:** `machine_dao.get_by_section(db, factory_section_id=…, workspace_id=…)` (`app.dao.machine`) is the lookup to use; compare as a set of ids; machine, section and factory all live. It holds today and after BUG-889 / BUG-891.
- **Interplay of the three bug rules:** a case about one bug must not depend on another — order cases (BUG-903) use only live sections of a live factory; BUG-905 and BUG-904 cases compare as sets.
- HR-10 (row locks) does not apply: no lock rule, no lock case.

## Not specified
- `factory_section_dao` — module-level singleton `DAOFactorySection(FactorySection)`, no logic
- Inherited `BaseDAO` methods `get`, `get_multi`, `create`, `update`, `remove`, `get_by_workspace`, `get_by_id_and_workspace` — not overridden; specified in `tests/unit/dao/base.spec.md`. Only what is specific to `FactorySection` is stated below ("Inherited `BaseDAO` methods on `FactorySection`"). `get`, `get_multi` and `remove` have no caller on this DAO.

Nothing in this file goes on the dead-code list: all three methods are specified; two have callers and `restore` is kept by reviewer decision (standing decision 4). The checklist (`docs/testing/unit-test-checklist-by-layer.md`) marks none of them as possibly unused.

---

## `DAOFactorySection.get_by_factory(db, *, factory_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `FactorySectionManager.search_factory_sections` when a factory is given, with the caller's `skip` / `limit` ← `GET /factory-sections/?factory_id=…`; `FactorySectionManager._check_name_exists_in_factory` with the defaults ← create / rename of a section)

**Purpose:** One page of the live sections of one factory of a workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `factory_id` | int | equality on `factory_sections.factory_id`; not validated (any integer, including `0`) |
| `workspace_id` | int | equality on `factory_sections.workspace_id` (the section's own; the factory's workspace is not looked at) |
| `skip` | int, default `0` | matching rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |

**Returns:** a `list` of `FactorySection` instances (possibly empty).

**Rules:**
- **R1.** Only sections with `workspace_id` and `factory_id` equal to the arguments are returned. A section of another factory of the same workspace, and a section of the same factory id asked for with another workspace id, are never returned.
- **R1a.** The workspace filter is on the **section's own** `workspace_id`; the workspace of the factory named by `factory_id` is never compared. Given a live section S of W1 whose `factory_id` is a live factory F9 of W2 (a row only a direct insert or the inherited `create` can produce — inherited R2a; the manager checks the factory before creating), `get_by_factory(factory_id=F9.id, workspace_id=W1.id)` returns S, and `get_by_factory(factory_id=F9.id, workspace_id=W2.id)` returns `[]` (verified 2026-10-16 on the test database, rolled back). The same holds after the BUG-904 fix: the fix looks at the factory row only for its `is_deleted` (R3a), so S is still listed for W1 while F9 is live (hidden while F9 is soft-deleted) and is never listed for W2. Not a bug: no row of another workspace is ever returned — the call returns only W1's own section; keeping a section and its factory in one workspace is the manager's job (decided by Claude under the reviewer's delegation (2026-10-16)).
- **R2.** [BUG-905] (HR-4, standing decision 1) Soft-deleted sections (`is_deleted = True`) are never returned and never use up a place in the page: given one live and one deleted section in the factory, only the live one is returned; given 100 deleted sections created first and one live section after them, the default call returns exactly that one. *(Today: `is_deleted` is not looked at — deleted sections are returned like live ones and count toward `skip` / `limit`; in the second example 100 rows come back, at least 99 of them deleted.)*
- **R2a.** `is_active` is not consulted: a live section with `is_active = False` is returned.
- **R3.** An unknown factory id, `factory_id=0`, an unknown workspace id, or a factory with no sections returns `[]`.
- **R3a.** [BUG-904] (P1) When the factory itself is soft-deleted (`factories.is_deleted = True`), its sections are hidden: `[]` is returned even though it has live sections. They are hidden by the factory's state alone — nothing about the sections themselves says "deleted". *(Today: the factory row is never looked at — the live sections of a soft-deleted factory are returned.)*
- **R3b.** What surrounds R3a and holds today and after the fix: (1) the call changes nothing — the sections of a soft-deleted factory stay in the database exactly as they were (`is_deleted = False`, `is_active`, `deleted_at = None`, every other column unchanged); (2) a factory that is live but inactive (`is_active = False`, `is_deleted = False`) hides nothing: its live sections are returned; (3) once the factory is no longer deleted (`factories.is_deleted` back to `False`), its live sections are returned again, unchanged, with nothing done to the section rows.
- **R4.** The workspace and factory filters are applied before `skip` / `limit` (HR-5): sections of other factories and other workspaces never use up a place in the page. With defaults at most 100 sections are returned — given 101 live sections in the factory, exactly 100; with `limit=101` all 101.
- **R5.** `limit=0` returns `[]`; `skip` at or past the number of matching sections returns `[]`. A negative `limit` or `skip` makes Postgres reject the query (see Errors).
- **R6.** [BUG-903] (HR-6) Sections are ordered by name case-insensitive ascending, then `id` ascending, before `skip` / `limit`, so consecutive windows (`skip=0, limit=2`, `skip=2, limit=2`, …) partition the factory's live sections with no repeats or gaps. *(Today: no ordering is requested; the order is whatever the database produces and is not specified.)*
- **R7.** Each section appears exactly once, whether or not machines are assigned to it; nothing is written.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInLimitClause`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInResultOffsetClause`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## `DAOFactorySection.soft_delete(db, *, db_obj, deleted_by)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `FactorySectionManager.delete_factory_section` ← `DELETE /factory-sections/{id}/`, which first answers 404 for a missing / other-workspace section and 400 "Factory section is already deleted" for a deleted one, and afterwards removes the section's machine assignments itself)

**Purpose:** Mark a section as deleted, keeping the row and everything that belongs to it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `db_obj` | `FactorySection` | the section to delete; not checked for workspace, for its current state, or for the state of its factory |
| `deleted_by` | int | profile id stored in `deleted_by`; must reference an existing profile (foreign key) — `None` is stored as `NULL` |

**Returns:** the same `db_obj` instance, flushed, not committed.

**Rules:**
- **R1.** Given a live section, after the call `is_deleted = True`, `deleted_at` = the current time from `utcnow()` (naive UTC) and `deleted_by` = the given id — in the database, not only on the object.
- **R2.** No other column is changed by the method: `name`, `factory_id`, `workspace_id`, `created_by`, `created_at` and `updated_by` keep their values (no `updated_by` stamp). `updated_at` becomes non-null because the database sets it on the UPDATE.
- **R2a.** (Q1) `is_active` is left as it was: an active section is still `is_active = True` after the delete, and a section with `is_active = False` is still `False`.
- **R3.** (Standing decision 2.) Nothing that belongs to the section, and nothing it belongs to, is changed: after the delete a machine assigned to the section, its assignment row (still pointing at the section) and the section's factory are exactly as before. No cascade, and no assignment blocks the delete. (The application's "delete section" removes the assignment rows in a separate step of the manager — not this method; FU-2.)
- **R4.** Given a section that is already soft-deleted, no error is raised and the deletion stamp is overwritten: `deleted_at` becomes the new `utcnow()` value and `deleted_by` the new id. (The manager refuses this case before calling.)
- **R5.** The change is flushed and not committed: in the same session the inherited `get_by_id_and_workspace` returns the section with `is_deleted = True`; rolling back makes it live again with an empty deletion stamp. The returned object is the very instance passed in (`result is db_obj`). That the section then disappears from `get_by_factory` is `get_by_factory` R2 (BUG-905 — today it is still returned). `restore` undoes the delete (`restore` R8).
- **R6.** No workspace check and no factory check: the section passed in is deleted whatever workspace it belongs to, and whether or not its factory is soft-deleted (the caller is responsible for the lookup). Other sections are never touched.
- **R7.** Given a `deleted_by` that is not an existing profile id, the flush fails (see Errors) and the section stays live with an empty deletion stamp.
- **R8.** Given `deleted_by=None`, the section is deleted with `deleted_at` set and `deleted_by = NULL`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `deleted_by` references no profile | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.ForeignKeyViolation` (constraint `factory_sections_deleted_by_fkey`) | — (not asserted) |

**Side effects:** one `factory_sections` row updated (`is_deleted`, `deleted_at`, `deleted_by`; `updated_at` by the database) and flushed; no commit; no other table written.

---

## `DAOFactorySection.restore(db, *, db_obj)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: nothing today — kept by reviewer decision, standing decision 4; the "restore section" feature that will call it is not built yet, see Follow-ups FU-1)

**Purpose:** Bring a soft-deleted section back exactly as it was — the undo of `soft_delete` — and with it, without touching them, the machine assignments that were hidden by its state.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `db_obj` | `FactorySection` | the section to restore; not checked for workspace, for its current state, for its name, or for the state of its factory |

There is no "who" argument: the method cannot record the acting user.

**Returns:** the same `db_obj` instance, flushed, not committed.

**Rules:**
- **R1.** Given a soft-deleted section (`is_deleted = True`, `deleted_at` and `deleted_by` set), after the call `is_deleted = False`, `deleted_at = None`, `deleted_by = None` — in the database, not only on the object.
- **R2.** No other column is changed by the method: `name`, `factory_id`, `workspace_id`, `created_by`, `created_at` keep their values. `updated_at` becomes non-null because the database sets it on the UPDATE.
- **R2a.** (P3) Nobody is recorded as having restored the section: `updated_by` keeps the value it had (including `None`). The clock is not read.
- **R3.** (Q2) `is_active` is not touched. A section deleted while active comes back with `is_active = True`; a soft-deleted section with `is_active = False` comes back live with `is_active = False`.
- **R4.** The current state is not checked and no error is raised for a section that is not deleted. Given a section that is already live (no deletion stamp), loaded from the database, nothing changes at all: no UPDATE is issued, so `updated_at` stays as it was (e.g. `None`) — whether the section is active or inactive.
- **R5.** The change is flushed and not committed: in the same session the section (in a live factory) is returned by `get_by_factory` with `is_deleted = False`; rolling back makes it soft-deleted again with its previous `deleted_at` and `deleted_by`. The returned object is the very instance passed in (`result is db_obj`).
- **R6.** No workspace check: the section passed in is restored whatever workspace it belongs to (the caller is responsible for the lookup). Other sections — deleted or live, same factory or not — are never touched: restoring one deleted section leaves a second deleted section of the same factory deleted, with its stamp unchanged.
- **R7.** (Standing decision 2.) Nothing that belongs to the section is written, and it is all there again: given a section with a machine assigned to it that is soft-deleted (by `soft_delete` alone) and then restored, the machine and its assignment row are exactly as they were before the delete, and the machine DAO's "machines of this section" lookup returns the machine. (Holds today and after BUG-889 / BUG-891.)
- **R7b.** The factory is not looked at and never changed. Given a soft-deleted section whose factory is itself soft-deleted, the restore succeeds with no error: the section row becomes live exactly as in R1, and the factory row stays as it was (`is_deleted = True`, its `deleted_at` / `deleted_by` unchanged).
- **R7c.** [BUG-904] (P1) A section restored per R7b stays hidden for as long as its factory is soft-deleted: it is not returned by `get_by_factory` (`get_by_factory` R3a). It is returned as soon as the factory is no longer deleted, with nothing further done to the section (`get_by_factory` R3b). *(Today: the factory row is never looked at — the section is listed right after the restore, while its factory is still deleted.)*
- **R8.** (Q2) Restore is the exact undo of `soft_delete`: a section that is soft-deleted and then restored has the same value in every column as before the delete — `is_active` included, whether it was `True` or `False` — except `updated_at` (set by the database); its deletion stamp is empty again.
- **R9.** (P4) The method makes no name check. Given a soft-deleted section "Paint" and another, live section "Paint" in the same factory, the restore succeeds and both are live afterwards; the other section is not changed. (Holds today; when a unique index on live section names is added — FU-2 e — this rule is replaced.)

**Errors:** none. (Nothing the method writes can violate a constraint today: it only clears `deleted_by` and `deleted_at` and sets one boolean, and the table has no unique index.)

**Side effects:** at most one `factory_sections` row updated (`is_deleted`, `deleted_at`, `deleted_by`; `updated_at` by the database) and flushed; no UPDATE when the section is already live; no commit; no other table written.

---

## Inherited `BaseDAO` methods on `FactorySection`
**Shape:** create / update / get / list
**Persistence:** writes / reads
**Visibility:** public (used by: `FactorySectionManager.create_factory_section` (`create`, dict); `update_factory_section` (`update`, dict); `get_by_id_and_workspace` from `FactorySectionManager.update_factory_section`, `get_factory_section`, `delete_factory_section` and from `MachineSectionAssignmentManager.set_assignment`; `get_by_workspace` from `FactorySectionManager.search_factory_sections` when no factory is given. `get`, `get_multi`, `remove`: no caller on this DAO)

**Purpose:** `DAOFactorySection` overrides none of the generic methods; the base spec (`tests/unit/dao/base.spec.md`) applies. The rules below state only what the `FactorySection` model and its schemas change.

**Rules:**
- **R1.** `create` with a dict holding `workspace_id`, `name`, `factory_id` creates a section with `is_active = True`, `is_deleted = False`, `created_at` set by the database, and `created_by`, `updated_by`, `updated_at`, `deleted_at`, `deleted_by` all `None`.
- **R2.** `create` with a `FactorySectionCreate` schema always fails: the schema has no `workspace_id`, so the flush raises `IntegrityError` (`NotNullViolation` on `workspace_id`) and no section is saved. The same error for a dict without `factory_id` (on `factory_id`) or without `name` (on `name`). A dict whose `factory_id` is not an existing factory raises `IntegrityError` (`ForeignKeyViolation`, constraint `factory_sections_factory_id_fkey`); one whose `workspace_id` is not an existing workspace raises `ForeignKeyViolation` (constraint `factory_sections_workspace_id_fkey`). (Callers pass a prepared dict — same situation as every workspace-owned model whose create form has no `workspace_id`; base spec notes.)
- **R2a.** `create` does not compare the factory's workspace with the section's: a dict with `workspace_id` of workspace A and the `factory_id` of a factory of workspace B is saved as given. (The manager checks the factory before calling.)
- **R3.** `update` with a `FactorySectionUpdate` applies the fields that were set to a value and leaves the others: `FactorySectionUpdate(name="B")` changes only the name; `FactorySectionUpdate(name=None, factory_id=<another factory>)` changes only the factory (base spec `update` R2, R3). `update` with a dict sets any column given, including `{"is_active": False}` — the only way to produce an inactive section, used by no application code; such a section is still returned by `get_by_factory` (`get_by_factory` R2a).
- **R4.** (P2) The raw lookups stay raw (HR-4 scope): `get`, `get_by_id_and_workspace` and `get_by_workspace` return soft-deleted sections, and sections of soft-deleted factories, like any other; `get` returns a section of any workspace; `get_by_id_and_workspace` returns `None` for a section of another workspace (base spec `get` R3, R4; `get_by_id_and_workspace` R2, R4; `get_by_workspace` R4). Hiding them is the calling manager's decision.
- **R5.** [BUG-100] (HR-6) `get_by_workspace` returns the workspace's sections ordered by `id` ascending before `skip` / `limit` (base spec `get_by_workspace` R3); no name ordering. *(Today: no ordering is requested; the order is not specified. The fix is in `app/dao/base.py` and reaches sections without a change in this file.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `create` without `workspace_id` (any `FactorySectionCreate`), without `factory_id` or without `name` | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.NotNullViolation` | — (not asserted) |
| `create` with an unknown `factory_id` or an unknown `workspace_id` | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.ForeignKeyViolation` | — (not asserted) |

**Side effects:** as in the base spec.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 20 | defaults `skip=0`, `limit=100`; keyword-only | `get_by_factory` R4 |
| 38 | `workspace_id` filter (the section's own) — own / other / unknown workspace; factory of another workspace | `get_by_factory` R1, R1a, R3 |
| 39 | `factory_id` filter — this / other / unknown factory, `0` | `get_by_factory` R1, R3 |
| 36–40 | no `is_deleted` filter (BUG-905); no `is_active` filter | `get_by_factory` R2, R2a |
| 36–40 | no join to `factories` — factory deleted / inactive / restored (BUG-904) | `get_by_factory` R3a, R3b |
| 36–40 | both filters in the query, before paging; one row per section; read only | `get_by_factory` R4, R7 |
| 41–43 | offset / limit, no `ORDER BY` (BUG-903); `limit=0`; negative values; empty / one / many rows | `get_by_factory` R4, R5, R6, Errors |
| 60–62 | three fields set unconditionally (already-deleted section → stamp overwritten); `utcnow()`; `is_active` not written; no `updated_by`; no workspace or factory check; `deleted_by=None` | `soft_delete` R1, R2, R2a, R4, R6, R8 |
| 60–65 | only the section row is written (no cascade to assignments) | `soft_delete` R3 |
| 63–65 | add + flush (FK on `deleted_by`), return same instance, no commit | `soft_delete` R5, R7, Errors |
| 80–82 | three fields reset unconditionally — no check of the section's state (already live → no change), of its workspace, of its name, or of its factory (BUG-904 decides visibility); `is_active` not written; no user argument; clock not read | `restore` R1, R2, R2a, R3, R4, R6, R7b, R7c, R8, R9 |
| 80–85 | only the section row is written | `restore` R7 |
| 83–85 | add + flush (no unique index), return same instance, no commit | `restore` R5, Errors |
| 88 | module singleton | Not specified |
| `base.py` 76–84 | `create`: dict / schema → `FactorySection(**data)`; `FactorySectionCreate` lacks `workspace_id`; no cross-check of factory and workspace | inherited R1, R2, R2a |
| `base.py` 108–119 | `update`: dict (all keys) / schema (`exclude_unset`, `exclude_none`) | inherited R3 |
| `base.py` 43, 161–167, 187–194 | raw lookups: no `is_deleted` filter, no factory check; `get` has no workspace filter; `get_by_workspace` has no `ORDER BY` (BUG-100) | inherited R4, R5 |

## Gap log
- G1 (`factory_section.cases.md` gap 3; verifier H2) — Fact — added `get_by_factory` R1a: the workspace filter is on the section's own `workspace_id`, the factory's workspace is not compared; stated for today and after the BUG-904 fix; verified by a rolled-back script (section of W1 pointing at F9 of W2: listed for `(F9.id, W1.id)`, not for `(F9.id, W2.id)`; the emitted SQL filters `factory_sections.workspace_id` and `factory_sections.factory_id` only). Judged not a bug (nothing of another workspace is returned) — decided by Claude under the reviewer's delegation (2026-10-16). Branch-map row 38 points at R1a.
