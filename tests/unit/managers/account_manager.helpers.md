# Helpers for `test_account_manager.py`

## Fixtures (add as test arguments)
- `db` — the database session (the cards' `session`).
- `M` — the `AccountManager()` instance. `w1`, `w2` — W1, W2. `u1`, `u2` — U1, U2.
- `mk_account`, `mk_tag`, `mk_link`, `mk_invoice` — row builders (fixtures too). Each inserts one row, flushes, returns it.
- The clock is patched to `NOW` automatically.
- Every fixture a test uses (also `u1`, `mk_link`) must be in its argument list.

## Builders
- `mk_account(deleted=False, **columns)` — default account; any column by keyword.
- `mk_tag(name, tag_code, **columns)` — default tag.
- `mk_link(account, tag, **columns)` — "A has T".
- `mk_invoice(account, state, **columns)` — "invoice of A"; `state`: `"draft"`, `"unpaid"`, `"partial"`, `"paid"`, `"voided"`.

## Card says -> write
| Card says | Write |
|---|---|
| `W1.id`, `U2.id`, `{A1.id}` | `w1.id`, `u2.id`, `a1.id` |
| MISSING, MISSING2, T0, NOW, FILLED, OPEN_INVOICES | constants with these names |
| A1 | `a1 = mk_account()` |
| A2 | `a2 = mk_account(name="Beta Co")` |
| A9 | `a9 = mk_account(name="Zeta Corp", workspace_id=w2.id)` |
| A1, but `city "Dhaka"` | `a1 = mk_account(city="Dhaka")` |
| A1, but deleted | `a1 = mk_account(deleted=True)` |
| A9 (in W2), but deleted | `a9 = mk_account(name="Zeta Corp", workspace_id=w2.id, deleted=True)` |
| A1 = filled account | `a1 = mk_account(**FILLED)` |
| five accounts differing only in `name` | `for n in ["Alpha", "Bravo"]: mk_account(name=n)` |
| 101 accounts "Account 001" … "Account 101" | `for i in range(1, 102): mk_account(name=f"Account {i:03d}")` |
| T1, `usage_count 3` | `t1 = mk_tag("Supplier", "supplier", usage_count=3)` |
| T2, `usage_count 0` | `t2 = mk_tag("Client", "client", usage_count=0)` |
| T3 (inactive), `usage_count 1` | `t3 = mk_tag("Legacy", "legacy", is_active=False, usage_count=1)` |
| T9 (in W2), `usage_count 1` | `t9 = mk_tag("Supplier", "supplier", workspace_id=w2.id, usage_count=1)` |
| Tag T4 = default tag, `name "Utility"`, `tag_code "utility"`, `usage_count 5` | `t4 = mk_tag("Utility", "utility", usage_count=5)` |
| A1 has T1 (row X1) | `x1 = mk_link(a1, t1)` |
| assignment row with other values | `mk_link(a1, t1, workspace_id=w2.id)` |
| I1 = invoice of A1, draft | `i1 = mk_invoice(a1, "draft")` |
| I1 = invoice of A1, unpaid, but `invoice_type "receivable"` | `i1 = mk_invoice(a1, "unpaid", invoice_type="receivable")` |
| a named row ("call it L", "Account A3 = …") | keep it: `low = mk_account(name="alpha")`, then `low.id` |
| "W1 has no accounts", "Nothing", "has 0 rows" in Given | no code |
| the 13 optional fields | tuple `OPTIONAL_FIELDS` |
| SNAP(…) | function: `SNAP()`, `SNAP(**FILLED, tag_ids=[t1.id])`; a FILLED key replaced: `SNAP(**{**FILLED, "city": "X"})` |
| tags(A1), audit(A1) | `tags(db, a1)`, `audit(db, a1)` |

Each row above shows ONE change. Several "but" values -> one keyword each, only those this card's Given names for that row.
Build Given rows in the order written. Take "before" values after the last Given row, just before the call.

## Reading helpers (plain functions)
- `reread(db, row)` — fresh copy of any row (also of a returned Account); `None` if deleted.
- `snap(db, row)` — dict of all columns of any row.
- `count_rows(db, Model, **equals)` — `count_rows(db, Account, workspace_id=w1.id, name="Acme Ltd")`.
- `written(db)` — the "nothing written" values.
- `tags(db, account)` — sorted tag ids. `links(db, account)` — assignment rows by tag id. `link_row(db, account, tag)` — that one row or `None`.
- `audit(db, account)` — the account's `FinancialAuditLog` rows.

## Already imported (never import)
`pytest`, `Decimal`, `ValidationError`, `IntegrityError`, `Account`, `AccountTag`, `AccountTagAssignment`, `AccountInvoice`, `FinancialAuditLog`, `AccountCreate`, `AccountUpdate`, `OPTIONAL_FIELDS`, `SNAP`.

## Then lines
- Before the assertions of Then line N write `# Then N` on its own line (each once, in order); for `raises:` before `with pytest.raises`.
- Expected values are the card's literals (`"Account 'Acme Ltd' updated"`, `1`), never read from a row (`a1.name`) or a "before" variable.
- A line with two parts ("exactly 1 row, it is in audit(A1)") -> assert both.
- `returns:` -> `result = M.method(db, ...)`, then `assert result.id == a1.id` / `result is None` / `result == []`.
- after create ("call it N") -> N is `result`: `assert result.id is not None`, then `reread(db, result)`, `tags(db, result)`, `audit(db, result)`.
- `raises: ValueError "text"` -> `with pytest.raises(ValueError) as exc:` around the call, then `assert str(exc.value) == f"Account {a9.id} not found"`. Only the type asked -> no `as exc`, no text assert. `TypeError`: the same.
- OPEN_INVOICES text -> `assert str(exc.value) == OPEN_INVOICES` (never type the dash). "Not OPEN_INVOICES" -> `!= OPEN_INVOICES`. "Starts with" -> `assert str(exc.value).startswith(f"Account {a9.id} ")`.
- target `schema` -> no M call. Raises: `with pytest.raises(ValidationError):` + `AccountCreate(name="")` inside. Returns: `obj = AccountUpdate(...)`, `assert isinstance(obj, AccountUpdate)`, `assert obj.primary_email == "..."`.
- target `database` -> no M call. `raises: IntegrityError on flush` -> as ACC-A-14 below; for an account put `mk_account(...)` inside. "Flush raises no error" -> `row = mk_account(...)`, `assert row.id is not None`.
- `re-read A1:` -> `row = reread(db, a1)`, then one `assert` per value (`assert row.is_active is False`).
- each of the 13 optional fields -> `for f in OPTIONAL_FIELDS:` + `assert getattr(row, f) == FILLED[f]` (or `is None`). "All except `city`" -> add `if f != "city":`.
- A "looser" check -> the card's expression as given: `assert (row.account_code or "").strip() == ""`.
- `count:` rows -> `assert count_rows(db, Account) == 1` (`AccountInvoice` the same).
- re-read assignment rows -> `for x in links(db, a1):` + asserts; one row -> `x = link_row(db, a1, t1)`.
- `unchanged(A1)` (also X1, A9, I1; one `before_…` per row) -> `before_a1 = snap(db, a1)` before the call, `assert snap(db, a1) == before_a1` after. Values after the dash ("in particular …", "same `id`, …") -> ALSO `row = reread(db, a1)` + one assert per value; X1: `row_x1 = link_row(db, a1, t1)`, `assert row_x1.id == x1.id`.
- `nothing written:` -> `before = written(db)` before the call; after: `assert written(db) == before`, then EVERY number the line lists (see ACC-U-01); a tag's count (also `re-read T1:`): `assert reread(db, t1).usage_count == 1`.
- `audit:` -> `logs = audit(db, a1)`, `assert len(logs) == 1`, `log = logs[0]`, then `assert log.action_type == "updated"`, `log.changes["after"]["city"] == "Dhaka"`. "`financial_audit_logs` has exactly N rows" -> first `assert count_rows(db, FinancialAuditLog) == N`.
- standard audit fields -> five asserts: `log.entity_type == "account"`, `log.entity_id == a1.id`, `log.workspace_id == w1.id`, `log.related_entity_type is None`, `log.related_entity_id is None`.
- `changes` has / has not a key -> `"after" in log.changes`, `"before" not in log.changes`.
- lists -> set: `assert {a.name for a in result} == {"Alpha"}`; in order: `[a.name for a in result] == ["Bravo", "Charlie"]`.
- "both are in {…}" -> `for a in result:` + `assert a.name in {"Alpha", "Bravo"}`. "All different" -> `assert len({a.id for a in result}) == len(result)`.
- A call with a not yet existing parameter (`ip_address`, …) -> exactly as shown, never inside `pytest.raises`.

## Example tests
```python
def test_acc_u_01__unknown_account_id_rejected(db, M, w1, u2, mk_account):
    """ACC-U-01 — updating an unknown account id raises and writes nothing.
    Rules: update_account R1; Errors row 1"""
    a1 = mk_account()
    before_a1 = snap(db, a1)
    before = written(db)

    # Then 1
    with pytest.raises(ValueError) as exc:
        M.update_account(db, account_id=MISSING, account_data=AccountUpdate(name="New Name"),
                         workspace_id=w1.id, user_id=u2.id)

    assert str(exc.value) == "Account 999999999 not found"
    # Then 2
    assert written(db) == before
    assert count_rows(db, Account) == 1
    assert count_rows(db, AccountTagAssignment) == 0
    assert count_rows(db, FinancialAuditLog) == 0
    # Then 3
    assert snap(db, a1) == before_a1


def test_acc_u_28__tag_list_replaces_tags(db, M, w1, u2, mk_account, mk_tag, mk_link):
    """ACC-U-28 — a tag list replaces the account's tags and adjusts usage counts.
    Rules: update_account R11, R12"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    t2 = mk_tag("Client", "client", usage_count=0)
    t4 = mk_tag("Utility", "utility", usage_count=5)
    mk_link(a1, t1)

    result = M.update_account(db, account_id=a1.id, account_data=AccountUpdate(tag_ids=[t2.id, t4.id]),
                              workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id == a1.id
    # Then 2
    assert tags(db, a1) == [t2.id, t4.id]
    # Then 3
    for x in links(db, a1):
        assert x.workspace_id == w1.id
        assert x.assigned_by == u2.id
        assert x.assigned_at is not None
    # Then 4
    assert reread(db, t1).usage_count == 0
    # Then 5
    assert reread(db, t2).usage_count == 1
    # Then 6
    assert reread(db, t4).usage_count == 6


def test_acc_c_17__audit_full_snapshot(db, M, w1, u2, mk_tag):
    """ACC-C-17 — the audit row holds the full snapshot including tag ids.
    Rules: create_account R9 [BUG-872]"""
    t1 = mk_tag("Supplier", "supplier", usage_count=0)
    t2 = mk_tag("Client", "client", usage_count=0)

    result = M.create_account(
        db, account_data=AccountCreate(name="Acme Ltd", **FILLED, allow_invoices=False, tag_ids=[t2.id, t1.id]),
        workspace_id=w1.id, user_id=u2.id)

    # Then 1
    assert result.id is not None
    # Then 2
    logs = audit(db, result)
    assert len(logs) == 1
    # Then 3
    assert logs[0].changes == {"after": SNAP(**FILLED, allow_invoices=False, tag_ids=[t1.id, t2.id])}


def test_acc_a_14__db_forbids_second_assignment(db, u2, mk_account, mk_tag, mk_link):
    """ACC-A-14 — a second assignment of the same tag fails on flush.
    Rules: assign_tag R10"""
    a1 = mk_account()
    t1 = mk_tag("Supplier", "supplier", usage_count=1)
    mk_link(a1, t1)

    # Then 1
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            mk_link(a1, t1, assigned_by=u2.id, assigned_at=NOW)

    # Then 2
    assert tags(db, a1) == [t1.id]
```
