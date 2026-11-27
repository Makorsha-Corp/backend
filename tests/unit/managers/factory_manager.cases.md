# Test cases — `app/managers/factory_manager.py`

> **Spec:** `tests/unit/managers/factory_manager.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-10-11). The reviewer accepted P1, Q1, Q2, Q3, Q4 as suggested and confirmed standing decision 2 ("hidden, not cascaded"), so no card changed; the Reviewer summary still names the cards that rest on each answer.
> **Revision:** 4 (2026-11-02, flake fix) — FAC-C-25, C-26, U-48, U-49, S-15, S-16, CN-14, CA-14 are now **non-strict**: forced row orders and a real VACUUM showed their result rests on physical row order (Spec gap 4). New strict statement-recorder alarms FAC-CN-20, CA-20 (BUG-893) and S-54 (BUG-898).
> **Revision 3:** (2026-11-02, spec reopened for `delete_factory`, BUG-1331) — additive: FAC-D-18 … D-42 for R5 (rewritten), R5a, R5b, R5c, Errors rows 4 and 5. No existing card changed; **nothing written** and the row vocabulary gained `production_lines` and `production_batches`. One agent wrote the spec rule, these cards and the tests, so the cards were not designed black-box from a spec someone else wrote; see the note in `factory_manager.verify.md`.
> **Revision 2:** (2026-10-16, review round delegated — decided by Claude under the reviewer's delegation (2026-10-16)) — no spec change. FAC-S-11, S-12, S-13, S-14 (BUG-898) are now **non-strict**: whether the deleted or non-matching row lands on today's page depends on the physical row order, so no Given of that size can make them fail for certain. New strict card FAC-S-52 (statement recorder: the soft-delete filter is in the query's WHERE clause) is BUG-898's order-independent alarm.
> **Counts:** 233 cases · 145 expected-to-pass · 88 expected-to-fail (bugs) · 12 deferred

## Reviewer summary
- **Per callable:** `create_factory` 36 (17 bug) · `update_factory` 52 (21 bug) · `get_factory` 9 (4 bug) · `search_factories` 53 (18 bug) · `delete_factory` 42 (15 bug) · `_check_name_exists` 20 (6 bug) · `_check_abbreviation_exists` 20 (6 bug).
- **Expected-to-fail by bug (all strict, except the non-strict BUG-899 cards FAC-S-47, S-48, S-49, S-50, S-51 and BUG-898 cards FAC-S-11, S-12, S-13, S-14):** BUG-893 8 · BUG-894 12 · BUG-895 6 · BUG-896 19 · BUG-897 4 · BUG-898 8 · BUG-899 6 · BUG-900 5 · BUG-902 5 · BUG-1331 15.
- **Open answers and the cards that rest on them** (every other card is independent of them):
  - **P1** (search text is trimmed; whitespace-only = no search — BUG-902): FAC-S-32, S-33, S-34, S-35, S-36. If the answer becomes "intended", these 5 cards are rewritten to today's behaviour.
  - **Q1** (the abbreviation follows the name's rules — trimmed, never blank, unique ignoring case, backed by the database): FAC-C-17, C-18, C-19, C-23, C-24, C-30, C-32, U-26, U-27, U-28, U-46, U-47, U-51, CA-07, CA-08, CA-09, CA-10. If the answer becomes "intended" (free text), these 17 cards go; the abbreviation cards that pass today (exact duplicate, cap, exclude, own-case change) stay.
  - **Q2** (a factory with machines / sections / stock can be deleted; nothing of theirs is touched): FAC-D-09, D-10. **Overturned for open batches only** (owner, 2026-11-02, BUG-1331): the "refused" set is FAC-D-18 … D-27 and D-35 … D-39; D-28 … D-34 and D-40 … D-42 are what still does not block. D-09, D-10 stand.
  - **Cross-workspace, a batch of the workspace on a foreign line** (delegated reading, 2026-11-02, as `machine_item_manager` `delete_item` R5a): FAC-D-37, D-42. If the owner wants its id listed, D-37 changes to `[{"type": "production_batch", "id": B1.id}, {"type": "other_workspace"}]` or to the entry alone, and D-42 stands.
  - **Q3** (nothing restores a factory; `DAOFactory.restore` is kept, feature to build): **no card** — there is no method to test; see Deferred.
  - **Q4** (the plan's `max_factories` is not checked): FAC-C-33 only.
  - **"Hidden, not cascaded"** (standing decision 2, the main session's reading): FAC-D-09, D-10 — the same two cards as Q2. If the reviewer meant a cascade, they are redesigned to "the machines and sections are soft-deleted with the factory".
- **Notable design choices:**
  - The two private checks have their own spec sections, so they get direct cards (19 + 19) that carry the whole comparison matrix (case, whitespace, cap, exclude, workspace, soft delete). The public methods repeat only one card per field and bug (case variant, whitespace variant, cap, race) plus the plain 409s — no cross-product.
  - BUG-899 (no order): FAC-S-47 and S-48 are **strict** xfail; FAC-S-49, S-50 and S-51 are **non-strict**, like the machine DAO's BUG-343 cards, because today's order is the physical row order and can match the intended order by accident (Spec gap 4; changed after verification round 1). Every other search card compares `sorted(ids(result))` or a one-element list, so it does not depend on the order.
  - BUG-898 has four small cards a local model can write (deleted row / non-matching row in front of the page, with `limit` or `skip`) and two bulk cards for the spec's own 100-row example; the 100th-row side of each boundary is a pass card. **Changed 2026-10-16:** the four small cards are **non-strict**. BUG-898 is a "deleted / non-matching rows take page places" bug, not an ordering bug, but with no `ORDER BY` (BUG-899) the database decides which rows form today's page, and for any Given there is a physical order that puts the live / matching rows first — then today's page equals the intended one and the card xpasses. No size or membership check with one call can avoid that (if the deleted rows always fall inside the page, there are fewer live rows than the page holds, and then today's and the intended result can coincide). The bulk cards FAC-S-15, S-16 stay strict: they xpass only if the live row inserted after 100 deleted ones lands physically ahead of one of them, never seen. The order-independent strict alarm is FAC-S-52 (statement recorder: the soft-delete filter must be in the query).
  - A duplicate that differs only by outer whitespace is marked `xfail BUG-896`, not BUG-894 (Spec gap 11).
  - "Flushed, not committed" has one savepoint and commit-spy card per writer: FAC-C-36 (create), FAC-U-52 (update), FAC-D-14 (`delete_factory` R7). The first two were added after verification round 1; the two readers have none.
  - The intended unique indexes (R8 / R8a) are tested on the table directly — two xfail cards (a second live row is refused) and two pass cards (a soft-deleted row and a row of another workspace are accepted) — and through the manager with a race simulation (four xfail cards).
  - W3, a workspace whose plan has `max_factories 1`, is a standing row so that the Q4 card needs no setup of its own.
  - BUG-1331: the refusal cards use no savepoint, because a refusal is a plain `ValueError` and a savepoint would hide a write; FAC-D-25 (pending row, `db.dirty`) and D-26 (statements, spies) are what catch a write that is undone. FAC-D-21 inserts explicit ids out of order, so the sort is shown under any query plan. `status` values outside the four valid ones have no card (a `status NOT IN (completed, cancelled)` fix is the same on valid data).
  - Cards marked `Author: claude` (revision 3 adds FAC-D-21, D-23, D-24, D-26): bulk setup of about 100 rows — FAC-C-25, C-26, U-48, U-49, S-15, S-16, S-17, S-18, S-19, CN-13, CN-14, CA-13, CA-14; race simulation — FAC-C-31, C-32, U-50, U-51; direct insert as the When — FAC-C-27, C-28, C-29, C-30; savepoint rollback and commit spy — FAC-C-36, FAC-U-52, FAC-D-14; non-strict xfail — FAC-S-49, S-50, S-51 (and since 2026-10-16 FAC-S-11, S-12, S-13, S-14: bodies by the local model, marker loosened); statement recorder — FAC-S-52 (added 2026-10-16); follow-up calls after the When — FAC-D-13. No edit of a standing row in this module.
- **Needs a decision:** nothing blocks a card. Worth a look: Spec gap 2 (no stock-row card for Q2), gap 4 (order cards: two strict, three non-strict), gap 6 (404 or 400 for a deleted factory of another workspace), gap 8 (a no-op by an unknown user).


## Conventions for this module

**IDs.** `FAC` = `app/managers/factory_manager.py`. `C` create_factory · `U` update_factory · `G` get_factory · `S` search_factories · `D` delete_factory · `CN` _check_name_exists · `CA` _check_abbreviation_exists.

**Actors and fixed values.**
- `M` = the singleton `factory_manager` (`from app.managers.factory_manager import FactoryManager, factory_manager`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- W1, W2 = two `workspaces` rows. W3 = a third `workspaces` row whose subscription plan row has `max_factories 1`. U1, U2 = two `profiles` rows: U1 is `created_by` of every Given factory, U2 is the acting user of the calls.
- `Factory` = `app.models.factory.Factory`. `FactoryCreate`, `FactoryUpdate` = the schemas of `app.schemas.factory`. `Machine` = `app.models.machine.Machine`. `FactorySection` = `app.models.factory_section.FactorySection`. `ProductionLine` = `app.models.production_line.ProductionLine`. `ProductionBatch` = `app.models.production_batch.ProductionBatch`.
- MISSING = `999999999`: an id that no row of any table has.
- T0 = `datetime(2025, 12, 1, 8, 0, 0)` (naive). NOW = `datetime(2026, 3, 1, 10, 0, 0)` (naive).
- Text values are written as Python literals: `"\t"` is one tab, `"\n"` one newline, `"\\"` one backslash. Copy them exactly as written, as plain strings (never raw strings).

**Externals.** In every test `app.dao.factory.utcnow` is patched to return NOW (the helper file does it; a card never patches anything itself, except the cards listed under Race simulations). Nothing else is mocked.

**Given rows.** W1, W2, W3, U1 and U2 exist in every test and need no Given line. No `factories`, `machines`, `factory_sections`, `production_lines` or `production_batches` row exists unless the card's Given lists it. Rows are inserted directly into the tables (never through `M`) and flushed one at a time in the order written, so ids rise in that order. A card names, by column name, every column that differs from these defaults.
- **factory** = `factories` row: `workspace_id W1.id`, `created_by U1.id`, `updated_by None`, `updated_at None`, `is_active True`, `is_deleted False`, `deleted_at None`, `deleted_by None`, `created_at` left to the database. The card always gives `name` and `abbreviation`; after the word "but" it lists every other column that differs.
- **deleted** (said of a factory) = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. (`is_active` stays True.)
- **machine of F** = `machines` row built with `Machine`: `workspace_id` = F's `workspace_id`, `factory_id F.id`, `is_active True`, `is_deleted False`. The card always gives `name`; after the word "but" it lists every other column that differs.
- **section of F** = `factory_sections` row built with `FactorySection`: `workspace_id` = F's `workspace_id`, `factory_id F.id`, `is_active True`, `is_deleted False`. The card always gives `name`; after the word "but" it lists every other column that differs.
- **line of F** = `production_lines` row built with `ProductionLine`: `workspace_id` = F's `workspace_id`, `factory_id F.id`, `is_active True`. The card always gives `name`; after the word "but" it lists every other column that differs.
- **batch on L** = `production_batches` row built with `ProductionBatch`: `workspace_id` = L's `workspace_id`, `production_line_id L.id`, `batch_date date(2026, 2, 1)`. The card always gives `batch_number` and `status`; after the word "but" it lists every other column that differs.

**Named checks.**
- **ids(result)** = `[f.id for f in result]` and **names(result)** = `[f.name for f in result]` — lists in the order returned (the order is part of the check). `sorted(ids(result)) == [F1.id, F2.id]` is used where the order is not part of the check; the right-hand ids are written in Given order, which is ascending id order.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values. (Expiring discards unflushed changes, so a re-read that shows a new value also proves the change was flushed.) "the returned row" = re-read by `result.id`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given row, before the call).
- **nothing written** = the numbers of rows in `factories`, `machines`, `factory_sections`, `production_lines` and `production_batches` (all workspaces) equal their values before the call.
- `count:` lines count the rows of the named table in all workspaces. Assert `updated_at` only as `is None` / `is not None`.
- `raises: HTTPException` = `fastapi.HTTPException`: plain `with pytest.raises(HTTPException) as exc:` around the call — no `begin_nested`; keep using `db` for the remaining checks.
- `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`; `raises: DataError` = `sqlalchemy.exc.DataError`. Wrap the call for both: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. `ForeignKeyViolation`, `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause` = classes of `psycopg2.errors`.
- `raises: ValueError` = plain `with pytest.raises(ValueError) as exc:` around the call: no `begin_nested`, a savepoint would hide a write; keep using `db` for the remaining checks.
- `raises: ValidationError` = `pydantic.ValidationError`: plain `with pytest.raises(ValidationError):` around the construction of the schema object.
- Further `raises:` lines of the same card are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**Targets.** "target `schema`" = the When only builds the schema object; `M` is not called. "target `database`" (cards marked Author: claude only) = the When inserts one row directly with `db.add(...)` and `db.flush()`; `M` is not called; an expected `IntegrityError` is wrapped as above.

**xfail cards.** Write the call and the checks exactly as shown — also when the call uses a parameter that does not exist yet (`include_deleted` on `get_factory`); the harness adds the marker. Every xfail in this module is strict, except FAC-S-47 … S-51 (BUG-899), FAC-S-11 … S-16 (BUG-898) and FAC-C-25, C-26, U-48, U-49, CN-14, CA-14 (BUG-893), marked `(non-strict)` on their Expect line.

**Statement recorder** (FAC-S-52, S-53, S-54, D-26, CN-20, CA-20, Author: claude). The SQL statements the session sends during the When are recorded; a `statement:` line is a check on the recorded text.

**Rolled back** (cards marked Author: claude only). `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**Race simulations** (cards marked Author: claude only). These cards patch one of the manager's own duplicate checks to return `False`, to put the code in the state "a concurrent request already passed the Python check"; nothing else may be patched this way. The call is wrapped as `with pytest.raises(HTTPException) as exc:` then `with db.begin_nested():` then the call.
- `FactoryManager._check_name_exists` → `False`: FAC-C-31, U-50 (`create_factory` R8, `update_factory` R14).
- `FactoryManager._check_abbreviation_exists` → `False`: FAC-C-32, U-51 (`create_factory` R8a, `update_factory` R14a).


## `FactoryManager.create_factory`

### FAC-C-01 — create stores a factory with the name, abbreviation, workspace and creator given
- **Rules:** `create_factory` R1, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. No factories exist.

**When**
- `result = M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, Factory)`.
2. returns: `result.id is not None`.
3. re-read the returned row: `name == "Main Plant"`, `abbreviation == "MP"`.
4. re-read the returned row: `workspace_id == W1.id`.
5. re-read the returned row: `created_by == U2.id`.
6. count: `factories` has exactly 1 row.

### FAC-C-02 — a new factory is active, not deleted, and carries no update or deletion stamp
- **Rules:** `create_factory` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No factories exist.

**When**
- `result = M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `is_active is True`, `is_deleted is False`.
3. re-read the returned row: `created_at is not None`.
4. re-read the returned row: `updated_at is None`, `updated_by is None`.
5. re-read the returned row: `deleted_at is None`, `deleted_by is None`.

### FAC-C-03 — the factory is created in the workspace passed as argument
- **Rules:** `create_factory` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.create_factory(db, factory_data=FactoryCreate(name="North Yard", abbreviation="NY"), workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W2.id`, `name == "North Yard"`, `abbreviation == "NY"`.
3. count: `factories` has exactly 2 rows.
4. unchanged: unchanged(F1).

