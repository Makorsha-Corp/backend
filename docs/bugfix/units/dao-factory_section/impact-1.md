# Impact review 1: dao-factory_section (2026-11-27)

Diff reviewed: `git diff origin/main -- app alembic` in the unit worktree. Two files changed,
nothing in `alembic/`.

## Changed functions

### `DAOFactorySection.get_by_factory` (app/dao/factory_section.py)
- New keyword-only `include_deleted: bool = False`.
- Default: adds `factory_sections.is_deleted = false` and a correlated
  `EXISTS (SELECT * FROM factories WHERE factories.id = factory_sections.factory_id AND factories.is_deleted = false)`.
- Always: `ORDER BY lower(factory_sections.name) ASC, factory_sections.id ASC` before OFFSET/LIMIT.

Compiled (Postgres dialect, `scripts/bugfix/compile_query.py`):
- default: `WHERE workspace_id = 1 AND factory_id = 2 AND is_deleted = false AND (EXISTS (... factories.id = factory_sections.factory_id AND factories.is_deleted = false)) ORDER BY lower(name) ASC, id ASC LIMIT 100 OFFSET 0`
- `include_deleted=True`: `WHERE workspace_id = 1 AND factory_id = 2 ORDER BY lower(name) ASC, id ASC LIMIT 100 OFFSET 0`

Checks: AND-only predicate (no precedence issue); EXISTS correlated on the outer row; reads only
`factories.is_deleted` (not the factory's workspace or `is_active`, so R1a and R3b(2) hold);
single SELECT (no second factory read); EXISTS cannot duplicate rows (R7); ORDER BY uses ORM
columns (`lower(factory_sections.name)` — "name" follows "order by" in the SQL text).

### `FactorySectionManager.search_factory_sections` (app/managers/factory_section_manager.py)
- Factory branch passes `include_deleted=include_deleted`. Nothing else changed (matches brief §5).

## Upstream
- `get_by_factory` on `factory_section_dao` has exactly two callers (grepped `factory_section_dao`,
  `DAOFactorySection`, `get_by_factory`; the other `get_by_factory` methods are on other DAOs):
  - `search_factory_sections` (factory branch) ← `FactorySectionService.get_factory_sections` ←
    `GET /factory-sections/`. Service never passes `include_deleted` (default False). The manager's
    Python post-filters (`is_deleted`, `search`) are list comprehensions that keep order, so the new
    SQL order reaches the endpoint. The Python `is_deleted` filter is now redundant in the factory
    branch, harmless.
  - `_check_name_exists_in_factory` (default args): now sees only live sections of a live factory.
    Its own `is_deleted` skip is redundant, harmless. Known side effect (brief §6): a rename inside
    a soft-deleted factory would skip the duplicate check; that path exists only via BUG-926 (open).
    Low risk, left as instructed.
- No script under `scripts/` or other app module calls it. Return type unchanged (list, possibly empty);
  no new exceptions.

## Downstream
- Only `Factory` model import added (`app.models.factory`); `import app.main` works per fixer, no
  circular import. No locks, no writes, no commit/flush. TC1–TC6 not affected (read only).

## Workspace bound (HR-16)
- The EXISTS is correlated to the section row, which is already bounded by the section's own
  `workspace_id`; the factory's workspace is deliberately not compared (spec R1a). OK.

## API contract
- Shape unchanged. Value changes visible on `GET /factory-sections/?factory_id=…` only:
  order now defined; sections of a soft-deleted factory no longer listed; deleted sections no
  longer consume page slots (a page can now be fuller). See `contract.md`. Frontend
  (`features/factorySections/factorySectionsApi.ts`, section pickers in Add/EditMachineDialog,
  FactoryDetailCard) just renders the list; no frontend change needed.

## Database
- No constraint, index or migration. No check script needed.

## Neighbouring bugs
- Partly helps BUG-917 (factory branch only: deleted sections no longer take page slots) and
  BUG-911 (the "100 deleted first" variant). Tester pre-check expects non-strict XPASS for
  FSM-S-55, FSM-S-56, FSM-CN-15; the strict cases of those bugs stay xfailed.
- BUG-920 (flag unreachable from API) unchanged; the manager option keeps working via pass-through.
- BUG-918 / BUG-924 (workspace branch) untouched, as scoped.

## Shortcuts / scope
- None. No special-cased inputs, no swallowed errors. Changes are exactly what the brief allows.

## New bugs found
- None new. (Fixer's "seen, not fixed" note on `app/dao/machine.py` unordered paging is the BUG-956
  family / HR-6 pattern already tracked in other units.)

## Verdict: APPROVE
