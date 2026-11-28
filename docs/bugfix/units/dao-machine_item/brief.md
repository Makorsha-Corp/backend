# Fix brief: dao-machine_item

## 1. Unit

| | |
|---|---|
| Slug | `dao-machine_item` |
| Source file | `app/dao/machine_item.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-machine_item` |
| Branch | `bugfix/dao-machine_item` (from `origin/main`) |
| Risk | `normal` (BUG-976 / BUG-977 are a trivial-list pattern; BUG-979 / BUG-980 / BUG-981 `join-ignores-soft-deleted` and BUG-982 `silent-result-cap` are not; machine stock lists, intended behaviour already settled in the rows) |

## 2. Bugs

### BUG-976: A machine's stock rows have no sort order
- **Pattern:** `unordered-pagination`
- **Where:** `DAOMachineItem.get_by_machine`; reached through `GET /machine-items/?machine_id=…`.
- **Today:** No `ORDER BY`; paging can repeat or skip rows.
- **Intended:** HR-6: item name case-insensitive ascending, then row `id` ascending, before `skip` / `limit` (the stock page's order, BUG-701).

### BUG-977: Machine placements of an item have no sort order
- **Pattern:** `unordered-pagination`
- **Where:** `DAOMachineItem.get_by_item`; reached through the item summary page.
- **Today:** No `ORDER BY`; with the 500 cap (BUG-982) the order decides which rows are left out.
- **Intended:** HR-6: row `id` ascending (BUG-906 precedent: no name to sort by; the caller re-sorts for display).

### BUG-979: A machine's stock list still shows a deleted machine, or a machine of a deleted factory
- **Pattern:** `join-ignores-soft-deleted`
- **Where:** `DAOMachineItem.get_by_machine`; reached through `GET /machine-items/?machine_id=…`.
- **Today:** The query never looks at the machine or factory row; the stock rows are returned.
- **Intended:** Rows of a machine with `is_deleted = True`, or whose factory has `is_deleted = True`, are not returned; an inactive-but-live machine or factory hides nothing; stock rows are never changed and are listed again once the parent is live (per BUG-882, BUG-890 precedent; decided by Claude under the reviewer's delegation (2026-10-30)).
- **Example:** Machine "Press 4" holds 7 bearings and is deleted. `GET /machine-items/?machine_id=<Press 4>` still answers with the 7 bearings, although the machine is no longer on the machines page.

### BUG-980: A machine's stock list still shows items removed from the catalog
- **Pattern:** `join-ignores-soft-deleted`
- **Where:** `DAOMachineItem.get_by_machine`; reached through `GET /machine-items/?machine_id=…`.
- **Today:** The item's `is_active` is never looked at; the row is returned and takes a place in the page.
- **Intended:** A row whose item has `is_active = False` is not returned and takes no place in the page; the row is never changed (per BUG-883 precedent; decided by Claude under the reviewer's delegation (2026-10-30)).
- **Example:** Machine "Press 4" holds Bolt (5) and removed item "Old Gasket" (3). The machine's stock list shows both.

### BUG-981: Item summary still lists and counts placements on deleted machines and in deleted factories
- **Pattern:** `join-ignores-soft-deleted`
- **Where:** `DAOMachineItem.get_by_item`; reached through `ItemSummaryService._machine_placements` (the item summary page).
- **Today:** The query never looks at the machine or factory row: a deleted machine shows as `Machine #<id>`, factory `—`, `factory_id` 0 and is counted in `machine_placement_count`; a machine of a deleted factory shows normally.
- **Intended:** Rows of a machine with `is_deleted = True`, or whose factory has `is_deleted = True`, are not returned; an inactive-but-live machine or factory hides nothing; stock rows are never changed (per BUG-884 precedent; decided by Claude under the reviewer's delegation (2026-10-30)).
- **Example:** "Bearing 6204" is on Press 1 (live) and Press 4 (deleted). The page says 2 machines and shows a row "Machine #4127" with factory "—".

### BUG-982: Item summary silently stops at 500 machines
- **Pattern:** `silent-result-cap`
- **Where:** `DAOMachineItem.get_by_item`; reached through the item summary page.
- **Today:** Default `limit=500`, never overridden by the caller; further placements are left out, unordered, and `machine_placement_count` says 500.
- **Intended:** All matching rows are returned, no cap; the unused `skip` / `limit` parameters go with the fix (per BUG-342 precedent; decided by Claude under the reviewer's delegation (2026-10-30)).
- **Example:** A consumable sits on 620 machines. The summary shows 500 and "500 machines", and a low-stock machine may be among the 120 left out, with nothing to tell the user the list is cut.

## 3. Intended behaviour (spec rules, copied)

Facts for the whole file:
- Table `machine_items` (`app.models.machine_item.MachineItem`): `id` PK; `workspace_id` NOT NULL (FK `workspaces.id`, ON DELETE CASCADE); `machine_id` NOT NULL (FK `machines.id`); `item_id` NOT NULL (FK `items.id`); `qty` Integer NOT NULL (Python default `0`); `req_qty`, `defective_qty` Integer nullable. No soft-delete column, no `is_active`, no timestamps. No unique index on the machine + item pair today (that is BUG-983, not this unit).
- Relationships: `machine` (lazy) and `item` (`lazy="joined"`: every query here already reads the item through a `LEFT OUTER JOIN`). Properties `item_name` and `item_unit` read the loaded item.
- Parents: `Machine` (`app.models.machine`): soft delete = `is_deleted = True` with `is_active = False`. `Factory` (`app.models.factory`): soft delete = `is_deleted = True`, `is_active` unchanged. `Item` (`app.models.item`): no `is_deleted`; removed = `is_active = False`. A machine's `factory_id` is NOT NULL.
- Standing decisions: soft-deleted things are kept but must not show up in lists or be counted. Things of a soft-deleted parent are **hidden by the parent's state, their own rows untouched** ("hidden, not cascaded"). Raw lookups stay raw: a single-row lookup used for get-or-create or for a check must see the row whatever its parents' state.
- Physical row order and collation order are **not** an order: a missing `ORDER BY` is a bug.
- Every parameter after `db` is keyword-only in the five methods of this file. The class validates nothing, writes nothing of its own and never commits.
- The `skip >= 0`, `1 <= limit <= 1000` bounds of `GET /machine-items/` are enforced by the endpoint, not here.

### `DAOMachineItem.get_by_machine(db, *, machine_id, workspace_id, skip=0, limit=100)`
Used by `MachineItemManager.list_machine_items` ← `GET /machine-items/?machine_id=…`, with the caller's `skip` / `limit`. Returns a `list` of `MachineItem` (possibly empty), each with its item loaded.
- **R1.** Returns the rows with that `machine_id` and that `workspace_id`. Rows of another machine are never returned.
- **R2.** Workspace isolation follows the row: a call with the right machine id and another workspace returns `[]`. Only the row's own `workspace_id` is compared, not the machine's or the item's: a row with `workspace_id` = B that points at a machine of workspace A is returned for B and not for A. (So any join you add to the machine, factory or item is on the id only, with no workspace condition of its own; the parent's state still hides the row whatever workspace the parent is in.)
- **R3.** Rows are returned whatever their quantities (`qty` of `0`, negative, `req_qty` / `defective_qty` empty).
- **R4.** An unknown machine id, `machine_id=0`, or a machine with no rows returns `[]`.
- **R4a.** [BUG-979] When the machine is soft-deleted (`machines.is_deleted = True`), `[]` is returned. *(Today: its rows are returned.)*
- **R4b.** [BUG-979] When the machine is live but its factory is soft-deleted (`factories.is_deleted = True`), `[]` is returned. *(Today: its rows are returned.)*
- **R4c.** What surrounds R4a and R4b, holding today and after the fix: (1) the call changes nothing: the stock rows stay exactly as they were; (2) a machine with `is_active = False`, `is_deleted = False`, and a machine in a factory with `is_active = False`, `is_deleted = False`, hide nothing: the rows are returned; (3) once the machine and its factory are no longer deleted, the rows are returned again, unchanged, with nothing done to them.
- **R5.** [BUG-980] A row whose item is removed (`items.is_active = False`) is not returned and takes no place in the page; the machine's other rows are returned. Given Anvil (removed) and Bolt (active) on one machine, `limit=1` returns the Bolt row. *(Today: the row is returned and counts in the page.)* This holds whatever workspace the item belongs to (R2).
- **R5a.** What surrounds R5, holding today and after the fix: the call changes nothing (the row of the removed item and the item stay as they were), and once the item's `is_active` is `True` again the row is returned, unchanged.
- **R6.** [BUG-976] (HR-6) Rows are ordered by item name case-insensitive ascending, then row `id` ascending, before `skip` / `limit`: items "Zulu", "apple", "Banana" come back "apple", "Banana", "Zulu", and items named "Bolt" and "bolt" come back lower row `id` first. *(Today: no ordering is requested; the order is whatever the database produces.)*
- **R7.** At most `limit` rows are returned after skipping `skip`; with the defaults at most 100: given 101 rows on the machine, exactly 100. Consecutive windows partition the machine's rows with no repeats or gaps (relies on R6).
- **R8.** `limit=0` returns `[]`; `skip` at or past the number of matching rows returns `[]`.
- **R9.** A negative `limit` or `skip` makes Postgres reject the query: negative `limit` raises `sqlalchemy.exc.DataError` (`.orig.pgcode == "2201W"`, "LIMIT must not be negative"); negative `skip` raises `DataError` (`.orig.pgcode == "2201X"`, "OFFSET must not be negative").
- **R10.** With BUG-983 (not this unit) a machine will have at most one row per item of a workspace. *(Today: two rows are possible, and both are returned.)* Nothing to do here.
- **R11.** Each returned row carries its item's data: `item_name` and `item_unit` give the item's `name` and `unit`, also for a removed item, **with no further query** (the whole call stays one SELECT).

Side effects: none.

### `DAOMachineItem.get_by_item(db, *, item_id, workspace_id)` (intended signature)
Used by `ItemSummaryService._machine_placements` (`app/services/item_summary_service.py`) ← the item summary page, **with no paging arguments** (the call is `get_by_item(db, item_id=item_id, workspace_id=workspace_id)`). It is the only caller in `app/`. Returns a `list` of `MachineItem` (possibly empty), each with its item loaded.
- **R1.** Returns the rows with that `item_id` and that `workspace_id`, whatever their quantities. Rows of another item are never returned.
- **R2.** Workspace isolation follows the row, as `get_by_machine` R2: a call with the right item id and another workspace returns `[]`; only the row's own `workspace_id` is compared.
- **R3.** An unknown item id, `item_id=0`, or an item with no rows returns `[]`.
- **R3a.** [BUG-981] A row whose machine is soft-deleted (`machines.is_deleted = True`) is not returned. Given the item on live Press 1 and on deleted Press 4, only the Press 1 row comes back; given it only on Press 4, `[]`. *(Today: both are returned; the summary shows the second as `Machine #<id>`, factory `—`, and counts it.)* This holds whatever workspace the machine belongs to (R2).
- **R3b.** [BUG-981] A row whose machine is live but whose factory is soft-deleted (`factories.is_deleted = True`) is not returned. *(Today: it is returned; the summary shows it with its name and factory.)*
- **R3c.** What surrounds R3a and R3b, holding today and after the fix: (1) the call changes nothing: the stock rows stay exactly as they were; (2) a machine with `is_active = False`, `is_deleted = False`, and a machine in a factory with `is_active = False`, `is_deleted = False`, hide nothing; (3) once the machine and its factory are no longer deleted, the row is returned again, unchanged, with nothing done to it.
- **R4.** The item's own state is **not** looked at: for a removed item (`items.is_active = False`) the rows are returned like any other (the caller named this item; hiding a removed item's placements is the item summary service's job, BUG-1339). **Do not add the item filter of `get_by_machine` R5 here.**
- **R5.** [BUG-982] All matching rows are returned: given 501 machines holding the item, 501 rows. *(Today: at most 500 rows. The caller passes no `limit`, so the default of 500 applies; with no order, which rows are left out is arbitrary.)* The query carries no `LIMIT` and no `OFFSET`.
- **R6.** [BUG-977] (HR-6) Rows are ordered by row `id` ascending. *(Today: no ordering is requested; the order is whatever the database produces.)*
- **R7.** Each returned row carries its item's data, as `get_by_machine` R11 (`item_name`, `item_unit`, no further query; one SELECT).
- **R8.** With BUG-983 (not this unit) each machine will appear once. *(Today: two rows are possible and both are returned.)* Nothing to do here.
- **Parameters:** `skip` and `limit` are removed, together with their `.offset` / `.limit` (decided by Claude under the reviewer's delegation (2026-10-30); same as the machine DAO and inventory DAO precedents). The method keeps `db`, then keyword-only `item_id`, `workspace_id`.

Errors: none. Side effects: none.

### Methods of this file that must not change
- `get_by_workspace(db, *, workspace_id, skip=0, limit=100)`: stays as it is (raw). Every row of the workspace is returned whatever its quantities and whatever the state of its parents (rows of a soft-deleted machine, of a machine in a soft-deleted factory and of a removed item are returned and take a place in the page). Its missing order is BUG-100, not this unit.
- `get_by_id_and_workspace(db, *, id, workspace_id)`: stays raw. The state of the row's parents is not looked at.
- `get_by_machine_and_item(db, *, machine_id, item_id, workspace_id)`: stays raw. It is the "find the row" step of every machine stock movement, of reconcile, of the work-order replace check and of the duplicate check on `POST /machine-items/`; a row of a soft-deleted machine, of a machine in a soft-deleted factory, or of a removed item is returned like any other (if it were hidden, a second row would be created for the pair). No match returns `None`; no row is created.
- Inherited `BaseDAO` methods (`create`, `update`, `remove`, `get`, `get_multi`): not overridden here; leave them.

## 4. Rules that apply

- **HR-4. Soft-deleted rows are hidden unless asked for.** Lists/searches exclude soft-deleted rows by default. Filters, joins and searches through related rows ignore related rows that are soft-deleted. Scope: managers and module-specific DAO query methods (here `get_by_machine`, `get_by_item`); the generic lookups (`get_by_id_and_workspace`, `get_by_workspace`) stay raw.
- **HR-5. Filter first, then page.** All filtering (soft-delete, flags) happens in the query before `skip` / `limit`; a page is only short when there are no more results. The fixes of BUG-979, BUG-980, BUG-981 must be in the query, not in Python after it.
- **HR-6. Every paged or top-N result has a stable order.** Default: name case-insensitive ascending, then `id` ascending. No order recipe counts as deterministic unless it ends in `id`. Rows with no name of their own to sort by use `id` ascending (BUG-906 precedent). Codebase convention for case-insensitive name order: `func.lower(<Model>.name).asc()`, then `<Model>.id.asc()` (as in `app/dao/factory_section.py`, `app/dao/item_tag.py`, `app/dao/account_tag.py`).
- **HR-16. Nothing links across workspaces.** No new join may widen what is returned: the outer `machine_items.workspace_id == workspace_id` filter stays. Do not add a workspace condition on the joined machine, factory or item either: R2 says only the row's own `workspace_id` is compared, and treating other-workspace items as "not found" is BUG-1086 (another unit).
- **"Hidden, not cascaded"** (reviewer decision, applied to BUG-882 / BUG-884 / BUG-890 / BUG-891, and here): things of a soft-deleted machine or factory are hidden by the parent's state alone; their rows are never deleted or altered, so restoring the parent brings them back exactly as they were. An inactive-but-live machine or factory hides nothing (`is_active` is never used to hide a machine or factory; for an item, `is_active = False` is its "removed" state and hides it in `get_by_machine` only).
- No owner answer (OQ-n) touches these bugs.

## 5. Scope

- May change: `app/dao/machine_item.py` only (`get_by_machine` and `get_by_item`).
- `get_by_item` loses `skip` and `limit`. Its only caller, `ItemSummaryService._machine_placements` in `app/services/item_summary_service.py`, passes neither, so **the caller needs no change and is not in scope.** No other code in `app/` calls `machine_item_dao.get_by_item`.
- `get_by_machine` keeps its signature and paging defaults (`skip=0`, `limit=100`).
- No migration, no schema or API change.

## 6. Out of scope (leave alone)

- **BUG-983** (`python-only-uniqueness`): two stock rows for one machine + item; unique index, data-merge script and manager violation handling. It is a database change spanning several files and is planned later. **Do not add an index, a migration or any uniqueness logic.** BUG-978 (top-1 lookup order of `get_by_machine_and_item`) is superseded by it: leave `get_by_machine_and_item` unchanged.
- **BUG-100** (`app/dao/base.py`, generic lists unordered; its row also names this file's `get_by_workspace` override): planned separately. Leave `get_by_workspace` as it is.
- `app/managers/machine_item_manager.py`: BUG-1070 (workspace-wide list without `machine_id` shows hidden rows), BUG-1071 (its display order), BUG-1074 (`machine_id=0` lists the whole workspace), BUG-1076 / BUG-1083 / BUG-1084 / BUG-1085 (writes to stock of deleted machines or removed items), BUG-1077 (hidden row still opens by id), BUG-1086 (row with another workspace's item; its filter is also meant to reach this file, but in that unit, not this one), and the others in that file (BUG-993, BUG-1010, BUG-1072, BUG-1073, BUG-1075, BUG-1078 … BUG-1081).
- `app/services/item_summary_service.py`: BUG-1339 (removed item's summary still shows its machine placements; the check is in the service, `get_by_item` R4 stays raw), BUG-2520 (cross-workspace names), BUG-2522 (display sort of placements), and the other open bugs of that file.
- BUG-948 / BUG-968 (item / machine delete blockers counting stock rows).
