## Fix: the machines page status filter works, search finds what you typed, and machines of a deleted factory or section stop showing up

**Fixes BUG-886, BUG-887, BUG-888, BUG-889, BUG-890, BUG-891 and BUG-892.** One file (`app/dao/machine.py`). No database change, no API shape change, no frontend change.

---

### What was wrong

**1. Filtering the machines page by status always crashed (BUG-886). This one matters most.**

The machines page has a filter "latest status: Running / Idle / Off / Maintenance". Every time it was used, the server answered with an error (500) and the page showed nothing. The code read the status out of the activity log in a way the database column doesn't support.

*Example:* Rahim's workshop has 12 machines, 5 of them running. He picks **Running** in the filter and gets an error instead of the 5 machines.

**2. Machines of a deleted factory still appeared (BUG-890, BUG-891)**

When a factory is deleted, it's hidden (soft-deleted) so it can be put back later. Its machines are left untouched, but they were still listed on the machines page, and the scheduler still made work-order drafts for them.

*Example:* "Gazipur Plant 2" is deleted. Its machine "Press 4" still shows on the machines page, and next Monday's preventive-maintenance order for "Press 4" is still drafted.

**3. Filtering by a deleted section still returned its machines (BUG-889)**

The same problem one level down: a machine still assigned to a deleted section was returned when filtering by that section.

*Example:* the section "Paint Line" is deleted while "Sprayer 2" is still in it. Filtering by "Paint Line" still lists "Sprayer 2", and drafts are generated for it.

**4. Search treated `%` and `_` as wildcards (BUG-888)**

The search box passed the text straight into a pattern match, where `%` means "anything" and `_` means "any one character".

*Example:* searching `%` listed every machine instead of only the one with model number "50%". Searching `M_1` matched "MX1" too. A backslash also behaved oddly.

**5. Search didn't ignore extra spaces (BUG-892)**

*Example:* typing `Press 4 ` (with a trailing space, common after copy-paste) found nothing. A search of only spaces showed only machines whose names happen to contain those spaces, instead of everything.

**6. Name sort depended on the database's language settings (BUG-887)**

Two machines called "Bolt" and "bolt" could come back in either order depending on how the database server was set up, so pages could shift between servers.

---

### What changed

All in `app/dao/machine.py`:

```diff
  # status filter: one "latest" status change per machine, newest first, ties by id
- func.max(MachineActivityEvent.created_at) ... metadata_json["status"].astext   # crashed
+ row_number() over (partition by machine_id order by created_at desc, id desc)
+ metadata_json["status"].as_string() == <status>, rn == 1

  # machine list, factory lookup, section lookup: hide machines of a deleted factory
+ .join(Factory, Factory.id == Machine.factory_id)
+ Factory.is_deleted == False

  # section lookup and section filter: a deleted section matches nothing
+ .join(FactorySection, FactorySection.id == MachineSectionAssignment.factory_section_id)
+ FactorySection.is_deleted == False

  # search: trim, then make % _ \ match literally
- if search: search_like = f"%{search}%"
+ search_text = search.strip() if search else ""
+ search_like = f"%{_escape_ilike(search_text)}%"   # ilike(..., escape="\\")

  # name sort: case-insensitive, then id
- "name": Machine.name
+ "name": func.lower(Machine.name)
```

The rules behind it: deleted factories and sections hide their children by their own state, the machine rows are never changed, so undoing the delete brings everything back (the same rule already merged for factory sections, BUG-882 precedent). House rule HR-6: lists sort case-insensitively by name, then by id. House rule HR-8: `%`, `_` and `\` in a search match literally. Search text is trimmed, as everywhere else (BUG-637 precedent).

### What you'll notice

- The status filter works. A machine is matched by its **most recent** status change; if two changes have the same time, the later-recorded one wins. A machine that never had a status change matches no status.
- Fewer machines than before on the machines page if any factory was deleted: those machines are gone until the factory is restored. An **inactive** (not deleted) factory still shows its machines.
- No work-order drafts for machines of a deleted factory or section.
- Search ignores leading and trailing spaces; `%`, `_` and `\` find only themselves.
- "apple", "Banana", "Zulu" sort in that order, the same on every server.
- Unchanged on purpose: the order and the 1000-machine cap of the factory and section lookups used by work-order generation (that is BUG-342 / BUG-343, a later PR).

### What to look at when reviewing

- **Duplicate-name check in a deleted factory.** The duplicate-name check uses the factory lookup, so inside a soft-deleted factory it no longer sees the existing machines. You can only get there by creating or editing a machine in a deleted factory, which is itself an open bug (BUG-963 / BUG-964, manager). We accepted this interim effect; object if you want it held until those are fixed.
- **Status filter vs status shown on a tie.** On a same-time tie the filter picks the later-recorded change, while the status shown on the machine card still picks by time only (BUG-1090, open). They can disagree on a tie until BUG-1090 is fixed.
- **Speed of the status filter.** It ranks every status change in the workspace. That is no slower than the old (broken) query, and it only runs when the filter is used. A database index for it is a follow-up, since it needs a migration.
- **The search-escaping helper is now in three DAOs** (invoices, help tickets, machines). Moving it into one shared helper is a separate tidy-up (follow-up F8), kept out of this one-file fix.

---

<details>
<summary>Pipeline checks (for the record)</summary>

- **Impact review:** callers checked: the machines page (`GET /machines/`, through the machine manager and service, including its maintenance-date sort path), the machine duplicate-name check, and work-order draft generation (`resolve_template_machine_ids`). Other machine users (stock, maintenance log, activity, attachments, orders) only read single machines by id, which is unchanged. Joins checked against the database: no machine returned twice, other-workspace activity ignored, workspace filter on both sides.
- **Contract:** no change in fields, status codes or messages. The status filter now returns 200 instead of 500; list contents change as described above. The frontend already sends these filters as they are, so there is no frontend PR.
- **Tests:** the 60 tests marked as known failures for these bugs (machine DAO, machine manager and machine service) now pass, and their markers are removed. Every other test in the full suite had the same result before and after, apart from known order-tie tests that may go either way (flip check CLEAN, base `614bbce`).
- **Migrations:** none.
- **Commits:** `83f4adf` (fix, markers, bugs.md).

</details>

## Code review

**PASS**: 0 blockers, 0 majors, 0 minors, 3 nits. This was an independent strict review; the reviewer didn't see the test results. Details are in `docs/bugfix/units/dao-machine/review-1.md`.

Nits (style only, nothing to act on):
- This file hides machines of deleted factories with a join; `app/dao/factory_section.py` uses `exists()` for the same rule. Both are correct.
- The search-escape helper is another copy of the one in `app/dao/account_invoice.py`. A shared helper is planned as a later cleanup.
- The case-insensitive name sort expression is built twice instead of being reused.

Open, not blocking: the status filter scans every status change in the workspace, the same amount of data as before. A database index for it is planned as a separate follow-up, since it needs a migration.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
