# Test cases — `app/dao/subscription_plan.py`

> **Spec:** `tests/unit/dao/subscription_plan.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open). Q1 was decided by Claude under the reviewer's delegation; O1 is the owner's answer.
> **Revision:** 1 — the spec did not change. Additive, from `subscription_plan.verify.md` (case-missing Finding 1; recipe R-1): SBP-GD-12. Conventions gain the `session:` line. No existing Given, When, Then or ID changed, none retired.
> **Counts:** 12 cases · 11 expected-to-pass · 1 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `get_default_plan` 12 (1 bug).
- **Depth:** lighter target (skill step 1a). One plain filtered read; no stock, order or money is written, and prices are not computed here.
- **Expected-to-fail:** BUG-1224 1 (SBP-GD-07, strict). The spec writes R5 to the index, so there is no order card: BUG-1212 is superseded, one candidate has nothing to order.
- **Commit spies:** none. The method only reads; no inherited writer has a caller here.
- **Notable design choices:**
  - Every filter negative puts the wrong row first in `id` order: GD-01, GD-03. A filter on `is_default` alone, or `.first()` on the table, fails there.
  - No pass card holds two active defaults, so none breaks when the index arrives.
  - GD-05 counts the table, so a committed plan in `marker_test` fails it loudly and not by accident.
  - GD-08 and GD-09 call `make_subscription_plan` as the When: R5 is about what can be stored, and they stay green with the index.
  - No `Author:` lines. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `SBP` = `app/dao/subscription_plan.py`. `GD` get_default_plan.

**Actors and fixed values.**
- `dao` = the singleton `subscription_plan_dao` (`from app.dao.subscription_plan import subscription_plan_dao`). `db` = the test's real database session. `get_default_plan` takes only `db`. `result` = what the When call returns.
- `SubscriptionPlan` = `app.models.subscription_plan.SubscriptionPlan`. `make_subscription_plan` = `tests/unit/factories.py`.

**Externals.** None. Nothing is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from the defaults below. A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.
- **plan** = `make_subscription_plan(db, name=…)`: `is_default False`, `is_active True` unless the card lists them. No plan exists unless the card's Given lists it. The table holds no committed rows and tests are rolled back. **Never** build two plans with `is_default True` and `is_active True`, except in the card about exactly that: BUG-1224's index would make the Given fail.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line). **unchanged(X) except `c`, …** = the same, leaving out the columns named.
- **nothing written** = the number of `subscription_plans` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P after the call, on the object itself. `pending: len(db.new) == 1` checks that P is the only object waiting in the session.
- A `session:` line is a check on the session object.
- `raises: IntegrityError` = `sqlalchemy.exc.IntegrityError`. Wrap the When: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on it.

**Race simulations.** None in this module.

## `SubscriptionPlanDAO.get_default_plan`

### SBP-GD-01 — returns the active default plan, not the first plan
- **Rules:** `get_default_plan` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = plan `name "Starter"`.
2. B = plan `name "Free"`, `is_default True`.

**When**
- `result = dao.get_default_plan(db)`.

**Then**
1. returns: `isinstance(result, SubscriptionPlan)`.
2. returns: `result.id == B.id`.
3. returns: `result.name == "Free"`.
4. returns: `result.is_default is True`, `result.is_active is True`.

### SBP-GD-02 — the only active plan is not returned when it is not the default
- **Rules:** `get_default_plan` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = plan `name "Starter"`.

**When**
- `result = dao.get_default_plan(db)`.

**Then**
1. returns: `result is None`.

### SBP-GD-03 — an inactive default is passed over for the active one
- **Rules:** `get_default_plan` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = plan `name "Old"`, `is_default True`, `is_active False`.
2. B = plan `name "Free"`, `is_default True`.

**When**
- `result = dao.get_default_plan(db)`.

**Then**
1. returns: `result.id == B.id`.

### SBP-GD-04 — an inactive default alone returns None
- **Rules:** `get_default_plan` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = plan `name "Old"`, `is_default True`, `is_active False`.

**When**
- `result = dao.get_default_plan(db)`.

**Then**
1. returns: `result is None`.

### SBP-GD-05 — no plans at all returns None
- **Rules:** `get_default_plan` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No `subscription_plans` row exists.

**When**
- `result = dao.get_default_plan(db)`.

**Then**
1. returns: `result is None`.
2. count: `subscription_plans` has exactly 0 rows.

### SBP-GD-06 — plans, but no active default, return None
- **Rules:** `get_default_plan` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = plan `name "Starter"`.
2. B = plan `name "Old"`, `is_default True`, `is_active False`.

**When**
- `result = dao.get_default_plan(db)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(A).
3. unchanged: unchanged(B).

