# Test cases — `app/dao/item_tag.py`

> **Spec:** `tests/unit/dao/item_tag.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-10-17); every answer (P1, P2, Q1, Q2 and the house-rule lines BUG-929, BUG-930, BUG-100) was decided by Claude under the reviewer's delegation, so nothing is provisional.
> **Counts:** 93 cases · 81 expected-to-pass · 12 expected-to-fail (bugs) · 9 deferred (ITG-DEC-16 added 2026-11-27 for BUG-3302)

## Reviewer summary
- **Per callable:** `get_by_code_in_workspace` 17 · `get_system_tags_in_workspace` 10 (3 bug) · `get_active_tags_in_workspace` 13 (3 bug) · `increment_usage_count` 13 (1 bug) · `decrement_usage_count` 16 (3 bug) · inherited `BaseDAO` methods on `ItemTag` 24 (2 bug).
- **Expected-to-fail by bug:** BUG-929 3 (ITG-SYS-08, SYS-09 non-strict; SYS-10 strict, statement recorder) · BUG-930 3 (ITG-ACT-11, ACT-12 non-strict; ACT-13 strict, statement recorder) · BUG-931 3 (ITG-INC-11, DEC-13, DEC-14 — strict) · BUG-100 2 (ITG-INH-18 non-strict; INH-19 strict, statement recorder) · BUG-3302 1 (ITG-DEC-16 strict).
- **Delegated answers and the cards that rest on them:** P1 (a deleted tag is found by its code) — ITG-CODE-15. P2 (the counters work on a deleted tag) — ITG-INC-06, DEC-09. Q2 (unknown / foreign tag → `None`, no error) — ITG-INC-03, INC-04, DEC-06, DEC-07. Q1 / BUG-931 — ITG-INC-11, DEC-13, DEC-14 (pass control ITG-INC-12).
- **Notable design choices:**
  - Row order (BUG-929, BUG-930, BUG-100): no pass card and no strict card depends on physical row order or on the database collation. List cards compare `sorted(ids(result))`, sizes, membership or `[]`. Two pass cards do check an order that `ORDER BY` already gives today: ITG-ACT-09 (system tags first — compares only the `is_system_tag` flags) and ITG-ACT-10 (single-word, all-lower-case ASCII names, which every collation orders alike).
  - Each of the three queries has one **strict** statement-recorder card asserting an `ORDER BY` with the intended keys (`lower(item_tags.name)` and `item_tags.id`; for the generic list only `item_tags.id`): ITG-SYS-10, ACT-13, INH-19.
  - BUG-930 "alpha" before "Alpha" (ITG-ACT-11) is **non-strict** although it is deterministic on the test database (`English_United States.1252` sorts "alpha" first): the result depends on the server's collation, and a server whose collation puts capitals first within a letter would make a strict card XPASS while the bug is still there. The strict alarm is ITG-ACT-13, which does not depend on the server.
  - BUG-931 uses the spec's stale-object recipe (flush with 3, change the stored value with an `UPDATE` statement in the same transaction, do not expire): deterministic → strict. Never two transactions. ITG-INC-12 is the pass control (object expired first → 11).
  - "Flushed" is shown with `stored_count` (a column query that does not expire the object); "flushes everything pending" / "flushes nothing at 0" with an unflushed rename and a `re-read` (which discards unflushed changes): ITG-INC-10, DEC-04, DEC-12.
  - Cards marked `Author: claude` (16): bulk setup (101 rows) — ITG-SYS-07, ACT-08; non-strict xfail — SYS-08, SYS-09, ACT-11, ACT-12, INH-18; statement recorder — SYS-10, ACT-13, INH-19; a direct `UPDATE` statement in the Given (stale object) — INC-11, INC-12, DEC-13, DEC-14; savepoint rollback and commit spy — INC-13, DEC-15.
- **Needs a decision:** None blocking. See Spec gaps 1 (schema module path assumed), 4 (no cascade card for `remove`), 5 (recorder cards name `lower(...)` as the case-insensitive key).


## Conventions for this module

**IDs.** `ITG` = `app/dao/item_tag.py`. `CODE` get_by_code_in_workspace · `SYS` get_system_tags_in_workspace · `ACT` get_active_tags_in_workspace · `INC` increment_usage_count · `DEC` decrement_usage_count · `INH` inherited `BaseDAO` methods on `ItemTag`.

**Actors and fixed values.**
- `dao` = the singleton `item_tag_dao` (`from app.dao.item_tag import item_tag_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns.
- W1, W2 = two `workspaces` rows. They exist in every test and need no Given line. No `item_tags` row exists unless the card's Given lists it.
- `ItemTag` = `app.models.item_tag.ItemTag`. `ItemTagCreate`, `ItemTagUpdate` = the schemas of `app.schemas.item_tag` (Spec gap 1). `select`, `text` = `sqlalchemy.select`, `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked.

**Given rows.** Rows are inserted directly into the table (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush.
- **tag** = `item_tags` row built with `ItemTag`: `workspace_id W1.id`, `is_system_tag False`, `is_active True`, `usage_count 0`, `color None`, `icon None`, `description None`, `created_by None`; `created_at` left to the model default. The card always gives `name` and `tag_code`; after the word "but" it lists every other column that differs.
- **system tag** = a tag, but `is_system_tag True`. **deleted** (said of a tag) = `is_active False`.
- A Given line written as code (`T1.name = "Lock Nut"`) is a step to run exactly as written, at that place in the order. A code line without `db.flush()` leaves the change pending (not flushed).

**Named checks.**
- **ids(result)** = `[t.id for t in result]`, **names(result)** = `[t.name for t in result]` — lists in the order returned (the order is part of the check). `sorted(ids(result)) == [T1.id, T2.id]` is used where the order is not part of the check; the right-hand ids are written in Given order, which is ascending id order.
- **stored_count(T)** = `db.scalar(select(ItemTag.usage_count).where(ItemTag.id == T.id))` — reads the database value without expiring or refreshing the object T. A pending (unflushed) change is not seen.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values. (Expiring discards unflushed changes, so a re-read that shows a new value also proves it was flushed.)
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line, before the call).
- **nothing written** = the number of `item_tags` rows (all workspaces) equals its value before the call.
- `count:` lines count `item_tags` rows in all workspaces, with the filter stated.
- **close to now** = `abs(datetime.now(timezone.utc).replace(tzinfo=None) - value) < timedelta(minutes=5)` (Spec gap 6).
- `raises: DataError` = `sqlalchemy.exc.DataError`; `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the call for both: `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards (the savepoint is rolled back). `NotNullViolation`, `ForeignKeyViolation`, `StringDataRightTruncation` = classes of `psycopg2.errors`.
- Further `raises:` lines of the same card are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; the harness adds the marker. Every xfail in this module is strict, except the five cards that rest on physical row order or on the server's collation — ITG-SYS-08, SYS-09, ACT-11, ACT-12, INH-18 — marked `(non-strict)` on their Expect line (`pytest.mark.xfail(strict=False, …)`).

**Stored value changed behind the object** (cards marked Author: claude only). The card's Given runs `db.execute(text("update item_tags set usage_count = <n> where id = :i"), {"i": T1.id})` after T1 was flushed; T1 is not expired, so the object still holds its old `usage_count`. One transaction, one session — never a second connection.

**Rolled back** (cards marked Author: claude only). `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**Statement recorder** (cards marked Author: claude only). The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` sent; `order_part` = the text of `sql` after `ORDER BY` (`""` when there is none). A `statement:` line is a check on these texts.

**Race simulations.** None in this module.


## `ItemTagDAO.get_by_code_in_workspace`

### ITG-CODE-01 — returns the tag of the workspace with that code and writes nothing
- **Rules:** `get_by_code_in_workspace` R1, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Raw Material"`, `tag_code "raw_material"`.
2. T2 = tag, `name "Machine Part"`, `tag_code "machine_part"`.

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=W1.id, tag_code="raw_material")`.

**Then**
1. returns: `isinstance(result, ItemTag)`.
2. returns: `result.id == T1.id`.
3. nothing written: nothing written.
4. unchanged: unchanged(T1).

### ITG-CODE-02 — a tag of another workspace with that code is not returned
- **Rules:** `get_by_code_in_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Raw Material"`, `tag_code "raw_material"`.
2. T9 = tag, `name "Spare Part"`, `tag_code "spare_part"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=W1.id, tag_code="spare_part")`.

