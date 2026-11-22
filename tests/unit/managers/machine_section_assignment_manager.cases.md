# Test cases — `app/managers/machine_section_assignment_manager.py`

> **Spec:** `tests/unit/managers/machine_section_assignment_manager.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-10-16); every answer (P1 / BUG-910, P2, Q1 and the lines citing BUG-906, BUG-907, BUG-908, BUG-909) was decided by Claude under the reviewer's delegation, so nothing is provisional.
> **Counts:** 51 cases · 47 expected-to-pass · 4 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Per callable:** `set_assignment` 37 (2 bug) · `clear_for_section` 14 (2 bug).
- **Expected-to-fail by bug:** BUG-909 1 (MSM-SET-08, strict) · BUG-910 1 (MSM-SET-19, strict) · BUG-907 1 (MSM-CLR-09, strict, bulk) · BUG-906 1 (MSM-CLR-13, non-strict). BUG-908 has no card here (its fix is in the section manager).
- **Delegated answers and the cards that rest on them:** P1 / BUG-910 — MSM-SET-19 (xfail) and the pass cards around it SET-20 (another factory still gets the "does not belong" message), SET-21 (an inactive-but-live factory is accepted), SET-22 (clearing stays allowed). P2 (a machine already loaded is not refreshed by `set_assignment`) — MSM-SET-31 … SET-34. Q1 (the machine is not looked at) — MSM-SET-24, SET-25, SET-26, SET-27.
- **Dead code after BUG-908:** `clear_for_section` is on the dead-code list "remove together with the fix of BUG-908". The 14 cards MSM-CLR-01 … CLR-14 test it as it behaves today and are deleted in that change (with them BUG-906's and BUG-907's xfails here).
- **Notable design choices:**
  - Three standing rows are added to the DAO's set: FD (a soft-deleted factory), SF (a live section of FD) and MF (a machine of FD) — the BUG-910 situation.
  - No order today (BUG-906): every card except MSM-CLR-13 (non-strict) compares the returned ids as sorted lists, one-element lists or sets. The query is the DAO's, not this manager's: the strict alarm is the DAO's statement-recorder card MSA-GS-22; no recorder here.
  - "Re-created" is seen only through `id` and `created_by` (U1 wrote the Given links, U2 calls); `created_at` is never compared.
  - BUG-909: MSM-SET-08 (strict, fails on the link id) has the pass companion SET-09. BUG-910: SET-19 (strict, fails because no error is raised) carries only fixed-path checks.
  - Refusals (404 / 400) need no savepoint; database errors are wrapped in one (Conventions).
  - Cards marked `Author: claude` (5): bulk setup — MSM-CLR-09 (10 001 rows); non-strict xfail with an edit of a Given row — CLR-13; savepoint rollback and commit spy — SET-35, CLR-14; a step after the When (`db.expire`) — SET-34.
- **Needs a decision:** None blocking. See Spec gaps 1 (constraint names asserted as "contained in"), 2 (keyword-only parameters: no card), 3 (R6 "machines not loaded" has a weak observable).


## Conventions for this module

**IDs.** `MSM` = `app/managers/machine_section_assignment_manager.py`. `SET` set_assignment · `CLR` clear_for_section.

**Actors and fixed values.**
- `mgr` = the singleton `machine_section_assignment_manager` (`from app.managers.machine_section_assignment_manager import machine_section_assignment_manager`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- W1, W2 = two `workspaces` rows. U1, U2 = two `profiles` rows: U1 is `created_by` of every Given assignment, U2 is the acting user of the calls.
- `MachineSectionAssignment` = `app.models.machine_section_assignment.MachineSectionAssignment`. `Machine` = `app.models.machine.Machine`. `HTTPException` = `fastapi.HTTPException`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `mgr`) and flushed one at a time in the order written, so ids rise in that order. A card names, by column name, every column that differs from these defaults.
- These eighteen rows exist in every test, inserted in this order, and need no Given line:
  - F1 = `factories` row: `name "Main Plant"`, `abbreviation "MP"`, `workspace_id W1.id`, `is_deleted False`. F2 = the same, but `name "North Yard"`, `abbreviation "NY"`. F9 = the same, but `name "Far Depot"`, `abbreviation "FR"`, `workspace_id W2.id`. FD = the same as F1, but `name "Closed Mill"`, `abbreviation "CM"`, `is_deleted True` (a soft-deleted factory of W1).
  - S1 = `factory_sections` row: `name "Cutting"`, `factory_id F1.id`, `workspace_id W1.id`, `is_active True`, `is_deleted False`. S2 = the same, but `name "Paint"`. S3 = the same, but `name "Welding"`, `factory_id F2.id`. SX = the same, but `name "Old Line"`, `is_deleted True` (a soft-deleted section of F1). S9 = the same, but `name "Packing"`, `factory_id F9.id`, `workspace_id W2.id`. SF = the same as S1, but `name "Boiler Room"`, `factory_id FD.id` (a live section of the soft-deleted factory FD).
  - M1 = `machines` row: `name "Lathe"`, `factory_id F1.id`, `workspace_id W1.id`, `is_active True`, `is_deleted False`, `is_running False`. M2 = the same, but `name "Press"`. M3 = the same, but `name "Drill"`. MD = the same, but `name "Old Saw"`, `is_deleted True` (a soft-deleted machine of W1). M9 = the same, but `name "Grinder"`, `factory_id F9.id`, `workspace_id W2.id`. MF = the same as M1, but `name "Kiln"`, `factory_id FD.id` (a live machine of FD).
  - So `M1.id < M2.id < M3.id < MD.id < M9.id < MF.id`.
- No `machine_section_assignments` row exists unless the card's Given lists it.
- **assignment of M to S** = `machine_section_assignments` row built with `MachineSectionAssignment`: `workspace_id` = M's `workspace_id`, `machine_id M.id`, `factory_section_id S.id`, `created_by U1.id`, `updated_by None`, `updated_at None`, `created_at` left to the database. After the word "but" the card lists every column that differs.
- **extra factory** = `factories` row: `workspace_id W1.id`, `is_active True`, `is_deleted False`. The card gives `name` and `abbreviation`, and after "but" every other column that differs.
- **section of F** = `factory_sections` row: `workspace_id` = F's `workspace_id`, `factory_id F.id`, `is_active True`, `is_deleted False`. The card gives `name`, and after "but" every other column that differs.
- **machine of F** = `machines` row: `workspace_id` = F's `workspace_id`, `factory_id F.id`, `is_active True`, `is_deleted False`, `is_running False`. The card gives `name`.
- A Given line written as code (`a1_id = A1.id`) is a step to run exactly as written, at that place in the order.

**Named checks.**
- **rows_of(M)** = `db.expire_all()`, then SELECT every `machine_section_assignments` row with `machine_id == M.id` (any workspace), as a list.
- **re-read X** = `db.expire_all()`, then SELECT X by id from its own table; the listed values are database values. "the returned row" = re-read by `result.id`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line, before the call). X may be an assignment, a machine, a section or a factory.
- **nothing written** = the numbers of rows in `machine_section_assignments`, `machines`, `factory_sections` and `factories` (all workspaces) equal their values before the call.
- `count:` lines count the rows of the named table in all workspaces, with the filter stated. Assert `created_at` / `updated_at` only as `is None` / `is not None`; never compare `created_at` values.
- `clear_for_section` returns machine ids (integers). Where the order is not part of the check: `sorted(result) == [M1.id, M2.id]`, right-hand ids in ascending order.
- `raises: HTTPException`: plain `with pytest.raises(HTTPException) as exc:` around the call — no `begin_nested`; keep using `db` for the remaining checks.
- `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards (the savepoint is rolled back). `ForeignKeyViolation`, `UniqueViolation` = classes of `psycopg2.errors`.
- Further `raises:` lines of the same card are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; the harness adds the marker. Every xfail in this module is strict, except MSM-CLR-13, marked `(non-strict)` on its Expect line (`pytest.mark.xfail(strict=False, …)`).

