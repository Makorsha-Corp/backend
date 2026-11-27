# Test cases — `app/managers/account_manager.py`

> **Spec:** `tests/unit/managers/account_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 — spec Gap log G1–G8 closed all 8 gaps of revision 1. G1/G8: `delete_account` R7, R7a–R7d → new ACC-D-13…21. G2: exact duplicate-code text in ACC-C-21, C-22, U-44, U-45; `create_account` R11b / `update_account` R20b and the rest of R11a / R20a → new ACC-C-30…35, ACC-U-49…54. G3: `unassign_tag` `user_id` is required → new ACC-UN-14. G4: tag column is `tag_code` (was `code`) in Conventions and 12 cards. G6: `AccountManager()` in Conventions. G7: ACC-S-26 and ACC-T-06 rebuilt so today's order cannot match by accident. No ID renumbered or retired.
> **Revision:** 3 (2026-11-03) — spec Gap log C1, C2 (corrections from the `account_tag_assignment` DAO describer). C1: `get_tags_for_account` R5 cites BUG-1486 (was BUG-719, an inventory bug) and gained "system tags are not grouped first"; ACC-T-06, T-07 re-tagged and made non-strict, `Author: claude` (today's tag order is not reliably the insertion order), new ACC-T-09 (system tag not first, non-strict) and ACC-T-10 (strict: the SELECT carries an `ORDER BY`). C2: new `update_account` R13a [BUG-1487] → new ACC-U-55 (xfail) and ACC-U-56 (pass). No ID renumbered or retired. Done by one agent, lighter than an independent design round.
> **Revision:** 4 (2026-11-22) — spec Gap log C3 (routed by the `account_service` verifier). Re-citation only, behaviour unchanged: ACC-C-14, C-15, U-38, AT-08, AT-10 (xfail) and the coverage rows for `create_account` R6b, `update_account` R11a and `_assign_tags_to_account` R6 (which also list the pass cards ACC-U-39, AT-09; they carry no xfail, so nothing else changed in them) now cite BUG-2987 (was BUG-629); the deferred `update_account` / `delete_account` R1a rows cite BUG-2986 (was BUG-124). No case added, renumbered or retired. Done by one agent.
> **Counts:** 193 cases · 101 expected-to-pass · 92 expected-to-fail (bugs; 3 of them non-strict) · 10 deferred

## Reviewer summary
- **Per callable:** `create_account` 35 cases (20 bug) · `update_account` 56 (31 bug) · `get_account` 7 (3 bug) · `search_accounts` 26 (11 bug) · `delete_account` 21 (8 bug) · `_assign_tags_to_account` 10 (5 bug) · `assign_tag` 14 (3 bug) · `unassign_tag` 14 (6 bug) · `get_tags_for_account` 10 (5 bug).
- **Notable design choices** (each a best-practice default, delegated by reviewer):
  - No race simulations. The intended account-code unique index is tested directly on the table (ACC-C-26, C-34, C-35); the existing `(account_id, tag_id)` constraint likewise (ACC-A-14).
  - Blank account codes: pass cards ACC-C-25, C-33, C-34, U-54 use rows whose stored code is `""` / spaces (what the code stores today), so the fix must tolerate such legacy rows; they assert "blank", not `NULL` — `NULL` is asserted only in the xfail cards.
  - `delete_account` R7: the "refused" cards are xfail; "not refused" (paid, voided, another account's invoice) and "R1–R3 win over the invoice check" are pass cards that hold today and guard the fix. Invoices are inserted directly in the spec's five consistent states only.
  - `unassign_tag`: pass cards call it WITHOUT the future required `user_id` so they protect today's behavior; they gain `user_id=U2.id` in the change that fixes BUG-873 (spec note G3), and ACC-UN-14 (call without it → `TypeError`) starts passing then. No case for `user_id=None`: the spec defines no runtime rejection.
  - Every bug rule is split: what works today (error type, resulting tag set, the audit keys written today, NULL ip/user agent) is in a pass card; only the buggy assertion is in the xfail card.
  - Order cards (ACC-S-20, S-26, T-06, T-07, T-09) follow spec note G7: intended order is neither id-ascending nor id-descending; search cards use 6–7 rows (chance match ≤ 1 in 720). The tag-order cards T-06, T-07, T-09 are non-strict (revision 3: the tag order is not reliably the insertion order); the strict alarm for BUG-1486 is ACC-T-10, which checks the SQL for an `ORDER BY`. S-20 / S-26 were not revisited in revision 3.
  - "Flushed, not committed" is checked through re-reads in the same session; "not committed" itself is not asserted (the harness rolls back).
  - Field-length limits of the Inputs tables are not rules and got no cases, except the `""` name boundary named in R2 / R6.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `ACC` = account_manager. `C` create_account · `U` update_account · `G` get_account · `S` search_accounts · `D` delete_account · `AT` _assign_tags_to_account · `A` assign_tag · `UN` unassign_tag · `T` get_tags_for_account.

**Actors and fixed values.**
- W1, W2 = two `workspaces` rows. U1, U2 = two `profiles` rows: U1 creates every Given row, U2 is the acting user of every call.
- M = `AccountManager()` — no constructor arguments (`from app.managers.account_manager import AccountManager`). `session` = the test's real database session, always the first argument.
- `AccountCreate`, `AccountUpdate` = the schemas in `app.schemas.account`.
- MISSING = `999999999`, MISSING2 = `999999998`: ids that no row of any table has.
- T0 = `datetime(2026, 1, 1, 9, 0, 0)`, NOW = `datetime(2026, 3, 1, 10, 0, 0)` (both naive).
- FILLED = these 13 keyword values: `account_code="SUP-001"`, `primary_contact_person="Rahim"`, `primary_email="rahim@acme.test"`, `primary_phone="+8801700000001"`, `secondary_contact_person="Karim"`, `secondary_email="karim@acme.test"`, `secondary_phone="+8801700000002"`, `address="12 Lake Road"`, `city="Dhaka"`, `country="Bangladesh"`, `postal_code="1207"`, `payment_preferences="Bank transfer, 30 days"`, `bank_details="City Bank 001-234"`.
- **the 13 optional fields** = the 13 fields named in FILLED.

**Externals.** Every test patches `app.managers.account_manager.utcnow` and `app.utils.audit_logger.utcnow` to return NOW. Nothing else is mocked.

**Given rows.** A row exists only if the card's Given lists it. Rows are inserted directly into the tables (never through M) and flushed in the order written, so ids rise in that order. A card names every field that differs from these defaults:
- **default account** = `accounts` row: `name "Acme Ltd"`, `workspace_id W1.id`, the 13 optional fields `None`, `allow_invoices True`, `is_active True`, `is_deleted False`, `created_by U1.id`, `updated_by None`, `updated_at None`, `deleted_at None`, `deleted_by None`.
- **filled account** = default account, but the 13 optional fields have the FILLED values.
- **deleted** (said of an account) = `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`.
- A1 = default account. A2 = default account, but `name "Beta Co"`. A9 = default account, but `name "Zeta Corp"`, `workspace_id W2.id`.
- **default tag** = `account_tags` row, inserted through the model `AccountTag` (`app.models.account_tag`): `workspace_id W1.id`, `is_active True`, `usage_count 0`, `is_system_tag False`; `name` and `tag_code` are always given (the column is `tag_code`, not `code`). The table has no unique constraint: two tags may share a `tag_code` or a name.
- T1 = default tag, `name "Supplier"`, `tag_code "supplier"`. T2 = default tag, `name "Client"`, `tag_code "client"`. T3 = default tag, `name "Legacy"`, `tag_code "legacy"`, but `is_active False`. T9 = default tag, `name "Supplier"`, `tag_code "supplier"`, but `workspace_id W2.id`.
- **A has T** = `account_tag_assignments` row: `account_id A.id`, `tag_id T.id`, `workspace_id` = A's workspace, `assigned_by U1.id`, `assigned_at T0`. Inserting it does NOT change `usage_count`; the Given states each count.
- **invoice of A** = `account_invoices` row, inserted through the model `AccountInvoice` (`app.models.account_invoice`), never through a manager: `workspace_id` = A's workspace, `account_id A.id`, `invoice_type "payable"`, `invoice_amount Decimal("1000.00")`, `invoice_date date(2026, 1, 15)`, `allow_payments True`, plus exactly one state (always set all three columns):
  **draft** = `invoice_status "draft"`, `paid_amount Decimal("0.00")`, `payment_status "unpaid"` · **unpaid** = `"confirmed"`, `0.00`, `"unpaid"` · **partial** = `"confirmed"`, `400.00`, `"partial"` · **paid** = `"confirmed"`, `1000.00`, `"paid"` · **voided** = `"voided"`, `0.00`, `"unpaid"`.
- OPEN_INVOICES = the text `Account has open invoices — settle or void them first` (the dash is an em dash, U+2014).

**Named checks.**
- **re-read X** = `session.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call.
- **tags(A)** = sorted list of `tag_id` of the `account_tag_assignments` rows with `account_id A.id`.
- **audit(A)** = the `financial_audit_logs` rows with `entity_type "account"` and `entity_id A.id`.
- **standard audit fields** = `entity_type == "account"`, `entity_id` = the account's id, `workspace_id == W1.id`, `related_entity_type is None`, `related_entity_id is None`.
- **nothing written** = these equal their values before the call: number of rows in `accounts`, in `account_tag_assignments` and in `financial_audit_logs` (all workspaces), and `usage_count` of every tag in Given.
- **SNAP(k=v, …)** = the full audit snapshot: a dict with exactly 17 keys — `name "Acme Ltd"`, the 13 optional fields `None`, `allow_invoices True`, `is_active True`, `tag_ids []` — with the listed keys replaced. `tag_ids` is a list of ints in ascending order.
- **SQL of the call** = the text of every SQL statement the session sends during the When, recorded with a `before_cursor_execute` listener on the session's connection; **tags SELECT** = the one recorded `SELECT` whose text contains `account_tags`.
- `raises: ValueError "text"` = `str(exc.value) == "text"` exactly, with `{X.id}` replaced by the real id. After a `ValueError`, keep using the same session for the remaining checks.
- `raises: ValidationError` = `pydantic.ValidationError`.
- `raises: IntegrityError on flush` = wrap the statement: `with pytest.raises(IntegrityError): with session.begin_nested(): …`.
- Search / list results: compare the **set** of names (or ids) unless the line says "in order" (then the exact list).

**Targets.** "target `schema`" = only build the schema object; M is not called. "target `database`" = only insert rows directly; M is not called.

**xfail cards.** Write the call exactly as shown, even when it uses a parameter that does not exist yet (`ip_address`, `user_agent`, `include_deleted`, `include_inactive`, `user_id` on `unassign_tag`); the resulting `TypeError` is the expected failure.

## `AccountManager.create_account`

### ACC-C-01 — minimal create stores the account with defaults and system fields
- **Rules:** create_account R1, R3, R4, R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 and W2 have no accounts, no tags.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd"), workspace_id=W1.id, user_id=U2.id)` — only `name` is sent.

**Then**
1. returns: an Account whose `id` is not None.
2. re-read that row: `name == "Acme Ltd"`, each of the 13 optional fields `is None`, `allow_invoices is True`.
3. re-read that row: `workspace_id == W1.id`, `created_by == U2.id`, `is_active is True`, `is_deleted is False`, `created_at is not None`.
4. re-read that row: `updated_at is None`, `updated_by is None`, `deleted_at is None`, `deleted_by is None`.
5. count: `accounts` has exactly 1 row.
6. count: `account_tag_assignments` has 0 rows.

### ACC-C-02 — every sent field is stored exactly as sent
- **Rules:** create_account R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no accounts.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd", **FILLED, allow_invoices=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: an Account whose `id` is not None.
2. re-read that row: `name == "Acme Ltd"`, `allow_invoices is False`.
3. re-read that row: each of the 13 optional fields `==` its FILLED value (assert all 13, one by one).
4. count: `accounts` has exactly 1 row.

### ACC-C-03 — the account is created in the workspace passed as argument
- **Rules:** create_account R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 (in W1).

**When**
- `M.create_account(session, account_data=AccountCreate(name="Zeta Corp"), workspace_id=W2.id, user_id=U2.id)`.

**Then**
1. returns: an Account whose `id` is not None and `!= A1.id`.
2. re-read that row: `workspace_id == W2.id`, `name == "Zeta Corp"`, `created_by == U2.id`.
3. count: `accounts` rows with `workspace_id W2.id` == 1.
4. count: `accounts` rows with `workspace_id W1.id` == 1.
5. unchanged: unchanged(A1).

### ACC-C-04 — name is stored trimmed
- **Rules:** create_account R2 [BUG-860], R8
- **Kind:** bug
- **Expect:** xfail BUG-860
- **Fails today on:** Then 2 (the name is stored as typed, with the outer spaces)

**Given**
1. W1 has no accounts.

**When**
- `M.create_account(session, account_data=AccountCreate(name="  Acme  Ltd  "), workspace_id=W1.id, user_id=U2.id)` — two spaces before, between and after.

**Then**
1. returns: an Account whose `id` is not None.
2. re-read that row: `name == "Acme  Ltd"` (outer spaces removed, the two inner spaces kept).
3. audit: audit(that account) has exactly 1 row; `description == "Account 'Acme  Ltd' created"`.

### ACC-C-05 — inner whitespace and case of the name are kept
- **Rules:** create_account R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no accounts.

**When**
- `M.create_account(session, account_data=AccountCreate(name="acme  LTD"), workspace_id=W1.id, user_id=U2.id)` — two inner spaces, no outer spaces.

**Then**
1. returns: an Account whose `id` is not None.
2. re-read that row: `name == "acme  LTD"`.

### ACC-C-06 — whitespace-only name is rejected by the schema
- **Rules:** create_account R2 [BUG-860]
- **Kind:** bug
- **Expect:** xfail BUG-860
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. W1 has no accounts.

**When**
- build `AccountCreate(name="   ")` (three spaces; target `schema`).

**Then**
1. raises: `ValidationError`.
2. count: `accounts` has 0 rows.

### ACC-C-07 — empty name is rejected by the schema
- **Rules:** create_account R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no accounts.

**When**
- build `AccountCreate(name="")` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. count: `accounts` has 0 rows.

### ACC-C-08 — valid tag ids are attached and counted
- **Rules:** create_account R6; _assign_tags_to_account R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1, `usage_count 0`.
2. T2, `usage_count 3`.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd", tag_ids=[T1.id, T2.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: an Account whose `id` is not None (call it N).
2. count: tags(N) `== [T1.id, T2.id]`.
3. re-read both assignment rows of N: `workspace_id == W1.id`, `assigned_by == U2.id`, `assigned_at is not None`.
4. re-read T1: `usage_count == 1`.
5. re-read T2: `usage_count == 4`.

### ACC-C-09 — the same tag id twice gives one assignment
- **Rules:** create_account R6; _assign_tags_to_account R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1, `usage_count 0`.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd", tag_ids=[T1.id, T1.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: an Account whose `id` is not None (call it N).
2. count: tags(N) `== [T1.id]` (exactly 1 assignment row).
3. re-read T1: `usage_count == 1`.

### ACC-C-10 — empty tag list attaches nothing
- **Rules:** create_account R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1, `usage_count 2`.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd", tag_ids=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: an Account whose `id` is not None.
2. count: `account_tag_assignments` has 0 rows.
3. re-read T1: `usage_count == 2`.

