# Spec — `app/dao/factory.py`

> **Status:** APPROVED (2026-10-16: P1, P2, P3, Q1–Q4 accepted as suggested; nothing provisional remains)
> **Source commit:** e48a092

> **Standing reviewer decisions applied here (not asked again):**
> 1. Soft-deleted rows are kept but must not show up in lists or be counted (inventory DAO Q2, 2026-10-10).
> 2. Things belonging to a soft-deleted factory (machines, sections, stock) are **hidden by the factory's state, their own rows untouched**, so that restoring the factory brings them back ("hidden, not cascaded" — machine DAO P1 / P2; confirmed 2026-10-11). `soft_delete` R3 and `restore` R7 rely on it.
> 3. "Whitespace" means what Python's `str.strip()` removes (machine DAO P3, 2026-10-10).
> 4. `DAOFactory.restore` is **kept** although nothing calls it: "restore factory" is a feature to build (factory manager Q3, 2026-10-11). It is specified in full below and is **not** on the dead-code list.
>
> **Review round 2026-10-16 (delegated).** The reviewer (project owner) delegated the open answers ("just do all of the steps you think makes sense"). P1, P2, P3 and Q1–Q4 were accepted as suggested — decided by Claude under the reviewer's delegation (2026-10-16); these are not the reviewer's own words. The "(pilot default — awaiting reviewer)" markers were removed; no rule changed.
>
> **Verified by running** (throwaway script against the test database, rolled back): every "Today:" note below; the four `is_active` / `is_deleted` combinations of `get_active_factories`; filtering before paging (100 deleted + 100 inactive factories created first, then one live one → it is returned); the 100-row default of both lists; `limit=0`, negative `limit` / `skip` and their error classes and codes; today's row order (insertion order; after updating an earlier row it comes back *after* a later one); every column written and not written by `soft_delete` and `restore`, including `is_active`; the foreign-key error on `deleted_by`; savepoint roll-back of both writes; that a machine and a section of the factory are untouched by both; a restore onto a name already used by a live factory (succeeds today, two live rows); the absence of any unique index on `factories`; the inherited `create` / `update` / `get` behavior on `Factory`. **Not run:** stock rows (`inventory`) of a deleted / restored factory — argued from the code (both methods write only the factory row), machines and sections were run; anything at the manager / HTTP level.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list — all accepted as suggested (decided by Claude under the reviewer's delegation (2026-10-16))
| # | What the code does today | Answer (accepted) |
|---|---|---|
| P1 | The factory DAO's two basic lookups ("all factories of a workspace", "one factory by id") also return deleted factories | intended — these are the raw lookups; the manager decides what to hide (same decision as for every other DAO) |
| P2 | Restoring a factory records nobody: no "restored by", no trace that it was ever deleted | intended for the DAO — the future "restore factory" feature must record who did it (same as machines) |
| P3 | Restoring a factory does not look whether its name or abbreviation was given to another factory in the meantime | intended for the DAO — the future "restore factory" feature must refuse it (same as machines); the database index already ordered under BUG-895 stops it as a last resort |
| Q1 | Deleting a factory leaves its "active" flag as it was (a deleted factory still says active = yes). Deleting a machine switches the flag off | intended — "deleted" and "active" are two separate things; delete only marks deleted |
| Q2 | Restoring a factory does not touch its "active" flag either. Restoring a machine always switches it on | intended — the factory comes back exactly as it was before the delete |
| Q3 | The "active factories" list (used only by the incoming-stock summary) leaves out factories whose "active" flag is off — but no screen or API can switch that flag off | intended — keep the check; it is harmless today and is what the name says. "Deactivate factory" does not exist as a feature |
| Q4 | The file's own comment says every method of this DAO needs a workspace. In fact the generic by-id lookup without a workspace is still there, and the production-line code uses it | intended for the DAO — the comment is out of date; the production-line code is looked at in its own review |

Already decided by house rules / existing bugs (no answer needed): the two lists have no sort order (BUG-100, BUG-706 — both already logged, the fix is in this file), and the database does not stop a restore from creating a second live factory with the same name (BUG-895, already logged). **No new bug is logged by this spec.**

### House-rule violations — applied automatically
> Overwrite an answer only if the house rule should NOT apply here.

