# Spec — `app/dao/work_order_completer.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** No owner answer in this round. **Delegated:** P1 and P2 of `tests/unit/dao/work_order_assignee.spec.md` apply here unchanged, and P3 below is accepted as suggested, all decided by Claude under the reviewer's delegation (2026-11-03). None of them is the owner's own answer.

> **Shared with `work_order_assignee`.** This DAO is a line-for-line copy of `WorkOrderAssigneeDAO` over `work_order_completers`. **Every rule, the Review (P1, P2), the Notes for the test designer and the Branch map of `tests/unit/dao/work_order_assignee.spec.md` apply here as written**, with the names below substituted, except `get_user_ids_by_order` (P3). Only what differs is stated here. Base behaviour is in `tests/unit/dao/base.spec.md`.
>
> **Verified by running:** the same script `v_wo.py` (harness `h.py`, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attdao\`) looped over both DAOs; every check of the assignee spec gave the same result here. Nothing committed. **Read, not run:** the callers (`grep` of `work_order_completer_dao` in `app/`, `tests/`, `scripts/`).

## Review
> All answered; applied 2026-11-03.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | As assignee P1: saving rewrites the rows | intended | Claude, delegated |
| P2 | As assignee P2: a deleted order's completers are still read | intended | Claude, delegated |
| P3 | `get_user_ids_by_order` has no caller on this DAO | remove | Claude, delegated |

No house-rule violations (as the assignee spec).

**What differs here, checked for each decision:**
- **P1** — the save happens once, when the order is completed (`WorkOrderManager` completion, `completer_ids` from `_resolve_completion_workers`); no stamp, no counter. Same answer.
- **Logs are history** — completers are the record of who did the work. Nothing in this DAO removes them after completion except `replace_for_order` itself; a hard delete of a profile also does (ON DELETE CASCADE; FU-1).

### P3. `get_user_ids_by_order` has no caller — 🗑️ remove
**Background:** The completer DAO copies all three assignee methods. A search of `app/`, `tests/` and `scripts/` finds `work_order_completer_dao.replace_for_order` (completion) and `.get_user_ids_by_orders` (list responses) only; the single-order read is used on the assignee DAO alone.
**What happens today:** It works when called directly (verified with the assignee checks), but nothing reaches it.
**Example:** No API request reads one order's completers through it; the work order response gets them from the batch read.
**Rules affected:** `get_user_ids_by_order` (whole method)
**Answer:** remove — per the subscription plan DAO precedent: no caller, dead code
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): moved to **Not specified**, listed in `docs/testing/dead-code-removal-checklist.md` (`app/dao/work_order_completer.py:33`). Not a bug — no BUG ID.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Work order manager** (completion) | Whether a completed order can be completed again, which would replace its completers, is the manager's state check (not looked at here). A hard delete of a profile removes its completer rows on every order (not searched for here). | reading the callers |

## Overview
`WorkOrderCompleterDAO` keeps `work_order_completers`, the workers who actually completed a work order, set when it is finished. Callers: `WorkOrderManager` completion (`replace_for_order`), `WorkOrderService` list responses (`get_user_ids_by_orders`, per workspace). It flushes, never commits, and takes no lock.

**Callables:** 2 specified (by reference) · 2 not specified
**Externals to mock:** none.
**Integration-only behavior:** none.

**Substitutions** (everything else as `work_order_assignee.spec.md`):
| Assignee spec | Here |
|---|---|
| `WorkOrderAssigneeDAO`, `work_order_assignee_dao` | `WorkOrderCompleterDAO`, `work_order_completer_dao` |
| table `work_order_assignees`, model `app.models.work_order_assignee.WorkOrderAssignee` | table `work_order_completers`, model `app.models.work_order_completer.WorkOrderCompleter` |
| unique constraint `uq_wo_assignee_wo_user` | `uq_wo_completer_wo_user` (same columns `(work_order_id, user_id)`, without `workspace_id`) |
| relationship `WorkOrder.assignee_links` | `WorkOrder.completer_links` |
| caller of `replace_for_order`: `_sync_assignees_from_text` | the completion path in `WorkOrderManager` (after `wo.status = COMPLETED`) |

## Not specified
- `WorkOrderCompleterDAO.get_user_ids_by_order` — dead code, to be removed (decided by Claude under the reviewer's delegation (2026-11-03); P3).
- `work_order_completer_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — no caller on this DAO; base spec.

---

## `WorkOrderCompleterDAO.get_user_ids_by_orders(db, *, work_order_ids, workspace_id)`
Rules R1–R6, Errors, Side effects: as the same-named section of `tests/unit/dao/work_order_assignee.spec.md`, with the substitutions above.

## `WorkOrderCompleterDAO.replace_for_order(db, *, work_order_id, workspace_id, user_ids)`
Rules R1–R8, Errors, Side effects: as the same-named section of `tests/unit/dao/work_order_assignee.spec.md`, with the substitutions above. (R2's "people of the last save" are the completers of the last completion.)

## Branch map
As `tests/unit/dao/work_order_assignee.spec.md`, same lines (10–31, 47–70, 73); lines 33–45 (`get_user_ids_by_order`) → Not specified (P3).
