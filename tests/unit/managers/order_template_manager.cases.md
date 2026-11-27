# Test cases — `app/managers/order_template_manager.py`

> **Spec:** `tests/unit/managers/order_template_manager.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-06; revised 2026-11-07: OQ-22 answered by the owner → BUG-2347; cases gaps 1–9 closed, new BUG-2349).
> **Revision:** 2 (2026-11-07) — spec revision 2026-11-07. OQ-22 answered: section Q22 now tests BUG-2347 (only the owner may skip approval). Q22-01, Q22-02, Q22-04 and Q22-05 become strict xfail BUG-2347; Q22-03 and Q22-06 stay pass. New in Q22: Q22-07 … Q22-18 (owner through `owner_user_id`, a suspended owner row, owner grants held in W0 or W2, the defaults, the stored value re-sent, other fields on a template that already skips approval). Gap answers: G3 → OTMG-DT-06 builds the minimal `ExpenseOrder` and loses `Author: claude`; G4 → CT-60, CT-61, UT-37 (`recurrence_type` over 50); G5 → BUG-2349: CT-57, CT-58, CT-59, UI-24, UI-25, UI-26, and CT-52 now pairs 13 integer digits with a price of 1.00, so its total stays valid; G6 → UT-38, UT-39; G7 → UT-40, UT-41; G8 → CT-62 … CT-65, UT-42 … UT-46. G1, G2, G9: facts confirm the cards as written; no card changed. The two "pending OQ-22" notes at the top of the create and update sections are rewritten. No ID retired.
> **Revision:** 3 (2026-11-09) — from `order_template_manager.verify.md` Finding 1 (case-missing, `update_item` R4a, BUG-2349): every overflow card sent a new price, so a total check run only when `unit_price` is sent passed. New: OTMG-UI-27 (only `quantity=10000` sent onto a stored price 1 000 000 000.00 → 422 `LTL`, strict xfail BUG-2349) and its just-below pair OTMG-UI-28 (only `quantity=1.01` sent onto a stored price 9900990099009.89 → subtotal 9999999999999.99, pass). No card changed or retired.
> **Counts:** 205 cases · 111 expected-to-pass · 94 expected-to-fail (bugs) · 4 deferred

## Reviewer summary
- **Per callable:** `create_template` 65 (41 bug) · `update_template` 46 (29 bug) · `get_template` 6 · `list_templates` 8 · `delete_template` 7 · `add_item` 15 · `update_item` 28 (10 bug) · `remove_item` 5 · `get_items` 7 (3 bug) · Q22 (R9, BUG-2347) 18 (11 bug).
- **Expected-to-fail by bug:** BUG-1216 17 · BUG-2347 13 · BUG-1014 7 · BUG-2361 7 · BUG-2355 5 · BUG-2357 5 · BUG-2363 5 · BUG-2364 5 · BUG-2365 5 · BUG-2349 5 · BUG-2359 4 · BUG-2362 4 · BUG-2358 3 · BUG-2360 3 · BUG-2366 3 · BUG-2356 2 · BUG-1226 1. All strict. Schema bugs (BUG-2355, 2357/2358 null parts, 2359, 2363, 2364, 2365) build the schema, as the spec asks.
- **Depth:** full (skill step 1a): line money. Subtotals are checked at a product ending in exactly 5 (0.50 × 0.25 = 0.125 → 0.13, which half-to-even would make 0.12), just below (0.123 → 0.12) and just above (0.126 → 0.13), on create, add and update; the spec's 1.50 × 0.25 → 0.38; price empty → 0.00 with the price kept empty; price 0; quantity default 1; 13 integer digits stored exactly. Update recomputes from sent-or-stored values: quantity only, price only, both, neither (a stored subtotal that disagrees stays, so a recompute is caught), a stored empty price. Line numbering: max + 1, not count + 1 (lines 2, 3, 4 → 5), not newest + 1 (built 3 then 1 → 4), another template's line 9 ignored. There is no recurring-run scheduling here (Q11: recurrence fields are only stored), so CT-03 / UT-08 store odd values unchecked.
- **Workspaces:** every by-id refusal is tested with a W0 row (lower id) and a W2 row (higher id), one per card; every reference refusal likewise for accounts, factories and departments. Grants held elsewhere: the approver UX is an active owner of W2 only; UZ is a member of nothing; a suspended W1 member. CT-37 / CT-38 give a department and a factory explicit ids (880000001, 880000002) so "a department id sent as a factory" cannot hit a real factory.
- **Refusals** check the session (`not db.new` / `not db.dirty` / `not db.deleted`) before any re-read, then nothing written or `unchanged`. Each writer has one commit-spy card (CT-55, UT-35, DT-07, AI-15, UI-23, RI-05). No refresh rule exists here.
- **BUG-2347 (OQ-22, owner 2026-11-07)** lives in section Q22. The owner is built both ways: through an active `owner` member row (UO) and through `workspaces.owner_user_id` (Q22-07, Q22-18). Callers refused with 403: a ground-team member, a suspended `owner` row, and grants held elsewhere (a W1 manager who owns W2 by member row, owns W0 by member row, or is W2's `owner_user_id`). Passing today and after the fix: the owner's own create and switch, the defaults sent by anyone, the stored value re-sent, and other fields changed on a template that already skips approval. Outside Q22, only the order-of-refusal cards CT-62, UT-42 and UT-43 send a flag.
- **Line totals (BUG-2349):** the spec's example 10 000 × 1 000 000 000 is refused. So is 1.01 × 9900990099009.90 = 9999999999999.999, which rounds half up to 10^13. Just below, 1.01 × 9900990099009.89 = 9999999999999.9889 → 9999999999999.99, is stored, on create and on update. On update the totals are reached both by a new price (UI-24 … UI-26) and by a new quantity onto the stored price (UI-27, UI-28).
- **Order of refusals (R11):** each card carries two or more bad inputs and expects only the first refusal.
- **Notable design choices:** no `Author: claude` card is left (DT-06 now builds the spec's minimal `ExpenseOrder`). Negative-number rounding (HR-15 −0.125 → −0.13) gets no card (spec Notes, G9). A null `cost_center_id` on a factory or department template gets BUG-2361's 400 (UT-38, UT-39). A cost centre of the wrong kind left by a category change gets 404 (UT-40, UT-41, explicit ids 880000001 / 880000002).
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `OTMG` = `app/managers/order_template_manager.py`. `CT` create_template · `UT` update_template · `GT` get_template · `LT` list_templates · `DT` delete_template · `AI` add_item · `UI` update_item · `RI` remove_item · `GI` get_items. `Q22` = `create_template` R9, `update_template` R9 (BUG-2347, OQ-22 answered 2026-11-07); the section keeps its IDs.

**Actors and fixed values.**
- `M` = the singleton `order_template_manager` (`from app.managers.order_template_manager import order_template_manager`). `db` = the test's real session, always the first positional argument; every other argument is passed by keyword. `result` = what the When call returns. The session does not autoflush.
- Classes: `OrderTemplate` (`app.models.order_template`), `OrderTemplateItem` (`app.models.order_template_item`), `Account` (`app.models.account`), `Factory` (`app.models.factory`), `Department` (`app.models.department`), `WorkspaceMember` (`app.models.workspace_member`), `ExpenseOrder` (`app.models.expense_order`). `OrderTemplateCreate`, `OrderTemplateUpdate`, `OrderTemplateItemCreate`, `OrderTemplateItemUpdate` = `app.schemas.order_template`. `make_workspace`, `make_profile` = `tests/unit/factories.py`. `HTTPException` = `fastapi.HTTPException`. `ValidationError` = `pydantic.ValidationError`. `Decimal` = `decimal.Decimal`. `date`, `datetime` = the `datetime` module's classes. `patch` = `unittest.mock.patch`. `select`, `func` = `sqlalchemy`.
- MISSING = `999999999`. T0 = `datetime(2026, 3, 1, 9, 0, 0)`, T1 = `datetime(2026, 3, 2, 9, 0, 0)`, T2 = `datetime(2026, 3, 3, 9, 0, 0)`, T3 = `datetime(2026, 3, 4, 9, 0, 0)`.
- N255 = `"R" * 255`, N256 = `"R" * 256`. U50 = `"k" * 50`, U51 = `"k" * 51`. R50 = `"w" * 50`, R51 = `"w" * 51`.
- FORBID = `"Only the workspace owner can skip approval on a template"`. LTL = `"Line total is too large"`.

**Externals.** None. Nothing is mocked, except the commit spy of **rolled back**. `created_at` of a new row comes from the real clock and is only checked `is not None`.

**Standing rows.** In every test, built in this order, no Given line:
1. W0 = `make_workspace(db)`, then W1, then W2 the same. So `W0.id < W1.id < W2.id`.
2. UO = `make_profile(db, name="Olive")`, then UA (`"Ann"`), UG (`"Gus"`), UX (`"Xia"`), UZ (`"Zed"`), in that order.
3. Memberships, `WorkspaceMember(workspace_id=…, user_id=…, role=…, status="active")`: (W1, UO, `"owner"`), (W1, UA, `"manager"`), (W1, UG, `"ground-team"`), (W2, UX, `"owner"`). UZ is a member of nothing; UX of W2 only.
No template, line, account, factory or department exists unless the card's Given lists it. Profiles are built after the workspaces, so no standing profile is any workspace's `owner_user_id` unless a Given line sets it. The owner of W1 is UO, through its member row.

**Given rows.** Inserted directly (never through `M`) and flushed one at a time in the order written, so ids within one table rise in that order. After the word "but" a line lists every column that differs. A line written as code is a step to run exactly as written, at that place.
- **template** = `OrderTemplate(workspace_id=W1.id, template_name="Rent", requires_approval=True, auto_approve=False, created_by=UO.id, created_at=T0)`. **inactive** = also `is_active False`, `updated_by UO.id`, `updated_at T1` (what a real delete leaves).
- **line n on T** = `OrderTemplateItem(workspace_id=W1.id, order_template_id=T.id, line_number=n, description="Line", quantity=Decimal("3.00"), unit_price=Decimal("10.00"), line_subtotal=Decimal("30.00"))`.
- **account** = `Account(workspace_id=W1.id, name="Acme", is_active=True, is_deleted=False)`. **closed** = also `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by UO.id`.
- **factory** = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`. **department** = `Department(workspace_id=W1.id, name="Sales")`. **deleted** (factory or department) = also `is_deleted True`, `deleted_at T0`, `deleted_by UO.id`.
- **ITEM** = `OrderTemplateItemCreate(description="Bolt", quantity=Decimal("2.00"), unit_price=Decimal("5.00"))`.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. "the new template" = the `order_templates` row with `id == result.id`.
- **lines(T)** = `db.expire_all()`, then the `OrderTemplateItem` rows with `order_template_id == T.id`, ordered by `line_number`, then `id`, as a list.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot after the last Given line). **unchanged(X) except `c`** = the same, leaving out the columns named.
- **nothing written** = the numbers of `order_templates` and `order_template_items` rows (all workspaces) equal their values before the call.
- `raises: HTTPException` = plain `with pytest.raises(HTTPException) as exc:` around the call, **no** savepoint; further `raises:` lines assert on `exc.value` after the block.
- `raises: ValidationError` (target `schema`) = `pytest.raises` around building the schema object only; `M` is not called.
- `session:` lines check `db.new`, `db.dirty`, `db.deleted` directly after the call (or the `with` block), before any re-read or `expire_all`.
- **rolled back** = `sp = db.begin_nested()` directly before the call and `with patch.object(db, "commit", wraps=db.commit) as cm:` around it; lines marked "(inside)" run first, then `sp.rollback()`, then the lines marked "(after)".
- **pending P** = `P = OrderTemplate(workspace_id=W1.id, template_name="Pending", requires_approval=True, auto_approve=False, created_by=UO.id, created_at=T3)`, `db.add(P)`, not flushed. `pending:` lines check P after the call.

**Money.** Every money check compares `Decimal` values read back from the database with `==` (`Decimal("0.13") == Decimal("0.130")` holds). Rounding is the column's: half away from zero (HR-15). Cards that tell half-up from half-to-even use a product ending in exactly 5 at the third decimal.

**xfail cards.** Write the call and the checks exactly as shown, also when the call raises today. `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`. Every xfail card here is strict.

**Race simulations.** None in this module.

## `OrderTemplateManager.create_template`

> R9 (BUG-2347) has its own section, Q22. In this section only CT-62 sends `requires_approval=False`, to test the order of refusals (R11).