**Rolled back** (cards marked Author: claude only). `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**Race simulations.** None in this module.


## `MachineSectionAssignmentManager.set_assignment`

### MSM-SET-01 — a machine without a section is put into a live section of its factory
- **Rules:** `set_assignment` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. No assignment exists.

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, MachineSectionAssignment)`.
2. returns: `result.id is not None`.
3. re-read the returned row: `machine_id == M1.id`, `factory_section_id == S1.id`, `workspace_id == W1.id`.
4. re-read the returned row: `created_by == U2.id`.
5. re-read the returned row: `updated_at is None`, `updated_by is None`.
6. count: rows_of(M1) has exactly 1 row.
7. count: `machine_section_assignments` has exactly 1 row.

### MSM-SET-02 — moving a machine to another section of its factory replaces its link with a new one
- **Rules:** `set_assignment` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. `a1_id = A1.id`

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=S2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.factory_section_id == S2.id`.
2. returns: `result.id != a1_id`.
3. count: rows_of(M1) has exactly 1 row.
4. re-read rows_of(M1)[0]: `id == result.id`, `factory_section_id == S2.id`.
5. re-read rows_of(M1)[0]: `created_by == U2.id`.
6. count: `machine_section_assignments` rows with `id == a1_id`: exactly 0.

### MSM-SET-03 — clearing a machine's section deletes its link and returns None
- **Rules:** `set_assignment` R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=None, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: rows_of(M1) has exactly 0 rows.
3. count: `machine_section_assignments` has exactly 0 rows.

### MSM-SET-04 — clearing validates nothing: an unknown factory_id and an unknown user_id still delete the link
- **Rules:** `set_assignment` R3 (Inputs: `factory_id` ignored and `user_id` unused when clearing)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=MISSING, factory_section_id=None, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. returns: `result is None`.
2. count: rows_of(M1) has exactly 0 rows.
3. unchanged: unchanged(S1).

### MSM-SET-05 — clearing a machine without a link returns None and writes nothing
- **Rules:** `set_assignment` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A2 = assignment of M2 to S1. (M1 has no assignment.)

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=None, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.
3. unchanged: unchanged(A2).
4. count: rows_of(M1) has exactly 0 rows.

### MSM-SET-06 — clearing an unknown machine id returns None and writes nothing
- **Rules:** `set_assignment` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `result = mgr.set_assignment(db, machine_id=MISSING, factory_id=F1.id, factory_section_id=None, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.
3. unchanged: unchanged(A1).

### MSM-SET-07 — clearing with an unknown workspace_id leaves the machine's link of W1 in place
- **Rules:** `set_assignment` R3 (assignment DAO `upsert_for_machine` R7: the link is looked for only in the given workspace)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1. (The link is in W1.)

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=None, workspace_id=MISSING, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.
3. unchanged: unchanged(A1).
4. count: rows_of(M1) has exactly 1 row.

### MSM-SET-08 — re-saving the section the machine already has leaves its link untouched
- **Rules:** `set_assignment` R4 [BUG-909]
- **Kind:** bug
- **Expect:** xfail BUG-909
- **Fails today on:** Then 3 (the link is deleted and a new one inserted, so the returned id is new)

**Given**
1. A1 = assignment of M1 to S1. (`created_by U1.id`.)
2. `a1_id = A1.id`

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.factory_section_id == S1.id`.
2. count: rows_of(M1) has exactly 1 row.
3. returns: `result.id == a1_id`.
4. re-read rows_of(M1)[0]: `id == a1_id`.
5. re-read rows_of(M1)[0]: `created_by == U1.id`.

### MSM-SET-09 — re-saving the same section keeps exactly one link of that machine to that section
- **Rules:** `set_assignment` R4 (the part that holds today and after the BUG-909 fix)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.factory_section_id == S1.id`.
2. returns: `result.machine_id == M1.id`.
3. count: rows_of(M1) has exactly 1 row.
4. re-read rows_of(M1)[0]: `factory_section_id == S1.id`, `workspace_id == W1.id`.
5. count: `machine_section_assignments` has exactly 1 row.

### MSM-SET-10 — a section id that no section has is answered with 404 and the machine keeps its link
- **Rules:** `set_assignment` R5, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory section with ID 999999999 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(A1).

### MSM-SET-11 — section id 0 is looked up, not taken as "clear", and answered with 404
- **Rules:** `set_assignment` R5, Errors row 1 (boundary: `0` is validated, only `None` clears)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=0, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory section with ID 0 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(A1).

### MSM-SET-12 — a negative section id is answered with 404
- **Rules:** `set_assignment` R5, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=-1, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory section with ID -1 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(A1).

### MSM-SET-13 — a section of another workspace is answered with the same 404
- **Rules:** `set_assignment` R6, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1. (S9 belongs to F9 of W2.)

**When**
- `mgr.set_assignment(db, machine_id=M1.id, factory_id=F9.id, factory_section_id=S9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory section with ID {S9.id} not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(A1).
6. unchanged: unchanged(S9).

### MSM-SET-14 — the same section is accepted from its own workspace
- **Rules:** `set_assignment` R6, R1 (other side of the workspace check)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No assignment exists. (M9, F9 and S9 belong to W2.)

**When**
- `result = mgr.set_assignment(db, machine_id=M9.id, factory_id=F9.id, factory_section_id=S9.id, workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == M9.id`, `factory_section_id == S9.id`, `workspace_id == W2.id`.
3. count: rows_of(M9) has exactly 1 row.

### MSM-SET-15 — a soft-deleted section is refused with 400 and the machine keeps its link
- **Rules:** `set_assignment` R7, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1. (SX is the soft-deleted section of F1.)

**When**
- `mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=SX.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot assign a machine to a deleted factory section"`.
4. nothing written: nothing written.
5. unchanged: unchanged(A1).
6. unchanged: unchanged(SX).

### MSM-SET-16 — a soft-deleted section of another factory gets the "deleted" message, not the factory message
- **Rules:** `set_assignment` R7, Errors row 2 (the deleted check comes first)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. No assignment exists. (SX is the soft-deleted section of F1; the call names F2.)

**When**
- `mgr.set_assignment(db, machine_id=M1.id, factory_id=F2.id, factory_section_id=SX.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot assign a machine to a deleted factory section"`.
4. nothing written: nothing written.
5. count: rows_of(M1) has exactly 0 rows.

### MSM-SET-17 — a live section of another factory is refused with 400 and the machine keeps its link
- **Rules:** `set_assignment` R8, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1. (S3 belongs to F2.)

**When**
- `mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=S3.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Factory section does not belong to this machine's factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(A1).

### MSM-SET-18 — a factory_id that names no factory is refused with the factory message
- **Rules:** `set_assignment` R8, Errors row 3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `mgr.set_assignment(db, machine_id=M1.id, factory_id=MISSING, factory_section_id=S2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Factory section does not belong to this machine's factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(A1).

### MSM-SET-19 — a live section of a soft-deleted factory is refused like a deleted section
- **Rules:** `set_assignment` R9 [BUG-910] (P1), Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-910
- **Fails today on:** Then 1 (no error is raised; the link to SF is saved)

**Given**
1. SG = section of FD, `name "Dry Store"`. (Another live section of the soft-deleted factory FD.)
2. AF = assignment of MF to SG.

**When**
- `mgr.set_assignment(db, machine_id=MF.id, factory_id=FD.id, factory_section_id=SF.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot assign a machine to a deleted factory section"`.
4. nothing written: nothing written.
5. unchanged: unchanged(AF).
6. count: rows_of(MF) has exactly 1 row.

### MSM-SET-20 — a section of the soft-deleted factory with another factory_id gets the factory message
- **Rules:** `set_assignment` R9 (order: the R8 check comes first), R8, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. No assignment exists. (SF belongs to the soft-deleted factory FD; the call names F1.)

**When**
- `mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=SF.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Factory section does not belong to this machine's factory"`.
4. nothing written: nothing written.

### MSM-SET-21 — a section of a live but inactive factory is accepted
- **Rules:** `set_assignment` R9 (an inactive-but-live factory is not refused)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FQ = extra factory, `name "Quiet Works"`, `abbreviation "QW"`, but `is_active False`.
2. SQ = section of FQ, `name "Night Shift"`.
3. MQ = machine of FQ, `name "Planer"`.

**When**
- `result = mgr.set_assignment(db, machine_id=MQ.id, factory_id=FQ.id, factory_section_id=SQ.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == MQ.id`, `factory_section_id == SQ.id`.
3. count: rows_of(MQ) has exactly 1 row.

### MSM-SET-22 — clearing the section of a machine of the soft-deleted factory is allowed
- **Rules:** `set_assignment` R9 (clearing stays allowed), R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AF = assignment of MF to SF.

**When**
- `result = mgr.set_assignment(db, machine_id=MF.id, factory_id=FD.id, factory_section_id=None, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: rows_of(MF) has exactly 0 rows.
3. unchanged: unchanged(SF).
4. unchanged: unchanged(FD).

### MSM-SET-23 — an inactive section of a live factory is accepted like an active one
- **Rules:** `set_assignment` R9a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SI = section of F1, `name "Spare Bay"`, but `is_active False`.

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=SI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `factory_section_id == SI.id`.
3. unchanged: unchanged(SI).

### MSM-SET-24 — a soft-deleted machine is not refused
- **Rules:** `set_assignment` R10 (Q1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. No assignment exists. (MD is the soft-deleted machine of F1.)

**When**
- `result = mgr.set_assignment(db, machine_id=MD.id, factory_id=F1.id, factory_section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == MD.id`, `factory_section_id == S1.id`.
3. unchanged: unchanged(MD).

### MSM-SET-25 — a machine whose own factory differs from factory_id is not refused
- **Rules:** `set_assignment` R10 (Q1)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No assignment exists. (M1 is in F1; the call names F2 and S3 of F2.)

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F2.id, factory_section_id=S3.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == M1.id`, `factory_section_id == S3.id`.
3. unchanged: unchanged(M1).

### MSM-SET-26 — a machine of another workspace is not refused and the link is stored in the caller's workspace
- **Rules:** `set_assignment` R10 (Q1)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No assignment exists. (M9 belongs to W2.)

**When**
- `result = mgr.set_assignment(db, machine_id=M9.id, factory_id=F1.id, factory_section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `machine_id == M9.id`, `factory_section_id == S1.id`.
3. re-read the returned row: `workspace_id == W1.id`.

### MSM-SET-27 — a machine_id that is no machine fails on flush and nothing changes
- **Rules:** `set_assignment` R11 (Q1), Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. A2 = assignment of M2 to S1.

**When**
- `mgr.set_assignment(db, machine_id=MISSING, factory_id=F1.id, factory_section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machine_section_assignments_machine_id_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. unchanged: unchanged(A2).

### MSM-SET-28 — a user_id that is no profile fails on flush and the machine's previous link is back
- **Rules:** `set_assignment` R11, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=S2.id, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"machine_section_assignments_created_by_fkey" in str(exc.value.orig)`.
4. unchanged: unchanged(A1).
5. re-read A1: `factory_section_id == S1.id`, `created_by == U1.id`.
6. count: rows_of(M1) has exactly 1 row.
7. nothing written: nothing written.

### MSM-SET-29 — a machine whose link has another workspace_id hits the one-link-per-machine constraint and nothing changes
- **Rules:** `set_assignment` R11, Errors row 7
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1, but `workspace_id W2.id`. (M1 belongs to W1; the link says W2.)

**When**
- `mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=S2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, UniqueViolation)`.
3. raises: `"uq_machine_section_assignment_machine" in str(exc.value.orig)`.
4. unchanged: unchanged(A1).
5. re-read A1: `workspace_id == W2.id`, `factory_section_id == S1.id`.
6. count: rows_of(M1) has exactly 1 row.
7. nothing written: nothing written.

### MSM-SET-30 — user_id None is stored as NULL
- **Rules:** `set_assignment` R1 (Inputs: `None` is stored as `NULL`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No assignment exists.

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=S1.id, workspace_id=W1.id, user_id=None)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `created_by is None`.
3. re-read the returned row: `factory_section_id == S1.id`.

### MSM-SET-31 — a machine whose section was already read still reports the old section after a move
- **Rules:** `set_assignment` R12 (P2)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. `loaded = M1.factory_section_id` (loads M1's assignment into the session; `loaded == S1.id`).

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=S2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.factory_section_id == S2.id`.
2. returns: `M1.factory_section_id == S1.id` (read on the same M1 object, before any re-read).
3. re-read rows_of(M1)[0]: `factory_section_id == S2.id`.

### MSM-SET-32 — a machine whose section was already read still reports it after clearing
- **Rules:** `set_assignment` R12 (P2), R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. `loaded = M1.factory_section_id` (loads M1's assignment into the session; `loaded == S1.id`).

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=None, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. returns: `M1.factory_section_id == S1.id` (read on the same M1 object, before any re-read).
3. count: rows_of(M1) has exactly 0 rows.

### MSM-SET-33 — a machine read without a section still reports no section after a first set
- **Rules:** `set_assignment` R12 (P2), R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No assignment exists.
2. `loaded = M1.factory_section_id` (loads M1's empty assignment into the session; `loaded is None`).

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.factory_section_id == S1.id`.
2. returns: `M1.factory_section_id is None` (read on the same M1 object, before any re-read).
3. count: rows_of(M1) has exactly 1 row.

### MSM-SET-34 — once the machine is expired it reports the new section
- **Rules:** `set_assignment` R12 (P2)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — a step (`db.expire(M1)`) between the call and the checks

**Given**
1. A1 = assignment of M1 to S1.
2. `loaded = M1.factory_section_id` (loads M1's assignment into the session).

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=S2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.factory_section_id == S2.id`.
2. returns: after `db.expire(M1)`, `M1.factory_section_id == S2.id`.

### MSM-SET-35 — the move is flushed but not committed: a fresh SELECT sees it, a rollback undoes it
- **Rules:** `set_assignment` R13, Side effects
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. A1 = assignment of M1 to S1.
2. `a1_id = A1.id`
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=S2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.factory_section_id == S2.id`.
2. re-read rows_of(M1)[0] inside the savepoint: `id == result.id`, `factory_section_id == S2.id`.
3. count: after the savepoint rollback, rows_of(M1) has exactly 1 row.
4. re-read rows_of(M1)[0] after the savepoint rollback: `id == a1_id`, `factory_section_id == S1.id`.
5. re-read rows_of(M1)[0] after the savepoint rollback: `created_by == U1.id`.
6. mock called: the `db.commit` spy was never called.

### MSM-SET-36 — a move touches only the machine's own link
- **Rules:** `set_assignment` R13, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1. (Another machine, same section.)
3. A3 = assignment of M3 to S2. (Another machine, the target section.)

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=S2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.machine_id == M1.id`.
2. unchanged: unchanged(A2).
3. unchanged: unchanged(A3).
4. count: `machine_section_assignments` has exactly 3 rows.
5. unchanged: unchanged(M1).
6. unchanged: unchanged(S1).
7. unchanged: unchanged(S2).
8. unchanged: unchanged(F1).

### MSM-SET-37 — clearing touches only the machine's own link
- **Rules:** `set_assignment` R13, R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1. (Another machine, same section.)

**When**
- `result = mgr.set_assignment(db, machine_id=M1.id, factory_id=F1.id, factory_section_id=None, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(A2).
3. count: `machine_section_assignments` has exactly 1 row.
4. unchanged: unchanged(M1).
5. unchanged: unchanged(S1).
6. unchanged: unchanged(F1).


## `MachineSectionAssignmentManager.clear_for_section`

### MSM-CLR-01 — every link of the section is deleted and its machine ids are returned; section, machines and factory are not written
- **Rules:** `clear_for_section` R1, R4, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1.
3. A3 = assignment of M3 to S2. (A link of another section.)

**When**
- `result = mgr.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(result) == [M1.id, M2.id]`.
3. returns: `len(result) == 2`.
4. count: `machine_section_assignments` rows with `factory_section_id == S1.id`: exactly 0.
5. count: `machine_section_assignments` has exactly 1 row.
6. unchanged: unchanged(A3).
7. unchanged: unchanged(S1).
8. unchanged: unchanged(M1).
9. unchanged: unchanged(M2).
10. unchanged: unchanged(F1).

### MSM-CLR-02 — the link of a soft-deleted machine is deleted and listed too
- **Rules:** `clear_for_section` R1, R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. AD = assignment of MD to S1. (MD is the soft-deleted machine.)

**When**
- `result = mgr.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(result) == [M1.id, MD.id]`.
2. count: `machine_section_assignments` has exactly 0 rows.
3. unchanged: unchanged(MD).

### MSM-CLR-03 — the links of a soft-deleted section are deleted and the section is not written
- **Rules:** `clear_for_section` R1, R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to SX. (SX is the soft-deleted section.)

**When**
- `result = mgr.clear_for_section(db, factory_section_id=SX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == [M1.id]`.
2. count: rows_of(M1) has exactly 0 rows.
3. unchanged: unchanged(SX).

### MSM-CLR-04 — a link of another workspace pointing at the same section is not touched
- **Rules:** `clear_for_section` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A9 = assignment of M9 to S1. (M9 belongs to W2, so the link says W2; it points at S1 of W1.)

**When**
- `result = mgr.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == [M1.id]`.
2. unchanged: unchanged(A9).
3. count: `machine_section_assignments` has exactly 1 row.

### MSM-CLR-05 — the other workspace's call removes only its own link
- **Rules:** `clear_for_section` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A9 = assignment of M9 to S1. (M9 belongs to W2, so the link says W2; it points at S1 of W1.)

**When**
- `result = mgr.clear_for_section(db, factory_section_id=S1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == [M9.id]`.
2. unchanged: unchanged(A1).
3. count: rows_of(M9) has exactly 0 rows.

### MSM-CLR-06 — an unknown section id returns an empty list and writes nothing
- **Rules:** `clear_for_section` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.

**When**
- `result = mgr.clear_for_section(db, factory_section_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.
2. nothing written: nothing written.
3. unchanged: unchanged(A1).

### MSM-CLR-07 — a section without links returns an empty list and writes nothing
- **Rules:** `clear_for_section` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1. (S2 has no links.)

**When**
- `result = mgr.clear_for_section(db, factory_section_id=S2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.
2. nothing written: nothing written.
3. unchanged: unchanged(A1).

### MSM-CLR-08 — a section whose only link is in another workspace returns an empty list
- **Rules:** `clear_for_section` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A9 = assignment of M9 to S1. (The link says W2; W1 has no link to S1.)

**When**
- `result = mgr.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.
2. nothing written: nothing written.
3. unchanged: unchanged(A9).

### MSM-CLR-09 — all 10 001 links of a section are deleted and listed
- **Rules:** `clear_for_section` R3 [BUG-907]
- **Kind:** bug
- **Expect:** xfail BUG-907
- **Fails today on:** Then 3 (at most 10 000 links are handled: 10 000 ids come back and 1 link is left)
- **Author:** claude — bulk setup (10 001 machines and 10 001 assignments, bulk `insert(...)`) outside the Conventions vocabulary; the call takes about 7 s

**Given**
1. 10 001 machines N1 … N10001, bulk-inserted; machine Nk (k = 1 … 10001) is M1 but `name` = `f"Bulk {k:05d}"` (so "Bulk 00001" … "Bulk 10001"), with `is_active True`, `is_deleted False`, `is_running False`.
2. For every Nk: assignment of Nk to S1 (bulk-inserted).

**When**
- `result = mgr.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(set(result)) == len(result)`.
2. returns: `set(result) <=` the set of the 10 001 machine ids.
3. returns: `len(result) == 10001`.
4. count: `machine_section_assignments` rows with `factory_section_id == S1.id`: exactly 0.

### MSM-CLR-10 — machines whose section was already read report no section right after the call; others keep theirs
- **Rules:** `clear_for_section` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1.
3. A3 = assignment of M3 to S2.
4. `loaded1 = M1.factory_section_id` (loads M1's assignment; `loaded1 == S1.id`).
5. `loaded2 = M2.factory_section_id` (loads M2's assignment; `loaded2 == S1.id`).
6. `loaded3 = M3.factory_section_id` (loads M3's assignment; `loaded3 == S2.id`).

**When**
- `result = mgr.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(result) == [M1.id, M2.id]`.
2. returns: `M1.factory_section_id is None` (read on the same M1 object, no expire or re-read).
3. returns: `M2.factory_section_id is None` (read on the same M2 object, no expire or re-read).
4. returns: `M3.factory_section_id == S2.id` (read on the same M3 object).

### MSM-CLR-11 — a name changed in memory before the call keeps its new value
- **Rules:** `clear_for_section` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. MN = machine of F1, `name "Belt Sander"`.
2. AN = assignment of MN to S1.
3. `loaded = MN.factory_section_id` (loads MN's assignment; `loaded == S1.id`).
4. `MN.name = "Edge Trimmer"` (changed in memory, not flushed).

**When**
- `result = mgr.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == [MN.id]`.
2. returns: `MN.name == "Edge Trimmer"` (read on the same MN object).
3. returns: `MN.factory_section_id is None` (read on the same MN object).

### MSM-CLR-12 — machines not loaded in the session before the call report no section afterwards
- **Rules:** `clear_for_section` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1.
3. `m1_id, m2_id, s1_id, w1_id = M1.id, M2.id, S1.id, W1.id`
4. `db.expunge_all()` (nothing stays loaded in the session).

**When**
- `result = mgr.clear_for_section(db, factory_section_id=s1_id, workspace_id=w1_id)`.

**Then**
1. returns: `sorted(result) == [m1_id, m2_id]`.
2. returns: `all(db.get(Machine, mid) is not None for mid in result)`.
3. returns: `db.get(Machine, m1_id).factory_section_id is None`.
4. returns: `db.get(Machine, m2_id).factory_section_id is None`.

### MSM-CLR-13 — the machine ids come back in the order of the link ids
- **Rules:** `clear_for_section` R7 [BUG-906]
- **Kind:** bug
- **Expect:** xfail BUG-906 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the updated link A1 usually comes back last, giving [M1, M2, M3] — but the physical row order can match the intended order by accident)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-906")`) and an edit of a Given row before the call; the assertion is never weakened

**Given**
1. A1 = assignment of M3 to S1. (Link ids and machine ids rise in different orders.)
2. A2 = assignment of M1 to S1.
3. A3 = assignment of M2 to S1.
4. A1 is changed after A3 was created: `A1.created_by = U2.id`, then `db.flush()`. (This usually moves A1 physically behind A3 in the table.)

**When**
- `result = mgr.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(result) == [M1.id, M2.id, M3.id]`.
2. returns: `result == [M3.id, M1.id, M2.id]`.

### MSM-CLR-14 — the removal is flushed but not committed: a fresh SELECT sees no link, a rollback brings every link back
- **Rules:** `clear_for_section` R8, Side effects
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. A1 = assignment of M1 to S1.
2. A2 = assignment of M2 to S1.
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = mgr.clear_for_section(db, factory_section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(result) == [M1.id, M2.id]`.
2. count: inside the savepoint, `machine_section_assignments` rows with `factory_section_id == S1.id`: exactly 0.
3. count: after the savepoint rollback, `machine_section_assignments` rows with `factory_section_id == S1.id`: exactly 2.
4. re-read A1 after the savepoint rollback: `machine_id == M1.id`, `created_by == U1.id`.
5. mock called: the `db.commit` spy was never called.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-908 — "delete section" must stop calling `clear_for_section` and keep the links (FU-1 (a), (b)) | factory section manager spec (`delete_factory_section`) | Deleting a section keeps its assignment rows; restoring it brings the machines back. No card here: `clear_for_section` does what its name says. |
| Dead code after BUG-908 — `clear_for_section` | the change that fixes BUG-908 (`docs/testing/dead-code-removal-checklist.md`) | Delete MSM-CLR-01 … CLR-14 with the method; BUG-906 / BUG-907 xfails here go with them. |
| BUG-906 order of the query `clear_for_section` runs — strict alarm | assignment DAO cases (`tests/unit/dao/machine_section_assignment.cases.md`) | MSA-GS-22 (statement recorder: `ORDER BY` present) covers the query; this manager does not issue it itself. |
| FU-1 (c), (d) — the section manager refuses writes into a soft-deleted factory; same 404 text | factory section manager spec | No card here. |
| Q1 / FU-2 (a) — the machine checks (exists in workspace, not deleted, its factory) before `set_assignment` | machine manager spec (`create_machine`, `update_machine`) | Here the manager accepts every machine (MSM-SET-24 … SET-27). |
| P2 / FU-2 (b) — callers expire `section_assignment` after `set_assignment` | machine manager spec | Here the manager does not refresh (MSM-SET-31 … SET-34). |
| FU-2 (c), (d), (e) — every edit re-stamps the link (BUG-909); a factory change keeps an old-factory section; a machine of a deleted factory with / without a section | machine manager spec (`update_machine`) | No card here. |
| Integration-only — the 404 / 400 reaching the client as JSON; the services' commit / rollback | integration tests (`POST /machines/`, `PUT /machines/{id}/`, `DELETE /factory-sections/{id}/`) | No card here. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `set_assignment` Errors rows 5–7 | "Detail message: — (not asserted)", while the Raises column names the constraint of each violation. | Designed as a loose check, as in the DAO: the constraint name is contained in `str(exc.value.orig)` (MSM-SET-27, SET-28, SET-29). Drop those lines if the text is not meant to be asserted. |
| 2 | Facts for the test designer ("every parameter after `session` is keyword-only — a positional call raises `TypeError`") | Stated as a fact, not as a rule of either callable. | No card (same as assignment DAO gap 2). |
| 3 | `clear_for_section` R6 ("machines not yet loaded are loaded and refreshed too") | The only observable is the machine's value after the call, which a fresh load gives anyway. | MSM-CLR-12 detaches everything (`db.expunge_all()`) and checks that every returned id is an existing machine reading `None`; it cannot tell "loaded and refreshed by the manager" from "loaded by the test". |

**Coverage gaps (deliberate).** `clear_for_section` R6's `machine is None` branch is unreachable (a link's machine always exists) — no card, as the spec says. Notes "Integration-only" items are under Deferred.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `set_assignment` | Returns | MSM-SET-01, SET-03 |
| `set_assignment` | R1 | MSM-SET-01, SET-14, SET-30, SET-33 |
| `set_assignment` | R2 | MSM-SET-02 |
| `set_assignment` | R3 | MSM-SET-03, SET-04, SET-05, SET-06, SET-07, SET-22, SET-37 |
| `set_assignment` | R4 [BUG-909] | MSM-SET-08 (strict xfail); SET-09 (pass companion) |
| `set_assignment` | R5 | MSM-SET-10, SET-11, SET-12 |
| `set_assignment` | R6 | MSM-SET-13; other side SET-14 |
| `set_assignment` | R7 | MSM-SET-15, SET-16 |
| `set_assignment` | R8 | MSM-SET-17, SET-18, SET-20 |
| `set_assignment` | R9 [BUG-910] (P1) | MSM-SET-19 (strict xfail); pass cards SET-20 (other factory first), SET-21 (inactive-but-live factory), SET-22 (clearing allowed) |
| `set_assignment` | R9a | MSM-SET-23 |
| `set_assignment` | R10 (Q1) | MSM-SET-24, SET-25, SET-26 |
| `set_assignment` | R11 (Q1) | MSM-SET-27, SET-28, SET-29 |
| `set_assignment` | R12 (P2) | MSM-SET-31, SET-32, SET-33, SET-34 |
| `set_assignment` | R13 | MSM-SET-35, SET-36, SET-37 |
| `set_assignment` | Errors row 1 (404 missing / other workspace) | MSM-SET-10, SET-11, SET-12, SET-13 |
| `set_assignment` | Errors row 2 (400 deleted section) | MSM-SET-15, SET-16 |
| `set_assignment` | Errors row 3 (400 other factory) | MSM-SET-17, SET-18, SET-20 |
| `set_assignment` | Errors row 4 [BUG-910] (400 deleted factory) | MSM-SET-19 |
| `set_assignment` | Errors row 5 (unknown `machine_id`) | MSM-SET-27 |
| `set_assignment` | Errors row 6 (unknown `user_id`) | MSM-SET-28 |
| `set_assignment` | Errors row 7 (unique, link in another workspace) | MSM-SET-29 |
| `set_assignment` | Side effects (at most one delete and one insert, none on refusal, no commit, no other table) | MSM-SET-10 … SET-20 (nothing written), SET-35, SET-36, SET-37 |
| `clear_for_section` | Returns | MSM-CLR-01, CLR-06 |
| `clear_for_section` | R1 | MSM-CLR-01, CLR-02, CLR-03, CLR-04, CLR-05 |
| `clear_for_section` | R2 | MSM-CLR-06, CLR-07, CLR-08 |
| `clear_for_section` | R3 [BUG-907] | MSM-CLR-09 (strict xfail) |
| `clear_for_section` | R4 | MSM-CLR-01, CLR-02, CLR-03 |
| `clear_for_section` | R5 | MSM-CLR-10, CLR-11 |
| `clear_for_section` | R6 | MSM-CLR-12 (the `machine is None` branch: no card, unreachable) |
| `clear_for_section` | R7 [BUG-906] | MSM-CLR-13 (non-strict xfail); strict alarm MSA-GS-22 in the DAO cases |
| `clear_for_section` | R8 | MSM-CLR-14 |
| `clear_for_section` | Errors (none) | MSM-CLR-06, CLR-07, CLR-08 are the "nothing to do" paths |
| `clear_for_section` | Side effects (links deleted, machines expired, no commit, no other table) | MSM-CLR-01, CLR-10, CLR-14 |
| BUG-906 | `clear_for_section` R7 | MSM-CLR-13 |
| BUG-907 | `clear_for_section` R3 | MSM-CLR-09 |
| BUG-909 | `set_assignment` R4 | MSM-SET-08 |
| BUG-910 | `set_assignment` R9 | MSM-SET-19 |
