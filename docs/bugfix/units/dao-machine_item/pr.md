## Fix: a machine's stock list hides deleted machines and removed items and keeps a fixed order; the item summary counts every live machine, past 500

**Fixes BUG-976, BUG-977, BUG-979, BUG-980, BUG-981 and BUG-982.** One file (`app/dao/machine_item.py`), two functions. No database change, no API shape change (some lists now return fewer rows, see below).

---

### What was wrong

**1. The item summary counted placements on deleted machines and in deleted factories (BUG-981). This is the one users feel most.**

The item summary page lists every machine that holds the item and shows "N machines". It never checked whether the machine, or its factory, had been deleted.

*Example:* "Bearing 6204" sits on Press 1 (live) and Press 4 (deleted last month). The summary says **"2 machines"** and shows a row **"Machine #4127, factory —"** that nobody can open. Bearings in a machine of a factory that was closed down showed as normal placements.

**2. A machine's stock list still showed a deleted machine, or a machine of a deleted factory (BUG-979)**

Asking for the stock of a machine that was deleted, or that sits in a deleted factory, still returned its stock rows. Elsewhere in the app (the machines page, the factory's stock), those are already hidden.

*Example:* "Press 4" (deleted) still holds 7 bearings in the database. Its stock list returned those 7 bearings; it now returns nothing. Nothing is deleted: if Press 4 is restored, its 7 bearings show again, unchanged.

**3. A machine's stock list showed items removed from the catalog (BUG-980)**

An item removed from the catalog still appeared in each machine's stock list, and it used up a place on the page.

*Example:* Press 1 holds Bolt (5) and the removed "Old Gasket" (3). The list showed both. Now it shows only Bolt, and a page of 20 rows really holds 20 live items.

**4. The item summary silently stopped at 500 machines (BUG-982)**

The placement list had a hidden cap of 500 that nobody asked for. A consumable used on 620 machines showed 500 rows and said "500 machines", with no sign that 120 were missing.

**5. Neither list had a fixed order (BUG-976, BUG-977)**

A machine's stock list had no sort order, so paging through it could repeat or skip an item. It is now sorted by item name, ignoring upper and lower case, then by the order the rows were made. The item summary's placement list (re-sorted on screen anyway) now comes back in row order too, so with the cap gone it is stable.

---

### What changed

All in `app/dao/machine_item.py`:

```diff
  # a machine's stock list (get_by_machine)
+ .join(Machine, ...).join(Factory, ...).join(Item, ...)   # look at the parent rows
+ Machine.is_deleted == False,                             # deleted machine: hidden
+ Factory.is_deleted == False,                             # machine of a deleted factory: hidden
+ Item.is_active == True,                                  # removed item: hidden, takes no place on the page
+ .order_by(func.lower(Item.name).asc(), MachineItem.id.asc())   # name ignoring case, then id
  .offset(skip).limit(limit)                               # paging after the filters

  # an item's placements (get_by_item)
- skip: int = 0, limit: int = 500                          # the hidden 500 cap is gone
+ .join(Machine, ...).join(Factory, ...)
+ Machine.is_deleted == False,
+ Factory.is_deleted == False,
+ .order_by(MachineItem.id.asc())                          # fixed order
```

The house rules behind it: lists hide rows of deleted parents by the parent's state alone and never change the rows themselves (house rule HR-4), filtering happens before paging (HR-5), and every list ends its sort with id (HR-6).

### What you'll notice

- A machine's stock list is in alphabetical order by item name ("apple", "Banana", "Zulu"), and paging through it never repeats or skips an item.
- Deleted machines, machines of deleted factories and removed catalog items no longer show stock. A machine or factory that is only **inactive** (not deleted) still shows its stock, as before.
- The item summary's machine count matches the live machines that hold the item, and it is no longer capped at 500.
- **Deliberately unchanged:** the workspace-wide stock list (`GET /machine-items/` without a machine) still shows everything; that is BUG-1070 and BUG-1071, in the manager. A removed item's own summary still lists its placements; hiding them is BUG-1339, in the summary service. Stock movements (receipts, transfers, work orders) find their row the same way as before, so a hidden row is never "not found" and never duplicated.

### What to look at when reviewing

- **Hidden, not deleted.** A removed item's stock on a machine just stops showing. The edit-machine dialog only deletes rows the user dropped from what it loaded, so it can never delete a hidden row. If you'd rather see removed items greyed out than hidden, object here.
- **The two lists on `GET /machine-items/` differ for now.** With a machine id the list is filtered and sorted; without one it is still raw until BUG-1070 and BUG-1071 are fixed.
- **Other-workspace links are not touched.** A stock row linked to another workspace's item or machine is still returned; that is BUG-1086, a separate unit. The new item join makes that later fix a one-line condition.
- **Placement list is unbounded.** It grows with the number of machines in the workspace holding one item, and the query is indexed on item and workspace.

## Code review

Code review: **PASS**, 0 blockers, 0 majors, 0 minors, 2 nits (strict independent review, `review-1.md`).

- **Stock is safe:** every stock movement, reconcile and duplicate check uses `get_by_machine_and_item`, which is unchanged and still sees every row. The two changed methods only feed display lists and a count.

Nits: `get_by_machine` joins the items table twice (an explicit join plus the item relationship's built-in join), which is harmless and the same pattern as `app/dao/inventory.py:35`; the `get_by_item` signature could now fit on one line.

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:** the only callers are the machine stock list (`MachineItemManager.list_machine_items` ← `GET /machine-items/?machine_id=`) and the item summary (`ItemSummaryService._machine_placements` ← `GET /items/{id}/summary/`). No write path or stock arithmetic uses either function. No caller passed `skip` / `limit` to `get_by_item`. One SELECT per call (the item is loaded in the same statement).
- **Contract:** response shapes, status codes and messages unchanged; values change as described above (`contract.md`). No frontend PR.
- **Tests:** the 36 tests marked as known failures for these bugs (machine item DAO, machine item manager and item summary service) now pass, and their markers are removed. Every other test in the full suite had the same result before and after (flip check CLEAN, base `092776b`).
- **Commits:** `253484f` (fix, marker removals, bugs.md), on `bugfix/dao-machine_item`, pushed.

</details>