**Then**
1. returns: `result is None`.

### ITG-CODE-03 — the same code in two workspaces: each workspace gets its own tag
- **Rules:** `get_by_code_in_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Raw Material"`, `tag_code "raw_material"`.
2. T9 = tag, `name "Raw Stock"`, `tag_code "raw_material"`, but `workspace_id W2.id`. (Same code as T1 on purpose.)

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=W2.id, tag_code="raw_material")`.

**Then**
1. returns: `result.id == T9.id`.
2. returns: `result.workspace_id == W2.id`.

### ITG-CODE-04 — an unknown workspace id returns None
- **Rules:** `get_by_code_in_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Raw Material"`, `tag_code "raw_material"`.

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=MISSING, tag_code="raw_material")`.

**Then**
1. returns: `result is None`.

### ITG-CODE-05 — a code differing in the case of some letters returns None
- **Rules:** `get_by_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Raw Material"`, `tag_code "raw_material"`.

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=W1.id, tag_code="Raw_Material")`.

**Then**
1. returns: `result is None`.

### ITG-CODE-06 — an all-capitals code returns None
- **Rules:** `get_by_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Raw Material"`, `tag_code "raw_material"`.

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=W1.id, tag_code="RAW_MATERIAL")`.

**Then**
1. returns: `result is None`.

### ITG-CODE-07 — a leading space returns None
- **Rules:** `get_by_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Raw Material"`, `tag_code "raw_material"`.

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=W1.id, tag_code=" raw_material")`.

**Then**
1. returns: `result is None`.

### ITG-CODE-08 — a trailing space returns None
- **Rules:** `get_by_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Raw Material"`, `tag_code "raw_material"`.

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=W1.id, tag_code="raw_material ")`.

**Then**
1. returns: `result is None`.

### ITG-CODE-09 — a prefix of the code returns None
- **Rules:** `get_by_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Raw Material"`, `tag_code "raw_material"`.

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=W1.id, tag_code="raw")`.

**Then**
1. returns: `result is None`.

### ITG-CODE-10 — the code with one more character returns None
- **Rules:** `get_by_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Raw Material"`, `tag_code "raw_material"`.

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=W1.id, tag_code="raw_material_")`.

**Then**
1. returns: `result is None`.

### ITG-CODE-11 — a LIKE pattern is not a pattern: "raw%" returns None
- **Rules:** `get_by_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Raw Material"`, `tag_code "raw_material"`.

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=W1.id, tag_code="raw%")`.

**Then**
1. returns: `result is None`.

### ITG-CODE-12 — an empty code finds a tag stored with an empty code
- **Rules:** `get_by_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Raw Material"`, `tag_code "raw_material"`.
2. T2 = tag, `name "Blank Mark"`, `tag_code ""`.

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=W1.id, tag_code="")`.

**Then**
1. returns: `result.id == T2.id`.
2. returns: `result.tag_code == ""`.

### ITG-CODE-13 — an empty code returns None when no tag has an empty code
- **Rules:** `get_by_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Raw Material"`, `tag_code "raw_material"`.

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=W1.id, tag_code="")`.

**Then**
1. returns: `result is None`.

### ITG-CODE-14 — a code of None returns None
- **Rules:** `get_by_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Raw Material"`, `tag_code "raw_material"`.

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=W1.id, tag_code=None)`.

**Then**
1. returns: `result is None`.

### ITG-CODE-15 — a deleted tag is found by its code and left as it was
- **Rules:** `get_by_code_in_workspace` R3 (P1), R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. TD = tag, `name "Spare Part"`, `tag_code "spare_part"`, but `is_active False`.

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=W1.id, tag_code="spare_part")`.

**Then**
1. returns: `result.id == TD.id`.
2. returns: `result.is_active is False`.
3. unchanged: unchanged(TD).

### ITG-CODE-16 — a system tag is found by its code
- **Rules:** `get_by_code_in_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = system tag, `name "Raw Material"`, `tag_code "raw_material"`.

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=W1.id, tag_code="raw_material")`.

**Then**
1. returns: `result.id == S1.id`.
2. returns: `result.is_system_tag is True`.

### ITG-CODE-17 — two tags with one code: one of them is returned
- **Rules:** `get_by_code_in_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Bolt Small"`, `tag_code "bolt_part"`.
2. T2 = tag, `name "Bolt Large"`, `tag_code "bolt_part"`. (Same code as T1 on purpose.)

**When**
- `result = dao.get_by_code_in_workspace(db, workspace_id=W1.id, tag_code="bolt_part")`.

**Then**
1. returns: `result.id in {T1.id, T2.id}`.
2. nothing written: nothing written.


## `ItemTagDAO.get_system_tags_in_workspace`

### ITG-SYS-01 — returns a list of the system tags of the workspace, no user tag, and writes nothing
- **Rules:** `get_system_tags_in_workspace` R1, R4, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = system tag, `name "Raw Material"`, `tag_code "raw_material"`.
2. S2 = system tag, `name "Machine Part"`, `tag_code "machine_part"`.
3. T3 = tag, `name "Custom Bin"`, `tag_code "custom_bin"`. (A user tag.)

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [S1.id, S2.id]`.
3. returns: `isinstance(result[0], ItemTag)`.
4. nothing written: nothing written.
5. unchanged: unchanged(S1).

### ITG-SYS-02 — a deleted system tag is not returned
- **Rules:** `get_system_tags_in_workspace` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. S1 = system tag, `name "Raw Material"`, `tag_code "raw_material"`.
2. SD = system tag, `name "Old Seed"`, `tag_code "old_seed"`, but `is_active False`.

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.
2. unchanged: unchanged(SD).

### ITG-SYS-03 — a system tag of another workspace is not returned
- **Rules:** `get_system_tags_in_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = system tag, `name "Raw Material"`, `tag_code "raw_material"`.
2. S9 = system tag, `name "Far Seed"`, `tag_code "far_seed"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### ITG-SYS-04 — the other workspace gets only its own system tag
- **Rules:** `get_system_tags_in_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S1 = system tag, `name "Raw Material"`, `tag_code "raw_material"`.
2. S9 = system tag, `name "Far Seed"`, `tag_code "far_seed"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [S9.id]`.

