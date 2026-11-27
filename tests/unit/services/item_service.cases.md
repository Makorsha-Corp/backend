# Test cases — `app/services/item_service.py`

> **Spec:** `tests/unit/services/item_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Counts:** 71 cases · 36 expected-to-pass · 35 expected-to-fail (bugs) · 10 deferred
> **Revision:** 2 (2026-11-04) — spec gained `get_similar_items` R1a (default `limit` 5) → new ITS-S-08 (pass; ID free in both `item_service` and `item_tag_service` cases files). Verifier findings addressed (`item_service.verify.md`): Finding 1 / mutants #38, #40 → ITS-P-10 now gives I1 `updated_by U2.id` and `updated_at datetime(2026, 2, 3, 4, 5, 6)` (both differ from the schema's `None` defaults) and asserts both; Finding 2 (hand variant `delete_tc3_norollback`) → ITS-D-09 gains an uncommitted "Extra" row and a `count:` = 0 line before any test-level rollback (TC3); Finding 3 / mutant #14 → ITS-S-08. No other card changed.

## Reviewer summary
- **Per callable:** `create_item` 12 (7 bug) · `get_item` 7 (3 bug) · `get_items_page` 18 (7 bug) · `get_distinct_units` 3 (1 bug) · `get_similar_items` 8 (2 bug) · `update_item` 12 (9 bug) · `delete_item` 11 (6 bug).
- **Depth:** lighter target for the transaction wrapper (skill step 1a): TC2, TC4, TC5 once (on create, the commit helper is shared), TC1 and TC3 once per writer, TC6 once per read. The service's own decisions get full cards: the D1 translations, the page shaping (`total`, `has_more` on both sides of `skip + len < total`, `limit=0`, the tag dicts, the row fields, BUG-1573) and the similar-name `query` / `normalized_query`.
- **Translations (D1):** one patched-manager card per translated message and status: create 404 (unknown tag), 400 (deleted tag), 409 (SKU); update 404 (the item's not-found text is rewritten); delete 404 (manager not-found), 400 (already deleted), 400 with blockers (in use). Update's tag / SKU translations reuse the texts and statuses of create and are not repeated (once per status). Real-rows cards for each bug the spec names: BUG-944, BUG-943, BUG-946 on create; BUG-940, BUG-941, BUG-938 on update; BUG-937, BUG-948 on delete. One "other `ValueError` passes unchanged" pass card per writer (the translation is per method).
- **Pass-through bugs:** one card each, strictness as in `item_manager.cases.md` / the DAO cases files (BUG-017 on the unit list only): BUG-012, BUG-013, BUG-014, BUG-015, BUG-017, BUG-033, BUG-034, BUG-934, BUG-935, BUG-936, BUG-939, BUG-942, BUG-945, BUG-947 strict; BUG-018, BUG-933 non-strict (row order). BUG-011, BUG-016 (endpoint), BUG-931 (race), BUG-932 (not reached) are Deferred.
- **Notable design choices:** commit point and uncommitted-extra-row device as `department_service.cases.md`. TC3 is reached without a manager bug through an unknown `user_id` (`items_created_by_fkey` / `items_updated_by_fkey`, manager spec R10 / R16) on create and update, and through the service's own 404 pre-check on delete and its generic error path (ITS-D-09, patched manager). ITS-D-02 spies on the manager's `delete_item` (wraps the real method) to show it is not called after the pre-check's 404.
- **Needs a decision:** None (spec gap 1 is not blocking).

## Conventions for this module

**IDs.** `ITS` = `app/services/item_service.py`. `C` create_item · `G` get_item · `P` get_items_page · `N` get_distinct_units · `S` get_similar_items · `U` update_item · `D` delete_item.

**Actors and fixed values.**
- `svc` = the singleton `item_service` (`from app.services.item_service import ItemService, item_service`). `db` = the test's real session, always the first argument; the rest by keyword. `result` = what the When call returns.
- W1, W2 = two `workspaces` rows; U1, U2 = two `profiles` rows (`make_workspace`, `make_profile`). U1 created every Given row, U2 is the acting user. They exist in every test.
- Classes: `Item` (`app.models.item`), `ItemTag` (`app.models.item_tag`), `ItemTagAssignment` (`app.models.item_tag_assignment`), `Factory` (`app.models.factory`). `ItemCreate`, `ItemUpdate` (`app.schemas.item`). `NotFoundError`, `ConflictError`, `AppValidationError` = `app.core.exceptions.NotFoundError`, `.ConflictError`, `.ValidationError`. `IntegrityError` (`sqlalchemy.exc`); `inspect`, `text` (`sqlalchemy`); `patch` (`unittest.mock`); `datetime` (`datetime`).
- MISSING = `999999999`.

**Externals.** None. Cards that say "with the manager patch `<method>` raising `<exc>`" wrap the When in `with patch.object(svc.item_manager, "<method>", side_effect=<exc>):`, inside the `raises:` wrap. That patch isolates the service's translation; it is not a race simulation.

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A Given line written as code is a step to run exactly.
- **item** = `Item(workspace_id=W1.id, unit="pcs", description=None, sku=None, item_type="physical", is_active=True, created_by=U1.id, updated_by=None)`; the card gives `name` and `name_normalized`. **I1** = item, `name "Bolt M8"`, `name_normalized "bolt m8"`. **I2** = item, `name "Washer Ten"`, `name_normalized "washer ten"`. **IX** = item, `name "Old Rivet"`, `name_normalized "old rivet"`, `is_active False` (a deleted item). **I9** = item, `name "Far Spring"`, `name_normalized "far spring"`, `workspace_id W2.id`.
- **tag** = `ItemTag(workspace_id=W1.id, is_system_tag=False, is_active=True, usage_count=0, created_by=None)`. **T1** = tag, `name "Spare Part"`, `tag_code "spare_part"`. **TD** = tag, `name "Obsolete"`, `tag_code "obsolete"`, `is_active False` (a deleted tag).
- **link of I to T** = `ItemTagAssignment(workspace_id=W1.id, item_id=I.id, tag_id=T.id, assigned_by=U1.id)`.
- **F1** = `Factory(workspace_id=W1.id, name="Main Plant", abbreviation="MP", created_by=U1.id)`. **stock of I** = an `inventory` row (the model class of that table): `workspace_id W1.id`, `item_id I.id`, `factory_id F1.id`, `inventory_type InventoryTypeEnum.STORAGE` (`app.models.enums`), `is_deleted False`, `created_by U1.id`; the card gives `qty`.
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). A Given line marked "(after the commit point)" runs after it, is flushed, and stays uncommitted.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the row counts of `items`, `item_tags`, `item_tag_assignments` (all workspaces) equal their values at the commit point.
- **stored_count(T)** = `db.scalar(text("select usage_count from item_tags where id = :i"), {"i": T.id})`. **tag_ids_of(I)** = sorted `tag_id` of a fresh SELECT of `item_tag_assignments` with `item_id == I.id`.
- **ids(x)** = `sorted(r.id for r in x)`. `count:` lines count with a fresh query, with the filter stated.
- `loaded:` lines run on the returned object first: each column named is not in `inspect(result).unloaded`.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `session:` lines check `db` itself; "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: <Type>`: plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint. Further `raises:` lines assert on `exc.value` after the block.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = the same with `patch.object(db, "refresh", side_effect=RuntimeError("boom"))` only.

