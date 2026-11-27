# Test cases — `app/services/account_tag_service.py`

> **Spec:** `tests/unit/services/account_tag_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-04) — spec Gap log G1: `create_tag` R8 and `update_tag` R6 now both say the 409 shows the trimmed submitted name in its original case. ATV-C-29 (`' VENDOR X '` → `'VENDOR X'`) and ATV-U-16 (`' vendor x '` → `'vendor x'`) already assert exactly that; they stay as written. No card added, changed or retired.
> **Revision:** 3 (2026-11-04) — from `account_tag_service.verify.md`: R-AT-1 → new ATV-U-23 (a failing re-read on `update_tag` leaves the change saved); R-AT-2 → **failing commit** now raises a prebuilt `boom`, and ATV-C-37, U-22, D-07 gain a last Then line `exc.value is boom` (the error reaches the caller unchanged, not a copy). No card retired.
> **Counts:** 82 cases · 41 expected-to-pass · 41 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `get_tags` 8 (3 bug) · `get_system_tags` 5 (2 bug) · `create_tag` 39 (23 bug) · `update_tag` 23 (12 bug) · `delete_tag` 7 (1 bug).
- **Depth:** lighter target (skill step 1a): labels on accounts; no stock, money or order state. As its twin `item_tag_service.cases.md`, the service holds its own rules (code derivation, code check, system-tag protection), so each rule and Errors row has its own cards; the code length is pinned at 50 and 51 / 60.
- **Built in from the item tag verifier's findings (R-IT-1 … R-IT-4):** every refusal (404, 403, the code 409 and BUG-1689's name 409, on create, update and delete) has a card with an uncommitted extra tag that must **still be there** (S3); the name 409 is also carded with a padded name, whose message shows the trimmed name. The failing-commit cards check the same kind of row is **gone** (S2).
- **Expected-to-fail:** BUG-1682 4, BUG-1683 1, BUG-1684 2, BUG-1685 3, BUG-1688 3, BUG-1689 9, BUG-1690 6, BUG-1691 3, BUG-1692 2, BUG-1693 4, pass-through BUG-1482 2 (non-strict), BUG-1483 1, BUG-1485 1. Every other xfail is strict (spec Notes).
- **Notable design choices:**
  - Regression split for BUG-1690 (b): a stored `café` code passes `AccountTagResponse` today and must keep passing (ATV-T-05, pass); only the `""` code is xfail (ATV-T-04). For BUG-1692, a `tag_code: null` in a PUT changes nothing today (dropped) and after the fix (ignored): ATV-U-10, pass.
  - The index cards (ATV-C-16 BUG-1684, ATV-C-27 BUG-1689) insert the second row directly; ATV-C-18 is the code race through the service (patched DAO lookup, spec Notes).
  - Names never repeat among live tags of a workspace in any Given (BUG-1689's index), except in the cards about exactly that.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `ATV` = `app/services/account_tag_service.py`. `T` get_tags · `Y` get_system_tags · `C` create_tag · `U` update_tag · `D` delete_tag.

**Actors and fixed values.**
- `svc` = the singleton `account_tag_service` (`from app.services.account_tag_service import AccountTagService, account_tag_service`). `db` = the test's real session, always the first argument; the rest by keyword. `result` = what the When call returns.
- `AccountTag` (`app.models.account_tag`), `Account` (`app.models.account`), `AccountTagAssignment` (`app.models.account_tag_assignment`), `AccountTagCreate`, `AccountTagUpdate`, `AccountTagResponse` (`app.schemas.account_tag`). `PydanticValidationError` = `pydantic.ValidationError`. `account_tag_dao` (`app.dao.account_tag`). `HTTPException` (`fastapi`); `IntegrityError`, `DataError` (`sqlalchemy.exc`); `inspect`, `text`, `select` (`sqlalchemy`); `patch` (`unittest.mock`).
- W1, W2 = two `workspaces` rows; U1 = a `profiles` row (`make_workspace`, `make_profile`); they exist in every test. U1 is the acting user. MISSING = `999999999`. `BN` = `"কাঁচামাল"` (Bengali, "raw material").

**Externals.** None is mocked. `created_at` is the model's Python default: checked as not None.

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written, ids rising in that order. A Given line written as code is a step to run exactly. No tag exists unless a Given line builds it.
- **tag** = `AccountTag(workspace_id=W1.id, is_system_tag=False, is_active=True, usage_count=0, color=None, icon=None, description=None, created_by=None)`; the card gives `name` and `tag_code`; after "but" every other column that differs. **system tag** = a tag, but `is_system_tag True`. **deleted** (of a tag) = `is_active False`.
- **account A1** = `Account(workspace_id=W1.id, name="Acme")`. **link of A1 to T** = `AccountTagAssignment(workspace_id=W1.id, account_id=A1.id, tag_id=T.id)`.
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). A Given line marked "(after the commit point)" runs after it, is flushed, and stays uncommitted. **X** in a card is always the extra row: tag, `name "Extra"`, `tag_code "extra"` (after the commit point).

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the number of `account_tags` rows (all workspaces) equals its value at the commit point.
- **the new row** = the one `account_tags` row of W1 whose id is not among the Given rows, read with a fresh query.
- `count:` lines count `account_tags` rows with a fresh query, with the filter stated. **ids(x)** = `sorted(t.id for t in x)`.
- `loaded:` lines run on the returned object first: each column named is not in `inspect(result).unloaded`.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `read:` lines call the named `svc` reader after the When and check its result.
- `session:` lines check `db` itself; "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `schema:` lines validate a row or build an input with a schema class.
- `raises: <Type>`: plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint. Further `raises:` lines assert on `exc.value` after the block. A schema card wraps only the schema's construction (target `schema`). An index card (target `database`) wraps its insert: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then `db.add(...)`, `db.flush()`.
- **failing commit** = `boom = RuntimeError("boom")` built first, then `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=boom), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.

**xfail cards.** Write the call and checks as shown, also when a field does not exist yet. Strict unless the Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Race simulations.** ATV-C-18 only (`create_tag` R6, BUG-1684): `with patch.object(account_tag_dao, "get_by_tag_code_in_workspace", return_value=None):` around the When, inside the `raises:` wrap — the state of a concurrent create that already passed the code check.