### FAC-C-04 — a name used by a live factory of the workspace is refused with 409
- **Rules:** `create_factory` R3, Errors row 1, Side effects; `_check_name_exists` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MX"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'Main Plant' already exists"`.
4. nothing written: nothing written.
5. count: `factories` has exactly 1 row.
6. unchanged: unchanged(F1).

### FAC-C-05 — an abbreviation used by a live factory of the workspace is refused with 409
- **Rules:** `create_factory` R4, Errors row 2; `_check_abbreviation_exists` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `M.create_factory(db, factory_data=FactoryCreate(name="North Yard", abbreviation="MP"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with abbreviation 'MP' already exists"`.
4. nothing written: nothing written.
5. count: `factories` has exactly 1 row.
6. unchanged: unchanged(F1).

### FAC-C-06 — name and abbreviation both taken by one factory: the name error is raised
- **Rules:** `create_factory` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'Main Plant' already exists"`.
4. nothing written: nothing written.
5. count: `factories` has exactly 1 row.

### FAC-C-07 — name taken by one factory and abbreviation by another: the name error is raised
- **Rules:** `create_factory` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="NY"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'Main Plant' already exists"`.
4. nothing written: nothing written.
5. count: `factories` has exactly 2 rows.

### FAC-C-08 — the same name and abbreviation in another workspace do not block the create
- **Rules:** `create_factory` R6; `_check_name_exists` R2; `_check_abbreviation_exists` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F9 = factory, `name "Main Plant"`, `abbreviation "MP"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. returns: `result.id != F9.id`.
3. re-read the returned row: `workspace_id == W1.id`, `name == "Main Plant"`, `abbreviation == "MP"`.
4. count: `factories` has exactly 2 rows.
5. unchanged: unchanged(F9).

### FAC-C-09 — the name and abbreviation of a soft-deleted factory can be used again
- **Rules:** `create_factory` R6; `_check_name_exists` R3; `_check_abbreviation_exists` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = factory, `name "Main Plant"`, `abbreviation "MP"`, but deleted. (A soft-deleted factory of W1.)

**When**
- `result = M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. returns: `result.id != FD.id`.
3. re-read the returned row: `name == "Main Plant"`, `abbreviation == "MP"`, `is_deleted is False`.
4. count: `factories` has exactly 2 rows.
5. unchanged: unchanged(FD).
6. re-read FD: `is_deleted is True`.

### FAC-C-10 — a name equal to another factory's abbreviation is accepted
- **Rules:** `create_factory` R6; `_check_name_exists` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.create_factory(db, factory_data=FactoryCreate(name="MP", abbreviation="MX"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name == "MP"`, `abbreviation == "MX"`.
3. count: `factories` has exactly 2 rows.

### FAC-C-11 — an abbreviation equal to another factory's name is accepted
- **Rules:** `create_factory` R6; `_check_abbreviation_exists` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.create_factory(db, factory_data=FactoryCreate(name="North Yard", abbreviation="Main Plant"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name == "North Yard"`, `abbreviation == "Main Plant"`.
3. count: `factories` has exactly 2 rows.

### FAC-C-12 — the name is stored trimmed
- **Rules:** `create_factory` R7 [BUG-896]
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 2 (the name is stored as typed, with the outer spaces)

**Given**
1. No factories exist.

**When**
- `result = M.create_factory(db, factory_data=FactoryCreate(name="  Main Plant ", abbreviation="MP"), workspace_id=W1.id, user_id=U2.id)`. The name has two spaces before and one space after.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name == "Main Plant"`.

### FAC-C-13 — inner whitespace and case of the name and the abbreviation are kept
- **Rules:** `create_factory` R1, R7, R7a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No factories exist.

**When**
- `result = M.create_factory(db, factory_data=FactoryCreate(name="main  PLANT", abbreviation="mP"), workspace_id=W1.id, user_id=U2.id)`. The name has two spaces between the words and none outside.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name == "main  PLANT"`.
3. re-read the returned row: `abbreviation == "mP"`.

### FAC-C-14 — an empty name is rejected by FactoryCreate
- **Rules:** `create_factory` R7 [BUG-896], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. No factories exist.

**When**
- `FactoryCreate(name="", abbreviation="MP")` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. count: `factories` has exactly 0 rows.

### FAC-C-15 — a name of three spaces is rejected by FactoryCreate
- **Rules:** `create_factory` R7 [BUG-896], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. No factories exist.

**When**
- `FactoryCreate(name="   ", abbreviation="MP")` (target `schema`; M is not called). The name is `"   "` (three spaces).

**Then**
1. raises: `ValidationError`.
2. count: `factories` has exactly 0 rows.

### FAC-C-16 — a name of one tab is rejected by FactoryCreate
- **Rules:** `create_factory` R7 [BUG-896], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. No factories exist.

**When**
- `FactoryCreate(name="\t", abbreviation="MP")` (target `schema`; M is not called). The name is the Python literal `"\t"` (one tab character).

**Then**
1. raises: `ValidationError`.
2. count: `factories` has exactly 0 rows.

### FAC-C-17 — the abbreviation is stored trimmed with its case kept
- **Rules:** `create_factory` R7a [BUG-896]
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 2 (the abbreviation is stored as typed, with the outer spaces)

**Given**
1. No factories exist.

**When**
- `result = M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation=" mp "), workspace_id=W1.id, user_id=U2.id)`. The abbreviation has one space before and one space after.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `abbreviation == "mp"`.

### FAC-C-18 — an empty abbreviation is rejected by FactoryCreate
- **Rules:** `create_factory` R7a [BUG-896], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. No factories exist.

**When**
- `FactoryCreate(name="Main Plant", abbreviation="")` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. count: `factories` has exactly 0 rows.

### FAC-C-19 — an abbreviation of two spaces is rejected by FactoryCreate
- **Rules:** `create_factory` R7a [BUG-896], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. No factories exist.

**When**
- `FactoryCreate(name="Main Plant", abbreviation="  ")` (target `schema`; M is not called). The abbreviation is `"  "` (two spaces).

**Then**
1. raises: `ValidationError`.
2. count: `factories` has exactly 0 rows.

### FAC-C-20 — a one-character name and abbreviation are accepted by FactoryCreate
- **Rules:** `create_factory` R7, R7a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No factories exist.

**When**
- `result = FactoryCreate(name="a", abbreviation="b")` (target `schema`; M is not called).

**Then**
1. returns: `result.name == "a"`.
2. returns: `result.abbreviation == "b"`.

### FAC-C-21 — a name that differs only in case from a live factory's name is refused with 409
- **Rules:** `create_factory` R3, Errors row 1; `_check_name_exists` R4 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-894
- **Fails today on:** Then 1 (no error is raised: names are compared exactly, so a second factory is created)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `M.create_factory(db, factory_data=FactoryCreate(name="main plant", abbreviation="MX"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'main plant' already exists"`.
4. count: `factories` has exactly 1 row.
5. unchanged: unchanged(F1).

### FAC-C-22 — a name that differs only by a trailing space is refused with 409 and the trimmed name in the message
- **Rules:** `create_factory` R3, R7 [BUG-896]; `_check_name_exists` R4 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 1 (no error is raised: the name is neither trimmed nor compared trimmed, so a second factory is created)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `M.create_factory(db, factory_data=FactoryCreate(name="Main Plant ", abbreviation="MX"), workspace_id=W1.id, user_id=U2.id)`. The name ends with one space.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'Main Plant' already exists"`.
4. count: `factories` has exactly 1 row.
5. unchanged: unchanged(F1).

### FAC-C-23 — an abbreviation that differs only in case from a live factory's abbreviation is refused with 409
- **Rules:** `create_factory` R4, Errors row 2; `_check_abbreviation_exists` R4 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-894
- **Fails today on:** Then 1 (no error is raised: abbreviations are compared exactly, so a second factory is created)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `M.create_factory(db, factory_data=FactoryCreate(name="North Yard", abbreviation="mp"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with abbreviation 'mp' already exists"`.
4. count: `factories` has exactly 1 row.
5. unchanged: unchanged(F1).

### FAC-C-24 — an abbreviation that differs only by outer spaces is refused with 409 and the trimmed value in the message
- **Rules:** `create_factory` R4, R7a [BUG-896]; `_check_abbreviation_exists` R4 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 1 (no error is raised: the abbreviation is neither trimmed nor compared trimmed, so a second factory is created)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `M.create_factory(db, factory_data=FactoryCreate(name="North Yard", abbreviation=" MP "), workspace_id=W1.id, user_id=U2.id)`. The abbreviation has one space before and one space after.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with abbreviation 'MP' already exists"`.
4. count: `factories` has exactly 1 row.
5. unchanged: unchanged(F1).

### FAC-C-25 — a duplicate name is refused also when the live factory is the 101st row of the workspace
- **Rules:** `create_factory` R3; `_check_name_exists` R5 [BUG-893]
- **Kind:** bug
- **Expect:** xfail BUG-893 (non-strict)
- **Fails today on:** Then 1 (no error is raised: only the first 100 rows of the workspace are examined, so a second "Late" is created)
- **Author:** claude — bulk setup (a loop over about 100 factories) outside the Conventions vocabulary; non-strict xfail since 2026-11-02 (row order, see Spec gap 4)

**Given**
1. 100 deleted factories D1 … D100, inserted in that order; factory Dk (k = 1 … 100) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 100"), `abbreviation` = `f"O{k:03d}"` (so "O001" … "O100"), and is deleted.
2. L = factory, `name "Late"`, `abbreviation "LT"`. (Live; row number 101 of W1.)

**When**
- `M.create_factory(db, factory_data=FactoryCreate(name="Late", abbreviation="LX"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'Late' already exists"`.
4. count: `factories` has exactly 101 rows.

### FAC-C-26 — a duplicate abbreviation is refused also when the live factory is the 101st row of the workspace
- **Rules:** `create_factory` R4; `_check_abbreviation_exists` R5 [BUG-893]
- **Kind:** bug
- **Expect:** xfail BUG-893 (non-strict)
- **Fails today on:** Then 1 (no error is raised: only the first 100 rows of the workspace are examined, so a second "LT" is created)
- **Author:** claude — bulk setup (a loop over about 100 factories) outside the Conventions vocabulary; non-strict xfail since 2026-11-02 (row order, see Spec gap 4)

**Given**
1. 100 deleted factories D1 … D100, inserted in that order; factory Dk (k = 1 … 100) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 100"), `abbreviation` = `f"O{k:03d}"` (so "O001" … "O100"), and is deleted.
2. L = factory, `name "Late"`, `abbreviation "LT"`. (Live; row number 101 of W1.)

**When**
- `M.create_factory(db, factory_data=FactoryCreate(name="Other", abbreviation="LT"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with abbreviation 'LT' already exists"`.
4. count: `factories` has exactly 101 rows.

### FAC-C-27 — the database refuses a second live row whose name differs only in case
- **Rules:** `create_factory` R8 [BUG-895]
- **Kind:** bug
- **Expect:** xfail BUG-895
- **Fails today on:** Then 1 (no error is raised: the table has no unique index, so the row is saved)
- **Author:** claude — target `database`: the When is a direct insert, not a manager call

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- insert directly (target `database`; M is not called): `db.add(Factory(workspace_id=W1.id, name="main plant", abbreviation="MX", created_by=U1.id))`, then `db.flush()`.

**Then**
1. raises: `IntegrityError` on flush.
2. count: `factories` has exactly 1 row.

### FAC-C-28 — the database accepts a soft-deleted row with the name and abbreviation of a live factory
- **Rules:** `create_factory` R8, R8a
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — target `database`: the When is a direct insert, not a manager call

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- insert directly (target `database`; M is not called): `db.add(Factory(workspace_id=W1.id, name="Main Plant", abbreviation="MP", created_by=U1.id, is_deleted=True, deleted_at=T0, deleted_by=U1.id))`, then `db.flush()`.

**Then**
1. count: `factories` has exactly 2 rows.
2. unchanged: unchanged(F1).

### FAC-C-29 — the database accepts a row of another workspace with the name and abbreviation of a live factory
- **Rules:** `create_factory` R8, R8a
- **Kind:** isolation
- **Expect:** pass
- **Author:** claude — target `database`: the When is a direct insert, not a manager call

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- insert directly (target `database`; M is not called): `db.add(Factory(workspace_id=W2.id, name="Main Plant", abbreviation="MP", created_by=U1.id))`, then `db.flush()`.

**Then**
1. count: `factories` has exactly 2 rows.
2. unchanged: unchanged(F1).

### FAC-C-30 — the database refuses a second live row whose abbreviation differs only in case
- **Rules:** `create_factory` R8a [BUG-895]
- **Kind:** bug
- **Expect:** xfail BUG-895
- **Fails today on:** Then 1 (no error is raised: the table has no unique index, so the row is saved)
- **Author:** claude — target `database`: the When is a direct insert, not a manager call

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- insert directly (target `database`; M is not called): `db.add(Factory(workspace_id=W1.id, name="North Yard", abbreviation="mp", created_by=U1.id))`, then `db.flush()`.

**Then**
1. raises: `IntegrityError` on flush.
2. count: `factories` has exactly 1 row.

### FAC-C-31 — a duplicate name that passed the Python check is answered with 409, not a database error
- **Rules:** `create_factory` R8 [BUG-895], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-895
- **Fails today on:** Then 1 (no error is raised: the table has no unique index, so the duplicate is saved)
- **Author:** claude — race simulation (patches the manager's own duplicate check) and a savepoint around the call

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. Race simulation: `FactoryManager._check_name_exists` is patched to return `False` (Conventions, Race simulations).

**When**
- `M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MX"), workspace_id=W1.id, user_id=U2.id)`. The call is wrapped in `db.begin_nested()`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'Main Plant' already exists"`.
4. count: `factories` has exactly 1 row.
5. unchanged: unchanged(F1).

### FAC-C-32 — a duplicate abbreviation that passed the Python check is answered with 409, not a database error
- **Rules:** `create_factory` R8a [BUG-895], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-895
- **Fails today on:** Then 1 (no error is raised: the table has no unique index, so the duplicate is saved)
- **Author:** claude — race simulation (patches the manager's own duplicate check) and a savepoint around the call

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. Race simulation: `FactoryManager._check_abbreviation_exists` is patched to return `False` (Conventions, Race simulations).

**When**
- `M.create_factory(db, factory_data=FactoryCreate(name="North Yard", abbreviation="MP"), workspace_id=W1.id, user_id=U2.id)`. The call is wrapped in `db.begin_nested()`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with abbreviation 'MP' already exists"`.
4. count: `factories` has exactly 1 row.
5. unchanged: unchanged(F1).

### FAC-C-33 — a third factory is created in a workspace whose plan allows one factory
- **Rules:** `create_factory` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. FA = factory, `name "Main Plant"`, `abbreviation "MP"`, but `workspace_id W3.id`.
2. FB = factory, `name "North Yard"`, `abbreviation "NY"`, but `workspace_id W3.id`.

**When**
- `result = M.create_factory(db, factory_data=FactoryCreate(name="South Dock", abbreviation="SD"), workspace_id=W3.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W3.id`, `name == "South Dock"`, `abbreviation == "SD"`.
3. count: `factories` has exactly 3 rows.

### FAC-C-34 — a user_id that is no profile id fails on flush and no factory is saved
- **Rules:** `create_factory` R10, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. No factories exist.

**When**
- `M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"factories_created_by_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. count: `factories` has exactly 0 rows.

### FAC-C-35 — a workspace_id that is no workspace id fails on flush and no factory is saved
- **Rules:** `create_factory` R10, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. No factories exist.

**When**
- `M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=MISSING, user_id=U2.id)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"factories_workspace_id_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. count: `factories` has exactly 0 rows.

### FAC-C-36 — the create is flushed but not committed: a rollback removes the factory
- **Rules:** `create_factory` Side effects
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. No factories exist.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. count: `factories` has exactly 1 row.
2. count after the savepoint rollback: `factories` has exactly 0 rows.
3. mock called: the `db.commit` spy was never called.


## `FactoryManager.update_factory`

### FAC-U-01 — a new name is stored and the editor is recorded
- **Rules:** `update_factory` R4, R11, R12, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "North Yard"`.
3. re-read F1: `abbreviation == "MP"`.
4. re-read F1: `updated_by == U2.id`.
5. re-read F1: `updated_at is not None`.
6. count: `factories` has exactly 1 row.

### FAC-U-02 — a new abbreviation is stored and the name is kept
- **Rules:** `update_factory` R4, R9, R11, R12
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(abbreviation="NY"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `abbreviation == "NY"`.
3. re-read F1: `name == "Main Plant"`.
4. re-read F1: `updated_by == U2.id`.
5. re-read F1: `updated_at is not None`.

### FAC-U-03 — name and abbreviation are changed in one call
- **Rules:** `update_factory` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name="North Yard", abbreviation="NY"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "North Yard"`, `abbreviation == "NY"`.
3. re-read F1: `updated_by == U2.id`.

### FAC-U-04 — an id that no factory has is answered with 404
- **Rules:** `update_factory` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `M.update_factory(db, factory_id=MISSING, factory_data=FactoryUpdate(name="North Yard"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(F1).

### FAC-U-05 — a factory of another workspace is answered with 404 and not changed
- **Rules:** `update_factory` R2, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `M.update_factory(db, factory_id=F9.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F9.id} not found"`.
4. unchanged: unchanged(F9).
5. re-read F9: `name == "Far Depot"`, `updated_by is None`.

### FAC-U-06 — a soft-deleted factory is answered with 400 and not changed
- **Rules:** `update_factory` R3, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)

**When**
- `M.update_factory(db, factory_id=FD.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted factory"`.
4. unchanged: unchanged(FD).
5. re-read FD: `name == "Old Plant"`, `updated_by is None`.
6. nothing written: nothing written.

### FAC-U-07 — a soft-deleted factory is answered with 400 also when the requested name is taken
- **Rules:** `update_factory` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)
2. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `M.update_factory(db, factory_id=FD.id, factory_data=FactoryUpdate(name="Main Plant"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted factory"`.
4. unchanged: unchanged(FD).
5. unchanged: unchanged(F1).

### FAC-U-08 — a soft-deleted factory is answered with 400 also for an empty request
- **Rules:** `update_factory` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)

**When**
- `M.update_factory(db, factory_id=FD.id, factory_data=FactoryUpdate(), workspace_id=W1.id, user_id=U2.id)`. No field is sent.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted factory"`.
4. unchanged: unchanged(FD).

### FAC-U-09 — a soft-deleted factory of another workspace is answered with 404, not 400
- **Rules:** `update_factory` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. FD9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`, deleted. (A soft-deleted factory of W2.)

**When**
- `M.update_factory(db, factory_id=FD9.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {FD9.id} not found"`.
4. unchanged: unchanged(FD9).

### FAC-U-10 — sending the current name is accepted and the name stays
- **Rules:** `update_factory` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name="Main Plant"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "Main Plant"`, `abbreviation == "MP"`.
3. count: `factories` has exactly 1 row.

### FAC-U-11 — sending the current abbreviation is accepted and the abbreviation stays
- **Rules:** `update_factory` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(abbreviation="MP"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "Main Plant"`, `abbreviation == "MP"`.
3. count: `factories` has exactly 1 row.

### FAC-U-12 — changing only the case of the factory's own name is stored
- **Rules:** `update_factory` R5; `_check_name_exists` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M.update_factory(db, factory_id=F2.id, factory_data=FactoryUpdate(name="SECOND"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F2` (the very object that was looked up).
2. re-read F2: `name == "SECOND"`.
3. re-read F2: `abbreviation == "SC"`.
4. re-read F2: `updated_by == U2.id`.
5. unchanged: unchanged(F1).

### FAC-U-13 — changing only the case of the factory's own abbreviation is stored
- **Rules:** `update_factory` R5; `_check_abbreviation_exists` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M.update_factory(db, factory_id=F2.id, factory_data=FactoryUpdate(abbreviation="sc"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F2` (the very object that was looked up).
2. re-read F2: `abbreviation == "sc"`.
3. re-read F2: `name == "Second"`.
4. re-read F2: `updated_by == U2.id`.
5. unchanged: unchanged(F1).

### FAC-U-14 — a name used by another live factory is refused with 409 and the abbreviation sent with it is not applied
- **Rules:** `update_factory` R6, Errors row 3, Side effects; `_check_name_exists` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `M.update_factory(db, factory_id=F2.id, factory_data=FactoryUpdate(name="Main Plant", abbreviation="S2"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'Main Plant' already exists"`.
4. unchanged: unchanged(F2).
5. re-read F2: `name == "Second"`, `abbreviation == "SC"`.
6. unchanged: unchanged(F1).
7. nothing written: nothing written.

### FAC-U-15 — an abbreviation used by another live factory is refused with 409 and the name sent with it is not applied
- **Rules:** `update_factory` R7, Errors row 4; `_check_abbreviation_exists` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `M.update_factory(db, factory_id=F2.id, factory_data=FactoryUpdate(name="Third", abbreviation="MP"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with abbreviation 'MP' already exists"`.
4. unchanged: unchanged(F2).
5. re-read F2: `name == "Second"`, `abbreviation == "SC"`.
6. unchanged: unchanged(F1).
7. nothing written: nothing written.

### FAC-U-16 — a taken abbreviation is refused with 409 when no name is sent
- **Rules:** `update_factory` R7
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `M.update_factory(db, factory_id=F2.id, factory_data=FactoryUpdate(abbreviation="MP"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with abbreviation 'MP' already exists"`.
4. unchanged: unchanged(F2).
5. re-read F2: `abbreviation == "SC"`.

### FAC-U-17 — a taken abbreviation is refused with 409 when the current name is sent with it
- **Rules:** `update_factory` R7, R5
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `M.update_factory(db, factory_id=F2.id, factory_data=FactoryUpdate(name="Second", abbreviation="MP"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with abbreviation 'MP' already exists"`.
4. unchanged: unchanged(F2).
5. re-read F2: `abbreviation == "SC"`.

### FAC-U-18 — new name and new abbreviation both taken: the name error is raised
- **Rules:** `update_factory` R8
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.
3. F3 = factory, `name "Third"`, `abbreviation "TH"`.

**When**
- `M.update_factory(db, factory_id=F3.id, factory_data=FactoryUpdate(name="Main Plant", abbreviation="SC"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'Main Plant' already exists"`.
4. unchanged: unchanged(F3).
5. re-read F3: `name == "Third"`, `abbreviation == "TH"`.

### FAC-U-19 — an explicit null name is left unchanged while the abbreviation is changed
- **Rules:** `update_factory` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name=None, abbreviation="T4"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "Main Plant"`.
3. re-read F1: `abbreviation == "T4"`.
4. re-read F1: `updated_by == U2.id`.

### FAC-U-20 — an explicit null abbreviation is left unchanged while the name is changed
- **Rules:** `update_factory` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name="Fourth", abbreviation=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "Fourth"`.
3. re-read F1: `abbreviation == "MP"`.
4. re-read F1: `updated_by == U2.id`.

### FAC-U-21 — a sent name is stored trimmed
- **Rules:** `update_factory` R10 [BUG-896]
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 2 (the name is stored as typed, with the outer spaces)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name=" Ops "), workspace_id=W1.id, user_id=U2.id)`. The name has one space before and one space after.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "Ops"`.

### FAC-U-22 — the current name sent with outer spaces counts as the current name
- **Rules:** `update_factory` R10 [BUG-896], R5
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 2 (the name is overwritten with the untrimmed text)

**Given**
1. F1 = factory, `name "Ops"`, `abbreviation "OP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name=" Ops "), workspace_id=W1.id, user_id=U2.id)`. The name has one space before and one space after.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "Ops"`.

### FAC-U-23 — an empty name is rejected by FactoryUpdate
- **Rules:** `update_factory` R10 [BUG-896], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `FactoryUpdate(name="")` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(F1).

### FAC-U-24 — a name of three spaces is rejected by FactoryUpdate
- **Rules:** `update_factory` R10 [BUG-896], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `FactoryUpdate(name="   ")` (target `schema`; M is not called). The name is `"   "` (three spaces).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(F1).

### FAC-U-25 — a name of one tab is rejected by FactoryUpdate
- **Rules:** `update_factory` R10 [BUG-896], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `FactoryUpdate(name="\t")` (target `schema`; M is not called). The name is the Python literal `"\t"` (one tab character).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(F1).

### FAC-U-26 — a sent abbreviation is stored trimmed with its case kept
- **Rules:** `update_factory` R10a [BUG-896]
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 2 (the abbreviation is stored as typed, with the outer spaces)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(abbreviation=" t4 "), workspace_id=W1.id, user_id=U2.id)`. The abbreviation has one space before and one space after.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `abbreviation == "t4"`.

### FAC-U-27 — an empty abbreviation is rejected by FactoryUpdate
- **Rules:** `update_factory` R10a [BUG-896], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `FactoryUpdate(abbreviation="")` (target `schema`; M is not called).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(F1).

### FAC-U-28 — an abbreviation of two spaces is rejected by FactoryUpdate
- **Rules:** `update_factory` R10a [BUG-896], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 1 (no error is raised; the schema accepts the value)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `FactoryUpdate(abbreviation="  ")` (target `schema`; M is not called). The abbreviation is `"  "` (two spaces).

**Then**
1. raises: `ValidationError`.
2. unchanged: unchanged(F1).

### FAC-U-29 — a one-character name and abbreviation are accepted by FactoryUpdate
- **Rules:** `update_factory` R10, R10a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No factories exist.

**When**
- `result = FactoryUpdate(name="a", abbreviation="b")` (target `schema`; M is not called).

**Then**
1. returns: `result.name == "a"`.
2. returns: `result.abbreviation == "b"`.

### FAC-U-30 — FactoryUpdate without fields has name None and abbreviation None
- **Rules:** `update_factory` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No factories exist.

**When**
- `result = FactoryUpdate()` (target `schema`; M is not called).

**Then**
1. returns: `result.name is None`.
2. returns: `result.abbreviation is None`.

### FAC-U-31 — an empty request does not stamp updated_by
- **Rules:** `update_factory` R11 [BUG-900]
- **Kind:** bug
- **Expect:** xfail BUG-900
- **Fails today on:** Then 3 (`updated_by` is stamped on every successful call)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(), workspace_id=W1.id, user_id=U2.id)`. No field is sent.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "Main Plant"`, `abbreviation == "MP"`.
3. re-read F1: `updated_by is None`.
4. re-read F1: `updated_at is None`.

### FAC-U-32 — a request with only null fields does not stamp updated_by
- **Rules:** `update_factory` R11 [BUG-900]
- **Kind:** bug
- **Expect:** xfail BUG-900
- **Fails today on:** Then 3 (`updated_by` is stamped on every successful call)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name=None, abbreviation=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "Main Plant"`, `abbreviation == "MP"`.
3. re-read F1: `updated_by is None`.
4. re-read F1: `updated_at is None`.

### FAC-U-33 — a request with the current values does not stamp updated_by
- **Rules:** `update_factory` R11 [BUG-900]
- **Kind:** bug
- **Expect:** xfail BUG-900
- **Fails today on:** Then 3 (`updated_by` is stamped on every successful call)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name="Main Plant", abbreviation="MP"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "Main Plant"`, `abbreviation == "MP"`.
3. re-read F1: `updated_by is None`.
4. re-read F1: `updated_at is None`.

### FAC-U-34 — an empty request keeps the previous updated_by
- **Rules:** `update_factory` R11 [BUG-900]
- **Kind:** bug
- **Expect:** xfail BUG-900
- **Fails today on:** Then 2 (`updated_by` is overwritten with the acting user U2)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`, but `updated_by U1.id`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(), workspace_id=W1.id, user_id=U2.id)`. No field is sent.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `updated_by == U1.id`.
3. re-read F1: `updated_at is None`.

### FAC-U-35 — an empty request succeeds and leaves name and abbreviation as they are
- **Rules:** `update_factory` R9, R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(), workspace_id=W1.id, user_id=U2.id)`. No field is sent.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "Main Plant"`, `abbreviation == "MP"`.
3. count: `factories` has exactly 1 row.

### FAC-U-36 — a request with only null fields succeeds and leaves name and abbreviation as they are
- **Rules:** `update_factory` R9, R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name=None, abbreviation=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "Main Plant"`, `abbreviation == "MP"`.
3. count: `factories` has exactly 1 row.

### FAC-U-37 — a real change replaces a previous updated_by with the acting user
- **Rules:** `update_factory` R11, R12
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`, but `updated_by U1.id`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "North Yard"`.
3. re-read F1: `updated_by == U2.id`.
4. re-read F1: `updated_at is not None`.

### FAC-U-38 — nothing but the name and the update stamp is modified, and the other factory is untouched
- **Rules:** `update_factory` R13, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`, but `is_active False`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "North Yard"`, `abbreviation == "MP"`.
3. re-read F1: `workspace_id == W1.id`, `created_by == U1.id`.
4. re-read F1: `is_active is False`, `is_deleted is False`.
5. re-read F1: `deleted_at is None`, `deleted_by is None`.
6. re-read F1: `created_at == created_before`, where `created_before` is `F1.created_at` read after the last Given row and before the call.
7. unchanged: unchanged(F2).
8. re-read F2: `updated_at is None`, `updated_by is None`.
9. count: `factories` has exactly 2 rows.

### FAC-U-39 — the name and abbreviation of a soft-deleted factory can be taken over
- **Rules:** `update_factory` R15; `_check_name_exists` R3; `_check_abbreviation_exists` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)
2. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name="Old Plant", abbreviation="OP"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "Old Plant"`, `abbreviation == "OP"`.
3. unchanged: unchanged(FD).
4. re-read FD: `is_deleted is True`.

### FAC-U-40 — the name and abbreviation of a factory of another workspace can be taken over
- **Rules:** `update_factory` R15; `_check_name_exists` R2; `_check_abbreviation_exists` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name="Far Depot", abbreviation="FD"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "Far Depot"`, `abbreviation == "FD"`.
3. unchanged: unchanged(F9).

### FAC-U-41 — a change by a user_id that is no profile id fails on flush and nothing is saved
- **Rules:** `update_factory` R16, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. unchanged: unchanged(F1).
4. re-read F1: `name == "Main Plant"`, `updated_by is None`.
5. nothing written: nothing written.

### FAC-U-42 — an empty request by a user_id that is no profile id succeeds, because nothing is stamped
- **Rules:** `update_factory` R11 [BUG-900], R16
- **Kind:** bug
- **Expect:** xfail BUG-900
- **Fails today on:** Then 1 (the call raises IntegrityError: `updated_by` is stamped on every call and MISSING is no profile id)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(), workspace_id=W1.id, user_id=MISSING)`. No field is sent.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `updated_by is None`.

### FAC-U-43 — a factory of the second workspace is renamed from its own workspace
- **Rules:** `update_factory` R4, R13
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = M.update_factory(db, factory_id=F9.id, factory_data=FactoryUpdate(name="West Yard"), workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. returns: `result is F9` (the very object that was looked up).
2. re-read F9: `name == "West Yard"`, `abbreviation == "FD"`.
3. re-read F9: `workspace_id == W2.id`, `updated_by == U2.id`.
4. unchanged: unchanged(F1).

### FAC-U-44 — a new name that differs only in case from another live factory's name is refused with 409
- **Rules:** `update_factory` R6, Errors row 3; `_check_name_exists` R4 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-894
- **Fails today on:** Then 1 (no error is raised: names are compared exactly, so the rename is saved)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `M.update_factory(db, factory_id=F2.id, factory_data=FactoryUpdate(name="MAIN PLANT"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'MAIN PLANT' already exists"`.
4. unchanged: unchanged(F2).
5. re-read F2: `name == "Second"`.

### FAC-U-45 — a new name that differs only by a trailing space is refused with 409 and the trimmed name in the message
- **Rules:** `update_factory` R6, R10 [BUG-896]; `_check_name_exists` R4 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 1 (no error is raised: the name is neither trimmed nor compared trimmed, so the rename is saved)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `M.update_factory(db, factory_id=F2.id, factory_data=FactoryUpdate(name="Main Plant "), workspace_id=W1.id, user_id=U2.id)`. The name ends with one space.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'Main Plant' already exists"`.
4. unchanged: unchanged(F2).
5. re-read F2: `name == "Second"`.

### FAC-U-46 — a new abbreviation that differs only in case from another live factory's abbreviation is refused with 409
- **Rules:** `update_factory` R7, Errors row 4; `_check_abbreviation_exists` R4 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-894
- **Fails today on:** Then 1 (no error is raised: abbreviations are compared exactly, so the change is saved)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `M.update_factory(db, factory_id=F2.id, factory_data=FactoryUpdate(abbreviation="mp"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with abbreviation 'mp' already exists"`.
4. unchanged: unchanged(F2).
5. re-read F2: `abbreviation == "SC"`.

### FAC-U-47 — a new abbreviation that differs only by outer spaces is refused with 409 and the trimmed value in the message
- **Rules:** `update_factory` R7, R10a [BUG-896]; `_check_abbreviation_exists` R4 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-896
- **Fails today on:** Then 1 (no error is raised: the abbreviation is neither trimmed nor compared trimmed, so the change is saved)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `M.update_factory(db, factory_id=F2.id, factory_data=FactoryUpdate(abbreviation=" MP "), workspace_id=W1.id, user_id=U2.id)`. The abbreviation has one space before and one space after.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with abbreviation 'MP' already exists"`.
4. unchanged: unchanged(F2).
5. re-read F2: `abbreviation == "SC"`.

### FAC-U-48 — a rename to a taken name is refused also when its live owner is the 101st row of the workspace
- **Rules:** `update_factory` R6; `_check_name_exists` R5 [BUG-893]
- **Kind:** bug
- **Expect:** xfail BUG-893 (non-strict)
- **Fails today on:** Then 1 (no error is raised: only the first 100 rows of the workspace are examined, so the rename is saved)
- **Author:** claude — bulk setup (a loop over about 100 factories) outside the Conventions vocabulary; non-strict xfail since 2026-11-02 (row order, see Spec gap 4)

**Given**
1. 100 deleted factories D1 … D100, inserted in that order; factory Dk (k = 1 … 100) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 100"), `abbreviation` = `f"O{k:03d}"` (so "O001" … "O100"), and is deleted.
2. L = factory, `name "Late"`, `abbreviation "LT"`. (Live; row number 101 of W1.)
3. F2 = factory, `name "Second"`, `abbreviation "SC"`. (Live; row number 102 of W1.)

**When**
- `M.update_factory(db, factory_id=F2.id, factory_data=FactoryUpdate(name="Late"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'Late' already exists"`.
4. re-read F2: `name == "Second"`.
5. count: `factories` has exactly 102 rows.

### FAC-U-49 — a change to a taken abbreviation is refused also when its live owner is the 101st row of the workspace
- **Rules:** `update_factory` R7; `_check_abbreviation_exists` R5 [BUG-893]
- **Kind:** bug
- **Expect:** xfail BUG-893 (non-strict)
- **Fails today on:** Then 1 (no error is raised: only the first 100 rows of the workspace are examined, so the change is saved)
- **Author:** claude — bulk setup (a loop over about 100 factories) outside the Conventions vocabulary; non-strict xfail since 2026-11-02 (row order, see Spec gap 4)

**Given**
1. 100 deleted factories D1 … D100, inserted in that order; factory Dk (k = 1 … 100) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 100"), `abbreviation` = `f"O{k:03d}"` (so "O001" … "O100"), and is deleted.
2. L = factory, `name "Late"`, `abbreviation "LT"`. (Live; row number 101 of W1.)
3. F2 = factory, `name "Second"`, `abbreviation "SC"`. (Live; row number 102 of W1.)

**When**
- `M.update_factory(db, factory_id=F2.id, factory_data=FactoryUpdate(abbreviation="LT"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with abbreviation 'LT' already exists"`.
4. re-read F2: `abbreviation == "SC"`.
5. count: `factories` has exactly 102 rows.

### FAC-U-50 — a rename to a taken name that passed the Python check is answered with 409, not a database error
- **Rules:** `update_factory` R14 [BUG-895], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-895
- **Fails today on:** Then 1 (no error is raised: the table has no unique index, so the duplicate rename is saved)
- **Author:** claude — race simulation (patches the manager's own duplicate check) and a savepoint around the call

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.
3. Race simulation: `FactoryManager._check_name_exists` is patched to return `False` (Conventions, Race simulations).

**When**
- `M.update_factory(db, factory_id=F2.id, factory_data=FactoryUpdate(name="Main Plant"), workspace_id=W1.id, user_id=U2.id)`. The call is wrapped in `db.begin_nested()`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with name 'Main Plant' already exists"`.
4. unchanged: unchanged(F2).
5. re-read F2: `name == "Second"`.
6. unchanged: unchanged(F1).

### FAC-U-51 — a change to a taken abbreviation that passed the Python check is answered with 409, not a database error
- **Rules:** `update_factory` R14a [BUG-895], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-895
- **Fails today on:** Then 1 (no error is raised: the table has no unique index, so the duplicate abbreviation is saved)
- **Author:** claude — race simulation (patches the manager's own duplicate check) and a savepoint around the call

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.
3. Race simulation: `FactoryManager._check_abbreviation_exists` is patched to return `False` (Conventions, Race simulations).

**When**
- `M.update_factory(db, factory_id=F2.id, factory_data=FactoryUpdate(abbreviation="MP"), workspace_id=W1.id, user_id=U2.id)`. The call is wrapped in `db.begin_nested()`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Factory with abbreviation 'MP' already exists"`.
4. unchanged: unchanged(F2).
5. re-read F2: `abbreviation == "SC"`.
6. unchanged: unchanged(F1).

### FAC-U-52 — the update is flushed but not committed: a rollback brings the old name back
- **Rules:** `update_factory` Side effects
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. re-read F1: `name == "North Yard"`.
2. re-read F1 after the savepoint rollback: `name == "Main Plant"`.
3. re-read F1 after the savepoint rollback: `updated_by is None`.
4. mock called: the `db.commit` spy was never called.


## `FactoryManager.get_factory`

### FAC-G-01 — a live factory of the workspace is returned and nothing is changed
- **Rules:** `get_factory` R1, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.get_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Factory)`.
2. returns: `result.id == F1.id`.
3. returns: `result.name == "Main Plant"`, `result.abbreviation == "MP"`.
4. unchanged: unchanged(F1).
5. nothing written: nothing written.

### FAC-G-02 — a live factory with is_active False is returned
- **Rules:** `get_factory` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`, but `is_active False`. (Still `is_deleted False`.)

**When**
- `result = M.get_factory(db, factory_id=F1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == F1.id`.
2. returns: `result.is_active is False`.

### FAC-G-03 — an id that no factory has is answered with 404
- **Rules:** `get_factory` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `M.get_factory(db, factory_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(F1).

### FAC-G-04 — a factory of another workspace is answered with 404
- **Rules:** `get_factory` R2, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `M.get_factory(db, factory_id=F9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F9.id} not found"`.
4. unchanged: unchanged(F9).

### FAC-G-05 — a factory of the second workspace is returned to its own workspace
- **Rules:** `get_factory` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = M.get_factory(db, factory_id=F9.id, workspace_id=W2.id)`.

**Then**
1. returns: `result.id == F9.id`.
2. returns: `result.name == "Far Depot"`.
3. returns: `result.workspace_id == W2.id`.

### FAC-G-06 — a soft-deleted factory is answered with 404 by default
- **Rules:** `get_factory` R3 [BUG-897], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-897
- **Fails today on:** Then 1 (no error is raised: the deleted factory is returned like a live one)

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)

**When**
- `M.get_factory(db, factory_id=FD.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {FD.id} not found"`.
4. unchanged: unchanged(FD).

### FAC-G-07 — include_deleted=True returns a soft-deleted factory of the workspace
- **Rules:** `get_factory` R4 [BUG-897]
- **Kind:** bug
- **Expect:** xfail BUG-897
- **Fails today on:** Then 1 (the call raises TypeError: the parameter `include_deleted` does not exist yet)

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)

**When**
- `result = M.get_factory(db, factory_id=FD.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == FD.id`.
2. returns: `result.is_deleted is True`.

### FAC-G-08 — include_deleted=True still answers 404 for a soft-deleted factory of another workspace
- **Rules:** `get_factory` R4 [BUG-897]
- **Kind:** bug
- **Expect:** xfail BUG-897
- **Fails today on:** Then 1 (the call raises TypeError: the parameter `include_deleted` does not exist yet)

**Given**
1. FD9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`, deleted. (A soft-deleted factory of W2.)

**When**
- `M.get_factory(db, factory_id=FD9.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {FD9.id} not found"`.
4. unchanged: unchanged(FD9).

### FAC-G-09 — include_deleted=True returns a live factory as well
- **Rules:** `get_factory` R4 [BUG-897], R1
- **Kind:** bug
- **Expect:** xfail BUG-897
- **Fails today on:** Then 1 (the call raises TypeError: the parameter `include_deleted` does not exist yet)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.get_factory(db, factory_id=F1.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == F1.id`.
2. returns: `result.is_deleted is False`.


## `FactoryManager.search_factories`

### FAC-S-01 — without a search every factory of the workspace is returned as a list
- **Rules:** `search_factories` R1, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Camp Site"`, `abbreviation "CS"`.
3. F3 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [F1.id, F2.id, F3.id]`.
3. returns: `isinstance(result[0], Factory)`.

### FAC-S-02 — a factory of another workspace is not listed
- **Rules:** `search_factories` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = M.search_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [F1.id]`.

### FAC-S-03 — a call for the second workspace lists only that workspace's factory
- **Rules:** `search_factories` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = M.search_factories(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [F9.id]`.

### FAC-S-04 — an unknown workspace id returns an empty list
- **Rules:** `search_factories` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.search_factories(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### FAC-S-05 — a live factory with is_active False is listed
- **Rules:** `search_factories` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`, but `is_active False`. (Still `is_deleted False`.)
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [F1.id, F2.id]`.

### FAC-S-06 — a soft-deleted factory is not listed by default and the call changes nothing
- **Rules:** `search_factories` R4, Side effects
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)

**When**
- `result = M.search_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [F1.id]`.
2. unchanged: unchanged(F1).
3. unchanged: unchanged(FD).
4. nothing written: nothing written.

### FAC-S-07 — a workspace whose only factory is soft-deleted returns an empty list
- **Rules:** `search_factories` R4, R9
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)

**When**
- `result = M.search_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FAC-S-08 — include_deleted=True lists soft-deleted factories along with live ones
- **Rules:** `search_factories` R5 [BUG-901]
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)

**When**
- `result = M.search_factories(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `sorted(ids(result)) == [F1.id, FD.id]`.

### FAC-S-09 — include_deleted=True does not list a soft-deleted factory of another workspace
- **Rules:** `search_factories` R5 [BUG-901], R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. FD9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`, deleted. (A soft-deleted factory of W2.)

**When**
- `result = M.search_factories(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `ids(result) == [F1.id]`.

### FAC-S-10 — an explicit include_deleted=False hides the soft-deleted factory
- **Rules:** `search_factories` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)

**When**
- `result = M.search_factories(db, workspace_id=W1.id, include_deleted=False)`.

**Then**
1. returns: `ids(result) == [F1.id]`.

### FAC-S-11 — a soft-deleted factory does not use up a place in the page
- **Rules:** `search_factories` R4 [BUG-898], R2 [BUG-898]
- **Kind:** bug
- **Expect:** xfail BUG-898 (non-strict)
- **Fails today on:** Then 1 (when the deleted D1 is among the first two rows of the physical order — the usual case — it is dropped after the page was cut, so only F2 comes back; not guaranteed, hence non-strict)
- **Author:** claude — non-strict xfail (which rows form today's page depends on the physical row order, which can put the live / matching rows first by accident); body written by the local model, marker loosened 2026-10-16

**Given**
1. D1 = factory, `name "Alpha"`, `abbreviation "AL"`, but deleted. (Inserted first.)
2. F2 = factory, `name "Bravo"`, `abbreviation "BR"`.
3. F3 = factory, `name "Charlie"`, `abbreviation "CH"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `sorted(ids(result)) == [F2.id, F3.id]`.

### FAC-S-12 — a search finds a matching factory that lies outside the first page of rows
- **Rules:** `search_factories` R2 [BUG-898], R6
- **Kind:** bug
- **Expect:** xfail BUG-898 (non-strict)
- **Fails today on:** Then 1 (only two rows are loaded and searched; when F3 is not among them — the usual case — the list is empty; not guaranteed, hence non-strict)
- **Author:** claude — non-strict xfail (which rows form today's page depends on the physical row order, which can put the live / matching rows first by accident); body written by the local model, marker loosened 2026-10-16

**Given**
1. F1 = factory, `name "Alpha"`, `abbreviation "AL"`.
2. F2 = factory, `name "Bravo"`, `abbreviation "BR"`.
3. F3 = factory, `name "Camp Site"`, `abbreviation "CS"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="camp", limit=2)`.

**Then**
1. returns: `ids(result) == [F3.id]`.

### FAC-S-13 — skip counts live factories only
- **Rules:** `search_factories` R2 [BUG-898], R4 [BUG-898]
- **Kind:** bug
- **Expect:** xfail BUG-898 (non-strict)
- **Fails today on:** Then 1 (when the deleted row is the one skipped — the usual case — both live factories come back; not guaranteed, hence non-strict)
- **Author:** claude — non-strict xfail (which rows form today's page depends on the physical row order, which can put the live / matching rows first by accident); body written by the local model, marker loosened 2026-10-16

**Given**
1. D1 = factory, `name "Alpha"`, `abbreviation "AL"`, but deleted. (Inserted first.)
2. F2 = factory, `name "Bravo"`, `abbreviation "BR"`.
3. F3 = factory, `name "Charlie"`, `abbreviation "CH"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [F3.id]`.

### FAC-S-14 — skip counts matching factories only
- **Rules:** `search_factories` R2 [BUG-898]
- **Kind:** bug
- **Expect:** xfail BUG-898 (non-strict)
- **Fails today on:** Then 1 (when the non-matching row is the one skipped — the usual case — both matching factories come back; not guaranteed, hence non-strict)
- **Author:** claude — non-strict xfail (which rows form today's page depends on the physical row order, which can put the live / matching rows first by accident); body written by the local model, marker loosened 2026-10-16

**Given**
1. F1 = factory, `name "Alpha"`, `abbreviation "AL"`.
2. F2 = factory, `name "Bravo Plant"`, `abbreviation "BP"`.
3. F3 = factory, `name "Delta Plant"`, `abbreviation "DP"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="plant", skip=1)`.

**Then**
1. returns: `ids(result) == [F3.id]`.

### FAC-S-15 — the default list shows a live factory that is the 101st row of the workspace
- **Rules:** `search_factories` R2 [BUG-898], R4 [BUG-898]
- **Kind:** bug
- **Expect:** xfail BUG-898 (non-strict)
- **Fails today on:** Then 1 (the first 100 rows are loaded, all deleted, so the list is empty)
- **Author:** claude — bulk setup (a loop over about 100 factories) outside the Conventions vocabulary; non-strict xfail since 2026-11-02 (row order, see Spec gap 4)

**Given**
1. 100 deleted factories D1 … D100, inserted in that order; factory Dk (k = 1 … 100) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 100"), `abbreviation` = `f"O{k:03d}"` (so "O001" … "O100"), and is deleted.
2. L = factory, `name "Late"`, `abbreviation "LT"`. (Live; row number 101 of W1.)

**When**
- `result = M.search_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [L.id]`.

### FAC-S-16 — a search finds a live factory that is the 101st row of the workspace
- **Rules:** `search_factories` R2 [BUG-898], R6
- **Kind:** bug
- **Expect:** xfail BUG-898 (non-strict)
- **Fails today on:** Then 1 (the first 100 rows are loaded, all deleted, so the list is empty)
- **Author:** claude — bulk setup (a loop over about 100 factories) outside the Conventions vocabulary; non-strict xfail since 2026-11-02 (row order, see Spec gap 4)

**Given**
1. 100 deleted factories D1 … D100, inserted in that order; factory Dk (k = 1 … 100) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 100"), `abbreviation` = `f"O{k:03d}"` (so "O001" … "O100"), and is deleted.
2. L = factory, `name "Late"`, `abbreviation "LT"`. (Live; row number 101 of W1.)

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="late")`.

**Then**
1. returns: `ids(result) == [L.id]`.

### FAC-S-17 — the default list shows a live factory that is the 100th row of the workspace
- **Rules:** `search_factories` R2, R4
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over about 100 factories) outside the Conventions vocabulary

**Given**
1. 99 deleted factories D1 … D99, inserted in that order; factory Dk (k = 1 … 99) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 099"), `abbreviation` = `f"O{k:03d}"` (so "O001" … "O099"), and is deleted.
2. L = factory, `name "Late"`, `abbreviation "LT"`. (Live; row number 100 of W1.)

**When**
- `result = M.search_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [L.id]`.

### FAC-S-18 — the default limit returns exactly 100 of 101 live factories
- **Rules:** `search_factories` R9
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over about 100 factories) outside the Conventions vocabulary

**Given**
1. 101 factories N1 … N101, inserted in that order; factory Nk (k = 1 … 101) has `name` = `f"N{k:03d}"` (so "N001" … "N101"), `abbreviation` = `f"A{k:03d}"` (so "A001" … "A101"), and is otherwise the default factory.

**When**
- `result = M.search_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `len(set(ids(result))) == 100`.
3. returns: `set(ids(result)) <= {N1.id, …, N101.id}` (the set of all 101 ids).

### FAC-S-19 — an explicit limit of 101 returns all 101 live factories
- **Rules:** `search_factories` R9
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over about 100 factories) outside the Conventions vocabulary

**Given**
1. 101 factories N1 … N101, inserted in that order; factory Nk (k = 1 … 101) has `name` = `f"N{k:03d}"` (so "N001" … "N101"), `abbreviation` = `f"A{k:03d}"` (so "A001" … "A101"), and is otherwise the default factory.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) == [N1.id, …, N101.id]` (all 101 ids, ascending).

### FAC-S-20 — the search text is found in the abbreviation of one factory and in the name of another
- **Rules:** `search_factories` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Camp Site"`, `abbreviation "CS"`.
3. F3 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="mp")`.

**Then**
1. returns: `sorted(ids(result)) == [F1.id, F2.id]`.

### FAC-S-21 — the search ignores case and finds text at the end of a name
- **Rules:** `search_factories` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Camp Site"`, `abbreviation "CS"`.
3. F3 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="PLANT")`.

**Then**
1. returns: `ids(result) == [F1.id]`.

### FAC-S-22 — a match in the abbreviation alone is enough
- **Rules:** `search_factories` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Camp Site"`, `abbreviation "CS"`.
3. F3 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="ny")`.

**Then**
1. returns: `ids(result) == [F3.id]`.

### FAC-S-23 — a search text that no factory contains returns an empty list
- **Rules:** `search_factories` R6, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Camp Site"`, `abbreviation "CS"`.
3. F3 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="zzz")`.

**Then**
1. returns: `result == []`.

### FAC-S-24 — two inner spaces in the search text do not match a name with one space
- **Rules:** `search_factories` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Camp Site"`, `abbreviation "CS"`.
3. F3 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="main  plant")`. The text has two spaces between the words.

**Then**
1. returns: `result == []`.

### FAC-S-25 — one inner space in the search text matches the space inside a name
- **Rules:** `search_factories` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Camp Site"`, `abbreviation "CS"`.
3. F3 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="n p")`.

**Then**
1. returns: `ids(result) == [F1.id]`.

### FAC-S-26 — a percent sign in the search text matches only a percent sign
- **Rules:** `search_factories` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "100% Cotton"`, `abbreviation "HC"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="%")`.