- **HR-6** `get_by_workspace` R3 — no sort order; paging with `skip` / `limit` can repeat or skip factories. Intended for this raw lookup (HR-6: "generic `BaseDAO` lists only guarantee `id` ascending"): `id` ascending before `skip` / `limit`. This method is a line-for-line copy of `BaseDAO.get_by_workspace` and **shadows** it, so the BUG-100 fix in `app/dao/base.py` does not reach factories: the same fix must be made here, or the copy deleted.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-100 (existing, pattern `unordered-pagination`, logged against `app/dao/base.py`; this override is the same line copied) — no new ID. Rules: `get_by_workspace` R3. The *display* order of the factory list page (name, then `id`) is a different, already logged bug of the manager — BUG-899 — and is not a rule of this DAO.
- **HR-6** `get_active_factories` R6 — no sort order; the workspace-wide incoming-stock summary is assembled factory by factory in whatever order the database returns them. Intended: name case-insensitive ascending, then `id` ascending, before `skip` / `limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-706 (existing, pattern `unordered-pagination`, logged against `app/managers/inventory_manager.py` "Incoming summary processes factories with no sort order"; the missing `ORDER BY` is in this method, the fix is here) — no new ID. Rules: `get_active_factories` R6.
- **HR-2** (fourth bullet: uniqueness is enforced in the database too) `restore` R9a — `factories` has no unique index, so restoring a factory whose name or abbreviation is now used by another live factory of the workspace succeeds and leaves two live factories with the same name. Intended: the database refuses it.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-895 (existing, pattern `python-only-uniqueness`: the partial unique indexes on the normalised name and abbreviation of live factories; the same index is the fix) — no new ID. Rules: `restore` R9a. Whether the DAO should *also* check in Python is P3.

Checked and **not** violated: **HR-5** — `get_active_factories` filters in the query before `skip` / `limit` (R3). **HR-4** — `get_active_factories` excludes soft-deleted factories; the two raw lookups are P1. **HR-9** — neither write stamps `updated_by` (P2). **HR-10** — plain soft delete / restore need no row lock.

### Precedent matches — confirmed (2026-10-16, delegated)

### P1. The two basic lookups also return deleted factories — ✅ intended
**Background:** Factories are soft-deleted: deleting sets `is_deleted = True` and the row stays. Every DAO inherits two generic lookups — "all rows of a workspace" and "one row by id inside a workspace" — and the reviewer decided for the base class that these stay raw and return soft-deleted rows, because "already deleted → 400" checks and restore need to see them (base DAO spec, HR-4 scope). The factory DAO does not inherit these two: it carries its own copies, identical line for line.
**What happens today:** `get_by_workspace` returns deleted factories along with live ones (and they count toward `skip` / `limit`); `get_by_id_and_workspace` returns a deleted factory by id.
**Example:** A workspace has factories "Main Plant" (live) and "Old Plant" (deleted). The raw list returns both. The factory list page hides "Old Plant" only because the manager drops it afterwards (and `GET /factories/{id}/` showing a deleted factory is already logged against the manager, BUG-897).
**Rules affected:** `get_by_workspace` R4; `get_by_id_and_workspace` R4
**Answer:** intended — per base DAO precedent (HR-4 scope): the copies behave exactly like the inherited raw lookups; hiding deleted factories is the calling manager's job (BUG-897, BUG-898 are logged there) (precedent — confirmed; decided by Claude under the reviewer's delegation (2026-10-16))

### P2. Restoring a factory records nobody — ✅ intended
**Background:** Deleting a factory records who did it (`deleted_by`) and when. `restore` takes only the factory — it has no "who" argument — clears the deletion stamp and writes nothing else. Factories have no activity log. For machines the reviewer accepted exactly this on 2026-10-11 (machine DAO Q8).
**What happens today:** After a restore nothing on the row shows that the factory was ever deleted or who brought it back: `deleted_at` / `deleted_by` are empty, `updated_by` keeps its old value.
**Example:** Rahim deletes "Main Plant" on Monday; Karim restores it on Tuesday (once the feature exists). The row shows neither.
**Rules affected:** `restore` R2a
**Answer:** intended — per machine DAO Q8 precedent: intended for the DAO; recording who restored (`updated_by`, HR-9) is the job of the manager method that will call it (follow-up FU-1) (precedent — confirmed; decided by Claude under the reviewer's delegation (2026-10-16))

### P3. Restoring a factory does not check its name or abbreviation — ✅ intended
**Background:** Factory names and abbreviations must be unique per workspace among live factories; the check is made by the manager on create and rename, and a deleted factory's name and abbreviation can be given to a new factory (HR-2). `restore` checks nothing. For machines the reviewer accepted "no name check at the DAO; the feature must refuse" on 2026-10-11 (machine DAO Q9). Unlike machines, factories are already due to get database unique indexes (BUG-895), which will stop a blind restore in the database.
**What happens today:** Restoring a deleted factory whose name was reused in the meantime succeeds, and the workspace has two live factories with the same name and abbreviation.
**Example:** "Main Plant / MP" is deleted; a new "Main Plant / MP" is created; the old one is restored. The factory list shows "Main Plant" twice.
**Rules affected:** `restore` R9 (the Python side); `restore` R9a is the database side (BUG-895, house-rule line above)
**Answer:** intended — per machine DAO Q9 precedent: no check in the DAO (it has none anywhere — create and rename rely on the manager too); the manager method that will call `restore` must refuse with 409 (follow-up FU-1); the BUG-895 index is the backstop (precedent — confirmed; decided by Claude under the reviewer's delegation (2026-10-16))

### New questions

### Q1. Deleting a factory leaves its "active" flag as it was — ✅ intended
**Background:** A factory row has two flags: `is_deleted` (set by delete) and `is_active` (yes on creation). The machine DAO's delete sets both (`is_deleted = True`, `is_active = False`); so does the account delete. The factory DAO's delete sets only `is_deleted` and the deletion stamp. The approved factory manager spec already describes this as it is (`delete_factory` R4: "`is_active` stays `True`") and deferred the decision to this review (its follow-up FU-1).
**What happens today:** A deleted factory has `is_deleted = True` and still `is_active = True`. Nothing visible depends on it: every factory list that hides deleted factories looks at `is_deleted`.
**Example:** "Old Plant" is deleted. In the database it reads "deleted: yes, active: yes"; the same delete on a machine reads "deleted: yes, active: no".
**Rules affected:** `soft_delete` R2a
**Suggested answer:** `intended` — "deleted" and "active" are separate facts, and delete should change only the first. It is also what makes an exact undo possible (Q2): if delete switched the flag off, restore could not know whether to switch it back on. Answer `bug — soft_delete also sets is_active = False` if factories should behave like machines; then Q2 must become "restore sets it back to True", and `delete_factory` R4 of the factory manager spec changes with it.
**Answer:** intended — as suggested (decided by Claude under the reviewer's delegation (2026-10-16))

### Q2. Restoring a factory does not touch its "active" flag — ✅ intended
**Background:** As Q1. The machine DAO's restore always sets `is_active = True`, which is why its spec notes one thing that is not brought back: a machine that was inactive before it was deleted comes back active. The factory DAO's restore clears only `is_deleted` and the deletion stamp.
**What happens today:** A restored factory has whatever `is_active` it had while deleted — which, given Q1, is what it had before the delete. A factory that was inactive when deleted comes back inactive.
**Example:** "Old Plant" (active) is deleted and restored: it is active again, because the flag never changed. A factory that someone had marked inactive in the database, then deleted, then restored, is still inactive — and so still missing from the incoming-stock summary (Q3).
**Rules affected:** `restore` R3, R8
**Suggested answer:** `intended` — restore is an exact undo: every column is back to its value before the delete. Answer `bug — restore sets is_active = True` only together with a `bug` on Q1.
**Answer:** intended — as suggested (decided by Claude under the reviewer's delegation (2026-10-16))

### Q3. The "active factories" list checks a flag that nothing can switch off — ✅ intended
**Background:** `get_active_factories` returns the factories of a workspace that are active **and** not deleted. Its only caller is the incoming-stock summary without a factory filter (`GET /inventory/incoming-summary/`), which adds up the pending orders of each such factory. A search of `app/` shows that nothing can set a factory's `is_active` to `False`: the create / update forms carry only name and abbreviation, delete does not touch the flag (Q1), and there is no "deactivate factory" endpoint. So in practice the "active" half of the filter never removes a factory. Elsewhere the reviewer decided that only "deleted" hides things — an inactive-but-live factory still counts for stock, machines and the per-factory incoming summary (BUG-882, BUG-890, BUG-718) — while the approved inventory manager spec describes the workspace-wide summary as "every factory that is active and not soft-deleted" (`get_incoming_summary` R2).
**What happens today:** A factory with `is_active = False` (possible only through a direct database change) is left out of this list.
**Example:** Support sets "Old Plant" to inactive directly in the database. The workspace-wide incoming-stock summary no longer shows its pending purchase orders; the factory list, the machines page, the stock page and the same summary asked for that one factory still show it.
**Rules affected:** `get_active_factories` R2
**Suggested answer:** `intended` — the method does what its name says, it changes nothing visible today, and it matches the approved inventory manager rule. What "inactive factory" should mean everywhere is a product decision for the day a "deactivate factory" feature is built (follow-up FU-4). Answer `bug — the list returns every live factory, active or not` if "only deleted hides" should hold here too (then `get_incoming_summary` R2 of the inventory manager spec changes with it).
**Answer:** intended — as suggested (decided by Claude under the reviewer's delegation (2026-10-16))

### Q4. The file says every method needs a workspace; the generic by-id lookup does not — ✅ intended
**Background:** The class comment reads: "This DAO previously inherited dangerous base methods without workspace filtering. All methods now require workspace_id". The DAO overrides two lookups with workspace-filtered copies, but it still inherits the generic ones that take no workspace: `get` (one row by id, any workspace), `get_multi`, `create`, `update`, `remove`. `get` is used: creating a production line looks the factory up with it and compares the workspace afterwards in Python. `get_multi` and `remove` have no caller on this DAO. For the base class the reviewer decided that unscoped primitives are intended and that a caller who leaks is logged against the caller (base DAO Q4).
**What happens today:** `factory_dao.get(db, id)` returns any workspace's factory, deleted or not. The production-line code that uses it does reject a foreign factory, with a message that confirms the factory exists ("Factory 9 does not belong to workspace 3").
**Example:** A developer trusts the comment, calls `factory_dao.get(db, id)` in a new endpoint and returns the result: a user of workspace A can read factory names of workspace B.
**Rules affected:** inherited methods R4
**Suggested answer:** `intended` for this DAO — the comment is out of date, not the code; the unscoped lookup is the base class's by design. The production-line caller (workspace compared after the fact, deleted factory accepted, error text) is to be looked at in the production line manager review (follow-up FU-3). No bug is logged here.
**Answer:** intended — as suggested (decided by Claude under the reviewer's delegation (2026-10-16))

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Factory manager / service / endpoint** (feature to build; continues factory manager spec FU-2) | `DAOFactory.restore` is specified here and has no caller. The `restore_factory` path, when built, must decide: 404 for a missing / other-workspace factory; the answer for a factory that is not deleted (`restore` R4 — the DAO silently does nothing); who restored (`updated_by`, HR-9 — P2); refusing with 409 when the name or abbreviation now belongs to another live factory (P3; with the BUG-895 index a blind restore fails in the database with `IntegrityError`, `restore` R9a); and that an inactive factory comes back inactive (Q2). | P2, P3, Q2; factory manager Q3 |
| FU-2 | **Machine DAO** (`tests/unit/dao/machine.spec.md`, APPROVED) | If Q1 / Q2 are accepted, factories and machines differ on purpose: deleting a machine switches `is_active` off and restoring switches it on; a factory's flag is never touched. No change is asked of the machine DAO; whether the two should be aligned is a product decision. | Q1, Q2 |
| FU-3 | **Production line manager** review (`app/managers/production_line_manager.py:54`) | Looks the factory up with the unscoped `factory_dao.get` and compares the workspace in Python; the error text tells a caller that a factory id of another workspace exists; a soft-deleted factory is accepted. (Already on factory manager FU-5's list for the soft-delete part.) | Q4 |
| FU-4 | **Product decision** / inventory manager | What an inactive-but-live factory means: today it is left out of the workspace-wide incoming-stock summary (`get_active_factories` R2) but summarised when asked for by id (BUG-718's intended behavior) and listed everywhere else. Moot until something can deactivate a factory. | Q3 |
| FU-5 | **Inventory manager** (already logged) | The caller of `get_active_factories` passes `limit=500` — BUG-709 (`silent-result-cap`). The DAO's paging itself is fine; the fix is the caller's (or an unpaged variant here). | — |

## Overview
`DAOFactory` reads and soft-deletes rows of the `factories` table — the physical sites of a workspace, each with a name and a short abbreviation. It serves the factory manager (`get_by_workspace` for the list page and the duplicate checks, `get_by_id_and_workspace` for every "does this factory exist in my workspace" check — also used by ten other managers and one service — and `soft_delete` for "delete factory"), and the workspace-wide incoming-stock summary (`get_active_factories`). It also holds `restore`, the undo of "delete factory", which the reviewer decided to keep although nothing calls it yet. It is meant to protect workspace isolation and soft-delete semantics: a deleted factory keeps its row, and nothing that belongs to it (machines, sections, stock) is touched by delete or restore — those are hidden through the factory's state and come back with it. It never commits; writes are flushed.

`get_by_workspace` and `get_by_id_and_workspace` are line-for-line copies of the inherited `BaseDAO` methods (same filters, same paging, no order, no soft-delete filter). They are specified here because they are what runs; they behave as the base spec says, and a fix made only in `app/dao/base.py` does not reach them.

The class comment ("all methods now require workspace_id") is out of date — Q4. The code wins.

**Callables:** 5 specified (+ 1 section on inherited `BaseDAO` behavior specific to `Factory`) · 1 not specified
**Externals to mock:** `utcnow` (patch `app.dao.factory.utcnow`; used by `soft_delete` only — `restore` does not read the clock)
**Integration-only behavior:** none. (`skip >= 0`, `1 <= limit <= 1000` for the factory list are enforced by `GET /factories/`, not here.)

**Model facts (table `factories`, class `app.models.factory.Factory`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` (ON DELETE CASCADE) | — |
| `name` | String NOT NULL, no length limit | — |
| `abbreviation` | String NOT NULL, no length limit | — |
| `created_at` | DateTime NOT NULL | `now()` (database default) |
| `created_by`, `updated_by`, `deleted_by` | Integer nullable, FK `profiles.id` (constraints `factories_created_by_fkey`, `factories_updated_by_fkey`, `factories_deleted_by_fkey`) | `NULL` |
| `updated_at` | DateTime nullable | `NULL`; set to `now()` by the database whenever an UPDATE is issued |
| `is_active` | Boolean NOT NULL | `True` (set by the ORM model) |
| `is_deleted` | Boolean NOT NULL | `False` (set by the ORM model) |
| `deleted_at` | DateTime nullable (naive UTC) | `NULL` |

