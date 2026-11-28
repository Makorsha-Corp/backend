# Fix notes: dao-machine_section_assignment

## Round 1 (2026-11-27)

Worktree: `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-machine_section_assignment`, branch `bugfix/dao-machine_section_assignment`. Only `app/dao/machine_section_assignment.py` changed. No migration and no change to any signature.

### Changed

- **BUG-906**: in `DAOMachineSectionAssignment.get_by_section`, added `.order_by(MachineSectionAssignment.id.asc())` before `.offset(skip).limit(limit)`.
- **BUG-909**: in `DAOMachineSectionAssignment.upsert_for_machine`, right after the `get_by_machine` lookup, added an early return. If `existing` is found and `existing.factory_section_id == factory_section_id`, the method returns `existing` and writes nothing. There is a one-line comment explaining why.
- **Docstring only (spec decision Q1)**: in `clear_for_section`, replaced the wrong claim that row-by-row deletes refresh already-loaded machines. It now says the caller must expire or reload them. The behaviour and the `limit=10000` cap are unchanged.

### Why

- BUG-906: with `id` ascending applied before skip/limit, consecutive windows split the section's rows with no repeats or gaps (HR-6). `clear_for_section` reads through `get_by_section`, so its returned ids now come back in row-id order (its R7) with no change to that method.
- BUG-909: re-saving the current section now returns the existing row with the same `id`, `created_by` and `created_at`, and issues no SQL write (HR-9, following the BUG-870 precedent). The check uses the row found within the given `workspace_id`, so HR-16 still holds. When `factory_section_id` is `None` the check cannot match, because the column is NOT NULL. So clearing (R4) and moving to another section (R2, which still replaces the row) behave as before.

### Reproduction (throwaway script in the session scratchpad, rowkit against `bf_dao_machine_section_assignment_test`; now deleted)

| Check | Before | After |
|---|---|---|
| `get_by_section` SELECT contains `ORDER BY` | False | True (`ORDER BY machine_section_assignments.id ASC LIMIT 500 OFFSET 0`, also confirmed with `compile_query.py`) |
| 5 rows, read in pages of 2, give all ids sorted | True (by luck: the small heap returned rows in id order) | True |
| `clear_for_section` deletes all 5 and leaves `[]` | yes | yes |
| SQL writes when re-saving the same section with another user | `DELETE`, `INSERT` | none |
| Re-save keeps the same `id` / `created_by` / `created_at` | False / False / True* | True / True / True |
| Machine has exactly one row after re-save | 1 | 1 |
| R2 move to another section: new id, new `created_by`, 1 row, `updated_by` None | yes | yes |
| R4 clear with `None`: returns None, 0 rows; clearing again returns None | yes | yes |

\* `created_at` matched even before the fix, because the database default is `now()`, the transaction start time, and the whole check runs in one transaction. A test that relies on `created_at` to detect re-creation would need separate transactions. `id` and `created_by` are the reliable signals.

Other checks: `ruff check app/dao/machine_section_assignment.py` passes, and `import app.main` succeeds.

### Assumptions

- Matching is on `factory_section_id` alone, because the lookup already pins `machine_id` and `workspace_id`. No other column could differ for an "unchanged" row.
- The same-section return does not flush. Nothing is pending from this method at that point, so a flush is not needed.

### Seen, not fixed

- Nothing new. BUG-907, BUG-908, BUG-910, BUG-971 and BUG-928 were left alone as the brief says.

### Risk

- Low. Callers expire the machine after the call. On a re-save the returned object is the same instance as the machine's loaded `section_assignment`, which is harmless. Worth a glance at `update_machine` R18: no activity event for a re-sent section, which was already the case.
