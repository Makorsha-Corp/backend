# Impact review: dao-machine, round 1 (2026-11-27)

Diff: `git -C E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-machine diff origin/main -- app alembic`. Only `app/dao/machine.py` changed, no migration. Signatures, paging defaults and `include_deleted` are unchanged.

**Verdict: APPROVE.** No blocking finding. Contract: no change (see `contract.md`).

## Checked against the database (scratch, `marker_test`, rolled back)

Script: `C:\Users\User\AppData\Local\Temp\claude\5703096e36d5cd6b\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\se_machine\check.py`, run from the worktree with `PYTHONPATH=.`.

| Case | Result |
|---|---|
| Machine A: two `status_updated` RUNNING rows with the same `created_at` | `RUNNING` returns A once (no duplicate) |
| Machine B: RUNNING then IDLE, same `created_at` | `IDLE` returns B and `RUNNING` does not (greater id wins) |
| A newer RUNNING row for B in **another** workspace (invalid data, HR-16) | ignored: B still IDLE only |
| Section filter + `search="  a "` + `RUNNING` together | A (trim, section join, latest-status join all combine) |
| Machine C in a soft-deleted factory | absent from `search_advanced` (with `limit=10_000` too) and `get_by_factory(<deleted factory>)` returns `[]` |
| `get_by_section` (live section, live factory) | A, with its section name loaded |

## Query shape (compiled, Postgres)

- Latest status: one uncorrelated derived table, `row_number() OVER (PARTITION BY machine_id ORDER BY created_at DESC, id DESC)` over `machine_activity_events WHERE workspace_id = :ws AND event_type = 'status_updated'`, status read as `CAST(metadata ->> 'status' AS VARCHAR)` (works on the `json` column). Outer: `JOIN anon ON machines.id = anon.machine_id ... AND anon.rn = 1 AND anon.status = :status`. `rn = 1` and the status test are both outside the window, so a latest row with NULL / missing status matches nothing and older rows are never consulted (R12c). Bounded by workspace both inside (activity rows) and outside (`machines.workspace_id`): HR-16 OK.
- Factory join: `JOIN factories ON factories.id = machines.factory_id` with `factories.is_deleted = false`. `machines.factory_id` is NOT NULL with a FK to `factories.id` (PK), so the inner join can neither drop live-factory rows nor duplicate any row.
- Section join (`get_by_section`, and `search_advanced` only when `factory_section_id` is given): `JOIN factory_sections ON factory_sections.id = machine_section_assignments.factory_section_id` with `is_deleted = false`. `factory_section_id` is NOT NULL FK; the assignment is unique per machine, so no duplicates. Without a section filter there is no section join, so a machine with a left-over assignment to a deleted section is still listed (R6a).
- The eager load still uses its own aliases (`machine_section_assignments_1`, `factory_sections_1`) and does not clash with the new explicit joins. No collection eager-load, so `LIMIT` is not wrapped.
- ORDER BY: `lower(machines.name) ASC|DESC, machines.id ASC` (ORM columns); `created_at` sort unchanged.
- `get_by_factory` / `get_by_section`: still **no ORDER BY**, same `LIMIT/OFFSET`, callers' `limit` untouched (brief §6, BUG-342 / BUG-343 respected).

## Performance

`machine_activity_events` has only single-column indexes (`id` PK, `machine_id`, `workspace_id`). The window scans and sorts all `status_updated` rows of the workspace. The old (broken) query did the same scan for its `max(created_at) GROUP BY` and then a second join back to the table, so this is no worse, and it only runs when the status filter is set. Follow-up (not for this unit, needs a migration): a partial index `(workspace_id, machine_id, created_at DESC, id DESC) WHERE event_type = 'status_updated'` would serve both this filter and `MachineActivityEventDAO.get_latest_status_map` once the activity table grows.

## Upstream (callers)

- `MachineManager.search_machines` → `MachineService.get_machines` → `GET /machines/`: the normal path passes through; the maintenance path (`skip=0, limit=10_000`, then pages in Python) now hides deleted-factory machines before the cap, which is the intended behaviour and slightly eases BUG-958. The `include_deleted=True` path uses `get_by_workspace` and is unaffected (BUG-956 / BUG-957 remain the manager's).
- `MachineManager._check_name_exists_in_factory` (create / update) uses `get_by_factory`. For a **soft-deleted** factory it now sees no machines, so a duplicate name is no longer refused there. Reaching that state at all requires creating / editing a machine in a soft-deleted factory, which is BUG-963 / BUG-964 (manager, open). Interim effect only; once BUG-963 / BUG-964 refuse those writes it cannot happen. Not blocking; noted for the manager unit.
- `resolve_template_machine_ids` (`app/utils/work_order_generation.py`, `limit=1000`): drafts are no longer generated for machines of a deleted factory or a deleted section (BUG-889 / BUG-891 intended). Order and cap unchanged (BUG-342 / BUG-343 still open).
- `machine_maintenance_log_manager`, `machine_item_manager`, `machine_activity_manager`, `attachment_manager`, work order / purchase / transfer managers: use only `get`, `get_by_id_and_workspace` (raw, unchanged). Not affected.
- No caller re-sorts the `search_advanced` result except the maintenance path, which re-sorts by maintenance date (its own rule).

## Consistency

- Matches the merged `factory_section` DAO rule (soft-deleted factory hides its children by state alone, inactive factory hides nothing). That DAO uses `EXISTS`; this one an inner join; equivalent here because of the NOT NULL FK to a PK.
- Edge (not in the brief, not blocking): `get_by_section` checks the **machine's** factory, not the section's factory. They differ only when a machine was moved without clearing its section (BUG-970, manager). Then a live machine in a live factory would still be listed for a section of a deleted factory (the section itself not deleted). Will disappear with BUG-970's fix.
- BUG-1090 (displayed latest status picks by timestamp only) can now disagree with this filter on a timestamp tie; known and out of scope per the brief.

## Shortcuts / scope

- `_escape_ilike` copied a third time (account_invoice, help_ticket, machine). Acceptable under the one-file rule; already recorded as follow-up F8 in `docs/bugfix/improvements.md` (shared helper in `app/utils/`).
- Name sort fallback for unknown `sort_by` is also case-insensitive: consistent with R13 ("sorts by name").
- `include_deleted=True` on the two lookups (dead code, §6) still hides deleted factory / section children; no caller passes it.
- Removed unused import `and_`. Nothing else outside the brief.

## Neighbouring bugs

BUG-958 (eased, not fixed), BUG-963 / BUG-964 (interim duplicate-name effect above), BUG-970 (section-of-other-factory edge), BUG-1090 (tie disagreement), BUG-342 / BUG-343 (untouched).

## Tester notes

- Pre-check conditional: the BUG-886 enum-input test correction for the 3 caller tests must be on origin/main before the baseline (commit `ca0ffe8` "batch-3 test corrections (… BUG-886)" is on main); otherwise drop those 3 targets as the pre-check says.
- `test_machine_section_assignment.py` must be run on its own (fixture clash when collected with the factory files; unrelated).

## New bugs found

None.