- **No uniqueness in the database today** (verified): the only indexes are the primary key and plain indexes on `id` and `workspace_id`. BUG-895 (already logged) adds partial unique indexes on live rows per workspace, on the normalised name and on the normalised abbreviation (normalised = lower-case of the value with surrounding whitespace removed).
- Soft delete of a factory = `is_deleted = True` + `deleted_at` + `deleted_by`. `is_active` is a separate flag that neither `soft_delete` nor `restore` writes. Nothing in the application sets a factory's `is_active` to `False`; a test builds such a row directly.
- Schemas (`app/schemas/factory.py`): `FactoryCreate` = `name: str`, `abbreviation: str` (no `workspace_id`); `FactoryUpdate` = `name: str | None = None`, `abbreviation: str | None = None`. No validators today (BUG-896 adds trimming / non-blank).
- Rows that point at a factory (`factory_id`): `machines`, `factory_sections`, `inventory`, `inventory_ledger`, `product_ledger`, `production_lines`, `products`, `projects`, `sales_orders`, `work_orders`. `Machine` (`app.models.machine`) needs `workspace_id`, `name`, `factory_id`; `FactorySection` (`app.models.factory_section`) needs `workspace_id`, `name`, `factory_id`; both have `is_active` (default `True`), `is_deleted` (default `False`), `deleted_at`, `deleted_by`.

