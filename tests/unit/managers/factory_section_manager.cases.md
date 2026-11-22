# Test cases — `app/managers/factory_section_manager.py`

> **Spec:** `tests/unit/managers/factory_section_manager.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-10-16); every answer (P1–P5, Q1–Q3 and the house-rule / reused-bug lines, BUG-911 … BUG-928) was decided by Claude under the reviewer's delegation (2026-10-16), so nothing is provisional.
> **Counts:** 207 cases · 139 expected-to-pass · 68 expected-to-fail (bugs) · 9 deferred

## Reviewer summary
- **Per callable:** `create_factory_section` 31 (10 bug) · `update_factory_section` 59 (22 bug) · `get_factory_section` 13 (6 bug) · `search_factory_sections` 66 (20 bug) · `delete_factory_section` 17 (3 bug) · `_check_name_exists_in_factory` 21 (7 bug).
- **Expected-to-fail by bug (strict unless said):** BUG-911 5 (C-24, U-57, CN-15, CN-16 non-strict; CN-17 strict, statement recorder) · BUG-912 6 · BUG-913 5 · BUG-914 2 · BUG-915 10 · BUG-916 4 · BUG-917 7 (S-53 … S-57 non-strict; S-58, S-59 strict, statement recorders) · BUG-918 5 (S-60 … S-63 non-strict; S-65 strict, recorder) · BUG-903 2 (S-64 non-strict; S-66 strict, recorder) · BUG-904 1 · BUG-908 2 · BUG-919 4 · BUG-921 3 · BUG-922 1 · BUG-923 1 · BUG-924 1 · BUG-925 2 · BUG-926 3 · BUG-927 1 · BUG-928 3.
- **Delegated answers and the cards that rest on them:** P1 / BUG-921 — S-36, S-37, S-38. P2 / BUG-922 — S-11. P3 / BUG-923 — U-24. P4 / BUG-924 — S-19 (with pass neighbours S-21, S-23, S-24). P5 / BUG-925 — G-11, G-12 (neighbour G-03). Q1 / BUG-926 — U-07, U-08, U-09 (neighbour U-10). Q2 / BUG-927 — D-13 (neighbours D-14, D-15). Q3 / BUG-928 — U-28, U-29, U-33 (neighbours U-30, U-31, U-32).
- **Notable design choices:**
  - Row order: no pass card and no strict xfail depends on the physical row order. Every card whose outcome today depends on which rows land in a page is non-strict (14 cards). Each such bug has one strict, order-independent alarm: BUG-911 CN-17, BUG-917 S-58 / S-59, BUG-918 S-65, BUG-903 S-66 — statement recorders. BUG-924 needs none (S-19 is deterministic with few rows).
  - BUG-911 has both recipes: 100 deleted then "Late" (CN-15 — also passes once BUG-905 alone is fixed) and 101 live sections (C-24, U-57, CN-16 — the cap itself). The recorder CN-17 accepts either fix shape (no `LIMIT`, or the name in the WHERE clause) — Spec gap 2.
  - BUG-908: D-07 (strict) checks that the assignment rows are kept, unchanged; D-08 (pass) that machines, factory, the other section and its assignment are untouched today; D-09 (strict) the in-memory machine.
  - "Re-created" is seen only through a new `id` and `created_by`, never `created_at`.
  - Standing rows: five factories (F1, F2, F9, FD soft-deleted, FI inactive), as in the section DAO cases; sections, machines and assignments come from each card.
  - Cards marked `Author: claude` (34): bulk setup — C-24, U-57, S-47, S-48, S-56, S-57, CN-14, CN-15, CN-16; direct insert as the When — C-25, C-26, C-27, C-28; race simulation — C-29, U-50, U-51; savepoint rollback and commit spy — C-31, U-58, D-11; statement recorder — S-58, S-59, S-65, S-66, CN-17; non-strict xfail without bulk — S-53, S-54, S-55, S-60, S-61, S-62, S-63, S-64; edit of the standing row FD — S-24; follow-up calls after the When — D-10.
- **Needs a decision:** nothing blocks a card. Worth a look: Spec gap 1 (assignment rows of another workspace and BUG-928), gap 2 (fix shape assumed by CN-17), gap 6 (backslash not in R8a).


## Conventions for this module

**IDs.** `FSM` = `app/managers/factory_section_manager.py`. `C` create_factory_section · `U` update_factory_section · `G` get_factory_section · `S` search_factory_sections · `D` delete_factory_section · `CN` _check_name_exists_in_factory.

**Actors and fixed values.**
- `M` = the singleton `factory_section_manager` (`from app.managers.factory_section_manager import FactorySectionManager, factory_section_manager`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only FSM-G-13 passes them by position). `result` = what the When call returns.
- W1, W2 = two `workspaces` rows. U1, U2 = two `profiles` rows: U1 is `created_by` of every Given row, U2 is the acting user of the calls.
- `FactorySection` = `app.models.factory_section.FactorySection`. `FactorySectionCreate`, `FactorySectionUpdate` = the schemas of `app.schemas.factory_section`. `Machine` = `app.models.machine.Machine`. `MachineSectionAssignment` = `app.models.machine_section_assignment.MachineSectionAssignment`. `HTTPException` = `fastapi.HTTPException`.
- MISSING = `999999999`: an id that no row of any table has.
- T0 = `datetime(2025, 12, 1, 8, 0, 0)` (naive). NOW = `datetime(2026, 3, 1, 10, 0, 0)` (naive).
- Text values are written as Python literals: `"\t"` is one tab, `"\n"` one newline. Copy them exactly as written, as plain strings (never raw strings).

**Externals.** In every test `app.dao.factory_section.utcnow` is patched to return NOW (the helper file does it; a card never patches anything itself, except the cards listed under Race simulations). Nothing else is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `M`) and flushed one at a time in the order written, so ids rise in that order. A card names, by column name, every column that differs from these defaults.
- These nine rows exist in every test and need no Given line: W1, W2, U1, U2 and five `factories` rows (all `created_by U1.id`):
  - F1 = `name "Main Plant"`, `abbreviation "MP"`, `workspace_id W1.id`, `is_active True`, `is_deleted False`, `deleted_at None`, `deleted_by None`.
  - F2 = the same as F1, but `name "North Yard"`, `abbreviation "NY"`. (A second live factory of W1.)
  - F9 = the same as F1, but `name "Far Depot"`, `abbreviation "FR"`, `workspace_id W2.id`. (The factory of W2.)
  - FD = the same as F1, but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. (A soft-deleted factory of W1; `is_active` stays True.)
  - FI = the same as F1, but `name "Idle Plant"`, `abbreviation "IP"`, `is_active False`. (A live but inactive factory of W1.)
- No `factory_sections`, `machines` or `machine_section_assignments` row exists unless the card's Given lists it.
- **section** = `factory_sections` row built with `FactorySection`: `workspace_id W1.id`, `factory_id F1.id`, `created_by U1.id`, `updated_by None`, `updated_at None`, `is_active True`, `is_deleted False`, `deleted_at None`, `deleted_by None`, `created_at` left to the database. The card always gives `name`; after the word "but" it lists every other column that differs. A section of W2 is always "but `factory_id F9.id`, `workspace_id W2.id`".
- **deleted** (said of a section) = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. (`is_active` stays True.)
- **machine of F** = `machines` row built with `Machine`: `workspace_id` = F's `workspace_id`, `factory_id F.id`, `is_active True`, `is_deleted False`. The card always gives `name`; after the word "but" it lists every other column that differs.
- **assignment of MA to S** = `machine_section_assignments` row built with `MachineSectionAssignment`: `workspace_id` = MA's `workspace_id`, `machine_id MA.id`, `factory_section_id S.id`, `created_by U1.id`.
- A Given line written as code (`created_before = S1.created_at`) is a step to run exactly as written, at that place in the order.

**Named checks.**
- **ids(result)** = `[s.id for s in result]` and **names(result)** = `[s.name for s in result]` — lists in the order returned (the order is part of the check). `sorted(ids(result)) == [S1.id, S2.id]` is used where the order is not part of the check; the right-hand ids are written in Given order, which is ascending id order.
- **rows_of_section(S)** = `db.expire_all()`, then SELECT every `machine_section_assignments` row with `factory_section_id == S.id` (any workspace), as a list.
- **re-read X** = `db.expire_all()`, then SELECT X by id from its own table; the listed values are database values. (Expiring discards unflushed changes, so a re-read that shows a new value also proves the change was flushed.) "the returned row" = re-read by `result.id`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line, before the call). X may be a section, a factory, a machine or an assignment.
- **nothing written** = the numbers of rows in `factory_sections`, `factories`, `machines` and `machine_section_assignments` (all workspaces) equal their values before the call.
- `count:` lines count the rows of the named table in all workspaces, with the filter stated. Assert `created_at` / `updated_at` only as `is None` / `is not None` or against a snapshot read before the call; "re-created" is seen only through a new `id` and `created_by`.
- `raises: HTTPException`: plain `with pytest.raises(HTTPException) as exc:` around the call — no `begin_nested`; keep using `db` for the remaining checks.
- `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`; `raises: DataError` = `sqlalchemy.exc.DataError`. Wrap the call for both: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. `ForeignKeyViolation`, `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause` = classes of `psycopg2.errors`.
- `raises: ValidationError` = `pydantic.ValidationError`: plain `with pytest.raises(ValidationError):` around the construction of the schema object.
- Further `raises:` lines of the same card are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**Targets.** "target `schema`" = the When only builds the schema object; `M` is not called. "target `database`" (cards marked Author: claude only) = the When inserts one row directly with `db.add(...)` and `db.flush()`; `M` is not called; an expected `IntegrityError` is wrapped as above.

**xfail cards.** Write the call and the checks exactly as shown — also when the call uses a parameter that does not exist yet (`include_deleted` on `get_factory_section`); the harness adds the marker. Every xfail in this module is strict, except the cards marked `(non-strict)` on their Expect line (`pytest.mark.xfail(strict=False, …)`): FSM-C-24, U-57, S-53, S-54, S-55, S-56, S-57, S-60, S-61, S-62, S-63, S-64, CN-15, CN-16 — each rests on the physical row order.

**Statement recorder** (cards marked Author: claude only). The SQL statements the session sends during the When are recorded; a `statement:` line is a check on the recorded text. "Its WHERE clause" = the text after the statement's first ` WHERE ` up to the next ` ORDER BY `, ` LIMIT `, ` OFFSET ` or the end, whichever comes first.

**Rolled back** (cards marked Author: claude only). `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**FD made live again** (FSM-S-24 only, Author: claude). `FD.is_deleted = False`, `FD.deleted_at = None`, `FD.deleted_by = None`, set directly on the standing row FD, then `db.flush()`.

**Race simulations** (cards marked Author: claude only). These cards patch `FactorySectionManager._check_name_exists_in_factory` to return `False`, to put the code in the state "a concurrent request already passed the Python check"; nothing else may be patched this way. The call is wrapped as `with pytest.raises(HTTPException) as exc:` then `with db.begin_nested():` then the call.
- FSM-C-29 (`create_factory_section` R9), FSM-U-50, U-51 (`update_factory_section` R15).


## `FactorySectionManager.create_factory_section`

### FSM-C-01 — create stores a section with the name, factory, workspace and creator given
- **Rules:** `create_factory_section` R1, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `result = M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, FactorySection)`.
2. returns: `result.id is not None`.
3. re-read the returned row: `name == "Paint"`, `factory_id == F1.id`.
4. re-read the returned row: `workspace_id == W1.id`.
5. re-read the returned row: `created_by == U2.id`.
6. count: `factory_sections` has exactly 1 row.

### FSM-C-02 — a new section is active, not deleted, and carries no update or deletion stamp
- **Rules:** `create_factory_section` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `result = M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `is_active is True`, `is_deleted is False`.
3. re-read the returned row: `created_at is not None`.
4. re-read the returned row: `updated_at is None`, `updated_by is None`.
5. re-read the returned row: `deleted_at is None`, `deleted_by is None`.

### FSM-C-03 — a section is created in the second workspace for that workspace's factory
- **Rules:** `create_factory_section` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.create_factory_section(db, section_data=FactorySectionCreate(name="Packing", factory_id=F9.id), workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W2.id`, `factory_id == F9.id`, `name == "Packing"`.
3. count: `factory_sections` has exactly 2 rows.
4. unchanged: unchanged(S1).

### FSM-C-04 — a factory id that no factory has is answered with 404
- **Rules:** `create_factory_section` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. nothing written: nothing written.
5. count: `factory_sections` has exactly 0 rows.

### FSM-C-05 — a factory of another workspace is answered with 404
- **Rules:** `create_factory_section` R3, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=F9.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F9.id} not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(F9).

### FSM-C-06 — factory id 0 is answered with 404
- **Rules:** `create_factory_section` R3, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 0 not found"`.
4. nothing written: nothing written.

### FSM-C-07 — a negative factory id is answered with 404
- **Rules:** `create_factory_section` R3, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=-1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID -1 not found"`.
4. nothing written: nothing written.

### FSM-C-08 — an unknown workspace id finds no factory and is answered with 404
- **Rules:** `create_factory_section` R3, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=MISSING, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F1.id} not found"`.
4. nothing written: nothing written.

### FSM-C-09 — a soft-deleted factory is answered with 400
- **Rules:** `create_factory_section` R4, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create section for deleted factory"`.
4. nothing written: nothing written.
5. unchanged: unchanged(FD).

### FSM-C-10 — a soft-deleted factory is answered with 400 also when the name is taken there
- **Rules:** `create_factory_section` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SH = section, `name "Paint"`, but `factory_id FD.id`. (A live section of the soft-deleted factory FD.)

