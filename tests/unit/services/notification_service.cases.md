# Test cases — `app/services/notification_service.py`

> **Spec:** `tests/unit/services/notification_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — additive, from `notification_service.verify.md` (R-NT-1). New: NSV-F-10 (no commit or rollback on a database error in `fan_out_mentions`). No existing card changed, none retired.
> **Revision:** 1 — spec Gap log G1 (BUG-1534's `workspace_id` is required, no default), G2 (the update fails by patching `notification_dao.mark_read`), G3 (`mark_read` R3 restated: loaded rows read `True` after the commit). New: NSV-M-10 (R3), NSV-M-11 (R4, failing update). Changed: Conventions (DAO patch; BUG-1534 note naming the 13 preview cards that gain `workspace_id=W1.id` when the fix lands), Reviewer summary. No existing card changed, none retired. (NSV-M-05 was never published and stays unused.)
> **Counts:** 47 cases · 39 expected-to-pass · 8 expected-to-fail (bugs) · 4 deferred

## Reviewer summary
- **Per callable:** `humanize_mention_preview` 17 (4 bug) · `_active_workspace_member_ids` 3 · `list_for_user` 7 (1 bug) · `mark_read` 10 (2 bug) · `fan_out_mentions` 10 (1 bug).
- **Depth:** lighter target (skill step 1a): an inbox and a text mapper; no stock, money or order. The preview mapper has real decisions (cut, token pattern, fallback, workspace scope), so each rule and each named example gets a card; the token cut is tested on both sides. Lists and marks pass through the DAO: one card per argument that must reach it, one pass-through per DAO bug (BUG-1412 non-strict, BUG-1413, BUG-1414 strict).
- **Expected-to-fail:** BUG-1534 3 (H-09, H-10, H-11), BUG-1536 1 (H-14), BUG-1535 1 (F-04), pass-through BUG-1412 1 (L-06, non-strict), BUG-1413 1 (M-08), BUG-1414 1 (M-07).
- **Notable design choices:**
  - Regression split for BUG-1534: today any profile is named, so a suspended member being named (H-12) holds today and after the fix; it is a pass card without the new parameter. The outsider and no-membership cards are xfail with the new parameter.
  - `mark_read` commits but never rolls back (R4): M-06 patches a failing commit and checks the rollback spy was **not** called, and that nothing was saved after the test's own rollback.
  - `fan_out_mentions` order is not specified (R7): its cards compare sets of recipients, never row order or ids.
  - `fan_out_mentions`' database error (F-09) is an unknown `actor_user_id` (FK to `profiles`, notification DAO spec), wrapped in a savepoint because the function does not roll back.
  - `mark_read` R4 has both halves: a failing commit (M-06) and a failing update by patching `notification_dao.mark_read` (M-11, spec G2); both check that no rollback ran. R3 (M-10) checks the loaded row reads `True` after the service's commit (spec G3).
- **Needs a decision:** None. When BUG-1534 is fixed, the 13 passing preview cards gain `workspace_id=W1.id` (Conventions, spec G1).

## Conventions for this module

**IDs.** `NSV` = `app/services/notification_service.py`. `H` humanize_mention_preview · `A` _active_workspace_member_ids · `L` list_for_user · `M` mark_read · `F` fan_out_mentions.

**Actors and fixed values.**
- `svc` = the singleton `notification_service`; `humanize_mention_preview`, `_active_workspace_member_ids` the module functions (`from app.services.notification_service import NotificationService, notification_service, humanize_mention_preview, _active_workspace_member_ids`). `db` = the test's real session, always the first argument; the rest by keyword. `result` = what the When call returns; for `list_for_user` it is the tuple: `result[0]` items, `result[1]` total, `result[2]` unread count.
- `Notification` (`app.models.notification`), `WorkspaceMember` (`app.models.workspace_member`), `MarkReadRequest` (`app.schemas.notification`), `notification_dao` (`app.dao.notification`). `IntegrityError`, `DataError` (`sqlalchemy.exc`); `text` (`sqlalchemy`); `patch` (`unittest.mock`).
- MISSING = `999999999`. NOW = `datetime(2026, 3, 5, 17, 0, 0)` (naive). T2 = `datetime(2026, 3, 2, 9, 0, 0, tzinfo=timezone.utc)`. EARLY = `datetime(2026, 3, 1, 8, 0, 0, tzinfo=timezone.utc)`.
- **bn(n)** = `"".join(chr(0x09E6 + int(c)) for c in str(n))`: the number n in Bengali digits.

**Externals.** None is mocked, except the **clock patch** on the card that names it: `patch("app.dao.notification.utcnow", return_value=NOW)` active during the When; and the **failing update** on NSV-M-11 (spec `mark_read` R4): `patch.object(notification_dao, "mark_read", side_effect=RuntimeError("boom"))`, combined with **spies**, inside `pytest.raises(RuntimeError)`.

**BUG-1534 note.** `workspace_id` becomes a required parameter of `humanize_mention_preview` with the fix (no default). The 13 preview cards that pass today (H-01 … H-08, H-12, H-13, H-15, H-16, H-17) call without it, as it does not exist yet; when the fix lands each gains `workspace_id=W1.id`, with no other change.

**Standing rows.** In every test, no Given line needed, in this order: W1, W2 = `make_workspace(db)`. Profiles from `make_profile(db, name=…)`: UA `"Ann"`, UB `"Bob"`, US `"Sue"`, UI `"Ivy"`, UO `"Otto"`, UN `"Nora"`. Memberships `WorkspaceMember(workspace_id=…, user_id=…, role="member", status=…)`: UA, UB `"active"` in W1; US `"suspended"` in W1; UI `"invited"` in W1; UO `"active"` in W2. UN has no membership. No notification exists unless a Given line builds it.

**Given rows.** Built directly, flushed one at a time in the order written, ids rising in that order. A Given line written as code is a step to run exactly.
- **note** = `Notification(workspace_id=W1.id, recipient_user_id=UA.id, actor_user_id=UB.id, notification_type="mention", entity_type="purchase_order", entity_id=1, source_type="discussion", source_id=1)`; `is_read`, `read_at`, `created_at` not passed unless listed after "but". A read note is `is_read True`, `read_at EARLY`.
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). A Given line marked "(after the commit point)" runs after it, is flushed, and stays uncommitted.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **idset(items)** = `{r.id for r in items}`. **mentions** = a fresh SELECT of `notifications` of W1 with `notification_type == "mention"` and `source_id == 77`.
- **utc_read(X)** = `db.execute(text("SELECT read_at AT TIME ZONE 'UTC' FROM notifications WHERE id = :id"), {"id": X.id}).scalar()`.
- **nothing written** = the number of `notifications` rows equals its value at the commit point.
- `count:` lines count with a fresh query, with the filter stated.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `session:` lines check `db` or a loaded object directly, before any expire or refresh.
- `raises: <Type>`: `with pytest.raises(<Type>) as exc:` around the call. A database error from `list_for_user` or `fan_out_mentions` is wrapped as `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call (neither rolls back).
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `selects` = every recorded `SELECT`; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**xfail cards.** Write the call and checks as shown, also when a parameter does not exist yet. Strict unless the Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Race simulations.** None in this module.

