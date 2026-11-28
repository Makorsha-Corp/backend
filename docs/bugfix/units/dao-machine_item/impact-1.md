# Impact review 1: dao-machine_item (2026-11-27)

Diff: `app/dao/machine_item.py` only (`get_by_machine`, `get_by_item`; imports).
No migration, no other file. Verdict at the end: **APPROVE**.

## Query shape (compiled, Postgres dialect, `scripts/bugfix/compile_query.py`)

`get_by_machine(machine_id=1, workspace_id=1)`:

```
FROM machine_items JOIN machines ON machines.id = machine_items.machine_id
  JOIN factories ON factories.id = machines.factory_id
  JOIN items ON items.id = machine_items.item_id
  LEFT OUTER JOIN items AS items_1 ON items_1.id = machine_items.item_id
WHERE machine_items.workspace_id = 1 AND machine_items.machine_id = 1
  AND machines.is_deleted = false AND factories.is_deleted = false AND items.is_active = true
ORDER BY lower(items.name) ASC, machine_items.id ASC LIMIT 100 OFFSET 0
```

`get_by_item(item_id=1, workspace_id=1)`:

```
FROM machine_items JOIN machines ON ... JOIN factories ON ...
  LEFT OUTER JOIN items AS items_1 ON items_1.id = machine_items.item_id
WHERE machine_items.workspace_id = 1 AND machine_items.item_id = 1
  AND machines.is_deleted = false AND factories.is_deleted = false
ORDER BY machine_items.id ASC          -- no LIMIT, no OFFSET
```

- Filters are in the query, before `OFFSET` / `LIMIT` (HR-5). The ORDER BY is
  `lower(items.name)` then `machine_items.id`, both ORM columns (HR-6 convention). One
  SELECT per call: the item comes from the `lazy="joined"` eager load in the same statement.
- AND-only WHERE, no OR, so there is no precedence issue. `machines.is_deleted`,
  `factories.is_deleted`, `items.is_active` and `machines.factory_id` are all NOT NULL
  (model and `100_squashed_baseline.sql`), so the `= false` / `= true` tests have no NULL
  branch, and the inner joins drop no row with valid FKs.
- **HR-16 / R2:** the joins are on id only, with no workspace condition on machine,
  factory or item. The outer `machine_items.workspace_id` filter stays, so nothing is
  widened. Rows that link to another workspace's item or machine are BUG-1086 (another unit).

## (a) `items` twice in FROM

- **Correctness: fine.** Both joins are many-to-one on `items.id` (PK), so each
  `machine_items` row matches at most one `items` row and one `items_1` row, which are
  the same item. The filter and sort read `items`; the loaded relationship reads
  `items_1`. They can't disagree. **No row duplication.** Every join here (machine,
  factory, item, eager item) is many-to-one, so the row count equals the
  `machine_items` count. SQLAlchemy also adds no subquery wrapping for LIMIT with a
  many-to-one joined eager load, so the LIMIT applies to `machine_items` rows.
- **Performance: negligible.** It's a second PK index lookup on `items` per row, for at
  most `limit` (≤ 1000) rows.
- **Codebase pattern:** `contains_eager` is used **nowhere** in `app/`. The established
  pattern is an explicit join plus the model's own eager load:
  - `app/dao/inventory.py` `_filtered_query` / `list_filtered`: `Inventory.item` is
    `lazy="joined"`, the DAO adds `.join(Item, Inventory.item_id == Item.id)`, and it
    orders by `Item.name`, giving the same double `items` in FROM.
  - `app/dao/machine.py` `get_by_section`: an explicit
    `.join(MachineSectionAssignment, ...)` for the filter, plus
    `joinedload(Machine.section_assignment)` (`_SECTION_EAGER_LOAD`) for loading.
    `get_by_factory` also uses an explicit `join(Factory)` for the `is_deleted` filter.

  `contains_eager` would remove one join, but it would be the first use in the codebase.
  It would also tie the loaded `item` to the filtered join, which is fine here but becomes
  a trap once BUG-1086 adds a workspace condition to that join. The fixer's choice matches
  the codebase. **Not a finding.**

## (b) Callers (upstream). Stock is involved, so every path was traced.

Grep over `app/`, `scripts/` and `alembic/` for `get_by_machine(` / `.get_by_item(` and
for `machine_item_dao` / `DAOMachineItem`. The other classes that share the method names
(`machine_item_ledger_dao`, `machine_activity_event`, `machine_maintenance_log`,
`machine_section_assignment`, `production_line`, `inventory_dao`, `product_dao`) are
separate DAOs and were excluded.