### ACC-C-11 — unknown tag id rejects the create
- **Rules:** create_account R6a [BUG-871]; Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-871
- **Fails today on:** Then 1 (no error is raised; the id is skipped and the account is created)

**Given**
1. W1 has no accounts, no tags.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd", tag_ids=[MISSING]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account tag 999999999 not found"`.
2. nothing written: `accounts` 0 rows, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.

### ACC-C-12 — tag of another workspace rejects the create
- **Rules:** create_account R6a [BUG-871]; Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-871
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. T9 (in W2), `usage_count 1`.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd", tag_ids=[T9.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account tag {T9.id} not found"`.
2. nothing written: `accounts` 0 rows, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.
3. re-read T9: `usage_count == 1`.

### ACC-C-13 — one unknown id rejects the whole list, valid tags are not attached
- **Rules:** create_account R6a [BUG-871]; _assign_tags_to_account R7 [BUG-871]
- **Kind:** bug
- **Expect:** xfail BUG-871
- **Fails today on:** Then 1 (no error is raised; T1 is attached)

**Given**
1. T1, `usage_count 0`.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd", tag_ids=[T1.id, MISSING]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account tag 999999999 not found"`.
2. nothing written: `accounts` 0 rows, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.
3. re-read T1: `usage_count == 0`.

### ACC-C-14 — inactive tag rejects the create
- **Rules:** create_account R6b [BUG-2987]; Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-2987
- **Fails today on:** Then 1 (no error is raised; the inactive tag is attached)

**Given**
1. T3 (inactive), `usage_count 0`.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd", tag_ids=[T3.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account tag {T3.id} is not active"`.
2. nothing written: `accounts` 0 rows, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.
3. re-read T3: `usage_count == 0`.

### ACC-C-15 — one inactive tag rejects the whole list, valid tags are not attached
- **Rules:** create_account R6b [BUG-2987]; _assign_tags_to_account R7
- **Kind:** bug
- **Expect:** xfail BUG-2987
- **Fails today on:** Then 1 (no error is raised; both tags are attached)

**Given**
1. T1, `usage_count 0`.
2. T3 (inactive), `usage_count 0`.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd", tag_ids=[T1.id, T3.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account tag {T3.id} is not active"`.
2. nothing written: `accounts` 0 rows, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.
3. re-read T1: `usage_count == 0`.
4. re-read T3: `usage_count == 0`.

### ACC-C-16 — create writes one "created" audit row
- **Rules:** create_account R8, R9 (keys written today), R10 (not passed)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no accounts; `financial_audit_logs` has 0 rows.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd", primary_contact_person="Rahim", primary_email="rahim@acme.test", address="12 Lake Road", city="Dhaka", country="Bangladesh"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: an Account whose `id` is not None (call it N).
2. audit: `financial_audit_logs` has exactly 1 row, and it is in audit(N).
3. audit: that row has the standard audit fields.
4. audit: `action_type == "created"`, `description == "Account 'Acme Ltd' created"`, `performed_by == U2.id`, `performed_at == NOW`.
5. audit: `ip_address is None`, `user_agent is None`.
6. audit: `changes` has the key `"after"` and does NOT have the key `"before"`.
7. audit: `changes["after"]["name"] == "Acme Ltd"`, `["primary_contact_person"] == "Rahim"`, `["primary_email"] == "rahim@acme.test"`, `["address"] == "12 Lake Road"`, `["city"] == "Dhaka"`, `["country"] == "Bangladesh"`.

### ACC-C-17 — audit row holds the full snapshot including tags
- **Rules:** create_account R9 [BUG-872]
- **Kind:** bug
- **Expect:** xfail BUG-872
- **Fails today on:** Then 3 (`changes["after"]` has only 6 keys and no tag ids)

**Given**
1. T1, `usage_count 0`.
2. T2, `usage_count 0`.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd", **FILLED, allow_invoices=False, tag_ids=[T2.id, T1.id]), workspace_id=W1.id, user_id=U2.id)` — tag ids sent in descending order.

**Then**
1. returns: an Account whose `id` is not None (call it N).
2. audit: audit(N) has exactly 1 row.
3. audit: `changes == {"after": SNAP(**FILLED, allow_invoices=False, tag_ids=[T1.id, T2.id])}`.

### ACC-C-18 — full snapshot shows unset fields as null and an empty tag list
- **Rules:** create_account R9 [BUG-872]
- **Kind:** bug
- **Expect:** xfail BUG-872
- **Fails today on:** Then 3 (`changes["after"]` has only 6 keys)

**Given**
1. W1 has no accounts.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd"), workspace_id=W1.id, user_id=U2.id)` — only `name` is sent.

**Then**
1. returns: an Account whose `id` is not None (call it N).
2. audit: audit(N) has exactly 1 row.
3. audit: `changes == {"after": SNAP()}` (all 17 keys present; the 13 optional fields `None`, `tag_ids == []`).

### ACC-C-19 — client IP and user agent are written to the audit row
- **Rules:** create_account R10 [BUG-140]
- **Kind:** bug
- **Expect:** xfail BUG-140
- **Fails today on:** Then 1 (the call raises `TypeError`: the parameters do not exist)

**Given**
1. W1 has no accounts.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd"), workspace_id=W1.id, user_id=U2.id, ip_address="203.0.113.7", user_agent="pytest-agent/1.0")`.

**Then**
1. returns: an Account whose `id` is not None (call it N).
2. audit: audit(N) has exactly 1 row.
3. audit: `ip_address == "203.0.113.7"`, `user_agent == "pytest-agent/1.0"`.

### ACC-C-20 — a second account with the same name is allowed
- **Rules:** create_account R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 (`name "Acme Ltd"`, in W1).

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: an Account whose `id` is not None and `!= A1.id`.
2. count: `accounts` rows with `workspace_id W1.id` and `name "Acme Ltd"` == 2.

### ACC-C-21 — duplicate account code is rejected
- **Rules:** create_account R11a [BUG-874]; Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 1 (no error is raised; the duplicate is created)

**Given**
1. A1, but `account_code "SUP-001"`.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Beta Traders", account_code="SUP-001"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account code 'SUP-001' already exists"`.
2. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.
3. unchanged: unchanged(A1).

### ACC-C-22 — account code is compared trimmed and case-insensitively
- **Rules:** create_account R11a [BUG-874]; Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. A1, but `account_code "SUP-001"`.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Beta Traders", account_code=" sup-001 "), workspace_id=W1.id, user_id=U2.id)` — lower case, one space before and after.

**Then**
1. raises: `ValueError "Account code 'sup-001' already exists"` (the sent code trimmed, case as typed — not the stored `SUP-001`).
2. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.
3. unchanged: unchanged(A1).

### ACC-C-23 — the code of a soft-deleted account can be reused
- **Rules:** create_account R11a (soft-deleted do not count)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A1, but deleted and `account_code "SUP-001"`.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Beta Traders", account_code="SUP-001"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: an Account whose `id` is not None and `!= A1.id`.
2. re-read that row: `account_code == "SUP-001"`, `is_deleted is False`.
3. count: `accounts` has exactly 2 rows.

### ACC-C-24 — the same code in another workspace is no conflict
- **Rules:** create_account R11a (per workspace)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A9 (in W2), but `account_code "SUP-001"`.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Beta Traders", account_code="SUP-001"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: an Account whose `id` is not None and `!= A9.id`.
2. re-read that row: `account_code == "SUP-001"`, `workspace_id == W1.id`.
3. unchanged: unchanged(A9).

### ACC-C-25 — empty-string codes do not conflict
- **Rules:** create_account R11a (non-empty boundary), R11b (a blank code never conflicts)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1, but `account_code ""` (empty string).

**When**
- `M.create_account(session, account_data=AccountCreate(name="Beta Traders", account_code=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: an Account whose `id` is not None and `!= A1.id`.
2. count: `accounts` rows with `workspace_id W1.id` == 2.

### ACC-C-26 — the database itself forbids two live accounts with the same code
- **Rules:** create_account R11a [BUG-874] (partial unique index)
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 1 (no index exists; the insert succeeds)

**Given**
1. A1, but `account_code "SUP-001"`.

**When**
- insert directly one more `accounts` row = default account, but `name "Beta Traders"`, `account_code "sup-001"` (lower case), and flush (target `database`).

**Then**
1. raises: `IntegrityError` on flush.
2. count: `accounts` has exactly 1 row.

### ACC-C-27 — invalid primary email is rejected by the schema
- **Rules:** create_account R12 [BUG-875]
- **Kind:** bug
- **Expect:** xfail BUG-875
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. W1 has no accounts.

**When**
- build `AccountCreate(name="Acme Ltd", primary_email="call me")` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. count: `accounts` has 0 rows.

### ACC-C-28 — invalid secondary email is rejected by the schema
- **Rules:** create_account R12 [BUG-875]
- **Kind:** bug
- **Expect:** xfail BUG-875
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. W1 has no accounts.

**When**
- build `AccountCreate(name="Acme Ltd", secondary_email="not-an-email")` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. count: `accounts` has 0 rows.

### ACC-C-29 — email fields are trimmed by the schema
- **Rules:** create_account R12 [BUG-875]
- **Kind:** bug
- **Expect:** xfail BUG-875
- **Fails today on:** Then 2 (the values keep their spaces)

**Given**
1. W1 has no accounts.

**When**
- build `AccountCreate(name="Acme Ltd", primary_email="  rahim@acme.test  ", secondary_email=" karim@acme.test ")` (target `schema`).

**Then**
1. returns: the schema object, no error raised.
2. returns: `obj.primary_email == "rahim@acme.test"`.
3. returns: `obj.secondary_email == "karim@acme.test"`.

### ACC-C-30 — the account code is stored trimmed, case kept
- **Rules:** create_account R11b [BUG-874]
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 2 (the code is stored as typed, with the outer spaces)

**Given**
1. W1 has no accounts.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd", account_code="  Sup-001 "), workspace_id=W1.id, user_id=U2.id)` — two spaces before, one after, mixed case.

**Then**
1. returns: an Account whose `id` is not None.
2. re-read that row: `account_code == "Sup-001"` (outer spaces removed, case as typed).

### ACC-C-31 — an empty account code is stored as NULL
- **Rules:** create_account R11b [BUG-874]
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 2 (the code is stored as the empty string `""`)

**Given**
1. W1 has no accounts.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd", account_code=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: an Account whose `id` is not None.
2. re-read that row: `account_code is None`.

### ACC-C-32 — a whitespace-only account code is stored as NULL
- **Rules:** create_account R11b [BUG-874]
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 2 (the code is stored as three spaces)

**Given**
1. W1 has no accounts.

**When**
- `M.create_account(session, account_data=AccountCreate(name="Acme Ltd", account_code="   "), workspace_id=W1.id, user_id=U2.id)` — three spaces.

**Then**
1. returns: an Account whose `id` is not None.
2. re-read that row: `account_code is None`.

### ACC-C-33 — whitespace-only codes do not conflict
- **Rules:** create_account R11b (a blank code never conflicts), R11a (non-empty boundary)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1, but `account_code "   "` (three spaces).
2. A2 (`account_code None`).

**When**
- `M.create_account(session, account_data=AccountCreate(name="Gamma Inc", account_code=" "), workspace_id=W1.id, user_id=U2.id)` — one space.

**Then**
1. returns: an Account whose `id` is not None, `!= A1.id` and `!= A2.id` (no error raised).
2. re-read that row: `name == "Gamma Inc"`.
3. re-read that row: `account_code` is blank — `(account_code or "").strip() == ""` (looser check intended: `" "` today, `None` after the BUG-874 fix).
4. count: `accounts` rows with `workspace_id W1.id` == 3.
5. unchanged: unchanged(A1).

### ACC-C-34 — the database allows several live accounts with a blank code
- **Rules:** create_account R11a (the index covers only non-empty trimmed codes), R11b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1, but `account_code ""` (empty string).
2. A2 (`account_code None`).

**When**
- insert directly one more `accounts` row = default account, but `name "Gamma Inc"`, `account_code "   "` (three spaces), and flush (target `database`).

**Then**
1. returns: the flush raises no error and the new row's `id` is not None.
2. count: `accounts` rows with `workspace_id W1.id` == 3.

### ACC-C-35 — the database index ignores padding around the code
- **Rules:** create_account R11a [BUG-874] (partial unique index, padding)
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 1 (no index exists; the insert succeeds)

**Given**
1. A1, but `account_code "SUP-001"`.

**When**
- insert directly one more `accounts` row = default account, but `name "Beta Traders"`, `account_code " SUP-001 "` (one space before and after), and flush (target `database`).

**Then**
1. raises: `IntegrityError` on flush.
2. count: `accounts` has exactly 1 row.

## `AccountManager.update_account`

### ACC-U-01 — unknown account id is rejected
- **Rules:** update_account R1; Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A1.

**When**
- `M.update_account(session, account_id=MISSING, account_data=AccountUpdate(name="New Name"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account 999999999 not found"`.
2. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.
3. unchanged: unchanged(A1).

### ACC-U-02 — account of another workspace is rejected and not changed
- **Rules:** update_account R2 (error raised, nothing written)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A9 (`name "Zeta Corp"`, in W2).

**When**
- `M.update_account(session, account_id=A9.id, account_data=AccountUpdate(name="New Name"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError` (assert only the type here, not the text).
2. unchanged: unchanged(A9) — in particular `name == "Zeta Corp"`, `updated_by is None`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.

### ACC-U-03 — account of another workspace gets the plain "not found" message
- **Rules:** update_account R2 [BUG-440]; Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-440
- **Fails today on:** Then 1 (the text is "Account {A9.id} does not belong to workspace {W1.id}")

**Given**
1. A9 (`name "Zeta Corp"`, in W2).

**When**
- `M.update_account(session, account_id=A9.id, account_data=AccountUpdate(name="New Name"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account {A9.id} not found"`.
2. unchanged: unchanged(A9).

### ACC-U-04 — soft-deleted account cannot be updated
- **Rules:** update_account R3 [BUG-863]; Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-863
- **Fails today on:** Then 1 (no error is raised; the deleted account is updated)

**Given**
1. A1, but deleted.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(name="New Name", is_active=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account {A1.id} not found"`.
2. unchanged: unchanged(A1) — in particular `name == "Acme Ltd"`, `is_active is False`, `is_deleted is True`, `updated_by is None`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.

### ACC-U-05 — every sent field is stored
- **Rules:** update_account R4, R8 (a value changed), R9, R19
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 (all 13 optional fields `None`, `updated_by None`, `updated_at None`).

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(name="Beta Co", **FILLED, allow_invoices=False, is_active=False), workspace_id=W1.id, user_id=U2.id)` — `tag_ids` is not sent.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `name == "Beta Co"`, `allow_invoices is False`, `is_active is False`.
3. re-read A1: each of the 13 optional fields `==` its FILLED value (assert all 13, one by one).
4. re-read A1: `updated_by == U2.id`, `updated_at is not None`.
5. re-read A1: `workspace_id == W1.id`, `created_by == U1.id`, `is_deleted is False`, `deleted_at is None`, `deleted_by is None`.
6. count: `accounts` has exactly 1 row.

### ACC-U-06 — fields that are not sent keep their value
- **Rules:** update_account R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = filled account.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(city="Chattogram"), workspace_id=W1.id, user_id=U2.id)` — only `city` is sent.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `city == "Chattogram"`.
3. re-read A1: `name == "Acme Ltd"`, `allow_invoices is True`, `is_active is True`.
4. re-read A1: each of the other 12 optional fields (all except `city`) `==` its FILLED value.