### ITG-SYS-05 — an unknown workspace id returns an empty list
- **Rules:** `get_system_tags_in_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = system tag, `name "Raw Material"`, `tag_code "raw_material"`.

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### ITG-SYS-06 — a workspace with only user tags and a deleted system tag returns an empty list
- **Rules:** `get_system_tags_in_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Custom Bin"`, `tag_code "custom_bin"`.
2. SD = system tag, `name "Old Seed"`, `tag_code "old_seed"`, but `is_active False`.

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### ITG-SYS-07 — all 101 system tags are returned (no limit)
- **Rules:** `get_system_tags_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (101 rows) outside the Conventions vocabulary

**Given**
1. 101 system tags N1 … N101, inserted in that order; Nk (k = 1 … 101) has `name` = `f"Seed {k:03d}"`, `tag_code` = `f"seed_{k:03d}"`.

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) ==` the 101 ids, ascending.

### ITG-SYS-08 — system tags come back by name, case-insensitive ascending
- **Rules:** `get_system_tags_in_workspace` R3 [BUG-929]
- **Kind:** bug
- **Expect:** xfail BUG-929 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the rows usually come back in insertion order ["Tool", "consumable", "Bolt"] — but the physical row order can match the intended order by accident)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-929")`); the assertion is never weakened

**Given**
1. S1 = system tag, `name "Tool"`, `tag_code "tool"`.
2. S2 = system tag, `name "consumable"`, `tag_code "consumable"`.
3. S3 = system tag, `name "Bolt"`, `tag_code "bolt"`.

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, S2.id, S3.id]`.
2. returns: `names(result) == ["Bolt", "consumable", "Tool"]`.

### ITG-SYS-09 — system tags whose names differ only in case come back in id order
- **Rules:** `get_system_tags_in_workspace` R3 [BUG-929]
- **Kind:** bug
- **Expect:** xfail BUG-929 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the updated row S1 usually comes back after S2, giving [S2.id, S1.id] — but the physical row order can match the intended order by accident)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-929")`); the assertion is never weakened

**Given**
1. S1 = system tag, `name "Alpha"`, `tag_code "alpha_upper"`.
2. S2 = system tag, `name "alpha"`, `tag_code "alpha_lower"`. (The "Alpha" / "alpha" pair is on purpose: the names are equal ignoring case, so only `id` decides. Retire this card if a unique index on tag names is ever added — item tag service FU-1 (c).)
3. S1 is changed after S2 was created: `S1.description = "moved"`, then `db.flush()`. (This usually moves S1 physically behind S2 in the table.)

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, S2.id]`.
2. returns: `ids(result) == [S1.id, S2.id]`.

### ITG-SYS-10 — the system-tag query asks the database for name case-insensitive, then id
- **Rules:** `get_system_tags_in_workspace` R3 [BUG-929]
- **Kind:** bug
- **Expect:** xfail BUG-929
- **Fails today on:** Then 2 (the query has no `ORDER BY`)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order or collation)

**Given**
1. S1 = system tag, `name "Raw Material"`, `tag_code "raw_material"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"lower(item_tags.name)" in order_part`.
4. statement: `"item_tags.id" in order_part`.


## `ItemTagDAO.get_active_tags_in_workspace`

### ITG-ACT-01 — returns a list of the system and user tags of the workspace and writes nothing
- **Rules:** `get_active_tags_in_workspace` R1, R5, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Custom Bin"`, `tag_code "custom_bin"`.
2. T2 = tag, `name "Spare Part"`, `tag_code "spare_part"`.
3. S1 = system tag, `name "Raw Material"`, `tag_code "raw_material"`.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [T1.id, T2.id, S1.id]`.
3. returns: `isinstance(result[0], ItemTag)`.
4. nothing written: nothing written.
5. unchanged: unchanged(T1).

### ITG-ACT-02 — a deleted user tag is not returned
- **Rules:** `get_active_tags_in_workspace` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T1 = tag, `name "Custom Bin"`, `tag_code "custom_bin"`.
2. TD = tag, `name "Obsolete"`, `tag_code "obsolete"`, but `is_active False`.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.
2. unchanged: unchanged(TD).

### ITG-ACT-03 — a deleted system tag is not returned
- **Rules:** `get_active_tags_in_workspace` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T1 = tag, `name "Custom Bin"`, `tag_code "custom_bin"`.
2. SD = system tag, `name "Old Seed"`, `tag_code "old_seed"`, but `is_active False`.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.

### ITG-ACT-04 — a tag of another workspace is not returned
- **Rules:** `get_active_tags_in_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Custom Bin"`, `tag_code "custom_bin"`.
2. T9 = tag, `name "Far Crate"`, `tag_code "far_crate"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.

### ITG-ACT-05 — the other workspace gets only its own tag
- **Rules:** `get_active_tags_in_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Custom Bin"`, `tag_code "custom_bin"`.
2. T9 = tag, `name "Far Crate"`, `tag_code "far_crate"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [T9.id]`.

### ITG-ACT-06 — an unknown workspace id returns an empty list
- **Rules:** `get_active_tags_in_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Custom Bin"`, `tag_code "custom_bin"`.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### ITG-ACT-07 — a workspace without tags returns an empty list
- **Rules:** `get_active_tags_in_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T9 = tag, `name "Far Crate"`, `tag_code "far_crate"`, but `workspace_id W2.id`. (W1 has no tags.)

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### ITG-ACT-08 — all 101 tags are returned (no limit)
- **Rules:** `get_active_tags_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — bulk setup (101 rows) outside the Conventions vocabulary

**Given**
1. 101 tags N1 … N101, inserted in that order; Nk (k = 1 … 101) has `name` = `f"Crate {k:03d}"`, `tag_code` = `f"crate_{k:03d}"`.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `sorted(ids(result)) ==` the 101 ids, ascending.

### ITG-ACT-09 — every system tag comes before every user tag
- **Rules:** `get_active_tags_in_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Anchor"`, `tag_code "anchor"`.
2. T2 = tag, `name "Bracket"`, `tag_code "bracket"`.
3. S1 = system tag, `name "Zinc Plate"`, `tag_code "zinc_plate"`.
4. S2 = system tag, `name "Yarn Spool"`, `tag_code "yarn_spool"`. (User tags are inserted first and their names sort first; the system tags must still lead.)

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `[t.is_system_tag for t in result] == [True, True, False, False]`.
2. returns: `sorted(t.id for t in result[:2]) == [S1.id, S2.id]`.