### OTMG-CT-01 — create stores every field sent, with the caller as creator, flushed
- **Rules:** `create_template` R1, R6 (valid references), Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. AC = account.
2. F = factory.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Office rent", description="Monthly", account_id=AC.id, expense_category="factory", cost_center_id=F.id, default_approver_id=UA.id, notes="Pay by the 5th"), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `isinstance(result, OrderTemplate)`.
2. returns: `result.id is not None`.
3. re-read the new template: `template_name == "Office rent"`, `description == "Monthly"`, `notes == "Pay by the 5th"`.
4. re-read the new template: `account_id == AC.id`, `expense_category == "factory"`, `cost_center_id == F.id`, `default_approver_id == UA.id`.
5. re-read the new template: `workspace_id == W1.id`, `created_by == UO.id`.
6. re-read the new template: `created_at is not None`.

### OTMG-CT-02 — fields not sent take the defaults; nothing is stamped as updated
- **Rules:** `create_template` R1, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent"), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `is_active is True`, `updated_by is None`, `updated_at is None`.
3. re-read the new template: `next_generation_date is None`, `last_generated_date is None`.
4. re-read the new template: `requires_approval is True`, `auto_approve is False`.
5. re-read the new template: `is_recurring is False`, `generate_days_before == 0`.
6. re-read the new template: `account_id is None`, `expense_category is None`, `cost_center_id is None`, `default_approver_id is None`.
7. re-read the new template: `description is None`, `notes is None`, `created_by == UA.id`.

### OTMG-CT-03 — recurrence fields are stored as sent, unchecked
- **Rules:** `create_template` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", is_recurring=True, recurrence_type="every odd moon", recurrence_interval=0, recurrence_day=31, start_date=date(2026, 5, 1), end_date=date(2026, 4, 1), generate_days_before=-3), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `is_recurring is True`, `recurrence_type == "every odd moon"`, `recurrence_interval == 0`, `recurrence_day == 31`.
3. re-read the new template: `start_date == date(2026, 5, 1)`, `end_date == date(2026, 4, 1)`.
4. re-read the new template: `generate_days_before == -3`.
5. re-read the new template: `next_generation_date is None`, `last_generated_date is None`.

### OTMG-CT-04 — items=[] creates no line
- **Rules:** `create_template` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `order_template_items` with `order_template_id == result.id` has exactly 0 rows.

### OTMG-CT-05 — items=None creates no line
- **Rules:** `create_template` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=None), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `order_template_items` with `order_template_id == result.id` has exactly 0 rows.

### OTMG-CT-06 — lines are numbered 1, 2, 3 in the order given, each with its own product
- **Rules:** `create_template` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[OrderTemplateItemCreate(description="Zinc", unit="kg", quantity=Decimal("2.00"), unit_price=Decimal("3.00"), notes="z"), OrderTemplateItemCreate(description="Bolt", quantity=Decimal("4.00"), unit_price=Decimal("1.50")), OrderTemplateItemCreate(description="Mesh", quantity=Decimal("1.00"), unit_price=Decimal("7.25"))]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: lines(the new template) has exactly 3 rows.
3. re-read lines(the new template): `[l.description for l in lines] == ["Zinc", "Bolt", "Mesh"]`.
4. re-read lines(the new template): `[l.line_number for l in lines] == [1, 2, 3]`.
5. re-read lines(the new template): `[l.line_subtotal for l in lines] == [Decimal("6.00"), Decimal("6.00"), Decimal("7.25")]`.
6. re-read lines(the new template): every line has `workspace_id == W1.id` and `order_template_id == result.id`.
7. re-read lines(the new template): first line `unit == "kg"`, `notes == "z"`, `quantity == Decimal("2.00")`, `unit_price == Decimal("3.00")`.

### OTMG-CT-07 — a product ending in 5 rounds half up: 0.50 × 0.25 = 0.125 gives 0.13
- **Rules:** `create_template` R8 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[OrderTemplateItemCreate(description="Washer", quantity=Decimal("0.50"), unit_price=Decimal("0.25"))]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read lines(the new template): exactly 1 line, `line_subtotal == Decimal("0.13")` (half to even would give 0.12).
3. re-read lines(the new template): `quantity == Decimal("0.50")`, `unit_price == Decimal("0.25")`.

### OTMG-CT-08 — products just below and just above the half: 0.123 gives 0.12, 0.126 gives 0.13
- **Rules:** `create_template` R8 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[OrderTemplateItemCreate(description="Low", quantity=Decimal("0.30"), unit_price=Decimal("0.41")), OrderTemplateItemCreate(description="High", quantity=Decimal("0.30"), unit_price=Decimal("0.42"))]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read lines(the new template): line 1 `line_subtotal == Decimal("0.12")`.
3. re-read lines(the new template): line 2 `line_subtotal == Decimal("0.13")`.

### OTMG-CT-09 — 1.50 × 0.25 = 0.375 gives 0.38
- **Rules:** `create_template` R8 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[OrderTemplateItemCreate(description="Tape", quantity=Decimal("1.50"), unit_price=Decimal("0.25"))]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read lines(the new template): exactly 1 line, `line_subtotal == Decimal("0.38")`.

### OTMG-CT-10 — a line with no price has subtotal 0.00 and keeps its price empty
- **Rules:** `create_template` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[OrderTemplateItemCreate(description="Labour", quantity=Decimal("4.00"))]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read lines(the new template): exactly 1 line, `unit_price is None`.
3. re-read lines(the new template): that line `line_subtotal == Decimal("0.00")`.

### OTMG-CT-11 — a price of 0 gives subtotal 0.00 and is stored as 0.00
- **Rules:** `create_template` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[OrderTemplateItemCreate(description="Free", quantity=Decimal("4.00"), unit_price=Decimal("0"))]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read lines(the new template): exactly 1 line, `unit_price == Decimal("0.00")`, `line_subtotal == Decimal("0.00")`.

### OTMG-CT-12 — quantity not sent is 1, so the subtotal is the price
- **Rules:** `create_template` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[OrderTemplateItemCreate(description="Fee", unit_price=Decimal("12.50"))]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read lines(the new template): exactly 1 line, `quantity == Decimal("1.00")`, `line_subtotal == Decimal("12.50")`.

### OTMG-CT-13 — 13 integer digits and 2 decimals are stored exactly
- **Rules:** `create_template` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[OrderTemplateItemCreate(description="Big", quantity=Decimal("9999999999999.99"), unit_price=Decimal("1.00"))]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read lines(the new template): exactly 1 line, `quantity == Decimal("9999999999999.99")`, `line_subtotal == Decimal("9999999999999.99")`.

### OTMG-CT-14 — a 255-character name is stored
- **Rules:** `create_template` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name=N255), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `template_name == N255`.

### OTMG-CT-15 — a name without spaces around it is stored as typed, inner space and case kept
- **Rules:** `create_template` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Office  RENT"), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `template_name == "Office  RENT"`.

### OTMG-CT-16 — a name with spaces around it is stored trimmed
- **Rules:** `create_template` R3 [BUG-2355]
- **Kind:** bug
- **Expect:** xfail BUG-2355
- **Fails today on:** Then 2 (stored as typed, `"  Rent "`)

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="  Rent "), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `template_name == "Rent"`.

### OTMG-CT-17 — a whitespace-only name is refused by the schema
- **Rules:** `create_template` R3 [BUG-2355]
- **Kind:** bug
- **Expect:** xfail BUG-2355
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. No template exists.

**When**
- build `OrderTemplateCreate(template_name="  ")` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-CT-18 — an empty name is refused by the schema
- **Rules:** `create_template` R3 [BUG-2355]
- **Kind:** bug
- **Expect:** xfail BUG-2355
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. No template exists.

**When**
- build `OrderTemplateCreate(template_name="")` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-CT-19 — a 256-character name is refused by the schema
- **Rules:** `create_template` R3 [BUG-2365]
- **Kind:** bug
- **Expect:** xfail BUG-2365
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. No template exists.

**When**
- build `OrderTemplateCreate(template_name=N256)` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-CT-20 — an unknown category is refused by the schema
- **Rules:** `create_template` R4 [BUG-2359]
- **Kind:** bug
- **Expect:** xfail BUG-2359
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. No template exists.

**When**
- build `OrderTemplateCreate(template_name="Rent", expense_category="garbage")` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-CT-21 — a category with spaces and capitals is stored trimmed and lower-cased
- **Rules:** `create_template` R4 [BUG-2359]
- **Kind:** bug
- **Expect:** xfail BUG-2359
- **Fails today on:** Then 2 (stored as typed, `" Factory "`)

**Given**
1. F = factory.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category=" Factory ", cost_center_id=F.id), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `expense_category == "factory"`.

### OTMG-CT-22 — category department with a live department of the workspace is stored
- **Rules:** `create_template` R4, R5, R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. D = department.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="department", cost_center_id=D.id), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `expense_category == "department"`, `cost_center_id == D.id`.

### OTMG-CT-23 — category other drops the cost centre
- **Rules:** `create_template` R5 [BUG-2360]
- **Kind:** bug
- **Expect:** xfail BUG-2360
- **Fails today on:** Then 3 (`cost_center_id` stored as sent)

**Given**
1. F = factory.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="other", cost_center_id=F.id), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `expense_category == "other"`.
3. re-read the new template: `cost_center_id is None`.

### OTMG-CT-24 — no category drops the cost centre
- **Rules:** `create_template` R5 [BUG-2360]
- **Kind:** bug
- **Expect:** xfail BUG-2360
- **Fails today on:** Then 2 (`cost_center_id` stored as sent)

**Given**
1. F = factory.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", cost_center_id=F.id), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `cost_center_id is None`.