**Then**
1. returns: `ids(result) == [F2.id]`.

### FAC-S-27 — a percent sign finds nothing when no factory contains one
- **Rules:** `search_factories` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="%")`.

**Then**
1. returns: `result == []`.

### FAC-S-28 — an underscore in the search text matches only an underscore
- **Rules:** `search_factories` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Dye_House"`, `abbreviation "DH"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="_")`.

**Then**
1. returns: `ids(result) == [F2.id]`.

### FAC-S-29 — a backslash in the search text matches only a backslash
- **Rules:** `search_factories` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "A\\B Works"`, `abbreviation "AB"`. (The name is written as the Python literal: one backslash between A and B.)

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="\\")`. The text is written as the Python literal: one backslash.

**Then**
1. returns: `ids(result) == [F2.id]`.

### FAC-S-30 — search=None applies no search filter
- **Rules:** `search_factories` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Camp Site"`, `abbreviation "CS"`.
3. F3 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search=None)`.

**Then**
1. returns: `sorted(ids(result)) == [F1.id, F2.id, F3.id]`.

### FAC-S-31 — an empty search text applies no search filter
- **Rules:** `search_factories` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Camp Site"`, `abbreviation "CS"`.
3. F3 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="")`.

**Then**
1. returns: `sorted(ids(result)) == [F1.id, F2.id, F3.id]`.

### FAC-S-32 — a search of three spaces applies no search filter
- **Rules:** `search_factories` R7 [BUG-902]
- **Kind:** bug
- **Expect:** xfail BUG-902
- **Fails today on:** Then 1 (the whitespace is searched as text and no factory contains it, so the list is empty)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Camp Site"`, `abbreviation "CS"`.
3. F3 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="   ")`. The text is `"   "` (three spaces).

**Then**
1. returns: `sorted(ids(result)) == [F1.id, F2.id, F3.id]`.

### FAC-S-33 — a search of one tab applies no search filter
- **Rules:** `search_factories` R7 [BUG-902]
- **Kind:** bug
- **Expect:** xfail BUG-902
- **Fails today on:** Then 1 (the whitespace is searched as text and no factory contains it, so the list is empty)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Camp Site"`, `abbreviation "CS"`.
3. F3 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="\t")`. The text is the Python literal `"\t"` (one tab character).

**Then**
1. returns: `sorted(ids(result)) == [F1.id, F2.id, F3.id]`.

### FAC-S-34 — a search of a space, a newline and a space applies no search filter
- **Rules:** `search_factories` R7 [BUG-902]
- **Kind:** bug
- **Expect:** xfail BUG-902
- **Fails today on:** Then 1 (the whitespace is searched as text and no factory contains it, so the list is empty)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Camp Site"`, `abbreviation "CS"`.
3. F3 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search=" \n ")`. The text is the Python literal `" \n "` (a space, a newline, a space).

**Then**
1. returns: `sorted(ids(result)) == [F1.id, F2.id, F3.id]`.

### FAC-S-35 — spaces around the search text are removed before matching
- **Rules:** `search_factories` R7 [BUG-902]
- **Kind:** bug
- **Expect:** xfail BUG-902
- **Fails today on:** Then 1 (the text is used with both spaces, which no factory contains, so the list is empty)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Camp Site"`, `abbreviation "CS"`.
3. F3 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search=" mp ")`. The text has one space before and one space after.

**Then**
1. returns: `sorted(ids(result)) == [F1.id, F2.id]`.

### FAC-S-36 — a tab before and a newline after the search text are removed before matching
- **Rules:** `search_factories` R7 [BUG-902]
- **Kind:** bug
- **Expect:** xfail BUG-902
- **Fails today on:** Then 1 (the text is used with its tab and newline, which no factory contains, so the list is empty)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Camp Site"`, `abbreviation "CS"`.
3. F3 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="\tPLANT\n")`. The text is the Python literal `"\tPLANT\n"`.

**Then**
1. returns: `ids(result) == [F1.id]`.

### FAC-S-37 — a matching soft-deleted factory is not returned by a search
- **Rules:** `search_factories` R8
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)
3. F3 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="plant")`.

