# Spec — `app/dao/workspace.py`

> **Status:** APPROVED (no questions; nothing open)
> **Source commit:** e48a092

> **Verified by running** (scripts `rd_h.py`, `rd_0.py`, `rd_3.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\refdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints, indexes, no trigger; every slug below; a keyword-only call; the two workspace-scoped base reads; a duplicate slug; `create` from `WorkspaceCreate`; the Python defaults; `update` of `settings`. **Not run:** anything over HTTP; two concurrent transactions.

## Review
No questions.

Checked and **not** a new line here: **HR-1, HR-2** — the slug is unique in the database (`ix_workspaces_slug`, a unique index) and `WorkspaceCreate` allows only lower-case letters, digits and single hyphens, so the case-sensitive compare cannot split one slug into two through the API. A race past `get_by_slug` hits the index and the API's integrity handler answers 409. **HR-4** — the table has no soft-delete column. **HR-5, HR-6, HR-7, HR-8** — one exact match on a unique column, so `.first()` has nothing to order and no `LIKE`. **HR-9, HR-10, HR-15** — this DAO writes nothing of its own. **HR-16** — this is the tenant table.

## Overview
`WorkspaceDAO` reads and writes the tenant table and adds one lookup by slug, used to refuse a taken slug when a workspace is made. Callers: `core/deps.py`, `WorkspaceManager`, `WorkspaceService`, `AuthService`, `ProjectManager`, `MobileUploadService` (all `get`, `WorkspaceService` also `update`). `WorkspaceManager.create_workspace` calls `get_by_slug` and builds the row itself. Nothing calls this DAO's `create`, `remove` or `get_multi`.

**Callables:** 1 specified · 2 not specified
**Externals to mock:** none. `created_at`, `updated_at` and `last_usage_reset_at` use `utcnow` from the model.
**Integration-only behavior:** none

**Model facts (table `workspaces`, class `app.models.workspace.Workspace`):** `slug` String(100) NOT NULL, unique index `ix_workspaces_slug`. `name` String(255) NOT NULL. `subscription_plan_id` NOT NULL, FK `subscription_plans.id`, no delete action. `settings` generic `JSON` NOT NULL, Python default `{}`. `subscription_status` default `'trial'`, `current_members_count` default `1`. Every default is Python's; the table has none but the `id` sequence. No `workspace_id`, no soft-delete column. Every workspace-owned table references this one with `ON DELETE CASCADE`.

**Notes for the test designer:** Use the module singleton `workspace_dao`. `make_workspace(db, slug="acme-co")` from `tests/unit/factories.py` makes a plan too. A slug with capitals can only be built this way: the schema refuses it.

## Not specified
- `workspace_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — `tests/unit/dao/base.spec.md`, apart from N1–N3. Base R7 and R5 cover `get_by_workspace` and `get_by_id_and_workspace` raising `AttributeError` on this model.

The checklist marks `get_by_slug` only; its four siblings were removed as dead code.

---

## `WorkspaceDAO.get_by_slug(db, *, slug)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `WorkspaceManager.create_workspace`)

**Purpose:** Find the workspace with this slug, if any.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `slug` | str | exact compare; keyword-only: a positional call raises `TypeError` |

**Returns:** the `Workspace`, or `None`.

**Rules:**
- **R1.** The workspace whose `slug` equals the argument is returned.
- **R2.** The compare is exact: `"ACME-CO"`, `" acme-co"`, `"acme-co "` find nothing for `acme-co`, and `"MiXeD"` is found only as typed.
- **R3.** No wildcard: `"acme%"` and `"acme_co"` find nothing.
- **R4.** An unknown slug, `""` and `None` return `None`, with no error.
- **R5.** No check of membership, owner or subscription state: any workspace is found. The result is not scoped, because the point is a check across all workspaces.

**Errors:** none.

**Side effects:** none

---

## Inherited methods, what is particular to this model
- **N1.** `create` with a `WorkspaceCreate` raises `TypeError`: `'owner_position' is an invalid keyword argument for Workspace`, nothing added. No code does this; the manager builds the row.
- **N2.** A second row with one slug raises `IntegrityError`, `.orig.pgcode == "23505"`, constraint `ix_workspaces_slug`.
- **N3.** `update` from a `WorkspaceUpdate` with `settings` replaces the whole value: `{"a": 1}` then `{"b": 2}` leaves `{"b": 2}`. `updated_at` moves, because the model's `onupdate` is Python's `utcnow`, so unlike a `now()` column it is later than `created_at` inside one test.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 13 | keyword-only parameter | Inputs |
| 15 | exact match on the unique column; `.first()`: row / `None` | R1, R2, R3, R4, R5 |
| 17 | module singleton | Not specified |