### OTMG-CT-25 — category factory without a cost centre is refused, nothing written
- **Rules:** `create_template` R5 [BUG-2361], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-2361
- **Fails today on:** Then 1 (no error is raised; the template is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="factory", items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`, `exc.value.detail == "Select a factory for this template"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-26 — category department without a cost centre is refused, nothing written
- **Rules:** `create_template` R5 [BUG-2361], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-2361
- **Fails today on:** Then 1 (no error is raised; the template is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="department", items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`, `exc.value.detail == "Select a department for this template"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-27 — an account of a later workspace (W2) is refused
- **Rules:** `create_template` R6 [BUG-1014], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1014
- **Fails today on:** Then 1 (no error is raised; the account is stored)

**Given**
1. AC2 = account, but `workspace_id W2.id`, `name "Far"`.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", account_id=AC2.id, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Account with ID {AC2.id} not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-28 — an account of an earlier workspace (W0) is refused
- **Rules:** `create_template` R6 [BUG-1014]
- **Kind:** bug
- **Expect:** xfail BUG-1014
- **Fails today on:** Then 1 (no error is raised; the account is stored)

**Given**
1. AC0 = account, but `workspace_id W0.id`, `name "Old"`.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", account_id=AC0.id, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Account with ID {AC0.id} not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-29 — a closed account of the workspace is refused
- **Rules:** `create_template` R6 [BUG-2362]
- **Kind:** bug
- **Expect:** xfail BUG-2362
- **Fails today on:** Then 1 (no error is raised; the account is stored)

**Given**
1. AC = account, closed.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", account_id=AC.id, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Account with ID {AC.id} not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-30 — an unknown account is refused as not found
- **Rules:** `create_template` R6 [BUG-1014], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1014
- **Fails today on:** Then 1 (the call raises IntegrityError at flush, not HTTPException)

**Given**
1. No account exists.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", account_id=MISSING), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Account with ID 999999999 not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-31 — a factory of a later workspace (W2) is refused
- **Rules:** `create_template` R6 [BUG-1216]
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (no error is raised; the id is stored)

**Given**
1. F2 = factory, but `workspace_id W2.id`, `name "Factory Nine"`, `abbreviation "F9"`.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="factory", cost_center_id=F2.id, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Factory with ID {F2.id} not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-32 — a factory of an earlier workspace (W0) is refused
- **Rules:** `create_template` R6 [BUG-1216]
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (no error is raised; the id is stored)

**Given**
1. F0 = factory, but `workspace_id W0.id`, `name "Factory Zero"`, `abbreviation "F0"`.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="factory", cost_center_id=F0.id, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Factory with ID {F0.id} not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-33 — a deleted factory of the workspace is refused
- **Rules:** `create_template` R6 [BUG-2362]
- **Kind:** bug
- **Expect:** xfail BUG-2362
- **Fails today on:** Then 1 (no error is raised; the id is stored)

**Given**
1. F = factory, deleted.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="factory", cost_center_id=F.id, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Factory with ID {F.id} not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-34 — a department of a later workspace (W2) is refused
- **Rules:** `create_template` R6 [BUG-1216]
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (no error is raised; the id is stored)

**Given**
1. D2 = department, but `workspace_id W2.id`, `name "Far Sales"`.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="department", cost_center_id=D2.id, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Department with ID {D2.id} not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-35 — a department of an earlier workspace (W0) is refused
- **Rules:** `create_template` R6 [BUG-1216]
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (no error is raised; the id is stored)

**Given**
1. D0 = department, but `workspace_id W0.id`, `name "Old Sales"`.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="department", cost_center_id=D0.id, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Department with ID {D0.id} not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-36 — a deleted department of the workspace is refused
- **Rules:** `create_template` R6 [BUG-2362]
- **Kind:** bug
- **Expect:** xfail BUG-2362
- **Fails today on:** Then 1 (no error is raised; the id is stored)

**Given**
1. D = department, deleted.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="department", cost_center_id=D.id, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Department with ID {D.id} not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-37 — category factory with the id of a department of the workspace is refused as a factory
- **Rules:** `create_template` R6 [BUG-1216]
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (no error is raised; the id is stored)

**Given**
1. D = department, but `id 880000001` (set explicitly; no factory has this id).

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="factory", cost_center_id=880000001, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Factory with ID 880000001 not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-38 — category department with the id of a factory of the workspace is refused as a department
- **Rules:** `create_template` R6 [BUG-1216]
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (no error is raised; the id is stored)

**Given**
1. F = factory, but `id 880000002` (set explicitly; no department has this id).

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="department", cost_center_id=880000002, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Department with ID 880000002 not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-39 — an approver who belongs to no workspace is refused
- **Rules:** `create_template` R6 [BUG-1216]
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (no error is raised; the approver is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", default_approver_id=UZ.id, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Profile with ID {UZ.id} not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-40 — an approver who is an active owner of another workspace only is refused
- **Rules:** `create_template` R6 [BUG-1216]
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (no error is raised; the approver is stored)

**Given**
1. No template exists (UX is an active owner of W2, not a member of W1).

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", default_approver_id=UX.id, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Profile with ID {UX.id} not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-41 — an approver whose membership of the workspace is not active is refused
- **Rules:** `create_template` R6 [BUG-1216]
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (no error is raised; the approver is stored)

**Given**
1. `WorkspaceMember(workspace_id=W1.id, user_id=UZ.id, role="manager", status="suspended")`.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", default_approver_id=UZ.id, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Profile with ID {UZ.id} not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-42 — an unknown approver is refused as not found
- **Rules:** `create_template` R6 [BUG-1216], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (the call raises IntegrityError at flush, not HTTPException)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", default_approver_id=MISSING), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Profile with ID 999999999 not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-43 — a ground-team member of the workspace is accepted as approver
- **Rules:** `create_template` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", default_approver_id=UG.id), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `default_approver_id == UG.id`.

### OTMG-CT-44 — line schema: more than 2 decimals in quantity is refused
- **Rules:** `create_template` R8 [BUG-2363]; `add_item` R4
- **Kind:** bug
- **Expect:** xfail BUG-2363
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateItemCreate(description="Bolt", quantity=Decimal("1.005"), unit_price=Decimal("10.00"))` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-CT-45 — line schema: more than 2 decimals in unit_price is refused
- **Rules:** `create_template` R8 [BUG-2363]; `add_item` R4
- **Kind:** bug
- **Expect:** xfail BUG-2363
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateItemCreate(description="Bolt", quantity=Decimal("3"), unit_price=Decimal("0.125"))` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-CT-46 — line schema: 14 integer digits in quantity are refused
- **Rules:** `create_template` R8 [BUG-2363]; `add_item` R4
- **Kind:** bug
- **Expect:** xfail BUG-2363
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateItemCreate(description="Bolt", quantity=Decimal("10000000000000"), unit_price=Decimal("1.00"))` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-CT-47 — line schema: 14 integer digits in unit_price are refused
- **Rules:** `create_template` R8 [BUG-2363]; `add_item` R4
- **Kind:** bug
- **Expect:** xfail BUG-2363
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateItemCreate(description="Bolt", quantity=Decimal("1"), unit_price=Decimal("10000000000000"))` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-CT-48 — line schema: quantity 0 is refused
- **Rules:** `create_template` R8 [BUG-2364]; `add_item` R4
- **Kind:** bug
- **Expect:** xfail BUG-2364
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateItemCreate(description="Bolt", quantity=Decimal("0"), unit_price=Decimal("1.00"))` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-CT-49 — line schema: a negative quantity is refused
- **Rules:** `create_template` R8 [BUG-2364]; `add_item` R4
- **Kind:** bug
- **Expect:** xfail BUG-2364
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateItemCreate(description="Refund", quantity=Decimal("-2"), unit_price=Decimal("3.00"))` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-CT-50 — line schema: a price of -0.01 is refused
- **Rules:** `create_template` R8 [BUG-2364]; `add_item` R4
- **Kind:** bug
- **Expect:** xfail BUG-2364
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateItemCreate(description="Refund", quantity=Decimal("1"), unit_price=Decimal("-0.01"))` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-CT-51 — line schema: quantity 0.01 and price 0 are accepted
- **Rules:** `create_template` R8; `add_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = OrderTemplateItemCreate(description="Bolt", quantity=Decimal("0.01"), unit_price=Decimal("0"))` (target `schema`).

**Then**
1. returns: `result.quantity == Decimal("0.01")`, `result.unit_price == Decimal("0")`.

### OTMG-CT-52 — line schema: 13 integer digits with 2 decimals are accepted
- **Rules:** `create_template` R8; `add_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = OrderTemplateItemCreate(description="Big", quantity=Decimal("9999999999999.99"), unit_price=Decimal("1.00"))` (target `schema`).

**Then**
1. returns: `result.quantity == Decimal("9999999999999.99")`, `result.unit_price == Decimal("1.00")`.

### OTMG-CT-53 — line schema: a unit of 51 characters is refused
- **Rules:** `create_template` R8 [BUG-2365]; `add_item` R4
- **Kind:** bug
- **Expect:** xfail BUG-2365
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateItemCreate(description="Bolt", unit=U51)` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-CT-54 — a unit of 50 characters is stored
- **Rules:** `create_template` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[OrderTemplateItemCreate(description="Bolt", unit=U50, quantity=Decimal("1.00"), unit_price=Decimal("2.00"))]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read lines(the new template): exactly 1 line, `unit == U50`.

### OTMG-CT-55 — create flushes and never commits
- **Rules:** `create_template` Returns, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Spy", items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`, rolled back.

**Then**
1. returns: `result.id is not None` (inside).
2. count: `order_templates` with `template_name == "Spy"` has exactly 1 row (inside).
3. count: `order_template_items` with `order_template_id == result.id` has exactly 1 row (inside).
4. mock called: `cm.call_count == 0`.
5. count: `order_templates` with `template_name == "Spy"` has exactly 0 rows (after).

### OTMG-CT-56 — category other without a cost centre is stored
- **Rules:** `create_template` R4, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="other"), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `expense_category == "other"`, `cost_center_id is None`.

### OTMG-CT-57 — line schema: a line total of 10^13 is refused, though each input is valid
- **Rules:** `create_template` R8a [BUG-2349]; `add_item` R4
- **Kind:** bug
- **Expect:** xfail BUG-2349
- **Fails today on:** Then 1 (no error is raised: the schema has no check on the total)

**Given**
1. Nothing.

**When**
- build `OrderTemplateItemCreate(description="Big", quantity=Decimal("10000"), unit_price=Decimal("1000000000"))` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-CT-58 — line schema: a total that rounds half up to 10^13 is refused (1.01 × 9900990099009.90 = 9999999999999.999)
- **Rules:** `create_template` R8a [BUG-2349]; `add_item` R4
- **Kind:** bug
- **Expect:** xfail BUG-2349
- **Fails today on:** Then 1 (no error is raised: the schema has no check on the total)

**Given**
1. Nothing.

**When**
- build `OrderTemplateItemCreate(description="Big", quantity=Decimal("1.01"), unit_price=Decimal("9900990099009.90"))` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-CT-59 — a total just below 10^13 is stored, rounded half up (1.01 × 9900990099009.89 → 9999999999999.99)
- **Rules:** `create_template` R8, R8a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", items=[OrderTemplateItemCreate(description="Big", quantity=Decimal("1.01"), unit_price=Decimal("9900990099009.89"))]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read lines(the new template): exactly 1 line, `quantity == Decimal("1.01")`, `unit_price == Decimal("9900990099009.89")`, `line_subtotal == Decimal("9999999999999.99")`.

### OTMG-CT-60 — template schema: a recurrence_type of 51 characters is refused
- **Rules:** `create_template` R3 [BUG-2365]
- **Kind:** bug
- **Expect:** xfail BUG-2365
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateCreate(template_name="Rent", recurrence_type=R51)` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-CT-61 — a recurrence_type of 50 characters is stored
- **Rules:** `create_template` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Rent", recurrence_type=R50), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `recurrence_type == R50`.

### OTMG-CT-62 — order of refusals: a non-owner skipping approval gets 403 before the missing cost centre and the foreign account
- **Rules:** `create_template` R11, R9 [BUG-2347]
- **Kind:** bug
- **Expect:** xfail BUG-2347
- **Fails today on:** Then 1 (no error is raised; the template is stored)

**Given**
1. AC2 = account, but `workspace_id W2.id`, `name "Far"`.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", requires_approval=False, expense_category="factory", account_id=AC2.id, items=[ITEM]), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`, `exc.value.detail == FORBID`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-63 — order of refusals: the missing cost centre (400) comes before the foreign account (404)
- **Rules:** `create_template` R11, R5 [BUG-2361]
- **Kind:** bug
- **Expect:** xfail BUG-2361
- **Fails today on:** Then 1 (no error is raised; the template is stored)

**Given**
1. AC2 = account, but `workspace_id W2.id`, `name "Far"`.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="factory", account_id=AC2.id, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`, `exc.value.detail == "Select a factory for this template"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-64 — order of refusals: the account's 404 comes before the cost centre's and the approver's
- **Rules:** `create_template` R11, R6 [BUG-1014]
- **Kind:** bug
- **Expect:** xfail BUG-1014
- **Fails today on:** Then 1 (no error is raised; the template is stored)

**Given**
1. AC2 = account, but `workspace_id W2.id`, `name "Far"`.
2. D2 = department, but `workspace_id W2.id`, `name "Far"`.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="department", cost_center_id=D2.id, account_id=AC2.id, default_approver_id=UZ.id, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Account with ID {AC2.id} not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-CT-65 — order of refusals: the cost centre's 404 comes before the approver's
- **Rules:** `create_template` R11, R6 [BUG-1216]
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (no error is raised; the template is stored)

**Given**
1. D2 = department, but `workspace_id W2.id`, `name "Far"`.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Rent", expense_category="department", cost_center_id=D2.id, default_approver_id=UZ.id, items=[ITEM]), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Department with ID {D2.id} not found"`.
3. session: `not db.new`.
4. nothing written.

## `OrderTemplateManager.update_template`

> R9 (BUG-2347) has its own section, Q22. In this section only UT-42 and UT-43 send `requires_approval`, to test the order of refusals (R11).

### OTMG-UT-01 — fields sent are applied and the update is stamped
- **Rules:** `update_template` R2, R6, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but `description "Old"`, `notes "n0"`, `updated_by UO.id`, `updated_at T1`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(description="Monthly", notes="n1"), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `isinstance(result, OrderTemplate)`, `result.id == T.id`.
2. re-read T: `description == "Monthly"`, `notes == "n1"`.
3. re-read T: `updated_by == UA.id`.
4. re-read T: `updated_at is not None`, `updated_at != T1`.
5. re-read T: `template_name == "Rent"`, `created_by == UO.id`, `created_at == T0`.

### OTMG-UT-02 — fields not sent keep their values
- **Rules:** `update_template` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. AC = account.
2. F = factory.
3. T = template, but `description "Monthly"`, `account_id AC.id`, `expense_category "factory"`, `cost_center_id F.id`, `default_approver_id UA.id`, `notes "n0"`, `is_recurring True`, `recurrence_type "monthly"`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(template_name="Lease"), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `template_name == "Lease"`.
3. re-read T: `description == "Monthly"`, `notes == "n0"`.
4. re-read T: `account_id == AC.id`, `expense_category == "factory"`, `cost_center_id == F.id`, `default_approver_id == UA.id`.
5. re-read T: `is_recurring is True`, `recurrence_type == "monthly"`, `is_active is True`.
6. re-read T: `requires_approval is True`, `auto_approve is False`.

### OTMG-UT-03 — an unknown id is refused, nothing written
- **Rules:** `update_template` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=MISSING, data=OrderTemplateUpdate(template_name="Lease"), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Order template with ID 999999999 not found"`.
3. session: `not db.dirty`, `not db.new`.
4. unchanged: unchanged(T).
5. nothing written.

### OTMG-UT-04 — a template of an earlier workspace (W0) is refused, nothing written
- **Rules:** `update_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`.
2. T = template.

**When**
- `M.update_template(db, tpl_id=Z.id, data=OrderTemplateUpdate(template_name="Lease"), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Order template with ID {Z.id} not found"`.
3. session: `not db.dirty`, `not db.new`.
4. unchanged: unchanged(Z).
5. nothing written.

### OTMG-UT-05 — a template of a later workspace (W2) is refused, nothing written
- **Rules:** `update_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id`.

**When**
- `M.update_template(db, tpl_id=Z.id, data=OrderTemplateUpdate(template_name="Lease"), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Order template with ID {Z.id} not found"`.
3. session: `not db.dirty`, `not db.new`.
4. unchanged: unchanged(Z).
5. nothing written.

### OTMG-UT-06 — an inactive template can be updated and stays inactive
- **Rules:** `update_template` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, inactive.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(notes="still here"), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `notes == "still here"`, `is_active is False`.

### OTMG-UT-07 — is_active true switches an inactive template back on
- **Rules:** `update_template` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, inactive.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(is_active=True), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `is_active is True`, `updated_by == UA.id`.

### OTMG-UT-08 — recurrence fields and next_generation_date are applied unchecked
- **Rules:** `update_template` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(is_recurring=True, recurrence_type="whenever", recurrence_interval=-1, recurrence_day=0, start_date=date(2026, 6, 1), end_date=date(2026, 5, 1), next_generation_date=date(2025, 1, 1)), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `is_recurring is True`, `recurrence_type == "whenever"`, `recurrence_interval == -1`, `recurrence_day == 0`.
3. re-read T: `start_date == date(2026, 6, 1)`, `end_date == date(2026, 5, 1)`, `next_generation_date == date(2025, 1, 1)`.

### OTMG-UT-09 — a 255-character name is stored
- **Rules:** `update_template` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(template_name=N255), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `template_name == N255`.

### OTMG-UT-10 — a sent name with spaces around it is stored trimmed
- **Rules:** `update_template` R4 [BUG-2355]
- **Kind:** bug
- **Expect:** xfail BUG-2355
- **Fails today on:** Then 2 (stored as typed, `"  Lease "`)

**Given**
1. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(template_name="  Lease "), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `template_name == "Lease"`.

### OTMG-UT-11 — update schema: a whitespace-only name is refused
- **Rules:** `update_template` R4 [BUG-2355]
- **Kind:** bug
- **Expect:** xfail BUG-2355
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateUpdate(template_name="   ")` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-UT-12 — update schema: a 256-character name is refused
- **Rules:** `update_template` R4 [BUG-2365]
- **Kind:** bug
- **Expect:** xfail BUG-2365
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateUpdate(template_name=N256)` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-UT-13 — an explicit null clears the description
- **Rules:** `update_template` R5 [BUG-2357]
- **Kind:** bug
- **Expect:** xfail BUG-2357
- **Fails today on:** Then 2 (the null is ignored; `"d"` stays)

**Given**
1. T = template, but `description "d"`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(description=None), workspace_id=W1.id, user_id=UA.id)` (`description` is sent, as null).

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `description is None`.

### OTMG-UT-14 — an explicit null clears the default approver
- **Rules:** `update_template` R5 [BUG-2357]
- **Kind:** bug
- **Expect:** xfail BUG-2357
- **Fails today on:** Then 2 (the null is ignored; UA stays)

**Given**
1. T = template, but `default_approver_id UA.id`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(default_approver_id=None), workspace_id=W1.id, user_id=UO.id)` (sent, as null).

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `default_approver_id is None`.

### OTMG-UT-15 — an explicit null clears the account
- **Rules:** `update_template` R5 [BUG-2357]
- **Kind:** bug
- **Expect:** xfail BUG-2357
- **Fails today on:** Then 2 (the null is ignored; the account stays)

**Given**
1. AC = account.
2. T = template, but `account_id AC.id`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(account_id=None), workspace_id=W1.id, user_id=UO.id)` (sent, as null).

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `account_id is None`.

### OTMG-UT-16 — update schema: a null name is refused
- **Rules:** `update_template` R5 [BUG-2357]
- **Kind:** bug
- **Expect:** xfail BUG-2357
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateUpdate(template_name=None)` (target `schema`; the field is passed explicitly).