### ITG-ACT-10 — within each group, lower-case names come back in alphabetical order
- **Rules:** `get_active_tags_in_workspace` R3, R4 (the part that holds today: names with one case only)
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "delta"`, `tag_code "delta"`.
2. T2 = tag, `name "alpha"`, `tag_code "alpha"`.
3. S1 = system tag, `name "yarn"`, `tag_code "yarn"`.
4. S2 = system tag, `name "bolt"`, `tag_code "bolt"`. (Single-word, all-lower-case ASCII names: every collation orders them alike.)

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `names(result) == ["bolt", "yarn", "alpha", "delta"]`.

### ITG-ACT-11 — names that differ only in case come back in id order, then the other names case-insensitively
- **Rules:** `get_active_tags_in_workspace` R4 [BUG-930]
- **Kind:** bug
- **Expect:** xfail BUG-930 (non-strict)
- **Fails today on:** Then 2 (names are ordered by the database collation; on the test database "alpha" sorts before "Alpha", giving [T3.id, T2.id, T1.id, T4.id]. Non-strict because the outcome depends on the server's collation, not on this code alone)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-930")`); the assertion is never weakened

**Given**
1. T1 = tag, `name "bravo"`, `tag_code "bravo"`.
2. T2 = tag, `name "Alpha"`, `tag_code "alpha_upper"`.
3. T3 = tag, `name "alpha"`, `tag_code "alpha_lower"`. (The "Alpha" / "alpha" pair is on purpose: equal ignoring case, so only `id` decides between them. Retire this card if a unique index on tag names is ever added — item tag service FU-1 (c).)
4. T4 = tag, `name "Charlie"`, `tag_code "charlie"`.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [T1.id, T2.id, T3.id, T4.id]`.
2. returns: `ids(result) == [T2.id, T3.id, T1.id, T4.id]`.

### ITG-ACT-12 — two tags with the same name come back lower id first
- **Rules:** `get_active_tags_in_workspace` R4 [BUG-930]
- **Kind:** bug
- **Expect:** xfail BUG-930 (non-strict)
- **Fails today on:** Then 2 (no tie-break is requested; the updated row T1 usually comes back after T2, giving [T2.id, T1.id] — but the physical row order can match the intended order by accident)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-930")`); the assertion is never weakened

**Given**
1. T1 = tag, `name "Bolt"`, `tag_code "bolt_a"`.
2. T2 = tag, `name "Bolt"`, `tag_code "bolt_b"`. (Same name as T1 on purpose: nothing checks tag names.)
3. T1 is changed after T2 was created: `T1.description = "moved"`, then `db.flush()`. (This usually moves T1 physically behind T2 in the table.)

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [T1.id, T2.id]`.
2. returns: `ids(result) == [T1.id, T2.id]`.

### ITG-ACT-13 — the active-tag query asks for system first, then name case-insensitive, then id
- **Rules:** `get_active_tags_in_workspace` R3, R4 [BUG-930]
- **Kind:** bug
- **Expect:** xfail BUG-930
- **Fails today on:** Then 4 (the order is `is_system_tag DESC, name` — `name` is not wrapped in `lower(...)`)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order or collation)

**Given**
1. S1 = system tag, `name "Raw Material"`, `tag_code "raw_material"`.
2. T1 = tag, `name "Custom Bin"`, `tag_code "custom_bin"`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id, T1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"item_tags.is_system_tag DESC" in order_part`.
4. statement: `"lower(item_tags.name)" in order_part`.
5. statement: `"item_tags.id" in order_part`.


## `ItemTagDAO.increment_usage_count`

### ITG-INC-01 — the counter goes up by one, flushed, and the session's tag object is returned
- **Rules:** `increment_usage_count` R1, R6, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count 2`.

**When**
- `result = dao.increment_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: `result.usage_count == 3`.
3. returns: `stored_count(T1) == 3`.
4. nothing written: nothing written.

### ITG-INC-02 — a counter of 0 becomes 1
- **Rules:** `increment_usage_count` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`. (`usage_count 0`.)

**When**
- `result = dao.increment_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. re-read T1: `usage_count == 1`.