**Cross-spec notes (not rules of this DAO, not logged here):**
- The factory manager's list (`search_factories`) and duplicate checks read through `get_by_workspace` and filter afterwards in Python — BUG-893 (100-row cap of the duplicate checks), BUG-898 (page before filter), BUG-899 (display order). All three are logged against the manager: the DAO's default `limit` of 100 and its raw result are correct for a raw lookup; the callers use it for a job it is not for. Their fixes will most likely add a filtered, ordered query to this file — that new method gets its own rules then.
- `tests/test_inventory_incoming_summary.py` (legacy, outside the pipeline) replaces `factory_dao` with a mock; it does not exercise this code.

**Notes for the test designer:**
- Use the module singleton `factory_dao` (`from app.dao.factory import factory_dao`). In the five methods specified here every parameter after `db` is keyword-only (a positional call raises `TypeError`). The inherited `get` takes the id positionally or as `id=`.
- Workspaces and profiles come from `tests/unit/factories.py` (`make_workspace`, `make_profile`). Build `Factory`, `Machine` and `FactorySection` rows directly (add + flush) with the NOT NULL columns listed above. The session runs with `autoflush=False`: flush before calling the DAO — an added but unflushed factory is not found by any lookup.
- **Distinct names and abbreviations.** Within one workspace give every *live* factory a name and an abbreviation that differ in more than case and surrounding whitespace, so no setup collides with the BUG-895 indexes once they exist. Only the `restore` R9a cases build a collision on purpose.
- **Load before asserting "nothing written".** Call `db.refresh(factory)` after building a row and before a call that is expected to issue no UPDATE (`restore` R4): on a just-inserted, never-refreshed object SQLAlchemy has not loaded the nullable columns and writes them anyway (verified: `updated_at` then becomes non-null). After any call that writes, `db.refresh(factory)` before asserting database-set columns.
- `updated_at`: assert `None` → not `None` (or still `None`), never "later than". `deleted_at` is compared with the mocked `utcnow` value (a naive `datetime`, e.g. `datetime(2026, 1, 1, 10, 0)`).
- **Raw-list order (BUG-100, `get_by_workspace` R3):** today's order is the table's physical order. Deterministic recipe (verified): create "First", then "Second", flush, then change a column of "First" (e.g. its abbreviation) and flush → today the list is `[Second, First]`, intended `[First, Second]` (ids ascending) → **strict** xfail. Assert on ids. Every other `get_by_workspace` case compares results as sets, or uses rows that were never updated and `limit` large enough to hold them all.
- **Active-list order (BUG-706, `get_active_factories` R6):** insert, in this order, "Zulu", "bolt", "apple", "Bolt", "Banana" (distinct abbreviations) and never update them → today `["Zulu", "bolt", "apple", "Bolt", "Banana"]` (verified), intended `["apple", "Banana", "bolt", "Bolt", "Zulu"]` ("bolt" before "Bolt" because it has the lower id) → **strict** xfail. Note "bolt" / "Bolt" differ only in case: keep them in this case only, and give them different abbreviations; if the BUG-895 name index is in place first, drop "Bolt" from the setup and keep the rest. Every other `get_active_factories` case compares results as sets.
- **Filter before paging (`get_active_factories` R3):** 100 soft-deleted and 100 inactive factories inserted first, then one live active one, default paging → exactly that one (verified today).
- **Soft-deleted factory fixtures:** build directly with `is_deleted=True, deleted_at=<fixed naive datetime>, deleted_by=<existing profile id>`; `is_active` as the case needs.
- **Not committed (`soft_delete` R5, `restore` R5):** use a savepoint — `sp = db.begin_nested()`, call, `sp.rollback()`, `db.refresh(factory)`.
- **Database errors** (foreign key, negative `limit` / `skip`, the BUG-895 violation): a failing statement aborts the Postgres transaction — wrap the call in `with db.begin_nested():` inside `pytest.raises(...)`.
- **`restore` R9a (BUG-895):** today the restore succeeds and two live rows exist (verified) → **strict** xfail. One case for the name (deleted "Main Plant" / "MP", live "main plant" / "XX"), one for the abbreviation (deleted "Old Site" / "MP", live "New Site" / " mp").
- **`restore` R7:** `machine_dao.get_by_factory(db, factory_id=…, workspace_id=…)` (`app.dao.machine`) is the lookup to use; compare as a set of ids. It holds today and after BUG-891.
- HR-10 (row locks) does not apply: no lock rule, no lock case.

