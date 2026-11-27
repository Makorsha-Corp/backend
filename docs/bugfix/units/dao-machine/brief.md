# Fix brief: dao-machine

## 1. Unit

| | |
|---|---|
| Slug | `dao-machine` |
| Source file | `app/dao/machine.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-machine` |
| Branch | `bugfix/dao-machine` (from `origin/main`) |
| Risk | `normal` (BUG-887 is a trivial-list pattern; BUG-886 `wrong-dialect-json-accessor`, BUG-888 `unescaped-like-wildcards`, BUG-889 / BUG-890 / BUG-891 `join-ignores-soft-deleted` and BUG-892 `whitespace-search-empties-results` are not on the list) |

## 2. Bugs

### BUG-886: Filtering the machines page by latest status always crashes
- **Pattern:** `wrong-dialect-json-accessor`
- **Where:** `DAOMachine.search_advanced`; reached through `GET /machines/?latest_event_type=…`.
- **Today:** The filter reads the status with `.astext`, which the activity log's `metadata` column (declared as generic `JSON`) does not have; every call with `latest_event_type` set raises `AttributeError` (500) before any query is sent.
- **Intended:** The filter returns the machines whose latest `status_updated` activity row has that status; latest = greatest `created_at`, ties broken by greatest `id`; machines with no status change never match; each machine once (reviewer confirmed, 2026-10-10).
- **Example:** A user picks "Running" in the status filter of the machines page: the page fails with a server error, even though 5 machines are running.

### BUG-887: Machine list name sort is collation-dependent on case-only ties
- **Pattern:** `unordered-pagination`
- **Where:** `DAOMachine.search_advanced`; reached through `GET /machines/`.
- **Today:** `ORDER BY machines.name, id` with the database's default collation; "Bolt" / "bolt" are ordered by the collation, not by `id`.
- **Intended:** HR-6: name case-insensitive (ascending or descending as requested), then `id` ascending.

