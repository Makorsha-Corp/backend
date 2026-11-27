# Spec — `app/utils/order_workflow_terminal.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

No questions.

## Overview
Two small helpers that decide whether an order (purchase order today) has reached
the end of its workflow. An order workflow (`order_workflows` row) holds an
ordered list of status ids, `status_sequence`; the **last** id in that list is
the workflow's terminal ("done") status. `terminal_status_ids_by_workflow` loads
the terminal status id of each requested workflow within one workspace, and
`is_order_terminal` checks one order's current status against that map. The only
caller is `InventoryManager` (incoming-stock summary per factory), which skips
purchase orders whose status is terminal. Invariant protected: workflows of
another workspace never contribute a terminal status.

**Callables:** 2 specified · 0 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Notes for the test designer:**
- `OrderWorkflow` columns: `id`, `workspace_id` (FK workspaces, NOT NULL),
  `name` (NOT NULL), `type` (NOT NULL), `description`, `status_sequence`
  (NOT NULL; stored as JSON text, read back as whatever JSON value was stored),
  `allowed_reverts_json`. Unique `(workspace_id, type)` — two workflows in one
  workspace need different `type` values. The model has no soft-delete column.
- `OrderWorkflow.type` is a free `String` column (no enum, no check constraint;
  the Pydantic schema is plain `str` too). The only value the app itself uses is
  `'purchase'` (the purchase-order workflow seeded per workspace); any other
  distinct strings (e.g. `'sales'`, `'other'`) are valid for tests. Neither
  helper looks at `type`; it only matters for satisfying the unique
  `(workspace_id, type)` constraint when one workspace needs several workflows.
- `status_sequence` elements are meant to be status ids but the column does not
  enforce element type or existence; tests may store arbitrary JSON lists
  (e.g. `[1, "x"]`, `[]`) or a non-list JSON value (e.g. `{"a": 1}`) directly on
  the model to reach the defensive branches.
- `is_order_terminal` is pure; no database needed.

## Not specified
(none)

---

## `terminal_status_ids_by_workflow(db, *, workspace_id, workflow_ids)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `InventoryManager` incoming-stock summary)

**Purpose:** For each requested workflow in the workspace, find its terminal status id (the last entry of its status sequence).

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | Open session. |
| `workspace_id` | `int` | Only workflows of this workspace are considered. |
| `workflow_ids` | iterable of `int` (may contain `None`) | Workflow ids to look up. Iterated exactly once (a generator is fine). `None` entries are ignored; duplicates collapse. |

**Returns:** a new `dict` mapping workflow id → terminal status id (`int`). Contains only workflows that were found and have a usable terminal status. Never `None`.

**Rules:**
- **R1.** When `workflow_ids` is empty, or contains only `None` values, the result is `{}` (no database query is needed; result is the same regardless of what is in the database).
- **R2.** `None` entries in `workflow_ids` are ignored; the other ids are still resolved (e.g. `[None, 7]` → result for workflow 7 only).
- **R3.** Repeated ids are treated as one (e.g. `[7, 7]` → one key `7`).
- **R4.** For a found workflow whose `status_sequence` is a non-empty list whose last element is an integer, the result maps the workflow's id to that last element (e.g. sequence `[11, 12, 13, 14]` → `{wf.id: 14}`). Only the last element matters; earlier elements may be anything.
- **R5.** Workspace isolation: a requested id that belongs to a workflow of **another** workspace is absent from the result (no error).
- **R6.** A requested id with no workflow row at all is absent from the result (no error).
- **R7.** A workflow whose `status_sequence` is an empty list is absent from the result.
- **R8.** A workflow whose `status_sequence` is not a list (e.g. a JSON object or a string) is absent from the result (no error).
- **R9.** A workflow whose sequence's last element is not an integer (e.g. a string `"14"`, a float `14.0`, or `null`) is absent from the result, even if earlier elements are integers. (A JSON boolean counts as an integer here: a last element `true` is kept and returned as `True`, which compares equal to status id `1`.)
- **R10.** Several requested workflows are resolved independently in one call: each qualifying workflow gets its own entry; non-qualifying ones (R5–R9) are simply missing.
- **R11.** Only workflows whose id was requested appear; other workflows of the same workspace are not included.

**Errors:** none raised by this function.

**Side effects:** none (read-only query).

---

## `is_order_terminal(*, workflow_id, current_status_id, terminal_by_wf)`
**Shape:** compute
**Persistence:** pure
**Visibility:** public (used by: `InventoryManager` incoming-stock summary)

**Purpose:** Decide whether an order sits in its workflow's terminal status.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workflow_id` | `int \| None` | The order's workflow id. |
| `current_status_id` | `int \| None` | The order's current status id. |
| `terminal_by_wf` | `dict[int, int]` | Map as produced by `terminal_status_ids_by_workflow`. Not modified. |

**Returns:** `bool`.

**Rules:**
- **R1.** `workflow_id` is `None` → `False` (an order without a workflow is never terminal).
- **R2.** `current_status_id` is `None` → `False`.
- **R3.** `workflow_id` not a key of `terminal_by_wf` → `False`.
- **R4.** `workflow_id` in the map and `current_status_id` equals the mapped id → `True`.
- **R5.** `workflow_id` in the map and `current_status_id` differs from the mapped id → `False` (including when the status is an earlier status of the same workflow).
- **R6.** Id `0` is a real value, not "missing": `workflow_id=0` with `{0: 5}` and `current_status_id=5` → `True`; `current_status_id=0` with mapped id `0` → `True`.
- **R7.** A map value of `None` (not produced by the loader, but possible for a hand-built map) → `False`.

**Errors:** none.

**Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 16 | comprehension filters `wid is not None`; set dedup | `terminal_status_ids_by_workflow` R2, R3 |
| 17 | `not wf_ids` → return `{}` | `terminal_status_ids_by_workflow` R1 |
| 20–26 | query filtered by workspace and id set | `terminal_status_ids_by_workflow` R5, R6, R11 |
| 29 | loop over zero / one / many workflows | `terminal_status_ids_by_workflow` R5, R6, R10 |
| 30 | `status_sequence or []` (falsy sequence) | `terminal_status_ids_by_workflow` R7 |
| 31 | `isinstance(seq, list)` false | `terminal_status_ids_by_workflow` R8 |
| 31 | `len(seq) > 0` false | `terminal_status_ids_by_workflow` R7 |
| 33 | `isinstance(last, int)` true / false | `terminal_status_ids_by_workflow` R4, R9 |
| 44 | `workflow_id is None` | `is_order_terminal` R1 |
| 44 | `current_status_id is None` | `is_order_terminal` R2 |
| 46–47 | `last_id is not None` false (missing key / `None` value) | `is_order_terminal` R3, R7 |
| 47 | `current_status_id == last_id` true / false | `is_order_terminal` R4, R5, R6 |

## Gap log
- G1 (order_workflow_terminal.cases.md gap 1) — Fact — Overview notes now state `OrderWorkflow.type` is a free string (no enum or check constraint); the app uses only `'purchase'`; any distinct strings satisfy the unique `(workspace_id, type)` constraint; `type` has no effect on either helper.
