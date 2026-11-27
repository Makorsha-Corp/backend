# Test cases — `app/dao/app_settings.py`

> **Spec:** `tests/unit/dao/app_settings.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open). Q1 was decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `app_settings.verify.md` (case-missing Findings 1, 2, 3; recipes R-1, R-2, R-3): Finding 1 → ASG-GN-14, GN-15, GN-16; Finding 2 → ASG-GN-17, GN-18; Finding 3 → ASG-GN-19. Conventions gain the `session:` line. No existing Given, When, Then or ID changed, none retired.
> **Counts:** 23 cases · 21 expected-to-pass · 2 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `get_by_name` 19 · `create` 4 (2 bug).
- **Depth:** lighter target (skill step 1a). A named on/off flag: one exact read, no stock, money or order state. Each input R3 names still gets a card.
- **Expected-to-fail:** BUG-1225 2, both strict (ASG-CR-01, CR-02). R4 has no card of its own: its only content is the two cards of N1, N2, and R3's exact cards stay green.
- **Commit spies:** none. `get_by_name` only reads; `create` is spied by BASE-C-05.
- **Notable design choices:**
  - No order card and no recorder: BUG-1213 is superseded, the index leaves one candidate.
  - GN-03 puts the other workspace's row first in `id` order, so a lookup by name alone fails it.
  - CR-01, CR-02 go through `create`, the base method the spec names. A dict is used: the base spec's way to pass `workspace_id`.
  - No pass card stores two rows of one name, so none breaks when the index arrives.
  - No `Author:` lines. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `ASG` = `app/dao/app_settings.py`. `GN` get_by_name · `CR` inherited `BaseDAO.create` on this table.

**Actors and fixed values.**
- `dao` = the singleton `app_settings_dao` (`from app.dao.app_settings import app_settings_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `AppSettings` = `app.models.app_settings.AppSettings`.

