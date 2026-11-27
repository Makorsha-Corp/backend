# Test cases — `app/utils/order_workflow_terminal.py`

> **Spec:** `tests/unit/utils/order_workflow_terminal.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 3 — re-run: spec unchanged since revision 2 (still APPROVED, source commit e48a092, Gap log G1 already applied); `order_workflow_terminal.verify.md` (PASS, 23/23 mutants killed) has no `case-missing` findings to address. No case added, removed or renumbered.
> **Previous revision:** 2 — spec Gap log G1: `OrderWorkflow.type` is a free string; conventions now use `'purchase'` / `'sales'` and gap 1 is closed. No case added, removed or renumbered.
> **Counts:** 31 cases · 31 expected-to-pass · 0 expected-to-fail (bugs) · 0 deferred

## Reviewer summary
- **Per callable:** `terminal_status_ids_by_workflow` 21 cases (0 bug) · `is_order_terminal` 10 cases (0 bug)
- **Notable design choices:**
  - Two workflows in one workspace use distinct `type` values `'purchase'` and `'sales'` (spec: `type` is a free string, only uniqueness per workspace matters). R10 is split into two cases (two qualifying workflows; one qualifying + one non-qualifying) to keep each failure readable.
  - R1 ("no query needed") is checked by result only (`{}` even though a qualifying workflow exists), not by counting queries — the spec phrases it as "result is the same regardless of what is in the database".
  - `is_order_terminal` R1/R2 cases use maps that would make a missing `None` check produce `True` (e.g. `{None: 14}` with `workflow_id=None`; `{7: None}` with `current_status_id=None`), so a dropped guard is caught.
  - Read-only side effect checked once (OWT-T-01): row re-read unchanged, workflow count unchanged.
- **Needs a decision:** None.

## Conventions for this module
- **IDs:** `OWT` = order_workflow_terminal; `T` = `terminal_status_ids_by_workflow`; `O` = `is_order_terminal`.
- **W1, W2** = two workspaces.
- **WF-A, WF-B** = order workflows in W1 with type `'purchase'` and `'sales'` respectively (`type` is a free string; only the unique `(workspace_id, type)` pair matters, neither helper reads it). **WF-C** = an order workflow in W2 (type `'purchase'`). Each has a non-null `name` (e.g. "PO flow", "SO flow"). `status_sequence` is given per case and stored as the exact JSON value shown (status ids are not required to exist as status rows).
- **MISSING** = an integer id that no `order_workflows` row has (e.g. max existing id + 1000).
- Externals mocked: none. Race simulations: none. Time: not mocked.
- `terminal_status_ids_by_workflow` is called as `terminal_status_ids_by_workflow(db, workspace_id=..., workflow_ids=...)`; `is_order_terminal` as `is_order_terminal(workflow_id=..., current_status_id=..., terminal_by_wf=...)` — keyword-only.
- Every `terminal_status_ids_by_workflow` case asserts the returned value is a `dict` and equals the exact dict shown (`==`, so extra keys fail).
- Every `is_order_terminal` case asserts the return with `is True` / `is False` and that `terminal_by_wf` equals a copy taken before the call (not modified).

## `terminal_status_ids_by_workflow`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| OWT-T-01 | R4, Side effects | happy | W1 has WF-A with `status_sequence` `[11, 12, 13, 14]` | call with `workspace_id=W1`, `workflow_ids=[WF-A.id]` | returns `{WF-A.id: 14}` (value is `int`); re-read WF-A from the database: `status_sequence == [11, 12, 13, 14]`, name/type/workspace unchanged; number of `order_workflows` rows in W1 still 1 | pass |
| OWT-T-02 | R1 | boundary | W1 has WF-A `[11, 12, 13, 14]` | call with `workspace_id=W1`, `workflow_ids=[]` | returns `{}` | pass |
| OWT-T-03 | R1 | boundary | W1 has WF-A `[11, 12, 13, 14]` | call with `workspace_id=W1`, `workflow_ids=[None, None]` | returns `{}` | pass |
| OWT-T-04 | R2 | boundary | W1 has WF-A `[11, 12, 13, 14]` | call with `workspace_id=W1`, `workflow_ids=[None, WF-A.id]` | returns `{WF-A.id: 14}` | pass |
| OWT-T-05 | R3 | boundary | W1 has WF-A `[11, 12, 13, 14]` | call with `workspace_id=W1`, `workflow_ids=[WF-A.id, WF-A.id]` | returns `{WF-A.id: 14}`; `len(result) == 1` | pass |
| OWT-T-06 | Inputs (iterated once; generator is fine) | happy | W1 has WF-A `[11, 12, 13, 14]` | call with `workspace_id=W1`, `workflow_ids=(x for x in [None, WF-A.id])` (a generator) | returns `{WF-A.id: 14}` | pass |
| OWT-T-07 | R5 | isolation | W1 has WF-A `[1, 2]`; W2 has WF-C `[3, 4]` | call with `workspace_id=W1`, `workflow_ids=[WF-A.id, WF-C.id]` | returns `{WF-A.id: 2}`; `WF-C.id` not a key; no exception | pass |
| OWT-T-08 | R5 | isolation | W1 has WF-A `[1, 2]`; W2 has WF-C `[3, 4]` | call with `workspace_id=W2`, `workflow_ids=[WF-A.id, WF-C.id]` | returns `{WF-C.id: 4}`; `WF-A.id` not a key | pass |
| OWT-T-09 | R6 | boundary | W1 has WF-A `[11, 12, 13, 14]` | call with `workspace_id=W1`, `workflow_ids=[MISSING]` | returns `{}`; no exception | pass |
| OWT-T-10 | R7 | boundary | W1 has WF-A with `status_sequence` `[]` | call with `workspace_id=W1`, `workflow_ids=[WF-A.id]` | returns `{}` | pass |
| OWT-T-11 | R4, R7 | boundary | W1 has WF-A with `status_sequence` `[5]` | call with `workspace_id=W1`, `workflow_ids=[WF-A.id]` | returns `{WF-A.id: 5}` | pass |
| OWT-T-12 | R8 | boundary | W1 has WF-A with `status_sequence` JSON object `{"a": 1}` | call with `workspace_id=W1`, `workflow_ids=[WF-A.id]` | returns `{}`; no exception | pass |
| OWT-T-13 | R8 | boundary | W1 has WF-A with `status_sequence` JSON string `"14"` | call with `workspace_id=W1`, `workflow_ids=[WF-A.id]` | returns `{}`; no exception | pass |
| OWT-T-14 | R9 | boundary | W1 has WF-A with `status_sequence` `[11, "14"]` | call with `workspace_id=W1`, `workflow_ids=[WF-A.id]` | returns `{}` | pass |
| OWT-T-15 | R9 | boundary | W1 has WF-A with `status_sequence` `[11, 14.0]` (last element stored as JSON float) | call with `workspace_id=W1`, `workflow_ids=[WF-A.id]` | returns `{}` | pass |
| OWT-T-16 | R9 | boundary | W1 has WF-A with `status_sequence` `[11, null]` | call with `workspace_id=W1`, `workflow_ids=[WF-A.id]` | returns `{}` | pass |
| OWT-T-17 | R9 (boolean note) | boundary | W1 has WF-A with `status_sequence` `[11, true]` | call with `workspace_id=W1`, `workflow_ids=[WF-A.id]` | returns a dict with exactly one key `WF-A.id`; its value `is True`; value `== 1` | pass |
| OWT-T-18 | R4 (earlier elements may be anything) | boundary | W1 has WF-A with `status_sequence` `["x", null, 14.5, 14]` | call with `workspace_id=W1`, `workflow_ids=[WF-A.id]` | returns `{WF-A.id: 14}` | pass |
| OWT-T-19 | R10, R5, R6, R2 | happy | W1 has WF-A `[1, 2, 3]` and WF-B `[4, 5]`; W2 has WF-C `[7, 8]` | call with `workspace_id=W1`, `workflow_ids=[WF-A.id, None, WF-B.id, WF-C.id, MISSING]` | returns `{WF-A.id: 3, WF-B.id: 5}` (exactly two keys) | pass |
| OWT-T-20 | R10, R7 | happy | W1 has WF-A `[1, 2, 3]` and WF-B `[]` | call with `workspace_id=W1`, `workflow_ids=[WF-A.id, WF-B.id]` | returns `{WF-A.id: 3}`; `WF-B.id` not a key | pass |
| OWT-T-21 | R11 | boundary | W1 has WF-A `[1, 2, 3]` and WF-B `[4, 5]` | call with `workspace_id=W1`, `workflow_ids=[WF-A.id]` | returns `{WF-A.id: 3}`; `WF-B.id` not a key | pass |

## `is_order_terminal`

No database needed (pure).

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| OWT-O-01 | R4 | happy | map `{7: 14}` | `workflow_id=7`, `current_status_id=14` | returns `True`; map still `{7: 14}` | pass |
| OWT-O-02 | R5 | boundary | map `{7: 14}` | `workflow_id=7`, `current_status_id=15` | returns `False`; map still `{7: 14}` | pass |
| OWT-O-03 | R5 (earlier status of same workflow) | boundary | map `{7: 14}` (workflow sequence would be `[11, 12, 13, 14]`) | `workflow_id=7`, `current_status_id=11` | returns `False` | pass |
| OWT-O-04 | R1 | boundary | map `{None: 14, 7: 14}` | `workflow_id=None`, `current_status_id=14` | returns `False` (a `None` key in the map must not make it terminal); map unchanged | pass |
| OWT-O-05 | R2 | boundary | map `{7: 14}` | `workflow_id=7`, `current_status_id=None` | returns `False`; map unchanged | pass |
| OWT-O-06 | R2, R7 | boundary | map `{7: None}` | `workflow_id=7`, `current_status_id=None` | returns `False` (a `None` status never matches, even a `None` map value); map unchanged | pass |
| OWT-O-07 | R3 | boundary | map `{7: 14}` | `workflow_id=8`, `current_status_id=14` | returns `False`; map still `{7: 14}` (no key 8 added) | pass |
| OWT-O-08 | R6 | boundary | map `{0: 5}` | `workflow_id=0`, `current_status_id=5` | returns `True` | pass |
| OWT-O-09 | R6 | boundary | map `{7: 0}` | `workflow_id=7`, `current_status_id=0` | returns `True` | pass |
| OWT-O-10 | R7 | boundary | map `{7: None}` | `workflow_id=7`, `current_status_id=14` | returns `False`; map unchanged | pass |

## Deferred to other specs
None.

## Spec gaps
None. (Previous gap 1, allowed `OrderWorkflow.type` values, closed by spec Gap log G1.)

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `terminal_status_ids_by_workflow` | R1 | OWT-T-02, OWT-T-03 |
| `terminal_status_ids_by_workflow` | R2 | OWT-T-04, OWT-T-06, OWT-T-19 |
| `terminal_status_ids_by_workflow` | R3 | OWT-T-05 |
| `terminal_status_ids_by_workflow` | R4 | OWT-T-01, OWT-T-11, OWT-T-18 |
| `terminal_status_ids_by_workflow` | R5 | OWT-T-07, OWT-T-08, OWT-T-19 |
| `terminal_status_ids_by_workflow` | R6 | OWT-T-09, OWT-T-19 |
| `terminal_status_ids_by_workflow` | R7 | OWT-T-10, OWT-T-11, OWT-T-20 |
| `terminal_status_ids_by_workflow` | R8 | OWT-T-12, OWT-T-13 |
| `terminal_status_ids_by_workflow` | R9 | OWT-T-14, OWT-T-15, OWT-T-16, OWT-T-17 |
| `terminal_status_ids_by_workflow` | R10 | OWT-T-19, OWT-T-20 |
| `terminal_status_ids_by_workflow` | R11 | OWT-T-21 |
| `terminal_status_ids_by_workflow` | Inputs: generator iterated once | OWT-T-06 |
| `terminal_status_ids_by_workflow` | Errors: none | (all cases assert no exception implicitly; OWT-T-07, -09, -12, -13 explicitly) |
| `terminal_status_ids_by_workflow` | Side effects: none (read-only) | OWT-T-01 |
| `is_order_terminal` | R1 | OWT-O-04 |
| `is_order_terminal` | R2 | OWT-O-05, OWT-O-06 |
| `is_order_terminal` | R3 | OWT-O-07 |
| `is_order_terminal` | R4 | OWT-O-01 |
| `is_order_terminal` | R5 | OWT-O-02, OWT-O-03 |
| `is_order_terminal` | R6 | OWT-O-08, OWT-O-09 |
| `is_order_terminal` | R7 | OWT-O-06, OWT-O-10 |
| `is_order_terminal` | Inputs: map not modified | OWT-O-01, -02, -04, -05, -06, -07, -10 |
| `is_order_terminal` | Errors: none / Side effects: none | all OWT-O cases |
