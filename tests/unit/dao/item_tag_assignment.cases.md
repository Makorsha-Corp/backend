# Test cases — `app/dao/item_tag_assignment.py`

> **Spec:** `tests/unit/dao/item_tag_assignment.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-10-17); every answer (P1, P2, P3 and the house-rule lines BUG-932, BUG-933, BUG-100, including "item chips are not grouped system tags first") was decided by Claude under the reviewer's delegation, so nothing is provisional.
> **Counts:** 88 cases · 80 expected-to-pass · 8 expected-to-fail (bugs) · 10 deferred

## Reviewer summary
- **Per callable:** `get_tags_for_items` 20 (3 bug) · `get_tags_for_item` 15 (3 bug) · `assignment_exists` 10 · `count_active_items_per_tag` 11 · `remove_all_tags_from_item` 14 · inherited `BaseDAO` methods on `ItemTagAssignment` 18 (2 bug).
- **Expected-to-fail by bug:** BUG-933 3 (ITA-TFS-17, TFS-18 non-strict; TFS-19 strict, statement recorder) · BUG-932 3 (ITA-TFI-12, TFI-13 non-strict; TFI-14 strict, statement recorder) · BUG-100 2 (ITA-INH-14 non-strict; INH-15 strict, statement recorder). BUG-934 and BUG-935 have no card here (fixed in the item manager; see Deferred).
- **Delegated answers and the cards that rest on them:** P1 (raw lookups: a deleted item's tags are listed, `assignment_exists` ignores tag / item state, deleted tags are counted) — ITA-TFS-12, TFI-09, EX-07, EX-08, CNT-09. P2 / P3 — `remove_all_tags_from_item` is tested as it behaves today (ITA-RM-01 … RM-14, including RM-02: links to a deleted tag are removed). HR-6 "system tags not first" — ITA-TFS-16 (pass), TFS-17, TFI-12 (non-strict).
- **Dead code after BUG-934:** `remove_all_tags_from_item` is on the dead-code list "remove together with the fix of BUG-934". The 14 cards ITA-RM-01 … RM-14 are deleted in that change.
- **Notable design choices:**
  - Row order (BUG-932, BUG-933, BUG-100): no pass card and no strict card depends on physical row order or on the database collation. List cards compare `sorted(ids(...))`, sizes, membership, `[]` or dict equality. One pass card checks an order `ORDER BY name` already gives today: ITA-TFS-16 (single-word, all-lower-case ASCII names, which every collation orders alike; the system tag "zulu" comes last, so "system tags first" would break it).
  - Collation, same decision as the item tag cases (ITG-ACT-11): "alpha" / "Alpha" in `get_tags_for_items` (ITA-TFS-17) fails deterministically on the test database (`English_United States.1252` sorts "alpha" first) but is **non-strict**: a server whose collation puts capitals first would make a strict card XPASS while the bug is still there. Each query's strict alarm is its statement-recorder card (TFS-19, TFI-14, INH-15), which depends on neither the server nor the row order.
  - Same-name ties: the two links are inserted in reverse order (higher tag id first), so today's physical order usually differs from the intended one — still non-strict (TFS-18, TFI-13).
  - No 101-row "no limit" cards: the spec names no limit to probe; "no limit" is covered by the multi-tag cards (Coverage matrix).
  - The database `ON DELETE CASCADE` from a tag to its links (deferred here by the item tag cases, their Spec gap 4) is shown with a direct `DELETE` statement (ITA-INH-18), not the ORM — see Spec gap 5.
  - Cards marked `Author: claude` (13): statement recorder — TFS-04 (no query for `[]`), TFS-19, TFI-14, INH-15; non-strict xfail — TFS-17, TFS-18, TFI-12, TFI-13, INH-14; savepoint rollback and commit spy — RM-09; a step after the When (edit of the standing row I1 and flush; a follow-up `create`) — RM-13, RM-14; a direct statement as the When — INH-18.
- **Needs a decision:** None blocking. See Spec gaps 1 (constraint names as "contained in"), 3 (`lower(...)` as the case-insensitive key), 4 (schema module assumed), 5 (ORM delete of a tag with links not specified).


## Conventions for this module

**IDs.** `ITA` = `app/dao/item_tag_assignment.py`. `TFS` get_tags_for_items (several items) · `TFI` get_tags_for_item (one item) · `EX` assignment_exists · `CNT` count_active_items_per_tag · `RM` remove_all_tags_from_item · `INH` inherited `BaseDAO` methods on `ItemTagAssignment`.

**Actors and fixed values.**
- `dao` = the singleton `item_tag_assignment_dao` (`from app.dao.item_tag_assignment import item_tag_assignment_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns. The session does not autoflush.
- W1, W2 = two `workspaces` rows. U1, U2 = two `profiles` rows: U1 is `assigned_by` of every Given link, U2 is used where a card needs a second user.
- `ItemTagAssignment` = `app.models.item_tag_assignment.ItemTagAssignment`; `ItemTag` = `app.models.item_tag.ItemTag`; `Item` = `app.models.item.Item`; `ItemTagAssignmentCreate` = the schema of `app.schemas.item_tag_assignment` (Spec gap 4). `select`, `text` = `sqlalchemy.select`, `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order.
- **item** = `items` row built with `Item`: `workspace_id W1.id`, `unit "pcs"`, `is_active True`; the card gives `name` and `name_normalized`. **tag** = `item_tags` row built with `ItemTag`: `workspace_id W1.id`, `is_system_tag False`, `is_active True`, `usage_count 0`, `color None`, `icon None`, `description None`, `created_by None`; the card gives `name` and `tag_code`. **system tag** = a tag, but `is_system_tag True`. After the word "but" a card lists every other column that differs.
- These rows exist in every test, inserted in this order, and need no Given line:
  - I1 = item, `name "Bolt M8"`, `name_normalized "bolt m8"`. I2 = item, `name "Washer 10"`, `name_normalized "washer 10"`. IX = item, `name "Old Rivet"`, `name_normalized "old rivet"`, but `is_active False` (the deleted item). I9 = item, `name "Far Spring"`, `name_normalized "far spring"`, but `workspace_id W2.id`.
  - T1 = tag, `name "Spare Part"`, `tag_code "spare_part"`. T2 = tag, `name "Hex Bolt"`, `tag_code "hex_bolt"`. TS = system tag, `name "Raw Material"`, `tag_code "raw_material"`. TD = tag, `name "Obsolete"`, `tag_code "obsolete"`, but `is_active False` (the deleted tag). T9 = tag, `name "Far Crate"`, `tag_code "far_crate"`, but `workspace_id W2.id`.
  - So `T1.id < T2.id < TS.id < TD.id < T9.id`. Further tags a card needs are called K1, K2, …; a further item I3.
- No `item_tag_assignments` row exists unless the card's Given lists it.
- **link of I to T** = `item_tag_assignments` row built with `ItemTagAssignment`: `workspace_id` = I's `workspace_id`, `item_id I.id`, `tag_id T.id`, `assigned_by U1.id`; `assigned_at` left to the model default. After the word "but" the card lists every column that differs.
- A Given line written as code (`l1_id = L1.id`) is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending (not flushed).

**Named checks.**
- **ids(x)** = `[t.id for t in x]`, **names(x)** = `[t.name for t in x]` — lists in the order returned (the order is part of the check); x is a list result or one value of a dict result (`result[I1.id]`). `sorted(ids(...)) == [T1.id, T2.id]` is used where the order is not part of the check; the right-hand ids are written in ascending id order.
- **links_of(I)** = `db.expire_all()`, then SELECT every `item_tag_assignments` row with `item_id == I.id` (any workspace), ordered by `id`, as a list.
- **re-read X** = `db.expire_all()`, then SELECT X by id from its own table; the listed values are database values. "the returned row" = re-read by `result.id`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line, before the call). X may be a link, an item or a tag.
- **nothing written** = the numbers of rows in `item_tag_assignments`, `items` and `item_tags` (all workspaces) equal their values before the call.
- `count:` lines count the rows of the named table in all workspaces, with the filter stated.
- **close to now** = `abs(datetime.now(timezone.utc).replace(tzinfo=None) - value) < timedelta(minutes=5)`.
- `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the call: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards (the savepoint is rolled back). `NotNullViolation`, `UniqueViolation`, `ForeignKeyViolation` = classes of `psycopg2.errors`. Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; the harness adds the marker. Every xfail in this module is strict, except the five cards that rest on physical row order or on the server's collation — ITA-TFS-17, TFS-18, TFI-12, TFI-13, INH-14 — marked `(non-strict)` on their Expect line (`pytest.mark.xfail(strict=False, …)`).