**xfail cards.** Write the call and checks as shown, also when a parameter does not exist yet. `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` when the Expect line says `(non-strict)`; the assertion of a non-strict card is never weakened.

**Race simulations.** None in this module.

## `ItemService.create_item`

### ITS-C-01 — a new item with a tag is committed and returned re-read
- **Rules:** `create_item` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1, but `usage_count 3`.

**When**
- `result = svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs", sku="B-M8", tag_ids=[T1.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `created_at`, `name`, `name_normalized`, `workspace_id`, `created_by`.
2. returns: `isinstance(result, Item)`.
3. returns: `result.id is not None`, `result.name == "Bolt M8"`, `result.sku == "B-M8"`.
4. committed: the row with `id == result.id` exists: `name == "Bolt M8"`, `name_normalized == "bolt m8"`, `workspace_id == W1.id`, `created_by == U2.id`, `is_active is True`.
5. committed: `tag_ids_of` the new item `== [T1.id]`.
6. committed: `stored_count(T1) == 4`.

### ITS-C-02 — an unknown user: the IntegrityError passes unchanged, the session is rolled back and usable
- **Rules:** `create_item` R3, Errors row 4; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. I2.
2. X = item, `name "Extra"`, `name_normalized "extra"` (after the commit point).

**When**
- `svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. count: `items` rows with `name == "Bolt M8"`: exactly 0.
4. count: `items` rows with `name == "Extra"`: exactly 0.
5. nothing written: nothing written.
6. unchanged: unchanged(I2).
7. session: usable.

### ITS-C-03 — a failing commit is rolled back and re-raised
- **Rules:** `create_item` R3; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. No items exist.

**When**
- `svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `items` rows with `name == "Bolt M8"`: exactly 0.
4. nothing written: nothing written.

### ITS-C-04 — a failing re-read after the commit leaves the item saved
- **Rules:** `create_item` R3; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. No items exist.

**When**
- `svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `items` rows of W1 with `name == "Bolt M8"`: exactly 1.

### ITS-C-05 — the manager's unknown-tag ValueError becomes NotFoundError 404 after a rollback
- **Rules:** `create_item` R2 [BUG-944], Errors row 1; TC3
- **Kind:** bug
- **Expect:** xfail BUG-944
- **Fails today on:** Then 1 (the call raises ValueError: the service translates nothing)

**Given**
1. I2.
2. X = item, `name "Extra"`, `name_normalized "extra"` (after the commit point).

**When**
- `svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`, with the manager patch `create_item` raising `ValueError("Item tag 999999999 not found")`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Item tag 999999999 not found"`.
4. count: `items` rows with `name == "Extra"`: exactly 0.
5. unchanged: unchanged(I2).

### ITS-C-06 — the manager's deleted-tag ValueError becomes ValidationError 400
- **Rules:** `create_item` R2 [BUG-943], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-943
- **Fails today on:** Then 1 (the call raises ValueError: the service translates nothing)

**Given**
1. No items exist.

**When**
- `svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`, with the manager patch `create_item` raising `ValueError("Item tag 77 is not active")`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Item tag 77 is not active"`.
4. nothing written: nothing written.

### ITS-C-07 — the manager's SKU ValueError becomes ConflictError 409
- **Rules:** `create_item` R2 [BUG-946], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-946
- **Fails today on:** Then 1 (the call raises ValueError: the service translates nothing)

**Given**
1. No items exist.

**When**
- `svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`, with the manager patch `create_item` raising `ValueError("Item with SKU 'B-M8' already exists")`.

**Then**
1. raises: `ConflictError`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Item with SKU 'B-M8' already exists"`.
4. nothing written: nothing written.

### ITS-C-08 — end to end: an unknown tag id gets the 404 and nothing is saved
- **Rules:** `create_item` R2 [BUG-944], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-944
- **Fails today on:** Then 1 (no error is raised: the unknown id is skipped and the item is created)

**Given**
1. T1, but `usage_count 3`.

**When**
- `svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[T1.id, MISSING]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Item tag 999999999 not found"`.
4. count: `items` rows with `name == "Bolt M8"`: exactly 0.
5. re-read: `stored_count(T1) == 3`.

### ITS-C-09 — end to end: a deleted tag gets the 400 and nothing is saved
- **Rules:** `create_item` R2 [BUG-943], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-943
- **Fails today on:** Then 1 (no error is raised: the deleted tag is linked)

**Given**
1. TD, but `usage_count 5`.

**When**
- `svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs", tag_ids=[TD.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == f"Item tag {TD.id} is not active"`.
4. count: `items` rows with `name == "Bolt M8"`: exactly 0.
5. re-read: `stored_count(TD) == 5`.

### ITS-C-10 — end to end: a SKU in use gets the 409 and nothing is saved
- **Rules:** `create_item` R2 [BUG-946], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-946
- **Fails today on:** Then 1 (no error is raised: SKUs are not checked)

**Given**
1. I1, but `sku "B-M8"`.

**When**
- `svc.create_item(db, item_in=ItemCreate(name="Hex Screw", unit="pcs", sku="B-M8"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ConflictError`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Item with SKU 'B-M8' already exists"`.
4. count: `items` rows with `sku == "B-M8"`: exactly 1.
5. unchanged: unchanged(I1).

