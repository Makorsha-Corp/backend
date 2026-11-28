# Fix brief: dao-machine_section_assignment

## 1. Unit

| | |
|---|---|
| Slug | `dao-machine_section_assignment` |
| Source file | `app/dao/machine_section_assignment.py` |
| Worktree | `E:\Projects\Makorsh-Corp\bugfix-worktrees\dao-machine_section_assignment` |
| Branch | `bugfix/dao-machine_section_assignment` (from `origin/main`) |
| Risk | `normal` (BUG-906 `unordered-pagination` is on the trivial list; BUG-909 `unchanged-rows-recreated` is not) |

## 2. Bugs

### BUG-906: Assignment rows of a section have no sort order
- **Pattern:** `unordered-pagination`
- **Where:** `DAOMachineSectionAssignment.get_by_section`; reached through `clear_for_section` ← "delete section".
- **Today:** No `ORDER BY`; the order is unspecified, paging can repeat or skip rows, and which rows the 10 000 cap of `clear_for_section` leaves behind is arbitrary.
- **Intended:** `id` ascending before `skip` / `limit` (HR-6; the rows have no name).

### BUG-909: Re-saving a machine's current section deletes and re-creates its assignment
- **Pattern:** `unchanged-rows-recreated`
- **Where:** `DAOMachineSectionAssignment.upsert_for_machine`; reached through `POST /machines/`, `PUT /machines/{id}/` whenever `factory_section_id` is sent.
- **Today:** When the machine already has exactly that section, the row is deleted and a new one inserted: new `id`, `created_by` = the saving user, `created_at` = now.
- **Intended:** HR-9: same section → nothing written, the existing row (same `id`, `created_by`, `created_at`) is returned (per BUG-870 precedent: account tags that stay keep their row untouched).
- **Example:** Rahim put "Press 4" into section "Cutting" in January. In March Karim edits the machine's note; the edit form re-sends "Cutting". Today the link row is thrown away and re-written as "created by Karim, March". Intended: the link still reads "created by Rahim, January", with the same row id.

## 3. Intended behaviour (spec rules, copied)

Facts for the whole file:
- Table `machine_section_assignments` (`app.models.machine_section_assignment.MachineSectionAssignment`): `id` Integer PK; `workspace_id` NOT NULL (FK `workspaces.id`); `machine_id` NOT NULL (FK `machines.id`), **unique** (`uq_machine_section_assignment_machine`) — at most one row per machine; `factory_section_id` NOT NULL (FK `factory_sections.id`); `created_at` NOT NULL, database default `now()` (the transaction start time); `created_by` nullable (FK `profiles.id`); `updated_at`, `updated_by` nullable, `NULL` by default.
- **No soft-delete column**: unassigning deletes the row. Absence of a row means "unassigned". Nothing in the database ties the row's `workspace_id` to the machine's or the section's workspace.
- `Machine.section_assignment` (`uselist=False`); `machine.factory_section_id` / `machine.factory_section_name` are read-only properties reading it.
- The DAO validates nothing about the machine, the section or the factory — the manager does. It never commits; writes are flushed.
- Every parameter after `db` is keyword-only in all four methods (a positional call raises `TypeError`). Signatures and defaults stay as they are.

### `DAOMachineSectionAssignment.get_by_machine(db, *, machine_id, workspace_id)` (used by `upsert_for_machine`; not in a bug; must not change)
- **R1.** Given a machine with an assignment row in the workspace, that row is returned. Given a machine without one, an unknown machine id, or a `workspace_id` other than the row's own, `None` is returned (a row of another workspace is never returned).
- **R2.** The machine, section and factory rows are not looked at: the row is returned when the machine is soft-deleted, when the section it points at is soft-deleted, and when the section belongs to another factory or workspace than the machine.
- **R3.** Nothing is written.