**Rolled back** (cards marked Author: claude only). `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the first checks run inside the savepoint; then `sp.rollback()` and the "after the savepoint rollback" checks.

**Statement recorder** (cards marked Author: claude only). The SQL statements the session sends during the When are recorded. `statements` = the list of their texts; `sql` = the text of the one `SELECT` sent; `order_part` = the text of `sql` after `ORDER BY` (`""` when there is none). A `statement:` line is a check on these texts.

**Race simulations.** None in this module.


## `ItemTagAssignmentDAO.get_tags_for_items`

### ITA-TFS-01 — returns a dict of the active tags per requested item and writes nothing
- **Rules:** `get_tags_for_items` R2, R3, R7, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. Link of I1 to TS.
3. Link of I2 to T2.

**When**
- `result = dao.get_tags_for_items(db, item_ids=[I1.id, I2.id], workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, dict)`.
2. returns: `list(result.keys()) == [I1.id, I2.id]`.
3. returns: `sorted(ids(result[I1.id])) == [T1.id, TS.id]`.
4. returns: `ids(result[I2.id]) == [T2.id]`.
5. returns: `isinstance(result[I1.id][0], ItemTag)`.
6. nothing written: nothing written.

### ITA-TFS-02 — an empty list of item ids returns an empty dict
- **Rules:** `get_tags_for_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I1 to T1.

**When**
- `result = dao.get_tags_for_items(db, item_ids=[], workspace_id=W1.id)`.

**Then**
1. returns: `result == {}`.

### ITA-TFS-03 — item ids None returns an empty dict
- **Rules:** `get_tags_for_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I1 to T1.

**When**
- `result = dao.get_tags_for_items(db, item_ids=None, workspace_id=W1.id)`.

**Then**
1. returns: `result == {}`.

### ITA-TFS-04 — an empty list of item ids sends no query
- **Rules:** `get_tags_for_items` R1 ("nothing is queried")
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude — statement recorder (the emitted SQL is inspected)

**Given**
1. Link of I1 to T1.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_tags_for_items(db, item_ids=[], workspace_id=W1.id)`.

**Then**
1. returns: `result == {}`.
2. statement: `statements == []`.

### ITA-TFS-05 — the keys follow the order of the request, not the order of the ids
- **Rules:** `get_tags_for_items` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. Link of I2 to T2.

**When**
- `result = dao.get_tags_for_items(db, item_ids=[I2.id, I1.id], workspace_id=W1.id)`.

**Then**
1. returns: `list(result.keys()) == [I2.id, I1.id]`.
2. returns: `ids(result[I2.id]) == [T2.id]`.
3. returns: `ids(result[I1.id]) == [T1.id]`.

### ITA-TFS-06 — an id given twice is one key and its tag is listed once
- **Rules:** `get_tags_for_items` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I1 to T1. (I2 has no links.)

**When**
- `result = dao.get_tags_for_items(db, item_ids=[I1.id, I2.id, I1.id], workspace_id=W1.id)`.

**Then**
1. returns: `list(result.keys()) == [I1.id, I2.id]`.
2. returns: `ids(result[I1.id]) == [T1.id]`.
3. returns: `result[I2.id] == []`.

### ITA-TFS-07 — an unknown item id maps to an empty list
- **Rules:** `get_tags_for_items` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I1 to T1.

**When**
- `result = dao.get_tags_for_items(db, item_ids=[I1.id, MISSING], workspace_id=W1.id)`.

**Then**
1. returns: `list(result.keys()) == [I1.id, MISSING]`.
2. returns: `result[MISSING] == []`.
3. returns: `ids(result[I1.id]) == [T1.id]`.

### ITA-TFS-08 — an item without tags maps to an empty list
- **Rules:** `get_tags_for_items` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I2 to T1. (I1 has no links.)

**When**
- `result = dao.get_tags_for_items(db, item_ids=[I1.id], workspace_id=W1.id)`.

**Then**
1. returns: `result == {I1.id: []}`.

### ITA-TFS-09 — a deleted tag is never listed; an item with only a deleted tag maps to an empty list
- **Rules:** `get_tags_for_items` R2, R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. Link of I1 to TD. (TD is the deleted tag.)
3. Link of I2 to TD.

**When**
- `result = dao.get_tags_for_items(db, item_ids=[I1.id, I2.id], workspace_id=W1.id)`.

**Then**
1. returns: `ids(result[I1.id]) == [T1.id]`.
2. returns: `result[I2.id] == []`.
3. unchanged: unchanged(TD).

### ITA-TFS-10 — a link recorded under another workspace is ignored
- **Rules:** `get_tags_for_items` R3, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I1 to T1, but `workspace_id W2.id`. (I1 and T1 belong to W1; the link says W2.)

**When**
- `result = dao.get_tags_for_items(db, item_ids=[I1.id], workspace_id=W1.id)`.

**Then**
1. returns: `result == {I1.id: []}`.

### ITA-TFS-11 — the link's own workspace decides: asked under the link's workspace, the tag is listed
- **Rules:** `get_tags_for_items` R3, R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I1 to T1, but `workspace_id W2.id`. (I1 and T1 belong to W1; the link says W2.)

**When**
- `result = dao.get_tags_for_items(db, item_ids=[I1.id], workspace_id=W2.id)`.

**Then**
1. returns: `ids(result[I1.id]) == [T1.id]`.