**When**
- `M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create section for deleted factory"`.
4. count: `factory_sections` has exactly 1 row.
5. unchanged: unchanged(SH).

### FSM-C-11 — a live but inactive factory is accepted
- **Rules:** `create_factory_section` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `result = M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=FI.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `factory_id == FI.id`, `name == "Paint"`.
3. unchanged: unchanged(FI).

### FSM-C-12 — a name used by a live section of the factory is refused with 409
- **Rules:** `create_factory_section` R6, Errors row 3; `_check_name_exists_in_factory` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Paint' already exists in this factory"`.
4. nothing written: nothing written.
5. count: `factory_sections` has exactly 1 row.
6. unchanged: unchanged(S1).

### FSM-C-13 — the same name in another factory of the workspace does not block the create
- **Rules:** `create_factory_section` R7; `_check_name_exists_in_factory` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S3 = section, `name "Paint"`, but `factory_id F2.id`.

**When**
- `result = M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. returns: `result.id != S3.id`.
3. re-read the returned row: `factory_id == F1.id`, `name == "Paint"`.
4. count: `factory_sections` has exactly 2 rows.
5. unchanged: unchanged(S3).

### FSM-C-14 — the name of a soft-deleted section of the factory can be used again
- **Rules:** `create_factory_section` R7; `_check_name_exists_in_factory` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SX = section, `name "Paint"`, but deleted.

**When**
- `result = M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. returns: `result.id != SX.id`.
3. re-read the returned row: `name == "Paint"`, `is_deleted is False`, `created_by == U2.id`.
4. count: `factory_sections` has exactly 2 rows.
5. unchanged: unchanged(SX).

### FSM-C-15 — the same name in another workspace does not block the create
- **Rules:** `create_factory_section` R7; `_check_name_exists_in_factory` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S9 = section, `name "Paint"`, but `factory_id F9.id`, `workspace_id W2.id`.

