# Code review 1: dao-machine_item (2026-11-28)
Verdict: PASS   (blockers: 0, majors: 0, minors: 0, nits: 2)
Diff reviewed: 092776b..253484f, files: app/dao/machine_item.py (no alembic changes)

## 1. What a correct fix must do (written before reading the diff)

- **get_by_machine (BUG-976, 979, 980).** Inner-join `machines` on `machine_items.machine_id`,
  `factories` on `machines.factory_id`, and `items` on `machine_items.item_id`, on ids only (no
  workspace condition on the parents, R2). Filter `machines.is_deleted = false`,
  `factories.is_deleted = false` and `items.is_active = true` in SQL, before OFFSET/LIMIT (HR-5).
  Do not use `is_active` of the machine or factory. `ORDER BY lower(items.name) ASC, machine_items.id ASC`
  before paging (HR-6). Keep the signature and the defaults `skip=0`, `limit=100`. Keep one SELECT
  with the item loaded. Keep the outer `machine_items.workspace_id` filter. Negative skip/limit
  still go to Postgres, which rejects them.
- **get_by_item (BUG-977, 981, 982).** Same machine and factory joins and filters, with **no** item
  filter (R4). `ORDER BY machine_items.id ASC`, with no LIMIT/OFFSET. Signature becomes
  `(db, *, item_id, workspace_id)`. Its only caller passes no paging arguments.
- **Must not change:** `get_by_workspace`, `get_by_id_and_workspace`, `get_by_machine_and_item`
  (the stock-movement "find the row" step must stay raw), and the inherited BaseDAO methods. No
  writes, no commits, no migration, no uniqueness logic (BUG-983).
- **Callers to check for stock arithmetic:** a hidden row must never be reached by a code path that
  computes or changes stock. Only list/summary paths may use the two changed methods.

## 2. Findings

No blockers, majors or minors.

Evidence gathered (throwaway script against `bf_dao_machine_item_test`, rolled back;
`C:\Users\User\AppData\Local\Temp\claude\5703096e36d5cd6b\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\review-dao-machine_item\check.py`):

- Order: items "Zulu", "apple", "Banana", "Bolt", "bolt" come back `apple, Banana, Bolt, bolt, Zulu`
  ("Bolt" has the lower id). Windows of size 2 over skip 0/2/4 put together give the full list,
  with no repeats and no gaps.
- Removed item "Anvil" is excluded and takes no place in the page: `limit=1` returns `apple`, not Anvil.
- Inactive-but-live machine, then inactive-but-live factory: all 5 rows are still returned.
  Deleted machine: `[]` from both methods. Deleted factory: `[]` from both. After restoring,
  all 5 rows come back unchanged.
- `get_by_item` for the removed item still returns its row (R4 holds). Results are in id order,
  with no cap.
- R2: a row with workspace B that points at workspace A's machine is returned for B and not
  for A.
- Each method sends exactly one SELECT (checked with a cursor listener), and `item_name` triggers
  no further query. Compiled SQL:
  `... FROM machine_items JOIN machines ON machines.id = machine_items.machine_id JOIN factories ON factories.id = machines.factory_id JOIN items ON items.id = machine_items.item_id LEFT OUTER JOIN items AS items_1 ... WHERE ... AND machines.is_deleted = false AND factories.is_deleted = false AND items.is_active = true ORDER BY lower(items.name) ASC, machine_items.id ASC LIMIT/OFFSET`.
- A negative limit still raises `DataError` with pgcode 2201W. `get_by_item(..., limit=5)` now raises
  `TypeError`. There are no such callers in `app/`.
- Callers: `get_by_machine` is used only by `MachineItemManager.list_machine_items`
  (app/managers/machine_item_manager.py:53), a list endpoint. `get_by_item` is used only by
  `ItemSummaryService._machine_placements` (app/services/item_summary_service.py:307), which
  passes no paging arguments. It does display and `len()` only and sums no stock. All stock
  movements, reconcile and the duplicate check go through `get_by_machine_and_item`, which is
  unchanged and raw. No stock arithmetic can lose a hidden row.
- Joined columns are not null (`machines.is_deleted`, `factories.is_deleted`, `items.is_active`
  are `nullable=False`, `machines.factory_id` is NOT NULL), so `== False/True` cannot drop rows on
  NULL. The inner joins cannot duplicate or drop rows, because every FK is NOT NULL and points
  at a PK. `machine_items.machine_id` and `item_id` are indexed.
- `ruff check app/dao/machine_item.py`: all checks passed.

### Nits
- N1. `get_by_machine` joins `items` twice: once by the explicit `.join(Item)` and once by the
  `lazy="joined"` eager alias `items_1`. `contains_eager(MachineItem.item)` would reuse the
  explicit join. Harmless, and the code base does the same thing in `app/dao/inventory.py:35`
  (also `lazy="joined"`), so it is consistent as it stands.
- N2. The `get_by_item` signature still wraps onto two lines now that it is short enough for one.
  Style only.

## 3. Questions (unproven)

None.

## 4. What is good

- The filters are in SQL before paging, on id-only joins, exactly as HR-5 and R2 require. The
  machine and factory `is_active` flags are rightly left alone.
- `get_by_item` leaves the item's state alone, which avoids the tempting copy-paste of the item
  filter and respects the BUG-1339 split.
- The change is minimal. It follows the house idiom (`func.lower(...).asc()`, then `id.asc()`,
  with `== False` filters as in app/dao/factory_section.py:49-52), and the comments explain why.