### ITA-TFS-12 — the tags of a deleted item are listed like those of a live one
- **Rules:** `get_tags_for_items` R4 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Link of IX to T1. (IX is the deleted item.)

**When**
- `result = dao.get_tags_for_items(db, item_ids=[IX.id], workspace_id=W1.id)`.

**Then**
1. returns: `ids(result[IX.id]) == [T1.id]`.
2. unchanged: unchanged(IX).

### ITA-TFS-13 — a tag of another workspace reached through a link of this workspace is listed
- **Rules:** `get_tags_for_items` R4 (P1)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I1 to T9. (T9 belongs to W2; the link says W1.)

**When**
- `result = dao.get_tags_for_items(db, item_ids=[I1.id], workspace_id=W1.id)`.

**Then**
1. returns: `ids(result[I1.id]) == [T9.id]`.

### ITA-TFS-14 — an item of another workspace reached through a link of this workspace gets its tag
- **Rules:** `get_tags_for_items` R4 (P1)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I9 to T1, but `workspace_id W1.id`. (I9 belongs to W2; the link says W1.)

**When**
- `result = dao.get_tags_for_items(db, item_ids=[I9.id], workspace_id=W1.id)`.

**Then**
1. returns: `ids(result[I9.id]) == [T1.id]`.

### ITA-TFS-15 — a tag on two items is the same object in both lists
- **Rules:** `get_tags_for_items` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. Link of I2 to T1.

**When**
- `result = dao.get_tags_for_items(db, item_ids=[I1.id, I2.id], workspace_id=W1.id)`.

**Then**
1. returns: `len(result[I1.id]) == 1`.
2. returns: `result[I1.id][0].id == T1.id`.
3. returns: `result[I1.id][0] is result[I2.id][0]`.

### ITA-TFS-16 — lower-case names come back alphabetically within each item, the system tag not first
- **Rules:** `get_tags_for_items` R6 (the part that holds today: names with one case only; system tags not grouped first), R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. K1 = tag, `name "delta"`, `tag_code "delta"`.
2. K2 = tag, `name "alpha"`, `tag_code "alpha"`.
3. K3 = tag, `name "charlie"`, `tag_code "charlie"`.
4. K4 = system tag, `name "zulu"`, `tag_code "zulu"`. (Single-word, all-lower-case ASCII names: every collation orders them alike.)
5. Link of I1 to K1.
6. Link of I1 to K4.
7. Link of I1 to K2.
8. Link of I2 to K3.
9. Link of I2 to K2.

**When**
- `result = dao.get_tags_for_items(db, item_ids=[I1.id, I2.id], workspace_id=W1.id)`.

**Then**
1. returns: `names(result[I1.id]) == ["alpha", "delta", "zulu"]`.
2. returns: `names(result[I2.id]) == ["alpha", "charlie"]`.

### ITA-TFS-17 — names that differ only in case come back in id order, then the other names case-insensitively
- **Rules:** `get_tags_for_items` R6 [BUG-933]
- **Kind:** bug
- **Expect:** xfail BUG-933 (non-strict)
- **Fails today on:** Then 2 (tags are ordered by the database collation; on the test database "alpha" sorts before "Alpha", giving [K3.id, K2.id, K1.id, K4.id]. Non-strict because the outcome depends on the server's collation, not on this code alone)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-933")`); the assertion is never weakened

**Given**
1. K1 = tag, `name "bravo"`, `tag_code "bravo"`.
2. K2 = tag, `name "Alpha"`, `tag_code "alpha_upper"`.
3. K3 = tag, `name "alpha"`, `tag_code "alpha_lower"`. (The "Alpha" / "alpha" pair is on purpose: equal ignoring case, so only `id` decides between them.)
4. K4 = system tag, `name "Charlie"`, `tag_code "charlie"`. (A system tag, on purpose: it must not be moved first.)
5. Link of I1 to K1.
6. Link of I1 to K2.
7. Link of I1 to K3.
8. Link of I1 to K4.

**When**
- `result = dao.get_tags_for_items(db, item_ids=[I1.id], workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result[I1.id])) == [K1.id, K2.id, K3.id, K4.id]`.
2. returns: `ids(result[I1.id]) == [K2.id, K3.id, K1.id, K4.id]`.

### ITA-TFS-18 — two tags with the same name come back lower id first
- **Rules:** `get_tags_for_items` R6 [BUG-933]
- **Kind:** bug
- **Expect:** xfail BUG-933 (non-strict)
- **Fails today on:** Then 2 (no tie-break is requested; which of the two comes first depends on the physical row order and the query plan — the links are inserted higher tag id first, so [K2.id, K1.id] is likely, but the intended order can come out by accident)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-933")`); the assertion is never weakened

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt_a"`.
2. K2 = tag, `name "Bolt"`, `tag_code "bolt_b"`. (Same name as K1 on purpose: nothing checks tag names.)
3. Link of I1 to K2. (Inserted first on purpose.)
4. Link of I1 to K1.

**When**
- `result = dao.get_tags_for_items(db, item_ids=[I1.id], workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result[I1.id])) == [K1.id, K2.id]`.
2. returns: `ids(result[I1.id]) == [K1.id, K2.id]`.

### ITA-TFS-19 — the tags-of-items query asks for name case-insensitive, then id
- **Rules:** `get_tags_for_items` R6 [BUG-933]
- **Kind:** bug
- **Expect:** xfail BUG-933
- **Fails today on:** Then 4 (the order is `item_id, name` — `name` is not wrapped in `lower(...)`)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order or collation)

**Given**
1. Link of I1 to T1.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_tags_for_items(db, item_ids=[I1.id], workspace_id=W1.id)`.

**Then**
1. returns: `list(result.keys()) == [I1.id]`.
2. returns: `ids(result[I1.id]) == [T1.id]`.
3. statement: `"ORDER BY" in sql`.
4. statement: `"lower(item_tags.name)" in order_part`.
5. statement: `"item_tags.id" in order_part`.

### ITA-TFS-20 — a link added but not flushed is not seen
- **Rules:** `get_tags_for_items` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. `P1 = ItemTagAssignment(workspace_id=W1.id, item_id=I1.id, tag_id=T2.id, assigned_by=U1.id)`
3. `db.add(P1)` (not flushed).

**When**
- `result = dao.get_tags_for_items(db, item_ids=[I1.id], workspace_id=W1.id)`.

**Then**
1. returns: `ids(result[I1.id]) == [T1.id]`.


## `ItemTagAssignmentDAO.get_tags_for_item`

### ITA-TFI-01 — returns a list of the item's active tags, system and user alike, and writes nothing
- **Rules:** `get_tags_for_item` R1, R2, R5, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. Link of I1 to T2.
3. Link of I1 to TS.
4. Link of I2 to T1. (A link of another item.)

**When**
- `result = dao.get_tags_for_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [T1.id, T2.id, TS.id]`.
3. returns: `isinstance(result[0], ItemTag)`.
4. nothing written: nothing written.

### ITA-TFI-02 — an item without links returns an empty list
- **Rules:** `get_tags_for_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I2 to T1. (I1 has no links.)