**Then**
1. raises: `ValidationError`.

### OTMG-UT-17 — update schema: a null is_active is refused
- **Rules:** `update_template` R5 [BUG-2357]
- **Kind:** bug
- **Expect:** xfail BUG-2357
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateUpdate(is_active=None)` (target `schema`; the field is passed explicitly).

**Then**
1. raises: `ValidationError`.

### OTMG-UT-18 — an empty payload stamps nothing
- **Rules:** `update_template` R6 [BUG-2356]
- **Kind:** bug
- **Expect:** xfail BUG-2356
- **Fails today on:** Then 2 (`updated_by` is written on every call)

**Given**
1. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `updated_by is None`.
3. re-read T: `updated_at is None`.
4. unchanged: unchanged(T).

### OTMG-UT-19 — values equal to the stored ones stamp nothing
- **Rules:** `update_template` R6 [BUG-2356]
- **Kind:** bug
- **Expect:** xfail BUG-2356
- **Fails today on:** Then 2 (`updated_by` is written on every call)

**Given**
1. T = template, but `notes "n0"`, `updated_by UO.id`, `updated_at T1`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(template_name="Rent", notes="n0"), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `updated_by == UO.id`.
3. re-read T: `updated_at == T1`.

### OTMG-UT-20 — a sent account of the workspace is stored
- **Rules:** `update_template` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. AC = account.
2. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(account_id=AC.id), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `account_id == AC.id`.

### OTMG-UT-21 — a reference not sent is not checked again
- **Rules:** `update_template` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. AC = account, closed.
2. T = template, but `account_id AC.id`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(notes="kept"), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `notes == "kept"`, `account_id == AC.id`.

### OTMG-UT-22 — a sent account of a later workspace (W2) is refused
- **Rules:** `update_template` R7 [BUG-1014]
- **Kind:** bug
- **Expect:** xfail BUG-1014
- **Fails today on:** Then 1 (no error is raised; the account is stored)

**Given**
1. T = template.
2. AC2 = account, but `workspace_id W2.id`, `name "Far"`.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(account_id=AC2.id), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Account with ID {AC2.id} not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-UT-23 — a sent account of an earlier workspace (W0) is refused
- **Rules:** `update_template` R7 [BUG-1014]
- **Kind:** bug
- **Expect:** xfail BUG-1014
- **Fails today on:** Then 1 (no error is raised; the account is stored)

**Given**
1. AC0 = account, but `workspace_id W0.id`, `name "Old"`.
2. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(account_id=AC0.id), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Account with ID {AC0.id} not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-UT-24 — a sent closed account is refused
- **Rules:** `update_template` R7 [BUG-2362]
- **Kind:** bug
- **Expect:** xfail BUG-2362
- **Fails today on:** Then 1 (no error is raised; the account is stored)

**Given**
1. AC = account, closed.
2. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(account_id=AC.id), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Account with ID {AC.id} not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-UT-25 — a sent factory of another workspace is refused on a factory template
- **Rules:** `update_template` R7 [BUG-1216]
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (no error is raised; the id is stored)

**Given**
1. F = factory.
2. T = template, but `expense_category "factory"`, `cost_center_id F.id`.
3. F2 = factory, but `workspace_id W2.id`, `name "Factory Nine"`, `abbreviation "F9"`.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(cost_center_id=F2.id), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Factory with ID {F2.id} not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-UT-26 — a sent approver who is an active owner of another workspace only is refused
- **Rules:** `update_template` R7 [BUG-1216]
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (no error is raised; the approver is stored)

**Given**
1. T = template, but `default_approver_id UA.id`.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(default_approver_id=UX.id), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Profile with ID {UX.id} not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-UT-27 — a sent approver who belongs to no workspace is refused
- **Rules:** `update_template` R7 [BUG-1216]
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (no error is raised; the approver is stored)

**Given**
1. T = template, but `default_approver_id UA.id`.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(default_approver_id=UZ.id), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Profile with ID {UZ.id} not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-UT-28 — category and cost centre sent together on a template without them are stored
- **Rules:** `update_template` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. F = factory.
2. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(expense_category="factory", cost_center_id=F.id), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `expense_category == "factory"`, `cost_center_id == F.id`.

### OTMG-UT-29 — a factory template changed to category other drops its cost centre
- **Rules:** `update_template` R8 [BUG-2360]
- **Kind:** bug
- **Expect:** xfail BUG-2360
- **Fails today on:** Then 3 (`cost_center_id` is kept)

**Given**
1. F = factory.
2. T = template, but `expense_category "factory"`, `cost_center_id F.id`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(expense_category="other"), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `expense_category == "other"`.
3. re-read T: `cost_center_id is None`.

### OTMG-UT-30 — category factory sent on a template with no cost centre is refused
- **Rules:** `update_template` R8 [BUG-2361]
- **Kind:** bug
- **Expect:** xfail BUG-2361
- **Fails today on:** Then 1 (no error is raised; the category is stored)

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(expense_category="factory"), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`, `exc.value.detail == "Select a factory for this template"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-UT-31 — a department template keeps its stored cost centre when only the name changes
- **Rules:** `update_template` R8 (merged state)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. D = department.
2. T = template, but `expense_category "department"`, `cost_center_id D.id`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(template_name="Lease"), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `template_name == "Lease"`, `expense_category == "department"`, `cost_center_id == D.id`.

### OTMG-UT-32 — update schema: an unknown category is refused
- **Rules:** `update_template` R8 [BUG-2359]
- **Kind:** bug
- **Expect:** xfail BUG-2359
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateUpdate(expense_category="garbage")` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-UT-33 — a sent category with spaces and capitals is stored trimmed and lower-cased
- **Rules:** `update_template` R8 [BUG-2359]
- **Kind:** bug
- **Expect:** xfail BUG-2359
- **Fails today on:** Then 2 (stored as typed, `" Other "`)

**Given**
1. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(expense_category=" Other "), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `expense_category == "other"`.

### OTMG-UT-34 — the template's lines are not touched
- **Rules:** `update_template` R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.
2. L1 = line 1 on T.
3. L2 = line 2 on T, but `quantity Decimal("2.00")`, `line_subtotal Decimal("20.00")`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(template_name="Lease", is_active=False), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == T.id`.
2. unchanged: unchanged(L1).
3. unchanged: unchanged(L2).
4. count: lines(T) has exactly 2 rows.

### OTMG-UT-35 — update flushes and never commits
- **Rules:** `update_template` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(template_name="Spy"), workspace_id=W1.id, user_id=UA.id)`, rolled back.

**Then**
1. returns: `result.id == T.id` (inside).
2. count: `order_templates` with `template_name == "Spy"` has exactly 1 row (inside; a fresh SELECT, no `expire_all`).
3. mock called: `cm.call_count == 0`.
4. re-read T: `template_name == "Rent"` (after).

### OTMG-UT-36 — category other sent on a template without a cost centre is stored
- **Rules:** `update_template` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(expense_category="other"), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `expense_category == "other"`, `cost_center_id is None`.

### OTMG-UT-37 — update schema: a recurrence_type of 51 characters is refused
- **Rules:** `update_template` R4 [BUG-2365]
- **Kind:** bug
- **Expect:** xfail BUG-2365
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateUpdate(recurrence_type=R51)` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-UT-38 — a null cost centre on a factory template gets the missing-cost-centre 400
- **Rules:** `update_template` R5, R8 [BUG-2361]
- **Kind:** bug
- **Expect:** xfail BUG-2361
- **Fails today on:** Then 1 (no error is raised: the null is ignored)

**Given**
1. F = factory.
2. T = template, but `expense_category "factory"`, `cost_center_id F.id`.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(cost_center_id=None), workspace_id=W1.id, user_id=UA.id)` (`cost_center_id` sent explicitly as `None`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`, `exc.value.detail == "Select a factory for this template"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-UT-39 — a null cost centre on a department template gets the missing-cost-centre 400
- **Rules:** `update_template` R5, R8 [BUG-2361]
- **Kind:** bug
- **Expect:** xfail BUG-2361
- **Fails today on:** Then 1 (no error is raised: the null is ignored)

**Given**
1. D = department.
2. T = template, but `expense_category "department"`, `cost_center_id D.id`.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(cost_center_id=None), workspace_id=W1.id, user_id=UA.id)` (`cost_center_id` sent explicitly as `None`).

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`, `exc.value.detail == "Select a department for this template"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-UT-40 — a department cost centre kept while the category moves to factory is refused as no such factory
- **Rules:** `update_template` R8a [BUG-1216]
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (no error is raised; the category is stored)

**Given**
1. D = department, but `id 880000001`.
2. T = template, but `expense_category "department"`, `cost_center_id D.id`.
3. No factory exists.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(expense_category="factory"), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Factory with ID 880000001 not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-UT-41 — a factory cost centre kept while the category moves to department is refused as no such department
- **Rules:** `update_template` R8a [BUG-1216]
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (no error is raised; the category is stored)

**Given**
1. F = factory, but `id 880000002`.
2. T = template, but `expense_category "factory"`, `cost_center_id F.id`.
3. No department exists.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(expense_category="department"), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Department with ID 880000002 not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-UT-42 — order of refusals: another workspace's template gives 404 before a non-owner's 403
- **Rules:** `update_template` R11, R1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id`.