**Then**
1. returns: `ids(result) == [F1.id]`.

### FAC-S-38 — a matching soft-deleted factory is returned by a search with include_deleted=True
- **Rules:** `search_factories` R8, R5 [BUG-901]
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)
3. F3 = factory, `name "North Yard"`, `abbreviation "NY"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="plant", include_deleted=True)`.

**Then**
1. returns: `sorted(ids(result)) == [F1.id, FD.id]`.

### FAC-S-39 — a workspace without factories returns an empty list
- **Rules:** `search_factories` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No factories exist.

**When**
- `result = M.search_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `result == []`.

### FAC-S-40 — skip equal to the number of factories returns an empty list
- **Rules:** `search_factories` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### FAC-S-41 — skip past the number of factories returns an empty list
- **Rules:** `search_factories` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, skip=5)`.

**Then**
1. returns: `result == []`.

### FAC-S-42 — skip 1 of two factories returns one of them
- **Rules:** `search_factories` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in [F1.id, F2.id]`.

### FAC-S-43 — limit 1 of two factories returns one of them
- **Rules:** `search_factories` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id in [F1.id, F2.id]`.

### FAC-S-44 — limit 0 returns an empty list
- **Rules:** `search_factories` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### FAC-S-45 — a negative limit is rejected by the database
- **Rules:** `search_factories` R9, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `M.search_factories(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### FAC-S-46 — a negative skip is rejected by the database
- **Rules:** `search_factories` R9, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `M.search_factories(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### FAC-S-47 — the list is ordered by name ignoring case
- **Rules:** `search_factories` R3 [BUG-899]
- **Kind:** bug
- **Expect:** xfail BUG-899 (non-strict)
- **Fails today on:** Then 1 (no order is requested, so the rows come back in physical row order, which can match the intended order by accident — non-strict)
- **Author:** claude — non-strict xfail (physical row order can match the intended order by accident); body by the local model, only the marker changed (2026-10-16)

**Given**
1. F1 = factory, `name "Delta"`, `abbreviation "DL"`.
2. F2 = factory, `name "alpha"`, `abbreviation "AL"`.
3. F3 = factory, `name "echo"`, `abbreviation "EC"`.
4. F4 = factory, `name "Bravo"`, `abbreviation "BR"`.
5. F5 = factory, `name "charlie"`, `abbreviation "CH"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["alpha", "Bravo", "charlie", "Delta", "echo"]`.

### FAC-S-48 — equal names come back in id order and deleted factories are ordered together with live ones
- **Rules:** `search_factories` R3 [BUG-899], R5 [BUG-901]
- **Kind:** bug
- **Expect:** xfail BUG-899 (non-strict)
- **Fails today on:** Then 1 (no order is requested, so the rows come back in physical row order, which can match the intended order by accident — non-strict)
- **Author:** claude — non-strict xfail (physical row order can match the intended order by accident); body by the local model, only the marker changed (2026-10-16)

**Given**
1. F1 = factory, `name "Zulu"`, `abbreviation "ZU"`.
2. D2 = factory, `name "Mango"`, `abbreviation "MG"`, but deleted.
3. F3 = factory, `name "apple"`, `abbreviation "AP"`.
4. F4 = factory, `name "mango"`, `abbreviation "MX"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `ids(result) == [F3.id, D2.id, F4.id, F1.id]`.

### FAC-S-49 — a middle page holds the second and third factory by name
- **Rules:** `search_factories` R3 [BUG-899], R9
- **Kind:** bug
- **Expect:** xfail BUG-899 (non-strict)
- **Author:** claude — non-strict xfail (the local model's harness only writes strict markers); body written by the local model, marker loosened at finishing
- **Fails today on:** Then 1 (no order is requested, so the rows come back in insertion order and the page is ["alpha", "echo"])

**Given**
1. F1 = factory, `name "Delta"`, `abbreviation "DL"`.
2. F2 = factory, `name "alpha"`, `abbreviation "AL"`.
3. F3 = factory, `name "echo"`, `abbreviation "EC"`.
4. F4 = factory, `name "Bravo"`, `abbreviation "BR"`.
5. F5 = factory, `name "charlie"`, `abbreviation "CH"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `names(result) == ["Bravo", "charlie"]`.

### FAC-S-50 — the last page holds the last factory by name
- **Rules:** `search_factories` R3 [BUG-899], R9
- **Kind:** bug
- **Expect:** xfail BUG-899 (non-strict)
- **Author:** claude — non-strict xfail (the local model's harness only writes strict markers); body written by the local model, marker loosened at finishing
- **Fails today on:** Then 1 (no order is requested, so the rows come back in insertion order and the page is ["charlie"])

**Given**
1. F1 = factory, `name "Delta"`, `abbreviation "DL"`.
2. F2 = factory, `name "alpha"`, `abbreviation "AL"`.
3. F3 = factory, `name "echo"`, `abbreviation "EC"`.
4. F4 = factory, `name "Bravo"`, `abbreviation "BR"`.
5. F5 = factory, `name "charlie"`, `abbreviation "CH"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, skip=4, limit=2)`.

**Then**
1. returns: `names(result) == ["echo"]`.

### FAC-S-51 — search results are ordered by name ignoring case
- **Rules:** `search_factories` R3 [BUG-899], R6
- **Kind:** bug
- **Expect:** xfail BUG-899 (non-strict)
- **Author:** claude — non-strict xfail (the local model's harness only writes strict markers); body written by the local model, marker loosened at finishing
- **Fails today on:** Then 1 (no order is requested, so the rows come back in insertion order)

**Given**
1. F1 = factory, `name "Zinc Plant"`, `abbreviation "ZP"`.
2. F2 = factory, `name "alpha plant"`, `abbreviation "AP"`.
3. F3 = factory, `name "Mid Plant"`, `abbreviation "MD"`.
4. F4 = factory, `name "Depot"`, `abbreviation "DP"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="plant")`.

**Then**
1. returns: `names(result) == ["alpha plant", "Mid Plant", "Zinc Plant"]`.


### FAC-S-52 — the list query leaves out soft-deleted factories in the database, before the page
- **Rules:** `search_factories` R4 [BUG-898], R2 [BUG-898]
- **Kind:** bug
- **Expect:** xfail BUG-898
- **Fails today on:** Then 2 (the query has no `is_deleted` condition after its `WHERE`; deleted rows are dropped in Python after the page was cut)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order); added 2026-10-16

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. D2 = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = M.search_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [F1.id]`.
2. statement: of the `SELECT` statements sent that read `factories`, at least one has `is_deleted` in the text after its first ` WHERE `.

### FAC-S-53 — the list query asks the database for an order
- **Rules:** `search_factories` R3 [BUG-899]
- **Kind:** bug
- **Expect:** xfail BUG-899
- **Fails today on:** Then 2 (no `SELECT` on `factories` has an `ORDER BY`)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order); added 2026-10-16

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = M.search_factories(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [F1.id]`.
2. statement: of the `SELECT` statements sent that read `factories`, at least one has an `ORDER BY`.

### FAC-S-54 — the search text is applied in the list query
- **Rules:** `search_factories` R2 [BUG-898], R6
- **Kind:** bug
- **Expect:** xfail BUG-898
- **Fails today on:** Then 2 (the search is a Python test after the page; no SELECT on `factories` names `name` after `WHERE`)
- **Author:** claude — statement recorder

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.search_factories(db, workspace_id=W1.id, search="plant")`, with the statement recorder on.

**Then**
1. returns: `ids(result) == [F1.id]`.
2. statement: some recorded `SELECT` on `factories` has `name` in its `WHERE` clause (before any `ORDER BY` or `LIMIT`), so a sort by name does not count. With FAC-S-52 it is the order-independent alarm for BUG-898; when both XPASS, remove the markers of FAC-S-11 … S-16.


## `FactoryManager.delete_factory`

### FAC-D-01 — a live factory is marked deleted with the clock value and the acting user
- **Rules:** `delete_factory` R3, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `is_deleted is True`.
3. re-read F1: `deleted_at == NOW`.
4. re-read F1: `deleted_by == U2.id`.
5. re-read F1: `is_active is True`.
6. count: `factories` has exactly 1 row.

### FAC-D-02 — no other column of the factory is changed by the delete
- **Rules:** `delete_factory` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`, but `updated_by U1.id`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `name == "Main Plant"`, `abbreviation == "MP"`.
3. re-read F1: `workspace_id == W1.id`, `created_by == U1.id`.
4. re-read F1: `updated_by == U1.id`.
5. re-read F1: `updated_at is not None`.
6. re-read F1: `created_at == created_before`, where `created_before` is `F1.created_at` read after the last Given row and before the call.
7. re-read F1: `is_deleted is True`.

### FAC-D-03 — the delete does not stamp updated_by
- **Rules:** `delete_factory` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `updated_by is None`.
3. re-read F1: `updated_at is not None`.
4. re-read F1: `is_deleted is True`.

### FAC-D-04 — a live factory with is_active False is deleted and stays inactive
- **Rules:** `delete_factory` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`, but `is_active False`. (Still `is_deleted False`.)

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `is_deleted is True`.
3. re-read F1: `is_active is False`.
4. re-read F1: `deleted_at == NOW`, `deleted_by == U2.id`.

### FAC-D-05 — an id that no factory has is answered with 404
- **Rules:** `delete_factory` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `M.delete_factory(db, factory_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. nothing written: nothing written.
5. unchanged: unchanged(F1).
6. re-read F1: `is_deleted is False`.

### FAC-D-06 — a factory of another workspace is answered with 404 and not deleted
- **Rules:** `delete_factory` R1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `M.delete_factory(db, factory_id=F9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F9.id} not found"`.
4. unchanged: unchanged(F9).
5. re-read F9: `is_deleted is False`.
6. re-read F9: `deleted_at is None`, `deleted_by is None`.

### FAC-D-07 — a soft-deleted factory of another workspace is answered with 404, not 400
- **Rules:** `delete_factory` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. FD9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`, deleted. (A soft-deleted factory of W2.)

**When**
- `M.delete_factory(db, factory_id=FD9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {FD9.id} not found"`.
4. unchanged: unchanged(FD9).
5. re-read FD9: `deleted_at == T0`, `deleted_by == U1.id`.

### FAC-D-08 — an already deleted factory is answered with 400 and keeps its deletion stamp
- **Rules:** `delete_factory` R2, Errors row 2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)

**When**
- `M.delete_factory(db, factory_id=FD.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Factory is already deleted"`.
4. unchanged: unchanged(FD).
5. re-read FD: `deleted_at == T0`.
6. re-read FD: `deleted_by == U1.id`.
7. nothing written: nothing written.

### FAC-D-09 — a factory with machines is deleted and its machines are left exactly as they were
- **Rules:** `delete_factory` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. MA1 = machine of F1, `name "Lathe"`.
3. MA2 = machine of F1, `name "Press"`, but `is_active False`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `is_deleted is True`.
3. unchanged: unchanged(MA1).
4. re-read MA1: `is_deleted is False`, `is_active is True`.
5. unchanged: unchanged(MA2).
6. re-read MA2: `is_deleted is False`, `is_active is False`.
7. count: `machines` has exactly 2 rows.

### FAC-D-10 — a factory with sections is deleted and its sections are left exactly as they were
- **Rules:** `delete_factory` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. SC1 = section of F1, `name "Assembly"`.
3. SC2 = section of F1, `name "Paint"`, but `is_active False`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `is_deleted is True`.
3. unchanged: unchanged(SC1).
4. re-read SC1: `is_deleted is False`, `is_active is True`.
5. unchanged: unchanged(SC2).
6. re-read SC2: `is_deleted is False`, `is_active is False`.
7. count: `factory_sections` has exactly 2 rows.

### FAC-D-11 — after the delete the factory is gone from the default list and shown with include_deleted=True
- **Rules:** `delete_factory` R6; `search_factories` R4, R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. returns: after the call, `ids(M.search_factories(db, workspace_id=W1.id)) == [F2.id]`.
3. returns: after the call, `sorted(ids(M.search_factories(db, workspace_id=W1.id, include_deleted=True))) == [F1.id, F2.id]`.

### FAC-D-12 — after the delete the name and the abbreviation count as free
- **Rules:** `delete_factory` R6; `_check_name_exists` R3; `_check_abbreviation_exists` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. returns: after the call, `M._check_name_exists(db, workspace_id=W1.id, name="Main Plant") is False`.
3. returns: after the call, `M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="MP") is False`.

### FAC-D-13 — after the delete a new factory can take the name and abbreviation, and an update of the deleted one answers 400
- **Rules:** `delete_factory` R6
- **Kind:** soft-delete
- **Expect:** pass
- **Author:** claude — two follow-up manager calls after the When call, one of them expected to raise

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. returns: after the call, `new = M.create_factory(db, factory_data=FactoryCreate(name="Main Plant", abbreviation="MP"), workspace_id=W1.id, user_id=U2.id)` gives `new.id != F1.id`.
3. re-read new: `name == "Main Plant"`, `abbreviation == "MP"`, `is_deleted is False`.
4. raises: after that, `M.update_factory(db, factory_id=F1.id, factory_data=FactoryUpdate(name="North Yard"), workspace_id=W1.id, user_id=U2.id)` raises `HTTPException` with `exc.value.status_code == 400`.
5. raises: that exception has `exc.value.detail == "Cannot update deleted factory"`.
6. count: `factories` has exactly 2 rows.

### FAC-D-14 — the delete is flushed but not committed: a rollback makes the factory live again
- **Rules:** `delete_factory` R7
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `is_deleted is True`.
3. re-read F1 after the savepoint rollback: `is_deleted is False`.
4. re-read F1 after the savepoint rollback: `deleted_at is None`, `deleted_by is None`.
5. mock called: the `db.commit` spy was never called.

### FAC-D-15 — only that factory row is touched
- **Rules:** `delete_factory` R7, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `is_deleted is True`.
3. unchanged: unchanged(F2).
4. re-read F2: `is_deleted is False`, `updated_at is None`.
5. nothing written: nothing written.
6. count: `factories` has exactly 2 rows.

### FAC-D-16 — a user_id that is no profile id fails on flush and the factory stays live
- **Rules:** `delete_factory` R8, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. unchanged: unchanged(F1).
4. re-read F1: `is_deleted is False`.
5. re-read F1: `deleted_at is None`, `deleted_by is None`.
6. nothing written: nothing written.

### FAC-D-17 — a factory of the second workspace is deleted from its own workspace
- **Rules:** `delete_factory` R3, R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = M.delete_factory(db, factory_id=F9.id, workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. returns: `result is F9` (the very object that was looked up).
2. re-read F9: `is_deleted is True`.
3. re-read F9: `deleted_at == NOW`, `deleted_by == U2.id`.
4. unchanged: unchanged(F1).
5. re-read F1: `is_deleted is False`.

### FAC-D-18 — a factory with a draft batch is refused and the batch is listed
- **Rules:** `delete_factory` R5a [BUG-1331], R5b [BUG-1331], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (DID NOT RAISE: nothing is looked at, the factory is deleted)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "draft"`.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError` (plain `pytest.raises`, no savepoint).
2. raises: `type(exc.value) is ValueError`.
3. raises: `len(exc.value.args) == 2`.
4. raises: `exc.value.args[0] == "Factory has open production batches"`.
5. raises: `exc.value.args[1] == [{"type": "production_batch", "id": B1.id}]`.
6. unchanged: unchanged(F1).
7. re-read F1: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
8. unchanged: unchanged(L1).
9. unchanged: unchanged(B1).
10. nothing written: nothing written.

### FAC-D-19 — a factory with an in_progress batch is refused and the batch is listed
- **Rules:** `delete_factory` R5a [BUG-1331], R5b [BUG-1331], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (DID NOT RAISE: nothing is looked at, the factory is deleted)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "in_progress"`.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError` (plain `pytest.raises`, no savepoint).
2. raises: `type(exc.value) is ValueError`.
3. raises: `len(exc.value.args) == 2`.
4. raises: `exc.value.args[0] == "Factory has open production batches"`.
5. raises: `exc.value.args[1] == [{"type": "production_batch", "id": B1.id}]`.
6. unchanged: unchanged(F1).
7. re-read F1: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
8. unchanged: unchanged(L1).
9. unchanged: unchanged(B1).
10. nothing written: nothing written.

### FAC-D-20 — only the open batches are listed when closed ones sit between them
- **Rules:** `delete_factory` R5a [BUG-1331], R5b [BUG-1331]
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (DID NOT RAISE: nothing is looked at, the factory is deleted)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "draft"`.
4. B2 = batch on L1, `batch_number "BATCH-2026-002"`, `status "completed"`.
5. B3 = batch on L1, `batch_number "BATCH-2026-003"`, `status "in_progress"`.
6. B4 = batch on L1, `batch_number "BATCH-2026-004"`, `status "cancelled"`.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError` (plain `pytest.raises`, no savepoint).
2. raises: `type(exc.value) is ValueError`.
3. raises: `len(exc.value.args) == 2`.
4. raises: `exc.value.args[0] == "Factory has open production batches"`.
5. raises: `exc.value.args[1] == [{"type": "production_batch", "id": B1.id}, {"type": "production_batch", "id": B3.id}]`.
6. unchanged: unchanged(F1).
7. re-read F1: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
8. unchanged: unchanged(B2).
9. unchanged: unchanged(B4).
10. nothing written: nothing written.

### FAC-D-21 — the blockers are sorted by id as numbers, on two lines, whatever the other columns say
- **Rules:** `delete_factory` R5b [BUG-1331]
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (DID NOT RAISE: nothing is looked at, the factory is deleted)
- **Author:** claude — explicit ids, inserted out of order

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.
3. L2 = line of F1, `name "Line B"`.
4. BC = batch on L2, `id 900000003`, `batch_number "BATCH-2026-002"`, `batch_date date(2026, 2, 1)`, `status "in_progress"`.
5. BA = batch on L2, `id 99999999`, `batch_number "BATCH-2026-003"`, `batch_date date(2026, 2, 2)`, `status "in_progress"`.
6. BB = batch on L1, `id 900000002`, `batch_number "BATCH-2026-001"`, `batch_date date(2026, 2, 3)`, `status "draft"`.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError` (plain `pytest.raises`, no savepoint).
2. raises: `type(exc.value) is ValueError`.
3. raises: `len(exc.value.args) == 2`.
4. raises: `exc.value.args[0] == "Factory has open production batches"`.
5. raises: `exc.value.args[1] == [{"type": "production_batch", "id": 99999999}, {"type": "production_batch", "id": 900000002}, {"type": "production_batch", "id": 900000003}]`.
6. unchanged: unchanged(F1).
7. re-read F1: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
8. nothing written: nothing written.

### FAC-D-22 — a batch on an inactive line blocks
- **Rules:** `delete_factory` R5a [BUG-1331]
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (DID NOT RAISE: nothing is looked at, the factory is deleted)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`, but `is_active False`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "draft"`.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError` (plain `pytest.raises`, no savepoint).
2. raises: `type(exc.value) is ValueError`.
3. raises: `len(exc.value.args) == 2`.
4. raises: `exc.value.args[0] == "Factory has open production batches"`.
5. raises: `exc.value.args[1] == [{"type": "production_batch", "id": B1.id}]`.
6. unchanged: unchanged(F1).
7. re-read F1: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
8. unchanged: unchanged(L1).
9. nothing written: nothing written.

### FAC-D-23 — all 101 open batches are listed, not a first page
- **Rules:** `delete_factory` R5b [BUG-1331]
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (DID NOT RAISE: nothing is looked at, the factory is deleted)
- **Author:** claude — bulk setup of 101 rows

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.
3. B1 … B101 = 101 batches on L1, `batch_number "BATCH-2026-001"` … `"BATCH-2026-101"`, each `status "draft"`.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError` (plain `pytest.raises`, no savepoint).
2. raises: `len(exc.value.args[1]) == 101`.
3. raises: `exc.value.args[1] == [{"type": "production_batch", "id": b.id} for b in [B1 … B101]]`, in that order.
4. re-read F1: `is_deleted is False`.

### FAC-D-24 — an open batch after 100 closed ones is found
- **Rules:** `delete_factory` R5a [BUG-1331], R5b [BUG-1331]
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (DID NOT RAISE: nothing is looked at, the factory is deleted)
- **Author:** claude — bulk setup of 100 rows

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.
3. 100 batches on L1, `batch_number "BATCH-2026-001"` … `"BATCH-2026-100"`, each `status "completed"`.
4. B1 = batch on L1, `batch_number "BATCH-2026-101"`, `status "draft"`.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError` (plain `pytest.raises`, no savepoint).
2. raises: `exc.value.args[1] == [{"type": "production_batch", "id": B1.id}]`.
3. re-read F1: `is_deleted is False`.

### FAC-D-25 — the refusal writes nothing: the pending row stays pending and nothing is dirty
- **Rules:** `delete_factory` R5c [BUG-1331]
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (DID NOT RAISE: nothing is looked at, the factory is deleted)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "draft"`.
4. P1 = `Factory(workspace_id=W1.id, name="Pending", abbreviation="PD", created_by=U1.id)`, added with `db.add` and **not flushed**.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError` (plain `pytest.raises`, no savepoint).
2. raises: `exc.value.args[1] == [{"type": "production_batch", "id": B1.id}]`.
3. session, before any `expire_all()`: `len(db.new) == 1`.
4. session, before any `expire_all()`: `P1 in db.new`.
5. session, before any `expire_all()`: `not db.dirty`.
6. session, before any `expire_all()`: `not db.deleted`.
7. in memory, before any `expire_all()`: `F1.is_deleted is False`, `F1.deleted_at is None`, `F1.deleted_by is None`.

### FAC-D-26 — no savepoint hides a write: no write statement, no savepoint, no flush, commit or rollback
- **Rules:** `delete_factory` R5c [BUG-1331]
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (DID NOT RAISE: nothing is looked at, the factory is deleted)
- **Author:** claude — statement recorder and spies

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "in_progress"`.
4. Statement recorder, and spies that wrap `db.commit`, `db.rollback` and `db.flush`, started directly before the call.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError` (plain `pytest.raises`, no savepoint).
2. raises: `exc.value.args[1] == [{"type": "production_batch", "id": B1.id}]`.
3. statement: no recorded statement starts with `UPDATE`, `INSERT` or `DELETE`.
4. statement: no recorded statement starts with `SAVEPOINT`.
5. mock called: the `db.commit` spy was never called.
6. mock called: the `db.rollback` spy was never called.
7. mock called: the `db.flush` spy was never called.

### FAC-D-27 — the refusal comes before the unknown user's failure on flush
- **Rules:** `delete_factory` R5a [BUG-1331], R8
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (the call raises IntegrityError: the stamp is flushed, nothing is refused first)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "draft"`.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `ValueError` (plain `pytest.raises`, no savepoint).
2. raises: `type(exc.value) is ValueError`.
3. raises: `len(exc.value.args) == 2`.
4. raises: `exc.value.args[0] == "Factory has open production batches"`.
5. raises: `exc.value.args[1] == [{"type": "production_batch", "id": B1.id}]`.
6. unchanged: unchanged(F1).
7. re-read F1: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
8. unchanged: unchanged(B1).
9. nothing written: nothing written.

### FAC-D-28 — an already deleted factory with an open batch is answered with 400, not refused with blockers
- **Rules:** `delete_factory` R2, R5a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted.
2. L1 = line of FD, `name "Line A"`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "draft"`.

**When**
- `M.delete_factory(db, factory_id=FD.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `status_code == 400`.
3. raises: `detail == "Factory is already deleted"`.
4. unchanged: unchanged(FD).
5. unchanged: unchanged(B1).
6. re-read FD: `deleted_at == T0`, `deleted_by == U1.id`.

### FAC-D-29 — a factory of another workspace with an open batch is answered with 404, not refused with blockers
- **Rules:** `delete_factory` R1, R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "draft"`.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `status_code == 404`.
3. raises: `detail == f"Factory with ID {F1.id} not found"`.
4. unchanged: unchanged(F1).
5. unchanged: unchanged(B1).

### FAC-D-30 — a completed batch does not block and is left as it was
- **Rules:** `delete_factory` R5, R5a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "completed"`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `is_deleted is True`.
3. re-read F1: `deleted_at == NOW`, `deleted_by == U2.id`.
4. unchanged: unchanged(L1).
5. unchanged: unchanged(B1).
6. re-read B1: `status == "completed"`.

### FAC-D-31 — a cancelled batch does not block and is left as it was
- **Rules:** `delete_factory` R5, R5a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "cancelled"`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `is_deleted is True`.
3. re-read F1: `deleted_at == NOW`, `deleted_by == U2.id`.
4. unchanged: unchanged(L1).
5. unchanged: unchanged(B1).
6. re-read B1: `status == "cancelled"`.

### FAC-D-32 — a production line without batches does not block and is left as it was
- **Rules:** `delete_factory` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `is_deleted is True`.
3. re-read F1: `deleted_at == NOW`, `deleted_by == U2.id`.
4. unchanged: unchanged(L1).
5. re-read L1: `is_active is True`.

### FAC-D-33 — an open batch of another factory of the workspace does not block
- **Rules:** `delete_factory` R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.
3. L2 = line of F2, `name "Line B"`.
4. B2 = batch on L2, `batch_number "BATCH-2026-001"`, `status "draft"`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `is_deleted is True`.
3. re-read F1: `deleted_at == NOW`, `deleted_by == U2.id`.
4. unchanged: unchanged(F2).
5. unchanged: unchanged(L2).
6. unchanged: unchanged(B2).

### FAC-D-34 — an open batch of a factory of another workspace does not block
- **Rules:** `delete_factory` R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`.
3. L9 = line of F9, `name "Line Z"`.
4. B9 = batch on L9, `batch_number "BATCH-2026-001"`, `status "in_progress"`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `is_deleted is True`.
3. re-read F1: `deleted_at == NOW`, `deleted_by == U2.id`.
4. unchanged: unchanged(F9).
5. unchanged: unchanged(L9).
6. unchanged: unchanged(B9).

### FAC-D-35 — a draft batch of another workspace on the factory's own line gives one generic entry
- **Rules:** `delete_factory` R5a [BUG-1331], R5b [BUG-1331], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (DID NOT RAISE: nothing is looked at, the factory is deleted)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "draft"`, but `workspace_id W2.id`.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError` (plain `pytest.raises`, no savepoint).
2. raises: `type(exc.value) is ValueError`.
3. raises: `len(exc.value.args) == 2`.
4. raises: `exc.value.args[0] == "Factory has open production batches"`.
5. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
6. unchanged: unchanged(F1).
7. re-read F1: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
8. unchanged: unchanged(L1).
9. unchanged: unchanged(B1).
10. nothing written: nothing written.

### FAC-D-36 — an in_progress batch of another workspace on another workspace's line of the factory gives one generic entry
- **Rules:** `delete_factory` R5a [BUG-1331], R5b [BUG-1331], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (DID NOT RAISE: nothing is looked at, the factory is deleted)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`, but `workspace_id W2.id`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "in_progress"`.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError` (plain `pytest.raises`, no savepoint).
2. raises: `type(exc.value) is ValueError`.
3. raises: `len(exc.value.args) == 2`.
4. raises: `exc.value.args[0] == "Factory has open production batches"`.
5. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
6. unchanged: unchanged(F1).
7. re-read F1: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
8. unchanged: unchanged(L1).
9. unchanged: unchanged(B1).
10. nothing written: nothing written.

### FAC-D-37 — a batch of the factory's workspace on another workspace's line of the factory gives one generic entry, not its id
- **Rules:** `delete_factory` R5a [BUG-1331], R5b [BUG-1331], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (DID NOT RAISE: nothing is looked at, the factory is deleted)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`, but `workspace_id W2.id`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "draft"`, but `workspace_id W1.id`.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError` (plain `pytest.raises`, no savepoint).
2. raises: `type(exc.value) is ValueError`.
3. raises: `len(exc.value.args) == 2`.
4. raises: `exc.value.args[0] == "Factory has open production batches"`.
5. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
6. unchanged: unchanged(F1).
7. re-read F1: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
8. unchanged: unchanged(L1).
9. unchanged: unchanged(B1).
10. nothing written: nothing written.

### FAC-D-38 — two cross-workspace batches give the generic entry once
- **Rules:** `delete_factory` R5b [BUG-1331], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (DID NOT RAISE: nothing is looked at, the factory is deleted)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "draft"`, but `workspace_id W2.id`.
4. B2 = batch on L1, `batch_number "BATCH-2026-002"`, `status "in_progress"`, but `workspace_id W2.id`.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError` (plain `pytest.raises`, no savepoint).
2. raises: `type(exc.value) is ValueError`.
3. raises: `len(exc.value.args) == 2`.
4. raises: `exc.value.args[0] == "Factory has open production batches"`.
5. raises: `exc.value.args[1] == [{"type": "other_workspace"}]`.
6. unchanged: unchanged(F1).
7. re-read F1: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
8. nothing written: nothing written.

### FAC-D-39 — the generic entry comes last, also when the foreign batch has the lower id
- **Rules:** `delete_factory` R5b [BUG-1331], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-1331
- **Fails today on:** Then 1 (DID NOT RAISE: nothing is looked at, the factory is deleted)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.
3. BX = batch on L1, `batch_number "BATCH-2026-001"`, `status "draft"`, but `workspace_id W2.id`.
4. BO = batch on L1, `batch_number "BATCH-2026-002"`, `status "in_progress"`.

**When**
- `M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError` (plain `pytest.raises`, no savepoint).
2. raises: `type(exc.value) is ValueError`.
3. raises: `len(exc.value.args) == 2`.
4. raises: `exc.value.args[0] == "Factory has open production batches"`.
5. raises: `exc.value.args[1] == [{"type": "production_batch", "id": BO.id}, {"type": "other_workspace"}]`.
6. unchanged: unchanged(F1).
7. re-read F1: `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
8. nothing written: nothing written.

### FAC-D-40 — a completed batch of another workspace on the factory's own line does not block
- **Rules:** `delete_factory` R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "completed"`, but `workspace_id W2.id`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `is_deleted is True`.
3. re-read F1: `deleted_at == NOW`, `deleted_by == U2.id`.
4. unchanged: unchanged(L1).
5. unchanged: unchanged(B1).

### FAC-D-41 — a cancelled batch of another workspace on another workspace's line of the factory does not block
- **Rules:** `delete_factory` R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`, but `workspace_id W2.id`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "cancelled"`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `is_deleted is True`.
3. re-read F1: `deleted_at == NOW`, `deleted_by == U2.id`.
4. unchanged: unchanged(L1).
5. unchanged: unchanged(B1).

### FAC-D-42 — a completed batch of the factory's workspace on another workspace's line of the factory does not block
- **Rules:** `delete_factory` R5a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. L1 = line of F1, `name "Line A"`, but `workspace_id W2.id`.
3. B1 = batch on L1, `batch_number "BATCH-2026-001"`, `status "completed"`, but `workspace_id W1.id`.

**When**
- `result = M.delete_factory(db, factory_id=F1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is F1` (the very object that was looked up).
2. re-read F1: `is_deleted is True`.
3. re-read F1: `deleted_at == NOW`, `deleted_by == U2.id`.
4. unchanged: unchanged(L1).
5. unchanged: unchanged(B1).


## `FactoryManager._check_name_exists`

### FAC-CN-01 — a live factory of the workspace with that name gives True and nothing is changed
- **Rules:** `_check_name_exists` R1, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Main Plant")`.

**Then**
1. returns: `result is True`.
2. unchanged: unchanged(F1).
3. nothing written: nothing written.

### FAC-CN-02 — a name that no factory of the workspace has gives False
- **Rules:** `_check_name_exists` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="North Yard")`.

**Then**
1. returns: `result is False`.

### FAC-CN-03 — a factory of another workspace with that name is not considered
- **Rules:** `_check_name_exists` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Far Depot")`.

**Then**
1. returns: `result is False`.

### FAC-CN-04 — the check for the second workspace finds that workspace's factory
- **Rules:** `_check_name_exists` R2, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = M._check_name_exists(db, workspace_id=W2.id, name="Far Depot")`.

**Then**
1. returns: `result is True`.

### FAC-CN-05 — a soft-deleted factory with that name is ignored
- **Rules:** `_check_name_exists` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)
2. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Old Plant")`.

**Then**
1. returns: `result is False`.

### FAC-CN-06 — a soft-deleted and a live factory with that name give True
- **Rules:** `_check_name_exists` R3, R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = factory, `name "Main Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1 with the same name as F1.)
2. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Main Plant")`.

**Then**
1. returns: `result is True`.

### FAC-CN-07 — the name in lower case matches the live factory
- **Rules:** `_check_name_exists` R4 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-894
- **Fails today on:** Then 1 (names are compared exactly, so the result is False)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="main plant")`.

**Then**
1. returns: `result is True`.

### FAC-CN-08 — the name in upper case matches the live factory
- **Rules:** `_check_name_exists` R4 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-894
- **Fails today on:** Then 1 (names are compared exactly, so the result is False)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="MAIN PLANT")`.

**Then**
1. returns: `result is True`.

### FAC-CN-09 — the name with a trailing space matches the live factory
- **Rules:** `_check_name_exists` R4 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-894
- **Fails today on:** Then 1 (names are compared exactly, so the result is False)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Main Plant ")`. The name ends with one space.

**Then**
1. returns: `result is True`.

### FAC-CN-10 — the name with a leading tab matches the live factory
- **Rules:** `_check_name_exists` R4 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-894
- **Fails today on:** Then 1 (names are compared exactly, so the result is False)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="\tMain Plant")`. The name is the Python literal `"\tMain Plant"`.

**Then**
1. returns: `result is True`.

### FAC-CN-11 — the name with two inner spaces does not match
- **Rules:** `_check_name_exists` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Main  Plant")`. The name has two spaces between the words.

**Then**
1. returns: `result is False`.

### FAC-CN-12 — a longer name that starts with the factory name does not match
- **Rules:** `_check_name_exists` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Main Plant 2")`.

**Then**
1. returns: `result is False`.

### FAC-CN-13 — a live factory that is the 100th row of the workspace is found
- **Rules:** `_check_name_exists` R5
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over about 100 factories) outside the Conventions vocabulary

**Given**
1. 99 deleted factories D1 … D99, inserted in that order; factory Dk (k = 1 … 99) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 099"), `abbreviation` = `f"O{k:03d}"` (so "O001" … "O099"), and is deleted.
2. L = factory, `name "Late"`, `abbreviation "LT"`. (Live; row number 100 of W1.)

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Late")`.

**Then**
1. returns: `result is True`.

### FAC-CN-14 — a live factory that is the 101st row of the workspace is found
- **Rules:** `_check_name_exists` R5 [BUG-893]
- **Kind:** bug
- **Expect:** xfail BUG-893 (non-strict)
- **Fails today on:** Then 1 (only the first 100 rows of the workspace are examined, so the result is False)
- **Author:** claude — bulk setup (a loop over about 100 factories) outside the Conventions vocabulary; non-strict xfail since 2026-11-02 (row order, see Spec gap 4)

**Given**
1. 100 deleted factories D1 … D100, inserted in that order; factory Dk (k = 1 … 100) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 100"), `abbreviation` = `f"O{k:03d}"` (so "O001" … "O100"), and is deleted.
2. L = factory, `name "Late"`, `abbreviation "LT"`. (Live; row number 101 of W1.)

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Late")`.

**Then**
1. returns: `result is True`.

### FAC-CN-15 — the factory named by exclude_id is ignored
- **Rules:** `_check_name_exists` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Main Plant", exclude_id=F1.id)`.

**Then**
1. returns: `result is False`.

### FAC-CN-16 — excluding another factory still gives True
- **Rules:** `_check_name_exists` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Main Plant", exclude_id=F2.id)`.

**Then**
1. returns: `result is True`.

### FAC-CN-17 — an explicit exclude_id=None ignores nothing
- **Rules:** `_check_name_exists` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Main Plant", exclude_id=None)`.

**Then**
1. returns: `result is True`.

### FAC-CN-18 — a workspace without factories gives False
- **Rules:** `_check_name_exists` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No factories exist.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Main Plant")`.

**Then**
1. returns: `result is False`.

### FAC-CN-19 — a factory whose abbreviation equals the name looked for does not match
- **Rules:** `_check_name_exists` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="MP")`.

**Then**
1. returns: `result is False`.

### FAC-CN-20 — the name check does not read a capped page of the workspace
- **Rules:** `_check_name_exists` R5 [BUG-893]
- **Kind:** bug
- **Expect:** xfail BUG-893
- **Fails today on:** Then 2 (the only SELECT on `factories` filters on `workspace_id` and has a `LIMIT`)
- **Author:** claude — statement recorder

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M._check_name_exists(db, workspace_id=W1.id, name="Main Plant")`, with the statement recorder on.