### ITS-C-11 — a ValueError with another text is not translated and the session is rolled back
- **Rules:** `create_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I2.
2. X = item, `name "Extra"`, `name_normalized "extra"` (after the commit point).

**When**
- `svc.create_item(db, item_in=ItemCreate(name="Bolt M8", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`, with the manager patch `create_item` raising `ValueError("something else")`, inside `raises: ValueError`.

**Then**
1. raises: `type(exc.value) is ValueError`.
2. raises: `exc.value.args == ("something else",)`.
3. count: `items` rows with `name == "Extra"`: exactly 0.
4. unchanged: unchanged(I2).

### ITS-C-12 — pass-through BUG-936: a padded name is committed trimmed
- **Rules:** `create_item` R1 [BUG-936]
- **Kind:** bug
- **Expect:** xfail BUG-936
- **Fails today on:** Then 2 (the name is stored with its outer spaces)

**Given**
1. No items exist.

**When**
- `result = svc.create_item(db, item_in=ItemCreate(name="  Steel  Rod 22 m ", unit="pcs"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the row with `id == result.id` has `name == "Steel  Rod 22 m"`.

## `ItemService.get_item`

### ITS-G-01 — a live item of the workspace is returned
- **Rules:** `get_item` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I9.
2. I1.

**When**
- `result = svc.get_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Item)`.
2. returns: `result.id == I1.id`, `result.name == "Bolt M8"`.

### ITS-G-02 — another workspace's item gets NotFoundError 404
- **Rules:** `get_item` R1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I1.
2. I9.

**When**
- `svc.get_item(db, item_id=I9.id, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
4. unchanged: unchanged(I9).

### ITS-G-03 — id 0 gets the 404
- **Rules:** `get_item` R1, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.

**When**
- `svc.get_item(db, item_id=0, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Item with ID 0 not found"`.

### ITS-G-04 — a deleted item is hidden by default
- **Rules:** `get_item` R2 [BUG-937], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-937
- **Fails today on:** Then 1 (no error is raised: the deleted item is returned)

**Given**
1. IX.

**When**
- `svc.get_item(db, item_id=IX.id, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {IX.id} not found"`.
4. unchanged: unchanged(IX).

### ITS-G-05 — include_deleted=True returns a deleted item
- **Rules:** `get_item` R3 [BUG-937]
- **Kind:** bug
- **Expect:** xfail BUG-937
- **Fails today on:** Then 1 (the call raises TypeError: the parameter does not exist)

**Given**
1. IX.

**When**
- `result = svc.get_item(db, item_id=IX.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result.id == IX.id`.
2. returns: `result.is_active is False`.

### ITS-G-06 — include_deleted=True does not reach another workspace
- **Rules:** `get_item` R3 [BUG-937], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-937
- **Fails today on:** Then 1 (the call raises TypeError, not NotFoundError)

**Given**
1. I9, but `is_active False`.

**When**
- `svc.get_item(db, item_id=I9.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.

### ITS-G-07 — the read neither commits nor rolls back
- **Rules:** `get_item` R4; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1.
2. I2.
3. P = item, `name "Pending"`, `name_normalized "pending"` (after the commit point).
4. `I2.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_item(db, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == I1.id`.
2. session: `I2 in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. count: `items` rows with `name == "Pending"`: exactly 1.
5. committed: `items` rows with `name == "Pending"`: exactly 0.
6. committed: re-read I2: `name == "Washer Ten"`.

## `ItemService.get_items_page`

### ITS-P-01 — the page holds the workspace's live items with total and paging values
- **Rules:** `get_items_page` R1, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. I2.
3. IX.
4. I9.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result.items) == [I1.id, I2.id]`.
2. returns: `result.total == 2`.
3. returns: `result.skip == 0`, `result.limit == 100`.
4. returns: `result.has_more is False`.

### ITS-P-02 — search reaches the list and the count; limit reaches the list
- **Rules:** `get_items_page` R1, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. I2.
3. I3 = item, `name "Bolt M10"`, `name_normalized "bolt m10"`.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id, search="bolt", skip=0, limit=1)`.

**Then**
1. returns: `len(result.items) == 1`.
2. returns: `result.items[0].id in (I1.id, I3.id)`.
3. returns: `result.total == 2`.
4. returns: `result.has_more is True`.

### ITS-P-03 — unit reaches the list and the count
- **Rules:** `get_items_page` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. I2, but `unit "kg"`.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id, unit="kg")`.

**Then**
1. returns: `ids(result.items) == [I2.id]`.
2. returns: `result.total == 1`.

### ITS-P-04 — tag_ids reach the list and the count
- **Rules:** `get_items_page` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. I2.
3. T1.
4. link of I2 to T1.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id, tag_ids=[T1.id])`.

**Then**
1. returns: `ids(result.items) == [I2.id]`.
2. returns: `result.total == 1`.

### ITS-P-05 — the last page exactly reaching the total has no more
- **Rules:** `get_items_page` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. I2.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `len(result.items) == 1`.
2. returns: `result.total == 2`.
3. returns: `result.skip == 1`, `result.limit == 1`.
4. returns: `result.has_more is False`.

### ITS-P-06 — skip past the end gives an empty page with no more
- **Rules:** `get_items_page` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. I2.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id, skip=5, limit=1000)`.

**Then**
1. returns: `result.items == []`.
2. returns: `result.total == 2`.
3. returns: `result.skip == 5`, `result.limit == 1000`.
4. returns: `result.has_more is False`.

### ITS-P-07 — limit=0 gives an empty page that has more
- **Rules:** `get_items_page` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. I2.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result.items == []`.
2. returns: `result.total == 2`.
3. returns: `result.has_more is True`.

### ITS-P-08 — limit=0 on an empty workspace has no more
- **Rules:** `get_items_page` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no items.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result.items == []`.
2. returns: `result.total == 0`.
3. returns: `result.has_more is False`.

### ITS-P-09 — each tag is a dict with exactly six keys; an item without tags has []
- **Rules:** `get_items_page` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. I2.
3. T1, but `color "#3366FF"`, `icon "wrench"`.
4. link of I1 to T1.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r for r in result.items if r.id == I1.id][0].tags == [{"id": T1.id, "name": "Spare Part", "tag_code": "spare_part", "color": "#3366FF", "icon": "wrench", "is_system_tag": False}]`.
2. returns: `[r for r in result.items if r.id == I2.id][0].tags == []`.

### ITS-P-10 — each listed item carries its row's values
- **Rules:** `get_items_page` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1, but `description "Zinc plated"`, `sku "B-M8"`, `unit "box"`, `updated_by U2.id`, `updated_at datetime(2026, 2, 3, 4, 5, 6)`.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.items) == 1`.
2. returns: `result.items[0].id == I1.id`, `result.items[0].workspace_id == W1.id`, `result.items[0].name == "Bolt M8"`.
3. returns: `result.items[0].description == "Zinc plated"`, `result.items[0].sku == "B-M8"`, `result.items[0].unit == "box"`.
4. returns: `result.items[0].is_active is True`, `result.items[0].created_by == U1.id`.
5. returns: `result.items[0].updated_by == U2.id`.
6. returns: `result.items[0].created_at is not None`.
7. returns: `result.items[0].updated_at.replace(tzinfo=None) == datetime(2026, 2, 3, 4, 5, 6)` (the stored stamp, compared as wall time).
8. returns: `result.items[0].item_type == "physical"`.

### ITS-P-11 — a service item is listed with item_type "service"
- **Rules:** `get_items_page` R3 [BUG-1573]
- **Kind:** bug
- **Expect:** xfail BUG-1573
- **Fails today on:** Then 2 (`item_type` is left out and reads "physical")

**Given**
1. R = item, `name "Repair"`, `name_normalized "repair"`, `item_type "service"`.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r.id for r in result.items] == [R.id]`.
2. returns: `result.items[0].item_type == "service"`.

### ITS-P-12 — pass-through BUG-012: a search with a non-ASCII digit does not raise
- **Rules:** `get_items_page` R1 [BUG-012]
- **Kind:** bug
- **Expect:** xfail BUG-012
- **Fails today on:** Then 1 (the call raises ValueError on "²")

**Given**
1. A = item, `name "Sheet 2 m²"`, `name_normalized "sheet 2m"`.
2. I2.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id, search="²")`.

**Then**
1. returns: `ids(result.items) == [A.id]`.
2. returns: `result.total == 1`.

### ITS-P-13 — pass-through BUG-013: "_" in a search matches literally
- **Rules:** `get_items_page` R1 [BUG-013]
- **Kind:** bug
- **Expect:** xfail BUG-013
- **Fails today on:** Then 1 (`_` is a wildcard: "Plain Bar" is returned too)

**Given**
1. A = item, `name "snake_case bolt"`, `name_normalized "snake_case bolt"`.
2. B = item, `name "Plain Bar"`, `name_normalized "plain bar"`.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id, search="_")`.

**Then**
1. returns: `ids(result.items) == [A.id]`.
2. returns: `result.total == 1`.

### ITS-P-14 — pass-through BUG-014: a deleted tag does not filter
- **Rules:** `get_items_page` R1 [BUG-014]
- **Kind:** bug
- **Expect:** xfail BUG-014
- **Fails today on:** Then 1 (the item linked to the deleted tag is returned)

**Given**
1. TD.
2. A = I1.
3. link of A to TD.
4. I2.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id, tag_ids=[TD.id])`.

**Then**
1. returns: `result.items == []`.
2. returns: `result.total == 0`.

### ITS-P-15 — pass-through BUG-015: a deleted tag's name does not match a search
- **Rules:** `get_items_page` R1 [BUG-015]
- **Kind:** bug
- **Expect:** xfail BUG-015
- **Fails today on:** Then 1 (the item is found through the deleted tag's name)

**Given**
1. TD.
2. A = I1.
3. link of A to TD.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id, search="obsol")`.

