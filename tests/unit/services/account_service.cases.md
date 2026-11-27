# Test cases — `app/services/account_service.py`

> **Spec:** `tests/unit/services/account_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-21) — spec fill-gaps G1–G4. G1: Conventions name the `Account` / `AccountTagAssignment` models (no card changes; the row assumptions hold). G2: `assign_tag` R4 / R4a now have cards ASV-A-12 (failing read stays saved), A-13 (a `ValueError` "not found" from the read → 404, saved), A-14 (another `ValueError` from the read → 422, saved). G3: new strict xfail ASV-G-11 (BUG-865: deleted tag not listed) and G-12 (BUG-1486: tag SELECT carries `ORDER BY`). G4: D-20, D-23 now cite R5a; new D-29 (a voided foreign invoice blocks nothing, pass) and D-30 (own + two foreign → own entry, then one `other_workspace`, xfail BUG-2984). No ID retired.
> **Revision:** 3 (2026-11-22) — from `account_service.verify.md` (NEEDS WORK, cards missing only). Finding 1 (tag entries' keys and values in list, by-tag, hub results) → R-AS-1 ASV-L-09, R-AS-2 ASV-T-09, R-AS-3 ASV-M-03. Finding 2 (default limits 100 / 100 / 50) → R-AS-4 ASV-L-10, R-AS-5 ASV-T-10, R-AS-6 ASV-H-05. Finding 3 (`unassign_tag` translation) → R-AS-7 ASV-N-08 (other ValueError → 422), R-AS-8 ASV-N-09 (case-sensitive "Not Found" → 422). ASV-D-08 Then 1 now compares case-insensitively (`t.upper()`). BUG-124 / BUG-629 reasons left as they are (describer is fixing the citations). No ID retired.
> **Revision:** 3a (2026-11-22) — citations only, from spec G5: BUG-124 → BUG-2986 (ASV-U-04, U-08 … U-11, D-09, D-11, D-12, D-26; Reviewer summary; Coverage matrix) and BUG-629 → BUG-2987 (ASV-C-09, C-12, U-07, C-02 companion note; Coverage matrix). No card changed meaning; counts unchanged.
> **Counts:** 124 cases · 81 expected-to-pass · 43 expected-to-fail (bugs) · 9 deferred

## Reviewer summary
- **Per callable:** `create_account` 13 (7 bug) · `get_account_with_tags` 12 (4 bug) · `get_accounts_with_tags` 10 (1 bug) · `_account_dict_with_tags` 3 · `_rollup_from_subquery_row` 5 · `get_accounts_hub_page` 5 · `update_account` 13 (10 bug) · `get_accounts_by_tag_id` 10 (1 bug) · `assign_tag` 14 (1 bug) · `unassign_tag` 9 (3 bug) · `delete_account` 30 (16 bug). All xfail cards are strict.
- **Depth:** full for `delete_account` (the open-invoices refusal reads money state and carries the owner's blocker list, BUG-2984); the rest is a transaction wrapper with a translation table, so lighter: TC1/TC3 per write, TC2/TC4/TC5 once per commit path, TC6 once per read, each translation once patched and once end-to-end through the real manager.
- **Translation cards** patch `svc.account_manager.<method>` to raise a given `ValueError` (spec Notes), so the translation is tested independently of the manager fix; each is `Author: claude`. Every bug also gets one end-to-end card through the real manager (strict xfail).
- **TC3 "every other pending change discarded"**: each error card adds an uncommitted workspace X after the commit point and checks it is gone.
- **BUG-2986 / Q3 after BUG-862**: ASV-D-12 wraps the manager's `get_account` so that it hides deleted accounts unless `include_deleted=True` is passed, i.e. the state after BUG-862; the 400 must still come. Declared under Race simulations though it is not a race (it is the only post-fix state simulation).
- **BUG-2984 blockers**: one card per blocker type (draft, confirmed unpaid, partial), per non-blocking state (settled, voided, other account's invoice), per cross-workspace shape (only W2, own + W2, W0 foreign with lower id, two foreign), id order with explicit ids, plus the patched translation.
- **No lock (HR-10 / manager R7d):** one pass card asserts no `FOR UPDATE` in the delete's SQL.
- **Hub:** mapping tested on canned manager rows (patched module global `account_invoice_manager`) and once end-to-end with confirmed invoices only (drafts are BUG-634 territory, not used).
- **`assign_tag` post-commit read** (R4 / R4a) is patched on the instance (`svc.get_account_with_tags`), `Author: claude`.
- **Needs a decision:** None. Gaps 1–4 closed by the spec's Gap log (G1–G4).

## Conventions for this module

**IDs.** `ASV` = `app/services/account_service.py`. `C` create_account · `G` get_account_with_tags · `L` get_accounts_with_tags · `M` _account_dict_with_tags · `R` _rollup_from_subquery_row · `H` get_accounts_hub_page · `U` update_account · `T` get_accounts_by_tag_id · `A` assign_tag · `N` unassign_tag · `D` delete_account.

**Actors and fixed values.**
- `svc` = `account_service` (`from app.services.account_service import AccountService, account_service`); `mod` = the module `app.services.account_service`. `db` = the test's real session, first argument; the rest by keyword. `result` = what the When returns.
- `AccountCreate`, `AccountUpdate` (`app.schemas.account`); `AccountTag` (`app.models.account_tag`); `AccountInvoice` (`app.models.account_invoice`); `NotFoundError`, `ConflictError`, `BusinessRuleError`, `AppValidationError` = `ValidationError` of `app.core.exceptions`. `Decimal`, `date`, `datetime`, `SimpleNamespace`, `patch`, `MagicMock`, `inspect`, `text`.
- **Standing rows** (every test, no Given line): W0, W1, W2 = `make_workspace(db)` three times, so `W0.id < W1.id < W2.id`; U1, U2 = `make_profile(db)`. U1 acts; U2 built the Given rows.
- MISSING = `999999999`. T0 = `datetime(2020, 1, 2, 3, 4, 5)`. OPEN = `"Account has open invoices — settle or void them first"` (em dash U+2014).
- KEYS = `{"id", "workspace_id", "name", "account_code", "primary_contact_person", "primary_email", "primary_phone", "secondary_contact_person", "secondary_email", "secondary_phone", "address", "city", "country", "postal_code", "payment_preferences", "bank_details", "allow_invoices", "is_active", "created_at", "account_tags"}`. TAGKEYS = `{"id", "name", "tag_code", "color", "icon", "is_system_tag"}`.

**Given rows.** Inserted directly (never through `svc`), flushed one at a time in the order written; after "but" a line lists every column that differs.
- **account** = `Account(workspace_id=W1.id, name="Acme Ltd", created_by=U2.id)` (`app.models.account`); model defaults `is_active True`, `is_deleted False`, `allow_invoices True`; every other column NULL.
- **gone** (after "but") = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U2.id`.
- **tag** = `AccountTag(workspace_id=W1.id, name="Supplier", tag_code="supplier")` (model fills `is_system_tag False`, `is_active True`, `usage_count 0`).
- **link(A, T)** = `AccountTagAssignment(account_id=A.id, tag_id=T.id, workspace_id=W1.id, assigned_by=U2.id, assigned_at=T0)` (`app.models.account_tag_assignment`; unique on `(account_id, tag_id)`).
- **invoice on A, state S** = `AccountInvoice(workspace_id=W1.id, account_id=A.id, invoice_type="payable", invoice_amount=Decimal("1000.00"), invoice_date=date(2025, 3, 1), …)` with S one of: **draft** (`invoice_status "draft"`, `paid_amount 0.00`, `payment_status "unpaid"`), **unpaid** (`"confirmed"`, `0.00`, `"unpaid"`), **partial** (`"confirmed"`, `400.00`, `"partial"`), **settled** (`"confirmed"`, `1000.00`, `"paid"`), **voided** (`"voided"`, `0.00`, `"unpaid"`, `void_note "x"`).
- **commit point** = after the last Given line `db.commit()`. Snapshots for `unchanged` / `nothing written` are taken there.
- **X** (only where listed, after the commit point) = `X = make_workspace(db)`, flushed, not committed; `X_ID = X.id`. **x_gone** = `db.get(type(X), X_ID) is None`.

**Named checks.**
- **re-read A** = `db.expire_all()`, then SELECT A by id; database values.
- **unchanged(A)** = after re-read, `name`, `account_code`, `city`, `is_active`, `is_deleted`, `deleted_at`, `deleted_by`, `updated_by` of A equal their commit-point values.
- **nothing written** = the row counts of `accounts`, `account_tag_assignments`, `financial_audit_logs` (all workspaces) and the `usage_count` of every `account_tags` row equal their commit-point values.
- **audit(A)** = `financial_audit_logs` rows with `entity_type == 'account'` and `entity_id == A.id`.
- **loaded(r)** = `inspect(r).expired_attributes.isdisjoint({c.key for c in inspect(type(r)).column_attrs})`; run before any attribute of `r` is read.
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line then re-reads with a fresh query.
- `session:` lines check `db` right after the call, before any re-read. "usable" = `db.execute(text("SELECT 1")).scalar() == 1`.
- `raises: <Type>` = plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint; further lines on `exc.value`, one assert each.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = the same with `patch.object(db, "refresh", side_effect=RuntimeError("boom"))`.
- **mgr raises E on m** = `with patch.object(svc.account_manager, "m", side_effect=E):` around the When (inside any `raises:` wrap). `Author: claude`.
- **Statement recorder** = the SQL text of every statement the session sends during the When is recorded in `stmts` (list of str).

