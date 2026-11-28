# Fix notes: dao-machine_item

## Round 1 (2026-11-27)

### Changed

File: `app/dao/machine_item.py` only.

- Imports: added `func` (sqlalchemy), `Factory`, `Item`, `Machine`. Nothing else was imported, and every new import is used.
- `DAOMachineItem.get_by_machine` (BUG-976, BUG-979, BUG-980):
  - inner joins `Machine` on `Machine.id == MachineItem.machine_id`, `Factory` on `Factory.id == Machine.factory_id`, and `Item` on `Item.id == MachineItem.item_id`. They join on ids only, with no workspace condition (R2, HR-16).
  - new filters: `Machine.is_deleted == False`, `Factory.is_deleted == False` (BUG-979) and `Item.is_active == True` (BUG-980). They are applied in the query, before `offset` / `limit` (HR-5).
  - `.order_by(func.lower(Item.name).asc(), MachineItem.id.asc())` comes before `offset` / `limit` (BUG-976, HR-6 convention).
  - The signature and the `skip=0`, `limit=100` defaults are unchanged.
- `DAOMachineItem.get_by_item` (BUG-977, BUG-981, BUG-982):
  - inner joins `Machine` and `Factory` on ids, as above, with filters `Machine.is_deleted == False` and `Factory.is_deleted == False` (BUG-981). The item's state is not looked at (R4).
  - `.order_by(MachineItem.id.asc())` (BUG-977).
  - removed the `skip` / `limit` parameters and their `.offset` / `.limit`, so the result is uncapped (BUG-982). The new signature is `get_by_item(self, db, *, item_id, workspace_id)`. The only caller (`ItemSummaryService._machine_placements`) passes neither, so it needs no change.
- `get_by_workspace`, `get_by_id_and_workspace` and `get_by_machine_and_item` are untouched and stay raw.

### Why

- The rows are hidden by the parent's state alone, through joins and filters in the one SELECT. No stock row is read for change or written ("hidden, not cascaded"), so a restored machine, factory or item brings its rows back unchanged. Only `is_deleted` is used for machines and factories, so an inactive-but-live parent hides nothing. This follows `app/dao/machine.py` (`join(Factory, ...)` plus `Factory.is_deleted == False`).
- A machine's `factory_id` is NOT NULL, so the inner joins drop no live row.
- Each method is still one SELECT. Compiled SQL of `get_by_machine`:
  `FROM machine_items JOIN machines ... JOIN factories ... JOIN items ON items.id = machine_items.item_id LEFT OUTER JOIN items AS items_1 ... WHERE ... machines.is_deleted = false AND factories.is_deleted = false AND items.is_active = true ORDER BY lower(items.name) ASC, machine_items.id ASC LIMIT 100 OFFSET 0`.
  The `lazy="joined"` eager load of `item` still adds its own `LEFT OUTER JOIN items AS items_1`, so `item_name` / `item_unit` need no further query (R11). I counted the statements: one SELECT per call.

### Reproduction (throwaway rowkit check in the session scratchpad, against `bf_dao_machine_item_test`; deleted afterwards)

| Check | Before | After |
|---|---|---|
| 976: items Zulu / apple / Banana / Bolt / bolt come back apple, Banana, Bolt, bolt, Zulu | FAIL | PASS |
| get_by_machine is one SELECT, including item_name / item_unit | PASS | PASS |
| 980: apple removed, `limit=1` returns Banana | FAIL | PASS |
| 980: item active again, all 5 rows return | PASS | PASS |
| 979: inactive machine hides nothing | PASS | PASS |
| 979: deleted machine returns `[]` | FAIL | PASS |
| 979: live machine in deleted factory returns `[]` | FAIL | PASS |
| 979: inactive factory hides nothing | PASS | PASS |
| 977: get_by_item returns rows by id ascending | PASS (by chance: physical order; no ORDER BY was sent) | PASS (ORDER BY id) |
| 981: placement on deleted machine, and on machine of deleted factory, hidden | FAIL | PASS |
| 981: once restored, all return; inactive machine hides nothing | PASS | PASS |
| get_by_item R4: removed item's placements still returned | PASS | PASS |
| 982: 502 placements, all 502 returned | FAIL (500) | PASS |
| 982: `skip` / `limit` gone from the signature | FAIL | PASS |
| stock rows unchanged (qty) | PASS | PASS |

Also: `python -c "import app.main"` passes, and `ruff check app/dao/machine_item.py` reports "All checks passed!".

### Assumptions

- I joined `Item` explicitly for the filter and the sort, following `app/dao/inventory.py`. I did not use `contains_eager` on the eager-loaded alias, because that would change how `item` is loaded. The cost is that `items` appears twice in the FROM clause of `get_by_machine`. It is still one SELECT.
- I used the `== False` / `== True` comparison style of `app/dao/machine.py`.

### Seen, not fixed

- None beyond the out-of-scope bugs already listed in the brief (BUG-100 order of `get_by_workspace`; BUG-983 / BUG-978 uniqueness and top-1 order of `get_by_machine_and_item`).

### Risk

- `get_by_item` lost `skip` / `limit`. Any caller outside `app/` that passes them would now get a `TypeError`. I checked `app/`, and the only caller passes neither.
- `get_by_machine` now inner-joins `items`. A row whose `item_id` points at a missing item can't exist because of the FK, so no rows are lost.