## `AccountTagService.get_tags`

### ATV-T-01 — live tags of the workspace only, system and user
- **Rules:** `get_tags` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. KZ1 = tag, `name "Far One"`, `tag_code "far_one"`, but `workspace_id W2.id`.
2. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.
3. KS = system tag, `name "Supplier"`, `tag_code "supplier"`.
4. KD = tag, `name "Obsolete"`, `tag_code "obsolete"`, but deleted.
5. KZ2 = tag, `name "Far Two"`, `tag_code "far_two"`, but `workspace_id W2.id`.

**When**
- `result = svc.get_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [K1.id, KS.id]`.

### ATV-T-02 — usage_count is the stored counter, not a recount
- **Rules:** `get_tags` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`, but `usage_count 9`.
2. A1 = account A1.
3. link of A1 to K1.

**When**
- `result = svc.get_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `[t.usage_count for t in result] == [9]`.

### ATV-T-03 — a stored tag with an empty code is still returned
- **Rules:** `get_tags` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = tag, `name "!!!"`, `tag_code ""`.

**When**
- `result = svc.get_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [K1.id]`.
2. returns: `result[0].tag_code == ""`.

### ATV-T-04 — a stored tag with an empty code passes the response schema
- **Rules:** `get_tags` R3 [BUG-1690]
- **Kind:** bug
- **Expect:** xfail BUG-1690
- **Fails today on:** Then 2 (`AccountTagResponse` refuses `""`)

**Given**
1. K1 = tag, `name "!!!"`, `tag_code ""`.

**When**
- `result = svc.get_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. schema: `AccountTagResponse.model_validate(result[0]).tag_code == ""`.

### ATV-T-05 — a stored tag with a non-ASCII code passes the response schema
- **Rules:** `get_tags` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = tag, `name "Café"`, `tag_code "café"`.

**When**
- `result = svc.get_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [K1.id]`.
2. schema: `AccountTagResponse.model_validate(result[0]).tag_code == "café"`.

### ATV-T-06 — the list neither commits nor rolls back
- **Rules:** `get_tags` R4; S4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.
2. K2 = tag, `name "Client B"`, `tag_code "client_b"`.
3. P = tag, `name "Pending"`, `tag_code "pending"` (after the commit point).
4. `K2.color = "#00FF00"` (after the commit point, not flushed).

**When**
- `result = svc.get_tags(db, workspace_id=W1.id)`, with **spies**.

**Then**
1. returns: `ids(result) == [K1.id, K2.id, P.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `K2 in db.dirty`.
5. committed: `account_tags` rows with `tag_code == "pending"`: exactly 0.

### ATV-T-07 — pass-through BUG-1482: system tags first, then name case-insensitive, then id
- **Rules:** `get_tags` R1 [BUG-1482]
- **Kind:** bug
- **Expect:** xfail BUG-1482 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no order is asked for; the system tag, built last, usually comes last)

**Given**
1. K1 = tag, `name "bravo"`, `tag_code "bravo"`.
2. K2 = tag, `name "Alpha"`, `tag_code "alpha"`.
3. K3 = tag, `name "Charlie"`, `tag_code "charlie"`.
4. KS = system tag, `name "Zeta"`, `tag_code "zeta"`.

**When**
- `result = svc.get_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [K1.id, K2.id, K3.id, KS.id]`.
2. returns: `[t.id for t in result] == [KS.id, K2.id, K1.id, K3.id]`.

### ATV-T-08 — pass-through BUG-1485: every live tag is returned, 101 of 101
- **Rules:** `get_tags` R1 [BUG-1485]
- **Kind:** bug
- **Expect:** xfail BUG-1485
- **Fails today on:** Then 1 (100 come back)

**Given**
1. 101 tags, by `add_all`: k = 0 … 100, tag, `name f"t{k:03d}"`, `tag_code f"t{k:03d}"`.

**When**
- `result = svc.get_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.

## `AccountTagService.get_system_tags`

### ATV-Y-01 — the workspace's system tags only, with the stored counter
- **Rules:** `get_system_tags` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. KZ1 = system tag, `name "Far One"`, `tag_code "far_one"`, but `workspace_id W2.id`.
2. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.
3. KS = system tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 9`.
4. KZ2 = system tag, `name "Far Two"`, `tag_code "far_two"`, but `workspace_id W2.id`.

**When**
- `result = svc.get_system_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [KS.id]`.
2. returns: `result[0].usage_count == 9`.

### ATV-Y-02 — a live system tag of the workspace is returned when there is a deleted one
- **Rules:** `get_system_tags` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. KS = system tag, `name "Supplier"`, `tag_code "supplier"`.
2. KD = system tag, `name "Utility"`, `tag_code "utility"`, but deleted.

**When**
- `result = svc.get_system_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `KS.id in [t.id for t in result]`.

### ATV-Y-03 — pass-through BUG-1483: a deleted system tag is not returned
- **Rules:** `get_system_tags` R1 [BUG-1483]
- **Kind:** bug
- **Expect:** xfail BUG-1483
- **Fails today on:** Then 1 (the deleted system tag is returned)

**Given**
1. KS = system tag, `name "Supplier"`, `tag_code "supplier"`.
2. KD = system tag, `name "Utility"`, `tag_code "utility"`, but deleted.

**When**
- `result = svc.get_system_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [KS.id]`.

### ATV-Y-04 — pass-through BUG-1482: system tags come by name, case-insensitive ascending
- **Rules:** `get_system_tags` R1 [BUG-1482]
- **Kind:** bug
- **Expect:** xfail BUG-1482 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no order is asked for; insertion order usually comes back)

**Given**
1. S1 = system tag, `name "Utility"`, `tag_code "utility"`.
2. S2 = system tag, `name "client"`, `tag_code "client"`.
3. S3 = system tag, `name "Bank"`, `tag_code "bank"`.

**When**
- `result = svc.get_system_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id, S2.id, S3.id]`.
2. returns: `[t.name for t in result] == ["Bank", "client", "Utility"]`.

### ATV-Y-05 — the list neither commits nor rolls back
- **Rules:** `get_system_tags` R2; S4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. KS = system tag, `name "Supplier"`, `tag_code "supplier"`.
2. K2 = tag, `name "Client B"`, `tag_code "client_b"`.
3. P = tag, `name "Pending"`, `tag_code "pending"` (after the commit point).
4. `K2.color = "#00FF00"` (after the commit point, not flushed).

**When**
- `result = svc.get_system_tags(db, workspace_id=W1.id)`, with **spies**.

**Then**
1. returns: `ids(result) == [KS.id]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `K2 in db.dirty`.
5. count: `account_tags` rows with `tag_code == "pending"`: exactly 1.
6. committed: `account_tags` rows with `tag_code == "pending"`: exactly 0.

