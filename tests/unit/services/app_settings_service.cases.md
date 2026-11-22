# Test cases — `app/services/app_settings_service.py`

> **Spec:** `tests/unit/services/app_settings_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — additive, from `app_settings_service.verify.md` Finding 1 (R-AS-1, surviving mutant `limit` 100 → 101). New: ASV-L-09. No existing card changed, none retired.
> **Revision:** 1 — spec Gap log G1 (the `id` tie-break is asserted on the statement only). Changed: ASV-L-06 (Then lines reordered so the first failing check is the same whether or not the query has an `ORDER BY` today; new Then 5: `ORDER BY` ends in `id`; Fails today on Then 2). Conventions: `re`. No card added or retired.
> **Counts:** 39 cases · 33 expected-to-pass · 6 expected-to-fail (bugs) · 5 deferred

## Reviewer summary
- **Per callable:** `get_settings` 9 (2 bug) · `get_by_id` 4 · `get_by_name` 4 · `create_setting` 11 (4 bug) · `update_setting` 7 · `delete_setting` 4.
- **Depth:** lighter target (skill step 1a): named on/off flags that nothing reads yet; no stock, money or order. The service owns its transaction (S1–S5) and calls the DAO directly, so each S rule gets its own card per write (S2 failing commit on all three writes) and per read (S5), and S3's failing re-read once (on create).
- **Expected-to-fail:** BUG-1524 2 (C-03, C-04), BUG-1225 2 (C-06, C-07), BUG-1525 2 (L-05 non-strict, L-06 strict SQL recorder). All other strict.
- **Notable design choices:**
  - Commit point and uncommitted-extra-row device as `department_service.cases.md`. For S4 ("not found" neither commits nor rolls back) the extra row is checked **twice**: still there after the call, gone after a test-level rollback.
  - **S5's aborted session** is asserted directly: after the `DataError` of `limit=-1`, the next statement raises (the service does not roll back a read).
  - The create path's database error is a NOT NULL violation from `name=None` via `model_construct`, independent of every bug fix here.
  - BUG-1525's tie-break by `id` cannot be shown with rows once BUG-1225 forbids equal names; the strict recorder L-06 checks that the `ORDER BY` puts the name first and ends in `id` (spec Notes, G1).
  - C-08 (same name in another workspace is stored) passes today and must keep passing after BUG-1225.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `ASV` = `app/services/app_settings_service.py`. `L` get_settings · `G` get_by_id · `N` get_by_name · `C` create_setting · `U` update_setting · `D` delete_setting.

**Actors and fixed values.**
- `svc` = the singleton `app_settings_service` (`from app.services.app_settings_service import AppSettingsService, app_settings_service`). `db` = the test's real session, always the first argument; the rest by keyword. `result` = what the When call returns.
- `AppSettings` (`app.models.app_settings`), `AppSettingsCreate`, `AppSettingsUpdate`, `AppSettingsBase` (`app.schemas.app_settings`). `PydanticValidationError` = `pydantic.ValidationError`. `IntegrityError`, `DataError`, `DBAPIError` (`sqlalchemy.exc`); `inspect`, `text` (`sqlalchemy`); `patch` (`unittest.mock`); `re` (the standard module).
- W1, W2 = two `workspaces` rows from `make_workspace`; they exist in every test. MISSING = `999999999`.

**Externals.** None is mocked.

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written, ids rising in that order.
- **setting** = `AppSettings(workspace_id=W1.id, name="feat", enabled=True)`. After "but" the card lists every column that differs. No setting exists unless the Given lists it.
- Never two rows of one workspace with names equal ignoring case and outer spaces (BUG-1225's index), except where the card is about exactly that.
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). A Given line marked "(after the commit point)" runs after it, is flushed, and stays uncommitted.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the number of `app_settings` rows (all workspaces) equals its value at the commit point.
- `count:` lines count `app_settings` rows with a fresh query, with the filter stated. **ids(x)** = `sorted(r.id for r in x)`.
- `loaded:` lines run on the returned object first: each column named is not in `inspect(result).unloaded`.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `schema:` lines check a model or schema class itself, not a row.
- `session:` lines check `db` itself: "usable" = `db.execute(text("SELECT 1")).scalar() == 1`; "aborted" = `db.execute(text("SELECT 1"))` raises `DBAPIError` (wrap in `pytest.raises`).
- `raises: <Type>`: plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint. Further `raises:` lines assert on `exc.value` after the block. A schema card wraps only the schema's construction (target `schema`).
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When; `mock called:` lines check `cm`, `rb` after it.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the one `SELECT` from `app_settings`; `order_part` = the text of `sql` after `ORDER BY` and before `LIMIT` (`""` when there is none). A `statement:` line is a check on these.

**xfail cards.** Write the call and checks as shown. Strict unless the Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Race simulations.** None in this module.

## `AppSettingsService.get_settings`

### ASV-L-01 — only the workspace's settings are listed
- **Rules:** `get_settings` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = setting, but `workspace_id W2.id`, `name "early"`.
2. A = setting.
3. B = setting, but `name "beta"`.
4. Z2 = setting, but `workspace_id W2.id`, `name "late"`.

**When**
- `result = svc.get_settings(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id, B.id]`.

### ASV-L-02 — limit=0 gives an empty list
- **Rules:** `get_settings` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.
2. B = setting, but `name "beta"`.

**When**
- `result = svc.get_settings(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### ASV-L-03 — limit=1 gives one setting
- **Rules:** `get_settings` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.
2. B = setting, but `name "beta"`.

**When**
- `result = svc.get_settings(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### ASV-L-04 — skip=1 with limit=1000 gives the rest
- **Rules:** `get_settings` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.
2. B = setting, but `name "beta"`.
3. C = setting, but `name "gamma"`.

**When**
- `result = svc.get_settings(db, workspace_id=W1.id, skip=1, limit=1000)`.

**Then**
1. returns: `len(result) == 2`.

### ASV-L-05 — settings come by name, case-insensitive ascending
- **Rules:** `get_settings` R2 [BUG-1525]
- **Kind:** bug
- **Expect:** xfail BUG-1525 (non-strict)
- **Fails today on:** Then 2 (no name order; insertion order usually comes back)

**Given**
1. Z = setting, but `name "zeta"`.
2. A = setting, but `name "Alpha"`.
3. B = setting, but `name "beta"`.

**When**
- `result = svc.get_settings(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [Z.id, A.id, B.id]`.
2. returns: `[r.name for r in result] == ["Alpha", "beta", "zeta"]`.

### ASV-L-06 — the query orders by lower(name), then id last, before the page
- **Rules:** `get_settings` R2 [BUG-1525]
- **Kind:** bug
- **Expect:** xfail BUG-1525
- **Fails today on:** Then 2 (the query does not order by name: `order_part` has no `lower(`)

**Given**
1. A = setting.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = svc.get_settings(db, workspace_id=W1.id, skip=0, limit=10)`.

**Then**
1. returns: `[r.id for r in result] == [A.id]`.
2. statement: `"lower(" in order_part.lower()`.
3. statement: `"ORDER BY" in sql`.
4. statement: `order_part.lower().index("name") < order_part.lower().index(".id")`.
5. statement: `re.search(r"\.id(\s+asc)?\s*$", order_part, re.IGNORECASE) is not None`.
6. statement: `sql.index("ORDER BY") < sql.index("LIMIT")`.

### ASV-L-07 — a negative limit raises DataError and leaves the session aborted
- **Rules:** `get_settings` R3, Errors; S5
- **Kind:** error
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `svc.get_settings(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. session: aborted.

### ASV-L-08 — the list neither commits nor rolls back
- **Rules:** `get_settings` R3; S5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = setting.
2. B = setting, but `workspace_id W2.id`, `name "other"`.
3. P = setting, but `name "pending"` (after the commit point).
4. `B.enabled = False` (after the commit point, not flushed).

**When**
- `result = svc.get_settings(db, workspace_id=W1.id)`, with **spies**.

**Then**
1. returns: `ids(result) == sorted([A.id, P.id])`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `B in db.dirty`.
5. committed: `app_settings` rows with `name == "pending"`: exactly 0.

### ASV-L-09 — with the default limit 101 settings give 100
- **Rules:** `get_settings` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 settings, by `add_all`: k = 0 … 100, setting, but `name f"s{k:03d}"`.

**When**
- `result = svc.get_settings(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

## `AppSettingsService.get_by_id`

### ASV-G-01 — the setting of that id in that workspace is returned
- **Rules:** `get_by_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = setting, but `enabled False`.

**When**
- `result = svc.get_by_id(db, setting_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, AppSettings)`.
2. returns: `result.id == A.id`, `result.name == "feat"`, `result.enabled is False`.

### ASV-G-02 — another workspace's id returns None
- **Rules:** `get_by_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = setting.
2. Z = setting, but `workspace_id W2.id`.

**When**
- `result = svc.get_by_id(db, setting_id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ASV-G-03 — id 0 returns None, no error
- **Rules:** `get_by_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = svc.get_by_id(db, setting_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ASV-G-04 — the read neither commits nor rolls back
- **Rules:** `get_by_id` R3; S5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = setting.
2. B = setting, but `name "other"`.
3. P = setting, but `name "pending"` (after the commit point).
4. `B.enabled = False` (after the commit point, not flushed).

**When**
- `result = svc.get_by_id(db, setting_id=MISSING, workspace_id=W1.id)`, with **spies**.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `B in db.dirty`.
5. committed: `app_settings` rows with `name == "pending"`: exactly 0.

## `AppSettingsService.get_by_name`

### ASV-N-01 — an exact name returns the workspace's setting
- **Rules:** `get_by_name` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z = setting, but `workspace_id W2.id`.
2. A = setting.

**When**
- `result = svc.get_by_name(db, name="feat", workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### ASV-N-02 — the name in capitals finds nothing
- **Rules:** `get_by_name` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = svc.get_by_name(db, name="FEAT", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ASV-N-03 — another workspace's name finds nothing
- **Rules:** `get_by_name` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = setting, but `workspace_id W2.id`, `name "beta"`.
2. A = setting.

**When**
- `result = svc.get_by_name(db, name="beta", workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ASV-N-04 — the read neither commits nor rolls back
- **Rules:** `get_by_name` R2; S5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = setting.
2. B = setting, but `name "other"`.
3. P = setting, but `name "pending"` (after the commit point).
4. `B.enabled = False` (after the commit point, not flushed).

**When**
- `result = svc.get_by_name(db, name="feat", workspace_id=W1.id)`, with **spies**.

**Then**
1. returns: `result.id == A.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `B in db.dirty`.
5. committed: `app_settings` rows with `name == "pending"`: exactly 0.

## `AppSettingsService.create_setting`

### ASV-C-01 — a new setting is committed and returned re-read
- **Rules:** `create_setting` R1; S1, S3
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no settings.

**When**
- `result = svc.create_setting(db, setting_in=AppSettingsCreate(name="feat", enabled=False), workspace_id=W1.id)`.

**Then**
1. loaded: `id`, `name`, `enabled`, `workspace_id`.
2. returns: `isinstance(result, AppSettings)`.
3. returns: `result.id is not None`, `result.name == "feat"`, `result.enabled is False`, `result.workspace_id == W1.id`.
4. committed: the row with `id == result.id` exists: `name == "feat"`, `enabled is False`, `workspace_id == W1.id`.
5. committed: `app_settings` rows of W1: exactly 1.

### ASV-C-02 — no acting user is recorded: the table has no such column
- **Rules:** `create_setting` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no settings.

**When**
- `result = svc.create_setting(db, setting_in=AppSettingsCreate(name="feat", enabled=True), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. schema: `not any(c.name in ("created_by", "updated_by", "user_id") for c in AppSettings.__table__.columns)`.

### ASV-C-03 — a whitespace-only name is refused by the schema
- **Rules:** `create_setting` R3 [BUG-1524], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1524
- **Fails today on:** Then 1 (the schema builds the object)

**Given**
1. W1 has no settings.

**When**
- build `AppSettingsCreate(name="   ", enabled=True)` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. nothing written: nothing written.

### ASV-C-04 — a padded name is stored trimmed
- **Rules:** `create_setting` R3 [BUG-1524]
- **Kind:** bug
- **Expect:** xfail BUG-1524
- **Fails today on:** Then 2 (stored as `" Feat "`)

**Given**
1. W1 has no settings.
2. `data = AppSettingsCreate(name=" Feat ", enabled=True)`.

**When**
- `result = svc.create_setting(db, setting_in=data, workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: the row with `id == result.id` has `name == "Feat"`.

### ASV-C-05 — the base schema still reads a blank name
- **Rules:** `create_setting` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no settings.

**When**
- `data = AppSettingsBase(name="   ", enabled=True)` (target `schema`).

**Then**
1. returns: `data.name == "   "`.

### ASV-C-06 — a name already used in the workspace is refused by the database after the rollback
- **Rules:** `create_setting` R4 [BUG-1225], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1225
- **Fails today on:** Then 1 (no error is raised: a second "feat" is stored)

**Given**
1. A = setting.

**When**
- `svc.create_setting(db, setting_in=AppSettingsCreate(name="feat", enabled=False), workspace_id=W1.id)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `app_settings` rows of W1: exactly 1.
4. unchanged: unchanged(A).
5. session: usable.

### ASV-C-07 — the same name in other case and with spaces collides too
- **Rules:** `create_setting` R4 [BUG-1225], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1225
- **Fails today on:** Then 1 (no error is raised: `" FEAT "` is stored)

**Given**
1. A = setting.

**When**
- `svc.create_setting(db, setting_in=AppSettingsCreate(name=" FEAT ", enabled=False), workspace_id=W1.id)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `app_settings` rows of W1: exactly 1.

### ASV-C-08 — the same name in another workspace is stored
- **Rules:** `create_setting` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = setting, but `workspace_id W2.id`.

**When**
- `result = svc.create_setting(db, setting_in=AppSettingsCreate(name="feat", enabled=True), workspace_id=W1.id)`.

**Then**
1. returns: `result.workspace_id == W1.id`.
2. committed: `app_settings` rows with `name == "feat"`: exactly 2.
3. committed: re-read Z: `workspace_id == W2.id`, `name == "feat"`.

### ASV-C-09 — a failing commit is rolled back and re-raised; other uncommitted changes go too
- **Rules:** `create_setting` R5; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = setting, but `name "other"`.
2. X = setting, but `name "extra"` (after the commit point).

**When**
- `svc.create_setting(db, setting_in=AppSettingsCreate(name="feat", enabled=True), workspace_id=W1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `app_settings` rows with `name == "feat"`: exactly 0.
4. count: `app_settings` rows with `name == "extra"`: exactly 0.
5. nothing written: nothing written.

### ASV-C-10 — a failing re-read after the commit leaves the setting saved
- **Rules:** `create_setting` R5; S3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no settings.

**When**
- `svc.create_setting(db, setting_in=AppSettingsCreate(name="feat", enabled=True), workspace_id=W1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `app_settings` rows of W1 with `name == "feat"`: exactly 1.

### ASV-C-11 — a database error at the flush is rolled back and passed on; the session is usable
- **Rules:** `create_setting` R5, Errors; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = setting, but `name "other"`.
2. X = setting, but `name "extra"` (after the commit point).
3. `data = AppSettingsCreate.model_construct(name=None, enabled=True)`.

**When**
- `svc.create_setting(db, setting_in=data, workspace_id=W1.id)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23502"`.
3. count: `app_settings` rows with `name == "extra"`: exactly 0.
4. nothing written: nothing written.
5. session: usable.

## `AppSettingsService.update_setting`

### ASV-U-01 — enabled is written, committed and returned re-read
- **Rules:** `update_setting` R2; S1, S3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = svc.update_setting(db, setting_id=A.id, setting_in=AppSettingsUpdate(enabled=False), workspace_id=W1.id)`.

**Then**
1. loaded: `enabled`, `name`.
2. returns: `result.id == A.id`, `result.enabled is False`.
3. committed: re-read A: `enabled is False`, `name == "feat"`.

### ASV-U-02 — another workspace's id returns None, writes nothing, neither commits nor rolls back
- **Rules:** `update_setting` R1; S4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = setting.
2. Z = setting, but `workspace_id W2.id`.
3. X = setting, but `name "extra"` (after the commit point).

**When**
- `result = svc.update_setting(db, setting_id=Z.id, setting_in=AppSettingsUpdate(enabled=False), workspace_id=W1.id)`, with **spies**.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: `app_settings` rows with `name == "extra"`: exactly 1.
5. unchanged: unchanged(Z).
6. committed: `app_settings` rows with `name == "extra"`: exactly 0.

### ASV-U-03 — id 0 returns None
- **Rules:** `update_setting` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = svc.update_setting(db, setting_id=0, setting_in=AppSettingsUpdate(enabled=False), workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(A).

### ASV-U-04 — enabled omitted leaves the setting unchanged and returns it
- **Rules:** `update_setting` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = svc.update_setting(db, setting_id=A.id, setting_in=AppSettingsUpdate(), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`, `result.enabled is True`.
2. unchanged: unchanged(A).

### ASV-U-05 — enabled null leaves the setting unchanged and returns it
- **Rules:** `update_setting` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = svc.update_setting(db, setting_id=A.id, setting_in=AppSettingsUpdate(enabled=None), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`, `result.enabled is True`.
2. unchanged: unchanged(A).

### ASV-U-06 — a name in the body is ignored
- **Rules:** `update_setting` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.
2. `data = AppSettingsUpdate.model_validate({"name": "renamed", "enabled": False})`.

**When**
- `result = svc.update_setting(db, setting_id=A.id, setting_in=data, workspace_id=W1.id)`.

**Then**
1. returns: `result.enabled is False`.
2. committed: re-read A: `name == "feat"`, `enabled is False`.

### ASV-U-07 — a failing commit is rolled back and re-raised; other uncommitted changes go too
- **Rules:** `update_setting` R4; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = setting.
2. X = setting, but `name "extra"` (after the commit point).

**When**
- `svc.update_setting(db, setting_id=A.id, setting_in=AppSettingsUpdate(enabled=False), workspace_id=W1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(A).
4. count: `app_settings` rows with `name == "extra"`: exactly 0.

## `AppSettingsService.delete_setting`

### ASV-D-01 — a found setting is hard-deleted and committed; True is returned
- **Rules:** `delete_setting` R2; S1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = setting.
2. B = setting, but `name "other"`.
3. `a_id = A.id`.

**When**
- `result = svc.delete_setting(db, setting_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. committed: `app_settings` rows with `id == a_id`: exactly 0.
3. committed: re-read B: `name == "other"`.

### ASV-D-02 — another workspace's id returns False; its row stays; neither commit nor rollback
- **Rules:** `delete_setting` R1; S4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = setting.
2. Z = setting, but `workspace_id W2.id`.
3. X = setting, but `name "extra"` (after the commit point).

**When**
- `result = svc.delete_setting(db, setting_id=Z.id, workspace_id=W1.id)`, with **spies**.

**Then**
1. returns: `result is False`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: `app_settings` rows with `name == "extra"`: exactly 1.
5. unchanged: unchanged(Z).
6. committed: `app_settings` rows with `name == "extra"`: exactly 0.

### ASV-D-03 — id 0 returns False
- **Rules:** `delete_setting` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = setting.

**When**
- `result = svc.delete_setting(db, setting_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. unchanged: unchanged(A).

### ASV-D-04 — a failing commit is rolled back and re-raised: the setting stays
- **Rules:** `delete_setting` R3; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = setting.
2. X = setting, but `name "extra"` (after the commit point).

**When**
- `svc.delete_setting(db, setting_id=A.id, workspace_id=W1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(A).
4. count: `app_settings` rows with `name == "extra"`: exactly 0.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| 404 `{"detail": "App setting not found"}` made of `None` / `False` | `/app-settings/` endpoints (integration) | Integration-only. |
| BUG-1217 — `GET /app-settings/` accepts `limit <= 0` (HR-7) | endpoint | Endpoint bounds. |
| BUG-1524 / BUG-461 — schema errors answer 422 | `POST /app-settings/` | Integration-only. |
| BUG-1225 — the 409 through the global `IntegrityError` handler; the index itself | migration + handler (integration); `tests/unit/dao/app_settings.cases.md` | The index on the normalised name. |
| `app_settings_service` singleton | none (no logic) | Entry point of every card. |

## Spec gaps
None. Revision 0's gap 1 is closed by spec Gap log G1.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_settings` | R1 | ASV-L-01, ASV-L-02, ASV-L-03, ASV-L-04, ASV-L-09 |
| `get_settings` | R2 [BUG-1525] | ASV-L-05, ASV-L-06 |
| `get_settings` | R3 | ASV-L-07, ASV-L-08 |
| `get_settings` | Errors | ASV-L-07 |
| `get_by_id` | R1 | ASV-G-01 |
| `get_by_id` | R2 | ASV-G-02, ASV-G-03 |
| `get_by_id` | R3 | ASV-G-04 |
| `get_by_name` | R1 | ASV-N-01, ASV-N-02, ASV-N-03 |
| `get_by_name` | R2 | ASV-N-04 |
| `create_setting` | R1 | ASV-C-01 |
| `create_setting` | R2 | ASV-C-02 |
| `create_setting` | R3 | ASV-C-05 |
| `create_setting` | R3 [BUG-1524] | ASV-C-03, ASV-C-04 |
| `create_setting` | R4 | ASV-C-08 |
| `create_setting` | R4 [BUG-1225] | ASV-C-06, ASV-C-07 |
| `create_setting` | R5 | ASV-C-09, ASV-C-10, ASV-C-11 |
| `create_setting` | Errors | ASV-C-03, ASV-C-06, ASV-C-07, ASV-C-11 |
| `update_setting` | R1 | ASV-U-02, ASV-U-03 |
| `update_setting` | R2 | ASV-U-01 |
| `update_setting` | R3 | ASV-U-04, ASV-U-05, ASV-U-06 |
| `update_setting` | R4 | ASV-U-07; ASV-C-10 (S3's failing re-read, once per service) |
| `delete_setting` | R1 | ASV-D-02, ASV-D-03 |
| `delete_setting` | R2 | ASV-D-01 |
| `delete_setting` | R3 | ASV-D-04 |
| Transaction rules | S1 | ASV-C-01, ASV-U-01, ASV-D-01 |
| Transaction rules | S2 | ASV-C-09, ASV-C-11, ASV-U-07, ASV-D-04 |
| Transaction rules | S3 | ASV-C-01, ASV-C-10, ASV-U-01 |
| Transaction rules | S4 | ASV-U-02, ASV-D-02 |
| Transaction rules | S5 | ASV-L-07, ASV-L-08, ASV-G-04, ASV-N-04 |