**Then**
1. returns: `result is True`.
2. statement: some recorded `SELECT` on `factories` has `name` in its `WHERE` clause (before any `ORDER BY` or `LIMIT`), or no recorded `SELECT` on `factories` has a `LIMIT`. It is order-independent: the alarm for the fix of BUG-893; when it XPASSes, remove the markers of FAC-C-25, U-48, CN-14 in the same step.


## `FactoryManager._check_abbreviation_exists`

### FAC-CA-01 — a live factory of the workspace with that abbreviation gives True and nothing is changed
- **Rules:** `_check_abbreviation_exists` R1, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="MP")`.

**Then**
1. returns: `result is True`.
2. unchanged: unchanged(F1).
3. nothing written: nothing written.

### FAC-CA-02 — a abbreviation that no factory of the workspace has gives False
- **Rules:** `_check_abbreviation_exists` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="NY")`.

**Then**
1. returns: `result is False`.

### FAC-CA-03 — a factory of another workspace with that abbreviation is not considered
- **Rules:** `_check_abbreviation_exists` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="FD")`.

**Then**
1. returns: `result is False`.

### FAC-CA-04 — the check for the second workspace finds that workspace's factory
- **Rules:** `_check_abbreviation_exists` R2, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F9 = factory, `name "Far Depot"`, `abbreviation "FD"`, but `workspace_id W2.id`. (A factory of W2.)

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W2.id, abbreviation="FD")`.