## `AccountTagService.create_tag`

### ATV-C-01 — a sent tag_code in the format is used as sent
- **Rules:** `create_tag` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name="Big Supplier", tag_code="supplier_x"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "supplier_x"`.
2. committed: the new row: `tag_code == "supplier_x"`, `name == "Big Supplier"`.

### ATV-C-02 — a sent code in capitals is refused by the schema
- **Rules:** `create_tag` R1a [BUG-1693], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1693
- **Fails today on:** Then 1 (the schema builds the object)

**Given**
1. W1 has no tags.

**When**
- build `AccountTagCreate(name="Big Supplier", tag_code="SUPPLIER")` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. nothing written: nothing written.

### ATV-C-03 — a sent code with a leading space is refused, not trimmed
- **Rules:** `create_tag` R1a [BUG-1693], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1693
- **Fails today on:** Then 1 (the schema builds the object)

**Given**
1. W1 has no tags.

**When**
- build `AccountTagCreate(name="Big Supplier", tag_code=" supplier")` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. nothing written: nothing written.

### ATV-C-04 — a sent code with a hyphen is refused
- **Rules:** `create_tag` R1a [BUG-1693], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1693
- **Fails today on:** Then 1 (the schema builds the object)

**Given**
1. W1 has no tags.

**When**
- build `AccountTagCreate(name="Big Supplier", tag_code="supplier-x")` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. nothing written: nothing written.

### ATV-C-05 — a sent code with an accented letter is refused
- **Rules:** `create_tag` R1a [BUG-1693], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1693
- **Fails today on:** Then 1 (the schema builds the object)

**Given**
1. W1 has no tags.

**When**
- build `AccountTagCreate(name="Café", tag_code="café")` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. nothing written: nothing written.

### ATV-C-06 — an empty sent code stays refused
- **Rules:** `create_tag` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no tags.

**When**
- build `AccountTagCreate(name="Big Supplier", tag_code="")` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.

### ATV-C-07 — a sent code of 51 characters stays refused; 50 are accepted
- **Rules:** `create_tag` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no tags.
2. `ok = AccountTagCreate(name="Long", tag_code="a" * 50)`.

**When**
- build `AccountTagCreate(name="Long", tag_code="a" * 51)` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. schema: `ok.tag_code == "a" * 50`.

### ATV-C-08 — with no code sent, spaces become _ and digits stay
- **Rules:** `create_tag` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name="Steel Bar 2"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "steel_bar_2"`.
2. committed: the new row: `tag_code == "steel_bar_2"`.

### ATV-C-09 — with the code sent as null, other symbols are dropped
- **Rules:** `create_tag` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name="Steel-Bar", tag_code=None), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "steelbar"`.

### ATV-C-10 — a derived code drops accented letters
- **Rules:** `create_tag` R3 [BUG-1690]
- **Kind:** bug
- **Expect:** xfail BUG-1690
- **Fails today on:** Then 1 (the code is `café`)

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name="Café"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "caf"`.
2. committed: the new row: `tag_code == "caf"`.

### ATV-C-11 — a derived code with nothing left is "tag"
- **Rules:** `create_tag` R3 [BUG-1690]
- **Kind:** bug
- **Expect:** xfail BUG-1690
- **Fails today on:** Then 1 (the code is `""`)

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name="!!!"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "tag"`.

### ATV-C-12 — a derived code of a 60-letter name is cut to 50
- **Rules:** `create_tag` R3 [BUG-1690]
- **Kind:** bug
- **Expect:** xfail BUG-1690
- **Fails today on:** Then 1 (the call raises DataError: the 60-character code does not fit the column)

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name="a" * 60), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "a" * 50`.
2. committed: the new row: `tag_code == "a" * 50`.

### ATV-C-13 — a derived code of exactly 50 characters is kept whole
- **Rules:** `create_tag` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name="a" * 50), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "a" * 50`.

### ATV-C-14 — a padded name derives its code from the trimmed name
- **Rules:** `create_tag` R3 [BUG-1690]
- **Kind:** bug
- **Expect:** xfail BUG-1690
- **Fails today on:** Then 1 (the code is `_bolt_`)

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name=" Bolt "), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "bolt"`.

### ATV-C-15 — a Bengali name derives "tag"
- **Rules:** `create_tag` R3 [BUG-1690]
- **Kind:** bug
- **Expect:** xfail BUG-1690
- **Fails today on:** Then 1 (the code is `কচমল`)

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name=BN), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "tag"`.

### ATV-C-16 — the database refuses a second live tag with the same code
- **Rules:** `create_tag` R6 [BUG-1684]
- **Kind:** bug
- **Expect:** xfail BUG-1684
- **Fails today on:** Then 1 (no index: the second row is stored)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.

**When**
- insert tag, `name "Vendor Y"`, `tag_code "vendor_x"` directly (target `database`).

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `account_tags` rows with `tag_code == "vendor_x"`: exactly 1.

### ATV-C-17 — the code index leaves deleted tags out
- **Rules:** `create_tag` R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. KD = tag, `name "Old Vendor"`, `tag_code "vendor_x"`, but deleted.

**When**
- insert tag, `name "Vendor X"`, `tag_code "vendor_x"` directly, then `db.flush()` (target `database`).

**Then**
1. count: `account_tags` rows with `tag_code == "vendor_x"`: exactly 2.

### ATV-C-18 — a create that loses the code race gets the 409, one row stays
- **Rules:** `create_tag` R6 [BUG-1684], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1684
- **Author:** claude
- **Fails today on:** Then 1 (no error: no index, so a second "vendor_x" is saved)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.

**When**
- `svc.create_tag(db, tag_in=AccountTagCreate(name="Vendor Two", tag_code="vendor_x"), workspace_id=W1.id, user_id=U1.id)`, with the race simulation active.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Tag with code 'vendor_x' already exists"`.
4. count: `account_tags` rows of W1 with `tag_code == "vendor_x"`: exactly 1.
5. unchanged: unchanged(K1).
6. session: usable.

