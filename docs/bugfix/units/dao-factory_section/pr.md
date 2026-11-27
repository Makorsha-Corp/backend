## Fix: a factory's section list hides deleted sections and deleted factories, and keeps a fixed A-to-Z order

**Fixes BUG-903, BUG-904 and BUG-905.** Two files (one real change, plus a one-line pass-through). No database change, no API shape change.

---

### What was wrong

All three are in the list of sections for one factory (`GET /factory-sections/?factory_id=…`). That list feeds the section pickers when adding or editing a machine, and the factory detail card.

**1. Deleted sections still showed up and took places in the page (BUG-905). This is the one users feel most.**

When a section was deleted, it stayed in the database marked *deleted*, but the factory's section list never looked at that mark. The manager then removed deleted rows *after* the page had been cut, so they still used up places.

*Example:* factory "Dhaka Plant" had 100 old sections deleted during a reorganisation, then one new section "Packing" was created. Opening the section picker showed **nothing**: the first 100 rows were all deleted ones, they were thrown away afterwards, and "Packing" never made it onto the page.

**2. Sections of a deleted factory were still listed (BUG-904)**

Deleting a factory hides it, but its sections were still listed when asked for by that factory's id.

*Example:* factory 9 "Old Plant" is deleted while it still has "Cutting" and "Paint". Asking for factory 9's sections returned both. Now it returns nothing, and restoring factory 9 brings both back untouched (the section rows themselves are never changed). A factory that is only *inactive*, not deleted, still shows its sections.

**3. The list had no order (BUG-903)**

The database could return sections in any order, so the list could reshuffle between loads, and paging could repeat or skip a section.

*Example:* "Zulu", "bolt", "apple", "Bolt", "Banana" now always come back as apple, Banana, bolt, Bolt, Zulu. Names that differ only in capitals keep the order they were created in.

---

### What changed

`app/dao/factory_section.py`, the factory's section list:

```diff
+ include_deleted: bool = False                       # new option, off by default
  ...
+ if not include_deleted:
+     FactorySection.is_deleted == False,             # deleted sections are hidden (house rule HR-4)
+     exists().where(Factory.id == FactorySection.factory_id,
+                    Factory.is_deleted == False),    # sections of a deleted factory are hidden
+ .order_by(func.lower(FactorySection.name).asc(),
+           FactorySection.id.asc())                  # A-to-Z ignoring capitals, then by id (HR-6: every list ends its sort with id)
```

`app/managers/factory_section_manager.py`, one line:

```diff
  self.factory_section_dao.get_by_factory(..., skip=skip, limit=limit,
+     include_deleted=include_deleted)                # the manager's "show deleted too" option keeps working
```

All filters run in the same single database query, before paging, so a hidden section never takes a place in the page. Only the factory's *deleted* flag is read; its workspace and *active* flag are not.

### What you'll notice

- Section pickers and the factory card no longer show or "lose space to" deleted sections. A page can now be fuller than before.
- Sections of a deleted factory disappear from that factory's list, and come back when the factory is restored.
- The section list is always A-to-Z, ignoring capitals.
- Unchanged: the workspace-wide section list (no factory chosen) still has its own open bugs (BUG-917, BUG-918, BUG-924) and is not touched here. Opening a single section by id is unchanged (BUG-925 is separate).

### What to look at when reviewing

- **Why the manager changed too.** The manager has a "show deleted sections too" option. In the factory branch it relied on the old list returning everything. Without the new `include_deleted` pass-through, fixing the list would have silently broken that option. The option is still not reachable from the endpoint; that is BUG-920, a separate fix.
- **One side effect accepted.** The duplicate-name check for sections uses this same list, so it no longer sees sections of a *deleted* factory. Today nothing can create or rename a section inside a deleted factory except through another open bug (BUG-926), so the risk is low. Object if you want the name check to keep scanning deleted factories.
- **Partial help for neighbouring bugs.** BUG-911 (duplicate-name check only scans 100 sections) and BUG-917 (filters applied after paging) are partly eased in the factory branch, because deleted rows no longer fill the page. Both stay open for their full fix.

Not a trivial unit (two files, and the soft-delete patterns aren't on the trivial list), so this is **not** marked "Good to auto-merge".

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:** `get_by_factory` has two callers, both in the factory-section manager: the section list (→ service → `GET /factory-sections/`, which never sends `include_deleted`) and the duplicate-name check (defaults). No scripts or other modules call it. The manager's later Python filters keep order, so the new sort reaches the endpoint. No new exceptions, no writes, no migration.
- **Contract:** same response shape, status codes and messages. Value-only changes on `GET /factory-sections/?factory_id=…` (order defined; deleted sections and sections of deleted factories hidden). The frontend just renders the list, so there is no frontend PR.
- **Tests:** the 16 tests marked as known failures for these bugs (factory-section DAO, manager and service) now pass and their markers are removed; every other test in the full suite had the same result before and after (flip check CLEAN, base `f27d6ca`). Only order-dependent "may pass by accident" tests moved, as expected, including two neighbouring BUG-917 cases and one BUG-911 case that the deleted-section fix partly helps.
- **Branch:** `bugfix/dao-factory_section`. **Commit:** `cab794a` (fix, markers, bugs.md).

</details>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