## Not specified
- `factory_dao` — module-level singleton `DAOFactory(Factory)`, no logic
- Inherited `BaseDAO` methods `get`, `get_multi`, `create`, `update`, `remove` — not overridden; specified in `tests/unit/dao/base.spec.md`. Only what is specific to `Factory` is stated below ("Inherited `BaseDAO` methods on `Factory`"). `get_multi` and `remove` have no caller on this DAO.

Nothing in this file goes on the dead-code list: all five methods are specified; four have callers and `restore` is kept by reviewer decision (factory manager Q3).

---

## `DAOFactory.get_by_workspace(db, *, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (override identical to `BaseDAO.get_by_workspace`. Used by: `FactoryManager.search_factories` with the caller's `skip` / `limit`; `FactoryManager._check_name_exists` and `_check_abbreviation_exists` with the defaults)

**Purpose:** One page of all factory rows of a workspace, raw: deleted and inactive ones included.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `workspace_id` | int | equality on `factories.workspace_id` |
| `skip` | int, default `0` | rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |

**Returns:** a `list` of `Factory` instances (possibly empty).

**Rules:**
- **R1.** Only factories with `workspace_id` equal to the argument are returned; a factory of another workspace never appears. A workspace with no factories, or an unknown workspace id, returns `[]`.
- **R2.** At most `limit` rows are returned after skipping `skip`; with defaults at most 100 — given 101 factories in the workspace, exactly 100. `limit=0` returns `[]`; `skip` at or past the number of the workspace's factories returns `[]`. A negative `limit` or `skip` makes Postgres reject the query (see Errors).
- **R3.** [BUG-100] (HR-6) Rows are ordered by `id` ascending before `skip` / `limit`, so consecutive windows (`skip=0, limit=2`, `skip=2, limit=2`, …) partition the workspace's factories with no repeats or gaps. No name ordering: "Zulu" with the lower id comes before "apple". *(Today: no ordering is requested; the rows come back in the table's physical order — a factory that was updated after a later one was created comes back after it.)*
- **R4.** (P1) Soft-deleted factories of the workspace are returned like live ones and count toward `skip` / `limit`: given one live and one deleted factory, both are returned; given 100 deleted factories created first and one live factory after them, the default call returns exactly 100 rows, at least 99 of them deleted (today, and with the R3 order, all 100 — the live one is not among them).
- **R5.** `is_active` is not consulted: a factory with `is_active = False` is returned.
- **R6.** Nothing is written.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInLimitClause`, `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInResultOffsetClause`, `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## `DAOFactory.get_by_id_and_workspace(db, *, id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (override identical to `BaseDAO.get_by_id_and_workspace`. Used by: `FactoryManager.update_factory`, `get_factory`, `delete_factory`; the factory-exists checks of `factory_section_manager`, `machine_manager`, `product_manager`, `project_manager`, `purchase_order_manager`, `transfer_order_manager`, `work_order_manager`, `expense_order_manager`, `inventory_manager`, `inventory_movements`, and `purchase_order_service`)