## `humanize_mention_preview`

### NSV-H-01 — a token cut by the limit stays as cut
- **Rules:** `humanize_mention_preview` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No notification exists.

**When**
- `result = humanize_mention_preview(db, message="x" * 197 + "@[5]")`.

**Then**
1. returns: `result == "x" * 197 + "@[5"`.

### NSV-H-02 — a token that just fits is replaced, so the text grows past the limit
- **Rules:** `humanize_mention_preview` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `tok = f"@[{UA.id}]"`.

**When**
- `result = humanize_mention_preview(db, message="x" * (200 - len(tok)) + tok)`.

**Then**
1. returns: `result == "x" * (200 - len(tok)) + "@Ann"`.

### NSV-H-03 — max_len=5 cuts the text to five characters
- **Rules:** `humanize_mention_preview` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No notification exists.

**When**
- `result = humanize_mention_preview(db, message="abcdefgh", max_len=5)`.

**Then**
1. returns: `result == "abcde"`.

### NSV-H-04 — an empty message gives an empty text
- **Rules:** `humanize_mention_preview` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No notification exists.

**When**
- `result = humanize_mention_preview(db, message="")`.

**Then**
1. returns: `result == ""`.

### NSV-H-05 — a text without a token is returned unchanged and no profile is read
- **Rules:** `humanize_mention_preview` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A recorder for the SQL statements the session sends during the When.