**When**
- `result = dao.get_tags_for_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### ITA-TFI-03 — an unknown item id returns an empty list
- **Rules:** `get_tags_for_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I1 to T1.

**When**
- `result = dao.get_tags_for_item(db, item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### ITA-TFI-04 — asked under another workspace, the item's links are not used
- **Rules:** `get_tags_for_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I1 to T1.

**When**
- `result = dao.get_tags_for_item(db, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### ITA-TFI-05 — a link recorded under another workspace is not used
- **Rules:** `get_tags_for_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I1 to T1, but `workspace_id W2.id`. (I1 and T1 belong to W1; the link says W2.)

**When**
- `result = dao.get_tags_for_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### ITA-TFI-06 — the link's own workspace decides: asked under the link's workspace, the tag is returned
- **Rules:** `get_tags_for_item` R1, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I1 to T1, but `workspace_id W2.id`. (I1 and T1 belong to W1; the link says W2.)

**When**
- `result = dao.get_tags_for_item(db, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.

### ITA-TFI-07 — a deleted tag is not returned and left as it was
- **Rules:** `get_tags_for_item` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. Link of I1 to TD. (TD is the deleted tag.)

**When**
- `result = dao.get_tags_for_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.
2. unchanged: unchanged(TD).

### ITA-TFI-08 — an item whose only tag is deleted returns an empty list
- **Rules:** `get_tags_for_item` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Link of I1 to TD. (TD is the deleted tag.)

**When**
- `result = dao.get_tags_for_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### ITA-TFI-09 — the tags of a deleted item are returned
- **Rules:** `get_tags_for_item` R3 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Link of IX to T1. (IX is the deleted item.)
2. Link of IX to T2.

**When**
- `result = dao.get_tags_for_item(db, item_id=IX.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [T1.id, T2.id]`.
2. unchanged: unchanged(IX).

### ITA-TFI-10 — a tag of another workspace reached through a link of this workspace is returned
- **Rules:** `get_tags_for_item` R3 (P1)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I1 to T9. (T9 belongs to W2; the link says W1.)

**When**
- `result = dao.get_tags_for_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T9.id]`.

### ITA-TFI-11 — an item of another workspace reached through a link of this workspace gets its tag
- **Rules:** `get_tags_for_item` R3 (P1)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I9 to T1, but `workspace_id W1.id`. (I9 belongs to W2; the link says W1.)

**When**
- `result = dao.get_tags_for_item(db, item_id=I9.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.

### ITA-TFI-12 — names that differ only in case come back in id order, then the other names case-insensitively
- **Rules:** `get_tags_for_item` R4 [BUG-932]
- **Kind:** bug
- **Expect:** xfail BUG-932 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the database answers in its own order, usually the order the links were inserted, [K1.id, K2.id, K3.id, K4.id] — but that is not guaranteed and could match by accident)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-932")`); the assertion is never weakened

**Given**
1. K1 = tag, `name "bravo"`, `tag_code "bravo"`.
2. K2 = tag, `name "Alpha"`, `tag_code "alpha_upper"`.
3. K3 = tag, `name "alpha"`, `tag_code "alpha_lower"`. (The "Alpha" / "alpha" pair is on purpose: equal ignoring case, so only `id` decides between them.)
4. K4 = system tag, `name "Charlie"`, `tag_code "charlie"`. (A system tag, on purpose: it must not be moved first.)
5. Link of I1 to K1.
6. Link of I1 to K2.
7. Link of I1 to K3.
8. Link of I1 to K4.

**When**
- `result = dao.get_tags_for_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [K1.id, K2.id, K3.id, K4.id]`.
2. returns: `ids(result) == [K2.id, K3.id, K1.id, K4.id]`.

### ITA-TFI-13 — two tags with the same name come back lower id first
- **Rules:** `get_tags_for_item` R4 [BUG-932]
- **Kind:** bug
- **Expect:** xfail BUG-932 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the links are inserted higher tag id first, so [K2.id, K1.id] is likely, but the physical row order and the query plan can give the intended order by accident)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-932")`); the assertion is never weakened

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt_a"`.
2. K2 = tag, `name "Bolt"`, `tag_code "bolt_b"`. (Same name as K1 on purpose: nothing checks tag names.)
3. Link of I1 to K2. (Inserted first on purpose.)
4. Link of I1 to K1.

**When**
- `result = dao.get_tags_for_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [K1.id, K2.id]`.
2. returns: `ids(result) == [K1.id, K2.id]`.

### ITA-TFI-14 — the tags-of-one-item query asks for name case-insensitive, then id
- **Rules:** `get_tags_for_item` R4 [BUG-932]
- **Kind:** bug
- **Expect:** xfail BUG-932
- **Fails today on:** Then 2 (the query has no `ORDER BY`)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order or collation)

**Given**
1. Link of I1 to T1.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_tags_for_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"lower(item_tags.name)" in order_part`.
4. statement: `"item_tags.id" in order_part`.

### ITA-TFI-15 — a link added but not flushed is not seen
- **Rules:** `get_tags_for_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. `P1 = ItemTagAssignment(workspace_id=W1.id, item_id=I1.id, tag_id=T2.id, assigned_by=U1.id)`
3. `db.add(P1)` (not flushed).