**Purpose:** Fetch one factory by id only if it belongs to the given workspace, raw: a deleted one is returned too.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `id` | int | equality on `factories.id`; not validated |
| `workspace_id` | int | equality on `factories.workspace_id` |

**Returns:** the `Factory`, or `None`.

**Rules:**
- **R1.** Given a factory with that id in that workspace, it is returned.
- **R2.** Given the id exists but belongs to another workspace, `None` is returned (indistinguishable from not existing).
- **R3.** Given no factory has that id (including `id=0`), `None` is returned; no error.
- **R4.** (P1) A soft-deleted factory of the workspace is returned like a live one.
- **R5.** `is_active` is not consulted: a factory with `is_active = False` is returned.

**Errors:** none

**Side effects:** none

---

## `DAOFactory.get_active_factories(db, *, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `InventoryManager.get_incoming_summary` when no factory is given ← `GET /inventory/incoming-summary/`, with `skip=0, limit=500`)

**Purpose:** One page of the factories of a workspace that are active and not deleted — the factories the workspace-wide incoming-stock summary covers.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `workspace_id` | int | equality on `factories.workspace_id` |
| `skip` | int, default `0` | matching rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |

**Returns:** a `list` of `Factory` instances (possibly empty).

**Rules:**
- **R1.** Only factories with `workspace_id` equal to the argument are returned; a factory of another workspace never appears. A workspace with no factories, or an unknown workspace id, returns `[]`.
- **R1a.** Soft-deleted factories (`is_deleted = True`) are never returned, whatever their `is_active` — also the factory `soft_delete` leaves behind, which is still `is_active = True`.
- **R2.** (Q3) A live factory is returned only when `is_active = True`: a factory with `is_active = False`, `is_deleted = False` is not returned. Of the four combinations only (active, not deleted) is returned.
- **R3.** The filters are applied before `skip` / `limit` (HR-5 holds): deleted and inactive factories never use up a place in the page. Given 100 deleted and 100 inactive factories created first and one active live factory after them, the default call returns exactly that one.
- **R4.** With defaults at most 100 factories are returned — given 101 active live factories, exactly 100; with `limit=500` all 101.
- **R5.** `limit=0` returns `[]`; `skip` at or past the number of matching factories returns `[]`. A negative `limit` or `skip` makes Postgres reject the query (see Errors).
- **R6.** [BUG-706] (HR-6) Factories are ordered by name case-insensitive ascending, then `id` ascending, before `skip` / `limit`, so consecutive windows partition the matching factories with no repeats or gaps. *(Today: no ordering is requested; the rows come back in the table's physical order.)*
- **R7.** Each factory appears exactly once, whether or not it has machines, sections or stock; nothing is written.

**Errors:** as `get_by_workspace` (negative `limit` / `skip`).

**Side effects:** none

---

## `DAOFactory.soft_delete(db, *, db_obj, deleted_by)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `FactoryManager.delete_factory` ← `DELETE /factories/{id}/`, which first answers 404 for a missing / other-workspace factory and 400 "Factory is already deleted" for a deleted one)

**Purpose:** Mark a factory as deleted, keeping the row and everything that belongs to it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `db_obj` | `Factory` | the factory to delete; not checked for workspace or current state |
| `deleted_by` | int | profile id stored in `deleted_by`; must reference an existing profile (foreign key) — `None` is stored as `NULL` |

**Returns:** the same `db_obj` instance, flushed, not committed.

**Rules:**
- **R1.** Given a live factory, after the call `is_deleted = True`, `deleted_at` = the current time from `utcnow()` (naive UTC) and `deleted_by` = the given id — in the database, not only on the object.
- **R2.** No other column is changed by the method: `name`, `abbreviation`, `workspace_id`, `created_by`, `created_at` and `updated_by` keep their values (no `updated_by` stamp). `updated_at` becomes non-null because the database sets it on the UPDATE.
- **R2a.** (Q1) `is_active` is left as it was: an active factory is still `is_active = True` after the delete, and a factory with `is_active = False` is still `False`.
- **R3.** (Standing decision 2.) Nothing that belongs to the factory is changed: after the delete a machine and a factory section of that factory are exactly as before (`is_deleted = False`, `is_active = True`, no deletion stamp). No cascade, and nothing that belongs to the factory blocks the delete.
- **R4.** Given a factory that is already soft-deleted, no error is raised and the deletion stamp is overwritten: `deleted_at` becomes the new `utcnow()` value and `deleted_by` the new id. (The manager refuses this case before calling.)
- **R5.** The change is flushed and not committed: in the same session the factory is no longer returned by `get_active_factories`, and is still returned by `get_by_workspace` and `get_by_id_and_workspace`; rolling back makes it live again with an empty deletion stamp. The returned object is the very instance passed in (`result is db_obj`). `restore` undoes the delete (`restore` R8).
- **R6.** No workspace check: the factory passed in is deleted whatever workspace it belongs to (the caller is responsible for the lookup). Other factories are never touched.
- **R7.** Given a `deleted_by` that is not an existing profile id, the flush fails (see Errors) and the factory stays live with an empty deletion stamp.
- **R8.** Given `deleted_by=None`, the factory is deleted with `deleted_at` set and `deleted_by = NULL`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `deleted_by` references no profile | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.ForeignKeyViolation` (constraint `factories_deleted_by_fkey`) | — (not asserted) |

**Side effects:** one `factories` row updated (`is_deleted`, `deleted_at`, `deleted_by`; `updated_at` by the database) and flushed; no commit; no other table written.

---

## `DAOFactory.restore(db, *, db_obj)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: nothing today — kept by reviewer decision, factory manager Q3; the "restore factory" feature that will call it is not built yet, see Follow-ups FU-1)