**Then**
1. returns: `result is True`.

### FAC-CA-05 — a soft-deleted factory with that abbreviation is ignored
- **Rules:** `_check_abbreviation_exists` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "OP"`, but deleted. (A soft-deleted factory of W1.)
2. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="OP")`.

**Then**
1. returns: `result is False`.

### FAC-CA-06 — a soft-deleted and a live factory with that abbreviation give True
- **Rules:** `_check_abbreviation_exists` R3, R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. FD = factory, `name "Old Plant"`, `abbreviation "MP"`, but deleted. (A soft-deleted factory of W1 with the same abbreviation as F1.)
2. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="MP")`.

**Then**
1. returns: `result is True`.

### FAC-CA-07 — the abbreviation in lower case matches the live factory
- **Rules:** `_check_abbreviation_exists` R4 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-894
- **Fails today on:** Then 1 (abbreviations are compared exactly, so the result is False)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="mp")`.

**Then**
1. returns: `result is True`.

### FAC-CA-08 — the abbreviation in mixed case matches the live factory
- **Rules:** `_check_abbreviation_exists` R4 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-894
- **Fails today on:** Then 1 (abbreviations are compared exactly, so the result is False)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="Mp")`.

**Then**
1. returns: `result is True`.

### FAC-CA-09 — the abbreviation with outer spaces matches the live factory
- **Rules:** `_check_abbreviation_exists` R4 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-894
- **Fails today on:** Then 1 (abbreviations are compared exactly, so the result is False)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation=" MP ")`. The abbreviation has one space before and one space after.