**When**
- `result = dao.get_tags_for_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.


## `ItemTagAssignmentDAO.assignment_exists`

### ITA-EX-01 — an existing link gives True and nothing is written
- **Rules:** `assignment_exists` R1, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. L1 = link of I1 to T1.

**When**
- `result = dao.assignment_exists(db, item_id=I1.id, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. nothing written: nothing written.
3. unchanged: unchanged(L1).

### ITA-EX-02 — another tag of the same item gives False
- **Rules:** `assignment_exists` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I1 to T1.

**When**
- `result = dao.assignment_exists(db, item_id=I1.id, tag_id=T2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### ITA-EX-03 — the same tag on another item gives False
- **Rules:** `assignment_exists` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I2 to T1.

**When**
- `result = dao.assignment_exists(db, item_id=I1.id, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### ITA-EX-04 — unknown ids give False
- **Rules:** `assignment_exists` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I1 to T1.

**When**
- `result = dao.assignment_exists(db, item_id=MISSING, tag_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### ITA-EX-05 — a link recorded only under another workspace gives False
- **Rules:** `assignment_exists` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I1 to T1, but `workspace_id W2.id`. (I1 and T1 belong to W1; the link says W2.)

**When**
- `result = dao.assignment_exists(db, item_id=I1.id, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### ITA-EX-06 — the link's own workspace decides: asked under the link's workspace gives True
- **Rules:** `assignment_exists` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I1 to T1, but `workspace_id W2.id`. (I1 and T1 belong to W1; the link says W2.)

**When**
- `result = dao.assignment_exists(db, item_id=I1.id, tag_id=T1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is True`.

### ITA-EX-07 — a link to a deleted tag gives True
- **Rules:** `assignment_exists` R3 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Link of I1 to TD. (TD is the deleted tag.)

**When**
- `result = dao.assignment_exists(db, item_id=I1.id, tag_id=TD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### ITA-EX-08 — a link of a deleted item gives True
- **Rules:** `assignment_exists` R3 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Link of IX to T1. (IX is the deleted item.)

**When**
- `result = dao.assignment_exists(db, item_id=IX.id, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### ITA-EX-09 — a link of this workspace to a tag of another workspace gives True
- **Rules:** `assignment_exists` R3 (P1)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I1 to T9. (T9 belongs to W2; the link says W1.)

**When**
- `result = dao.assignment_exists(db, item_id=I1.id, tag_id=T9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### ITA-EX-10 — a link added but not flushed gives False
- **Rules:** `assignment_exists` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `P1 = ItemTagAssignment(workspace_id=W1.id, item_id=I1.id, tag_id=T1.id, assigned_by=U1.id)`
2. `db.add(P1)` (not flushed).

**When**
- `result = dao.assignment_exists(db, item_id=I1.id, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.


## `ItemTagAssignmentDAO.count_active_items_per_tag`

### ITA-CNT-01 — counts the live items of each tag, system and user tags alike, and writes nothing
- **Rules:** `count_active_items_per_tag` R1, R5 (system tags), R6, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. I3 = item, `name "Spring Pin"`, `name_normalized "spring pin"`.
2. Link of I1 to T1.
3. Link of I2 to T1.
4. Link of I3 to T1.
5. Link of I1 to T2.
6. Link of I2 to TS.

**When**
- `result = dao.count_active_items_per_tag(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, dict)`.
2. returns: `result == {T1.id: 3, T2.id: 1, TS.id: 1}`.
3. nothing written: nothing written.

### ITA-CNT-02 — links to a deleted item are not counted; a tag only on deleted items has no entry
- **Rules:** `count_active_items_per_tag` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. Link of IX to T1. (IX is the deleted item.)
3. Link of IX to T2.

**When**
- `result = dao.count_active_items_per_tag(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {T1.id: 1}`.
2. returns: `T2.id not in result`.

### ITA-CNT-03 — a tag without links has no entry
- **Rules:** `count_active_items_per_tag` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I1 to T1. (T2 has no links.)

**When**
- `result = dao.count_active_items_per_tag(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {T1.id: 1}`.
2. returns: `T2.id not in result`.

### ITA-CNT-04 — links of another workspace are not counted
- **Rules:** `count_active_items_per_tag` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. Link of I9 to T9. (A link of W2.)

**When**
- `result = dao.count_active_items_per_tag(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {T1.id: 1}`.

### ITA-CNT-05 — the other workspace gets only its own count
- **Rules:** `count_active_items_per_tag` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. Link of I9 to T9. (A link of W2.)

**When**
- `result = dao.count_active_items_per_tag(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == {T9.id: 1}`.

### ITA-CNT-06 — an unknown workspace returns an empty dict
- **Rules:** `count_active_items_per_tag` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I1 to T1.

**When**
- `result = dao.count_active_items_per_tag(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == {}`.

### ITA-CNT-07 — a workspace without links returns an empty dict
- **Rules:** `count_active_items_per_tag` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I1 to T1. (W2 has no links.)

**When**
- `result = dao.count_active_items_per_tag(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == {}`.

### ITA-CNT-08 — an item of another workspace linked under this workspace is counted
- **Rules:** `count_active_items_per_tag` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I9 to T1, but `workspace_id W1.id`. (I9 belongs to W2; the link says W1.)

**When**
- `result = dao.count_active_items_per_tag(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {T1.id: 1}`.

### ITA-CNT-09 — a deleted tag with links to live items has an entry
- **Rules:** `count_active_items_per_tag` R5 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Link of I1 to TD. (TD is the deleted tag.)
2. Link of I2 to TD.

**When**
- `result = dao.count_active_items_per_tag(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {TD.id: 2}`.

### ITA-CNT-10 — a tag of another workspace linked under this workspace has an entry
- **Rules:** `count_active_items_per_tag` R5 (P1)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I1 to T9. (T9 belongs to W2; the link says W1.)

**When**
- `result = dao.count_active_items_per_tag(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {T9.id: 1}`.

### ITA-CNT-11 — a link added but not flushed is not counted
- **Rules:** `count_active_items_per_tag` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. `P1 = ItemTagAssignment(workspace_id=W1.id, item_id=I2.id, tag_id=T1.id, assigned_by=U1.id)`
3. `db.add(P1)` (not flushed).

**When**
- `result = dao.count_active_items_per_tag(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {T1.id: 1}`.


## `ItemTagAssignmentDAO.remove_all_tags_from_item`

### ITA-RM-01 — every link of the item is deleted and their number returned
- **Rules:** `remove_all_tags_from_item` R1, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. Link of I1 to T2.
3. Link of I1 to TS.

**When**
- `result = dao.remove_all_tags_from_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 3`.
2. count: links_of(I1) has exactly 0 rows.
3. count: `item_tag_assignments` has exactly 0 rows.

### ITA-RM-02 — a link to a deleted tag is deleted and counted too; the tag stays deleted
- **Rules:** `remove_all_tags_from_item` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. Link of I1 to TD. (TD is the deleted tag.)

**When**
- `result = dao.remove_all_tags_from_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 2`.
2. count: links_of(I1) has exactly 0 rows.
3. unchanged: unchanged(TD).
4. re-read TD: `is_active is False`.

### ITA-RM-03 — the links of a deleted item are deleted; the item is not touched
- **Rules:** `remove_all_tags_from_item` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Link of IX to T1. (IX is the deleted item.)
2. Link of IX to T2.

**When**
- `result = dao.remove_all_tags_from_item(db, item_id=IX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 2`.
2. count: links_of(IX) has exactly 0 rows.
3. unchanged: unchanged(IX).

### ITA-RM-04 — the links of other items stay
- **Rules:** `remove_all_tags_from_item` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. L2 = link of I2 to T1.
3. L3 = link of I2 to T2.

**When**
- `result = dao.remove_all_tags_from_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.
2. count: links_of(I1) has exactly 0 rows.
3. count: links_of(I2) has exactly 2 rows.
4. unchanged: unchanged(L2).
5. unchanged: unchanged(L3).

### ITA-RM-05 — a link of the same item recorded under another workspace stays
- **Rules:** `remove_all_tags_from_item` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. L2 = link of I1 to T2, but `workspace_id W2.id`. (I1 belongs to W1; this link says W2.)

**When**
- `result = dao.remove_all_tags_from_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.
2. count: links_of(I1) has exactly 1 row.
3. unchanged: unchanged(L2).
4. re-read L2: `workspace_id == W2.id`, `tag_id == T2.id`.

### ITA-RM-06 — the item and tag rows are not written and the tag counter stays
- **Rules:** `remove_all_tags_from_item` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. K1 = tag, `name "Gasket"`, `tag_code "gasket"`, but `usage_count 4`.
2. Link of I1 to K1.

**When**
- `result = dao.remove_all_tags_from_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.
2. re-read K1: `usage_count == 4`.
3. unchanged: unchanged(K1).
4. unchanged: unchanged(I1).
5. count: `items` has exactly 4 rows.
6. count: `item_tags` has exactly 6 rows.

### ITA-RM-07 — an item without links returns 0 and nothing is written
- **Rules:** `remove_all_tags_from_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L2 = link of I2 to T1. (I1 has no links.)

**When**
- `result = dao.remove_all_tags_from_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 0`.
2. nothing written: nothing written.
3. unchanged: unchanged(L2).

### ITA-RM-08 — an unknown item id returns 0 and nothing is written
- **Rules:** `remove_all_tags_from_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. L1 = link of I1 to T1.

**When**
- `result = dao.remove_all_tags_from_item(db, item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == 0`.
2. nothing written: nothing written.
3. unchanged: unchanged(L1).

### ITA-RM-09 — the deletion is flushed but not committed: gone in the session, back after a rollback
- **Rules:** `remove_all_tags_from_item` R5
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — savepoint rollback and a commit spy

**Given**
1. L1 = link of I1 to T1.
2. Link of I1 to T2.
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.remove_all_tags_from_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 2`.
2. count: links_of(I1) has exactly 0 rows (inside the savepoint).
3. count: after the savepoint rollback, links_of(I1) has exactly 2 rows.
4. re-read L1 after the savepoint rollback: `tag_id == T1.id`, `assigned_by == U1.id`.
5. mock called: the `db.commit` spy was never called.

### ITA-RM-10 — a link added but not flushed is not deleted and is saved by the method's flush
- **Rules:** `remove_all_tags_from_item` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `P1 = ItemTagAssignment(workspace_id=W1.id, item_id=I1.id, tag_id=T2.id, assigned_by=U1.id)`
2. `db.add(P1)` (not flushed; I1 has no flushed link).

**When**
- `result = dao.remove_all_tags_from_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 0`.
2. count: links_of(I1) has exactly 1 row.
3. re-read links_of(I1)[0]: `tag_id == T2.id`.

### ITA-RM-11 — the deleted link objects leave the session; a link of another item stays in it
- **Rules:** `remove_all_tags_from_item` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. L1 = link of I1 to T1.
2. L2 = link of I1 to T2.
3. L3 = link of I2 to T1.

**When**
- `result = dao.remove_all_tags_from_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 2`.
2. returns: `L1 not in db`.
3. returns: `L2 not in db`.
4. returns: `L3 in db`.

### ITA-RM-12 — an item whose tag links were already loaded still lists them
- **Rules:** `remove_all_tags_from_item` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. Link of I1 to T1.
2. Link of I1 to T2.
3. `loaded = len(I1.tag_assignments)` (loads the collection into the session; `loaded == 2`).

**When**
- `result = dao.remove_all_tags_from_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 2`.
2. returns: `len(I1.tag_assignments) == 2` (read on the same I1 object, before any re-read).
3. count: links_of(I1) has exactly 0 rows.

### ITA-RM-13 — a later flush of the item does not bring the deleted links back
- **Rules:** `remove_all_tags_from_item` R6
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — changes the standing row I1 and flushes between the call and the checks

**Given**
1. Link of I1 to T1.
2. Link of I1 to T2.
3. `loaded = len(I1.tag_assignments)` (loads the collection into the session).

**When**
- `result = dao.remove_all_tags_from_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 2`.
2. count: after `I1.name = "Bolt M8 Long"` and `db.flush()`, links_of(I1) has exactly 0 rows.
3. count: `item_tag_assignments` has exactly 0 rows.

### ITA-RM-14 — the same item and tag can be linked again right after; the new link has a new id
- **Rules:** `remove_all_tags_from_item` R6
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — a follow-up DAO call (`dao.create`) after the When

**Given**
1. L1 = link of I1 to T1.
2. `l1_id = L1.id`

**When**
- `result = dao.remove_all_tags_from_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.
2. returns: after `new = dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "tag_id": T1.id})`, `new.id != l1_id`.
3. count: links_of(I1) has exactly 1 row.
4. re-read links_of(I1)[0]: `id != l1_id`, `tag_id == T1.id`.


## Inherited `BaseDAO` methods on `ItemTagAssignment`

### ITA-INH-01 — create with a dict stores a link with assigned_at set and assigned_by None
- **Rules:** inherited R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No link exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "tag_id": T1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `item_id == I1.id`, `tag_id == T1.id`.
3. re-read the returned row: `assigned_by is None`.
4. re-read the returned row: `assigned_at.tzinfo is None`.
5. re-read the returned row: `assigned_at` is close to now.
6. count: `item_tag_assignments` has exactly 1 row.

### ITA-INH-02 — create with assigned_by stores it
- **Rules:** inherited R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No link exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "tag_id": T1.id, "assigned_by": U2.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `assigned_by == U2.id`.
3. re-read the returned row: `assigned_at is not None`.

### ITA-INH-03 — create with an ItemTagAssignmentCreate schema fails on flush and saves nothing
- **Rules:** inherited R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No link exists.

**When**
- `dao.create(db, obj_in=ItemTagAssignmentCreate(item_id=I1.id, tag_id=T1.id))`. (The schema has no `workspace_id`.)

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, NotNullViolation)`.
3. raises: `"workspace_id" in str(exc.value.orig)`.
4. nothing written: nothing written.
5. count: `item_tag_assignments` has exactly 0 rows.

### ITA-INH-04 — a second link for the same item and tag fails on flush and the first stays
- **Rules:** inherited R2, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = link of I1 to T1.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "tag_id": T1.id})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, UniqueViolation)`.
3. raises: `"uq_item_tag" in str(exc.value.orig)`.
4. unchanged: unchanged(L1).
5. count: links_of(I1) has exactly 1 row.

### ITA-INH-05 — a second link for the same item and tag fails also under another workspace
- **Rules:** inherited R2, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. L1 = link of I1 to T1.

**When**
- `dao.create(db, obj_in={"workspace_id": W2.id, "item_id": I1.id, "tag_id": T1.id})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, UniqueViolation)`.
3. raises: `"uq_item_tag" in str(exc.value.orig)`.
4. unchanged: unchanged(L1).
5. count: links_of(I1) has exactly 1 row.

### ITA-INH-06 — create with an unknown item_id fails on flush and saves nothing
- **Rules:** inherited R2, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. No link exists.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "item_id": MISSING, "tag_id": T1.id})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"item_tag_assignments_item_id_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.

### ITA-INH-07 — create with an unknown tag_id fails on flush and saves nothing
- **Rules:** inherited R2, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. No link exists.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "tag_id": MISSING})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"item_tag_assignments_tag_id_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.

### ITA-INH-08 — create with an unknown workspace_id fails on flush and saves nothing
- **Rules:** inherited R2, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. No link exists.

**When**
- `dao.create(db, obj_in={"workspace_id": MISSING, "item_id": I1.id, "tag_id": T1.id})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"item_tag_assignments_workspace_id_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.