**Then**
1. returns: `result.items == []`.
2. returns: `result.total == 0`.

### ITS-P-16 — pass-through BUG-033: items come by name case-insensitively
- **Rules:** `get_items_page` R1 [BUG-033]
- **Kind:** bug
- **Expect:** xfail BUG-033
- **Fails today on:** Then 2 (the page comes in id order)

**Given**
1. item, `name "Zulu"`, `name_normalized "zulu"`.
2. item, `name "Mike"`, `name_normalized "mike"`.
3. item, `name "alpha"`, `name_normalized "alpha"`.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result.items) == 3`.
2. returns: `[r.name for r in result.items] == ["alpha", "Mike", "Zulu"]`.

### ITS-P-17 — pass-through BUG-933: an item's tags come by name case-insensitively, then id
- **Rules:** `get_items_page` R2 [BUG-933]
- **Kind:** bug
- **Expect:** xfail BUG-933 (non-strict)
- **Fails today on:** Then 2 (the database collation decides; "alpha" sorts before "Alpha")

**Given**
1. I1.
2. K1 = tag, `name "bravo"`, `tag_code "bravo"`.
3. K2 = tag, `name "Alpha"`, `tag_code "alpha_upper"`.
4. K3 = tag, `name "alpha"`, `tag_code "alpha_lower"`.
5. link of I1 to K1.
6. link of I1 to K2.
7. link of I1 to K3.

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(t["id"] for t in result.items[0].tags) == [K1.id, K2.id, K3.id]`.
2. returns: `[t["id"] for t in result.items[0].tags] == [K2.id, K3.id, K1.id]`.