### ATV-C-19 — a sent code taken: 409, nothing written, other uncommitted changes stay
- **Rules:** `create_tag` R4, R11, Errors row 2; S3
- **Kind:** error
- **Expect:** pass

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.
2. X (after the commit point).

**When**
- `svc.create_tag(db, tag_in=AccountTagCreate(name="Vendor Two", tag_code="vendor_x"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Tag with code 'vendor_x' already exists"`.
4. count: `account_tags` rows with `name == "Vendor Two"`: exactly 0.
5. count: `account_tags` rows with `tag_code == "extra"`: exactly 1.
6. unchanged: unchanged(K1).

### ATV-C-20 — the same code in another workspace does not block
- **Rules:** `create_tag` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. KZ = tag, `name "Vendor X"`, `tag_code "vendor_x"`, but `workspace_id W2.id`.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name="Vendor X", tag_code="vendor_x"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.workspace_id == W1.id`, `result.tag_code == "vendor_x"`.
2. committed: `account_tags` rows with `tag_code == "vendor_x"`: exactly 2.

### ATV-C-21 — a deleted tag's code can be used again
- **Rules:** `create_tag` R5 [BUG-1683]
- **Kind:** bug
- **Expect:** xfail BUG-1683
- **Fails today on:** Then 1 (the call raises HTTPException 409: deleted tags are counted)

**Given**
1. KD = tag, `name "Old Vendor"`, `tag_code "vendor_x"`, but deleted.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name="Vendor X", tag_code="vendor_x"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id != KD.id`, `result.tag_code == "vendor_x"`.
2. committed: `account_tags` rows of W1 with `tag_code == "vendor_x"`: exactly 2.

### ATV-C-22 — a derived code taken gets the first free suffix
- **Rules:** `create_tag` R7 [BUG-1691]
- **Kind:** bug
- **Expect:** xfail BUG-1691
- **Fails today on:** Then 1 (the call raises HTTPException 409 `Tag with code 'steelbar' already exists`)

**Given**
1. K1 = tag, `name "Steel-Bar"`, `tag_code "steelbar"`.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name="SteelBar"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "steelbar_2"`.
2. committed: the new row: `tag_code == "steelbar_2"`, `name == "SteelBar"`.

### ATV-C-23 — the suffix skips taken ones: _2 taken gives _3
- **Rules:** `create_tag` R7 [BUG-1691]
- **Kind:** bug
- **Expect:** xfail BUG-1691
- **Fails today on:** Then 1 (the call raises HTTPException 409 `Tag with code 'steelbar' already exists`)

**Given**
1. K1 = tag, `name "Steel-Bar"`, `tag_code "steelbar"`.
2. K2 = tag, `name "Steel Bar Two"`, `tag_code "steelbar_2"`.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name="SteelBar"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "steelbar_3"`.

### ATV-C-24 — the suffixed code stays within 50: the base is cut
- **Rules:** `create_tag` R7 [BUG-1691]
- **Kind:** bug
- **Expect:** xfail BUG-1691
- **Fails today on:** Then 1 (the call raises HTTPException 409: the 50-letter code is taken)

**Given**
1. K1 = tag, `name "a" * 50`, `tag_code "a" * 50`.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name="a" * 50 + "!"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "a" * 48 + "_2"`.

### ATV-C-25 — a live name in another case is refused, with the submitted name
- **Rules:** `create_tag` R8 [BUG-1689], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1689
- **Fails today on:** Then 1 (no error: names are not checked)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_1"`.

**When**
- `svc.create_tag(db, tag_in=AccountTagCreate(name="VENDOR X", tag_code="vendor_2"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Tag with name 'VENDOR X' already exists"`.
4. nothing written: nothing written.

### ATV-C-26 — a system tag's name blocks too
- **Rules:** `create_tag` R8 [BUG-1689], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1689
- **Fails today on:** Then 1 (no error: names are not checked)

**Given**
1. KS = system tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `svc.create_tag(db, tag_in=AccountTagCreate(name="supplier", tag_code="supplier_2"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Tag with name 'supplier' already exists"`.
4. nothing written: nothing written.

### ATV-C-27 — the database refuses a second live tag with the same name ignoring case
- **Rules:** `create_tag` R8 [BUG-1689]
- **Kind:** bug
- **Expect:** xfail BUG-1689
- **Fails today on:** Then 1 (no index: the second row is stored)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_1"`.

**When**
- insert tag, `name "VENDOR X"`, `tag_code "vendor_2"` directly (target `database`).

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `account_tags` rows of W1: exactly 1.