### ITA-INH-09 — create with an unknown assigned_by fails on flush and saves nothing
- **Rules:** inherited R2, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. No link exists.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "tag_id": T1.id, "assigned_by": MISSING})`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `isinstance(exc.value.orig, ForeignKeyViolation)`.
3. raises: `"item_tag_assignments_assigned_by_fkey" in str(exc.value.orig)`.
4. nothing written: nothing written.

### ITA-INH-10 — create saves a link to a deleted tag
- **Rules:** inherited R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. No link exists. (TD is the deleted tag.)

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "tag_id": TD.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `tag_id == TD.id`.
3. count: links_of(I1) has exactly 1 row.

### ITA-INH-11 — create saves a link of a deleted item
- **Rules:** inherited R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. No link exists. (IX is the deleted item.)

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "item_id": IX.id, "tag_id": T1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `item_id == IX.id`.
3. count: links_of(IX) has exactly 1 row.

### ITA-INH-12 — create saves a link between an item and a tag of different workspaces
- **Rules:** inherited R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No link exists. (I1 belongs to W1, T9 to W2.)

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "item_id": I1.id, "tag_id": T9.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `workspace_id == W1.id`, `item_id == I1.id`, `tag_id == T9.id`.

### ITA-INH-13 — get_by_workspace returns the links of that workspace only
- **Rules:** inherited R4 (the part that holds today)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. L1 = link of I1 to T1.
2. L2 = link of I2 to T2.
3. L9 = link of I9 to T9. (A link of W2.)

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [L1.id, L2.id]`.
2. returns: `len(result) == 2`.

