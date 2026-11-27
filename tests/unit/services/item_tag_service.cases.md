# Test cases — `app/services/item_tag_service.py`

> **Spec:** `tests/unit/services/item_tag_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — additive, from `item_tag_service.verify.md` (R-IT-1 … R-IT-4). New: ITS-D-07 (a 403 on delete leaves other changes, S3), ITS-C-30 (a name 409 on create leaves other changes, S3, xfail BUG-1531), ITS-U-18 (a name 409 on rename leaves other changes, S3, xfail BUG-1531), ITS-C-31 (a padded name's 409 shows the trimmed name, xfail BUG-1531). No existing card changed, none retired.
> **Revision:** 1 — spec Gap log G1 (R4 covers a sent `tag_code` only; a derived code is R7, today's 409 is R7's Today note) and G2 (race patch target `item_tag_dao.get_by_code_in_workspace`). New: ITS-C-29 (race through the service, xfail BUG-1528). Changed: Conventions (race simulation, `item_tag_dao`); Reviewer summary. No card retired.
> **Counts:** 68 cases · 38 expected-to-pass · 30 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `get_tags` 8 (3 bug) · `get_system_tags` 4 (1 bug) · `create_tag` 31 (17 bug) · `update_tag` 18 (8 bug) · `delete_tag` 7 (1 bug).
- **Depth:** lighter target (skill step 1a): tags are labels; no stock, money or order state. Unlike the other services in this batch, this one holds its own rules (code derivation, duplicate checks, system-tag protection), so each rule and Errors row has its own cards; boundaries both sides (code cut at 50: 50 and 60 characters). Transaction rules S1–S4: S2 per write (failing commit), the failing re-read once (create), S3 (refusal without rollback) once per write, S4 per list.
- **Expected-to-fail:** BUG-1526 4, BUG-1527 1, BUG-1528 2, BUG-1529 3, BUG-1530 2, BUG-1531 8, BUG-1532 6, BUG-1533 2, pass-through BUG-929 1 and BUG-930 1 (both non-strict, as the item tag DAO cards). Every other xfail is strict (spec Notes).
- **Notable design choices:**
  - **S3 is the opposite of the other services:** refusals come before the `try` and do not roll back. ITS-C-11, C-30, U-01, U-05, U-18, D-02, D-07 keep an uncommitted extra tag and check it is **still there** after the refusal. The failing-commit cards check that the same kind of row is **gone**.
  - Regression split: BUG-1532 R4 — that a stored `café` tag is still returned by `get_tags` holds today (T-05, pass); only the response-schema check is xfail (T-06).
  - The index cards (C-14 BUG-1528, C-23 BUG-1531) insert the second row directly, as the spec's Notes say. C-29 is the code race through the service (patched `get_by_code_in_workspace`, spec G2); the name race stays index-only until the fix names its lookup.
  - R4 covers a sent code only (spec G1); a taken derived code is R7 (C-16, C-17), and today's 409 for it is only a Today note, never a pass card.
  - Names never repeat among live tags of a workspace in any Given (BUG-1531's index), except in the cards about exactly that.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `ITS` = `app/services/item_tag_service.py`. `T` get_tags · `Y` get_system_tags · `C` create_tag · `U` update_tag · `D` delete_tag.

**Actors and fixed values.**
- `svc` = the singleton `item_tag_service` (`from app.services.item_tag_service import ItemTagService, item_tag_service`). `db` = the test's real session, always the first argument; the rest by keyword. `result` = what the When call returns.
- `ItemTag` (`app.models.item_tag`), `Item` (`app.models.item`), `ItemTagAssignment` (`app.models.item_tag_assignment`), `ItemTagCreate`, `ItemTagUpdate`, `ItemTagResponse` (`app.schemas.item_tag`). `PydanticValidationError` = `pydantic.ValidationError`. `item_tag_dao` (`app.dao.item_tag`). `HTTPException` (`fastapi`); `IntegrityError` (`sqlalchemy.exc`); `inspect`, `text`, `select` (`sqlalchemy`); `patch` (`unittest.mock`).
- W1, W2 = two `workspaces` rows; U1 = a `profiles` row (`make_workspace`, `make_profile`). U1 is the acting user. MISSING = `999999999`. `BN` = `"কাঁচামাল"` (Bengali, "raw material").

**Externals.** None is mocked. `created_at` is the model's Python default: checked as not None.

**Standing rows.** In every test, no Given line needed: I1 = `Item(workspace_id=W1.id, name="Bolt M8", name_normalized="bolt m8", unit="pcs", is_active=True)`; IX = the same, but `name "Old Rivet"`, `name_normalized "old rivet"`, `is_active False`. No tag exists unless a Given line builds it.

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written, ids rising in that order. A Given line written as code is a step to run exactly.
- **tag** = `ItemTag(workspace_id=W1.id, is_system_tag=False, is_active=True, usage_count=0, color=None, icon=None, description=None, created_by=None)`; the card gives `name` and `tag_code`; after "but" every other column that differs. **system tag** = a tag, but `is_system_tag True`. **deleted** (of a tag) = `is_active False`.
- **link of I to T** = `ItemTagAssignment(workspace_id=W1.id, item_id=I.id, tag_id=T.id, assigned_by=U1.id)`.
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). A Given line marked "(after the commit point)" runs after it, is flushed, and stays uncommitted.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **stored_count(T)** = `db.scalar(select(ItemTag.usage_count).where(ItemTag.id == T.id))`, without expiring or refreshing T.
- **nothing written** = the number of `item_tags` rows (all workspaces) equals its value at the commit point.
- **the new row** = the one `item_tags` row of W1 whose id is not among the Given rows, read with a fresh query.
- `count:` lines count `item_tags` rows with a fresh query, with the filter stated. **ids(x)** = `sorted(t.id for t in x)`.
- `loaded:` lines run on the returned object first: each column named is not in `inspect(result).unloaded`.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `read:` lines call the named `svc` reader after the When and check its result.
- `session:` lines check `db` itself; "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `schema:` lines validate a row with a schema class.
- `raises: <Type>`: plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint. Further `raises:` lines assert on `exc.value` after the block. A schema card wraps only the schema's construction (target `schema`). An index card (target `database`) wraps its insert: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then `db.add(...)`, `db.flush()`.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.

**xfail cards.** Write the call and checks as shown. Strict unless the Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Race simulations.** ITS-C-29 only (`create_tag` R6, BUG-1528): `with patch.object(item_tag_dao, "get_by_code_in_workspace", return_value=None):` around the When, inside the `raises:` wrap — the state of a concurrent create that already passed the code check.

## `ItemTagService.get_tags`

### ITS-T-01 — live tags of the workspace only, system tags first
- **Rules:** `get_tags` R1, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`.
2. KS = system tag, `name "Raw Material"`, `tag_code "raw_material"`.
3. KD = tag, `name "Obsolete"`, `tag_code "obsolete"`, but deleted.
4. KZ = tag, `name "Far Crate"`, `tag_code "far_crate"`, but `workspace_id W2.id`.