**When**
- `result = M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `factory_id == F1.id`, `name == "Paint"`.
3. count: `factory_sections` has exactly 2 rows.
4. unchanged: unchanged(S9).

### FSM-C-16 — the name is stored trimmed
- **Rules:** `create_factory_section` R8 [BUG-915]
- **Kind:** bug
- **Expect:** xfail BUG-915
- **Fails today on:** Then 2 (the name is stored as typed, with the outer spaces)

**Given**
1. No sections exist.

**When**
- `result = M.create_factory_section(db, section_data=FactorySectionCreate(name="  Paint ", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`. The name has two spaces before and one space after.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name == "Paint"`.

### FSM-C-17 — inner whitespace and case of the name are kept
- **Rules:** `create_factory_section` R1, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `result = M.create_factory_section(db, section_data=FactorySectionCreate(name="spray  BAY", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`. The name has two spaces between the words and none outside.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name == "spray  BAY"`.

### FSM-C-18 — an empty name is rejected by FactorySectionCreate
- **Rules:** `create_factory_section` R8 [BUG-915], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-915
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. No sections exist.

**When**
- `FactorySectionCreate(name="", factory_id=F1.id)` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. count: `factory_sections` has exactly 0 rows.

### FSM-C-19 — a name of three spaces is rejected by FactorySectionCreate
- **Rules:** `create_factory_section` R8 [BUG-915], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-915
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. No sections exist.

**When**
- `FactorySectionCreate(name="   ", factory_id=F1.id)` (target `schema`; M is not called). The name is `"   "` (three spaces).

**Then**
1. raises: `ValidationError`.
2. count: `factory_sections` has exactly 0 rows.

### FSM-C-20 — a name of one tab is rejected by FactorySectionCreate
- **Rules:** `create_factory_section` R8 [BUG-915], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-915
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. No sections exist.

**When**
- `FactorySectionCreate(name="\t", factory_id=F1.id)` (target `schema`; M is not called). The name is the Python literal `"\t"` (one tab character).

**Then**
1. raises: `ValidationError`.
2. count: `factory_sections` has exactly 0 rows.

### FSM-C-21 — a one-character name is accepted by FactorySectionCreate
- **Rules:** `create_factory_section` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `result = FactorySectionCreate(name="a", factory_id=F1.id)` (target `schema`; M is not called).

**Then**
1. returns: `result.name == "a"`.
2. returns: `result.factory_id == F1.id`.

### FSM-C-22 — a name that differs only in case from a live section's name is refused with 409
- **Rules:** `create_factory_section` R6, Errors row 3; `_check_name_exists_in_factory` R4 [BUG-912]
- **Kind:** bug
- **Expect:** xfail BUG-912
- **Fails today on:** Then 1 (no error is raised: names are compared exactly, so a second section is created)

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.create_factory_section(db, section_data=FactorySectionCreate(name="paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'paint' already exists in this factory"`.
4. count: `factory_sections` has exactly 1 row.
5. unchanged: unchanged(S1).

### FSM-C-23 — a name that differs only by a trailing space is refused with 409 and the trimmed name in the message
- **Rules:** `create_factory_section` R6, R8 [BUG-915]; `_check_name_exists_in_factory` R4 [BUG-912]
- **Kind:** bug
- **Expect:** xfail BUG-915
- **Fails today on:** Then 1 (no error is raised: the name is neither trimmed nor compared trimmed, so a second section is created)

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint ", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`. The name ends with one space.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Paint' already exists in this factory"`.
4. count: `factory_sections` has exactly 1 row.
5. unchanged: unchanged(S1).

### FSM-C-24 — a duplicate name is refused also when its live owner is the 101st live section of the factory
- **Rules:** `create_factory_section` R6; `_check_name_exists_in_factory` R5 [BUG-911]
- **Kind:** bug
- **Expect:** xfail BUG-911 (non-strict)
- **Fails today on:** Then 1 (only 100 sections of the factory are examined; when L is not among them — the usual case, L being inserted last — no error is raised and a second "Late" is created; the physical row order can put L among them, hence non-strict)
- **Author:** claude — bulk setup (a loop over 100 sections) and a non-strict xfail

**Given**
1. 100 sections B1 … B100, inserted in that order; section Bk (k = 1 … 100) has `name` = `f"Bay {k:03d}"` (so "Bay 001" … "Bay 100") and is live.
2. L = section, `name "Late"`. (Live; the 101st live section of F1.)

**When**
- `M.create_factory_section(db, section_data=FactorySectionCreate(name="Late", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Late' already exists in this factory"`.
4. count: `factory_sections` has exactly 101 rows.

### FSM-C-25 — the database refuses a second live section with the same name in one factory
- **Rules:** `create_factory_section` R9 [BUG-913]
- **Kind:** bug
- **Expect:** xfail BUG-913
- **Fails today on:** Then 1 (no error is raised: the table has no unique index, so the row is saved)
- **Author:** claude — target `database`: the When is a direct insert, not a manager call

**Given**
1. S1 = section, `name "Paint"`.

**When**
- insert directly (target `database`; M is not called): `db.add(FactorySection(workspace_id=W1.id, factory_id=F1.id, name="Paint", created_by=U1.id))`, then `db.flush()`.

**Then**
1. raises: `IntegrityError` on flush.
2. count: `factory_sections` has exactly 1 row.

### FSM-C-26 — the database refuses a second live section whose name differs only in case and outer spaces
- **Rules:** `create_factory_section` R9 [BUG-913]
- **Kind:** bug
- **Expect:** xfail BUG-913
- **Fails today on:** Then 1 (no error is raised: the table has no unique index, so the row is saved)
- **Author:** claude — target `database`: the When is a direct insert, not a manager call

**Given**
1. S1 = section, `name "Paint"`.

**When**
- insert directly (target `database`; M is not called): `db.add(FactorySection(workspace_id=W1.id, factory_id=F1.id, name="PAINT ", created_by=U1.id))`, then `db.flush()`. The name ends with one space.

**Then**
1. raises: `IntegrityError` on flush.
2. count: `factory_sections` has exactly 1 row.

### FSM-C-27 — the database accepts a soft-deleted section with the name of a live one
- **Rules:** `create_factory_section` R9
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — target `database`: the When is a direct insert, not a manager call

**Given**
1. S1 = section, `name "Paint"`.

**When**
- insert directly (target `database`; M is not called): `db.add(FactorySection(workspace_id=W1.id, factory_id=F1.id, name="Paint", created_by=U1.id, is_deleted=True, deleted_at=T0, deleted_by=U1.id))`, then `db.flush()`.

**Then**
1. count: `factory_sections` has exactly 2 rows.
2. unchanged: unchanged(S1).

### FSM-C-28 — the database accepts a live section of another factory with the same name
- **Rules:** `create_factory_section` R9
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — target `database`: the When is a direct insert, not a manager call

**Given**
1. S1 = section, `name "Paint"`.

**When**
- insert directly (target `database`; M is not called): `db.add(FactorySection(workspace_id=W1.id, factory_id=F2.id, name="Paint", created_by=U1.id))`, then `db.flush()`.

**Then**
1. count: `factory_sections` has exactly 2 rows.
2. unchanged: unchanged(S1).

### FSM-C-29 — a duplicate name that passed the Python check is answered with 409, not a database error
- **Rules:** `create_factory_section` R9 [BUG-913], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-913
- **Fails today on:** Then 1 (no error is raised: the table has no unique index, so the duplicate is saved)
- **Author:** claude — race simulation (patches the manager's own duplicate check) and a savepoint around the call

**Given**
1. S1 = section, `name "Paint"`.
2. Race simulation: `FactorySectionManager._check_name_exists_in_factory` is patched to return `False` (Conventions, Race simulations).

**When**
- `M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`. The call is wrapped in `db.begin_nested()`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Paint' already exists in this factory"`.
4. count: `factory_sections` has exactly 1 row.
5. unchanged: unchanged(S1).

### FSM-C-30 — a user_id that is no profile id fails on flush and no section is saved
- **Rules:** `create_factory_section` R10, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"factory_sections_created_by_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. count: `factory_sections` has exactly 0 rows.

### FSM-C-31 — the create is flushed but not committed: a rollback removes the section
- **Rules:** `create_factory_section` Returns, Side effects
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. No sections exist.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. count: `factory_sections` has exactly 1 row.
2. count after the savepoint rollback: `factory_sections` has exactly 0 rows.
3. mock called: the `db.commit` spy was never called.


## `FactorySectionManager.update_factory_section`

### FSM-U-01 — a new name is stored and the editor is recorded
- **Rules:** `update_factory_section` R4, R11, R13, R14, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Spray"`.
3. re-read S1: `factory_id == F1.id`.
4. re-read S1: `updated_by == U2.id`.
5. re-read S1: `updated_at is not None`.
6. count: `factory_sections` has exactly 1 row.

### FSM-U-02 — an id that no section has is answered with 404
- **Rules:** `update_factory_section` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.update_factory_section(db, section_id=MISSING, section_data=FactorySectionUpdate(name="Spray"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory section with ID 999999999 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(S1).

### FSM-U-03 — a section of another workspace is answered with 404 and not changed
- **Rules:** `update_factory_section` R2, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.

**When**
- `M.update_factory_section(db, section_id=S9.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory section with ID {S9.id} not found"`.
4. unchanged: unchanged(S9).
5. re-read S9: `name == "Packing"`, `updated_by is None`.

### FSM-U-04 — a soft-deleted section is answered with 400 and not changed
- **Rules:** `update_factory_section` R3, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SX = section, `name "Old Line"`, but deleted.

**When**
- `M.update_factory_section(db, section_id=SX.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted factory section"`.
4. unchanged: unchanged(SX).
5. nothing written: nothing written.

### FSM-U-05 — a soft-deleted section is answered with 400 also when the requested name is taken
- **Rules:** `update_factory_section` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SX = section, `name "Old Line"`, but deleted.
2. S2 = section, `name "Paint"`.

**When**
- `M.update_factory_section(db, section_id=SX.id, section_data=FactorySectionUpdate(name="Paint"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted factory section"`.
4. unchanged: unchanged(SX).
5. unchanged: unchanged(S2).

### FSM-U-06 — a soft-deleted section is answered with 400 also when it is moved to a soft-deleted factory
- **Rules:** `update_factory_section` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SX = section, `name "Old Line"`, but deleted.

**When**
- `M.update_factory_section(db, section_id=SX.id, section_data=FactorySectionUpdate(factory_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted factory section"`.
4. unchanged: unchanged(SX).

### FSM-U-07 — a section of a soft-deleted factory cannot be renamed
- **Rules:** `update_factory_section` R3a [BUG-926], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-926
- **Fails today on:** Then 1 (no error is raised: the section's factory is not looked at, so the rename is saved)

**Given**
1. SH = section, `name "Paint"`, but `factory_id FD.id`. (A live section of the soft-deleted factory FD.)

**When**
- `M.update_factory_section(db, section_id=SH.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted factory section"`.
4. unchanged: unchanged(SH).
5. re-read SH: `name == "Paint"`, `updated_by is None`.

### FSM-U-08 — a section of a soft-deleted factory is refused also when its own factory id is sent
- **Rules:** `update_factory_section` R3a [BUG-926]
- **Kind:** bug
- **Expect:** xfail BUG-926
- **Fails today on:** Then 1 (no error is raised: the same factory id is not checked and the call succeeds)

**Given**
1. SH = section, `name "Paint"`, but `factory_id FD.id`. (A live section of the soft-deleted factory FD.)

**When**
- `M.update_factory_section(db, section_id=SH.id, section_data=FactorySectionUpdate(factory_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted factory section"`.
4. unchanged: unchanged(SH).

### FSM-U-09 — a section of a soft-deleted factory cannot be moved out to a live factory
- **Rules:** `update_factory_section` R3a [BUG-926]
- **Kind:** bug
- **Expect:** xfail BUG-926
- **Fails today on:** Then 1 (no error is raised: the move to F1 is saved)

**Given**
1. SH = section, `name "Paint"`, but `factory_id FD.id`. (A live section of the soft-deleted factory FD.)

**When**
- `M.update_factory_section(db, section_id=SH.id, section_data=FactorySectionUpdate(factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted factory section"`.
4. unchanged: unchanged(SH).
5. re-read SH: `factory_id == FD.id`.

### FSM-U-10 — a section of a live but inactive factory is renamed
- **Rules:** `update_factory_section` R3a (the side that holds today), R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SF = section, `name "Paint"`, but `factory_id FI.id`.

**When**
- `result = M.update_factory_section(db, section_id=SF.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is SF` (the very object that was looked up).
2. re-read SF: `name == "Spray"`, `factory_id == FI.id`.
3. re-read SF: `updated_by == U2.id`.

### FSM-U-11 — sending the current name without a move is accepted and the name stays
- **Rules:** `update_factory_section` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Paint"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Paint"`, `factory_id == F1.id`.
3. count: `factory_sections` has exactly 1 row.

### FSM-U-12 — changing only the case of the section's own name is stored
- **Rules:** `update_factory_section` R5; `_check_name_exists_in_factory` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="PAINT"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "PAINT"`.
3. re-read S1: `updated_by == U2.id`.
4. unchanged: unchanged(S2).

### FSM-U-13 — a name used by another live section of the factory is refused with 409
- **Rules:** `update_factory_section` R6, Errors row 6; `_check_name_exists_in_factory` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.

**When**
- `M.update_factory_section(db, section_id=S2.id, section_data=FactorySectionUpdate(name="Paint"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Paint' already exists in this factory"`.
4. unchanged: unchanged(S2).
5. re-read S2: `name == "Welding"`.
6. unchanged: unchanged(S1).
7. nothing written: nothing written.

### FSM-U-14 — a new name taken in the target factory refuses the move with 409 and the factory stays
- **Rules:** `update_factory_section` R6, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S3 = section, `name "Welding"`, but `factory_id F2.id`.

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Welding", factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Welding' already exists in this factory"`.
4. unchanged: unchanged(S1).
5. re-read S1: `name == "Paint"`, `factory_id == F1.id`.
6. unchanged: unchanged(S3).

### FSM-U-15 — a name used only in the old factory does not block a move with that new name
- **Rules:** `update_factory_section` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Welding", factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Welding"`, `factory_id == F2.id`.
3. unchanged: unchanged(S2).

### FSM-U-16 — a name used in another factory can be taken by a rename without a move
- **Rules:** `update_factory_section` R16
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S3 = section, `name "Welding"`, but `factory_id F2.id`.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Welding"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Welding"`, `factory_id == F1.id`.
3. unchanged: unchanged(S3).

### FSM-U-17 — a section without machines is moved to another live factory
- **Rules:** `update_factory_section` R7, R10 (the side that holds today), R14
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `factory_id == F2.id`.
3. re-read S1: `name == "Paint"`.
4. re-read S1: `updated_by == U2.id`.
5. unchanged: unchanged(F1).
6. unchanged: unchanged(F2).

### FSM-U-18 — a move to a factory id that no factory has is answered with 404
- **Rules:** `update_factory_section` R7, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(factory_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. unchanged: unchanged(S1).
5. nothing written: nothing written.

### FSM-U-19 — a move to a factory of another workspace is answered with 404
- **Rules:** `update_factory_section` R7, Errors row 3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(factory_id=F9.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F9.id} not found"`.
4. unchanged: unchanged(S1).
5. re-read S1: `factory_id == F1.id`.

### FSM-U-20 — a move to a negative factory id is answered with 404
- **Rules:** `update_factory_section` R7, Errors row 3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(factory_id=-1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID -1 not found"`.
4. unchanged: unchanged(S1).

### FSM-U-21 — a move to a live but inactive factory is accepted
- **Rules:** `update_factory_section` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(factory_id=FI.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `factory_id == FI.id`.

### FSM-U-22 — a move to a soft-deleted factory is answered with 400
- **Rules:** `update_factory_section` R8, Errors row 4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(factory_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot move section to deleted factory"`.
4. unchanged: unchanged(S1).
5. nothing written: nothing written.

### FSM-U-23 — a move to a soft-deleted factory is answered with 400 also when the new name is taken there
- **Rules:** `update_factory_section` R8
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. SH = section, `name "Welding"`, but `factory_id FD.id`.

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Welding", factory_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot move section to deleted factory"`.
4. unchanged: unchanged(S1).
5. unchanged: unchanged(SH).

### FSM-U-24 — factory id 0 is checked like any id and answered with 404
- **Rules:** `update_factory_section` R8a [BUG-923], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-923
- **Fails today on:** Then 1 (the call raises IntegrityError: `0` skips the factory check, is written, and the flush fails on the foreign key)

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(factory_id=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 0 not found"`.
4. unchanged: unchanged(S1).

### FSM-U-25 — a plain move into a factory where the name is taken is refused with 409
- **Rules:** `update_factory_section` R9 [BUG-914], Errors row 6
- **Kind:** bug
- **Expect:** xfail BUG-914
- **Fails today on:** Then 1 (no error is raised: a move without a different name is never checked, so F2 ends with two live "Paint")

**Given**
1. S1 = section, `name "Paint"`.
2. S3 = section, `name "Paint"`, but `factory_id F2.id`.

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Paint' already exists in this factory"`.
4. re-read S1: `factory_id == F1.id`.
5. unchanged: unchanged(S3).

### FSM-U-26 — a move that re-sends the current name into a factory where it is taken is refused with 409
- **Rules:** `update_factory_section` R9 [BUG-914], Errors row 6
- **Kind:** bug
- **Expect:** xfail BUG-914
- **Fails today on:** Then 1 (no error is raised: the name equals the current one, so it is not checked, and the move is saved)

**Given**
1. S1 = section, `name "Paint"`.
2. S3 = section, `name "Paint"`, but `factory_id F2.id`.

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Paint", factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Paint' already exists in this factory"`.
4. re-read S1: `factory_id == F1.id`.
5. unchanged: unchanged(S3).

### FSM-U-27 — a move into a factory where the name belongs only to a soft-deleted section is accepted
- **Rules:** `update_factory_section` R9 (the side that holds today), R16
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. SX3 = section, `name "Paint"`, but `factory_id F2.id`, deleted.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `factory_id == F2.id`, `name == "Paint"`.
3. unchanged: unchanged(SX3).

### FSM-U-28 — a section with an assigned machine cannot be moved to another factory
- **Rules:** `update_factory_section` R10 [BUG-928], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-928
- **Fails today on:** Then 1 (no error is raised: the move is saved and the machine of F1 is linked to a section of F2)

**Given**
1. S1 = section, `name "Paint"`.
2. MA1 = machine of F1, `name "Lathe"`.
3. A1 = assignment of MA1 to S1.

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot move a section that has machines assigned"`.
4. re-read S1: `factory_id == F1.id`.
5. unchanged: unchanged(A1).

### FSM-U-29 — the assignment of a soft-deleted machine also blocks the move
- **Rules:** `update_factory_section` R10 [BUG-928]
- **Kind:** bug
- **Expect:** xfail BUG-928
- **Fails today on:** Then 1 (no error is raised: the move is saved)

**Given**
1. S1 = section, `name "Paint"`.
2. MD = machine of F1, `name "Old Saw"`, but `is_deleted True`.
3. A1 = assignment of MD to S1.

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot move a section that has machines assigned"`.
4. re-read S1: `factory_id == F1.id`.
5. unchanged: unchanged(A1).

### FSM-U-30 — a section with an assigned machine is renamed and its assignment is left as it was
- **Rules:** `update_factory_section` R10 (rename not affected), R14
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. MA1 = machine of F1, `name "Lathe"`.
3. A1 = assignment of MA1 to S1.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Spray"`, `factory_id == F1.id`.
3. unchanged: unchanged(A1).
4. count: rows_of_section(S1) has exactly 1 row.
5. unchanged: unchanged(MA1).

### FSM-U-31 — a section with an assigned machine moved to a soft-deleted factory gets the "deleted factory" message
- **Rules:** `update_factory_section` R8, R10 (checked after R8)
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. MA1 = machine of F1, `name "Lathe"`.
3. A1 = assignment of MA1 to S1.

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(factory_id=FD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot move section to deleted factory"`.
4. unchanged: unchanged(S1).
5. unchanged: unchanged(A1).

### FSM-U-32 — a section with an assigned machine moved to an unknown factory gets 404
- **Rules:** `update_factory_section` R7, R10 (checked after R7)
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. MA1 = machine of F1, `name "Lathe"`.
3. A1 = assignment of MA1 to S1.

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(factory_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. unchanged: unchanged(S1).
5. unchanged: unchanged(A1).

### FSM-U-33 — the machine refusal comes before the name check of the target factory
- **Rules:** `update_factory_section` R10 [BUG-928] (checked before R9)
- **Kind:** bug
- **Expect:** xfail BUG-928
- **Fails today on:** Then 1 (no error is raised: the move is saved)

**Given**
1. S1 = section, `name "Paint"`.
2. S3 = section, `name "Paint"`, but `factory_id F2.id`.
3. MA1 = machine of F1, `name "Lathe"`.
4. A1 = assignment of MA1 to S1.

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot move a section that has machines assigned"`.
4. re-read S1: `factory_id == F1.id`.

### FSM-U-34 — an explicit null name is left unchanged while the factory is changed
- **Rules:** `update_factory_section` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name=None, factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Paint"`.
3. re-read S1: `factory_id == F2.id`.

### FSM-U-35 — an explicit null factory id is left unchanged while the name is changed
- **Rules:** `update_factory_section` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Spray", factory_id=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Spray"`.
3. re-read S1: `factory_id == F1.id`.

### FSM-U-36 — the current factory id sent with a new name keeps the factory
- **Rules:** `update_factory_section` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Spray", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Spray"`, `factory_id == F1.id`.

### FSM-U-37 — a sent name is stored trimmed
- **Rules:** `update_factory_section` R12 [BUG-915]
- **Kind:** bug
- **Expect:** xfail BUG-915
- **Fails today on:** Then 2 (the name is stored as typed, with the outer spaces)

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name=" Spray "), workspace_id=W1.id, user_id=U2.id)`. The name has one space before and one space after.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Spray"`.

### FSM-U-38 — the current name sent with outer spaces counts as the current name
- **Rules:** `update_factory_section` R12 [BUG-915], R5
- **Kind:** bug
- **Expect:** xfail BUG-915
- **Fails today on:** Then 2 (the name is overwritten with the untrimmed text)

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name=" Paint "), workspace_id=W1.id, user_id=U2.id)`. The name has one space before and one space after.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Paint"`.

### FSM-U-39 — an empty name is rejected by FactorySectionUpdate
- **Rules:** `update_factory_section` R12 [BUG-915], Errors row 7
- **Kind:** bug
- **Expect:** xfail BUG-915
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `FactorySectionUpdate(name="")` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(S1).

### FSM-U-40 — a name of three spaces is rejected by FactorySectionUpdate
- **Rules:** `update_factory_section` R12 [BUG-915], Errors row 7
- **Kind:** bug
- **Expect:** xfail BUG-915
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `FactorySectionUpdate(name="   ")` (target `schema`; M is not called). The name is `"   "` (three spaces).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(S1).

### FSM-U-41 — a one-character name is accepted by FactorySectionUpdate
- **Rules:** `update_factory_section` R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `result = FactorySectionUpdate(name="a")` (target `schema`; M is not called).

**Then**
1. returns: `result.name == "a"`.
2. returns: `result.factory_id is None`.

### FSM-U-42 — FactorySectionUpdate without fields has name None and factory_id None
- **Rules:** `update_factory_section` Inputs, R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `result = FactorySectionUpdate()` (target `schema`; M is not called).

**Then**
1. returns: `result.name is None`.
2. returns: `result.factory_id is None`.

### FSM-U-43 — an empty request does not stamp updated_by
- **Rules:** `update_factory_section` R13 [BUG-919]
- **Kind:** bug
- **Expect:** xfail BUG-919
- **Fails today on:** Then 3 (`updated_by` is stamped on every successful call)

**Given**
1. S1 = section, `name "Paint"`.
2. `db.refresh(S1)`

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(), workspace_id=W1.id, user_id=U2.id)`. No field is sent.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Paint"`, `factory_id == F1.id`.
3. re-read S1: `updated_by is None`.
4. re-read S1: `updated_at is None`.

### FSM-U-44 — a request with only null fields does not stamp updated_by
- **Rules:** `update_factory_section` R13 [BUG-919]
- **Kind:** bug
- **Expect:** xfail BUG-919
- **Fails today on:** Then 3 (`updated_by` is stamped on every successful call)

**Given**
1. S1 = section, `name "Paint"`.
2. `db.refresh(S1)`

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name=None, factory_id=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Paint"`, `factory_id == F1.id`.
3. re-read S1: `updated_by is None`.
4. re-read S1: `updated_at is None`.

### FSM-U-45 — a request with the current values does not stamp updated_by
- **Rules:** `update_factory_section` R13 [BUG-919]
- **Kind:** bug
- **Expect:** xfail BUG-919
- **Fails today on:** Then 3 (`updated_by` is stamped on every successful call)

**Given**
1. S1 = section, `name "Paint"`.
2. `db.refresh(S1)`

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Paint"`, `factory_id == F1.id`.
3. re-read S1: `updated_by is None`.
4. re-read S1: `updated_at is None`.

### FSM-U-46 — an empty request keeps the previous updated_by
- **Rules:** `update_factory_section` R13 [BUG-919]
- **Kind:** bug
- **Expect:** xfail BUG-919
- **Fails today on:** Then 2 (`updated_by` is overwritten with the acting user U2)

**Given**
1. S1 = section, `name "Paint"`, but `updated_by U1.id`.
2. `db.refresh(S1)`

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(), workspace_id=W1.id, user_id=U2.id)`. No field is sent.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `updated_by == U1.id`.
3. re-read S1: `updated_at is None`.

### FSM-U-47 — an empty request succeeds and leaves name and factory as they are
- **Rules:** `update_factory_section` R11, R13 (the side that holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(), workspace_id=W1.id, user_id=U2.id)`. No field is sent.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Paint"`, `factory_id == F1.id`.
3. count: `factory_sections` has exactly 1 row.

### FSM-U-48 — a real change replaces a previous updated_by with the acting user
- **Rules:** `update_factory_section` R13
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`, but `updated_by U1.id`.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Spray"`.
3. re-read S1: `updated_by == U2.id`.

### FSM-U-49 — nothing but the name and the update stamp is modified by a rename
- **Rules:** `update_factory_section` R14
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.
3. MA1 = machine of F1, `name "Lathe"`.
4. A1 = assignment of MA1 to S2.
5. `created_before = S1.created_at`

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `workspace_id == W1.id`, `created_by == U1.id`, `created_at == created_before`.
3. re-read S1: `is_active is True`, `is_deleted is False`.
4. re-read S1: `deleted_at is None`, `deleted_by is None`.
5. unchanged: unchanged(S2).
6. unchanged: unchanged(A1).
7. unchanged: unchanged(MA1).
8. unchanged: unchanged(F1).

### FSM-U-50 — a rename to a taken name that passed the Python check is answered with 409, not a database error
- **Rules:** `update_factory_section` R15 [BUG-913], Errors row 6
- **Kind:** bug
- **Expect:** xfail BUG-913
- **Fails today on:** Then 1 (no error is raised: the table has no unique index, so the duplicate rename is saved)
- **Author:** claude — race simulation (patches the manager's own duplicate check) and a savepoint around the call

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.
3. Race simulation: `FactorySectionManager._check_name_exists_in_factory` is patched to return `False` (Conventions, Race simulations).

**When**
- `M.update_factory_section(db, section_id=S2.id, section_data=FactorySectionUpdate(name="Paint"), workspace_id=W1.id, user_id=U2.id)`. The call is wrapped in `db.begin_nested()`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Paint' already exists in this factory"`.
4. re-read S2: `name == "Welding"`.
5. unchanged: unchanged(S1).

### FSM-U-51 — a move whose name is taken in the target and passed the Python check is answered with 409
- **Rules:** `update_factory_section` R15 [BUG-913], Errors row 6
- **Kind:** bug
- **Expect:** xfail BUG-913
- **Fails today on:** Then 1 (no error is raised: the table has no unique index, so F2 ends with two live "Paint")
- **Author:** claude — race simulation (patches the manager's own duplicate check) and a savepoint around the call

**Given**
1. S1 = section, `name "Paint"`.
2. S3 = section, `name "Paint"`, but `factory_id F2.id`.
3. Race simulation: `FactorySectionManager._check_name_exists_in_factory` is patched to return `False` (Conventions, Race simulations).

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(factory_id=F2.id), workspace_id=W1.id, user_id=U2.id)`. The call is wrapped in `db.begin_nested()`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Paint' already exists in this factory"`.
4. re-read S1: `factory_id == F1.id`.
5. unchanged: unchanged(S3).

### FSM-U-52 — the name of a soft-deleted section of the factory can be taken by a rename
- **Rules:** `update_factory_section` R16
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. SX = section, `name "Old Line"`, but deleted.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Old Line"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Old Line"`.
3. unchanged: unchanged(SX).

### FSM-U-53 — the name of a section of another workspace can be taken by a rename
- **Rules:** `update_factory_section` R16
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.

**When**
- `result = M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Packing"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Packing"`.
3. unchanged: unchanged(S9).

### FSM-U-54 — a rename by a user_id that is no profile id fails on flush and nothing is saved
- **Rules:** `update_factory_section` R17, Errors row 8
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"factory_sections_updated_by_fkey" in str(exc.value.orig)`.
4. re-read S1: `name == "Paint"`.
5. re-read S1: `updated_by is None`.

### FSM-U-55 — a new name that differs only in case from another live section's name is refused with 409
- **Rules:** `update_factory_section` R6, Errors row 6; `_check_name_exists_in_factory` R4 [BUG-912]
- **Kind:** bug
- **Expect:** xfail BUG-912
- **Fails today on:** Then 1 (no error is raised: names are compared exactly, so the rename is saved)

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.

**When**
- `M.update_factory_section(db, section_id=S2.id, section_data=FactorySectionUpdate(name="paint"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'paint' already exists in this factory"`.
4. re-read S2: `name == "Welding"`.
5. unchanged: unchanged(S1).

### FSM-U-56 — a new name that differs only by a trailing space is refused with 409 and the trimmed name in the message
- **Rules:** `update_factory_section` R6, R12 [BUG-915]; `_check_name_exists_in_factory` R4 [BUG-912]
- **Kind:** bug
- **Expect:** xfail BUG-915
- **Fails today on:** Then 1 (no error is raised: the name is neither trimmed nor compared trimmed, so the rename is saved)

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.

**When**
- `M.update_factory_section(db, section_id=S2.id, section_data=FactorySectionUpdate(name="Paint "), workspace_id=W1.id, user_id=U2.id)`. The name ends with one space.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Paint' already exists in this factory"`.
4. re-read S2: `name == "Welding"`.
5. unchanged: unchanged(S1).

### FSM-U-57 — a rename to a taken name is refused also when its live owner is the 101st live section of the factory
- **Rules:** `update_factory_section` R6; `_check_name_exists_in_factory` R5 [BUG-911]
- **Kind:** bug
- **Expect:** xfail BUG-911 (non-strict)
- **Fails today on:** Then 1 (only 100 sections of the factory are examined; when L is not among them — the usual case — no error is raised and the rename is saved; the physical row order can put L among them, hence non-strict)
- **Author:** claude — bulk setup (a loop over 100 sections) and a non-strict xfail

**Given**
1. 100 sections B1 … B100, inserted in that order; section Bk (k = 1 … 100) has `name` = `f"Bay {k:03d}"` (so "Bay 001" … "Bay 100") and is live.
2. L = section, `name "Late"`. (Live; the 101st live section of F1.)
3. S2 = section, `name "Welding"`. (Live; the 102nd.)

**When**
- `M.update_factory_section(db, section_id=S2.id, section_data=FactorySectionUpdate(name="Late"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Section with name 'Late' already exists in this factory"`.
4. re-read S2: `name == "Welding"`.

### FSM-U-58 — the update is flushed but not committed: a rollback brings the old name back
- **Rules:** `update_factory_section` Returns, Side effects
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. S1 = section, `name "Paint"`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read S1: `name == "Spray"`.
2. re-read S1 after the savepoint rollback: `name == "Paint"`.
3. re-read S1 after the savepoint rollback: `updated_by is None`.
4. mock called: the `db.commit` spy was never called.

### FSM-U-59 — a section of the second workspace is renamed from its own workspace
- **Rules:** `update_factory_section` R2, R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.

**When**
- `result = M.update_factory_section(db, section_id=S9.id, section_data=FactorySectionUpdate(name="Boxing"), workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. returns: `result is S9` (the very object that was looked up).
2. re-read S9: `name == "Boxing"`, `factory_id == F9.id`.
3. unchanged: unchanged(S1).


## `FactorySectionManager.get_factory_section`

### FSM-G-01 — a live section of the workspace is returned and nothing is changed
- **Rules:** `get_factory_section` R1, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.get_factory_section(db, section_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, FactorySection)`.
2. returns: `result.id == S1.id`.
3. returns: `result.name == "Paint"`, `result.factory_id == F1.id`.
4. unchanged: unchanged(S1).
5. nothing written: nothing written.

### FSM-G-02 — a live section with is_active False is returned
- **Rules:** `get_factory_section` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SI = section, `name "Idle Bay"`, but `is_active False`. (Still `is_deleted False`.)

**When**
- `result = M.get_factory_section(db, section_id=SI.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == SI.id`.
2. returns: `result.is_active is False`.

### FSM-G-03 — a section of a live but inactive factory is returned
- **Rules:** `get_factory_section` R1, R5 (inactive factory hides nothing)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SF = section, `name "Paint"`, but `factory_id FI.id`.

**When**
- `result = M.get_factory_section(db, section_id=SF.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == SF.id`.
2. returns: `result.factory_id == FI.id`.

### FSM-G-04 — an id that no section has is answered with 404
- **Rules:** `get_factory_section` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.get_factory_section(db, section_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory section with ID 999999999 not found"`.
4. nothing written: nothing written.

### FSM-G-05 — a section of another workspace is answered with 404
- **Rules:** `get_factory_section` R2, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.

**When**
- `M.get_factory_section(db, section_id=S9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory section with ID {S9.id} not found"`.
4. unchanged: unchanged(S9).

### FSM-G-06 — a section of the second workspace is returned to its own workspace
- **Rules:** `get_factory_section` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.

**When**
- `result = M.get_factory_section(db, section_id=S9.id, workspace_id=W2.id)`.

**Then**
1. returns: `result.id == S9.id`.
2. returns: `result.workspace_id == W2.id`.

### FSM-G-07 — a soft-deleted section is answered with 404 by default
- **Rules:** `get_factory_section` R3 [BUG-916], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-916
- **Fails today on:** Then 1 (no error is raised: the deleted section is returned like a live one)

**Given**
1. SX = section, `name "Old Line"`, but deleted.

**When**
- `M.get_factory_section(db, section_id=SX.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory section with ID {SX.id} not found"`.
4. unchanged: unchanged(SX).

### FSM-G-08 — include_deleted=True returns a soft-deleted section of the workspace
- **Rules:** `get_factory_section` R4 [BUG-916]
- **Kind:** bug
- **Expect:** xfail BUG-916
- **Fails today on:** Then 1 (the call raises TypeError: the parameter `include_deleted` does not exist yet)

**Given**
1. SX = section, `name "Old Line"`, but deleted.

**When**
- `result = M.get_factory_section(db, section_id=SX.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == SX.id`.
2. returns: `result.is_deleted is True`.

### FSM-G-09 — include_deleted=True still answers 404 for a soft-deleted section of another workspace
- **Rules:** `get_factory_section` R4 [BUG-916]
- **Kind:** bug
- **Expect:** xfail BUG-916
- **Fails today on:** Then 1 (the call raises TypeError: the parameter `include_deleted` does not exist yet)

**Given**
1. SX9 = section, `name "Old Bin"`, but `factory_id F9.id`, `workspace_id W2.id`, deleted.

**When**
- `M.get_factory_section(db, section_id=SX9.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory section with ID {SX9.id} not found"`.

### FSM-G-10 — include_deleted=True returns a live section as well
- **Rules:** `get_factory_section` R4 [BUG-916], R1
- **Kind:** bug
- **Expect:** xfail BUG-916
- **Fails today on:** Then 1 (the call raises TypeError: the parameter `include_deleted` does not exist yet)

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.get_factory_section(db, section_id=S1.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == S1.id`.
2. returns: `result.is_deleted is False`.

### FSM-G-11 — a live section of a soft-deleted factory is answered with 404 by default
- **Rules:** `get_factory_section` R5 [BUG-925], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-925
- **Fails today on:** Then 1 (no error is raised: the factory is not looked at and the section is returned)

**Given**
1. SH = section, `name "Paint"`, but `factory_id FD.id`. (A live section of the soft-deleted factory FD.)

**When**
- `M.get_factory_section(db, section_id=SH.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory section with ID {SH.id} not found"`.
4. unchanged: unchanged(SH).

### FSM-G-12 — include_deleted=True returns a live section of a soft-deleted factory
- **Rules:** `get_factory_section` R5 [BUG-925]
- **Kind:** bug
- **Expect:** xfail BUG-925
- **Fails today on:** Then 1 (the call raises TypeError: the parameter `include_deleted` does not exist yet)

**Given**
1. SH = section, `name "Paint"`, but `factory_id FD.id`. (A live section of the soft-deleted factory FD.)

**When**
- `result = M.get_factory_section(db, section_id=SH.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == SH.id`.
2. returns: `result.factory_id == FD.id`.

### FSM-G-13 — the id and workspace can be passed by position, as the service does
- **Rules:** `get_factory_section` R1; Facts (positional call by the service)
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.get_factory_section(db, S1.id, W1.id)`.

**Then**
1. returns: `result.id == S1.id`.


## `FactorySectionManager.search_factory_sections`

### FSM-S-01 — without a factory every section of the workspace is returned as a list
- **Rules:** `search_factory_sections` R1, R9 (`search=None`)
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.
3. S3 = section, `name "Cutting"`, but `factory_id F2.id`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [S1.id, S2.id, S3.id]`.
3. returns: `isinstance(result[0], FactorySection)`.

### FSM-S-02 — a section of another workspace is not listed
- **Rules:** `search_factory_sections` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### FSM-S-03 — a call for the second workspace lists only that workspace's section
- **Rules:** `search_factory_sections` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [S9.id]`.

### FSM-S-04 — an unknown workspace id returns an empty list
- **Rules:** `search_factory_sections` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### FSM-S-05 — a live section with is_active False is listed
- **Rules:** `search_factory_sections` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. SI = section, `name "Idle Bay"`, but `is_active False`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, SI.id]`.

### FSM-S-06 — with a factory only that factory's sections are returned
- **Rules:** `search_factory_sections` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S3 = section, `name "Cutting"`, but `factory_id F2.id`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### FSM-S-07 — a call for the other factory returns only its section
- **Rules:** `search_factory_sections` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S3 = section, `name "Cutting"`, but `factory_id F2.id`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=F2.id)`.

**Then**
1. returns: `ids(result) == [S3.id]`.

### FSM-S-08 — an unknown factory id returns an empty list
- **Rules:** `search_factory_sections` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=MISSING)`.

**Then**
1. returns: `result == []`.

### FSM-S-09 — a negative factory id returns an empty list
- **Rules:** `search_factory_sections` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=-1)`.

**Then**
1. returns: `result == []`.

### FSM-S-10 — a factory of another workspace returns an empty list
- **Rules:** `search_factory_sections` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=F9.id)`.

**Then**
1. returns: `result == []`.

### FSM-S-11 — factory id 0 filters like any id and returns an empty list
- **Rules:** `search_factory_sections` R2a [BUG-922]
- **Kind:** bug
- **Expect:** xfail BUG-922
- **Fails today on:** Then 1 (`0` is taken as "no factory", so both sections of the workspace are listed)

**Given**
1. S1 = section, `name "Paint"`.
2. S3 = section, `name "Cutting"`, but `factory_id F2.id`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=0)`.

**Then**
1. returns: `result == []`.

### FSM-S-12 — without a factory a soft-deleted section is not listed and the call changes nothing
- **Rules:** `search_factory_sections` R5, Side effects
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. SX = section, `name "Old Line"`, but deleted.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.
2. unchanged: unchanged(SX).
3. nothing written: nothing written.

### FSM-S-13 — with a factory a soft-deleted section is not listed
- **Rules:** `search_factory_sections` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. SX = section, `name "Old Line"`, but deleted.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### FSM-S-14 — a workspace whose only section is soft-deleted returns an empty list
- **Rules:** `search_factory_sections` R5, R11
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SX = section, `name "Old Line"`, but deleted.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FSM-S-15 — include_deleted=True without a factory lists soft-deleted sections along with live ones
- **Rules:** `search_factory_sections` R6 [BUG-920] (the manager part, holds today)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. SX = section, `name "Old Line"`, but deleted.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, SX.id]`.

### FSM-S-16 — include_deleted=True with a factory lists its soft-deleted sections along with live ones
- **Rules:** `search_factory_sections` R6 [BUG-920] (the manager part, holds today)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. SX = section, `name "Old Line"`, but deleted.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=F1.id, include_deleted=True)`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, SX.id]`.

### FSM-S-17 — include_deleted=True does not list a soft-deleted section of another workspace
- **Rules:** `search_factory_sections` R6, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. SX9 = section, `name "Old Bin"`, but `factory_id F9.id`, `workspace_id W2.id`, deleted.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### FSM-S-18 — an explicit include_deleted=False hides the soft-deleted section
- **Rules:** `search_factory_sections` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. SX = section, `name "Old Line"`, but deleted.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, include_deleted=False)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### FSM-S-19 — without a factory the live section of a soft-deleted factory is hidden
- **Rules:** `search_factory_sections` R7 [BUG-924] (P4)
- **Kind:** bug
- **Expect:** xfail BUG-924
- **Fails today on:** Then 2 (the factory is not looked at; SH of the soft-deleted factory FD is listed too)

**Given**
1. S1 = section, `name "Paint"`.
2. SH = section, `name "Cutting"`, but `factory_id FD.id`. (A live section of the soft-deleted factory FD.)

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `S1.id in ids(result)`.
2. returns: `ids(result) == [S1.id]`.
3. unchanged: unchanged(SH).

### FSM-S-20 — with the soft-deleted factory as filter its live section is hidden
- **Rules:** `search_factory_sections` R7 [BUG-904]
- **Kind:** bug
- **Expect:** xfail BUG-904
- **Fails today on:** Then 1 (the factory is not looked at; SH is returned)

**Given**
1. SH = section, `name "Cutting"`, but `factory_id FD.id`. (A live section of the soft-deleted factory FD.)

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=FD.id)`.

**Then**
1. returns: `result == []`.
2. unchanged: unchanged(SH).

### FSM-S-21 — include_deleted=True without a factory lists the section of a soft-deleted factory
- **Rules:** `search_factory_sections` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. SH = section, `name "Cutting"`, but `factory_id FD.id`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, SH.id]`.

### FSM-S-22 — include_deleted=True with the soft-deleted factory as filter lists its section
- **Rules:** `search_factory_sections` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SH = section, `name "Cutting"`, but `factory_id FD.id`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=FD.id, include_deleted=True)`.

**Then**
1. returns: `ids(result) == [SH.id]`.

### FSM-S-23 — the section of a live but inactive factory is listed
- **Rules:** `search_factory_sections` R7 (an inactive factory hides nothing)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. SF = section, `name "Cutting"`, but `factory_id FI.id`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, SF.id]`.

### FSM-S-24 — once its factory is no longer deleted the section is listed again, unchanged
- **Rules:** `search_factory_sections` R7 (rows untouched, listed again)
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — changes the standing row FD directly, with a snapshot taken before that step

**Given**
1. SH = section, `name "Cutting"`, but `factory_id FD.id`.
2. BEFORE = every column of SH, taken now.
3. FD made live again (Conventions). Nothing is done to SH.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [SH.id]`.
2. unchanged: after re-read, every column of SH equals its value in BEFORE.

### FSM-S-25 — the search ignores case and finds the text in the names of two factories' sections
- **Rules:** `search_factory_sections` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = section, `name "Main Hall"`.
2. S2 = section, `name "Paint"`.
3. S3 = section, `name "Side hall"`, but `factory_id F2.id`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search="HALL")`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, S3.id]`.

### FSM-S-26 — the search finds text in the middle of a name
- **Rules:** `search_factory_sections` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Main Hall"`.
2. S2 = section, `name "Cutting"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search="utt")`.

**Then**
1. returns: `ids(result) == [S2.id]`.

### FSM-S-27 — the factory's name is not searched
- **Rules:** `search_factory_sections` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Cutting"`. (Its factory F1 is "Main Plant".)
2. S2 = section, `name "Welding"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search="plant")`.

**Then**
1. returns: `result == []`.

### FSM-S-28 — two inner spaces in the search text do not match a name with one space
- **Rules:** `search_factory_sections` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Main Hall"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search="main  hall")`. The text has two spaces between the words.

**Then**
1. returns: `result == []`.

### FSM-S-29 — one inner space in the search text matches the space inside a name
- **Rules:** `search_factory_sections` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Main Hall"`.
2. S2 = section, `name "Paint"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search="n h")`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### FSM-S-30 — a percent sign in the search text matches only a percent sign
- **Rules:** `search_factory_sections` R8a (HR-8)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "50% zone"`.
2. S2 = section, `name "Paint"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search="%")`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### FSM-S-31 — a percent sign finds nothing when no section contains one
- **Rules:** `search_factory_sections` R8a (HR-8)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search="%")`.

**Then**
1. returns: `result == []`.

### FSM-S-32 — an underscore in the search text matches only an underscore
- **Rules:** `search_factory_sections` R8a (HR-8)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Bay_2"`.
2. S2 = section, `name "Paint"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search="_")`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### FSM-S-33 — the search combines with the factory filter
- **Rules:** `search_factory_sections` R2, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = section, `name "Main Hall"`.
2. S3 = section, `name "Side hall"`, but `factory_id F2.id`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=F2.id, search="hall")`.

**Then**
1. returns: `ids(result) == [S3.id]`.

### FSM-S-34 — search=None applies no search filter
- **Rules:** `search_factory_sections` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Main Hall"`.
2. S2 = section, `name "Paint"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search=None)`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, S2.id]`.

### FSM-S-35 — an empty search text applies no search filter
- **Rules:** `search_factory_sections` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Main Hall"`.
2. S2 = section, `name "Paint"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search="")`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, S2.id]`.

### FSM-S-36 — a search of three spaces applies no search filter
- **Rules:** `search_factory_sections` R9 [BUG-921] (P1)
- **Kind:** bug
- **Expect:** xfail BUG-921
- **Fails today on:** Then 1 (the text is used as typed; no name contains three spaces, so the list is empty)

**Given**
1. S1 = section, `name "Main Hall"`.
2. S2 = section, `name "Paint"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search="   ")`. The text is three spaces.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, S2.id]`.