**Then**
1. returns: `result is True`.

### FAC-CA-10 — the abbreviation with a trailing newline matches the live factory
- **Rules:** `_check_abbreviation_exists` R4 [BUG-894]
- **Kind:** bug
- **Expect:** xfail BUG-894
- **Fails today on:** Then 1 (abbreviations are compared exactly, so the result is False)

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="MP\n")`. The abbreviation is the Python literal `"MP\n"`.

**Then**
1. returns: `result is True`.

### FAC-CA-11 — a longer abbreviation that starts with the factory abbreviation does not match
- **Rules:** `_check_abbreviation_exists` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="MP2")`.

**Then**
1. returns: `result is False`.

### FAC-CA-12 — the abbreviation with an inner space does not match
- **Rules:** `_check_abbreviation_exists` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="M P")`.

**Then**
1. returns: `result is False`.

### FAC-CA-13 — a live factory that is the 100th row of the workspace is found
- **Rules:** `_check_abbreviation_exists` R5
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (a loop over about 100 factories) outside the Conventions vocabulary

**Given**
1. 99 deleted factories D1 … D99, inserted in that order; factory Dk (k = 1 … 99) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 099"), `abbreviation` = `f"O{k:03d}"` (so "O001" … "O099"), and is deleted.
2. L = factory, `name "Late"`, `abbreviation "LT"`. (Live; row number 100 of W1.)

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="LT")`.

**Then**
1. returns: `result is True`.

### FAC-CA-14 — a live factory that is the 101st row of the workspace is found
- **Rules:** `_check_abbreviation_exists` R5 [BUG-893]
- **Kind:** bug
- **Expect:** xfail BUG-893 (non-strict)
- **Fails today on:** Then 1 (only the first 100 rows of the workspace are examined, so the result is False)
- **Author:** claude — bulk setup (a loop over about 100 factories) outside the Conventions vocabulary; non-strict xfail since 2026-11-02 (row order, see Spec gap 4)

**Given**
1. 100 deleted factories D1 … D100, inserted in that order; factory Dk (k = 1 … 100) has `name` = `f"Old {k:03d}"` (so "Old 001" … "Old 100"), `abbreviation` = `f"O{k:03d}"` (so "O001" … "O100"), and is deleted.
2. L = factory, `name "Late"`, `abbreviation "LT"`. (Live; row number 101 of W1.)

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="LT")`.

**Then**
1. returns: `result is True`.

### FAC-CA-15 — the factory named by exclude_id is ignored
- **Rules:** `_check_abbreviation_exists` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="MP", exclude_id=F1.id)`.

**Then**
1. returns: `result is False`.

### FAC-CA-16 — excluding another factory still gives True
- **Rules:** `_check_abbreviation_exists` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="MP", exclude_id=F2.id)`.

**Then**
1. returns: `result is True`.

### FAC-CA-17 — an explicit exclude_id=None ignores nothing
- **Rules:** `_check_abbreviation_exists` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="MP", exclude_id=None)`.

**Then**
1. returns: `result is True`.

### FAC-CA-18 — a workspace without factories gives False
- **Rules:** `_check_abbreviation_exists` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No factories exist.

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="MP")`.

**Then**
1. returns: `result is False`.

### FAC-CA-19 — a factory whose name equals the abbreviation looked for does not match
- **Rules:** `_check_abbreviation_exists` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.
2. F2 = factory, `name "Second"`, `abbreviation "SC"`.

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="Main Plant")`.

**Then**
1. returns: `result is False`.

### FAC-CA-20 — the abbreviation check does not read a capped page of the workspace
- **Rules:** `_check_abbreviation_exists` R5 [BUG-893]
- **Kind:** bug
- **Expect:** xfail BUG-893
- **Fails today on:** Then 2 (the only SELECT on `factories` filters on `workspace_id` and has a `LIMIT`)
- **Author:** claude — statement recorder

**Given**
1. F1 = factory, `name "Main Plant"`, `abbreviation "MP"`.

**When**
- `result = M._check_abbreviation_exists(db, workspace_id=W1.id, abbreviation="MP")`, with the statement recorder on.