### BUG-888: `%` and `_` in machine search act as wildcards
- **Pattern:** `unescaped-like-wildcards`
- **Where:** `DAOMachine.search_advanced`; reached through `GET /machines/`.
- **Today:** Search text placed in `ILIKE '%…%'` unescaped; `%` or `_` alone matches every machine, `\` acts as the escape character.
- **Intended:** HR-8: `%`, `_` and `\` match literally in name, model number and manufacturer.

### BUG-889: Filtering machines by a soft-deleted section still returns its machines
- **Pattern:** `join-ignores-soft-deleted`
- **Where:** `DAOMachine.get_by_section`, and the section filter of `DAOMachine.search_advanced`.
- **Today:** The section filter joins only the assignment table and never looks at `factory_sections.is_deleted`; left-over assignments to a deleted section still match.
- **Intended:** HR-4: a soft-deleted section matches no machine; assignment rows are kept.

### BUG-890: Machines of a soft-deleted factory still appear on the machines page
- **Pattern:** `join-ignores-soft-deleted`
- **Where:** `DAOMachine.search_advanced`; reached through `GET /machines/`.
- **Today:** The machine search never looks at the factory row; live machines of a soft-deleted factory are listed, with or without a factory filter.
- **Intended:** A machine whose factory has `is_deleted = True` is hidden (not returned), by the factory's state alone; the machine row is never deleted or altered, and the machine is listed again, unchanged, once the factory is no longer deleted; an inactive-but-live factory still counts (per BUG-882 precedent; reviewer confirmed 2026-10-10: hidden so they can be put back if the user undoes the factory delete).
- **Example:** Factory 9 "Old Plant" is deleted while it still has machine "Press 4". The machines page still lists "Press 4" with factory id 9.

### BUG-891: Factory / section machine lookups return machines of a soft-deleted factory
- **Pattern:** `join-ignores-soft-deleted`
- **Where:** `DAOMachine.get_by_factory`, `DAOMachine.get_by_section`; reached through work-order generation and the machine duplicate-name check.
- **Today:** Neither lookup looks at the factory row; work-order drafts are still generated for machines of a deleted factory.
- **Intended:** A machine whose factory has `is_deleted = True` is hidden (not returned by either lookup), by the factory's state alone; machine and assignment rows are never deleted or altered, and the machine is returned again, unchanged, once the factory is no longer deleted (per BUG-882 / BUG-884 precedent; reviewer confirmed 2026-10-10).
- **Example:** A weekly template is run for Factory 9, which was deleted last month. Drafts are still created for its 12 machines.

### BUG-892: Machine search text is not trimmed
- **Pattern:** `whitespace-search-empties-results`
- **Where:** `DAOMachine.search_advanced`; reached through `GET /machines/`.
- **Today:** `" bolt "` finds nothing; a whitespace-only search matches only values containing those spaces.
- **Intended:** Leading / trailing whitespace removed before matching; whitespace-only search applies no filter; whitespace = spaces, tabs and newlines (`str.strip()`) (per BUG-637 precedent; reviewer confirmed, 2026-10-10).
- **Example:** A user pastes "Press 4 " (with a trailing space) into the search box and gets an empty list.

## 3. Intended behaviour (spec rules, copied)

Facts for the whole file:
- Table `machines` (`app.models.machine.Machine`): `workspace_id`, `factory_id` NOT NULL; `name` String NOT NULL (no unique constraint); `is_running`, `is_active`, `is_deleted` Boolean NOT NULL; `model_number`, `manufacturer` String(200) nullable; `created_at` NOT NULL (server default `now()`); `updated_at` set by the database on every UPDATE.
- Soft delete of a machine = `is_deleted = True` with `is_active = False`, `deleted_at`, `deleted_by`. Every list here looks only at `is_deleted`; **`is_active` and `is_running` are never used to hide a machine.**
- `machine.factory_section_id` / `machine.factory_section_name` are read-only properties read from the machine's assignment row (`machine_section_assignments`, unique on `machine_id`, no soft-delete column), or `None` when the machine has no assignment.
- `FactorySection` (`app.models.factory_section`): `is_active` (default `True`), `is_deleted` (default `False`). `Factory` (`app.models.factory`): `is_active` (default `True`), `is_deleted` (default `False`); a factory soft delete sets `is_deleted = True` and leaves `is_active` and the factory's machines untouched.
- Activity log `machine_activity_events` (`app.models.machine_activity_event.MachineActivityEvent`): NOT NULL `workspace_id`, `machine_id`, `event_type`, `created_at` (naive UTC); nullable `metadata_json` (Python attribute; database column `metadata`, declared type generic `JSON`, stored as Postgres `json`). A status change is a row with `event_type = "status_updated"` and `metadata_json = {"status": "<IDLE|RUNNING|OFF|MAINTENANCE>", ...}`. `MachineEventTypeEnum` (`app.models.enums`, a `str` enum) members `IDLE`, `RUNNING`, `OFF`, `MAINTENANCE` (value = name).
- Every parameter after `db` is keyword-only. The class never commits; lists only read.

### `DAOMachine.get_by_factory(db, *, factory_id, workspace_id, skip=0, limit=100)`
Used by `MachineManager._check_name_exists_in_factory` (default paging) and `resolve_template_machine_ids` in `app/utils/work_order_generation.py` (`limit=1000`). Returns a `list` of `Machine`, each with its section assignment loaded.
- **R1.** Returns the machines with `workspace_id` and `factory_id` equal to the arguments. A machine of the same factory id in another workspace, or of another factory in the same workspace, is never returned.
- **R2.** Soft-deleted machines (`is_deleted = True`) are never returned. `is_active` and `is_running` are not consulted: a machine with `is_active = False`, `is_deleted = False` is returned.
- **R3.** An unknown factory id, `factory_id=0`, an unknown workspace id, or a factory with no live machines returns `[]`.
- **R3a.** [BUG-891] When the factory itself is soft-deleted (`factories.is_deleted = True`), its machines are hidden: `[]` is returned even though it has live machines. They are hidden by the factory's state alone — nothing about the machines themselves says "deleted". *(Today: the factory row is never looked at — the live machines of a soft-deleted factory are returned.)*
- **R3b.** Holds today and after the fix: (1) the call changes nothing — the machines of a soft-deleted factory stay in the database exactly as they were (`is_deleted = False`, `is_active`, `deleted_at = None`, every other column and the section assignment row unchanged); (2) a factory that is live but inactive (`is_active = False`, `is_deleted = False`) hides nothing: its machines are returned; (3) once the factory is no longer deleted (`factories.is_deleted` back to `False`), its machines are returned again, unchanged, with nothing done to the machine rows.
- **R4.** `skip` and `limit` are applied after filtering: with defaults at most 100 machines are returned — given 101 live machines in the factory, exactly 100; soft-deleted machines (and, after the fix, machines hidden by R3a) never use up a place in the page.
- **R5.** `limit=0` returns `[]`; `skip` at or past the number of matching machines returns `[]`. A negative `limit` raises `sqlalchemy.exc.DataError` (pgcode `2201W`, "LIMIT must not be negative"); a negative `skip` raises `DataError` (pgcode `2201X`, "OFFSET must not be negative").
- **R6.** (BUG-343, **not in this unit**, see §6.) Today no ordering is requested; leave it so.
- **R7.** Each machine appears exactly once, whether or not it has a section assignment.
- **R8.** Section data is available on every returned machine: `factory_section_id` and `factory_section_name` give the assigned section's id and name; both are `None` for a machine without an assignment.

Side effects: none.

### `DAOMachine.get_by_section(db, *, factory_section_id, workspace_id, skip=0, limit=100)`
Used by `resolve_template_machine_ids` in `app/utils/work_order_generation.py` (`limit=1000`). Returns a `list` of `Machine`, each with its section assignment loaded.
- **R1.** Returns the machines of the workspace that have an assignment row pointing at `factory_section_id`. Machines without an assignment, and machines assigned to another section, are never returned.
- **R2.** Workspace isolation follows the machine: a machine of another workspace is never returned, even when its assignment points at the given section id. Soft-deleted machines are never returned although their assignment row still exists; `is_active` and `is_running` are not consulted.
- **R3.** An unknown section id, `factory_section_id=0`, or a section with no assigned live machine in the workspace returns `[]`.
- **R3a.** [BUG-891] A machine whose factory is soft-deleted (`factories.is_deleted = True`) is hidden: it is not returned, although the machine, its assignment and the section are all live. *(Today: the factory row is never looked at — such a machine is returned.)*
- **R3b.** Holds today and after the fix: (1) the call changes nothing — the machine of a soft-deleted factory and its assignment row stay exactly as they were; (2) a machine whose factory is live but inactive (`is_active = False`, `is_deleted = False`) is returned; (3) once the factory is no longer deleted, the machine is returned again, unchanged and still assigned to the same section, with nothing done to the machine or assignment rows.
- **R4.** [BUG-889] (HR-4) When the section itself is soft-deleted (`factory_sections.is_deleted = True`), `[]` is returned even if assignment rows still point at it; the assignment rows are not changed. A section that is live but inactive (`is_active = False`) is unaffected. *(Today: the section row is never looked at — machines assigned to a soft-deleted section are returned.)*
- **R5.** Paging behaves as `get_by_factory` R4–R5 (defaults `skip=0`, `limit=100`; 101 assigned machines → exactly 100; `limit=0` → `[]`; negative values → the same `DataError`s).
- **R6.** Each machine appears exactly once (a machine has at most one assignment).
- **R7.** (BUG-343, **not in this unit**, see §6.) Today no ordering is requested; leave it so.
- **R8.** Every returned machine reports the section it was found through: `factory_section_id` equals the argument and `factory_section_name` is that section's name.

Side effects: none.

### `DAOMachine.search_advanced(db, *, workspace_id, factory_id=None, factory_section_id=None, is_running=None, search=None, has_model_number=None, has_manufacturer=None, latest_event_type=None, sort_by="name", sort_dir="asc", skip=0, limit=100)`
Used by `MachineManager.search_machines` ← `MachineService.get_machines` ← `GET /machines/`. The endpoint enforces `skip >= 0`, `1 <= limit <= 1000` and passes `latest_event_type` as a `MachineEventTypeEnum`; `sort_by` / `sort_dir` / `search` are free text there. For the maintenance-window filter and the `maintenance_date` sort the manager calls it with `skip=0, limit=10_000` and pages in Python. Returns a `list` of `Machine`, each with its section assignment loaded.

Inputs: `factory_id` `None` = all factories, any integer (incl. `0`) filters; `factory_section_id` `None` = all machines, assigned or not, any integer (incl. `0`) filters; `is_running` `None` = both; `search` `None` and `""` = no search; `has_model_number` / `has_manufacturer` `None` = no filter; `latest_event_type` `None` = no filter; `sort_by` `"name"` or `"created_at"`, anything else behaves as `"name"`; `sort_dir` exactly `"desc"` = descending, anything else ascending.

- **R1.** Only machines with `workspace_id` equal to the argument are returned; a machine of another workspace is never returned, whatever the other filters. An unknown workspace id returns `[]`.
- **R2.** Soft-deleted machines are never returned and never use up a place in the page. There is no way to include them. `is_active` is not consulted.
- **R3.** With no optional filter, every live machine of the workspace is returned (paged), whether or not it has a section assignment, each exactly once.
- **R3a.** [BUG-890] A machine whose factory is soft-deleted (`factories.is_deleted = True`) is hidden — by the factory's state alone, the machine itself being live — and is never returned: not without a factory filter, not when that factory's own id is given as `factory_id`, and whatever the other filters; it does not use up a place in the page. Example: Factory A live with machine "Lathe", Factory B soft-deleted with machine "Press" → with no filter only "Lathe"; with `factory_id` = B `[]`; with `limit=1` and `sort_dir="desc"` the single row is "Lathe". *(Today: both machines are returned, "Press" alone for `factory_id` = B, and "Press" for the `limit=1` descending case.)*
- **R3b.** Holds today and after the fix: a machine whose factory is live but inactive (`factories.is_active = False`, `is_deleted = False`) is returned like any other. Searching never changes anything: the machine row of a soft-deleted factory stays as it was (`is_deleted = False`).
- **R3c.** Holds today and after the fix: once its factory is no longer deleted, a machine hidden per R3a is returned again — with no filter and for that factory's id — with every column and its section assignment exactly as before, and with nothing done to the machine row. Example: Factory B soft-deleted with machine "Press" (running, model number "P-4", assigned to section "Line 1") → Factory B restored → "Press" is listed, still running, model number "P-4", section "Line 1".
- **R4.** Given any integer `factory_id`, only machines with that `factory_id` are returned; `factory_id=0` or an unknown id returns `[]`; `None` applies no factory filter.
- **R5.** Given any integer `factory_section_id`, only machines with an assignment row pointing at that section are returned — unassigned machines and machines of other sections are excluded; `0` or an unknown id returns `[]`; `None` applies no section filter. Each matching machine appears exactly once.
- **R6.** `factory_id` and `factory_section_id` given together must both match (a section id of another factory than `factory_id` returns `[]`).
- **R6a.** [BUG-889] (HR-4) Given the id of a soft-deleted section (`factory_sections.is_deleted = True`), `[]` is returned even if assignment rows still point at it. Without a section filter, a machine with such a left-over assignment is still listed (the machine itself is live). *(Today: machines assigned to the soft-deleted section are returned for its id.)*
- **R7.** `is_running=True` returns only machines with `is_running = True`; `False` only those with `is_running = False`; `None` both.
- **R8.** [BUG-892] `search=None`, `search=""` and a whitespace-only `search` (e.g. `"   "`, `"\t"`, `" \n "`) apply no search filter. Otherwise leading / trailing whitespace is removed before matching (`" bolt "` and `"\tbolt\n"` find "Bolt cutter"); inner whitespace is kept as typed. "Whitespace" is what Python's `str.strip()` removes. *(Today: `None` and `""` apply no filter — that part holds — but the text is used untrimmed.)*
- **R9.** [BUG-888] (HR-8) A search matches a machine when the text is a case-insensitive **literal** substring of its `name`, its `model_number` or its `manufacturer` (any one is enough; `"BOLT"` finds "bolt" and "Bolt cutter"; `"sie"` finds manufacturer "Siemens"). A `NULL` model number / manufacturer simply does not match. `note`, the factory name and the section name are not searched. `%`, `_` and `\` are matched literally: `%` alone finds only machines containing `%` (e.g. model number "50%"), `_` alone only those containing `_`, `a\b` finds name `a\b` and not `ab`. *(Today: `%` and `_` act as wildcards; `\` is the `ILIKE` escape character, so `a\b` matches "ab" and not `a\b`.)*
- **R10.** `has_model_number=True` returns only machines whose `model_number` is neither `NULL` nor `""`; `False` only those whose `model_number` is `NULL` or `""`; `None` no filter. A whitespace-only model number counts as having one. (Intended at the DAO; must not change.)
- **R11.** `has_manufacturer` behaves exactly as R10 on `manufacturer`, independently of `has_model_number`.
- **R12.** [BUG-886] Given a `latest_event_type`, the call succeeds and returns only the machines whose latest status change has that status, where a status change is an activity row of that machine with `event_type = "status_updated"` and its status is the `"status"` value of the row's `metadata_json`. `latest_event_type=None` applies no status filter (holds today). *(Today: every call with `latest_event_type` set raises `AttributeError` while the query is built; no query is sent.)*
- **R12a.** [BUG-886] "Latest" is the status change with the greatest `created_at`; among rows sharing that `created_at`, the one with the greatest `id`. Example: machine A has RUNNING at 10:00 and IDLE at 11:00 → A matches `IDLE` and not `RUNNING`. Machine C has RUNNING and then OFF, both at 11:00 (OFF inserted second) → C matches `OFF` only.
- **R12b.** [BUG-886] A machine with no status change never matches any `latest_event_type`. Activity rows of other types (`"created"`, `"updated"`, `"deactivated"`, …) are ignored even when newer and even when their metadata has a `"status"` key.
- **R12c.** [BUG-886] A latest status change whose `metadata_json` is `NULL`, or has no `"status"` key, matches no `latest_event_type`; older status changes of that machine are not consulted instead.
- **R12d.** [BUG-886] Only status changes recorded in the given workspace count (`machine_activity_events.workspace_id == workspace_id`).
- **R12e.** [BUG-886] Each matching machine appears exactly once, also when two status changes with the same status share the newest `created_at`; the filter combines with all other filters (R13a), sorting and paging like any other.
- **R13.** `sort_by="name"` sorts by machine name, `sort_by="created_at"` by creation time; any other value (e.g. `"maintenance_date"`, `"createdAt"`, `""`) sorts by name, with no error. (Intended at the DAO; must not change.)
- **R13a.** All given filters combine with AND; the three search alternatives (name, model number, manufacturer) combine with OR.
- **R14.** [BUG-887] (HR-6) Sorting by name is case-insensitive: ascending gives "apple", "Banana", "Zulu"; descending the reverse. Machines whose names differ only in case, or are identical, come back in `id` ascending order — in both directions. *(Today: the database's default collation decides a case-only difference instead of the `id`.)*
- **R15.** `sort_dir="desc"` (exactly, lower-case) sorts descending; any other value (`"asc"`, `"DESC"`, `"descending"`, `""`) sorts ascending, with no error. (Intended at the DAO; must not change.)
- **R16.** Sorting by `created_at` puts the earliest-created machine first ascending and last descending; machines with the same `created_at` come back in `id` ascending order in both directions.
- **R17.** `skip` and `limit` are applied after all filtering and ordering, so consecutive windows partition the matching machines with no repeats or gaps. With defaults at most the first 100 are returned.
- **R18.** `limit=0` returns `[]`; `skip` at or past the number of matching machines returns `[]`. Negative `limit` / `skip` raise the same `DataError`s as `get_by_factory` R5.

Side effects: none.

### `DAOMachine.soft_delete` and `DAOMachine.restore` (not in a bug; must not change)
- `soft_delete` R5: the change is flushed, not committed; in the same session the machine is no longer returned by `get_by_factory`, `get_by_section` or `search_advanced`, and is still returned by the inherited `get_by_id_and_workspace`.
- `restore` R5: after a restore the machine is returned again by `get_by_factory`, `search_advanced` and (if it has an assignment) `get_by_section` — given its factory is live.
- `restore` R7: the factory is not looked at and never changed; restoring a machine whose factory is soft-deleted succeeds.
- `restore` R7a [BUG-890] [BUG-891]: a machine restored per R7 stays hidden for as long as its factory is soft-deleted: not returned by `search_advanced` (its R3a) nor by `get_by_factory` / `get_by_section` (their R3a). It appears in all three as soon as the factory is no longer deleted, with nothing further done to the machine.

### Inherited `BaseDAO` methods (not overridden; must not change)
- The raw lookups stay raw (HR-4 scope): `get`, `get_by_id_and_workspace` and `get_by_workspace` return soft-deleted machines, and machines of soft-deleted factories, like any other. Hiding them is the calling manager's decision. Many managers fetch one machine through `get_by_id_and_workspace`; it must not start hiding anything.

## 4. Rules that apply

- **HR-4. Soft-deleted rows are hidden unless asked for.** Lists/searches exclude soft-deleted rows by default. Filters, joins and searches through related rows ignore related rows that are soft-deleted (e.g. a deleted section neither filters nor matches). Scope: managers and module-specific DAO query methods; the generic `BaseDAO` methods stay raw.
- **HR-5. Filter first, then page.** All filtering happens in the query before `skip` / `limit`; a page is only short when there are no more results.
- **HR-6. Every paged or top-N result has a stable order.** Default: name case-insensitive ascending, then `id` ascending. No order recipe counts as deterministic unless it ends in `id`.
- **HR-8. Search text is literal.** Text placed in `LIKE` / `ILIKE` patterns is escaped: `%` and `_` (and, per the bug row, `\`) match literally.
- **HR-16. Nothing links across workspaces.** Any new join or subquery must stay bounded by the workspace, directly or through the outer `machines.workspace_id` filter; no response may show another workspace's rows.
- **"Hidden, not cascaded"** (reviewer decision 2026-10-10, applied to BUG-882 / BUG-884 / BUG-890 / BUG-891): things inside a soft-deleted factory are hidden by the factory's state alone; their rows are never deleted or altered, so restoring the factory brings them back exactly as they were. An inactive-but-live factory hides nothing.
- **Whitespace search** (BUG-637 precedent): trim with `str.strip()`; whitespace-only = no search.
- No owner answer (OQ-n) touches these bugs.

## 5. Scope

- May change: `app/dao/machine.py` only.
- No migration, no schema or API change. Method signatures stay as they are, including the paging defaults (`skip=0`, `limit=100`) of `get_by_factory` / `get_by_section`.
- `latest_event_type` keeps its type (`MachineEventTypeEnum | None`).

## 6. Out of scope (leave alone)

- **BUG-342 / BUG-343** (`app/utils/work_order_generation.py` with `get_by_section` / `get_by_factory`): the 1000-machine cap and the missing sort order of the two lookups. **Do not add an `ORDER BY` to `get_by_factory` or `get_by_section`, and do not change their paging or the callers' `limit`.** These bugs are planned separately. (A join you add for BUG-889 / BUG-891 must not change the order or paging in any other way than hiding rows.)
- Dead code the reviewer listed for removal (`get_active_by_workspace`, the `include_deleted` parameter of `get_by_factory` / `get_by_section`): leave them; their removal is a separate change.
- `app/managers/machine_manager.py`: BUG-950 … BUG-975 and BUG-1000 (duplicate-name check cap and case, include-deleted list path BUG-956 / BUG-957, maintenance window BUG-958 / BUG-973, deleted-factory checks on edit / delete / open BUG-963 … BUG-966, BUG-974, and others). In particular BUG-951 (the duplicate-name check reads only 100 machines) is the manager's.
- BUG-1090 (`app/dao/machine_activity_event.py`, the displayed latest status picks by timestamp only): after this fix the filter and the displayed status can disagree on a timestamp tie; that is known and is BUG-1090's.
- BUG-1570 (`app/api/v1/endpoints/machines.py`, misspelt maintenance filter or sort silently ignored).
- BUG-340 / BUG-341 (`app/utils/work_order_generation.py`, template default machine), BUG-3300 (`app/managers/work_order_template_manager.py`, section fallback).
- BUG-906 / BUG-907 / BUG-909 (`app/dao/machine_section_assignment.py`).
- BUG-100 / BUG-101 (`app/dao/base.py`, generic lists).
