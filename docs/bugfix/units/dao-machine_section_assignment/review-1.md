# Code review 1: dao-machine_section_assignment (2026-11-27)
Verdict: PASS   (blockers: 0, majors: 0, minors: 1, nits: 2)
Diff reviewed: 092776b..881a95c, files: app/dao/machine_section_assignment.py (no alembic changes)

## 1. What a correct fix must do (written before reading the diff)

- **BUG-906 (`get_by_section`)**: add `ORDER BY id ASC` in SQL, after the two
  workspace/section filters and before `OFFSET`/`LIMIT`. `id` is the PK, so the
  order is unique and indexed; nothing else is needed. Defaults (`skip=0`,
  `limit=500`), keyword-only signature, negative skip/limit DataErrors and the
  filters must be unchanged. `clear_for_section` gets its order (R7) for free and
  must keep the `limit=10000` cap exactly (BUG-907 out of scope).
- **BUG-909 (`upsert_for_machine`)**: look up the existing row in the given
  workspace only (HR-16, `get_by_machine` unchanged). If a row exists and its
  `factory_section_id` equals the one passed, return that row with **nothing
  written**: no delete, no insert, no update of `updated_at`/`updated_by`, and
  `user_id` unused (so an invalid user id cannot fail the re-save). Every other
  path stays as it was: `None` deletes the row (or no-ops when there is none);
  a different section deletes the old row and inserts a new one with
  `created_by=user_id` (R2, move replaces); the other-workspace row case still
  hits the unique constraint (R7). Since `factory_section_id` is NOT NULL on the
  row, a `None` argument can never match the same-section check.
- Must not change: callers (manager already expires `section_assignment` after
  the call, which is harmless on a no-op), `clear_for_section` behaviour, any
  other file. Docstring of `clear_for_section` may be corrected (spec Q1).

## 2. Findings

### R1-1 [minor] `upsert_for_machine` docstring still says it always replaces
- Where: app/dao/machine_section_assignment.py:42-43 (`upsert_for_machine`)
- Problem: the docstring reads "Replace whatever assignment a machine has with
  `factory_section_id`", which is no longer true when the section is the same:
  the row is kept. The new contract is only stated in the inline comment at
  line 45, so a reader of the docstring (or IDE hover) gets the old behaviour.
- Evidence: docstring text vs. lines 46-47 (`return existing` on same section).
- Suggested direction: state in the docstring that re-saving the current
  section leaves the existing row untouched and returns it.

### Nits
- app/dao/machine_section_assignment.py:46 uses truthiness `if existing and ...`;
  `existing is not None` would be more explicit. It matches the existing
  `if existing:` on line 48 and app/dao/inventory.py:259, so it is consistent;
  style only.
- Out of this unit's scope (do not change here): the comment in
  app/managers/machine_manager.py:176-178 ("The assignment row was
  deleted/replaced out from under the ORM's cached relationship") is now not
  always true; the expire is still harmless. For the owner to note for a later
  manager touch.

## 3. Questions (unproven)

None.

## 4. What is good

- Minimal: one `order_by` line, a two-line early return, and the spec-Q1
  docstring correction for `clear_for_section`; the BUG-907 cap is untouched.
- The same-section check uses the row found in the caller's workspace, so HR-16
  holds. Checked with a rolled-back script against
  `bf_dao_machine_section_assignment_test`:
  - a re-save emits only the lookup SELECT: same object, same `id`,
    `created_by` and `created_at`, `updated_at` stays NULL;
  - a re-save with a user id that does not exist (99999999) succeeds, writing nothing;
  - a move still creates a new row with `created_by` = the saving user, and the
    machine keeps exactly one row;
  - `None` clears the row, and `None` again returns `None`;
  - paging `skip=0/2/4, limit=2` over 5 rows, after updating three of them to
    disturb the physical order, gives exactly the ids in ascending order;
  - `clear_for_section` returns the machine ids in row-id order.
- `ruff check` passes on the changed file.