**xfail cards.** `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write calls exactly as shown, also with parameters that do not exist yet.

**Race simulations.** ASV-D-12 only (`delete_account` R3, Q3 — the post-BUG-862 state): `real = svc.account_manager.get_account`; `def hidden(*a, **k): return real(*a, **k) if k.get("include_deleted") else None`; `with patch.object(svc.account_manager, "get_account", side_effect=hidden):` around the When.

## `AccountService.create_account`

### ASV-C-01 — a new account is committed and returned re-read
- **Rules:** `create_account` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no accounts.

**When**
- `result = svc.create_account(db, account_in=AccountCreate(name="Acme Ltd", account_code="SUP-001", city="Dhaka"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id is not None`, `result.created_at is not None`.
3. returns: `result.name == "Acme Ltd"`, `result.workspace_id == W1.id`, `result.created_by == U1.id`.
4. committed: the `accounts` row with `id == result.id` has `name == "Acme Ltd"`, `account_code == "SUP-001"`, `city == "Dhaka"`, `is_deleted is False`.
5. committed: audit(result) has exactly 1 row, `action_type == "created"`.

### ASV-C-02 — an active tag in tag_ids is attached and committed
- **Rules:** `create_account` R1 (companion of BUG-871 / BUG-2987)
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = tag.

**When**
- `result = svc.create_account(db, account_in=AccountCreate(name="Acme Ltd", tag_ids=[T.id]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. committed: `account_tag_assignments` rows with `account_id == result.id`: exactly 1, its `tag_id == T.id`.
3. committed: re-read T: `usage_count == 1`.

### ASV-C-03 — a database error rolls back the account and every other pending change
- **Rules:** `create_account` R2; TC3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = account.
2. X (after the commit point).

**When**
- `svc.create_account(db, account_in=AccountCreate(name="Beta Traders"), workspace_id=W1.id, user_id=MISSING)`.

**Then**
1. raises: `IntegrityError`.
2. count: `accounts` rows with `name == "Beta Traders"`: exactly 0.
3. session: `x_gone`.
4. nothing written: nothing written.
5. session: usable.

### ASV-C-04 — a failing commit is rolled back and re-raised
- **Rules:** `create_account` R2; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no accounts.

**When**
- `svc.create_account(db, account_in=AccountCreate(name="Acme Ltd"), workspace_id=W1.id, user_id=U1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `accounts` rows of W1: exactly 0.
4. nothing written: nothing written.

### ASV-C-05 — a failing re-read after the commit leaves the account saved
- **Rules:** `create_account` R2; TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no accounts.

**When**
- `svc.create_account(db, account_in=AccountCreate(name="Acme Ltd"), workspace_id=W1.id, user_id=U1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `accounts` rows of W1 with `name == "Acme Ltd"`: exactly 1.

### ASV-C-06 — any other ValueError of the manager passes unchanged, rolled back
- **Rules:** `create_account` R3 (last sentence), R2; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. A = account.
2. X (after the commit point).
3. `E = ValueError("something else")`.

**When**
- `svc.create_account(db, account_in=AccountCreate(name="Beta Traders"), workspace_id=W1.id, user_id=U1.id)`, with **mgr raises E on create_account**.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value is E`.
3. session: `x_gone`.
4. nothing written: nothing written.

### ASV-C-07 — translation: "Account tag N not found" becomes 404
- **Rules:** `create_account` R3 [BUG-871]
- **Kind:** bug
- **Expect:** xfail BUG-871
- **Fails today on:** Then 1 (the bare ValueError is re-raised)
- **Author:** claude

**Given**
1. X (after the commit point).
2. `E = ValueError("Account tag 77 not found")`.

**When**
- `svc.create_account(db, account_in=AccountCreate(name="Acme Ltd"), workspace_id=W1.id, user_id=U1.id)`, with **mgr raises E on create_account**.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Account tag 77 not found"`.
4. session: `x_gone`.

### ASV-C-08 — translation: duplicate code becomes 409
- **Rules:** `create_account` R3 [BUG-874]
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 1 (the bare ValueError is re-raised)
- **Author:** claude

**Given**
1. X (after the commit point).
2. `E = ValueError("Account code 'SUP-001' already exists")`.

**When**
- `svc.create_account(db, account_in=AccountCreate(name="Beta Traders", account_code="SUP-001"), workspace_id=W1.id, user_id=U1.id)`, with **mgr raises E on create_account**.

**Then**
1. raises: `ConflictError`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "Account code 'SUP-001' already exists"`.
4. session: `x_gone`.

### ASV-C-09 — translation: inactive tag becomes 422
- **Rules:** `create_account` R3 [BUG-2987]
- **Kind:** bug
- **Expect:** xfail BUG-2987
- **Fails today on:** Then 1 (the bare ValueError is re-raised)
- **Author:** claude

**Given**
1. X (after the commit point).
2. `E = ValueError("Account tag 7 is not active")`.

**When**
- `svc.create_account(db, account_in=AccountCreate(name="Acme Ltd", tag_ids=[7]), workspace_id=W1.id, user_id=U1.id)`, with **mgr raises E on create_account**.

**Then**
1. raises: `BusinessRuleError`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == "Account tag 7 is not active"`.
4. session: `x_gone`.

### ASV-C-10 — end to end: an unknown tag id is refused with 404, nothing saved
- **Rules:** `create_account` R3 [BUG-871]
- **Kind:** bug
- **Expect:** xfail BUG-871
- **Fails today on:** Then 1 (no error: the id is skipped and the account created)

**Given**
1. W1 has no accounts.

**When**
- `svc.create_account(db, account_in=AccountCreate(name="Acme Ltd", tag_ids=[MISSING]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == "Account tag 999999999 not found"`.
3. count: `accounts` rows of W1: exactly 0.
4. nothing written: nothing written.

### ASV-C-11 — end to end: a duplicate account code is refused with 409
- **Rules:** `create_account` R3 [BUG-874]
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 1 (no error: the duplicate is created)

**Given**
1. A = account, but `account_code "SUP-001"`.

**When**
- `svc.create_account(db, account_in=AccountCreate(name="Beta Traders", account_code="SUP-001"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `ConflictError`.
2. raises: `exc.value.detail == "Account code 'SUP-001' already exists"`.
3. count: `accounts` rows of W1 with `account_code == "SUP-001"`: exactly 1.
4. nothing written: nothing written.

### ASV-C-12 — end to end: a deleted tag is refused with 422
- **Rules:** `create_account` R3 [BUG-2987]
- **Kind:** bug
- **Expect:** xfail BUG-2987
- **Fails today on:** Then 1 (no error: the inactive tag is attached)

**Given**
1. T = tag, but `name "Old vendor"`, `tag_code "old"`, `is_active False`.

**When**
- `svc.create_account(db, account_in=AccountCreate(name="Acme Ltd", tag_ids=[T.id]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `BusinessRuleError`.
2. raises: `exc.value.detail == f"Account tag {T.id} is not active"`.
3. count: `accounts` rows of W1: exactly 0.
4. nothing written: nothing written.

### ASV-C-13 — client IP and user agent reach the audit row
- **Rules:** `create_account` R4 [BUG-140]
- **Kind:** bug
- **Expect:** xfail BUG-140
- **Fails today on:** Then 1 (the call raises TypeError: no such parameters)

**Given**
1. W1 has no accounts.

**When**
- `result = svc.create_account(db, account_in=AccountCreate(name="Acme Ltd"), workspace_id=W1.id, user_id=U1.id, ip_address="203.0.113.7", user_agent="UA/1.0")`.

**Then**
1. returns: `result.id is not None`.
2. committed: audit(result) has exactly 1 row with `ip_address == "203.0.113.7"`, `user_agent == "UA/1.0"`.

## `AccountService.get_account_with_tags`

### ASV-G-01 — a live account gives the 20-key dict with its tags
- **Rules:** `get_account_with_tags` R1, R4; Facts (account dict)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = account, but `account_code "SUP-001"`, `city "Dhaka"`.
2. T = tag, but `color "#ff0000"`, `icon "truck"`.
3. link(A, T).

**When**
- `result = svc.get_account_with_tags(db, account_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `set(result.keys()) == KEYS`.
2. returns: `result["id"] == A.id`, `result["name"] == "Acme Ltd"`, `result["account_code"] == "SUP-001"`, `result["city"] == "Dhaka"`, `result["workspace_id"] == W1.id`.
3. returns: `len(result["account_tags"]) == 1`.
4. returns: `set(result["account_tags"][0].keys()) == TAGKEYS`.
5. returns: `result["account_tags"][0] == {"id": T.id, "name": "Supplier", "tag_code": "supplier", "color": "#ff0000", "icon": "truck", "is_system_tag": False}`.

### ASV-G-02 — two tags are both listed (compared as a set)
- **Rules:** `get_account_with_tags` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = account.
2. T1 = tag.
3. T2 = tag, but `name "Client"`, `tag_code "client"`.
4. link(A, T1).
5. link(A, T2).

**When**
- `result = svc.get_account_with_tags(db, account_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `{t["id"] for t in result["account_tags"]} == {T1.id, T2.id}`.
2. returns: `len(result["account_tags"]) == 2`.

### ASV-G-03 — an account without tags has account_tags == []
- **Rules:** `get_account_with_tags` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = account.

**When**
- `result = svc.get_account_with_tags(db, account_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result["account_tags"] == []`.

### ASV-G-04 — an inactive (not deleted) account is returned
- **Rules:** `get_account_with_tags` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = account, but `is_active False`.

**When**
- `result = svc.get_account_with_tags(db, account_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result["id"] == A.id`, `result["is_active"] is False`.

### ASV-G-05 — a missing id gets 404
- **Rules:** `get_account_with_tags` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = account.

**When**
- `svc.get_account_with_tags(db, account_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Account with ID 999999999 not found"`.

### ASV-G-06 — an account of W0 (built before W1) gets 404
- **Rules:** `get_account_with_tags` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = account, but `workspace_id W0.id`.
2. A = account.

**When**
- `svc.get_account_with_tags(db, account_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Account with ID {Z.id} not found"`.

### ASV-G-07 — an account of W2 (built after W1) gets 404
- **Rules:** `get_account_with_tags` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = account.
2. Z = account, but `workspace_id W2.id`.

**When**
- `svc.get_account_with_tags(db, account_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Account with ID {Z.id} not found"`.

### ASV-G-08 — a soft-deleted account gets 404 by default
- **Rules:** `get_account_with_tags` R3 [BUG-862]
- **Kind:** bug
- **Expect:** xfail BUG-862
- **Fails today on:** Then 1 (no error: the deleted account's dict is returned)

**Given**
1. A = account, gone.

**When**
- `svc.get_account_with_tags(db, account_id=A.id, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Account with ID {A.id} not found"`.

### ASV-G-09 — include_deleted=True returns the soft-deleted account
- **Rules:** `get_account_with_tags` R3 [BUG-862]
- **Kind:** bug
- **Expect:** xfail BUG-862
- **Fails today on:** Then 1 (the call raises TypeError: no `include_deleted` parameter)

**Given**
1. A = account, gone.

**When**
- `result = svc.get_account_with_tags(db, account_id=A.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `result["id"] == A.id`.
2. returns: `result["is_active"] is False`.

### ASV-G-10 — a read neither commits nor rolls back; a pending edit stays
- **Rules:** `get_account_with_tags` R5; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = account.
2. B = account, but `name "Beta Traders"`.
3. (after the commit point) `B.city = "Khulna"` in memory, not flushed.

**When**
- `svc.get_account_with_tags(db, account_id=A.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. session: `B in db.dirty`.
4. session: `len(db.dirty) == 1`.

### ASV-G-11 — a deleted tag of the account is not listed
- **Rules:** `get_account_with_tags` R4 [BUG-865]
- **Kind:** bug
- **Expect:** xfail BUG-865
- **Fails today on:** Then 2 (the deleted tag is listed too)

**Given**
1. A = account.
2. T = tag.
3. D = tag, but `name "Old vendor"`, `tag_code "old"`, `is_active False`.
4. link(A, T).
5. link(A, D).

**When**
- `result = svc.get_account_with_tags(db, account_id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result["id"] == A.id`.
2. returns: `[t["id"] for t in result["account_tags"]] == [T.id]`.

### ASV-G-12 — the SELECT reading the account's tags carries an ORDER BY
- **Rules:** `get_account_with_tags` R4 [BUG-1486]
- **Kind:** bug
- **Expect:** xfail BUG-1486
- **Fails today on:** Then 2 (the tag SELECT has no `ORDER BY`)

**Given**
1. A = account.
2. T1 = tag, but `name "Zeta"`, `tag_code "zeta"`.
3. T2 = tag, but `name "Alpha"`, `tag_code "alpha"`.
4. link(A, T1).
5. link(A, T2).

**When**
- `result = svc.get_account_with_tags(db, account_id=A.id, workspace_id=W1.id)`, with the statement recorder.

**Then**
1. returns: `len(result["account_tags"]) == 2`.
2. statement: the one text in `stmts` that selects `FROM account_tags` contains `"ORDER BY"`.

## `AccountService.get_accounts_with_tags`

### ASV-L-01 — the workspace's live active accounts, none of W0 or W2 (as a set), each a dict
- **Rules:** `get_accounts_with_tags` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = account, but `workspace_id W0.id`.
2. A = account.
3. B = account, but `name "Beta Traders"`.
4. Z2 = account, but `workspace_id W2.id`.

**When**
- `result = svc.get_accounts_with_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `{r["id"] for r in result} == {A.id, B.id}`.
3. returns: every item has `set(r.keys()) == KEYS`.

### ASV-L-02 — search is passed on as the name filter (text in the middle of the name)
- **Rules:** `get_accounts_with_tags` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = account.
2. B = account, but `name "Beta Traders"`.

**When**
- `result = svc.get_accounts_with_tags(db, workspace_id=W1.id, search="cme")`.

**Then**
1. returns: `[r["id"] for r in result] == [A.id]`.

### ASV-L-03 — tag_code is passed on
- **Rules:** `get_accounts_with_tags` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = account.
2. B = account, but `name "Beta Traders"`.
3. T = tag.
4. link(B, T).

**When**
- `result = svc.get_accounts_with_tags(db, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: `[r["id"] for r in result] == [B.id]`.
2. returns: `[t["id"] for t in result[0]["account_tags"]] == [T.id]`.

### ASV-L-04 — skip and limit are passed on: 4 accounts, skip=1, limit=2 give 2 distinct of them
- **Rules:** `get_accounts_with_tags` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = account.
2. B = account, but `name "Beta Traders"`.
3. C = account, but `name "Gamma Co"`.
4. D = account, but `name "Delta Inc"`.

**When**
- `result = svc.get_accounts_with_tags(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `{r["id"] for r in result} <= {A.id, B.id, C.id, D.id}`.
3. returns: `len({r["id"] for r in result}) == 2`.

### ASV-L-05 — no match gives []
- **Rules:** `get_accounts_with_tags` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = account.

**When**
- `result = svc.get_accounts_with_tags(db, workspace_id=W1.id, search="Zeta")`.

**Then**
1. returns: `result == []`.

### ASV-L-06 — inactive accounts are left out by default
- **Rules:** `get_accounts_with_tags` R1 (companion of BUG-878)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = account.
2. B = account, but `name "Beta Traders"`, `is_active False`.

**When**
- `result = svc.get_accounts_with_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `[r["id"] for r in result] == [A.id]`.

### ASV-L-07 — include_inactive=True lists inactive accounts too
- **Rules:** `get_accounts_with_tags` R2 [BUG-878]
- **Kind:** bug
- **Expect:** xfail BUG-878
- **Fails today on:** Then 1 (the call raises TypeError: no `include_inactive` parameter)

**Given**
1. A = account.
2. B = account, but `name "Beta Traders"`, `is_active False`.

**When**
- `result = svc.get_accounts_with_tags(db, workspace_id=W1.id, include_inactive=True)`.

**Then**
1. returns: `{r["id"] for r in result} == {A.id, B.id}`.

### ASV-L-08 — a read neither commits nor rolls back; a pending edit stays
- **Rules:** `get_accounts_with_tags` R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = account.
2. (after the commit point) `A.city = "Khulna"` in memory, not flushed.

**When**
- `svc.get_accounts_with_tags(db, workspace_id=W2.id)`, inside **spies**.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. session: `A in db.dirty`.

### ASV-L-09 — each list item carries its tag entries with all six keys and stored values
- **Rules:** `get_accounts_with_tags` R1; Facts (account dict)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = account.
2. T = tag, but `color "#ff0000"`, `icon "truck"`.
3. link(A, T).

**When**
- `result = svc.get_accounts_with_tags(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["account_tags"] == [{"id": T.id, "name": "Supplier", "tag_code": "supplier", "color": "#ff0000", "icon": "truck", "is_system_tag": False}]`.

### ASV-L-10 — the default limit is 100: 101 accounts give 100
- **Rules:** `get_accounts_with_tags` R1 (signature default `limit=100`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows, by `add_all`: k = 1 … 101, account, but `name f"a{k:03d}"`.

**When**
- `result = svc.get_accounts_with_tags(db, workspace_id=W1.id)` (no `skip`, no `limit`).

**Then**
1. returns: `len(result) == 100`.

## `AccountService._account_dict_with_tags`

### ASV-M-01 — builds the 20-key dict with the tags read for the given workspace
- **Rules:** `_account_dict_with_tags` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = account, but `primary_email "a@acme.test"`, `bank_details "IBAN 1"`.
2. T = tag.
3. link(A, T).

**When**
- `result = svc._account_dict_with_tags(db, account=A, workspace_id=W1.id)`.

**Then**
1. returns: `set(result.keys()) == KEYS`.
2. returns: `result["primary_email"] == "a@acme.test"`, `result["bank_details"] == "IBAN 1"`, `result["allow_invoices"] is True`.
3. returns: `[t["id"] for t in result["account_tags"]] == [T.id]`.

### ASV-M-02 — the account is not re-checked: a deleted account still maps
- **Rules:** `_account_dict_with_tags` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = account, gone.

**When**
- `result = svc._account_dict_with_tags(db, account=A, workspace_id=W1.id)`.

**Then**
1. returns: `result["id"] == A.id`, `result["is_active"] is False`.
2. returns: `result["account_tags"] == []`.

### ASV-M-03 — the tag entries carry all six keys and stored values
- **Rules:** `_account_dict_with_tags` R1 (used by `get_accounts_hub_page` R2)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = account.
2. T = tag, but `color "#ff0000"`, `icon "truck"`.
3. link(A, T).

**When**
- `result = svc._account_dict_with_tags(db, account=A, workspace_id=W1.id)`.

**Then**
1. returns: `result["account_tags"] == [{"id": T.id, "name": "Supplier", "tag_code": "supplier", "color": "#ff0000", "icon": "truck", "is_system_tag": False}]`.

## `AccountService._rollup_from_subquery_row`

### ASV-R-01 — None gives (Decimal 0, 0, False)
- **Rules:** `_rollup_from_subquery_row` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing in the database is needed.

**When**
- `result = AccountService._rollup_from_subquery_row(None)`.

**Then**
1. returns: `result == (Decimal(0), 0, False)`.
2. returns: `type(result[0]) is Decimal`, `type(result[1]) is int`, `type(result[2]) is bool`.

### ASV-R-02 — values are converted, the Decimal keeps its scale
- **Rules:** `_rollup_from_subquery_row` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `row = SimpleNamespace(outstanding_total=Decimal("1500.00"), open_count=3, has_overdue=1)`.

**When**
- `result = AccountService._rollup_from_subquery_row(row)`.

**Then**
1. returns: `str(result[0]) == "1500.00"`.
2. returns: `result[1] == 3`, `type(result[1]) is int`.
3. returns: `result[2] is True`.

### ASV-R-03 — None values give zeros
- **Rules:** `_rollup_from_subquery_row` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `row = SimpleNamespace(outstanding_total=None, open_count=None, has_overdue=None)`.

**When**
- `result = AccountService._rollup_from_subquery_row(row)`.

**Then**
1. returns: `result == (Decimal(0), 0, False)`.
2. returns: `str(result[0]) == "0"`.

### ASV-R-04 — missing attributes give zeros
- **Rules:** `_rollup_from_subquery_row` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `row = SimpleNamespace()`.

**When**
- `result = AccountService._rollup_from_subquery_row(row)`.

**Then**
1. returns: `result == (Decimal(0), 0, False)`.
2. returns: `str(result[0]) == "0"`.

### ASV-R-05 — zero values stay zero, no rounding of a fraction
- **Rules:** `_rollup_from_subquery_row` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `row = SimpleNamespace(outstanding_total=Decimal("0.005"), open_count=0, has_overdue=False)`.

**When**
- `result = AccountService._rollup_from_subquery_row(row)`.

**Then**
1. returns: `str(result[0]) == "0.005"`.
2. returns: `result[1] == 0`, `result[2] is False`.

## `AccountService.get_accounts_hub_page`

### ASV-H-01 — items map the manager's rows in its order, total unchanged
- **Rules:** `get_accounts_hub_page` R1, R2
- **Kind:** happy
- **Expect:** pass
- **Author:** claude

**Given**
1. A = account.
2. B = account, but `name "Beta Traders"`.
3. `P = SimpleNamespace(outstanding_total=Decimal("600.00"), open_count=2, has_overdue=True)`; `Q = SimpleNamespace(outstanding_total=Decimal("0"), open_count=0, has_overdue=False)`.
4. `fake = MagicMock(return_value=([(B, P, Q), (A, Q, P)], 7))`, patched as `patch.object(mod.account_invoice_manager, "list_accounts_hub_page", fake)` around the When.

**When**
- `items, total = svc.get_accounts_hub_page(db, workspace_id=W1.id, section="payable", search="ac", skip=5, limit=2)`.

**Then**
1. returns: `total == 7`.
2. returns: `[i["id"] for i in items] == [B.id, A.id]`.
3. returns: `items[0]["open_balance"] == {"payable_outstanding": Decimal("600.00"), "receivable_outstanding": Decimal("0"), "open_payable_count": 2, "open_receivable_count": 0, "has_overdue_payable": True, "has_overdue_receivable": False}`.
4. returns: `items[1]["open_balance"]["receivable_outstanding"] == Decimal("600.00")`, `items[1]["open_balance"]["has_overdue_receivable"] is True`.
5. returns: `set(items[0].keys()) == KEYS | {"open_balance"}`.
6. mock called: `fake.call_args.kwargs` has `workspace_id == W1.id`, `section == "payable"`, `search == "ac"`, `skip == 5`, `limit == 2`.

### ASV-H-02 — end to end: an account without invoices gets zero balances
- **Rules:** `get_accounts_hub_page` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = account.

**When**
- `items, total = svc.get_accounts_hub_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `total == 1`.
2. returns: `items[0]["id"] == A.id`.
3. returns: `items[0]["open_balance"] == {"payable_outstanding": Decimal("0"), "receivable_outstanding": Decimal("0"), "open_payable_count": 0, "open_receivable_count": 0, "has_overdue_payable": False, "has_overdue_receivable": False}`.

### ASV-H-03 — end to end: confirmed open invoices give the outstanding sums per type
- **Rules:** `get_accounts_hub_page` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = account.
2. I1 = invoice on A, state partial.
3. I2 = invoice on A, state unpaid, but `invoice_type "receivable"`, `invoice_amount Decimal("500.00")`.

**When**
- `items, total = svc.get_accounts_hub_page(db, workspace_id=W1.id)`.

**Then**
1. returns: `total == 1`.
2. returns: `items[0]["open_balance"]["payable_outstanding"] == Decimal("600.00")`, `items[0]["open_balance"]["open_payable_count"] == 1`.
3. returns: `items[0]["open_balance"]["receivable_outstanding"] == Decimal("500.00")`, `items[0]["open_balance"]["open_receivable_count"] == 1`.

### ASV-H-04 — a read neither commits nor rolls back; a pending edit stays
- **Rules:** `get_accounts_hub_page` R3; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = account.
2. (after the commit point) `A.city = "Khulna"` in memory, not flushed.

**When**
- `svc.get_accounts_hub_page(db, workspace_id=W2.id)`, inside **spies**.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. session: `A in db.dirty`.

### ASV-H-05 — the default limit is 50: 51 accounts give 50 items, total 51
- **Rules:** `get_accounts_hub_page` R1 (signature default `limit=50`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 rows, by `add_all`: k = 1 … 51, account, but `name f"a{k:03d}"`.

**When**
- `items, total = svc.get_accounts_hub_page(db, workspace_id=W1.id)` (no `skip`, no `limit`).

**Then**
1. returns: `len(items) == 50`.
2. returns: `total == 51`.

## `AccountService.update_account`

### ASV-U-01 — a change is committed and the row returned re-read
- **Rules:** `update_account` R1; TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = account, but `city "Dhaka"`.

**When**
- `result = svc.update_account(db, account_id=A.id, account_in=AccountUpdate(name="Acme Limited"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. loaded: `loaded(result)`.
2. returns: `result.id == A.id`, `result.name == "Acme Limited"`, `result.updated_at is not None`.
3. committed: re-read A: `name == "Acme Limited"`, `city == "Dhaka"`.

### ASV-U-02 — a failing commit is rolled back and re-raised
- **Rules:** `update_account` R2; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. A = account.

**When**
- `svc.update_account(db, account_id=A.id, account_in=AccountUpdate(name="Acme Limited"), workspace_id=W1.id, user_id=U1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(A).
4. nothing written: nothing written.

### ASV-U-03 — any other exception passes unchanged, every pending change discarded
- **Rules:** `update_account` R2, R3 (last sentence); TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. A = account.
2. X (after the commit point).
3. `E = ValueError("something else")`.

**When**
- `svc.update_account(db, account_id=A.id, account_in=AccountUpdate(name="Acme Limited"), workspace_id=W1.id, user_id=U1.id)`, with **mgr raises E on update_account**.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value is E`.
3. session: `x_gone`.
4. unchanged: unchanged(A).

### ASV-U-04 — translation: "Account N not found" becomes 404 "Account with ID N not found"
- **Rules:** `update_account` R3 [BUG-2986]
- **Kind:** bug
- **Expect:** xfail BUG-2986
- **Fails today on:** Then 1 (the bare ValueError is re-raised)
- **Author:** claude

**Given**
1. A = account.
2. X (after the commit point).
3. `E = ValueError(f"Account {A.id} not found")`.

**When**
- `svc.update_account(db, account_id=A.id, account_in=AccountUpdate(name="Acme Limited"), workspace_id=W1.id, user_id=U1.id)`, with **mgr raises E on update_account**.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Account with ID {A.id} not found"`.
4. session: `x_gone`.

### ASV-U-05 — translation: duplicate code becomes 409
- **Rules:** `update_account` R3 [BUG-874]
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 1 (the bare ValueError is re-raised)
- **Author:** claude

**Given**
1. A = account.
2. `E = ValueError("Account code 'SUP-001' already exists")`.

**When**
- `svc.update_account(db, account_id=A.id, account_in=AccountUpdate(account_code="SUP-001"), workspace_id=W1.id, user_id=U1.id)`, with **mgr raises E on update_account**.

**Then**
1. raises: `ConflictError`.
2. raises: `exc.value.detail == "Account code 'SUP-001' already exists"`.
3. unchanged: unchanged(A).

### ASV-U-06 — translation: "Account tag N not found" becomes 404 with the manager's text
- **Rules:** `update_account` R3 [BUG-871]
- **Kind:** bug
- **Expect:** xfail BUG-871
- **Fails today on:** Then 1 (the bare ValueError is re-raised)
- **Author:** claude

**Given**
1. A = account.
2. `E = ValueError("Account tag 77 not found")`.

**When**
- `svc.update_account(db, account_id=A.id, account_in=AccountUpdate(tag_ids=[77]), workspace_id=W1.id, user_id=U1.id)`, with **mgr raises E on update_account**.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == "Account tag 77 not found"`.
3. unchanged: unchanged(A).

### ASV-U-07 — translation: inactive tag becomes 422
- **Rules:** `update_account` R3 [BUG-2987]
- **Kind:** bug
- **Expect:** xfail BUG-2987
- **Fails today on:** Then 1 (the bare ValueError is re-raised)
- **Author:** claude

**Given**
1. A = account.
2. `E = ValueError("Account tag 7 is not active")`.

**When**
- `svc.update_account(db, account_id=A.id, account_in=AccountUpdate(tag_ids=[7]), workspace_id=W1.id, user_id=U1.id)`, with **mgr raises E on update_account**.

**Then**
1. raises: `BusinessRuleError`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == "Account tag 7 is not active"`.

### ASV-U-08 — end to end: a missing id gets 404
- **Rules:** `update_account` R3 [BUG-2986]
- **Kind:** bug
- **Expect:** xfail BUG-2986
- **Fails today on:** Then 1 (a bare ValueError is raised, 500 at the API)

**Given**
1. A = account.

**When**
- `svc.update_account(db, account_id=MISSING, account_in=AccountUpdate(name="Acme Limited"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == "Account with ID 999999999 not found"`.
3. unchanged: unchanged(A).
4. nothing written: nothing written.

### ASV-U-09 — end to end: an account of W2 gets the same 404
- **Rules:** `update_account` R3 [BUG-2986]
- **Kind:** bug
- **Expect:** xfail BUG-2986
- **Fails today on:** Then 1 (a bare ValueError "does not belong to workspace" is raised)

**Given**
1. A = account.
2. Z = account, but `workspace_id W2.id`.

**When**
- `svc.update_account(db, account_id=Z.id, account_in=AccountUpdate(name="Taken"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Account with ID {Z.id} not found"`.
3. unchanged: unchanged(Z).

### ASV-U-10 — end to end: an account of W0 gets the same 404
- **Rules:** `update_account` R3 [BUG-2986]
- **Kind:** bug
- **Expect:** xfail BUG-2986
- **Fails today on:** Then 1 (a bare ValueError "does not belong to workspace" is raised)

**Given**
1. Z = account, but `workspace_id W0.id`.
2. A = account.

**When**
- `svc.update_account(db, account_id=Z.id, account_in=AccountUpdate(name="Taken"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Account with ID {Z.id} not found"`.
3. unchanged: unchanged(Z).

### ASV-U-11 — end to end: a soft-deleted account gets 404, nothing written
- **Rules:** `update_account` R3 [BUG-2986] (manager BUG-863)
- **Kind:** bug
- **Expect:** xfail BUG-2986
- **Fails today on:** Then 1 (no error: the deleted account is updated)

**Given**
1. A = account, gone.

**When**
- `svc.update_account(db, account_id=A.id, account_in=AccountUpdate(name="Revived"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Account with ID {A.id} not found"`.
3. unchanged: unchanged(A).

### ASV-U-12 — end to end: a duplicate code on update gets 409
- **Rules:** `update_account` R3 [BUG-874]
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 1 (no error: the duplicate code is stored)

**Given**
1. A = account, but `account_code "SUP-001"`.
2. B = account, but `name "Beta Traders"`, `account_code "SUP-002"`.

**When**
- `svc.update_account(db, account_id=B.id, account_in=AccountUpdate(account_code="SUP-001"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `ConflictError`.
2. raises: `exc.value.detail == "Account code 'SUP-001' already exists"`.
3. re-read B: `account_code == "SUP-002"`.

### ASV-U-13 — client IP and user agent reach the audit row
- **Rules:** `update_account` R4 [BUG-140]
- **Kind:** bug
- **Expect:** xfail BUG-140
- **Fails today on:** Then 1 (the call raises TypeError: no such parameters)

**Given**
1. A = account.

**When**
- `result = svc.update_account(db, account_id=A.id, account_in=AccountUpdate(name="Acme Limited"), workspace_id=W1.id, user_id=U1.id, ip_address="203.0.113.7", user_agent="UA/1.0")`.

**Then**
1. returns: `result.id == A.id`.
2. committed: audit(A) has exactly 1 row with `action_type == "updated"`, `ip_address == "203.0.113.7"`, `user_agent == "UA/1.0"`.

## `AccountService.get_accounts_by_tag_id`

### ASV-T-01 — lists the tag's accounts as dicts (as a set)
- **Rules:** `get_accounts_by_tag_id` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = account.
2. B = account, but `name "Beta Traders"`.
3. C = account, but `name "Gamma Co"`.
4. T = tag.
5. S = tag, but `name "Client"`, `tag_code "client"`.
6. link(A, T).
7. link(B, T).
8. link(C, S).

**When**
- `result = svc.get_accounts_by_tag_id(db, tag_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `{r["id"] for r in result} == {A.id, B.id}`.
2. returns: `len(result) == 2`.
3. returns: every item has `set(r.keys()) == KEYS`.

### ASV-T-02 — a tag without accounts gives []
- **Rules:** `get_accounts_by_tag_id` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = tag.

**When**
- `result = svc.get_accounts_by_tag_id(db, tag_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### ASV-T-03 — skip and limit are passed on: 4 accounts, skip=1, limit=2 give 2 distinct of them
- **Rules:** `get_accounts_by_tag_id` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = tag.
2. A = account; link(A, T).
3. B = account, but `name "Beta Traders"`; link(B, T).
4. C = account, but `name "Gamma Co"`; link(C, T).
5. D = account, but `name "Delta Inc"`; link(D, T).

**When**
- `result = svc.get_accounts_by_tag_id(db, tag_id=T.id, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `len({r["id"] for r in result}) == 2`.
3. returns: `{r["id"] for r in result} <= {A.id, B.id, C.id, D.id}`.

### ASV-T-04 — a missing tag gets 404
- **Rules:** `get_accounts_by_tag_id` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. T = tag.

**When**
- `svc.get_accounts_by_tag_id(db, tag_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Account tag 999999999 not found"`.

### ASV-T-05 — a tag of W0 (built before W1) gets 404
- **Rules:** `get_accounts_by_tag_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = tag, but `workspace_id W0.id`.
2. T = tag.

**When**
- `svc.get_accounts_by_tag_id(db, tag_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Account tag {Z.id} not found"`.

### ASV-T-06 — a tag of W2 (built after W1) gets 404
- **Rules:** `get_accounts_by_tag_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = tag.
2. Z = tag, but `workspace_id W2.id`.

**When**
- `svc.get_accounts_by_tag_id(db, tag_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Account tag {Z.id} not found"`.

### ASV-T-07 — a deleted tag gets 404, nothing listed
- **Rules:** `get_accounts_by_tag_id` R2 [BUG-2982]
- **Kind:** bug
- **Expect:** xfail BUG-2982
- **Fails today on:** Then 1 (no error: the tag's accounts are listed)

**Given**
1. A = account.
2. T = tag, but `is_active False`.
3. link(A, T).

**When**
- `svc.get_accounts_by_tag_id(db, tag_id=T.id, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Account tag {T.id} not found"`.

### ASV-T-08 — a read neither commits nor rolls back; a pending edit stays
- **Rules:** `get_accounts_by_tag_id` R4; TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = account.
2. T = tag.
3. (after the commit point) `A.city = "Khulna"` in memory, not flushed.

**When**
- `svc.get_accounts_by_tag_id(db, tag_id=T.id, workspace_id=W1.id)`, inside **spies**.

**Then**
1. mock called: `cm.call_count == 0`.
2. mock called: `rb.call_count == 0`.
3. session: `A in db.dirty`.

### ASV-T-09 — each by-tag item carries its tag entries with all six keys and stored values
- **Rules:** `get_accounts_by_tag_id` R3; Facts (account dict)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = account.
2. T = tag, but `color "#ff0000"`, `icon "truck"`.
3. link(A, T).

**When**
- `result = svc.get_accounts_by_tag_id(db, tag_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0]["account_tags"] == [{"id": T.id, "name": "Supplier", "tag_code": "supplier", "color": "#ff0000", "icon": "truck", "is_system_tag": False}]`.

### ASV-T-10 — the default limit is 100: 101 tagged accounts give 100
- **Rules:** `get_accounts_by_tag_id` R3 (signature default `limit=100`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = tag.
2. 101 rows, by `add_all`: k = 1 … 101, account, but `name f"a{k:03d}"`; flushed.
3. 101 rows, by `add_all`: link(Ak, T) for each account Ak of line 2.

**When**
- `result = svc.get_accounts_by_tag_id(db, tag_id=T.id, workspace_id=W1.id)` (no `skip`, no `limit`).

**Then**
1. returns: `len(result) == 100`.

## `AccountService.assign_tag`

### ASV-A-01 — the tag is attached, committed, and listed in the returned dict
- **Rules:** `assign_tag` R1; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = account.
2. T = tag.

**When**
- `result = svc.assign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result["id"] == A.id`.
2. returns: `[t["id"] for t in result["account_tags"]] == [T.id]`.
3. committed: `account_tag_assignments` rows with `account_id == A.id`, `tag_id == T.id`: exactly 1, `assigned_by == U1.id`.
4. committed: re-read T: `usage_count == 1`.

### ASV-A-02 — an already-assigned tag: no change, the dict lists it once
- **Rules:** `assign_tag` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = account.
2. T = tag, but `usage_count 1`.
3. link(A, T).

**When**
- `result = svc.assign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[t["id"] for t in result["account_tags"]] == [T.id]`.
2. committed: `account_tag_assignments` rows with `account_id == A.id`: exactly 1, `assigned_by == U2.id`, `assigned_at == T0`.
3. committed: re-read T: `usage_count == 1`.

### ASV-A-03 — a missing account gets 404, rolled back
- **Rules:** `assign_tag` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = tag.
2. X (after the commit point).

**When**
- `svc.assign_tag(db, account_id=MISSING, tag_id=T.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == "Account 999999999 not found"`.
3. session: `x_gone`.
4. nothing written: nothing written.

### ASV-A-04 — an account of W2 gets the same 404
- **Rules:** `assign_tag` R2, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = tag.
2. Z = account, but `workspace_id W2.id`.

**When**
- `svc.assign_tag(db, account_id=Z.id, tag_id=T.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Account {Z.id} not found"`.
3. nothing written: nothing written.

### ASV-A-05 — a soft-deleted account gets 404
- **Rules:** `assign_tag` R2, Errors row 1 [BUG-863]
- **Kind:** bug
- **Expect:** xfail BUG-863
- **Fails today on:** Then 1 (no error: the tag is attached)

**Given**
1. A = account, gone.
2. T = tag.

**When**
- `svc.assign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Account {A.id} not found"`.
3. nothing written: nothing written.

### ASV-A-06 — a missing tag gets 404 with the tag text
- **Rules:** `assign_tag` R2, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = account.

**When**
- `svc.assign_tag(db, account_id=A.id, tag_id=MISSING, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == "Account tag 999999999 not found"`.
3. nothing written: nothing written.

### ASV-A-07 — a tag of W0 gets 404
- **Rules:** `assign_tag` R2, Errors row 2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = tag, but `workspace_id W0.id`.
2. A = account.

**When**
- `svc.assign_tag(db, account_id=A.id, tag_id=Z.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Account tag {Z.id} not found"`.
3. nothing written: nothing written.

### ASV-A-08 — an inactive tag gets 422, rolled back
- **Rules:** `assign_tag` R2, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. A = account.
2. T = tag, but `is_active False`.
3. X (after the commit point).

**When**
- `svc.assign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `BusinessRuleError`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == f"Account tag {T.id} is not active"`.
4. session: `x_gone`.
5. nothing written: nothing written.

### ASV-A-09 — the "not found" match is case-sensitive and anywhere in the text
- **Rules:** `assign_tag` R2
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. A = account.
2. T = tag.
3. `E = ValueError("Account 5 Not Found")`.

**When**
- `svc.assign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id, user_id=U1.id)`, with **mgr raises E on assign_tag**.

**Then**
1. raises: `BusinessRuleError`.
2. raises: `exc.value.detail == "Account 5 Not Found"`.

### ASV-A-10 — "not found" in the middle of the text gives 404 with that text
- **Rules:** `assign_tag` R2
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. A = account.
2. T = tag.
3. `E = ValueError("Row was not found here")`.

**When**
- `svc.assign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id, user_id=U1.id)`, with **mgr raises E on assign_tag**.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == "Row was not found here"`.

### ASV-A-11 — any other exception passes unchanged, every pending change discarded
- **Rules:** `assign_tag` R3; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. A = account.
2. T = tag.
3. X (after the commit point).
4. `E = RuntimeError("boom")`.

**When**
- `svc.assign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id, user_id=U1.id)`, with **mgr raises E on assign_tag**.

**Then**
1. raises: `RuntimeError`.
2. raises: `exc.value is E`.
3. session: `x_gone`.
4. nothing written: nothing written.

### ASV-A-12 — a failing read after the commit reaches the caller; the assignment stays saved
- **Rules:** `assign_tag` R4, R4a; TC5
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. A = account.
2. T = tag.
3. `E = RuntimeError("boom")`.

**When**
- `svc.assign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id, user_id=U1.id)`, inside `with pytest.raises(RuntimeError) as exc:` around `with patch.object(svc, "get_account_with_tags", side_effect=E):`.

**Then**
1. raises: `exc.value is E`.
2. committed: `account_tag_assignments` rows with `account_id == A.id`, `tag_id == T.id`: exactly 1.
3. committed: re-read T: `usage_count == 1`.

### ASV-A-13 — a "not found" ValueError from the read becomes 404; the assignment stays saved
- **Rules:** `assign_tag` R4a
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. A = account.
2. T = tag.
3. `E = ValueError("Account 5 not found")`.

**When**
- `svc.assign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id, user_id=U1.id)`, inside `with pytest.raises(NotFoundError) as exc:` around `with patch.object(svc, "get_account_with_tags", side_effect=E):`.

**Then**
1. raises: `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Account 5 not found"`.
3. committed: `account_tag_assignments` rows with `account_id == A.id`, `tag_id == T.id`: exactly 1.

### ASV-A-14 — another ValueError from the read becomes 422; the assignment stays saved
- **Rules:** `assign_tag` R4a
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. A = account.
2. T = tag.
3. `E = ValueError("bad state")`.

**When**
- `svc.assign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id, user_id=U1.id)`, inside `with pytest.raises(BusinessRuleError) as exc:` around `with patch.object(svc, "get_account_with_tags", side_effect=E):`.

**Then**
1. raises: `exc.value.status_code == 422`.
2. raises: `exc.value.detail == "bad state"`.
3. committed: re-read T: `usage_count == 1`.

## `AccountService.unassign_tag`

### ASV-N-01 — the tag is removed and committed
- **Rules:** `unassign_tag` R1; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = account.
2. T = tag, but `usage_count 1`.
3. link(A, T).

**When**
- `result = svc.unassign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id)` (no `user_id`: today's signature; this card gains `user_id=U1.id` with the BUG-873 fix).

**Then**
1. returns: `result is None`.
2. committed: `account_tag_assignments` rows with `account_id == A.id`: exactly 0.
3. committed: re-read T: `usage_count == 0`.

### ASV-N-02 — a missing account gets 404, rolled back
- **Rules:** `unassign_tag` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. T = tag.
2. X (after the commit point).

**When**
- `svc.unassign_tag(db, account_id=MISSING, tag_id=T.id, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == "Account 999999999 not found"`.
3. session: `x_gone`.

### ASV-N-03 — an account of W2 gets the same 404, its link kept
- **Rules:** `unassign_tag` R2, Errors
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = account, but `workspace_id W2.id`.
2. T = tag, but `workspace_id W2.id`, `usage_count 1`.
3. link(Z, T), but `workspace_id W2.id`.

**When**
- `svc.unassign_tag(db, account_id=Z.id, tag_id=T.id, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Account {Z.id} not found"`.
3. nothing written: nothing written.

### ASV-N-04 — a tag that is not assigned gets 404 with the new text
- **Rules:** `unassign_tag` R2 [BUG-879]
- **Kind:** bug
- **Expect:** xfail BUG-879
- **Fails today on:** Then 1 (a BusinessRuleError 422 "is not assigned" is raised)

**Given**
1. A = account.
2. T = tag.

**When**
- `svc.unassign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Tag {T.id} assignment not found for account {A.id}"`.
3. nothing written: nothing written.

### ASV-N-05 — a soft-deleted account gets 404, its link kept
- **Rules:** `unassign_tag` R2, Errors [BUG-863]
- **Kind:** bug
- **Expect:** xfail BUG-863
- **Fails today on:** Then 1 (no error: the link is removed)

**Given**
1. A = account, gone.
2. T = tag, but `usage_count 1`.
3. link(A, T).

**When**
- `svc.unassign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Account {A.id} not found"`.
3. nothing written: nothing written.

### ASV-N-06 — any other exception passes unchanged, every pending change discarded
- **Rules:** `unassign_tag` R3; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. A = account.
2. T = tag, but `usage_count 1`.
3. link(A, T).
4. X (after the commit point).
5. `E = RuntimeError("boom")`.

**When**
- `svc.unassign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id)`, with **mgr raises E on unassign_tag**.

**Then**
1. raises: `exc.value is E`.
2. session: `x_gone`.
3. nothing written: nothing written.

### ASV-N-07 — user_id reaches the manager: audit row and updated_by
- **Rules:** `unassign_tag` R4 [BUG-873]
- **Kind:** bug
- **Expect:** xfail BUG-873
- **Fails today on:** Then 1 (the call raises TypeError: no `user_id` parameter)

**Given**
1. A = account.
2. T = tag, but `usage_count 1`.
3. link(A, T).

**When**
- `result = svc.unassign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result is None`.
2. committed: re-read A: `updated_by == U1.id`.
3. committed: audit(A) has exactly 1 row, `action_type == "updated"`, `performed_by == U1.id`.

### ASV-N-08 — any other ValueError becomes 422 with the manager's text, rolled back
- **Rules:** `unassign_tag` R2 (as `assign_tag` R2)
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. A = account.
2. T = tag.
3. X (after the commit point).
4. `E = ValueError("bad state")`.

**When**
- `svc.unassign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id)`, with **mgr raises E on unassign_tag**.

**Then**
1. raises: `BusinessRuleError`.
2. raises: `exc.value.status_code == 422`.
3. raises: `exc.value.detail == "bad state"`.
4. session: `x_gone`.

### ASV-N-09 — the "not found" match is case-sensitive: "Not Found" gives 422
- **Rules:** `unassign_tag` R2 (as `assign_tag` R2)
- **Kind:** boundary
- **Expect:** pass
- **Author:** claude

**Given**
1. A = account.
2. T = tag.
3. `E = ValueError("Tag 5 Not Found")`.

**When**
- `svc.unassign_tag(db, account_id=A.id, tag_id=T.id, workspace_id=W1.id)`, with **mgr raises E on unassign_tag**.

**Then**
1. raises: `BusinessRuleError`.
2. raises: `exc.value.detail == "Tag 5 Not Found"`.

## `AccountService.delete_account`

### ASV-D-01 — a live account is soft-deleted and committed
- **Rules:** `delete_account` R1; TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = account.

**When**
- `result = svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result is None`.
2. committed: re-read A: `is_deleted is True`, `is_active is False`, `deleted_by == U1.id`, `deleted_at is not None`.
3. committed: audit(A) has exactly 1 row, `action_type == "deleted"`.

### ASV-D-02 — an inactive (not deleted) account is deleted too
- **Rules:** `delete_account` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = account, but `is_active False`.

**When**
- `result = svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result is None`.
2. committed: re-read A: `is_deleted is True`, `deleted_by == U1.id`.

### ASV-D-03 — a missing id gets 404, nothing written
- **Rules:** `delete_account` R2, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = account.
2. X (after the commit point).

**When**
- `svc.delete_account(db, account_id=MISSING, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Account with ID 999999999 not found"`.
4. session: `x_gone`.
5. nothing written: nothing written.

### ASV-D-04 — an account of W0 gets 404, untouched
- **Rules:** `delete_account` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = account, but `workspace_id W0.id`.
2. A = account.

**When**
- `svc.delete_account(db, account_id=Z.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Account with ID {Z.id} not found"`.
3. unchanged: unchanged(Z).

### ASV-D-05 — an account of W2 gets 404, untouched
- **Rules:** `delete_account` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = account.
2. Z = account, but `workspace_id W2.id`.

**When**
- `svc.delete_account(db, account_id=Z.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == f"Account with ID {Z.id} not found"`.
3. unchanged: unchanged(Z).

### ASV-D-06 — a failing commit is rolled back and re-raised
- **Rules:** `delete_account` R6; TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. A = account.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(A).
4. nothing written: nothing written.

### ASV-D-07 — any other exception passes unchanged, every pending change discarded
- **Rules:** `delete_account` R6; TC3
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. A = account.
2. X (after the commit point).
3. `E = RuntimeError("boom")`.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`, with **mgr raises E on delete_account**.

**Then**
1. raises: `exc.value is E`.
2. session: `x_gone`.
3. unchanged: unchanged(A).

### ASV-D-08 — the delete takes no row lock
- **Rules:** `delete_account` R4 (manager R7d; HR-10 not applied)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = account.
2. I = invoice on A, state settled.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`, with the statement recorder.

**Then**
1. statement: no text in `stmts` contains `"FOR UPDATE"` when upper-cased: `all("FOR UPDATE" not in t.upper() for t in stmts)`.
2. committed: re-read A: `is_deleted is True`.

### ASV-D-09 — an already-deleted account gets 400 "already deleted"
- **Rules:** `delete_account` R3, Errors row 2 [BUG-2986]
- **Kind:** bug
- **Expect:** xfail BUG-2986
- **Fails today on:** Then 1 (a bare ValueError is raised, 500 at the API)

**Given**
1. A = account, gone.
2. X (after the commit point).

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == f"Account {A.id} is already deleted"`.
4. re-read A: `deleted_at == T0`, `deleted_by == U2.id`.
5. session: `x_gone`.
6. nothing written: nothing written.

### ASV-D-10 — today's already-deleted refusal still writes nothing
- **Rules:** `delete_account` R3 (companion: nothing written holds before and after)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = account, gone.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`, wrapped in `with pytest.raises(Exception):`.

**Then**
1. re-read A: `deleted_at == T0`, `deleted_by == U2.id`, `is_deleted is True`.
2. nothing written: nothing written.

### ASV-D-11 — an already-deleted account with an open invoice still gets "already deleted"
- **Rules:** `delete_account` R3 (manager R7c) [BUG-2986]
- **Kind:** bug
- **Expect:** xfail BUG-2986
- **Fails today on:** Then 1 (a bare ValueError is raised)

**Given**
1. A = account, gone.
2. I = invoice on A, state draft.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.detail == f"Account {A.id} is already deleted"`.
3. nothing written: nothing written.

### ASV-D-12 — after BUG-862 hides deleted accounts, a second delete still gets 400
- **Rules:** `delete_account` R3 (Q3) [BUG-2986]
- **Kind:** bug
- **Expect:** xfail BUG-2986
- **Fails today on:** Then 1 (the pre-check answers NotFoundError 404)
- **Author:** claude

**Given**
1. A = account, gone.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`, with the race simulation active.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.detail == f"Account {A.id} is already deleted"`.
3. nothing written: nothing written.

### ASV-D-13 — a draft invoice blocks the delete; the blocker is listed
- **Rules:** `delete_account` R4, R5, Errors row 3 [BUG-876]
- **Kind:** bug
- **Expect:** xfail BUG-876
- **Fails today on:** Then 1 (no error: the account is deleted)

**Given**
1. A = account.
2. I = invoice on A, state draft.
3. X (after the commit point).

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == OPEN`.
4. raises: `exc.value.errors == [{"type": "account_invoice", "id": I.id}]`.
5. unchanged: unchanged(A).
6. count: audit(A) has exactly 0 rows.
7. session: `x_gone`.
8. nothing written: nothing written.

### ASV-D-14 — a confirmed unpaid invoice blocks the delete
- **Rules:** `delete_account` R4, R5 [BUG-876]
- **Kind:** bug
- **Expect:** xfail BUG-876
- **Fails today on:** Then 1 (no error: the account is deleted)

**Given**
1. A = account.
2. I = invoice on A, state unpaid.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.detail == OPEN`.
3. raises: `exc.value.errors == [{"type": "account_invoice", "id": I.id}]`.
4. unchanged: unchanged(A).

### ASV-D-15 — a partially paid receivable invoice blocks the delete
- **Rules:** `delete_account` R4, R5 [BUG-876]
- **Kind:** bug
- **Expect:** xfail BUG-876
- **Fails today on:** Then 1 (no error: the account is deleted)

**Given**
1. A = account.
2. I = invoice on A, state partial, but `invoice_type "receivable"`.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.detail == OPEN`.
3. raises: `exc.value.errors == [{"type": "account_invoice", "id": I.id}]`.
4. unchanged: unchanged(A).

### ASV-D-16 — a settled invoice does not block; the invoice is untouched
- **Rules:** `delete_account` R1, R4 (manager R7b)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = account.
2. I = invoice on A, state settled.

**When**
- `result = svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result is None`.
2. committed: re-read A: `is_deleted is True`.
3. committed: re-read I: `invoice_status == "confirmed"`, `paid_amount == Decimal("1000.00")`, `payment_status == "paid"`.

### ASV-D-17 — a voided invoice does not block
- **Rules:** `delete_account` R1, R4 (manager R7b)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = account.
2. I = invoice on A, state voided.

**When**
- `result = svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result is None`.
2. committed: re-read A: `is_deleted is True`.
3. committed: re-read I: `invoice_status == "voided"`.

### ASV-D-18 — another account's open invoice does not block
- **Rules:** `delete_account` R1, R4 (manager R7b)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = account.
2. B = account, but `name "Beta Traders"`.
3. I = invoice on B, state draft.

**When**
- `result = svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result is None`.
2. committed: re-read A: `is_deleted is True`.
3. committed: re-read B: `is_deleted is False`.

### ASV-D-19 — two open invoices are listed by id ascending, inserted in reverse
- **Rules:** `delete_account` R5 [BUG-2984]
- **Kind:** bug
- **Expect:** xfail BUG-2984
- **Fails today on:** Then 1 (no error: the account is deleted)

**Given**
1. A = account.
2. I2 = invoice on A, state unpaid, but `id 900000002`.
3. I1 = invoice on A, state draft, but `id 900000001`.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.errors == [{"type": "account_invoice", "id": 900000001}, {"type": "account_invoice", "id": 900000002}]`.
3. unchanged: unchanged(A).

### ASV-D-20 — only an open invoice carrying W2's workspace_id: one other_workspace entry, no id
- **Rules:** `delete_account` R5, R5a [BUG-2984] (HR-16)
- **Kind:** bug
- **Expect:** xfail BUG-2984
- **Fails today on:** Then 1 (no error: the account is deleted)

**Given**
1. A = account.
2. F = invoice on A, state draft, but `workspace_id W2.id`.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.detail == OPEN`.
3. raises: `exc.value.errors == [{"type": "other_workspace"}]`.
4. unchanged: unchanged(A).

### ASV-D-21 — own open invoice plus a W2 one: own entry, then other_workspace last
- **Rules:** `delete_account` R5 [BUG-2984]
- **Kind:** bug
- **Expect:** xfail BUG-2984
- **Fails today on:** Then 1 (no error: the account is deleted)

**Given**
1. A = account.
2. I = invoice on A, state draft.
3. F = invoice on A, state unpaid, but `workspace_id W2.id`.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.errors == [{"type": "account_invoice", "id": I.id}, {"type": "other_workspace"}]`.

### ASV-D-22 — a W0 invoice with a lower id than the own one: other_workspace still last
- **Rules:** `delete_account` R5 [BUG-2984]
- **Kind:** bug
- **Expect:** xfail BUG-2984
- **Fails today on:** Then 1 (no error: the account is deleted)

**Given**
1. A = account.
2. F = invoice on A, state draft, but `workspace_id W0.id`, `id 900000011`.
3. I = invoice on A, state draft, but `id 900000012`.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.errors == [{"type": "account_invoice", "id": 900000012}, {"type": "other_workspace"}]`.

### ASV-D-23 — two foreign open invoices give one other_workspace entry
- **Rules:** `delete_account` R5, R5a [BUG-2984]
- **Kind:** bug
- **Expect:** xfail BUG-2984
- **Fails today on:** Then 1 (no error: the account is deleted)

**Given**
1. A = account.
2. F0 = invoice on A, state draft, but `workspace_id W0.id`.
3. F2 = invoice on A, state partial, but `workspace_id W2.id`.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.errors == [{"type": "other_workspace"}]`.

### ASV-D-24 — open plus settled and voided: only the open one is listed
- **Rules:** `delete_account` R4, R5 [BUG-2984]
- **Kind:** bug
- **Expect:** xfail BUG-2984
- **Fails today on:** Then 1 (no error: the account is deleted)

**Given**
1. A = account.
2. S = invoice on A, state settled.
3. V = invoice on A, state voided.
4. I = invoice on A, state partial.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.errors == [{"type": "account_invoice", "id": I.id}]`.
3. nothing written: nothing written.

### ASV-D-25 — translation: the manager's open-invoices refusal carries its blockers into errors
- **Rules:** `delete_account` R5 [BUG-2984]
- **Kind:** bug
- **Expect:** xfail BUG-2984
- **Fails today on:** Then 1 (the bare ValueError is re-raised)
- **Author:** claude

**Given**
1. A = account.
2. X (after the commit point).
3. `B = [{"type": "account_invoice", "id": 118}, {"type": "account_invoice", "id": 131}]`; `E = ValueError(OPEN, B)`.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`, with **mgr raises E on delete_account**.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == OPEN`.
4. raises: `exc.value.errors == [{"type": "account_invoice", "id": 118}, {"type": "account_invoice", "id": 131}]`.
5. session: `x_gone`.

### ASV-D-26 — translation: "already deleted" from the manager becomes 400
- **Rules:** `delete_account` R3 [BUG-2986]
- **Kind:** bug
- **Expect:** xfail BUG-2986
- **Fails today on:** Then 1 (the bare ValueError is re-raised)
- **Author:** claude

**Given**
1. A = account.
2. `E = ValueError(f"Account {A.id} is already deleted")`.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`, with **mgr raises E on delete_account**.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.detail == f"Account {A.id} is already deleted"`.
3. unchanged: unchanged(A).

### ASV-D-27 — any other ValueError of the manager passes unchanged
- **Rules:** `delete_account` R6 (Q1: other ValueErrors are not translated)
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. A = account.
2. `E = ValueError("something else")`.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`, with **mgr raises E on delete_account**.

**Then**
1. raises: `ValueError`.
2. raises: `exc.value is E`.
3. unchanged: unchanged(A).

### ASV-D-28 — client IP and user agent reach the audit row
- **Rules:** `delete_account` R7 [BUG-140]
- **Kind:** bug
- **Expect:** xfail BUG-140
- **Fails today on:** Then 1 (the call raises TypeError: no such parameters)

**Given**
1. A = account.

**When**
- `result = svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id, ip_address="203.0.113.7", user_agent="UA/1.0")`.

**Then**
1. returns: `result is None`.
2. committed: audit(A) has exactly 1 row with `action_type == "deleted"`, `ip_address == "203.0.113.7"`, `user_agent == "UA/1.0"`.

### ASV-D-29 — a voided invoice carrying W2's workspace_id blocks nothing
- **Rules:** `delete_account` R5a, R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = account.
2. F = invoice on A, state voided, but `workspace_id W2.id`.

**When**
- `result = svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result is None`.
2. committed: re-read A: `is_deleted is True`.
3. committed: re-read F: `invoice_status == "voided"`, `workspace_id == W2.id`.

### ASV-D-30 — one own open invoice plus two foreign ones: own entry, then one other_workspace
- **Rules:** `delete_account` R5, R5a [BUG-2984]
- **Kind:** bug
- **Expect:** xfail BUG-2984
- **Fails today on:** Then 1 (no error: the account is deleted)

**Given**
1. A = account.
2. F0 = invoice on A, state unpaid, but `workspace_id W0.id`.
3. I = invoice on A, state draft.
4. F2 = invoice on A, state partial, but `workspace_id W2.id`.

**When**
- `svc.delete_account(db, account_id=A.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.detail == OPEN`.
3. raises: `exc.value.errors == [{"type": "account_invoice", "id": I.id}, {"type": "other_workspace"}]`.
4. unchanged: unchanged(A).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_accounts_by_tag_id` R5 [BUG-2983] | `GET /accounts/by-tag/{tag_id}/` (integration) | `limit=0` and `limit=-1` → 422 |
| `get_accounts_with_tags` limit bound [BUG-867] | `GET /accounts/` (integration) | `limit >= 1` |
| `create_account` / `update_account` / `delete_account` R4/R7 [BUG-140] endpoint half | accounts endpoint (FU-2) | the request's client IP / user agent are read and passed |
| `unassign_tag` R4 [BUG-873] endpoint half | accounts endpoint (FU-2) | `current_user.id` passed |
| `get_account_with_tags` R3 / `get_accounts_with_tags` R2 endpoint half [BUG-862, BUG-878] | accounts endpoint (FU-2) | `include_deleted` / `include_inactive` exposed |
| HTTP bodies of translated errors | `tests/unit/core/exceptions.spec.md` | status + `errors` serialisation |
| `get_accounts_hub_page` `has_more` | `GET /accounts/hub/` (integration) | computed by the endpoint |
| `get_accounts_with_tags` R1 order (BUG-866), tag filters | `account_manager.cases.md`, `account.cases.md` (DAO) | order, filters |
| BUG-2985 | frontend | blockers shown in the delete toast / dialog |

## Spec gaps
None open. All four gaps of revision 1 were closed by the spec's Gap log (2026-11-21):

| # | Where | Resolution |
|---|---|---|
| 1 | Facts ("Rows") | G1: Facts name `Account` and `AccountTagAssignment` with their NOT NULL columns and defaults; the cards' assumptions hold. Conventions now name the models. |
| 2 | `assign_tag` R4 (TC5) | G2: the read is `self.get_account_with_tags` inside the `try`, patched on the instance; new R4a. Cards ASV-A-12, A-13, A-14. |
| 3 | `get_account_with_tags` R4 | G3: BUG-865 and BUG-1486 are open today. Strict xfail cards ASV-G-11 (BUG-865) and G-12 (BUG-1486, SQL recorder). |
| 4 | `delete_account` R5 | G4: new R5a confirms a foreign open invoice blocks on its own as the single `other_workspace` entry. D-20, D-23 cite R5a; new D-29, D-30. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_account` | R1 (TC1, TC2) | ASV-C-01, C-02 |
| `create_account` | R2 (TC3, TC4, TC5) | ASV-C-03, C-04, C-05, C-06 |
| `create_account` | R3 [BUG-871 / 874 / 629] | ASV-C-06, C-07, C-08, C-09, C-10, C-11, C-12 |
| `create_account` | R4 [BUG-140] | ASV-C-13 |
| `get_account_with_tags` | R1 | ASV-G-01, G-04 |
| `get_account_with_tags` | R2, Errors | ASV-G-05, G-06, G-07 |
| `get_account_with_tags` | R3 [BUG-862] | ASV-G-08, G-09 |
| `get_account_with_tags` | R4 [BUG-865, BUG-1486] | ASV-G-01, G-02, G-03, G-11, G-12 |
| `get_account_with_tags` | R5 (TC6) | ASV-G-10 |
| `get_accounts_with_tags` | R1 | ASV-L-01 … L-06, L-09, L-10 |
| `get_accounts_with_tags` | R2 [BUG-878] | ASV-L-07 |
| `get_accounts_with_tags` | R3 (TC6) | ASV-L-08 |
| `_account_dict_with_tags` | R1 | ASV-M-01, M-02, M-03 |
| `_rollup_from_subquery_row` | R1 | ASV-R-01 |
| `_rollup_from_subquery_row` | R2 | ASV-R-02 … R-05 |
| `get_accounts_hub_page` | R1 | ASV-H-01, H-03, H-05 |
| `get_accounts_hub_page` | R2 | ASV-H-01, H-02, H-03 |
| `get_accounts_hub_page` | R3 (TC6) | ASV-H-04 |
| `update_account` | R1 (TC1, TC2) | ASV-U-01 |
| `update_account` | R2 (TC3, TC4) | ASV-U-02, U-03 |
| `update_account` | R3 [BUG-2986 / 871 / 874 / 629] | ASV-U-03 … U-12 |
| `update_account` | R4 [BUG-140] | ASV-U-13 |
| `get_accounts_by_tag_id` | R1, Errors | ASV-T-04, T-05, T-06 |
| `get_accounts_by_tag_id` | R2 [BUG-2982] | ASV-T-07 |
| `get_accounts_by_tag_id` | R3 | ASV-T-01, T-02, T-03, T-09, T-10 |
| `get_accounts_by_tag_id` | R4 (TC6) | ASV-T-08 |
| `get_accounts_by_tag_id` | R5 [BUG-2983] | Deferred |
| `assign_tag` | R1 | ASV-A-01, A-02 |
| `assign_tag` | R2, Errors rows 1–3 | ASV-A-03 … A-10 |
| `assign_tag` | R3 (TC3) | ASV-A-11 |
| `assign_tag` | R4 (TC5), R4a | ASV-A-12, A-13, A-14 |
| `unassign_tag` | R1 | ASV-N-01 |
| `unassign_tag` | R2 [BUG-879, BUG-863], Errors | ASV-N-02 … N-05, N-08, N-09 |
| `unassign_tag` | R3 | ASV-N-06 |
| `unassign_tag` | R4 [BUG-873] | ASV-N-07 |
| `delete_account` | R1 | ASV-D-01, D-02, D-16, D-17, D-18 |
| `delete_account` | R2, Errors row 1 | ASV-D-03, D-04, D-05 |
| `delete_account` | R3 [BUG-2986], Errors row 2 | ASV-D-09, D-10, D-11, D-12, D-26 |
| `delete_account` | R4 [BUG-876] | ASV-D-08, D-13, D-14, D-15, D-24 |
| `delete_account` | R5 [BUG-2984], Errors row 3 | ASV-D-13, D-19 … D-25, D-30 |
| `delete_account` | R5a [BUG-2984] | ASV-D-20, D-23, D-29, D-30 |
| `delete_account` | R6 (TC3, TC4) | ASV-D-06, D-07, D-27 |
| `delete_account` | R7 [BUG-140] | ASV-D-28 |