### ITA-INH-14 — get_by_workspace returns the links in id order
- **Rules:** inherited R4 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (no ordering is requested; the order is the physical row order and the plan's — after the update L1 may come back after L2, e.g. under a sequential scan, but it can also equal the intended order)
- **Author:** claude — non-strict xfail (`pytest.mark.xfail(strict=False, reason="BUG-100")`); the assertion is never weakened

**Given**
1. L1 = link of I1 to T1.
2. L2 = link of I2 to T2.
3. L1 is changed after L2 was created: `L1.assigned_by = U2.id`, then `db.flush()`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [L1.id, L2.id]`.
2. returns: `ids(result) == [L1.id, L2.id]`.

### ITA-INH-15 — the workspace list query on links asks the database for id order
- **Rules:** inherited R4 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 2 (the query has no `ORDER BY`)
- **Author:** claude — statement recorder (the emitted SQL is inspected; does not depend on row order)

**Given**
1. L1 = link of I1 to T1.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [L1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"item_tag_assignments.id" in order_part`.

### ITA-INH-16 — remove deletes one link for good
- **Rules:** inherited R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. L1 = link of I1 to T1.
2. L2 = link of I1 to T2.
3. `l1_id = L1.id`

**When**
- `result = dao.remove(db, id=l1_id)`.

**Then**
1. returns: `result.id == l1_id`.
2. count: `item_tag_assignments` rows with `id == l1_id`: exactly 0.
3. unchanged: unchanged(L2).

### ITA-INH-17 — update with a dict sets the given column and nothing else
- **Rules:** inherited R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. L1 = link of I1 to T1.
2. `at_before = L1.assigned_at`

**When**
- `result = dao.update(db, db_obj=L1, obj_in={"assigned_by": U2.id})`.

**Then**
1. returns: `result.id == L1.id`.
2. re-read L1: `assigned_by == U2.id`.
3. re-read L1: `assigned_at == at_before`.
4. re-read L1: `item_id == I1.id`, `tag_id == T1.id`, `workspace_id == W1.id`.

### ITA-INH-18 — deleting a tag row in the database deletes its links
- **Rules:** Overview model facts ("hard-deleting … a tag … deletes its links (`ON DELETE CASCADE`)")
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude — a direct SQL statement as the When (not the ORM; Spec gap 5)

**Given**
1. K1 = tag, `name "Scrap"`, `tag_code "scrap"`.
2. Link of I1 to K1.
3. L2 = link of I1 to T1.

**When**
- `db.execute(text("delete from item_tags where id = :i"), {"i": K1.id})`.

**Then**
1. count: links_of(I1) has exactly 1 row.
2. re-read L2: `tag_id == T1.id`.
3. count: `item_tag_assignments` rows with `tag_id == K1.id`: exactly 0.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| P2 / BUG-934 — a tag save keeps the links of staying tags (same `id`, `assigned_by`, `assigned_at`, no counter change); only removed / new tags change (FU-1 (a)) | item manager spec (`update_item` with `tag_ids`) | The strict xfail cards for BUG-934. No card here: this DAO's `remove_all_tags_from_item` does what its name says (ITA-RM-01 … RM-14). |
| P3 / BUG-935 — a tag save leaves links to deleted tags untouched; they come back when the tag is restored (FU-1 (b), (c)) | item manager spec (`update_item`) | The strict xfail cards for BUG-935. Here ITA-RM-02 documents that the DAO method itself removes them. |
| Dead code after BUG-934 — `remove_all_tags_from_item` | the change that fixes BUG-934 (`docs/testing/dead-code-removal-checklist.md`) | Delete ITA-RM-01 … RM-14 with the method. |
| FU-1 (d), (e), (g) — `delete_item` keeps links and lowers only active tags' counters; `_assign_tags_to_item` skips tags already on the item (raw `assignment_exists`) and attaches a repeated id once; all counter changes go through the item tag DAO | item manager spec | Here `assignment_exists` is raw (ITA-EX-07 … EX-09). |
| FU-1 (f) / FU-3 — the manager pass-throughs and the item summary inherit BUG-932 / BUG-933 and P1 | item manager spec; item summary service spec | Here the DAO order cards (TFS-17 … TFS-19, TFI-12 … TFI-14). |
| FU-2 — `get_tags` replaces `usage_count` by the live count (`result.get(tag.id, 0)`) | item tag service spec (`get_tags`) | Here a tag without links has no entry (ITA-CNT-03). |
| FU-4 — `ItemWithTagsResponse` / `ItemTagAssignmentResponse` of `app/schemas/item_tag_assignment.py` unused | schemas review | No card. |
| `get_tags_for_item` R3 (last sentence) — "the same tags as `get_tags_for_items` gives for that item" | none (covered indirectly) | No two-call card: each situation (deleted tag, deleted item, foreign tag / item, other workspace) has a card for both methods with the same Given. |
| Inherited `get`, `get_multi`, `create`, `update`, `remove`, `get_by_workspace`, `get_by_id_and_workspace` — generic behaviour (paging, missing ids, flushed-not-committed) | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not repeated here; only what the `ItemTagAssignment` model and its schema change has cards (ITA-INH-01 … INH-18). |
| Notes "keyword-only parameters" (a positional call raises `TypeError`) | none (no rule) | Spec gap 2. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | inherited Errors ("Detail message: — (not asserted)") | The Raises column names the constraint of each violation, but the text is "not asserted". | Designed as loose checks: the constraint (or column) name is contained in `str(exc.value.orig)` (ITA-INH-03 … INH-09). Drop those lines if the text is not meant to be asserted. |
| 2 | Notes for the test designer ("every parameter after `db` is keyword-only — a positional call raises `TypeError`") | Stated as a note, not as a rule of any callable. | No card. |
| 3 | `get_tags_for_items` R6, `get_tags_for_item` R4 ("name case-insensitive") | How the case-insensitive key is expressed in SQL is not stated (`lower(name)`, a case-insensitive collation, …); nor whether `get_tags_for_items` keeps `item_id` first in its `ORDER BY`. | The strict recorder cards ITA-TFS-19, TFI-14 assert `lower(item_tags.name)` and `item_tags.id` in the `ORDER BY` (same choice as ITG-SYS-10, ACT-13), not their position. If the fix uses another form, those lines change with it. |
| 4 | Model facts ("Schema `ItemTagAssignmentCreate` = …") | The module of `ItemTagAssignmentCreate` is not named (FU-4 names `app/schemas/item_tag_assignment.py` for the module's other schemas). | Conventions assume `app.schemas.item_tag_assignment` (ITA-INH-03). Correct the Conventions line if it differs. |
| 5 | Model facts ("Hard-deleting an item, a tag or a workspace deletes its links (`ON DELETE CASCADE`)"; relationships "no cascade options") | What an ORM delete of a tag or item that still has links does (e.g. the item tag DAO's inherited `remove`) is not stated: the database cascade and the ORM's handling of the backref collection may differ. | ITA-INH-18 shows the database cascade with a direct `DELETE` statement for a tag only; no card for item / workspace hard delete (the application never hard-deletes them) and none for the ORM path. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_tags_for_items` | Returns (dict of lists of `ItemTag`) | ITA-TFS-01 |
| `get_tags_for_items` | R1 | ITA-TFS-02, TFS-03, TFS-04 |
| `get_tags_for_items` | R2 | ITA-TFS-01, TFS-05, TFS-06, TFS-07, TFS-08, TFS-09, TFS-10, TFS-16 |
| `get_tags_for_items` | R3 | ITA-TFS-01, TFS-09, TFS-10, TFS-11 |
| `get_tags_for_items` | R4 (P1) | ITA-TFS-11, TFS-12, TFS-13, TFS-14 |
| `get_tags_for_items` | R5 | ITA-TFS-15 |
| `get_tags_for_items` | R6 [BUG-933] | ITA-TFS-16 (pass: one-case names, system tag not first); TFS-17, TFS-18 (non-strict xfail); TFS-19 (strict xfail, statement recorder) |
| `get_tags_for_items` | R7 | ITA-TFS-01 (nothing written; all tags of the item), TFS-16 (three tags of one item), TFS-20 (only flushed links) |
| `get_tags_for_item` | Returns (list of `ItemTag`) | ITA-TFI-01 |
| `get_tags_for_item` | R1 | ITA-TFI-01, TFI-02, TFI-03, TFI-04, TFI-05, TFI-06 |
| `get_tags_for_item` | R2 | ITA-TFI-01 (system tag), TFI-07, TFI-08 |
| `get_tags_for_item` | R3 (P1) | ITA-TFI-06, TFI-09, TFI-10, TFI-11; "same as `get_tags_for_items`" indirect (Deferred) |
| `get_tags_for_item` | R4 [BUG-932] | ITA-TFI-12, TFI-13 (non-strict xfail); TFI-14 (strict xfail, statement recorder) |
| `get_tags_for_item` | R5 | ITA-TFI-01 (nothing written; three tags), TFI-15 (only flushed links) |
| `assignment_exists` | Returns (`bool`) | ITA-EX-01, EX-02 |
| `assignment_exists` | R1 | ITA-EX-01, EX-02, EX-03, EX-04 |
| `assignment_exists` | R2 | ITA-EX-05, EX-06 |
| `assignment_exists` | R3 (P1) | ITA-EX-07, EX-08, EX-09 |
| `assignment_exists` | R4 | ITA-EX-10 |
| `assignment_exists` | R5 | ITA-EX-01 |
| `count_active_items_per_tag` | Returns (dict) | ITA-CNT-01 |
| `count_active_items_per_tag` | R1 | ITA-CNT-01 |
| `count_active_items_per_tag` | R2 | ITA-CNT-02, CNT-03 |
| `count_active_items_per_tag` | R3 | ITA-CNT-04, CNT-05, CNT-06, CNT-07 |
| `count_active_items_per_tag` | R4 | ITA-CNT-08 |
| `count_active_items_per_tag` | R5 (P1) | ITA-CNT-01 (system tag), CNT-09, CNT-10 |
| `count_active_items_per_tag` | R6 | ITA-CNT-01 (nothing written), CNT-11 (only flushed links); "no meaningful order" — dict equality only |
| `remove_all_tags_from_item` | Returns (`int`) | ITA-RM-01, RM-07 |
| `remove_all_tags_from_item` | R1 | ITA-RM-01 |
| `remove_all_tags_from_item` | R2 | ITA-RM-02, RM-03 |
| `remove_all_tags_from_item` | R3 | ITA-RM-04, RM-05, RM-06 |
| `remove_all_tags_from_item` | R4 | ITA-RM-07, RM-08 |
| `remove_all_tags_from_item` | R5 | ITA-RM-09, RM-10 |
| `remove_all_tags_from_item` | R6 | ITA-RM-11, RM-12, RM-13, RM-14 |
| `remove_all_tags_from_item` | Errors (none) | ITA-RM-07, RM-08 are the "nothing to do" paths |
| `remove_all_tags_from_item` | Side effects (rows deleted and flushed, no other table, no commit) | ITA-RM-01, RM-06, RM-09 |
| inherited | R1 | ITA-INH-01, INH-02 |
| inherited | R2 | ITA-INH-03 … INH-09 |
| inherited | R3 | ITA-INH-10, INH-11, INH-12 |
| inherited | R4 [BUG-100] | ITA-INH-14 (non-strict xfail); INH-15 (strict xfail, statement recorder); INH-13 (pass companion) |
| inherited | R5 | ITA-INH-16, INH-17 |
| inherited | Errors row 1 (`NotNullViolation`) | ITA-INH-03 |
| inherited | Errors row 2 (`UniqueViolation`, same and other workspace) | ITA-INH-04, INH-05 |
| inherited | Errors row 3 (`ForeignKeyViolation` ×4) | ITA-INH-06, INH-07, INH-08, INH-09 |
| model facts | `ON DELETE CASCADE` from a tag | ITA-INH-18 |
| BUG-932 | `get_tags_for_item` R4 | ITA-TFI-12, TFI-13, TFI-14 |
| BUG-933 | `get_tags_for_items` R6 | ITA-TFS-17, TFS-18, TFS-19 |
| BUG-100 | inherited R4 | ITA-INH-14, INH-15 |
| BUG-934, BUG-935 | item manager | Deferred |
