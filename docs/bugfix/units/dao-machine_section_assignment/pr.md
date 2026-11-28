## Fix: editing a machine no longer rewrites who put it in its section, and a section's machine links keep a fixed order

**Fixes BUG-909 and BUG-906.** One file (`app/dao/machine_section_assignment.py`), two small changes plus a docstring correction. No database change, no API change.

---

### What was wrong

**1. Saving a machine without changing its section re-created the section link (BUG-909). This is the one that matters.**

Each machine can sit in one factory section, recorded as a "link" row that says who placed it there and when. The machine edit form always sends the machine's section back, even when the user only changed something else. When the section was the same, the old link was deleted and a new one written in its place: a new row id, "created by" the person who just saved, "created at" now.

*Example:* Rahim put "Press 4" into the "Cutting" section in January. In March Karim fixes a typo in the machine's note and saves. The form re-sends "Cutting". Before this fix, the link read "created by Karim, March", and Rahim's original placement was lost. Now the link still reads "created by Rahim, January", with the same row id, and nothing is written for it.

**2. The links of a section had no sort order (BUG-906)**

When a section is deleted, its machines are unassigned by reading the section's links in pages. The read had no `ORDER BY`, so the database could return the rows in any order, and pages could repeat or skip a row. It also made it random which rows would be left over by the existing 10 000-row cap (that cap is a separate bug, BUG-907, not changed here).

---

### What changed

All in `app/dao/machine_section_assignment.py`:

```diff
  # get_by_section: the links of one section
+   .order_by(MachineSectionAssignment.id.asc())      # fixed order, before skip / limit

  # upsert_for_machine: set a machine's section
    existing = self.get_by_machine(...)
+   if existing and existing.factory_section_id == factory_section_id:
+       return existing                                # same section: keep the row, write nothing
```

- The order follows house rule HR-6 (every list has a stable order; these rows have no name, so it is by row id).
- The "same value, write nothing" rule is house rule HR-9, following the precedent already set for account tags (BUG-870).
- The `clear_for_section` docstring claimed that deleting row by row refreshes machines already loaded in the session. It doesn't, and the callers expire those machines themselves; the comment now says so. No behaviour change.

### What you'll notice

- Editing a machine keeps its original section placement record (who and when) as long as the section stays the same.
- Moving a machine to a **different** section still replaces the link with a new one stamped with the person who moved it, as before. Clearing the section still removes the link.
- Deleting a section unassigns its machines in a fixed order. Nothing visible in the API changes: no response shows the link row's id or audit fields.

### What to look at when reviewing

- **The early return doesn't flush.** Nothing is pending from this method at that point, and the callers (`set_assignment`, used by machine create and update) ignore the returned object, then expire the machine and commit in the service. If you'd rather the DAO always flush, say so.
- **Moving a machine is still "delete and insert", not an in-place update.** That is the intended behaviour in the spec (a move is a new placement, made by the person who moved it). Object if you want moves to keep the original row.
- **Left for other PRs:** the 10 000-row cap when a section is deleted (BUG-907), and editing a machine whose section was deleted (BUG-971: the manager refuses before this code runs). Once BUG-971 is fixed, this change already makes that re-save a no-op here.

## Code review

Code review: **PASS**, 0 blockers, 0 majors, 1 minor, 2 nits (strict independent review, `review-1.md`).

Minor, for you to decide:
- **R1-1:** the docstring of `upsert_for_machine` still says it always replaces the assignment. On a re-save of the same section it now keeps the row; only the inline comment says so. Only the comment is out of date; the code is correct.

Nits: `if existing and ...` instead of `is not None` (matches the rest of the file); an out-of-scope comment in `app/managers/machine_manager.py:176-178` still says the row is "deleted/replaced".

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:** callers checked up to `POST /machines/`, `PUT /machines/{id}/` and `DELETE /factory-sections/{id}/`. `upsert_for_machine` is called only by `MachineSectionAssignmentManager.set_assignment` (machine create / update); `get_by_section` only by `clear_for_section` (section delete). Nothing relied on the old order or on the link being re-created. A manual check of a same-section machine update confirmed only the `machines` UPDATE is written: no delete, insert or activity entry for the link.
- **Contract:** no change (request, status codes, messages and response fields unchanged). No frontend PR.
- **Tests:** the 8 tests marked as known failures for these bugs (assignment DAO, assignment manager, machine manager) now pass, and their markers are removed. Every other test in the full suite had the same result before and after (flip check CLEAN, base `092776b`; 30 order-dependent tests that are allowed to vary between runs were ignored). The tests for BUG-907 and BUG-971 still fail as expected.
- **Commits:** `881a95c` (fix and test marker removals, branch `bugfix/dao-machine_section_assignment`, pushed).

</details>