### ATV-C-28 — the name is checked before the code
- **Rules:** `create_tag` R8 [BUG-1689], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1689
- **Fails today on:** Then 3 (the code's 409 comes instead)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.

**When**
- `svc.create_tag(db, tag_in=AccountTagCreate(name="Vendor X", tag_code="vendor_x"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Tag with name 'Vendor X' already exists"`.
4. nothing written: nothing written.

### ATV-C-29 — a padded name's 409 names the trimmed name
- **Rules:** `create_tag` R8 [BUG-1689], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1689
- **Fails today on:** Then 1 (no error: names are not checked)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_1"`.

**When**
- `svc.create_tag(db, tag_in=AccountTagCreate(name=" VENDOR X ", tag_code="vendor_2"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Tag with name 'VENDOR X' already exists"`.
4. nothing written: nothing written.

### ATV-C-30 — a name refusal leaves other uncommitted changes alone
- **Rules:** `create_tag` R8, R11 [BUG-1689]; S3
- **Kind:** bug
- **Expect:** xfail BUG-1689
- **Fails today on:** Then 1 (no error: names are not checked)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_1"`.
2. X (after the commit point).

**When**
- `svc.create_tag(db, tag_in=AccountTagCreate(name="VENDOR X", tag_code="vendor_2"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. count: `account_tags` rows with `tag_code == "extra"`: exactly 1.

### ATV-C-31 — a deleted tag's name does not block
- **Rules:** `create_tag` R8
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. KD = tag, `name "Vendor X"`, `tag_code "old_vendor"`, but deleted.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name="Vendor X", tag_code="vendor_x"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "Vendor X"`, `result.id != KD.id`.

### ATV-C-32 — another workspace's name does not block
- **Rules:** `create_tag` R8
- **Kind:** isolation
- **Expect:** pass

**Given**
1. KZ = tag, `name "Vendor X"`, `tag_code "vendor_x"`, but `workspace_id W2.id`.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name="Vendor X", tag_code="vendor_w1"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.name == "Vendor X"`, `result.workspace_id == W1.id`.

### ATV-C-33 — a whitespace-only name is refused by the schema
- **Rules:** `create_tag` R9 [BUG-1682], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1682
- **Fails today on:** Then 1 (the schema builds the object)

**Given**
1. W1 has no tags.

**When**
- build `AccountTagCreate(name="   ")` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. nothing written: nothing written.

### ATV-C-34 — a padded name is stored trimmed
- **Rules:** `create_tag` R9 [BUG-1682]
- **Kind:** bug
- **Expect:** xfail BUG-1682
- **Fails today on:** Then 2 (stored as `" Bolt "`)

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name=" Bolt ", tag_code="bolt"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.tag_code == "bolt"`.
2. committed: the new row: `name == "Bolt"`.

### ATV-C-35 — a new tag carries every given field and the fixed ones; committed and returned re-read
- **Rules:** `create_tag` R10, Returns; S1
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no tags.

**When**
- `result = svc.create_tag(db, tag_in=AccountTagCreate(name="Steel", tag_code="steel", color="#FF0000", icon="bolt", description="Metal stock"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `created_at`, `tag_code`, `name`, `usage_count`.
2. returns: `isinstance(result, AccountTag)`.
3. returns: `result.created_at is not None`, `result.created_by == U1.id`.
4. committed: the new row: `workspace_id == W1.id`, `name == "Steel"`, `tag_code == "steel"`.
5. committed: the new row: `color == "#FF0000"`, `icon == "bolt"`, `description == "Metal stock"`.
6. committed: the new row: `created_by == U1.id`, `is_system_tag is False`, `usage_count == 0`, `is_active is True`.

### ATV-C-36 — a client cannot make a system tag
- **Rules:** `create_tag` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no tags.
2. `data = AccountTagCreate.model_validate({"name": "Steel", "is_system_tag": True, "usage_count": 5, "is_active": False})`.

**When**
- `result = svc.create_tag(db, tag_in=data, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.is_system_tag is False`.
2. committed: the new row: `is_system_tag is False`, `usage_count == 0`, `is_active is True`.

### ATV-C-37 — a failing commit is rolled back and re-raised; other uncommitted changes go too
- **Rules:** `create_tag` R11; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.
2. X (after the commit point).

**When**
- `svc.create_tag(db, tag_in=AccountTagCreate(name="Steel"), workspace_id=W1.id, user_id=U1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `account_tags` rows with `name == "Steel"`: exactly 0.
4. count: `account_tags` rows with `tag_code == "extra"`: exactly 0.
5. raises: `exc.value is boom`.

### ATV-C-38 — a failing re-read after the commit leaves the tag saved
- **Rules:** `create_tag` R11; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no tags.

**When**
- `svc.create_tag(db, tag_in=AccountTagCreate(name="Steel"), workspace_id=W1.id, user_id=U1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `account_tags` rows of W1 with `name == "Steel"`: exactly 1.

### ATV-C-39 — a database error inside the write is rolled back and passed on
- **Rules:** `create_tag` R11; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. X (after the commit point).
2. `data = AccountTagCreate.model_construct(name=None, tag_code="nameless", color=None, icon=None, description=None)` (after the commit point).

**When**
- `svc.create_tag(db, tag_in=data, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23502"`.
3. count: `account_tags` rows with `tag_code == "extra"`: exactly 0.
4. nothing written: nothing written.
5. session: usable.

## `AccountTagService.update_tag`

### ATV-U-01 — another workspace's id: 404, nothing written, other uncommitted changes stay
- **Rules:** `update_tag` R1, R9, Errors row 1; S3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. KZ1 = tag, `name "Far One"`, `tag_code "far_one"`, but `workspace_id W2.id`.
2. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.
3. KZ2 = tag, `name "Far Two"`, `tag_code "far_two"`, but `workspace_id W2.id`.
4. X (after the commit point).

**When**
- `svc.update_tag(db, tag_id=KZ2.id, tag_in=AccountTagUpdate(name="Hacked"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Tag not found"`.
4. count: `account_tags` rows with `tag_code == "extra"`: exactly 1.
5. unchanged: unchanged(KZ2).

### ATV-U-02 — id 0 gets the 404
- **Rules:** `update_tag` R1, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.

**When**
- `svc.update_tag(db, tag_id=0, tag_in=AccountTagUpdate(name="Hacked"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Tag not found"`.
4. unchanged: unchanged(K1).

### ATV-U-03 — a deleted tag is not found
- **Rules:** `update_tag` R2 [BUG-1685], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1685
- **Fails today on:** Then 1 (no error: the deleted tag is edited)

**Given**
1. KD = tag, `name "Obsolete"`, `tag_code "obsolete"`, but deleted.

**When**
- `svc.update_tag(db, tag_id=KD.id, tag_in=AccountTagUpdate(name="Revived"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Tag not found"`.
4. unchanged: unchanged(KD).

### ATV-U-04 — is_active true cannot bring a deleted tag back
- **Rules:** `update_tag` R2 [BUG-1685], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1685
- **Fails today on:** Then 1 (no error: the tag is restored)

**Given**
1. KD = tag, `name "Obsolete"`, `tag_code "obsolete"`, but deleted.

**When**
- `svc.update_tag(db, tag_id=KD.id, tag_in=AccountTagUpdate(is_active=True), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. committed: re-read KD: `is_active is False`.

### ATV-U-05 — a system tag: 403, nothing written, other uncommitted changes stay
- **Rules:** `update_tag` R3, R9, Errors row 2; S3
- **Kind:** error
- **Expect:** pass

**Given**
1. KS = system tag, `name "Supplier"`, `tag_code "supplier"`.
2. X (after the commit point).

**When**
- `svc.update_tag(db, tag_id=KS.id, tag_in=AccountTagUpdate(color="#00FF00"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "System tags cannot be modified"`.
4. count: `account_tags` rows with `tag_code == "extra"`: exactly 1.
5. unchanged: unchanged(KS).

### ATV-U-06 — another workspace's system tag gets the 404, not the 403
- **Rules:** `update_tag` R1, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. KZ = system tag, `name "Far Supplier"`, `tag_code "far_supplier"`, but `workspace_id W2.id`.

**When**
- `svc.update_tag(db, tag_id=KZ.id, tag_in=AccountTagUpdate(color="#00FF00"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Tag not found"`.

### ATV-U-07 — every field sent is written; committed and returned re-read
- **Rules:** `update_tag` R4, R9, Returns; S1
- **Kind:** happy
- **Expect:** pass

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`, but `color "#000000"`, `icon "box"`, `description "Old"`, `usage_count 3`.

**When**
- `result = svc.update_tag(db, tag_id=K1.id, tag_in=AccountTagUpdate(name="Vendor Prime", color="#FF0000", icon="star", description="New"), workspace_id=W1.id)`.

**Then**
1. loaded: `name`, `color`, `tag_code`.
2. returns: `result.id == K1.id`, `result.name == "Vendor Prime"`.
3. committed: re-read K1: `name == "Vendor Prime"`, `color == "#FF0000"`, `icon == "star"`, `description == "New"`.
4. committed: re-read K1: `tag_code == "vendor_x"`, `usage_count == 3`, `is_active is True`.

### ATV-U-08 — omitted fields stay
- **Rules:** `update_tag` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`, but `color "#000000"`, `icon "box"`, `description "Old"`.

**When**
- `result = svc.update_tag(db, tag_id=K1.id, tag_in=AccountTagUpdate(color="#FF0000"), workspace_id=W1.id)`.

**Then**
1. returns: `result.color == "#FF0000"`.
2. committed: re-read K1: `name == "Vendor X"`, `icon == "box"`, `description == "Old"`, `tag_code == "vendor_x"`.

### ATV-U-09 — a tag_code in the body is ignored; the other fields apply
- **Rules:** `update_tag` R4a [BUG-1692]
- **Kind:** bug
- **Expect:** xfail BUG-1692
- **Fails today on:** Then 3 (the code is written: two live tags share `vendor_x`)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.
2. K2 = tag, `name "Other"`, `tag_code "other"`.
3. `data = AccountTagUpdate.model_validate({"name": "Other Two", "tag_code": "vendor_x"})`.

**When**
- `result = svc.update_tag(db, tag_id=K2.id, tag_in=data, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == K2.id`, `result.name == "Other Two"`.
2. committed: re-read K2: `name == "Other Two"`.
3. committed: re-read K2: `tag_code == "other"`.

### ATV-U-10 — a tag_code sent as null changes nothing
- **Rules:** `update_tag` R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.
2. `data = AccountTagUpdate.model_validate({"tag_code": None})`.

**When**
- `result = svc.update_tag(db, tag_id=K1.id, tag_in=data, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == K1.id`, `result.tag_code == "vendor_x"`.
2. unchanged: unchanged(K1).

### ATV-U-11 — a body with only a tag_code value changes nothing
- **Rules:** `update_tag` R4a [BUG-1692]
- **Kind:** bug
- **Expect:** xfail BUG-1692
- **Fails today on:** Then 2 (the code is written)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.
2. `data = AccountTagUpdate.model_validate({"tag_code": "renamed"})`.

**When**
- `result = svc.update_tag(db, tag_id=K1.id, tag_in=data, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == K1.id`.
2. unchanged: unchanged(K1).

### ATV-U-12 — explicit null clears color, icon and description
- **Rules:** `update_tag` R5 [BUG-1688]
- **Kind:** bug
- **Expect:** xfail BUG-1688
- **Fails today on:** Then 2 (every null is dropped)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`, but `color "#000000"`, `icon "box"`, `description "Old"`.

**When**
- `result = svc.update_tag(db, tag_id=K1.id, tag_in=AccountTagUpdate(color=None, icon=None, description=None), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == K1.id`.
2. committed: re-read K1: `color is None`, `icon is None`, `description is None`.
3. committed: re-read K1: `name == "Vendor X"`.

### ATV-U-13 — null for name is refused by the schema
- **Rules:** `update_tag` R5 [BUG-1688], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-1688
- **Fails today on:** Then 1 (the schema builds the object)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.

**When**
- build `AccountTagUpdate(name=None)` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. unchanged: unchanged(K1).

### ATV-U-14 — null for is_active is refused by the schema
- **Rules:** `update_tag` R5 [BUG-1688], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-1688
- **Fails today on:** Then 1 (the schema builds the object)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.

**When**
- build `AccountTagUpdate(is_active=None)` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. unchanged: unchanged(K1).

### ATV-U-15 — a rename to another live tag's name is refused
- **Rules:** `update_tag` R6 [BUG-1689], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1689
- **Fails today on:** Then 1 (no error: the rename is stored)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.
2. K2 = tag, `name "Other"`, `tag_code "other"`.

**When**
- `svc.update_tag(db, tag_id=K2.id, tag_in=AccountTagUpdate(name="vendor x"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Tag with name 'vendor x' already exists"`.
4. unchanged: unchanged(K2).

### ATV-U-16 — a padded rename's 409 names the trimmed name
- **Rules:** `update_tag` R6 [BUG-1689], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1689
- **Fails today on:** Then 1 (no error: the rename is stored)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.
2. K2 = tag, `name "Other"`, `tag_code "other"`.

**When**
- `svc.update_tag(db, tag_id=K2.id, tag_in=AccountTagUpdate(name=" vendor x "), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Tag with name 'vendor x' already exists"`.
4. unchanged: unchanged(K2).

### ATV-U-17 — a name refusal on rename leaves other uncommitted changes alone
- **Rules:** `update_tag` R6, R9 [BUG-1689]; S3
- **Kind:** bug
- **Expect:** xfail BUG-1689
- **Fails today on:** Then 1 (no error: the rename is stored)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.
2. K2 = tag, `name "Other"`, `tag_code "other"`.
3. X (after the commit point).

**When**
- `svc.update_tag(db, tag_id=K2.id, tag_in=AccountTagUpdate(name="vendor x"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. count: `account_tags` rows with `tag_code == "extra"`: exactly 1.

### ATV-U-18 — the tag's own name in another case is accepted
- **Rules:** `update_tag` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.

**When**
- `result = svc.update_tag(db, tag_id=K1.id, tag_in=AccountTagUpdate(name="VENDOR X"), workspace_id=W1.id)`.

**Then**
1. returns: `result.name == "VENDOR X"`.
2. committed: re-read K1: `name == "VENDOR X"`.

### ATV-U-19 — is_active false hides a live tag exactly as a delete
- **Rules:** `update_tag` R7
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`, but `usage_count 3`.
2. A1 = account A1.
3. L = link of A1 to K1.

**When**
- `result = svc.update_tag(db, tag_id=K1.id, tag_in=AccountTagUpdate(is_active=False), workspace_id=W1.id)`.

**Then**
1. returns: `result.is_active is False`.
2. committed: re-read K1: `is_active is False`, `usage_count == 3`, `name == "Vendor X"`, `tag_code == "vendor_x"`.
3. committed: re-read L: `tag_id == K1.id`, `account_id == A1.id`.
4. read: `svc.get_tags(db, workspace_id=W1.id) == []`.

### ATV-U-20 — a blank new name is refused by the schema
- **Rules:** `update_tag` R8 [BUG-1682]
- **Kind:** bug
- **Expect:** xfail BUG-1682
- **Fails today on:** Then 1 (the schema builds the object)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.

**When**
- build `AccountTagUpdate(name="  ")` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. unchanged: unchanged(K1).

### ATV-U-21 — a padded new name is stored trimmed
- **Rules:** `update_tag` R8 [BUG-1682]
- **Kind:** bug
- **Expect:** xfail BUG-1682
- **Fails today on:** Then 2 (stored with its spaces)

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.
2. `data = AccountTagUpdate(name="  Vendor Prime  ")`.

**When**
- `result = svc.update_tag(db, tag_id=K1.id, tag_in=data, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == K1.id`.
2. committed: re-read K1: `name == "Vendor Prime"`.

### ATV-U-22 — a failing commit is rolled back and re-raised; other uncommitted changes go too
- **Rules:** `update_tag` R9; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.
2. X (after the commit point).

**When**
- `svc.update_tag(db, tag_id=K1.id, tag_in=AccountTagUpdate(name="Steel"), workspace_id=W1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(K1).
4. count: `account_tags` rows with `tag_code == "extra"`: exactly 0.
5. raises: `exc.value is boom`.

### ATV-U-23 — a failing re-read after the commit leaves the change saved
- **Rules:** `update_tag` R9; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.

**When**
- `svc.update_tag(db, tag_id=K1.id, tag_in=AccountTagUpdate(name="Steel"), workspace_id=W1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read K1: `name == "Steel"`, `is_active is True`.

## `AccountTagService.delete_tag`

### ATV-D-01 — a live user tag gets is_active False and nothing else; committed
- **Rules:** `delete_tag` R4, Returns; S1
- **Kind:** happy
- **Expect:** pass

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`, but `usage_count 3`, `color "#000000"`.
2. A1 = account A1.
3. L = link of A1 to K1.

**When**
- `result = svc.delete_tag(db, tag_id=K1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. committed: re-read K1: `is_active is False`.
3. committed: re-read K1: `usage_count == 3`, `name == "Vendor X"`, `tag_code == "vendor_x"`, `color == "#000000"`, `is_system_tag is False`.
4. committed: re-read L: `tag_id == K1.id`, `account_id == A1.id`.
5. read: `svc.get_tags(db, workspace_id=W1.id) == []`.

### ATV-D-02 — another workspace's id: 404, nothing written, other uncommitted changes stay
- **Rules:** `delete_tag` R1, R5, Errors row 1; S3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. KZ1 = tag, `name "Far One"`, `tag_code "far_one"`, but `workspace_id W2.id`.
2. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.
3. KZ2 = tag, `name "Far Two"`, `tag_code "far_two"`, but `workspace_id W2.id`.
4. X (after the commit point).

**When**
- `svc.delete_tag(db, tag_id=KZ1.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Tag not found"`.
4. count: `account_tags` rows with `tag_code == "extra"`: exactly 1.
5. unchanged: unchanged(KZ1).

### ATV-D-03 — id 0 gets the 404
- **Rules:** `delete_tag` R1, Errors row 1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.

**When**
- `svc.delete_tag(db, tag_id=0, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Tag not found"`.
4. unchanged: unchanged(K1).

### ATV-D-04 — an already deleted tag is not found
- **Rules:** `delete_tag` R2 [BUG-1685], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1685
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

### ATV-D-05 — a system tag: 403, nothing written
- **Rules:** `delete_tag` R3, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. KS = system tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `svc.delete_tag(db, tag_id=KS.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "System tags cannot be deleted"`.
4. unchanged: unchanged(KS).

### ATV-D-06 — a system-tag refusal leaves other uncommitted changes alone
- **Rules:** `delete_tag` R3, R5; S3
- **Kind:** error
- **Expect:** pass

**Given**
1. KS = system tag, `name "Supplier"`, `tag_code "supplier"`.
2. X (after the commit point).

**When**
- `svc.delete_tag(db, tag_id=KS.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. count: `account_tags` rows with `tag_code == "extra"`: exactly 1.

### ATV-D-07 — a failing commit is rolled back and re-raised: the tag stays live
- **Rules:** `delete_tag` R5; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. K1 = tag, `name "Vendor X"`, `tag_code "vendor_x"`.
2. X (after the commit point).

**When**
- `svc.delete_tag(db, tag_id=K1.id, workspace_id=W1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(K1).
4. count: `account_tags` rows with `tag_code == "extra"`: exactly 0.
5. raises: `exc.value is boom`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| HTTP status of the `HTTPException`s; `AccountTagResponse` on the answers (`GET /account-tags/` 500 today, BUG-1690 (b)) | `/account-tags/` endpoints (integration) | The list answers 200 with a stored `""` code once fixed. |
| BUG-1682, BUG-1688, BUG-1693 — 422 at the API (400 today, BUG-461) | `POST`, `PUT /account-tags/` | Integration-only. |
| BUG-1684, BUG-1689 — the partial unique indexes; a lost race through the global handler as 409 | migration + integration | Index cards C-16, C-27 here; the 409 shape over HTTP is integration. |
| BUG-1484 — counter race | account code (account manager) | Not reached here. |
| BUG-1482, BUG-1483, BUG-1485 — the DAO's own cards | `tests/unit/dao/account_tag.cases.md` | One pass-through card each here. |
| FU-2 — the three unreachable `except HTTPException: raise` clauses | dead-code removal | No case: unreachable. |

## Spec gaps
None. Revision 1's gap 1 is closed by spec Gap log G1.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_tags` | R1 | ATV-T-01 |
| `get_tags` | R1 [BUG-1482] | ATV-T-07 |
| `get_tags` | R1 [BUG-1485] | ATV-T-08 |
| `get_tags` | R2 | ATV-T-02 |
| `get_tags` | R3 | ATV-T-03, ATV-T-05 |
| `get_tags` | R3 [BUG-1690] | ATV-T-04 |
| `get_tags` | R4 | ATV-T-06 |
| `get_system_tags` | R1 | ATV-Y-01, ATV-Y-02 |
| `get_system_tags` | R1 [BUG-1483] | ATV-Y-03 |
| `get_system_tags` | R1 [BUG-1482] | ATV-Y-04 |
| `get_system_tags` | R2 | ATV-Y-05 |
| `create_tag` | R1 | ATV-C-01 |
| `create_tag` | R1a | ATV-C-06, ATV-C-07 |
| `create_tag` | R1a [BUG-1693] | ATV-C-02, ATV-C-03, ATV-C-04, ATV-C-05 |
| `create_tag` | R2 | ATV-C-08, ATV-C-09 |
| `create_tag` | R3 | ATV-C-13 |
| `create_tag` | R3 [BUG-1690] | ATV-C-10, ATV-C-11, ATV-C-12, ATV-C-14, ATV-C-15 |
| `create_tag` | R4 | ATV-C-19, ATV-C-20 |
| `create_tag` | R5 [BUG-1683] | ATV-C-21 |
| `create_tag` | R6 | ATV-C-17 |
| `create_tag` | R6 [BUG-1684] | ATV-C-16, ATV-C-18 |
| `create_tag` | R7 [BUG-1691] | ATV-C-22, ATV-C-23, ATV-C-24 |
| `create_tag` | R8 | ATV-C-31, ATV-C-32 |
| `create_tag` | R8 [BUG-1689] | ATV-C-25, ATV-C-26, ATV-C-27, ATV-C-28, ATV-C-29, ATV-C-30 |
| `create_tag` | R9 [BUG-1682] | ATV-C-33, ATV-C-34 |
| `create_tag` | R10 | ATV-C-35, ATV-C-36 |
| `create_tag` | R11 | ATV-C-19, ATV-C-37, ATV-C-38, ATV-C-39 |
| `create_tag` | Errors row 1 | ATV-C-25, ATV-C-26, ATV-C-28, ATV-C-29 |
| `create_tag` | Errors row 2 | ATV-C-18, ATV-C-19 |
| `create_tag` | Errors row 3 | ATV-C-02, ATV-C-03, ATV-C-04, ATV-C-05, ATV-C-33 |
| `create_tag` | Returns | ATV-C-35 |
| `update_tag` | R1 | ATV-U-01, ATV-U-02, ATV-U-06 |
| `update_tag` | R2 [BUG-1685] | ATV-U-03, ATV-U-04 |
| `update_tag` | R3 | ATV-U-05, ATV-U-06 |
| `update_tag` | R4 | ATV-U-07, ATV-U-08 |
| `update_tag` | R4a | ATV-U-10 |
| `update_tag` | R4a [BUG-1692] | ATV-U-09, ATV-U-11 |
| `update_tag` | R5 [BUG-1688] | ATV-U-12, ATV-U-13, ATV-U-14 |
| `update_tag` | R6 | ATV-U-18 |
| `update_tag` | R6 [BUG-1689] | ATV-U-15, ATV-U-16, ATV-U-17 |
| `update_tag` | R7 | ATV-U-19 |
| `update_tag` | R8 [BUG-1682] | ATV-U-20, ATV-U-21 |
| `update_tag` | R9 | ATV-U-01, ATV-U-05, ATV-U-07, ATV-U-17, ATV-U-22, ATV-U-23 |
| `update_tag` | Errors row 1 | ATV-U-01, ATV-U-02, ATV-U-03, ATV-U-04 |
| `update_tag` | Errors row 2 | ATV-U-05 |
| `update_tag` | Errors row 3 | ATV-U-15, ATV-U-16 |
| `update_tag` | Errors row 4 | ATV-U-13, ATV-U-14 |
| `update_tag` | Returns | ATV-U-07 |
| `delete_tag` | R1 | ATV-D-02, ATV-D-03 |
| `delete_tag` | R2 [BUG-1685] | ATV-D-04 |
| `delete_tag` | R3 | ATV-D-05, ATV-D-06 |
| `delete_tag` | R4 | ATV-D-01 |
| `delete_tag` | R5 | ATV-D-02, ATV-D-06, ATV-D-07 |
| `delete_tag` | Errors row 1 | ATV-D-02, ATV-D-03, ATV-D-04 |
| `delete_tag` | Errors row 2 | ATV-D-05 |
| `delete_tag` | Returns | ATV-D-01 |
| Transaction rules | S1 | ATV-C-35, ATV-U-07, ATV-D-01 |
| Transaction rules | S2 | ATV-C-37, ATV-C-38, ATV-C-39, ATV-U-22, ATV-U-23, ATV-D-07 |
| Transaction rules | S3 | ATV-C-19, ATV-C-30, ATV-U-01, ATV-U-05, ATV-U-17, ATV-D-02, ATV-D-06 |
| Transaction rules | S4 | ATV-T-06, ATV-Y-05 |