### ITS-P-18 — the page read neither commits nor rolls back
- **Rules:** `get_items_page` R5; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1.
2. I9.
3. P = item, `name "Pending"`, `name_normalized "pending"` (after the commit point).
4. `I9.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_items_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result.items) == sorted([I1.id, P.id])`.
2. session: `I9 in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. committed: `items` rows with `name == "Pending"`: exactly 0.
5. committed: re-read I9: `name == "Far Spring"`.

## `ItemService.get_distinct_units`

### ITS-N-01 — the workspace's units come back as the manager gives them
- **Rules:** `get_distinct_units` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. I2, but `unit "kg"`.
3. I9, but `unit "ltr"`.

**When**
- `result = svc.get_distinct_units(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(result) == ["kg", "pcs"]`.

### ITS-N-02 — pass-through BUG-017: one unit in three spellings is listed once, lower case
- **Rules:** `get_distinct_units` R1 [BUG-017]
- **Kind:** bug
- **Expect:** xfail BUG-017
- **Fails today on:** Then 1 (three entries come back)

**Given**
1. I1, but `unit "kg"`.
2. I2, but `unit "Kg"`.
3. item, `name "Pin"`, `name_normalized "pin"`, `unit "KG"`.

**When**
- `result = svc.get_distinct_units(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == ["kg"]`.

### ITS-N-03 — the unit read neither commits nor rolls back
- **Rules:** `get_distinct_units` R1; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. I1.
2. I9.
3. P = item, `name "Pending"`, `name_normalized "pending"`, `unit "box"` (after the commit point).
4. `I9.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_distinct_units(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(result) == ["box", "pcs"]`.
2. session: `I9 in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. committed: `items` rows with `name == "Pending"`: exactly 0.
5. committed: re-read I9: `name == "Far Spring"`.

## `ItemService.get_similar_items`

### ITS-S-01 — the query is echoed untrimmed, normalized, and the manager's match comes back
- **Rules:** `get_similar_items` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = item, `name "Bolt"`, `name_normalized "bolt"`.

**When**
- `result = svc.get_similar_items(db, workspace_id=W1.id, name="  BOLT ")`.

**Then**
1. returns: `result.query == "  BOLT "`.
2. returns: `result.normalized_query == "bolt"`.
3. returns: `len(result.matches) == 1`.
4. returns: `result.matches[0].id == B.id`, `result.matches[0].name == "Bolt"`.
5. returns: `result.matches[0].match_type == "exact_normalized"`, `result.matches[0].similarity_score == 1.0`.

### ITS-S-02 — a name of punctuation normalizes to "" and finds nothing
- **Rules:** `get_similar_items` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B = item, `name "Bolt"`, `name_normalized "bolt"`.

**When**
- `result = svc.get_similar_items(db, workspace_id=W1.id, name="!!")`.

**Then**
1. returns: `result.query == "!!"`.
2. returns: `result.normalized_query == ""`.
3. returns: `result.matches == []`.

### ITS-S-03 — exclude_item_id reaches the manager
- **Rules:** `get_similar_items` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. B1 = item, `name "Bolt"`, `name_normalized "bolt"`.
2. B2 = item, `name "Bolt "`, `name_normalized "bolt"`.

**When**
- `result = svc.get_similar_items(db, workspace_id=W1.id, name="bolt", exclude_item_id=B1.id)`.

**Then**
1. returns: `[m.id for m in result.matches] == [B2.id]`.

### ITS-S-04 — limit reaches the manager
- **Rules:** `get_similar_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. item, `name "Bolt"`, `name_normalized "bolt"`.
2. item, `name "Bolt "`, `name_normalized "bolt"`.
3. item, `name "BOLT"`, `name_normalized "bolt"`.

**When**
- `result = svc.get_similar_items(db, workspace_id=W1.id, name="bolt", limit=2)`.

**Then**
1. returns: `len(result.matches) == 2`.

### ITS-S-05 — pass-through BUG-034: a score of exactly 0.35 is included
- **Rules:** `get_similar_items` R1 [BUG-034]
- **Kind:** bug
- **Expect:** xfail BUG-034
- **Fails today on:** Then 1 (the float score 0.3499… is compared with 0.35 and the item is dropped)

**Given**
1. Q = item, `name "Qa"`, `name_normalized "abcdefghijklmnopqr"`.

**When**
- `result = svc.get_similar_items(db, workspace_id=W1.id, name="abcdefg")`.

**Then**
1. returns: `len(result.matches) == 1`.
2. returns: `result.matches[0].id == Q.id`, `result.matches[0].similarity_score == 0.35`.

### ITS-S-06 — pass-through BUG-018: equal scores come by name case-insensitively, then id
- **Rules:** `get_similar_items` R1 [BUG-018]
- **Kind:** bug
- **Expect:** xfail BUG-018 (non-strict)
- **Fails today on:** Then 2 (ties come back in storage order)

**Given**
1. item, `name "delta"`, `name_normalized "steel rod 22m"`.
2. item, `name "Bravo"`, `name_normalized "steel rod 22m"`.
3. item, `name "alpha"`, `name_normalized "steel rod 22m"`.

**When**
- `result = svc.get_similar_items(db, workspace_id=W1.id, name="Steel Rod 22m")`.

**Then**
1. returns: `len(result.matches) == 3`.
2. returns: `[m.name for m in result.matches] == ["alpha", "Bravo", "delta"]`.

### ITS-S-07 — the similar-name read neither commits nor rolls back
- **Rules:** `get_similar_items` R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = item, `name "Bolt"`, `name_normalized "bolt"`.
2. I9.
3. P = item, `name "Pending"`, `name_normalized "pending"` (after the commit point).
4. `I9.name = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.get_similar_items(db, workspace_id=W1.id, name="bolt")`.

**Then**
1. returns: `[m.id for m in result.matches] == [B.id]`.
2. session: `I9 in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. committed: `items` rows with `name == "Pending"`: exactly 0.
5. committed: re-read I9: `name == "Far Spring"`.

### ITS-S-08 — without limit, 6 matching items give exactly 5 of them
- **Rules:** `get_similar_items` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. B1 = item, `name "Bolt A"`, `name_normalized "bolt"`.
2. B2 = item, `name "Bolt B"`, `name_normalized "bolt"`.
3. B3 = item, `name "Bolt C"`, `name_normalized "bolt"`.
4. B4 = item, `name "Bolt D"`, `name_normalized "bolt"`.
5. B5 = item, `name "Bolt E"`, `name_normalized "bolt"`.
6. B6 = item, `name "Bolt F"`, `name_normalized "bolt"`.

**When**
- `result = svc.get_similar_items(db, workspace_id=W1.id, name="bolt")`.

**Then**
1. returns: `len(result.matches) == 5`.
2. returns: `len({m.id for m in result.matches}) == 5`.
3. returns: `{m.id for m in result.matches} <= {B1.id, B2.id, B3.id, B4.id, B5.id, B6.id}`.

## `ItemService.update_item`

### ITS-U-01 — a rename is committed and returned re-read
- **Rules:** `update_item` R1, Returns; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.

**When**
- `result = svc.update_item(db, item_id=I1.id, item_in=ItemUpdate(name="Lock Nut"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. loaded: `updated_at`, `updated_by`, `name`.
2. returns: `result.id == I1.id`.
3. returns: `result.name == "Lock Nut"`, `result.updated_by == U2.id`, `result.updated_at is not None`.
4. committed: re-read I1: `name == "Lock Nut"`, `name_normalized == "lock nut"`, `updated_by == U2.id`, `updated_at is not None`.
5. committed: re-read I1: `created_by == U1.id`, `is_active is True`.

### ITS-U-02 — an unknown user: the IntegrityError passes unchanged, the session is rolled back
- **Rules:** `update_item` R3; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. I1.
2. X = item, `name "Extra"`, `name_normalized "extra"` (after the commit point).

**When**
- `svc.update_item(db, item_id=I1.id, item_in=ItemUpdate(name="Lock Nut"), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. count: `items` rows with `name == "Extra"`: exactly 0.
4. unchanged: unchanged(I1).
5. nothing written: nothing written.
6. session: usable.

### ITS-U-03 — the manager's not-found ValueError becomes NotFoundError 404 with the service's text
- **Rules:** `update_item` R2 [BUG-940]
- **Kind:** bug
- **Expect:** xfail BUG-940
- **Fails today on:** Then 1 (the call raises ValueError: the service translates nothing)

**Given**
1. I1.
2. X = item, `name "Extra"`, `name_normalized "extra"` (after the commit point).

**When**
- `svc.update_item(db, item_id=I1.id, item_in=ItemUpdate(name="Lock Nut"), workspace_id=W1.id, user_id=U2.id)`, with the manager patch `update_item` raising `ValueError(f"Item {I1.id} not found")`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {I1.id} not found"`.
4. count: `items` rows with `name == "Extra"`: exactly 0.
5. unchanged: unchanged(I1).

### ITS-U-04 — end to end: a missing item gets the 404
- **Rules:** `update_item` R2 [BUG-940]
- **Kind:** bug
- **Expect:** xfail BUG-940
- **Fails today on:** Then 1 (the call raises ValueError "Item 999999999 not found")

**Given**
1. I1.

**When**
- `svc.update_item(db, item_id=MISSING, item_in=ItemUpdate(name="Lock Nut"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Item with ID 999999999 not found"`.
4. unchanged: unchanged(I1).

### ITS-U-05 — end to end: another workspace's item gets the same 404
- **Rules:** `update_item` R2 [BUG-941]
- **Kind:** bug
- **Expect:** xfail BUG-941
- **Fails today on:** Then 1 (the call raises ValueError "… does not belong to workspace …")

**Given**
1. I9.

**When**
- `svc.update_item(db, item_id=I9.id, item_in=ItemUpdate(name="Lock Nut"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
4. unchanged: unchanged(I9).

### ITS-U-06 — end to end: a deleted item gets the 404 and is not changed
- **Rules:** `update_item` R2 [BUG-938]
- **Kind:** bug
- **Expect:** xfail BUG-938
- **Fails today on:** Then 1 (no error is raised: the deleted item is renamed)

**Given**
1. IX.

**When**
- `svc.update_item(db, item_id=IX.id, item_in=ItemUpdate(name="Lock Nut"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {IX.id} not found"`.
4. committed: re-read IX: `name == "Old Rivet"`, `updated_by is None`.

### ITS-U-07 — a ValueError with another text is not translated
- **Rules:** `update_item` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.

**When**
- `svc.update_item(db, item_id=I1.id, item_in=ItemUpdate(name="Lock Nut"), workspace_id=W1.id, user_id=U2.id)`, with the manager patch `update_item` raising `ValueError("something else")`, inside `raises: ValueError`.

**Then**
1. raises: `type(exc.value) is ValueError`.
2. raises: `exc.value.args == ("something else",)`.
3. unchanged: unchanged(I1).

### ITS-U-08 — pass-through BUG-939: an empty update does not stamp the item
- **Rules:** `update_item` R1 [BUG-939]
- **Kind:** bug
- **Expect:** xfail BUG-939
- **Fails today on:** Then 2 (`updated_by` becomes U2)

**Given**
1. I1.

**When**
- `result = svc.update_item(db, item_id=I1.id, item_in=ItemUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == I1.id`.
2. committed: re-read I1: `updated_by is None`.

### ITS-U-09 — pass-through BUG-934: a tag that stays keeps its link
- **Rules:** `update_item` R1 [BUG-934]
- **Kind:** bug
- **Expect:** xfail BUG-934
- **Fails today on:** Then 3 (every link is deleted and T1 is linked again with a new id)

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. T2 = tag, `name "Galvanized"`, `tag_code "galvanized"`, `usage_count 6`.
4. L1 = link of I1 to T1.
5. link of I1 to T2.
6. `l1_id = L1.id`

**When**
- `result = svc.update_item(db, item_id=I1.id, item_in=ItemUpdate(tag_ids=[T1.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == I1.id`.
2. committed: `tag_ids_of(I1) == [T1.id]`.
3. committed: the `item_tag_assignments` row with `item_id == I1.id` and `tag_id == T1.id` has `id == l1_id`, `assigned_by == U1.id`.

### ITS-U-10 — pass-through BUG-935: a tag save keeps the link to a deleted tag
- **Rules:** `update_item` R1 [BUG-935]
- **Kind:** bug
- **Expect:** xfail BUG-935
- **Fails today on:** Then 2 (the link to the deleted tag is erased)

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. TD, but `usage_count 7`.
4. link of I1 to T1.
5. link of I1 to TD.

**When**
- `result = svc.update_item(db, item_id=I1.id, item_in=ItemUpdate(tag_ids=[T1.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == I1.id`.
2. committed: `tag_ids_of(I1) == sorted([T1.id, TD.id])`.

### ITS-U-11 — pass-through BUG-942: an explicit null clears the description
- **Rules:** `update_item` R1 [BUG-942]
- **Kind:** bug
- **Expect:** xfail BUG-942
- **Fails today on:** Then 2 (the null is dropped and the old description stays)

**Given**
1. I1, but `description "Zinc plated"`.

**When**
- `result = svc.update_item(db, item_id=I1.id, item_in=ItemUpdate(description=None), workspace_id=W1.id, user_id=U2.id)`. `description` is sent explicitly as `None`.

**Then**
1. returns: `result.id == I1.id`.
2. committed: re-read I1: `description is None`.

### ITS-U-12 — pass-through BUG-947: is_active sent with an edit is ignored
- **Rules:** `update_item` R1 [BUG-947]
- **Kind:** bug
- **Expect:** xfail BUG-947
- **Fails today on:** Then 3 (`is_active` false is written)

**Given**
1. I1.

**When**
- `result = svc.update_item(db, item_id=I1.id, item_in=ItemUpdate(name="Lock Nut", is_active=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == I1.id`.
2. committed: re-read I1: `name == "Lock Nut"`.
3. committed: re-read I1: `is_active is True`.

## `ItemService.delete_item`

### ITS-D-01 — a delete is committed and None is returned
- **Rules:** `delete_item` R5, Returns; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. link of I1 to T1.

**When**
- `result = svc.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. committed: re-read I1: `is_active is False`, `updated_by == U2.id`, `updated_at is not None`.
3. committed: re-read I1: `name == "Bolt M8"`.
4. committed: `stored_count(T1) == 3`.
5. committed: `tag_ids_of(I1) == [T1.id]`.

### ITS-D-02 — a missing id: NotFoundError 404, the manager's delete is not called, the session is rolled back
- **Rules:** `delete_item` R1, Errors row 1; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. I1.
2. X = item, `name "Extra"`, `name_normalized "extra"` (after the commit point).

**When**
- `svc.delete_item(db, item_id=MISSING, workspace_id=W1.id, user_id=U2.id)`, inside `with patch.object(svc.item_manager, "delete_item", wraps=svc.item_manager.delete_item) as spy:`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Item with ID 999999999 not found"`.
4. mock called: `spy.call_count == 0`.
5. count: `items` rows with `name == "Extra"`: exactly 0.
6. unchanged: unchanged(I1).
7. session: usable.

### ITS-D-03 — another workspace's item gets the 404
- **Rules:** `delete_item` R1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. I1.
2. I9.

**When**
- `svc.delete_item(db, item_id=I9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
4. unchanged: unchanged(I9).

### ITS-D-04 — end to end: a deleted item gets the 404
- **Rules:** `delete_item` R2 [BUG-937], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-937
- **Fails today on:** Then 1 (the call raises ValueError "Item <id> is already deleted")

**Given**
1. IX.

**When**
- `svc.delete_item(db, item_id=IX.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {IX.id} not found"`.
4. unchanged: unchanged(IX).

### ITS-D-05 — the manager's already-deleted ValueError becomes ValidationError 400
- **Rules:** `delete_item` R3 [BUG-940], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-940
- **Fails today on:** Then 1 (the call raises ValueError: the service translates nothing)

**Given**
1. I1.

**When**
- `svc.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`, with the manager patch `delete_item` raising `ValueError(f"Item {I1.id} is already deleted")`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == f"Item {I1.id} is already deleted"`.
4. unchanged: unchanged(I1).

### ITS-D-06 — the manager's not-found ValueError becomes the 404
- **Rules:** `delete_item` R3 [BUG-940], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-940
- **Fails today on:** Then 1 (the call raises ValueError: the service translates nothing)

**Given**
1. I1.

**When**
- `svc.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`, with the manager patch `delete_item` raising `ValueError(f"Item {I1.id} not found")`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Item with ID {I1.id} not found"`.
4. unchanged: unchanged(I1).

### ITS-D-07 — the manager's in-use ValueError becomes the 400 with the blockers as given, after a rollback
- **Rules:** `delete_item` R4 [BUG-948], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (the ValueError escapes unchanged)

**Given**
1. I1.
2. X = item, `name "Extra"`, `name_normalized "extra"` (after the commit point).

**When**
- `svc.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`, with the manager patch `delete_item` raising `ValueError("Item has stock or open orders", [{"type": "work_order", "id": 3}, {"type": "factory_stock", "id": 1}, {"type": "other_workspace"}])`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Item has stock or open orders"`.
4. raises: `exc.value.errors == [{"type": "work_order", "id": 3}, {"type": "factory_stock", "id": 1}, {"type": "other_workspace"}]`.
5. count: `items` rows with `name == "Extra"`: exactly 0.
6. unchanged: unchanged(I1).

### ITS-D-08 — end to end: stock in a factory blocks the delete with a 400 that lists it
- **Rules:** `delete_item` R4 [BUG-948], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-948
- **Fails today on:** Then 1 (no error is raised: stock is not looked at and the item is deleted)

**Given**
1. I1.
2. F1.
3. SK = stock of I1, `qty 400`.

**When**
- `svc.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Item has stock or open orders"`.
4. raises: `exc.value.errors == [{"type": "factory_stock", "id": SK.id}]`.
5. committed: re-read I1: `is_active is True`, `updated_by is None`.

### ITS-D-09 — a ValueError with another text is not translated and the session is rolled back
- **Rules:** `delete_item` R6; TC3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. I1.
2. X = item, `name "Extra"`, `name_normalized "extra"` (after the commit point).

**When**
- `svc.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`, with the manager patch `delete_item` raising `ValueError("something else", [])`, inside `raises: ValueError`.

**Then**
1. raises: `type(exc.value) is ValueError`.
2. raises: `exc.value.args == ("something else", [])`.
3. count: `items` rows with `name == "Extra"`: exactly 0 (counted right after the call, before any test-level rollback).
4. unchanged: unchanged(I1).
5. session: usable.

### ITS-D-10 — an unknown user on an item not in use: the IntegrityError passes unchanged, nothing saved
- **Rules:** `delete_item` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. I1.
2. T1, but `usage_count 4`.
3. link of I1 to T1.

**When**
- `svc.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. committed: re-read I1: `is_active is True`, `updated_by is None`.
4. committed: `stored_count(T1) == 4`.
5. session: usable.

### ITS-D-11 — pass-through BUG-945: a deleted tag on the item also counts one item less
- **Rules:** `delete_item` R5 [BUG-945]
- **Kind:** bug
- **Expect:** xfail BUG-945
- **Fails today on:** Then 2 (only active tags are lowered; TD stays at 9)

**Given**
1. I1.
2. TD, but `usage_count 9`.
3. link of I1 to TD.

**When**
- `result = svc.delete_item(db, item_id=I1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. committed: `stored_count(TD) == 8`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| RFC 7807 body and HTTP status of `NotFoundError` / `ValidationError` / `ConflictError` (D1; BUG-940, BUG-941 "never 500") | `/items/` endpoints with `api_exception_handler` (integration; `tests/unit/core/exceptions.spec.md`) | 404 / 400 / 409 bodies; the 400 of BUG-948 carries `errors`. |
| BUG-937 — the `include_deleted` query parameter | `GET /items/{id}/` (integration) | Accepted and passed on. |
| BUG-011 — `exclude_item_id` not offered by the endpoint | `GET /items/similar/` | The service passes it (ITS-S-03); the endpoint never sends it. |
| BUG-016 — no lower bound on `limit` | `GET /items/` (HR-7) | `limit=0` → 422; here the service's answer for `limit=0` is ITS-P-07. |
| BUG-931 — lost concurrent counter changes | item tag DAO (`tests/unit/dao/item_tag.cases.md`) | A race; one session cannot show it. |
| BUG-932 — tags of one item unordered | assignment DAO (`item_tag_assignment.cases.md`) | `get_tags_for_item` is not called by any specified service method. |
| BUG-018, BUG-933 strict `ORDER BY` recorders | item DAO ITEM-S-28, assignment DAO ITA-TFS-19 | The queries are the DAOs'; S-06 and P-17 here are pass-throughs only. |
| BUG-936, BUG-942 schema errors answer 422 (BUG-461) | `POST`, `PUT /items/` | Integration-only; the schema cards are the manager's. |
| Manager / DAO rules beyond one pass-through per bug (BUG-948 every blocker type and cross-workspace shape; R10a) | `item_manager.cases.md`, `item.cases.md` | Not re-tested here. |
| BUG-949 | frontend | No backend case. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `get_similar_items` Returns; Facts | The attribute names of `SimilarItemMatch` are not given. | Not blocking: S-01, S-03, S-05, S-06 assume they mirror the manager's dict keys (`id`, `name`, `similarity_score`, `match_type`; item manager spec `find_similar_items` R2). |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_item` | R1 | ITS-C-01 |
| `create_item` | R1 [BUG-936] | ITS-C-12 |
| `create_item` | R1 [BUG-931] | Deferred (item tag DAO) |
| `create_item` | R2 [BUG-944] | ITS-C-05, ITS-C-08 |
| `create_item` | R2 [BUG-943] | ITS-C-06, ITS-C-09 |
| `create_item` | R2 [BUG-946] | ITS-C-07, ITS-C-10 |
| `create_item` | R3 | ITS-C-02, ITS-C-03, ITS-C-04, ITS-C-11 |
| `create_item` | Errors row 1 | ITS-C-05, ITS-C-08 |
| `create_item` | Errors row 2 | ITS-C-06, ITS-C-09 |
| `create_item` | Errors row 3 | ITS-C-07, ITS-C-10 |
| `create_item` | Errors row 4 | ITS-C-02 |
| `create_item` | Returns | ITS-C-01 |
| `get_item` | R1 | ITS-G-01, ITS-G-02, ITS-G-03 |
| `get_item` | R2 [BUG-937] | ITS-G-04 |
| `get_item` | R3 [BUG-937] | ITS-G-05, ITS-G-06 |
| `get_item` | R4 | ITS-G-07 |
| `get_item` | Errors row 1 | ITS-G-02, ITS-G-03, ITS-G-04, ITS-G-06 |
| `get_items_page` | R1 | ITS-P-01, ITS-P-02, ITS-P-03, ITS-P-04 |
| `get_items_page` | R1 [BUG-012] | ITS-P-12 |
| `get_items_page` | R1 [BUG-013] | ITS-P-13 |
| `get_items_page` | R1 [BUG-014] | ITS-P-14 |
| `get_items_page` | R1 [BUG-015] | ITS-P-15 |
| `get_items_page` | R1 [BUG-033] | ITS-P-16 |
| `get_items_page` | R1 [BUG-016] | Deferred (`GET /items/`) |
| `get_items_page` | R2 | ITS-P-09 |
| `get_items_page` | R2 [BUG-933] | ITS-P-17 |
| `get_items_page` | R2 [BUG-932] | Deferred (not reached) |
| `get_items_page` | R3 | ITS-P-10 |
| `get_items_page` | R3 [BUG-1573] | ITS-P-11 |
| `get_items_page` | R4 | ITS-P-01, ITS-P-02, ITS-P-05, ITS-P-06, ITS-P-07, ITS-P-08 |
| `get_items_page` | R5 | ITS-P-18 |
| `get_distinct_units` | R1 | ITS-N-01, ITS-N-03 |
| `get_distinct_units` | R1 [BUG-017] | ITS-N-02 |
| `get_similar_items` | R1 | ITS-S-01, ITS-S-03, ITS-S-04 |
| `get_similar_items` | R1 [BUG-034] | ITS-S-05 |
| `get_similar_items` | R1 [BUG-018] | ITS-S-06 |
| `get_similar_items` | R1 [BUG-011] | ITS-S-03 (service part); Deferred (endpoint) |
| `get_similar_items` | R1a | ITS-S-08 |
| `get_similar_items` | R2 | ITS-S-01, ITS-S-02 |
| `get_similar_items` | R3 | ITS-S-07 |
| `update_item` | R1 | ITS-U-01 |
| `update_item` | R1 [BUG-934] | ITS-U-09 |
| `update_item` | R1 [BUG-935] | ITS-U-10 |
| `update_item` | R1 [BUG-939] | ITS-U-08 |
| `update_item` | R1 [BUG-942] | ITS-U-11 |
| `update_item` | R1 [BUG-947] | ITS-U-12 |
| `update_item` | R2 [BUG-940] | ITS-U-03, ITS-U-04 |
| `update_item` | R2 [BUG-941] | ITS-U-05 |
| `update_item` | R2 [BUG-938] | ITS-U-06 |
| `update_item` | R2 [BUG-944, BUG-943, BUG-946] | ITS-C-05, ITS-C-06, ITS-C-07 (same texts and statuses; each translation once per status) |
| `update_item` | R3 | ITS-U-02, ITS-U-07; ITS-C-03, ITS-C-04 (TC4, TC5 once per service) |
| `update_item` | Returns | ITS-U-01 |
| `delete_item` | R1 | ITS-D-02, ITS-D-03 |
| `delete_item` | R2 [BUG-937] | ITS-D-04 |
| `delete_item` | R3 [BUG-940] | ITS-D-05, ITS-D-06 |
| `delete_item` | R4 [BUG-948] | ITS-D-07, ITS-D-08 |
| `delete_item` | R5 | ITS-D-01 |
| `delete_item` | R5 [BUG-945] | ITS-D-11 |
| `delete_item` | R6 | ITS-D-09, ITS-D-10; ITS-C-03 (TC4 once per service) |
| `delete_item` | Errors row 1 | ITS-D-02, ITS-D-03, ITS-D-04, ITS-D-06 |
| `delete_item` | Errors row 2 | ITS-D-05 |
| `delete_item` | Errors row 3 | ITS-D-07, ITS-D-08 |
| `delete_item` | Returns | ITS-D-01 |
| Transaction contract | TC1 | ITS-C-01, ITS-U-01, ITS-D-01 |
| Transaction contract | TC2 | ITS-C-01 (also ITS-U-01) |
| Transaction contract | TC3 | ITS-C-02, ITS-C-11, ITS-U-02, ITS-D-02, ITS-D-09 |
| Transaction contract | TC4 | ITS-C-03 |
| Transaction contract | TC5 | ITS-C-04 |
| Transaction contract | TC6 | ITS-G-07, ITS-P-18, ITS-N-03, ITS-S-07 |
