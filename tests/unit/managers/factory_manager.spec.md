# Spec — `app/managers/factory_manager.py`

> **Status:** APPROVED (2026-10-11; reopened and approved again 2026-11-02 for `delete_factory`, BUG-1331)
> **Source commit:** e48a092

> **Follow-up note 2026-11-02 (reopens this module).** Owner's answer in `tests/unit/dao/production_batch.spec.md` Q1: `delete_factory` refuses while the factory has `draft` or `in_progress` batches, listing them (BUG-1331; frontend note BUG-1332). `completed` and `cancelled` batches do not block. This overturns R5 and Q2 below for batches only: everything else still does not block. **Applied 2026-11-02 (describer, apply-review):** `delete_factory` R5 and Q2 rewritten for batches only, R5a, R5b, R5c added, tagged BUG-1331; Errors rows 4, 5 and FU-6, FU-7 added. Everything else in this spec is unchanged. The cross-workspace form follows `machine_item_manager` `delete_item` R5a (BUG-1081), decided by Claude under the reviewer's delegation (2026-11-02).

> **Review round 2026-10-11.** The reviewer answered `ok` to the quick list: P1 and Q1–Q4 are accepted as suggested, and the "hidden, not cascaded" reading in standing decision 2 was put to the reviewer explicitly, with the alternative, and confirmed. The "(pilot default — awaiting reviewer)" markers were removed; no rule changed.
>
> **Standing reviewer decisions applied here (not asked again):**
> 1. Soft-deleted rows are kept but must not show up in lists or be counted (inventory DAO Q2, 2026-10-10).
> 2. Things belonging to a soft-deleted factory (machines, sections, stock) are **hidden by the factory's state, their own rows untouched**, so that restoring the factory brings them back (machine DAO P1 / P2, 2026-10-10). Confirmed by the reviewer on 2026-10-11; `delete_factory` R5 and Q2 rely on it.
> 3. "Whitespace" means what Python's `str.strip()` removes — spaces, tabs and newlines — wherever trimming is specified (machine DAO P3, 2026-10-10).
>
> **Verified by running** (throwaway script against the test database, rolled back): every "Today:" note below, every error message and status code, the absence of any unique constraint on `factories`, the foreign-key errors, the negative `limit` / `skip` errors, the 100-row cap of the duplicate checks and of the list, and that deleting a factory leaves its machine and section rows untouched. **Not run:** anything at the HTTP level (service, endpoint), and the two-requests-at-once race behind BUG-895 (argued from the missing constraint, which was verified; a direct duplicate insert was run and succeeded).

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list — all accepted by the reviewer (2026-10-11)
| # | In one line | Answer (accepted) |
|---|---|---|
| P1 | The factory search does not trim the text: `" mp "` finds nothing | bug — trim; whitespace-only = no search (same as machines, BUG-892) |
| Q1 | Is the abbreviation held to the same standard as the name (trimmed, never blank, unique ignoring case, backed by the database)? | yes — bug where it is not |
| Q2 | A factory that still has machines, sections, stock or open orders can be deleted, and nothing of theirs is touched | intended — they are hidden with the factory and come back when it is restored; **overturned for open production batches only** (owner, 2026-11-02, BUG-1331) |
| Q3 | Nothing can restore a deleted factory; the "restore" method of the factory DAO is never called | keep the method; "restore factory" is a feature still to be built (not dead code, not a bug of this manager) |
| Q4 | The subscription plan's "maximum factories" is never checked when a factory is created | intended for now — plan limits (except members) are not enforced anywhere yet; record as a product follow-up |

### House-rule violations — applied automatically
> Overwrite an answer only if the house rule should NOT apply here.

- **HR-2** `_check_name_exists` R5, `_check_abbreviation_exists` R5 — the duplicate checks load at most 100 factories of the workspace (soft-deleted ones included, in no order) and look only at those; a live duplicate outside them is missed. Intended: every live factory of the workspace is checked.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-893 (pattern `capped-uniqueness-scan`; BUG-001 shape). Rules: `_check_name_exists` R5, `_check_abbreviation_exists` R5.
- **HR-2** `_check_name_exists` R4 — names are compared with exact equality: "Main Plant", "main plant" and "Main Plant " count as three different names. Intended: compared case-insensitively after trimming.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-894 (pattern `unnormalised-uniqueness-compare`; BUG-002 shape). Rules: `_check_name_exists` R4. (The same for the abbreviation is Q1.)
- **HR-2** `create_factory` R8, `update_factory` R14 — the `factories` table has no unique constraint; two requests at the same moment can both pass the Python check. Intended: a partial unique index on live rows (normalised name per workspace); a violation surfaces as 409, never 500.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-895 (pattern `python-only-uniqueness`; BUG-003 shape). Rules: `create_factory` R8, `update_factory` R14. (The same for the abbreviation is Q1.)
- **HR-1** `create_factory` R7, `update_factory` R10 — factory names are stored exactly as typed (`"  Plant  "` keeps its spaces); `""` and `"   "` are accepted on create; on update `""` skips the duplicate check and is written. Intended: stored trimmed; blank / whitespace-only rejected by `FactoryCreate` / `FactoryUpdate` (422), nothing written (fix in `app/schemas/factory.py`).
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-896 (pattern `blank-name-accepted`; BUG-004 shape). Rules: `create_factory` R7, `update_factory` R10. (The same for the abbreviation is Q1.)
- **HR-4** `get_factory` R3 — a soft-deleted factory is returned by id (`GET /factories/{id}/` answers 200) although the list hides it and update answers 400. Intended: 404 by default; new `include_deleted=True` parameter returns it.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-897 (pattern `get-returns-soft-deleted`; BUG-005 shape). Rules: `get_factory` R3, R4.
- **HR-5** `search_factories` R2, R4 — one page of `limit` rows is loaded first (deleted factories included) and only then are deleted rows dropped and the search applied, in Python. Pages come back short or empty although more factories exist, and the search only looks inside the loaded page. Intended: filter first, then page.
**Answer:** bug — per HR-5 (house rule)
**Resolution:** 🐞 BUG-898 (pattern `paginate-before-filter`; BUG-006 / BUG-007 shape — one ID, one fix: move the filters into the query). Rules: `search_factories` R2, R4.
- **HR-6** `search_factories` R3 — no sort order; paging can repeat or skip factories. Intended: name case-insensitive ascending, then `id` ascending, before `skip` / `limit`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-899 (pattern `unordered-pagination`; BUG-008 shape). Rules: `search_factories` R3.
- **HR-9** `update_factory` R11 — `updated_by` is written on every successful update, including an empty request or unchanged values. Intended: only when a field actually changes value.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-900 (pattern `audit-stamp-on-noop`; BUG-009 shape). Rules: `update_factory` R11.
- **HR-4** (second bullet: "where an `include_deleted` option exists it is reachable from the API") `search_factories` R5 — the list has an `include_deleted` option that `FactoryService.get_factories` and `GET /factories/` never pass. Intended: reachable from the API. The manager itself behaves correctly; the fix is in the service and the endpoint.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-901 (pattern `flag-unreachable-from-api`; BUG-010 shape). Rules: `search_factories` R5 (manager rule holds today; tagged for traceability). Integration note: `FactoryResponse` has no `is_deleted` field, so once deleted factories can be listed the response cannot tell them apart — to be settled with the fix.
- **HR-8** `search_factories` R6a — search text must be literal (`%`, `_` match themselves). Today compliant (the filter is a Python substring test); the BUG-898 fix moves the search into SQL, where the text must be escaped. Same fix as BUG-898 — no new ID.
**Answer:** bug — per HR-8 (house rule)
**Resolution:** logged against BUG-898. `search_factories` R6a holds today; its tests are regression guards for the BUG-898 fix, not expected-to-fail.