### ITG-INC-03 — an unknown tag id returns None, writes nothing and raises nothing
- **Rules:** `increment_usage_count` R2 (Q2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count 2`.

**When**
- `result = dao.increment_usage_count(db, tag_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.
3. unchanged: unchanged(T1).

### ITG-INC-04 — a tag of another workspace returns None and its counter stays
- **Rules:** `increment_usage_count` R2 (Q2)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T9 = tag, `name "Far Crate"`, `tag_code "far_crate"`, but `workspace_id W2.id`, `usage_count 5`.

**When**
- `result = dao.increment_usage_count(db, tag_id=T9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. returns: `stored_count(T9) == 5`.
3. unchanged: unchanged(T9).

### ITG-INC-05 — the tag's own workspace counts it
- **Rules:** `increment_usage_count` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T9 = tag, `name "Far Crate"`, `tag_code "far_crate"`, but `workspace_id W2.id`, `usage_count 5`.

**When**
- `result = dao.increment_usage_count(db, tag_id=T9.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is T9`.
2. re-read T9: `usage_count == 6`.

### ITG-INC-06 — a deleted tag is counted like any other
- **Rules:** `increment_usage_count` R3 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. TD = tag, `name "Obsolete"`, `tag_code "obsolete"`, but `is_active False`, `usage_count 2`.

**When**
- `result = dao.increment_usage_count(db, tag_id=TD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is TD`.
2. re-read TD: `usage_count == 3`.
3. re-read TD: `is_active is False`.

### ITG-INC-07 — a system tag is counted like any other
- **Rules:** `increment_usage_count` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = system tag, `name "Raw Material"`, `tag_code "raw_material"`, but `usage_count 4`.

**When**
- `result = dao.increment_usage_count(db, tag_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is S1`.
2. re-read S1: `usage_count == 5`.

### ITG-INC-08 — a negative stored counter goes up by one
- **Rules:** `increment_usage_count` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count -2`.

**When**
- `result = dao.increment_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. re-read T1: `usage_count == -1`.

### ITG-INC-09 — only the counter of that tag changes
- **Rules:** `increment_usage_count` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count 4`, `color "#AA3300"`, `icon "bolt"`, `description "M8 bolts"`.
2. T2 = tag, `name "Lock Nut"`, `tag_code "lock_nut"`, but `usage_count 4`.

**When**
- `result = dao.increment_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. re-read T1: `usage_count == 5`.
3. re-read T1: `name == "Hex Bolt"`, `tag_code == "hex_bolt"`, `workspace_id == W1.id`.
4. re-read T1: `color == "#AA3300"`, `icon == "bolt"`, `description == "M8 bolts"`.
5. re-read T1: `is_active is True`, `is_system_tag is False`, `created_by is None`.
6. unchanged: unchanged(T2).
7. nothing written: nothing written.

### ITG-INC-10 — the flush also saves another pending change of the same tag
- **Rules:** `increment_usage_count` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count 2`.
2. `T1.name = "Lock Nut"` (pending: not flushed).

**When**
- `result = dao.increment_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. re-read T1: `name == "Lock Nut"`.
3. re-read T1: `usage_count == 3`.

### ITG-INC-11 — the increase is applied to the stored value, not to the loaded one *(revised 2026-11-27, bug-fix pre-check)*
- **Rules:** `increment_usage_count` R5 [BUG-931]
- **Kind:** bug
- **Expect:** xfail BUG-931
- **Fails today on:** Then 2 (the loaded value is used: `result.usage_count` is 4, not 11)
- **Author:** claude — a direct `UPDATE` statement in the Given (stored value changed behind the loaded object)

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count 3`. (Flushed; the object holds 3.)
2. `db.execute(text("update item_tags set usage_count = 10 where id = :i"), {"i": T1.id})` — T1 is not expired.

**When**
- `result = dao.increment_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`, inside the statement recorder.

**Then**
1. returns: `result is T1`.
2. returns: `result.usage_count == 11` (read on the object, before any re-read).
3. returns: `stored_count(T1) == 11`.
4. sql: an `UPDATE` of `item_tags` was sent whose `SET usage_count = usage_count + …` computes from the stored column. (A re-read followed by writing a fixed value would pass Then 1–3 but still lose concurrent changes; R5 requires a single relative update.)

### ITG-INC-12 — with the object expired first, the increase starts from the stored value
- **Rules:** `increment_usage_count` R5 (the control that holds today), R1
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — a direct `UPDATE` statement in the Given

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count 3`.
2. `db.execute(text("update item_tags set usage_count = 10 where id = :i"), {"i": T1.id})`
3. `db.expire(T1)`

**When**
- `result = dao.increment_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: `stored_count(T1) == 11`.

### ITG-INC-13 — the increase is flushed but not committed: a rollback restores the old value
- **Rules:** `increment_usage_count` R6
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count 2`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.increment_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: inside the savepoint, `stored_count(T1) == 3`.
3. re-read T1 after the savepoint rollback: `usage_count == 2`.
4. mock called: the `db.commit` spy was never called.


## `ItemTagDAO.decrement_usage_count`

### ITG-DEC-01 — the counter goes down by one, flushed, and the session's tag object is returned
- **Rules:** `decrement_usage_count` R1, R7, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count 3`.

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: `result.usage_count == 2`.
3. returns: `stored_count(T1) == 2`.
4. nothing written: nothing written.

### ITG-DEC-02 — a counter of 1 becomes 0
- **Rules:** `decrement_usage_count` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count 1`.

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. re-read T1: `usage_count == 0`.

### ITG-DEC-03 — a counter of 0 stays 0 and the tag is returned
- **Rules:** `decrement_usage_count` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`. (`usage_count 0`.)

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: `result.usage_count == 0`.
3. re-read T1: `usage_count == 0`.
4. unchanged: unchanged(T1).

### ITG-DEC-04 — at 0 nothing is flushed: another pending change stays unsaved
- **Rules:** `decrement_usage_count` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`. (`usage_count 0`.)
2. `T1.name = "Lock Nut"` (pending: not flushed).

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. re-read T1: `name == "Hex Bolt"`.
3. re-read T1: `usage_count == 0`.

### ITG-DEC-05 — a negative stored counter is left as it is and the tag is returned
- **Rules:** `decrement_usage_count` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count -2`.

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: `result.usage_count == -2`.
3. re-read T1: `usage_count == -2`.

### ITG-DEC-06 — an unknown tag id returns None, writes nothing and raises nothing
- **Rules:** `decrement_usage_count` R4 (Q2)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count 3`.

**When**
- `result = dao.decrement_usage_count(db, tag_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.
3. unchanged: unchanged(T1).

### ITG-DEC-07 — a tag of another workspace returns None and its counter stays
- **Rules:** `decrement_usage_count` R4 (Q2)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T9 = tag, `name "Far Crate"`, `tag_code "far_crate"`, but `workspace_id W2.id`, `usage_count 5`.

**When**
- `result = dao.decrement_usage_count(db, tag_id=T9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. returns: `stored_count(T9) == 5`.
3. unchanged: unchanged(T9).

### ITG-DEC-08 — the tag's own workspace decrements it
- **Rules:** `decrement_usage_count` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T9 = tag, `name "Far Crate"`, `tag_code "far_crate"`, but `workspace_id W2.id`, `usage_count 5`.

**When**
- `result = dao.decrement_usage_count(db, tag_id=T9.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is T9`.
2. re-read T9: `usage_count == 4`.

### ITG-DEC-09 — a deleted tag is decremented like any other
- **Rules:** `decrement_usage_count` R5 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. TD = tag, `name "Obsolete"`, `tag_code "obsolete"`, but `is_active False`, `usage_count 3`.

**When**
- `result = dao.decrement_usage_count(db, tag_id=TD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is TD`.
2. re-read TD: `usage_count == 2`.
3. re-read TD: `is_active is False`.

### ITG-DEC-10 — a system tag is decremented like any other
- **Rules:** `decrement_usage_count` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = system tag, `name "Raw Material"`, `tag_code "raw_material"`, but `usage_count 4`.

**When**
- `result = dao.decrement_usage_count(db, tag_id=S1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is S1`.
2. re-read S1: `usage_count == 3`.

### ITG-DEC-11 — only the counter of that tag changes
- **Rules:** `decrement_usage_count` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count 4`, `color "#AA3300"`, `icon "bolt"`, `description "M8 bolts"`.
2. T2 = tag, `name "Lock Nut"`, `tag_code "lock_nut"`, but `usage_count 4`.

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. re-read T1: `usage_count == 3`.
3. re-read T1: `name == "Hex Bolt"`, `tag_code == "hex_bolt"`, `workspace_id == W1.id`.
4. re-read T1: `color == "#AA3300"`, `icon == "bolt"`, `description == "M8 bolts"`.
5. re-read T1: `is_active is True`, `is_system_tag is False`, `created_by is None`.
6. unchanged: unchanged(T2).
7. nothing written: nothing written.

### ITG-DEC-12 — when a value is written, the flush also saves another pending change of the same tag
- **Rules:** `decrement_usage_count` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count 3`.
2. `T1.name = "Lock Nut"` (pending: not flushed).

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. re-read T1: `name == "Lock Nut"`.
3. re-read T1: `usage_count == 2`.

### ITG-DEC-13 — the decrease is applied to the stored value, not to the loaded one *(revised 2026-11-27, bug-fix pre-check)*
- **Rules:** `decrement_usage_count` R6 [BUG-931]
- **Kind:** bug
- **Expect:** xfail BUG-931
- **Fails today on:** Then 2 (the loaded value is used: `result.usage_count` is 2, not 9)
- **Author:** claude — a direct `UPDATE` statement in the Given (stored value changed behind the loaded object)

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count 3`. (Flushed; the object holds 3.)
2. `db.execute(text("update item_tags set usage_count = 10 where id = :i"), {"i": T1.id})` — T1 is not expired.

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`, inside the statement recorder.

**Then**
1. returns: `result is T1`.
2. returns: `result.usage_count == 9` (read on the object, before any re-read).
3. returns: `stored_count(T1) == 9`.
4. sql: an `UPDATE` of `item_tags` was sent whose `SET usage_count = usage_count - …` computes from the stored column, and whose `WHERE` also tests the stored `usage_count >` (no read-then-write; R6).

### ITG-DEC-14 — the "not below 0" check uses the stored value: stored 0 stays 0
- **Rules:** `decrement_usage_count` R6 [BUG-931]
- **Kind:** bug
- **Expect:** xfail BUG-931
- **Fails today on:** Then 2 (the loaded value 3 passes the check: `result.usage_count` is 2, not 0)
- **Author:** claude — a direct `UPDATE` statement in the Given (stored value changed behind the loaded object)

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count 3`. (Flushed; the object holds 3.)
2. `db.execute(text("update item_tags set usage_count = 0 where id = :i"), {"i": T1.id})` — T1 is not expired.

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: `result.usage_count == 0` (read on the object, before any re-read).
3. returns: `stored_count(T1) == 0`.

### ITG-DEC-15 — the decrease is flushed but not committed: a rollback restores the old value
- **Rules:** `decrement_usage_count` R7
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count 3`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: inside the savepoint, `stored_count(T1) == 2`.
3. re-read T1 after the savepoint rollback: `usage_count == 3`.
4. mock called: the `db.commit` spy was never called.

### ITG-DEC-16 — after a savepoint rollback, the tag object shows the stored count again *(added 2026-11-27, bug-fix pre-check, unit dao-item_tag-2)*
- **Rules:** `decrement_usage_count` R7 [BUG-3302] (bug row Intended: after a savepoint rollback the in-memory `usage_count` equals the stored value, as for the increment)
- **Kind:** bug
- **Expect:** pass (BUG-3302 fixed in bugfix/dao-item_tag-2; was strict xfail)
- **Failed before the fix on:** Then 4 (the object still held the rolled-back 4 while the database had 5)
- **Author:** claude — savepoint rollback

**Given**
1. T1 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`, but `usage_count 5`.
2. `sp = db.begin_nested()` directly before the call (no commit spy).

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: inside the savepoint, `T1.usage_count == 4` (read on the object; this load is what the rollback must undo).
3. after `sp.rollback()`: `stored_count(T1) == 5`.
4. after `sp.rollback()`, read on the object without any expire or re-read: `T1.usage_count == 5`.


## Inherited `BaseDAO` methods on `ItemTag`

### ITG-INH-01 — create with a dict stores a tag with the model defaults
- **Rules:** inherited R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No tag exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "Spare Part", "tag_code": "spare_part"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `name == "Spare Part"`, `tag_code == "spare_part"`.
3. re-read the returned row: `is_system_tag is False`, `is_active is True`, `usage_count == 0`.
4. re-read the returned row: `created_by is None`, `color is None`, `icon is None`, `description is None`.
5. re-read the returned row: `created_at.tzinfo is None`.
6. re-read the returned row: `created_at` is close to now.
7. count: `item_tags` has exactly 1 row.

### ITG-INH-02 — create with an ItemTagCreate schema fails on flush and saves nothing
- **Rules:** inherited R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No tag exists.

**When**
- `dao.create(db, obj_in=ItemTagCreate(name="Spare Part", tag_code="spare_part"))`. (The schema has no `workspace_id`.)

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "workspace_id"' in str(exc.value.orig)`.
4. count: `item_tags` has exactly 0 rows.

### ITG-INH-03 — create with a dict without tag_code fails on flush and saves nothing
- **Rules:** inherited R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No tag exists.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": "Spare Part"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "tag_code"' in str(exc.value.orig)`.
4. count: `item_tags` has exactly 0 rows.

### ITG-INH-04 — create with a dict without name fails on flush and saves nothing
- **Rules:** inherited Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No tag exists.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "tag_code": "spare_part"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `'column "name"' in str(exc.value.orig)`.
4. count: `item_tags` has exactly 0 rows.

### ITG-INH-05 — create with an unknown workspace_id fails on flush and saves nothing
- **Rules:** inherited R2, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. No tag exists.

**When**
- `dao.create(db, obj_in={"workspace_id": MISSING, "name": "Spare Part", "tag_code": "spare_part"})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"item_tags_workspace_id_fkey" in str(exc.value.orig)`.
4. count: `item_tags` has exactly 0 rows.

### ITG-INH-06 — create with an unknown created_by fails on flush and saves nothing
- **Rules:** inherited R2, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. No tag exists.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": "Spare Part", "tag_code": "spare_part", "created_by": MISSING})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"item_tags_created_by_fkey" in str(exc.value.orig)`.
4. count: `item_tags` has exactly 0 rows.

### ITG-INH-07 — a color of 8 characters is too long and nothing is saved
- **Rules:** inherited R2, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. No tag exists.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": "Spare Part", "tag_code": "spare_part", "color": "#AA33001"})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, StringDataRightTruncation)`.
3. raises: `exc.value.orig.pgcode == "22001"`.
4. count: `item_tags` has exactly 0 rows.

### ITG-INH-08 — a color of exactly 7 characters is saved
- **Rules:** inherited R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No tag exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "Spare Part", "tag_code": "spare_part", "color": "#AA3300"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `color == "#AA3300"`.

### ITG-INH-09 — an icon of 51 characters is too long and nothing is saved
- **Rules:** inherited R2, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. No tag exists.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "name": "Spare Part", "tag_code": "spare_part", "icon": "i" * 51})`.

**Then**
1. raises: `DataError` on flush.
2. raises: `isinstance(exc.value.orig, StringDataRightTruncation)`.
3. raises: `exc.value.orig.pgcode == "22001"`.
4. count: `item_tags` has exactly 0 rows.

### ITG-INH-10 — an icon of exactly 50 characters is saved
- **Rules:** inherited R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No tag exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "Spare Part", "tag_code": "spare_part", "icon": "i" * 50})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `icon == "i" * 50`.

### ITG-INH-11 — a 500-character name and a 60-character code are saved (no database length limit)
- **Rules:** inherited R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No tag exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "N" * 500, "tag_code": "c" * 60})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name == "N" * 500`.
3. re-read the returned row: `tag_code == "c" * 60`.

### ITG-INH-12 — create checks no uniqueness: a second tag with the same name and code is saved
- **Rules:** inherited R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Spare Part"`, `tag_code "spare_part"`.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "Spare Part", "tag_code": "spare_part"})`. (Same name and code as T1 on purpose.)

**Then**
1. returns: `result.id != T1.id`.
2. count: `item_tags` rows with `tag_code == "spare_part"`: exactly 2.
3. unchanged: unchanged(T1).

### ITG-INH-13 — update with an ItemTagUpdate changes the name and keeps a colour sent as None
- **Rules:** inherited R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Spare Part"`, `tag_code "spare_part"`, but `color "#AA3300"`.

**When**
- `result = dao.update(db, db_obj=T1, obj_in=ItemTagUpdate(name="Spare Kit", color=None))`.

**Then**
1. returns: `result.id == T1.id`.
2. re-read T1: `name == "Spare Kit"`.
3. re-read T1: `color == "#AA3300"`.

### ITG-INH-14 — update with the dict {"is_active": False} deletes the tag
- **Rules:** inherited R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T1 = tag, `name "Spare Part"`, `tag_code "spare_part"`.

**When**
- `result = dao.update(db, db_obj=T1, obj_in={"is_active": False})`.

**Then**
1. returns: `result.id == T1.id`.
2. re-read T1: `is_active is False`.
3. re-read T1: `name == "Spare Part"`, `tag_code == "spare_part"`.
4. count: `item_tags` has exactly 1 row.

### ITG-INH-15 — update with the dict {"is_active": True} brings a deleted tag back
- **Rules:** inherited R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. TD = tag, `name "Obsolete"`, `tag_code "obsolete"`, but `is_active False`.

**When**
- `result = dao.update(db, db_obj=TD, obj_in={"is_active": True})`.

**Then**
1. returns: `result.id == TD.id`.
2. re-read TD: `is_active is True`.

### ITG-INH-16 — update with the dict {"color": None} clears the colour
- **Rules:** inherited R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Spare Part"`, `tag_code "spare_part"`, but `color "#AA3300"`.

**When**
- `result = dao.update(db, db_obj=T1, obj_in={"color": None})`.

**Then**
1. returns: `result.id == T1.id`.
2. re-read T1: `color is None`.
3. re-read T1: `name == "Spare Part"`.

### ITG-INH-17 — get_by_workspace returns the workspace's tags, deleted ones included, and no tag of another workspace
- **Rules:** inherited R5 (the part that holds today), R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Spare Part"`, `tag_code "spare_part"`.
2. TD = tag, `name "Obsolete"`, `tag_code "obsolete"`, but `is_active False`.
3. T9 = tag, `name "Far Crate"`, `tag_code "far_crate"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [T1.id, TD.id]`.
2. returns: `len(result) == 2`.

### ITG-INH-18 — get_by_workspace returns the tags in id order
- **Rules:** inherited R5 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the updated row T1 usually comes back after T2, giving [T2.id, T1.id] — but the physical row order can match the intended order by accident)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-100")`); the assertion is never weakened

**Given**
1. T1 = tag, `name "Spare Part"`, `tag_code "spare_part"`.
2. T2 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`.
3. T1 is changed after T2 was created: `T1.description = "moved"`, then `db.flush()`. (This usually moves T1 physically behind T2 in the table.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [T1.id, T2.id]`.
2. returns: `ids(result) == [T1.id, T2.id]`.

### ITG-INH-19 — the workspace list query on tags asks the database for id order
- **Rules:** inherited R5 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 2 (the query has no `ORDER BY`)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order)

**Given**
1. T1 = tag, `name "Spare Part"`, `tag_code "spare_part"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"item_tags.id" in order_part`.

### ITG-INH-20 — get returns a deleted tag
- **Rules:** inherited R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. TD = tag, `name "Obsolete"`, `tag_code "obsolete"`, but `is_active False`.

**When**
- `result = dao.get(db, TD.id)`.

**Then**
1. returns: `result.id == TD.id`.
2. returns: `result.is_active is False`.

### ITG-INH-21 — get returns a tag of any workspace
- **Rules:** inherited R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T9 = tag, `name "Far Crate"`, `tag_code "far_crate"`, but `workspace_id W2.id`.

**When**
- `result = dao.get(db, T9.id)`.

**Then**
1. returns: `result.id == T9.id`.
2. returns: `result.workspace_id == W2.id`.

### ITG-INH-22 — get_by_id_and_workspace returns a deleted tag
- **Rules:** inherited R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. TD = tag, `name "Obsolete"`, `tag_code "obsolete"`, but `is_active False`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=TD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == TD.id`.
2. returns: `result.is_active is False`.

### ITG-INH-23 — get_by_id_and_workspace returns None for a tag of another workspace
- **Rules:** inherited R6
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T9 = tag, `name "Far Crate"`, `tag_code "far_crate"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=T9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ITG-INH-24 — remove deletes the tag row for good
- **Rules:** inherited R7 (the tag row; the cascade is Spec gap 4)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Spare Part"`, `tag_code "spare_part"`.
2. T2 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`.
3. `t1_id = T1.id`

**When**
- `result = dao.remove(db, id=t1_id)`.

**Then**
1. returns: `result.id == t1_id`.
2. count: `item_tags` rows with `id == t1_id`: exactly 0.
3. unchanged: unchanged(T2).


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 (a) — "create tag" refuses a deleted tag's code for ever; needs a live-only lookup | item tag service spec (`create_tag`) | Here `get_by_code_in_workspace` returns the deleted tag (ITG-CODE-15). |
| FU-1 (b), (c), (d) — no unique index on code / name, names never checked or trimmed, code derived from the name can break the schema pattern | item tag service spec; HR-1 / HR-2 | Here create accepts a duplicate (ITG-INH-12) and long names (ITG-INH-11). |
| FU-1 (e) — `get_tags` replaces `usage_count` with a live count; two numbers for one field | item tag service spec (`get_tags`, `get_system_tags`) | No card here. |
| FU-1 (f) — `update_tag` / `delete_tag` act on a deleted tag | item tag service spec | Here `update` with a dict works on any tag (ITG-INH-14, INH-15). |
| FU-2 — the manager attaches and counts deleted tags, skips unknown ids, re-creates unchanged assignments, `delete_item` decrements only active tags; all counter calls inherit BUG-931 | item manager spec | Here the counters work on deleted tags (ITG-INC-06, DEC-09) and return `None` for an unknown / foreign tag (ITG-INC-03, INC-04, DEC-06, DEC-07). |
| FU-3 — `get_tags_for_item` without order, `get_tags_for_items` with the BUG-930 issue, `count_active_items_per_tag` counts deleted tags | item tag assignment DAO spec | No card here. |
| inherited R7 — `remove` also deletes the tag's `item_tag_assignments` rows (`ON DELETE CASCADE`) | `tests/unit/dao/base.cases.md` (remove R4) / item tag assignment DAO cases | Spec gap 4: ITG-INH-24 checks only the tag row. |
| Inherited `get`, `get_multi`, `create`, `update`, `remove`, `get_by_workspace`, `get_by_id_and_workspace` — generic behaviour (paging, missing ids, `get_multi` without workspace filter, flushed-not-committed) | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not repeated here; only what the `ItemTag` model and its schemas change has cards (ITG-INH-01 … INH-24). |
| Notes "keyword-only parameters" (a positional call raises `TypeError`) | none (no rule) | Spec gap 3. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Overview, model facts ("Schemas: `ItemTagCreate` … `ItemTagUpdate` …") | The module the two schemas live in is not named. | Conventions assume `app.schemas.item_tag` (ITG-INH-02, INH-13). Correct the Conventions line if the module differs. |
| 2 | inherited Errors ("Detail message: — (not asserted)") | The Raises column names the constraint / column of each violation, but the text is "not asserted". | Designed as loose checks: the constraint name or `column "<name>"` is contained in `str(exc.value.orig)` (ITG-INH-02 … INH-06). Drop those lines if the text is not meant to be asserted. |
| 3 | Notes for the test designer ("every parameter after `db` is keyword-only — a positional call raises `TypeError`") | Stated as a note, not as a rule of any callable. | No card. |
| 4 | inherited R7 (`remove` cascades to `item_tag_assignments`) | The spec gives no columns of `item_tag_assignments` or of the `items` row an assignment needs, so no assignment row can be built from the spec. | ITG-INH-24 checks only that the tag row is gone; the cascade is deferred. |
| 5 | `get_system_tags_in_workspace` R3, `get_active_tags_in_workspace` R4 ("name case-insensitive") | How the case-insensitive key is expressed in SQL is not stated (`lower(name)`, a case-insensitive collation, …). | The strict recorder cards ITG-SYS-10, ACT-13 assert `lower(item_tags.name)` in the `ORDER BY`. If the fix uses another form, those two lines must change with it. |
| 6 | inherited R1 (`created_at` "close to now") | No tolerance is given. | "close to now" = within 5 minutes of the test's clock (Conventions; ITG-INH-01). |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_code_in_workspace` | Returns | ITG-CODE-01, CODE-02 |
| `get_by_code_in_workspace` | R1 | ITG-CODE-01, CODE-02, CODE-03, CODE-04 |
| `get_by_code_in_workspace` | R2 | ITG-CODE-05, CODE-06, CODE-07, CODE-08, CODE-09, CODE-10, CODE-11, CODE-12, CODE-13, CODE-14 |
| `get_by_code_in_workspace` | R3 (P1) | ITG-CODE-15, CODE-16 |
| `get_by_code_in_workspace` | R4 | ITG-CODE-17 |
| `get_by_code_in_workspace` | R5 | ITG-CODE-01, CODE-15, CODE-17 |
| `get_system_tags_in_workspace` | Returns (a list) | ITG-SYS-01 |
| `get_system_tags_in_workspace` | R1 | ITG-SYS-01, SYS-02, SYS-03, SYS-04, SYS-05, SYS-06 |
| `get_system_tags_in_workspace` | R2 | ITG-SYS-07 |
| `get_system_tags_in_workspace` | R3 [BUG-929] | ITG-SYS-08, SYS-09 (non-strict xfail); SYS-10 (strict xfail, statement recorder) |
| `get_system_tags_in_workspace` | R4 | ITG-SYS-01 |
| `get_active_tags_in_workspace` | Returns (a list) | ITG-ACT-01 |
| `get_active_tags_in_workspace` | R1 | ITG-ACT-01, ACT-02, ACT-03, ACT-04, ACT-05, ACT-06, ACT-07 |
| `get_active_tags_in_workspace` | R2 | ITG-ACT-08 |
| `get_active_tags_in_workspace` | R3 | ITG-ACT-09, ACT-10; ACT-13 Then 3 |
| `get_active_tags_in_workspace` | R4 [BUG-930] | ITG-ACT-10 (pass: one-case names); ACT-11, ACT-12 (non-strict xfail); ACT-13 (strict xfail, statement recorder) |
| `get_active_tags_in_workspace` | R5 | ITG-ACT-01 |
| `increment_usage_count` | Returns | ITG-INC-01, INC-03 |
| `increment_usage_count` | R1 | ITG-INC-01, INC-02, INC-05 |
| `increment_usage_count` | R2 (Q2) | ITG-INC-03, INC-04 |
| `increment_usage_count` | R3 (P2) | ITG-INC-06, INC-07 |
| `increment_usage_count` | R4 | ITG-INC-08 |
| `increment_usage_count` | R5 [BUG-931] | ITG-INC-11 (strict xfail); INC-12 (pass control) |
| `increment_usage_count` | R6 | ITG-INC-01, INC-10, INC-13 |
| `increment_usage_count` | Side effects (one row, one column, no commit) | ITG-INC-09, INC-13 |
| `decrement_usage_count` | Returns | ITG-DEC-01, DEC-03, DEC-06 |
| `decrement_usage_count` | R1 | ITG-DEC-01, DEC-02, DEC-08 |
| `decrement_usage_count` | R2 | ITG-DEC-03, DEC-04 |
| `decrement_usage_count` | R3 | ITG-DEC-05 |
| `decrement_usage_count` | R4 (Q2) | ITG-DEC-06, DEC-07 |
| `decrement_usage_count` | R5 (P2) | ITG-DEC-09, DEC-10 |
| `decrement_usage_count` | R6 [BUG-931] | ITG-DEC-13, DEC-14 (strict xfail) |
| `decrement_usage_count` | R7 | ITG-DEC-01, DEC-12, DEC-15; DEC-16 (strict xfail, BUG-3302) |
| `decrement_usage_count` | Side effects (one row, one column, no commit) | ITG-DEC-11, DEC-15 |
| inherited | R1 | ITG-INH-01 |
| inherited | R2 | ITG-INH-02, INH-03, INH-05, INH-06, INH-07, INH-08, INH-09, INH-10, INH-11 |
| inherited | R3 | ITG-INH-12 |
| inherited | R4 | ITG-INH-13, INH-14, INH-15, INH-16 |
| inherited | R5 [BUG-100] | ITG-INH-18 (non-strict xfail); INH-19 (strict xfail, statement recorder); INH-17 (pass companion) |
| inherited | R6 | ITG-INH-17, INH-20, INH-21, INH-22, INH-23 |
| inherited | R7 | ITG-INH-24 (tag row only; cascade deferred, Spec gap 4) |
| inherited | Errors row 1 (`NotNullViolation`) | ITG-INH-02, INH-03, INH-04 |
| inherited | Errors row 2 (`ForeignKeyViolation`) | ITG-INH-05, INH-06 |
| inherited | Errors row 3 (`StringDataRightTruncation`) | ITG-INH-07, INH-09 |
| BUG-929 | `get_system_tags_in_workspace` R3 | ITG-SYS-08, SYS-09, SYS-10 |
| BUG-930 | `get_active_tags_in_workspace` R4 | ITG-ACT-11, ACT-12, ACT-13 |
| BUG-931 | `increment_usage_count` R5, `decrement_usage_count` R6 | ITG-INC-11, DEC-13, DEC-14 |
| BUG-100 | inherited R5 | ITG-INH-18, INH-19 |
| BUG-3302 | `decrement_usage_count` R7 (in-memory value after a savepoint rollback) | ITG-DEC-16 |