### ACC-U-07 — `allow_invoices=False` and `is_active=False` are stored
- **Rules:** update_account R4, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 (`allow_invoices True`, `is_active True`).

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(allow_invoices=False, is_active=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `allow_invoices is False`, `is_active is False`.
3. re-read A1: `is_deleted is False`, `deleted_at is None`, `name == "Acme Ltd"`.

### ACC-U-08 — an inactive account can be switched back on
- **Rules:** update_account R7, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1, but `is_active False` (not deleted).

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(is_active=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `is_active is True`, `is_deleted is False`.

### ACC-U-09 — invalid primary email is rejected by the schema
- **Rules:** update_account R4a [BUG-875]
- **Kind:** bug
- **Expect:** xfail BUG-875
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `AccountUpdate(primary_email="call me")` (target `schema`).

**Then**
1. raises: `ValidationError`.

### ACC-U-10 — invalid secondary email is rejected by the schema
- **Rules:** update_account R4a [BUG-875]
- **Kind:** bug
- **Expect:** xfail BUG-875
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `AccountUpdate(secondary_email="not-an-email")` (target `schema`).

**Then**
1. raises: `ValidationError`.

### ACC-U-11 — sent email fields are trimmed by the schema
- **Rules:** update_account R4a [BUG-875]
- **Kind:** bug
- **Expect:** xfail BUG-875
- **Fails today on:** Then 2 (the values keep their spaces)

**Given**
1. Nothing.

**When**
- build `AccountUpdate(primary_email="  rahim@acme.test  ", secondary_email=" karim@acme.test ")` (target `schema`).

**Then**
1. returns: the schema object, no error raised.
2. returns: `obj.primary_email == "rahim@acme.test"`.
3. returns: `obj.secondary_email == "karim@acme.test"`.

### ACC-U-12 — explicit null clears the nullable fields
- **Rules:** update_account R5 [BUG-608]
- **Kind:** bug
- **Expect:** xfail BUG-608
- **Fails today on:** Then 3 (the old values stay)

**Given**
1. A1 = filled account.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(account_code=None, primary_contact_person=None, primary_email=None, primary_phone=None, secondary_contact_person=None, secondary_email=None, secondary_phone=None, address=None, city=None, country=None, postal_code=None, payment_preferences=None, bank_details=None), workspace_id=W1.id, user_id=U2.id)` — the 13 optional fields are sent as explicit `None`; `name`, `allow_invoices`, `is_active`, `tag_ids` are not sent.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `name == "Acme Ltd"`, `allow_invoices is True`, `is_active is True`.
3. re-read A1: each of the 13 optional fields `is None` (assert all 13, one by one).

### ACC-U-13 — explicit null for `name` is rejected by the schema
- **Rules:** update_account R5 [BUG-608]
- **Kind:** bug
- **Expect:** xfail BUG-608
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `AccountUpdate(name=None)` (target `schema`).

**Then**
1. raises: `ValidationError`.

### ACC-U-14 — explicit null for `allow_invoices` is rejected by the schema
- **Rules:** update_account R5 [BUG-608]
- **Kind:** bug
- **Expect:** xfail BUG-608
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `AccountUpdate(allow_invoices=None)` (target `schema`).

**Then**
1. raises: `ValidationError`.

### ACC-U-15 — explicit null for `is_active` is rejected by the schema
- **Rules:** update_account R5 [BUG-608]
- **Kind:** bug
- **Expect:** xfail BUG-608
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `AccountUpdate(is_active=None)` (target `schema`).

**Then**
1. raises: `ValidationError`.

### ACC-U-16 — `tag_ids=None` leaves the tags untouched
- **Rules:** update_account R10, R5 (`tag_ids: null`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 1`.
3. A1 has T1 (call that assignment row X1).

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(city="Dhaka", tag_ids=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `city == "Dhaka"`.
3. count: tags(A1) `== [T1.id]`.
4. unchanged: unchanged(X1) — same `id`, `assigned_at == T0`, `assigned_by == U1.id`.
5. re-read T1: `usage_count == 1`.

### ACC-U-17 — `tag_ids` not sent leaves the tags untouched
- **Rules:** update_account R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 1`.
3. A1 has T1 (call that assignment row X1).

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(name="Beta Co"), workspace_id=W1.id, user_id=U2.id)` — `tag_ids` is not sent.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `name == "Beta Co"`.
3. count: tags(A1) `== [T1.id]`.
4. unchanged: unchanged(X1) — same `id`, `assigned_at == T0`, `assigned_by == U1.id`.
5. re-read T1: `usage_count == 1`.

### ACC-U-18 — a sent name is stored trimmed
- **Rules:** update_account R6 [BUG-860], R17
- **Kind:** bug
- **Expect:** xfail BUG-860
- **Fails today on:** Then 2 (the name is stored as typed, with the outer spaces)

**Given**
1. A1.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(name="  Beta  Co  "), workspace_id=W1.id, user_id=U2.id)` — two spaces before, between and after.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `name == "Beta  Co"` (outer spaces removed, the two inner spaces kept).
3. audit: audit(A1) has exactly 1 row; `description == "Account 'Beta  Co' updated"`.

### ACC-U-19 — whitespace-only name is rejected by the schema
- **Rules:** update_account R6 [BUG-860]
- **Kind:** bug
- **Expect:** xfail BUG-860
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `AccountUpdate(name="   ")` (three spaces; target `schema`).

**Then**
1. raises: `ValidationError`.

### ACC-U-20 — empty name is rejected by the schema
- **Rules:** update_account R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- build `AccountUpdate(name="")` (target `schema`).

**Then**
1. raises: `ValidationError`.

### ACC-U-21 — an empty request changes no business field
- **Rules:** update_account R4, R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = filled account.
2. T1, `usage_count 1`.
3. A1 has T1.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(), workspace_id=W1.id, user_id=U2.id)` — no field is sent. This card does not check `updated_by` or audit rows.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `name == "Acme Ltd"`, `allow_invoices is True`, `is_active is True`, `is_deleted is False`.
3. re-read A1: each of the 13 optional fields `==` its FILLED value.
4. count: tags(A1) `== [T1.id]`.
5. re-read T1: `usage_count == 1`.

### ACC-U-22 — an empty request does not stamp `updated_by`
- **Rules:** update_account R8 [BUG-869]
- **Kind:** bug
- **Expect:** xfail BUG-869
- **Fails today on:** Then 2 (`updated_by` is set to U2)

**Given**
1. A1 (`updated_by None`).

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(), workspace_id=W1.id, user_id=U2.id)` — no field is sent.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `updated_by is None`.

### ACC-U-23 — an empty request writes no audit row
- **Rules:** update_account R15 [BUG-632]
- **Kind:** bug
- **Expect:** xfail BUG-632
- **Fails today on:** Then 2 (one "updated" audit row is written)

**Given**
1. A1; `financial_audit_logs` has 0 rows.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(), workspace_id=W1.id, user_id=U2.id)` — no field is sent.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. audit: `financial_audit_logs` has 0 rows.

### ACC-U-24 — sending the current values does not stamp `updated_by`
- **Rules:** update_account R8 [BUG-869]
- **Kind:** bug
- **Expect:** xfail BUG-869
- **Fails today on:** Then 3 (`updated_by` becomes U2)

**Given**
1. A1, but `city "Dhaka"`, `updated_by U1.id`.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(name="Acme Ltd", city="Dhaka"), workspace_id=W1.id, user_id=U2.id)` — both values equal the stored ones.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `name == "Acme Ltd"`, `city == "Dhaka"`.
3. re-read A1: `updated_by == U1.id`.

### ACC-U-25 — sending the current values writes no audit row
- **Rules:** update_account R15 [BUG-632]
- **Kind:** bug
- **Expect:** xfail BUG-632
- **Fails today on:** Then 2 (one "updated" audit row is written)

**Given**
1. A1, but `city "Dhaka"`; `financial_audit_logs` has 0 rows.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(name="Acme Ltd", city="Dhaka"), workspace_id=W1.id, user_id=U2.id)` — both values equal the stored ones.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. audit: `financial_audit_logs` has 0 rows.

### ACC-U-26 — sending the current tag set is not a change
- **Rules:** update_account R8 [BUG-869], R15 [BUG-632]
- **Kind:** bug
- **Expect:** xfail BUG-869, BUG-632
- **Fails today on:** Then 3 (`updated_by` is set to U2)

**Given**
1. A1 (`updated_by None`); `financial_audit_logs` has 0 rows.
2. T1, `usage_count 1`.
3. A1 has T1.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(tag_ids=[T1.id]), workspace_id=W1.id, user_id=U2.id)` — only `tag_ids` is sent.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. count: tags(A1) `== [T1.id]`.
3. re-read A1: `updated_by is None`.
4. audit: `financial_audit_logs` has 0 rows.

### ACC-U-27 — changing only the tag set stamps the account and writes an audit row
- **Rules:** update_account R8 (tag set changed), R15 (tag set changed)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 (`updated_by None`, no tags); `financial_audit_logs` has 0 rows.
2. T1, `usage_count 0`.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(tag_ids=[T1.id]), workspace_id=W1.id, user_id=U2.id)` — only `tag_ids` is sent.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. count: tags(A1) `== [T1.id]`.
3. re-read A1: `updated_by == U2.id`.
4. audit: audit(A1) has exactly 1 row; `action_type == "updated"`, `performed_by == U2.id`.

### ACC-U-28 — a tag list replaces the account's tags and adjusts usage counts
- **Rules:** update_account R11, R12
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 1`.
3. T2, `usage_count 0`.
4. Tag T4 = default tag, `name "Utility"`, `tag_code "utility"`, `usage_count 5`.
5. A1 has T1.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(tag_ids=[T2.id, T4.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. count: tags(A1) `== [T2.id, T4.id]`.
3. re-read the two assignment rows of A1: `workspace_id == W1.id`, `assigned_by == U2.id`, `assigned_at is not None`.
4. re-read T1: `usage_count == 0`.
5. re-read T2: `usage_count == 1`.
6. re-read T4: `usage_count == 6`.

### ACC-U-29 — an empty tag list removes all tags
- **Rules:** update_account R11, R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 1`.
3. T2, `usage_count 4`.
4. A1 has T1. A1 has T2.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(tag_ids=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. count: tags(A1) `== []`.
3. re-read T1: `usage_count == 0`.
4. re-read T2: `usage_count == 3`.

### ACC-U-30 — removing a tag never takes its usage count below 0
- **Rules:** update_account R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 0` (already 0 although assigned).
3. A1 has T1.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(tag_ids=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. count: tags(A1) `== []`.
3. re-read T1: `usage_count == 0`.

### ACC-U-31 — repeated ids in the tag list count once
- **Rules:** update_account R11; _assign_tags_to_account R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 (no tags).
2. T1, `usage_count 0`.
3. T2, `usage_count 0`.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(tag_ids=[T1.id, T1.id, T2.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. count: tags(A1) `== [T1.id, T2.id]` (exactly 2 assignment rows).
3. re-read T1: `usage_count == 1`.
4. re-read T2: `usage_count == 1`.

### ACC-U-32 — keeping one tag and adding another gives the right set and counts
- **Rules:** update_account R11, R12, R13 (set and counts)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 1`.
3. T2, `usage_count 0`.
4. A1 has T1.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(tag_ids=[T1.id, T2.id]), workspace_id=W1.id, user_id=U2.id)`. This card does not check the kept assignment row's `id`, `assigned_at` or `assigned_by`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. count: tags(A1) `== [T1.id, T2.id]`.
3. re-read T1: `usage_count == 1`.
4. re-read T2: `usage_count == 1`.

### ACC-U-33 — a tag that stays keeps its assignment row
- **Rules:** update_account R13 [BUG-870]
- **Kind:** bug
- **Expect:** xfail BUG-870
- **Fails today on:** Then 3 (the row is deleted and re-created: new `id`, `assigned_by == U2.id`)

**Given**
1. A1.
2. T1, `usage_count 1`.
3. T2, `usage_count 0`.
4. A1 has T1 (call that assignment row X1; remember `X1.id`).

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(tag_ids=[T1.id, T2.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. count: tags(A1) `== [T1.id, T2.id]`.
3. re-read the assignment row of A1 with `tag_id T1.id`: `id == X1.id`, `assigned_at == T0`, `assigned_by == U1.id`.

### ACC-U-34 — a kept tag whose count is 0 stays at 0
- **Rules:** update_account R13 [BUG-870]
- **Kind:** bug
- **Expect:** xfail BUG-870
- **Fails today on:** Then 3 (the count ends at 1)

**Given**
1. A1.
2. T1, `usage_count 0` (already 0 although assigned).
3. A1 has T1.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(tag_ids=[T1.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. count: tags(A1) `== [T1.id]`.
3. re-read T1: `usage_count == 0`.

### ACC-U-35 — unknown tag id rejects the whole update
- **Rules:** update_account R14 [BUG-871]; Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-871
- **Fails today on:** Then 1 (no error is raised; the account loses its tags)

**Given**
1. A1 (`name "Acme Ltd"`).
2. T1, `usage_count 1`.
3. A1 has T1.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(name="New Name", tag_ids=[MISSING]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account tag 999999999 not found"`.
2. unchanged: unchanged(A1) — in particular `name == "Acme Ltd"`, `updated_by is None`.
3. count: tags(A1) `== [T1.id]`.
4. nothing written: `accounts` 1 row, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T1 `usage_count == 1`.