**When**
- `result = humanize_mention_preview(db, message="Please check the press @ 5")`.

**Then**
1. returns: `result == "Please check the press @ 5"`.
2. statement: `selects == []`.

### NSV-H-06 — a known profile is named, and the same id twice is replaced twice
- **Rules:** `humanize_mention_preview` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. `m = f"hi @[{UA.id}] and @[{UB.id}] and @[{UA.id}]"`.

**When**
- `result = humanize_mention_preview(db, message=m)`.

**Then**
1. returns: `result == "hi @Ann and @Bob and @Ann"`.

### NSV-H-07 — leading zeros are read as the number
- **Rules:** `humanize_mention_preview` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `m = f"@[00{UA.id}]"`.

**When**
- `result = humanize_mention_preview(db, message=m)`.

**Then**
1. returns: `result == "@Ann"`.

### NSV-H-08 — an id with no profile becomes @User <id>
- **Rules:** `humanize_mention_preview` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. No notification exists.

**When**
- `result = humanize_mention_preview(db, message="ping @[999999999]")`.

**Then**
1. returns: `result == "ping @User 999999999"`.

### NSV-H-09 — a member of another workspace only is not named
- **Rules:** `humanize_mention_preview` R5 [BUG-1534]
- **Kind:** bug
- **Expect:** xfail BUG-1534
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter)

**Given**
1. `m = f"@[{UO.id}]"`.

**When**
- `result = humanize_mention_preview(db, message=m, workspace_id=W1.id)`.

**Then**
1. returns: `result == f"@User {UO.id}"`.

### NSV-H-10 — a profile with no membership is not named
- **Rules:** `humanize_mention_preview` R5 [BUG-1534]
- **Kind:** bug
- **Expect:** xfail BUG-1534
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter)

**Given**
1. `m = f"@[{UN.id}]"`.

**When**
- `result = humanize_mention_preview(db, message=m, workspace_id=W1.id)`.

**Then**
1. returns: `result == f"@User {UN.id}"`.

### NSV-H-11 — with the workspace given, a member in any status is named
- **Rules:** `humanize_mention_preview` R5 [BUG-1534]
- **Kind:** bug
- **Expect:** xfail BUG-1534
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter)

**Given**
1. `m = f"@[{US.id}] @[{UI.id}] @[{UA.id}]"`.

**When**
- `result = humanize_mention_preview(db, message=m, workspace_id=W1.id)`.

**Then**
1. returns: `result == "@Sue @Ivy @Ann"`.

### NSV-H-12 — a suspended member is named
- **Rules:** `humanize_mention_preview` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `m = f"@[{US.id}]"`.

**When**
- `result = humanize_mention_preview(db, message=m)`.

**Then**
1. returns: `result == "@Sue"`.

### NSV-H-13 — text that only looks like a token is left as typed
- **Rules:** `humanize_mention_preview` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No notification exists.

**When**
- `result = humanize_mention_preview(db, message="@[abc] @[] @[ 1] @[-1]")`.

**Then**
1. returns: `result == "@[abc] @[] @[ 1] @[-1]"`.

### NSV-H-14 — Bengali digits make no token
- **Rules:** `humanize_mention_preview` R7 [BUG-1536]
- **Kind:** bug
- **Expect:** xfail BUG-1536
- **Fails today on:** Then 1 (read as the number: `@Ann`)

**Given**
1. `m = "@[" + bn(UA.id) + "]"`.

**When**
- `result = humanize_mention_preview(db, message=m)`.

**Then**
1. returns: `result == m`.

### NSV-H-15 — a superscript digit makes no token
- **Rules:** `humanize_mention_preview` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No notification exists.

**When**
- `result = humanize_mention_preview(db, message="@[²]")`.

**Then**
1. returns: `result == "@[²]"`.

### NSV-H-16 — ASCII digits still make a token
- **Rules:** `humanize_mention_preview` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. `m = f"@[{UB.id}]"`.

**When**
- `result = humanize_mention_preview(db, message=m)`.

**Then**
1. returns: `result == "@Bob"`.