**Externals.** None. Nothing is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from the defaults below. A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.
- W1, W2 = two `workspaces` rows from `make_workspace`; they exist in every test and need no Given line.
- **setting** = `AppSettings(workspace_id=W1.id, name="feat", enabled=True)`. After the word "but" the card lists every column that differs. No setting exists unless the card's Given lists it.
- **Never** give two rows of one workspace one name, or names that differ only in case or outer spaces, except in the cards about exactly that: BUG-1225's index would make the Given fail.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line). **unchanged(X) except `c`, …** = the same, leaving out the columns named.
- **nothing written** = the number of `app_settings` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P after the call, on the object itself. `pending: len(db.new) == 1` checks that P is the only object waiting in the session.
- A `session:` line is a check on the session object.
- `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the When: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on it.

**Race simulations.** None in this module.

## `DAOAppSettings.get_by_name`

### ASG-GN-01 — returns the row with that name, not the workspace's first row
- **Rules:** `get_by_name` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = setting, but `name "alpha"`, `enabled False`.
2. A = setting.

**When**
- `result = dao.get_by_name(db, name="feat", workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, AppSettings)`.
2. returns: `result.id == A.id`.
3. returns: `result.name == "feat"`, `result.workspace_id == W1.id`.
4. returns: `result.enabled is True`.

### ASG-GN-02 — a switched-off flag is returned too
- **Rules:** `get_by_name` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = setting, but `enabled False`.

**When**
- `result = dao.get_by_name(db, name="feat", workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.enabled is False`.

### ASG-GN-03 — an earlier row of the same name in another workspace is not returned
- **Rules:** `get_by_name` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = setting, but `workspace_id W2.id`.
2. A = setting.

**When**
- `result = dao.get_by_name(db, name="feat", workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.workspace_id == W1.id`.

### ASG-GN-04 — the name under another workspace returns None
- **Rules:** `get_by_name` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = dao.get_by_name(db, name="feat", workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### ASG-GN-05 — workspace_id=0 returns None
- **Rules:** `get_by_name` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = dao.get_by_name(db, name="feat", workspace_id=0)`.

**Then**
1. returns: `result is None`.

### ASG-GN-06 — capitals do not find a lower-case name
- **Rules:** `get_by_name` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = dao.get_by_name(db, name="FEAT", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ASG-GN-07 — a leading space finds nothing
- **Rules:** `get_by_name` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = dao.get_by_name(db, name=" feat", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ASG-GN-08 — a trailing space finds nothing
- **Rules:** `get_by_name` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = dao.get_by_name(db, name="feat ", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ASG-GN-09 — % is no wildcard
- **Rules:** `get_by_name` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = dao.get_by_name(db, name="fe%", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ASG-GN-10 — an empty name returns None
- **Rules:** `get_by_name` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = dao.get_by_name(db, name="", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ASG-GN-11 — a None name returns None
- **Rules:** `get_by_name` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = dao.get_by_name(db, name=None, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ASG-GN-12 — writes nothing: a pending row stays pending and is not found
- **Rules:** `get_by_name` R3, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = setting.
2. `P = AppSettings(workspace_id=W1.id, name="pending", enabled=True)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_name(db, name="pending", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. nothing written: nothing written.
6. unchanged: unchanged(A).
7. statement: `written == []`.

### ASG-GN-13 — writes nothing: a read that finds its row leaves the session as it was
- **Rules:** `get_by_name` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = setting.
2. `P = AppSettings(workspace_id=W1.id, name="pending", enabled=True)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_name(db, name="feat", workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. nothing written: nothing written.
5. statement: `written == []`.

### ASG-GN-14 — the start of a name finds nothing
- **Rules:** `get_by_name` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = dao.get_by_name(db, name="fe", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ASG-GN-15 — the end of a name finds nothing
- **Rules:** `get_by_name` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = dao.get_by_name(db, name="at", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ASG-GN-16 — _ is no wildcard
- **Rules:** `get_by_name` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = dao.get_by_name(db, name="fe_t", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ASG-GN-17 — a stored name in another case is not found: the stored side is not normalised
- **Rules:** `get_by_name` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting, but `name "Feat"`.

**When**
- `result = dao.get_by_name(db, name="feat", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ASG-GN-18 — a stored name with a space is not found: the stored side is not trimmed
- **Rules:** `get_by_name` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting, but `name " feat"`.

**When**
- `result = dao.get_by_name(db, name="feat", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ASG-GN-19 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_name` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = setting.
2. B = setting, but `name "beta"`.
3. `B.enabled = False` (not flushed).

**When**
- `result = dao.get_by_name(db, name="feat", workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.

## Inherited `BaseDAO.create` on `app_settings`

### ASG-CR-01 — a second row of one name in one workspace is refused
- **Rules:** `create` N1 [BUG-1225]; `get_by_name` R4 [BUG-1225]
- **Kind:** bug
- **Expect:** xfail BUG-1225
- **Fails today on:** Then 1 (no error is raised: the second row is stored)

**Given**
1. A = setting.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": "feat", "enabled": False})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `app_settings` has exactly 1 row with `workspace_id == W1.id` and `name == "feat"`.
4. unchanged: unchanged(A).

### ASG-CR-02 — the compare is case-insensitive after trimming
- **Rules:** `create` N2 [BUG-1225]; `get_by_name` R4 [BUG-1225]
- **Kind:** bug
- **Expect:** xfail BUG-1225
- **Fails today on:** Then 1 (no error is raised: both rows are stored)

**Given**
1. A = setting, but `name "Feat"`.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": " feat ", "enabled": False})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `app_settings` has exactly 1 row with `workspace_id == W1.id`.
4. unchanged: unchanged(A).

### ASG-CR-03 — the same name in another workspace is stored
- **Rules:** `create` N1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W2.id, "name": "feat", "enabled": False})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W2.id`, `name == "feat"`, `enabled is False`.
3. unchanged: unchanged(A).

### ASG-CR-04 — another name in the same workspace is stored
- **Rules:** `create` N1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "feat two", "enabled": False})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W1.id`, `name == "feat two"`.
3. unchanged: unchanged(A).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-1225 — a duplicate through the API answers 409 | `AppSettingsService`, `POST /app-settings/` | The DAO raises `IntegrityError`; the API's answer is that layer's. |
| BUG-1225 — rows that already repeat a name are cleaned up before the index | the migration or a script | Not a unit test. |
| BUG-1213 (HR-6) — superseded by BUG-1225 | this file, ASG-CR-01, CR-02 | One candidate under the index; no order card. |
| FU-1 — a name of `"   "` is stored (HR-1, as BUG-004) | `AppSettingsCreate`, `app/schemas/app_settings.py` | Schema rule; that spec owns it. |
| FU-1 — HR-6 display order of `GET /app-settings/`; BUG-1217 `limit` | `AppSettingsService` | Not this DAO's. |
| Generic behavior of inherited `get_by_workspace`, `get_by_id_and_workspace`, `create`, `update`, `remove` | `tests/unit/dao/base.spec.md` / `base.cases.md` | Commit spies: BASE-C-05, BASE-U-12, BASE-R-02. |
| Module singleton `app_settings_dao` | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes: keyword-only parameters | Stated as a note, not as a rule. | No card, as in `work_order_approver.cases.md` gap 1. |
| 2 | `get_by_name` R4 | Holds no behavior of the lookup beyond R3 and `create` N1, N2. | Covered by ASG-CR-01, CR-02. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_name` | Returns | ASG-GN-01 |
| `get_by_name` | R1 | ASG-GN-01, ASG-GN-02 |
| `get_by_name` | R2 | ASG-GN-03, ASG-GN-04, ASG-GN-05 |
| `get_by_name` | R3 | ASG-GN-06, ASG-GN-07, ASG-GN-08, ASG-GN-09, ASG-GN-10, ASG-GN-11, ASG-GN-12, ASG-GN-14, ASG-GN-15, ASG-GN-16, ASG-GN-17, ASG-GN-18 |
| `get_by_name` | R4 | ASG-GN-17, ASG-GN-18 |
| `get_by_name` | R4 [BUG-1225] | ASG-CR-01, ASG-CR-02 |
| `get_by_name` | Side effects | ASG-GN-12, ASG-GN-13, ASG-GN-19 |
| `create` | N1 | ASG-CR-03, ASG-CR-04 |
| `create` | N1 [BUG-1225] | ASG-CR-01 |
| `create` | N2 [BUG-1225] | ASG-CR-02 |
