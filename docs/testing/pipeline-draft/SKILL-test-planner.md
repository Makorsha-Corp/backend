---
name: test-planner
description: >
  Produce a structured unit-test PLAN for one source file under app/ (a manager,
  service, dao, util, core, or integration module). Reads the target, its direct
  dependencies, and the testing guide; classifies every callable by shape and by
  writes-vs-reads; emits a per-callable test-case table to
  tests/unit/<layer>/<module>.plan.md. Writes NO test code. Use when the by-layer
  checklist (docs/testing/unit-test-checklist-by-layer.md) has an untested file
  and you want the plan before implementation.
---

# Test Planner

You turn ONE source file into a reviewable test plan. You do not write tests.

## Inputs

- `$FILE` — path to the target, e.g. `app/managers/department_manager.py`.

## Procedure

### 1. Gather context

Read, in this order:

1. `$FILE` in full.
2. Every first-party module `$FILE` imports: its DAO(s), model(s), Pydantic
   schema(s), and any `app/utils/*` helpers. Note their real signatures and
   return types — you will reference them in the plan.
3. `docs/testing/unit-test-guide.md` — the layer + function-shape playbook. The
   plan MUST follow it.
4. `tests/conftest.py` and `tests/factories/` — know what fixtures and factories
   already exist. Do not invent new ones unless necessary; if you must, list them
   under "New fixtures required".
5. The file's section in `docs/testing/unit-test-checklist-by-layer.md`. Any
   callable flagged `⚠️ [possibly unused]` — do NOT plan tests for it. List it
   under "Skipped (flagged unused)" and move on.

### 2. Classify each callable

For every method / function defined in `$FILE` (including `_private` helpers;
exclude `__init__` unless it contains logic):

| Axis | Values |
|---|---|
| Shape | `create` · `update` · `delete`/`soft-delete` · `get`/`get-or-404` · `list`/`search` (+pagination) · `state-transition` (confirm/void/approve/reopen) · `recalculate`/`compute` · `validator`/`guard` · `event-log` · `mapper`/`enrich` · `helper` |
| Persistence | `writes` (calls a DAO create/update/delete, or mutates + flushes) · `reads` (only queries) · `pure` (no session use) |
| Collaborators | list the DAOs / managers / utils it calls |
| Externals | Cloudinary, SSLCommerz, notification dispatch, email, `utcnow`, filesystem — anything that must be mocked |

`writes` and `reads` callables → real DB session fixture (`db`).
`pure` callables → no fixture.
Mock ONLY externals, never the session, never the DAO (unless the guide's
entry for that shape says otherwise).

### 3. Write the plan

Create `tests/unit/<layer>/<module>.plan.md` with this structure:

```
# Test plan — <module path>

## Summary
- N callables: X to test, Y skipped (unused), Z n/a (trivial)
- Fixture: `db` (real session) | none
- Externals to mock: <list or "none">
- New fixtures/factories required: <list or "none">

## Skipped
- `Class.method` — flagged unused in checklist (MAK-110 candidate)

## n/a
- `Class.__init__` — assigns collaborators, no logic

## <Class.method>  — shape: <shape>, persistence: <writes|reads|pure>
Behavior: <2–4 sentences: what it does, what it returns, what it raises>
Collaborators: <daos/managers/utils>
Setup needs: <factory rows to insert before the call>

| # | Case | Setup | Action | Expected |
|---|------|-------|--------|----------|
| 1 | happy path | 1 workspace, no existing dept | create_department(valid) | returns Department; row in db; workspace_id + created_by stamped |
| 2 | duplicate name | existing dept "Sales" | create_department(name="Sales") | raises HTTPException 409; no new row |
| ... |

Edge cases to cover: <bullet list — every branch, every raise, boundary inputs>
Suspicious / bugs noticed: <anything that looks wrong — do NOT fix, just note>
```

### 4. Rules

- One row in the case table per distinct behavior. Every `if`/`raise`/early-return
  in the source must map to at least one case.
- Assertions must be on **real return values or DB state**, never "mock was
  called" alone. If a case can only be checked via a collaborator call, say which
  argument matters and why.
- Do not plan tests that assert private call order or implementation details that
  a valid refactor would change.
- If `$FILE` mixes `writes` and `pure` callables, note it — the executor will
  split fixtures per test, that's fine.
- If a callable uses Postgres-only SQL (JSONB query, `DISTINCT ON`, `pg_trgm`,
  `pg_notify`), mark it `integration-only` and skip — it belongs to MAK-108.
- Output ONLY the plan file. End your turn with its path and the summary block.