**Then**
1. returns: `result is True`.
2. statement: some recorded `SELECT` on `factories` has `abbreviation` in its `WHERE` clause (before any `ORDER BY` or `LIMIT`), or no recorded `SELECT` on `factories` has a `LIMIT`. The alarm for the fix of BUG-893 on the abbreviation; when it XPASSes, remove the markers of FAC-C-26, U-49, CA-14 in the same step.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Overview "Integration-only behavior": `skip >= 0`, `1 <= limit <= 1000` | `GET /factories/` (endpoint) | 422 for `skip=-1`, `limit=0`, `limit=1001`. Here the manager lets Postgres reject negatives and `limit=0` returns `[]` by rule (`search_factories` R9). |
| `search_factories` R5 [BUG-901], second half — `include_deleted` reachable from the API (FU-3) | `FactoryService.get_factories` / `GET /factories/`; `FactoryResponse` | The option is passed through, and a listed deleted factory can be told from a live one. Here only the manager's own behaviour has cards (they pass today). |
| `get_factory` R4 [BUG-897] — `include_deleted` exposed on `GET /factories/{id}/` (FU-3) | `FactoryService.get_factory` / endpoint | The option is passed through; 404 for a deleted factory by default at the API. |
| `create_factory` R7 / R7a, `update_factory` R10 / R10a — the 422 a schema `ValidationError` becomes | `POST /factories/`, `PUT /factories/{id}/` | Status 422 and that nothing is written. Here the schema is built directly. |
| Returns / Side effects of the three writers — "not committed"; commit and rollback | `FactoryService` | Commit on success, rollback on error, the re-read of the row. Here "flushed" is seen through re-reads; "not committed" has one card per writer (FAC-C-36, FAC-U-52, FAC-D-14); the readers have none. |
| `delete_factory` R5 (Q2) — the machines, sections and stock of a deleted factory are hidden while it is deleted (BUG-890, BUG-891, BUG-882) | machine DAO spec / inventory specs | The hiding itself. Here only "their rows are untouched" is tested. |
| `delete_factory` R5a, R5b [BUG-1331] — the 400 of a refused delete, its body with the blockers (FU-6); showing it is BUG-1332, no backend test | `FactoryService.delete_factory` / `DELETE /factories/{id}/` | `ValueError` becomes a 400 carrying message and blockers, not a 500. Here the manager's `ValueError` is tested. |
| `delete_factory` R5 (Q2) — stock rows, products, projects, work orders and sales orders of a deleted factory | integration tests of `DELETE /factories/{id}/` (or this spec once it gives those models' columns — Spec gap 2) | Each kind of row is left untouched and none blocks the delete. |
| Q3 / FU-1 — `DAOFactory.restore` has no caller | factory DAO spec (`app/dao/factory.py`) | The restore itself, and `is_active` on `soft_delete` / `restore`. |
| Q3 / FU-2 — "restore factory" does not exist | factory manager / service / endpoint (feature to build) | 404, the answer for a factory that is not deleted, who restored, 409 when the name or abbreviation was given away in the meantime. |
| Q4 / FU-4 — `max_factories`, `max_machines`, `max_projects` are read by no code | product decision / workspace and subscription review | Enforcing the plan limit. Here "not consulted" is one card (`create_factory` R9). |
| FU-5 — managers that look a factory up through the raw DAO lookups | the nine managers named in the spec's FU-5 | Whether each refuses a soft-deleted factory. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Status line | Closed: the spec was APPROVED on 2026-10-11; all pilot defaults were accepted unchanged. | Nothing to do. |
| 2 | `delete_factory` R5; Facts for the test designer | R5 names "machines, factory sections and stock rows", but the Facts give the required columns of `Machine` and `FactorySection` only — nothing for `inventory` (or the other eight tables that point at a factory). | No stock-row card. R5 is tested with machines (FAC-D-09) and sections (FAC-D-10); the rest is deferred. |
| 3 | `delete_factory` R5 ("no deletion stamp") | The names of the deletion-stamp columns of `machines` and `factory_sections` are not given. | Not blocking: the two cards assert `is_deleted`, `is_active` and unchanged(row), which covers every column. |
| 4 | `search_factories` R3 [BUG-899]; Notes "Order" | The Notes say today's order is insertion order "on the test database", but — unlike the cap note — not whether that is deterministic enough for a strict xfail. (The machine DAO cards for the same kind of bug are non-strict.) | FAC-S-47 and S-48 are **strict** xfail: only freshly inserted rows, intended order different from insertion order and from its reverse. FAC-S-49, S-50 and S-51 are **non-strict** (changed after verification round 1): a page of the physical row order can equal the intended page by accident. If S-47 or S-48 ever passes today, it must become non-strict too. | **Revision 4 (2026-11-02):** the eight 100-row cards FAC-C-25, C-26, U-48, U-49, S-15, S-16, CN-14, CA-14 were strict and went red in about 1 run in 10 of repeated runs. Under every forced order except ascending id (id descending, newest first, newest two first, live first, hash) all eight XPASS and no other card changes outcome, and a real `VACUUM factories` between Given inserts reproduces it; so they are non-strict, and FAC-CN-20, CA-20, S-54 (with S-52) are the strict, order-independent alarms.
| 5 | Facts table (`created_at`, `updated_at`) | Whether the two columns are naive or timezone-aware is stated only for `deleted_at`. | Not blocking: `updated_at` is asserted only as `is None` / `is not None`; `created_at` is compared with a snapshot taken before the call; no Given sets either column. |
| 6 | `update_factory` R2 × R3, `delete_factory` R1 × R2 | The answer for a soft-deleted factory of another workspace is not stated (404 by R2 / R1, or 400 by R3 / R2). | Designed as 404 (FAC-U-09, D-07): R2 / R1 say "a factory of another workspace" without a condition on its state. |
| 7 | `update_factory`, `delete_factory` — `is_active` | No rule says what the two writers do with a live factory whose `is_active` is `False`; only the Facts say "nothing in this manager reads or writes `is_active`". | Designed from that sentence: such a factory is renamed / deleted like any other and stays inactive (FAC-U-38, D-04). |
| 8 | `update_factory` R11 [BUG-900] × R16 | R16 fails "given a change that stamps" the unknown user; what a no-op by an unknown `user_id` does after the BUG-900 fix is only implied. | Designed as: it succeeds and stamps nothing (FAC-U-42, xfail BUG-900). Remove the card if the fix is meant to validate the user anyway. |
| 9 | Errors tables of `update_factory` and `delete_factory` | The foreign-key constraint names are given for `create_factory` only. | Not blocking: the update and delete cards assert `IntegrityError` and `ForeignKeyViolation` only. |
| 10 | Review Q1 — one bug ID for two fields | The abbreviation rules share BUG-894 / BUG-895 / BUG-896 with the name rules. A fix of the name alone leaves the abbreviation cards failing under the same ID, and a strict xfail cannot say which half is fixed. | Not blocking: name and abbreviation always have separate cards. |
| 11 | `create_factory` R3 / R4, `update_factory` R6 / R7 × BUG-894 × BUG-896 | A duplicate that differs only by outer whitespace is caught by either fix (schema trim, or trimmed compare); only the message text needs BUG-896. | The four such cards (FAC-C-22, U-45, C-24, U-47) are marked `xfail BUG-896` and cite both rules: they keep failing until BUG-896 is fixed, whatever happens to BUG-894. |
| 12 | `get_factory` R4 | Not stated: `include_deleted=True` with an id that no factory has (presumably 404). | No card; the other-workspace side of R4 has one (FAC-G-08). |
| 13 | `search_factories` R3 | "Then `id` ascending" can only be observed with two factories of equal normalised name, which the Notes allow only when all but one are soft-deleted. | One card, with `include_deleted=True` (FAC-S-48); a live-only tie cannot be built. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_factory` | R1 | FAC-C-01, C-03, C-13 |
| `create_factory` | R2 | FAC-C-02 |
| `create_factory` | R3 | FAC-C-04, C-21 (xfail), C-22 (xfail), C-25 (xfail) |
| `create_factory` | R4 | FAC-C-05, C-23 (xfail), C-24 (xfail), C-26 (xfail) |
| `create_factory` | R5 | FAC-C-06, C-07 |
| `create_factory` | R6 | FAC-C-08, C-09, C-10, C-11 |
| `create_factory` | R7 [BUG-896] | FAC-C-12 (xfail), C-13, C-14 (xfail), C-15 (xfail), C-16 (xfail), C-20, C-22 (xfail) |
| `create_factory` | R7a [BUG-896] (Q1) | FAC-C-13, C-17 (xfail), C-18 (xfail), C-19 (xfail), C-20, C-24 (xfail) |
| `create_factory` | R8 [BUG-895] | FAC-C-27 (xfail), C-28, C-29, C-31 (xfail) |
| `create_factory` | R8a [BUG-895] (Q1) | FAC-C-28, C-29, C-30 (xfail), C-32 (xfail) |
| `create_factory` | R9 (Q4) | FAC-C-33 |
| `create_factory` | R10 | FAC-C-34, C-35 |
| `create_factory` | Errors row 1 (name taken) | FAC-C-04, C-21 (xfail), C-31 (xfail) |
| `create_factory` | Errors row 2 (abbreviation taken) | FAC-C-05, C-23 (xfail), C-32 (xfail) |
| `create_factory` | Errors row 3 [BUG-896] (blank value, schema) | FAC-C-14 (xfail), C-15 (xfail), C-16 (xfail), C-18 (xfail), C-19 (xfail) |
| `create_factory` | Errors row 4 (`user_id` no profile) | FAC-C-34 |
| `create_factory` | Errors row 5 (`workspace_id` no workspace) | FAC-C-35 |
| `create_factory` | Side effects | FAC-C-01, C-04, C-36 |
| `update_factory` | R1 | FAC-U-04 |
| `update_factory` | R2 | FAC-U-05, U-09 |
| `update_factory` | R3 | FAC-U-06, U-07, U-08 |
| `update_factory` | R4 | FAC-U-01, U-02, U-03, U-43 |
| `update_factory` | R5 | FAC-U-10, U-11, U-12, U-13, U-17, U-22 (xfail) |
| `update_factory` | R6 | FAC-U-14, U-44 (xfail), U-45 (xfail), U-48 (xfail) |
| `update_factory` | R7 | FAC-U-15, U-16, U-17, U-46 (xfail), U-47 (xfail), U-49 (xfail) |
| `update_factory` | R8 | FAC-U-18 |
| `update_factory` | R9 | FAC-U-02, U-19, U-20, U-30, U-35, U-36 |
| `update_factory` | R10 [BUG-896] | FAC-U-21 (xfail), U-22 (xfail), U-23 (xfail), U-24 (xfail), U-25 (xfail), U-29, U-45 (xfail) |
| `update_factory` | R10a [BUG-896] (Q1) | FAC-U-26 (xfail), U-27 (xfail), U-28 (xfail), U-29, U-47 (xfail) |
| `update_factory` | R11 [BUG-900] | FAC-U-01, U-02, U-31 (xfail), U-32 (xfail), U-33 (xfail), U-34 (xfail), U-35, U-36, U-37, U-42 (xfail) |
| `update_factory` | R12 | FAC-U-01, U-02, U-37 |
| `update_factory` | R13 | FAC-U-38, U-43 |
| `update_factory` | R14 [BUG-895] | FAC-U-50 (xfail) |
| `update_factory` | R14a [BUG-895] (Q1) | FAC-U-51 (xfail) |
| `update_factory` | R15 | FAC-U-39, U-40 |
| `update_factory` | R16 | FAC-U-41, U-42 (xfail) |
| `update_factory` | Errors row 1 (not found / other workspace) | FAC-U-04, U-05 |
| `update_factory` | Errors row 2 (soft-deleted) | FAC-U-06 |
| `update_factory` | Errors row 3 (name taken) | FAC-U-14, U-44 (xfail), U-50 (xfail) |
| `update_factory` | Errors row 4 (abbreviation taken) | FAC-U-15, U-46 (xfail), U-51 (xfail) |
| `update_factory` | Errors row 5 [BUG-896] (blank value, schema) | FAC-U-23 (xfail), U-24 (xfail), U-25 (xfail), U-27 (xfail), U-28 (xfail) |
| `update_factory` | Errors row 6 (`user_id` no profile) | FAC-U-41 |
| `update_factory` | Side effects | FAC-U-01, U-14, U-38, U-52 |
| `get_factory` | R1 | FAC-G-01, G-02, G-05, G-09 (xfail) |
| `get_factory` | R2 | FAC-G-03, G-04 |
| `get_factory` | R3 [BUG-897] | FAC-G-06 (xfail) |
| `get_factory` | R4 [BUG-897] | FAC-G-07 (xfail), G-08 (xfail), G-09 (xfail) |
| `get_factory` | Errors row 1 (404) | FAC-G-03, G-04, G-06 (xfail) |
| `get_factory` | Side effects | FAC-G-01 |
| `search_factories` | R1 | FAC-S-01, S-02, S-03, S-04, S-05, S-09 |
| `search_factories` | R2 [BUG-898] | FAC-S-11 … S-16 (non-strict xfail), S-52, S-54 (strict xfail, statement recorder), S-17 |
| `search_factories` | R3 [BUG-899] | FAC-S-47 (xfail), S-48 (xfail), S-49 (xfail), S-50 (xfail), S-51 (xfail) |
| `search_factories` | R4 [BUG-898] | FAC-S-06, S-07, S-10, S-11, S-13 (non-strict xfail), S-15 (xfail), S-52 (strict xfail, statement recorder), S-17, D-11 |
| `search_factories` | R5 [BUG-901] | FAC-S-08, S-09, S-38, S-48 (xfail), D-11 |
| `search_factories` | R6 | FAC-S-54 (xfail), S-12 (xfail), S-16 (xfail), S-20, S-21, S-22, S-23, S-24, S-25, S-51 (xfail) |
| `search_factories` | R6a (HR-8) | FAC-S-26, S-27, S-28, S-29 |
| `search_factories` | R7 [BUG-902] (P1) | FAC-S-01, S-30, S-31, S-32 (xfail), S-33 (xfail), S-34 (xfail), S-35 (xfail), S-36 (xfail) |
| `search_factories` | R8 | FAC-S-37, S-38 |
| `search_factories` | R9 | FAC-S-07, S-18, S-19, S-23, S-39, S-40, S-41, S-42, S-43, S-44, S-45, S-46, S-49 (xfail), S-50 (xfail) |
| `search_factories` | Errors row 1 (negative `limit`) | FAC-S-45 |
| `search_factories` | Errors row 2 (negative `skip`) | FAC-S-46 |
| `search_factories` | Side effects | FAC-S-06 |
| `delete_factory` | R1 | FAC-D-05, D-06, D-07 |
| `delete_factory` | R2 | FAC-D-08 |
| `delete_factory` | R3 | FAC-D-01, D-04, D-17 |
| `delete_factory` | R4 | FAC-D-01, D-02, D-03, D-04 |
| `delete_factory` | R5 (Q2) | FAC-D-09, D-10, D-30, D-31, D-32 |
| `delete_factory` | R5a [BUG-1331] | FAC-D-18, D-19, D-20, D-22, D-24, D-27, D-35, D-36, D-37 (xfail); D-28, D-29, D-30, D-31, D-33, D-34, D-40, D-41, D-42 |
| `delete_factory` | R5b [BUG-1331] | FAC-D-18, D-19, D-20, D-21, D-23, D-24, D-35, D-36, D-37, D-38, D-39 (xfail) |
| `delete_factory` | R5c [BUG-1331] | FAC-D-25, D-26 (xfail) |
| `delete_factory` | R6 | FAC-D-11, D-12, D-13 |
| `delete_factory` | R7 | FAC-D-14, D-15, D-17 |
| `delete_factory` | R8 | FAC-D-16, D-27 (xfail) |
| `delete_factory` | Errors row 1 (not found / other workspace) | FAC-D-05, D-06 |
| `delete_factory` | Errors row 2 (already deleted) | FAC-D-08 |
| `delete_factory` | Errors row 3 (`user_id` no profile) | FAC-D-16 |
| `delete_factory` | Errors row 4 [BUG-1331] (open batch) | FAC-D-18, D-19 (xfail) |
| `delete_factory` | Errors row 5 [BUG-1331] (cross-workspace row) | FAC-D-35, D-36, D-37, D-38, D-39 (xfail) |
| `delete_factory` | Side effects | FAC-D-15 |
| `_check_name_exists` | R1 | FAC-C-04, CN-01, CN-02, CN-04, CN-06 |
| `_check_name_exists` | R2 | FAC-C-08, U-40, CN-03, CN-04 |
| `_check_name_exists` | R3 | FAC-C-09, U-39, D-12, CN-05, CN-06 |
| `_check_name_exists` | R4 [BUG-894] | FAC-C-21 (xfail), C-22 (xfail), U-44 (xfail), U-45 (xfail), CN-07 (xfail), CN-08 (xfail), CN-09 (xfail), CN-10 (xfail), CN-11, CN-12 |
| `_check_name_exists` | R5 [BUG-893] | FAC-C-25, U-48, CN-14 (non-strict xfail), CN-20 (strict xfail, statement recorder), CN-13 |
| `_check_name_exists` | R6 | FAC-U-12, U-14, CN-01, CN-15, CN-16, CN-17 |
| `_check_name_exists` | R7 | FAC-C-10, CN-18, CN-19 |
| `_check_abbreviation_exists` | R1 | FAC-C-05, CA-01, CA-02, CA-04, CA-06 |
| `_check_abbreviation_exists` | R2 | FAC-C-08, U-40, CA-03, CA-04 |
| `_check_abbreviation_exists` | R3 | FAC-C-09, U-39, D-12, CA-05, CA-06 |
| `_check_abbreviation_exists` | R4 [BUG-894] (Q1) | FAC-C-23 (xfail), C-24 (xfail), U-46 (xfail), U-47 (xfail), CA-07 (xfail), CA-08 (xfail), CA-09 (xfail), CA-10 (xfail), CA-11, CA-12 |
| `_check_abbreviation_exists` | R5 [BUG-893] | FAC-C-26, U-49, CA-14 (non-strict xfail), CA-20 (strict xfail, statement recorder), CA-13 |
| `_check_abbreviation_exists` | R6 | FAC-U-13, U-15, CA-01, CA-15, CA-16, CA-17 |
| `_check_abbreviation_exists` | R7 | FAC-C-11, CA-18, CA-19 |