### Precedent matches — confirm all with ok

### P1. The factory search does not trim the text — 🐞 BUG-902
**Background:** `GET /factories/?search=…` looks for the text inside the name or the abbreviation. The text is used exactly as typed. For the machines page the reviewer already ruled (BUG-892): trim; a whitespace-only search means "no search".
**What happens today:** `" mp "` does not find the factory "Main Plant" (abbreviation "MP"); a search of three spaces returns only factories whose name or abbreviation contains three spaces in a row.
**Example:** A user pastes "Main Plant " (trailing space) into the factory search and gets an empty list.
**Rules affected:** `search_factories` R7
**Answer:** bug — per BUG-637 / BUG-892 precedent: leading / trailing whitespace (spaces, tabs, newlines — `str.strip()`) is removed before matching; a whitespace-only search applies no search filter (reviewer, 2026-10-11)
**Resolution:** 🐞 BUG-902 (pattern `whitespace-search-empties-results`). Rules: `search_factories` R7.

### New questions

### Q1. Is the abbreviation held to the same standard as the name? — 🐞 BUG-894 / BUG-895 / BUG-896
**Background:** Every factory has a name ("Main Plant") and a short abbreviation ("MP"). The code already refuses a second live factory with the same abbreviation in a workspace, exactly as it does for names — so uniqueness is clearly meant. The house rules (HR-1, HR-2) are written for "names"; whether they cover the abbreviation is not written down. For account codes the reviewer decided the same question with "yes" (BUG-874: trimmed, case-insensitive, backed by the database). Nothing else in the application uses the abbreviation today (it is not part of any order number) — it is only stored, searched and shown.
**What happens today:** With a factory "MP" in the workspace, new factories with abbreviation `"mp"` and `" MP "` are both accepted (three factories that read "MP"). `""` and `"  "` are accepted as abbreviations. The database has no uniqueness on it.
**Example:** A user creates "Main Plant / MP", a colleague later creates "Metal Press / mp": 201. Reports and pickers that show only the abbreviation now have two entries that differ by case alone.
**Rules affected:** `_check_abbreviation_exists` R4; `create_factory` R7a, R8a; `update_factory` R10a, R14a
**Suggested answer:** `bug — the abbreviation follows the same rules as the name: stored trimmed, case kept as typed; blank / whitespace-only rejected by the schema (422); unique per workspace among live factories ignoring case and surrounding whitespace; backed by a partial unique index; a duplicate answers 409`. (The 100-row cap of the abbreviation check is not part of this question: it is a bug either way — BUG-893.) Answer `intended` if abbreviations are free text where "MP" and "mp" may coexist.
**Answer:** bug — as suggested (reviewer, 2026-10-11)
**Resolution:** logged against the three name bugs (same fix, same files): BUG-894 (compare), BUG-895 (database index), BUG-896 (trim / blank). Rules: `_check_abbreviation_exists` R4; `create_factory` R7a, R8a; `update_factory` R10a, R14a.

### Q2. A factory that still has machines, sections, stock or open orders can be deleted — ✅ intended, except open production batches — 🐞 BUG-1331
**Background:** Deleting a factory is a soft delete: the row stays and is flagged deleted. Machines, factory sections, stock rows, production lines, projects, products, work orders and sales orders all point at a factory. `delete_factory` looks at none of them and changes none of them. The reviewer's standing decision for machines and stock (see top note, decision 2 — **main session's interpretation**) is that these are *hidden* through the factory's state and come back when the factory is restored; they are not deleted along with it. For accounts the reviewer decided differently for one case: an account with open invoices cannot be deleted (BUG-876).
**What happens today:** Any live factory is deleted, whatever it contains. Its machines, sections, stock and orders keep their own rows unchanged (`is_deleted = False`).
**Example:** "Old Plant" has 12 machines, 3 sections, 400 units of stock and 2 open work orders. A user deletes it: 200. The factory disappears from the factory list; its machines and stock are meant to disappear with it (BUG-890, BUG-891, BUG-882 — not yet fixed, so today they are still listed); the 2 open work orders are still open.
**Rules affected:** `delete_factory` R5, R5a, R5b, R5c
**Suggested answer:** `intended` — follows the standing decision: nothing is cascaded and nothing blocks the delete, so that a restore brings everything back exactly as it was. Answer `bug — refuse with 400 while the factory has …` if deletion should be blocked by something (the candidates: stock with a non-zero quantity, open work orders / purchase orders / sales orders).
**Answer:** intended (reviewer, 2026-10-11). **Overturned for batches only:** bug — `delete_factory` refuses while `draft` or `in_progress` batches exist, listing them (owner, 2026-11-02, `tests/unit/dao/production_batch.spec.md` Q1).
**Resolution:** 🐞 BUG-1331 (pattern `delete-ignores-dependents`; frontend note BUG-1332). A batch with `status` `draft` or `in_progress` on a line of the factory blocks; `completed` and `cancelled` do not. Everything else stays as answered on 2026-10-11: nothing else blocks, nothing is cascaded. The list form is decided by Claude under the reviewer's delegation (2026-11-02), per BUG-968 and HR-16. Rules: `delete_factory` R5 ✅, R5a, R5b, R5c.