### SBP-GD-07 — a second active default is refused
- **Rules:** `get_default_plan` R5 [BUG-1224]
- **Kind:** bug
- **Expect:** xfail BUG-1224
- **Fails today on:** Then 1 (no error is raised: two active default plans are stored)

**Given**
1. A = plan `name "Free"`, `is_default True`.

**When**
- `make_subscription_plan(db, name="Pro", is_default=True)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError` on flush.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `subscription_plans` has exactly 1 row with `is_default` and `is_active` both true.
4. unchanged: unchanged(A).

### SBP-GD-08 — a second default that is inactive is stored
- **Rules:** `get_default_plan` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = plan `name "Free"`, `is_default True`.

**When**
- `result = make_subscription_plan(db, name="Old", is_default=True, is_active=False)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `is_default is True`, `is_active is False`.
3. unchanged: unchanged(A).

### SBP-GD-09 — a plan that is not the default is stored next to the default
- **Rules:** `get_default_plan` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = plan `name "Free"`, `is_default True`.

**When**
- `result = make_subscription_plan(db, name="Pro")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `is_default is False`, `is_active is True`.
3. unchanged: unchanged(A).

### SBP-GD-10 — writes nothing: a pending default stays pending and is not returned
- **Rules:** `get_default_plan` R4, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = plan `name "Starter"`.
2. `P = SubscriptionPlan(name="Pending", display_name="Pending", is_default=True, is_active=True)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_default_plan(db)`.

**Then**
1. returns: `result is None`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. nothing written: nothing written.
6. unchanged: unchanged(A).
7. statement: `written == []`.

### SBP-GD-11 — writes nothing: a read that finds its row leaves the session as it was
- **Rules:** `get_default_plan` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = plan `name "Free"`, `is_default True`.
2. `P = SubscriptionPlan(name="Pending", display_name="Pending")`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_default_plan(db)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. nothing written: nothing written.
5. statement: `written == []`.

### SBP-GD-12 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_default_plan` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = plan `name "Free"`, `is_default True`.
2. B = plan `name "Starter"`.
3. `B.display_name = "Edited"` (not flushed).

**When**
- `result = dao.get_default_plan(db)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_default_plan` R4 — no active default raises `ValueError("No default subscription plan found")` | `WorkspaceManager.create_workspace` | This DAO returns `None`; the refusal is the manager's. |
| BUG-1212 (HR-6) — superseded by BUG-1224 | this file, SBP-GD-07 | One candidate under the index; no order card. Nothing left to test elsewhere. |
| BUG-1224 — the live table is checked for a second default before the index goes on | the migration | Not a unit test. |
| `get_by_name` | dead code, on `docs/testing/dead-code-removal-checklist.md` | Removed from the spec (Q1). No card. |
| Generic behavior of inherited methods, `get` the only one with a caller | `tests/unit/dao/base.spec.md` / `base.cases.md` | `get_by_workspace`, `get_by_id_and_workspace` raise `AttributeError` here (base R7, R5). |
| Module singleton `subscription_plan_dao` | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Model facts | **Money.** `price_monthly`, `price_yearly` round half away from zero in the column (`0.125` → `0.13`, verified). The spec states it as a fact, under HR-15, not as a rule. | No card: this DAO never writes a price, so the rounding is the column's. |
| 2 | `get_default_plan` R5 | Gives no constraint name, and the index does not exist yet. | SBP-GD-07 asserts the code only. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_default_plan` | Returns | SBP-GD-01 |
| `get_default_plan` | R1 | SBP-GD-01 |
| `get_default_plan` | R2 | SBP-GD-02 |
| `get_default_plan` | R3 | SBP-GD-03, SBP-GD-04 |
| `get_default_plan` | R4 | SBP-GD-05, SBP-GD-06, SBP-GD-10 |
| `get_default_plan` | R5 | SBP-GD-08, SBP-GD-09 |
| `get_default_plan` | R5 [BUG-1224] | SBP-GD-07 |
| `get_default_plan` | Side effects | SBP-GD-10, SBP-GD-11, SBP-GD-12 |