**When**
- `M.update_template(db, tpl_id=Z.id, data=OrderTemplateUpdate(requires_approval=False, expense_category="factory"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Order template with ID {Z.id} not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(Z).

### OTMG-UT-43 — order of refusals: a non-owner's 403 comes before the missing cost centre
- **Rules:** `update_template` R11, R9 [BUG-2347]
- **Kind:** bug
- **Expect:** xfail BUG-2347
- **Fails today on:** Then 1 (no error is raised; both fields are applied)

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(requires_approval=False, expense_category="factory"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`, `exc.value.detail == FORBID`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-UT-44 — order of refusals: the missing cost centre (400) comes before the foreign account (404)
- **Rules:** `update_template` R11, R8 [BUG-2361]
- **Kind:** bug
- **Expect:** xfail BUG-2361
- **Fails today on:** Then 1 (no error is raised; both fields are applied)

**Given**
1. AC2 = account, but `workspace_id W2.id`, `name "Far"`.
2. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(expense_category="factory", account_id=AC2.id), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`, `exc.value.detail == "Select a factory for this template"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-UT-45 — order of refusals: the account's 404 comes before the cost centre's
- **Rules:** `update_template` R11, R7 [BUG-1014]
- **Kind:** bug
- **Expect:** xfail BUG-1014
- **Fails today on:** Then 1 (no error is raised; the fields are applied)

**Given**
1. AC2 = account, but `workspace_id W2.id`, `name "Far"`.
2. D2 = department, but `workspace_id W2.id`, `name "Far"`.
3. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(expense_category="department", cost_center_id=D2.id, account_id=AC2.id), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Account with ID {AC2.id} not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-UT-46 — order of refusals: the cost centre's 404 comes before the approver's
- **Rules:** `update_template` R11, R7 [BUG-1216]
- **Kind:** bug
- **Expect:** xfail BUG-1216
- **Fails today on:** Then 1 (no error is raised; the fields are applied)

**Given**
1. D = department.
2. D2 = department, but `workspace_id W2.id`, `name "Far"`.
3. T = template, but `expense_category "department"`, `cost_center_id D.id`.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(cost_center_id=D2.id, default_approver_id=UZ.id), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Department with ID {D2.id} not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

## `OrderTemplateManager.get_template`