### NSV-H-17 — nothing is written
- **Rules:** `humanize_mention_preview` R8
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = note (after the commit point).
2. `m = f"@[{UA.id}]"`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = humanize_mention_preview(db, message=m)`.

**Then**
1. returns: `result == "@Ann"`.
2. statement: `written == []`.
3. committed: `notifications` rows: exactly 0.

## `_active_workspace_member_ids`

### NSV-A-01 — the set of the workspace's active members
- **Rules:** `_active_workspace_member_ids` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No extra rows.

**When**
- `result = _active_workspace_member_ids(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, set)`.
2. returns: `result == {UA.id, UB.id}`.

### NSV-A-02 — status must be exactly "active"
- **Rules:** `_active_workspace_member_ids` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. UC = `make_profile(db, name="Cal")`.
2. `WorkspaceMember(workspace_id=W1.id, user_id=UC.id, role="member", status="Active")`.

**When**
- `result = _active_workspace_member_ids(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == {UA.id, UB.id}`.

### NSV-A-03 — no cap: 101 more active members are all in the set
- **Rules:** `_active_workspace_member_ids` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 profiles, k = 1 … 101, `make_profile(db, name=f"M{k}")`, each with `WorkspaceMember(workspace_id=W1.id, user_id=<its id>, role="member", status="active")`.

**When**
- `result = _active_workspace_member_ids(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 103`.

## `NotificationService.list_for_user`

### NSV-L-01 — the user's notifications of the workspace, with total and unread count
- **Rules:** `list_for_user` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = note.
2. B = note, but `is_read True`, `read_at EARLY`.
3. C = note, but `recipient_user_id UB.id`.
4. Z = note, but `workspace_id W2.id`.

**When**
- `result = svc.list_for_user(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `isinstance(result, tuple)`, `len(result) == 3`.
2. returns: `idset(result[0]) == {A.id, B.id}`.
3. returns: `result[1] == 2`, `result[2] == 1`.

### NSV-L-02 — unread_only reaches the DAO
- **Rules:** `list_for_user` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = note.
2. B = note, but `is_read True`, `read_at EARLY`.

**When**
- `result = svc.list_for_user(db, workspace_id=W1.id, user_id=UA.id, unread_only=True)`.

**Then**
1. returns: `idset(result[0]) == {A.id}`.

### NSV-L-03 — with the defaults 51 notifications give a page of 50
- **Rules:** `list_for_user` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 notes, by `add_all`.

**When**
- `result = svc.list_for_user(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `len(result[0]) == 50`.
2. returns: `result[1] == 51`.

### NSV-L-04 — skip and limit reach the DAO
- **Rules:** `list_for_user` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 3 notes, by `add_all`.

**When**
- `result = svc.list_for_user(db, workspace_id=W1.id, user_id=UA.id, skip=2, limit=1000)`.

**Then**
1. returns: `len(result[0]) == 1`.
2. returns: `result[1] == 3`.

### NSV-L-05 — nothing is written, committed or rolled back
- **Rules:** `list_for_user` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = note.
2. P = note (after the commit point).

**When**
- `result = svc.list_for_user(db, workspace_id=W1.id, user_id=UA.id)`, with **spies**.

**Then**
1. returns: `idset(result[0]) == {A.id, P.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. committed: re-read A: `is_read is False`.
5. committed: `notifications` rows: exactly 1.

### NSV-L-06 — pass-through BUG-1412: on a tie the higher id comes first
- **Rules:** `list_for_user` R1 [BUG-1412]
- **Kind:** bug
- **Expect:** xfail BUG-1412 (non-strict)
- **Fails today on:** Then 2 (no order among tied rows; physical order puts the updated row last)

**Given**
1. A = note, but `created_at T2`.
2. B = note, but `created_at T2`.
3. C = note, but `created_at T2`.
4. `A.preview = "edited"`, then `db.flush()`.

**When**
- `result = svc.list_for_user(db, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `len(result[0]) == 3`.
2. returns: `[r.id for r in result[0]] == [C.id, B.id, A.id]`.

### NSV-L-07 — a negative limit raises the DAO's DataError
- **Rules:** `list_for_user` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = note.

**When**
- `svc.list_for_user(db, workspace_id=W1.id, user_id=UA.id, limit=-1)`, inside the savepoint wrap of `raises:`.

**Then**
1. raises: `DataError`.
2. nothing written: nothing written.

## `NotificationService.mark_read`

### NSV-M-01 — ids omitted marks all the user's unread notifications and commits
- **Rules:** `mark_read` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = note.
2. B = note.
3. C = note, but `recipient_user_id UB.id`.
4. Z = note, but `workspace_id W2.id`.

**When**
- `result = svc.mark_read(db, workspace_id=W1.id, user_id=UA.id, data=MarkReadRequest())`.

**Then**
1. returns: `result == 2`.
2. committed: re-read A: `is_read is True`, `read_at is not None`.
3. committed: re-read B: `is_read is True`.
4. committed: re-read C: `is_read is False`.
5. committed: re-read Z: `is_read is False`.

### NSV-M-02 — ids=None marks all, like omitted
- **Rules:** `mark_read` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = note.
2. B = note.

**When**
- `result = svc.mark_read(db, workspace_id=W1.id, user_id=UA.id, data=MarkReadRequest(ids=None))`.

**Then**
1. returns: `result == 2`.

### NSV-M-03 — named ids mark only those
- **Rules:** `mark_read` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = note.
2. B = note.

**When**
- `result = svc.mark_read(db, workspace_id=W1.id, user_id=UA.id, data=MarkReadRequest(ids=[A.id]))`.

**Then**
1. returns: `result == 1`.
2. committed: re-read A: `is_read is True`.
3. committed: re-read B: `is_read is False`.

### NSV-M-04 — another person's notification is not marked
- **Rules:** `mark_read` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. C = note, but `recipient_user_id UB.id`.

**When**
- `result = svc.mark_read(db, workspace_id=W1.id, user_id=UA.id, data=MarkReadRequest(ids=[C.id]))`.

**Then**
1. returns: `result == 0`.
2. unchanged: unchanged(C).

### NSV-M-06 — a failing commit reaches the caller unchanged; no rollback; nothing saved
- **Rules:** `mark_read` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. A = note.

**When**
- `svc.mark_read(db, workspace_id=W1.id, user_id=UA.id, data=MarkReadRequest())`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 0`.
3. committed: re-read A: `is_read is False`.

### NSV-M-07 — pass-through BUG-1414: an empty list marks nothing
- **Rules:** `mark_read` R1 [BUG-1414]
- **Kind:** bug
- **Expect:** xfail BUG-1414
- **Fails today on:** Then 1 (`[]` is treated like `None`: 2 is returned)

**Given**
1. A = note.
2. B = note.

**When**
- `result = svc.mark_read(db, workspace_id=W1.id, user_id=UA.id, data=MarkReadRequest(ids=[]))`.

**Then**
1. returns: `result == 0`.
2. committed: re-read A: `is_read is False`.

### NSV-M-08 — pass-through BUG-1413: read_at read as UTC is the moment of the call
- **Rules:** `mark_read` R1 [BUG-1413]
- **Kind:** bug
- **Expect:** xfail BUG-1413
- **Fails today on:** Then 2 (the naive UTC value is read as Dhaka time)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. A = note.
3. clock patch.

**When**
- `result = svc.mark_read(db, workspace_id=W1.id, user_id=UA.id, data=MarkReadRequest())`.

**Then**
1. returns: `result == 1`.
2. re-read A: `utc_read(A) == NOW`.

### NSV-M-09 — a second call marks nothing
- **Rules:** `mark_read` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = note.
2. `svc.mark_read(db, workspace_id=W1.id, user_id=UA.id, data=MarkReadRequest())` (after the commit point).

**When**
- `result = svc.mark_read(db, workspace_id=W1.id, user_id=UA.id, data=MarkReadRequest())`.

**Then**
1. returns: `result == 0`.
2. committed: re-read A: `is_read is True`.

### NSV-M-10 — a row loaded before the call reads True afterwards: the commit expired it
- **Rules:** `mark_read` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = note.
2. `db.refresh(A)` (after the commit point).

**When**
- `result = svc.mark_read(db, workspace_id=W1.id, user_id=UA.id, data=MarkReadRequest(ids=[A.id]))`.

**Then**
1. returns: `result == 1`.
2. session: `A.is_read is True`.

### NSV-M-11 — a failing update reaches the caller unchanged; no commit, no rollback; nothing saved
- **Rules:** `mark_read` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. A = note.

**When**
- `svc.mark_read(db, workspace_id=W1.id, user_id=UA.id, data=MarkReadRequest())`, with the failing update.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. committed: re-read A: `is_read is False`.

## `NotificationService.fan_out_mentions`

### NSV-F-01 — each mentioned active member gets one notification with every field
- **Rules:** `fan_out_mentions` R1, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. No notification exists.

**When**
- `result = svc.fan_out_mentions(db, workspace_id=W1.id, actor_user_id=UN.id, mentioned_user_ids=[UA.id, UB.id], entity_type="purchase_order", entity_id=12, source_id=77, preview="hi @Ann")`.

**Then**
1. returns: `result is None`.
2. count: `{n.recipient_user_id for n in mentions} == {UA.id, UB.id}`.
3. count: `len(mentions) == 2`.
4. count: every row of mentions: `workspace_id == W1.id`, `actor_user_id == UN.id`, `entity_type == "purchase_order"`, `entity_id == 12`.
5. count: every row of mentions: `source_type == "discussion"`, `preview == "hi @Ann"`, `is_read is False`.

### NSV-F-02 — preview defaults to None
- **Rules:** `fan_out_mentions` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No notification exists.

**When**
- `svc.fan_out_mentions(db, workspace_id=W1.id, actor_user_id=UN.id, mentioned_user_ids=[UA.id], entity_type="purchase_order", entity_id=12, source_id=77)`.

**Then**
1. count: `len(mentions) == 1`.
2. count: `mentions[0].preview is None`.

### NSV-F-03 — suspended, invited, other-workspace and unknown ids are skipped without error
- **Rules:** `fan_out_mentions` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No notification exists.

**When**
- `result = svc.fan_out_mentions(db, workspace_id=W1.id, actor_user_id=UN.id, mentioned_user_ids=[US.id, UI.id, UO.id, MISSING, UA.id], entity_type="purchase_order", entity_id=12, source_id=77)`.

**Then**
1. returns: `result is None`.
2. count: `{n.recipient_user_id for n in mentions} == {UA.id}`.

### NSV-F-04 — the actor is never notified of their own mention
- **Rules:** `fan_out_mentions` R4 [BUG-1535]
- **Kind:** bug
- **Expect:** xfail BUG-1535
- **Fails today on:** Then 1 (the actor gets a notification)

**Given**
1. No notification exists.

**When**
- `svc.fan_out_mentions(db, workspace_id=W1.id, actor_user_id=UA.id, mentioned_user_ids=[UA.id, UB.id], entity_type="purchase_order", entity_id=12, source_id=77)`.

**Then**
1. count: `{n.recipient_user_id for n in mentions} == {UB.id}`.

### NSV-F-05 — an id listed twice gets one notification
- **Rules:** `fan_out_mentions` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No notification exists.

**When**
- `svc.fan_out_mentions(db, workspace_id=W1.id, actor_user_id=UN.id, mentioned_user_ids=[UA.id, UA.id], entity_type="purchase_order", entity_id=12, source_id=77)`.

**Then**
1. count: `len(mentions) == 1`.

### NSV-F-06 — an empty list creates nothing
- **Rules:** `fan_out_mentions` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No notification exists.

**When**
- `result = svc.fan_out_mentions(db, workspace_id=W1.id, actor_user_id=UN.id, mentioned_user_ids=[], entity_type="purchase_order", entity_id=12, source_id=77)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### NSV-F-07 — the rows are flushed into the caller's transaction, not committed
- **Rules:** `fan_out_mentions` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No notification exists.

**When**
- `svc.fan_out_mentions(db, workspace_id=W1.id, actor_user_id=UN.id, mentioned_user_ids=[UA.id], entity_type="purchase_order", entity_id=12, source_id=77)`, with **spies**.

**Then**
1. count: `len(mentions) == 1`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. committed: `notifications` rows: exactly 0.

### NSV-F-08 — another workspace's call does not notify this workspace's members
- **Rules:** `fan_out_mentions` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No notification exists.

**When**
- `svc.fan_out_mentions(db, workspace_id=W2.id, actor_user_id=UN.id, mentioned_user_ids=[UA.id, UO.id], entity_type="purchase_order", entity_id=12, source_id=77)`.

**Then**
1. count: `notifications` rows with `source_id == 77`: exactly 1.
2. count: that row: `recipient_user_id == UO.id`, `workspace_id == W2.id`.

### NSV-F-09 — a database error reaches the caller unchanged
- **Rules:** `fan_out_mentions` R6, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No notification exists.

**When**
- `svc.fan_out_mentions(db, workspace_id=W1.id, actor_user_id=MISSING, mentioned_user_ids=[UA.id], entity_type="purchase_order", entity_id=12, source_id=77)`, inside the savepoint wrap of `raises:`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. nothing written: nothing written.

### NSV-F-10 — on a database error the function neither commits nor rolls back
- **Rules:** `fan_out_mentions` R6, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No notification exists.

**When**
- `svc.fan_out_mentions(db, workspace_id=W1.id, actor_user_id=MISSING, mentioned_user_ids=[UA.id], entity_type="purchase_order", entity_id=12, source_id=77)`, wrapped in this order, outermost first: **spies**, then `with pytest.raises(IntegrityError) as exc:`, then `with db.begin_nested():` (the savepoint's own rollback does not go through `db.rollback`).

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `GET /me/notifications/` shaping (`entity_label`, `actor`), paging bounds `1 <= limit <= 200`, `skip >= 0` | endpoint (integration) | Integration-only. |
| `POST /me/notifications/read/` returns `{"marked_read": n}` | endpoint (integration) | Integration-only. |
| Live stream: `pg_notify` delivered on a real commit | integration | Not observable under the `db` fixture. |
| FU-1 — the discussion service's `_extract_mentions` (BUG-1536), passing `workspace_id` (BUG-1534), cut after replacing | `DiscussionService` (no spec yet) | Must change with these fixes. |

## Spec gaps
None. Revision 0's gaps 1, 2 and 3 are closed by spec Gap log G1, G2, G3.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `humanize_mention_preview` | R1 | NSV-H-01, NSV-H-02, NSV-H-03, NSV-H-04 |
| `humanize_mention_preview` | R2 | NSV-H-05 |
| `humanize_mention_preview` | R3 | NSV-H-02, NSV-H-06, NSV-H-07 |
| `humanize_mention_preview` | R4 | NSV-H-08 |
| `humanize_mention_preview` | R5 | NSV-H-12 |
| `humanize_mention_preview` | R5 [BUG-1534] | NSV-H-09, NSV-H-10, NSV-H-11 |
| `humanize_mention_preview` | R6 | NSV-H-13 |
| `humanize_mention_preview` | R7 | NSV-H-15, NSV-H-16 |
| `humanize_mention_preview` | R7 [BUG-1536] | NSV-H-14 |
| `humanize_mention_preview` | R8 | NSV-H-17 |
| `_active_workspace_member_ids` | R1 | NSV-A-01, NSV-A-02, NSV-A-03 |
| `list_for_user` | R1 | NSV-L-01, NSV-L-02, NSV-L-03, NSV-L-04 |
| `list_for_user` | R1 [BUG-1412] | NSV-L-06 |
| `list_for_user` | R2 | NSV-L-05 |
| `list_for_user` | Errors | NSV-L-07 |
| `mark_read` | R1 | NSV-M-01, NSV-M-02, NSV-M-03, NSV-M-04, NSV-M-09 |
| `mark_read` | R1 [BUG-1413] | NSV-M-08 |
| `mark_read` | R1 [BUG-1414] | NSV-M-07 |
| `mark_read` | R2 | NSV-M-01, NSV-M-09 |
| `mark_read` | R3 | NSV-M-10 |
| `mark_read` | R4 | NSV-M-06, NSV-M-11 |
| `fan_out_mentions` | R1 | NSV-F-01, NSV-F-02, NSV-F-08 |
| `fan_out_mentions` | R2 | NSV-F-03, NSV-F-08 |
| `fan_out_mentions` | R3 | NSV-F-05 |
| `fan_out_mentions` | R4 [BUG-1535] | NSV-F-04 |
| `fan_out_mentions` | R5 | NSV-F-06 |
| `fan_out_mentions` | R6 | NSV-F-07, NSV-F-09, NSV-F-10 |
| `fan_out_mentions` | R7 | NSV-F-01 |
| `fan_out_mentions` | Errors | NSV-F-09, NSV-F-10 |