### FSM-S-37 — a search of one tab applies no search filter
- **Rules:** `search_factory_sections` R9 [BUG-921] (P1)
- **Kind:** bug
- **Expect:** xfail BUG-921
- **Fails today on:** Then 1 (the text is used as typed; no name contains a tab, so the list is empty)

**Given**
1. S1 = section, `name "Main Hall"`.
2. S2 = section, `name "Paint"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search="\t")`. The text is the Python literal `"\t"` (one tab).

**Then**
1. returns: `sorted(ids(result)) == [S1.id, S2.id]`.

### FSM-S-38 — spaces around the search text are removed before matching
- **Rules:** `search_factory_sections` R9 [BUG-921] (P1)
- **Kind:** bug
- **Expect:** xfail BUG-921
- **Fails today on:** Then 1 (the text is used untrimmed; no name contains " hall " with the trailing space, so the list is empty)

**Given**
1. S1 = section, `name "Main Hall"`.
2. S2 = section, `name "Paint"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search=" hall ")`. The text has one space before and one space after.

**Then**
1. returns: `ids(result) == [S1.id]`.

### FSM-S-39 — a matching soft-deleted section is not returned by a search
- **Rules:** `search_factory_sections` R10
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = section, `name "Main Hall"`.
2. SX = section, `name "Old Hall"`, but deleted.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search="hall")`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### FSM-S-40 — a matching soft-deleted section is returned by a search with include_deleted=True
- **Rules:** `search_factory_sections` R10, R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = section, `name "Main Hall"`.
2. SX = section, `name "Old Hall"`, but deleted.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search="hall", include_deleted=True)`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, SX.id]`.

### FSM-S-41 — a workspace without sections returns an empty list
- **Rules:** `search_factory_sections` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FSM-S-42 — skip equal to the number of sections returns an empty list
- **Rules:** `search_factory_sections` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### FSM-S-43 — skip past the number of sections returns an empty list
- **Rules:** `search_factory_sections` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, skip=5)`.