### OTMG-GT-01 — returns the workspace's template
- **Rules:** `get_template` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`.
2. T = template, but `template_name "Lease"`.

**When**
- `result = M.get_template(db, tpl_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, OrderTemplate)`.
2. returns: `result.id == T.id`, `result.template_name == "Lease"`, `result.workspace_id == W1.id`.

### OTMG-GT-02 — an inactive template is returned
- **Rules:** `get_template` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, inactive.

**When**
- `result = M.get_template(db, tpl_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == T.id`, `result.is_active is False`.

### OTMG-GT-03 — an unknown id raises 404
- **Rules:** `get_template` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.

**When**
- `M.get_template(db, tpl_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Order template with ID 999999999 not found"`.

### OTMG-GT-04 — a template of an earlier workspace (W0) raises 404
- **Rules:** `get_template` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`.
2. T = template.

**When**
- `M.get_template(db, tpl_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Order template with ID {Z.id} not found"`.

### OTMG-GT-05 — a template of a later workspace (W2) raises 404
- **Rules:** `get_template` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id`.

**When**
- `M.get_template(db, tpl_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Order template with ID {Z.id} not found"`.

### OTMG-GT-06 — writes nothing: a pending row stays pending, an unflushed edit stays dirty
- **Rules:** `get_template` (reader)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.
2. B = template, but `template_name "Lease"`.
3. pending P.
4. `B.notes = "edited"` (not flushed).

**When**
- `result = M.get_template(db, tpl_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == T.id`.
2. pending: `P in db.new`, `P.id is None`, `len(db.new) == 1`.
3. session: `B in db.dirty`, `len(db.dirty) == 1`, `not db.deleted`.

## `OrderTemplateManager.list_templates`

### OTMG-LT-01 — with the manager's defaults: active and inactive templates of the workspace, newest first
- **Rules:** `list_templates` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = template, but `created_at T1`.
2. B = template, inactive, but `template_name "Lease"`, `created_at T2`.

**When**
- `result = M.list_templates(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `[t.id for t in result] == [B.id, A.id]`.

### OTMG-LT-02 — templates of an earlier (W0) and a later (W2) workspace are not listed
- **Rules:** `list_templates` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z0 = template, but `workspace_id W0.id`, `created_at T3`.
2. A = template, but `created_at T1`.
3. Z2 = template, but `workspace_id W2.id`, `created_at T2`.

**When**
- `result = M.list_templates(db, workspace_id=W1.id)`.

**Then**
1. returns: `[t.id for t in result] == [A.id]`.

### OTMG-LT-03 — is_active=True is passed through
- **Rules:** `list_templates` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = template, but `created_at T1`.
2. B = template, inactive, but `template_name "Lease"`, `created_at T2`.

**When**
- `result = M.list_templates(db, workspace_id=W1.id, is_active=True)`.

**Then**
1. returns: `[t.id for t in result] == [A.id]`.

### OTMG-LT-04 — is_active=False and the category are passed through together
- **Rules:** `list_templates` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = template, inactive, but `expense_category "factory"`, `created_at T1`.
2. B = template, inactive, but `template_name "Lease"`, `expense_category "other"`, `created_at T2`.
3. C = template, but `template_name "Power"`, `expense_category "factory"`, `created_at T3`.

**When**
- `result = M.list_templates(db, workspace_id=W1.id, is_active=False, expense_category="factory")`.

**Then**
1. returns: `[t.id for t in result] == [A.id]`.

### OTMG-LT-05 — skip and limit are passed through
- **Rules:** `list_templates` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, but `created_at T1`.
2. B = template, but `template_name "Lease"`, `created_at T3`.
3. C = template, but `template_name "Power"`, `created_at T2`.

**When**
- `result = M.list_templates(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `[t.id for t in result] == [C.id]`.

### OTMG-LT-06 — the default limit is 100: 101 templates give the newest 100
- **Rules:** `list_templates` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 templates E1 … E101, built with `add_all`: Ek = template, but `template_name` = `f"Rent {k}"`, `created_at` = `T0 + timedelta(minutes=k)` (`timedelta` from `datetime`).
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = M.list_templates(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `[t.id for t in result] == newest[:100]`.

### OTMG-LT-07 — limit=1000 gives all 101
- **Rules:** `list_templates` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 templates E1 … E101, built with `add_all`: Ek = template, but `template_name` = `f"Rent {k}"`, `created_at` = `T0 + timedelta(minutes=k)` (`timedelta` from `datetime`).
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = M.list_templates(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `[t.id for t in result] == newest`.

### OTMG-LT-08 — writes nothing: a pending row stays pending, an unflushed edit stays dirty
- **Rules:** `list_templates` (reader)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = template, but `created_at T1`.
2. B = template, but `workspace_id W2.id`, `created_at T1`.
3. pending P.
4. `B.notes = "edited"` (not flushed).

**When**
- `result = M.list_templates(db, workspace_id=W1.id)`.

**Then**
1. returns: `[t.id for t in result] == [A.id]`.
2. pending: `P in db.new`, `P.id is None`, `len(db.new) == 1`.
3. session: `B in db.dirty`, `len(db.dirty) == 1`.

## `OrderTemplateManager.delete_template`

### OTMG-DT-01 — an active template is switched off and stamped; it and its lines stay
- **Rules:** `delete_template` R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. L1 = line 1 on T.
3. L2 = line 2 on T.

**When**
- `result = M.delete_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result is None`.
2. re-read T: `is_active is False`, `updated_by == UA.id`, `updated_at is not None`.
3. re-read T: `template_name == "Rent"`, `created_by == UO.id`.
4. count: lines(T) has exactly 2 rows.
5. unchanged: unchanged(L1).

### OTMG-DT-02 — an unknown id is refused, nothing written
- **Rules:** `delete_template` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.

**When**
- `M.delete_template(db, tpl_id=MISSING, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Order template with ID 999999999 not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-DT-03 — a template of an earlier workspace (W0) is refused, nothing written
- **Rules:** `delete_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`.
2. T = template.

**When**
- `M.delete_template(db, tpl_id=Z.id, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Order template with ID {Z.id} not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(Z).

### OTMG-DT-04 — a template of a later workspace (W2) is refused, nothing written
- **Rules:** `delete_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id`.

**When**
- `M.delete_template(db, tpl_id=Z.id, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Order template with ID {Z.id} not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(Z).

### OTMG-DT-05 — an already inactive template: no error, nothing written, the first deleter kept
- **Rules:** `delete_template` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, inactive.

**When**
- `result = M.delete_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result is None`.
2. session: `not db.dirty`.
3. re-read T: `updated_by == UO.id`, `updated_at == T1`, `is_active is False`.
4. unchanged: unchanged(T).

### OTMG-DT-06 — expense orders made from the template are not touched
- **Rules:** `delete_template` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.
2. E = `ExpenseOrder(workspace_id=W1.id, expense_number="EXP-1", expense_category="other", created_by=UO.id, order_template_id=T.id)`.

**When**
- `result = M.delete_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result is None`.
2. re-read E: `order_template_id == T.id`.
3. unchanged: unchanged(E).

### OTMG-DT-07 — delete flushes and never commits
- **Rules:** `delete_template` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.delete_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=UA.id)`, rolled back.

**Then**
1. returns: `result is None` (inside).
2. count: `order_templates` with `id == T.id` and `is_active` false has exactly 1 row (inside; a fresh SELECT, no `expire_all`).
3. mock called: `cm.call_count == 0`.
4. re-read T: `is_active is True`, `updated_by is None` (after).

## `OrderTemplateManager.add_item`

### OTMG-AI-01 — the first line of a template gets number 1 and every field sent
- **Rules:** `add_item` R2, R3, R4, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=OrderTemplateItemCreate(description="Bolt", unit="pcs", quantity=Decimal("2.00"), unit_price=Decimal("5.00"), notes="m6"), workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, OrderTemplateItem)`, `result.id is not None`.
2. re-read the returned line: `line_number == 1`, `workspace_id == W1.id`, `order_template_id == T.id`.
3. re-read the returned line: `description == "Bolt"`, `unit == "pcs"`, `notes == "m6"`.
4. re-read the returned line: `quantity == Decimal("2.00")`, `unit_price == Decimal("5.00")`, `line_subtotal == Decimal("10.00")`.

### OTMG-AI-02 — lines 1, 2, 3 give number 4
- **Rules:** `add_item` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. L1 = line 1 on T.
3. L2 = line 2 on T.
4. L3 = line 3 on T.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=ITEM, workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned line: `line_number == 4`.

### OTMG-AI-03 — the highest number counts, not the number of lines: lines 2, 3, 4 give 5
- **Rules:** `add_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. L2 = line 2 on T.
3. L3 = line 3 on T.
4. L4 = line 4 on T.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=ITEM, workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned line: `line_number == 5`.
3. unchanged: unchanged(L2).

### OTMG-AI-04 — the highest number counts, not the newest line: lines built as 3 then 1 give 4
- **Rules:** `add_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. L3 = line 3 on T.
3. L1 = line 1 on T.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=ITEM, workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned line: `line_number == 4`.

### OTMG-AI-05 — another template's higher line numbers do not count
- **Rules:** `add_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = template, but `template_name "Lease"`.
2. T = template.
3. K = line 9 on S.
4. L1 = line 1 on T.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=ITEM, workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned line: `line_number == 2`, `order_template_id == T.id`.

### OTMG-AI-06 — an inactive template accepts a line
- **Rules:** `add_item` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, inactive.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=ITEM, workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned line: `order_template_id == T.id`, `line_number == 1`.
3. re-read T: `is_active is False`.

### OTMG-AI-07 — an unknown template is refused, nothing written
- **Rules:** `add_item` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.

**When**
- `M.add_item(db, tpl_id=MISSING, data=ITEM, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Order template not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-AI-08 — a template of an earlier workspace (W0) is refused, nothing written
- **Rules:** `add_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`.
2. T = template.

**When**
- `M.add_item(db, tpl_id=Z.id, data=ITEM, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Order template not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-AI-09 — a template of a later workspace (W2) is refused, nothing written
- **Rules:** `add_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id`.

**When**
- `M.add_item(db, tpl_id=Z.id, data=ITEM, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Order template not found"`.
3. session: `not db.new`.
4. nothing written.

### OTMG-AI-10 — a product ending in 5 rounds half up: 0.50 × 0.25 gives 0.13
- **Rules:** `add_item` R4 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=OrderTemplateItemCreate(description="Washer", quantity=Decimal("0.50"), unit_price=Decimal("0.25")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned line: `line_subtotal == Decimal("0.13")` (half to even would give 0.12).

### OTMG-AI-11 — a product below the half rounds down: 0.30 × 0.41 gives 0.12
- **Rules:** `add_item` R4 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=OrderTemplateItemCreate(description="Low", quantity=Decimal("0.30"), unit_price=Decimal("0.41")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned line: `line_subtotal == Decimal("0.12")`.

### OTMG-AI-12 — a line with no price has subtotal 0.00 and keeps its price empty
- **Rules:** `add_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=OrderTemplateItemCreate(description="Labour", quantity=Decimal("4.00")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned line: `unit_price is None`, `line_subtotal == Decimal("0.00")`.

### OTMG-AI-13 — quantity not sent is 1, so the subtotal is the price
- **Rules:** `add_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=OrderTemplateItemCreate(description="Fee", unit_price=Decimal("12.50")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned line: `quantity == Decimal("1.00")`, `line_subtotal == Decimal("12.50")`.

### OTMG-AI-14 — a price of 0 gives subtotal 0.00
- **Rules:** `add_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=OrderTemplateItemCreate(description="Free", quantity=Decimal("4.00"), unit_price=Decimal("0")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned line: `unit_price == Decimal("0.00")`, `line_subtotal == Decimal("0.00")`.

### OTMG-AI-15 — add flushes and never commits
- **Rules:** `add_item` Returns
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=ITEM, workspace_id=W1.id)`, rolled back.

**Then**
1. returns: `result.id is not None` (inside).
2. count: `order_template_items` with `order_template_id == T.id` has exactly 1 row (inside).
3. mock called: `cm.call_count == 0`.
4. count: `order_template_items` with `order_template_id == T.id` has exactly 0 rows (after).

## `OrderTemplateManager.update_item`

### OTMG-UI-01 — quantity sent: subtotal is the new quantity × the stored price
- **Rules:** `update_item` R2, R4, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(quantity=Decimal("4.00")), workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, OrderTemplateItem)`, `result.id == L.id`.
2. re-read L: `quantity == Decimal("4.00")`, `unit_price == Decimal("10.00")`.
3. re-read L: `line_subtotal == Decimal("40.00")`.

### OTMG-UI-02 — price sent: subtotal is the stored quantity × the new price
- **Rules:** `update_item` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(unit_price=Decimal("2.50")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `quantity == Decimal("3.00")`, `unit_price == Decimal("2.50")`.
3. re-read L: `line_subtotal == Decimal("7.50")`.

### OTMG-UI-03 — both sent: subtotal is the new quantity × the new price
- **Rules:** `update_item` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(quantity=Decimal("2.00"), unit_price=Decimal("1.25")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `line_subtotal == Decimal("2.50")`.

### OTMG-UI-04 — neither sent: the subtotal is not recomputed, even when it disagrees with the stored values
- **Rules:** `update_item` R2, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T, but `line_subtotal Decimal("99.00")`.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(description="Hex bolt"), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `description == "Hex bolt"`.
3. re-read L: `line_subtotal == Decimal("99.00")`, `quantity == Decimal("3.00")`, `unit_price == Decimal("10.00")`.

### OTMG-UI-05 — fields not sent keep their values
- **Rules:** `update_item` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T, but `unit "pcs"`, `notes "n0"`.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(unit="kg"), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `unit == "kg"`.
3. re-read L: `notes == "n0"`, `description == "Line"`, `line_number == 1`, `order_template_id == T.id`.
4. re-read L: `line_subtotal == Decimal("30.00")`.

### OTMG-UI-06 — a stored empty price counts as 0 when only the quantity is sent
- **Rules:** `update_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T, but `unit_price None`, `line_subtotal Decimal("0.00")`.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(quantity=Decimal("5.00")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `quantity == Decimal("5.00")`, `unit_price is None`.
3. re-read L: `line_subtotal == Decimal("0.00")`.

### OTMG-UI-07 — a new quantity on a stored price rounds half up: 0.50 × 0.25 gives 0.13
- **Rules:** `update_item` R4 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T, but `unit_price Decimal("0.25")`, `line_subtotal Decimal("0.75")`.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(quantity=Decimal("0.50")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `line_subtotal == Decimal("0.13")` (half to even would give 0.12).

### OTMG-UI-08 — a new price on a stored quantity below the half rounds down: 0.30 × 0.41 gives 0.12
- **Rules:** `update_item` R4 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T, but `quantity Decimal("0.30")`, `line_subtotal Decimal("3.00")`.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(unit_price=Decimal("0.41")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `line_subtotal == Decimal("0.12")`.

### OTMG-UI-09 — a new price on a stored quantity above the half rounds up: 0.30 × 0.42 gives 0.13
- **Rules:** `update_item` R4 (HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T, but `quantity Decimal("0.30")`, `line_subtotal Decimal("3.00")`.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(unit_price=Decimal("0.42")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `line_subtotal == Decimal("0.13")`.

### OTMG-UI-10 — a line of an inactive template is updated
- **Rules:** `update_item` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, inactive.
2. L = line 1 on T.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(quantity=Decimal("1.00")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `quantity == Decimal("1.00")`, `line_subtotal == Decimal("10.00")`.

### OTMG-UI-11 — an unknown line is refused, nothing written
- **Rules:** `update_item` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T.

**When**
- `M.update_item(db, item_id=MISSING, data=OrderTemplateItemUpdate(quantity=Decimal("4.00")), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Template item not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(L).

### OTMG-UI-12 — a line of an earlier workspace (W0) is refused, nothing written
- **Rules:** `update_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`.
2. ZL = line 1 on Z, but `workspace_id W0.id`.
3. T = template.
4. L = line 1 on T.

**When**
- `M.update_item(db, item_id=ZL.id, data=OrderTemplateItemUpdate(quantity=Decimal("4.00")), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Template item not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(ZL).

### OTMG-UI-13 — a line of a later workspace (W2) is refused, nothing written
- **Rules:** `update_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T.
3. Z = template, but `workspace_id W2.id`.
4. ZL = line 1 on Z, but `workspace_id W2.id`.

**When**
- `M.update_item(db, item_id=ZL.id, data=OrderTemplateItemUpdate(quantity=Decimal("4.00")), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Template item not found"`.
3. session: `not db.dirty`.
4. unchanged: unchanged(ZL).

### OTMG-UI-14 — a price of 0 is stored as 0.00
- **Rules:** `update_item` R2, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(unit_price=Decimal("0")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `unit_price == Decimal("0.00")`, `quantity == Decimal("3.00")`.

### OTMG-UI-15 — a price of 0 gives subtotal 0.00
- **Rules:** `update_item` R5 [BUG-1226]
- **Kind:** bug
- **Expect:** xfail BUG-1226
- **Fails today on:** Then 2 (0 counts as not sent; the subtotal stays 30.00)

**Given**
1. T = template.
2. L = line 1 on T.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(unit_price=Decimal("0")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `line_subtotal == Decimal("0.00")`.

### OTMG-UI-16 — an explicit null clears the description
- **Rules:** `update_item` R3 [BUG-2358]
- **Kind:** bug
- **Expect:** xfail BUG-2358
- **Fails today on:** Then 2 (the null is ignored; `"Line"` stays)

**Given**
1. T = template.
2. L = line 1 on T.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(description=None), workspace_id=W1.id)` (sent, as null).

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `description is None`.

### OTMG-UI-17 — an explicit null clears the price and the subtotal becomes 0.00
- **Rules:** `update_item` R3, R6 [BUG-2358]
- **Kind:** bug
- **Expect:** xfail BUG-2358
- **Fails today on:** Then 2 (the null is ignored; the price stays 10.00)

**Given**
1. T = template.
2. L = line 1 on T.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(unit_price=None), workspace_id=W1.id)` (sent, as null).

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `unit_price is None`.
3. re-read L: `line_subtotal == Decimal("0.00")`.

### OTMG-UI-18 — line update schema: a null quantity is refused
- **Rules:** `update_item` R3 [BUG-2358]
- **Kind:** bug
- **Expect:** xfail BUG-2358
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateItemUpdate(quantity=None)` (target `schema`; the field is passed explicitly).

**Then**
1. raises: `ValidationError`.

### OTMG-UI-19 — line update schema: more than 2 decimals in the price are refused
- **Rules:** `update_item` R4 [BUG-2363]
- **Kind:** bug
- **Expect:** xfail BUG-2363
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateItemUpdate(unit_price=Decimal("0.125"))` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-UI-20 — line update schema: quantity 0 is refused
- **Rules:** `update_item` R4 [BUG-2364]
- **Kind:** bug
- **Expect:** xfail BUG-2364
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateItemUpdate(quantity=Decimal("0"))` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-UI-21 — line update schema: a negative price is refused
- **Rules:** `update_item` R4 [BUG-2364]
- **Kind:** bug
- **Expect:** xfail BUG-2364
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing.

**When**
- build `OrderTemplateItemUpdate(unit_price=Decimal("-0.01"))` (target `schema`).

**Then**
1. raises: `ValidationError`.

### OTMG-UI-22 — line update schema: quantity 0.01 and price 0 are accepted
- **Rules:** `update_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing.

**When**
- `result = OrderTemplateItemUpdate(quantity=Decimal("0.01"), unit_price=Decimal("0"))` (target `schema`).

**Then**
1. returns: `result.quantity == Decimal("0.01")`, `result.unit_price == Decimal("0")`.

### OTMG-UI-23 — update_item flushes and never commits
- **Rules:** `update_item` Returns
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(quantity=Decimal("4.00")), workspace_id=W1.id)`, rolled back.

**Then**
1. returns: `result.id == L.id` (inside).
2. count: `order_template_items` with `id == L.id` and `quantity == Decimal("4.00")` has exactly 1 row (inside; a fresh SELECT, no `expire_all`).
3. mock called: `cm.call_count == 0`.
4. re-read L: `quantity == Decimal("3.00")`, `line_subtotal == Decimal("30.00")` (after).

### OTMG-UI-24 — a new price that makes the total 10^13 or more is refused with 422
- **Rules:** `update_item` R4a [BUG-2349]
- **Kind:** bug
- **Expect:** xfail BUG-2349
- **Fails today on:** Then 1 (the call raises DataError at flush, not HTTPException)

**Given**
1. T = template.
2. L = line 1 on T, but `quantity Decimal("10000.00")`, `line_subtotal Decimal("100000.00")`.

**When**
- `M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(unit_price=Decimal("1000000000")), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`, `exc.value.detail == LTL`.
3. session: `not db.dirty`.
4. unchanged: unchanged(L).

### OTMG-UI-25 — a new price that keeps the total just below 10^13 is stored, rounded half up
- **Rules:** `update_item` R4, R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T, but `quantity Decimal("1.01")`, `line_subtotal Decimal("10.10")`.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(unit_price=Decimal("9900990099009.89")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `quantity == Decimal("1.01")`, `unit_price == Decimal("9900990099009.89")`, `line_subtotal == Decimal("9999999999999.99")`.

### OTMG-UI-26 — a new price whose total rounds half up to 10^13 is refused with 422
- **Rules:** `update_item` R4a [BUG-2349]
- **Kind:** bug
- **Expect:** xfail BUG-2349
- **Fails today on:** Then 1 (the call raises DataError at flush, not HTTPException)

**Given**
1. T = template.
2. L = line 1 on T, but `quantity Decimal("1.01")`, `line_subtotal Decimal("10.10")`.

**When**
- `M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(unit_price=Decimal("9900990099009.90")), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`, `exc.value.detail == LTL`.
3. session: `not db.dirty`.
4. unchanged: unchanged(L).

### OTMG-UI-27 — a new quantity that makes the total with the stored price 10^13 or more is refused with 422
- **Rules:** `update_item` R4a [BUG-2349]
- **Kind:** bug
- **Expect:** xfail BUG-2349
- **Fails today on:** Then 1 (the call raises DataError at flush, not HTTPException)

**Given**
1. T = template.
2. L = line 1 on T, but `quantity Decimal("1.00")`, `unit_price Decimal("1000000000.00")`, `line_subtotal Decimal("1000000000.00")`.

**When**
- `M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(quantity=Decimal("10000")), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 422`, `exc.value.detail == LTL`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. unchanged: unchanged(L).

### OTMG-UI-28 — a new quantity that keeps the total with the stored price just below 10^13 is stored, rounded half up
- **Rules:** `update_item` R4, R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T, but `quantity Decimal("1.00")`, `unit_price Decimal("9900990099009.89")`, `line_subtotal Decimal("9900990099009.89")`.

**When**
- `result = M.update_item(db, item_id=L.id, data=OrderTemplateItemUpdate(quantity=Decimal("1.01")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `quantity == Decimal("1.01")`, `unit_price == Decimal("9900990099009.89")`, `line_subtotal == Decimal("9999999999999.99")`.

## `OrderTemplateManager.remove_item`

### OTMG-RI-01 — the line is deleted and flushed; the others keep their numbers; the removed line is returned
- **Rules:** `remove_item` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. L1 = line 1 on T.
3. L2 = line 2 on T, but `description "Middle"`.
4. L3 = line 3 on T.

**When**
- `result = M.remove_item(db, item_id=L2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L2.id`, `result.line_number == 2`, `result.description == "Middle"`.
2. count: `order_template_items` with `id == L2.id` has exactly 0 rows (a fresh SELECT, no `expire_all`).
3. re-read lines(T): `[l.id for l in lines] == [L1.id, L3.id]`.
4. re-read lines(T): `[l.line_number for l in lines] == [1, 3]`.

### OTMG-RI-02 — an unknown line is refused, nothing deleted
- **Rules:** `remove_item` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T.

**When**
- `M.remove_item(db, item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Template item not found"`.
3. session: `not db.deleted`.
4. nothing written.

### OTMG-RI-03 — a line of an earlier workspace (W0) is refused, nothing deleted
- **Rules:** `remove_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`.
2. ZL = line 1 on Z, but `workspace_id W0.id`.
3. T = template.
4. L = line 1 on T.

**When**
- `M.remove_item(db, item_id=ZL.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Template item not found"`.
3. session: `not db.deleted`.
4. nothing written.

### OTMG-RI-04 — a line of a later workspace (W2) is refused, nothing deleted
- **Rules:** `remove_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T.
3. Z = template, but `workspace_id W2.id`.
4. ZL = line 1 on Z, but `workspace_id W2.id`.

**When**
- `M.remove_item(db, item_id=ZL.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Template item not found"`.
3. session: `not db.deleted`.
4. nothing written.

### OTMG-RI-05 — remove flushes and never commits
- **Rules:** `remove_item` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.
2. L = line 1 on T.

**When**
- `result = M.remove_item(db, item_id=L.id, workspace_id=W1.id)`, rolled back.

**Then**
1. returns: `result.id == L.id` (inside).
2. count: `order_template_items` with `id == L.id` has exactly 0 rows (inside; a fresh SELECT, no `expire_all`).
3. mock called: `cm.call_count == 0`.
4. count: `order_template_items` with `id == L.id` has exactly 1 row (after).

## `OrderTemplateManager.get_items`

### OTMG-GI-01 — returns the template's lines ordered by line number
- **Rules:** `get_items` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = template, but `template_name "Lease"`.
2. T = template.
3. A = line 3 on T.
4. K = line 1 on S.
5. B = line 1 on T.
6. C = line 2 on T.

**When**
- `result = M.get_items(db, tpl_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `[l.id for l in result] == [B.id, C.id, A.id]`.

### OTMG-GI-02 — the lines of an inactive template are returned
- **Rules:** `get_items` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, inactive.
2. A = line 1 on T.

**When**
- `result = M.get_items(db, tpl_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `[l.id for l in result] == [A.id]`.

### OTMG-GI-03 — a template with no lines gives an empty list
- **Rules:** `get_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.get_items(db, tpl_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### OTMG-GI-04 — an unknown template raises 404
- **Rules:** `get_items` R2 [BUG-2366]
- **Kind:** bug
- **Expect:** xfail BUG-2366
- **Fails today on:** Then 1 (no error is raised; `[]` is returned)

**Given**
1. T = template.
2. A = line 1 on T.

**When**
- `M.get_items(db, tpl_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == "Order template with ID 999999999 not found"`.

### OTMG-GI-05 — a template of an earlier workspace (W0) raises 404
- **Rules:** `get_items` R2 [BUG-2366]
- **Kind:** bug
- **Expect:** xfail BUG-2366
- **Fails today on:** Then 1 (no error is raised; `[]` is returned)

**Given**
1. Z = template, but `workspace_id W0.id`.
2. ZL = line 1 on Z, but `workspace_id W0.id`.
3. T = template.

**When**
- `M.get_items(db, tpl_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Order template with ID {Z.id} not found"`.

### OTMG-GI-06 — a template of a later workspace (W2) raises 404
- **Rules:** `get_items` R2 [BUG-2366]
- **Kind:** bug
- **Expect:** xfail BUG-2366
- **Fails today on:** Then 1 (no error is raised; `[]` is returned)

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id`.
3. ZL = line 1 on Z, but `workspace_id W2.id`.

**When**
- `M.get_items(db, tpl_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`, `exc.value.detail == f"Order template with ID {Z.id} not found"`.

### OTMG-GI-07 — writes nothing: a pending line stays pending, an unflushed edit stays dirty
- **Rules:** `get_items` (reader)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.
2. A = line 2 on T.
3. B = line 3 on T.
4. `P = OrderTemplateItem(workspace_id=W1.id, order_template_id=T.id, line_number=1, description="Pending", quantity=Decimal("1"))`, `db.add(P)`, not flushed.
5. `B.description = "Edited"` (not flushed).

**When**
- `result = M.get_items(db, tpl_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `A.id in [l.id for l in result]`, `len(result) == 2`.
2. pending: `P in db.new`, `P.id is None`, `len(db.new) == 1`.
3. session: `B in db.dirty`, `len(db.dirty) == 1`.

## `create_template` R9, `update_template` R9 — BUG-2347 (OQ-22, owner 2026-11-07)

> The owner's answer: only the workspace owner may create a template that skips approval (`requires_approval False` or `auto_approve True`), or change either flag. Owner = `workspaces.owner_user_id == user_id`, or an active `owner` member row in that workspace. Refusals are strict xfail BUG-2347; the owner's own requests, the defaults, re-sent stored values and other fields pass today and after the fix.

### OTMG-Q22-01 — a ground-team member may not create a template that skips approval
- **Rules:** `create_template` R9 [BUG-2347], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-2347
- **Fails today on:** Then 1 (no error is raised; the template is stored)

**Given**
1. No template exists (UG is an active `ground-team` member of W1).

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Misc supplies", requires_approval=False, items=[ITEM]), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`, `exc.value.detail == FORBID`.
3. session: `not db.new`.
4. nothing written.

### OTMG-Q22-02 — a ground-team member may not create a template that auto-approves
- **Rules:** `create_template` R9 [BUG-2347]
- **Kind:** bug
- **Expect:** xfail BUG-2347
- **Fails today on:** Then 1 (no error is raised; the template is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Misc supplies", auto_approve=True, items=[ITEM]), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`, `exc.value.detail == FORBID`.
3. session: `not db.new`.
4. nothing written.

### OTMG-Q22-03 — the owner (active owner member row) creates a template that skips approval and auto-approves; it is stored
- **Rules:** `create_template` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Payroll", requires_approval=False, auto_approve=True), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `requires_approval is False`, `auto_approve is True`.

### OTMG-Q22-04 — a ground-team member may not switch requires_approval off
- **Rules:** `update_template` R9 [BUG-2347]
- **Kind:** bug
- **Expect:** xfail BUG-2347
- **Fails today on:** Then 1 (no error is raised; the change is applied)

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(requires_approval=False), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`, `exc.value.detail == FORBID`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-Q22-05 — a ground-team member may not switch auto_approve on
- **Rules:** `update_template` R9 [BUG-2347]
- **Kind:** bug
- **Expect:** xfail BUG-2347
- **Fails today on:** Then 1 (no error is raised; the change is applied)

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(auto_approve=True), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`, `exc.value.detail == FORBID`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-Q22-06 — the owner switches requires_approval back on and auto_approve off; it is applied
- **Rules:** `update_template` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but `requires_approval False`, `auto_approve True`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(requires_approval=True, auto_approve=False), workspace_id=W1.id, user_id=UO.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `requires_approval is True`, `auto_approve is False`.

### OTMG-Q22-07 — the owner through `owner_user_id` (a W1 manager by member row) creates a template that skips approval; it is stored
- **Rules:** `create_template` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. `W1.owner_user_id = UA.id`, then `db.flush()`.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Payroll", requires_approval=False), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `requires_approval is False`, `created_by == UA.id`.

### OTMG-Q22-08 — a suspended owner row is not the owner
- **Rules:** `create_template` R9 [BUG-2347]
- **Kind:** bug
- **Expect:** xfail BUG-2347
- **Fails today on:** Then 1 (no error is raised; the template is stored)

**Given**
1. P1 = `make_profile(db)`.
2. `db.add(WorkspaceMember(workspace_id=W1.id, user_id=P1.id, role="owner", status="suspended"))`, then `db.flush()`.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Misc supplies", requires_approval=False, items=[ITEM]), workspace_id=W1.id, user_id=P1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`, `exc.value.detail == FORBID`.
3. session: `not db.new`.
4. nothing written.

### OTMG-Q22-09 — the owner of W2 (member row), a manager in W1, may not create a W1 template that skips approval
- **Rules:** `create_template` R9 [BUG-2347]
- **Kind:** bug
- **Expect:** xfail BUG-2347
- **Fails today on:** Then 1 (no error is raised; the template is stored)

**Given**
1. `db.add(WorkspaceMember(workspace_id=W1.id, user_id=UX.id, role="manager", status="active"))`, then `db.flush()` (UX also owns W2 by its standing member row).

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Misc supplies", requires_approval=False, items=[ITEM]), workspace_id=W1.id, user_id=UX.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`, `exc.value.detail == FORBID`.
3. session: `not db.new`.
4. nothing written.

### OTMG-Q22-10 — the owner of W0 (member row), a manager in W1, may not create a W1 template that auto-approves
- **Rules:** `create_template` R9 [BUG-2347]
- **Kind:** bug
- **Expect:** xfail BUG-2347
- **Fails today on:** Then 1 (no error is raised; the template is stored)

**Given**
1. P1 = `make_profile(db)`.
2. `db.add(WorkspaceMember(workspace_id=W0.id, user_id=P1.id, role="owner", status="active"))`, then `db.flush()`.
3. `db.add(WorkspaceMember(workspace_id=W1.id, user_id=P1.id, role="manager", status="active"))`, then `db.flush()`.

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Misc supplies", auto_approve=True, items=[ITEM]), workspace_id=W1.id, user_id=P1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`, `exc.value.detail == FORBID`.
3. session: `not db.new`.
4. nothing written.

### OTMG-Q22-11 — W2's `owner_user_id`, a manager in W1, may not create a W1 template that skips approval
- **Rules:** `create_template` R9 [BUG-2347]
- **Kind:** bug
- **Expect:** xfail BUG-2347
- **Fails today on:** Then 1 (no error is raised; the template is stored)

**Given**
1. `W2.owner_user_id = UA.id`, then `db.flush()` (UA is a W1 `manager`).

**When**
- `M.create_template(db, data=OrderTemplateCreate(template_name="Misc supplies", requires_approval=False, items=[ITEM]), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`, `exc.value.detail == FORBID`.
3. session: `not db.new`.
4. nothing written.

### OTMG-Q22-12 — the defaults sent explicitly need no role: a ground-team member's template is stored
- **Rules:** `create_template` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=OrderTemplateCreate(template_name="Misc supplies", requires_approval=True, auto_approve=False), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `requires_approval is True`, `auto_approve is False`, `created_by == UG.id`.

### OTMG-Q22-13 — a ground-team member may not switch requires_approval back on either
- **Rules:** `update_template` R9 [BUG-2347]
- **Kind:** bug
- **Expect:** xfail BUG-2347
- **Fails today on:** Then 1 (no error is raised; the change is applied)

**Given**
1. T = template, but `requires_approval False`.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(requires_approval=True), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`, `exc.value.detail == FORBID`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-Q22-14 — a refused flag change writes none of the other fields sent with it
- **Rules:** `update_template` R9 [BUG-2347]
- **Kind:** bug
- **Expect:** xfail BUG-2347
- **Fails today on:** Then 1 (no error is raised; the change is applied)

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(template_name="Lease", requires_approval=False), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`, `exc.value.detail == FORBID`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).
5. re-read T: `template_name == "Rent"`, `requires_approval is True`, `updated_by is None`.

### OTMG-Q22-15 — re-sending the stored flags is no change: a ground-team member's other field is applied
- **Rules:** `update_template` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(template_name="Lease", requires_approval=True, auto_approve=False), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `template_name == "Lease"`, `requires_approval is True`, `auto_approve is False`, `updated_by == UG.id`.

### OTMG-Q22-16 — a ground-team member may rename a template that already skips approval; the flags stay
- **Rules:** `update_template` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but `requires_approval False`, `auto_approve True`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(template_name="Lease"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `template_name == "Lease"`, `requires_approval is False`, `auto_approve is True`.

### OTMG-Q22-17 — the owner of W2 (member row), a manager in W1, may not switch a W1 template's requires_approval off
- **Rules:** `update_template` R9 [BUG-2347]
- **Kind:** bug
- **Expect:** xfail BUG-2347
- **Fails today on:** Then 1 (no error is raised; the change is applied)

**Given**
1. `db.add(WorkspaceMember(workspace_id=W1.id, user_id=UX.id, role="manager", status="active"))`, then `db.flush()`.
2. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(requires_approval=False), workspace_id=W1.id, user_id=UX.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`, `exc.value.detail == FORBID`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).

### OTMG-Q22-18 — the owner through `owner_user_id` switches auto_approve on; it is applied
- **Rules:** `update_template` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. `W1.owner_user_id = UA.id`, then `db.flush()`.
2. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=OrderTemplateUpdate(auto_approve=True), workspace_id=W1.id, user_id=UA.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `auto_approve is True`, `requires_approval is True`, `updated_by == UA.id`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Service commit, rollback and HTTP mapping of every callable | `OrderTemplateService` (`tests/unit/services/order_template_service.spec.md`) | TC1–TC6 and pass-throughs |
| `list_templates` R1, the endpoint's default `is_active=True` and `1 <= limit <= 1000` | `GET /order-templates/` | endpoint defaults (HR-7) |
| `get_by_workspace` R1–R8, BUG-1210; `get_by_template` order, BUG-1211 | `tests/unit/dao/order_template.cases.md` | already covered there; `list_templates` and `get_items` here check pass-through only |
| FU-1: an order made from a template copies the line fields, not `line_subtotal`; inactive template → 400 `Template is inactive` | `ExpenseOrderManager.create_expense_order_from_template` | the consumer's own rules |

## Spec gaps
None open. Gaps 1–9 of revision 1 were closed by the spec's Gap log (2026-11-07):
- G1: date and integer types confirmed (CT-03, UT-08 unchanged). G2: `is_deleted`, `deleted_at` confirmed for the conventions **closed** / **deleted**. G3: the minimal `ExpenseOrder` row, used in DT-06. G4: `recurrence_type` over 50 → 422 (CT-60, CT-61, UT-37).
- G5: BUG-2349 (CT-57 … CT-59, UI-24 … UI-26; CT-52 adjusted). G6: a null cost centre gets BUG-2361's 400 (UT-38, UT-39). G7: R8a (UT-40, UT-41). G8: R11 (CT-62 … CT-65, UT-42 … UT-46). G9: no card, by the spec's Notes.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_template` | Returns | OTMG-CT-01, OTMG-CT-55 |
| `create_template` | R1 | OTMG-CT-01, OTMG-CT-02 |
| `create_template` | R2 | OTMG-CT-03 |
| `create_template` | R3 | OTMG-CT-14, OTMG-CT-15 |
| `create_template` | R3 [BUG-2355] | OTMG-CT-16, OTMG-CT-17, OTMG-CT-18 |
| `create_template` | R3 [BUG-2365] | OTMG-CT-19, OTMG-CT-60 |
| `create_template` | R3 (`recurrence_type` 50) | OTMG-CT-61 |
| `create_template` | R4 | OTMG-CT-01, OTMG-CT-22, OTMG-CT-56 |
| `create_template` | R4 [BUG-2359] | OTMG-CT-20, OTMG-CT-21 |
| `create_template` | R5 | OTMG-CT-56 |
| `create_template` | R5 [BUG-2360] | OTMG-CT-23, OTMG-CT-24 |
| `create_template` | R5 [BUG-2361], Errors row 2 | OTMG-CT-25, OTMG-CT-26, OTMG-CT-63 |
| `create_template` | R6 (valid references) | OTMG-CT-01, OTMG-CT-22, OTMG-CT-43 |
| `create_template` | R6 [BUG-1014], Errors rows 1, 4 | OTMG-CT-27, OTMG-CT-28, OTMG-CT-30, OTMG-CT-64 |
| `create_template` | R6 [BUG-1216], Errors rows 1, 4 | OTMG-CT-65, OTMG-CT-31, OTMG-CT-32, OTMG-CT-34, OTMG-CT-35, OTMG-CT-37, OTMG-CT-38, OTMG-CT-39, OTMG-CT-40, OTMG-CT-41, OTMG-CT-42 |
| `create_template` | R6 [BUG-2362] | OTMG-CT-29, OTMG-CT-33, OTMG-CT-36 |
| `create_template` | R7 | OTMG-CT-02 |
| `create_template` | R8 | OTMG-CT-06 … OTMG-CT-13, OTMG-CT-51, OTMG-CT-52, OTMG-CT-54, OTMG-CT-59 |
| `create_template` | R8a [BUG-2349] | OTMG-CT-57, OTMG-CT-58 (boundary pass: OTMG-CT-59) |
| `create_template` | R8 [BUG-2363] | OTMG-CT-44, OTMG-CT-45, OTMG-CT-46, OTMG-CT-47 |
| `create_template` | R8 [BUG-2364] | OTMG-CT-48, OTMG-CT-49, OTMG-CT-50 |
| `create_template` | R8 [BUG-2365] | OTMG-CT-53 |
| `create_template` | R9 | OTMG-Q22-03, OTMG-Q22-07, OTMG-Q22-12 |
| `create_template` | R9 [BUG-2347], Errors row 3 | OTMG-Q22-01, OTMG-Q22-02, OTMG-Q22-08, OTMG-Q22-09, OTMG-Q22-10, OTMG-Q22-11 |
| `create_template` | R10 | OTMG-CT-02, OTMG-CT-04, OTMG-CT-05 |
| `create_template` | R11 | OTMG-CT-62 [BUG-2347], OTMG-CT-63 [BUG-2361], OTMG-CT-64 [BUG-1014], OTMG-CT-65 [BUG-1216] |
| `create_template` | Side effects (flush, no commit) | OTMG-CT-55 |
| `update_template` | Returns | OTMG-UT-01 |
| `update_template` | R1, Errors | OTMG-UT-03, OTMG-UT-04, OTMG-UT-05 |
| `update_template` | R2 | OTMG-UT-01, OTMG-UT-02, OTMG-UT-06, OTMG-UT-07 |
| `update_template` | R3 | OTMG-UT-08 |
| `update_template` | R4 | OTMG-UT-09 |
| `update_template` | R4 [BUG-2355] | OTMG-UT-10, OTMG-UT-11 |
| `update_template` | R4 [BUG-2365] | OTMG-UT-12, OTMG-UT-37 |
| `update_template` | R5 [BUG-2357] | OTMG-UT-13, OTMG-UT-14, OTMG-UT-15, OTMG-UT-16, OTMG-UT-17 |
| `update_template` | R5 null cost centre [BUG-2361] | OTMG-UT-38, OTMG-UT-39 |
| `update_template` | R6 | OTMG-UT-01, OTMG-UT-07 |
| `update_template` | R6 [BUG-2356] | OTMG-UT-18, OTMG-UT-19 |
| `update_template` | R7 | OTMG-UT-20, OTMG-UT-21 |
| `update_template` | R7 [BUG-1014] | OTMG-UT-22, OTMG-UT-23 |
| `update_template` | R7 [BUG-1216] | OTMG-UT-25, OTMG-UT-26, OTMG-UT-27 |
| `update_template` | R7 [BUG-2362] | OTMG-UT-24 |
| `update_template` | R8 | OTMG-UT-28, OTMG-UT-31, OTMG-UT-36 |
| `update_template` | R8 [BUG-2359] | OTMG-UT-32, OTMG-UT-33 |
| `update_template` | R8 [BUG-2360] | OTMG-UT-29 |
| `update_template` | R8 [BUG-2361] | OTMG-UT-30 |
| `update_template` | R8a [BUG-1216] | OTMG-UT-40, OTMG-UT-41 |
| `update_template` | R9 | OTMG-Q22-06, OTMG-Q22-15, OTMG-Q22-16, OTMG-Q22-18 |
| `update_template` | R9 [BUG-2347] | OTMG-Q22-04, OTMG-Q22-05, OTMG-Q22-13, OTMG-Q22-14, OTMG-Q22-17 |
| `update_template` | R10 | OTMG-UT-34 |
| `update_template` | R11 | OTMG-UT-42, OTMG-UT-43 [BUG-2347], OTMG-UT-44 [BUG-2361], OTMG-UT-45 [BUG-1014], OTMG-UT-46 [BUG-1216] |
| `update_template` | Side effects (flush, no commit) | OTMG-UT-35 |
| `get_template` | R1 | OTMG-GT-01, OTMG-GT-02 |
| `get_template` | R2 | OTMG-GT-03, OTMG-GT-04, OTMG-GT-05 |
| `get_template` | reader writes nothing | OTMG-GT-06 |
| `list_templates` | R1 | OTMG-LT-01 … OTMG-LT-07 |
| `list_templates` | reader writes nothing | OTMG-LT-08 |
| `delete_template` | Returns | OTMG-DT-01, OTMG-DT-05 |
| `delete_template` | R1 | OTMG-DT-02, OTMG-DT-03, OTMG-DT-04 |
| `delete_template` | R2 | OTMG-DT-01 |
| `delete_template` | R3 | OTMG-DT-05 |
| `delete_template` | R4 | OTMG-DT-06 |
| `delete_template` | Side effects (flush, no commit) | OTMG-DT-07 |
| `add_item` | Returns | OTMG-AI-01, OTMG-AI-15 |
| `add_item` | R1 | OTMG-AI-07, OTMG-AI-08, OTMG-AI-09 |
| `add_item` | R2 | OTMG-AI-01 … OTMG-AI-05 |
| `add_item` | R3 | OTMG-AI-01, OTMG-AI-06 |
| `add_item` | R4 | OTMG-AI-01, OTMG-AI-10 … OTMG-AI-14, OTMG-CT-51, OTMG-CT-52 |
| `add_item` | R4 [BUG-2363, BUG-2364, BUG-2365, BUG-2349] | OTMG-CT-44 … OTMG-CT-50, OTMG-CT-53, OTMG-CT-57, OTMG-CT-58 (same schema `OrderTemplateItemCreate`) |
| `update_item` | Returns | OTMG-UI-01, OTMG-UI-23 |
| `update_item` | R1 | OTMG-UI-11, OTMG-UI-12, OTMG-UI-13 |
| `update_item` | R2 | OTMG-UI-01, OTMG-UI-04, OTMG-UI-05, OTMG-UI-10, OTMG-UI-14 |
| `update_item` | R3 [BUG-2358] | OTMG-UI-16, OTMG-UI-17, OTMG-UI-18 |
| `update_item` | R4 | OTMG-UI-01 … OTMG-UI-09, OTMG-UI-22, OTMG-UI-25, OTMG-UI-28 |
| `update_item` | R4a [BUG-2349] | OTMG-UI-24, OTMG-UI-26, OTMG-UI-27 |
| `update_item` | R4a (just below) | OTMG-UI-25, OTMG-UI-28 |
| `update_item` | R4 [BUG-2363, BUG-2364] | OTMG-UI-19, OTMG-UI-20, OTMG-UI-21 |
| `update_item` | R5 | OTMG-UI-14 |
| `update_item` | R5 [BUG-1226] | OTMG-UI-15 |
| `update_item` | R6 [BUG-2358] | OTMG-UI-17 |
| `remove_item` | R1 | OTMG-RI-02, OTMG-RI-03, OTMG-RI-04 |
| `remove_item` | R2 | OTMG-RI-01, OTMG-RI-05 |
| `get_items` | R1 | OTMG-GI-01, OTMG-GI-02, OTMG-GI-03 |
| `get_items` | R2 [BUG-2366] | OTMG-GI-04, OTMG-GI-05, OTMG-GI-06 |
| `get_items` | reader writes nothing | OTMG-GI-07 |