### `DAOMachineSectionAssignment.get_by_section(db, *, factory_section_id, workspace_id, skip=0, limit=500)`
Used only by `clear_for_section` (with `limit=10000`). Returns a `list` of `MachineSectionAssignment` (possibly empty).
- **R1.** Only rows with `factory_section_id` and `workspace_id` equal to the arguments are returned. A row of the same section id with another `workspace_id`, and rows pointing at other sections, are never returned.
- **R2.** The machine and section rows are not looked at: rows of soft-deleted machines are returned, and the rows of a soft-deleted section are returned exactly as for a live one. (Raw lookup, intended; hiding is the caller's decision.)
- **R3.** An unknown section id, or a section with no rows in the workspace, returns `[]`.
- **R4.** Filters are applied before `skip` / `limit`. With defaults at most 500 rows are returned — given 501 rows of the section, exactly 500; with `limit=501`, 501.
- **R5.** `limit=0` returns `[]`; `skip` at or past the number of matching rows returns `[]`. A negative `limit` raises `sqlalchemy.exc.DataError` (`.orig` is `psycopg2.errors.InvalidRowCountInLimitClause`, pgcode `2201W`, "LIMIT must not be negative"); a negative `skip` raises `DataError` (`.orig` is `InvalidRowCountInResultOffsetClause`, pgcode `2201X`, "OFFSET must not be negative").
- **R6.** [BUG-906] (HR-6) Rows are ordered by `id` ascending before `skip` / `limit`, so consecutive windows (`skip=0, limit=2`, `skip=2, limit=2`, …) partition the section's rows with no repeats or gaps. *(Today: no ordering is requested; the order is whatever the database produces.)*
- **R7.** Nothing is written.

Side effects: none.

### `DAOMachineSectionAssignment.upsert_for_machine(db, *, machine_id, factory_section_id, workspace_id, user_id)`
Used by `MachineSectionAssignmentManager.set_assignment` ← `MachineManager.create_machine` (when `factory_section_id` is given) and `MachineManager.update_machine` (whenever `factory_section_id` is in the request, including `null`) ← `POST /machines/`, `PUT /machines/{id}/`. The manager first refuses a missing / other-workspace section (404), a deleted section (400) and a section of another factory (400); it checks nothing about the machine. Returns the machine's `MachineSectionAssignment` (flushed, not committed), or `None` when `factory_section_id` is `None`.
- **R1.** Given a machine without an assignment and a section id, one row is created with `workspace_id`, `machine_id`, `factory_section_id` as given, `created_by = user_id`, `created_at` set by the database, `updated_at = None`, `updated_by = None`; it is returned and is the machine's only row.
- **R2.** (Intended, must not change.) Given a machine assigned to section A and a different section B, afterwards the machine has exactly one row, pointing at B; it is a new row (different `id`) with `created_by = user_id`; the old row is gone. `updated_at` / `updated_by` stay `None`. (A move replaces the row; it is not an in-place update.)
- **R3.** [BUG-909] (HR-9) Given a machine already assigned to exactly the section passed, nothing is written: the existing row is returned with the same `id`, `created_by` and `created_at`; the machine still has exactly one row. *(Today: the row is deleted and a new one inserted — new `id`, `created_by` = the given user; still exactly one row.)*
- **R4.** (Intended, must not change.) Given `factory_section_id=None` and a machine with an assignment, the row is deleted and `None` is returned; the machine has no row afterwards. Given `None` and a machine without an assignment, `None` is returned and nothing is written. `user_id` is not used in either case.
- **R5.** Only the machine's own row is touched: rows of other machines (in the same section or not) are unchanged. The machine, section and factory rows are never written.
- **R6.** Nothing about the target is checked: the row is created for a section of another factory than the machine's, a soft-deleted section, a section of another workspace, a soft-deleted machine, and a machine of another workspace (stored with the given `workspace_id`). (The manager refuses the first three before calling; the others are a manager matter, not this unit's.)
- **R7.** The existing row is looked for only in the given workspace (`get_by_machine` R1). Given a machine whose row has another `workspace_id`, that row is not found and not deleted; the insert then violates the one-row-per-machine constraint (`IntegrityError` / `UniqueViolation`, `uq_machine_section_assignment_machine`) and nothing changes.
- **R8.** Given a `machine_id`, `factory_section_id`, `user_id` or `workspace_id` that references no row, the flush fails with `IntegrityError` / `ForeignKeyViolation` (constraints `machine_section_assignments_machine_id_fkey`, `…_factory_section_id_fkey`, `…_created_by_fkey`, `…_workspace_id_fkey`). Inside a savepoint that is rolled back, the machine's previous row (if any) is back unchanged. (With R3 in place, a re-save of the current section writes nothing and so cannot fail on the user's foreign key; the other cases are unchanged.)
- **R9.** Changes are flushed, not committed: in the same session `get_by_machine` returns the new row (or `None` after clearing); rolling back restores the previous state.
- **R10.** (Intended, must not change.) A `Machine` object whose `section_assignment` was already loaded in the session is not refreshed by this DAO: its `factory_section_id` still gives the old section (or the old value after clearing) until the machine is expired or reloaded; then it gives the new value. A later flush of that machine (e.g. after changing its name) does not bring the deleted row back. Refreshing loaded objects is the caller's job (both callers expire the machine after the call).

Side effects: at most one `machine_section_assignments` row deleted and at most one inserted, flushed; no commit; no other table written. After the fix, a re-save of the current section writes nothing at all.

The callers' rules say the same thing and follow from R3 with no change in the callers: `set_assignment` R4 — given the section the machine already has, nothing is written and the existing link is returned with the same `id`, `created_by` and `created_at`; `update_machine` R18 — re-sending the section the machine already has writes nothing: same link `id`, `created_by` (and, as today, no machine activity event is recorded for it).