| Method | Caller | Use |
|---|---|---|
| `get_by_machine` | `MachineItemManager.list_machine_items` (with `machine_id`) ← `MachineItemService.get_machine_items` ← `GET /machine-items/?machine_id=` | read-only list, returned as is |
| `get_by_item` | `ItemSummaryService._machine_placements` ← `get_summary` ← `GET /items/{id}/summary/` | display rows; `machine_placement_count = len(placements)`; re-sorted in Python (display sort, BUG-2522) |

These are the only callers. **No write path or stock arithmetic uses either method.**
Every stock movement and check finds its row with the unchanged, raw
`get_by_machine_and_item`:
- `inventory_movements.py:179` (find-or-create machine stock in movements)
- `po_machine_inventory.py:48` (PO receipt to a machine)
- `ledger_manager.py:174` (reconcile snapshot)
- `work_order_manager.py:932` (replace check)
- `machine_item_manager.py:142` (duplicate check on create)

Single-row reads, updates and deletes use `get_by_id_and_workspace`, which is unchanged.
So a hidden row is never "not found" by a movement, and no second row can be created
for a pair because of this fix. The item summary's placement data is display only: it
feeds into no total that is written anywhere. `_machine_placements` does not re-filter
or dedupe, and its stable `sort()` replaces the DAO order for display. That's fine,
because R6 of `get_by_item` is only about the cap and determinism.

Frontend consumers of `GET /machine-items/?machine_id=` (`../frontend/src`): the machine
detail panel and body, `EditMachineDialog`, `ItemSelectorDialog` (machine tab),
`AddTransferOrderDialog` (source machine stock), `EditWorkOrderItemsDialog` (REPLACE:
current qty), and `SheetMaintenanceEntryForm`. None of these writes stock from the list
alone:
- `EditMachineDialog` deletes only the original rows the user dropped from the drafts.
  A hidden row (removed item) is not among the originals, so it is never deleted. A
  re-add of the same pair is refused by the raw duplicate check.
- The transfer, selector and replace dialogs show a removed item's machine stock as
  absent (qty 0 fallback in REPLACE). That matches the settled intent (BUG-980: removed
  items don't show). Writes to a removed item's machine stock are already meant to be
  refused (BUG-1083…1085, manager unit).
- A deleted machine, or a machine of a deleted factory, isn't reachable in these screens.

**No caller breaks.**

## (c) `skip` / `limit` removed from `get_by_item`

- `app/`: the only caller passes neither.
- `scripts/`: `merge_duplicate_machine_items.py` and `repair_machine_zero_average.py`
  query `MachineItem` directly and use the ledger DAO. Neither calls `get_by_item`.
- `alembic/`: the SQL baseline and migrations don't import the DAO.
- `tests/`: no call passes paging arguments to `machine_item_dao.get_by_item`. The
  ledger DAO's `get_by_item(..., skip=, limit=)` is a different class.
  `tests/test_item_summary_empty.py` patches the method with `return_value=[]`.

The removal is safe. It is uncapped, and `get_by_item` is indexed on `item_id` /
`workspace_id`. The list grows with the number of machines holding one item, so it is
bounded by the workspace's machine count.

## Downstream

The fix uses only model columns and plain joins: no locks, no DAO calls, no commit. The
service contract is unaffected (read path).

## Neighbouring bugs

- **BUG-1086** (other-workspace item treated as not found; filter "also in
  `app/dao/machine_item.py`"): not touched. The explicit `Item` join makes the later fix a
  one-line condition. That unit must change R2 here.
- **BUG-1339** (service hides a removed item's placements): `get_by_item` correctly does
  not filter on the item (R4), so there is no clash.
- **BUG-2522** (placement display sort): service-side, unaffected. **BUG-2520** (other-
  workspace names in the summary): unaffected.
- The item summary's `Machine #<id>` / `—` fallbacks in `_machine_placements` are no
  longer reached for deleted machines. They are still reachable for other-workspace
  machines (BUG-2520).
- **BUG-1070** (workspace-wide list via the raw `get_by_workspace`): left alone, as the
  brief says. The two list paths of `GET /machine-items/` now differ (filtered with
  `machine_id`, raw without) until that bug is fixed. The difference is known and logged.
- **BUG-983 / BUG-978 / BUG-100**: untouched, as scoped.

## Shortcuts / scope

No special-casing, and nothing outside the brief changed. The comments are short and
accurate. The `== False` / `== True` comparisons follow `app/dao/machine.py`.

## Precheck risks (for the tester)

The strict SQL-text check needs `lower(` in the ORDER BY and a single SELECT. Both are
present in the compiled SQL above.

## New bugs found

None.

## Verdict

**APPROVE.** Contract: response shapes are unchanged, but values change (fewer rows, an
ordered list, an uncapped placement list, and a changed meaning for
`machine_placement_count`). See `contract.md`. A frontend change is not required.