### ACC-U-36 — tag of another workspace rejects the whole update
- **Rules:** update_account R14 [BUG-871]; Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-871
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. A1.
2. T1, `usage_count 1`.
3. T9 (in W2), `usage_count 0`.
4. A1 has T1.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(tag_ids=[T9.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account tag {T9.id} not found"`.
2. count: tags(A1) `== [T1.id]`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T1 `usage_count == 1`, T9 `usage_count == 0`.
4. unchanged: unchanged(A1).

### ACC-U-37 — one unknown id rejects the list, valid new tags are not attached
- **Rules:** update_account R14 [BUG-871]; _assign_tags_to_account R7 [BUG-871]
- **Kind:** bug
- **Expect:** xfail BUG-871
- **Fails today on:** Then 1 (no error is raised; T2 is attached)

**Given**
1. A1.
2. T1, `usage_count 1`.
3. T2, `usage_count 0`.
4. A1 has T1.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(tag_ids=[T1.id, T2.id, MISSING]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account tag 999999999 not found"`.
2. count: tags(A1) `== [T1.id]`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T1 `usage_count == 1`, T2 `usage_count == 0`.
4. unchanged: unchanged(A1).

### ACC-U-38 — a newly added inactive tag rejects the update
- **Rules:** update_account R11a [BUG-2987]; Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-2987
- **Fails today on:** Then 1 (no error is raised; the inactive tag is attached)

**Given**
1. A1 (`name "Acme Ltd"`).
2. T1, `usage_count 1`.
3. T3 (inactive), `usage_count 0`.
4. A1 has T1.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(name="New Name", tag_ids=[T1.id, T3.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account tag {T3.id} is not active"`.
2. count: tags(A1) `== [T1.id]`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T1 `usage_count == 1`, T3 `usage_count == 0`.
4. unchanged: unchanged(A1) — in particular `name == "Acme Ltd"`.

### ACC-U-39 — an inactive tag that is already assigned and stays is not rechecked
- **Rules:** update_account R11a (tags staying are not rechecked), R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1.
2. T2, `usage_count 0`.
3. T3 (inactive), `usage_count 1`.
4. A1 has T3.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(tag_ids=[T3.id, T2.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id` (no error raised).
2. count: tags(A1) `== [T2.id, T3.id]`.
3. re-read T2: `usage_count == 1`.
4. re-read T3: `usage_count == 1`.

### ACC-U-40 — a real change writes one "updated" audit row
- **Rules:** update_account R15 (changed), R16 (keys written today), R17, R18 (not passed)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1, but `city "Dhaka"`, `payment_preferences "Cash"`; `financial_audit_logs` has 0 rows.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(name="Beta Co", city="Chattogram", allow_invoices=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. audit: `financial_audit_logs` has exactly 1 row, it is in audit(A1) and has the standard audit fields.
3. audit: `action_type == "updated"`, `description == "Account 'Beta Co' updated"` (the name AFTER the update), `performed_by == U2.id`, `performed_at == NOW`.
4. audit: `ip_address is None`, `user_agent is None`.
5. audit: `changes` has both keys `"before"` and `"after"`.
6. audit: `changes["before"]["name"] == "Acme Ltd"`, `["city"] == "Dhaka"`, `["allow_invoices"] is True`, `["payment_preferences"] == "Cash"`, `["primary_contact_person"] is None`, `["primary_email"] is None`, `["address"] is None`, `["country"] is None`.
7. audit: `changes["after"]["name"] == "Beta Co"`, `["city"] == "Chattogram"`, `["allow_invoices"] is False`, `["payment_preferences"] == "Cash"`, `["primary_contact_person"] is None`, `["primary_email"] is None`, `["address"] is None`, `["country"] is None`.

### ACC-U-41 — audit row holds the full before / after snapshot including tags
- **Rules:** update_account R16 [BUG-872]
- **Kind:** bug
- **Expect:** xfail BUG-872
- **Fails today on:** Then 3 (`changes` has only 8 keys per side and no tag ids)

**Given**
1. A1 = filled account.
2. T1, `usage_count 1`.
3. T2, `usage_count 0`.
4. A1 has T1.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(bank_details="DBBL 999-888", is_active=False, tag_ids=[T2.id, T1.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. audit: audit(A1) has exactly 1 row.
3. audit: `changes == {"before": SNAP(**FILLED, tag_ids=[T1.id]), "after": SNAP(**FILLED, bank_details="DBBL 999-888", is_active=False, tag_ids=[T1.id, T2.id])}` (in "after", `bank_details` is the new value).

### ACC-U-42 — client IP and user agent are written to the audit row
- **Rules:** update_account R18 [BUG-140]
- **Kind:** bug
- **Expect:** xfail BUG-140
- **Fails today on:** Then 1 (the call raises `TypeError`: the parameters do not exist)

**Given**
1. A1.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(name="Beta Co"), workspace_id=W1.id, user_id=U2.id, ip_address="203.0.113.7", user_agent="pytest-agent/1.0")`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. audit: audit(A1) has exactly 1 row.
3. audit: `ip_address == "203.0.113.7"`, `user_agent == "pytest-agent/1.0"`.

### ACC-U-43 — renaming to another live account's name is allowed
- **Rules:** update_account R20
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 (`name "Acme Ltd"`).
2. A2 (`name "Beta Co"`).

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(name="Beta Co"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `name == "Beta Co"`.
3. count: `accounts` rows with `workspace_id W1.id` and `name "Beta Co"` == 2.

### ACC-U-44 — taking another live account's code is rejected
- **Rules:** update_account R20a [BUG-874]; Errors row 6
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 1 (no error is raised; the code is stored)

**Given**
1. A1 (`account_code None`).
2. A2, but `account_code "SUP-001"`.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(account_code="SUP-001"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account code 'SUP-001' already exists"`.
2. unchanged: unchanged(A1) — in particular `account_code is None`, `updated_by is None`.
3. nothing written: `accounts` 2 rows, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.

### ACC-U-45 — the code conflict check is trimmed and case-insensitive
- **Rules:** update_account R20a [BUG-874]; Errors row 6
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. A1 (`account_code None`).
2. A2, but `account_code "SUP-001"`.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(account_code=" sup-001 "), workspace_id=W1.id, user_id=U2.id)` — lower case, one space before and after.

**Then**
1. raises: `ValueError "Account code 'sup-001' already exists"` (the sent code trimmed, case as typed — not the stored `SUP-001`).
2. unchanged: unchanged(A1) — in particular `account_code is None`.
3. nothing written: `accounts` 2 rows, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.

### ACC-U-46 — an account keeping its own code is no conflict
- **Rules:** update_account R20a (own code)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1, but `account_code "SUP-001"`.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(account_code="SUP-001", city="Dhaka"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id` (no error raised).
2. re-read A1: `account_code == "SUP-001"`, `city == "Dhaka"`.

### ACC-U-47 — the code of a soft-deleted account can be taken
- **Rules:** update_account R20a (soft-deleted do not count)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A1 (`account_code None`).
2. A2, but deleted and `account_code "SUP-001"`.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(account_code="SUP-001"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id` (no error raised).
2. re-read A1: `account_code == "SUP-001"`.
3. unchanged: unchanged(A2).

### ACC-U-48 — the same code in another workspace is no conflict
- **Rules:** update_account R20a (per workspace)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 (`account_code None`).
2. A9 (in W2), but `account_code "SUP-001"`.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(account_code="SUP-001"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id` (no error raised).
2. re-read A1: `account_code == "SUP-001"`.
3. unchanged: unchanged(A9).

### ACC-U-49 — a code conflict leaves the other sent fields and the tags unchanged
- **Rules:** update_account R20a [BUG-874]; Errors row 6
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 1 (no error is raised; name, code and tags are changed)

**Given**
1. A1 (`name "Acme Ltd"`, `account_code None`, `updated_by None`); `financial_audit_logs` has 0 rows.
2. A2, but `account_code "SUP-001"`.
3. T1, `usage_count 1`.
4. T2, `usage_count 0`.
5. A1 has T1 (call that assignment row X1).

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(name="New Name", account_code="SUP-001", tag_ids=[T2.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account code 'SUP-001' already exists"`.
2. unchanged: unchanged(A1) — in particular `name == "Acme Ltd"`, `account_code is None`, `updated_by is None`.
3. count: tags(A1) `== [T1.id]`.
4. unchanged: unchanged(X1).
5. nothing written: `accounts` 2 rows, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T1 `usage_count == 1`, T2 `usage_count == 0`.

### ACC-U-50 — re-sending the own code in another case and with padding is no conflict
- **Rules:** update_account R20a (own code, other case / padding)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1, but `account_code "SUP-001"`.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(account_code=" sup-001 ", city="Dhaka"), workspace_id=W1.id, user_id=U2.id)` — lower case, one space before and after.

**Then**
1. returns: the row A1 — `result.id == A1.id` (no error raised).
2. re-read A1: `city == "Dhaka"`.
3. re-read A1: `account_code.strip() == "sup-001"` (looser check intended: `" sup-001 "` today, `"sup-001"` after the BUG-874 fix).

### ACC-U-51 — a sent account code is stored trimmed, case kept
- **Rules:** update_account R20b [BUG-874]
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 2 (the code is stored as typed, with the outer spaces)

**Given**
1. A1 (`account_code None`).

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(account_code="  Sup-001 "), workspace_id=W1.id, user_id=U2.id)` — two spaces before, one after, mixed case.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `account_code == "Sup-001"` (outer spaces removed, case as typed).

### ACC-U-52 — sending an empty account code clears the code
- **Rules:** update_account R20b [BUG-874]
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 2 (the code is stored as the empty string `""`)

**Given**
1. A1, but `account_code "SUP-001"`.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(account_code=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `account_code is None`.

### ACC-U-53 — sending a whitespace-only account code clears the code
- **Rules:** update_account R20b [BUG-874]
- **Kind:** bug
- **Expect:** xfail BUG-874
- **Fails today on:** Then 2 (the code is stored as three spaces)

**Given**
1. A1, but `account_code "SUP-001"`.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(account_code="   "), workspace_id=W1.id, user_id=U2.id)` — three spaces.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `account_code is None`.

### ACC-U-54 — a blank sent code never conflicts with other blank codes
- **Rules:** update_account R20b (a blank code never conflicts), R20a (non-empty boundary)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1, but `account_code "SUP-001"`.
2. A2, but `account_code ""` (empty string).
3. Account A3 = default account, but `name "Gamma Inc"`, `account_code "   "` (three spaces).

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(account_code=" "), workspace_id=W1.id, user_id=U2.id)` — one space.

**Then**
1. returns: the row A1 — `result.id == A1.id` (no error raised).
2. re-read A1: `account_code` is blank — `(account_code or "").strip() == ""` (looser check intended: `" "` today, `None` after the BUG-874 fix).
3. unchanged: unchanged(A2) and unchanged(A3).

### ACC-U-55 — a link to a deleted tag survives a tag save
- **Rules:** update_account R13a [BUG-1487]
- **Kind:** bug
- **Expect:** xfail BUG-1487
- **Fails today on:** Then 2 (the link to T3 is deleted: tags(A1) is `[T2.id]`)

**Given**
1. A1.
2. T1, `usage_count 1`.
3. T2, `usage_count 0`.
4. T3 (inactive), `usage_count 1`.
5. A1 has T1. A1 has T3 (call that assignment row X3; remember `X3.id`).

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(tag_ids=[T2.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. count: tags(A1) `== [T2.id, T3.id]`.
3. re-read the assignment row of A1 with `tag_id T3.id`: `id == X3.id`, `assigned_at == T0`, `assigned_by == U1.id`.
4. re-read T3: `usage_count == 1`.

### ACC-U-56 — a link to a live tag not in the list is removed, next to a deleted-tag link
- **Rules:** update_account R11, R12, R13a (links to active tags are still replaced)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 1`.
3. T2, `usage_count 0`.
4. T3 (inactive), `usage_count 1`.
5. A1 has T1. A1 has T3.

**When**
- `M.update_account(session, account_id=A1.id, account_data=AccountUpdate(tag_ids=[T2.id]), workspace_id=W1.id, user_id=U2.id)`. This card does not check the link to T3 or T3's count.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. count: `T1.id not in` tags(A1) and `T2.id in` tags(A1).
3. re-read T1: `usage_count == 0`.
4. re-read T2: `usage_count == 1`.

## `AccountManager.get_account`

### ACC-G-01 — a live account of the workspace is returned
- **Rules:** get_account R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1.
2. A2.

**When**
- `M.get_account(session, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: the row A1 — `result is not None`, `result.id == A1.id`, `result.name == "Acme Ltd"`.

### ACC-G-02 — unknown id returns None
- **Rules:** get_account R2
- **Kind:** error
- **Expect:** pass

**Given**
1. A1.

**When**
- `M.get_account(session, account_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `None` (no error raised).

### ACC-G-03 — account of another workspace returns None
- **Rules:** get_account R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A9 (in W2).

**When**
- `M.get_account(session, account_id=A9.id, workspace_id=W1.id)`.

**Then**
1. returns: `None` (no error raised).

### ACC-G-04 — soft-deleted account is hidden by default
- **Rules:** get_account R4 [BUG-862]
- **Kind:** bug
- **Expect:** xfail BUG-862
- **Fails today on:** Then 1 (the deleted account is returned)

**Given**
1. A1, but deleted.

**When**
- `M.get_account(session, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: `None`.

### ACC-G-05 — `include_deleted=True` returns a soft-deleted account
- **Rules:** get_account R4 [BUG-862]
- **Kind:** bug
- **Expect:** xfail BUG-862
- **Fails today on:** Then 1 (the call raises `TypeError`: the parameter does not exist)

**Given**
1. A1, but deleted.

**When**
- `M.get_account(session, account_id=A1.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: the row A1 — `result is not None`, `result.id == A1.id`, `result.is_deleted is True`.

### ACC-G-06 — `include_deleted=True` still hides other workspaces
- **Rules:** get_account R4 [BUG-862], R3
- **Kind:** bug
- **Expect:** xfail BUG-862
- **Fails today on:** Then 1 (the call raises `TypeError`: the parameter does not exist)

**Given**
1. A9 (in W2), but deleted.

**When**
- `M.get_account(session, account_id=A9.id, workspace_id=W1.id, include_deleted=True)`.

**Then**
1. returns: `None`.

### ACC-G-07 — an inactive, not deleted account is returned
- **Rules:** get_account R5; update_account R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1, but `is_active False` (`is_deleted False`).

**When**
- `M.get_account(session, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: the row A1 — `result is not None`, `result.id == A1.id`, `result.is_active is False`.

## `AccountManager.search_accounts`

### ACC-S-01 — default search returns only active, live accounts of the workspace
- **Rules:** search_accounts R1; update_account R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. Account = default account, but `name "Alpha"`.
2. Account = default account, but `name "Bravo"`, `is_active False`.
3. Account = default account, but `name "Charlie"`, deleted.
4. Account = default account, but `name "Delta"`, `workspace_id W2.id`.

**When**
- `M.search_accounts(session, workspace_id=W1.id)` — no other argument.

**Then**
1. returns: a list of Account objects; the set of names `== {"Alpha"}`; `len(result) == 1`.
2. returns: `result[0].id` == the id of the "Alpha" row.

### ACC-S-02 — `include_inactive=True` adds inactive accounts, never deleted or foreign ones
- **Rules:** search_accounts R1a [BUG-878]
- **Kind:** bug
- **Expect:** xfail BUG-878
- **Fails today on:** Then 1 (the call raises `TypeError`: the parameter does not exist)

**Given**
1. Account = default account, but `name "Alpha"`.
2. Account = default account, but `name "Bravo"`, `is_active False`.
3. Account = default account, but `name "Charlie"`, deleted.
4. Account = default account, but `name "Delta"`, `workspace_id W2.id`, `is_active False`.

**When**
- `M.search_accounts(session, workspace_id=W1.id, include_inactive=True)`.

**Then**
1. returns: the set of names `== {"Alpha", "Bravo"}`; `len(result) == 2`.

### ACC-S-03 — a workspace without accounts gives an empty list
- **Rules:** search_accounts R14
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no accounts.
2. A9 (in W2).

**When**
- `M.search_accounts(session, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### ACC-S-04 — empty name text means no name filter
- **Rules:** search_accounts R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 (`name "Acme Ltd"`).
2. A2 (`name "Beta Co"`).

**When**
- `M.search_accounts(session, workspace_id=W1.id, name="")`.

**Then**
1. returns: the set of names `== {"Acme Ltd", "Beta Co"}`; `len(result) == 2`.

### ACC-S-05 — whitespace-only name text means no name filter
- **Rules:** search_accounts R2, R5 [BUG-637]
- **Kind:** bug
- **Expect:** xfail BUG-637
- **Fails today on:** Then 1 (returns `[]`)

**Given**
1. A1 (`name "Acme Ltd"`).
2. A2 (`name "Beta Co"`).

**When**
- `M.search_accounts(session, workspace_id=W1.id, name="   ")` — three spaces.

**Then**
1. returns: the set of names `== {"Acme Ltd", "Beta Co"}`; `len(result) == 2`.

### ACC-S-06 — name text matches anywhere in the name, ignoring case
- **Rules:** search_accounts R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 (`name "Acme Ltd"`).
2. Account = default account, but `name "Big ACME Traders"`.
3. A2 (`name "Beta Co"`).

**When**
- `M.search_accounts(session, workspace_id=W1.id, name="acme")`.

**Then**
1. returns: the set of names `== {"Acme Ltd", "Big ACME Traders"}`; `len(result) == 2`.

### ACC-S-07 — name text that matches nothing gives an empty list
- **Rules:** search_accounts R3, R14
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 (`name "Acme Ltd"`).
2. A2 (`name "Beta Co"`).

**When**
- `M.search_accounts(session, workspace_id=W1.id, name="zzz")`.

**Then**
1. returns: `result == []`.

### ACC-S-08 — `%` in the name text matches literally
- **Rules:** search_accounts R4 [BUG-868]
- **Kind:** bug
- **Expect:** xfail BUG-868
- **Fails today on:** Then 1 (both accounts are returned)

**Given**
1. Account = default account, but `name "100% Cotton"`.
2. A1 (`name "Acme Ltd"`).

**When**
- `M.search_accounts(session, workspace_id=W1.id, name="%")`.

**Then**
1. returns: the set of names `== {"100% Cotton"}`; `len(result) == 1`.

### ACC-S-09 — `_` in the name text matches literally
- **Rules:** search_accounts R4 [BUG-868]
- **Kind:** bug
- **Expect:** xfail BUG-868
- **Fails today on:** Then 1 (both accounts are returned)

**Given**
1. Account = default account, but `name "Acme_Ltd"` (underscore).
2. A1 (`name "Acme Ltd"`, with a space).

**When**
- `M.search_accounts(session, workspace_id=W1.id, name="_")`.

**Then**
1. returns: the set of names `== {"Acme_Ltd"}`; `len(result) == 1`.

### ACC-S-10 — a backslash in the name text matches literally
- **Rules:** search_accounts R4 [BUG-868]
- **Kind:** bug
- **Expect:** xfail BUG-868
- **Fails today on:** Then 1 (the backslash is treated as an escape character; the account is not found)

**Given**
1. Account = default account, but `name` = the 8 characters `Acme\Ltd` (one backslash; Python `"Acme\\Ltd"`).
2. A1 (`name "Acme Ltd"`).

**When**
- `M.search_accounts(session, workspace_id=W1.id, name="\\")` — a string of exactly one backslash character.

**Then**
1. returns: `len(result) == 1` and `result[0].name == "Acme\\Ltd"` (the row of Given 1).

### ACC-S-11 — the name text is trimmed before matching
- **Rules:** search_accounts R5 [BUG-637]
- **Kind:** bug
- **Expect:** xfail BUG-637
- **Fails today on:** Then 1 (returns `[]`)

**Given**
1. A1 (`name "Acme Ltd"`).
2. A2 (`name "Beta Co"`).

**When**
- `M.search_accounts(session, workspace_id=W1.id, name=" acme ")` — one space before and after.

**Then**
1. returns: the set of names `== {"Acme Ltd"}`; `len(result) == 1`.

### ACC-S-12 — empty tag code means no tag filter
- **Rules:** search_accounts R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 (`name "Acme Ltd"`).
2. A2 (`name "Beta Co"`).
3. T1, `usage_count 1`.
4. A1 has T1.

**When**
- `M.search_accounts(session, workspace_id=W1.id, tag_code="")`.

**Then**
1. returns: the set of names `== {"Acme Ltd", "Beta Co"}`; `len(result) == 2`.

### ACC-S-13 — tag code returns only accounts carrying that tag in this workspace
- **Rules:** search_accounts R7, R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 (`name "Acme Ltd"`).
2. A2 (`name "Beta Co"`).
3. Account = default account, but `name "Gamma Inc"` (no tags).
4. A9 (`name "Zeta Corp"`, in W2).
5. T1 (`tag_code "supplier"`), `usage_count 1`. T2 (`tag_code "client"`), `usage_count 1`. T9 (`tag_code "supplier"`, in W2), `usage_count 1`.
6. A1 has T1. A2 has T2. A9 has T9.

**When**
- `M.search_accounts(session, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: the set of names `== {"Acme Ltd"}`; `len(result) == 1`.

### ACC-S-14 — an account matching through two assignments appears once
- **Rules:** search_accounts R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 (`name "Acme Ltd"`).
2. T1 (`name "Supplier"`, `tag_code "supplier"`), `usage_count 1`.
3. Tag T5 = default tag, `name "Supplier B"`, `tag_code "supplier"` (same code as T1), `usage_count 1`.
4. A1 has T1. A1 has T5.

**When**
- `M.search_accounts(session, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].id == A1.id`.

### ACC-S-15 — an assignment recorded under another workspace does not match
- **Rules:** search_accounts R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 (`name "Acme Ltd"`, in W1).
2. T1 (`tag_code "supplier"`, in W1), `usage_count 1`.
3. One `account_tag_assignments` row: `account_id A1.id`, `tag_id T1.id`, `workspace_id W2.id` (NOT W1), `assigned_by U1.id`, `assigned_at T0`.

**When**
- `M.search_accounts(session, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: `result == []`.

### ACC-S-16 — tag code is compared case-insensitively
- **Rules:** search_accounts R8 [BUG-861]
- **Kind:** bug
- **Expect:** xfail BUG-861
- **Fails today on:** Then 1 (returns `[]`)

**Given**
1. A1 (`name "Acme Ltd"`).
2. T1 (`tag_code "supplier"`), `usage_count 1`.
3. A1 has T1.

**When**
- `M.search_accounts(session, workspace_id=W1.id, tag_code="Supplier")` — capital S.

**Then**
1. returns: the set of names `== {"Acme Ltd"}`; `len(result) == 1`.

### ACC-S-17 — tag code is trimmed before comparing
- **Rules:** search_accounts R8 [BUG-861]
- **Kind:** bug
- **Expect:** xfail BUG-861
- **Fails today on:** Then 1 (returns `[]`)

**Given**
1. A1 (`name "Acme Ltd"`).
2. T1 (`tag_code "supplier"`), `usage_count 1`.
3. A1 has T1.

**When**
- `M.search_accounts(session, workspace_id=W1.id, tag_code=" supplier ")` — one space before and after.

**Then**
1. returns: the set of names `== {"Acme Ltd"}`; `len(result) == 1`.

### ACC-S-18 — an inactive tag does not match the tag filter
- **Rules:** search_accounts R9 [BUG-864]
- **Kind:** bug
- **Expect:** xfail BUG-864
- **Fails today on:** Then 1 (the account is returned)

**Given**
1. A1 (`name "Acme Ltd"`).
2. T3 (`tag_code "legacy"`, inactive), `usage_count 1`.
3. A1 has T3.

**When**
- `M.search_accounts(session, workspace_id=W1.id, tag_code="legacy")`.

**Then**
1. returns: `result == []`.

### ACC-S-19 — name and tag code must both match
- **Rules:** search_accounts R10
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 (`name "Acme Ltd"`).
2. Account B = default account, but `name "Acme Traders"`.
3. A2 (`name "Beta Co"`).
4. T1 (`tag_code "supplier"`), `usage_count 2`. T2 (`tag_code "client"`), `usage_count 1`.
5. A1 has T1. B has T2. A2 has T1.

**When**
- `M.search_accounts(session, workspace_id=W1.id, name="acme", tag_code="supplier")`.

**Then**
1. returns: the set of names `== {"Acme Ltd"}`; `len(result) == 1`.

### ACC-S-20 — results are ordered by name ignoring case, then id
- **Rules:** search_accounts R11 [BUG-866]
- **Kind:** bug
- **Expect:** xfail BUG-866
- **Fails today on:** Then 1 (no ordering is applied)

**Given**

Six default accounts in W1, inserted in exactly this order, differing only in `name`:
1. `name "delta"`.
2. `name "charlie"`.
3. `name "Bravo"`.
4. `name "alpha"` (call it L).
5. `name "ALPHA"` (call it H; `H.id > L.id`).
6. `name "Echo"`.

**When**
- `M.search_accounts(session, workspace_id=W1.id)`.

**Then**
1. returns: names in order `== ["alpha", "ALPHA", "Bravo", "charlie", "delta", "Echo"]`.
2. returns: `result[0].id == L.id` and `result[1].id == H.id`.

### ACC-S-21 — `limit` caps the page size
- **Rules:** search_accounts R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Five default accounts in W1, differing only in `name`: "Alpha", "Bravo", "Charlie", "Delta", "Echo".

**When**
- `M.search_accounts(session, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: the 2 names are different and both are in `{"Alpha", "Bravo", "Charlie", "Delta", "Echo"}`.

### ACC-S-22 — the last page is short only because no more matches exist
- **Rules:** search_accounts R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Five default accounts in W1, differing only in `name`: "Alpha", "Bravo", "Charlie", "Delta", "Echo".

**When**
- `M.search_accounts(session, workspace_id=W1.id, skip=4, limit=2)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `result[0].name` is in `{"Alpha", "Bravo", "Charlie", "Delta", "Echo"}`.

### ACC-S-23 — `skip` beyond the matches gives an empty list
- **Rules:** search_accounts R12, R14
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Five default accounts in W1, differing only in `name`: "Alpha", "Bravo", "Charlie", "Delta", "Echo".

**When**
- `M.search_accounts(session, workspace_id=W1.id, skip=5, limit=2)`.

**Then**
1. returns: `result == []`.

### ACC-S-24 — the default page size is 100
- **Rules:** search_accounts R12
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 default accounts in W1, differing only in `name`: "Account 001" … "Account 101".

**When**
- `M.search_accounts(session, workspace_id=W1.id)` — `skip` and `limit` not passed.

**Then**
1. returns: `len(result) == 100`.
2. returns: the 100 ids are all different.

### ACC-S-25 — filters are applied before paging
- **Rules:** search_accounts R12, R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**

Six default accounts in W1, inserted in exactly this order, differing only in the fields named:
1. `name "Acme X1"`, `is_active False`.
2. `name "Acme X2"`, deleted.
3. `name "Zed One"`.
4. `name "Zed Two"`.
5. `name "Acme A"`.
6. `name "Acme B"`.

**When**
- `M.search_accounts(session, workspace_id=W1.id, name="acme", skip=0, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: the set of names `== {"Acme A", "Acme B"}`.

### ACC-S-26 — a page is cut from the ordered result
- **Rules:** search_accounts R11 [BUG-866], R12
- **Kind:** bug
- **Expect:** xfail BUG-866
- **Fails today on:** Then 2 (no ordering is applied before `skip` / `limit`)

**Given**

Seven default accounts in W1, inserted in exactly this order, differing only in `name`:
1. `name "Echo"`.
2. `name "Bravo"`.
3. `name "Golf"`.
4. `name "Alpha"`.
5. `name "Delta"`.
6. `name "Foxtrot"`.
7. `name "Charlie"`.

**When**
- `M.search_accounts(session, workspace_id=W1.id, skip=1, limit=5)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: names in order `== ["Bravo", "Charlie", "Delta", "Echo", "Foxtrot"]` ("Alpha" skipped, "Golf" cut off).

## `AccountManager.delete_account`

### ACC-D-01 — delete soft-deletes the account and keeps everything else
- **Rules:** delete_account R4, R9, R7b (no invoices)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = filled account (`updated_by None`).
2. `account_invoices` has 0 rows.

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `is_deleted is True`, `is_active is False`, `deleted_at == NOW`, `deleted_by == U2.id`.
3. re-read A1: `updated_by is None`, `created_by == U1.id`, `workspace_id == W1.id`.
4. re-read A1: `name == "Acme Ltd"`, `allow_invoices is True`, and each of the 13 optional fields `==` its FILLED value.
5. count: `accounts` has exactly 1 row (the row is kept).

### ACC-D-02 — unknown account id is rejected
- **Rules:** delete_account R1; Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A1.

**When**
- `M.delete_account(session, account_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account 999999999 not found"`.
2. unchanged: unchanged(A1) — in particular `is_deleted is False`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.

### ACC-D-03 — account of another workspace is rejected and not deleted
- **Rules:** delete_account R2 (error raised, nothing written)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A9 (in W2).

**When**
- `M.delete_account(session, account_id=A9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError` (assert only the type here, not the text).
2. unchanged: unchanged(A9) — in particular `is_deleted is False`, `is_active is True`, `deleted_at is None`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.

### ACC-D-04 — account of another workspace gets the plain "not found" message
- **Rules:** delete_account R2 [BUG-440]; Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-440
- **Fails today on:** Then 1 (the text is "Account {A9.id} does not belong to workspace {W1.id}")

**Given**
1. A9 (in W2).

**When**
- `M.delete_account(session, account_id=A9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account {A9.id} not found"`.
2. unchanged: unchanged(A9).

### ACC-D-05 — an already deleted account is rejected
- **Rules:** delete_account R3; Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. A1, but deleted (`deleted_at T0`, `deleted_by U1.id`).

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account {A1.id} is already deleted"`.
2. re-read A1: `deleted_at == T0`, `deleted_by == U1.id`, `is_deleted is True`.
3. unchanged: unchanged(A1).
4. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.

### ACC-D-06 — delete writes one "deleted" audit row
- **Rules:** delete_account R5 (keys written today), R10 (not passed)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1, but `primary_contact_person "Rahim"`, `primary_email "rahim@acme.test"`; `financial_audit_logs` has 0 rows.

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. audit: `financial_audit_logs` has exactly 1 row, it is in audit(A1) and has the standard audit fields.
3. audit: `action_type == "deleted"`, `description == "Account 'Acme Ltd' deleted"`, `performed_by == U2.id`, `performed_at == NOW`.
4. audit: `ip_address is None`, `user_agent is None`.
5. audit: `changes` has the key `"before"` and does NOT have the key `"after"`.
6. audit: `changes["before"]["name"] == "Acme Ltd"`, `["primary_contact_person"] == "Rahim"`, `["primary_email"] == "rahim@acme.test"`.

### ACC-D-07 — audit row holds the full "before" snapshot including tags
- **Rules:** delete_account R5 [BUG-872]
- **Kind:** bug
- **Expect:** xfail BUG-872
- **Fails today on:** Then 3 (`changes["before"]` has only 3 keys)

**Given**
1. A1 = filled account.
2. T1, `usage_count 1`.
3. A1 has T1.

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. audit: audit(A1) has exactly 1 row.
3. audit: `changes == {"before": SNAP(**FILLED, tag_ids=[T1.id])}` (`is_active` in the snapshot is `True`, the value before the delete).

### ACC-D-08 — the account's tag assignment rows are kept
- **Rules:** delete_account R6 (assignments stay)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 3`.
3. T2, `usage_count 1`.
4. A1 has T1 (row X1). A1 has T2 (row X2).

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. count: tags(A1) `== [T1.id, T2.id]`.
3. unchanged: unchanged(X1) and unchanged(X2).

### ACC-D-09 — delete lowers the usage count of each assigned tag
- **Rules:** delete_account R6 [BUG-877]
- **Kind:** bug
- **Expect:** xfail BUG-877
- **Fails today on:** Then 3 (the count stays 3)

**Given**
1. A1.
2. T1, `usage_count 3`.
3. T2, `usage_count 1`.
4. Tag T4 = default tag, `name "Utility"`, `tag_code "utility"`, `usage_count 5` (NOT assigned to A1).
5. A1 has T1. A1 has T2.

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read T4: `usage_count == 5`.
3. re-read T1: `usage_count == 2`.
4. re-read T2: `usage_count == 0`.

### ACC-D-10 — delete never takes a usage count below 0
- **Rules:** delete_account R6 (floor 0)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 0` (already 0 although assigned).
3. A1 has T1.

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `is_deleted is True`.
3. re-read T1: `usage_count == 0`.

### ACC-D-11 — an inactive account can be deleted
- **Rules:** delete_account R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1, but `is_active False` (`is_deleted False`).

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. re-read A1: `is_deleted is True`, `is_active is False`, `deleted_at == NOW`, `deleted_by == U2.id`.
3. audit: audit(A1) has exactly 1 row with `action_type == "deleted"`.

### ACC-D-12 — client IP and user agent are written to the audit row
- **Rules:** delete_account R10 [BUG-140]
- **Kind:** bug
- **Expect:** xfail BUG-140
- **Fails today on:** Then 1 (the call raises `TypeError`: the parameters do not exist)

**Given**
1. A1.

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id, ip_address="203.0.113.7", user_agent="pytest-agent/1.0")`.

**Then**
1. returns: the row A1 — `result.id == A1.id`.
2. audit: audit(A1) has exactly 1 row.
3. audit: `ip_address == "203.0.113.7"`, `user_agent == "pytest-agent/1.0"`.

### ACC-D-13 — an account with a draft invoice cannot be deleted
- **Rules:** delete_account R7 [BUG-876], R7a [BUG-876]; Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-876
- **Fails today on:** Then 1 (no error is raised; invoices are not looked at and the account is deleted)

**Given**
1. A1 (`updated_by None`); `financial_audit_logs` has 0 rows.
2. T1, `usage_count 3`.
3. A1 has T1.
4. I1 = invoice of A1, draft.

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account has open invoices — settle or void them first"` (= OPEN_INVOICES; a draft invoice is open).
2. unchanged: unchanged(A1) — in particular `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`, `updated_by is None`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T1 `usage_count == 3`.
4. unchanged: unchanged(I1).
5. count: `account_invoices` has exactly 1 row.
### ACC-D-14 — an account with a confirmed, unpaid receivable invoice cannot be deleted
- **Rules:** delete_account R7 [BUG-876], R7a [BUG-876] (unpaid; both invoice types count)
- **Kind:** bug
- **Expect:** xfail BUG-876
- **Fails today on:** Then 1 (no error is raised; invoices are not looked at and the account is deleted)

**Given**
1. A1 (`updated_by None`); `financial_audit_logs` has 0 rows.
2. T1, `usage_count 3`.
3. A1 has T1.
4. I1 = invoice of A1, unpaid, but `invoice_type "receivable"`.

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account has open invoices — settle or void them first"` (= OPEN_INVOICES; confirmed with nothing paid is open, whatever the invoice type).
2. unchanged: unchanged(A1) — in particular `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`, `updated_by is None`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T1 `usage_count == 3`.
4. unchanged: unchanged(I1).
5. count: `account_invoices` has exactly 1 row.
### ACC-D-15 — an account with a partially paid invoice cannot be deleted
- **Rules:** delete_account R7 [BUG-876], R7a [BUG-876] (partial: `paid_amount < invoice_amount`)
- **Kind:** bug
- **Expect:** xfail BUG-876
- **Fails today on:** Then 1 (no error is raised; invoices are not looked at and the account is deleted)

**Given**
1. A1 (`updated_by None`); `financial_audit_logs` has 0 rows.
2. T1, `usage_count 3`.
3. A1 has T1.
4. I1 = invoice of A1, partial (`paid_amount 400.00` of `invoice_amount 1000.00`).

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account has open invoices — settle or void them first"` (= OPEN_INVOICES; a balance of 600.00 is still to pay).
2. unchanged: unchanged(A1) — in particular `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`, `updated_by is None`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T1 `usage_count == 3`.
4. unchanged: unchanged(I1) — in particular `paid_amount == Decimal("400.00")`, `payment_status == "partial"`.
5. count: `account_invoices` has exactly 1 row.
### ACC-D-16 — one open invoice is enough among settled and voided ones
- **Rules:** delete_account R7 [BUG-876] (one open invoice is enough), R7a [BUG-876]
- **Kind:** bug
- **Expect:** xfail BUG-876
- **Fails today on:** Then 1 (no error is raised; invoices are not looked at and the account is deleted)

**Given**
1. A1 (`updated_by None`); `financial_audit_logs` has 0 rows.
2. T1, `usage_count 3`.
3. A1 has T1.
4. I1 = invoice of A1, paid.
5. I2 = invoice of A1, voided.
6. I3 = invoice of A1, draft, but `invoice_type "receivable"`.

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account has open invoices — settle or void them first"` (= OPEN_INVOICES; I3 is open although I1 and I2 are not).
2. unchanged: unchanged(A1) — in particular `is_deleted is False`, `is_active is True`, `deleted_at is None`, `deleted_by is None`, `updated_by is None`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T1 `usage_count == 3`.
4. unchanged: unchanged(I1), unchanged(I2) and unchanged(I3).
5. count: `account_invoices` has exactly 3 rows.
### ACC-D-17 — an account whose only invoice is fully paid can be deleted
- **Rules:** delete_account R7b, R7a (other side: `paid_amount == invoice_amount`), R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1; `financial_audit_logs` has 0 rows.
2. I1 = invoice of A1, paid (`invoice_status "confirmed"`, `paid_amount 1000.00` of `invoice_amount 1000.00`, `payment_status "paid"`).

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id` (no error raised).
2. re-read A1: `is_deleted is True`, `is_active is False`, `deleted_at == NOW`, `deleted_by == U2.id`.
3. audit: audit(A1) has exactly 1 row with `action_type == "deleted"`.
4. unchanged: unchanged(I1) — in particular `invoice_status == "confirmed"`, `payment_status == "paid"`.
5. count: `account_invoices` has exactly 1 row.

### ACC-D-18 — an account whose only invoice is voided can be deleted
- **Rules:** delete_account R7b, R7a (other side: voided, although `payment_status` is "unpaid"), R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1; `financial_audit_logs` has 0 rows.
2. I1 = invoice of A1, voided (`invoice_status "voided"`, `paid_amount 0.00`, `payment_status "unpaid"`).

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id` (no error raised).
2. re-read A1: `is_deleted is True`, `is_active is False`, `deleted_at == NOW`, `deleted_by == U2.id`.
3. audit: audit(A1) has exactly 1 row with `action_type == "deleted"`.
4. unchanged: unchanged(I1) — in particular `invoice_status == "voided"`, `payment_status == "unpaid"`.
5. count: `account_invoices` has exactly 1 row.

### ACC-D-19 — open invoices of another account do not block the deletion
- **Rules:** delete_account R7b (other accounts' invoices), R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 (no invoices).
2. A2 (`name "Beta Co"`, in W1).
3. I1 = invoice of A2, draft.
4. I2 = invoice of A2, unpaid.

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: the row A1 — `result.id == A1.id` (no error raised).
2. re-read A1: `is_deleted is True`, `is_active is False`, `deleted_by == U2.id`.
3. unchanged: unchanged(A2) — in particular `is_deleted is False`.
4. unchanged: unchanged(I1) and unchanged(I2).

### ACC-D-20 — an account of another workspace gets the account error even with an open invoice
- **Rules:** delete_account R7c (R2 is checked before the invoices), R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A9 (`name "Zeta Corp"`, in W2).
2. I1 = invoice of A9, draft (`workspace_id W2.id`).

**When**
- `M.delete_account(session, account_id=A9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError`; `str(exc.value)` starts with `"Account {A9.id} "` (looser check intended: the rest of the text differs today and after the BUG-440 fix).
2. raises: `str(exc.value) != "Account has open invoices — settle or void them first"` (not OPEN_INVOICES).
3. unchanged: unchanged(A9) — in particular `is_deleted is False`.
4. unchanged: unchanged(I1).
5. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.

### ACC-D-21 — an already deleted account gets "already deleted" even with an open invoice
- **Rules:** delete_account R7c (R3 is checked before the invoices), R3
- **Kind:** error
- **Expect:** pass

**Given**
1. A1, but deleted (`deleted_at T0`, `deleted_by U1.id`).
2. I1 = invoice of A1, draft.

**When**
- `M.delete_account(session, account_id=A1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account {A1.id} is already deleted"` (not OPEN_INVOICES).
2. unchanged: unchanged(A1) — in particular `deleted_at == T0`, `deleted_by == U1.id`.
3. unchanged: unchanged(I1).
4. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.

## `AccountManager._assign_tags_to_account`

### ACC-AT-01 — an empty list writes nothing
- **Rules:** _assign_tags_to_account R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 2`.

**When**
- `M._assign_tags_to_account(session, account_id=A1.id, tag_ids=[], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `None`.
2. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows, T1 `usage_count == 2`.

### ACC-AT-02 — each new tag gets one assignment row and one increment
- **Rules:** _assign_tags_to_account R4, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 (no tags).
2. T1, `usage_count 0`.
3. T2, `usage_count 3`.

**When**
- `M._assign_tags_to_account(session, account_id=A1.id, tag_ids=[T1.id, T2.id], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `None`.
2. count: tags(A1) `== [T1.id, T2.id]` (exactly 2 assignment rows).
3. re-read both assignment rows: `account_id == A1.id`, `workspace_id == W1.id`, `assigned_by == U2.id`, `assigned_at is not None`, `id is not None`.
4. re-read T1: `usage_count == 1`.
5. re-read T2: `usage_count == 4`.

### ACC-AT-03 — a tag that is already assigned is skipped
- **Rules:** _assign_tags_to_account R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 1`.
3. T2, `usage_count 0`.
4. A1 has T1 (call that assignment row X1).

**When**
- `M._assign_tags_to_account(session, account_id=A1.id, tag_ids=[T1.id, T2.id], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `None`.
2. count: tags(A1) `== [T1.id, T2.id]` (exactly 2 assignment rows, not 3).
3. unchanged: unchanged(X1) — same `id`, `assigned_at == T0`, `assigned_by == U1.id`.
4. re-read T1: `usage_count == 1`.
5. re-read T2: `usage_count == 1`.

### ACC-AT-04 — the same id twice gives one assignment and one increment
- **Rules:** _assign_tags_to_account R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 (no tags).
2. T1, `usage_count 0`.

**When**
- `M._assign_tags_to_account(session, account_id=A1.id, tag_ids=[T1.id, T1.id], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `None`.
2. count: tags(A1) `== [T1.id]` (exactly 1 assignment row).
3. re-read T1: `usage_count == 1`.

### ACC-AT-05 — unknown tag id raises
- **Rules:** _assign_tags_to_account R2 [BUG-871]; Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-871
- **Fails today on:** Then 1 (no error is raised; the id is skipped)

**Given**
1. A1 (no tags).

**When**
- `M._assign_tags_to_account(session, account_id=A1.id, tag_ids=[MISSING], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account tag 999999999 not found"`.
2. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.

### ACC-AT-06 — tag of another workspace raises
- **Rules:** _assign_tags_to_account R2 [BUG-871]; Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-871
- **Fails today on:** Then 1 (no error is raised; the id is skipped)

**Given**
1. A1 (no tags).
2. T9 (in W2), `usage_count 1`.

**When**
- `M._assign_tags_to_account(session, account_id=A1.id, tag_ids=[T9.id], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account tag {T9.id} not found"`.
2. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows, T9 `usage_count == 1`.

### ACC-AT-07 — all ids are validated before anything is attached
- **Rules:** _assign_tags_to_account R7 [BUG-871], R2 [BUG-871]
- **Kind:** bug
- **Expect:** xfail BUG-871
- **Fails today on:** Then 1 (no error is raised; T1 is attached)

**Given**
1. A1 (no tags).
2. T1, `usage_count 0`.

**When**
- `M._assign_tags_to_account(session, account_id=A1.id, tag_ids=[T1.id, MISSING], workspace_id=W1.id, user_id=U2.id)` — the valid id comes first.

**Then**
1. raises: `ValueError "Account tag 999999999 not found"`.
2. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows, T1 `usage_count == 0`.

### ACC-AT-08 — an inactive tag that is not yet assigned raises
- **Rules:** _assign_tags_to_account R6 [BUG-2987]; Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-2987
- **Fails today on:** Then 1 (no error is raised; the inactive tag is attached)

**Given**
1. A1 (no tags).
2. T3 (inactive), `usage_count 0`.

**When**
- `M._assign_tags_to_account(session, account_id=A1.id, tag_ids=[T3.id], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account tag {T3.id} is not active"`.
2. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows, T3 `usage_count == 0`.

### ACC-AT-09 — an inactive tag that is already assigned is skipped without error
- **Rules:** _assign_tags_to_account R6 (already assigned), R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1.
2. T3 (inactive), `usage_count 1`.
3. A1 has T3 (call that assignment row X3).

**When**
- `M._assign_tags_to_account(session, account_id=A1.id, tag_ids=[T3.id], workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `None` (no error raised).
2. count: tags(A1) `== [T3.id]` (exactly 1 assignment row).
3. unchanged: unchanged(X3).
4. re-read T3: `usage_count == 1`.

### ACC-AT-10 — an inactive id in the list keeps valid tags from being attached
- **Rules:** _assign_tags_to_account R7, R6 [BUG-2987]
- **Kind:** bug
- **Expect:** xfail BUG-2987
- **Fails today on:** Then 1 (no error is raised; both tags are attached)

**Given**
1. A1 (no tags).
2. T1, `usage_count 0`.
3. T3 (inactive), `usage_count 0`.

**When**
- `M._assign_tags_to_account(session, account_id=A1.id, tag_ids=[T1.id, T3.id], workspace_id=W1.id, user_id=U2.id)` — the valid id comes first.

**Then**
1. raises: `ValueError "Account tag {T3.id} is not active"`.
2. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows, T1 `usage_count == 0`, T3 `usage_count == 0`.

## `AccountManager.assign_tag`

### ACC-A-01 — assigning a tag creates one assignment and raises the count
- **Rules:** assign_tag R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 (no tags).
2. T1, `usage_count 2`.

**When**
- `M.assign_tag(session, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `None`.
2. count: tags(A1) `== [T1.id]` (exactly 1 assignment row).
3. re-read that assignment row: `account_id == A1.id`, `tag_id == T1.id`, `workspace_id == W1.id`, `assigned_by == U2.id`, `assigned_at is not None`, `id is not None`.
4. re-read T1: `usage_count == 3`.

### ACC-A-02 — unknown account id is rejected
- **Rules:** assign_tag R1; Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 0`.

**When**
- `M.assign_tag(session, account_id=MISSING, tag_id=T1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account 999999999 not found"`.
2. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows, T1 `usage_count == 0`.

### ACC-A-03 — account of another workspace is rejected as not found
- **Rules:** assign_tag R2; Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A9 (in W2).
2. T1 (in W1), `usage_count 0`.

**When**
- `M.assign_tag(session, account_id=A9.id, tag_id=T1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account {A9.id} not found"`.
2. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows, T1 `usage_count == 0`.

### ACC-A-04 — a soft-deleted account cannot be tagged
- **Rules:** assign_tag R3 [BUG-863]; Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-863
- **Fails today on:** Then 1 (no error is raised; the tag is assigned)

**Given**
1. A1, but deleted.
2. T1, `usage_count 0`.

**When**
- `M.assign_tag(session, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account {A1.id} not found"`.
2. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows, T1 `usage_count == 0`.

### ACC-A-05 — unknown tag id is rejected
- **Rules:** assign_tag R4; Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 (no tags).

**When**
- `M.assign_tag(session, account_id=A1.id, tag_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account tag 999999999 not found"`.
2. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.

### ACC-A-06 — tag of another workspace is rejected as not found
- **Rules:** assign_tag R4; Errors row 2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 (in W1, no tags).
2. T9 (in W2), `usage_count 1`.

**When**
- `M.assign_tag(session, account_id=A1.id, tag_id=T9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account tag {T9.id} not found"`.
2. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows, T9 `usage_count == 1`.

### ACC-A-07 — when account and tag are both unknown, the account error wins
- **Rules:** assign_tag R4 (account checked first), R1
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no accounts and no tags.

**When**
- `M.assign_tag(session, account_id=MISSING, tag_id=MISSING2, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account 999999999 not found"`.
2. nothing written: `accounts` 0 rows, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows.

### ACC-A-08 — an inactive tag is rejected
- **Rules:** assign_tag R5; Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 (no tags).
2. T3 (inactive), `usage_count 0`.

**When**
- `M.assign_tag(session, account_id=A1.id, tag_id=T3.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account tag {T3.id} is not active"`.
2. nothing written: `accounts` 1 row, `account_tag_assignments` 0 rows, `financial_audit_logs` 0 rows, T3 `usage_count == 0`.

### ACC-A-09 — an inactive tag is rejected even when it is already assigned
- **Rules:** assign_tag R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1.
2. T3 (inactive), `usage_count 1`.
3. A1 has T3 (call that assignment row X3).

**When**
- `M.assign_tag(session, account_id=A1.id, tag_id=T3.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `ValueError "Account tag {T3.id} is not active"`.
2. unchanged: unchanged(X3).
3. nothing written: `accounts` 1 row, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T3 `usage_count == 1`.

### ACC-A-10 — assigning an already assigned tag changes nothing
- **Rules:** assign_tag R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 (`updated_by None`).
2. T1, `usage_count 1`.
3. A1 has T1 (call that assignment row X1).

**When**
- `M.assign_tag(session, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `None` (no error raised).
2. count: tags(A1) `== [T1.id]` (exactly 1 assignment row).
3. unchanged: unchanged(X1) — same `id`, `assigned_at == T0`, `assigned_by == U1.id`.
4. re-read T1: `usage_count == 1`.
5. audit: `financial_audit_logs` has 0 rows.
6. re-read A1: `updated_by is None`.

### ACC-A-11 — a real assignment writes an "updated" audit row with the tag ids
- **Rules:** assign_tag R8 [BUG-873]
- **Kind:** bug
- **Expect:** xfail BUG-873
- **Fails today on:** Then 3 (no audit row is written)

**Given**
1. A1 (`name "Acme Ltd"`); `financial_audit_logs` has 0 rows.
2. T1, `usage_count 1`.
3. T2, `usage_count 0`.
4. A1 has T1.

**When**
- `M.assign_tag(session, account_id=A1.id, tag_id=T2.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `None`.
2. count: tags(A1) `== [T1.id, T2.id]`.
3. audit: `financial_audit_logs` has exactly 1 row, it is in audit(A1) and has the standard audit fields.
4. audit: `action_type == "updated"`, `description == "Account 'Acme Ltd' updated"`, `performed_by == U2.id`, `performed_at == NOW`.
5. audit: `changes == {"before": {"tag_ids": [T1.id]}, "after": {"tag_ids": [T1.id, T2.id]}}`.

### ACC-A-12 — a real assignment stamps the account's `updated_by`
- **Rules:** assign_tag R8 [BUG-873]
- **Kind:** bug
- **Expect:** xfail BUG-873
- **Fails today on:** Then 3 (`updated_by` stays `None`)

**Given**
1. A1 (`updated_by None`, `updated_at None`).
2. T1, `usage_count 0`.

**When**
- `M.assign_tag(session, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `None`.
2. count: tags(A1) `== [T1.id]`.
3. re-read A1: `updated_by == U2.id`.
4. re-read A1: `updated_at is not None`.

### ACC-A-13 — an inactive account can be tagged
- **Rules:** assign_tag R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1, but `is_active False` (`is_deleted False`).
2. T1, `usage_count 0`.

**When**
- `M.assign_tag(session, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `None` (no error raised).
2. count: tags(A1) `== [T1.id]`.
3. re-read T1: `usage_count == 1`.

### ACC-A-14 — the database forbids a second assignment of the same tag to the same account
- **Rules:** assign_tag R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 1`.
3. A1 has T1.

**When**
- insert directly one more `account_tag_assignments` row: `account_id A1.id`, `tag_id T1.id`, `workspace_id W1.id`, `assigned_by U2.id`, `assigned_at NOW`, and flush (target `database`).

**Then**
1. raises: `IntegrityError` on flush.
2. count: tags(A1) `== [T1.id]` (still exactly 1 assignment row).

## `AccountManager.unassign_tag`

### ACC-UN-01 — removing a tag deletes the assignment and lowers the count
- **Rules:** unassign_tag R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 3`.
3. T2, `usage_count 1`.
4. A1 has T1. A1 has T2 (row X2).

**When**
- `M.unassign_tag(session, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id)` — no `user_id` argument.

**Then**
1. returns: `None`.
2. count: tags(A1) `== [T2.id]` (exactly 1 assignment row left).
3. re-read T1: `usage_count == 2`.
4. re-read T2: `usage_count == 1`.
5. unchanged: unchanged(X2).

### ACC-UN-02 — a usage count of 0 stays 0
- **Rules:** unassign_tag R5 (floor 0)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 0` (already 0 although assigned).
3. A1 has T1.

**When**
- `M.unassign_tag(session, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id)` — no `user_id` argument.

**Then**
1. returns: `None`.
2. count: tags(A1) `== []`.
3. re-read T1: `usage_count == 0`.

### ACC-UN-03 — unknown account id is rejected
- **Rules:** unassign_tag R1; Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 1`.
3. A1 has T1.

**When**
- `M.unassign_tag(session, account_id=MISSING, tag_id=T1.id, workspace_id=W1.id)` — no `user_id` argument.

**Then**
1. raises: `ValueError "Account 999999999 not found"`.
2. count: tags(A1) `== [T1.id]`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T1 `usage_count == 1`.

### ACC-UN-04 — account of another workspace is rejected as not found
- **Rules:** unassign_tag R2; Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A9 (in W2).
2. T9 (in W2), `usage_count 1`.
3. A9 has T9 (assignment `workspace_id W2.id`).

**When**
- `M.unassign_tag(session, account_id=A9.id, tag_id=T9.id, workspace_id=W1.id)` — no `user_id` argument.

**Then**
1. raises: `ValueError "Account {A9.id} not found"`.
2. count: tags(A9) `== [T9.id]`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T9 `usage_count == 1`.

### ACC-UN-05 — a tag cannot be removed from a soft-deleted account
- **Rules:** unassign_tag R3 [BUG-863]; Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-863
- **Fails today on:** Then 1 (no error is raised; the assignment is removed)

**Given**
1. A1, but deleted.
2. T1, `usage_count 1`.
3. A1 has T1.

**When**
- `M.unassign_tag(session, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id)` — no `user_id` argument.

**Then**
1. raises: `ValueError "Account {A1.id} not found"`.
2. count: tags(A1) `== [T1.id]`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T1 `usage_count == 1`.

### ACC-UN-06 — removing a tag that is not assigned is rejected and changes nothing
- **Rules:** unassign_tag R4 (error raised, nothing changes)
- **Kind:** error
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 1`.
3. T2, `usage_count 4` (NOT assigned to A1).
4. A1 has T1.

**When**
- `M.unassign_tag(session, account_id=A1.id, tag_id=T2.id, workspace_id=W1.id)` — no `user_id` argument.

**Then**
1. raises: `ValueError` (assert only the type here, not the text).
2. count: tags(A1) `== [T1.id]`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T1 `usage_count == 1`, T2 `usage_count == 4`.

### ACC-UN-07 — "not assigned" uses the "assignment not found" message
- **Rules:** unassign_tag R4 [BUG-879]; Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-879
- **Fails today on:** Then 1 (the text is "Tag {T2.id} is not assigned to account {A1.id}")

**Given**
1. A1 (no tags).
2. T2, `usage_count 4` (NOT assigned to A1).

**When**
- `M.unassign_tag(session, account_id=A1.id, tag_id=T2.id, workspace_id=W1.id)` — no `user_id` argument.

**Then**
1. raises: `ValueError "Tag {T2.id} assignment not found for account {A1.id}"`.
2. re-read T2: `usage_count == 4`.

### ACC-UN-08 — removing an unknown tag id is rejected and changes nothing
- **Rules:** unassign_tag R4 (unknown tag id)
- **Kind:** error
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 1`.
3. A1 has T1.

**When**
- `M.unassign_tag(session, account_id=A1.id, tag_id=MISSING, workspace_id=W1.id)` — no `user_id` argument.

**Then**
1. raises: `ValueError` (assert only the type here, not the text).
2. count: tags(A1) `== [T1.id]`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T1 `usage_count == 1`.

### ACC-UN-09 — an unknown tag id uses the "assignment not found" message
- **Rules:** unassign_tag R4 [BUG-879]; Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-879
- **Fails today on:** Then 1 (the text is "Tag 999999999 is not assigned to account {A1.id}")

**Given**
1. A1 (no tags).

**When**
- `M.unassign_tag(session, account_id=A1.id, tag_id=MISSING, workspace_id=W1.id)` — no `user_id` argument.

**Then**
1. raises: `ValueError "Tag 999999999 assignment not found for account {A1.id}"`.
2. count: `account_tag_assignments` has 0 rows.

### ACC-UN-10 — a tag of another workspace is rejected and not touched
- **Rules:** unassign_tag R4 (tag of another workspace)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 (in W1, no tags).
2. A9 (in W2).
3. T9 (in W2), `usage_count 1`.
4. A9 has T9 (assignment `workspace_id W2.id`).

**When**
- `M.unassign_tag(session, account_id=A1.id, tag_id=T9.id, workspace_id=W1.id)` — no `user_id` argument.

**Then**
1. raises: `ValueError` (assert only the type here, not the text).
2. count: tags(A9) `== [T9.id]`.
3. nothing written: `accounts` 2 rows, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T9 `usage_count == 1`.

### ACC-UN-11 — an inactive tag can be removed from an account
- **Rules:** unassign_tag R6, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1.
2. T3 (inactive), `usage_count 2`.
3. A1 has T3.

**When**
- `M.unassign_tag(session, account_id=A1.id, tag_id=T3.id, workspace_id=W1.id)` — no `user_id` argument.

**Then**
1. returns: `None` (no error raised).
2. count: tags(A1) `== []`.
3. re-read T3: `usage_count == 1`, `is_active is False`.

### ACC-UN-12 — a real removal writes an "updated" audit row with the tag ids
- **Rules:** unassign_tag R7 [BUG-873]
- **Kind:** bug
- **Expect:** xfail BUG-873
- **Fails today on:** Then 1 (the call raises `TypeError`: `user_id` does not exist; and no audit row is written)

**Given**
1. A1 (`name "Acme Ltd"`); `financial_audit_logs` has 0 rows.
2. T1, `usage_count 1`.
3. T2, `usage_count 1`.
4. A1 has T1. A1 has T2.

**When**
- `M.unassign_tag(session, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `None`.
2. count: tags(A1) `== [T2.id]`.
3. audit: `financial_audit_logs` has exactly 1 row, it is in audit(A1) and has the standard audit fields.
4. audit: `action_type == "updated"`, `description == "Account 'Acme Ltd' updated"`, `performed_by == U2.id`.
5. audit: `changes == {"before": {"tag_ids": [T1.id, T2.id]}, "after": {"tag_ids": [T2.id]}}`.

### ACC-UN-13 — a real removal stamps the account's `updated_by`
- **Rules:** unassign_tag R7 [BUG-873]
- **Kind:** bug
- **Expect:** xfail BUG-873
- **Fails today on:** Then 1 (the call raises `TypeError`: `user_id` does not exist; and `updated_by` is not set)

**Given**
1. A1 (`updated_by None`, `updated_at None`).
2. T1, `usage_count 1`.
3. A1 has T1.

**When**
- `M.unassign_tag(session, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `None`.
2. count: tags(A1) `== []`.
3. re-read A1: `updated_by == U2.id`.
4. re-read A1: `updated_at is not None`.

### ACC-UN-14 — `user_id` is a required argument
- **Rules:** unassign_tag Inputs (`user_id` required, no default) [BUG-873]; R7 [BUG-873]
- **Kind:** bug
- **Expect:** xfail BUG-873
- **Fails today on:** Then 1 (no error is raised: the parameter does not exist yet, the call succeeds and the tag is removed)

**Given**
1. A1.
2. T1, `usage_count 1`.
3. A1 has T1.

**When**
- `M.unassign_tag(session, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id)` — `user_id` is deliberately NOT passed; write the call exactly like this.

**Then**
1. raises: `TypeError` (missing required argument `user_id`; assert only the type).
2. count: tags(A1) `== [T1.id]`.
3. nothing written: `accounts` 1 row, `account_tag_assignments` 1 row, `financial_audit_logs` 0 rows, T1 `usage_count == 1`.

## `AccountManager.get_tags_for_account`

### ACC-T-01 — returns the account's tags, each once
- **Rules:** get_tags_for_account R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1.
2. A2.
3. T1, `usage_count 1`.
4. T2, `usage_count 1`.
5. Tag T4 = default tag, `name "Utility"`, `tag_code "utility"`, `usage_count 1`.
6. A1 has T1. A1 has T2. A2 has T4.

**When**
- `M.get_tags_for_account(session, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: a list of AccountTag objects with `len(result) == 2`.
2. returns: the set of `id`s `== {T1.id, T2.id}`.
3. returns: the set of `tag_code`s `== {"supplier", "client"}`.

### ACC-T-02 — an account without tags gives an empty list
- **Rules:** get_tags_for_account R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 (no tags).
2. A2.
3. T1, `usage_count 1`.
4. A2 has T1.

**When**
- `M.get_tags_for_account(session, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### ACC-T-03 — an unknown account id gives an empty list
- **Rules:** get_tags_for_account R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1.
2. T1, `usage_count 1`.
3. A1 has T1.

**When**
- `M.get_tags_for_account(session, account_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []` (no error raised).

### ACC-T-04 — asking with another workspace id gives an empty list
- **Rules:** get_tags_for_account R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 (in W1).
2. T1 (in W1), `usage_count 1`.
3. A1 has T1 (assignment `workspace_id W1.id`).

**When**
- `M.get_tags_for_account(session, account_id=A1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### ACC-T-05 — inactive tags are not returned
- **Rules:** get_tags_for_account R4 [BUG-865]
- **Kind:** bug
- **Expect:** xfail BUG-865
- **Fails today on:** Then 1 (the inactive tag T3 is returned too)

**Given**
1. A1.
2. T1, `usage_count 1`.
3. T3 (inactive), `usage_count 1`.
4. A1 has T1. A1 has T3.

**When**
- `M.get_tags_for_account(session, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1` and `result[0].id == T1.id`.

### ACC-T-06 — tags are ordered by name ignoring case
- **Rules:** get_tags_for_account R5 [BUG-1486]
- **Kind:** bug
- **Expect:** xfail BUG-1486 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no ordering is applied)

**Given**
1. A1.
2. Three default tags, inserted in exactly this order, each `usage_count 1`: `name "Bravo"` / `tag_code "b1"`; `name "charlie"` / `tag_code "c1"`; `name "alpha"` / `tag_code "a1"`.
3. A1 has each of the three tags; assignment rows inserted in the same order (Bravo, charlie, alpha).

**When**
- `M.get_tags_for_account(session, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: names in order `== ["alpha", "Bravo", "charlie"]` (neither ascending nor descending tag id).

### ACC-T-07 — tags with the same name ignoring case are ordered by id
- **Rules:** get_tags_for_account R5 [BUG-1486]
- **Kind:** bug
- **Expect:** xfail BUG-1486 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no ordering is applied)

**Given**
1. A1.
2. Three default tags, inserted in exactly this order, each `usage_count 1`: `name "beta"` / `tag_code "b1"` (call it B); `name "ALPHA"` / `tag_code "a1"` (call it H); `name "alpha"` / `tag_code "a2"` (call it L; `L.id > H.id`).
3. A1 has each of the three tags; assignment rows inserted in the same order (B, H, L).

**When**
- `M.get_tags_for_account(session, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: ids in order `== [H.id, L.id, B.id]`.

### ACC-T-08 — the tags of a soft-deleted account are still returned
- **Rules:** get_tags_for_account R6
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A1, but deleted (so also `is_active False`).
2. T1, `usage_count 1`.
3. A1 has T1.

**When**
- `M.get_tags_for_account(session, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 1` and `result[0].id == T1.id`.

### ACC-T-09 — a system tag is not placed first
- **Rules:** get_tags_for_account R5 [BUG-1486] (system tags not grouped first)
- **Kind:** bug
- **Expect:** xfail BUG-1486 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no ordering is applied)

**Given**
1. A1.
2. Three default tags, inserted in exactly this order, each `usage_count 1`: `name "Zulu"` / `tag_code "z1"`, but `is_system_tag True` (call it Z); `name "alpha"` / `tag_code "a1"` (call it H); `name "Mike"` / `tag_code "m1"` (call it K).
3. A1 has each of the three tags; assignment rows inserted in the same order (Z, H, K).

**When**
- `M.get_tags_for_account(session, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: ids in order `== [H.id, K.id, Z.id]` (neither ascending nor descending tag id, and not system-first).

### ACC-T-10 — the tags SELECT carries an ORDER BY
- **Rules:** get_tags_for_account R5 [BUG-1486]
- **Kind:** bug
- **Expect:** xfail BUG-1486
- **Author:** claude
- **Fails today on:** Then 3 (the query has no `ORDER BY`)

**Given**
1. A1.
2. T1, `usage_count 1`. T2, `usage_count 1`.
3. A1 has T1. A1 has T2.
4. `session.expire_all()`, then a recorder of the SQL of the call.

**When**
- `M.get_tags_for_account(session, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: the set of ids `== {T1.id, T2.id}`.
2. statement: exactly one recorded `SELECT` contains `account_tags` (the tags SELECT).
3. statement: `"ORDER BY" in` the tags SELECT.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `update_account` R1a [BUG-2986] | `AccountService.update_account` / `PUT /accounts/{id}/` | Not found, other workspace and soft-deleted answer 404 `Account with ID {id} not found`, never 500. |
| `delete_account` R1a [BUG-2986] | `AccountService.delete_account` / `DELETE /accounts/{id}/` | Not found / other workspace → 404; already deleted → 400; open invoices → 400; never 500. |
| `search_accounts` R13 [BUG-867] | `GET /accounts/` | `limit=0` and negative `limit` answer 422; `limit=1` accepted. |
| `search_accounts` R1a [BUG-878] (API part) | `AccountService` / `GET /accounts/` | `include_inactive` is reachable from the endpoint and defaults to false. |
| `get_account` R4 [BUG-862] (API part) | `AccountService` / `GET /accounts/{id}/` | Soft-deleted account answers 404 by default; `include_deleted` exposure. |
| `create_account` R10, `update_account` R18, `delete_account` R10 [BUG-140] (pass-through) | endpoints → `AccountService` | Client IP (trusted-proxy resolved) and user agent of the request reach the manager. |
| `create_account` R6a / R6b, `update_account` R14 / R11a (HTTP status) | `AccountService` | `Account tag {id} not found` → 404; `Account tag {id} is not active` → 4xx business error; never 500. |
| `create_account` R11a, `update_account` R20a [BUG-874] (HTTP status) | `AccountService` | Duplicate account code answers 409. |
| `unassign_tag` R4 [BUG-879] (HTTP status) | `AccountService.unassign_tag` / `DELETE /accounts/{id}/tags/{tag_id}/` | "assignment not found" answers 404, not 422. |
| `create_account` R2, R12; `update_account` R4a, R5, R6 (HTTP status) | `POST /accounts/`, `PUT /accounts/{id}/` | Schema rejections answer 422 and nothing is written. |

## Spec gaps
None. (Gaps 1–8 of revision 1 were closed by the spec's Gap log G1–G8; this revision found no new gap.)

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_account` | R1 | ACC-C-01, ACC-C-02 |
| `create_account` | R2 [BUG-860] | ACC-C-04, ACC-C-05, ACC-C-06, ACC-C-07 |
| `create_account` | R3 | ACC-C-01, ACC-C-03 |
| `create_account` | R4 | ACC-C-01 |
| `create_account` | R5 | ACC-C-01, ACC-C-10 |
| `create_account` | R6 | ACC-C-08, ACC-C-09 |
| `create_account` | R6a [BUG-871] / Errors row 1 | ACC-C-11, ACC-C-12, ACC-C-13 |
| `create_account` | R6b [BUG-2987] / Errors row 2 | ACC-C-14, ACC-C-15 |
| `create_account` | R8 | ACC-C-16, ACC-C-04 |
| `create_account` | R9 [BUG-872] | ACC-C-16 (today's keys), ACC-C-17, ACC-C-18 |
| `create_account` | R10 [BUG-140] | ACC-C-16 (NULL when not passed), ACC-C-19; pass-through Deferred |
| `create_account` | R11 | ACC-C-20 |
| `create_account` | R11a [BUG-874] / Errors row 3 | ACC-C-21, ACC-C-22, ACC-C-23, ACC-C-24, ACC-C-25, ACC-C-26, ACC-C-33, ACC-C-34, ACC-C-35; 409 Deferred |
| `create_account` | R11b [BUG-874] | ACC-C-30, ACC-C-31, ACC-C-32 (stored form); ACC-C-25, ACC-C-33, ACC-C-34 (blank never conflicts) |
| `create_account` | R12 [BUG-875] | ACC-C-27, ACC-C-28, ACC-C-29; valid emails stored: ACC-C-02 |
| `update_account` | R1 / Errors row 1 | ACC-U-01 |
| `update_account` | R1a [BUG-2986] | Deferred |
| `update_account` | R2 [BUG-440] / Errors row 2 | ACC-U-02, ACC-U-03 |
| `update_account` | R3 [BUG-863] / Errors row 3 | ACC-U-04 |
| `update_account` | R4 | ACC-U-05, ACC-U-06, ACC-U-07, ACC-U-08, ACC-U-21 |
| `update_account` | R4a [BUG-875] | ACC-U-09, ACC-U-10, ACC-U-11 |
| `update_account` | R5 [BUG-608] | ACC-U-12, ACC-U-13, ACC-U-14, ACC-U-15, ACC-U-16 |
| `update_account` | R6 [BUG-860] | ACC-U-18, ACC-U-19, ACC-U-20 |
| `update_account` | R7 | ACC-U-07, ACC-U-08, ACC-G-07, ACC-S-01, ACC-S-02 |
| `update_account` | R8 [BUG-869] | ACC-U-05, ACC-U-27 (changed); ACC-U-22, ACC-U-24, ACC-U-26 |
| `update_account` | R9 | ACC-U-05 |
| `update_account` | R10 | ACC-U-16, ACC-U-17, ACC-U-21 |
| `update_account` | R11 | ACC-U-28, ACC-U-29, ACC-U-31, ACC-U-32, ACC-U-39, ACC-U-56 |
| `update_account` | R11a [BUG-2987] / Errors row 5 | ACC-U-38, ACC-U-39 |
| `update_account` | R12 | ACC-U-28, ACC-U-29, ACC-U-30, ACC-U-32, ACC-U-56 |
| `update_account` | R13 [BUG-870] | ACC-U-32 (set and counts), ACC-U-33, ACC-U-34 |
| `update_account` | R13a [BUG-1487] | ACC-U-55; ACC-U-56 (active links still removed) |
| `update_account` | R14 [BUG-871] / Errors row 4 | ACC-U-35, ACC-U-36, ACC-U-37 |
| `update_account` | R15 [BUG-632] | ACC-U-27, ACC-U-40 (changed); ACC-U-23, ACC-U-25, ACC-U-26 |
| `update_account` | R16 [BUG-872] | ACC-U-40 (today's keys), ACC-U-41 |
| `update_account` | R17 | ACC-U-40, ACC-U-18 |
| `update_account` | R18 [BUG-140] | ACC-U-40 (NULL when not passed), ACC-U-42; pass-through Deferred |
| `update_account` | R19 | ACC-U-05 |
| `update_account` | R20 | ACC-U-43 |
| `update_account` | R20a [BUG-874] / Errors row 6 | ACC-U-44, ACC-U-45, ACC-U-46, ACC-U-47, ACC-U-48, ACC-U-49, ACC-U-50, ACC-U-54; 409 Deferred |
| `update_account` | R20b [BUG-874] | ACC-U-51, ACC-U-52, ACC-U-53 (stored form); ACC-U-54 (blank never conflicts) |
| `get_account` | R1 | ACC-G-01 |
| `get_account` | R2 | ACC-G-02 |
| `get_account` | R3 | ACC-G-03, ACC-G-06 |
| `get_account` | R4 [BUG-862] | ACC-G-04, ACC-G-05, ACC-G-06; API part Deferred |
| `get_account` | R5 | ACC-G-07 |
| `search_accounts` | R1 | ACC-S-01, ACC-S-13, ACC-S-25 |
| `search_accounts` | R1a [BUG-878] | ACC-S-02; API part Deferred |
| `search_accounts` | R2 | ACC-S-01 (`None`), ACC-S-04, ACC-S-05 |
| `search_accounts` | R3 | ACC-S-06, ACC-S-07, ACC-S-25 |
| `search_accounts` | R4 [BUG-868] | ACC-S-08, ACC-S-09, ACC-S-10 |
| `search_accounts` | R5 [BUG-637] | ACC-S-05, ACC-S-11 |
| `search_accounts` | R6 | ACC-S-01 (`None`), ACC-S-12 |
| `search_accounts` | R7 | ACC-S-13, ACC-S-14, ACC-S-15 |
| `search_accounts` | R8 [BUG-861] | ACC-S-16, ACC-S-17 |
| `search_accounts` | R9 [BUG-864] | ACC-S-18 |
| `search_accounts` | R10 | ACC-S-19 |
| `search_accounts` | R11 [BUG-866] | ACC-S-20, ACC-S-26 |
| `search_accounts` | R12 | ACC-S-21, ACC-S-22, ACC-S-23, ACC-S-24, ACC-S-25, ACC-S-26 |
| `search_accounts` | R13 [BUG-867] | Deferred |
| `search_accounts` | R14 | ACC-S-03, ACC-S-07, ACC-S-23 |
| `delete_account` | R1 / Errors row 1 | ACC-D-02 |
| `delete_account` | R1a [BUG-2986] | Deferred |
| `delete_account` | R2 [BUG-440] / Errors row 2 | ACC-D-03, ACC-D-04 |
| `delete_account` | R3 / Errors row 3 | ACC-D-05 |
| `delete_account` | R4 | ACC-D-01, ACC-D-11 |
| `delete_account` | R5 [BUG-872] | ACC-D-06 (today's keys), ACC-D-07 |
| `delete_account` | R6 [BUG-877] | ACC-D-08, ACC-D-09, ACC-D-10 |
| `delete_account` | R7 [BUG-876] / Errors row 4 | ACC-D-13, ACC-D-14, ACC-D-15, ACC-D-16; HTTP status Deferred |
| `delete_account` | R7a [BUG-876] | ACC-D-13 (draft), ACC-D-14 (unpaid, receivable), ACC-D-15 (partial), ACC-D-16; other side: ACC-D-17 (paid), ACC-D-18 (voided) |
| `delete_account` | R7b | ACC-D-01 (no invoices), ACC-D-17, ACC-D-18, ACC-D-19 |
| `delete_account` | R7c | ACC-D-20 (R2 first), ACC-D-21 (R3 first); R1: an unknown id has no invoices — ACC-D-02 |
| `delete_account` | R7d | none — the spec states there is nothing to test (no lock) |
| `delete_account` | R8 | ACC-D-11 |
| `delete_account` | R9 | ACC-D-01 |
| `delete_account` | R10 [BUG-140] | ACC-D-06 (NULL when not passed), ACC-D-12; pass-through Deferred |
| `_assign_tags_to_account` | R1 | ACC-AT-01, ACC-C-10 |
| `_assign_tags_to_account` | R2 [BUG-871] / Errors row 1 | ACC-AT-05, ACC-AT-06, ACC-AT-07 |
| `_assign_tags_to_account` | R3 | ACC-AT-03, ACC-AT-09 |
| `_assign_tags_to_account` | R4 | ACC-AT-02, ACC-AT-03, ACC-C-08 |
| `_assign_tags_to_account` | R5 | ACC-AT-04, ACC-C-09, ACC-U-31 |
| `_assign_tags_to_account` | R6 [BUG-2987] / Errors row 2 | ACC-AT-08, ACC-AT-09, ACC-AT-10 |
| `_assign_tags_to_account` | R7 [BUG-871] | ACC-AT-07, ACC-AT-10, ACC-C-13, ACC-C-15, ACC-U-37 |
| `_assign_tags_to_account` | R8 | ACC-AT-02 |
| `assign_tag` | R1 / Errors row 1 | ACC-A-02, ACC-A-07 |
| `assign_tag` | R2 / Errors row 1 | ACC-A-03 |
| `assign_tag` | R3 [BUG-863] / Errors row 1 | ACC-A-04 |
| `assign_tag` | R4 / Errors row 2 | ACC-A-05, ACC-A-06, ACC-A-07 |
| `assign_tag` | R5 / Errors row 3 | ACC-A-08, ACC-A-09 |
| `assign_tag` | R6 | ACC-A-10 |
| `assign_tag` | R7 | ACC-A-01 |
| `assign_tag` | R8 [BUG-873] | ACC-A-11, ACC-A-12 |
| `assign_tag` | R9 | ACC-A-13 |
| `assign_tag` | R10 | ACC-A-14 |
| `unassign_tag` | R1 / Errors row 1 | ACC-UN-03 |
| `unassign_tag` | R2 / Errors row 1 | ACC-UN-04 |
| `unassign_tag` | R3 [BUG-863] / Errors row 1 | ACC-UN-05 |
| `unassign_tag` | R4 [BUG-879] / Errors row 2 | ACC-UN-06, ACC-UN-07, ACC-UN-08, ACC-UN-09, ACC-UN-10; 404 Deferred |
| `unassign_tag` | R5 | ACC-UN-01, ACC-UN-02, ACC-UN-11 |
| `unassign_tag` | R6 | ACC-UN-11 |
| `unassign_tag` | R7 [BUG-873] | ACC-UN-12, ACC-UN-13 |
| `unassign_tag` | Inputs — `user_id` required [BUG-873] | ACC-UN-14 |
| `get_tags_for_account` | R1 | ACC-T-01 |
| `get_tags_for_account` | R2 | ACC-T-02, ACC-T-03 |
| `get_tags_for_account` | R3 | ACC-T-04 |
| `get_tags_for_account` | R4 [BUG-865] | ACC-T-05 |
| `get_tags_for_account` | R5 [BUG-1486] | ACC-T-06, ACC-T-07, ACC-T-09, ACC-T-10 |
| `get_tags_for_account` | R6 | ACC-T-08 |
