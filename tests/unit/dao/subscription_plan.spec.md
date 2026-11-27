# Spec — `app/dao/subscription_plan.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** O1 is the owner's answer (owner's answers relayed by the coordinator, 2026-11-02): BUG-1224, which supersedes BUG-1212, since the index leaves one candidate. **Delegated:** Q1 `remove`, decided by Claude under the reviewer's delegation (2026-11-02); none of that is the owner's own answer. Added by running (`ar_1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\refdao\`, rolled back): a temporary partial index refuses a second active default with 23505 and allows an inactive default and a non-default plan.

> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Base behaviour is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Verified by running** (scripts `rd_h.py`, `rd_0.py`, `rd_3.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\refdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints, indexes, no trigger, the one referencing table; no default plan, one, an inactive one, two; **two default plans: the result changed from the lower to the higher `id` after the lower row was updated, and back after the higher was**; both inactive; `get_by_name` with every value below; an inactive plan by name; a duplicate name; prices of `0.125` and `-1.005` stored as `0.13` and `-1.01`. **Not run:** anything over HTTP; the intended behavior of BUG-1212.

## Review
> All answered 2026-11-02.

| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| O1 | Nothing stops two plans being the default | bug — partial unique index | owner |
| Q1 | The lookup of a plan by name has no caller | remove | Claude, delegated |

### House-rule violations — applied automatically

- **HR-6** `get_default_plan` R5 — a top-1 with no `ORDER BY`. With two active default plans the plan a new workspace gets depends on physical row order (verified: it flipped after an unrelated update). Intended: the lowest `id`.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1212 (pattern `unordered-pagination`), **superseded by BUG-1224**: O1's index leaves one candidate, so `.first()` needs no order, as on any unique column. Rules: `get_default_plan` R5.

Checked and **not** a new line here: **HR-4** — no soft-delete column; `is_active` is not one. **HR-15** — prices are never computed here; the `Numeric(10, 2)` columns round half away from zero (verified). **HR-5, HR-7, HR-8, HR-9, HR-10, HR-16** — no list, no `LIKE`, no write of its own, no workspace.

### New questions

### O1. Nothing stops two plans being the default — 🐞 BUG-1224
**Background:** `is_default` marks the plan every new workspace starts on when none is chosen, with its limits (members, storage, orders, factories, machines, projects) and its price. The seed marks one plan out of three. No endpoint writes plans, and `is_default` is in no plan schema, so today a second default can only come from the database or a changed seed.
**What happens today:** The table has no constraint on `is_default`. Two active default plans can exist; which one a new workspace gets is then BUG-1212's choice (lowest `id`, once fixed), with no error and nothing logged. With no active default, `create_workspace` raises `ValueError("No default subscription plan found")`.
**Example:** Someone marks "Pro" as default in the database and forgets "Free". Every new workspace still gets "Free", lowest `id`, and nobody is told; delete "Free"'s flag and every workspace gets "Pro".
**Rules affected:** `get_default_plan` R5 (BUG-1212 picks the lowest `id` only until the index exists)
**Suggested answer:** `bug — a partial unique index allows only one row with is_default and is_active both true`. It changes no plan or price, and a fix would have to check the live table first. Alternative: `intended — the seed is the only writer, the lowest id is enough`.
**Answer:** bug — partial unique index
**Resolution:** owner's answer 2026-11-02: 🐞 BUG-1224 (pattern `python-only-uniqueness`). A partial unique index allows one row with `is_default` and `is_active` both true. It changes no plan or price; the live table must be checked for a second default before it is applied. Rules: `get_default_plan` R5.

### Q1. The lookup of a plan by name has no caller — ✅ remove
**Background:** `get_by_name` finds a plan by its unique name. A search of `app/`, `tests/` and `scripts/` finds no call. Its sibling `get_active_plans` was removed as dead code. Plans are referred to by id.
**What happens today:** The method works (verified) and nothing reaches it.
**Example:** No request or job ever runs it.
**Rules affected:** `get_by_name` (all)
**Suggested answer:** `remove`. If it goes, its section and the Branch map rows go too. Not money: it only reads.
**Answer:** remove
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): moved to Not specified, section and Branch map rows deleted, added to `docs/testing/dead-code-removal-checklist.md`. No bug.

## Overview
`SubscriptionPlanDAO` reads the global list of plans, which belongs to no workspace, and finds the default plan. Callers: `WorkspaceManager.create_workspace` (`get`, `get_default_plan`) and its two limit readers (`get`). `AuthService` holds a reference and calls nothing. It writes nothing of its own.

**Callables:** 1 specified · 3 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `subscription_plans`, class `app.models.subscription_plan.SubscriptionPlan`):** `name` String(100) NOT NULL, unique index `ix_subscription_plans_name`. `is_default`, `is_custom`, `is_active` Boolean NOT NULL, Python defaults `False`, `False`, `True`, with no constraint between them today (BUG-1224 adds one). `currency` default `'USD'`, `features` default `[]`, limits default 5, 1000, 100, 2, 10, 5 (`-1` means unlimited, by comment). `price_monthly`, `price_yearly` `Numeric(10, 2)` nullable. No database default but the `id` sequence. No `workspace_id`, no soft-delete column. One table references it: `workspaces.subscription_plan_id`, no delete action.

**Notes for the test designer:**
- Use the module singleton `subscription_plan_dao`. Build plans with `make_subscription_plan(db, name=…, is_default=…, is_active=…)` from `tests/unit/factories.py`, which leaves `is_default` `False`.
- The table is global but has no committed rows in `marker_test`, and tests are rolled back, so the "no default" case works as written. If that ever stops being true, set existing rows' `is_default` to `False` inside the test.
- R5 is written to the index: strict xfail on BUG-1224. Call in `with db.begin_nested():`.

## Not specified
- `SubscriptionPlanDAO.get_by_name` — dead code, to be removed (reviewer).
- `subscription_plan_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — `tests/unit/dao/base.spec.md`. Only `get` has a caller. `get_by_workspace` and `get_by_id_and_workspace` raise `AttributeError` on this model (base R7, R5).

---

## `SubscriptionPlanDAO.get_default_plan(db)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `WorkspaceManager.create_workspace`, when no plan is chosen)

**Purpose:** The plan a new workspace starts on.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |

**Returns:** the plan, or `None`.

**Rules:**
- **R1.** The plan with `is_default` true and `is_active` true is returned.
- **R2.** A plan with `is_default` false is never returned, even when it is the only active one.
- **R3.** An inactive default plan is not returned: with an active default as well, that one is; with none, `None`.
- **R4.** No plans at all, or no active default, returns `None`, with no error.
- **R5.** [BUG-1224] (O1) At most one plan can be default and active, so the query has one candidate: storing a second raises `IntegrityError`, `.orig.pgcode == "23505"`. A second default that is inactive, and any non-default plan, are stored. *(Today: two are stored, and the result follows physical row order. Verified: it changed after an update.)*

**Errors:** none. **Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 21 | `is_default` AND `is_active` | `get_default_plan` R1, R2, R3 |
| 22 | `.first()`: row / `None`; no `ORDER BY` | `get_default_plan` R4, R5 |
| 25 | module singleton | Not specified |
