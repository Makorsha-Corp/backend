# Fix notes: dao-machine

## Round 1 (2026-11-27)

Only file changed: `app/dao/machine.py` (worktree `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-machine`). No migration, no change to any signature or paging default.

### Changed

- **Module level (BUG-888):** added `_ILIKE_ESCAPE = "\\"` and the helper `_escape_ilike(value: str) -> str`, which escapes `\`, then `%` and `_`. It copies the pattern in `app/dao/account_invoice.py`. Imports: removed `and_`, which is no longer used. Added `Factory` and `FactorySection`.
- **`get_by_factory` (BUG-891):** added `.join(Factory, Factory.id == Machine.factory_id)` and the filter `Factory.is_deleted == False`. I did not add an `ORDER BY` and did not touch the paging or `include_deleted` (§6).
- **`get_by_section` (BUG-889, BUG-891):** added `.join(FactorySection, FactorySection.id == MachineSectionAssignment.factory_section_id)` and `.join(Factory, Factory.id == Machine.factory_id)`, with the filters `FactorySection.is_deleted == False` and `Factory.is_deleted == False`. I did not add an `ORDER BY` and did not touch the paging.
- **`search_advanced`:**
  - BUG-890: the base query always inner-joins `Factory` and filters `Factory.is_deleted == False`.
  - BUG-889: the section-filter branch also joins `FactorySection` and filters `FactorySection.is_deleted == False`. This only happens when `factory_section_id` is given, so without a section filter a machine with a left-over assignment to a deleted section is still listed (R6a).
  - BUG-892: `search_text = search.strip() if search else ""`. The search filter is applied only when `search_text` is not empty.
  - BUG-888: the pattern is `f"%{_escape_ilike(search_text)}%"`, and all three `ilike` calls pass `escape=_ILIKE_ESCAPE`.
  - BUG-886: I replaced the max(created_at) subquery and the `.astext` accessor with one subquery. It ranks the `status_updated` rows of the workspace with `row_number() OVER (PARTITION BY machine_id ORDER BY created_at DESC, id DESC)` and reads the status with `metadata_json["status"].as_string()`, which compiles to `metadata ->> 'status'` on Postgres and works on the generic `JSON` type. The outer query joins on `machine_id` and filters `rn == 1 AND status == latest_event_type.value`.
  - BUG-887: the name sort key is now `func.lower(Machine.name)`, both in the map and as the fallback for unknown `sort_by` values. The tiebreaker is still `Machine.id.asc()` in both directions. The `created_at` sort is unchanged.

### Why

- BUG-886: `as_string()` is the JSON text accessor that works on any dialect, so the query builds. `row_number` with `created_at DESC, id DESC` picks exactly one latest row per machine. The tie goes to the greater id (R12a), and the same-status ties of R12e cannot produce duplicates. A latest row with NULL metadata or no `status` key gives a NULL status, which matches nothing, and older rows are never used instead (R12c). Rows of other event types are excluded before ranking (R12b), the subquery is limited to the workspace (R12d, HR-16), and a machine with no status change has no row to join, so it never matches.
- BUG-887: with `lower(name)`, names that differ only in case are equal keys, so `id ASC` decides their order (HR-6).
- BUG-888 / BUG-892: literal matching per HR-8, and trimming per the BUG-637 precedent. A whitespace-only search strips to `""`, so no filter is applied.
- BUG-889 / BUG-890 / BUG-891: hidden by state only (HR-4, "hidden, not cascaded"). All the new pieces are inner joins plus filters. `machines.factory_id` is NOT NULL with a foreign key, and the section join only follows an assignment row that is already joined, so the joins remove only the rows meant to be hidden. They cannot add duplicates, because there is one factory per machine and one assignment per machine. Nothing is written. Inactive factories and sections are not filtered.

### Reproduction (scratch check against `marker_test` with rowkit, rolled back; now deleted)

| Bug | Before | After |
|---|---|---|
| 886 | `latest_event_type=IDLE/RUNNING/OFF`: every call raised `AttributeError ... 'astext'` | IDLE gives Lathe (RUNNING 10:00, IDLE 11:00). RUNNING gives only "Bolt": its newer `updated` event is ignored, the "ab" machine's latest row has NULL metadata so it matches nothing, and Lathe is not returned. OFF gives "bolt" (RUNNING then OFF, both at 11:00). Combined with `factory_id` + `search="bolt"` it gives "Bolt". |
| 887 | desc: `Bolt(id+1), bolt(id)`, so the collation decided | desc: `bolt(id), Bolt(id+1)`. asc: `bolt, Bolt`, i.e. id ascending in both directions |
| 888 | `%` and `_` returned every machine; `a\b` found "ab" only | `%` finds only model number "50%"; `_` finds only model number "x_y"; `a\b` finds only `a\b` |
| 889 | `factory_section_id=<deleted section>` gave "bolt" in both `search_advanced` and `get_by_section` | `[]` in both; without a section filter "bolt" is still listed; the live section still returns "Lathe" with section name "Line1" |
| 890 | `factory_id=B` (deleted) gave "Press"; `limit=1, sort_dir="desc"` gave "Press" | `[]`; "Lathe" |
| 891 | `get_by_factory(B)` and `get_by_section(section of B)` gave "Press" | `[]` for both |
| 892 | `" bolt "` and `"\tbolt\n"` gave `[]` | both give bolt and Bolt; `"   "` gives all 5 live machines |
| R3b/R3c | n/a | After setting B back to `is_deleted=False, is_active=False`, "Press" is returned again by `search_advanced(factory_id=B)` and `get_by_factory(B)` |

Also passed: `python -c "import app.main"` and `ruff check app/dao/machine.py`. `scripts/bugfix/compile_query.py` cannot run the `latest_event_type` path, because the CLI passes a plain `str` and the code calls `.value`, which only the enum has. The endpoint always passes the enum, and the database run above went through that path.

### Assumptions

- The section join in `get_by_section` / `search_advanced` is bounded by workspace only through the outer `machines.workspace_id` filter, which HR-16 allows. I did not add `FactorySection.workspace_id` or `Factory.workspace_id` filters, because that would hide extra rows, which goes beyond the brief.
- The fallback name sort for unknown `sort_by` values is also case-insensitive, since R13 says such values "sort by name".
- `include_deleted=True` on `get_by_factory` / `get_by_section` (dead code per §6) still hides machines of a deleted factory and machines in a deleted section. The brief does not say otherwise, and no caller passes it.

### Seen, not fixed

- `get_active_by_workspace` (dead code, §6) does not hide machines of soft-deleted factories.
- `MachineActivityEventDAO.get_latest_status_map` picks by timestamp only and can return either row on a tie (BUG-1090, known). The displayed status and this filter can disagree on a tie.

### Risk

- Changes to the `get_by_factory` / `get_by_section` query: the new inner joins could, in theory, change Postgres's unspecified row order. Neither method has an `ORDER BY` (BUG-343, out of scope), so their order was never guaranteed.
- `search_advanced` now always joins `factories`. Check that the manager's `limit=10_000` path (maintenance filter or sort) still behaves the same.
