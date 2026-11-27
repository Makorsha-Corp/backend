# Fix notes: dao-factory_section

## Round 1 (2026-11-27)

### Changed
- `app/dao/factory_section.py`
  - Imports: added `from sqlalchemy import exists, func` and `from app.models.factory import Factory`.
  - `DAOFactorySection.get_by_factory`: new keyword-only `include_deleted: bool = False` (placed after `limit`; all parameters stay keyword-only). Docstring gained the new argument.
    - **BUG-905:** with `include_deleted=False`, adds `FactorySection.is_deleted == False` to the query filter (before offset/limit).
    - **BUG-904:** with `include_deleted=False`, adds a correlated `EXISTS (SELECT * FROM factories WHERE factories.id = factory_sections.factory_id AND factories.is_deleted = false)`.
    - **BUG-903:** always `ORDER BY lower(factory_sections.name) ASC, factory_sections.id ASC` before `OFFSET` / `LIMIT`.
- `app/managers/factory_section_manager.py`
  - `FactorySectionManager.search_factory_sections`: the factory branch now passes `include_deleted=include_deleted` to `get_by_factory`. Nothing else changed. `_check_name_exists_in_factory` is untouched and still uses the default.

### Why
- All filters run in SQL before paging (HR-5), so deleted sections and sections of a deleted factory never take a place in the page (R2, R3a, R4).
- The EXISTS reads only `factories.is_deleted`. It never compares the factory's `workspace_id` or `is_active`, so R1a (the section's own workspace decides) and R3b(2) (an inactive factory hides nothing) still hold. Nothing is written, so R3b(1)/(3) hold: sections come back unchanged once the factory is restored. It is one query, with no second read of the factory row.
- I used EXISTS rather than a JOIN so the query can never return a section more than once (R7). With `include_deleted=True` both deleted filters are skipped, but the workspace/factory filters, the order and the paging stay (R8). That keeps the manager's `include_deleted=True` option working in the factory branch (manager R6/R7).
- Compiled SQL (default call):
  `... WHERE workspace_id = :w AND factory_id = :f AND is_deleted = false AND (EXISTS (SELECT * FROM factories WHERE factories.id = factory_sections.factory_id AND factories.is_deleted = false)) ORDER BY lower(name) ASC, id ASC LIMIT 100 OFFSET 0`.

### Checks run (throwaway, deleted)
I ran these against the database with rowkit:
- Order: "Zulu", "bolt", "apple", "Bolt", "Banana" came back as apple, Banana, bolt, Bolt, Zulu.
- Paging: windows of 2 split the list with no repeats or gaps.
- Deleted and inactive sections: a deleted section was hidden by default and returned (ordered with the live ones) with `include_deleted=True`. An inactive section was returned.
- Inactive factory: hid nothing.
- Deleted factory: the default call gave `[]`, and `include_deleted=True` gave all sections, through both the DAO and the manager. The section row was untouched (`is_deleted=False`, `deleted_at=None`). Restoring the factory brought the sections back.
- Another workspace id gave `[]`.
- `import app.main` works. `ruff check` passes on both files.

### Assumptions
- `include_deleted` comes after `limit` in the signature. It is keyword-only, so callers are not affected by where it sits.
- `lower()` is used for case-insensitive order, matching the HR-6 wording (the same as `func.lower` used elsewhere in the DAOs).

### Seen, not fixed
- `app/dao/machine.py` `get_by_factory` / `get_by_section` / `get_active_by_workspace` page with no `ORDER BY` (HR-6). Other units may already track this.
- `FactorySectionManager.search_factory_sections` still filters deleted sections and search text in Python after the page is cut in the workspace branch. This is BUG-917 / BUG-918 / BUG-924, not this unit. In the factory branch its Python `is_deleted` filter is now redundant but harmless; I left it as the brief requires.

### Risk
- The known side effect from the brief: `_check_name_exists_in_factory` no longer sees sections of a soft-deleted factory (the BUG-926 path). It was left as instructed.
- No migration and no schema change.