**When**
- `result = svc.get_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [K1.id, KS.id]`.
2. returns: `result[0].id == KS.id`.

### ITS-T-02 — each tag shows the number of active items linked to it; no link shows 0
- **Rules:** `get_tags` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`, but `usage_count 9`.
2. K2 = tag, `name "Nut"`, `tag_code "nut"`, but `usage_count 4`.
3. link of I1 to K1.
4. link of IX to K1.

**When**
- `result = svc.get_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `{t.id: t.usage_count for t in result} == {K1.id: 1, K2.id: 0}`.

### ITS-T-03 — the live count is not saved or committed, but the objects stay changed
- **Rules:** `get_tags` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`, but `usage_count 9`.
2. link of I1 to K1.

**When**
- `result = svc.get_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[0].usage_count == 1`.
2. session: `K1 in db.dirty`.
3. count: `stored_count(K1) == 9`.
4. committed: `stored_count(K1) == 9`.

### ITS-T-04 — the list neither commits nor rolls back
- **Rules:** `get_tags` R5; S4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`.
2. P = tag, `name "Pending"`, `tag_code "pending"` (after the commit point).

**When**
- `result = svc.get_tags(db, workspace_id=W1.id)`, with **spies**.

**Then**
1. returns: `ids(result) == [K1.id, P.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. committed: `item_tags` rows with `tag_code == "pending"`: exactly 0.

### ITS-T-05 — a stored tag with an invalid code is still returned
- **Rules:** `get_tags` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = tag, `name "Café"`, `tag_code "café"`.

**When**
- `result = svc.get_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [K1.id]`.
2. returns: `result[0].tag_code == "café"`.

### ITS-T-06 — a stored tag with an invalid code passes the response schema
- **Rules:** `get_tags` R4 [BUG-1532]
- **Kind:** bug
- **Expect:** xfail BUG-1532
- **Fails today on:** Then 2 (`ItemTagResponse` refuses `café`)

**Given**
1. K1 = tag, `name "Café"`, `tag_code "café"`.

**When**
- `result = svc.get_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. schema: `ItemTagResponse.model_validate(result[0]).tag_code == "café"`.

### ITS-T-07 — a stored tag with an empty code passes the response schema
- **Rules:** `get_tags` R4 [BUG-1532]
- **Kind:** bug
- **Expect:** xfail BUG-1532
- **Fails today on:** Then 2 (`ItemTagResponse` refuses `""`)

**Given**
1. K1 = tag, `name "!!!"`, `tag_code ""`.

**When**
- `result = svc.get_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. schema: `ItemTagResponse.model_validate(result[0]).tag_code == ""`.

### ITS-T-08 — pass-through BUG-930: names come case-insensitive ascending
- **Rules:** `get_tags` R1 [BUG-930]
- **Kind:** bug
- **Expect:** xfail BUG-930 (non-strict)
- **Fails today on:** Then 2 (the order rests on the server's collation)

**Given**
1. K1 = tag, `name "bravo"`, `tag_code "bravo"`.
2. K2 = tag, `name "Alpha"`, `tag_code "alpha"`.
3. K3 = tag, `name "Charlie"`, `tag_code "charlie"`.

**When**
- `result = svc.get_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [K1.id, K2.id, K3.id]`.
2. returns: `[t.name for t in result] == ["Alpha", "bravo", "Charlie"]`.

## `ItemTagService.get_system_tags`

### ITS-Y-01 — the workspace's system tags only
- **Rules:** `get_system_tags` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`.
2. KS = system tag, `name "Raw Material"`, `tag_code "raw_material"`.
3. KZ = system tag, `name "Far Raw"`, `tag_code "far_raw"`, but `workspace_id W2.id`.

**When**
- `result = svc.get_system_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [KS.id]`.

### ITS-Y-02 — usage_count is the stored counter
- **Rules:** `get_system_tags` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. KS = system tag, `name "Raw Material"`, `tag_code "raw_material"`, but `usage_count 9`.
2. link of I1 to KS.
3. link of IX to KS.