**Then**
1. returns: `result == []`.

### FSM-S-44 — skip 1 of two sections returns one of them
- **Rules:** `search_factory_sections` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `set(ids(result)) <= {S1.id, S2.id}`.

### FSM-S-45 — limit 1 of two sections returns one of them
- **Rules:** `search_factory_sections` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=F1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `set(ids(result)) <= {S1.id, S2.id}`.

### FSM-S-46 — limit 0 returns an empty list
- **Rules:** `search_factory_sections` R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### FSM-S-47 — without a factory the default limit returns exactly 100 of 101 live sections
- **Rules:** `search_factory_sections` R11
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 sections) outside the Conventions vocabulary

**Given**
1. 101 sections B1 … B101, inserted in that order; section Bk (k = 1 … 101) has `name` = `f"Bay {k:03d}"` (so "Bay 001" … "Bay 101") and is live.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len(set(ids(result))) == 100`.
3. returns: `set(ids(result)) <= {B1.id, …, B101.id}` (the set of all 101 ids).

### FSM-S-48 — with a factory the default limit returns exactly 100 of 101 live sections
- **Rules:** `search_factory_sections` R11
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 101 sections) outside the Conventions vocabulary

**Given**
1. 101 sections B1 … B101, inserted in that order; section Bk (k = 1 … 101) has `name` = `f"Bay {k:03d}"` (so "Bay 001" … "Bay 101") and is live.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len(set(ids(result))) == 100`.
3. returns: `set(ids(result)) <= {B1.id, …, B101.id}` (the set of all 101 ids).