### Q3. Nothing can restore a deleted factory — ✅ keep `DAOFactory.restore`; feature to build
**Background:** The reviewer's reason for hiding (not deleting) a deleted factory's machines is "we need to be able to put them back if the user undoes" (machine DAO, follow-up FU-4). `FactoryManager` has no restore method, `FactoryService` has none, and there is no endpoint. The factory DAO has a `restore` method (`app/dao/factory.py:113`) that clears the deletion flag and stamp; a search of `app/` and `tests/` for `factory_dao.restore`, `.restore(` and `DAOFactory` finds no caller of it (the only `.restore(` calls in `app/` are the inventory DAO's own).
**What happens today:** A deleted factory cannot be brought back through the application. Its name and abbreviation can be given to a new factory in the meantime.
**Example:** A user deletes "Main Plant" by mistake. There is no button or API call to undo it; the only way back is a direct database change.
**Rules affected:** none of this manager (no method exists to specify)
**Suggested answer:** `intended for now — keep DAOFactory.restore (not dead code), build "restore factory" as a feature` — the same decision as for machines ("keep restore", machine DAO Q5). It is recorded under **Follow-ups for other reviews** (FU-1, FU-2) with the points the new manager method must decide. Answer `remove` if factories are not meant to be restorable — then `DAOFactory.restore` goes on the dead-code list, and decision 2 above loses its reason.
**Answer:** intended for now — keep, feature to build (reviewer, 2026-10-11)
**Resolution:** no rule, no bug, **no dead-code entry** for `DAOFactory.restore`. Follow-ups FU-1, FU-2.

### Q4. The plan's "maximum factories" is never checked — ✅ intended for now
**Background:** Every workspace has a subscription plan with limits, among them `max_factories` (seeded plans: 1, 3 and −1 = unlimited; model default 2). The member limit (`max_members`) is enforced when a member is added or invited. A search of `app/` for `max_factories` finds only the plan model, the plan schema and the seed data — nothing reads it. The same is true of `max_machines` and `max_projects`.
**What happens today:** `create_factory` never looks at the plan. A workspace on the 1-factory plan can create any number of factories.
**Example:** A workspace on the smallest plan ("1 factory") creates a second and a third factory: 201 each time.
**Rules affected:** `create_factory` R9
**Suggested answer:** `intended for now` — no plan limit other than members is enforced anywhere, so this is a product feature not yet built rather than a defect of this manager; recorded as follow-up FU-4. Answer `bug — refuse the create when the workspace already has max_factories live factories (−1 = unlimited)` if it should be enforced now; the status code and message would then be asked as a follow-up (the member limit says "Workspace has reached maximum member limit (N). Upgrade subscription to add more members.").
**Answer:** intended for now (reviewer, 2026-10-11)
**Resolution:** rule unchanged. Rules: `create_factory` R9 ✅. Follow-up FU-4.

## Follow-ups for other reviews
> Nothing below is a rule of this manager and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Factory DAO** review (`app/dao/factory.py`) | `DAOFactory.restore` has no caller in `app/` or `tests/`; by Q3 it is kept and must be specified there, not removed. Two things to decide there: `soft_delete` leaves `is_active = True` and `restore` does not touch `is_active` (the machine DAO sets `False` / `True`); `get_active_factories` (used by the incoming-stock summary) filters on both flags, but nothing in the application can set a factory's `is_active` to `False`. | Q3; machine spec FU-4 |
| FU-2 | **Factory manager / service / endpoint** (feature to build) | A `restore_factory` path does not exist. When built it must decide: 404 for a missing / other-workspace factory; the answer for a factory that is not deleted; who restored (`updated_by`, HR-9); and refusing with 409 when the name or abbreviation was given to another live factory in the meantime (with the BUG-895 unique index a blind restore would fail in the database). | Q3; machine spec FU-4 |
| FU-3 | **Factory service / endpoint** (`app/services/factory_service.py`, `app/api/v1/endpoints/factories.py`, `FactoryResponse`) | Exposing `include_deleted` on `GET /factories/` and on `GET /factories/{id}/` (BUG-901, BUG-897); `FactoryResponse` carries only `id`, `name`, `abbreviation`, so a listed deleted factory cannot be told from a live one. | HR-4 lines |
| FU-4 | **Product decision / workspace & subscription review** | `max_factories`, `max_machines` and `max_projects` of the subscription plan are read by no code; only `max_members` is enforced. | Q4 |
| FU-6 | **Factory service / endpoint** (`app/services/factory_service.py`, `DELETE /factories/{id}/`) | BUG-1331: translate the manager's `ValueError("Factory has open production batches", blockers)` into a 400 whose body carries the message and the blockers, as item manager FU-1: `app.core.exceptions.ValidationError(detail=exc.args[0], errors=exc.args[1])`. Today `FactoryService.delete_factory` rolls back and re-raises every exception, so an untranslated `ValueError` would be a 500. | BUG-1331 |
| FU-7 | **Frontend** (`frontend/src/pages/newpages/FactoriesPage.tsx`) | BUG-1332: show the blockers of a refused delete. No backend test (BUG-949 precedent). | BUG-1331 |
| FU-5 | Reviews of the managers that look a factory up before using it (`factory_section_manager`, `machine_manager`, `product_manager`, `project_manager`, `purchase_order_manager`, `transfer_order_manager`, `work_order_manager`, `expense_order_manager`, `production_line_manager`) | They read the factory through the raw `factory_dao.get_by_id_and_workspace` / `get`, which return soft-deleted factories; whether each refuses a soft-deleted factory is to be checked there (already logged for stock posting and transfers: BUG-662, BUG-684, BUG-715, BUG-718, BUG-822). | decision 1 |

## Overview
`FactoryManager` owns factories — the physical sites of a workspace, each with a name and a short abbreviation. It is called only by `FactoryService` (which commits / rolls back and re-reads the row) behind the `/factories/` endpoints. It is meant to protect: workspace isolation (a factory is visible and editable only from its own workspace), one live factory per name and per abbreviation in a workspace, and soft-delete semantics (a deleted factory cannot be edited or deleted again, and is hidden from the list). The manager never commits; the DAO flushes. It has no restore method (Q3).

The class docstring says the factory model has "no audit fields or soft delete" — that is out of date: the model has both and the manager uses them. The code wins.

**Callables:** 7 specified · 1 not specified
**Externals to mock:** `utcnow` (patch `app.dao.factory.utcnow`; used for `deleted_at` only)
**Integration-only behavior:** the bounds on `GET /factories/` (`skip >= 0`, `1 <= limit <= 1000` — HR-7 is already met by the endpoint); exposing `include_deleted` through the service and endpoints (BUG-901, BUG-897 — FU-3); the 400 body of a refused delete (BUG-1331 — FU-6); the 422 a schema `ValidationError` becomes at the API; the service's commit / rollback.

**Facts for the test designer**
- Import: `from app.managers.factory_manager import FactoryManager, factory_manager`. `FactoryManager()` takes no arguments; the module instance `factory_manager` holds no per-call state and can serve every test.
- Table `factories`, class `app.models.factory.Factory`:

  | Column | Type / constraint | Default |
  |---|---|---|
  | `id` | Integer PK | sequence |
  | `workspace_id` | Integer NOT NULL, FK `workspaces.id` (ON DELETE CASCADE) | — |
  | `name` | String NOT NULL, no length limit | — |
  | `abbreviation` | String NOT NULL, no length limit | — |
  | `created_at` | DateTime NOT NULL | `now()` (database default) |
  | `created_by`, `updated_by`, `deleted_by` | Integer nullable, FK `profiles.id` | `NULL` |
  | `updated_at` | DateTime nullable | `NULL`; set to `now()` by the database whenever an UPDATE is issued |
  | `is_active` | Boolean NOT NULL | `True` (set by the ORM model, no database default) |
  | `is_deleted` | Boolean NOT NULL | `False` (set by the ORM model, no database default) |
  | `deleted_at` | DateTime nullable (naive UTC) | `NULL` |

- **No uniqueness in the database today** (verified): the only indexes are the primary key and plain indexes on `id` and `workspace_id`. Two live rows with the same name and abbreviation in one workspace can be inserted directly.
- Soft delete of a factory = `is_deleted = True` + `deleted_at` + `deleted_by`. **`is_active` stays `True`** (unlike machines and accounts). Nothing in this manager reads or writes `is_active`.
- Schemas (`app/schemas/factory.py`): `FactoryCreate` = `name: str`, `abbreviation: str` (both required); `FactoryUpdate` = `name: str | None = None`, `abbreviation: str | None = None`. Today: no validators, no trimming, no length checks; unknown fields are ignored.
- `created_by`, `updated_by`, `deleted_by` reference `profiles.id`; profiles are global and the manager never checks that the user belongs to the workspace — any existing profile id works.
- `ProductionLine` (`app.models.production_line`, table `production_lines`): required `workspace_id`, `factory_id`, `name`; `is_active` default `True`. **No `is_deleted` column.**
- `ProductionBatch` (`app.models.production_batch`, table `production_batches`): required `workspace_id`, `batch_number` (at most 50 characters, unique per `workspace_id`: `uq_batch_workspace_number`), `production_line_id`, `batch_date` (a `date`), `status` (default `draft`; valid values `draft`, `in_progress`, `completed`, `cancelled`; no database check). `created_at`, `updated_at` are set by the ORM. **No `is_deleted` column.** A batch reaches a factory only through its line (`production_batches.production_line_id` → `production_lines.factory_id`). No foreign key ties a batch or a line to the factory's workspace (verified): the cross-workspace rows of `delete_factory` R5a can be inserted directly.
- Rows that point at a factory (`factory_id`): `machines`, `factory_sections`, `inventory`, `inventory_ledger`, `product_ledger`, `production_lines`, `products`, `projects`, `sales_orders`, `work_orders`. `Machine` (`app.models.machine`) needs `workspace_id`, `name`, `factory_id`; `FactorySection` (`app.models.factory_section`) needs `workspace_id`, `name`, `factory_id`; both have `is_active` (default `True`) and `is_deleted` (default `False`).

**Notes for the test designer**
- Workspaces and profiles come from `tests/unit/factories.py` (`make_workspace`, `make_profile`). Build extra `Factory` rows directly (add + flush) with `workspace_id`, `name`, `abbreviation`. The session runs with `autoflush=False`: flush before calling the manager.
- After a call that writes, `db.refresh(factory)` before asserting database-set columns (`created_at`, `updated_at`).
- `updated_at`: assert `None` → not `None` (or unchanged), never "later than". `deleted_at` is compared with the mocked `utcnow` value (a naive `datetime`).
- **Cap of 100 (BUG-893, BUG-898):** today's "first 100" are, on the test database, the first 100 rows inserted for the workspace (verified: 100 soft-deleted factories inserted first, then one live "Late" / "LT" → the list returns `[]`, searching `late` returns `[]`, `skip=100` returns it, and creating another "Late" or another "LT" succeeds). Build the cases that way; today's result is deterministic → strict xfail.
- **Order (BUG-899):** today's order is whatever the database returns (insertion order on the test database). Insert names so that the intended order differs from insertion order and from its reverse.
- **Case / whitespace duplicates (BUG-894):** today such duplicates are simply created (verified) → strict xfail.
- **At most one live row per normalised name / abbreviation** can exist per workspace once BUG-895 is fixed. A setup that needs two rows with equal (normalised) names or abbreviations must make all but one soft-deleted, or put them in different workspaces. Cases that are not about duplicates use distinct names and abbreviations.
- **Database-level 409 (`create_factory` R8 / R8a, `update_factory` R14 / R14a):** to simulate a concurrent request that already passed the Python check, patch `FactoryManager._check_name_exists` (and / or `_check_abbreviation_exists`) to return `False`. Wrap the manager call itself in `db.begin_nested()` inside `pytest.raises(HTTPException)` so the session is usable for the "nothing created / changed" re-read. A direct duplicate insert that violates the intended index raises `sqlalchemy.exc.IntegrityError` on flush.
- **Database errors** (foreign keys, negative `limit` / `skip`): a failing statement aborts the Postgres transaction — wrap the call in `with db.begin_nested():`.
- **Schema rejections (BUG-896):** assert `pydantic.ValidationError` when constructing `FactoryCreate` / `FactoryUpdate`; the manager is never reached.
- **Open batches (BUG-1331):** a refusal is a plain Python `ValueError`, so no database error aborts the transaction: do **not** wrap the call in `db.begin_nested()`, a savepoint would hide a write. To show that the order of the blockers comes from a sort, give rows explicit `id` values, inserted out of order, with batch number, date, status and line not rising with `id`.
- HR-10 (row locks) does not apply: rename and soft delete are plain state changes whose worst race is an overwritten audit stamp. No lock rule, no lock case.

## Not specified
- `FactoryManager.__init__` — stores the `Factory` model and the factory DAO, no logic
- `factory_manager` — module-level singleton `FactoryManager()`, no logic

---

## `FactoryManager.create_factory(session, factory_data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `FactoryService.create_factory` ← `POST /factories/`)

**Purpose:** Create a factory in a workspace, refusing a name or an abbreviation already used by a live factory there.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `factory_data` | `FactoryCreate` | `name`, `abbreviation`: required strings; intended: each trimmed and at least 1 character after trimming [BUG-896] *(Today: no trimming, no blank check, no length limit.)* |
| `workspace_id` | int | workspace the factory is created in; not checked to exist (foreign key only) |
| `user_id` | int | creator; stored as `created_by` (foreign key to `profiles.id`; workspace membership not checked) |

**Returns:** the new `Factory`, flushed (has an `id`), not committed.

**Rules:**
- **R1.** Given no live factory of the workspace uses the name or the abbreviation, one factory row is created with `name` and `abbreviation` as received, `workspace_id` = the argument and `created_by` = `user_id`; the returned object has an `id`.
- **R2.** The new row has `is_active = True`, `is_deleted = False`, `created_at` set by the database, and `updated_at`, `updated_by`, `deleted_at`, `deleted_by` all `None`.
- **R3.** Given a live factory of the same workspace already has the name, `HTTPException` 409 `Factory with name '<name>' already exists` is raised and nothing is created. `<name>` is the submitted name as received by the manager (i.e. trimmed by the schema once BUG-896 is fixed), never the existing factory's spelling (department Q13 precedent). What counts as "the same name" follows `_check_name_exists` R1–R7.
- **R4.** Given a live factory of the same workspace already has the abbreviation (and the name is free), 409 `Factory with abbreviation '<abbreviation>' already exists` is raised and nothing is created; `<abbreviation>` is the submitted value as received. What counts as "the same abbreviation" follows `_check_abbreviation_exists` R1–R7.
- **R5.** The name is checked first: when both the name and the abbreviation are taken (by the same factory or by two different ones), the name error of R3 is raised.
- **R6.** A factory of another workspace, or a soft-deleted factory of the same workspace, with the same name and / or abbreviation does not block the create. Name and abbreviation are compared separately: a new factory whose *name* equals another factory's *abbreviation* (or the reverse) is created normally.
- **R7.** [BUG-896] [HR-1] The name is stored with leading / trailing whitespace removed (`"  Main Plant "` → `"Main Plant"`; inner whitespace and case kept); a blank or whitespace-only name (`""`, `"   "`, `"\t"`) is rejected by `FactoryCreate` itself — Pydantic `ValidationError` (422 at the API), the manager is not reached, nothing is created. *(Today: stored exactly as typed; `""` and `"   "` are accepted. Fix in `app/schemas/factory.py`, on `FactoryCreate` / `FactoryUpdate`, not on `FactoryBase`, which `FactoryResponse` inherits.)*
- **R7a.** [BUG-896] (Q1) The abbreviation is treated the same way: stored trimmed with its case kept as typed (`" mp "` → `"mp"`); blank or whitespace-only is rejected by `FactoryCreate` (`ValidationError`), nothing created. *(Today: stored as typed; `""` and `"  "` accepted.)*
- **R8.** [BUG-895] [HR-2] The database itself refuses a second live factory with the same normalised name (lower-case of the trimmed name) in one workspace: a direct insert of a second live row whose name differs only in case fails with `IntegrityError`, while a soft-deleted row or a row of another workspace with that name is accepted. When such a duplicate reaches the insert through the manager (the Python check was passed, e.g. by a concurrent request), 409 `Factory with name '<name>' already exists` is raised — not an unhandled database error — and nothing is created. *(Today: no constraint; the duplicate is saved. Requires a partial unique index on live rows and mapping of the integrity error to 409.)*
- **R8a.** [BUG-895] (Q1) The same holds for the abbreviation, with its own partial unique index and 409 `Factory with abbreviation '<abbreviation>' already exists`. *(Today: no constraint.)*
- **R9.** ✅ (Q4) The workspace's subscription plan is not consulted: a factory is created however many live factories the workspace already has, including when the plan's `max_factories` is 1.
- **R10.** Given a `user_id` that is not an existing profile id, or a `workspace_id` that is not an existing workspace, the flush fails with `IntegrityError` (see Errors) and no factory is saved.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Live factory of the workspace has the name | `HTTPException` 409 | `Factory with name '<name>' already exists` — submitted name; same for the database-level violation [BUG-895] |
| Name free, live factory of the workspace has the abbreviation | `HTTPException` 409 | `Factory with abbreviation '<abbreviation>' already exists` — submitted value; same for the database-level violation [BUG-895] |
| Blank / whitespace-only name or abbreviation [BUG-896] | Pydantic `ValidationError` when building `FactoryCreate` (422 at the API) | Pydantic's message (not asserted) |
| `user_id` references no profile | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.ForeignKeyViolation` (constraint `factories_created_by_fkey`) | — (not asserted) |
| `workspace_id` references no workspace | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.ForeignKeyViolation` (constraint `factories_workspace_id_fkey`) | — (not asserted) |

**Side effects:** one `factories` row inserted and flushed (R1, R2). No commit. Nothing on any error.

---

## `FactoryManager.update_factory(session, factory_id, factory_data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `FactoryService.update_factory` ← `PUT /factories/{id}/`)

**Purpose:** Change the name and / or abbreviation of a live factory of the workspace and record who edited it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `factory_id` | int | factory to change |
| `factory_data` | `FactoryUpdate` | `name`, `abbreviation`: optional strings, `None` by default; intended: when given, trimmed and at least 1 character after trimming [BUG-896] *(Today: no validation.)* |
| `workspace_id` | int | caller's workspace; the factory must belong to it |
| `user_id` | int | editor; stored as `updated_by` (foreign key to `profiles.id`) |

**Returns:** the same `Factory` instance, modified and flushed, not committed.

**Rules:**
- **R1.** No factory with that id → `HTTPException` 404 `Factory with ID <factory_id> not found`.
- **R2.** The factory belongs to another workspace → the same 404 with the same message (indistinguishable from not existing); the factory is not changed.
- **R3.** The factory is soft-deleted → 400 `Cannot update deleted factory`, whatever the input (also when the requested name is taken — the 400 comes first); nothing changes.
- **R4.** Given a `name` that differs from the current name and is not used by another live factory of the workspace, the name is changed to it. Given such an `abbreviation`, the abbreviation is changed. Both can be changed in one call; a field that is not sent keeps its value.
- **R5.** Given a `name` (or `abbreviation`) equal to the factory's current value, no duplicate check is made for that field and it stays as it is. Changing only the case of the factory's own name or abbreviation (`"Second"` → `"SECOND"`) succeeds and is stored — the factory never conflicts with itself, today and after BUG-894.
- **R6.** Given a `name` that differs from the current one and is used by another live factory of the workspace → 409 `Factory with name '<name>' already exists` (`<name>` = submitted value as received); nothing changes — an `abbreviation` sent in the same call is not applied. Detection follows `_check_name_exists` R1–R7 with the factory itself excluded.
- **R7.** Given an `abbreviation` that differs from the current one and is used by another live factory of the workspace (the name being free, unchanged or not sent) → 409 `Factory with abbreviation '<abbreviation>' already exists`; nothing changes — a valid new `name` sent in the same call is not applied. Detection follows `_check_abbreviation_exists` R1–R7 with the factory itself excluded.
- **R8.** The name is checked first: when both the new name and the new abbreviation are taken, the name error of R6 is raised.
- **R9.** A field omitted or sent as explicit `null` is left unchanged (both columns are mandatory; `null` means "leave it", never "clear it"). `{"name": null, "abbreviation": "T4"}` changes only the abbreviation.
- **R10.** [BUG-896] [HR-1] A sent name is stored trimmed (`" Ops "` → `"Ops"`), and `" Ops "` sent to a factory already named `"Ops"` is "equal to the current name" (R5). A blank or whitespace-only name is rejected by `FactoryUpdate` itself — `ValidationError` (422 at the API), the manager is not reached, nothing changes. *(Today: stored as typed; `""` skips the duplicate check and is written, so the factory's name becomes the empty string — and a second factory can be given `""` too.)*
- **R10a.** [BUG-896] (Q1) The same for a sent abbreviation: stored trimmed, case kept; blank or whitespace-only rejected by `FactoryUpdate`. *(Today: stored as typed; `""` is written without a duplicate check.)*
- **R11.** [BUG-900] [HR-9] `updated_by` is set to `user_id` only when the call actually changes the name or the abbreviation. Given an empty request, only `null` fields, or values equal to the current ones, the call succeeds, returns the factory, and `updated_by` and `updated_at` keep their previous values (including `None`). *(Today: `updated_by` is set to `user_id` on every successful call, and `updated_at` with it whenever that changes the stored `updated_by`.)*
- **R12.** Whenever the name or abbreviation is changed, the database sets `updated_at` (from `None` to a value on the first change).
- **R13.** Nothing else is modified: `workspace_id`, `created_by`, `created_at`, `is_active`, `is_deleted`, `deleted_at`, `deleted_by` keep their values; other factories are not touched. (The schema has no other fields, so `is_active` cannot be changed through this method.)
- **R14.** [BUG-895] [HR-2] Renaming to a name another live factory of the workspace has is refused by the database as well: when such a rename reaches the flush (the Python check was passed, e.g. by a concurrent request), 409 `Factory with name '<name>' already exists` is raised — not an unhandled database error — and nothing changes. *(Today: no constraint; the duplicate rename is saved.)*
- **R14a.** [BUG-895] (Q1) The same for the abbreviation, with 409 `Factory with abbreviation '<abbreviation>' already exists`. *(Today: no constraint.)*
- **R15.** The name and abbreviation of a soft-deleted factory, or of a factory of another workspace, can be taken over by an update.
- **R16.** Given a `user_id` that is not an existing profile id (and a change that stamps it), the flush fails with `IntegrityError` (`ForeignKeyViolation`) and nothing is saved.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Not found / other workspace | `HTTPException` 404 | `Factory with ID <factory_id> not found` |
| Factory is soft-deleted | `HTTPException` 400 | `Cannot update deleted factory` |
| New name used by another live factory | `HTTPException` 409 | `Factory with name '<name>' already exists` — submitted name; same for the database-level violation [BUG-895] |
| New abbreviation used by another live factory (name not conflicting) | `HTTPException` 409 | `Factory with abbreviation '<abbreviation>' already exists` — submitted value; same for the database-level violation [BUG-895] |
| Blank / whitespace-only name or abbreviation [BUG-896] | Pydantic `ValidationError` when building `FactoryUpdate` (422 at the API) | Pydantic's message (not asserted) |
| `user_id` references no profile | `sqlalchemy.exc.IntegrityError` (`ForeignKeyViolation`) | — (not asserted) |

**Side effects:** on success with a real change: `name` and / or `abbreviation`, `updated_by` (and `updated_at` by the database), flushed. On a no-op: nothing written (intended, BUG-900). No commit. On error nothing is written.

---

## `FactoryManager.get_factory(session, factory_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `FactoryService.get_factory` ← `GET /factories/{id}/`)

**Purpose:** Fetch one factory of the caller's workspace by id.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `factory_id` | int | factory to fetch |
| `workspace_id` | int | caller's workspace |
| `include_deleted` | bool, default `False` | *(requires new parameter — BUG-897)* `True` also returns a soft-deleted factory. Today the parameter does not exist: passing it raises `TypeError`. |

**Returns:** the `Factory`.

**Rules:**
- **R1.** A live factory of the workspace is returned. Its `is_active` flag is not consulted: a live factory with `is_active = False` is returned too.
- **R2.** No factory with that id, or a factory of another workspace → 404 `Factory with ID <factory_id> not found` (same answer for both).
- **R3.** [BUG-897] [HR-4] A soft-deleted factory → 404 `Factory with ID <factory_id> not found` by default. *(Today: returned like a live one.)*
- **R4.** [BUG-897] With `include_deleted=True` a soft-deleted factory of the workspace is returned; a factory of another workspace still gives 404. *(Requires new parameter `include_deleted`.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Not found / other workspace / soft-deleted without `include_deleted` | `HTTPException` 404 | `Factory with ID <factory_id> not found` |

**Side effects:** none

---

## `FactoryManager.search_factories(session, workspace_id, search=None, skip=0, limit=100, include_deleted=False)`
**Shape:** search
**Persistence:** reads
**Visibility:** public (used by: `FactoryService.get_factories` ← `GET /factories/`, which passes `search`, `skip`, `limit` and never `include_deleted`; the endpoint enforces `skip >= 0`, `1 <= limit <= 1000`)

**Purpose:** List the workspace's factories, optionally filtered by a text found in the name or the abbreviation, one page at a time.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `workspace_id` | int | workspace to list |
| `search` | str or `None` | text looked for in name or abbreviation; `None` / `""` = no filter; not trimmed today (R7) |
| `skip` | int, default 0 | matching factories to skip; not validated here |
| `limit` | int, default 100 | maximum number returned; not validated here |
| `include_deleted` | bool, default `False` | `True` keeps soft-deleted factories; never passed by the API today (R5) |

**Returns:** a `list` of `Factory` (possibly empty).

**Rules:**
- **R1.** Only factories of `workspace_id` are returned; an unknown workspace id gives `[]`. `is_active` is not consulted: a live factory with `is_active = False` is listed.
- **R2.** [BUG-898] [HR-5] The filters (R4–R7) are applied to all factories of the workspace first; then `skip` matching factories are skipped and at most `limit` returned. A page is short only when there are no more matches, and a search finds a matching factory wherever it is in the workspace. *(Today: one page of `limit` rows — deleted and non-matching factories included — is loaded first and filtered afterwards. With 100 deleted factories created first and one live factory "Late", the default list is `[]` and searching `late` gives `[]`; only `skip=100` shows it.)*
- **R3.** [BUG-899] [HR-6] Results are ordered by name case-insensitively ascending, then `id` ascending, before `skip` / `limit`, so consecutive pages neither repeat nor skip factories. With `include_deleted=True`, deleted and live factories are ordered together by the same key. *(Today: no order is requested; the rows come back in whatever order the database produces.)*
- **R4.** [BUG-898] With `include_deleted=False` (the default) soft-deleted factories are never returned and never use up a place in the page. *(Today: they are removed only after the page was cut.)*
- **R5.** [BUG-901] [HR-4] With `include_deleted=True` soft-deleted factories of the workspace are returned along with live ones. The manager behaves so today; the option must become reachable from `GET /factories/` (fix in `FactoryService.get_factories` and the endpoint — integration-only). *(Today: service and endpoint never pass it.)*
- **R6.** Given a non-blank `search`, a factory matches when the text is a case-insensitive substring of its name **or** of its abbreviation (either is enough): `"mp"` finds a factory with abbreviation "MP" and one named "Camp Site"; `"PLANT"` finds "Main Plant". Inner whitespace of the text is significant. (Holds today as long as the factory is inside the loaded page — the whole-workspace part is R2.)
- **R6a.** (HR-8) The text is literal: `%`, `_` and `\` match only those characters — `search="%"` returns only factories whose name or abbreviation contains `%`, and `[]` when none does. *(Holds today — the filter is a Python substring test. It must keep holding when the BUG-898 fix moves the search into SQL `ILIKE`, which needs escaping; these cases pass today and guard that fix.)*
- **R7.** [BUG-902] (P1) `search=None`, `search=""` and a whitespace-only `search` (`"   "`, `"\t"`, `" \n "`) apply no search filter. Otherwise leading / trailing whitespace (`str.strip()`: spaces, tabs, newlines) is removed before matching: `" mp "` finds the factory with abbreviation "MP". *(Today: `None` and `""` apply no filter — that part holds — but the text is used untrimmed: `" mp "` finds only a factory whose name or abbreviation contains `" mp "` with both spaces, and `"   "` only one containing three consecutive spaces.)*
- **R8.** `search` combines with the deleted filter: with `include_deleted=False` a matching soft-deleted factory is not returned; with `include_deleted=True` it is.
- **R9.** No factories in the workspace, no match, or `skip` at or past the number of matches → `[]`. `limit=0` → `[]`. Defaults are `skip=0`, `limit=100`: given 101 live factories, exactly 100 are returned. A negative `limit` or `skip` makes Postgres reject the query (see Errors).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInLimitClause` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`; `.orig` is `psycopg2.errors.InvalidRowCountInResultOffsetClause` | `OFFSET must not be negative` |

**Side effects:** none

---

## `FactoryManager.delete_factory(session, factory_id, workspace_id, user_id)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `FactoryService.delete_factory` ← `DELETE /factories/{id}/`, which answers 200 with the factory)

**Purpose:** Soft-delete a live factory of the workspace, leaving everything that belongs to it untouched, unless it has open production batches.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `factory_id` | int | factory to delete |
| `workspace_id` | int | caller's workspace |
| `user_id` | int | deleter; stored as `deleted_by` (foreign key to `profiles.id`) |

**Returns:** the same `Factory` instance, soft-deleted and flushed, not committed.

**Rules:**
- **R1.** No factory with that id, or a factory of another workspace → 404 `Factory with ID <factory_id> not found`; the other workspace's factory is not changed.
- **R2.** The factory is already soft-deleted → 400 `Factory is already deleted`; its `deleted_at` and `deleted_by` stay as they were.
- **R3.** Given a live factory, it gets `is_deleted = True`, `deleted_at = utcnow()` (naive UTC) and `deleted_by = user_id`.
- **R4.** The row is kept and nothing else on it is changed by the method: `name`, `abbreviation`, `workspace_id`, `created_by`, `created_at`, `updated_by` keep their values and **`is_active` stays `True`**. `updated_at` becomes non-null because the database sets it on the UPDATE.
- **R5.** ✅ (Q2; relies on standing decision 2; narrowed by BUG-1331, see R5a.) Apart from an open production batch (R5a), nothing that belongs to the factory blocks the delete, and nothing that belongs to it is changed: a factory with machines, factory sections, stock rows, production lines, or `completed` or `cancelled` production batches is deleted like an empty one, and afterwards each of those rows is exactly as before (`is_deleted = False` where the table has the column, `is_active` unchanged, no deletion stamp). No cascade.
- **R5a.** [BUG-1331] (Q2, owner) A live factory with an **open batch** is not deleted: `ValueError` with the message `"Factory has open production batches"` and the list of blockers (R5b; 400 at the API, the translation belongs in `FactoryService`, FU-6); nothing written (R5c). An open batch is a `production_batches` row with `status` `draft` or `in_progress` whose line has `production_lines.factory_id` = this factory. `completed` and `cancelled` batches do not block. The line's `is_active` is not consulted: a batch on an inactive line blocks. A batch on a line of any other factory does not count, whatever its status. Checked after R1 and R2 (a missing, other-workspace or already-deleted factory gets those errors, whatever its batches) and before any write, so it also comes before the failure of R8. **A row linking across workspaces is invalid data (HR-16), but it still refuses the delete:** a **cross-workspace row** is an open batch of this factory whose own `workspace_id` differs from the factory's, or whose line's `workspace_id` differs from the factory's, because the line is the link between the two. So a batch of the factory's workspace on another workspace's line of this factory counts as cross-workspace and is not listed by id (as `machine_item_manager` `delete_item` R5a: a W1 return on a W2 purchase order), decided by Claude under the reviewer's delegation (2026-11-02). A cross-workspace row with `status` `completed` or `cancelled` does not block. *(Today: nothing is looked at; the factory is deleted.)*
- **R5b.** [BUG-1331] **The refusal lists every blocker.** The `ValueError` has exactly two args: `args[0]` = `"Factory has open production batches"`; `args[1]` = a `list` of `dict`s, each exactly `{"type": "production_batch", "id": <batch id>}`, one per open batch of the factory's workspace, however many there are (no page, no cap), sorted by `"id"` ascending as numbers. When at least one cross-workspace row of R5a exists, the list ends with exactly one `{"type": "other_workspace"}`, the only key, however many such rows there are, last whatever their ids (HR-16). Nothing of another workspace is shown. A factory whose only blockers are such rows gets a list of that one entry. Only open batches are listed; the list is never empty when raised. *(Today: no refusal.)*
- **R5c.** [BUG-1331] The refusal comes before any write, not after one that is undone: on the refused call no `UPDATE`, `INSERT` or `DELETE` is sent, no savepoint is opened, the session is not flushed, committed or rolled back, the factory is not modified in memory, and changes the caller has pending in the session stay pending. *(Today: no refusal.)*
- **R6.** After the delete, in the same session: the factory is no longer returned by `search_factories` with the default `include_deleted=False` and is returned with `include_deleted=True`; its name and abbreviation can be used for a new factory (`create_factory` R6) or taken by a rename (`update_factory` R15); `update_factory` answers 400 for it (`update_factory` R3). `get_factory` follows `get_factory` R3 / R4.
- **R7.** The change is flushed, not committed: rolling back makes the factory live again. Other factories are never touched.
- **R8.** Given a `user_id` that is not an existing profile id, the flush fails with `IntegrityError` (`ForeignKeyViolation`) and the factory stays live.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Not found / other workspace | `HTTPException` 404 | `Factory with ID <factory_id> not found` |
| Already soft-deleted | `HTTPException` 400 | `Factory is already deleted` |
| `user_id` references no profile | `sqlalchemy.exc.IntegrityError`; `.orig` is `psycopg2.errors.ForeignKeyViolation` | — (not asserted) |
| [BUG-1331] live factory with an open batch (R5a) | `ValueError` (two args, R5b; 400 at the API, FU-6) | `args[0]` = `Factory has open production batches`; `args[1]` = the blockers |
| [BUG-1331] a cross-workspace row in a blocking state (R5a), alone or with normal blockers | `ValueError` (two args, R5b) | same `args[0]`; `args[1]` ends with one `{"type": "other_workspace"}`, nothing of the other workspace in it |

**Side effects:** one `factories` row updated (`is_deleted`, `deleted_at`, `deleted_by`; `updated_at` by the database) and flushed. No commit. No other table is written. On a refusal nothing is written (R5c). There is no way to undo it through the application (Q3).

---

## `FactoryManager._check_name_exists(session, workspace_id, name, exclude_id=None)`
**Shape:** validator
**Persistence:** reads
**Visibility:** internal (used by: `create_factory` without `exclude_id`; `update_factory` with `exclude_id` = the factory being edited)

**Purpose:** Tell whether a live factory of the workspace already uses a name.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `workspace_id` | int | workspace to check |
| `name` | str | name to look for |
| `exclude_id` | int or `None` | factory id to ignore (the one being renamed); `None` = ignore none |

**Returns:** `True` if a matching live factory exists, else `False`. Never raises.

**Rules:**
- **R1.** A live factory of the workspace whose name equals `name` (in the sense of R4) → `True`.
- **R2.** A factory with that name in another workspace is not considered → `False`.
- **R3.** A soft-deleted factory with that name is ignored → `False` (unless a live one matches too).
- **R4.** [BUG-894] [HR-2] Names match regardless of case and of leading / trailing whitespace (`str.strip()`): with a live "Main Plant", each of `"main plant"`, `"MAIN PLANT"`, `"Main Plant "`, `"\tMain Plant"` → `True`. Inner differences do not match (`"Main  Plant"` with two spaces, `"Main Plant 2"` → `False`). *(Today: exact comparison — only `"Main Plant"` itself → `True`; every case or whitespace variant → `False`.)*
- **R5.** [BUG-893] [HR-2] Every live factory of the workspace is examined, however many factories (live or deleted) it has: a matching live factory is found also when more than 100 factories exist. *(Today: only the first 100 factories of the workspace — deleted ones included, in no defined order — are examined; a match outside them → `False`. See Notes for the test designer.)*
- **R6.** Given `exclude_id`, the factory with that id is ignored even when its name matches (→ `False` if it is the only match); a matching live factory with any other id still gives `True`. With `exclude_id=None` nothing is ignored.
- **R7.** A workspace with no factories → `False`. Only the name is compared: a factory whose *abbreviation* equals `name` does not match.

**Errors:** none

**Side effects:** none

---

## `FactoryManager._check_abbreviation_exists(session, workspace_id, abbreviation, exclude_id=None)`
**Shape:** validator
**Persistence:** reads
**Visibility:** internal (used by: `create_factory` without `exclude_id`; `update_factory` with `exclude_id` = the factory being edited)

**Purpose:** Tell whether a live factory of the workspace already uses an abbreviation.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `workspace_id` | int | workspace to check |
| `abbreviation` | str | abbreviation to look for |
| `exclude_id` | int or `None` | factory id to ignore; `None` = ignore none |

**Returns:** `True` if a matching live factory exists, else `False`. Never raises.

**Rules:**
- **R1.** A live factory of the workspace whose abbreviation equals `abbreviation` (in the sense of R4) → `True`.
- **R2.** A factory with that abbreviation in another workspace is not considered → `False`.
- **R3.** A soft-deleted factory with that abbreviation is ignored → `False` (unless a live one matches too).
- **R4.** [BUG-894] (Q1) Abbreviations match regardless of case and of leading / trailing whitespace (`str.strip()`): with a live "MP", each of `"mp"`, `"Mp"`, `" MP "`, `"MP\n"` → `True`; `"MP2"` and `"M P"` → `False`. *(Today: exact comparison — only `"MP"` → `True`.)*
- **R5.** [BUG-893] [HR-2] Every live factory of the workspace is examined, however many factories it has. *(Today: only the first 100 factories of the workspace, deleted ones included, in no defined order; a match outside them → `False`.)*
- **R6.** Given `exclude_id`, the factory with that id is ignored even when its abbreviation matches; a matching live factory with any other id still gives `True`. With `exclude_id=None` nothing is ignored.
- **R7.** A workspace with no factories → `False`. Only the abbreviation is compared: a factory whose *name* equals `abbreviation` does not match.

**Errors:** none

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 53–60 | name exists → 409 / not → continue | `create_factory` R1, R3, R5 |
| 63–70 | abbreviation exists → 409 / not → continue (only reached when the name is free) | `create_factory` R4, R5 |
| 73–77 | dump of `name` + `abbreviation`, plus `workspace_id`, `created_by`; no normalisation; no plan check | `create_factory` R1, R2, R7, R7a, R9 |
| 77 / `dao/base.py` 76–84 | `create`: dict branch (always a dict here) → row, add, flush (foreign keys) | `create_factory` R1, R2, R10 |
| — (no unique constraint on `factories`) | duplicate past the Python check | `create_factory` R8, R8a; `update_factory` R14, R14a |
| 105–112 | factory not found (incl. other workspace) → 404 | `update_factory` R1, R2 |
| 115–119 | `is_deleted` → 400 (before any conflict check) | `update_factory` R3 |
| 122 | `name` truthy and different from current → check / else skip (`None`, `""`, same) | `update_factory` R4, R5, R9, R10 |
| 123–130 | name exists (self excluded) → 409 | `update_factory` R6, R8 |
| 133 | `abbreviation` truthy and different from current → check / else skip | `update_factory` R4, R5, R9, R10a |
| 134–141 | abbreviation exists (self excluded) → 409 (after the name check) | `update_factory` R7, R8 |
| 144 | `exclude_unset` / `exclude_none`: omitted and `null` dropped; `""` kept | `update_factory` R9, R10, R10a |
| 145 | `updated_by` always set | `update_factory` R11 |
| 147 / `dao/base.py` 108–119 | `update`: dict branch (always a dict here); only existing attributes set (always true here); add + flush | `update_factory` R4, R12, R13, R16 |
| 170–178 | factory not found (incl. other workspace) → 404 / found → returned | `get_factory` R1, R2 |
| 170 (no `is_deleted` check) | soft-deleted factory returned | `get_factory` R3, R4 |
| 186–189 | defaults `search=None`, `skip=0`, `limit=100`, `include_deleted=False` | `search_factories` R4, R7, R9 |
| 206–208 / `dao/factory.py` 34–40 | workspace filter, offset / limit before any other filter, no `ORDER BY`; `limit=0`; negative values | `search_factories` R1, R2, R3, R9, Errors |
| 211–212 | `include_deleted` false → drop deleted (after paging) / true → keep | `search_factories` R4, R5, R8 |
| 215 | `search` truthy → filter / `None`, `""` → none; whitespace-only is truthy | `search_factories` R6, R7 |
| 216–221 | lower-cased substring in name OR abbreviation; untrimmed; Python `in` (literal) | `search_factories` R6, R6a, R7, R8 |
| 212, 217 | comprehensions over empty / one / many | `search_factories` R9 |
| 247–255 | factory not found (incl. other workspace) → 404 | `delete_factory` R1 |
| 258–262 | already deleted → 400 | `delete_factory` R2 |
| — (no check of batches exists today) | open batch of the factory, own or cross-workspace → `ValueError`; closed batches, lines, other factories → continue; belongs between 258–262 and 265 | `delete_factory` R5, R5a, R5b, R5c |
| 265 / `dao/factory.py` 106–111 | three fields set (`is_active` untouched), `utcnow()`, add + flush, same instance; no other table | `delete_factory` R3, R4, R5, R6, R7, R8 |
| `dao/factory.py` 56–63 | lookup by id AND workspace; no `is_deleted` filter | `update_factory` R1–R3; `get_factory` R1–R3; `delete_factory` R1, R2 |
| 289, 317 / `dao/factory.py` 34–40 | default `skip=0`, `limit=100`: only the first 100 rows of the workspace, deleted included, unordered | `_check_name_exists` R2, R5; `_check_abbreviation_exists` R2, R5 |
| 290, 318 | loop over empty / one / many | `_check_name_exists` R1, R7; `_check_abbreviation_exists` R1, R7 |
| 292–293, 320–321 | deleted → `continue` | `_check_name_exists` R3; `_check_abbreviation_exists` R3 |
| 294 | exact `==` on name | `_check_name_exists` R1, R4, R7 |
| 322 | exact `==` on abbreviation | `_check_abbreviation_exists` R1, R4, R7 |
| 294, 322 | `exclude_id is None` / `factory.id != exclude_id` | `_check_name_exists` R6; `_check_abbreviation_exists` R6 |
| 295–296, 323–324 | `True` on first match / `False` after the loop | `_check_name_exists` R1, R7; `_check_abbreviation_exists` R1, R7 |
