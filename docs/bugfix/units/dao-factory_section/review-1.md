# Code review 1: dao-factory_section (2026-11-27)
Verdict: PASS   (blockers: 0, majors: 0, minors: 2, nits: 2)
Diff reviewed: f27d6ca..cab794a, files: app/dao/factory_section.py, app/managers/factory_section_manager.py

## 1. What a correct fix must do (written before reading the diff)

- `get_by_factory` gets a keyword-only `include_deleted: bool = False`.
- Default: in SQL, before OFFSET/LIMIT, keep only sections with
  `workspace_id` = arg (the section's own column), `factory_id` = arg,
  `factory_sections.is_deleted = false`, and whose factory row has
  `is_deleted = false`. That factory check is done in the same query (JOIN on
  the PK or a correlated EXISTS). It never reads `factories.workspace_id` or
  `factories.is_active`. A join on `factories.id` (PK) can't duplicate rows.
- `include_deleted=True`: both deleted filters dropped. Workspace/factory
  filters, ordering and paging stay.
- ORDER BY `lower(name) ASC, id ASC`, always (both modes), before paging.
- Must not change: `soft_delete`, `restore`, inherited raw methods, section
  `is_active` not consulted, nothing written, negative skip/limit still reach
  Postgres (DataError 2201W / 2201X).
- Manager: only the factory branch of `search_factory_sections` passes
  `include_deleted=include_deleted`. `_check_name_exists_in_factory` keeps the
  default. Nothing else changes.
- Edge cases: empty factory, unknown ids, `limit=0`, `skip` past the end,
  ties on case-folded names (`bolt` and `Bolt` broken by id), inactive factory,
  deleted factory then restored, the R1a cross-workspace row.

## 2. Findings

### R1-1 [minor] Bug ids in code comments
- Where: app/dao/factory_section.py:47-48, 55 (`get_by_factory`)
- Problem: the comments `# BUG-905: ...`, `# BUG-904: ...` and `# BUG-903: ...`
  point to tracker ids. Nothing else in `app/` does this
  (`git grep "BUG-[0-9]" origin/main -- app` finds nothing). The ids mean
  nothing to a reader without the tracker, and the history already holds them
  in the commit message. The words after each id are worth keeping.
- Evidence: no BUG-id comments in `app/` on origin/main. This change adds the
  first 3.
- Suggested direction: keep the "why" (hide soft-deleted sections; hide
  sections of a soft-deleted factory, reading only its `is_deleted`; stable
  order before paging per HR-6) and drop the bug ids.

### R1-2 [minor] Docstring "Returns" doesn't describe the new contract
- Where: app/dao/factory_section.py:37-38
- Problem: it still says "List of factory sections belonging to the
  workspace". It doesn't say that by default the list holds only live
  sections of a live factory, or that it is ordered by name case-insensitive,
  then id. Callers such as the duplicate-name check depend on the first
  point.
- Evidence: the docstring text compared with the brief's R2/R3a/R6.
- Suggested direction: one line saying the list is live-only by default and
  ordered by lower(name), id.

### Nits
- N1. The signature wraps onto a continuation line with `include_deleted` on
  its own line. The sibling `DAOMachine.get_by_factory`
  (app/dao/machine.py:26-28) puts each group on its own line in the same
  style, so the change is consistent enough. Only the parameter order differs
  (machine puts `include_deleted` before `skip`). Both are keyword-only, so
  this is harmless.
- N2. Manager app/managers/factory_section_manager.py:244: the Python
  `if not include_deleted` filter after the call now does nothing in the
  factory branch. It is correctly left alone (it still serves the workspace
  branch, and changing it is BUG-917, out of scope).

## 3. Questions (unproven)

- `factory_sections.factory_id` has no index (app/models/factory_section.py;
  only `id` and `workspace_id` are indexed). The filter on it is not new and
  the EXISTS probes `factories.id` (PK), so this change adds no cost. A
  factory_id index may still be worth it once section counts grow. Not for
  this unit.

## 4. What is good

- Compiled SQL (scripts/bugfix/compile_query.py), default mode:
  `WHERE workspace_id = 1 AND factory_id = 9 AND is_deleted = false AND
  EXISTS (SELECT * FROM factories WHERE factories.id = factory_sections.factory_id
  AND factories.is_deleted = false) ORDER BY lower(name) ASC, id ASC LIMIT .. OFFSET ..`.
  The EXISTS is correctly correlated, it can't duplicate rows, it is one
  query, and it reads only `factories.is_deleted`. With `include_deleted=True`
  both filters are gone and the order stays.
- Checked against marker_test with a rowkit script, rolled back:
  - order: apple, Banana, bolt, Bolt, inactive, Zulu (ties broken by id);
  - windows of 2 partition the list with no repeats or gaps;
  - `skip` past the end and `limit=0` give `[]`;
  - deleted sections are hidden by default and appear, ordered together, with
    `include_deleted=True`;
  - an inactive factory hides nothing; a deleted factory hides everything
    (shown with `include_deleted=True`); the section rows stay unchanged;
    restoring the factory brings them back;
  - R1a: the W1 section on a W2 factory is listed for W1 only, and hidden
    while that factory is deleted;
  - negative limit/skip raise DataError 2201W/2201X;
  - the manager with `include_deleted=True` on the factory branch still
    returns deleted sections and sections of a deleted factory.
- Uses the codebase's `== False` filter style (app/dao/machine.py:36). The
  manager change is exactly the allowed pass-through. ruff check is clean on
  both files.