### FSM-S-49 — without a factory a negative limit is rejected by the database
- **Rules:** `search_factory_sections` R11, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.search_factory_sections(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### FSM-S-50 — with a factory a negative limit is rejected by the database
- **Rules:** `search_factory_sections` R11, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.search_factory_sections(db, workspace_id=W1.id, factory_id=F1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### FSM-S-51 — without a factory a negative skip is rejected by the database
- **Rules:** `search_factory_sections` R11, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.search_factory_sections(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### FSM-S-52 — with a factory a negative skip is rejected by the database
- **Rules:** `search_factory_sections` R11, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.search_factory_sections(db, workspace_id=W1.id, factory_id=F1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### FSM-S-53 — a soft-deleted section does not use up a place in the page
- **Rules:** `search_factory_sections` R3 [BUG-917], R5 [BUG-917]
- **Kind:** bug
- **Expect:** xfail BUG-917 (non-strict)
- **Fails today on:** Then 1 (when the deleted SX is among the first two rows of the physical order — the usual case — it is dropped after the page was cut, so only one section comes back; not guaranteed, hence non-strict)
- **Author:** claude — non-strict xfail (which rows form today's page depends on the physical row order)

**Given**
1. SX = section, `name "Old Line"`, but deleted. (Inserted first.)
2. S2 = section, `name "Paint"`.
3. S3 = section, `name "Welding"`, but `factory_id F2.id`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `sorted(ids(result)) == [S2.id, S3.id]`.

### FSM-S-54 — a search finds a matching section that lies outside the first page of rows
- **Rules:** `search_factory_sections` R3 [BUG-917], R8
- **Kind:** bug
- **Expect:** xfail BUG-917 (non-strict)
- **Fails today on:** Then 1 (only two rows are loaded and searched; when S3 is not among them — the usual case — the list is empty; not guaranteed, hence non-strict)
- **Author:** claude — non-strict xfail (which rows form today's page depends on the physical row order)

**Given**
1. S1 = section, `name "Cutting"`.
2. S2 = section, `name "Paint"`.
3. S3 = section, `name "Main Hall"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search="hall", limit=2)`.

**Then**
1. returns: `ids(result) == [S3.id]`.

### FSM-S-55 — skip counts live sections only
- **Rules:** `search_factory_sections` R3 [BUG-917], R5 [BUG-917]
- **Kind:** bug
- **Expect:** xfail BUG-917 (non-strict)
- **Fails today on:** Then 1 (when the deleted row is the one skipped — the usual case — both live sections come back; not guaranteed, hence non-strict)
- **Author:** claude — non-strict xfail (which rows form today's page depends on the physical row order)

**Given**
1. SX = section, `name "Old Line"`, but deleted. (Inserted first.)
2. S2 = section, `name "Paint"`.
3. S3 = section, `name "Welding"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=F1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `set(ids(result)) <= {S2.id, S3.id}`.

### FSM-S-56 — with a factory the default list shows a live section that comes after 100 deleted ones
- **Rules:** `search_factory_sections` R3 [BUG-917], R5 [BUG-917]
- **Kind:** bug
- **Expect:** xfail BUG-917 (non-strict)
- **Fails today on:** Then 1 (the first 100 rows of the physical order — usually the 100 deleted ones — are loaded and dropped, so the list is empty; not guaranteed, hence non-strict; this card also passes once BUG-905 alone is fixed)
- **Author:** claude — bulk setup (a loop over 100 sections) and a non-strict xfail

**Given**
1. 100 deleted sections D1 … D100, inserted in that order; section Dk (k = 1 … 100) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 100") and is deleted.
2. L = section, `name "Late"`. (Live; row number 101 of F1.)

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `ids(result) == [L.id]`.

### FSM-S-57 — without a factory a search finds a live section that comes after 100 deleted ones
- **Rules:** `search_factory_sections` R3 [BUG-917], R5 [BUG-917], R8
- **Kind:** bug
- **Expect:** xfail BUG-917 (non-strict)
- **Fails today on:** Then 1 (the first 100 rows of the physical order — usually the 100 deleted ones — are loaded and dropped, so the list is empty; not guaranteed, hence non-strict)
- **Author:** claude — bulk setup (a loop over 100 sections) and a non-strict xfail

**Given**
1. 100 deleted sections D1 … D100, inserted in that order; section Dk (k = 1 … 100) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 100") and is deleted.
2. L = section, `name "Late"`. (Live; row number 101 of W1.)

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, search="late")`.

**Then**
1. returns: `ids(result) == [L.id]`.

### FSM-S-58 — without a factory the list query leaves out soft-deleted sections in the database, before the page
- **Rules:** `search_factory_sections` R3 [BUG-917], R5 [BUG-917]
- **Kind:** bug
- **Expect:** xfail BUG-917
- **Fails today on:** Then 2 (the workspace query has no `is_deleted` condition; deleted rows are dropped in Python after the page was cut)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order)

**Given**
1. S1 = section, `name "Paint"`.
2. SX = section, `name "Old Line"`, but deleted.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.
2. statement: of the `SELECT` statements sent that read `factory_sections`, at least one has `factory_sections.is_deleted` in its WHERE clause.

### FSM-S-59 — with a factory the search text is a condition of the query, before the page
- **Rules:** `search_factory_sections` R3 [BUG-917], R8
- **Kind:** bug
- **Expect:** xfail BUG-917
- **Fails today on:** Then 2 (the search is applied in Python after the page was cut; no query has a `LIKE`)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order)

**Given**
1. S1 = section, `name "Main Hall"`.
2. S2 = section, `name "Paint"`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=F1.id, search="hall")`.

**Then**
1. returns: `ids(result) == [S1.id]`.
2. statement: of the `SELECT` statements sent that read `factory_sections`, at least one has `LIKE` (in any case; `ILIKE` counts) in its WHERE clause.

### FSM-S-60 — without a factory the list is ordered by name ignoring case
- **Rules:** `search_factory_sections` R4 [BUG-918]
- **Kind:** bug
- **Expect:** xfail BUG-918 (non-strict)
- **Fails today on:** Then 1 (no order is requested, so the rows come back in physical row order, which can match the intended order by accident — non-strict)
- **Author:** claude — non-strict xfail (physical row order can match the intended order by accident)

**Given**
1. S1 = section, `name "Delta"`.
2. S2 = section, `name "alpha"`, but `factory_id F2.id`.
3. S3 = section, `name "echo"`.
4. S4 = section, `name "Bravo"`, but `factory_id F2.id`.
5. S5 = section, `name "charlie"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["alpha", "Bravo", "charlie", "Delta", "echo"]`.

### FSM-S-61 — without a factory names equal ignoring case come back in id order
- **Rules:** `search_factory_sections` R4 [BUG-918]
- **Kind:** bug
- **Expect:** xfail BUG-918 (non-strict)
- **Fails today on:** Then 1 (no order is requested; the physical order puts "Zinc Room" first — usually — but can match by accident, hence non-strict)
- **Author:** claude — non-strict xfail (physical row order can match the intended order by accident)

**Given**
1. S1 = section, `name "Zinc Room"`.
2. S2 = section, `name "paint"`, but `factory_id F2.id`.
3. S3 = section, `name "Paint"`.
4. S4 = section, `name "Assembly"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S4.id, S2.id, S3.id, S1.id]`.

### FSM-S-62 — deleted sections are ordered together with live ones
- **Rules:** `search_factory_sections` R4 [BUG-918], R6
- **Kind:** bug
- **Expect:** xfail BUG-918 (non-strict)
- **Fails today on:** Then 1 (no order is requested, so the rows come back in physical row order — non-strict)
- **Author:** claude — non-strict xfail (physical row order can match the intended order by accident)

**Given**
1. S1 = section, `name "Zinc Room"`.
2. SX = section, `name "Mango"`, but deleted.
3. S3 = section, `name "apple"`.
4. S4 = section, `name "mango"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `ids(result) == [S3.id, SX.id, S4.id, S1.id]`.

### FSM-S-63 — without a factory a middle page holds the second and third section by name
- **Rules:** `search_factory_sections` R4 [BUG-918], R11
- **Kind:** bug
- **Expect:** xfail BUG-918 (non-strict)
- **Fails today on:** Then 1 (no order is requested, so the page is cut from the physical row order — non-strict)
- **Author:** claude — non-strict xfail (physical row order can match the intended order by accident)

**Given**
1. S1 = section, `name "Delta"`.
2. S2 = section, `name "alpha"`, but `factory_id F2.id`.
3. S3 = section, `name "echo"`.
4. S4 = section, `name "Bravo"`, but `factory_id F2.id`.
5. S5 = section, `name "charlie"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `names(result) == ["Bravo", "charlie"]`.

### FSM-S-64 — with a factory the list is ordered by name ignoring case
- **Rules:** `search_factory_sections` R4 [BUG-903]
- **Kind:** bug
- **Expect:** xfail BUG-903 (non-strict)
- **Fails today on:** Then 1 (no order is requested, so the rows come back in physical row order — non-strict)
- **Author:** claude — non-strict xfail (physical row order can match the intended order by accident)

**Given**
1. S1 = section, `name "Delta"`.
2. S2 = section, `name "alpha"`.
3. S3 = section, `name "echo"`.
4. S4 = section, `name "Bravo"`.
5. S5 = section, `name "charlie"`.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `names(result) == ["alpha", "Bravo", "charlie", "Delta", "echo"]`.

### FSM-S-65 — without a factory the list query asks the database for a name order
- **Rules:** `search_factory_sections` R4 [BUG-918]
- **Kind:** bug
- **Expect:** xfail BUG-918
- **Fails today on:** Then 2 (no `SELECT` on `factory_sections` has an `ORDER BY` that mentions `name`)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order)

**Given**
1. S1 = section, `name "Paint"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.
2. statement: of the `SELECT` statements sent that read `factory_sections`, at least one has an `ORDER BY` whose text (after `ORDER BY`) contains `name`.

### FSM-S-66 — with a factory the list query asks the database for a name order
- **Rules:** `search_factory_sections` R4 [BUG-903]
- **Kind:** bug
- **Expect:** xfail BUG-903
- **Fails today on:** Then 2 (no `SELECT` on `factory_sections` has an `ORDER BY`)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order)

**Given**
1. S1 = section, `name "Paint"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = M.search_factory_sections(db, workspace_id=W1.id, factory_id=F1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.
2. statement: of the `SELECT` statements sent that read `factory_sections`, at least one has an `ORDER BY` whose text (after `ORDER BY`) contains `name`.


## `FactorySectionManager.delete_factory_section`

### FSM-D-01 — a live section is marked deleted with the clock value and the acting user
- **Rules:** `delete_factory_section` R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M.delete_factory_section(db, section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `is_deleted is True`.
3. re-read S1: `deleted_at == NOW`.
4. re-read S1: `deleted_by == U2.id`.
5. count: `factory_sections` has exactly 1 row.

### FSM-D-02 — no other column of the section is changed by the delete
- **Rules:** `delete_factory_section` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`, but `updated_by U1.id`.
2. `created_before = S1.created_at`

**When**
- `result = M.delete_factory_section(db, section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `name == "Paint"`, `factory_id == F1.id`.
3. re-read S1: `workspace_id == W1.id`, `created_by == U1.id`.
4. re-read S1: `updated_by == U1.id`.
5. re-read S1: `created_at == created_before`.
6. re-read S1: `is_active is True`.
7. re-read S1: `updated_at is not None`.

### FSM-D-03 — a live section with is_active False is deleted and stays inactive
- **Rules:** `delete_factory_section` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SI = section, `name "Idle Bay"`, but `is_active False`.

**When**
- `result = M.delete_factory_section(db, section_id=SI.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is SI` (the very object that was looked up).
2. re-read SI: `is_deleted is True`.
3. re-read SI: `is_active is False`.

### FSM-D-04 — an id that no section has is answered with 404
- **Rules:** `delete_factory_section` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.delete_factory_section(db, section_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory section with ID 999999999 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(S1).

### FSM-D-05 — a section of another workspace is answered with 404 and not deleted
- **Rules:** `delete_factory_section` R1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.

**When**
- `M.delete_factory_section(db, section_id=S9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory section with ID {S9.id} not found"`.
4. unchanged: unchanged(S9).
5. re-read S9: `is_deleted is False`, `deleted_at is None`.

### FSM-D-06 — an already deleted section is answered with 400 and keeps its deletion stamp
- **Rules:** `delete_factory_section` R2, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SX = section, `name "Old Line"`, but deleted.

**When**
- `M.delete_factory_section(db, section_id=SX.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Factory section is already deleted"`.
4. unchanged: unchanged(SX).
5. re-read SX: `deleted_at == T0`.
6. re-read SX: `deleted_by == U1.id`.
7. nothing written: nothing written.

### FSM-D-07 — the machine assignments of the deleted section are kept
- **Rules:** `delete_factory_section` R5 [BUG-908], R5a [BUG-908]
- **Kind:** bug
- **Expect:** xfail BUG-908
- **Fails today on:** Then 3 (every assignment row of the section is deleted with it)

**Given**
1. S1 = section, `name "Paint"`.
2. MA1 = machine of F1, `name "Lathe"`.
3. MA2 = machine of F1, `name "Press"`.
4. A1 = assignment of MA1 to S1.
5. A2 = assignment of MA2 to S1.

**When**
- `result = M.delete_factory_section(db, section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `is_deleted is True`.
3. count: rows_of_section(S1) has exactly 2 rows.
4. unchanged: unchanged(A1).
5. re-read A1: `machine_id == MA1.id`, `factory_section_id == S1.id`, `created_by == U1.id`.
6. unchanged: unchanged(A2).

### FSM-D-08 — a section with assigned machines is deleted; machines, factory and the other section are untouched
- **Rules:** `delete_factory_section` R5 (the side that holds today), R6, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.
3. MA1 = machine of F1, `name "Lathe"`.
4. MA2 = machine of F1, `name "Press"`.
5. A1 = assignment of MA1 to S1.
6. A3 = assignment of MA2 to S2.

**When**
- `result = M.delete_factory_section(db, section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `is_deleted is True`, `deleted_by == U2.id`.
3. unchanged: unchanged(MA1).
4. unchanged: unchanged(MA2).
5. unchanged: unchanged(F1).
6. unchanged: unchanged(S2).
7. unchanged: unchanged(A3).
8. count: `machines` has exactly 2 rows.

### FSM-D-09 — a machine whose section was read before the delete still reports that section
- **Rules:** `delete_factory_section` R5b [BUG-908]
- **Kind:** bug
- **Expect:** xfail BUG-908
- **Fails today on:** Then 2 (the manager deletes the link and refreshes the machine, so its section reads `None`)

**Given**
1. S1 = section, `name "Paint"`.
2. MA1 = machine of F1, `name "Lathe"`.
3. A1 = assignment of MA1 to S1.
4. `loaded_section_id = MA1.factory_section_id`

**When**
- `result = M.delete_factory_section(db, section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. returns: read on the object, without expiring anything first: `MA1.factory_section_id == S1.id`.

### FSM-D-10 — after the delete the section leaves the default list, its name is free, and update and delete answer 400
- **Rules:** `delete_factory_section` R7; `search_factory_sections` R5, R6; `create_factory_section` R7; `update_factory_section` R3
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — follow-up manager calls after the When call, two of them expected to raise

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.

**When**
- `result = M.delete_factory_section(db, section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. returns: after the call, `ids(M.search_factory_sections(db, workspace_id=W1.id)) == [S2.id]`.
3. returns: after the call, `sorted(ids(M.search_factory_sections(db, workspace_id=W1.id, include_deleted=True))) == [S1.id, S2.id]`.
4. returns: after that, `new = M.create_factory_section(db, section_data=FactorySectionCreate(name="Paint", factory_id=F1.id), workspace_id=W1.id, user_id=U2.id)` gives `new.id != S1.id`.
5. raises: after that, `M.update_factory_section(db, section_id=S1.id, section_data=FactorySectionUpdate(name="Spray"), workspace_id=W1.id, user_id=U2.id)` raises `HTTPException` with `exc.value.detail == "Cannot update deleted factory section"`.
6. raises: after that, `M.delete_factory_section(db, section_id=S1.id, workspace_id=W1.id, user_id=U2.id)` raises `HTTPException` with `exc.value.detail == "Factory section is already deleted"`.

### FSM-D-11 — the delete is flushed but not committed: a rollback makes the section live again
- **Rules:** `delete_factory_section` R8, Returns
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. S1 = section, `name "Paint"`.
2. MA1 = machine of F1, `name "Lathe"`.
3. A1 = assignment of MA1 to S1.
4. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = M.delete_factory_section(db, section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `is_deleted is True`.
3. re-read S1 after the savepoint rollback: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
4. count after the savepoint rollback: rows_of_section(S1) has exactly 1 row.
5. mock called: the `db.commit` spy was never called.

### FSM-D-12 — a user_id that is no profile id fails on flush and the section stays live
- **Rules:** `delete_factory_section` R9, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `M.delete_factory_section(db, section_id=S1.id, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"factory_sections_deleted_by_fkey" in str(exc.value.orig)`.
4. re-read S1: `is_deleted is False`.
5. re-read S1: `deleted_at is None`, `deleted_by is None`.

### FSM-D-13 — a live section of a soft-deleted factory cannot be deleted
- **Rules:** `delete_factory_section` R10 [BUG-927], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-927
- **Fails today on:** Then 1 (no error is raised: the factory is not looked at and the section is deleted)

**Given**
1. SH = section, `name "Paint"`, but `factory_id FD.id`. (A live section of the soft-deleted factory FD.)

**When**
- `M.delete_factory_section(db, section_id=SH.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot delete a section of a deleted factory"`.
4. unchanged: unchanged(SH).
5. re-read SH: `is_deleted is False`.

### FSM-D-14 — a section of a live but inactive factory is deleted
- **Rules:** `delete_factory_section` R10 (an inactive factory is not refused), R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SF = section, `name "Paint"`, but `factory_id FI.id`.

**When**
- `result = M.delete_factory_section(db, section_id=SF.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is SF` (the very object that was looked up).
2. re-read SF: `is_deleted is True`, `deleted_by == U2.id`.

### FSM-D-15 — an already deleted section of a soft-deleted factory gets the "already deleted" message
- **Rules:** `delete_factory_section` R2, R10 (checked after R2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SXH = section, `name "Old Line"`, but `factory_id FD.id`, deleted.

**When**
- `M.delete_factory_section(db, section_id=SXH.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Factory section is already deleted"`.
4. unchanged: unchanged(SXH).

### FSM-D-16 — only that section row is touched
- **Rules:** `delete_factory_section` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.

**When**
- `result = M.delete_factory_section(db, section_id=S1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is S1` (the very object that was looked up).
2. re-read S1: `is_deleted is True`.
3. unchanged: unchanged(S2).
4. unchanged: unchanged(F1).
5. count: `factory_sections` has exactly 2 rows.

### FSM-D-17 — a section of the second workspace is deleted from its own workspace
- **Rules:** `delete_factory_section` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.

**When**
- `result = M.delete_factory_section(db, section_id=S9.id, workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. returns: `result is S9` (the very object that was looked up).
2. re-read S9: `is_deleted is True`, `deleted_at == NOW`, `deleted_by == U2.id`.
3. unchanged: unchanged(S1).


## `FactorySectionManager._check_name_exists_in_factory`

### FSM-CN-01 — a live section of the factory with that name gives True and nothing is changed
- **Rules:** `_check_name_exists_in_factory` R1, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Paint")`.

**Then**
1. returns: `result is True`.
2. unchanged: unchanged(S1).
3. nothing written: nothing written.

### FSM-CN-02 — a name that no section of the factory has gives False
- **Rules:** `_check_name_exists_in_factory` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Welding")`.

**Then**
1. returns: `result is False`.

### FSM-CN-03 — a section of another factory with that name is not considered
- **Rules:** `_check_name_exists_in_factory` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S3 = section, `name "Paint"`, but `factory_id F2.id`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Paint")`.

**Then**
1. returns: `result is False`.

### FSM-CN-04 — a section of another workspace is not considered
- **Rules:** `_check_name_exists_in_factory` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F9.id, name="Packing")`.

**Then**
1. returns: `result is False`.

### FSM-CN-05 — the check for the second workspace finds that workspace's section
- **Rules:** `_check_name_exists_in_factory` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S9 = section, `name "Packing"`, but `factory_id F9.id`, `workspace_id W2.id`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W2.id, factory_id=F9.id, name="Packing")`.

**Then**
1. returns: `result is True`.

### FSM-CN-06 — a soft-deleted section with that name is ignored
- **Rules:** `_check_name_exists_in_factory` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SX = section, `name "Paint"`, but deleted.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Paint")`.

**Then**
1. returns: `result is False`.

### FSM-CN-07 — a soft-deleted and a live section with that name give True
- **Rules:** `_check_name_exists_in_factory` R3, R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. SX = section, `name "Paint"`, but deleted.
2. S2 = section, `name "Paint"`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Paint")`.

**Then**
1. returns: `result is True`.

### FSM-CN-08 — the name in lower case matches the live section
- **Rules:** `_check_name_exists_in_factory` R4 [BUG-912]
- **Kind:** bug
- **Expect:** xfail BUG-912
- **Fails today on:** Then 1 (names are compared exactly, so the result is False)

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="paint")`.

**Then**
1. returns: `result is True`.

### FSM-CN-09 — the name in upper case matches the live section
- **Rules:** `_check_name_exists_in_factory` R4 [BUG-912]
- **Kind:** bug
- **Expect:** xfail BUG-912
- **Fails today on:** Then 1 (names are compared exactly, so the result is False)

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="PAINT")`.

**Then**
1. returns: `result is True`.

### FSM-CN-10 — the name with outer spaces matches the live section
- **Rules:** `_check_name_exists_in_factory` R4 [BUG-912]
- **Kind:** bug
- **Expect:** xfail BUG-912
- **Fails today on:** Then 1 (names are compared exactly, so the result is False)

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name=" Paint ")`. The name has one space before and one space after.

**Then**
1. returns: `result is True`.

### FSM-CN-11 — the name with a trailing newline matches the live section
- **Rules:** `_check_name_exists_in_factory` R4 [BUG-912]
- **Kind:** bug
- **Expect:** xfail BUG-912
- **Fails today on:** Then 1 (names are compared exactly, so the result is False)

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Paint\n")`. The name ends with the Python literal `"\n"` (one newline).

**Then**
1. returns: `result is True`.

### FSM-CN-12 — the name with an inner space does not match
- **Rules:** `_check_name_exists_in_factory` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Pa int")`.

**Then**
1. returns: `result is False`.

### FSM-CN-13 — a longer name that starts with the section name does not match
- **Rules:** `_check_name_exists_in_factory` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Paint 2")`.

**Then**
1. returns: `result is False`.

### FSM-CN-14 — a live section that is the 100th live section of the factory is found
- **Rules:** `_check_name_exists_in_factory` R5
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over 99 sections) outside the Conventions vocabulary

**Given**
1. 99 sections B1 … B99, inserted in that order; section Bk (k = 1 … 99) has `name` = `f"Bay {k:03d}"` (so "Bay 001" … "Bay 099") and is live.
2. L = section, `name "Late"`. (Live; the 100th section of F1 — every section of F1 fits in the first 100 rows.)

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Late")`.

**Then**
1. returns: `result is True`.

### FSM-CN-15 — a live section that comes after 100 soft-deleted ones is found
- **Rules:** `_check_name_exists_in_factory` R5 [BUG-911], R3
- **Kind:** bug
- **Expect:** xfail BUG-911 (non-strict)
- **Fails today on:** Then 1 (the first 100 rows of the physical order — usually the 100 deleted ones — are examined, so the result is False; not guaranteed, hence non-strict; this card also passes once BUG-905 alone is fixed, so FSM-CN-16 carries the cap itself)
- **Author:** claude — bulk setup (a loop over 100 sections) and a non-strict xfail

**Given**
1. 100 deleted sections D1 … D100, inserted in that order; section Dk (k = 1 … 100) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 100") and is deleted.
2. L = section, `name "Late"`. (Live; row number 101 of F1.)

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Late")`.

**Then**
1. returns: `result is True`.

### FSM-CN-16 — a live section that is the 101st live section of the factory is found
- **Rules:** `_check_name_exists_in_factory` R5 [BUG-911]
- **Kind:** bug
- **Expect:** xfail BUG-911 (non-strict)
- **Fails today on:** Then 1 (only 100 sections are examined; when L is not among them — the usual case, L being inserted last — the result is False; not guaranteed, hence non-strict)
- **Author:** claude — bulk setup (a loop over 100 sections) and a non-strict xfail

**Given**
1. 100 sections B1 … B100, inserted in that order; section Bk (k = 1 … 100) has `name` = `f"Bay {k:03d}"` (so "Bay 001" … "Bay 100") and is live.
2. L = section, `name "Late"`. (Live; the 101st live section of F1.)

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Late")`.

**Then**
1. returns: `result is True`.

### FSM-CN-17 — the duplicate check does not read a capped page of sections
- **Rules:** `_check_name_exists_in_factory` R5 [BUG-911]
- **Kind:** bug
- **Expect:** xfail BUG-911
- **Fails today on:** Then 2 (the one `SELECT` sent has a `LIMIT` and no `name` condition: a page of 100 sections is loaded and compared in Python)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order)

**Given**
1. S1 = section, `name "Paint"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Paint")`.

**Then**
1. returns: `result is True`.
2. statement: of the `SELECT` statements sent that read `factory_sections`, at least one either has no `LIMIT`, or has `name` in its WHERE clause.

### FSM-CN-18 — the section named by exclude_id is ignored
- **Rules:** `_check_name_exists_in_factory` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Paint", exclude_id=S1.id)`.

**Then**
1. returns: `result is False`.

### FSM-CN-19 — excluding another section still gives True
- **Rules:** `_check_name_exists_in_factory` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.
2. S2 = section, `name "Welding"`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Paint", exclude_id=S2.id)`.

**Then**
1. returns: `result is True`.

### FSM-CN-20 — an explicit exclude_id=None ignores nothing
- **Rules:** `_check_name_exists_in_factory` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = section, `name "Paint"`.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Paint", exclude_id=None)`.

**Then**
1. returns: `result is True`.

### FSM-CN-21 — a factory without sections gives False
- **Rules:** `_check_name_exists_in_factory` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No sections exist.

**When**
- `result = M._check_name_exists_in_factory(db, workspace_id=W1.id, factory_id=F1.id, name="Paint")`.

**Then**
1. returns: `result is False`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview "Integration-only behavior": `skip >= 0`, `1 <= limit <= 1000` on `GET /factory-sections/` | endpoint `GET /factory-sections/` | 422 for `skip=-1`, `limit=0`, `limit=1001`. Here the manager lets Postgres reject negatives and `limit=0` returns `[]` (`search_factory_sections` R11). |
| `search_factory_sections` R6 [BUG-920] — `include_deleted` reachable from the API (FU-3) | `FactorySectionService.get_factory_sections` / `GET /factory-sections/`; `FactorySectionResponse` | The option is passed through, and a listed deleted section can be told from a live one (the response has no `is_deleted`). Here only the manager's own behaviour has cards (FSM-S-15, S-16, S-17, S-21, S-22 — pass today). |
| `get_factory_section` R4 [BUG-916], R5 [BUG-925] — `include_deleted` on `GET /factory-sections/{id}/` (FU-3) | `FactorySectionService.get_factory_section` / endpoint | The option is passed through; 404 for a hidden section by default at the API. |
| `create_factory_section` R8, `update_factory_section` R12 [BUG-915] — the 422 a schema `ValidationError` becomes | `POST /factory-sections/`, `PUT /factory-sections/{id}/` | Status 422 and that nothing is written. Here the schema is built directly. |
| Returns / Side effects of the three writers — "not committed"; commit, rollback, `db.refresh` | `FactorySectionService` | Commit on success, rollback on error, the refresh of the row. Here one savepoint-and-spy card per writer (FSM-C-31, U-58, D-11). |
| `delete_factory_section` R5a [BUG-908] — machines of a deleted section are hidden as its members, and are in it again after a restore | machine DAO spec (`get_by_section` R4, BUG-889); factory section DAO spec (`restore` R7, FSD-RS-13) | The hiding and the restore. Here only "the assignment rows are kept, unchanged" (FSM-D-07) and the in-memory machine (FSM-D-09). |
| FU-1 — new DAO queries for BUG-911, BUG-917, BUG-918, BUG-920, BUG-924 | factory section DAO spec, at the time of the fixes | Each new DAO method gets its own rules and cards then. |
| FU-2 — "restore section" feature | future manager / service / endpoint | Normalised name check, refusal for a section of a deleted factory, reliance on kept assignment rows. |
| FU-4 — machine form after BUG-908 / BUG-928 | machine manager spec | A machine linked to a deleted section; no cross-factory link from a section move. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `update_factory_section` R10 [BUG-928] | "Any machine-assignment row **of the workspace**" — whether an assignment row of another workspace that points at the section also blocks the move is not stated. | No card for it; the cards use assignment rows of W1 only (FSM-U-28, U-29, U-33). |
| 2 | `_check_name_exists_in_factory` R5 [BUG-911] | The intended shape of the fix is only suggested ("e.g. a dedicated existence query"). A strict, order-independent check of "every live section is examined" is not possible through results (any capped page can contain the match). | FSM-CN-17 (statement recorder) accepts either fix shape: a query without `LIMIT`, or a query with the name in its WHERE clause. A fix that keeps a capped page and loops over pages would leave CN-17 failing — then this card must be revised. |
| 3 | `update_factory_section` R8a [BUG-923] × Notes | Today the call raises `IntegrityError` and aborts the transaction; the card is written to the fixed path (`HTTPException`, no savepoint). | Not blocking: FSM-U-24 fails today inside the call, which strict xfail accepts; the session is rolled back by the test teardown. |
| 4 | `update_factory_section` R13 [BUG-919] × R17 | What a no-op (`{}`) by an unknown `user_id` does after the BUG-919 fix is only implied (R17 says "with a change that stamps it"). | No card (the factory manager's FAC-U-42 has one; here it was left out). |
| 5 | `update_factory_section` R2 × R3, `delete_factory_section` R1 × R2 | The answer for a soft-deleted section of another workspace (404 by R2 / R1, or 400 by R3 / R2) is not stated. | No card; the other-workspace cards use live sections. |
| 6 | `search_factory_sections` R8a (HR-8) vs. `docs/testing/bugs.md` BUG-917 | The register row says `%`, `_` **and `\`** stay literal; the spec rule names only `%` and `_`. | Cards for `%` and `_` only (FSM-S-30, S-31, S-32); no backslash card. |
| 7 | `search_factory_sections` R7 [BUG-924] "takes no place in the page" | Like BUG-917, a page card for this part could only be non-strict. | No page card; the strict card FSM-S-19 (the section of FD is listed today) carries BUG-924. |
| 8 | `get_factory_section` R4 | Not stated: `include_deleted=True` with an id that no section has (presumably 404). | No card; the other-workspace side of R4 has one (FSM-G-09). |
| 9 | `create_factory_section` R6 × BUG-912 × BUG-915 | A duplicate that differs only by outer whitespace is caught by either fix; only the message text needs BUG-915. | FSM-C-23 and U-56 are marked `xfail BUG-915` and cite both rules (as in the factory manager, its gap 11). |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_factory_section` | R1 | FSM-C-01, C-03, C-17 |
| `create_factory_section` | R2 | FSM-C-02 |
| `create_factory_section` | R3 | FSM-C-04, C-05, C-06, C-07, C-08 |
| `create_factory_section` | R4 | FSM-C-09, C-10 |
| `create_factory_section` | R5 | FSM-C-11 |
| `create_factory_section` | R6 | FSM-C-12, C-22 (xfail), C-23 (xfail), C-24 (non-strict xfail) |
| `create_factory_section` | R7 | FSM-C-13, C-14, C-15, D-10 |
| `create_factory_section` | R8 [BUG-915] | FSM-C-16 (xfail), C-17, C-18 (xfail), C-19 (xfail), C-20 (xfail), C-21, C-23 (xfail) |
| `create_factory_section` | R9 [BUG-913] | FSM-C-25 (xfail), C-26 (xfail), C-27, C-28, C-29 (xfail) |
| `create_factory_section` | R10 | FSM-C-30 |
| `create_factory_section` | Errors row 1 (factory missing / other workspace) | FSM-C-04, C-05, C-06, C-07, C-08 |
| `create_factory_section` | Errors row 2 (factory soft-deleted) | FSM-C-09 |
| `create_factory_section` | Errors row 3 (name taken) | FSM-C-12, C-22 (xfail), C-29 (xfail) |
| `create_factory_section` | Errors row 4 [BUG-915] (blank name, schema) | FSM-C-18 (xfail), C-19 (xfail), C-20 (xfail) |
| `create_factory_section` | Errors row 5 (`user_id` no profile) | FSM-C-30 |
| `create_factory_section` | Returns, Side effects | FSM-C-01, C-12, C-31 |
| `update_factory_section` | R1 | FSM-U-02 |
| `update_factory_section` | R2 | FSM-U-03, U-59 |
| `update_factory_section` | R3 | FSM-U-04, U-05, U-06, D-10 |
| `update_factory_section` | R3a [BUG-926] | FSM-U-07 (xfail), U-08 (xfail), U-09 (xfail), U-10 |
| `update_factory_section` | R4 | FSM-U-01, U-10, U-59 |
| `update_factory_section` | R5 | FSM-U-11, U-12, U-38 (xfail) |
| `update_factory_section` | R6 | FSM-U-13, U-14, U-15, U-55 (xfail), U-56 (xfail), U-57 (non-strict xfail) |
| `update_factory_section` | R7 | FSM-U-17, U-18, U-19, U-20, U-21, U-32 |
| `update_factory_section` | R8 | FSM-U-22, U-23, U-31 |
| `update_factory_section` | R8a [BUG-923] | FSM-U-24 (xfail) |
| `update_factory_section` | R9 [BUG-914] | FSM-U-25 (xfail), U-26 (xfail), U-27 |
| `update_factory_section` | R10 [BUG-928] | FSM-U-17, U-28 (xfail), U-29 (xfail), U-30, U-31, U-32, U-33 (xfail) |
| `update_factory_section` | R11 | FSM-U-01, U-34, U-35, U-36, U-42, U-47 |
| `update_factory_section` | R12 [BUG-915] | FSM-U-37 (xfail), U-38 (xfail), U-39 (xfail), U-40 (xfail), U-41, U-56 (xfail) |
| `update_factory_section` | R13 [BUG-919] | FSM-U-01, U-43 (xfail), U-44 (xfail), U-45 (xfail), U-46 (xfail), U-47, U-48 |
| `update_factory_section` | R14 | FSM-U-01, U-17, U-30, U-49 |
| `update_factory_section` | R15 [BUG-913] | FSM-U-50 (xfail), U-51 (xfail) |
| `update_factory_section` | R16 | FSM-U-16, U-27, U-52, U-53 |
| `update_factory_section` | R17 | FSM-U-54 |
| `update_factory_section` | Errors row 1 (section missing / other workspace) | FSM-U-02, U-03 |
| `update_factory_section` | Errors row 2 (section soft-deleted; [BUG-926] its factory) | FSM-U-04, U-07 (xfail) |
| `update_factory_section` | Errors row 3 (target factory missing / other workspace / [BUG-923] `0`) | FSM-U-18, U-19, U-20, U-24 (xfail) |
| `update_factory_section` | Errors row 4 (target factory soft-deleted) | FSM-U-22 |
| `update_factory_section` | Errors row 5 [BUG-928] (move with assignments) | FSM-U-28 (xfail) |
| `update_factory_section` | Errors row 6 (name taken; [BUG-914], [BUG-913]) | FSM-U-13, U-14, U-25 (xfail), U-50 (xfail) |
| `update_factory_section` | Errors row 7 [BUG-915] (blank name, schema) | FSM-U-39 (xfail), U-40 (xfail) |
| `update_factory_section` | Errors row 8 (`user_id` no profile) | FSM-U-54 |
| `update_factory_section` | Returns, Side effects | FSM-U-01, U-47, U-49, U-58 |
| `get_factory_section` | R1 | FSM-G-01, G-02, G-03, G-06, G-13 |
| `get_factory_section` | R2 | FSM-G-04, G-05 |
| `get_factory_section` | R3 [BUG-916] | FSM-G-07 (xfail) |
| `get_factory_section` | R4 [BUG-916] | FSM-G-08 (xfail), G-09 (xfail), G-10 (xfail) |
| `get_factory_section` | R5 [BUG-925] | FSM-G-03, G-11 (xfail), G-12 (xfail) |
| `get_factory_section` | Errors row 1 (404) | FSM-G-04, G-05, G-07 (xfail), G-11 (xfail) |
| `get_factory_section` | Side effects | FSM-G-01 |
| `search_factory_sections` | R1 | FSM-S-01, S-02, S-03, S-04, S-05, S-17 |
| `search_factory_sections` | R2 | FSM-S-06, S-07, S-08, S-09, S-10, S-33 |
| `search_factory_sections` | R2a [BUG-922] | FSM-S-11 (xfail) |
| `search_factory_sections` | R3 [BUG-917] | FSM-S-53, S-54, S-55, S-56, S-57 (non-strict xfail), S-58, S-59 (strict xfail, statement recorder) |
| `search_factory_sections` | R4 [BUG-918] / [BUG-903] | FSM-S-60, S-61, S-62, S-63 (non-strict xfail, BUG-918), S-64 (non-strict xfail, BUG-903), S-65 (strict xfail, BUG-918), S-66 (strict xfail, BUG-903) |
| `search_factory_sections` | R5 [BUG-917] | FSM-S-12, S-13, S-14, S-18, S-53, S-55, S-56, S-57 (non-strict xfail), S-58 (xfail), D-10 |
| `search_factory_sections` | R6 [BUG-920] | FSM-S-15, S-16, S-17, S-40, S-62 (non-strict xfail), D-10 |
| `search_factory_sections` | R7 [BUG-924] / [BUG-904] | FSM-S-19 (xfail, BUG-924), S-20 (xfail, BUG-904), S-21, S-22, S-23, S-24 |
| `search_factory_sections` | R8 | FSM-S-25, S-26, S-27, S-28, S-29, S-33, S-54 (non-strict xfail) |
| `search_factory_sections` | R8a (HR-8) | FSM-S-30, S-31, S-32 |
| `search_factory_sections` | R9 [BUG-921] | FSM-S-01, S-34, S-35, S-36 (xfail), S-37 (xfail), S-38 (xfail) |
| `search_factory_sections` | R10 | FSM-S-39, S-40 |
| `search_factory_sections` | R11 | FSM-S-14, S-41, S-42, S-43, S-44, S-45, S-46, S-47, S-48, S-49, S-50, S-51, S-52 |
| `search_factory_sections` | Errors row 1 (negative `limit`) | FSM-S-49, S-50 |
| `search_factory_sections` | Errors row 2 (negative `skip`) | FSM-S-51, S-52 |
| `search_factory_sections` | Side effects | FSM-S-12 |
| `delete_factory_section` | R1 | FSM-D-04, D-05 |
| `delete_factory_section` | R2 | FSM-D-06, D-15, D-10 |
| `delete_factory_section` | R3 | FSM-D-01, D-03, D-14, D-17 |
| `delete_factory_section` | R4 | FSM-D-02, D-03 |
| `delete_factory_section` | R5 [BUG-908] | FSM-D-07 (xfail), D-08 |
| `delete_factory_section` | R5a [BUG-908] | FSM-D-07 (xfail); rest deferred |
| `delete_factory_section` | R5b [BUG-908] | FSM-D-09 (xfail) |
| `delete_factory_section` | R6 | FSM-D-08 |
| `delete_factory_section` | R7 | FSM-D-10 |
| `delete_factory_section` | R8 | FSM-D-11 |
| `delete_factory_section` | R9 | FSM-D-12 |
| `delete_factory_section` | R10 [BUG-927] | FSM-D-13 (xfail), D-14, D-15 |
| `delete_factory_section` | Errors row 1 (missing / other workspace) | FSM-D-04, D-05 |
| `delete_factory_section` | Errors row 2 (already deleted) | FSM-D-06 |
| `delete_factory_section` | Errors row 3 [BUG-927] (factory soft-deleted) | FSM-D-13 (xfail) |
| `delete_factory_section` | Errors row 4 (`user_id` no profile) | FSM-D-12 |
| `delete_factory_section` | Returns, Side effects | FSM-D-01, D-08, D-11, D-16 |
| `_check_name_exists_in_factory` | R1 | FSM-C-12, CN-01, CN-02, CN-05, CN-07 |
| `_check_name_exists_in_factory` | R2 | FSM-C-13, C-15, CN-03, CN-04, CN-05 |
| `_check_name_exists_in_factory` | R3 | FSM-C-14, CN-06, CN-07, CN-15 (non-strict xfail) |
| `_check_name_exists_in_factory` | R4 [BUG-912] | FSM-C-22 (xfail), C-23 (xfail), U-55 (xfail), U-56 (xfail), CN-08 (xfail), CN-09 (xfail), CN-10 (xfail), CN-11 (xfail), CN-12, CN-13 |
| `_check_name_exists_in_factory` | R5 [BUG-911] | FSM-C-24, U-57, CN-15, CN-16 (non-strict xfail), CN-14, CN-17 (strict xfail, statement recorder) |
| `_check_name_exists_in_factory` | R6 | FSM-U-12, U-13, CN-18, CN-19, CN-20 |
| `_check_name_exists_in_factory` | R7 | FSM-CN-21 |
| `_check_name_exists_in_factory` | Side effects | FSM-CN-01 |
