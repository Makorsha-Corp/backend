# Spec — `app/dao/purchase_order_approver.py`

> **Status:** APPROVED (2026-11-01; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-01.** Q1 is the owner's own answer, not a delegated one. BUG-1200 stands from the house rule. The new bugs' rules belong to the modules named under Follow-ups, so no rule here carries those tags: these reads stay raw.

> **Shared with the family.** `expense_order_approver`, `purchase_order_approver`, `sales_order_approver`, `transfer_order_approver` and `work_order_approver` are one shape: the same two methods on the same lines, over five tables of the same shape. Everything here is shared except **What differs here**. Base behaviour is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **What differs here.** Table only, and only raw SQL can see it: `approved` has **no** database default (the other four have `false`), so a raw insert that leaves it out fails with `23502`; the ORM always sends `False`. One extra index, `ix_purchase_order_approvers_id`. The model's docstring says "Approve-only", but `set_approval` also withdraws.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `ap_1.py` … `ap_4.py` with the harness `ap_h.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\apdao\`, each transaction rolled back against `marker_test`; nothing committed). The shared checks ran once, as a loop over all five DAOs: catalog facts of all five tables; keyword-only parameters; order by `assigned_at` with ids reversed; a tie, before and after the lower `id` was approved; pending and approved rows together; 101 rows; unknown ids, `0`, another order, another workspace, a stranger; a row of workspace A on an order of workspace B; a duplicate; defaults and naive `assigned_at`; deleting a profile and an order; one statement per call, no join, no `FOR UPDATE`, no `ORDER BY` on the single lookup; a member who left, through the DAO, `approval_summary` and the notification service; a completed order. For the review round, `ap_5.py`: the real `remove_member_from_workspace` leaves the pending row on all five; the last approver removed by hand gives 0 of 0, met, on all five; a work order that never had an approver is 0 of 0, met; `sheet_entry` with one person twice saves one row with no error. **Not run:** anything over HTTP; two concurrent transactions; the intended behaviour of BUG-1200.

## Review
> All answered; applied 2026-11-01.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | A pending approver who left the workspace still holds up the order | bug — taken off open orders; an order left with none needs a new approver (BUG-1201, BUG-1202) | **owner** |

Decided by a house rule: approvers stamped with the same time come back in no fixed order (BUG-1200, HR-6).

### House-rule violations — applied automatically

- **HR-6** `get_by_order` R5 — ordered by `assigned_at` alone. On a tie the order is whatever the database produces. Verified on all five tables: two rows, one stamp; approving the lower `id` put it second on the expense, sales and work tables, and left it first on the purchase and transfer tables, so the result rests on physical row order. Ties are not rare: of 30 approvers added one after another with the default stamp, 18 to 27 repeated a stamp on this Windows machine, whose clock is coarse. Intended: `assigned_at` ascending, then `id` ascending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1200 (pattern `tied-timestamp-no-tiebreak`; one bug for the five DAOs, same line in each). Rules: `get_by_order` R5.

Checked and **not** a new line here: **HR-6** on `get_by_order_and_user` — it has no `ORDER BY`, but the unique constraint leaves at most one row (R4). **HR-5, HR-7, HR-8** — no paging, no `LIKE`. **HR-4** — the table has no soft-delete column and neither have purchase orders. **HR-9** — the DAO writes nothing. **HR-10** — the DAO only reads; `set_approval` is the check-then-write, in the purchase order manager, FU-1 (c). **HR-15** — no money. **HR-16** — no response of this DAO is affected: `list_approvers` answers 404 for another workspace's order before this read, the other callers pass the order's own workspace, and every write takes the workspace from a checked order. See `get_by_order` R2. **HR-1, HR-2, HR-3** — no user text.

### New questions

### Q1. OWNER — A pending approver who left the workspace still holds up the order — 🐞 BUG-1201, BUG-1202 (owner)
**Background:** Unless the order sets `required_approvals`, every assigned approver must approve. Removing a member from the workspace sets the membership to `inactive`, keeps the row, and touches no approver row. A new approver must be an active member, but nothing looks again afterwards. Someone who left is refused by every endpoint of the workspace (403 `You do not have access to this workspace`) and gets no notifications.
**What happens today:** Both reads return the approver rows of people who left, so they stay on the list and in the count, and cannot approve. An approval they gave before leaving stays and counts. (Verified on all five order types: 1 of 2 before and after leaving, in both cases.)
**Example:** Rahim and Karim are the approvers of purchase order PO-2026-014. Karim approves. Rahim is removed from the workspace before he has approved. Confirming the order's invoice answers 400 `Requires 2 approval(s); 1 so far`, and Rahim can never approve. It stays that way until someone takes Rahim off the order by hand.
**Rules affected:** `get_by_order` R7, `get_by_order_and_user` R5
**Suggested answer:** `bug — removing a member takes them off the pending approvers of open orders, with an approver_removed event; an approval they already gave stays and counts`. The fix is in `WorkspaceManager.remove_member_from_workspace`; these two reads stay raw and the rules keep their wording. An order left with no approver counts as 0 of 0, met, today: FU-1 (a). Alternatives: `bug — pending approvers who are no longer active stop counting, and their rows stay`, or `intended — the order's owner replaces the approver by hand`.
**Answer:** bug — removing a member takes them off the pending approvers of open orders, with an `approver_removed` event; approvals already given stay. An order left with no approvers does not pass: a new approver must be added before it can go on (owner, 2026-11-01)
**Resolution:** fix routed to `WorkspaceManager.remove_member_from_workspace` (BUG-1201). An open purchase order here means not voided, status not `Complete`, invoice not locked (the check `set_approval` applies to a withdrawal). Left with no approver, `required = 1` by BUG-1202: `AccountInvoiceService.confirm_invoice` answers 400 `Requires 1 approval(s); 0 so far` until a new approver is added and approves. A pending approver's departure with an approval already given by someone else leaves that approval standing: Karim's approval on the example order then makes 1 of 1. These two reads stay raw. Rules: `get_by_order` R7 ✅, `get_by_order_and_user` R5 ✅, unchanged; the tagged rules are in Follow-ups.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Purchase order manager** (`app/managers/purchase_order_manager.py`, not yet specified) | Read, not run. (a) **BUG-1202** (owner, 2026-11-01), logged: rule for that spec is in FU-3. (b) `add_approver` and `remove_approver` have no completed-order check, as BUG-737 and BUG-756; `set_approval` records a repeat, as BUG-757. (c) `set_approval` checks state and writes with no row lock (HR-10), as BUG-720 and BUG-744. (d) List tie: see BUG-1200. | reading the callers |
| FU-2 | **Workspace manager** (`app/managers/workspace_manager.py`, not yet specified) | **[BUG-1201]** `WorkspaceManager.remove_member_from_workspace`: every pending approver row (`approved = False`) of that member on an open order of the workspace is deleted, with one `approver_removed` event per order, written as `remove_approver` writes it (`performed_by` = the remover, metadata `user_id`, `user_name`). Rows with `approved = True` stay and count. Rows on closed orders stay. Covers all five order types. *(Today: the membership goes `inactive` and no approver row is touched. Verified.)* The fix needs a read of one user's pending rows in a workspace, which no approver DAO has; when it is added, this spec gets a section for it. On this order type: open means not voided, status not `Complete`, invoice not locked (the check `set_approval` applies to a withdrawal). | Q1 (owner) |
| FU-3 | **Purchase order manager** (`app/managers/purchase_order_manager.py`, `approval_summary`) | **[BUG-1202]** With no explicit `required_approvals` and no approvers, `required = 1`, so `met` is false; only an explicit `required_approvals = 0` waives approval, as BUG-755. *(Today: 0 of 0, met. Verified.)* | Q1 (owner) |

## Overview
`PurchaseOrderApproverDAO` reads `purchase_order_approvers`: who is assigned to approve a purchase order, and whether they have. It has two reads: all approvers of an order, and one person's row on an order. Callers: `get_by_order` is used by `PurchaseOrderManager` approval reset after an invoice is voided, `list_approvers` (`GET /purchase-orders/{id}/approvers/`), `approval_summary`, and `approval_notification_service` (who is still pending, who hears about the invoice); `get_by_order_and_user` by `PurchaseOrderManager.add_approver`, `remove_approver`, `set_approval`. Rows are written by the manager, not this DAO. It is meant to protect workspace isolation. It never writes, never commits and takes no lock.

**Callables:** 2 specified · 2 not specified
**Externals to mock:** none. No method reads the clock.
**Integration-only behavior:** none.

**Model facts (table `purchase_order_approvers`, class `PurchaseOrderApprover`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `purchase_order_id` | Integer NOT NULL, FK `purchase_orders.id` ON DELETE CASCADE | — |
| `user_id` | Integer NOT NULL, FK `profiles.id` ON DELETE CASCADE | — |
| `assigned_by` | Integer nullable, FK `profiles.id` ON DELETE SET NULL | `NULL` |
| `assigned_at` | `timestamp without time zone` NOT NULL, naive UTC | Python `utcnow`, no database default |
| `approved` | Boolean NOT NULL | Python `False`; no database default |
| `approved_at` | `timestamp without time zone`, nullable | `NULL` |

- Unique constraint `uq_po_approver_po_user` on (`purchase_order_id`, `user_id`). The workspace is not part of it. No check constraint, no trigger, no soft-delete column; no table references this one.
- `purchase_order_id` and `workspace_id` of a row are independent: the database does not require the order to belong to the row's workspace.
- Deleting a profile deletes that person's approver rows, an approval included, and nulls `assigned_by` on the rows they assigned. Deleting an order deletes its rows. (Verified. No code path that deletes a profile was found.)

**Notes for the test designer:**
- Use the module singleton `purchase_order_approver_dao` (`from app.dao.purchase_order_approver import purchase_order_approver_dao`). Every parameter after `db` is keyword-only (a positional call raises `TypeError`).
- Workspaces and profiles from `tests/unit/factories.py`. Build the order as `PurchaseOrder(workspace_id, po_number, destination_type="storage", destination_id, subtotal=0, total_amount=0, current_status_id, created_by)`, and for the ids of unrelated parents wrap that insert in `SET LOCAL session_replication_role = replica`, then `origin` (verified; a later `UPDATE` of the order checks them again). Build `PurchaseOrderApprover(workspace_id, purchase_order_id, user_id, assigned_at, …)` directly (add + flush). The session runs with `autoflush=False`: flush before calling the DAO.
- Always give `assigned_at` explicitly. Its default is bound when the model is imported, so patching `utcnow` does not change it (verified).
- **The tie (BUG-1200):** two rows of one order with one `assigned_at`, then an `UPDATE` of the **lower**-`id` row (`approved = True`, `approved_at`), flushed, then `db.expire_all()`. This rests on physical row order, which is not an order, and it did not flip on every table. Write the case to the intended result and mark it **non-strict** xfail (`strict=False`); never weaken the assertion.
- **Database errors:** wrap inserts expected to raise `IntegrityError` in `with db.begin_nested():` inside `pytest.raises(...)`.

## Not specified
- `purchase_order_approver_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods (`get`, `get_multi`, `get_by_workspace`, `get_by_id_and_workspace`, `create`, `update`, `remove`) — not overridden and with **no caller on this DAO**: managers add and delete these rows themselves. See `tests/unit/dao/base.spec.md`. The file's header says every query must filter by `workspace_id`; `get`, `get_multi` and `remove` do not, and nothing calls them here.

The checklist (`docs/testing/unit-test-checklist-by-layer.md`) marks neither method as possibly unused.

---

## `PurchaseOrderApproverDAO.get_by_order(db, *, purchase_order_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: see Overview)

**Purpose:** All approvers of one purchase order, first assigned first.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `purchase_order_id` | int | equality on the row's `purchase_order_id`; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** a `list` of `PurchaseOrderApprover` instances (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `purchase_order_id` and that `workspace_id`, approved and pending alike. Rows of another order are never returned.
- **R2.** Workspace isolation follows the row: a call with the right order id and another workspace returns `[]`. Only the row's own `workspace_id` is compared, not the order's. A row with `workspace_id` = A on an order of workspace B is returned for A and not for B. (HR-16: that row is invalid data, no code path writes one, and it cannot reach a response, because `list_approvers` answers 404 for an order of another workspace first.)
- **R3.** An unknown order id, `purchase_order_id=0`, an unknown workspace, or an order with no approvers returns `[]`.
- **R4.** Rows are ordered by `assigned_at` ascending: given rows stamped 12:00, 11:00, 10:00 in `id` order, the result is the reverse.
- **R5.** [BUG-1200] (HR-6) On an `assigned_at` tie the lowest `id` comes first. *(Today: nothing orders the tied rows. Verified: after the lower `id` was updated it came second on three of the five tables.)*
- **R6.** There is no cap: given 101 approvers, 101 rows.
- **R7.** ✅ (Q1) Membership is not looked at: the row of someone whose membership is `inactive` is returned, whether approved or not. BUG-1201 deletes pending rows at removal, in the workspace manager; a row that exists is still returned.
- **R8.** The order is not looked at. Orders have no soft delete and no completed column: completion is the order's status. The status is not looked at.
- **R9.** Rows come back as stored, and the call changes nothing.

**Errors:** none.

**Side effects:** none

---

## `PurchaseOrderApproverDAO.get_by_order_and_user(db, *, purchase_order_id, user_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: see Overview)

**Purpose:** One person's approver row on one purchase order, if there is one.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `purchase_order_id` | int | equality on the row's `purchase_order_id`; not validated |
| `user_id` | int | equality on the row's `user_id`; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** the `PurchaseOrderApprover` instance, or `None`.

**Rules:**
- **R1.** Returns the row matching the order, the user and the workspace.
- **R2.** No matching row returns `None`, with no error: a user with no row on this order (even with a row on another order), an unknown order or user id, `0` for either. Nothing is created.
- **R3.** Workspace isolation follows the row, as `get_by_order` R2: a call with another workspace returns `None`. A row of workspace A on an order of workspace B is returned for A and not for B, and it still blocks user U on that order: a new row for B fails on `uq_po_approver_po_user`.
- **R4.** At most one row can match, so no order is needed: a second row for the same order and user raises `sqlalchemy.exc.IntegrityError` (`uq_po_approver_po_user`, `23505`) at flush.
- **R5.** ✅ (Q1) Neither approval, membership nor the order is looked at: the row is returned whether approved or pending, for someone who left (Q1), and as `get_by_order` R8.

**Errors:** none raised here. The `IntegrityError` of R4 belongs to the insert.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 11–13 | keyword-only parameters | Notes for the test designer |
| 16–19 | order AND workspace; no join | `get_by_order` R1, R2, R3, R7, R8 |
| 20 | `assigned_at` ascending; no tie-break (BUG-1200) | `get_by_order` R4, R5 |
| 21 | `.all()`: no cap; empty / one / many | `get_by_order` R3, R6, R9 |
| 24–26 | keyword-only parameters | Notes for the test designer |
| 29–33 | order AND user AND workspace; no join | `get_by_order_and_user` R1, R2, R3, R5 |
| 34 | `.first()`: row / `None`; no `ORDER BY`, at most one row | `get_by_order_and_user` R1, R2, R4 |
| 38 | module singleton | Not specified |
