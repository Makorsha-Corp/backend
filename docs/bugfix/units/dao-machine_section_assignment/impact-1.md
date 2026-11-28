# Impact review 1: dao-machine_section_assignment

Date: 2026-11-27. Diff: worktree `bugfix/dao-machine_section_assignment`, `git diff origin/main -- app alembic`
(only `app/dao/machine_section_assignment.py`; no migration). Checks in a rolled-back rowkit session
against `bf_dao_machine_section_assignment_test`, script in the session scratchpad (`se_msa/`), run
from the worktree with `PYTHONPATH=.`.

**Verdict: APPROVE.** No contract change (see `contract.md`).

## Changed functions

### `get_by_section` (BUG-906)
- `.order_by(MachineSectionAssignment.id.asc())` before `.offset().limit()`: ORM column, SQL
  `ORDER BY machine_section_assignments.id ASC LIMIT .. OFFSET ..`. Filters unchanged (workspace
  bound kept, HR-16). Signature and defaults unchanged.
- Callers: only `DAOMachineSectionAssignment.clear_for_section` (`limit=10000`). `machine_dao.get_by_section`
  (`app/utils/work_order_generation.py`) is a different class, untouched.
- `clear_for_section` → `MachineSectionAssignmentManager.clear_for_section` (iterates the ids and
  expires each machine; order-insensitive) → `FactorySectionManager.delete_factory_section`
  (`app/managers/factory_section_manager.py:299`) → `DELETE /factory-sections/{id}/`. Nothing re-sorts
  or depends on the previous order. The cap (BUG-907) is untouched; which rows a 10 000 cap would
  leave is now deterministic (lowest ids kept first), which is the brief's intent.

### `upsert_for_machine` (BUG-909): early return for the same section
- `existing` comes from `get_by_machine` (bounded by `workspace_id`, HR-16). The check compares only
  `factory_section_id`; `machine_id` and `workspace_id` are already pinned by the lookup, so no other
  column could differ for an "unchanged" row. `factory_section_id=None` can never match (column NOT
  NULL), so clear (R4) and move (R2, still delete + insert) are unchanged. A row in another workspace
  is not found, so R7 (unique violation on insert) is unchanged.
- **Callers** (grep `upsert_for_machine`, `machine_section_assignment_dao`, `assignment_dao`,
  `set_assignment`): only `MachineSectionAssignmentManager.set_assignment`, called from
  `MachineManager.create_machine` (line 91) and `MachineManager.update_machine` (line 173).
  - **Returned object:** both machine-manager callers discard the return value of `set_assignment`;
    no service or endpoint uses it. The returned object is now the persistent existing row (the same
    instance as a loaded `machine.section_assignment`) instead of a freshly flushed new one. Same type,
    same fields except `id`/`created_by` now the original ones, which is the intended change.
  - **Flush:** the early-return path does not flush. Nothing is pending from this method at that
    point; the machine's own changes in `update_machine` are flushed by `machine_dao.update` before
    the call, and the service commits afterwards (`MachineService.update_machine` commit + refresh).
    No caller relies on a flush inside the DAO.
  - **Expire:** both callers expire `machine.section_assignment` after the call; on reload it gives
    the same row. `factory_section_id` / `factory_section_name` on the response are unchanged.
  - **Audit fields:** the assignment row keeps `created_by`/`created_at`; `updated_*` stay NULL (as
    before; R2 and R3 never write them). The machine's own `updated_by` is still stamped by
    `update_machine` on every update (pre-existing behaviour, unrelated; the machine-level no-op
    stamping is not in this unit's bugs).
  - **Events:** the activity log is driven by `collect_field_changes` on `machine.factory_section_id`
    (read before the call) vs the requested value; equal → no change entry, as before. The fix does
    not touch event logging (`update_machine` R18 already said "no event").
  - **create_machine:** a new machine has no row, so the early return can never trigger there.
- **Checked** (manager level, worktree code): machine with a row in section S, `update_machine` with
  `factory_section_id=S` by a second user → statements written: only the `machines` UPDATE (its
  `updated_by`); no DELETE/INSERT on `machine_section_assignments`; no activity INSERT; same row id;
  one row; `machine.factory_section_id == S` after the call.
- **Neighbour BUG-971** (editing a machine whose section is deleted fails because the manager
  re-validates the re-sent section): still open; the manager's refusal happens before the DAO, so this
  fix neither helps nor hurts it. Note for its unit: once BUG-971 lets the same (deleted) section
  through, this early return already makes it a no-op at the DAO.

### `clear_for_section` docstring (spec decision Q1)
- Wording only; behaviour and `limit=10000` unchanged. Correct: the assignment manager expires the
  machines itself.

## Downstream
- `get_by_machine` unchanged. No locks, no new queries beyond the ORDER BY. No migration, no constraint.

## Database
- No schema change. No check script needed.

## Neighbouring bugs
- BUG-907 (cap) and BUG-908 (hard delete on section delete): untouched, as the brief says.
- BUG-910, BUG-928, BUG-971: untouched; no clash.
- BUG-934 (item tags re-created) cites BUG-909 as precedent; not affected.

## Shortcuts / scope
- None. The early return is the rule itself (same value → no write), not a special case. Nothing
  outside the brief changed. Worktree has no leftover `.scratch/`.

## New bugs found
- None.

## Process note (for the orchestrator)
- The fixer's agent definition (`.claude/agents/bug-fixer.md` step 5) says throwaway checks go
  **only under `<worktree>/.scratch/` (not the session scratchpad)**; this round's rules told the
  fixer to use the scratchpad, and the fix-notes say it did. The brief itself says nothing about
  scratch location. One of the two should be made consistent (the agent definition is the one
  that names `.scratch/`).