**When**
- `result = svc.get_system_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `result[0].usage_count == 9`.

### ITS-Y-03 — the list neither commits nor rolls back
- **Rules:** `get_system_tags` R3; S4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. KS = system tag, `name "Raw Material"`, `tag_code "raw_material"`.
2. P = tag, `name "Pending"`, `tag_code "pending"` (after the commit point).

**When**
- `result = svc.get_system_tags(db, workspace_id=W1.id)`, with **spies**.

**Then**
1. returns: `ids(result) == [KS.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: `item_tags` rows with `tag_code == "pending"`: exactly 1.
5. committed: `item_tags` rows with `tag_code == "pending"`: exactly 0.

### ITS-Y-04 — pass-through BUG-929: system tags come by name, case-insensitive ascending
- **Rules:** `get_system_tags` R1 [BUG-929]
- **Kind:** bug
- **Expect:** xfail BUG-929 (non-strict)
- **Fails today on:** Then 2 (no order is asked for; insertion order usually comes back)

**Given**
1. S1 = system tag, `name "Tool"`, `tag_code "tool"`.
2. S2 = system tag, `name "consumable"`, `tag_code "consumable"`.
3. S3 = system tag, `name "Bolt"`, `tag_code "bolt"`.

**When**
- `result = svc.get_system_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id, S2.id, S3.id]`.
2. returns: `[t.name for t in result] == ["Bolt", "consumable", "Tool"]`.

## `ItemTagService.create_tag`

### ITS-C-01 — a sent tag_code is used as sent
- **Rules:** `create_tag` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=ItemTagCreate(name="Steel", tag_code="metal_1"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "metal_1"`.
2. committed: the new row: `tag_code == "metal_1"`, `name == "Steel"`.

### ITS-C-02 — with no code, spaces become _ and digits stay
- **Rules:** `create_tag` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=ItemTagCreate(name="Raw Material 2"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "raw_material_2"`.
2. committed: the new row: `tag_code == "raw_material_2"`.

### ITS-C-03 — with no code, other symbols are dropped
- **Rules:** `create_tag` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=ItemTagCreate(name="Steel-Bar"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "steelbar"`.

### ITS-C-04 — a derived code drops accented letters
- **Rules:** `create_tag` R3 [BUG-1532]
- **Kind:** bug
- **Expect:** xfail BUG-1532
- **Fails today on:** Then 1 (the code is `café`)

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=ItemTagCreate(name="Café"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "caf"`.
2. committed: the new row: `tag_code == "caf"`.

### ITS-C-05 — a derived code with nothing left is "tag"
- **Rules:** `create_tag` R3 [BUG-1532]
- **Kind:** bug
- **Expect:** xfail BUG-1532
- **Fails today on:** Then 1 (the code is `""`)

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=ItemTagCreate(name="!!!"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "tag"`.

### ITS-C-06 — a derived code is cut to 50 characters
- **Rules:** `create_tag` R3 [BUG-1532]
- **Kind:** bug
- **Expect:** xfail BUG-1532
- **Fails today on:** Then 1 (the code keeps all 60 characters)

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=ItemTagCreate(name="a" * 60), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "a" * 50`.

### ITS-C-07 — a derived code of exactly 50 characters is kept whole
- **Rules:** `create_tag` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=ItemTagCreate(name="a" * 50), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "a" * 50`.

### ITS-C-08 — a padded name is stored trimmed and its code derived from the trimmed name
- **Rules:** `create_tag` R3, R9 [BUG-1526]
- **Kind:** bug
- **Expect:** xfail BUG-1526
- **Fails today on:** Then 1 (the code is `_bolt_`)

**Given**
1. W1 has no tags.
2. `data = ItemTagCreate(name=" Bolt ")`.

**When**
- `result = svc.create_tag(db, tag_in=data, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "bolt"`.
2. committed: the new row: `name == "Bolt"`, `tag_code == "bolt"`.

### ITS-C-09 — a Bengali name derives "tag"
- **Rules:** `create_tag` R3 [BUG-1532]
- **Kind:** bug
- **Expect:** xfail BUG-1532
- **Fails today on:** Then 1 (the code is `কচমল`)

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=ItemTagCreate(name=BN), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "tag"`.

### ITS-C-10 — a whitespace-only name is refused by the schema
- **Rules:** `create_tag` R9 [BUG-1526], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1526
- **Fails today on:** Then 1 (the schema builds the object)

**Given**
1. W1 has no tags.

**When**
- build `ItemTagCreate(name="   ")` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. nothing written: nothing written.

### ITS-C-11 — an explicit code taken: 409, nothing written, and no rollback of other changes
- **Rules:** `create_tag` R4, R7, R11, Errors row 2; S3
- **Kind:** error
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`.
2. X = tag, `name "Extra"`, `tag_code "extra"` (after the commit point).

**When**
- `svc.create_tag(db, tag_in=ItemTagCreate(name="Screw", tag_code="bolt"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Tag with code 'bolt' already exists"`.
4. count: `item_tags` rows with `name == "Screw"`: exactly 0.
5. count: `item_tags` rows with `tag_code == "extra"`: exactly 1.
6. unchanged: unchanged(K1).

### ITS-C-12 — the same code in another workspace does not block
- **Rules:** `create_tag` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. KZ = tag, `name "Bolt"`, `tag_code "bolt"`, but `workspace_id W2.id`.

**When**
- `result = svc.create_tag(db, tag_in=ItemTagCreate(name="Bolt", tag_code="bolt"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.workspace_id == W1.id`, `result.tag_code == "bolt"`.
2. committed: `item_tags` rows with `tag_code == "bolt"`: exactly 2.

### ITS-C-13 — a deleted tag's code can be used again
- **Rules:** `create_tag` R5 [BUG-1527]
- **Kind:** bug
- **Expect:** xfail BUG-1527
- **Fails today on:** Then 1 (409: deleted tags are counted)

**Given**
1. KD = tag, `name "Old Bolt"`, `tag_code "bolt"`, but deleted.

**When**
- `result = svc.create_tag(db, tag_in=ItemTagCreate(name="Bolt", tag_code="bolt"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id != KD.id`, `result.tag_code == "bolt"`.
2. committed: `item_tags` rows of W1 with `tag_code == "bolt"`: exactly 2.

### ITS-C-14 — the database refuses a second live tag with the same code
- **Rules:** `create_tag` R6 [BUG-1528]
- **Kind:** bug
- **Expect:** xfail BUG-1528
- **Fails today on:** Then 1 (no index: the second row is stored)

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`.

**When**
- insert tag, `name "Screw"`, `tag_code "bolt"` directly (target `database`).

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `item_tags` rows with `tag_code == "bolt"`: exactly 1.

### ITS-C-15 — the code index leaves deleted tags out
- **Rules:** `create_tag` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. KD = tag, `name "Old Bolt"`, `tag_code "bolt"`, but deleted.

**When**
- insert tag, `name "Bolt"`, `tag_code "bolt"` directly, then `db.flush()` (target `database`).

**Then**
1. count: `item_tags` rows with `tag_code == "bolt"`: exactly 2.

### ITS-C-16 — a derived code taken gets the first free suffix
- **Rules:** `create_tag` R7 [BUG-1533]
- **Kind:** bug
- **Expect:** xfail BUG-1533
- **Fails today on:** Then 1 (409 `Tag with code 'steelbar' already exists`)

**Given**
1. K1 = tag, `name "Steel-Bar"`, `tag_code "steelbar"`.

**When**
- `result = svc.create_tag(db, tag_in=ItemTagCreate(name="SteelBar"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "steelbar_2"`.
2. committed: the new row: `tag_code == "steelbar_2"`, `name == "SteelBar"`.

### ITS-C-17 — the suffix skips taken ones: _2 taken gives _3
- **Rules:** `create_tag` R7 [BUG-1533]
- **Kind:** bug
- **Expect:** xfail BUG-1533
- **Fails today on:** Then 1 (409 `Tag with code 'steelbar' already exists`)

**Given**
1. K1 = tag, `name "Steel-Bar"`, `tag_code "steelbar"`.
2. K2 = tag, `name "Steel Bar Two"`, `tag_code "steelbar_2"`.

**When**
- `result = svc.create_tag(db, tag_in=ItemTagCreate(name="SteelBar"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "steelbar_3"`.

### ITS-C-18 — a live name in another case is refused, with the submitted name
- **Rules:** `create_tag` R8 [BUG-1531], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1531
- **Fails today on:** Then 1 (no error: names are not checked)

**Given**
1. K1 = tag, `name "Paint"`, `tag_code "paint1"`.

**When**
- `svc.create_tag(db, tag_in=ItemTagCreate(name="PAINT", tag_code="paint2"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Tag with name 'PAINT' already exists"`.
4. nothing written: nothing written.

### ITS-C-19 — a system tag's name blocks too
- **Rules:** `create_tag` R8 [BUG-1531], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1531
- **Fails today on:** Then 1 (no error: names are not checked)

**Given**
1. KS = system tag, `name "Raw Material"`, `tag_code "raw_material"`.

**When**
- `svc.create_tag(db, tag_in=ItemTagCreate(name="raw material", tag_code="rm2"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Tag with name 'raw material' already exists"`.
4. nothing written: nothing written.

### ITS-C-20 — the name is checked before the code
- **Rules:** `create_tag` R8 [BUG-1531], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1531
- **Fails today on:** Then 3 (the code's 409 comes instead)

**Given**
1. K1 = tag, `name "Paint"`, `tag_code "paint"`.

**When**
- `svc.create_tag(db, tag_in=ItemTagCreate(name="Paint", tag_code="paint"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Tag with name 'Paint' already exists"`.
4. nothing written: nothing written.

### ITS-C-21 — a deleted tag's name does not block
- **Rules:** `create_tag` R8
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. KD = tag, `name "Paint"`, `tag_code "old_paint"`, but deleted.

**When**
- `result = svc.create_tag(db, tag_in=ItemTagCreate(name="Paint", tag_code="paint"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "Paint"`, `result.id != KD.id`.

### ITS-C-22 — another workspace's name does not block
- **Rules:** `create_tag` R8
- **Kind:** isolation
- **Expect:** pass

**Given**
1. KZ = tag, `name "Paint"`, `tag_code "paint"`, but `workspace_id W2.id`.

**When**
- `result = svc.create_tag(db, tag_in=ItemTagCreate(name="Paint", tag_code="paint_w1"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "Paint"`, `result.workspace_id == W1.id`.

### ITS-C-23 — the database refuses a second live tag with the same name ignoring case
- **Rules:** `create_tag` R8 [BUG-1531]
- **Kind:** bug
- **Expect:** xfail BUG-1531
- **Fails today on:** Then 1 (no index: the second row is stored)

**Given**
1. K1 = tag, `name "Paint"`, `tag_code "paint1"`.

**When**
- insert tag, `name "PAINT"`, `tag_code "paint2"` directly (target `database`).

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `item_tags` rows of W1: exactly 1.

### ITS-C-24 — a new tag carries every given field and the fixed ones; committed and returned re-read
- **Rules:** `create_tag` R10, Returns; S1
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=ItemTagCreate(name="Steel", tag_code="steel", color="#FF0000", icon="bolt", description="Metal stock"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `created_at`, `tag_code`, `name`, `usage_count`.
2. returns: `isinstance(result, ItemTag)`.
3. returns: `result.created_at is not None`, `result.created_by == U1.id`.
4. committed: the new row: `workspace_id == W1.id`, `name == "Steel"`, `tag_code == "steel"`.
5. committed: the new row: `color == "#FF0000"`, `icon == "bolt"`, `description == "Metal stock"`.
6. committed: the new row: `created_by == U1.id`, `is_system_tag is False`, `usage_count == 0`, `is_active is True`.

### ITS-C-25 — a client cannot make a system tag
- **Rules:** `create_tag` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no tags.
2. `data = ItemTagCreate.model_validate({"name": "Steel", "is_system_tag": True, "usage_count": 5})`.

**When**
- `result = svc.create_tag(db, tag_in=data, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.is_system_tag is False`.
2. committed: the new row: `is_system_tag is False`, `usage_count == 0`.

### ITS-C-26 — a failing commit is rolled back and re-raised; other uncommitted changes go too
- **Rules:** `create_tag` R11; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`.
2. X = tag, `name "Extra"`, `tag_code "extra"` (after the commit point).

**When**
- `svc.create_tag(db, tag_in=ItemTagCreate(name="Steel"), workspace_id=W1.id, user_id=U1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `item_tags` rows with `name == "Steel"`: exactly 0.
4. count: `item_tags` rows with `tag_code == "extra"`: exactly 0.

### ITS-C-27 — a failing re-read after the commit leaves the tag saved
- **Rules:** `create_tag` R11; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no tags.

**When**
- `svc.create_tag(db, tag_in=ItemTagCreate(name="Steel"), workspace_id=W1.id, user_id=U1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `item_tags` rows of W1 with `name == "Steel"`: exactly 1.

### ITS-C-28 — a database error inside the write is rolled back and passed on
- **Rules:** `create_tag` R11; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. X = tag, `name "Extra"`, `tag_code "extra"` (after the commit point).
2. `data = ItemTagCreate.model_construct(name=None, tag_code="nameless", color=None, icon=None, description=None)` (after the commit point).

**When**
- `svc.create_tag(db, tag_in=data, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23502"`.
3. count: `item_tags` rows with `tag_code == "extra"`: exactly 0.
4. nothing written: nothing written.
5. session: usable.

### ITS-C-29 — a create that loses the code race gets the 409, one row stays
- **Rules:** `create_tag` R6 [BUG-1528], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1528
- **Fails today on:** Then 1 (no error: no index, so a second "steel" is saved)

**Given**
1. K1 = tag, `name "Steel"`, `tag_code "steel"`.

**When**
- `svc.create_tag(db, tag_in=ItemTagCreate(name="Steel Two", tag_code="steel"), workspace_id=W1.id, user_id=U1.id)`, with the race simulation active.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Tag with code 'steel' already exists"`.
4. count: `item_tags` rows of W1 with `tag_code == "steel"`: exactly 1.
5. unchanged: unchanged(K1).
6. session: usable.

### ITS-C-30 — a name refusal leaves other uncommitted changes alone
- **Rules:** `create_tag` R8, R11 [BUG-1531]; S3
- **Kind:** bug
- **Expect:** xfail BUG-1531
- **Fails today on:** Then 1 (no error: names are not checked)

**Given**
1. K1 = tag, `name "Paint"`, `tag_code "paint1"`.
2. X = tag, `name "Extra"`, `tag_code "extra"` (after the commit point).

**When**
- `svc.create_tag(db, tag_in=ItemTagCreate(name="PAINT", tag_code="paint2"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. count: `item_tags` rows with `tag_code == "extra"`: exactly 1.

### ITS-C-31 — a padded name's 409 names the trimmed name
- **Rules:** `create_tag` R8 [BUG-1531], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1531
- **Fails today on:** Then 1 (no error: names are not checked)

**Given**
1. K1 = tag, `name "Paint"`, `tag_code "paint1"`.

**When**
- `svc.create_tag(db, tag_in=ItemTagCreate(name=" PAINT ", tag_code="paint2"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Tag with name 'PAINT' already exists"`.
4. nothing written: nothing written.

## `ItemTagService.update_tag`

### ITS-U-01 — another workspace's id: 404, nothing written, no rollback of other changes
- **Rules:** `update_tag` R1, R9, Errors row 1; S3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`.
2. KZ = tag, `name "Far"`, `tag_code "far"`, but `workspace_id W2.id`.
3. X = tag, `name "Extra"`, `tag_code "extra"` (after the commit point).

**When**
- `svc.update_tag(db, tag_id=KZ.id, tag_in=ItemTagUpdate(name="Hacked"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Tag not found"`.
4. count: `item_tags` rows with `tag_code == "extra"`: exactly 1.
5. unchanged: unchanged(KZ).

### ITS-U-02 — id 0 gets the 404
- **Rules:** `update_tag` R1, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`.

**When**
- `svc.update_tag(db, tag_id=0, tag_in=ItemTagUpdate(name="Hacked"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Tag not found"`.
4. unchanged: unchanged(K1).

### ITS-U-03 — a deleted tag is not found
- **Rules:** `update_tag` R2 [BUG-1529], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1529
- **Fails today on:** Then 1 (no error: the deleted tag is edited)

**Given**
1. KD = tag, `name "Obsolete"`, `tag_code "obsolete"`, but deleted.

**When**
- `svc.update_tag(db, tag_id=KD.id, tag_in=ItemTagUpdate(name="Revived"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Tag not found"`.
4. unchanged: unchanged(KD).

### ITS-U-04 — is_active true cannot bring a deleted tag back
- **Rules:** `update_tag` R2 [BUG-1529], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1529
- **Fails today on:** Then 1 (no error: the tag is restored)

**Given**
1. KD = tag, `name "Obsolete"`, `tag_code "obsolete"`, but deleted.

**When**
- `svc.update_tag(db, tag_id=KD.id, tag_in=ItemTagUpdate(is_active=True), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. committed: re-read KD: `is_active is False`.

### ITS-U-05 — a system tag: 403, nothing written, no rollback of other changes
- **Rules:** `update_tag` R3, R9, Errors row 2; S3
- **Kind:** error
- **Expect:** pass

**Given**
1. KS = system tag, `name "Raw Material"`, `tag_code "raw_material"`.
2. X = tag, `name "Extra"`, `tag_code "extra"` (after the commit point).

**When**
- `svc.update_tag(db, tag_id=KS.id, tag_in=ItemTagUpdate(color="#00FF00"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "System tags cannot be modified"`.
4. count: `item_tags` rows with `tag_code == "extra"`: exactly 1.
5. unchanged: unchanged(KS).

### ITS-U-06 — another workspace's system tag gets the 404, not the 403
- **Rules:** `update_tag` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. KZ = system tag, `name "Far Raw"`, `tag_code "far_raw"`, but `workspace_id W2.id`.

**When**
- `svc.update_tag(db, tag_id=KZ.id, tag_in=ItemTagUpdate(color="#00FF00"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Tag not found"`.

### ITS-U-07 — every field sent is written; the code stays on a rename; committed and returned re-read
- **Rules:** `update_tag` R4, R9, Returns; S1
- **Kind:** happy
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`, but `color "#000000"`, `icon "nut"`, `description "Old"`, `usage_count 3`.

**When**
- `result = svc.update_tag(db, tag_id=K1.id, tag_in=ItemTagUpdate(name="Steel Bolt", color="#FF0000", icon="bolt", description="New"), workspace_id=W1.id)`.

**Then**
1. loaded: `name`, `color`, `tag_code`.
2. returns: `result.id == K1.id`, `result.name == "Steel Bolt"`.
3. committed: re-read K1: `name == "Steel Bolt"`, `color == "#FF0000"`, `icon == "bolt"`, `description == "New"`.
4. committed: re-read K1: `tag_code == "bolt"`, `usage_count == 3`, `is_active is True`.

### ITS-U-08 — omitted fields stay
- **Rules:** `update_tag` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`, but `color "#000000"`, `icon "nut"`, `description "Old"`.

**When**
- `result = svc.update_tag(db, tag_id=K1.id, tag_in=ItemTagUpdate(color="#FF0000"), workspace_id=W1.id)`.

**Then**
1. returns: `result.color == "#FF0000"`.
2. committed: re-read K1: `name == "Bolt"`, `icon == "nut"`, `description == "Old"`.

### ITS-U-09 — explicit null clears color, icon and description
- **Rules:** `update_tag` R5 [BUG-1530]
- **Kind:** bug
- **Expect:** xfail BUG-1530
- **Fails today on:** Then 2 (every null is dropped)

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`, but `color "#000000"`, `icon "nut"`, `description "Old"`.

**When**
- `result = svc.update_tag(db, tag_id=K1.id, tag_in=ItemTagUpdate(color=None, icon=None, description=None), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == K1.id`.
2. committed: re-read K1: `color is None`, `icon is None`, `description is None`.
3. committed: re-read K1: `name == "Bolt"`.

### ITS-U-10 — null for name is refused by the schema
- **Rules:** `update_tag` R5 [BUG-1530]
- **Kind:** bug
- **Expect:** xfail BUG-1530
- **Fails today on:** Then 1 (the schema builds the object)

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`.

**When**
- build `ItemTagUpdate(name=None)` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. unchanged: unchanged(K1).

### ITS-U-11 — a rename to another live tag's name is refused
- **Rules:** `update_tag` R6 [BUG-1531], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1531
- **Fails today on:** Then 1 (no error: the rename is stored)

**Given**
1. K1 = tag, `name "Paint"`, `tag_code "paint"`.
2. K2 = tag, `name "Bolt"`, `tag_code "bolt"`.

**When**
- `svc.update_tag(db, tag_id=K2.id, tag_in=ItemTagUpdate(name="paint"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Tag with name 'paint' already exists"`.
4. unchanged: unchanged(K2).

### ITS-U-12 — the tag's own name in another case is accepted
- **Rules:** `update_tag` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = tag, `name "Paint"`, `tag_code "paint"`.

**When**
- `result = svc.update_tag(db, tag_id=K1.id, tag_in=ItemTagUpdate(name="PAINT"), workspace_id=W1.id)`.

**Then**
1. returns: `result.name == "PAINT"`.
2. committed: re-read K1: `name == "PAINT"`.

### ITS-U-13 — a blank new name is refused by the schema
- **Rules:** `update_tag` R7 [BUG-1526]
- **Kind:** bug
- **Expect:** xfail BUG-1526
- **Fails today on:** Then 1 (the schema builds the object)

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`.

**When**
- build `ItemTagUpdate(name="  ")` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. unchanged: unchanged(K1).

### ITS-U-14 — a padded new name is stored trimmed
- **Rules:** `update_tag` R7 [BUG-1526]
- **Kind:** bug
- **Expect:** xfail BUG-1526
- **Fails today on:** Then 2 (stored with its spaces)

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`.
2. `data = ItemTagUpdate(name="  Steel  ")`.

**When**
- `result = svc.update_tag(db, tag_id=K1.id, tag_in=data, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == K1.id`.
2. committed: re-read K1: `name == "Steel"`.

### ITS-U-15 — is_active false hides a live tag exactly as a delete
- **Rules:** `update_tag` R8
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`, but `usage_count 3`.
2. L = link of I1 to K1.

**When**
- `result = svc.update_tag(db, tag_id=K1.id, tag_in=ItemTagUpdate(is_active=False), workspace_id=W1.id)`.

**Then**
1. returns: `result.is_active is False`.
2. committed: re-read K1: `is_active is False`, `usage_count == 3`, `name == "Bolt"`.
3. committed: re-read L: `tag_id == K1.id`.
4. read: `svc.get_tags(db, workspace_id=W1.id) == []`.

### ITS-U-16 — is_active true on a live tag changes nothing
- **Rules:** `update_tag` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`.

**When**
- `result = svc.update_tag(db, tag_id=K1.id, tag_in=ItemTagUpdate(is_active=True), workspace_id=W1.id)`.

**Then**
1. returns: `result.is_active is True`.
2. unchanged: unchanged(K1).

### ITS-U-17 — a failing commit is rolled back and re-raised; other uncommitted changes go too
- **Rules:** `update_tag` R9; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`.
2. X = tag, `name "Extra"`, `tag_code "extra"` (after the commit point).

**When**
- `svc.update_tag(db, tag_id=K1.id, tag_in=ItemTagUpdate(name="Steel"), workspace_id=W1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(K1).
4. count: `item_tags` rows with `tag_code == "extra"`: exactly 0.

### ITS-U-18 — a name refusal on rename leaves other uncommitted changes alone
- **Rules:** `update_tag` R6, R9 [BUG-1531]; S3
- **Kind:** bug
- **Expect:** xfail BUG-1531
- **Fails today on:** Then 1 (no error: the rename is stored)

**Given**
1. K1 = tag, `name "Paint"`, `tag_code "paint"`.
2. K2 = tag, `name "Bolt"`, `tag_code "bolt"`.
3. X = tag, `name "Extra"`, `tag_code "extra"` (after the commit point).

**When**
- `svc.update_tag(db, tag_id=K2.id, tag_in=ItemTagUpdate(name="paint"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. count: `item_tags` rows with `tag_code == "extra"`: exactly 1.

## `ItemTagService.delete_tag`

### ITS-D-01 — a live user tag gets is_active False and nothing else; committed
- **Rules:** `delete_tag` R4, Returns; S1
- **Kind:** happy
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`, but `usage_count 3`, `color "#000000"`.
2. L = link of I1 to K1.

**When**
- `result = svc.delete_tag(db, tag_id=K1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. committed: re-read K1: `is_active is False`.
3. committed: re-read K1: `usage_count == 3`, `name == "Bolt"`, `tag_code == "bolt"`, `color == "#000000"`, `is_system_tag is False`.
4. committed: re-read L: `tag_id == K1.id`, `item_id == I1.id`.
5. read: `svc.get_tags(db, workspace_id=W1.id) == []`.

### ITS-D-02 — another workspace's id: 404, nothing written, no rollback of other changes
- **Rules:** `delete_tag` R1, R5, Errors row 1; S3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. KZ = tag, `name "Far"`, `tag_code "far"`, but `workspace_id W2.id`.
2. X = tag, `name "Extra"`, `tag_code "extra"` (after the commit point).

**When**
- `svc.delete_tag(db, tag_id=KZ.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Tag not found"`.
4. count: `item_tags` rows with `tag_code == "extra"`: exactly 1.
5. unchanged: unchanged(KZ).

### ITS-D-03 — id 0 gets the 404
- **Rules:** `delete_tag` R1, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`.

**When**
- `svc.delete_tag(db, tag_id=0, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Tag not found"`.
4. unchanged: unchanged(K1).

### ITS-D-04 — an already deleted tag is not found
- **Rules:** `delete_tag` R2 [BUG-1529], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1529
- **Fails today on:** Then 1 (no error: deleted again, `None`)

**Given**
1. KD = tag, `name "Obsolete"`, `tag_code "obsolete"`, but deleted.

**When**
- `svc.delete_tag(db, tag_id=KD.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Tag not found"`.
4. unchanged: unchanged(KD).

### ITS-D-05 — a system tag: 403, nothing written
- **Rules:** `delete_tag` R3, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. KS = system tag, `name "Raw Material"`, `tag_code "raw_material"`.

**When**
- `svc.delete_tag(db, tag_id=KS.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "System tags cannot be deleted"`.
4. unchanged: unchanged(KS).

### ITS-D-06 — a failing commit is rolled back and re-raised: the tag stays live
- **Rules:** `delete_tag` R5; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. K1 = tag, `name "Bolt"`, `tag_code "bolt"`.
2. X = tag, `name "Extra"`, `tag_code "extra"` (after the commit point).

**When**
- `svc.delete_tag(db, tag_id=K1.id, workspace_id=W1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(K1).
4. count: `item_tags` rows with `tag_code == "extra"`: exactly 0.

### ITS-D-07 — a system-tag refusal leaves other uncommitted changes alone
- **Rules:** `delete_tag` R3, R5; S3
- **Kind:** error
- **Expect:** pass

**Given**
1. KS = system tag, `name "Raw Material"`, `tag_code "raw_material"`.
2. X = tag, `name "Extra"`, `tag_code "extra"` (after the commit point).

**When**
- `svc.delete_tag(db, tag_id=KS.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. count: `item_tags` rows with `tag_code == "extra"`: exactly 1.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| HTTP status of the `HTTPException`s; `ItemTagResponse` on the answers (`GET /item-tags/` 500 today, BUG-1532 (b)) | `/item-tags/` endpoints (integration) | The list answers 200 with a stored `café` tag once fixed. |
| BUG-1526, BUG-1530 — 422 at the API (400 today, BUG-461) | `POST`, `PUT /item-tags/` | Integration-only. |
| BUG-1528, BUG-1531 — the partial unique indexes; a lost race through the global handler or the service as 409 | migration + integration | Index cards C-14, C-23 here; the 409 shape is integration. |
| Existing duplicate names to merge before BUG-1531's index | data migration (Q1) | Not a unit rule. |
| BUG-931 — counter race | item code (`item_manager`) | Not reached here. |
| FU-2 — the same bugs in `account_tag_service` | account tag service spec | Precedents only. |
| FU-3 — the three unreachable `except HTTPException: raise` clauses | dead-code removal | No case: unreachable. |

## Spec gaps
None. Revision 0's gaps 1 and 2 are closed by spec Gap log G1, G2.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_tags` | R1 | ITS-T-01 |
| `get_tags` | R1 [BUG-930] | ITS-T-08 |
| `get_tags` | R2 | ITS-T-02 |
| `get_tags` | R3 | ITS-T-03 |
| `get_tags` | R4 | ITS-T-05 |
| `get_tags` | R4 [BUG-1532] | ITS-T-06, ITS-T-07 |
| `get_tags` | R5 | ITS-T-01, ITS-T-04 |
| `get_system_tags` | R1 | ITS-Y-01 |
| `get_system_tags` | R1 [BUG-929] | ITS-Y-04 |
| `get_system_tags` | R2 | ITS-Y-02 |
| `get_system_tags` | R3 | ITS-Y-03 |
| `create_tag` | R1 | ITS-C-01 |
| `create_tag` | R2 | ITS-C-02, ITS-C-03 |
| `create_tag` | R3 | ITS-C-07 |
| `create_tag` | R3 [BUG-1532] | ITS-C-04, ITS-C-05, ITS-C-06, ITS-C-09 |
| `create_tag` | R3 [BUG-1526] | ITS-C-08 |
| `create_tag` | R4 | ITS-C-11, ITS-C-12 |
| `create_tag` | R5 [BUG-1527] | ITS-C-13 |
| `create_tag` | R6 | ITS-C-15 |
| `create_tag` | R6 [BUG-1528] | ITS-C-14, ITS-C-29 |
| `create_tag` | R7 | ITS-C-11 (an explicit code taken stays R4's 409) |
| `create_tag` | R7 [BUG-1533] | ITS-C-16, ITS-C-17 |
| `create_tag` | R8 | ITS-C-21, ITS-C-22 |
| `create_tag` | R8 [BUG-1531] | ITS-C-18, ITS-C-19, ITS-C-20, ITS-C-23, ITS-C-30, ITS-C-31 |
| `create_tag` | R9 [BUG-1526] | ITS-C-08, ITS-C-10 |
| `create_tag` | R10 | ITS-C-24, ITS-C-25 |
| `create_tag` | R11 | ITS-C-11, ITS-C-26, ITS-C-27, ITS-C-28, ITS-C-30 |
| `create_tag` | Errors row 1 | ITS-C-18, ITS-C-19, ITS-C-20, ITS-C-31 |
| `create_tag` | Errors row 2 | ITS-C-11, ITS-C-29 |
| `create_tag` | Errors row 3 | ITS-C-10 |
| `create_tag` | Returns | ITS-C-24 |
| `update_tag` | R1 | ITS-U-01, ITS-U-02 |
| `update_tag` | R2 [BUG-1529] | ITS-U-03, ITS-U-04 |
| `update_tag` | R3 | ITS-U-05, ITS-U-06 |
| `update_tag` | R4 | ITS-U-07, ITS-U-08 |
| `update_tag` | R5 [BUG-1530] | ITS-U-09, ITS-U-10 |
| `update_tag` | R6 | ITS-U-12 |
| `update_tag` | R6 [BUG-1531] | ITS-U-11, ITS-U-18 |
| `update_tag` | R7 [BUG-1526] | ITS-U-13, ITS-U-14 |
| `update_tag` | R8 | ITS-U-15, ITS-U-16 |
| `update_tag` | R9 | ITS-U-01, ITS-U-05, ITS-U-07, ITS-U-17, ITS-U-18 |
| `update_tag` | Errors row 1 | ITS-U-01, ITS-U-02, ITS-U-03, ITS-U-04 |
| `update_tag` | Errors row 2 | ITS-U-05 |
| `update_tag` | Errors row 3 | ITS-U-11 |
| `update_tag` | Returns | ITS-U-07 |
| `delete_tag` | R1 | ITS-D-02, ITS-D-03 |
| `delete_tag` | R2 [BUG-1529] | ITS-D-04 |
| `delete_tag` | R3 | ITS-D-05, ITS-D-07 |
| `delete_tag` | R4 | ITS-D-01 |
| `delete_tag` | R5 | ITS-D-02, ITS-D-06, ITS-D-07 |
| `delete_tag` | Errors row 1 | ITS-D-02, ITS-D-03, ITS-D-04 |
| `delete_tag` | Errors row 2 | ITS-D-05 |
| `delete_tag` | Returns | ITS-D-01 |
| Transaction rules | S1 | ITS-C-24, ITS-U-07, ITS-D-01 |
| Transaction rules | S2 | ITS-C-26, ITS-C-27, ITS-C-28, ITS-U-17, ITS-D-06 |
| Transaction rules | S3 | ITS-C-11, ITS-C-30, ITS-U-01, ITS-U-05, ITS-U-18, ITS-D-02, ITS-D-07 |
| Transaction rules | S4 | ITS-T-04, ITS-Y-03 |
