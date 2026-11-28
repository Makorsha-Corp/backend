# API contract: dao-machine_item (round 1, 2026-11-27)

**No contract change.** There's no frontend work, so the frontend stage is skipped.

Request inputs, status codes, error messages and response fields are unchanged.
`GET /machine-items/` keeps its `skip` / `limit` / `machine_id` query parameters. Only
the internal `get_by_item` DAO method lost `skip` / `limit`, and no endpoint sends them.

Value changes a client can see. None of them needs frontend work: the screens render the
rows they get, and no screen writes stock based on a row being absent.

- **`GET /machine-items/?machine_id=…`**
  - The list is ordered by item name case-insensitive, then row id. Example: items "Zulu",
    "apple", "Banana" come back apple, Banana, Zulu.
  - A soft-deleted machine, or a machine of a soft-deleted factory, returns `[]`. The rows
    come back unchanged when the machine or factory is restored. An inactive but not
    deleted machine or factory still lists its stock. Example: "Press 4" (deleted) holds 7
    bearings, and the list is `[]`.
  - A row whose item is removed from the catalog (`is_active = false`) is not listed and
    takes no place in the page. Example: Press 4 holds Bolt (5) and removed "Old Gasket"
    (3), and the list shows only Bolt.

  Screens that read this list: machine detail, edit machine, the item selector's machine
  tab, the transfer order source stock, work order REPLACE current qty, and the
  maintenance sheet. They now just don't show the removed item. `EditMachineDialog` deletes
  only the rows the user dropped from what it loaded, so a hidden row is never deleted.
- **`GET /items/{id}/summary/`**
  - `machine_placements` leaves out placements on soft-deleted machines and on machines of
    soft-deleted factories. `machine_placement_count` counts only the rest. Example:
    "Bearing 6204" on Press 1 (live) and Press 4 (deleted) now shows 1 machine, with no
    "Machine #4127 / —" row.
  - The list is no longer capped at 500. Example: a consumable on 620 machines shows 620
    rows and "620 machines".
  - A removed item's placements are still listed. Hiding them is BUG-1339, in the service.