### `DAOMachineSectionAssignment.clear_for_section(db, *, factory_section_id, workspace_id)` (reads through `get_by_section`; must keep working)
Used by `MachineSectionAssignmentManager.clear_for_section` ← `FactorySectionManager.delete_factory_section` ← `DELETE /factory-sections/{id}/`. Returns the `list` of `machine_id`s of the removed rows.
- **R1.** Every assignment row with this `factory_section_id` and `workspace_id` is deleted (a real DELETE) and its `machine_id` is in the returned list; the list has one entry per deleted row.
- **R2.** Rows pointing at other sections, and rows of other workspaces pointing at the same section id, are not touched and their machines are not in the list.
- **R3.** The state of the section and of the machines does not matter: rows of soft-deleted machines are deleted and listed too; the call works the same whether the section is live or soft-deleted. The section, machine and factory rows themselves are never written.
- **R4.** [BUG-907, **not in this unit**] The 10 000-row cap. Leave it exactly as it is (see §6).
- **R5.** An unknown section id, or a section with no rows in the workspace, returns `[]` and writes nothing.
- **R6.** (Intended, must not change.) A `Machine` whose `section_assignment` was already loaded still reports the removed section until it is expired or reloaded; then it reports `None`.
- **R7.** [BUG-906] The returned ids follow the order of `get_by_section` R6 (row `id` ascending). This follows from the `get_by_section` fix; `clear_for_section` itself needs no change for it. *(Today: unspecified.)*
- **R8.** Changes are flushed, not committed: in the same session `get_by_section` returns `[]`; rolling back a savepoint around the call brings every row back.

### Inherited `BaseDAO` methods (not overridden; must not change)
- **R1.** `create` with a `MachineSectionAssignmentCreate` always fails (the schema has no `workspace_id`: `NotNullViolation`); `create` with a dict holding `workspace_id`, `machine_id`, `factory_section_id` creates a row; a second row for the same machine raises `UniqueViolation`.
- **R2.** `update` with a dict sets the given columns; `updated_at` becomes non-null.
- **R3.** [BUG-100, **not in this unit**] `get_by_workspace` order — fixed in `app/dao/base.py`, nothing to do in this file. Do not override it here.

## 4. Rules that apply

- **HR-6. Every paged or top-N result has a stable order.** Default: name case-insensitive ascending, then `id` ascending. Generic `BaseDAO` lists only guarantee `id` ascending (stable paging); choosing a display order is the manager's job. Assignment rows have no name, so `id` ascending is the whole order.
- **HR-9. Audit stamps mean something changed.** `updated_by` (and similar "last changed by" fields) is written only when at least one field actually changes value. Applied here (BUG-870 precedent): a row whose values would not change is left untouched rather than deleted and re-created.
- **HR-5. Filter first, then page.** All filtering happens in the query before `skip` / `limit` (holds today; keep it).
- **HR-16. Nothing links across workspaces.** Every lookup stays bounded by `workspace_id` (holds today; keep it — the same-section check must use the row found in the given workspace).
- Spec decision Q1 (decided by Claude under the reviewer's delegation, 2026-10-16): the docstring of `clear_for_section` wrongly claims that row-by-row deletes refresh already-loaded machines; reloading is the caller's job. The comment is to be corrected when the file is next touched. You may correct that docstring wording; do not change the method's behaviour.
- No owner answer (OQ-n) touches these bugs.

## 5. Scope

- May change: `app/dao/machine_section_assignment.py` only.
- No migration, no schema or API change. Method signatures stay as they are, including `get_by_section`'s defaults (`skip=0`, `limit=500`) and keyword-only parameters.

## 6. Out of scope (leave alone)

- **BUG-907** (`clear_for_section`, the 10 000-row cap): **not in this unit.** It closes when `clear_for_section` is removed together with the BUG-908 fix (a multi-file change). Do not change the `limit=10000` call or the cap in any way.
- **BUG-908** (`app/managers/factory_section_manager.py`, "delete section" hard-deletes the section's assignment rows): fixed in the section manager in a separate unit. **Do not remove or rename `clear_for_section` or `get_by_section` in this unit**, even though they will become dead code after BUG-908; both are reachable today and must keep their behaviour (apart from the BUG-906 order).
- **BUG-910** (`app/managers/machine_section_assignment_manager.py`, `set_assignment` accepts a section of a soft-deleted factory).
- **BUG-971** (`app/managers/machine_manager.py`, editing a machine fails when its section was deleted — the re-sent section is re-validated in the manager). Not fixed by BUG-909; leave the manager alone.
- **BUG-928** (`app/managers/factory_section_manager.py`, moving a section to another factory ignores its machine assignments).
- **BUG-100** (`app/dao/base.py`, generic lists without order).
- Moving a machine to another section keeps replacing the row (R2, intended). Changing a machine's factory without sending a section keeps a section of the old factory: a manager matter, not this file's.