**Purpose:** Bring a soft-deleted factory back exactly as it was — the undo of `soft_delete` — and with it, without touching them, the machines, sections and stock that were hidden by its state.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `db_obj` | `Factory` | the factory to restore; not checked for workspace, for its current state, or for its name / abbreviation |

There is no "who" argument: the method cannot record the acting user.

**Returns:** the same `db_obj` instance, flushed, not committed.

**Rules:**
- **R1.** Given a soft-deleted factory (`is_deleted = True`, `deleted_at` and `deleted_by` set), after the call `is_deleted = False`, `deleted_at = None`, `deleted_by = None` — in the database, not only on the object.
- **R2.** No other column is changed by the method: `name`, `abbreviation`, `workspace_id`, `created_by`, `created_at` keep their values. `updated_at` becomes non-null because the database sets it on the UPDATE.
- **R2a.** (P2) Nobody is recorded as having restored the factory: `updated_by` keeps the value it had (including `None`). The clock is not read.
- **R3.** (Q2) `is_active` is not touched. A factory deleted while active comes back with `is_active = True`. A soft-deleted factory with `is_active = False` comes back live with `is_active = False`: it is returned by `get_by_workspace` and `get_by_id_and_workspace` and not by `get_active_factories`.
- **R4.** The current state is not checked and no error is raised for a factory that is not deleted. Given a factory that is already live (no deletion stamp), loaded from the database, nothing changes at all: no UPDATE is issued, so `updated_at` stays as it was (e.g. `None`) — whether the factory is active or inactive.
- **R5.** The change is flushed and not committed: in the same session an active factory is returned again by `get_active_factories`; rolling back makes it soft-deleted again with its previous `deleted_at` and `deleted_by`. The returned object is the very instance passed in (`result is db_obj`).
- **R6.** No workspace check: the factory passed in is restored whatever workspace it belongs to (the caller is responsible for the lookup). Other factories — deleted or live, same workspace or not — are never touched: restoring one deleted factory leaves a second deleted factory of the same workspace deleted, with its stamp unchanged.
- **R7.** (Standing decision 2.) Nothing that belongs to the factory is written, and it is all there again: after the restore a machine and a factory section of that factory are exactly as they were before the factory was deleted (`is_deleted = False`, `is_active = True`, no deletion stamp), and the machine DAO's "machines of this factory" lookup returns the factory's live machines. (Holds today and after BUG-890 / BUG-891 — machine spec `get_by_factory` R3b.)
- **R8.** (Q2) Restore is the exact undo of `soft_delete`: a factory that is soft-deleted and then restored has the same value in every column as before the delete — `is_active` included, whether it was `True` or `False` — except `updated_at` (set by the database); its deletion stamp is empty again.
- **R9.** (P3) The method makes no name or abbreviation check of its own. Restoring a factory whose name and abbreviation are used only by another *soft-deleted* factory of the workspace, or by a factory of *another* workspace, succeeds, and that other factory is not changed. (Holds today and after BUG-895.)
- **R9a.** [BUG-895] (HR-2) Restoring a factory whose normalised name — or normalised abbreviation — is used by another **live** factory of the same workspace is refused by the database: the flush raises `IntegrityError`, the factory stays soft-deleted with its stamp unchanged, and the other factory is not changed. Normalised = lower-case, surrounding whitespace removed: deleted "Main Plant" collides with live "main plant"; deleted abbreviation "MP" with live " mp". *(Today: no constraint — the restore succeeds and the workspace has two live factories with the same name / abbreviation. Requires the partial unique indexes of BUG-895.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| [BUG-895] name or abbreviation used by another live factory of the workspace | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.UniqueViolation` | — (not asserted) |

Nothing else the method writes can violate a constraint: it only clears `deleted_by` and `deleted_at` and sets one boolean.

**Side effects:** at most one `factories` row updated (`is_deleted`, `deleted_at`, `deleted_by`; `updated_at` by the database) and flushed; no UPDATE when the factory is already live; no commit; no other table written.

---

## Inherited `BaseDAO` methods on `Factory`
**Shape:** create / update / get
**Persistence:** writes / reads
**Visibility:** public (used by: `FactoryManager.create_factory` (`create`, dict), `FactoryManager.update_factory` (`update`, dict), `ProductionLineManager.create_production_line` (`get`). `get_multi` and `remove`: no caller on this DAO)

**Purpose:** `DAOFactory` overrides neither `create`, `update`, `get`, `get_multi` nor `remove`; the base spec (`tests/unit/dao/base.spec.md`) applies. The rules below state only what the `Factory` model and its schemas change.

**Rules:**
- **R1.** `create` with a dict holding `workspace_id`, `name`, `abbreviation` creates a factory with `is_active = True`, `is_deleted = False`, `created_at` set by the database, and `created_by`, `updated_by`, `updated_at`, `deleted_at`, `deleted_by` all `None`.
- **R2.** `create` with a `FactoryCreate` schema always fails: the schema has no `workspace_id`, so the flush raises `IntegrityError` (`NotNullViolation` on `workspace_id`) and no factory is saved. The same error (on `abbreviation`) for a dict without `abbreviation`; a dict whose `workspace_id` is not an existing workspace raises `IntegrityError` (`ForeignKeyViolation`, constraint `factories_workspace_id_fkey`). (Callers pass a prepared dict — same situation as every workspace-owned model whose create form has no `workspace_id`; base spec notes.)
- **R3.** `update` with a `FactoryUpdate` applies the fields that were set to a value and leaves the others: `FactoryUpdate(name="B")` changes only the name; `FactoryUpdate(name=None, abbreviation="U2")` changes only the abbreviation (base spec `update` R2, R3). `update` with a dict sets any column given, including `{"is_active": False}` — the only way to produce an inactive factory, used by no application code; such a factory then drops out of `get_active_factories` (`get_active_factories` R2).
- **R4.** (Q4) The raw by-id lookup stays raw: `get(db, id)` returns the factory with that id whatever workspace it belongs to and whether or not it is soft-deleted (base spec `get` R3, R4).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `create` without `workspace_id` (any `FactoryCreate`) or without `abbreviation` | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.NotNullViolation` | — (not asserted) |
| `create` with an unknown `workspace_id` | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.ForeignKeyViolation` | — (not asserted) |

**Side effects:** as in the base spec.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 20 | defaults `skip=0`, `limit=100`; keyword-only | `get_by_workspace` R2 |
| 36 | `workspace_id` filter — own / other / unknown workspace | `get_by_workspace` R1 |
| 34–40 | no `is_deleted` filter, no `is_active` filter (raw) | `get_by_workspace` R4, R5, R6 |
| 37–39 | offset / limit, no `ORDER BY` (BUG-100); `limit=0`; negative values; empty / one / many rows | `get_by_workspace` R2, R3, Errors |
| 58–61 | `workspace_id` AND `id` — match / other workspace / missing | `get_by_id_and_workspace` R1, R2, R3 |
| 56–63 | no `is_deleted` filter, no `is_active` filter; `.first()` → row or `None` | `get_by_id_and_workspace` R3, R4, R5 |
| 66 | defaults `skip=0`, `limit=100` | `get_active_factories` R4 |
| 83 | `workspace_id` filter | `get_active_factories` R1 |
| 84 | `is_active == True` — active / inactive | `get_active_factories` R2 |
| 85 | `is_deleted == False` — live / deleted (any `is_active`) | `get_active_factories` R1a |
| 82–86 | all three filters in the query, before paging | `get_active_factories` R3, R7 |
| 87–89 | offset / limit, no `ORDER BY` (BUG-706); `limit=0`; negative values | `get_active_factories` R4, R5, R6, Errors |
| 106–108 | three fields set unconditionally (already-deleted factory → stamp overwritten); `utcnow()`; `is_active` not written; no `updated_by`; no workspace check; `deleted_by=None` | `soft_delete` R1, R2, R2a, R4, R6, R8 |
| 106–111 | only the factory row is written (no cascade) | `soft_delete` R3 |
| 109–111 | add + flush (FK on `deleted_by`), return same instance, no commit | `soft_delete` R5, R7, Errors |
| 126–128 | three fields reset unconditionally — no check of the factory's state (already live → no change), of its workspace, or of its name / abbreviation; `is_active` not written; no user argument; clock not read | `restore` R1, R2, R2a, R3, R4, R6, R8, R9 |
| 126–131 | only the factory row is written | `restore` R7 |
| 129–131 | add + flush (no unique index today — BUG-895), return same instance, no commit | `restore` R5, R9a, Errors |
| 134 | module singleton | Not specified |
| `base.py` 76–84 | `create`: dict / schema → `Factory(**data)`; `FactoryCreate` lacks `workspace_id` | inherited R1, R2 |
| `base.py` 108–119 | `update`: dict (all keys) / schema (`exclude_unset`, `exclude_none`) | inherited R3 |
| `base.py` 43 | `get`: no workspace filter, no `is_deleted` filter | inherited R4 |
